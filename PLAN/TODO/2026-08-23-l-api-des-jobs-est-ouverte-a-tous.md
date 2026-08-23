# L'API d'extraction est ouverte à tous — PRIORITAIRE

**Constaté et mesuré le 23 août 2026. Rien n'est codé.**
**C'est la note à traiter en premier : le reste de la série y déverserait des données.**

## Ce que le code fait aujourd'hui

Trois ViewSets de `hypostasis_extractor/views.py` portent
`permission_classes = [permissions.AllowAny]`, sans aucun filtre par propriétaire :

| Ligne | ViewSet |
|---|---|
| `views.py:96` | `ExtractionJobViewSet` — `list()` ne filtre que par `page` et `status` ; `retrieve()` fait un `get_object_or_404` nu |
| `views.py:187` | `ExtractedEntityViewSet` |
| `views.py:268` | `ExtractionExampleViewSet` |

`ExtractionJobDetailSerializer` expose `prompt_description`, `raw_result` **et toutes
les `entities`** de la page.

## Ce qui a été mesuré

Requêtes lancées depuis le conteneur `nginx`, **sans aucun cookie de session**, avec
`Host: beta.hypostasia.org` (la valeur de `DOMAIN` dans le `.env` de cette machine) :

| Endpoint | Réponse anonyme | Contenu |
|---|---|---|
| `/api/extraction-jobs/` | **200** — 11 107 o | les 37 jobs de la base |
| `/api/extraction-jobs/4/` | **200** — 17 487 o | le prompt entier + **25 extractions**, verbatim complet |
| `/api/extracted-entities/` | **200** — **375 122 o** | **toutes** les extractions de la base |
| `/api/extraction-examples/` | 200 | `[]` — vide sur cette base, mais ouvert |
| `/api/analyseurs/` | 403 | protégé |
| `/api/pages/` | 401 | protégé |
| `/api/sidebar/` | 200 — 176 o | un partial « aucune analyse trouvée » |

**C'est routé dans les deux topologies** : `nginx/dev.conf:63` envoie `location /`
vers `web:8000`, `nginx/default.conf:49` vers `web:8001`. Rien ne dépend de `DEBUG`.

## Ce que ça viole

`AGENTS.md`, section « Les invariants » :

> **Aucun `DEFAULT_PERMISSION_CLASSES`** : tout endpoint DRF est `AllowAny` par
> défaut. Contrôle explicite dans chaque vue, et **doctrine du 404, jamais 403**.

L'invariant est respecté sur sa première moitié — le contrôle est bien censé être
explicite — et **absent** sur ces trois vues, qui n'en font aucun. Le 403 de
`/api/analyseurs/` est par ailleurs un second écart, plus bénin : la doctrine
demande un 404.

## Ce qui casse si on ne fait rien

**Ça ne casse pas : ça fuit, dès maintenant.** N'importe qui connaissant l'adresse
lit le corpus extrait de tous les carnets, publics comme privés, avec le verbatim
de chaque passage cité et les prompts.

Et la série de notes du 23 août aggraverait mécaniquement la fuite : la note
« la provenance d'un prompt » y ajouterait le prompt assemblé, soit 25 000 à
80 000 caractères de corpus **par job** — l'article entier, les extractions du
périmètre, et la consigne de forme.

## Ce qui est voulu

1. **Un contrôle explicite dans chacune des trois vues**, sur le modèle de ce qui
   existe déjà dans `front/` (`_exiger_authentification`, `_acces_ou_refus`) : un
   job, une extraction, un exemple ne sont lisibles que par qui a accès à la note
   qui les porte.
2. **Doctrine du 404** : un objet auquel on n'a pas droit n'existe pas.
3. **Un test par vue**, qui interroge en anonyme et exige un 404 — sinon la
   régression reviendra sans bruit.
4. Vérifier au passage `SidebarViewSet` (`core/views.py:657`) : il rend du HTML en
   `AllowAny`, il faut dire si c'est voulu (l'extension navigateur) ou non.

## Ce qu'il faut mesurer

Rien à facturer ici : la vérification est un simple appel HTTP anonyme, à faire
**avant et après**, sur les sept endpoints du tableau ci-dessus. Le test automatique
doit reproduire exactement ces appels.

## Coût de mise en œuvre

Trois vues, un helper de permission déjà écrit ailleurs, trois à six tests.
Une demi-journée, sans dépendance à aucune autre note de la série.
