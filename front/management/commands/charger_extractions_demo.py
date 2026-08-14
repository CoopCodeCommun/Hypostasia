"""
Pose a la main, sans appeler aucun LLM, les extractions de demonstration
sur les notes etalons.
/ Hand-place demonstration extractions on the reference notes, no LLM call.

LOCALISATION : front/management/commands/charger_extractions_demo.py

POURQUOI CETTE COMMANDE EXISTE

Apres `charger_fixtures_sample`, la base porte six notes et 670 elements
mais ZERO extraction : le panneau affiche « 0 extractions » et il n'y a
aucune carte a styler. Lancer une vraie analyse coute un appel facture,
ne se rejoue pas, et ne garantit pas de produire les cas limites que la
maquette dessine — les marques imbriquees, l'ancre sur un tableau, la
carte a deux commentaires.

CE QUE LA TABLE CI-DESSOUS COUVRE EXPRES

  · les 8 familles d'hypostases (extractor_tags.py:16-62)
  · les 2 statuts de debat, obtenus en posant des commentaires
  · deux idees SUPERPOSEES sur un meme element (marques imbriquees)
  · une idee qui ENJAMBE deux elements (deux ancrages, deux <mark>)
  · une ancre portee par un element `table`
  · des ancres sur des tours de parole audio
  · des cartes a 0, 1 et 2 commentaires

COMMENT LES POSITIONS SONT CALCULEES

Jamais en dur. Chaque portion declare un FRAGMENT litteral ; la commande
le cherche dans le texte de l'element et en deduit les bornes. Si le
fragment a disparu — parce que la note etalon a change — la commande
LEVE plutot que d'ancrer a cote : une ancre fausse produit un surlignage
decale que rien ne signale.
/ Offsets are derived from literal fragments, never hardcoded. A missing
fragment raises instead of silently anchoring at the wrong place.

Usage :
    uv run python manage.py charger_extractions_demo
    uv run python manage.py charger_extractions_demo --reset
    uv run python manage.py charger_extractions_demo --a-blanc
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Page
from hypostasis_extractor.models import (
    AncrageExtraction,
    CommentaireExtraction,
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)

User = get_user_model()


# Nom qui distingue un job pose par cette commande d'un job d'analyse reel.
# Le --reset ne touche QUE ceux-la.
# / Name telling a demo job from a real analysis job; --reset only drops these.
NOM_DU_JOB_DE_DEMONSTRATION = "Démonstration — idées posées à la main"


# Les commentateurs de la maquette.
#
# LE PREFIXE `demo_` N'EST PAS DECORATIF. Une premiere version prenait
# `jonas` tel quel : `get_or_create` a trouve le COMPTE REEL du
# mainteneur — celui avec lequel il se connecte — et lui a attribue des
# phrases qu'il n'a jamais ecrites. Symetriquement, un vrai commentaire
# de ce compte sur une extraction de demonstration serait detruit par le
# `--reset`, qui cascade depuis le job.
#
# Le prenom, lui, reste sans prefixe : c'est le gabarit de carte qui
# l'affiche (`_card_body.html:117`), et le fil doit se lire « Sonia »,
# pas « Demo Sonia ».
# / The `demo_` prefix keeps fixture comments off real accounts: the
# first version borrowed the maintainer's own login.
COMMENTATEURS = {
    "demo_jonas": "Jonas",
    "demo_sonia": "Sonia",
    "demo_amina": "Amina",
}


# Chaque idee : ses attributs de carte, ses portions (ordre d'element +
# fragment litteral), et ses commentaires.
# / Each idea: card attributes, portions (element order + literal fragment),
# and comments.
IDEES_DE_DEMONSTRATION = {
    # -----------------------------------------------------------------
    # Note PDF a coordonnees — porte le tableau et la superposition
    # / Coordinate-bearing PDF note — carries the table and the overlap
    # -----------------------------------------------------------------
    "Étude épistémologique de l'IA": [
        {
            "hypostases": "PHENOMENE",
            "resume": "Les architectures d'IA actuelles ne se ramènent à "
                      "aucune des six formes canoniques du raisonnement.",
            "mots_cles": "raisonnement, architectures",
            "portions": [
                (2, "sont structurellement irréductibles aux six formes "
                    "canoniques de raisonnement de l'épistémologie classique"),
            ],
            "commentaires": [],
        },
        {
            # Imbriquee dans la precedente : c'est elle qui fait naitre les
            # marques imbriquees du § 4 de la maquette.
            # / Nested inside the previous one: this is what produces the
            # nested marks of the mockup's § 4.
            "hypostases": "THEORIE",
            "resume": "Le noyau de la thèse : une irréductibilité de forme, "
                      "pas de degré.",
            "mots_cles": "irréductibilité, formes canoniques",
            "portions": [
                (2, "irréductibles aux six formes canoniques"),
            ],
            "commentaires": [
                ("demo_sonia", "« Irréductible » est un mot fort. Irréductible "
                          "en pratique, ou démontré ?"),
                ("demo_amina", "Démontré, mais sous les hypothèses de la section "
                          "2. Hors de ces hypothèses, on ne sait pas."),
            ],
        },
        {
            "hypostases": "CONJECTURE",
            "resume": "L'appui théorique repose sur trois résultats "
                      "spectraux empruntés à la mécanique quantique.",
            "mots_cles": "Mackey, Gleason, Parthasarathy",
            "portions": [
                (2, "les théorèmes spectraux de Mackey, Gleason et le "
                    "plongement de Parthasarathy"),
            ],
            "commentaires": [
                ("demo_jonas", "Emprunt élégant, mais le transfert au cas "
                          "neuronal mérite d'être explicité."),
            ],
        },
        {
            "hypostases": "PROBLEME",
            "resume": "Une anomalie de transcription entache le manuscrit "
                      "d'origine.",
            "mots_cles": "transcription, matrice",
            "portions": [
                (7, "une anomalie de transcription dans le manuscrit originel"),
            ],
            "commentaires": [],
        },
        {
            # Ancre portee par un element `table` : 4 471 signes d'un seul
            # tenant (mesure sur la note etalon le 12 aout ; le second
            # tableau en fait 1 544). La gouttiere designera « ce passage »
            # en montrant tout le tableau — point de conception laisse au
            # mainteneur.
            # / Anchor on a `table` element: the gutter will point at the
            # whole table. That design call is left to the maintainer.
            "hypostases": "DONNEE",
            "resume": "Le tableau de correspondance aligne chaque catégorie "
                      "épistémologique sur son ancrage documentaire.",
            "mots_cles": "tableau, correspondance",
            "portions": [
                (4, "Argument extrait du document d'audit"),
            ],
            "commentaires": [],
        },
    ],
    # -----------------------------------------------------------------
    # Note web — porte l'idee qui enjambe deux elements
    # / Web note — carries the idea spanning two elements
    # -----------------------------------------------------------------
    "Badgeons la Normandie": [
        {
            "hypostases": "PRINCIPE",
            "resume": "Les badges ouverts naissent d'un manque : rien ne "
                      "reconnaissait les apprentissages informels.",
            "mots_cles": "reconnaissance, informel",
            "portions": [
                (1, "combler un manque dans les outils de reconnaissance "
                    "des apprentissages informels"),
            ],
            "commentaires": [
                ("demo_sonia", "C'est le point de départ historique, à garder "
                          "en tête de la synthèse."),
            ],
        },
        {
            "hypostases": "INVARIANT",
            "resume": "La reconnaissance se décline en deux régimes, formel "
                      "et informel, sans hiérarchie entre eux.",
            "mots_cles": "formel, informel",
            "portions": [
                (8, "La reconnaissance peut être formelle (certification ou "
                    "accréditation) ou informelle (endossement)"),
            ],
            "commentaires": [],
        },
        {
            # DEUX portions : l'idee deborde du list_item « critères » sur le
            # list_item « preuves ». Deux ancrages, deux <mark>.
            # / TWO portions: the idea spans two list items.
            "hypostases": "METHODE",
            "resume": "Ce qu'un badge démontre et ce qui le prouve sont deux "
                      "métadonnées distinctes, portées ensemble.",
            "mots_cles": "critères, preuves",
            "portions": [
                (5, "qu'est-ce que le badge démontre/indique"),
                (6, "preuves : les éléments produits par le récepteur"),
            ],
            "commentaires": [],
        },
        {
            "hypostases": "MODE",
            "resume": "Accumulés, les badges cessent d'être des jetons "
                      "isolés et deviennent un profil.",
            "mots_cles": "collection, profil",
            "portions": [
                (8, "une collection de badges permet à une personne de bâtir "
                    "des profils"),
            ],
            "commentaires": [],
        },
    ],
    # -----------------------------------------------------------------
    # Note audio — ancres sur tours de parole
    # / Audio note — anchors on speech turns
    # -----------------------------------------------------------------
    "Palais César — deux locuteurs": [
        {
            "hypostases": "EVENEMENT",
            "resume": "La question qui donne son objet à l'échange.",
            "mots_cles": "césar, habitation",
            "portions": [
                (6, "Est-ce que César a vécu ici?"),
            ],
            "commentaires": [
                ("demo_amina", "La réponse arrive au tour suivant : non."),
            ],
        },
        {
            "hypostases": "PARADOXE",
            "resume": "Le lieu porte le nom de César sans avoir été le sien.",
            "mots_cles": "toponymie, attribution",
            "portions": [
                (3, "c'est pas le vrai palais de César"),
            ],
            "commentaires": [],
        },
        {
            "hypostases": "CROYANCE",
            "resume": "L'intuition du locuteur précède la confirmation.",
            "mots_cles": "intuition, confirmation",
            "portions": [
                (8, "j'en étais sûr"),
            ],
            "commentaires": [],
        },
    ],
}


class Command(BaseCommand):
    help = (
        "Pose les extractions de démonstration sur les notes étalons, "
        "sans appeler de LLM."
    )

    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--reset",
            action="store_true",
            help="Supprime les extractions de démonstration avant de les reposer.",
        )
        analyseur_d_arguments.add_argument(
            "--a-blanc",
            action="store_true",
            help="Annonce ce qui serait fait, sans rien écrire en base.",
        )

    def handle(self, *args, **options):
        remise_a_zero_demandee = options["reset"]
        execution_a_blanc = options["a_blanc"]

        if execution_a_blanc:
            self._annoncer_sans_ecrire()
            return

        with transaction.atomic():
            if remise_a_zero_demandee:
                self._supprimer_les_jobs_de_demonstration()

            commentateurs = self._preparer_les_commentateurs()

            for titre_de_la_note, idees in IDEES_DE_DEMONSTRATION.items():
                self._charger_une_note(titre_de_la_note, idees, commentateurs)

        self.stdout.write(self.style.SUCCESS(
            f"{ExtractedEntity.objects.count()} extraction(s) en base, "
            f"{AncrageExtraction.objects.count()} ancrage(s), "
            f"{CommentaireExtraction.objects.count()} commentaire(s)."
        ))

    # -------------------------------------------------------------------
    # Le chargement d'une note
    # / Loading one note
    # -------------------------------------------------------------------

    def _charger_une_note(self, titre_de_la_note, idees, commentateurs):
        """
        Pose les idees d'une note. Une note absente est nommee et sautee.
        / Place one note's ideas. A missing note is named and skipped.
        """
        page_de_la_note = Page.objects.filter(title=titre_de_la_note).first()
        if page_de_la_note is None:
            self.stdout.write(self.style.WARNING(
                f"Note absente, sautée : « {titre_de_la_note} »"
            ))
            return

        # Idempotence : un job de demonstration deja peuple vaut chargement
        # fait. Sans ce garde-fou, chaque relance empilerait les cartes.
        # / Idempotency: an already-populated demo job means "already loaded".
        job_de_demonstration = ExtractionJob.objects.filter(
            page=page_de_la_note, name=NOM_DU_JOB_DE_DEMONSTRATION
        ).first()
        if job_de_demonstration is not None and job_de_demonstration.entities.exists():
            self.stdout.write(
                f"Déjà chargée, sautée : « {titre_de_la_note} »"
            )
            return

        if job_de_demonstration is None:
            job_de_demonstration = ExtractionJob.objects.create(
                page=page_de_la_note,
                name=NOM_DU_JOB_DE_DEMONSTRATION,
                prompt_description=(
                    "Idées posées à la main pour la mise au point de "
                    "l'interface. Aucun appel LLM."
                ),
                status=ExtractionJobStatus.COMPLETED,
            )

        # Les elements sont relus une fois : chaque idee y cherche ses
        # fragments. / Elements read once; each idea looks its fragments up.
        elements_par_ordre = {
            element.ordre: element
            for element in page_de_la_note.elements.all()
        }

        for idee in idees:
            self._poser_une_idee(
                idee,
                job_de_demonstration,
                page_de_la_note,
                elements_par_ordre,
                titre_de_la_note,
                commentateurs,
            )

        job_de_demonstration.entities_count = job_de_demonstration.entities.count()
        job_de_demonstration.save(update_fields=["entities_count"])

        self.stdout.write(self.style.SUCCESS(
            f"« {titre_de_la_note} » : {job_de_demonstration.entities_count} idée(s)."
        ))

    def _poser_une_idee(
        self,
        idee,
        job_de_demonstration,
        page_de_la_note,
        elements_par_ordre,
        titre_de_la_note,
        commentateurs,
    ):
        """
        Cree l'extraction, ses portions et ses commentaires.
        / Create the extraction, its portions and its comments.
        """
        # Les bornes de chaque portion sont calculees AVANT toute ecriture :
        # une idee dont un fragment a disparu ne doit rien laisser derriere
        # elle. / Offsets computed before any write.
        portions_calculees = []
        for ordre_de_l_element, fragment in idee["portions"]:
            element = elements_par_ordre.get(ordre_de_l_element)
            if element is None:
                raise CommandError(
                    f"« {titre_de_la_note} » : aucun élément d'ordre "
                    f"{ordre_de_l_element}. La note étalon a changé."
                )

            texte_de_l_element = element.texte or ""
            nombre_d_occurrences = texte_de_l_element.count(fragment)
            if nombre_d_occurrences == 0:
                raise CommandError(
                    f"« {titre_de_la_note} », élément #{ordre_de_l_element} : "
                    f"fragment introuvable — « {fragment[:60]}… ». La note "
                    f"étalon a changé ; corriger la table de la commande "
                    f"plutôt que d'ancrer à côté."
                )
            # AMBIGUITE REFUSEE. `.find()` rend la PREMIERE occurrence : un
            # fragment present deux fois s'ancrerait sur l'une des deux, au
            # hasard de l'ecriture, et l'autre moitie du temps ce serait la
            # mauvaise. Une ancre fausse ne se voit pas — c'est tout l'objet
            # de ce garde-fou.
            # / `.find()` takes the first hit; two hits means the anchor is
            # a coin toss, and a wrong anchor is invisible.
            if nombre_d_occurrences > 1:
                raise CommandError(
                    f"« {titre_de_la_note} », élément #{ordre_de_l_element} : "
                    f"le fragment « {fragment[:60]}… » y figure deux fois ou "
                    f"plus ({nombre_d_occurrences}). Allonger le fragment "
                    f"jusqu'à ce qu'il désigne un seul passage."
                )

            debut_dans_element = texte_de_l_element.find(fragment)
            portions_calculees.append(
                (element, debut_dans_element, debut_dans_element + len(fragment))
            )

        # Le texte cite est la concatenation des portions. Les separateurs de
        # jonction entre deux elements n'appartiennent a aucune portion : on
        # les rend par une espace. / Joined portions; junction separators
        # belong to no portion and render as a single space.
        texte_extrait = " ".join(fragment for _ordre, fragment in idee["portions"])

        # LA POSITION DANS LA PAGE SE RECONSTRUIT, ELLE NE SE CHERCHE PAS.
        #
        # `start_char` et `end_char` sont censes designer une position dans
        # `page.text_readability`. Or ce champ est VIDE sur les pages
        # ingerees par le moteur element : mesure du 12 aout, les notes
        # « Etude epistemologique » et « Badgeons la Normandie » ont un
        # `text_readability` de longueur 0. Une premiere version cherchait
        # le fragment dedans et retombait sur 0 en cas d'echec : NEUF
        # extractions sur douze portaient `start_char = 0`, et tout clic
        # sur une carte renvoyait en tete de document
        # (`job_results.html`, `scrollToExtraction`).
        #
        # Ces champs servent au TRI (`front/views.py:941`,
        # `hypostasis_extractor/views.py:266`). On les reconstruit donc
        # depuis les elements, seule source de verite qui reste : la somme
        # des longueurs des elements precedents, plus un separateur de
        # jonction chacun, plus le debut de la premiere portion. La valeur
        # n'est pas un offset dans `text_readability` — ce texte n'existe
        # pas — mais une position dans le document RECONSTITUE, monotone
        # et distincte, ce que le tri demande.
        # / text_readability is empty on element-engine pages; a silent
        # zero-fallback made nine of twelve extractions share position 0.
        # Rebuild the offset from the elements instead.
        element_de_la_premiere_portion = portions_calculees[0][0]
        debut_de_la_premiere_portion = portions_calculees[0][1]
        decalage_des_elements_precedents = 0
        for ordre_parcouru, element_parcouru in sorted(elements_par_ordre.items()):
            if ordre_parcouru >= element_de_la_premiere_portion.ordre:
                break
            decalage_des_elements_precedents += len(element_parcouru.texte or "") + 1

        debut_dans_la_page = (
            decalage_des_elements_precedents + debut_de_la_premiere_portion
        )

        extraction = ExtractedEntity.objects.create(
            job=job_de_demonstration,
            extraction_class=idee["hypostases"].split(",")[0].strip().lower(),
            extraction_text=texte_extrait,
            start_char=debut_dans_la_page,
            end_char=debut_dans_la_page + len(texte_extrait),
            # Les cles sont celles que lit `entity_json_attrs`
            # (extractor_tags.py:180-185). / Canonical keys read by the tag.
            attributes={
                "hypostases": idee["hypostases"],
                "resume": idee["resume"],
                "mots_cles": idee["mots_cles"],
            },
        )

        for ordre_dans_extraction, (
            element,
            debut_dans_element,
            fin_dans_element,
        ) in enumerate(portions_calculees):
            AncrageExtraction.objects.create(
                extraction=extraction,
                element=element,
                ordre_dans_extraction=ordre_dans_extraction,
                debut_dans_element=debut_dans_element,
                fin_dans_element=fin_dans_element,
            )

        # Le statut de debat n'est JAMAIS assigne ici : un signal le derive
        # de l'existence de commentaires (hypostasis_extractor/signals.py).
        # / Debate status is signal-derived, never assigned here.
        for nom_du_commentateur, texte_du_commentaire in idee["commentaires"]:
            CommentaireExtraction.objects.create(
                entity=extraction,
                user=commentateurs[nom_du_commentateur],
                commentaire=texte_du_commentaire,
            )

    # -------------------------------------------------------------------
    # Les a-cotes
    # / Supporting steps
    # -------------------------------------------------------------------

    def _preparer_les_commentateurs(self):
        """
        Rend les utilisateurs qui commentent, en les creant au besoin.
        / Return the commenting users, creating them if needed.

        Les comptes crees ici sont des FIGURANTS : ils portent un nom de
        connexion inutilisable et sont inactifs. Une fixture ne doit pas
        ouvrir une porte d'entree — `get_or_create` sans mot de passe
        laisse un champ vide, ce qui n'est pas la meme chose qu'un mot de
        passe impossible.
        / Fixture accounts are extras: unusable password and inactive. A
        blank password field is not an impossible one.
        """
        commentateurs = {}
        for nom_d_utilisateur, prenom in COMMENTATEURS.items():
            utilisateur, vient_d_etre_cree = User.objects.get_or_create(
                username=nom_d_utilisateur,
                defaults={
                    "first_name": prenom,
                    "email": f"{nom_d_utilisateur}@demo.hypostasia.org",
                    "is_active": False,
                },
            )
            if vient_d_etre_cree:
                utilisateur.set_unusable_password()
                utilisateur.save(update_fields=["password"])
            commentateurs[nom_d_utilisateur] = utilisateur
        return commentateurs

    def _supprimer_les_jobs_de_demonstration(self):
        """
        Ne supprime QUE les jobs poses par cette commande. Un job d'analyse
        reel survit. / Only demo jobs are dropped; real analysis jobs survive.
        """
        jobs_de_demonstration = ExtractionJob.objects.filter(
            name=NOM_DU_JOB_DE_DEMONSTRATION
        )
        nombre_supprime = jobs_de_demonstration.count()
        jobs_de_demonstration.delete()
        self.stdout.write(
            f"{nombre_supprime} job(s) de démonstration supprimé(s)."
        )

    def _annoncer_sans_ecrire(self):
        """Sortie de `--a-blanc`. / `--a-blanc` output."""
        for titre_de_la_note, idees in IDEES_DE_DEMONSTRATION.items():
            nombre_de_portions = sum(len(idee["portions"]) for idee in idees)
            nombre_de_commentaires = sum(
                len(idee["commentaires"]) for idee in idees
            )
            note_est_en_base = Page.objects.filter(
                title=titre_de_la_note
            ).exists()
            etat_de_la_note = "" if note_est_en_base else "  [ABSENTE de la base]"
            self.stdout.write(
                f"« {titre_de_la_note} » : {len(idees)} idée(s), "
                f"{nombre_de_portions} ancrage(s), "
                f"{nombre_de_commentaires} commentaire(s).{etat_de_la_note}"
            )
