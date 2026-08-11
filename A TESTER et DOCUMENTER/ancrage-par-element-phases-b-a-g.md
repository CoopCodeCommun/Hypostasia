# Ancrage par element — phases B, C, E, F, G

Suite de `ancrage-par-element-phase-a.md`. Le coeur algorithmique du moteur
ELEMENT est ecrit et teste. **Aucun pipeline ne cree encore d'element** : la
phase D (ingestion Docling) reste a faire.

## Ce qui a ete fait

| Phase | Fichier | Ce que ca fait |
|---|---|---|
| B | `services/ancrage.py` | Traduit un span LangExtract en portions d'ancrage |
| C | `services/chunking.py` | Groupe les elements en chunks sans jamais en couper un |
| E | `services/reconciliation.py` | Repositionne les portions apres une correction |
| F | `services/moteur_structure.py` | Scinder, fusionner, renumeroter |
| G | `services/masquage.py` | Masquer, demasquer |
| G | `services/reingestion.py` | Reconnaitre le contenu inchange par empreinte |

## Tests a realiser

### Test 1 : la suite automatique

```bash
docker exec hypostasia_web uv run python manage.py test hypostasis_extractor
```

Attendu : `OK`, environ 167 tests.

### Test 2 : le cycle complet, a la main

```bash
docker exec hypostasia_web uv run python manage.py shell
```

```python
from core.models import Page, ElementDocument, EtatElement, empreinte_du_texte
from hypostasis_extractor.models import (
    ExtractionJob, ExtractedEntity, AncrageExtraction, EtatAncrage,
)
from hypostasis_extractor.services.chunking import construire_les_chunks
from hypostasis_extractor.services.ancrage import decouper_le_span_en_portions_par_element
from hypostasis_extractor.services.moteur_structure import scinder_un_element, fusionner_deux_elements
from hypostasis_extractor.services.masquage import masquer_un_element, demasquer_un_element

page = Page.objects.create(
    url="http://essai.local/manuel", html_original="x",
    html_readability="x", text_readability="x", content_hash="essai_manuel",
)

def ajouter(ordre, texte):
    return ElementDocument.objects.create(
        page=page, ordre=ordre, label="text", texte=texte,
        empreinte_contenu=empreinte_du_texte(texte),
    )

premier = ajouter(0, "L'IA ne doit pas remplacer :")
second = ajouter(1, "le jugement des personnes concernees")

# 1. Chunking : un seul chunk, avec sa table d'offsets
chunk = construire_les_chunks([premier, second])[0]
print("texte du chunk :", repr(chunk["texte"]))
print("offsets        :", chunk["offsets"])

# 2. Un span qui traverse les deux elements -> deux portions
portions = decouper_le_span_en_portions_par_element(
    span_dans_le_chunk=(0, len(chunk["texte"])),
    elements_du_chunk=chunk["elements"],
    offsets_des_elements_dans_le_chunk=chunk["offsets"],
)
print("portions :", len(portions))   # attendu : 2

job = ExtractionJob.objects.create(page=page, name="essai", prompt_description="essai")
extraction = ExtractedEntity.objects.create(
    job=job, extraction_text="l'extraction traverse", start_char=0, end_char=20,
)
for portion in portions:
    AncrageExtraction.objects.create(extraction=extraction, **portion)

premier.refresh_from_db()
print("etat du premier :", premier.etat)   # attendu : analyse

# 3. Scission : la portion du premier element est coupee en deux
scinder_un_element(premier, 5)
print("portions apres scission :", extraction.ancrages.count())   # attendu : 3

# 4. Masquage puis demasquage : aller-retour complet
masquer_un_element(second, justification="essai")
second.refresh_from_db()
print("second masque :", second.masque, "| etat :", second.etat)  # attendu : True | libre

resultat = demasquer_un_element(second)
second.refresh_from_db()
print("rattachees :", resultat["portions_rattachees"], "| etat :", second.etat)

# Nettoyage / Cleanup
extraction.delete(); page.elements.all().delete(); job.delete(); page.delete()
```

### Test 3 : la re-ingestion d'un pad qui grossit

```python
from hypostasis_extractor.services.reingestion import reconcilier_les_elements_par_empreinte

# ... page avec 3 comptes-rendus deja crees ...
resultat = reconcilier_les_elements_par_empreinte(page, [
    {"texte": "Compte-rendu d'avril.", "label": "text"},
    {"texte": "Compte-rendu de janvier.", "label": "text"},
    {"texte": "Compte-rendu de fevrier.", "label": "text"},
    {"texte": "Compte-rendu de mars.", "label": "text"},
])
print(len(resultat["inchanges"]), "inchanges")   # attendu : 3
print(len(resultat["apparus"]), "apparu")        # attendu : 1
```

Seul l'element apparu devra partir en analyse : c'est tout l'interet.

## Deux points a trancher avant la phase D

### 1. Plafond des tres gros elements
La regle « on ne coupe jamais un element » est obligatoire (section 4.1). Un
tableau Docling serialise de 30 000 caracteres part donc entier dans son chunk :
cout proportionnel, et risque de troncature a `max_output_tokens` qui ferait
perdre les extractions apres le point de coupure. Le parametre
`decalages_dans_l_element` de `services/ancrage.py` est deja pret pour un
decoupage des tres gros elements — il ne manque que la decision du seuil.

### 2. Edition concurrente pendant une analyse
Si quelqu'un raccourcit un element pendant qu'un job d'analyse tourne, la garde
de `services/ancrage.py` leve une `ValueError` et fait tomber le job entier. Il
faudra l'attraper par extraction et marquer la portion `DETACHEE`, plutot que de
perdre toute l'analyse.

## Deux changements de schema a valider

1. **Contraintes d'unicite DEFERRABLE** (`core.0037`, `hypostasis_extractor.0032`).
   Sans elles, le moteur de structure est incodable. Effet de bord : les
   violations d'unicite remontent au commit et non au `save()`, et `ON CONFLICT`
   / `bulk_create(ignore_conflicts=True)` sont refuses par PostgreSQL sur ces
   deux tables.

2. **Journal rattache a la Page** (`core.0038`). Sans ce changement, scinder puis
   refusionner effacait la trace de la scission.

## Compatibilite

Le moteur ANCIEN n'est toujours pas touche. Aucun ancien champ retire ni
modifie. Les tests `CoexistenceDesDeuxMoteursTest` echouent si quelqu'un en
retire un par megarde.
