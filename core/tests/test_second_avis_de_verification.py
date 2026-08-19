"""
Tests du SECOND AVIS de verification — deux juges en parallele.
/ Second-opinion verification tests: two judges side by side.

LOCALISATION : core/tests/test_second_avis_de_verification.py

CE QUE CETTE CAMPAGNE EST, ET CE QU'ELLE N'EST PAS. Un second juge tourne
a cote du juge de production pour etre compare a lui sur des donnees
reelles. Il rend un degre, sur SA propre echelle, avec SON propre seuil —
et il NE PILOTE RIEN : ni `etat_de_verification`, ni
`score_de_verification`, ni le libelle affiche.

POURQUOI DES COLONNES ET PAS UNE TABLE. `indexer_les_citations` DETRUIT
et RECREE tous les `SourceLink` d'un article a chaque mise a jour de wiki
(core/services/synthese.py) ; le report de verdict ne recopie que des
COLONNES. Une table liee par une cle etrangere en CASCADE aurait perdu
tous les avis a chaque tour — c'est-a-dire exactement les donnees que la
campagne existe pour accumuler. Quatre colonnes voyagent gratuitement
dans le mecanisme de report qui existe deja.
/ Columns, not a table: wiki updates delete and recreate every SourceLink,
and only columns ride the existing verdict carry-over.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    EtatDeVerification, Page, SourceLink, TypeDeNote, TypeLien,
)
from core.services.synthese import indexer_les_citations
from hypostasis_extractor.models import AIModel, ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()

TEXTE_DE_LA_SOURCE = (
    "Le compte rendu note que le seuil de dix mille euros déclenche le "
    "passage en assemblée."
)


class BaseDuSecondAvis(TestCase):
    """Un article cité, verifié par le juge de production."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="second_avis_test", password="motdepasse",
        )
        self.modele_ia = AIModel.objects.create(
            name="Juge de production", model_choice="mock_default",
            is_active=True,
        )
        note_source = Page.objects.create(
            url="http://exemple.local/second-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-second-source", title="Compte rendu",
        )
        job = ExtractionJob.objects.create(
            page=note_source, name="Analyse second", status="completed",
            ai_model=None,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=job, extraction_class="donnee",
            extraction_text=(
                "le seuil de dix mille euros déclenche le passage en assemblée"
            ),
            start_char=0, end_char=60,
        )
        self.article = Page.objects.create(
            url="http://exemple.local/second-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash="hash-second-article",
            title="Synthèse à deux juges", type_de_note=TypeDeNote.SYNTHESE,
        )
        self._indexer()

    def _markdown(self):
        return f"Affirmation numéro 1.[[ext:{self.extraction.pk}]]\n"

    def _indexer(self):
        bilan = indexer_les_citations(self.article, self._markdown(), None)
        self.article.text_readability = bilan["texte_nettoye"]
        self.article.save(update_fields=["text_readability"])

    def _lien(self):
        return SourceLink.objects.filter(
            page_cible=self.article, type_lien=TypeLien.CITE,
        ).get()

    def _juger_en_production(self, reponse):
        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch("core.llm_providers.appeler_llm", return_value=reponse):
            verifier_les_citations_d_un_article(self.article, self.modele_ia)


class LeSecondAvisSeStockeAvecSonSeuilTest(BaseDuSecondAvis):
    """
    Un degre sans son seuil n'est pas interpretable, et surtout il n'est
    pas COMPARABLE a l'autre : les deux juges ne sont pas sur la meme
    regle. Le seuil est donc FIGE sur l'avis, au moment ou l'avis est
    rendu. / The threshold is frozen on the opinion: the two judges do
    not share a ruler.
    """

    def test_un_second_avis_porte_sa_methode_son_score_et_son_seuil(self):
        from core.services.verification import poser_un_second_avis

        lien = self._lien()

        poser_un_second_avis(
            lien, score=41.0, methode="juge-local v1 (large) — Test",
            seuil_utile=38.0,
        )

        lien.refresh_from_db()
        self.assertEqual(lien.score_du_second_avis, 41.0)
        self.assertEqual(
            lien.methode_du_second_avis, "juge-local v1 (large) — Test",
        )
        self.assertEqual(lien.seuil_du_second_avis, 38.0)
        self.assertIsNotNone(lien.second_avis_rendu_le)

    def test_le_second_avis_ne_pilote_rien(self):
        # Le point qui decide : le second juge OBSERVE, il ne decide pas.
        # / The second judge observes; it never decides.
        from core.services.verification import poser_un_second_avis

        self._juger_en_production("1: 70")
        lien = self._lien()
        etat_avant = lien.etat_de_verification
        degre_avant = lien.score_de_verification

        poser_un_second_avis(
            lien, score=5.0, methode="juge-local v1 (large) — Test",
            seuil_utile=38.0,
        )

        lien.refresh_from_db()
        self.assertEqual(lien.etat_de_verification, etat_avant)
        self.assertEqual(lien.score_de_verification, degre_avant)
        self.assertEqual(etat_avant, EtatDeVerification.VERIFIE)

    def test_le_seuil_du_second_avis_est_fige_pas_relu(self):
        # Le seuil de la Configuration bouge : celui de l'avis ne bouge
        # pas. Sinon l'accord affiche pourrait contredire le libelle
        # affiche. / A moving global threshold must not rewrite the
        # frozen one carried by the opinion.
        from core.models import Configuration
        from core.services.verification import poser_un_second_avis

        lien = self._lien()
        poser_un_second_avis(
            lien, score=41.0, methode="juge-local v1 (large) — Test",
            seuil_utile=38.0,
        )

        configuration = Configuration.get_solo()
        configuration.seuil_de_verification = 90.0
        configuration.save(update_fields=["seuil_de_verification"])

        lien.refresh_from_db()
        self.assertEqual(lien.seuil_du_second_avis, 38.0)


class LeSecondAvisSurvitAuxMisesAJourTest(BaseDuSecondAvis):
    """
    LE DEFAUT QUI A FAIT ABANDONNER LA TABLE. Un wiki se reindexe a
    chaque tour : ses SourceLink sont detruits et recrees. Un avis lie
    par une cle etrangere en CASCADE aurait disparu a chaque fois — et
    la campagne n'aurait jamais accumule que ce qui a survecu depuis la
    derniere verification.
    / Wiki updates delete and recreate the links; the opinion must ride
    the existing verdict carry-over.
    """

    def test_la_reindexation_conserve_le_second_avis_en_entier(self):
        from core.services.verification import poser_un_second_avis

        self._juger_en_production("1: 70")
        poser_un_second_avis(
            self._lien(), score=41.0,
            methode="juge-local v1 (large) — Test", seuil_utile=38.0,
        )

        # Le meme corps, reindexe : le chemin d'une mise a jour de wiki.
        indexer_les_citations(self.article, self._markdown(), None)

        lien = self._lien()
        self.assertEqual(lien.score_du_second_avis, 41.0)
        self.assertEqual(lien.seuil_du_second_avis, 38.0)
        self.assertEqual(
            lien.methode_du_second_avis, "juge-local v1 (large) — Test",
        )
        self.assertIsNotNone(lien.second_avis_rendu_le)


class LesPairesQuiRestentANoterTest(BaseDuSecondAvis):
    """
    L'IDEMPOTENCE. Une paire deja notee par cette methode n'est pas
    renotee : sur un juge local a 25 s la paire, relancer une tache ne
    doit pas tout refaire.
    / Idempotence: at ~25 s a pair, re-running must not redo the work.
    """

    def test_une_paire_deja_notee_n_est_pas_rendue_a_noter(self):
        from core.services.verification import (
            paires_sans_second_avis, poser_un_second_avis,
        )

        self._juger_en_production("1: 70")
        methode = "juge-local v1 (large) — Test"

        self.assertEqual(len(paires_sans_second_avis(self.article, methode)), 1)

        poser_un_second_avis(
            self._lien(), score=41.0, methode=methode, seuil_utile=38.0,
        )

        self.assertEqual(len(paires_sans_second_avis(self.article, methode)), 0)

    def test_une_paire_notee_par_une_AUTRE_methode_reste_a_noter(self):
        # Changer de juge, c'est changer d'echelle : l'avis precedent ne
        # vaut pas pour le nouveau. / Another judge, another ruler.
        from core.services.verification import (
            paires_sans_second_avis, poser_un_second_avis,
        )

        self._juger_en_production("1: 70")
        poser_un_second_avis(
            self._lien(), score=41.0, methode="ancien juge", seuil_utile=38.0,
        )

        self.assertEqual(
            len(paires_sans_second_avis(self.article, "nouveau juge")), 1,
        )

    def test_une_citation_introuvable_n_est_pas_a_noter(self):
        # Le verbatim n'existe nulle part : il n'y a rien a juger, et
        # payer 25 s de processeur pour le confirmer serait absurde.
        # / Nothing to judge, and 25 s of CPU to confirm it would be absurd.
        from core.services.verification import paires_sans_second_avis

        ExtractedEntity.objects.filter(pk=self.extraction.pk).update(
            extraction_text="un texte qui n'apparait nulle part",
        )
        self._juger_en_production("")

        self.assertEqual(
            self._lien().etat_de_verification, EtatDeVerification.INTROUVABLE,
        )
        self.assertEqual(
            len(paires_sans_second_avis(self.article, "un juge")), 0,
        )


class LAccordSeCalculeAvecDeuxSeuilsTest(BaseDuSecondAvis):
    """
    LA REGLE QUI EMPECHE UNE COMPARAISON FAUSSE. Chaque juge est lu avec
    SON seuil. Lire 70 et 41 sur la meme regle ferait conclure au
    desaccord la ou il y a accord parfait.
    / Each judge is read with ITS threshold; a shared one would invent
    disagreements.
    """

    def _accord(self):
        from core.services.verification import accord_des_deux_juges
        return accord_des_deux_juges(self._lien())

    def test_deux_juges_au_dessus_de_leur_propre_seuil_sont_d_accord(self):
        from core.services.verification import poser_un_second_avis

        self._juger_en_production("1: 70")       # seuil 45 -> au-dessus
        poser_un_second_avis(
            self._lien(), score=41.0, methode="juge local", seuil_utile=38.0,
        )                                         # seuil 38 -> au-dessus

        self.assertIs(self._accord(), True)

    def test_un_juge_au_dessus_et_l_autre_en_dessous_divergent(self):
        from core.services.verification import poser_un_second_avis

        self._juger_en_production("1: 70")       # au-dessus de 45
        poser_un_second_avis(
            self._lien(), score=12.0, methode="juge local", seuil_utile=38.0,
        )                                         # en dessous de 38

        self.assertIs(self._accord(), False)

    def test_sans_degre_de_production_l_accord_est_incalculable(self):
        # C'EST L'ETAT DE TOUTE LA BASE AUJOURD'HUI : 145 citations, 0
        # degre — les verdicts sont anterieurs a l'addendum du 18 aout.
        # « Incalculable » n'est pas un cas limite, c'est le depart.
        # / The whole base is in this state: verdicts, but no degrees.
        from core.services.verification import poser_un_second_avis

        lien = self._lien()
        lien.etat_de_verification = EtatDeVerification.VERIFIE
        lien.verifie_par = "verbatim+nli-lot v2 — un juge d'avant"
        lien.save(update_fields=["etat_de_verification", "verifie_par"])
        poser_un_second_avis(
            lien, score=41.0, methode="juge local", seuil_utile=38.0,
        )

        self.assertIsNone(self._accord())

    def test_sans_second_avis_l_accord_est_incalculable(self):
        self._juger_en_production("1: 70")

        self.assertIsNone(self._accord())
