"""
L'analyse des notes etalons par le vrai modele.
/ Analysis of the reference notes by the real model.

LOCALISATION : front/tests/test_analyse_des_notes_etalons.py

Lancer avec :
    docker exec -w /app hypostasia_web python manage.py test \\
        front.tests.test_analyse_des_notes_etalons \\
        --settings=hypostasia.settings_test_opus

POURQUOI CETTE COMMANDE REMPLACE `charger_fixtures_llm_reel`

Deux jeux de demonstration vivaient en parallele, et le mainteneur l'a
vu a l'ecran : DEUX carnets, dont un nomme « moteur reel » — ce qui
disait, sans le vouloir, que le reste ne l'etait pas.

L'explication tient a un croisement de dates. `charger_fixtures_llm_reel`
date du 10 aout 2026, `charger_fixtures_sample` du 11 : la premiere est
ANTERIEURE aux documents etalons du depot. Elle avait le bon principe —
ingerer puis analyser POUR DE VRAI — mais sur deux textes inventes,
ecrits en dur dans le fichier Python. La seconde a apporte les vrais
documents le lendemain, sans les faire analyser. Les deux se sont
croisees sans se rejoindre.

Resultat mesure avant correction : sur 19 extractions, 7 venaient du
modele (les textes jouets) et 12 etaient ecrites a la main ; et TROIS
documents sur six n'avaient aucune extraction.
/ Two demo datasets ran in parallel because one command predated the
repository's own documents by a day. The real documents were never
analysed; three of six had no extraction at all.

CE QUE FAIT CELLE-CI

Elle ne cree NI note NI carnet : elle analyse celles qui sont deja la.
C'est toute la difference, et c'est ce qui fait disparaitre le second
carnet. / It creates no note and no notebook: it analyses what is there.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from core.models import AIModel, Configuration, Dossier, ElementDocument, Page
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.management.commands.analyser_les_notes_etalons import (
    LIMITE_D_ELEMENTS_POUR_ANALYSE,
    NOM_DU_CARNET_ETALON,
)
from hypostasis_extractor.models import (
    AnalyseurSyntaxique,
    ExtractedEntity,
    ExtractionJob,
)


class AnalyseDesNotesEtalonsTest(TestCase):
    """
    LOCALISATION : front/tests/test_analyse_des_notes_etalons.py
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="jonas", is_staff=True,
        )
        modele = AIModel.objects.create(
            name="Modele d'essai", provider="google",
            model_name="gemini-2.5-flash", is_active=True,
        )
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = modele
        configuration.save()
        AnalyseurSyntaxique.objects.create(
            name="Hypostasia", is_active=True, type_analyseur="analyser",
            est_par_defaut=True,
        )
        self.carnet = Dossier.objects.create(
            name=NOM_DU_CARNET_ETALON, owner=self.proprietaire,
        )

    def _creer_une_note(self, titre, nombre_d_elements):
        note = Page.objects.create(
            title=titre, source_type="file",
            html_original="", html_readability="", text_readability="",
            content_hash=f"hash-{titre}", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(note, self.carnet, self.proprietaire)
        for position in range(nombre_d_elements):
            ElementDocument.objects.create(
                page=note, ordre=position, label="text",
                texte=f"element {position}",
                empreinte_contenu=f"empreinte-{titre}-{position}",
                reference_docling=f"#/texts/{position}",
                chemin_de_section=[], provenance={},
            )
        return note

    def _lancer(self, *arguments):
        with patch(
            "hypostasis_extractor.tasks_element."
            "analyser_une_page_avec_le_moteur_element.delay",
        ) as envoi_en_file:
            call_command("analyser_les_notes_etalons", *arguments)
        return envoi_en_file

    def test_une_note_sans_analyse_part_dans_la_file(self):
        self._creer_une_note("Debat IA", 12)

        envoi_en_file = self._lancer()

        self.assertEqual(envoi_en_file.call_count, 1)

    def test_l_analyse_part_en_file_et_ne_bloque_pas_l_installation(self):
        # `.delay()` et jamais `.apply()` : le demarrage du conteneur ne
        # doit pas attendre le modele, et l'administrateur suit
        # l'avancement depuis son menu des taches.
        # / Queued, never run in place: startup must not wait.
        self._creer_une_note("Debat IA", 12)

        with patch(
            "hypostasis_extractor.tasks_element."
            "analyser_une_page_avec_le_moteur_element.apply",
        ) as execution_immediate, patch(
            "hypostasis_extractor.tasks_element."
            "analyser_une_page_avec_le_moteur_element.delay",
        ):
            call_command("analyser_les_notes_etalons")

        self.assertEqual(execution_immediate.call_count, 0)

    def test_une_note_trop_grosse_est_sautee(self):
        # La Presentation V3 porte 549 elements a elle seule, soit 73 %
        # du corpus etalon : l'analyser a chaque installation neuve
        # couterait sans rien montrer de plus. Le seuil est explicite,
        # et la note sautee est annoncee.
        # / One document holds 73 % of the corpus; the cap is explicit.
        self._creer_une_note("Presentation V3", LIMITE_D_ELEMENTS_POUR_ANALYSE + 1)

        envoi_en_file = self._lancer()

        self.assertEqual(envoi_en_file.call_count, 0)

    def test_une_note_deja_analysee_par_un_modele_est_sautee(self):
        # Sinon chaque demarrage du conteneur refacturerait l'analyse.
        # / Otherwise every container start would re-bill.
        note = self._creer_une_note("Debat IA", 12)
        ExtractionJob.objects.create(
            page=note, name="Analyseur: Hypostasia", prompt_description="p",
            status="completed", ai_model=Configuration.get_solo().ai_model,
        )

        envoi_en_file = self._lancer()

        self.assertEqual(envoi_en_file.call_count, 0)

    def test_les_extractions_posees_a_la_main_n_empechent_pas_l_analyse(self):
        """
        Les deux origines coexistent sur une meme note.
        / Both origins coexist on the same note.

        LOCALISATION : front/tests/test_analyse_des_notes_etalons.py

        `charger_extractions_demo` pose des extractions ECRITES A LA MAIN
        pour couvrir des cas limites qu'un modele ne produit pas de facon
        fiable : marques imbriquees, ancre portee par un tableau, cartes
        a 0/1/2 commentaires. C'est la matiere qui sert a styler
        l'interface, et elle doit rester.

        Ses jobs se reconnaissent a leur `ai_model` VIDE. Une garde qui
        regarderait « cette note a-t-elle des extractions ? » sauterait
        donc justement les notes que le mainteneur veut faire analyser.
        / Hand-written jobs carry no ai_model; a guard watching mere
        extractions would skip exactly the notes meant to be analysed.
        """
        note = self._creer_une_note("Badgeons la Normandie", 28)
        job_manuel = ExtractionJob.objects.create(
            page=note, name="Démonstration — idées posées à la main",
            prompt_description="", status="completed", ai_model=None,
        )
        ExtractedEntity.objects.create(
            job=job_manuel, extraction_class="phenomene",
            extraction_text="une idee posee a la main",
            start_char=0, end_char=24,
        )

        envoi_en_file = self._lancer()

        self.assertEqual(
            envoi_en_file.call_count, 1,
            "Une note portant des extractions ECRITES A LA MAIN doit "
            "quand meme etre analysee par le modele : les deux origines "
            "coexistent.",
        )

    def test_une_analyse_deja_en_file_n_est_pas_renvoyee(self):
        # Un redemarrage pendant le traitement renverrait toutes les
        # analyses — et les refacturerait — si l'on ne regardait que les
        # extractions produites. / A restart mid-flight would re-queue.
        note = self._creer_une_note("Debat IA", 12)
        ExtractionJob.objects.create(
            page=note, name="Analyseur: Hypostasia", prompt_description="p",
            status="pending", ai_model=Configuration.get_solo().ai_model,
        )

        envoi_en_file = self._lancer()

        self.assertEqual(envoi_en_file.call_count, 0)

    def test_forcer_reanalyse_meme_ce_qui_est_deja_fait(self):
        note = self._creer_une_note("Debat IA", 12)
        ExtractionJob.objects.create(
            page=note, name="Analyseur: Hypostasia", prompt_description="p",
            status="completed", ai_model=Configuration.get_solo().ai_model,
        )

        envoi_en_file = self._lancer("--forcer")

        self.assertEqual(envoi_en_file.call_count, 1)

    def test_la_commande_ne_cree_ni_note_ni_carnet(self):
        """
        C'est ce qui fait disparaitre le second carnet.
        / This is what makes the second notebook disappear.

        `charger_fixtures_llm_reel` montait SON carnet et SES deux notes,
        ecrites en dur dans le fichier Python. D'ou les deux carnets de
        demonstration que voyait le mainteneur, dont un nomme « moteur
        reel » — ce qui disait, sans le vouloir, que l'autre ne l'etait
        pas. / The previous command built its own notebook and notes.
        """
        self._creer_une_note("Debat IA", 12)
        carnets_avant = Dossier.objects.count()
        notes_avant = Page.objects.count()

        self._lancer()

        self.assertEqual(Dossier.objects.count(), carnets_avant)
        self.assertEqual(Page.objects.count(), notes_avant)

    def test_sans_notes_a_analyser_la_commande_ne_fait_rien(self):
        envoi_en_file = self._lancer()

        self.assertEqual(envoi_en_file.call_count, 0)
