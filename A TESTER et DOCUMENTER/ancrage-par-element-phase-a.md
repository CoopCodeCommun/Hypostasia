# Ancrage par element — phase A (modeles + signal d'etat)

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
