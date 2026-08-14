# File d'ingestion Docling — convertisseur partagé, worker dédié en dev, rang affiché

> Écrit le 14 août 2026. Réfère : CHANGELOG du 14 août (section « LA FILE
> D'INGESTION »), `supervisord-dev.conf`, décisions du mainteneur prises
> en début de session.

## Ce qui a été livré

### A — le convertisseur Docling est partagé par process

`hypostasis_extractor/services/ingestion_docling.py` construisait un
`DocumentConverter()` neuf à chaque appel, aux **deux** portes d'entrée
(fichier `:112` et capture web `:157`). Il est mémoïsé par
`_convertisseur_docling()`, `@lru_cache(maxsize=1)`.

Ce qu'on partage n'est pas le convertisseur — son `__init__` ne charge
aucun modèle — mais son **cache de pipelines** (`initialized_pipelines`,
un attribut d'instance rempli au premier `convert()`).

Mesure, six conversions du même PDF dans un process (avant → après) :
moyenne des conversions 2 à 6 **9,87 s → 6,70 s**, RSS final
**2424 → 2132 Mo**, pic **2928 → 2288 Mo**, dérive après warm-up
**+407 → +239 Mo**. La RAM monte moins vite, pas plus.

### B — le dev sert la file Docling comme la prod

Nouveau `supervisord-dev.conf` : `runserver` + `celery_worker` (file par
défaut, concurrence 2) + `celery_worker_docling` (file dédiée,
**concurrence 1**). Plus aucun `uv run`, ni en dev ni en prod.

### C — la position dans la file est affichée

« en attente — 3ᵉ dans la file » dans le menu des tâches. Rang
cross-utilisateurs, position seule sans le total, fantômes exclus, et
fan-out WebSocket vers ceux qui attendent quand une ingestion se termine.

---

## À FAIRE EN PREMIER — basculer sur supervisord

Ton `runserver` et ton worker actuels tournent encore à la main. **Rien
n'a été démarré ni arrêté à ta place.** Pour basculer :

```bash
# 1. Arrêter ce qui tourne à la main (tes panneaux byobu)
#    Ctrl-C sur le runserver et sur le worker celery

# 2. Tout démarrer d'un coup
make dev

# 3. Vérifier
make status
```

Tu dois voir **trois** programmes en RUNNING : `runserver`,
`celery_worker`, `celery_worker_docling`.

Commandes du quotidien :

```bash
make restart S=runserver
make logs S=celery_worker_docling
make stop
make                      # liste toutes les cibles
```

Les logs vont dans des **fichiers** (`logs/`) et non sur stdout :
supervisord tourne en démon en dev.

### Le Makefile — ce qu'il reste à éprouver

Les cibles inoffensives ont été testées ici : `aide` (les 20 cibles
listées, vérifiées par script), `check`, `test`, `test-suite` (13 tests
verts par ce chemin), `status`/`restart`/`logs`/`stop` quand les services
sont arrêtés (message clair au lieu de l'erreur brute de supervisorctl),
et `prod-update` qui **refuse bien** de tourner ici (`.env` porte
`DEBUG=true`).

**`make test-rapide` : 1722 tests, OK, 7 min 28.** C'est la preuve que
l'exclusion des e2e fonctionne (1722 + les 222 e2e = la suite entière) et
que rien du chantier d'aujourd'hui n'a cassé le reste du dépôt. Note la
durée : « le geste quotidien » coûte tout de même sept minutes et demie —
pour une boucle de développement serrée, `make test-suite S=...` est le
bon réflexe.

Restent à éprouver par toi, parce qu'ils touchent ton environnement ou
n'existent pas ici :

1. **`make install`** — non lancé : il appelle `charger_fixtures_demo`,
   or une autre session travaille en ce moment sur les fixtures. À faire
   quand ce chantier sera terminé.
2. **`make dev`** — non lancé : il aurait tué ton `runserver` (port 8000).
3. **`make fixtures`** — même raison que `install`.
4. **`make test-e2e`** — plusieurs minutes de navigateur, non lancé.
5. **`make test-llm`** — payant, évidemment non lancé. Vérifier que la
   confirmation apparaît bien (répondre autre chose que `oui` annule).
6. **`make prod-update` sur la vraie machine de production.** Attention :
   `docker-compose-prod.yml` nomme ses conteneurs `hypostasia_dev_web`,
   donc là-bas il faut `make prod-update CONTENEUR=hypostasia_dev_web`.
   Cette cible fait un `git pull` — c'est toi qui la lances, jamais moi.

---

## À tester à la main

1. **Le worker Docling est bien seul sur sa file.**
   `docker exec hypostasia_web supervisorctl -c /app/supervisord-dev.conf status`
   puis `docker exec hypostasia_web ps -eo pid,args | grep celery` : tu
   dois voir **deux** workers, dont un seul avec `-Q ingestion_docling`
   et `--concurrency=1`.

2. **Le gain de temps du convertisseur partagé.** Importer deux PDF à la
   suite (le même fait l'affaire). Dans `logs/celery_worker_docling.log`, la
   première conversion prend ~80 s (chargement des modèles), la
   **seconde ~7 s**. Avant ce chantier la seconde prenait ~10 s. Si la
   seconde reprend 80 s, le partage ne fonctionne pas.

3. **Le rang s'affiche.** Importer 3 ou 4 PDF coup sur coup, puis ouvrir
   le menu des tâches (bouton de la toolbar). Les notes en attente
   doivent afficher « en attente — 2ᵉ dans la file », « 3ᵉ dans la
   file »… et celle qui est sur le worker « En cours… ».

4. **Le rang descend tout seul.** Laisser le menu OUVERT pendant qu'une
   conversion se termine : la position doit descendre sans que tu
   touches à rien (c'est le fan-out WebSocket). Si elle ne bouge que
   quand tu rafraîchis, vérifier la console du navigateur — le message
   attendu est `{"type":"file_ingestion_modifiee"}`.

5. **Le rang traverse les utilisateurs.** Avec deux comptes : importer
   des PDF depuis le compte A, puis un depuis le compte B. Le compte B
   doit voir une position qui tient compte des notes de A — **sans
   jamais voir leurs titres**. C'est le comportement voulu, décidé
   explicitement ; le vérifier de visu vaut mieux que de me croire.

6. **Un worker tué ne bloque pas le compteur.** Tuer le worker Docling
   pendant qu'une note est en attente
   (`supervisorctl … stop celery_worker_docling`), attendre 15 minutes
   (`DELAI_INGESTION_FANTOME_MIN`), vérifier que la note fantôme cesse
   de compter dans le rang des autres.

7. **Arrêt gracieux (le vrai bénéfice du retrait de `uv run`).** Lancer
   une conversion, puis `supervisorctl … stop celery_worker_docling`
   pendant qu'elle tourne : le worker doit **attendre la fin de la
   conversion** (jusqu'à 120 s) au lieu d'être coupé net.

### En production, au prochain déploiement

Le retrait de `uv run` touche aussi `supervisord.conf` et `start.sh`.
C'est le seul changement que **je n'ai pas pu vérifier à l'exécution** —
il n'y a pas de prod ici. Au premier déploiement : vérifier que les
quatre programmes démarrent (`gunicorn`, `daphne`, `celery_worker`,
`celery_worker_docling`). Le `PATH` de l'image contient `/app/.venv/bin`
(Dockerfile:59) et supervisord transmet son environnement à ses enfants,
donc le risque est faible — mais il est non nul et il est à vérifier.

## Preuves déjà faites

- **172 tests verts**, 10 suites, une à la fois, jamais `--parallel` :
  `test_ingestion_docling` (27), `test_files_celery_ingestion` (13,
  neuf), `test_notifications_ingestion` (16), `test_tasks_element` (22),
  `test_masquage_et_reingestion` (26), `test_position_en_file_ingestion`
  (11, neuf), `test_taches_ingestion` (21), `test_capture_web_docling`
  (7), `test_ingestion_ui` (21), `test_import_docling` (8).
- TDD strict : chaque test a été écrit et **vu rouge** avant le code
  (`ImportError: cannot import name '_convertisseur_docling'`,
  `'_rangs_dans_la_file_d_ingestion'`, `does not have the attribute
  'notifier_la_file_d_ingestion'`, `supervisord-dev.conf est absent`).
- Mesures RAM/temps avant et après, dans le conteneur, mêmes conditions.
- `supervisord-dev.conf` validé par le parseur de supervisord
  (`ServerOptions.process_config_file`) — mais **pas démarré**, pour ne
  pas couper l'environnement en cours.
- Deux relectures adverses par agent (phase A, puis phases B et C).

## Correctifs issus de la relecture adverse (phase A)

- **Un test ne prouvait rien.** La première version de
  `test_importer_le_module_ne_construit_aucun_convertisseur` lisait
  `cache_info().currsize` : un `DocumentConverter()` construit par un
  autre chemin laisse ce compteur à zéro. Vérifié en injectant la
  violation — le test restait vert. Il observe désormais
  `'docling' in sys.modules` **après avoir reproduit le bootstrap
  complet de Celery** (`import_default_modules()`, qui tire
  `tasks_element.py`), et il a été vérifié discriminant.
- **L'explication du coût était fausse** dans le docstring : ce n'est
  pas la construction du convertisseur qui coûte 2 à 3,6 s, c'est le
  pipeline. Un lecteur qui croyait le commentaire aurait pu conclure que
  le convertisseur est bon marché à reconstruire, donc annuler ce
  chantier.
- **La justification du danger prefork était trop faible** : le vrai
  risque n'est pas la copie-sur-écriture de torch mais les threads
  onnxruntime et OpenMP du pipeline PDF.
- **`lru_cache` ne verrouille pas l'exécution** : deux appelants
  concurrents construiraient chacun leur convertisseur. Sans
  conséquence aujourd'hui (toutes les conversions passent par
  `.delay()`, vérifié sur les trois points d'entrée), c'est désormais
  écrit dans le docstring.

## Correctifs issus de la relecture adverse (phases B et C)

Tous vérifiés à la main avant correction.

- **Le rang était faux pendant chaque conversion.** Le fan-out ne
  partait qu'à la *fin* d'une ingestion ; or le passage à `en_cours`
  fait aussi sortir une page de la file. Le chiffre restait donc faux
  pendant 83 à 164 s, et la page en cours annonçait « 1ᵉʳ dans la file »
  pendant sa propre conversion. Trois autres chemins (gardes « page déjà
  ingérée ») ne prévenaient personne non plus. Le fan-out vit désormais
  dans `_noter_l_etat_d_ingestion` — le point de passage unique — au
  lieu d'être éparpillé chez six appelants dont il manquait à tous.
- **N+1 dans le fan-out** : une requête par page en file. Deux requêtes
  fixes désormais, quelle que soit la longueur de la file.
- **Le test de topologie laissait passer la dérive qu'il devait
  empêcher** : `-Qcelery,ingestion_docling` (forme collée, valide pour
  Celery) était lu « file par défaut », donc ignoré par le test des
  mélanges. Le lecteur couvre maintenant les quatre écritures de chaque
  option et refuse `--autoscale`.
- **`?v=37` figé** alors que `hypostasia.js` change : nginx sert
  `/static/` en `immutable` 30 jours, ce qui interdit la revalidation.
  Passé à `v=38`.
- Logs de dev : deux journaux tournants sur un même fichier (lignes
  perdues à la rotation) → `redirect_stderr`. `killasgroup` ajouté aux
  workers de prod. Socket de dev distincte. En-tête du `docker-compose`
  remis à jour.
- Deux tests non discriminants réparés (voir la section phase A pour le
  premier ; le second passait au vert même sans tri sur le `pk`).

## Ce qui reste ouvert — décisions à prendre

**Le plus important : une note qui attend plus de 15 minutes disparaît
de sa propre file.** `ingestion_maj_le` est posé une seule fois, à la
mise en file, et n'est jamais rafraîchi pendant l'attente. La règle du
fantôme (`DELAI_INGESTION_FANTOME_MIN = 15`) ne distingue donc pas « le
worker est mort » de « j'attends sagement depuis 16 minutes ». À 83-164 s
par document, **le seuil tombe dès 7 à 11 documents en file** — un import
par lot suffit. Alors : le menu affiche « En cours… » (faux, elle
attend), le badge s'éteint, et elle décale le rang de tous ceux qui sont
derrière alors que sa tâche est toujours dans Redis.

Le défaut est **antérieur** à ce chantier — la règle du fantôme existait
déjà et le badge en souffrait — mais l'affichage du rang le rend visible
et nuisible. Je ne l'ai pas corrigé : il faut choisir un second délai
pour l'attente (2 h ? proportionnel à la longueur de la file ?) et le
propager à `_calculer_etat_bouton` et à `relancer_ingestion`. C'est ton
arbitrage, pas le mien. **À tester : importer 12 PDF d'affilée et
regarder le menu au bout de 20 minutes.**

**Accessoirement** : `relancer_ingestion` réécrit `ingestion_maj_le`,
donc une page relancée passe derrière dans l'ordre affiché alors que
dans Redis sa tâche reste devant. Le rang d'un tiers baisse sans raison
réelle.

### Décision sur la mémoire du worker

**La croissance mémoire du worker Docling n'est bornée par rien.** Ni
`worker_max_tasks_per_child`, ni `worker_max_memory_per_child`. Chaque
conversion laisse 40 à 70 Mo qui ne sont jamais rendus à l'OS — **avant
comme après** ce chantier, ce n'est pas une régression. Mais un enfant
qui enchaîne une soixantaine de PDF atteindrait ~5 Go sur un hôte 8 Go
partagé avec la production.

Le partage du convertisseur rend ce plancher **permanent** au lieu de
transitoire, sans l'aggraver (mesuré : la dérive est plus faible
qu'avant).

Le correctif coûterait une option sur `celery_worker_docling` dans les
deux fichiers supervisord, par exemple
`--max-memory-per-child=3000000` (3 Go : l'enfant est recyclé après la
conversion qui dépasse ce seuil). Je ne l'ai pas appliqué — c'est
au-delà du périmètre demandé, et le seuil est un arbitrage qui
t'appartient.
