"""
Ce que chaque personne doit lire le matin, et rien de plus.
/ What each person must read in the morning, and nothing more.

LOCALISATION : core/services/recapitulatif_du_matin.py

SIX CHOSES SE RACONTENT (addendum du 21 aout 2026) :

1. les **wikis modifies** depuis le dernier mail de cette personne —
   par la passe de nuit comme par un humain, la distinction est portee
   par `TourDeWiki.fait_par`, et le tour dit CE QUI l'a appele
   (les notes entrees dans le perimetre) ;
2. les **notes neuves** dans ses carnets ;
3. les **commentaires neufs** sur les extractions de ses carnets —
   avec leur TEXTE et leur AUTEUR : un compte ne donne envie de
   repondre a personne ;
4. les **carnets publics** qui viennent d'apparaitre ;
5. les **wikis et syntheses neufs** dans ses carnets ;
6. les wikis dont le perimetre a recu du **neuf** que l'article n'a pas
   repris.

ON NE S'ANNONCE JAMAIS A SOI-MEME CE QU'ON VIENT DE FAIRE. Sa propre
note, son propre commentaire, son propre tour accepte, son propre
carnet public : le lendemain matin, leur auteur le sait deja. Les lui
raconter fait du recapitulatif un accuse de reception — et c'est
l'utilisateur le PLUS ACTIF qui recevrait le plus de bruit, donc celui
qui cesserait de le lire le premier.

CE QUI RESTE ANNONCE, MEME SUR SES PROPRES OBJETS : ce que LE MOTEUR a
fait. Un tour de la passe de nuit sur mon wiki est une nouvelle pour
moi — je ne l'ai pas decide, et c'est meme la seule facon de
l'apprendre sans ouvrir l'article.
/ One is never told what one did oneself — except what the ENGINE did,
which is news even on one's own wiki.

LE PERIMETRE DE CHACUN, ET POURQUOI IL N'EST PAS LE MEME PARTOUT.
Les rubriques 2, 3 et 5 portent sur les carnets qu'on SUIT — les siens
et ceux qu'on lui a partages. Elles n'incluent PAS les carnets publics
de tiers : cent notes importees dans un carnet public arroseraient
sinon tout le monde. La rubrique 4, elle, porte sur les publics — mais
elle n'annonce que le CARNET, jamais son contenu.
/ Followed notebooks for content; public ones only announce themselves.

CE QUI EMPECHE LE SPAM, et c'est la partie qui compte. « Du neuf » (6)
ne veut PAS dire « il reste des extractions ecartees » : un wiki
volontairement partiel en porte pour toujours, et l'annoncer chaque
matin serait un rappel quotidien que personne ne lirait plus au bout de
trois jours. Il faut que quelque chose soit APPARU depuis le dernier
mail — une extraction, un commentaire — ET qu'il ne soit pas repris.
/ "News" requires something new since the last mail.

Un tour qui n'a RIEN change (lot entierement rejete) n'est pas une
nouvelle : c'est un fait d'histoire, qui se lit dans l'historique de
l'article, pas dans un mail. Une REPARATION DE TITRES non plus : elle
change le texte, mais elle ne change pas ce que l'article DIT.
/ A round that changed nothing is history, not news.
"""

from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from core.models import (
    Dossier, DossierPartage, EnvoiDuRecapitulatif, MotifDeTourDeWiki, Page,
    SyntheseDirigee, TypeDeNote, VisibiliteDossier, Wiki,
)
from core.services.destinataires_de_wiki import destinataires_d_un_wiki
from core.services.nouveautes_du_perimetre import nouveautes_du_perimetre
from core.services.synthese import (
    extractions_ecartees, notes_du_perimetre_d_un_wiki,
)

# Sans envoi precedent, on regarde la derniere journee. Remonter plus
# loin ferait raconter a une nouvelle personne un mois d'histoire dans
# son tout premier mail. / A first mail covers one day, not a month.
DUREE_PAR_DEFAUT = timedelta(hours=24)

# Le delai minimal entre deux mails a la meme personne. VINGT heures,
# et non vingt-quatre : le planificateur tombe a heure fixe, et une
# journee pile ferait sauter un matin sur deux au moindre retard de
# quelques minutes.
# / Twenty hours, not twenty-four: a fixed-hour scheduler would skip
# every other morning on the slightest delay.
DELAI_ENTRE_DEUX_MAILS = timedelta(hours=20)

# Au-dela, une rubrique se resume au lieu de se derouler : un mail de
# deux cents lignes n'est plus un mail, c'est un journal. Le compte
# total est dit dans tous les cas — jamais de troncature muette.
# / Beyond this a section is summarised, never silently truncated.
LIGNES_PAR_RUBRIQUE = 10


def borne_du_destinataire(utilisateur):
    """
    Depuis quand faut-il raconter a cette personne ?
    / Since when should we tell this person?

    LOCALISATION : core/services/recapitulatif_du_matin.py

    C'EST LA BORNE HAUTE DU MAIL PRECEDENT, pas l'heure a laquelle il
    est parti. La matiere se calcule a un instant, puis les mails
    partent — ce qui prend du temps quand il y a du monde. Repartir de
    l'heure d'ENVOI ferait tomber dans un trou tout ce qui est ne entre
    les deux : ni raconte ce matin-la (pas encore calcule), ni le
    lendemain (deja passe).
    / The previous mail's high bound, not the hour it left: anything
    born in between would fall in a hole.

    `envoye_le` sert de repli pour les envois d'avant ce champ.
    / `envoye_le` is the fallback for pre-field sends.
    """
    dernier_envoi = EnvoiDuRecapitulatif.objects.filter(
        destinataire=utilisateur,
    ).first()
    if dernier_envoi is not None:
        return dernier_envoi.couvre_jusqu_a or dernier_envoi.envoye_le
    return timezone.now() - DUREE_PAR_DEFAUT


def a_deja_recu_un_recapitulatif_aujourd_hui(utilisateur):
    """
    Cette personne a-t-elle deja eu son mail du jour ?
    / Has this person already had today's mail?

    LOCALISATION : core/services/recapitulatif_du_matin.py

    LA PROMESSE « UN PAR JOUR » NE TENAIT QUE PAR ACCIDENT. La seule
    garde etait « rien de nouveau depuis le dernier envoi » : un
    commentaire arrive a 9 h, une relance a la main a 10 h, et la
    personne recevait un SECOND mail le meme jour. En exploitation par
    le planificateur seul, la promesse tenait de fait ; elle ne tenait
    pas de droit.
    / The "one a day" promise held by accident: any manual re-run after
    fresh activity sent a second mail.
    """
    depuis_une_journee = timezone.now() - DELAI_ENTRE_DEUX_MAILS
    return EnvoiDuRecapitulatif.objects.filter(
        destinataire=utilisateur, envoye_le__gt=depuis_une_journee,
    ).exists()


def carnets_suivis_par(utilisateur):
    """
    Les carnets dont on suit le CONTENU : les siens, et ceux qu'on lui
    a partages. / The notebooks whose content one follows.

    LOCALISATION : core/services/recapitulatif_du_matin.py

    PAS LES PUBLICS DE TIERS, deliberement : un carnet public est
    lisible par tout le monde, et annoncer chacune de ses notes a tout
    le monde ferait du recapitulatif un flux d'actualite. Les publics
    ont leur propre rubrique, qui annonce le carnet et rien d'autre.
    / Deliberately not third-party public notebooks: they get their own
    section, which announces the notebook and nothing else.
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return Dossier.objects.none()

    identifiants_partages = DossierPartage.objects.filter(
        Q(utilisateur=utilisateur) | Q(groupe__membres=utilisateur),
    ).values_list("dossier_id", flat=True)

    return Dossier.objects.filter(
        Q(owner=utilisateur) | Q(pk__in=identifiants_partages),
    ).distinct()


def _notes_neuves(carnets_suivis, depuis, utilisateur):
    """
    Les notes ordinaires entrees dans ces carnets depuis la borne, sauf
    les siennes. / The plain notes that entered, minus one's own.

    LOCALISATION : core/services/recapitulatif_du_matin.py

    LES WIKIS ET LES SYNTHESES SONT EXCLUS : ils ont leur rubrique. Les
    compter deux fois ferait annoncer « une note neuve » pour un article
    dont le mail parle deja trois lignes plus bas.
    / Wikis and syntheses are excluded: they have their own section.
    """
    return Page.objects.filter(
        appartenances_dossiers__dossier__in=carnets_suivis,
        created_at__gt=depuis,
        type_de_note=TypeDeNote.NOTE,
    ).exclude(owner=utilisateur).distinct().select_related(
        "owner",
    ).order_by("-created_at")


def _commentaires_neufs(carnets_suivis, depuis, utilisateur):
    """
    Les commentaires poses depuis la borne sur les extractions des
    notes de ces carnets, sauf les siens.
    / The comments posted since the bound, minus one's own.

    LOCALISATION : core/services/recapitulatif_du_matin.py

    ON REND LES OBJETS, PAS UN COMPTE : le mail montre le TEXTE et son
    AUTEUR, parce qu'un compte ne donne envie de repondre a personne.
    / Objects, not a count: the mail shows the text and its author.
    """
    from hypostasis_extractor.models import CommentaireExtraction

    return CommentaireExtraction.objects.filter(
        entity__job__page__appartenances_dossiers__dossier__in=carnets_suivis,
        entity__masquee=False,
        created_at__gt=depuis,
    ).exclude(user=utilisateur).distinct().select_related(
        "user", "entity", "entity__job__page",
    ).order_by("-created_at")


def _carnets_publics_neufs(utilisateur, depuis):
    """
    Les carnets publics apparus depuis la borne — sauf les siens.
    / Public notebooks that appeared since the bound, minus one's own.

    LOCALISATION : core/services/recapitulatif_du_matin.py
    """
    return Dossier.objects.filter(
        visibilite=VisibiliteDossier.PUBLIC,
        created_at__gt=depuis,
    ).exclude(owner=utilisateur).select_related("owner").order_by(
        "-created_at",
    )


def _articles_neufs(carnets_suivis, depuis, utilisateur):
    """
    Les wikis et syntheses dirigees nes depuis la borne dans ces
    carnets. / The wikis and directed syntheses born since the bound.

    LOCALISATION : core/services/recapitulatif_du_matin.py

    LA DATE DE NAISSANCE D'UN WIKI EST CELLE DE SA PAGE : le modele
    `Wiki` ne porte qu'un compteur de tours et une `derniere_mise_a_jour`
    (auto_now), qui dirait « neuf » a chaque mise a jour.
    / A wiki's birth date is its page's: its own date is an auto_now.
    """
    wikis = Wiki.objects.filter(
        dossier__in=carnets_suivis, page__created_at__gt=depuis,
    ).exclude(page__owner=utilisateur).select_related(
        "page", "dossier",
    ).order_by("-page__created_at")

    dirigees = SyntheseDirigee.objects.filter(
        dossier__in=carnets_suivis, produite_le__gt=depuis,
    ).exclude(produite_par=utilisateur).select_related(
        "page", "dossier", "produite_par",
    ).order_by("-produite_le")

    articles = [
        {
            "genre": "wiki", "objet": wiki, "page": wiki.page,
            "carnet": wiki.dossier, "sujet": wiki.sujet,
            "ne_le": wiki.page.created_at, "par": wiki.page.owner,
        }
        for wiki in wikis
    ] + [
        {
            "genre": "synthese", "objet": dirigee, "page": dirigee.page,
            "carnet": dirigee.dossier,
            "sujet": dirigee.page.title or "synthèse",
            "ne_le": dirigee.produite_le, "par": dirigee.produite_par,
        }
        for dirigee in dirigees
    ]
    articles.sort(key=lambda article: article["ne_le"], reverse=True)
    return articles


def _premieres(elements, combien=LIGNES_PAR_RUBRIQUE):
    """
    Les N premieres, et le total. Jamais une troncature muette : un
    mail qui montre dix lignes sur soixante doit dire soixante.
    / The first N, and the total: never a silent truncation.
    """
    elements = list(elements)
    return {
        "lignes": elements[:combien],
        "total": len(elements),
        "montre": min(combien, len(elements)),
    }


def matiere_par_destinataire(depuis_force=None):
    """
    Ce qu'il y a a dire, range par personne.
    / What there is to say, sorted by person.

    LOCALISATION : core/services/recapitulatif_du_matin.py

    :param depuis_force: une borne basse imposee, pour un ESSAI. En
        service normal, chacun a la sienne — la date de son dernier
        mail. / A forced bound, for a trial run only.
    :return: une liste de dicts, un par destinataire AYANT quelque
        chose a lire, triee par pk d'utilisateur. Une personne sans
        rien a lire n'est PAS dans la liste — pas de mail vide.
        / People with nothing to read are absent.
    """
    matiere_par_pk = {}

    def _entree_de(utilisateur):
        """L'entree de cette personne, creee au premier besoin.
        / This person's entry, created on first need."""
        entree = matiere_par_pk.get(utilisateur.pk)
        if entree is None:
            entree = {
                "utilisateur": utilisateur,
                "depuis": depuis_force or borne_du_destinataire(utilisateur),
                "wikis_modifies": [],
                "wikis_avec_du_neuf": [],
                "notes_neuves": None,
                "commentaires_neufs": None,
                "carnets_publics_neufs": None,
                "articles_neufs": None,
            }
            matiere_par_pk[utilisateur.pk] = entree
        return entree

    # ---- 1 et 6 : les wikis, modifies ou en retard sur leur perimetre.
    # / Wikis: changed, or behind their scope.
    for wiki in Wiki.objects.select_related("page", "dossier"):
        destinataires = destinataires_d_un_wiki(wiki)
        if not destinataires:
            continue

        tours_qui_ont_change = list(
            wiki.tours.exclude(texte_avant=F("texte_apres"))
            .exclude(motif=MotifDeTourDeWiki.REPARATION_DE_TITRES)
            .select_related("fait_par")
            .prefetch_related("notes_declenchantes")
        )

        notes = notes_du_perimetre_d_un_wiki(wiki)
        try:
            reste_a_reprendre = extractions_ecartees(wiki.page).count()
        except Exception:
            # Perimetre illisible (article historique) : on ne raconte
            # rien plutot que de raconter faux.
            # / Unreadable scope: say nothing rather than something false.
            reste_a_reprendre = 0

        for utilisateur in destinataires:
            entree = _entree_de(utilisateur)
            # PAS MES PROPRES TOURS, mais TOUJOURS ceux du moteur : un
            # tour de la passe de nuit sur mon wiki est une nouvelle
            # pour moi, puisque je ne l'ai pas decide.
            # / Not my own rounds, but always the engine's.
            tours_a_raconter = [
                tour for tour in tours_qui_ont_change
                if tour.fait_le > entree["depuis"]
                and tour.fait_par_id != utilisateur.pk
            ]
            if tours_a_raconter:
                entree["wikis_modifies"].append({
                    "wiki": wiki,
                    "tours": tours_a_raconter,
                    "reste_a_reprendre": reste_a_reprendre,
                })
                continue

            if not reste_a_reprendre:
                continue
            comptes = nouveautes_du_perimetre(notes, entree["depuis"])
            if comptes["total"]:
                entree["wikis_avec_du_neuf"].append({
                    "wiki": wiki,
                    "nouveautes": comptes,
                    "reste_a_reprendre": reste_a_reprendre,
                })

    # ---- 2 a 5 : ce qui est arrive dans les carnets qu'on suit.
    # Les destinataires possibles sont ceux qui suivent AU MOINS un
    # carnet : chercher tous les utilisateurs enverrait un mail vide a
    # qui n'a jamais rien ouvert.
    # / Only people who follow at least one notebook.
    from django.contrib.auth import get_user_model

    for utilisateur in get_user_model().objects.exclude(
        email="",
    ).exclude(email__isnull=True).order_by("pk"):
        carnets_suivis = carnets_suivis_par(utilisateur)
        if not carnets_suivis.exists():
            continue

        borne = depuis_force or borne_du_destinataire(utilisateur)
        notes_neuves = _premieres(
            _notes_neuves(carnets_suivis, borne, utilisateur),
        )
        commentaires = _premieres(
            _commentaires_neufs(carnets_suivis, borne, utilisateur),
        )
        publics = _premieres(_carnets_publics_neufs(utilisateur, borne))
        articles = _premieres(
            _articles_neufs(carnets_suivis, borne, utilisateur),
        )

        if not any((
            notes_neuves["total"], commentaires["total"],
            publics["total"], articles["total"],
        )):
            continue

        entree = _entree_de(utilisateur)
        entree["notes_neuves"] = notes_neuves
        entree["commentaires_neufs"] = commentaires
        entree["carnets_publics_neufs"] = publics
        entree["articles_neufs"] = articles

    return [
        entree for _pk, entree in sorted(matiere_par_pk.items())
        if _il_y_a_quelque_chose_a_dire(entree)
    ]


def _il_y_a_quelque_chose_a_dire(entree):
    """
    Une entree vide ne fait pas un mail.
    / An empty entry makes no mail.

    LOCALISATION : core/services/recapitulatif_du_matin.py
    """
    if entree["wikis_modifies"] or entree["wikis_avec_du_neuf"]:
        return True
    for rubrique in ("notes_neuves", "commentaires_neufs",
                     "carnets_publics_neufs", "articles_neufs"):
        contenu = entree[rubrique]
        if contenu and contenu["total"]:
            return True
    return False
