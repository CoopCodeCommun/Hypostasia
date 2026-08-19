# Deux juges en parallèle : ShieldStral câblé à côté de Mistral / Two judges side by side

**Date :** 2026-08-18
**Migration :** Oui — `core.0071_second_avis_de_verification`
```bash
docker exec -w /app hypostasia_web python manage.py migrate core
```

## Résumé / Summary

**Quoi / What :** un **second juge** tourne désormais à côté du juge de
production. ShieldStral, modèle local de 3,8 milliards de paramètres, rend un
degré lu sur les **logits** d'un token — sans clé d'API, sans réseau, sur
processeur. Le bouton « Vérifier les citations » lance les deux. Le second avis
**ne pilote rien** : il est là pour être comparé.
*/ A second, local judge (ShieldStral, logits-read) now runs alongside the
production judge. It drives nothing; it exists to be compared.*

**Pourquoi / Why :** les deux mesures publiées sur ce juge ne concordent pas —
**AUC 0,923** sur quinze paires relues à la main, **0,734** sur les 145 paires
gelées, dont la « vérité » est elle-même un juge à 77 % de reproductibilité.
Aucune référence humaine à grande échelle n'existe. Cette campagne en produira
une, **un désaccord à la fois**.
*/ The two published measurements disagree, and no large-scale human reference
exists. This campaign builds one, one disagreement at a time.*

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | quatre colonnes de second avis sur `SourceLink` |
| `core/migrations/0071_…` | la migration |
| `core/services/juge_local.py` | **nouveau** — le juge local, son cadrage, son seuil, ses threads |
| `core/services/verification.py` | `poser_un_second_avis`, `paires_sans_second_avis`, `accord_des_deux_juges` |
| `core/services/synthese.py` | le report de verdict emporte **aussi** le second avis |
| `front/tasks.py` | `noter_avec_le_juge_local_task` — **par paquets de 10** |
| `front/views_synthese.py` | `_lancer_un_second_avis` (dans la **vue**), le verrou de re-clic, le contexte du panneau |
| `front/templates/…/preuve.html` | l'accord, la seconde barre, les quatre états |
| `front/templates/…/_style_maquette.html` | l'encadré du second avis |
| `hypostasia/celery.py` | routage vers `verification_locale` |
| `supervisord.conf`, `supervisord-dev.conf` | **troisième worker**, concurrence 1, `nice -n 19` |
| `front/management/commands/comparer_les_deux_juges.py` | **nouveau** — lire la campagne |
| `benchmarks/juge_local/mesurer_les_threads.py` | **nouveau** — la mesure qui fonde le réglage |
| `benchmarks/juge_de_verification/comparer_shieldstral.py` | importe le cadrage de la production, sans copie |
| `AGENTS.md` | « deux workers » devient trois |
| `core/tests/test_second_avis_de_verification.py` | **nouveau** — 11 tests |
| `front/tests/test_second_avis_a_l_ecran.py` | **nouveau** — 11 tests |
| `hypostasis_extractor/tests/test_worker_du_juge_local.py` | **nouveau** — 8 tests |

## Les cinq décisions, et ce que chacune évite

### 1. Des colonnes, pas une table liée

Une table `AvisDeVerification` liée par une FK en `CASCADE` avait un défaut
fatal : `indexer_les_citations` **détruit et recrée** tous les `SourceLink` d'un
article à chaque mise à jour de wiki, et le report de verdict ne recopie que des
**colonnes**. Chaque tour aurait effacé tous les avis — c'est-à-dire exactement
les données que la campagne existe pour accumuler.

Quatre colonnes voyagent gratuitement dans le report existant. **Limite
assumée** : un seul second juge à la fois. Un troisième exigerait la table, et
il faudrait alors régler le report.

### 2. Le seuil est **figé sur l'avis**

Les deux juges ne sont pas sur la même règle : **45/100** pour un juge d'API
sollicité par le protocole texte, **≈ 38/100** pour un juge local lu sur les
logits. Relire un degré avec le seuil de l'autre ferait conclure au désaccord là
où il y a accord parfait. `accord_des_deux_juges` lit donc **chaque juge avec
son seuil**, et le seuil du second avis n'est jamais relu depuis la
Configuration.

### 3. Par paquets de 10, à cause d'un plafond qui tue en silence

`CELERY_TASK_TIME_LIMIT = 30 * 60` (`settings.py:219`). La synthèse dirigée
étalon porte **87 citations** : à 25,7 s/paire, c'est **37 minutes** — SIGKILL,
modèle de 7,7 Go rechargé, reste du lot sans avis, **et personne ne le sait**.

Dix paires font ~4 min 20. Trois bénéfices d'un seul geste : sous le plafond, un
redémarrage ne coûte qu'un paquet, et l'avancement se lit tout seul.

### 4. Le fan-out vit dans la **vue**, jamais dans la tâche

`bin/install.sh:149` appelle `verifier_les_citations_etalons`, qui lance
`verifier_les_citations_task` **directement** — et `install.sh` tourne à
**chaque démarrage de conteneur**. Un fan-out placé dans la tâche aurait mis les
145 paires de l'étalon en file à chaque redémarrage, soit **~1 h de processeur**,
exactement pendant que Docling convertit les fixtures.

**Conséquence assumée : l'étalon d'installation n'a pas de second avis.** Il
faut un geste explicite pour lui en donner un.

### 5. `nice -n 19`, et pas une porte « attendre que le CPU baisse »

Une porte **affame en silence** : sur une machine chargée elle ne s'ouvre
jamais, et rien ne le dit — la dégradation silencieuse contre laquelle tout le
reste du projet est écrit. Elle court aussi après une course : on mesure une
charge basse, on démarre, Docling arrive trois secondes plus tard.

`nice` laisse le noyau arbitrer en continu, sans scrutation. Vérifié sur cette
machine : `nice -n 19` réussit dans le conteneur **sans `CapAdd` et sans
privilège** — baisser sa priorité ne demande aucune capacité. Et `nice` fait un
`exec` : il ne laisse **aucun wrapper** entre supervisord et le worker,
contrairement à `uv run`.

**La borne à connaître** : le nice n'arbitre qu'**à l'intérieur** du cgroup de
ce conteneur. Docling, gunicorn et daphne y vivent — donc là où ça compte. Face
à PostgreSQL, Redis ou Traefik, qui sont d'autres cgroups, le conteneur pèse son
poids plein.

## Le réglage des threads : **6**, mesuré

Machine à 8 cœurs, 22 Go, aucune limite Docker. Modèle chargé une seule fois,
3 paires par réglage :

| threads | s/paire | accélération vs 2 | rendement/thread |
|---|---|---|---|
| 2 | 62,3 | 1,00× | 1,00 |
| 3 | 46,4 | 1,34× | 0,90 |
| 4 | 36,1 | 1,73× | 0,86 |
| **6** | **25,7** | **2,42×** | **0,81** |
| 8 | 20,2 | 3,09× | 0,77 |

**Cette mesure a corrigé une intuition fausse** : on avait supposé qu'une
inférence CPU passait mal à l'échelle. Six threads rendent **2,42×**.

`SHIELDSTRAL_THREADS` (défaut 6) et `SHIELDSTRAL_SEUIL` (défaut 38) se règlent
par l'environnement. Le seuil est **provisoire par construction** : sa propre
mesure le déclare sur-ajusté.

Le voisinage de Docling, lui, **a été mesuré depuis** — voir plus bas. Le
résultat nuance l'argument : `nice` pondère le temps processeur et non la bande
passante mémoire, mais Docling ne perd que 7 % sans aucune protection. Si un
jour le voisinage gêne, c'est le nombre de threads qu'il faudra baisser.

## Ce que la première campagne a mesuré

Base **reconstruite de zéro** le 18 août au soir, deux articles, 35 citations.

| | |
|---|---|
| comparables (les deux juges) | **29** |
| **accord** | **20/29 — 69 %** |
| **AUC du second juge** | **0,867** |
| désaccords | **9, tous dans le même sens** |

Les neuf : Mistral pose son cran **40** (« appuie de loin, sans rien établir »)
là où le juge local voit 46,9 à 85,2. Ce n'est pas du bruit, c'est un décalage
systématique de calibration.

**Le seuil de 38 ne transfère pas** — l'accord maximal sur ce corpus est à 85
(24/29). **Il ne faut pas pour autant l'y déplacer** : ce serait ajuster le
second juge sur le premier, l'inverse de ce à quoi sert un second avis. Détail
et réserves : `benchmarks/juge_local/2026-08-18_premiere-campagne-a-deux-juges.md`.

**Les quatre crans, confirmés sur données de production** : le juge de
production rend `{0: 1, 40: 14, 70: 13, 100: 1}` — aucune valeur intermédiaire,
sur un corpus et un jour différents de ceux du banc. Le juge local, lui, rend
8,5 · 37,8 · 46,9 · 75,5 · 99,0. C'est ce qui justifie après coup d'avoir stocké
un **flottant**.

## Ce que `nice` achète vraiment

Mesuré, quatre conditions :

| | Docling (8 conversions) | juge local (s/paire) |
|---|---|---|
| chacun seul | 130,6 s | 23,8 s |
| ensemble, juge local sous `nice -n 19` | **124,7 s** | 27,7 s |
| ensemble, **sans** nice | **139,9 s** | 26,6 s |

**`nice` achète ~11 % du temps mural de Docling.** C'est réel et c'est modeste :
Docling ne perd que **7 %** sans aucune protection. L'idée qu'il « mourrait de
faim » était exagérée pour ce qui concerne `nice` — les protections qui portent
sont la **file dédiée à concurrence 1** et le **plafond de threads**. Réserve :
une seule passe par condition, bruit de l'ordre de ±5 %. Détail :
`benchmarks/juge_local/2026-08-18_le-voisinage-de-docling.md`.

---

## Comment tester (à la main) / Manual test

### Avant tout : le troisième worker doit être démarré

Le programme est neuf dans les deux fichiers supervisord. Sur une stack déjà en
route :

```bash
docker exec hypostasia_web supervisorctl reread
docker exec hypostasia_web supervisorctl update
docker exec hypostasia_web supervisorctl status
```

**Attendu** : `celery_worker_juge_local RUNNING`. Le modèle de 7,7 Go n'est
chargé qu'à la **première tâche**, pas au démarrage du worker.

### Test 1 — le geste lance bien les deux juges

1. Ouvrir un article, cliquer « Vérifier les citations ».
2. **Attendu** : les verdicts Mistral arrivent en quelques secondes, comme
   avant.
3. Ouvrir le panneau de preuve d'un renvoi.
4. **Attendu** : « Second avis en cours… » sous la barre de production.
5. `docker compose logs -f web | grep juge_local` — le chargement, puis les
   paquets.
6. Après quelques minutes, rouvrir le panneau.
7. **Attendu** : « Les deux juges sont d'accord » (ou « divergent »), une
   seconde barre avec **son propre seuil** (38, pas 45) et le nom du juge.

### Test 2 — le second avis ne pilote rien

1. Noter l'état et le degré de production d'un renvoi.
2. Attendre le second avis, même très bas.
3. **Attendu** : l'état affiché et la barre de production sont **inchangés**.
   Le corps de l'article ne porte toujours aucun chiffre.

### Test 3 — Docling reste prioritaire

1. Lancer une vérification sur un article à beaucoup de citations.
2. Pendant que le juge local tourne, importer un PDF.
3. **Attendu** : la conversion Docling ne traîne pas visiblement. `top` dans le
   conteneur montre le processus celery du juge local à `NI 19`.
4. **C'est la mesure qui manque** : chronométrer une même conversion avec et
   sans juge local en parallèle.

### Test 4 — un re-clic n'empile rien

1. Cliquer « Vérifier les citations » deux fois de suite.
2. `docker exec -w /app hypostasia_web python manage.py shell -c "
   from hypostasis_extractor.models import ExtractionJob
   print(ExtractionJob.objects.filter(raw_result__contains={'est_second_avis': True}).count())"`
3. **Attendu** : **un seul** job de second avis tant que le premier tourne.

### Test 5 — l'installation ne déclenche rien

```bash
docker exec -w /app hypostasia_web python manage.py verifier_les_citations_etalons
```
**Attendu** : aucun job `est_second_avis` créé, aucun chargement de 7,7 Go dans
les journaux.

### Lire la campagne

```bash
docker exec -w /app hypostasia_web python manage.py comparer_les_deux_juges
```

Rend le nombre de citations comparables, le taux d'accord, l'**AUC** du second
juge, et **la liste des désaccords** — qui est le livrable réel de cette
campagne : c'est elle qui se relit à la main.

**Elle lit la base vivante** : un chiffre lu deux jours de suite peut différer
parce que des articles ont été revérifiés entre-temps. Ce n'est pas un défaut.

### Vérification navigateur — reste à faire

L'encadré du second avis et le titre d'accord sont **neufs** : leurs contrastes
ne sont **pas calculés** (ceux des barres le sont). Et rien n'a été vu dans un
navigateur — la stack ne prend aucun port de l'hôte. Restent à contrôler :
l'accord et le désaccord en clair **et** en sombre, et que le filet coloré ne
soit jamais le seul porteur du sens (le mot est dans le titre, c'est délibéré).
