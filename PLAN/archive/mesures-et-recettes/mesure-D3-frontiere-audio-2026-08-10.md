# Mesure D3 — frontière préférentielle du chunking audio (10 août 2026)

Question ouverte n°1 de `SPEC-ancrage-par-element-v2.md` (§ 4.1, « cas
audio ») et décision D3 du cahier
`PLAN/branchement-moteur-ancrage-cahier-des-charges.md` : *faut-il une
frontière de chunk préférée au changement de locuteur, et un tour de
parole correspond-il en général à un seul élément ?* Consigne du
propriétaire : **une mesure chiffrée, pas une opinion** — la voici.

## Protocole

- **Corpus** : les transcriptions diarisées RÉELLES de la base dev —
  `Page.source_type='audio'` avec `transcription_raw.segments` portant
  `speaker`. Filtre : ≥ 2 locuteurs et ≥ 10 tours. **24 transcriptions
  retenues** (sur 37 avec transcription), **2 153 tours de parole**,
  segments ASR regroupés en tours (segments consécutifs d'un même
  locuteur).
- **Simulation** : l'algorithme § 4.1 rejoué à l'identique
  (`BUDGET_MAXIMUM_PAR_CHUNK=1500`, `PLANCHER_AVANT_COUPURE_PREFEREE=900`,
  règle obligatoire « jamais couper un élément » respectée : un élément
  sur-budget forme un chunk seul), sous quatre régimes : éléments =
  TOURS ou SEGMENTS ASR, avec ou sans frontière préférée « cet élément
  ouvre un nouveau tour ».
- Script : `tmp/mesure_d3_audio.py` (lecture seule, rejouable).

## Résultats

### La forme des tours (n = 2 153)

| médiane | moyenne | p75 | p90 | p99 | max |
|---|---|---|---|---|---|
| 125 c | 459 c | 434 c | 1 095 c | 4 265 c | **34 715 c** |

- Tours > 1 500 c (budget) : **141, soit 6,5 %**.
- Tours > 900 c (plancher) : 262, soit 12 %.
- Les 8 plus longs : 34 715 (page 596), 31 374 (page 90), 12 872
  (page 99), 11 570 (page 61), 11 021 (page 121), 6 055, 5 801, 5 416.

**Lecture** : un tour ordinaire est très court (un chunk de 1 500 c en
contient ~8), mais la queue de distribution est réelle — podcasts et
exposés produisent des monologues de 10 000 à 35 000 caractères.

### Le chunking simulé (agrégat des 24 transcriptions)

| Régime | chunks (= appels LLM) | chunks multi-locuteurs | coupes en plein tour | chunks sur-budget |
|---|---|---|---|---|
| TOURS, sans préférence | **605** | 359 (59,3 %) | **0** | 141 |
| TOURS, avec préférence | 681 (**+12,6 %**) | 390 (57,3 %) | 0 | 141 |
| SEGMENTS, sans préférence | 706 | 482 | **605** | 0 |
| SEGMENTS, avec préférence | 800 | 513 | 375 | 0 |

## Ce que les chiffres tranchent

1. **La frontière préférentielle « changement de locuteur » est
   REJETÉE.** Elle coûte +12,6 % d'appels LLM et ne fait passer les
   chunks multi-locuteurs que de 59,3 % à 57,3 % : les tours sont trop
   courts pour qu'un chunk n'en contienne qu'un, la préférence ne peut
   rien y changer. C'est la même conclusion que la spec avait déjà
   tirée côté sections (« le gain est marginal ») — l'attribution au
   locuteur est portée par l'ancre M2M (la portion garde son élément,
   donc son locuteur), pas par la frontière de chunk.

2. **Les éléments audio doivent être les TOURS DE PAROLE, pas les
   segments ASR.** Éléments = segments : 605 coupes en plein tour (85 %
   des frontières internes tombent au milieu d'un tour) — exactement le
   défaut que le moteur existe pour éviter. Éléments = tours : zéro.

3. **Un tour sur-budget doit être SCINDÉ À L'INGESTION.** 6,5 % des
   tours dépassent 1 500 c, jusqu'à 34 715 c : la règle « jamais couper
   un élément » enverrait des chunks de 35 000 caractères au LLM. À
   l'ingestion audio, un tour > 1 500 c est découpé en plusieurs
   éléments consécutifs du même locuteur, la coupe posée à la frontière
   de segment ASR la plus proche du budget (les segments suivent les
   pauses : c'est la meilleure frontière disponible). Le label porte le
   locuteur ; l'adjacence permet à « recoller avec le suivant » (U1) de
   réparer un découpage malheureux à la main.

## Décision proposée pour la bascule audio (D2, ordre 3)

- 1 élément par tour de parole ; tours > 1 500 c scindés au segment le
  plus proche du budget.
- Chunking : budget seul, AUCUNE frontière préférentielle audio.
- La règle obligatoire « jamais couper un élément » reste entière.

Consigné par addendum daté dans `SPEC-ancrage-par-element-v2.md`.
