# Ancrage par élément — phases B, C, E, F, G

**Date :** 2026-08-05
**Migration :** Oui

## 2026-08-05 — Ancrage par element, phases B, C et E : intersection, chunking, reconciliation

**Quoi / What :** les trois algorithmes du moteur ELEMENT qui ne dependent
d'aucune decision d'interface.
- **Phase B** — `services/ancrage.py` : transforme un span rendu par LangExtract
  (des offsets dans le texte d'un chunk) en portions d'ancrage, une par element
  traverse.
- **Phase C** — `services/chunking.py` : regroupe les elements en chunks sans
  jamais couper un element en deux.
- **Phase E** — `services/reconciliation.py` : repositionne les portions apres
  une correction de texte, et serialise les corrections concurrentes.

**Pourquoi / Why :** ce sont les trois endroits ou une ancre peut devenir fausse.
Un chunk qui coupe un element fait lire une demi-phrase au LLM ; un span mal
traduit ancre au mauvais endroit ; une correction de texte fait glisser toutes
les positions. Chacun des trois refuse de deviner : quand la position n'est pas
certaine, la portion est marquee `DETACHEE` plutot que placee au hasard.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/ancrage.py` | Decoupage d'un span en portions + table des offsets |
| `hypostasis_extractor/services/chunking.py` | Construction des chunks alignes sur les elements |
| `hypostasis_extractor/services/reconciliation.py` | Repositionnement des portions + verrou de concurrence |
| `hypostasis_extractor/tests/test_chunking_par_element.py` | 23 tests |
| `hypostasis_extractor/tests/test_reconciliation.py` | 23 tests |

### Fichiers deplaces / Moved files
| Avant / Before | Apres / After | Raison / Reason |
|---|---|---|
| `hypostasis_extractor/services.py` | `hypostasis_extractor/services/__init__.py` | La spec impose un paquet `services/`. Les imports existants restent valides ; les imports relatifs internes sont passes de `from .models` a `from ..models` |
| `hypostasis_extractor/tests.py` | `hypostasis_extractor/tests/test_modeles_extraction.py` | Un module et un paquet de meme nom empechaient `manage.py test` de decouvrir les tests |

### Ecarts avec la spec, et pourquoi / Deviations from the spec
| Ou / Where | Ecart / Deviation | Raison / Reason |
|---|---|---|
| section 2.3 | Parametre `decalages_dans_l_element` ajoute | La table d'offsets de la spec dit ou un morceau d'element est DANS LE CHUNK, jamais ou il est DANS L'ELEMENT. Sans cette information, une portion d'un element trop gros serait ancree a 0 |
| section 2.3 | Un element absent de la table leve une erreur au lieu d'etre saute | Un saut silencieux produit une ancre incomplete que rien en aval ne detecte : la portion du milieu disparait et la numerotation se resserre |
| section 4.1 | Taille calculee par somme des longueurs, pas par `position_debut/fin_dans_page` | Ces attributs n'existent pas sur `ElementDocument`. La somme mesure en plus exactement ce que le budget veut borner : le texte reellement envoye au LLM |
| section 4.1 | Cle `offsets` ajoutee a chaque chunk | La section 2.3 dit reutiliser « la meme table que celle utilisee pour construire le chunk » — table que le chunker de la spec ne produisait pas |
| section 4.1 | Un element plus gros que le budget part entier | La regle 1 est declaree obligatoire. Consequence : un chunk ne contient jamais une sous-chaine d'element, contrairement a ce que la section 2.3 envisage |
| section 6 | `reconcilier_les_portions_de_l_element` ecrit aussi le texte | La spec appelle `texte_de_la_portion_avant_edition()`, methode inexistante, tout en ayant retire `ancien_texte`. Les deux sont inconciliables |
| section 6 | Les portions des extractions masquees sont repositionnees | Les ignorer laisserait des offsets perimes qui ressortiraient faux au demasquage |
| section 6 | Les portions deja `DETACHEE` sont exclues | Leurs offsets ne veulent plus rien dire : les reutiliser pouvait faire repasser une portion `EXACTE` sur un passage sans rapport |

### Migration
- **Migration necessaire / Migration required :** Non — aucun changement de schema.

## 2026-08-05 — Ancrage par element, phase F : moteur scission / fusion

**Quoi / What :** `services/moteur_structure.py` — couper un element en deux,
recoller deux elements adjacents, en redistribuant les portions d'ancrage.
Plus deux changements de schema que ces operations rendent necessaires.

**Pourquoi / Why :** une transcription audio colle deux tours de parole en un
seul element, ou attribue le mauvais locuteur au milieu d'un segment. Sans
scission ni fusion, la seule facon de corriger serait de tout re-analyser et de
perdre le debat attache. « Recoller un tour de parole scinde » est l'operation
numero un sur une vraie diarisation.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/moteur_structure.py` | Scission, fusion, coalescence, renumerotation |
| `hypostasis_extractor/tests/test_moteur_structure.py` | 41 tests |

### Changement de schema 1 : contraintes d'unicite DEFERRABLE
Les contraintes `unicite_ordre_dans_la_page` et `unicite_ordre_dans_l_extraction`
sont desormais verifiees au COMMIT, plus a chaque ligne ecrite.

**Raison :** le pseudo-code de la spec section 5.1 est incodable autrement. Il
cree le premier morceau avec l'`ordre` de l'element d'origine, qui existe encore
a cet instant — `IntegrityError` immediate, verifiee empiriquement. Meme
probleme pour le decalage des `ordre_dans_extraction` : decaler des numeros
de +1 fait forcement se telescoper deux lignes en chemin.

**Consequences a connaitre :**
- Une violation d'unicite sur ces deux tables ne se manifeste plus au `save()`
  mais au commit, donc hors de tout `try/except` place autour de l'ecriture.
- `bulk_create(ignore_conflicts=True)` et tout `ON CONFLICT` sont desormais
  refuses par PostgreSQL sur ces deux tables : une contrainte deferrable ne peut
  pas servir d'arbitre a un upsert.

### Changement de schema 2 : le journal des operations tient a la Page
`ElementOperation.element` passe de `CASCADE` a `SET_NULL`, et le modele gagne
`page` (FK obligatoire), `identifiant_stable_element` et `donnees`.

**Raison :** scission et fusion suppriment toujours leurs elements sources. Avec
une CASCADE sur l'element, chaque operation effacait l'historique de la
precedente — scinder puis refusionner ne laissait aucune trace de la scission.
Le journal etait decoratif, et l'invariant « rien ne disparait en silence » faux
la ou il compte le plus.

### Defauts de la spec corriges au passage / Spec defects fixed
| Section | Defaut / Defect |
|---|---|
| 5.1 | Le pseudo-code viole la contrainte d'unicite des la premiere ligne ; son `transaction.atomic()` arrive apres les `create` |
| 5.2 | La fusion promeut toutes les portions en `RETROUVEE`, y compris celles qui etaient `DETACHEE` — une portion detachee ressuscitait sur des offsets jamais valides |
| 5.2 | La coalescence recollait deux portions distantes de la longueur du separateur, ou qu'elles soient. Deux portions separees par deux caracteres de vrai texte etaient recollees en avalant ce texte. On ne recolle plus qu'a la couture |
| 5.2 | `_fusionner_les_provenances` : les boites PDF du second element heritaient du `page_no` du premier, donc auraient ete dessinees sur la mauvaise page. Chaque boite porte desormais sa page |

### Migration
- **Migration necessaire / Migration required :** Oui
- `core.0037` (contrainte deferrable), `hypostasis_extractor.0032` (idem),
  `core.0038` (journal rattache a la page, ecrite a la main car la table est
  vide et le champ `page` non-nullable).
- **Sans effet sur les donnees existantes** : les trois tables concernees ne
  sont alimentees par aucun pipeline a ce stade.

## 2026-08-05 — Ancrage par element, phase G : masquage et re-ingestion

**Quoi / What :** `services/masquage.py` (masquer, demasquer) et
`services/reingestion.py` (reconcilier les elements par empreinte).

**Pourquoi / Why :** deux besoins distincts.
- **Masquer** : la transcription audio invente du contenu — un bruit de fond
  transcrit en mots, une phrase repetee. Ce n'est ni une coquille a corriger
  (il n'y a rien a corriger VERS) ni une note d'incertitude. L'element sort du
  contenu utile sans etre supprime, et l'operation est reversible.
- **Re-ingerer** : un pad de 200 comptes-rendus grossit d'un compte-rendu par
  semaine. Il faut re-analyser sans repayer 200 appels au LLM ni perdre les
  debats attaches aux 199 autres. Les elements sont reconnus par empreinte de
  contenu, jamais par position.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/masquage.py` | Masquer, demasquer, detacher les portions |
| `hypostasis_extractor/services/reingestion.py` | Reconciliation des elements par empreinte |
| `hypostasis_extractor/tests/test_masquage_et_reingestion.py` | 26 tests |

### Ecarts avec la spec, et pourquoi / Deviations from the spec
| Ou / Where | Ecart / Deviation | Raison / Reason |
|---|---|---|
| 5.4 | Le demasquage ne reutilise pas la reconciliation | Celle-ci repositionne apres un CHANGEMENT de texte et rend la main quand le texte est inchange — exactement le cas du demasquage. Elle exclut de plus les portions detachees, a raison |
| 5.4 | Le journal note un hash du texte BRUT, pas l'empreinte normalisee | L'empreinte ecrase les espaces et la casse. Corriger une double espace pendant un masquage decale tous les offsets qui suivent sans changer l'empreinte d'un iota : les portions seraient rattachees a des positions fausses |
| 5.4 | Le journal note les identifiants des portions detachees | Un element peut porter des portions detachees AVANT le masquage, par une correction anterieure. Les rattacher au demasquage les ferait pointer n'importe quoi. Seules celles que ce masquage a detachees reviennent |
| 5.3 | Les elements deja masques sont apparies, pas exclus | En les excluant, un element masque dont le texte reste dans la source serait recree en doublon a chaque re-ingestion, masque a son tour, exclu, recree... Un pad re-ingere cinquante fois accumulerait cinquante copies du meme bruit |
| 5.3 | Les empreintes en double sont signalees des DEUX cotes | Ne regarder que l'ancien document laisse passer le cas le plus probable : un intitule repete qui apparait une seconde fois dans le NOUVEAU contenu |
| 5.3 | Le masquage par re-ingestion passe par `masquer_un_element` | Un masquage ecrit a la main ne serait ni journalise ni recuperable : l'element ne pourrait jamais retrouver ses ancres, meme a texte strictement identique |
| 5.3 | Numerotation en deux temps (plage temporaire puis renumerotation) | Un element masque restant a l'ordre 0 entre en collision definitive avec un nouvel element cree a l'ordre 0. Ce conflit-la n'est pas transitoire, donc la contrainte differee le refuse a juste titre |
| 5.2 | La fusion refuse un element masque avec un visible | Le resultat ne pourrait etre ni l'un ni l'autre : visible, il renverrait au LLM le bruit qu'un humain avait retire ; masque, il ferait disparaitre du contenu utile |

### Migration
- **Migration necessaire / Migration required :** Non — aucun changement de schema.

---

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

