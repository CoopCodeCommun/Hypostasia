"""
Tests des AVIS DES JUGES LOCAUX — plusieurs juges en parallèle.
/ Local judges' opinions: several judges side by side.

LOCALISATION : core/tests/test_avis_des_juges_locaux.py

CE QUI CHANGE PAR RAPPORT AU SECOND AVIS À COLONNES. La campagne du
18 août portait UN second juge, et le stockait dans quatre colonnes de
`SourceLink` — un choix documenté, et assumé comme une limite : « un
troisième exigerait la table ».

Le 19 août, la mesure a écarté ce juge unique (ShieldStral, 24 s de
processeur par paire) au profit de plusieurs encodeurs à moins d'une
demi-seconde. Il faut donc la table.

LE PIÈGE QUE CETTE TABLE DOIT SURVIVRE, ET C'EST LA RAISON D'ÊTRE DE LA
MOITIÉ DE CE FICHIER. `indexer_les_citations` DÉTRUIT et RECRÉE tous les
`SourceLink` d'un article à chaque mise à jour de wiki. Une table liée
en CASCADE perdrait donc tous les avis à chaque tour — c'est-à-dire
exactement les données que la campagne existe pour accumuler. Le report
doit les reporter explicitement, comme il reporte déjà les verdicts.
/ Wiki updates delete and recreate every SourceLink; the carry-over must
carry the opinions too, or a CASCADE table loses everything each round.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AvisDeVerification, EtatDeVerification, Page, SourceLink, TypeDeNote,
    TypeLien,
)
from core.services.synthese import indexer_les_citations
from core.services.verification import (
    accord_des_juges_locaux, paires_sans_avis, poser_un_avis_local,
)
from hypostasis_extractor.models import AIModel, ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()

TEXTE_DE_LA_SOURCE = (
    "Le compte rendu note que le seuil de dix mille euros déclenche le "
    "passage en assemblée."
)

# Deux juges qui ne sont PAS sur la même règle : c'est tout l'objet de
# ces tests. Lire l'un avec le seuil de l'autre ferait conclure au
# désaccord là où il y a accord.
# / Two judges on different rulers, which is the whole point.
JUGE_A = "xnli-directe v1 — CamemBERTa v2"
JUGE_B = "xnli-directe v1 — mDeBERTa v3"


class BaseDesAvisLocaux(TestCase):
    """Un article cité, vérifié par le juge de production."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="avis_locaux_test", password="motdepasse",
        )
        self.modele_ia = AIModel.objects.create(
            name="Juge de production", model_choice="mock_default",
            is_active=True,
        )
        note_source = Page.objects.create(
            url="http://exemple.local/avis-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-avis-source", title="Compte rendu",
        )
        job = ExtractionJob.objects.create(
            page=note_source, name="Analyse avis", status="completed",
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
            url="http://exemple.local/avis-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash="hash-avis-article",
            title="Synthèse à plusieurs juges", type_de_note=TypeDeNote.SYNTHESE,
        )
        self._indexer("Affirmation numéro 1.")

    def _indexer(self, phrase):
        markdown = f"{phrase}[[ext:{self.extraction.pk}]]\n"
        bilan = indexer_les_citations(self.article, markdown, None)
        self.article.text_readability = bilan["texte_nettoye"]
        self.article.save(update_fields=["text_readability"])

    def _lien(self):
        return SourceLink.objects.filter(
            page_cible=self.article, type_lien=TypeLien.CITE,
        ).get()

    def _citation_verifiee(self):
        """Une citation avec un degré de production. / A judged citation."""
        lien = self._lien()
        lien.score_de_verification = 70.0
        lien.etat_de_verification = EtatDeVerification.VERIFIE
        lien.save(update_fields=[
            "score_de_verification", "etat_de_verification",
        ])
        return lien


class UnAvisLocalPorteSaMethodeEtSonSeuilTest(BaseDesAvisLocaux):
    """Chaque juge écrit SON avis, sur SA règle."""

    def test_un_avis_porte_sa_methode_son_score_et_son_seuil(self):
        lien = self._citation_verifiee()

        poser_un_avis_local(lien, score=81.4, methode=JUGE_A, seuil=50.0)

        avis = AvisDeVerification.objects.get(lien=lien, methode=JUGE_A)
        self.assertAlmostEqual(avis.score, 81.4)
        self.assertAlmostEqual(avis.seuil, 50.0)
        self.assertIsNotNone(avis.rendu_le)

    def test_plusieurs_juges_coexistent_sur_la_meme_citation(self):
        """CE QUE LES COLONNES NE SAVAIENT PAS FAIRE. / What columns could not do."""
        lien = self._citation_verifiee()

        poser_un_avis_local(lien, score=81.4, methode=JUGE_A, seuil=50.0)
        poser_un_avis_local(lien, score=42.0, methode=JUGE_B, seuil=55.0)

        self.assertEqual(lien.avis_locaux.count(), 2)
        self.assertEqual(
            set(lien.avis_locaux.values_list("methode", flat=True)),
            {JUGE_A, JUGE_B},
        )

    def test_un_second_passage_du_meme_juge_remplace_son_avis(self):
        """Un juge n'a qu'UN avis courant. / One current opinion per judge."""
        lien = self._citation_verifiee()

        poser_un_avis_local(lien, score=81.4, methode=JUGE_A, seuil=50.0)
        poser_un_avis_local(lien, score=12.0, methode=JUGE_A, seuil=50.0)

        self.assertEqual(lien.avis_locaux.filter(methode=JUGE_A).count(), 1)
        avis = lien.avis_locaux.get(methode=JUGE_A)
        self.assertAlmostEqual(avis.score, 12.0)

    def test_un_avis_local_ne_pilote_rien(self):
        """
        LA DÉFINITION MÊME D'UN AVIS LOCAL. Il ne touche ni l'état, ni le
        degré de production, ni le libellé affiché.
        / It drives nothing: that is what makes it a second opinion.
        """
        lien = self._citation_verifiee()
        etat_avant = lien.etat_de_verification
        degre_avant = lien.score_de_verification

        poser_un_avis_local(lien, score=2.0, methode=JUGE_A, seuil=50.0)

        lien.refresh_from_db()
        self.assertEqual(lien.etat_de_verification, etat_avant)
        self.assertAlmostEqual(lien.score_de_verification, degre_avant)


class LesAvisSurviventAuxMisesAJourTest(BaseDesAvisLocaux):
    """
    LE TEST QUI JUSTIFIE LE REPORT. Sans lui, la table perdrait tous ses
    avis à chaque mise à jour de wiki, en silence.
    / Without the carry-over, every wiki update would wipe the table.
    """

    def test_la_reindexation_conserve_TOUS_les_avis(self):
        lien = self._citation_verifiee()
        poser_un_avis_local(lien, score=81.4, methode=JUGE_A, seuil=50.0)
        poser_un_avis_local(lien, score=42.0, methode=JUGE_B, seuil=55.0)

        # LE MÊME CORPS, RÉINDEXÉ — le chemin exact d'une mise à jour de
        # wiki. Le report s'appuie sur la clé (extraction, texte cité) :
        # une citation dont le texte a bougé n'est PAS la même paire, et
        # son avis ne doit justement pas la suivre.
        # / Same body, re-indexed: the actual wiki-update path.
        self._indexer("Affirmation numéro 1.")

        nouveau_lien = self._lien()
        avis = {
            avis.methode: avis
            for avis in nouveau_lien.avis_locaux.all()
        }
        self.assertEqual(set(avis), {JUGE_A, JUGE_B})
        self.assertAlmostEqual(avis[JUGE_A].score, 81.4)
        self.assertAlmostEqual(avis[JUGE_A].seuil, 50.0)
        self.assertAlmostEqual(avis[JUGE_B].score, 42.0)
        self.assertAlmostEqual(avis[JUGE_B].seuil, 55.0)


    def test_les_avis_survivent_meme_SANS_verdict_de_production(self):
        """
        LE CAS QUI PERDAIT TOUT, ET IL EST ORDINAIRE. Le report des
        VERDICTS exclut les liens `NON_VERIFIE` — légitime, ils n'ont
        pas de verdict à reporter. Mais les juges locaux, eux, notent
        ces liens-là : `preparer_les_paires_a_juger` n'écarte jamais
        `NON_VERIFIE`.

        Scénario : le juge de production échoue (clé absente, quota,
        panne) et laisse tout en `NON_VERIFIE`, tandis que les juges
        locaux — hors réseau — notent l'article entier. À la première
        mise à jour de wiki, la CASCADE emportait TOUS ces avis.
        / Local judges score NON_VERIFIE links, which the verdict
        carry-over excludes: their opinions must survive anyway.
        """
        lien = self._lien()  # aucun degré de production, donc NON_VERIFIE
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.NON_VERIFIE,
        )
        poser_un_avis_local(lien, score=81.4, methode=JUGE_A, seuil=50.0)
        poser_un_avis_local(lien, score=42.0, methode=JUGE_B, seuil=55.0)

        self._indexer("Affirmation numéro 1.")

        avis = {a.methode: a for a in self._lien().avis_locaux.all()}
        self.assertEqual(set(avis), {JUGE_A, JUGE_B})
        self.assertAlmostEqual(avis[JUGE_A].score, 81.4)
        self.assertAlmostEqual(avis[JUGE_B].seuil, 55.0)

    def test_la_date_du_jugement_n_est_pas_redatee_par_le_report(self):
        """
        LA FICHE MENTAIT SUR LA DATE. Avec `auto_now`, Django réécrivait
        `rendu_le` à chaque écriture — donc à chaque report — et le
        panneau de preuve affichait la date de la mise à jour de wiki
        comme celle du jugement.
        / auto_now silently re-dated every opinion at each wiki update.
        """
        from datetime import timedelta

        from django.utils import timezone

        lien = self._citation_verifiee()
        poser_un_avis_local(lien, score=81.4, methode=JUGE_A, seuil=50.0)
        avis = lien.avis_locaux.get(methode=JUGE_A)
        hier = timezone.now() - timedelta(days=1)
        AvisDeVerification.objects.filter(pk=avis.pk).update(rendu_le=hier)

        self._indexer("Affirmation numéro 1.")

        reporte = self._lien().avis_locaux.get(methode=JUGE_A)
        self.assertEqual(reporte.rendu_le, hier)


class LesPairesQuiRestentANoterTest(BaseDesAvisLocaux):
    """Chaque juge a sa propre liste de restes. / Each judge, its backlog."""

    def test_une_paire_deja_notee_par_ce_juge_n_est_plus_a_noter(self):
        lien = self._citation_verifiee()
        poser_un_avis_local(lien, score=81.4, methode=JUGE_A, seuil=50.0)

        self.assertEqual(paires_sans_avis(self.article, JUGE_A), [])

    def test_une_paire_notee_par_un_AUTRE_juge_reste_a_noter(self):
        lien = self._citation_verifiee()
        poser_un_avis_local(lien, score=81.4, methode=JUGE_A, seuil=50.0)

        restantes = paires_sans_avis(self.article, JUGE_B)
        self.assertEqual([paire.lien.pk for paire in restantes], [lien.pk])


class LAccordSeCompteJugeParJugeTest(BaseDesAvisLocaux):
    """
    CHAQUE JUGE EST LU AVEC SON PROPRE SEUIL. Les lire sur une règle
    commune ferait conclure au désaccord là où il y a accord.
    / Each judge read with ITS threshold.
    """

    def test_deux_juges_au_dessus_de_leur_seuil_confirment(self):
        lien = self._citation_verifiee()  # degré de production 70, seuil 45
        poser_un_avis_local(lien, score=81.0, methode=JUGE_A, seuil=50.0)
        poser_un_avis_local(lien, score=60.0, methode=JUGE_B, seuil=55.0)

        confirment, tranchent, total = accord_des_juges_locaux(lien)
        self.assertEqual((confirment, tranchent, total), (2, 2, 2))

    def test_un_juge_sous_son_seuil_ne_confirme_pas(self):
        lien = self._citation_verifiee()
        poser_un_avis_local(lien, score=81.0, methode=JUGE_A, seuil=50.0)
        poser_un_avis_local(lien, score=40.0, methode=JUGE_B, seuil=55.0)

        confirment, tranchent, total = accord_des_juges_locaux(lien)
        self.assertEqual((confirment, tranchent, total), (1, 2, 2))

    def test_un_juge_dans_la_bande_de_neutralite_ne_compte_pas(self):
        """
        LE DEFAUT QUE CETTE BANDE EMPECHE. Mesure du 19 août sur les avis
        réels : la moitié des scores tombent à moins de deux points du
        seuil, là où le modèle ne penche ni d'un côté ni de l'autre.
        Les compter ferait passer un tirage au sort pour un avis.
        / Half the real scores sit within two points of the threshold.
        """
        lien = self._citation_verifiee()
        poser_un_avis_local(lien, score=81.0, methode=JUGE_A, seuil=50.0)
        poser_un_avis_local(lien, score=50.1, methode=JUGE_B, seuil=50.0)

        confirment, tranchent, total = accord_des_juges_locaux(lien)
        self.assertEqual((confirment, tranchent, total), (1, 1, 2))

    def test_sans_degre_de_production_l_accord_est_incalculable(self):
        """
        UN CAS ORDINAIRE, PAS UNE EXCEPTION. L'appelant doit dire
        « comparaison impossible », jamais faire passer une absence pour
        un désaccord.
        / Ordinary, not exceptional: absence is not disagreement.
        """
        lien = self._lien()
        poser_un_avis_local(lien, score=81.0, methode=JUGE_A, seuil=50.0)

        self.assertIsNone(accord_des_juges_locaux(lien))

    def test_sans_aucun_avis_local_l_accord_est_incalculable(self):
        lien = self._citation_verifiee()

        self.assertIsNone(accord_des_juges_locaux(lien))
