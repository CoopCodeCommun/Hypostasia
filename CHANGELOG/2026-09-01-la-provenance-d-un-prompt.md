# La provenance d'un prompt / Prompt provenance

**Date :** 2026-09-01
**Migration :** **Oui** — `hypostasis_extractor/0037_la_provenance_d_une_production`
(appliquée à la base de dev) :
`docker exec -w /app hypostasia_web python manage.py migrate hypostasis_extractor`

## Résumé / Summary

**Quoi / What :** une table dédiée, `ProvenanceDeProduction`, enregistre pour
chacun des **cinq** chemins de production LLM l'empreinte SHA-256 du prompt
réellement assemblé, sa longueur, le modèle, l'analyseur et sa version, et les
identifiants d'extractions montrés. Trois assembleurs purs rendent désormais ce
prompt sans appeler aucun modèle. La passe de nuit laisse enfin sa trace.
/ A dedicated table records, for each of the five LLM production paths, the
SHA-256 of the prompt actually assembled, plus model, analyzer and shown
extractions. Three pure assemblers return that prompt without calling anything.

**Pourquoi / Why :** mesuré le 1er septembre 2026 sur la base de dev (154 jobs),
`prompt_description` portait **onze formes différentes** selon l'appelant —
tantôt une étiquette de 38 caractères, tantôt le préambule système entier
(4 999 car.), **jamais le prompt réellement envoyé** : sur un job de synthèse
mesuré, 75 928 caractères assemblés contre 1 239 enregistrés. `analyseur_version`
valait `NULL` sur **154 jobs sur 154**, et `AnalyseurVersion.objects.count()`
valait **0** — le champ ne pouvait pas être rempli, rien ne créait de version. Et
**25 des 30 tours de wiki** portaient `job=None` **et** `fait_par=None` : rien ne
disait quel modèle avait écrit un article de nuit.
/ Eleven different shapes, never the prompt actually sent; zero analyzer
versions in base; 25 of 30 wiki rounds naming no writer at all.

### Les cinq chemins tracés / The five traced paths

| Chemin | Où | Ce que l'empreinte couvre |
|---|---|---|
| `analyse` | `services/analyse_par_element.py` | **ce que nous composons** — le préambule et les exemples, pas le message final : LangExtract l'assemble hors de notre vue, et prétendre le contraire serait faux |
| `synthese_note` | `front/tasks.py` (`synthetiser_page_task`) | le message exact envoyé |
| `wiki` | `front/tasks.py` (`produire_un_wiki_task`) | le message exact envoyé |
| `synthese_dirigee` | `front/tasks.py` | le message exact envoyé |
| `maj_wiki` | `front/tasks.py` (les deux appelants, humain **et** nuit) | le message exact envoyé |

La provenance s'écrit **avant** l'appel : un prompt dont le modèle ne revient pas
a bel et bien été envoyé, et sa trace répond encore à « qu'a-t-on demandé, et
avec quel préambule ? ».

### L'ordre des notes est devenu canonique / A canonical note order

`_blocs_d_extractions_par_note` trie désormais par clé. Sans cela, l'empreinte
aurait dérivé toute seule : `notes_du_perimetre_d_un_wiki` rend un queryset
`.distinct()` **sans `order_by`**, `SyntheseDirigee.notes_du_perimetre` est une
M2M sans `Meta.ordering`, et `Page` n'a aucun ordre par défaut — la base était
libre de rendre les notes dans l'ordre qu'elle voulait, et « le prompt a-t-il
changé entre deux tours ? » aurait répondu oui à tort.

### Les trois trous du versionnage sont bouchés / Three versioning holes closed

- créer un analyseur écrit sa **v1** ;
- `partial_update` versionne les **quatre champs qui décident de ce qui part au
  modèle** (`type_analyseur`, `est_par_defaut`, `inclure_extractions`,
  `inclure_texte_original`) — et **seulement quand la valeur change** : le bouton
  « Sauver » de l'éditeur repost nom et description à chaque clic, et un snapshot
  pèse ~24 Ko (mesuré : 23 873 octets pour « Hypostasia ») ;
- les fixtures posent une v1 **après** les pièces et les exemples, gardée par
  « aucune version n'existe » — elles tournent à chaque démarrage de conteneur.

### Ce qu'une relecture adverse du code livré a corrigé / What an adversarial review fixed

Trois défauts trouvés **après** la première livraison, tous vérifiés dans le code :

- **L'empreinte du chemin `analyse` mentait.** Elle sérialisait le **nom** des
  exemples few-shot — qui ne part jamais au modèle — et **omettait leurs
  extractions et leurs attributs**, qui partent. Modifier une extraction
  d'exemple, geste qui crée pourtant une `AnalyseurVersion`, ne changeait donc
  pas l'empreinte : « le prompt-source a-t-il changé ? » répondait **non à
  tort**. Elle se calcule maintenant sur l'objet rendu par
  `_construire_exemples_langextract` — celui qui part vraiment.
- **Un applieur qui refuse la nuit laissait une fiche menteuse.** Le job naissait
  `completed` **avant** l'application ; si l'applieur refusait ensuite (deux
  titres en collision, un article sans citation), la fiche disait `completed`
  alors que rien n'avait été appliqué, **une seconde fiche** naissait pour le
  même tour, et la provenance de ce tour n'était **jamais** ancrée — précisément
  là où « quel prompt est parti ? » compte le plus.
- **`collectstatic` n'avait pas été passé** après la modification du JS. Le
  bundle servi depuis `staticfiles/` ne portait pas la troisième option, malgré
  le `?v=42`. Invariant du projet, corrigé.

Plus deux corrections moyennes : la provenance de nuit s'ancre sur **le tour de
ce job** (`filter(job=job)`) et non sur « le dernier tour », qu'un tour manuel
concurrent aurait pu être ; et une analyse relancée écrit **une trace par
envoi** — c'est ce qu'elle fait vraiment — ce que la docstring et le test disent
désormais.

### Un point à trancher, pas tranché ici / One open question

`ExtractionJob.analyseur_version` reste sans écrivain. La provenance porte
désormais cette information (`ProvenanceDeProduction.analyseur_version`), et
remplir les deux ferait diverger deux copies de la même chose. **Le champ est
donc soit à retirer, soit à documenter comme remplacé** — c'est une décision du
mainteneur, pas de la session.

### La passe de nuit : son job est une FICHE DE PRODUCTION, pas une tâche
### / The nightly pass: a production sheet, not a task

Trois décisions, chacune prise contre un défaut vérifié dans le code.

- **Il n'existe jamais « en cours ».** Il est écrit après coup, avec son issue
  (`completed` ou `error`). Trois vues prennent « le dernier job en cours de
  cette page » pour décider ce qu'elles affichent (`LireViewSet.retrieve`,
  `previsualiser_analyse`, `drawer_contenu`) : un job de nuit en vol ferait lire
  « une analyse tourne déjà » sur un article que personne n'analyse. Et
  `_verifier_et_nettoyer_job_bloque` marque en erreur tout job `processing` sans
  battement depuis **5 minutes** — or un tour de nuit ne bat pas le cœur, et un
  appel de rédaction dépasse 5 minutes : le job aurait été tué en vol, avec le
  message « Vérifiez que le worker Celery tourne », qui aurait été faux.
- **Il n'allume aucun badge.** Le menu des tâches l'ignore
  (`_jobs_qui_s_adressent_a_quelqu_un`), parce que la nuit ne s'adresse à
  personne. Sans cette exclusion le badge se serait allumé chaque matin — une
  fois par wiki modifié et par propriétaire — **et le clic ne l'aurait pas
  éteint** : le lien du menu mène à `/lire/<page>/?marquer_lue=…`, or
  `LireViewSet.retrieve` redirige toute page de wiki vers `/wikis/<id>/`
  **avant** de lire `marquer_lue`, en jetant la chaîne de requête. Seul « tout
  marquer lu » en serait venu à bout.
- **Il ne réveille personne.** Pas de `demandeur_id`, et le chemin de nuit ne
  passe ni par `_terminer_un_job_d_article` ni par `_echouer_un_job_d_article` —
  les deux seuls endroits qui appellent `notifier_tache_terminee` pour un
  article. Le récapitulatif du matin raconte la nuit à leur place.

Son marqueur `est_maj_wiki_de_nuit` est distinct de `est_maj_wiki` : les vues
`proposition` et `appliquer` (`front/views_synthese.py`) adressent par son id
n'importe quel job `est_maj_wiki` de la page, et un `appliquer` forgé sur un job
de nuit écrirait un tour manuel fantôme, signé par l'utilisateur, avec zéro
opération.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | `CheminDeProduction` et `ProvenanceDeProduction` |
| `hypostasis_extractor/migrations/0037_…` | création de la table |
| `hypostasis_extractor/services/provenance.py` | **neuf** — `empreinte_d_un_prompt()`, `derniere_version_de()`, `analyseur_de_redaction()`, `enregistrer_la_provenance()` (qui ne lève jamais : l'article compte plus que son journal) |
| `hypostasis_extractor/services/analyse_par_element.py` | `_tracer_l_analyse()` — une seule provenance par job, jamais par chunk |
| `hypostasis_extractor/views.py` | la création écrit sa v1 ; `partial_update` versionne les quatre champs qui décident de ce qui part |
| `front/services/fixtures_analyseurs.py` | `_poser_la_v1_si_elle_manque()` |
| `front/tasks.py` | les trois assembleurs purs ; `_tracer_la_production()` ; `_blocs_d_extractions_par_note()` trie par clé ; `_ecrire_le_job_d_un_tour_de_nuit()` ; `construire_la_proposition_d_operations()` rend sa provenance en troisième élément |
| `front/views_taches.py` | `_jobs_qui_s_adressent_a_quelqu_un()` — les quatre requêtes du menu (compteur de non-lues, état d'erreur, liste déroulante, « tout marquer lu ») passent par lui. `__contains` et non le lookup direct : `.exclude()` sur un lookup JSONField ordinaire écarte aussi les lignes où la clé est absente |
| `front/tests/test_l_assemblage_des_prompts_d_article.py` | **neuf** — 12 tests |
| `hypostasis_extractor/tests/test_la_provenance_d_une_production.py` | **neuf** — 12 tests |
| `hypostasis_extractor/tests/test_le_versionnage_d_un_analyseur.py` | **neuf** — 8 tests |
| `front/tests/test_la_passe_de_nuit_des_wikis.py` | `LaNuitLaisseLaTraceDeCeQuiAEcritTest` — 7 tests |

---

## Comment tester (à la main) / Manual test

### Test 1 — un tour de nuit nomme son rédacteur

1. Avoir au moins un wiki avec des extractions non reprises (sinon la passe
   n'a aucune raison de le reprendre).
2. Lancer la passe :
   `docker exec -w /app hypostasia_web python manage.py mettre_a_jour_les_wikis`
3. Vérifier en base que le dernier tour porte un job, et que ce job porte le
   modèle du rôle rédacteur :

```bash
docker exec -w /app hypostasia_web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','hypostasia.settings')
django.setup()
from core.models import TourDeWiki
for tour in TourDeWiki.objects.filter(fait_par__isnull=True)[:5]:
    modele = tour.job.ai_model.name if tour.job and tour.job.ai_model else None
    print(tour.pk, tour.motif, '| job:', tour.job_id, '| modele:', modele)
"
```

### Test 2 — la nuit ne réveille personne et n'allume aucun badge

1. Ouvrir le menu des tâches (la cloche) avec le compte propriétaire du carnet,
   noter le compteur.
2. Lancer la passe de nuit.
3. **Attendu** : le bouton ne change ni de couleur ni de compteur, pendant la
   passe comme après. Le menu déroulant ne montre **aucune** ligne pour le tour
   de nuit — l'article, lui, la montre dans son dépliant « Historique ».

### Test 3 — l'empreinte ne bouge pas toute seule

1. Ouvrir un carnet, produire un wiki.
2. Relancer la production **sans rien changer**.
3. **Attendu** : les deux provenances portent la **même** empreinte.

```bash
docker exec -w /app hypostasia_web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','hypostasia.settings')
django.setup()
from hypostasis_extractor.models import ProvenanceDeProduction
for p in ProvenanceDeProduction.objects.all()[:10]:
    print(p.chemin, p.empreinte[:12], p.longueur, 'car.',
          '| modele:', p.modele.name if p.modele else None,
          '| montrees:', len(p.extractions_montrees))
"
```

4. Modifier une pièce de prompt de l'analyseur de synthèse, reproduire :
   l'empreinte doit **changer**.

### Test 4 — un échec se nomme aussi

1. Rendre le modèle rédacteur injoignable (une `base_url` fausse sur l'`AIModel`
   du rôle, ou une clé d'API absente).
2. Lancer la passe.
3. **Attendu** : le dépliant « Historique » de l'article montre un tour d'échec ;
   en base, ce tour porte un `job` dont le `status` vaut `error` et dont
   `error_message` reprend le message du modèle.
