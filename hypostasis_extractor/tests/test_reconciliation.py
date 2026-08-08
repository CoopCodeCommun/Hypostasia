"""
Tests de la reconciliation apres correction de texte — SPEC v2 sections 6 et 7.
/ Tests for reconciliation after a text correction — SPEC v2 sections 6 and 7.

LOCALISATION : hypostasis_extractor/tests/test_reconciliation.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor.tests.test_reconciliation

Contient test_reconciliation_ambigue_detache_plutot_que_deviner, cinquieme
et dernier test nomme dans la section 10 de la spec pour l'ancre M2M.
"""

import threading

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase

from core.models import ElementDocument, EtatElement, Page, empreinte_du_texte
from hypostasis_extractor.models import (
    AncrageExtraction,
    CommentaireExtraction,
    EtatAncrage,
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)
from hypostasis_extractor.services.reconciliation import (
    reconcilier_les_portions_de_l_element,
    trouver_toutes_les_occurrences,
)


class TrouverLesOccurrencesTest(TestCase):
    """La brique de recherche, testee seule. / The search helper, tested alone."""

    def test_aucune_occurrence(self):
        self.assertEqual(trouver_toutes_les_occurrences("abcdef", "zzz"), [])

    def test_une_seule_occurrence(self):
        self.assertEqual(trouver_toutes_les_occurrences("abcdef", "cd"), [2])

    def test_plusieurs_occurrences(self):
        self.assertEqual(
            trouver_toutes_les_occurrences("le chat et le chien", "le "), [0, 11],
        )

    def test_les_occurrences_qui_se_chevauchent_comptent(self):
        """
        Dans "aaaa", chercher "aa" donne 0, 1, 2. Pour mesurer une
        ambiguite, un chevauchement est une ambiguite comme une autre.
        / Overlapping matches count as ambiguity.
        """
        self.assertEqual(trouver_toutes_les_occurrences("aaaa", "aa"), [0, 1, 2])

    def test_un_texte_vide_ne_se_trouve_nulle_part(self):
        """
        Un texte vide se « trouverait » a toutes les positions, ce qui n'a
        pas de sens et bouclerait sans fin.
        / An empty needle would match everywhere and loop forever.
        """
        self.assertEqual(trouver_toutes_les_occurrences("abcdef", ""), [])


class BaseReconciliationTestCase(TestCase):
    """Socle commun : une page, un element, un job.
    / Common ground: one page, one element, one job."""

    def setUp(self):
        self.utilisateur_de_test = get_user_model().objects.create_user(
            username="testeur_reconciliation",
            password="motdepasse_de_test_123",
        )
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-reconciliation",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="empreinte_page_reconciliation",
        )
        self.element = ElementDocument.objects.create(
            page=self.page_de_test,
            ordre=0,
            label="text",
            texte="Le jugement des personnes concernees compte.",
            empreinte_contenu=empreinte_du_texte(
                "Le jugement des personnes concernees compte.",
            ),
        )
        self.job = ExtractionJob.objects.create(
            page=self.page_de_test,
            name="Job de test reconciliation",
            prompt_description="Extraire",
            status=ExtractionJobStatus.COMPLETED
        )

    def _creer_une_extraction(self, texte="le jugement", masquee=False):
        return ExtractedEntity.objects.create(
            job=self.job,
            extraction_text=texte,
            start_char=0,
            end_char=len(texte),
            masquee=masquee,
        )

    def _ancrer(self, extraction, debut, fin, ordre=0):
        return AncrageExtraction.objects.create(
            extraction=extraction,
            element=self.element,
            ordre_dans_extraction=ordre,
            debut_dans_element=debut,
            fin_dans_element=fin,
        )


class ReconciliationTest(BaseReconciliationTestCase):
    """Les trois issues possibles pour une portion.
    / The three possible outcomes for a portion."""

    def test_un_texte_inchange_ne_touche_a_rien(self):
        """Corriger sans rien changer ne doit pas remuer les ancres."""
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, 3, 11)

        resultat = reconcilier_les_portions_de_l_element(
            self.element, self.element.texte,
        )

        self.assertEqual(resultat["exactes"], [])
        self.assertEqual(resultat["retrouvees"], [])
        self.assertEqual(resultat["detachees"], [])
        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.ANCREE)

    def test_une_portion_non_deplacee_reste_exacte(self):
        """
        La correction porte sur la FIN du texte : le passage ancre au
        debut n'a pas bouge.
        / The correction is at the END: the portion at the start did not move.
        """
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, 3, 11)  # "jugement"
        self.assertEqual(self.element.texte[3:11], "jugement")

        reconcilier_les_portions_de_l_element(
            self.element,
            "Le jugement des personnes concernees compte beaucoup.",
        )

        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.ANCREE)
        self.assertEqual(portion.debut_dans_element, 3)
        self.assertEqual(portion.texte_de_la_portion(), "jugement")

    def test_une_portion_deplacee_est_retrouvee(self):
        """
        La correction insere du texte AVANT le passage : il glisse, mais
        on le retrouve sans ambiguite.
        / Text inserted BEFORE the passage: it moves but is found again.
        """
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, 3, 11)  # "jugement"

        resultat = reconcilier_les_portions_de_l_element(
            self.element,
            "Selon nous, le jugement des personnes concernees compte.",
        )

        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.ANCREE)
        self.assertEqual(portion.texte_de_la_portion(), "jugement")
        self.assertEqual(resultat["retrouvees"], [portion.pk])

    def test_une_portion_disparue_est_detachee(self):
        """Le passage n'existe plus dans le nouveau texte."""
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, 3, 11)  # "jugement"

        resultat = reconcilier_les_portions_de_l_element(
            self.element, "Un texte entierement different maintenant.",
        )

        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)
        self.assertEqual(resultat["detachees"], [portion.pk])

    def test_reconciliation_ambigue_detache_plutot_que_deviner(self):
        """
        Test nomme dans la section 10 de la spec.

        Le passage cherche a BOUGE et apparait maintenant DEUX fois dans
        le nouveau texte. On ne peut pas savoir laquelle est la bonne.
        Choisir la premiere serait ancrer faux en silence : on detache.
        / The passage moved AND now appears twice: we detach.

        Noter que le passage doit avoir BOUGE pour que l'ambiguite se
        pose. S'il est toujours exactement a la meme position, l'ancre
        pointe encore le bon texte et la detacher detruirait une ancre
        valide — c'est le cas 1, teste par
        test_une_portion_non_deplacee_reste_exacte.
        / If the passage did not move, case 1 legitimately wins first.
        """
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, 3, 11)  # "jugement"

        nouveau_texte = "Selon le jugement et le jugement des autres."
        # Le passage n'est plus a sa position d'origine...
        # / The passage is no longer at its original position...
        self.assertNotEqual(nouveau_texte[3:11], "jugement")
        # ...et il apparait deux fois. / ...and it appears twice.
        self.assertEqual(
            trouver_toutes_les_occurrences(nouveau_texte, "jugement"), [9, 24],
        )

        resultat = reconcilier_les_portions_de_l_element(
            self.element, nouveau_texte,
        )

        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)
        self.assertEqual(resultat["detachees"], [portion.pk])
        self.assertEqual(resultat["retrouvees"], [])

    def test_le_nouveau_texte_est_bien_ecrit(self):
        """La fonction ecrit le texte : l'appelant n'a pas a le faire."""
        nouveau_texte = "Un texte corrige."

        reconcilier_les_portions_de_l_element(self.element, nouveau_texte)

        self.element.refresh_from_db()
        self.assertEqual(self.element.texte, nouveau_texte)

    def test_plusieurs_portions_sont_traitees_en_un_passage(self):
        """Chaque portion a son propre sort, dans le meme appel."""
        extraction = self._creer_une_extraction()
        portion_qui_bouge = self._ancrer(extraction, 3, 11, ordre=0)   # "jugement"
        portion_qui_disparait = self._ancrer(extraction, 37, 43, ordre=1)  # "compte"

        resultat = reconcilier_les_portions_de_l_element(
            self.element, "Voici le jugement des personnes concernees.",
        )

        portion_qui_bouge.refresh_from_db()
        portion_qui_disparait.refresh_from_db()
        self.assertEqual(portion_qui_bouge.etat_ancrage, EtatAncrage.ANCREE)
        self.assertEqual(portion_qui_disparait.etat_ancrage, EtatAncrage.DETACHEE)
        self.assertEqual(resultat["retrouvees"], [portion_qui_bouge.pk])
        self.assertEqual(resultat["detachees"], [portion_qui_disparait.pk])


class EtatApresReconciliationTest(BaseReconciliationTestCase):
    """
    Le piege du bulk_update : il ne declenche AUCUN signal.
    / The bulk_update trap: it fires NO signal.
    """

    def test_l_etat_de_l_element_est_recalcule_apres_detachement(self):
        """
        Toutes les portions detachees : l'element doit retomber LIBRE.

        Sans appel explicite a recalculer_etat_de_l_element, bulk_update
        ne declencherait aucun signal et l'element resterait DEBATTU —
        exigeant une justification pour editer un passage auquel plus
        rien n'est reellement attache.
        / Without the explicit recompute, the element would stay DEBATTU.
        """
        extraction = self._creer_une_extraction()
        self._ancrer(extraction, 3, 11)
        CommentaireExtraction.objects.create(
            entity=extraction,
            user=self.utilisateur_de_test,
            commentaire="Un desaccord.",
        )
        self.element.refresh_from_db()
        self.assertEqual(self.element.etat, EtatElement.DEBATTU)

        reconcilier_les_portions_de_l_element(
            self.element, "Un texte entierement different maintenant.",
        )

        self.element.refresh_from_db()
        self.assertEqual(self.element.etat, EtatElement.LIBRE)

    def test_l_etat_reste_debattu_si_la_portion_est_retrouvee(self):
        """Une portion retrouvee reste active : l'etat ne change pas."""
        extraction = self._creer_une_extraction()
        self._ancrer(extraction, 3, 11)
        CommentaireExtraction.objects.create(
            entity=extraction,
            user=self.utilisateur_de_test,
            commentaire="Un desaccord.",
        )

        reconcilier_les_portions_de_l_element(
            self.element,
            "Selon nous, le jugement des personnes concernees compte.",
        )

        self.element.refresh_from_db()
        self.assertEqual(self.element.etat, EtatElement.DEBATTU)


class PortionsDejaDetacheesTest(BaseReconciliationTestCase):
    """
    Une portion detachee ne doit jamais ressusciter.
    / A detached portion must never come back to life.
    """

    def test_une_portion_detachee_n_est_pas_repositionnee(self):
        """
        Ses offsets ne veulent plus rien dire. Les reutiliser pour
        decouper l'ancien texte donnerait un morceau arbitraire, qui
        pourrait « correspondre » et faire repasser la portion EXACTE sur
        un passage sans aucun rapport avec son extraction.
        / Reusing meaningless offsets could resurrect a wrong anchor.
        """
        extraction = self._creer_une_extraction(texte="jugement")
        portion = self._ancrer(extraction, 3, 11)  # "jugement"

        # Premiere edition : le passage disparait, la portion est detachee.
        # / First edit: the passage disappears, the portion is detached.
        reconcilier_les_portions_de_l_element(
            self.element, "Le critique des personnes concernees compte.",
        )
        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)
        offsets_apres_detachement = (
            portion.debut_dans_element, portion.fin_dans_element,
        )

        # Seconde edition : sans exclusion, la portion detachee serait
        # retraitee et pourrait repasser EXACTE sur "critique".
        # / Without the exclusion, it could come back as EXACTE on "critique".
        resultat = reconcilier_les_portions_de_l_element(
            self.element, "Le critique des uns seulement.",
        )

        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.DETACHEE)
        self.assertEqual(
            (portion.debut_dans_element, portion.fin_dans_element),
            offsets_apres_detachement,
            "les offsets d'une portion detachee ne doivent plus bouger",
        )
        self.assertEqual(resultat["exactes"], [])
        self.assertEqual(resultat["retrouvees"], [])

    def test_une_portion_detachee_ne_fait_pas_remonter_l_etat(self):
        """
        Si une portion detachee ressuscitait, elle ferait remonter
        l'element de LIBRE vers ANALYSE sur la foi d'une ancre fantome.
        / A resurrected portion would wrongly raise the element state.
        """
        extraction = self._creer_une_extraction(texte="jugement")
        self._ancrer(extraction, 3, 11)
        reconcilier_les_portions_de_l_element(
            self.element, "Le critique des personnes concernees compte.",
        )
        self.element.refresh_from_db()
        self.assertEqual(self.element.etat, EtatElement.LIBRE)

        reconcilier_les_portions_de_l_element(
            self.element, "Le critique des uns seulement.",
        )

        self.element.refresh_from_db()
        self.assertEqual(self.element.etat, EtatElement.LIBRE)


class EmpreinteApresCorrectionTest(BaseReconciliationTestCase):
    """
    L'empreinte doit suivre le texte.
    / The fingerprint must follow the text.
    """

    def test_l_empreinte_est_recalculee(self):
        """
        Une empreinte perimee ferait passer un element corrige pour un
        element « disparu » lors de la re-ingestion (section 5.3) : il
        serait masque, ses portions detachees, et un doublon serait cree
        puis re-analyse. On perdrait le debat attache.
        / A stale fingerprint would make re-ingestion treat a corrected
        element as a disappeared one.
        """
        nouveau_texte = "Un texte entierement corrige."

        reconcilier_les_portions_de_l_element(self.element, nouveau_texte)

        self.element.refresh_from_db()
        self.assertEqual(
            self.element.empreinte_contenu, empreinte_du_texte(nouveau_texte),
        )

    def test_l_empreinte_ne_bouge_pas_si_le_texte_ne_bouge_pas(self):
        """Retour immediat : rien n'est reecrit."""
        empreinte_avant = self.element.empreinte_contenu

        reconcilier_les_portions_de_l_element(self.element, self.element.texte)

        self.element.refresh_from_db()
        self.assertEqual(self.element.empreinte_contenu, empreinte_avant)


class ContratDeRetourTest(BaseReconciliationTestCase):
    """
    Ce que la fonction rend a son appelant.
    / What the function returns to its caller.
    """

    def test_l_ancien_texte_est_rendu_pour_le_journal(self):
        """
        La vue de la phase H doit journaliser PageEdit.donnees_avant. Sans
        ce retour, elle devrait relire le texte AVANT l'appel, hors
        verrou — donc rouvrir une course sur le journal.
        / Returned so the caller journals without an unlocked re-read.
        """
        texte_avant = self.element.texte

        resultat = reconcilier_les_portions_de_l_element(
            self.element, "Un texte corrige.",
        )

        self.assertEqual(resultat["ancien_texte"], texte_avant)

    def test_appeler_apres_avoir_ecrit_le_texte_soi_meme_ne_fait_rien(self):
        """
        Risque residuel documente : un appelant qui ecrit le texte
        lui-meme AVANT d'appeler obtient un retour immediat et des
        portions laissees a leurs anciens offsets. La fonction ne peut pas
        detecter ce cas de l'interieur. Ce test fige le comportement pour
        que personne ne le decouvre en production.
        / Documented residual risk: writing the text first yields a no-op.
        """
        extraction = self._creer_une_extraction()
        portion = self._ancrer(extraction, 3, 11)

        # L'appelant fait ce qu'il ne faut pas faire.
        # / The caller does what it must not do.
        self.element.texte = "Selon nous, le jugement des personnes comptent."
        self.element.save(update_fields=["texte"])

        resultat = reconcilier_les_portions_de_l_element(
            self.element, "Selon nous, le jugement des personnes comptent.",
        )

        # Rien n'a bouge : la portion pointe desormais le mauvais passage.
        # / Nothing moved: the portion now points at the wrong passage.
        portion.refresh_from_db()
        self.assertEqual(resultat["retrouvees"], [])
        self.assertEqual(portion.debut_dans_element, 3)


class PortionsMasqueesTest(BaseReconciliationTestCase):
    """
    Ecart assume avec la spec : les portions masquees sont repositionnees
    aussi, mais ne sont pas comptees dans le resultat.
    / Hidden portions are repositioned too, but not reported.
    """

    def test_une_portion_masquee_est_repositionnee(self):
        """
        La spec dit de les ignorer. On les traite quand meme : une portion
        laissee avec ses anciens offsets sur un texte qui a change pointe
        n'importe quoi, et ressortirait fausse au demasquage.
        / A hidden portion left behind would resurface with a wrong anchor.
        """
        extraction_masquee = self._creer_une_extraction(masquee=True)
        portion = self._ancrer(extraction_masquee, 3, 11)  # "jugement"

        reconcilier_les_portions_de_l_element(
            self.element,
            "Selon nous, le jugement des personnes concernees compte.",
        )

        portion.refresh_from_db()
        self.assertEqual(portion.etat_ancrage, EtatAncrage.ANCREE)
        # L'ancre pointe toujours le bon passage.
        # / The anchor still points to the right passage.
        self.assertEqual(portion.texte_de_la_portion(), "jugement")

    def test_une_portion_masquee_n_est_pas_comptee_dans_le_resultat(self):
        """
        Elle n'a pas a apparaitre dans « 3 extractions repositionnees »
        affiche a l'utilisateur : il ne la voit pas.
        / It must not show up in the user-facing count.
        """
        extraction_masquee = self._creer_une_extraction(masquee=True)
        self._ancrer(extraction_masquee, 3, 11)

        resultat = reconcilier_les_portions_de_l_element(
            self.element,
            "Selon nous, le jugement des personnes concernees compte.",
        )

        self.assertEqual(resultat["retrouvees"], [])
        self.assertEqual(resultat["exactes"], [])
        self.assertEqual(resultat["detachees"], [])


class ConcurrenceTest(TransactionTestCase):
    """
    Le verrou de la section 7, teste avec deux transactions reelles.
    / The section 7 lock, tested with two real transactions.

    LOCALISATION : hypostasis_extractor/tests/test_reconciliation.py

    TransactionTestCase et non TestCase : TestCase encapsule chaque test
    dans une transaction annulee a la fin, ce qui empeche deux
    transactions concurrentes de se voir.
    / TestCase wraps everything in one rolled-back transaction, which
    would hide real concurrency.
    """

    def setUp(self):
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-concurrence",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="empreinte_page_concurrence",
        )
        self.element = ElementDocument.objects.create(
            page=self.page_de_test,
            ordre=0,
            label="text",
            texte="AAAA le jugement BBBB",
            empreinte_contenu=empreinte_du_texte("AAAA le jugement BBBB"),
        )
        self.job = ExtractionJob.objects.create(
            page=self.page_de_test,
            name="Job de test concurrence",
            prompt_description="Extraire",
            status=ExtractionJobStatus.COMPLETED
        )

    def test_la_reconciliation_lit_le_texte_commite_par_l_autre_transaction(self):
        """
        Le verrou protege la LECTURE, pas seulement l'ecriture.

        POURQUOI CE TEST EST CONSTRUIT AINSI

        Un test naif — deux fils qui ecrivent, on verifie qui gagne — ne
        prouve rien : sous PostgreSQL, un UPDATE ordinaire bloque de toute
        facon sur une ligne deja verrouillee FOR UPDATE. Il passerait
        identiquement sans select_for_update dans le code teste. Il
        validerait une garantie de Postgres, pas le code.
        / A naive write-race test passes even without select_for_update:
        Postgres already serializes the UPDATE itself.

        Ce que le verrou apporte vraiment, c'est que la reconciliation lit
        ancien_texte APRES le commit de l'autre transaction, donc qu'elle
        repositionne les portions par rapport au texte REELLEMENT en base.
        Sans verrou, le fil 2 lirait le texte de depart, calculerait ses
        offsets dessus, et ecraserait le travail du fil 1 avec des ancres
        calculees sur un texte perime.
        / Without the lock, thread 2 would reposition against a stale text.

        MISE EN SCENE
        - texte de depart : "AAAA le jugement BBBB", portion sur [8:16]
        - fil 1 : insere "XX " au debut, SANS repositionner la portion
          (une ecriture brute, pas une reconciliation) -> le texte devient
          "XX AAAA le jugement BBBB" et [8:16] y vaut "le jugem"
        - fil 2 : reconcilie vers "XX AAAA le jugement CCCC"

        LE DISCRIMINANT
        - Si le fil 2 lit le texte COMMITE par le fil 1, il cherche
          ancien[8:16] = "le jugem", le trouve au meme endroit dans le
          nouveau texte -> EXACTE, offsets inchanges (8, 16).
        - Si le fil 2 lit le texte de DEPART (donc sans verrou), il
          cherche ancien[8:16] = "jugement", ne le trouve plus a la meme
          position, mais une seule fois plus loin -> RETROUVEE, offsets
          deplaces (11, 19).

        Les deux issues sont differentes et observables : c'est ce qui
        fait que ce test prouve quelque chose. Un test qui se contenterait
        de regarder qui ecrit en dernier passerait meme sans verrou, car
        PostgreSQL serialise deja l'UPDATE lui-meme.
        / Both outcomes differ and are observable: that is what makes this
        test discriminating.
        """
        extraction = ExtractedEntity.objects.create(
            job=self.job,
            extraction_text="jugement",
            start_char=0,
            end_char=8,
        )
        position_de_depart = self.element.texte.index("jugement")
        portion = AncrageExtraction.objects.create(
            extraction=extraction,
            element=self.element,
            ordre_dans_extraction=0,
            debut_dans_element=position_de_depart,
            fin_dans_element=position_de_depart + len("jugement"),
        )

        verrou_pris_par_le_premier = threading.Event()
        premier_a_commite = threading.Event()
        second_fil_termine = threading.Event()

        def premier_correcteur():
            """Prend le verrou, insere du texte au debut, commite."""
            try:
                with transaction.atomic():
                    element_verrouille = (
                        ElementDocument.objects.select_for_update().get(
                            pk=self.element.pk,
                        )
                    )
                    verrou_pris_par_le_premier.set()
                    # On laisse au second fil le temps d'arriver sur le
                    # verrou avant de commiter.
                    # / Give thread 2 time to hit the lock before committing.
                    second_fil_termine.wait(timeout=2)
                    element_verrouille.texte = "XX " + element_verrouille.texte
                    element_verrouille.save(update_fields=["texte"])
                premier_a_commite.set()
            finally:
                connection.close()

        def second_correcteur():
            """Attend que le verrou soit pris, puis reconcilie."""
            try:
                verrou_pris_par_le_premier.wait(timeout=5)
                reconcilier_les_portions_de_l_element(
                    self.element, "XX AAAA le jugement CCCC",
                )
            finally:
                second_fil_termine.set()
                connection.close()

        fil_un = threading.Thread(target=premier_correcteur)
        fil_deux = threading.Thread(target=second_correcteur)
        fil_un.start()
        fil_deux.start()
        fil_un.join(timeout=20)
        fil_deux.join(timeout=20)

        # Les deux fils sont bien alles au bout : un join expire passerait
        # silencieusement sans cette verification.
        # / A timed-out join would pass silently without this check.
        self.assertFalse(fil_un.is_alive(), "le premier fil n'a pas termine")
        self.assertFalse(fil_deux.is_alive(), "le second fil n'a pas termine")
        self.assertTrue(premier_a_commite.is_set())

        portion.refresh_from_db()
        self.element.refresh_from_db()

        # Le fil 2 a lu le texte commite par le fil 1 : ce qu'il cherchait
        # etait toujours au meme endroit, la portion n'a pas eu a bouger.
        # / Thread 2 read the committed text: the portion did not move.
        self.assertEqual(
            portion.etat_ancrage,
            EtatAncrage.ANCREE,
            "la portion a ete repositionnee : le fil 2 a lu un texte perime, "
            "donc le verrou n'a pas joue son role",
        )
        self.assertEqual(
            (portion.debut_dans_element, portion.fin_dans_element),
            (position_de_depart, position_de_depart + len("jugement")),
            "les offsets ont bouge : le fil 2 a travaille sur le texte de depart",
        )
        self.assertEqual(self.element.texte, "XX AAAA le jugement CCCC")
