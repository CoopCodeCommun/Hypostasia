"""
Tests du service de rangement note <-> carnet (phase D).
/ Note <-> notebook filing service tests (phase D).

LOCALISATION : core/tests/test_corpus_rangement.py

SPEC-corpus § 4.3 : pendant la coexistence FK / table de liaison, la FK
Page.dossier porte le PREMIER carnet de la note, ecrite uniquement par le
service. Au retrait d'une appartenance, si la FK pointait ce carnet, elle
est reaffectee a une autre appartenance restante, ou mise a NULL s'il
n'en reste aucune.
/ During coexistence, the FK carries the note's FIRST notebook, written
only by the service. On removal, the FK is reassigned or nulled.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import AppartenancePageDossier, Dossier, Page
from core.services.corpus import (
    deplacer_une_note_vers_un_carnet,
    ranger_une_note_dans_un_carnet,
    retirer_une_note_d_un_carnet,
)

Utilisateur = get_user_model()


def creer_une_page(url_unique, owner=None, dossier=None):
    """Cree une page minimale pour les tests. / Minimal test page."""
    return Page.objects.create(
        url=url_unique,
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="texte",
        content_hash=f"hash-{url_unique}",
        owner=owner,
        dossier=dossier,
    )


class RangerUneNoteTest(TestCase):
    """Le rangement maintient FK et appartenances. / Filing keeps both in sync."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="rangeur_test", password="motdepasse"
        )
        self.carnet_un = Dossier.objects.create(
            name="Carnet un", owner=self.utilisateur
        )
        self.carnet_deux = Dossier.objects.create(
            name="Carnet deux", owner=self.utilisateur
        )

    def test_ranger_cree_l_appartenance_et_pose_la_fk(self):
        note = creer_une_page("http://exemple.local/note-a-ranger")

        ranger_une_note_dans_un_carnet(note, self.carnet_un, self.utilisateur)

        note.refresh_from_db()
        self.assertEqual(note.dossier_id, self.carnet_un.pk)
        appartenance = AppartenancePageDossier.objects.get(
            page=note, dossier=self.carnet_un
        )
        self.assertEqual(appartenance.integree_par, self.utilisateur)

    def test_ranger_dans_un_second_carnet_ne_change_pas_la_fk(self):
        # La FK porte le PREMIER carnet ; le second n'est qu'une
        # appartenance de plus. / The FK keeps the FIRST notebook.
        note = creer_une_page("http://exemple.local/note-second-carnet")
        ranger_une_note_dans_un_carnet(note, self.carnet_un, self.utilisateur)

        ranger_une_note_dans_un_carnet(note, self.carnet_deux, self.utilisateur)

        note.refresh_from_db()
        self.assertEqual(note.dossier_id, self.carnet_un.pk)
        self.assertEqual(note.appartenances_dossiers.count(), 2)

    def test_ranger_est_idempotent(self):
        # Ranger deux fois dans le meme carnet ne cree qu'une appartenance
        # et ne leve pas. / Filing twice is idempotent.
        note = creer_une_page("http://exemple.local/note-idempotente")
        ranger_une_note_dans_un_carnet(note, self.carnet_un, self.utilisateur)
        ranger_une_note_dans_un_carnet(note, self.carnet_un, self.utilisateur)

        self.assertEqual(note.appartenances_dossiers.count(), 1)

    def test_ranger_sans_carnet_est_refuse_proprement(self):
        # Relecture D : un dossier_id perime (supprime dans un autre
        # onglet) donnait un IntegrityError -> 500 apres creation de la
        # page. Le service doit refuser None avec une erreur explicite.
        # / A stale dossier must be refused with an explicit error, not
        # an IntegrityError deep in the transaction.
        note = creer_une_page("http://exemple.local/note-sans-cible")
        with self.assertRaises(ValueError):
            ranger_une_note_dans_un_carnet(note, None, self.utilisateur)

    def test_ranger_repare_une_fk_posee_sans_appartenance(self):
        # Cas de coexistence : une page creee par un ancien chemin avec la
        # FK seule. Ranger dans le MEME carnet cree l'appartenance
        # manquante sans doublon.
        # / Coexistence: FK-only page gets its missing membership.
        note = creer_une_page(
            "http://exemple.local/note-fk-seule", dossier=self.carnet_un,
        )
        ranger_une_note_dans_un_carnet(note, self.carnet_un, self.utilisateur)

        self.assertEqual(note.appartenances_dossiers.count(), 1)
        note.refresh_from_db()
        self.assertEqual(note.dossier_id, self.carnet_un.pk)


class RetirerUneNoteTest(TestCase):
    """Le retrait reaffecte la FK (§ 4.3). / Removal reassigns the FK."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="retireur_test", password="motdepasse"
        )
        self.carnet_un = Dossier.objects.create(
            name="Carnet un", owner=self.utilisateur
        )
        self.carnet_deux = Dossier.objects.create(
            name="Carnet deux", owner=self.utilisateur
        )
        self.note = creer_une_page("http://exemple.local/note-a-retirer")
        ranger_une_note_dans_un_carnet(
            self.note, self.carnet_un, self.utilisateur
        )
        ranger_une_note_dans_un_carnet(
            self.note, self.carnet_deux, self.utilisateur
        )

    def test_retirer_le_carnet_de_la_fk_reaffecte_la_fk(self):
        retirer_une_note_d_un_carnet(self.note, self.carnet_un)

        self.note.refresh_from_db()
        self.assertEqual(self.note.dossier_id, self.carnet_deux.pk)
        self.assertEqual(self.note.appartenances_dossiers.count(), 1)

    def test_retirer_un_autre_carnet_ne_touche_pas_la_fk(self):
        retirer_une_note_d_un_carnet(self.note, self.carnet_deux)

        self.note.refresh_from_db()
        self.assertEqual(self.note.dossier_id, self.carnet_un.pk)

    def test_retirer_la_derniere_appartenance_met_la_fk_a_null(self):
        retirer_une_note_d_un_carnet(self.note, self.carnet_un)
        retirer_une_note_d_un_carnet(self.note, self.carnet_deux)

        self.note.refresh_from_db()
        self.assertIsNone(self.note.dossier_id)
        self.assertEqual(self.note.appartenances_dossiers.count(), 0)
        # La note existe toujours : retirer n'est JAMAIS supprimer (§ 9).
        # / The note still exists: removing is NEVER deleting.
        self.assertTrue(Page.objects.filter(pk=self.note.pk).exists())

    def test_retirer_un_carnet_absent_est_sans_effet(self):
        carnet_etranger = Dossier.objects.create(
            name="Jamais utilisé", owner=self.utilisateur
        )
        retirer_une_note_d_un_carnet(self.note, carnet_etranger)

        self.note.refresh_from_db()
        self.assertEqual(self.note.appartenances_dossiers.count(), 2)
        self.assertEqual(self.note.dossier_id, self.carnet_un.pk)


class SuppressionDeCarnetTest(TestCase):
    """
    La suppression d'un carnet — par la vue, l'admin ou une cascade —
    reaffecte la FK des notes multi-carnets (relecture D).
    / Deleting a notebook — via the view, the admin or a cascade —
    reassigns multi-notebook notes' FK.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="supprimeur_test", password="motdepasse"
        )
        self.carnet_condamne = Dossier.objects.create(
            name="Carnet condamné", owner=self.utilisateur
        )
        self.carnet_survivant = Dossier.objects.create(
            name="Carnet survivant", owner=self.utilisateur
        )

    def test_supprimer_le_carnet_reaffecte_la_fk_des_notes_multi_carnets(self):
        # dossier.delete() DIRECT (pas la vue) : le signal doit reaffecter
        # la FK, sinon le SET_NULL brut casserait l'invariant « FK =
        # premier carnet ». / Direct delete: the signal must reassign.
        note = creer_une_page("http://exemple.local/note-survivante")
        ranger_une_note_dans_un_carnet(note, self.carnet_condamne, self.utilisateur)
        ranger_une_note_dans_un_carnet(note, self.carnet_survivant, self.utilisateur)

        self.carnet_condamne.delete()

        note.refresh_from_db()
        self.assertEqual(note.dossier_id, self.carnet_survivant.pk)
        self.assertEqual(note.appartenances_dossiers.count(), 1)

    def test_supprimer_le_dernier_carnet_rend_la_note_orpheline(self):
        note = creer_une_page("http://exemple.local/note-bientot-orpheline")
        ranger_une_note_dans_un_carnet(note, self.carnet_condamne, self.utilisateur)

        self.carnet_condamne.delete()

        note.refresh_from_db()
        self.assertIsNone(note.dossier_id)
        # La note existe toujours. / The note still exists.
        self.assertTrue(Page.objects.filter(pk=note.pk).exists())


class DeplacerUneNoteTest(TestCase):
    """
    Le deplacement : sortir d'un carnet, entrer dans un autre. C'est la
    semantique actuelle de classer_depuis_extension et du deplacement par
    glisser-deposer, exprimee avec le service.
    / Moving: leave one notebook, enter another — today's semantics.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="deplaceur_test", password="motdepasse"
        )
        self.carnet_origine = Dossier.objects.create(
            name="Origine", owner=self.utilisateur
        )
        self.carnet_cible = Dossier.objects.create(
            name="Cible", owner=self.utilisateur
        )

    def test_deplacer_sort_de_l_origine_et_entre_dans_la_cible(self):
        note = creer_une_page("http://exemple.local/note-a-deplacer")
        ranger_une_note_dans_un_carnet(
            note, self.carnet_origine, self.utilisateur
        )

        deplacer_une_note_vers_un_carnet(
            note, self.carnet_cible, self.utilisateur
        )

        note.refresh_from_db()
        self.assertEqual(note.dossier_id, self.carnet_cible.pk)
        carnets_de_la_note = list(
            note.appartenances_dossiers.values_list("dossier_id", flat=True)
        )
        self.assertEqual(carnets_de_la_note, [self.carnet_cible.pk])

    def test_deplacer_ne_touche_pas_les_autres_carnets(self):
        # Une note aussi rangee ailleurs y RESTE : le deplacement ne
        # concerne que le carnet que la FK designait.
        # / Other notebooks keep the note: the move only concerns the
        # FK notebook.
        autre_carnet = Dossier.objects.create(
            name="Autre", owner=self.utilisateur
        )
        note = creer_une_page("http://exemple.local/note-multi-deplacee")
        ranger_une_note_dans_un_carnet(
            note, self.carnet_origine, self.utilisateur
        )
        ranger_une_note_dans_un_carnet(note, autre_carnet, self.utilisateur)

        deplacer_une_note_vers_un_carnet(
            note, self.carnet_cible, self.utilisateur
        )

        note.refresh_from_db()
        self.assertEqual(note.dossier_id, self.carnet_cible.pk)
        carnets_de_la_note = set(
            note.appartenances_dossiers.values_list("dossier_id", flat=True)
        )
        self.assertEqual(
            carnets_de_la_note, {self.carnet_cible.pk, autre_carnet.pk}
        )

    def test_deplacer_une_note_sans_carnet_revient_a_ranger(self):
        note = creer_une_page("http://exemple.local/note-sans-carnet-deplacee")

        deplacer_une_note_vers_un_carnet(
            note, self.carnet_cible, self.utilisateur
        )

        note.refresh_from_db()
        self.assertEqual(note.dossier_id, self.carnet_cible.pk)
        self.assertEqual(note.appartenances_dossiers.count(), 1)
