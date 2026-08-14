"""
Les ingestions apparaissent-elles dans le bouton et le dropdown ?
/ Do ingestions show up in the tasks button and dropdown?

LOCALISATION : front/tests/test_taches_ingestion.py
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Dossier, EtatIngestion, NotificationTacheLue, Page, TypeDeTache
from core.services.corpus import ranger_une_note_dans_un_carnet
from hypostasis_extractor.models import ExtractionJob, ExtractionJobStatus

User = get_user_model()


class IngestionDansLesTachesTest(TestCase):

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="proprio", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def _creer_page(self, etat, lue=False):
        # ingestion_maj_le=now() des qu'un etat est demande : c'est ce
        # que le code reel ecrit TOUJOURS (import, relance, tache) —
        # un NULL actif n'est plus qu'un artefact du bug corrige de
        # core/views.py (correction 2). / Real code always stamps a
        # date; NULL-active is now only the fixed bug's artifact.
        page = Page.objects.create(
            title="Un document", source_type="file",
            original_filename="doc.pdf",
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=self.proprietaire,
            ingestion_etat=etat,
            ingestion_maj_le=timezone.now() if etat else None,
        )
        if lue:
            # Correction 1 : "deja lue" est desormais une ligne
            # NotificationTacheLue pour le proprietaire, plus le
            # booleen partage (mort pour cette decision).
            # / "Already read" is now a NotificationTacheLue row.
            NotificationTacheLue.objects.create(
                utilisateur=self.proprietaire, type_tache=TypeDeTache.INGESTION,
                tache_id=page.pk,
            )
        return page

    def test_une_ingestion_en_cours_compte_dans_le_bouton(self):
        self._creer_page(EtatIngestion.EN_COURS)

        reponse = self.client.get("/taches/bouton/")

        self.assertContains(reponse, "1")
        self.assertEqual(reponse.context["nombre_en_cours"], 1)

    def test_une_ingestion_reussie_non_lue_compte_comme_non_lue(self):
        self._creer_page(EtatIngestion.REUSSIE, lue=False)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_non_lues"], 1)

    def test_une_ingestion_deja_lue_ne_compte_plus(self):
        self._creer_page(EtatIngestion.REUSSIE, lue=True)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_non_lues"], 0)

    def test_une_page_sans_ingestion_ne_compte_jamais(self):
        # Une page nee avant le moteur ELEMENT, ou un .txt : son
        # ingestion_etat est vide, elle n'est pas une tache.
        # / A page that never requested an ingestion is not a task.
        self._creer_page("")

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_non_lues"], 0)
        self.assertEqual(reponse.context["nombre_en_cours"], 0)

    def test_l_ingestion_apparait_dans_le_dropdown(self):
        page = self._creer_page(EtatIngestion.REUSSIE)

        reponse = self.client.get("/taches/dropdown/")

        libelles = [t.libelle_de_tache for t in reponse.context["taches"]]
        self.assertIn("Découpage", libelles)
        self.assertEqual(reponse.context["taches"][0].page_resultat_id, page.pk)

    def test_marquer_lue_une_ingestion(self):
        page = self._creer_page(EtatIngestion.REUSSIE, lue=False)

        self.client.post(f"/taches/{page.pk}/marquer-lue/?type=ingestion")

        self.assertTrue(
            NotificationTacheLue.objects.filter(
                utilisateur=self.proprietaire, type_tache=TypeDeTache.INGESTION,
                tache_id=page.pk,
            ).exists()
        )

    def test_on_ne_marque_pas_lue_la_page_d_un_autre(self):
        # Doctrine du projet : 404, jamais 403.
        # / Project doctrine: 404, never 403.
        autre = User.objects.create_user(username="autre")
        page_d_autrui = Page.objects.create(
            title="Pas la mienne", source_type="file",
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=autre,
            ingestion_etat=EtatIngestion.REUSSIE,
        )

        reponse = self.client.post(
            f"/taches/{page_d_autrui.pk}/marquer-lue/?type=ingestion",
        )

        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(
            NotificationTacheLue.objects.filter(
                type_tache=TypeDeTache.INGESTION, tache_id=page_d_autrui.pk,
            ).exists()
        )

    def test_marquer_lue_via_le_lien_lecture(self):
        # Deuxieme chemin de marquage : le lien du dropdown pointe vers
        # /lire/<id>/?marquer_lue=<pk>&type=ingestion, traite par
        # front/views.py (LectureViewSet.retrieve), pas par le ViewSet
        # Taches. Les deux chemins sont independants (complement du brief,
        # piege 2).
        # / Second read-marking path: the dropdown link, handled by
        # LectureViewSet.retrieve, independent from TachesViewSet.
        page = self._creer_page(EtatIngestion.REUSSIE, lue=False)

        self.client.get(
            f"/lire/{page.pk}/?marquer_lue={page.pk}&type=ingestion",
        )

        self.assertTrue(
            NotificationTacheLue.objects.filter(
                utilisateur=self.proprietaire, type_tache=TypeDeTache.INGESTION,
                tache_id=page.pk,
            ).exists()
        )


class IngestionFantomeTest(TestCase):
    """
    Defaut 2 (revue de cloture du 11 aout) : le comptage du badge n'a
    aucune borne de temps, contrairement a relancer_ingestion qui
    considere un etat actif comme fantome au-dela de
    DELAI_INGESTION_FANTOME_MIN. Un worker mort laissait le badge
    allume pour toujours.
    / The badge count had no time bound, unlike relancer_ingestion's
    ghost detection; a dead worker left the badge on forever.
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="proprio2", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def _creer_page_en_cours(self, ingestion_maj_le):
        return Page.objects.create(
            title="Un document", source_type="file",
            original_filename="doc.pdf",
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=self.proprietaire,
            ingestion_etat=EtatIngestion.EN_COURS,
            ingestion_maj_le=ingestion_maj_le,
        )

    def test_une_ingestion_en_cours_perimee_ne_compte_plus(self):
        from front.views import DELAI_INGESTION_FANTOME_MIN
        self._creer_page_en_cours(
            timezone.now() - timedelta(minutes=DELAI_INGESTION_FANTOME_MIN + 1),
        )

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_en_cours"], 0)

    def test_une_ingestion_en_cours_recente_compte_toujours(self):
        self._creer_page_en_cours(timezone.now())

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_en_cours"], 1)

    def test_une_ingestion_en_cours_sans_date_ne_compte_plus(self):
        # Correction 2 (revue de cloture du 11 aout) : renverse la regle
        # ci-dessus. Les pages actives SANS ingestion_maj_le viennent
        # d'un bug de core/views.py corrige aujourd'hui — un NULL actif
        # ne peut plus etre produit legitimement. Sans date, on ne peut
        # pas prouver la recence : traiter comme un fantome (exclu du
        # compte), sinon le badge reste allume pour toujours pour ces
        # pages orphelines de la periode buguee.
        # / An active state with no timestamp can no longer be produced
        # legitimately (the writing bug is fixed); without a date we
        # cannot prove recency, so treat it as a ghost.
        self._creer_page_en_cours(None)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_en_cours"], 0)


class NotificationDestinataireCarnetTest(TestCase):
    """
    Defaut 1 (revue de cloture du 11 aout) : _destinataires_de_notification
    (front/tasks.py) previent le proprietaire d'un carnet contenant une
    note d'autrui. Le bouton, le dropdown et les DEUX chemins de
    marquage lu doivent refleter la meme regle — sinon la notification
    part, et son destinataire ne voit rien.
    / The notification recipients rule (front/tasks.py) also covers
    notebook owners; the button, dropdown, and both mark-read paths
    must mirror it, or the notification lands nowhere visible.
    """

    def setUp(self):
        self.auteur = User.objects.create_user(username="auteur", password="x")
        self.proprietaire_carnet = User.objects.create_user(
            username="prof", password="x",
        )
        self.tiers = User.objects.create_user(username="tiers", password="x")

        self.carnet = Dossier.objects.create(
            name="Carnet de classe", owner=self.proprietaire_carnet,
        )

        self.page = Page.objects.create(
            title="Note d'un eleve", source_type="file",
            original_filename="doc.pdf",
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=self.auteur,
            ingestion_etat=EtatIngestion.EN_COURS,
            ingestion_maj_le=timezone.now(),
        )
        ranger_une_note_dans_un_carnet(self.page, self.carnet)

    def test_le_proprietaire_du_carnet_voit_l_ingestion_dans_le_bouton(self):
        self.client.force_login(self.proprietaire_carnet)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_en_cours"], 1)

    def test_le_proprietaire_du_carnet_voit_l_ingestion_dans_le_dropdown(self):
        self.client.force_login(self.proprietaire_carnet)

        reponse = self.client.get("/taches/dropdown/")

        pks_des_taches = [t.page_resultat_id for t in reponse.context["taches"]]
        self.assertIn(self.page.pk, pks_des_taches)

    def test_le_proprietaire_du_carnet_marque_lue_l_ingestion(self):
        Page.objects.filter(pk=self.page.pk).update(
            ingestion_etat=EtatIngestion.REUSSIE,
        )
        self.client.force_login(self.proprietaire_carnet)

        reponse = self.client.post(
            f"/taches/{self.page.pk}/marquer-lue/?type=ingestion",
        )

        self.assertEqual(reponse.status_code, 204)
        self.assertTrue(
            NotificationTacheLue.objects.filter(
                utilisateur=self.proprietaire_carnet, type_tache=TypeDeTache.INGESTION,
                tache_id=self.page.pk,
            ).exists()
        )

    def test_le_proprietaire_du_carnet_marque_lue_via_le_lien_lecture(self):
        Page.objects.filter(pk=self.page.pk).update(
            ingestion_etat=EtatIngestion.REUSSIE,
        )
        self.client.force_login(self.proprietaire_carnet)

        self.client.get(
            f"/lire/{self.page.pk}/?marquer_lue={self.page.pk}&type=ingestion",
        )

        self.assertTrue(
            NotificationTacheLue.objects.filter(
                utilisateur=self.proprietaire_carnet, type_tache=TypeDeTache.INGESTION,
                tache_id=self.page.pk,
            ).exists()
        )

    def test_le_proprietaire_du_carnet_voit_une_extraction_dans_le_bouton(self):
        ExtractionJob.objects.create(
            page=self.page, status=ExtractionJobStatus.PENDING,
        )
        self.client.force_login(self.proprietaire_carnet)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_en_cours"], 2)

    def test_un_tiers_sans_lien_ne_voit_rien_dans_le_bouton(self):
        self.client.force_login(self.tiers)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_en_cours"], 0)

    def test_un_tiers_sans_lien_ne_voit_rien_dans_le_dropdown(self):
        self.client.force_login(self.tiers)

        reponse = self.client.get("/taches/dropdown/")

        pks_des_taches = [t.page_resultat_id for t in reponse.context["taches"]]
        self.assertNotIn(self.page.pk, pks_des_taches)

    def test_un_tiers_sans_lien_recoit_404_au_marquage(self):
        # Doctrine du projet : 404, jamais 403 — un tiers sans acces ne
        # doit pas savoir si la note existe. / 404, never 403.
        Page.objects.filter(pk=self.page.pk).update(
            ingestion_etat=EtatIngestion.REUSSIE,
        )
        self.client.force_login(self.tiers)

        reponse = self.client.post(
            f"/taches/{self.page.pk}/marquer-lue/?type=ingestion",
        )

        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(
            NotificationTacheLue.objects.filter(
                utilisateur=self.tiers, type_tache=TypeDeTache.INGESTION,
                tache_id=self.page.pk,
            ).exists()
        )

    def test_pas_de_n_plus_1_sur_le_dropdown(self):
        # Elargir le perimetre ne doit pas transformer une requete en
        # trente : le nombre de requetes doit rester borne quel que
        # soit le nombre de taches rendues (jusqu'a 30, spec § 11).
        # / Widening scope must not turn one query into thirty.
        for numero in range(5):
            autre_page = Page.objects.create(
                title=f"Note {numero}", source_type="file",
                original_filename="doc.pdf",
                html_original="", html_readability="", text_readability="",
                content_hash=f"hash-{numero}", owner=self.auteur,
                ingestion_etat=EtatIngestion.REUSSIE,
            )
            ranger_une_note_dans_un_carnet(autre_page, self.carnet)
            ExtractionJob.objects.create(
                page=autre_page, status=ExtractionJobStatus.COMPLETED,
            )

        self.client.force_login(self.proprietaire_carnet)

        # 15 requetes fixes (session, user, 3 listes, 11 compteurs/
        # exists du bouton, et 1 pour ranger la file d'ingestion),
        # aucune par ligne rendue : la preuve que l'elargissement de
        # perimetre n'a pas transforme 1 requete en 30.
        # / 15 fixed queries, none per rendered row.
        #
        # 14 -> 15 le 14 aout 2026 : la position dans la file d'attente
        # (_rangs_dans_la_file_d_ingestion) rend TOUTE la file en une
        # seule requete, pas une par ligne affichee. C'est precisement
        # ce que ce test verrouille — si ce chiffre devait bouger avec
        # le nombre de notes en file, l'affichage serait a refaire.
        # / The queue-rank feature adds exactly one query for the whole
        # menu; if this number ever varied with the row count, the
        # feature would need rewriting.
        with self.assertNumQueries(15):
            self.client.get("/taches/dropdown/")


class IngestionFantomeSansDateDansLeMenuTest(TestCase):
    """
    Correction 2, second endroit (revue de cloture du 11 aout) : sous
    PostgreSQL, order_by("-ingestion_maj_le") place les NULL EN TETE
    (NULLS FIRST par defaut en DESC). Une page active sans date —
    laissee par le bug corrige de core/views.py — squattait donc le
    haut du dropdown devant des ingestions reellement recentes.
    / Under PostgreSQL, DESC ordering puts NULLs first by default; an
    active-but-dateless ghost page used to squat the top of the
    dropdown ahead of genuinely recent ingestions.
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="proprio3", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def test_la_page_fantome_sans_date_ne_squatte_pas_la_tete_du_dropdown(self):
        # Test discriminant (relecture, defaut 3) : la version precedente
        # ne distinguait pas le correctif — avec seulement 2 pages, le
        # sorted() Python final (date_tri = ingestion_maj_le OR
        # created_at) rattrapait deja le fantome par son created_at
        # "maintenant", que le tri SQL soit corrige ou non. Le vrai bug
        # se joue AVANT ce sorted() : nulls_last ne s'applique qu'a la
        # PRE-TRANCHE SQL [:30] de chaque queryset — si 30 fantomes ou
        # plus trient AVANT une tache datee (NULLS FIRST par defaut en
        # DESC sous PostgreSQL), la tache datee est EVINCEE du [:30]
        # AVANT MEME que le sorted() Python n'ait la moindre chance de
        # la repositionner. 30 fantomes garantissent l'eviction complete
        # (ils remplissent a eux seuls la tranche).
        # / The previous version never discriminated the fix: with only
        # 2 rows, the final Python sort always fixed the order via
        # created_at fallback, fix or no fix. The real bug happens
        # BEFORE that sort, in the SQL-level [:30] slice — 30 ghosts
        # guarantee the dated task is evicted from the slice entirely
        # under the old NULLS-FIRST ordering.
        for numero in range(30):
            Page.objects.create(
                title=f"Fantome sans date {numero}", source_type="file",
                original_filename="doc.pdf",
                html_original="", html_readability="", text_readability="",
                content_hash=f"hash-fantome-{numero}", owner=self.proprietaire,
                ingestion_etat=EtatIngestion.EN_COURS, ingestion_maj_le=None,
            )
        # Ingestion reellement recente, datee.
        page_recente = Page.objects.create(
            title="Recente", source_type="file",
            original_filename="doc.pdf",
            html_original="", html_readability="", text_readability="",
            content_hash="hash-recente", owner=self.proprietaire,
            ingestion_etat=EtatIngestion.REUSSIE,
            ingestion_maj_le=timezone.now(),
        )

        reponse = self.client.get("/taches/dropdown/")

        taches = reponse.context["taches"]
        pks_des_taches = [t.page_resultat_id for t in taches]
        # Avant le correctif : les 30 fantomes squattent le [:30] SQL,
        # la tache recente n'apparait meme plus dans le dropdown.
        # / Before the fix: the 30 ghosts fill the SQL slice, the
        # recent task never even reaches the dropdown.
        self.assertIn(page_recente.pk, pks_des_taches)
        self.assertEqual(taches[0].page_resultat_id, page_recente.pk)
