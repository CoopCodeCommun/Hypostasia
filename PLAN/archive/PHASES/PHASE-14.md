# PHASE-14 — Dashboard consensus + actions statut

**Complexite** : L | **Mode** : Plan then normal | **Prerequis** : PHASE-06, PHASE-09, PHASE-10

---

## 1. Contexte

Le PLAN dit "ce cycle peut etre repete jusqu'a atteindre un consensus", mais l'interface ne donne aucun moyen de savoir ou en est le consensus. L'utilisateur doit compter mentalement les statuts de chaque carte pour repondre a "est-ce qu'on est pret a synthetiser ?". Le dashboard de consensus est le chainage manquant entre les statuts individuels (PHASE-06) et le bouton de synthese (Phase 5). Sans ce dashboard, le garde-fou "consensus avant synthese" est invisible et donc inapplicable. Cette phase implemente le dashboard UI et les actions de changement de statut sur les extractions.

## 2. Prerequis

- **PHASE-06** — Le champ `statut_debat` sur `ExtractedEntity` et les boutons "Marquer comme consensus" / "Rejeter" doivent exister.
- **PHASE-09** — Les pastilles de marge doivent etre en place pour que le dashboard et les pastilles soient coherents visuellement.
- **PHASE-10** — Le drawer vue liste doit exister car le dashboard interagit avec lui (clic sur une extraction bloquante → scroll vers le passage).

## 3. Objectifs precis

### Dashboard de consensus

- [ ] Creer le dashboard accessible via le bouton "Dashboard" dans la barre d'outils (dropdown) ou en bandeau compact en haut de la zone de lecture
- [ ] Compteurs par statut avec icones et couleurs de la charte :
  - ⚫ X consensuels, ▶ X discutables, ▷ X discutes, ! X controverses
- [ ] Barre de progression : % d'extractions en statut CONSENSUEL (les masquees ne comptent pas)
- [ ] Liste des extractions "bloquantes" : CONTROVERSE d'abord, puis DISCUTE avec le plus de commentaires
- [ ] Bouton "Lancer la synthese" grise tant que le seuil n'est pas atteint (defaut 80%)
- [ ] Seuil configurable (ajustable dans la config IA)
- [ ] En mode mono-utilisateur (Phase 1), le seuil est indicatif — le bouton est toujours cliquable avec un avertissement
- [ ] Le dashboard se met a jour automatiquement apres chaque changement de statut (reponse HTMX OOB swap)

### Actions statut sur les extractions

- [ ] Bouton "Marquer comme consensus" sur chaque extraction → passe `statut_debat` a `consensus`
- [ ] Bouton "Rejeter" sur chaque extraction → passe `statut_debat` a `rejete`
- [ ] L'extraction commence en `ouvert`, passe en `en_cours` au premier commentaire
- [ ] Chaque changement de statut met a jour le dashboard (OOB swap) + la pastille de marge + la carte inline/drawer

### Interaction dashboard ↔ texte

- [ ] Clic sur une extraction bloquante dans le dashboard → scroll le texte vers le passage + deplie la carte inline
- [ ] Le dashboard pointe vers les extractions non consensuelles pour faciliter la resolution

## 4. Fichiers a modifier

- `front/views.py` — action `dashboard` sur ExtractionViewSet (calcul des compteurs, % consensus, extractions bloquantes) + actions changement de statut
- `front/templates/front/includes/dashboard_consensus.html` — nouveau template pour le dashboard (compteurs, barre de progression, liste bloquants, bouton synthese)
- `front/templates/front/includes/lecture_principale.html` — integration du dashboard en bandeau ou dropdown
- `front/static/front/css/hypostasia.css` — styles barre de progression, compteurs, bouton grise
- `front/static/front/js/marginalia.js` — interaction dashboard → scroll passage

## 5. Criteres de validation

- [ ] Le dashboard affiche les compteurs corrects par statut (creer des extractions avec differents statuts)
- [ ] La barre de progression reflette le % de consensus
- [ ] Le bouton "Lancer la synthese" est grise quand le % est sous le seuil
- [ ] En mode mono-user, le bouton est cliquable malgre le grisage (avec avertissement)
- [ ] La liste des bloquants montre les CONTROVERSE en premier, puis les DISCUTE
- [ ] Clic sur un bloquant → scroll vers le passage + deplie la carte inline
- [ ] Changement de statut d'une extraction → le dashboard se met a jour (OOB swap)
- [ ] Les pastilles de marge changent de couleur apres un changement de statut

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Cliquer sur le bouton "Dashboard" dans la toolbar** : ouvrir le dashboard de consensus
   - **Attendu** : compteurs par statut (ex: "8 CONSENSUEL, 2 DISCUTE, 1 DISCUTABLE")
   - **Attendu** : barre de progression avec % de consensus (ex: "71% consensus")
2. **Verifier le bouton "Lancer la synthese"** : observer son etat si le % est sous le seuil (80%)
   - **Attendu** : le bouton est grise
3. **Cliquer sur une extraction DISCUTEE dans la liste des bloquants** : selectionner un bloquant
   - **Attendu** : le texte scroll vers le passage et la carte se deplie
4. **Changer le statut d'une extraction (dans la carte)** : marquer comme consensus ou rejeter
   - **Attendu** : le dashboard se met a jour en temps reel (sans rechargement de page, via OOB swap HTMX)
5. **Verifier les pastilles de marge** : observer les cercles colores apres le changement de statut
   - **Attendu** : les pastilles de marge changent de couleur apres le changement de statut

## 6. Extraits du PLAN.md

> **Dashboard de consensus** — accessible via le bouton "Dashboard" dans la barre d'outils (dropdown) ou en bandeau compact :
>
> Mockup cible :
> ```
> ┌─────────────────────────────────────────┐
> │  Debat sur "L'IA dans l'education"      │
> │                                          │
> │  ⚫ 8 consensuels  ▶ 3 discutables      │
> │  ▷ 2 discutes      ! 1 controverse      │
> │                                          │
> │  ████████████░░░░  57% consensus         │
> │                                          │
> │  Bloquants :                             │
> │  ! "L'avenement de l'IA..."   3 comments │
> │  ▶ "L'integration d'outils..." 0 comment │
> │                                          │
> │  [Lancer la synthese]  (grise si < 80%) │
> └─────────────────────────────────────────┘
> ```
>
> - Compteurs par statut avec icones et couleurs de la charte (ajust. 2 + 4)
> - Barre de progression : % d'extractions en statut CONSENSUEL (les masquees ne comptent pas)
> - Liste des extractions "bloquantes" : CONTROVERSE d'abord, puis DISCUTE avec le plus de commentaires
> - Bouton "Lancer la synthese" grise tant que le seuil n'est pas atteint
> - Seuil configurable (defaut 80%, ajustable dans la config IA). En mode mono-user (Phase 1), le seuil est indicatif — le bouton est toujours cliquable avec un avertissement
> - Le dashboard se met a jour automatiquement apres chaque changement de statut (reponse HTMX OOB swap)
>
> **Statut de debat sur les extractions** :
> - [ ] Ajouter un champ `statut_debat` sur `ExtractedEntity` : `ouvert`, `en_cours`, `consensus`, `rejete`
> - [ ] L'extraction commence en `ouvert`, passe en `en_cours` au premier commentaire
> - [ ] Bouton "Marquer comme consensus" et "Rejeter" sur chaque extraction
> - [ ] Affichage visuel du statut dans les cartes d'extraction et dans l'annotation HTML
> - [ ] Couleurs accessibles :
>   - CONSENSUEL → texte `#15803d` sur fond `#f0fdf4` avec icone ⚫
>   - DISCUTABLE → texte `#B61601` sur fond `#fef2f2` avec icone ▶
>   - DISCUTE → texte `#b45309` sur fond `#fffbeb` avec icone ▷
>   - CONTROVERSE → texte `#C2410C` sur fond `#FFF4ED` avec icone !
>
> **Tests E2E** :
> - [ ] Dashboard : verifier les compteurs par statut
> - [ ] Dashboard : verifier que la barre de progression reflette le % de consensus
> - [ ] Dashboard : verifier que le bouton "Lancer la synthese" est grise sous le seuil
> - [ ] Pastilles de marge : verifier que les pastilles sont colorees par statut
> - [ ] Pastilles de marge : clic sur une pastille → deplie la carte inline sous le passage
