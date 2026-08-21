# La tension entre les juges, sur le renvoi / Judge disagreement, on the reference

**Date :** 2026-08-20
**Migration :** Non

## Resume / Summary

**Quoi / What :** le renvoi `[N]` change de couleur quand les quatre juges
locaux **démentent franchement** le juge de production. La carte de preuve
réunit désormais les **cinq** juges côte à côte, et une aide « ? » explique la
lecture sous la légende.
/ The [N] reference turns amber when the four local judges franky contradict
the production judge; the proof card now shows all five side by side.

**Pourquoi / Why :** les juges locaux existent pour **contrôler** le juge de
production, mais leur désaccord n'était visible nulle part — il fallait ouvrir
chaque fiche et comparer un chiffre du haut à quatre barres du bas.
/ The local judges exist to check the production judge, but their disagreement
was visible nowhere.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/services/degre_agrege.py` | **Neuf.** `degre_agrege` (normalisation par seuil, amplitude non linéaire, facteur d'accord) et `tension_des_juges` |
| `front/views_synthese.py` | le renvoi porte `data-accord-local` ; `prefetch_related("avis_locaux")` |
| `front/templates/front/corpus/_style_maquette.html` | la couleur de tension, le style de l'aide |
| `front/templates/front/corpus/partials/preuve.html` | le juge de production entre dans la comparaison, nommé « référence » |
| `front/templates/front/corpus/article.html` | l'aide « ? » en `<details>` natif |
| `core/tests/test_degre_agrege.py` | **Neuf**, 17 tests |
| `front/tests/test_tension_sur_le_renvoi.py` | **Neuf**, 5 tests |
| `front/tests/test_les_cinq_juges_en_un_clic.py` | **Neuf**, 4 tests |
| `PRESENTATION-V3.md` | § 3.6 révisé + réserve sur le `−0,96` |
| `PLAN/TODO/` | **Neuf.** Deux notes d'intention |

### Les mesures qui ont décidé de la forme / The measurements behind the design

Sur **209 citations** et **836 avis** réels :

| mesure | résultat | ce qu'elle a écarté |
|---|---|---|
| Pearson (degré agrégé local, juge de production) | **0,187** | la couleur pilotée par la moyenne des locaux |
| citations dont la couleur basculerait | **111/209 = 53 %** | idem |
| valeurs distinctes rendues par `mistral-small` | **4** | la couleur pilotée par le seul juge de production |
| hors bande neutre | 105/209 = 50 % | — |
| **dont CONTREDISENT le cran** | **44/209**, soit **42 % du signal** | **le canal d'intensité** |
| contradictions **franches** | **16/209 = 7,7 %** | *c'est le signal retenu* |
| 4 juges unanimes ET francs | 8/209 = 3,8 % | la marque « unanimité » |

**Le canal d'intensité a été écarté pour une raison de fond** : une intensité
n'a **pas de signe**, or 42 % du signal qu'elle aurait rendu visible est une
**contradiction** de la teinte qu'elle module. Un liseré ambre « renforcé »
parce que les locaux donnent 87 aurait dit « encore plus douteux » là où
l'information est « les contrôleurs réhabilitent ».

**Seule la tension est colorée.** Peindre aussi l'accord mettrait 92 % des
renvois en vert, et un signal qui est partout cesse d'être un signal.

⚠️ **Aucun invariant n'est révoqué** : la teinte du paragraphe reste celle du
juge de production, et les avis locaux se lisent toujours **à côté** de lui,
jamais à sa place (`core/models.py:2169`).

---

## Comment tester (a la main) / Manual test

### Test 1 — les tests automatiques
```bash
docker compose exec -T web python manage.py test \
    core.tests.test_degre_agrege \
    front.tests.test_tension_sur_le_renvoi \
    front.tests.test_les_cinq_juges_en_un_clic \
    front.tests.test_degre_a_l_ecran front.tests.test_second_avis_a_l_ecran
```
Attendu : **49 tests OK**.

Les deux qui protègent le plus : `test_le_html_de_l_article_ne_contient_pas_le_degre`
(aucun chiffre dans le texte, § 3.6) et
`test_une_divergence_MOLLE_ne_fait_pas_tension` — sans cette garde, la marque
se déclencherait sur une citation sur cinq, donc deviendrait du bruit.

### Test 2 — à l'œil, dans l'article
Ouvrir « État des lieux du carnet de démonstration ». Attendu : **63 renvois,
dont 2 en ambre** (3 %). Les autres gardent la couleur neutre habituelle.

Cliquer un renvoi ambre, déplier « avis des juges locaux » : la **première**
barre est celle du **juge de référence**, suivie des quatre juges locaux. On
doit voir d'un coup d'œil pourquoi il y a désaccord.

### Test 3 — l'aide
Sous l'article, déplier **« ? Comment lire les couleurs »**. Vérifier qu'elle
s'ouvre **au clavier** (Tab puis Entrée) — c'est pour cela que c'est un
`<details>` natif et non un `title`, qui ne s'atteint ni au clavier ni au doigt.

### ⚠️ Ce qui reste à faire
**La vérification au navigateur, en clair ET en sombre, contrastes calculés.**
Le token `--faible` vaut `#b45309` en clair et `#fbbf24` en sombre ; il faut
vérifier le contraste du renvoi ambre sur le fond du texte, dans les deux
thèmes. Exigence d'`AGENTS.md` que rien ne remplace.

Le CSS touché vit dans un **template** (`_style_maquette.html`), pas dans
`maquette.css` : ni `collectstatic` ni bump `?v=` ne sont nécessaires.
