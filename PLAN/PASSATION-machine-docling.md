# Passation — chantier PDF/Docling sur machine dédiée

> Écrit le 11 août 2026, à donner tel quel à la session qui travaillera
> sur une machine capable de faire tourner Docling.
> **Lire aussi** : `INDEX-DOCUMENTATION.md` (point d'entrée de tous les
> documents), puis le `CHANGELOG.md` (entrées R1 à R4 = l'état réel).

---

## 0. Ce qu'il faut savoir en trois phrases

Hypostasia est un outil de **délibération sourcée** : on importe des
documents, un LLM en extrait des « idées », et chaque idée reste
**ancrée** au passage exact dont elle vient — c'est cette ancre qui fait
la preuve. Des humains commentent ces idées ; la base en porte **983**,
c'est la donnée la plus précieuse du produit.

Depuis le 10-11 août, il n'existe plus qu'**un seul moteur d'ancrage**,
dit ELEMENT : chaque document est découpé en `ElementDocument` (un bloc
= un paragraphe, un titre, une puce, ou **un tour de parole** pour un
audio), et une idée pointe une ou plusieurs **portions** d'éléments.

L'ancien moteur (ancrage par offsets de caractères) a été **entièrement
supprimé** : ~1 100 lignes, le champ `Page.moteur`, sa migration.

---

## 1. Ta mission

**Docling ne tourne pas sur la machine de développement** : il charge
des modèles ML de plusieurs Go, et l'hôte n'a que 8 Go partagés avec la
production — il est déjà tombé une fois pour cette raison (10 août).

Tu es sur une machine capable. Trois objectifs, dans cet ordre :

1. **Installer et éprouver Docling** sur des PDF réels.
2. **Produire des fixtures étalons** versionnées, qui permettront de
   travailler le visualiseur PDF sans Docling ensuite.
3. **Écrire la spec du visualiseur PDF** (elle est incomplète), puis le
   coder si le temps le permet.

### ⚠️ Ce qui N'A PAS besoin de toi — MESURÉ, pas supposé

**L'audio ne touche pas Docling.** Une transcription diarisée est déjà
structurée : `services/ingestion_audio.py` la découpe en tours de parole
sans charger le moindre modèle — 1,8 s sur la petite machine. Le lecteur
audio se fera là-bas. N'y touche pas.

**Le markdown et le HTML non plus, en pratique.** Ils passent bien par
Docling (`.md` est dans `EXTENSIONS_COUVERTES_PAR_DOCLING`, et la
capture web a `convertir_du_html_avec_docling`), mais **sans OCR ni
modèle de layout** — ceux-là ne se chargent que pour les PDF et les
images. Mesure du 11 août sur la petite machine, fixture
`pad-markdown.md` :

| | |
|---|---|
| RAM du process avant import | 108 Mo |
| après import du service | 178 Mo |
| **après conversion markdown** | **784 Mo**, 3,5 s |
| éléments extraits | 19, labels justes (`title`, `section_header`, `text`) |

Autrement dit : **seul le PDF (et l'image) exige ta machine.** Si tu
mesures autre chose sur docx/pptx/xlsx, note-le — personne ne l'a
encore fait.

**Et il ne faut PAS sortir le markdown ni le HTML de Docling** : c'est
lui qui donne les vrais labels de structure, ceux que la gouttière
affiche en mode structure. Le découpage maison par paragraphes met tout
en `text` — la base en porte la trace : 4 888 éléments `text` pour
4 `title` et 3 `section_header`.

---

## 2. Le contexte technique

### Le modèle de données qui compte

```
Page ──< ElementDocument ──< AncrageExtraction >── ExtractedEntity ──< CommentaireExtraction
         (bloc de doc)       (portion ancrée)       (une « idée »)      (parole humaine)
```

- `ElementDocument.provenance` (JSON) porte **d'où vient le bloc** :
  - PDF → `{"page_no": 4, "boites": [{l, t, r, b, coord_origin}, …]}`
    (une LISTE : un paragraphe peut être à cheval sur deux pages)
  - audio → `{"locuteur": "Marie", "debut": 12.5, "fin": 30.0}`
- `AncrageExtraction.element` est en **PROTECT** : on ne supprime jamais
  un élément qui porte une portion. Pour supprimer une page entière, il
  faut retirer les portions d'abord.
- `Page.moteur` **n'existe plus** : ne cherche pas ce champ.

### État mesuré de la base de dev (11 août)

| | |
|---|---|
| Pages | 213, **toutes** sur le moteur ELEMENT |
| Commentaires humains | **983** — ne jamais en perdre un |
| Ancres actives / détachées | 22 148 / 1 311 |
| Éléments avec `locuteur` (audio) | **2 210** |
| Éléments avec `page_no` (PDF) | **0** ← le trou que tu viens combler |

**Aucun PDF n'a jamais été ingéré par le moteur ELEMENT.** C'est pour
ça que le visualiseur PDF n'a pas pu être développé : il n'y a pas une
seule boîte de coordonnées en base.

---

## 3. Objectif 1 — Docling

Le service existe déjà : `hypostasis_extractor/services/
ingestion_docling.py`. Il expose `convertir_un_fichier_avec_docling`,
`extraire_les_elements_bruts` et `creer_les_elements_d_une_page`, et il
est appelé par la tâche Celery `ingerer_un_fichier_avec_docling`
(`tasks_element.py`), sur une **file dédiée à concurrence 1**
(`ingestion_docling`) précisément pour ne jamais lancer deux
conversions à la fois.

**Ce qu'on attend de toi :**

1. Vérifier qu'il tourne, et **mesurer** : RAM au pic, durée, pour un
   PDF de 1, 10 et 100 pages.
2. Vérifier que `extraire_les_elements_bruts` remplit bien
   `provenance = {"page_no", "boites"}`. **C'est le point critique** :
   si les boîtes ne sortent pas, le visualiseur PDF est impossible et
   il faut le dire tout de suite.
3. Noter le système de coordonnées (`coord_origin` : haut-gauche ou
   bas-gauche ? unités ? relatif à quelle taille de page ?). La spec
   `SPEC-ancrage-par-element-v2.md § 8.2` mentionne
   `convertToViewportRectangle` et `devicePixelRatio` — il faut savoir
   ce que Docling donne exactement pour écrire la conversion.

**PDF disponibles dans le dépôt** (déjà là, aucun à fabriquer) :

```
PLAN/References/exemple alignement.pdf
media/sources/BULL_10-05-2026_WVLBsXG.pdf
media/sources/Synthese_BULL2.pdf
media/sources/resume_nouvelle_tentative_piPO40n.pdf
"Sujets d'études/IA et Apprentissage/…carto.docx (1)-1.pdf"
```

Prends-en un **avec des tableaux** et un **avec des images** : ce sont
les deux formes qui cassent les convertisseurs.

---

## 4. Objectif 2 — les fixtures étalons (le vrai livrable)

C'est ce qui a le plus de valeur : **une fois ces fixtures produites,
tout le reste du travail PDF pourra se faire sans Docling**, donc sur
n'importe quelle machine.

L'idée : ne pas versionner les PDF ni les modèles, mais **le RÉSULTAT
de la conversion**, en JSON, pour pouvoir rejouer l'ingestion à l'infini
sans rien installer.

### Ce qu'il faut produire

Dans `hypostasis_extractor/tests/fixtures/` (qui contient déjà
`pad-markdown.md` et `notes-texte-brut.txt`) :

```
pdf-simple.elements.json        ~3 pages, texte courant
pdf-tableaux.elements.json      un PDF à tableaux
pdf-images.elements.json        un PDF à images/figures
docx-structure.elements.json    titres, listes, gras
```

Format de chaque fichier — **exactement ce que
`extraire_les_elements_bruts` retourne**, pour que la fixture puisse
être passée telle quelle à `creer_les_elements_d_une_page` :

```json
{
  "source": "BULL_10-05-2026.pdf",
  "docling_version": "x.y.z",
  "converti_le": "2026-08-12",
  "elements": [
    {
      "texte": "Le conseil a voté le budget…",
      "label": "text",
      "reference_docling": "#/texts/0",
      "chemin_de_section": ["Introduction"],
      "provenance": {
        "page_no": 1,
        "boites": [{"l": 72.0, "t": 700.5, "r": 523.0, "b": 680.2,
                    "coord_origin": "BOTTOMLEFT"}]
      }
    }
  ]
}
```

Ajoute aussi, à côté, une **capture PNG de chaque page** du PDF source
(`pdf-simple.page-1.png`…) : le visualiseur devra dessiner les boîtes
par-dessus, et sans image de référence on ne peut ni développer ni
tester le calage.

### Une commande pour les rejouer

Écris `manage.py charger_fixtures_pdf` qui lit ces JSON et crée les
Pages + ElementDocument **sans Docling** — c'est elle qui permettra à la
petite machine de travailler. Le patron existe : regarde
`core/management/commands/enrichir_la_provenance_audio.py` pour le style
attendu (commandes en français, `--a-blanc` obligatoire, bilan chiffré).

⚠️ **Ne mets pas d'appel Docling dans une commande de fixtures.** C'est
exactement ce qui a fait tomber le serveur le 10 août.

---

## 5. Objectif 3 — la spec du visualiseur PDF

`SPEC-ancrage-par-element-v2.md § 8.2` existe mais est **insuffisante
pour coder** : elle donne un bon delta (trois corrections :
`convertToViewportRectangle`, `devicePixelRatio`, `provenance.boites`
en liste) **sans le socle** — aucun mot sur le composant PDF.js, la
pagination, le zoom, le calque de surlignage.

À écrire, en addendum daté dans la spec :

- quel composant (PDF.js ? version ? servi comment ?) ;
- pagination et zoom : que se passe-t-il quand on change de page ou
  qu'on zoome — les boîtes se recalculent, se redessinent ?
- le calque : SVG au-dessus du canvas, ou div positionnés ?
- le lien avec le texte : cliquer une idée dans le panneau doit ouvrir
  le PDF **à la bonne page, boîte surlignée** ;
- le cas d'un paragraphe **à cheval sur deux pages** (d'où la LISTE de
  boîtes) ;
- ce qu'on fait d'un PDF **sans couche texte** (scan pur) : c'est le cas
  de la page 97 en base, 4 Mo d'images sans un caractère.

L'étalon `tmp/maquettes/maquette.html` montre l'intention côté UI mais
**mocke** ce bouton : il affiche un toast. Le bouton existe déjà dans
l'application (`.bouton-voir-source` dans la gouttière, apparaît dès
qu'un élément a `provenance.page_no`) et dit honnêtement que le
visualiseur n'est pas disponible. Ton travail est de le rendre vrai.

---

## 6. Pièges d'environnement — le non-respect a déjà cassé des choses

| Piège | Conséquence vécue |
|---|---|
| **Deux `manage.py test` en parallèle** | ils se détruisent la base : 755 erreurs fantômes, 648 `ProgrammingError`. **Une suite à la fois.** |
| **Docling en masse** | OOM, serveur tombé (10 août). Une conversion à la fois, `free -h` avant. |
| **Build Tailwind FIGÉ** | toute classe arbitraire `z-[70]`, `min-w-[160px]` est **inerte**. Utiliser du style inline ou rebuilder. |
| **`DEBUG=False` → cache de templates** | après un `.html` : `supervisorctl restart daphne gunicorn`. Après un JS/CSS : `collectstatic` **et** bump du `?v=`. |
| **Playwright** | dans le conteneur, `PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright`, et `--host-resolver-rules="MAP localhost <ip nginx>"` sinon **aucun statique n'est servi** et le rapport est faux. |
| **Nouvelle tâche Celery** | redémarrer `celery_worker`, sinon il tourne avec l'ancien code et ignore la tâche. |
| **`AncrageExtraction.element` en PROTECT** | supprimer une page exige de retirer ses portions d'abord. |
| **Aucun `DEFAULT_PERMISSION_CLASSES`** | tout endpoint DRF est `AllowAny` par défaut : toute `@action` qui lit un objet doit appeler `_verifier_acces_page` / `_utilisateur_peut_ecrire_page`. Doctrine du **404**, jamais 403. |

Commandes utiles :

```bash
# tests (JAMAIS deux en parallèle, JAMAIS --parallel)
docker exec -e PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright \
  hypostasia_dev_web python manage.py test <cible> --noinput \
  --settings=hypostasia.settings_test_opus

# après un template
docker exec hypostasia_dev_web supervisorctl restart daphne gunicorn
```

---

## 7. La méthode attendue, non négociable

- **TDD strict** : le test d'abord, on le regarde échouer, puis le code.
- **Relecture adverse par un agent à chaque phase**, avec correctifs
  testés. C'est ce qui a rattrapé, sur la session précédente : des
  chiffres faux dans la documentation, une commande morte à l'import,
  une tâche qui pouvait figer un état pour toujours.
- **Tout front comparé à l'étalon au navigateur réel**, clair ET sombre,
  **contrastes calculés** — pas des impressions.
- **Trou de spec → écrire la spec avant de coder**, en addendum daté.
- `CHANGELOG.md` + fiche `A TESTER et DOCUMENTER/` par phase.
- **Ne jamais commiter sans autorisation explicite du propriétaire.**
  Si autorisé : identité Jonas VM, **pas de `Co-Authored-By`**.

---

## 8. État complet du produit

### Fait

| Couche | État |
|---|---|
| Moteur ELEMENT (phases A→H) | ✅ |
| Branchement BR-A→F | ✅ (BR-A et BR-C **supprimés** avec le flag) |
| Usage U1→U5 | ✅ commité |
| **R1** reconversion + allègement de la base | ✅ commité |
| **R2** pastilles mortes, filtre recâblé | ✅ non commité |
| **R3** mort de l'ancien moteur | ✅ non commité |
| **R4** conformité maquette + **ingestion audio** | ✅ non commité |
| Corpus A→I, Synthèse A→I | ✅ |
| Bascule CSS T1→T10 | ✅ |

### À faire

| # | Chantier | Bloqué par |
|---|---|---|
| 1 | **Fixtures PDF étalons** | Docling → **toi** |
| 2 | **Spec + visualiseur PDF** | les fixtures ci-dessus |
| 3 | Spec + lecteur audio | rien (données en base) — **petite machine** |
| 4 | Écran « sélection des preuves » (A→G) | rien ; 0 ligne écrite à ce jour |
| 5 | Statuts de débat incohérents | décision : 878 extractions commentées au statut périmé, 3 335 `non_pertinent` non fusionnés |
| 6 | Backlog UX P1 (11 postes) | rien |
| 7 | Audit des classes Tailwind arbitraires | rien (probablement toutes inertes) |
| 8 | `charger_fixtures_llm_reel` sans Docling | appelle encore Docling |
| 9 | RAG (`INSPIRATION_ATOMIC § 6`) | à réconcilier avec ELEMENT ; pgvector absent |
| 10 | Geste UI scission/fusion | **absent de la maquette** : décision de design |

---

## 9. Par quoi commencer, concrètement

1. Installer Docling, convertir **un seul** PDF, mesurer la RAM.
2. Regarder si `provenance.boites` est rempli. **Si non, s'arrêter et le
   dire** : tout le chantier PDF en dépend.
3. Produire les 4 fixtures JSON + les PNG de pages.
4. Écrire `manage.py charger_fixtures_pdf` (sans Docling).
5. Vérifier que la gouttière affiche « p. N » et le bouton « voir la
   source » sur une page ingérée — le code existe déjà et attend ces
   données.
6. Alors seulement, écrire la spec du visualiseur.
