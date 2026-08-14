"""
Les taches d'ingestion previennent-elles l'utilisateur ?
/ Do ingestion tasks notify the user?

LOCALISATION : hypostasis_extractor/tests/test_notifications_ingestion.py
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page
from core.services.corpus import ranger_une_note_dans_un_carnet

User = get_user_model()


class NotificationDeLIngestionTest(TestCase):
    """Une ingestion qui se termine doit se faire connaitre."""

    def setUp(self):
        self.proprietaire = User.objects.create_user(username="proprio")
        self.page = Page.objects.create(
            title="Une note", source_type="web",
            html_original="<p>du texte</p>", html_readability="<p>du texte</p>",
            text_readability="du texte", content_hash="x",
            owner=self.proprietaire,
        )

    def test_une_capture_ingeree_previent_son_proprietaire(self):
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1, 2, 3],
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        notification.assert_called_once_with(
            user_pk=self.proprietaire.pk,
            tache_id=self.page.pk,
            tache_type="ingestion",
            status="completed",
        )

    def test_une_ingestion_en_echec_previent_aussi(self):
        # Un echec silencieux est pire qu'un echec : l'utilisateur
        # attendrait indefiniment. / A silent failure is worse.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", side_effect=ValueError("conversion HS"),
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        self.assertEqual(
            notification.call_args.kwargs["status"], "error",
        )

    def test_le_proprietaire_d_un_carnet_est_prevenu_aussi(self):
        # C'est la correction de la phase D, restee a moitie faite :
        # une note rangee dans le carnet d'un collegue doit le prevenir.
        # / The phase D fix, left half-done.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        collegue = User.objects.create_user(username="collegue")
        carnet_du_collegue = Dossier.objects.create(
            name="Le carnet du collègue", owner=collegue,
        )
        ranger_une_note_dans_un_carnet(
            self.page, carnet_du_collegue, self.proprietaire,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1],
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in notification.call_args_list
        }
        self.assertEqual(pks_prevenus, {self.proprietaire.pk, collegue.pk})

    def test_une_notification_qui_echoue_ne_casse_pas_l_ingestion(self):
        # Une ingestion reussie ne doit pas devenir un echec parce que
        # le canal de notification est tombe.
        # / A dead channel must not fail a successful ingestion.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1],
        ), patch(
            "front.tasks.notifier_tache_terminee",
            side_effect=RuntimeError("channel layer HS"),
        ):
            resultat = ingerer_une_capture_web_avec_docling.apply(
                args=[self.page.pk],
            )

        self.assertEqual(resultat.result, {"elements": 1})


class LaFileEstPrevenueQuandElleAvanceTest(TestCase):
    """
    Une ingestion qui se termine fait avancer la file de TOUT LE MONDE.
    / A finished ingestion moves everyone else's queue position.

    LOCALISATION : hypostasis_extractor/tests/test_notifications_ingestion.py

    LE DEFAUT QUE CES TESTS FERMENT

    `_prevenir_de_l_ingestion` ne previent que les destinataires de la
    page TERMINEE. Le menu des taches affiche desormais une position
    dans la file (front/views_taches.py) : sans notification, celui qui
    attend derriere garde « 3ᵉ dans la file » affiche a l'ecran alors
    qu'il est passe 2ᵉ, puis 1ᵉʳ. Le chiffre se fige, et un chiffre fige
    est pire que pas de chiffre : il se lit comme une file bloquee.
    / Without this, the displayed position freezes — and a frozen number
    reads as a stuck queue, which is worse than no number at all.
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(username="proprio-file")
        self.page_qui_se_termine = Page.objects.create(
            title="Celle qui finit", source_type="web",
            html_original="<p>du texte</p>", html_readability="<p>du texte</p>",
            text_readability="du texte", content_hash="fin",
            owner=self.proprietaire,
        )

    def _creer_page_en_attente(self, proprietaire, titre, anciennete_en_secondes=0):
        from datetime import timedelta

        from django.utils import timezone

        from core.models import EtatIngestion

        return Page.objects.create(
            title=titre, source_type="file", original_filename="doc.pdf",
            html_original="", html_readability="", text_readability="",
            content_hash=f"hash-{titre}", owner=proprietaire,
            ingestion_etat=EtatIngestion.EN_ATTENTE,
            ingestion_maj_le=timezone.now() - timedelta(
                seconds=anciennete_en_secondes,
            ),
        )

    def _terminer_l_ingestion(self):
        """
        Joue la fin de l'ingestion et rend les mocks de notification.
        / Runs the ingestion's end and returns the notification mocks.
        """
        from core.models import EtatIngestion
        from hypostasis_extractor.tasks_element import (
            _noter_l_etat_d_ingestion, _prevenir_de_l_ingestion,
        )

        with patch("front.tasks.notifier_tache_terminee") as fin_de_tache, patch(
            "front.tasks.notifier_la_file_d_ingestion",
        ) as file_qui_avance:
            _noter_l_etat_d_ingestion(
                self.page_qui_se_termine.pk, EtatIngestion.REUSSIE,
            )
            _prevenir_de_l_ingestion(self.page_qui_se_termine, "completed")
        return fin_de_tache, file_qui_avance

    def test_le_debut_d_une_conversion_previent_aussi_la_file(self):
        """
        La transition EN_ATTENTE -> EN_COURS fait AVANCER la file.
        / Moving to EN_COURS moves the queue forward too.

        LOCALISATION : hypostasis_extractor/tests/test_notifications_ingestion.py

        Defaut trouve par la relecture adverse du 14 aout 2026, et le
        plus grave du chantier : le fan-out ne partait qu'a la FIN d'une
        ingestion. Or une page qui passe EN_COURS QUITTE la file — les
        rangs de tous ceux qui restent derriere diminuent d'un cran, et
        personne ne l'apprenait. Le chiffre affiche restait donc faux
        pendant TOUTE la duree de chaque conversion (83 a 164 s), et la
        page en cours annoncait encore « 1ᵉʳ dans la file » pendant sa
        propre conversion. Il n'existe aucun polling de secours : le
        WebSocket est le seul rafraichissement.
        / The fan-out only fired at the END; but moving to EN_COURS also
        leaves the queue. The displayed rank stayed wrong for the whole
        duration of every conversion.
        """
        from core.models import EtatIngestion
        from hypostasis_extractor.tasks_element import _noter_l_etat_d_ingestion

        celui_qui_attend = User.objects.create_user(username="derriere-la-conversion")
        self._creer_page_en_attente(celui_qui_attend, "encore-en-file")

        with patch("front.tasks.notifier_la_file_d_ingestion") as file_qui_avance:
            _noter_l_etat_d_ingestion(
                self.page_qui_se_termine.pk, EtatIngestion.EN_COURS,
            )

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in file_qui_avance.call_args_list
        }
        self.assertEqual(pks_prevenus, {celui_qui_attend.pk})

    def test_une_page_deja_ingeree_previent_aussi_la_file(self):
        """
        Les gardes d'entree « page deja ingeree » font avancer la file.
        / The "already ingested" guards move the queue too.

        LOCALISATION : hypostasis_extractor/tests/test_notifications_ingestion.py

        Second defaut de la relecture adverse : trois chemins ecrivent
        REUSSIE puis rendent la main SANS passer par
        `_prevenir_de_l_ingestion` (redelivrance Celery, page ayant
        acquis ses elements autrement). La file avancait en silence.
        C'est pourquoi le fan-out vit desormais dans
        `_noter_l_etat_d_ingestion`, le point de passage unique de
        l'ecriture d'etat, et non chez ses appelants.
        / Three paths wrote REUSSIE and returned without notifying;
        hence the fan-out now lives in the single state-writing point.
        """
        from core.models import EtatIngestion
        from hypostasis_extractor.tasks_element import _noter_l_etat_d_ingestion

        celui_qui_attend = User.objects.create_user(username="derriere-la-garde")
        self._creer_page_en_attente(celui_qui_attend, "encore-en-file")

        with patch("front.tasks.notifier_la_file_d_ingestion") as file_qui_avance:
            _noter_l_etat_d_ingestion(
                self.page_qui_se_termine.pk, EtatIngestion.REUSSIE,
            )

        self.assertEqual(file_qui_avance.call_count, 1)

    def test_entrer_dans_la_file_ne_previent_personne(self):
        """
        Une page qui ENTRE en file ne change le rang de personne.
        / A page joining the queue changes nobody's rank.

        Elle se range derriere tout le monde : notifier serait du bruit,
        et ce bruit couterait une requete et N envois WebSocket a chaque
        import. / It queues up behind everyone; notifying would be noise.
        """
        from core.models import EtatIngestion
        from hypostasis_extractor.tasks_element import _noter_l_etat_d_ingestion

        self._creer_page_en_attente(
            User.objects.create_user(username="deja-en-file"), "encore-en-file",
        )

        with patch("front.tasks.notifier_la_file_d_ingestion") as file_qui_avance:
            _noter_l_etat_d_ingestion(
                self.page_qui_se_termine.pk, EtatIngestion.EN_ATTENTE,
            )

        self.assertEqual(file_qui_avance.call_count, 0)

    def test_le_fan_out_ne_coute_pas_une_requete_par_page_en_file(self):
        """
        Le cout du fan-out ne doit pas croitre avec la longueur de la file.
        / The fan-out's cost must not grow with the queue's length.

        LOCALISATION : hypostasis_extractor/tests/test_notifications_ingestion.py

        Troisieme defaut de la relecture : la premiere version appelait
        `_destinataires_de_notification` page par page — une requete
        chacune. C'est exactement le N+1 que le calcul du rang evite
        cote vue ; le payer ici serait incoherent, et le cout arriverait
        le jour ou la file s'allonge.
        / One query per queued page is the very N+1 the rank computation
        avoids on the view side.
        """
        from core.models import EtatIngestion
        from hypostasis_extractor.tasks_element import _noter_l_etat_d_ingestion

        proprietaire_du_carnet = User.objects.create_user(username="prof-file")
        carnet = Dossier.objects.create(
            name="Carnet de file", owner=proprietaire_du_carnet,
        )
        for numero in range(10):
            page_en_file = self._creer_page_en_attente(
                self.proprietaire, f"en-file-{numero}", numero,
            )
            ranger_une_note_dans_un_carnet(page_en_file, carnet)

        # 3 requetes fixes : l'UPDATE d'etat, le nettoyage des
        # notifications lues, puis DEUX pour rassembler les
        # destinataires (proprietaires de notes, proprietaires de
        # carnets) — jamais une par page en file.
        # / Fixed query count, never one per queued page.
        with patch("front.tasks.notifier_la_file_d_ingestion"):
            with self.assertNumQueries(4):
                _noter_l_etat_d_ingestion(
                    self.page_qui_se_termine.pk, EtatIngestion.EN_COURS,
                )

    def test_ceux_qui_attendent_derriere_sont_prevenus(self):
        celui_qui_attend = User.objects.create_user(username="qui-attend")
        self._creer_page_en_attente(celui_qui_attend, "encore-en-file")

        _fin_de_tache, file_qui_avance = self._terminer_l_ingestion()

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in file_qui_avance.call_args_list
        }
        self.assertEqual(pks_prevenus, {celui_qui_attend.pk})

    def test_un_utilisateur_n_est_prevenu_qu_une_fois_pour_ses_deux_notes(self):
        # Deux notes en file du meme utilisateur, c'est UN rafraichissement
        # a lui demander, pas deux. / Two notes, one refresh.
        celui_qui_attend = User.objects.create_user(username="qui-attend-2")
        self._creer_page_en_attente(celui_qui_attend, "premiere", 30)
        self._creer_page_en_attente(celui_qui_attend, "seconde", 20)

        _fin_de_tache, file_qui_avance = self._terminer_l_ingestion()

        self.assertEqual(file_qui_avance.call_count, 1)

    def test_le_proprietaire_de_la_page_terminee_est_toujours_prevenu(self):
        # Le fan-out s'AJOUTE a la notification de fin ; il ne la
        # remplace pas. / The fan-out adds to the end notification.
        self._creer_page_en_attente(
            User.objects.create_user(username="qui-attend-3"), "en-file",
        )

        fin_de_tache, _file_qui_avance = self._terminer_l_ingestion()

        fin_de_tache.assert_called_once_with(
            user_pk=self.proprietaire.pk,
            tache_id=self.page_qui_se_termine.pk,
            tache_type="ingestion",
            status="completed",
        )

    def test_une_page_fantome_en_file_ne_declenche_aucune_notification(self):
        # Son worker est mort : son proprietaire n'attend plus rien, et
        # elle ne compte deja plus dans les rangs affiches.
        # / Its worker is dead; it no longer counts in the displayed
        # ranks either.
        from front.views import DELAI_INGESTION_FANTOME_MIN

        self._creer_page_en_attente(
            User.objects.create_user(username="abandonne"), "fantome",
            anciennete_en_secondes=(DELAI_INGESTION_FANTOME_MIN + 1) * 60,
        )

        _fin_de_tache, file_qui_avance = self._terminer_l_ingestion()

        self.assertEqual(file_qui_avance.call_count, 0)

    def test_une_file_vide_ne_declenche_aucune_notification(self):
        _fin_de_tache, file_qui_avance = self._terminer_l_ingestion()

        self.assertEqual(file_qui_avance.call_count, 0)

    def test_un_canal_tombe_ne_fait_pas_echouer_l_ingestion(self):
        # Meme principe que partout ailleurs dans ce fichier : prevenir
        # la file est un service rendu, pas une condition de succes.
        # / Notifying the queue is a courtesy, never a success condition.
        from hypostasis_extractor.tasks_element import _prevenir_de_l_ingestion

        self._creer_page_en_attente(
            User.objects.create_user(username="qui-attend-4"), "en-file",
        )

        with patch("front.tasks.notifier_tache_terminee"), patch(
            "front.tasks.notifier_la_file_d_ingestion",
            side_effect=RuntimeError("channel layer HS"),
        ):
            _prevenir_de_l_ingestion(self.page_qui_se_termine, "completed")

        # Aucune exception ne remonte : le test passe s'il arrive ici.
        # / No exception escaped: reaching this line is the assertion.

    def test_la_page_qui_vient_de_finir_ne_se_previent_pas_elle_meme(self):
        # Cas de la re-ingestion : la page terminee peut se retrouver
        # elle-meme en attente d'un nouveau cycle. Son proprietaire est
        # deja prevenu par la notification de fin — le prevenir deux
        # fois ferait clignoter le menu sans raison.
        # / On re-ingestion the finished page may itself be queued again;
        # its owner is already covered by the end notification.
        from datetime import timedelta

        from django.utils import timezone

        from core.models import EtatIngestion

        Page.objects.filter(pk=self.page_qui_se_termine.pk).update(
            ingestion_etat=EtatIngestion.EN_ATTENTE,
            ingestion_maj_le=timezone.now() - timedelta(seconds=5),
        )

        _fin_de_tache, file_qui_avance = self._terminer_l_ingestion()

        self.assertEqual(file_qui_avance.call_count, 0)


class DestinatairesDeLAnalyseEtDeLaTranscriptionTest(TestCase):
    """
    La correction de la phase D, appliquee aux deux chemins oublies.
    / The phase D fix, applied to the two forgotten paths.
    """

    def test_l_analyse_previent_les_proprietaires_de_carnets(self):
        from hypostasis_extractor.models import ExtractionJob
        from hypostasis_extractor.tasks_element import _prevenir_l_utilisateur

        proprietaire = User.objects.create_user(username="proprio2")
        collegue = User.objects.create_user(username="collegue2")
        page = Page.objects.create(
            title="Note analysée", source_type="web", html_original="",
            html_readability="", text_readability="", content_hash="y",
            owner=proprietaire,
        )
        carnet = Dossier.objects.create(name="Carnet", owner=collegue)
        ranger_une_note_dans_un_carnet(page, carnet, proprietaire)

        job = ExtractionJob.objects.create(
            page=page, name="j", prompt_description="p", status="completed",
        )

        with patch("front.tasks.notifier_tache_terminee") as notification:
            _prevenir_l_utilisateur(job, "completed")

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in notification.call_args_list
        }
        self.assertEqual(pks_prevenus, {proprietaire.pk, collegue.pk})
