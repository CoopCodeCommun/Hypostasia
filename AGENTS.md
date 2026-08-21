# Hypostasia — instructions pour les agents

> Ce fichier est chargé dans le contexte de **chaque** session. Il porte les
> invariants du projet, puis son architecture.
>
> `CLAUDE.md` est un lien symbolique vers celui-ci.

**Les conventions de code — ViewSets explicites, serializers DRF, FALC,
commentaires bilingues, patterns HTMX, i18n, accessibilité — sont dans le skill
`djc`**, dont un hook `SessionStart` (`.claude/settings.json`) ordonne
l'invocation dès le démarrage. Si cette consigne n'est pas arrivée, l'invoquer à
la main : `Skill(djc)` — et ne réponds à aucune question de convention de code
sans l'avoir chargé. **Ne recopie jamais ici ce que `djc` dit déjà** : une seconde copie
finit toujours par diverger de la première, puis par la contredire. C'est
exactement ce qui est arrivé au fichier `GUIDELINES.md` que celui-ci remplace —
il se réclamait d'un skill disparu et se contredisait sur `uv run` à 226 lignes
d'écart.

## Où trouver le reste

| Ce que tu cherches | Où |
|---|---|
| Les chantiers ouverts, l'environnement, les décisions en attente | `PLAN/PASSATION.md` |
| Ce qui a changé et comment le tester à la main | `CHANGELOG/` |
| Les défauts connus non corrigés | `CHANGELOG/DEFAUTS-DIFFERES.md` |
| Ce qui est **décidé mais pas codé** | `PLAN/TODO/` — une note par intention, supprimée le jour où le code la porte |
| L'état cible d'un domaine | `PLAN/specs/` — leurs **encarts datés en tête** font foi, pas leurs sections |
| Le pourquoi des décisions de conception | `PRESENTATION-V3.md` |
| Le **mécanisme** du moteur, en diagrammes | `PLAN/Diagrams/` — ingestion → périmètre → article sourcé → vérification. Mermaid, rendu nativement par GitHub |
| Ce qui est archivé, et pourquoi | `PLAN/README.md` |
| L'état vivant, hors dépôt | la mémoire persistante : `~/.claude/projects/<chemin-du-dépôt-aplati>/memory/`, index dans `MEMORY.md` — **à lire en premier** |

> Le nom du dossier de mémoire **dépend de la machine** : c'est le chemin du
> dépôt, aplati (`/home/ubuntu/Hypostasia` → `-home-ubuntu-Hypostasia`). Cette
> ligne a survécu à un changement de machine en pointant vers l'ancienne, le
> 16 août 2026 : un agent qui suit la consigne « à lire en premier » lit alors
> un dossier vide, sans que rien ne le signale. **Ne code jamais un chemin en
> dur ici** : lister
> `~/.claude/projects/` le donne en une commande.

**Trois documents seulement tiennent un état d'avancement** : `CHANGELOG/`,
`PLAN/PASSATION.md` et la mémoire. N'en écris pas un quatrième : il périmera
sans que personne ne le sache. C'est ce qui est arrivé à `PRESENTATION-V3.md`,
qui a affirmé pendant six jours que le moteur ELEMENT n'était branché à rien.

⚠️ **`docs/superpowers/` contient des plans ÉCRITS et NON EXÉCUTÉS**, qui se
lisent comme du livré si on ne le sait pas. Lesquels, et ce qu'ils feront péter
en s'exécutant : `CHANGELOG/DEFAUTS-DIFFERES.md`. **Ce fichier-ci ne les
énumère pas** — il périmerait à la première exécution, et il s'interdit de tenir
un état d'avancement.

---

# PARTIE 1 — CE QUI CASSE LE PROJET

## Git — aucune écriture, jamais

Ni `commit`, ni `add`, ni `push`, **ni `checkout --`, ni `stash`, ni `reset`,
ni `restore --`, ni `clean`**. Le mainteneur commite lui-même, et le working tree
porte régulièrement des heures de travail non commité : une seule commande
destructive les efface.

**Jamais de `Co-Authored-By`** dans quoi que ce soit.

Si une consigne de tâche dit « commite », **écris le message suggéré dans ton
rapport final et arrête-toi.**

En cas de modification indésirable (reformat, écrasement) : **ne tente pas de
rollback avec git.** Préviens le mainteneur, documente ce qui s'est passé,
attends ses instructions.

## `ruff` — les deux commandes sont dangereuses sur un fichier existant

| Commande | Le danger |
|---|---|
| `ruff format` | réécrit le fichier **entier** : des milliers de lignes que tu n'as pas écrites |
| `ruff check --fix` | supprime les **imports à effet de bord** (`@admin.register`, `@receiver`, `@app.task`) : l'enregistrement disparaît en silence, Django ne démarre plus |

**Fichier neuf** (créé dans ta session) : les deux sont permises.
**Fichier pré-existant** : `format` jamais ; `--fix` seulement après inspection
manuelle des imports « inutilisés », puis `make check` **et** la suite complète.

## Les invariants

Chacun a déjà cassé quelque chose. Aucun ne lève d'erreur explicite.

- **`DEBUG` et `NGINX_CONF` vont ENSEMBLE.** La conf de prod avec `DEBUG=true`
  envoie `/` vers le port 8001 où personne n'écoute : **502 sur tout le site**.
  L'inverse laisse gunicorn sans trafic. Verrouillé par
  `front/tests/test_script_d_installation.py`.
- **TROIS workers Celery, jamais moins.** `celery_worker` sert la file par
  défaut à concurrence 2 ; `celery_worker_docling` sert `ingestion_docling` à
  **concurrence 1** — une conversion à la fois (~2 Go et ~83 s de warm-up
  chacune). C'est aussi ce qui rend exacte la position affichée dans la file.
  `celery_worker_juge_local` sert `verification_locale` à **concurrence 1** et
  **sous `nice -n 19`**. Depuis le 19 août 2026 il porte **quatre encodeurs NLI**
  (`core/services/juges_locaux.py`) et non plus ShieldStral. Résidents, ils
  occupent **5,13 Go de RSS pour 6,01 Go de pic au chargement** (mesuré le
  19 août) et coûtent **42 à 160 ms** par citation et par juge, contre 7,7 Go et
  ~25 s pour ShieldStral. **Ce pic de 6 Go décide de l'hébergement** : ajouté à
  une conversion Docling (~2 Go) et à PostgreSQL, il exclut un VPS de 4 ou 8 Go,
  et `nice` ne protège pas de l'OOM killer. **La topologie ne change pas pour autant** : la
  concurrence 1 est ce qui borne la mémoire (les modèles sont chargés une fois,
  pas une fois par process), et le `nice` remplace une porte « attendre que le
  CPU baisse » qui aurait affamé la tâche **en silence** sur une machine
  chargée. Verrouillés par
  `hypostasis_extractor/tests/test_files_celery_ingestion.py` et
  `.../test_worker_du_juge_local.py`.
- **Une suite de tests à la fois, jamais `--parallel`.** La base de test est
  partagée : deux exécutions simultanées se détruisent mutuellement en plein vol
  (755 erreurs fantômes constatées).
- **Le build Tailwind est FIGÉ.** Toute classe absente du bundle est **inerte** :
  `z-[70]`, `min-w-[160px]`, `h-11` ne font rien, sans la moindre erreur. Passer
  par les tokens CSS de `maquette.css` (`--papier`, `--encre`, `--panneau`,
  `--gouttiere`), ou vérifier au navigateur que la classe agit.
- **Après toute modification de CSS ou de JS : `collectstatic`** *et* bump du
  `?v=` dans le gabarit. Les statiques sont servis depuis `staticfiles/`, pas
  depuis les sources — un fichier neuf non collecté donne un 404 silencieux.
- **Aucun `DEFAULT_PERMISSION_CLASSES`** : tout endpoint DRF est `AllowAny` par
  défaut. Contrôle explicite dans chaque vue, et **doctrine du 404, jamais 403**.
- **Une migration doit être appliquée à la base de dev dès que le code la
  référence.** Le serveur de dev est permanent : il tombe en `ProgrammingError`
  sinon. C'est arrivé.
- **`AncrageExtraction.element` est en PROTECT** : supprimer une page exige de
  retirer ses portions d'abord.

## Les commandes : par le Makefile, depuis l'hôte

```bash
make                 # liste les cibles
make install         # docker compose up -d + bin/install.sh (idempotent)
make dev             # runserver + les TROIS workers Celery
make check
make test            # l'aide des cibles de test et de leur coût
make test-rapide     # le geste quotidien — tout sauf e2e/docling/llm
```

Le Makefile est une **façade** : il appelle `bin/install.sh` et
`supervisord-dev.conf`, il ne réimplémente rien. Deux descriptions du même
démarrage finiraient par diverger — c'est la panne que ce Makefile existe pour
empêcher. **N'écris donc jamais une commande de lancement ailleurs qu'ici.**

`make test-llm` appelle de vrais modèles : **c'est facturé**, la cible demande
confirmation.

`uv run` fonctionne encore mais n'apporte rien (le `PATH` de l'image contient
déjà `/app/.venv/bin`). **Sous supervisord il est à proscrire** : le SIGTERM
d'arrêt irait au wrapper au lieu du worker qui doit finir sa tâche.

## La méthode attendue

- **Planifier avant de coder.** Pour toute tâche non triviale : comprendre,
  proposer l'approche, attendre la validation du mainteneur.
- **TDD** : le test d'abord, qu'on regarde échouer, puis le code.
- **Ne jamais inventer un chiffre.** Un compte annoncé est un compte mesuré.
  Si tu n'as pas mesuré, dis-le.
- **Un trou de spec s'écrit avant de se coder**, en addendum daté.
- **Vérifier au navigateur** tout travail de front, en clair **et** en sombre,
  contrastes calculés — pas des impressions.
- **Un fichier `CHANGELOG/AAAA-MM-JJ-slug.md` par chantier**, créé en même temps
  que le code : le résumé au-dessus d'un `---`, comment tester à la main en
  dessous. Format complet dans `CHANGELOG/README.md`.
- **Résoudre le problème posé, rien de plus.** Pas de refactoring bonus, pas
  d'abstraction « au cas où ». Trois lignes similaires valent mieux qu'une
  abstraction prématurée.
- **Répondre en français**, être concis.

---

# PARTIE 2 — L'ARCHITECTURE

## Les trois apps et leur frontière

| App | Responsabilité | Type de réponse |
|---|---|---|
| `core` | Les modèles de données, et l'API JSON de l'extension navigateur | JSON uniquement |
| `front` | Toute l'interface web (partials HTMX) | HTML uniquement |
| `hypostasis_extractor` | Pipeline d'extraction, analyseurs, ingestion Docling | HTML + JSON |

**La règle de séparation** : `core/views.py` ne sert **que** l'extension
navigateur — `PageViewSet` (dont les actions `me`, `mes_dossiers`,
`classer_depuis_extension`) et `SidebarViewSet`. Aucun template de page complète. `front/` gère toute l'interface utilisateur.
Les deux apps partagent les **modèles** de `core`, jamais les **vues**.

### Les vues sont éclatées en huit fichiers

`front/views.py` a dépassé les 6 000 lignes ; les ViewSets récents vivent à côté
et sont importés dans `front/urls.py` :

| Fichier | Ce qu'il porte |
|---|---|
| `front/views.py` | lecture, extractions, import, config IA, bibliothèque, dossiers, pages |
| `front/views_corpus.py` | carnets, notes, bases de connaissances |
| `front/views_synthese.py` | wikis, synthèses dirigées, citations |
| `front/views_alignement.py` | tableau d'alignement cross-documents |
| `front/views_taches.py` | le menu des tâches et leurs notifications |
| `front/views_accueil.py` | l'aide, le manifeste, et le message d'accueil |
| `front/views_auth.py`, `views_groupes.py`, `views_invitation.py` | comptes, groupes, invitations |

**Un ViewSet neuf va dans son propre fichier**, jamais dans `front/views.py`.

## Le routing

Tout passe par `DefaultRouter` dans `front/urls.py`. Jamais de `path()` manuel
pour une vue DRF — sauf les deux collections carnet-niveau de la couche
synthèse, dont le préfixe `carnets/` appartient déjà au `CarnetViewSet`.

```
lire · dossiers · pages · extractions · config-ia · import · questionnaire
alignement · auth · groupes · invitation · taches
carnets · notes · bases                          ← couche corpus
wikis · syntheses · citations                    ← couche synthèse
elements                                         ← moteur ELEMENT (BR-E)
aide · manifeste                                 ← les deux écrans d'accueil
```

Plus trois `path()` explicites : la racine (`BibliothequeViewSet`, qui
**redirige vers `/carnets/`** depuis le 21 août 2026 — elle ne rend plus
d'écran),
`carnets/<pk>/wikis/` et `carnets/<pk>/syntheses/`.

> **`/arbre/` n'existe plus.** L'arbre latéral et son ViewSet ont été retirés le
> 12 août 2026, avec le menu burger. `front/tests/test_aucun_geste_orphelin.py`
> vérifie que chaque geste qu'il portait a gardé un point d'entrée ailleurs :
> **ne pas casser ce test**, il existe parce qu'un retrait « propre » a deux fois
> failli supprimer une fonction entière sans que personne ne le voie.

## WebSocket — deux messages, et pas un de plus

**Le WebSocket ne pousse aucune progression.** La refonte A.6 (mai 2026) a
supprimé le streaming par chunk : il ne reste qu'un consumer minimal qui dit
« c'est fini », et le client va rechercher le reste en HTTP.

```
Celery (front/tasks.py)
    ↓ notifier_tache_terminee()  ·  notifier_la_file_d_ingestion()
    ↓ group_send vers le group « user_<pk> »
NotificationConsumer (front/consumers.py) — AsyncJsonWebsocketConsumer
    ↓ send_json(...)   ← du JSON, PAS du HTML
hypostasia.js (~l. 1415)
    ↓ refetch le bouton des tâches en HTTP
```

| Message | Quand | Ce que le client en fait |
|---|---|---|
| `tache_terminee` | une tâche de l'utilisateur se termine | refetch du bouton (couleur + badge) |
| `file_ingestion_modifiee` | l'ingestion **de quelqu'un d'autre** se termine | met à jour la position affichée dans la file |

**Le second existe parce que la position dans la file change sans que rien ne se
soit passé chez le destinataire** — il faut donc le lui dire.

### Ce qu'il ne faut PAS croire

- **Pas d'OOB swap par WebSocket.** Aucun template ne porte `hx-ext="ws"`, le
  consumer n'envoie jamais de HTML. Toute doc qui décrit `analyse_progression`,
  `rafraichir_drawer` ou `analyse_terminee` décrit un état mort depuis mai 2026 —
  il n'en reste qu'un commentaire vestigial dans `drawer_vue_liste.html:128`.
- **Le consumer refuse les non-authentifiés** (`connect()` ferme la connexion) et
  chaque utilisateur n'écoute que son propre group `user_<pk>`.

> Cette section a décrit le contraire — trois messages, des fragments HTML, des
> pièges de MutationObserver — jusqu'au 16 août 2026. C'était le § 7b de
> `GUIDELINES.md`, recopié sans vérification dans le fichier chargé à chaque
> session. Vérifié cette fois : `rg` sur les trois noms de messages rend zéro
> occurrence en Python et en JS.

## Celery — deux files, et ce qui passe dedans

- **Broker** : Redis. `CELERY_BROKER_URL` (`settings.py:212`) vaut
  `redis://redis:6379/0` en conteneur ; la valeur par défaut du code
  (`redis://localhost:6379/0`) ne sert qu'en exécution hors Docker.
- **Backend** : `django-db`, via `django-celery-results`.
- **Config** : `hypostasia/celery.py`, namespace `CELERY_` dans `settings.py`.
- **Tâches** : `front/tasks.py` (transcription, analyse, notifications),
  `hypostasis_extractor/tasks_element.py` (ingestion Docling).

### Le pattern d'une tâche

```python
# Les imports Django vivent DANS le corps de la tache, pas en tete de fichier :
# le worker charge le module avant que Django ne soit pret.
# / Django imports live inside the task body, not at module level.
@shared_task(bind=True)
def ma_tache_longue(self, job_id, chemin_fichier):
    from core.models import MonModele
    ...
```

**Toute tâche nouvelle exige un redémarrage du worker**, sinon il tourne avec
l'ancien code : `make restart S=celery_worker`.

### Import audio — le flux complet

1. `ImportViewSet.fichier()` détecte l'audio via `est_fichier_audio()`
2. le fichier est sauvé dans `AUDIO_TEMP_DIR` sous un nom UUID
3. une `Page` en statut `processing` et un `TranscriptionJob` sont créés
4. `transcrire_audio_task.delay(job_id, chemin)` part dans la file
5. la réponse est un partial de polling HTMX (toutes les 3 s)
6. `ImportViewSet.status()` répond au polling et rend le résultat quand il est là

## Le fork LangExtract — RETIRÉ, et un risque qui demeure

Il n'y a plus de fork. `_creer_annotateur_avec_progression`, sa sous-classe
`AnnotateurAvecProgression` et `_recuperer_extractions_json_corrompu` ont été
**retirés le 18 août 2026** — **497 lignes** de `front/tasks.py`, qui n'avaient
aucun appelant. Tous les chemins d'extraction passent par `lx.extract` et
l'`Annotator` standard.

> Cette section a décrit pendant des mois un « workaround actif » qui ne
> protégeait **aucun chemin**. `PLAN/LANGEXTRACT_OVERRIDES.md` décrit le code
> supprimé : le lire comme un document d'archive, pas comme l'état du dépôt.

**Le risque, lui, est réel et n'est couvert par rien.** Une plateforme qui rend
`[...]` au lieu de `{"extractions": [...]}` fait perdre ses extractions **en
silence** : le `FormatHandler` rejette, `suppress_parse_errors=True` fait rendre
une liste vide, et le job finit `completed` avec zéro extraction — indiscernable
d'une page sans idée. Seule trace : un `logging.exception` dans les journaux du
worker.

Le point d'injection propre, s'il faut y remédier un jour, est
`resolver_params={"format_handler": …}` — pas une sous-classe d'`Annotator`.

### Une extraction par une plateforme compatible OpenAI

LangExtract choisit son moteur par **expression régulière sur le nom du
modèle** : `^mistral`, `^qwen`, `^llama`, `^gemma`, `^phi`, `^deepseek` partent
tous vers `OllamaLanguageModel`, qui parle l'API propriétaire d'Ollama. Pointé
sur `api.mistral.ai`, ce moteur échoue — et rien dans le nom ne le laissait
deviner.

`resolve_model_params` passe donc un `ModelConfig` qui désigne le provider par
son **nom**, ce qui court-circuite la table. **C'est une API publique de la
bibliothèque : aucun fork.** Verrouillé par
`hypostasis_extractor/tests/test_extraction_par_api_compatible.py`, dont un test
épingle exprès le routage par défaut : s'il tombe, c'est la table de motifs qui a
changé.

## Docker — un seul compose pour dev et prod

| | `DEBUG=true` (dev) | `DEBUG=false` (prod) |
|---|---|---|
| Démarrage | `bin/start-dev.sh` | `bin/start-prod.sh` |
| Serveur HTTP | `runserver` **:8000** (ASGI, sert aussi le WS) | Gunicorn **:8001** |
| WebSocket | le même runserver | Daphne **:8000** |
| Celery | 2 workers (`supervisord-dev.conf`) | 2 workers (`supervisord.conf`) |
| Nginx | `NGINX_CONF=dev.conf` → tout vers 8000 | `default.conf` → `/` vers 8001, `/ws/` vers 8000 |

### Cette stack ne prend AUCUN port de l'hôte

Les ports **80 et 443 appartiennent au Traefik partagé** de la machine — celui
qui détient le réseau `frontend` (déclaré `external: true`) et qui définit le
résolveur `myresolver` que les labels de `nginx` réclament. Notre `nginx` s'y
inscrit par ses labels, rien de plus.

**Ce Traefik doit tourner AVANT la stack.** Sans lui, tous les conteneurs
démarrent parfaitement et **rien ne répond sur le domaine** : personne n'écoute
sur 80. Aucun message ne le dit.

> Un service `traefik` a vécu dans ce compose jusqu'au 16 août 2026. Il prenait
> `0.0.0.0:80` et `:443` — donc la place du vrai — et ne définissait **aucun**
> résolveur de certificats alors que les labels en réclamaient un : le site ne
> répondait qu'en TLS auto-signé. **Ne pas le remettre.**

### Deux dossiers doivent exister AVANT `docker compose up`

`staticfiles/` et `media/` sont montés dans `nginx` et **ignorés par git** : un
clone frais ne les a pas. Si Docker les rencontre absents, c'est le **démon**
qui les crée — donc `root:root` — et le conteneur web, qui tourne en **uid
1000**, ne peut plus y écrire : `collectstatic` échoue, `bin/install.sh`
s'arrête sous `set -e`, et `restart: unless-stopped` relance le conteneur en
boucle. Constaté en production le 16 août 2026, sur un clone neuf.

`make install` les crée donc sur l'hôte, avant tout conteneur. Le `mkdir -p` de
`bin/install.sh` ne rattrape rien : il tourne **dans** le conteneur, après coup,
et `mkdir -p` réussit sur un dossier existant quel qu'en soit le propriétaire.
Verrouillé par `front/tests/test_script_d_installation.py`.

### Les scripts, tous dans `bin/`

- **`bin/install.sh`** — la séquence d'installation, idempotente. Accepte une
  étape : `tout` (défaut), `fixtures`, `statiques`, `llm`. Chaque étape saute ce
  qui est déjà présent (~3 min au premier passage à cause des conversions PDF,
  **10 s** ensuite). `analyser_les_notes_etalons` est **idempotente par défaut** —
  elle n'analyse que ce qui ne l'est pas encore, donc un redémarrage ne
  refacture rien ; `--forcer` est le seul flag, et il fait l'inverse.
- **`bin/start-dev.sh`** — installation, puis `supervisord-dev.conf`.
- **`bin/start-prod.sh`** — attente PostgreSQL, installation, puis
  `supervisord.conf`.

Ces trois-là s'exécutent **dans le conteneur** : c'est ce qui leur permet de
tourner au démarrage, quand aucun hôte n'est au bout du fil. Le Makefile vit sur
l'hôte et ne fait que les **appeler**.

**Pour tout refaire : `docker compose down -v && make install`.** Il n'existe pas
de rechargement partiel, délibérément — il laisserait une base à moitié ancienne
sans qu'on sache ce qu'elle porte.

### La sauvegarde

```bash
make backup          # dump PostgreSQL + media/ + .env dans une archive borg
                     # (au 1er lancement : cle SSH, depot BWH, .env, cron)
make backup-check    # la derniere archive est-elle VRAIMENT restaurable ?
make restore         # ECRASE la base (confirmation « RESTAURER » exigee)
make verif-prod      # depot, cron, secrets, coherence DEBUG/NGINX_CONF
```

Ces scripts vivent aussi dans `bin/` mais s'exécutent **sur l'hôte** : le cron et
la clé SSH du dépôt sont sur la machine, pas dans le conteneur.

Une archive porte le **dump, `media/` et `.env`** — le reste est dans git.
`make backup-check` ne se contente pas de constater qu'une archive existe : il
**déroule** le dump (`pg_restore -f /dev/null`), parce qu'un dump amputé de ses
100 derniers octets passe `pg_restore -l` au vert (mesuré le 16 août 2026).

**Deux pièges de shell, verrouillés par des tests.** Ni l'un ni l'autre ne lève
d'erreur : ils rendent simplement la sauvegarde fausse.

- **Ne jamais sourcer le `.env` tel quel.** Il déclare `UID=1000`, une variable
  en **lecture seule** de bash : sous `set -e`, le script s'arrête à cette ligne.
  Passer par `. <(grep -vE '^[[:space:]]*(UID|GID)=' "$FICHIER")`.
- **Jamais de `printf | grep -q` dans un script à `pipefail`.** `grep -q` sort à
  la première correspondance, l'écrivain prend un SIGPIPE, et `pipefail` fait
  lire une correspondance **trouvée** comme une **absence**. Utiliser un
  here-string : `grep -q motif <<< "$VAR"`.

### Clés API

**Les clés ne sont JAMAIS en base.** Aucun modèle n'a de champ pour en porter une —
vérifié le 17 août 2026 : `rg "api_key\s*=\s*models\."` ne rend rien. Les variables
d'environnement sont la **seule** source : `GOOGLE_API_KEY`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `OLLAMA_API_KEY`, `OPENROUTER_API_KEY`.

> Cette section annonçait « champ en base > variable d'environnement », et l'admin Django
> comme endroit où les saisir. Les deux étaient faux : l'admin est désactivé
> (`core/admin.py`) et le champ n'a jamais existé. `.env.example` portait la même erreur.

Un modèle servi par une **API compatible OpenAI** (`Provider.COMPATIBLE_OPENAI`) dit dans
sa ligne quelle variable lire — `variable_de_cle_api` — et jamais la clé elle-même.
C'est `base_url` qui désigne la plateforme : OpenRouter, Mistral, Scaleway, un Ollama
local. Une valeur d'enum par plateforme obligerait à toucher au code à chaque nouvelle,
pour un chemin d'appel identique.

### Un modèle par rôle

`Configuration.ai_model` n'est plus le modèle de tout le monde. `ModeleParRole` affecte un
`AIModel` à un usage — **rédacteur d'article**, **juge de vérification** — et la
résolution passe TOUJOURS par `core/services/modeles_par_role.modele_du_role()`, jamais
par une lecture directe de la table : c'est ce qui donne le **repli** sur
`Configuration.ai_model` partout. Table vide ⇒ comportement d'avant, à l'identique.

Le rôle se résout **à la création du job**, jamais à l'appel : c'est
`ExtractionJob.ai_model` qui porte la provenance de ce qui a été produit.

L'affectation se fait par `manage.py affecter_un_modele_a_un_role` — l'admin Django est
désactivé et il n'y a pas d'écran. **Un modèle créé pour un rôle naît `is_active=False`** :
l'écran de configuration IA propose au clic tout modèle actif et le pose dans
`Configuration.ai_model`, qui est le modèle d'**extraction** — or LangExtract ne pilote
que Google, OpenAI et Ollama.

## Le front — avant de toucher un template

### Les écrans du corpus ont deux includes obligatoires

`_style_maquette.html` et `_fil_ariane_oob.html`. **Rien ne les pose à la place
de l'écran, et les oublier ne lève aucune erreur** — l'écran s'affiche
simplement sans son style et sans son fil d'Ariane.

### Le CSS

Tailwind est **compilé localement** (`front/static/front/css/tailwind.css`),
chargé avec un `?v=`. Le build est figé (voir les invariants). Les tokens de
design vivent dans `maquette.css`.

Polices : **Lora** (citations humaines), **B612** (labels, tags), **B612 Mono**
(texte machine/IA), **Srisakdi** (interventions lecteur). Trois polices = trois
provenances : le lecteur sait qui parle sans avoir à le lire.

### L'étalon visuel

`front/static/front/maquettes/` — `maquette.html` (lecture), `corpus.html`
(carnet), `selection-preuves.html`. **Lire l'en-tête de `maquette.html` avant de
coder un écran** : elle distingue les référentiels tirés du code réel (la
maquette s'y aligne) des cibles, et porte trois arbitrages du mainteneur qu'il ne
faut pas lire comme des retards.

`scripts/verifier_les_maquettes.py` contrôle l'étalon **contre lui-même**, jamais
contre le rendu Django.

### Les commentaires de template Django

`{# … #}` ne fonctionne que **sur une seule ligne**. Pour plusieurs lignes :
`{% comment %} … {% endcomment %}`.

## Le vocabulaire métier

- **Hypostase** — le type sémantique d'une extraction. Il y en a **30**,
  réparties en **6 familles épistémiques**. C'est le concept fondateur du projet,
  et son nom.
  > Ne pas confondre avec les **8 familles de couleurs** de l'affichage
  > (`hypostase_famille`) : ce regroupement-là est purement visuel.
- **Statut de débat** — **deux** valeurs seulement : `NOUVEAU` et `COMMENTE`
  (`hypostasis_extractor/models.py:186`). Les six statuts d'autrefois
  (consensuel, discutable, discuté, controversé…) ont été fusionnés le 2 mai 2026.
- **Carnet** (`Dossier` en code), **base de connaissances**, **note** (`Page` en
  code). Le renommage en base a été délibérément abandonné : « carnet » est le
  mot à l'écran, `Dossier` le nom dans le code.
- **Élément** (`ElementDocument`) — l'unité d'ancrage. Une extraction est ancrée
  à une **portion** d'élément, et c'est cette ancre qui fait la preuve.

### Le moteur ELEMENT est le SEUL moteur

Décision de gouvernance du **10 août 2026**. L'ancien moteur d'ancrage — offsets
absolus, pastilles de marge — est mort, et son code a été retiré le jour même
(R3, ~1 100 lignes, plus le flag `Page.moteur`). **Tout document qui décrit deux
moteurs, ou un choix entre eux, est périmé sur ce point.**

### « Phase » ne veut pas dire la même chose selon le document

C'est le piège de vocabulaire le plus coûteux du projet, parce qu'il ne
ressemble pas à un piège :

| Document | Sa numérotation |
|---|---|
| `SPEC-ancrage-par-element-v2.md` | A → K, plus les addenda BR-A → BR-F et U1 → U5 |
| `SPEC-synthese-carnet.md` | A → I |
| `SPEC-corpus-base-carnet-note.md` | A → I |
| `PLAN/archive/PHASES/` | 1 → 29 |

Le détail par spec est dans `PLAN/specs/README.md`.

« La phase H » désigne quatre choses différentes. **Toujours préciser de quelle
spec on parle** — et se méfier d'une consigne qui ne le précise pas.
