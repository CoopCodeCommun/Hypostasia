# LA FAMILLE 4 N'AVAIT JAMAIS ETE COMPLETE

**Date :** 2026-08-14
**Migration :** Non

**Quoi / What :** le referentiel des 30 hypostases n'en decrivait
reellement que 28. La famille 4 est corrigee, et cinq tests empechent
desormais les cinq copies du referentiel de diverger. / The 30-hypostases
reference actually described only 28; family 4 is fixed and five tests now
keep the five copies from drifting.

### LE MOTIF, ET CE QUI LE VIOLAIT

La geometrie des debats se deduit : 2 dispositifs de preuve (formel,
empirique) x 3 modes de raisonnement (induction, abduction, deduction)
= **6 modes**. Chaque hypostase est un couple *(ce qui ne peut pas la
refuter, ce qui ne peut pas la prouver)*, les deux etant distincts —
donc **6 x 5 = 30** cases, une par hypostase.

Lu comme une matrice 6x6, le referentiel doit occuper toutes les cases
hors diagonale. **Cinq familles sur six le faisaient.** La famille 4
(« non refutee par deduction formelle ») cumulait trois defauts :

- `principe` et `loi` occupaient **la meme case** (*non prouve par
  induction empirique*) ;
- `domaine` occupait une **case diagonale** — *non prouve par deduction
  formelle*, soit le mode de sa propre famille, le seul interdit ;
- **deux cases restaient vides**, face a `invariant` et face a
  `evenement`.

Le referentiel promettait 30 manieres d'etre discutable et en livrait
28, dont une comptee deux fois.

L'anomalie figurait **a l'identique dans les six sources** du depot
(`seed_prompts.py`, le banc d'essai de mars 2026, le prompt de
production et les trois fixtures de demo) : elle ne venait pas d'une
recopie fautive, elle etait dans la saisie d'origine.

### LA CORRECTION

| Hypostase | Avant | Apres | Fait desormais face a |
|---|---|---|---|
| `loi` | induction empirique | *inchangee* | `approximation` |
| `principe` | induction empirique | **induction formelle** | `invariant` |
| `domaine` | deduction formelle *(illegal)* | **deduction empirique** | `evenement` |

`loi` ne bouge pas : « non prouve par induction empirique » y decrit le
probleme de Hume — une correlation ne se prouve pas en generalisant des
observations. Les 15 paires symetriques de la matrice sont desormais
completes.

Fichiers touches : `seed_prompts.py`,
`benchmarks/extraction_format/prompts.py`,
`front/services/fixtures_analyseurs.py`, et les fixtures
`demo_ia.json`, `demo_completes.json`, `demo_alignement_versions.json`.

### CE QUI EMPECHE LA DERIVE MAINTENANT

`hypostasis_extractor/tests/test_referentiel_des_hypostases.py` — 11 tests.
Les 30 hypostases sont ecrites en de nombreux endroits sans qu'aucun
lien de code ne relie ces copies :

1. `core.models.HypostasisChoices` ;
2. le referentiel du prompt ;
3. les 30 exemples few-shot ;
4. `front.normalisation.HYPOSTASES_CONNUES` — **le filtre**, qui supprime
   en silence toute hypostase qu'il ne connait pas ;
5. le `README.md`, ou la matrice est desormais publiee ;
6. **les fixtures de demo — douze copies**, reparties entre des
   `promptpiece.content` et des `extractionjob.prompt_description`.

Le point 6 est le moins evident et le plus piegeux. `demo_ia.json` ne
porte pas que des donnees d'illustration : il contient un analyseur
« Hypostasia » COMPLET, prompt inclus. Or
`creer_les_modeles_ia_et_les_analyseurs()` fait un `get_or_create` sur le
NOM et ne garnit le prompt que si l'analyseur n'a aucune piece — donc sur
une base ou la fixture a ete chargee en premier, **c'est le prompt de la
fixture qui gagne**, et le referentiel du code n'y arrivera jamais. Une
fixture laissee en arriere est un referentiel fantome : invisible dans
les fichiers Python, et pourtant celui qu'un modele recevra.

Restent hors filet : `seed_prompts.py` et
`benchmarks/extraction_format/prompts.py`, corriges eux aussi mais
surveilles par aucun test — ni l'un ni l'autre n'est charge par
l'installation.

Jusqu'ici, seul le *compte* de la copie n°4 etait teste
(`test_phase29_normalize`) : compter 30 de chaque cote ne dit pas que ce
sont les memes 30. Un renommage passait sans bruit.

`hypostasis_extractor/tests/test_justesse_semantique_llm.py` — 2 tests
sous le tag `llm_reel`, qui mesurent sur un vrai appel si le modele
range les passages dans la bonne famille epistemique (10/10 au
14 aout, seuil a 60 %). C'est le seul test qui puisse attraper une
regression du prompt : toute la mecanique reste verte meme quand les
etiquettes deviennent fausses.

### A FAIRE SUR LES BASES EXISTANTES

`creer_les_modeles_ia_et_les_analyseurs()` ne reecrit **jamais** un
analyseur deja garni — c'est voulu, un prompt retouche a la main
appartient a son auteur. La consequence : **une base existante garde
l'ancien prompt**, famille 4 cassee comprise. La correction du code ne
se propage pas toute seule. Voir `README.md` §
« Les 30 hypostases » pour le referentiel a jour.

### AUSSI

- `benchmarks/extraction_format/test_format_extraction.py` renomme en
  `lancer_comparaison_formats.py` : il n'a jamais contenu de `TestCase`
  et laissait croire a une couverture inexistante.
- `README.md` : la matrice complete et les 6 familles sont publiees. La
  mention « 8 familles » y designait les familles **de couleurs**
  (affichage des cartes), sans rapport avec les 6 familles
  epistemiques — l'ambiguite est levee.

