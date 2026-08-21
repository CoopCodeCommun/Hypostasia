"""
Deux pannes silencieuses autour de la passe de nuit.
/ Two silent failures around the nightly pass.

LOCALISATION : core/tests/test_l_etat_de_la_passe_de_nuit.py

1. **Deux passes en meme temps** : une nuit plus longue que prevu, un
   cron qui repart, et le redacteur est appele deux fois sur les memes
   wikis. La facture double.
2. **Une passe morte** : `terminee_le` reste NULL quand le conteneur
   est tue. Le recapitulatif du matin, qui attend la fin de la passe,
   attendrait POUR TOUJOURS — plus un seul mail, et pas un message.
/ Concurrent passes double the bill; a dead pass would block the mail
forever.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import PasseDeNuit
from core.services.passe_de_nuit import (
    DUREE_MAXIMALE_D_UNE_PASSE, fermer_les_passes_abandonnees,
    passe_en_cours,
)


class UnePasseAbandonneeNeBloqueRienTest(TestCase):
    """La passe morte est fermee, pas attendue. / Dead, not awaited."""

    def test_une_passe_trop_vieille_est_declaree_terminee(self):
        passe = PasseDeNuit.objects.create()
        PasseDeNuit.objects.filter(pk=passe.pk).update(
            lancee_le=timezone.now() - DUREE_MAXIMALE_D_UNE_PASSE
            - timedelta(minutes=1),
        )

        nombre_ferme = fermer_les_passes_abandonnees()

        passe.refresh_from_db()
        self.assertEqual(nombre_ferme, 1)
        self.assertIsNotNone(passe.terminee_le)

    def test_une_passe_recente_reste_en_cours(self):
        passe = PasseDeNuit.objects.create()

        fermer_les_passes_abandonnees()

        passe.refresh_from_db()
        self.assertIsNone(passe.terminee_le)
        self.assertTrue(passe.tourne_encore)

    def test_passe_en_cours_ignore_les_abandonnees(self):
        passe = PasseDeNuit.objects.create()
        PasseDeNuit.objects.filter(pk=passe.pk).update(
            lancee_le=timezone.now() - timedelta(days=2),
        )

        self.assertIsNone(passe_en_cours())

    def test_passe_en_cours_rend_la_passe_vivante(self):
        passe = PasseDeNuit.objects.create()

        self.assertEqual(passe_en_cours(), passe)

    def test_aucune_passe_du_tout(self):
        self.assertIsNone(passe_en_cours())
