# SPEC v2 — Ancrage par élément, ancre multi-éléments, moteur scission/fusion/ajout

**Projet** : Hypostasia V3
**Version de la spec** : 2.0 — 5 août 2026
**Remplace** : `SPEC-ancrage-par-element.md` v1.0 (4 août 2026)
**Statut** : **IMPLÉMENTÉE** — phases A-G codées et migrées, branchement BR-A→F
fait. Le texte ci-dessous est celui de la proposition d'origine, gardé pour les
décisions écartées qu'il conserve ; **les encarts datés en tête de fichier font
foi sur l'état réel**, pas les sections. Deux réserves connues : § 8.2 (PDF) et
§ 8.3 (audio) sont insuffisants pour coder tels quels — voir `PLAN/PASSATION.md`.
**Conventions** : skill `djc` (ViewSet explicites, serializers DRF, HTMX, FALC, commentaires FR/EN)
**Complétée par** : `SPEC-corpus-base-carnet-note.md` v1.1, `SPEC-synthese-carnet.md` v1.0
et `SPEC-selection-des-preuves.md` v1.0 (couches au-dessus)

> **Note de dépôt (8 août 2026) — cette spec est IMPLÉMENTÉE, pas en attente.**
>
> Elle a été codée, testée et migrée. Le texte ci-dessous est celui de la
> proposition d'origine, déposé sans modification : c'est le seul endroit où les
> décisions écartées et leurs raisons sont conservées, et le code ne les porte pas.
>
> Ce qui existe dans le dépôt : `hypostasis_extractor/services/` (ancrage,
> chunking, reconciliation, moteur_structure, garde_edition, masquage,
> reingestion, ingestion_docling, analyse_par_element), `front/services/rendu_elements.py`,
> les migrations `core.0035` à `0039` et `hypostasis_extractor.0031` à `0033`,
> et la commande `core/management/commands/basculer_vers_le_moteur_element.py`.
>
> **Addendum du 16 août 2026** — cette commande a été **supprimée** le 10 août
> avec l'ancien moteur (R3). Son travail est fait : 538 pages basculées, le récit
> est dans `CHANGELOG/2026-08-10-r1-reconversion-du-moteur-element.md`. Puisque
> la doctrine de ce fichier est « les encarts font foi », un encart périmé est
> plus dangereux qu'une section périmée : celui du 8 août est donc corrigé ici,
> pas réécrit plus haut.
>
> **Trois écarts entre cette spec et le code livré**, tous documentés au `CHANGELOG/` :
> le § 5.1 était incodable en l'état (il violait une contrainte d'unicité dès la
> première ligne — les contraintes ont été rendues `DEFERRABLE`) ; `element_parent`
> a été retiré (toujours `NULL` après scission ou fusion) ; et `EtatAncrage` a été
> réduit à `ANCREE` / `DETACHEE`.
>
> **Ce qui reste à faire** : le pipeline d'analyse par élément n'est appelé par
> aucune tâche Celery ni aucune vue. Le moteur est prêt, il n'est pas branché au
> parcours utilisateur.

---

> **Addendum du 9 août 2026 — branchement BR-A (décisions D1-D2 du
> cahier PLAN/archive/cahiers-des-charges/branchement-moteur-ancrage-cahier-des-charges.md)** :
>
> 1. **Le flag moteur est un CHAMP explicite** (`Page.moteur`, choices
>    ancien/element, défaut ancien, migration core.0053) — jamais le
>    discriminant implicite `elements.exists()`, qui prendrait une
>    ingestion ELEMENT échouée (zéro élément) pour une page ANCIEN. Le
>    flag est posé au point de passage unique de l'ingestion
>    (`creer_les_elements_d_une_page`).
> 2. **L'existant reste intégralement ANCIEN** (§ 9.2 à la lettre) — y
>    compris les **537 pages sur 541 du dev qui portent déjà des
>    éléments DORMANTS** (ingérés par les phases de test du moteur, le
>    flux réel ne les lit pas). Découverte du 9 août : la reconversion
>    § 9.5 sera quasi gratuite pour elles (les éléments existent), mais
>    elle reste une décision explicite par carnet, jamais un effet de
>    migration.
> 3. **Ordre de bascule des flux (D2)** : import FICHIER d'abord
>    (BR-B), capture web ensuite, AUDIO en dernier — après la mesure de
>    la frontière préférentielle (question ouverte n°1).

---

> **Addendum du 9 août 2026 — branchement BR-B (import de fichier)** :
>
> 1. **Types couverts** : `.pdf`, `.docx`, `.md`, `.pptx`, `.xlsx`
>    (`fichier_couvert_par_docling`). Le `.txt` n'a pas de structure à
>    découper : repli intégral sur l'ancien pipeline, toast honnête. Le
>    `.json` de transcription garde son pipeline dédié.
> 2. **Double écriture de transition** (précision au § 9) : pour un type
>    couvert, le pipeline synchrone existant continue de remplir
>    `html_readability` — l'affichage reste celui de l'ANCIEN moteur
>    jusqu'à BR-D, où `lecture_principale` sera routée vers
>    `rendu_elements`. La page devient `moteur=element` dès que la tâche
>    `ingerer_un_fichier_avec_docling` aboutit (flag BR-A). Une
>    ingestion qui échoue laisse donc une page ANCIEN parfaitement
>    lisible : dégradation silencieuse assumée, tracée dans le journal
>    Celery.
> 3. Vérifié en réel le 9 août : page 674 (import `.md`), 4 éléments,
>    ingestion par le vrai worker — première page ELEMENT née du flux
>    réel en dev.

---

> **Addendum du 9 août 2026 — branchement BR-C (analyse)** :
>
> 1. **Routage** : la vue `analyser` crée toujours le même
>    ExtractionJob ; seule la tâche lancée dépend de `page.moteur` —
>    `analyser_une_page_avec_le_moteur_element` pour ELEMENT,
>    `analyser_page_task` sinon. Même retour utilisateur : le moteur est
>    un détail d'implémentation.
> 2. **M6 tranché — coexistence des jobs** : la relance d'analyse ne
>    purge PAS les jobs précédents (même sémantique que l'ancien
>    moteur). La promesse § 4.2 de SPEC-synthese est tenue par les
>    gardes existantes : le bloc `nettoyer_ia` de la vue refuse AVANT
>    toute purge (et avant l'appel LLM) si une dirigée cite les
>    extractions, et la ré-analyse d'un même job (chemin ELEMENT) porte
>    sa propre garde § 4.2 avant sa purge interne.
> 3. **Écarts § 4.2 assumés (pas corrigés)** pour le branchement
>    initial : pas de compteur de tokens (le bilan compte chunks et
>    extractions), boucle séquentielle sur les chunks (une VERTU sur un
>    hôte 8 Go partagé — cohérente avec la file Docling à concurrence
>    1), `suppress_parse_errors` au lieu de la récupération fine du
>    JSON tronqué. À réévaluer quand le moteur ANCIEN sera retiré.
> 4. Vérifié en réel le 9 août : job 938 sur la page 674 —
>    `raw_result.moteur='element'`, 1 chunk, LLM réel, 2,9 s.
>    La fenêtre « analyse ANCIEN sur page ELEMENT » (relecture BR-B,
>    défaut n°4) s'est refermée AVANT toute analyse réelle : aucun job
>    d'offsets n'existe sur une page ELEMENT.
> 5. **Relecture BR-C appliquée** : battement de cœur par chunk dans
>    l'analyse ELEMENT (le juge de blocage de la vue tolère désormais
>    90 min pour un job PENDING en file, 5 min sans battement pour un
>    PROCESSING) ; et `analyser_page_task` revalide `page.moteur` à
>    l'exécution — un job lancé pendant une ingestion Docling est
>    délégué au moteur ELEMENT au lieu d'écrire des offsets sans
>    portions.

---

> **Addendum du 9 août 2026 — branchement BR-D (affichage)** :
>
> 1. **Le branchement de la lecture passe par un tag de template**
>    (`front/templatetags/rendu_moteur.py`, `blocs_de_lecture_de`),
>    appelé dans `lecture_principale.html` — le partial est rendu
>    depuis plus de six contextes de vue, un tag couvre tout d'un coup
>    (précédent : corpus_permissions). Partial dédié
>    `_blocs_elements.html` : balise par label, listes regroupées,
>    marques `mark.portion.hl-extraction` par portion (markup figé par
>    test_rendu_elements, compatible avec les tokens de la maquette).
> 2. **Repli sûr** : zéro bloc (page ANCIEN, ou ELEMENT à zéro élément
>    après une ingestion échouée) → `html_annote`/`html_readability`
>    comme avant. Jamais de page blanche.
> 3. **Les éléments masqués ne sont pas rendus** dans la lecture ; les
>    voir et les démasquer est l'affaire de BR-E (ElementViewSet).
> 4. Vérification visuelle au navigateur réel (9 août, clair + sombre) :
>    conforme, avec deux corrections nées du passage `span`→`mark` —
>    reset des défauts navigateur de `<mark>` (texte MarkText,
>    fond Mark fluo sur les statuts sans règle, dont `non_pertinent`)
>    dans maquette.css. Écart de parti pris consigné : surlignage
>    permanent (décision T7) là où l'étalon révèle au survol.

---

> **Addendum du 10 août 2026 — branchement BR-E (endpoints élément)** :
>
> 1. `ElementViewSet` vit dans `hypostasis_extractor/views_element.py`
>    (§ 7 de la spec), enregistré sous `/elements/<pk>/…` dans
>    front/urls.py. **Adressage par pk**, pas par identifiant_stable :
>    le rendu BR-D expose `data-element-id={{ element.pk }}`, et
>    l'identifiant stable reste l'affaire des ancres, pas des URL.
> 2. La fusion est exposée comme `fusionner_avec_le_suivant` (une seule
>    cible possible, l'élément d'ordre + 1) : l'UX la plus simple pour
>    l'opération n°1 sur une diarisation, et l'adjacence est garantie
>    par construction.
> 3. Verrou § 7 posé dans la vue (`select_for_update` sur la ou les
>    lignes AVANT le service) — le défaut de concurrence consigné le
>    8 août est soldé. Les gardes des services remontent en 409 avec
>    leur message FALC ; le journal des corrections de texte va dans
>    PageEdit (type contenu), celui des opérations de structure reste
>    dans ElementOperation (créé par les services).

> **Addendum du 10 août 2026 — question ouverte n°1 TRANCHÉE par la
> mesure (D3 du cahier de branchement)** :
>
> Mesure sur les 24 transcriptions diarisées réelles de la base dev
> (2 153 tours de parole) — protocole et chiffres complets dans
> `PLAN/mesure-D3-frontiere-audio-2026-08-10.md` :
>
> 1. **Pas de frontière préférentielle au changement de locuteur** :
>    +12,6 % d'appels LLM pour un gain de 2 points (chunks
>    multi-locuteurs 59,3 % → 57,3 %). Un tour médian fait 125
>    caractères : un chunk en contient toujours plusieurs, c'est
>    l'ancre M2M qui porte l'attribution au locuteur (§ 4.1, même
>    conclusion que côté sections). Le chunking audio est au budget
>    seul.
> 2. **L'élément audio est le TOUR DE PAROLE** (segments ASR
>    consécutifs d'un même locuteur), jamais le segment : éléments =
>    segments produirait 605 coupes en plein tour sur ce corpus (85 %
>    des frontières internes), zéro avec les tours.
> 3. **Un tour au-delà du budget de chunk (1 500 c — 6,5 % des tours,
>    max observé 34 715 c) est scindé À L'INGESTION** en éléments
>    consécutifs du même locuteur, coupe posée à la frontière de
>    segment ASR la plus proche du budget. La règle « jamais couper un
>    élément » reste entière en aval.

---

> **Addendum du 10 août 2026 — U4 : bascule de la CAPTURE WEB
> (décision D2, ordre 2)** :
>
> Après l'import fichier (BR-B), la capture web (extension navigateur,
> `POST /api/pages/`) nourrit à son tour le moteur ELEMENT, sur le même
> patron :
> 1. La source est `page.html_original` (le HTML capturé), pas un
>    fichier sur disque : Docling convertit un `DocumentStream` nommé
>    `.html` (`convertir_du_html_avec_docling`,
>    `ingerer_une_capture_web`).
> 2. La tâche `ingerer_une_capture_web_avec_docling` partage la file
>    dédiée `ingestion_docling` (concurrence 1) — une seule conversion
>    à la fois sur l'hôte 8 Go, fichier ou HTML confondus.
> 3. Double écriture de transition : le pipeline synchrone remplit
>    `html_readability`, l'affichage reste ANCIEN jusqu'à ce que les
>    éléments existent ; un échec laisse une page ANCIEN lisible (repli
>    honnête), l'état d'ingestion (U2) le dit et permet la relance.

---

## 0. Ce qui change par rapport à la v1, et pourquoi

La v1 a été relue par un agent adverse (`RELECTURE-spec-ancrage.md`). Cinq défauts structurels rendaient la v1 non codable telle quelle. La v2 les corrige un par un.

| # | Défaut trouvé en v1 | Correction en v2 |
|---|---|---|
| 1 | Une extraction ne peut ancrer qu'**un seul élément** — or 7,5 % des extractions d'une phrase, 76 % de deux phrases, enjambent déjà ≥2 éléments Docling | **Ancre M2M** : une extraction pointe vers *N* éléments, chacun avec sa portion locale |
| 2 | Migration 3→4 : `IntegrityError` garanti (le plan lui-même projette des échecs, puis rend le champ non-nullable) | **Abandon de la migration de données.** Nouveau moteur, base vierge, fixtures. Aucune donnée existante n'est convertie automatiquement |
| 3 | Verrou de scellement stocké dans un champ calculé → course, contradiction, re-render périmé | **Le scellement est supprimé entièrement** (YAGNI, décision utilisateur). Plus de course, plus de champ calculé qu'on réécrit à la main |
| 4 | Insertion et fusion d'éléments interdites, alors que « recoller un tour de parole scindé » est l'opération n°1 sur une vraie diarisation | **Moteur scission/fusion/ajout** avec recalcul d'ancre, § 5 |
| 5 | `SourceLink` oublié, fork LangExtract passé sous silence, collision de vocabulaire « orpheline » | `SourceLink` intégré au pipeline (§ 7) ; le fork est réduit, pas supprimé (§ 6) ; l'état renommé `DETACHEE` |

**Ce qui ne change pas** : le principe d'ancrage local, le volet source PDF/audio, la conversion de coordonnées bbox, le curseur de lecture audio. Ces parties sont reprises de la v1 en §§ 8-9 avec les seules corrections identifiées par la relecture (PDF.js `convertToViewportRectangle`, `devicePixelRatio`, `prov` en liste).

---

## 1. Objet

Remplacer l'ancrage par offsets caractères dans un texte plat par un **ancrage par élément de document**, avec une **ancre multi-éléments** pour les extractions qui enjambent plusieurs paragraphes, et un **moteur de structure** (scission, fusion, ajout) qui recalcule les ancres au lieu d'interdire toute évolution du document.

### Principes

1. **Un seul pivot** : le `DoclingDocument`, stocké en JSON. L'HTML est un rendu régénérable.
2. **L'ancre est locale et peut être multiple.** Une extraction pointe vers un ensemble ordonné d'éléments, chacun avec l'offset de sa portion. Jamais d'offset dans un texte global.
3. **La structure peut évoluer**, mais par des opérations nommées et tracées — scission, fusion, ajout, masquage — jamais par une édition qui déplace silencieusement des ancres.
4. **Rien ne disparaît en silence.** Une extraction qu'on ne peut plus ancrer est marquée `DETACHEE`, pas effacée. Un élément qu'on retire du contenu utile est `masque`, pas supprimé.
5. **Le chunking respecte les éléments par obligation, les frontières de section par préférence.** Mesuré : aligner sur les éléments coûte +1 appel LLM sur 30 et élimine 100 % des éléments coupés en deux. Préférer les frontières de section/locuteur n'apporte qu'un gain marginal au-delà d'un plancher de 900 caractères — ce n'est donc qu'une préférence, jamais une contrainte dure (voir § 4, l'historique de cette décision est dans la conversation qui a produit cette spec).

---

## 2. Modèle de données

### 2.1 `ElementDocument`

```python
class EtatElement(models.TextChoices):
    """
    Le regime d'edition d'un element depend de ce qui s'y est attache.
    / Editing regime of an element depends on what is attached to it.

    Cet etat n'est JAMAIS saisi a la main. Il est recalcule par un signal.
    Il n'y a plus d'etat SCELLE : le scellement a ete abandonne (YAGNI).
    / There is no more SCELLE state: sealing was dropped (YAGNI).
    """
    LIBRE = "libre", "Libre — aucune extraction"
    ANALYSE = "analyse", "Analysé — extractions sans commentaire"
    DEBATTU = "debattu", "Débattu — des commentaires sont attachés"


class ElementDocument(models.Model):
    """
    Un element adressable du document : un paragraphe, un titre, un item de
    liste, un tableau, ou un tour de parole dans une transcription.
    / An addressable element of the document.

    LOCALISATION : core/models.py

    C'est l'unite d'ancrage. Une extraction ne pointe plus dans le texte
    global de la page : elle pointe vers un ou plusieurs ElementDocument,
    via la table de liaison AncrageExtraction (§ 2.2).

    identifiant_stable est NOTRE identifiant, pas le self_ref Docling
    ("#/texts/4"), qui est un index positionnel et glisserait si la
    structure changeait. Toutes les ancres, tous les liens externes,
    pointent identifiant_stable — jamais l'ordre ni le self_ref.
    """

    page = models.ForeignKey(
        "Page",
        on_delete=models.CASCADE,
        related_name="elements",
        verbose_name="Page qui contient cet element",
    )

    identifiant_stable = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Notre identifiant. Ne change jamais, meme apres scission "
                  "ou fusion — c'est ce a quoi toute ancre se refere.",
    )

    reference_docling = models.CharField(
        max_length=64,
        blank=True,
        help_text="Le self_ref d'origine, ex '#/texts/4'. Indicatif seulement, "
                  "jamais utilise comme cle.",
    )

    ordre = models.PositiveIntegerField(
        help_text="Position dans le document, 0, 1, 2, 3... Renumerote "
                  "librement a chaque scission/fusion/ajout : rien d'autre "
                  "ne depend de sa valeur numerique que le tri.",
    )

    label = models.CharField(
        max_length=32,
        help_text="Label Docling : text, section_header, title, list_item, "
                  "table, formula, code...",
    )

    texte = models.TextField(
        help_text="Le texte de cet element. C'est ici qu'on ancre.",
    )

    empreinte_contenu = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA256 du texte normalise (espaces ecrases, minuscules). "
                  "Utilise par le moteur d'ajout (§ 5.3) pour reconnaitre "
                  "un element inchange lors d'une re-ingestion.",
    )

    chemin_de_section = models.JSONField(
        default=list,
        help_text="Titres parents au moment de l'ingestion, ex "
                  "['Introduction', '1) Le calcul des IA']. Instantane, "
                  "pas re-derive automatiquement apres une scission de titre.",
    )

    provenance = models.JSONField(
        default=dict,
        help_text="Provenance physique, selon la source :\n"
                  "PDF   -> {page_no, boites: [{l,t,r,b,coord_origin}, ...]}\n"
                  "       (LISTE de boites : un paragraphe a cheval sur deux\n"
                  "       pages ou deux colonnes produit plusieurs entrees)\n"
                  "audio -> {start_time, end_time, voice}\n"
                  "md/html/txt -> {}",
    )

    etat = models.CharField(
        max_length=16,
        choices=EtatElement.choices,
        default=EtatElement.LIBRE,
        help_text="Recalcule par signal. Ne jamais assigner a la main.",
    )

    masque = models.BooleanField(
        default=False,
        help_text="Element retire du contenu utile sans etre supprime. "
                  "Cas reel : Voxtral hallucine un segment (bruit, musique, "
                  "doublon). Reversible, trace dans ElementOperation (§ 5.4).",
    )

    element_parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="elements_issus_d_une_operation",
        help_text="Si cet element vient d'une scission ou d'une fusion, "
                  "l'element (ou l'un des elements) d'origine. Indicatif, "
                  "l'historique complet est dans ElementOperation.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page", "ordre"]
        constraints = [
            models.UniqueConstraint(
                fields=["page", "ordre"],
                name="unicite_ordre_dans_la_page",
            ),
        ]
```

**Ce qui a été retiré par rapport à la v1**, avec la raison :

- Les multiples de 100 sur `ordre` — la relecture a montré qu'aucune ancre n'en dépend (elles pointent `identifiant_stable`), et que le schéma de gap s'épuise après six scissions au même endroit. Renuméroter à chaque opération est sans risque et plus simple.
- L'état `SCELLE` et tout ce qui en dépendait (champ verrou séparé, courses, `sceller`/`desceller`).
- `provenance.bbox` (singulier) devient `provenance.boites` (liste), suivant le point de la relecture sur les paragraphes à cheval sur deux pages.

### 2.2 `AncrageExtraction` — la table qui porte le M2M

C'est la pièce centrale de la v2. En v1, `ExtractedEntity.element` était une simple `ForeignKey` : une extraction, un élément. Mesuré sur le document de test, ça échoue déjà à 7,5 % pour une extraction d'une phrase. La v2 remplace cette FK par une table de liaison ordonnée.

```python
class EtatAncrage(models.TextChoices):
    """
    Est-ce qu'on retrouve encore, ELEMENT PAR ELEMENT, le passage source
    d'une portion d'extraction ?
    / Can we still locate, per element, the source passage of a portion?

    Renomme depuis la v1 : ORPHELINE -> DETACHEE, parce que "orpheline"
    designe deja une PAGE sans dossier ailleurs dans le code et les tests
    (front/tests/e2e/test_01_navigation.py:34). Collision de vocabulaire
    trouvee par la relecture.
    """
    EXACTE = "exacte", "Exacte — position calculee au premier ancrage"
    RETROUVEE = "retrouvee", "Retrouvée — repositionnee apres une edition"
    DETACHEE = "detachee", "Détachée — le passage source a change"


class AncrageExtraction(models.Model):
    """
    Une PORTION d'une extraction, dans UN element.
    / One PORTION of an extraction, within ONE element.

    LOCALISATION : hypostasis_extractor/models.py

    Une ExtractedEntity qui tient dans un seul element a UNE seule ligne
    AncrageExtraction. Une ExtractedEntity dont le span LangExtract
    enjambe trois elements (une liste a puces, par exemple) a TROIS
    lignes, ordre 0, 1, 2, qui mises bout a bout reconstituent le texte
    extrait — a l'exception des separateurs de jonction (les "\n\n" entre
    elements), qui n'appartiennent a aucune portion.

    C'est pourquoi le surlignage produit N balises <mark>, pas une seule
    qui traverserait deux <p> : le modele de donnees suit exactement ce
    que le rendu HTML doit de toute facon faire.
    """
    extraction = models.ForeignKey(
        "ExtractedEntity",
        on_delete=models.CASCADE,
        related_name="ancrages",
    )
    element = models.ForeignKey(
        "core.ElementDocument",
        on_delete=models.PROTECT,        # on ne supprime jamais un element porteur
        related_name="portions_d_extractions",
    )
    ordre_dans_extraction = models.PositiveSmallIntegerField(
        help_text="0 pour la premiere portion (la plus a gauche dans le "
                  "document), 1 pour la suivante, etc.",
    )
    debut_dans_element = models.PositiveIntegerField()
    fin_dans_element = models.PositiveIntegerField()
    etat_ancrage = models.CharField(
        max_length=16,
        choices=EtatAncrage.choices,
        default=EtatAncrage.EXACTE,
    )

    class Meta:
        ordering = ["extraction", "ordre_dans_extraction"]
        constraints = [
            models.UniqueConstraint(
                fields=["extraction", "ordre_dans_extraction"],
                name="unicite_ordre_dans_l_extraction",
            ),
        ]

    def texte_de_la_portion(self) -> str:
        """Relit le texte de cette portion depuis l'element, a la demande."""
        return self.element.texte[self.debut_dans_element:self.fin_dans_element]
```

**Bornes réalistes** : sur le document mesuré, la plus grosse section fait 24 éléments. Une extraction couvrant une section entière donnerait une ancre à 24 lignes — cas extrême, pas empêché par le modèle, mais à surveiller : le § 8.3 (surlignage) prévoit explicitement l'affichage de *N* portions dans la colonne de lecture.

**Ce que `ExtractedEntity` garde** : `extraction_text` (le texte complet retourné par LangExtract, pour affichage et recherche), `job`, `hypostase`, `statut_debat`, etc. — inchangé. Ce qui disparaît : `element` (FK directe), `start_char`/`end_char`, `debut_dans_element`/`fin_dans_element` (déplacés dans `AncrageExtraction`).

### 2.3 L'algorithme d'intersection *a posteriori*

C'est la pièce qui transforme un span LangExtract (des offsets dans le texte du *chunk* envoyé au LLM) en une ou plusieurs lignes `AncrageExtraction`.

```python
def decouper_le_span_en_portions_par_element(
    span_dans_le_chunk: tuple[int, int],
    elements_du_chunk: list["ElementDocument"],
    offsets_des_elements_dans_le_chunk: dict[int, tuple[int, int]],
) -> list[dict]:
    """
    Prend le span brut renvoye par LangExtract (des offsets dans le texte
    du chunk, PAS dans un element), et le decoupe en portions, une par
    element traverse.
    / Takes the raw span returned by LangExtract (offsets in the CHUNK's
    text, NOT in an element), and splits it into portions, one per
    crossed element.

    LOCALISATION : hypostasis_extractor/services/ancrage.py

    Le chunk est construit par concatenation des textes d'elements avec
    un separateur "\n\n" (§ 4). offsets_des_elements_dans_le_chunk donne,
    pour chaque element, sa position (debut, fin) DANS CE CHUNK — c'est
    la meme table de positions que celle utilisee pour construire le
    chunk, on ne la recalcule pas.

    Cas traites :
      1. Le span tient entierement dans un element -> UNE portion.
      2. Le span traverse 2+ elements -> UNE portion par element traverse,
         les separateurs de jonction "\n\n" tombent dans les "trous"
         entre deux positions d'element et sont exclus des portions.
      3. Le span commence ou finit dans un separateur (rare, LangExtract
         aligne rarement au milieu d'un espace) -> on rogne aux bornes
         de l'element le plus proche.
    """
    debut_span, fin_span = span_dans_le_chunk
    portions = []
    numero_de_portion = 0

    for element in elements_du_chunk:
        debut_element_dans_chunk, fin_element_dans_chunk = (
            offsets_des_elements_dans_le_chunk[element.pk]
        )

        # Intersection entre [debut_span, fin_span) et
        # [debut_element_dans_chunk, fin_element_dans_chunk)
        debut_intersection = max(debut_span, debut_element_dans_chunk)
        fin_intersection = min(fin_span, fin_element_dans_chunk)

        chevauchement_reel = fin_intersection > debut_intersection
        if not chevauchement_reel:
            continue

        portions.append({
            "element": element,
            "ordre_dans_extraction": numero_de_portion,
            "debut_dans_element": debut_intersection - debut_element_dans_chunk,
            "fin_dans_element": fin_intersection - debut_element_dans_chunk,
        })
        numero_de_portion += 1

    return portions
```

**Cas non trivial signalé par la relecture** : quand un élément dépasse le budget de chunk, le chunker peut produire un chunk qui est une *sous-chaîne* de l'élément (pas l'inverse). L'algorithme ci-dessus fonctionne dans les deux sens : `offsets_des_elements_dans_le_chunk` porte, pour cet élément découpé, les bornes de la portion réellement présente dans le chunk — pas 0 à `len(element.texte)`.

**Recomposition pour l'affichage** : `extraction.ancrages.all()` donne les portions dans l'ordre. La concaténation de leurs `texte_de_la_portion()` **n'est pas** égale à `extraction_text` au caractère près (les séparateurs de jonction manquent) — c'est documenté, assumé, et sans conséquence : `extraction_text` sert à l'affichage de la carte dans le drawer, les portions servent au surlignage dans le document.

### 2.4 `SourceLink` — reconnecté

La v1 l'avait complètement oublié. `SourceLink` (`core/models.py:1316`) est le mécanisme par lequel une synthèse peut remonter jusqu'à l'extraction, donc jusqu'au passage source, qui l'a alimentée. Il ancrait par `start_char_cible`/`end_char_cible` — le système que la v2 abandonne.

```python
# Champs modifies sur SourceLink :

# AVANT (v1, jamais peuple, offsets plats) :
#   start_char_cible = models.PositiveIntegerField(...)
#   end_char_cible = models.PositiveIntegerField(...)

# APRES (v2) : le lien pointe une PORTION d'ancrage, pas un offset plat.
ancrage_source = models.ForeignKey(
    "hypostasis_extractor.AncrageExtraction",
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name="liens_de_provenance",
    help_text="La portion d'extraction precise qui a alimente ce passage "
              "de synthese. Remplace start_char_source/end_char_source.",
)
```

`extraction_source` (déjà présent) reste la FK vers l'`ExtractedEntity` entière — utile pour "quelle extraction", `ancrage_source` répond à "quel élément précisément, avec quel offset local". La génération de `SourceLink` elle-même (quand une synthèse V2 cite une extraction) est hors du périmètre de cette spec — c'est la **spec opposabilité** mentionnée en clôture de la conversation, qui vient après celle-ci.

---

## 3. Régime d'édition — la matrice, sans scellement

| Opération | LIBRE | ANALYSÉ | DÉBATTU |
|---|:---:|:---:|:---:|
| Corriger le texte | ✅ | ✅ + réconciliation | ✅ + justification + notification |
| Scinder l'élément (§ 5.1) | ✅ | ✅ + recalcul d'ancres | ✅ + justification |
| Fusionner deux éléments adjacents (§ 5.2) | ✅ | ✅ + recalcul d'ancres | ✅ + justification |
| Masquer l'élément (§ 5.4) | ✅ | ✅ + avertissement | ✅ + justification |
| Renommer le locuteur | ✅ | ✅ | ✅ |
| Ajouter une note hors-texte | ✅ | ✅ | ✅ |
| Insérer un élément au milieu du document | ❌ | ❌ | ❌ |

**Ce qui a disparu par rapport à la v1** : les deux lignes `Sceller`/`Desceller`, et la colonne `SCELLÉ`. Décision utilisateur : « pour le praxis, si c'est trop complexe avec le verrou, on le saute. YAGNI. On scelle pas. » Ça règle d'un coup trois des points de la relecture : le verrou dans un champ calculé, la course signal/scellement, et le scellement en masse sans garde-fou.

**Ce qui change de statut** : fusion et masquage passent de `❌` (v1) à `✅` (v2). La relecture avait montré que l'interdiction de fusion serait intenable sur une vraie diarisation (« recoller un tour de parole scindé est l'opération n°1 »), et que l'invariant « rien ne se supprime » se heurte au bruit halluciné par la transcription. Les deux sont désormais des opérations nommées, tracées, réversibles — pas des suppressions.

**Ce qui reste interdit** : insérer un élément de contenu nouveau au milieu du document. C'était la ligne de la v1 la mieux justifiée (l'invariant structurel) et rien dans l'exploration n'a changé cet avis. La seule façon légitime de faire grossir la structure est l'**ajout par re-ingestion** (§ 5.3), qui opère au périmètre reconnu par un diff de contenu, jamais par une insertion manuelle arbitraire.

---

## 4. Pipeline d'ingestion et chunking

```
    fichier source (immuable, dans source_file)
              │
              ▼
     docling-serve (tache Celery)  ──►  DoclingDocument (JSON)
              │
              ▼
     HierarchicalChunker           ──►  N × ElementDocument
              │                          (texte, label, provenance, empreinte)
              ▼
   ┌──────────────────────────────────────────────────────────┐
   │  CONSTRUCTION DES CHUNKS — alignement obligatoire,        │
   │  frontieres preferees, jamais imposees                    │
   └──────────────────────────────────────────────────────────┘
              │
              ▼
       analyser_page_task            ──►  N × ExtractedEntity
                                           + M × AncrageExtraction
                                           (intersection a posteriori, § 2.3)
```

### 4.1 Construction des chunks

```python
BUDGET_MAXIMUM_PAR_CHUNK = 1500      # inchange depuis la v1 / front/tasks.py:1050
PLANCHER_AVANT_COUPURE_PREFEREE = 900


def construire_les_chunks(elements_de_la_page: list["ElementDocument"]) -> list[dict]:
    """
    Construit les chunks a envoyer a LangExtract.
    / Builds the chunks to send to LangExtract.

    LOCALISATION : hypostasis_extractor/services/chunking.py

    DEUX REGLES, DE PRIORITE DIFFERENTE :

      1. OBLIGATOIRE — on ne coupe JAMAIS au milieu d'un element. Mesure :
         ca coute 1 appel LLM de plus sur 30 (documents de test), et ca
         elimine 100% des elements coupes en deux (6/6 sur le document
         de test avec le chunker aveugle actuel).

      2. PREFERENCE — si un element ouvre un nouveau sous-titre ET que le
         chunk en cours depasse deja PLANCHER_AVANT_COUPURE_PREFEREE, on
         coupe la, meme si le budget n'est pas encore atteint. Mesure :
         le gain est marginal (27-28 chunks a cheval sur 2 sections, avec
         ou sans cette preference, une fois l'alignement sur les elements
         garanti) — ce n'est PAS elle qui protege contre l'enjambement
         dangereux. C'est l'ancre M2M (§ 2.2-2.3) qui le fait, en stockant
         chaque portion avec l'element (donc le locuteur, donc la section)
         dont elle vient reellement.

    Une precedente version de cette regle rendait la frontiere de section
    OBLIGATOIRE (jamais de chunk a cheval sur un sous-titre). Rejetee :
    sur le document de test, 7 "sous-titres" sur 63 sont en realite des
    intros de liste ("L'IA ne doit pas remplacer :", "Chaque annee :").
    En frontiere dure, ces 7 intros sont coupees de leur liste, et le LLM
    lit des puces sans savoir de quoi elles sont la liste — exactement le
    defaut que l'ancre M2M existe pour eviter, reintroduit par la
    frontiere elle-meme. D'ou : preference, jamais obligation.
    """
    chunks = []
    elements_du_chunk_en_cours = []

    def taille_si_on_ajoute(element):
        if not elements_du_chunk_en_cours:
            return len(element.texte)
        premier = elements_du_chunk_en_cours[0]
        return (element.position_fin_dans_page - premier.position_debut_dans_page)

    def cloturer():
        if elements_du_chunk_en_cours:
            chunks.append({
                "elements": list(elements_du_chunk_en_cours),
                "texte": "\n\n".join(e.texte for e in elements_du_chunk_en_cours),
            })

    for element in elements_de_la_page:
        if element.masque:
            continue

        if elements_du_chunk_en_cours:
            taille_actuelle = (
                elements_du_chunk_en_cours[-1].position_fin_dans_page
                - elements_du_chunk_en_cours[0].position_debut_dans_page
            )
            budget_depasse = taille_si_on_ajoute(element) > BUDGET_MAXIMUM_PAR_CHUNK
            ouvre_une_section = element.label == "section_header"
            coupure_preferee = (
                ouvre_une_section and taille_actuelle >= PLANCHER_AVANT_COUPURE_PREFEREE
            )
            if budget_depasse or coupure_preferee:
                cloturer()
                elements_du_chunk_en_cours = []

        elements_du_chunk_en_cours.append(element)

    cloturer()
    return chunks
```

**Cas audio — question ouverte, pas tranchée dans cette spec.** La même préférence (couper à un changement de `voice`) s'appliquerait en principe, mais elle n'a pu être mesurée que sur un extrait de 3 tours de parole (`essai.vtt`), trop court pour conclure. Il faudra vérifier sur une vraie transcription diarisée si un tour de parole correspond en général à un seul élément Docling — si oui, le problème se pose rarement en pratique. À trancher avant la phase G de l'implémentation (§ 10), pas avant.

### 4.2 Ce qui reste du fork LangExtract

La relecture a montré que « le fork disparaît » était survendu. Ce qui disparaît réellement : la copie locale de `_annotate_documents_single_pass`, si la boucle d'annotation est reprise par Hypostasia et que le découpage en chunks est fait en amont (§ 4.1) plutôt que par `ChunkIterator`.

Ce qui **reste nécessaire**, repris du fork existant (`front/tasks.py:183-544`) :

- La récupération de JSON tronqué (`_recuperer_extractions_json_corrompu`) — un `response_schema` structuré peut quand même être tronqué à `max_output_tokens`, ce n'est pas résolu par le nouveau moteur.
- Le compteur de tokens par appel.
- `resolver.resolve()` / `resolver.align()` de LangExtract restent utilisés pour produire le span brut dans le chunk — c'est ce span qui alimente `decouper_le_span_en_portions_par_element` (§ 2.3). La dépendance à LangExtract ne disparaît pas, elle se déplace vers une surface plus stable de son API.
- La parallélisation (`batch_length=5`) devient à réécrire côté Celery (`group()` de tâches), ce n'est pas gratuit.

---

## 5. Le moteur scission / fusion / ajout

C'est la pièce commandée explicitement : « il nous faut ce moteur de séparation fusion et ajout puis recalcul des ancres ». Les trois opérations partagent un principe : **le contenu total ne change jamais**, seule la façon dont il est découpé en éléments change — sauf l'ajout, qui est le seul cas où du contenu nouveau apparaît, et uniquement par re-ingestion, jamais par saisie manuelle au milieu du document.

### 5.1 Scission

```python
def scinder_un_element(element: "ElementDocument", position_de_coupe: int) -> tuple:
    """
    Coupe un element en deux au caractere indique, et redistribue les
    portions d'ancrage qui le traversaient.
    / Splits an element in two at the given character, and redistributes
    the anchor portions that crossed it.

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    Cas reel qui motive cette operation : Voxtral fusionne deux tours de
    parole en un seul element, ou attribue mal un locuteur au milieu d'un
    segment. On coupe, on renomme le second morceau au bon locuteur.

    TROIS CAS pour chaque AncrageExtraction qui pointait l'element original :

      1. La portion finit avant la coupe (fin_dans_element <= position) :
         elle reste entiere, rattachee au PREMIER morceau, offsets inchanges.

      2. La portion commence apres la coupe (debut_dans_element >= position) :
         elle reste entiere, rattachee au SECOND morceau, offsets decales
         de -position.

      3. La portion CHEVAUCHE le point de coupe : elle est elle-meme
         scindee en DEUX portions, une par morceau, avec un ordre_dans_
         extraction recalcule pour toute l'extraction. C'est exactement
         le mecanisme qui gerait deja l'enjambement de plusieurs elements
         Docling d'origine (§ 2.3) — la scission manuelle n'est qu'un
         nouveau cas du meme algorithme, pas un cas special.
    """
    texte_original = element.texte

    premier_morceau = ElementDocument.objects.create(
        page=element.page,
        ordre=element.ordre,           # renumerotation globale ensuite
        label=element.label,
        texte=texte_original[:position_de_coupe],
        provenance=element.provenance,  # a affiner manuellement si PDF/audio
        empreinte_contenu=empreinte_du_texte(texte_original[:position_de_coupe]),
        element_parent=element,
    )
    second_morceau = ElementDocument.objects.create(
        page=element.page,
        ordre=element.ordre + 1,
        label=element.label,
        texte=texte_original[position_de_coupe:],
        provenance=element.provenance,
        empreinte_contenu=empreinte_du_texte(texte_original[position_de_coupe:]),
        element_parent=element,
    )

    with transaction.atomic():
        for portion in AncrageExtraction.objects.select_for_update().filter(element=element):
            _redistribuer_une_portion(
                portion, position_de_coupe, premier_morceau, second_morceau,
            )
        element.delete()   # PROTECT sur AncrageExtraction.element garantit
                            # qu'on ne peut arriver ici que si tout a ete redistribue
        _renumeroter_les_elements_de_la_page(premier_morceau.page)

    return premier_morceau, second_morceau


def _redistribuer_une_portion(portion, position_de_coupe, premier_morceau, second_morceau):
    """Applique les trois cas decrits ci-dessus a une portion d'ancrage."""
    if portion.fin_dans_element <= position_de_coupe:
        portion.element = premier_morceau
        portion.save(update_fields=["element"])
        return

    if portion.debut_dans_element >= position_de_coupe:
        portion.element = second_morceau
        portion.debut_dans_element -= position_de_coupe
        portion.fin_dans_element -= position_de_coupe
        portion.save(update_fields=["element", "debut_dans_element", "fin_dans_element"])
        return

    # Cas 3 : chevauchement — la portion devient deux portions.
    portions_suivantes = AncrageExtraction.objects.filter(
        extraction=portion.extraction,
        ordre_dans_extraction__gt=portion.ordre_dans_extraction,
    )
    portions_suivantes.update(ordre_dans_extraction=F("ordre_dans_extraction") + 1)

    AncrageExtraction.objects.create(
        extraction=portion.extraction,
        element=second_morceau,
        ordre_dans_extraction=portion.ordre_dans_extraction + 1,
        debut_dans_element=0,
        fin_dans_element=portion.fin_dans_element - position_de_coupe,
        etat_ancrage=EtatAncrage.RETROUVEE,
    )
    portion.element = premier_morceau
    portion.fin_dans_element = position_de_coupe
    portion.etat_ancrage = EtatAncrage.RETROUVEE
    portion.save(update_fields=["element", "fin_dans_element", "etat_ancrage"])
```

### 5.2 Fusion

```python
def fusionner_deux_elements(premier: "ElementDocument", second: "ElementDocument") -> "ElementDocument":
    """
    Recolle deux elements ADJACENTS en un seul, et rattache toutes les
    portions d'ancrage a l'element fusionne.
    / Merges two ADJACENT elements into one, and reattaches every anchor
    portion to the merged element.

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    Contrainte : premier.ordre + 1 == second.ordre. On ne fusionne que
    des voisins immediats — fusionner deux elements distants n'a pas de
    sens (quel texte y aurait-il entre les deux ?).

    Les portions de `premier` gardent leurs offsets. Les portions de
    `second` sont decalees de len(premier.texte) + len(SEPARATEUR).
    Si une portion de `premier` finissait pile a la fin de son texte ET
    qu'une portion de `second`, sur la MEME extraction, commencait pile
    au debut du sien, elles sont coalescees en une seule portion (elles
    sont devenues contigues dans l'element fusionne) — optimisation, pas
    une obligation : le surlignage fonctionne identiquement avec deux
    portions adjacentes ou une seule.
    """
    SEPARATEUR = "\n\n"
    if second.ordre != premier.ordre + 1:
        raise ValueError("Seuls deux elements adjacents peuvent etre fusionnes.")

    decalage = len(premier.texte) + len(SEPARATEUR)
    texte_fusionne = premier.texte + SEPARATEUR + second.texte

    element_fusionne = ElementDocument.objects.create(
        page=premier.page,
        ordre=premier.ordre,
        label=premier.label,
        texte=texte_fusionne,
        provenance=_fusionner_les_provenances(premier.provenance, second.provenance),
        empreinte_contenu=empreinte_du_texte(texte_fusionne),
        element_parent=premier,
    )

    with transaction.atomic():
        AncrageExtraction.objects.select_for_update().filter(
            element=premier,
        ).update(element=element_fusionne, etat_ancrage=EtatAncrage.RETROUVEE)

        for portion in AncrageExtraction.objects.select_for_update().filter(element=second):
            portion.element = element_fusionne
            portion.debut_dans_element += decalage
            portion.fin_dans_element += decalage
            portion.etat_ancrage = EtatAncrage.RETROUVEE
            portion.save(update_fields=["element", "debut_dans_element", "fin_dans_element", "etat_ancrage"])

        _coalescer_les_portions_contigues(element_fusionne)
        premier.delete()
        second.delete()
        _renumeroter_les_elements_de_la_page(element_fusionne.page)

    return element_fusionne
```

### 5.3 Ajout — uniquement par re-ingestion

**Ce n'est pas une insertion manuelle.** C'est le cas du « gros pad collaboratif » exploré avant cette spec : un document source qui grossit (nouveau compte-rendu ajouté en haut, coquille corrigée en bas), et qu'on veut ré-analyser sans tout refaire.

```python
def reingerer_une_page(page: "Page", nouveau_contenu_source: str) -> dict:
    """
    Reconvertit une page dont le contenu source a change, et reconcilie
    les elements par empreinte de contenu plutot que par position.
    / Reconverts a page whose source content changed, reconciling
    elements by content fingerprint rather than by position.

    LOCALISATION : hypostasis_extractor/services/reingestion.py

    Mesure sur un pad de test (3 CR -> 3 CR + 1 nouveau + 1 correction) :
      - identification par INDEX : 8/8 des 8 premiers elements changent
        de sens, tout est a re-analyser.
      - identification par EMPREINTE : les elements identiques sont
        reconnus (memes ancres conservees), seuls les elements NOUVEAUX
        sont a analyser. Sur ce pad, 36% du contenu ; sur un pad reel de
        200 comptes-rendus ou un seul est ajoute par semaine, de l'ordre
        de 2%.

    C'est le SEUL mecanisme qui fait grandir la structure du document.
    Il n'agit qu'aux points reconnus par le diff de contenu — jamais par
    une position arbitraire choisie par un utilisateur en train d'editer.
    """
    nouveau_document = convertir_avec_docling(nouveau_contenu_source)
    nouveaux_elements_bruts = extraire_les_elements(nouveau_document)

    anciens_par_empreinte = {
        e.empreinte_contenu: e for e in page.elements.filter(masque=False)
    }
    nouveaux_par_empreinte = {
        empreinte_du_texte(e["texte"]): e for e in nouveaux_elements_bruts
    }

    empreintes_inchangees = set(anciens_par_empreinte) & set(nouveaux_par_empreinte)
    empreintes_disparues = set(anciens_par_empreinte) - set(nouveaux_par_empreinte)
    empreintes_apparues = set(nouveaux_par_empreinte) - set(anciens_par_empreinte)

    with transaction.atomic():
        # Les elements inchanges gardent leur identifiant_stable : leurs
        # ancres, leurs commentaires, leur etat restent valides sans y
        # toucher.
        for empreinte in empreintes_inchangees:
            ancien = anciens_par_empreinte[empreinte]
            nouveau = nouveaux_par_empreinte[empreinte]
            ancien.ordre = nouveau["ordre_dans_le_nouveau_document"]
            ancien.save(update_fields=["ordre"])

        # Les elements disparus : leurs extractions passent DETACHEE,
        # exactement comme une correction de texte classique (§ 6).
        for empreinte in empreintes_disparues:
            _detacher_les_extractions_de(anciens_par_empreinte[empreinte])
            anciens_par_empreinte[empreinte].masque = True
            anciens_par_empreinte[empreinte].save(update_fields=["masque"])

        # Les elements apparus sont crees, PUIS envoyes en analyse — c'est
        # le seul cas ou une nouvelle ExtractedEntity peut naitre sur une
        # page deja partiellement debattue.
        elements_a_analyser = []
        for empreinte in empreintes_apparues:
            brut = nouveaux_par_empreinte[empreinte]
            elements_a_analyser.append(ElementDocument.objects.create(
                page=page,
                ordre=brut["ordre_dans_le_nouveau_document"],
                label=brut["label"],
                texte=brut["texte"],
                provenance=brut["provenance"],
                empreinte_contenu=empreinte,
            ))

        _renumeroter_les_elements_de_la_page(page)

    return {
        "inchanges": len(empreintes_inchangees),
        "disparus": len(empreintes_disparues),
        "apparus": len(empreintes_apparues),
        "elements_a_analyser": elements_a_analyser,
    }
```

**Limite connue, assumée** : l'empreinte seule est ambiguë sur un contenu dupliqué (un même intitulé de section répété plusieurs semaines de suite). Une V2 de cette fonction pourrait combiner empreinte + position relative pour désambiguïser ; non nécessaire pour la première version, à mesurer sur un vrai pad avant d'investir dessus.

### 5.4 Masquage

```python
def masquer_un_element(element: "ElementDocument", justification: str, utilisateur) -> None:
    """
    Retire un element du contenu utile sans le supprimer.
    / Removes an element from the useful content without deleting it.

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    Cas reel : Voxtral transcrit un bruit de fond, une toux, un doublon
    de phrase. Ce n'est pas une correction de texte (le contenu n'existe
    pas, il n'y a rien a corriger VERS), ni une note hors-texte (qui
    documente une INCERTITUDE, pas une absence de contenu).

    Un element masque :
      - n'apparait plus dans les nouveaux chunks (§ 4.1)
      - reste visible dans le document, barre et grise
      - ses extractions existantes passent DETACHEE, pas supprimees
      - peut etre demasque, ce qui les repositionne si le texte n'a pas
        change entre-temps (meme logique que la reconciliation, § 6)
    """
    with transaction.atomic():
        _detacher_les_extractions_de(element)
        element.masque = True
        element.save(update_fields=["masque"])

        ElementOperation.objects.create(
            element=element,
            type_operation=TypeOperationElement.MASQUAGE,
            user=utilisateur,
            justification=justification,
        )
```

**`ElementOperation`** remplace, pour cette famille d'opérations, l'usage détourné de `PageEdit`/`TypeEdit` de la v1 (qui n'avait ni `SCISSION` ni `FUSION` ni `MASQUAGE` dans ses choix — relevé par la relecture). Nouveau modèle léger :

```python
class TypeOperationElement(models.TextChoices):
    SCISSION = "scission", "Élément scindé"
    FUSION = "fusion", "Éléments fusionnés"
    MASQUAGE = "masquage", "Élément masqué"
    DEMASQUAGE = "demasquage", "Élément démasqué"


class ElementOperation(models.Model):
    """Historique des operations structurelles sur les elements."""
    element = models.ForeignKey("core.ElementDocument", on_delete=models.CASCADE, related_name="operations")
    type_operation = models.CharField(max_length=16, choices=TypeOperationElement.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    justification = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

`PageEdit`/`TypeEdit` reste pour les corrections de **texte** (`TITRE`, `CONTENU`, `BLOC_TRANSCRIPTION`, `LOCUTEUR` — inchangés depuis l'existant). `ElementOperation` couvre les opérations de **structure**. Les deux journaux sont consultables ensemble dans l'historique de la page.

---

## 6. Réconciliation après une correction de texte

Reprise de la v1, corrigée sur les trois points relevés par la relecture.

```python
def reconcilier_les_portions_de_l_element(element, nouveau_texte):
    """
    Repositionne les portions d'ancrage apres une correction de texte.
    / Repositions anchor portions after a text correction.

    LOCALISATION : hypostasis_extractor/services/reconciliation.py

    CORRECTIONS APPORTEES PAR RAPPORT A LA V1 (relecture) :
      - ancien_texte n'est plus un parametre mort : on ne le lisait pas,
        il n'a jamais ete necessaire, retire.
      - .find() prenait la premiere occurrence sans verifier l'unicite :
        si le texte cherche apparait plusieurs fois dans l'element, on
        marque DETACHEE plutot que de deviner faux en silence.
      - un seul appel groupe en transaction.atomic() + select_for_update,
        au lieu d'un .save() par portion qui redeclenchait le signal a
        chaque fois (N portions = 2N requetes COUNT en v1).
      - les portions des extractions masquees (extraction.masquee=True)
        sont ignorees : pas de travail sur ce que personne ne voit.
    """
    resultat = {"exactes": [], "retrouvees": [], "detachees": []}

    with transaction.atomic():
        portions = list(
            AncrageExtraction.objects
            .select_for_update()
            .filter(element=element, extraction__masquee=False)
        )

        for portion in portions:
            texte_recherche = portion.texte_de_la_portion_avant_edition()  # snapshot pre-transaction

            texte_a_la_position_actuelle = nouveau_texte[
                portion.debut_dans_element:portion.fin_dans_element
            ]
            if texte_a_la_position_actuelle == texte_recherche:
                portion.etat_ancrage = EtatAncrage.EXACTE
                resultat["exactes"].append(portion.pk)
                continue

            occurrences = _toutes_les_occurrences(nouveau_texte, texte_recherche)
            if len(occurrences) == 1:
                portion.debut_dans_element, portion.fin_dans_element = occurrences[0], occurrences[0] + len(texte_recherche)
                portion.etat_ancrage = EtatAncrage.RETROUVEE
                resultat["retrouvees"].append(portion.pk)
                continue

            # Zero occurrence, OU plusieurs occurrences ambigues : on ne
            # devine pas. / Zero matches, OR several ambiguous matches:
            # we don't guess.
            portion.etat_ancrage = EtatAncrage.DETACHEE
            resultat["detachees"].append(portion.pk)

        AncrageExtraction.objects.bulk_update(
            portions, ["debut_dans_element", "fin_dans_element", "etat_ancrage"],
        )

    return resultat
```

**Sur `RETROUVEE` comme état instable** (relevé par la relecture) : en v2, l'état d'une portion est explicitement documenté comme « le résultat du dernier passage de réconciliation », pas un historique cumulatif. L'historique cumulatif, lui, vit dans `PageEdit.donnees_avant`/`donnees_apres`. Ce n'est pas un bug, c'est la portée assumée du champ — précisé pour que ça ne soit plus une ambiguïté silencieuse.

---

## 7. Concurrence

Absente de la v1 (relevé comme manque n°1). Deux garde-fous, minimaux mais suffisants pour la charge attendue (dossiers de dizaines de contributeurs, pas des milliers d'éditions simultanées) :

```python
def corriger_le_texte_d_un_element(request, identifiant_stable):
    """
    LOCALISATION : hypostasis_extractor/views_element.py

    select_for_update() serialise les corrections concurrentes sur LE
    MEME element. Deux utilisateurs qui corrigent des elements differents
    ne se bloquent jamais : le verrou est par ligne, pas par page.
    """
    with transaction.atomic():
        element = ElementDocument.objects.select_for_update().get(
            identifiant_stable=identifiant_stable,
        )
        # ... validation, ecriture, reconciliation, tout dans la meme transaction
```

Pas de verrou optimiste par version de champ (`updated_at` comparé côté client) dans cette première version — le coût d'un `select_for_update` court (une correction d'élément dure quelques dizaines de millisecondes) est jugé suffisant. À revoir si la recette manuelle montre des blocages perceptibles.

---

## 8. Ce qui est repris tel quel de la v1

Ces parties de la v1 ont été relues et validées sans réserve structurelle par la relecture (§ « Ce qui est vérifié et juste »). Elles ne sont pas reproduites ici en entier — seules les corrections ponctuelles sont listées.

### 8.1 UX / UI générale (v1 § 5.1, 5.2, 5.5, 5.6, 5.7)

Reprise telle quelle : la disposition à trois volets, la barre d'état dans la gouttière, l'avertissement avant édition d'un élément débattu, la section « détachées » du drawer (renommée depuis « orphelines », § 2.2).

**Corrections à appliquer** :
- `role="alert"` contenant un formulaire → remplacer par un `role="dialog"` avec piégeage de focus et restitution au fermeture (contresens ARIA relevé par la relecture — `alert` est pour un message bref, pas un formulaire).
- Le `visually-hidden` d'état (v1 § 5.2) doit couvrir `ANALYSE` autant que `DEBATTU`, pas seulement ce dernier.
- Toute ligne mentionnant `SCELLE`/cadenas est retirée (la fonctionnalité n'existe plus).
- La section « détachées » gagne les lignes issues du masquage (§ 5.4) et de la re-ingestion (§ 5.3), pas seulement de la correction de texte.

### 8.2 Surlignage PDF (v1 § 5.3)

Reprise avec les trois corrections de la relecture :

- **Utiliser `viewport.convertToViewportRectangle()` de PDF.js** plutôt que la formule manuelle — elle gère la rotation de page (`/Rotate 90`) et l'origine de CropBox non nulle, deux cas qui cassent silencieusement avec un calcul à la main.
- **`devicePixelRatio`** : le canvas est rendu à `scale × dpr`, dimensionné en pixels CSS. Le calque de surlignage doit utiliser la même échelle CSS, pas l'échelle device.
- **`provenance.boites`** est une liste (§ 2.1) — un élément à cheval sur deux pages ou deux colonnes produit plusieurs rectangles, pas un seul.

Le principe reste : le surlignage porte sur l'élément entier (une boîte Docling par élément, pas par extraction). Avec l'ancre M2M, une extraction qui traverse deux éléments produit deux rectangles PDF distincts — cohérent avec les deux (ou N) balises `<mark>` en HTML.

### 8.3 Curseur audio (v1 § 5.4)

Reprise telle quelle pour le principe (texte→audio, audio→texte, bouton ▶ sur les cartes d'extraction). Une correction de la relecture : `trouverLeBlocAlInstant`, référencée mais non spécifiée en v1, doit être une recherche dichotomique sur un tableau trié des `(start_time, element_id)` de la page — un scan linéaire à 4 appels/seconde sur un conseil de 2h (potentiellement des milliers d'éléments) dégraderait visiblement. Ajouter un bouton « suivre la lecture » activable/désactivable (relevé comme absent — l'auto-scroll forcé agace dès la première utilisation).

### 8.4 Endpoints (v1 § 6)

Repris, moins `sceller`/`desceller`/`formulaire_descellement`. Ajoutés : `scinder`, `fusionner`, `masquer`, `demasquer`, chacun avec son serializer dédié suivant la convention du projet (un serializer par action POST).

---

## 9. Migration : moteur nouveau, données vierges, fixtures

**Changement radical par rapport à la v1.** La v1 tentait de convertir les extractions existantes vers le nouveau modèle en trois migrations `RunPython`, et la relecture a montré que ce plan ne passe pas (contradiction 3→4, mapping offset→élément non garanti fiable). Décision explicite : **on n'essaie plus.**

```
1. Le nouveau moteur (ElementDocument, AncrageExtraction, ElementOperation,
   SourceLink.ancrage_source) est ajoute au schema. Les anciens champs
   (ExtractedEntity.start_char/end_char, front/utils.py, le pont
   texte<->HTML de 504 lignes) restent en place, INTOUCHES.

2. Les DEUX systemes coexistent. Une Page a un flag "moteur" :
   ANCIEN ou ELEMENT. Les pages existantes restent ANCIEN et continuent
   de fonctionner exactement comme aujourd'hui — aucune regression.

3. Toute NOUVELLE page ingeree passe par le moteur ELEMENT.

4. Des fixtures de test (5-10 documents representatifs : PDF avec
   tableaux, verbatim audio diarise, pad markdown, prise de notes texte
   brut, page web-clipper) couvrent le moteur ELEMENT en profondeur AVANT
   la mise en production.

5. (Hors perimetre de cette spec, decision separee a prendre le moment
   venu) : une commande manage.py reconvertir_avec_docling permettra,
   dossier par dossier et a la demande, de faire migrer une page ANCIEN
   vers ELEMENT — perdant potentiellement les extractions non
   reancrables, exactement comme la migration 3 de la v1 l'aurait fait,
   mais cette fois en decision explicite et ponctuelle par le
   proprietaire du dossier, pas en masse et sans recul.
```

Ce choix répond directement à la contradiction relevée par la relecture (migration 3 projette des échecs, migration 4 impose la non-nullabilité) en la supprimant : il n'y a plus de migration de données à faire passer de force, donc plus de contrainte à violer.

**Coût accepté** : deux moteurs à maintenir en parallèle un temps. Le moteur ANCIEN n'a plus de nouveau développement, seulement la maintenance minimale. C'est un compromis délibéré entre le risque d'une migration de données irréversible et le coût, borné, d'une double implémentation temporaire.

---

## 10. Tests

Repris et complétés depuis la v1 (§ 8), avec l'ajout des cas issus de la v2 :

### Le moteur de structure — `hypostasis_extractor/tests/test_moteur_structure.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_scission_redistribue_une_portion_simple` | Portion entièrement avant/après la coupe → rattachée sans division |
| `test_scission_divise_une_portion_qui_chevauche` | Portion à cheval sur le point de coupe → devient 2 portions, `ordre_dans_extraction` recalculé pour toute l'extraction |
| `test_scission_conserve_le_texte_total` | Concaténation des deux morceaux == texte original |
| `test_fusion_refuse_des_elements_non_adjacents` | `ValueError` si `second.ordre != premier.ordre + 1` |
| `test_fusion_decale_les_portions_du_second` | Offsets corrects après fusion |
| `test_fusion_coalesce_les_portions_contigues` | Deux portions adjacentes de la même extraction → une seule après fusion |
| `test_reingestion_conserve_les_ancres_des_elements_inchanges` | Élément avec même empreinte → même `identifiant_stable`, ancres intactes |
| `test_reingestion_detache_les_extractions_des_elements_disparus` | Élément absent du nouveau contenu → ses portions passent `DETACHEE` |
| `test_masquage_detache_sans_supprimer` | Élément masqué → portions `DETACHEE`, rien supprimé, `demasquer` possible |

### L'ancre M2M — `hypostasis_extractor/tests/test_ancrage_m2m.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_span_dans_un_seul_element_donne_une_portion` | Cas simple |
| `test_span_sur_trois_elements_donne_trois_portions_ordonnees` | Cas d'une extraction sur une liste à puces |
| `test_separateurs_de_jonction_exclus_des_portions` | Les `\n\n` entre éléments n'apparaissent dans aucune portion |
| `test_element_decoupe_en_sous_chaine_du_chunk` | Élément trop gros pour un chunk → intersection dans le bon sens |
| `test_reconciliation_ambigue_detache_plutot_que_deviner` | Texte trouvé à 2 positions → `DETACHEE`, pas de choix arbitraire |

### Chunking — `hypostasis_extractor/tests/test_chunking_par_element.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_aucun_chunk_ne_coupe_un_element` | Invariant central : 0 élément coupé, sur un corpus de test |
| `test_preference_de_section_respecte_le_plancher` | Sous plancher, on ne coupe pas même à un sous-titre |
| `test_element_masque_absent_des_chunks` | Un élément masqué n'apparaît dans aucun chunk produit |

### Reprise de la v1

Tous les tests de `test_ancrage_element.py`, `test_coordonnees_pdf.py`, et E2E (§ 8 v1) sont repris, moins les tests de scellement, plus les nouveaux tests de concurrence (`select_for_update` effectif sous accès concurrent, testé avec deux transactions imbriquées).

---

## 11. Ordre d'implémentation suggéré

| Phase | Contenu | Dépend de |
|---|---|---|
| **A** | Modèles (`ElementDocument`, `AncrageExtraction`, `ElementOperation`, `SourceLink.ancrage_source`) + signal d'état simplifié (sans scellement) | — |
| **B** | Algorithme d'intersection (§ 2.3) + tests | A |
| **C** | Chunking par élément avec préférence de section (§ 4.1) + tests | A |
| **D** | Pipeline d'ingestion Docling → éléments → chunks → LangExtract → ancres | B, C |
| **E** | Réconciliation après correction de texte (§ 6) + concurrence (§ 7) | A |
| **F** | Moteur scission/fusion (§ 5.1, 5.2) | A, B |
| **G** | Moteur ajout par re-ingestion (§ 5.3) + masquage (§ 5.4) | E, F |
| **H** | `ElementViewSet` : endpoints, serializers | E, F, G |
| **I** | UX/UI : volet PDF corrigé (PDF.js natif, devicePixelRatio) | D, H |
| **J** | UX/UI : volet audio + curseur + « suivre la lecture » | D, H |
| **K** | Fixtures de test (5-10 documents représentatifs) + double-moteur en place | tout |

**A à G ne dépendent d'aucune décision UI.** C'est le cœur du modèle de données et des algorithmes, testable en isolation avant tout écran.

---

## 12. Questions ouvertes

1. **Frontière préférentielle côté audio.** Non mesurée sur une vraie transcription diarisée (§ 4.1). À trancher avant la phase D si le premier client à livrer est le lycée avec des comptes-rendus audio, avant la phase G sinon.
2. **`empreinte_contenu` sur duplication de contenu.** La re-ingestion (§ 5.3) peut se tromper si deux éléments distincts ont un texte identique. Non traité en première version — à mesurer sur un vrai pad avant d'investir dans une désambiguïsation par position relative.
3. **RGPD / lycée.** L'invariant « rien ne se supprime » (masquage, pas suppression) entre en tension avec le droit à l'effacement quand la source est la voix d'un mineur. Hors périmètre de cette spec technique — nécessite une décision produit séparée : un masquage *réversible* pour l'usage courant, une purge *réelle et irréversible* réservée à une action administrative distincte, documentée et tracée hors du modèle d'édition normal.
4. **Génération effective de `SourceLink`** au moment où une synthèse V2 cite une extraction. Cette spec ne fait que reconnecter le modèle de données (§ 2.4) — la mécanique de génération (quand, par quel signal, avec quelle vérification) est le sujet de la spec opposabilité, à écrire séparément.
5. **Double-moteur, durée de vie.** Combien de temps ANCIEN et ELEMENT coexistent avant qu'une décision soit prise sur les pages ANCIEN restantes — dépend du rythme réel d'ingestion des deux clients (lycée, réseaux tiers-lieux), pas fixable a priori.

---

*Spec v2 rédigée le 5 août 2026, à partir de la spec v1.0, de sa relecture adverse (`RELECTURE-spec-ancrage.md`), de la synthèse sourcing/multi-éléments (`SYNTHESE-sourcing-et-multi-elements.md`), et des mesures de chunking comparatif (30 vs 42 vs 57 chunks, 0 vs 0 vs 6 éléments coupés, 7/7 antécédents préservés uniquement en A et C) obtenues sur `ia-sens-commun.pdf` avec `docling 2.118.0` et `langextract 1.6.0`.*
