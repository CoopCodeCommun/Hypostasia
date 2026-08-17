"""
Le prompt systeme de synthese decrit-il le produit d'aujourd'hui ?
/ Does the synthesis system prompt describe today's product?

LOCALISATION : front/tests/test_prompt_de_synthese_a_jour.py

Ce prompt est enseigne au modele a CHAQUE wiki et a CHAQUE synthese
dirigee (`_prompt_systeme_de_synthese`, front/tasks.py). Deux
evolutions du produit l'ont laisse derriere :

1. Les SIX statuts de debat ont ete fusionnes en DEUX le 2 mai 2026 —
   il n'existe plus que NOUVEAU et COMMENTE
   (`hypostasis_extractor/models.py`). Un prompt qui pondere par
   CONSENSUEL / DISCUTABLE / DISCUTE / CONTROVERSE enseigne un
   vocabulaire que la base ne porte plus.
2. La synthese a cesse d'etre une VERSION d'un texte le 9 aout 2026
   pour devenir une NOTE DU CARNET (SPEC-synthese § 2). Un prompt qui
   demande « une nouvelle version du document » decrit le modele
   abandonne : une synthese de carnet n'a pas de « texte original »,
   elle a un carnet de notes.

Constate le 16 aout 2026 sur un appel reel : le modele a justifie ses
operations par « avec le statut CONSENSUEL ».
/ The prompt taught six abolished statuses and the abandoned
version-of-a-document model; a real call echoed them back.
"""

from django.test import TestCase


class PromptDeSyntheseAJourTest(TestCase):
    """Le prompt ne doit enseigner que ce qui existe. / Only what exists."""

    def setUp(self):
        from front.services.fixtures_analyseurs import (
            creer_les_modeles_ia_et_les_analyseurs,
        )
        creer_les_modeles_ia_et_les_analyseurs()
        from front.tasks import _prompt_systeme_de_synthese
        self.prompt = _prompt_systeme_de_synthese()

    def test_aucun_statut_aboli_n_est_enseigne(self):
        for statut_aboli in (
            "CONSENSUEL", "DISCUTABLE", "DISCUTÉ", "CONTROVERSÉ",
            "NON PERTINENT",
        ):
            self.assertNotIn(
                statut_aboli, self.prompt.upper(),
                f"le prompt enseigne « {statut_aboli} », aboli le "
                f"2 mai 2026",
            )

    def test_les_deux_statuts_reels_sont_enseignes(self):
        self.assertIn("COMMENT", self.prompt.upper())
        self.assertIn("NOUVEAU", self.prompt.upper())

    def test_la_synthese_n_est_pas_presentee_comme_une_version(self):
        # « nouvelle version du document » = le modele abandonne le
        # 9 aout 2026. / The abandoned version-of-a-page model.
        self.assertNotIn("nouvelle version", self.prompt.lower())

    def test_le_prompt_ne_suppose_pas_un_texte_original(self):
        # Une synthese de carnet n'en a pas : son perimetre est un
        # ensemble de notes. / A notebook synthesis has no source text.
        self.assertNotIn("texte original", self.prompt.lower())
