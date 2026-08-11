"""
Le retour visuel des productions asynchrones (frictions F1, F2, F3 de
la recette connectee du 10 aout 2026).
/ Visual feedback for async productions.

LOCALISATION : front/tests/test_retour_de_production.py

CE QUI EST VERROUILLE ICI.
- F1 : lancer une production (wiki, synthese) renvoyait LA LISTE. Le
  nouvel objet y apparaissait comme s'il etait fini — « tour 1 ·
  0 sources » — alors que la tache venait de partir. Rien ne disait
  d'attendre, rien ne se rafraichissait : l'utilisateur recliquait.
- F2 : la verification affichait « Verification lancee… » et ce
  message ne partait JAMAIS, faute d'interrogation. Les verdicts
  n'apparaissaient qu'apres un rechargement manuel que rien ne
  suggerait.
- F3 : le formulaire d'application du diff visait
  `#corpus-panneau-onglet`, qui n'existe QUE dans l'onglet du carnet.
  Depuis /wikis/{id}/ — lien partage, F5 — « Appliquer » ne faisait
  rien.
/ Productions returned the list (looking finished), verification never
announced completion, and "apply" targeted an id absent from the
direct-URL page.

Les tests ne lancent AUCUNE tache reelle : ils creent les jobs a la
main et pilotent leur statut. / No real task is launched.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Dossier,
    Page,
    TypeDeNote,
    VisibiliteDossier,
    Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from hypostasis_extractor.models import ExtractionJob, ExtractionJobStatus

Utilisateur = get_user_model()


class RetourDeProductionTest(TestCase):
    """Une production dit qu'elle tourne, et dit quand elle a fini."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            "proprio_prod", "proprio-prod@exemple.test", "motdepasse123",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet de production", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        # Une note source, sinon le carnet n'a rien a synthetiser.
        self.note = Page.objects.create(
            url="https://exemple.test/source-production",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="Un texte de source.",
            content_hash="hash-source-production",
            owner=self.proprietaire, title="Note source",
        )
        ranger_une_note_dans_un_carnet(
            self.note, self.carnet, utilisateur=self.proprietaire,
        )
        self.client.force_login(self.proprietaire)

    def _creer_un_wiki_avec_son_job(self, statut):
        page_d_article = Page.objects.create(
            title="Wiki — sujet de test", text_readability="",
            html_readability="", html_original="", content_hash="",
            type_de_note=TypeDeNote.WIKI, owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            page_d_article, self.carnet, utilisateur=self.proprietaire,
        )
        wiki = Wiki.objects.create(
            page=page_d_article, dossier=self.carnet, sujet="sujet de test",
        )
        job = ExtractionJob.objects.create(
            page=page_d_article, name="Wiki — sujet de test", status=statut,
            raw_result={"est_wiki": True, "wiki_id": wiki.pk},
        )
        return wiki, job

    # --- F1 : la production annonce qu'elle tourne -----------------------

    def test_creer_un_wiki_ne_renvoie_plus_la_liste_muette(self):
        """La reponse annonce la production au lieu de la faire croire finie."""
        reponse = self.client.post(
            f"/carnets/{self.carnet.pk}/wikis/",
            {"sujet": "La gouvernance des communs"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("synthese-tache-lancee", contenu,
                      "La creation ne rend pas d'etat de tache")
        # Et surtout : PAS la liste, qui montrerait un wiki « fini ».
        self.assertNotIn("synthese-liste-wikis", contenu,
                         "La creation renvoie encore la liste muette")

    def test_l_etat_s_interroge_lui_meme_tant_que_la_tache_tourne(self):
        wiki, job = self._creer_un_wiki_avec_son_job(
            ExtractionJobStatus.PENDING,
        )
        reponse = self.client.get(
            f"/wikis/{wiki.pk}/etat/?job_id={job.pk}", HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()
        self.assertIn("hx-get=", contenu, "L'etat ne se re-interroge pas")
        self.assertIn(f"job_id={job.pk}", contenu)
        self.assertIn("essais=1", contenu, "Le compteur d'essais est absent")

    def test_l_etat_rend_la_liste_quand_la_production_est_finie(self):
        wiki, job = self._creer_un_wiki_avec_son_job(
            ExtractionJobStatus.COMPLETED,
        )
        reponse = self.client.get(
            f"/wikis/{wiki.pk}/etat/?job_id={job.pk}", HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("synthese-liste-wikis", reponse.content.decode())

    def test_l_interrogation_s_arrete_au_lieu_de_boucler_sans_fin(self):
        """Un worker mort doit produire un MESSAGE, pas un poll infini."""
        wiki, job = self._creer_un_wiki_avec_son_job(
            ExtractionJobStatus.PENDING,
        )
        reponse = self.client.get(
            f"/wikis/{wiki.pk}/etat/?job_id={job.pk}&essais=101",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()
        self.assertIn("plus de temps que prévu", contenu)
        self.assertNotIn("hx-get=", contenu,
                         "L'etat continue d'interroger au-dela du plafond")

    def test_une_tache_en_erreur_le_dit_et_rassure(self):
        wiki, job = self._creer_un_wiki_avec_son_job(ExtractionJobStatus.ERROR)
        reponse = self.client.get(
            f"/wikis/{wiki.pk}/etat/?job_id={job.pk}", HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()
        self.assertIn("échoué", contenu)
        # L'apostrophe est echappee par Django (&#x27;) : on cherche les
        # deux moities du message plutot que la chaine litterale.
        # / Django escapes the apostrophe; match around it.
        self.assertIn("Rien n", contenu)
        self.assertIn("a été modifié", contenu)

    def test_un_job_d_une_autre_page_n_est_pas_suivi(self):
        """On ne suit pas la tache d'un article qui n'est pas le sien."""
        wiki, _ = self._creer_un_wiki_avec_son_job(ExtractionJobStatus.PENDING)
        job_etranger = ExtractionJob.objects.create(
            page=self.note, name="Job d'une autre page", status="pending",
        )
        reponse = self.client.get(
            f"/wikis/{wiki.pk}/etat/?job_id={job_etranger.pk}",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 404)

    def test_l_etat_exige_l_acces_a_l_article(self):
        wiki, job = self._creer_un_wiki_avec_son_job(
            ExtractionJobStatus.PENDING,
        )
        self.client.logout()
        intrus = Utilisateur.objects.create_user(
            "intrus_prod", "intrus-prod@exemple.test", "motdepasse123",
        )
        self.client.force_login(intrus)
        reponse = self.client.get(
            f"/wikis/{wiki.pk}/etat/?job_id={job.pk}", HTTP_HX_REQUEST="true",
        )
        self.assertIn(reponse.status_code, (403, 404))

    # --- F2 : la verification finit par le dire --------------------------

    def test_la_verification_s_interroge_et_rendra_l_article(self):
        wiki, _ = self._creer_un_wiki_avec_son_job(ExtractionJobStatus.PENDING)
        reponse = self.client.post(
            f"/wikis/{wiki.pk}/verifier/", HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()
        self.assertIn("synthese-tache-lancee", contenu)
        self.assertIn("hx-get=", contenu,
                      "La verification n'annonce toujours pas sa fin")
        self.assertIn("apres=article", contenu,
                      "La verification doit rendre l'ARTICLE, pas la liste")

    def test_l_etat_rend_l_article_apres_une_verification(self):
        wiki, job = self._creer_un_wiki_avec_son_job(
            ExtractionJobStatus.COMPLETED,
        )
        reponse = self.client.get(
            f"/wikis/{wiki.pk}/etat/?job_id={job.pk}&apres=article",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("synthese-article", reponse.content.decode())

    # --- F3 : appliquer marche aussi depuis l'URL directe ----------------

    def test_le_formulaire_d_application_ne_vise_plus_un_id_absent(self):
        """`#corpus-panneau-onglet` n'existe pas sur /wikis/{id}/.

        Le gabarit doit viser l'article, present dans les DEUX
        contextes. / The target must exist on the direct URL too.
        """
        from pathlib import Path

        from django.conf import settings

        gabarit = (
            Path(settings.BASE_DIR) / "front" / "templates" / "front"
            / "corpus" / "partials" / "diff_operations.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn('hx-target="#corpus-panneau-onglet"', gabarit,
                         "Le formulaire vise encore un id absent en accès direct")
        self.assertIn("synthese-article", gabarit,
                      "Le formulaire ne vise pas l'article")
