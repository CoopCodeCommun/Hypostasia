"""
Tests du chunking aligne sur les elements — SPEC v2 section 4.1 (phase C).
/ Tests for element-aligned chunking — SPEC v2 section 4.1 (phase C).

LOCALISATION : hypostasis_extractor/tests/test_chunking_par_element.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor.tests.test_chunking_par_element

Les trois tests nommes dans la section 10 de la spec sont ici :
  - test_aucun_chunk_ne_coupe_un_element
  - test_preference_de_section_respecte_le_plancher
  - test_element_masque_absent_des_chunks
"""

from django.test import TestCase

from core.models import ElementDocument, Page, empreinte_du_texte
from hypostasis_extractor.services.ancrage import (
    SEPARATEUR_DE_JONCTION,
    decouper_le_span_en_portions_par_element,
)
from hypostasis_extractor.services.chunking import (
    BUDGET_MAXIMUM_PAR_CHUNK,
    PLANCHER_AVANT_COUPURE_PREFEREE,
    construire_les_chunks,
)


class BaseChunkingTestCase(TestCase):
    """Socle commun : une page vide, et de quoi lui ajouter des elements.
    / Common ground: an empty page, and helpers to add elements."""

    def setUp(self):
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-chunking",
            html_original="<p>original</p>",
            html_readability="<p>lisible</p>",
            text_readability="texte lisible",
            content_hash="empreinte_page_chunking",
            title="Page de test pour le chunking",
        )
        self.prochain_ordre = 0

    def _ajouter_un_element(self, texte, label="text", masque=False):
        """Ajoute un element a la suite sur la page de test.
        / Appends an element to the test page."""
        element = ElementDocument.objects.create(
            page=self.page_de_test,
            ordre=self.prochain_ordre,
            label=label,
            texte=texte,
            empreinte_contenu=empreinte_du_texte(texte),
            masque=masque,
        )
        self.prochain_ordre += 1
        return element

    def _elements_de_la_page(self):
        """Les elements dans l'ordre du document. / Elements in document order."""
        return list(self.page_de_test.elements.all())


class AlignementSurLesElementsTest(BaseChunkingTestCase):
    """
    La regle 1, obligatoire : on ne coupe jamais au milieu d'un element.
    / Rule 1, mandatory: never cut in the middle of an element.
    """

    def test_aucun_chunk_ne_coupe_un_element(self):
        """
        Invariant central (SPEC section 10) : sur un corpus qui depasse
        largement le budget, chaque element se retrouve ENTIER dans
        exactement un chunk.
        / Every element ends up WHOLE in exactly one chunk.
        """
        # 20 elements de 200 caracteres : 4000 caracteres au total, soit
        # plusieurs fois le budget de 1500.
        # / 20 elements of 200 chars: several times the budget.
        for numero in range(20):
            self._ajouter_un_element(f"Element numero {numero}. " + "x" * 180)

        chunks = construire_les_chunks(self._elements_de_la_page())

        self.assertGreater(len(chunks), 1, "le corpus doit produire plusieurs chunks")

        # Chaque element apparait une fois et une seule, en entier.
        # / Each element appears exactly once, whole.
        elements_vus = []
        for chunk in chunks:
            for element in chunk["elements"]:
                elements_vus.append(element.pk)
                # Le texte de l'element est present EN ENTIER dans le chunk.
                # / The element text is present WHOLE in the chunk.
                self.assertIn(element.texte, chunk["texte"])

        self.assertEqual(len(elements_vus), 20)
        self.assertEqual(len(set(elements_vus)), 20, "aucun element en double")

    def test_un_element_plus_gros_que_le_budget_part_entier(self):
        """
        Ecart assume : la regle 1 prime sur le budget. Un element qui
        depasse a lui seul le budget n'est pas coupe, il part seul — et
        l'element suivant n'est ni perdu ni colle avec lui.
        / Rule 1 wins over the budget, and the next element is not lost.
        """
        texte_enorme = "y" * (BUDGET_MAXIMUM_PAR_CHUNK * 2)
        element_enorme = self._ajouter_un_element(texte_enorme)
        element_suivant = self._ajouter_un_element("Un element normal apres le gros.")

        chunks = construire_les_chunks(self._elements_de_la_page())

        # Deux chunks : le gros seul, puis le suivant. Rien n'est perdu.
        # / Two chunks: the big one alone, then the next. Nothing is lost.
        self.assertEqual(len(chunks), 2)

        chunk_du_gros_element = chunks[0]
        self.assertEqual(chunk_du_gros_element["elements"], [element_enorme])
        self.assertEqual(chunk_du_gros_element["texte"], texte_enorme)
        # Le chunk depasse le budget, et c'est assume.
        # / The chunk exceeds the budget, and that is accepted.
        self.assertGreater(
            len(chunk_du_gros_element["texte"]), BUDGET_MAXIMUM_PAR_CHUNK,
        )
        # La table d'offsets d'un chunk mono-element est correcte aussi.
        # / The offsets table of a single-element chunk is correct too.
        self.assertEqual(
            chunk_du_gros_element["offsets"][element_enorme.pk],
            (0, len(texte_enorme)),
        )

        self.assertEqual(chunks[1]["elements"], [element_suivant])

    def test_un_chunk_pile_au_budget_n_est_pas_coupe(self):
        """
        Borne exacte : deux elements dont le total AVEC separateur fait
        pile le budget tiennent dans un seul chunk.
        / Exact bound: total WITH separator equal to the budget still fits.
        """
        longueur_du_premier = 748
        longueur_du_second = (
            BUDGET_MAXIMUM_PAR_CHUNK
            - longueur_du_premier
            - len(SEPARATEUR_DE_JONCTION)
        )
        self._ajouter_un_element("a" * longueur_du_premier)
        self._ajouter_un_element("b" * longueur_du_second)

        chunks = construire_les_chunks(self._elements_de_la_page())

        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]["texte"]), BUDGET_MAXIMUM_PAR_CHUNK)

    def test_un_caractere_de_plus_que_le_budget_coupe(self):
        """
        Borne exacte, l'autre cote : un caractere de plus et on coupe.
        Ce test verrouille la prise en compte du separateur dans le calcul
        — sans elle, le total serait sous-estime de 2 et ne couperait pas.
        / One character more and we cut. This locks separator accounting.
        """
        longueur_du_premier = 749
        longueur_du_second = (
            BUDGET_MAXIMUM_PAR_CHUNK
            - longueur_du_premier
            - len(SEPARATEUR_DE_JONCTION)
            + 1
        )
        self._ajouter_un_element("a" * longueur_du_premier)
        self._ajouter_un_element("b" * longueur_du_second)

        chunks = construire_les_chunks(self._elements_de_la_page())

        self.assertEqual(len(chunks), 2)

    def test_les_separateurs_comptent_dans_le_budget(self):
        """
        Verrouille explicitement le point precedent : un decoupage qui
        ignorerait les separateurs produirait un chunk plus gros que le
        budget. On verifie sur une serie ou les separateurs pesent.
        / A chunker ignoring separators would exceed the budget here.
        """
        # 15 elements de 100 caracteres : les 14 separateurs pesent 28
        # caracteres, assez pour changer le decoupage.
        # / 14 separators weigh 28 chars, enough to change the split.
        for numero in range(15):
            self._ajouter_un_element("c" * 100)

        chunks = construire_les_chunks(self._elements_de_la_page())

        for chunk in chunks:
            self.assertLessEqual(len(chunk["texte"]), BUDGET_MAXIMUM_PAR_CHUNK)
            # Le texte reellement envoye au LLM contient bien les separateurs.
            # / The text actually sent to the LLM does contain the separators.
            nombre_de_separateurs = len(chunk["elements"]) - 1
            self.assertEqual(
                len(chunk["texte"]),
                sum(len(element.texte) for element in chunk["elements"])
                + nombre_de_separateurs * len(SEPARATEUR_DE_JONCTION),
            )

    def test_le_budget_est_respecte_quand_c_est_possible(self):
        """
        Hors du cas de l'element trop gros, aucun chunk ne depasse le
        budget.
        / Apart from the too-big-element case, no chunk exceeds the budget.
        """
        for numero in range(15):
            self._ajouter_un_element(f"Paragraphe {numero}. " + "z" * 180)

        chunks = construire_les_chunks(self._elements_de_la_page())

        for chunk in chunks:
            self.assertLessEqual(len(chunk["texte"]), BUDGET_MAXIMUM_PAR_CHUNK)

    def test_une_page_sans_element_ne_produit_aucun_chunk(self):
        """Cas limite : rien a analyser, aucun appel LLM a faire."""
        chunks = construire_les_chunks([])

        self.assertEqual(chunks, [])


class PreferenceDeSectionTest(BaseChunkingTestCase):
    """
    La regle 2, preferentielle : couper a un sous-titre, mais seulement
    au-dessus du plancher.
    / Rule 2, preferential: cut at a section header, but only above the floor.
    """

    def test_preference_de_section_respecte_le_plancher(self):
        """
        Sous le plancher, on ne coupe PAS a un sous-titre (SPEC section 10).
        C'est ce qui protege les intros de liste : « L'IA ne doit pas
        remplacer : » suivi de ses puces reste dans le meme chunk.
        / Below the floor, we do NOT cut at a section header.
        """
        self._ajouter_un_element("Une intro courte.")
        titre = self._ajouter_un_element(
            "Un sous-titre juste apres", label="section_header",
        )
        self._ajouter_un_element("Le contenu de la section.")

        chunks = construire_les_chunks(self._elements_de_la_page())

        # Tout tient dans un seul chunk : on est loin du plancher.
        # / Everything fits in one chunk: we are far below the floor.
        self.assertEqual(len(chunks), 1)
        self.assertIn(titre, chunks[0]["elements"])

    def test_au_dessus_du_plancher_un_sous_titre_ouvre_un_chunk(self):
        """
        Au-dessus du plancher, un sous-titre declenche la coupure meme si
        le budget n'est pas atteint.
        / Above the floor, a section header triggers the cut.
        """
        # Un premier bloc qui depasse le plancher (900) sans atteindre le
        # budget (1500). / A first block above the floor, below the budget.
        self._ajouter_un_element("a" * (PLANCHER_AVANT_COUPURE_PREFEREE + 50))
        titre = self._ajouter_un_element(
            "Nouvelle section", label="section_header",
        )
        self._ajouter_un_element("Le contenu de la nouvelle section.")

        chunks = construire_les_chunks(self._elements_de_la_page())

        self.assertEqual(len(chunks), 2)
        # Le sous-titre ouvre le second chunk, il n'est pas reste dans le premier.
        # / The header opens the second chunk.
        self.assertEqual(chunks[1]["elements"][0], titre)

    def test_le_plancher_est_atteint_a_la_valeur_exacte(self):
        """
        Borne exacte du plancher : a la valeur PILE, on coupe. Verrouille
        le >= de la comparaison — un > laisserait passer ce cas.
        / Exact floor bound: at the exact value, we cut. This locks the >=.
        """
        self._ajouter_un_element("a" * PLANCHER_AVANT_COUPURE_PREFEREE)
        titre = self._ajouter_un_element("Nouvelle section", label="section_header")

        chunks = construire_les_chunks(self._elements_de_la_page())

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[1]["elements"][0], titre)

    def test_un_caractere_sous_le_plancher_ne_coupe_pas(self):
        """L'autre cote de la borne : un caractere de moins, on ne coupe pas."""
        self._ajouter_un_element("a" * (PLANCHER_AVANT_COUPURE_PREFEREE - 1))
        titre = self._ajouter_un_element("Nouvelle section", label="section_header")

        chunks = construire_les_chunks(self._elements_de_la_page())

        self.assertEqual(len(chunks), 1)
        self.assertIn(titre, chunks[0]["elements"])

    def test_un_sous_titre_en_tete_de_page_n_ouvre_pas_un_chunk_vide(self):
        """
        Cas limite : le document commence par un sous-titre. Il ne doit
        pas produire un premier chunk vide.
        / A document starting with a header must not produce an empty chunk.
        """
        titre = self._ajouter_un_element("Titre initial", label="section_header")
        self._ajouter_un_element("Du contenu.")

        chunks = construire_les_chunks(self._elements_de_la_page())

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["elements"][0], titre)


class ElementsMasquesTest(BaseChunkingTestCase):
    """Les elements masques ne partent jamais au LLM.
    / Hidden elements never reach the LLM."""

    def test_element_masque_absent_des_chunks(self):
        """
        SPEC section 10 : un element masque n'apparait dans aucun chunk
        produit. Cas reel : la transcription audio a invente un segment.
        / A hidden element appears in no chunk.
        """
        self._ajouter_un_element("Un vrai passage.")
        element_masque = self._ajouter_un_element(
            "Bruit de fond invente par la transcription.", masque=True,
        )
        self._ajouter_un_element("Un autre vrai passage.")

        chunks = construire_les_chunks(self._elements_de_la_page())

        tous_les_elements_des_chunks = [
            element for chunk in chunks for element in chunk["elements"]
        ]
        self.assertNotIn(element_masque, tous_les_elements_des_chunks)
        for chunk in chunks:
            self.assertNotIn(element_masque.texte, chunk["texte"])
            self.assertNotIn(element_masque.pk, chunk["offsets"])

    def test_une_page_entierement_masquee_ne_produit_aucun_chunk(self):
        """Cas limite : tout est masque, il n'y a rien a analyser."""
        self._ajouter_un_element("Bruit un.", masque=True)
        self._ajouter_un_element("Bruit deux.", masque=True)

        chunks = construire_les_chunks(self._elements_de_la_page())

        self.assertEqual(chunks, [])


class TableDesOffsetsTest(BaseChunkingTestCase):
    """
    La table d'offsets produite par le chunking doit etre exacte : c'est
    elle qui alimente le decoupage des spans (phase B).
    / The offsets table feeds span splitting (phase B), it must be exact.
    """

    def test_les_offsets_pointent_le_bon_texte_dans_le_chunk(self):
        """
        Pour chaque element, le texte du chunk entre ses bornes est
        exactement son propre texte.
        / For each element, the chunk text between its bounds is its own text.
        """
        for numero in range(6):
            self._ajouter_un_element(f"Paragraphe numero {numero}.")

        chunks = construire_les_chunks(self._elements_de_la_page())

        for chunk in chunks:
            for element in chunk["elements"]:
                debut, fin = chunk["offsets"][element.pk]
                self.assertEqual(chunk["texte"][debut:fin], element.texte)

    def test_les_separateurs_tombent_entre_les_elements(self):
        """
        Entre la fin d'un element et le debut du suivant, il y a
        exactement le separateur de jonction.
        / Exactly the joining separator sits between two elements.
        """
        self._ajouter_un_element("Premier paragraphe.")
        self._ajouter_un_element("Deuxieme paragraphe.")

        chunk_unique = construire_les_chunks(self._elements_de_la_page())[0]
        premier, deuxieme = chunk_unique["elements"]
        _, fin_du_premier = chunk_unique["offsets"][premier.pk]
        debut_du_deuxieme, _ = chunk_unique["offsets"][deuxieme.pk]

        self.assertEqual(
            chunk_unique["texte"][fin_du_premier:debut_du_deuxieme],
            SEPARATEUR_DE_JONCTION,
        )

    def test_la_table_alimente_directement_le_decoupage_des_spans(self):
        """
        Test d'integration phase C -> phase B : un span rendu sur le texte
        d'un chunk se decoupe correctement avec la table produite ici.
        / Integration test C -> B: a span on the chunk text splits correctly.
        """
        premier = self._ajouter_un_element("L'IA ne doit pas remplacer :")
        deuxieme = self._ajouter_un_element("le jugement des personnes")

        chunk_unique = construire_les_chunks(self._elements_de_la_page())[0]

        # Un span qui couvre tout le chunk, separateur compris.
        # / A span covering the whole chunk, separator included.
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(0, len(chunk_unique["texte"])),
            elements_du_chunk=chunk_unique["elements"],
            offsets_des_elements_dans_le_chunk=chunk_unique["offsets"],
        )

        self.assertEqual(len(portions), 2)
        self.assertEqual(portions[0]["element"], premier)
        self.assertEqual(portions[1]["element"], deuxieme)
        # Chaque portion couvre son element en entier, sans le separateur.
        # / Each portion covers its whole element, without the separator.
        self.assertEqual(portions[0]["fin_dans_element"], len(premier.texte))
        self.assertEqual(portions[1]["debut_dans_element"], 0)

    def test_un_texte_contenant_deja_des_separateurs_ne_trompe_pas_la_table(self):
        """
        Piege : un element dont le texte contient DEJA des sauts de ligne
        doubles. La table doit rester exacte.
        / Trap: an element whose text already contains double line breaks.

        Elle l'est parce que la construction est POSITIONNELLE : on avance
        d'une longueur connue. Une implementation qui chercherait le texte
        dans le chunk (str.find) se tromperait ici. Ce test verrouille ce
        choix d'implementation.
        / Positional construction, not sub-string search: this test locks that.
        """
        premier = self._ajouter_un_element(
            "Un paragraphe\n\navec un saut interne",
        )
        second = self._ajouter_un_element("Un autre paragraphe")

        chunk_unique = construire_les_chunks(self._elements_de_la_page())[0]

        for element in (premier, second):
            debut, fin = chunk_unique["offsets"][element.pk]
            self.assertEqual(chunk_unique["texte"][debut:fin], element.texte)

    def test_un_element_non_sauvegarde_est_refuse(self):
        """
        La table est indexee par pk. Deux elements a pk=None
        s'ecraseraient mutuellement, et la table dirait que le second
        commence la ou commence le premier.
        / Unsaved elements share pk=None and would collide in the table.
        """
        element_non_sauvegarde = ElementDocument(
            page=self.page_de_test, ordre=99, label="text",
            texte="Pas encore en base", empreinte_contenu="peu importe",
        )

        with self.assertRaises(ValueError):
            construire_les_chunks([element_non_sauvegarde])

    def test_l_ordre_des_elements_du_chunk_suit_le_document(self):
        """
        Le decoupage des spans exige des elements dans l'ordre du
        document — il leve une erreur sinon. Le chunking doit donc les
        rendre dans cet ordre.
        / Span splitting requires document order; chunking must respect it.
        """
        for numero in range(8):
            self._ajouter_un_element(f"Paragraphe {numero}. " + "w" * 150)

        chunks = construire_les_chunks(self._elements_de_la_page())

        for chunk in chunks:
            ordres = [element.ordre for element in chunk["elements"]]
            self.assertEqual(ordres, sorted(ordres))
