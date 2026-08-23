# Dériver un préambule par carnet — optionnel, à décider sur mesure

**Discuté le 23 août 2026. Volontairement placé en dernier de la série, et
volontairement non décidé.**

## D'où vient l'idée

La proposition initiale du mainteneur était que **chaque utilisateur** puisse dériver
ses prompts en copie privée. Abandonné le 23 août, pour trois raisons :

1. **La nuit n'a pas d'utilisateur.** `mettre_a_jour_un_wiki_la_nuit_task` tourne avec
   `fait_par=None` — c'est même le seul signe qu'aucun humain n'a rien décidé. Quel
   prompt prendrait-elle ? Celui du propriétaire de l'article ? Du carnet ? Le
   défaut ? Deux de ces réponses font que le collectif reçoit chaque matin un article
   réécrit selon le goût d'une personne qui n'a rien demandé cette nuit-là.
2. **L'objet est collectif.** Un wiki appartient à un carnet ; ses destinataires sont
   le propriétaire de l'article, ceux des carnets qui le portent, **et les partages**
   (`core/services/destinataires_de_wiki.py`). Un prompt personnel sur un objet
   collectif produit des articles dont plus personne ne peut dire d'où ils viennent —
   dans un outil de délibération sourcée, c'est l'inverse du but.
3. **Ça contredit « benchmarkable »** : N types × M utilisateurs, ce sont N×M prompts
   en circulation dont aucun n'a d'étalon.

**Retenu** : si dérivation il y a, c'est **par carnet** — l'unité de gouvernance du
projet. Une équipe qui répond à un appel à projet ajuste la consigne de *son* carnet,
pas la sienne propre.

## Pourquoi cette note est en dernier, et pourquoi elle peut ne jamais être codée

Depuis que la **direction** vit sur l'article
(`2026-08-23-la-direction-d-un-article-se-perd-a-la-mise-a-jour.md` : un sujet et une
consigne de forme par wiki), le besoin de dériver le **préambule** s'affaiblit
beaucoup. Le préambule dit le métier — « tu es un rédacteur en synthèse délibérative,
un statut NOUVEAU n'est pas un consensus » — et ce métier ne varie pas d'un carnet à
l'autre.

**La décision doit donc se prendre sur mesure, pas sur intuition** : quand la trace de
provenance existera (`2026-08-23-la-provenance-d-un-prompt-n-est-ecrite-nulle-part.md`),
on saura si deux carnets veulent vraiment deux préambules — ou si ce qu'ils voulaient
était une direction, qu'ils ont désormais.

## Ce qu'il faudrait résoudre, le jour où on le fait

1. **La surface de sécurité change.** L'édition des prompts est aujourd'hui
   **staff-only** (`_exiger_staff`, PHASE-26b : « bibliothèque d'analyseurs
   admin-only »). Ouvrir la dérivation aux membres d'un carnet, c'est laisser
   quelqu'un écrire du texte **exécuté par le rédacteur** sur un article lu par tous
   les partages du carnet. Qui dérive : le propriétaire ? les partages en écriture ?
   les groupes ? Ce n'est pas un réglage, c'est une décision.
2. **Le passage du carnet partout.** `_prompt_systeme_de_synthese()` est appelée
   **sans aucun argument** en trois sites de production, un banc et un test. La
   dérivation exige de lui passer un carnet à chaque appel — y compris depuis la
   nuit, qui en a bien un (`wiki.dossier`).
3. **La dérive silencieuse.** `bin/install.sh` tourne à chaque démarrage de conteneur
   et ne regarnit un analyseur que s'il n'a **aucune** pièce — précisément pour ne pas
   écraser un travail d'auteur. Une copie de carnet **gèle** donc : le jour où le
   préambule par défaut évolue, elle ne bouge pas, et six mois plus tard la moitié des
   carnets tournent sur une consigne périmée sans le savoir. Il faut au minimum un
   « votre version dérive du défaut, modifié le … ». À noter : **ce gel existe déjà
   au niveau 0** — une évolution du prompt par défaut dans le code ne se propage
   jamais à une base déjà installée.
4. **La matrice de bancs.** Trois types × N carnets dérivés : décider ce qu'on mesure,
   et ce qu'on refuse de mesurer.

## Ce qu'il faut mesurer, avant même de décider

- **La question préalable est factuelle** : combien de carnets ont réellement voulu un
  préambule différent ? La trace de provenance y répondra. Tant qu'elle n'existe pas,
  toute réponse est une opinion.
- **Fixtures étalons à écrire** : deux carnets étalons de nature franchement
  différente — un corpus de délibération, un corpus documentaire — pour éprouver si
  un même préambule les sert aussi bien.
- **Un banc LLM réel** (`make test-llm`, tag `llm_reel`, **facturé**) : le même carnet,
  le préambule par défaut contre un préambule dérivé, mesuré sur les métriques déjà
  employées par `benchmarks/redaction/`. Si l'écart reste sous les **11 points
  d'amplitude intra-modèle** mesurés au `PASSATION` § 6, il ne conclut rien — et la
  dérivation ne se justifie alors que par le confort, ce qu'il faudra dire.

## Ce qui casse si on ne fait rien

Rien. C'est la seule note de la série dont l'absence ne casse et n'empêche rien : les
carnets partagent un préambule, et chacun dirige ses articles par leurs champs
propres. Elle est écrite pour que la question ne se reperde pas, et pour qu'on la
tranche avec un chiffre plutôt qu'une impression.
