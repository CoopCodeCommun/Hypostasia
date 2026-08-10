"""
Tests du modele de la couche synthese (phase A).
/ Synthesis layer model tests (phase A).

LOCALISATION : core/tests/test_synthese_modele.py

SPEC-synthese-carnet.md § 2-3 : le type de note decide de l'eligibilite
comme SOURCE. Une synthese n'est JAMAIS source d'une autre synthese —
sans cette exclusion mecanique, le wiki finirait par se citer lui-meme.
/ The note type decides source eligibility; a synthesis is never a source.
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from core.models import (
    CategorieDossier, Dossier, ListeDeCategories, Page, TypeDeNote,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from core.services.synthese import notes_sources_du_carnet

Utilisateur = get_user_model()


def creer_une_page(url_unique, **champs):
    """Cree une page minimale pour les tests. / Minimal test page."""
    return Page.objects.create(
        url=url_unique,
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="texte",
        content_hash=f"hash-{url_unique}",
        title=f"Note {url_unique[-10:]}",
        **champs,
    )


class TypeDeNoteTest(TestCase):
    """Le champ type_de_note. / The type_de_note field."""

    def test_le_type_par_defaut_est_note(self):
        note = creer_une_page("http://exemple.local/sa-defaut")
        self.assertEqual(note.type_de_note, TypeDeNote.NOTE)

    def test_les_trois_genres_existent(self):
        self.assertEqual(TypeDeNote.NOTE, "note")
        self.assertEqual(TypeDeNote.WIKI, "wiki")
        self.assertEqual(TypeDeNote.SYNTHESE, "synthese")


class NotesSourcesDuCarnetTest(TestCase):
    """
    Le garde-fou § 3.3 : le perimetre d'une synthese ne contient JAMAIS
    une synthese ni un wiki. Le test EXERCE la regle (spec : « pas
    verifier qu'une phrase est affichee »).
    / § 3.3 guard: a synthesis scope never contains a synthesis or wiki.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="synthetiseur_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet synthèse A", owner=self.proprietaire,
        )

    def test_une_synthese_n_est_jamais_source(self):
        # N notes ordinaires + M syntheses/wikis -> perimetre = N.
        # / N plain notes + M syntheses/wikis -> scope = N.
        for numero in range(3):
            note = creer_une_page(f"http://exemple.local/sa-note-{numero}")
            ranger_une_note_dans_un_carnet(note, self.carnet, self.proprietaire)

        wiki = creer_une_page(
            "http://exemple.local/sa-wiki", type_de_note=TypeDeNote.WIKI,
        )
        synthese = creer_une_page(
            "http://exemple.local/sa-synthese",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        ranger_une_note_dans_un_carnet(wiki, self.carnet, self.proprietaire)
        ranger_une_note_dans_un_carnet(synthese, self.carnet, self.proprietaire)

        sources = notes_sources_du_carnet(self.carnet)

        self.assertEqual(sources.count(), 3)
        self.assertNotIn(wiki.pk, [page.pk for page in sources])
        self.assertNotIn(synthese.pk, [page.pk for page in sources])

    def test_une_note_dans_deux_carnets_compte_une_fois(self):
        autre_carnet = Dossier.objects.create(
            name="Autre carnet A", owner=self.proprietaire,
        )
        note = creer_une_page("http://exemple.local/sa-double")
        ranger_une_note_dans_un_carnet(note, self.carnet, self.proprietaire)
        ranger_une_note_dans_un_carnet(note, autre_carnet, self.proprietaire)

        self.assertEqual(notes_sources_du_carnet(self.carnet).count(), 1)

    def test_les_notes_filtrees_du_corpus_excluent_les_syntheses(self):
        # Dependance C.6 de la phase F corpus : le filtre passe du
        # versionnage (parent_page) au TYPE — comme estUneSource() de
        # l'etalon. / Corpus filters switch from parent_page to the type.
        from front.views_corpus import _appartenances_filtrees_par_facettes

        note = creer_une_page("http://exemple.local/sa-filtre-note")
        synthese = creer_une_page(
            "http://exemple.local/sa-filtre-synthese",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        ranger_une_note_dans_un_carnet(note, self.carnet, self.proprietaire)
        ranger_une_note_dans_un_carnet(synthese, self.carnet, self.proprietaire)

        appartenances = list(
            _appartenances_filtrees_par_facettes(self.carnet, [])
        )
        pages_listees = [a.page_id for a in appartenances]
        self.assertIn(note.pk, pages_listees)
        self.assertNotIn(synthese.pk, pages_listees)


# =============================================================================
# PHASE C — les deux genres : Wiki (vivant) et SyntheseDirigee (acte date)
# / PHASE C — the two kinds: living Wiki and dated frozen synthesis.
# =============================================================================


class GenresDeSyntheseTest(TestCase):
    """
    SPEC-synthese § 3.1-3.2 : le wiki recalcule son perimetre, la
    synthese dirigee le fige. Les tests EXERCENT la difference.
    / § 3.1-3.2: the wiki recomputes its scope, the frozen synthesis
    never does. The tests exercise the difference.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="genres_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet genres C", owner=self.proprietaire,
        )
        self.premiere_note = creer_une_page("http://exemple.local/sc-note-1")
        self.seconde_note = creer_une_page("http://exemple.local/sc-note-2")
        ranger_une_note_dans_un_carnet(
            self.premiere_note, self.carnet, self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            self.seconde_note, self.carnet, self.proprietaire,
        )

    def test_une_synthese_est_une_note_du_carnet(self):
        # § 2 : la synthese est rattachee par une appartenance ORDINAIRE,
        # et les categories du carnet s'y appliquent comme a toute note.
        # / § 2: an ordinary membership, notebook categories apply.
        from core.models import SyntheseDirigee

        page_de_synthese = creer_une_page(
            "http://exemple.local/sc-synthese",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        appartenance = ranger_une_note_dans_un_carnet(
            page_de_synthese, self.carnet, self.proprietaire,
        )
        axe = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )
        categorie = CategorieDossier.objects.create(
            liste=axe, nom="Synthèse de conseil",
        )
        appartenance.categories.add(categorie)

        SyntheseDirigee.objects.create(
            page=page_de_synthese,
            dossier=self.carnet,
            produite_par=self.proprietaire,
        )

        self.assertEqual(
            page_de_synthese.appartenances_dossiers.get().categories.get().pk,
            categorie.pk,
        )
        self.assertEqual(
            page_de_synthese.synthese_dirigee.dossier_id, self.carnet.pk,
        )

    def test_le_perimetre_d_une_dirigee_est_fige(self):
        # § 3.2 : ajouter une note au carnet ne change pas
        # notes_du_perimetre. / Adding a note never changes the scope.
        from core.models import SyntheseDirigee

        page_de_synthese = creer_une_page(
            "http://exemple.local/sc-dirigee",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        dirigee = SyntheseDirigee.objects.create(
            page=page_de_synthese, dossier=self.carnet,
            produite_par=self.proprietaire,
        )
        dirigee.notes_du_perimetre.set([self.premiere_note, self.seconde_note])

        note_arrivee_apres = creer_une_page("http://exemple.local/sc-apres")
        ranger_une_note_dans_un_carnet(
            note_arrivee_apres, self.carnet, self.proprietaire,
        )

        self.assertEqual(dirigee.notes_du_perimetre.count(), 2)
        self.assertNotIn(
            note_arrivee_apres.pk,
            [page.pk for page in dirigee.notes_du_perimetre.all()],
        )

    def test_un_wiki_recalcule_son_perimetre(self):
        # § 3.1.1 : une note ajoutee au carnet ENTRE dans le perimetre du
        # wiki au calcul suivant. / A new note enters the wiki's scope.
        from core.models import Wiki
        from core.services.synthese import notes_du_perimetre_d_un_wiki

        page_d_article = creer_une_page(
            "http://exemple.local/sc-wiki", type_de_note=TypeDeNote.WIKI,
        )
        wiki = Wiki.objects.create(
            page=page_d_article, dossier=self.carnet,
            sujet="Le seuil de passage en assemblée",
        )

        self.assertEqual(notes_du_perimetre_d_un_wiki(wiki).count(), 2)

        note_arrivee_apres = creer_une_page("http://exemple.local/sc-neuve")
        ranger_une_note_dans_un_carnet(
            note_arrivee_apres, self.carnet, self.proprietaire,
        )

        self.assertEqual(notes_du_perimetre_d_un_wiki(wiki).count(), 3)

    def test_le_perimetre_d_un_wiki_exclut_les_syntheses(self):
        # Le garde-fou § 3.3 s'applique AUSSI au wiki sans categorie
        # (perimetre = tout le carnet). / § 3.3 also guards the wiki.
        from core.models import Wiki
        from core.services.synthese import notes_du_perimetre_d_un_wiki

        autre_synthese = creer_une_page(
            "http://exemple.local/sc-autre-synthese",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        ranger_une_note_dans_un_carnet(
            autre_synthese, self.carnet, self.proprietaire,
        )
        page_d_article = creer_une_page(
            "http://exemple.local/sc-wiki-garde",
            type_de_note=TypeDeNote.WIKI,
        )
        wiki = Wiki.objects.create(
            page=page_d_article, dossier=self.carnet, sujet="Gouvernance",
        )

        perimetre = notes_du_perimetre_d_un_wiki(wiki)

        self.assertEqual(perimetre.count(), 2)
        self.assertNotIn(
            autre_synthese.pk, [page.pk for page in perimetre],
        )

    def test_le_perimetre_d_un_wiki_filtre_par_facettes(self):
        # § 3.1.1 : OU dans un axe, ET entre les axes (spec corpus § 8.2).
        # Les categories se lisent sur l'appartenance A CE CARNET.
        # / OR within an axis, AND across axes, read on the membership.
        from core.models import Wiki
        from core.services.synthese import notes_du_perimetre_d_un_wiki

        axe_type = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )
        axe_theme = ListeDeCategories.objects.create(
            nom="Thème", dossier=self.carnet,
        )
        categorie_cr = CategorieDossier.objects.create(
            liste=axe_type, nom="Compte rendu",
        )
        categorie_rapport = CategorieDossier.objects.create(
            liste=axe_type, nom="Rapport",
        )
        categorie_budget = CategorieDossier.objects.create(
            liste=axe_theme, nom="Budget",
        )

        # premiere_note : Compte rendu + Budget -> retenue.
        # seconde_note : Rapport seul (pas Budget) -> exclue par le ET.
        # troisieme_note : sans categorie -> exclue.
        # / note 1 kept; note 2 fails the AND; note 3 uncategorized.
        appartenance_premiere = self.premiere_note.appartenances_dossiers.get(
            dossier=self.carnet,
        )
        appartenance_premiere.categories.add(categorie_cr, categorie_budget)
        appartenance_seconde = self.seconde_note.appartenances_dossiers.get(
            dossier=self.carnet,
        )
        appartenance_seconde.categories.add(categorie_rapport)
        troisieme_note = creer_une_page("http://exemple.local/sc-note-3")
        ranger_une_note_dans_un_carnet(
            troisieme_note, self.carnet, self.proprietaire,
        )

        page_d_article = creer_une_page(
            "http://exemple.local/sc-wiki-facettes",
            type_de_note=TypeDeNote.WIKI,
        )
        wiki = Wiki.objects.create(
            page=page_d_article, dossier=self.carnet, sujet="Budget",
        )
        wiki.categories_du_perimetre.set(
            [categorie_cr, categorie_rapport, categorie_budget],
        )

        perimetre = notes_du_perimetre_d_un_wiki(wiki)

        self.assertEqual(
            [page.pk for page in perimetre], [self.premiere_note.pk],
        )

    def test_la_dirigee_survit_a_la_suppression_de_son_carnet(self):
        # Ecart assume vs spec § 3.2 (CASCADE) : l'acte date et son
        # perimetre fige SURVIVENT au carnet — la preuve d'une adoption ne
        # disparait pas avec le rangement. Consigne en addendum.
        # / The dated act survives notebook deletion (documented deviation).
        from core.models import SyntheseDirigee

        page_de_synthese = creer_une_page(
            "http://exemple.local/sc-survit",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        dirigee = SyntheseDirigee.objects.create(
            page=page_de_synthese, dossier=self.carnet,
            produite_par=self.proprietaire,
        )
        dirigee.notes_du_perimetre.set([self.premiere_note])

        self.carnet.delete()

        dirigee.refresh_from_db()
        self.assertIsNone(dirigee.dossier)
        self.assertEqual(dirigee.notes_du_perimetre.count(), 1)


ETAT_AVANT_TYPE = [("core", "0046_page_type_de_note")]
ETAT_APRES_TYPE = [("core", "0047_typer_les_syntheses_existantes")]


class MigrationDesSynthesesExistantesTest(TransactionTestCase):
    """
    La migration § 2.1 : les Pages issues d'une synthese passent en
    SYNTHESE. Critere : ExtractionJob.raw_result porte est_synthese et
    page_synthese_id ; repli : parent_page non nul (seule ecriture en
    production). / Existing synthesis pages get typed.
    """

    def _migrer_vers(self, cibles):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(cibles)
        return executor.loader.project_state(cibles).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_les_versions_existantes_passent_en_synthese(self):
        apps_avant = self._migrer_vers(ETAT_AVANT_TYPE)
        PageHistorique = apps_avant.get_model("core", "Page")

        racine = PageHistorique.objects.create(
            url="http://exemple.local/sa-mig-racine",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-sa-mig-1",
        )
        version_synthese = PageHistorique.objects.create(
            url=None,
            html_original="<p>s</p>", html_readability="<p>s</p>",
            text_readability="synthese", content_hash="hash-sa-mig-2",
            parent_page_id=racine.pk, version_number=2,
        )

        apps_apres = self._migrer_vers(ETAT_APRES_TYPE)
        Page_apres = apps_apres.get_model("core", "Page")

        self.assertEqual(
            Page_apres.objects.get(pk=version_synthese.pk).type_de_note,
            "synthese",
        )
        # La racine reste une note ordinaire. / The root stays a note.
        self.assertEqual(
            Page_apres.objects.get(pk=racine.pk).type_de_note, "note",
        )


ETAT_AVANT_ESTAMPILLAGE = [("core", "0049_wiki_et_synthese_dirigee")]
ETAT_APRES_ESTAMPILLAGE = [
    ("core", "0050_estampiller_les_syntheses_dirigees_existantes"),
]


class MigrationEstampillageDirigeesTest(TransactionTestCase):
    """
    La migration phase C (§ 13) : chaque page deja typee SYNTHESE recoit
    son enregistrement SyntheseDirigee — produite_le = created_at,
    perimetre fige = la racine dont elle etait la version.
    / Every SYNTHESE-typed page gets its SyntheseDirigee record.
    """

    def _migrer_vers(self, cibles):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(cibles)
        return executor.loader.project_state(cibles).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_les_syntheses_typees_recoivent_leur_enregistrement(self):
        apps_avant = self._migrer_vers(ETAT_AVANT_ESTAMPILLAGE)
        PageHistorique = apps_avant.get_model("core", "Page")
        DossierHistorique = apps_avant.get_model("core", "Dossier")

        carnet = DossierHistorique.objects.create(name="Carnet estampillage")
        racine = PageHistorique.objects.create(
            url="http://exemple.local/sc-est-racine",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-sc-est-1",
            dossier_id=carnet.pk,
        )
        version_synthese = PageHistorique.objects.create(
            url=None,
            html_original="<p>s</p>", html_readability="<p>s</p>",
            text_readability="synthese", content_hash="hash-sc-est-2",
            parent_page_id=racine.pk, version_number=2,
            type_de_note="synthese", dossier_id=carnet.pk,
        )
        note_ordinaire = PageHistorique.objects.create(
            url="http://exemple.local/sc-est-note",
            html_original="<p>n</p>", html_readability="<p>n</p>",
            text_readability="note", content_hash="hash-sc-est-3",
        )

        apps_apres = self._migrer_vers(ETAT_APRES_ESTAMPILLAGE)
        SyntheseDirigeeApres = apps_apres.get_model("core", "SyntheseDirigee")

        enregistrement = SyntheseDirigeeApres.objects.get(
            page_id=version_synthese.pk,
        )
        self.assertEqual(enregistrement.produite_le, version_synthese.created_at)
        self.assertEqual(enregistrement.dossier_id, carnet.pk)
        # Le perimetre historique : la note dont elle etait la version.
        # / The historical scope: the root note it versioned.
        self.assertEqual(
            [page.pk for page in enregistrement.notes_du_perimetre.all()],
            [racine.pk],
        )
        # Une note ordinaire ne recoit rien. / Plain notes get nothing.
        self.assertFalse(
            SyntheseDirigeeApres.objects.filter(
                page_id=note_ordinaire.pk,
            ).exists()
        )

    def test_la_migration_est_reversible_sans_toucher_le_reste(self):
        # Le rollback ne supprime que ce que la migration a cree : une
        # dirigee nee de l'application (page SANS parent_page, phase C)
        # SURVIT (relecture C, M1). / Rollback deletes only what the
        # migration created; app-born records survive.
        apps_avant = self._migrer_vers(ETAT_AVANT_ESTAMPILLAGE)
        PageHistorique = apps_avant.get_model("core", "Page")
        racine = PageHistorique.objects.create(
            url="http://exemple.local/sc-rev-racine",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-sc-rev-0",
        )
        version_synthese = PageHistorique.objects.create(
            url=None,
            html_original="<p>s</p>", html_readability="<p>s</p>",
            text_readability="synthese", content_hash="hash-sc-rev-1",
            type_de_note="synthese", parent_page_id=racine.pk,
        )

        apps_apres = self._migrer_vers(ETAT_APRES_ESTAMPILLAGE)
        PageApres = apps_apres.get_model("core", "Page")
        SyntheseDirigeeApres = apps_apres.get_model("core", "SyntheseDirigee")
        page_phase_c = PageApres.objects.create(
            url=None,
            html_original="<p>n</p>", html_readability="<p>n</p>",
            text_readability="nouvelle", content_hash="hash-sc-rev-2",
            type_de_note="synthese",
        )
        SyntheseDirigeeApres.objects.create(page_id=page_phase_c.pk)

        apps_retour = self._migrer_vers(ETAT_AVANT_ESTAMPILLAGE)
        SyntheseDirigeeRetour = apps_retour.get_model("core", "SyntheseDirigee")

        self.assertFalse(
            SyntheseDirigeeRetour.objects.filter(
                page_id=version_synthese.pk,
            ).exists()
        )
        self.assertTrue(
            SyntheseDirigeeRetour.objects.filter(
                page_id=page_phase_c.pk,
            ).exists()
        )

    def test_le_carnet_vient_des_appartenances_si_la_fk_est_vide(self):
        # Depuis la phase D corpus, la FK peut etre NULL alors que la
        # note appartient a des carnets (relecture C, M3).
        # / The FK may be NULL while memberships exist.
        apps_avant = self._migrer_vers(ETAT_AVANT_ESTAMPILLAGE)
        PageHistorique = apps_avant.get_model("core", "Page")
        DossierHistorique = apps_avant.get_model("core", "Dossier")
        Appartenance = apps_avant.get_model("core", "AppartenancePageDossier")

        carnet = DossierHistorique.objects.create(name="Carnet M3")
        racine = PageHistorique.objects.create(
            url="http://exemple.local/sc-m3-racine",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-sc-m3-0",
        )
        version_synthese = PageHistorique.objects.create(
            url=None,
            html_original="<p>s</p>", html_readability="<p>s</p>",
            text_readability="synthese", content_hash="hash-sc-m3-1",
            type_de_note="synthese", parent_page_id=racine.pk,
        )
        Appartenance.objects.create(
            page_id=version_synthese.pk, dossier_id=carnet.pk,
        )

        apps_apres = self._migrer_vers(ETAT_APRES_ESTAMPILLAGE)
        SyntheseDirigeeApres = apps_apres.get_model("core", "SyntheseDirigee")

        self.assertEqual(
            SyntheseDirigeeApres.objects.get(
                page_id=version_synthese.pk,
            ).dossier_id,
            carnet.pk,
        )
