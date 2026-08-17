"""
Une tache d'article refuse un job qui n'est pas le sien, SANS y toucher.
/ An article task refuses a job that is not its own, without touching it.

LOCALISATION : front/tests/test_une_tache_ne_touche_que_son_job.py

Constate le 17 aout 2026 sur une installation neuve. Des taches
d'article, lancees depuis la suite de tests, ont atterri sur les jobs
d'ANALYSE 4 et 5 de la base de dev — meme cle primaire, tout autre
objet. Elles ont leve (« KeyError: 'wiki_id' »,
« Page has no synthese_dirigee »), et le gestionnaire d'erreur les a
marques `error`. Consequence : leurs 42 extractions ont cesse d'etre
CITABLES, et le carnet etalon est passe de 101 a 41 extractions
citables. Aucun test n'a echoue.

La cause racine — le broker partage entre la base de test et celle de
dev — est fermee dans `settings.py` (`CELERY_TASK_ALWAYS_EAGER` sous
test). Ceci est la DEUXIEME barriere : quelle que soit la provenance du
message, une tache ne doit jamais degrader un job qu'elle n'a pas
produit. Un job d'analyse qui porte des extractions valides est de la
DONNEE ; le marquer `error` la rend invisible.
/ Root cause closed in settings; this is the second barrier: a task must
never degrade a job it did not create.
"""

from unittest.mock import patch

from django.test import TestCase

from front.tests.test_synthese_phase_c import creer_fixtures_phase_c
from hypostasis_extractor.models import ExtractionJob


class UneTacheNeToucheQueSonJobTest(TestCase):
    """Un job etranger ressort INTACT. / A foreign job comes out intact."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        # Un job d'ANALYSE termine, porteur d'extractions : exactement ce
        # que les taches d'article ont degrade en base de dev.
        # / A completed ANALYSIS job carrying extractions.
        self.job_d_analyse = self.fixtures["job_analyse"]
        self.job_d_analyse.status = "completed"
        self.job_d_analyse.save(update_fields=["status"])

    def _relancer_et_relire(self, tache):
        with patch("core.llm_providers.appeler_llm") as mock_llm:
            tache(self.job_d_analyse.pk)
        self.job_d_analyse.refresh_from_db()
        return mock_llm

    def test_la_production_de_wiki_ne_degrade_pas_un_job_d_analyse(self):
        from front.tasks import produire_un_wiki_task

        mock_llm = self._relancer_et_relire(produire_un_wiki_task)

        self.assertEqual(self.job_d_analyse.status, "completed")
        self.assertIsNone(self.job_d_analyse.error_message)
        self.assertFalse(mock_llm.called, "un appel a été payé pour rien")

    def test_la_synthese_de_carnet_ne_degrade_pas_un_job_d_analyse(self):
        from front.tasks import produire_une_synthese_de_carnet_task

        mock_llm = self._relancer_et_relire(
            produire_une_synthese_de_carnet_task,
        )

        self.assertEqual(self.job_d_analyse.status, "completed")
        self.assertIsNone(self.job_d_analyse.error_message)
        self.assertFalse(mock_llm.called)

    def test_la_mise_a_jour_de_wiki_ne_degrade_pas_un_job_d_analyse(self):
        from front.tasks import proposer_une_maj_de_wiki_task

        mock_llm = self._relancer_et_relire(proposer_une_maj_de_wiki_task)

        self.assertEqual(self.job_d_analyse.status, "completed")
        self.assertIsNone(self.job_d_analyse.error_message)
        self.assertFalse(mock_llm.called)

    def test_les_extractions_du_job_etranger_restent_citables(self):
        # Le point qui compte vraiment : c'est la CITABILITE qui etait
        # perdue, et elle depend du statut du job.
        # / Citability is what was lost, and it hangs on the job status.
        from core.services.synthese import extractions_citables_de_la_note
        from front.tasks import produire_un_wiki_task

        note = self.fixtures["note_source"]
        citables_avant = extractions_citables_de_la_note(note).count()
        self.assertGreater(citables_avant, 0)

        with patch("core.llm_providers.appeler_llm"):
            produire_un_wiki_task(self.job_d_analyse.pk)

        self.assertEqual(
            extractions_citables_de_la_note(note).count(), citables_avant,
        )
