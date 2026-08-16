# PHASE-27a — Modeles tracabilite + PageEdit logging + vue historique

## Contexte

Le cycle Lecture → Extraction → Commentaire → Synthese → Nouvelle version existe
en parties isolees mais il manque le lien structurel entre elles. Cette sous-phase
pose les fondations : modeles de donnees + logging automatique des editions + vue historique.

## Objectifs

1. **PageEdit** — modele d'historique des editions manuelles (titre, contenu, bloc, locuteur)
2. **SourceLink** — modele de liens de provenance (schema seulement, pas d'UI)
3. **Hooks** — creation automatique de PageEdit dans les 3 actions d'edition existantes
4. **Vue historique** — timeline verticale accessible via bouton + F5

## Fichiers modifies

| Fichier | Changement |
|---------|-----------|
| `core/models.py` | +TypeEdit, +PageEdit, +TypeLien, +SourceLink |
| `core/migrations/0026_pageedit_sourcelink.py` | Auto-generee |
| `core/admin.py` | +register PageEdit, SourceLink |
| `front/views.py` | +import PageEdit, +hooks dans 3 actions, +historique() |
| `front/templates/front/includes/historique_page.html` | Nouveau |
| `front/templates/front/includes/lecture_principale.html` | +bouton Historique |
| `front/templates/front/base.html` | +elif historique_preloaded |
| `front/tests/test_phase27a.py` | 15 tests unitaires |
| `front/tests/e2e/test_20_tracabilite.py` | 3 tests E2E |

## Criteres de validation

- [x] `uv run python manage.py check` → 0 erreur
- [x] Migration 0026 generee et appliquee
- [x] 19/19 tests unitaires passent
- [ ] Tests E2E (bouton visible, timeline, F5) — bloques par infra Playwright Sync/asyncio

## Suivi des tests

**Module :** `front.tests.test_phase27a` | **Derniere execution :** 2026-03-20 | **Resultat : 19/19 OK**

| Classe | Test | Statut |
|--------|------|--------|
| `PageEditModelTest` | `test_creation_page_edit_titre` | OK |
| `PageEditModelTest` | `test_creation_page_edit_locuteur` | OK |
| `PageEditModelTest` | `test_creation_page_edit_contenu` | OK |
| `PageEditModelTest` | `test_creation_page_edit_bloc_transcription` | OK |
| `PageEditModelTest` | `test_ordering_par_created_at_desc` | OK |
| `PageEditModelTest` | `test_page_edit_accepte_user_none` | OK |
| `PageEditModelTest` | `test_str_representation` | OK |
| `SourceLinkModelTest` | `test_creation_source_link_basique` | OK |
| `SourceLinkModelTest` | `test_creation_source_link_avec_page_source` | OK |
| `SourceLinkModelTest` | `test_type_lien_choices` | OK |
| `HistoriqueViewTest` | `test_historique_retourne_200_authentifie` | OK |
| `HistoriqueViewTest` | `test_historique_vide_affiche_message` | OK |
| `HistoriqueViewTest` | `test_historique_htmx_contient_data_testid` | OK |
| `HistoriqueViewTest` | `test_historique_f5_retourne_page_complete` | OK |
| `HistoriqueContenuDiffTest` | `test_diff_titre_contient_del_et_ins` | OK |
| `ModifierTitrePageEditTest` | `test_modifier_titre_cree_page_edit` | OK |
| `ModifierTitrePageEditTest` | `test_modifier_titre_description_tronquee_si_trop_longue` | OK |
| `EditerBlocPageEditTest` | `test_editer_bloc_cree_page_edit` | OK |
| `RenommerLocuteurPageEditTest` | `test_renommer_locuteur_cree_page_edit` | OK |

**E2E :** `front.tests.e2e.test_20_tracabilite.E2ETracabiliteTest` — 5 tests definis, bloques par infra Playwright

## Verification navigateur

1. Connecte en tant que jonas/admin1234
2. Ouvrir une page existante
3. Modifier le titre inline → sauvegarder
4. Cliquer "Historique" (sous le switcher versions)
5. **Attendu** : timeline avec l'entree "Titre change : 'ancien' → 'nouveau'"
6. Badge bleu "Titre modifie", user, date, diff rouge/vert
7. F5 sur la page historique → page complete (pas juste le partial)
