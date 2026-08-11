"""
Tests de l'ancre multi-elements — SPEC v2 phase A.
/ Tests for the multi-element anchor — SPEC v2 phase A.

LOCALISATION : hypostasis_extractor/tests/test_ancrage_m2m.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test hypostasis_extractor.tests.test_ancrage_m2m
/ Run with the command above.

CE QUE CE FICHIER COUVRE, ET CE QU'IL NE COUVRE PAS

La section 10 de la SPEC v2 liste cinq tests pour ce fichier :

  | Test de la SPEC section 10                            | Phase | Etat   |
  |-------------------------------------------------------|-------|--------|
  | test_span_dans_un_seul_element_donne_une_portion       | B     | ecrit  |
  | test_span_sur_trois_elements_donne_trois_portions...   | B     | ecrit  |
  | test_separateurs_de_jonction_exclus_des_portions       | B     | ecrit  |
  | test_element_decoupe_en_sous_chaine_du_chunk           | B     | ecrit  |
  | test_reconciliation_ambigue_detache_plutot_que_deviner | E     | a venir|

Ce fichier couvre donc :
  - phase A : les modeles, leurs contraintes, le signal d'etat
  - phase B : le decoupage d'un span en portions (classe DecoupageDuSpanTest)
/ This file covers phase A models and phase B span splitting.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from core.models import (
    ElementDocument,
    ElementOperation,
    EtatElement,
    SourceLink,
    TypeLien,
    TypeOperationElement,
    Page,
    empreinte_du_texte,
)
from hypostasis_extractor.models import (
    AncrageExtraction,
    CommentaireExtraction,
    EtatAncrage,
    ExtractedEntity,
    ExtractionJob,
)
from hypostasis_extractor.services.ancrage import (
    SEPARATEUR_DE_JONCTION,
    construire_la_table_des_offsets,
    decouper_le_span_en_portions_par_element,
)


class BaseAncrageTestCase(TestCase):
    """
    Socle commun : une page, trois elements, un job d'extraction.
    / Common ground: one page, three elements, one extraction job.

    LOCALISATION : hypostasis_extractor/tests/test_ancrage_m2m.py

    Les trois elements imitent une liste a puces : une phrase d'introduction
    puis deux puces. C'est le cas type d'une extraction qui deborde d'un
    seul element.
    / The three elements mimic a bulleted list, the typical spanning case.
    """

    def setUp(self):
        self.utilisateur_de_test = get_user_model().objects.create_user(
            username="testeur_ancrage",
            password="motdepasse_de_test_123",
        )

        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-de-test",
            html_original="<p>original</p>",
            html_readability="<p>lisible</p>",
            text_readability="texte lisible",
            content_hash="empreinte_de_page_pour_les_tests",
            title="Page de test pour l'ancrage",
        )

        self.premier_element = self._creer_un_element(
            ordre=0,
            texte="L'IA ne doit pas remplacer :",
            label="text",
        )
        self.deuxieme_element = self._creer_un_element(
            ordre=1,
            texte="le jugement des personnes concernees",
            label="list_item",
        )
        self.troisieme_element = self._creer_un_element(
            ordre=2,
            texte="la deliberation collective",
            label="list_item",
        )

        self.job_d_extraction = ExtractionJob.objects.create(
            page=self.page_de_test,
            name="Job de test pour l'ancrage",
            prompt_description="Extraire les principes",
        )

    def _creer_un_element(self, ordre, texte, label="text"):
        """Cree un ElementDocument sur la page de test.
        / Creates an ElementDocument on the test page."""
        return ElementDocument.objects.create(
            page=self.page_de_test,
            ordre=ordre,
            label=label,
            texte=texte,
            empreinte_contenu=empreinte_du_texte(texte),
        )

    def _creer_une_extraction(self, texte_extrait="texte extrait"):
        """Cree une ExtractedEntity rattachee au job de test.
        / Creates an ExtractedEntity attached to the test job."""
        return ExtractedEntity.objects.create(
            job=self.job_d_extraction,
            extraction_text=texte_extrait,
            # Les anciens champs restent obligatoires : les deux moteurs
            # coexistent, on ne les a pas retires (SPEC v2 section 9).
            # / Old fields stay mandatory: both engines coexist.
            start_char=0,
            end_char=len(texte_extrait),
        )

    def _ancrer(self, extraction, element, ordre, debut, fin,
                etat=EtatAncrage.ANCREE):
        """Cree une portion d'ancrage. / Creates an anchor portion."""
        return AncrageExtraction.objects.create(
            extraction=extraction,
            element=element,
            ordre_dans_extraction=ordre,
            debut_dans_element=debut,
            fin_dans_element=fin,
            etat_ancrage=etat,
        )


class AncreMultiElementsTest(BaseAncrageTestCase):
    """
    L'ancre M2M elle-meme : une extraction, plusieurs portions ordonnees.
    / The M2M anchor itself: one extraction, several ordered portions.
    """

    def test_une_extraction_peut_avoir_une_seule_portion(self):
        """Le cas simple : l'extraction tient dans un seul element."""
        extraction = self._creer_une_extraction("le jugement des personnes")
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=25)

        self.assertEqual(extraction.ancrages.count(), 1)
        self.assertEqual(
            extraction.ancrages.first().element,
            self.deuxieme_element,
        )

    def test_une_extraction_peut_traverser_trois_elements(self):
        """
        Le cas qui justifie la table de liaison : trois elements traverses
        donnent trois portions, lisibles dans l'ordre du document.
        / Three crossed elements give three portions, in document order.
        """
        extraction = self._creer_une_extraction("l'extraction traverse la liste")
        self._ancrer(extraction, self.premier_element, ordre=0, debut=0, fin=28)
        self._ancrer(extraction, self.deuxieme_element, ordre=1, debut=0, fin=36)
        self._ancrer(extraction, self.troisieme_element, ordre=2, debut=0, fin=26)

        portions = list(extraction.ancrages.all())

        self.assertEqual(len(portions), 3)
        # L'ordering du Meta trie par ordre_dans_extraction : on doit
        # retrouver les elements dans l'ordre du document.
        # / Meta ordering sorts by ordre_dans_extraction.
        self.assertEqual(portions[0].element, self.premier_element)
        self.assertEqual(portions[1].element, self.deuxieme_element)
        self.assertEqual(portions[2].element, self.troisieme_element)

    def test_un_element_peut_porter_les_portions_de_plusieurs_extractions(self):
        """
        L'autre sens du M2M : deux extractions differentes ancrees sur le
        meme element.
        / The other direction of the M2M: two extractions on one element.
        """
        premiere_extraction = self._creer_une_extraction("le jugement")
        seconde_extraction = self._creer_une_extraction("des personnes concernees")

        self._ancrer(premiere_extraction, self.deuxieme_element, 0, 0, 11)
        self._ancrer(seconde_extraction, self.deuxieme_element, 0, 12, 36)

        self.assertEqual(
            self.deuxieme_element.portions_d_extractions.count(), 2,
        )

    def test_texte_de_la_portion_relit_depuis_l_element(self):
        """
        Le texte d'une portion n'est pas stocke : il est relu dans
        l'element a chaque appel.
        / A portion's text is never stored, always re-read from the element.
        """
        extraction = self._creer_une_extraction("le jugement")
        portion = self._ancrer(
            extraction, self.deuxieme_element, ordre=0, debut=0, fin=11,
        )

        self.assertEqual(portion.texte_de_la_portion(), "le jugement")

    def test_texte_de_la_portion_suit_une_correction_de_l_element(self):
        """
        Consequence de la relecture a la demande : si l'element est
        corrige, la portion ne garde pas une vieille copie du texte.
        / If the element is corrected, the portion holds no stale copy.
        """
        extraction = self._creer_une_extraction("le jugement")
        portion = self._ancrer(
            extraction, self.deuxieme_element, ordre=0, debut=0, fin=11,
        )

        self.deuxieme_element.texte = "LE JUGEMENT des personnes concernees"
        self.deuxieme_element.save(update_fields=["texte"])
        portion.refresh_from_db()

        self.assertEqual(portion.texte_de_la_portion(), "LE JUGEMENT")

    def test_deux_portions_ne_peuvent_pas_partager_le_meme_ordre(self):
        """
        Contrainte unicite_ordre_dans_l_extraction : deux portions de la
        MEME extraction ne peuvent pas avoir le meme numero d'ordre.
        / Two portions of the SAME extraction cannot share an order number.

        La contrainte est DEFERRABLE : elle n'est plus verifiee a chaque
        ligne ecrite, mais a la fin de la transaction. Le moteur de
        structure en a besoin pour decaler des numeros sans se
        telescoper. On force donc la verification ici, comme le ferait un
        commit. / The constraint is deferred, so we force the check.
        """
        extraction = self._creer_une_extraction("texte")
        self._ancrer(extraction, self.premier_element, ordre=0, debut=0, fin=5)

        # Ecrire le doublon ne leve plus rien tout de suite...
        # / Writing the duplicate no longer raises immediately...
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=5)

        # ...mais la contrainte tient toujours a la verification.
        # / ...but the constraint still holds when checked.
        with self.assertRaises(IntegrityError):
            connection.check_constraints()

    def test_deux_extractions_peuvent_avoir_chacune_une_portion_zero(self):
        """
        La contrainte porte sur le COUPLE (extraction, ordre). Deux
        extractions differentes ont chacune leur portion numero 0.
        / The constraint is on the PAIR (extraction, order).
        """
        premiere_extraction = self._creer_une_extraction("premiere")
        seconde_extraction = self._creer_une_extraction("seconde")

        self._ancrer(premiere_extraction, self.premier_element, 0, 0, 8)
        self._ancrer(seconde_extraction, self.deuxieme_element, 0, 0, 7)

        self.assertEqual(AncrageExtraction.objects.count(), 2)

    def test_un_element_porteur_ne_peut_pas_etre_supprime(self):
        """
        PROTECT sur AncrageExtraction.element : on ne supprime jamais un
        element qui porte une portion. Le moteur de structure doit d'abord
        redistribuer les portions.
        / An element carrying a portion is never deleted directly.
        """
        extraction = self._creer_une_extraction("le jugement")
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=11)

        with self.assertRaises(ProtectedError):
            self.deuxieme_element.delete()

    def test_supprimer_l_extraction_supprime_ses_portions(self):
        """
        CASCADE sur AncrageExtraction.extraction : les portions n'ont pas
        de sens sans leur extraction.
        / Portions make no sense without their extraction.
        """
        extraction = self._creer_une_extraction("le jugement")
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=11)

        extraction.delete()

        self.assertEqual(AncrageExtraction.objects.count(), 0)


class DecoupageDuSpanTest(BaseAncrageTestCase):
    """
    Le decoupage d'un span de chunk en portions — SPEC v2 section 2.3.
    / Splitting a chunk span into portions — SPEC v2 section 2.3.

    LOCALISATION : hypostasis_extractor/tests/test_ancrage_m2m.py

    Rappel du chunk construit par le setUp du socle commun :

        "L'IA ne doit pas remplacer :\\n\\nle jugement des personnes
         concernees\\n\\nla deliberation collective"
         |---- element 1 (28) ----|  |------ element 2 (36) ------|
                                                                   |-- el 3 --|

    Positions dans le chunk :
        element 1 :  0 -> 28
        separateur: 28 -> 30
        element 2 : 30 -> 66
        separateur: 66 -> 68
        element 3 : 68 -> 94
    """

    def setUp(self):
        super().setUp()
        self.elements_du_chunk = [
            self.premier_element,
            self.deuxieme_element,
            self.troisieme_element,
        ]
        self.texte_du_chunk, self.offsets = construire_la_table_des_offsets(
            self.elements_du_chunk,
        )

    def test_la_table_des_offsets_place_les_elements_et_les_separateurs(self):
        """Verifie le socle de tous les autres tests de cette classe."""
        self.assertEqual(self.offsets[self.premier_element.pk], (0, 28))
        self.assertEqual(self.offsets[self.deuxieme_element.pk], (30, 66))
        self.assertEqual(self.offsets[self.troisieme_element.pk], (68, 94))
        self.assertEqual(
            self.texte_du_chunk[28:30], SEPARATEUR_DE_JONCTION,
        )

    def test_span_dans_un_seul_element_donne_une_portion(self):
        """
        Cas simple (SPEC section 10) : le span tient dans un element, on
        obtient une seule portion, aux bons offsets locaux.
        / Simple case: the span fits in one element, one portion.
        """
        # "le jugement" = caracteres 30 a 41 du chunk, soit 0 a 11 de l'element 2
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(30, 41),
            elements_du_chunk=self.elements_du_chunk,
            offsets_des_elements_dans_le_chunk=self.offsets,
        )

        self.assertEqual(len(portions), 1)
        self.assertEqual(portions[0]["element"], self.deuxieme_element)
        self.assertEqual(portions[0]["ordre_dans_extraction"], 0)
        self.assertEqual(portions[0]["debut_dans_element"], 0)
        self.assertEqual(portions[0]["fin_dans_element"], 11)
        self.assertEqual(
            self.deuxieme_element.texte[0:11], "le jugement",
        )

    def test_span_sur_trois_elements_donne_trois_portions_ordonnees(self):
        """
        Cas de la liste a puces (SPEC section 10) : le span couvre les
        trois elements, on obtient trois portions numerotees 0, 1, 2 dans
        l'ordre du document.
        / The span covers three elements: three portions, ordered 0, 1, 2.
        """
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(0, 94),
            elements_du_chunk=self.elements_du_chunk,
            offsets_des_elements_dans_le_chunk=self.offsets,
        )

        self.assertEqual(len(portions), 3)
        self.assertEqual(
            [portion["ordre_dans_extraction"] for portion in portions], [0, 1, 2],
        )
        self.assertEqual(
            [portion["element"] for portion in portions], self.elements_du_chunk,
        )
        # Chaque portion couvre son element en entier.
        # / Each portion covers its whole element.
        for portion in portions:
            self.assertEqual(portion["debut_dans_element"], 0)
            self.assertEqual(
                portion["fin_dans_element"], len(portion["element"].texte),
            )

    def test_separateurs_de_jonction_exclus_des_portions(self):
        """
        Invariant central (SPEC section 10) : les separateurs entre
        elements n'apparaissent dans aucune portion. Mises bout a bout,
        les portions rendent le texte SANS les separateurs.
        / Joining separators appear in no portion.
        """
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(0, 94),
            elements_du_chunk=self.elements_du_chunk,
            offsets_des_elements_dans_le_chunk=self.offsets,
        )

        textes_des_portions = [
            portion["element"].texte[
                portion["debut_dans_element"]:portion["fin_dans_element"]
            ]
            for portion in portions
        ]
        texte_recompose = "".join(textes_des_portions)

        self.assertNotIn(SEPARATEUR_DE_JONCTION, texte_recompose)
        # Le texte recompose est bien le chunk MOINS les separateurs.
        # / The recomposed text is the chunk MINUS the separators.
        self.assertEqual(
            texte_recompose,
            self.texte_du_chunk.replace(SEPARATEUR_DE_JONCTION, ""),
        )

    def test_span_qui_commence_dans_un_separateur_est_rogne(self):
        """
        Cas 3 de la spec : LangExtract aligne parfois au milieu d'un
        separateur. L'intersection rogne aux bornes de l'element, sans
        traitement special.
        / A span starting inside a separator is trimmed to element bounds.
        """
        # Le span commence a 29, soit au milieu du separateur (28 -> 30).
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(29, 41),
            elements_du_chunk=self.elements_du_chunk,
            offsets_des_elements_dans_le_chunk=self.offsets,
        )

        self.assertEqual(len(portions), 1)
        self.assertEqual(portions[0]["element"], self.deuxieme_element)
        self.assertEqual(portions[0]["debut_dans_element"], 0)

    def test_span_entierement_dans_un_separateur_ne_donne_aucune_portion(self):
        """
        Cas limite : le span ne couvre qu'un separateur. On rend une liste
        vide plutot que d'inventer une portion.
        / A span covering only a separator yields no portion.
        """
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(28, 30),
            elements_du_chunk=self.elements_du_chunk,
            offsets_des_elements_dans_le_chunk=self.offsets,
        )

        self.assertEqual(portions, [])

    def test_span_vide_ne_donne_aucune_portion(self):
        """Deux bornes egales : zero caractere, donc zero portion."""
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(35, 35),
            elements_du_chunk=self.elements_du_chunk,
            offsets_des_elements_dans_le_chunk=self.offsets,
        )

        self.assertEqual(portions, [])

    def test_element_decoupe_en_sous_chaine_du_chunk(self):
        """
        Cas de l'element trop gros (SPEC section 10) : le chunk ne porte
        qu'un morceau de l'element. Les offsets rendus doivent pointer
        dans le texte COMPLET de l'element, pas dans le morceau.
        / The chunk carries only a slice; offsets must point into the FULL element.
        """
        element_tres_long = self._creer_un_element(
            ordre=3,
            texte="A" * 1500 + "le passage recherche" + "B" * 1500,
        )
        # Le chunk ne porte que les caracteres 1490 a 1540 de l'element.
        # Dans le chunk, ce morceau occupe les positions 0 a 50.
        # / The chunk carries element chars 1490..1540, at chunk positions 0..50.
        offsets_du_morceau = {element_tres_long.pk: (0, 50)}
        decalages = {element_tres_long.pk: 1490}

        # "le passage recherche" commence a 10 dans le morceau.
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(10, 30),
            elements_du_chunk=[element_tres_long],
            offsets_des_elements_dans_le_chunk=offsets_du_morceau,
            decalages_dans_l_element=decalages,
        )

        self.assertEqual(len(portions), 1)
        # 10 dans le morceau + 1490 de decalage = 1500 dans l'element.
        self.assertEqual(portions[0]["debut_dans_element"], 1500)
        self.assertEqual(portions[0]["fin_dans_element"], 1520)
        self.assertEqual(
            element_tres_long.texte[1500:1520], "le passage recherche",
        )

    def test_span_qui_finit_dans_un_separateur_est_rogne(self):
        """
        Cas 3 de la spec, seconde moitie : le span FINIT dans un
        separateur. Il est rogne a la fin de l'element precedent.
        / Second half of spec case 3: the span ENDS inside a separator.
        """
        # Le span finit a 29, soit au milieu du separateur (28 -> 30).
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(0, 29),
            elements_du_chunk=self.elements_du_chunk,
            offsets_des_elements_dans_le_chunk=self.offsets,
        )

        self.assertEqual(len(portions), 1)
        self.assertEqual(portions[0]["element"], self.premier_element)
        self.assertEqual(portions[0]["fin_dans_element"], 28)
        self.assertEqual(
            portions[0]["fin_dans_element"], len(self.premier_element.texte),
        )

    def test_decalage_sur_un_chunk_qui_melange_morceau_et_elements_entiers(self):
        """
        Le cas reel de la phase C : un chunk porte la QUEUE d'un element
        trop gros, puis des elements entiers. Le decalage ne doit
        s'appliquer qu'au premier.
        / A chunk carries the TAIL of a big element, then whole elements.
        """
        element_tres_long = self._creer_un_element(
            ordre=3, texte="X" * 1000 + "la fin du gros element",
        )
        element_suivant = self._creer_un_element(
            ordre=4, texte="un element entier",
        )
        # Le chunk porte les caracteres 1000 a 1022 du gros element
        # (positions 0 a 22 du chunk), puis l'element suivant apres le
        # separateur (positions 24 a 41).
        offsets = {
            element_tres_long.pk: (0, 22),
            element_suivant.pk: (24, 41),
        }
        decalages = {element_tres_long.pk: 1000}

        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(0, 41),
            elements_du_chunk=[element_tres_long, element_suivant],
            offsets_des_elements_dans_le_chunk=offsets,
            decalages_dans_l_element=decalages,
        )

        self.assertEqual(len(portions), 2)
        # Le premier est decale de 1000, le second ne l'est pas.
        # / The first is shifted by 1000, the second is not.
        self.assertEqual(portions[0]["debut_dans_element"], 1000)
        self.assertEqual(portions[0]["fin_dans_element"], 1022)
        self.assertEqual(portions[1]["debut_dans_element"], 0)
        self.assertEqual(portions[1]["fin_dans_element"], 17)
        self.assertEqual(
            element_tres_long.texte[1000:1022], "la fin du gros element",
        )
        self.assertEqual(element_suivant.texte[0:17], "un element entier")

    def test_un_element_sans_bornes_connues_leve_une_erreur(self):
        """
        On refuse d'ancrer a l'aveugle. Sauter l'element en silence
        produirait une ancre incomplete que rien en aval ne detecterait :
        la portion du milieu disparaitrait, la numerotation se resserrerait,
        et la contrainte d'unicite resterait satisfaite.
        / We refuse to anchor blind: a silent skip yields an undetectable
        incomplete anchor.
        """
        offsets_incomplets = dict(self.offsets)
        del offsets_incomplets[self.deuxieme_element.pk]

        with self.assertRaises(KeyError):
            decouper_le_span_en_portions_par_element(
                span_dans_le_chunk=(0, 94),
                elements_du_chunk=self.elements_du_chunk,
                offsets_des_elements_dans_le_chunk=offsets_incomplets,
            )

    def test_un_span_a_l_envers_leve_une_erreur(self):
        """
        Un span inverse est un bug de l'appelant. Sans garde, il rendrait
        une liste vide, indistinguable du cas legitime « span entierement
        dans un separateur ».
        / An inverted span would silently look like the separator case.
        """
        with self.assertRaises(ValueError):
            decouper_le_span_en_portions_par_element(
                span_dans_le_chunk=(41, 30),
                elements_du_chunk=self.elements_du_chunk,
                offsets_des_elements_dans_le_chunk=self.offsets,
            )

    def test_un_span_negatif_leve_une_erreur(self):
        """Un offset negatif n'a pas de sens dans un texte."""
        with self.assertRaises(ValueError):
            decouper_le_span_en_portions_par_element(
                span_dans_le_chunk=(-5, 20),
                elements_du_chunk=self.elements_du_chunk,
                offsets_des_elements_dans_le_chunk=self.offsets,
            )

    def test_des_elements_hors_ordre_levent_une_erreur(self):
        """
        ordre_dans_extraction doit valoir 0 pour la portion la plus a
        gauche DANS LE DOCUMENT. Une liste dans le desordre produirait une
        numerotation fausse sans que rien ne le signale.
        / Out-of-order elements would silently produce wrong numbering.
        """
        elements_a_l_envers = [
            self.troisieme_element,
            self.deuxieme_element,
            self.premier_element,
        ]

        with self.assertRaises(ValueError):
            decouper_le_span_en_portions_par_element(
                span_dans_le_chunk=(0, 94),
                elements_du_chunk=elements_a_l_envers,
                offsets_des_elements_dans_le_chunk=self.offsets,
            )

    def test_un_decalage_faux_leve_une_erreur(self):
        """
        Un decalage incoherent produirait des offsets hors du texte de
        l'element, et texte_de_la_portion() rendrait une chaine vide en
        silence.
        / A wrong shift would yield a silent empty slice.
        """
        decalage_absurde = {self.deuxieme_element.pk: 1_000_000}

        with self.assertRaises(ValueError):
            decouper_le_span_en_portions_par_element(
                span_dans_le_chunk=(30, 41),
                elements_du_chunk=self.elements_du_chunk,
                offsets_des_elements_dans_le_chunk=self.offsets,
                decalages_dans_l_element=decalage_absurde,
            )

    def test_les_portions_produites_sont_creables_telles_quelles(self):
        """
        Le contrat de sortie : chaque dict rendu peut alimenter
        directement AncrageExtraction.objects.create().
        / Each returned dict can feed AncrageExtraction.objects.create() as is.
        """
        extraction = self._creer_une_extraction("l'extraction traverse la liste")
        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(0, 94),
            elements_du_chunk=self.elements_du_chunk,
            offsets_des_elements_dans_le_chunk=self.offsets,
        )

        for portion in portions:
            AncrageExtraction.objects.create(extraction=extraction, **portion)

        self.assertEqual(extraction.ancrages.count(), 3)
        # Et le signal d'etat a bien vu passer les trois elements.
        # / And the state signal saw all three elements.
        for element in self.elements_du_chunk:
            element.refresh_from_db()
            self.assertEqual(element.etat, EtatElement.ANALYSE)


class ElementDocumentTest(BaseAncrageTestCase):
    """
    Le modele ElementDocument : identifiant stable, ordre, empreinte.
    / The ElementDocument model: stable id, order, fingerprint.
    """

    def test_l_identifiant_stable_est_unique_et_rempli_automatiquement(self):
        """Chaque element recoit un UUID, sans qu'on ait a le demander."""
        self.assertIsNotNone(self.premier_element.identifiant_stable)
        self.assertNotEqual(
            self.premier_element.identifiant_stable,
            self.deuxieme_element.identifiant_stable,
        )

    def test_l_identifiant_stable_ne_bouge_pas_quand_le_texte_change(self):
        """
        C'est tout l'interet du champ : les ancres pointent cet
        identifiant, il doit survivre a une correction de texte.
        / Anchors point to this id, it must survive a text correction.
        """
        identifiant_avant = self.premier_element.identifiant_stable

        self.premier_element.texte = "Texte corrige apres relecture"
        self.premier_element.ordre = 7
        self.premier_element.save(update_fields=["texte", "ordre"])
        self.premier_element.refresh_from_db()

        self.assertEqual(self.premier_element.identifiant_stable, identifiant_avant)

    def test_deux_elements_ne_peuvent_pas_partager_le_meme_ordre(self):
        """
        Contrainte unicite_ordre_dans_la_page : l'ordre est unique DANS
        une page.
        / The order is unique WITHIN a page.

        La contrainte est DEFERRABLE (verifiee a la fin de la
        transaction) pour que le moteur de structure puisse passer par des
        etats temporairement incoherents. On force la verification ici.
        / Deferred constraint: we force the check.
        """
        self._creer_un_element(ordre=0, texte="Un autre element")

        with self.assertRaises(IntegrityError):
            connection.check_constraints()

    def test_deux_pages_peuvent_avoir_chacune_un_element_d_ordre_zero(self):
        """La contrainte porte sur le COUPLE (page, ordre)."""
        autre_page = Page.objects.create(
            url="http://exemple.local/autre-page",
            html_original="<p>a</p>",
            html_readability="<p>a</p>",
            text_readability="a",
            content_hash="autre_empreinte_de_page",
        )
        ElementDocument.objects.create(
            page=autre_page,
            ordre=0,
            label="text",
            texte="Premier element de l'autre page",
            empreinte_contenu=empreinte_du_texte("Premier element de l'autre page"),
        )

        self.assertEqual(ElementDocument.objects.filter(ordre=0).count(), 2)

    def test_les_elements_sont_tries_par_ordre(self):
        """L'ordering du Meta trie par page puis par ordre."""
        elements_de_la_page = list(self.page_de_test.elements.all())

        self.assertEqual(
            [element.ordre for element in elements_de_la_page], [0, 1, 2],
        )

    def test_l_empreinte_ignore_la_casse_et_les_espaces(self):
        """
        Deux textes qui ne different que par la casse ou les espaces
        donnent la meme empreinte : la re-ingestion doit les reconnaitre
        comme inchanges.
        / Case and whitespace differences give the same fingerprint.
        """
        empreinte_de_reference = empreinte_du_texte("Le jugement des personnes")

        self.assertEqual(
            empreinte_du_texte("le  jugement   des personnes  "),
            empreinte_de_reference,
        )
        self.assertNotEqual(
            empreinte_du_texte("Le jugement des machines"),
            empreinte_de_reference,
        )

    def test_supprimer_la_page_supprime_ses_elements(self):
        """CASCADE sur ElementDocument.page."""
        page_a_supprimer = Page.objects.create(
            url="http://exemple.local/page-jetable",
            html_original="<p>a</p>",
            html_readability="<p>a</p>",
            text_readability="a",
            content_hash="empreinte_page_jetable",
        )
        ElementDocument.objects.create(
            page=page_a_supprimer,
            ordre=0,
            label="text",
            texte="Element jetable",
            empreinte_contenu=empreinte_du_texte("Element jetable"),
        )

        page_a_supprimer.delete()

        self.assertEqual(
            ElementDocument.objects.filter(page_id=page_a_supprimer.pk).count(), 0,
        )


class EtatDeLElementTest(BaseAncrageTestCase):
    """
    Le signal recalculer_etat_de_l_element.
    / The recalculer_etat_de_l_element signal.

    LOCALISATION : hypostasis_extractor/tests/test_ancrage_m2m.py

    Rappel de la regle retenue : une portion ne compte que si son
    extraction n'est pas masquee ET que son ancrage n'est pas detache.
    / A portion counts only if not hidden AND not detached.

    Il n'y a pas d'etat SCELLE : le scellement a ete abandonne.
    / There is no SCELLE state.
    """

    def test_un_element_sans_extraction_est_libre(self):
        """Etat par defaut, aucune portion attachee."""
        self.assertEqual(self.premier_element.etat, EtatElement.LIBRE)

    def test_ancrer_une_extraction_rend_l_element_analyse(self):
        """Une portion active, aucun commentaire : ANALYSE."""
        extraction = self._creer_une_extraction("le jugement")
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=11)

        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.ANALYSE)

    def test_commenter_une_extraction_rend_l_element_debattu(self):
        """Un commentaire sur l'extraction ancree : DEBATTU."""
        extraction = self._creer_une_extraction("le jugement")
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=11)

        CommentaireExtraction.objects.create(
            entity=extraction,
            user=self.utilisateur_de_test,
            commentaire="Je ne suis pas d'accord avec cette lecture.",
        )

        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.DEBATTU)

    def test_un_commentaire_fait_basculer_tous_les_elements_traverses(self):
        """
        Consequence de l'ancre M2M : une extraction qui traverse trois
        elements les fait TOUS passer DEBATTU d'un seul commentaire.
        / One comment switches ALL crossed elements to DEBATTU.
        """
        extraction = self._creer_une_extraction("l'extraction traverse la liste")
        self._ancrer(extraction, self.premier_element, ordre=0, debut=0, fin=28)
        self._ancrer(extraction, self.deuxieme_element, ordre=1, debut=0, fin=36)
        self._ancrer(extraction, self.troisieme_element, ordre=2, debut=0, fin=26)

        CommentaireExtraction.objects.create(
            entity=extraction,
            user=self.utilisateur_de_test,
            commentaire="Cette liste melange deux idees differentes.",
        )

        for element in (self.premier_element, self.deuxieme_element,
                        self.troisieme_element):
            element.refresh_from_db()
            self.assertEqual(element.etat, EtatElement.DEBATTU)

    def test_supprimer_le_dernier_commentaire_ramene_a_analyse(self):
        """Le signal fonctionne aussi a la suppression."""
        extraction = self._creer_une_extraction("le jugement")
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=11)
        commentaire = CommentaireExtraction.objects.create(
            entity=extraction,
            user=self.utilisateur_de_test,
            commentaire="Un commentaire qui sera retire.",
        )

        commentaire.delete()

        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.ANALYSE)

    def test_supprimer_la_derniere_portion_ramene_a_libre(self):
        """Plus aucune portion attachee : retour a LIBRE."""
        extraction = self._creer_une_extraction("le jugement")
        portion = self._ancrer(
            extraction, self.deuxieme_element, ordre=0, debut=0, fin=11,
        )

        portion.delete()

        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.LIBRE)

    def test_une_portion_detachee_ne_compte_pas(self):
        """
        Regle retenue : une portion detachee a perdu son passage source,
        elle n'impose plus de regime d'edition contraint.
        / A detached portion no longer constrains editing.
        """
        extraction = self._creer_une_extraction("le jugement")
        portion = self._ancrer(
            extraction, self.deuxieme_element, ordre=0, debut=0, fin=11,
        )
        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.ANALYSE)

        portion.etat_ancrage = EtatAncrage.DETACHEE
        portion.save(update_fields=["etat_ancrage"])

        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.LIBRE)

    def test_une_extraction_masquee_ne_compte_pas(self):
        """
        Regle retenue : une extraction masquee par la curation ne se voit
        plus, elle ne doit pas contraindre l'element.
        / A hidden extraction must not constrain the element.
        """
        extraction = self._creer_une_extraction("le jugement")
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=11)
        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.ANALYSE)

        extraction.masquee = True
        extraction.save(update_fields=["masquee"])

        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.LIBRE)

    def test_demasquer_une_extraction_restaure_l_etat(self):
        """L'operation est reversible dans les deux sens."""
        extraction = self._creer_une_extraction("le jugement")
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=11)
        extraction.masquee = True
        extraction.save(update_fields=["masquee"])

        extraction.masquee = False
        extraction.save(update_fields=["masquee"])

        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.ANALYSE)

    def test_une_extraction_active_maintient_debattu_malgre_une_masquee(self):
        """
        Deux extractions sur le meme element : masquer la commentee ne
        doit pas effacer l'etat si l'autre reste active.
        / Hiding one commented extraction must not erase the other's state.
        """
        extraction_commentee = self._creer_une_extraction("premiere")
        extraction_simple = self._creer_une_extraction("seconde")
        self._ancrer(extraction_commentee, self.deuxieme_element, 0, 0, 11)
        self._ancrer(extraction_simple, self.deuxieme_element, 0, 12, 20)
        CommentaireExtraction.objects.create(
            entity=extraction_commentee,
            user=self.utilisateur_de_test,
            commentaire="Un desaccord.",
        )
        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.DEBATTU)

        extraction_commentee.masquee = True
        extraction_commentee.save(update_fields=["masquee"])

        # L'autre extraction reste active et sans commentaire : ANALYSE.
        # / The other extraction stays active, uncommented: ANALYSE.
        self.deuxieme_element.refresh_from_db()
        self.assertEqual(self.deuxieme_element.etat, EtatElement.ANALYSE)

    def test_l_etat_d_un_element_n_affecte_pas_ses_voisins(self):
        """Le recalcul est cible : seul l'element ancre change d'etat."""
        extraction = self._creer_une_extraction("le jugement")
        self._ancrer(extraction, self.deuxieme_element, ordre=0, debut=0, fin=11)

        self.premier_element.refresh_from_db()
        self.troisieme_element.refresh_from_db()
        self.assertEqual(self.premier_element.etat, EtatElement.LIBRE)
        self.assertEqual(self.troisieme_element.etat, EtatElement.LIBRE)


class ElementOperationTest(BaseAncrageTestCase):
    """
    Le journal des operations de structure.
    / The structural operations journal.
    """

    def test_on_peut_journaliser_un_masquage(self):
        """Le modele accepte les quatre types d'operation de structure."""
        operation = ElementOperation.objects.create(
            page=self.page_de_test,
            element=self.premier_element,
            identifiant_stable_element=self.premier_element.identifiant_stable,
            type_operation=TypeOperationElement.MASQUAGE,
            user=self.utilisateur_de_test,
            justification="Segment invente par la transcription audio.",
        )

        self.assertEqual(self.premier_element.operations.count(), 1)
        self.assertEqual(operation.type_operation, "masquage")

    def test_les_quatre_types_d_operation_existent(self):
        """
        SCISSION, FUSION, MASQUAGE, DEMASQUAGE — ce sont exactement les
        types que TypeEdit ne couvrait pas.
        / The four types TypeEdit did not cover.
        """
        types_attendus = {"scission", "fusion", "masquage", "demasquage"}
        types_declares = {choix[0] for choix in TypeOperationElement.choices}

        self.assertEqual(types_declares, types_attendus)

    def test_supprimer_l_element_ne_supprime_pas_son_journal(self):
        """
        SET_NULL et non CASCADE.

        Une scission et une fusion suppriment toujours leurs elements
        sources. Avec une CASCADE, chaque operation effacerait l'histoire
        de la precedente : le journal serait decoratif. Il tient donc a la
        Page, et la reference a l'element se vide simplement.
        / With CASCADE, each operation would erase the previous one's history.
        """
        identifiant_stable = self.premier_element.identifiant_stable
        operation = ElementOperation.objects.create(
            page=self.page_de_test,
            element=self.premier_element,
            identifiant_stable_element=identifiant_stable,
            type_operation=TypeOperationElement.SCISSION,
            user=self.utilisateur_de_test,
        )

        self.premier_element.delete()

        operation.refresh_from_db()
        self.assertEqual(ElementOperation.objects.count(), 1)
        self.assertIsNone(operation.element_id)
        # De quoi reconnaitre l'element disparu.
        # / Enough to recognize the vanished element.
        self.assertEqual(operation.identifiant_stable_element, identifiant_stable)

    def test_supprimer_la_page_supprime_son_journal(self):
        """La page est le conteneur : sa suppression emporte le journal."""
        ElementOperation.objects.create(
            page=self.page_de_test,
            element=self.premier_element,
            type_operation=TypeOperationElement.SCISSION,
            user=self.utilisateur_de_test,
        )

        self.page_de_test.delete()

        self.assertEqual(ElementOperation.objects.count(), 0)

    def test_l_operation_survit_a_la_suppression_de_son_auteur(self):
        """
        SET_NULL sur user : la trace de l'operation reste meme si le
        compte qui l'a faite disparait.
        / The operation trace survives its author's deletion.
        """
        operation = ElementOperation.objects.create(
            page=self.page_de_test,
            element=self.premier_element,
            type_operation=TypeOperationElement.FUSION,
            user=self.utilisateur_de_test,
            justification="Recollage de deux tours de parole scindes.",
        )

        self.utilisateur_de_test.delete()
        operation.refresh_from_db()

        self.assertIsNone(operation.user)
        self.assertEqual(operation.justification,
                         "Recollage de deux tours de parole scindes.")


class SourceLinkAncrageTest(BaseAncrageTestCase):
    """
    SourceLink.ancrage_source — le lien de provenance vers une portion.
    / SourceLink.ancrage_source — provenance link to a portion.
    """

    def test_un_lien_peut_pointer_une_portion_precise(self):
        """
        extraction_source dit QUELLE extraction, ancrage_source dit DANS
        QUEL ELEMENT et a quel endroit.
        / extraction_source says WHICH extraction, ancrage_source says WHERE.
        """
        extraction = self._creer_une_extraction("le jugement")
        portion = self._ancrer(
            extraction, self.deuxieme_element, ordre=0, debut=0, fin=11,
        )

        lien = SourceLink.objects.create(
            page_cible=self.page_de_test,
            start_char_cible=0,
            end_char_cible=11,
            type_lien=TypeLien.IDENTIQUE,
            extraction_source=extraction,
            ancrage_source=portion,
        )

        self.assertEqual(lien.ancrage_source, portion)
        self.assertEqual(lien.ancrage_source.texte_de_la_portion(), "le jugement")
        self.assertEqual(portion.liens_de_provenance.count(), 1)

    def test_le_champ_ancrage_source_est_facultatif(self):
        """
        Les deux moteurs coexistent : un lien de l'ancien moteur, sans
        portion, reste valide.
        / Both engines coexist: a link without a portion stays valid.
        """
        lien = SourceLink.objects.create(
            page_cible=self.page_de_test,
            start_char_cible=0,
            end_char_cible=10,
            type_lien=TypeLien.MODIFIE,
        )

        self.assertIsNone(lien.ancrage_source)

    def test_supprimer_la_portion_ne_supprime_pas_le_lien(self):
        """
        SET_NULL : le lien de provenance survit a la disparition de la
        portion, il perd seulement sa precision.
        / SET_NULL: the link survives, it only loses its precision.
        """
        extraction = self._creer_une_extraction("le jugement")
        portion = self._ancrer(
            extraction, self.deuxieme_element, ordre=0, debut=0, fin=11,
        )
        lien = SourceLink.objects.create(
            page_cible=self.page_de_test,
            start_char_cible=0,
            end_char_cible=11,
            type_lien=TypeLien.IDENTIQUE,
            ancrage_source=portion,
        )

        portion.delete()
        lien.refresh_from_db()

        self.assertIsNone(lien.ancrage_source)
        self.assertEqual(SourceLink.objects.count(), 1)


class CoexistenceDesDeuxMoteursTest(BaseAncrageTestCase):
    """
    Non-regression : l'ancien moteur n'a pas ete touche.
    / Non-regression: the old engine was not touched.

    LOCALISATION : hypostasis_extractor/tests/test_ancrage_m2m.py

    La SPEC v2 section 9 est explicite : les anciens champs restent en
    place, rien n'est migre de force, les deux moteurs coexistent. Ces
    tests echouent si quelqu'un retire un ancien champ par megarde.
    / These tests fail if someone removes an old field by mistake.
    """

    def test_les_anciens_champs_d_offset_existent_toujours(self):
        """ExtractedEntity.start_char / end_char n'ont pas ete retires."""
        noms_des_champs = {champ.name for champ in ExtractedEntity._meta.get_fields()}

        self.assertIn("start_char", noms_des_champs)
        self.assertIn("end_char", noms_des_champs)

    def test_les_anciens_offsets_de_sourcelink_existent_toujours(self):
        """SourceLink garde ses offsets plats a cote de ancrage_source."""
        noms_des_champs = {champ.name for champ in SourceLink._meta.get_fields()}

        self.assertIn("start_char_source", noms_des_champs)
        self.assertIn("end_char_source", noms_des_champs)
        self.assertIn("ancrage_source", noms_des_champs)

    def test_une_extraction_de_l_ancien_moteur_reste_utilisable(self):
        """
        Une extraction sans aucune portion d'ancrage fonctionne comme
        avant : c'est le cas de toutes les pages existantes.
        / An extraction without portions works as before.
        """
        extraction = self._creer_une_extraction("texte de l'ancien moteur")

        self.assertEqual(extraction.ancrages.count(), 0)
        self.assertEqual(extraction.start_char, 0)
        self.assertEqual(extraction.end_char, len("texte de l'ancien moteur"))
