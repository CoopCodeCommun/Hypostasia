"""
Tests pour les surcharges LangExtract (auto-wrap JSON, fences).
/ Tests for LangExtract overrides (JSON auto-wrap, fences).

LOCALISATION : front/tests/test_langextract_overrides.py

Ces tests valident la logique de pre-traitement de la sortie LLM
avant passage au Resolver de langextract. Ils ne necessitent pas
de connexion LLM ni de base de donnees.
/ These tests validate the LLM output pre-processing logic
before passing to the langextract Resolver. They require no
LLM connection or database.

Lancer avec : uv run python manage.py test front.tests.test_langextract_overrides -v2
/ Run with:    uv run python manage.py test front.tests.test_langextract_overrides -v2
"""

import json

from django.test import SimpleTestCase


# =============================================================================
# Fonction utilitaire extraite du code de AnnotateurAvecProgression
# pour pouvoir la tester de maniere isolee.
# / Utility function extracted from AnnotateurAvecProgression code
# so it can be tested in isolation.
# =============================================================================

def pre_traiter_sortie_llm(texte_sortie_llm):
    """
    Pre-traite la sortie brute du LLM avant de la passer au Resolver.
    Reproduit la logique de front/tasks.py:AnnotateurAvecProgression.
    / Pre-processes raw LLM output before passing it to the Resolver.
    Reproduces the logic from front/tasks.py:AnnotateurAvecProgression.

    LOCALISATION : front/tests/test_langextract_overrides.py

    Retourne un tuple (texte_final, a_ete_wrappe).
    / Returns a tuple (final_text, was_wrapped).
    """
    texte_sortie_llm_stripped = texte_sortie_llm.strip()

    # Retirer les fences ```json ... ``` si presentes
    # / Remove ```json ... ``` fences if present
    if texte_sortie_llm_stripped.startswith("```"):
        lignes_sortie = texte_sortie_llm_stripped.split("\n")
        lignes_sortie = lignes_sortie[1:]
        if lignes_sortie and lignes_sortie[-1].strip() == "```":
            lignes_sortie = lignes_sortie[:-1]
        texte_sortie_llm_stripped = "\n".join(lignes_sortie).strip()

    # Si la sortie est un tableau JSON nu, le wrapper
    # dans {"extractions": [...]} pour que le Resolver l'accepte.
    # / If output is a bare JSON array, wrap it
    # / in {"extractions": [...]} so the Resolver accepts it.
    a_ete_wrappe = False
    if texte_sortie_llm_stripped.startswith("["):
        try:
            tableau_extractions_brut = json.loads(texte_sortie_llm_stripped)
            texte_sortie_llm = json.dumps({"extractions": tableau_extractions_brut})
            a_ete_wrappe = True
        except json.JSONDecodeError:
            # JSON tronque — laisser le resolver gerer
            # / Truncated JSON — let the resolver handle it
            texte_sortie_llm = texte_sortie_llm

    return texte_sortie_llm, a_ete_wrappe


# =============================================================================
# Tests de la logique de wrapping des tableaux JSON nus
# / Tests for bare JSON array wrapping logic
# =============================================================================


class AutoWrapTableauJSONTest(SimpleTestCase):
    """
    Verifie que les sorties LLM mal formatees sont corrigees
    avant d'etre passees au Resolver de langextract.
    / Verify that malformed LLM outputs are fixed
    before being passed to the langextract Resolver.
    """

    # -----------------------------------------------------------------
    # Cas 1 : format correct — ne pas modifier
    # / Case 1: correct format — do not modify
    # -----------------------------------------------------------------

    def test_format_correct_non_modifie(self):
        """Un JSON deja wrappe dans {"extractions": [...]} passe tel quel."""
        sortie_llm_correcte = json.dumps({
            "extractions": [
                {
                    "extraction_class": "argument",
                    "extraction_text": "L'IA est un outil",
                    "attributes": {"Resume": "L'IA aide"},
                }
            ]
        })

        resultat, a_ete_wrappe = pre_traiter_sortie_llm(sortie_llm_correcte)

        self.assertFalse(a_ete_wrappe)
        # Le contenu doit rester identique (pas de wrapping)
        # / Content must remain identical (no wrapping)
        donnees_resultat = json.loads(resultat)
        self.assertIn("extractions", donnees_resultat)

    # -----------------------------------------------------------------
    # Cas 2 : tableau JSON nu — doit etre wrappe
    # / Case 2: bare JSON array — must be wrapped
    # -----------------------------------------------------------------

    def test_tableau_nu_wrappe_dans_extractions(self):
        """Un tableau JSON nu [...] est wrappe dans {"extractions": [...]}."""
        sortie_llm_tableau_nu = json.dumps([
            {
                "extraction_class": "argument",
                "extraction_text": "tu exerces ton esprit critique",
                "attributes": {"Resume": "Esprit critique"},
            },
            {
                "extraction_class": "argument",
                "extraction_text": "t'aide a travailler mieux",
                "attributes": {"Resume": "Aide au travail"},
            },
        ])

        resultat, a_ete_wrappe = pre_traiter_sortie_llm(sortie_llm_tableau_nu)

        self.assertTrue(a_ete_wrappe)
        donnees_resultat = json.loads(resultat)
        self.assertIn("extractions", donnees_resultat)
        self.assertEqual(len(donnees_resultat["extractions"]), 2)
        self.assertEqual(
            donnees_resultat["extractions"][0]["extraction_text"],
            "tu exerces ton esprit critique",
        )

    # -----------------------------------------------------------------
    # Cas 3 : tableau JSON avec fences ```json
    # / Case 3: JSON array with ```json fences
    # -----------------------------------------------------------------

    def test_tableau_avec_fences_json(self):
        """Un tableau JSON dans des fences ```json est aussi wrappe."""
        sortie_llm_avec_fences = '```json\n[\n  {"extraction_class": "hypostase", "extraction_text": "test"}\n]\n```'

        resultat, a_ete_wrappe = pre_traiter_sortie_llm(sortie_llm_avec_fences)

        self.assertTrue(a_ete_wrappe)
        donnees_resultat = json.loads(resultat)
        self.assertIn("extractions", donnees_resultat)
        self.assertEqual(len(donnees_resultat["extractions"]), 1)

    # -----------------------------------------------------------------
    # Cas 4 : JSON tronque — ne pas crasher
    # / Case 4: truncated JSON — do not crash
    # -----------------------------------------------------------------

    def test_json_tronque_ne_crashe_pas(self):
        """Un JSON tronque (tableau ouvert mais pas ferme) ne crashe pas."""
        sortie_llm_tronquee = '[{"extraction_class": "argument", "extraction_text": "test'

        resultat, a_ete_wrappe = pre_traiter_sortie_llm(sortie_llm_tronquee)

        # Le wrapping n'a pas pu se faire (JSONDecodeError)
        # / Wrapping could not be done (JSONDecodeError)
        self.assertFalse(a_ete_wrappe)
        # Le texte brut est retourne tel quel pour que le resolver gere
        # / Raw text is returned as-is for the resolver to handle
        self.assertIn("argument", resultat)

    # -----------------------------------------------------------------
    # Cas 5 : fences avec wrapper correct
    # / Case 5: fences with correct wrapper
    # -----------------------------------------------------------------

    def test_fences_avec_wrapper_correct(self):
        """Des fences ```json avec le format {"extractions": [...]} sont gerees."""
        sortie_correcte_avec_fences = (
            '```json\n'
            '{"extractions": [{"extraction_class": "fait", "extraction_text": "test"}]}\n'
            '```'
        )

        resultat, a_ete_wrappe = pre_traiter_sortie_llm(sortie_correcte_avec_fences)

        # Le wrapper est deja present — pas besoin de re-wrapper
        # / Wrapper already present — no need to re-wrap
        self.assertFalse(a_ete_wrappe)

    # -----------------------------------------------------------------
    # Cas 6 : tableau vide
    # / Case 6: empty array
    # -----------------------------------------------------------------

    def test_tableau_vide_wrappe(self):
        """Un tableau vide [] est quand meme wrappe."""
        sortie_llm_vide = "[]"

        resultat, a_ete_wrappe = pre_traiter_sortie_llm(sortie_llm_vide)

        self.assertTrue(a_ete_wrappe)
        donnees_resultat = json.loads(resultat)
        self.assertEqual(donnees_resultat, {"extractions": []})

    # -----------------------------------------------------------------
    # Cas 7 : espaces et retours a la ligne autour du tableau
    # / Case 7: whitespace and newlines around the array
    # -----------------------------------------------------------------

    def test_espaces_autour_du_tableau(self):
        """Les espaces/newlines autour du tableau nu sont geres."""
        sortie_llm_avec_espaces = '\n\n  [{"extraction_class": "a", "extraction_text": "b"}]  \n\n'

        resultat, a_ete_wrappe = pre_traiter_sortie_llm(sortie_llm_avec_espaces)

        self.assertTrue(a_ete_wrappe)
        donnees_resultat = json.loads(resultat)
        self.assertIn("extractions", donnees_resultat)

    # -----------------------------------------------------------------
    # Cas 8 : fences yaml (pas json) — pas de wrapping
    # / Case 8: yaml fences (not json) — no wrapping
    # -----------------------------------------------------------------

    def test_fences_yaml_pas_de_wrapping(self):
        """Des fences ```yaml ne sont pas traitees comme du JSON."""
        sortie_yaml = '```yaml\nextractions:\n  - extraction_class: argument\n```'

        resultat, a_ete_wrappe = pre_traiter_sortie_llm(sortie_yaml)

        # Le YAML ne commence pas par [ apres retrait des fences
        # / YAML doesn't start with [ after fence removal
        self.assertFalse(a_ete_wrappe)


# =============================================================================
# Tests de la documentation des surcharges
# / Tests for overrides documentation
# =============================================================================


class DocumentationSurchargesTest(SimpleTestCase):
    """
    Verifie que la documentation des surcharges LangExtract existe
    et contient les sections requises.
    / Verify that the LangExtract overrides documentation exists
    and contains required sections.
    """

    def setUp(self):
        from django.conf import settings
        self.chemin_doc_surcharges = (
            settings.BASE_DIR / "PLAN" / "LANGEXTRACT_OVERRIDES.md"
        )

    def test_fichier_documentation_existe(self):
        """Le fichier PLAN/LANGEXTRACT_OVERRIDES.md existe."""
        self.assertTrue(
            self.chemin_doc_surcharges.exists(),
            f"Documentation manquante : {self.chemin_doc_surcharges}",
        )

    def test_documentation_contient_checklist_montee_version(self):
        """La documentation contient une checklist de montee de version."""
        contenu_documentation = self.chemin_doc_surcharges.read_text(encoding="utf-8")
        self.assertIn("Checklist", contenu_documentation)

    def test_documentation_mentionne_auto_wrap(self):
        """La documentation mentionne le workaround auto-wrap."""
        contenu_documentation = self.chemin_doc_surcharges.read_text(encoding="utf-8")
        self.assertIn("Auto-wrap", contenu_documentation)

    def test_documentation_mentionne_annotateur(self):
        """La documentation mentionne AnnotateurAvecProgression."""
        contenu_documentation = self.chemin_doc_surcharges.read_text(encoding="utf-8")
        self.assertIn("AnnotateurAvecProgression", contenu_documentation)

    def test_documentation_mentionne_version_langextract(self):
        """La documentation indique la version de langextract couplee."""
        contenu_documentation = self.chemin_doc_surcharges.read_text(encoding="utf-8")
        self.assertIn("v1.1.1", contenu_documentation)


# =============================================================================
# Tests du wrapper ModeleAvecCompteurTokens (PHASE-26b)
# / Tests for ModeleAvecCompteurTokens wrapper (PHASE-26b)
# =============================================================================


class _FauxScoredOutput:
    """Simule un ScoredOutput de langextract. / Simulates a langextract ScoredOutput."""
    def __init__(self, output_text):
        self.output = output_text
        self.score = 1.0


class _FauxModeleLLM:
    """Simule un modele LLM langextract. / Simulates a langextract LLM model."""
    def __init__(self):
        self.requires_fence_output = False
        self.model_id = "fake-model"

    def infer(self, batch_prompts, **kwargs):
        # Retourne un ScoredOutput par prompt / Returns one ScoredOutput per prompt
        resultats = []
        for prompt in batch_prompts:
            resultats.append(_FauxScoredOutput('{"extractions": []}'))
        return resultats


class ModeleAvecCompteurTokensTest(SimpleTestCase):
    """
    Verifie que le proxy ModeleAvecCompteurTokens accumule les tokens
    et preserve l'interface du modele sous-jacent.
    / Verify that ModeleAvecCompteurTokens proxy accumulates tokens
    and preserves the underlying model's interface.
    """

    def setUp(self):
        from front.tasks import ModeleAvecCompteurTokens
        self.faux_modele = _FauxModeleLLM()
        self.wrapper = ModeleAvecCompteurTokens(self.faux_modele)

    def test_accumule_tokens_input(self):
        """Les tokens input sont estimes via len(prompt) // 4."""
        prompt_test = "A" * 100  # 100 chars → 25 tokens estimes
        self.wrapper.infer(batch_prompts=[prompt_test])
        self.assertEqual(self.wrapper.total_input_tokens, 25)

    def test_accumule_tokens_output(self):
        """Les tokens output sont estimes via len(output) // 4."""
        self.wrapper.infer(batch_prompts=["test prompt"])
        # La sortie du faux modele est '{"extractions": []}' = 19 chars → 4 tokens
        self.assertEqual(self.wrapper.total_output_tokens, 4)

    def test_accumule_sur_plusieurs_appels(self):
        """Les tokens s'accumulent sur plusieurs appels infer()."""
        self.wrapper.infer(batch_prompts=["A" * 40])  # 10 tokens input
        self.wrapper.infer(batch_prompts=["B" * 80])  # 20 tokens input
        self.assertEqual(self.wrapper.total_input_tokens, 30)

    def test_preserve_interface_modele(self):
        """__getattr__ delegue au modele sous-jacent."""
        self.assertEqual(self.wrapper.model_id, "fake-model")
        self.assertFalse(self.wrapper.requires_fence_output)

    def test_infer_retourne_resultats(self):
        """infer() retourne bien les resultats du modele."""
        resultats = self.wrapper.infer(batch_prompts=["test"])
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0].output, '{"extractions": []}')
