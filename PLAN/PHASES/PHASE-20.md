# PHASE-20 — Notifications de progression

**Complexite** : S | **Mode** : Normal | **Prerequis** : PHASE-14

---

## 1. Contexte

Le dashboard de consensus montre l'etat statique du debat a un instant T. La heat map montre l'intensite spatiale. Mais aucune brique ne repond a la question temporelle : "est-ce que ca avance ? est-ce que c'est bloque ? qu'est-ce qui a change depuis ma derniere visite ?" Sans cette facette, l'utilisateur doit comparer mentalement avec son souvenir, ce qui cree de l'inertie — le debat stagne parce que personne ne sait qu'il stagne. Les notifications sont le signal que la geometrie du debat a change de forme.

En Phase 1 (mono-utilisateur, pas d'auth), les notifications sont de simples indicateurs visuels in-app, pas des push ou des emails. Elles apparaissent quand l'utilisateur ouvre un document.

## 2. Prerequis

- **PHASE-14** : dashboard de consensus (les donnees de statut et de comptage doivent exister pour calculer les mouvements)

## 3. Objectifs precis

### Phase 1 — notifications in-app

- [ ] **Systeme de "derniere visite"** : stocker un timestamp `derniere_visite` en `localStorage` pour chaque page (Phase 1 sans auth)
- [ ] **Calcul des mouvements** : au chargement d'une page, comparer l'etat actuel avec l'etat a la derniere visite. Changements detectes :
  - Nombre de commentaires ajoutes depuis `derniere_visite`
  - Extractions dont le statut a change
  - Extractions sans commentaire (orphelines)
  - Seuil de consensus franchi (vers le haut ou vers le bas)
- [ ] **Bandeau de notification** : partial HTMX en haut de la zone de lecture, affiche les mouvements detectes. Bouton [x] pour fermer. Le bandeau disparait apres consultation (mise a jour du timestamp)
- [ ] **Notification de seuil** : quand le % de consensus depasse le seuil configure (defaut 80%), bandeau special avec bouton "Lancer la synthese" actif
- [ ] **Pas de push, pas d'email en Phase 1** — tout est in-app, visible a l'ouverture du document

> **Note** : Le bouton "Lancer la synthese" affiche dans le bandeau est un placeholder disabled jusqu'a PHASE-28 (wizard). Ne pas tenter de le wirer a un endpoint.

### Phase 2+ — previsions (non implementees dans cette phase)

- Migration du timestamp en base (`DerniereVisite` : user + page + timestamp)
- Notifications par email (digest quotidien ou hebdomadaire)
- Mouvements sociaux : desequilibre de participation, mentions
- Mouvements structurels : gaps d'alignement, couverture desequilibree
- Page "Centre de notifications" avec historique des mouvements

## 4. Fichiers a modifier

- `front/views.py` — LectureViewSet : calcul des mouvements au chargement de la page
- `front/templates/front/includes/bandeau_notification.html` — nouveau template, bandeau de notification HTMX
- `front/templates/front/includes/lecture_principale.html` — inclusion du bandeau en haut de la zone de lecture
- `front/static/front/js/marginalia.js` — gestion du localStorage `derniere_visite` (lecture/ecriture du timestamp)

## 5. Criteres de validation

- [ ] Premiere visite : pas de bandeau (rien a comparer)
- [ ] Ajouter des commentaires, revenir sur la page : le bandeau affiche "N nouveaux commentaires"
- [ ] Changer le statut de 2 extractions, revenir : le bandeau affiche "2 extractions -> CONSENSUEL"
- [ ] Atteindre le seuil de consensus : bandeau special avec bouton "Lancer la synthese"
- [ ] Fermer le bandeau (x) : il ne reapparait pas au rechargement
- [ ] Le timestamp `derniere_visite` est correctement stocke et lu depuis `localStorage`

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir un document — noter l'etat. Fermer l'onglet.**
   - **Attendu** : la page s'affiche normalement, le timestamp de derniere visite est enregistre
2. **Depuis un autre onglet ou en admin : ajouter un commentaire ou changer un statut d'extraction**
   - **Attendu** : la modification est enregistree en base
3. **Reouvrir le document**
   - **Attendu** : un bandeau en haut indique "Depuis votre derniere visite : 2 extractions → CONSENSUEL, 3 commentaires" (ou equivalent)
4. **Cliquer sur le bandeau ou le bouton fermer**
   - **Attendu** : le bandeau disparait
5. **Recharger la page**
   - **Attendu** : le bandeau ne reapparait pas (la derniere visite a ete mise a jour)

## 6. Extraits du PLAN.md

> ### Etape 1.16 — Notifications de progression et facette temporelle de la geometrie du debat
>
> **Argumentaire** : le dashboard de consensus montre l'etat **statique** du debat a un instant T. La heat map montre l'intensite **spatiale**. Mais aucune brique ne repond a la question **temporelle** : "est-ce que ca avance ? est-ce que c'est bloque ? qu'est-ce qui a change depuis ma derniere visite ?"
>
> Les notifications sont le **signal que la geometrie du debat a change de forme**. Pas un jugement — une observation : "quelque chose a bouge".
>
> **Niveau 1 — Phase 1 (mono-utilisateur, notifications in-app)** :
> Mouvements detectes :
> - **Seuil de consensus atteint** : "Ce document a atteint 80% de consensus. Pret pour une synthese ?"
> - **Extractions orphelines** : "5 extractions n'ont aucun commentaire depuis leur creation."
> - **Statut change** : "2 extractions sont passees de DISCUTE a CONSENSUEL depuis votre derniere visite."
> - **Nouveaux commentaires** : "3 nouveaux commentaires depuis votre derniere visite."
>
> **Actions Phase 1** :
> - [ ] Systeme de "derniere visite" : timestamp `derniere_visite` en `localStorage` par page
> - [ ] Calcul des mouvements au chargement : commentaires ajoutes, statuts changes, orphelines, seuil franchi
> - [ ] Bandeau de notification HTMX en haut de la zone de lecture, bouton [x] pour fermer
> - [ ] Notification de seuil (80% consensus) avec bouton "Lancer la synthese"
> - [ ] Pas de push, pas d'email en Phase 1
>
> **Lien avec la geometrie du debat** : chaque notification est un evenement geometrique — un deplacement dans l'une des facettes du dodecaedre (statistique, sociale, temporelle, structurelle, thermique, spatiale).
>
> **Fichiers concernes** : `front/views.py` (calcul des mouvements), nouveau template `bandeau_notification.html`, `marginalia.js` (gestion localStorage).
