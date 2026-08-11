"""
Tests des permissions de la couche corpus (phase C).
/ Corpus layer permission tests (phase C).

LOCALISATION : core/tests/test_corpus_permissions.py

SPEC-corpus-base-carnet-note.md v1.1 § 5 : l'acces a une note se derive de
ses carnets — le plus permissif gagne. La propriete s'ELARGIT (owner de la
note OU owner d'un carnet la contenant), elle ne se deplace pas. Le
comportement legacy (note sans carnet, sans owner → tout authentifie) est
preserve.
/ Access derives from the note's notebooks — most permissive wins.
Ownership widens, never moves. Legacy behaviour preserved.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from core.models import (
    AppartenancePageDossier,
    Dossier,
    DossierPartage,
    GroupeUtilisateurs,
    Page,
    VisibiliteDossier,
)
from front.views import (
    _est_proprietaire_page,
    _utilisateur_a_acces_page,
    _utilisateur_peut_ecrire_page,
)

Utilisateur = get_user_model()


def creer_une_page(url_unique, owner=None):
    """Cree une page minimale pour les tests. / Minimal test page."""
    return Page.objects.create(
        url=url_unique,
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="texte",
        content_hash=f"hash-{url_unique}",
        owner=owner,
    )


class AccesParLeCarnetTest(TestCase):
    """La lecture se derive des carnets. / Reading derives from notebooks."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprietaire_perm_test", password="motdepasse"
        )
        self.visiteur = Utilisateur.objects.create_user(
            username="visiteur_perm_test", password="motdepasse"
        )
        self.anonyme = AnonymousUser()

    def test_acces_par_le_carnet_le_plus_permissif(self):
        # Une note dans un carnet prive ET un carnet public est lisible :
        # le plus permissif gagne. C'est voulu, et l'interface doit le dire
        # au moment du rangement (spec § 7.3).
        # / Private + public → readable: most permissive wins.
        carnet_prive = Dossier.objects.create(
            name="Privé", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        carnet_public = Dossier.objects.create(
            name="Public", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        note = creer_une_page("http://exemple.local/note-deux-carnets")
        AppartenancePageDossier.objects.create(page=note, dossier=carnet_prive)
        AppartenancePageDossier.objects.create(page=note, dossier=carnet_public)

        self.assertTrue(_utilisateur_a_acces_page(self.visiteur, note))

    def test_anonyme_accede_a_une_note_de_carnet_public(self):
        # Le cas que IsAuthenticated cassait en v1.0 de la spec (§ 9).
        # / The case IsAuthenticated broke in spec v1.0.
        carnet_public = Dossier.objects.create(
            name="Public", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        note = creer_une_page("http://exemple.local/note-publique")
        AppartenancePageDossier.objects.create(page=note, dossier=carnet_public)

        self.assertTrue(_utilisateur_a_acces_page(self.anonyme, note))

    def test_note_de_carnet_prive_refusee_aux_autres(self):
        carnet_prive = Dossier.objects.create(
            name="Privé", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        note = creer_une_page("http://exemple.local/note-privee")
        AppartenancePageDossier.objects.create(page=note, dossier=carnet_prive)

        self.assertFalse(_utilisateur_a_acces_page(self.visiteur, note))
        self.assertFalse(_utilisateur_a_acces_page(self.anonyme, note))
        self.assertTrue(_utilisateur_a_acces_page(self.proprietaire, note))

    def test_note_sans_carnet_sans_owner_reste_accessible_a_tout_authentifie(self):
        # Comportement legacy preserve (spec § 5.2, correction n°6 : la
        # v1.0 rendait ces notes invisibles pour tous).
        # / Legacy behaviour preserved: any authenticated user.
        note_orpheline = creer_une_page("http://exemple.local/note-orpheline")

        self.assertTrue(_utilisateur_a_acces_page(self.visiteur, note_orpheline))
        self.assertFalse(_utilisateur_a_acces_page(self.anonyme, note_orpheline))

    def test_note_sans_carnet_avec_owner_reservee_a_son_owner(self):
        note_personnelle = creer_une_page(
            "http://exemple.local/note-personnelle", owner=self.proprietaire,
        )

        self.assertTrue(
            _utilisateur_a_acces_page(self.proprietaire, note_personnelle)
        )
        self.assertFalse(
            _utilisateur_a_acces_page(self.visiteur, note_personnelle)
        )

    def test_le_fallback_owner_ne_joue_que_sans_aucun_carnet(self):
        # LE CAS-PIEGE CENTRAL (relecture C) : une note dont JE suis
        # l'owner mais rangee uniquement dans le carnet prive d'autrui
        # m'est REFUSEE en lecture. Les carnets decident ; le fallback
        # owner n'existe que pour une note sans aucun carnet.
        # / THE central trap: my note filed only in someone else's private
        # notebook is refused to me. Notebooks decide.
        carnet_prive_d_autrui = Dossier.objects.create(
            name="Privé d'autrui", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        ma_note = creer_une_page(
            "http://exemple.local/ma-note-chez-autrui", owner=self.visiteur,
        )
        AppartenancePageDossier.objects.create(
            page=ma_note, dossier=carnet_prive_d_autrui,
        )

        self.assertFalse(_utilisateur_a_acces_page(self.visiteur, ma_note))

    def test_acces_par_partage_direct(self):
        # La moitie DossierPartage du flux, exercee au niveau page.
        # / The DossierPartage half of the flow, at page level.
        carnet_partage = Dossier.objects.create(
            name="Partagé", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PARTAGE,
        )
        DossierPartage.objects.create(
            dossier=carnet_partage, utilisateur=self.visiteur,
        )
        note = creer_une_page("http://exemple.local/note-partagee")
        AppartenancePageDossier.objects.create(
            page=note, dossier=carnet_partage,
        )

        self.assertTrue(_utilisateur_a_acces_page(self.visiteur, note))
        self.assertTrue(_utilisateur_peut_ecrire_page(self.visiteur, note))

    def test_acces_par_partage_de_groupe(self):
        carnet_partage = Dossier.objects.create(
            name="Partagé au groupe", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PARTAGE,
        )
        groupe = GroupeUtilisateurs.objects.create(
            nom="Groupe de test", owner=self.proprietaire,
        )
        groupe.membres.add(self.visiteur)
        DossierPartage.objects.create(dossier=carnet_partage, groupe=groupe)
        note = creer_une_page("http://exemple.local/note-groupe")
        AppartenancePageDossier.objects.create(
            page=note, dossier=carnet_partage,
        )

        self.assertTrue(_utilisateur_a_acces_page(self.visiteur, note))

    def test_liste_prechargee_vide_ne_declenche_pas_de_requete_carnets(self):
        # dossiers_precharges=[] (liste vide) n'est PAS None : l'appelant
        # a precharge et sait qu'il n'y a aucun carnet — on ne re-requete
        # pas les appartenances.
        # / An empty prefetched list is not None: no membership re-query.
        note_orpheline = creer_une_page(
            "http://exemple.local/note-orpheline-prefetch"
        )
        with self.assertNumQueries(0):
            acces = _utilisateur_a_acces_page(
                self.visiteur, note_orpheline, dossiers_precharges=[],
            )
        self.assertTrue(acces)

    def test_pas_de_n_plus_un_sur_la_liste(self):
        # Avec les carnets precharges, la verification d'acces d'une note
        # de carnet public ne fait AUCUNE requete. C'est le contrat qui
        # rend les listes possibles (spec § 5.3).
        # / With prefetched notebooks, zero queries for a public-notebook
        # note.
        carnet_public = Dossier.objects.create(
            name="Public", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        note = creer_une_page("http://exemple.local/note-prefetch")
        AppartenancePageDossier.objects.create(page=note, dossier=carnet_public)

        dossiers_precharges = list(
            Dossier.objects.filter(appartenances_pages__page=note)
        )
        with self.assertNumQueries(0):
            acces = _utilisateur_a_acces_page(
                self.visiteur, note, dossiers_precharges=dossiers_precharges,
            )
        self.assertTrue(acces)


class EcritureEtProprieteTest(TestCase):
    """Ecrire et moderer. / Writing and moderating."""

    def setUp(self):
        self.professeur = Utilisateur.objects.create_user(
            username="professeur_test", password="motdepasse"
        )
        self.eleve = Utilisateur.objects.create_user(
            username="eleve_test", password="motdepasse"
        )
        self.visiteur = Utilisateur.objects.create_user(
            username="visiteur_ecriture_test", password="motdepasse"
        )
        # Le carnet de classe appartient au professeur ; l'eleve y depose
        # une capture dont il est owner (l'extension renseigne toujours
        # owner — core/views.py:229).
        # / Class notebook owned by the teacher; the pupil files a capture
        # they own.
        self.carnet_de_classe = Dossier.objects.create(
            name="Vie lycéenne", owner=self.professeur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.capture_de_l_eleve = creer_une_page(
            "http://exemple.local/capture-eleve", owner=self.eleve,
        )
        AppartenancePageDossier.objects.create(
            page=self.capture_de_l_eleve, dossier=self.carnet_de_classe,
        )

    def test_proprietaire_de_carnet_garde_la_moderation(self):
        # LE CAS QUE LA v1.0 CASSAIT (spec § 0, correction n°5) : le prof
        # doit pouvoir moderer la capture d'un eleve, meme si page.owner
        # est l'eleve.
        # / The teacher keeps moderation over a pupil's capture.
        self.assertTrue(
            _est_proprietaire_page(self.professeur, self.capture_de_l_eleve)
        )

    def test_auteur_de_la_note_est_aussi_proprietaire(self):
        # On elargit, on ne deplace pas : l'eleve garde ses droits.
        # / Ownership widens: the pupil keeps their rights.
        self.assertTrue(
            _est_proprietaire_page(self.eleve, self.capture_de_l_eleve)
        )

    def test_un_tiers_n_est_pas_proprietaire(self):
        self.assertFalse(
            _est_proprietaire_page(self.visiteur, self.capture_de_l_eleve)
        )

    def test_ecriture_exige_un_carnet_inscriptible(self):
        # Un carnet public est LISIBLE par tous mais inscriptible seulement
        # par son owner et ses invites. Lecture publique != ecriture.
        # / Public read is not write.
        self.assertTrue(
            _utilisateur_a_acces_page(self.visiteur, self.capture_de_l_eleve)
        )
        self.assertFalse(
            _utilisateur_peut_ecrire_page(self.visiteur, self.capture_de_l_eleve)
        )
        self.assertTrue(
            _utilisateur_peut_ecrire_page(
                self.professeur, self.capture_de_l_eleve
            )
        )

    def test_anonyme_n_ecrit_jamais(self):
        self.assertFalse(
            _utilisateur_peut_ecrire_page(
                AnonymousUser(), self.capture_de_l_eleve
            )
        )

    def test_superuser_ne_gagne_pas_l_ecriture_par_magie(self):
        # Conformite stricte au § 5.2 (relecture C) : le code prescrit n'a
        # AUCUN bypass superuser en ecriture, et l'existant non plus
        # (_utilisateur_peut_ecrire_dossier n'en a pas). Un superuser
        # non-owner, non-partage, n'ecrit pas.
        # / Strict § 5.2 conformity: no superuser bypass on write.
        superuser = Utilisateur.objects.create_superuser(
            username="superuser_test", password="motdepasse"
        )
        carnet_prive = Dossier.objects.create(
            name="Privé strict", owner=self.professeur,
            visibilite=VisibiliteDossier.PRIVE,
        )
        note = creer_une_page("http://exemple.local/note-superuser")
        AppartenancePageDossier.objects.create(page=note, dossier=carnet_prive)

        # Lecture : oui, le bypass lecture est prescrit par la spec.
        # / Read: yes, the read bypass IS prescribed.
        self.assertTrue(_utilisateur_a_acces_page(superuser, note))
        # Ecriture : non. / Write: no.
        self.assertFalse(_utilisateur_peut_ecrire_page(superuser, note))

    def test_ecriture_sans_carnet_retombe_sur_le_proprietaire(self):
        # Une note sans carnet avec owner : seul son owner ecrit.
        # / No notebook, with owner: only the note's owner writes.
        note_isolee = creer_une_page(
            "http://exemple.local/note-isolee-ecriture", owner=self.eleve,
        )
        self.assertTrue(_utilisateur_peut_ecrire_page(self.eleve, note_isolee))
        self.assertFalse(
            _utilisateur_peut_ecrire_page(self.visiteur, note_isolee)
        )

    def test_ecriture_orpheline_sans_owner_reste_ouverte_a_tout_authentifie(self):
        # DECISION phase D (point 1 de la relecture C) : le comportement
        # actuel est preserve. Aujourd'hui les vues ne verifient l'ecriture
        # que si page.dossier existe — une orpheline owner=None est donc
        # inscriptible par tout authentifie. On garde cette regle, par
        # symetrie exacte avec la lecture legacy (§ 5.2) et avec
        # _utilisateur_peut_ecrire_dossier (owner=None → tout authentifie).
        # / DECISION: current behaviour preserved — ownerless, notebook-less
        # notes stay writable by any authenticated user.
        note_orpheline = creer_une_page(
            "http://exemple.local/note-orpheline-ecriture-legacy"
        )
        self.assertTrue(
            _utilisateur_peut_ecrire_page(self.visiteur, note_orpheline)
        )
        self.assertFalse(
            _utilisateur_peut_ecrire_page(AnonymousUser(), note_orpheline)
        )
