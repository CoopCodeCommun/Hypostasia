"""
Le controle d'acces de l'alignement cross-documents.
/ Access control for cross-document alignment.

LOCALISATION : front/tests/test_alignement_permissions.py

CE QUI EST VERROUILLE ICI. `/alignement/tableau/` et
`/alignement/export_markdown/` ne verifiaient AUCUNE permission
(correctif du 9 aout 2026) : `?dossier_id=N` alignait n'importe quel
carnet et `?page_ids=1,2` n'importe quelles notes, par leur simple
identifiant. Le tableau produit affiche le TEXTE des extractions et
leurs resumes, et l'export en fait un fichier telechargeable : c'etait
une fuite directe du contenu prive d'autrui.

Deux exigences distinctes sont testees :
1. le contenu inaccessible ne sort pas ;
2. la reponse ne permet pas de DEDUIRE qu'une note existe — une note
   interdite est traitee exactement comme une note absente. C'est la
   doctrine du 404 plutot que du 403 deja retenue pour les bases
   privees (phase H corpus).
/ Two separate requirements: private content must not leak, and the
answer must not let a caller tell "forbidden" from "missing".
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page, VisibiliteDossier
from core.services.corpus import ranger_une_note_dans_un_carnet
from hypostasis_extractor.models import (
    ExtractedEntity,
    ExtractionJob,
    HypostasisTag,
)

Utilisateur = get_user_model()


def _creer_une_note(suffixe, titre, owner=None):
    return Page.objects.create(
        url=f"https://exemple.test/{suffixe}",
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="Le texte de la note.",
        content_hash=f"hash-{suffixe}",
        owner=owner,
        title=titre,
    )


class AlignementPermissionsTest(TestCase):
    """Personne ne lit par l'alignement ce qu'il ne peut pas lire ailleurs."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            "proprio_align", "proprio@exemple.test", "motdepasse123",
        )
        self.intrus = Utilisateur.objects.create_user(
            "intrus_align", "intrus@exemple.test", "motdepasse123",
        )

        # Un carnet PRIVE avec deux notes : le materiau interdit.
        # / A PRIVATE notebook with two notes: the forbidden material.
        self.carnet_prive = Dossier.objects.create(
            name="Carnet prive", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.note_privee_une = _creer_une_note(
            "privee-1", "Secret industriel", owner=self.proprietaire,
        )
        self.note_privee_deux = _creer_une_note(
            "privee-2", "Second secret", owner=self.proprietaire,
        )
        for note in (self.note_privee_une, self.note_privee_deux):
            ranger_une_note_dans_un_carnet(
                note, self.carnet_prive, utilisateur=self.proprietaire,
            )

        # Un carnet PUBLIC avec deux notes : le materiau autorise.
        self.carnet_public = Dossier.objects.create(
            name="Carnet public", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.note_publique_une = _creer_une_note(
            "publique-1", "Note publique", owner=self.proprietaire,
        )
        self.note_publique_deux = _creer_une_note(
            "publique-2", "Autre note publique", owner=self.proprietaire,
        )
        for note in (self.note_publique_une, self.note_publique_deux):
            ranger_une_note_dans_un_carnet(
                note, self.carnet_public, utilisateur=self.proprietaire,
            )

        # CHAQUE note porte une extraction : sans elle le tableau
        # d'alignement est vide et n'affiche meme pas les titres de
        # colonnes — un test « le contenu ne fuit pas » passerait alors
        # pour de mauvaises raisons, et un test « le contenu sort bien »
        # echouerait a tort. / Every note gets an extraction: an empty
        # table shows no column titles at all, which would make the
        # leak test pass for the wrong reason.
        self.etiquette = HypostasisTag.objects.create(
            name="axiome", description="pour le test",
        )
        self.textes_d_extraction = {
            self.note_privee_une: "LE-SECRET-A-NE-PAS-FUITER",
            self.note_privee_deux: "SECOND-SECRET-A-NE-PAS-FUITER",
            self.note_publique_une: "extrait public un",
            self.note_publique_deux: "extrait public deux",
        }
        for note, texte in self.textes_d_extraction.items():
            job = ExtractionJob.objects.create(page=note, status="completed")
            ExtractedEntity.objects.create(
                job=job, hypostasis_tag=self.etiquette,
                extraction_text=texte, start_char=0, end_char=10,
                # L'alignement lit les hypostases dans attributes, PAS
                # dans hypostasis_tag (views_alignement.py,
                # _extraire_hypostases_de_entite) : sans cette cle,
                # l'entite existe mais le tableau reste vide.
                # / Alignment reads hypostases from `attributes`.
                attributes={"hypostases": "axiome"},
            )

    # --- Mode dossier_id -------------------------------------------------

    def test_carnet_prive_inaccessible_repond_comme_un_carnet_absent(self):
        """404, et le MEME message qu'un carnet inexistant."""
        self.client.force_login(self.intrus)
        reponse_interdite = self.client.get(
            f"/alignement/tableau/?dossier_id={self.carnet_prive.pk}"
        )
        reponse_absente = self.client.get("/alignement/tableau/?dossier_id=999999")

        self.assertEqual(reponse_interdite.status_code, 404)
        self.assertEqual(reponse_absente.status_code, 404)
        # L'octet pres : une difference de message serait un oracle.
        # / Byte for byte: a different message would be an oracle.
        self.assertEqual(reponse_interdite.content, reponse_absente.content)

    def test_carnet_prive_refuse_a_l_anonyme(self):
        reponse = self.client.get(
            f"/alignement/tableau/?dossier_id={self.carnet_prive.pk}"
        )
        self.assertEqual(reponse.status_code, 404)

    def test_carnet_public_reste_alignable(self):
        """Le correctif ne ferme pas ce qui doit rester ouvert."""
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            f"/alignement/tableau/?dossier_id={self.carnet_public.pk}"
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Note publique", contenu)
        self.assertIn("extrait public un", contenu)

    def test_le_proprietaire_aligne_toujours_son_carnet_prive(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.get(
            f"/alignement/tableau/?dossier_id={self.carnet_prive.pk}"
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Secret industriel", contenu)
        self.assertIn("LE-SECRET-A-NE-PAS-FUITER", contenu)

    # --- Mode page_ids ---------------------------------------------------

    def test_page_ids_ne_permet_pas_d_aligner_des_notes_privees(self):
        """Le vecteur le plus grave : deux identifiants suffisaient."""
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            "/alignement/tableau/?page_ids="
            f"{self.note_privee_une.pk},{self.note_privee_deux.pk}"
        )
        self.assertEqual(reponse.status_code, 400)
        contenu = reponse.content.decode()
        self.assertNotIn("Secret industriel", contenu)
        self.assertNotIn("LE-SECRET-A-NE-PAS-FUITER", contenu)

    def test_page_ids_melange_ne_laisse_pas_passer_la_privee(self):
        """Une note interdite glissee parmi des notes permises est retiree.

        Il reste alors moins de deux pages : la comparaison n'a plus
        d'objet et la reponse est la meme que pour des pages absentes.
        / The forbidden note is dropped, leaving fewer than two pages.
        """
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            "/alignement/tableau/?page_ids="
            f"{self.note_publique_une.pk},{self.note_privee_une.pk}"
        )
        self.assertNotIn("Secret industriel", reponse.content.decode())

    def test_page_ids_interdites_repond_comme_des_pages_absentes(self):
        """Aucun moyen de deduire l'existence des notes visees."""
        self.client.force_login(self.intrus)
        reponse_interdite = self.client.get(
            "/alignement/tableau/?page_ids="
            f"{self.note_privee_une.pk},{self.note_privee_deux.pk}"
        )
        reponse_absente = self.client.get(
            "/alignement/tableau/?page_ids=999998,999999"
        )
        self.assertEqual(
            reponse_interdite.status_code, reponse_absente.status_code
        )
        self.assertEqual(reponse_interdite.content, reponse_absente.content)

    def test_page_ids_publiques_restent_alignables(self):
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            "/alignement/tableau/?page_ids="
            f"{self.note_publique_une.pk},{self.note_publique_deux.pk}"
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Note publique", reponse.content.decode())

    # --- L'export : meme porte, meme serrure -----------------------------

    def test_export_markdown_ne_fuit_pas_par_dossier_id(self):
        """L'export passe par le meme filtre — sinon la fuite se
        telechargerait. / The export shares the filter."""
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            f"/alignement/export_markdown/?dossier_id={self.carnet_prive.pk}"
        )
        self.assertEqual(reponse.status_code, 404)
        self.assertNotIn("Secret industriel", reponse.content.decode())

    def test_export_markdown_ne_fuit_pas_par_page_ids(self):
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            "/alignement/export_markdown/?page_ids="
            f"{self.note_privee_une.pk},{self.note_privee_deux.pk}"
        )
        self.assertEqual(reponse.status_code, 400)
        contenu = reponse.content.decode()
        self.assertNotIn("Secret industriel", contenu)
        self.assertNotIn("LE-SECRET-A-NE-PAS-FUITER", contenu)

    # --- Le cas du superuser ---------------------------------------------

    def test_le_superuser_garde_son_acces_en_lecture(self):
        """La regle de lecture du produit accorde un bypass au superuser
        (_utilisateur_a_acces_page) : l'alignement ne doit pas etre plus
        strict que le reste, sinon il devient incoherent.
        / Alignment must not be stricter than the rest of the product.
        """
        administrateur = Utilisateur.objects.create_superuser(
            "admin_align", "admin@exemple.test", "motdepasse123",
        )
        self.client.force_login(administrateur)
        reponse = self.client.get(
            f"/alignement/tableau/?dossier_id={self.carnet_prive.pk}"
        )
        self.assertEqual(reponse.status_code, 200)
