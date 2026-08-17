# 2. Du prompt à l'article sourcé

> Un appel au modèle, et un système de sourçage. C'est tout — et c'est ce qui
> permet de remonter d'une phrase à un tour de parole horodaté.
>
> Ce que cette planche établit : **le numéro `[N]` n'est jamais enregistré**, et
> **aucun texte n'est jamais retiré de l'article**.

---

## Ce qui part au modèle

Le prompt ne contient **pas** le texte des notes du carnet. Il contient des **extractions
étiquetées**, avec leurs commentaires.

```mermaid
flowchart TD
    PER["Le périmètre — N extractions"]
    BL["_blocs_d_extractions_par_note<br/>un bloc par note"]
    FORME["Par extraction :<br/>Identifiant ext:N<br/>Citation<br/>ses commentaires, avec le nom de l'auteur"]

    SYS["Prompt système<br/>l'analyseur de synthèse<br/>DEUX statuts de débat : nouveau · commenté"]
    CONS["Consignes de forme<br/>titres de niveau 2 UNIQUEMENT<br/>chaque affirmation finit par son marqueur<br/>ligne finale de contrôle obligatoire"]

    LLM(["UN appel au modèle<br/>appeler_llm"])

    PER --> BL --> FORME --> LLM
    SYS --> LLM
    CONS --> LLM

    classDef appel fill:#fff7ed,stroke:#b45309,color:#7c2d12
    class LLM appel
```

**On lui demande la chose la plus grossière possible** — *quelle source* — et jamais *où
dans la source*. C'est délibéré : l'état de l'art mesure que contraindre un modèle à citer
plus finement **dégrade** l'attribution de 16 à 276 %. Le grain fin est retrouvé par
jointure, parce qu'il a été payé une fois, à l'extraction.

---

## Du texte rendu à l'article enregistré

```mermaid
flowchart TD
    REP["Réponse du modèle<br/>markdown + marqueurs + ligne de contrôle"]

    T1{"ligne de contrôle<br/>présente ?"}
    T1NON["ÉCHEC BRUYANT<br/>génération tronquée<br/>RIEN n'est enregistré"]

    N1["_normaliser_les_niveaux_de_titre<br/>tout titre de niveau 3+ ramené au niveau 2"]
    T2{"deux sections<br/>de même titre ?"}
    T2OUI["REFUS<br/>elles seraient l'une et l'autre<br/>impossibles à mettre à jour"]

    IDX["indexer_les_citations"]
    IDX1["marqueur hors périmètre ou inexistant :<br/>le MARQUEUR est retiré et SIGNALÉ<br/>— jamais le texte"]
    IDX2["marqueur dans un titre : retiré<br/>un titre n'affirme rien"]
    IDX3["marqueur en double dans un paragraphe : retiré<br/>pour que tous les compteurs s'accordent"]
    SL["SourceLink, un par couple<br/>paragraphe × extraction<br/>quelle portion · quelle section · quelles bornes"]
    RECO["Réconciliation des verdicts<br/>sur les ANCIENNES bornes<br/>contestations perdues SIGNALÉES"]

    T3{"au moins<br/>une citation ?"}
    T3NON["REFUS<br/>un texte sans preuve<br/>n'est pas un succès"]

    HTML["HTML rendu<br/>échappement puis markdown puis bleach"]
    HASH["content_hash"]
    FIN["Article enregistré"]

    REP --> T1
    T1 -- non --> T1NON
    T1 -- oui --> N1 --> T2
    T2 -- oui --> T2OUI
    T2 -- non --> IDX
    IDX --> IDX1
    IDX --> IDX2
    IDX --> IDX3
    IDX --> SL --> RECO --> T3
    T3 -- non --> T3NON
    T3 -- oui --> HTML --> HASH --> FIN

    classDef refus fill:#fdecea,stroke:#b91c1c,color:#7f1d1d
    classDef verite fill:#eef7ee,stroke:#047857,color:#064e3b
    class T1NON,T2OUI,T3NON refus
    class SL,FIN verite
```

**Ce tronc commun sert les TROIS producteurs d'articles** : le wiki, la synthèse dirigée, et
la synthèse d'une note. Le troisième dupliquait sa propre écriture et échappait donc aux
trois gardes — corrigé le 17 août 2026. *Une garde qui ne couvre que deux producteurs sur
trois n'est pas une garde.*

**On ne retire jamais de texte, seulement des marqueurs.** Un paragraphe sans marqueur reste
dans l'article, et s'affiche marqué « non sourcé ». C'est un état des lieux, pas une censure.

---

## À l'affichage : le numéro est attribué, jamais persisté

```mermaid
flowchart LR
    MD["Le markdown stocké<br/>porte des marqueurs ext:N"]
    JET["_html_avec_renvois<br/>chaque marqueur devient un jeton"]
    NUM["Numérotation par ordre<br/>de PREMIÈRE APPARITION"]
    BTN["Bouton exposant N<br/>data-etat + hx-get vers SA preuve"]
    PAR["_classer_le_paragraphe<br/>le paragraphe prend le PIRE<br/>verdict de ses sources"]
    ECR["À l'écran"]

    MD --> JET --> NUM --> BTN --> ECR
    JET --> PAR --> ECR

    POURQUOI["Un numéro STOCKÉ serait faux<br/>après la moindre réindexation"]
    NUM -.-> POURQUOI
```

---

## Deux calculs qui ne coûtent rien

```mermaid
flowchart TD
    P["Le périmètre"]
    CIT["Les extractions qui ont un SourceLink"]
    EC["ÉCARTÉES = périmètre − citées<br/>différence d'ensembles, en SQL"]

    ELS["Les éléments de la note"]
    PORT["Ceux qui portent au moins une portion"]
    COUV["COUVERTURE = jointure<br/>ni masquées, ni détachées, ni jobs inachevés"]

    P --> EC
    CIT --> EC
    ELS --> COUV
    PORT --> COUV

    L1["Zéro appel au modèle.<br/>JAMAIS une liste stockée : dans la maquette,<br/>elle était fausse sur trois articles sur quatre"]
    L2["Limite à afficher : ceci n'audite que les CITATIONS.<br/>Une extraction lue et utilisée sans être citée<br/>traverse le filtre. Borne inférieure, pas garantie"]
    EC -.-> L1
    EC -.-> L2

    classDef verite fill:#eef7ee,stroke:#047857,color:#064e3b
    class EC,COUV verite
```

**La couverture sépare deux choses que « non sourcé » confond** : le modèle a inventé, ou
**le passage n'a jamais produit d'extraction**. Sans elle, un trou de couverture se présente
comme une invention potentielle.

---

## La mise à jour d'un wiki : le modèle propose, l'humain accepte

```mermaid
flowchart TD
    B["Proposer une mise à jour"]
    REP0["Réparation des titres de niveau 3 hérités,<br/>PAR LE CHEMIN D'ÉCRITURE NORMAL<br/>— sinon les bornes des SourceLink se décalent<br/>et les verdicts sont perdus en silence"]
    EXP["Ce que le modèle voit :<br/>l'article + la LISTE des titres adressables<br/>+ les écartées"]
    LLM(["Appel au modèle"])
    OPS["Un tableau JSON d'opérations<br/>no_change · append · replace · insert"]
    JETON["Jeton de fraîcheur :<br/>updated_at de l'article"]

    PREV["Prévisualisation par un PASSAGE À BLANC<br/>de l'applieur réel — jamais deux vérités"]
    HUM(["L'humain coche, opération par opération"])

    FRAIS{"article inchangé<br/>depuis ?"}
    PERIME["REFUS 409 — proposition périmée<br/>jamais un écrasement"]

    APP["appliquer_les_operations"]
    R1["titre introuvable → REJET, contenu CONSERVÉ"]
    R2["contenu portant une ligne de titre → REJET"]
    R3["opération sans aucune source → REJET"]
    R4["insertion sous un titre existant → REJET"]
    TRONC["Le tronc commun d'écriture<br/>réindexation comprise"]

    B --> REP0 --> EXP --> LLM --> OPS --> JETON --> PREV --> HUM --> FRAIS
    FRAIS -- non --> PERIME
    FRAIS -- oui --> APP
    APP --> R1
    APP --> R2
    APP --> R3
    APP --> R4
    APP --> TRONC

    classDef refus fill:#fdecea,stroke:#b91c1c,color:#7f1d1d
    classDef humain fill:#f5f3ff,stroke:#6d28d9,color:#3b0764
    class PERIME,R1,R2,R3,R4 refus
    class HUM humain
```

**Les rejets sont par OPÉRATION, jamais par lot** — une hallucination ne jette pas les faits
des autres opérations. Et le contenu rejeté est **conservé et montré** : jamais un
`logger.warning` qui l'avale.

---

Planche suivante : [la vérification des citations](03-la-verification-des-citations.md).
