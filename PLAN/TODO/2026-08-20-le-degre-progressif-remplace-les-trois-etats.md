# Le degré progressif — pourquoi il n'a PAS été codé tel quel

**Intention posée le 20 août 2026, révisée le même jour par la mesure.**

## Ce qui était voulu

Remplacer les trois états discrets par un **degré de 0 à 100**, moyenne des
scores des juges, pilotant une **couleur progressive** dans la gouttière.

## Ce que la mesure a dit, et qui a changé la cible

Trois chiffres, sur 209 citations réelles et 836 avis :

| mesure | résultat | conséquence |
|---|---|---|
| Pearson (degré agrégé local, juge de production) | **0,187** | les deux signaux ne disent pas la même chose |
| citations dont la couleur **basculerait** | **111/209 = 53 %** | une citation sur deux changerait de camp |
| valeurs distinctes rendues par `mistral-small` | **4** (0, 40, 70, 100) | le juge de référence n'est pas continu |

**Aucun des deux signaux ne permet à lui seul ce qui était demandé** : le juge
de production est la référence mais n'a que quatre valeurs ; les juges locaux
sont continus mais s'accordent à peine avec l'écran actuel. Piloter la couleur
par leur moyenne aurait donné une **fausse impression de précision** — un
raffinement apparent du même signal, qui en dit un autre.

**Et cela révoquait un invariant écrit** : « un avis local se lit À CÔTÉ du juge
de production, jamais à sa place » (`core/models.py:2169`), « ILS NE PILOTENT
RIEN » (`core/services/juges_locaux.py:22`).

## Le défaut qui a tué la variante intermédiaire

Une variante posait la **teinte** par le juge de production et l'**intensité**
par le degré local. Elle a été écartée pour une raison mesurée :

**une intensité est un canal SANS SIGNE**, or **42 % du signal qu'elle aurait
rendu visible est une CONTRADICTION de la teinte qu'elle module.** Un liseré
ambre « renforcé » parce que les locaux donnent 87 aurait dit *« encore plus
douteux »* là où l'information est *« les contrôleurs réhabilitent »*.

## Ce qui a été codé à la place

| | |
|---|---|
| teinte du paragraphe | **inchangée** — juge de production, règle du pire verdict |
| **couleur du renvoi `[N]`** | **ambre quand les locaux démentent franchement** le cran : 16 citations sur 209, **7,7 %** |
| carte de preuve | les **cinq** juges côte à côte, le juge de production nommé « référence » |
| aide | un « ? » en `<details>` natif sous la légende |

Seule la tension est colorée : peindre aussi l'accord aurait mis 92 % des
renvois en vert, et un signal qui est partout cesse d'être un signal.

## Ce qui reste ouvert

**La couleur progressive reste la cible du mainteneur.** Elle redeviendra
possible le jour où un agrégat dépassera ~0,6 d'AUC contre une référence — ce
qu'aucun ne fait aujourd'hui (moyenne des locaux : **0,566** ; le meilleur juge
seul fait mieux, **0,642**, ce qui veut dire que **moyenner détruit de
l'information**).

Deux décisions à prendre avant d'y revenir :

1. **le changement de juge** — faire piloter la couleur par les locaux est une
   révocation d'invariant, qui demande un addendum de spec daté ;
2. **la règle du paragraphe** — toutes les affirmations sont multi-sources, de
   **3 à 11 citations**. Rien ne dit comment fondre 3 à 11 degrés en un liseré.
   Le `min` est le seul choix cohérent avec l'existant, et il n'est écrit nulle
   part.

Et le préalable de tous : **la marge de neutralité**, qui rend CamemBERTa v2 et
mDeBERTa v3 muets **85 % du temps** (§ 6 de `PLAN/PASSATION.md`).
