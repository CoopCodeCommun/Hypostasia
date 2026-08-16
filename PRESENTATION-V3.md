# Hypostasia V3 — ce que devient le projet, et pourquoi

**Date** : 9 août 2026, au soir (première rédaction le 8 août ; mis à jour après
les couches corpus A-H et synthèse A-F).
**Lecteur visé** : quelqu'un qui connaît Hypostasia mais pas les décisions de
conception de ces dernières semaines — un contributeur qui arrive, un partenaire,
ou le développeur qui reprendra ce code dans six mois.

Ce document explique et justifie. Il ne remplace ni les spécifications
(`SPEC-synthese-carnet.md`, `SPEC-selection-des-preuves.md`), ni le plan de
refonte (`PLAN/INSPIRATION_ATOMIC.md`), ni les maquettes (`front/static/front/maquettes/`) :
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
`parent_page` n'a plus aucun écrivain en production.

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

| Couche | Objet |
|---|---|
| **Ancrage par élément** | où, exactement, dans quel texte |
| **Corpus** : base → carnet → note | qui range quoi, avec quel vocabulaire |
| **Synthèse au niveau du carnet** | ce qu'on affirme, sur quelles preuves |

> Ce tableau portait une colonne « État » jusqu'au 16 août 2026. Elle disait de
> l'ancrage qu'il était « **pas encore branché** au parcours utilisateur » —
> faux depuis le branchement BR-A→F du 10 août — et de la synthèse que son
> « interface était à faire », alors que ses écrans étaient livrés le 9. Elle a
> été retirée plutôt que corrigée : ce document explique **pourquoi** les
> couches sont ce qu'elles sont, et cette question-là ne périme pas. L'état, lui,
> se lit dans `CHANGELOG/` et `PLAN/PASSATION.md`.

### 2.1 L'ancrage par élément — le socle

L'ancien moteur ancrait une extraction par deux offsets dans le texte plat de
la page. Défaut structurel : « un décalage n'est pas une adresse, c'est une
distance depuis un point qui bouge » — corriger une coquille en haut de page
faussait toutes les ancres du dessous.

Le moteur ELEMENT ancre dans l'**élément de document** : un paragraphe, un titre,
un item de liste, un tableau, un tour de parole, chacun identifié par un UUID qui
ne change jamais (`ElementDocument`, `core/models.py:1752`). Une extraction porte
une ou plusieurs **portions**, chacune bornée à l'intérieur d'un élément
(`AncrageExtraction`, `hypostasis_extractor/models.py:670`). La table de liaison
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
  jamais écrire d'ancres calculées sur un texte qui n'existe plus ;
- `ingestion_docling.py` — l'entrée de toute la chaîne : un fichier devient N
  `ElementDocument`, chacun avec son label, son chemin de section et sa
  provenance physique (`{page_no, boites}` pour un PDF, une **liste** de boîtes
  car un paragraphe peut être à cheval sur deux colonnes ou deux pages).

**Un PDF scanné est lu comme un PDF natif** (mesuré le 14 août 2026). Docling
embarque `RapidOCR` et n'OCRise que les *zones* dépourvues de couche texte
(`force_full_page_ocr=False`) : la même étude, rastérisée en images, ressort avec
**11 éléments, mêmes labels, mêmes pages, mêmes boîtes** que sa version native.
Neuf des onze sont restitués au-dessus de 0,90 de similarité, tableaux compris.
Le coût est le temps : 3,7 s par page en régime établi, environ dix fois plus
quand l'OCR entre en jeu, sur une file Celery dédiée à concurrence 1.

Deux conséquences à retenir. D'abord cette capacité n'est **déclarée nulle part** :
`rapidocr` arrive en dépendance transitive de `docling-slim`, absent de
`pyproject.toml` — si l'amont la bascule en extra optionnel, l'OCR disparaît en
silence. Ensuite, un scan produit une page aux dimensions de son image (935×1210
pour un scan 110 dpi, contre 612×792 pt en natif) : le calque de surlignage du
visualiseur PDF doit se calculer **relativement à `page.size`**, jamais en points
absolus.

Côté affichage, `front/services/rendu_elements.py` est écrit et testé : il
remplace l'injection de balises par offsets par un découpage du texte de chaque
élément en segments aux bornes des portions, ce qui rend enfin représentables
les extractions en plusieurs portions et les chevauchements — 3 898 paires
d'extractions se chevauchent en base, ce n'est pas un cas d'école. Il est **appelé en production** depuis le
branchement du 10 août : `front/views.py:4246` et le tag de gabarit
`front/templatetags/rendu_moteur.py:37` s'en servent pour rendre la lecture.

> Ce paragraphe affirmait le contraire — « aucun code de production ne
> l'appelle » — jusqu'au 16 août 2026. C'était vrai le 9, faux le 10.

### 2.2 Le corpus — base → carnet → note

**Implémentée** (voir § 5 pour le modèle ; l'état exact est dans `CHANGELOG/`). Deux
relations N-N portées par des tables de liaison (`AppartenancePageDossier`,
`AppartenanceDossierBase`) qui portent elles-mêmes les catégories, l'épinglage
et l'ordre manuel — modèles, migrations, permissions, endpoints et écrans
carnet / note / bases sont en place.

### 2.3 La synthèse au niveau du carnet

La synthèse est devenue une note typée du
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
L'étage au-dessus — le prompt qui produit ces opérations et l'écran qui montre
le diff — a été livré avec les phases G à I les 9 et 10 août.

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

Découverte structurante de la spec corpus : la navigation était un arbre
(`arbre_dossiers.html`, retiré depuis le 12 août 2026 avec le menu burger), et
**un arbre suppose un parent unique**. Sous le N-N,
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
déjà là, sous une autre forme. Et le reste a suivi : l'arbre de navigation a été **retiré** le 12 août avec le
menu burger, et le fil d'Ariane à bascule `Base › Carnet ▾ › Note` **existe** —
`front/templates/front/corpus/_fil_ariane.html`, chevron et menu de bascule
compris. Le principe énoncé ici a donc été appliqué jusqu'au bout.

> Ce paragraphe décrivait encore la cohabitation des deux navigations jusqu'au
> 16 août 2026, vingt lignes après avoir lui-même daté le retrait de l'arbre.

---

## 6. Où en est le code

**Cette section ne tient pas l'état d'avancement, et c'est délibéré.** Elle l'a
tenu jusqu'au 16 août 2026, et elle a fini par mentir : elle affirmait encore que
le moteur d'ancrage « n'est branché à aucune tâche Celery ni aucune vue » et que
« les phases H à K ne sont pas commencées », alors que le branchement BR-A→F
était livré depuis le 10 août. Un document qui explique **pourquoi** les choses
sont comme elles sont n'a pas le même rythme qu'un état des lieux, qui périme en
quinze jours. Les tenir dans le même fichier condamnait l'un des deux.

L'état réel se lit à trois endroits, et eux sont tenus à jour :

| Ce qu'on cherche | Où |
|---|---|
| Le statut de chaque domaine | l'en-tête de la `SPEC-*.md` concernée |
| La carte du dépôt et les invariants | `AGENTS.md` |
| Ce qui a changé, quand, et comment le vérifier à la main | `CHANGELOG/` |
| Les chantiers ouverts, les décisions en attente, l'environnement | `PLAN/PASSATION.md` |

Ce qui reste vrai ici, et qui ne périme pas : les décisions expliquées aux § 1
à § 5 — pourquoi le contenant a changé de nature, pourquoi la synthèse est
devenue une note du carnet, pourquoi la citation est un objet vérifié — et la
doctrine de l'étalon au § 7.

---

## 7. Les maquettes comme étalon

`front/static/front/maquettes/` contient trois écrans navigables — `corpus.html` (le carnet :
facettes, wikis, synthèses dirigées, alignement), `selection-preuves.html` (le
regroupement, les oppositions, le panneau « pourquoi cette extraction est
là »), `maquette.html` (la note : lecture par éléments, sourcing, bascule de
carnet). Ce ne sont pas des
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
audio, la progression WebSocket (« ne pousse aujourd'hui que "terminé" »). La
maquette ne laisse pas croire que le produit fait ce qu'il ne fait pas — c'est
la même exigence de transparence que le § 3, appliquée à elle-même.

Et le marquage se **retire** quand la cible est atteinte : l'en-tête de
`maquette.html` porte les sept écarts avec leur état réel, et celui du lecteur
audio est estampillé « RÉSOLU le 13 août ». Un tableau de cibles qu'on ne
dépointe pas redevient une carte périmée — une session est déjà repartie sur
l'une d'elles.

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
(`PLAN/archive/cahiers-des-charges/corpus-phase-f-cahier-des-charges.md`) ; le filtre corpus « une synthèse
n'est pas une source » est exactement l'invariant que l'étalon exerçait ; et
cinq scénarios de bout en bout rejouent dans un vrai navigateur, sur le produit
réel, ce que la maquette montrait. La décision de bascule CSS est la
conséquence logique de cette autorité : si l'étalon fait foi sur le
comportement, il n'y a pas de raison qu'un CSS que personne ne défend fasse foi
sur la forme.

---

## 8. Les 30 hypostases — la géométrie des débats

> Cet exposé vivait dans le `README.md`, où il occupait un quart du fichier. Il
> est ici depuis le 16 août 2026 : un README sert à installer et lancer, ce
> document-ci sert à comprendre. Le README en garde le résumé et renvoie ici.

Une **hypostase** est une maniere d'etre discutable. C'est le concept fondateur du projet — d'ou son nom.

*A **hypostasis** is a way of being debatable. It is the founding concept of the project — hence its name.*

### Pourquoi exactement 30

Le nombre n'est pas arbitraire : il se deduit.

Une idee peut etre mise a l'epreuve de **2 manieres** (les dispositifs de preuve) selon **3 modes de raisonnement** :

| Dispositif de preuve | Mode de raisonnement |
|---|---|
| formel, empirique | induction, abduction, deduction |

**2 × 3 = 6 modes de mise a l'epreuve.**

Chaque hypostase se definit alors par un couple :

1. **ce qui ne peut pas la refuter** — 6 choix ;
2. **ce qui ne peut pas la prouver** — 5 choix restants.

Le second ne peut pas etre egal au premier : un meme mode ne peut pas a la fois echouer a refuter et echouer a prouver la meme idee sans la vider de son sens.

**6 × 5 = 30 hypostases**, chacune occupant une case unique.

*The count is derived, not arbitrary: 2 proof devices x 3 reasoning modes = 6 modes; each hypostasis is a pair (what cannot refute it, what cannot prove it), the two being distinct — 6 x 5 = 30.*

### La matrice complete

Chaque case hors diagonale contient exactement une hypostase. La diagonale est vide par construction.

| non refutee par ↓ \ non prouvee par → | induction emp. | induction form. | abduction emp. | abduction form. | deduction emp. | deduction form. |
|---|---|---|---|---|---|---|
| **induction empirique** | — | formalisme | classification | paradoxe | aporie | approximation |
| **deduction empirique** | mode | croyance | variation | dimension | — | événement |
| **induction formelle** | axiome | — | valeur | structure | conjecture | invariant |
| **deduction formelle** | loi | principe | paradigme | objet | domaine | — |
| **abduction empirique** | variance | donnée | — | variable | indice | phénomène |
| **abduction formelle** | hypothèse | théorie | définition | — | problème | méthode |

La matrice se lit aussi par paires symetriques : `valeur` ↔ `donnée`, `conjecture` ↔ `croyance`, `structure` ↔ `théorie`, `principe` ↔ `invariant`... Les 15 paires sont completes.

### Les 6 familles epistemiques

Une **famille** regroupe les 5 hypostases qui partagent le meme « ce qui ne peut pas les refuter ».

*A **family** groups the 5 hypostases sharing the same "what cannot refute them".*

#### Famille 1 — non refutee par induction empirique

*Ce qu'on observe sans pouvoir generaliser.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **classification** | distribuer en classes, en catégories | abduction empirique |
| **aporie** | difficulté d'ordre rationnel apparemment sans issue | déduction empirique |
| **approximation** | calcul approché d'une grandeur réelle | déduction formelle |
| **paradoxe** | proposition à la fois vraie et fausse | abduction formelle |
| **formalisme** | considération de la forme d'un raisonnement | induction formelle |

#### Famille 2 — non refutee par deduction empirique

*Ce qui se produit sans cadre formel.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **événement** | ce qui arrive | déduction formelle |
| **variation** | changement d'un état dans un autre | abduction empirique |
| **dimension** | grandeur mesurable qui détermine des positions | abduction formelle |
| **mode** | manière d'être d'un système | induction empirique |
| **croyance** | certitude ou conviction qui fait croire une chose vraie ou possible | induction formelle |

#### Famille 3 — non refutee par induction formelle

*Ce qu'on formalise sans pouvoir verifier.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **invariant** | grandeur, relation ou propriété conservée lors d'une transformation | déduction formelle |
| **valeur** | mesure d'une grandeur variable | abduction empirique |
| **structure** | organisation des parties d'un système | abduction formelle |
| **axiome** | proposition admise au départ d'une théorie | induction empirique |
| **conjecture** | opinion ou proposition non vérifiée | déduction empirique |

#### Famille 4 — non refutee par deduction formelle

*Ce qu'on deduit formellement.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **paradigme** | modèle ou exemple | abduction empirique |
| **objet** | ce sur quoi porte le discours, la pensée, la connaissance | abduction formelle |
| **principe** | cause a priori d'une connaissance | induction formelle |
| **domaine** | champ discerné par des limites, bornes, frontières | déduction empirique |
| **loi** | corrélation | induction empirique |

#### Famille 5 — non refutee par abduction empirique

*Ce qu'on constate sans pouvoir l'expliquer.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **phénomène** | ce qui se manifeste à la connaissance via les sens | déduction formelle |
| **variable** | ce qui prend différentes valeurs, dont dépend l'état d'un système | abduction formelle |
| **variance** | dispersion d'une distribution ou d'un échantillon | induction empirique |
| **indice** | indicateur numérique ou littéral qui sert à distinguer ou classer | déduction empirique |
| **donnée** | ce qui est admis, donné, qui sert à découvrir ou à raisonner | induction formelle |

#### Famille 6 — non refutee par abduction formelle

*Ce qu'on propose sans pouvoir le confirmer.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **méthode** | procédure qui indique ce que l'on doit faire ou comment le faire | déduction formelle |
| **définition** | détermination, caractérisation du contenu d'un concept | abduction empirique |
| **hypothèse** | explication ou possibilité d'un événement | induction empirique |
| **problème** | difficulté à résoudre | déduction empirique |
| **théorie** | construction intellectuelle explicative, hypothétique et synthétique | induction formelle |

### Ou vit ce referentiel dans le code

Les 30 hypostases sont ecrites a **quatre endroits**, qui doivent rester d'accord :

| Emplacement | Role |
|---|---|
| `core/models.py` → `HypostasisChoices` | la taxonomie du modele |
| `front/services/fixtures_analyseurs.py` | le referentiel enseigne au LLM (le tableau ci-dessus) |
| `front/services/fixtures_analyseurs.py` | les 30 exemples few-shot, un par hypostase |
| `front/normalisation.py` → `HYPOSTASES_CONNUES` | **le filtre** : toute hypostase inconnue est supprimee |

`hypostasis_extractor/tests/test_referentiel_des_hypostases.py` verifie que les quatre concordent et que les 6 familles respectent le motif. Toute evolution du referentiel doit donc toucher les quatre ensemble.

> **Correction du 14 aout 2026.** La famille 4 violait le motif depuis l'origine : `principe` et `loi` occupaient la meme case, `domaine` occupait une case diagonale (interdite), et deux cases restaient vides. Le referentiel ne comptait donc reellement que 28 manieres d'etre discutable. `principe` est passe a *induction formelle* et `domaine` a *deduction empirique* ; `loi` n'a pas bouge. Les 30 cases sont desormais toutes occupees, une seule fois chacune.

---


---

## Sources

**Dans le dépôt** : `SPEC-synthese-carnet.md` (et ses seize addendums),
`SPEC-corpus-base-carnet-note.md`, `SPEC-selection-des-preuves.md`,
`SPEC-ancrage-par-element-v2.md`, `PLAN/INSPIRATION_ATOMIC.md`,
`PLAN/README.md`,
`PLAN/archive/cahiers-des-charges/` (bascule CSS, écran carnet),
`PLAN/archive/mesures-et-recettes/audit-ux-ui-2026-08-08.md`, `CHANGELOG/` (entrées des 5, 8 et 9 août
2026), `front/static/front/maquettes/` (dont `donnees.js`),
`scripts/verifier_les_maquettes.py`, `core/models.py`,
`core/services/` (`corpus.py`, `synthese.py`, `section_ops.py`),
`front/views_corpus.py`, `front/tasks.py`,
`hypostasis_extractor/models.py`, `hypostasis_extractor/services/`,
`front/services/rendu_elements.py`.

> `core/management/commands/basculer_vers_le_moteur_element.py`, citée par une
> version antérieure de ce document, a été **supprimée** avec l'ancien moteur le
> 10 août 2026 (R3). Son travail — la bascule des 538 pages — est fait, et le
> récit en est conservé dans
> `CHANGELOG/2026-08-10-r1-reconversion-du-moteur-element.md`.

**Notes de la mémoire Atomic (août 2026)** : « Sourcing et attribution dans les
systèmes RAG — état de l'art 2026 » (benchmarks cités : ALCE, LongBench-Cite,
CiteControl, FACTS ; outils : RAGAS, MiniCheck, Vertex AI check-grounding,
Anthropic Citations API ; standards : W3C Web Annotation, Media Fragments
URI) ; « Praxis (En commun / Projet collectif) — plateforme de gestion de
corpus à trois niveaux » ; « Hypostasia V3 — couche corpus et refonte de la
navigation » ; « Atomic — base de connaissances personnelle local-first » ;
« Trois moteurs RAG open source décortiqués ».
