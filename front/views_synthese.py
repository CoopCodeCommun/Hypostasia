"""
Les endpoints de la couche synthese (SPEC-synthese § 10, phases H-I).
/ Synthesis layer endpoints (§ 10, phases H-I).

LOCALISATION : front/views_synthese.py

Toutes les reponses sont du HTML (HTMX). AllowAny avec controle PAR
OBJET, comme partout dans front/ : un carnet public est lisible par un
anonyme, l'ECRITURE sur le carnet est exigee pour creer, mettre a jour,
appliquer ou verifier.
/ HTML-only responses; per-object access control; notebook write access
required for every mutating gesture.

FLUX :
- Onglets Wikis / Syntheses de l'ecran carnet -> listes + formulaires
- Article (wiki ou synthese) -> renvois [N] cliquables -> panneau de
  preuve (GET /citations/{id}/preuve/)
- Wiki : proposer une mise a jour (tache), previsualiser les operations
  (diff avec l'AVANT, § 6.4), appliquer les retenues (applieur § 6 +
  fraicheur addendum n°1 + reindexation + tour incremente)
- Synthese dirigee : JAMAIS de mise a jour (§ 10) — le bouton est
  desactive avec son motif ; ecartees § 8 et couverture § 9 en partials
- Verifier (§ 7) : geste explicite -> tache asynchrone
"""

import logging

from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from core.models import (
    CategorieDossier, Dossier, Page, RoleDeModele, SourceLink, SyntheseDirigee,
    TypeDeNote, TypeLien, Wiki,
)
from core.services.contexte_de_citation import passage_autour_de_la_citation
from core.services.corpus import ranger_une_note_dans_un_carnet
from core.services.modeles_par_role import modele_du_role
from core.services.nouveautes_du_perimetre import (
    derniere_verification, nouveautes_du_perimetre,
)
from core.services.verification import (
    accord_des_juges_locaux, seuil_de_verification,
)
from core.services.synthese import (
    MOTIF_DE_MARQUEUR, PerimetreDExtractionsInconnu, extractions_ecartees,
    couverture_de_la_note, notes_du_perimetre_d_un_wiki,
    notes_sources_du_carnet,
)

logger = logging.getLogger(__name__)


def _acces_ou_refus(request, carnet):
    """Acces lecture au carnet, sinon la reponse de refus. / Read gate."""
    from front.views import _reponse_acces_refuse, _utilisateur_a_acces_dossier

    if not _utilisateur_a_acces_dossier(request.user, carnet):
        return _reponse_acces_refuse(request)
    return None


def _ecriture_ou_refus(request, carnet):
    """Ecriture sur le carnet, sinon le refus. / Write gate."""
    from front.views import (
        _reponse_acces_refuse, _utilisateur_peut_ecrire_dossier,
    )

    if not request.user.is_authenticated:
        return _reponse_acces_refuse(request)
    if not _utilisateur_peut_ecrire_dossier(request.user, carnet):
        return _reponse_acces_refuse(request)
    return None


def _acces_article_ou_refus(request, page_d_article):
    """Acces a un article par ses carnets. / Article access by notebooks."""
    from front.views import _reponse_acces_refuse, _utilisateur_a_acces_page

    if not _utilisateur_a_acces_page(request.user, page_d_article):
        return _reponse_acces_refuse(request)
    return None


def _html_avec_renvois(page_d_article, renvois_rendus=None):
    """
    Le HTML de l'article avec des renvois [N] CLIQUABLES : chaque
    marqueur [[ext:N]] devient une ancre vers la fiche de preuve de SON
    SourceLink, dans la colonne de droite. Le numero suit l'ordre de
    premiere apparition — jamais persiste (§ 4.4).
    / The article HTML with clickable [N] references anchored to their
    SourceLink card; numbering by first appearance, never stored.

    LOCALISATION : front/views_synthese.py

    :param renvois_rendus: une liste OPTIONNELLE que la fonction
        remplit de couples `(numero, lien)`, dans l'ordre d'apparition
        des marqueurs.

        POURQUOI UN PARAMETRE DE SORTIE, ET PAS UN SECOND APPEL. La
        colonne de droite doit lister les preuves **dans l'ordre du
        texte et avec les memes numeros**. Recalculer cette
        numerotation ailleurs en ferait une seconde copie — et deux
        copies d'une meme regle finissent toujours par diverger, ici
        sur le cas le plus retors : une extraction citee deux fois
        porte le MEME numero mais DEUX SourceLink distincts.
        Laisser le defaut a `None` garde la signature d'origine pour
        les six appelants qui ne veulent que le HTML.
        / An out-parameter, not a second pass: recomputing the numbering
        elsewhere would be a second copy of the rule, and the two would
        drift on the hardest case — one extraction, two links, one number.
    """
    import html as html_module

    import markdown

    from front.tasks import _nettoyer_le_html_de_synthese

    texte = page_d_article.text_readability or ""
    liens = list(
        SourceLink.objects.filter(
            page_cible=page_d_article, type_lien=TypeLien.CITE,
        )
        # Les avis locaux sont lus PAR LIEN pour calculer la tension :
        # sans ce prefetch, un article de 80 renvois fait 80 requetes de
        # plus. / Without this, one query per reference.
        #
        # LE RESTE SERT LA COLONNE DE DROITE, qui rend une fiche
        # COMPLETE par renvoi : sans ces jointures, un article de 63
        # citations en faisait plus de 250 requetes.
        # / The rest feeds the right-hand column, one full card per
        # reference: without these joins, 63 citations meant 250+ queries.
        .select_related(
            "extraction_source__job__page", "ancrage_source",
        )
        .prefetch_related(
            "avis_locaux",
            "extraction_source__commentaires__user",
            "extraction_source__ancrages__element",
        )
        .order_by("start_char_cible", "pk")
    )

    numero_par_extraction = {}
    jetons = {}

    def _en_jeton(correspondance):
        identifiant = int(correspondance.group(1))
        position = correspondance.start()
        if identifiant not in numero_par_extraction:
            numero_par_extraction[identifiant] = (
                len(numero_par_extraction) + 1
            )
        numero = numero_par_extraction[identifiant]
        # Le lien du couple (paragraphe, extraction) : celui dont les
        # bornes cibles contiennent la position du marqueur.
        # / The link whose target bounds contain the marker position.
        lien_du_marqueur = next(
            (lien for lien in liens
             if lien.extraction_source_id == identifiant
             and lien.start_char_cible <= position <= lien.end_char_cible),
            None,
        )
        # LE JETON EST UNIQUE PAR MARQUEUR, PAS PAR EXTRACTION, et c'est
        # ce rang qui l'y oblige. Sans lui, une extraction citee dans
        # DEUX paragraphes produisait DEUX FOIS le meme jeton : le
        # dictionnaire n'en gardait que le dernier lien, et
        # `str.replace` remplacait les deux occurrences par celui-la. Le
        # lecteur cliquait le renvoi du premier paragraphe et obtenait
        # la preuve du second — autres bornes, autre statut — et le
        # SourceLink du premier n'etait atteignable par AUCUN chemin.
        #
        # Mesure du 19 aout 2026 sur la base de demonstration : 4
        # citations sur 61 n'etaient jamais rendues sur le wiki des open
        # badges, et 4 autres l'etaient deux fois.
        #
        # Le NUMERO, lui, reste celui de l'extraction : une meme source
        # citee deux fois porte le meme [N] aux deux endroits, comme une
        # bibliographie. Seule la CIBLE differe.
        # / One token per marker, not per extraction: a twice-cited
        # extraction used to render one link twice and strand the other.
        jeton = (
            f"RENVOIJETON{numero}X{identifiant}N{len(jetons)}FIN"
        )
        jetons[jeton] = (numero, lien_du_marqueur)
        return jeton

    texte_a_rendre = MOTIF_DE_MARQUEUR.sub(_en_jeton, texte)
    html_rendu = _nettoyer_le_html_de_synthese(
        markdown.markdown(
            html_module.escape(texte_a_rendre),
            extensions=["extra", "nl2br"],
        )
    )
    for jeton, (numero, lien_du_marqueur) in jetons.items():
        if lien_du_marqueur is None:
            html_rendu = html_rendu.replace(jeton, f"[{numero}]")
            continue
        # Bouton exposant comme l'etalon (cible cliquable dediee) —
        # injecte APRES bleach, donc hors de son allowlist.
        # / Superscript button like the etalon, injected post-bleach.
        # LE CORPS DE L'ARTICLE NE PORTE AUCUN CHIFFRE, et c'est un
        # ARBITRAGE, pas un oubli (`PRESENTATION-V3.md` § 3.6). La revue
        # d'etat de l'art rapporte une correlation de **-0,96 entre la
        # precision des citations et l'utilite percue** : plus un
        # systeme est rigoureux sur ses sources, moins il est utilise.
        #
        # D'ou : AUCUN CHIFFRE dans le corps, jamais. La rigueur est
        # disponible AU CLIC — le panneau de preuve porte le degre, le
        # seuil, la citation exacte et les avis des juges locaux — pas
        # imposee a la lecture.
        #
        # REVISION DU 20 AOUT 2026 : le degre devient progressif et
        # colore la gouttiere au lieu de choisir entre trois etats. Ce
        # qui change est la GRANULARITE DE LA COULEUR, pas la presence
        # du nombre : le texte reste sans chiffre.
        # Voir PLAN/TODO/2026-08-20-le-degre-progressif-remplace-les-trois-etats.md
        #
        # Verrouille par `test_le_html_de_l_article_ne_contient_pas_le_degre`.
        # / The article body carries no number: a measured arbitration.
        # LA TENSION ENTRE LES JUGES, et rien d'autre. Le renvoi ne dit
        # jamais le DEGRE — c'est l'interdit du § 3.6 — il dit si les
        # quatre juges locaux confirment le juge de production ou le
        # dementent franchement.
        #
        # Mesure du 20 aout 2026 : la contradiction franche touche
        # **16 citations sur 209, soit 7,7 %**. C'est le seul signal que
        # les locaux apportent vraiment : la moitie d'entre eux sort de
        # la bande neutre, mais 42 % de ce signal CONTREDIT le cran.
        # / The reference never carries the degree, only whether the
        #   local judges contradict the production judge.
        from core.services.degre_agrege import tension_des_juges

        tension = tension_des_juges(
            list(lien_du_marqueur.avis_locaux.all()),
            lien_du_marqueur.score_de_verification,
        )
        attribut_de_tension = ""
        libelle_de_tension = ""
        if tension is not None:
            attribut_de_tension = f'data-accord-local="{tension}" '
            # UNE COULEUR NE SE LIT PAS TOUTE SEULE (recette F6), et
            # vert/ambre est un axe rouge-vert, aplati en deuteranopie.
            # / A colour alone is unreadable; green/amber is red-green.
            libelle_de_tension = (
                ", les contrôleurs démentent le juge"
                if tension == "tension"
                else ", les contrôleurs confirment le juge"
            )

        # UNE ANCRE, PLUS UN BOUTON HTMX. Les fiches de preuve ne sont
        # plus chargees une par une dans un tiroir : elles sont TOUTES
        # rendues dans la colonne de droite, cote a cote avec le texte.
        # Un `href="#preuve-N"` y mene donc **sans JavaScript** ; le
        # script de l'article ne fait qu'y ajouter le defilement doux et
        # le surlignage de la fiche visee.
        # / An anchor, not an HTMX button: every card is already in the
        # right-hand column, so the link works without JavaScript.
        html_rendu = html_rendu.replace(
            jeton,
            f'<a class="renvoi" href="#preuve-{lien_du_marqueur.pk}" '
            f'data-testid="synthese-renvoi" '
            f'data-lien-id="{lien_du_marqueur.pk}" '
            f'data-etat="{lien_du_marqueur.etat_de_verification}" '
            f'{attribut_de_tension}'
            f'aria-label="Source {numero}{libelle_de_tension}">'
            f'[{numero}]</a>',
        )
        if renvois_rendus is not None:
            renvois_rendus.append((numero, lien_du_marqueur))

    # LES VERDICTS AU FIL DU TEXTE (confrontation, manque n°1) : chaque
    # paragraphe devient une .affirmation[data-verification] — verte,
    # bleue debat, orange, pointillee non verifiee, ou ROUGE s'il n'a
    # AUCUNE source (§ 4.4 : un paragraphe sans marqueur est une
    # affirmation non sourcee). L'etat d'un paragraphe multi-citations
    # est le PIRE de ses verdicts : une phrase n'est pas plus fiable
    # que sa plus mauvaise preuve.
    # / Per-paragraph verification states; worst verdict wins; no
    # marker = "non_source" in red.
    import re as re_module

    # « introuvable » passe DEVANT « faible » : une preuve cassee est
    # pire qu'une preuve insuffisante. / Broken beats insufficient.
    gravite = {
        "introuvable": 6, "faible": 5, "conteste": 4, "non_verifie": 3,
        "source_debat": 2, "verifie": 1,
    }

    def _classer_le_paragraphe(correspondance):
        interieur = correspondance.group(1)
        etats_presents = re_module.findall(r'data-etat="([a-z_]+)"', interieur)
        if not etats_presents:
            etat_du_paragraphe = "non_source"
        else:
            etat_du_paragraphe = max(
                etats_presents, key=lambda e: gravite.get(e, 0),
            )
        # Le title NOMME l'etat : une couleur ne se lit pas toute
        # seule, et le lecteur ne connait pas la legende par coeur
        # (recette du 10 aout, F6). / Colour alone names nothing.
        return (
            f'<p class="affirmation" '
            f'data-verification="{etat_du_paragraphe}" '
            f'title="{_LIBELLES_DE_VERDICT.get(etat_du_paragraphe, etat_du_paragraphe)}"'
            f'>{interieur}</p>'
        )

    html_rendu = re_module.sub(
        r"<p>(.*?)</p>", _classer_le_paragraphe, html_rendu,
        flags=re_module.DOTALL,
    )
    return html_rendu


_LIBELLES_DE_VERDICT = {
    "verifie": "Vérifié : la source dit ceci mot pour mot, et l'implique.",
    "source_debat": "Source en débat : elle est contestée par des lecteurs.",
    "faible": "Faible : la source existe mais ne suffit pas à tout ce "
              "qui est affirmé.",
    "introuvable": "Citation introuvable : le passage cité n'est plus dans "
                   "la source. Soit la citation a été déformée, soit la "
                   "source a été modifiée depuis.",
    "conteste": "Contesté par un lecteur.",
    "non_verifie": "Pas encore vérifié.",
    "non_source": "Non sourcé : ce paragraphe ne cite aucune preuve.",
}


def _qualifier_une_ligne_d_article(page_d_article):
    """
    La qualification d'une ligne de liste (confrontation, manque n°7) :
    N sources · N faibles · N ecartees — la fiabilite se voit AVANT
    d'ouvrir. / List-line quality counts, visible before opening.
    """
    liens = SourceLink.objects.filter(
        page_cible=page_d_article, type_lien=TypeLien.CITE,
    )
    try:
        nombre_d_ecartees = extractions_ecartees(page_d_article).count()
    except (PerimetreDExtractionsInconnu, ValueError):
        nombre_d_ecartees = None
    return {
        "sources": liens.exclude(extraction_source__isnull=True)
        .values("extraction_source_id").distinct().count(),
        "faibles": liens.filter(etat_de_verification="faible").count(),
        "introuvables": liens.filter(
            etat_de_verification="introuvable",
        ).count(),
        "verifiees": liens.filter(etat_de_verification="verifie").count(),
        "ecartees": nombre_d_ecartees,
    }


def _contexte_d_article(request, page_d_article):
    """Le contexte commun de l'ecran article. / Shared article context."""
    enregistrement_de_wiki = Wiki.objects.filter(
        page=page_d_article,
    ).select_related("dossier").first()
    enregistrement_de_dirigee = SyntheseDirigee.objects.filter(
        page=page_d_article,
    ).select_related("dossier", "produite_par").first()
    carnet = (
        enregistrement_de_wiki.dossier if enregistrement_de_wiki
        else (enregistrement_de_dirigee.dossier
              if enregistrement_de_dirigee else None)
    )
    from front.views import _utilisateur_peut_ecrire_dossier

    liens = SourceLink.objects.filter(
        page_cible=page_d_article, type_lien=TypeLien.CITE,
    )
    # « Citations 8 » quand la numerotation s'arrete a [6] etait deux
    # chiffres sous le meme mot (confrontation, divergence 9) : on
    # compte les SOURCES DISTINCTES, et les renvois a part.
    # / Distinct sources vs reference marks: two separate counts.
    nombre_de_renvois = liens.count()
    nombre_de_sources = (
        liens.exclude(extraction_source__isnull=True)
        .values("extraction_source_id").distinct().count()
    )
    comptes_de_verdicts = {
        "verifie": liens.filter(etat_de_verification="verifie").count(),
        "faible": liens.filter(etat_de_verification="faible").count(),
        "introuvable": liens.filter(
            etat_de_verification="introuvable",
        ).count(),
        "conteste": liens.filter(etat_de_verification="conteste").count(),
    }
    # Le compteur d'ecartees vit DANS le pli (confrontation, manque 4) :
    # le chiffre est le message. None = perimetre inconnu (historique).
    # / The left-out count lives in the summary; None = unknown scope.
    try:
        nombre_d_ecartees = extractions_ecartees(page_d_article).count()
    except (PerimetreDExtractionsInconnu, ValueError):
        nombre_d_ecartees = None
    # Le fil d'Ariane « Base > Carnet > Article » : un article n'a
    # qu'UN carnet (il en est le produit), donc pas de bascule ici — le
    # menu ne s'affiche qu'a partir de deux entrees.
    # / An article belongs to exactly one notebook: no switcher here.
    from front.views_corpus import contexte_du_fil_d_ariane
    fil = contexte_du_fil_d_ariane(request, carnet=carnet) if carnet else {}
    # LES PREUVES SONT TOUTES RENDUES, dans l'ordre du texte, dans la
    # colonne de droite. Elles ne se chargent plus une par une dans un
    # tiroir qui recouvre l'article : le lecteur doit pouvoir lire le
    # texte et sa preuve COTE A COTE, comme la vue de lecture montre ses
    # extractions a cote de la note.
    # / All evidence cards are rendered, in text order, in the right-hand
    # column: the reader must be able to read text and proof side by side.
    renvois_de_l_article = []
    html_de_l_article = _html_avec_renvois(
        page_d_article, renvois_de_l_article,
    )
    second_avis_en_cours = un_second_avis_est_en_cours(page_d_article)
    # LE SEUIL EST LU UNE FOIS, pas une fois par fiche : il ne change
    # pas pendant un rendu, et le relire coutait 59 requetes.
    # / Read once: it cannot change mid-render.
    seuil_courant = seuil_de_verification()
    # Les elements des notes sources sont lus UNE FOIS PAR NOTE, pas
    # deux fois par fiche : 63 citations tirees de 6 notes coutaient
    # 65 requetes d'elements. / One read per note, not two per card.
    memoire_des_elements = {}
    preuves = [
        contexte_d_une_preuve(
            lien, numero, seuil_courant, memoire_des_elements,
        )
        for numero, lien in renvois_de_l_article
    ]
    # CE QUI EST APPARU DEPUIS, et qui donne — ou non — une raison de
    # relancer un geste couteux. Les deux lignes d'en-tete restent
    # cliquables dans tous les cas : c'est la boite de dialogue qui dit
    # ce qu'il y a, ou ce qu'il n'y a pas.
    # / What appeared since, and whether relaunching has any point.
    if enregistrement_de_wiki:
        notes_du_perimetre = notes_du_perimetre_d_un_wiki(
            enregistrement_de_wiki,
        )
        date_de_l_article = enregistrement_de_wiki.derniere_mise_a_jour
    elif enregistrement_de_dirigee:
        # Le perimetre d'une dirigee est FIGE : on interroge celui de
        # l'acte, jamais un perimetre recalcule aujourd'hui — sans quoi
        # « ce qui est nouveau » changerait de sens avec le carnet.
        # / A frozen scope: never recompute it today.
        notes_du_perimetre = enregistrement_de_dirigee.notes_du_perimetre.all()
        date_de_l_article = enregistrement_de_dirigee.produite_le
    else:
        notes_du_perimetre = Page.objects.none()
        date_de_l_article = None

    nouveautes_pour_la_maj = nouveautes_du_perimetre(
        notes_du_perimetre, date_de_l_article,
    )
    nouveautes_pour_la_verification = nouveautes_du_perimetre(
        notes_du_perimetre, derniere_verification(page_d_article),
    )

    # Quels etats de verification l'article porte-t-il REELLEMENT ? La
    # legende les annoncait tous, « non source » compris, avant meme
    # qu'une verification ait eu lieu : elle promettait des couleurs que
    # le texte n'avait pas (recette du 10 aout, F7).
    # / Which verdicts does the article actually carry? The legend
    # announced all of them before any verification had run.
    import re as _re
    etats_presents = set(
        _re.findall(r'data-verification="([a-z_]+)"', html_de_l_article)
    )
    return {
        **fil,
        "fil_note": page_d_article,
        "etats_de_verification_presents": etats_presents,
        "article": page_d_article,
        "wiki": enregistrement_de_wiki,
        "dirigee": enregistrement_de_dirigee,
        "carnet": carnet,
        "html_de_l_article": html_de_l_article,
        "preuves": preuves,
        "seuil_de_verification": seuil_courant,
        "second_avis_en_cours": second_avis_en_cours,
        "nombre_de_renvois": nombre_de_renvois,
        "nombre_de_citations": nombre_de_sources,
        "comptes_de_verdicts": comptes_de_verdicts,
        "nombre_d_ecartees": nombre_d_ecartees,
        "nouveautes_pour_la_maj": nouveautes_pour_la_maj,
        "nouveautes_pour_la_verification": nouveautes_pour_la_verification,
        "peut_ecrire": (
            request.user.is_authenticated and carnet is not None
            and _utilisateur_peut_ecrire_dossier(request.user, carnet)
        ),
    }


def _etat_de_la_tache(request, page_d_article, carnet, apres):
    """
    L'etat d'une production asynchrone, interrogeable en boucle.
    / The state of an async production, pollable.

    LOCALISATION : front/views_synthese.py

    POURQUOI. Une production (wiki, synthese) se lancait en RENVOYANT LA
    LISTE : le nouvel objet y apparaissait comme s'il etait fini —
    « tour 1 · 0 sources » — alors que la tache venait a peine de
    partir. Rien ne disait d'attendre, rien ne se rafraichissait, et
    l'utilisateur recliquait (recette du 10 aout, friction F1). La
    verification, elle, affichait un message qui ne partait JAMAIS,
    faute d'interrogation (F2). Ce point d'entree unique repond aux
    deux : tant que le job tourne il se renvoie lui-meme, et quand il
    finit il rend le resultat.

    `apres` dit quoi rendre a la fin : la LISTE apres une production
    (l'utilisateur est dans l'onglet, il voit sa ligne complete avec
    ses vrais compteurs) ou l'ARTICLE apres une verification (il y est
    deja, ce sont les verdicts qu'il attend).

    Le compteur d'essais evite la boucle sans fin : si un worker est
    mort, l'ecran finit par le DIRE au lieu d'interroger indefiniment.
    / A pollable single entry point; the attempt counter turns a dead
    worker into a message instead of an endless poll.
    """
    from hypostasis_extractor.models import ExtractionJob, ExtractionJobStatus

    identifiant_de_job = request.GET.get("job_id", "")
    if not str(identifiant_de_job).isdigit():
        return render(request, "front/corpus/partials/erreur.html", {
            "message": "Tâche introuvable : impossible de suivre cette "
                       "production.",
        }, status=400)

    job = ExtractionJob.objects.filter(
        pk=int(identifiant_de_job), page=page_d_article,
    ).first()
    if job is None:
        return render(request, "front/corpus/partials/erreur.html", {
            "message": "Tâche introuvable : impossible de suivre cette "
                       "production.",
        }, status=404)

    if job.status == ExtractionJobStatus.ERROR:
        return render(request, "front/corpus/partials/erreur.html", {
            "message": "La production a échoué. Rien n'a été modifié. "
                       "Vous pouvez relancer le geste ; si l'échec se "
                       "répète, l'erreur est dans les journaux du "
                       "serveur.",
        })

    if job.status != ExtractionJobStatus.COMPLETED:
        essais = request.GET.get("essais", "0")
        essais = int(essais) + 1 if str(essais).isdigit() else 1
        # L'ECHEANCE SUIT LE RYTHME DU FILET, pas celui de l'ancien
        # sondage. Le bandeau n'interroge plus toutes les 3 secondes :
        # il apprend la fin par le WebSocket, et ne repasse de lui-meme
        # que toutes les 25 secondes, pour le cas ou le socket est
        # coupe. Garder 100 essais aurait porte l'abandon a 40 minutes.
        # / The deadline follows the safety net's pace, not the old
        # 3-second poll: 100 tries would now mean forty minutes.
        if essais > 24:
            return render(request, "front/corpus/partials/tache_lancee.html", {
                "message": "Cette production prend plus de temps que "
                           "prévu. Elle continue peut-être en arrière-"
                           "plan : rechargez la page dans un moment "
                           "pour voir où elle en est.",
            })
        suffixe = "&apres=article" if apres == "article" else ""
        return render(request, "front/corpus/partials/tache_lancee.html", {
            "message": _MESSAGES_D_ATTENTE.get(apres, _MESSAGES_D_ATTENTE["liste"]),
            "hx_get": (
                f"{request.path}?job_id={job.pk}&essais={essais}{suffixe}"
            ),
            # Une fois finie, cette attente repond par un ARTICLE : il
            # remplace l'ecran, pas la fente qu'il occupe.
            # / When it ends this wait answers with a whole article.
            "hx_target": "#zone-lecture" if apres == "article" else None,
        })

    # Termine : on rend ce que l'utilisateur attend.
    if apres == "article":
        contexte = _contexte_d_article(request, page_d_article)
        contexte["echec_du_juge"] = _echec_du_juge(job)
        return render(request, "front/corpus/article.html", contexte)
    return None  # au caller de rendre la liste : il connait son ViewSet


def _echec_du_juge(job):
    """
    Ce que le juge n'a PAS pu juger, s'il y a lieu. / What the judge
    could not judge, if anything.

    LOCALISATION : front/views_synthese.py

    INDISPENSABLE depuis que l'echec du juge ne degrade plus rien. Une
    verification qui echoue en entier laisse desormais les verdicts
    precedents INTACTS : sans ce message, l'ecran serait rigoureusement
    identique a celui d'avant le clic, avec un job « terminé » — et
    l'utilisateur croirait que son juge a jugé. Une degradation
    silencieuse est pire qu'une erreur.

    Rend None quand tout s'est bien passe : le gabarit n'affiche alors
    aucun bandeau.
    / Since a judge failure no longer degrades anything, it must be said
    out loud, or the screen looks exactly like a success.

    :param job: l'ExtractionJob de la verification
    :return: {"sans_verdict": int, "erreur": str} ou None
    """
    bilan = (job.raw_result or {}).get("bilan_de_verification") or {}
    nombre_sans_verdict = bilan.get("sans_verdict", 0)
    erreur_du_juge = bilan.get("erreur_du_juge", "")
    if not nombre_sans_verdict and not erreur_du_juge:
        return None
    return {"sans_verdict": nombre_sans_verdict, "erreur": erreur_du_juge}


_MESSAGES_D_ATTENTE = {
    "liste": "Rédaction en cours… L'article s'affichera ici dès qu'il "
             "sera prêt. Vous pouvez quitter cette page : la production "
             "continue, et « Mes tâches » vous préviendra.",
    "article": "Vérification en cours : verbatim d'abord, puis le juge "
               "d'implication, paire par paire. Les verdicts "
               "s'afficheront ici, avec leur provenance.",
}


class WikiViewSet(viewsets.ViewSet):
    """Les wikis d'un carnet (§ 3.1, § 10). / Notebook wikis."""

    permission_classes = [permissions.AllowAny]

    def lister_pour_le_carnet(self, request, pk=None):
        """GET /carnets/{id}/wikis/ — l'onglet Wikis. / The Wikis tab."""
        carnet = get_object_or_404(Dossier, pk=pk)
        refus = _acces_ou_refus(request, carnet)
        if refus:
            return refus
        # Acces direct -> l'ecran carnet complet (le partial serait nu).
        # / Direct hit -> the full notebook screen.
        if request.method == "GET" and not request.headers.get("HX-Request"):
            from django.shortcuts import redirect
            return redirect(f"/carnets/{carnet.pk}/")
        from front.views import _utilisateur_peut_ecrire_dossier

        wikis = list(
            Wiki.objects.filter(dossier=carnet)
            .select_related("page").order_by("-derniere_mise_a_jour")
        )
        for wiki in wikis:
            wiki.qualite = _qualifier_une_ligne_d_article(wiki.page)
        return render(request, "front/corpus/liste_wikis.html", {
            "carnet": carnet,
            "wikis": wikis,
            # Le moteur ne se CHOISIT pas a la creation (recette, F10) :
            # a defaut de le choisir, l'ecran doit au moins le DIRE, et
            # dire ou il se change. C'est le modele du role REDACTEUR
            # qui s'affiche, car c'est lui qui produira l'article.
            # / The engine is not chosen here; the screen must at least
            # name it — and it names the WRITER's model, the one that
            # will actually produce the article.
            "modele_de_redaction": modele_du_role(
                RoleDeModele.REDACTEUR_D_ARTICLE,
            ),
            "nombre_de_notes_sources":
                notes_sources_du_carnet(carnet).count(),
            "peut_ecrire": (
                request.user.is_authenticated
                and _utilisateur_peut_ecrire_dossier(request.user, carnet)
            ),
        })

    def creer_pour_le_carnet(self, request, pk=None):
        """
        POST /carnets/{id}/wikis/ — cree le wiki et lance la production.
        / Creates the wiki and launches production.
        """
        carnet = get_object_or_404(Dossier, pk=pk)
        refus = _ecriture_ou_refus(request, carnet)
        if refus:
            return refus

        sujet = (request.data.get("sujet") or "").strip()
        if not sujet:
            return render(request, "front/corpus/partials/erreur.html", {
                "message": "Le sujet du wiki est obligatoire : c'est la "
                           "consigne de rédaction de l'article.",
            }, status=400)

        page_d_article = Page.objects.create(
            title=f"Wiki — {sujet}"[:500],
            text_readability="", html_readability="", html_original="",
            content_hash="", type_de_note=TypeDeNote.WIKI,
            owner=request.user,
        )
        ranger_une_note_dans_un_carnet(page_d_article, carnet, request.user)
        wiki = Wiki.objects.create(
            page=page_d_article, dossier=carnet, sujet=sujet,
        )
        identifiants_de_categories = [
            int(v) for v in request.data.getlist("categorie")
            if str(v).isdigit()
        ]
        if identifiants_de_categories:
            wiki.categories_du_perimetre.set(
                CategorieDossier.objects.filter(
                    pk__in=identifiants_de_categories,
                    liste__dossier=carnet,
                )
            )

        from hypostasis_extractor.models import ExtractionJob

        job = ExtractionJob.objects.create(
            page=page_d_article,
            ai_model=modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE),
            name=f"Wiki — {sujet}"[:200],
            prompt_description="Production d'article de wiki (phase H)",
            status="pending",
            raw_result={
                "est_wiki": True, "wiki_id": wiki.pk,
                "demandeur_id": request.user.pk,
            },
        )
        from front.tasks import produire_un_wiki_task
        produire_un_wiki_task.delay(job.pk)

        # On NE renvoie PAS la liste : elle montrerait le wiki comme
        # s'il etait fini (« tour 1 · 0 sources ») alors que la tache
        # vient de partir (recette du 10 aout, F1). On renvoie un etat
        # qui s'interroge lui-meme et laissera place a la liste.
        # / Returning the list would show the wiki as finished.
        return render(request, "front/corpus/partials/tache_lancee.html", {
            "message": _MESSAGES_D_ATTENTE["liste"],
            "hx_get": f"/wikis/{wiki.pk}/etat/?job_id={job.pk}",
        })

    @action(detail=True, methods=["GET"], url_path="etat")
    def etat(self, request, pk=None):
        """GET /wikis/{id}/etat/?job_id=N — l'avancement d'une tache.

        Rend la LISTE quand une production s'acheve, l'ARTICLE quand
        c'est une verification (?apres=article).
        / Polling endpoint: list after a production, article after a
        verification.
        """
        wiki = get_object_or_404(
            Wiki.objects.select_related("page", "dossier"), pk=pk,
        )
        refus = _acces_article_ou_refus(request, wiki.page)
        if refus:
            return refus
        apres = "article" if request.GET.get("apres") == "article" else "liste"
        reponse = _etat_de_la_tache(request, wiki.page, wiki.dossier, apres)
        if reponse is not None:
            return reponse
        return self.lister_pour_le_carnet(request, pk=wiki.dossier_id)

    def retrieve(self, request, pk=None):
        """GET /wikis/{id}/ — l'article. / The article."""
        wiki = get_object_or_404(
            Wiki.objects.select_related("page", "dossier"), pk=pk,
        )
        refus = _acces_article_ou_refus(request, wiki.page)
        if refus:
            return refus
        contexte = _contexte_d_article(request, wiki.page)
        contexte["perimetre_de_notes"] = (
            notes_du_perimetre_d_un_wiki(wiki).count()
        )
        # Acces direct (F5, lien partage) -> la page complete dans le
        # chrome ; HTMX -> le contenu seul (audit visuel n°11).
        # / Direct hit -> full page; HTMX -> content only.
        if request.headers.get("HX-Request"):
            return render(request, "front/corpus/article.html", contexte)
        contexte["article_preloaded"] = True
        return render(request, "front/base.html", contexte)

    @action(detail=True, methods=["POST"], url_path="mise_a_jour")
    def mise_a_jour(self, request, pk=None):
        """
        POST /wikis/{id}/mise_a_jour/ — lance la PROPOSITION (jamais
        l'application). / Launches the proposal, never the application.
        """
        wiki = get_object_or_404(Wiki, pk=pk)
        refus = _ecriture_ou_refus(request, wiki.dossier)
        if refus:
            return refus
        from hypostasis_extractor.models import ExtractionJob

        job = ExtractionJob.objects.create(
            page=wiki.page,
            ai_model=modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE),
            name=f"Mise à jour — {wiki.sujet}"[:200],
            prompt_description="Proposition d'opérations (phase H)",
            status="pending",
            raw_result={
                "est_maj_wiki": True, "wiki_id": wiki.pk,
                "demandeur_id": request.user.pk,
            },
        )
        from front.tasks import proposer_une_maj_de_wiki_task
        proposer_une_maj_de_wiki_task.delay(job.pk)
        return render(request, "front/corpus/partials/tache_lancee.html", {
            "message": "La proposition de mise à jour est en cours de "
                       "rédaction. Elle vous attendra ici : rien ne "
                       "sera appliqué sans votre accord.",
            "hx_get": f"/wikis/{wiki.pk}/proposition/?job_id={job.pk}",
        })

    @action(detail=True, methods=["GET"], url_path="proposition")
    def proposition(self, request, pk=None):
        """
        GET /wikis/{id}/proposition/?job_id=N — le diff des operations,
        avec l'AVANT (§ 6.4, phase I). Poll tant que la tache tourne.
        / The operations diff with the before; polls while running.
        """
        wiki = get_object_or_404(Wiki, pk=pk)
        refus = _ecriture_ou_refus(request, wiki.dossier)
        if refus:
            return refus
        from hypostasis_extractor.models import ExtractionJob

        identifiant_de_job = request.GET.get("job_id", "")
        job = get_object_or_404(
            ExtractionJob,
            pk=int(identifiant_de_job) if identifiant_de_job.isdigit() else 0,
            page=wiki.page, raw_result__est_maj_wiki=True,
        )
        if job.status in ("pending", "processing"):
            return render(
                request, "front/corpus/partials/tache_lancee.html", {
                    "message": "Proposition en cours de rédaction…",
                    "hx_get":
                        f"/wikis/{wiki.pk}/proposition/?job_id={job.pk}",
                    "recharger": True,
                },
            )
        if job.status != "completed":
            return render(request, "front/corpus/partials/erreur.html", {
                "message": job.error_message
                or "La proposition a échoué. Relancez la mise à jour.",
            }, status=200)

        # Previsualisation par UN PASSAGE A BLANC de l'applieur (§ 6.4) :
        # les rejets mecaniques et l'« avant » de chaque replace viennent
        # du meme code que l'application reelle — jamais deux verites.
        # / Preview via a dry run of the very applier used for real.
        from core.services.section_ops import appliquer_les_operations
        from core.services.synthese import extractions_du_perimetre

        identifiants_du_perimetre = set(
            extractions_du_perimetre(wiki.page).values_list("pk", flat=True)
        )
        bilan_a_blanc = appliquer_les_operations(
            wiki.page.text_readability or "",
            job.raw_result.get("operations", []),
            identifiants_du_perimetre,
        )
        return render(request, "front/corpus/partials/diff_operations.html", {
            "wiki": wiki,
            "job": job,
            "bilan": bilan_a_blanc,
            "updated_at_de_l_article":
                job.raw_result.get("updated_at_de_l_article", ""),
        })

    @action(detail=True, methods=["POST"], url_path="appliquer")
    def appliquer(self, request, pk=None):
        """
        POST /wikis/{id}/appliquer/ — applique les operations RETENUES
        par l'humain. Fraicheur d'abord (addendum n°1), reindexation,
        tour incremente, contestations perdues montrees.
        / Applies the human-retained operations; freshness first.
        """
        wiki = get_object_or_404(Wiki.objects.select_related("page"), pk=pk)
        refus = _ecriture_ou_refus(request, wiki.dossier)
        if refus:
            return refus
        from hypostasis_extractor.models import ExtractionJob

        identifiant_de_job = str(request.data.get("job_id", ""))
        job = get_object_or_404(
            ExtractionJob,
            pk=int(identifiant_de_job) if identifiant_de_job.isdigit() else 0,
            page=wiki.page, raw_result__est_maj_wiki=True,
        )

        indices_retenus = {
            int(v) for v in str(request.data.get("indices", "")).split(",")
            if v.strip().isdigit()
        }
        operations = job.raw_result.get("operations", [])
        operations_retenues = [
            operation for indice, operation in enumerate(operations)
            if indice in indices_retenus
        ]

        # LE MEME CHEMIN QUE LA PASSE DE NUIT (addendum du 21 aout 2026) :
        # fraicheur, application, ecriture du corps, historique, juges.
        # Ce qui change ici, et seulement ici : un humain a choisi les
        # operations, et c'est lui qui signe le tour.
        # / The same path the nightly pass takes; only the signer differs.
        from core.models import MotifDeTourDeWiki
        from core.services.section_ops import PropositionPerimee
        from front.tasks import appliquer_un_tour_de_wiki

        try:
            bilan, bilan_d_indexation = appliquer_un_tour_de_wiki(
                wiki, operations_retenues,
                motif=MotifDeTourDeWiki.MAJ_MANUELLE,
                fait_par=request.user,
                job=job,
                updated_at_de_la_proposition=job.raw_result.get(
                    "updated_at_de_l_article", "",
                ),
            )
        except PropositionPerimee as peremption:
            return render(request, "front/corpus/partials/erreur.html", {
                "message": str(peremption).split("/")[0].strip(),
            }, status=409)

        contexte = _contexte_d_article(request, wiki.page)
        contexte.update({
            "perimetre_de_notes": notes_du_perimetre_d_un_wiki(wiki).count(),
            "operations_appliquees": bilan["operations_appliquees"],
            "operations_rejetees": bilan["operations_rejetees"],
            # JAMAIS en silence : une contestation humaine dont la paire
            # a disparu est montree (relecture G, B1).
            # / Lost human contestations are shown, never swallowed.
            "contestations_perdues":
                bilan_d_indexation.get("contestations_perdues", []),
        })
        return render(request, "front/corpus/article.html", contexte)

    @action(detail=True, methods=["GET"], url_path="historique")
    def historique(self, request, pk=None):
        """
        GET /wikis/{id}/historique/ — l'histoire de l'article : quand,
        par qui, pourquoi, et quel ajout.
        / The article's history: when, by whom, why, what was added.

        LOCALISATION : front/views_synthese.py

        En LECTURE, pas en ecriture : quiconque peut lire l'article
        peut lire son histoire. Un lecteur qui ne peut pas ecrire a
        precisement besoin de savoir d'ou vient ce qu'il lit.
        / Read access is enough: a reader needs the provenance most.
        """
        wiki = get_object_or_404(
            Wiki.objects.select_related("page", "dossier"), pk=pk,
        )
        refus = _acces_article_ou_refus(request, wiki.page)
        if refus:
            return refus

        # Les vingt derniers tours, du plus recent au plus ancien
        # (l'ordering du modele). Au-dela, l'ecran deviendrait un
        # journal a derouler, et le total est dit dans le resume.
        # / The last twenty rounds; the total is announced.
        tours = list(
            wiki.tours.select_related("fait_par")
            .prefetch_related("operations", "notes_declenchantes")[:20]
        )
        return render(
            request, "front/corpus/partials/historique_de_wiki.html", {
                "wiki": wiki,
                "tours": tours,
                "nombre_total_de_tours": wiki.tours.count(),
            },
        )

    @action(detail=True, methods=["POST"], url_path="verifier")
    def verifier(self, request, pk=None):
        """POST /wikis/{id}/verifier/ — la verification § 7, a la
        demande. / On-demand § 7 verification."""
        wiki = get_object_or_404(Wiki, pk=pk)
        refus = _ecriture_ou_refus(request, wiki.dossier)
        if refus:
            return refus
        return _lancer_une_verification(request, wiki.page)


def _lancer_un_second_avis(demandeur_id, page_d_article):
    """
    Met en file le SECOND AVIS du juge local. / Queues the local judge's
    second opinion.

    LOCALISATION : front/views_synthese.py

    LE FAN-OUT VIT ICI, DANS LA VUE, ET SURTOUT PAS DANS LA TACHE — et
    ce n'est pas un detail de rangement. `bin/install.sh` appelle
    `verifier_les_citations_etalons` A CHAQUE DEMARRAGE DE CONTENEUR, et
    cette commande lance `verifier_les_citations_task` DIRECTEMENT. Un
    fan-out place dans la tache mettrait donc les 145 paires de l'etalon
    en file a chaque redemarrage — environ une heure de processeur —
    exactement pendant que Docling convertit les fixtures.
    Consequence assumee : l'etalon d'installation n'a PAS de second
    avis ; il faut une commande explicite pour lui en donner un.
    / The fan-out lives in the VIEW: install.sh calls the task directly
    at every container start, and would queue an hour of CPU each time.

    LE VERROU DE RE-CLIC. Le juge de production coute des secondes, donc
    un re-clic y est benin. Le juge local coute des dizaines de minutes :
    sans ce verrou, chaque re-clic empilerait un lot entier dans une
    file a concurrence 1.
    / The re-click lock: seconds for the API judge, tens of minutes here.
    """
    from hypostasis_extractor.models import ExtractionJob

    from core.services.juges_locaux import JUGES

    # LE VERROU EST BORNE DANS LE TEMPS, et c'est ce qui l'empeche de se
    # refermer pour toujours. Les taches ne sont PAS en `acks_late` : un
    # SIGKILL pendant un paquet, un OOM, ou un `docker compose down` qui
    # vide Redis pendant qu'un job est `pending` laisse ce job dans cet
    # etat DEFINITIVEMENT. Sans borne, plus aucun second avis ne
    # repartirait jamais sur cette page — et rien ne le dirait a l'ecran.
    #
    # Deux heures : bien au-dela du pire lot realiste (145 paires a 25 s
    # font une heure), et bien en-deca d'un blocage qu'on veut pouvoir
    # depasser dans la journee.
    # / A time-bounded lock: without acks_late, a killed job would hold
    # it forever and no second opinion would ever run on this page again.
    # LE VERROU ET L'AFFICHAGE POSENT LA MEME QUESTION, donc la meme
    # fonction : « un second avis tourne-t-il sur cette page ? ». Deux
    # ecritures du meme predicat auraient fini par diverger — l'une
    # bornee a deux heures, l'autre pas — et le verrou aurait interdit
    # de relancer une campagne que la colonne n'annoncait plus.
    # / One predicate, one function: two copies would have drifted, and
    # the lock would forbid relaunching a run the column no longer shows.
    if un_second_avis_est_en_cours(page_d_article):
        return None

    job = ExtractionJob.objects.create(
        page=page_d_article,
        # Pas d'`ai_model` : le juge local n'est PAS au referentiel, et
        # ne doit pas y entrer — il serait alors propose au clic comme
        # modele d'extraction, que LangExtract ne sait pas piloter.
        # / No AIModel row on purpose: it would be offered for extraction.
        ai_model=None,
        name=f"Second avis — {page_d_article.title}"[:200],
        # LES QUATRE JUGES SONT NOMMES DANS LA DESCRIPTION, pas un
        # seul : un libelle au singulier ferait croire qu'un unique
        # juge tourne, et le job qui en decoule serait illisible.
        # / Name all four: a singular label would misdescribe the job.
        prompt_description=(
            f"Avis des {len(JUGES)} juges locaux de vérification"
        ),
        status="pending",
        raw_result={
            # Un marqueur DISTINCT de `est_verification` : le menu des
            # taches liste ce dernier, et sans distinction chaque geste
            # y ferait deux lignes « Vérification », dont une d'une
            # heure. / A DISTINCT marker: the task menu lists the other.
            "est_second_avis": True,
            "demandeur_id": demandeur_id,
        },
    )
    from front.tasks import noter_avec_le_juge_local_task
    noter_avec_le_juge_local_task.delay(job.pk)
    return job


def _lancer_une_verification(request, page_d_article):
    """Cree le job de verification et lance la tache. / Launches § 7."""
    from hypostasis_extractor.models import ExtractionJob

    # Le JUGE, pas le redacteur : juger « soutient / ne_soutient_pas »
    # sur un lot de 20 paires n'est pas le meme metier que rediger un
    # article. / The JUDGE, not the writer: two opposite jobs.
    job = ExtractionJob.objects.create(
        page=page_d_article,
        ai_model=modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION),
        name=f"Vérification — {page_d_article.title}"[:200],
        prompt_description="Vérification des citations (§ 7)",
        status="pending",
        raw_result={
            "est_verification": True,
            "demandeur_id": request.user.pk,
        },
    )
    from front.tasks import verifier_les_citations_task
    verifier_les_citations_task.delay(job.pk)

    _lancer_un_second_avis(request.user.pk, page_d_article)

    # Sans hx_get, ce message restait affiche POUR TOUJOURS : les
    # verdicts n'apparaissaient qu'apres un rechargement manuel que
    # rien ne suggerait (recette du 10 aout, F2).
    # / Without hx_get this message never went away.
    from core.models import Wiki as ModeleWiki
    enregistrement_de_wiki = ModeleWiki.objects.filter(
        page=page_d_article,
    ).only("pk").first()
    racine = (
        f"/wikis/{enregistrement_de_wiki.pk}" if enregistrement_de_wiki
        else f"/syntheses/{page_d_article.pk}"
    )
    return render(request, "front/corpus/partials/tache_lancee.html", {
        "message": _MESSAGES_D_ATTENTE["article"],
        "hx_get": f"{racine}/etat/?job_id={job.pk}&apres=article",
        "hx_target": "#zone-lecture",
    })


class SyntheseViewSet(viewsets.ViewSet):
    """Les syntheses dirigees (§ 3.2, § 10). / Frozen syntheses."""

    permission_classes = [permissions.AllowAny]

    def lister_pour_le_carnet(self, request, pk=None):
        """GET /carnets/{id}/syntheses/ — l'onglet. / The tab."""
        carnet = get_object_or_404(Dossier, pk=pk)
        refus = _acces_ou_refus(request, carnet)
        if refus:
            return refus
        # Acces direct -> l'ecran carnet complet (le partial serait nu).
        # / Direct hit -> the full notebook screen.
        if request.method == "GET" and not request.headers.get("HX-Request"):
            from django.shortcuts import redirect
            return redirect(f"/carnets/{carnet.pk}/")
        from front.views import _utilisateur_peut_ecrire_dossier

        syntheses = list(
            SyntheseDirigee.objects.filter(dossier=carnet)
            .select_related("page", "produite_par")
            .order_by("-produite_le")
        )
        for synthese in syntheses:
            synthese.qualite = _qualifier_une_ligne_d_article(synthese.page)
        axes = list(
            carnet.listes_de_categories.prefetch_related(
                "categories_de_dossier",
            )
        )
        return render(request, "front/corpus/liste_syntheses.html", {
            "carnet": carnet,
            "syntheses": syntheses,
            "axes": axes,
            # Meme raison que pour le wiki (recette, F10).
            "modele_de_redaction": modele_du_role(
                RoleDeModele.REDACTEUR_D_ARTICLE,
            ),
            "nombre_de_notes_sources":
                notes_sources_du_carnet(carnet).count(),
            "peut_ecrire": (
                request.user.is_authenticated
                and _utilisateur_peut_ecrire_dossier(request.user, carnet)
            ),
        })

    def creer_pour_le_carnet(self, request, pk=None):
        """
        POST /carnets/{id}/syntheses/ — fige le perimetre AU MOMENT DU
        GESTE (§ 3.2) et lance la production. Le garde-fou § 3.3 est
        mecanique : notes_sources_du_carnet exclut les syntheses.
        / Freezes the scope at request time and launches production.
        """
        carnet = get_object_or_404(Dossier, pk=pk)
        refus = _ecriture_ou_refus(request, carnet)
        if refus:
            return refus

        titre = (request.data.get("titre") or "").strip()
        if not titre:
            return render(request, "front/corpus/partials/erreur.html", {
                "message": "Le titre de la synthèse est obligatoire : "
                           "c'est ce que le collectif adoptera.",
            }, status=400)

        notes_retenues = notes_sources_du_carnet(carnet)
        categorie_de_direction = None
        identifiant_de_categorie = str(request.data.get("categorie_id", ""))
        if identifiant_de_categorie.isdigit():
            categorie_de_direction = CategorieDossier.objects.filter(
                pk=int(identifiant_de_categorie), liste__dossier=carnet,
            ).first()
            if categorie_de_direction is not None:
                notes_retenues = notes_retenues.filter(
                    appartenances_dossiers__dossier=carnet,
                    appartenances_dossiers__categories=categorie_de_direction,
                )
        notes_figees = list(notes_retenues.values_list("pk", flat=True))

        page_de_synthese = Page.objects.create(
            title=titre[:500],
            text_readability="", html_readability="", html_original="",
            content_hash="", type_de_note=TypeDeNote.SYNTHESE,
            owner=request.user,
        )
        ranger_une_note_dans_un_carnet(page_de_synthese, carnet, request.user)
        synthese_dirigee = SyntheseDirigee.objects.create(
            page=page_de_synthese, dossier=carnet,
            produite_par=request.user, produite_le=timezone.now(),
            categorie_de_direction=categorie_de_direction,
            axe_de_direction=(
                categorie_de_direction.liste
                if categorie_de_direction else None
            ),
            perimetre_d_extractions_fige=True,
        )
        synthese_dirigee.notes_du_perimetre.set(notes_figees)

        from hypostasis_extractor.models import ExtractionJob

        job = ExtractionJob.objects.create(
            page=page_de_synthese,
            ai_model=modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE),
            name=titre[:200],
            prompt_description="Synthèse dirigée de carnet (phase H)",
            status="pending",
            raw_result={
                "est_synthese_carnet": True,
                "demandeur_id": request.user.pk,
                "notes_du_perimetre": notes_figees,
            },
        )
        from front.tasks import produire_une_synthese_de_carnet_task
        produire_une_synthese_de_carnet_task.delay(job.pk)

        # Meme raison que pour le wiki (recette du 10 aout, F1) : la
        # liste montrerait la synthese comme si elle etait redigee.
        # / Same as the wiki: the list would look finished.
        return render(request, "front/corpus/partials/tache_lancee.html", {
            "message": _MESSAGES_D_ATTENTE["liste"],
            "hx_get": f"/syntheses/{page_de_synthese.pk}/etat/?job_id={job.pk}",
        })

    @action(detail=True, methods=["GET"], url_path="etat")
    def etat(self, request, pk=None):
        """GET /syntheses/{page_id}/etat/?job_id=N — l'avancement.

        L'identifiant est celui de la PAGE, comme partout dans ce
        ViewSet. / The id is the PAGE id, as everywhere here.
        """
        page_de_synthese = get_object_or_404(
            Page, pk=pk, type_de_note=TypeDeNote.SYNTHESE,
        )
        refus = _acces_article_ou_refus(request, page_de_synthese)
        if refus:
            return refus
        enregistrement = SyntheseDirigee.objects.filter(
            page=page_de_synthese,
        ).select_related("dossier").first()
        carnet_de_la_synthese = enregistrement.dossier if enregistrement else None
        apres = "article" if request.GET.get("apres") == "article" else "liste"
        reponse = _etat_de_la_tache(
            request, page_de_synthese, carnet_de_la_synthese, apres,
        )
        if reponse is not None:
            return reponse
        if carnet_de_la_synthese is None:
            # Une synthese sans carnet (dossier SET_NULL, ecart assume
            # de l'addendum n°5) n'a pas de liste ou retourner : on rend
            # l'article. / A notebook-less synthesis has no list.
            contexte = _contexte_d_article(request, page_de_synthese)
            return render(request, "front/corpus/article.html", contexte)
        return self.lister_pour_le_carnet(request, pk=carnet_de_la_synthese.pk)

    def retrieve(self, request, pk=None):
        """GET /syntheses/{page_id}/ — l'article fige. / The frozen
        article. L'identifiant est celui de la PAGE de l'article."""
        page_de_synthese = get_object_or_404(
            Page, pk=pk, type_de_note=TypeDeNote.SYNTHESE,
        )
        refus = _acces_article_ou_refus(request, page_de_synthese)
        if refus:
            return refus
        contexte = _contexte_d_article(request, page_de_synthese)
        if request.headers.get("HX-Request"):
            return render(request, "front/corpus/article.html", contexte)
        contexte["article_preloaded"] = True
        return render(request, "front/base.html", contexte)

    @action(detail=True, methods=["GET"], url_path="ecartees")
    def ecartees(self, request, pk=None):
        """GET /syntheses/{page_id}/ecartees/ — § 8, jamais une liste
        stockee. / § 8 partial, always computed."""
        page_de_synthese = get_object_or_404(Page, pk=pk)
        refus = _acces_article_ou_refus(request, page_de_synthese)
        if refus:
            return refus
        try:
            toutes_les_ecartees = extractions_ecartees(page_de_synthese)
            # La fenetre de 200 est ANNONCEE (recette du 10 aout, B3) :
            # le resume disait « 458 » quand le volet en montrait 200,
            # sans un mot. Le total est passe au template.
            # / The 200-row window is announced; the total is passed.
            nombre_total_d_ecartees = toutes_les_ecartees.count()
            ecartees = list(
                toutes_les_ecartees.select_related("job__page")[:200]
            )
            perimetre_inconnu = False
        except PerimetreDExtractionsInconnu:
            # Une dirigee historique : dire « inconnu » plutot que
            # mentir « 100 % ecarte » (relecture E, I2).
            # / Historical synthesis: say "unknown", never lie.
            ecartees = []
            nombre_total_d_ecartees = 0
            perimetre_inconnu = True

        # GROUPEES PAR DOCUMENT, et chaque document se deplie.
        #
        # POURQUOI. La liste etait plate : 200 lignes ou chaque citation
        # redisait le nom de sa note en petit, a droite. Sur un perimetre
        # de six notes, c'etait six noms repetes jusqu'a 200 fois, et
        # aucun moyen de repondre a la seule question qu'on se pose
        # vraiment — « qu'est-ce que le modele a laisse de CE
        # document-la ? ».
        # / A flat list repeated six note names up to 200 times and
        # could not answer the only question that matters: what did the
        # model leave out OF THIS document?
        groupes = {}
        for extraction in ecartees:
            note = extraction.job.page
            groupes.setdefault(note.pk, {"note": note, "extractions": []})
            groupes[note.pk]["extractions"].append(extraction)
        # Le document qui a le plus ete ecarte vient en tete : c'est
        # celui sur lequel la question se pose.
        # / The most-skipped document leads: that is where the question is.
        ecartees_par_document = sorted(
            groupes.values(),
            key=lambda groupe: -len(groupe["extractions"]),
        )
        return render(request, "front/corpus/partials/ecartees.html", {
            "article": page_de_synthese,
            "ecartees_par_document": ecartees_par_document,
            "nombre_total_d_ecartees": nombre_total_d_ecartees,
            "nombre_affiche": len(ecartees),
            "perimetre_inconnu": perimetre_inconnu,
        })

    @action(detail=True, methods=["GET"], url_path="couverture")
    def couverture(self, request, pk=None):
        """GET /syntheses/{page_id}/couverture/ — § 9, la jointure par
        note du perimetre. / § 9 partial, per scoped note."""
        page_de_synthese = get_object_or_404(Page, pk=pk)
        refus = _acces_article_ou_refus(request, page_de_synthese)
        if refus:
            return refus
        dirigee = SyntheseDirigee.objects.filter(
            page=page_de_synthese,
        ).first()
        notes = (
            list(dirigee.notes_du_perimetre.all()) if dirigee else []
        )
        couvertures = [
            {"note": note, **couverture_de_la_note(note)}
            for note in notes
        ]
        return render(request, "front/corpus/partials/couverture.html", {
            "article": page_de_synthese,
            "couvertures": couvertures,
        })

    @action(detail=True, methods=["POST"], url_path="verifier")
    def verifier(self, request, pk=None):
        """POST /syntheses/{page_id}/verifier/ — § 7 a la demande."""
        page_de_synthese = get_object_or_404(Page, pk=pk)
        dirigee = SyntheseDirigee.objects.filter(
            page=page_de_synthese,
        ).select_related("dossier").first()
        carnet = dirigee.dossier if dirigee else None
        if carnet is None:
            from front.views import _reponse_acces_refuse
            return _reponse_acces_refuse(request)
        refus = _ecriture_ou_refus(request, carnet)
        if refus:
            return refus
        return _lancer_une_verification(request, page_de_synthese)


def un_second_avis_est_en_cours(page_d_article):
    """
    Une campagne de juges locaux tourne-t-elle sur cet article ?
    / Is a local-judge run under way on this article?

    LOCALISATION : front/views_synthese.py

    « EN COURS » ET « JAMAIS DEMANDE » NE SE CONFONDENT PAS. La doctrine
    maison veut qu'une degradation silencieuse soit pire qu'une erreur :
    une barre absente ne doit pas se lire comme un zero.

    LA BORNE DE DEUX HEURES EST CELLE DU VERROU DE RE-CLIC, et pour la
    meme raison : les taches ne sont PAS en `acks_late`. Un SIGKILL, un
    OOM ou un `docker compose down` qui vide Redis laisse un job
    `pending` DEFINITIVEMENT. Sans borne, la colonne afficherait « avis
    en cours… » pour toujours, sur toutes les citations de la page, sans
    que rien ne le dise.
    / A dead pending job would show "running…" forever, on every card.
    """
    from datetime import timedelta

    from hypostasis_extractor.models import ExtractionJob

    return ExtractionJob.objects.filter(
        page=page_d_article,
        status__in=["pending", "processing"],
        created_at__gte=timezone.now() - timedelta(hours=2),
        raw_result__contains={"est_second_avis": True},
    ).exists()


def contexte_d_une_preuve(lien, numero=None, seuil=None,
                          memoire_des_elements=None):
    """
    Le contexte d'UNE fiche de preuve. / One evidence card's context.

    LOCALISATION : front/views_synthese.py

    UN SEUL ENDROIT POUR DEUX APPELANTS : la colonne de droite, qui en
    rend une par renvoi, et `CitationViewSet.preuve`, qui en rend une
    seule. Deux constructions du meme contexte finiraient par diverger,
    et le lecteur verrait deux fiches differentes pour la meme citation
    selon le chemin d'acces.
    / One builder for two callers: otherwise the same citation would
    render differently depending on how it was reached.

    LE TRI DES AVIS SE FAIT EN MEMOIRE, pas par `order_by` : la colonne
    prefetch les avis de tous les liens en une requete, et un `order_by`
    sur le manager relancerait une requete PAR FICHE — ce que le
    prefetch existait justement pour eviter.
    / Sorted in memory: an order_by on the related manager would defeat
    the prefetch and issue one query per card.
    """
    extraction = lien.extraction_source
    # Par score DECROISSANT : le lecteur compare des barres, et des
    # barres en desordre se comparent mal.
    # / By descending score: the reader compares bars.
    avis_locaux = sorted(
        lien.avis_locaux.all(), key=lambda un_avis: -un_avis.score,
    )
    return {
        "numero": numero,
        "lien": lien,
        "extraction": extraction,
        "note_source": extraction.job.page if extraction else None,
        # LE TEXTE QUI ENTOURE LA CITATION, en DEUX longueurs :
        # l'apercu, et ce que le clic sur la citation ouvre. Une
        # citation sortie de son paragraphe se lit mal, et parfois faux.
        # Le service rend des chaines vides quand l'ancre est detachee :
        # ses positions sont perimees, et un contexte decoupe dessus
        # serait une invention presentee comme une preuve.
        # / Two lengths; empty when the anchor is stale.
        "passage": passage_autour_de_la_citation(
            extraction, memoire_des_elements,
        ),
        "avis_locaux": avis_locaux,
        # LA VERSION DU PROTOCOLE, quand les juges la PARTAGENT — et
        # None sinon. Recopiee sur chaque barre elle n'identifie
        # personne, elle remplit ; mais la factoriser quand elle n'est
        # pas commune mentirait sur les autres juges, et le § 7.2 veut
        # que l'etat porte son verificateur — version comprise.
        # / Factored out only when actually shared (§ 7.2).
        "version_commune": _version_commune_des_avis(avis_locaux),
        # (combien confirment, combien d'avis), ou None quand la
        # comparaison est IMPOSSIBLE — et c'est le cas ORDINAIRE tant
        # qu'un article n'a pas ete reverifie.
        # / None is the ordinary case, not an exception.
        "accord_local": accord_des_juges_locaux(lien, seuil),
    }


def _version_commune_des_avis(avis_locaux):
    """
    La version de protocole que TOUS les avis partagent, ou None.
    / The protocol version shared by ALL opinions, or None.

    LOCALISATION : front/views_synthese.py

    POURQUOI CE N'EST PAS UNE CONSTANTE. `methode()` prefixe la version
    a chaque avis d'un meme lot — « xnli-directe v1 — bge-m3 ». Recopiee
    sur les quatre barres de la fiche, elle n'identifie personne. Mais
    deux lots juges a des dates differentes peuvent porter deux
    versions : la factoriser alors mentirait sur les avis de l'autre
    lot. On ne la sort de la ligne que si elle est VRAIMENT commune.
    / Only factored out when genuinely shared: two batches can differ.

    :param avis_locaux: des `AvisDeVerification`.
    :return: la version, ou None — y compris quand la liste est vide.
    """
    versions = {un_avis.version for un_avis in avis_locaux}
    if len(versions) == 1:
        return versions.pop() or None
    return None


class CitationViewSet(viewsets.ViewSet):
    """Le panneau de preuve d'une citation. / The evidence panel."""

    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=["GET"], url_path="preuve")
    def preuve(self, request, pk=None):
        """
        GET /citations/{id}/preuve/ — la citation exacte, son etat de
        verification AVEC provenance, le debat joint, le retour a la
        source. / Exact quote, provenanced verdict, debate, deep link.

        ⚠️ AUCUN GABARIT N'APPELLE PLUS CETTE ROUTE. Les fiches sont
        TOUTES rendues dans la colonne de l'article, et le renvoi [N]
        est une ancre, plus un `hx-get`. Elle reste parce qu'elle rend
        la MEME fiche par le MEME constructeur de contexte
        (`contexte_d_une_preuve`) : c'est la couture par laquelle les
        tests du 20 aout examinent une fiche isolement, sans monter
        tout un article. Ne pas la lire comme le chemin de l'interface.
        / No template calls this route any more: every card is rendered
        in the article's column. It stays as the test seam that renders
        one card through the same context builder.
        """
        lien = get_object_or_404(
            SourceLink.objects.select_related(
                "page_cible", "extraction_source__job__page",
                "ancrage_source",
            ).prefetch_related("extraction_source__commentaires__user",
                               "commentaires_source"),
            pk=pk, type_lien=TypeLien.CITE,
        )
        refus = _acces_article_ou_refus(request, lien.page_cible)
        if refus:
            return refus
        second_avis_en_cours = un_second_avis_est_en_cours(lien.page_cible)

        # LE DEGRE ET SON SEUIL VONT ENSEMBLE, TOUJOURS. Un « soutenu a
        # 45 sur 100 » ne veut rien dire sans la barre a partir de
        # laquelle on compte : c'est ce qui rend l'etat CONTESTABLE SUR
        # LE BON OBJET — on discute le seuil, pas le verdict.
        # / The degree and its threshold always travel together.
        contexte = contexte_d_une_preuve(lien)
        contexte["seuil_de_verification"] = seuil_de_verification()
        contexte["second_avis_en_cours"] = second_avis_en_cours
        return render(
            request, "front/corpus/partials/preuve.html", contexte,
        )
