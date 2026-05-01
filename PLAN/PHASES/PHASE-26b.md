# PHASE-26b — Bibliotheque d'analyseurs + couts + historique prompts

> ⚠️ **Vue dediee DEPRECATED 2026-05-01 — YAGNI.** La galerie/grille publique d'analyseurs
> est retiree, fusionnee dans le menu de configuration LLM existant. **Conserves** : le
> modele `Analyseur`, le calcul de couts (utilise par PHASE-26h), l'historique des
> prompts (audit), et l'edition admin-only via permission `is_staff` dans le menu config.
> Voir `../discussions/YAGNI 2026-05-01.md`.

**Complexite** : L | **Mode** : Normal | **Prerequis** : PHASE-25, PHASE-26g

> **Decision d'architecture (2026-03-18)** : les utilisateurs ne peuvent PAS editer les prompts.
> Seuls les admins (`is_staff=True`) creent et maintiennent les analyseurs. Les utilisateurs
> choisissent un analyseur dans une bibliotheque prefabriquee. Raisons :
> - Securite : un prompt craft par un user malveillant pourrait tenter d'exfiltrer des donnees
> - Couts : des prompts demesures = surconsommation de tokens
> - Qualite : des prompts mal ecrits = extractions inutiles
> - UX : l'editeur de prompt par pieces est trop complexe pour un utilisateur final

> **Avancement partiel via PHASE-26g (2026-03-18)** : l'etape 4.2 (calcul des couts) est
> partiellement realisee. L'estimation utilise maintenant le vrai `QAPromptGenerator` de LangExtract
> pour mesurer l'overhead prompt par chunk, et integre les tokens de thinking (Gemini 2.5 Flash/Pro)
> avec un multiplicateur x5 configurable par modele. Voir [PHASE-26g](PHASE-26g.md).

---

## 1. Contexte

La gestion des analyseurs (prompts) est actuellement dans `hypostasis_extractor/views.py`
(`AnalyseurSyntaxiqueViewSet`, ~900 lignes) avec `permissions.AllowAny` — aucune restriction.

Le plan initial prevoyait de sortir cet editeur dans le front pour tous les users. Apres
reflexion, c'est un risque de securite trop important : le prompt est envoye tel quel au LLM,
et le retour est traite cote serveur (parsing Pydantic via LangExtract). Laisser les users
ecrire des prompts librement ouvre une surface d'attaque (prompt injection, exfiltration,
surconsommation).

**Nouveau modele** : bibliotheque d'analyseurs prefabriques, geres par les admins, choisis
par les utilisateurs.

## 2. Prerequis

- PHASE-25 (Users et partage) — necessaire pour l'ownership et les permissions.
- PHASE-26g (Hub d'analyse) — le selecteur d'analyseur et l'estimation des couts existent deja.

## 3. Objectifs precis

### Etape 4.0 — Permissions et verrouillage

Les analyseurs et modeles IA sont des ressources sensibles (couts API, qualite des prompts).

**Permissions** :

| Role | Droits |
|------|--------|
| **Admin** (`is_staff`) | CRUD complet : analyseurs, pieces de prompt, exemples few-shot, modeles IA |
| **User authentifie** | Lecture seule : parcourir la bibliotheque, voir les descriptions, consulter le prompt assemble |
| **User authentifie** | Selection : choisir un analyseur + un modele IA au moment de l'analyse |
| **User non authentifie** | Aucun acces |

Concretement :
- [ ] `AnalyseurSyntaxiqueViewSet` : verrouiller toutes les actions de mutation derriere `is_staff=True`
- [ ] `list()` et `retrieve()` : accessibles aux users authentifies (lecture seule)
- [ ] Le selecteur d'analyseur dans `confirmation_analyse.html` reste accessible a tout user authentifie
- [ ] Acces direct a `/api/analyseurs/` par un non-staff → message "Acces reserve aux administrateurs"
- [ ] Acces direct a `/api/analyseurs/` par un non-authentifie → redirect login

### Etape 4.1 — Bibliotheque d'analyseurs (vue utilisateur)

L'utilisateur voit une **bibliotheque** d'analyseurs disponibles, pas un editeur.

- [ ] Vue bibliotheque : grille de cartes des analyseurs actifs (`is_active=True`)
  - Chaque carte affiche : nom, description, type (analyser/reformuler/restituer), icone par type
  - Badge "N exemples" pour indiquer la qualite de l'entrainement
  - Charte visuelle : polices B612/B612 Mono, couleurs par type d'analyseur
- [ ] Bouton "Voir le prompt" sur chaque carte → modale lecture seule du prompt assemble
  - Affiche les pieces concatenees avec coloration syntaxique par role (DEFINITION, INSTRUCTION, FORMAT, CONTEXT)
  - Affiche les exemples few-shot en lecture seule
  - Pas de bouton d'edition — consultation uniquement
- [ ] Selection rapide : depuis le drawer d'analyse (26g), le selecteur d'analyseur pointe vers cette bibliotheque
- [ ] Filtre par type d'analyseur (analyser, reformuler, restituer) dans la bibliotheque

**Pas de clonage utilisateur dans un premier temps** — on garde le modele simple. Si le
besoin emerge (users avances voulant customiser), on ajoutera un mecanisme de "fork" dans
une phase ulterieure, avec revue admin obligatoire avant activation.

### Etape 4.1b — Interface d'administration des analyseurs (vue admin)

L'editeur complet existant (`AnalyseurSyntaxiqueViewSet`) reste en place mais :

- [ ] Deplacer l'acces de l'admin Django vers une page front dediee (`/analyseurs/admin/`)
- [ ] Garder l'editeur HTMX existant (pieces, exemples, attributs, test runs) tel quel
- [ ] Ajouter un lien visible uniquement pour les `is_staff` dans la navigation
- [ ] Preview du prompt assemble avant test ou publication

### Etape 4.2 — Calcul des couts fiabilise

> Partiellement fait via PHASE-26g (estimation avec QAPromptGenerator + thinking tokens).

**Reste a faire** :
- [ ] Stocker les tokens reels consommes (retour API) dans `ExtractionJob` (champs `tokens_input_reels`, `tokens_output_reels`)
- [ ] Comparer cout reel vs estime apres chaque analyse (affichage dans le drawer de resultats)
- [ ] Dashboard cumulatif des couts par modele/analyseur (vue admin, accessible aux `is_staff`)
- [ ] Utiliser le bon tokenizer par provider pour l'estimation (tiktoken pour OpenAI, estimation caracteres pour Gemini, tokenizer Anthropic pour Claude)

### Etape 4.3 — Historique des prompts

- [ ] Stocker un snapshot complet du prompt dans chaque `ExtractionJob` (deja fait partiellement via `prompt_description`)
- [ ] Table `AnalyseurVersion` : snapshot automatique a chaque modification d'un analyseur (pieces + exemples)
- [ ] Permettre de comparer deux versions de prompt (diff side-by-side, vue admin)
- [ ] Rollback a une version precedente d'un analyseur (action admin)
- [ ] L'utilisateur voit la version de l'analyseur utilisee pour chaque extraction (transparence)

## 4. Fichiers a modifier

- `hypostasis_extractor/views.py` — verrouillage permissions sur `AnalyseurSyntaxiqueViewSet`
- `hypostasis_extractor/models.py` — `AnalyseurVersion` (snapshot), champs tokens reels sur `ExtractionJob`
- `hypostasis_extractor/services.py` — capture tokens reels retournes par l'API
- `front/views.py` — `BibliothequeAnalyseursViewSet` (grille lecture seule, modale prompt)
- `front/templates/front/includes/` — `bibliotheque_analyseurs.html`, `modale_prompt_readonly.html`, `carte_analyseur.html`
- `core/models.py` — champs supplementaires sur `AIModel` pour estimation cout par provider
- `front/tasks.py` — integration couts reels apres analyse
- `front/serializers.py` — serializers pour bibliotheque (lecture seule)

## 5. Criteres de validation

- [ ] Un user non-staff ne peut PAS creer, modifier ou supprimer un analyseur (ni pieces, ni exemples)
- [ ] Un user non-staff PEUT parcourir la bibliotheque et consulter les prompts en lecture seule
- [ ] Un user non-staff PEUT choisir un analyseur et un modele IA au moment de l'analyse
- [ ] L'admin peut gerer les analyseurs depuis le front (pas besoin du Django admin)
- [ ] Le cout reel vs estime s'affiche apres chaque analyse
- [ ] L'historique des versions d'analyseur permet comparaison et rollback (admin)
- [ ] `uv run python manage.py check` passe

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **En tant qu'utilisateur normal : ouvrir la bibliotheque d'analyseurs**
   - **Attendu** : grille de cartes, lecture seule, pas de bouton creer/modifier/supprimer
2. **Cliquer "Voir le prompt" sur un analyseur**
   - **Attendu** : modale avec le prompt assemble, lecture seule, pas d'edition
3. **Lancer une analyse en choisissant un analyseur depuis le drawer**
   - **Attendu** : le selecteur fonctionne, l'analyse se lance
4. **En tant qu'admin : acceder a la gestion des analyseurs**
   - **Attendu** : editeur complet (pieces, exemples, test runs), liens dans la navigation
5. **En tant qu'admin : verifier le dashboard des couts**
   - **Attendu** : cout reel vs estime par analyse, cumulatif par modele/analyseur
6. **En tant qu'admin : verifier l'historique des versions d'un analyseur**
   - **Attendu** : liste des versions, diff side-by-side, bouton rollback
7. **En tant qu'utilisateur normal : tenter d'acceder a /api/analyseurs/ en direct**
   - **Attendu** : message "Acces reserve aux administrateurs", pas de 403 brut
