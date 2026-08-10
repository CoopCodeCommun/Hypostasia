"""
La FAMILLE ENTIERE des endpoints non gardes (relecture du 10 aout).
/ The whole family of unguarded endpoints (Aug 10 adversarial review).

LOCALISATION : front/tests/test_permissions_famille.py

Le correctif du matin (drawer_contenu & co) a bouche 4 lecteurs — la
relecture adverse a montre que la famille n'etait PAS eteinte :
- des lecteurs ANONYMES rendaient le texte integral d'une note privee
  (`/lire/<pk>/exporter/`, `previsualiser_analyse` — le prompt complet
  contient tout le texte —, `telecharger_source`, `previsualiser_
  synthese`, les formulaires audio, `/questionnaire/?page_id=`) ;
- des ECRITURES auth-only sans droit d'objet (IDOR) : modifier le
  titre, reecrire une transcription, creer/supprimer des extractions,
  lancer une analyse LLM payante, commenter, promouvoir en exemple
  d'entrainement, et LIRE/MODIFIER les partages d'un dossier d'autrui.

Regles appliquees (memes helpers que le reste du produit) :
- lecture -> _verifier_acces_page (403, comme /lire/<pk>/ lui-meme) ;
  les endpoints a ?page_id= gardent la doctrine du 404 ;
- ecriture -> _utilisateur_peut_ecrire_page (403) ;
- destructif en masse (supprimer_ia) et promotion en entrainement ->
  proprietaire (_est_proprietaire_page), comme masquer/restaurer ;
- partages d'un dossier -> OWNER du dossier, comme renommer/detruire ;
- commenter / questionner -> ACCES en lecture (le debat est ouvert a
  qui peut lire — c'est le produit).
/ Read endpoints get the read rule; writes get the write rule;
mass-destructive and training promotion require ownership; sharing
requires folder ownership; commenting requires read access.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page, Question, VisibiliteDossier
from core.services.corpus import ranger_une_note_dans_un_carnet
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()


class BaseFamilleTest(TestCase):
    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            "proprio_famille", "p@exemple.test", "motdepasse123",
        )
        self.intrus = Utilisateur.objects.create_user(
            "intrus_famille", "i@exemple.test", "motdepasse123",
        )

        self.carnet_prive = Dossier.objects.create(
            name="Carnet prive famille", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.note_privee = Page.objects.create(
            url="https://exemple.test/famille-privee",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="Le texte secret de la note.",
            content_hash="hash-famille-privee",
            owner=self.proprietaire, title="Note privee",
        )
        ranger_une_note_dans_un_carnet(
            self.note_privee, self.carnet_prive,
            utilisateur=self.proprietaire,
        )
        job = ExtractionJob.objects.create(
            page=self.note_privee, status="completed",
        )
        self.extraction_privee = ExtractedEntity.objects.create(
            job=job, extraction_class="principe",
            extraction_text="texte secret", start_char=3, end_char=15,
        )

        self.carnet_public = Dossier.objects.create(
            name="Carnet public famille", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.note_publique = Page.objects.create(
            url="https://exemple.test/famille-publique",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="Un texte offert a tous.",
            content_hash="hash-famille-publique",
            owner=self.proprietaire, title="Note publique",
        )
        ranger_une_note_dans_un_carnet(
            self.note_publique, self.carnet_public,
            utilisateur=self.proprietaire,
        )
        job_public = ExtractionJob.objects.create(
            page=self.note_publique, status="completed",
        )
        self.extraction_publique = ExtractedEntity.objects.create(
            job=job_public, extraction_class="principe",
            extraction_text="texte offert", start_char=3, end_char=15,
        )


class LecteursAnonymesRestantsTest(BaseFamilleTest):
    """Les lecteurs de LectureViewSet refusent qui ne peut pas lire."""

    def _en_intrus(self):
        self.client.force_login(self.intrus)

    def test_exporter_est_garde(self):
        pk = self.note_privee.pk
        # Anonyme. / Anonymous.
        reponse = self.client.get(f"/lire/{pk}/exporter/?type_export=markdown")
        self.assertEqual(reponse.status_code, 403)
        self.assertNotIn(b"secret", reponse.content)
        # Intrus authentifie. / Authenticated outsider.
        self._en_intrus()
        reponse = self.client.get(f"/lire/{pk}/exporter/?type_export=markdown")
        self.assertEqual(reponse.status_code, 403)
        self.assertNotIn(b"secret", reponse.content)

    def test_exporter_marche_toujours_pour_le_proprietaire(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.get(
            f"/lire/{self.note_privee.pk}/exporter/?type_export=markdown",
        )
        self.assertEqual(reponse.status_code, 200)

    def test_telecharger_source_est_garde(self):
        self._en_intrus()
        reponse = self.client.get(
            f"/lire/{self.note_privee.pk}/telecharger_source/",
        )
        self.assertEqual(reponse.status_code, 403)

    def test_previsualiser_analyse_est_garde(self):
        # Le prompt complet contient TOUT le texte de la note : c'etait
        # la fuite la plus grave. / The full prompt embeds the whole
        # note text: the worst leak.
        self._en_intrus()
        reponse = self.client.get(
            f"/lire/{self.note_privee.pk}/previsualiser_analyse/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertNotIn(b"secret", reponse.content)

    def test_previsualiser_synthese_est_garde(self):
        self._en_intrus()
        reponse = self.client.get(
            f"/lire/{self.note_privee.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 403)

    def test_les_formulaires_audio_sont_gardes(self):
        self._en_intrus()
        reponse = self.client.get(
            f"/lire/{self.note_privee.pk}/formulaire_editer_bloc/",
        )
        self.assertEqual(reponse.status_code, 403)
        reponse = self.client.get(
            f"/lire/{self.note_privee.pk}/formulaire_renommer_locuteur/",
        )
        self.assertEqual(reponse.status_code, 403)


class QuestionnaireGardeTest(BaseFamilleTest):
    """Le questionnaire suit la regle d'acces, doctrine du 404."""

    def test_la_liste_d_une_note_interdite_est_introuvable(self):
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            f"/questionnaire/?page_id={self.note_privee.pk}",
        )
        self.assertEqual(reponse.status_code, 404)

    def test_la_liste_reste_ouverte_au_proprietaire(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.get(
            f"/questionnaire/?page_id={self.note_privee.pk}",
        )
        self.assertEqual(reponse.status_code, 200)

    def test_poser_une_question_exige_l_acces(self):
        self.client.force_login(self.intrus)
        reponse = self.client.post(
            "/questionnaire/poser_question/",
            {"page_id": self.note_privee.pk, "texte_question": "Une question ?"},
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(Question.objects.count(), 0)


class EcrituresSansDroitTest(BaseFamilleTest):
    """Les ecritures refusent qui ne peut pas ecrire la note."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.intrus)

    def test_modifier_titre_est_garde(self):
        reponse = self.client.post(
            f"/lire/{self.note_privee.pk}/modifier_titre/",
            {"titre": "Titre vole"},
        )
        self.assertEqual(reponse.status_code, 403)
        self.note_privee.refresh_from_db()
        self.assertEqual(self.note_privee.title, "Note privee")

    def test_les_ecritures_de_transcription_sont_gardees(self):
        for action in ("renommer_locuteur", "editer_bloc", "supprimer_bloc"):
            reponse = self.client.post(
                f"/lire/{self.note_privee.pk}/{action}/", {},
            )
            self.assertEqual(
                reponse.status_code, 403,
                f"{action} doit refuser un tiers sans droit",
            )

    def test_creer_manuelle_est_garde(self):
        reponse = self.client.post(
            "/extractions/creer_manuelle/",
            {"page_id": self.note_privee.pk, "text": "vol",
             "start_char": 0, "end_char": 3},
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(
            ExtractedEntity.objects.filter(
                job__page=self.note_privee,
            ).count(), 1,
        )

    def test_lancer_une_analyse_ia_est_garde(self):
        # Une analyse coute de l'argent ET lit la note : jamais pour un
        # tiers. / An analysis costs money AND reads the note.
        reponse = self.client.post(
            "/extractions/ia/",
            {"page_id": self.note_privee.pk, "text": "un texte"},
        )
        self.assertEqual(reponse.status_code, 403)

    def test_le_panneau_est_garde_en_lecture(self):
        reponse = self.client.post(
            "/extractions/panneau/", {"page_id": self.note_privee.pk},
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertNotIn(b"texte secret", reponse.content)

    def test_supprimer_ia_exige_le_proprietaire(self):
        reponse = self.client.post(
            "/extractions/supprimer_ia/", {"page_id": self.note_privee.pk},
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(
            ExtractedEntity.objects.filter(
                job__page=self.note_privee,
            ).count(), 1,
        )

    def test_promouvoir_en_entrainement_exige_le_proprietaire(self):
        reponse = self.client.post(
            "/extractions/promouvoir_entrainement/",
            {"page_id": self.note_privee.pk, "analyseur_id": 1},
        )
        self.assertEqual(reponse.status_code, 403)

    def test_commenter_exige_l_acces_en_lecture(self):
        # Note privee : refus. / Private note: refused.
        reponse = self.client.post(
            "/extractions/ajouter_commentaire/",
            {"entity_id": self.extraction_privee.pk, "commentaire": "hop"},
        )
        self.assertEqual(reponse.status_code, 403)
        # Note publique : le debat est ouvert a qui peut lire — pas de
        # 403. / Public note: readers can join the debate.
        reponse = self.client.post(
            "/extractions/ajouter_commentaire/",
            {"entity_id": self.extraction_publique.pk, "commentaire": "hop"},
        )
        self.assertNotEqual(reponse.status_code, 403)


class PartageDuDossierTest(BaseFamilleTest):
    """Les partages d'un dossier n'appartiennent qu'a son owner."""

    def test_lire_les_partages_d_autrui_est_refuse(self):
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            f"/dossiers/{self.carnet_prive.pk}/partager/",
        )
        self.assertEqual(reponse.status_code, 403)

    def test_modifier_les_partages_d_autrui_est_refuse(self):
        self.client.force_login(self.intrus)
        reponse = self.client.post(
            f"/dossiers/{self.carnet_prive.pk}/partager/",
            {"retirer_user_id": self.proprietaire.pk},
        )
        self.assertEqual(reponse.status_code, 403)

    def test_l_owner_gere_ses_partages(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.get(
            f"/dossiers/{self.carnet_prive.pk}/partager/",
        )
        self.assertEqual(reponse.status_code, 200)
