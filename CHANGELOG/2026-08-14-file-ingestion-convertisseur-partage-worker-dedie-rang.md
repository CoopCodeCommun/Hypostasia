# LA FILE D'INGESTION : UN CONVERTISSEUR PARTAGE, UN WORKER DEDIE EN DEV, ET UN RANG AFFICHE

**Date :** 2026-08-14
**Migration :** Non

**Quoi / What :** trois corrections sur le chemin d'ingestion Docling —
le convertisseur n'est plus reconstruit a chaque document, le dev sert
enfin la file Docling comme la prod, et celui qui attend voit sa
position dans la file. / Three fixes on the Docling ingestion path: a
shared converter, dev queue topology aligned on production, and a
visible queue position.

### A. LE CONVERTISSEUR ETAIT JETE APRES CHAQUE DOCUMENT

`ingestion_docling.py` construisait un `DocumentConverter()` neuf a
chaque appel, aux DEUX portes d'entree — la conversion de fichier et
celle de la capture web. Il est desormais memoise par process
(`_convertisseur_docling`, `@lru_cache(maxsize=1)`).

Ce qui coute cher n'est pas le convertisseur lui-meme : son `__init__`
ne charge aucun modele. C'est le PIPELINE, bati au premier `convert()`
et range dans un dictionnaire d'INSTANCE (`initialized_pipelines`).
Jeter le convertisseur jetait ce cache avec lui.

Mesure, six conversions du meme PDF dans un process :

| | avant | apres |
|---|---|---|
| moyenne des conversions 2 a 6 | 9,87 s | **6,70 s** (-32 %) |
| RSS final | 2424 Mo | **2132 Mo** |
| pic de RSS | 2928 Mo | **2288 Mo** |
| derive apres le warm-up | +407 Mo | **+239 Mo** |

La memoire ne monte donc pas plus vite — elle monte moins.

**Sur pour le pool prefork**, et c'est la seule chose qui rendait ce
partage risque : la construction est PARESSEUSE. Le pipeline PDF ouvre
onnxruntime (RapidOCR) et des pools OpenMP ; forker un process qui
porte des threads de ces bibliotheques bloque classiquement. Un test
reproduit le bootstrap complet de Celery — autodiscover compris — et
verifie que `docling` n'est jamais importe avant le fork.

### B. LE DEV NE SERVAIT PAS LA FILE COMME LA PROD

`supervisord.conf` declare un worker dedie `-Q ingestion_docling
--concurrency=1` depuis toujours. Le lancement de dev, lui, tirait
`-Q celery,ingestion_docling --concurrency=2` depuis un worker unique :
deux conversions Docling simultanees etaient possibles (~2 Go et ~83 s
de warm-up chacune, sur un hote 8 Go partage), et une ingestion pouvait
occuper les deux slots au detriment des analyses.

Nouveau `supervisord-dev.conf` : `runserver` (ASGI, port 8000) +
`celery_worker` (file par defaut, concurrence 2) + `celery_worker_docling`
(file dediee, **concurrence 1**). Le dev se lance desormais d'une seule
commande.

**Aucune commande ne passe plus par `uv run`**, ni en dev ni en prod
(`supervisord.conf`, `start.sh`). `uv run` laissait un process wrapper
VIVANT entre supervisord et le programme reel : supervisord surveillait
le wrapper, et son SIGTERM d'arret allait a lui plutot qu'au worker —
or c'est le worker qui doit le recevoir pour finir sa conversion en
cours (`stopwaitsecs`). Le PATH de l'image contient deja
`/app/.venv/bin` : la mention « `uv run` est obligatoire » qu'on lisait
dans le README, les GUIDELINES et la passation etait fausse.

Un test verrouille la topologie, pour les deux environnements a la
fois : `test_files_celery_ingestion.py`. Il refuse qu'un worker melange
la file dediee avec une autre, qu'elle soit servie a plus de 1, qu'elle
ne soit servie par personne, ou qu'un programme repasse par un wrapper.

### C. CELUI QUI ATTEND VOIT MAINTENANT OU IL EN EST

Une ingestion dure 83 s a froid et la file est servie une conversion a
la fois : la cinquieme note importee attendait plusieurs minutes
derriere un « En cours… » immobile, qui se lit comme une panne. Le menu
des taches affiche desormais **« en attente — 3ᵉ dans la file »**.

**Le rang traverse les utilisateurs** — c'est la seule requete de
`front/views_taches.py` qui ne filtre pas par proprietaire, et c'est
une decision explicite du mainteneur. La file d'ingestion est globale :
un worker, aucune identite dans les taches. Un rang calcule sur ses
seules pages afficherait « 1ᵉʳ » pendant que quatre notes d'autrui
passent devant. Ce qui sort est un ENTIER DE CHARGE : jamais un titre,
un proprietaire ni un contenu, et le mainteneur a retenu la position
SEULE, sans le total. Un test verifie qu'aucun titre de tiers ne fuit.

Deux pieges, tenus par des tests :

- **les fantomes sont exclus du rang** (meme regle que le compteur du
  badge : `DELAI_INGESTION_FANTOME_MIN`, ou date absente). Sans ca, une
  note abandonnee par un worker mort decalerait le compteur de tout le
  monde, definitivement ;
- **la fin d'une ingestion previent ceux qui attendent derriere**
  (`_prevenir_la_file_d_attente`). Leur position vient de changer sans
  que rien ne se soit passe chez eux : sans ce fan-out, le chiffre
  affiche se fige — et un chiffre fige est pire que pas de chiffre. Un
  message par UTILISATEUR, pas par page.

Le message WebSocket est un type NOUVEAU, `file_ingestion_modifiee`,
sans charge utile. Deliberement pas un `tache_terminee` : aucune tache
de ce destinataire ne s'est terminee, et reutiliser l'autre message
deviendrait un mensonge le jour ou le client affichera « Tache
terminee » en clair.

Le rang n'est exact que si la file est servie a concurrence 1 : le
point C depend du point B.

### CE QUE LES RELECTURES ADVERSES ONT CORRIGE

Deux relectures par agent, l'une sur A, l'autre sur B et C. Chaque
defaut ci-dessous a ete verifie a la main avant correction.

**Le fan-out ne partait qu'a la fin d'une ingestion.** Or le passage a
`en_cours` fait AUSSI sortir une page de la file : le rang affiche
etait donc faux pendant TOUTE la duree de chaque conversion (83 a
164 s), et la page en cours annoncait encore « 1ᵉʳ dans la file »
pendant sa propre conversion. Il n'existe aucun polling de secours —
le WebSocket est le seul rafraichissement du menu. Trois autres chemins
(les gardes « page deja ingeree ») ecrivaient `reussie` et rendaient la
main sans rien dire. Le fan-out vit desormais dans
`_noter_l_etat_d_ingestion`, le point de passage unique de l'ecriture
d'etat : six chemins l'avaient manque chez les appelants, aucun ne peut
plus y echapper.

**Le fan-out faisait un N+1** — une requete par page en file pour en
trouver les destinataires, exactement le cout que le calcul du rang
evite cote vue. Il tient maintenant en deux requetes fixes, quelle que
soit la longueur de la file.

**Le test de topologie laissait passer la derive qu'il devait
empecher.** Il ne lisait que `-Q file` et `--concurrency=N` ; la forme
collee `-Qcelery,ingestion_docling` — parfaitement valide pour Celery —
etait lue comme « la file par defaut », le programme etait ignore par le
test des melanges, et la suite restait VERTE avec un worker qui tire les
deux files. Le lecteur couvre desormais les quatre ecritures de chaque
option, refuse `--autoscale` (qui ecraserait la concurrence declaree en
silence) et verifie les reglages d'arret.

**Deux tests ne prouvaient rien.** Celui de l'invariant prefork lisait
un compteur de cache qu'un convertisseur construit par un autre chemin
laisse a zero (verifie en injectant la violation) ; il observe
maintenant `sys.modules` apres avoir rejoue le bootstrap complet de
Celery. Celui du departage a date egale passait au vert meme sans tri
sur le `pk`, l'ordre d'insertion PostgreSQL suffisant ; la page qui doit
sortir premiere est desormais creee en second.

**`?v=37` n'avait pas bouge** alors que `hypostasia.js` change. Nginx
sert `/static/` en `Cache-Control: public, immutable` pendant 30 jours,
ce qui interdit meme la revalidation : tout navigateur deja venu aurait
garde l'ancien script — et sa position figee, precisement le defaut
corrige. Passe a `v=38`.

Corriges aussi : les logs de dev ouvraient deux journaux tournants
independants sur un meme fichier (lignes perdues au premier
basculement) ; `killasgroup` manquait sur les workers de prod (enfants
prefork orphelins apres un SIGKILL) ; la socket de dev etait celle de la
prod ; l'en-tete du `docker-compose.yml` documentait encore l'ancien
lancement et oubliait `celery_worker_docling`.

### CE QUI RESTE OUVERT — DEUX ARBITRAGES

**1. Une note qui attend plus de 15 minutes disparait de sa propre
file.** `ingestion_maj_le` est pose une fois, a la mise en file, et
n'est jamais rafraichi pendant l'attente : la regle du fantome
(`DELAI_INGESTION_FANTOME_MIN = 15`) ne distingue donc pas « worker
mort » de « sagement en file depuis 16 minutes ». A 83-164 s par
document, le seuil tombe des ~7 a 11 documents en file. La note sort
alors du rang (le menu affiche « En cours… », ce qui est faux), le badge
s'eteint, et elle decale le rang de tous ceux qui sont derriere alors
que sa tache est toujours dans Redis. Le defaut est ANTERIEUR au
chantier — la regle du fantome existait — mais l'affichage du rang le
rend visible et nuisible. Le corriger demande de choisir un second delai
pour l'attente et de le propager au badge et a la relance : c'est un
arbitrage, il n'a pas ete tranche.

**2. Une relance reordonne la file affichee.** `relancer_ingestion`
reecrit `ingestion_maj_le` : une page qui etait devant passe derriere,
alors que dans Redis sa tache reste devant. Le rang d'un tiers baisse
sans raison reelle.

**3. La croissance memoire du worker Docling n'est bornee par rien** —
ni `worker_max_tasks_per_child`, ni `worker_max_memory_per_child`.
Chaque conversion laisse 40 a 70 Mo qui ne sont jamais rendus a l'OS,
avant comme apres ce chantier. Un enfant qui enchaine une soixantaine de
PDF atteindrait ~5 Go sur un hote 8 Go. Le partage du convertisseur rend
ce plancher permanent au lieu de transitoire, sans l'aggraver (mesure :
la derive est plus faible qu'avant). Decision a prendre :
`--max-memory-per-child` sur `celery_worker_docling`.

---

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

