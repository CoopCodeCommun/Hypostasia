  Incohérences et problèmes dans le document

  1. Numérotation cassée (Phase 10 / Tests)

  La section 11 "Phase 10 — Tests Playwright" contient des étapes numérotées 9.1 et 9.2 au lieu de 10.1 et 10.2. Copier-coller de la Phase 9.

  2. Conflit entre la TOC et le contenu

  La TOC dit Phase 5 — Edition collaborative mais le titre de la section 6 dit Phase 5 — Edition collaborative et fil de tracabilite. Incohérence mineure mais c'est le genre de chose qui perd un agent IA.

  3. Le SourceLink est dans Phase 1 mais dépend de Phase 5

  L'Étape 1.4 crée le modèle SourceLink et exige que "quand une restitution est créée, exiger ou générer les SourceLinks". Mais tout le mécanisme de navigation de ces liens (fil de réflexion, diff avec provenance,
   synthèse sourcée) est dans la Phase 5. Résultat : tu vas créer un modèle en Phase 1 qui ne sera ni visible ni utile avant la Phase 5. C'est une abstraction prématurée — exactement ce que ton propre CLAUDE.md
  interdit.

  Suggestion : soit déplacer SourceLink en Phase 5, soit réduire l'Étape 1.4 au strict minimum (juste le champ FK parent_page qui existe déjà + un champ justification sur la restitution).

  4. Le statut de débat (Étape 1.5) bloque la synthèse mais rien ne le prévoit côté UX

  Tu dis "le statut consensus est un prérequis pour générer une synthèse/restitution". Mais en Phase 1 il n'y a pas encore de users (Phase 2), donc qui marque le consensus ? Un seul utilisateur qui clique
  "consensus" sur son propre commentaire, ça n'a pas de sens. Ce prérequis a du sens seulement après la Phase 2.

  5. Phases 8 et 9 — ambitieuses mais sans priorisation interne

  Ces phases sont des projets entiers en soi (WebSocket, hostapd, portail captif, Docker ARM64, SQLCipher…). Elles manquent d'un MVP interne. Pour la Phase 8, le MVP serait : upload de chunks audio par POST
  classique + polling HTMX, sans WebSocket. Pour la Phase 9, le MVP serait : un docker-compose.yml qui marche sur un laptop sans WiFi AP.

  6. Deep Research (Phase 7) — fantôme

  2 étapes, aucun détail technique réel, un lien vers un article Korben. C'est un placeholder, pas un plan. Soit l'étoffer, soit le retirer et le mettre en "idées futures".

  7. Tests Playwright en Phase 10 mais "à démarrer en parallèle des Phases 1-3"

  Le graphe de priorité dit de commencer les tests tôt, mais le plan les met en dernier. Contradiction. Les tests devraient être intégrés à chaque phase, pas une phase séparée.

  8. Pas de section "données / backup / export"

  Aucune mention de comment on exporte ses données, comment on fait un backup de la base SQLite, comment on migre vers PostgreSQL si besoin. Pour un outil de gestion de connaissance, c'est un oubli important.

  ---
  Avis commercial / métier IA (CEO)

  Ce qui est fort

  Le positionnement est excellent. "Cycle itératif de réflexion sourcée" — c'est un vrai problème de marché que personne ne résout bien. Les outils existants sont soit :
  - Des éditeurs collaboratifs (Google Docs, Notion) qui n'ont aucune traçabilité des décisions
  - Des outils de knowledge management (Confluence, Obsidian) qui ne gèrent pas le débat
  - Des outils IA (ChatGPT, NotebookLM) qui produisent du texte sans sourçage

  Hypostasia se positionne dans un créneau vide : la délibération structurée avec traçabilité complète. C'est pertinent pour :
  - Cabinets juridiques (rédaction de contrats, négociation de clauses)
  - Collectivités territoriales (chartes, PLU, concertations citoyennes)
  - ESS / coopératives (gouvernance partagée, rédaction de statuts)
  - Recherche académique (revue par les pairs, annotation de corpus)

  Ce qui est risqué commercialement

  1. Trop de features, pas assez de focus. Tu as 10 phases qui couvrent : extension navigateur, import multi-format, transcription audio, LLM multi-provider, auth, collab, recherche sémantique, deep research,
  enregistrement live, boîtier WiFi offline, tests E2E. C'est le plan d'un produit à 50 personnes sur 3 ans, pas d'un solo/petit projet. Un investisseur ou un client pose la question : "c'est quoi le produit au
  jour 1 ?" Et la réponse est floue.
  2. Le mode local / boîtier WiFi (Phase 9) est séduisant mais c'est un produit à part entière. C'est du hardware + réseau + ops + sécurité physique. Si tu veux vraiment le faire, c'est un spin-off, pas une phase
  du même projet.
  3. Le live audio (Phase 8) est une feature de type "Otter.ai" qui est un marché saturé. Google Meet, Teams, Otter, Fireflies, Granola — tous font la transcription live. Le différenciateur d'Hypostasia n'est pas
  la transcription, c'est ce qu'on en fait après (extraction, débat, synthèse). Risque de diluer l'identité du produit.
  4. Pas de pricing / modèle économique. Pour un projet qui appelle des API LLM à chaque extraction, reformulation et restitution, la question du coût est structurante. Qui paie ? Le serveur ? L'utilisateur avec
  sa propre clé API ? Un abonnement ? Ça influence l'architecture (multi-tenant, quotas, etc.).

  Ma recommandation business

  Couper les 10 phases en 2 produits :

  Produit 1 — "Hypostasia Core" (Phases 1-5) : Outil de délibération sourcée. Import de texte → Extraction → Débat → Synthèse traçable. C'est là que la valeur unique est. C'est ça qu'il faut livrer en premier.

  Produit 2 — "Hypostasia Live" (Phases 8-9) : Boîtier de réunion confidentielle avec transcription + prise de notes. Si la demande est validée par des clients pilotes, c'est un produit hardware/SaaS séparé.

  Les Phases 6-7 (recherche sémantique, deep research) sont des améliorations de Produit 1, pas des phases distinctes.

  ---
  Avis CTO — Stack technique

  Ce qui est bien choisi

  - Django 6 + HTMX : stack mature, pas de frontend JS à maintenir, rendu serveur, parfait pour un produit de contenu. Le choix de HTMX plutôt que React/Vue est le bon — le produit est fondamentalement du texte et
   des formulaires, pas une app temps réel.
  - DRF ViewSets explicites : la convention "pas de ModelViewSet" est radicale mais saine. Le code est lisible par n'importe qui.
  - Celery pour les tâches longues : correct. Les LLM ont des latences de 5-60s, ça ne tient pas en synchrone.
  - SQLite en dev : parfait pour le POC. Léger, pas de dépendance externe.
  - Python 3.14 : très en avance (pas encore stable à la date du plan), mais c'est gérable.

  Ce qui pose problème

  1. SQLite + Celery avec broker SQLite = fragile. Le broker SQLAlchemy SQLite pour Celery est explicitement marqué "experimental / not recommended for production" dans la doc Celery. En prod, même petite, il faut
   Redis ou au minimum un fichier séparé avec du soin. Pour le mode local (Phase 9), c'est acceptable. Pour une vraie prod multi-user, non.
  2. Pas de PostgreSQL dans le plan. Tu parles d'embeddings vectoriels (Phase 6) et tu mentionnes pgvector en passant, mais la migration SQLite → PostgreSQL n'est nulle part comme étape explicite. Si tu fais de la
   recherche sémantique, du multi-user, et des écritures concurrentes (Phase 5 collab), SQLite ne tiendra pas. Ajouter une étape "migration PostgreSQL" en Phase 1 ou Phase 2.
  3. WebSocket (Phase 8) avec Django = django-channels = ASGI = changement d'architecture. Passer de WSGI (gunicorn) à ASGI (daphne/uvicorn) n'est pas trivial. Ça change le déploiement, la gestion des workers, et
  potentiellement le comportement de certains middlewares. Ta recommandation SSE est la bonne — rester en SSE tant que possible.
  4. LangExtract comme dépendance structurante. Le plan mentionne que LangExtract ne supporte que Gemini et OpenAI. Si cette lib est abandonnée ou n'évolue pas, tu es bloqué. La couche d'abstraction LLM (Phase 3)
  devrait prévoir de pouvoir remplacer LangExtract par des appels directs avec structured output (JSON mode d'OpenAI, tool_use d'Anthropic, etc.).
  5. Tailwind via CDN. En prod et surtout en mode offline (Phase 9), c'est un problème. Ça devrait être dans Phase 1 (socle technique) : builder Tailwind localement ou au minimum télécharger le fichier compilé.
  C'est un prérequis, pas un nice-to-have.
  6. Pas de monitoring / observabilité. Aucune mention de logging structuré, Sentry, métriques, health check. Pour un outil qui appelle des API LLM en asynchrone, quand un job échoue silencieusement, comment tu le
   sais ?
  7. Le multi-tenancy n'est pas adressé. Le skill Stack CCC mentionne django-tenants, mais le plan n'en parle pas. Si plusieurs organisations utilisent la même instance, il faut y penser avant la Phase 2 (users),
  pas après.

  Résumé technique en une phrase

  La stack de base (Django + HTMX + Celery + DRF) est solide et bien choisie. Les risques sont : SQLite en prod, pas de plan de migration PostgreSQL, dépendance sur LangExtract, et les Phases
8-9 qui nécessitent
  un changement d'architecture (ASGI, hardware) qui n'est pas suffisamment isolé du cœur.

  ---
  Actions concrètes que je recommande sur le document

  1. Fixer la numérotation Phase 10 (étapes 9.x → 10.x) et la TOC
  2. Déplacer SourceLink de Phase 1 vers Phase 5 (ou le réduire à un simple champ texte en Phase 1)
  3. Ajouter une Étape 1.6 : servir Tailwind + HTMX en local (prérequis Phase 9 mais utile dès maintenant)
  4. Ajouter une étape PostgreSQL dans Phase 2 (pré-requis multi-user)
  5. Réduire Phase 7 à une note "idée future" ou l'intégrer comme sous-étape de Phase 6
  6. Ajouter une section "export / backup / portabilité des données" (RGPD, autonomie utilisateur)
  7. Intégrer les tests à chaque phase plutôt qu'une Phase 10 séparée
  8. Ajouter une note sur le modèle économique (même préliminaire) pour guider les décisions d'architecture

  Tu veux que j'applique ces corrections au document ?