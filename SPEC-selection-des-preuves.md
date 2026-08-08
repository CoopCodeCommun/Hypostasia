# SPEC — La sélection des preuves

**Projet** : Hypostasia V3
**Version** : 1.0 — 8 août 2026
**Complète** : `SPEC-synthese-carnet.md` (qui suppose un ensemble de preuves déjà choisi)
**Étalon** : `tmp/maquettes/selection-preuves.html`
**Statut** : proposition, à valider
**Conventions** : skill `djc`

---

## 0. Ce que cette spec décide

| # | Décision | § |
|---|---|---|
| 1 | Le périmètre est **humain**, défini par les facettes du carnet, pas par une distance | 2 |
| 2 | **Le centroïde n'est ni nécessaire pour former, ni admissible pour représenter** | 3 |
| 3 | Un groupe **s'énumère**, il ne s'échantillonne pas | 3.3 |
| 4 | L'algorithme doit **accepter les singletons** — pas de k fixe | 4 |
| 5 | Une **seconde passe transverse** cherche les oppositions ; la géométrie ne peut pas | 5 |
| 6 | Le regroupement est **auditable** : chaque appartenance s'explique par son arête | 6 |
| 7 | Pas de pgvector pour ce calcul — O(n²) suffit à l'échelle d'un carnet | 7 |
| 8 | Le **débat** est un critère de tri que personne d'autre n'a | 8 |

---

## 1. Le problème

L'état de l'art prescrit de **sélectionner les preuves avant d'écrire** : le modèle reçoit
un ensemble déjà choisi, il ne le choisit pas en rédigeant. Reste à décider *comment*
choisir.

La pratique courante sélectionne par **proximité au centroïde sémantique** : on calcule le
point moyen des documents d'un sujet, puis on retient les *K* extractions les plus proches.

Pour une base de connaissances personnelle, c'est bon : on veut l'idée dominante. **Pour
une synthèse délibérative, c'est l'inverse de ce qu'on veut.**

> Une position minoritaire est, par construction géométrique, éloignée de la moyenne.
> Elle ne remonte jamais.

Ce n'est pas un défaut de réglage : c'est ce que l'algorithme calcule. Augmenter *K* ne
répare rien — l'ordre reste le même, on descend plus bas dans une liste triée par
conformité.

Et le cas est concret. Dans l'étalon, une extraction dit : *« la renégociation du bail
repose sur un accord verbal avec le propriétaire actuel »*. Personne d'autre n'en parle,
alors qu'un membre du conseil la commente : *« c'est le vrai risque du budget »*. Un tri
par centralité l'écarte. Une synthèse budgétaire sans elle est fausse.

---

## 2. Le périmètre est humain

**Aucune distance ne décide de qui entre.** Le périmètre est défini par les **facettes du
carnet** — les axes de classement et leurs catégories, posés par un collectif
(`SPEC-corpus-base-carnet-note.md` § 3.3).

```
Périmètre = extractions des notes du carnet
            ∩ notes retenues par les filtres de facettes
            ∖ notes de type WIKI ou SYNTHESE          (SPEC-synthese § 3.3)
```

Trois propriétés qui découlent de ce choix :

- **Un humain a rangé, un humain filtre.** Le périmètre est explicable sans parler de
  vecteurs.
- **Il est reproductible.** Deux exécutions sur les mêmes filtres donnent le même
  périmètre.
- **Il se resserre par le sens, pas par la taille.** Quand un carnet grossit, on ne
  prend pas « les 50 plus centrales » : on synthétise *par axe*. C'est exactement ce
  qu'est la synthèse dirigée.

---

## 3. Le centroïde : la règle

### 3.1 La formule

> **Le centroïde n'est ni nécessaire pour former un groupe, ni admissible pour le
> représenter. Il ne sert qu'à décrire un groupe déjà formé.**

Cette formule est plus sévère qu'une version antérieure (« autorisé pour former, interdit
pour représenter »), et c'est délibéré. L'algorithme retenu (§ 4) **n'utilise aucun
centroïde pour former** : il compare des paires de membres. Le seul algorithme qui forme
par centroïdes, *k-means*, est celui que cette spec écarte.

Prétendre que le centroïde est « autorisé pour former » aurait été contourner la question
plutôt que d'y répondre.

### 3.2 Pourquoi le regroupement n'a pas le défaut de la sélection

| | Sélection par centroïde | Regroupement |
|---|---|---|
| Opération | un **classement**, donc un seuil, donc une exclusion | une **partition**, tout est classé |
| Sort d'un avis minoritaire | loin du centre → n'entre jamais | groupe de taille 1 → **devient visible** |
| Réversible | non — l'écarté n'existe plus dans la sortie | oui — chaque extraction garde son ancre |

**Le critère de sûreté est la réversibilité.** Une opération qui préserve l'accès à la
source peut se permettre d'être approximative ; une opération qui supprime ne le peut pas.
Un regroupement raté est une gêne visible et corrigeable. Une sélection ratée est
invisible.

### 3.3 Un groupe s'énumère

**Toutes les extractions d'un groupe partent au modèle.** Le groupe sert à *structurer*
le contexte, jamais à le *réduire*.

Chiffré sur l'étalon : résumer chaque groupe par son membre le plus central efface
**11 extractions sur 19**. Et dans certains cas — ceux qu'on ne voit pas venir — le
représentant n'est **ni l'une ni l'autre** des deux faces d'un désaccord : les deux
disparaissent, et il ne reste aucune trace qu'il y a eu débat.

C'est le pire cas, et c'est le plus courant dès qu'un groupe compte trois membres ou plus.

---

## 4. L'algorithme

### 4.1 Ce qui convient

**Agglomératif à liaison simple, avec seuil de distance.** Propriétés qui décident :

- **accepte les singletons** — une position isolée reste un groupe, elle n'est pas
  reléguée dans un fourre-tout « bruit » ;
- **aucun *k* à choisir**, aucune graine — donc **reproductible**, donc auditable ;
- l'appartenance s'explique par une **arête** : « ce membre est entré parce qu'il est à
  15 d'un autre membre, sous le seuil de 24 ». C'est une explication qu'un humain peut
  contester.

HDBSCAN convient aussi, avec l'avantage d'un « bruit » explicite — à condition de traiter
ce bruit comme une section de première classe, pas comme un rebut.

### 4.2 Ce qui ne convient pas

**k-means et toute affectation forcée à *k* fixe.**

- Chaque point est forcé dans un cluster : une position isolée est **absorbée** par le
  groupe voisin. Vérifié sur l'étalon : à *k* = 4, l'avis sur le bail disparaît dans un
  groupe de cinq.
- Le découpage dépend de *k* **et** de l'ordre d'initialisation. Deux réglages voisins
  donnent deux résultats. Rien n'est reproductible, donc rien n'est auditable.

**La sélection de représentants par centralité** — c'est le § 3.3.

### 4.3 Le défaut de l'algorithme retenu, et sa détection

La liaison simple a son propre défaut : **l'effet de chaîne**. A touche B, B touche C, et
A se retrouve groupé avec C sans jamais l'avoir approché. Un seul point intermédiaire peut
fusionner deux sujets sans rapport.

Le cas est monté dans l'étalon : une extraction qui parle du seuil financier *et* des
statuts relie deux grappes distantes. Au seuil 46, elles fusionnent.

**Détection, sans facteur arbitraire** :

```python
def part_des_paires_hors_seuil(membres, seuil):
    """
    La part des paires du groupe dont la distance depasse le seuil : ces
    deux membres-la ne se sont JAMAIS approches, ils sont ensemble par un
    chemin. C'est la mesure directe de l'effet de chaine.
    / Direct measure of the chain effect.

    LOCALISATION : core/services/regroupement.py

    UN CRITERE PROPORTIONNEL AU SEUIL NE MARCHE PAS. Une premiere version
    alertait quand le diametre depassait 2,2 fois le seuil : en montant le
    seuil, l'alerte DISPARAISSAIT alors que la fusion s'aggravait.
    / A threshold-proportional criterion hides the problem as it grows.
    """
```

Le **diamètre** du groupe est affiché en permanence dès trois membres, pas seulement en
cas d'alerte. Un chiffre visible vaut mieux qu'un seuil d'alerte à régler.

---

## 5. La seconde passe : les oppositions

### 5.1 Ce que la géométrie ne peut pas voir

**Les embeddings mesurent le sujet, pas la position.** Deux avis opposés sur la même
question sont proches, donc dans le même groupe.

Cas de l'étalon : *« au-delà de dix mille euros, ça passe en assemblée »* et *« si on fixe
un seuil sans le réévaluer, l'inflation l'aura vidé de son sens »* sont à distance 19. Un
résumé du groupe en ferait une position unique.

**Aucun réglage de clustering ne corrige ça.** Il faut une passe qui lise.

### 5.2 Elle doit être transverse

Une seconde passe qui travaillerait **groupe par groupe** raterait les oppositions dont
les deux faces sont sémantiquement éloignées — celles qui n'ont aucun mot en commun.

Cas de l'étalon : *« je voudrais qu'on prenne le temps de l'expliquer aux équipes »*
contre *« l'assemblée générale est seule compétente pour les engagements pluriannuels »*.
Distance : plus de 300. Elles ne se croiseront jamais dans un même groupe.

**Donc la passe s'applique à tout le périmètre, pas cluster par cluster.** Coût : elle
voit *n* extractions au lieu de quelques-unes, mais elle ne produit qu'une liste de
paires, pas du texte.

### 5.3 Ce qu'elle produit

```python
class Opposition(models.Model):
    """
    Deux extractions qui se contredisent. Produite par une passe LLM
    TRANSVERSE au perimetre, jamais par la geometrie.
    / Produced by a cross-perimeter LLM pass, never by geometry.

    LOCALISATION : core/models.py

    Les embeddings les rapprochent quand elles parlent du meme sujet, et
    les eloignent quand le vocabulaire differe — dans les deux cas, la
    distance ne dit RIEN de l'accord ou du desaccord.
    """
    run = models.ForeignKey("RegroupementRun", on_delete=models.CASCADE,
                            related_name="oppositions")
    face_a = models.ForeignKey("hypostasis_extractor.ExtractedEntity",
                               on_delete=models.CASCADE, related_name="+")
    face_b = models.ForeignKey("hypostasis_extractor.ExtractedEntity",
                               on_delete=models.CASCADE, related_name="+")
    motif = models.TextField(help_text="En quoi elles se contredisent, en une phrase.")
    meme_groupe = models.BooleanField(
        help_text="Vrai si la geometrie les a mises ensemble. Sert a montrer "
                  "qu'un resume du groupe effacerait le desaccord.",
    )
```

---

## 6. L'auditabilité

C'est l'exigence de fond : *« un des buts de ce moteur, c'est la compréhension et la
transparence — autant dans un cadre de gouvernance humaine que de transparence
algorithmique. »*

### 6.1 Le run est versionné et rejouable

```python
class RegroupementRun(models.Model):
    """
    Un regroupement, avec de quoi le REJOUER a l'identique.
    / A grouping run, with everything needed to replay it.

    LOCALISATION : core/models.py

    Meme patron qu'AnalyseurVersion et ExtractionJob.raw_result, deja
    pratiques dans le depot.
    """
    dossier = models.ForeignKey("Dossier", on_delete=models.CASCADE)
    modele_embedding = models.CharField(max_length=100)
    version_embedding = models.CharField(max_length=50)
    algorithme = models.CharField(max_length=40)
    parametres = models.JSONField(
        help_text="Seuil, ordre d'initialisation, tout ce qui change le resultat.",
    )
    lance_le = models.DateTimeField(auto_now_add=True)
    lance_par = models.ForeignKey(settings.AUTH_USER_MODEL,
                                  on_delete=models.SET_NULL, null=True)
```

**Un recalcul est un nouveau run, jamais un écrasement.** Comparer deux runs doit être
possible.

### 6.2 Chaque appartenance s'explique par son arête

C'est le point le plus important de ce paragraphe, et celui qui était faux dans une
première version de l'étalon.

**Le panneau affichait la similarité au centroïde pour expliquer une appartenance décidée
par liaison simple.** C'était exactement la confusion que cette spec combat : expliquer
par le centre une appartenance qui ne lui doit rien.

Ce qu'il faut afficher :

> *Elle est entrée par une seule arête : d(604, 503) = 15 ≤ seuil 24. Ce n'est pas sa
> proximité au centre qui l'a fait entrer.*

Et, pour chaque voisin listé, **son groupe** — un voisin très proche mais rangé ailleurs
est précisément ce qu'un humain doit voir pour contester.

### 6.3 Le déplacement manuel est possible et journalisé

Un humain doit pouvoir sortir une extraction d'un groupe ou l'y mettre, **avec une
justification**. Patron existant : `ElementOperation` (`core/models.py:1617-1702`), qui
journalise déjà les scissions et fusions d'éléments.

### 6.4 L'échelle doit être dite

La similarité affichée n'est pas un cosinus tant qu'on travaille sur une projection : il
faut le dire **à l'écran**, pas dans un commentaire de code. Distance et similarité ne
peuvent pas cohabiter sans que leur relation soit visible.

---

## 7. Pas de pgvector pour ce calcul

**Vérifié** : `docker-compose.yml:50` utilise `postgres:17-alpine`, pas l'image pgvector ;
`pyproject.toml` ne contient ni pgvector, ni sentence-transformers, ni scikit-learn ;
aucun champ `embedding` dans aucun modèle. C'est **planifié** en PHASE-33
(`PLAN/README.md:126`), pas fait.

**Il ne faut pas attendre.** À l'échelle d'un carnet — quelques dizaines à quelques
centaines d'extractions — un cosinus O(n²) en numpy suffit largement : 300 extractions
font 45 000 paires, calculées en quelques millisecondes.

pgvector sert la **recherche** à l'échelle de la base entière. Ce n'est pas ce problème.

Ce qu'il faut, en revanche :

- un champ `embedding` sur `ExtractedEntity` (dimension du modèle retenu) ;
- une abstraction d'embedding dans `core/llm_providers.py`, qui ne fait aujourd'hui que
  du chat ;
- une tâche Celery de calcul par lot — patron `ExtractionJob` déjà rodé.

---

## 8. Le tri par le débat

### 8.1 Le signal que personne d'autre n'a

Un RAG classique trie par proximité au centre — donc par **consensus**. Hypostasia dispose
d'un signal qu'aucun autre outil ne possède : le **commentaire**.

Une extraction portant trois commentaires contradictoires est, littéralement, le contraire
d'un consensus. Le centroïde la rejetterait ; nous devrions la faire remonter en premier.

### 8.2 Ce qui est déjà en base

- `statut_debat` (`nouveau` / `commente`) — recalculé par signal à chaque commentaire ;
- le nombre de `CommentaireExtraction` ;
- leurs auteurs, donc la diversité des contributeurs.

Rien de tout cela n'a coûté à produire : c'est la délibération elle-même.

### 8.3 Les ordres proposés

| Ordre | Ce qu'il privilégie | Quand |
|---|---|---|
| **par le débat** | densité de contestation | défaut pour une synthèse délibérative |
| par taille | les groupes les plus fournis | vue d'ensemble |
| par centralité | le consensus | **présenté pour montrer ce qu'il coûte**, pas pour être utilisé |

Le troisième existe dans l'étalon **à titre de démonstration** : on doit pouvoir voir où
tombent les positions isolées quand on trie par consensus.

### 8.4 La raison d'entrée est affichée

Chaque extraction porte pourquoi elle est là : *débattue*, *couvre une famille
d'hypostases*, *position isolée*, *épinglée par un humain*. C'est ce qui rend la sélection
lisible sans expliquer l'algorithme.

---

## 9. La couverture

Traitée en `SPEC-synthese-carnet.md` § 9, mais elle **s'affiche ici** : c'est au moment de
choisir les preuves qu'on veut savoir ce que l'analyse n'a jamais touché.

Sans elle, « non sourcé » confond deux choses — le modèle a inventé, ou le passage n'a
jamais produit d'extraction.

---

## 10. Tests

### `core/tests/test_regroupement.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_une_position_isolee_reste_un_groupe` | agglomératif, singleton préservé |
| `test_kmeans_absorbe_les_isolees` | démonstration du défaut — le test documente |
| `test_le_resultat_est_reproductible` | deux exécutions identiques → mêmes groupes |
| `test_l_effet_de_chaine_est_detecte` | point-pont → part des paires hors seuil ≥ seuil d'alerte |
| `test_le_diametre_est_calcule` | pas de facteur proportionnel au seuil |
| `test_l_arete_d_entree_est_retrouvable` | pour chaque membre, le voisin qui l'a fait entrer |

### `core/tests/test_oppositions.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_une_opposition_dans_un_groupe_est_signalee` | deux avis proches et contraires |
| `test_une_opposition_lointaine_est_trouvee` | deux faces sans mot commun, groupes différents |
| `test_la_passe_est_transverse` | elle reçoit tout le périmètre, pas un groupe |

### `core/tests/test_regroupement_run.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_un_run_est_rejouable` | mêmes paramètres → mêmes groupes |
| `test_un_recalcul_cree_un_nouveau_run` | l'ancien n'est pas écrasé |
| `test_un_deplacement_manuel_est_journalise` | avec sa justification |

---

## 11. Ordre d'implémentation

| Phase | Contenu | Dépend de |
|---|---|---|
| **A** | Champ `embedding` + abstraction dans `llm_providers` + tâche de calcul par lot | — |
| **B** | `regroupement.py` : distances, agglomératif, diamètre, effet de chaîne + tests | A |
| **C** | `RegroupementRun` + `Opposition` + migrations | B |
| **D** | Passe d'oppositions (LLM, transverse) | C |
| **E** | Tri par le débat, raisons d'entrée | B |
| **F** | UI : l'onglet du carnet, la carte, les groupes énumérés, le panneau « pourquoi » | C, D, E |
| **G** | Déplacement manuel journalisé | C, F |

**A à E n'ont aucune interface.**

---

## 12. Questions ouvertes

1. **Quel modèle d'embedding ?** Un petit modèle local suffirait pour le regroupement d'un
   carnet, et éviterait un appel API par extraction. À chiffrer contre
   `text-embedding-3-small`.
2. **Le seuil de regroupement est-il réglable par l'utilisateur, ou fixé ?** L'étalon le
   rend réglable pour qu'on voie son effet. En production, un curseur peut être une
   mauvaise idée : il donne l'impression que le résultat est une affaire de goût.
3. **Que fait-on quand le périmètre dépasse ce qui tient dans un contexte ?** La réponse
   de cette spec est : on découpe par axe (synthèse dirigée), on ne sélectionne pas les
   plus centrales. Reste à définir le seuil de bascule.
4. **La passe d'oppositions vaut-elle son coût sur un grand périmètre ?** Elle voit tout
   le périmètre. Faut-il la limiter aux extractions débattues, ce qui reviendrait à
   supposer que le désaccord est toujours commenté ?
5. **L'alignement cross-documents** partage la même matière (extractions × notes).
   Faut-il fusionner les deux écrans, ou garder l'un tabulaire et l'autre géométrique ?

---

*Spec v1.0 rédigée le 8 août 2026. Vérifications exécutées sur le dépôt :
absence de pgvector (`docker-compose.yml:50`, `pyproject.toml`), absence de champ
`embedding` (recherche exhaustive), `PLAN/README.md:126` (PHASE-33),
`PLAN/INSPIRATION_ATOMIC.md` § 8 (usages RAG déjà prévus),
`core/models.py` (ElementOperation:1617-1702, statut_debat),
`core/llm_providers.py` (chat uniquement), Celery opérationnel
(`hypostasia/settings.py:189-199`).
Étalon : `tmp/maquettes/selection-preuves.html`, dont le moteur JS a été rejoué sous node
pour vérifier ses verdicts.*
