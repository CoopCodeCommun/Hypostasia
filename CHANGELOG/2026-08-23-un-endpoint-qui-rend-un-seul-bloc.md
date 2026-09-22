# Le swap ciblé remplace le rechargement de la lecture / A targeted swap replaces the full reading reload

**Date :** 2026-08-23, poursuivi le 2026-08-24
**Migration :** Non

## Résumé / Summary

**Quoi / What :** `GET /elements/<pk>/bloc/` rend **un seul bloc de lecture**, prêt
à remplacer le sien. Le corps de boucle de `_blocs_elements.html` devient un
gabarit à part, `_un_bloc_element.html`, inclus par les deux chemins. Et chaque
bloc porte enfin son **`identifiant_stable`** dans le DOM.
/ A new endpoint renders one reading block; the loop body becomes its own
template, included by both paths; blocks now carry their stable id.

**Pourquoi / Why :** aujourd'hui, toute opération d'élément répond avec un
`HX-Trigger: lectureReload`, et le front refait `zoneLecture.innerHTML` **pour la
page entière** (`hypostasia.js:494-512`). Sur une note de 210 blocs, changer un mot
reconstruit tout : le défilement et le focus sont perdus à chaque geste — le code
les resynchronise déjà à la main, ce qui dit assez que le rechargement casse
quelque chose. Et le jour où un mode d'édition existera, ce rechargement
**détruira la session en cours**. C'est le point 3 du § 11 de
`SPEC-edition-par-blocs-et-stenotypie.md`, et il ne dépend **d'aucune** des trois
voies d'édition en concurrence.
/ Today every element operation reloads the whole reading zone.

### Le choix qui compte

**Le rendu passe par le service de la page, jamais par un rendu à part.**
`construire_les_blocs_de_lecture` est appelé sur la page, puis on prend le bloc
visé. C'est plus de travail que de rendre un bloc seul, **et c'est voulu** : un
second chemin de rendu finirait par produire un bloc qui ne ressemble plus à ses
voisins — numérotation, surlignage, minutage — sans que rien ne le signale.
`test_le_bloc_rendu_seul_est_identique_a_celui_de_la_page` épingle cette égalité,
au caractère près.

### Deux points de sécurité, décidés explicitement

- **L'action est `AllowAny` dans un ViewSet `IsAuthenticated`, et c'est délibéré.**
  Une note rangée dans un carnet **public** se lit sans compte —
  `_utilisateur_a_acces_dossier` le dit noir sur blanc : « Dossier public →
  accessible à tous (y compris anonymes) ». Héritée `IsAuthenticated`, cette vue
  serait **moins** accessible que la page qu'elle sert par morceaux : le lecteur
  anonyme d'une note publique verrait ses échanges de bloc échouer sur un texte
  qu'il a sous les yeux. Le contrôle n'est pas relâché, il est **déplacé** dans le
  corps de la vue, où il applique `_utilisateur_a_acces_page` — la règle exacte de
  l'écran de lecture. **Deux tests** épinglent qu'un anonyme lit le bloc d'un
  carnet public **et n'y reçoit aucun bouton d'opération**.
- **Doctrine du 404, jamais 403.** Un pk mort, un accès refusé : `Http404`, sans
  distinction. Et surtout **pas** `_reponse_passage_disparu()`, qui déclenche un
  `lectureReload` — recharger la page de qui a demandé UN bloc serait exactement le
  défaut qu'on répare.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/templates/front/includes/_un_bloc_element.html` | **neuf** — le corps de boucle extrait, inclus par les deux chemins |
| `front/templates/front/includes/_blocs_elements.html` | la boucle n'est plus qu'un `{% include %}` (213 → 39 lignes) |
| `hypostasis_extractor/views_element.py` | action `bloc` (GET), `AllowAny`, contrôle explicite, 404 |
| `hypostasis_extractor/tests/test_le_rendu_d_un_seul_bloc.py` | **neuf** — 9 tests |

**Le DOM d'un bloc gagne deux attributs** : `id="bloc-<identifiant_stable>"` (la
cible du swap) et `data-element="<identifiant_stable>"` (le contrat du § 7.1, qui
désigne un bloc par son identifiant stable **et jamais par son pk**). Aucun gabarit
ne le portait — vérifié avant : `rg identifiant_stable front/templates/` ne rendait
rien. `data-element-id` (le pk) **reste**, c'est ce que les boutons postent.

Le placeholder d'un élément masqué reçoit les mêmes attributs : il prend la place
du bloc, il lui faut donc la même cible, sans quoi un démasquage ne pourrait pas
s'échanger.

---

## Deuxième temps — les trois gestes de ligne sont branchés (24 août 2026)

`corriger`, `masquer` et `demasquer` **ne déclenchent plus `lectureReload`**. Ils
répondent avec **le bloc touché**, porteur de `hx-swap-oob="true"`, et HTMX le
substitue à celui qui porte le même `id`. Le reste de l'écran ne bouge pas.

**Pourquoi cela marche alors que les boutons portent `hx-swap="none"`** : HTMX
traite les éléments hors bande **même** quand le swap principal est `none`. C'est
documenté, et c'est vérifié au navigateur ci-dessous.

**`scinder` et `fusionner_avec_le_suivant` gardent le rechargement complet**, et
c'est délibéré : ils renumérotent la page — plusieurs blocs changent d'ordre, et
deux éléments neufs remplacent l'ancien. Un swap d'un seul bloc ne peut pas le
montrer. **Un pk mort le garde aussi** : il signifie qu'un tiers a restructuré la
page, donc que la vue du client est périmée pour de bon — là, recharger est le bon
geste, et c'est le seul cas.

**Un seul chemin de rendu.** `_html_du_bloc()` sert **et** l'endpoint **et** les
réponses d'opération. C'est tout l'objet du chantier : deux chemins finiraient par
rendre un bloc qui ne ressemble plus à ses voisins, sans que rien ne le signale.

### La preuve, au navigateur

Les tests disent ce que le serveur **envoie** ; seul un navigateur dit ce que HTMX
en **fait**. Éprouvé sur https://beta.hypostasia.org/, Chromium piloté par
Playwright depuis le conteneur, sur une **note jetable créée puis supprimée** — les
douze blocs de la note étalon portent tous des ancrages, et masquer en aurait
détaché.

**La méthode** : poser un attribut témoin sur un bloc **voisin** avant le geste. Si
`lectureReload` partait, la zone entière serait remplacée et le témoin
disparaîtrait.

| | |
|---|---|
| blocs au chargement | 3 |
| témoin posé sur le bloc voisin | oui |
| après un clic sur « masquer » | le bloc visé porte `element-masque` |
| **le témoin a survécu** | **oui** — la zone n'a pas été refaite |
| blocs + placeholders | 2 + 1 = 3 |
| erreurs JavaScript | **0** |

### Fichiers modifiés au deuxième temps

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/views_element.py` | `_html_du_bloc()` et `_reponse_de_succes_avec_le_bloc()` ; les trois gestes de ligne basculent ; l'action `bloc` réutilise le helper |
| `front/templates/front/includes/_un_bloc_element.html` | drapeau `pour_swap_oob` → `hx-swap-oob="true"` sur la racine, faux par défaut |
| `hypostasis_extractor/tests/test_le_rendu_d_un_seul_bloc.py` | +8 tests (classe `LeSwapCibleRemplaceLeRechargement`) |
| `hypostasis_extractor/tests/test_views_element.py` | un test mis à jour : `corriger` n'envoie plus `lectureReload`, il envoie le bloc |

### Le coût, mesuré le 24 août 2026

Rendre un bloc construit les blocs de **toute** la page — c'est le prix du chemin
de rendu unique. Mesuré sur la machine du projet, **au repos** (charge 0,38 à
0,60), médiane de 5 tours :

| | **swap d'un bloc** | ce qu'il **remplace** | rapport |
|---|---|---|---|
| page 19 — 210 blocs, 58 770 car. | **68,5 ms** · **1 449 octets** | 159,5 ms · 801 402 octets | **2,3× plus rapide, 553× plus léger** |
| page 3 — 12 blocs, 4 411 car. | 14,3 ms · 4 112 octets | 18,3 ms · 49 590 octets | 1,3× · 12× |

Sur les 68,5 ms de la grosse note, **49,7 ms sont `construire_les_blocs_de_lecture`**
— les 210 blocs construits pour n'en rendre qu'un. C'est le gaspillage assumé du
chemin unique, et **il reste largement gagnant** : la colonne de droite ne compte
même pas la **seconde requête HTTP** vers `/lire/<id>/` ni le `DOMParser` côté
client que `lectureReload` imposait en plus.

**Ce qui n'est pas optimisé, et pourquoi** : on pourrait ne construire que le bloc
visé et tomber sous les 20 ms. Ce serait un **second chemin de rendu**, c'est-à-dire
exactement ce que ce chantier existe pour empêcher. Le jour où le coût gênera, ce
sera à l'intérieur du service — pas à côté de lui.

**La borne à connaître** : le coût est linéaire en nombre de blocs. Une note deux
fois plus grosse que la page 19 coûterait ~140 ms par correction.

### Ce qui n'est toujours PAS fait

**Le panneau d'extractions n'est pas rafraîchi.** Il ne l'était pas davantage
avant : `lectureReload` retire explicitement les `[hx-swap-oob]` de la réponse
qu'il va chercher (`hypostasia.js`), et ne remplace que `#zone-lecture`. Le
périmètre est donc identique — mais après un `masquer`, qui détache des portions,
le panneau reste en retard. C'était vrai hier, ça l'est encore.

---

## Comment tester (à la main) / Manual test

### Test 1 — le bloc servi seul
1. Ouvrir une note sur https://beta.hypostasia.org/ (`jonas` / `admin1234`) et
   relever l'`id` d'un élément (les boutons d'action portent `/elements/<pk>/…`).
2. Aller sur `/elements/<pk>/bloc/`.
3. **Attendu** : le HTML d'un seul bloc — sa gouttière, son filet d'état, son
   corps — sans le conteneur `data-testid="blocs-elements"` de la page.
4. **Attendu** : la balise ouvrante porte `id="bloc-<uuid>"` et
   `data-element="<uuid>"`, où l'uuid est l'`identifiant_stable` de l'élément.

### Test 2 — il ne dérive pas de la page
1. Afficher la note entière, et comparer le bloc rendu à l'écran avec celui que
   l'endpoint sert.
2. **Attendu** : le même markup, au jeton CSRF près.

### Test 3 — les droits
1. En navigation privée (donc anonyme), demander `/elements/<pk>/bloc/` pour une
   note d'un carnet **privé** → **404**.
2. Rendre le carnet **public**, redemander → **200**, et le bloc ne porte **aucun**
   bouton d'opération.
3. Demander un pk qui n'existe pas → **404**.

### Tests automatiques
```bash
docker exec -w /app hypostasia_web python manage.py test \
  hypostasis_extractor.tests.test_le_rendu_d_un_seul_bloc --noinput
```
→ **17 tests, OK** (mesuré le 24 août 2026 : 9 pour l'endpoint, 8 pour le swap).

La non-régression du gabarit extrait :
```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_ancres_detachees_drawer front.tests.test_boutons_elements \
  front.tests.test_lecteur_audio front.tests.test_lecture_elements \
  front.tests.test_oob_lecture_element front.tests.test_rendu_elements \
  hypostasis_extractor.tests.test_views_element --noinput
```
→ **125 tests, OK, en 100 s** (mesuré le 23 août 2026).

Et la non-régression du contrat de réponse des trois gestes :
```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_phases front.tests.test_boutons_elements \
  hypostasis_extractor.tests.test_views_element \
  hypostasis_extractor.tests.test_le_rendu_d_un_seul_bloc --noinput
```
→ **585 tests, OK, en 357 s** (mesuré le 24 août 2026).
