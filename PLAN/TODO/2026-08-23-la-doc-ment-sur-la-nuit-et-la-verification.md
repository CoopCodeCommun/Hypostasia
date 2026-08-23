# La doc ment sur la nuit et sur la vérification

**Constaté le 23 août 2026. Rien n'est corrigé.**

`AGENTS.md` pose la méthode : **« un trou de spec s'écrit avant de se coder »**, en
addendum daté. Cette note liste ce qui est à écrire avant que la série du 23 août ne
soit codée — c'est le seul lot de la série qui ne touche aucune ligne de code.

## Ce que la doc affirme, et que le code contredit

### 1. `PLAN/Diagrams/03-la-verification-des-citations.md`

Le § « Qui déclenche, et par où » (l. 22) affirme :

> **La vérification n'est JAMAIS automatique à la production.**

et ne montre que **deux** déclencheurs (l'humain, l'installation). Le nœud de départ
de la cascade (l. 68) le répète : « geste EXPLICITE, jamais automatique à la
production ».

**Faux depuis le commit `08965de` (21 août 2026, 08:18 UTC**, dont le chantier est
consigné dans `CHANGELOG/2026-08-20-la-preuve-dans-son-contexte.md`, § « La
vérification s'enchaîne, et ne rejuge que ce qui a bougé »**).**
`_ecrire_le_corps_d_un_article` (`front/tasks.py:1366`) appelle
`enchainer_la_verification()` à **toute** écriture de corps d'article — création,
régénération, mise à jour appliquée, réparation de titres. C'est un **troisième
déclencheur**, et il est **facturé**. Il part avec le fan-out des quatre juges
locaux (`_lancer_un_second_avis`), qui n'apparaissent pas non plus sur la planche.

### 2. `PLAN/Diagrams/02-du-prompt-a-l-article-source.md`

Le § « La mise à jour d'un wiki : le modèle propose, l'humain accepte » (l. 149) ne
montre qu'un chemin, dont le nœud `HUM` est « L'humain coche, opération par
opération ».

**Incomplet depuis l'addendum du 21 août** : `mettre_a_jour_un_wiki_la_nuit`
applique **sans humain** (`fait_par=None`), par le même applieur.

### 3. `PLAN/Diagrams/README.md`

La table des conventions dit : « Cadre **violet** : un geste **humain** — rien ne
s'applique tout seul ». La seconde moitié est fausse depuis que la nuit applique.

### 4. `PLAN/specs/SPEC-synthese-carnet.md`

L'addendum du 18 août (l. 15) énumère ce qui **ne change pas** du § 7, et y inclut :

> le caractère **explicite** du geste — la vérification ne se déclenche jamais à la
> production.

Aucun encart postérieur ne corrige cette phrase. L'addendum du 21 août, le plus
récent, ne parle pas de la vérification — il écrit en revanche que « le coût est
borné à un appel au rédacteur par wiki ayant du neuf », ce qui est **incomplet** :
chaque wiki réellement modifié enchaîne aussi un job de juge d'API.

> **Précision de méthode** : la règle du projet est *encarts datés > sections*, et
> non *récent > ancien*. Un encart faux n'est donc pas neutralisé par le silence
> d'un encart plus récent : il faut l'écrire.

### 5. La docstring de `verifier_les_citations_task`

`front/tasks.py:2656` : « La verification § 7 en asynchrone — un geste explicite,
jamais automatique (decision Q3). » Même erreur, dans le code cette fois.

### 6. Le prompt de mise à jour ment au modèle

`construire_la_proposition_d_operations` (`front/tasks.py:2255`) dit au rédacteur :

> Tu ne réécris JAMAIS l'article : tu proposes des opérations, **un humain les
> acceptera une par une**.

La passe de nuit emploie **le même prompt** et n'a aucun humain. Ce n'est pas qu'une
inexactitude : c'est ce qui autorise le modèle à proposer largement, en comptant sur
un filtre humain qui n'existe pas la nuit. À corriger **en même temps** que la borne
de `PLAN/TODO/2026-08-22-borner-la-reecriture-nocturne-d-un-wiki.md`, jamais après.

## Ce qui est voulu

- un **addendum daté** à `SPEC-synthese-carnet.md` : la vérification s'enchaîne à
  toute écriture de corps, elle est facturée, elle ne juge que les citations sans
  verdict ; et le coût d'une nuit inclut ce jugement ;
- la **planche 03** reprise : trois déclencheurs, et les quatre juges locaux ;
- la **planche 02** reprise : la nuit applique, par le même applieur ;
- le **README des Diagrams** : le violet dit « un geste humain », sans prétendre que
  rien ne s'applique tout seul ;
- les deux textes de code (docstring Q3, prompt de mise à jour).

**Une planche 04 « La nuit des wikis » reste à écrire** : planificateur, deux
conditions de reprise, fan-out et compteur de fermeture, tour, enchaînement facturé,
récapitulatif du matin. Aucune des trois planches ne couvre ce mécanisme.

## Ce qui casse si on ne fait rien

Rien ne casse : on se trompe. Une session qui lit la planche 03 conclut qu'un
article produit n'est jamais jugé, et n'ira pas chercher pourquoi la facture monte.
C'est exactement ce que le § 7b de feu `GUIDELINES.md` a fait pendant des mois avec
le WebSocket.

## Coût de mise en œuvre

Un addendum, trois blocs Mermaid retouchés, deux lignes de code. Une demi-journée.
Aucune dépendance : c'est le seul lot qui peut être fait pendant qu'on code le reste.
