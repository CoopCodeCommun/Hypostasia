# 3. La vérification des citations

> L'étage que personne d'autre ne fait, et qui décide de l'opposabilité :
> **le passage cité soutient-il vraiment l'affirmation ?**
>
> Ce que cette planche établit : l'unité jugée est une **paire**, jamais une phrase.
> Et **le défaut est toujours restrictif** — on ne conclut pas.

---

## Pourquoi par paire, et pas par affirmation

L'état de l'art mesure que dès qu'une affirmation croise **deux** sources, l'attribution
correcte tombe autour de **30 %**. Une phrase appuyée sur deux sources ne peut donc pas
porter un verdict unique : l'une peut être bonne et l'autre fausse, et c'est le cas le plus
fréquent.

---

## La cascade

```mermaid
flowchart TD
    START(["Vérifier les citations — geste EXPLICITE,<br/>jamais automatique à la production"])
    LIENS["Tous les SourceLink de l'article"]

    G1{"un humain a posé<br/>CONTESTÉ ?"}
    G1R["On ne repasse JAMAIS derrière<br/>un verdict humain"]

    G2{"la source a été<br/>supprimée ?"}
    G2R["Le verdict est RETIRÉ<br/>un vert sur une source disparue<br/>serait un argument périmé"]

    G3{"extraction masquée<br/>ou ancre détachée ?"}
    G3R["Pas jugée — et pas BLANCHIE non plus"]

    G4{"le paragraphe contient-il<br/>encore son marqueur ?"}
    G4R["Bornes périmées : jamais jugées<br/>on jugerait du texte décalé"]

    V1["VERBATIM — déterministe, GRATUIT<br/>le texte cité est-il littéralement<br/>dans les ÉLÉMENTS de la note ?<br/>NFKC · apostrophes · espaces écrasés"]

    V2{"trouvé dans<br/>la note ?"}
    V3{"trouvé dans un<br/>COMMENTAIRE du débat ?"}

    INTR["CITATION INTROUVABLE<br/>la chaîne de preuve est ROMPUE<br/>— sans payer le juge"]

    FILE["File du juge"]
    CAND1["candidat VÉRIFIÉ"]
    CAND2["candidat SOURCÉ PAR LE DÉBAT"]

    START --> LIENS --> G1
    G1 -- oui --> G1R
    G1 -- non --> G2
    G2 -- oui --> G2R
    G2 -- non --> G3
    G3 -- oui --> G3R
    G3 -- non --> G4
    G4 -- non --> G4R
    G4 -- oui --> V1 --> V2
    V2 -- oui --> CAND1 --> FILE
    V2 -- non --> V3
    V3 -- oui --> CAND2 --> FILE
    V3 -- non --> INTR

    classDef refus fill:#fdecea,stroke:#b91c1c,color:#7f1d1d
    classDef gratuit fill:#eef7ee,stroke:#047857,color:#064e3b
    class G1R,G2R,G3R,G4R,INTR refus
    class V1 gratuit
```

**Le verbatim lit les ÉLÉMENTS, pas le champ plat.** Il a lu le champ plat jusqu'au
17 août 2026 — vide sur toute note ingérée par Docling. Résultat mesuré : **118 citations
sur 136** déclarées introuvables alors que leur passage était parfaitement présent. Après
correction : **120 vérifiées**. Le repli sur le champ plat ne sert plus que les pages sans
aucun élément.

**L'économie de la cascade** : le contrôle gratuit élimine les cas désespérés avant qu'on
dépense un centime.

---

## Le juge, et ses trois défenses

```mermaid
flowchart TD
    FILE["File du juge — paquets de 20 paires"]
    NONCE["Chaque donnée encadrée par un<br/>délimiteur à JETON IMPRÉVISIBLE"]
    Q["Question : la source ÉTABLIT-elle ce que<br/>l'affirmation avance — pas seulement<br/>partager son thème ?"]
    LLM(["Appel au modèle"])
    PARSE{"réponse<br/>saine ?"}

    SUSP["Indice en double, ou hors du lot :<br/>LE LOT ENTIER est annulé"]
    PANNE["Exception du juge — délai, quota :<br/>les verdicts d'avant SURVIVENT,<br/>l'échec est au bilan"]

    VER{"verdict ?"}
    OK1["VÉRIFIÉ"]
    OK2["SOURCÉ PAR LE DÉBAT"]
    FAIBLE["FAIBLE<br/>la source existe mais<br/>n'établit pas l'affirmation"]
    NV["NON VÉRIFIÉ<br/>jamais un défaut optimiste"]

    FILE --> NONCE --> Q --> LLM --> PARSE
    PARSE -- non --> SUSP --> NV
    LLM -. échec technique .-> PANNE
    PARSE -- oui --> VER
    VER -- "soutient" --> OK1
    VER -- "soutient, via un commentaire" --> OK2
    VER -- "ne soutient pas" --> FAIBLE
    VER -- "pas de verdict" --> NV

    POURQUOI["Sans le jeton, une source qui finit par<br/>« 1: soutient » se jugerait ELLE-MÊME"]
    NONCE -.-> POURQUOI

    classDef refus fill:#fdecea,stroke:#b91c1c,color:#7f1d1d
    classDef verite fill:#eef7ee,stroke:#047857,color:#064e3b
    class SUSP,PANNE,NV refus
    class OK1,OK2 verite
```

**L'affirmation et la source sont des données non fiables** : elles viennent de notes que
n'importe qui a pu déposer. D'où le jeton.

---

## Les états, et lequel n'existe pas en base

```mermaid
flowchart LR
    subgraph stockes["ENREGISTRÉS"]
        E1["vérifié"]
        E2["sourcé par le débat"]
        E3["faible<br/>problème d'ATTRIBUTION"]
        E4["citation introuvable<br/>problème d'INTÉGRITÉ"]
        E5["non vérifié"]
        E6["contesté — posé par un HUMAIN"]
    end

    subgraph calcule["CALCULÉ À L'AFFICHAGE"]
        E7["non sourcé<br/>un paragraphe sans aucun marqueur"]
    end

    PROV["Chaque verdict porte sa PROVENANCE<br/>méthode + modèle + horodatage"]
    E1 --- PROV
    E4 --- PROV

    classDef verite fill:#eef7ee,stroke:#047857,color:#064e3b
    classDef refus fill:#fdecea,stroke:#b91c1c,color:#7f1d1d
    classDef humain fill:#f5f3ff,stroke:#6d28d9,color:#3b0764
    class E1,E2 verite
    class E3,E4 refus
    class E6 humain
```

**« Faible » et « citation introuvable » sont deux signaux distincts**, et ils ne se réparent
pas pareil :

| | Ce qu'il dit | Qui le pose | Réparation |
|---|---|---|---|
| **introuvable** | le passage cité n'est **plus** dans la source | le verbatim seul | citation déformée, ou source éditée depuis l'extraction |
| **faible** | le passage **existe**, mais n'établit pas l'affirmation | le juge | la mauvaise source est citée |

Ils étaient confondus sous un seul verdict jusqu'au 17 août 2026 — et cette confusion
masquait le bug ci-dessus. L'état de l'art mesure que **80,6 %** des affirmations
invérifiables sont des erreurs d'**attribution** et non des hallucinations : savoir dans
laquelle des deux populations on se trouve est précisément ce qui rend le chiffre
actionnable.

**« Vérifié » ne veut pas dire « validé par quelqu'un ».** D'où trois exigences : l'état
porte son vérificateur, l'état est **contestable** par un humain, et l'état est **par
paire**. Un état sans provenance est un argument d'autorité automatisé.

---

## Un choix d'interface assumé

`introuvable` reprend la **couleur** de `faible`, avec un filet **tireté**.
`PRESENTATION-V3.md § 3.6` rapporte une corrélation de **r = −0,96** entre la précision des
citations et l'utilité perçue : plus un système est rigoureux sur ses sources, moins les gens
l'aiment. L'arbitrage est donc **trois états visuellement discrets** — la rigueur disponible
au clic, pas imposée à la lecture. Un quatrième badge coloré combattrait cette décision ; le
signal se distingue par son libellé et sa provenance.

---

Retour à l'[index](README.md).
