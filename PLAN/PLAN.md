# PLAN — Hypostasia : du POC a la production

> Ce document est la reference vivante du projet. Il decrit l'etat actuel de chaque composant,
> les problemes identifies, et les phases d'amelioration prevues.

---

## Principe fondamental — Cycle iteratif de reflexion sourcee

Hypostasia n'est pas un simple outil de prise de notes ou d'extraction. C'est un **outil de gestion de debat et de connaissance** dont le coeur est un cycle iteratif :

```
Lecture → Extraction → Commentaire → Debat → Synthese → Nouvelle version
                                                              ↓
                                                     (on recommence)
```

Ce cycle peut etre repete autant de fois que necessaire jusqu'a atteindre un **consensus**.
Cas d'usage principaux : redaction de contrats, de chartes, de specifications, de comptes-rendus,
de documents strategiques — tout texte qui doit etre debattu, amende et valide collectivement.

### Regle non negociable : tracabilite totale des sources

**Chaque mot de chaque version doit pouvoir etre remonte a son origine.**

Une nouvelle version de texte est toujours le produit de :
- **Texte source** (la version precedente ou le document original)
- **Extractions** (passages identifies comme importants)
- **Commentaires** (debat humain sur ces extractions)
- **Synthese** (humaine ou assistee IA)

Le lien entre ces elements doit etre **explicite et navigable** :
- Depuis un paragraphe de la version N, je peux voir quel passage de la version N-1 en est l'origine
- Depuis ce passage, je peux voir les commentaires et le debat qui ont conduit a la modification
- Depuis la synthese, je peux voir les sources exactes qui l'ont alimentee
- Ce fil est navigable de bout en bout, de la version finale jusqu'au texte original

**Pourquoi c'est non negociable** : c'est le garde-fou contre l'AI slop et les hallucinations.
Si une IA participe a la synthese, chaque element de sa production doit pointer vers une source humaine verifiable.
Pas de texte "sorti de nulle part". Pas de reformulation sans ancrage. Pas de consensus fictif.

### Valeurs fondatrices — le texte comme commun, l'humain comme auteur

Trois convictions structurent chaque decision de design dans Hypostasia :

**1. Le texte est un commun.**
Un contrat, une charte, un compte-rendu de debat — ces textes n'appartiennent pas a un individu.
Ils sont le produit d'une deliberation collective. Hypostasia traite le texte comme une ressource
partagee que chacun peut lire, annoter, contester et amender. Le cycle iteratif (lecture → extraction
→ debat → synthese) est le mecanisme de gouvernance de ce commun.

**2. Le travail humain est la valeur.**
Chaque commentaire, chaque desaccord, chaque reformulation porte la pensee d'un humain. L'interface
doit rendre ce travail **visible et credite**. La charte typographique distingue visuellement qui parle :
Lora italique pour la voix humaine citee, Srisakdi pour l'intervention du lecteur, B612 Mono pour la
machine. Ce n'est pas decoratif — c'est un acte de reconnaissance : le travail intellectuel humain
ne se confond jamais avec la production automatique.

**3. Le LLM est un outil, pas un auteur.**
L'IA n'a pas d'opinion. Elle aide a prendre en main des sujets complexes : extraire les arguments
d'un texte dense, resumer un fil de 50 commentaires, suggerer un brouillon de synthese. Mais chaque
production IA est :
- **Marquee visuellement** comme telle (B612 Mono = "la machine a dit ca")
- **Editable et supprimable** par l'humain (l'IA propose, l'humain dispose)
- **Sourcee** : le resume IA pointe vers le passage exact qu'il resume, le brouillon de synthese
  contient des `[src:extraction-42]` qui renvoient aux sources humaines
- **Jamais presentee comme une verite** — c'est une aide a la lecture, pas un oracle

La confiance dans le LLM n'existe que si tout est comprehensible. Si l'utilisateur ne peut pas
verifier en 2 clics d'ou vient une phrase generee, le systeme a echoue. Le mode comparaison
cote-a-cote (Etape 5.8) incarne cette valeur : chaque modification entre deux versions montre
**exactement** quelles sources humaines l'ont motivee.

### Geometrie du debat — observer la forme d'une deliberation

Le cycle deliberatif (lecture → extraction → debat → synthese) produit des donnees structurees :
des extractions typees par hypostase, des statuts de debat, des commentaires, des contributeurs,
des liens entre documents. Ces donnees dessinent une **forme** — la geometrie du debat.

Cette geometrie n'est pas un jugement ("bon debat" / "mauvais debat"). C'est une **cartographie** :
ou en est le debat, quelle est sa forme, quels sont ses angles morts, ses zones denses et ses zones vides.
C'est le dodecaedre a construire — chaque facette revele un aspect de la deliberation.

Les facettes de la geometrie :

| Facette | Question a laquelle elle repond | Brique dans le produit |
|---|---|---|
| **Spatiale** | Ou sont les debats dans le texte ? | Pastilles de marge, surlignage |
| **Statistique** | Quel % du debat est consensuel ? | Dashboard de consensus |
| **Thermique** | Ou ca chauffe ? Ou c'est froid ? | Heat map du debat |
| **Structurelle** | Quels types d'arguments sont couverts ? Quels gaps ? | Alignement par hypostases |
| **Sociale** | Qui participe ? Qui est silencieux ? | Filtre "qui a dit quoi" |
| **Temporelle** | Le debat avance-t-il ou stagne-t-il ? | Notifications de progression |

Aucune facette seule ne decrit la sante du debat. C'est leur **combinaison** qui donne la geometrie
complete. Un debat peut avoir 90% de consensus (statistique excellente) mais n'avoir couvert que des
CONJECTURES sans aucun PRINCIPE ni AXIOME (structure incomplete). Ou bien couvrir tous les types
d'hypostases (structure riche) mais avec un seul contributeur (desequilibre social).

L'ambition d'Hypostasia est de rendre cette geometrie **visible et navigable** — pas de la noter,
mais de la donner a voir pour que les participants et le facilitateur puissent decider ensemble
"sommes-nous prets a synthetiser ?" en connaissance de cause.

> Ce concept est a approfondir avec Jean et Dominique. La forme visuelle du dodecaedre (radar chart ?
> graphe de liens ? autre representation ?) reste a definir. Les briques techniques sont posees
> progressivement dans les Etapes 1.4, 1.12, 1.15, 2.4, et la section dediee ci-dessous.

---

## Avis strategique — Forces et doutes

### Points forts (positionnement marche)

- **Creneau vide identifie** : aucun outil ne fait "deliberation structuree avec tracabilite complete". Google Docs fait la collab sans tracabilite des decisions. Confluence fait le knowledge management sans debat. ChatGPT produit du texte sans sourcage. Hypostasia est au croisement.
- **Cas d'usage a forte valeur** : cabinets juridiques (contrats, clauses), collectivites territoriales (chartes, PLU, concertations), ESS/cooperatives (gouvernance partagee, statuts), recherche academique (annotation de corpus, revue par les pairs).
- **Cycle iteratif source = garde-fou anti AI-slop** : dans un marche ou tout le monde colle du LLM partout sans verification, la tracabilite totale est un argument de vente puissant. "Chaque mot remonte a sa source humaine."
- **Alignement cross-documents par hypostases** : capacite unique a comparer des documents de natures differentes (verbatim, lois, chartes) en les alignant par types semantiques communs (PHENOMENE, CONJECTURE, AXIOME...). C'est le pont entre "ce qui est vecu", "ce qui est prescrit" et "ce qui est organise" — un besoin reel en recherche, en gouvernance et en audit. (→ Etape 1.12, Etape 6.2)
- **Deep Research contextuel integre aux extractions** : chaque extraction peut etre automatiquement enrichie par des sources externes (articles academiques, rapports, web) via Local Deep Research. Les sources apparaissent directement dans la carte d'extraction, comme un apparat critique integre — le standard attendu en recherche universitaire et en redaction juridique. Pas de panneau separe, pas de rupture de contexte. (→ Etape 7.2)
- **Geometrie du debat** : les donnees produites par le cycle deliberatif (extractions typees, statuts, commentaires, contributeurs, liens cross-documents) dessinent une forme — la geometrie du debat. Hypostasia rend cette geometrie visible a travers plusieurs facettes : spatiale (ou sont les debats dans le texte), statistique (% de consensus), thermique (heat map de l'intensite), structurelle (alignement par hypostases), sociale (qui participe), temporelle (comment le debat evolue). Aucun outil de deliberation ne propose cette cartographie multi-axes. C'est le dodecaedre a construire — pas un jugement, une observation navigable qui permet aux participants de decider ensemble "sommes-nous prets a synthetiser ?". (→ Etapes 1.4, 1.12, 1.15, 1.16, 2.4 ; concept a approfondir avec Jean et Dominique)
- **Stack technique sobre** : Django + HTMX = pas de frontend JS a maintenir, time-to-market rapide, maintenable par une petite equipe.

### Doutes et risques identifies

- **Trop de features, pas assez de focus** : 10 phases couvrant extension navigateur, import multi-format, transcription, LLM multi-provider, auth, collab, recherche semantique, deep research, live audio, boitier WiFi offline, tests E2E. C'est le plan d'un produit a 50 personnes sur 3 ans. Risque de dispersion.
- **Phases 8 (live audio) et 9 (boitier WiFi) sont des produits a part entiere** : la transcription live est un marche sature (Otter, Fireflies, Granola). Le boitier WiFi est du hardware + reseau + ops. Le differenciateur d'Hypostasia n'est pas la transcription, c'est ce qu'on fait apres (extraction, debat, synthese).
- **Pas de modele economique** : qui paie les appels LLM ? Abonnement ? Cle API utilisateur ? Hebergement ? Ca influence l'architecture (multi-tenant, quotas, facturation).
- **Export / backup / portabilite** : adresse dans les regles transverses (regle 8), mais pas encore implemente. A traiter au fil des phases, en priorite avant toute mise en prod.
- **Recommandation** : decouper en "Hypostasia Core" (Phases 1-5, le coeur deliberatif) et "Hypostasia Live" (Phases 8-9, produit separe si valide par des pilotes). Les Phases 6-7 sont des ameliorations de Core, pas des phases distinctes.

---

## Table des matieres

1. [Etat actuel du POC](#1-etat-actuel-du-poc)
2. [Phase 1 — Socle technique](#2-phase-1--socle-technique)
3. [Phase 2 — Gestion utilisateurs et partage](#3-phase-2--gestion-utilisateurs-et-partage)
4. [Phase 3 — Providers IA unifies](#4-phase-3--providers-ia-unifies)
5. [Phase 4 — Prompts et couts](#5-phase-4--prompts-et-couts)
6. [Phase 5 — Edition collaborative et fil de tracabilite](#6-phase-5--edition-collaborative-et-fil-de-tracabilite)
7. [Phase 6 — Recherche semantique](#7-phase-6--recherche-semantique)
8. [Phase 7 — Deep Research automatique](#8-phase-7--deep-research-automatique)
9. [Phase 8 — Transcription temps reel et prise de notes live](#9-phase-8--transcription-temps-reel-et-prise-de-notes-live)
10. [Phase 9 — Mode 100% local et hors-ligne](#10-phase-9--mode-100-local-et-hors-ligne)
11. [Regles transverses](#11-regles-transverses)

---

## Resume — Vue d'ensemble en quelques lignes (tout est detaille plus bas)

### Vue d'ensemble de l'interface cible

**Mode lecture normal** — le texte est au centre, les annotations en marge :

```
┌────────────────────────────────────────────────────────────────────┐
│ [☰]  Titre du document        [Dashboard ▾] [Analyser] [E] [L] [⚙]│
│  ↑                                ↑            ↑        ↑   ↑     │
│  arbre                        consensus     lancer   drawer focus  │
│  overlay                      (Etape 1.4)   extract.  vue   mode   │
│  (T)                                        IA       liste  lecture │
├───────────────────────────────────────────────────────────────┬────┤
│ 📊 Depuis votre derniere visite : 2 → CONSENSUEL, 3 comm. [✕]│    │
│    (bandeau de notification — Etape 1.16)                     │    │
├───────────────────────────────────────────────────────────────┤    │
│                                                               │ m  │
│   L'intelligence artificielle souleve des                     │ a  │
│   questions fondamentales sur l'avenir du                     │ r  │
│   travail creatif.                                            │ g  │
│                                                               │ e  │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │    │
│  ░ Plusieurs participants ont exprime des inquietudes     ░   │ ●  │
│  ░ quant a la disparition des metiers creatifs.           ░   │ ↑  │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │ pastille
│  ↑ surlignage hl-extraction (clic ou J/K pour deplier)       │ coloree
│                                                               │ par  │
│   ┌────────────────────────────────────────────────────────┐  │ statut
│   │ CONJECTURE              B612 gras uppercase  [▴]      │  │    │
│   │                         couleur famille Speculatif     │  │    │
│   │ L'IA va transformer     B612 Mono 14pt                 │  │    │
│   │ les metiers creatifs    (typo-machine = "l'IA a dit")  │  │    │
│   │ en metiers de                                          │  │    │
│   │ supervision.                                           │  │    │
│   │                                                        │  │    │
│   │ « Je pense que dans     Lora italique 16pt             │  │    │
│   │   5 ans, on ne          (typo-citation = "un humain    │  │    │
│   │   dessinera plus »       a ecrit ca")                  │  │    │
│   │                                                        │  │    │
│   │ ● DISCUTE  #ia #metiers                    📎 2  💬 3  │  │    │
│   │   ↑ badge statut colore (Etape 1.4)                    │  │    │
│   │                                                        │  │    │
│   │ ── Commentaires ──────────────────────────────         │  │    │
│   │ Marie :               Srisakdi 20pt bleu               │  │    │
│   │ Trop reducteur, il y  Srisakdi 16pt bleu               │  │    │
│   │ a des metiers ou la   (typo-lecteur = "quelqu'un       │  │    │
│   │ main reste essentielle  reagit maintenant")             │  │    │
│   └────────────────────────────────────────────────────────┘  │    │
│   ↑ carte inline depliee sous le passage (Etape 1.3 bis)     │    │
│                                                               │    │
│   En revanche, le secteur juridique semble                    │    │
│   mieux prepare, avec des outils deja                         │ ●● │
│   operationnels dans les cabinets.                            │    │
│                                                               │    │
│   Le consensus se forme autour de l'idee                      │    │
│   que la regulation est necessaire.                           │ ○  │
│                                                               │    │
└───────────────────────────────────────────────────────────────┴────┘

Legende :
 ● pastille coloree = statut de debat (vert ○ consensuel, rouge ● discutable,
   ambre ● discute, orange ● controverse) — Etape 1.4
 ░░ surlignage = passage extrait, fond colore si heat map active — Etape 1.15
 3 polices = 3 provenances : machine (B612 Mono) / citation (Lora) / lecteur (Srisakdi)
```

**Avec le drawer vue liste ouvert** (touche E) — vision facilitateur :

```
┌─────────────────────────────────────┬──────────────────────────────┐
│                                     │ ≡ 12 extractions        [✕]  │
│  Texte de l'article                 │ Tri: [Position ▾]  Filtre: ▾ │
│  toujours visible                   │                              │
│  en dessous, avec pastilles         │ ┌──────────────────────────┐ │
│  de marge                           │ │ CONJECTURE    ● DISCUTE  │ │
│                                     │ │ L'IA va transformer...   │ │
│                                     │ │ 💬 3  📎 2  ━━━ (dense)  │ │
│                                     │ └──────────────────────────┘ │
│                                     │ ┌──────────────────────────┐ │
│                                     │ │ LOI           ○ CONSENS. │ │
│                                     │ │ La loi d'Amara...        │ │
│                                     │ │ 💬 1  ── (leger)         │ │
│                                     │ └──────────────────────────┘ │
│                                     │ ┌──────────────────────────┐ │
│                                     │ │ PHENOMENE     ● DISCUTAB │ │
│                                     │ │ Le marche de l'IA...     │ │
│                                     │ └──────────────────────────┘ │
│                                     │                              │
│                                     │ Curation : 3 masquees        │
│                                     │ [Voir masquees]              │
│                                     │                              │
│                                     │ ── Dashboard rapide ──       │
│                                     │ ⚫ 8 CS  ▶ 2 DSC  ▷ 1 DS   │
│                                     │ ████████░░░  71% consensus   │
└─────────────────────────────────────┴──────────────────────────────┘
```

### Introduction
Hypostasia est un outil de gestion de debat et de connaissance. Son cycle fondamental :
Lecture → Extraction → Commentaire → Debat → Synthese → Nouvelle version.
**Tracabilite totale** : chaque mot remonte a sa source humaine. Pas de magie, pas d'hallucination.

**3 valeurs fondatrices** : le texte est un commun, le travail humain est la valeur, le LLM est un outil pas un auteur.

**Concept fondateur** : la **geometrie du debat** — 6 facettes (spatiale, statistique, thermique, structurelle, sociale, temporelle) qui cartographient la forme d'une deliberation. Pas un jugement, une observation navigable. A co-construire avec Jean et Dominique.

### Etat actuel (section 1)
POC fonctionnel : extension navigateur, import multi-format, transcription audio diarisee, extraction IA configurable (LangExtract), commentaires, versioning basique, extraction manuelle.
**Manques critiques** : pas de statuts de debat, pas de lien source entre versions, layout 3 colonnes inadapte, pas de distinction typographique humain/machine, pas de CRUD complets.

### Phase 1 — Socle technique (section 2)
17 etapes. C'est la plus grosse phase.

**Decisions impactantes** :
- **Etape 1.3 bis** : abandon du layout 3 colonnes → **lecteur avec marginalia**. Le texte occupe toute la largeur. Extractions inline sous les passages. Arbre et vue liste en overlay. Decision fondamentale qui simplifie tout le responsive et resout le split-attention.
- **Etape 1.4** : statuts de debat (CONSENSUEL/DISCUTABLE/DISCUTE/CONTROVERSE) + dashboard de consensus + pastilles de marge colorees. Le seuil de consensus conditionne l'acces a la synthese.
- **Etape 1.8** : charte typographique Yves avec 4 ajustements UX (Lora pour les citations au lieu de B612 italic, couleurs distinctes DISCUTE/DISCUTABLE, Srisakdi 16pt pour les fils longs, jaune WCAG remplace par orange fonce). 8 familles de couleurs pour les hypostases. Preparation dark mode via CSS variables.
- **Etape 1.12** : alignement basique par hypostases des la Phase 1 (pas besoin d'embeddings). Differenciateur produit montre tot aux financeurs.
- **Etape 1.13** : raccourcis clavier (?, L, E, T, J/K, C, S, X, /, Escape).
- **Etape 1.14** : mobile = lecture augmentee + reaction rapide + capture + extraction IA (analyseur par defaut). Pas d'extraction manuelle ni de wizard sur mobile.
- **Etape 1.15** : heat map du debat — fond colore par intensite sur le texte.
- **Etape 1.16** : notifications de progression — signal que la geometrie du debat a change.

### Phase 2 — Users (section 3)
Auth Django, propriete/partage de dossiers, auth dans l'extension.
**Decision** : filtre "qui a dit quoi" (Etape 2.4) — combinable avec la heat map pour voir la temperature du debat par contributeur.

### Phase 3 — Providers IA (section 4)
Couche d'abstraction LLM (`core/llm_providers.py`). Ajout Ollama, Anthropic. Transcription multi-provider (Whisper).
**Decision** : garder LangExtract pour l'extraction, contribuer en upstream pour Ollama/Anthropic, forker si refuse.

### Phase 4 — Prompts et couts (section 5)
Gestion des analyseurs dans le front (sortir de l'admin Django). Calcul des couts fiabilise. Historique des prompts.

### Phase 5 — Collab et tracabilite (section 6)
Le coeur du produit.
**Decisions impactantes** :
- **Etape 5.1** : modele `SourceLink` — lie chaque passage d'une version a son origine (source + extraction + commentaires).
- **Etape 5.6** : wizard de synthese en 5 etapes (selection → revue → redaction → verification sourcage → publication). Accessible uniquement quand le seuil de consensus est atteint.
- **Etape 5.7** : export PDF (WeasyPrint) et HTML (single-file interactif). L'artefact final du debat.
- **Etape 5.8** : comparaison cote-a-cote avec provenance explicite (✎ humain, 🤖 IA validee, 🤖⚠️ IA non modifiee). Compteur de sourcage en bas du diff.

### Phase 6 — Recherche semantique (section 7)
Embeddings + pgvector. Recherche filtree + **alignement cross-documents par hypostases** (le differenciateur du produit). Tableau croise hypostase × documents avec detection de gaps.

### Phase 7 — Deep Research (section 8)
Integration Local Deep Research (LDR). Sources externes dans les cartes d'extraction (pas dans un panneau separe).
**Decision** : sources dans les cartes en section accordion, pas en panneau dedie.

### Phase 8 — Live audio (section 9)
Side-projet fablab. MVP : bouton rec + chunks POST + polling HTMX. Extensions : streaming, edition collaborative live.

### Phase 9 — Mode local (section 10)
Side-projet fablab. Boitier WiFi isole, zero internet. Ollama + Whisper local. Docker compose "valise".

### Regles transverses (section 11)
Stack CCC, pas de sur-ingenierie, dark mode ready via CSS variables, export/portabilite, modele economique a clarifier.

---

## 1. Etat actuel du POC

### 1.1 Extension navigateur (`extension/`)

**Fichiers** : `popup.js`, `popup.html`, `content.js`, `sidebar.js`, `sidebar.html`, `background.js`, `options.js`

**Ce qui fonctionne** :
- Popup avec bouton "Recolter" qui injecte Readability.js dans la page active
- Verification de doublon par URL exacte (`GET /api/pages/?url=...`)
- Envoi du contenu (html_original, html_readability, title, url) en POST JSON a `/api/pages/`
- Sidebar injectable via content script (iframe, toggle, scroll-to-text)
- URL serveur configurable via `chrome.storage.sync` + page options

**Problemes identifies** :
- La verification de doublon ne compare que l'URL exacte — pas de deduplication par contenu (content_hash)
- Pas de gestion du cas ou l'URL change mais le contenu est identique (pages dynamiques, UTM params)
- L'extension n'affiche pas le statut du serveur (online/offline)
- Pas de feedback sur ce qui se passe cote serveur apres l'envoi
- La sidebar charge les donnees via `test_sidebar_view` qui est une vue de test, pas de production
- Pas de gestion d'authentification (sera necessaire avec la Phase 2)

### 1.2 Reception et classement par dossier

**Fichiers** : `core/views.py` (PageViewSet), `front/views.py` (ArbreViewSet, DossierViewSet, PageViewSet)

**Ce qui fonctionne** :
- API JSON `core/PageViewSet` : `list()` avec filtre URL, `create()` avec derivation automatique de text_readability et content_hash
- Arbre de dossiers HTMX avec pages orphelines
- Creation de dossier, classement de page dans un dossier (drag-and-drop ou action)
- Pages racines vs restitutions filtrees dans l'arbre

**Problemes identifies** :
- Pas de suppression de page depuis l'interface (seulement admin Django)
- Pas de renommage de dossier
- Pas de suppression de dossier (ni vide ni avec pages)
- Pas de tri/filtre dans l'arbre (par date, titre, source_type)
- Pas de pagination — toutes les pages chargees d'un coup

### 1.3 Import de documents et transcription audio

**Fichiers** : `front/views.py` (ImportViewSet), `front/serializers.py`, `front/tasks.py`, `front/services/transcription_audio.py`, `front/services/conversion_fichiers.py`

**Ce qui fonctionne** :
- Import de fichiers texte/PDF/DOCX/PPTX/XLSX via MarkItDown
- Import de fichiers JSON (re-import de transcriptions exportees)
- Import audio (MP3, WAV, M4A, etc.) avec lancement asynchrone Celery
- Transcription via Voxtral (Mistral AI) avec diarisation (identification locuteurs)
- Mode mock pour tests sans API
- Polling HTMX toutes les 3s pendant la transcription
- Affichage diarise avec couleurs par locuteur et timestamps

**Problemes identifies** :
- Un seul provider de transcription (Voxtral/Mistral) — pas de Whisper/OpenAI
- Pas de progress bar (juste "en cours..." puis resultat)
- Le fichier audio temporaire est supprime apres transcription — pas de re-ecoute possible
  sauf si `source_file` est renseigne (ce qui n'est pas toujours le cas)
- Pas de segmentation manuelle (fusionner/splitter des segments)

### 1.4 Edition de transcription (texte + locuteur)

**Fichiers** : `front/views.py` (LectureViewSet actions: renommer_locuteur, editer_bloc, supprimer_bloc, formulaire_editer_bloc, formulaire_renommer_locuteur)

**Ce qui fonctionne** :
- Renommage de locuteur avec 3 portees : "ce bloc seul", "ce bloc et suivants", "tous"
- Edition inline du texte d'un bloc (textarea pre-rempli, preservant timestamps proportionnels)
- Suppression d'un bloc de transcription
- Reconstruction automatique du HTML diarise et text_readability apres chaque modification

**Problemes identifies** :
- Pas d'historique des modifications (undo impossible)
- La redistribution des timestamps est proportionnelle, pas semantique
- Pas de fusion de blocs consecutifs
- Pas de re-ecoute du segment audio pendant l'edition

### 1.5 Framework d'extraction configurable

**Fichiers** : `hypostasis_extractor/models.py` (AnalyseurSyntaxique, PromptPiece, AnalyseurExample, ExampleExtraction, ExtractionAttribute), `hypostasis_extractor/services.py`, `front/tasks.py` (analyser_page_task, reformuler_entite_task, restituer_debat_task)

**Ce qui fonctionne** :
- Analyseurs configurables avec 3 types : `analyser`, `reformuler`, `restituer`
- Prompt compose de pieces ordonnees (definition, instruction, format, context)
- Exemples few-shot avec extractions typees et attributs cle-valeur
- Extraction via LangExtract (Google Gemini + OpenAI GPT)
- Reformulation d'une extraction via LLM (Celery async)
- Restitution de debat (extraction + commentaires + reformulation → LLM → nouvelle version)
- Previsualisation du prompt complet avant envoi (estimation tokens + cout)
- Anti-doublon : pas de re-lancement si un job est deja en cours
- Timeout a 5 minutes avec feedback

**Problemes identifies** :
- LangExtract ne supporte que Google Gemini et OpenAI — pas Ollama, pas Anthropic. Strategie : garder LangExtract tant que ca marche, contribuer au projet open-source pour ajouter d'autres providers (Ollama, Anthropic). Si l'equipe d'origine refuse le merge, forker la lib.
- L'appel LLM pour reformulation/restitution est code en dur dans `front/tasks.py` (`_appeler_llm_reformulation`) — pas de couche d'abstraction
- Le mock mode du services.py utilise `gemini-2.5-flash` comme model_id au lieu d'un vrai mock
- Les 3 fonctions (run_langextract_job, run_analyseur_on_page, analyser_page_task) font des choses similaires avec du code duplique
- L'interface de configuration des analyseurs est dans l'admin Django (pas dans le front)
- **La synthese IA ne source pas ses affirmations** : le LLM recoit extraction + commentaires mais sa reponse n'est pas liee paragraphe par paragraphe aux sources qui l'ont alimentee

### 1.6 Commentaires sur les extractions

**Fichiers** : `hypostasis_extractor/models.py` (CommentaireExtraction), `front/views.py` (ExtractionViewSet actions: commenter, fil_discussion, vue_commentaires)

**Ce qui fonctionne** :
- Ajout de commentaire sur une extraction (prenom + texte, pas d'auth)
- Fil de discussion par extraction
- Indicateur visuel dans le HTML annote (classe CSS `hl-commentee`)
- Comptage des commentaires par extraction

**Problemes identifies** :
- Pas d'authentification — identification par prenom uniquement
- Pas de modification ni suppression de commentaire
- Pas de notification quand un commentaire est ajoute
- **Pas de statut de debat** : rien n'indique si un debat sur une extraction est ouvert, resolu, ou en attente de consensus
- **Pas de lien vers la version suivante** : quand un debat aboutit a une synthese, le commentaire ne pointe pas vers le texte produit

### 1.7 Versioning de texte (restitutions)

**Fichiers** : `core/models.py` (Page.parent_page, version_number, version_label), `front/views.py` (ExtractionViewSet.restituer_debat)

**Ce qui fonctionne** :
- Chaine de versions : page racine → restitutions via parent_page FK
- Navigation entre versions dans le partial de lecture
- Restitution manuelle (texte saisi) ou IA (generee par LLM depuis debat)
- Chaque version a un numero et un label descriptif

**Problemes identifies (critiques pour le cycle iteratif)** :
- **Pas de lien source entre versions** : quand on cree la version N, rien ne relie chaque paragraphe de N au passage source dans N-1, ni aux commentaires/extractions qui ont motive le changement. C'est le probleme central — sans ca, on perd la tracabilite
- Pas de diff entre versions
- Pas de merge/cherry-pick entre versions
- Le versioning est lie aux extractions (restitution par entite) mais pas au texte global
- Pas de vue "fil de discussion" qui montre le chemin complet : texte original → extraction → commentaires → synthese → nouvelle version
- Une restitution IA n'a aucun lien explicite vers les commentaires qui l'ont motivee (le prompt les inclut mais le resultat ne les reference pas)

### 1.8 Few-shot et demonstration d'extraction

**Fichiers** : `hypostasis_extractor/views.py` (AnalyseurViewSet), `hypostasis_extractor/models.py` (AnalyseurExample, ExampleExtraction, ExtractionAttribute, AnalyseurTestRun, TestRunExtraction)

**Ce qui fonctionne** :
- CRUD complet des analyseurs, pieces de prompt, exemples, extractions, attributs
- Promotion d'extractions de production en exemples d'entrainement
- Test d'un analyseur sur un exemple (anti data-leakage : exclut l'exemple teste des few-shot)
- Annotation humaine des extractions de test (validated/rejected)
- Promotion d'extractions de test en exemples attendus

**Problemes identifies** :
- L'interface de gestion des analyseurs est complexe (beaucoup d'actions HTMX imbriquees)
- Pas de metriques de qualite automatiques (precision, recall entre attendus et obtenus)
- Pas d'export/import d'analyseur (prompt + exemples) pour partage entre instances

### 1.9 Extraction manuelle par selection de texte

**Fichiers** : `front/views.py` (ExtractionViewSet.manuelle, ExtractionViewSet.creer_manuelle)

**Ce qui fonctionne** :
- Selection de texte dans la zone de lecture → formulaire HTMX
- Creation d'une ExtractedEntity avec start_char/end_char positionnes
- Attributs cle-valeur dynamiques
- Annotation HTML du texte selectionne (span avec classe hl-extraction)

**Problemes identifies** :
- Le mapping des positions texte est fragile (mismatch possible avec les entites HTML)
- Pas de suppression d'extraction manuelle depuis l'interface

### 1.10 Indication de debat sur le texte

**Fichiers** : `front/utils.py` (annoter_html_avec_barres)

**Ce qui fonctionne** :
- Annotation HTML : chaque extraction est enveloppee dans un `<span class="hl-extraction">`
- Les extractions commentees ont la classe supplementaire `hl-commentee`
- Clic sur une extraction dans le texte → scroll vers la carte d'extraction correspondante
- Mapping bidirectionnel positions texte ↔ positions HTML avec gestion des entites HTML

**Problemes identifies** :
- Les extractions qui se chevauchent ne sont pas gerees (le premier span gagne)
- La couleur ne distingue pas le type d'extraction (analyseur, manuelle, reformulee)
- Pas d'indicateur inline du nombre de commentaires

### 1.11 Design actuel du front

**Fichiers** : `front/templates/front/base.html` (1602 lignes, tout CSS+JS inline), `hypostasis_extractor/templates/hypostasis_extractor/includes/_card_body.html`

**Etat actuel** :
- **Polices** : Inter (UI) + Lora (zone de lecture) via Google Fonts CDN
- **Layout actuel** : 3 colonnes flex — sidebar gauche (arbre, `w-64`) | zone lecture (`flex-1`, `max-w-3xl`) | sidebar droite (extractions, `w-[32rem]`, repliee par defaut)
- **Layout cible** : lecteur avec marginalia — le texte occupe toute la largeur, les extractions s'affichent inline sous le passage concerne (voir Etape 1.3 bis "Refonte layout"). L'arbre est un overlay sur demande, le panneau d'extractions est un drawer temporaire (vue liste). Ce changement est detaille dans l'Etape 1.3 bis
- **Cartes d'extraction** : `_card_body.html` affiche 4 attributs generiques (`attr_0` a `attr_3`). L'hypostase est dans `attr_0` (pastilles indigo generiques), le resume IA dans `attr_1`, la citation source dans `text`, le statut dans `attr_2`, les hashtags dans `attr_3`
- **Annotations HTML** : `.hl-extraction` avec icones Lucide en marge gauche (`::before`), 3 variantes (quote bleu, message-circle ambre, bookmark violet)
- **CSS** : 219 lignes inline dans `<style>` de `base.html`
- **JS** : ~1260 lignes inline dans `<script>` de `base.html` (22+ event handlers, sidebars, modals, HTMX)
- **Couleurs** : palette Tailwind par defaut (indigo, slate, amber, red, green)

**Ecarts avec la charte cible** (charte Yves + ajustements UX, voir section "Reference : charte typographique") :
- **Typographie** : Inter/Lora au lieu de B612/B612 Mono/Lora/Srisakdi (Lora est deja chargee, les 3 autres non)
- **Distinction humain vs machine** : absente — le resume IA et la citation source ont des styles presque identiques. Cible : B612 Mono (machine) vs Lora italique (citation humaine) vs Srisakdi (lecteur)
- **Hypostase** : affichee comme pastille indigo generique, pas de couleur par famille
- **Statuts de debat** : couleurs Tailwind generiques au lieu des hex ajustes (`#429900`, `#B61601`, `#D97706`, `#FF4000`)
- **Icones de statut** : absentes (cible : ⚫ consensuel, ▶ discutable, ▷ discute, ! controverse)
- **Interventions lecteur** : pas de style distinct pour les commentaires/corrections humaines
- **CSS/JS inline** : tout dans `base.html`, pas de fichiers statiques separes

### Reference : familles de couleurs des hypostases

Le modele `HypostasisChoices` (`core/models.py:214-248`) definit 29 hypostases. Pour la lisibilite des cartes d'extraction, elles sont regroupees en 8 familles de couleurs :

| Famille | Hypostases | Couleur |
|---------|-----------|---------|
| Epistemique | classification, axiome, theorie, definition, formalisme | Indigo |
| Empirique | phenomene, evenement, donnee, variable, indice | Emeraude |
| Speculatif | hypothese, conjecture, approximation | Ambre |
| Structurel | structure, invariant, dimension, domaine | Ardoise |
| Normatif | loi, principe, valeur, croyance | Violet |
| Problematique | aporie, paradoxe, probleme | Rouge |
| Mode/Variation | mode, variation, variance, paradigme | Cyan |
| Objet/Methode | objet, methode | Gris |

### Reference : charte typographique (Yves + ajustements UX)

Source initiale : `Retour design Yves/CHARTE puce.pdf`

La charte de Yves est la base. Les ajustements ci-dessous corrigent 4 problemes identifies lors de la review UX.

#### Ajustement 1 : Lora pour les citations humaines (au lieu de B612 italique)

**Pourquoi** : B612 a ete concue pour les cockpits d'Airbus — optimisee pour la lisibilite en conditions de stress, en petite taille, sur ecrans basse resolution. Elle est fonctionnelle mais froide. Pour des labels et statuts a 12px, c'est parfait. Mais pour les citations humaines en italique a 18pt, elle manque de caractere. Une citation comme `[...] Elinor Ostrom a surtout travaille sur la notion de dilemme social [...]` en B612 italique ressemble a un rapport d'ingenieur, pas a une parole humaine qu'on veut preserver.

**Solution** : garder B612 pour les labels/statuts et B612 Mono pour le texte machine (c'est son territoire naturel). Mais pour les citations humaines (`[...]`), utiliser **Lora italique** (deja chargee dans le projet). La chaleur de la citation humaine doit contraster avec la froideur de la synthese machine — c'est le coeur du produit.

#### Ajustement 2 : DISCUTE et DISCUTABLE doivent avoir des couleurs differentes

**Pourquoi** : dans la charte Yves, DISCUTE et DISCUTABLE sont tous deux en rouge `#B61601`. La seule difference est l'icone (▷ vs ▶) et le poids (courant vs gras). A 12px dans un panneau de 32rem, sur un ecran de laptop a 1m de distance, cette distinction est invisible. C'est un probleme de design d'information : deux statuts semantiquement differents ne peuvent pas partager la meme couleur.

**Solution** :
- DISCUTABLE (on *peut* en debattre) → rouge `#B61601` ▶ — le debat est possible mais pas encore lance
- DISCUTE (le debat *a eu lieu*) → orange fonce `#D97706` ▷ — le debat est en cours ou a eu lieu
- Si la nuance s'avere trop fine en pratique, fusionner les deux en un seul statut "EN DEBAT"

#### Ajustement 3 : Srisakdi a 16pt pour le corps des commentaires (au lieu de 20pt)

**Pourquoi** : dans le mockup de Yves, il y a une seule ligne de lecteur : *"Ca fait longtemps que je ne suis pas intervenu."* Ca rend bien. Mais dans un vrai fil de discussion avec 5-10 commentaires de 3-4 lignes chacun, du texte en cursive 20pt bleu va ecraser visuellement tout le reste. Le panneau droit fait 32rem — chaque ligne contiendra ~30 caracteres en Srisakdi 20pt. C'est illisible.

**Solution** : Srisakdi a **16pt** pour le corps des commentaires. 20pt uniquement pour la signature/nom de l'auteur. Le nom en Srisakdi 20pt sert de marqueur visuel "c'est un humain qui parle", le corps en Srisakdi 16pt reste lisible dans un fil long.

#### Ajustement 4 : le jaune `#FFDC00` (CONTROVERSE) echoue au contraste WCAG

**Pourquoi** : la charte Yves propose deux couleurs pour CONTROVERSE : orange `#FF4000` et jaune `#FFDC00`. Le jaune `#FFDC00` sur fond blanc donne un ratio de contraste de **1.3:1**. Le minimum WCAG AA pour du texte est **4.5:1**. C'est illisible — un utilisateur malvoyant ou un ecran en plein soleil ne verra rien. Meme l'orange `#FF4000` en texte direct sur blanc donne **3.7:1**, en dessous du seuil AA.

C'est un probleme d'accessibilite mais aussi un probleme fonctionnel : le statut CONTROVERSE est le plus important a reperer visuellement (c'est un signal d'alerte). S'il est illisible, il perd sa fonction.

**Solution** :
- **Texte du badge** : utiliser `#C2410C` (orange fonce, ratio **4.8:1** sur blanc = WCAG AA conforme) au lieu de `#FF4000`
- **Fond du badge** : utiliser `#FFF4ED` (orange tres pale) pour le contraste fond/texte
- Le `#FF4000` peut servir de couleur d'**accent** (bordure gauche, icone `!`) mais jamais comme couleur de texte
- Le jaune `#FFDC00` est ecarte definitivement pour le texte. Il peut etre conserve comme couleur secondaire d'accent (ex: bordure, gradient) si necessaire
- **Regle generale** : toutes les couleurs de texte de statut doivent etre verifiees WCAG AA (4.5:1 minimum sur fond blanc). Verifier aussi le vert `#429900` (ratio **3.9:1** sur blanc — limite, a surveiller ; sur fond `#f0fdf4` c'est OK)

Couleurs de statut accessibles :

| Statut | Couleur texte | Couleur fond | Ratio WCAG | Icone |
|--------|--------------|-------------|------------|-------|
| CONSENSUEL | `#15803d` (vert fonce) | `#f0fdf4` (vert pale) | **5.1:1** | ⚫ |
| DISCUTABLE | `#B61601` (rouge) | `#fef2f2` (rouge pale) | **6.2:1** | ▶ |
| DISCUTE | `#b45309` (ambre fonce) | `#fffbeb` (ambre pale) | **4.8:1** | ▷ |
| CONTROVERSE | `#C2410C` (orange fonce) | `#FFF4ED` (orange pale) | **4.8:1** | ! |

> Note : le vert `#429900` de la charte Yves est remplace par `#15803d` (Tailwind green-700) pour le texte,
> car `#429900` donne 3.9:1 sur blanc — en dessous du seuil AA. Le vert `#429900` reste utilisable
> comme fond ou accent mais pas comme couleur de texte.

#### Charte typographique consolidee

| Element | Police | Style | Taille | Couleur | Justification |
|---------|--------|-------|--------|---------|---------------|
| Labels / statuts de debat | B612 Mono | gras | 12pt | selon statut | Aviation font = lisible en petit, ideal pour labels |
| Resume IA (texte machine) | B612 Mono | courant | 14pt | neutre `#475569` | Mono = signal "la machine a dit ca" |
| Citations humaines (source) | **Lora** | italique | 16-18pt | texte courant `#1e293b` | Serif chaleureuse = signal "un humain a ecrit ca" (**ajust. 1**) |
| Interventions lecteur (nom) | Srisakdi | regular | 20pt | bleu `#0056D6` | Cursive = signal "quelqu'un reagit maintenant" |
| Interventions lecteur (corps) | Srisakdi | regular | **16pt** | bleu `#0056D6` | Taille reduite pour les fils longs (**ajust. 3**) |

Couleurs des statuts de debat (WCAG AA conforme — **ajust. 4**) :
- **CONSENSUEL** : texte `#15803d` sur fond `#f0fdf4` — icone ⚫ (**ajust. 4** — etait `#429900`, ratio insuffisant)
- **DISCUTABLE** : texte `#B61601` sur fond `#fef2f2` — icone ▶
- **DISCUTE** : texte `#b45309` sur fond `#fffbeb` — icone ▷ (**ajust. 2** — etait rouge `#B61601` dans la charte Yves)
- **CONTROVERSE** : texte `#C2410C` sur fond `#FFF4ED` — icone ! — accent `#FF4000` pour bordure/icone (**ajust. 4** — jaune `#FFDC00` ecarte)

> Regle : toute couleur de texte de statut doit avoir un ratio WCAG AA >= 4.5:1 sur son fond.
> Les couleurs "vives" de la charte Yves (`#429900`, `#FF4000`, `#FFDC00`) sont utilisables
> comme accents (bordures, icones, fonds) mais pas comme couleur de texte.

Structure cible d'une carte d'extraction (mockup Yves `DEBAT extraction 03`, ajuste) :
1. **Header** : hypostase(s) typee(s) en B612 gras uppercase, coloree par famille
2. **Corps** : resume IA en B612 Mono 14pt (texte machine) + citation source en **Lora italique** 16pt entre `[...]`
3. **Footer** : badge statut colore (avec distinction DISCUTE/DISCUTABLE) + hashtags

---

## 2. Phase 1 — Socle technique

> Objectif : stabiliser le code existant, eliminer les dettes techniques, preparer le terrain.

### Etape 1.1 — Nettoyage et deduplication du code d'extraction

**Probleme** : `run_langextract_job()`, `run_analyseur_on_page()`, et `analyser_page_task()` font des choses similaires avec du code duplique pour la construction des exemples LangExtract.

**Actions** :
- [ ] Extraire une fonction unique `_construire_exemples_langextract(analyseur)` dans `hypostasis_extractor/services.py`
- [ ] Supprimer `run_langextract_job()` si plus utilise (verifier les appels)
- [ ] Faire de `analyser_page_task` le seul point d'entree pour les analyses (Celery)

**Fichiers concernes** : `hypostasis_extractor/services.py`, `front/tasks.py`

### Etape 1.2 — CRUD manquants dans le front

**Actions** :
- [ ] Suppression de page (avec confirmation HTMX)
- [ ] Renommage de dossier
- [ ] Suppression de dossier (vide uniquement, ou avec reclassement des pages en orphelines)
- [ ] Suppression d'extraction manuelle
- [ ] Modification/suppression de commentaire

**Fichiers concernes** : `front/views.py`, `front/serializers.py`, templates `front/includes/`

### Etape 1.3 — Extension navigateur : robustesse

**Actions** :
- [ ] Deduplication par content_hash en plus de l'URL (envoyer un hash cote extension, comparer cote serveur)
- [ ] Normaliser l'URL avant comparaison (retirer UTM params, fragment, trailing slash)
- [ ] Afficher un indicateur de statut serveur (online/offline) dans la popup
- [ ] Remplacer `test_sidebar_view` par un vrai endpoint de production

**Fichiers concernes** : `extension/popup.js`, `core/views.py`, `core/serializers.py`

### Etape 1.3 bis — Refonte layout : du 3 colonnes au lecteur avec marginalia

**Argumentaire — pourquoi changer le layout fondamental** :

Le layout 3 colonnes (arbre | lecture | extractions) est un pattern d'IDE/client mail. Il fonctionne
mais ne correspond pas au modele mental d'Hypostasia. Hypostasia est un **outil de lecture augmentee**,
pas un IDE. Le modele mental correct est un **livre annote** : le texte est au centre de l'attention,
les annotations sont en marge, contextuelles.

Problemes concrets du 3 colonnes :
1. **L'arbre est une colonne permanente pour un usage ponctuel** — on choisit un document, puis l'arbre
   est inutile pendant 90% de la session. Il consomme 16rem de largeur en permanence.
2. **Split-attention** — la carte d'extraction est a droite, le passage qu'elle reference est au centre.
   L'utilisateur fait en permanence des allers-retours visuels. C'est le probleme fondamental : deux zones
   separees pour une information contextuellement liee.
3. **Competition spatiale** — sur tout ecran < 27", les 3 colonnes se disputent l'espace. On a concu
   des overlays (Etape 1.8 ajust. 8) pour contourner le probleme, mais le vrai probleme c'est que
   les 3 colonnes ne sont presque jamais necessaires simultanement.

Le layout cible resout ces 3 problemes d'un coup :
- Le texte occupe toute la largeur → confort de lecture optimal
- Les extractions s'affichent inline sous le passage → zero split-attention
- L'arbre est un overlay sur demande → zero gaspillage d'espace
- Pas de media queries complexes pour les petits ecrans → le layout est nativement responsive

**Principe : lecteur avec marginalia**

```
┌──────────────────────────────────────────────────────────┐
│ [☰]  Titre du document                   [Analyser] [⚙] │
│  ↑                                                       │
│  arbre en overlay sur demande (☰ ou touche T)            │
├───────────────────────────────────────────────────┬──────┤
│                                                   │ marge│
│   L'intelligence artificielle souleve des         │      │
│   questions fondamentales sur l'avenir du          │  ●   │ ← pastille DISCUTE
│   travail creatif. Plusieurs participants          │      │
│   ont exprime des inquietudes.                     │      │
│                                                   │      │
│   ┌─────────────────────────────────────────────┐ │      │
│   │ CONJECTURE            [replier ▴]           │ │      │
│   │ L'IA va transformer les metiers creatifs    │ │      │
│   │ en metiers de supervision.                  │ │      │
│   │ « Je pense que dans 5 ans, on ne dessinera  │ │      │
│   │   plus, on pilotera »                       │ │      │
│   │ ● DISCUTE  #ia #metiers    💬 3    📎 2    │ │      │
│   └─────────────────────────────────────────────┘ │      │
│       ↑ carte depliee inline sous le passage      │      │
│                                                   │      │
│   En revanche, le secteur juridique semble        │      │
│   mieux prepare, avec des outils deja             │  ●●  │ ← 2 extractions
│   operationnels dans les cabinets.                │      │
│                                                   │      │
│   Le consensus se forme autour de l'idee          │      │
│   que la regulation est necessaire mais           │  ○   │ ← CONSENSUEL
│   ne doit pas freiner l'innovation.               │      │
│                                                   │      │
└───────────────────────────────────────────────────┴──────┘
```

**Les 3 modes d'affichage des extractions** :

| Mode | Declencheur | Ce qui s'affiche |
|---|---|---|
| **Marginalia** (defaut) | Vue de lecture normale | Pastilles colorees dans la marge droite (statut). Le texte est surligne. Tap/clic sur pastille → deplie la carte inline |
| **Inline deplie** | Clic sur une pastille de marge | La carte d'extraction s'ouvre sous le passage concerne, pousse le texte vers le bas. Bouton replier (▴) pour fermer |
| **Drawer vue liste** | Toggle (touche E, ou bouton "Toutes les extractions") | Overlay a droite (32rem, position fixed, meme que l'overlay 13" prevu avant) montrant TOUTES les cartes en liste scrollable. C'est l'outil du facilitateur pour scanner le debat. Se ferme avec E ou Escape |

**Mockup — Drawer vue liste (overlay)** :

```
┌──────────────────────────────────┬─────────────────────────┐
│                                  │ ≡ 12 extractions   [✕]  │
│   Texte de l'article             │                         │
│   toujours visible               │ ┌─────────────────────┐ │
│   en dessous                     │ │ CONJECTURE     ● DS │ │
│                                  │ │ L'IA va trans...    │ │
│                                  │ │ 💬 3  📎 2         │ │
│                                  │ └─────────────────────┘ │
│                                  │ ┌─────────────────────┐ │
│                                  │ │ LOI            ○ CS │ │
│                                  │ │ La loi d'Amara...   │ │
│                                  │ │ 💬 1               │ │
│                                  │ └─────────────────────┘ │
│                                  │ ┌─────────────────────┐ │
│                                  │ │ PHENOMENE      ● DT │ │
│                                  │ │ Le marche de...     │ │
│                                  │ └─────────────────────┘ │
│                                  │                         │
│                                  │ Curation : 2 masquees   │
│                                  │ [Voir masquees]         │
└──────────────────────────────────┴─────────────────────────┘
```

**L'arbre de dossiers — overlay sur demande** :

```
┌─────────────────────┬────────────────────────────────────┐
│ ☰ Bibliotheque  [✕] │                                    │
│                     │                                    │
│ 📁 Projet IA       │  (le texte reste visible           │
│   📄 Charte v1     │   en dessous, assombri)            │
│   📄 Charte v2     │                                    │
│   📄 CR reunion    │                                    │
│ 📁 Juridique       │                                    │
│   📄 Contrat X     │                                    │
│ 📁 Recherche       │                                    │
│                     │                                    │
│ [+ Nouveau dossier] │                                    │
│ [+ Importer]        │                                    │
└─────────────────────┴────────────────────────────────────┘
```

L'arbre s'ouvre en overlay (position fixed, 16-20rem depuis la gauche, fond blanc, ombre).
Le reste de la page est assombri (backdrop). Clic sur un document → charge la page, ferme l'arbre.
Raccourci `T` pour toggle. Bouton hamburger `☰` toujours visible en haut a gauche.

**Actions** :
- [ ] Supprimer la sidebar gauche permanente. L'arbre devient un overlay (position fixed, toggle via ☰ ou touche T)
- [ ] Supprimer la sidebar droite permanente. Les extractions s'affichent inline (sous le passage) ou en drawer overlay (touche E)
- [ ] Zone de lecture en pleine largeur (`max-w-4xl` centre, marges confortables)
- [ ] Marge droite (3-4rem) avec pastilles colorees par statut de debat :
  - Couleur = statut (vert consensuel, rouge discutable, ambre discute, orange controverse)
  - Taille = nombre d'extractions sur ce passage (1 pastille = 1 extraction, empilees si plusieurs)
  - Clic pastille → deplie la carte inline sous le paragraphe
- [ ] Carte inline : meme contenu que la carte actuelle (hypostase, resume, citation, statut, commentaires, sources)
  - S'insere dans le DOM entre les paragraphes, pousse le texte vers le bas
  - Bouton replier (▴) pour fermer
  - Animation CSS : slideDown 200ms ease
- [ ] Drawer vue liste : overlay droit (32rem, position fixed, transition translateX)
  - Toggle via touche E ou bouton "Toutes les extractions" dans la barre d'outils
  - Affiche toutes les cartes en mode compact (tri, filtre, curation)
  - Clic sur une carte dans le drawer → scroll le texte vers le passage + deplie la carte inline
  - Fermeture : touche E, Escape, ou clic sur le backdrop
- [ ] Arbre overlay : position fixed gauche, 20rem, backdrop assombri
  - Toggle via ☰ ou touche T
  - Meme contenu que l'arbre actuel (HTMX, drag-and-drop, CRUD dossiers)
  - Fermeture au clic sur un document ou sur le backdrop
- [ ] Barre d'outils en haut : `[☰] Titre du document [Dashboard ▾] [Analyser] [Vue liste E] [Focus L] [⚙]`
- [ ] Le dashboard de consensus (Etape 1.4) s'affiche en dropdown depuis le bouton "Dashboard" dans la barre d'outils, ou en bandeau fixe en haut de la zone de lecture (au choix lors de l'implementation)

**Fichiers concernes** :
- Refactoring majeur de `front/templates/front/base.html` (suppression du layout flex 3 colonnes)
- Refactoring de `front/templates/front/bibliotheque.html` (arbre en overlay)
- Nouveau template `front/templates/front/includes/carte_inline.html` (carte d'extraction depliable dans le texte)
- Adaptation de `front/templates/front/includes/extraction_results.html` → vue liste pour le drawer
- `front/static/front/js/marginalia.js` (gestion des pastilles, depliage inline, drawer)
- `front/static/front/js/arbre_overlay.js` (toggle arbre)
- CSS : layout mono-colonne centre, styles des pastilles de marge, animations inline, drawer overlay

**Coherence avec le reste du PLAN** :
- Les Etapes 1.4 a 1.14 sont mises a jour pour refleter ce layout (voir notes dans chaque etape)
- L'Etape 1.8 "responsive 13-14"" est simplifiee : le layout est nativement responsive, plus besoin de breakpoints complexes
- L'Etape 1.11 "mode focus" est simplifiee : il suffit de masquer les pastilles de marge et centrer le texte
- L'Etape 1.14 "mobile" est coherente : meme principe de marginalia, bottom sheet au lieu d'inline
- La Phase 5 "wizard de synthese" s'ouvre en pleine page ou en drawer large, pas dans un panneau permanent

### Etape 1.4 — Statut de debat sur les extractions

**Pourquoi** : actuellement, rien n'indique si un debat sur une extraction est ouvert, resolu, ou en attente de consensus. L'utilisateur ne sait pas ou en est le debat global sur un texte. Le statut visuel est un prerequis pour le "dashboard de consensus" (voir section UX) et pour le garde-fou "pas de synthese sans consensus".

**Actions** :
- [ ] Ajouter un champ `statut_debat` sur `ExtractedEntity` : `ouvert`, `en_cours`, `consensus`, `rejete`
- [ ] L'extraction commence en `ouvert`, passe en `en_cours` au premier commentaire
- [ ] Bouton "Marquer comme consensus" et "Rejeter" sur chaque extraction
- [ ] Affichage visuel du statut dans les cartes d'extraction et dans l'annotation HTML
- [ ] Appliquer les couleurs accessibles de la charte (voir section 1.11 "Reference : charte typographique", ajust. 2 et 4) :
  - CONSENSUEL → texte `#15803d` sur fond `#f0fdf4` avec icone ⚫
  - DISCUTABLE → texte `#B61601` sur fond `#fef2f2` avec icone ▶
  - DISCUTE → texte `#b45309` sur fond `#fffbeb` avec icone ▷ — **distinct du DISCUTABLE**
  - CONTROVERSE → texte `#C2410C` sur fond `#FFF4ED` avec icone ! — accent `#FF4000` pour bordure
- [ ] Definir les couleurs en variables CSS dans `:root` (texte + fond + accent pour chaque statut) :
  ```css
  /* Texte des badges (WCAG AA >= 4.5:1 sur le fond correspondant) */
  --statut-consensuel-text: #15803d;
  --statut-discutable-text: #B61601;
  --statut-discute-text: #b45309;
  --statut-controverse-text: #C2410C;

  /* Fonds des badges (pastels legers) */
  --statut-consensuel-bg: #f0fdf4;
  --statut-discutable-bg: #fef2f2;
  --statut-discute-bg: #fffbeb;
  --statut-controverse-bg: #FFF4ED;

  /* Accents (bordures, icones — couleurs vives, pas pour du texte) */
  --statut-consensuel-accent: #429900;
  --statut-discutable-accent: #B61601;
  --statut-discute-accent: #D97706;
  --statut-controverse-accent: #FF4000;
  ```
- [ ] Utiliser un template tag ou un dict dans `_card_body.html` pour mapper `attr_2` → couleur + icone

> Note : le prerequis "consensus avant synthese" sera actif seulement apres la Phase 2 (users).
> En mode mono-utilisateur, le statut est indicatif.
>
> Si en pratique la nuance DISCUTE/DISCUTABLE s'avere trop fine pour les utilisateurs,
> fusionner en un seul statut "EN DEBAT" (`#B61601`, icone ▶). A valider en test utilisateur.

- [ ] **Dashboard de consensus** — accessible via le bouton "Dashboard" dans la barre d'outils (dropdown) ou en bandeau compact en haut de la zone de lecture :

  > **Pourquoi** : le PLAN dit *"ce cycle peut etre repete jusqu'a atteindre un consensus"* (ligne 18),
  > mais l'interface ne donne aucun moyen de savoir ou en est le consensus. L'utilisateur doit
  > compter mentalement les statuts de chaque carte pour repondre a "est-ce qu'on est pret a
  > synthetiser ?". C'est le chainage manquant entre les statuts individuels (Etape 1.4) et
  > le bouton de synthese (Phase 5). Sans ce dashboard, le garde-fou "consensus avant synthese"
  > est invisible et donc inapplicable.

  Mockup cible :
  ```
  ┌─────────────────────────────────────────┐
  │  Debat sur "L'IA dans l'education"      │
  │                                          │
  │  ⚫ 8 consensuels  ▶ 3 discutables      │
  │  ▷ 2 discutes      ! 1 controverse      │
  │                                          │
  │  ████████████░░░░  57% consensus         │
  │                                          │
  │  Bloquants :                             │
  │  ! "L'avenement de l'IA..."   3 comments │
  │  ▶ "L'integration d'outils..." 0 comment │
  │                                          │
  │  [Lancer la synthese]  (grise si < 80%) │
  └─────────────────────────────────────────┘
  ```

  - Compteurs par statut avec icones et couleurs de la charte (ajust. 2 + 4)
  - Barre de progression : % d'extractions en statut CONSENSUEL (les masquees ne comptent pas)
  - Liste des extractions "bloquantes" : CONTROVERSE d'abord, puis DISCUTE avec le plus de commentaires
  - Bouton "Lancer la synthese" grise tant que le seuil n'est pas atteint
  - Seuil configurable (defaut 80%, ajustable dans la config IA). En mode mono-user (Phase 1), le seuil est indicatif — le bouton est toujours cliquable avec un avertissement
  - Le dashboard se met a jour automatiquement apres chaque changement de statut (reponse HTMX OOB swap)

- [ ] **Pastilles de marge** (remplace l'ancienne minimap) — dans la marge droite du texte (~3-4rem) :

  > **Pourquoi** : dans le layout lecteur + marginalia (Etape 1.3 bis), la marge droite joue le role
  > de la minimap ET du point d'entree vers les cartes inline. Les pastilles colorees donnent la vision
  > spatiale "ou se situent les debats dans le texte" tout en servant de bouton pour deplier les cartes.
  > C'est un seul element visuel pour deux fonctions (indicateur + interaction).

  - Pastilles rondes (8-10px) dans la marge droite, alignees verticalement avec le passage extrait
  - Couleur = statut de debat (memes variables CSS que les badges)
  - Si plusieurs extractions couvrent le meme passage → pastilles empilees verticalement
  - Clic sur une pastille → deplie la carte d'extraction inline sous le paragraphe
  - La marge se redessine apres chaque annotation HTML (meme donnees que `front/utils.py`)
  - Optionnel Phase 2+ : opacite proportionnelle au nombre de commentaires (plus de debat = plus opaque)

**Fichiers concernes** : `hypostasis_extractor/models.py`, `front/views.py` (action dashboard sur ExtractionViewSet), templates (`_card_body.html`, `carte_inline.html`, `extraction_results.html`, `lecture_principale.html`), `front/utils.py`, CSS

**Tests E2E** :
- [ ] Dashboard : verifier les compteurs par statut (creer des extractions avec differents statuts)
- [ ] Dashboard : verifier que la barre de progression reflette le % de consensus
- [ ] Dashboard : verifier que le bouton "Lancer la synthese" est grise sous le seuil
- [ ] Pastilles de marge : verifier que les pastilles sont colorees par statut
- [ ] Pastilles de marge : clic sur une pastille → deplie la carte inline sous le passage

### Etape 1.5 — Assets statiques locaux (Tailwind, HTMX, fonts) et extraction CSS/JS

**Probleme** : Tailwind CSS est charge via CDN (`cdn.tailwindcss.com`). En mode hors-ligne ou si le CDN tombe, l'app est inutilisable. C'est aussi un prerequis pour la Phase 9 (mode local). De plus, tout le CSS (219 lignes) et tout le JS (~1260 lignes) sont inline dans `base.html`, ce qui rend le design difficile a iterer.

**Actions** :
- [ ] Inventorier toutes les ressources chargees depuis un CDN (Tailwind, HTMX, SweetAlert2, fonts, icones)
- [ ] Telecharger ou compiler Tailwind en local (option : Tailwind CLI standalone, fichier CSS pre-compile)
- [ ] Verifier que HTMX est deja servi en local (sinon le telecharger)
- [ ] Configurer `django.contrib.staticfiles` et `collectstatic` pour servir tout en local
- [ ] Extraire le CSS inline de `base.html` dans `front/static/front/css/hypostasia.css`
- [ ] Extraire le JS inline de `base.html` dans `front/static/front/js/hypostasia.js`
- [ ] Charger les polices B612, B612 Mono et Srisakdi (Google Fonts, puis fichiers locaux pour le mode offline)
- [ ] Tester l'app avec acces internet coupe

**Fichiers concernes** : templates (`bibliotheque.html`, `base.html`), `front/static/`, `hypostasia/settings.py`

### Etape 1.6 — Migration SQLite vers PostgreSQL

**Probleme** : SQLite ne supporte pas les ecritures concurrentes (verrou exclusif sur toute la base), ce qui bloque la Phase 5 (collab) et la Phase 8 (live). Le broker Celery SQLAlchemy+SQLite est marque "experimental / not recommended" par la doc Celery. PostgreSQL est necessaire pour pgvector (Phase 6).

**Actions** :
- [ ] Installer PostgreSQL localement (ou via Docker)
- [ ] Configurer `DATABASES` dans `settings.py` pour PostgreSQL (avec fallback SQLite via variable d'env pour le mode local Phase 9)
- [ ] Migrer le broker Celery de `sqla+sqlite` vers `redis://` ou `amqp://` (Redis recommande)
- [ ] Installer Redis localement (ou via Docker) pour le broker Celery
- [ ] Mettre a jour `docker-compose.yml` / `supervisord.conf` avec les services PostgreSQL et Redis
- [ ] Tester : `uv run python manage.py migrate` sur la nouvelle base
- [ ] Documenter la procedure de migration des donnees SQLite → PostgreSQL si des donnees de dev existent

> Note : le mode local (Phase 9) pourra conserver SQLite comme option pour le boitier offline.
> Le flag `MODE_LOCAL` dans settings.py selectionnera le bon backend DB.

**Fichiers concernes** : `hypostasia/settings.py`, `hypostasia/celery.py`, `docker-compose.yml`, `supervisord.conf`

### Etape 1.7 — Setup Playwright et premiers tests E2E

**Actions** :
- [ ] Configurer Playwright avec Django test server (`LiveServerTestCase` ou fixture)
- [ ] Fixtures de donnees : pages de test, dossiers, analyseurs, extractions
- [ ] CI : ajouter les tests Playwright au pipeline
- [ ] Tests E2E Phase 1 :
  - Arbre et navigation : creer dossier, classer page, naviguer
  - Lecture : ouvrir une page, verifier le contenu, acces direct (F5)
  - Import document : upload PDF, verifier la page creee
  - Import audio : upload MP3, polling, verifier transcription (mock)
  - Edition transcription : renommer locuteur, editer bloc, supprimer bloc
  - Extraction manuelle : selectionner texte, creer extraction
  - Config IA : toggle on/off, selectionner modele
  - Charte visuelle : verifier que les polices B612/B612 Mono/Lora/Srisakdi sont chargees
  - Cartes d'extraction : verifier couleur par famille d'hypostase, distinction machine (B612 Mono) vs citation (Lora italique)
  - Statuts de debat : verifier 4 couleurs texte distinctes (`#15803d`, `#B61601`, `#b45309`, `#C2410C`) + fonds pastels + ratio WCAG >= 4.5:1
  - Interventions lecteur : verifier Srisakdi 20pt sur le nom, 16pt sur le corps du commentaire
  - Scroll bidirectionnel : clic icone marge → scroll vers carte, clic carte → scroll vers texte
  - Etats interactifs : hover sur carte (fond change), empty state panneau vide (texte + CTA), loading skeleton pendant analyse mock
  - Variables CSS : verifier que `:root` contient les variables de surface, texte, bordure, hypostases, statuts, provenances (prerequis dark mode)
  - Layout : verifier que la zone de lecture est en pleine largeur, que le drawer s'ouvre en overlay au clic sur E, que l'arbre s'ouvre en overlay au clic sur ☰
  - Cartes compactes : verifier le mode accordeon (une seule carte ouverte), les indicateurs de densite (badge commentaires, epaisseur bordure)
  - Curation : masquer une extraction sans commentaire (verifier disparition), verifier que le bouton "Masquer" est absent sur une extraction commentee, restaurer une extraction masquee
  - Mode focus : toggle avec `L`, verifier centrage du texte, popup inline sur pastille, Escape pour fermer
  - Alignement basique : selectionner 3 pages, verifier le tableau croise hypostase × documents, verifier les gaps

**Fichiers concernes** : nouveau dossier `tests/e2e/`, `pyproject.toml`

### Etape 1.8 — Charte visuelle et typographique (retours Yves + ajustements UX)

**Pourquoi** : le front utilise Inter + Lora (polices generiques). Les cartes d'extraction n'ont pas de distinction visuelle entre texte machine (IA) et texte humain (citation). Les hypostases sont affichees en pastilles indigo uniformes sans couleur par famille. Le design actuel ne suit pas la charte du designer (voir section 1.11).

La distinction typographique humain/machine/lecteur est le signal UX central du produit : un utilisateur doit pouvoir scanner une carte et savoir *instantanement* ce qui vient d'un LLM, ce qui vient d'un texte source, et ce qui vient d'un lecteur humain. Trois polices, trois provenances, zero ambiguite.

**Actions typographie** :
- [ ] Charger B612, B612 Mono et Srisakdi dans `base.html` (Google Fonts puis fichiers locaux)
- [ ] Creer 5 classes CSS utilitaires :
  ```css
  /* Labels, tags d'hypostase — B612 aviation = lisible en petit */
  .typo-hypostase { font-family: 'B612', sans-serif; font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }

  /* Texte machine (resume IA, synthese) — mono = signal "la machine a dit ca" */
  .typo-machine   { font-family: 'B612 Mono', monospace; font-size: 14px; color: #475569; }

  /* Citations humaines (texte source entre [...]) — serif chaleureuse, PAS B612 */
  /* Justification : B612 italique est froide (font d'aviation). Lora italique     */
  /* a le caractere et la chaleur d'une parole humaine qu'on preserve.              */
  .typo-citation  { font-family: 'Lora', Georgia, serif; font-style: italic; font-size: 16px; color: #1e293b; }

  /* Interventions lecteur — nom/signature (accroche visuelle) */
  .typo-lecteur-nom  { font-family: 'Srisakdi', cursive; font-size: 20px; color: #0056D6; }

  /* Interventions lecteur — corps du commentaire (lisible en fil long) */
  /* Justification : 20pt en cursive dans un panneau de 32rem = ~30 chars/ligne.    */
  /* Avec 5-10 commentaires, ca ecrase tout. 16pt garde l'identite Srisakdi         */
  /* tout en restant lisible dans un fil de discussion dense.                         */
  .typo-lecteur-corps { font-family: 'Srisakdi', cursive; font-size: 16px; color: #0056D6; }
  ```
- [ ] Conserver Inter pour l'UI generale et Lora pour la zone de lecture (la zone de lecture n'est pas touchee par cette etape)

**Actions cartes d'extraction** (`_card_body.html`) :
- [ ] `attr_0` (hypostase) : appliquer `.typo-hypostase` + couleur par famille (voir tableau ci-dessous)
- [ ] `attr_1` (resume IA) : appliquer `.typo-machine` (B612 Mono 14px, texte neutre) — le mono signale visuellement "c'est la machine qui parle"
- [ ] `text` (citation source) : appliquer `.typo-citation` (**Lora** italique 16px) + prefixer `[` et suffixer `]` — la serif chaleureuse signale "c'est un humain qui a ecrit ca"
- [ ] `attr_2` (statut de debat) : appliquer couleurs charte ajustee + icones Unicode (voir Etape 1.4), avec distinction DISCUTE `#D97706` / DISCUTABLE `#B61601`
- [ ] `attr_3` (hashtags) : ajouter `data-hashtag` pour rendu cliquable futur

**Couleurs par famille d'hypostase** :

| Famille | Hypostases | Couleur Tailwind | Hex fond | Hex texte |
|---------|-----------|-----------------|----------|-----------|
| Epistemique | classification, axiome, theorie, definition, formalisme | indigo | `#e0e7ff` | `#4338ca` |
| Empirique | phenomene, evenement, donnee, variable, indice | emerald | `#d1fae5` | `#047857` |
| Speculatif | hypothese, conjecture, approximation | amber | `#fef3c7` | `#b45309` |
| Structurel | structure, invariant, dimension, domaine | slate | `#e2e8f0` | `#475569` |
| Normatif | loi, principe, valeur, croyance | violet | `#ede9fe` | `#6d28d9` |
| Problematique | aporie, paradoxe, probleme | red | `#fee2e2` | `#b91c1c` |
| Mode/Variation | mode, variation, variance, paradigme | cyan | `#cffafe` | `#0e7490` |
| Objet/Methode | objet, methode | gray | `#f1f5f9` | `#64748b` |

- [ ] Implementer le mapping hypostase → couleur via un template tag dans `hypostasis_extractor/templatetags/extractor_tags.py`
- [ ] Chaque pastille d'hypostase dans le header de carte utilise le fond et texte de sa famille

**Actions interventions lecteur** :
- [ ] Nom de l'auteur du commentaire : `.typo-lecteur-nom` (Srisakdi 20pt bleu) — c'est l'accroche visuelle qui dit "un humain reagit"
- [ ] Corps du commentaire : `.typo-lecteur-corps` (Srisakdi 16pt bleu) — taille reduite pour rester lisible dans les fils de 5-10 commentaires
- [ ] Appliquer dans `vue_commentaires.html` et `vue_questionnaire.html`
- [ ] Distinction visuelle a 3 niveaux dans les cartes et fils :
  - **Mono neutre** (B612 Mono) = la machine a synthetise
  - **Serif chaleureuse** (Lora italique) = un humain a ecrit le texte source
  - **Cursive bleue** (Srisakdi) = un lecteur reagit maintenant

**Actions interaction texte ↔ extractions** :
- [ ] Clic sur une pastille de marge → deplie la carte inline sous le passage (Etape 1.3 bis)
- [ ] Clic sur une carte dans le drawer vue liste → scroll le texte vers le passage + deplie la carte inline
- [ ] Les deux interactions sont bidirectionnelles : la carte inline montre le passage, le drawer pointe vers le texte

**Actions etats interactifs** (ajust. 5 — etats hover, active, loading, empty, error) :

> **Pourquoi** : les mockups de Yves montrent des etats statiques. Mais une interface reelle a 5 etats
> par composant : repos, survol, actif/selectionne, chargement, vide, erreur. Si ces etats ne sont pas
> definis dans le design system, chaque developpeur invente le sien au cas par cas. Resultat : un hover
> bleu ici, un hover gris la, un loading spinner a droite et un texte "Chargement..." a gauche.
> L'incoherence visuelle mine la confiance utilisateur.
>
> **Regle** : definir une fois, reutiliser partout. Chaque etat a un traitement unique dans toute l'app.

- [ ] **Hover** : fond `slate-50` + `cursor-pointer` sur tous les elements interactifs (cartes, items arbre, boutons). Transition `150ms ease`. Pas de changement de taille (evite les decalages de layout)
- [ ] **Active / selectionne** : bordure gauche 3px couleur accent + fond teinte. Ex : carte d'extraction selectionnee = bordure gauche couleur famille d'hypostase + fond pale. Item arbre selectionne = fond `indigo-50` + bordure gauche `indigo-500`
- [ ] **Loading** :
  - *Boutons* : icone spinner inline + texte "En cours..." + `pointer-events: none` + opacite reduite
  - *Cartes* : squelette anime (skeleton screen) avec shimmer gris pulse — pas un spinner centre
  - *Zone de lecture* : barre de progression fine en haut (style YouTube) pour les analyses longues
  - Classe CSS `.is-loading` applicable a tout conteneur → affiche le skeleton, cache le contenu
- [ ] **Empty states** :
  - *Arbre sans pages* : icone document + texte "Importez votre premier document" + bouton CTA "Importer"
  - *Drawer vue liste vide* : icone loupe + texte "Aucune extraction pour cette page" + bouton "Lancer une analyse"
  - *Fil de commentaires vide* : texte "Pas encore de commentaire" + formulaire visible directement
  - Chaque empty state a une illustration ou icone + un texte explicatif + une action primaire
- [ ] **Error states** :
  - Erreur LLM : message inline rouge avec bouton "Reessayer" (pas d'alerte bloquante)
  - Erreur reseau : bandeau jaune en haut de la zone concernee avec message + auto-retry apres 5s
  - Erreur de validation : champs en rouge + message sous le champ (jamais de toast pour les erreurs de formulaire)
- [ ] Definir les variables CSS pour les etats :
  ```css
  --hover-bg: #f8fafc;       /* slate-50 */
  --active-bg: #f1f5f9;      /* slate-100 */
  --loading-shimmer: #e2e8f0; /* slate-200 */
  --error-text: #dc2626;      /* red-600 */
  --error-bg: #fef2f2;        /* red-50 */
  ```

**Actions compatibilite dark mode** (ajust. 7 — preparer sans implementer) :

> **Pourquoi** : Hypostasia est un outil de lecture intensive. Les sessions peuvent durer des heures
> (relecture de contrats, analyse de debats). Le dark mode n'est pas esthetique — c'est de la sante
> visuelle. Ne pas le prevoir maintenant n'empeche pas de le faire plus tard, MAIS si les couleurs
> sont codees en dur dans le CSS au lieu d'utiliser des variables, la migration dark mode sera un
> cauchemar (retrouver et remplacer 200+ valeurs hex dispersees dans templates et CSS).
>
> **Regle** : utiliser des CSS custom properties pour TOUTES les couleurs semantiques des maintenant.
> L'implementation dark mode viendra plus tard, mais la structure doit etre prete.

- [ ] Structurer TOUTES les couleurs en variables CSS dans `:root` (pas seulement les statuts, deja fait) :
  ```css
  /* Surfaces */
  --surface-primary: #ffffff;
  --surface-secondary: #f8fafc;
  --surface-tertiary: #f1f5f9;

  /* Texte */
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-tertiary: #94a3b8;

  /* Bordures */
  --border-default: #e2e8f0;
  --border-strong: #cbd5e1;
  ```
- [ ] Les 8 familles d'hypostases utilisent des variables (ex: `--hypostase-epistemique-bg`, `--hypostase-epistemique-text`)
- [ ] Les 4 statuts de debat utilisent deja des variables (fait dans Etape 1.4)
- [ ] Les 3 provenances typographiques utilisent des variables couleur (ex: `--typo-machine-color`, `--typo-citation-color`, `--typo-lecteur-color`)
- [ ] **Ne PAS implementer le theme dark maintenant** — juste s'assurer que toutes les couleurs passent par des variables
- [ ] Quand le dark mode sera implemente (post-Phase 1), il suffira d'ajouter un bloc `@media (prefers-color-scheme: dark) { :root { ... } }` — zero refactoring du CSS existant

**Actions responsive** (ajust. 8 — simplifie grace au layout lecteur + marginalia) :

> **Note** : le passage au layout lecteur + marginalia (Etape 1.3 bis) elimine le probleme de competition
> spatiale entre colonnes. Le texte occupe toujours la pleine largeur, les extractions sont inline ou
> en drawer overlay. Il n'y a plus de breakpoint complexe a gerer — le layout est nativement responsive.

- [ ] **Zone de lecture** : `max-w-4xl` centre avec `mx-auto` et padding horizontal confortable (`px-6` a `px-12` selon la largeur). Fonctionne de 768px a 2560px sans media query
- [ ] **Marge des pastilles** : a droite du texte, 3-4rem de large. Sur ecrans < 1024px, la marge se reduit a 2rem (pastilles plus petites)
- [ ] **Drawer vue liste** : meme overlay (32rem, position fixed droite) quelle que soit la taille d'ecran. Pas de breakpoint — c'est toujours un overlay, jamais une colonne permanente
- [ ] **Arbre overlay** : meme overlay (20rem, position fixed gauche) quelle que soit la taille d'ecran. Pas de breakpoint — c'est toujours un overlay
- [ ] **Seul breakpoint** : `max-width: 768px` pour le mode mobile (Etape 1.14) — bottom sheet au lieu d'inline, barre d'outils adaptee

**Actions hierarchie des cartes d'extraction** (ajust. 9 — cartes compactes + densite + curation post-extraction) :

> **Pourquoi** : le mockup montre des cartes de taille uniforme. Mais en realite, une extraction
> CONSENSUELLE avec 12 commentaires et 3 sources externes est *beaucoup* plus importante qu'une
> extraction DISCUTABLE sans commentaire. Si toutes les cartes ont le meme poids visuel, l'utilisateur
> ne peut pas scanner l'interface pour trouver "ou en est le debat" sans lire chaque carte.
>
> C'est un probleme de **surcharge informationnelle** : 20 cartes de meme taille (dans le drawer vue
> liste ou depliees inline) = un mur de cartes. L'oeil n'a aucun point d'entree prioritaire.
>
> De plus, les LLM sur-extraient systematiquement. Suivant le prompt, pratiquement chaque phrase
> est extraite — y compris des phrases de remplissage comme *"je sais pas trop quoi en penser,
> je trouve ca dangereux"* alors que seule l'argumentation qui suit meriterait une extraction.
> Sans mecanisme de curation humaine, ces extractions parasites polluent l'interface (pastilles
> de marge, drawer vue liste, cartes inline) et noient les extractions importantes.

- [ ] **Mode compact dans le drawer vue liste** : chaque carte affiche une seule ligne — pastille hypostase coloree + debut du resume IA (truncate a ~60 chars) + indicateurs (icones commentaires, sources, statut). La carte est cliquable pour expansion
- [ ] **Expansion au clic** : clic sur une carte compacte (dans le drawer) → deploie le contenu complet (resume IA en B612 Mono, citation source en Lora italique, statut, hashtags, fil de commentaires). Un seul clic pour ouvrir, un seul pour fermer. Une seule carte ouverte a la fois (accordeon). Note : les cartes inline (dans le texte) s'affichent toujours en version complete — elles sont deja contextualisees
- [ ] **Indicateurs de densite** sur la carte compacte :
  - Nombre de commentaires (badge numerique, ex: `💬 12`)
  - Nombre de sources externes (badge, ex: `📎 3`)
  - Bordure gauche dont l'epaisseur encode la densite : 2px (0 commentaire), 3px (1-3), 4px (4+)
  - Couleur de bordure = couleur du statut de debat (pas de la famille d'hypostase, pour ne pas melanger les signaux)
- [ ] **Curation post-extraction (masquer les extractions non pertinentes)** :

  > **Principe** : c'est un outil de **tri apres extraction**, pas un mecanisme de debat.
  > Le LLM produit 30 extractions, l'humain revoit et masque celles qui sont du bruit.
  > Une fois qu'un commentaire existe sur une extraction, elle est "en jeu" dans le cycle
  > deliberatif — on ne peut plus la masquer. On juge de la pertinence d'une extraction,
  > pas de la pertinence d'un debat.

  - Bouton **"Masquer"** (icone oeil barre) sur chaque carte d'extraction **qui n'a aucun commentaire**
  - Champ `masquee = BooleanField(default=False)` sur `ExtractedEntity`
  - **Garde** : si `extraction.commentaires.count() > 0`, le bouton "Masquer" est absent. Une extraction commentee ne peut pas etre masquee — elle fait partie du debat
  - Les extractions masquees disparaissent des pastilles de marge, des cartes inline et du drawer vue liste. L'annotation HTML (le `<span>`) n'est pas generee
  - **Toggle en bas du drawer vue liste** : "Voir les X extractions masquees" → affiche les cartes masquees en opacite reduite, avec un bouton "Restaurer" pour annuler le masquage
  - L'annotation HTML (`front/utils.py`) doit filtrer les entites masquees : `entites.filter(masquee=False)`
  - Pas de modele separe, pas de ratio, pas de vote — juste un booleen sur l'entite. Si le multi-user (Phase 2) necessite un systeme de vote pour le masquage, on l'ajoutera a ce moment-la
- [ ] **Tri des cartes** (menu deroulant en haut du drawer vue liste) :
  - Par position dans le texte (defaut — ordre d'apparition dans le document)
  - Par activite recente (derniers commentaires en haut)
  - Par statut de debat (CONTROVERSE en haut, CONSENSUEL en bas)

**Fichiers concernes** : CSS (`hypostasia.css` ou `base.html`), `_card_body.html`, `carte_inline.html`, `extraction_results.html` (drawer vue liste), `vue_commentaires.html`, `vue_questionnaire.html`, `hypostasis_extractor/templatetags/extractor_tags.py`, `hypostasis_extractor/models.py` (champ `masquee` sur ExtractedEntity), `front/views.py` (ExtractionViewSet — action masquer/restaurer), `front/utils.py` (filtrage des entites masquees)

### Etape 1.9 — Rythme visuel de la transcription (anti-mur-de-texte)

**Pourquoi** : le mockup de Yves (`DEBAT transcription - ex.pdf`) montre une transcription bien aeree avec quelques blocs. Mais une reunion d'une heure genere 50 a 100 blocs de texte. Sans rythme visuel, c'est un mur uniforme ou l'oeil n'a aucun point d'accroche. L'utilisateur ne sait pas ou il en est, ne peut pas scanner rapidement, et perd le contexte temporel.

C'est un probleme specifique aux transcriptions longues : contrairement a un article (qui a des titres, sous-titres, paragraphes), une transcription est une suite monotone de `LOCUTEUR: texte`. La seule variation est le nom du locuteur — mais si 3 personnes parlent alternativement pendant une heure, les blocs se ressemblent tous.

**Solution** : introduire 4 types de reperes visuels qui cassent la monotonie sans ajouter de contenu.

**Actions** :
- [ ] **Alternance de fond par locuteur** : chaque locuteur a un fond tres pale distinct (comme les bulles de chat). Ex: locuteur A → `#f8fafc`, locuteur B → `#fdf4ff`, locuteur C → `#f0fdf4`. Le changement de locuteur est visible d'un coup d'oeil, meme sans lire les noms
- [ ] **Marqueurs temporels periodiques** : inserer un separateur leger toutes les 5 minutes dans le flux de blocs. Format : fine ligne horizontale + timestamp (`── 05:00 ──`). Ca cree des "chapitres" implicites dans la transcription et permet de repondre a "qu'est-ce qui a ete dit vers la 20e minute ?"
- [ ] **Groupement des tours de parole** : si un locuteur a 3 blocs consecutifs, les grouper visuellement sous un seul header de locuteur (nom + timestamp du premier bloc). Les blocs suivants du meme locuteur n'affichent pas le nom — seulement le texte avec un indent. Ca evite la repetition `SPEAKER_00: ... SPEAKER_00: ... SPEAKER_00: ...`
- [ ] **Mini-barre de progression temporelle** : barre fine en haut de la zone de lecture qui indique la position dans la transcription (debut → fin). Au scroll, la barre suit. Clic sur la barre → scroll vers le timestamp correspondant

- [ ] **Timeline audio horizontale** (uniquement pour les pages `source_type=audio`) :

  > **Pourquoi** : les reperes visuels ci-dessus aident a *lire* la transcription, mais pas a *naviguer*
  > dedans. Pour un debat d'1h avec 8 locuteurs (30+ pages), l'utilisateur a besoin de repondre a
  > "qu'est-ce que Michel a dit vers la 40e minute ?" sans scroller pendant 2 minutes. La timeline
  > est un outil de navigation spatiale — elle transforme une liste lineaire de blocs en une carte
  > temporelle survolable.
  >
  > Les donnees necessaires existent deja : `TextBlock` a `speaker`, `start_time`, `end_time`.
  > Les couleurs par locuteur existent deja dans le HTML diarise. La Phase 8 (live audio)
  > reutilisera ce meme composant.

  Mockup cible :
  ```
  ┌──────────────────────────────────────────────────┐
  │ ▮▮▮▯▯▯▯▮▮▮▮▮▯▯▮▮▮▯▯▯▮▮▮▮▯▯▮▮▮▮▮▮▯▯▯▮▮▮▮▮▮▮▮▮ │
  │ Jean  Yves  Michel    Vero  Michel    Jonas  ... │
  │ 0:00            30:00            60:00    77:00  │
  └──────────────────────────────────────────────────┘
  ```

  - Barre horizontale en haut de la zone de lecture (sous le titre, au-dessus de l'article)
  - Chaque segment est colore par locuteur (meme couleur que les fonds de blocs)
  - La largeur de chaque segment est proportionnelle a la duree
  - **Survol** → tooltip avec le nom du locuteur + timestamp + preview du texte (30 premiers chars)
  - **Clic** → scroll vers le bloc correspondant dans la transcription
  - **Marqueurs d'extraction** : les extractions creees depuis la transcription apparaissent comme des points sur la timeline, colores par statut de debat. On voit quels moments ont genere le plus d'extractions
  - La timeline est generee cote serveur (HTML/CSS pur) a partir des donnees `TextBlock` — pas de librairie JS externe

- [ ] **Filtrage par locuteur** :

  > **Pourquoi** : dans un debat a 6 personnes, l'utilisateur veut parfois suivre le fil de pensee
  > d'un seul participant. Scroller en sautant 5 blocs sur 6 est epuisant. Le filtre masque
  > temporairement les blocs des autres locuteurs.

  - Menu deroulant (ou boutons-pilules) en haut de la zone de lecture : liste des locuteurs avec leur couleur
  - Clic sur un locuteur → masque les blocs des autres (CSS `display: none` ou filtre HTMX)
  - Bouton "Tous" pour restaurer l'affichage complet
  - Le filtre est local (pas de requete serveur) — pur JS/CSS sur les blocs existants
  - La timeline se met a jour pour montrer uniquement les segments du locuteur filtre

**Fichiers concernes** : `front/views.py` (LectureViewSet — generation du HTML diarise + timeline), CSS dans `base.html` ou `hypostasia.css`, JS pour la barre de progression temporelle, le filtrage par locuteur et l'interaction timeline

**Tests E2E** :
- [ ] Transcription longue (20+ blocs) : verifier l'alternance de fond par locuteur
- [ ] Verifier la presence de marqueurs temporels toutes les 5 minutes
- [ ] Verifier le groupement des tours de parole consecutifs
- [ ] Timeline : verifier que les segments sont colores par locuteur, que le clic scroll vers le bon bloc
- [ ] Timeline : verifier que les marqueurs d'extraction apparaissent sur la timeline
- [ ] Filtrage : selectionner un locuteur, verifier que seuls ses blocs sont visibles, restaurer avec "Tous"

### Etape 1.10 — Onboarding et etats vides intelligents

**Pourquoi** : un nouvel utilisateur arrive sur une page vide. Aucune indication de quoi faire. Le concept d'hypostase (PHENOMENE, CONJECTURE, INVARIANT) est puissant mais inhabituel — sans guidage, l'utilisateur traite les extractions comme des surligneurs et passe a cote du modele epistemique qui fait la valeur du produit.

Le cycle deliberatif (Lecture → Extraction → Commentaire → Debat → Synthese) est le coeur du produit. Si l'utilisateur ne comprend pas ce cycle des sa premiere session, il ne reviendra pas. C'est particulierement vrai pour les cas d'usage cibles (collectivites, ESS, juridique) ou les utilisateurs ne sont pas des technophiles.

**Actions** :
- [ ] **Etats vides guides** : quand la bibliotheque est vide, afficher un parcours en 4 etapes dans la zone de lecture :
  1. "Importez votre premier document" → bouton import (texte, PDF, audio)
  2. "Lancez une extraction IA" → explication en 1 phrase + bouton "Analyser" (barre d'outils)
  3. "Lisez les hypostases" → explication de ce que sont les hypostases et pourquoi c'est different d'un surligneur
  4. "Commentez et debattez" → explication du cycle deliberatif
  - Pas un tutoriel modal bloquant — juste l'etat vide de la zone de lecture qui guide. Il disparait des que l'utilisateur a une page
  - S'integre avec les empty states definis dans l'Etape 1.8 (ajust. 5) : l'arbre vide, le panneau vide, le fil vide ont chacun leur message contextuel. L'onboarding est l'empty state de la zone de lecture elle-meme
- [ ] **Tooltips sur les hypostases** : au survol d'une pastille d'hypostase dans les cartes d'extraction, un mini-tooltip affiche la definition en 1 phrase. Ex: *"Conjecture — Affirmation plausible non demontree"*
  - Les 29 definitions existent deja dans `HypostasisChoices` (`core/models.py:214-248`) → les exposer via un template tag ou un dict dans le template
  - Attribut HTML `title` ou tooltip CSS/JS leger (pas de librairie externe)
- [ ] **Document exemple pre-charge** : livrer l'app avec un texte deja extrait et commente. L'utilisateur voit le resultat final (cartes d'extraction colorees, commentaires, statuts de debat) avant de creer le sien
  - Ce document sert aussi de fixture pour les tests E2E Playwright (Etape 1.7) — double usage
  - Commande `uv run python manage.py loaddata exemple_deliberation` pour charger les donnees de demo
  - Le document doit illustrer le cycle complet : texte source → extractions typees → commentaires → au moins une restitution (version 2)

**Fichiers concernes** : `front/templates/front/includes/lecture_principale.html` (etat vide guide), `hypostasis_extractor/templatetags/extractor_tags.py` (tooltips hypostases), `_card_body.html` (attribut title), nouveau fixture `front/fixtures/exemple_deliberation.json`

**Tests E2E** :
- [ ] Premiere visite : verifier que l'etat vide guide s'affiche avec les 4 etapes
- [ ] Apres import d'une page : verifier que l'etat vide disparait
- [ ] Survol d'une pastille d'hypostase : verifier que le tooltip affiche la definition
- [ ] Chargement du document exemple : verifier que les cartes, commentaires et versions sont presents

### Etape 1.11 — Mode lecture focus

**Pourquoi** : meme avec le layout lecteur + marginalia (Etape 1.3 bis), les pastilles de marge et le
surlignage des extractions creent un bruit visuel pour la lecture longue. Le cas d'usage est frequent :
relire un texte de 20 pages avant d'extraire, relire une version de synthese (Phase 5), relire une
transcription post-reunion. Dans tous ces cas, l'utilisateur n'a pas besoin des indications d'extraction
— il a besoin de concentration pure.

Le mode focus est **simplifie** grace au layout lecteur + marginalia : il n'y a plus de sidebars a replier.
Il suffit de masquer les pastilles de marge, retirer le surlignage, et resserrer le texte.

**Actions** :
- [ ] Bouton "Mode lecture" dans la barre d'outils (icone livre ouvert) + raccourci `L`
- [ ] En mode focus :
  - Les pastilles de marge droite sont masquees (`display: none`)
  - Le surlignage des extractions (`.hl-extraction`) est desactive (supprime le fond colore, garde le texte normal)
  - Le texte se resserre en `max-w-2xl` avec marges generreuses (padding horizontal `4rem`) pour un confort de lecture optimal
  - La barre d'outils reste visible mais discrete (opacite reduite, apparait au hover)
  - `Escape` ou second clic sur `L` → quitte le mode focus, restaure le layout normal avec marginalia

  Mockup cible :
  ```
  ┌──────────────────────────────────────────────┐
  │ [☰]  L'IA dans l'education      [Focus ●]   │
  │                                              │
  │       La loi d'Amara suggere que nous        │
  │       surestimons toujours l'impact a        │
  │       court terme d'une technologie et       │
  │       sous-estimons l'impact a long terme.   │
  │                                              │
  │       En consequence, il faut adopter une    │
  │       approche prudente mais ouverte, qui    │
  │       reconnaisse a la fois les risques      │
  │       immediats et le potentiel...           │
  │                                              │
  │       (pas de pastilles, pas de surlignage   │
  │        — lecture pure)                        │
  │                                              │
  └──────────────────────────────────────────────┘
  ```

- [ ] L'etat du mode focus est persiste en `localStorage` (si l'utilisateur prefere lire en focus, il le retrouve a la prochaine visite)

**Fichiers concernes** : `marginalia.js` (toggle mode focus), `hypostasia.css` (styles `.mode-focus`), `lecture_principale.html` (bouton dans la barre d'outils)

**Tests E2E** :
- [ ] Clic sur "Mode lecture" : verifier que les pastilles disparaissent et le texte se centre
- [ ] `L` : verifier le toggle du mode focus
- [ ] Persistence : activer le mode focus, recharger la page, verifier qu'il est toujours actif
- [ ] Escape en mode focus : verifier le retour au mode normal avec pastilles

### Etape 1.12 — Alignement basique par hypostases (version Phase 1)

**Pourquoi des la Phase 1** : l'alignement cross-documents par hypostase est le cas d'usage differenciateur du produit (voir `PLAN/References/exemple alignement.pdf`). Il ne necessite PAS les embeddings de la Phase 6 — c'est un simple regroupement des extractions existantes par type d'hypostase sur N documents. Les donnees necessaires existent des que les extractions sont typees (ce qui est le cas des la Phase 1).

Implementer une version basique maintenant permet de :
- Montrer la valeur du produit aux financeurs des les premiers tests
- Valider le concept d'alignement avec les utilisateurs pilotes (Jean, Ephicentria)
- Poser les bases UX que la Phase 6 enrichira avec la recherche semantique

**Actions** :
- [ ] Bouton "Aligner" accessible depuis la selection multiple dans l'arbre (selectionner 2-6 pages → clic droit ou bouton "Aligner")
- [ ] Vue tableau croise hypostase × documents (meme layout que l'Etape 6.2 mode alignement, mais sans recherche semantique)
- [ ] Construction du tableau par requete simple : `ExtractedEntity.objects.filter(page__in=pages_selectionnees)` groupe par hypostase (attribut `attr_0`)
- [ ] Cellules avec resume tronque, gaps marques, compteurs
- [ ] Export Markdown du tableau d'alignement
- [ ] Pas de detection de conflits semantiques (ca vient avec les embeddings en Phase 6)
- [ ] Pas d'export PDF (ca vient en Phase 5 avec l'export visuel)

**Fichiers concernes** : `front/views.py` (action sur un AlignementViewSet ou action sur ArbreViewSet), nouveau template `front/includes/alignement_tableau.html`, `hypostasis_extractor/templatetags/extractor_tags.py`

**Tests E2E** :
- [ ] Selectionner 3 pages avec des extractions, lancer l'alignement
- [ ] Verifier que le tableau affiche les hypostases en lignes et les documents en colonnes
- [ ] Verifier que les cellules vides affichent "gap"
- [ ] Export Markdown : verifier le contenu du fichier exporte

### Etape 1.13 — Raccourcis clavier et navigation au clavier

**Argumentaire** : Hypostasia est un outil de travail intellectuel — les utilisateurs vont y passer des heures
a lire, extraire, commenter, debattre. Imposer le clic pour chaque action est lent et fatiguant. Les outils
de reference (VS Code, Notion, Roam, Hypothesis) offrent tous une navigation clavier intensive.
Le standard UX pour les outils de productivite est clair : les power users abandonnent un outil qui ne supporte
pas le clavier. Pour le public academique vise, c'est un attendu de base.

Le layout lecteur + marginalia (Etape 1.3 bis) s'y prete naturellement : les raccourcis agissent sur le
contexte actif (texte, carte inline, drawer). Les raccourcis ne declenchent des actions que quand aucun champ
de saisie n'est focus (sinon l'utilisateur taperait des lettres dans son commentaire au lieu de naviguer).

**Raccourcis prevus** :

```
┌───────────┬─────────────────────────────────────────────┐
│ Raccourci │               Action                        │
├───────────┼─────────────────────────────────────────────┤
│ ?         │ Afficher la palette des raccourcis (modale) │
├───────────┼─────────────────────────────────────────────┤
│ L         │ Toggle mode lecture focus (Etape 1.11)      │
├───────────┼─────────────────────────────────────────────┤
│ E         │ Toggle drawer vue liste (show/hide)         │
├───────────┼─────────────────────────────────────────────┤
│ T         │ Toggle arbre de dossiers (show/hide)        │
├───────────┼─────────────────────────────────────────────┤
│ J / K     │ Extraction suivante / precedente            │
│           │ (scroll vers la pastille + deplie inline)   │
├───────────┼─────────────────────────────────────────────┤
│ C         │ Commenter l'extraction selectionnee         │
│           │ (ouvre le champ commentaire)                │
├───────────┼─────────────────────────────────────────────┤
│ S         │ Marquer l'extraction comme consensuelle     │
├───────────┼─────────────────────────────────────────────┤
│ X         │ Masquer l'extraction (curation, Etape 1.8)  │
├───────────┼─────────────────────────────────────────────┤
│ /         │ Ouvrir la recherche (Phase 6, desactive     │
│           │ avant — affiche placeholder "bientot")      │
├───────────┼─────────────────────────────────────────────┤
│ Escape    │ Fermer modale / quitter mode focus /        │
│           │ deselectionner extraction                   │
└───────────┴─────────────────────────────────────────────┘
```

**Mockup — Modale d'aide raccourcis (touche ?)** :

```
┌─────────────────────────────────────────────┐
│         Raccourcis clavier                   │
│                                             │
│  Navigation                                 │
│  ─────────                                  │
│  J / K    Extraction suivante / precedente  │
│  L        Mode lecture focus                │
│  T        Afficher/masquer l'arbre          │
│  E        Drawer vue liste (extractions)    │
│  Escape   Fermer / deselectionner           │
│                                             │
│  Actions                                    │
│  ───────                                    │
│  C        Commenter                         │
│  S        Marquer consensuel                │
│  X        Masquer (curation)                │
│  /        Recherche                         │
│                                             │
│              [Fermer]                       │
└─────────────────────────────────────────────┘
```

**Actions** :
- [ ] Listener `keydown` global sur `document`, desactive quand un `<input>`, `<textarea>` ou `[contenteditable]` est focus
- [ ] Systeme de dispatch simple : `switch (event.key)` dans un seul fichier JS, pas de framework
- [ ] Etat "extraction selectionnee" : index courant dans la liste des cartes, surlignage CSS de la carte active
- [ ] `J`/`K` : scroll vers la pastille suivante/precedente dans la marge + deplie la carte inline
- [ ] `?` : modale simple (HTML statique injecte dans le DOM, toggle display)
- [ ] `Escape` : ferme la modale si ouverte, ferme le drawer si ouvert, quitte le mode focus si actif, replie la carte inline sinon
- [ ] `L` : toggle mode focus (Etape 1.11). `E` : toggle drawer vue liste. `T` : toggle arbre overlay
- [ ] `C` : focus le champ commentaire de l'extraction selectionnee (scroll si necessaire)
- [ ] `S`, `X` : declenchent les actions HTMX correspondantes sur l'extraction selectionnee
- [ ] Prevision pour Phase 6 : `/` affiche un placeholder "Recherche — bientot disponible" en Phase 1

**Fichiers concernes** : nouveau `front/static/front/js/keyboard.js` (inclus dans `bibliotheque.html`), CSS pour l'etat `.extraction-selectionnee`

**Tests E2E** :
- [ ] Appuyer sur `?` → la modale s'affiche, `Escape` la ferme
- [ ] Appuyer sur `J`/`K` → les cartes d'extraction deroulent
- [ ] Appuyer sur `L` → le mode focus s'active
- [ ] Taper dans un champ commentaire → les raccourcis sont desactives (pas de declenchement)

### Etape 1.14 — Interface mobile : lecture augmentee et reaction

**Argumentaire** : le mobile n'est pas un ecran desktop "en plus petit". C'est un **contexte d'usage different**
avec ses propres forces. Hypostasia sur mobile ne doit pas etre une version degradee du desktop — il doit
offrir l'interface adaptee a ce qu'on fait reellement sur un telephone :

| | Desktop (bureau, longue session) | Mobile (deplacement, micro-sessions) |
|---|---|---|
| **Duree** | 30 min a 3h | 2 a 10 min |
| **Intention** | Analyser, debattre, synthetiser, aligner | Capturer, lire augmente, reagir, suivre |
| **Precision** | Souris + clavier → selection fine | Doigt → tap grossier |
| **Posture** | Active (je produis du travail) | Reactive (je lis et je reagis) |

Le mobile fait tres bien les choses que le desktop fait mal : **lecture immersive** (pas de distractions laterales),
**reaction rapide** (commenter en 30 secondes), **capture en mobilite** (envoyer un article depuis le navigateur),
**suivi d'avancement** (dashboard en un coup d'oeil). Ce n'est pas une limitation — c'est un design adapte au contexte.

**Cas d'usage cle — capture + lecture augmentee en mobilite** :
1. Je tombe sur un article (Twitter, newsletter, navigateur mobile)
2. Extension navigateur → j'envoie sur Hypostasia
3. Un tap sur "Analyser" → extraction IA avec l'analyseur par defaut
4. 30 secondes d'attente (indicateur de chargement)
5. Je lis l'article **avec les extractions deja en place** — lecture augmentee sur mon tel

#### Ce que fait le mobile (mode lecteur)

**1. Lire le texte avec marqueurs d'extraction**
Le texte s'affiche en pleine largeur, les `<span class="hl-extraction">` sont visibles comme sur desktop.
Pas de colonnes laterales — le texte occupe tout l'ecran.

**2. Tap sur un marqueur → bottom sheet**
Au tap sur un passage surligne, un bottom sheet monte depuis le bas avec la carte d'extraction complete :
hypostase, resume IA, citation source, statut de debat, commentaires existants.

**3. Commenter une extraction**
Depuis le bottom sheet, un champ texte + bouton "Envoyer" pour reagir a chaud.
Cas d'usage : "Je lis dans le train, je vois un commentaire de mon collegue, je reponds en 30 secondes."

**4. Lancer une extraction IA (analyseur par defaut)**
Un bouton "Analyser" visible en haut de la page de lecture. Un tap → l'extraction tourne avec
l'analyseur par defaut (pas de choix de parametres avances). Le resultat s'integre directement
dans les marqueurs du texte. Pas besoin de panneau lateral pour ca.
Cas d'usage : "J'ai envoye un article depuis mon navigateur mobile, je lance l'analyse pour une lecture augmentee."

**5. Dashboard de consensus simplifie**
En haut de la page : barre de progression + compteurs par statut (N consensuelles, N discutees, N en attente).
Cas d'usage : "Avant une reunion, je check en 5 secondes ou en est le debat sur ce document."

**6. Navigation dans l'arbre**
L'arbre de dossiers s'ouvre en plein ecran (pas en overlay partiel). Tap sur un document → lecture.

**Mockup — Bottom sheet extraction (mobile)** :

```
┌─────────────────────────────┐
│  Article : "L'IA dans       │
│  l'education"               │
│                             │
│  ... le texte de l'article  │
│  avec les ░░marqueurs░░     │
│  surlignés cliquables...    │
│                             │
│  ... suite du texte ...     │
│                             │
│  ... et encore du texte     │
│  avec un ░░autre passage░░  │
│  extrait ici ...            │
│                             │
└─────────────────────────────┘
        ↓ tap sur un marqueur
┌─────────────────────────────┐
│ ━━━━━━━━ (drag handle) ━━━━ │
│                             │
│ CONJECTURE                  │
│                             │
│ L'IA generative va          │
│ transformer les metiers     │
│ creatifs.                   │
│                             │
│ « Je pense que dans 5 ans,  │
│   on ne dessinera plus »    │
│                             │
│ ● DISCUTE  #ia #metiers     │
│                             │
│ ── Commentaires (2) ──────  │
│ Marie : Trop reducteur...   │
│ Jean : Sources ?            │
│                             │
│ ┌─────────────────────────┐ │
│ │ Votre commentaire...    │ │
│ └─────────────────────────┘ │
│              [Envoyer]      │
└─────────────────────────────┘
```

#### Ce que le mobile ne fait PAS — et pourquoi

| Fonctionnalite exclue | Raison |
|---|---|
| **Extraction manuelle** | Selectionner precisement un passage au doigt est frustrant (handles de selection, zoom, copier/coller parasite). Le ratio effort/valeur est mauvais. |
| **Choix d'analyseur avance** | Sur mobile on utilise l'analyseur par defaut. Le choix multi-analyseur avec parametres est un workflow desktop. |
| **Wizard de synthese** | 5 etapes avec formulaires, edition longue, verification des SourceLinks. Travail de bureau. |
| **Alignement cross-documents** | Le tableau hypostase x documents est illisible sur 375px. |
| **Mode focus** | Sur mobile on EST deja en mode focus — une seule chose a la fois. |
| **Raccourcis clavier** | Pas de clavier physique. |
| **Curation (masquer/restaurer)** | Action de gestion fine post-extraction, workflow desktop. |

#### Implementation technique

**Actions Phase 1** :
- [ ] **Breakpoint mobile** : `max-width: 768px`. Pas de colonnes laterales, pas d'overlay — layout mono-colonne pleine largeur
- [ ] **Arbre mobile** : plein ecran, navigation tap, bouton retour. Pas de vue arbre + lecture simultanee
- [ ] **Bottom sheet** : composant JS simple (div position fixed, transition CSS translateY, drag handle pour fermer). Pas de librairie tierce
- [ ] **Contenu du bottom sheet** : reutilise les memes donnees que la carte desktop (meme endpoint HTMX, template different)
- [ ] **Bouton "Analyser"** : visible en haut de la page de lecture mobile, lance `LectureViewSet.analyser()` avec l'analyseur par defaut
- [ ] **Indicateur de chargement** : skeleton ou spinner pendant l'extraction (meme pattern que desktop)
- [ ] **Dashboard mobile** : version compacte du dashboard de consensus (barre + compteurs) en haut de page
- [ ] **Detection du contexte** : la vue Django renvoie un template mobile ou desktop selon le user-agent (ou la largeur via CSS `@media`, ou les deux)

**Actions Phase 2+** (quand l'auth existe) :
- [ ] Notifications push (progression du debat, nouveau commentaire)
- [ ] Mode facilitateur audio (Phase 8) : gros bouton rec, segments live, interface minimale

**Fichiers concernes** :
- Nouveau template `front/templates/front/includes/bottom_sheet_extraction.html`
- Template mobile `front/templates/front/lecture_mobile.html` (ou detection via media queries dans le template existant)
- CSS : media queries `max-width: 768px` dans le fichier de styles existant
- JS : `front/static/front/js/bottom_sheet.js`

**Tests E2E** :
- [ ] Sur viewport 375px : le layout est mono-colonne, pas de sidebar visible
- [ ] Tap sur un marqueur d'extraction → le bottom sheet s'ouvre avec la bonne carte
- [ ] Saisir un commentaire dans le bottom sheet → le commentaire est enregistre
- [ ] Bouton "Analyser" → l'extraction tourne et les marqueurs apparaissent dans le texte
- [ ] Drag handle vers le bas → le bottom sheet se ferme
- [ ] Navigation arbre → plein ecran, tap document → retour a la lecture

### Etape 1.15 — Heat map du debat sur le texte

**Argumentaire** : les pastilles de marge (Etape 1.3 bis, Etape 1.4) indiquent **ou** se trouvent les
extractions et **quel** est leur statut individuel. Mais elles ne montrent pas l'**intensite** du debat.
Un passage avec 12 commentaires et 3 desaccords a la meme pastille qu'un passage avec 1 commentaire
consensuel. L'utilisateur doit ouvrir chaque carte pour comprendre "ou ca chauffe".

La heat map resout ca en colorant le **fond du texte** selon l'intensite du debat :
- Plus il y a de commentaires et de desaccords sur un passage, plus le fond est **chaud** (rouge/orange)
- Les passages consensuels sont en **vert pale**
- Les passages non extraits sont **neutres** (pas de fond)

Ca donne une **temperature du texte** lisible en 2 secondes — avant meme de regarder les pastilles ou
d'ouvrir une carte. C'est particulierement utile pour les textes longs (20+ pages) ou scroller en lisant
les cartes une par une est impraticable.

> **Lien avec la "geometrie du debat"** : cette heat map est la brique visuelle de base d'un concept
> plus large discute avec Jean et Dominique — la **geometrie du debat**, un objet visuel qui rend
> compte de la forme et de la sante d'un debat a l'echelle d'un dossier entier (plusieurs textes
> analyses). Pas un jugement de qualite, mais une **cartographie** : ou en est le debat, quelle est
> sa forme, quels sont ses angles morts, ses zones denses et ses zones vides.
>
> La heat map par texte est le niveau micro (un document). La geometrie du debat par dossier serait
> le niveau macro — le dodecaedre a construire. Les deux se nourrissent des memes donnees (statuts,
> nombre de commentaires, couverture des extractions, repartition des hypostases).
>
> **A Jean et Dominique** : cette etape pose la premiere brique. La heat map montre l'intensite du
> debat sur un texte. Mais comment representer la geometrie du debat a l'echelle d'un dossier de
> 5 documents ? Quelles dimensions comptent pour vous : couverture (% du texte extrait), equilibre
> des statuts, diversite des contributeurs, repartition des hypostases, profondeur des fils ?
> Quelle forme visuelle vous parle : radar chart multi-axes, diagramme de Voronoi, graphe de liens,
> autre chose ? C'est votre concept — on attend vos retours pour l'integrer dans une etape dediee.

**Mockup — Heat map activee** :

```
┌──────────────────────────────────────────────────────────┐
│ [☰]  Charte IA v2              [Heat map ●] [⚙]         │
├───────────────────────────────────────────────────┬──────┤
│                                                   │ marge│
│   L'intelligence artificielle souleve des         │      │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │      │
│  ░ questions fondamentales sur l'avenir du    ░   │  ●   │
│  ░ travail creatif. Plusieurs participants    ░   │      │
│  ░ ont exprime des inquietudes.               ░   │      │
│  ░░░░░░░░░░░░░░░░░░░ fond rouge pale ░░░░░░░░░  │      │
│          (3 desaccords, 8 commentaires)           │      │
│                                                   │      │
│   En revanche, le secteur juridique semble        │      │
│  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  │  ●●  │
│  ▒ mieux prepare, avec des outils deja        ▒   │      │
│  ▒ operationnels dans les cabinets.           ▒   │      │
│  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ fond orange pale ▒▒▒▒▒▒▒  │      │
│          (1 desaccord, 4 commentaires)            │      │
│                                                   │      │
│   Le consensus se forme autour de l'idee          │      │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │  ○   │
│  ▓ que la regulation est necessaire mais      ▓   │      │
│  ▓ ne doit pas freiner l'innovation.          ▓   │      │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ fond vert pale ▓▓▓▓▓▓▓▓  │      │
│          (consensuel, 2 commentaires)             │      │
│                                                   │      │
│   Suite du texte sans extraction...               │      │
│   (pas de fond — passage non extrait)             │      │
│                                                   │      │
└───────────────────────────────────────────────────┴──────┘
```

**Calcul de la temperature** :
- Score par passage = `(nombre_commentaires * 1) + (nombre_statuts_non_consensuels * 3)`
- Normalise sur une echelle 0-1 (0 = consensuel sans commentaire, 1 = maximum du document)
- Mapping couleur :
  - Score 0 → `--statut-consensuel-bg` (vert pale `#f0fdf4`)
  - Score 0.3 → `--heatmap-tiede` (jaune pale `#fefce8`)
  - Score 0.6 → `--heatmap-chaud` (orange pale `#fff7ed`)
  - Score 1.0 → `--heatmap-brulant` (rouge pale `#fef2f2`)
  - Pas d'extraction → pas de fond (neutre)

**Actions** :
- [ ] Toggle "Heat map" dans la barre d'outils (icone thermometre ou flamme). Desactive par defaut — c'est un mode d'analyse, pas le mode de lecture normal
- [ ] Le fond colore est applique sur les `<span class="hl-extraction">` existants via une classe CSS supplementaire `.heatmap-active`
- [ ] La couleur de fond est calculee cote serveur (dans `front/utils.py` ou `front/views.py`) et injectee en `style="background-color: ..."` sur chaque span
- [ ] Quand la heat map est active, les pastilles de marge restent visibles (double signal : couleur marge = statut, couleur fond = intensite)
- [ ] L'etat du toggle est persiste en `localStorage`
- [ ] Compatible avec le mode focus (Etape 1.11) : en mode focus, la heat map est desactivee (lecture pure)

**Fichiers concernes** : `front/utils.py` (calcul du score + injection CSS), `front/views.py` (LectureViewSet — passage du flag heatmap), `marginalia.js` (toggle), CSS variables pour la palette heat map

**Tests E2E** :
- [ ] Activer la heat map : verifier que les passages extraits ont un fond colore
- [ ] Verifier qu'un passage avec beaucoup de commentaires a un fond plus chaud qu'un passage consensuel
- [ ] Verifier que les passages non extraits n'ont pas de fond
- [ ] Desactiver la heat map : verifier que les fonds disparaissent
- [ ] Mode focus + heat map : verifier que la heat map est desactivee en mode focus

### Etape 1.16 — Notifications de progression et facette temporelle de la geometrie du debat

**Argumentaire** : le dashboard de consensus (Etape 1.4) montre l'etat **statique** du debat a un
instant T. La heat map (Etape 1.15) montre l'intensite **spatiale**. Mais aucune brique ne repond a
la question **temporelle** : "est-ce que ca avance ? est-ce que c'est bloque ? qu'est-ce qui a change
depuis ma derniere visite ?"

Sans cette facette, l'utilisateur doit ouvrir le document, regarder le dashboard, comparer mentalement
avec son souvenir de la derniere fois. C'est invisible et ca cree de l'inertie — le debat stagne parce
que personne ne sait qu'il stagne.

Les notifications sont le **signal que la geometrie du debat a change de forme**. Pas un jugement —
une observation : "quelque chose a bouge". Chaque notification correspond a un mouvement dans le
dodecaedre (voir introduction "Geometrie du debat").

**Deux niveaux** :

**Niveau 1 — Phase 1 (mono-utilisateur, notifications in-app)** :

Les notifications sont de simples **indicateurs visuels** dans l'interface, pas des push ou des emails
(pas d'auth en Phase 1). Elles apparaissent quand l'utilisateur ouvre un document.

Mouvements detectes :
- **Seuil de consensus atteint** : "Ce document a atteint 80% de consensus. Pret pour une synthese ?"
  → Le seuil est configurable (defaut 80%). Le bouton "Lancer la synthese" dans le dashboard passe de
  grise a actif. C'est le mouvement le plus important — le dodecaedre se rapproche de sa forme complete.
- **Extractions orphelines** : "5 extractions n'ont aucun commentaire depuis leur creation."
  → Zone froide dans la geometrie. Le debat n'a pas commence sur ces passages.
- **Statut change** : "2 extractions sont passees de DISCUTE a CONSENSUEL depuis votre derniere visite."
  → Mouvement positif dans la facette statistique.
- **Nouveaux commentaires** : "3 nouveaux commentaires depuis votre derniere visite."
  → Activite dans la facette sociale.

Mockup — Bandeau de notification en haut de la zone de lecture :

```
┌──────────────────────────────────────────────────────────┐
│ [☰]  Charte IA v2                         [Analyser] [⚙]│
├──────────────────────────────────────────────────────────┤
│ 📊 Depuis votre derniere visite :                        │
│    · 2 extractions → CONSENSUEL  · 3 nouveaux commentaires│
│    · Consensus : 57% → 71%      [Voir le dashboard]  [✕]│
├──────────────────────────────────────────────────────────┤
│                                                          │
│   (texte de lecture avec marginalia...)                   │
│                                                          │
```

```
┌──────────────────────────────────────────────────────────┐
│ 🎯 Ce document a atteint 80% de consensus.               │
│    Pret pour une synthese ?   [Lancer la synthese]    [✕]│
├──────────────────────────────────────────────────────────┤
```

**Niveau 2 — Phase 2+ (multi-utilisateurs, notifications riches)** :

Avec l'authentification, les notifications deviennent **personnelles** et peuvent utiliser des canaux
externes (email, push). Les mouvements detectes s'enrichissent avec les facettes sociales et structurelles.

Mouvements supplementaires :
- **Desequilibre de participation** : "Michel a commente 12 extractions. Les 3 autres contributeurs
  n'ont rien dit depuis 5 jours." → Asymetrie dans la facette sociale.
- **Gap d'alignement** : "Le document 'Charte v2' a 0 extraction de type PRINCIPE alors que
  'Charte v1' en avait 4." → Regression dans la facette structurelle (necessite l'alignement, Etape 1.12).
- **Debat bloque** : "L'extraction 'L'IA va transformer...' est en CONTROVERSE depuis 2 semaines,
  avec 8 commentaires sans changement de statut." → Stagnation dans la facette temporelle.
- **Couverture desequilibree** : "Toutes les CONJECTURES sont DISCUTEES mais aucun AXIOME n'a ete
  extrait." → Le debat couvre les hypotheses mais pas les fondements (facette structurelle).
- **Mention directe** : "Yves vous a mentionne dans un commentaire sur 'La loi d'Amara'."
  → Facette sociale, interaction directe.

**Lien avec la geometrie du debat** :

Chaque notification est un **evenement geometrique** — un deplacement dans l'une des facettes du
dodecaedre. Le systeme de notifications est la facon dont le dodecaedre **communique ses mouvements**
aux participants. Sans lui, la geometrie est visible mais muette.

```
                    Statistique
                    (dashboard)
                   ╱            ╲
        Sociale   ╱              ╲  Temporelle
    (qui a dit   ╱   Geometrie    ╲  (notifications
      quoi)     ╱    du debat      ╲  de progression)
               ╱                    ╲
  Structurelle ╲                    ╱ Thermique
  (alignement   ╲                  ╱  (heat map)
   hypostases)   ╲                ╱
                  ╲──────────────╱
                    Spatiale
                   (pastilles
                    de marge)
```

> **A Jean et Dominique** : ce schema est une premiere ebauche des facettes. Le dodecaedre reel
> a peut-etre d'autres faces : la facette **epistemique** (repartition des hypostases — est-ce qu'on
> a des PHENOMENES et des LOIS, ou seulement des CONJECTURES ?), la facette **convergence** (est-ce
> que les desaccords se resorbent dans le temps ou se creusent ?), la facette **completude** (le texte
> est-il integralement couvert par des extractions, ou y a-t-il des zones mortes ?).
>
> Chaque facette supplementaire enrichit la geometrie. La question ouverte : quelle **representation
> visuelle** donne a voir cette geometrie d'un coup d'oeil ? Un radar chart multi-axes ? Un diagramme
> dont la forme se deforme en fonction de l'etat du debat ? Un score composite ? Plusieurs indicateurs
> independants ? C'est votre concept — on pose les briques techniques, a vous la vision.

**Actions Phase 1** :
- [ ] **Systeme de "derniere visite"** : stocker un timestamp `derniere_visite` en `localStorage` pour chaque page (Phase 1 sans auth) ou en base par user (Phase 2)
- [ ] **Calcul des mouvements** : au chargement d'une page, comparer l'etat actuel du dashboard avec l'etat a la derniere visite. Changements detectes :
  - Nombre de commentaires ajoutes depuis `derniere_visite`
  - Extractions dont le statut a change
  - Extractions sans commentaire (orphelines)
  - Seuil de consensus franchi (vers le haut ou vers le bas)
- [ ] **Bandeau de notification** : partial HTMX en haut de la zone de lecture, affiche les mouvements detectes. Bouton [✕] pour fermer. Le bandeau disparait apres consultation (mise a jour du timestamp)
- [ ] **Notification de seuil** : quand le % de consensus depasse le seuil configure (defaut 80%), bandeau special avec bouton "Lancer la synthese" actif
- [ ] **Pas de push, pas d'email en Phase 1** — tout est in-app, visible a l'ouverture du document

**Actions Phase 2+** :
- [ ] Migration du timestamp en base (`DerniereVisite` : user + page + timestamp)
- [ ] Notifications par email (digest quotidien ou hebdomadaire, configurable par user)
- [ ] Mouvements sociaux : desequilibre de participation, mentions
- [ ] Mouvements structurels : gaps d'alignement, couverture desequilibree (necessite Etape 1.12)
- [ ] Page "Centre de notifications" avec historique des mouvements

**Fichiers concernes** : `front/views.py` (LectureViewSet — calcul des mouvements au chargement), nouveau template `front/templates/front/includes/bandeau_notification.html`, `marginalia.js` (gestion du localStorage derniere_visite), Phase 2 : nouveau modele `DerniereVisite` dans `core/models.py`

**Tests E2E** :
- [ ] Premiere visite : pas de bandeau (rien a comparer)
- [ ] Ajouter des commentaires, revenir sur la page : verifier que le bandeau affiche "N nouveaux commentaires"
- [ ] Changer le statut de 2 extractions, revenir : verifier "2 extractions → CONSENSUEL"
- [ ] Atteindre le seuil de consensus : verifier le bandeau special avec bouton synthese
- [ ] Fermer le bandeau (✕) : verifier qu'il ne reapparait pas au rechargement

---

## 3. Phase 2 — Gestion utilisateurs et partage

> Objectif : passer d'un mode mono-utilisateur (prenom) a un vrai systeme d'auth avec partage.

### Etape 2.1 — Authentification Django

**Actions** :
- [ ] Activer `django.contrib.auth` (deja installe) avec login/logout/register
- [ ] Creer un modele `UserProfile` si necessaire (preferences, avatar)
- [ ] Ajouter un middleware d'authentification pour le front (pages protegees)
- [ ] L'API core (extension) reste `AllowAny` pour le MVP, mais prevoir token auth

**Fichiers concernes** : `hypostasia/settings.py`, nouveau fichier `front/auth_views.py` ou actions sur un `AuthViewSet`

### Etape 2.2 — Propriete et partage de dossiers

**Actions** :
- [ ] Ajouter `owner` (FK User) sur `Dossier` et `Page`
- [ ] Modele `DossierPartage` : user + dossier + permission (lecture/ecriture)
- [ ] Filtrer l'arbre par user connecte (mes dossiers + dossiers partages avec moi)
- [ ] Remplacer `prenom` par `request.user` dans CommentaireExtraction et Question/Reponse

**Fichiers concernes** : `core/models.py`, `front/views.py` (ArbreViewSet, DossierViewSet), migrations

### Etape 2.3 — Auth dans l'extension navigateur

**Actions** :
- [ ] Ajouter un champ token/session dans les options de l'extension
- [ ] Envoyer le token dans les headers de chaque requete API
- [ ] Associer automatiquement les pages creees au user connecte

**Fichiers concernes** : `extension/popup.js`, `extension/options.js`, `core/views.py`

### Etape 2.4 — Filtre "qui a dit quoi" sur les commentaires

**Argumentaire** : quand 5 personnes debattent sur un document avec 20 extractions, les fils de
commentaires melangent les voix de tout le monde. Avant une reunion de consensus, le facilitateur
a besoin de repondre a "qu'est-ce que Michel a dit sur ce texte ?" ou "quelles extractions Sarah
a-t-elle commentees ?" sans ouvrir les 20 fils un par un.

C'est un besoin de **preparation de reunion** : le facilitateur veut arriver en sachant qui a dit quoi,
ou sont les convergences et les divergences entre personnes. Sans ce filtre, il doit lire l'integralite
des fils, ce qui prend 30 minutes pour un document bien debattu.

**Actions** :
- [ ] Menu deroulant "Filtrer par contributeur" en haut du drawer vue liste
  - Liste des users ayant commente au moins une extraction du document
  - Chaque entree montre le nom + le nombre de commentaires (ex: "Michel (7)")
  - Option "Tous" pour restaurer la vue complete
- [ ] Quand un contributeur est selectionne :
  - Le drawer ne montre que les extractions **ayant au moins un commentaire de ce contributeur**
  - Les commentaires des autres contributeurs restent visibles mais en opacite reduite (pas masques — le contexte du debat est utile)
  - Les pastilles de marge ne montrent que les extractions commentees par ce contributeur
- [ ] La heat map (Etape 1.15) peut se combiner avec le filtre : "montrer la temperature du debat du point de vue de Michel" (seuls ses commentaires comptent dans le calcul)

**Fichiers concernes** : `front/views.py` (ExtractionViewSet — action filtre par contributeur), `extraction_results.html` (drawer), `marginalia.js` (filtrage des pastilles), CSS (opacite reduite pour les commentaires hors filtre)

### Tests E2E Phase 2

- [ ] Login/logout/register
- [ ] Arbre filtre par user (mes dossiers + partages)
- [ ] Commentaire avec user authentifie (plus de prenom libre)
- [ ] Filtre contributeur : selectionner un user, verifier que seules ses extractions commentees sont visibles
- [ ] Filtre contributeur : verifier que les commentaires des autres sont en opacite reduite (pas masques)
- [ ] Filtre contributeur + heat map : verifier que la temperature reflette uniquement les commentaires du contributeur selectionne

---

## 4. Phase 3 — Providers IA unifies

> Objectif : une couche d'abstraction unique pour tous les appels LLM (extraction, reformulation, restitution, transcription).

### Etat actuel des providers

| Fonctionnalite | Providers supportes | Code |
|----------------|---------------------|------|
| Extraction LangExtract | Google Gemini, OpenAI GPT | `hypostasis_extractor/services.py:resolve_model_params` |
| Reformulation | Google Gemini, OpenAI GPT, Mock | `front/tasks.py:_appeler_llm_reformulation` |
| Restitution | idem reformulation | `front/tasks.py:restituer_debat_task` |
| Transcription audio | Voxtral (Mistral), Mock | `front/services/transcription_audio.py` |

### Etape 3.1 — Couche d'abstraction LLM

**Actions** :
- [ ] Creer `core/llm_providers.py` avec une interface commune : `appeler_llm(modele, messages, **kwargs) -> str`
- [ ] Implementer les backends : `GoogleGeminiBackend`, `OpenAIBackend`, `OllamaBackend`, `AnthropicBackend`, `MockBackend`
- [ ] Pour Ollama : utiliser l'API compatible OpenAI (`base_url` parametrable)
- [ ] Pour Anthropic : utiliser le SDK `anthropic`
- [ ] Migrer `_appeler_llm_reformulation` et `resolve_model_params` vers cette couche

**Strategie LangExtract** : LangExtract est la dependance structurante pour l'extraction. Elle ne supporte que Gemini et OpenAI.
- Court terme : garder LangExtract tel quel, ca fonctionne
- Moyen terme : contribuer au repo open-source pour ajouter les providers Ollama et Anthropic (PR upstream)
- Si le merge est refuse : forker la lib et maintenir notre version (`hypostasia-langextract` ou fork GitHub)
- La couche d'abstraction LLM (`core/llm_providers.py`) est concue pour que ce remplacement soit possible sans toucher au reste du code

**Fichiers concernes** : nouveau `core/llm_providers.py`, `front/tasks.py`, `hypostasis_extractor/services.py`

### Etape 3.2 — Modele AIModel etendu

**Actions** :
- [ ] Ajouter les providers Ollama et Anthropic dans `Provider` TextChoices
- [ ] Ajouter les modeles Ollama (llama3, mistral, etc.) et Anthropic (claude-sonnet, claude-haiku) dans `AIModelChoices`
- [ ] Ajouter un champ `base_url` sur `AIModel` pour Ollama et endpoints custom
- [ ] Mettre a jour le mapping `prefix_to_provider` dans `AIModel.save()`

**Fichiers concernes** : `core/models.py`, migration

### Etape 3.3 — Transcription audio multi-provider

**Actions** :
- [ ] Ajouter Whisper (OpenAI) comme provider de transcription
- [ ] Ajouter un backend local (whisper.cpp ou faster-whisper via Ollama)
- [ ] Unifier avec la couche d'abstraction

**Fichiers concernes** : `core/models.py` (TranscriptionConfig), `front/services/transcription_audio.py`

### Tests E2E Phase 3

- [ ] Analyse IA avec chaque provider (mock) : verifier extractions
- [ ] Reformulation avec provider alterne
- [ ] Transcription audio avec Whisper mock

---

## 5. Phase 4 — Prompts et couts

> Objectif : rendre la gestion des prompts user-friendly et fiabiliser le calcul des couts.

### Etape 4.1 — Interface de gestion des analyseurs dans le front

**Actions** :
- [ ] Sortir la gestion des analyseurs de l'admin Django
- [ ] Creer des partials HTMX pour : liste analyseurs, edition prompt pieces, gestion exemples
- [ ] Preview live du prompt assemble (avant test ou analyse)
- [ ] Templates de prompts pre-configures (bouton "charger un template")
- [ ] L'interface utilise la charte visuelle Yves : preview des cartes d'extraction avec polices B612/B612 Mono, couleurs par famille d'hypostase, distinction machine/citation

**Fichiers concernes** : `front/views.py` (nouveau AnalyseurFrontViewSet ou actions sur ExtractionViewSet), templates `front/includes/`

### Etape 4.2 — Calcul des couts fiabilise

**Probleme actuel** : l'estimation utilise `cl100k_base` (tokenizer GPT-4) pour tous les modeles, et 20% d'output par defaut, ce qui sous-estime pour Gemini et sur-estime pour les petits modeles.

**Actions** :
- [ ] Utiliser le bon tokenizer par provider (tiktoken pour OpenAI, estimation caracteres pour Gemini, tokenizer Anthropic pour Claude)
- [ ] Stocker les tokens reels consommes dans `ExtractionJob` (usage retourne par l'API)
- [ ] Afficher le cout reel vs estime apres chaque analyse
- [ ] Dashboard cumulatif des couts par modele/analyseur

**Fichiers concernes** : `front/views.py` (previsualiser_analyse), `core/models.py` (AIModel.estimer_cout_euros), `front/tasks.py`, `hypostasis_extractor/services.py`

### Etape 4.3 — Historique des prompts

**Actions** :
- [ ] Stocker un snapshot complet du prompt dans chaque ExtractionJob (deja fait partiellement via `prompt_description`)
- [ ] Permettre de comparer deux versions de prompt
- [ ] Rollback a une version precedente d'un analyseur

**Fichiers concernes** : `hypostasis_extractor/models.py`, `hypostasis_extractor/services.py`

### Tests E2E Phase 4

- [ ] Gestion des analyseurs dans le front (creer, editer prompt, ajouter exemple)
- [ ] Preview du prompt assemble
- [ ] Verification cout reel vs estime apres analyse mock

---

## 6. Phase 5 — Edition collaborative et fil de tracabilite

> Objectif : permettre l'edition du texte source avec historique, traçabilite,
> et navigation complete du fil de reflexion (texte source → extraction → debat → synthese → nouvelle version).

### Etape 5.1 — Modele de tracabilite source (SourceLink)

**Probleme** : le cycle Lecture → Extraction → Commentaire → Synthese → Nouvelle version existe en parties isolees mais il manque le lien structurel entre elles. On ne peut pas remonter le fil d'un paragraphe de la version finale jusqu'au texte original.

**Actions** :
- [ ] Creer un modele `SourceLink` (ou `Provenance`) qui lie un passage de texte a son origine :
  - `page_cible` (FK Page) — la page/version qui contient le passage produit
  - `start_char_cible` / `end_char_cible` — position du passage dans la version cible
  - `page_source` (FK Page, nullable) — la version precedente d'ou vient le texte
  - `start_char_source` / `end_char_source` — position du passage source
  - `extraction_source` (FK ExtractedEntity, nullable) — extraction qui a motive le changement
  - `commentaires_source` (M2M CommentaireExtraction) — commentaires du debat
  - `type_lien` : `identique` (passage repris tel quel), `modifie` (passage reformule), `nouveau` (passage sans source directe), `supprime` (passage source retire)
  - `justification` — texte libre expliquant pourquoi ce passage a change
- [ ] Quand une restitution est creee (manuelle ou IA), exiger ou generer les SourceLinks
- [ ] Pour les restitutions IA : demander au LLM de structurer sa reponse avec des references aux sources, puis parser les references pour creer les SourceLinks automatiquement
- [ ] Migration + tests unitaires du modele

**Fichiers concernes** : `core/models.py` (nouveau modele), migration, `front/tasks.py` (restituer_debat_task), `hypostasis_extractor/models.py`

### Etape 5.2 — Historique des modifications

**Actions** :
- [ ] Modele `PageEdit` : FK Page, user, timestamp, diff (avant/apres), type_edit (titre, contenu, bloc_transcription)
- [ ] Enregistrer chaque modification dans editer_bloc, renommer_locuteur, modifier_titre
- [ ] Vue historique par page (timeline des modifications)

**Fichiers concernes** : nouveau modele dans `core/models.py`, `front/views.py`

### Etape 5.3 — Diff entre versions avec liens de provenance

**Actions** :
- [ ] Utiliser `difflib` pour generer un diff HTML entre deux versions de text_readability
- [ ] Action "comparer" sur LectureViewSet : affiche un side-by-side des deux versions
- [ ] Coloration des ajouts/suppressions/modifications
- [ ] **Superposer les SourceLinks sur le diff** : chaque zone modifiee affiche un lien vers l'extraction/commentaire/debat qui l'a motivee
- [ ] Clic sur une zone modifiee → popup ou panneau montrant : passage source + extraction + commentaires
- [ ] Note : l'Etape 5.8 (comparaison cote-a-cote avec provenance) etend cette etape en ajoutant les indicateurs de provenance (✎/🤖/🤖⚠️) et le compteur de sourcage sur chaque zone modifiee

**Fichiers concernes** : `front/views.py`, nouveau template `front/includes/diff_versions.html`, `core/models.py` (SourceLink)

### Etape 5.4 — Vue "fil de reflexion" complet

**Objectif** : pour n'importe quel passage de n'importe quelle version, pouvoir naviguer toute la chaine de reflexion depuis l'origine.

**Actions** :
- [ ] Action "Voir le fil" sur un passage annote → affiche une timeline verticale :
  1. Texte original (version 1, passage source)
  2. Extraction qui a identifie ce passage
  3. Commentaires du debat (avec auteurs et dates)
  4. Synthese produite (avec justification)
  5. Texte final dans la version N
- [ ] Chaque element du fil est cliquable (navigation vers la page/extraction/commentaire concerne)
- [ ] Si le passage a traverse plusieurs iterations (v1 → v2 → v3), le fil montre toute la chaine
- [ ] Export du fil en Markdown (pour documentation ou audit)
- [ ] Charte visuelle dans le fil — la distinction typographique encode la provenance :
  - Texte source en `.typo-citation` (Lora italique — chaleur d'une parole humaine preservee)
  - Commentaires en `.typo-lecteur-nom` + `.typo-lecteur-corps` (Srisakdi bleu — quelqu'un reagit)
  - Synthese IA en `.typo-machine` (B612 Mono neutre — la machine a produit ca)
  - L'utilisateur scanne le fil et sait *instantanement* qui a dit quoi, sans lire les labels

**Fichiers concernes** : `front/views.py` (nouvelle action sur LectureViewSet), nouveau template `front/includes/fil_reflexion.html`

### Etape 5.5 — Verrous d'edition (si multi-user)

**Actions** :
- [ ] Systeme de verrou optimiste (timestamp de derniere modification)
- [ ] Alerte si quelqu'un a modifie entre temps
- [ ] Pas de verrou pessimiste (trop complexe pour un MVP)

**Fichiers concernes** : `front/views.py`, `front/serializers.py`

### Etape 5.6 — Synthese assistee avec sourcage obligatoire (wizard guide)

**Objectif** : quand l'IA produit une synthese/restitution, chaque paragraphe doit etre ancre sur une source verifiable. Et l'UX de creation de cette synthese doit incarner la tracabilite — pas juste la stocker en base.

> **Pourquoi un wizard** : la synthese est le climax du cycle deliberatif — le moment ou le debat
> se cristallise en texte. Actuellement c'est un bouton "Restituer" → un textarea → l'IA genere
> → c'est stocke. C'est trop brutal pour l'acte le plus important du produit.
>
> Un textarea libre ne garantit rien : l'utilisateur (ou l'IA) peut ecrire n'importe quoi sans lien
> avec les sources. Le wizard force la tracabilite *par le design de l'interaction*, pas juste par
> la structure de donnees. Chaque etape du wizard correspond a une exigence de tracabilite :
> selection des sources, revue du debat, redaction sourcee, verification, publication.
>
> Le dashboard de consensus (Etape 1.4) conditionne l'acces au wizard : le bouton "Lancer la synthese"
> n'est actif que quand le seuil de consensus est atteint. Les extractions masquees (Etape 1.8)
> sont exclues par defaut de la selection.

**Wizard de synthese en 5 etapes** (partials HTMX multi-etapes, en pleine page ou drawer large) :

> **Note layout** : le wizard ne s'affiche pas dans un panneau permanent (il n'y en a plus depuis
> l'Etape 1.3 bis). Il s'ouvre en **mode pleine page** : la zone de lecture est remplacee par le wizard,
> avec un bouton "Retour au texte" pour quitter. C'est un acte majeur (rediger une synthese) qui
> merite son propre espace. Alternativement, un drawer large (50% de la largeur) peut etre utilise
> si l'utilisateur veut garder le texte visible a cote.

**Etape 1 — Selection des extractions** :
```
┌─────────────────────────────────────────┐
│  Synthese — Etape 1/5 : Selection       │
│                                          │
│  Quelles extractions inclure ?           │
│                                          │
│  ☑ ⚫ LOI "La loi d'Amara..."      (CS) │
│  ☑ ⚫ PRINCIPE "Le numerique..."   (CS) │
│  ☐ ▶ CONJECTURE "L'IA va..."     (DSC) │
│  ☑ ▷ HYPOTHESE "Si on applique..." (DS) │
│                                          │
│  3 extractions masquees (non montrees)   │
│                                          │
│  3 selectionnees / 4 visibles            │
│                                          │
│              [Suivant →]                 │
└─────────────────────────────────────────┘
```
- Vue checkbox avec les cartes compactes, pre-cochees sur les CONSENSUELLES
- Les extractions masquees (curation Etape 1.8) ne sont pas montrees
- Les extractions CONTROVERSE sont signalees avec un warning

**Etape 2 — Revue des commentaires** :
```
┌─────────────────────────────────────────┐
│  Synthese — Etape 2/5 : Revue           │
│                                          │
│  LOI "La loi d'Amara..."          ⚫ CS  │
│  ┌─────────────────────────────────┐     │
│  │ Jonas (3 mars) :                │     │
│  │ "D'accord avec cette loi, mais  │     │
│  │ il faut nuancer pour le cas..." │     │
│  │                                 │     │
│  │ Yves (4 mars) :                 │     │
│  │ "La nuance est essentielle,     │     │
│  │ voir aussi les travaux de..."   │     │
│  └─────────────────────────────────┘     │
│  Points cles a retenir : ___________    │
│                                          │
│         [← Precedent]  [Suivant →]       │
└─────────────────────────────────────────┘
```
- Pour chaque extraction incluse, afficher les commentaires cles
- Champ optionnel "Points cles a retenir" pour guider la redaction
- L'utilisateur valide qu'il a bien lu le debat avant de passer a la redaction

**Etape 3 — Redaction** :
```
┌─────────────────────────────────────────┐
│  Synthese — Etape 3/5 : Redaction       │
│                                          │
│  ┌─────────────────────────────────┐     │
│  │ [Textarea de redaction]         │     │
│  │                                 │     │
│  │ La loi d'Amara, nuancee par les │     │
│  │ observations de Jonas et Yves,  │     │
│  │ suggere que [src:extr-42]...    │     │
│  └─────────────────────────────────┘     │
│                                          │
│  Sources disponibles :                   │
│  📌 extr-42 : LOI "La loi d'Amara..."   │
│  📌 extr-45 : PRINCIPE "Le num..."      │
│  📌 comment-17 : Jonas "D'accord..."    │
│                                          │
│  [Pre-remplir par IA]                    │
│                                          │
│         [← Precedent]  [Suivant →]       │
└─────────────────────────────────────────┘
```
- Textarea avec les citations sources listees en dessous (cliquables pour inserer la reference)
- Bouton "Pre-remplir par IA" : l'IA genere un brouillon avec references inline `[src:extraction-42]`
- L'humain a le dernier mot — il peut modifier, supprimer, ajouter

**Etape 4 — Verification du sourcage** :
```
┌─────────────────────────────────────────┐
│  Synthese — Etape 4/5 : Verification    │
│                                          │
│  ✅ "La loi d'Amara, nuancee par..."    │
│     → src: extr-42, comment-17           │
│                                          │
│  ⚠️ "En conclusion, il faut agir        │
│     rapidement sur ces enjeux."          │
│     → AUCUNE SOURCE                      │
│     [Ajouter une source] [Valider tel q] │
│                                          │
│  1 passage non source sur 2              │
│                                          │
│         [← Precedent]  [Suivant →]       │
└─────────────────────────────────────────┘
```
- Le systeme affiche chaque paragraphe avec ses sources liees
- Les passages sans source sont marques en warning (fond orange pale)
- L'utilisateur peut ajouter une source manuellement ou valider "tel quel"
- Le bouton "Suivant" est actif meme avec des passages non sources (mais le warning reste visible)

**Etape 5 — Publication** :
```
┌─────────────────────────────────────────┐
│  Synthese — Etape 5/5 : Publication     │
│                                          │
│  Label de version : [V2 — Post-debat___]│
│                                          │
│  Resume des changements :                │
│  - 3 extractions integrees              │
│  - 2 commentaires pris en compte        │
│  - 1 passage non source (valide)        │
│                                          │
│         [← Precedent]                    │
│         [Creer la version 2 →]           │
└─────────────────────────────────────────┘
```
- Label de version et resume automatique
- Bouton final "Creer la version" → cree la Page fille, les SourceLinks, redirige vers la nouvelle version

**Actions techniques** :
- [ ] Modifier le prompt de restitution pour exiger des references inline (ex: `[src:extraction-42]`, `[src:comment-17]`)
- [ ] Parser la reponse IA pour extraire les references et creer les SourceLinks automatiquement
- [ ] Si un paragraphe IA n'a aucune reference → le marquer visuellement comme "non source" (warning)
- [ ] Implementer les 5 etapes du wizard comme partials HTMX enchaines (chaque etape = un partial, navigation par boutons Precedent/Suivant)
- [ ] L'etat du wizard est stocke en session (ou dans un modele temporaire `SyntheseEnCours`) pour permettre la navigation avant/arriere sans perte de donnees
- [ ] Le wizard est accessible uniquement depuis le dashboard de consensus (Etape 1.4) — pas de bouton "Restituer" isole sur les cartes
- [ ] Charte visuelle dans le wizard : citations en `.typo-citation`, commentaires en `.typo-lecteur`, texte IA en `.typo-machine`

**Fichiers concernes** : `front/tasks.py` (restituer_debat_task), `front/views.py` (SyntheseViewSet ou actions sur ExtractionViewSet), nouveaux templates `front/includes/synthese_etape_1.html` a `synthese_etape_5.html`, `front/serializers.py`

### Etape 5.7 — Export visuel du debat (PDF et HTML)

**Argumentaire** : l'export Markdown (prevu dans plusieurs etapes) couvre le besoin technique —
archivage, versionning, portabilite. Mais le **livrable politique** est different. Quand un facilitateur
presente le resultat d'un debat au CA, aux financeurs, aux elus d'une collectivite, ou a un comite de
pilotage, il ne montre pas du Markdown brut. Il montre un **document mis en forme** qui porte la
credibilite de tout le processus deliberatif.

L'export visuel est le moment ou Hypostasia produit son **artefact final** — celui qui justifie tout le
travail d'extraction, de debat et de synthese. Si cet artefact est laid ou illisible, le produit perd
sa valeur percue au moment le plus critique. L'export doit etre **aussi beau que l'interface**.

C'est aussi un outil de **communication interne** : partager un PDF du debat avec des parties prenantes
qui n'ont pas de compte Hypostasia. Le document doit etre autosuffisant — comprehensible sans connaitre
l'outil.

**Deux formats d'export** :

**1. Export PDF — Le livrable formel**

Le PDF preserve integralement la charte typographique de Yves :
- B612 Mono pour les resumes IA
- Lora italique pour les citations sources
- Srisakdi pour les interventions lecteur
- B612 gras uppercase pour les hypostases, avec les couleurs par famille
- Badges de statut colores (CONSENSUEL vert, DISCUTE ambre, etc.)

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  CHARTE IA — COMPTE-RENDU DE DEBAT                     │
│  Exporte le 8 mars 2026 depuis Hypostasia               │
│                                                         │
│  ═══════════════════════════════════════════════         │
│                                                         │
│  RESUME DU DEBAT                                        │
│  14 extractions · 47 commentaires · 3 contributeurs     │
│  ████████████░░░░  71% consensus                        │
│                                                         │
│  ───────────────────────────────────────────────         │
│                                                         │
│  CONJECTURE                                    DISCUTE  │
│  L'IA generative va transformer les metiers    ▷        │
│  creatifs en metiers de supervision.                    │
│                                                         │
│  « Je pense que dans 5 ans, on ne dessinera             │
│    plus, on pilotera des IA. »                          │
│                      — Source: paragraphe 3, ligne 12   │
│                                                         │
│  💬 Jonas (3 mars) : Trop reducteur, il y a des        │
│     metiers ou la main humaine reste essentielle.       │
│  💬 Yves (4 mars) : D'accord avec Jonas. Voir          │
│     aussi les travaux de Crawford sur le sujet.         │
│  💬 Marie (5 mars) : La supervision est aussi           │
│     un metier creatif, non ?                            │
│                                                         │
│  ───────────────────────────────────────────────         │
│                                                         │
│  LOI                                       CONSENSUEL   │
│  La loi d'Amara : on surestime toujours    ⚫           │
│  l'impact a court terme...                              │
│                                                         │
│  (...)                                                  │
│                                                         │
│  ═══════════════════════════════════════════════         │
│  Genere par Hypostasia · hypostasia.org                 │
│  Tracabilite complete : chaque element remonte          │
│  a sa source humaine verifiable.                        │
└─────────────────────────────────────────────────────────┘
```

**2. Export HTML — Le livrable partageable**

Fichier HTML autonome (single-file, CSS inline, polices embarquees en base64 ou via CDN) :
- Meme rendu visuel que le PDF
- Interactif : les cartes d'extraction sont depliables (accordeon JS inline)
- Navigable : ancres internes entre le texte source et les extractions
- Partageable par email ou lien (c'est un fichier, pas une URL Hypostasia)

**Contenu de l'export** (les deux formats) :

1. **En-tete** : titre du document, date d'export, nombre d'extractions/commentaires/contributeurs, barre de consensus
2. **Texte source** : le texte integral avec les passages extraits surlignes (memes couleurs que la heat map)
3. **Cartes d'extraction** : inserees apres chaque passage surligne (meme layout que les cartes inline)
   - Hypostase typee et coloree
   - Resume IA (B612 Mono)
   - Citation source (Lora italique)
   - Fil de commentaires avec noms et dates
   - Sources Deep Research si disponibles (Etape 7.2)
   - Statut de debat avec badge colore
4. **Synthese** (si une version synthetisee existe, Phase 5) : le texte de synthese avec les SourceLinks resolus
5. **Pied de page** : mention Hypostasia, note de tracabilite

**Actions** :
- [ ] Bouton "Exporter" dans la barre d'outils avec dropdown : "PDF" / "HTML" / "Markdown" (Markdown existe deja)
- [ ] **Generation PDF** : via WeasyPrint (librairie Python, genere du PDF depuis du HTML+CSS). WeasyPrint supporte les Google Fonts, les CSS custom properties, et les layouts complexes
  - Template HTML dedie a l'export (`front/templates/front/export/debat_pdf.html`) — pas le meme que l'interface web
  - CSS dedie (`front/static/front/css/export.css`) avec `@page` pour les marges, en-tetes/pieds de page
  - Les polices (B612, Lora, Srisakdi) sont embarquees ou chargees depuis le CDN au moment de la generation
- [ ] **Generation HTML** : meme template que le PDF mais avec JS inline pour les accordeons
  - Single-file : tout le CSS et JS est inline dans le `<head>`
  - Les polices sont chargees via CDN (Google Fonts) — le fichier reste leger
  - Fallback si hors-ligne : les polices degradent gracieusement vers les familles generiques
- [ ] **Endpoint** : action `exporter` sur `LectureViewSet` avec parametre `format=pdf|html|markdown`
  - PDF : `Content-Type: application/pdf`, `Content-Disposition: attachment`
  - HTML : `Content-Type: text/html`, `Content-Disposition: attachment`
- [ ] Le contenu de l'export est genere cote serveur (pas de JS cote client pour le PDF)
- [ ] L'export inclut automatiquement les extractions non masquees (curation Etape 1.8 respectee)
- [ ] L'export d'un dossier (Phase 2+) genere un document multi-textes avec table des matieres

**Fichiers concernes** :
- Nouveau `front/templates/front/export/debat_pdf.html` (template export PDF/HTML)
- Nouveau `front/static/front/css/export.css` (styles d'impression, `@page`)
- `front/views.py` (LectureViewSet — action exporter, generation PDF via WeasyPrint)
- `requirements.txt` / `pyproject.toml` : ajout de `weasyprint`

**Tests E2E** :
- [ ] Export PDF : verifier que le fichier est genere, qu'il contient les extractions avec les bonnes couleurs
- [ ] Export HTML : verifier que le fichier est autonome (s'ouvre dans un navigateur sans serveur)
- [ ] Export HTML : verifier que les accordeons fonctionnent (clic deplie/replie)
- [ ] Verifier que les extractions masquees ne sont pas dans l'export
- [ ] Verifier que la charte typographique est respectee (polices, couleurs, statuts)

### Etape 5.8 — Mode comparaison cote-a-cote avec provenance explicite

**Argumentaire** : l'Etape 5.3 prevoit un diff technique entre deux versions (ajouts/suppressions colores
via `difflib`). Mais un diff ne repond qu'a la question "qu'est-ce qui a change ?". Il ne repond pas a
la question **fondamentale** : "pourquoi ca a change ?".

Un diff classique (type GitHub) montre du vert et du rouge. C'est utile pour du code, mais pour un texte
deliberatif c'est insuffisant — et meme dangereux. Sans provenance explicite, une modification peut
ressembler a de la magie : le texte de la v1 devient le texte de la v2, et personne ne sait si c'est
un humain qui a reformule, une IA qui a invente, ou un consensus reel qui a muri.

Le mode comparaison incarne la valeur fondatrice "le LLM est un outil, pas un auteur" (voir introduction).
Chaque zone modifiee doit repondre a 3 questions en un coup d'oeil :
1. **Quoi** : qu'est-ce qui a change (le diff visuel)
2. **Pourquoi** : quelle deliberation a motive ce changement (les sources)
3. **Qui** : qui a contribue a cette modification (les auteurs)

C'est la **tracabilite rendue visuelle** — pas cachee dans une base de donnees, pas dans un log,
mais directement dans l'interface, au moment ou l'utilisateur compare deux versions.

**Mockup — Comparaison cote-a-cote** :

```
┌────────────────────────────────────────────────────────────────┐
│ Comparer : [V1 — Brouillon ▾]  ←→  [V2 — Post-debat ▾]       │
│                                                                │
│ ┌───────────────────────────┬────────────────────────────────┐ │
│ │  Version 1                │  Version 2                     │ │
│ │                           │                                │ │
│ │  L'IA est un outil        │  L'IA est un outil             │ │
│ │  ░░░░░░░░░░░░░░░░░░░░░░  │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │ │
│ │  ░ prometteur pour ░░░░  │  ▓ essentiel pour l'education ▓ │ │
│ │  ░ l'education. ░░░░░░░  │  ▓ sous reserve de regulation ▓ │ │
│ │  ░░░░░░░░░░░░░░░░░░░░░░  │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │ │
│ │                           │                                │ │
│ │                           │  📎 Pourquoi ce changement :   │ │
│ │                           │  ┌──────────────────────────┐  │ │
│ │                           │  │ Source : extraction #42  │  │ │
│ │                           │  │ CONJECTURE — "L'IA va    │  │ │
│ │                           │  │ transformer les metiers" │  │ │
│ │                           │  │                          │  │ │
│ │                           │  │ 💬 Jonas (3 mars) :      │  │ │
│ │                           │  │ "Trop reducteur, il faut │  │ │
│ │                           │  │ nuancer avec la question │  │ │
│ │                           │  │ de la regulation."       │  │ │
│ │                           │  │                          │  │ │
│ │                           │  │ 💬 Marie (5 mars) :      │  │ │
│ │                           │  │ "D'accord. Ajouter       │  │ │
│ │                           │  │ 'sous reserve de         │  │ │
│ │                           │  │ regulation'."            │  │ │
│ │                           │  │                          │  │ │
│ │                           │  │ Statut : CONSENSUEL ⚫   │  │ │
│ │                           │  └──────────────────────────┘  │ │
│ │                           │                                │ │
│ │  Il faut aussi penser     │  Il faut aussi penser          │ │
│ │  aux implications         │  aux implications              │ │
│ │  ethiques.                │  ethiques.                     │ │
│ │  (inchange)               │  (inchange)                    │ │
│ │                           │                                │ │
│ │  ░░░░░░░░░░░░░░░░░░░░░░  │                                │ │
│ │  ░ Le marche semble ░░░  │  (passage supprime)             │ │
│ │  ░ bien oriente. ░░░░░░  │                                │ │
│ │  ░░░░░░░░░░░░░░░░░░░░░░  │  📎 Pourquoi supprime :       │ │
│ │                           │  ┌──────────────────────────┐  │ │
│ │                           │  │ Source : curation         │  │ │
│ │                           │  │ Extraction #51 masquee   │  │ │
│ │                           │  │ par Jonas — "Phrase de   │  │ │
│ │                           │  │ remplissage, pas un      │  │ │
│ │                           │  │ argument."               │  │ │
│ │                           │  └──────────────────────────┘  │ │
│ └───────────────────────────┴────────────────────────────────┘ │
│                                                                │
│ Legende :                                                      │
│  ░ Texte retire (v1)  ▓ Texte ajoute (v2)                     │
│  📎 = source du changement (extraction + commentaires)         │
│  Texte sans fond = inchange                                    │
│                                                                │
│ Provenance des modifications :                                 │
│  · 2 modifications sourcees (extraction #42, curation #51)     │
│  · 0 modification sans source                                  │
│  · Redaction : humaine / assistee IA (✎ / 🤖)                  │
│                                                                │
│ [Exporter ce diff]  [Retour au texte]                          │
└────────────────────────────────────────────────────────────────┘
```

**Les 3 types de zones dans le diff** :

| Zone | Affichage | Provenance |
|---|---|---|
| **Inchangee** | Texte normal, pas de fond | Pas de source a montrer |
| **Modifiee/ajoutee** | Fond vert, texte v2 a cote du texte v1 | Bloc "📎 Pourquoi" : extraction source + commentaires qui ont motive le changement + statut de debat + qui a redige (humain ✎ ou IA assistee 🤖) |
| **Supprimee** | Fond rouge en v1, vide ou "(passage supprime)" en v2 | Bloc "📎 Pourquoi supprime" : curation (extraction masquee) ou decision explicite dans un commentaire |

**Provenance de la redaction** — qui a ecrit le texte modifie :

Chaque zone modifiee porte un indicateur de provenance de la redaction elle-meme :
- **✎ Redaction humaine** : l'humain a ecrit le texte directement dans le wizard (Etape 5.6, etape 3)
- **🤖 Brouillon IA, valide par l'humain** : l'IA a genere le brouillon (bouton "Pre-remplir par IA"),
  l'humain l'a relu, eventuellement modifie, puis valide. Le texte final peut contenir des passages
  ecrits par l'IA — mais l'humain en porte la responsabilite (il a valide)
- **🤖⚠️ Brouillon IA, non modifie** : l'IA a genere le texte et l'humain l'a valide sans modification.
  Ce n'est pas interdit, mais c'est signale visuellement — le lecteur du diff sait que ce passage n'a
  pas ete reformule par un humain. C'est de la transparence, pas du jugement

Cette distinction est essentielle. Si tout est marque "synthese", personne ne sait si un humain a
vraiment travaille le texte ou si c'est du copier-coller de LLM valide en un clic. La transparence
est la condition de la confiance.

**Compteur de provenance en bas du diff** :
```
Provenance des modifications :
 · 4 modifications sourcees (liens vers extractions et commentaires)
 · 1 modification sans source ⚠️ (a justifier ou sourcer)
 · Redaction : 3 humaines (✎) · 1 IA validee (🤖) · 1 IA non modifiee (🤖⚠️)
```

Ce compteur est le **resume de la qualite du travail deliberatif** sur cette version. Un diff avec
5 modifications sourcees et 0 sans source = tracabilite parfaite. Un diff avec 3 modifications
sans source = des zones ou le travail humain n'a pas ete documente. Ce n'est pas un jugement —
c'est une observation qui aide le facilitateur a decider si la version est prete a etre publiee.

**Actions** :
- [ ] Vue comparaison pleine page : 2 colonnes scrollables en sync (scroll de l'une scroll l'autre)
  - Selecteurs de version en haut (dropdown v1 / v2, avec labels de version)
  - Diff genere par `difflib.SequenceMatcher` au niveau paragraphe (pas au niveau caractere — trop bruyant pour du texte long)
- [ ] **Annotation des zones modifiees avec SourceLinks** :
  - Chaque zone modifiee est associee aux SourceLinks correspondants (Etape 5.1)
  - Le bloc "📎 Pourquoi" s'affiche inline sous la zone modifiee en v2
  - Si aucun SourceLink n'existe → afficher "⚠️ Modification sans source"
- [ ] **Indicateur de provenance de la redaction** :
  - Stocker dans le SourceLink si le texte a ete ecrit par l'humain, pre-rempli par l'IA et modifie, ou pre-rempli par l'IA et non modifie
  - Afficher l'icone correspondante (✎ / 🤖 / 🤖⚠️) sur chaque zone modifiee
- [ ] **Compteur de provenance** en bas du diff : resume statistique des sources et de la redaction
- [ ] **Bouton "Exporter ce diff"** : genere un PDF/HTML du diff avec les annotations de provenance (reutilise le moteur d'export de l'Etape 5.7)
- [ ] **Navigation depuis le diff** : clic sur une extraction dans le bloc "📎 Pourquoi" → ouvre la carte inline dans le texte source (ou le drawer)
- [ ] Le diff est accessible depuis le switcher de versions (Etape 1.2) : bouton "Comparer" entre deux pilules de version

**Fichiers concernes** :
- Extension de `front/views.py` (LectureViewSet — action comparer, enrichit l'Etape 5.3)
- Nouveau template `front/templates/front/includes/comparaison_versions.html`
- `core/models.py` : champ `provenance_redaction` sur SourceLink (`humaine`, `ia_modifiee`, `ia_brute`)
- CSS : styles du diff (fond vert/rouge, blocs de provenance, compteur)

**Tests E2E** :
- [ ] Selectionner V1 et V2 : verifier que le diff s'affiche en 2 colonnes synchronisees
- [ ] Verifier que les zones modifiees ont un bloc "📎 Pourquoi" avec les bonnes sources
- [ ] Verifier qu'une modification sans SourceLink affiche le warning "⚠️ sans source"
- [ ] Verifier les indicateurs de provenance (✎ / 🤖 / 🤖⚠️)
- [ ] Verifier le compteur de provenance en bas du diff
- [ ] Clic sur une source dans le bloc "📎 Pourquoi" → navigation vers l'extraction
- [ ] Export du diff : verifier que le PDF/HTML contient les annotations de provenance

### Tests E2E Phase 5

- [ ] Ajouter commentaire, verifier fil de discussion, indicateur visuel
- [ ] Creer restitution, verifier version et liens SourceLink
- [ ] Vue diff entre deux versions avec provenance
- [ ] Vue "fil de reflexion" complet (navigation source → extraction → commentaire → synthese → version)
- [ ] Wizard de synthese : parcourir les 5 etapes, verifier que les sources sont liees
- [ ] Wizard : verifier que les passages non sources sont marques en warning
- [ ] Wizard : verifier que le bouton "Lancer la synthese" est inaccessible sous le seuil de consensus
- [ ] Export PDF : verifier le rendu visuel (polices, couleurs, mise en page)
- [ ] Export HTML : verifier l'autonomie du fichier et l'interactivite des accordeons
- [ ] Comparaison V1/V2 : verifier le diff, les sources, les indicateurs de provenance (✎/🤖/🤖⚠️)
- [ ] Comparaison : verifier qu'une modification sans source est signalee

---

## 7. Phase 6 — Recherche semantique

> Objectif : retrouver des passages par sens, pas seulement par mots-cles.

### Etape 6.1 — Embeddings et index vectoriel

**Actions** :
- [ ] Ajouter un champ `embedding` (ou table separee) pour chaque Page et/ou extraction
- [ ] Generer les embeddings via le provider LLM actif (ou un modele dedie comme `text-embedding-3-small`)
- [ ] Stocker dans un index vectoriel (options : pgvector si migration PostgreSQL, ou ChromaDB/FAISS en SQLite)
- [ ] Recherche par similarite cosinus

**Fichiers concernes** : nouveau `core/embeddings.py`, `core/models.py`

### Etape 6.2 — Interface de recherche et alignement par hypostases

**Pourquoi une vue dediee** : un champ de recherche dans le header avec des resultats en dropdown ne suffit pas. La recherche semantique cross-documents est une activite a part entiere — pas un accessoire de navigation. L'utilisateur veut explorer sa bibliotheque par concept, par type d'hypostase, par statut de debat. Ca merite une vue pleine page.

De plus, un cas d'usage central a ete identifie par les utilisateurs pilotes (Jean, Ephicentria) : l'**alignement cross-documents par hypostase**. Le principe : prendre N documents sources, regrouper leurs extractions par hypostase, et visualiser un tableau croise qui montre les convergences, les divergences, et les **gaps** (un document ne dit rien sur un concept). Ce tableau est exactement ce que les hypostases permettent naturellement — c'est leur raison d'etre. Aucun outil concurrent ne fait ca.

> Reference : `PLAN/References/exemple alignement.pdf` — Jean a produit manuellement (via Perplexity)
> un alignement entre 3 documents (verbatim eleves, lois d'Asimov-Ephicentria, charte Ostrom-Ephicentria)
> en utilisant 8 hypostases comme cles d'alignement. Chaque hypostase fait le pont entre
> "ce qui est vecu" (verbatim), "ce qui est prescrit" (lois), et "ce qui est organise" (charte).
> Hypostasia doit pouvoir generer ce tableau automatiquement a partir des extractions existantes.

La vue recherche a **deux modes** : recherche filtree et alignement par hypostases.

#### Mode 1 — Recherche filtree

Vue pleine page qui remplace la zone de lecture (meme slot central). Champ de recherche + filtres lateraux + resultats.

```
┌─────────────────────────────────────────────────────┐
│  🔍 "dilemme social Ostrom"                         │
│  ┌───────────────┐  ┌────────────────────────────┐  │
│  │ Filtres        │  │ Resultats                  │  │
│  │               │  │                            │  │
│  │ Type:          │  │ 📄 Debat IA education      │  │
│  │ ☑ Pages       │  │ "...notion de dilemme      │  │
│  │ ☑ Extractions │  │  social..." (score 94%)    │  │
│  │ ☐ Commentaires│  │ PRINCIPE ⚫ CONSENSUEL      │  │
│  │               │  │                            │  │
│  │ Hypostase:     │  │ 📄 Charte numerique        │  │
│  │ ☐ PROBLEME   │  │ "...Ostrom definit..."     │  │
│  │ ☐ VALEUR     │  │ DEFINITION ▷ DISCUTE       │  │
│  │ ☑ PRINCIPE   │  │                            │  │
│  │ ☐ ...        │  │ 💬 Commentaire de Jean      │  │
│  │               │  │ "Voir aussi les travaux    │  │
│  │ Statut:        │  │  d'Ostrom sur..."          │  │
│  │ ☑ Tous        │  │                            │  │
│  │               │  │ 3 resultats / 42 documents │  │
│  │ Dossier:       │  └────────────────────────────┘  │
│  │ ☑ Tous        │                                   │
│  └───────────────┘  [Mode: Recherche | Alignement]   │
└─────────────────────────────────────────────────────┘
```

**Actions recherche filtree** :
- [ ] Vue pleine page accessible depuis un bouton 🔍 dans le header (ou raccourci `/`)
- [ ] Champ de recherche en haut — recherche textuelle immediate, semantique si embeddings disponibles
- [ ] Panneau de filtres a gauche :
  - Type de resultat : Pages, Extractions, Commentaires (checkboxes)
  - Hypostase : liste des 29 hypostases regroupees par famille de couleur (checkboxes). Ex: "toutes les CONJECTURE" ou "toutes les hypostases de la famille Speculatif"
  - Statut de debat : CONSENSUEL, DISCUTABLE, DISCUTE, CONTROVERSE (checkboxes)
  - Dossier : filtrer par dossier de la bibliotheque
  - Document : filtrer par page specifique
- [ ] Chaque resultat affiche : document source, extrait avec match surligne, pastille hypostase coloree (famille), badge statut de debat
- [ ] Clic sur un resultat → navigation vers la page avec le passage mis en evidence (scroll + surlignage)
- [ ] Les filtres sont appliques en HTMX (pas de rechargement de page) — chaque changement de filtre met a jour les resultats
- [ ] Requete sans texte de recherche = navigation par filtres. Ex: cocher uniquement "CONJECTURE" + "DISCUTE" → "montre-moi toutes les conjectures encore en debat dans ma bibliotheque"

#### Mode 2 — Alignement par hypostases (cross-documents)

> **C'est le mode differenciateur du produit.** Il repond a la question :
> "Pour chaque concept (hypostase), que disent mes differents documents ?"
>
> L'alignement rend visible en un coup d'oeil :
> - Les **convergences** : tous les documents parlent du meme PROBLEME
> - Les **divergences** : deux documents ont des VALEUR contradictoires
> - Les **gaps** : un document ne dit rien sur un concept present dans les autres
>
> Les gaps sont aussi precieux que les contenus : "votre charte ne mentionne aucune
> CROYANCE alors que le verbatim des eleves en est plein" est un finding critique.

```
┌──────────────────────────────────────────────────────────────────┐
│  Alignement par hypostases               [Recherche | Alignement]│
│                                                                  │
│  Documents : [Verbatim ×] [Lois Asimov ×] [Charte Ostrom ×] [+]│
│  Hypostases : [8 selectionnees / 29]  [Configurer]               │
│                                                                  │
│  ┌────────────┬──────────────┬──────────────┬──────────────┐     │
│  │ Hypostase  │ Verbatim     │ Lois Asimov  │ Charte Ostrom│     │
│  ├────────────┼──────────────┼──────────────┼──────────────┤     │
│  │            │ Peur de      │ Loi 1 — Ne   │ Art. 2       │     │
│  │ PROBLEME   │ "deficit     │ pas nuire aux│ (usages      │     │
│  │ 🔴         │ cognitif"... │ personnes... │ interdits)...│     │
│  │            │ 📌 2 extr.   │ 📌 1 extr.   │ 📌 2 extr.   │     │
│  ├────────────┼──────────────┼──────────────┼──────────────┤     │
│  │            │ Valeur       │ Loi 1, Loi 3 │ Art. 4, 8, 9 │     │
│  │ VALEUR     │ accordee a   │ (liberte,    │ (ecologie,   │     │
│  │ 🟣         │ la liberte...│ communs)...  │ sobriete)... │     │
│  │            │ 📌 1 extr.   │ 📌 2 extr.   │ 📌 3 extr.   │     │
│  ├────────────┼──────────────┼──────────────┼──────────────┤     │
│  │            │ Usage IA     │ Loi 1 —      │ Art. 2, 4    │     │
│  │ PHENOMENE  │ "meilleur    │ Claude ne    │ (interdiction│     │
│  │ 🟢         │ ami", miroir │ doit pas se  │ usages       │     │
│  │            │ 📌 1 extr.   │ substituer...│ miroir)...   │     │
│  ├────────────┼──────────────┼──────────────┼──────────────┤     │
│  │            │              │              │              │     │
│  │ CONJECTURE │  ── vide ──  │  ── vide ──  │  ── vide ──  │     │
│  │ 🟡  ⚠ GAP │              │              │              │     │
│  ├────────────┼──────────────┼──────────────┼──────────────┤     │
│  │            │ "La planete  │ Loi 3 —      │ Art. 4, 8    │     │
│  │ AXIOME     │ est finie",  │ limites      │ (sobriete,   │     │
│  │ 🔵         │ ressources...│ planetaires..│ logiciels    │     │
│  │            │ 📌 1 extr.   │ 📌 1 extr.   │ libres)...   │     │
│  └────────────┴──────────────┴──────────────┴──────────────┘     │
│                                                                  │
│  Synthese : 5 hypostases couvertes, 1 gap, 0 conflit            │
│  20 extractions alignees sur 3 documents                         │
│                                                                  │
│  [Exporter PDF]  [Exporter Markdown]  [Lancer synthese croisee] │
└──────────────────────────────────────────────────────────────────┘
```

**Actions alignement** :
- [ ] **Selection des documents** : l'utilisateur choisit 2 a 6 documents a aligner (au-dela de 6, le tableau deborde). Selection par picker dans l'arbre ou par recherche
- [ ] **Selection des hypostases** : par defaut, montrer toutes les hypostases qui ont au moins une extraction dans au moins un des documents selectionnes. L'utilisateur peut filtrer (cocher/decocher) pour se concentrer sur certaines familles
- [ ] **Construction du tableau** : pour chaque cellule (hypostase × document), requete `ExtractedEntity.objects.filter(page=document, extraction_text__contains=hypostase)` ou mieux, filtre sur `attr_0` (le champ hypostase dans les attributs d'extraction)
- [ ] **Contenu des cellules** :
  - Si 1 extraction : afficher le debut du resume IA (truncate ~80 chars) en `.typo-machine`
  - Si N extractions : afficher le nombre + le debut de la premiere. Clic → deplier toutes les extractions de cette cellule
  - Si 0 extraction : cellule grisee avec mention "— vide —" et icone ⚠ GAP. Le gap est un finding, pas une absence neutre
- [ ] **Pastille de couleur par hypostase** : la colonne hypostase utilise les couleurs par famille (Etape 1.8). Ca cree un code couleur vertical qui aide au scan
- [ ] **Clic sur une cellule** → popup avec les extractions completes (resume IA en `.typo-machine`, citation source en `.typo-citation`, statut, commentaires). Clic sur "Voir dans le texte" → navigation vers la page avec le passage surligne
- [ ] **Detection des gaps** : les cellules vides sont comptees et resumees en bas. Un gap signifie "ce document ne dit rien sur ce concept". C'est souvent plus revelateur que le contenu
- [ ] **Ligne de synthese en bas** : compteurs (X hypostases couvertes, Y gaps, Z conflits potentiels). Un "conflit potentiel" = meme hypostase mais statuts de debat divergents (ex: CONSENSUEL dans un document, CONTROVERSE dans un autre)
- [ ] **Export** :
  - PDF : tableau formate avec les couleurs d'hypostase et la charte typographique (B612 pour les hypostases, B612 Mono pour les resumes). C'est le livrable qu'on presente aux financeurs, au CA, aux participants d'un atelier
  - Markdown : tableau Markdown avec les extractions completes et liens vers les pages sources
- [ ] **Synthese croisee** (Phase 5+ requise) : bouton "Lancer synthese croisee" → lance le wizard de synthese (Etape 5.6) mais avec les extractions de TOUS les documents alignes, pas d'un seul. L'IA recoit le tableau d'alignement comme contexte et produit une synthese cross-documents

> **Note architecturale** : l'alignement de base (grouper les extractions existantes par hypostase)
> ne necessite PAS les embeddings de l'Etape 6.1. C'est un simple GROUP BY sur les attributs
> d'extraction. Les embeddings enrichissent l'alignement en trouvant des passages *semantiquement
> proches* meme si l'hypostase differe (ex: un PHENOMENE dans un document qui repond a un
> PROBLEME dans un autre). Mais la version de base est implementable des que les extractions
> sont typees — c'est-a-dire des la Phase 1.
>
> **Recommandation** : implementer une version basique de l'alignement dans une Etape 1.12
> (apres la charte et l'onboarding), avec juste le tableau croisant les extractions par hypostase.
> L'Etape 6.2 ajoute la recherche semantique, les scores de similarite, et la detection
> intelligente de conflits. Ca permet de montrer l'alignement aux financeurs des la Phase 1.

**Fichiers concernes** : `front/views.py` (RechercheViewSet a etendre ou nouveau AlignementViewSet), nouveaux templates `front/includes/recherche_resultats.html`, `front/includes/alignement_tableau.html`, `front/includes/alignement_cellule.html`, CSS, `hypostasis_extractor/templatetags/extractor_tags.py` (filtres par hypostase)

### Tests E2E Phase 6

- [ ] Recherche par mot-cle : verifier resultats pertinents avec extraits surligne
- [ ] Recherche semantique : verifier que des resultats apparaissent meme sans mot exact
- [ ] Filtrage par hypostase : cocher "CONJECTURE" → seules les conjectures apparaissent
- [ ] Filtrage par statut : cocher "DISCUTE" → seules les extractions en debat apparaissent
- [ ] Filtrage combine : "CONJECTURE" + "DISCUTE" → "toutes les conjectures encore en debat"
- [ ] Clic sur un resultat → navigation vers la page avec passage surligne
- [ ] Alignement : selectionner 3 documents, verifier le tableau croise
- [ ] Alignement : verifier que les gaps sont affiches et comptes
- [ ] Alignement : clic sur une cellule → popup avec extractions completes
- [ ] Alignement : export Markdown avec tableau et liens sources

---

## 8. Phase 7 — Deep Research automatique

> Objectif : enrichir chaque extraction avec des sources externes verifiees.
> Outil cible : **Local Deep Research** (LDR) — https://github.com/LearningCircuit/local-deep-research
> Licence MIT, ~4k stars, ~95% sur SimpleQA benchmark, disponible sur PyPI (`pip install local-deep-research`).
> Application Flask (port 5000), bases SQLCipher chiffrees par user (AES-256), images Docker signees Cosign.

### Pourquoi Local Deep Research

| Critere | LDR | Perplexity API | SearXNG + LLM maison |
|---------|-----|----------------|----------------------|
| Open-source | Oui (MIT) | Non (API payante) | Oui (mais assemblage manuel) |
| Mode local | Oui (Ollama + SearXNG) | Non (cloud) | Oui |
| Multi-sources | 10+ gratuits (arXiv, PubMed, Semantic Scholar, Wikipedia, Wayback Machine, GitHub, SearXNG) + premium (Tavily, Brave, Google via SerpAPI) + docs prives (RAG) | Web uniquement | Configurable |
| API Python | Oui (`LDRClient`, `quick_query()`) — gere auth/CSRF automatiquement | Oui (REST) | Non (a construire) |
| API REST | Oui (`/api/start_research`, `/api/v1/quick_summary`, `/api/v1/detailed_research`, `/api/report/{id}`) | Oui | Non |
| LLM locaux | Ollama, vLLM, LM Studio + tout endpoint compatible OpenAI | Non | Libre |
| Sortie | Markdown avec citations inline + liste de sources (URL, titre, extrait) | Texte + sources | A definir |
| LLM supportes | Ollama, OpenAI, Google Gemini, Anthropic | GPT uniquement | Libre |
| Securite | SQLCipher (base chiffree par user, AES-256) | Cloud | Libre |

**Choix** : LDR est le meilleur compromis — il combine recherche multi-sources, mode local, API Python native, et citations structurees. Alternative : si LDR est trop lourd ou instable, fallback sur SearXNG + notre propre couche d'abstraction LLM (Phase 3).

### Architecture d'integration

```
Hypostasia                          Local Deep Research
┌──────────────────┐                ┌──────────────────────┐
│ front/tasks.py   │  HTTP REST     │ LDR Server (:5000)   │
│ (Celery task)    │───────────────>│                      │
│                  │  POST          │ ┌──────────────────┐ │
│ "sourcer cette   │  /api/start    │ │ Search engines   │ │
│  extraction"     │  _research     │ │ SearXNG, arXiv,  │ │
│                  │                │ │ PubMed, Brave,   │ │
│                  │  GET           │ │ docs prives      │ │
│                  │<───────────────│ └──────────────────┘ │
│                  │  /api/report/  │ ┌──────────────────┐ │
│                  │  {id}          │ │ LLM (Ollama /    │ │
│                  │                │ │ OpenAI / Gemini) │ │
│ Cree les         │  JSON:         │ └──────────────────┘ │
│ SourceReference  │  - markdown    └──────────────────────┘
│ en base          │  - citations[]
└──────────────────┘  - sources[]
```

**Option A (recommandee)** : LDR tourne comme service Docker a cote de Django. Communication via API REST.
**Option B** : import Python direct via le client officiel dans le worker Celery :
```python
from local_deep_research.api import LDRClient, quick_query
summary = quick_query("user", "pass", "texte de l'extraction")
```
Plus simple mais couple le code et les dependances.

**Limites connues de LDR** :
- Latence elevee (plusieurs minutes pour un rapport complet avec recherche iterative)
- Qualite tres dependante du LLM utilise (GPT-4 >> Llama 7B)
- Auth obligatoire depuis v1.0 (friction pour usage purement local)
- Parsing de pages web dynamiques/complexes parfois incomplet

### Etape 7.1 — Modele de donnees et service de recherche

**Actions** :
- [ ] Creer un modele `SourceReference` dans `core/models.py` :
  - `extraction` (FK ExtractedEntity) — l'extraction qu'on cherche a sourcer
  - `url` — URL de la source trouvee
  - `titre` — titre de la page/article source
  - `extrait` — passage pertinent extrait de la source
  - `score_pertinence` — score de pertinence (0-1) retourne par LDR
  - `type_source` — `web`, `arxiv`, `pubmed`, `wikipedia`, `document_prive`
  - `date_recherche` — timestamp de la recherche
  - `rapport_complet` — texte Markdown du rapport LDR (stocke une fois par recherche)
- [ ] Creer `core/deep_research.py` — service qui appelle LDR :
  - `lancer_recherche(texte_extraction, contexte_page) -> research_id`
  - `recuperer_rapport(research_id) -> {markdown, citations[], sources[]}`
  - `parser_citations(rapport) -> list[SourceReference]`
- [ ] Gerer le fallback si LDR n'est pas disponible (warning, pas d'erreur bloquante)

**Fichiers concernes** : `core/models.py`, nouveau `core/deep_research.py`, migration

### Etape 7.2 — Tache Celery et integration front (sources dans les cartes)

**Argumentaire** : les sources Deep Research doivent etre integrees **dans la carte d'extraction elle-meme**,
pas dans un panneau separe. Raisons :
- Creer un "panneau de sources" separe ajouterait une 4e couche d'information dans une interface deja dense
  (arbre + lecture + extractions). L'utilisateur devrait naviguer entre panneau d'extractions et panneau de sources.
- L'information reste **contextuelle** : les sources sont lues la ou l'extraction est affichee.
- Le pattern accordion (section depliable) est deja utilise pour les cartes compactes (Etape 1.8).
- Compatible avec le mode focus (Etape 1.11) : le popup inline peut aussi montrer les sources.
- **Argument academique** : pour un chercheur, voir une extraction + ses sources dans la meme carte
  revient a un apparat critique integre — c'est le standard attendu en recherche.

**Mockup — Carte avec sources depliees** :

```
┌─────────────────────────────────────┐
│ CONJECTURE                          │
├─────────────────────────────────────┤
│ L'IA generative va transformer      │
│ les metiers creatifs en metiers     │
│ de supervision.                      │
│                                     │
│ « Je pense que dans 5 ans, on      │
│   ne dessinera plus, on pilotera » │
├─────────────────────────────────────┤
│ ● DISCUTE    #ia #metiers          │
│                          📎 3 ▾    │  ← clic pour deplier
├─────────────────────────────────────┤
│ ┊ Sources Deep Research :           │
│ ┊                                   │
│ ┊ 📄 McKinsey 2024 — "Generative   │
│ ┊    AI and the future of work"     │
│ ┊    → 30% des taches creatives...  │
│ ┊    ★★★ pertinence haute           │
│ ┊                                   │
│ ┊ 📄 MIT Tech Review — "AI won't   │
│ ┊    replace artists but..."        │
│ ┊    → Nuance sur la supervision... │
│ ┊    ★★☆ pertinence moyenne         │
│ ┊                                   │
│ ┊ 📄 Rapport France Strategie 2025  │
│ ┊    → Donnees emploi secteur...    │
│ ┊    ★★★ pertinence haute           │
│ ┊                                   │
│ ┊ [Voir le rapport complet]         │
└─────────────────────────────────────┘
```

**Actions** :
- [ ] Tache Celery `sourcer_extraction_task(entity_id)` :
  1. Recupere l'extraction et son contexte (page, commentaires)
  2. Construit la requete de recherche (extraction_text + attributs + contexte)
  3. Appelle LDR via API REST (POST `/api/start_research`)
  4. Polling du statut (GET `/api/research/{id}/status`) avec timeout 2 minutes
  5. Recupere le rapport (GET `/api/report/{id}`)
  6. Parse les citations et cree les `SourceReference` en base
- [ ] Bouton "Sourcer" sur chaque carte d'extraction (inline ou dans le drawer vue liste)
- [ ] Indicateur visuel : badge `📎 N` dans le footer de la carte (a cote du statut de debat)
- [ ] Section depliable dans la carte (accordion) : liste des sources avec titre, URL, extrait, score de pertinence (etoiles)
- [ ] Lien "Voir le rapport complet" en bas de la section → modale avec le Markdown LDR
- [ ] En mode focus (Etape 1.11) : le popup inline inclut aussi la section sources si elle existe

**Fichiers concernes** : `front/tasks.py`, `front/views.py` (ExtractionViewSet), templates `front/includes/`

### Etape 7.3 — Recherche dans les documents prives

**Probleme** : LDR peut chercher dans des documents locaux (RAG). C'est pertinent pour Hypostasia : sourcer une extraction en cherchant dans les autres pages de la bibliotheque.

**Actions** :
- [ ] Configurer LDR pour indexer les pages Hypostasia comme corpus de documents prives
- [ ] Option 1 : exporter les pages en fichiers Markdown dans un dossier que LDR indexe
- [ ] Option 2 : utiliser l'API de LDR pour ajouter des documents au vecteur store (FAISS/Chroma)
- [ ] Quand une source est trouvee dans un document prive → lien interne vers la page Hypostasia

**Fichiers concernes** : `core/deep_research.py`, configuration LDR

### Etape 7.4 — Configuration et mode local

**Actions** :
- [ ] Page de configuration LDR dans le front : URL du serveur LDR, modele LLM, moteurs de recherche actifs
- [ ] En mode local (Phase 9) : LDR tourne sur le meme boitier, avec Ollama et SearXNG locaux
- [ ] Flag `DEEP_RESEARCH_ENABLED` dans settings.py (desactive par defaut, activable dans la config IA)

**Fichiers concernes** : `hypostasia/settings.py`, `front/views.py` (ConfigurationIAViewSet), `docker-compose.yml`

### Dependances

- **Phase 3 (Providers IA)** : LDR utilise ses propres providers, mais la config LLM peut etre alignee
- **Phase 6 (Recherche semantique)** : les embeddings de Phase 6 peuvent alimenter le corpus prive de LDR
- **Phase 9 (Mode local)** : LDR + Ollama + SearXNG = recherche 100% locale

### Tests E2E Phase 7

- [ ] Bouton "Sourcer" avec LDR mock → verifier creation des SourceReference
- [ ] Affichage de la section de sources dans les cartes d'extraction (accordion depliable) avec extraits et scores
- [ ] Recherche dans les documents prives (page Hypostasia comme source)

---

## 9. Phase 8 — Transcription temps reel et prise de notes live

> Objectif : permettre l'enregistrement audio en direct (reunion, cours, entretien),
> la transcription en temps reel affichee dans l'interface, et l'edition collaborative
> des notes par un humain pendant que la transcription tourne.

> **Note strategique** : cette phase est un side-projet a prototyper en fablab. L'idee
> est fondamentale pour le positionnement produit et a deja interesse des financeurs.
> Le MVP (etape 8.1) doit fonctionner rapidement pour demontrer la faisabilite.
> Les etapes suivantes (8.2-8.5) sont des extensions progressives.
>
> **Design** : la vue transcription doit suivre le mockup Yves (`Retour design Yves/DEBAT transcription - ex.pdf`) :
> noms de locuteurs en gras avec timestamps, texte en italique, surlignages colores
> pour les extractions (vert/jaune), annotations en marge. Le texte humain (corrections,
> notes du preneur de notes) utilise `.typo-lecteur` (Srisakdi bleu `#0056D6`) pour se
> distinguer du texte transcrit automatiquement (`.typo-machine`, B612 Mono neutre).

### MVP — Etape 8.1 — Capture audio et transcription par chunks (sans WebSocket)

**Objectif MVP** : un bouton "Enregistrer" dans le navigateur, des chunks audio envoyes toutes les 30s par POST classique, transcrits par le provider existant, affiches par polling HTMX. Pas de WebSocket, pas de SSE, pas d'edition live — juste la preuve que ca marche.

**Actions MVP** :
- [ ] Bouton Start/Stop dans un partial HTMX (pas de Pause pour le MVP)
- [ ] Capture audio via `MediaRecorder` API — format WebM/Opus
- [ ] Envoi de chaque chunk par POST multipart toutes les 30s vers une action `ImportViewSet.chunk_audio`
- [ ] Cote serveur : chaque chunk est transcrit par le provider actif (Voxtral ou Whisper)
- [ ] Les segments transcrits sont appended au `TranscriptionJob.raw_result`
- [ ] Polling HTMX toutes les 3s (meme mecanisme que l'import audio existant) pour afficher les nouveaux segments
- [ ] Bouton "Terminer" → assemble les chunks en fichier final, page passe en mode lecture

**Fichiers concernes** : nouveau JS `front/static/front/js/enregistrement_live.js`, `front/views.py` (ImportViewSet), templates

### Extension — Etape 8.2 — Indicateurs et Pause

**Actions** :
- [ ] Bouton Pause/Resume en plus de Start/Stop
- [ ] Indicateur visuel d'enregistrement (duree, niveau sonore, statut)
- [ ] Sauvegarde du fichier audio complet dans `source_file` pour re-ecoute ulterieure
- [ ] Format WAV en option (meilleure qualite pour re-transcription)

**Fichiers concernes** : `front/static/front/js/enregistrement_live.js`, templates

### Extension — Etape 8.3 — Transcription streaming

**Actions** :
- [ ] Envoyer chaque chunk audio au provider de transcription des reception (pas attendre la fin)
- [ ] Pour Voxtral/Mistral : verifier si l'API supporte le streaming ou chunking
- [ ] Pour Whisper (OpenAI) : utiliser l'endpoint de transcription en mode chunk
- [ ] Pour Ollama local (whisper.cpp) : transcription en quasi-temps reel
- [ ] Stocker les segments transcrits incrementalement dans `TranscriptionJob.raw_result`
- [ ] Diffuser les nouveaux segments au front via WebSocket (django-channels) ou SSE (Server-Sent Events)

**Choix technique** :
- Option A : **WebSocket via django-channels** — bidirectionnel, adapte si edition collaborative en meme temps
- Option B : **SSE (Server-Sent Events)** — plus simple, unidirectionnel (serveur → client), suffisant si l'edition passe par HTMX classique
- Recommandation : commencer par SSE (plus simple), migrer vers WebSocket si besoin de collab temps reel

**Fichiers concernes** : `front/tasks.py` (nouvelle tache ou adaptation de `transcrire_audio_task`), `front/services/transcription_audio.py`, nouveau `front/consumers.py` si WebSocket

### Extension — Etape 8.4 — Affichage live de la transcription

**Actions** :
- [ ] Zone de lecture en mode "live" : les segments apparaissent au fur et a mesure
- [ ] Auto-scroll vers le dernier segment (desactivable par l'utilisateur)
- [ ] Indicateur de locuteur avec couleur (meme systeme que transcription classique)
- [ ] Timestamps en temps reel
- [ ] Transition fluide : quand l'enregistrement s'arrete, la page passe en mode lecture normal

**Fichiers concernes** : nouveau template `front/includes/transcription_live.html`, JS live

### Extension — Etape 8.5 — Edition collaborative pendant la transcription

**Probleme** : un humain doit pouvoir corriger le texte, renommer un locuteur, ou ajouter des notes pendant que la transcription continue a arriver.

**Actions** :
- [ ] Chaque bloc de transcription est editable inline (meme mecanisme que `editer_bloc`) pendant le live
- [ ] Les modifications humaines sont marquees comme telles (flag `edited_by_human`)
- [ ] Les nouveaux segments arrivent en append — ils ne touchent pas les segments deja edites
- [ ] Zone de "notes libres" attachee a la page, editable en parallele de la transcription
- [ ] Si multi-user (Phase 2) : les modifications d'un user sont diffusees aux autres en temps reel

**Fichiers concernes** : `front/views.py`, `core/models.py` (flag sur segments ou modele `NoteLibre`), templates, JS

### Extension — Etape 8.6 — Finalisation et post-traitement

**Actions** :
- [ ] Bouton "Terminer l'enregistrement" → assemble tous les chunks en fichier final
- [ ] Re-transcription optionnelle du fichier complet (meilleure qualite que chunk par chunk)
- [ ] Merge des edits humains avec la transcription finale (les edits humains ont priorite)
- [ ] La page passe en mode lecture classique avec toutes les fonctionnalites (extraction, commentaires, etc.)

**Fichiers concernes** : `front/tasks.py`, `front/views.py`, `front/services/transcription_audio.py`

### Dependances

- **Phase 3 (Providers IA)** : necessaire pour avoir plusieurs providers de transcription (Whisper streaming, Voxtral, local)
- **Phase 2 (Users)** : necessaire pour l'edition collaborative multi-user
- **Phase 5 (Collab)** : le mecanisme d'historique des modifications s'applique aussi ici

### Tests E2E Phase 8

- [ ] Enregistrement audio mock → verifier que les chunks arrivent au serveur
- [ ] Segments de transcription qui apparaissent en live (SSE ou polling)
- [ ] Edition d'un bloc pendant que la transcription continue
- [ ] Finalisation : la page passe en mode lecture classique

---

## 10. Phase 9 — Mode 100% local et hors-ligne

> Objectif : deployer Hypostasia sur un boitier physique (Raspberry Pi, NUC, mini-PC)
> qui cree son propre reseau WiFi isole. Les participants se connectent au WiFi,
> ouvrent le navigateur, et utilisent l'app sans aucune connexion internet.
> Garantie de confidentialite totale : zero donnee ne quitte le reseau local.

> **Note strategique** : cette phase est un side-projet a prototyper en fablab.
> L'idee du boitier confidentiel est fondamentale pour le positionnement aupres
> de certains financeurs (collectivites, ESS, juridique). Le MVP (etape 9.1 + 9.2)
> est un `docker-compose` qui tourne sur un laptop sans internet. Le hardware
> (etapes 9.3-9.5) vient apres validation du concept.

### Cas d'usage

- Reunion confidentielle (CA, comite de direction, negociation)
- Atelier participatif en zone sans internet (terrain, rural)
- Formation ou cours avec prise de notes collaborative
- Contexte juridique ou medical ou les donnees ne doivent pas transiter sur internet

### MVP — Etape 9.1 — Audit des dependances reseau

**Probleme** : l'app actuelle depend de services externes a plusieurs niveaux.

| Composant | Dependance internet | Alternative locale |
|-----------|--------------------|--------------------|
| Tailwind CSS | CDN (`cdn.tailwindcss.com`) | Build local ou fichier CSS pre-compile |
| HTMX | CDN ou fichier local ? | Verifier — doit etre un fichier statique local |
| LLM extraction | API Google Gemini / OpenAI | Ollama local (llama3, mistral, phi3) |
| LLM reformulation/restitution | API Google / OpenAI | Ollama local |
| Transcription audio | API Voxtral (Mistral) | whisper.cpp ou faster-whisper local |
| Embeddings (Phase 6) | API OpenAI/Google | Modele local via Ollama ou sentence-transformers |
| Deep Research (Phase 7) | Recherche web | LDR local avec Ollama + SearXNG (si installe), sinon desactive |

**Actions** :
- [ ] Verifier que l'etape 1.5 (assets statiques locaux) a ete completee — prerequis
- [ ] Tester l'app avec `ALLOWED_HOSTS = ["*"]` et sans acces internet
- [ ] Identifier toute dependance reseau residuelle non couverte par l'etape 1.5

**Fichiers concernes** : `hypostasia/settings.py`, templates (base, bibliotheque), `front/static/`

### MVP — Etape 9.2 — Stack IA 100% locale

**Actions** :
- [ ] Ollama comme provider LLM obligatoire en mode local (Phase 3 prerequis)
- [ ] Whisper local (whisper.cpp ou faster-whisper) pour la transcription audio
- [ ] Prevoir un flag `MODE_LOCAL = True` dans settings.py qui :
  - Desactive les providers cloud (Google, OpenAI, Anthropic, Voxtral)
  - N'affiche que les modeles Ollama dans la config IA
  - Deep Research : LDR local si installe (Ollama + SearXNG), sinon desactive
  - Affiche un bandeau "Mode confidentiel — aucune donnee ne quitte ce reseau"
- [ ] Script d'installation des modeles Ollama (`ollama pull llama3`, `ollama pull mistral`)
- [ ] Script d'installation du modele Whisper local
- [ ] **MVP validable** : `docker-compose -f docker-compose.local.yml up` sur un laptop sans internet → l'app demarre, on peut importer un fichier, lancer une analyse Ollama, commenter. Ca suffit pour demontrer la faisabilite aux financeurs.

**Fichiers concernes** : `hypostasia/settings.py`, `core/models.py` (filtrage providers), `core/llm_providers.py`, templates, nouveau `docker-compose.local.yml`

### Extension fablab — Etape 9.3 — Hardware et reseau WiFi isole

**Architecture cible** :

```
┌─────────────────────────────────────┐
│  Boitier Hypostasia (NUC / RPi 5)  │
│                                      │
│  ┌──────────┐  ┌──────────────────┐ │
│  │ hostapd  │  │ Django + Gunicorn│ │
│  │ (WiFi AP)│  │ + Celery worker  │ │
│  └──────────┘  └──────────────────┘ │
│  ┌──────────┐  ┌──────────────────┐ │
│  │ dnsmasq  │  │ Ollama (LLM)     │ │
│  │ (DHCP)   │  │ + Whisper local  │ │
│  └──────────┘  └──────────────────┘ │
│  ┌──────────┐  ┌──────────────────┐ │
│  │ nginx    │  │ SQLite (DB)      │ │
│  │ (static) │  │                  │ │
│  └──────────┘  └──────────────────┘ │
└─────────────────────────────────────┘
        │ WiFi (ex: "Hypostasia-Secure")
        │ Pas de passerelle internet
   ┌────┴────┐  ┌────┴────┐  ┌────┴────┐
   │ PC 1    │  │ PC 2    │  │ Tel 3   │
   │ Chrome  │  │ Firefox │  │ Safari  │
   └─────────┘  └─────────┘  └─────────┘
```

**Actions** :
- [ ] Script de configuration hostapd (point d'acces WiFi sans passerelle internet)
- [ ] Script de configuration dnsmasq (DHCP + DNS local → `hypostasia.local`)
- [ ] Configuration nginx pour servir les fichiers statiques + proxy vers gunicorn
- [ ] Supervisord etendu : gunicorn + celery + ollama
- [ ] Portail captif optionnel : redirection automatique vers `http://hypostasia.local/`

**Fichiers concernes** : nouveau dossier `deploy/local-box/` avec scripts et configs

### Extension fablab — Etape 9.4 — Image deployable

**Actions** :
- [ ] Dockerfile adapte pour ARM64 (Raspberry Pi 5) et x86_64 (NUC/mini-PC)
- [ ] Docker Compose avec services : django, celery, ollama, nginx
- [ ] Script `setup-box.sh` : installe le systeme, configure WiFi AP, deploie les conteneurs
- [ ] Documentation : liste du materiel recommande, procedure de premiere mise en route
- [ ] Prevoir un mode "valise" : le boitier s'allume, le WiFi demarre, l'app est prete en < 2 minutes

**Materiel recommande** :
- **Option economique** : Raspberry Pi 5 (8 Go RAM) + adaptateur WiFi USB — LLM limite (phi3, tinyllama)
- **Option performante** : Intel NUC / Beelink mini-PC (32 Go RAM, iGPU) — LLM correct (llama3 8B, mistral 7B)
- **Option GPU** : Mini-PC avec GPU Nvidia (ex: Minisforum avec RTX 4060) — LLM performant + Whisper rapide

**Fichiers concernes** : `deploy/local-box/`, `Dockerfile`, `docker-compose.yml`, `supervisord.conf`

### Extension fablab — Etape 9.5 — Securite du reseau local

**Actions** :
- [ ] WiFi avec mot de passe WPA2/WPA3 (configurable au premier demarrage)
- [ ] HTTPS auto-signe (mkcert) pour eviter les warnings navigateur sur le reseau local
- [ ] Pas de route vers internet (iptables : DROP FORWARD, pas de NAT)
- [ ] Login obligatoire sur l'app (Phase 2 prerequis)
- [ ] Option de chiffrement de la base SQLite (SQLCipher) pour protection si vol du boitier
- [ ] Bouton "Purger toutes les donnees" accessible a l'admin (nettoyage post-reunion)

**Fichiers concernes** : `deploy/local-box/`, `hypostasia/settings.py`

### Dependances

- **Phase 3 (Providers IA)** : Ollama backend obligatoire
- **Phase 2 (Users)** : authentification pour le multi-user en reseau local
- **Phase 8 (Live audio)** : transcription temps reel en local via Whisper
- **Phase 5 (Collab)** : edition collaborative sur le meme reseau

### Tests E2E Phase 9

- [ ] App fonctionnelle sans acces internet (toutes les ressources statiques locales)
- [ ] Analyse avec Ollama local (mock ou vrai Ollama en CI)
- [ ] Bandeau "Mode confidentiel" affiche quand `MODE_LOCAL=True`

---

## 11. Regles transverses

Ces regles s'appliquent a TOUTES les phases :

1. **Chaque etape = 1 session Claude Code** : decoupage en taches qui tiennent dans une session (~30min de code max)
2. **Stack CCC obligatoire** : ViewSet explicite, DRF Serializers, HTMX partials, commentaires FR/EN, noms verbeux
3. **Pas de sur-ingenierie** : on resout le probleme pose, rien de plus
4. **Tests avant merge** : au minimum `uv run python manage.py check` + test manuel du flux modifie. Les tests E2E Playwright sont ecrits au fil des phases, pas dans une phase separee
5. **Migration explicite** : si un modele change, creer la migration dans la meme etape
6. **GUIDELINES.md fait foi** : en cas de doute, c'est la spec de reference
7. **Ce fichier est mis a jour** : chaque etape terminee est cochee, chaque nouvelle idee est ajoutee dans la bonne phase
8. **Export et portabilite des donnees** : chaque fonctionnalite qui stocke des donnees utilisateur doit prevoir un export (Markdown, JSON). Backup de la base SQLite documente. Conformite RGPD (droit a l'effacement, droit a la portabilite)
9. **Observabilite** : logging structure (django logging existant dans `logs/`), health check endpoint, monitoring des taches Celery (jobs en echec, timeouts)
10. **Dark mode ready** : toutes les couleurs utilisees dans le CSS et les templates doivent passer par des CSS custom properties (`var(--xxx)`), jamais de hex en dur. Cela garantit qu'un theme dark pourra etre ajoute sans refactoring (un seul bloc `@media (prefers-color-scheme: dark)` a ajouter). Voir Etape 1.8, section "compatibilite dark mode"
11. **Modele economique** : a clarifier avant la mise en prod. Options envisagees :
    - *Cle API utilisateur* : chaque user fournit sa propre cle OpenAI/Gemini/Anthropic (zero cout serveur IA)
    - *Abonnement SaaS* : hebergement + quotas d'appels LLM inclus (necessite multi-tenant)
    - *Auto-heberge* : l'organisation deploie sa propre instance (modele open-core ou licence commerciale)
    - *Mode local* : vente du boitier physique (hardware + logiciel pre-installe) ou licence pour l'image deployable
    - Le choix impacte l'architecture (multi-tenant ou non, quotas, facturation, gestion des cles API)

---

## Priorite suggeree

```
Phase 1  (Socle + refonte layout + charte visuelle + raccourcis + mobile + heat map + notifications + alignement basique) ████████░░  — Prerequis a tout (inclut PostgreSQL, Playwright, design Yves, etats interactifs, rythme transcription)
Phase 3  (Providers IA)       ███████░░░  — Debloque beaucoup de valeur
Phase 2  (Users)              ██████░░░░  — Necessaire pour prod multi-user
Phase 4  (Prompts)            █████░░░░░  — Ameliore l'UX d'analyse
Phase 5  (Collab + traçabilite) ████░░░░░░  — Coeur du produit, apres les users
Phase 8  (Live audio)         ████░░░░░░  — Apres providers IA + users + collab
Phase 9  (Mode local)         ████░░░░░░  — Apres providers IA + users (produit separe ?)
Phase 6  (Recherche)          ███░░░░░░░  — Feature avancee (necessite PostgreSQL + pgvector)
Phase 7  (Deep Research)      ██░░░░░░░░  — Feature avancee, necessite Phase 6
```

> Les tests E2E Playwright sont integres dans chaque phase, pas dans une phase separee.
> La charte visuelle Yves (Etape 1.8) est dans la Phase 1 car elle pose les bases typographiques
> et les couleurs par famille d'hypostase utilisees dans toutes les phases suivantes.
