# PHASE-27b — Diff side-by-side entre versions de pages

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-27a

---

## 1. Contexte

Le switcher de versions (pilules V1, V2…) permet de naviguer entre les versions
d'une page, mais on ne peut pas voir **ce qui a changé** entre elles. Un diff
visuel est indispensable pour comprendre l'évolution du texte au fil des itérations.

L'infrastructure existe déjà pour les analyseurs (`_diff_inline_mots` dans
`hypostasis_extractor/views.py`, template `versions_diff.html`). On réutilise
cette logique pour les Pages, au niveau paragraphe.

Pas de superposition de SourceLinks dans cette phase (c'est 27c/27d + 28).
Le diff ici est purement technique : quoi a changé, pas pourquoi.

## 2. Objectifs précis

### 2.1 — Bouton "Comparer" dans le switcher versions

- Visible uniquement si la page a ≥2 versions
- Placé après les pilules de version dans `lecture_principale.html`
- Ouvre le diff en HTMX (remplace #zone-lecture)

### 2.2 — Action `comparer()` sur LectureViewSet

- URL auto : `/lire/{pk}/comparer/?v2={pk2}` (pk = version gauche, v2 = version droite)
- Si `v2` absent : comparer avec le parent direct (`page.parent_page`)
- Si page sans parent et sans v2 → message "Pas d'autre version à comparer"
- Utilise `difflib.SequenceMatcher` au niveau **paragraphe** (split sur `\n\n`)
  pour éviter le bruit d'un diff caractère par caractère sur texte long
- Dans chaque paragraphe modifié, applique `_diff_inline_mots()` pour le
  détail mot par mot
- Pattern F5/HTMX : partial pour HTMX, base.html avec `diff_preloaded` pour F5
- Push-url sur `/lire/{pk}/comparer/?v2={pk2}`

### 2.3 — Template `diff_versions_pages.html`

- Layout 2 colonnes scrollables en sync (scroll de l'une scroll l'autre via JS)
- En-tête : sélecteurs de version (2 dropdowns pour choisir V gauche / V droite)
- Légende couleur : rouge = supprimé, vert = ajouté
- Chaque paragraphe classé comme `identique`, `modifie`, `supprime` ou `ajoute`
- Les paragraphes modifiés contiennent le diff mot-à-mot (`<del>` / `<ins>`)
- Bouton "Retour à la lecture" en haut

### 2.4 — Fonction utilitaire `_diff_paragraphes()`

- Extraire dans un helper réutilisable (sera étendu en PHASE-28 avec les SourceLinks)
- Input : `texte_ancien`, `texte_nouveau` (text_readability des 2 versions)
- Output : liste de tuples `(operation, contenu_gauche, contenu_droite)`
  - operation: `equal`, `replace`, `delete`, `insert`
  - Pour `replace` : contenu_gauche/droite contiennent le HTML du diff mot-à-mot

### 2.5 — Scroll synchronisé (JS minimal)

- Les 2 colonnes du diff scrollent ensemble
- Script léger (~15 lignes) dans le template ou un fichier JS dédié
- Pas de lib externe

## 3. Fichiers à modifier

| Fichier | Changement |
|---------|-----------|
| `front/views.py` | +action `comparer()` sur LectureViewSet, +`_diff_paragraphes()` |
| `front/templates/front/includes/diff_versions_pages.html` | Nouveau — 2 colonnes + diff |
| `front/templates/front/includes/lecture_principale.html` | +bouton "Comparer" dans switcher |
| `front/templates/front/base.html` | +elif `diff_preloaded` |
| `front/tests/test_phase27b.py` | Tests unitaires |
| `front/tests/e2e/test_20_tracabilite.py` | +tests E2E diff |

## 4. Critères de validation

- [x] `uv run python manage.py check` → 0 erreur
- [x] `_diff_paragraphes()` : test avec textes identiques → tous `equal`
- [x] `_diff_paragraphes()` : test avec ajout/suppression/modification de paragraphes
- [x] Action `comparer()` retourne 200 avec partial correct (HTMX)
- [x] F5 sur `/lire/{pk}/comparer/?v2={pk2}` retourne la page complète
- [x] Bouton "Comparer" visible uniquement si ≥2 versions
- [x] Le scroll synchronisé fonctionne
- [x] Fixture V2 "Synthese deliberative" cree avec 12 blocs diff

## Suivi des tests

**Module :** `front.tests.test_phase27b` | **Derniere execution :** 2026-03-20 | **Resultat : 15/15 OK**

| Classe | Test | Statut |
|--------|------|--------|
| `DiffInlineMotsTest` | `test_textes_identiques` | OK |
| `DiffInlineMotsTest` | `test_mot_modifie` | OK |
| `DiffInlineMotsTest` | `test_echappement_html` | OK |
| `DiffParagraphesTest` | `test_textes_identiques` | OK |
| `DiffParagraphesTest` | `test_paragraphe_ajoute` | OK |
| `DiffParagraphesTest` | `test_paragraphe_supprime` | OK |
| `DiffParagraphesTest` | `test_paragraphe_modifie` | OK |
| `DiffParagraphesTest` | `test_textes_vides` | OK |
| `DiffParagraphesTest` | `test_texte_ancien_vide` | OK |
| `DiffParagraphesTest` | `test_texte_nouveau_vide` | OK |
| `ComparerActionTest` | `test_comparer_avec_v2_explicite` | OK |
| `ComparerActionTest` | `test_comparer_sans_v2_utilise_parent` | OK |
| `ComparerActionTest` | `test_comparer_sans_parent_affiche_message` | OK |
| `ComparerActionTest` | `test_comparer_f5_page_complete` | OK |
| `ComparerActionTest` | `test_comparer_chaines_differentes_refuse` | OK |

**E2E :** `front.tests.e2e.test_20_tracabilite.E2EDiffVersionsTest` — 6 tests definis, bloques par infra Playwright

**Fixture :** `charger_fixtures_demo` cree la V2 "Synthese deliberative" du debat (12 blocs diff)

## 5. Vérification navigateur

1. Ouvrir une page qui a ≥2 versions (original + restitution)
2. Le bouton "Comparer" est visible à côté des pilules V1/V2
3. Cliquer "Comparer"
4. **Attendu** : vue 2 colonnes, V1 à gauche, V2 à droite
5. Les paragraphes inchangés sont en texte normal
6. Les paragraphes modifiés ont du rouge (supprimé) et du vert (ajouté)
7. Scroll d'une colonne → l'autre suit
8. Les dropdowns en haut permettent de changer V1/V2
9. F5 → page complète avec le diff

## 6. Code existant réutilisable

- `_diff_inline_mots()` dans `hypostasis_extractor/views.py:1449` — diff mot par mot
- Template `hypostasis_extractor/includes/versions_diff.html` — modèle de layout
- `page.toutes_les_versions` — queryset de toutes les versions
- `page.page_racine` — remonte à la version 1

## 7. Notes pour les phases suivantes

- PHASE-27c ajoutera les SourceLinks manuels, PHASE-27d le fil de réflexion
- PHASE-28 (Étape 5.8) superposera les SourceLinks sur ce diff avec les indicateurs
  de provenance (✎ / 🤖 / 🤖⚠️) et le compteur de sourçage
- Le helper `_diff_paragraphes()` sera étendu pour retourner les positions de caractères
  (nécessaire pour mapper les SourceLinks sur les zones modifiées)
