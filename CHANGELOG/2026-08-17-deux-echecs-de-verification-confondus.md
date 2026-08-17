# Deux échecs de vérification confondus, et le bug que la distinction a révélé / Two verification failures conflated, and the bug it exposed

**Date :** 2026-08-17
**Migration :** Oui — `core/0063_verdict_citation_introuvable`
(`docker exec -w /app hypostasia_web python manage.py migrate core`)

## Résumé / Summary

**Quoi / What :** le verdict `FAIBLE` recouvrait **deux échecs de nature différente**.
Les séparer a immédiatement révélé un bug systématique : le contrôle verbatim cherchait
le passage cité dans `Page.text_readability`, **vide sur toute note ingérée par Docling**.
Il déclarait donc introuvables **118 citations sur 136** dont le passage était
parfaitement présent.
*/ The `FAIBLE` verdict conflated two different failures. Splitting them exposed a
systematic bug: the verbatim check read `Page.text_readability`, which is empty on every
Docling-ingested note.*

**Pourquoi / Why :** un compteur unique ne permettait pas de savoir **laquelle des deux
réparations** entreprendre — et il masquait une accusation fausse à grande échelle sur
l'étage qui fait toute la valeur du produit.
*/ A single counter hid which repair to undertake, and masked a false accusation at scale.*

### Les deux signaux, et pourquoi ils ne se confondent pas

| Verdict | Ce qu'il dit | Qui le pose | Nature | Réparation |
|---|---|---|---|---|
| **Citation introuvable** (`introuvable`) | le passage cité n'est **plus dans la source** | le **verbatim** seul, déterministe, sans juge | **intégrité** — la chaîne de preuve est rompue | citation déformée par le modèle, ou source éditée depuis l'extraction |
| **Faible** (`faible`) | le passage **existe**, mais n'établit pas ce qui est affirmé | le **juge** NLI | **attribution** — la mauvaise source est citée | l'affirmation ou son renvoi sont à revoir |

L'état de l'art mesure que **80,6 %** des affirmations invérifiables sont des erreurs
d'attribution et non des hallucinations : savoir dans laquelle des deux populations on se
trouve est précisément ce qui rend le chiffre actionnable.

### Le bug que la distinction a révélé

Le moteur ELEMENT est le **seul** moteur depuis le 10 août 2026 : la vérité du texte
d'une note, ce sont ses `ElementDocument`. Or `_texte_de_la_source` lisait
`Page.text_readability`.

**Mesuré le 17 août 2026 sur le carnet « Documents étalons » :**

| Note | Extractions | Présentes dans `text_readability` | Présentes dans les **éléments** |
|---|---|---|---|
| Badgeons la Normandie | 16 | **0** (champ vide) | **16** |
| Étude épistémologique de l'IA | 28 | **0** (champ vide) | **28** |
| Présentation des Open Badges | 37 | **0** (champ vide) | **37** |
| Débat IA — transcription | 18 | 18 | 18 |

Trois notes sur quatre ont un `text_readability` **vide** — c'est l'état normal d'une note
ingérée par Docling. Le verbatim cherchait donc dans une chaîne vide et échouait à coup
sûr. Le repli sur `text_readability` ne sert que les pages **sans aucun élément** — antérieures à
la bascule, ou ingestion jamais aboutie.

> **Correction du 17 août 2026, au soir.** Cette ligne disait « une transcription Voxtral
> porte son texte sans avoir d'élément ». C'est **faux** : depuis la bascule, l'audio est
> ingéré en éléments lui aussi — la note de dev en porte **12**, mesuré. Le repli ne sert
> donc plus les transcriptions.

### Effet du correctif, sur les mêmes articles et le même modèle

Gemini 2.5 Flash, wiki (54 paires) et synthèse dirigée (82 paires) du carnet étalon.

| | Avant | Après |
|---|---|---|
| **Vérifiées** | **0** | **120** |
| Faibles (juge refuse) | 18 | 16 |
| **Introuvables** (verbatim) | **118** | **0** |
| Sans verdict | 0 | 0 |

**88 % des citations sont exactes au mot ET soutenues par le juge.** Le produit annonçait
l'inverse.

> ⚠️ **Les chiffres « 15 vérifiées / 66 faibles » et « 13 / 72 » du CHANGELOG du 16 août
> sont FAUX** : ils ont été mesurés avec ce bug. Les seuls survivants étaient les
> extractions de la transcription Voxtral, la seule note à porter son `text_readability`.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | `EtatDeVerification.INTROUVABLE` (valeur `introuvable`, 11 signes — le champ fait 12) |
| `core/services/verification.py` | le verbatim lit les **éléments**, repli sur `text_readability` ; verdict `INTROUVABLE` avec sa provenance ; compteur `citations_introuvables` séparé |
| `front/views_synthese.py` | gravité (`introuvable` **devant** `faible`), libellé qui dit la cause, deux jeux de compteurs |
| `front/templates/front/corpus/_style_maquette.html` | filet **tireté** à la couleur de `faible` — pas de quatrième teinte |
| `front/templates/front/corpus/article.html` | la légende distingue les deux |
| `core/migrations/0063_*.py` | **Nouveau** — les `choices` du champ |
| `core/tests/test_verification.py` | +6 tests, 2 assertions mises à jour (changement de comportement voulu) |

### Un choix d'interface assumé

`introuvable` **reprend la couleur de `faible`**, à dessein. `PRESENTATION-V3.md § 3.6`
arbitre pour trois états visuellement discrets, à cause de la corrélation **r = −0,96**
entre précision des citations et utilité perçue : un quatrième badge de couleur
combattrait cette décision. Le signal se distingue par son **libellé**, sa **provenance**
et un filet **tireté** — pas par une teinte de plus.

---

## Comment tester (à la main) / Manual test

### Test 1 — les deux verdicts se distinguent

```bash
docker exec -w /app hypostasia_web python manage.py test core.tests.test_verification --noinput
```

### Test 2 — sur données réelles

1. Ouvrir le wiki du carnet 1, cliquer **« Vérifier les citations »**, attendre.
2. Les renvois passent majoritairement au **vert**. Sur les données étalons, attendre
   **~88 % de vérifiées**.
3. Cliquer un renvoi **faible** : le panneau doit dire *« la source existe mais ne suffit
   pas »* — donc un problème d'**attribution**.
4. S'il apparaît un renvoi **introuvable** (filet tireté), le panneau doit dire *« le
   passage cité n'est plus dans la source »* — donc un problème d'**intégrité**, et sa
   provenance porte `(verbatim introuvable dans la source)`.

### Test 3 — le repli ne doit pas avoir été cassé

Une page **sans aucun élément** — antérieure à la bascule, ou ingestion jamais aboutie —
doit encore voir ses citations vérifiées depuis son texte plat. C'est ce que verrouille
`test_une_note_sans_element_retombe_sur_text_readability`. (Ce n'est **pas** le cas de la
note audio : elle porte 12 éléments.)

### Vérif en base

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from collections import Counter
from core.models import SourceLink
print(dict(Counter(SourceLink.objects.values_list('etat_de_verification', flat=True))))"
```

### Piège à connaître

**`make restart S=celery_worker` après toute modification de `front/tasks.py` ou d'un
service qu'il importe.** Sans ça, la vérification tourne avec l'ancien code — c'est arrivé
deux fois pendant cette session.
