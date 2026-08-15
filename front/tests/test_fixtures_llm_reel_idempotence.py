"""
L'analyse par vrai LLM ne doit se payer qu'une fois.
/ The real-LLM analysis must be paid for only once.

LOCALISATION : front/tests/test_fixtures_llm_reel_idempotence.py

Lancer avec :
    docker exec -w /app hypostasia_web python manage.py test \\
        front.tests.test_fixtures_llm_reel_idempotence \\
        --settings=hypostasia.settings_test_opus

POURQUOI CETTE GARDE EXISTE

`charger_fixtures_llm_reel` est REJOUABLE par conception : chaque
execution refait de vrais appels au modele. C'est ce qu'on veut quand on
la lance a la main pour comparer le rendu a la maquette etalon.

Mais depuis le 15 aout 2026, elle est aussi appelee par `install.sh`, et
`install.sh` est rejoue par le conteneur a CHAQUE demarrage — en
developpement comme en production. Sans garde, un simple
`docker compose restart` refacturerait deux analyses. L'intention du
mainteneur est que l'installation TESTE les cles API, pas qu'elle les
consomme en boucle.
/ The command is replayable by design, but install.sh runs on every
container start: without a guard, a mere restart would re-bill two
analyses. The point is to TEST the API keys, not to burn them.

`--si-absent` rend donc la commande sans effet quand la demonstration
porte deja des extractions. `--reset` reste le moyen explicite de tout
refaire. / --si-absent makes it a no-op once extractions exist.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from core.models import Configuration, Dossier, Page
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.management.commands.charger_fixtures_llm_reel import NOM_DU_CARNET
from hypostasis_extractor.models import (
    AnalyseurSyntaxique,
    ExtractedEntity,
    ExtractionJob,
)


class LAnalyseReelleNeSeRefaitPasToute_SeuleTest(TestCase):
    """
    LOCALISATION : front/tests/test_fixtures_llm_reel_idempotence.py
    """

    def setUp(self):
        self.proprietaire = User.objects.create_superuser(
            username="proprio-llm", password="x",
        )
        modele = self._modele_ia()
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = modele
        configuration.save()

        AnalyseurSyntaxique.objects.create(
            name="Hypostasia", is_active=True, type_analyseur="analyser",
            est_par_defaut=True,
        )

    def _modele_ia(self):
        from core.models import AIModel

        return AIModel.objects.create(
            name="Modele d'essai", provider="google",
            model_name="gemini-2.5-flash", is_active=True,
        )

    def _monter_une_demonstration_deja_analysee(self):
        """
        Reproduit l'etat d'apres une premiere installation reussie.
        / Reproduces the state after a first successful install.
        """
        carnet = Dossier.objects.create(
            name=NOM_DU_CARNET, owner=self.proprietaire,
        )
        note = Page.objects.create(
            title="Une note deja analysee", source_type="file",
            html_original="", html_readability="", text_readability="",
            content_hash="deja-analysee", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(note, carnet, self.proprietaire)
        job = ExtractionJob.objects.create(
            page=note, name="analyse", prompt_description="p",
            status="completed",
        )
        ExtractedEntity.objects.create(
            job=job, extraction_class="phenomene",
            extraction_text="une idee extraite par le modele",
            start_char=0, end_char=31,
        )
        return carnet

    def test_sans_si_absent_la_commande_analyse_meme_si_deja_fait(self):
        # Le comportement historique ne change pas : lancee a la main,
        # elle refait tout. / Run by hand, it still redoes everything.
        self._monter_une_demonstration_deja_analysee()

        with patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._analyser_reellement",
        ) as analyse, patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_un_fichier_markdown",
        ), patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_une_capture",
        ):
            call_command("charger_fixtures_llm_reel")

        self.assertGreater(
            analyse.call_count, 0,
            "Sans --si-absent, la commande doit refaire les analyses.",
        )

    def test_avec_si_absent_aucune_analyse_n_est_relancee(self):
        # Le cas de l'installation rejouee : rien ne doit etre facture.
        # / The replayed-install case: nothing must be billed.
        self._monter_une_demonstration_deja_analysee()

        with patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._analyser_reellement",
        ) as analyse:
            call_command("charger_fixtures_llm_reel", "--si-absent")

        self.assertEqual(
            analyse.call_count, 0,
            "La demonstration porte deja des extractions : --si-absent "
            "doit rendre la commande sans effet, sinon chaque demarrage "
            "de conteneur refacture deux appels au modele.",
        )

    def test_avec_si_absent_une_base_neuve_est_bien_analysee(self):
        # L'autre moitie de la garde : si rien n'existe, il faut analyser,
        # sans quoi une installation neuve n'aurait aucune extraction —
        # et les cles API ne seraient jamais testees.
        # / The other half: a fresh base must still be analysed.
        with patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._analyser_reellement",
        ) as analyse, patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_un_fichier_markdown",
        ), patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_une_capture",
        ):
            call_command("charger_fixtures_llm_reel", "--si-absent")

        self.assertEqual(analyse.call_count, 2)

    def test_en_asynchrone_l_analyse_part_dans_la_file_celery(self):
        """
        L'installation ne doit pas attendre le modele.
        / The install must not wait on the model.

        LOCALISATION : front/tests/test_fixtures_llm_reel_idempotence.py

        Decision du mainteneur (15 aout 2026) : les analyses partent dans
        la file Celery, et se suivent depuis le menu des taches de
        l'utilisateur administrateur. En synchrone, l'installation
        bloquait le demarrage du conteneur pendant chaque appel au
        modele, sans que personne ne puisse voir ou elle en etait.
        / Analyses go through the Celery queue and are followed from the
        admin's task menu, instead of blocking container startup.
        """
        with patch(
            "hypostasis_extractor.tasks_element."
            "analyser_une_page_avec_le_moteur_element.delay",
        ) as envoi_en_file, patch(
            "hypostasis_extractor.tasks_element."
            "analyser_une_page_avec_le_moteur_element.apply",
        ) as execution_immediate, patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_un_fichier_markdown",
        ), patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_une_capture",
        ), patch(
            "core.models.Page.elements",
        ):
            call_command("charger_fixtures_llm_reel", "--asynchrone")

        self.assertEqual(
            execution_immediate.call_count, 0,
            "En asynchrone, l'analyse ne doit pas etre executee sur place.",
        )
        self.assertGreater(
            envoi_en_file.call_count, 0,
            "L'analyse doit partir dans la file Celery (.delay), pour se "
            "suivre depuis le menu des taches.",
        )

    def test_un_job_en_attente_compte_comme_deja_analyse(self):
        """
        Une analyse partie en file ne doit pas etre relancee au demarrage
        suivant. / A queued analysis must not be re-queued on next start.

        En asynchrone, les extractions n'existent pas encore quand le
        conteneur redemarre : ne regarder qu'elles ferait repartir les
        appels — et donc refacturer — a chaque redemarrage tant que la
        file n'a pas ete videe.
        / Extractions do not exist yet while the job is queued; watching
        only them would re-bill on every restart.
        """
        carnet = Dossier.objects.create(
            name=NOM_DU_CARNET, owner=self.proprietaire,
        )
        note = Page.objects.create(
            title="Note en cours d'analyse", source_type="file",
            html_original="", html_readability="", text_readability="",
            content_hash="en-cours", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(note, carnet, self.proprietaire)
        ExtractionJob.objects.create(
            page=note, name="analyse", prompt_description="p",
            status="pending",
        )

        with patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._analyser_reellement",
        ) as analyse:
            call_command("charger_fixtures_llm_reel", "--si-absent")

        self.assertEqual(analyse.call_count, 0)

    def test_reset_supprime_une_note_dont_les_elements_sont_ancres(self):
        """
        `--reset` doit savoir defaire ce que l'analyse a produit.
        / --reset must undo what the analysis produced.

        LOCALISATION : front/tests/test_fixtures_llm_reel_idempotence.py

        Defaut constate le 15 aout 2026, en conditions reelles : des la
        PREMIERE execution reussie, `--reset` levait une ProtectedError.
        Une analyse produit des ancrages, un ancrage protege son
        ElementDocument, et un ElementDocument protege sa Page —
        `page.delete()` etait donc refuse. L'option de remise a zero ne
        fonctionnait qu'avant d'avoir servi a quelque chose.
        / From the very first successful run, --reset raised
        ProtectedError: an anchor protects its element, which protects
        its page. The reset only worked before it was ever useful.
        """
        from core.models import ElementDocument
        from hypostasis_extractor.models import AncrageExtraction

        carnet = self._monter_une_demonstration_deja_analysee()
        note = Page.objects.filter(
            appartenances_dossiers__dossier=carnet,
        ).first()
        element = ElementDocument.objects.create(
            page=note, ordre=0, label="text", texte="un passage ancre",
            empreinte_contenu="empreinte", reference_docling="#/texts/0",
            chemin_de_section=[], provenance={},
        )
        AncrageExtraction.objects.create(
            extraction=ExtractedEntity.objects.filter(job__page=note).first(),
            element=element, ordre_dans_extraction=0,
            debut_dans_element=0, fin_dans_element=5,
        )

        with patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._analyser_reellement",
        ), patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_un_fichier_markdown",
        ), patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_une_capture",
        ):
            call_command("charger_fixtures_llm_reel", "--reset")

        self.assertFalse(
            Page.objects.filter(pk=note.pk).exists(),
            "--reset n'a pas supprime la note ancree : la remise a zero "
            "est impossible des que l'analyse a produit un ancrage.",
        )

    def test_un_carnet_sans_extraction_est_analyse_malgre_si_absent(self):
        # Cas d'une premiere installation interrompue : le carnet existe,
        # mais l'analyse n'a jamais abouti (cle absente, appel en erreur).
        # Il faut retenter au demarrage suivant, sinon la demonstration
        # resterait nue pour toujours.
        # / An interrupted first install must be retried on next start.
        Dossier.objects.create(name=NOM_DU_CARNET, owner=self.proprietaire)

        with patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._analyser_reellement",
        ) as analyse, patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_un_fichier_markdown",
        ), patch(
            "front.management.commands.charger_fixtures_llm_reel."
            "Command._ingerer_une_capture",
        ):
            call_command("charger_fixtures_llm_reel", "--si-absent")

        self.assertEqual(analyse.call_count, 2)
