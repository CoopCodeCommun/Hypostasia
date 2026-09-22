# Un seul écouteur Échap, et c'est la cascade / One Escape listener, and it is the cascade

**Date :** 2026-08-29
**Migration :** Non

## Résumé / Summary

**Quoi / What :** `marginalia.js` ne porte plus d'écouteur clavier. La fermeture de
l'éditeur de correction en place par `Échap` vit désormais dans la cascade de
`keyboard.js`, à un rang **après** le drawer.
/ marginalia.js no longer listens to the keyboard; closing the in-place editor with
Escape now lives in keyboard.js's cascade, ranked after the drawer.

**Pourquoi / Why :** deux écouteurs indépendants répondaient à la même touche.
**Mesuré le 29 août 2026, sur le serveur de dev** : avec le drawer ouvert par-dessus
un éditeur de correction, **un seul `Échap` fermait les deux** — et jetait la
correction en cours de frappe, sans confirmation ni enregistrement. La cascade
existe précisément pour fermer **une chose à la fois**, la plus proche de
l'utilisateur.

### Ce que la mesure a démenti en chemin

Ce chantier partait d'une phrase de `SPEC-edition-par-blocs-et-stenotypie.md` (§ 2)
qui appelait cet écouteur « un danger direct » pour le **futur** mode d'édition. En
allant vérifier, deux choses se sont révélées :

- **`marginalia.js` n'est pas du code mort.** Il est chargé par `base.html:584` et
  porte le clic sur les ancres inline, l'ouverture du drawer et le filtrage par
  contributeur. Son **nom** est un vestige des pastilles de marge, pas son contenu.
- **L'écouteur `Échap` n'était pas mort non plus** : c'est le jumeau du bouton
  « Annuler ». Le **neutraliser** aurait retiré une fonction qui marche. Le geste
  juste était donc de le **fusionner**, ce que la spec proposait en second.
- **Et le danger n'était pas seulement futur** : il produisait déjà le défaut
  ci-dessus, aujourd'hui, en production.

> **Un piège de méthode, payé ici** : un premier `grep` semblait montrer que rien
> ne posait jamais la classe `est-en-edition` — donc que l'éditeur était injecté
> invisible. C'était mon `head` qui tronquait la sortie et cachait
> `_editeur_en_place.html`, dont le script inline la pose. **Ne jamais tronquer une
> vérification d'exhaustivité.** Le navigateur a démenti l'hypothèse en trente
> secondes : l'éditeur s'ouvre, visible, 168 px de haut.

### Le comportement, avant et après

| | avant | après |
|---|---|---|
| éditeur seul, un `Échap` | fermé | **fermé** |
| éditeur **+ drawer**, un `Échap` | **les deux fermés** — la correction est perdue | **le drawer seul** |
| éditeur + drawer, un second `Échap` | — | **l'éditeur** |
| le bouton « Annuler » | ferme | **ferme** |

Vérifié au navigateur sur le serveur de dev, **zéro erreur JavaScript**.

### Pourquoi ce rang, après le drawer

Le drawer est un panneau qui s'ouvre **par-dessus** le texte : il est donc plus
proche de l'utilisateur que l'éditeur, qui vit dans le document. La cascade ferme
le plus proche en premier — c'est sa règle depuis toujours, et le rang 4.5 la
respecte.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/static/front/js/marginalia.js` | l'écouteur `keydown` retiré ; `fermerEditeurEnPlace()` extraite et **exposée** sur `window.marginalia` |
| `front/static/front/js/keyboard.js` | rangs **0.0 bis** (le `<dialog>`), **0.0 ter** (le menu) et **4.5** (l'éditeur, après le drawer) |
| `front/static/front/js/user_menu.js` | l'écouteur `keydown` retiré ; `fermerSiOuvert()` exposée |
| `front/templates/front/base.html` | `?v=` bumpés : marginalia 27→**28**, keyboard 26→**28**, user_menu 26→**27** |
| `front/tests/test_phases.py` | **4 tests** : plus aucun `keydown` dans marginalia, la fonction est exposée, le rang est après le drawer, et **aucun script ne pose d'écouteur clavier au niveau document** |

`collectstatic` passé — sans lui et sans le bump, les navigateurs auraient servi
l'ancien fichier.

### Deux autres écouteurs, trouvés par la relecture adverse

Le chantier ne visait que `marginalia.js`. Une relecture a montré que **le même
défaut se rejouait ailleurs**, et qu'un troisième cas lui était voisin :

| Où | Le défaut | Le rang |
|---|---|---|
| `user_menu.js:52` | menu ouvert par-dessus un éditeur : **un `Échap` fermait les deux** | **0.0 ter** — le menu s'ouvre par-dessus l'écran, il ferme en premier |
| le `<dialog>` de scission | il est en **top layer**, mais le rang 4.5 fermait l'éditeur **caché derrière lui** — brouillon perdu sans que rien ne se voie — et le `preventDefault` de la cascade empêchait en plus sa fermeture native | **0.0 bis** — avant tout le reste |

**Vérifié au navigateur**, sur deux blocs distincts (ouvrir l'éditeur cache les
boutons de **son** bloc) :

| | un `Échap` | l'éditeur |
|---|---|---|
| menu + éditeur | ferme **le menu seul** | **survit**, et un second `Échap` le ferme |
| dialogue + éditeur | ferme **le dialogue seul** | **survit** |

Zéro erreur JavaScript. `user_menu.js` expose désormais
`window.userMenu.fermerSiOuvert()`, sur le modèle de `marginalia`.

**Et le test a été élargi** : la règle ne vaut pas pour `marginalia.js` seul mais
pour **tout écouteur clavier au niveau document**. Il est borné aux écouteurs de
**document** — un écouteur posé sur **un champ** est légitime, il ne se déclenche que
si le focus y est, et `hypostasia.js` en garde un sur le champ du titre.

### Ce que cela débloque

L'addendum A de la spec nommait cet écouteur comme **l'obstacle à lever avant la
première ligne du mode d'édition** : si le mode réutilise la convention
`.est-en-edition` / `.editeur` — le chemin naturel —, une frappe d'`Échap` aurait
effacé le travail. **C'est levé.** Le mode aura son propre rang dans la cascade,
au-dessus de celui-ci.

---

## Comment tester (à la main) / Manual test

Sur https://beta.hypostasia.org/ (`jonas` / `admin1234`), ouvrir une note qu'on peut
écrire — par exemple `/lire/21/` — et passer en mode structure pour voir les boutons.

### Test 1 — l'éditeur seul
1. Fermer le drawer s'il est ouvert.
2. Cliquer « corriger » sur un passage : l'éditeur s'ouvre.
3. `Échap`. **Attendu** : l'éditeur se ferme.

### Test 2 — le défaut corrigé
1. Cliquer « corriger » : l'éditeur s'ouvre.
2. Taper quelque chose dedans, **sans valider**.
3. Ouvrir le drawer des analyses.
4. `Échap` **une fois**. **Attendu** : le drawer se ferme, **l'éditeur reste ouvert
   avec le texte tapé**. Avant ce chantier, les deux se fermaient et le texte
   partait.
5. `Échap` une seconde fois. **Attendu** : l'éditeur se ferme.

### Test 3 — le bouton n'a pas bougé
1. Ouvrir l'éditeur, cliquer « Annuler ». **Attendu** : il se ferme.

### Tests automatiques
```bash
docker exec -w /app hypostasia_web python manage.py test front.tests.test_phases --noinput
```
→ **528 tests, OK, en 272 s** (mesuré le 29 août 2026).
