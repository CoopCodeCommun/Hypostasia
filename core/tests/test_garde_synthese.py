"""
Tests du blocage d'edition d'une source citee (SPEC-synthese § 5,
phase E).
/ Edit-blocking tests for cited sources (phase E).

LOCALISATION : core/tests/test_garde_synthese.py

La regle : editer un ElementDocument qui porte une portion d'une
extraction citee par une synthese DIRIGEE est refuse — la preuve d'un
acte adopte ne bouge pas. Un wiki, lui, ne bloque rien : il est vivant,
sa prochaine mise a jour corrige.
/ Editing an element cited by a FROZEN synthesis is refused; a wiki
never blocks.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Dossier, ElementDocument, Page, SyntheseDirigee, TypeDeNote, Wiki,
    empreinte_du_texte,
)
from core.services.synthese import indexer_les_citations
from hypostasis_extractor.models import (
    AncrageExtraction, ExtractedEntity, ExtractionJob,
)

Utilisateur = get_user_model()


def creer_une_page(url_unique, **champs):
    """Cree une page minimale. / Minimal page."""
    champs.setdefault("title", f"Note {url_unique[-12:]}")
    return Page.objects.create(
        url=url_unique,
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="texte",
        content_hash=f"hash-{url_unique}",
        **champs,
    )


class GardeSyntheseTest(TestCase):
    """§ 5.1 : la dirigee bloque, le wiki non. / Frozen blocks, wiki not."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="gardien_test", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet garde E", owner=self.proprietaire,
        )
        self.note_source = creer_une_page("http://exemple.local/se-source")
        self.element = ElementDocument.objects.create(
            page=self.note_source, ordre=0, label="text",
            texte="le passage cite par la synthese",
            empreinte_contenu=empreinte_du_texte(
                "le passage cite par la synthese",
            ),
        )
        job = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse garde",
            status="completed", ai_model=None,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=job, extraction_class="argument",
            extraction_text="le passage cite",
            start_char=0, end_char=15,
        )
        AncrageExtraction.objects.create(
            extraction=self.extraction, element=self.element,
            ordre_dans_extraction=0, debut_dans_element=0,
            fin_dans_element=15,
        )

    def _faire_citer_par(self, type_de_note, titre):
        """Cree l'article citant et indexe la citation. / Citing article."""
        article = creer_une_page(
            f"http://exemple.local/se-{titre}", type_de_note=type_de_note,
            title=titre,
        )
        if type_de_note == TypeDeNote.SYNTHESE:
            SyntheseDirigee.objects.create(
                page=article, dossier=self.carnet,
                produite_par=self.proprietaire,
            )
        else:
            Wiki.objects.create(
                page=article, dossier=self.carnet, sujet=titre,
            )
        indexer_les_citations(
            article, f"Affirmation.[[ext:{self.extraction.pk}]]\n", None,
        )
        return article

    def test_editer_un_element_cite_par_une_dirigee_est_bloque(self):
        from hypostasis_extractor.services.garde_edition import (
            EditionBloqueeParUneSynthese,
        )
        from hypostasis_extractor.services.reconciliation import (
            reconcilier_les_portions_de_l_element,
        )

        self._faire_citer_par(TypeDeNote.SYNTHESE, "Synthese du 12 mars")

        with self.assertRaises(EditionBloqueeParUneSynthese) as contexte:
            reconcilier_les_portions_de_l_element(
                self.element, "le passage corrige par un editeur",
            )
        # § 5.3 : le refus NOMME ce qui bloque. / The refusal names it.
        self.assertIn("Synthese du 12 mars", str(contexte.exception))
        # Et rien n'a bouge. / And nothing moved.
        self.element.refresh_from_db()
        self.assertEqual(
            self.element.texte, "le passage cite par la synthese",
        )

    def test_editer_un_element_cite_par_un_wiki_est_permis(self):
        from hypostasis_extractor.services.reconciliation import (
            reconcilier_les_portions_de_l_element,
        )

        self._faire_citer_par(TypeDeNote.WIKI, "Wiki du seuil")

        resultat = reconcilier_les_portions_de_l_element(
            self.element, "le passage cite par la synthese, corrige",
        )

        self.element.refresh_from_db()
        self.assertIn("corrige", self.element.texte)
        self.assertIsInstance(resultat, dict)

    def test_le_blocage_couvre_tous_les_elements_d_une_extraction_M2M(self):
        # Une extraction a cheval sur 3 elements : la citer gele les 3 —
        # une preuve coupee en deux n'est plus une preuve (§ 5.1).
        # / One citation freezes every element the extraction spans.
        from hypostasis_extractor.services.garde_edition import (
            EditionBloqueeParUneSynthese,
            verifier_qu_aucune_synthese_ne_cite,
        )

        autres_elements = []
        for numero in (1, 2):
            element = ElementDocument.objects.create(
                page=self.note_source, ordre=numero, label="text",
                texte=f"suite du passage {numero}",
                empreinte_contenu=empreinte_du_texte(
                    f"suite du passage {numero}",
                ),
            )
            AncrageExtraction.objects.create(
                extraction=self.extraction, element=element,
                ordre_dans_extraction=numero, debut_dans_element=0,
                fin_dans_element=5,
            )
            autres_elements.append(element)

        self._faire_citer_par(TypeDeNote.SYNTHESE, "Synthese M2M")

        for element in [self.element] + autres_elements:
            with self.assertRaises(EditionBloqueeParUneSynthese):
                verifier_qu_aucune_synthese_ne_cite(element)

    def test_reconciliation_fonctionne_toujours(self):
        # Non-regression : un element NON cite s'edite librement.
        # / Non-regression: an uncited element edits freely.
        from hypostasis_extractor.services.reconciliation import (
            reconcilier_les_portions_de_l_element,
        )

        element_libre = ElementDocument.objects.create(
            page=self.note_source, ordre=5, label="text",
            texte="un element sans citation",
            empreinte_contenu=empreinte_du_texte("un element sans citation"),
        )

        resultat = reconcilier_les_portions_de_l_element(
            element_libre, "un element sans citation, modifie",
        )

        element_libre.refresh_from_db()
        self.assertIn("modifie", element_libre.texte)
        self.assertIsInstance(resultat, dict)

    def test_masquer_un_element_cite_par_une_dirigee_est_bloque(self):
        from hypostasis_extractor.services.garde_edition import (
            EditionBloqueeParUneSynthese,
        )
        from hypostasis_extractor.services.masquage import masquer_un_element

        self._faire_citer_par(TypeDeNote.SYNTHESE, "Synthese masquage")

        with self.assertRaises(EditionBloqueeParUneSynthese):
            masquer_un_element(self.element, "bruit", None)
        self.element.refresh_from_db()
        self.assertFalse(self.element.masque)

    def test_scinder_un_element_cite_par_une_dirigee_est_bloque(self):
        from hypostasis_extractor.services.garde_edition import (
            EditionBloqueeParUneSynthese,
        )
        from hypostasis_extractor.services.moteur_structure import (
            scinder_un_element,
        )

        self._faire_citer_par(TypeDeNote.SYNTHESE, "Synthese scission")

        with self.assertRaises(EditionBloqueeParUneSynthese):
            scinder_un_element(self.element, 10)

    def test_une_citation_d_un_autre_type_de_lien_ne_bloque_pas(self):
        # Seuls les liens CITE comptent : les liens de provenance du
        # versionnage historique (identique/modifie...) ne gelent rien.
        # / Only CITE links freeze; legacy provenance links do not.
        from core.models import SourceLink, TypeLien
        from hypostasis_extractor.services.garde_edition import (
            verifier_qu_aucune_synthese_ne_cite,
        )

        article = creer_une_page(
            "http://exemple.local/se-legacy",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        SourceLink.objects.create(
            page_cible=article, start_char_cible=0, end_char_cible=10,
            extraction_source=self.extraction,
            type_lien=TypeLien.IDENTIQUE,
        )

        # Ne doit PAS lever. / Must NOT raise.
        verifier_qu_aucune_synthese_ne_cite(self.element)


class CorrectifsRelectureGardeTest(TestCase):
    """
    Correctifs de la relecture E : demasquage permis (I1), fusion et
    reingestion testees (I4). / Review fixes: unhide allowed, merge and
    re-ingestion covered.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="gardien_e_test", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet garde E2", owner=self.proprietaire,
        )
        self.note_source = creer_une_page("http://exemple.local/se2-source")
        self.element = ElementDocument.objects.create(
            page=self.note_source, ordre=0, label="text",
            texte="le passage cite pour la garde",
            empreinte_contenu=empreinte_du_texte(
                "le passage cite pour la garde",
            ),
        )
        job = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse garde E2",
            status="completed", ai_model=None,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=job, extraction_class="argument",
            extraction_text="le passage cite",
            start_char=0, end_char=15,
        )
        self.portion = AncrageExtraction.objects.create(
            extraction=self.extraction, element=self.element,
            ordre_dans_extraction=0, debut_dans_element=0,
            fin_dans_element=15,
        )

    def _citer_par_une_dirigee(self, titre="Synthese garde E2"):
        article = creer_une_page(
            f"http://exemple.local/se2-{titre[-6:]}",
            type_de_note=TypeDeNote.SYNTHESE, title=titre,
        )
        SyntheseDirigee.objects.create(
            page=article, dossier=self.carnet,
            produite_par=self.proprietaire,
        )
        indexer_les_citations(
            article, f"Affirmation.[[ext:{self.extraction.pk}]]\n", None,
        )
        return article

    def test_demasquer_un_element_cite_est_permis(self):
        # I1 : le demasquage repasse des ancres de DETACHEE a ANCREE
        # apres verification du hash — il rend la preuve PLUS fidele.
        # Le bloquer enfermait l'utilisateur (element masque par erreur
        # puis cite : plus jamais demasquable). / Unhiding makes the
        # evidence MORE faithful; blocking it locked users out.
        from hypostasis_extractor.services.masquage import (
            demasquer_un_element, masquer_un_element,
        )

        masquer_un_element(self.element, "erreur de manipulation", None)
        self._citer_par_une_dirigee("Synthese demasquage")

        resultat = demasquer_un_element(self.element, "retour", None)

        self.element.refresh_from_db()
        self.assertFalse(self.element.masque)
        self.assertEqual(resultat["portions_rattachees"], 1)

    def test_fusionner_bloque_aussi_par_le_second_element(self):
        # I4 : la fusion touche les DEUX elements — une citation sur le
        # second suffit a refuser. / A citation on the SECOND element
        # alone refuses the merge.
        from hypostasis_extractor.services.garde_edition import (
            EditionBloqueeParUneSynthese,
        )
        from hypostasis_extractor.services.moteur_structure import (
            fusionner_deux_elements,
        )

        element_libre = ElementDocument.objects.create(
            page=self.note_source, ordre=1, label="text",
            texte="un element libre avant",
            empreinte_contenu=empreinte_du_texte("un element libre avant"),
        )
        self._citer_par_une_dirigee("Synthese fusion")

        # premier = libre, second = cite : le second refuse.
        with self.assertRaises(EditionBloqueeParUneSynthese):
            fusionner_deux_elements(element_libre, self.element)

    def test_la_reingestion_d_une_page_citee_est_refusee(self):
        from hypostasis_extractor.services.garde_edition import (
            EditionBloqueeParUneSynthese,
        )
        from hypostasis_extractor.services.reingestion import (
            reconcilier_les_elements_par_empreinte,
        )

        self._citer_par_une_dirigee("Synthese reingestion")

        with self.assertRaises(EditionBloqueeParUneSynthese):
            reconcilier_les_elements_par_empreinte(
                self.note_source,
                [{"texte": "nouveau contenu", "label": "text"}],
            )
