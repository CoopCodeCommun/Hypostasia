# PHASE-27c — SourceLinks manuels + association source-cible

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-27a + PHASE-27b

---

## 1. Contexte

Le modèle SourceLink existe (créé en 27a) mais n'est ni peuplé ni visible.
Le diff side-by-side (27b) montre **quoi** a changé. Cette phase ajoute le
**pourquoi** : lier manuellement un passage modifié à sa source (extraction,
commentaire, passage original).

Les SourceLinks IA (parsing automatique des références LLM) sont reportés
à PHASE-28 (wizard synthèse). Ici on ne fait que le peuplement **manuel** :
- Auto-peuplement basique lors des éditions (titre, bloc, locuteur)
- Interface pour lier manuellement un passage à sa source

C'est la brique fondamentale de la traçabilité. Sans SourceLinks peuplés,
le fil de réflexion (27d) et la comparaison avec provenance (28) n'ont rien
à afficher.

## 2. Objectifs précis

### 2.1 — Auto-peuplement lors des éditions existantes

Les hooks PageEdit de PHASE-27a capturent l'état avant/après. On étend ces
hooks pour créer un SourceLink quand c'est pertinent :

| Action | SourceLink créé | type_lien |
|--------|----------------|-----------|
| `modifier_titre()` | Oui si la page a un parent | `modifie` |
| `renommer_locuteur()` | Non (pas un changement de contenu textuel) | — |
| `editer_bloc()` | Oui — passage cible = nouveau texte, source = ancien texte | `modifie` |

Pour les pages **avec parent** (restitutions) :
- On peut mapper le passage modifié vers la position dans la version parente
- Le SourceLink pointe vers `page_source=parent, start/end_char_source`

Pour les pages **sans parent** (originaux) :
- Le SourceLink a `page_source=NULL` (auto-modification, pas de chaîne)
- On garde quand même la trace dans PageEdit

### 2.2 — Interface de liaison manuelle

Action `lier_source()` sur LectureViewSet :
- Accessible via un bouton contextuel sur les passages annotés dans le diff (27b)
- L'utilisateur sélectionne un passage dans la version cible → popup
- La popup montre les extractions et commentaires de la version source
- Clic sur une extraction/commentaire → crée le SourceLink
- Le SourceLink est immédiatement visible dans le diff (icône 📎)

**Workflow simplifié (MVP)** :
1. Ouvrir le diff entre V1 et V2 (PHASE-27b)
2. Cliquer sur une zone modifiée (ou un bouton "Lier" sur cette zone)
3. Un panneau latéral ou modal s'ouvre avec :
   - Le passage source (V1) correspondant
   - Les extractions liées à ce passage source
   - Les commentaires sur ces extractions
4. L'utilisateur coche la source pertinente → SourceLink créé
5. Badge 📎 affiché sur la zone dans le diff

### 2.3 — Serializer et validation

- `SourceLinkSerializer` : validation des FK, vérification que les pages existent
- `LierSourceSerializer` : données du formulaire de liaison manuelle
- Vérification que `start_char_cible < end_char_cible`
- Vérification que la page_source est dans la même chaîne de versions

### 2.4 — API pour les SourceLinks d'une page

- Action `source_links()` sur LectureViewSet → retourne les SourceLinks d'une page en JSON
  (pour enrichir le diff côté template sans tout re-rendre)
- Filtre par `page_cible` et optionnellement par plage de caractères

### 2.5 — Peuplement initial basique (passages identiques)

Quand une restitution est créée (dans `front/tasks.py:restituer_debat_task`
ou manuellement) :
- Comparer les paragraphes de la version source et cible
- Pour chaque paragraphe identique : créer un SourceLink type=`identique`
- Pour les passages non mappés : laisser sans SourceLink (warning en PHASE-28)

## 3. Fichiers à modifier

| Fichier | Changement |
|---------|-----------|
| `front/views.py` | +hooks SourceLink dans `editer_bloc`, +`lier_source()`, +`source_links()` |
| `front/serializers.py` | +`SourceLinkSerializer`, +`LierSourceSerializer` |
| `front/templates/front/includes/diff_versions_pages.html` | +bouton "Lier" sur zones modifiées, +badge 📎 |
| `front/templates/front/includes/modal_lier_source.html` | Nouveau — modal liaison manuelle |
| `front/tests/test_phase27c.py` | Tests unitaires |
| `front/tests/e2e/test_20_tracabilite.py` | +tests E2E liaison |

## 4. Critères de validation

- [ ] `uv run python manage.py check` → 0 erreur
- [ ] `editer_bloc` crée un SourceLink pour les pages avec parent
- [ ] L'interface de liaison manuelle permet de lier une zone modifiée à une extraction
- [ ] `source_links()` retourne les SourceLinks en JSON pour une page donnée
- [ ] Le badge 📎 s'affiche sur les zones liées dans le diff
- [ ] Le peuplement initial (passages identiques) fonctionne
- [ ] SourceLinkSerializer valide les données correctement

## 5. Vérification navigateur

1. Avoir 2 versions d'un document (original + restitution)
2. Ouvrir le diff (PHASE-27b)
3. Les zones identiques sont marquées automatiquement (type=identique)
4. Cliquer "Lier" sur une zone modifiée
5. **Attendu** : modal avec les extractions/commentaires de la version source
6. Sélectionner une source → badge 📎 apparaît sur la zone
7. Les zones modifiées sans source restent sans badge (warning futur en PHASE-28)

## 6. Tests prevus

**Module :** `front.tests.test_phase27c` | **Statut : A ECRIRE**

| Classe | Test | Quoi |
|--------|------|------|
| `SourceLinkAutoTest` | `test_editer_bloc_cree_source_link_avec_parent` | SourceLink cree pour page avec parent |
| `SourceLinkAutoTest` | `test_editer_bloc_pas_de_source_link_sans_parent` | Pas de SourceLink si page sans parent |
| `SourceLinkAutoTest` | `test_modifier_titre_cree_source_link_avec_parent` | SourceLink sur modification titre |
| `SourceLinkSerializerTest` | `test_validation_start_inf_end` | start_char < end_char valide |
| `SourceLinkSerializerTest` | `test_validation_meme_chaine_versions` | Refuse si pages de chaines differentes |
| `LierSourceActionTest` | `test_lier_source_cree_source_link` | L'action lier_source cree le lien |
| `LierSourceActionTest` | `test_lier_source_retourne_badge` | Le badge apparait apres liaison |
| `SourceLinksApiTest` | `test_source_links_retourne_json` | L'API retourne les links en JSON |
| `SourceLinksApiTest` | `test_source_links_filtre_par_plage` | Filtre par start/end_char fonctionne |
| `PeuplementInitialTest` | `test_passages_identiques_crees` | Peuplement auto des passages identiques |

**E2E :** `front.tests.e2e.test_20_tracabilite` — tests prevus :
- `test_bouton_lier_visible_sur_zone_modifiee`
- `test_modal_lier_affiche_extractions_source`
- `test_liaison_affiche_badge`
- `test_f5_diff_conserve_badges`

## 7. Notes pour les phases suivantes

- PHASE-27d utilisera ces SourceLinks pour construire le fil de réflexion
- PHASE-28 ajoutera :
  - Le peuplement IA (parsing des `[src:extraction-42]` dans les réponses LLM)
  - Les indicateurs de provenance (✎ / 🤖 / 🤖⚠️) sur chaque SourceLink
  - Le compteur de sourçage en bas du diff
  - Le warning "⚠️ sans source" sur les zones non liées
