# La direction d'un article se perd à la mise à jour

**Décidé par le mainteneur le 23 août 2026. Rien n'est codé.**
**À trancher APRÈS `2026-08-22-borner-la-reecriture-nocturne-d-un-wiki.md`** — voir
« ce que ça déplace » en bas.

## Ce que le code fait aujourd'hui

| Moment | Ce que le rédacteur reçoit |
|---|---|
| création d'un wiki | `=== SUJET DE L'ARTICLE ===\n{wiki.sujet}` + « le sujet oriente la rédaction ; il ne t'autorise pas à inventer » |
| création d'une synthèse dirigée | `=== TITRE DEMANDÉ ===\n{page.title}` (+ `=== DIRECTION ===` si une catégorie est choisie) |
| **mise à jour d'un wiki — manuelle comme nocturne** | **ni sujet, ni titre** |

Vérifié deux fois le 23 août : `grep "sujet" front/tasks.py` rend **3 occurrences,
toutes dans `produire_un_wiki_task`** ; et le prompt de
`construire_la_proposition_d_operations` (l. 2243) n'assemble que l'article actuel,
la liste des titres adressables, les extractions écartées, la consigne et le format
JSON.

**Le corps de l'article ne rattrape pas l'oubli** : le contrat de forme interdit le
`#` de niveau 1. Mesuré sur les cinq wikis de la base de dev : **les cinq commencent
par `## `**, aucun ne porte son sujet. Exemple — sujet « Les open badges et la
reconnaissance des… », première ligne du corps « ## Origines et objectifs des Open
Badges ».

La consigne de rédaction posée à la création **s'évapore donc au premier tour de mise
à jour**. Chaque nuit, le rédacteur voit un article sans direction et des extractions
à caser : il complète, il ne poursuit pas une intention.

## Ce qui est voulu — deux champs, sur l'objet

L'architecture a trois étages, et la direction est celui du milieu :

| étage | quoi | où il vit | partagé par |
|---|---|---|---|
| le métier | « tu es un rédacteur en synthèse délibérative… » | l'analyseur, en base, versionné | tous les articles |
| **l'intention** | **« le sujet est X », « suis ce plan »** | **l'objet : `Wiki`, `SyntheseDirigee`** | **un seul article** |
| le contrat | `##`, `[[ext:N]]`, `CITATIONS_USED`, le JSON | en dur, dans le code | tout, sans exception |

**Deux champs, et non un seul.** `Wiki.sujet` n'est pas qu'une consigne : **c'est le
titre affiché**. `front/templates/front/corpus/liste_wikis.html:31` le rend en
`class="titre-note"`, et le récapitulatif du matin l'imprime trois fois
(`recapitulatif_du_matin.txt:37,56,73` et `.html:31,119`), dont une en
`truncatechars:80`. Un plan de quarante lignes dans ce champ casserait la liste des
wikis **et** le mail de tout le monde.

Donc : `sujet` reste court (de quoi ça parle, et ça titre), et un second champ porte
la forme — un `TextField`, nom à trancher (voir ci-dessous). Deux blocs distincts
dans le prompt :

```
=== SUJET DE L'ARTICLE ===        ← ce dont l'article parle
=== PLAN À SUIVRE ===             ← les questions / le squelette à épouser
```

**Les deux sont rejoués à la mise à jour**, manuelle comme nocturne.

`SyntheseDirigee` n'a **aucun** champ de sujet (le prompt utilise `page.title`) : il
lui faut le champ de forme aussi. Comme elle est figée, la question du rejeu ne la
concerne pas — un seul passage, à la création.

## Ce que ça remplace : la FK vers un document directeur

Une première version prévoyait `Wiki.note_directrice = FK(Page)` : un document du
carnet, lu en entier et exclu du corpus citable. **Abandonné le 23 août**, et voici
pourquoi — chacun de ces points a été vérifié :

- **le compteur des écartées aurait menti.** `extractions_ecartees` est une différence
  dont **les deux membres** dérivent du même périmètre : exclure une note la retire
  des deux côtés. Sur le carnet « Thales » (2 notes, 397 extractions), faire de la
  note 19 (285 extractions) la directrice du wiki 3 aurait fait passer l'en-tête de
  « 350 non reprises » à « ~65 » — **ce qui se lit comme un progrès alors que rien
  n'a été repris** — et fait disparaître le groupe du document du panneau § 8, sans
  un mot. L'écran de couverture § 9 ne rattrape pas : il n'est pas rendu pour un wiki ;
- **rien n'aurait relancé le wiki quand le document change.**
  `nouveautes_du_perimetre` ne compte que les extractions et commentaires **des notes
  du périmètre**. Modifier l'appel à projet, le ré-ingérer, y ajouter des questions —
  aucun de ces gestes n'aurait réveillé l'article. **Le « lien vivant » que la FK
  semblait acheter n'existait pas** ;
- **le `on_delete` n'avait pas de bonne réponse** : `SET_NULL` laisse le wiki réécrit
  sans son squelette dès la nuit suivante, sans erreur ; `CASCADE` détruit le wiki
  avec la note ; `PROTECT` (le seul cohérent avec `AncrageExtraction.element`) exige
  un geste de détachement à écrire ;
- **la taille.** Un PDF de 40 pages fait 80 000 à 120 000 caractères. Ajouté à un
  prompt de mise à jour déjà à 68 700 c sur le wiki 3, on atteignait ~150 000 c
  ≈ 37 000 tokens, **par wiki et par nuit**.

**Ce qu'on perd** : il faut recopier les questions à la main. C'est du travail — et
c'est aussi un geste de clarification : on choisit les quinze questions qui comptent
au lieu d'envoyer quarante pages chaque nuit.

## Ce qui reste à trancher

1. **Le nom du champ.** « Direction » est **déjà pris trois fois** :
   `SyntheseDirigee`, `categorie_de_direction`, et le bloc `=== DIRECTION ===` du
   prompt. Et « suivre » a déjà le sens d'abonnement — la docstring de `Wiki` dit
   « un wiki ne s'adopte pas, il **se suit** ». C'est exactement le piège « phase »
   que `AGENTS.md` documente. Candidats : `consigne_de_forme`, `plan_a_suivre`,
   `squelette`.
2. **Le document reste dans le corpus citable.** L'appel à projet déposé dans le
   carnet reste une note ordinaire : l'article pourra sourcer des affirmations sur
   lui. Ce n'est pas faux, et c'est **visible** — une citation se voit. Le remède
   propre est `categories_du_perimetre`, aujourd'hui inatteignable à l'écran : voir
   `2026-08-23-le-perimetre-par-categories-est-inatteignable.md`.
3. **Faut-il rejouer le sujet aussi à la création d'une synthèse dirigée ?** Elle n'a
   pas de champ sujet du tout : soit on lui en donne un, soit `page.title` continue
   d'en tenir lieu.

## Ce que ça déplace

Rappeler le plan voulu **pousse mécaniquement le modèle vers `replace_section`** au
lieu d'`append_to_section`. C'est l'effet recherché pour la qualité — et chaque
paragraphe remplacé **perd sa paire (extraction, paragraphe)**, donc son verdict et
ses quatre avis locaux (`core/services/synthese.py:645-720`).

D'où l'ordre : **la borne nocturne d'abord, cette note ensuite.**

## Ce qu'il faut mesurer

- **Fixtures étalons à écrire** : un carnet étalon portant un vrai gabarit — un appel
  à projet avec ses questions, une charte avec son plan — et l'article attendu. C'est
  le seul moyen de dire si « le plan a été suivi », qui n'est pas une métrique
  automatique évidente : elle demande sans doute un juge, donc un protocole écrit.
- **Un banc LLM réel** (`make test-llm`, tag `llm_reel`, **facturé**) : le même wiki,
  N tours de mise à jour, avec et sans la direction rejouée. Trois mesures — la part
  de sections du plan effectivement couvertes, le nombre de `replace_section`
  proposés, et le nombre de verdicts perdus au tour.
- **Bonne nouvelle mesurée** : le banc des rédacteurs
  (`benchmarks/redaction/lancer_les_passes.py`) mesure `produire_un_wiki_task`, qui
  **porte déjà le sujet**. Rejouer le sujet à la mise à jour n'invalide donc **aucune**
  mesure existante.
- **Le bruit** : 11 points d'amplitude intra-modèle (`PASSATION` § 6). Répéter.

## Ce qui casse si on ne fait rien

Rien ne casse. Simplement, les deux cas d'usage qui ont motivé toute cette série sont
impossibles : répondre à un appel à projet et le tenir à jour, produire une charte
sur le modèle d'une autre. À la création, ça marcherait une fois ; dès la première
nuit, l'article perdrait son plan et redeviendrait un wiki ordinaire.

## Coût de mise en œuvre

Deux champs texte, une migration, deux blocs de prompt, le rejeu dans
`construire_la_proposition_d_operations`, un `<textarea>` dans deux formulaires, et
les tests. Une à deux journées — plus le banc, qui est le vrai travail.
