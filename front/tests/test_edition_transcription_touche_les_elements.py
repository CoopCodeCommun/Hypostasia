"""
L'edition de transcription refuse une note passee au moteur ELEMENT.
/ Transcript editing refuses a note that runs on the ELEMENT engine.

LOCALISATION : front/tests/test_edition_transcription_touche_les_elements.py

Les trois gestes — renommer un locuteur, modifier un bloc, supprimer un
bloc — appartiennent a l'ANCIENNE interface, celle du HTML diarise fige.
Ils reecrivent `transcription_raw`, le HTML et le texte plat, et le
lecteur ne rend AUCUN des trois : il rend les `ElementDocument`. Sur une
note a elements, ils annonçaient donc un succes sans rien changer de ce
que l'utilisateur voit.

POURQUOI ON REFUSE PLUTOT QUE DE CORRIGER LA CIBLE

Un premier correctif visait l'element par son `ordre`, en supposant
« bloc d'index N = element ordre N ». C'est FAUX : un BLOC groupe les
segments consecutifs d'un meme locuteur, alors que l'ingestion audio cree
UN ELEMENT PAR SEGMENT et saute les segments vides. La correspondance ne
tient que sur un corpus qui alterne les locuteurs — la fixture de dev,
precisement, ce qui la rendait invisible. Ailleurs, on ecrivait le texte
d'un locuteur dans l'element d'un AUTRE, et la reconciliation replaçait
les ancres sur un texte etranger.

S'y ajoute que ces gestes n'ont plus AUCUN declencheur dans l'interface :
le JS ecoute `.speaker-name`, `.texte-bloc-cliquable` et
`.btn-supprimer-bloc`, que le rendu par elements n'emet pas.

Le refus arrive AVANT toute ecriture : jamais de demi-etat.
/ Block index does not map to element order, and the UI cannot even
trigger these gestures anymore. Refuse before writing anything.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import ElementDocument, Page

Utilisateur = get_user_model()

SEGMENTS = [
    {"speaker": "Laurent", "text": "La première prise de parole.",
     "start": 0.0, "end": 10.0},
    {"speaker": "Eric", "text": "La deuxième prise de parole.",
     "start": 10.5, "end": 20.0},
]


class RefusSurUneNoteAElementsTest(TestCase):
    """Une note a elements refuse les trois gestes. / All three refused."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio_transcript", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)
        self.page = Page.objects.create(
            url="http://exemple.local/transcript",
            title="Débat enregistré", source_type="audio",
            html_original="", html_readability="",
            text_readability="", content_hash="hash-transcript",
            owner=self.proprietaire,
            transcription_raw={"segments": list(SEGMENTS)},
        )
        self.element = ElementDocument.objects.create(
            page=self.page, ordre=0, label="text",
            texte="La première prise de parole.",
            empreinte_contenu="t0",
            provenance={"debut": 0.0, "fin": 10.0, "locuteur": "Laurent"},
        )

    def test_renommer_un_locuteur_est_refuse(self):
        reponse = self.client.post(
            f"/lire/{self.page.pk}/renommer_locuteur/",
            {"ancien_nom": "Laurent", "nouveau_nom": "Laurent Dupont",
             "portee": "tous"},
        )

        self.assertEqual(reponse.status_code, 409)

    def test_editer_un_bloc_est_refuse(self):
        reponse = self.client.post(
            f"/lire/{self.page.pk}/editer_bloc/",
            {"index_bloc": 0, "nouveau_texte": "Un texte corrigé."},
        )

        self.assertEqual(reponse.status_code, 409)

    def test_supprimer_un_bloc_est_refuse(self):
        reponse = self.client.post(
            f"/lire/{self.page.pk}/supprimer_bloc/",
            {"index_bloc": 0},
        )

        self.assertEqual(reponse.status_code, 409)

    def test_le_refus_ne_laisse_AUCUN_demi_etat(self):
        # C'est le point qui compte : un refus tardif aurait ampute le
        # raw avant de lever. / A late refusal would have truncated the
        # raw transcript before raising.
        self.client.post(
            f"/lire/{self.page.pk}/supprimer_bloc/", {"index_bloc": 0},
        )
        self.page.refresh_from_db()
        self.element.refresh_from_db()

        self.assertEqual(
            self.page.transcription_raw.get("segments"), SEGMENTS,
            "la transcription brute a été modifiée malgré le refus",
        )
        self.assertFalse(self.element.masque)
        self.assertEqual(self.element.texte, "La première prise de parole.")
        self.assertEqual(
            self.element.provenance.get("locuteur"), "Laurent",
        )


class UneNoteSansElementResteEditableTest(TestCase):
    """
    Une page sans element garde ses gestes : rien n'est casse pour elle.
    / A page with no element keeps its gestures.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio_sans_element", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)
        self.page = Page.objects.create(
            url="http://exemple.local/transcript-legacy",
            title="Transcription héritée", source_type="audio",
            html_original="", html_readability="",
            text_readability="", content_hash="hash-legacy",
            owner=self.proprietaire,
            transcription_raw={"segments": list(SEGMENTS)},
        )

    def test_le_renommage_passe_encore(self):
        reponse = self.client.post(
            f"/lire/{self.page.pk}/renommer_locuteur/",
            {"ancien_nom": "Laurent", "nouveau_nom": "Laurent Dupont",
             "portee": "tous"},
        )

        self.assertNotEqual(reponse.status_code, 409)
        self.page.refresh_from_db()
        locuteurs = [
            segment.get("speaker")
            for segment in self.page.transcription_raw["segments"]
        ]
        self.assertIn("Laurent Dupont", locuteurs)
