"""
Services de la couche corpus : validation des categories d'appartenance.
/ Corpus layer services: membership category validation.

LOCALISATION : core/services/corpus.py

SPEC-corpus-base-carnet-note.md v1.1 § 3.4 : « la validation qui n'a pas
le droit de manquer ». Sans elle, le modele perd son sens — le vocabulaire
d'un carnet fuirait dans un autre.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _


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
