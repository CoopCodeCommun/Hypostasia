# Hypostasia V3 — ce que devient le projet, et pourquoi

**Date** : 9 août 2026, au soir (première rédaction le 8 août ; mis à jour après
les couches corpus A-H et synthèse A-F).
**Lecteur visé** : quelqu'un qui connaît Hypostasia mais pas les décisions de
conception de ces dernières semaines — un contributeur qui arrive, un partenaire,
ou le développeur qui reprendra ce code dans six mois.

Ce document explique et justifie. Il ne remplace ni les spécifications
(`SPEC-synthese-carnet.md`, `SPEC-selection-des-preuves.md`), ni le plan de
refonte (`PLAN/INSPIRATION_ATOMIC.md`), ni les maquettes (`tmp/maquettes/`) :
il dit d'où viennent les idées, comment les mécanismes fonctionnent, et ce qui
sépare aujourd'hui l'intention du code.

Une règle de rédaction, annoncée d'emblée parce qu'elle est le sujet même du
document : **quand un chiffre vient d'une étude menée sur d'autres systèmes et
non d'une mesure sur Hypostasia, c'est dit explicitement.** Un outil qui promet
des synthèses vérifiables ne peut pas se présenter avec des chiffres
invérifiables.

---

## 1. Ce qui change, en une page

Hypostasia V2 est un outil « un dossier contient des pages » : on importe un
document, on l'analyse, des extractions apparaissent dans la marge, on les
commente. La synthèse y était une *version* du document — `synthetiser_page_task`
créait une nouvelle `Page` avec un `parent_page` et un numéro incrémenté, comme
si résumer un débat revenait à le réécrire. Ce n'est plus vrai depuis le 9 août :
la tâche a été réécrite, la synthèse est une note typée du carnet, et
`parent_page` n'a plus aucun écrivain en production (§ 6.2).

Hypostasia V3 en fait une **plateforme de gestion de corpus qui produit des
synthèses sourcées et contestables**. Trois déplacements :

1. **Le contenant change de nature.** Le dossier devient un *carnet*, une note
   peut appartenir à plusieurs carnets, et les carnets se regroupent en bases de
   connaissances. La relation note↔carnet porte les catégories : chaque
   collectif classe avec son propre vocabulaire sans l'imposer aux autres.
   Modèle repris de Praxis (§ 5).

2. **La synthèse change de niveau et de statut.** Elle cesse d'être une version
   d'une page pour devenir une *note du carnet*, en deux genres incompatibles
   dans un seul objet : le **wiki**, article thématique vivant mis à jour par
   opérations de section, et la **synthèse dirigée**, acte daté, figé, qu'un
   collectif adopte et auquel il peut se référer six mois plus tard. Mécanisme
   repris d'Atomic, corrigé sur plusieurs points (§ 4).

3. **La citation devient un objet vérifié.** Chaque affirmation d'une synthèse
   est reliée à ses preuves par un lien persisté, contrôlé mécaniquement
   (verbatim puis implication), affiché avec son état — et, plus important
   encore, la synthèse expose **ce qu'elle n'a pas repris** et **ce que
   l'analyse n'a jamais lu**. C'est la partie la plus travaillée de la refonte
   (§ 3), parce que l'état de l'art montre que c'est là que tous les systèmes
   comparables échouent.

Ce que ça débloque, concrètement : un compte rendu de conseil qui intéresse
deux groupes de travail vit dans leurs deux carnets sans être dupliqué, avec un
seul débat visible des deux ; douze séances étalées sur deux ans produisent un
wiki qui se met à jour à mesure que le carnet grossit ; et une synthèse adoptée
en assemblée peut être contestée *dans* l'outil — en remontant à la source
exacte de chaque affirmation, ou en pointant l'argument qu'elle a laissé de
côté.

Le déclencheur n'est pas théorique. Deux demandes réelles — un lycée (comptes
rendus de conseils de vie lycéenne, profs et élèves) et des réseaux régionaux
de tiers-lieux (veille de financements) — portent d'abord sur la gestion de
corpus, pas sur la synthèse. Le besoin commercial a précédé le besoin technique
(note « Hypostasia V3 — couche corpus et refonte de la navigation », mémoire
Atomic, août 2026).

---

## 2. Les trois couches

La V3 s'organise en trois couches, chacune consommant les garanties de celle du
dessous. L'ordre de construction suit l'ordre de dépendance, et les trois
couches sont désormais codées à des degrés différents.

| Couche | Objet | État |
|---|---|---|
| **Ancrage par élément** | où, exactement, dans quel texte | implémentée et migrée, **pas encore branchée** au parcours utilisateur |
| **Corpus** : base → carnet → note | qui range quoi, avec quel vocabulaire | implémentée, migrée et testée, écrans compris |
| **Synthèse au niveau du carnet** | ce qu'on affirme, sur quelles preuves | socle et vérification codés (modèles, citations, calculs, gardes, verbatim + juge NLI) ; interface à faire |

### 2.1 L'ancrage par élément — le socle

L'ancien moteur ancrait une extraction par deux offsets dans le texte plat de
la page. Défaut structurel : « un décalage n'est pas une adresse, c'est une
distance depuis un point qui bouge » — corriger une coquille en haut de page
faussait toutes les ancres du dessous.

Le moteur ELEMENT ancre dans l'**élément de document** : un paragraphe, un titre,
un item de liste, un tableau, un tour de parole, chacun identifié par un UUID qui
ne change jamais (`ElementDocument`, `core/models.py:1609`). Une extraction porte
une ou plusieurs **portions**, chacune bornée à l'intérieur d'un élément
(`AncrageExtraction`, `hypostasis_extractor/models.py:666`). La table de liaison
n'est pas un luxe : mesuré sur les données du projet, une extraction d'une seule
phrase enjambe déjà deux éléments dans 7,5 % des cas, une extraction de deux
phrases dans 76 % des cas.

Autour de ce modèle, une famille de services (`hypostasis_extractor/services/`) :

- `ancrage.py` — traduit un span rendu par le LLM sur un chunk en portions par
  élément, par intersection ; les séparateurs de jonction n'appartiennent à
  aucune portion ;
- `chunking.py` — découpe sur les frontières d'éléments, jamais au milieu ;
- `analyse_par_element.py` — le pipeline chunks → LLM → ancres ;
- `reconciliation.py` — repositionne les portions après une correction de
  texte, avec la règle « on ne devine pas » : un passage qui apparaît deux fois
  pourrait être l'un ou l'autre, on le marque `DETACHEE` et un humain tranche ;
- `moteur_structure.py` — scission et fusion d'éléments sans perdre les ancres
  (le contenu total ne change jamais, seul le découpage change) ;
- `masquage.py` et `reingestion.py` — écarter du bruit sans le supprimer, et
  ré-analyser un pad qui grossit en reconnaissant les éléments inchangés par
  empreinte (sur un pad de 200 comptes rendus, seuls ~2 % du contenu repartent
  en analyse) ;
- `garde_edition.py` — refuse l'édition pendant qu'une analyse tourne, pour ne
  jamais écrire d'ancres calculées sur un texte qui n'existe plus.

Côté affichage, `front/services/rendu_elements.py` est écrit et testé : il
remplace l'injection de balises par offsets par un découpage du texte de chaque
élément en segments aux bornes des portions, ce qui rend enfin représentables
les extractions en plusieurs portions et les chevauchements — 3 898 paires
d'extractions se chevauchent en base, ce n'est pas un cas d'école. **Mais aucun
code de production ne l'appelle** : ni vue, ni template, ni tâche (vérifié par
recherche exhaustive le 9 août — il n'apparaît que dans sa propre suite de tests
et dans les commentaires de la maquette). Comme le pipeline d'analyse par
élément, il attend le branchement (§ 6.1).

### 2.2 Le corpus — base → carnet → note

**Implémentée** (voir § 5 pour le modèle, § 6.2 pour l'état exact). Deux
relations N-N portées par des tables de liaison (`AppartenancePageDossier`,
`AppartenanceDossierBase`) qui portent elles-mêmes les catégories, l'épinglage
et l'ordre manuel — modèles, migrations, permissions, endpoints et écrans
carnet / note / bases sont en place.

### 2.3 La synthèse au niveau du carnet

**Socle codé, interface à faire.** La synthèse est devenue une note typée du
carnet (`type_de_note` : note / wiki / synthèse), avec un garde-fou mécanique :
**une synthèse n'est jamais source d'une autre synthèse** — sans cette clause de
filtre, le wiki finirait par se citer lui-même et la délibération d'origine
disparaîtrait sous ses propres résumés. Le garde-fou est un champ, pas une
propriété calculée, précisément pour être une clause `filter()` ; il est exercé
par test et refusé à deux étages (la vue et, en profondeur, la tâche).

### 2.4 Pourquoi cet ordre

La synthèse cite des preuves ; une preuve est une portion ancrée ; une portion
ancrée n'existe que si l'ancrage survit aux éditions, scissions et
ré-ingestions. Construire la synthèse d'abord aurait produit des citations
posées sur du sable — précisément le défaut que l'état de l'art constate
partout ailleurs (§ 3). Et la couche corpus s'intercale parce que la synthèse a
besoin d'un périmètre défini par des humains (le carnet et ses facettes), pas
par une distance vectorielle (§ 4.3).

---

## 3. La méthode de vérification des preuves

C'est le cœur de la V3, et la partie de ce document qui mérite la lecture la
plus attentive. Elle repose sur une revue de l'état de l'art menée en août 2026
(note « Sourcing et attribution dans les systèmes RAG — état de l'art 2026 »,
mémoire Atomic), croisée avec la lecture du code source de plusieurs moteurs de
synthèse réels. **Tous les chiffres de cette section proviennent de benchmarks
et d'études menés sur d'autres systèmes — ALCE, LongBench-Cite, CiteControl,
FACTS notamment — et non de mesures sur Hypostasia.** Ils dimensionnent le
problème ; ils ne mesurent pas notre solution.

### 3.1 Quatre résultats qui dictent la conception

**1. Citation présente ≠ citation correcte.** Sur les benchmarks d'attribution
(ALCE, LongBench-Cite), les citations sont formellement présentes dans les
sorties, mais seulement **39 à 77 %** sont factuellement vérifiées — c'est-à-dire
que la source citée soutient réellement l'affirmation. Le taux de citation est
la métrique que la plupart des produits affichent, et c'est la moins
informative. Conséquence directe : afficher des renvois `[N]` ne prouve rien ;
il faut un étage qui *vérifie*, en aval de la génération.

**2. L'attribution s'effondre en multi-sources.** Dès qu'une affirmation
combine deux sources, l'attribution correcte tombe autour de **30 %**. Or toute
synthèse qui croise des documents — c'est-à-dire toute synthèse intéressante —
vit dans ce régime. Conséquence : l'état de vérification doit être porté **par
paire (affirmation, source)**, jamais par affirmation. Une phrase appuyée sur
deux sources ne peut pas porter un verdict unique : l'une des deux peut être
bonne et l'autre fausse, et c'est le cas le plus fréquent.

**3. Demander au modèle de citer plus finement *dégrade* l'attribution, de
16 à 276 %.** C'est le résultat le plus contre-intuitif et le plus actionnable
de la revue : contraindre le LLM à citer à la phrase plutôt qu'au paragraphe
*empire* la qualité d'attribution, dans des proportions massives. La leçon de
conception : **le grain fin doit venir d'une résolution mécanique en aval,
jamais d'une consigne au modèle.** On laisse le LLM citer au grain du
paragraphe — là où il est le moins mauvais — et on affine ensuite, par calcul.

    C'est exactement ce que l'ancrage par élément permet. Une extraction citée
    par la synthèse porte déjà ses portions : élément identifié par UUID,
    bornes dans le texte de cet élément (`AncrageExtraction`). Remonter d'une
    citation au passage exact — jusqu'au caractère, jusqu'au tour de parole
    horodaté pour l'audio — est une jointure, pas une prouesse du modèle. Le
    grain fin est *gratuit* parce qu'il a été payé une fois, à l'extraction,
    et vérifié par les mécanismes de la couche d'ancrage.

**4. 80,6 % des affirmations invérifiables sont des erreurs d'attribution, pas
des hallucinations.** Le contenu est vrai ; il est simplement rattaché à la
mauvaise source. C'est une bonne nouvelle : une erreur d'attribution est
**réparable par vérification automatique** — on peut chercher la bonne source
dans le périmètre —, alors qu'une hallucination ne l'est pas. Ce chiffre
justifie l'arbitrage central de la V3 : investir dans un étage de vérification
plutôt que dans un meilleur prompt.

### 3.2 L'architecture en cinq étages

L'état de l'art converge vers une architecture que la V3 adopte intégralement.
Chaque étage existe pour neutraliser un des échecs mesurés ci-dessus.

| # | Étage | Ce qu'il neutralise |
|---|---|---|
| 1 | Indexer **au grain de la preuve** | l'écart entre ce qu'on cite et ce qu'on peut montrer |
| 2 | **Sélectionner avant d'écrire** | le biais de sélection implicite du modèle |
| 3 | Générer au **grain du paragraphe**, résolution mécanique en aval | la dégradation de 16 à 276 % (résultat 3) |
| 4 | **Vérifier** : verbatim puis NLI | les 23 à 61 % de citations non soutenues (résultat 1) |
| 5 | Sérialiser en **W3C Web Annotation**, sélecteurs redondants | la fragilité des ancres dans le temps |

**Étage 1 — indexer au grain de la preuve.** L'unité indexée doit être ce qu'on
veut pouvoir montrer à l'utilisateur, pas le chunk de récupération d'un moteur
RAG. Chez Hypostasia, cette unité existe déjà : l'extraction et ses portions
ancrées. Un moteur qui indexe des chunks de 800 tokens ne pourra jamais
surligner la phrase exacte ; un moteur qui indexe des preuves le fait par
construction.

**Étage 2 — sélectionner les preuves avant d'écrire.** Le modèle reçoit un
ensemble de preuves déjà choisi ; il ne les choisit pas en rédigeant. Sinon la
sélection est invisible, non reproductible, et impossible à contester. *Comment*
choisir est le sujet de `SPEC-selection-des-preuves.md`, et le point où
Hypostasia diverge frontalement de la pratique courante (§ 4.3) : le périmètre
est défini par les facettes du carnet — un humain a rangé, un humain filtre —,
le regroupement s'énumère au lieu de s'échantillonner, et une passe transverse
cherche les oppositions que la géométrie ne peut pas voir.

**Étage 3 — générer au grain du paragraphe, avec des citations résolues
mécaniquement.** Le modèle cite des sources numérotées ; le code résout. Détail
qui compte : **le numéro `[N]` n'est jamais stocké** (`SPEC-synthese-carnet.md`
§ 4.3). Il est attribué à l'affichage, par ordre d'apparition, à partir
d'identifiants d'extraction persistés. Un index stocké est instable entre deux
ingestions : une citation `[3]` mémorisée pointerait vers autre chose après
réindexation — défaut observé dans le code d'un moteur réel, où la
déduplication par index détruisait en outre l'information de *quelle*
affirmation citait quoi.

Le lien persisté est `SourceLink` (`core/models.py:1439`) : quelle extraction
(`extraction_source`), quelle portion exacte (`ancrage_source`), dans quel
article, dans quelle section, avec quel état de vérification. Il est écrit
depuis le 9 août par `indexer_les_citations()` : le markdown est la vérité, les
liens n'en sont que l'index, reconstruit à chaque enregistrement à partir des
marqueurs `[[ext:N]]`. Le durcissement voulu par la spec est en place, sous une
forme plus fine qu'un `PROTECT` global : un signal `pre_delete` refuse la
suppression d'une extraction citée par une synthèse **dirigée** (l'acte daté ne
perd pas ses preuves) et bascule à l'état `SUPPRIMEE` les citations d'un simple
wiki (vivant, le tour suivant corrige). Jamais d'orphelinage silencieux dans un
cas comme dans l'autre.

**Étage 4 — vérifier, en deux contrôles en cascade.**

1. **Verbatim** : le texte cité existe-t-il littéralement dans la source ?
   Contrôle déterministe, sans modèle, coût nul.
2. **Implication (NLI)** : la source soutient-elle l'affirmation ? Un modèle
   léger de vérification (type MiniCheck dans l'état de l'art) suffirait, avec
   droit de veto.

   Le choix du juge a été tranché par le propriétaire le 9 août
   (`SPEC-synthese-carnet.md` § 14, question n°3) : **ce sera le LLM déjà
   configuré**, appelé **en lot** (une requête juge N paires) et **à la
   demande** — un geste explicite de vérification, jamais automatique à la
   production. Le calcul est celui d'un serveur de 8 Go partagé avec la
   production : de l'ordre de 0,01 à 0,05 € par synthèse en lot, contre ~1 Go
   de RAM permanente pour un modèle local de moindre qualité sur du français
   délibératif. L'interface du service reste prévue pour brancher un modèle
   local plus tard sans réécriture.

L'ordre importe : le verbatim élimine à coût nul les cas où le modèle a déformé
la citation ; le NLI, plus coûteux, ne traite que ce qui reste. C'est l'étage
que le résultat 4 justifie : puisque 80,6 % des invérifiables sont des erreurs
d'attribution réparables, un vérificateur automatique récupère l'essentiel de
ce qu'un meilleur prompt ne récupérerait pas.

**Étage 5 — sérialiser en W3C Web Annotation, avec des sélecteurs redondants.**
`TextQuoteSelector` (le texte exact, avec préfixe et suffixe),
`TextPositionSelector` (les offsets), et `FragmentSelector` avec Media
Fragments URI pour l'audio et la vidéo (`t=npt:847.2,863.5`). La redondance
n'est pas décorative : c'est ce qui permet de retrouver une ancre après édition
du document — si les offsets ont glissé, la citation avec son contexte permet
de la relocaliser, et c'est déjà la logique de `reconciliation.py`. Le format
est un standard ouvert : une annotation Hypostasia doit rester lisible hors
d'Hypostasia.

### 3.3 Les trois états affichés — et ce qu'ils n'établissent pas

À l'écran, chaque affirmation porte un état : **vérifié** (verbatim et NLI
passent), **faible** (le passage existe mais le soutien est incertain), **non
sourcé** (rien dans le périmètre ne soutient l'affirmation). Trois états et non
une avalanche de scores : c'est un choix d'interface assumé, motivé par le
résultat inconfortable du § 3.6.

Ce que ces états n'établissent **pas** doit être dit avec la même clarté, parce
qu'en contexte de gouvernance, « vérifié » sera lu comme « validé par
quelqu'un ». Il ne l'est pas. Trois conséquences, inscrites dans la spec
(`SPEC-synthese-carnet.md` § 7.2) :

- **L'état porte son vérificateur** : modèle, version, date, seuil. Un état
  sans provenance est un argument d'autorité automatisé.
- **L'état est contestable** : on peut débattre d'une extraction, il faut
  pouvoir débattre d'un verdict. Un humain peut poser un état « contesté ».
- **L'état est par paire (affirmation, source)** — voir résultat 2. Une phrase
  à deux sources porte deux verdicts.

Deux raffinements complètent le tableau. D'abord, **le statut de débat remonte
à la citation** : une affirmation « vérifiée » peut reposer sur une extraction
que trois commentaires contestent — le renvoi doit le montrer, sinon le vert
ment par omission. Ensuite, la **provenance « débat »** : une affirmation peut
venir d'un commentaire et non d'une extraction — *« un avenant écrit a été
chiffré à trois cents euros »* vient d'un commentaire d'Amina, pas du rapport.
Classer ce cas « faible » maquillerait une provenance parfaitement légitime ;
`SourceLink.commentaires_source` existe pour la porter, et la spec demande un
état ou un attribut propre : sourcé par le débat.

### 3.4 Ce qui n'a pas été repris — la différence d'ensembles

Une synthèse dit ce qu'elle retient ; elle ne dit jamais ce qu'elle a laissé de
côté. Or c'est calculable **sans aucun appel au modèle** :

```
écartées = extractions du périmètre − extractions citées
```

(`SPEC-synthese-carnet.md` § 8 ; pour une synthèse dirigée, le périmètre est
figé à la production, sans quoi la question « qu'a-t-on écarté en mars ? »
recevrait une réponse recalculée aujourd'hui, c'est-à-dire une réécriture en
douce.)

Le calcul est codé depuis le 9 août (`core/services/synthese.py`), et la
relecture adverse l'a durci sur deux points qui méritent d'être dits. D'abord,
le périmètre d'une dirigée est figé **deux fois** : les notes *et* les
extractions effectivement proposées au modèle (`extractions_du_perimetre` +
un drapeau, migration `core.0051`) — sans ce second figeage, une ré-analyse
postérieure réécrivait « ce que la synthèse n'a pas repris » avec des
extractions que l'acte daté n'avait jamais vues. Ensuite, les 292 synthèses
historiques n'ont pas ce périmètre : plutôt que d'annoncer « tout a été
écarté », le service **refuse explicitement** de répondre pour elles. Une
réponse fausse à charge aurait été pire que pas de réponse. (Un drapeau levé
sur un périmètre vide, lui, veut dire « rien n'avait été proposé » : écartées
= ∅, et non « tout ».)

C'est probablement la fonctionnalité la plus différenciante de la V3, pour deux
raisons qui tiennent en une phrase chacune. **Elle ne coûte rien** : une
différence d'ensembles est déterministe, rejouable, et son coût LLM est zéro.
**Personne d'autre ne l'offre** : la revue d'état de l'art n'a trouvé aucun
système comparable qui montre ses écartées — et c'est ce qui transforme une
synthèse en objet contestable, donc utilisable dans une gouvernance : *voici
les arguments que la synthèse n'a pas repris*.

Une règle absolue en découle : **jamais une liste stockée, toujours un calcul.**
Dans la maquette, la liste écrite à la main était fausse sur trois articles sur
quatre avant qu'on la calcule. Et une limite à afficher plutôt qu'à taire :
cette différence n'audite que les *citations* — une extraction lue par le
modèle et utilisée sans être citée la traverse. C'est une borne inférieure de
contrôle, pas une garantie.

### 3.5 La couverture — « inventé » n'est pas « jamais extrait »

« Non sourcé » confond aujourd'hui deux situations très différentes : le modèle
a inventé — rien dans le document ne le dit — ou le modèle a raison, mais **le
passage n'a jamais produit d'extraction**. Le cas est réel dans l'étalon : la
synthèse du 12 mars affirme *« l'ordre du jour sera transmis par écrit »*,
marquée non sourcée — alors que Jonas le dit littéralement au dernier tour de
parole. Le passage existe ; l'analyse ne l'a simplement jamais extrait. Sans
correctif, la chaîne d'audit présente comme une invention potentielle ce qui
est un trou de couverture — un faux positif qui décrédibilise l'outil là où il
prétend être rigoureux.

La **couverture** répond : quels éléments du document portent au moins une
extraction, lesquels n'en portent aucune. C'est une jointure
(`portions_d_extractions`, `hypostasis_extractor/models.py:706`), pas une
estimation — aucun appel au modèle. Le calcul est codé (phase D, même service
que les écartées) ; l'écran, lui, reste à faire. À l'écran il montrera un
liseré élément par élément et un chiffre global — *« 14 éléments sur 41 portent
une extraction »*. Avant d'adopter une synthèse, savoir que l'analyse a lu un
tiers du document ou sa totalité change tout.

Deux honnêtetés à afficher avec le chiffre. La jointure ne compte ni les
extractions masquées, ni les ancres détachées, ni les jobs inachevés — sans
quoi la couverture se gonflerait de ce qui n'est plus une preuve. Et le
dénominateur inclut les éléments non textuels (titres, tableaux) qui ne
porteront jamais d'extraction : ce rapport n'est pas un pourcentage de lecture
comparable d'un document à l'autre.

Avec les écartées, la chaîne d'audit est complète : la couverture dit ce qui
n'est **jamais entré** dans le périmètre ; l'écart dit ce que la synthèse a
**laissé** parmi ce qui y était.

### 3.6 Le résultat inconfortable : r = −0,96

La revue d'état de l'art rapporte une corrélation de **−0,96 entre la précision
des citations et l'utilité perçue par les utilisateurs** (mesurée sur d'autres
systèmes, pas sur Hypostasia). Autrement dit : plus un système est rigoureux
sur ses sources, moins les gens l'aiment. Un texte constellé de renvois, de
réserves et d'états de vérification se lit mal ; un texte fluide et affirmatif
inspire confiance — à tort.

On ne cache pas ce résultat, on en fait un arbitrage explicite plutôt qu'un
arbitrage subi :

- **trois états** visuellement discrets, pas un score par phrase ni une
  avalanche de badges — la rigueur est disponible au clic (le panneau de preuve
  montre la citation exacte, le débat attaché, le lien vers la source), pas
  imposée à la lecture ;
- les écartées et la couverture vivent dans des panneaux dépliables, pas dans
  le corps de l'article ;
- et le public visé n'est pas celui des benchmarks : un collectif qui adopte
  une synthèse en assemblée a un rapport à la vérifiabilité qu'un utilisateur
  de chatbot n'a pas. C'est un pari, il est assumé, et il est dit ici pour que
  le lecteur de 2027 sache que le choix a été fait en connaissance de cause.

---

## 4. L'inspiration Atomic

### 4.1 Ce qu'est Atomic

[Atomic](https://github.com/kenforthewin/atomic) est une base de connaissances
personnelle open source (MIT, Rust + React), local-first — « your notes, your
hardware, your model ». Ses notes markdown (« atoms ») forment un graphe
sémantique, et sa fonctionnalité phare est la **synthèse wiki** : un article
vivant par sujet, généré avec citations inline à partir de tous les atoms qui
le touchent, mis à jour quand la base grossit. Le code d'Atomic (v1.43.0) a été
lu intégralement lors de l'analyse comparative d'août 2026 (note « Trois
moteurs RAG open source décortiqués », mémoire Atomic) ;
`PLAN/INSPIRATION_ATOMIC.md` (2 100 lignes) en avait déjà tiré une spec de
refonte en avril.

### 4.2 Ce qu'on lui prend

**Le wiki thématique et vivant.** Un article par sujet, alimenté par les
extractions du carnet, qui se suit plutôt qu'il ne s'adopte. C'est le premier
des deux genres de synthèse de la V3 — l'autre, la synthèse dirigée figée,
n'a pas d'équivalent chez Atomic et vient des besoins de gouvernance
d'Hypostasia.

**La mise à jour par opérations de section, pas par réécriture.** Quand le
carnet grossit, le modèle ne régénère pas l'article : il renvoie une liste
d'opérations structurées — `NoChange`, `AppendToSection`, `ReplaceSection`,
`InsertSection` — qu'un applieur fusionne (`PLAN/INSPIRATION_ATOMIC.md` § 7).
Bénéfices : les sections non touchées restent intactes au caractère près, le
coût LLM se limite au diff, et chaque tour est inspectable.

L'applieur existe (`core/services/section_ops.py`, 9 août) : fonction pure,
schéma d'opérations contractualisé dans la spec, rejet **par opération** — une
hallucination ne jette pas les faits des autres opérations —, et un contrôle
optimiste de concurrence qui refuse visiblement une proposition périmée plutôt
que d'écraser un article qui a bougé entre-temps. Les sources d'une opération
ne sont pas un champ parallèle déclaré par le modèle : elles sont **dérivées**
des marqueurs présents dans le contenu, parce que le markdown est la vérité.
Ce qui manque est l'étage au-dessus : le prompt qui produit ces opérations et
l'écran qui montre le diff (phases G à I).

**Le cycle proposition → diff → acceptation.** La synthèse n'écrase jamais un
contenu existant : elle propose un diff qu'un humain accepte. Avec une
exigence ajoutée par la spec : le diff d'un `ReplaceSection` doit montrer
l'*avant* — approuver une réécriture sans voir ce qui disparaît n'est pas une
acceptation.

**Le rejet mécanique des propositions dont le titre de section n'existe pas.**
Un `heading` absent de l'article ne peut pas être une approximation de
placement : c'est une hallucination du modèle. La règle « titre introuvable =
proposition rejetée » est un garde-fou déterministe, sans heuristique et sans
appel au modèle. La V3 le reprend et l'étend : une opération dont les sources
sont vides, ou dont une source n'appartient pas au périmètre, est rejetée de la
même façon (`SPEC-synthese-carnet.md` § 6.3).

### 4.3 Ce qu'on corrige

La lecture du code d'Atomic a autant appris par ses défauts que par ses
qualités. Trois corrections explicites :

| Comportement d'Atomic (et du § 7 initial) | Correction V3 |
|---|---|
| Titre introuvable → `logger.warning`, **contenu jeté en silence** | rejet **visible**, contenu conservé et montré |
| `after_heading` introuvable → **fallback en fin d'article** | rejet visible — insérer à un endroit que le modèle n'a pas choisi est pire qu'un rejet, parce que personne ne le voit |
| Numérotation `[N]` **stockée** dans le markdown | jamais stockée : identifiants persistés, numéros attribués à l'affichage |

Ces trois corrections sont codées et testées. La relecture adverse en a ajouté
deux que personne n'avait vues, et qui relèvent de la même famille : le contenu
d'une opération pouvait **contenir** une ligne de titre et fabriquer ainsi une
section que l'humain n'avait pas approuvée — au titre dupliqué, donc ambiguë
pour toujours ; et une insertion sous un titre déjà présent produisait la même
corruption. Les deux sont désormais rejetées. Seule l'opération d'insertion
crée une section.

S'y ajoutent les défauts relevés dans le moteur de citations d'Atomic, qui ont
directement façonné l'architecture du § 3 : grain limité au chunk (impossible
de remonter à la phrase), index instable entre deux ingestions, citations non
résolvables silencieusement supprimées, clé étrangère désactivée (les
citations survivent à la suppression de leur source), et **zéro vérification**
que le chunk cité soutient l'affirmation. Chaque étage de la V3 répond à l'un
de ces points.

### 4.4 Ce qu'on refuse : la sélection par centroïde

Atomic sélectionne les preuves d'un wiki par **proximité au centroïde
sémantique** : le point moyen des contenus d'un sujet, puis les *K* plus
proches. Pour une base de connaissances personnelle, c'est un bon choix — on
veut l'idée dominante. **Pour une synthèse délibérative, c'est structurellement
destructeur** : une position minoritaire est, par construction géométrique,
éloignée de la moyenne. Elle ne remonte jamais. Ce n'est pas un défaut de
réglage — c'est ce que l'algorithme calcule ; augmenter *K* ne change pas
l'ordre, on descend juste plus bas dans une liste triée par conformité.

Le cas est monté dans l'étalon : une extraction dit que *« la renégociation du
bail repose sur un accord verbal avec le propriétaire actuel »*. Personne
d'autre n'en parle — donc elle est loin du centre — alors qu'un membre du
conseil la commente : *« c'est le vrai risque du budget »*. Un tri par
centralité l'écarte ; une synthèse budgétaire sans elle est fausse.

D'où la règle de `SPEC-selection-des-preuves.md`, volontairement plus sévère
qu'une version intermédiaire :

> **Le centroïde n'est ni nécessaire pour former un groupe, ni admissible pour
> le représenter. Il ne sert qu'à décrire un groupe déjà formé.**

« Ni nécessaire pour former » : l'algorithme retenu — agglomératif à liaison
simple, avec seuil de distance — compare des paires de membres, jamais un
centre ; il accepte les singletons (une position isolée reste un groupe
visible, elle n'est pas absorbée), ne demande ni *k* ni graine (donc
reproductible, donc auditable), et chaque appartenance s'explique par une
arête : *« entrée parce qu'à distance 15 d'un membre, sous le seuil de 24 »* —
une explication qu'un humain peut contester. Il a son propre défaut, et il est
sérieux — voir § 4.5.

« Ni admissible pour représenter » : **un groupe s'énumère, il ne
s'échantillonne pas.** Toutes les extractions du groupe partent au modèle ; le
groupe structure le contexte, il ne le réduit jamais. Chiffré sur l'étalon :
résumer chaque groupe par son membre le plus central efface 11 extractions sur
19 — et dans le pire cas, le représentant n'est *ni l'une ni l'autre* des deux
faces d'un désaccord : les deux disparaissent, sans laisser trace qu'il y a eu
débat.

Deux compléments que la géométrie ne peut pas fournir. Les embeddings mesurent
le *sujet*, pas la *position* : deux avis opposés sur la même question sont
proches. Une **passe transverse** (LLM, sur tout le périmètre, jamais groupe
par groupe) produit la liste des oppositions — y compris celles dont les deux
faces n'ont aucun mot en commun. Et le **tri par le débat** exploite le signal
qu'aucun autre outil ne possède : une extraction portant trois commentaires
contradictoires est littéralement le contraire d'un consensus ; le centroïde la
rejetterait, Hypostasia la fait remonter en premier. Ce signal n'a rien coûté à
produire : c'est la délibération elle-même.

---

### 4.5 Le défaut de la méthode retenue, et pourquoi on le montre

Un document qui n'exposerait que les défauts des méthodes écartées serait
malhonnête. La liaison simple a le sien, et il est sérieux : **l'effet de
chaîne**. A touche B, B touche C, et A se retrouve groupé avec C sans l'avoir
jamais approché. Un seul point intermédiaire peut fusionner deux sujets sans
rapport.

L'étalon le monte délibérément : une extraction qui parle du seuil financier
*et* des statuts relie deux grappes distantes. Au-delà d'un certain seuil, elles
n'en font plus qu'une, et le groupe résultant mélange « comment décider » et
« le cadre statutaire ».

Ce n'est pas masqué, c'est **mesuré et affiché**. Pour chaque groupe d'au moins
trois membres, l'écran indique son **diamètre** — la plus grande distance entre
deux de ses membres — et la **part de ses paires au-delà du seuil** : ces
membres-là ne se sont jamais approchés, ils sont ensemble par un chemin. Quand
cette part dépasse un tiers, un avertissement le nomme.

Un détail de conception mérite d'être raconté, parce qu'il illustre le genre
d'erreur que ce dispositif doit attraper : la première version de la détection
alertait quand le diamètre dépassait 2,2 fois le seuil. En montant le seuil,
l'alerte **disparaissait** — alors que la fusion s'aggravait. Un critère
proportionnel au réglage masque le problème à mesure qu'il grandit. La mesure
retenue — la part des paires hors seuil — ne dépend d'aucun facteur arbitraire.

**Ce que l'étalon établit, et ce qu'il n'établit pas.** Il établit que résumer
un groupe par son membre central est destructeur : c'est chiffré, 11 extractions
effacées sur 19, et dans certains cas les *deux* faces d'un désaccord — le
représentant n'étant ni l'une ni l'autre, il ne reste aucune trace qu'il y a eu
débat. Il n'établit pas que la formation des groupes soit sans danger : elle a
le sien, et il faut le regarder.

---

## 5. L'inspiration Praxis

### 5.1 Ce qu'est Praxis

[Praxis](https://praxis.encommun.io/) (« En commun ») est une plateforme
québécoise de mise en commun des savoirs, éditée par Projet collectif, un
OBNL. Analyse menée en août 2026 sur la documentation et des corpus réels en
ligne — pas de code source public (note « Praxis — plateforme de gestion de
corpus à trois niveaux », mémoire Atomic). Ordres de grandeur observés :
944 carnets, des corpus de plusieurs centaines de notes, 4 855 notes
« organisation » géolocalisées. Le modèle : **note** (unité de connaissance) →
**carnet** (collection de notes) → **base de connaissances** (ensemble de
carnets), avec deux relations **N-N** — une note vit dans plusieurs carnets, un
carnet dans plusieurs bases — et un niveau base facultatif. Ce ne sont pas
trois étages d'un arbre : c'est un graphe à trois types de nœuds.

### 5.2 La catégorie portée par la relation — le point qui ne se devine pas

C'est le détail du modèle Praxis qui change tout, et le seul qui compte
vraiment : **la catégorisation d'une note est contextuelle au carnet.** La
catégorie n'est pas un attribut de la note ; c'est un attribut de la *relation*
note↔carnet.

Exemple concret, transposé dans les maquettes : le compte rendu du conseil du
12 mars appartient au carnet « Conseil d'administration » *et* au carnet
« Veille financement ». Dans le premier, il est classé **« Budget »** ; dans le
second, **« Subvention »**. Même note, deux classements — et aucun des deux
n'est « le bon » : chacun répond à la question de son carnet. (Chez Praxis, le
cas documenté est la note « Appel à projets APCHQ 2026 », catégorisée
différemment dans ses deux carnets.)

La conséquence est politique avant d'être technique : **chaque collectif garde
son vocabulaire de classement sans imposer le sien aux autres.** Si les
catégories étaient portées par la note, le premier collectif à classer
imposerait sa taxonomie à tous les suivants — exactement ce qu'un outil de
communs ne doit pas faire. Techniquement, cela se traduit par des tables de
liaison qui portent les catégories (`AppartenancePageDossier`,
`AppartenanceDossierBase`), avec une validation applicative : une catégorie
appliquée doit appartenir au carnet de l'appartenance. Elle est codée à deux
étages — le formulaire, pour une erreur lisible, et un signal, pour qu'un
`.add()` lancé depuis un shell soit refusé lui aussi. Sans ce filet, le
vocabulaire d'un carnet fuirait dans un autre, c'est-à-dire exactement ce que
la catégorie portée par la relation existe pour empêcher.

Les catégories sont elles-mêmes groupées en **axes** (chez Praxis : jusqu'à
trois listes de dix catégories par carnet) — classer par thème *et* par
échéance *et* par territoire sont trois questions indépendantes, pas une seule
liste plate. Ces axes sont ce qui donnera plus tard son périmètre à la synthèse
dirigée : on synthétise *par axe*, pas « les cinquante notes les plus
centrales ».

### 5.3 Ce qu'on prend d'autre

- **L'épinglage et l'ordre manuel**, pour donner à un carnet un ordre
  **narratif** — les temps d'une délibération — et pas seulement
  chronologique. Praxis s'en sert pour des actes de symposiums.
- **Le guide de rédaction par carnet**, affiché au contributeur *au moment où
  il contribue*, pas rangé dans une page d'aide. Praxis assume que produire un
  bon corpus est un travail coûteux, et l'outille.

Reporté, mais noté : citation APA et licence par note, flux RSS à quatre
granularités, rôles fins gestionnaire/contributeur.

### 5.4 Ce qu'on refuse : la conversation déportée

**Praxis n'a aucune fonction de commentaire, nulle part** — ni sur les notes,
ni sur les carnets, ni sur les termes du lexique. La conversation est déportée
sur Passerelles, la plateforme de discussion du même éditeur. C'est cohérent
pour une base de savoirs *stabilisés* : un fil de discussion sous chaque fiche
abîmerait les deux.

Hypostasia refuse ce choix, et ce refus est sa différenciation : **le
commentaire sur une extraction *est* la délibération.** L'outil n'archive pas
un savoir stabilisé, il fait travailler un désaccord. Les extractions et les
commentaires appartiennent à la note, pas au carnet : une note dans deux
carnets a un seul débat, visible des deux — le filtrer par carnet
fragmenterait la délibération selon qui range quoi où. Conséquence à dire
honnêtement à l'utilisateur : ranger une note dans un carnet public n'expose
pas que le texte, mais aussi les analyses et les commentaires avec le nom de
leurs auteurs — dans le cas du lycée, des échanges d'élèves. L'avertissement
doit être chiffré et nommer ce qui sort.

### 5.5 La conséquence d'interface : le N-N détruit l'arbre

Découverte structurante de la spec corpus : la navigation actuelle est un arbre
(`arbre_dossiers.html`), et **un arbre suppose un parent unique**. Sous le N-N,
la même note apparaîtrait sous deux carnets — question sans réponse à l'écran :
est-ce la même note ou deux copies ? Si j'en supprime une, l'autre
disparaît-elle ? Praxis, significativement, n'a pas d'arbre.

Principe retenu : **l'overlay de navigation ne montre plus jamais de notes,
seulement des contenants** (bases et carnets). Le clic sur un carnet charge ses
notes dans la colonne de lecture ; on est toujours *dans* un carnet, un seul à
la fois — la question du parent ne se pose jamais. Le contexte perdu est rendu
par un **fil d'Ariane à bascule** : `Base › Carnet ▾ › Note`, où le chevron
ouvre la liste des carnets contenant la note et recharge la même note dans un
autre contexte. Et la multi-appartenance devient visible là où elle a du
sens : une bande « Dans N carnets » sur la note, montrant ses catégories dans
chacun — c'est ce bloc qui rend le modèle compréhensible sans l'expliquer, on
*voit* que les étiquettes diffèrent d'une ligne à l'autre.

**Où en est ce principe.** Le bloc « Dans N carnets » existe et il est éditable
(phase G) : chaque ligne montre un carnet, les catégories de la note *dans ce
carnet-là*, et son nom rouvre la note dans ce contexte — la bascule est donc
déjà là, sous une autre forme. Le reste ne l'est pas : l'arbre de navigation
existe toujours et montre toujours des notes, et le fil d'Ariane à bascule
`Base › Carnet ▾ › Note` n'est pas construit. Les écrans neufs (`/carnets/`,
`/bases/`) cohabitent aujourd'hui avec l'ancienne navigation au lieu de la
remplacer. C'est un chantier d'interface identifié, pas un principe abandonné.

---

## 6. Ce qui est déjà là, ce qui reste à faire

État des lieux factuel, chaque affirmation vérifiée sur le dépôt le 9 août 2026
au soir. Les migrations appliquées sur la base de développement vont jusqu'à
`core.0051`.

### 6.1 Implémenté et migré : le moteur d'ancrage par élément

Les services listés au § 2.1 existent et sont testés (par exemple 19 tests à
LLM simulé plus 3 à appels réels pour `analyse_par_element.py`, 24 pour
`garde_edition.py` — `CHANGELOG.md`, entrées du 5 août 2026). Les migrations de
schéma sont en place (`core` 0035 à 0039, `hypostasis_extractor` 0031 à 0033).

La bascule des données existantes est faite : la commande
`manage.py basculer_vers_le_moteur_element`
(`core/management/commands/basculer_vers_le_moteur_element.py`) a été exécutée
sur la base de développement — 538 pages, 29 921 extractions, 13 174 éléments
créés. Trois versions successives de la méthode de ré-ancrage ont été
comparées ; la version retenue traduit les anciens offsets par intersection
plutôt que de rechercher le texte.

**Deux mesures, deux périmètres — les deux comptent.** Sur l'échantillon de
contrôle des extractions commentées, celles qui portent un débat et qu'il
fallait absolument préserver, le ré-ancrage atteint **99,7 %** (113 sur 115),
contre 39,7 % pour la recherche de texte initiale. Sur l'**ensemble** des
29 921 extractions, la première version de la commande n'en récupérait que
28,7 % (8 585 ancres) ; le `CHANGELOG.md` conserve ce chiffre en tête de son
entrée du 5 août sans le mettre à jour après le passage à la traduction
d'offsets. **Le taux global après la version finale n'est donc pas
documenté** — à remesurer avant de le citer. Ce qui est établi : aucune
extraction ni aucun commentaire n'a été supprimé, et ce qu'on ne retrouve pas
reste en base, détaché, pour qu'un humain tranche.

**Nuance à connaître, et elle est importante** : le pipeline d'analyse du moteur
ELEMENT n'est toujours appelé par aucune tâche Celery ni aucune vue, et le
service de rendu par éléments (`front/services/rendu_elements.py`) n'est appelé
par rien non plus — l'un comme l'autre n'existent que pour leurs propres tests
(vérifié par recherche exhaustive le 9 août). Il manque la tâche, le bouton, le
compteur de tokens, et le branchement de l'affichage. Le moteur est prêt ; il
n'est pas branché au parcours utilisateur, et les phases H à K de la spec
d'ancrage — celles qui le brancheraient — ne sont pas commencées.

Conséquence directe à connaître avant de lire le § 3 : le seul chemin d'édition
de texte réellement exposé aux utilisateurs aujourd'hui reste celui de l'ancien
moteur (`editer_bloc`), et il n'est **pas** gardé. Le propriétaire l'a tranché
le 9 août (`SPEC-synthese-carnet.md` § 14, question n°5) : au plus simple, on ne
garde pas l'ancien chemin, et le gel effectif des sources citées sera livré avec
le branchement du moteur élément. D'ici là, un passage cité par une synthèse
adoptée reste techniquement modifiable par l'ancien chemin. C'est assumé, et
c'est dit.

### 6.2 Codé : la couche corpus, et le socle de la couche synthèse

**La couche corpus est faite.** Les huit phases A à H ont été livrées les 8 et
9 août, avec leurs relectures adverses et les trous de spec bouchés :

- les six modèles (`BaseDeConnaissances`, `AppartenancePageDossier`,
  `AppartenanceDossierBase`, `ListeDeCategories`, `CategorieDossier`,
  `CategorieBase`), le champ `role_special` qui remplace le repérage des
  carnets « magiques » par leur nom, et les migrations `core.0040` à `0045`
  (dont deux migrations de données réversibles : 537 pages avec dossier →
  537 appartenances, cohérence contrôlée) ;
- la validation des catégories par la relation, à deux étages ;
- les permissions dérivées des carnets — l'accès prend le carnet le plus
  permissif, la propriété s'élargit à l'owner d'un carnet contenant la note —
  et la bascule **en un seul lot** de tous les lecteurs de `Page.dossier` vers
  la table de liaison ; une conversion progressive aurait laissé une note
  ajoutée à un second carnet invisible dans ce carnet ;
- les endpoints (carnet, rangement, catégorisation, épinglage, ordre manuel,
  bases) et les écrans : carnet avec facettes, note avec son bloc « Dans N
  carnets », liste et détail des bases ;
- de l'ordre de 150 tests dédiés à cette couche, dont cinq scénarios de bout en
  bout dans un vrai navigateur, et les 37 contrôles de l'étalon qui passent.

Ce qui reste sur cette couche : la phase I (reprise du drag-drop et des derniers
écrans multi-carnets) et la **migration 3**, le retrait de `Page.dossier`. La
clé étrangère est toujours là, écrite par un seul service, et elle porte le
« premier carnet » pendant la coexistence — son retrait attend la recette.

**La couche synthèse est codée pour tout son socle hors interface**, phases A à
F, chacune relue de façon adverse :

- `type_de_note` et le garde-fou « une synthèse n'est jamais source » (A) ;
- `SourceLink` complété et l'indexeur de citations (B, ci-dessous) ;
- les deux genres au modèle — `Wiki` (périmètre par catégories, recalculé à
  chaque appel) et `SyntheseDirigee` (périmètre de notes figé) —, migration
  `core.0049`, plus `core.0050` qui a estampillé les 292 synthèses historiques
  d'un enregistrement de synthèse dirigée (C) ;
- les écartées et la couverture (D, § 3.4 et § 3.5) ;
- la garde d'édition des sources citées (E, § 5 de la spec) ;
- l'applieur d'opérations de section (F, § 4.2 ci-dessus).

**Le point le plus visible pour un utilisateur** : `synthetiser_page_task` a été
réécrite. La synthèse n'est plus une version du document mais une note typée du
carnet ; `parent_page` n'a plus aucun écrivain en production, ce qui rend le
versionnage de page **dormant** — le schéma reste, plus personne ne l'alimente.
La tâche exige du modèle des marqueurs `[[ext:N]]` et une ligne de contrôle
finale : sans elle, la génération est tenue pour tronquée et l'échec est
bruyant, rien n'est enregistré. Une synthèse tronquée passée pour un succès
serait pire qu'une erreur. Le HTML dérivé passe par une allowlist stricte
(un `[texte](javascript:…)` traversait l'échappement et devenait un lien actif),
et la page, ses liens de citation, ses appartenances et son acte daté naissent
dans une seule transaction.

Ce qui **n'est pas** fait sur cette couche : la vérification elle-même
(phase G — verbatim, NLI en lot, les trois états, la provenance « débat »), **en
cours d'implémentation** au moment où ces lignes sont écrites ; et toute
l'interface — onglets Wikis et Synthèses du carnet, article, panneau de preuve
(H), diff des opérations avec l'avant (I). Une synthèse produite aujourd'hui
apparaît dans l'arbre latéral mais pas dans l'écran carnet, qui ne liste que les
notes ordinaires ; c'est un séquencement assumé, l'inverse l'aurait rendue
invisible partout.

Enfin, `SPEC-selection-des-preuves.md` (§ 4.3 à 4.5 de ce document) n'est pas
entamée : ni regroupement, ni passe transverse, ni tri par le débat, ni
`RegroupementRun`, ni `Opposition`. C'est le prochain gros bloc après la
vérification.

**Un chantier décidé, pas encore ouvert : la bascule CSS.** Le propriétaire a
tranché le 9 août — l'ancien CSS est à jeter, le design de la maquette fait foi,
et la bascule se fait **à fonctionnalité constante**. Elle est positionnée juste
avant la phase H de la spec synthèse, pour une raison de coût : cette phase bâtit
trois écrans neufs qui n'existent que dans l'étalon, et les écrire sur l'ancien
CSS reviendrait à les écrire deux fois. Le cahier des charges est dans
`PLAN/bascule-css-cahier-des-charges.md` ; il est explicitement un document de
travail à arbitrer, rien n'est engagé.

### 6.3 `SourceLink` : le schéma a trouvé son écrivain

`SourceLink` existait en base depuis les migrations `core.0026` puis `core.0036`
(qui lui avait ajouté `ancrage_source`), mais **aucun code de production ne
l'écrivait ni ne le lisait** — c'était le blocage central relevé par la première
version de ce document. Il est levé depuis le 9 août.

La migration `core.0048` lui a ajouté ce qui manquait : la section et le rang
dans la section, l'état de vérification **par paire** (affirmation, source) — la
leçon du résultat 2 du § 3.1 —, l'état de la source (présente, supprimée,
détachée) et le type de lien « cite ». `indexer_les_citations()` l'écrit, la
tâche de synthèse l'appelle avec un périmètre désormais **obligatoire** dans sa
signature, et un marqueur inexistant ou hors périmètre est retiré du texte *et*
signalé : jamais gardé en silence, jamais accepté en silence non plus. La dérive
se propage — une ancre que la réconciliation, le masquage ou la réingestion fait
passer à l'état détaché détache la citation qui la pointait.

Restent théoriques, faute de la phase G et des écrans : les trois états affichés
et le retour visuel à la source depuis une citation. Le lien, lui, est peuplé.

### 6.4 pgvector : pas installé, et pas nécessaire tout de suite

Vérifié : `docker-compose.yml:50` utilise `postgres:17-alpine` (pas l'image
pgvector), `pyproject.toml` ne contient ni pgvector ni sentence-transformers,
et aucun modèle ne porte de champ `embedding`. C'est planifié (PHASE-33,
`PLAN/README.md:126`), pas fait. `SPEC-selection-des-preuves.md` § 7 tranche
qu'il ne faut pas l'attendre : à l'échelle d'un carnet — quelques centaines
d'extractions — un cosinus O(n²) en numpy suffit largement ; pgvector sert la
recherche à l'échelle de la base entière, ce qui est un autre problème.

### 6.5 Note sur les documents de référence

Quatre specs se complètent, et elles doivent être lues dans cet ordre :

| Spec | Couche | Dans le dépôt |
|---|---|---|
| `SPEC-ancrage-par-element-v2.md` v2.0 | ancrage — élément, portion, réconciliation | oui, déposée le 8 août 2026 — **implémentée**, avec trois écarts documentés ; phases H-K (branchement) non commencées |
| `SPEC-corpus-base-carnet-note.md` v1.1 | corpus — base, carnet, note, catégories | oui — **implémentée** (phases A-H), reste la phase I et la migration 3 |
| `SPEC-synthese-carnet.md` v1.0 | synthèse — deux genres, sourcing, vérification | oui — **implémentée hors interface** (phases A-G), 16 addendums en tête de fichier ; H-I à faire |
| `SPEC-selection-des-preuves.md` v1.0 | sélection — regroupement, oppositions, audit | oui — non entamée |

Les quatre sont maintenant dans le dépôt. Celle d'ancrage y figure bien qu'elle
soit déjà implémentée, et c'est délibéré : le code porte ce qui a été retenu,
jamais ce qui a été écarté ni pourquoi. Trois de ses décisions ont d'ailleurs
changé en cours de route — son § 5.1 violait une contrainte d'unicité dès la
première ligne (les contraintes sont devenues `DEFERRABLE`), `element_parent`
a été retiré, et `EtatAncrage` réduit à deux valeurs. Ces écarts sont notés en
tête du fichier et au `CHANGELOG.md`.

La même discipline vaut pour la spec de synthèse, qui porte en tête **seize
addendums** datés : ce sont les décisions prises pendant l'implémentation et les
trous que les relectures ont révélés. On ne réécrit pas la spec pour lui donner
raison après coup ; on écrit à la suite ce qu'on a découvert.

| Chantier | État | Preuve |
|---|---|---|
| Moteur d'ancrage par élément | fait, migré, **non branché** à l'UI d'analyse (phases H-K non commencées) | `hypostasis_extractor/services/`, `CHANGELOG.md` |
| Rendu par éléments | écrit et testé, **appelé nulle part** en production | `front/services/rendu_elements.py` |
| Ingestion Docling | faite | `hypostasis_extractor/services/ingestion_docling.py` |
| Couche corpus (N-N, catégories sur la relation) | faite et testée, phases A-H ; reste la phase I et le retrait de `Page.dossier` | `core/services/corpus.py`, `front/views_corpus.py`, migrations `core.0040-0045` |
| Synthèse carnet — socle (deux genres, `SourceLink` peuplé, écartées, couverture, gardes, applieur) | fait, phases A-F | `core/services/synthese.py`, `core/services/section_ops.py`, migrations `core.0046-0052` |
| Synthèse carnet — vérification (verbatim, juge NLI en lot, provenance des verdicts) | fait (phase G), déclencheur UI à faire | `core/services/verification.py`, migration `core.0052` |
| Synthèse carnet — interface (article, panneau de preuve, diff) | à faire (phases H-I) | `SPEC-synthese-carnet.md` § 13 |
| Bascule CSS (design de la maquette, à feature constante) | décidée, cahier des charges rédigé, non engagée | `PLAN/bascule-css-cahier-des-charges.md` |
| Sélection des preuves (regroupement, oppositions, tri par le débat) | spécifiée, non entamée | `SPEC-selection-des-preuves.md` |
| `SourceLink` | schéma complet **et écrit en production** | `core/models.py:1439`, `core/services/synthese.py` |
| Versionnage de page (`parent_page`) | dormant : schéma conservé, plus aucun écrivain | `front/tasks.py` |
| Embeddings / pgvector | absents ; PHASE-33 planifiée | `docker-compose.yml:50`, `pyproject.toml` |
| Backlog UX (P1 de l'audit du 8 août) | ouvert | `PLAN/audit-ux-ui-2026-08-08.md` |

---

## 7. Les maquettes comme étalon

`tmp/maquettes/` contient trois écrans navigables — `corpus.html` (le carnet :
facettes, wikis, synthèses dirigées, alignement), `selection-preuves.html` (le
regroupement, les oppositions, le panneau « pourquoi cette extraction est
là »), `maquette.html` (la note : lecture par éléments, sourcing, bascule de
carnet) — servis par un `index.html` qui les présente. Ce ne sont pas des
dessins : ce sont des programmes, et leur raison d'être est d'un autre ordre
que l'illustration.

**La règle du corpus unique.** Tout part de `donnees.js`, dont l'en-tête fixe
la discipline : les trois écrans affichaient chacun leur propre copie des
données — « trois copies, trois vérités », avec des offsets d'ancrage faux
dans 19 cas sur 20. Désormais, on n'écrit dans `donnees.js` que ce qu'un humain
ou un LLM produit vraiment — un texte, une citation, un commentaire — et
**tout le reste est dérivé** par des fonctions : offsets, comptes, écartées,
couverture, similarités. « Si un chiffre est tapé quelque part, c'est un
défaut. » Quatre choses restent moquées, et c'est assumé parce qu'elles ne
peuvent pas se déduire du reste : les textes (qui tiennent lieu de sortie de
Docling et de l'extracteur), les commentaires (la délibération humaine), les
positions 2D (la projection d'embeddings), la liste des oppositions (la
seconde passe LLM).

**37 contrôles Playwright.** `scripts/verifier_les_maquettes.py` pilote un
navigateur et vérifie 37 assertions. Les plus significatives ne vérifient pas
des nombres figés mais des **invariants** — c'est-à-dire exactement ce que le
futur back devra garantir :

- *écartées = périmètre − citées*, recalculé dans la page au moment du test ;
- la couverture est une vraie jointure (recomptée indépendamment) ;
- le garde-fou « une synthèse n'est jamais source » est **exercé** : le carnet
  contient des synthèses, la portée d'une nouvelle doit compter exactement les
  notes ordinaires ;
- une opération de section au titre introuvable est visiblement rejetée ;
- chaque citation se retrouve littéralement dans le texte de son élément
  (sinon l'ancrage affiché serait faux) ;
- tous les liens de preuve aboutissent — ouverts un par un, dans une seconde
  page, jusqu'au surlignage effectif du passage.

**Ce qui n'existe pas encore est marqué.** Les fonctionnalités cibles portent
une pastille « cible » avec leur justification en infobulle : le fil d'Ariane
(« remplace l'arbre de navigation, que le N-N rend impossible »), le lecteur
audio (« aucun lecteur n'existe dans le produit »), la progression WebSocket
(« ne pousse aujourd'hui que "terminé" »). La maquette ne laisse pas croire que
le produit fait ce qu'il ne fait pas — c'est la même exigence de transparence
que le § 3, appliquée à elle-même.

**Pourquoi « étalon ».** Quand le back sera branché, on rejouera les mêmes
contrôles contre le vrai moteur et on comparera les sorties. Les specs
elles-mêmes se placent sous cette autorité : *« toute divergence entre cette
spec et la maquette est un défaut de l'une des deux, à trancher avant de
coder »* (`SPEC-synthese-carnet.md`, en-tête). La maquette n'est pas une
promesse d'interface ; c'est un banc de test du comportement, écrit avant le
code qu'il testera.

Le mécanisme a commencé à jouer son rôle. L'écran carnet du 8 août a été
construit *contre* l'étalon, à partir d'un cahier des charges qui listait les
écarts et sept arbitrages entre la spec et la maquette
(`PLAN/corpus-phase-f-cahier-des-charges.md`) ; le filtre corpus « une synthèse
n'est pas une source » est exactement l'invariant que l'étalon exerçait ; et
cinq scénarios de bout en bout rejouent dans un vrai navigateur, sur le produit
réel, ce que la maquette montrait. La décision de bascule CSS (§ 6.2) est la
conséquence logique de cette autorité : si l'étalon fait foi sur le
comportement, il n'y a pas de raison qu'un CSS que personne ne défend fasse foi
sur la forme.

---

## Sources

**Dans le dépôt** : `SPEC-synthese-carnet.md` (et ses seize addendums),
`SPEC-corpus-base-carnet-note.md`, `SPEC-selection-des-preuves.md`,
`SPEC-ancrage-par-element-v2.md`, `PLAN/INSPIRATION_ATOMIC.md`,
`PLAN/README.md`, `PLAN/bascule-css-cahier-des-charges.md`,
`PLAN/corpus-phase-f-cahier-des-charges.md`,
`PLAN/audit-ux-ui-2026-08-08.md`, `CHANGELOG.md` (entrées des 5, 8 et 9 août
2026), `tmp/maquettes/` (dont `donnees.js`),
`scripts/verifier_les_maquettes.py`, `core/models.py`,
`core/services/` (`corpus.py`, `synthese.py`, `section_ops.py`),
`front/views_corpus.py`, `front/tasks.py`,
`hypostasis_extractor/models.py`, `hypostasis_extractor/services/`,
`front/services/rendu_elements.py`,
`core/management/commands/basculer_vers_le_moteur_element.py`.

**Notes de la mémoire Atomic (août 2026)** : « Sourcing et attribution dans les
systèmes RAG — état de l'art 2026 » (benchmarks cités : ALCE, LongBench-Cite,
CiteControl, FACTS ; outils : RAGAS, MiniCheck, Vertex AI check-grounding,
Anthropic Citations API ; standards : W3C Web Annotation, Media Fragments
URI) ; « Praxis (En commun / Projet collectif) — plateforme de gestion de
corpus à trois niveaux » ; « Hypostasia V3 — couche corpus et refonte de la
navigation » ; « Atomic — base de connaissances personnelle local-first » ;
« Trois moteurs RAG open source décortiqués ».
