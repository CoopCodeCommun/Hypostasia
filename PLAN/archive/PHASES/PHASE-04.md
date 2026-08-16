# PHASE-04 — CRUD manquants dans le front

**Complexite** : M | **Mode** : Normal | **Prerequis** : aucun

---

## 1. Contexte

Plusieurs operations CRUD basiques manquent dans l'interface : suppression de page, renommage/suppression de dossier, suppression d'extraction manuelle, modification/suppression de commentaire. Ces manques obligent l'utilisateur a passer par l'admin Django ou a ne pas pouvoir faire ces operations du tout.

## 2. Prerequis

Aucun. Cette phase est independante.

## 3. Objectifs precis

- [ ] Suppression de page (avec confirmation HTMX — SweetAlert2 ou modal)
- [ ] Renommage de dossier (inline editing ou modal HTMX)
- [ ] Suppression de dossier (vide uniquement, ou avec reclassement des pages en orphelines)
- [ ] Suppression d'extraction manuelle
- [ ] Modification/suppression de commentaire

Chaque action doit :
- Utiliser un `@action` sur le ViewSet concerne
- Valider via un DRF Serializer (pas de Django Form)
- Retourner un partial HTML (HTMX swap) — jamais du JSON pour l'UI
- Suivre les conventions du skill `django-htmx-readable` (noms verbeux, commentaires bilingues)

## 4. Fichiers a modifier

- `front/views.py` — ajouter les actions `@action` sur les ViewSets existants (PageViewSet, DossierViewSet, ExtractionViewSet)
- `front/serializers.py` — ajouter les serializers de validation si necessaire
- `front/templates/front/includes/` — partials HTMX pour les confirmations et retours visuels
- `front/templates/front/includes/arbre_dossiers.html` — mise a jour apres suppression/renommage

## 5. Criteres de validation

- [ ] On peut supprimer une page depuis l'interface (avec confirmation)
- [ ] On peut renommer un dossier depuis l'interface
- [ ] On peut supprimer un dossier vide depuis l'interface
- [ ] On peut supprimer une extraction manuelle
- [ ] On peut modifier et supprimer un commentaire
- [ ] Chaque action renvoie un partial HTML (pas de JSON pour l'UI)
- [ ] `uv run python manage.py check` passe sans erreur

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Clic droit ou menu contextuel sur une page dans l'arbre** : option "Supprimer" visible
   - **Attendu** : confirmation demandee, puis la page disparait de l'arbre
2. **Clic droit sur un dossier** : options "Renommer" et "Supprimer" visibles
   - **Attendu renommer** : le nom change dans l'arbre sans rechargement
   - **Attendu supprimer vide** : le dossier disparait
   - **Attendu supprimer avec pages** : message d'avertissement "Ce dossier contient X pages"
3. **Verifier les pages orphelines** : supprimer un dossier parent contenant des pages
   - **Attendu** : les pages orphelines restent accessibles dans la racine de l'arbre apres suppression du dossier parent

## 6. Extraits du PLAN.md

> ### Etape 1.2 — CRUD manquants dans le front
>
> **Actions** :
> - [ ] Suppression de page (avec confirmation HTMX)
> - [ ] Renommage de dossier
> - [ ] Suppression de dossier (vide uniquement, ou avec reclassement des pages en orphelines)
> - [ ] Suppression d'extraction manuelle
> - [ ] Modification/suppression de commentaire
>
> **Fichiers concernes** : `front/views.py`, `front/serializers.py`, templates `front/includes/`
