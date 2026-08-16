# Audit UX/UI — 8 août 2026

**Méthode** : agent Opus en navigation réelle (Playwright) sur
https://hyp.nasjo.fr (base = copie de prod, 537 notes migrées), anonyme,
lecture seule, comparé aux trois étalons `tmp/maquettes/`. Captures dans
le scratchpad de session (`shots/01` à `12`).

## Ce qui marche (constaté)

Accueil anonyme abouti (onboarding 4 étapes, légende statuts redondante
forme+couleur) ; arbre bibliothèque avec vraies données ; `/carnets/` et
`/carnets/{id}/` : ossature de l'étalon en place (tablist, facettes
role=search + noscript, compteurs dérivés) ; `/lire/{id}/` : colonne 648px
Lora proche de l'étalon, bloc « Dans N carnets » chargé en HTMX, 20
pastilles fonctionnelles ; accessibilité structurelle correcte (aria,
tabindex onglets, cibles tactiles toolbar).

## Défauts constatés (D1-D16)

| # | Défaut | Gravité |
|---|---|---|
| D1 | Extractions inatteignables en mobile (43 boutons DOM, 0 visible à 375px ; hl-extraction sans tabindex/clic) | P1 |
| D2 | Listes sans recherche/pagination : 8 095px de liste pour 120 notes ; arbre injecte 120 lignes dans un tiroir de 320px | P1 |
| D3 | Écrans corpus visuellement hors système (titres bleu lien B612 vs encre Georgia de l'étalon ; pas de :hover ; seule le titre cliquable) | P1 |
| D4 | `/bases/` : état vide non didactique | P1 — CORRIGÉ |
| D5 | Aucun fil d'Ariane, aucun état actif de nav | P1 |
| D6 | Le tiroir bibliothèque recouvre la nav (Carnets/Bases masqués) | P2 |
| D7 | « 0 axes de classement » répété sur 20 carnets, info donnée 3 fois | P2 — CORRIGÉ |
| D8 | Onglets « cible » = 75% de la barre, jargon de spec exposé | P2 — CORRIGÉ |
| D9 | Bloc « Dans N carnets » rendu AU-DESSUS du h1 | P2 — CORRIGÉ |
| D10 | Mobilier PDF dans le flux (16 paragraphes parasites/10 utiles) + OCR brut dans les titres | P2 |
| D11 | Pastilles 16×16px < WCAG 2.5.8 (24px min) ; surlignage quasi invisible ; hl-extraction non focusable | P1 |
| D12 | Aucun thème sombre (les 3 étalons ont le mécanisme 3 états) | P3 |
| D13 | Actions d'écriture offertes à l'anonyme sans indice | P2 |
| D14 | HTML sans Cache-Control → UI périmée constatée en direct | P2 — CORRIGÉ |
| D15 | Homonymes « Mes imports » ×3 indistincts ; owner+compteur collés | P2 |
| D16 | Vue carnet à 46% de l'écran (max-w-3xl vs .zone.large 80rem étalon) | P3 |

## Propositions restantes (backlog priorisé)

- **P1-1** extractions mobiles : hl-extraction cliquable + tabindex + bottom-sheet existant ; gouttière compacte. (`hypostasia.css` ~1490, rendu des éléments)
- **P1-2** recherche + pagination hx-get `?q=&page=` sur `#corpus-notes`.
- **P1-3** `.ligne-note` de l'étalon : grille auto/1fr/auto, titre encre, ligne entière cliquable, survol `--papier-creux`.
- **P1-4** pastilles 24×24px (WCAG 2.5.8) + :focus-visible + surlignage au survol.
- **P1-6** fil d'Ariane `base › carnet › note` sticky + état actif de nav.
- **P2-10** filtre du mobilier PDF + normalisation OCR à l'affichage.
- **P2-11** griser les actions d'écriture en anonyme.
- **P2-13** homonymes : « Mes imports — Antoine R », séparateurs dans l'arbre.
- **P2-14** tiroir sous la barre de nav.
- **P3-15** thème 3 états (étalon) ; **P3-16** `.zone.large` ; **P3-17** tri + compteur `/carnets/` ; **P3-18** monogramme mobile.
- **Transverse** : ~250 lignes de CSS identiques triplées entre les 3
  étalons (`.badge-hypostase`, `.carte-preuve`, `.bouton-plat`, `.toast`,
  `.indicateur-statut`, `.menu-bascule`) — à factoriser dans
  `hypostasia.css` au moment du portage (couche synthèse).
