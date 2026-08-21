"""
Le recapitulatif du matin : un mail par jour, jamais deux.
/ The morning recap: one mail a day, never two.

LOCALISATION : front/tests/test_le_recapitulatif_du_matin.py

SPEC-synthese, addendum du 21 aout 2026. Trois regles s'exercent ici :

- **le mail part TOUJOURS apres le run de la nuit** — c'est la
  `PasseDeNuit` qui le dit, pas un ecart entre deux lignes de cron ;
- **un seul mail par personne et par jour** (modele Discourse), et rien
  du tout quand il n'y a rien a dire ;
- **le perimetre des destinataires porte les partages du carnet**, pas
  seulement les proprietaires.
/ The mail follows the night run; one mail per person per day; shares
are included.
"""

from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.models import (
    DossierPartage, EnvoiDuRecapitulatif, MotifDeTourDeWiki, Page,
    PasseDeNuit, TourDeWiki, TypeDeNote, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c


class BaseDuRecapitulatif(TestCase):
    """Un wiki, son proprietaire, et une lectrice. / A wiki and readers."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.proprietaire = self.fixtures["demandeur"]
        self.proprietaire.email = "proprietaire@exemple.local"
        self.proprietaire.save(update_fields=["email"])

        self.page_du_wiki = Page.objects.create(
            title="Wiki du matin", text_readability="",
            html_readability="", html_original="",
            content_hash="hash-matin", type_de_note=TypeDeNote.WIKI,
            owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            self.page_du_wiki, self.fixtures["carnet"], self.proprietaire,
        )
        self.wiki = Wiki.objects.create(
            page=self.page_du_wiki, dossier=self.fixtures["carnet"],
            sujet="Le seuil",
        )
        # L'article part A JOUR : il cite tout son perimetre. Sans le
        # chemin d'ecriture reel, aucun SourceLink ne serait indexe et
        # TOUT paraitrait « non repris » — le recapitulatif annoncerait
        # du neuf des le premier matin.
        # / Written through the real path: otherwise everything would
        # look left out.
        from core.services.synthese import extractions_du_perimetre
        from front.tasks import _ecrire_le_corps_d_un_article

        with patch("front.tasks.enchainer_la_verification"):
            _ecrire_le_corps_d_un_article(
                self.page_du_wiki,
                f"## Le seuil\n\nLe seuil est acté."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]] "
                f"L'ajournement coûte."
                f"[[ext:{self.fixtures['extraction_cout'].pk}]]\n",
                set(
                    extractions_du_perimetre(self.page_du_wiki)
                    .values_list("pk", flat=True)
                ),
                motif_du_tour=MotifDeTourDeWiki.CREATION,
                wiki_du_tour=self.wiki,
            )
        # La creation est un vrai tour, mais chaque test part d'une
        # ardoise vide : il pose lui-meme ce qu'il veut raconter.
        # / Each test lays down its own history.
        TourDeWiki.objects.all().delete()

    def _un_tour_de_nuit(self, fait_par=None):
        """Un tour qui a REELLEMENT change l'article. / A real change."""
        return TourDeWiki.objects.create(
            wiki=self.wiki,
            numero_de_tour=self.wiki.tours_de_mise_a_jour + 1,
            fait_par=fait_par,
            motif=(
                MotifDeTourDeWiki.MAJ_NOCTURNE if fait_par is None
                else MotifDeTourDeWiki.MAJ_MANUELLE
            ),
            texte_avant="## Le seuil\n\nAvant.\n",
            texte_apres="## Le seuil\n\nAvant. Et un ajout.\n",
        )

    def _envoyer(self, **options):
        call_command(
            "envoyer_le_recapitulatif_du_matin", verbosity=0, **options,
        )


class LeMailSuitLaNuitTest(BaseDuRecapitulatif):
    """
    Une passe en cours retient le mail : il annonce le travail de la
    nuit, il ne peut donc pas partir avant sa fin.
    / A running pass holds the mail back.
    """

    def test_une_passe_en_cours_empeche_l_envoi(self):
        PasseDeNuit.objects.create()  # terminee_le reste NULL
        self._un_tour_de_nuit()

        with self.assertRaises(CommandError):
            self._envoyer(attendre_minutes=0)

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(EnvoiDuRecapitulatif.objects.exists())

    def test_une_passe_terminee_laisse_partir_le_mail(self):
        passe = PasseDeNuit.objects.create()
        passe.terminee_le = timezone.now()
        passe.save(update_fields=["terminee_le"])
        self._un_tour_de_nuit()

        self._envoyer(attendre_minutes=0)

        self.assertEqual(len(mail.outbox), 1)

    def test_l_envoi_force_passe_outre(self):
        # Un envoi a la main, quand quelqu'un sait ce qu'il fait.
        # / A manual send, for someone who knows what they are doing.
        PasseDeNuit.objects.create()
        self._un_tour_de_nuit()

        self._envoyer(attendre_minutes=0, sans_attendre_la_nuit=True)

        self.assertEqual(len(mail.outbox), 1)


class UnSeulMailParJourTest(BaseDuRecapitulatif):
    """La promesse Discourse. / The Discourse promise."""

    def test_un_seul_mail_pour_un_tour(self):
        self._un_tour_de_nuit()

        self._envoyer()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to, [self.proprietaire.email],
        )

    def test_relancer_le_meme_matin_n_envoie_rien(self):
        self._un_tour_de_nuit()

        self._envoyer()
        self._envoyer()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EnvoiDuRecapitulatif.objects.count(), 1)

    def test_rien_a_dire_rien_a_envoyer(self):
        self._envoyer()

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(EnvoiDuRecapitulatif.objects.exists())

    def test_un_tour_qui_n_a_rien_change_ne_fait_pas_un_mail(self):
        # Un lot entierement rejete est un fait d'histoire, pas une
        # nouvelle a annoncer. / A fully rejected batch is not news.
        TourDeWiki.objects.create(
            wiki=self.wiki, numero_de_tour=1,
            motif=MotifDeTourDeWiki.MAJ_NOCTURNE,
            texte_avant="## Le seuil\n\nRien n'a bougé.\n",
            texte_apres="## Le seuil\n\nRien n'a bougé.\n",
        )

        self._envoyer()

        self.assertEqual(len(mail.outbox), 0)

    def test_une_reparation_de_titres_ne_fait_pas_un_mail(self):
        # Elle change le texte, mais pas ce que l'article DIT :
        # l'annoncer userait le mail sans rien apprendre.
        # / It changes the text, not what the article says.
        TourDeWiki.objects.create(
            wiki=self.wiki, numero_de_tour=2,
            motif=MotifDeTourDeWiki.REPARATION_DE_TITRES,
            texte_avant="### Le seuil\n\nActé.\n",
            texte_apres="## Le seuil\n\nActé.\n",
        )

        self._envoyer()

        self.assertEqual(len(mail.outbox), 0)

    def test_un_tour_plus_vieux_que_la_borne_n_est_pas_reraconte(self):
        tour = self._un_tour_de_nuit()
        TourDeWiki.objects.filter(pk=tour.pk).update(
            fait_le=timezone.now() - timedelta(days=3),
        )

        self._envoyer()

        self.assertEqual(len(mail.outbox), 0)


class CeQueDitLeMailTest(BaseDuRecapitulatif):
    """Le contenu : qui a modifie quoi. / The content: who changed what."""

    def test_le_mail_distingue_le_moteur_d_un_humain(self):
        self._un_tour_de_nuit()

        self._envoyer()

        corps = mail.outbox[0].body
        self.assertIn("Le seuil", corps)
        self.assertIn("moteur", corps.lower())

    def test_un_tour_humain_nomme_son_auteur(self):
        self._un_tour_de_nuit(fait_par=self.proprietaire)

        self._envoyer()

        self.assertIn(self.proprietaire.username, mail.outbox[0].body)

    def test_le_mail_porte_un_lien_vers_l_article(self):
        self._un_tour_de_nuit()

        self._envoyer()

        self.assertIn(f"/wikis/{self.wiki.pk}/", mail.outbox[0].body)

    def test_le_neuf_non_repris_est_annonce_sans_aucun_tour(self):
        # L'article est a jour : rien a dire ce matin-la.
        # / The article is up to date: nothing to say.
        self._envoyer()
        self.assertEqual(len(mail.outbox), 0)

        # Une extraction arrive dans le perimetre, que l'article n'a pas
        # reprise : c'est une raison de revenir, et une seule fois.
        # / A new extraction the article has not taken up.
        from hypostasis_extractor.models import ExtractedEntity

        ExtractedEntity.objects.create(
            job=self.fixtures["job_analyse"], extraction_class="donnee",
            extraction_text="Un fait arrivé après.",
            start_char=53, end_char=74,
        )

        self._envoyer()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("pas encore repris", mail.outbox[0].body.lower())


class UnEssaiNEstPasUnEnvoiTest(BaseDuRecapitulatif):
    """
    `--adresse-de-test` eprouve la configuration SMTP et le rendu sans
    consommer la journee de personne.
    / A trial run must not consume anyone's daily mail.
    """

    def test_l_essai_part_a_l_adresse_donnee(self):
        self._un_tour_de_nuit()

        self._envoyer(adresse_de_test="essai@exemple.local")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["essai@exemple.local"])

    def test_l_essai_n_enregistre_aucun_envoi(self):
        # Sinon eprouver la configuration priverait quelqu'un de son
        # mail du lendemain. / Otherwise a test would steal a real mail.
        self._un_tour_de_nuit()

        self._envoyer(adresse_de_test="essai@exemple.local")

        self.assertFalse(EnvoiDuRecapitulatif.objects.exists())

    def test_apres_un_essai_le_vrai_mail_part_toujours(self):
        self._un_tour_de_nuit()

        self._envoyer(adresse_de_test="essai@exemple.local")
        self._envoyer()

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].to, [self.proprietaire.email])
        self.assertEqual(EnvoiDuRecapitulatif.objects.count(), 1)

    def test_un_essai_sans_matiere_n_envoie_rien(self):
        self._envoyer(adresse_de_test="essai@exemple.local")

        self.assertEqual(len(mail.outbox), 0)


class LesDestinatairesDuMailTest(BaseDuRecapitulatif):
    """Le collectif, pas seulement le proprietaire. / The whole group."""

    def test_une_lectrice_partagee_recoit_le_recapitulatif(self):
        from django.contrib.auth import get_user_model

        lectrice = get_user_model().objects.create_user(
            username="lectrice_du_matin", password="motdepasse",
            email="lectrice@exemple.local",
        )
        DossierPartage.objects.create(
            dossier=self.fixtures["carnet"], utilisateur=lectrice,
        )
        self._un_tour_de_nuit()

        self._envoyer()

        adresses = sorted(
            adresse for message in mail.outbox for adresse in message.to
        )
        self.assertEqual(
            adresses, ["lectrice@exemple.local", "proprietaire@exemple.local"],
        )

    def test_un_envoi_qui_echoue_n_arrete_pas_les_autres(self):
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user(
            username="second_lecteur", password="motdepasse",
            email="second@exemple.local",
        )
        DossierPartage.objects.create(
            dossier=self.fixtures["carnet"],
            utilisateur=get_user_model().objects.get(
                username="second_lecteur",
            ),
        )
        self._un_tour_de_nuit()

        appels = {"nombre": 0}

        def _envoyer_en_echouant_une_fois(*arguments, **options):
            appels["nombre"] += 1
            if appels["nombre"] == 1:
                raise OSError("le serveur SMTP a refusé la connexion")
            return 1

        with patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=_envoyer_en_echouant_une_fois,
        ):
            self._envoyer()

        # Le second a bien ete tente malgre l'echec du premier.
        # / The second was attempted despite the first failure.
        self.assertEqual(appels["nombre"], 2)
        self.assertEqual(EnvoiDuRecapitulatif.objects.count(), 1)
