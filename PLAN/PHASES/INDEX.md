# Index des phases — Hypostasia V3

> 28+ prompts sequentiels pour Claude Code, chacun dimensionne pour une session de 30-45 min.

## Mode recommande

| Situation | Mode |
|---|---|
| Phases L (complexes) | `/plan` d'abord, puis implementation |
| Phases M (moderees) | Mode normal directement |
| Phases S (simples) | Mode normal ou Ralph Loop |

## Graphe de dependances

```
PHASE-01 (extract CSS/JS)
  └── PHASE-02 (fonts/CDN)
       ├── PHASE-07 (layout core) ──► PHASE-08 (arbre) ──► PHASE-18 (alignement)
       │                          ──► PHASE-09 (pastilles) ◄── PHASE-06 (modeles)
       │                               ├── PHASE-10 (drawer) ──► PHASE-14 (dashboard)
       │                               ├── PHASE-17 (focus+raccourcis)    ├── PHASE-20 (notifs)
       │                               └── PHASE-19 (heat map)           └── PHASE-21 (mobile)
       └── PHASE-11 (CSS classes)
            └── PHASE-12 (cartes) ──► PHASE-13 (etats)
                                  ──► PHASE-15 (transcription)
                                  ──► PHASE-16 (onboarding)

Independants : PHASE-03, PHASE-04, PHASE-05, PHASE-06, PHASE-22

PHASE-03 ──► PHASE-24 (providers IA)
PHASE-22 ──► PHASE-25 (users base) ──► PHASE-25b (auth extension navigateur)
                                   ──► PHASE-25c (visibilite 3 niveaux + groupes)
                                   │       └── PHASE-25d (invitations email + Explorer) ──► PHASE-25d-v2 (Explorer v2 UX)
                                   ──► PHASE-26a (filtre contributeur) ◄── PHASE-19 (heat map)
                                   │       └── PHASE-26a-bis (filtre multi-contributeurs)
                                   │               └── 26a-ux (scroll, noms, entites, HSL, sauf)
                                   ──► PHASE-26f (modale edition + permissions contributeurs) ◄── PHASE-26c (statuts)
                                   ──► PHASE-26b (analyseurs front + couts + prompts)
                                   ──► PHASE-26g (hub analyse drawer + WS + estimation cout) ◄── PHASE-10 + PHASE-24
                                   ──► PHASE-26h (credits prepays + Stripe) ◄── PHASE-26g + PHASE-26b
                                   ──► PHASE-27a (modeles+historique)
                                   │       ├── PHASE-27b (diff) ──► PHASE-28-light (synthese deliberative)
                                   │       │                    ──► PHASE-27c (SourceLinks manuels) [enrichissement]
                                   │       │                    ──► PHASE-27d (fil reflexion) [enrichissement]
                                   │       │                    ──► PHASE-28 (wizard 5 etapes) [si besoin]
                                   │       └── PHASE-27e (verrous) [independant]
Independant : PHASE-29-normalize (normalisation attributs, ameliore 18+28-light+27c+27d)

Toutes Phase 1 ──► PHASE-23 (Playwright)
```

## Pistes paralleles

- **Piste A (visuelle)** : 01 → 02 → 07 → 08 → 09 → 10 → 11 → 12 → 13 → 14
- **Piste B (backend)** : 03, 04, 05, 06 (tous independants)
- **Piste C (infra)** : 22 (PostgreSQL, a tout moment)
- **Piste D (users)** : 25 → 25b (extension) → 25c (visibilite) → 25d (invitations) → 26a → 26a-bis → 26a-ux

## Suivi d'avancement

> **Mettre a jour ce tableau apres chaque phase.** Claude le lit en debut de session
> pour savoir ou on en est. Remplacer `[ ]` par `[x]` et ajouter la date + le hash du commit.

### Socle technique (Phase 1 du PLAN)

| # | Titre | Taille | Statut | Date | Commit |
|---|---|---|---|---|---|
| [01](PHASE-01.md) | Extraction CSS/JS depuis base.html | M | [x] | 2026-03-11 | 9507c91 |
| [02](PHASE-02.md) | Assets locaux : polices, CDN, collectstatic | M | [x] | 2026-03-11 | 9507c91 |
| [03](PHASE-03.md) | Nettoyage code extraction | S | [x] | 2026-03-10 | — |
| [04](PHASE-04.md) | CRUD manquants | M | [x] | 2026-03-11 | 9507c91 |
| [05](PHASE-05.md) | Extension navigateur robustesse | S | [x] | 2026-03-11 | 9507c91 |
| [06](PHASE-06.md) | Modeles de donnees : statut_debat + masquee | S | [x] | 2026-03-11 | 9507c91 |
| [07](PHASE-07.md) | Refonte layout : suppression 3 colonnes | L | [x] | 2026-03-11 | — |
| [08](PHASE-08.md) | Refonte layout : arbre overlay + toolbar | M | [x] | 2026-03-11 | — |
| [09](PHASE-09.md) | Refonte layout : pastilles marge + cartes inline | L | [x] | 2026-03-11 | — |
| [10](PHASE-10.md) | Refonte layout : drawer vue liste | M | [x] | 2026-03-13 | — |
| [11](PHASE-11.md) | Charte visuelle : typographie + variables CSS | M | [x] | 2026-03-13 | — |
| [12](PHASE-12.md) | Charte visuelle : cartes extraction + statuts | M | [x] | 2026-03-13 | — |
| [13](PHASE-13.md) | Charte visuelle : etats interactifs + empty states | M | [x] | 2026-03-13 | — |
| [14](PHASE-14.md) | Dashboard consensus + actions statut | L | [x] | 2026-03-13 | — |
| [15](PHASE-15.md) | Rythme visuel transcription | M | [x] | 2026-03-12 | |
| [16](PHASE-16.md) | Onboarding + tooltips hypostases | S | [x] | 2026-03-13 | — |
| [17](PHASE-17.md) | Mode focus + raccourcis clavier | M | [x] | 2026-03-13 | — |
| [18](PHASE-18.md) | Alignement basique par hypostases | M | [x] | 2026-03-14 | — |
| [19](PHASE-19.md) | Heat map du debat | S | [x] | 2026-03-14 | — |
| [20](PHASE-20.md) | Notifications de progression | S | [x] | 2026-03-14 | — |
| [21](PHASE-21.md) | Mobile : bottom sheet + responsive | M | [x] | 2026-03-15 | — |
| [22](PHASE-22.md) | PostgreSQL + Redis | M | [x] | 2026-03-14 | — |
| [23](PHASE-23.md) | Setup Playwright E2E | M | [x] | 2026-03-15 | — |

### Phases suivantes (Phases 2-5 du PLAN)

| # | Titre | Taille | Statut | Date | Commit |
|---|---|---|---|---|---|
| [24](PHASE-24.md) | Providers IA unifies | L | [x] | 2026-03-15 | — |
| [25](PHASE-25.md) | Users et partage (auth + owner + partage binaire) | L | [x] | 2026-03-15 | — |
| [25b](PHASE-25b.md) | Auth extension navigateur (token API) | M | [x] | 2026-03-15 | — |
| [25c](PHASE-25c.md) | Visibilite 3 niveaux + groupes + arbre restructure | L | [x] | 2026-03-15 | — |
| [25d](PHASE-25d.md) | Invitation par email + page Explorer | M | [x] | 2026-03-15 | — |
| [26a](PHASE-26.md) | Filtre contributeur sur les commentaires | M | [x] | 2026-03-16 | — |
| [26a-bis](PHASE-26a-bis.md) | Filtre multi-contributeurs (pilules toggle) | S | [x] | 2026-03-16 | — |
| 26a-ux | 5 ameliorations UX filtre contributeurs (scroll, noms, entites, HSL, sauf) | M | [x] | 2026-03-16 | — |
| 26c | Refactoring statuts debat : 6 statuts + ownership + cleanup double badge | M | [x] | 2026-03-17 | — |
| 26d | Palette Wong daltonien-safe + formes + pastilles 16px + aide FALC + fixtures demo | L | [x] | 2026-03-17 | — |
| 26e | Alignement raccourci A toggle dossier + scroll extraction + navigation retour | S | [x] | 2026-03-17 | — |
| 26f | Refonte UX edition extraction (modale + permissions contributeurs + refresh carte inline) | M | [x] | 2026-03-18 | — |
| [26g](PHASE-26g.md) | Hub d'analyse dans le drawer (zero polling, WS, estimation cout, thinking) | L | [x] | 2026-03-18 | — |
| [26b](PHASE-26b.md) | Bibliotheque d'analyseurs (admin-only edit) + couts + historique prompts | L | [x] | 2026-03-20 | — |
| [26h](PHASE-26h.md) | Credits prepays + paiement Stripe (gate avant analyse) | L | [x] | 2026-03-18 | — |
| [27a](PHASE-27a.md) | Tracabilite : modeles + PageEdit logging + historique | M | [x] | 2026-03-20 | — |
| [27b](PHASE-27b.md) | Tracabilite : diff side-by-side entre versions | M | [x] | 2026-03-20 | — |
| [28-light](PHASE-28-light.md) | Synthese deliberative (bouton + prompt + V2 auto) | M | [x] | 2026-03-20 | — |
| [29-normalize](PHASE-29-normalize.md) | Normalisation deterministe des attributs d'extraction (independant) | S | [x] | 2026-03-21 | — |
| [25d-v2](PHASE-25d-v2.md) | Explorer v2 : integration layout, recherche document, curation, preview, superuser | L | [x] | 2026-03-22 | — |
| [27c](PHASE-27c.md) | Tracabilite : SourceLinks manuels + association source-cible (enrichissement) | M | [ ] | | |
| [27d](PHASE-27d.md) | Tracabilite : fil de reflexion (timeline provenance) (enrichissement) | M | [ ] | | |
| [27e](PHASE-27e.md) | Tracabilite : verrous d'edition optimistes | S | [ ] | | |
| [28](PHASE-28.md) | Wizard synthese 5 etapes + export PDF/HTML + provenance (si besoin) | L | [ ] | | |

### Refonte v4 — phases attendues (post-2026-04-26)

> Spec complete : `../INSPIRATION_ATOMIC.md`. Squelettes prets a deroulert dans
> l'Annexe A du meme document. Decision validee : refactoring profond (pas from
> scratch), adoption du modele Atomic-style (1 chunk = 1 extraction), suppression
> de LangExtract.

| # | Titre | Taille | Prerequis | Statut |
|---|---|---|---|---|
| 31 | Chunking markdown-aware (methode rasoir style Atomic) | M | aucun | [ ] |
| 32 | OpenRouter + instructor (provider LLM unifie, structured outputs) | S | PHASE-24 | [ ] |
| 38 | Refonte pipeline extraction Atomic-style (1 chunk = 1 extraction, suppression LangExtract) | L | 31, 32 | [ ] |
| 30 | Sourcage [N] automatique des syntheses deliberatives | M | 28-light, 32 | [ ] |
| 33 | RAG socle (pgvector + pipeline d'embedding) | L | 31, 32 | [ ] |
| 34 | RAG features (recherche semantique, doublons, alignement semantique) | L | 33 | [ ] |
| 36 | Update incremental section_ops (syntheses) | L | 30 | [ ] |
| 35 | Chat agentique avec la base | L | 34 | [ ] |
| 37a | Notifications "ce qui te concerne" | S | 34 | [ ] |
| 37b | Cartographie contributeurs par sujet | M | 34 | [ ] |
| 37c | Detection contradiction cross-document | M | 34 | [ ] |
| 37d | Heat map semantique (extension PHASE-19) | S | 34 | [ ] |
| 37e | Geometrie du debat enrichie (7e facette semantique) | M | 34 | [ ] |
| 37f | Suggestion d'analyseur a l'import | S | 34, 26b | [ ] |

**Ordre suggere** : 31 → 32 → 38 → 30 → 33 → 34 → 36 → 35 → 37 (sous-phases independantes).

**Note importante** : la refonte rend obsoletes plusieurs phases anciennes :
- **PHASE-29-normalize** devient inutile (Pydantic + JSON Schema natif valident a la source)
- **PHASE-27c (SourceLinks manuels)** est largement automatisee par PHASE-30
- **PHASE-27d (fil de reflexion)** profite de la chaine `[N]` plus simple
- **`LANGEXTRACT_OVERRIDES.md`** sera supprime apres PHASE-38

### Phases avancees (non detaillees, post-refonte v4)

| # | Titre | Statut |
|---|---|---|
| 39+ | Live audio MVP | [ ] |
| 40+ | Live audio streaming + collab | [ ] |
| 41+ | Mode local : audit + stack IA | [ ] |
| 42+ | Mode local : hardware + image | [ ] |
| 43+ | WebSocket temps reel collaboratif (push cartes, commentaires, statuts) | [ ] |
| 44+ | Deep Research (LDR — exploration documentaire automatisee) | [ ] |

## Verification apres chaque phase

```bash
uv run python manage.py check        # zero erreur
uv run python manage.py migrate      # si modeles modifies
# Test manuel du flux dans le navigateur
# Commit avec message descriptif
```

---

## Suivi des tests par phase

> **Convention :** apres chaque phase, lister les tests Django et E2E avec leur resultat.
> Permet de detecter les regressions lors des phases suivantes.
> Commande : `docker exec hypostasia_web uv run python manage.py test <module> -v2`

### PHASE-27a — Tracabilite : modeles + PageEdit + historique

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

**E2E :** `front.tests.e2e.test_20_tracabilite.E2ETracabiliteTest` — 5 tests (bloques par infra Playwright Sync/asyncio)

---

### PHASE-27b — Tracabilite : diff side-by-side + alignement hypostases entre versions

**Module :** `front.tests.test_phase27b` | **Derniere execution :** 2026-03-20 | **Resultat : 24/24 OK**

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
| `ComparerActionTest` | `test_comparer_v1_sans_v2_trouve_enfant` | OK |
| `ComparerActionTest` | `test_comparer_f5_page_complete` | OK |
| `ComparerActionTest` | `test_comparer_chaines_differentes_refuse` | OK |
| `AlignementVersionsTest` | `test_alignement_2_versions_avec_extractions` | OK |
| `AlignementVersionsTest` | `test_delta_supprime_si_hypostase_absente_v2` | OK |
| `AlignementVersionsTest` | `test_delta_ajoute_si_hypostase_absente_v1` | OK |
| `AlignementVersionsTest` | `test_delta_conserve_avec_changement_statut` | OK |
| `AlignementVersionsTest` | `test_sans_extraction_message_vide` | OK |
| `AlignementVersionsTest` | `test_comparer_hypostases_htmx_200` | OK |
| `AlignementVersionsTest` | `test_comparer_hypostases_sans_v2_retourne_400` | OK |
| `AlignementVersionsTest` | `test_comparer_hypostases_contient_onglets` | OK |

**E2E :** `front.tests.e2e.test_20_tracabilite.E2EDiffVersionsTest` — 6 tests (bloques par infra Playwright Sync/asyncio)

**Fixtures :** `charger_fixtures_demo` + `demo_alignement_versions.json` (V1 Debat IA + V2 Synthese + 30 entites)

**Extension 27b — Alignement hypostases entre versions :**
- Onglets "Hypostases" (actif par defaut) + "Diff texte" dans la page de comparaison
- Tableau d'alignement avec deltas (ajoute/supprime/conserve + evolution statut)
- Navigation cellule → lecture + scroll + surlignage + carte inline (V1 et V2)
- Raccourci clavier `Z` pour ouvrir/fermer la comparaison de versions
- Bug fix : V1 sans `?v2` trouvait pas la V2 enfant (fallback `restitutions`)
- Bug fix : clic cellule V2 ne marchait pas (selecteur `[data-page-id]` trop large)

---

### PHASE-28-light — Synthese deliberative (bouton + prompt + V2 auto)

**Module :** `front.tests.test_phase28_light` | **Derniere execution :** 2026-03-21 | **Resultat : 31/31 OK**

| Classe | Test | Statut |
|--------|------|--------|
| `PromptSyntheseTest` | `test_prompt_contient_texte_original` | OK |
| `PromptSyntheseTest` | `test_prompt_contient_statuts` | OK |
| `PromptSyntheseTest` | `test_prompt_exclut_non_pertinent` | OK |
| `PromptSyntheseTest` | `test_prompt_exclut_masquees` | OK |
| `PromptSyntheseTest` | `test_prompt_tri_par_statut` | OK |
| `PromptSyntheseTest` | `test_prompt_contient_commentaires` | OK |
| `PromptSyntheseTest` | `test_prompt_contient_resume_ia_depuis_attributes` | OK |
| `PromptSyntheseTest` | `test_prompt_contient_section_consigne` | OK |
| `PromptSyntheseTest` | `test_prompt_sans_entites_affiche_message` | OK |
| `SynthetiserActionTest` | `test_synthetiser_requiert_authentification` | OK |
| `SynthetiserActionTest` | `test_synthetiser_cree_job` | OK |
| `SynthetiserActionTest` | `test_synthetiser_anti_doublon` | OK |
| `SynthetiserActionTest` | `test_synthetiser_sans_analyseur_actif` | OK |
| `SynthetiserActionTest` | `test_synthetiser_sans_modele_ia` | OK |
| `SynthetiserActionTest` | `test_synthetiser_retourne_toast_et_spinner` | OK |
| `SyntheseStatusTest` | `test_status_pending_retourne_spinner` | OK |
| `SyntheseStatusTest` | `test_status_completed_retourne_lien_vers_synthese` | OK |
| `SyntheseStatusTest` | `test_status_error_retourne_message_et_retry` | OK |
| `SyntheseStatusTest` | `test_status_sans_job_retourne_erreur` | OK |
| `SynthetiserTaskTest` | `test_task_cree_page_enfant` | OK |
| `SynthetiserTaskTest` | `test_task_parent_page_est_racine` | OK |
| `SynthetiserTaskTest` | `test_task_version_number_incrementee` | OK |
| `SynthetiserTaskTest` | `test_task_erreur_marque_job_error` | OK |
| `SynthetiserTaskTest` | `test_task_html_echappe_xss` | OK |
| `SynthetiserTaskTest` | `test_task_version_label_correcte` | OK |
| `SynthetiserTaskTest` | `test_task_sans_job_analyse_erreur` | OK |
| `DashboardBoutonTest` | `test_bouton_est_cliquable` | OK |
| `DashboardBoutonTest` | `test_bouton_variante_avertissement` | OK |
| `DashboardBoutonTest` | `test_zone_btn_synthese_presente` | OK |
| `DashboardBoutonTest` | `test_dashboard_entites_nouveau_ne_montre_pas_etat_vide` | OK |
| `DashboardBoutonTest` | `test_dashboard_aucune_entite_montre_etat_vide` | OK |

---

### PHASE-29-normalize — Normalisation deterministe des attributs d'extraction

**Module :** `front.tests.test_phase29_normalize` | **Derniere execution :** 2026-03-21 | **Resultat : 23/23 OK**

| Classe | Test | Statut |
|--------|------|--------|
| `NormalisationClesTest` | `test_resume_avec_accent_et_majuscule` | OK |
| `NormalisationClesTest` | `test_hypostases_singulier_devient_pluriel` | OK |
| `NormalisationClesTest` | `test_mots_cles_avec_tirets` | OK |
| `NormalisationClesTest` | `test_cle_inconnue_conservee` | OK |
| `NormalisationClesTest` | `test_dict_complet_4_cles` | OK |
| `NormalisationClesTest` | `test_dict_vide` | OK |
| `NormalisationClesTest` | `test_collision_cles_garde_premiere_valeur` | OK |
| `NormalisationValeurTest` | `test_accent_sur_hypostase` | OK |
| `NormalisationValeurTest` | `test_hypostases_multiples` | OK |
| `NormalisationValeurTest` | `test_hypostase_hallucinee_supprimee` | OK |
| `NormalisationValeurTest` | `test_typo_corrigee_par_fuzzy_match` | OK |
| `NormalisationValeurTest` | `test_valide_inchangee` | OK |
| `NormalisationValeurTest` | `test_chaine_vide` | OK |
| `NormalisationValeurTest` | `test_les_30_hypostases_connues` | OK |
| `IntegrationTest` | `test_entite_creee_avec_cles_normalisees` | OK |
| `IntegrationTest` | `test_alignement_lecture_directe` | OK |
| `SimplificationAvalTest` | `test_prompt_synthese_lecture_directe` | OK |
| `SimplificationAvalTest` | `test_template_tag_lecture_directe` | OK |
| `SimplificationAvalTest` | `test_template_tag_fallback_entites_non_migrees` | OK |
| `NormaliserTexteTest` | `test_accent_et_majuscule` | OK |
| `NormaliserTexteTest` | `test_tiret_remplace_par_underscore` | OK |
| `NormaliserTexteTest` | `test_espaces_trimmes` | OK |
| `NormaliserTexteTest` | `test_chaine_vide` | OK |

**Migration :** `0024_normalize_entity_attributes` — 465 entites normalisees, 11 hypostases hallucinees supprimees

**Regression :** `front.tests.test_phase28_light` 31/31 OK + `front.tests.test_phase27b` 24/24 OK

---

### Session 2026-03-22 — Approche A + 30 few-shot + flux analyse unifie

**Module :** `front.tests.test_analyse_drawer_unifie` | **Resultat : 16/16 OK**

| Classe | Test | Statut |
|--------|------|--------|
| `AnalyseStatusEnCoursTest` | `test_analyse_status_en_cours_contient_bandeau_progression` | OK |
| `AnalyseStatusEnCoursTest` | `test_analyse_status_en_cours_ne_contient_pas_aucune_analyse` | OK |
| `AnalyseStatusEnCoursTest` | `test_analyse_status_en_cours_contient_cartes_entites` | OK |
| `AnalyseStatusEnCoursTest` | `test_analyse_status_en_cours_utilise_drawer_vue_liste` | OK |
| `AnalyseStatusEnCoursTest` | `test_analyse_status_en_cours_ne_contient_pas_bandeau_vert` | OK |
| `AnalyseStatusEnCoursTest` | `test_analyse_status_en_cours_affiche_message_attente_si_zero_entite` | OK |
| `AnalyseStatusCartesOnlyTest` | `test_cartes_only_ne_contient_pas_bandeau` | OK |
| `AnalyseStatusCartesOnlyTest` | `test_cartes_only_contient_les_cartes` | OK |
| `AnalyseStatusCartesOnlyTest` | `test_cartes_only_contient_oob_texte_annote` | OK |
| `AnalyseStatusCartesOnlyTest` | `test_cartes_only_message_attente_si_zero_entite` | OK |
| `AnalyseStatusTermineeTest` | `test_analyse_terminee_contient_bandeau_vert` | OK |
| `AnalyseStatusTermineeTest` | `test_analyse_terminee_ne_contient_pas_bandeau_progression` | OK |
| `AnalyseStatusTermineeTest` | `test_analyse_terminee_utilise_drawer_vue_liste` | OK |
| `AnalyseStatusTermineeTest` | `test_analyse_terminee_contient_cartes` | OK |
| `AnalyseConsumerSignalTest` | `test_rafraichir_drawer_cible_drawer_cartes_liste` | OK |
| `AnalyseConsumerSignalTest` | `test_analyse_terminee_cible_drawer_contenu` | OK |

**Regression :** `front.tests.test_phases` 742/742 OK

**Pieges resolus :**

1. **MutationObserver + HTMX-WS = incompatible.** Les OOB swaps HTMX via WebSocket
   ne declenchent pas les MutationObserver JS. Solution : injecter un div OOB avec
   `hx-get + hx-trigger="load"` qui force HTMX a lancer la requete automatiquement.

2. **Deux templates = UX incoherente.** `panneau_analyse_en_cours.html` (cartes simples)
   et `drawer_vue_liste.html` (cartes riches) donnaient un rendu different pendant et apres
   l'analyse. Solution : un seul template `drawer_vue_liste.html` avec `analyse_en_cours=True`.

3. **OOB en conflit : cartes vs barre.** Le signal `rafraichir_drawer` ecrasait
   `#drawer-contenu` (tout le drawer), y compris `#barre-progression-analyse` qui etait
   mis a jour par `analyse_progression`. Solution : `rafraichir_drawer` cible
   `#drawer-cartes-liste` (sous-zone) via `?cartes_only=1`.

4. **`{% empty %}` affichait "Aucune analyse" pendant l'analyse.** Solution : conditionner
   avec `{% if analyse_en_cours %}` dans le `{% empty %}` du for loop.

---

### PHASE-25d-v2 — Explorer v2 : integration layout, recherche document, curation, preview, superuser

**Derniere execution :** 2026-03-22 | **Resultat : 742/742 OK** (regression complete)

**Changements :**

| Fichier | Action |
|---------|--------|
| `front/views_explorer.py` | Refonte : `list()` double mode (navigation/recherche), `_navigation_dossiers()`, `_recherche_documents()`, `_extraire_snippet()`, `preview()`, permissions superuser, exclusion propres dossiers, queries curation |
| `front/templates/front/includes/explorer_contenu.html` | **Nouveau** — partial integre au layout (titre + filtres + spinner + curation + resultats) |
| `front/templates/front/includes/explorer_card_document.html` | **Nouveau** — card resultat document (snippet, hypostases, mots-cles, bouton Suivre dossier) |
| `front/templates/front/includes/explorer_preview.html` | **Nouveau** — preview depliable (8 pages max, titre + extrait) |
| `front/templates/front/includes/explorer_curation.html` | **Nouveau** — debats en vitrine (3 controversees + 3 sans commentaire + compteurs statuts Wong) |
| `front/templates/front/includes/explorer_page.html` | **Supprime** — page standalone remplacee par partial integre |
| `front/templates/front/includes/explorer_resultats.html` | Double mode navigation (dossiers) / recherche (documents) |
| `front/templates/front/includes/explorer_card.html` | Chevron preview depliable + badge visibilite superuser + garde suivre (public + pas propre dossier) |
| `front/templates/front/includes/onboarding_vide.html` | Onglets "Decouvrir l'app" / "Explorer les dossiers" |
| `front/templates/front/base.html` | Cascade `explorer_preloaded` + liens HTMX toolbar + sidebar |
| `front/serializers.py` | `ExplorerFiltresSerializer` : +`visibilite`, +`statut` |
| `front/tests/test_phases.py` | `Phase25dExplorerRechercheTest` adapte au mode document-centrique |

**Conformite stack-ccc :** audit OK (ViewSet explicite, DRF Serializer, variables verbeuses FR, commentaires bilingues, LOCALISATION, DEPENDENCIES, FLUX, data-testid, aria-label/live/hidden, hx-indicator)
