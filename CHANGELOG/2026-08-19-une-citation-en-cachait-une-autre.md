# Une citation en cachait une autre / One citation was hiding another

**Date :** 2026-08-19
**Migration :** Non

## Résumé / Summary

**Quoi / What :** quand une même extraction était citée dans **deux paragraphes**, le
second renvoi écrasait le premier : les deux marqueurs pointaient vers le **même**
`SourceLink`, et l'autre n'était atteignable par aucun chemin.
*/ A twice-cited extraction rendered one link twice and stranded the other.*

**Pourquoi / Why :** dans `_html_avec_renvois`, le jeton de substitution était construit
sur **l'extraction seule**, jamais sur le paragraphe.
*/ The substitution token was keyed on the extraction alone.*

### Fichiers / Files

| Fichier | Changement |
|---|---|
| `front/views_synthese.py` | le jeton porte le rang du marqueur |
| `front/tests/test_une_extraction_citee_deux_fois.py` | **neuf** — 3 tests |

## Le mécanisme, en trois lignes

```python
jeton = f"RENVOIJETON{numero}X{identifiant}FIN"   # ← ne dépend que de l'extraction
jetons[jeton] = (numero, lien_du_marqueur)        # ← le second écrase le premier
html_rendu = html_rendu.replace(jeton, …)          # ← remplace TOUTES les occurrences
```

1. deux marqueurs de la même extraction produisaient **le même jeton** ;
2. le dictionnaire n'en gardait que **le dernier lien** ;
3. `str.replace` remplaçait **les deux** occurrences par celui-là.

## Ce que le lecteur subissait

Il cliquait le renvoi du **premier** paragraphe et obtenait la preuve du **second** —
autres bornes, autre source, **autre statut de vérification**. Et la citation du premier
paragraphe n'existait pour lui d'aucune façon.

**Rien ne le signalait.** Le compte de renvois à l'écran était juste, les états affichés
étaient cohérents avec la base — pour les liens rendus. C'est en comparant les
identifiants distincts au nombre de citations que l'écart apparaît.

## Mesuré, avant et après

Sur la base de démonstration, wiki « Les open badges » (page 7) :

| | avant | après |
|---|---|---|
| renvois rendus | 61 | 61 |
| **identifiants distincts** | **57** | **61** |
| rendus deux fois | 1849, 1850, 1851, 1852 | aucun |
| **jamais rendus** | **1815, 1822, 1833, 1836** | **aucun** |

Les huit liens en cause portaient **les mêmes quatre extractions** (85, 103, 126, 139),
chacune citée dans deux paragraphes.

**La preuve que c'était visible à l'écran** : la distribution des statuts affichés passe
de `faible: 32 · non_verifie: 9` à **`faible: 31 · non_verifie: 10`**. Un marqueur
annonçait « faible » là où sa vraie citation est « en attente ».

La synthèse (page 8) n'était pas touchée : ses 79 citations portent 79 extractions
distinctes.

## Ce qui ne change PAS, et c'est voulu

Le **numéro** affiché `[N]` suit toujours l'extraction, pas le paragraphe : une même
source citée deux fois porte le même `[1]` aux deux endroits, comme une bibliographie.
Seule la **cible** du renvoi diffère. Vérifié : 57 numéros distincts pour 57 extractions
distinctes sur la page 7.

---

## Comment tester (à la main) / Manual test

### Test 1 — le cas qui échouait

1. Ouvrir un wiki où **la même source** est citée dans **deux paragraphes** différents.
   Sur la base de démonstration : le wiki « Les open badges », paragraphes 3 et 8.
2. Cliquer le renvoi du **premier** paragraphe, noter la citation affichée dans le
   panneau de preuve.
3. Cliquer le renvoi du **second**.

**Attendu** : deux citations **différentes**, avec leurs propres bornes et leur propre
statut. Avant le correctif, les deux ouvraient la même.

### Test 2 — aucune citation orpheline

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
import re
from core.models import Page, SourceLink, TypeLien
from front.views_synthese import _html_avec_renvois
for p in Page.objects.filter(type_de_note__in=['wiki','synthese']):
    liens = set(SourceLink.objects.filter(page_cible=p, type_lien=TypeLien.CITE).values_list('pk', flat=True))
    if not liens: continue
    rendus = {int(i) for i in re.findall(r'/citations/(\\\\d+)/preuve/', _html_avec_renvois(p))}
    print(p.pk, p.type_de_note, 'en base', len(liens), 'rendus', len(rendus),
          'ORPHELINES' if liens - rendus else 'ok')"
```

**Attendu** : `ok` partout, et `en base == rendus` pour chaque page.

### Vérifs

- Le numéro reste bibliographique : une source citée deux fois garde le même `[N]`.
- Aucun `data-etat` vide, et chacun conforme à la base.
