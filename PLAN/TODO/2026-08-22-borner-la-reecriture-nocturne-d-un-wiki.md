# Faut-il empêcher la nuit de réécrire un article entier ?

**Question posée par le mainteneur le 22 août 2026, non tranchée.**
Ce document expose le problème et la borne proposée. **Rien n'est codé.**

## Ce que le code fait aujourd'hui

La passe de nuit applique des opérations de section sans humain
(`SPEC-synthese-carnet.md`, addendum du 21 août 2026). L'applieur
(`core/services/section_ops.py`) accepte quatre opérations, dont
`replace_section`, qui remplace le **corps** d'une section.

La règle « une seule opération de contenu par section et par lot » borne **par
section**, pas globalement. Donc un lot de N `replace_section`, un par section,
est parfaitement légitime au regard de chaque contrôle pris isolément — et
**réécrit l'article entier**.

Rien dans le code ne l'en empêche. Le seul frein est une consigne de prompt
(« privilégie l'ajout au remplacement »), c'est-à-dire la discipline du modèle.

## Ce que ça coûterait vraiment

Pas une perte esthétique : **une perte de jugement, et une facture.**

`indexer_les_citations` (`core/services/synthese.py`) reconcilie les verdicts
des juges **par paire (extraction, paragraphe)**. Un verdict est reporté quand
la paire est strictement identique. Si tous les paragraphes changent, toutes
les paires changent :

- **tous les verdicts de vérification tombent** — l'article repart sans aucune
  note, comme s'il venait d'être écrit ;
- il faut donc **tout rejuger**, et le juge de vérification est une API
  **facturée** (les quatre juges locaux, eux, sont gratuits) ;
- les **contestations humaines** dont la paire a disparu sont signalées
  (`contestations_perdues`) mais bien perdues.

À cela s'ajoute la perte de ce qu'un humain avait accepté aux tours précédents,
et que personne n'a demandé de remplacer.

## Ce qui n'est PAS le problème

- **La régénération complète** (`produire_un_wiki_task`) : la nuit n'y a aucun
  chemin, c'est vérifié et testé. Ce document ne parle que de la réécriture
  **par morceaux**, section après section.
- **Le geste manuel.** Un humain qui accepte opération par opération voit
  l'avant et l'après de chaque remplacement (§ 6.4). Le brider l'empêcherait
  d'assumer une refonte légitime.

## Ce qu'Atomic fait — vérifié dans son code le 22 août 2026

**Rien.** Aucune borne numérique, aucun quota, aucune proportion : cherché
explicitement (`ops.len()`, `MAX_OPS`, `too many`) dans tout le dépôt Rust.
`ReplaceSection` n'est pas traité différemment d'`AppendToSection` dans
l'applieur — même branche, aucun compteur. Il y a seulement deux consignes de
prompt : *« use sparingly — only when existing content is directly contradicted
or superseded »* et *« Prefer AppendToSection over ReplaceSection »*.

**Mais leur plan d'origine les prévoyait tous** (`docs/plans/wiki-proposal-loop-plan.md`,
section « Cost & Runaway Protection ») : quiet window de 10 min, cooldown par
tag de 30 min, `MAX_SUPERSEDES = 3`, plafonds de 20 propositions/jour et 3/tag,
précheck du provider — qualifiés de *« Non-negotiable guardrails… none are
"polish" »*. **Aucun n'a été écrit.** Atomic ne fait d'ailleurs **aucune** mise
à jour de wiki en tâche de fond : chez eux tout part d'un clic.

Il n'y a donc pas de modèle à copier. Il y a la liste de ce que son auteur
jugeait indispensable, et qu'il n'a jamais eu le temps d'écrire.

## La borne proposée

**Mesure préalable, sur les cinq wikis de la base de dev (22 août 2026) :**

| wiki | sections | caractères |
|---|---|---|
| 1 | 5 | 6 924 |
| 2 | 7 | 6 816 |
| 3 | 7 | 7 382 |
| 4 | **1** | 3 956 |
| 5 | 6 | 6 382 |

**Un plafond absolu ne protège pas.** `MAX_SUPERSEDES = 3` (le chiffre
d'Atomic) autorise trois remplacements sur un article qui n'a **qu'une seule
section** — soit sa réécriture intégrale, précisément le cas le plus facile à
détruire.

**La règle proposée** — appliquée **à la nuit seule** :

> Un lot nocturne ne peut pas remplacer plus de la **moitié** des sections d'un
> article, et **au moins une section doit rester intacte**.

| sections | remplacements autorisés la nuit |
|---|---|
| 7 | 3 |
| 6 | 3 |
| 5 | 2 |
| 2 | 1 |
| **1** | **0** — la nuit ne peut qu'ajouter ou insérer |

Le dépassement serait **rejeté visiblement**, opération par opération, avec son
motif dans l'historique — comme tous les autres rejets du § 6.2. Les premières
opérations du lot passent, les suivantes sont refusées : le lecteur voit
exactement ce que la nuit a voulu faire et ce qu'on lui a refusé.

## Ce qu'il faut trancher

1. **Faut-il la borne ?** L'argument contre est réel : c'est de la complexité
   pour un risque **jamais observé** — aucun lot massif de remplacements n'a été
   constaté à ce jour. L'argument pour est que la nuit applique **sans humain**,
   et que c'est exactement la situation où un garde-fou mécanique remplace un
   jugement absent.
2. **Le seuil.** « La moitié » est un choix, pas une mesure. Un tiers serait plus
   prudent, deux tiers plus permissif.
3. **La nuit seule, ou aussi le geste manuel ?** Ce document propose la nuit
   seule.

## Ce qui casse si on ne fait rien

Rien aujourd'hui. Le jour où un modèle décide de « rafraîchir » un article, la
nuit le fera sans que personne ne l'ait vu passer, et le matin l'annoncera comme
une mise à jour ordinaire. L'historique gardera tout — c'est le filet — mais les
verdicts, eux, seront à repayer.

## Coût de mise en œuvre

Une trentaine de lignes dans `core/services/section_ops.py` (un paramètre de
plafond, un compteur de remplacements, un motif de rejet), le passage de ce
paramètre depuis `appliquer_un_tour_de_wiki` selon l'appelant, et trois ou
quatre tests. Une heure environ.

---

## Ajout du 23 août 2026 — ce que la relecture adverse a établi

Cette borne n'est plus seulement un garde-fou de prudence : elle est devenue un
**prérequis de mesure**, et elle a un voisin qui l'appelle.

**1. Sans elle, aucun banc de la nuit n'est reproductible.** Tant qu'un lot nocturne
peut remplacer toutes les sections, chaque nuit peut faire tomber tous les verdicts
et tous les avis locaux — la réconciliation d'`indexer_les_citations` se fait par
paire (extraction, paragraphe), et une paire modifiée perd son verdict. Deux passes
du même banc sur le même carnet ne partiraient donc pas du même état. Toute la série
de notes du 23 août sur la mesure des prompts bute ici.

**2. Le prompt dit encore au modèle qu'un humain filtrera.**
`construire_la_proposition_d_operations` (`front/tasks.py:2255`) écrit : « tu proposes
des opérations, **un humain les acceptera une par une** ». C'est faux pour la nuit
depuis le 21 août, et ce n'est pas une inexactitude cosmétique : c'est précisément ce
qui autorise le modèle à proposer largement, en comptant sur un filtre qui n'existe
pas. **À corriger dans le même chantier que la borne, jamais après** — corriger le
prompt seul rendrait le modèle plus prudent sans qu'aucun mécanisme ne le garantisse,
et poser la borne seule laisserait le modèle proposer autant de rejets.

**3. Rejouer la direction de l'article pousse mécaniquement vers `replace_section`.**
`2026-08-23-la-direction-d-un-article-se-perd-a-la-mise-a-jour.md` prévoit d'injecter
le sujet et la consigne de forme dans le prompt de mise à jour. Un modèle à qui l'on
rappelle le plan voulu remplace au lieu d'ajouter — c'est l'effet recherché pour la
qualité, et c'est exactement ce que cette borne existe pour contenir. **Cette note
doit donc être tranchée AVANT celle-là.**

**4. Le coût du rejugement, chiffré.** Mesuré le 23 août avec
`AIModel.estimer_cout_euros` : le juge de vérification enchaîné coûte ~0,0014 € par
paquet de 20 paires — c'est **négligeable**. L'argument financier de la note ci-dessus
est donc plus faible qu'écrit ; l'argument qui reste, et qui est le bon, est la
**perte de jugement** : les verdicts humains contestés, les avis des quatre juges
locaux, et ce qu'un humain avait accepté aux tours précédents.

## Ce qu'il faut mesurer, avant de choisir le seuil

- **Fixtures étalons à écrire** : un wiki étalon **gelé hors base** — son article,
  son périmètre, ses verdicts et ses avis locaux — pour que deux passes du banc
  partent du même état. Sur le modèle de `benchmarks/juge_de_verification/etalon-du-juge.json`.
- **Un banc LLM réel** (`make test-llm`, tag `llm_reel`, **facturé**) : sur ce même
  wiki, N passes de proposition, et le compte des `replace_section` proposés — avec
  la consigne de prompt actuelle, puis avec la consigne corrigée. C'est ce qui dira
  si la borne mord souvent ou jamais, et donc si « la moitié » est le bon seuil.
- **Le risque jamais observé doit être mesuré, pas supposé** : à ce jour, aucun lot
  massif de remplacements n'a été constaté. Si le banc n'en produit aucun non plus,
  l'argument « c'est de la complexité pour un risque théorique » redevient recevable,
  et la décision doit être prise à la lumière de ce chiffre.
- **Attention au bruit** : `PLAN/PASSATION.md` § 6 mesure 11 points d'amplitude
  intra-modèle. Répéter chaque passe, et ne rien conclure d'un écart plus petit.
