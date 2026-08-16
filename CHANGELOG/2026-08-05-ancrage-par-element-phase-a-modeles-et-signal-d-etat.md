# Ancrage par element, phase A : modeles et signal d'etat

**Date :** 2026-08-05
**Migration :** Oui

**Quoi / What :** ajout du socle de donnees du moteur ELEMENT — `ElementDocument`,
`AncrageExtraction` (ancre multi-elements), `ElementOperation`, le champ
`SourceLink.ancrage_source`, et le signal `recalculer_etat_de_l_element`.
Implemente la phase A de `SPEC-ancrage-par-element-v2.md` (section 11).

**Pourquoi / Why :** l'ancrage actuel se fait par offsets de caracteres dans un
texte plat. Des qu'un texte est corrige, les positions glissent et le lien avec
le passage source est perdu. Le nouveau moteur ancre dans un element de document
identifie par un UUID stable, via une table de liaison ordonnee qui permet a une
extraction de couvrir plusieurs elements — mesure : une extraction d'une phrase
enjambe deja deux elements dans 7,5 % des cas, une extraction de deux phrases
dans 76 % des cas.

**Etat / Status :** socle de donnees uniquement. Aucun pipeline ne cree encore
d'element : le moteur d'intersection (phase B), le chunking (phase C) et
l'ingestion (phase D) restent a ecrire. Le nouveau moteur n'est donc lu par
aucun code existant.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | + `empreinte_du_texte()`, `EtatElement`, `ElementDocument`, `TypeOperationElement`, `ElementOperation` ; + champ `SourceLink.ancrage_source` ; imports `hashlib`, `re`, `uuid` |
| `hypostasis_extractor/models.py` | + `EtatAncrage`, `AncrageExtraction` (table de liaison M2M ordonnee) |
| `hypostasis_extractor/signals.py` | + `recalculer_etat_de_l_element()` et ses trois recepteurs (ancrage, commentaire, masquage d'extraction) |
| `hypostasis_extractor/tests/` | Nouveau package + `test_ancrage_m2m.py` (37 tests) |
| `core/migrations/0035_elementdocument_elementoperation.py` | Creation des modeles |
| `core/migrations/0036_sourcelink_ancrage_source_and_more.py` | FK croisees + contrainte d'unicite |
| `hypostasis_extractor/migrations/0031_ancrageextraction.py` | Creation de la table de liaison |

### Coexistence des deux moteurs / Both engines coexist
Conformement a la section 9 de la spec, **aucun ancien champ n'est retire ni
modifie**. `ExtractedEntity.start_char` / `end_char` et
`SourceLink.start_char_source` / `end_char_source` restent en place et
fonctionnent comme avant. Les trois migrations sont purement additives
(`CreateModel`, `AddField`, `AddConstraint`) — aucun `RemoveField`, aucun
`AlterField`, aucun `RunPython`. Trois tests de non-regression verifient
explicitement que les anciens champs existent toujours.

### Regle de calcul de l'etat / State computation rule
Une portion d'ancrage ne compte dans l'etat d'un element que si son extraction
n'est **pas masquee** et que son ancrage n'est **pas detache**. Consequence
voulue : un element dont toutes les portions sont detachees redevient `LIBRE`,
donc librement editable. Il n'y a pas d'etat `SCELLE` — le scellement a ete
abandonne (YAGNI).

### Migration
- **Migration necessaire / Migration required :** Oui
- `core.0035`, `hypostasis_extractor.0031`, `core.0036` — dans cet ordre, gere
  automatiquement par les dependances.
- Commande : `docker exec hypostasia_web uv run python manage.py migrate`
- **Sans effet sur les donnees existantes** : uniquement des tables nouvelles et
  une colonne nullable sur `SourceLink`.

---

Implemente la phase A de `SPEC-ancrage-par-element-v2.md` (section 11).
Socle de donnees uniquement : aucun pipeline ne cree encore d'element.

## Ce qui a ete fait

### Modifications

| Fichier | Changement |
|---|---|
| `core/models.py` | `empreinte_du_texte()`, `EtatElement`, `ElementDocument`, `TypeOperationElement`, `ElementOperation`, champ `SourceLink.ancrage_source` |
| `hypostasis_extractor/models.py` | `EtatAncrage`, `AncrageExtraction` |
| `hypostasis_extractor/signals.py` | `recalculer_etat_de_l_element()` + 3 recepteurs |
| `hypostasis_extractor/tests/test_ancrage_m2m.py` | 37 tests |

### Les trois idees a retenir

1. **L'ancre est multiple.** Une extraction ne pointe plus un offset dans le
   texte de la page. Elle pointe une ou plusieurs lignes `AncrageExtraction`,
   chacune disant « dans CET element, du caractere X au caractere Y ».

2. **L'identifiant ne bouge jamais.** `ElementDocument.identifiant_stable` est
   un UUID. Meme si on coupe l'element en deux, meme si l'ordre change, les
   ancres continuent de pointer au bon endroit.

3. **L'etat est calcule, jamais saisi.** `ElementDocument.etat` vaut `LIBRE`,
   `ANALYSE` ou `DEBATTU`. Un signal le recalcule. Personne ne l'ecrit a la main.

## Tests a realiser

### Test 1 : la suite automatique passe

```bash
docker exec hypostasia_web uv run python manage.py test hypostasis_extractor.tests.test_ancrage_m2m
```

Attendu : `Ran 37 tests` puis `OK`.

### Test 2 : verifier que la prod n'a pas bouge

Le nouveau moteur ne doit rien changer aux pages existantes.

```bash
# Les anciens champs sont toujours la
docker exec hypostasia_web uv run python manage.py shell -c "
from hypostasis_extractor.models import ExtractedEntity
print('start_char present :', hasattr(ExtractedEntity, 'start_char'))
print('extractions existantes :', ExtractedEntity.objects.count())
print('extractions avec une ancre :', ExtractedEntity.objects.filter(ancrages__isnull=False).count())
"
```

Attendu : `start_char present : True`, le nombre d'extractions inchange, et
**0 extraction avec une ancre** (aucun pipeline ne les cree encore).

### Test 3 : le cycle d'etat, a la main

```bash
docker exec hypostasia_web uv run python manage.py shell
```

```python
from core.models import Page, ElementDocument, EtatElement, empreinte_du_texte
from hypostasis_extractor.models import (
    ExtractionJob, ExtractedEntity, AncrageExtraction,
    CommentaireExtraction, EtatAncrage,
)
from django.contrib.auth import get_user_model

page = Page.objects.first()
element = ElementDocument.objects.create(
    page=page, ordre=9000, label="text",
    texte="Un paragraphe pour l'essai manuel.",
    empreinte_contenu=empreinte_du_texte("Un paragraphe pour l'essai manuel."),
)
print("1. a la creation :", element.etat)          # attendu : libre

job = ExtractionJob.objects.create(page=page, name="essai", prompt_description="essai")
extraction = ExtractedEntity.objects.create(
    job=job, extraction_text="Un paragraphe", start_char=0, end_char=13,
)
portion = AncrageExtraction.objects.create(
    extraction=extraction, element=element,
    ordre_dans_extraction=0, debut_dans_element=0, fin_dans_element=13,
)
element.refresh_from_db()
print("2. apres ancrage :", element.etat)          # attendu : analyse

CommentaireExtraction.objects.create(
    entity=extraction, user=get_user_model().objects.first(),
    commentaire="Essai manuel.",
)
element.refresh_from_db()
print("3. apres commentaire :", element.etat)      # attendu : debattu

portion.etat_ancrage = EtatAncrage.DETACHEE
portion.save(update_fields=["etat_ancrage"])
element.refresh_from_db()
print("4. ancre detachee :", element.etat)         # attendu : libre

# Nettoyage / Cleanup
extraction.delete(); element.delete(); job.delete()
```

### Test 4 : un element porteur ne se supprime pas

```python
# Doit lever ProtectedError tant qu'une portion pointe l'element
element.delete()
```

## Ce qui N'EST PAS fait

| Manque | Phase prevue |
|---|---|
| `decouper_le_span_en_portions_par_element()` (section 2.3) | B |
| Chunking aligne sur les elements (section 4.1) | C |
| Pipeline Docling -> elements -> ancres (section 4) | D |
| Reconciliation apres correction (section 6) | E |
| Scission / fusion / masquage (section 5) | F, G |
| Flag `Page.moteur` ANCIEN/ELEMENT (section 9) | reporte, decision prise en phase A |

Les cinq tests nommes dans la section 10 de la spec pour `test_ancrage_m2m.py`
dependent tous de la phase B ou de la phase E. Ils sont a ajouter dans ce meme
fichier quand ces phases seront ecrites. Le detail est en tete de
`test_ancrage_m2m.py`.

## Compatibilite

Les deux moteurs coexistent (section 9 de la spec). Aucun ancien champ n'est
retire ni modifie. Les trois migrations sont purement additives. Trois tests de
non-regression (`CoexistenceDesDeuxMoteursTest`) echouent si quelqu'un retire
un ancien champ par megarde.

Le signal `recalculer_etat_apres_masquage_d_extraction` s'execute a chaque
sauvegarde d'`ExtractedEntity`. Deux gardes evitent un cout inutile sur les
analyses en masse : sortie immediate a la creation, et sortie immediate si
`update_fields` est fourni sans contenir `masquee`.

