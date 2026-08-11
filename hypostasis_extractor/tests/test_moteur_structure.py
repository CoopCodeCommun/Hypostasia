"""
Tests du moteur scission / fusion — SPEC v2 sections 5.1 et 5.2 (phase F).
/ Tests for the split / merge engine — SPEC v2 sections 5.1 and 5.2.

LOCALISATION : hypostasis_extractor/tests/test_moteur_structure.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor.tests.test_moteur_structure

Les six tests nommes dans la section 10 de la spec pour ce fichier sont
ici. Les trois autres (re-ingestion, masquage) viendront avec la phase G.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    ElementDocument,
    ElementOperation,
    EtatElement,
    Page,
    TypeOperationElement,
    empreinte_du_texte,
)
from hypostasis_extractor.models import (
    AncrageExtraction,
    CommentaireExtraction,
    EtatAncrage,
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)
from hypostasis_extractor.services.ancrage import SEPARATEUR_DE_JONCTION
from hypostasis_extractor.services.moteur_structure import (
    fusionner_deux_elements,
    renumeroter_les_elements_de_la_page,
    scinder_un_element,
)


class BaseMoteurStructureTestCase(TestCase):
    """Socle commun : une page et de quoi y poser des elements ancres.
    / Common ground: a page and helpers to add anchored elements."""

    def setUp(self):
        self.utilisateur_de_test = get_user_model().objects.create_user(
            username="testeur_structure",
            password="motdepasse_de_test_123",
        )
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-structure",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="empreinte_page_structure",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page_de_test,
            name="Job de test structure",
            prompt_description="Extraire",
            status=ExtractionJobStatus.COMPLETED
        )
        self.prochain_ordre = 0

    def _ajouter_un_element(self, texte, label="text", provenance=None):
        element = ElementDocument.objects.create(
            page=self.page_de_test,
            ordre=self.prochain_ordre,
            label=label,
            texte=texte,
            empreinte_contenu=empreinte_du_texte(texte),
            provenance=provenance or {},
        )
        self.prochain_ordre += 1
        return element

    def _creer_une_extraction(self, texte="extrait"):
        return ExtractedEntity.objects.create(
            job=self.job,
            extraction_text=texte,
            start_char=0,
            end_char=len(texte),
        )

    def _ancrer(self, extraction, element, debut, fin, ordre=0):
        return AncrageExtraction.objects.create(
            extraction=extraction,
            element=element,
            ordre_dans_extraction=ordre,
            debut_dans_element=debut,
            fin_dans_element=fin,
        )

    def _ordres_de_la_page(self):
        return list(
            self.page_de_test.elements.order_by("ordre").values_list(
                "ordre", flat=True,
            )
        )


class ScissionTest(BaseMoteurStructureTestCase):
    """La scission d'un element en deux. / Splitting an element in two."""

    def test_scission_conserve_le_texte_total(self):
        """
        SPEC section 10 : la concatenation des deux morceaux redonne le
        texte original. Le contenu ne change jamais, seul son decoupage.
        / The two pieces concatenated give back the original text.
        """
        texte_original = "Premier tour de parole. Second tour de parole."
        element = self._ajouter_un_element(texte_original)

        premier, second = scinder_un_element(element, 24)

        self.assertEqual(premier.texte + second.texte, texte_original)
        self.assertEqual(premier.texte, "Premier tour de parole. ")
        self.assertEqual(second.texte, "Second tour de parole.")

    def test_scission_redistribue_une_portion_simple(self):
        """
        SPEC section 10 : une portion entierement avant ou apres la coupe
        est rattachee sans etre divisee.
        / A portion entirely before or after the cut is not divided.
        """
        element = self._ajouter_un_element("AAAA BBBB CCCC DDDD")
        extraction_avant = self._creer_une_extraction("AAAA")
        extraction_apres = self._creer_une_extraction("DDDD")
        portion_avant = self._ancrer(extraction_avant, element, 0, 4)
        portion_apres = self._ancrer(extraction_apres, element, 15, 19)

        premier, second = scinder_un_element(element, 10)

        portion_avant.refresh_from_db()
        portion_apres.refresh_from_db()
        # Celle d'avant : meme offsets, sur le premier morceau.
        # / The one before: same offsets, on the first piece.
        self.assertEqual(portion_avant.element, premier)
        self.assertEqual(portion_avant.debut_dans_element, 0)
        self.assertEqual(portion_avant.texte_de_la_portion(), "AAAA")
        # Celle d'apres : offsets recules de 10, sur le second morceau.
        # / The one after: offsets shifted back by 10, on the second piece.
        self.assertEqual(portion_apres.element, second)
        self.assertEqual(portion_apres.debut_dans_element, 5)
        self.assertEqual(portion_apres.texte_de_la_portion(), "DDDD")
        # Aucune portion n'a ete creee ni supprimee.
        # / No portion was created or deleted.
        self.assertEqual(AncrageExtraction.objects.count(), 2)

    def test_scission_divise_une_portion_qui_chevauche(self):
        """
        SPEC section 10 : une portion a cheval sur la coupe devient DEUX
        portions, et l'ordre_dans_extraction est recalcule pour toute
        l'extraction.
        / A straddling portion becomes TWO, with renumbered order.
        """
        element = self._ajouter_un_element("AAAA BBBB CCCC DDDD")
        extraction = self._creer_une_extraction("BBBB CCCC")
        portion_a_cheval = self._ancrer(extraction, element, 5, 14)

        premier, second = scinder_un_element(element, 10)

        portions = list(extraction.ancrages.all())
        self.assertEqual(len(portions), 2)
        # Premiere moitie sur le premier morceau.
        # / First half on the first piece.
        self.assertEqual(portions[0].element, premier)
        self.assertEqual(portions[0].ordre_dans_extraction, 0)
        self.assertEqual(portions[0].texte_de_la_portion(), "BBBB ")
        # Seconde moitie sur le second morceau, a partir du caractere 0.
        # / Second half on the second piece, from character 0.
        self.assertEqual(portions[1].element, second)
        self.assertEqual(portions[1].ordre_dans_extraction, 1)
        self.assertEqual(portions[1].debut_dans_element, 0)
        self.assertEqual(portions[1].texte_de_la_portion(), "CCCC")
        # Mises bout a bout, les deux portions redonnent le passage.
        # / Both portions concatenated give back the passage.
        self.assertEqual(
            portions[0].texte_de_la_portion() + portions[1].texte_de_la_portion(),
            "BBBB CCCC",
        )

    def test_scission_decale_les_portions_suivantes_de_l_extraction(self):
        """
        Quand une portion se coupe en deux, les portions SUIVANTES de la
        meme extraction doivent reculer d'un numero.
        / Following portions of the same extraction shift by one.
        """
        element_a_couper = self._ajouter_un_element("AAAA BBBB CCCC")
        element_suivant = self._ajouter_un_element("EEEE FFFF")
        extraction = self._creer_une_extraction("une extraction sur deux elements")
        self._ancrer(extraction, element_a_couper, 0, 14, ordre=0)
        portion_sur_le_suivant = self._ancrer(
            extraction, element_suivant, 0, 9, ordre=1,
        )

        scinder_un_element(element_a_couper, 5)

        portions = list(extraction.ancrages.all())
        self.assertEqual(len(portions), 3)
        self.assertEqual(
            [portion.ordre_dans_extraction for portion in portions], [0, 1, 2],
        )
        # La portion de l'element suivant est passee de 1 a 2.
        # / The portion on the next element went from 1 to 2.
        portion_sur_le_suivant.refresh_from_db()
        self.assertEqual(portion_sur_le_suivant.ordre_dans_extraction, 2)

    def test_scission_marque_les_portions_touchees_retrouvee(self):
        """
        Une portion coupee en deux n'est plus a la position calculee au
        premier ancrage : elle passe RETROUVEE.
        / A split portion is no longer at its original position.
        """
        element = self._ajouter_un_element("AAAA BBBB CCCC")
        extraction = self._creer_une_extraction()
        self._ancrer(extraction, element, 0, 14)

        scinder_un_element(element, 5)

        for portion in extraction.ancrages.all():
            self.assertEqual(portion.etat_ancrage, EtatAncrage.ANCREE)

    def test_scission_renumerote_les_elements_suivants(self):
        """
        Passer de un a deux elements decale tout ce qui suit d'un cran,
        sans laisser de trou ni de doublon.
        / Going from one to two elements shifts everything after by one.
        """
        premier_element = self._ajouter_un_element("AAAA BBBB")
        deuxieme_element = self._ajouter_un_element("CCCC")
        troisieme_element = self._ajouter_un_element("DDDD")

        scinder_un_element(premier_element, 5)

        self.assertEqual(self._ordres_de_la_page(), [0, 1, 2, 3])
        deuxieme_element.refresh_from_db()
        troisieme_element.refresh_from_db()
        self.assertEqual(deuxieme_element.ordre, 2)
        self.assertEqual(troisieme_element.ordre, 3)

    def test_scission_journalise_l_operation(self):
        """Toute operation de structure laisse une trace."""
        element = self._ajouter_un_element("AAAA BBBB")

        premier, _ = scinder_un_element(
            element, 5,
            utilisateur=self.utilisateur_de_test,
            justification="Deux locuteurs colles par la transcription.",
        )

        operation = ElementOperation.objects.get(element=premier)
        self.assertEqual(operation.type_operation, TypeOperationElement.SCISSION)
        self.assertEqual(operation.user, self.utilisateur_de_test)
        self.assertEqual(
            operation.justification,
            "Deux locuteurs colles par la transcription.",
        )

    def test_scission_conserve_l_etat_debattu(self):
        """
        Les deux morceaux d'un element debattu restent debattus : le
        commentaire porte toujours sur l'extraction ancree.
        / Both pieces of a debated element stay debated.
        """
        element = self._ajouter_un_element("AAAA BBBB CCCC")
        extraction = self._creer_une_extraction()
        self._ancrer(extraction, element, 0, 14)
        CommentaireExtraction.objects.create(
            entity=extraction,
            user=self.utilisateur_de_test,
            commentaire="Un desaccord.",
        )

        premier, second = scinder_un_element(element, 5)

        premier.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(premier.etat, EtatElement.DEBATTU)
        self.assertEqual(second.etat, EtatElement.DEBATTU)

    def test_scission_refuse_une_coupe_au_debut(self):
        """Couper a 0 produirait un premier morceau vide."""
        element = self._ajouter_un_element("AAAA BBBB")

        with self.assertRaises(ValueError):
            scinder_un_element(element, 0)

    def test_scission_refuse_une_coupe_a_la_fin(self):
        """Couper a la fin produirait un second morceau vide."""
        element = self._ajouter_un_element("AAAA BBBB")

        with self.assertRaises(ValueError):
            scinder_un_element(element, len(element.texte))

    def test_scission_sans_aucune_extraction(self):
        """Cas le plus simple : rien d'ancre, la coupe passe."""
        element = self._ajouter_un_element("AAAA BBBB")

        premier, second = scinder_un_element(element, 5)

        self.assertEqual(premier.etat, EtatElement.LIBRE)
        self.assertEqual(second.etat, EtatElement.LIBRE)
        self.assertEqual(ElementDocument.objects.count(), 2)

    def test_la_filiation_vit_dans_le_journal(self):
        """
        Le journal est la SEULE trace de filiation, et c'est voulu.

        Un champ element_parent a existe sur ElementDocument. Il etait
        structurellement inutile : scission et fusion suppriment toujours
        leurs elements sources, et le on_delete=SET_NULL du champ vidait
        donc la reference a chaque fois. Un champ qui ne peut jamais rien
        indiquer est pire qu'un champ absent — il invite a s'y fier.

        Il a ete supprime. ElementOperation.donnees porte ce qu'il faut :
        l'identifiant de l'element d'origine, et ceux des morceaux.
        / element_parent could never hold anything; the journal can.
        """
        element = self._ajouter_un_element("AAAA BBBB")
        identifiant_d_origine = element.pk
        identifiant_stable_d_origine = str(element.identifiant_stable)

        premier, second = scinder_un_element(element, 5)

        self.assertFalse(
            ElementDocument.objects.filter(pk=identifiant_d_origine).exists(),
        )

        operation = ElementOperation.objects.get(
            type_operation=TypeOperationElement.SCISSION,
        )
        self.assertEqual(
            operation.donnees["element_d_origine"], identifiant_stable_d_origine,
        )
        self.assertEqual(
            operation.donnees["morceaux"],
            [str(premier.identifiant_stable), str(second.identifiant_stable)],
        )

    def test_le_champ_element_parent_n_existe_plus(self):
        """
        Fige la suppression : si quelqu'un le reintroduit, il devra lire
        le test precedent et comprendre pourquoi il avait ete retire.
        / Locks the removal so a reintroduction is deliberate.
        """
        noms_des_champs = {
            champ.name for champ in ElementDocument._meta.get_fields()
        }

        self.assertNotIn("element_parent", noms_des_champs)


class FusionTest(BaseMoteurStructureTestCase):
    """La fusion de deux elements adjacents. / Merging two adjacent elements."""

    def test_fusion_refuse_des_elements_non_adjacents(self):
        """
        SPEC section 10 : ValueError si second.ordre != premier.ordre + 1.
        Fusionner deux elements distants ferait disparaitre en silence ce
        qui se trouve entre les deux.
        / Merging distant elements would silently drop what lies between.
        """
        premier = self._ajouter_un_element("AAAA")
        self._ajouter_un_element("BBBB")
        troisieme = self._ajouter_un_element("CCCC")

        with self.assertRaises(ValueError):
            fusionner_deux_elements(premier, troisieme)

    def test_fusion_refuse_l_ordre_inverse(self):
        """Fusionner dans le mauvais sens est refuse aussi."""
        premier = self._ajouter_un_element("AAAA")
        second = self._ajouter_un_element("BBBB")

        with self.assertRaises(ValueError):
            fusionner_deux_elements(second, premier)

    def test_fusion_recolle_les_textes(self):
        """Le texte fusionne est la concatenation, separateur compris."""
        premier = self._ajouter_un_element("Premier tour.")
        second = self._ajouter_un_element("Second tour.")

        element_fusionne = fusionner_deux_elements(premier, second)

        self.assertEqual(
            element_fusionne.texte,
            "Premier tour." + SEPARATEUR_DE_JONCTION + "Second tour.",
        )

    def test_fusion_decale_les_portions_du_second(self):
        """
        SPEC section 10 : les portions du second element sont decalees de
        la longueur du premier plus celle du separateur.
        / Portions of the second shift by len(first) + len(separator).
        """
        premier = self._ajouter_un_element("Premier tour.")
        second = self._ajouter_un_element("Second tour.")
        extraction_du_premier = self._creer_une_extraction("Premier")
        extraction_du_second = self._creer_une_extraction("Second")
        portion_du_premier = self._ancrer(extraction_du_premier, premier, 0, 7)
        portion_du_second = self._ancrer(extraction_du_second, second, 0, 6)

        fusionner_deux_elements(premier, second)

        portion_du_premier.refresh_from_db()
        portion_du_second.refresh_from_db()
        # Celle du premier n'a pas bouge d'offset.
        # / The first one's offsets did not move.
        self.assertEqual(portion_du_premier.debut_dans_element, 0)
        self.assertEqual(portion_du_premier.texte_de_la_portion(), "Premier")
        # Celle du second est decalee de 13 + 2 = 15.
        # / The second one shifted by 13 + 2 = 15.
        decalage_attendu = len("Premier tour.") + len(SEPARATEUR_DE_JONCTION)
        self.assertEqual(portion_du_second.debut_dans_element, decalage_attendu)
        self.assertEqual(portion_du_second.texte_de_la_portion(), "Second")

    def test_fusion_coalesce_les_portions_contigues(self):
        """
        SPEC section 10 : deux portions de la MEME extraction devenues
        contigues apres la fusion sont remplacees par une seule.
        / Two portions of the SAME extraction become one after merging.
        """
        premier = self._ajouter_un_element("Premier tour.")
        second = self._ajouter_un_element("Second tour.")
        extraction = self._creer_une_extraction("une extraction a cheval")
        # Une portion qui finit pile a la fin du premier...
        self._ancrer(extraction, premier, 0, 13, ordre=0)
        # ...et une qui commence pile au debut du second.
        self._ancrer(extraction, second, 0, 12, ordre=1)

        element_fusionne = fusionner_deux_elements(premier, second)

        portions = list(extraction.ancrages.all())
        self.assertEqual(len(portions), 1)
        portion_unique = portions[0]
        self.assertEqual(portion_unique.element, element_fusionne)
        self.assertEqual(portion_unique.debut_dans_element, 0)
        self.assertEqual(
            portion_unique.fin_dans_element, len(element_fusionne.texte),
        )
        self.assertEqual(portion_unique.ordre_dans_extraction, 0)

    def test_fusion_ne_coalesce_pas_des_portions_non_contigues(self):
        """
        Deux portions separees par du texte non extrait restent deux
        portions.
        / Two portions separated by unextracted text stay separate.
        """
        premier = self._ajouter_un_element("Premier tour.")
        second = self._ajouter_un_element("Second tour.")
        extraction = self._creer_une_extraction()
        self._ancrer(extraction, premier, 0, 7, ordre=0)   # "Premier"
        self._ancrer(extraction, second, 7, 12, ordre=1)   # "tour."

        fusionner_deux_elements(premier, second)

        self.assertEqual(extraction.ancrages.count(), 2)

    def test_fusion_ne_coalesce_pas_deux_extractions_differentes(self):
        """
        Deux portions contigues mais appartenant a des extractions
        DIFFERENTES ne doivent surtout pas etre recollees.
        / Contiguous portions of DIFFERENT extractions stay separate.
        """
        premier = self._ajouter_un_element("Premier tour.")
        second = self._ajouter_un_element("Second tour.")
        premiere_extraction = self._creer_une_extraction("une")
        seconde_extraction = self._creer_une_extraction("autre")
        self._ancrer(premiere_extraction, premier, 0, 13)
        self._ancrer(seconde_extraction, second, 0, 12)

        fusionner_deux_elements(premier, second)

        self.assertEqual(premiere_extraction.ancrages.count(), 1)
        self.assertEqual(seconde_extraction.ancrages.count(), 1)

    def test_fusion_renumerote_les_elements_suivants(self):
        """Passer de deux elements a un avance tout ce qui suit."""
        premier = self._ajouter_un_element("AAAA")
        second = self._ajouter_un_element("BBBB")
        troisieme = self._ajouter_un_element("CCCC")

        fusionner_deux_elements(premier, second)

        self.assertEqual(self._ordres_de_la_page(), [0, 1])
        troisieme.refresh_from_db()
        self.assertEqual(troisieme.ordre, 1)

    def test_fusion_journalise_l_operation(self):
        """Toute operation de structure laisse une trace."""
        premier = self._ajouter_un_element("AAAA")
        second = self._ajouter_un_element("BBBB")

        element_fusionne = fusionner_deux_elements(
            premier, second,
            utilisateur=self.utilisateur_de_test,
            justification="Tour de parole scinde a tort par la transcription.",
        )

        operation = ElementOperation.objects.get(element=element_fusionne)
        self.assertEqual(operation.type_operation, TypeOperationElement.FUSION)
        self.assertEqual(operation.user, self.utilisateur_de_test)

    def test_fusion_refuse_deux_pages_differentes(self):
        """On ne fusionne pas des elements de pages differentes."""
        premier = self._ajouter_un_element("AAAA")
        autre_page = Page.objects.create(
            url="http://exemple.local/autre-page-structure",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="t",
            content_hash="autre_empreinte_structure",
        )
        element_ailleurs = ElementDocument.objects.create(
            page=autre_page, ordre=1, label="text", texte="BBBB",
            empreinte_contenu=empreinte_du_texte("BBBB"),
        )

        with self.assertRaises(ValueError):
            fusionner_deux_elements(premier, element_ailleurs)


class PortionsDetacheesTest(BaseMoteurStructureTestCase):
    """
    Une portion detachee ne ressuscite pas par une operation de structure.
    / A detached portion is not resurrected by a structural operation.

    LOCALISATION : hypostasis_extractor/tests/test_moteur_structure.py

    Fusionner ou scinder, ce n'est pas retrouver un passage source perdu.
    Promouvoir une portion detachee en RETROUVEE la ferait reapparaitre
    sur des offsets que personne n'a jamais valides, et ferait remonter
    l'etat de l'element sur la foi d'une ancre fantome.
    """

    def _detacher(self, portion):
        portion.etat_ancrage = EtatAncrage.DETACHEE
        portion.save(update_fields=["etat_ancrage"])
        return portion

    def test_la_fusion_ne_ressuscite_pas_une_portion_detachee_du_premier(self):
        premier = self._ajouter_un_element("Premier tour.")
        second = self._ajouter_un_element("Second tour.")
        extraction = self._creer_une_extraction()
        portion = self._detacher(self._ancrer(extraction, premier, 0, 7))

        element_fusionne = fusionner_deux_elements(premier, second)

        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)
        # Elle a bien change d'element (sinon le PROTECT aurait bloque),
        # mais son etat n'a pas bouge.
        # / It moved element, but its state did not change.
        self.assertEqual(portion.element, element_fusionne)

    def test_la_fusion_ne_ressuscite_pas_une_portion_detachee_du_second(self):
        premier = self._ajouter_un_element("Premier tour.")
        second = self._ajouter_un_element("Second tour.")
        extraction = self._creer_une_extraction()
        portion = self._detacher(self._ancrer(extraction, second, 0, 6))

        fusionner_deux_elements(premier, second)

        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)

    def test_la_fusion_ne_fait_pas_remonter_l_etat_sur_une_ancre_fantome(self):
        """
        Le vrai degat : un element LIBRE qui repasse ANALYSE, donc un
        regime d'edition durci sans raison.
        / The real damage: a LIBRE element wrongly hardened to ANALYSE.
        """
        premier = self._ajouter_un_element("Premier tour.")
        second = self._ajouter_un_element("Second tour.")
        extraction = self._creer_une_extraction()
        self._detacher(self._ancrer(extraction, premier, 0, 7))
        premier.refresh_from_db()
        self.assertEqual(premier.etat, EtatElement.LIBRE)

        element_fusionne = fusionner_deux_elements(premier, second)

        element_fusionne.refresh_from_db()
        self.assertEqual(element_fusionne.etat, EtatElement.LIBRE)

    def test_la_scission_ne_ressuscite_pas_une_portion_detachee(self):
        """Les deux moities d'une portion detachee restent detachees."""
        element = self._ajouter_un_element("AAAA BBBB CCCC")
        extraction = self._creer_une_extraction()
        self._detacher(self._ancrer(extraction, element, 0, 14))

        scinder_un_element(element, 5)

        portions = list(extraction.ancrages.all())
        self.assertEqual(len(portions), 2)
        for portion in portions:
            self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)

    def test_une_portion_attachee_passe_bien_retrouvee(self):
        """Contre-epreuve : le cas normal fonctionne toujours."""
        premier = self._ajouter_un_element("Premier tour.")
        second = self._ajouter_un_element("Second tour.")
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, premier, 0, 7)

        fusionner_deux_elements(premier, second)

        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.ANCREE)


class JournalDesOperationsTest(BaseMoteurStructureTestCase):
    """
    Le journal survit aux operations suivantes.
    / The journal survives subsequent operations.
    """

    def test_le_journal_survit_a_une_operation_ulterieure(self):
        """
        Scinder puis refusionner : les DEUX operations doivent rester
        lisibles. Avec un journal rattache a l'element (supprime par
        chaque operation), la trace de la scission disparaissait.
        / Both operations must remain readable afterwards.
        """
        element = self._ajouter_un_element("Premier tour.Second tour.")

        premier, second = scinder_un_element(
            element, 13, utilisateur=self.utilisateur_de_test,
        )
        fusionner_deux_elements(
            premier, second, utilisateur=self.utilisateur_de_test,
        )

        types_journalises = list(
            ElementOperation.objects
            .filter(page=self.page_de_test)
            .order_by("created_at", "pk")
            .values_list("type_operation", flat=True)
        )
        self.assertEqual(
            types_journalises,
            [TypeOperationElement.SCISSION, TypeOperationElement.FUSION],
        )

    def test_le_journal_garde_le_contexte_de_la_scission(self):
        """
        Meme sans les elements, on doit pouvoir dire ce qui a ete coupe
        et ou.
        / Even without the elements, we must know what was cut and where.
        """
        element = self._ajouter_un_element("Premier tour.Second tour.")
        identifiant_d_origine = str(element.identifiant_stable)

        premier, second = scinder_un_element(element, 13)

        operation = ElementOperation.objects.get(
            type_operation=TypeOperationElement.SCISSION,
        )
        self.assertEqual(operation.donnees["position_de_coupe"], 13)
        self.assertEqual(operation.donnees["element_d_origine"], identifiant_d_origine)
        self.assertEqual(
            operation.donnees["morceaux"],
            [str(premier.identifiant_stable), str(second.identifiant_stable)],
        )
        self.assertEqual(
            str(operation.identifiant_stable_element), identifiant_d_origine,
        )

    def test_la_reference_a_l_element_passe_a_null_sans_perdre_la_ligne(self):
        """
        SET_NULL et non CASCADE : la ligne du journal reste, seule la
        reference se vide.
        / SET_NULL, not CASCADE: the journal row stays.
        """
        element = self._ajouter_un_element("Premier tour.Second tour.")
        premier, second = scinder_un_element(element, 13)
        operation_de_scission = ElementOperation.objects.get(
            type_operation=TypeOperationElement.SCISSION,
        )
        self.assertEqual(operation_de_scission.element, premier)

        fusionner_deux_elements(premier, second)

        operation_de_scission.refresh_from_db()
        self.assertIsNone(operation_de_scission.element_id)
        self.assertIsNotNone(operation_de_scission.identifiant_stable_element)
        self.assertEqual(operation_de_scission.page, self.page_de_test)

    def test_supprimer_la_page_supprime_son_journal(self):
        """La page reste le conteneur : sa suppression emporte le journal."""
        element = self._ajouter_un_element("Premier tour.Second tour.")
        scinder_un_element(element, 13)
        self.assertEqual(ElementOperation.objects.count(), 1)

        self.page_de_test.elements.all().delete()
        self.page_de_test.delete()

        self.assertEqual(ElementOperation.objects.count(), 0)


class CoalescenceTest(BaseMoteurStructureTestCase):
    """
    On ne recolle qu'a la couture.
    / We only merge portions at the seam.
    """

    def test_deux_portions_distantes_de_deux_caracteres_ne_sont_pas_recollees(self):
        """
        Le piege : tester la seule DISTANCE entre deux portions revient a
        recoller n'importe quelle paire separee par deux caracteres de
        VRAI texte — ce que la reconciliation peut produire. Ces deux
        caracteres seraient avales dans une portion qui ne les a jamais
        extraits.
        / Testing distance alone would swallow two characters of real text.
        """
        premier = self._ajouter_un_element("Premier XY tour.")
        second = self._ajouter_un_element("Second tour.")
        extraction = self._creer_une_extraction()
        # Deux portions DANS le premier element, separees par "XY".
        # / Two portions INSIDE the first element, separated by "XY".
        self._ancrer(extraction, premier, 0, 8, ordre=0)    # "Premier "
        self._ancrer(extraction, premier, 10, 16, ordre=1)  # " tour."

        fusionner_deux_elements(premier, second)

        # Elles restent deux portions : elles ne sont pas a la couture.
        # / They stay two portions: they are not at the seam.
        self.assertEqual(extraction.ancrages.count(), 2)
        textes = [
            portion.texte_de_la_portion() for portion in extraction.ancrages.all()
        ]
        self.assertNotIn("XY", "".join(textes))


class ProvenanceApresFusionTest(BaseMoteurStructureTestCase):
    """La provenance physique survit a la fusion.
    / Physical provenance survives the merge."""

    def test_les_boites_pdf_s_additionnent(self):
        """
        Un paragraphe a cheval sur deux colonnes garde ses deux boites :
        le surlignage PDF doit dessiner deux rectangles.
        / Two PDF boxes remain two boxes for highlighting.
        """
        premier = self._ajouter_un_element(
            "AAAA", provenance={"page_no": 1, "boites": [{"l": 0, "t": 0}]},
        )
        second = self._ajouter_un_element(
            "BBBB", provenance={"page_no": 1, "boites": [{"l": 5, "t": 5}]},
        )

        element_fusionne = fusionner_deux_elements(premier, second)

        self.assertEqual(len(element_fusionne.provenance["boites"]), 2)

    def test_chaque_boite_garde_sa_page_pdf(self):
        """
        Fusionner deux elements a cheval sur DEUX pages PDF : sans un
        numero de page par boite, les boites de la page 2 seraient
        dessinees sur la page 1, page_no etant unique au niveau de la
        provenance.
        / Without a per-box page number, page 2 boxes would be drawn on page 1.
        """
        premier = self._ajouter_un_element(
            "Fin de la page 1",
            provenance={"page_no": 1, "boites": [{"l": 0, "t": 700}]},
        )
        second = self._ajouter_un_element(
            "Debut de la page 2",
            provenance={"page_no": 2, "boites": [{"l": 0, "t": 50}]},
        )

        element_fusionne = fusionner_deux_elements(premier, second)

        boites = element_fusionne.provenance["boites"]
        self.assertEqual(len(boites), 2)
        self.assertEqual(boites[0]["page_no"], 1)
        self.assertEqual(boites[1]["page_no"], 2)

    def test_l_intervalle_audio_s_elargit(self):
        """La fusion de deux segments couvre les deux intervalles."""
        premier = self._ajouter_un_element(
            "AAAA", provenance={"start_time": 10.0, "end_time": 15.0, "voice": "A"},
        )
        second = self._ajouter_un_element(
            "BBBB", provenance={"start_time": 15.0, "end_time": 22.5, "voice": "A"},
        )

        element_fusionne = fusionner_deux_elements(premier, second)

        self.assertEqual(element_fusionne.provenance["start_time"], 10.0)
        self.assertEqual(element_fusionne.provenance["end_time"], 22.5)
        self.assertEqual(element_fusionne.provenance["voice"], "A")

    def test_deux_locuteurs_differents_effacent_le_locuteur(self):
        """
        Recoller deux locuteurs differents effacerait qui a dit quoi. On
        prefere ne plus rien affirmer sur le locuteur.
        / Merging two different speakers erases the speaker attribution.
        """
        premier = self._ajouter_un_element(
            "AAAA", provenance={"start_time": 10.0, "end_time": 15.0, "voice": "A"},
        )
        second = self._ajouter_un_element(
            "BBBB", provenance={"start_time": 15.0, "end_time": 22.5, "voice": "B"},
        )

        element_fusionne = fusionner_deux_elements(premier, second)

        self.assertNotIn("voice", element_fusionne.provenance)


class ScissionPuisFusionTest(BaseMoteurStructureTestCase):
    """
    Les deux operations bout a bout : l'aller-retour doit retomber sur ses
    pieds. / Both operations back to back must round-trip.
    """

    def test_scinder_puis_refusionner_redonne_un_texte_equivalent(self):
        """
        Aller-retour complet. Le texte n'est pas identique au caractere
        pres — la fusion insere un separateur la ou la scission n'en avait
        pas retire — mais le contenu est le meme.
        / Round-trip: same content, with a separator at the seam.
        """
        texte_original = "Premier tour.Second tour."
        element = self._ajouter_un_element(texte_original)

        premier, second = scinder_un_element(element, 13)
        element_refusionne = fusionner_deux_elements(premier, second)

        self.assertEqual(
            element_refusionne.texte.replace(SEPARATEUR_DE_JONCTION, ""),
            texte_original,
        )
        self.assertEqual(ElementDocument.objects.count(), 1)

    def test_l_ancre_survit_a_l_aller_retour(self):
        """
        Une portion coupee en deux par la scission est recollee en une
        seule par la fusion, et pointe toujours le meme passage.
        / A portion split then merged points at the same passage again.
        """
        element = self._ajouter_un_element("AAAA BBBB CCCC")
        extraction = self._creer_une_extraction("BBBB")
        self._ancrer(extraction, element, 5, 9)

        premier, second = scinder_un_element(element, 7)
        self.assertEqual(extraction.ancrages.count(), 2)

        element_refusionne = fusionner_deux_elements(premier, second)

        portions = list(extraction.ancrages.all())
        self.assertEqual(len(portions), 1)
        # Le separateur insere par la fusion se glisse dans le passage :
        # on retrouve "BB" + separateur + "BB".
        # / The inserted separator sits inside the passage.
        self.assertEqual(
            portions[0].texte_de_la_portion().replace(SEPARATEUR_DE_JONCTION, ""),
            "BBBB",
        )


class RenumerotationTest(BaseMoteurStructureTestCase):
    """Le rangement des ordres apres une serie d'operations.
    / Tidying up the ordering after a series of operations."""

    def test_les_trous_sont_combles(self):
        """Des ordres 0, 5, 12 redeviennent 0, 1, 2."""
        premier = self._ajouter_un_element("AAAA")
        deuxieme = self._ajouter_un_element("BBBB")
        troisieme = self._ajouter_un_element("CCCC")
        ElementDocument.objects.filter(pk=deuxieme.pk).update(ordre=5)
        ElementDocument.objects.filter(pk=troisieme.pk).update(ordre=12)

        renumeroter_les_elements_de_la_page(self.page_de_test)

        self.assertEqual(self._ordres_de_la_page(), [0, 1, 2])
        premier.refresh_from_db()
        deuxieme.refresh_from_db()
        troisieme.refresh_from_db()
        self.assertEqual(
            [premier.ordre, deuxieme.ordre, troisieme.ordre], [0, 1, 2],
        )

    def test_la_renumerotation_ne_change_pas_l_ordre_relatif(self):
        """Le tri du document est preserve."""
        premier = self._ajouter_un_element("Premier")
        deuxieme = self._ajouter_un_element("Deuxieme")
        ElementDocument.objects.filter(pk=premier.pk).update(ordre=3)
        ElementDocument.objects.filter(pk=deuxieme.pk).update(ordre=9)

        renumeroter_les_elements_de_la_page(self.page_de_test)

        textes_dans_l_ordre = list(
            self.page_de_test.elements.order_by("ordre").values_list(
                "texte", flat=True,
            )
        )
        self.assertEqual(textes_dans_l_ordre, ["Premier", "Deuxieme"])

    def test_les_identifiants_stables_ne_bougent_pas(self):
        """
        Rien ne depend de la valeur numerique de l'ordre : les ancres
        pointent identifiant_stable.
        / Anchors point to identifiant_stable, never to ordre.
        """
        element = self._ajouter_un_element("AAAA")
        identifiant_avant = element.identifiant_stable
        ElementDocument.objects.filter(pk=element.pk).update(ordre=42)

        renumeroter_les_elements_de_la_page(self.page_de_test)

        element.refresh_from_db()
        self.assertEqual(element.identifiant_stable, identifiant_avant)
        self.assertEqual(element.ordre, 0)
