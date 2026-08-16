# PHASE-26a — Filtre contributeur sur les commentaires

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-25, PHASE-19

---

## 1. Contexte

Quand plusieurs personnes debattent sur un document, le facilitateur a besoin de filtrer par contributeur pour preparer les reunions de consensus ("qu'est-ce que Michel a dit ?"). Ce filtre se combine avec la heat map (PHASE-19) pour visualiser la temperature du debat du point de vue d'un contributeur specifique.

## 2. Prerequis

- PHASE-25 (Users et partage) — le filtre contributeur necessite de vrais utilisateurs (plus de prenoms libres).
- PHASE-19 (Heat map du debat) — necessaire pour le filtrage combine heat map + contributeur.

## 3. Objectifs precis

### Etape 2.4 — Filtre "qui a dit quoi" sur les commentaires

- [ ] Menu deroulant "Filtrer par contributeur" en haut du drawer vue liste
  - Liste des users ayant commente au moins une extraction du document
  - Chaque entree montre le nom + le nombre de commentaires (ex: "Michel (7)")
  - Option "Tous" pour restaurer la vue complete
- [ ] Quand un contributeur est selectionne :
  - Le drawer ne montre que les extractions ayant au moins un commentaire de ce contributeur
  - Les commentaires des autres contributeurs restent visibles mais en opacite reduite (pas masques — le contexte du debat est utile)
  - Les pastilles de marge ne montrent que les extractions commentees par ce contributeur
- [ ] La heat map peut se combiner avec le filtre : "montrer la temperature du debat du point de vue de Michel" (seuls ses commentaires comptent dans le calcul)

## 4. Fichiers a modifier

- `front/views.py` — ExtractionViewSet (action filtre par contributeur)
- `front/templates/front/includes/extraction_results.html` — drawer avec filtre contributeur
- `front/static/front/js/marginalia.js` — filtrage des pastilles par contributeur
- `front/static/front/css/hypostasia.css` — opacite reduite pour commentaires hors filtre
- `front/serializers.py` — serializers pour filtres contributeur

## 5. Criteres de validation

- [ ] Le menu "Filtrer par contributeur" liste les users avec leur nombre de commentaires
- [ ] Selectionner un contributeur filtre les extractions et les pastilles de marge
- [ ] Les commentaires des autres contributeurs sont visibles mais en opacite reduite
- [ ] Le filtre "Tous" restaure la vue complete
- [ ] Le filtre se combine avec la heat map (temperature par contributeur)
- [ ] `uv run python manage.py check` passe

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir un document avec des commentaires de plusieurs utilisateurs**
   - **Attendu** : le document s'affiche avec toutes les extractions et commentaires
2. **Activer le filtre "qui a dit quoi" — selectionner un contributeur**
   - **Attendu** : seules les extractions/commentaires de ce contributeur sont mises en evidence
3. **Combiner le filtre contributeur avec la heat map**
   - **Attendu** : la temperature du debat est filtree par personne

## 6. Extraits du PLAN.md

> ### Etape 2.4 — Filtre "qui a dit quoi" sur les commentaires
>
> **Argumentaire** : quand 5 personnes debattent sur un document avec 20 extractions, les fils de
> commentaires melangent les voix de tout le monde. Avant une reunion de consensus, le facilitateur
> a besoin de repondre a "qu'est-ce que Michel a dit sur ce texte ?" ou "quelles extractions Sarah
> a-t-elle commentees ?" sans ouvrir les 20 fils un par un.
>
> C'est un besoin de **preparation de reunion** : le facilitateur veut arriver en sachant qui a dit quoi,
> ou sont les convergences et les divergences entre personnes. Sans ce filtre, il doit lire l'integralite
> des fils, ce qui prend 30 minutes pour un document bien debattu.
>
> **Actions** :
> - [ ] Menu deroulant "Filtrer par contributeur" en haut du drawer vue liste
>   - Liste des users ayant commente au moins une extraction du document
>   - Chaque entree montre le nom + le nombre de commentaires (ex: "Michel (7)")
>   - Option "Tous" pour restaurer la vue complete
> - [ ] Quand un contributeur est selectionne :
>   - Le drawer ne montre que les extractions **ayant au moins un commentaire de ce contributeur**
>   - Les commentaires des autres contributeurs restent visibles mais en opacite reduite (pas masques — le contexte du debat est utile)
>   - Les pastilles de marge ne montrent que les extractions commentees par ce contributeur
> - [ ] La heat map (Etape 1.15) peut se combiner avec le filtre : "montrer la temperature du debat du point de vue de Michel" (seuls ses commentaires comptent dans le calcul)
>
> **Fichiers concernes** : `front/views.py` (ExtractionViewSet — action filtre par contributeur), `extraction_results.html` (drawer), `marginalia.js` (filtrage des pastilles), CSS (opacite reduite pour les commentaires hors filtre)
