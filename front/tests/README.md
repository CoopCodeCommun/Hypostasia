# Tests front — Hypostasia

Tests de validation des phases de développement de l'app `front`.

## Lancer les tests

```bash
# Tous les tests front
uv run python manage.py test front.tests -v2

# Un seul fichier
uv run python manage.py test front.tests.test_phases -v2

# Une seule classe
uv run python manage.py test front.tests.test_phases.Phase01ExtractionCSSJSTest -v2

# Un seul test
uv run python manage.py test front.tests.test_phases.Phase02PolicesLocalesTest.test_toutes_les_polices_presentes -v2
```

## Structure

```
front/tests/
├── __init__.py          # Re-export de tous les tests
├── test_phases.py       # Tests de validation PHASE-01 à PHASE-07
└── README.md            # Ce fichier
```

## Couverture par phase

### PHASE-01 — Extraction CSS/JS depuis base.html

**Classe** : `Phase01ExtractionCSSJSTest` (10 tests)

| Test | Vérifie |
|------|---------|
| `test_fichier_css_existe` | `front/static/front/css/hypostasia.css` existe |
| `test_fichier_js_existe` | `front/static/front/js/hypostasia.js` existe |
| `test_fichier_css_non_vide` | Le CSS fait plus de 100 octets |
| `test_fichier_js_non_vide` | Le JS fait plus de 100 octets |
| `test_pas_de_balise_style_inline` | Aucun bloc `<style>` dans `base.html` |
| `test_pas_de_script_inline` | Aucun `<script>` sans attribut `src` dans `base.html` |
| `test_lien_static_css` | `base.html` charge le CSS via `{% static %}` |
| `test_lien_static_js` | `base.html` charge le JS via `{% static %}` |
| `test_csrf_hx_headers_present` | `hx-headers` et `X-CSRFToken` toujours dans `base.html` |
| `test_template_base_se_charge` | Django peut charger le template sans erreur |

### PHASE-02 — Assets locaux : polices, CDN, collectstatic

**Classe** : `Phase02AucunCDNTest` (2 tests)

| Test | Vérifie |
|------|---------|
| `test_aucun_cdn_dans_base_html` | Aucun domaine CDN dans `base.html` |
| `test_aucun_cdn_dans_tous_les_templates` | Aucun domaine CDN dans tous les fichiers `.html` du projet |

Domaines CDN vérifiés : `cdn.tailwindcss.com`, `unpkg.com`, `cdn.jsdelivr.net`, `fonts.googleapis.com`, `fonts.gstatic.com`, `cdnjs.cloudflare.com`.

---

**Classe** : `Phase02VendorJSTest` (6 tests)

| Test | Vérifie |
|------|---------|
| `test_htmx_local_existe` | `front/static/front/vendor/htmx-2.0.4.min.js` existe |
| `test_htmx_local_non_vide` | Le fichier fait au moins 10 Ko |
| `test_sweetalert2_local_existe` | `front/static/front/vendor/sweetalert2-11.min.js` existe |
| `test_sweetalert2_local_non_vide` | Le fichier fait au moins 10 Ko |
| `test_base_html_charge_htmx_local` | `base.html` charge HTMX via `{% static %}` |
| `test_base_html_charge_sweetalert2_local` | `base.html` charge SweetAlert2 via `{% static %}` |

---

**Classe** : `Phase02TailwindCSSTest` (5 tests)

| Test | Vérifie |
|------|---------|
| `test_tailwind_css_compile_existe` | `front/static/front/css/tailwind.css` existe |
| `test_tailwind_css_taille_raisonnable` | Le CSS compilé fait au moins 50 Ko |
| `test_tailwind_css_contient_classes_utilisees` | Les classes `bg-white`, `text-slate-800`, `flex-1`, `font-semibold` sont présentes |
| `test_base_html_charge_tailwind_local` | `base.html` charge `tailwind.css` via `{% static %}` |
| `test_fichier_source_input_css_existe` | `front/tailwind/input.css` (source Tailwind) existe |

---

**Classe** : `Phase02PolicesLocalesTest` (5 tests)

| Test | Vérifie |
|------|---------|
| `test_repertoire_fonts_existe` | `front/static/front/fonts/` existe |
| `test_toutes_les_polices_presentes` | Les 6 fichiers woff2 requis sont présents (B612, B612 Mono, Srisakdi, Lora) |
| `test_polices_non_vides` | Chaque fichier woff2 fait au moins 5 Ko |
| `test_font_face_dans_tailwind_compile` | Le CSS compilé contient des `@font-face` pour B612, B612 Mono, Srisakdi, Lora |
| `test_urls_woff2_relatives_correctes` | Les URLs dans le CSS compilé utilisent `../fonts/` (chemin relatif correct) |

Polices requises (cf. CLAUDE.md §0 — 3 polices = 3 provenances) :

| Police | Fichier | Provenance |
|--------|---------|------------|
| B612 regular | `b612-regular.woff2` | Police de base (body) |
| B612 bold | `b612-bold.woff2` | Labels système |
| B612 Mono | `b612mono-regular.woff2` | Texte machine (IA) |
| Srisakdi | `srisakdi-regular.woff2` | Intervention lecteur |
| Lora regular | `lora-regular.woff2` | Texte humain cité |
| Lora italic | `lora-italic.woff2` | Texte humain cité (italique) |

---

**Classe** : `Phase02FontBodyTest` (3 tests)

| Test | Vérifie |
|------|---------|
| `test_body_utilise_b612` | `hypostasia.css` déclare `B612` sur le body |
| `test_body_nutilise_plus_inter` | `hypostasia.css` ne référence plus `Inter` dans un `font-family` |
| `test_lecture_article_utilise_lora` | La classe `.lecture-article` utilise `Lora` |

---

**Classe** : `Phase02CollectstaticTest` (3 tests)

| Test | Vérifie |
|------|---------|
| `test_static_root_configure` | `settings.STATIC_ROOT` est défini |
| `test_static_url_configure` | `settings.STATIC_URL` est défini |
| `test_staticfiles_app_installee` | `django.contrib.staticfiles` est dans `INSTALLED_APPS` |

---

**Classe** : `Phase02PageAccueilSansErreurTest` (5 tests)

| Test | Vérifie |
|------|---------|
| `test_page_accueil_status_200` | `GET /` retourne un status 200 |
| `test_page_accueil_contient_tailwind_css` | Le HTML rendu contient un lien vers `tailwind.css` |
| `test_page_accueil_contient_hypostasia_css` | Le HTML rendu contient un lien vers `hypostasia.css` |
| `test_page_accueil_contient_htmx` | Le HTML rendu contient un lien vers `htmx` |
| `test_page_accueil_sans_cdn` | Le HTML rendu ne contient aucun domaine CDN |

### PHASE-03 — Nettoyage code extraction

**Classe** : `Phase03AnalyserEndpointStockeAnalyseurIdTest` (2 tests)

| Test | Vérifie |
|------|---------|
| `test_analyser_cree_job_avec_analyseur_id` | POST `/lire/{id}/analyser/` crée un job avec `analyseur_id` dans `raw_result` |
| `test_analyser_ne_stocke_plus_examples_data` | Le job créé ne contient plus `examples_data` dans `raw_result` |

---

**Classe** : `Phase03AnalyserPageTaskUtiliseFonctionCommuneTest` (1 test)

| Test | Vérifie |
|------|---------|
| `test_task_charge_analyseur_depuis_raw_result` | `analyser_page_task` utilise `analyseur_id` de `raw_result` pour charger les exemples |

### PHASE-04 — CRUD manquants

**Classe** : `Phase04CRUDEndpointsTest` (tests CRUD)

Tests de validation des endpoints CRUD ajoutés en PHASE-04 (renommage pages, dossiers, suppression commentaires, etc.).

### PHASE-05 — Extension navigateur robustesse

Tests de validation de la robustesse de l'extension navigateur (PHASE-05).

### PHASE-06 — Modèles de données : statut_debat + masquee

**Classe** : `Phase06ChampStatutDebatTest` (4 tests)

| Test | Vérifie |
|------|---------|
| `test_champ_statut_debat_existe` | `ExtractedEntity` a un champ `statut_debat` |
| `test_statut_debat_defaut_discutable` | Le défaut est `"discutable"` |
| `test_statut_debat_choices_complets` | Les 4 valeurs (`consensuel`, `discutable`, `discute`, `controverse`) sont présentes |
| `test_statut_debat_max_length_suffisant` | `max_length` >= 11 (longueur de `"controverse"`) |

---

**Classe** : `Phase06ChampMasqueeTest` (3 tests)

| Test | Vérifie |
|------|---------|
| `test_champ_masquee_existe` | `ExtractedEntity` a un champ `masquee` |
| `test_masquee_defaut_false` | Le défaut est `False` |
| `test_masquee_est_boolean` | Le champ est un `BooleanField` |

---

**Classe** : `Phase06CreationEntiteDefautsTest` (1 test)

| Test | Vérifie |
|------|---------|
| `test_creation_entite_avec_defauts` | `ExtractedEntity.objects.create()` applique `statut_debat="discutable"` et `masquee=False` |

---

**Classe** : `Phase06VariablesCSSStatutTest` (12 tests)

| Test | Vérifie |
|------|---------|
| `test_variable_consensuel_text` | `--statut-consensuel-text` définie dans `hypostasia.css` |
| `test_variable_consensuel_bg` | `--statut-consensuel-bg` définie |
| `test_variable_consensuel_accent` | `--statut-consensuel-accent` définie |
| `test_variable_discutable_text` | `--statut-discutable-text` définie |
| `test_variable_discutable_bg` | `--statut-discutable-bg` définie |
| `test_variable_discutable_accent` | `--statut-discutable-accent` définie |
| `test_variable_discute_text` | `--statut-discute-text` définie |
| `test_variable_discute_bg` | `--statut-discute-bg` définie |
| `test_variable_discute_accent` | `--statut-discute-accent` définie |
| `test_variable_controverse_text` | `--statut-controverse-text` définie |
| `test_variable_controverse_bg` | `--statut-controverse-bg` définie |
| `test_variable_controverse_accent` | `--statut-controverse-accent` définie |

### PHASE-07 — Refonte layout : suppression 3 colonnes, lecteur mono-colonne

**Classe** : `Phase07LayoutMonoColonneBaseHtmlTest` (13 tests)

| Test | Vérifie |
|------|---------|
| `test_sidebar_left_supprimee` | `base.html` ne contient plus `id="sidebar-left"` |
| `test_pas_de_flex_3_colonnes` | Le conteneur flex 3 colonnes est supprimé |
| `test_sidebar_right_cachee` | `sidebar-right` existe toujours mais a la classe `hidden` |
| `test_panneau_extractions_existe` | `#panneau-extractions` est conservé comme cible OOB |
| `test_toggle_left_panel_supprime` | Le bouton `#toggle-left-panel` est supprimé |
| `test_toggle_right_panel_supprime` | Le bouton `#toggle-right-panel` est supprimé |
| `test_branding_hypostasia_present` | Le branding "Hypostasia" est dans la toolbar |
| `test_titre_toolbar_present` | Le span `#titre-toolbar` existe pour le titre OOB |
| `test_bouton_import_dans_toolbar` | Le bouton import fichier est dans la toolbar |
| `test_lien_config_llm_dans_toolbar` | Le lien config LLM (engrenage) est dans la toolbar |
| `test_zone_lecture_existe` | `#zone-lecture` est toujours présent |
| `test_zone_lecture_pas_flex1` | `#zone-lecture` n'utilise plus `flex-1` |
| `test_zone_lecture_data_testid` | Le `data-testid` est conservé |

---

**Classe** : `Phase07LecturePrincipaleTest` (4 tests)

| Test | Vérifie |
|------|---------|
| `test_max_width_44rem` | Le conteneur principal utilise `max-width: 44rem` |
| `test_padding_right_marge_reservee` | `padding-right: 3.5rem` (marge réservée PHASE-09) |
| `test_oob_titre_toolbar` | Snippet OOB avec `hx-swap-oob` pour `#titre-toolbar` |
| `test_data_testid_conserve` | `data-testid="lecture-zone-principale"` conservé |

---

**Classe** : `Phase07CSSNettoyageTest` (9 tests)

| Test | Vérifie |
|------|---------|
| `test_pas_de_transition_sidebar_left` | Transitions `#sidebar-left` supprimées |
| `test_pas_de_transition_sidebar_left_collapsed` | Style `#sidebar-left.collapsed` supprimé |
| `test_pas_de_media_query_mobile_overlay` | `@media (max-width: 767px)` supprimé |
| `test_pas_de_mobile_backdrop` | Classe `.mobile-backdrop` supprimée |
| `test_pas_de_debat_mode_sidebar` | Style `#sidebar-right.debat-mode` supprimé |
| `test_styles_lecture_conserves` | `.lecture-article` toujours présent |
| `test_styles_extraction_conserves` | `.hl-extraction` toujours présent |
| `test_styles_tree_arrow_conserves` | `.tree-arrow` toujours présent |
| `test_variables_statut_debat_conservees` | Variables CSS statuts de débat conservées |

---

**Classe** : `Phase07JSNettoyageTest` (11 tests)

| Test | Vérifie |
|------|---------|
| `test_pas_de_estMobile` | `estMobile()` supprimée |
| `test_pas_de_montrerBackdropMobile` | `montrerBackdropMobile()` supprimée |
| `test_pas_de_cacherBackdropMobile` | `cacherBackdropMobile()` supprimée |
| `test_pas_de_gererBackdropMobile` | `gererBackdropMobile()` supprimée |
| `test_pas_de_toggle_left_panel` | Handler `#toggle-left-panel` supprimé |
| `test_pas_de_toggle_right_panel` | Handler `#toggle-right-panel` supprimé |
| `test_pas_de_gererVisibilitePanneauDroit` | `gererVisibilitePanneauDroit()` supprimée |
| `test_pas_de_activerModeDebat` | Listener `activerModeDebat` supprimé |
| `test_ouvrirPanneauDroit_existe_noop` | `ouvrirPanneauDroit()` existe toujours (no-op) |
| `test_onglets_panneau_avec_guard_null` | Onglets du panneau protégés par guard null |
| `test_scrollToCarteDepuisBloc_conserve` | `scrollToCarteDepuisBloc()` conservée |

---

**Classe** : `Phase07VueLectureOOBTitreTest` (2 tests)

| Test | Vérifie |
|------|---------|
| `test_lecture_contient_oob_titre_toolbar` | `GET /lire/{id}/` renvoie un snippet OOB pour `#titre-toolbar` avec le titre |
| `test_lecture_page_sans_titre_affiche_sans_titre` | Page sans titre → "Sans titre" dans le OOB |

## Ajouter des tests pour les phases suivantes

Créer un nouveau fichier `test_phase_XX.py` dans `front/tests/` et l'importer dans `__init__.py` :

```python
# front/tests/test_phase_XX.py
from django.test import TestCase

class PhaseXXExempleTest(TestCase):
    def test_exemple(self):
        ...
```

```python
# front/tests/__init__.py
from front.tests.test_phases import *      # noqa: F401,F403
from front.tests.test_phase_XX import *    # noqa: F401,F403
```
