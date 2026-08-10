# Couche corpus, phase F — l'écran carnet dans le site

## Ce qui a été fait

L'écran carnet vit désormais dans le site (htmx, CSS, CSRF de base.html) :
en-tête à compteurs dérivés + guide de rédaction, facettes en puces
toujours visibles (cases à cocher natives — état annoncé, fonctionne sans
JS), résumé des filtres avec OU/ET écrits, lignes de note enrichies
(rang, extractions, « dans N carnets », couleurs Wong), boutons ▲▼
d'ordre narratif au clavier, onglets avec pastilles « cible ».

Décisions actées (déléguées par le propriétaire, « sécurité et FALC ») :
puces visibles ; branche de cascade dans base.html ; retrait par
« écriture carnet OU propriété de la note » ; `guide_de_redaction` en
TextField (migration core.0044, appliquée sur dev).

## Tests à réaliser

### Test 1 : suites automatiques
```bash
docker exec hypostasia_dev_web python manage.py test front.tests.test_corpus_phase_e front.tests.test_corpus_phase_f --noinput
```
40 tests verts (29 + 11).

### Test 2 : sur le site
1. Ouvrir `https://hyp.nasjo.fr/carnets/` — la liste s'affiche DANS le
   site (arbre à gauche, pas une page nue).
2. Ouvrir un carnet, créer un axe et des catégories (POST categories/ ou
   shell), cocher des puces : la liste se filtre sans rechargement, l'URL
   porte `?categorie=…`, un F5 garde les cases cochées.
3. Le résumé « X sur Y notes — Type : A OU B » apparaît, « Tout
   afficher » vide les filtres.
4. Boutons ▲▼ (propriétaire) : le premier clic fige l'ordre puis échange ;
   sous filtre, l'échange se fait avec la voisine VISIBLE ; l'épingle se
   transfère en croisant la frontière épinglées/normales.
5. Renseigner `guide_de_redaction` sur un carnet (admin ou shell) : le
   bandeau ambre apparaît en tête.

## Validation contre l'étalon (agent Opus, 8 août)

Tableau B.0-B.10 : B.0/B.1/B.2/B.9 FAITS ; corrigés après validation :
`hx-push-url="true"` (les filtres entrent vraiment dans l'URL), « Tout
afficher » recharge l'écran entier (les cases se décochent), garde sur
`deplacer` non numérique, rang = position affichée (forloop.counter),
onglets cibles en vrais `role="tab"` désactivés, message `role="status"`
après chaque geste d'ordre (« Ordre modifié » / « Déjà à l'extrémité »),
« dans N carnets » ne compte que les carnets visibles du demandeur
(partages non comptés — sous-compte assumé, jamais de fuite), un seul
`aria-live` (celui de #zone-lecture).

## À reporter en phase G

- Boutons épingler/catégoriser DANS l'écran carnet (la vue sait déjà
  cibler avec `ecran=carnet`, aucun bouton ne l'appelle encore).
- Source de la note dans la ligne (fichier · pages · poids).
- Fil d'Ariane à bascule (écran note).
- Validateur hex `RegexValidator(^#[0-9A-Fa-f]{6}$)` sur
  `CategorieDossier.couleur` avant d'ouvrir le champ à l'UI.
- `prefers-reduced-motion` et thème sombre (CSS global du site).
- Unifier les deux sémantiques de `reordonner` (page_ids vs deplacer).

## Limites connues

- Onglets Wikis / Synthèses / Preuves : pastilles « cible », en attente
  de SPEC-synthese et SPEC-selection.
- Fil d'Ariane à bascule (B.8) : reporté à la phase G (écran note), c'est
  là qu'il prend son sens.
- L'exclusion des synthèses se fait encore par parent_page (C.6) : à
  basculer sur type_de_note dès SPEC-synthese phase A.
