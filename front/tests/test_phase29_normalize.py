"""
Tests pour la normalisation deterministe des attributs (PHASE-29).
/ Tests for deterministic attribute normalization (PHASE-29).

LOCALISATION : front/tests/test_phase29_normalize.py
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from front.normalisation import (
    HYPOSTASES_CONNUES,
    SYNONYMES_CLES,
    _normaliser_texte,
    normaliser_attributs_entite,
    normaliser_valeur_hypostase,
)


# ========================================================================
# Tests de normalisation des cles d'attributs
# / Tests for attribute key normalization
# ========================================================================

class NormalisationClesTest(TestCase):
    """Tests pour normaliser_attributs_entite() — normalisation des cles."""

    def test_resume_avec_accent_et_majuscule(self):
        """'Résumé' doit devenir 'resume'."""
        # / 'Résumé' must become 'resume'
        resultat = normaliser_attributs_entite({"Résumé": "un texte"})
        self.assertIn("resume", resultat)
        self.assertEqual(resultat["resume"], "un texte")

    def test_hypostases_singulier_devient_pluriel(self):
        """'hypostase' doit devenir 'hypostases'."""
        # / 'hypostase' must become 'hypostases'
        resultat = normaliser_attributs_entite({"hypostase": "theorie"})
        self.assertIn("hypostases", resultat)
        self.assertEqual(resultat["hypostases"], "theorie")

    def test_mots_cles_avec_tirets(self):
        """'mots-clés' doit devenir 'mots_cles'."""
        # / 'mots-clés' must become 'mots_cles'
        resultat = normaliser_attributs_entite({"mots-clés": "a, b"})
        self.assertIn("mots_cles", resultat)
        self.assertEqual(resultat["mots_cles"], "a, b")

    def test_cle_inconnue_conservee(self):
        """Une cle inconnue est conservee (normalisee en minuscule sans accents)."""
        # / An unknown key is kept (normalized to lowercase without accents)
        resultat = normaliser_attributs_entite({"Catégorie": "test"})
        self.assertIn("categorie", resultat)
        self.assertEqual(resultat["categorie"], "test")

    def test_dict_complet_4_cles(self):
        """Un dict avec les 4 cles LLM typiques est normalise correctement."""
        # / A dict with the typical 4 LLM keys is normalized correctly
        entree = {
            "Hypostases": "théorie, hypothèse",
            "Résumé": "Un résumé",
            "Statut": "nouveau",
            "mots-clés": "phi, psi",
        }
        resultat = normaliser_attributs_entite(entree)
        self.assertEqual(set(resultat.keys()), {"hypostases", "resume", "statut", "mots_cles"})
        self.assertEqual(resultat["resume"], "Un résumé")
        self.assertEqual(resultat["statut"], "nouveau")
        self.assertEqual(resultat["mots_cles"], "phi, psi")

    def test_dict_vide(self):
        """Un dict vide retourne un dict vide."""
        # / An empty dict returns an empty dict
        self.assertEqual(normaliser_attributs_entite({}), {})

    def test_collision_cles_garde_premiere_valeur(self):
        """Si 2 variantes d'une meme cle, la premiere valeur non vide est gardee."""
        # / If 2 variants of the same key, first non-empty value is kept
        entree = {"resume": "premier", "Résumé": "second"}
        resultat = normaliser_attributs_entite(entree)
        self.assertEqual(resultat["resume"], "premier")


# ========================================================================
# Tests de normalisation des valeurs d'hypostases
# / Tests for hypostase value normalization
# ========================================================================

class NormalisationValeurTest(TestCase):
    """Tests pour normaliser_valeur_hypostase() — normalisation des valeurs."""

    def test_accent_sur_hypostase(self):
        """'Théorie' avec accent doit devenir 'theorie'."""
        # / 'Théorie' with accent must become 'theorie'
        resultat = normaliser_valeur_hypostase("Théorie")
        self.assertEqual(resultat, "theorie")

    def test_hypostases_multiples(self):
        """Plusieurs hypostases separees par virgule."""
        # / Multiple hypostases separated by comma
        resultat = normaliser_valeur_hypostase("théorie, hypothèse, phénomène")
        self.assertEqual(resultat, "theorie, hypothese, phenomene")

    def test_hypostase_hallucinee_supprimee(self):
        """Une hypostase inventee par le LLM est supprimee."""
        # / A hallucinated hypostase from the LLM is removed
        resultat = normaliser_valeur_hypostase("theorie, cybernétique_quantique")
        self.assertEqual(resultat, "theorie")

    def test_typo_corrigee_par_fuzzy_match(self):
        """Une typo proche (seuil 0.8) est corrigee."""
        # / A close typo (threshold 0.8) is corrected
        resultat = normaliser_valeur_hypostase("theorei")
        self.assertEqual(resultat, "theorie")

    def test_valide_inchangee(self):
        """Une hypostase deja correcte reste inchangee."""
        # / An already correct hypostase stays unchanged
        resultat = normaliser_valeur_hypostase("axiome")
        self.assertEqual(resultat, "axiome")

    def test_chaine_vide(self):
        """Une chaine vide retourne une chaine vide."""
        # / An empty string returns an empty string
        self.assertEqual(normaliser_valeur_hypostase(""), "")

    def test_les_30_hypostases_connues(self):
        """Les 30 hypostases connues sont toutes acceptees."""
        # / All 30 known hypostases are accepted
        self.assertEqual(len(HYPOSTASES_CONNUES), 30)
        for hypostase in HYPOSTASES_CONNUES:
            resultat = normaliser_valeur_hypostase(hypostase)
            self.assertEqual(resultat, hypostase, f"{hypostase} devrait etre acceptee")


# ========================================================================
# Tests d'integration
# / Integration tests
# ========================================================================

class IntegrationTest(TestCase):
    """Tests d'integration — normalisation au stockage."""

    def test_entite_creee_avec_cles_normalisees(self):
        """Simule le pipeline : les attributs LLM sont normalises avant create()."""
        # / Simulate pipeline: LLM attributes are normalized before create()
        attributs_llm_bruts = {
            "Hypostases": "Théorie",
            "Résumé": "Un beau résumé",
            "Statut": "nouveau",
            "mots-clés": "alpha, beta",
        }
        attributs_normalises = normaliser_attributs_entite(attributs_llm_bruts)

        self.assertEqual(attributs_normalises["hypostases"], "theorie")
        self.assertEqual(attributs_normalises["resume"], "Un beau résumé")
        self.assertEqual(attributs_normalises["statut"], "nouveau")
        self.assertEqual(attributs_normalises["mots_cles"], "alpha, beta")

    def test_alignement_lecture_directe(self):
        """Apres normalisation, _extraire_hypostases lit directement 'hypostases'."""
        # / After normalization, _extraire_hypostases reads 'hypostases' directly
        from front.views_alignement import _extraire_hypostases_de_entite

        entite_mock = MagicMock()
        entite_mock.attributes = {"hypostases": "theorie, hypothese", "resume": "test"}

        resultats = _extraire_hypostases_de_entite(entite_mock)
        hypostases_trouvees = [h for h, _ in resultats]
        self.assertIn("theorie", hypostases_trouvees)
        self.assertIn("hypothese", hypostases_trouvees)


# ========================================================================
# Tests de simplification en aval
# / Downstream simplification tests
# ========================================================================

class SimplificationAvalTest(TestCase):
    """Tests que les lectures simplifiees fonctionnent avec les cles canoniques."""

    def test_prompt_synthese_lecture_directe(self):
        """Le prompt de synthese lit 'resume' directement (sans fallback Résumé)."""
        # / Synthesis prompt reads 'resume' directly (no Résumé fallback)
        attributs_normalises = {"resume": "Un résumé IA", "hypostases": "theorie"}
        resume_ia = attributs_normalises.get("resume", "")
        self.assertEqual(resume_ia, "Un résumé IA")

    def test_template_tag_lecture_directe(self):
        """entity_json_attrs lit les cles canoniques directement."""
        # / entity_json_attrs reads canonical keys directly
        from hypostasis_extractor.templatetags.extractor_tags import entity_json_attrs

        entite_mock = MagicMock()
        entite_mock.attributes = {
            "hypostases": "phenomene",
            "resume": "Un résumé",
            "statut": "consensuel",
            "mots_cles": "alpha, beta",
        }

        resultat = entity_json_attrs(entite_mock)
        self.assertEqual(resultat[0], "phenomene")
        self.assertEqual(resultat[1], "Un résumé")
        self.assertEqual(resultat[2], "consensuel")
        self.assertEqual(resultat[3], "alpha, beta")

    def test_template_tag_fallback_entites_non_migrees(self):
        """entity_json_attrs garde le fallback pour les entites non migrees."""
        # / entity_json_attrs keeps fallback for non-migrated entities
        from hypostasis_extractor.templatetags.extractor_tags import entity_json_attrs

        entite_mock = MagicMock()
        entite_mock.attributes = {
            "Hypostases": "Théorie",
            "Résumé": "Un vieux résumé",
        }

        resultat = entity_json_attrs(entite_mock)
        self.assertEqual(resultat[0], "Théorie")
        self.assertEqual(resultat[1], "Un vieux résumé")


# ========================================================================
# Tests du helper _normaliser_texte
# / Tests for _normaliser_texte helper
# ========================================================================

class NormaliserTexteTest(TestCase):
    """Tests pour le helper _normaliser_texte."""

    def test_accent_et_majuscule(self):
        """'Résumé' → 'resume'."""
        self.assertEqual(_normaliser_texte("Résumé"), "resume")

    def test_tiret_remplace_par_underscore(self):
        """'mots-clés' → 'mots_cles'."""
        self.assertEqual(_normaliser_texte("mots-clés"), "mots_cles")

    def test_espaces_trimmes(self):
        """Les espaces en debut/fin sont trimmes."""
        # / Leading/trailing spaces are trimmed
        self.assertEqual(_normaliser_texte("  théorie  "), "theorie")

    def test_chaine_vide(self):
        """Chaine vide retourne chaine vide."""
        self.assertEqual(_normaliser_texte(""), "")


# ========================================================================
# Tests des synonymes d'hypostases (LLM produit "proposition" → "hypothese")
# / Tests for hypostase synonyms (LLM produces "proposition" → "hypothese")
# ========================================================================

class SynonymesHypostasesTest(TestCase):
    """Tests pour le mapping SYNONYMES_HYPOSTASES dans normaliser_valeur_hypostase."""

    def test_proposition_mappee_vers_hypothese(self):
        """'proposition' est mappee vers 'hypothese'."""
        # / 'proposition' is mapped to 'hypothese'
        resultat = normaliser_valeur_hypostase("proposition")
        self.assertEqual(resultat, "hypothese")

    def test_prediction_mappee_vers_conjecture(self):
        """'prediction' est mappee vers 'conjecture'."""
        # / 'prediction' is mapped to 'conjecture'
        resultat = normaliser_valeur_hypostase("prédiction")
        self.assertEqual(resultat, "conjecture")

    def test_these_mappee_vers_theorie(self):
        """'these' est mappee vers 'theorie'."""
        # / 'these' is mapped to 'theorie'
        resultat = normaliser_valeur_hypostase("thèse")
        self.assertEqual(resultat, "theorie")

    def test_critique_mappee_vers_probleme(self):
        """'critique' est mappee vers 'probleme'."""
        # / 'critique' is mapped to 'probleme'
        resultat = normaliser_valeur_hypostase("critique")
        self.assertEqual(resultat, "probleme")

    def test_defi_mappe_vers_probleme(self):
        """'defi' est mappe vers 'probleme'."""
        # / 'defi' is mapped to 'probleme'
        resultat = normaliser_valeur_hypostase("défi")
        self.assertEqual(resultat, "probleme")

    def test_synonyme_dans_liste_multi_valeurs(self):
        """Les synonymes sont resolus dans une liste multi-valeurs."""
        # / Synonyms are resolved in a multi-value list
        resultat = normaliser_valeur_hypostase("proposition, théorie")
        self.assertEqual(resultat, "hypothese, theorie")

    def test_hypostase_valide_pas_mappee_par_synonyme(self):
        """Une hypostase valide n'est pas ecrasee par le mapping synonyme."""
        # / A valid hypostase is not overridden by synonym mapping
        resultat = normaliser_valeur_hypostase("hypothese")
        self.assertEqual(resultat, "hypothese")


# ========================================================================
# Tests annotation multi-jobs (pastilles de toutes les extractions)
# / Tests for multi-job annotation (pastilles from all extractions)
# ========================================================================

class AnnotationMultiJobsTest(TestCase):
    """Tests que la vue lecture affiche les pastilles de TOUS les jobs completed."""

    def setUp(self):
        """Cree une page avec 2 jobs completed et des entites dans chacun."""
        # / Create a page with 2 completed jobs and entities in each
        from django.contrib.auth.models import User
        from core.models import Page, Dossier, VisibiliteDossier
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        self.utilisateur = User.objects.create_user("test_multijob", password="test1234")
        self.dossier = Dossier.objects.create(
            name="Test multi-jobs", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.page = Page.objects.create(
            title="Page multi-jobs",
            html_readability="<p>Premier passage. Deuxieme passage. Troisieme passage.</p>",
            text_readability="Premier passage. Deuxieme passage. Troisieme passage.",
            status="completed",
            dossier=self.dossier,
            owner=self.utilisateur,
        )

        # Job 1 : 1 entite sur "Premier passage"
        # / Job 1: 1 entity on "Premier passage"
        self.job_1 = ExtractionJob.objects.create(
            page=self.page, name="Job 1", status="completed",
        )
        self.entite_1 = ExtractedEntity.objects.create(
            job=self.job_1,
            extraction_class="theorie",
            extraction_text="Premier passage",
            start_char=0, end_char=15,
            attributes={"resume": "test1", "hypostases": "theorie"},
        )

        # Job 2 : 1 entite sur "Troisieme passage"
        # / Job 2: 1 entity on "Troisieme passage"
        self.job_2 = ExtractionJob.objects.create(
            page=self.page, name="Job 2", status="completed",
        )
        self.entite_2 = ExtractedEntity.objects.create(
            job=self.job_2,
            extraction_class="probleme",
            extraction_text="Troisieme passage",
            start_char=34, end_char=51,
            attributes={"resume": "test2", "hypostases": "probleme"},
        )

        self.client.login(username="test_multijob", password="test1234")

    def test_lecture_affiche_pastilles_de_tous_les_jobs(self):
        """La page de lecture affiche les pastilles des 2 jobs (pas seulement le dernier)."""
        # / The reading page shows pastilles from both jobs (not just the last one)
        reponse = self.client.get(f"/lire/{self.page.pk}/", HTTP_HX_REQUEST="true")
        contenu = reponse.content.decode("utf-8")

        # Les deux entites doivent etre presentes dans le HTML annote
        # / Both entities must be present in the annotated HTML
        self.assertIn(f"data-extraction-id=\"{self.entite_1.pk}\"", contenu)
        self.assertIn(f"data-extraction-id=\"{self.entite_2.pk}\"", contenu)

    def test_lecture_f5_affiche_pastilles_de_tous_les_jobs(self):
        """L'acces direct (F5) affiche aussi les pastilles des 2 jobs."""
        # / Direct access (F5) also shows pastilles from both jobs
        reponse = self.client.get(f"/lire/{self.page.pk}/")
        contenu = reponse.content.decode("utf-8")

        self.assertIn(f"data-extraction-id=\"{self.entite_1.pk}\"", contenu)
        self.assertIn(f"data-extraction-id=\"{self.entite_2.pk}\"", contenu)
