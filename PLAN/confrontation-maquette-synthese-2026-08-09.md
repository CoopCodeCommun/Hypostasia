# Confrontation maquette — écrans synthèse (phase H/I), 9 août 2026

Rapport de l'agent de confrontation (Playwright, parcours réels
anonymes sur hyp.nasjo.fr, carnet public « Démonstration », synthèse
671 à 8 citations/verdicts réels, wiki 1 à 9 citations) face à l'étalon
`tmp/maquettes/corpus.html`. Critique et priorisation par le skill
frontend-design. La bascule CSS (PLAN/bascule-css-cahier-des-charges.md)
traitera une partie des divergences : chaque item porte son moment.

## P0 — corrigent le SENS du produit (avant ou pendant la bascule CSS)

1. **Les verdicts sont invisibles au fil du texte.** 6 citations sur 8
   sont « Faible » et rien ne le montre : pas de coloration des
   affirmations (`data-verification` de l'étalon), pas de légende, pas
   de compteur en en-tête. Un lecteur pressé lit l'article comme
   entièrement fiable — l'inverse exact de la promesse « synthèse
   contestable ». → Liseré/fond par état sur les paragraphes, légende
   des états (avec leurs définitions), compteur « 2 vérifiées ·
   6 faibles » dans l'en-tête ET dans les lignes de liste.
2. **L'état « non sourcé » n'existe pas à l'écran.** Un paragraphe sans
   marqueur est indistinguable d'un paragraphe sourcé. → Le calcul
   d'affichage prévu (fiche G) : marquer les paragraphes sans renvoi.
3. **Un article ouvert par l'arbre latéral perd tout** (/lire/672/ :
   ni bandeau, ni renvois, ni verdicts — le texte nu). Une synthèse lue
   sans ses verdicts est dangereuse. → Rediriger les Pages WIKI/SYNTHESE
   de l'écran lecture vers l'écran article (ou y rendre les renvois).
4. **Navigation cassée** : aucune URL poussée (article non partageable
   — un « acte daté opposable » doit avoir une adresse), history.back()
   sort du site, aucun bouton retour-liste, onglet actif figé sur
   « Notes » après bascule (aria-selected ment). → hx-push-url sur
   onglets et articles, bouton « ◀ Tous les wikis / Toutes les
   synthèses », JS d'état d'onglet (ou renvoyer la barre avec chaque
   panneau).
5. **Le compteur d'écartées est caché** derrière un pli non chiffré
   (« Calcul en cours… » si replié, intersect once). → Le chiffre DANS
   le summary (« 46 extractions non reprises »), chargé au rendu de
   l'article, pas à l'intersection.

## P1 — frottements d'usage réels (pendant la bascule CSS)

6. **Panneau de preuve en pied d'article** : le clic sur [N] emporte le
   lecteur en bas (paragraphe lu à y=−315) sans retour. → Panneau
   latéral overlay comme l'étalon (voile, ✕, .est-ouvert), renvoi
   marqué actif, focus géré.
7. **Renvois en liens 16px soulignés** (cibles 25×22px < 44px tactile),
   pas d'état actif. → Boutons exposants monospace de l'étalon.
8. **Cliquer l'affirmation** (pas seulement le renvoi) → toutes ses
   sources + encart multi-sources (30 % d'attribution correcte).
9. **Compteurs d'onglets** Wikis (n) / Synthèses (n) ; lignes de liste
   qualifiées (N sources · N écartées · N faibles…).
10. **« Citations 8 » vs numérotation [1..6]** : compter les extractions
    DISTINCTES (« 6 sources citées, 8 renvois »).
11. **Latences muettes** : 2 s sans feedback au clic d'un renvoi.
    → indicateur de chargement (hx-indicator).
12. **Modèle rédacteur absent de l'en-tête** (provenance § 7.2 au
    niveau article) ; « Couverture » du wiki qui s'ouvre pour ne rien
    dire (masquer le bloc pour un wiki).

## P2 — polissage (bascule CSS)

13. Pastille « vivante » du wiki, liseré coloré par type d'opération
    dans le diff, cartes de preuve complètes dans les écartées
    (cliquables vers la source), option « notes retenues par les
    filtres actuels » à la création, taux de commentaires dans le
    récap garde-fou, motif complet du garde-fou (« sinon la
    délibération disparaît sous ses résumés »), sommaire/ancres pour
    les articles longs (4 196 px sur mobile), roving tabindex sur la
    tablist, surfaces de création en modale (ou assumer l'inline).

## Non vérifié par l'agent (réservé aux connectés) — à recetter à la main
Création wiki/synthèse (feedback pendant la génération), diff
d'opérations réel, « Vérifier les citations », bouton MAJ désactivé,
états vides des listes. Voir la fiche A TESTER phases H-I.

## Ce qui marche et est prouvé
Écartées et couverture exactes et honnêtes (46/50 extractions, mises en
garde affichées), panneau de preuve avec débat nominatif joint + lien
profond vers le passage exact (/lire/1/?extraction=490), numérotation
[N] stable par extraction, aucun débordement mobile, aucune erreur
console, clavier correct sur l'essentiel, contrat de génération tenu en
réel (8 et 9 citations, 0 hallucination, garde zéro-citation née d'un
constat réel).
