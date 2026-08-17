# 1. De l'ingestion au périmètre

> Comment un fichier devient des **preuves citables**, et comment un humain
> décide lesquelles partent au modèle.
>
> Ce que cette planche établit : **rien n'entre dans un périmètre sans être ancré.**

---

## Les trois entrées, et le seul point de sortie

Trois formes d'entrée, trois convertisseurs — mais **un seul aboutissement** :
des `ElementDocument`. Tout ce qui suit ne connaît que ces éléments.

```mermaid
flowchart TD
    subgraph entrees["TROIS ENTRÉES"]
        F1["Fichier PDF, DOCX…<br/>ImportViewSet._importer_fichier_document"]
        W1["Capture web par l'extension<br/>core/views.py PageViewSet.create"]
        A1["Audio<br/>ImportViewSet, file par défaut"]
    end

    F2["Conversion synchrone MarkItDown<br/>front/services/conversion_fichiers.py"]
    F3["Page créée + content_hash<br/>empreinte de déduplication"]
    W2["PageCreateSerializer<br/>texte dérivé du HTML capturé"]
    A2["TranscriptionJob + Page en processing"]
    A3["transcrire_audio_task<br/>Voxtral, diarisation<br/>écrit transcription_raw"]

    D1["ingerer_un_fichier_avec_docling<br/>file ingestion_docling, concurrence 1"]
    D2["ingerer_une_capture_web_avec_docling"]
    D3["ingerer_une_transcription_diarisee_en_elements<br/>un élément par tour de parole"]

    EL["ElementDocument<br/>texte · ordre · label · chemin_de_section<br/>empreinte_contenu · provenance<br/>identifiant_stable qui ne bouge JAMAIS"]

    ETAT["_noter_l_etat_d_ingestion RÉUSSIE<br/>seul point de passage de toutes les ingestions"]
    PROJ["Page.text_readability réécrit<br/>PROJECTION dérivée des éléments"]

    ECHEC["EtatIngestion.ECHOUEE<br/>refus BRUYANT + notification"]

    F1 --> F2 --> F3 --> D1
    W1 --> W2 --> D2
    A1 --> A2 --> A3 --> D3

    D1 --> EL
    D2 --> EL
    D3 --> EL
    D1 -. "type non couvert · fichier absent · échec Docling" .-> ECHEC

    EL --> ETAT --> PROJ

    classDef refus fill:#fdecea,stroke:#b91c1c,color:#7f1d1d
    classDef verite fill:#eef7ee,stroke:#047857,color:#064e3b
    class ECHEC refus
    class EL verite
```

**Le champ plat n'est plus une vérité concurrente.** Il l'a été : l'import de fichier
écrivait un texte par MarkItDown *et* des éléments par Docling — mesuré le 17 août 2026,
une note portait 58 524 signes de texte plat **et** 189 éléments, aux offsets sans rapport.
Depuis, il est **dérivé** des éléments à la réussite de l'ingestion. Il garde ses deux
rôles légitimes — l'empreinte de déduplication, et le repli d'une page sans élément — sans
plus pouvoir mentir.

---

## De l'élément à la preuve : les trois façons de créer une extraction

Une extraction n'est **pas** un bout de texte : c'est un texte **plus ses portions
ancrées**. Les trois chemins passent par la même usine à portions.

```mermaid
flowchart TD
    subgraph auto["ANALYSE PAR LE MODÈLE"]
        AN1["Bouton Analyser<br/>front/views.py analyser"]
        AN2["analyser_une_page_avec_le_moteur_element<br/>tasks_element.py"]
        AN3["analyser_une_page_par_element"]
        AN4["construire_les_chunks<br/>chunking.py — sur les FRONTIÈRES d'éléments,<br/>jamais au milieu d'un paragraphe"]
        AN5["appeler_langextract_sur_un_chunk"]
    end

    subgraph main["À LA MAIN, ET IA SUR SÉLECTION"]
        M1["creer_manuelle<br/>ou action ia sur une sélection"]
        M2["ancrer_un_texte_dans_une_page<br/>ancrage.py"]
    end

    OFF["construire_la_table_des_offsets<br/>où chaque élément tombe dans le texte collé"]
    INT["decouper_le_span_en_portions_par_element<br/>intersection span × éléments"]

    PORT{"des portions ?"}
    OK["ExtractedEntity<br/>+ AncrageExtraction, une par portion"]
    NON["RIEN n'est créé<br/>409 à la main · écartée et COMPTÉE pour l'action ia"]

    AN1 --> AN2 --> AN3 --> AN4 --> AN5 --> INT
    AN4 --> OFF
    M1 --> M2 --> OFF --> INT
    INT --> PORT
    PORT -- oui --> OK
    PORT -- non --> NON

    G1["Refus AVANT de payer :<br/>IA désactivée · page SANS ÉLÉMENT ·<br/>job sans modèle · garde § 4.2<br/>une note citée par une dirigée ne se ré-analyse pas"]
    AN2 -. refus .-> G1

    classDef refus fill:#fdecea,stroke:#b91c1c,color:#7f1d1d
    classDef verite fill:#eef7ee,stroke:#047857,color:#064e3b
    class NON,G1 refus
    class OK verite
```

**On ne devine jamais.** Un span qui tombe entièrement dans un séparateur de jonction, ou
un texte introuvable dans les éléments, ne produit **aucune** portion — et alors rien n'est
enregistré. Une ancre fausse se donne pour une preuve ; une absence d'ancre non.

> C'est la leçon de l'incident du 13 août 2026 : la création manuelle cherchait sa position
> dans le champ plat, n'y trouvait rien, et retombait sur le caractère 0. **Neuf extractions
> sur douze** pointaient le début du document.

---

## Le périmètre : ce sont des humains qui le décident

Aucune distance sémantique ne choisit. Le périmètre vient du **rangement** — un humain a
classé, un humain filtre.

```mermaid
flowchart TD
    C["Carnet"]
    NS["notes_sources_du_carnet<br/>garde-fou § 3.3 MÉCANIQUE :<br/>les wikis et les synthèses sont EXCLUS"]
    FAC["Facettes du carnet<br/>OU dans un même axe · ET entre les axes"]

    W["WIKI<br/>périmètre RECALCULÉ à chaque production<br/>notes_du_perimetre_d_un_wiki"]
    S["SYNTHÈSE DIRIGÉE<br/>périmètre FIGÉ au moment du geste"]
    S2["Figé DEUX fois :<br/>les notes ET les extractions proposées"]

    EX["extractions_citables_de_la_note<br/>TOUS les jobs terminés, non masquées"]
    PER["LE PÉRIMÈTRE<br/>N extractions, ÉNUMÉRÉES — jamais échantillonnées"]

    C --> NS --> FAC
    FAC --> W --> EX
    FAC --> S --> S2 --> EX
    EX --> PER

    NOTE["Le SUJET d'un wiki n'est PAS un filtre :<br/>il oriente la rédaction, rien de plus"]
    W -.-> NOTE

    classDef verite fill:#eef7ee,stroke:#047857,color:#064e3b
    classDef garde fill:#eef2ff,stroke:#4338ca,color:#1e1b4b
    class PER verite
    class NS,S2 garde
```

**Pourquoi le périmètre d'une dirigée est figé deux fois.** Sans le second figeage — les
extractions réellement proposées au modèle — une ré-analyse postérieure réécrirait « ce que
la synthèse n'a pas repris » avec des extractions que l'acte daté n'a **jamais vues**.
C'est-à-dire une réécriture en douce du passé.

**Pourquoi le périmètre s'énumère.** Résumer un groupe par son membre le plus central
efface, mesuré sur l'étalon, **11 extractions sur 19** — et parfois les *deux* faces d'un
désaccord, sans laisser trace qu'il y a eu débat.

---

Planche suivante : [du prompt à l'article sourcé](02-du-prompt-a-l-article-source.md).
