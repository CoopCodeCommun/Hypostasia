"""
Tests du SCORE de verification (SPEC-synthese, addendum du 18 aout 2026).
/ Verification SCORE tests (18 Aug 2026 addendum).

LOCALISATION : core/tests/test_score_de_verification.py

CE QUE L'ADDENDUM CHANGE, ET CE QU'IL NE CHANGE PAS. Le juge ne rend plus
un verdict binaire (« soutient » / « ne_soutient_pas ») mais un DEGRE de
0 a 100 : dans quelle mesure cette source etablit-elle ce que cette
affirmation avance ? Le SEUIL devient un reglage, pose sur la
Configuration, et le changer NE REJUGE RIEN — les scores sont deja en
base.

`INTROUVABLE`, `CONTESTE` et `NON_VERIFIE` sont INCHANGES : ils sont
poses sans juge, et ils ne portent pas de score.

POURQUOI CE FICHIER EST SEPARE DE `test_verification.py`. Celui-la
couvre la CASCADE (verbatim, puis juge) et ses defenses ; celui-ci
couvre le DEGRE et le SEUIL. Les deux se lisent seuls.
/ The judge now returns a 0-100 degree; the threshold is a setting, and
moving it re-labels without re-judging.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Configuration, EtatDeVerification, Page, ProvenanceDuVerbatim,
    SourceLink, TypeDeNote, TypeLien,
)
from core.services.synthese import indexer_les_citations
from hypostasis_extractor.models import (
    AIModel, CommentaireExtraction, ExtractedEntity, ExtractionJob,
)

Utilisateur = get_user_model()

TEXTE_DE_LA_SOURCE = (
    "Le compte rendu note que le seuil de dix mille euros déclenche le "
    "passage en assemblée. L'ajournement répété est présenté comme un "
    "coût en soi."
)


class BaseDuScore(TestCase):
    """Le decor commun : une note, deux extractions, un juge."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="scoreur_test", password="motdepasse",
        )
        self.modele_ia = AIModel.objects.create(
            name="Juge à score test", model_choice="mock_default",
            is_active=True,
        )
        self.note_source = Page.objects.create(
            url="http://exemple.local/score-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-score-source", title="Compte rendu de mars",
        )
        self.job_analyse = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse score", status="completed",
            ai_model=None,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=self.job_analyse, extraction_class="donnee",
            extraction_text=(
                "le seuil de dix mille euros déclenche le passage en assemblée"
            ),
            start_char=0, end_char=60,
        )

    def _creer_un_article_qui_cite(self, extractions):
        """Cree l'article et ses SourceLink par indexation reelle."""
        markdown = "\n\n".join(
            f"Affirmation numéro {numero}.[[ext:{extraction.pk}]]"
            for numero, extraction in enumerate(extractions, start=1)
        ) + "\n"
        article = Page.objects.create(
            url="http://exemple.local/score-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash="hash-score-article",
            title="Synthèse de mars", type_de_note=TypeDeNote.SYNTHESE,
        )
        bilan = indexer_les_citations(article, markdown, None)
        article.text_readability = bilan["texte_nettoye"]
        article.save(update_fields=["text_readability"])
        return article

    def _liens(self, article):
        return SourceLink.objects.filter(
            page_cible=article, type_lien=TypeLien.CITE,
        ).order_by("start_char_cible")

    def _verifier(self, article, reponse_du_juge):
        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_du_juge,
        ):
            return verifier_les_citations_d_un_article(article, self.modele_ia)


class LeJugeRendUnDegreTest(BaseDuScore):
    """Le juge rend un score, et le seuil en tire un libelle."""

    def test_un_score_au_dessus_du_seuil_pose_verifie_et_le_score(self):
        article = self._creer_un_article_qui_cite([self.extraction])

        self._verifier(article, "1: 70")

        lien = self._liens(article).get()
        self.assertEqual(lien.etat_de_verification, EtatDeVerification.VERIFIE)
        # Le score EST stocke : sans lui, changer le seuil exigerait de
        # rejuger, donc de repayer. / The score is stored.
        self.assertEqual(lien.score_de_verification, 70.0)

    def test_un_score_au_dessous_du_seuil_pose_faible_et_le_score(self):
        article = self._creer_un_article_qui_cite([self.extraction])

        self._verifier(article, "1: 40")

        lien = self._liens(article).get()
        self.assertEqual(lien.etat_de_verification, EtatDeVerification.FAIBLE)
        self.assertEqual(lien.score_de_verification, 40.0)

    def test_le_score_zero_est_un_score_pas_une_absence(self):
        # `mistral-small-latest` rend un 0 sur l'etalon (scores.json,
        # paire 10). Un `if lien.score:` l'effacerait du recalcul.
        # / Zero is a score, not a missing value.
        article = self._creer_un_article_qui_cite([self.extraction])

        self._verifier(article, "1: 0")

        lien = self._liens(article).get()
        self.assertEqual(lien.score_de_verification, 0.0)
        self.assertEqual(lien.etat_de_verification, EtatDeVerification.FAIBLE)

    def test_la_provenance_du_verdict_nomme_la_methode_a_score(self):
        # Deux methodes qui posent la meme question ne se comparent que
        # si elles portent deux noms. / Two methods, two names.
        article = self._creer_un_article_qui_cite([self.extraction])

        self._verifier(article, "1: 70")

        lien = self._liens(article).get()
        self.assertIn("nli-score", lien.verifie_par)
        self.assertIn("Juge à score test", lien.verifie_par)


class LeSeuilEstUnReglageTest(BaseDuScore):
    """
    LA PROMESSE CENTRALE DE L'ADDENDUM : changer le seuil change les
    libelles, SANS rejuger — donc sans repayer, et sans perdre la mesure
    precedente. / Moving the threshold re-labels without re-judging.
    """

    def test_changer_le_seuil_relabellise_sans_appeler_le_juge(self):
        from core.services.verification import appliquer_le_seuil

        article = self._creer_un_article_qui_cite([self.extraction])
        self._verifier(article, "1: 70")
        self.assertEqual(
            self._liens(article).get().etat_de_verification,
            EtatDeVerification.VERIFIE,
        )

        # Le seuil monte au-dessus du score : le meme lien devient faible.
        with patch("core.llm_providers.appeler_llm") as mock_llm:
            nombre_change = appliquer_le_seuil(
                SourceLink.objects.filter(page_cible=article), seuil=80.0,
            )

        mock_llm.assert_not_called()
        self.assertEqual(nombre_change, 1)
        lien = self._liens(article).get()
        self.assertEqual(lien.etat_de_verification, EtatDeVerification.FAIBLE)
        # Le SCORE, lui, n'a pas bouge : c'est la mesure, pas le libelle.
        # / The score is the measurement; only the label moved.
        self.assertEqual(lien.score_de_verification, 70.0)

    def test_le_seuil_redescendu_rend_le_libelle_precedent(self):
        from core.services.verification import appliquer_le_seuil

        article = self._creer_un_article_qui_cite([self.extraction])
        self._verifier(article, "1: 70")
        liens = SourceLink.objects.filter(page_cible=article)

        appliquer_le_seuil(liens, seuil=80.0)
        appliquer_le_seuil(liens, seuil=45.0)

        self.assertEqual(
            self._liens(article).get().etat_de_verification,
            EtatDeVerification.VERIFIE,
        )

    def test_le_seuil_par_defaut_vient_de_la_configuration(self):
        from core.services.verification import seuil_de_verification

        configuration = Configuration.objects.first() \
            or Configuration.objects.create()
        configuration.seuil_de_verification = 62.5
        configuration.save(update_fields=["seuil_de_verification"])

        self.assertEqual(seuil_de_verification(), 62.5)


class LeRecalculNeTouchePasCeQuiNaPasDeScoreTest(BaseDuScore):
    """
    Le recalcul n'a d'emprise QUE sur ce qu'un juge a note. Tout le
    reste — verdict humain, chaine de preuve cassee, jamais juge — lui
    est etranger. / The re-label only touches judged pairs.
    """

    def test_un_verdict_conteste_par_un_humain_est_ignore(self):
        from core.services.verification import appliquer_le_seuil

        article = self._creer_un_article_qui_cite([self.extraction])
        lien = self._liens(article).get()
        lien.etat_de_verification = EtatDeVerification.CONTESTE
        lien.verifie_par = "Jonas"
        lien.save(update_fields=["etat_de_verification", "verifie_par"])

        appliquer_le_seuil(
            SourceLink.objects.filter(page_cible=article), seuil=0.0,
        )

        lien.refresh_from_db()
        self.assertEqual(lien.etat_de_verification, EtatDeVerification.CONTESTE)

    def test_une_paire_heritee_sans_score_reste_telle_quelle(self):
        # Les 145 paires gelees du 17 aout portent un verdict binaire et
        # AUCUN score. Elles ne sont pas rejugees, et le seuil ne les
        # touche pas. / The 145 frozen pairs carry no score.
        from core.services.verification import appliquer_le_seuil

        article = self._creer_un_article_qui_cite([self.extraction])
        lien = self._liens(article).get()
        lien.etat_de_verification = EtatDeVerification.VERIFIE
        lien.verifie_par = "verbatim+nli-lot v2 — Gemini 2.5 Flash"
        lien.score_de_verification = None
        lien.save(update_fields=[
            "etat_de_verification", "verifie_par", "score_de_verification",
        ])

        nombre_change = appliquer_le_seuil(
            SourceLink.objects.filter(page_cible=article), seuil=99.0,
        )

        lien.refresh_from_db()
        self.assertEqual(nombre_change, 0)
        self.assertEqual(lien.etat_de_verification, EtatDeVerification.VERIFIE)

    def test_une_citation_introuvable_n_a_pas_de_score(self):
        # INTROUVABLE est pose par le VERBATIM seul, sans juge : il n'y a
        # pas de degre a porter. Et s'il en restait un d'un jugement
        # anterieur, il serait EFFACE — un score sans verdict qui le
        # constate est un chiffre orphelin.
        # / INTROUVABLE is set without a judge: any stale score is erased.
        article = self._creer_un_article_qui_cite([self.extraction])
        self._verifier(article, "1: 70")
        ExtractedEntity.objects.filter(pk=self.extraction.pk).update(
            extraction_text="un texte qui n'apparait nulle part",
        )

        self._verifier(article, "")

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.INTROUVABLE,
        )
        self.assertIsNone(lien.score_de_verification)


class LeRecalculRespecteLesEchellesTest(BaseDuScore):
    """
    Deux juges n'ont pas la meme echelle. Mesure du 18 aout : le seuil
    utile est 45/100 pour un juge d'API a qui on demande un nombre, et
    37,8/100 pour un juge local a logits. Relabelliser les scores d'un
    juge avec le seuil d'un autre ferait passer pour « verifie » ce que
    le premier avait note « appuie de loin ».
    / Judges do not share a scale; a global re-label must not cross them.
    """

    def test_le_recalcul_laisse_les_scores_d_un_autre_juge_intacts(self):
        from core.services.verification import appliquer_le_seuil

        article = self._creer_un_article_qui_cite([self.extraction])
        self._verifier(article, "1: 40")
        lien = self._liens(article).get()
        provenance_d_origine = lien.verifie_par

        nombre_change = appliquer_le_seuil(
            SourceLink.objects.filter(page_cible=article), seuil=0.0,
            provenance="verbatim+nli-score v3 — un tout autre juge",
        )

        lien.refresh_from_db()
        self.assertEqual(nombre_change, 0)
        self.assertEqual(lien.etat_de_verification, EtatDeVerification.FAIBLE)
        self.assertEqual(lien.verifie_par, provenance_d_origine)


class LaProvenanceDuVerbatimSurvitAuCommentaireTest(BaseDuScore):
    """
    Le recalcul doit savoir OU le verbatim a ete trouve — dans la source
    ou dans un commentaire du debat — pour choisir entre `VERIFIE` et
    `SOURCE_DEBAT` au-dessus du seuil.

    IL NE PEUT PAS LE DEDUIRE DE `commentaires_source` :
    `CommentaireExtraction.entity` et `.user` sont tous deux en CASCADE.
    Supprimer une extraction ou un compte efface le temoin, et le
    recalcul poserait alors `VERIFIE` sur un verbatim qui n'a JAMAIS ete
    dans la source. D'ou un champ propre, pose par le parcours
    deterministe : il enregistre un FAIT, pas un verdict.
    / The M2M witness is destructible by CASCADE; a dedicated field is not.
    """

    def setUp(self):
        super().setUp()
        # Le verbatim n'est PAS dans la source, mais dans un commentaire.
        # / The quote lives in a debate comment, not in the source.
        ExtractedEntity.objects.filter(pk=self.extraction.pk).update(
            extraction_text="une reformulation absente du compte rendu",
        )
        self.extraction.refresh_from_db()
        self.commentaire = CommentaireExtraction.objects.create(
            entity=self.extraction, user=self.utilisateur,
            commentaire=(
                "Je précise : une reformulation absente du compte rendu, "
                "mais que nous avons bien dite en séance."
            ),
        )

    def test_une_paire_sourcee_par_le_debat_porte_sa_provenance(self):
        article = self._creer_un_article_qui_cite([self.extraction])

        self._verifier(article, "1: 70")

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.SOURCE_DEBAT,
        )
        self.assertEqual(
            lien.provenance_du_verbatim, ProvenanceDuVerbatim.DEBAT,
        )

    def test_la_bascule_reste_reversible_apres_suppression_du_commentaire(self):
        from core.services.verification import appliquer_le_seuil

        article = self._creer_un_article_qui_cite([self.extraction])
        self._verifier(article, "1: 70")
        liens = SourceLink.objects.filter(page_cible=article)

        # Le commentaire disparait — CASCADE sur l'extraction ou sur le
        # compte de son auteur. Le temoin M2M n'existe plus.
        self.commentaire.delete()

        appliquer_le_seuil(liens, seuil=80.0)
        self.assertEqual(
            self._liens(article).get().etat_de_verification,
            EtatDeVerification.FAIBLE,
        )

        appliquer_le_seuil(liens, seuil=45.0)
        # SANS le champ de provenance, ce serait VERIFIE : un verbatim
        # qui n'a jamais ete dans la source, blanchi par un reglage
        # d'affichage. / Without the field, this would read VERIFIE.
        self.assertEqual(
            self._liens(article).get().etat_de_verification,
            EtatDeVerification.SOURCE_DEBAT,
        )


class LeDegreVoyageAvecLeVerdictTest(BaseDuScore):
    """
    Un wiki se met a jour a chaque tour, et sa reindexation DETRUIT puis
    RECREE ses SourceLink en reportant les verdicts. Si le degre ne
    voyageait pas avec eux, le lien recree garderait « verifie » avec un
    score NULL — donc sortirait DEFINITIVEMENT du recalcul. Un article
    vivant perdrait sa sensibilite au seuil des sa premiere mise a jour,
    sans que rien ne le signale.
    / The verdict carry-over must take the degree with it, or living
    articles silently freeze out of every future threshold change.
    """

    def test_la_reindexation_conserve_le_degre_et_sa_provenance(self):
        from core.models import SourceLink as ModeleDeLien

        article = self._creer_un_article_qui_cite([self.extraction])
        self._verifier(article, "1: 70")
        texte_precedent = article.text_readability

        # Le meme corps, reindexe : c'est le chemin d'une mise a jour de
        # wiki dont ce paragraphe n'a pas bouge.
        # / Same body, re-indexed: a wiki update leaving this paragraph.
        markdown = f"Affirmation numéro 1.[[ext:{self.extraction.pk}]]\n"
        self.assertIn("[[ext:", markdown)
        indexer_les_citations(article, markdown, None)

        lien = ModeleDeLien.objects.filter(
            page_cible=article, type_lien=TypeLien.CITE,
        ).get()
        self.assertNotEqual(texte_precedent, "")
        self.assertEqual(lien.etat_de_verification, EtatDeVerification.VERIFIE)
        self.assertEqual(lien.score_de_verification, 70.0)
        self.assertEqual(
            lien.provenance_du_verbatim, ProvenanceDuVerbatim.SOURCE,
        )

    def test_le_lien_reporte_reste_sensible_au_seuil(self):
        from core.services.verification import appliquer_le_seuil

        article = self._creer_un_article_qui_cite([self.extraction])
        self._verifier(article, "1: 70")
        markdown = f"Affirmation numéro 1.[[ext:{self.extraction.pk}]]\n"
        indexer_les_citations(article, markdown, None)

        nombre_change = appliquer_le_seuil(
            SourceLink.objects.filter(page_cible=article), seuil=80.0,
        )

        self.assertEqual(nombre_change, 1)
        self.assertEqual(
            self._liens(article).get().etat_de_verification,
            EtatDeVerification.FAIBLE,
        )


class LeParseurDesScoresTest(BaseDuScore):
    """
    Le parseur n'accepte QUE des entiers 0-100, et rejette un lot
    structurellement suspect EN ENTIER. / Integers only; structurally
    suspicious batches are voided whole.
    """

    def test_un_score_sur_l_echelle_zero_un_ne_produit_aucun_verdict(self):
        # LE MODE D'ECHEC LE PLUS PROBABLE D'UN FUTUR JUGE. Un modele qui
        # repond « 0.92 » au lieu de « 92 » rend des valeurs DANS les
        # bornes : si le parseur les acceptait, tout le lot basculerait
        # en « faible » SANS UNE ERREUR. Refuser la ligne laisse la paire
        # sans verdict — et un echec du juge ne degrade RIEN (§ 7).
        # / A 0-1 scale answer would silently mark the whole batch weak.
        article = self._creer_un_article_qui_cite([self.extraction])

        bilan = self._verifier(article, "1: 0.92")

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.NON_VERIFIE,
        )
        self.assertIsNone(lien.score_de_verification)
        self.assertEqual(bilan["sans_verdict"], 1)

    def test_un_score_hors_bornes_ne_perd_que_sa_paire(self):
        # Une anomalie de VALEUR n'est pas une anomalie de STRUCTURE :
        # rejeter dix-neuf bons verdicts pour un « 250 » isole serait
        # une degradation, et le § 7 l'interdit.
        # / A value anomaly is not a structural one: it costs one pair.
        article = self._creer_un_article_qui_cite([self.extraction])

        bilan = self._verifier(article, "1: 250")

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.NON_VERIFIE,
        )
        self.assertEqual(bilan["sans_verdict"], 1)

    def test_un_indice_duplique_rejette_le_lot_en_entier(self):
        # Inchange depuis la v2 : c'est la signature d'une injection.
        # / Unchanged from v2: this is an injection signature.
        article = self._creer_un_article_qui_cite([self.extraction])

        self._verifier(article, "1: 70\n1: 0")

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.NON_VERIFIE,
        )
        self.assertIsNone(lien.score_de_verification)
