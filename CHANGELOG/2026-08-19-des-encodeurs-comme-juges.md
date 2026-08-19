# Des encodeurs CPU comme juges de vérification / CPU encoders as verification judges

**Date :** 2026-08-19
**Migration :** Non

## Résumé / Summary

**Quoi / What :** un troisième banc d'essai, `comparer_un_encodeur.py`, qui mesure
**sept encodeurs** de 68 à 608 millions de paramètres — LettuceDetect, XNLI français,
bge-m3 — comme juges d'implication, sur les mêmes paires que les deux bancs existants.
Aucun code de production n'est touché : **rien n'est branché**, c'est une mesure.
/ A third bench measuring seven 68M–608M encoders as entailment judges, on the same
pairs as the two existing benches. No production code touched: nothing is wired in.

**Pourquoi / Why :** les trois mesures existantes ne concordent pas (AUC 0,923 · 0,734 ·
0,867 selon la référence), et le seul juge local disponible, ShieldStral, coûte
**~24 s de processeur par paire** — 90 minutes pour 223 citations. Un encodeur entraîné
pour cette tâche précise coûte **moins d'une seconde** par paire et pourrait rendre le
second avis praticable en continu.
/ The three existing measures disagree, and the only local judge costs ~24 s of CPU per
pair. A purpose-trained encoder costs under a second.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `benchmarks/juge_de_verification/comparer_un_encodeur.py` | **neuf** — le banc |
| `benchmarks/juge_de_verification/mesurer_le_plafond_de_l_etalon.py` | **neuf** — le plafond de l'étalon, **facturé** |
| `benchmarks/juge_de_verification/2026-08-19_des-encodeurs-contre-l-etalon.md` | **neuf** — le compte rendu et ses réserves |
| `benchmarks/juge_de_verification/README.md` | les lignes des deux nouveaux scripts |

### Les deux bornes, et pourquoi elles comptent plus que le classement

Ce chantier a produit deux chiffres qui **changent la lecture de tout le dossier**, y
compris des mesures antérieures.

| borne | valeur | ce qu'elle dit |
|---|---|---|
| **plafond** de l'étalon | **0,690** | `gemini-2.5-flash`, qui a *produit* l'étalon, ne prédit ses propres verdicts gelés qu'à 0,690 — parce que le protocole texte ne rend que **quatre crans**, et que **120 paires sur 145 reçoivent exactement 70** |
| **baseline lexicale** | **0,889** | un simple recouvrement de mots source→affirmation bat tous les juges mesurés, ShieldStral compris |

**Conséquence** : dépasser 0,690 ne démontre rien, et ne pas dépasser 0,889 est le vrai
constat. Les deux références sont **lexicalement saturées** — le paragraphe a été écrit à
partir de ses sources et en reprend le vocabulaire. Une AUC contre elles ne distingue pas
un juge d'implication d'un `grep`.

Le banc imprime donc la baseline **dans chaque tableau**, sans exception. Elle n'est pas
une curiosité : c'est le comparateur.

### Le jeu adverse — `--adverse`

Puisqu'aucune AUC contre les deux références ne démontre qu'un juge *vérifie*, le banc
porte un **troisième jeu** conçu pour que le compteur de mots n'y puisse rien : chaque
paire positive de l'étalon, plus la **même paire dont l'affirmation a été niée**.

La négation frappe la phrase que la source établit — choisie par recouvrement lexical, pas
au hasard : nier une phrase sans rapport laisserait la paire soutenue au sens large, et
l'étiquette mentirait. Elle n'enlève aucun mot et n'ajoute que « ne » / « n' » et « pas »,
tous sous quatre caractères, donc invisibles pour le compteur.

| propriété | valeur |
|---|---|
| paires | **228** — 114 positives, 114 négatives, **équilibré** |
| positives transformables | 114 sur 118 |
| recouvrement identique avant/après | **114 / 114** |
| **AUC du compteur de mots** | **0,500** |

**Tout ce qui dépasse 0,5 sur ce jeu est une détection qu'un `grep` ne peut pas produire.**
C'est la seule affirmation de ce genre que le dossier puisse soutenir.

### Ce que le banc refuse de faire

- **`--depuis` refuse un JSON mesuré sur l'autre jeu.** Chaque sortie porte l'empreinte du
  jeu (nom, nombre de paires, md5 des textes). Sans ce contrôle, relire 145 scores contre
  les 15 vérités des paires relues à la main ne lève aucune erreur : `zip` tronque en
  silence et rend des nombres plausibles. Même panne que le `shieldstral.json` fautif — un
  artefact qui a perdu sa question.
- **Le contrôle d'orientation exige une MARGE, pas un signe.** Un modèle qui note 0,964 la
  paire fausse et 0,994 la vraie *ordonne* sans *séparer* ; il passait « ✓ » avec une
  simple comparaison. C'est l'état mesuré de `lettucedect-610m-eurobert-fr`.
- **Rien ne s'écrit sans `--sortie`.**

### Ce que ce banc emprunte, et ce qu'il s'interdit de recopier

Il importe de `comparer_shieldstral.py` la métrique (`aire_sous_la_courbe`,
`meilleur_seuil`) **et** les deux chargeurs de paires. Deux implémentations de l'AUC
finiraient par ne plus mesurer la même chose, et les chiffres des deux bancs doivent se
lire côte à côte.

La seule copie qu'il s'autorise : les deux gabarits français de la bibliothèque
`lettucedetect` (`summary_prompt_fr.txt`, `qa_prompt_fr.txt`), parce que cette
bibliothèque **n'est pas installée** — le banc n'utilise que `transformers`. La copie est
signalée à l'endroit où elle vit.

---

## Comment tester (à la main) / Manual test

Aucun appel réseau une fois les poids en cache, **aucune écriture en base, aucune
facturation**. Les poids (~9 Go au total) descendent au premier passage.

### Test 1 — le plancher de bruit, qui passe avant tout le reste

```bash
docker exec -w /app -e PYTHONPATH=/tmp/banc_deps hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_encodeur.py \
    lettucedect-v2-mmbert-base --etalon --plancher
```

Attendu : `reproductibilité : N/N scores identiques au bit près (100,0 %)`.

**C'est le chiffre qui justifie tout le reste.** Le juge de référence des 145 paires ne
retrouve que **77 %** de ses propres verdicts à température 0. Un encodeur n'a ni
échantillonnage, ni jeton imprévisible : il *devrait* être parfaitement déterministe.
« Devrait » n'est pas « est » — d'où la vérification.

### Test 2 — le contrôle d'orientation refuse un modèle muet

Chaque candidat est d'abord confronté à une paire dont la réponse est connue : une source
qui dit « 67 millions », une affirmation qui dit « 69 millions ». Le banc affiche

```
orientation : ✓ — la paire fausse note 0.008, la paire vraie 0.991
```

et, si le modèle ne les sépare pas, un `⚠ INVERSÉE OU MUETTE` suivi d'une réserve
imprimée au-dessus de ses chiffres.

**Ce contrôle existe parce qu'une étiquette inversée ne lève aucune erreur** : les deux
modèles EuroBERT ne déclarent pas les leurs (`LABEL_0` / `LABEL_1`). Un banc qui se
tromperait de sens rendrait une AUC symétrique — 0,27 au lieu de 0,73 — et le chiffre
aurait l'air d'un mauvais modèle plutôt que d'une erreur de lecture.

Pour le voir échouer exprès : `lettucedect-610m-eurobert-fr` déclenche l'avertissement.

### Test 3 — la campagne entière

```bash
docker exec -w /app -e PYTHONPATH=/tmp/banc_deps hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_encodeur.py --tous --etalon \
    --sortie /app/benchmarks/juge_de_verification/encodeurs-etalon.json
```

Un tableau par candidat, trié par AUC décroissante, avec le nombre de passes avant et le
coût par passe. **Rien ne s'écrit sans `--sortie`** — délibérément : le banc voisin
`comparer_la_chaine.py` écrivait `resultats.json` sans qu'on le lui demande, et ce
fichier était l'**entrée** d'une autre mesure.

### Une dépendance à installer hors de l'environnement

`cmarkea/distilcamembert-base-nli` exige `sentencepiece`, absent de l'image. Il s'installe
**à côté**, sans toucher au conteneur ni à `pyproject.toml` :

```bash
docker exec hypostasia_web pip install --target /tmp/banc_deps sentencepiece
```

d'où le `-e PYTHONPATH=/tmp/banc_deps` de toutes les commandes ci-dessus. Sans lui, ce
seul candidat échoue et les six autres tournent.

### Vérifs

- L'étalon doit rester **intact** : `md5sum benchmarks/juge_de_verification/etalon-du-juge.json`
  → `a8837446ffdbd5dfc7bb881c1c9bfb93`. Le banc ne l'ouvre qu'en lecture.
- La base doit rester **inchangée** : ce banc n'importe pas Django et n'ouvre aucune
  connexion.
