"""
La carte de preuve montre les CINQ juges, cote a cote.
/ The proof card shows all FIVE judges, side by side.

LOCALISATION : front/tests/test_les_cinq_juges_en_un_clic.py

POURQUOI CE TEST EXISTE. Le degre du juge de production et les avis des
quatre juges locaux vivaient dans DEUX BLOCS separes de la fiche : le
lecteur devait les rapprocher lui-meme, en memorisant un chiffre du haut
pour le comparer a quatre barres du bas.

Or c'est precisement la COMPARAISON qui rend la chose verifiable — les
juges locaux n'existent que pour controler le premier. Le renvoi signale
desormais leur desaccord par sa couleur ; la fiche doit permettre de
voir, en UN CLIC, qui dit quoi.

CE QUI NE CHANGE PAS : le bloc de production reste en tete, mis en
avant — c'est lui qui porte le verdict. Les cinq lignes de comparaison
s'ajoutent DANS le depliant, sans rien casser de ce que
`test_second_avis_a_l_ecran.py` verrouille.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AvisDeVerification, Configuration, EtatDeVerification, Page, SourceLink,
    TypeDeNote, TypeLien,
)


class LaCarteDePreuveMontreLesCinqJuges(TestCase):
    """Le juge de production entre dans la comparaison. / It joins in."""

    def setUp(self):
        from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

        self.utilisateur = get_user_model().objects.create_user(
            username="lecteur", password="motdepasse",
        )
        self.client.force_login(self.utilisateur)
        note = Page.objects.create(
            title="Note", owner=self.utilisateur, type_de_note=TypeDeNote.NOTE,
        )
        job = ExtractionJob.objects.create(page=note, status="completed")
        extraction = ExtractedEntity.objects.create(
            job=job, extraction_text="un passage", extraction_class="hypostase",
            start_char=0, end_char=10,
        )
        texte = f"Une affirmation sourcée [[ext:{extraction.pk}]]."
        article = Page.objects.create(
            title="Wiki", owner=self.utilisateur, type_de_note=TypeDeNote.WIKI,
            text_readability=texte,
        )
        self.lien = SourceLink.objects.create(
            page_cible=article, extraction_source=extraction,
            type_lien=TypeLien.CITE,
            start_char_cible=0, end_char_cible=len(texte),
            score_de_verification=70.0,
            etat_de_verification=EtatDeVerification.VERIFIE,
            verifie_par="mistral-small-latest",
        )
        for numero, score in enumerate([51.8, 50.0, 98.0, 57.0]):
            AvisDeVerification.objects.create(
                lien=self.lien, methode=f"xnli-directe v1 — juge {numero}",
                score=score, seuil=50.0,
            )
        Configuration.get_solo()

    def _fiche(self):
        return self.client.get(f"/citations/{self.lien.pk}/preuve/").content.decode()

    def test_le_juge_de_production_figure_dans_la_comparaison(self):
        """
        Le lecteur ne doit pas avoir a memoriser le chiffre du haut pour
        le comparer aux barres du bas.
        / The reader must not have to memorise the number above.
        """
        contenu = self._fiche()

        self.assertIn('data-testid="synthese-barre-juge-de-production"', contenu)

    def test_il_est_nomme_comme_LA_REFERENCE(self):
        """
        Cinq barres cote a cote sans hierarchie feraient croire a cinq
        juges egaux. Or les locaux se lisent A COTE du juge de
        production, JAMAIS a sa place (`core/models.py`).
        / Five equal-looking bars would suggest five equal judges.
        """
        contenu = self._fiche()

        self.assertIn("référence", contenu.lower())

    def test_les_quatre_juges_locaux_restent_affiches(self):
        """La comparaison n'a de sens qu'a cinq. / Five, or nothing."""
        contenu = self._fiche()

        self.assertEqual(contenu.count('data-testid="synthese-barre-avis-local"'), 4)

    def test_le_depliant_et_son_resume_d_accord_sont_intacts(self):
        """
        Ce que `test_second_avis_a_l_ecran.py` verrouille ne doit pas
        bouger : la comparaison s'AJOUTE, elle ne remplace rien.
        / The comparison is added; nothing is replaced.
        """
        contenu = self._fiche()

        self.assertIn('data-testid="synthese-avis-locaux"', contenu)
        self.assertIn("<details", contenu)
