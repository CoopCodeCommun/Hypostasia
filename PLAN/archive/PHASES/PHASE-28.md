# PHASE-28 — Wizard synthese + export PDF/HTML + comparaison

**Complexite** : L | **Mode** : Plan then normal | **Prerequis** : PHASE-27, PHASE-14, PHASE-09

---

## 1. Contexte

La synthese est le climax du cycle deliberatif — le moment ou le debat se cristallise en texte. Actuellement c'est un bouton "Restituer" vers un textarea vers generation IA — trop brutal pour l'acte le plus important du produit. Cette phase implemente un wizard guide en 5 etapes qui force la tracabilite par le design de l'interaction, l'export du debat en PDF (WeasyPrint) et HTML single-file avec la charte visuelle complete, et le mode comparaison cote-a-cote avec indicateurs de provenance de la redaction (humaine / IA validee / IA non modifiee).

## 2. Prerequis

- **PHASE-27** : modele SourceLink et tracabilite (le wizard cree des SourceLinks)
- **PHASE-14** : dashboard de consensus (le wizard est accessible depuis le dashboard, gate par le seuil de consensus)
- **PHASE-09** : cartes d'extraction inline (le wizard etape 1 affiche les cartes avec checkboxes)

## 3. Objectifs precis

### Etape 5.6 — Synthese assistee avec sourcage obligatoire (wizard guide)

**Wizard de synthese en 5 etapes** (partials HTMX multi-etapes, en pleine page) :

**Etape 1 — Selection des extractions** :
- [ ] Vue checkbox avec cartes compactes, pre-cochees sur les CONSENSUELLES
- [ ] Les extractions masquees (curation) ne sont pas montrees
- [ ] Les extractions CONTROVERSE sont signalees avec un warning

**Etape 2 — Revue des commentaires** :
- [ ] Pour chaque extraction incluse, afficher les commentaires cles
- [ ] Champ optionnel "Points cles a retenir" pour guider la redaction
- [ ] L'utilisateur valide qu'il a bien lu le debat avant de passer a la redaction

**Etape 3 — Redaction** :
- [ ] Textarea avec les citations sources listees en dessous (cliquables pour inserer la reference)
- [ ] Bouton "Pre-remplir par IA" : l'IA genere un brouillon avec references inline `[src:extraction-42]`
- [ ] L'humain a le dernier mot — il peut modifier, supprimer, ajouter

**Etape 4 — Verification du sourcage** :
- [ ] Le systeme affiche chaque paragraphe avec ses sources liees
- [ ] Les passages sans source sont marques en warning (fond orange pale)
- [ ] L'utilisateur peut ajouter une source manuellement ou valider "tel quel"
- [ ] Le bouton "Suivant" est actif meme avec des passages non sources (mais le warning reste visible)

**Etape 5 — Publication** :
- [ ] Label de version et resume automatique
- [ ] Bouton final "Creer la version" -> cree la Page fille, les SourceLinks, redirige vers la nouvelle version

**Actions techniques** :
- [ ] Modifier le prompt de restitution pour exiger des references inline (`[src:extraction-42]`, `[src:comment-17]`)
- [ ] Parser la reponse IA pour extraire les references et creer les SourceLinks automatiquement
- [ ] Si un paragraphe IA n'a aucune reference -> le marquer visuellement comme "non source" (warning)
- [ ] Implementer les 5 etapes du wizard comme partials HTMX enchaines
- [ ] L'etat du wizard est stocke en session (ou modele temporaire `SyntheseEnCours`)
- [ ] Le wizard est accessible uniquement depuis le dashboard de consensus — pas de bouton "Restituer" isole
- [ ] Charte visuelle dans le wizard : citations en `.typo-citation`, commentaires en `.typo-lecteur`, texte IA en `.typo-machine`

### Etape 5.7 — Export visuel du debat (PDF et HTML)

**Export PDF — Le livrable formel** (via WeasyPrint) :
- [ ] Template HTML dedie a l'export (`front/templates/front/export/debat_pdf.html`)
- [ ] CSS dedie (`front/static/front/css/export.css`) avec `@page` pour marges, en-tetes/pieds de page
- [ ] Polices B612 Mono (resumes IA), Lora italique (citations), Srisakdi (interventions lecteur), B612 gras uppercase (hypostases avec couleurs par famille)
- [ ] Badges de statut colores (CONSENSUEL vert, DISCUTE ambre, etc.)

**Export HTML — Le livrable partageable** :
- [ ] Single-file : tout le CSS et JS inline dans le `<head>`
- [ ] Interactif : cartes d'extraction depliables (accordeon JS inline)
- [ ] Navigable : ancres internes entre texte source et extractions
- [ ] Polices via CDN Google Fonts, degradation gracieuse si hors-ligne

**Contenu des deux formats** :
- [ ] En-tete : titre, date export, nombre extractions/commentaires/contributeurs, barre de consensus
- [ ] Texte source integral avec passages extraits surlignes
- [ ] Cartes d'extraction avec hypostase typee, resume IA, citation source, fil commentaires, statut debat
- [ ] Synthese avec SourceLinks resolus (si version synthetisee existe)
- [ ] Pied de page : mention Hypostasia, note de tracabilite

**Actions techniques** :
- [ ] Bouton "Exporter" dans la barre d'outils avec dropdown : "PDF" / "HTML" / "Markdown"
- [ ] Endpoint : action `exporter` sur `LectureViewSet` avec parametre `format=pdf|html|markdown`
- [ ] Generation cote serveur (pas de JS cote client pour le PDF)
- [ ] L'export inclut les extractions non masquees (curation respectee)
- [ ] L'export d'un dossier genere un document multi-textes avec table des matieres

### Etape 5.8 — Mode comparaison cote-a-cote avec provenance explicite

- [ ] Vue comparaison pleine page : 2 colonnes scrollables en sync
  - Selecteurs de version en haut (dropdown v1/v2 avec labels de version)
  - Diff genere par `difflib.SequenceMatcher` au niveau paragraphe
- [ ] Annotation des zones modifiees avec SourceLinks :
  - Chaque zone modifiee est associee aux SourceLinks correspondants
  - Bloc "Pourquoi" s'affiche inline sous la zone modifiee en v2
  - Si aucun SourceLink n'existe -> afficher "Modification sans source" (warning)
- [ ] Indicateur de provenance de la redaction :
  - Stocker dans le SourceLink si le texte a ete ecrit par l'humain, pre-rempli par l'IA et modifie, ou pre-rempli par l'IA et non modifie
  - Afficher l'icone correspondante sur chaque zone modifiee : redaction humaine / brouillon IA valide / brouillon IA non modifie
- [ ] Compteur de provenance en bas du diff : resume statistique des sources et de la redaction
- [ ] Bouton "Exporter ce diff" : genere un PDF/HTML du diff avec annotations de provenance
- [ ] Navigation depuis le diff : clic sur une extraction dans le bloc "Pourquoi" -> ouvre la carte inline
- [ ] Le diff est accessible depuis le switcher de versions : bouton "Comparer" entre deux pilules de version

## 4. Fichiers a modifier

- `front/views.py` — SyntheseViewSet (ou actions sur ExtractionViewSet) pour le wizard, LectureViewSet (action exporter, action comparer enrichie)
- `front/tasks.py` — `restituer_debat_task` (prompt avec references inline, parsing SourceLinks)
- `front/serializers.py` — serializers pour wizard, export, comparaison
- `front/templates/front/includes/synthese_etape_1.html` a `synthese_etape_5.html` — nouveaux templates wizard
- `front/templates/front/export/debat_pdf.html` — nouveau template export PDF/HTML
- `front/templates/front/includes/comparaison_versions.html` — nouveau template comparaison avec provenance
- `front/static/front/css/export.css` — nouveau fichier styles d'impression, `@page`
- `core/models.py` — champ `provenance_redaction` sur SourceLink (`humaine`, `ia_modifiee`, `ia_brute`)
- `pyproject.toml` — ajout de `weasyprint`

## 5. Criteres de validation

### Wizard synthese
- [ ] Les 5 etapes du wizard fonctionnent avec navigation avant/arriere sans perte de donnees
- [ ] Les extractions masquees ne sont pas montrees a l'etape 1
- [ ] Le bouton "Pre-remplir par IA" genere un brouillon avec references inline
- [ ] Les passages sans source sont marques en warning a l'etape 4
- [ ] La publication cree la Page fille avec les SourceLinks corrects
- [ ] Le wizard est inaccessible sous le seuil de consensus

### Export
- [ ] Export PDF : le fichier est genere avec les bonnes polices et couleurs
- [ ] Export HTML : le fichier est autonome (s'ouvre dans un navigateur sans serveur)
- [ ] Export HTML : les accordeons fonctionnent (clic deplie/replie)
- [ ] Les extractions masquees ne sont pas dans l'export
- [ ] La charte typographique est respectee (polices, couleurs, statuts)

### Comparaison
- [ ] Le diff s'affiche en 2 colonnes synchronisees avec selecteurs de version
- [ ] Les zones modifiees ont un bloc "Pourquoi" avec les bonnes sources
- [ ] Une modification sans SourceLink affiche le warning "sans source"
- [ ] Les indicateurs de provenance s'affichent correctement
- [ ] Le compteur de provenance en bas resume les statistiques
- [ ] Clic sur une source dans le bloc "Pourquoi" -> navigation vers l'extraction
- [ ] Export du diff : le PDF/HTML contient les annotations de provenance

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir un document avec assez de consensus (>= seuil) — le bouton "Synthese" est actif**
   - **Attendu** : le bouton est visible et cliquable
2. **Cliquer sur "Synthese" — le wizard s'ouvre en 5 etapes :**
   - **Etape 1** : selectionner les extractions a inclure (les masquees ne sont pas montrees)
   - **Etape 2** : revue des extractions selectionnees
   - **Etape 3** : redaction (bouton "Pre-remplir par IA" genere un brouillon avec [src:extraction-42])
   - **Etape 4** : verification du sourcage (passages sans source marques en warning)
   - **Etape 5** : publication → la Page fille est creee
3. **Naviguer avant/arriere dans le wizard**
   - **Attendu** : aucune donnee perdue
4. **Ouvrir la Page fille**
   - **Attendu** : les SourceLinks sont presents et navigables
5. **Export PDF : cliquer sur "Exporter PDF"**
   - **Attendu** : le fichier genere a les bonnes polices et couleurs
6. **Export HTML : cliquer sur "Exporter HTML" — ouvrir le fichier dans un navigateur SANS serveur**
   - **Attendu** : tout fonctionne (accordeons cliquables)
7. **Ouvrir le mode comparaison**
   - **Attendu** : 2 colonnes synchronisees, zones modifiees avec bloc "Pourquoi" et badges (redaction humaine, IA validee, IA non modifiee)

## 6. Extraits du PLAN.md

> ### Etape 5.6 — Synthese assistee avec sourcage obligatoire (wizard guide)
>
> **Objectif** : quand l'IA produit une synthese/restitution, chaque paragraphe doit etre ancre sur une source verifiable. Et l'UX de creation de cette synthese doit incarner la tracabilite — pas juste la stocker en base.
>
> **Pourquoi un wizard** : la synthese est le climax du cycle deliberatif — le moment ou le debat
> se cristallise en texte. Actuellement c'est un bouton "Restituer" -> un textarea -> l'IA genere
> -> c'est stocke. C'est trop brutal pour l'acte le plus important du produit.
>
> Un textarea libre ne garantit rien : l'utilisateur (ou l'IA) peut ecrire n'importe quoi sans lien
> avec les sources. Le wizard force la tracabilite *par le design de l'interaction*, pas juste par
> la structure de donnees. Chaque etape du wizard correspond a une exigence de tracabilite :
> selection des sources, revue du debat, redaction sourcee, verification, publication.
>
> Le dashboard de consensus (Etape 1.4) conditionne l'acces au wizard : le bouton "Lancer la synthese"
> n'est actif que quand le seuil de consensus est atteint. Les extractions masquees (Etape 1.8)
> sont exclues par defaut de la selection.
>
> **Actions techniques** :
> - [ ] Modifier le prompt de restitution pour exiger des references inline (ex: `[src:extraction-42]`, `[src:comment-17]`)
> - [ ] Parser la reponse IA pour extraire les references et creer les SourceLinks automatiquement
> - [ ] Si un paragraphe IA n'a aucune reference -> le marquer visuellement comme "non source" (warning)
> - [ ] Implementer les 5 etapes du wizard comme partials HTMX enchaines
> - [ ] L'etat du wizard est stocke en session (ou dans un modele temporaire `SyntheseEnCours`)
> - [ ] Le wizard est accessible uniquement depuis le dashboard de consensus — pas de bouton "Restituer" isole
> - [ ] Charte visuelle dans le wizard : citations en `.typo-citation`, commentaires en `.typo-lecteur`, texte IA en `.typo-machine`
>
> **Fichiers concernes** : `front/tasks.py`, `front/views.py`, nouveaux templates `front/includes/synthese_etape_1.html` a `synthese_etape_5.html`, `front/serializers.py`

> ### Etape 5.7 — Export visuel du debat (PDF et HTML)
>
> **Argumentaire** : l'export Markdown couvre le besoin technique — archivage, versionning, portabilite.
> Mais le **livrable politique** est different. Quand un facilitateur presente le resultat d'un debat
> au CA, aux financeurs, aux elus d'une collectivite, ou a un comite de pilotage, il ne montre pas
> du Markdown brut. Il montre un **document mis en forme** qui porte la credibilite de tout le processus
> deliberatif.
>
> L'export visuel est le moment ou Hypostasia produit son **artefact final** — celui qui justifie tout le
> travail d'extraction, de debat et de synthese.
>
> **Deux formats d'export** :
> 1. Export PDF via WeasyPrint (librairie Python, genere du PDF depuis du HTML+CSS)
> 2. Export HTML autonome (single-file, CSS inline, polices embarquees ou via CDN)
>
> **Actions** :
> - [ ] Bouton "Exporter" dans la barre d'outils avec dropdown : "PDF" / "HTML" / "Markdown"
> - [ ] Generation PDF via WeasyPrint : template HTML dedie, CSS dedie avec `@page`
> - [ ] Generation HTML : single-file avec CSS/JS inline, polices via CDN
> - [ ] Endpoint : action `exporter` sur `LectureViewSet` avec parametre `format=pdf|html|markdown`
> - [ ] L'export inclut automatiquement les extractions non masquees (curation respectee)
> - [ ] L'export d'un dossier genere un document multi-textes avec table des matieres
>
> **Fichiers concernes** : nouveau `front/templates/front/export/debat_pdf.html`, nouveau `front/static/front/css/export.css`, `front/views.py`, `pyproject.toml` (ajout `weasyprint`)

> ### Etape 5.8 — Mode comparaison cote-a-cote avec provenance explicite
>
> **Argumentaire** : un diff classique montre du vert et du rouge. C'est utile pour du code, mais pour
> un texte deliberatif c'est insuffisant — et meme dangereux. Sans provenance explicite, une modification
> peut ressembler a de la magie. Le mode comparaison incarne la valeur fondatrice "le LLM est un outil,
> pas un auteur". Chaque zone modifiee doit repondre a 3 questions en un coup d'oeil :
> 1. **Quoi** : qu'est-ce qui a change (le diff visuel)
> 2. **Pourquoi** : quelle deliberation a motive ce changement (les sources)
> 3. **Qui** : qui a contribue a cette modification (les auteurs)
>
> **Provenance de la redaction** — qui a ecrit le texte modifie :
> - Redaction humaine : l'humain a ecrit le texte directement dans le wizard
> - Brouillon IA, valide par l'humain : l'IA a genere le brouillon, l'humain l'a relu et valide
> - Brouillon IA, non modifie : l'IA a genere le texte et l'humain l'a valide sans modification (signale visuellement)
>
> **Compteur de provenance** en bas du diff : resume statistique des sources et de la redaction.
> C'est le resume de la qualite du travail deliberatif sur cette version.
>
> **Actions** :
> - [ ] Vue comparaison pleine page : 2 colonnes scrollables en sync
> - [ ] Annotation des zones modifiees avec SourceLinks
> - [ ] Indicateur de provenance de la redaction
> - [ ] Compteur de provenance en bas du diff
> - [ ] Bouton "Exporter ce diff"
> - [ ] Navigation depuis le diff
> - [ ] Le diff est accessible depuis le switcher de versions
>
> **Fichiers concernes** : `front/views.py`, nouveau `front/templates/front/includes/comparaison_versions.html`, `core/models.py` (champ `provenance_redaction` sur SourceLink)

## Tests prevus

**Module :** `front.tests.test_phase28` | **Statut : A ECRIRE**

### Wizard synthese

| Classe | Test | Quoi |
|--------|------|------|
| `WizardEtape1Test` | `test_affiche_extractions_non_masquees` | Extractions masquees exclues |
| `WizardEtape1Test` | `test_pre_coche_consensuelles` | Extractions consensuelles pre-cochees |
| `WizardEtape1Test` | `test_warning_controversees` | Warning sur extractions controversees |
| `WizardEtape2Test` | `test_affiche_commentaires_par_extraction` | Commentaires groupes par extraction |
| `WizardEtape3Test` | `test_pre_remplir_ia_genere_brouillon` | Le bouton IA genere un brouillon avec refs |
| `WizardEtape3Test` | `test_textarea_editable` | L'humain peut modifier le brouillon |
| `WizardEtape4Test` | `test_passages_sans_source_marques_warning` | Warning sur passages non sources |
| `WizardEtape5Test` | `test_publication_cree_page_fille` | La Page fille est creee avec SourceLinks |
| `WizardEtape5Test` | `test_publication_cree_source_links` | Les SourceLinks sont corrects |
| `WizardNavigationTest` | `test_avant_arriere_sans_perte` | Navigation avant/arriere conserve les donnees |
| `WizardAccesTest` | `test_inaccessible_sous_seuil_consensus` | Gate par le seuil de consensus |

### Export

| Classe | Test | Quoi |
|--------|------|------|
| `ExportPdfTest` | `test_genere_pdf_valide` | Le PDF est genere sans erreur |
| `ExportPdfTest` | `test_pdf_contient_extractions` | Les extractions sont dans le PDF |
| `ExportHtmlTest` | `test_genere_html_autonome` | Le HTML est self-contained |
| `ExportHtmlTest` | `test_accordeons_fonctionnent` | JS inline deplie/replie |
| `ExportMarkdownTest` | `test_genere_markdown_correct` | Le Markdown est bien forme |
| `ExportTest` | `test_exclut_extractions_masquees` | Curation respectee dans les exports |

### Comparaison avec provenance

| Classe | Test | Quoi |
|--------|------|------|
| `ComparaisonProvenanceTest` | `test_diff_avec_source_links` | Le bloc "Pourquoi" s'affiche sous les zones |
| `ComparaisonProvenanceTest` | `test_zone_sans_source_warning` | Warning "sans source" sur zones non liees |
| `ComparaisonProvenanceTest` | `test_indicateur_redaction_humaine` | Icone correcte pour redaction humaine |
| `ComparaisonProvenanceTest` | `test_indicateur_ia_validee` | Icone correcte pour IA modifiee |
| `ComparaisonProvenanceTest` | `test_indicateur_ia_brute` | Icone correcte pour IA non modifiee |
| `ComparaisonProvenanceTest` | `test_compteur_provenance` | Resume statistique en bas du diff |

**E2E :** tests prevus :
- `test_wizard_5_etapes_complet`
- `test_export_pdf_telecharge`
- `test_export_html_autonome`
- `test_comparaison_provenance_affiche_blocs`
- `test_clic_source_ouvre_extraction`
