# PHASE-06 — Modeles de donnees : statut_debat + masquee

**Complexite** : S | **Mode** : Normal | **Prerequis** : PHASE-01

---

## 1. Contexte

Actuellement, rien n'indique si un debat sur une extraction est ouvert, resolu, ou en attente de consensus. L'utilisateur ne sait pas ou en est le debat global sur un texte. Le statut visuel est un prerequis pour le "dashboard de consensus" et pour le garde-fou "pas de synthese sans consensus". De plus, il manque un mecanisme de curation (masquer les extractions non pertinentes).

## 2. Prerequis

- **PHASE-01** — Le fichier CSS extrait (`hypostasia.css`) doit exister pour y definir les variables CSS de statut.

## 3. Objectifs precis

- [ ] Ajouter un champ `statut_debat` sur `ExtractedEntity` avec la taxonomie unifiee :
  ```python
  STATUT_DEBAT_CHOICES = [
      ("consensuel", "Consensuel"),       # Vert — accord atteint
      ("discutable", "Discutable"),       # Orange — a debattre
      ("discute", "Discuté"),            # Ambre — debat en cours
      ("controverse", "Controversé"),     # Rouge — desaccord fort
  ]
  statut_debat = CharField(max_length=20, choices=STATUT_DEBAT_CHOICES, default="discutable")
  ```
- [ ] L'extraction commence en `discutable`, passe en `discute` au premier commentaire

  | Valeur modele | Label UI | Couleur CSS | Variable CSS |
  |---|---|---|---|
  | consensuel | CONSENSUEL | Vert #16a34a | --color-consensuel |
  | discutable | DISCUTABLE | Orange #ea580c | --color-discutable |
  | discute | DISCUTE | Ambre #d97706 | --color-discute |
  | controverse | CONTROVERSE | Rouge #dc2626 | --color-controverse |
- [ ] Ajouter un champ `masquee` (BooleanField, defaut False) sur `ExtractedEntity` pour la curation
- [ ] Creer la migration correspondante
- [ ] Definir les variables CSS dans `:root` pour les couleurs de statut :
  - CONSENSUEL : texte `#15803d`, fond `#f0fdf4`, accent `#429900`
  - DISCUTABLE : texte `#B61601`, fond `#fef2f2`, accent `#B61601`
  - DISCUTE : texte `#b45309`, fond `#fffbeb`, accent `#D97706`
  - CONTROVERSE : texte `#C2410C`, fond `#FFF4ED`, accent `#FF4000`

## 4. Fichiers a modifier

- `hypostasis_extractor/models.py` — ajouter `statut_debat` et `masquee` sur `ExtractedEntity`
- `hypostasis_extractor/migrations/` — nouvelle migration auto-generee
- `front/static/front/css/hypostasia.css` (ou `base.html` si CSS encore inline) — variables CSS `:root`

## 5. Criteres de validation

- [ ] `uv run python manage.py makemigrations` genere une migration sans erreur
- [ ] `uv run python manage.py migrate` s'execute sans erreur
- [ ] `ExtractedEntity.objects.create(...)` cree une entite avec `statut_debat="discutable"` et `masquee=False` par defaut
- [ ] Les variables CSS sont definies dans `:root`
- [ ] `uv run python manage.py check` passe sans erreur

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir http://localhost:8000/admin/** : naviguer vers les modeles d'extraction
   - **Attendu** : les modeles d'extraction ont les nouveaux champs `statut_debat` et `masquee`
2. **Modifier le statut d'une extraction dans l'admin** : changer la valeur du champ `statut_debat`
   - **Attendu** : la valeur est sauvegardee (CONSENSUEL, DISCUTABLE, DISCUTE, CONTROVERSE)
3. **Cocher "masquee" sur une extraction dans l'admin** : activer le booleen `masquee`
   - **Attendu** : l'extraction reste en base mais n'apparait plus dans l'interface front (si l'UI est deja adaptee, sinon juste verifier le champ en admin)

## 6. Extraits du PLAN.md

> ### Etape 1.4 — Statut de debat sur les extractions
>
> **Pourquoi** : actuellement, rien n'indique si un debat sur une extraction est ouvert, resolu, ou en attente de consensus. L'utilisateur ne sait pas ou en est le debat global sur un texte. Le statut visuel est un prerequis pour le "dashboard de consensus" (voir section UX) et pour le garde-fou "pas de synthese sans consensus".
>
> **Actions** :
> - [ ] Ajouter un champ `statut_debat` sur `ExtractedEntity` : `ouvert`, `en_cours`, `consensus`, `rejete`
> - [ ] L'extraction commence en `ouvert`, passe en `en_cours` au premier commentaire
> - [ ] Bouton "Marquer comme consensus" et "Rejeter" sur chaque extraction
> - [ ] Affichage visuel du statut dans les cartes d'extraction et dans l'annotation HTML
> - [ ] Appliquer les couleurs accessibles de la charte :
>   - CONSENSUEL → texte `#15803d` sur fond `#f0fdf4` avec icone ⚫
>   - DISCUTABLE → texte `#B61601` sur fond `#fef2f2` avec icone ▶
>   - DISCUTE → texte `#b45309` sur fond `#fffbeb` avec icone ▷
>   - CONTROVERSE → texte `#C2410C` sur fond `#FFF4ED` avec icone !
> - [ ] Definir les couleurs en variables CSS dans `:root` :
>   ```css
>   --statut-consensuel-text: #15803d;
>   --statut-discutable-text: #B61601;
>   --statut-discute-text: #b45309;
>   --statut-controverse-text: #C2410C;
>   --statut-consensuel-bg: #f0fdf4;
>   --statut-discutable-bg: #fef2f2;
>   --statut-discute-bg: #fffbeb;
>   --statut-controverse-bg: #FFF4ED;
>   --statut-consensuel-accent: #429900;
>   --statut-discutable-accent: #B61601;
>   --statut-discute-accent: #D97706;
>   --statut-controverse-accent: #FF4000;
>   ```
>
> Note : le prerequis "consensus avant synthese" sera actif seulement apres la Phase 2 (users).
> En mode mono-utilisateur, le statut est indicatif.
>
> Si en pratique la nuance DISCUTE/DISCUTABLE s'avere trop fine pour les utilisateurs,
> fusionner en un seul statut "EN DEBAT" (`#B61601`, icone ▶). A valider en test utilisateur.
