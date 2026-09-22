# Le point détaché de son mot / The full stop torn from its word

**Date :** 2026-08-22
**Migration :** Non
**Réingestion :** **Oui, pour en tirer le bénéfice** — voir plus bas.

## Resume / Summary

**Quoi / What :** Docling **découpe** un paragraphe au niveau du balisage en
ligne. `des **synthèses sourcées et contestables**. Trois déplacements` lui
arrive en **trois** fragments — `des`, le gras, puis `. Trois déplacements`.
Notre recollage les joignait avec un espace **inconditionnel**, ce qui
produisait `contestables .` : un point détaché de son mot. `_recoller()`
(`hypostasis_extractor/services/ingestion_docling.py`) colle désormais la
ponctuation basse au mot qui la précède, et ce qui suit une parenthèse
ouvrante à cette parenthèse.
/ Docling splits a paragraph at inline markup; our rejoining inserted an
unconditional space, tearing the full stop from its word.

**Pourquoi / Why :** ce n'est pas cosmétique. Le juge de vérification compare
la citation du modèle au texte de l'élément **mot pour mot**. Le modèle recolle
le point — comme n'importe quel lecteur — notre texte ne le recollait pas, et
la citation partait en `INTROUVABLE`. Mesure du 19 août 2026 : sur **60**
citations introuvables, **34 (57 %)** ne tenaient qu'à une retouche de forme,
dont **20 à une espace de ponctuation**. Seules **11 (18 %)** étaient un vrai
saut de passage.
/ Not cosmetic: the verification judge compares word for word, and 57 % of
"not found" citations came from this kind of artefact.

**Ce que la mesure du 22 août a établi, et qui change la décision.** La question
posée était : donnée déjà présente, ou moteur ? **Les deux, et il fallait les
séparer.**

| origine | le défaut vient de | ce qu'on fait |
|---|---|---|
| **markdown, PDF, docx** | **le MOTEUR** — `PRESENTATION-V3.md` porte **zéro** espace avant un point, l'élément stocké en porte un | corrigé ici |
| **capture web** | **la DONNÉE** — le HTML d'origine porte déjà les espaces : **505** occurrences sur une page, 18 sur une autre | rien à corriger : on recopie fidèlement |

Autrement dit : le correctif traite la moitié du problème, celle qui nous
appartient. Sur une source web qui écrit `mot .`, le moteur continuera de rendre
`mot .` — et il a raison de le faire.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/services/ingestion_docling.py` | `_recoller()` **neuve** : ponctuation basse collée au mot, ouvrantes collées à ce qui suit. Le recollage inline l'appelle au lieu de concaténer avec un espace |
| `hypostasis_extractor/tests/test_ingestion_docling.py` | `RecollageDesFragmentsTest` (6 tests) |
| `hypostasis_extractor/migrations/0036_alter_extractedentity_end_char_and_more.py` | **Sans rapport** : résorbe une dérive de `help_text` qui traînait, et que `makemigrations` reproposait à chaque appel |

**La ponctuation haute française garde son espace** (`;` `:` `!` `?`) : la
typographie française lui veut une espace insécable devant, et trancher cela ici
serait un choix de rendu, pas une réparation. C'est verrouillé par un test, pour
que personne ne « complète » la liste par symétrie.

---

## Comment tester (a la main) / Manual test

### Test 1 — le recollage, sans rien réingérer

```bash
docker compose exec web python -c "
from hypostasis_extractor.services.ingestion_docling import _recoller
print(_recoller('des synthèses sourcées et contestables', '. Trois déplacements.'))
print(_recoller('le fichier', 'reconciliation.py'))
print(_recoller('un mot', '; la suite'))
"
```

Attendu :
```
des synthèses sourcées et contestables. Trois déplacements.
le fichier reconciliation.py
un mot ; la suite
```

### Test 2 — ce qui reste en base, et pourquoi

**Le correctif ne répare pas rétroactivement** : les 22 éléments déjà ingérés
gardent leur espace. Pour les compter :

```bash
docker compose exec web python manage.py shell -c "
import re
from core.models import ElementDocument
motif = re.compile(r'\w \.')
touches = [e.pk for e in ElementDocument.objects.all() if motif.search(e.texte or '')]
print(len(touches), 'element(s) portent encore un espace avant un point')
"
```

Au 22 août 2026 : **22 éléments sur 1103**, répartis sur 4 pages — dont **3
captures web**, où le défaut vient de la source et où il ne faut donc **rien**
changer.

### Test 3 — la réingestion, pour les documents dont le moteur est fautif

Seules les pages issues d'un **fichier** (markdown, PDF, docx) gagnent à être
réingérées. La commande existe :

```bash
docker compose exec web python manage.py reingerer_les_notes --help
```

⚠️ **Une réingestion détruit et recrée les `ElementDocument`.** Les ancrages
d'extraction sont en `PROTECT` : lire ce que la commande dit avant de la lancer,
et vérifier ce qu'elle propose de faire des extractions existantes.

### Ce qu'il faut savoir sur la mesure d'origine

Les 57 % viennent de
`benchmarks/extraction_format/2026-08-19_le-mode-d-echec-du-verbatim.md`. Ce
correctif traite **la cause côté moteur** ; il ne traite pas la question posée
au § 6 de `PLAN/PASSATION.md` (« faut-il assouplir la comparaison du
verbatim ? »), qui reste ouverte et qui porte, elle, sur ce que « verbatim »
veut dire dans la chaîne de preuve.
