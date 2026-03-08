❯ Analyse tout le plan ! donne moi des remarques et idée !

∴ Thinking…

  The user wants me to give a full UX/design review of the ENTIRE plan — not just the Yves design bits, but the whole product from a UX designer
  perspective. All phases, all features, the whole user experience. Let me think deeply about this.

  Let me re-read the plan structure:
  - Phase 1: Socle technique (cleanup, CRUD, extension, statut débat, assets, PostgreSQL, Playwright, charte visuelle)
  - Phase 2: Users & sharing
  - Phase 3: Unified AI providers
  - Phase 4: Prompts & costs
  - Phase 5: Collaborative editing & traceability (SourceLink)

  - Phase 6: Semantic search
  - Phase 7: Deep Research (LDR)
  - Phase 8: Live audio transcription
  - Phase 9: Offline/local mode

  I need to think about this from a pure UX perspective — the user journeys, the information architecture, the interaction patterns, the emotional
  design, the onboarding, the cognitive load, etc. Not just visual design. The key personas I'm seeing are the analyst who imports text, runs
  extraction, reviews hypostases, comments, and synthesizes findings, and the facilitator who records meetings, reviews transcriptions, extracts
  key points, and shares results.

  Now I'm considering the other personas in this workflow — the reviewer who receives shared documents and validates extractions, and the
  researcher who searches across documents to build knowledge. But looking at the broader UX landscape, I'm noticing some critical gaps. There's no
   onboarding flow anywhere in the plan, so a new user lands on an empty three-column layout with no guidance on what to do next. The concept of
  hypostases itself has a steep learning curve that needs to be addressed. The three-column layout is assumed without questioning whether it's the
  right information architecture, and the sidebar file manager pattern might not be the best metaphor — there's no dashboard or home view to orient
   users. The core workflow cycle of lecture, extraction, commentaire, débat, synthèse, and nouvelle version is described, but I need to think
  through how users actually navigate this flow.

  The extraction experience feels fragmented — manual extraction requires selecting text and filling a form, but there's no keyboard shortcut
  support, and the AI extraction gives no preview of what will actually be extracted before results appear. The cards pile up in the right panel
  with no way to filter, sort, or group them. The debate experience is particularly problematic because while comments attach to individual
  extractions, the actual debate spans across multiple extractions, yet there's no unified debate view showing all opinions together. The status
  workflow from open to in-progress to consensus to rejected is entirely manual with no guided progression. And the synthesis experience — which
  should be the product's climax where knowledge crystallizes into new text — is hidden away as a button on an extraction card with no guided
  experience around it.

  Beyond the core flow, there are gaps in search and discovery that Phase 6 doesn't address: semantic search results need a completely different
  layout than the three-column design. The transcription experience works for short recordings but breaks down with longer audio like the six-page
  example, where there's no timeline, no way to jump to specific moments, and no audio playback synced to the text. Mobile interactions aren't
  really considered — text selection works completely differently on touch devices, and the three-column layout forces constant panel switching.
  Accessibility is mentioned in the skill stack but hasn't been thought through in the actual experience design.

  I'm also imagining some alternative approaches: a horizontal timeline that maps the entire debate cycle from source through extractions,
  comments, synthesis, and new versions as clickable nodes. Or a heat map overlaid on the source text showing which passages generated the most
  discussion, with color intensity reflecting consensus versus controversy. Even a bird's-eye consensus dashboard that gives an overview of the
  whole synthesis process.

  Then there's the possibility of a guided wizard for synthesis instead of a single button—walking through extraction selection, comment review,
  synthesis writing, source verification, and publication as discrete steps. For audio content, I could add a speaker timeline with a waveform and
  colored segments per speaker, like a podcast editor. A reading mode that strips away all the UI clutter for focused text viewing with subtle
  extraction markers that expand inline when clicked. A comparison view showing side-by-side versions with diff highlighting and annotations
  explaining why each change was made. And for collaborative work, an activity feed that surfaces real-time updates when others comment or make
  changes.

  I'm also thinking about a minimap-style extraction indicator running vertically alongside the text, color-coded by status so you can see at a
  glance where everything is. And for power users doing intensive analysis, keyboard shortcuts for navigating extractions, approving or rejecting
  them, adding comments—basically making the whole workflow keyboard-driven.

● Bon. Je mets ma casquette de designer UX produit, pas juste "visual design". Je vais passer en revue tout le plan du point de vue de l'expérience
   utilisateur — les flux, l'architecture d'information, les interactions manquantes, les idées.

  ---
  Critique UX globale du produit Hypostasia

  1. L'onboarding n'existe nulle part dans le plan

  Problème : le cycle Lecture → Extraction → Commentaire → Débat → Synthèse → Nouvelle version est le coeur du produit. Mais aucune phase ne
  prévoit comment un nouvel utilisateur découvre ce cycle. Il arrive sur une interface 3 colonnes vide. Que fait-il ?

  Le concept d'hypostase est puissant mais inhabituel. PHÉNOMÈNE, CONJECTURE, INVARIANT — ce vocabulaire n'est pas intuitif. Sans guidage,
  l'utilisateur va traiter les extractions comme des surligneurs et passer à côté du modèle épistémique.

  Propositions :
  - Page d'accueil "premier pas" : quand la bibliothèque est vide, afficher un parcours guidé en 4 étapes (importer un texte → lancer une
  extraction → lire les hypostases → commenter). Pas un tutoriel modal, juste un état vide intelligent avec des appels à l'action
  - Tooltip contextuel sur les hypostases : au survol d'une pastille CONJECTURE ou INVARIANT, un mini-tooltip explique en 1 phrase ce que ça
  signifie. Ex: "Conjecture — Affirmation plausible non démontrée"
  - Document exemple pré-chargé : livrer l'app avec un texte déjà extrait et commenté (le débat IA de Yves est parfait pour ça). L'utilisateur voit
   le résultat final avant de créer le sien
  - Ça peut être une Étape 1.9 ou intégré à l'Étape 1.2 (CRUD manquants — l'état vide est un CRUD d'UX)

  ---
  2. Le cycle délibératif n'a pas de vue dédiée

  Problème : le plan décrit un cycle itératif mais l'interface le fragmente en interactions dispersées :
  - Les extractions sont dans le panneau droit
  - Les commentaires sont dans un fil par extraction
  - La synthèse est un bouton sur une carte
  - La nouvelle version est dans un switcher de pilules en haut de la lecture

  L'utilisateur n'a jamais une vue d'ensemble de où en est le débat. Il ne sait pas : combien d'extractions sont résolues ? Lesquelles bloquent ?
  Est-ce que le texte est prêt pour une synthèse ?

  Propositions :

  a) Tableau de bord de débat ("Consensus dashboard")

  Un partial HTMX accessible depuis le panneau d'analyse, qui montre :

  ┌─────────────────────────────────────────┐
  │  Débat sur "L'IA dans l'éducation"      │
  │                                          │
  │  ⚫ 8 consensuels  ▶ 3 discutables      │
  │  ▷ 2 discutés      ! 1 controversé      │
  │                                          │
  │  ████████████░░░░  57% consensus         │
  │                                          │
  │  Bloquants :                             │
  │  ! "L'avènement de l'IA..."   3 comments │
  │  ▶ "L'intégration d'outils..." 0 comment │
  │                                          │
  │  [Lancer la synthèse]  (grisé si < 80%) │
  └─────────────────────────────────────────┘

  Le bouton "Lancer la synthèse" ne devrait s'activer que quand un seuil de consensus est atteint (configurable). C'est le garde-fou UX contre la
  synthèse prématurée.

  b) Mini-carte des extractions ("extraction minimap")

  Une bande verticale fine à côté du texte de lecture (comme le minimap d'un éditeur de code), colorée par statut de débat. L'utilisateur voit d'un
   coup d'oeil quelles zones du texte sont consensuelles (vert) et lesquelles sont encore en débat (rouge/orange). Clic sur une zone → scroll vers
  l'extraction.

  ┌──┬────────────────────────────┐
  │▓▓│ Paragraphe 1 (consensuel)  │
  │▓▓│                            │
  │░░│ Paragraphe 2 (pas extrait) │
  │██│ Paragraphe 3 (controversé) │
  │▓▓│ Paragraphe 4 (consensuel)  │
  │▒▒│ Paragraphe 5 (discuté)     │
  └──┴────────────────────────────┘

  ---
  3. La synthèse/restitution est le climax du produit — et elle est sous-designée

  Problème : la Phase 5 décrit SourceLink, diff, fil de réflexion. C'est bien techniquement. Mais l'UX de la création d'une synthèse n'est pas
  pensée. Actuellement : un bouton "Restituer" → un textarea → l'IA génère → c'est stocké. C'est trop brutal pour l'acte le plus important du
  produit.

  Proposition : Wizard de synthèse guidée

  Étape 1 : Sélection — Quelles extractions inclure ? Vue checkbox avec les cartes, pré-cochées sur les consensuelles.

  Étape 2 : Revue — Pour chaque extraction incluse, afficher les commentaires clés. L'utilisateur valide ou ajuste.

  Étape 3 : Rédaction — Textarea avec les citations sources en sidebar. L'IA peut pré-remplir mais l'humain a le dernier mot. Chaque paragraphe
  doit être lié à sa source (drag & drop ou référence inline).

  Étape 4 : Vérification — Le système affiche les passages non sourcés en surbrillance. L'utilisateur complète ou valide.

  Étape 5 : Publication — Créer la nouvelle version avec label, résumé des changements.

  Ce wizard serait un partial HTMX multi-étapes dans le panneau droit (mode débat 70vw). C'est l'UX qui incarne la traçabilité — pas juste la
  stocker en base.

  ---
  4. La transcription longue a besoin d'un timeline audio

  Problème : le mockup de Yves montre une transcription de 6 pages. C'est un mur de texte. Pour un débat d'1h avec 8 locuteurs, on parle de 30+
  pages. Aucun outil de navigation temporelle n'est prévu.

  Propositions :

  a) Barre de timeline horizontale

  ┌──────────────────────────────────────────────────┐
  │ ▮▮▮▯▯▯▯▮▮▮▮▮▯▯▮▮▮▯▯▯▮▮▮▮▯▯▮▮▮▮▮▮▯▯▯▮▮▮▮▮▮▮▮▮ │
  │ Jean  Yves  Michel    Véro  Michel    Jonas  ... │
  │ 0:00            30:00            60:00    77:00  │
  └──────────────────────────────────────────────────┘

  Chaque segment est coloré par locuteur. Clic → scroll vers le bloc. Survol → preview du texte. C'est un pattern de podcast editor simplifié.

  b) Filtrage par locuteur

  Bouton "Afficher uniquement Michel R" → masque les autres blocs. Utile pour suivre le fil de pensée d'un seul participant.

  c) Marqueurs d'extraction sur la timeline

  Les extractions créées depuis la transcription apparaissent comme des points sur la timeline, colorés par statut. On voit quels moments du débat
  ont généré le plus d'extractions.

  Ça s'intègre dans la Phase 8 mais le pattern de timeline est utile dès la Phase 1 pour les transcriptions audio existantes.

  ---
  5. Le mode lecture a besoin d'un "focus mode"

  Problème : le layout 3 colonnes est efficace pour le travail analytique mais fatigant pour la lecture longue. Sur un 13" laptop, la zone de
  lecture fait ~500px avec les deux sidebars. C'est étroit pour un texte de 20 pages.

  Proposition : un bouton "Mode lecture" qui :
  - Replie les deux sidebars
  - Centre le texte en max-w-2xl avec marges généreuses
  - Conserve les marqueurs d'extraction en marge (discrets, juste les pastilles)
  - Clic sur une pastille → popup inline avec la carte d'extraction (pas ouverture du panneau complet)
  - Touche Escape ou clic hors popup → referme
  - Raccourci clavier L pour toggle

  C'est essentiel pour la Phase 5 (lecture de versions) et la Phase 8 (relecture post-transcription).

  ---
  6. La recherche (Phase 6) a besoin d'une vue dédiée, pas juste un champ dans le header

  Problème : l'Étape 6.2 dit "champ de recherche dans le header + résultats en partial HTMX". C'est trop réducteur pour une recherche sémantique
  cross-documents.

  Proposition : une vue recherche pleine page (ou mode spécial du layout) :

  ┌─────────────────────────────────────────────────┐
  │  🔍 "dilemme social Ostrom"                     │
  │  ┌───────────────┐  ┌────────────────────────┐  │
  │  │ Filtres        │  │ Résultats              │  │
  │  │               │  │                        │  │
  │  │ Type:          │  │ 📄 Débat IA éducation  │  │
  │  │ ☑ Pages       │  │ "...notion de dilemme  │  │
  │  │ ☑ Extractions │  │  social..." (score 94%) │  │
  │  │ ☐ Commentaires│  │ PRINCIPE ⚫ CONSENSUEL  │  │
  │  │               │  │                        │  │
  │  │ Hypostase:     │  │ 📄 Charte numérique    │  │
  │  │ ☑ Toutes      │  │ "...Ostrom définit..." │  │
  │  │               │  │ DÉFINITION ▷ DISCUTÉ   │  │
  │  │ Statut:        │  │                        │  │
  │  │ ☑ Tous        │  │ 💬 Commentaire de Jean  │  │
  │  │               │  │ "Voir aussi les travaux │  │
  │  │ Dossier:       │  │  d'Ostrom sur..."      │  │
  │  │ ☑ Tous        │  │                        │  │
  │  └───────────────┘  └────────────────────────┘  │
  └─────────────────────────────────────────────────┘

  Chaque résultat affiche : le document source, l'extrait avec le match surligné, l'hypostase, le statut. Clic → navigation vers la page avec le
  passage mis en évidence.

  La recherche sémantique est d'autant plus puissante qu'elle filtre par hypostase : "montre-moi toutes les LOI dans mes documents" ou "toutes les
  CONJECTURES qui sont encore DISCUTÉES".

  ---
  7. Le Deep Research (Phase 7) devrait enrichir les cartes, pas créer une vue séparée

  Problème : l'Étape 7.2 prévoit un "panneau de sources" séparé. Ça crée une 4e couche d'information. L'utilisateur doit déjà jongler entre texte,
  extraction, commentaires.

  Proposition : les sources externes s'intègrent dans la carte d'extraction elle-même :

  ┌─────────────────────────────────────┐
  │ LOI                          ⚫ CS  │
  │                                     │
  │ La loi d'Amara décrit une           │  ← .typo-machine
  │ corrélation selon laquelle...       │
  │                                     │
  │ [...] Il y a une règle dans le      │  ← .typo-citation
  │ numérique qui a l'air de se         │
  │ vérifier [...] [...]                │
  │                                     │
  │ 📚 3 sources                        │  ← section dépliable
  │  ├ Wikipedia: Roy Amara (95%)       │
  │  ├ arxiv: Hype Cycles... (82%)      │
  │  └ PubMed: Technology... (71%)      │
  │                                     │
  │ #Loi d'Amara #technologies          │
  └─────────────────────────────────────┘

  La section "sources" est repliée par défaut, dépliable au clic. Ça garde les sources contextualisées avec l'extraction qu'elles sourcent.

  ---
  8. Les raccourcis clavier sont absents du plan

  Problème : Hypostasia est un outil de travail intellectuel. Les utilisateurs vont passer des heures dedans. Tout passer par des clics dans des
  menus est lent.

  Proposition : un système de raccourcis clavier (Phase 1 ou 2) :

  ┌───────────┬─────────────────────────────────────┐
  │ Raccourci │               Action                │
  ├───────────┼─────────────────────────────────────┤
  │ L         │ Toggle mode lecture (focus)         │
  ├───────────┼─────────────────────────────────────┤
  │ E         │ Toggle panneau extractions          │
  ├───────────┼─────────────────────────────────────┤
  │ T         │ Toggle arbre de dossiers            │
  ├───────────┼─────────────────────────────────────┤
  │ J / K     │ Extraction suivante / précédente    │
  ├───────────┼─────────────────────────────────────┤
  │ C         │ Commenter l'extraction sélectionnée │
  ├───────────┼─────────────────────────────────────┤
  │ S         │ Marquer comme consensuel            │
  ├───────────┼─────────────────────────────────────┤
  │ R         │ Rejeter l'extraction                │
  ├───────────┼─────────────────────────────────────┤
  │ Ctrl+F    │ Recherche dans le texte             │
  ├───────────┼─────────────────────────────────────┤
  │ /         │ Recherche sémantique (Phase 6)      │
  ├───────────┼─────────────────────────────────────┤
  │ ?         │ Afficher les raccourcis             │
  └───────────┴─────────────────────────────────────┘

  Pattern : palette de commandes (type Ctrl+K dans VS Code ou Notion). Pas prioritaire pour le MVP mais à prévoir dans l'architecture JS.

  ---
  9. Le mobile n'est pas un layout dégradé — c'est un usage différent

  Problème : le code actuel traite le mobile comme "les mêmes 3 colonnes en overlay". Mais l'usage mobile est fondamentalement différent : on lit,
  on commente, on ne fait pas d'extraction IA.

  Proposition : 2 modes mobiles distincts :

  a) Mode lecteur mobile (défaut) : juste le texte avec les marqueurs d'extraction. Tap sur un marqueur → bottom sheet avec la carte d'extraction +
   bouton commenter.

  b) Mode facilitateur mobile (Phase 8) : enregistrement audio + visualisation live des segments. Interface minimale : gros bouton rec, segments
  qui défilent.

  Pas de panneau d'analyse sur mobile. Pas de wizard de synthèse sur mobile. Ces flux sont desktop/tablet.

  ---
  10. Idées supplémentaires

  a) Heat map du débat sur le texte

  Au lieu de juste des pastilles en marge, colorer le fond du texte en dégradé léger selon l'intensité du débat. Plus il y a de
  commentaires/désaccords sur un passage, plus le fond est chaud (rouge). Les passages consensuels sont en vert pâle. Les passages non extraits
  sont neutres.

  Ça donne une "température du texte" lisible en 2 secondes. C'est activable/désactivable par toggle.

  b) Vue "qui a dit quoi" (Phase 2+)

  Quand il y a plusieurs utilisateurs, un filtre par auteur dans le panneau d'extractions : "Montrer uniquement les commentaires de Michel". Utile
  pour préparer une réunion de consensus.

  c) Export visuel du débat

  En plus de l'export Markdown (Phase 5), un export PDF/HTML qui préserve la mise en forme Yves : hypostases colorées, distinction machine/humain,
  statuts. C'est le livrable qu'on présente aux financeurs, aux clients, au CA. L'export doit être aussi beau que l'interface.

  d) Notification de progression du débat

  Quand un seuil de consensus est atteint (ex: 80% des extractions en CONSENSUEL), une notification dans l'interface : "Le débat sur 'Charte IA' a
  atteint 80% de consensus. Prêt pour une synthèse ?". C'est le nudge UX qui fait avancer le cycle.

  e) Mode comparaison côte-à-côte (Phase 5)

  ┌──────────────────────┬──────────────────────┐
  │  Version 1           │  Version 2           │
  │                      │                      │
  │  L'IA est un outil   │  L'IA est un outil   │
  │  - prometteur pour - │  + essentiel pour +  │
  │  l'éducation.        │  l'éducation, sous   │
  │                      │  + réserve de    +   │
  │                      │  + régulation.   +   │
  │                      │                      │
  │  📎 Source: extract.  │                      │
  │  #42 + 3 comments    │                      │
  └──────────────────────┴──────────────────────┘

  Le diff est annoté avec les SourceLinks. Chaque zone modifiée montre pourquoi elle a changé (lien vers l'extraction et les commentaires). C'est
  la traçabilité rendue visuelle.

  ---
  Résumé des ajouts recommandés au PLAN

  ┌───────────────────────────────────────┬──────────┬────────┬────────────────────┐
  │                 Idée                  │  Phase   │ Effort │     Impact UX      │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Onboarding / états vides intelligents │ 1        │ Faible │ Critique           │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Dashboard de consensus                │ 1.4 ou 2 │ Moyen  │ Fort               │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Extraction minimap (bande latérale)   │ 1.8      │ Moyen  │ Fort               │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Mode lecture focus                    │ 1        │ Faible │ Fort               │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Wizard de synthèse guidée             │ 5        │ Fort   │ Critique           │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Timeline audio pour transcriptions    │ 1 ou 8   │ Moyen  │ Fort               │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Filtrage par locuteur                 │ 1        │ Faible │ Moyen              │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Sources dans la carte (Phase 7)       │ 7        │ Faible │ Fort               │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Raccourcis clavier                    │ 2        │ Moyen  │ Fort (power users) │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Vue recherche pleine page             │ 6        │ Moyen  │ Fort               │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Heat map du débat                     │ 2+       │ Moyen  │ Différenciant      │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Export visuel du débat                │ 5        │ Moyen  │ Fort (financeurs)  │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Mode mobile lecteur/facilitateur      │ 2        │ Moyen  │ Moyen              │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Dark mode (variables CSS)             │ 1.8      │ Faible │ Moyen              │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Vue comparaison annotée               │ 5        │ Fort   │ Critique           │
  ├───────────────────────────────────────┼──────────┼────────┼────────────────────┤
  │ Notification de seuil de consensus    │ 2+       │ Faible │ Fort               │
  └───────────────────────────────────────┴──────────┴────────┴────────────────────┘

