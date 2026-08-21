# SPEC — Couche corpus : base de connaissances, carnet, note

**Projet** : Hypostasia V3
**Version de la spec** : 1.1 — 5 août 2026 (corrigée après relecture adverse)
**Complète** : `SPEC-ancrage-par-element-v2.md` (couche ancrage, en dessous)
**Complétée par** : `SPEC-synthese-carnet.md` et `SPEC-selection-des-preuves.md` (au-dessus)
**Statut** : **IMPLÉMENTÉE — phases A à H.** La **phase I** (extension) est
partiellement livrée, et sous une forme que ce texte ne décrit pas : voir
l'addendum du 20 août 2026 ci-dessous. Le reste du texte se lit comme la
justification du code livré, pas comme un travail à faire.

> **Addendum du 20 août 2026 — la phase I, en mono-carnet**
>
> L'en-tête annonçait « phases A à **I** codées » depuis le 8 août. C'était faux
> sur la phase I, et le dépôt le disait lui-même : `core/services/corpus.py`
> portait, en commentaire, « le multi-rangement depuis l'extension (cases à
> cocher, § 7.2) **est** la phase I » — au futur.
>
> Ce qui est livré le 20 août, et qui **diverge du § 7** de cette spec :
>
> | Ce que le § 7 prévoit | Ce qui est codé | Pourquoi |
> |---|---|---|
> | cases à cocher, plusieurs carnets d'un coup, `carnet_ids` | **un `<select>`, un seul carnet** | arbitrage du mainteneur : le geste de capture doit rester d'un seul clic. Le multi reste possible plus tard sans casser le contrat |
> | le carnet se choisit **après** la capture (`classer_depuis_extension`) | le carnet se choisit **avant**, `dossier_id` voyage avec le `POST` | un choix explicite fait après coup laisse la note dans le fourre-tout si la popup se ferme entre les deux gestes |
> | `dossier_name` + `carnets_names` dans la réponse de classement | inchangés, mais **plus aucun appelant** | l'endpoint survit sans client ; à retirer ou à rebrancher lors du vrai multi-carnets |
>
> Ce que la phase I apporte **conformément** au § 7 : les partages par **groupe**
> sont enfin honorés par l'API de l'extension (§ 7.1, « bug préexistant à
> corriger au passage »), et l'avertissement « ce carnet est public » apparaît au
> moment du geste (§ 7.3).
>
> **La question ouverte n°5 est traitée, et son énoncé était en-dessous de la
> vérité.** Elle dit « url et titre de tout le corpus sont déjà exposés ».
> Mesuré le 20 août : `GET /api/pages/` sans jeton rendait **291 840 octets pour
> 13 notes**, dont **150 384 caractères de texte lisible** et le HTML d'origine —
> et **12 des 13 notes portaient `url: null`**. Ce n'étaient pas les URL qui
> fuyaient, c'était le contenu. L'endpoint exige désormais un jeton et se borne
> au périmètre du porteur.
>
> **La question ouverte n°4 est tranchée pour l'instant** : l'unicité globale de
> `Page.url` n'est pas touchée. Quand un tiers détient l'URL, la capture répond
> `409 {"code": "url_prise_ailleurs"}` et l'extension le dit en clair. La
> conséquence reste entière : deux collectifs d'une même instance ne peuvent pas
> capturer la même page.
>
> Détail, mesures et recette : `CHANGELOG/2026-08-20-le-webclipper-choisit-son-carnet.md`.
**Conventions** : skill `djc` (ViewSet explicites, serializers DRF, HTMX, FALC, commentaires FR/EN)

> **Note de dépôt (8 août 2026)** — ce document existait hors du dépôt et y est
> déposé sans modification de fond. Les deux specs qui le complètent y renvoient
> de façon structurante ; sans lui, elles ne sont pas exécutables.

---

## 0. Ce qui change depuis la v1.0

La v1.0 a été relue par un agent adverse avec accès au dépôt. Verdict : « implémentable sous conditions ». Neuf corrections, toutes vérifiées dans le code avant d'être appliquées.

| # | Défaut trouvé en v1.0 | Correction en v1.1 |
|---|---|---|
| 1 | Le renommage `Dossier`→`Carnet` était chiffré à 131 occurrences ; c'est **243** (`\bDossier\b` hors migrations), plus **3 fixtures JSON**, **5 fichiers JS** et les `related_name`. Et `DossierPartage`, `VisibiliteDossier`, `/dossiers/`, `name` survivaient au rename — donc la « double langue » qu'il devait supprimer persistait | **Renommage abandonné** pour cette spec (§ 3.0). `Dossier` reste le nom en code, « carnet » le mot à l'écran |
| 2 | `integree_le = auto_now_add` rendait impossible `integree_le = page.created_at` en migration : `auto_now_add` écrase toute valeur assignée | `default=timezone.now` (§ 3.2) |
| 3 | Le signal `m2m_changed` ignorait le kwarg `reverse` → validation erratique sur `categorie.appartenances.add(...)`. Et la moitié base↔carnet n'avait ni validateur ni signal ni test | Signal corrigé + symétrique ajouté (§ 3.4) |
| 4 | `CategorieDossier.dossier` dénormalisé pouvait diverger de `liste.dossier`, et la contrainte d'unicité invoquée pour le justifier ne l'utilisait même pas | Dénormalisation supprimée (§ 3.3) |
| 5 | `_est_proprietaire_page` faisait **perdre la modération au propriétaire du carnet** dès que `page.owner` était renseigné — or l'extension renseigne toujours `owner` (`core/views.py:229`). Dans le cas lycée, le prof perdait la modération sur les captures des élèves | Règle élargie : owner de la note **OU** owner d'un carnet la contenant (§ 5.2) |
| 6 | Les pages `owner=None` sans dossier, aujourd'hui accessibles à **tout authentifié** (`front/views.py:274-277`), devenaient invisibles pour tous | Comportement legacy préservé explicitement (§ 5.2) |
| 7 | `CarnetViewSet.permission_classes = [IsAuthenticated]` tuait les carnets publics pour les anonymes, alors que `_utilisateur_a_acces_dossier` les autorise (`front/views.py:105-107`) | `AllowAny` + contrôle par objet (§ 9) |
| 8 | « Conversion progressive des appelants » incompatible avec « toute lecture passe par la table de liaison » : pendant la transition, une note rangée dans un carnet public restait refusée par les anciennes vues | Liste fermée des lecteurs à convertir, **en un seul lot** (§ 4.3) |
| 9 | « Les deux specs ne se touchent que sur les permissions » : faux. `front/tasks.py:930` crée les pages-versions avec `dossier=page_racine.dossier`, `:959` et `:989` notifient via `page.dossier.owner` | Points de contact déclarés (§ 11) |

Deux affirmations de la v1.0 étaient factuellement fausses et sont retirées : l'extension n'est **pas** publiée sur un store (`extension/README.md:18` — installation en mode développeur uniquement), et `POST /api/pages/` n'est **pas** « inchangé » (il dépend de `Page.dossier` en trois endroits, `core/views.py:173-175`, `:230`).

---

## 1. Objet

Faire passer Hypostasia d'un outil « un dossier contient des pages » à une **plateforme de gestion de corpus**, sur le modèle à trois niveaux de Praxis (En Commun) : **base de connaissances → carnet → note**, avec deux relations N-N et **la catégorie portée par la relation, pas par l'objet**.

### Le blocage actuel, en une phrase

`Page.dossier` est une `ForeignKey` `SET_NULL` (`core/models.py:102`). Une page vit dans un dossier et un seul. Dès qu'un verbatim intéresse deux groupes de travail, il faut le dupliquer — et les extractions, les commentaires et le débat se dupliquent avec, ou se perdent.

### Ce que ça débloque

| Besoin client | Impossible aujourd'hui | Après |
|---|---|---|
| Lycée : un CR de conseil intéresse la classe *et* la vie scolaire | Duplication | Une note, deux carnets |
| Tiers-lieux : un appel à projets classé « logement » par un réseau, « transition » par un autre | Un seul classement possible | Catégories propres à chaque carnet |
| Un réseau régional regroupe ses carnets thématiques | Niveau absent | Base de connaissances |
| Ordre narratif dans un carnet (les temps d'une délibération) | Tri chronologique uniquement | Épinglage + ordre manuel |

### Principes

1. **Deux cardinalités N-N.** Une note dans plusieurs carnets, un carnet dans plusieurs bases. Ce ne sont pas des arborescences.
2. **La catégorie appartient à la relation.** Une note classée « Financement » dans le carnet A et « Automne 2025 » dans le carnet B. Chaque collectif garde son vocabulaire sans l'imposer aux autres. C'est le point le plus fin du modèle Praxis, et le seul qui ne se devine pas.
3. **Le niveau base est facultatif.** Un carnet peut vivre sans base, au niveau plateforme — c'est le cas dans Praxis pour les carnets de veille collective ouverte.
4. **La propriété d'une note s'élargit, elle ne se déplace pas.** Aujourd'hui elle se dérive du dossier ; demain c'est `Page.owner` **ou** le propriétaire d'un carnet contenant la note. On ajoute un titulaire, on n'en retire pas.
5. **On ne touche pas à la couche ancrage.** `ElementDocument`, `AncrageExtraction`, les extractions et les commentaires sont sous la note et ne bougent pas. Les rares points de contact réels sont déclarés en § 11, pas supposés inexistants.

---

## 2. Ce qu'on prend de Praxis, et ce qu'on ne prend pas

| Praxis | Décision | Raison |
|---|---|---|
| Base de connaissances (N-N carnets) | **Pris** | Niveau manquant, demandé par les réseaux régionaux |
| Carnet (N-N notes) | **Pris** | Le préalable à tout le reste |
| Catégories de la relation note↔carnet | **Pris** | Le cœur de la demande |
| Catégories de la relation carnet↔base | **Pris** | Symétrie — avec sa propre validation et ses propres tests, pas « gratuite » |
| Épinglage + ordre manuel dans un carnet | **Pris** | Sert directement à présenter les temps d'une délibération |
| Guide de rédaction par carnet | **Pris** | Un `TextField` sur le dossier, coût nul |
| 4 niveaux de visibilité note + 4 carnet | **Simplifié** | On garde les 3 niveaux existants sur le carnet. Pas de visibilité au niveau note en v1 (§ 6.1) |
| Suppression des commentaires | **Refusé** | Le commentaire sur une extraction *est* la délibération. C'est notre différenciation, pas une lacune |
| Note « organisation » géolocalisée | **Refusé** | Hors sujet pour nos deux clients |
| Citation APA + licence CC par note | **Reporté** | Utile en production, pas en proto |
| RSS 4 granularités | **Reporté** | On a les WebSocket ; le RSS est un ajout, pas un préalable |

---

## 3. Modèle de données

### 3.0 On ne renomme pas `Dossier` en `Carnet`

La v1.0 proposait ce renommage en préalable. **Abandonné**, après chiffrage réel :

```
grep -rn "\bDossier\b" --include=*.py . | grep -v migrations | wc -l
→ 243        (et non 131 : les "131" comptaient .dossier, pas l'identifiant de classe)

fixtures referencant "model": "core.dossier"
→ front/fixtures/demo_completes.json
  front/fixtures/demo_alignement_versions.json
  front/fixtures/exemple_deliberation.json
  (loaddata casse apres rename, donc reset_demo aussi)

fichiers JS utilisant .dossier-node / data-dossier-id / '/dossiers/'
→ 5 (arbre_overlay.js, arbre_context_menu.js, alignement.js, ...)
```

À quoi s'ajoutent les `related_name` (`dossiers_possedes`, `dossiers_partages`, `partages_dossier`) que `RenameModel` ne renomme pas — il faut des `AlterField` — et surtout : `DossierPartage`, `VisibiliteDossier`, l'URL `/dossiers/` et le champ `name` (anglais, face au `nom` des nouveaux modèles) **survivraient** au renommage. La « double langue permanente » invoquée comme justification ne serait donc pas supprimée. On paierait le coût sans obtenir le bénéfice.

**Décision** : `Dossier` reste le nom du modèle. « Carnet » est le mot à l'écran, via `verbose_name` et les chaînes traduites. La table de liaison s'appelle `AppartenancePageDossier` — inélégant à côté de `BaseDeConnaissances`, assumé.

**Et le renommage, alors ?** Il redevient pertinent *après*, quand le modèle aura cessé de bouger : renommer une classe dont on est en train de changer les relations, c'est deux refactorings entremêlés dans un même diff. Renommer une classe stable, c'est un `sed` et des tests verts. L'ordre inverse de la v1.0 est le bon.

### 3.1 `BaseDeConnaissances` — le niveau nouveau

```python
class BaseDeConnaissances(models.Model):
    """
    Un ensemble de carnets, porte par un collectif.
    / A set of notebooks, held by a collective.

    LOCALISATION : core/models.py

    Exemples reels attendus :
      - un reseau regional de tiers-lieux : ses carnets thematiques de veille
      - un lycee : ses carnets par classe, par projet, par instance

    Ce niveau est FACULTATIF. Un carnet peut exister sans base, directement
    au niveau plateforme — c'est le cas dans Praxis pour les carnets de
    veille collective ouverte. On ne force personne a creer une base pour
    ouvrir un carnet.
    """

    nom = models.CharField(
        max_length=200,
        help_text="Nom de la base de connaissances / Knowledge base name",
    )
    slug = models.SlugField(
        max_length=220,
        unique=True,
        help_text="Identifiant d'URL, ex 'reseau-tiers-lieux-occitanie'.",
    )
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="bases_possedees",
    )
    visibilite = models.CharField(
        max_length=10,
        choices=VisibiliteDossier.choices,   # PRIVE / PARTAGE / PUBLIC, existant
        default=VisibiliteDossier.PRIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Base de connaissances"
        verbose_name_plural = "Bases de connaissances"
```

### 3.2 Les deux tables de liaison

C'est ici que tout se joue. Les deux suivent exactement le même patron : une table intermédiaire qui **porte des catégories propres au contenant**.

```python
class AppartenancePageDossier(models.Model):
    """
    Rattachement d'une note a un carnet, avec les categories propres A CE
    CARNET, l'epinglage et l'ordre manuel.
    / Membership of a note in a notebook, with categories specific TO THIS
    NOTEBOOK, pinning and manual ordering.

    LOCALISATION : core/models.py

    C'EST LA PIECE CENTRALE DE CETTE SPEC.

    Une meme note rattachee a deux carnets a DEUX lignes ici, avec des
    categories differentes dans chacune. Exemple observe sur Praxis : la
    note "Appel a projets APCHQ 2026" appartient a deux carnets et porte
    des categories distinctes dans chacun.

    La categorie n'est donc PAS un attribut de la note. C'est un attribut
    de la RELATION note-carnet. Si on mettait les categories sur la Page,
    le premier collectif a classer imposerait son vocabulaire a tous les
    suivants — exactement ce qu'on veut eviter.
    """

    page = models.ForeignKey(
        "Page",
        on_delete=models.CASCADE,
        related_name="appartenances_dossiers",
    )
    dossier = models.ForeignKey(
        "Dossier",
        on_delete=models.CASCADE,
        related_name="appartenances_pages",
    )
    categories = models.ManyToManyField(
        "CategorieDossier",
        blank=True,
        related_name="appartenances",
        help_text="Categories de CE carnet appliquees a CETTE note. "
                  "Validation en § 3.4 : chaque categorie doit venir du "
                  "meme carnet que cette appartenance.",
    )
    integree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="integrations_de_notes",
    )

    # PAS auto_now_add : la migration de donnees (§ 4.2) doit pouvoir
    # ecrire page.created_at ici. auto_now_add ecrase toute valeur
    # assignee, y compris via bulk_create et les modeles historiques.
    # / NOT auto_now_add: the data migration must be able to write
    # page.created_at here.
    integree_le = models.DateTimeField(default=timezone.now)

    epinglee = models.BooleanField(
        default=False,
        help_text="Remonte en tete du carnet, avant le tri normal",
    )
    ordre_manuel = models.PositiveIntegerField(
        default=0,
        help_text="Ordre de curation. 0 = pas d'ordre impose, on retombe "
                  "sur le tri chronologique. Sert a donner un ordre "
                  "NARRATIF : les temps d'une deliberation.",
    )

    class Meta:
        ordering = ["dossier", "-epinglee", "ordre_manuel", "-integree_le"]
        constraints = [
            models.UniqueConstraint(
                fields=["page", "dossier"],
                name="unicite_page_dans_un_dossier",
            ),
        ]


class AppartenanceDossierBase(models.Model):
    """
    Rattachement d'un carnet a une base, avec les categories propres A
    CETTE BASE. Meme patron, un cran au-dessus.
    / Membership of a notebook in a knowledge base. Same pattern, one
    level up.
    """

    dossier = models.ForeignKey(
        "Dossier", on_delete=models.CASCADE, related_name="appartenances_bases",
    )
    base = models.ForeignKey(
        "BaseDeConnaissances", on_delete=models.CASCADE,
        related_name="appartenances_dossiers",
    )
    categories = models.ManyToManyField(
        "CategorieBase", blank=True, related_name="appartenances",
    )
    integre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="integrations_de_carnets",
    )
    integre_le = models.DateTimeField(default=timezone.now)
    epingle = models.BooleanField(default=False)
    ordre_manuel = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["base", "-epingle", "ordre_manuel", "-integre_le"]
        constraints = [
            models.UniqueConstraint(
                fields=["dossier", "base"],
                name="unicite_dossier_dans_une_base",
            ),
        ]
```

### 3.3 Les catégories, et leurs listes

Praxis documente un plafond de **3 listes de 10 catégories** par carnet. Ce plafond révèle une structure : les catégories ne sont pas une liste plate, elles sont groupées en **axes de classement** (« Type de financement », « Territoire », « Échéance »). Un carnet de veille en a besoin : classer par thème *et* par échéance sont deux questions différentes.

```python
class ListeDeCategories(models.Model):
    """
    Un axe de classement dans un carnet ou une base.
    / A classification axis within a notebook or a knowledge base.

    LOCALISATION : core/models.py

    Exemple pour un carnet de veille financement :
      liste "Type"       -> Appel a projets, Subvention, Prix
      liste "Echeance"   -> Ce mois-ci, Ce trimestre, Passe
      liste "Territoire" -> Regional, National, Europeen
    """

    nom = models.CharField(max_length=100)

    # Une liste appartient SOIT a un carnet, SOIT a une base. Jamais aux deux.
    # / A list belongs EITHER to a notebook OR to a base. Never both.
    dossier = models.ForeignKey(
        "Dossier", on_delete=models.CASCADE,
        null=True, blank=True, related_name="listes_de_categories",
    )
    base = models.ForeignKey(
        "BaseDeConnaissances", on_delete=models.CASCADE,
        null=True, blank=True, related_name="listes_de_categories",
    )

    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["dossier", "base", "ordre", "nom"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(dossier__isnull=False, base__isnull=True)
                    | models.Q(dossier__isnull=True, base__isnull=False)
                ),
                name="liste_appartient_a_un_seul_contenant",
            ),
        ]


class CategorieDossier(models.Model):
    """
    Une categorie applicable aux notes d'un carnet.
    / A category applicable to the notes of one notebook.

    PAS DE CHAMP dossier ICI. La v1.0 le denormalisait "pour la
    validation" ; c'etait une fausse bonne idee :
      - la contrainte d'unicite invoquee pour le justifier porte sur
        (liste, nom), elle ne l'utilisait meme pas ;
      - deplacer une ListeDeCategories vers un autre carnet laissait
        toutes ses categories pointer l'ancien, et la validation § 3.4
        validait alors contre une donnee perimee.
    Le carnet se lit via self.liste.dossier. Une jointure de plus, a
    l'echelle d'un proto, contre une classe entiere de bugs en moins.
    """
    liste = models.ForeignKey(
        ListeDeCategories, on_delete=models.CASCADE,
        related_name="categories_de_dossier",
    )
    nom = models.CharField(max_length=100)
    couleur = models.CharField(
        max_length=7, blank=True, default="",
        help_text="Hex optionnel, ex '#E69F00'. Vide = palette Wong par defaut.",
    )
    ordre = models.PositiveSmallIntegerField(default=0)

    @property
    def dossier_id(self):
        """Le carnet de cette categorie, via sa liste. / This category's notebook."""
        return self.liste.dossier_id

    class Meta:
        ordering = ["liste", "ordre", "nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["liste", "nom"], name="unicite_nom_dans_la_liste",
            ),
        ]


class CategorieBase(models.Model):
    """Une categorie applicable aux carnets d'une base. Meme patron."""
    liste = models.ForeignKey(
        ListeDeCategories, on_delete=models.CASCADE,
        related_name="categories_de_base",
    )
    nom = models.CharField(max_length=100)
    couleur = models.CharField(max_length=7, blank=True, default="")
    ordre = models.PositiveSmallIntegerField(default=0)

    @property
    def base_id(self):
        return self.liste.base_id

    class Meta:
        ordering = ["liste", "ordre", "nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["liste", "nom"], name="unicite_nom_dans_la_liste_de_base",
            ),
        ]
```

**Déplacer une liste d'un contenant à un autre est interdit.** `ListeDeCategories.dossier` et `.base` sont fixés à la création. Changer le contenant d'une liste rendrait incohérentes toutes les catégorisations déjà posées avec ses catégories. Une méthode `clean()` le refuse ; l'interface n'offre pas l'opération. Pour déplacer un axe, on en crée un nouveau dans le carnet cible.

**Pas de plafond en base.** Praxis affiche « 3 listes de 10 catégories » comme une limite documentée ; on ne la code pas en contrainte. On avertit dans l'interface au-delà de 3 listes, sans bloquer.

### 3.4 La validation qui n'a pas le droit de manquer

```python
def valider_les_categories_d_une_appartenance(appartenance, categories_soumises):
    """
    Verifie que chaque categorie appliquee vient bien du carnet de cette
    appartenance.
    / Checks that each applied category comes from this membership's notebook.

    LOCALISATION : core/services/corpus.py

    SANS CETTE VALIDATION, LE MODELE PERD SON SENS : on pourrait appliquer
    a une note, dans le carnet A, une categorie definie par le carnet B.
    Le vocabulaire de B fuirait dans A — exactement ce que la categorie
    portee par la relation existe pour empecher.

    Un ManyToManyField ne peut pas exprimer cette contrainte au niveau
    base (il faudrait une FK composite). Elle est donc applicative.
    """
    categories_etrangeres = [
        categorie for categorie in categories_soumises
        if categorie.liste.dossier_id != appartenance.dossier_id
    ]
    if categories_etrangeres:
        noms = ", ".join(c.nom for c in categories_etrangeres)
        raise ValidationError(
            _("Ces catégories n'appartiennent pas à ce carnet : %(noms)s / "
              "These categories do not belong to this notebook: %(noms)s")
            % {"noms": noms}
        )


@receiver(m2m_changed, sender=AppartenancePageDossier.categories.through)
def refuser_une_categorie_d_un_autre_dossier(
    sender, instance, action, pk_set, reverse, **kwargs
):
    """
    Filet de securite au niveau ORM : meme un .add() ou un .set() direct
    en shell ou en fixture ne peut pas introduire une categorie etrangere.
    / ORM-level safety net.

    LOCALISATION : core/signals.py

    LE KWARG reverse EST INDISPENSABLE. La v1.0 l'ignorait, ce qui cassait
    le sens inverse :
      - reverse=False : categories.add(cat) sur une appartenance
                        -> instance EST l'appartenance, pk_set = pks de categories
      - reverse=True  : categorie.appartenances.add(appartenance)
                        -> instance EST la categorie, pk_set = pks d'appartenances
    Sans distinguer les deux, on filtre des pks d'appartenances comme si
    c'etaient des pks de categories : validation erratique, ou qui laisse
    tout passer.
    """
    if action != "pre_add":
        return

    if reverse:
        categorie_ajoutee = instance
        appartenances = AppartenancePageDossier.objects.filter(pk__in=pk_set)
        for appartenance in appartenances:
            valider_les_categories_d_une_appartenance(appartenance, [categorie_ajoutee])
        return

    categories = CategorieDossier.objects.select_related("liste").filter(pk__in=pk_set)
    valider_les_categories_d_une_appartenance(instance, categories)


@receiver(m2m_changed, sender=AppartenanceDossierBase.categories.through)
def refuser_une_categorie_d_une_autre_base(
    sender, instance, action, pk_set, reverse, **kwargs
):
    """
    Le symetrique, cote base. La v1.0 l'avait purement et simplement
    oublie : le § 2 vendait la symetrie carnet<->base comme "cout nul une
    fois la premiere faite", et la spec oubliait la moitie base — ni
    validateur, ni signal, ni test. Le vocabulaire d'une base pouvait
    fuir dans une autre.
    / The symmetric one, base side. v1.0 simply forgot it.
    """
    if action != "pre_add":
        return

    if reverse:
        categorie_ajoutee = instance
        appartenances = AppartenanceDossierBase.objects.filter(pk__in=pk_set)
        for appartenance in appartenances:
            _valider_les_categories_de_base(appartenance, [categorie_ajoutee])
        return

    categories = CategorieBase.objects.select_related("liste").filter(pk__in=pk_set)
    _valider_les_categories_de_base(instance, categories)
```

---

## 4. Migration `Page.dossier` FK → N-N

### 4.1 Pourquoi on migre les données ici, alors qu'on a refusé de le faire dans la spec ancrage

C'est la question que se posera tout relecteur des deux specs, et elle mérite une réponse explicite.

La spec ancrage v2 refuse la migration de données parce que convertir un offset global vers un couple `(élément, offset local)` demande de **deviner** : rien ne garantit que le découpage reconstruit corresponde à celui d'origine, et le plan v1 projetait lui-même 3,9 % d'échecs irrécupérables.

Ici, c'est l'inverse. Passer d'une `ForeignKey` à une table de liaison est un **élargissement pur** : chaque page a 0 ou 1 dossier, donc devient exactement 0 ou 1 ligne d'appartenance. Zéro information perdue, zéro ambiguïté, zéro décision à prendre par ligne. C'est réversible tant que la FK reste en place, et vérifiable par un simple `COUNT`.

Les deux décisions sont opposées parce que les deux migrations le sont.

### 4.2 Le plan, en trois migrations

| # | Contenu | Réversible |
|---|---|---|
| 1 | Créer `BaseDeConnaissances`, les deux appartenances, `ListeDeCategories`, les deux catégories. `Page.dossier` reste en place, intouchée. | oui |
| 2 | **RunPython** : pour chaque `Page` avec `dossier_id` non nul, créer `AppartenancePageDossier(page, dossier, integree_par=page.owner, integree_le=page.created_at)`. Bilan + contrôle d'intégrité. | **oui** |
| 3 | *(version suivante, après recette)* Retirer `Page.dossier`. | non |

**La migration 2 est réversible**, contrairement à toutes celles de l'ancienne spec ancrage — c'est ce qui rend ce plan acceptable là où l'autre ne l'était pas. Et `integree_le` est écrivable parce que le champ n'est **pas** `auto_now_add` (§ 3.2) ; c'est la raison d'être de ce choix.

**Contrôle d'intégrité obligatoire** en fin de migration 2 :

```
[migration 00XX] pages avec un dossier         : N
                 appartenances creees          : N
                 pages sans dossier (ignorees) : M
                 → COHERENT
```

Si les deux premiers nombres diffèrent, la migration lève une exception et annule. Il n'y a aucune raison légitime qu'ils diffèrent.

*(La v1.0 annonçait « 1 247 pages, 38 sans dossier ». Ces chiffres venaient d'une base qu'aucun relecteur ne peut consulter — ils sont retirés. La migration les affichera pour de vrai.)*

### 4.3 La conversion des lecteurs : un seul lot, pas « progressif »

La v1.0 disait « toute lecture passe par la table de liaison » **et** « conversion progressive des 131 occurrences ». Les deux sont incompatibles : tant que l'arbre de navigation lit `dossier.pages` (`front/templates/front/includes/_dossier_node.html:11,36,63,74`) et que `_verifier_acces_page` lit `page.dossier` (`front/views.py:253`), une note ajoutée à un second carnet **n'y apparaît pas**, et une note rangée dans un carnet public reste **refusée** par les anciennes vues.

Le chiffre réel rend le lot unique faisable. Sur les 131 occurrences de `.dossier` :

```
88   dans front/tests/test_phases.py      (tests, à adapter avec le reste)
 8   Invitation.dossier                    (un autre champ, ne pas toucher)
 4   dans des migrations                   (ne jamais toucher)
~25  lecteurs applicatifs réels            ← le vrai périmètre
```

**Liste fermée des lecteurs à convertir en phase D**, en un seul lot, tests verts avant merge :

| Fichier | Ce qu'il lit |
|---|---|
| `front/views.py:253` | `_verifier_acces_page` — le plus critique |
| `front/views.py:369-375` | comptages de l'arbre |
| `front/views_alignement.py:314` | `Page.objects.filter(dossier=dossier)` — **absent du grep `.dossier`**, c'est un kwarg de filtre |
| `front/templates/.../_dossier_node.html` | `dossier.pages.count`, `dossier.pages.all` |
| `core/views.py:173-175` | périmètre de dédup de `POST /api/pages/` |
| `core/views.py:230`, `:377-378`, `:411-419` | résolution et écriture du dossier |
| `front/tasks.py:930`, `:959`, `:989` | pages-versions et notifications (§ 11) |

**Ce que fait la FK pendant la coexistence** : elle porte le *premier* carnet de la note, écrite uniquement par la fonction de service `ranger_une_note_dans_un_carnet()`. Au retrait d'une appartenance (`retirer_d_un_carnet`, § 9), si la FK pointait ce carnet, elle est réaffectée à une autre appartenance restante, ou mise à `NULL` s'il n'en reste aucune. La v1.0 ne définissait pas ce cas.

---

## 5. Permissions

### 5.1 Ce qui casse

`_est_proprietaire_dossier(utilisateur, page)` (`front/views.py:186`) fait aujourd'hui `page.dossier.owner == utilisateur`. Avec le N-N, « le dossier de la page » n'existe plus. La fonction doit être remplacée.

`_utilisateur_a_acces_dossier(utilisateur, dossier)` (`front/views.py:78`) et `_utilisateur_peut_ecrire_dossier(utilisateur, dossier)` (`:140`) **ne changent pas** : elles portent sur *un* carnet, et cette question garde son sens. Ce sont leurs appelants, qui passaient `page.dossier`, qui changent.

### 5.2 Les trois nouvelles fonctions

```python
def _utilisateur_a_acces_page(utilisateur, page, dossiers_precharges=None):
    """
    Un utilisateur accede a une note s'il accede a AU MOINS UN carnet qui
    la contient.
    / A user can access a note if they can access AT LEAST ONE notebook
    containing it.

    LOCALISATION : front/views.py

    C'est la regle la plus permissive, et c'est voulu : ranger une note
    dans un carnet public LA REND PUBLIQUE. L'interface doit le dire au
    moment du rangement (§ 7.3), pas apres.

    dossiers_precharges evite une requete quand l'appelant a deja fait le
    prefetch (§ 5.3).

    CAS LEGACY PRESERVE : une note sans aucun carnet et sans owner est
    aujourd'hui accessible a TOUT UTILISATEUR AUTHENTIFIE
    (front/views.py:274-277). La v1.0 de cette spec les rendait invisibles
    pour tout le monde. On preserve le comportement existant.
    """
    if utilisateur and utilisateur.is_authenticated and utilisateur.is_superuser:
        return True

    if dossiers_precharges is not None:
        dossiers_contenant_la_note = dossiers_precharges
    else:
        dossiers_contenant_la_note = Dossier.objects.filter(
            appartenances_pages__page=page,
        ).distinct()

    for dossier in dossiers_contenant_la_note:
        if _utilisateur_a_acces_dossier(utilisateur, dossier):
            return True

    if dossiers_contenant_la_note:
        return False

    # Aucun carnet : on retombe exactement sur le comportement actuel
    # / No notebook: fall back to exactly the current behaviour
    if page.owner_id is None:
        return bool(utilisateur and utilisateur.is_authenticated)
    return _est_proprietaire_page(utilisateur, page)


def _utilisateur_peut_ecrire_page(utilisateur, page, dossiers_precharges=None):
    """
    Ecrire sur une note exige le droit d'ecriture sur AU MOINS UN carnet
    qui la contient.
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return False

    dossiers_contenant_la_note = (
        dossiers_precharges
        if dossiers_precharges is not None
        else Dossier.objects.filter(appartenances_pages__page=page).distinct()
    )

    for dossier in dossiers_contenant_la_note:
        if _utilisateur_peut_ecrire_dossier(utilisateur, dossier):
            return True

    if dossiers_contenant_la_note:
        return False
    return _est_proprietaire_page(utilisateur, page)


def _est_proprietaire_page(utilisateur, page):
    """
    Remplace _est_proprietaire_dossier(utilisateur, page).
    / Replaces _est_proprietaire_dossier(utilisateur, page).

    LOCALISATION : front/views.py

    ON ELARGIT, ON NE DEPLACE PAS. La v1.0 faisait primer page.owner seul.
    Consequence non vue a l'epoque : l'extension renseigne TOUJOURS
    page.owner = request.user (core/views.py:229). Donc pour toute page
    capturee par un eleve, le prof proprietaire du carnet de classe
    PERDAIT la moderation — suppression de page (front/views.py:3189),
    de version (:1224), d'extraction (:221), d'entite (:4010, :4062).
    Ce n'etait pas une preservation du comportement, c'etait un
    basculement de gouvernance non discute.

    Regle retenue : proprietaire de la note OU proprietaire d'un carnet
    qui la contient. Le titulaire actuel garde ses droits, l'auteur en
    gagne.
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return False

    if page.owner_id == utilisateur.pk:
        return True

    return Dossier.objects.filter(
        appartenances_pages__page=page,
        owner=utilisateur,
    ).exists()
```

### 5.3 Performance

Ces fonctions sont appelées à chaque affichage de note. Sans précaution, c'est un N+1 sur toute liste. Deux règles :

- Toute vue qui liste des notes fait `prefetch_related("appartenances_dossiers__dossier")` et passe le résultat en `dossiers_precharges`.
- Un test `assertNumQueries` verrouille le compte sur la vue de liste principale.

---

## 6. Ce qui reste non tranché, volontairement

### 6.1 Visibilité au niveau note

Praxis a quatre niveaux sur la note *et* quatre sur le carnet. On n'implémente **que** ceux du carnet en v1. L'accès effectif à une note est l'union des accès à ses carnets (§ 5.2).

Conséquence assumée : on ne peut pas mettre une note privée dans un carnet public. Si le besoin apparaît, on ajoutera `Page.visibilite` avec une règle de **restriction uniquement** (une note peut être plus fermée que ses carnets, jamais plus ouverte). Pas avant d'avoir vu le besoin.

### 6.2 Rôles fins sur le carnet

Praxis distingue *gestionnaire* et *contributeur*. On garde le modèle existant : `owner` + `DossierPartage` (`core/models.py:1135`), sans distinction de rôle parmi les partagés. N'importe quel partagé peut créer et renommer des catégories. Pour un proto avec des collectifs de bonne foi, acceptable. Un champ `role` sur `DossierPartage` est l'évolution évidente le jour où ça pose problème.

### 6.3 Les carnets « magiques » identifiés par leur nom

`« A ranger »` et `« Mes imports »` sont aujourd'hui trouvés par `get_or_create(name=...)` (`core/views.py:414`, `front/views.py:284-296`), et la popup de l'extension filtre sur `dossier.name === 'A ranger'` (`extension/popup.js:459`). Un utilisateur qui renomme son carnet casse ces flux.

**Correction incluse dans cette spec** (c'est trois lignes et ça élimine une classe de bugs) : un champ `role_special` sur `Dossier`, valeurs `""` / `"a_ranger"` / `"mes_imports"`, avec une contrainte d'unicité par `(owner, role_special)` quand il est non vide. Les `get_or_create` par nom sont convertis. L'extension continue de filtrer par nom en attendant sa mise à jour — sans casser, puisque le nom par défaut ne change pas.

---

## 7. L'extension de navigateur — existante, à adapter

**Elle existe déjà et fonctionne** : `extension/`, manifest v3, Readability.js, popup + sidebar + options. Elle n'est pas à construire.

**Correction de la v1.0** : elle n'est **pas** publiée sur un store. `extension/README.md:18` documente une installation en mode développeur uniquement, et précise que sous Firefox les extensions ainsi chargées « disparaissent à la fermeture du navigateur ». Il n'existe donc pas de parc d'extensions impossible à mettre à jour. La rétrocompatibilité du payload est un confort, pas une contrainte dure — et la vraie difficulté est ailleurs.

### 7.1 Ce que l'extension appelle, et ce qui change vraiment

| Appel | Rôle actuel | Ce qui change |
|---|---|---|
| `GET /api/pages/?url=` | Dédoublonnage | Inchangé côté extension. Voir l'angle mort § 12.5 sur `AllowAny` |
| `GET /api/pages/me/` | Vérifier le token | Inchangé |
| `POST /api/pages/` | Créer la page | **À convertir** — dépend de `Page.dossier` en trois endroits (`core/views.py:173-175` dédup, `:230` résolution, écriture directe de la FK) |
| `GET /api/pages/mes_dossiers/` (`core/views.py:271`) | Lister les dossiers | Même forme de réponse. **Bug préexistant à corriger au passage** : ignore les partages par groupe, contrairement à `front/views.py:126-135` (§ 12.3) |
| `POST /api/pages/{id}/classer_depuis_extension/` (`:314`) | **Déplace** la page | Devient un **ajout**. C'est la vraie casse — voir ci-dessous |

### 7.2 Déplacement ou ajout : la vraie question

Le code actuel fait un **déplacement** : `page_a_classer.dossier = dossier_cible; save(update_fields=["dossier"])` (`core/views.py:377-378`). Le flux réel est : la popup crée la page sans `dossier_id`, le serveur l'affecte à « À ranger » (`_resoudre_dossier`, `:411-419`), puis le clic sur un dossier l'en **sort**.

Avec une sémantique « ajout d'appartenance », la note resterait dans « À ranger » **pour toujours** — le carnet fourre-tout ne se viderait plus jamais. La v1.0 gardait le format du payload et changeait la sémantique sans le voir.

**Règle retenue** : ranger depuis l'extension **retire l'appartenance à « À ranger »** et ajoute les carnets choisis. C'est un déplacement hors du fourre-tout, plus des ajouts. Le carnet spécial `role_special="a_ranger"` (§ 6.3) rend cette règle exprimable sans comparer des chaînes.

```python
class ClasserDepuisExtensionSerializer(serializers.Serializer):
    """
    Valide le rangement d'une note dans un ou plusieurs carnets.
    / Validates filing a note into one or several notebooks.

    LOCALISATION : core/serializers.py

    On accepte l'ancien format {"dossier_id": 12} en plus du nouveau
    {"carnet_ids": [12, 15]} : ca ne coute rien et evite d'avoir a
    synchroniser exactement la mise a jour de l'extension et celle du
    serveur pendant le developpement.
    """

    dossier_id = serializers.IntegerField(required=False)
    carnet_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=False,
    )

    def validate(self, donnees_validees):
        ancien_format = donnees_validees.get("dossier_id")
        nouveau_format = donnees_validees.get("carnet_ids")

        if not ancien_format and not nouveau_format:
            raise serializers.ValidationError(
                _("Indiquez au moins un carnet / Provide at least one notebook")
            )

        donnees_validees["carnets_a_utiliser"] = (
            nouveau_format if nouveau_format else [ancien_format]
        )
        return donnees_validees
```

**La forme de la réponse est un contrat, elle aussi.** La popup lit `donnees.dossier_name` (`extension/popup.js:497`, produit par `core/views.py:386`) pour afficher « Classée dans … ». Le champ est **conservé** — il porte le nom du premier carnet — et un champ `carnets_names` (liste) est ajouté à côté. La v1.0 ne spécifiait que la requête.

### 7.3 Ce qui change dans la popup

`extension/popup.js:437-465` affiche un bouton par dossier ; un clic range et c'est fini. Nouvelle version : des **cases à cocher** plus un bouton « Ranger », permettant de déposer une capture dans plusieurs carnets d'un coup.

Un avertissement apparaît dès qu'un carnet public est coché : « Ce carnet est public — la note y sera visible par tous. » C'est la contrepartie directe de la règle d'accès la plus permissive (§ 5.2), et elle doit être dite **au moment du geste**.

Le classement par catégorie ne se fait **pas** depuis l'extension. Trop d'interface pour une popup, et le geste de capture doit rester rapide.

---

## 8. UX / UI

### 8.1 Les trois écrans

```
┌─ BASE ────────────────────────────────────────────────┐
│  Réseau des tiers-lieux d'Occitanie                   │
│  12 carnets · 340 notes                               │
│  [Thématique ▾] [Territoire ▾]      ← listes de la base│
│                                                        │
│  📔 Veille financement      86 notes   📌              │
│  📔 Retours d'expérience    54 notes                   │
└────────────────────────────────────────────────────────┘

┌─ CARNET ──────────────────────────────────────────────┐
│  Veille financement          86 notes · public         │
│  [Type ▾] [Échéance ▾] [Territoire ▾]  ← 3 listes      │
│                                                        │
│  📌 Appel à projets ADEME 2027   [AAP] [Ce mois-ci]    │
│     Fonds Leader — mode d'emploi [Subvention]          │
└────────────────────────────────────────────────────────┘

┌─ NOTE ────────────────────────────────────────────────┐
│  Appel à projets APCHQ 2026                            │
│                                                        │
│  Dans 2 carnets :                                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Veille financement    [AAP] [Ce mois-ci]     ✎  │  │
│  │ Habitat participatif  [Logement]             ✎  │  │
│  └──────────────────────────────────────────────────┘  │
│                                     [+ Ajouter à…]     │
│                                                        │
│  [le contenu de la note, avec ses surlignages —        │
│   couche ancrage, spec v2, inchangée]                  │
└────────────────────────────────────────────────────────┘
```

**Le bloc « Dans N carnets »** est la traduction visuelle directe du modèle. Chaque ligne montre un carnet **et les catégories de la note dans ce carnet-là**. Le crayon édite les catégories de cette relation seulement. C'est ce qui rend le concept compréhensible sans l'expliquer.

### 8.2 Filtrer par catégorie

Chaque liste devient un menu déroulant. Les filtres de plusieurs listes se combinent en **ET**, les catégories d'une même liste en **OU**. C'est la convention des facettes de e-commerce, elle n'a pas besoin d'être expliquée.

En HTMX : chaque changement de filtre est un `hx-get` sur la liste des notes, avec `hx-push-url` pour que l'état soit dans l'URL et partageable.

### 8.3 Accessibilité

| Élément | Exigence |
|---|---|
| Pastilles de catégorie | La couleur ne porte jamais seule l'information — le nom est toujours écrit |
| Menus de filtre | `<details>`/`<summary>` natif, ou `aria-expanded` + gestion clavier |
| Bloc « Dans N carnets » | `<ul>` sémantique |
| Avertissement carnet public | `role="status"`, annoncé au cochage |
| Ordre manuel (glisser-déposer) | Alternative clavier obligatoire : boutons monter/descendre |

Tout élément interactif porte un `data-testid` selon la convention `<module>-<element>-<contexte>`.

---

## 9. Endpoints

```python
class CarnetViewSet(viewsets.ViewSet):
    """
    LOCALISATION : front/views_corpus.py
    Toutes les reponses sont du HTML. Aucune reponse JSON pour l'interface.

    AllowAny, PAS IsAuthenticated. La v1.0 mettait IsAuthenticated, ce qui
    tuait les carnets publics pour les anonymes — alors que
    _utilisateur_a_acces_dossier les autorise explicitement
    (front/views.py:105-107) et que c'est le comportement actuel.
    Le controle se fait PAR OBJET, comme partout ailleurs dans front/views.py.
    """
    permission_classes = [permissions.AllowAny]
```

| Méthode | Route | Rôle |
|---|---|---|
| `list` | `GET /carnets/` | Mes carnets + partagés + publics |
| `retrieve` | `GET /carnets/{id}/` | Le carnet, ses notes, ses filtres |
| `notes_filtrees` | `GET /carnets/{id}/notes/` | Partial HTMX de la liste filtrée |
| `gerer_categories` | `GET/POST /carnets/{id}/categories/` | Listes et catégories |
| `reordonner` | `POST /carnets/{id}/reordonner/` | Nouvel `ordre_manuel` |

| Méthode | Route | Rôle |
|---|---|---|
| `ajouter_a_un_carnet` | `POST /notes/{id}/carnets/` | Crée une appartenance |
| `retirer_d_un_carnet` | `DELETE /notes/{id}/carnets/{carnet_id}/` | Supprime l'appartenance. **Ne supprime jamais la note** |
| `categoriser` | `POST /notes/{id}/carnets/{carnet_id}/categories/` | Catégories de *cette* relation |
| `epingler` | `POST /notes/{id}/carnets/{carnet_id}/epingler/` | Bascule `epinglee` |

| Méthode | Route | Rôle |
|---|---|---|
| `list` / `retrieve` | `GET /bases/`, `GET /bases/{slug}/` | Base et ses carnets |
| `ajouter_un_carnet` | `POST /bases/{slug}/carnets/` | Crée une appartenance carnet↔base |
| `gerer_categories` | `GET/POST /bases/{slug}/categories/` | Listes et catégories de la base |

**Deux points de vigilance, tous deux des suppressions déguisées** :

- `retirer_d_un_carnet` sur la **dernière** appartenance rend la note invisible à tous sauf son propriétaire. L'interface doit avertir.
- `page.delete()` (`front/views.py:3189`) retire la note de **tous** les carnets, avec ses extractions et ses commentaires. Sous N-N, ça peut détruire le travail de collectifs qui n'ont pas été consultés. L'avertissement doit nommer les autres carnets concernés.

---

## 10. Tests

### `core/tests/test_corpus_modele.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_une_note_dans_deux_carnets` | Deux appartenances, aucune duplication de `Page` |
| `test_categories_differentes_selon_le_carnet` | La même note porte `[AAP]` dans A et `[Logement]` dans B |
| `test_categorie_etrangere_refusee_par_le_serializer` | `ValidationError` |
| `test_categorie_etrangere_refusee_par_le_signal_sens_direct` | `appartenance.categories.add(cat)` |
| `test_categorie_etrangere_refusee_par_le_signal_sens_inverse` | `cat.appartenances.add(appartenance)` — le cas que la v1.0 cassait |
| `test_categorie_etrangere_refusee_cote_base` | Le symétrique, oublié en v1.0 |
| `test_deplacer_une_liste_est_refuse` | `clean()` lève |
| `test_unicite_page_dossier` | `IntegrityError` |
| `test_liste_appartient_a_un_seul_contenant` | `IntegrityError` |
| `test_carnet_sans_base_est_valide` | Le niveau base est bien facultatif |

### `core/tests/test_corpus_permissions.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_acces_par_le_carnet_le_plus_permissif` | Privé + public → lisible |
| `test_anonyme_accede_a_une_note_de_carnet_public` | Le cas que `IsAuthenticated` cassait |
| `test_note_sans_carnet_sans_owner_reste_accessible_a_tout_authentifie` | Comportement legacy préservé |
| `test_proprietaire_de_carnet_garde_la_moderation` | Le prof supprime la capture d'un élève |
| `test_auteur_de_la_note_est_aussi_proprietaire` | L'élève supprime sa propre capture |
| `test_ecriture_exige_un_carnet_inscriptible` | Lecture publique ≠ écriture |
| `test_pas_de_n_plus_un_sur_la_liste` | `assertNumQueries` |

### `core/tests/test_corpus_migration.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_migration_cree_une_appartenance_par_page` | Comptes égaux |
| `test_migration_preserve_la_date_d_origine` | `integree_le == page.created_at` — impossible avec `auto_now_add` |
| `test_migration_est_reversible` | Rollback → table vide, `Page.dossier` intacte |

### `front/tests/e2e/test_22_corpus.py`

| Test | Scénario |
|---|---|
| `test_ajouter_une_note_a_un_second_carnet` | Le bloc passe de 1 à 2 lignes |
| `test_categoriser_dans_un_carnet_seulement` | Les catégories de l'autre ne bougent pas |
| `test_filtres_combines_et_ou` | ET entre listes, OU dans une liste |
| `test_avertissement_dernier_carnet` | Retirer la dernière appartenance avertit |
| `test_ordre_manuel_au_clavier` | Monter/descendre sans souris |

### `core/tests/test_extension_api.py`

| Test | Ce qu'il vérifie |
|---|---|
| `test_ancien_format_dossier_id_fonctionne` | Confort de développement |
| `test_nouveau_format_carnet_ids_multiple` | Rangement dans 3 carnets en un appel |
| `test_rangement_vide_le_carnet_a_ranger` | La note sort du fourre-tout |
| `test_reponse_conserve_dossier_name` | `popup.js:497` ne casse pas |
| `test_mes_dossiers_inclut_les_partages_par_groupe` | Bug préexistant corrigé |

---

## 11. Points de contact avec la spec ancrage

La v1.0 affirmait que les deux specs « ne se touchent que sur les permissions ». **C'est faux**, et voici les points réels :

| Point | Fichier | Règle retenue |
|---|---|---|
| Les pages-versions (synthèses) héritent du dossier de leur racine | `front/tasks.py:930` (`dossier=page_racine.dossier`) | **Une version suit les appartenances de sa racine.** Un signal réplique les appartenances de la racine sur la version à sa création, et l'interface n'offre pas de ranger une version séparément |
| Les notifications de fin de synthèse ciblent `page.dossier.owner` | `front/tasks.py:959`, `:989` | Cible : `page.owner` **plus** les propriétaires des carnets contenant la note, dédoublonnés |
| `reconvertir_avec_docling` est spécifié « dossier par dossier, par le propriétaire du dossier » | `SPEC-ancrage-par-element-v2.md` § 9 | Une note dans deux carnets serait reconvertie par le propriétaire d'un seul, avec perte potentielle d'extractions pour l'autre. **La commande doit lister les carnets affectés et exiger une confirmation** |
| L'alignement est scopé par dossier | `front/views_alignement.py:314` | Reste scopé par carnet, mais la limite de 6 pages rencontrera des carnets qui grossissent par le multi-rangement. À surveiller, pas à changer maintenant |

> **Ajout du 8 août 2026** — un cinquième point de contact est apparu avec
> `SPEC-synthese-carnet.md` : la synthèse **cesse d'être une version de page** et
> devient une note typée du carnet. La première ligne de ce tableau est donc
> remplacée par le § 2.1 de cette spec-là. `parent_page` reste pour les vraies
> versions d'un même document.

---

## 12. Ordre d'implémentation

| Phase | Contenu | Dépend de |
|---|---|---|
| **A** | Modèles + migrations 1 et 2 + `Dossier.role_special` | — |
| **B** | Validation des catégories (serializer + les deux signaux) + tests modèle | A |
| **C** | Permissions : les trois fonctions, `prefetch_related` | A |
| **D** | **Conversion en un lot** des ~25 lecteurs listés en § 4.3, tests verts avant merge | C |
| **E** | `CarnetViewSet` et les endpoints de note | B, D |
| **F** | UI carnet : liste, filtres par facette, ordre manuel | E |
| **G** | UI note : bloc « Dans N carnets », édition des catégories par relation | E |
| **H** | `BaseViewSet` + UI base | E |
| **I** | Extension : `classer_depuis_extension` multi-carnets, popup à cases à cocher, partages par groupe | E |
| **J** | Migration 3 : retrait de `Page.dossier`, après recette | tout |

**A à D n'ont aucune UI** et sont testables en isolation. Ils peuvent avancer pendant que la couche ancrage (spec v2, phases A-G) avance de son côté.

> **Note du 8 août 2026** — `SPEC-synthese-carnet.md` phase A dépend de la
> **phase A** de cette spec (les appartenances doivent exister), et sa phase C
> dépend de la **phase B** (les catégories, pour `axe_de_direction`).
> `SPEC-selection-des-preuves.md` § 2 dépend de la **phase F** (les facettes
> définissent le périmètre).

---

## 13. Questions ouvertes

1. **Les pages sans dossier après migration.** Faut-il les ranger d'office dans « À ranger » ? Ça change leur visibilité (aujourd'hui : tout authentifié si `owner=None`). À trancher **avant** la migration 2, pas après.
2. **Le renommage `Dossier` → `Carnet`**, repoussé après stabilisation du modèle (§ 3.0). À reprogrammer explicitement, sinon il ne se fera jamais.
3. **Rôle `gestionnaire` vs `contributeur`** (§ 6.2). Le déclencheur sera le premier collectif où quelqu'un renomme les catégories d'un autre.
4. **Le périmètre de dédoublonnage sous N-N.** `POST /api/pages/` renvoie un conflit si l'URL existe dans le périmètre accessible (`core/views.py:173-175`). Avec les carnets publics, ce périmètre s'élargit beaucoup : faut-il refuser une capture parce qu'un inconnu l'a déjà faite dans un carnet public ?
5. **`GET /api/pages/` est `AllowAny` et retourne `Page.objects.all()`** (`core/views.py:100-121`) : url et titre de tout le corpus sont déjà exposés sans authentification. Hors périmètre RGPD accepté, mais c'est un trou de **modèle**, pas de conformité — il contredit tout le modèle de visibilité que cette spec construit.

---

*Spec v1.1 rédigée le 5 août 2026. Vérifications exécutées sur le dépôt : `core/models.py` (Dossier:41, Page:75, Page.dossier:102, DossierPartage:1135, GroupeUtilisateurs:1109), `front/views.py` (:78, :140, :186, :253, :274-277, :369-375, :3189), `core/views.py` (:100-121, :173-175, :229, :230, :271, :314, :377-378, :386, :411-419), `front/tasks.py` (:930, :959, :989), `front/views_alignement.py:314`, `extension/` (README:18, popup.js:12-16, :388, :437-465, :457, :497). 34 migrations sur `core`, 243 occurrences de `\bDossier\b` hors migrations, 3 fixtures JSON, 5 fichiers JS, 10 templates Django.*
