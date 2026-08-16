# Couche corpus, phase F : l'ecran carnet contre l'etalon

**Date :** 2026-08-08
**Migration :** Oui

**Quoi / What :** l'UI carnet integree au site, construite contre l'etalon
tmp/maquettes/corpus.html a partir du cahier des charges
PLAN/corpus-phase-f-cahier-des-charges.md.

**Decisions du proprietaire (deleguees le 8 aout, « securite et FALC
d'abord ») :**
1. Facettes en PUCES TOUJOURS VISIBLES (comme l'etalon), realisees en
   cases a cocher natives habillees — etat annonce nativement, fonctionne
   sans JavaScript (bouton Filtrer en noscript).
2. Integration par une BRANCHE dans la cascade de base.html (le patron
   existant du depot), pas de refonte en blocks.
3. Retrait d'une note : ecriture sur le carnet OU propriete de la note —
   personne ne peut rendre votre note publique sans que vous puissiez
   l'en sortir. Teste.

### Ce que l'ecran fait desormais / What the screen now does
- En-tete : « N notes · N axes · N categories » (tout derive), visibilite
  icone + mot, guide de redaction (nouveau champ Dossier.guide_de_redaction,
  migration core.0044 — la spec § 2 le disait « Pris », § 3 avait oublie
  le champ).
- Facettes : puces par axe avec compteur « Type (3) », point colore
  (couleur choisie ou palette Wong — jamais la couleur seule, § 8.3),
  restauration depuis l'URL (?categorie=), etat vide explicite.
- Resume des filtres : « X sur Y notes — Type : AAP OU Subvention ET ... »
  avec OU et ET ecrits, bouton « Tout afficher ».
- Ligne de note : rang ou epingle, « N extractions », « dans N carnets »
  si N>1 (annotations en une requete), etiquettes teintees.
- Ordre narratif au clavier : boutons monter/descendre (§ 8.3), echange
  des voisines VISIBLES avec transfert d'epingle (etalon:1188-1194) ;
  premier geste : l'ordre courant est fige (1..n). Les filtres actifs
  accompagnent chaque geste.
- Onglets : Notes actif avec compteur ; Wikis / Syntheses dirigees /
  Selection des preuves en pastille « cible » (le produit ne pretend pas).
- epingler/categoriser rendent la liste (ecran=carnet) ou le bloc de la
  note selon l'origine du geste.

### Fichiers / Files
| Fichier | Changement |
|---|---|
| `core/models.py` | + `Dossier.guide_de_redaction`, + `CategorieDossier.couleur_effective` (palette Wong) |
| `core/migrations/0044_dossier_guide_de_redaction.py` | Migration du champ |
| `front/views_corpus.py` | Contexte enrichi, phrase des filtres, double contrat reordonner, cible selon l'ecran, rendu base.html vs HTMX |
| `front/templates/front/base.html` | + branches carnet_preloaded / carnets_liste_preloaded |
| `front/templates/front/corpus/` | carnet_detail et carnets_liste en includes du site ; notes_du_carnet avec resume et boutons |
| `front/tests/test_corpus_phase_f.py` | 11 tests (URL, resume, ordre, epingle transferee, cible d'ecran, compteurs) |

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0044`
  (guide_de_redaction, appliquee sur dev).

---

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

