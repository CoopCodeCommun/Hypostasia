"""
Ce que l'ancienne passe de nuit a laisse en base, et qui ne doit rien
reveiller.
/ What the removed nightly pass left in the database, which must wake
nothing up.

LOCALISATION : front/tests/test_les_vestiges_de_la_nuit.py

La passe de nuit est retiree (SPEC-synthese, addendum du 21 septembre
2026) : plus aucun job ne nait avec le marqueur `MARQUEUR_DU_JOB_DE_NUIT`.
Mais ceux qu'elle a ecrits sont TOUJOURS EN BASE, et le menu des taches
les exclut (`_jobs_qui_s_adressent_a_quelqu_un`, front/views_taches.py).

POURQUOI CETTE EXCLUSION COMPTE : un job de nuit nommait le redacteur
d'un article applique sans demande, pas un destinataire. S'il comptait,
le badge des taches s'allumerait pour lui — et LE CLIC NE L'ETEINDRAIT
PAS : le lien du menu mene a `/lire/<page>/?marquer_lue=…`, or une page
de wiki est redirigee vers `/wikis/<id>/` AVANT que `marquer_lue` ne
soit lu.
/ Old nightly jobs are still stored; the task menu excludes them, or
the badge would light up and the click could not clear it.
"""

from django.test import TestCase

from core.models import Page, TypeDeNote, Wiki
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c
from hypostasis_extractor.models import ExtractionJob


class UnAncienJobDeNuitNAllumePasLeBadgeTest(TestCase):
    """Le badge des taches ignore les vestiges de la nuit."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page_du_wiki = Page.objects.create(
            title="Wiki du seuil", text_readability="## Le seuil\n\nActé.\n",
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-vestiges", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            self.page_du_wiki, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        Wiki.objects.create(
            page=self.page_du_wiki, dossier=self.fixtures["carnet"],
            sujet="Le seuil",
        )

    def _non_lues(self):
        from front.views_taches import _calculer_etat_bouton

        return _calculer_etat_bouton(self.fixtures["demandeur"])[
            "nombre_non_lues"
        ]

    def _un_job_termine(self, raw_result):
        return ExtractionJob.objects.create(
            page=self.page_du_wiki, ai_model=self.fixtures["modele_ia"],
            name="Mise à jour — Le seuil", status="completed",
            raw_result=raw_result,
        )

    def test_un_job_ordinaire_allume_le_badge(self):
        # LE TEMOIN : sans lui, le test d'a cote passerait aussi si le
        # badge ne comptait AUCUN job termine.
        # / The control: otherwise the next test would pass even if no
        # finished job were ever counted.
        avant = self._non_lues()

        self._un_job_termine({"est_maj_wiki": True})

        self.assertEqual(self._non_lues(), avant + 1)

    def test_un_ancien_job_de_nuit_n_allume_pas_le_badge(self):
        from front.tasks import MARQUEUR_DU_JOB_DE_NUIT

        avant = self._non_lues()

        self._un_job_termine({MARQUEUR_DU_JOB_DE_NUIT: True})

        self.assertEqual(self._non_lues(), avant)
