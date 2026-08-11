# Rapport — correction de coord_origin (prefixe d'enumeration)

## Defaut

`hypostasis_extractor/services/ingestion_docling.py:436` faisait
`str(getattr(boite, "coord_origin", "") or "")` sur un membre de
l'enumeration `CoordOrigin` de docling-core. `str()` d'un membre d'enum
rend `"CoordOrigin.BOTTOMLEFT"` (prefixe de classe compris) au lieu de
`"BOTTOMLEFT"`.

## Corrections apportees

### 1. Service (`hypostasis_extractor/services/ingestion_docling.py`)

- Nouvelle fonction `_coord_origin_en_chaine(coord_origin)` : rend
  `""` si `None`, `.value` si l'objet en a un (membre d'enum),
  `str(...)` sinon (deja une chaine). Commentaire bilingue explicitant
  pourquoi `.value` et pas `str()`.
- `_provenance_de_l_element` appelle desormais cette fonction au lieu de
  `str(getattr(...))`.

### 2. Commande de reparation

`core/management/commands/reparer_la_provenance_des_boites.py`, sur le
patron de `enrichir_la_provenance_audio.py` : en-tete LOCALISATION,
`--a-blanc`, bilan chiffre, commentaires bilingues, noms de variables
verbeux en francais.

Parcourt les `ElementDocument` dont `provenance != {}`, et pour chaque
boite dont `coord_origin` commence par `"CoordOrigin."`, retire ce
prefixe. Ne touche a rien d'autre (coordonnees, page_no, reste de la
provenance). Idempotente : relancee, elle rapporte 0 correction.

### 3. Tests (TDD)

- `hypostasis_extractor/tests/test_ingestion_docling.py` :
  `ProvenancePhysiqueTest.test_le_coord_origin_est_reduit_a_sa_valeur`
  — une fausse boite portant un vrai membre d'enum Python
  (`CoordOriginFeinte.BOTTOMLEFT`), assertion que la provenance rendue
  porte `"BOTTOMLEFT"`. Observee en echec avant le correctif
  (`'CoordOriginFeinte.BOTTOMLEFT' != 'BOTTOMLEFT'`), verte apres.
- `core/tests/test_reparation_provenance_boites.py` (nouveau fichier,
  6 tests) : reparation reelle, coordonnees inchangees, valeur deja
  propre laissee intacte, provenance sans boite laissee intacte,
  idempotence, `--a-blanc` n'ecrit rien. Observes en erreur avant la
  commande (`Unknown command`), verts apres.

## Resultats des tests

```
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_ingestion_docling \
    core.tests.test_reparation_provenance_boites
```

```
Ran 30 tests in 4.307s

OK (skipped=2)
```

(2 skips : `ConversionDoclingReelleTest`, conditionnee a `TESTS_DOCLING`,
non lancee — conforme aux consignes.)

## Reparation de la base de dev

### A blanc

```
MODE A BLANC — rien ne sera ecrit.
  element 1206 (page 9) : coord_origin corrige
  ... (11 elements, page 9)
Elements avec provenance examines : 32
Elements corriges                 : 11
Boites corrigees                   : 11
Boites deja propres                : 0
Rien n'a ete ecrit : relancer sans --a-blanc pour agir.
```

### Pour de vrai

```
  element 1206 (page 9) : coord_origin corrige
  ... (11 elements, page 9)
Elements avec provenance examines : 32
Elements corriges                 : 11
Boites corrigees                   : 11
Boites deja propres                : 0
```

### Verification d'idempotence (relance immediate)

```
Elements avec provenance examines : 32
Elements corriges                 : 0
Boites corrigees                   : 0
Boites deja propres                : 11
Rien a faire : toutes les boites etaient deja propres.
```

### Verification en base

```python
from core.models import ElementDocument
for e in ElementDocument.objects.exclude(provenance__page_no=None)[:3]:
    print(e.provenance['boites'][0])
```

```
{'b': 661.032, 'l': 46.0, 'r': 472.768, 't': 739.232, 'page_no': 1, 'coord_origin': 'BOTTOMLEFT'}
{'b': 602.688, 'l': 46.0, 'r': 203.376, 't': 617.488, 'page_no': 1, 'coord_origin': 'BOTTOMLEFT'}
{'b': 439.93, 'l': 46.0, 'r': 571.2, 't': 589.18, 'page_no': 1, 'coord_origin': 'BOTTOMLEFT'}
```

`coord_origin` vaut `'BOTTOMLEFT'`, sans prefixe de classe, sur les 11
boites reparees et sur toute nouvelle relance.

## Fichiers touches

- `hypostasis_extractor/services/ingestion_docling.py` (modifie)
- `hypostasis_extractor/tests/test_ingestion_docling.py` (modifie)
- `core/management/commands/reparer_la_provenance_des_boites.py` (nouveau)
- `core/tests/test_reparation_provenance_boites.py` (nouveau)

Aucune operation git effectuee. Aucun `ruff format` / `ruff check --fix`
lance. Aucune conversion Docling relancee.

## Correction post-revue (Important + mineur)

### Important — la commande plantait sur une boite abimee

`boite.get("coord_origin")` a la ligne 85 supposait chaque entree de
`boites` deja un dict. Une entree de forme inattendue (chaine, nombre) y
levait un `AttributeError` non capture et arretait toute la commande —
exactement au moment ou une base abimee en a le plus besoin.

Corrige dans `core/management/commands/reparer_la_provenance_des_boites.py` :
- `boites` non-liste (absente, None, ou d'un type inattendu) : element
  ignore, compte a part (`Elements a la provenance inattendue`).
- Une boite qui n'est pas un dict : ignoree, comptee a part (`Boites
  ignorees (pas un dict)`), les autres boites du meme element restent
  traitees.
- Extraction de la logique par-element dans
  `_corriger_les_boites_d_un_element`, qui ne leve jamais.

### Mineur — une boite sans coord_origin ne compte plus comme "propre"

Une boite dont `coord_origin` est absente, `None`, ou n'est pas une
chaine tombe desormais dans son propre compteur, `Boites sans
coord_origin (muettes)`, distinct de `Boites deja propres`.

### Tests ajoutes (TDD)

`core/tests/test_reparation_provenance_boites.py`, classe
`LaReparationSurvitAUneDonneeAbimeeTest` (3 tests) :
- `boites` valant une chaine -> pas de crash, compte dans le bilan.
- une boite parmi la liste n'est pas un dict -> pas de crash, l'autre
  boite (valide) est quand meme corrigee, comptee separement.
- une boite sans `coord_origin` -> `Boites deja propres : 0`,
  `Boites sans coord_origin (muettes) : 1`.

Observes en echec avant le correctif (2 `AttributeError`, 1 assertion
sur le libelle du bilan), verts apres.

### Resultat

```
docker exec hypostasia_web sh -c 'ps -eo cmd | grep "[m]anage.py test"'
```
→ vide, aucune suite en cours avant de lancer la mienne.

```
docker exec -w /app hypostasia_web uv run python manage.py test \
    core.tests.test_reparation_provenance_boites
```
```
Ran 9 tests in 0.113s

OK
```

Commande non relancee sur la base de dev (deja reparee et idempotente,
conforme a la consigne). Fichiers touches : `core/management/commands/
reparer_la_provenance_des_boites.py` et `core/tests/
test_reparation_provenance_boites.py` (modifies). Aucune operation git.

## Correction post-re-revue — provenance elle-meme non-dict

`(element.provenance or {}).get("boites")` ne protegeait que le cas
falsy (None, {}). Une `provenance` valant une LISTE ou une CHAINE non
vide est truthy : `or {}` ne s'applique pas, et `.get()` levait le meme
`AttributeError`, un niveau au-dessus des boites.

Corrige en ajoutant `if not isinstance(provenance, dict): ... continue`
avant tout acces `.get()`, dans la meme categorie de bilan que les
boites (`Elements a la provenance inattendue`) — pas de nouveau
compteur, comme demande.

Test ajoute : `test_une_provenance_qui_n_est_pas_un_dict_ne_fait_pas_planter`
(provenance = liste non vide), observe en `AttributeError: 'list' object
has no attribute 'get'` avant le correctif, vert apres.

```
docker exec hypostasia_web sh -c 'ps -eo cmd | grep "[m]anage.py test"'
```
→ vide.

```
docker exec -w /app hypostasia_web uv run python manage.py test \
    core.tests.test_reparation_provenance_boites
```
```
Ran 10 tests in 0.111s

OK
```

Rien d'autre touche : le coeur (correction de `coord_origin`),
l'idempotence, `--a-blanc`, et les compteurs existants restent
inchanges. Aucune operation git.
