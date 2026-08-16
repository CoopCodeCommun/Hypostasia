notes design : 

Avis UX designer — Critique honnête du système de design

  Je vais être direct. Yves a posé des fondations solides sur certains points, mais il y a des problèmes réels que le mockup statique ne révèle
  pas.

  ---
  Ce qui est excellent dans la proposition Yves

  1. La distinction humain/machine/lecteur par la typographie est une trouvaille

  C'est rare de voir un design system qui encode la provenance sémantique dans la police elle-même. C'est exactement ce qu'il faut pour un outil de
   débat sourcé. Un utilisateur qui a passé 5 minutes dans l'interface saura instinctivement :
  - Mono = la machine a dit ça
  - Italique serif = un humain a écrit ça à l'origine
  - Cursive bleue = quelqu'un réagit en ce moment

  C'est du design fonctionnel, pas du décoratif. Approuvé sans réserve.

  2. L'hypostase en header de carte crée un scan vertical efficace

  Le mockup DEBAT extraction 03 montre une colonne de cartes où l'oeil accroche immédiatement : PHÉNOMÈNE PROBLÈME, LOI, CONJECTURE, ÉVÉNEMENT. On
  scanne les hypostases comme on scanne des titres de journal. C'est le bon pattern pour 10-30 extractions.

  3. Les icônes Unicode pour les statuts

  ⚫ ▶ ▷ ! — c'est minimaliste, lisible même à 12px, et ça ne dépend d'aucune librairie d'icônes. Bon choix technique.

  ---
  Ce qui me pose problème

  1. B612 est une police d'aviation, pas une police de lecture

  B612 a été conçue pour les cockpits d'Airbus — optimisée pour la lisibilité en conditions de stress, en petite taille, sur écrans basse
  résolution. Elle est fonctionnelle mais froide. Pour des labels et statuts à 12px, c'est parfait. Mais pour les citations humaines en italique à
  18pt, elle manque de caractère. La citation [...] Elinor Ostrom a surtout travaillé sur la notion de dilemme social [...] en B612 italique va
  ressembler à un rapport d'ingénieur, pas à une parole humaine qu'on veut préserver.

  Ma recommandation : garder B612 pour les labels/statuts et B612 Mono pour le texte machine (c'est son territoire naturel). Mais pour les
  citations humaines ([...]), utiliser Lora italique (déjà chargée dans le projet) ou une serif plus expressive. La chaleur de la citation humaine
  doit contraster avec la froideur de la synthèse machine — c'est le coeur du produit.

  2. DISCUTÉ et DISCUTABLE utilisent la même couleur

  Les deux sont en rouge #B61601. La seule différence est l'icône (▷ vs ▶) et le poids (courant vs gras). À 12px dans un panneau de 32rem, sur un
  écran de laptop à 1m de distance, cette distinction est invisible. C'est un problème de design d'information : deux statuts sémantiquement
  différents ne peuvent pas partager la même couleur.

  Ma recommandation :
  - DISCUTABLE (on peut en débattre) → rouge #B61601 ▶
  - DISCUTÉ (le débat a eu lieu) → orange foncé #D97706 ▷
  - Ou bien : fusionner les deux en un seul statut "EN DÉBAT" si la nuance n'est pas critique pour les utilisateurs

  3. Srisakdi à 20pt va exploser dans les fils de commentaires

  Dans le mockup, il y a une seule ligne de lecteur : "Ça fait longtemps que je ne suis pas intervenu." Ça rend bien. Mais dans un vrai fil de
  discussion avec 5-10 commentaires de 3-4 lignes chacun, du texte en cursive 20pt bleu va écraser visuellement tout le reste. Le panneau droit
  fait 32rem — chaque ligne contiendra ~30 caractères en Srisakdi 20pt. C'est illisible.

  Ma recommandation : Srisakdi à 16pt pour le corps des commentaires, 20pt uniquement pour le premier mot ou la signature. Ou bien : Srisakdi pour
  le nom de l'auteur + première ligne, puis basculer en B612 regular pour le corps du commentaire.

  4. Le jaune #FFDC00 (CONTROVERSÉ) échoue au contraste WCAG

  #FFDC00 sur fond blanc donne un ratio de contraste de 1.3:1. Le minimum WCAG AA est 4.5:1. C'est illisible. Le mockup montre #FF4000 (orange) qui
   est à 3.7:1 — mieux mais toujours insuffisant sur fond blanc.

  Ma recommandation : utiliser #FF4000 comme couleur de fond léger (#FFF4ED) avec #C2410C comme couleur de texte. Le jaune #FFDC00 peut servir
  d'accent (bordure, icône) mais jamais de couleur de texte.

  5. Les mockups ne montrent aucun état interactif

  C'est le défaut classique des mockups statiques. Il manque :
  - Hover sur une carte → qu'est-ce qui se passe ? Le texte surligne dans la colonne de lecture ?
  - Carte sélectionnée/active → comment distinguer la carte qu'on est en train de lire ?
  - État vide → "Aucune extraction" — quel message, quel visuel ?
  - État loading → l'IA analyse en ce moment — comment montrer la progression ?
  - Débordement → 30 extractions dans un panneau de 32rem — scroll, pagination, regroupement par hypostase ?

  L'interaction bidirectionnelle (clic texte ↔ clic carte) est le geste fondamental de l'app et il n'est pas designé du tout.

  6. Le mockup transcription est un mur de texte

  Le PDF DEBAT transcription montre une transcription de 6 pages d'un débat réel. C'est 100% italique avec des noms en gras et des timestamps
  discrets. Le problème : au-delà de 2 pages, l'oeil ne sait plus où se poser. Il n'y a pas de rythme visuel.

  Ma recommandation :
  - Alterner les fonds de blocs par locuteur (déjà partiellement fait dans le code actuel avec les couleurs)
  - Ajouter un séparateur visuel plus fort entre les interventions (bordure gauche colorée par locuteur, pas juste un changement de nom)
  - Les surlignages vert/jaune du mockup (extractions dans le texte) sont bons — mais ils doivent être la seule couleur dans le corps du texte,
  sinon trop de bruit

  ---
  Ce qui manque au design system

  1. Pas de dark mode

  L'outil est fait pour de la lecture longue. Beaucoup d'utilisateurs académiques/juridiques travaillent tard. Un dark mode n'est pas un luxe,
  c'est une nécessité ergonomique. Le fait d'avoir des couleurs hex fixes (#429900, #B61601) sans variables CSS rend le dark mode plus difficile
  après coup.

  Recommandation : dès l'Étape 1.8, définir toutes les couleurs en var(--couleur) dans :root et :root[data-theme="dark"]. Même si le dark mode
  n'est pas implémenté en Phase 1, les variables sont prêtes.

  2. Pas de réflexion sur les 13-14" laptops

  Le layout 3 colonnes (16rem + flex + 32rem) totalise ~48rem de sidebars. Sur un écran 13" à 1440px, la zone de lecture fait ~480px. C'est étroit.
   Avec la zone de lecture en Lora 18px + les marges, on tombe à ~60 caractères par ligne — acceptable mais limite.

  Le vrai problème c'est le mode débat à 70vw : sur 1440px ça laisse ~430px pour la lecture. C'est trop peu.

  Recommandation : en mode débat, la zone de lecture devrait se réduire ou se replier (afficher uniquement le passage pertinent) plutôt que de
  coexister compressée.

  3. Pas de hiérarchie entre les cartes

  Le mockup montre des cartes de même taille, même poids visuel. En réalité, une extraction CONSENSUELLE avec 12 commentaires et 3 sources est plus
   importante qu'une extraction DISCUTABLE sans commentaire. Le design devrait refléter cette densité informationnelle.

  Recommandation : cartes compactes par défaut (hypostase + titre en 1 ligne), expansion au clic. Les cartes avec commentaires/sources ont un
  indicateur de densité (barre latérale plus épaisse, badge numérique).

> REMARQUE JONAS : trier humainement ?
> # Pertinence / Inutile
> - Rajouter des boutons pertinent / inutile pour trier les extractions. Ne rendre visible que ceux qui ont un ratio > 1 
  
  ---
  Synthèse : verdict designer

  ┌────────────────────────────────────┬──────┬────────────────────────────────────────────────────────────────┐
  │               Aspect               │ Note │                          Commentaire                           │
  ├────────────────────────────────────┼──────┼────────────────────────────────────────────────────────────────┤
  │ Distinction humain/machine/lecteur │ 9/10 │ Fondamentalement juste, à calibrer en tailles                  │
  ├────────────────────────────────────┼──────┼────────────────────────────────────────────────────────────────┤
  │ Hypostase en header                │ 8/10 │ Bon pattern, les 8 familles de couleurs l'améliorent           │
  ├────────────────────────────────────┼──────┼────────────────────────────────────────────────────────────────┤
  │ Typographie B612/Mono              │ 6/10 │ Parfait pour labels/machine, froid pour citations humaines     │
  ├────────────────────────────────────┼──────┼────────────────────────────────────────────────────────────────┤
  │ Couleurs statuts                   │ 5/10 │ Rouge dédoublé, jaune inaccessible, pas de dark mode           │
  ├────────────────────────────────────┼──────┼────────────────────────────────────────────────────────────────┤
  │ Srisakdi lecteur                   │ 7/10 │ Identité forte, taille à réduire pour les fils longs           │
  ├────────────────────────────────────┼──────┼────────────────────────────────────────────────────────────────┤
  │ Cartes d'extraction                │ 6/10 │ Mockup statique, manque les états interactifs et la hiérarchie │
  ├────────────────────────────────────┼──────┼────────────────────────────────────────────────────────────────┤
  │ Transcription                      │ 5/10 │ Mur de texte, manque de rythme visuel                          │
  ├────────────────────────────────────┼──────┼────────────────────────────────────────────────────────────────┤
  │ Système global                     │ 7/10 │ Bonne direction, besoin de calibrage et d'états dynamiques     │
  └────────────────────────────────────┴──────┴────────────────────────────────────────────────────────────────┘

  Le principal risque : appliquer le mockup tel quel sans l'adapter aux contraintes réelles (taille d'écran, longueur des contenus, interactions,
  accessibilité). Le concept est bon. L'exécution doit être plus pragmatique que le mockup.

