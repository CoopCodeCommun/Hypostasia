# Typer les analyseurs par action — trois types, pas deux

**Décidé par le mainteneur le 23 août 2026. Rien n'est codé.**

---

## ⚠️ ADDENDUM DU 1er SEPTEMBRE 2026 — deux prescriptions de cette note sont fausses, et une décision manque

> Cet encart fait foi sur les trois points qu'il traite. Le corps de la note
> reste juste partout ailleurs. Les faits ci-dessous ont été vérifiés dans le
> code du 1er septembre 2026, et relus par une seconde lecture adverse.

### 1. « BASCULER l'analyseur existant » casserait la synthèse d'une note

La note écrit : « IL FAUT UNE MIGRATION DE DONNÉES qui BASCULE l'analyseur
existant, jamais qui en crée un à côté. »

Or « Synthèse délibérative » sert **deux métiers**, pas un :

- la **rédaction d'article**, par `_prompt_systeme_de_synthese()`
  (`front/tasks.py`), dont les quatre appelants sont les trois assembleurs
  d'article et le banc de la chaîne complète ;
- la **synthèse d'une note**, par trois vues qui résolvent
  `type_analyseur="synthetiser"` : `previsualiser_synthese`
  (`front/views.py:2857, 2861, 2876`), `synthetiser` (`:3143, 3149`) et
  `drawer_contenu` (`:5816`).

Le basculer laisserait ces trois vues sans aucun analyseur : **HTTP 400** et le
toast « Aucun analyseur de synthèse actif ». Pire, le toast de `synthetiser`
promet que `docker compose down -v && make install` répare — ce serait **faux** :
`creer_les_modeles_ia_et_les_analyseurs()` fait `get_or_create(name="Synthèse
délibérative")`, retrouverait l'analyseur **basculé par son nom**, et ne
recréerait jamais de `synthetiser`. La casse serait permanente et le remède
affiché mentirait.

⇒ **La migration doit COPIER**, pas basculer : « Synthèse délibérative » reste en
`synthetiser`, et un analyseur `rediger_un_article` naît avec une **copie de ses
pièces actuelles** — donc le texte du mainteneur s'il l'a édité, jamais celui des
fixtures. L'intention de la note est préservée (le prompt personnalisé ne devient
pas orphelin : il part dans les deux), sans casser un geste existant.

**Et la migration seule ne suffit pas.** `bin/install.sh` migre **avant** de poser
les fixtures : sur un clone neuf, « Synthèse délibérative » n'existe pas encore
au moment du `migrate`, donc la copie ne copierait rien. Il faut **aussi** un
troisième `get_or_create` dans `fixtures_analyseurs.py`, et le nom de la copie
doit être **exactement** la constante des fixtures — sinon le démarrage suivant
crée un **second** `rediger_un_article` garni du texte par défaut qui, s'il naît
`est_par_defaut=True`, **décoche celui du mainteneur**. C'est le piège que la
note décrit, reconstitué un cran plus bas. À épingler par un test qui compare le
nom de la migration à celui des fixtures.

### 2. « Onze querysets » : exact, mais dix d'entre eux ne bougent pas

Le compte est aujourd'hui de **douze** (le chantier de la provenance en a ajouté
un). **Deux seulement changent de valeur** :

| Emplacement | Destin |
|---|---|
| `front/tasks.py:1145` (`_prompt_systeme_de_synthese`) | → `rediger_un_article` |
| `hypostasis_extractor/services/provenance.py:79` (`analyseur_de_redaction`) | → `rediger_un_article`, **en verrou avec le précédent** : deux règles divergentes feraient nommer à la provenance un autre analyseur que celui qui a servi |

Les huit autres `synthetiser` servent la **synthèse d'une note** et restent ;
`migrations/0035` est figée et ne se touche pas.

### 3. LE « puis carnet » DU RÉGIME DE REPLI N'A AUCUN ÉCRIVAIN — décision demandée

La note demande d'écrire l'ordre de résolution « geste (`?analyseur_id=`), puis
carnet, puis défaut ». **Deux de ces trois niveaux n'existent pas** :

- **carnet** : il n'y a aucune clé étrangère `Dossier → AnalyseurSyntaxique`,
  nulle part. Le seul champ carnet-niveau approchant est
  `Dossier.guide_de_redaction` (`core/models.py:98`) — un texte **montré aux
  humains** dans l'écran du carnet, injecté dans **aucun** prompt ;
- **geste** : aucun des trois chemins d'article ne porte d'`analyseur_id` — la
  note le dit elle-même (« les trois autres n'ont aucun paramètre »).

Coder ces deux niveaux fabriquerait du code mort, c'est-à-dire exactement la
faute que la note sur la provenance existe pour empêcher.

⇒ **Le régime posé est donc, pour `rediger_un_article` : défaut du type, puis
repli en dur JOURNALISÉ.** Si le niveau « carnet » est voulu, il demande un
champ, un écran et un écrivain — **c'est un chantier à part, à décider par le
mainteneur**, pas une ligne de ce chantier-ci.

---

## Ce que le code fait aujourd'hui

`AnalyseurSyntaxique.TypeAnalyseur` (`hypostasis_extractor/models.py:289`) ne connaît
que **deux** valeurs : `ANALYSER` et `SYNTHETISER`.

Conséquence : **quatre appels LLM différents partagent le même préambule**, à la
lettre près. `_prompt_systeme_de_synthese()` (`front/tasks.py:1112`) prend le premier
analyseur actif de type `synthetiser`, trié `-est_par_defaut, name`, sans aucun
argument — et sert la création d'un wiki, la synthèse dirigée, la mise à jour d'un
wiki et (par un autre chemin) la synthèse d'une note.

Deux de ces appels laissent en outre choisir leur analyseur au moment du geste
(`analyseur_id` pour l'analyse, `?analyseur_id=` pour la synthèse d'une note) ; les
trois autres n'ont **aucun paramètre**.

## Ce qui est voulu

**Trois types**, et pas davantage tant qu'une mesure ne le réclame :

| type | ce qu'il sert |
|---|---|
| `analyser` | l'extraction d'hypostases d'une note |
| `synthetiser` | la synthèse d'une note |
| `rediger_un_article` | wiki (création), synthèse dirigée, **et** mise à jour |

**Pourquoi la mise à jour n'a pas son type.** C'est le même métier sur le même
article : ce qui change est la **consigne**, qui reste en dur dans le code, et le
**contrat de sortie**, qui est un tableau JSON d'opérations et reste en dur aussi.
Un type de plus ferait diverger deux préambules qui doivent dire la même chose.

**Le contrat de format ne descend PAS en base**, même verrouillé. Il reste dans
`_consignes_de_forme_d_article()` et dans les consignes du prompt de mise à jour : un
verrou sans interrupteur est plus sûr qu'un cadenas.

## Cinq obstacles mécaniques, tous vérifiés le 23 août

1. **`max_length=20`** sur `type_analyseur` (`models.py:299`). `rediger_un_article`
   tient (18 car.) ; un `mettre_a_jour_un_wiki` aurait fait **21** et exigé une
   `AlterField`. C'est une raison de plus de s'en tenir à trois.
2. **Le `<select>` du type est écrit en dur, à deux endroits** :
   `hypostasis_extractor/templates/hypostasis_extractor/analyseur_editor.html:83-84`
   et `front/static/front/js/hypostasia.js:261-264`. Un type absent de cette liste
   n'est pas sélectionnable — **et pire** : le `<select>` retombe sur la première
   option, et l'auto-save PATCH (`analyseur_editor.html:400`) **écrase le vrai type**
   au premier `change`.
3. **Onze querysets `filter(type_analyseur="…")` en dur** (`front/views.py:650, 2834,
   2838, 2853, 3120, 3126, 5793` ; `front/tasks.py:1120` ;
   `analyser_les_notes_etalons.py:96` ; `benchmarks/chaine_complete/comparer_la_chaine.py:197` ;
   `migrations/0035:61`). Ils n'échouent pas sur un type neuf : ils l'**ignorent**.
4. **`verifier_utilisabilite_analyseur` blanchit tout ce qui n'est pas `analyser`**
   (`hypostasis_extractor/services/__init__.py:246-248` : `return True, []`). Un
   `rediger_un_article` sans la moindre pièce de prompt passerait pour utilisable.
   La garde est donc à **étendre**, pas à créer.
5. **`est_par_defaut` vole le défaut en basculant de type.**
   `AnalyseurSyntaxique.save()` (`models.py:341-345`) filtre sur la valeur
   **nouvelle** : changer le type d'un analyseur par défaut décoche le défaut du type
   d'**arrivée** et laisse le type de **départ** sans aucun défaut. Aucune
   `UniqueConstraint`, aucune garantie « au moins un par type » ; sans défaut, tout
   retombe sur le premier par ordre **alphabétique**, et aucun test n'épingle ce tri.

## Le piège de la migration : le prompt du mainteneur devient orphelin, en silence

`creer_les_modeles_ia_et_les_analyseurs()` tourne **à chaque démarrage de conteneur**
(`bin/install.sh`). Elle fait `get_or_create(name=…)`, et ne garnit un analyseur que
s'il n'a **aucune** pièce — précisément pour ne pas écraser un travail d'auteur.

Sur une base existante, avec les types neufs :

1. l'ancien « Synthèse délibérative » (`type=synthetiser`, éventuellement édité à la
   main) **reste tel quel** ;
2. les fixtures créent un **nouvel** analyseur `rediger_un_article`, garni du texte
   **par défaut** ;
3. le code interroge le nouveau type, le trouve, et **le prompt personnalisé cesse
   d'être utilisé**. Aucune erreur, aucun journal.

Il faut donc une **migration de données** qui bascule l'analyseur existant vers son
nouveau type, plutôt que d'en créer un à côté. Précédent à ne pas suivre :
`migrations/0028` a retiré `reformuler`/`restituer` par un `AlterField` **sans
`RunPython`** — le dépôt tolère déjà des valeurs orphelines en base.

Et dans la fenêtre où le code typé est déployé mais les fixtures n'ont pas tourné,
`_prompt_systeme_de_synthese()` retombe sur son repli en dur de trois lignes
(`front/tasks.py:1136-1141`) : **le rédacteur écrit sans consigne, et rien ne lève.**
Le régime de repli par type doit être posé explicitement, sur le modèle documenté de
`modele_du_role()` — ainsi que l'ordre de résolution : geste (`?analyseur_id=`), puis
carnet, puis défaut.

## Ce qu'il faut mesurer

- **Fixtures étalons à écrire** : un jeu gelé hors base pour chacun des trois types —
  un carnet, ses notes, ses extractions, et la sortie attendue. Sans étalon par type,
  « le type X fait mieux » n'est pas une phrase mesurable.
- **Un banc LLM réel par type** (`make test-llm`, tag `llm_reel`, **facturé**), avant
  et après la séparation : si trois préambules distincts ne font pas mieux qu'un seul,
  la séparation ne doit se justifier que par la lisibilité, et il faut le dire.
- **Attention au banc qui ment déjà** : `benchmarks/chaine_complete/comparer_la_chaine.py:237-256`
  réassemble le prompt de création **à la main** (il n'appelle que les trois helpers),
  alors que sa docstring dit « le prompt de production ». Il ne suivra ni le typage,
  ni la direction rejouée. `benchmarks/redaction/lancer_les_passes.py:130` passe par
  la vraie tâche et suivra. **Deux bancs vont diverger sans qu'une ligne le dise** :
  à corriger dans ce chantier.
- **Le bruit** : `PLAN/PASSATION.md` § 6 mesure 11 points d'amplitude intra-modèle.
  Répéter, et ne rien conclure sous cette amplitude.

## Ce qui casse si on ne fait rien

Rien ne casse : on ne peut simplement pas régler séparément quatre gestes qui n'ont
pas le même but. Et le jour où l'on veut qu'un wiki soit rédigé autrement qu'une
synthèse dirigée, il faut modifier le code — ce que l'éditeur de prompts existe
précisément pour éviter.

## Coût de mise en œuvre

Ce n'est pas « ajouter une valeur d'enum » : c'est une migration de données, onze
querysets, deux `<select>` en dur, du JS, une garde d'utilisabilité par type, le
régime de repli, et une quinzaine de fichiers de test qui épinglent les deux valeurs
actuelles. Deux à trois jours, plus les bancs.
