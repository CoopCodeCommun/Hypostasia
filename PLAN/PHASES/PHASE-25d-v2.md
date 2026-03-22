# PHASE-25d-v2 — Explorer : refonte UX recherche + preview + permissions

**Complexite** : L | **Mode** : `/plan` d'abord | **Prerequis** : PHASE-25d (terminee)

---

## 1. Contexte

La page `/explorer/` (PHASE-25d) est fonctionnelle mais basique :
elle liste les dossiers publics, permet de filtrer par nom ou auteur,
et d'en suivre certains. Quatre ameliorations UX ont ete identifiees
pour en faire un vrai outil de decouverte.

Cette phase est **independante** de la Phase 6 (recherche semantique +
alignement par hypostases) prevue dans le PLAN. Elle ameliore
l'Explorer existant sans toucher a l'architecture embeddings/pgvector.
La Phase 6 pourra s'appuyer sur cette base amelioree.

---

## 2. Objectifs precis

### 2.0 — Integrer l'Explorer dans le layout principal (prioritaire)

**Probleme constate en exploration live** :
L'Explorer est une **page standalone isolee** (`explorer_page.html` = `<!DOCTYPE html>`
complet avec sa propre `<nav>`). Quand on y accede, on perd :
- La toolbar principale (Dashboard, Analyses, Lecture, Debat, raccourcis)
- La sidebar bibliotheque (arbre des dossiers)
- Le drawer d'analyse
- Le systeme de toast de la biblio
- La coherence visuelle (layout different, nav minimale)

C'est une **rupture de contexte** majeure. L'utilisateur quitte mentalement
l'application pour atterrir sur une page deconnectee. Le retour se fait
uniquement via le lien "Hypostasia" en haut a gauche.

**Solution** : l'Explorer doit s'afficher **dans la zone de lecture** du layout
principal (`#zone-lecture` de `bibliotheque.html`), exactement comme les
pages de lecture, le dashboard ou l'onboarding.

```
┌──────────────────────────────────────────────────────┐
│ [=] Hypostasia  Dashboard  Analyses  Lecture  Debat  │  ← toolbar conservee
├───────────┬──────────────────────────────────────────┤
│ Arbre     │  Explorer les dossiers publics           │  ← dans #zone-lecture
│ Mes dos.  │                                          │
│  > Demo   │  [Rechercher...]  [Auteur ▼]  [Tri ▼]   │
│  > Gouv.  │                                          │
│  > Mes im │  ┌ Dossier X ───────────── [Suivre] ┐   │
│           │  │ par alice · 5 p. · 12/03          │   │
│           │  └───────────────────────────────────┘   │
│           │  ┌ Dossier Y ───────────── [Suivre] ┐   │
│ [Explorer]│  │ par bob · 3 p. · 10/03            │   │
│           │  └───────────────────────────────────┘   │
└───────────┴──────────────────────────────────────────┘
```

**Design : onglets sur la page d'accueil**

La home actuelle (`onboarding_vide.html`) affiche les 4 etapes + statuts +
raccourcis. L'idee : ajouter **deux onglets** en haut de cette zone d'accueil :

```
     [ Decouvrir l'app ]    [ Explorer les dossiers ]
     ─────────────────      ──────────────────────────

     (contenu de l'onglet actif)
```

- **"Decouvrir l'app"** = le contenu onboarding actuel (4 etapes, statuts, raccourcis)
- **"Explorer les dossiers"** = barre de recherche + filtres + cards dossiers

Le switch entre onglets est **HTMX** (`hx-get` + `hx-target` sur la sous-zone).
Le bouton sidebar "Explorer" et le lien toolbar chargent directement l'onglet
Explorer via `hx-get="/explorer/" hx-target="#zone-lecture" hx-push-url="/explorer/"`.

L'URL `/explorer/` en acces F5 renvoie `base.html` avec le partial Explorer
pre-charge (meme pattern que `/lire/{id}/`, `/analyseurs/`, `/credits/`).
Le flag `explorer_preloaded` dans le contexte de `base.html` declenche
l'inclusion du bon partial.

**Implementation** :
- `onboarding_vide.html` → ajouter la barre d'onglets en haut. Par defaut,
  l'onglet "Decouvrir" est actif. L'onglet "Explorer" charge le partial
  via `hx-get="/explorer/" hx-target="#zone-accueil-contenu"`
- `explorer_page.html` → **supprime** (page standalone)
- `explorer_contenu.html` → **nouveau** partial (titre + filtres + resultats),
  sans `<!DOCTYPE>`, sans `<nav>`, sans `<script>` — juste le contenu
- `base.html` :
  - Ajouter `{% elif explorer_preloaded %}` dans la cascade `#zone-lecture`
  - MAJ bouton sidebar : `hx-get="/explorer/" hx-target="#zone-lecture" hx-push-url="/explorer/"`
  - MAJ lien toolbar : meme pattern
- `views_explorer.py` `list()` :
  - HTMX → renvoie `explorer_contenu.html`
  - F5 → renvoie `base.html` avec `explorer_preloaded=True` dans le contexte

### 2.1 — Exclure ses propres dossiers de l'Explorer

**Probleme** : l'utilisateur voit ses propres dossiers publics dans la liste
et peut meme se "suivre" lui-meme. C'est inutile (il y a deja acces via
l'arbre) et perturbant.

**Solution** :
- Dans `list()`, exclure `owner=request.user` du queryset si l'utilisateur
  est connecte (les anonymes voient tout)
- Dans `explorer_card.html`, ne pas afficher le bouton "Suivre" si
  `dossier.owner == user` (securite defense en profondeur)

### 2.2 — Preview depliable du contenu d'un dossier

**Probleme** : en cliquant sur un dossier, on est redirige vers `/lire/{pk}/`
(la page de lecture). On ne peut pas apercevoir le contenu sans quitter
l'Explorer. L'utilisateur ne sait pas ce que contient un dossier avant
de s'y engager.

**Solution** : collapse/expand sur chaque card dossier.

```
┌─────────────────────────────────────────────────────────┐
│ Debat IA education                          [Suivre]    │
│ par jean · 12 pages · 3 suivis · 15/03/2026            │
│ [tag Verbatim] [tag Lois Asimov] [tag Charte]          │
│                                              [▼ Ouvrir] │
├─────────────────────────────────────────────────────────┤
│  ┌ Verbatim eleves sur l'IA ──────────────────────────┐ │
│  │ Les eleves ont ete interroges sur leur perception   │ │
│  │ de l'IA. Plusieurs themes emergent : la peur du...  │ │
│  └─────────────────────────────────────────────────────┘ │
│  ┌ Lois d'Asimov-Ephicentria ─────────────────────────┐ │
│  │ Ce document reprend les trois lois de la robotique  │ │
│  │ d'Asimov et les adapte au contexte numerique...     │ │
│  └─────────────────────────────────────────────────────┘ │
│  ┌ Charte numerique Ostrom ───────────────────────────┐ │
│  │ Inspiree des principes d'Elinor Ostrom pour la...   │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  + 9 autres pages...                                    │
└─────────────────────────────────────────────────────────┘
```

**Comportement** :
- Bouton chevron `▼` sur la card (ou clic sur toute la zone basse)
- `hx-get="/explorer/{pk}/preview/"` → partial avec les pages du dossier
- Afficher les **8 premieres pages racines** (pas les versions/restitutions)
- Pour chaque page : titre + 2-3 premieres lignes de `text_readability`
  (tronquees a ~150 caracteres, affichees en `text-slate-500 text-xs`)
- Si plus de 8 pages, lien "… + N autres pages" qui pointe vers `/lire/{pk}/`
- Le collapse est local a la card (pas de navigation, pas de changement d'URL)
- Animation CSS `max-height` + `overflow-hidden` pour le deploiement fluide

**Nouvelle action ViewSet** :
```python
@action(detail=True, methods=["GET"], url_path="preview")
def preview(self, request, pk=None):
    """
    Retourne le partial HTML avec les pages du dossier (max 8).
    / Returns the HTML partial with folder pages (max 8).
    """
```

### 2.3 — Visibilite superuser (tous les dossiers)

**Probleme** : un superuser (admin) ne voit que les dossiers publics,
comme tout le monde. Il ne peut pas decouvrir ni superviser les dossiers
prives ou partages d'autres utilisateurs.

**Solution** :
- Si `request.user.is_superuser`, ne pas filtrer par `visibilite=PUBLIC`
  → afficher **tous** les dossiers (prives, partages, publics)
- Ajouter un badge visuel sur chaque card pour indiquer la visibilite :
  - `PUBLIC` → badge vert "Public"
  - `PARTAGE` → badge bleu "Partage"
  - `PRIVE` → badge gris "Prive"
- Le bouton "Suivre" reste restreint aux dossiers **publics** uniquement
  (le superuser voit tout mais ne peut suivre que les publics ou ceux
  partages avec lui). Cela respecte le modele de permissions existant.
- Ajouter un filtre `visibilite` (dropdown) dans la barre de filtres,
  visible uniquement pour les superusers

### 2.4 — Recherche centree document (pas dossier)

**Probleme UX fondamental** : la recherche actuelle renvoie des **dossiers**.
L'utilisateur qui cherche "Ostrom" obtient un dossier "Demonstration"
sans savoir quel document matche, quel passage, pourquoi. C'est comme
un catalogue qui montre le nom du rayon mais pas le livre.

**Pivot** : la recherche renvoie des **documents (Pages)**, pas des dossiers.
Chaque resultat montre le document, son extrait contextuel, et le dossier
parent avec un bouton "Suivre".

**Donnees cherchables** (par priorite de pertinence) :

| Source | Champ | Exemple |
|--------|-------|---------|
| `Page.title` | Titre du document | "Elinor Ostrom — Gouvernance des communs" |
| `Page.text_readability` | Contenu du texte | Tout le corps du document |
| `ExtractedEntity.attributes→mots_cles` | Mots-cles extraits par l'IA | "gouvernance, communs, ressources" |
| `ExtractedEntity.attributes→hypostases` | Hypostases assignees | "structure, definition, principe" |
| `ExtractedEntity.attributes→resume` | Resume IA de l'extraction | "Les principes d'Ostrom pour la gouvernance..." |
| `Dossier.name` | Nom du dossier parent | "Demonstration" |
| `User.username` | Nom de l'auteur | "jean" |

**Implementation** :

```python
# Deux modes de recherche selon la presence d'un terme
# / Two search modes depending on search term presence

if terme_recherche:
    # Mode recherche → renvoie des Pages (documents)
    # / Search mode → returns Pages (documents)
    queryset_pages = Page.objects.filter(
        parent_page__isnull=True,  # pages racines uniquement
        dossier__isnull=False,     # pages classees dans un dossier
    ).select_related("dossier", "dossier__owner")

    # Filtrer selon les permissions (meme logique que les dossiers)
    # / Filter according to permissions (same logic as folders)
    if request.user.is_superuser:
        pass  # voit tout
    elif request.user.is_authenticated:
        queryset_pages = queryset_pages.filter(
            dossier__visibilite=VisibiliteDossier.PUBLIC,
        ).exclude(dossier__owner=request.user)
    else:
        queryset_pages = queryset_pages.filter(
            dossier__visibilite=VisibiliteDossier.PUBLIC,
        )

    queryset_pages = queryset_pages.filter(
        Q(title__icontains=terme_recherche)
        | Q(text_readability__icontains=terme_recherche)
        | Q(dossier__name__icontains=terme_recherche)
        | Q(dossier__owner__username__icontains=terme_recherche)
        | Q(extraction_jobs__entities__attributes__mots_cles__icontains=terme_recherche)
        | Q(extraction_jobs__entities__attributes__resume__icontains=terme_recherche)
    ).distinct()

    # Generer un extrait contextuel pour chaque resultat
    # / Generate a contextual snippet for each result
    # (voir section 2.4b ci-dessous)

else:
    # Mode navigation → renvoie des Dossiers (comportement actuel)
    # / Browse mode → returns Folders (current behavior)
    queryset_dossiers = ...  # logique existante
```

### 2.4b — Extrait contextuel avec surlignage

Quand un document matche via `text_readability`, extraire un **snippet**
de ~200 caracteres autour du terme trouve, avec le terme balise `<mark>`.

```python
def _extraire_snippet(texte_complet, terme, longueur_contexte=100):
    """
    Trouve la premiere occurrence du terme dans le texte et retourne
    un extrait avec du contexte avant/apres + balise <mark>.
    / Finds the first occurrence of the search term and returns
    a snippet with surrounding context + <mark> tag.
    """
    position = texte_complet.lower().find(terme.lower())
    if position == -1:
        return texte_complet[:200] + "..."
    debut = max(0, position - longueur_contexte)
    fin = min(len(texte_complet), position + len(terme) + longueur_contexte)
    extrait = texte_complet[debut:fin]
    # Surligner le terme / Highlight the term
    # (escape HTML du texte, puis wrapping <mark>)
    return extrait  # implementation complete dans le code
```

### 2.4c — Card resultat document

```
┌──────────────────────────────────────────────────────────┐
│  📄 Elinor Ostrom — Gouvernance des communs              │
│  dans Demonstration · par jean                [Suivre ▸] │
│                                                          │
│  "...les principes d'Elinor [Ostrom] pour la             │
│   gouvernance des communs montrent que les               │
│   ressources partagees peuvent etre gerees..."           │
│                                                          │
│  🏷 structure · definition · principe                     │
│  gouvernance, communs, ressources partagees              │
└──────────────────────────────────────────────────────────┘
```

- **Ligne 1** : titre du document (lien cliquable vers `/lire/{page_id}/`)
- **Ligne 2** : dossier parent + auteur + bouton "Suivre" le dossier
  - Si c'est le dossier du user → afficher "(votre dossier)" au lieu du bouton
- **Bloc citation** : snippet de ~200 chars avec terme surligne en `<mark>`
  - Si le match vient du titre → pas de snippet
  - Si le match vient des mots-cles/resume IA → snippet du resume
- **Ligne tags** : hypostases (pastilles colorees) + mots-cles (texte gris)

### 2.4d — Double mode : navigation et recherche

| Champ vide | Champ rempli |
|------------|--------------|
| Mode **navigation** | Mode **recherche** |
| Affiche des **dossiers** (cards actuelles) | Affiche des **documents** (nouvelles cards) |
| Filtres : auteur, tri, visibilite | Filtres : auteur, tri |
| Preview depliable par dossier | Snippet contextuel par document |

Ce double mode permet de garder la navigation par dossiers (decouverte)
tout en offrant une recherche fine par contenu (exploration).

### 2.4e — Spinner de chargement (`hx-indicator`)

Ajouter un `hx-indicator` sur la barre de recherche pour signaler que
la requete est en cours (important pour la recherche dans `text_readability`
qui peut prendre quelques centaines de ms sur un gros corpus).

```html
{# Spinner de recherche — visible pendant la requete HTMX #}
{# / Search spinner — visible during HTMX request #}
<svg class="htmx-indicator w-4 h-4 animate-spin text-slate-400"
     id="explorer-spinner" ...>
</svg>
```

- Le spinner apparait **dans** le champ de recherche (a droite)
- `hx-indicator="#explorer-spinner"` sur l'input et les selects
- Disparait automatiquement quand HTMX recoit la reponse

### 2.5 — Curation : extractions en debat + invitations a participer

**Reflexion UX** : Hypostasia n'est pas un reseau social. Les metriques
"plus lu" ou "plus suivi" sont du remplissage. Les pilules d'hypostases
sont trop techniques et trop nombreuses pour un non-initie.

Ce qui donne envie de participer a un debat, c'est de **lire un passage
provocant** et de reagir. Le meilleur levier de curation, c'est le contenu
lui-meme — pas des compteurs abstraits.

#### 2.5a — "Ca fait debat" : extractions controversees en vitrine

Afficher les **3 extractions les plus disputees** des documents publics
(CONTROVERSE > DISCUTE > DISCUTABLE), avec la citation exacte, le resume IA,
et un lien direct vers le passage dans le texte.

```
─── Ca fait debat ──────────────────────────────────────

  « L'intelligence artificielle est la revolution la
    plus importante depuis l'invention de l'ecriture. »

  L'IA comparee a l'ecriture comme rupture
  civilisationnelle majeure.

  dans Debat IA — Laurent Alexandre...
  🔴 CONTROVERSE                        [Rejoindre →]

────────────────────────────────────────────────────────

  « Le transhumanisme n'est pas une ideologie, c'est
    la description lucide de ce qui arrive. »

  Le transhumanisme presente comme description
  objective de la convergence NBIC.

  dans Debat IA — Laurent Alexandre...
  🔴 CONTROVERSE                        [Rejoindre →]

────────────────────────────────────────────────────────

  « On nous presente l'IA comme une fatalite historique,
    alors qu'il s'agit d'un choix politique... »

  L'IA n'est pas une fatalite mais un choix
  politique deguise en progres.

  🔵 DISCUTE                            [Rejoindre →]
```

**Design** :
- Citation source en **Lora italique** (provenance humaine, regles typo du projet)
- Resume IA en **B612 Mono** (provenance machine) — plus petit, sous la citation
- Pastille de statut avec forme Wong + couleur (PHASE-26d)
- Bouton "Rejoindre" → navigue vers `/lire/{page_id}/` avec scroll + surlignage
  sur l'extraction (meme pattern que les pastilles de marge existantes)
- Separateur fin entre chaque extraction — respiration editoriale

**Selection des extractions** :
```python
# Prioriser par intensite de debat puis par recence
# / Prioritize by debate intensity then by recency
PRIORITE_STATUTS = ["controverse", "discute", "discutable"]

extractions_en_debat = ExtractedEntity.objects.filter(
    job__page__dossier__visibilite=VisibiliteDossier.PUBLIC,
    job__status="completed",
    statut_debat__in=PRIORITE_STATUTS,
).select_related(
    "job__page", "job__page__dossier",
).order_by(
    # Trier par priorite de statut : controverse > discute > discutable
    models.Case(
        models.When(statut_debat="controverse", then=0),
        models.When(statut_debat="discute", then=1),
        models.When(statut_debat="discutable", then=2),
    ),
    "-job__created_at",
)[:3]
```

**Si aucun debat actif** : afficher un message encourageant a la place :
"Pas encore de debat sur les documents publics. Ouvrez un texte,
commentez une extraction — le debat commence avec vous."

#### 2.5b — "En attente de votre avis" : extractions sans commentaire

Sous les debats actifs, montrer **2-3 extractions DISCUTABLE ou DISCUTE
qui n'ont aucun commentaire**. Ce sont les passages qui attendent un
premier retour. Appel a l'action explicite.

```
─── En attente de votre avis ───────────────────────────

  « Les algorithmes de recommandation decident ce que
    nous lisons, ce que nous achetons... »

  🟠 DISCUTABLE · 0 commentaire         [Commenter →]

  « Il affirme que l'homme qui vivra mille ans est
    deja ne... »

  🟠 DISCUTABLE · 0 commentaire         [Commenter →]
```

**Design** : plus compact que les debats actifs — pas de resume IA,
juste la citation + le statut + le call-to-action. Sentiment d'urgence
legere : "personne n'a encore reagi".

#### 2.5c — Bandeau de compteurs (ligne de contexte)

Ligne compacte au-dessus des dossiers, avec les compteurs de statuts
cliquables + stats globales. Pas de bloc separe — juste une ligne.

```
🔴 5 controverses · 🔵 8 en debat · 🟢 8 consensuels
2 dossiers · 7 documents · 645 extractions
```

- Compteurs de statuts cliquables → filtre les documents par statut
- Stats globales non cliquables — juste du contexte
- Disparait en mode recherche (remplace par "X resultats pour « terme »")

---

## 3. Design UX — Direction esthetique

### Tonalite

L'Explorer est un **outil de decouverte**, pas un dashboard. Il doit donner
envie de fouiller, de parcourir. L'esthetique doit etre **editoriale** :
espaces genereux, typographie soignee, hierarchie visuelle claire.
Penser a un catalogue de bibliotheque plutot qu'a un moteur de recherche.

### Composants visuels

**Card dossier (fermee)** :
- Fond blanc, bordure fine `border-slate-200`, ombre subtile au hover
- Titre en `font-semibold text-slate-800` — c'est l'element le plus lisible
- Metadata en `text-xs text-slate-400` : auteur, pages, suivis, date
- Tags preview (3 premiers titres de pages) en petits badges `bg-slate-100`
- Bouton Suivre : discret, `text-xs`, couleur bleue/ambre selon etat
- Chevron `▼` pour deployer le preview, anime en rotation

**Card dossier (depliee)** :
- Zone de preview sous la card avec `border-t border-slate-100`
- Chaque page = mini-card avec titre en gras + extrait en italique
- Extraits en `text-slate-500 text-xs italic` (provenance humaine → Lora)
- Transition `max-height` fluide (~300ms ease-out)

**Badge visibilite (superuser)** :
- Petit badge inline a cote du titre du dossier
- Couleurs semantiques : vert/public, bleu/partage, gris/prive
- Forme : `rounded-full px-2 py-0.5 text-[10px] font-medium`

**Etat vide ameliore** :
- Illustration legere (SVG loupe + dossier) au lieu du SVG generique actuel
- Message contextuel : "Aucun dossier ne correspond a votre recherche"
  vs "Aucun dossier public pour le moment" (si pas de filtre actif)

---

## 4. Fichiers a modifier/creer

| Fichier | Action |
|---------|--------|
| `front/views_explorer.py` | Modifier `list()` (F5 vs HTMX, exclure ses dossiers, superuser, recherche etendue) + ajouter `preview()` |
| `front/templates/front/includes/explorer_contenu.html` | **Nouveau** — partial Explorer (titre + filtres + resultats) |
| `front/templates/front/includes/explorer_page.html` | **Supprime** — remplace par `explorer_contenu.html` integre au layout |
| `front/templates/front/includes/onboarding_vide.html` | Ajouter barre d'onglets (Decouvrir / Explorer) + zone `#zone-accueil-contenu` |
| `front/templates/front/includes/explorer_card.html` | Ajouter chevron + zone collapse + badge visibilite |
| `front/templates/front/includes/explorer_preview.html` | **Nouveau** — partial pour le contenu depliable |
| `front/templates/front/includes/explorer_resultats.html` | MAJ message etat vide contextuel |
| `front/templates/front/base.html` | +`explorer_preloaded` dans la cascade + MAJ bouton sidebar + lien toolbar |
| `front/serializers.py` | MAJ `ExplorerFiltresSerializer` (+`visibilite`, +`concept`, +`statut`) |
| `front/static/front/css/hypostasia.css` | Styles onglets accueil + transition collapse |
| `front/tests/test_explorer_v2.py` | **Nouveau** — tests unitaires |

---

## 5. Criteres de validation

- [ ] L'Explorer s'affiche dans `#zone-lecture` du layout principal (toolbar + sidebar conservees)
- [ ] Le bouton "Explorer" de la sidebar charge le contenu en HTMX sans navigation
- [ ] L'acces direct F5 sur `/explorer/` affiche la page complete avec layout principal
- [ ] Les filtres HTMX internes (recherche, auteur, tri) fonctionnent dans le partial
- [ ] L'utilisateur connecte ne voit pas ses propres dossiers dans l'Explorer
- [ ] L'utilisateur ne peut pas se suivre lui-meme (bouton absent + protection backend)
- [ ] Le chevron `▼` sur une card deploie le preview avec les 8 premieres pages
- [ ] Chaque page du preview affiche titre + debut du texte (~150 chars)
- [ ] Le collapse est anime (transition fluide, pas de saut)
- [ ] Le superuser voit tous les dossiers (prives, partages, publics)
- [ ] Les badges de visibilite sont affiches pour le superuser
- [ ] Le superuser ne peut suivre que les dossiers publics
- [ ] Le filtre "visibilite" apparait uniquement pour les superusers
- [ ] Recherche vide → mode navigation (dossiers, comportement actuel)
- [ ] Recherche remplie → mode recherche (documents avec snippets)
- [ ] La recherche trouve des documents par titre, contenu texte, mots-cles, resume IA, ou nom d'auteur
- [ ] Chaque resultat document affiche un snippet avec le terme surligne (`<mark>`)
- [ ] Chaque resultat montre le dossier parent avec bouton "Suivre"
- [ ] Un spinner `hx-indicator` apparait dans le champ de recherche pendant le chargement
- [ ] Le placeholder du champ de recherche reflete la portee : texte, auteur, concept
- [ ] Les resultats sont dedupliques (pas de document en double)
- [ ] Bloc "Ca fait debat" affiche 3 extractions controversees avec citation + resume + statut
- [ ] Bouton "Rejoindre" navigue vers la page avec scroll + surlignage sur l'extraction
- [ ] Citation en Lora italique, resume en B612 Mono (regles typo du projet)
- [ ] Bloc "En attente de votre avis" affiche 2-3 extractions sans commentaire
- [ ] Si aucun debat actif, message encourageant a la place des blocs
- [ ] Bandeau compteurs (statuts cliquables + stats globales) au-dessus des dossiers
- [ ] Clic sur un compteur de statut → filtre les documents par statut
- [ ] L'anonyme voit toujours uniquement les dossiers publics (pas de regression)
- [ ] 742+ tests passent (existants + nouveaux)

---

## 6. Verification navigateur

0. **Integration layout** → cliquer "Explorer" dans la sidebar → la toolbar reste visible, le contenu s'affiche dans la zone de lecture. F5 sur `/explorer/` → meme resultat avec page complete
1. **Connecte normal** → ouvrir `/explorer/` → verifier que ses propres dossiers publics sont absents
2. **Connecte normal** → deployer une card → voir les pages + extraits de texte
3. **Connecte normal** → rechercher "Ostrom" → trouver le document "Elinor Ostrom — Gouvernance des communs" avec snippet surligne + dossier parent
4. **Superuser** → ouvrir `/explorer/` → voir tous les dossiers avec badges de visibilite
5. **Superuser** → filtrer par "Prive" → ne voir que les dossiers prives
6. **Superuser** → tenter de suivre un dossier prive → bouton absent
7. **Anonyme** → ouvrir `/explorer/` → ne voir que les dossiers publics, pas de regression

---

## 7. Relation avec le plan existant

Cette phase **ne touche pas** aux fonctionnalites prevues en Phase 6
(recherche semantique, alignement par hypostases). Elle ameliore
uniquement l'Explorer de la PHASE-25d avec des ameliorations UX
qui seront **reutilisees** par la Phase 6 :

- La recherche etendue (2.4) sera remplacee par la recherche semantique
  quand les embeddings seront disponibles (etape 6.1)
- Le preview depliable (2.2) sera enrichi avec les extractions et
  les hypostases quand le mode Alignement sera disponible (etape 6.2)
- La visibilite superuser (2.3) est permanente et transverse

Le graphe de dependances reste inchange :
```
PHASE-25d (terminee) ──► PHASE-25d-v2 (cette phase)
                                       ──► Phase 6 (recherche semantique, futur)
```
