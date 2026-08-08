# SPEC — La synthèse au niveau du carnet

**Projet** : Hypostasia V3
**Version** : 1.0 — 8 août 2026
**Complète** : `SPEC-corpus-base-carnet-note.md` v1.1 (couche corpus, au-dessus)
et `SPEC-ancrage-par-element-v2.md` (couche ancrage, en dessous)
**Étalon** : `tmp/maquettes/corpus.html` — toute divergence entre cette spec et la
maquette est un défaut de l'une des deux, à trancher avant de coder
**Statut** : proposition, à valider
**Conventions** : skill `djc` (ViewSets explicites, serializers DRF, HTMX, FALC,
commentaires FR/EN)

---

## 0. Ce que cette spec décide

| # | Décision | § |
|---|---|---|
| 1 | La synthèse quitte le versionnage de page : c'est une **note du carnet**, typée | 2 |
| 2 | **Deux genres**, pas deux réglages : le wiki vivant et la synthèse dirigée | 3 |
| 3 | Le type de note exclut **mécaniquement** les synthèses du corpus source | 3.3 |
| 4 | Le lien de citation est **persisté** — sans lui, rien ne fonctionne | 4 |
| 5 | Éditer un élément cité par une synthèse **figée** est bloqué ; par un wiki, non | 5 |
| 6 | Une opération de section au titre introuvable est **rejetée visiblement** | 6 |
| 7 | Trois états de vérification, et ce qu'ils **n'établissent pas** | 7 |
| 8 | « Ce qui n'a pas été repris » est une **différence d'ensembles**, jamais une liste | 8 |
| 9 | La **couverture** distingue « inventé » de « jamais extrait » | 9 |
| 10 | Pas de journal des acceptations en v1 — YAGNI assumé | 11.3 |
| 11 | Le marqueur stocké est `[[ext:<id>]]` ; le numéro `[N]` ne l'est jamais | 4.4 |
| 12 | Une source supprimée : refusée si une dirigée cite, signalée si un wiki cite | 4.2 |
| 13 | Le périmètre d'un wiki est défini par des **facettes**, pas par son sujet | 3.1.1 |

---

## 1. Le problème

Aujourd'hui, `synthetiser_page_task` (`front/tasks.py:810`) crée une **nouvelle Page**
rattachée à la précédente par `parent_page`, avec un `version_number` incrémenté. La
synthèse est donc une *version du document*.

Trois conséquences, toutes mauvaises :

- **Sur une transcription, ça n'a pas de sens.** Un compte rendu de conseil n'a pas de
  « version 2 » : la synthèse n'est pas une réécriture du verbatim, c'est un autre texte.
- **Une synthèse d'un seul document n'apprend rien.** Le document dit déjà ce qu'il dit.
  L'intérêt naît quand on synthétise douze séances sur deux ans — ce que le versionnage
  de page ne permet pas d'exprimer.
- **Le numéro ne dit rien.** `V2` ne renseigne ni sur ce qui a changé, ni sur pourquoi.

La couche corpus donne le niveau qui manquait : le **carnet**. Une synthèse porte sur un
ensemble de notes rangées ensemble par un collectif ; c'est là qu'elle appartient.

### Ce qui reste vrai de l'existant

`page.parent_page` et `version_number` **ne disparaissent pas**, mais il faut être exact
sur ce qu'ils servent aujourd'hui : `front/tasks.py:929` est la **seule** écriture de
`parent_page` en production, et c'est la synthèse. La ré-ingestion, elle, modifie en place
(`hypostasis_extractor/services/reingestion.py`) et ne crée aucune version.

Après cette spec, `parent_page` n'a donc plus **aucun** écrivain. On le garde — il porte
l'historique déjà en base, et une vraie gestion de versions de document reste
souhaitable — mais il devient dormant. Le dire évite qu'une session le croie actif.

---

## 2. La synthèse est une note du carnet

```python
class TypeDeNote(models.TextChoices):
    """
    Ce qu'une note EST. Ce n'est pas une etiquette d'affichage : le type
    decide si la note peut servir de SOURCE a une synthese (§ 3.3).
    / Not a display label: the type decides source eligibility.
    """
    NOTE = "note", "Note"
    WIKI = "wiki", "Wiki"
    SYNTHESE = "synthese", "Synthèse dirigée"
```

```python
# core/models.py — sur Page
type_de_note = models.CharField(
    max_length=10,
    choices=TypeDeNote.choices,
    default=TypeDeNote.NOTE,
    db_index=True,
    help_text="Ce que cette note est. Une synthese ou un wiki n'est JAMAIS "
              "source d'une autre synthese — voir services/synthese.py. "
              "/ A synthesis is never a source for another synthesis.",
)
```

**Pourquoi un champ et non une propriété dérivée** : la règle d'exclusion (§ 3.3) doit
être exprimable en une clause `filter()`, pas en boucle Python. Une synthèse qui se
glisserait dans un périmètre par erreur ne se verrait pas — et se citerait elle-même au
tour suivant.

Une synthèse est donc rattachée à son carnet par une `AppartenancePageDossier` ordinaire,
avec ses catégories. **Corollaire assumé** : elle est analysable et commentable comme
n'importe quelle note. C'est voulu — une synthèse contestée doit pouvoir l'être *dans*
l'outil, pas à côté.

### 2.1 Ce que devient l'existant

| Aujourd'hui | Demain |
|---|---|
| `synthetiser_page_task` crée une Page avec `parent_page` | crée une Page `type_de_note=SYNTHESE`, sans `parent_page`, rattachée au carnet |
| Les pilules `V1 · V2` dans l'en-tête | retirées ; l'onglet « Synthèses dirigées » du carnet les remplace |
| `front/tasks.py:930` réplique le dossier de la racine | remplacé par une appartenance au carnet d'origine de la demande |
| `front/tasks.py:959,989` notifie `page.dossier.owner` | notifie les propriétaires des carnets contenant la synthèse |

**Migration de données** : les Pages existantes issues d'une synthèse passent en
`type_de_note=SYNTHESE`. Le critère de repérage est **`ExtractionJob.raw_result`**, qui
porte `est_synthese: True` (`front/tasks.py:872`, lu par `front/views.py:2063`) et
`page_synthese_id` (`front/tasks.py:946`). *Ne pas chercher `ExtractionJob.job_type` : ce
champ n'existe pas.* En repli, `parent_page` non nul suffit — c'est aujourd'hui la seule
écriture de ce champ en production (`front/tasks.py:929`). Réversible : on ne détruit ni `parent_page`, ni les
extractions, ni les commentaires. Bilan chiffré obligatoire en fin de migration.

---

## 3. Deux genres, pas deux réglages

C'est la décision structurante de cette spec. Les deux besoins sont réels et
**incompatibles dans un seul objet**.

### 3.1 Le wiki — thématique et vivant

Un article par sujet, alimenté par les extractions du carnet **que son périmètre
retient**, mis à jour par opérations de section quand le carnet grossit (§ 6). **Un wiki
ne s'adopte pas, il se suit.**

```python
class Wiki(models.Model):
    """
    Un article de synthese VIVANT, sur un sujet, dans un carnet.
    / A living synthesis article, on one subject, in one notebook.

    LOCALISATION : core/models.py

    Il n'a pas de version : il a un ETAT, et un compteur de tours de mise
    a jour. Chaque tour applique des operations de section (§ 6), jamais
    une reecriture. C'est ce qui permet de voir ce qui a change.
    """
    page = models.OneToOneField(
        "Page", on_delete=models.CASCADE, related_name="wiki",
        help_text="La note qui porte l'article. type_de_note = WIKI.",
    )
    dossier = models.ForeignKey(
        "Dossier", on_delete=models.CASCADE, related_name="wikis",
        help_text="Le carnet dont il synthetise les notes.",
    )
    sujet = models.TextField(
        help_text="Ce sur quoi porte l'article, en une phrase. C'est une "
                  "CONSIGNE DE REDACTION, pas un filtre — voir § 3.1.1.",
    )
    # Le PERIMETRE d'un wiki est defini par des CATEGORIES, exactement
    # comme celui d'une synthese dirigee. Sans ca, c'est le modele qui
    # choisirait ses sources en ecrivant.
    # / Facets define the scope; the subject only guides the writing.
    categories_du_perimetre = models.ManyToManyField(
        "CategorieDossier", blank=True, related_name="wikis",
        help_text="Les categories qui definissent le perimetre. Vide = tout "
                  "le carnet. Les categories d'un meme axe se combinent en "
                  "OU, les axes entre eux en ET (spec corpus § 8.2).",
    )
    tours_de_mise_a_jour = models.PositiveIntegerField(default=1)
    derniere_mise_a_jour = models.DateTimeField(auto_now=True)
```

#### 3.1.1 Le sujet n'est pas un filtre — et c'est un point de principe

`SPEC-selection-des-preuves.md` § 1 pose que les preuves se choisissent **avant**
d'écrire. Si le périmètre d'un wiki était « les extractions qui touchent son sujet », il
faudrait bien que quelqu'un décide ce qui « touche le sujet » — et ce quelqu'un serait le
modèle, en rédigeant. Le principe fondateur serait retourné.

**Donc le périmètre d'un wiki est défini par des facettes**, comme celui d'une synthèse
dirigée. Le `sujet` sert à deux choses, et deux seulement : orienter la rédaction dans le
prompt, et dire au lecteur de quoi parle l'article.

Un wiki sans catégorie de périmètre prend **tout le carnet** (moins les synthèses, § 3.3).
C'est le cas par défaut, et il est légitime pour un petit carnet.

**Différence avec la synthèse dirigée** : le wiki stocke des *catégories*, donc son
périmètre se **recalcule** à chaque tour — une note ajoutée au carnet et classée dans ces
catégories y entre. La synthèse dirigée fige la *liste des notes* : elle ne bouge plus.

### 3.2 La synthèse dirigée — un acte daté

Commandée sur un axe de catégories ou une sélection de notes, produite une fois,
**jamais réécrite**. C'est ce qu'un conseil adopte, et ce qu'on peut lui opposer plus tard.

```python
class SyntheseDirigee(models.Model):
    """
    Une synthese FIGEE, produite a une date, sur un perimetre explicite.
    / A frozen synthesis, produced once, on an explicit scope.

    LOCALISATION : core/models.py

    Elle n'a pas de tours : elle a une date de production et un perimetre
    qu'on ne peut plus changer. Si le carnet evolue, on en produit une
    autre — on ne modifie pas celle-ci. C'est la condition pour qu'un
    collectif puisse s'y referer six mois plus tard.
    """
    page = models.OneToOneField(
        "Page", on_delete=models.CASCADE, related_name="synthese_dirigee",
    )
    dossier = models.ForeignKey(
        "Dossier", on_delete=models.CASCADE, related_name="syntheses_dirigees",
    )
    produite_le = models.DateTimeField(default=timezone.now)
    produite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    # Le PERIMETRE est fige a la production : c'est ce qui permet de
    # recalculer « ce qui n'a pas ete repris » (§ 8) des mois apres.
    # / The scope is frozen; it is what makes § 8 reproducible.
    notes_du_perimetre = models.ManyToManyField(
        "Page", related_name="syntheses_qui_la_couvrent",
        help_text="Les notes effectivement dans le perimetre au moment de "
                  "la production. Fige, jamais recalcule.",
    )
    axe_de_direction = models.ForeignKey(
        "ListeDeCategories", on_delete=models.SET_NULL, null=True, blank=True,
        help_text="L'axe qui a dirige la synthese, s'il y en a un.",
    )
    categorie_de_direction = models.ForeignKey(
        "CategorieDossier", on_delete=models.SET_NULL, null=True, blank=True,
    )
```

**Pourquoi `notes_du_perimetre` est figé et non recalculé** : la fonctionnalité du § 8
(« ce qui n'a pas été repris ») n'a de sens que si le périmètre d'alors est connu. Un
périmètre recalculé aujourd'hui donnerait une réponse différente sur une synthèse de mars
— ce serait la réécrire en douce.

### 3.3 Le garde-fou : une synthèse n'est jamais une source

```python
def notes_sources_du_carnet(dossier):
    """
    Les notes d'un carnet qui peuvent servir de SOURCE a une synthese.
    / The notes of a notebook that can serve as sources.

    LOCALISATION : core/services/synthese.py

    SANS CETTE EXCLUSION, LE SYSTEME S'EFFONDRE SUR LUI-MEME. Une synthese
    est une note du carnet (§ 2). Si elle entrait dans le perimetre de la
    suivante, celle-ci citerait celle-la ; au troisieme tour, le wiki se
    citerait lui-meme et la deliberation d'origine disparaitrait sous ses
    propres resumes.

    L'exclusion est MECANIQUE — une clause de filtre, pas une convention
    d'interface. Une synthese qui se glisserait dans un perimetre ne se
    verrait pas.
    / Mechanical exclusion: a filter clause, not a UI convention.
    """
    return Page.objects.filter(
        appartenances_dossiers__dossier=dossier,
        type_de_note=TypeDeNote.NOTE,
    ).distinct()
```

**Test obligatoire** : créer un carnet contenant N notes et M synthèses, vérifier que le
périmètre d'une nouvelle synthèse contient exactement N entrées. Le test doit **exercer**
la règle, pas vérifier qu'une phrase est affichée.

---

## 4. Le lien de citation — le préalable à tout

### 4.1 Ce qui existe, et ce qui manque

`SourceLink` existe déjà (`core/models.py:1320`) avec `extraction_source`,
`ancrage_source` et `commentaires_source`. **Mais aucun code de production ne l'écrit ni
ne le lit** — seules deux suites de tests le créent. Vérifié par recherche exhaustive.

Sans ce lien peuplé, **trois fonctionnalités sont impossibles** : le blocage d'édition
(§ 5), « ce qui n'a pas été repris » (§ 8), et le retour à la source depuis une citation.

### 4.2 Le devenir d'une source supprimée

**`PROTECT` au niveau ORM est impossible, et c'est vérifié.** Relancer une analyse
supprime toutes les extractions du job :

```python
# hypostasis_extractor/services/analyse_par_element.py:121
job_extraction.entities.all().delete()
```

Un `on_delete=PROTECT` sur `SourceLink.extraction_source` ferait donc lever
`ProtectedError` à toute relance d'analyse sur une note citée — **y compris par un simple
wiki**. Cela gèlerait le corpus exactement comme le § 5.1 dit vouloir l'éviter. Deux
autres chemins suppriment aussi des extractions :
`hypostasis_extractor/services/__init__.py:242` et `hypostasis_extractor/views.py:904`.

**La règle retenue : `SET_NULL` au niveau ORM, arbitrage par signal.**

```python
class EtatDeLaSource(models.TextChoices):
    """
    Ce qu'est devenue la source d'une citation.
    / What became of a citation source.
    """
    PRESENTE  = "presente",  "Présente"
    SUPPRIMEE = "supprimee", "Source supprimée"
    DETACHEE  = "detachee",  "Ancre détachée"


@receiver(pre_delete, sender=ExtractedEntity)
def arbitrer_la_suppression_d_une_source(sender, instance, **kwargs):
    """
    Une extraction citee ne peut pas disparaitre en silence.
    / A cited extraction cannot vanish silently.

    LOCALISATION : core/signals.py

    DEUX REGIMES, selon QUI cite :

    · une SYNTHESE DIRIGEE cite -> on REFUSE la suppression. C'est un acte
      date : sa preuve ne peut pas s'evaporer. La relance d'analyse sur
      une telle note est donc bloquee, exactement comme l'edition (§ 5).

    · seuls des WIKIS citent -> on AUTORISE, et chaque citation bascule en
      SUPPRIMEE. Le wiki est vivant : sa prochaine mise a jour verra la
      source manquante et corrigera. Le lecteur, lui, voit « source
      supprimee » au lieu d'un renvoi mort.

    Ce qui est interdit dans les deux cas, c'est l'orphelinage silencieux.
    / Never silent orphaning; the regime depends on who cites.
    """
    citations = SourceLink.objects.filter(extraction_source=instance)
    if citations.filter(page_cible__type_de_note=TypeDeNote.SYNTHESE).exists():
        raise SuppressionRefuseeSourceCitee(instance, citations)
    citations.update(etat_de_la_source=EtatDeLaSource.SUPPRIMEE)
```

```python
# core/models.py — sur SourceLink
extraction_source = models.ForeignKey(
    "hypostasis_extractor.ExtractedEntity",
    on_delete=models.SET_NULL, null=True, blank=True,
    related_name="citations_dans_des_syntheses",
)
etat_de_la_source = models.CharField(
    max_length=10, choices=EtatDeLaSource.choices,
    default=EtatDeLaSource.PRESENTE, db_index=True,
    help_text="Bascule par signal a la suppression de la source, ou par la "
              "reconciliation quand l'ancre se detache.",
)
```

**Conséquence sur la relance d'analyse** : `analyse_par_element.py` doit appeler la même
garde que l'édition (§ 5) avant de purger. Une note citée par une synthèse figée ne se
ré-analyse pas — il faut d'abord retirer la citation ou produire une nouvelle synthèse.
Une note citée seulement par des wikis se ré-analyse librement.

**Et quand une ancre se détache** (`reconciliation.py`, `EtatAncrage.DETACHEE`), la
citation bascule en `DETACHEE` par le même mécanisme : la source existe encore, mais on
ne sait plus où elle pointe. C'est l'**état de dérive** que le § 11.2 renvoyait à plus
tard ; il est ici, et il ne coûte qu'un champ.


### 4.3 Le lien porte la position dans l'article

```python
# Ce que SourceLink doit gagner
article = models.ForeignKey(
    "Page", on_delete=models.CASCADE, related_name="citations",
    help_text="La synthese ou le wiki qui cite.",
)
section = models.CharField(
    max_length=200,
    help_text="Titre exact de la section citante. Sert aux operations "
              "de mise a jour (§ 6) et a la navigation.",
)
ordre_dans_la_section = models.PositiveSmallIntegerField()
etat_de_verification = models.CharField(
    max_length=12, choices=EtatDeVerification.choices,
    default=EtatDeVerification.NON_VERIFIE,
)
```

### 4.4 Ce qui est stocké dans le texte : le marqueur, pas le numéro

**Le numéro `[N]` n'est jamais stocké.** Un index est instable entre deux ingestions ou
deux tours de wiki : une citation `[3]` mémorisée pointerait vers autre chose après
réindexation.

**Ce qui est stocké dans le markdown est un marqueur d'identifiant** :

```
Le seuil de dix mille euros déclencherait le passage en assemblée.[[ext:608]]
L'ajournement répété est présenté comme un coût en soi.[[ext:602]][[ext:606]]
```

| Élément | Forme | Pourquoi |
|---|---|---|
| Marqueur | `[[ext:<id>]]`, accolé à la fin de l'affirmation | double crochet : ne peut se confondre ni avec un lien markdown `[texte](url)` ni avec une note de bas de page |
| Plusieurs sources | marqueurs consécutifs | l'ordre est celui que le modèle a produit |
| Affichage | `[1]`, `[2]`… par ordre d'apparition | stable dans une page rendue, jamais persisté |

**L'unité « affirmation » est le paragraphe markdown.** C'est la granularité que le
modèle produit naturellement, celle à laquelle l'état de l'art recommande de citer
(§ 7.1), et elle ne demande aucune structure supplémentaire. Un paragraphe sans marqueur
est une affirmation **non sourcée** — c'est ainsi qu'on la détecte, sans avoir besoin
d'un enregistrement pour dire qu'il n'y en a pas.

**Les `SourceLink` sont dérivés du texte à l'enregistrement**, jamais l'inverse : on
parse les marqueurs, on crée un lien par couple (paragraphe, identifiant). Si le texte
change, les liens sont recalculés. Le markdown reste la source de vérité de l'article ;
les liens en sont l'index.

```python
MOTIF_DE_MARQUEUR = re.compile(r"\[\[ext:(\d+)\]\]")

def indexer_les_citations(article):
    """
    Cree un SourceLink par couple (paragraphe, extraction citee).
    / One SourceLink per (paragraph, cited extraction) pair.

    LOCALISATION : core/services/synthese.py

    Le markdown est la verite ; les liens en sont l'index. On les
    reconstruit a chaque enregistrement plutot que de les maintenir en
    parallele — deux verites divergent toujours.
    / Rebuild the index; never maintain two truths.

    Un marqueur pointant une extraction HORS DU PERIMETRE est une
    hallucination : le lien n'est pas cree, le marqueur est retire du
    texte, et le fait est signale a l'humain (jamais en silence).
    """
```

### 4.5 Les champs existants de `SourceLink`

Le modèle porte déjà des champs d'un autre usage. À trancher explicitement, sinon le
code d'écriture ne saura pas quoi mettre dans les colonnes NOT NULL :

| Champ existant | Décision |
|---|---|
| `page_cible` | **c'est l'article citant.** On ne crée pas de champ `article`, on réutilise celui-là |
| `start_char_cible`, `end_char_cible` | bornes du **paragraphe citant** dans le markdown de l'article, recalculées à chaque indexation |
| `type_lien` | ajouter la valeur `"cite"` à `TypeLien` (`core/models.py:1310`, qui ne connaît aujourd'hui que identique / modifie / nouveau / supprime) |
| `ancrage_source` | **la première portion** de l'extraction, par `ordre_dans_extraction`. Le panneau de preuve affiche toutes les portions via `extraction_source.ancrages` |
| `commentaires_source` | renseigné quand l'affirmation vient du débat (§ 7.4) |

*Note : `PLAN/INSPIRATION_ATOMIC.md` § 5 prescrit un champ `citation_index` stocké et
l'abandon silencieux des citations hallucinées. Les deux sont écartés ici. Le § 5 porte
désormais un avertissement.*


---

## 5. Le blocage d'édition d'une source citée

### 5.1 La règle

**Éditer un `ElementDocument` qui porte une portion d'une extraction citée par une
synthèse dirigée est refusé.** Le wiki, lui, ne bloque rien.

```python
class EditionBloqueeParUneSynthese(Exception):
    """
    Levee quand on tente de modifier un element dont une portion est citee
    par une synthese FIGEE.
    / Raised when editing an element cited by a frozen synthesis.

    LOCALISATION : hypostasis_extractor/services/garde_edition.py

    POURQUOI SEULEMENT LES SYNTHESES DIRIGEES

    Une synthese dirigee est un ACTE DATE : un collectif l'a adoptee, et
    peut s'y referer six mois plus tard. Si le texte cite bouge apres coup,
    la preuve de l'acte change en silence. C'est le pire cas de gouvernance.

    Un wiki, lui, est VIVANT : ses citations bougent deja a chaque tour de
    mise a jour, et s'il perd une source, la passe suivante le corrige.
    Bloquer sur les wikis figerait le corpus sans rien proteger — un carnet
    a cinq wikis gelerait la moitie de ses elements des la premiere semaine.
    / Wikis recompute; frozen syntheses cannot.
    """
```

```python
def verifier_qu_aucune_synthese_ne_cite(element):
    """
    LOCALISATION : hypostasis_extractor/services/garde_edition.py

    Meme patron que verifier_qu_aucune_analyse_ne_tourne() (ligne 108),
    appele aux memes endroits : reconciliation, moteur_structure,
    masquage, reingestion.

    ATTENTION AU M2M : une extraction peut porter des portions sur
    PLUSIEURS elements. Citer cette extraction gele donc TOUS ses
    elements, pas seulement celui qui porte le passage cite. C'est
    inevitable — une preuve coupee en deux n'est plus une preuve.
    / One citation freezes every element the extraction spans.
    """
    citations = SourceLink.objects.filter(
        extraction_source__ancrages__element=element,
        article__type_de_note=TypeDeNote.SYNTHESE,
    ).select_related("article").distinct()
    if citations.exists():
        raise EditionBloqueeParUneSynthese(element, list(citations))
```

### 5.2 Ce qu'on ne fait PAS

**On ne retire pas `reconciliation.py`.** Il existe, il est testé, il est transactionnel,
et il fait un travail que le blocage ne fait pas : repositionner les ancres après une
édition légitime. Son principe reste : *« on ne devine pas. Un passage qui apparaît deux
fois pourrait être l'un ou l'autre. On préfère marquer DETACHEE et laisser un humain
trancher. »*

Les deux mécanismes sont complémentaires :

| | Réconciliation *(existe)* | Blocage sur citation *(à faire)* |
|---|---|---|
| Protège | l'ancre suit le texte modifié | la preuve d'un acte adopté ne bouge pas |
| Quand | à chaque édition autorisée | tant qu'une synthèse figée cite |

**On n'interdit pas l'édition après analyse.** L'édition de blocs de transcription
(`front/views.py:2541`, `editer_bloc_inline.html`) est le cas d'usage audio principal :
corriger un mot mal transcrit, renommer un locuteur. L'interdire imposerait de relancer une
analyse complète pour une coquille — et `reconciliation.py` existe précisément pour que ce
soit inutile.

### 5.3 Ce que l'utilisateur voit

Le refus doit **nommer ce qui bloque** : *« ce passage est cité par la synthèse du
12 mars, adoptée. Pour le corriger, il faut d'abord retirer la citation ou produire une
nouvelle synthèse. »* Un refus sans motif est un bug d'interface.

---

## 6. Mise à jour d'un wiki par opérations de section

### 6.1 Le principe

Le modèle ne réécrit pas l'article : il renvoie une **liste d'opérations** qu'un applier
fusionne, et qu'un humain accepte. Schéma repris de `PLAN/INSPIRATION_ATOMIC.md` § 7 —
`NoChange`, `AppendToSection`, `ReplaceSection`, `InsertSection`.

### 6.2 Le rejet est visible, et le contenu conservé

**Cette spec corrige `INSPIRATION_ATOMIC.md` § 7 sur deux points.**

| Cas | § 7 actuel | Cette spec |
|---|---|---|
| `AppendToSection` / `ReplaceSection`, titre introuvable | `logger.warning`, **contenu jeté en silence** (l. 1337, 1344 après annotation) | opération **rejetée visiblement**, contenu conservé et montré |
| `InsertSection`, `after_heading` introuvable | **fallback : ajout en fin d'article** (l. 1353 après annotation) | opération **rejetée visiblement** |

Justification : un titre de section absent de l'article est une **hallucination du
modèle**, pas une approximation de placement. Un fallback silencieux insère du contenu à
un endroit que le modèle n'a pas choisi — c'est pire qu'un rejet, parce que personne ne
voit que quelque chose a mal tourné. Et jeter le contenu en silence est une **perte de
données**.

### 6.3 Le contrôle mécanique s'étend aux sources

Le § 7 ne contrôle que le titre. Il faut aussi rejeter :

- une opération de contenu dont `sources` est **vide** — une affirmation sans preuve n'a
  rien à faire dans un article sourcé ;
- une opération dont une source **n'appartient pas au périmètre** — le modèle a cité
  quelque chose qu'on ne lui a pas donné.

Ces deux contrôles sont déterministes. Ils n'appellent aucun modèle.

### 6.4 Le diff montre l'avant

Un `ReplaceSection` qui n'affiche que le nouveau contenu fait approuver une réécriture
sans montrer ce qui disparaît. **L'ancien corps de section doit être affiché à côté du
nouveau.**

---

## 7. Les trois états de vérification

### 7.1 Ce qu'ils sont

```python
class EtatDeVerification(models.TextChoices):
    NON_VERIFIE = "non_verifie", "Non vérifié"
    VERIFIE     = "verifie",     "Vérifié"
    FAIBLE      = "faible",      "Faible"
    NON_SOURCE  = "non_source",  "Non sourcé"
```

Deux contrôles en cascade, dans cet ordre :

1. **Verbatim** — le texte cité existe-t-il littéralement dans la source ?
2. **Implication (NLI)** — la source soutient-elle l'affirmation ?

### 7.2 Ce qu'ils n'établissent PAS, et qui doit être dit

**« Vérifié » ne veut pas dire « validé par quelqu'un ».** En gouvernance, il sera lu
ainsi. Trois conséquences à assumer dans le modèle :

- L'état porte **son vérificateur** : modèle, version, date, seuil. Un état sans
  provenance est un argument d'autorité automatisé.
- L'état est **contestable** : on peut débattre d'une extraction, il faut pouvoir
  débattre d'un verdict. Un `CommentaireVerification` ou, plus simple, un état
  `CONTESTE` posé par un humain.
- L'état est **par paire (affirmation, source)**, pas par affirmation. Une phrase à deux
  sources ne peut pas porter un seul verdict — l'état de l'art situe l'attribution
  correcte autour de **30 %** en multi-source.

### 7.3 Le statut de débat remonte à la citation

Une affirmation « vérifiée » peut reposer sur une extraction **contestée** et rester
verte. Il faut propager : une citation dont l'extraction source porte `statut_debat =
commente` est marquée comme telle sur le renvoi `[N]`. C'est mécanique et honnête.

### 7.4 La provenance « débat » manque

Une affirmation peut venir d'un **commentaire**, pas de la citation de l'extraction —
par exemple *« un avenant écrit a été chiffré à trois cents euros »*, qui vient d'un
commentaire d'Amina. Aujourd'hui ces cas sont classés `faible`, ce qui **maquille** une
provenance légitime.

`SourceLink.commentaires_source` existe déjà. Il faut un quatrième état, ou un attribut
de source : **sourcé par le débat**. Une affirmation qui rapporte fidèlement un
commentaire n'est pas « faible » — elle a une autre nature de preuve.

---

## 8. Ce qui n'a pas été repris

```python
def extractions_ecartees(article):
    """
    Ce qu'une synthese N'A PAS repris : difference d'ensembles.
    / What the synthesis left out: a set difference.

    LOCALISATION : core/services/synthese.py

    Une synthese dit ce qu'elle retient ; elle ne dit jamais ce qu'elle a
    laisse de cote. C'est pourtant calculable sans aucun appel au modele,
    et c'est ce qui rend une synthese CONTESTABLE — donc utilisable dans
    une gouvernance.

    JAMAIS UNE LISTE STOCKEE. Une liste ecrite a la main ne peut pas etre
    juste : dans la maquette, elle etait fausse sur trois articles sur
    quatre avant qu'on la calcule.
    / Never a stored list; always computed.
    """
    perimetre = extractions_du_perimetre(article)
    citees = SourceLink.objects.filter(article=article).values_list(
        "extraction_source_id", flat=True)
    return perimetre.exclude(id__in=citees)
```

**Périmètre** : pour une synthèse dirigée, les extractions de `notes_du_perimetre` (figé).
Pour un wiki, les extractions des notes sources du carnet (§ 3.3) au moment du calcul.

**Limite à dire** : ceci n'audite que les **citations**. Une extraction lue par le modèle
et utilisée sans être citée traverse la différence. C'est une borne inférieure de
contrôle, pas une garantie — et il faut l'écrire à l'écran plutôt que de survendre.

---

## 9. La couverture

### 9.1 Le problème qu'elle résout

« Non sourcé » confond aujourd'hui deux situations très différentes :

- le modèle a **inventé** — rien dans le document ne le dit ;
- le modèle a raison, mais **le passage n'a jamais été extrait**.

Le cas est réel dans l'étalon : la synthèse du 12 mars affirme *« l'ordre du jour sera
transmis par écrit »*, marqué non sourcé. Or Jonas le dit littéralement au dernier tour.
Le passage existe ; il n'a simplement pas produit d'extraction. La chaîne d'audit le
présente comme une invention potentielle — un faux positif qui décrédibilise l'outil là
où il prétend être rigoureux.

### 9.2 Le calcul

```python
def couverture_de_la_note(page):
    """
    Quels elements portent au moins une extraction, et lesquels non.
    / Which elements carry at least one extraction.

    LOCALISATION : core/services/synthese.py

    C'est une JOINTURE, pas une estimation : aucun appel au modele, aucun
    calcul. Les donnees sont deja la (related_name="portions_d_extractions",
    hypostasis_extractor/models.py:706).
    """
    elements = page.elements.all()
    couverts = elements.filter(portions_d_extractions__isnull=False).distinct()
    return {"total": elements.count(), "couverts": couverts.count()}
```

### 9.3 Ce que ça donne à l'écran

Un liseré en glissière — élément couvert / non couvert — et un chiffre global :
*« 14 éléments sur 41 portent une extraction »*. Avant d'adopter une synthèse, savoir
que l'analyse a lu un tiers du document ou la totalité change tout.

Avec « ce qui n'a pas été repris » (§ 8), la chaîne est complète : la couverture dit ce
qui n'est **jamais entré** dans le périmètre, l'écart dit ce que la synthèse a **laissé**
parmi ce qui y était.

---

## 10. Les endpoints

```python
class WikiViewSet(viewsets.ViewSet):
    """
    LOCALISATION : front/views_synthese.py
    Toutes les reponses sont du HTML. Aucune reponse JSON pour l'interface.
    permission_classes = [permissions.AllowAny] — controle PAR OBJET,
    comme partout ailleurs dans front/views.py (un carnet public est
    lisible par un anonyme).
    """
```

| Méthode | Route | Rôle |
|---|---|---|
| `list` | `GET /carnets/{id}/wikis/` | Les wikis du carnet |
| `retrieve` | `GET /wikis/{id}/` | L'article, ses citations, ses écartées |
| `previsualiser` | `GET /carnets/{id}/wikis/nouveau/` | Sujet, périmètre chiffré, coût estimé |
| `creer` | `POST /carnets/{id}/wikis/` | Lance la tâche |
| `previsualiser_maj` | `GET /wikis/{id}/mise_a_jour/` | Les opérations proposées, avec l'avant |
| `appliquer_maj` | `POST /wikis/{id}/mise_a_jour/` | Applique les opérations retenues |

| Méthode | Route | Rôle |
|---|---|---|
| `list` | `GET /carnets/{id}/syntheses/` | Les synthèses dirigées |
| `previsualiser` | `GET /carnets/{id}/syntheses/nouvelle/` | Direction, portée, coût |
| `creer` | `POST /carnets/{id}/syntheses/` | Lance la tâche, fige le périmètre |
| `ecartees` | `GET /syntheses/{id}/ecartees/` | Partial HTMX de la différence |
| `couverture` | `GET /syntheses/{id}/couverture/` | Partial HTMX de la jointure |

**Une synthèse dirigée n'a pas d'endpoint de mise à jour.** Ce n'est pas un oubli : le
bouton doit être visiblement désactivé, avec le motif en infobulle.

---

## 11. Ce qui est volontairement hors périmètre

### 11.1 Le regroupement des extractions

Traité dans `SPEC-selection-des-preuves.md`. Cette spec-ci suppose qu'on lui remet un
ensemble d'extractions déjà choisi.

### 11.2 L'état de dérive des sources

Une synthèse figée dont une source a été éditée **avant** la mise en place du blocage
(§ 5), ou dont une ancre est passée en `DETACHEE`, devrait le signaler. Le
`TextQuoteSelector` permettrait la détection. **Reporté** — le blocage traite le cas
nominal ; la dérive résiduelle est un chantier à part.

### 11.3 Le journal des acceptations

Qui a accepté quelles opérations, quand. **YAGNI assumé pour le POC.**

Attention à ne pas confondre avec le lien de citation (§ 4), qui n'est **pas** de la
traçabilité mais le modèle de données minimal du sourcing. Sans lui, rien ne marche.

Conséquence à assumer : « retirer une affirmation » d'une synthèse figée contredit le
figeage. En v1, cette action **n'existe pas** — on produit une nouvelle synthèse.

### 11.4 La recherche sémantique

`front/templates/front/includes/recherche_semantique.html` est orphelin, l'endpoint
qu'il appelle n'existe pas, et la touche `/` est un placeholder. Hors périmètre, et à
**supprimer** plutôt qu'à laisser croire qu'il existe.

---

## 12. Tests

### `core/tests/test_synthese_modele.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_une_synthese_est_une_note_du_carnet` | appartenance créée, catégories applicables |
| `test_une_synthese_n_est_jamais_source` | périmètre de N notes + M synthèses → N |
| `test_le_perimetre_d_une_dirigee_est_fige` | ajouter une note au carnet ne change pas `notes_du_perimetre` |
| `test_un_wiki_recalcule_son_perimetre` | l'inverse pour un wiki |

### `core/tests/test_synthese_citations.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_le_lien_de_citation_est_ecrit` | après production, `SourceLink` peuplé pour chaque `[N]` |
| `test_supprimer_une_source_citee_est_refuse` | `ProtectedError` ou passage en « source supprimée » |
| `test_ecartees_est_une_difference_d_ensembles` | périmètre − citées, sur trois configurations |
| `test_couverture_est_une_jointure` | comptes égaux à un `LEFT JOIN` manuel |

### `core/tests/test_garde_synthese.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_editer_un_element_cite_par_une_dirigee_est_bloque` | `EditionBloqueeParUneSynthese` |
| `test_editer_un_element_cite_par_un_wiki_est_permis` | pas d'exception |
| `test_le_blocage_couvre_tous_les_elements_d_une_extraction_M2M` | extraction sur 3 éléments → 3 bloqués |
| `test_reconciliation_fonctionne_toujours` | non-régression du service existant |

### `core/tests/test_section_ops.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_heading_introuvable_rejette_visiblement` | opération rejetée, contenu **conservé** |
| `test_after_heading_introuvable_ne_fait_pas_de_fallback` | pas d'ajout en fin |
| `test_sources_vides_rejetees` | contrôle mécanique § 6.3 |
| `test_sources_hors_perimetre_rejetees` | idem |

---

## 13. Ordre d'implémentation

| Phase | Contenu | Dépend de |
|---|---|---|
| **A** | `type_de_note` + migration + `notes_sources_du_carnet()` + tests | corpus phase A |
| **B** | `SourceLink` : `etat_de_la_source` + signal d'arbitrage, `type_lien="cite"`, parseur de marqueurs, **écriture dans la tâche** | A |
| **C** | `Wiki` et `SyntheseDirigee` + migration des synthèses existantes | A |
| **D** | § 8 écartées et § 9 couverture (calculs purs, testables sans UI) | B, C |
| **E** | `garde_edition` : blocage sur synthèse figée | B |
| **F** | `section_ops` : applier avec rejet visible et contrôles étendus | C |
| **G** | Vérification verbatim + NLI, les trois états, la provenance « débat » | B |
| **H** | UI : onglets Wikis / Synthèses du carnet, article, panneau de preuve | C, D |
| **I** | UI : diff des opérations avec l'avant | F, H |

**A à D n'ont aucune interface** et sont testables en isolation.

---

## 14. Questions ouvertes

1. **Un wiki par sujet, combien par carnet ?** Aucune limite technique. Faut-il un
   avertissement au-delà de quelques-uns, comme pour les axes de classement ?
2. **Que devient une synthèse quand une de ses notes quitte le carnet ?** Le périmètre est
   figé, donc la synthèse garde sa trace. Mais la note n'est plus accessible aux mêmes
   personnes. Faut-il masquer la citation, ou la garder en signalant l'accès perdu ?
3. **La vérification NLI, avec quel modèle ?** Un petit modèle local suffirait et
   coûterait moins qu'un appel API par affirmation. À chiffrer.
4. **L'alignement cross-documents** (`views_alignement.py`) devient une vue du carnet
   filtrée par facettes. Est-ce une quatrième forme de synthèse, ou une visualisation ?
   La maquette le traite comme une visualisation.

---

*Spec v1.0 rédigée le 8 août 2026. Vérifications exécutées sur le dépôt :
`core/models.py` (Page:79-105, SourceLink:1320-1360, ElementDocument:1465),
`hypostasis_extractor/models.py` (AncrageExtraction:700-710, statut_debat:181-195),
`hypostasis_extractor/services/garde_edition.py` (:83, :108, :190),
`hypostasis_extractor/services/reconciliation.py`, `front/tasks.py` (:810, :930, :959, :989),
`front/views.py` (:2541), `PLAN/INSPIRATION_ATOMIC.md` (§ 5 et § 7, tous deux annotés le 8 août 2026).
Étalon : `tmp/maquettes/corpus.html`, vérifié par `scripts/verifier_les_maquettes.py`
(37 contrôles Playwright).*
