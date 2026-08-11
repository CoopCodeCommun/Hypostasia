"""
Correction 1 (revue de cloture du 11 aout 2026) : le drapeau
« notification lue » est desormais PAR DESTINATAIRE. Depuis
l'elargissement du perimetre de lecture du bouton « taches » (le
proprietaire d'un carnet voit aussi les taches des notes qu'il contient),
un booleen UNIQUE et partage (ExtractionJob.notification_lue,
TranscriptionJob.notification_lue, Page.ingestion_notification_lue)
faisait que le premier destinataire qui clique eteint la notification
pour TOUS les autres.

Le modele NotificationTacheLue (utilisateur, type_tache, tache_id)
remplace la DECISION prise sur ces trois booleens ; ils restent en base
(voir le rapport de tache) mais ne pilotent plus rien ici.

LOCALISATION : front/tests/test_notification_par_destinataire.py
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import Dossier, EtatIngestion, NotificationTacheLue, Page, TranscriptionJob
from core.services.corpus import ranger_une_note_dans_un_carnet
from hypostasis_extractor.models import ExtractionJob, ExtractionJobStatus

User = get_user_model()


class DeuxDestinatairesVoientLaMemeTacheTest(TestCase):
    """
    Le test qui compte (brief de la tache) : deux utilisateurs voient
    la meme tache ; l'un la marque lue ; l'autre la voit toujours comme
    non lue. Le couple (auteur de la note, proprietaire du carnet) est
    exactement le cas d'usage qui a motive l'elargissement du 11 aout.
    / The test that matters: two users see the same task; one marks it
    read; the other still sees it unread.
    """

    def setUp(self):
        self.auteur = User.objects.create_user(username="auteur-x", password="x")
        self.prof = User.objects.create_user(username="prof-x", password="x")
        self.carnet = Dossier.objects.create(name="Carnet de classe", owner=self.prof)
        self.page = Page.objects.create(
            title="Note d'eleve", source_type="file", original_filename="d.pdf",
            html_original="", html_readability="", text_readability="",
            content_hash="hash-partage", owner=self.auteur,
        )
        ranger_une_note_dans_un_carnet(self.page, self.carnet)

    def test_extraction_marquee_lue_par_le_prof_reste_non_lue_pour_l_auteur(self):
        job = ExtractionJob.objects.create(
            page=self.page, status=ExtractionJobStatus.COMPLETED,
        )

        self.client.force_login(self.prof)
        reponse_marquage = self.client.post(
            f"/taches/{job.pk}/marquer-lue/?type=extraction",
        )
        self.assertEqual(reponse_marquage.status_code, 204)

        # Le prof ne voit plus rien de non lu.
        # / The teacher no longer sees anything unread.
        reponse_prof = self.client.get("/taches/bouton/")
        self.assertEqual(reponse_prof.context["nombre_non_lues"], 0)

        # L'auteur, lui, voit TOUJOURS sa notification.
        # / The author still sees the notification.
        self.client.force_login(self.auteur)
        reponse_auteur = self.client.get("/taches/bouton/")
        self.assertEqual(reponse_auteur.context["nombre_non_lues"], 1)

    def test_transcription_marquee_lue_par_le_prof_reste_non_lue_pour_l_auteur(self):
        job = TranscriptionJob.objects.create(page=self.page, status="completed")

        self.client.force_login(self.prof)
        self.client.post(f"/taches/{job.pk}/marquer-lue/?type=transcription")

        self.client.force_login(self.auteur)
        reponse_auteur = self.client.get("/taches/bouton/")
        self.assertEqual(reponse_auteur.context["nombre_non_lues"], 1)

    def test_ingestion_marquee_lue_par_le_prof_reste_non_lue_pour_l_auteur(self):
        Page.objects.filter(pk=self.page.pk).update(
            ingestion_etat=EtatIngestion.REUSSIE,
        )

        self.client.force_login(self.prof)
        self.client.post(f"/taches/{self.page.pk}/marquer-lue/?type=ingestion")

        self.client.force_login(self.auteur)
        reponse_auteur = self.client.get("/taches/bouton/")
        self.assertEqual(reponse_auteur.context["nombre_non_lues"], 1)

    def test_le_lien_lecture_ne_marque_lue_que_pour_qui_clique(self):
        # Second chemin de marquage (front/views.py, LectureViewSet),
        # independant de TachesViewSet.marquer_lue.
        # / Second read-marking path, independent from the ViewSet.
        job = ExtractionJob.objects.create(
            page=self.page, status=ExtractionJobStatus.COMPLETED,
        )

        self.client.force_login(self.prof)
        self.client.get(
            f"/lire/{self.page.pk}/?marquer_lue={job.pk}&type=analyse",
        )

        self.client.force_login(self.auteur)
        reponse_auteur = self.client.get("/taches/bouton/")
        self.assertEqual(reponse_auteur.context["nombre_non_lues"], 1)

    def test_marquer_toutes_lues_ne_touche_que_l_appelant(self):
        ExtractionJob.objects.create(
            page=self.page, status=ExtractionJobStatus.COMPLETED,
        )

        self.client.force_login(self.prof)
        self.client.post("/taches/marquer-toutes-lues/")

        self.client.force_login(self.auteur)
        reponse_auteur = self.client.get("/taches/bouton/")
        self.assertEqual(reponse_auteur.context["nombre_non_lues"], 1)

    def test_marquer_lue_deux_fois_par_le_meme_destinataire_ne_casse_rien(self):
        # Idempotence : cliquer deux fois (double-clic, onglet double)
        # ne doit pas lever d'IntegrityError sur la contrainte d'unicite.
        # / Clicking twice must not raise on the uniqueness constraint.
        job = ExtractionJob.objects.create(
            page=self.page, status=ExtractionJobStatus.COMPLETED,
        )
        self.client.force_login(self.auteur)

        premiere = self.client.post(f"/taches/{job.pk}/marquer-lue/?type=extraction")
        seconde = self.client.post(f"/taches/{job.pk}/marquer-lue/?type=extraction")

        self.assertEqual(premiere.status_code, 204)
        self.assertEqual(seconde.status_code, 204)


class ModeleNotificationTacheLueTest(TestCase):
    """
    Le modele lui-meme : l'existence de la ligne EST le drapeau — pas
    de champ booleen supplementaire.
    / The model itself: row existence IS the flag.
    """

    def setUp(self):
        self.utilisateur = User.objects.create_user(username="u-notif", password="x")

    def test_l_existence_de_la_ligne_est_le_drapeau(self):
        NotificationTacheLue.objects.create(
            utilisateur=self.utilisateur, type_tache="extraction", tache_id=42,
        )
        self.assertTrue(
            NotificationTacheLue.objects.filter(
                utilisateur=self.utilisateur, type_tache="extraction", tache_id=42,
            ).exists()
        )

    def test_un_meme_couple_utilisateur_type_tache_ne_peut_pas_se_dupliquer(self):
        NotificationTacheLue.objects.create(
            utilisateur=self.utilisateur, type_tache="extraction", tache_id=1,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NotificationTacheLue.objects.create(
                    utilisateur=self.utilisateur, type_tache="extraction", tache_id=1,
                )


class CoutEnRequetesDuBoutonTest(TestCase):
    """
    Le passage a un drapeau par destinataire NE DOIT PAS degrader le
    cout en requetes du bouton : l'anti-jointure vers NotificationTacheLue
    est une SOUS-REQUETE (exclude(pk__in=...)), pas une requete separee
    ni une boucle — le total reste 9 requetes constantes quel que soit
    le nombre de taches (aucune requete par ligne).
    / Widening to a per-recipient flag must not degrade the button's
    query cost: the anti-join is a subquery, not an extra round trip.
    """

    def setUp(self):
        self.utilisateur = User.objects.create_user(username="u-cout", password="x")
        self.page = Page.objects.create(
            title="Note", source_type="file", original_filename="d.pdf",
            html_original="", html_readability="", text_readability="",
            content_hash="hash-cout", owner=self.utilisateur,
        )
        for _numero in range(5):
            ExtractionJob.objects.create(
                page=self.page, status=ExtractionJobStatus.COMPLETED,
            )
        NotificationTacheLue.objects.create(
            utilisateur=self.utilisateur, type_tache="extraction",
            tache_id=ExtractionJob.objects.first().pk,
        )

    def test_neuf_requetes_constantes(self):
        from front.views_taches import _calculer_etat_bouton
        with self.assertNumQueries(9):
            _calculer_etat_bouton(self.utilisateur)
