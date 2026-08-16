# PHASE-10 — Refonte layout : drawer vue liste

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-09

> **Evolution PHASE-26g (2026-03-18)** : le drawer est devenu un **hub d'analyse** avec 4 etats
> (vide, confirmation, en cours, termine). La largeur est passee a 36rem. Le bouton "Analyser"
> dans la toolbar a ete supprime — tout se lance depuis le drawer. La progression est 100% WebSocket
> (zero polling HTTP). Voir [PHASE-26g](PHASE-26g.md) pour le detail.

---

## 1. Contexte

Le drawer vue liste est l'outil du facilitateur pour scanner l'ensemble du debat. Tandis que les pastilles de marge et les cartes inline (PHASE-09) donnent une vue contextuelle passage par passage, le drawer offre une vue d'ensemble de toutes les extractions en liste scrollable. C'est un overlay a droite (36rem, position fixed) qui ne consomme jamais de largeur permanente — il s'ouvre sur demande et se ferme facilement.

## 2. Prerequis

- **PHASE-09** — Les pastilles de marge et cartes inline doivent exister car le drawer interagit avec elles (clic sur une carte dans le drawer → scroll vers le passage + deplie la carte inline).

## 3. Objectifs precis

- [ ] Creer le drawer overlay a droite (32rem, position fixed, transition `translateX`)
- [ ] Toggle via touche `E` ou bouton "Vue liste" / "Toutes les extractions" dans la barre d'outils
- [ ] Fermeture : touche `E`, `Escape`, ou clic sur le backdrop
- [ ] Afficher toutes les cartes d'extraction en mode compact (une ligne par carte) :
  - Pastille hypostase coloree + debut du resume IA (truncate ~60 chars) + indicateurs (commentaires, sources, statut)
- [ ] Expansion au clic : clic sur une carte compacte → deploie le contenu complet (accordeon, une seule carte ouverte a la fois)
- [ ] Indicateurs de densite sur la carte compacte :
  - Nombre de commentaires (badge `💬 12`)
  - Nombre de sources externes (badge `📎 3`)
  - Bordure gauche dont l'epaisseur encode la densite : 2px (0 commentaire), 3px (1-3), 4px (4+)
  - Couleur de bordure = couleur du statut de debat
- [ ] Clic sur une carte dans le drawer → scroll le texte vers le passage correspondant + deplie la carte inline
- [ ] Les deux interactions sont bidirectionnelles : carte inline ↔ drawer
- [ ] Tri des cartes (menu deroulant en haut du drawer) :
  - Par position dans le texte (defaut)
  - Par activite recente (derniers commentaires en haut)
  - Par statut de debat (CONTROVERSE en haut, CONSENSUEL en bas)
- [ ] Curation post-extraction dans le drawer :
  - Bouton "Masquer" (icone oeil barre) sur les cartes sans commentaire
  - Toggle en bas du drawer : "Voir les X extractions masquees" → affiche en opacite reduite avec bouton "Restaurer"
- [ ] Compteur en haut du drawer : "≡ 12 extractions" + bouton fermer [✕]

## 4. Fichiers a modifier

- `front/templates/front/includes/extraction_results.html` — adaptation pour la vue liste drawer (mode compact + expansion)
- `front/templates/front/includes/drawer_vue_liste.html` — nouveau template pour le drawer overlay
- `front/static/front/js/marginalia.js` — ajout de la logique drawer (toggle, accordeon, scroll bidirectionnel, tri)
- `front/static/front/css/hypostasia.css` — styles drawer overlay, carte compacte, indicateurs de densite, transitions
- `front/views.py` — action masquer/restaurer sur ExtractionViewSet
- `hypostasis_extractor/models.py` — utiliser le champ `masquee` (ajoute en PHASE-06) sur `ExtractedEntity`
- `front/utils.py` — filtrage `entites.filter(masquee=False)` dans l'annotation HTML

## 5. Criteres de validation

- [ ] Touche `E` ouvre/ferme le drawer overlay a droite
- [ ] Le drawer affiche toutes les extractions en mode compact (une ligne par carte)
- [ ] Clic sur une carte compacte → expansion du contenu complet (accordeon)
- [ ] Clic sur une carte dans le drawer → scroll du texte vers le passage + deplie la carte inline
- [ ] Le tri fonctionne (position, activite recente, statut)
- [ ] Le bouton "Masquer" est present uniquement sur les cartes sans commentaire
- [ ] Les extractions masquees disparaissent des pastilles de marge et du drawer
- [ ] Le toggle "Voir les X masquees" affiche les cartes masquees en opacite reduite
- [ ] Les indicateurs de densite (commentaires, sources, epaisseur bordure) sont corrects
- [ ] Fermeture via `E`, `Escape`, ou clic backdrop

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Appuyer sur la touche `E`** : ouvrir le drawer vue liste
   - **Attendu** : un drawer s'ouvre a droite avec la liste de toutes les extractions (overlay a droite, fond assombri, liste de cartes compactes)
2. **Verifier les infos de chaque carte compacte** : inspecter le contenu du drawer
   - **Attendu** : hypostase, debut du resume, statut (pastille coloree), nb commentaires
3. **Cliquer sur une carte dans le drawer** : selectionner une extraction
   - **Attendu** : le texte scroll vers le passage concerne et la carte inline se deplie
4. **Verifier les controles** : inspecter le haut du drawer
   - **Attendu** : tri (par position, par statut, par hypostase), filtre
5. **Verifier le bas du drawer** : scroller jusqu'en bas
   - **Attendu** : compteur "3 masquees" + lien "Voir masquees"
6. **Appuyer sur `E` ou cliquer en dehors** : fermer le drawer
   - **Attendu** : le drawer se ferme
7. **Observer la largeur du drawer** : verifier la mise en page
   - **Attendu** : le texte reste visible sous le drawer (le drawer ne prend que ~40% de largeur)

## 6. Extraits du PLAN.md

> **Mockup — Drawer vue liste (overlay)** :
>
> ```
> ┌──────────────────────────────────┬─────────────────────────┐
> │                                  │ ≡ 12 extractions   [✕]  │
> │   Texte de l'article             │                         │
> │   toujours visible               │ ┌─────────────────────┐ │
> │   en dessous                     │ │ CONJECTURE     ● DS │ │
> │                                  │ │ L'IA va trans...    │ │
> │                                  │ │ 💬 3  📎 2         │ │
> │                                  │ └─────────────────────┘ │
> │                                  │ ┌─────────────────────┐ │
> │                                  │ │ LOI            ○ CS │ │
> │                                  │ │ La loi d'Amara...   │ │
> │                                  │ │ 💬 1               │ │
> │                                  │ └─────────────────────┘ │
> │                                  │ ┌─────────────────────┐ │
> │                                  │ │ PHENOMENE      ● DT │ │
> │                                  │ │ Le marche de...     │ │
> │                                  │ └─────────────────────┘ │
> │                                  │                         │
> │                                  │ Curation : 2 masquees   │
> │                                  │ [Voir masquees]         │
> └──────────────────────────────────┴─────────────────────────┘
> ```
>
> **Actions** :
> - [ ] Drawer vue liste : overlay droit (32rem, position fixed, transition translateX)
>   - Toggle via touche E ou bouton "Toutes les extractions" dans la barre d'outils
>   - Affiche toutes les cartes en mode compact (tri, filtre, curation)
>   - Clic sur une carte dans le drawer → scroll le texte vers le passage + deplie la carte inline
>   - Fermeture : touche E, Escape, ou clic sur le backdrop
>
> **Hierarchie des cartes** (ajust. 9) :
> - [ ] Mode compact dans le drawer vue liste : chaque carte affiche une seule ligne — pastille hypostase coloree + debut du resume IA (truncate a ~60 chars) + indicateurs
> - [ ] Expansion au clic : accordeon, une seule carte ouverte a la fois
> - [ ] Indicateurs de densite : commentaires, sources, bordure gauche epaisseur variable
> - [ ] Curation post-extraction : bouton "Masquer" sur les cartes sans commentaire
>   - Utilise le champ `masquee` sur `ExtractedEntity` (ajoute en PHASE-06)
>   - Garde : si `extraction.commentaires.count() > 0`, le bouton "Masquer" est absent
>   - Toggle "Voir les X extractions masquees" en bas du drawer
>   - `front/utils.py` doit filtrer : `entites.filter(masquee=False)`
> - [ ] Tri des cartes : par position (defaut), par activite recente, par statut de debat
