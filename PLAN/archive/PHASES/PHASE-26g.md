# PHASE-26g — Hub d'analyse dans le drawer (panneau E)

**Complexite**: L | **Mode**: Normal | **Prerequis**: PHASE-10, PHASE-23, PHASE-24

## 1. Contexte

Le bouton "Analyser" dans la navbar et le panneau "Extractions" (E) faisaient doublon.
Quand l'utilisateur cliquait "Analyser", la zone de lecture disparaissait pour afficher
la confirmation — c'etait perturbant. Le terme "Extraction" etait du jargon technique.

Cette phase consolide tout dans le panneau E : l'utilisateur ouvre E, lance l'analyse,
voit la progression et les resultats arriver — sans jamais quitter le texte.

## 2. Objectifs realises

### 2.1 Les 4 etats du drawer

Le panneau passe d'un etat a l'autre, chaque etat remplace le precedent dans `#drawer-contenu` :

| Etat | Contenu | Declencheur |
|------|---------|-------------|
| 1 — Pas d'analyse | CTA "Lancer une analyse" + empty state | Ouverture du drawer sur page sans analyse |
| 2 — Confirmation | Analyseur, cout, prompt, boutons Annuler/Lancer | Clic "Lancer une analyse" ou "Nouvelle analyse" |
| 3 — En cours | Barre de progression WS + cartes qui arrivent une par une | Clic "Lancer" dans la confirmation |
| 4 — Termine | Bandeau resume + bouton "Nouvelle analyse" + cartes | Fin de l'analyse (signal WS) |

### 2.2 Renommage et nettoyage

- Bouton toolbar "Extractions" renomme en "Analyses"
- Titre du drawer renomme en "Analyses"
- Bouton "Analyser" dans la navbar supprime (doublon)
- Drawer elargi de 32rem a 36rem
- `aria-label` du drawer mis a jour

### 2.3 Progression 100% WebSocket (zero polling HTTP)

- La barre de progression est mise a jour par WebSocket (`analyse_progression`)
- Les cartes d'extraction arrivent par WebSocket (`extraction_carte`)
- Le texte annote se met a jour progressivement par WebSocket (OOB `#readability-content`)
- La fin du job est signalee par un nouveau type WS `analyse_terminee` qui injecte un `hx-trigger="load"` pour charger le drawer final
- **Zero requete HTTP de polling** pendant l'analyse

### 2.4 Estimation de cout precise

- Utilise le vrai `QAPromptGenerator` de LangExtract pour mesurer l'overhead prompt par chunk
- Formule affichee : `N_chunks x overhead + texte_source`
- Integre les tokens de thinking (Gemini 2.5 Flash/Pro) avec multiplicateur x5
- Note explicative sur le thinking facture au tarif output

### 2.5 Detection des jobs bloques

- Fonction `_verifier_et_nettoyer_job_bloque()` appliquee dans les 3 points d'entree :
  `drawer_contenu`, `analyse_status`, `previsualiser_analyse`
- Delai de timeout : 5 minutes sans progression (`updated_at` inchange)
- Le job bloque est marque en erreur et le drawer affiche les resultats

### 2.6 Badges hypostases colores dans le drawer

- Le drawer utilise maintenant les memes badges colores que `_card_body.html`
- Filtres `split_comma` + `hypostase_famille` avec variables CSS `--hypostase-*-bg/text`

## 3. Fichiers modifies

### Templates
| Fichier | Changement |
|---------|------------|
| `front/templates/front/base.html` | Supprime bouton Analyser, renomme "Analyses", elargi 36rem |
| `front/templates/front/includes/lecture_principale.html` | Supprime OOB du bouton Analyser |
| `front/templates/front/includes/drawer_vue_liste.html` | Bandeau resume (etat 4), CTA HTMX (etat 1), badges colores, OOB titre |
| `front/templates/front/includes/confirmation_analyse.html` | Refonte pour le drawer : cibles `#drawer-contenu`, boutons pastel, thinking tokens |
| `front/templates/front/includes/panneau_analyse_en_cours.html` | Zero polling, barre WS, OOB titre |
| `front/templates/front/includes/extraction_results.html` | Bouton Reessayer en HTMX |
| `front/templates/front/includes/ws_analyse_progression.html` | Affiche chunks + barre animee stries |

### Views (`front/views.py`)
| Methode | Changement |
|---------|------------|
| `previsualiser_analyse` | Estimation LangExtract reelle + thinking, timeout jobs bloques |
| `analyser` | Retourne dans le drawer, `HX-Trigger: ouvrirDrawer` |
| `analyse_status` | Retourne drawer complet + OOB texte, timeout jobs bloques |
| `drawer_contenu` | Detecte les jobs en cours/bloques |
| `_verifier_et_nettoyer_job_bloque` | Nouvelle fonction utilitaire timeout 5 min |

### Models (`core/models.py`)
| Changement |
|------------|
| `MULTIPLICATEUR_THINKING` : table des multiplicateurs thinking par modele |
| `multiplicateur_thinking()` : methode qui retourne le multiplicateur |

### Tasks (`front/tasks.py`)
| Changement |
|------------|
| Compteur `numero_chunk_courant` dans le callback |
| Envoi `chunk_courant` et `chunks_total` dans `analyse_progression` WS |
| Envoi `analyse_terminee` via NotificationConsumer en fin de job (succes et erreur) |

### Consumers (`front/consumers.py`)
| Changement |
|------------|
| `analyse_terminee` : nouveau handler qui injecte un OOB `hx-trigger="load"` |
| `analyse_progression` : passe `chunk_courant` et `chunks_total` au template |

### JavaScript
| Fichier | Changement |
|---------|------------|
| `front/static/front/js/hypostasia.js` | `ouvrirPanneauDroit()` delegue au drawer, listener `ouvrirDrawer` |
| `front/static/front/js/drawer_vue_liste.js` | Header doc mis a jour |

### CSS
| Fichier | Changement |
|---------|------------|
| `front/static/front/css/hypostasia.css` | Animation `animate-progres-actif` (stries animees) |

## 4. Cas limites geres

| Situation | Comportement |
|-----------|-------------|
| Drawer ferme pendant l'analyse | WS messages silencieusement ignores (OOB sur element absent = no-op). Le texte continue d'etre annote. A la reouverture, `drawer_contenu` detecte le job en cours → Etat 3 |
| F5 pendant l'analyse | `retrieve()` charge la page. Le drawer n'est pas ouvert. L'utilisateur ouvre E → `drawer_contenu` detecte le job → Etat 3 |
| Analyse deja faite, user veut relancer | Bouton "Nouvelle analyse" dans Etat 4 → charge confirmation (Etat 2) |
| Changement de page pendant l'analyse | Le drawer se recharge avec la nouvelle page. L'ancienne analyse continue en background. Les WS ciblent des IDs absents → silencieusement ignores |
| Job bloque (crash Celery, 503 API) | `_verifier_et_nettoyer_job_bloque` detecte l'inactivite > 5 min, marque le job en erreur, affiche les resultats |

## 5. Impact sur les phases futures

### PHASE-26b (Gestion analyseurs + couts)
L'etape 4.2 (calcul des couts fiabilise) est **partiellement realisee** :
- [x] Estimation precise par chunk avec le vrai pipeline LangExtract
- [x] Integration des tokens de thinking dans l'estimation
- [x] Affichage transparent de la formule dans la confirmation
- [ ] Stocker les tokens reels consommes (retour API) — reste a faire
- [ ] Dashboard cumulatif des couts — reste a faire

### PHASE-10 (Drawer)
Le drawer est maintenant un **hub d'analyse** (4 etats) et non plus une simple liste d'extractions.
La largeur a ete elargie de 32rem a 36rem pour accommoder la confirmation d'analyse.

### PHASE-23 (Playwright E2E)
Les tests E2E qui cliquaient `#btn-toolbar-analyser` sont obsoletes.
Le flux de test doit desormais : ouvrir le drawer (E) → cliquer "Lancer une analyse" → voir la confirmation.
