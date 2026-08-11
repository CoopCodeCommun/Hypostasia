"""
Tests pour l'utilisabilite des analyseurs d'extraction.
/ Tests for extraction analyzers usability.

LOCALISATION : front/tests/test_utilisabilite_analyseur.py

Un analyseur d'extraction sans exemple few-shot complet fait echouer
LangExtract (le LLM repond hors format, bug "exemples=0"). Ces tests verifient :
- la regle metier services.verifier_utilisabilite_analyseur,
- le serializer AnalyseurUtilisabiliteSerializer qui l'expose,
- l'exclusion des analyseurs non utilisables du selecteur d'analyse
  (front._analyseurs_extraction_utilisables).
La sauvegarde n'est jamais bloquee : on retire seulement l'analyseur des choix.

/ An incomplete extraction analyzer breaks LangExtract. These tests check the
business rule, the serializer exposing it, and the exclusion from the selector.
Saving is never blocked: the analyzer is only removed from the choices.

Lancer avec : uv run python manage.py test front.tests.test_utilisabilite_analyseur -v2
/ Run with:    uv run python manage.py test front.tests.test_utilisabilite_analyseur -v2
"""

from django.test import TestCase

from hypostasis_extractor.models import (
    AnalyseurSyntaxique, AnalyseurExample, ExampleExtraction,
)
from hypostasis_extractor.services import verifier_utilisabilite_analyseur
from hypostasis_extractor.serializers import AnalyseurUtilisabiliteSerializer
from front.views import _analyseurs_extraction_utilisables


class UtilisabiliteAnalyseurTest(TestCase):
    """Regle metier + serializer + exclusion du selecteur."""

    def _creer_analyseur(self, type_analyseur="analyser"):
        # Cree un analyseur actif d'un type donne / Create an active analyzer
        return AnalyseurSyntaxique.objects.create(
            name="Analyseur test", type_analyseur=type_analyseur,
        )

    def _ajouter_exemple_complet(self, analyseur):
        # Ajoute un exemple complet : texte source + une extraction remplie
        # / Add a complete example: source text + one filled extraction
        exemple = AnalyseurExample.objects.create(
            analyseur=analyseur, name="Exemple",
            example_text="Texte source de l'exemple.",
        )
        ExampleExtraction.objects.create(
            example=exemple, extraction_class="hypothese",
            extraction_text="une hypothese",
        )
        return exemple

    # ---- Regle metier / Business rule ----

    def test_analyseur_sans_exemple_non_utilisable(self):
        analyseur = self._creer_analyseur()
        utilisable, problemes = verifier_utilisabilite_analyseur(analyseur)
        self.assertFalse(utilisable)
        self.assertEqual(problemes, ["L'analyseur n'a aucun exemple few-shot."])

    def test_exemple_sans_texte_source_non_utilisable(self):
        analyseur = self._creer_analyseur()
        AnalyseurExample.objects.create(
            analyseur=analyseur, name="Vide", example_text="",
        )
        utilisable, problemes = verifier_utilisabilite_analyseur(analyseur)
        self.assertFalse(utilisable)
        self.assertIn("Aucun exemple n'a de texte source.", problemes)

    def test_exemple_sans_extraction_non_utilisable(self):
        analyseur = self._creer_analyseur()
        AnalyseurExample.objects.create(
            analyseur=analyseur, name="Sans extraction", example_text="Du texte.",
        )
        utilisable, problemes = verifier_utilisabilite_analyseur(analyseur)
        self.assertFalse(utilisable)
        self.assertIn(
            "Aucun exemple ne contient d'extraction exploitable (classe + texte).",
            problemes,
        )

    def test_extraction_incomplete_non_utilisable(self):
        # Extraction avec classe mais sans texte → non exploitable
        # / Extraction with class but no text → not usable
        analyseur = self._creer_analyseur()
        exemple = AnalyseurExample.objects.create(
            analyseur=analyseur, name="Ex", example_text="Du texte.",
        )
        ExampleExtraction.objects.create(
            example=exemple, extraction_class="hypothese", extraction_text="",
        )
        utilisable, _problemes = verifier_utilisabilite_analyseur(analyseur)
        self.assertFalse(utilisable)

    def test_analyseur_complet_utilisable(self):
        analyseur = self._creer_analyseur()
        self._ajouter_exemple_complet(analyseur)
        utilisable, problemes = verifier_utilisabilite_analyseur(analyseur)
        self.assertTrue(utilisable)
        self.assertEqual(problemes, [])

    def test_analyseur_synthese_toujours_utilisable(self):
        # La synthese ne s'appuie pas sur des exemples few-shot
        # / Synthesis does not rely on few-shot examples
        analyseur = self._creer_analyseur(type_analyseur="synthetiser")
        utilisable, problemes = verifier_utilisabilite_analyseur(analyseur)
        self.assertTrue(utilisable)
        self.assertEqual(problemes, [])

    # ---- Serializer ----

    def test_serializer_expose_etat(self):
        analyseur = self._creer_analyseur()
        donnees = AnalyseurUtilisabiliteSerializer(analyseur).data
        self.assertFalse(donnees["est_utilisable"])
        self.assertTrue(donnees["problemes"])

        # Apres ajout d'un exemple complet, l'analyseur devient utilisable
        # / After adding a complete example, the analyzer becomes usable
        self._ajouter_exemple_complet(analyseur)
        donnees_ok = AnalyseurUtilisabiliteSerializer(analyseur).data
        self.assertTrue(donnees_ok["est_utilisable"])
        self.assertEqual(donnees_ok["problemes"], [])

    # ---- Exclusion du selecteur / Selector exclusion ----

    def test_select_exclut_analyseur_non_utilisable(self):
        analyseur_casse = self._creer_analyseur()  # actif mais sans exemple
        analyseur_ok = self._creer_analyseur()
        self._ajouter_exemple_complet(analyseur_ok)

        analyseurs_proposes = _analyseurs_extraction_utilisables()
        self.assertIn(analyseur_ok, analyseurs_proposes)
        self.assertNotIn(analyseur_casse, analyseurs_proposes)

    def test_select_ignore_analyseur_inactif(self):
        # Un analyseur complet mais inactif ne doit pas apparaitre non plus
        # / A complete but inactive analyzer must not appear either
        analyseur_inactif = self._creer_analyseur()
        self._ajouter_exemple_complet(analyseur_inactif)
        analyseur_inactif.is_active = False
        analyseur_inactif.save(update_fields=["is_active"])

        analyseurs_proposes = _analyseurs_extraction_utilisables()
        self.assertNotIn(analyseur_inactif, analyseurs_proposes)
