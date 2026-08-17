"""
Les syntheses etalons se completent quand le perimetre grossit.
/ The reference syntheses catch up when the scope grows.

LOCALISATION : front/tests/test_syntheses_etalons_completent.py

`bin/install.sh` lance `produire_les_syntheses_etalons` APRES
`analyser_les_notes_etalons` — mais les analyses partent dans la file
Celery et ne sont pas finies quand la commande passe. Au PREMIER
demarrage, l'article ne cite donc qu'une partie du corpus : mesure du
17 aout 2026 sur une installation neuve, le perimetre fige portait
65 extractions sur les 101 finalement produites.

Le commentaire d'`install.sh` promettait que « le demarrage suivant
complete ce qui manque ». Un saut base sur « l'article est non vide »
rendait cette promesse FAUSSE : l'article restait a 65 pour toujours.

Le saut compare donc la TAILLE DU PERIMETRE au moment de la production
avec celle d'aujourd'hui. Inchangee, on saute et rien n'est refacture ;
elle a grossi, on reproduit.
/ The install script promises the next start completes what is missing;
a skip on "article not empty" made that promise false.
"""

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from core.models import Page, TypeDeNote
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob


class LesSynthesesEtalonsSeCompletentTest(TestCase):
    """Le saut porte sur la TAILLE DU PERIMETRE, pas sur « non vide »."""

    def setUp(self):
        from front.management.commands.produire_les_syntheses_etalons import (
            NOM_DU_CARNET_ETALON,
        )

        self.fixtures = creer_fixtures_phase_c()
        # La commande cherche le carnet par son nom.
        # / The command finds the notebook by name.
        self.carnet = self.fixtures["carnet"]
        self.carnet.name = NOM_DU_CARNET_ETALON
        self.carnet.save(update_fields=["name"])

        from core.models import Configuration
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = self.fixtures["modele_ia"]
        configuration.save()

    def _produire(self):
        """Lance la commande avec un modele mocke qui cite vraiment."""
        import re as re_module

        def _repondre(_modele_ia, message_complet):
            identifiants = re_module.findall(
                r"Identifiant : ext:(\d+)", message_complet or "",
            )
            if not identifiants:
                return "## Section\n\nRien.\n\nCITATIONS_USED: aucune"
            premier = identifiants[0]
            return (
                f"## Section\n\nUne affirmation.[[ext:{premier}]]\n\n"
                f"CITATIONS_USED: {premier}"
            )

        # Les taches sont jouees EN SYNCHRONE : sans worker, `.delay()`
        # ne ferait rien et l'article resterait vide — la commande
        # reproduirait alors a chaque passage, et le test ne mesurerait
        # pas le saut. En production, le worker les execute.
        # / Run the tasks synchronously: otherwise the article stays empty
        # and the skip is never exercised.
        from front import tasks as taches

        with patch("core.llm_providers.appeler_llm", side_effect=_repondre), \
             patch.object(
                 taches.produire_un_wiki_task, "delay",
                 side_effect=taches.produire_un_wiki_task,
             ), \
             patch.object(
                 taches.produire_une_synthese_de_carnet_task, "delay",
                 side_effect=taches.produire_une_synthese_de_carnet_task,
             ):
            call_command("produire_les_syntheses_etalons")

    def _nombre_de_jobs_d_articles(self):
        return ExtractionJob.objects.filter(
            page__type_de_note__in=[TypeDeNote.WIKI, TypeDeNote.SYNTHESE],
        ).count()

    def test_une_seconde_passe_sans_changement_ne_refacture_rien(self):
        self._produire()
        jobs_apres_la_premiere = self._nombre_de_jobs_d_articles()
        self.assertGreater(jobs_apres_la_premiere, 0)

        self._produire()

        self.assertEqual(
            self._nombre_de_jobs_d_articles(), jobs_apres_la_premiere,
            "un second passage a relancé une production",
        )

    def test_une_extraction_de_plus_declenche_une_reprise(self):
        self._produire()
        jobs_apres_la_premiere = self._nombre_de_jobs_d_articles()

        # Le cas reel : une analyse Celery aboutit APRES la commande.
        # / The real case: a Celery analysis lands after the command.
        ExtractedEntity.objects.create(
            job=self.fixtures["job_analyse"],
            extraction_class="donnee",
            extraction_text="Une extraction arrivée après coup.",
            start_char=0, end_char=34,
        )

        self._produire()

        self.assertGreater(
            self._nombre_de_jobs_d_articles(), jobs_apres_la_premiere,
            "le périmètre a grossi et rien n'a été reproduit",
        )

    def test_les_articles_ne_sont_jamais_dupliques(self):
        self._produire()
        ExtractedEntity.objects.create(
            job=self.fixtures["job_analyse"],
            extraction_class="donnee",
            extraction_text="Une autre extraction tardive.",
            start_char=0, end_char=29,
        )
        self._produire()

        self.assertEqual(
            Page.objects.filter(type_de_note=TypeDeNote.WIKI).count(), 1,
        )
        self.assertEqual(
            Page.objects.filter(type_de_note=TypeDeNote.SYNTHESE).count(), 1,
        )
