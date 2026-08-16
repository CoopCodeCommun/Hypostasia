# Recette connectée du carnet 1 — 10 août 2026

Parcours réel, connecté (`jonas`, propriétaire du carnet 1
« Démonstration », 5 notes sources), avec de VRAIS appels LLM
(GPT-4o Mini). Chaque étape a abouti ; **aucune erreur 500, aucune
trace nouvelle** dans `django.log` / `extractor.log`, aucune tâche
échouée ni dépassant son plafond.

## Ce qui a été exercé, et en combien de temps

| Étape | Résultat | Durée |
|---|---|---|
| Création d'un wiki (bouton `✦ Nouveau wiki`) | job 941, 5060 caractères, contenu pertinent sur Ostrom | ~30 s |
| Ouverture de l'article | bandeau, 17 renvois cliquables, panneau de preuve | 2,2 s |
| Proposition de mise à jour | job 942, 8 opérations `append_to_section` | ~7 s |
| Application des opérations | article passé au tour 2 | 4 s |
| Vérification des citations | job 943, verbatim + juge NLI en lot | ~25 s |
| Création d'une synthèse dirigée | job 944 | ~35 s |
| Compteurs du carnet | Wikis 2→3, Synthèses 4→5, Notes inchangé | — |

**Objets créés** : Wiki pk **3** (page 678), SyntheseDirigee pk **294**
(page 679), jobs 941-944. Aucun contenu existant touché, aucune
suppression.

## Ce qui marche bien
- La distinction **wiki vivant / synthèse figée** est la réussite de
  l'écran : bandeaux explicites, « Périmètre (figé) » contre
  « Périmètre (recalculé) », bouton de mise à jour désactivé sur la
  synthèse avec un `title` qui explique pourquoi et renvoie au wiki.
- Le **panneau de preuve** : verbatim, débat humain rattaché à
  l'extraction, lien vers la source.
- La règle d'exclusion des wikis et synthèses du corpus source est
  tenue **et expliquée** dans les deux formulaires.
- Le bouton `✦ Nouveau wiki` (lot architecture de page) fait
  exactement ce qu'il annonce : active l'onglet, pose le focus.

---

# BACK — à trancher par le propriétaire, non corrigé

> **Mise à jour (session Fable, 10 août, nuit) : B1, B2 et B3 sont
> CORRIGÉS en TDD** (voir CHANGELOG du 10 août « Recette connectée :
> les trois défauts BACK sont corrigés »). B4 est consigné : B2 force
> déjà le modèle à rédiger ; la qualité du sourçage relève du prompt
> et la surface UI des marqueurs retirés reste à créer.

## B1. Le producteur de wiki perd des citations (le plus grave)
Le texte produit contient **17** marqueurs `[[ext:…]]` mais seulement
**15** `SourceLink` sont créés. Deux marqueurs pointent alors vers le
lien d'un autre. Après mise à jour : 25 renvois dans le DOM contre
« 23 » annoncés ; après vérification, l'en-tête dit « 10 vérifiées ·
13 faibles » (23) quand le corps affiche 9 vérifiées / 16 faibles (25).
**Trois chiffres se contredisent sur le même écran.**
La synthèse dirigée, elle, est cohérente (15 marqueurs = 15 liens) :
le défaut est propre au chemin wiki.

## B2. Les opérations de mise à jour n'ont aucun contenu rédactionnel
Les 8 opérations proposées ont un `contenu` réduit à un marqueur nu :
`{"type":"append_to_section","contenu":"[[ext:35284]]","section":"…"}`.
Appliquées, elles produisent des **paragraphes orphelins faits d'un
seul renvoi** — `[3]`, `[4]`, `[5]`, `[6]`. Le modèle a compris
« ajoute une source » au lieu de « ajoute un passage sourcé ».
Aggravant : **rien dans le diff ne permettait de le prévoir** — la
prévisualisation affichait déjà `[[ext:35284]]` comme « Contenu »,
sans que cela alerte. C'est le résultat le plus abîmé du parcours.

## B3. Le volet des écartées se contredit
Le résumé annonce « 458 extractions du périmètre n'ont pas été
reprises », le contenu déplié en affiche **200**. La troncature
(`front/views_synthese.py`, `[:200]`) n'est pas annoncée, et le
libellé change au passage (« reprises » → « citées »).

## B4. Sourçage très pauvre
Sur 465 extractions du périmètre, le wiki n'en cite que **2**,
réparties sur 17 renvois. Un marqueur a été retiré comme
hors-périmètre, **silencieusement**. Le lecteur voit un article dense
adossé à deux phrases.

---

# FRONT

> **Mise à jour (10 août) : F1, F2 et F3 sont CORRIGÉS** — voir le
> CHANGELOG « les trois frictions FRONT sont corrigées ». Un point
> d'entrée `GET /wikis|syntheses/{pk}/etat/?job_id=N` porte le retour
> de production et la fin de vérification ; le formulaire du diff vise
> désormais l'article, présent dans les deux contextes. 10 tests
> dédiés.
>
> **Mise à jour (10 août) : F4 à F10 sont CORRIGÉS À LEUR TOUR** — voir
> le CHANGELOG « les sept dernières frictions ». 14 tests dédiés.
> **Toutes les frictions de cette recette sont soldées** : B1-B3 par la
> session Fable, F1-F10 ici. Ce qui reste n'est pas un défaut mais du
> non-exercé (cf. plus bas) : `replace_section`, les rejets mécaniques,
> les contestations perdues, le décochage sélectif.
>
> **Un flake à connaître** : `front.tests.e2e.test_03_import.
> test_importer_fichier_md` a échoué deux fois en suite complète et
> repassé deux fois isolément, toujours pendant que la session
> parallèle modifiait l'ingestion. Ce n'est pas une régression : c'est
> le seul test e2e qui touche le code en cours d'édition à côté.

## F1. Une production se lance sans le moindre retour (friction n°1)
Après « Créer le wiki » comme après « Produire la synthèse », la vue
renvoie la liste rechargée. Le nouvel objet y apparaît **comme s'il
était fini** : « tour 1 · 0 sources · 465 écartées ». Rien ne dit
qu'une tâche tourne, rien ne se rafraîchit. Un utilisateur conclut à
un wiki vide et **reclique**. D'autant plus visible que la mise à
jour, elle, affiche correctement un partial « tâche lancée » qui
interroge le serveur.

## F2. La vérification ne dit jamais qu'elle est finie
La zone reste indéfiniment sur « Vérification lancée : verbatim
d'abord, puis le juge d'implication… ». Pas de polling, pas de message
de fin : les verdicts n'apparaissent qu'après un rechargement manuel,
que rien ne suggère.

## F3. Appliquer depuis l'URL directe d'un article est cassé
Le formulaire du diff cible `hx-target="#corpus-panneau-onglet"`, qui
**n'existe pas** sur `/wikis/3/` en accès direct — il ne vit que dans
le panneau d'onglet du carnet. Un utilisateur arrivé par lien partagé
ou par F5 clique « Appliquer les opérations cochées » et **rien ne se
passe**.

## F4. Lire un wiki ne change pas l'URL
Pas de `hx-push-url` sur le lien de la liste : on lit l'article à
l'adresse `/carnets/1/`, F5 ramène à la liste des notes, et l'article
n'est pas partageable depuis l'endroit où on le lit.

## F5. Le diff parle en langage machine
« append_to_section », « Contenu : `[[ext:35284]]` » : le type
d'opération est un identifiant technique et la syntaxe interne des
marqueurs est exposée telle quelle, alors qu'elle est masquée partout
ailleurs. On ne devine pas ce que le texte deviendra.

## F6. Les verdicts se lisent comme un trait de séparation
La légende montre de petits tirets colorés ; le corps affiche un filet
pleine largeur **sous** le paragraphe — pris d'abord pour une bordure
décorative. Le filet couvre tout le paragraphe alors que celui-ci peut
porter des renvois de verdicts différents.

## F7. La légende promet des couleurs que l'article n'a pas
Elle s'affiche avant toute vérification, « non sourcé » compris, état
qu'aucun renvoi ne portait.

## F8. « Mes tâches » ne distingue pas les trois actions
Production, proposition de mise à jour et vérification apparaissent en
trois lignes identiques « Analyse de « Wiki — Recette… » — Terminee ».
Le `name` du job (« Mise à jour — … », « Vérification — … ») est ignoré
au profit du titre de page. Le panneau est par ailleurs **sans
accents** (« Mes taches recentes », « Terminee »), seul endroit de
l'interface dans ce cas.

## F9. Le `<title>` de l'onglet ne change jamais
« Hypostasia — Bibliothèque » sur un carnet comme sur un article.

## F10. Aucun choix de moteur à la création
Ni pour le wiki ni pour la synthèse ; seul un « Diriger par
(optionnel) » catégoriel existe. Le modèle est celui de la
configuration globale — ce qui est peut-être voulu, mais rien ne le
dit.

---

## Non exercé, et pourquoi
- **`replace_section` et les rejets mécaniques** (motif de rejet,
  affichage de l'« avant ») : le modèle n'a proposé que des
  `append_to_section`, toutes acceptables. Il faudrait provoquer une
  proposition avec un titre de section introuvable.
- **Les contestations humaines perdues** : aucune contestation sur ce
  wiki.
- **Le décochage sélectif d'opérations** : appliqué une seule fois,
  avec les 8 cases par défaut, pour ne pas relancer d'action facturée.

## Le contenu de recette a été SUPPRIMÉ (10 août, sur demande)
Wiki 3 (page 678) et SyntheseDirigee 294 (page 679) n'existent plus.

**Méthode** : un essai à blanc avec le `Collector` de Django d'abord —
il suit les cascades et dit exactement ce qui partirait. Il annonçait
2 pages, 1 wiki, 1 synthèse, 4 jobs, 38 `SourceLink`, 2 appartenances,
et surtout **0 extraction emportée**. Le point à vérifier était
celui-là : les 7 extractions citées appartiennent aux notes du carnet,
pas aux articles ; les perdre aurait amputé le corpus source.

**Résultat** : 518 lignes supprimées, dont 465 + 5 entrées de tables de
liaison (le périmètre figé de la synthèse — les liens, pas les
extractions). Contrôle après coup : extractions de la page 1
**21 → 21, inchangé** ; wikis du carnet 3 → 2 ; synthèses 5 → 4. Les
wikis 1 et 2 et les 4 synthèses d'origine sont intacts, le carnet est
revenu exactement à son état d'avant recette, `/wikis/3/` et
`/syntheses/679/` répondent 404.

Les jobs 941-944 sont partis avec leurs pages. Les captures du parcours
restent dans `tmp/recette/` : elles documentent les frictions, elles ne
dépendent pas des objets supprimés.

Captures : `tmp/recette/01-*.png` à `22-mes-taches.png`. Les plus
parlantes : `10-diff-operations.png` (le diff en langage machine),
`15-article-verifie.png` (les paragraphes orphelins et les filets de
verdict), `04-apres-creation.png` (la création sans retour).
