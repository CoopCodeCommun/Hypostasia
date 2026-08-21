"""
Services de la couche corpus : perimetres d'acces et rangement des notes.
/ Corpus layer services: access scopes and note filing.

LOCALISATION : core/services/corpus.py

SPEC-corpus-base-carnet-note.md v1.1 § 3.4 : « la validation qui n'a pas
le droit de manquer ». Sans elle, le modele perd son sens — le vocabulaire
d'un carnet fuirait dans un autre.

LES TROIS PERIMETRES VIVENT ICI, ET NULLE PART AILLEURS. `front/` rend de
l'interface et `core/views.py` sert l'extension : si chacun ecrivait sa
propre version de « qui peut lire quoi », les deux divergeraient. C'est
deja arrive : `core/views.py` ignorait les partages par GROUPE que
`front/views.py` honorait, et un membre de groupe ne voyait pas dans
l'extension un carnet que le site lui montrait.
/ The three scopes live here and nowhere else: front/ renders UI and
core/views.py serves the extension; two copies of "who may read what"
diverge, and they did.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from core.models import Dossier, DossierPartage, Page, VisibiliteDossier


def carnets_visibles_par(utilisateur):
    """
    Les carnets qu'un visiteur peut OUVRIR : les siens, les orphelins,
    les publics, ceux qu'on lui a partages. Anonyme : les publics.
    / The notebooks a visitor may OPEN.

    LOCALISATION : core/services/corpus.py

    Le partage compte qu'il soit direct (`DossierPartage.utilisateur`) ou
    par groupe (`DossierPartage.groupe`) : les deux ouvrent le carnet.
    / A share counts whether it is direct or through a group.

    :param utilisateur: l'utilisateur, authentifie ou anonyme
    :return: un QuerySet de Dossier
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return Dossier.objects.filter(visibilite=VisibiliteDossier.PUBLIC)

    identifiants_partages = DossierPartage.objects.filter(
        Q(utilisateur=utilisateur) | Q(groupe__membres=utilisateur)
    ).values_list("dossier_id", flat=True)

    return Dossier.objects.filter(
        Q(owner=utilisateur)
        | Q(owner__isnull=True)
        | Q(visibilite=VisibiliteDossier.PUBLIC)
        | Q(pk__in=identifiants_partages)
    ).distinct()


def carnets_ou_ecrire(utilisateur):
    """
    Les carnets ou un utilisateur peut ECRIRE : les siens, les orphelins,
    ceux qu'on lui a partages. Anonyme : aucun.
    / The notebooks a user may WRITE to.

    LOCALISATION : core/services/corpus.py

    C'est la version QuerySet de `_utilisateur_peut_ecrire_dossier`
    (front/views.py), qui delegue ici : une seule ecriture de la regle.
    / The QuerySet form of the predicate in front/views.py, which
    delegates here so the rule exists once.

    LA DIFFERENCE AVEC LA LECTURE TIENT EN UN MOT : `PUBLIC` n'est pas
    dans la liste. Un carnet public est lisible par tous et inscriptible
    par son proprietaire et ses invites seulement — sans quoi n'importe
    qui deposerait dans le carnet de n'importe qui.
    / Public means readable by all, never writable by all.

    PAS DE CONTOURNEMENT SUPERUSER, contrairement a la lecture
    (`notes_visibles_par`). Tout lire n'est pas ecrire partout, et en
    ajouter un serait un changement de gouvernance jamais discute.
    / No superuser bypass here, unlike reading.

    `Q(owner__isnull=True)` OUVRE LES CARNETS SANS PROPRIETAIRE A TOUT
    UTILISATEUR AUTHENTIFIE, et c'est le comportement d'origine, conserve
    tel quel (SPEC-corpus § 5.2, correction n°6). Il faut savoir ce qu'il
    implique : `Dossier.owner` est un `SET_NULL`, donc supprimer un compte
    rend TOUS ses carnets orphelins — donc inscriptibles par n'importe
    qui, et proposes dans le menu de l'extension. Aucun carnet orphelin
    n'existe en base au 20 aout 2026 ; le jour ou l'on supprimera un
    compte, ce sera une decision a prendre, pas une surprise a subir.
    / Ownerless notebooks are writable by any authenticated user — the
    original behaviour, preserved. Note that owner is SET_NULL: deleting
    an account orphans all its notebooks. None exist as of 20 Aug 2026.

    :param utilisateur: l'utilisateur, authentifie ou anonyme
    :return: un QuerySet de Dossier
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return Dossier.objects.none()

    identifiants_partages = DossierPartage.objects.filter(
        Q(utilisateur=utilisateur) | Q(groupe__membres=utilisateur)
    ).values_list("dossier_id", flat=True)

    return Dossier.objects.filter(
        Q(owner=utilisateur)
        | Q(owner__isnull=True)
        | Q(pk__in=identifiants_partages)
    ).distinct()


def peut_ecrire_dans_le_carnet(utilisateur, dossier):
    """
    La forme « un seul carnet » de `carnets_ou_ecrire`, sans requete
    quand la reponse se lit sur l'objet.
    / The single-notebook form of carnets_ou_ecrire, query-free when the
    answer is readable on the object itself.

    LOCALISATION : core/services/corpus.py

    ELLE VIT COLLEE A `carnets_ou_ecrire` POUR NE PAS EN DIVERGER : les
    deux premiers tests correspondent, ligne pour ligne, aux deux
    premieres clauses `Q` de la fonction du dessus. Les modifier separement
    est une faute — c'est pour cela qu'elles sont voisines.
    / It sits next to carnets_ou_ecrire so the two cannot drift: the two
    fast checks mirror that function's first two Q clauses.

    POURQUOI PAS UNE SIMPLE DELEGATION AU QUERYSET : ce predicat est
    appele DANS DES BOUCLES d'affichage (une appartenance affichee = un
    appel). Une requete par carnet affiche est le N+1 que
    SPEC-corpus § 5.3 proscrit ; les deux tests directs ci-dessous
    couvrent le cas courant — ses propres carnets — sans toucher la base.
    / A plain delegation would cost one query per displayed notebook.

    :param utilisateur: l'utilisateur, authentifie ou anonyme
    :param dossier: le carnet vise
    :return: True si l'utilisateur peut y ecrire
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return False
    if dossier is None:
        return False

    # Miroir de `Q(owner=utilisateur)` / mirrors Q(owner=utilisateur)
    if dossier.owner_id == utilisateur.pk:
        return True

    # Miroir de `Q(owner__isnull=True)` / mirrors Q(owner__isnull=True)
    if dossier.owner_id is None:
        return True

    # Le partage, lui, se lit en base. / Shares need the database.
    return carnets_ou_ecrire(utilisateur).filter(pk=dossier.pk).exists()


class CarnetRefuse(Exception):
    """
    Le carnet demande n'existe pas, ou l'utilisateur ne peut pas y ecrire.
    / The requested notebook is unknown, or not writable by this user.

    LOCALISATION : core/services/corpus.py

    C'EST UNE EXCEPTION ET NON UN REPLI, ET C'EST TOUT LE SUJET. Une
    destination refusee etait remplacee EN SILENCE par un carnet
    fourre-tout : l'import repondait « enregistre », l'utilisateur
    croyait avoir range dans le carnet de classe, et la note etait
    ailleurs.
    / An exception, not a fallback: a refused destination used to be
    silently swapped for a catch-all notebook.
    """


def carnet_ou_ranger(utilisateur, dossier_id):
    """
    Le carnet ou deposer une note. Il est EXIGE, jamais devine.
    / The notebook to file a note into. It is REQUIRED, never guessed.

    LOCALISATION : core/services/corpus.py

    UNE NOTE APPARTIENT TOUJOURS A UN CARNET, et cette fonction est
    l'endroit unique qui le garantit. Elle sert la capture web
    (core/views.py) comme les quatre chemins d'import (front/views.py).

    IL N'Y A PLUS DE FOURRE-TOUT. Deux carnets magiques recueillaient
    les notes sans destination — « A ranger » pour l'extension,
    « Mes imports » pour l'import de fichiers. Ils se creaient tout
    seuls, ne se videraient jamais, et surtout ils faisaient d'une
    destination NON CHOISIE un cas normal. Depuis que l'interface fait
    choisir, ne rien choisir est une erreur, pas un defaut.
    / No more catch-all notebooks: since the interface makes you choose,
    choosing nothing is an error, not a default.

    LE DROIT D'ECRITURE EST VERIFIE ICI, ET IL NE L'ETAIT NULLE PART.
    Les quatre chemins d'import faisaient
    `Dossier.objects.filter(pk=dossier_id).first()`, sans le moindre
    controle : n'importe quel utilisateur authentifie pouvait deposer
    un fichier dans le carnet de n'importe qui, en passant son
    identifiant. Personne ne l'exploitait parce que l'interface
    n'envoyait jamais `dossier_id` — elle va le faire.
    / Write access is checked here, and it was checked nowhere: any
    authenticated user could drop a file into anyone's notebook.

    :param utilisateur: celui qui depose
    :param dossier_id: l'identifiant du carnet vise
    :raises CarnetRefuse: aucun carnet demande, inconnu, ou interdit
    :return: le Dossier
    """
    if not dossier_id:
        raise CarnetRefuse(
            "Choisissez un carnet de destination. / Choose a destination "
            "notebook."
        )

    carnet = carnets_ou_ecrire(utilisateur).filter(pk=dossier_id).first()
    if carnet is None:
        # Un carnet inconnu et un carnet interdit recoivent la MEME
        # reponse : doctrine du 404, jamais 403 — sinon un import
        # devient un moyen de savoir quels carnets existent.
        # / Unknown and forbidden get the SAME answer.
        raise CarnetRefuse(
            "Ce carnet n'existe pas, ou vous n'avez pas le droit d'y "
            "écrire. / Unknown notebook, or no write access."
        )
    return carnet


def notes_visibles_par(utilisateur):
    """
    Les notes qu'un visiteur peut lire, en une requete.
    / The notes a visitor may read, in one query.

    LOCALISATION : core/services/corpus.py

    C'est la version QuerySet de `_utilisateur_a_acces_page`
    (front/views.py) : l'acces se derive des carnets, et LE PLUS
    PERMISSIF GAGNE (SPEC-corpus § 5.2). Une note rangee dans un carnet
    public est publique.
    / The QuerySet form of the per-object rule: access derives from the
    notebooks, most permissive wins.

    LE CAS LEGACY EST PRESERVE : une note sans aucun carnet et sans
    proprietaire reste lisible par tout utilisateur authentifie
    (correction n°6 de la spec).
    / Legacy preserved: ownerless, notebook-less notes stay readable.

    :param utilisateur: l'utilisateur, authentifie ou anonyme
    :return: un QuerySet de Page
    """
    if utilisateur and utilisateur.is_authenticated and utilisateur.is_superuser:
        return Page.objects.all()

    filtre_du_carnet = Q(
        appartenances_dossiers__dossier__in=carnets_visibles_par(utilisateur)
    )

    if not utilisateur or not utilisateur.is_authenticated:
        # Un anonyme n'a pas de note orpheline a lui : seuls les carnets
        # publics lui ouvrent quelque chose.
        # / An anonymous visitor only reads through public notebooks.
        return Page.objects.filter(filtre_du_carnet).distinct()

    # Une note sans aucun carnet : elle suit son proprietaire, et le cas
    # legacy (aucun proprietaire) reste ouvert a tout authentifie.
    # / A notebook-less note follows its owner; the legacy case stays open.
    filtre_de_l_orpheline = Q(appartenances_dossiers__isnull=True) & (
        Q(owner__isnull=True) | Q(owner=utilisateur)
    )

    return Page.objects.filter(
        filtre_du_carnet | filtre_de_l_orpheline
    ).distinct()


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
    base (il faudrait une FK composite). Elle est donc applicative :
    ici pour les serializers, et en filet de securite dans les signaux
    m2m_changed (core/signals.py).
    / A ManyToManyField cannot express this constraint at the database
    level; it is enforced in application code.
    """
    categories_etrangeres = [
        categorie for categorie in categories_soumises
        if categorie.liste.dossier_id != appartenance.dossier_id
    ]
    if categories_etrangeres:
        noms = ", ".join(categorie.nom for categorie in categories_etrangeres)
        raise ValidationError(
            _("Ces catégories n'appartiennent pas à ce carnet : %(noms)s / "
              "These categories do not belong to this notebook: %(noms)s")
            % {"noms": noms}
        )


def valider_les_categories_d_une_appartenance_de_base(appartenance, categories_soumises):
    """
    Le symetrique, cote base : chaque categorie appliquee a une
    appartenance carnet-base doit venir de la base de cette appartenance.
    / The symmetric one, base side: each category applied to a
    notebook-base membership must come from that membership's base.

    LOCALISATION : core/services/corpus.py

    La v1.0 de la spec l'avait oublie : le vocabulaire d'une base pouvait
    fuir dans une autre. / Spec v1.0 forgot it entirely.
    """
    categories_etrangeres = [
        categorie for categorie in categories_soumises
        if categorie.liste.base_id != appartenance.base_id
    ]
    if categories_etrangeres:
        noms = ", ".join(categorie.nom for categorie in categories_etrangeres)
        raise ValidationError(
            _("Ces catégories n'appartiennent pas à cette base : %(noms)s / "
              "These categories do not belong to this knowledge base: %(noms)s")
            % {"noms": noms}
        )


# ---------------------------------------------------------------------------
# RANGEMENT NOTE <-> CARNET (SPEC-corpus § 4.3, phase D)
# Pendant la coexistence FK / table de liaison, la FK Page.dossier porte le
# PREMIER carnet de la note et n'est ecrite QUE par ces fonctions. Toute vue
# qui range, retire ou deplace une note passe par ici — jamais d'ecriture
# directe de page.dossier ailleurs.
# / NOTE <-> NOTEBOOK FILING: during coexistence, the FK carries the note's
# FIRST notebook and is written ONLY by these functions.
# ---------------------------------------------------------------------------


def ranger_une_note_dans_un_carnet(page, dossier, utilisateur=None):
    """
    Range une note dans un carnet : cree l'appartenance, et pose la FK si
    la note n'avait pas encore de premier carnet.
    / Files a note into a notebook: creates the membership, and sets the
    FK if the note had no first notebook yet.

    LOCALISATION : core/services/corpus.py

    Idempotent : ranger deux fois dans le meme carnet ne cree qu'une
    appartenance. get_or_create absorbe aussi la course entre deux
    rangements simultanes (la contrainte unicite_page_dans_un_dossier
    tranche, le perdant recupere la ligne du gagnant).
    / Idempotent; the unique constraint settles concurrent filings.

    :return: l'appartenance (creee ou existante) / the membership row
    """
    if dossier is None:
        # Refus explicite plutot qu'un IntegrityError au fond de la
        # transaction (relecture D : dossier_id perime -> 500).
        # / Explicit refusal instead of a deep IntegrityError.
        raise ValueError(
            "ranger_une_note_dans_un_carnet exige un carnet non nul. "
            "/ A non-null notebook is required."
        )

    with transaction.atomic():
        appartenance, _creee = page.appartenances_dossiers.get_or_create(
            dossier=dossier,
            defaults={"integree_par": utilisateur},
        )

        # La FK porte le premier carnet. Elle ne bouge pas si elle est
        # deja posee. / The FK carries the first notebook; it does not
        # move if already set.
        if page.dossier_id is None:
            page.dossier = dossier
            page.save(update_fields=["dossier"])

    return appartenance


def retirer_une_note_d_un_carnet(page, dossier):
    """
    Retire une note d'un carnet. NE SUPPRIME JAMAIS LA NOTE.
    / Removes a note from a notebook. NEVER deletes the note.

    LOCALISATION : core/services/corpus.py

    Regle § 4.3 : si la FK pointait ce carnet, elle est reaffectee a une
    autre appartenance restante (la plus ancienne), ou mise a NULL s'il
    n'en reste aucune. La v1.0 de la spec ne definissait pas ce cas.
    / § 4.3 rule: the FK is reassigned to another remaining membership,
    or nulled if none remains.
    """
    with transaction.atomic():
        page.appartenances_dossiers.filter(dossier=dossier).delete()

        la_fk_pointait_ce_carnet = page.dossier_id == dossier.pk
        if la_fk_pointait_ce_carnet:
            appartenance_restante = (
                page.appartenances_dossiers.order_by("integree_le", "pk").first()
            )
            page.dossier = (
                appartenance_restante.dossier if appartenance_restante else None
            )
            page.save(update_fields=["dossier"])


def deplacer_une_note_vers_un_carnet(page, dossier_cible, utilisateur=None):
    """
    Deplace une note : elle sort du carnet que la FK designait, elle entre
    dans le carnet cible. Les AUTRES carnets de la note ne bougent pas.
    / Moves a note: it leaves the FK notebook and enters the target one.
    The note's OTHER notebooks are untouched.

    LOCALISATION : core/services/corpus.py

    C'est la semantique actuelle de classer_depuis_extension
    (core/views.py) et du deplacement par glisser-deposer (front/views.py),
    exprimee avec la table de liaison. Le multi-rangement depuis
    l'extension (cases a cocher, § 7.2) est la phase I.
    / Today's move semantics, expressed with the link table.
    """
    with transaction.atomic():
        ancien_dossier_id = page.dossier_id
        if ancien_dossier_id and ancien_dossier_id != dossier_cible.pk:
            page.appartenances_dossiers.filter(
                dossier_id=ancien_dossier_id
            ).delete()

        appartenance, _creee = page.appartenances_dossiers.get_or_create(
            dossier=dossier_cible,
            defaults={"integree_par": utilisateur},
        )
        page.dossier = dossier_cible
        page.save(update_fields=["dossier"])

    return appartenance
