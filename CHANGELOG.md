# Changelog — Hypostasia V3

> Journal des modifications par phase. Format bilingue FR/EN.
> Reverse chronological order.

---

## 2026-03-17 — PHASE-26c : Refactoring statuts de debat (6 statuts + ownership)

**Quoi / What:** Refactoring du systeme de statuts de debat : passage de 4 a 6 statuts, ajout du controle d'ownership, suppression du double badge, integration de "masquer" dans le cycle deliberatif.

**Pourquoi / Why:** 3 problemes UX identifies : toutes les extractions demarraient en rouge (alarmant), n'importe quel user pouvait changer le statut, et "masquer" etait deconnecte du cycle deliberatif.

### Changements principaux / Main changes

1. **6 statuts** : nouveau (gris), discutable (orange), discute (ambre), consensuel (vert), controverse (rouge), non_pertinent (gris pale)
2. **Ownership** : seul le proprietaire du dossier peut changer statut, masquer, restaurer
3. **Non pertinent** remplace le boolean `masquee` (synchronise via `save()`)
4. **Double badge supprime** : le `_card_body.html` n'affiche plus le statut en doublon
5. **Auto-promotion** : commentaire sur nouveau/discutable → discute
6. **Dashboard 6 compteurs** : grille 3x2, non_pertinent exclu du calcul de consensus

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | +2 choices, default→nouveau, save() sync masquee |
| `hypostasis_extractor/migrations/0021_*.py` | AlterField + RunPython data migration |
| `front/views.py` | Helper _est_proprietaire_dossier, ownership checks, est_proprietaire contexte |
| `front/serializers.py` | +2 choices ChangerStatutSerializer |
| `front/static/front/css/hypostasia.css` | 6 couleurs statut, discutable rouge→orange |
| `front/static/front/js/marginalia.js` | +2 entrees COULEURS_STATUT |
| `front/static/front/js/keyboard.js` | Check ownership avant raccourci S |
| `front/templates/.../carte_inline.html` | Boutons owner-only, +discutable, +non_pertinent |
| `front/templates/.../_card_body.html` | Suppression double badge statut |
| `front/templates/.../drawer_vue_liste.html` | Masquer/restaurer owner-only, "Non pertinentes" |
| `front/templates/.../dashboard_consensus.html` | Grille 3x2, 6 compteurs |
| `front/templates/front/base.html` | data-est-proprietaire sur #zone-lecture |
| `hypostasis_extractor/templatetags/extractor_tags.py` | +2 icones statut |
| `front/tests/test_phases.py` | ~17 updates + 5 nouvelles classes test |
| `front/management/commands/charger_fixtures_demo.py` | Redistribution 6 statuts |

### Migration
- **Migration necessaire / Migration required:** Oui — `hypostasis_extractor/migrations/0021_refactoring_statuts_debat.py`
- `uv run python manage.py migrate`

---

## 2026-03-16 — PHASE-26a UX : 5 ameliorations filtre multi-contributeurs

**Quoi / What:** 5 ameliorations UX du filtre multi-contributeurs :
1. **Scroll-to-first** : le drawer scrolle en haut apres activation/desactivation d'un filtre
2. **Noms dans compteur** : "2 sur 78 (marie)" au lieu de "2 sur 78"
3. **Badge entites** : la pilule active affiche le nombre d'entites distinctes (pas de commentaires)
4. **Couleur HSL** : chaque contributeur a une couleur deterministe (hash MD5 du username)
5. **Mode Sauf** : bouton "Sauf" pour inverser le filtre (exclure au lieu d'inclure)

**Pourquoi / Why:** Le facilitateur utilise le filtre pour preparer ses reunions de consensus.
Ces ameliorations rendent l'outil plus lisible (couleurs distinctes, noms), plus precis
(entites vs commentaires), et plus flexible (mode exclure pour voir "tout sauf X").

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | Helper `_calculer_teinte_contributeur()`, enrichissement contributeurs (nombre_entites + couleur_hsl), mode `exclure` avec `.exclude()` |
| `front/templates/front/includes/drawer_vue_liste.html` | Compteur avec noms + sauf, pilule-exclue/pilule-active, bouton Sauf, badge entites, commentaires mode inversé |
| `front/static/front/js/drawer_vue_liste.js` | Scroll-to-first, variable `modeFiltre`, handler bouton Sauf, `getContributeursActuels` inclut pilule-exclue |
| `front/static/front/js/marginalia.js` | `appliquerFiltreContributeurs` supporte `modeFiltre` pour inverser le dimming pastilles |
| `front/static/front/css/hypostasia.css` | `.pilule-contributeur.pilule-active` HSL, `.pilule-exclue` hachures, `.pilule-toggle-mode` |
| `front/tests/test_phases.py` | 8 tests : compteur noms, entites count, couleur HSL (3), exclure, compteur sauf, HX-Trigger mode |

### Migration
- **Migration necessaire / Migration required:** Non

---

## 2026-03-16 — PHASE-26a-bis : Filtre multi-contributeurs (pilules toggle)

**Quoi / What:** Remplacement du `<select>` mono-sélection contributeur par des pilules toggle
réutilisant le pattern `.pilule-locuteur` existant (PHASE-15). Supporte la sélection multiple :
cliquer plusieurs pilules → union des commentaires. Le paramètre `?contributeur=` accepte
désormais une liste séparée par virgules (`?contributeur=1,2,3`), rétro-compatible avec le
format single (`?contributeur=42`).

**Pourquoi / Why:** Le facilitateur veut comparer 2+ contributeurs ("qu'est-ce que Marie ET
Thomas ont dit ?"). Les pilules toggle survivent au swap HTMX, zéro JS custom fragile,
mobile-friendly, FALC.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | `drawer_contenu()` : parsing multi-IDs virgule-séparée, `user_id__in`, HX-Trigger `contributeurs_ids` (plural). Renommage `_calculer_scores_temperature_par_contributeurs()`. `LectureViewSet.retrieve()` : parsing multi-IDs. |
| `front/templates/front/includes/drawer_vue_liste.html` | Select+chip → pilules `.pilule-locuteur` toggle + bouton "Tous ×". Conditions `contributeur_actif` → `contributeurs_actifs` (set). |
| `front/static/front/js/drawer_vue_liste.js` | `getContributeursActuels()` (lecture pilules actives), handler clic pilule toggle, suppression handler select/chip. |
| `front/static/front/js/marginalia.js` | `contributeursFiltresActuels = []`, `appliquerFiltreContributeurs()` (array), listener `contributeurs_ids`. |
| `front/static/front/css/hypostasia.css` | +`.pilule-reset-contributeurs`, suppression `.chip-contributeur-actif` et `.btn-retirer-filtre-contributeur`. |
| `front/tests/test_phases.py` | 4 tests existants adaptés + 5 nouveaux tests PHASE-26a-bis (multi-filtre, HX-Trigger multi, pilules, heatmap union, rétro-compat). |

---

## 2026-03-16 — PHASE-26a : Filtre contributeur sur les commentaires

**Quoi / What:** Filtre par contributeur dans le drawer vue liste des extractions.
Quand un contributeur est selectionne, seules les extractions qu'il a commentees
apparaissent, les commentaires des autres sont dimmes (opacite reduite), les pastilles
de marge non concernees sont desactivees, et la heat map se recalcule pour ne compter
que les commentaires de ce contributeur.

**Pourquoi / Why:** Le facilitateur a besoin de filtrer par contributeur pour preparer
les reunions de consensus ("qu'est-ce que Michel a dit ?"). Ce filtre se combine avec
la heat map pour visualiser la temperature du debat du point de vue d'un contributeur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | +helper `_calculer_scores_temperature_par_contributeur()`, modifier `drawer_contenu()` (param contributeur, liste contributeurs, HX-Trigger), modifier `retrieve()` (heat map par contributeur) |
| `front/templates/front/includes/drawer_vue_liste.html` | +dropdown contributeur, +classe dimming commentaires |
| `front/static/front/js/drawer_vue_liste.js` | +param contributeur sur `chargerContenu()`, event listener select, heatmap reload |
| `front/static/front/js/marginalia.js` | +listener `contributeurFiltreChange`, filtrage pastilles, API `getContributeurFiltre`/`resetContributeurFiltre` |
| `front/static/front/css/hypostasia.css` | +`.commentaire-hors-filtre`, +`.pastille-hors-filtre` |
| `front/tests/test_phases.py` | +13 tests unitaires PHASE-26a (7 base + 6 UX) |
| `front/tests/e2e/test_17_filtre_contributeur.py` | **NOUVEAU** — 6 tests E2E |
| `front/management/commands/charger_fixtures_demo.py` | +24 commentaires sur pages Wikipedia (Ostrom, Alexandre, Sadin) par 4 contributeurs, dossier "Petits textes" rendu public |

### Ameliorations UX (post-implementation)
1. Icone personne devant le select contributeur (differencie du select de tri)
2. Chip/badge actif "nom x" pour retirer le filtre en un clic
3. Compteur "N sur M" quand filtre actif (ex: "2 sur 78")
4. Highlight du nom du contributeur filtre dans les commentaires (fond bleu + gras)
5. Badge point bleu sur le bouton toolbar Extractions quand filtre actif

---

## 2026-03-15 — PHASE-25d UX : Ameliorations Explorer

**Quoi / What:** 7 ameliorations UX sur l'Explorer et le systeme d'invitation :
1. Description optionnelle sur les dossiers (champ `description` 200 chars)
2. Compteur de suivis affiche en ambre sur les cards ("3 suivis")
3. Bouton Explorer (globe) ajoute dans la toolbar principale desktop
4. Toasts de confirmation sur Suivre/Ne plus suivre/Inviter
5. Selecteur tri (Plus recents / Plus suivis / Alphabetique)
6. Preview des 3 premiers titres de pages en badges gris dans les cards
7. Fix bug dropdown auteur duplique (Meta.ordering polluait DISTINCT)

**Pourquoi / Why:** Les cards etaient trop minimales (nom + date), l'Explorer
pas assez decouvrable (cache dans le footer de l'arbre uniquement), et pas de
feedback apres les actions Suivre/Inviter.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +champ `description` sur Dossier |
| `core/migrations/0024_dossier_description.py` | Migration auto |
| `front/serializers.py` | +champ `tri` dans ExplorerFiltresSerializer |
| `front/views_explorer.py` | +annotate nombre_suivis, +tri (populaire/nom/recent), +preview pages, +toasts HX-Trigger, fix DISTINCT |
| `front/views.py` | +toast sur action inviter |
| `front/templates/front/includes/explorer_page.html` | +select tri, +listener toast SweetAlert |
| `front/templates/front/includes/explorer_card.html` | +description, +compteur suivis ambre, +preview pages badges |
| `front/templates/front/base.html` | +bouton globe Explorer dans toolbar |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0024_dossier_description.py`
- Commande : `uv run python manage.py migrate`

---

## 2026-03-15 — PHASE-25d : Invitation par email + Explorer + DossierSuivi

**Quoi / What:** Invitation par email pour dossiers et groupes (email connu = partage direct,
email inconnu = invitation avec token + email). Page Explorer pour decouvrir les dossiers publics
(recherche, filtre auteur, pagination). Suivi de dossiers publics (4e section "Suivis" dans l'arbre).
Inscription avec token d'invitation → auto-acceptation.

**Pourquoi / Why:** PHASE-25c imposait de connaitre le username exact pour partager. Pas de
decouverte de contenu public. Pas moyen d'inviter un non-inscrit.

### Fichiers crees / Created files
| Fichier / File | Description |
|---|---|
| `front/views_invitation.py` | InvitationViewSet + helpers (creer, accepter, envoyer email) |
| `front/views_explorer.py` | ExplorerViewSet (list, suivre, ne_plus_suivre) |
| `front/templates/front/includes/explorer_page.html` | Page Explorer complete |
| `front/templates/front/includes/explorer_resultats.html` | Resultats pagines |
| `front/templates/front/includes/explorer_card.html` | Card dossier individuelle |
| `front/templates/front/invitation_erreur.html` | Page erreur invitation |
| `front/templates/front/emails/invitation_dossier.txt` | Email invitation dossier (texte) |
| `front/templates/front/emails/invitation_dossier.html` | Email invitation dossier (HTML) |
| `front/templates/front/emails/invitation_groupe.txt` | Email invitation groupe (texte) |
| `front/templates/front/emails/invitation_groupe.html` | Email invitation groupe (HTML) |
| `front/tests/e2e/test_16_invitation_explorer.py` | 8 tests E2E |
| `core/migrations/0023_dossiersuivi_invitation.py` | Migration auto |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +Invitation, +DossierSuivi |
| `hypostasia/settings.py` | +config email (EMAIL_BACKEND, SITE_URL, etc.) |
| `front/serializers.py` | +InviterEmailSerializer, +ExplorerFiltresSerializer |
| `front/views.py` | +action inviter sur DossierViewSet, _render_arbre 4 sections (+ Suivis) |
| `front/views_auth.py` | Handle ?token= dans register |
| `front/views_groupes.py` | +action inviter sur GroupeViewSet |
| `front/urls.py` | +ExplorerViewSet, +InvitationViewSet |
| `front/templates/front/includes/arbre_dossiers.html` | +section Suivis |
| `front/templates/front/includes/_dossier_node.html` | +bouton Ne plus suivre |
| `front/templates/front/includes/partage_dossier_form.html` | +section email + invitations en attente |
| `front/templates/front/register.html` | +hidden field token |
| `front/templates/front/base.html` | +lien Explorer dans footer arbre |
| `front/tests/test_phases.py` | +18 tests unitaires PHASE-25d |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0023_dossiersuivi_invitation.py`
- Commande : `uv run python manage.py migrate`

---

## 2026-03-15 — PHASE-25c : Visibilite 3 niveaux + groupes + arbre restructure

**Quoi / What:** Systeme de visibilite a 3 niveaux (prive/partage/public) sur les dossiers.
Groupes d'utilisateurs (CRUD) pour faciliter le partage. Arbre restructure en 3 sections
accordeon (Mes dossiers / Partages avec moi / Dossiers publics). Anonymes limites aux dossiers
publics. Controle d'acces lecture/ecriture sur LectureViewSet. Moderation : owner du dossier
peut supprimer les commentaires. Auto-classement des imports dans "Mes imports". Menu contextuel
avec sous-menu visibilite. OOB swaps corriges (centralises via _render_arbre).

**Pourquoi / Why:** Le modele de visibilite PHASE-25 etait binaire (tout ou rien). Pas de
distinction prive/partage/public, pas de groupes, les anonymes voyaient tout.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +VisibiliteDossier, +GroupeUtilisateurs, visibilite sur Dossier, DossierPartage avec groupe+constraints |
| `core/migrations/0022_*.py` | Migration auto |
| `front/views.py` | +3 helpers acces, _render_arbre 3 sections, +changer_visibilite, +quitter, acces LectureViewSet, auto-classify imports, OOB fixes, moderation, DossierViewSet.list filtre |
| `front/views_groupes.py` | **Nouveau** — GroupeViewSet CRUD |
| `front/serializers.py` | +ChangerVisibiliteSerializer, +GroupeCreateSerializer, +GroupeAjouterMembreSerializer |
| `front/urls.py` | +GroupeViewSet |
| `front/templates/front/includes/arbre_dossiers.html` | Rewrite — 3 sections accordeon |
| `front/templates/front/includes/_dossier_node.html` | **Nouveau** — partial reutilisable |
| `front/templates/front/includes/partage_dossier_form.html` | +section groupes |
| `front/static/front/js/arbre_context_menu.js` | +sous-menu visibilite |
| `front/static/front/js/arbre_overlay.js` | +JS accordeon + bouton quitter |
| `front/templates/front/includes/groupe_detail.html` | **Nouveau** — partial template detail groupe |
| `front/tests/test_phases.py` | +23 tests PHASE-25c |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0022_alter_dossierpartage_unique_together_and_more.py`
- Commande : `uv run python manage.py migrate`

---

## 2026-03-15 — PHASE-25b : Auth extension navigateur

**Quoi / What:** Authentification par token API pour l'extension navigateur Chrome.
L'extension envoie le token dans les headers HTTP. POST /api/pages/ exige un token valide (401 sinon).
Page `/auth/token/` pour generer/regenerer le token. Apres recolte, boutons dossiers pour classer
la page. Dossier "A ranger" auto-cree par defaut. Dedup filtree par owner + partages.
Fix URL hardcodee dans sidebar.js.

**Pourquoi / Why:** L'extension fonctionnait sans authentification — impossible de tracer
qui envoie quoi, ni de classer les pages par utilisateur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `hypostasia/settings.py` | +rest_framework.authtoken dans INSTALLED_APPS, +CORS_ALLOW_HEADERS |
| `core/views.py` | TokenAuthentication, owner sur create, endpoints me/mes_dossiers/classer_depuis_extension, dedup filtree owner+partages |
| `front/views_auth.py` | +action mon_token (GET/POST) — generation et regeneration de token |
| `front/templates/front/mon_token.html` | **Nouveau** — page standalone token avec bouton copier/regenerer |
| `front/templates/front/base.html` | Lien "Mon token API" dans dropdown menu utilisateur |
| `extension/popup.js` | Token dans headers, feedback auth, boutons dossiers post-recolte |
| `extension/popup.html` | Zones #authStatus et #dossiersChoix |
| `extension/sidebar.js` | Fix URL hardcodee → lecture serverUrl depuis storage + token dans headers |
| `extension/options.html` | Renommer "Cle API" en "Token d'authentification" + help-text |
| `front/tests/test_phases.py` | +12 tests unitaires PHASE-25b |
| `front/tests/e2e/test_15_token.py` | **Nouveau** — 3 tests E2E page token |

---

## 2026-03-15 — PHASE-25 : Users et partage

**Quoi / What:** Authentification Django (login/register/logout), propriete des ressources
(owner sur Dossier/Page), remplacement de `prenom` par `user` FK obligatoire sur
CommentaireExtraction/Question/ReponseQuestion, partage binaire de dossiers (DossierPartage),
protection des ecritures (lectures restent publiques).

**Pourquoi / Why:** L'app fonctionnait en mono-utilisateur avec identification par prenom libre.
Cette phase ajoute une vraie authentification pour tracer les contributions et permettre
le partage de dossiers entre utilisateurs.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +owner sur Dossier/Page, +DossierPartage, user FK sur Question/ReponseQuestion |
| `hypostasis_extractor/models.py` | user FK remplace prenom sur CommentaireExtraction |
| `core/migrations/0021_*.py` | Migration PHASE-25 (owner, DossierPartage, user FK) |
| `hypostasis_extractor/migrations/0020_*.py` | Migration PHASE-25 (user FK commentaire) |
| `core/admin.py` | Adapte pour user FK |
| `front/views_auth.py` | **Nouveau** — AuthViewSet (login/register/logout) |
| `front/views.py` | +_exiger_authentification(), protection ~28 actions POST, request.user dans create, _render_arbre filtre owner |
| `front/serializers.py` | +LoginSerializer, +RegisterSerializer, +DossierPartageSerializer, -prenom sur 3 serializers |
| `front/urls.py` | Enregistrer AuthViewSet |
| `front/templates/front/login.html` | **Nouveau** — page de connexion |
| `front/templates/front/register.html` | **Nouveau** — page d'inscription |
| `front/templates/front/base.html` | Menu utilisateur dans navbar |
| `front/templates/front/includes/fil_discussion.html` | Supprimer prenom, user FK, layout SMS server-side |
| `front/templates/front/includes/vue_commentaires.html` | Idem |
| `front/templates/front/includes/vue_questionnaire.html` | Supprimer prenom, gater formulaires |
| `front/templates/front/includes/drawer_vue_liste.html` | Affichage user.username |
| `front/templates/front/includes/arbre_dossiers.html` | Bouton partager |
| `front/templates/front/includes/partage_dossier_form.html` | **Nouveau** — formulaire partage |
| `front/management/commands/charger_fixtures_demo.py` | Creer users demo, assigner ownership |
| `front/tests/test_phases.py` | +19 tests unitaires PHASE-25, adaptation tests existants |
| `front/tests/e2e/base.py` | Helpers creer_utilisateur_demo, se_connecter |
| `front/tests/e2e/test_13_auth.py` | **Nouveau** — 10 tests E2E auth |
| `front/tests/e2e/__init__.py` | Import test_13 |
| `hypostasia/settings.py` | LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL |

### Audit stack-ccc

Audit complet de conformite au skill stack-ccc realise. 10 non-conformites detectees et corrigees :
- LOCALISATION ajoutee dans toutes les docstrings (views, serializers, helpers)
- Imports deplaces en haut de fichier (plus d'import interne dans les methodes)
- `role="alert"` + `aria-live="assertive"` sur les zones d'erreurs (login, register)
- `aria-label` sur les formulaires d'authentification et le dropdown menu
- `data-testid` sur tous les elements interactifs du partage (input, boutons, lignes)
- `aria-hidden="true"` sur les SVG decoratifs du partage

### Tests — 712 tests verts (614 unitaires + 98 E2E)

| Suite | Nombre | Statut |
|---|---|---|
| Tests unitaires PHASE-25 | 19 | OK |
| Tests unitaires existants (adaptes) | 595 | OK |
| Tests E2E PHASE-25 (auth) | 10 | OK |
| Tests E2E existants (adaptes) | 88 | OK |

---

## 2026-03-15 — PHASE-24 : Providers IA unifies

**Quoi / What:** Couche d'abstraction unique `core/llm_providers.py` pour les appels LLM directs.
Ajout de 2 nouveaux providers : Ollama (local) et Anthropic (Claude).
Suppression du code mort `core/services.py`.

**Pourquoi / Why:** 3 chemins d'appel LLM disperses dans le code. Cette phase les unifie
en un seul point d'entree `appeler_llm()` et ajoute le support Ollama (gratuit, local)
et Anthropic Claude (reformulation/restitution uniquement).

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `pyproject.toml` | Ajout dependance `anthropic>=0.40` |
| `core/models.py` | Provider +2 (OLLAMA, ANTHROPIC), AIModelChoices +9 modeles, champ `base_url`, prefix_to_provider etendu, tarifs |
| `core/llm_providers.py` | **Nouveau** — fonction unique `appeler_llm()` dispatche vers 5 providers |
| `core/migrations/0020_*.py` | **Nouveau** — migration auto (base_url + choices) |
| `front/tasks.py` | Supprime `_appeler_llm_reformulation()`, remplace par `appeler_llm()` |
| `hypostasis_extractor/services.py` | Ajout Ollama (model_url) et Anthropic (ValueError) dans `resolve_model_params()` |
| `core/services.py` | **Supprime** — code mort (dispatch legacy) |
| `front/tests/test_phases.py` | +10 tests unitaires PHASE-24 |
| `PLAN/PHASES/INDEX.md` | PHASE-24 cochee |

### Migration
- **Migration necessaire / Migration required:** Oui
- `uv run python manage.py migrate` — ajoute `base_url` sur `AIModel`, etend les choices

---

## 2026-03-11 — Corrections post-audit phases 1-6

- Renommage du skill `django-htmx-readable` → `stack-ccc` (CLAUDE.md + dossier `skills/`)
  / Renamed skill `django-htmx-readable` → `stack-ccc` (CLAUDE.md + `skills/` directory)
- Ajout attributs `aria-*` et `data-testid` dans les templates
  / Added `aria-*` and `data-testid` attributes in templates
- Mise a jour INDEX.md (phases 01-06 marquees completees)
  / Updated INDEX.md (phases 01-06 marked as completed)
- Creation de ce CHANGELOG
  / Created this CHANGELOG

**Fichiers modifies / Modified files:**
- `CLAUDE.md`
- `PLAN/PHASES/INDEX.md`
- `front/templates/front/base.html`
- `front/templates/front/includes/arbre_dossiers.html`
- `front/templates/front/includes/panneau_analyse.html`
- `front/templates/front/includes/extraction_results.html`
- `front/templates/front/includes/extraction_manuelle_form.html`
- `front/templates/front/includes/lecture_principale.html`
- `skills/django-htmx-readable/` → `skills/stack-ccc/`
- `CHANGELOG.md` (nouveau / new)

**Migration** : non / no

---

## 2026-03-11 — PHASE-06 : Modeles de donnees (statut_debat + masquee)

- Ajout des champs `statut_debat` et `masquee` sur `ExtractedEntity`
  / Added `statut_debat` and `masquee` fields on `ExtractedEntity`

**Fichiers modifies / Modified files:**
- `hypostasis_extractor/models.py`
- `hypostasis_extractor/migrations/0018_extractedentity_masquee_extractedentity_statut_debat.py`

**Migration** : oui / yes

---

## 2026-03-11 — PHASE-05 : Extension navigateur robustesse

- Amelioration de la robustesse de l'extension navigateur (gestion d'erreurs, retry)
  / Improved browser extension robustness (error handling, retry)

**Fichiers modifies / Modified files:**
- `core/views.py`

**Migration** : non / no

---

## 2026-03-11 — PHASE-04 : CRUD manquants

- Ajout des operations CRUD manquantes (renommer/supprimer dossiers, supprimer pages, deplacer pages)
  / Added missing CRUD operations (rename/delete folders, delete pages, move pages)

**Fichiers modifies / Modified files:**
- `front/views.py`
- `front/templates/front/includes/arbre_dossiers.html`
- `front/static/front/js/hypostasia.js`

**Migration** : non / no

---

## 2026-03-10 — PHASE-03 : Nettoyage code extraction

- Nettoyage et refactorisation du code d'extraction
  / Cleanup and refactoring of extraction code

**Migration** : non / no

---

## 2026-03-11 — PHASE-02 : Assets locaux (polices, CDN, collectstatic)

- Localisation des assets : Tailwind CSS, HTMX, SweetAlert2 en fichiers statiques
  / Localized assets: Tailwind CSS, HTMX, SweetAlert2 as static files
- Ajout des polices Lora (via Google Fonts, sera localise plus tard)
  / Added Lora fonts (via Google Fonts, to be localized later)

**Fichiers modifies / Modified files:**
- `front/templates/front/base.html`
- `front/static/front/css/tailwind.css`
- `front/static/front/css/hypostasia.css`
- `front/static/front/vendor/htmx-2.0.4.min.js`
- `front/static/front/vendor/sweetalert2-11.min.js`

**Migration** : non / no

---

## 2026-03-11 — PHASE-01 : Extraction CSS/JS depuis base.html

- Extraction du CSS inline vers `hypostasia.css` et du JS inline vers `hypostasia.js`
  / Extracted inline CSS to `hypostasia.css` and inline JS to `hypostasia.js`
- Mise en place de la structure `front/static/front/`
  / Set up `front/static/front/` structure

**Fichiers modifies / Modified files:**
- `front/templates/front/base.html`
- `front/static/front/css/hypostasia.css` (nouveau / new)
- `front/static/front/js/hypostasia.js` (nouveau / new)

**Migration** : non / no
