# ShieldStral — le cadrage fait tout

**18 août 2026.** Mesure locale, sur processeur, sans clé et sans réseau.
Rejouable : `benchmarks/juge_de_verification/comparer_shieldstral.py`.

---

## Ce que cette mesure établit

Le même modèle, les mêmes quinze paires, la même question — et deux résultats
opposés selon **où** on met l'affirmation et la source dans le message.

| Cadrage | sévérité | accord au seuil 0,5 | **AUC** | meilleur seuil |
|---|---|---|---|---|
| `ensemble` — affirmation ET source dans `<Document>` | large | 4/15 | **0,538** | 0,000 → 13/15 |
| `ensemble` | strict | 2/15 | **0,500** | 0,000 → 13/15 |
| **`separe`** — `<Query>` = l'affirmation, `<Document>` = la source seule | **large** | 11/15 | **0,923** | **0,378 → 14/15** |
| `separe` | strict | 8/15 | 0,846 | 0,000 → 13/15 |

**Lire l'AUC, pas l'accord.** Un taux d'accord dépend du seuil qu'on a choisi, et
tout ce banc existe parce que le seuil était le problème. L'AUC ne dépend
d'aucun seuil : c'est la probabilité qu'une paire vraie reçoive un score plus
haut qu'une paire fausse. 0,5 = le hasard. Le cadrage `ensemble` est **à
0,538** : il ne classe rien. Le cadrage `separe` est **à 0,923**.

Dit autrement, et c'est la formulation du bilan du 18 août : 13 paires positives
× 2 négatives = **26 couples**, et 0,923 × 26 = **24 couples bien ordonnés sur
26**.

## Pourquoi le cadrage change tout

La fiche du modèle décrit un triplet `<Instruct>` / `<Query>` / `<Document>` :
la question va dans `Query`, le texte à évaluer va dans `Document`. Le modèle
répond si le **Document** satisfait la **Query**.

Le cadrage `ensemble` viole cette structure — il met deux textes dans
`Document` là où le modèle en attend un, et lui demande implicitement de deviner
lequel il juge. Le cadrage `separe` la respecte : l'affirmation est la requête,
la source est le document à évaluer.

**Ce n'est donc pas un réglage de prompt, c'est une erreur de protocole.** Le
modèle n'y était pour rien.

## La séparation, paire par paire (cadrage `separe`, sévérité large)

| | scores |
|---|---|
| les deux paires que la relecture humaine **refuse** | 0,321 · 0,349 |
| les treize qu'elle **accepte** | 0,202 → 0,867 |

Une seule acceptée (0,202) tombe sous les refusées : c'est l'unique erreur du
14/15. Les autres sont toutes au-dessus de 0,378.

## Le même juge sur les 145 paires gelées : **AUC 0,734**

Le cadrage `separe`, sévérité large, rejoué sur l'**étalon gelé** — dix fois
plus de paires, et une référence qui n'est plus une relecture humaine mais les
verdicts de `gemini-2.5-flash`.

| jeu | paires | référence | AUC |
|---|---|---|---|
| relues à la main | 15 | un humain | **0,923** |
| **étalon gelé** | **145** | `gemini-2.5-flash` | **0,734** |

**Le 0,923 ne généralise pas.** C'est le résultat principal de cette seconde
mesure, et il fallait la faire avant de fonder quoi que ce soit sur la
première.

### Pourquoi l'accord ne veut rien dire sur ce jeu

L'étalon porte **118 « soutient » pour 27 « ne_soutient_pas »** — 81 % de
positifs. *Accepter tout* donne donc déjà 118/145. Le « meilleur seuil
0,000 → 118/145 » rendu par le banc n'est pas un échec du modèle : c'est un
artefact de la métrique sur un jeu déséquilibré. **Sur ce jeu, seule l'AUC se
lit.**

### Ce que les distributions montrent

| ce que la référence dit | médiane | moyenne | étendue |
|---|---|---|---|
| « soutient » (118) | **0,755** | 0,682 | 0,020 – 0,994 |
| « ne_soutient_pas » (27) | **0,378** | 0,459 | 0,020 – 0,893 |

Elles se séparent — loin du hasard, loin d'une séparation nette. Le compromis,
chiffré :

| seuil | rejets de la référence retrouvés | acceptations sacrifiées |
|---|---|---|
| 0,30 | 8/27 (30 %) | 11/118 (9 %) |
| **0,40** | **14/27 (52 %)** | **17/118 (14 %)** |
| 0,50 | 17/27 (63 %) | 27/118 (23 %) |

### La réserve qui interdit d'aller plus loin

**La « vérité » de ce jeu est un juge dont la reproductibilité mesurée est de
77 %.** Une part du désaccord est le bruit de la référence, pas l'erreur de
ShieldStral — et ces données ne permettent pas de démêler les deux. Un accord
parfait avec cette référence serait d'ailleurs suspect : il voudrait dire qu'on
a reproduit un juge instable.

**Conclusion : prometteur, pas démontré.** Le cadrage `separe` est bien le bon
— cela, c'est établi deux fois. Ce qui n'est pas établi, c'est le niveau de
performance : il faut une référence relue à la main sur plusieurs affirmations,
et elle n'existe pas.

## Ce que cette mesure ne dit PAS

- **Le seuil 0,378 est sur-ajusté.** Il est choisi *après coup* sur ces quinze
  points, qui portent tous sur **une seule** affirmation. Il ne dit pas ce qu'il
  vaudrait ailleurs. C'est l'AUC qui se lit sans cette réserve.
- **La « vérité » est une relecture humaine de quinze paires**, faite par un
  modèle de langage sur des paires qu'un autre modèle avait produites. Ce n'est
  pas un étalon : c'est un avis.
- **Rien n'est mesuré sur la stabilité.** Un modèle local à température nulle
  devrait être déterministe, mais ce n'est pas vérifié ici.

## L'erreur que cette mesure corrige, et ce qu'elle coûte

Le banc committé portait le cadrage `ensemble` — celui que le bilan du 18 août
déclare faux — et `shieldstral.json` en était la sortie. Les chiffres cités dans
ce bilan (14/15, AUC 0,92) n'avaient donc **aucun artefact rejouable** : qui
aurait relancé le banc aurait obtenu 4/15 et conclu l'inverse du texte.

Et le « seuil optimal 0,05 » qui circulait était **le meilleur seuil du cadrage
abandonné** — vérifié : 0,05 rend bien 13/15 en `ensemble`/strict. Il avait
survécu à la mesure qui l'avait produit, en étant recopié sans son cadre.

**Les deux cadrages restent dans le banc exprès.** Retirer le mauvais laisserait
le bon sans point de comparaison, et la prochaine personne qui doute referait
l'erreur.

## Rejouer

```bash
# les 15 paires relues à la main, les deux cadrages, les deux sévérités
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_shieldstral.py

# l'étalon gelé des 145 paires, cadrage séparé, sévérité large
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_shieldstral.py \
    --etalon --cadrage separe --severite large
```

Aucun appel réseau, aucune écriture en base, aucune facturation. Le modèle est
chargé depuis le cache local de HuggingFace (7,7 Go). Comptez environ deux
minutes de temps processeur par paire.

Sorties : `shieldstral.json` (15 paires, quatre combinaisons) et
`shieldstral-etalon.json` (145 paires).
