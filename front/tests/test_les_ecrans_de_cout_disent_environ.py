"""
Les confirmations d'analyse et de synthese : un cout annonce « environ »,
et un comptage qui ne tombe pas sur un jeton special.
/ Analysis and synthesis confirmations: "environ", and no crash on
special-token text.

LOCALISATION : front/tests/test_les_ecrans_de_cout_disent_environ.py

DEUX REGLES, LES MEMES QUE LA MODALE « Mettre a jour » d'un wiki :

- le montant est un ORDRE DE GRANDEUR, pas un plafond : la sortie est
  estimee, et les tokens de reflexion d'un modele absent de
  `MULTIPLICATEUR_THINKING` ne sont pas comptes. L'ecran dit « environ »,
  jamais « ≤ » ;
- le texte d'un jeton special (`<|endoftext|>`) se compte comme du
  texte. Par defaut tiktoken LEVE dessus : une note qui parle de
  tokenizers ferait tomber l'ecran en 500.
/ Order of magnitude, not a cap; special-token text is plain text.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import AIModel, Configuration, Dossier, Page
from hypostasis_extractor.models import (
    AnalyseurExample,
    AnalyseurSyntaxique,
    ExampleExtraction,
    ExtractedEntity,
    ExtractionJob,
    PromptPiece,
)

TEXTE_AVEC_UN_JETON_SPECIAL = (
    "Un modèle de langue s'arrête quand il rencontre <|endoftext|>."
)


def _configurer_un_modele_mock():
    # « mock » est la VALEUR du choix, presente dans la table de tarifs
    # a (0, 0) : le montant affiche est le plancher, 0,01 €.
    # / "mock" is priced (0, 0): the floor amount is displayed.
    modele_ia = AIModel.objects.create(
        name="Mock des ecrans de cout", model_choice="mock", is_active=True,
    )
    configuration = Configuration.get_solo()
    configuration.ai_active = True
    configuration.ai_model = modele_ia
    configuration.save()
    return modele_ia


class LaConfirmationDAnalyseTest(TestCase):
    """GET /lire/{pk}/previsualiser_analyse/."""

    def setUp(self):
        self.utilisateur = User.objects.create_user(
            username="ecran_cout_analyse", password="test1234",
        )
        self.client.force_login(self.utilisateur)
        _configurer_un_modele_mock()
        analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur des ecrans de cout", type_analyseur="analyser",
            is_active=True,
        )
        PromptPiece.objects.create(
            analyseur=analyseur, role="instruction",
            content="Tu es un analyseur de test.", order=0,
        )
        # Un analyseur sans exemple n'est pas « utilisable » : l'ecran
        # repondrait 400 (_analyseurs_extraction_utilisables).
        # / An analyzer without an example is not usable.
        exemple = AnalyseurExample.objects.create(
            analyseur=analyseur, name="Exemple",
            example_text="Texte d'exemple pour le few-shot.", order=0,
        )
        ExampleExtraction.objects.create(
            example=exemple, extraction_class="hypostase",
            extraction_text="Texte d'exemple", order=0,
        )

    def _lire_la_confirmation(self, texte):
        # Une page sans proprietaire ni carnet est lisible par tout
        # authentifie (voir Phase23PrevisualiserAnalyseViewTest).
        # / A page with no owner nor notebook is readable by any user.
        page = Page.objects.create(
            title="Page des ecrans de cout", text_readability=texte,
            html_readability=f"<p>{texte}</p>", source_type="file",
            status="completed",
        )
        return self.client.get(
            f"/lire/{page.pk}/previsualiser_analyse/", HTTP_HX_REQUEST="true",
        )

    def test_un_jeton_special_dans_la_note_ne_fait_pas_tomber_l_ecran(self):
        reponse = self._lire_la_confirmation(TEXTE_AVEC_UN_JETON_SPECIAL)

        # Le bloc d'estimation, et pas seulement un 200 : la vue a un
        # chemin « analyse deja en cours » qui rend 200 sans rien compter.
        # / The estimate block, not just a 200: an early exit returns 200.
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('data-testid="estimation-tokens"', reponse.content.decode())

    def test_le_montant_est_annonce_comme_un_ordre_de_grandeur(self):
        contenu = self._lire_la_confirmation(
            "Un texte ordinaire à analyser.",
        ).content.decode()

        self.assertIn("environ 0,01", contenu)
        self.assertNotIn("&le;", contenu)
        self.assertNotIn("≤", contenu)


class LaConfirmationDeSyntheseTest(TestCase):
    """GET /lire/{pk}/previsualiser_synthese/."""

    def setUp(self):
        self.utilisateur = User.objects.create_user(
            username="ecran_cout_synthese", password="test1234",
        )
        self.client.force_login(self.utilisateur)
        self.modele_ia = _configurer_un_modele_mock()
        AnalyseurSyntaxique.objects.create(
            name="Synthese des ecrans de cout", type_analyseur="synthetiser",
            est_par_defaut=True,
        )

    def _lire_la_confirmation(self, texte):
        carnet = Dossier.objects.create(
            name="Carnet des ecrans de cout", owner=self.utilisateur,
        )
        page = Page.objects.create(
            title="Page des ecrans de cout", dossier=carnet,
            owner=self.utilisateur, text_readability=texte,
            html_readability=f"<p>{texte}</p>",
        )
        job = ExtractionJob.objects.create(
            page=page, ai_model=self.modele_ia, status="completed",
            name="Analyse",
        )
        ExtractedEntity.objects.create(
            job=job, extraction_class="theorie", extraction_text=texte,
            start_char=0, end_char=5,
        )
        return self.client.get(
            f"/lire/{page.pk}/previsualiser_synthese/", HTTP_HX_REQUEST="true",
        )

    def test_un_jeton_special_dans_la_note_ne_fait_pas_tomber_l_ecran(self):
        reponse = self._lire_la_confirmation(TEXTE_AVEC_UN_JETON_SPECIAL)

        # Le bloc d'estimation, et pas seulement un 200 : la vue a un
        # chemin « synthese deja en cours » qui rend 200 sans rien compter.
        # / The estimate block, not just a 200: an early exit returns 200.
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('data-testid="estimation-synthese"', reponse.content.decode())

    def test_le_montant_est_annonce_comme_un_ordre_de_grandeur(self):
        contenu = self._lire_la_confirmation(
            "Un texte ordinaire à synthétiser.",
        ).content.decode()

        self.assertIn("environ 0,01", contenu)
        self.assertNotIn("&le;", contenu)
        self.assertNotIn("≤", contenu)
