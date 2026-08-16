# PHASE-28-light — Synthese deliberative (bouton + prompt + V2 auto)

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-27b, PHASE-14, PHASE-26g

---

## 1. Contexte

Le tableau d'alignement des hypostases entre versions (PHASE-27b) montre que la
tracabilite fonctionne **structurellement** : quand une V2 est analysee, le matching
par type d'hypostase (donnee ↔ donnee, hypothese ↔ hypothese) revele immediatement
les correspondances, ajouts et suppressions. On n'a pas besoin de SourceLinks manuels
pour que la provenance soit visible.

Cette phase implemente un **"Lancer la synthese" MVP** : un bouton dans le dashboard
qui collecte les materiaux du debat (texte + hypostases + commentaires + statuts),
appelle un LLM avec un prompt de synthese deliberative, et cree une Page enfant (V2).

Le cycle existant prend ensuite le relais :
1. L'utilisateur lance l'analyse (hypostasiation) sur la V2
2. Le tableau d'alignement montre la correspondance V1 ↔ V2
3. L'utilisateur affine (edite la V2, relance l'analyse, commente)

Le wizard 5 etapes (PHASE-28 full), les SourceLinks manuels (27c), le fil de
reflexion (27d) et les verrous (27e) deviennent des **enrichissements futurs**,
pas des prerequis.

### Ce qui change dans le graphe de dependances

```
AVANT :  27b → 27c → 27d → 28 (wizard 5 etapes)
APRES :  27b → 28-light (synthese simple)
              → 27c, 27d, 27e (enrichissements independants)
              → 28-full (wizard 5 etapes, si besoin plus tard)
```

---

## 2. Objectifs precis

### 2.1 — Analyseur de type "synthetiser"

Ajouter un 4e type dans `TypeAnalyseur` :

| Type | Action | Niveau |
|------|--------|--------|
| `analyser` | Extraire les hypostases d'un texte | Page |
| `reformuler` | Reformuler une extraction | Entite |
| `restituer` | Restituer une extraction avec debat | Entite |
| **`synthetiser`** | **Synthetiser le debat complet d'une page** | **Page** |

Le nouvel analyseur a les flags :
- `inclure_texte_original = True`
- `inclure_extractions = True`

Son prompt est construit en 2 parties : pieces fixes (systeme) + contexte dynamique
(texte + extractions + commentaires, assemble par le code).

### 2.2 — Prompt de synthese deliberative

**Prompt systeme** (stocke dans 3 PromptPieces de l'analyseur) :

**Piece 1 — Contexte et mission** (role=context, order=0) :

```
Tu es un moteur de synthese deliberative. Ta mission est de produire une nouvelle
version d'un texte qui integre les resultats d'un cycle de debat structure.

Tu recois :
1. Le TEXTE ORIGINAL (transcription ou document source)
2. Les HYPOSTASES EXTRAITES — unites argumentatives typees avec leur statut de debat
3. Les COMMENTAIRES des contributeurs sur ces hypostases
4. Les RESUMES IA de chaque hypostase

Les hypostases sont les 30 manieres d'etre discutable definies par la geometrie
des debats. Chaque unite argumentative est classee selon son type (voir definitions
ci-dessous) et son statut de debat (consensuel, discutable, discute, controverse,
non pertinent, nouveau).
```

**Piece 2 — Definitions informelles des hypostases** (role=definition, order=1) :

```
# Definitions informelles des hypostases

Les hypostases ont des definitions venant des dictionnaires :

- paradigme : un paradigme est un modele ou un exemple.
- objet : Un objet est ce sur quoi porte le discours, la pensee, la connaissance.
- principe : les principes sont les causes a priori d'une connaissance
- domaine : un domaine est un champ discerne par des limites, bornes, confins, frontieres, demarcations.
- loi : les lois expriment des correlations.
- phenomene : les phenomenes se manifestent a la connaissance via les sens.
- variable : une variable est ce qui prend differentes valeurs et ce dont depend l'etat d'un systeme.
- variance : Une variance caracterise une dispersion d'une distribution ou d'un echantillon.
- indice : Un indice est un indicateur numerique ou litteral qui sert a distinguer ou classer.
- donnee : Une donnee est ce qui est admis, donne, qui sert a decouvrir ou a raisonner.
- methode : Une methode est une procedure qui indique ce que l'on doit faire ou comment le faire.
- definition : Une definition est la determination, la caracterisation du contenu d'un concept.
- hypothese : Une hypothese concerne l'explication ou la possibilite d'un evenement.
- probleme : Un probleme est une difficulte a resoudre
- theorie : Une theorie est une construction intellectuelle explicative, hypothetique et synthetique.
- approximation : Une approximation est un calcul approche d'une grandeur reelle.
- classification : Les classifications sont le fait de distribuer en classes, en categories.
- aporie : Les apories sont des difficultes d'ordre rationnel apparemment sans issues.
- paradoxe : Les paradoxes sont des propositions a la fois vraies et fausses.
- formalisme : Un formalisme est la consideration de la forme d'un raisonnement.
- evenement : Les evenements sont ce qui arrive.
- variation : les variations sont des changements d'un etat dans un autre.
- dimension : Les dimensions sont des grandeurs mesurables qui determinent des positions.
- mode : Les modes sont les manieres d'etre d'un systeme.
- croyance : Les croyances sont des certitudes ou des convictions qui font croire une chose vraie, vraisemblable ou possible.
- invariant : Les invariants sont des grandeurs, relations ou proprietes conservees lors d'une transformation
- valeur : Une valeur est une mesure d'une grandeur variable.
- structure : Les structures sont l'organisation des parties d'un systeme.
- axiome : Les axiomes sont des propositions admises au depart d'une theorie.
- conjecture : Les conjectures sont des opinions ou propositions non verifiees.
```

**Piece 3 — Regles de ponderation et redaction** (role=instruction, order=2) :

```
REGLES DE PONDERATION PAR STATUT :

- CONSENSUEL (poids fort) : Integrer comme acquis. Ces points font accord —
  les affirmer clairement dans la synthese.
- DISCUTABLE (poids moyen) : Integrer avec nuance. Mentionner que le point
  merite discussion ou examen.
- DISCUTE (poids moyen-faible) : Presenter les termes du debat. Reprendre
  les arguments des commentaires pour et contre.
- CONTROVERSE (poids faible) : Exposer le desaccord sans trancher. Citer les
  positions en presence. Ne pas prendre parti.
- NON_PERTINENT (poids zero) : Ignorer completement. Ces elements ont ete
  ecartes par les contributeurs.
- NOUVEAU (poids faible) : Integrer seulement si pertinent pour la coherence.
  Ces elements n'ont pas encore ete evalues par les contributeurs.

REGLES DE REDACTION :

- Ecris a la troisieme personne, en voix neutre et synthetique
- Structure le texte en paragraphes thematiques (pas de listes a puces)
- Chaque affirmation doit pouvoir etre rattachee a une hypostase source
- Preserve la richesse argumentative : ne simplifie pas a l'exces
- Longueur cible : 40-60% du texte original (synthese, pas resume)
- Si des commentaires apportent des precisions factuelles, integre-les
  dans le fil du texte
- Les points controverses doivent etre presentes comme tels :
  "Sur ce point, les avis divergent..." / "Cette position est contestee..."
- Ne fabrique aucune information absente des materiaux fournis
- N'ajoute pas d'opinion personnelle ni de recommandation
```

**Prompt utilisateur** (construit dynamiquement dans la tache Celery) :

```
=== TEXTE ORIGINAL ===
{text_readability de la page}

=== HYPOSTASES ET DEBAT ===

[Pour chaque extraction, triees par statut : consensuel → discutable →
discute → controverse → nouveau. Les non_pertinent sont exclus.]

**[CONSENSUEL] donnee — Des preuves empiriques de gouvernance collective**
Citation : "Linux, Wikipedia et les cooperatives comme preuves empiriques
de gouvernance collective."
Resume IA : "..."
Commentaires :
  - alice : "Point solide, bien documente"
  - bob : "Ajouter les Creative Commons comme exemple supplementaire"

**[CONTROVERSE] conjecture — Bifurcation elite augmentee / humanite**
Citation : "Prediction d'une bifurcation entre elite augmentee et humanite
laissee pour compte."
Resume IA : "..."
Commentaires :
  - alice : "Vision catastrophiste sans base empirique"
  - charlie : "Tendance reelle deja observable dans l'education"

[...]

=== CONSIGNE ===
Produis la synthese deliberative de ce debat. Integre les points consensuels
comme acquis, presente les controverses sans trancher, et ignore les elements
marques non pertinents. Le texte doit etre autonome et lisible sans connaitre
les materiaux sources.
```

### 2.3 — Bouton "Lancer la synthese" dans le dashboard

Modifier le template `dashboard_consensus.html` :

Le bouton est **toujours cliquable**, quel que soit le seuil de consensus.
Il ouvre **toujours une modale de confirmation** avant de lancer la synthese.

**Seuil atteint (>= 80%)** :
- Bouton vert plein "Lancer la synthese"
- Au clic → modale de confirmation :
  - "Vous allez generer une nouvelle version synthetisee a partir du debat."
  - "Consensus : X% (seuil atteint)"
  - "La version synthetisee pourra etre analysee et commentee a son tour."
  - Boutons : [Annuler] [Lancer la synthese]
- Si confirme → POST vers `LectureViewSet.synthetiser()`

**Seuil NON atteint (< 80%)** :
- Bouton vert attenue (opacite 0.6) "Lancer la synthese"
- Le message de % actuel reste affiche sous le bouton
- Au clic → modale de confirmation **avec avertissement renforce** :
  - "⚠️ Le seuil de consensus n'est pas atteint (X% / 80%)"
  - "Le debat n'est pas encore mur. Des points sont encore discutes
    ou controverses."
  - "**La nouvelle version repartira d'un cycle vierge : les statuts
    de debat actuels ne seront pas reportes. Vous pourrez toujours
    revenir a cette version pour continuer le debat.**"
  - Boutons : [Annuler] [Lancer quand meme]
- Si confirme → POST vers `LectureViewSet.synthetiser()` normalement

**Apres lancement** :
- Le bouton se transforme en spinner "Synthese en cours..."
- Polling HTMX identique au pattern existant (analyse_status)
- Quand termine → bouton "Voir la synthese (V2)" avec redirection

### 2.4 — Action `synthetiser()` sur LectureViewSet

Nouvelle action `@action(detail=True, methods=["post"])` sur `LectureViewSet`
(basename="lire", URL generee : `/lire/{pk}/synthetiser/`).

Note : le dashboard est sur `ExtractionViewSet` (basename="extraction"),
mais le bouton du dashboard peut POST vers une URL d'un autre ViewSet
via `hx-post="/lire/{page_id}/synthetiser/"`.

1. **Guards** : authentification, permission ecriture, credits suffisants
2. **Anti-doublon** : verifier qu'aucune synthese n'est deja en cours
3. **Remonter a la page racine** : `page_racine = page.page_racine`
   (les versions sont toutes filles de la racine, pas en chaine)
4. **Collecter les materiaux** :
   - `page.text_readability` (texte original)
   - Toutes les `ExtractedEntity` du dernier job complete, avec :
     - `extraction_class`, `extraction_text`, `statut_debat`
     - `attributes` (JSONField contenant resume, mots_cles, etc.)
     - `commentaires` associes (via related_name, champs : `user.username` + `commentaire`)
5. **Trouver l'analyseur** de type `synthetiser` actif
6. **Construire le prompt** :
   - Pieces systeme de l'analyseur (PromptPieces ordonnees par `order`)
   - Bloc dynamique avec texte + extractions + commentaires (cf. 2.2)
7. **Creer un ExtractionJob** :
   - `page=page, status="pending", name="Synthese deliberative"`
   - `prompt_description=prompt_complet`
   - `raw_result={"analyseur_id": analyseur.pk, "est_synthese": True}`
8. **Lancer la tache** : `synthetiser_page_task.delay(job_id)`
9. **Retourner** le partial HTMX de polling (reutiliser le pattern existant)

### 2.5 — Tache Celery `synthetiser_page_task`

Dans `front/tasks.py` :

1. Charger le job + page + analyseur
2. Assembler le prompt complet (systeme + utilisateur)
3. Appeler `appeler_llm(modele_ia, prompt_complet)` depuis `core/llm_providers.py`
   (pas LangExtract — on veut du texte libre, pas des extractions structurees)
4. Recuperer le texte de synthese
5. **Remonter a la page racine** : `page_racine = page_source.page_racine`
6. **Creer la Page enfant** (pattern identique a `creer_restitution()`) :
   ```python
   texte_brut = strip_tags(texte_synthese_html)
   hash_contenu = hashlib.sha256(texte_brut.encode("utf-8")).hexdigest()
   prochain_numero = page_racine.restitutions.count() + 2

   page_synthese = Page.objects.create(
       parent_page=page_racine,          # toujours la racine, pas page_source
       version_number=prochain_numero,
       version_label="Synthese deliberative",
       dossier=page_racine.dossier,
       source_type=page_racine.source_type,  # copier le type de source
       url=None,
       title=page_racine.title,
       html_original=texte_synthese_html,
       html_readability=texte_synthese_html,
       text_readability=texte_brut,
       content_hash=hash_contenu,
       owner=user,
   )
   ```
7. Marquer le job comme `completed`
8. Envoyer notification WebSocket : "Synthese terminee — Voir la V2"
9. **Debiter les credits** si Stripe actif

### 2.6 — Notification et redirection

Quand la synthese est terminee :
- Le polling detecte `status=completed`
- Le partial retourne un bouton "Voir la synthese (V2)" avec `hx-redirect`
  vers `/lire/{page_synthese.pk}/`
- L'utilisateur peut alors lancer l'analyse sur la V2
- Le tableau d'alignement (PHASE-27b) est immediatement fonctionnel

---

## 3. Fichiers a modifier

| Fichier | Changement |
|---------|-----------|
| `hypostasis_extractor/models.py` | Ajouter `"synthetiser"` dans `TypeAnalyseur` |
| `front/views.py` | +`LectureViewSet.synthetiser()` action |
| `front/tasks.py` | +`synthetiser_page_task()` tache Celery |
| `front/serializers.py` | +`SynthetiserSerializer` (validation page_id) |
| `front/templates/front/includes/dashboard_consensus.html` | Bouton actif + modale confirmation mono-user |
| `front/templates/front/includes/synthese_en_cours.html` | Nouveau — partial polling synthese |
| `front/fixtures/demo_ia.json` | +Analyseur "Synthese deliberative" avec ses PromptPieces |
| `front/tests/test_phase28_light.py` | Tests unitaires |

---

## 4. Criteres de validation

- [x] `uv run python manage.py check` → 0 erreur
- [x] Le type `synthetiser` existe dans les choices de `TypeAnalyseur`
- [x] L'analyseur "Synthese deliberative" est cree via fixtures
- [x] Le bouton "Lancer la synthese" est toujours cliquable (jamais disabled)
- [x] Le bouton est vert plein si seuil atteint, attenue (opacite 0.6) sinon
- [x] Une modale de confirmation s'ouvre au clic (avec avertissement si seuil non atteint)
- [x] Au clic, le prompt est construit avec texte + extractions + commentaires + statuts
- [x] Les extractions `non_pertinent` sont exclues du prompt
- [x] Les extractions sont triees par statut (consensuel d'abord)
- [x] Les commentaires de chaque extraction sont inclus dans le prompt
- [x] La tache Celery cree une Page enfant avec le texte de synthese
- [x] La Page enfant a `parent_page`, `version_number`, `version_label` corrects
- [x] L'utilisateur est redirige vers la V2 apres completion (via bouton "Voir la synthese")
- [ ] Le tableau d'alignement V1 ↔ V2 fonctionne apres analyse de la V2 (verification navigateur)
- [x] Les credits sont debites si Stripe actif

---

## 5. Verification navigateur

1. Ouvrir une page avec des extractions et commentaires (ex: debat IA demo)
2. Ouvrir le dashboard → verifier l'etat du seuil
3. Cliquer "Lancer la synthese" (ou "Lancer quand meme")
4. **Attendu** : spinner de progression dans le dashboard
5. Apres quelques secondes : bouton "Voir la synthese (V2)"
6. Cliquer → la V2 s'ouvre avec le texte synthetise
7. Lancer l'analyse (hypostasiation) sur la V2
8. Ouvrir "Comparer" depuis la V1 → le tableau d'alignement montre les correspondances
9. Verifier que les points consensuels sont affirmes, les controverses presentees

---

## 6. Tests

**Module :** `front.tests.test_phase28_light` | **Derniere execution :** 2026-03-20 | **Resultat : 16/16 OK**

| Classe | Test | Statut |
|--------|------|--------|
| `PromptSyntheseTest` | `test_prompt_contient_texte_original` | OK |
| `PromptSyntheseTest` | `test_prompt_contient_statuts` | OK |
| `PromptSyntheseTest` | `test_prompt_exclut_non_pertinent` | OK |
| `PromptSyntheseTest` | `test_prompt_exclut_masquees` | OK |
| `PromptSyntheseTest` | `test_prompt_tri_par_statut` | OK |
| `PromptSyntheseTest` | `test_prompt_contient_commentaires` | OK |
| `SynthetiserActionTest` | `test_synthetiser_requiert_authentification` | OK |
| `SynthetiserActionTest` | `test_synthetiser_cree_job` | OK |
| `SynthetiserActionTest` | `test_synthetiser_anti_doublon` | OK |
| `SynthetiserTaskTest` | `test_task_cree_page_enfant` | OK |
| `SynthetiserTaskTest` | `test_task_parent_page_est_racine` | OK |
| `SynthetiserTaskTest` | `test_task_version_number_incrementee` | OK |
| `SynthetiserTaskTest` | `test_task_erreur_marque_job_error` | OK |
| `DashboardBoutonTest` | `test_bouton_est_cliquable` | OK |
| `DashboardBoutonTest` | `test_bouton_variante_avertissement` | OK |
| `DashboardBoutonTest` | `test_zone_btn_synthese_presente` | OK |

**Notes d'implementation :**
- Le `SynthetiserSerializer` est vide (le pk vient de l'URL `detail=True`), appele par convention
- Bug corrige : `.exclude(raw_result__est_synthese=True)` remplace par `.exclude(raw_result__contains={"est_synthese": True})` car le lookup JSONField standard exclut les lignes ou la cle est absente
- Bug corrige : la modale se ferme apres le POST via `hx-on::after-request`
- `commentaire.user.username` (pas `.prenom`, migre en PHASE-25)
- `page_source.owner` dans la tache Celery (pas de `request.user` en tache async)

---

## 7. Prompt detaille — justification des choix

### Pourquoi pas de `[src:extraction-42]` dans cette version ?

Le wizard complet (PHASE-28) prevoyait des references inline que le systeme parserait
pour creer des SourceLinks. Ici on s'en passe car :
- Le tableau d'alignement par hypostases fournit la tracabilite structurellement
- Les references inline ajoutent de la complexite au prompt et au parsing
- Le LLM produit parfois des references incorrectes (hallucination de numeros)
- On pourra les ajouter dans une iteration future si le besoin se confirme

### Pourquoi inclure les commentaires ?

Les commentaires sont la matiere premiere du debat. Sans eux, la synthese ne serait
qu'un resume pondera — pas une synthese deliberative. Les commentaires apportent :
- Des precisions factuelles (exemples, sources, nuances)
- Des objections argumentees (qui justifient les statuts discute/controverse)
- Le contexte humain du debat (qui aide le LLM a calibrer le ton)

### Pourquoi trier par statut ?

L'ordre consensuel → discutable → discute → controverse donne au LLM un signal
de priorite implicite : les premiers elements du prompt ont plus de poids dans
la generation. Cela renforce la ponderation explicite des regles.

---

## 8. Notes pour les phases suivantes

- **27c (SourceLinks)** : enrichissement optionnel. Si implemente, les SourceLinks
  auto-crees lors de la synthese pourront etre affiches dans le diff.
- **27d (fil de reflexion)** : pourra utiliser les PageEdit + le lien parent/enfant
  pour construire la timeline, meme sans SourceLinks explicites.
- **28-full (wizard)** : si le besoin de controle fin se confirme apres usage du
  28-light, le wizard 5 etapes restera pertinent comme evolution.
- **Iterations sur le prompt** : le prompt est un brouillon. L'interet du systeme
  d'analyseurs (PHASE-26b) est qu'on peut le modifier depuis l'interface sans
  toucher au code. Tester, ajuster, versionner.
