"""
Tests du masquage et de la re-ingestion — SPEC v2 sections 5.3 et 5.4.
/ Tests for hiding and re-ingestion — SPEC v2 sections 5.3 and 5.4.

LOCALISATION : hypostasis_extractor/tests/test_masquage_et_reingestion.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor.tests.test_masquage_et_reingestion

Les trois tests nommes dans la section 10 de la spec pour la phase G sont
ici :
  - test_masquage_detache_sans_supprimer
  - test_reingestion_conserve_les_ancres_des_elements_inchanges
  - test_reingestion_detache_les_extractions_des_elements_disparus
"""

from django.contrib.auth import get_user_model
from django.db import connection
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
from hypostasis_extractor.services.chunking import construire_les_chunks
from hypostasis_extractor.services.masquage import (
    demasquer_un_element,
    hash_du_texte_brut,
    masquer_un_element,
)
from hypostasis_extractor.services.reconciliation import (
    reconcilier_les_portions_de_l_element,
)
from hypostasis_extractor.services.reingestion import (
    reconcilier_les_elements_par_empreinte,
)


class BasePhaseGTestCase(TestCase):
    """Socle commun. / Common ground."""

    def setUp(self):
        self.utilisateur_de_test = get_user_model().objects.create_user(
            username="testeur_phase_g",
            password="motdepasse_de_test_123",
        )
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-phase-g",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="empreinte_page_phase_g",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page_de_test,
            name="Job de test phase G",
            prompt_description="Extraire",
            status=ExtractionJobStatus.COMPLETED
        )
        self.prochain_ordre = 0

    def _ajouter_un_element(self, texte, label="text", masque=False):
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

    def _creer_une_extraction(self, texte="extrait"):
        return ExtractedEntity.objects.create(
            job=self.job, extraction_text=texte,
            start_char=0, end_char=len(texte),
        )

    def _ancrer(self, extraction, element, debut, fin, ordre=0):
        return AncrageExtraction.objects.create(
            extraction=extraction, element=element,
            ordre_dans_extraction=ordre,
            debut_dans_element=debut, fin_dans_element=fin,
        )


class MasquageTest(BasePhaseGTestCase):
    """Masquer sans supprimer. / Hiding without deleting."""

    def test_masquage_detache_sans_supprimer(self):
        """
        SPEC section 10 : un element masque voit ses portions passer
        DETACHEE, rien n'est supprime, et le demasquage reste possible.
        / Hidden element: portions detached, nothing deleted, undo possible.
        """
        element = self._ajouter_un_element("Bruit de fond transcrit a tort.")
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, element, 0, 5)

        nombre_detache = masquer_un_element(
            element,
            justification="Segment invente par la transcription.",
            utilisateur=self.utilisateur_de_test,
        )

        element.refresh_from_db()
        portion.refresh_from_db()
        self.assertTrue(element.masque)
        self.assertEqual(nombre_detache, 1)
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)
        # Rien n'est supprime : ni l'element, ni la portion, ni l'extraction.
        # / Nothing is deleted.
        self.assertTrue(ElementDocument.objects.filter(pk=element.pk).exists())
        self.assertTrue(AncrageExtraction.objects.filter(pk=portion.pk).exists())
        self.assertTrue(ExtractedEntity.objects.filter(pk=extraction.pk).exists())

    def test_un_element_masque_retombe_libre(self):
        """
        Plus aucune portion active : l'element redevient librement
        editable. C'est la consequence voulue de la regle de calcul de
        l'etat.
        / No active portion left: the element becomes freely editable again.
        """
        element = self._ajouter_un_element("Un passage debattu.")
        extraction = self._creer_une_extraction()
        self._ancrer(extraction, element, 0, 8)
        CommentaireExtraction.objects.create(
            entity=extraction, user=self.utilisateur_de_test,
            commentaire="Un desaccord.",
        )
        element.refresh_from_db()
        self.assertEqual(element.etat, EtatElement.DEBATTU)

        masquer_un_element(element, utilisateur=self.utilisateur_de_test)

        element.refresh_from_db()
        self.assertEqual(element.etat, EtatElement.LIBRE)

    def test_masquage_journalise_le_hash_du_texte_brut(self):
        """
        C'est le hash du texte EXACT qui est note, pas l'empreinte
        normalisee.

        L'empreinte de core/models.py ecrase les espaces et met en
        minuscules — parfait pour reconnaitre un contenu inchange lors
        d'une re-ingestion, dangereux ici : corriger une double espace
        decale tous les offsets qui suivent sans changer l'empreinte
        normalisee d'un iota.
        / The exact text is hashed, not the normalized fingerprint.
        """
        element = self._ajouter_un_element("Un texte a masquer.")

        masquer_un_element(element, utilisateur=self.utilisateur_de_test)

        operation = ElementOperation.objects.get(
            type_operation=TypeOperationElement.MASQUAGE,
        )
        self.assertEqual(
            operation.donnees["hash_du_texte_au_masquage"],
            hash_du_texte_brut("Un texte a masquer."),
        )
        # Et ce hash distingue bien ce que l'empreinte normalisee confond.
        # / And this hash tells apart what the normalized one conflates.
        self.assertNotEqual(
            hash_du_texte_brut("Un  texte a masquer."),
            hash_du_texte_brut("Un texte a masquer."),
        )
        self.assertEqual(
            empreinte_du_texte("Un  texte a masquer."),
            empreinte_du_texte("Un texte a masquer."),
        )

    def test_masquage_ne_journalise_que_les_portions_qu_il_detache(self):
        """
        Une portion deja detachee AVANT le masquage ne doit pas figurer
        dans le journal : ses offsets sont perimes depuis plus longtemps,
        et le demasquage ne doit pas la faire revenir.
        / A portion detached BEFORE the hide must not be journaled.
        """
        element = self._ajouter_un_element("Le jugement des personnes.")
        extraction_deja_detachee = self._creer_une_extraction()
        extraction_active = self._creer_une_extraction()
        portion_deja_detachee = self._ancrer(
            extraction_deja_detachee, element, 0, 2,
        )
        portion_deja_detachee.etat_ancrage = EtatAncrage.DETACHEE
        portion_deja_detachee.save(update_fields=["etat_ancrage"])
        portion_active = self._ancrer(extraction_active, element, 3, 11)

        nombre_detache = masquer_un_element(element)

        operation = ElementOperation.objects.get(
            type_operation=TypeOperationElement.MASQUAGE,
        )
        self.assertEqual(nombre_detache, 1)
        self.assertEqual(operation.donnees["portions_detachees"], [portion_active.pk])
        self.assertNotIn(
            portion_deja_detachee.pk, operation.donnees["portions_detachees"],
        )

    def test_masquer_deux_fois_ne_fait_rien(self):
        """Idempotent : un element deja masque n'est pas retouche."""
        element = self._ajouter_un_element("Un texte.")
        masquer_un_element(element)

        resultat = masquer_un_element(element)

        self.assertEqual(resultat, 0)
        self.assertEqual(
            ElementOperation.objects.filter(
                type_operation=TypeOperationElement.MASQUAGE,
            ).count(),
            1,
        )

    def test_un_element_masque_ne_part_plus_au_llm(self):
        """
        Integration avec le chunking : un element masque n'apparait dans
        aucun chunk. / Integration with chunking.
        """
        self._ajouter_un_element("Un vrai passage.")
        element_a_masquer = self._ajouter_un_element("Du bruit.")

        masquer_un_element(element_a_masquer)

        chunks = construire_les_chunks(
            list(self.page_de_test.elements.all()),
        )
        tous_les_elements = [
            element for chunk in chunks for element in chunk["elements"]
        ]
        self.assertNotIn(element_a_masquer, tous_les_elements)


class DemasquageTest(BasePhaseGTestCase):
    """Revenir en arriere. / Undoing."""

    def test_demasquer_rattache_les_portions_si_le_texte_n_a_pas_change(self):
        """
        Le cas nominal : on masque, on demasque, tout revient.
        / The nominal case: hide then unhide, everything comes back.
        """
        element = self._ajouter_un_element("Le jugement des personnes.")
        extraction = self._creer_une_extraction("jugement")
        portion = self._ancrer(extraction, element, 3, 11)
        masquer_un_element(element, utilisateur=self.utilisateur_de_test)

        resultat = demasquer_un_element(
            element, utilisateur=self.utilisateur_de_test,
        )

        element.refresh_from_db()
        portion.refresh_from_db()
        self.assertFalse(element.masque)
        self.assertEqual(resultat["portions_rattachees"], 1)
        self.assertEqual(portion.etat_ancrage, EtatAncrage.ANCREE)
        # L'ancre pointe toujours le bon passage.
        # / The anchor still points at the right passage.
        self.assertEqual(portion.texte_de_la_portion(), "jugement")
        self.assertEqual(element.etat, EtatElement.ANALYSE)

    def test_demasquer_laisse_detache_si_le_texte_a_change(self):
        """
        Le texte a ete corrige pendant que l'element etait masque : les
        offsets ne designent plus rien de sur. On ne devine pas.
        / The text changed while hidden: we do not guess.
        """
        element = self._ajouter_un_element("Le jugement des personnes.")
        extraction = self._creer_une_extraction("jugement")
        portion = self._ancrer(extraction, element, 3, 11)
        masquer_un_element(element, utilisateur=self.utilisateur_de_test)

        # Le texte change pendant le masquage.
        # / The text changes while hidden.
        reconcilier_les_portions_de_l_element(
            element, "Un tout autre contenu maintenant.",
        )

        resultat = demasquer_un_element(element)

        element.refresh_from_db()
        portion.refresh_from_db()
        self.assertFalse(element.masque)
        self.assertEqual(resultat["portions_rattachees"], 0)
        self.assertEqual(resultat["portions_laissees_detachees"], 1)
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)
        # L'element reste librement editable : rien d'actif n'y est attache.
        # / The element stays freely editable.
        self.assertEqual(element.etat, EtatElement.LIBRE)

    def test_demasquer_journalise_la_decision(self):
        """Le journal dit si le texte avait change, et ce qui en a decoule."""
        element = self._ajouter_un_element("Un texte.")
        masquer_un_element(element)

        demasquer_un_element(element, justification="Fausse alerte.")

        operation = ElementOperation.objects.get(
            type_operation=TypeOperationElement.DEMASQUAGE,
        )
        self.assertFalse(operation.donnees["le_texte_a_change"])
        self.assertEqual(operation.justification, "Fausse alerte.")

    def test_demasquer_un_element_non_masque_ne_fait_rien(self):
        """Idempotent dans l'autre sens."""
        element = self._ajouter_un_element("Un texte.")

        resultat = demasquer_un_element(element)

        self.assertEqual(resultat["portions_rattachees"], 0)
        self.assertFalse(
            ElementOperation.objects.filter(
                type_operation=TypeOperationElement.DEMASQUAGE,
            ).exists(),
        )

    def test_demasquer_sans_masquage_journalise_ne_rattache_rien(self):
        """
        Un element masque en base sans passer par masquer_un_element n'a
        aucun contexte de reference. Sans lui, on ne sait ni quel etait le
        texte, ni quelles portions ce masquage avait detachees : on ne
        rattache rien.
        / Without a journaled context, nothing is reattached.
        """
        element = self._ajouter_un_element("Un texte.", masque=True)
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, element, 0, 3)
        portion.etat_ancrage = EtatAncrage.DETACHEE
        portion.save(update_fields=["etat_ancrage"])

        resultat = demasquer_un_element(element)

        portion.refresh_from_db()
        self.assertEqual(resultat["portions_rattachees"], 0)
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)

    def test_demasquer_ne_ressuscite_pas_une_portion_detachee_avant(self):
        """
        Le piege : une portion detachee AVANT le masquage, par une
        correction de texte. Ses offsets sont perimes depuis. La rattacher
        au demasquage la ferait pointer n'importe quoi — exactement
        l'ancre fausse silencieuse que tout ce module existe pour eviter.
        / A portion detached BEFORE the hide must not come back.
        """
        element = self._ajouter_un_element("Le jugement des personnes.")
        extraction = self._creer_une_extraction("jugement")
        portion = self._ancrer(extraction, element, 3, 11)
        # Une correction fait disparaitre le passage : portion detachee.
        # / A correction makes the passage disappear.
        reconcilier_les_portions_de_l_element(
            element, "Le monde des personnes concernees.",
        )
        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)

        masquer_un_element(element)
        resultat = demasquer_un_element(element)

        portion.refresh_from_db()
        self.assertEqual(resultat["portions_rattachees"], 0)
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)

    def test_demasquer_laisse_detache_si_seuls_des_espaces_ont_change(self):
        """
        Le second piege : une correction qui ne change QUE des espaces ou
        la casse. L'empreinte normalisee ne la voit pas, mais chaque
        caractere qui suit a bouge — les offsets sont faux.
        / A whitespace-only fix moves every following offset.
        """
        element = self._ajouter_un_element("Le  jugement des personnes.")
        extraction = self._creer_une_extraction("jugement")
        portion = self._ancrer(extraction, element, 4, 12)
        self.assertEqual(portion.texte_de_la_portion(), "jugement")
        masquer_un_element(element)

        # On corrige la double espace pendant le masquage. La phase E
        # saute les portions detachees, donc les offsets ne bougent pas.
        # / The double space is fixed while hidden.
        ElementDocument.objects.filter(pk=element.pk).update(
            texte="Le jugement des personnes.",
        )
        element.refresh_from_db()

        resultat = demasquer_un_element(element)

        portion.refresh_from_db()
        self.assertEqual(resultat["portions_rattachees"], 0)
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)
        # L'empreinte normalisee, elle, n'aurait rien vu.
        # / The normalized fingerprint would have seen nothing.
        self.assertEqual(
            empreinte_du_texte("Le  jugement des personnes."),
            empreinte_du_texte("Le jugement des personnes."),
        )


class ReingestionTest(BasePhaseGTestCase):
    """La reconciliation par empreinte. / Fingerprint-based reconciliation."""

    def test_reingestion_conserve_les_ancres_des_elements_inchanges(self):
        """
        SPEC section 10 : un element de meme empreinte garde son
        identifiant_stable, donc ses ancres et ses commentaires.
        / Same fingerprint: same identifiant_stable, anchors intact.
        """
        element_inchange = self._ajouter_un_element("Un compte-rendu de mars.")
        extraction = self._creer_une_extraction("compte-rendu")
        portion = self._ancrer(extraction, element_inchange, 3, 15)
        identifiant_avant = element_inchange.identifiant_stable

        resultat = reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [
                {"texte": "Un compte-rendu d'avril.", "label": "text"},
                {"texte": "Un compte-rendu de mars.", "label": "text"},
            ],
        )

        element_inchange.refresh_from_db()
        portion.refresh_from_db()
        self.assertEqual(len(resultat["inchanges"]), 1)
        self.assertEqual(len(resultat["apparus"]), 1)
        self.assertEqual(len(resultat["disparus"]), 0)
        # Meme identifiant, meme ancre, ancre toujours valide.
        # / Same id, same anchor, still valid.
        self.assertEqual(element_inchange.identifiant_stable, identifiant_avant)
        self.assertEqual(portion.etat_ancrage, EtatAncrage.ANCREE)
        self.assertEqual(portion.texte_de_la_portion(), "compte-rendu")
        # Il a recule d'une place, le nouveau compte-rendu est au-dessus.
        # / It moved down one place.
        self.assertEqual(element_inchange.ordre, 1)

    def test_reingestion_detache_les_extractions_des_elements_disparus(self):
        """
        SPEC section 10 : un element absent du nouveau contenu voit ses
        portions passer DETACHEE, et il est masque, pas supprime.
        / A disappeared element: portions detached, element hidden not deleted.
        """
        element_qui_disparait = self._ajouter_un_element("Un passage retire.")
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, element_qui_disparait, 0, 8)

        resultat = reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [{"texte": "Un tout autre passage.", "label": "text"}],
        )

        element_qui_disparait.refresh_from_db()
        portion.refresh_from_db()
        self.assertEqual(len(resultat["disparus"]), 1)
        self.assertTrue(element_qui_disparait.masque)
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)
        # Rien n'est supprime.
        # / Nothing is deleted.
        self.assertTrue(
            ElementDocument.objects.filter(pk=element_qui_disparait.pk).exists(),
        )

    def test_reingestion_reconnait_le_contenu_malgre_la_casse_et_les_espaces(self):
        """
        L'empreinte normalise : une difference de casse ou d'espaces ne
        fait pas passer un element pour nouveau.
        / Case and whitespace differences do not make an element look new.
        """
        element = self._ajouter_un_element("Le compte-rendu de mars")

        resultat = reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [{"texte": "le   compte-rendu de mars  ", "label": "text"}],
        )

        self.assertEqual(len(resultat["inchanges"]), 1)
        self.assertEqual(len(resultat["apparus"]), 0)
        self.assertEqual(resultat["inchanges"][0].pk, element.pk)

    def test_reingestion_d_un_pad_qui_grossit(self):
        """
        Le cas d'usage reel : trois comptes-rendus, un quatrieme ajoute en
        haut. Seul le nouveau doit partir en analyse.
        / The real use case: only the new one goes to analysis.
        """
        for mois in ("janvier", "fevrier", "mars"):
            self._ajouter_un_element(f"Compte-rendu de {mois}.")

        resultat = reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [
                {"texte": "Compte-rendu d'avril.", "label": "text"},
                {"texte": "Compte-rendu de janvier.", "label": "text"},
                {"texte": "Compte-rendu de fevrier.", "label": "text"},
                {"texte": "Compte-rendu de mars.", "label": "text"},
            ],
        )

        self.assertEqual(len(resultat["inchanges"]), 3)
        self.assertEqual(len(resultat["apparus"]), 1)
        self.assertEqual(len(resultat["disparus"]), 0)
        self.assertEqual(resultat["apparus"][0].texte, "Compte-rendu d'avril.")
        # Le document est dans le bon ordre.
        # / The document is in the right order.
        textes_dans_l_ordre = list(
            self.page_de_test.elements.filter(masque=False)
            .order_by("ordre").values_list("texte", flat=True)
        )
        self.assertEqual(textes_dans_l_ordre[0], "Compte-rendu d'avril.")
        self.assertEqual(textes_dans_l_ordre[3], "Compte-rendu de mars.")


class ContenuDupliqueTest(BasePhaseGTestCase):
    """
    La limite connue de l'empreinte : deux elements au texte identique.
    / The known fingerprint limitation: two elements with identical text.
    """

    def test_deux_elements_identiques_ne_s_ecrasent_pas(self):
        """
        Un dictionnaire empreinte -> element perdrait l'un des deux, et
        le declarerait disparu a tort. On apparie par file, un pour un.
        / A plain dict would drop one of them and wrongly call it disappeared.
        """
        premier_ordre_du_jour = self._ajouter_un_element("Ordre du jour")
        self._ajouter_un_element("Reunion de mars.")
        second_ordre_du_jour = self._ajouter_un_element("Ordre du jour")
        self._ajouter_un_element("Reunion d'avril.")

        resultat = reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [
                {"texte": "Ordre du jour", "label": "text"},
                {"texte": "Reunion de mars.", "label": "text"},
                {"texte": "Ordre du jour", "label": "text"},
                {"texte": "Reunion d'avril.", "label": "text"},
            ],
        )

        # Les quatre sont reconnus, aucun n'est declare disparu.
        # / All four recognized, none wrongly declared disappeared.
        self.assertEqual(len(resultat["inchanges"]), 4)
        self.assertEqual(len(resultat["disparus"]), 0)
        self.assertEqual(len(resultat["apparus"]), 0)
        identifiants_reconnus = {
            element.pk for element in resultat["inchanges"]
        }
        self.assertIn(premier_ordre_du_jour.pk, identifiants_reconnus)
        self.assertIn(second_ordre_du_jour.pk, identifiants_reconnus)

    def test_les_empreintes_en_double_sont_signalees(self):
        """
        L'appariement se fait dans l'ordre du document : si ces elements
        ont ete deplaces l'un par rapport a l'autre, il peut se tromper.
        On le signale plutot que de le taire.
        / Order-based pairing can be wrong; it is surfaced, not hidden.
        """
        self._ajouter_un_element("Ordre du jour")
        self._ajouter_un_element("Ordre du jour")

        resultat = reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [
                {"texte": "Ordre du jour", "label": "text"},
                {"texte": "Ordre du jour", "label": "text"},
            ],
        )

        self.assertEqual(len(resultat["empreintes_en_double"]), 1)
        self.assertEqual(
            resultat["empreintes_en_double"][0],
            empreinte_du_texte("Ordre du jour"),
        )

    def test_un_doublon_retire_ne_fait_disparaitre_qu_un_seul_element(self):
        """
        Deux elements identiques, un seul reste dans le nouveau contenu :
        exactement un doit etre declare disparu.
        / Two identical elements, one remains: exactly one disappears.
        """
        self._ajouter_un_element("Ordre du jour")
        self._ajouter_un_element("Ordre du jour")

        resultat = reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [{"texte": "Ordre du jour", "label": "text"}],
        )

        self.assertEqual(len(resultat["inchanges"]), 1)
        self.assertEqual(len(resultat["disparus"]), 1)


class NumerotationApresReingestionTest(BasePhaseGTestCase):
    """
    Les ordres apres une re-ingestion.
    / Ordering after a re-ingestion.

    LOCALISATION : hypostasis_extractor/tests/test_masquage_et_reingestion.py

    ATTENTION AU PIEGE DU TESTCASE : la contrainte d'unicite sur
    (page, ordre) est DEFERRABLE, donc verifiee au COMMIT. Or un TestCase
    ne committe jamais — il annule tout a la fin. Un etat final violant la
    contrainte passerait donc inapercu. On force la verification avec
    connection.check_constraints().
    / A TestCase never commits, so a deferred constraint is never checked:
    we force it.
    """

    def test_aucune_collision_d_ordre_avec_un_element_masque(self):
        """
        Le cas qui a fait echouer la premiere version : un element masque
        reste a l'ordre 0 et un nouvel element est cree a l'ordre 0. Ce
        conflit n'est pas transitoire — il subsiste a la fin — donc meme
        une contrainte differee le refuse, a juste titre.
        / A hidden element at order 0 permanently collides with a new one.
        """
        element_a_masquer = self._ajouter_un_element("Du bruit.")
        masquer_un_element(element_a_masquer)

        reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [
                {"texte": "Un premier passage.", "label": "text"},
                {"texte": "Un second passage.", "label": "text"},
            ],
        )

        # La contrainte tient vraiment, verification forcee.
        # / The constraint really holds, forced check.
        connection.check_constraints()

        ordres = sorted(
            self.page_de_test.elements.values_list("ordre", flat=True),
        )
        self.assertEqual(ordres, [0, 1, 2])
        self.assertEqual(len(set(ordres)), 3, "aucun ordre en double")

    def test_le_contenu_utile_vient_avant_les_masques(self):
        """
        Un element masque n'a plus de place dans le nouveau document : il
        est range a la suite du contenu utile.
        / A hidden element is filed after the useful content.
        """
        element_qui_disparait = self._ajouter_un_element("Un passage retire.")
        self._ajouter_un_element("Un passage garde.")

        reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [
                {"texte": "Un passage garde.", "label": "text"},
                {"texte": "Un nouveau passage.", "label": "text"},
            ],
        )

        connection.check_constraints()

        element_qui_disparait.refresh_from_db()
        ordres_du_contenu_utile = list(
            self.page_de_test.elements.filter(masque=False)
            .order_by("ordre").values_list("ordre", flat=True)
        )
        self.assertEqual(ordres_du_contenu_utile, [0, 1])
        # Le masque est apres tout le contenu utile.
        # / The hidden one comes after all useful content.
        self.assertEqual(element_qui_disparait.ordre, 2)

    def test_les_ordres_restent_uniques_apres_plusieurs_reingestions(self):
        """Trois passages successifs ne doivent pas creer de collision."""
        self._ajouter_un_element("Un passage initial.")

        for numero in range(3):
            reconcilier_les_elements_par_empreinte(
                self.page_de_test,
                [
                    {"texte": f"Nouveau passage {numero}.", "label": "text"},
                    {"texte": "Un passage initial.", "label": "text"},
                ],
            )
            connection.check_constraints()

        ordres = list(self.page_de_test.elements.values_list("ordre", flat=True))
        self.assertEqual(len(ordres), len(set(ordres)), "aucun ordre en double")


class ElementMasqueQuiReapparaitTest(BasePhaseGTestCase):
    """
    Un element masque a la main dont le texte revient dans la source.
    / A hand-hidden element whose text comes back in the source.
    """

    def test_la_reapparition_est_signalee_sans_creer_de_doublon(self):
        """
        L'element masque est APPARIE, pas recree.

        La spec l'exclut de la comparaison. Il serait alors recree en
        doublon, masque a son tour, exclu lui aussi, recree... Un pad
        re-ingere cinquante fois accumulerait cinquante copies du meme
        bruit. On l'apparie donc : il garde son identite, reste masque, et
        sa reapparition dans la source est signalee.
        / Paired, not recreated: otherwise each re-ingestion adds a copy.
        """
        element_masque = self._ajouter_un_element("Bruit de fond.")
        masquer_un_element(
            element_masque,
            justification="Halluciné par la transcription.",
            utilisateur=self.utilisateur_de_test,
        )

        resultat = reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [{"texte": "Bruit de fond.", "label": "text"}],
        )

        self.assertEqual(len(resultat["deja_masques_reapparus"]), 1)
        self.assertEqual(len(resultat["apparus"]), 0)
        self.assertEqual(len(resultat["disparus"]), 0)
        # Un seul element en base, toujours masque.
        # / A single element in base, still hidden.
        self.assertEqual(self.page_de_test.elements.count(), 1)
        element_masque.refresh_from_db()
        self.assertTrue(element_masque.masque)

    def test_trois_reingestions_n_accumulent_pas_de_doublons(self):
        """
        La preuve du probleme evite : re-ingerer trois fois le meme
        contenu ne doit pas laisser trois copies du bruit masque.
        / Three re-ingestions must not leave three copies.
        """
        element_masque = self._ajouter_un_element("Bruit de fond.")
        masquer_un_element(element_masque)
        contenu_source = [
            {"texte": "Bruit de fond.", "label": "text"},
            {"texte": "Un vrai passage.", "label": "text"},
        ]

        for _ in range(3):
            reconcilier_les_elements_par_empreinte(
                self.page_de_test, contenu_source,
            )

        self.assertEqual(self.page_de_test.elements.count(), 2)
        self.assertEqual(
            self.page_de_test.elements.filter(masque=True).count(), 1,
        )

    def test_un_element_masque_n_est_pas_declare_disparu(self):
        """
        Il est deja hors du contenu utile : le declarer disparu une
        seconde fois n'aurait pas de sens.
        / Already out of the useful content: not declared disappeared again.
        """
        element_masque = self._ajouter_un_element("Bruit.", masque=True)

        resultat = reconcilier_les_elements_par_empreinte(
            self.page_de_test,
            [{"texte": "Un autre contenu.", "label": "text"}],
        )

        identifiants_disparus = {
            element.pk for element in resultat["disparus"]
        }
        self.assertNotIn(element_masque.pk, identifiants_disparus)
