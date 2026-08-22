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
    Dossier, DossierPartage, EnvoiDuRecapitulatif, MotifDeTourDeWiki, Page,
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
        self._vieillir_les_fixtures()

    def _vieillir_les_fixtures(self):
        """
        Recule les fixtures hors de la fenetre du recapitulatif.
        / Ages the fixtures out of the recap window.

        Le recapitulatif annonce les notes, les carnets et les
        extractions APPARUS depuis la borne. Les fixtures naissent a
        l'instant : sans ce recul, chaque test aurait « quelque chose a
        dire » avant meme d'avoir rien pose. Un carnet cree il y a
        trois jours n'est pas une nouvelle — c'est exactement ce que le
        recul represente.
        / Fixtures are born now; without ageing them, every test would
        have news before laying anything down.
        """
        from hypostasis_extractor.models import ExtractedEntity

        il_y_a_trois_jours = timezone.now() - timedelta(days=3)
        Dossier.objects.all().update(created_at=il_y_a_trois_jours)
        Page.objects.all().update(created_at=il_y_a_trois_jours)
        ExtractedEntity.objects.all().update(created_at=il_y_a_trois_jours)

    def _un_collegue(self, nom="collegue"):
        """
        Quelqu'un d'AUTRE que le destinataire.
        / Somebody other than the recipient.

        On ne s'annonce plus a soi-meme : un test qui cree un objet au
        nom du destinataire ne verifie donc plus rien. Le cas reel — et
        le seul interessant — est celui d'un geste fait par un autre.
        / One is no longer told what one did; the real case is someone
        else's gesture.
        """
        from django.contrib.auth import get_user_model

        utilisateur, _cree = get_user_model().objects.get_or_create(
            username=nom, defaults={"email": f"{nom}@exemple.local"},
        )
        return utilisateur

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
        # Un COLLEGUE, pas moi : on ne s'annonce plus ses propres
        # gestes. / A colleague, not me.
        collegue = self._un_collegue("collegue_qui_met_a_jour")

        self._un_tour_de_nuit(fait_par=collegue)

        self._envoyer()

        self.assertIn(collegue.username, mail.outbox[0].body)

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


class LesCinqRubriquesTest(BaseDuRecapitulatif):
    """
    Ce que le recapitulatif surveille, au-dela des wikis.
    / What the recap watches beyond wikis.
    """

    def _une_note_neuve(self, titre="Note arrivée ce matin"):
        # Deposee par un COLLEGUE : ses propres notes ne sont plus
        # annoncees a leur auteur. / Filed by a colleague.
        note = Page.objects.create(
            title=titre, text_readability="Du texte.",
            html_readability="<p>t</p>", html_original="<p>t</p>",
            content_hash=f"hash-{titre[:20]}",
            owner=self._un_collegue("collegue_qui_depose"),
        )
        ranger_une_note_dans_un_carnet(
            note, self.fixtures["carnet"], self.proprietaire,
        )
        return note

    def test_une_note_neuve_dans_mon_carnet_est_annoncee(self):
        note = self._une_note_neuve()

        self._envoyer()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(note.title, mail.outbox[0].body)
        self.assertIn(f"/lire/{note.pk}/", mail.outbox[0].body)

    def test_un_commentaire_neuf_porte_son_texte_et_son_auteur(self):
        # UN COMPTE NE DONNE ENVIE DE REPONDRE A PERSONNE.
        # / A count makes nobody want to answer.
        from django.contrib.auth import get_user_model
        from hypostasis_extractor.models import CommentaireExtraction

        commentatrice = get_user_model().objects.create_user(
            username="commentatrice", password="motdepasse",
            email="commentatrice@exemple.local",
        )
        CommentaireExtraction.objects.create(
            entity=self.fixtures["extraction_seuil"],
            user=commentatrice,
            commentaire="Ce seuil me paraît beaucoup trop bas.",
        )

        self._envoyer()

        corps = mail.outbox[0].body
        self.assertIn("Ce seuil me paraît beaucoup trop bas.", corps)
        self.assertIn("commentatrice", corps)

    def test_le_texte_brut_n_echappe_pas_les_apostrophes(self):
        # « C&#x27;est » sous les yeux du lecteur : Django echappe pour
        # le HTML, or rien n'est interprete dans un texte brut.
        # / Django escapes for HTML; nothing is interpreted in plain text.
        from django.contrib.auth import get_user_model
        from hypostasis_extractor.models import CommentaireExtraction

        quelqu_un = get_user_model().objects.create_user(
            username="apostrophe", password="motdepasse",
            email="apostrophe@exemple.local",
        )
        CommentaireExtraction.objects.create(
            entity=self.fixtures["extraction_seuil"], user=quelqu_un,
            commentaire="C'est exactement l'inverse qu'il faudrait dire.",
        )

        self._envoyer()

        corps = mail.outbox[0].body
        self.assertIn("C'est exactement l'inverse", corps)
        self.assertNotIn("&#x27;", corps)

    def test_le_html_echappe_le_contenu_d_utilisateur(self):
        # Un commentaire est du contenu d'utilisateur, et il serait
        # INTERPRETE dans la version HTML.
        # / A comment is user content and would render in the HTML part.
        from django.contrib.auth import get_user_model
        from hypostasis_extractor.models import CommentaireExtraction

        quelqu_un = get_user_model().objects.create_user(
            username="injecteur", password="motdepasse",
            email="injecteur@exemple.local",
        )
        CommentaireExtraction.objects.create(
            entity=self.fixtures["extraction_seuil"], user=quelqu_un,
            commentaire="<script>alert('bonjour')</script>",
        )

        self._envoyer()

        html = mail.outbox[0].alternatives[0][0]
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_un_commentaire_porte_un_bouton_reagir(self):
        from django.contrib.auth import get_user_model
        from hypostasis_extractor.models import CommentaireExtraction

        quelqu_un = get_user_model().objects.create_user(
            username="repondeur", password="motdepasse",
            email="repondeur@exemple.local",
        )
        CommentaireExtraction.objects.create(
            entity=self.fixtures["extraction_seuil"], user=quelqu_un,
            commentaire="Je ne suis pas d'accord.",
        )

        self._envoyer()

        note_commentee = self.fixtures["note_source"]
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Réagir", html)
        self.assertIn(f"/lire/{note_commentee.pk}/", html)

    def test_un_carnet_public_neuf_est_annonce(self):
        from django.contrib.auth import get_user_model
        from core.models import VisibiliteDossier

        quelqu_un_d_autre = get_user_model().objects.create_user(
            username="fondateur", password="motdepasse",
            email="fondateur@exemple.local",
        )
        carnet_public = Dossier.objects.create(
            name="Carnet public tout neuf", owner=quelqu_un_d_autre,
            visibilite=VisibiliteDossier.PUBLIC,
        )

        self._envoyer()

        corps = mail.outbox[0].body
        self.assertIn("Carnet public tout neuf", corps)
        self.assertIn(f"/carnets/{carnet_public.pk}/", corps)

    def test_mon_propre_carnet_public_ne_m_est_pas_annonce(self):
        # On ne s'annonce pas a soi-meme ce qu'on vient de creer.
        # / One does not announce one's own creation to oneself.
        from core.models import VisibiliteDossier

        Dossier.objects.create(
            name="Mon carnet public à moi", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )

        self._envoyer()

        if mail.outbox:
            self.assertNotIn("Mon carnet public à moi", mail.outbox[0].body)

    def test_un_wiki_neuf_est_annonce_comme_article(self):
        page_du_wiki = Page.objects.create(
            title="Wiki tout neuf", text_readability="## S\n\nDu texte.\n",
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-wiki-neuf", type_de_note=TypeDeNote.WIKI,
            owner=self._un_collegue("collegue_qui_ouvre_un_wiki"),
        )
        wiki_neuf = Wiki.objects.create(
            page=page_du_wiki, dossier=self.fixtures["carnet"],
            sujet="Un sujet fraîchement ouvert",
        )

        self._envoyer()

        corps = mail.outbox[0].body
        self.assertIn("Un sujet fraîchement ouvert", corps)
        self.assertIn(f"/wikis/{wiki_neuf.pk}/", corps)

    def test_une_synthese_neuve_est_annoncee_comme_article(self):
        from core.models import SyntheseDirigee

        page_de_synthese = Page.objects.create(
            title="Synthèse du 21 août", text_readability="Du texte.",
            html_readability="<p>s</p>", html_original="<p>s</p>",
            content_hash="hash-synthese-neuve",
            type_de_note=TypeDeNote.SYNTHESE,
            owner=self._un_collegue("collegue_qui_synthetise"),
        )
        dirigee = SyntheseDirigee.objects.create(
            page=page_de_synthese, dossier=self.fixtures["carnet"],
            produite_par=self._un_collegue("collegue_qui_synthetise"),
        )

        self._envoyer()

        corps = mail.outbox[0].body
        self.assertIn("Synthèse du 21 août", corps)
        self.assertIn(f"/syntheses/{dirigee.pk}/", corps)

    def test_une_note_d_un_carnet_qui_n_est_pas_le_mien_n_est_pas_annoncee(self):
        # Le perimetre du CONTENU, ce sont les carnets qu'on suit — pas
        # tous les publics du monde, sinon cent notes importees
        # arroseraient tout le monde.
        # / Followed notebooks only, or one import would spam everyone.
        from django.contrib.auth import get_user_model
        from core.models import VisibiliteDossier

        etranger = get_user_model().objects.create_user(
            username="etranger", password="motdepasse",
            email="etranger@exemple.local",
        )
        carnet_d_ailleurs = Dossier.objects.create(
            name="Carnet d'ailleurs", owner=etranger,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        note_d_ailleurs = Page.objects.create(
            title="Note qui ne me regarde pas",
            text_readability="Du texte.", html_readability="<p>t</p>",
            html_original="<p>t</p>", content_hash="hash-ailleurs",
            owner=etranger,
        )
        ranger_une_note_dans_un_carnet(
            note_d_ailleurs, carnet_d_ailleurs, etranger,
        )

        self._envoyer()

        mails_du_proprietaire = [
            message for message in mail.outbox
            if message.to == [self.proprietaire.email]
        ]
        if mails_du_proprietaire:
            self.assertNotIn(
                "Note qui ne me regarde pas", mails_du_proprietaire[0].body,
            )

    def test_le_titre_du_mail_parle_d_hypostasia_pas_de_mes_wikis(self):
        self._une_note_neuve()

        self._envoyer()

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Ce qui a bougé sur Hypostasia.org", html)


class UnParJourMecaniquementTest(BaseDuRecapitulatif):
    """
    La promesse ne tenait que par accident : elle tient maintenant par
    construction. / The promise held by accident; now it holds by
    construction.
    """

    def test_une_relance_apres_du_neuf_n_envoie_pas_un_second_mail(self):
        # LE TROU. Mail du matin ; un commentaire arrive dans la
        # journee ; quelqu'un relance la commande a la main : la
        # personne recevait un SECOND mail le meme jour.
        # / A comment arrives, someone re-runs, and a second mail left.
        from django.contrib.auth import get_user_model
        from hypostasis_extractor.models import CommentaireExtraction

        self._un_tour_de_nuit()
        self._envoyer()
        self.assertEqual(len(mail.outbox), 1)

        commentateur = get_user_model().objects.create_user(
            username="arrive_a_neuf_heures", password="motdepasse",
            email="neuf@exemple.local",
        )
        CommentaireExtraction.objects.create(
            entity=self.fixtures["extraction_seuil"], user=commentateur,
            commentaire="Une remarque de milieu de journée.",
        )

        self._envoyer()

        self.assertEqual(len(mail.outbox), 1)

    def test_forcer_leve_la_garde_pour_un_rattrapage(self):
        self._un_tour_de_nuit()
        self._envoyer()

        from django.contrib.auth import get_user_model
        from hypostasis_extractor.models import CommentaireExtraction

        quelqu_un = get_user_model().objects.create_user(
            username="rattrapage", password="motdepasse",
            email="rattrapage@exemple.local",
        )
        CommentaireExtraction.objects.create(
            entity=self.fixtures["extraction_seuil"], user=quelqu_un,
            commentaire="À rattraper.",
        )

        self._envoyer(forcer=True)

        self.assertEqual(len(mail.outbox), 2)


class LaBorneHauteTest(BaseDuRecapitulatif):
    """
    Ce qui naît pendant que les mails partent ne doit pas tomber dans
    un trou. / What is born while mails are sent must not fall in a hole.
    """

    def test_l_envoi_enregistre_l_instant_du_CALCUL_pas_celui_de_l_envoi(self):
        from core.models import EnvoiDuRecapitulatif

        self._un_tour_de_nuit()

        self._envoyer()

        envoi = EnvoiDuRecapitulatif.objects.get()
        self.assertIsNotNone(envoi.couvre_jusqu_a)
        # Le calcul precede l'envoi : la borne haute est ANTERIEURE a
        # l'heure d'envoi, et c'est tout l'objet du champ.
        # / The computation precedes the send.
        self.assertLessEqual(envoi.couvre_jusqu_a, envoi.envoye_le)

    def test_le_mail_suivant_repart_de_la_borne_haute(self):
        from core.models import EnvoiDuRecapitulatif
        from core.services.recapitulatif_du_matin import borne_du_destinataire

        self._un_tour_de_nuit()
        self._envoyer()

        envoi = EnvoiDuRecapitulatif.objects.get()
        self.assertEqual(
            borne_du_destinataire(self.proprietaire), envoi.couvre_jusqu_a,
        )


class OnNeSAnnoncePasASoiMemeTest(BaseDuRecapitulatif):
    """
    Le lendemain matin, l'auteur d'un geste le sait deja. Le lui
    raconter fait du recapitulatif un accuse de reception — et c'est
    l'utilisateur le plus actif qui recevrait le plus de bruit.
    / One already knows what one did: telling them makes the recap a
    receipt, and the most active user gets the most noise.
    """

    def _une_note_de(self, proprietaire, titre):
        note = Page.objects.create(
            title=titre, text_readability="Du texte.",
            html_readability="<p>t</p>", html_original="<p>t</p>",
            content_hash=f"hash-{titre[:24]}", owner=proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            note, self.fixtures["carnet"], self.proprietaire,
        )
        return note

    def _un_autre_utilisateur(self, nom):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(
            username=nom, password="motdepasse",
            email=f"{nom}@exemple.local",
        )

    def test_ma_propre_note_ne_m_est_pas_annoncee(self):
        self._une_note_de(self.proprietaire, "Note que j'ai écrite")
        self._une_note_de(
            self._un_autre_utilisateur("collegue_note"),
            "Note écrite par quelqu'un d'autre",
        )

        self._envoyer()

        corps = mail.outbox[0].body
        self.assertIn("Note écrite par quelqu'un d'autre", corps)
        self.assertNotIn("Note que j'ai écrite", corps)

    def test_mon_propre_commentaire_ne_m_est_pas_annonce(self):
        from hypostasis_extractor.models import CommentaireExtraction

        CommentaireExtraction.objects.create(
            entity=self.fixtures["extraction_seuil"],
            user=self.proprietaire,
            commentaire="Ma propre remarque, que je connais déjà.",
        )
        CommentaireExtraction.objects.create(
            entity=self.fixtures["extraction_seuil"],
            user=self._un_autre_utilisateur("collegue_commentaire"),
            commentaire="La remarque d'un autre, qui m'apprend quelque chose.",
        )

        self._envoyer()

        corps = mail.outbox[0].body
        self.assertIn("La remarque d'un autre", corps)
        self.assertNotIn("Ma propre remarque", corps)

    def test_mon_propre_tour_ne_m_est_pas_annonce(self):
        self._un_tour_de_nuit(fait_par=self.proprietaire)

        self._envoyer()

        self.assertEqual(len(mail.outbox), 0)

    def test_un_tour_du_MOTEUR_sur_mon_wiki_m_est_annonce(self):
        # Je ne l'ai pas decide : c'est meme la seule facon de
        # l'apprendre sans ouvrir l'article.
        # / I did not decide it; this is how I learn of it.
        self._un_tour_de_nuit(fait_par=None)

        self._envoyer()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("moteur", mail.outbox[0].body.lower())

    def test_le_tour_d_un_collegue_sur_mon_wiki_m_est_annonce(self):
        self._un_tour_de_nuit(
            fait_par=self._un_autre_utilisateur("collegue_tour"),
        )

        self._envoyer()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("collegue_tour", mail.outbox[0].body)

    def test_mon_propre_wiki_neuf_ne_m_est_pas_annonce(self):
        page_du_wiki = Page.objects.create(
            title="Wiki que j'ouvre moi-même",
            text_readability="## S\n\nDu texte.\n",
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-wiki-a-moi", type_de_note=TypeDeNote.WIKI,
            owner=self.proprietaire,
        )
        Wiki.objects.create(
            page=page_du_wiki, dossier=self.fixtures["carnet"],
            sujet="Un sujet que j'ouvre moi-même",
        )

        self._envoyer()

        if mail.outbox:
            self.assertNotIn(
                "Un sujet que j'ouvre moi-même", mail.outbox[0].body,
            )


class LaBorneImposeeTest(BaseDuRecapitulatif):
    """
    `--depuis-jours` sert a REGARDER, jamais a envoyer.
    / --depuis-jours is for looking, never for sending.
    """

    def test_elle_est_refusee_sur_un_envoi_reel(self):
        # Sinon tout le monde recevrait des semaines d'histoire deja lue.
        # / Otherwise everyone would get weeks of already-read history.
        with self.assertRaises(CommandError):
            self._envoyer(depuis_jours=30)

        self.assertEqual(len(mail.outbox), 0)

    def test_elle_remonte_le_temps_pour_un_essai(self):
        # Avec une borne a un jour, rien. Avec une borne a trente, ce
        # qui date de trois jours reapparait.
        # / One-day bound: nothing. Thirty-day bound: it comes back.

        # Une note d'un COLLEGUE, vieillie hors de la fenetre d'un
        # jour : seule une borne remontee la fait reapparaitre.
        # / A colleague's note, aged out of the one-day window.
        note_ancienne = Page.objects.create(
            title="Note déposée il y a trois jours",
            text_readability="Du texte.", html_readability="<p>t</p>",
            html_original="<p>t</p>", content_hash="hash-ancienne",
            owner=self._un_collegue("collegue_d_avant_hier"),
        )
        ranger_une_note_dans_un_carnet(
            note_ancienne, self.fixtures["carnet"], self.proprietaire,
        )
        Page.objects.filter(pk=note_ancienne.pk).update(
            created_at=timezone.now() - timedelta(days=3),
        )

        self._envoyer(adresse_de_test="essai@exemple.local")
        self.assertEqual(len(mail.outbox), 0)

        self._envoyer(
            adresse_de_test="essai@exemple.local", depuis_jours=30,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(note_ancienne.title, mail.outbox[0].body)
