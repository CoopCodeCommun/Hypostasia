"""
Tests de la commande charger_extractions_demo.
/ Tests for the charger_extractions_demo command.

LOCALISATION : front/tests/test_charger_extractions_demo.py

CE QUE CES TESTS EPROUVENT

La commande pose a la main, sans appeler aucun LLM, les extractions de
demonstration qui manquaient a la base : sans elles le panneau affiche
« 0 extractions » et il n'y a rien a styler.

Le test le plus important est celui des positions : une ancre porte des
positions DANS LE TEXTE DE L'ELEMENT, et une position fausse produit un
surlignage decale que rien ne signale. On verifie donc que chaque portion
relue redonne exactement le fragment declare.
/ The key test is positional: a wrong offset silently shifts the highlight.

Les textes des elements ne sont PAS recopies ici. Ils sont fabriques a
partir des fragments declares par la commande elle-meme : un element porte
la concatenation de ses fragments maximaux (ceux qui ne sont contenus dans
aucun autre). Les fragments imbriques — la superposition que la maquette
dessine — se retrouvent alors naturellement dans le texte de leur englobant.
/ Element texts are built from the command's own maximal fragments.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Page
from hypostasis_extractor.models import (
    AncrageExtraction,
    CommentaireExtraction,
    ExtractedEntity,
    ExtractionJob,
)
from hypostasis_extractor.templatetags.extractor_tags import HYPOSTASE_VERS_FAMILLE

from front.management.commands.charger_extractions_demo import (
    IDEES_DE_DEMONSTRATION,
    NOM_DU_JOB_DE_DEMONSTRATION,
)

User = get_user_model()


def fragments_maximaux(fragments):
    """
    Ne garde que les fragments qui ne sont contenus dans aucun autre.
    / Keep only fragments not contained in any other one.

    LOCALISATION : front/tests/test_charger_extractions_demo.py

    C'est ce qui permet de fabriquer le texte d'un element sans recopier le
    document reel : deux idees superposees partagent le meme englobant, et
    seule celui-ci a besoin d'etre ecrit dans le texte.
    """
    retenus = []
    for fragment in fragments:
        est_contenu_ailleurs = any(
            fragment != autre and fragment in autre for autre in fragments
        )
        if not est_contenu_ailleurs:
            retenus.append(fragment)
    return retenus


def construire_les_notes_de_demonstration():
    """
    Cree les Pages et les ElementDocument que la commande attend.
    / Create the Pages and ElementDocument rows the command expects.

    LOCALISATION : front/tests/test_charger_extractions_demo.py
    """
    for rang_de_la_note, (titre_de_la_note, idees) in enumerate(
        IDEES_DE_DEMONSTRATION.items()
    ):

        # Rassemble, par ordre d'element, tous les fragments que les idees
        # de cette note veulent ancrer.
        # / Gather, per element order, every fragment the ideas want anchored.
        fragments_par_ordre_d_element = {}
        for idee in idees:
            for ordre_de_l_element, fragment in idee["portions"]:
                fragments_par_ordre_d_element.setdefault(
                    ordre_de_l_element, []
                ).append(fragment)

        page_de_la_note = Page.objects.create(
            title=titre_de_la_note,
            url=f"https://exemple.test/note-{rang_de_la_note}",
        )

        for ordre_de_l_element, fragments in sorted(
            fragments_par_ordre_d_element.items()
        ):
            # Un peu de texte avant, pour qu'aucune portion ne commence par
            # hasard a l'offset 0 : un bug de calcul y passerait inapercu.
            # / Prefix text so no portion starts at offset 0 by accident.
            texte_de_l_element = "Contexte. " + " ".join(
                fragments_maximaux(fragments)
            )
            page_de_la_note.elements.create(
                ordre=ordre_de_l_element,
                label="text",
                texte=texte_de_l_element,
                empreinte_contenu=f"empreinte-{page_de_la_note.pk}-{ordre_de_l_element}",
            )

        # `text_readability` est laisse VIDE, comme il l'est en production
        # sur les pages ingerees par le moteur element : mesure du 12 aout,
        # les notes 9 et 5 ont un `text_readability` de longueur 0. Un
        # decor de test plus favorable que la production cache les defauts
        # qu'il devrait montrer.
        # / Left empty, as it is in production for element-engine pages.


class ChargerExtractionsDemoTest(TestCase):
    """
    LOCALISATION : front/tests/test_charger_extractions_demo.py
    """

    def setUp(self):
        construire_les_notes_de_demonstration()

    def executer_la_commande(self, *arguments):
        """Lance la commande et rend sa sortie. / Run the command, return stdout."""
        sortie = StringIO()
        call_command("charger_extractions_demo", *arguments, stdout=sortie)
        return sortie.getvalue()

    # -------------------------------------------------------------------
    # Ce que la commande produit
    # / What the command produces
    # -------------------------------------------------------------------

    def test_pose_une_extraction_par_idee_declaree(self):
        """Chaque idee de la table donne exactement une extraction."""
        self.executer_la_commande()

        nombre_d_idees_declarees = sum(
            len(idees) for idees in IDEES_DE_DEMONSTRATION.values()
        )
        self.assertEqual(
            ExtractedEntity.objects.count(), nombre_d_idees_declarees
        )

    def test_chaque_portion_relue_redonne_son_fragment(self):
        """
        Le test central : une ancre mal positionnee decale le surlignage sans
        que rien ne le signale.
        / The key test: a wrong offset silently shifts the highlight.
        """
        self.executer_la_commande()

        fragments_attendus = []
        for idees in IDEES_DE_DEMONSTRATION.values():
            for idee in idees:
                for _ordre_de_l_element, fragment in idee["portions"]:
                    fragments_attendus.append(fragment)

        textes_des_portions = [
            ancrage.texte_de_la_portion()
            for ancrage in AncrageExtraction.objects.all()
        ]

        self.assertEqual(sorted(textes_des_portions), sorted(fragments_attendus))

    def test_les_positions_tiennent_dans_le_texte_de_l_element(self):
        """Aucune ancre ne deborde de l'element qui la porte."""
        self.executer_la_commande()

        for ancrage in AncrageExtraction.objects.select_related("element"):
            longueur_de_l_element = len(ancrage.element.texte)
            self.assertLess(ancrage.debut_dans_element, ancrage.fin_dans_element)
            self.assertLessEqual(ancrage.fin_dans_element, longueur_de_l_element)

    def test_les_portions_sont_numerotees_depuis_zero_et_sans_trou(self):
        """ordre_dans_extraction : 0, 1, 2… pour chaque extraction."""
        self.executer_la_commande()

        for extraction in ExtractedEntity.objects.all():
            ordres_des_portions = list(
                extraction.ancrages.order_by(
                    "ordre_dans_extraction"
                ).values_list("ordre_dans_extraction", flat=True)
            )
            self.assertEqual(
                ordres_des_portions, list(range(len(ordres_des_portions)))
            )

    def test_deux_extractions_ne_partagent_pas_la_position_zero(self):
        """
        `start_char` sert au TRI (`front/views.py:941`,
        `hypostasis_extractor/views.py:266`) et au saut vers le passage
        (`job_results.html`, `scrollToExtraction`). Une premiere version
        le cherchait dans `page.text_readability` et retombait sur 0 en
        cas d'echec — or ce champ est VIDE sur les pages ingerees par le
        moteur element : 9 extractions sur 12 portaient `start_char = 0`
        sur la base reelle, et tout clic renvoyait en tete de document.

        Le fallback silencieux etait exactement ce que la commande
        prétend interdire ailleurs.
        / A silent zero-fallback made 9 of 12 extractions share position 0.
        """
        self.executer_la_commande()

        for titre_de_la_note in IDEES_DE_DEMONSTRATION:
            page_de_la_note = Page.objects.get(title=titre_de_la_note)
            positions_dans_la_note = [
                extraction.start_char
                for extraction in ExtractedEntity.objects.filter(
                    job__page=page_de_la_note
                )
            ]
            self.assertEqual(
                len(positions_dans_la_note),
                len(set(positions_dans_la_note)),
                f"« {titre_de_la_note} » : deux extractions partagent la "
                f"même position — {sorted(positions_dans_la_note)}.",
            )

    def test_la_position_suit_l_ordre_du_document(self):
        """
        Trier par `start_char` doit rendre l'ordre de lecture. Sinon le
        tri « Position » du panneau ment.
        / Sorting by start_char must yield reading order.
        """
        self.executer_la_commande()

        for titre_de_la_note in IDEES_DE_DEMONSTRATION:
            page_de_la_note = Page.objects.get(title=titre_de_la_note)
            extractions_de_la_note = ExtractedEntity.objects.filter(
                job__page=page_de_la_note
            ).order_by("start_char")

            reperes_de_lecture = []
            for extraction in extractions_de_la_note:
                premiere_portion = extraction.ancrages.order_by(
                    "ordre_dans_extraction"
                ).first()
                reperes_de_lecture.append(
                    (
                        premiere_portion.element.ordre,
                        premiere_portion.debut_dans_element,
                    )
                )

            self.assertEqual(
                reperes_de_lecture,
                sorted(reperes_de_lecture),
                f"« {titre_de_la_note} » : l'ordre par start_char ne suit "
                f"pas l'ordre du document — {reperes_de_lecture}.",
            )

    def test_la_fin_est_apres_le_debut(self):
        """`end_char` doit borner l'extraction, pas la contredire."""
        self.executer_la_commande()

        for extraction in ExtractedEntity.objects.all():
            self.assertGreater(extraction.end_char, extraction.start_char)

    # -------------------------------------------------------------------
    # Ce que la commande refuse d'ancrer
    # / What the command refuses to anchor
    # -------------------------------------------------------------------

    def test_un_fragment_ambigu_leve_plutot_que_de_prendre_le_premier(self):
        """
        `.find()` prend la PREMIERE occurrence. Un fragment qui apparait
        deux fois dans le meme element s'ancrerait sur l'une des deux, au
        hasard de l'ecriture — et l'autre moitie du temps ce serait la
        mauvaise. La promesse « jamais d'ancre fausse en silence » ne tient
        que si l'ambiguite est refusee.
        / A fragment occurring twice would anchor on whichever came first.
        """
        titre_de_la_note = next(iter(IDEES_DE_DEMONSTRATION))
        page_de_la_note = Page.objects.get(title=titre_de_la_note)
        premier_element = page_de_la_note.elements.order_by("ordre").first()
        # Le texte est double : chaque fragment y figure desormais deux fois.
        # / Doubling the text makes every fragment ambiguous.
        premier_element.texte = premier_element.texte + " " + premier_element.texte
        premier_element.save(update_fields=["texte"])

        with self.assertRaises(CommandError) as erreur_levee:
            self.executer_la_commande()

        self.assertIn("deux fois", str(erreur_levee.exception).lower())

    # -------------------------------------------------------------------
    # Les comptes qui commentent
    # / The commenting accounts
    # -------------------------------------------------------------------

    def test_la_commande_ne_commente_jamais_sous_un_compte_existant(self):
        """
        Les commentaires de demonstration sont FICTIFS. Les attribuer a un
        compte reel — celui du mainteneur, par exemple — lui prete des
        phrases qu'il n'a pas ecrites, et expose ses vrais commentaires a
        la cascade d'un `--reset`.
        / Demo comments are fictional and must never borrow a real account.
        """
        compte_reel = User.objects.create_user(
            username="jonas", password="motdepasse", first_name="Jonas"
        )

        self.executer_la_commande()

        self.assertFalse(
            CommentaireExtraction.objects.filter(user=compte_reel).exists(),
            "Un commentaire de démonstration a été posé sous un compte "
            "réel préexistant.",
        )

    def test_les_comptes_de_demonstration_ne_peuvent_pas_se_connecter(self):
        """
        Un compte cree par une fixture ne doit pas devenir une porte
        d'entree. / A fixture-created account must not be a way in.
        """
        self.executer_la_commande()

        for auteur in {
            commentaire.user
            for commentaire in CommentaireExtraction.objects.select_related("user")
        }:
            self.assertTrue(
                auteur.username.startswith("demo_"),
                f"« {auteur.username} » n'est pas nommé comme un compte "
                f"de démonstration.",
            )
            self.assertFalse(auteur.has_usable_password())

    # -------------------------------------------------------------------
    # La couverture que la maquette exige
    # / The coverage the mockup requires
    # -------------------------------------------------------------------

    def test_les_huit_familles_d_hypostases_sont_couvertes(self):
        """
        La maquette donne une couleur a chacune des 8 familles
        (hypostasia.css:48-70). Styler sans les avoir toutes, c'est styler
        a l'aveugle.
        / All 8 families must be present, or we style blind.
        """
        self.executer_la_commande()

        familles_posees = set()
        for extraction in ExtractedEntity.objects.all():
            for hypostase in (extraction.attributes or {}).get(
                "hypostases", ""
            ).split(","):
                hypostase_normalisee = hypostase.strip().lower()
                if not hypostase_normalisee:
                    continue
                # On verifie l'APPARTENANCE avant de mapper. Passer par
                # `.get(cle, "objet")` ferait retomber « METHODOLOGIE »,
                # « PHENOMEME » ou n'importe quelle faute de frappe sur la
                # famille par defaut : le test resterait vert en couvrant
                # une hypostase qui n'existe pas.
                # / Membership first: a typo would silently fall back to
                # the default family and keep this test green.
                self.assertIn(
                    hypostase_normalisee,
                    HYPOSTASE_VERS_FAMILLE,
                    f"« {hypostase_normalisee} » n'est pas une hypostase "
                    f"connue (extractor_tags.py).",
                )
                familles_posees.add(HYPOSTASE_VERS_FAMILLE[hypostase_normalisee])

        self.assertEqual(familles_posees, set(HYPOSTASE_VERS_FAMILLE.values()))

    def test_les_deux_statuts_de_debat_sont_representes(self):
        """
        Le statut est auto-derive par signal de l'existence de commentaires.
        La commande ne l'assigne jamais : elle pose des commentaires.
        / Status is signal-derived; the command only posts comments.
        """
        self.executer_la_commande()

        statuts_poses = set(
            ExtractedEntity.objects.values_list("statut_debat", flat=True)
        )
        self.assertEqual(statuts_poses, {"nouveau", "commente"})

    def test_une_extraction_porte_deux_commentaires(self):
        """La maquette dessine des cartes a 0, 1 et 2 commentaires."""
        self.executer_la_commande()

        nombres_de_commentaires = sorted(
            extraction.commentaires.count()
            for extraction in ExtractedEntity.objects.all()
        )
        self.assertIn(0, nombres_de_commentaires)
        self.assertIn(1, nombres_de_commentaires)
        self.assertIn(2, nombres_de_commentaires)

    def test_deux_extractions_se_superposent_sur_un_meme_element(self):
        """
        Les marques imbriquees de la maquette (§ 4) supposent deux idees
        dont les plages se recouvrent dans le meme element.
        / Nested marks require two overlapping ranges in one element.
        """
        self.executer_la_commande()

        a_trouve_une_superposition = False
        for element_id in set(
            AncrageExtraction.objects.values_list("element_id", flat=True)
        ):
            plages = list(
                AncrageExtraction.objects.filter(
                    element_id=element_id
                ).values_list("debut_dans_element", "fin_dans_element")
            )
            for indice_a, (debut_a, fin_a) in enumerate(plages):
                for debut_b, fin_b in plages[indice_a + 1:]:
                    if debut_a < fin_b and debut_b < fin_a:
                        a_trouve_une_superposition = True

        self.assertTrue(
            a_trouve_une_superposition,
            "Aucune superposition : le rendu des marques imbriquees ne sera "
            "jamais exerce.",
        )

    def test_une_extraction_enjambe_deux_elements(self):
        """
        Une extraction qui deborde d'un element porte DEUX ancrages et
        produit DEUX <mark> — c'est la raison d'etre de la table de liaison.
        / A spanning extraction carries two anchors and renders two marks.
        """
        self.executer_la_commande()

        nombres_d_ancrages = [
            extraction.ancrages.count()
            for extraction in ExtractedEntity.objects.all()
        ]
        self.assertIn(2, nombres_d_ancrages)

    # -------------------------------------------------------------------
    # Rejouabilite
    # / Replayability
    # -------------------------------------------------------------------

    def test_deux_executions_ne_doublent_rien(self):
        """La commande est idempotente. / The command is idempotent."""
        self.executer_la_commande()
        nombre_apres_le_premier_passage = ExtractedEntity.objects.count()

        self.executer_la_commande()

        self.assertEqual(
            ExtractedEntity.objects.count(), nombre_apres_le_premier_passage
        )

    def test_reset_efface_puis_recree(self):
        """--reset rend le meme etat, pas un etat empile."""
        self.executer_la_commande()
        nombre_apres_le_premier_passage = ExtractedEntity.objects.count()

        self.executer_la_commande("--reset")

        self.assertEqual(
            ExtractedEntity.objects.count(), nombre_apres_le_premier_passage
        )

    def test_reset_n_efface_que_les_jobs_de_demonstration(self):
        """
        Un job d'analyse reel, lui, doit survivre a un --reset.
        / A real analysis job must survive a --reset.
        """
        self.executer_la_commande()
        page_quelconque = Page.objects.first()
        job_reel = ExtractionJob.objects.create(
            page=page_quelconque,
            name="Analyse réelle",
            prompt_description="posée par un vrai analyseur",
        )

        self.executer_la_commande("--reset")

        self.assertTrue(ExtractionJob.objects.filter(pk=job_reel.pk).exists())

    def test_un_seul_job_de_demonstration_par_note(self):
        """Pas d'empilement de jobs a chaque relance."""
        self.executer_la_commande()
        self.executer_la_commande()

        for titre_de_la_note in IDEES_DE_DEMONSTRATION:
            page_de_la_note = Page.objects.get(title=titre_de_la_note)
            self.assertEqual(
                ExtractionJob.objects.filter(
                    page=page_de_la_note, name=NOM_DU_JOB_DE_DEMONSTRATION
                ).count(),
                1,
            )

    # -------------------------------------------------------------------
    # Ce que la commande refuse de faire en silence
    # / What the command refuses to do silently
    # -------------------------------------------------------------------

    def test_une_note_absente_est_signalee_sans_faire_echouer_le_reste(self):
        """
        Sur une base ou une note etalon manque, les autres sont quand meme
        chargees et la note manquante est nommee.
        / A missing note is named; the others still load.
        """
        titre_supprime = next(iter(IDEES_DE_DEMONSTRATION))
        Page.objects.filter(title=titre_supprime).delete()

        sortie = self.executer_la_commande()

        self.assertIn(titre_supprime, sortie)
        self.assertGreater(ExtractedEntity.objects.count(), 0)

    def test_un_fragment_introuvable_leve_une_erreur_explicite(self):
        """
        Si le texte d'un element a change, la commande doit le DIRE plutot
        que de poser une ancre fausse. Un ancrage faux est invisible.
        / A changed element text must raise, never anchor at a wrong offset.
        """
        titre_de_la_note = next(iter(IDEES_DE_DEMONSTRATION))
        page_de_la_note = Page.objects.get(title=titre_de_la_note)
        premier_element = page_de_la_note.elements.order_by("ordre").first()
        premier_element.texte = "Ce texte ne contient plus aucun fragment declare."
        premier_element.save(update_fields=["texte"])

        with self.assertRaises(CommandError) as erreur_levee:
            self.executer_la_commande()

        self.assertIn(titre_de_la_note, str(erreur_levee.exception))

    def test_a_blanc_n_ecrit_rien(self):
        """--a-blanc annonce ce qui serait fait sans rien creer."""
        sortie = self.executer_la_commande("--a-blanc")

        self.assertEqual(ExtractedEntity.objects.count(), 0)
        self.assertEqual(AncrageExtraction.objects.count(), 0)
        self.assertEqual(CommentaireExtraction.objects.count(), 0)
        self.assertTrue(sortie.strip())
