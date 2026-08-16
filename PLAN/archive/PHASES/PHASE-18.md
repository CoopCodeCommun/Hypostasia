# PHASE-18 — Alignement basique par hypostases (version Phase 1)

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-08

---

## 1. Contexte

L'alignement cross-documents par hypostase est le cas d'usage differenciateur du produit. Il ne necessite PAS les embeddings de la Phase 6 — c'est un simple regroupement des extractions existantes par type d'hypostase sur N documents. Les donnees necessaires existent des que les extractions sont typees (ce qui est le cas des la Phase 1). Implementer une version basique maintenant permet de montrer la valeur du produit aux financeurs, valider le concept avec les utilisateurs pilotes (Jean, Ephicentria), et poser les bases UX que la Phase 6 enrichira avec la recherche semantique.

## 2. Prerequis

- **PHASE-08** : l'arbre overlay permet de selectionner plusieurs documents pour l'alignement

## 3. Objectifs precis

- [ ] Bouton "Aligner" accessible depuis la selection multiple dans l'arbre (selectionner 2-6 pages -> clic droit ou bouton "Aligner")
- [ ] Vue tableau croise hypostase x documents (meme layout que l'Etape 6.2 mode alignement, mais sans recherche semantique)
- [ ] Construction du tableau par requete simple : `ExtractedEntity.objects.filter(page__in=pages_selectionnees)` groupe par hypostase (attribut `attr_0`)
- [ ] Cellules avec resume tronque, gaps marques, compteurs
- [ ] Export Markdown du tableau d'alignement
- [ ] Pas de detection de conflits semantiques (ca vient avec les embeddings en Phase 6)
- [ ] Pas d'export PDF (ca vient en Phase 5 avec l'export visuel)

## 4. Fichiers a modifier

- `front/views.py` — action sur un AlignementViewSet ou action sur ArbreViewSet (construction du tableau)
- `front/urls.py` — enregistrement du nouveau ViewSet si necessaire
- `front/templates/front/includes/alignement_tableau.html` — nouveau template, tableau croise hypostase x documents
- `hypostasis_extractor/templatetags/extractor_tags.py` — tags utilitaires pour le rendu du tableau
- `front/templates/front/includes/arbre_dossiers.html` — bouton "Aligner" sur selection multiple

## 5. Criteres de validation

- [ ] Selectionner 3 pages avec des extractions dans l'arbre, lancer l'alignement
- [ ] Le tableau affiche les hypostases en lignes et les documents en colonnes
- [ ] Les cellules vides affichent "gap"
- [ ] Les cellules remplies affichent le resume tronque de l'extraction
- [ ] Export Markdown : le contenu du fichier exporte est correct et lisible
- [ ] Le ViewSet est explicite (`viewsets.ViewSet`, pas `ModelViewSet`) conformement aux conventions

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Avoir au moins 2 documents avec des extractions dans des dossiers**
   - **Attendu** : les documents sont visibles dans l'arbre avec des extractions existantes
2. **Ouvrir la vue d'alignement (depuis l'arbre (selection multiple) ou un bouton dedie dans la toolbar)**
   - **Attendu** : un tableau croise avec les hypostases en lignes et les documents en colonnes
3. **Examiner les cellules du tableau**
   - **Attendu** : chaque cellule montre le nombre d'extractions de ce type dans ce document
4. **Les cellules vides (gaps) sont mises en evidence**
   - **Attendu** : elles montrent les angles morts du debat
5. **Cliquer sur une cellule**
   - **Attendu** : naviguer vers les extractions correspondantes

## 6. Extraits du PLAN.md

> ### Etape 1.12 — Alignement basique par hypostases (version Phase 1)
>
> **Pourquoi des la Phase 1** : l'alignement cross-documents par hypostase est le cas d'usage differenciateur du produit (voir `PLAN/References/exemple alignement.pdf`). Il ne necessite PAS les embeddings de la Phase 6 — c'est un simple regroupement des extractions existantes par type d'hypostase sur N documents. Les donnees necessaires existent des que les extractions sont typees (ce qui est le cas des la Phase 1).
>
> Implementer une version basique maintenant permet de :
> - Montrer la valeur du produit aux financeurs des les premiers tests
> - Valider le concept d'alignement avec les utilisateurs pilotes (Jean, Ephicentria)
> - Poser les bases UX que la Phase 6 enrichira avec la recherche semantique
>
> **Actions** :
> - [ ] Bouton "Aligner" accessible depuis la selection multiple dans l'arbre (selectionner 2-6 pages -> clic droit ou bouton "Aligner")
> - [ ] Vue tableau croise hypostase x documents (meme layout que l'Etape 6.2 mode alignement, mais sans recherche semantique)
> - [ ] Construction du tableau par requete simple : `ExtractedEntity.objects.filter(page__in=pages_selectionnees)` groupe par hypostase (attribut `attr_0`)
> - [ ] Cellules avec resume tronque, gaps marques, compteurs
> - [ ] Export Markdown du tableau d'alignement
> - [ ] Pas de detection de conflits semantiques (ca vient avec les embeddings en Phase 6)
> - [ ] Pas d'export PDF (ca vient en Phase 5 avec l'export visuel)
>
> **Fichiers concernes** : `front/views.py` (action sur un AlignementViewSet ou action sur ArbreViewSet), nouveau template `front/includes/alignement_tableau.html`, `hypostasis_extractor/templatetags/extractor_tags.py`
