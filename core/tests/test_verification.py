"""
Tests de la verification des citations (SPEC-synthese § 7, phase G).
/ Citation verification tests (phase G).

LOCALISATION : core/tests/test_verification.py

Deux controles en cascade, PAR PAIRE (affirmation, source) : le
VERBATIM (deterministe — le texte cite existe-t-il litteralement dans
la source ?) puis l'IMPLICATION (NLI — la source soutient-elle
l'affirmation ?), jugee par le LLM configure, EN LOT (question ouverte
n°3 tranchee le 9 aout). L'etat porte sa provenance (§ 7.2) : un etat
sans provenance est un argument d'autorite automatise. Un verdict
humain (CONTESTE) n'est jamais ecrase. Une affirmation qui reprend
fidelement un COMMENTAIRE n'est pas « faible » : elle est sourcee par
le debat (§ 7.4).
/ Verbatim then batched-LLM NLI, per pair, with provenance; human
verdicts never overwritten; debate-sourced claims recognized.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    EtatDeVerification, Page, SourceLink, TypeDeNote, TypeLien,
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


class VerificationDesCitationsTest(TestCase):
    """La cascade § 7.1 et ses etats. / The § 7.1 cascade and states."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="verificateur_test", password="motdepasse",
        )
        self.modele_ia = AIModel.objects.create(
            name="Juge NLI test", model_choice="mock_default", is_active=True,
        )
        self.note_source = Page.objects.create(
            url="http://exemple.local/sg-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-sg-source", title="Compte rendu de mars",
        )
        self.job_analyse = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse G", status="completed",
            ai_model=None,
        )
        self.extraction_seuil = ExtractedEntity.objects.create(
            job=self.job_analyse, extraction_class="donnee",
            extraction_text=(
                "le seuil de dix mille euros déclenche le passage en assemblée"
            ),
            start_char=0, end_char=60,
        )
        self.extraction_cout = ExtractedEntity.objects.create(
            job=self.job_analyse, extraction_class="argument",
            extraction_text="L'ajournement répété est présenté comme un coût",
            start_char=61, end_char=108,
        )

    def _creer_un_article_qui_cite(self, extractions):
        """Cree l'article et ses SourceLink par indexation reelle.
        / Creates the article and its links through real indexing."""
        markdown = "\n\n".join(
            f"Affirmation numéro {numero}.[[ext:{extraction.pk}]]"
            for numero, extraction in enumerate(extractions, start=1)
        ) + "\n"
        article = Page.objects.create(
            url="http://exemple.local/sg-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash="hash-sg-article",
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

    def test_une_citation_verbatim_et_soutenue_est_verifiee(self):
        article = self._creer_un_article_qui_cite([self.extraction_seuil])

        with patch(
            "core.llm_providers.appeler_llm", return_value="1: soutient",
        ) as mock_llm:
            from core.services.verification import (
                verifier_les_citations_d_un_article,
            )
            bilan = verifier_les_citations_d_un_article(
                article, self.modele_ia,
            )

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.VERIFIE,
        )
        # § 7.2 : l'etat porte son verificateur et sa date.
        # / § 7.2: the verdict carries its judge and date.
        self.assertIn("Juge NLI test", lien.verifie_par)
        self.assertIsNotNone(lien.verifie_le)
        self.assertEqual(bilan["verifiees"], 1)
        self.assertEqual(mock_llm.call_count, 1)

    def test_une_citation_dont_le_texte_a_derive_est_introuvable_sans_nli(self):
        # Le verbatim echoue : la citation exacte n'existe plus dans la
        # source — inutile de payer un appel NLI (cascade § 7.1). Et ce
        # n'est PAS « faible » : la citation est INTROUVABLE, ce qui ne
        # dit pas la meme chose (voir la classe dediee plus bas).
        # / Verbatim fails: no LLM call, and the verdict is INTROUVABLE.
        article = self._creer_un_article_qui_cite([self.extraction_seuil])
        ExtractedEntity.objects.filter(pk=self.extraction_seuil.pk).update(
            extraction_text="un texte qui n'apparait nulle part",
        )

        with patch("core.llm_providers.appeler_llm") as mock_llm:
            from core.services.verification import (
                verifier_les_citations_d_un_article,
            )
            verifier_les_citations_d_un_article(article, self.modele_ia)

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.INTROUVABLE,
        )
        self.assertFalse(mock_llm.called)

    def test_le_verbatim_tolere_les_espaces_et_retours_ligne(self):
        # La source peut avoir des retours a la ligne la ou l'extraction
        # a des espaces : seule la suite des mots compte.
        # / Whitespace-insensitive verbatim.
        self.note_source.text_readability = TEXTE_DE_LA_SOURCE.replace(
            "dix mille euros", "dix\nmille   euros",
        )
        self.note_source.save(update_fields=["text_readability"])
        article = self._creer_un_article_qui_cite([self.extraction_seuil])

        with patch(
            "core.llm_providers.appeler_llm", return_value="1: soutient",
        ):
            from core.services.verification import (
                verifier_les_citations_d_un_article,
            )
            verifier_les_citations_d_un_article(article, self.modele_ia)

        self.assertEqual(
            self._liens(article).get().etat_de_verification,
            EtatDeVerification.VERIFIE,
        )

    def test_une_affirmation_reprise_du_debat_est_source_par_le_debat(self):
        # § 7.4 : l'extraction a derive mais un COMMENTAIRE porte le
        # texte cite — provenance legitime, pas « faible ».
        # / § 7.4: a claim faithfully echoing a comment is debate-sourced.
        ExtractedEntity.objects.filter(pk=self.extraction_cout.pk).update(
            extraction_text="un avenant écrit a été chiffré à trois cents euros",
        )
        commentaire = CommentaireExtraction.objects.create(
            entity=self.extraction_cout, user=self.utilisateur,
            commentaire=(
                "Précision : un avenant écrit a été chiffré à trois "
                "cents euros par le prestataire."
            ),
        )
        article = self._creer_un_article_qui_cite([self.extraction_cout])

        # Depuis la relecture G (I4), la fidelite au commentaire se juge
        # AUSSI : le chemin debat passe par le juge NLI.
        # / Debate fidelity is judged too (review G, I4).
        with patch(
            "core.llm_providers.appeler_llm", return_value="1: soutient",
        ) as mock_llm:
            from core.services.verification import (
                verifier_les_citations_d_un_article,
            )
            verifier_les_citations_d_un_article(article, self.modele_ia)

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.SOURCE_DEBAT,
        )
        self.assertIn(commentaire, lien.commentaires_source.all())
        self.assertTrue(mock_llm.called)

    def test_le_nli_en_lot_departage_en_un_seul_appel(self):
        article = self._creer_un_article_qui_cite(
            [self.extraction_seuil, self.extraction_cout],
        )

        with patch(
            "core.llm_providers.appeler_llm",
            return_value="1: soutient\n2: ne_soutient_pas",
        ) as mock_llm:
            from core.services.verification import (
                verifier_les_citations_d_un_article,
            )
            bilan = verifier_les_citations_d_un_article(
                article, self.modele_ia,
            )

        liens = list(self._liens(article))
        self.assertEqual(
            liens[0].etat_de_verification, EtatDeVerification.VERIFIE,
        )
        self.assertEqual(
            liens[1].etat_de_verification, EtatDeVerification.FAIBLE,
        )
        # UN appel pour N paires (decision Q3). / One call for N pairs.
        self.assertEqual(mock_llm.call_count, 1)
        self.assertEqual(bilan["verifiees"], 1)
        self.assertEqual(bilan["faibles"], 1)

    def test_une_reponse_inexploitable_laisse_non_verifie_et_signale(self):
        # Un verdict manquant ne devient JAMAIS un faux VERIFIE : la
        # paire reste NON_VERIFIE et le bilan le signale.
        # / A missing verdict never becomes a false positive.
        article = self._creer_un_article_qui_cite([self.extraction_seuil])

        with patch(
            "core.llm_providers.appeler_llm",
            return_value="je ne peux pas juger cela",
        ):
            from core.services.verification import (
                verifier_les_citations_d_un_article,
            )
            bilan = verifier_les_citations_d_un_article(
                article, self.modele_ia,
            )

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.NON_VERIFIE,
        )
        self.assertEqual(bilan["sans_verdict"], 1)

    def test_un_verdict_humain_n_est_pas_ecrase(self):
        # § 7.2 : l'etat est contestable — un CONTESTE pose par un
        # humain survit a toute re-verification automatique.
        # / A human CONTESTE verdict survives re-verification.
        article = self._creer_un_article_qui_cite([self.extraction_seuil])
        self._liens(article).update(
            etat_de_verification=EtatDeVerification.CONTESTE,
            verifie_par="Amina (contestation humaine)",
        )

        with patch(
            "core.llm_providers.appeler_llm", return_value="1: soutient",
        ) as mock_llm:
            from core.services.verification import (
                verifier_les_citations_d_un_article,
            )
            verifier_les_citations_d_un_article(article, self.modele_ia)

        lien = self._liens(article).get()
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.CONTESTE,
        )
        self.assertEqual(lien.verifie_par, "Amina (contestation humaine)")
        # Rien a juger -> pas d'appel. / Nothing to judge, no call.
        self.assertFalse(mock_llm.called)


class CorrectifsRelectureGTest(TestCase):
    """
    Correctifs de la relecture adverse de la phase G (9 aout, nuit).
    / Fixes from the phase G adversarial review.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="relecture_g_test", password="motdepasse",
        )
        self.modele_ia = AIModel.objects.create(
            name="Juge G", model_choice="mock_default", is_active=True,
        )
        self.note_source = Page.objects.create(
            url="http://exemple.local/rg-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-rg-source", title="Compte rendu",
        )
        self.job_analyse = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse RG", status="completed",
            ai_model=None,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=self.job_analyse, extraction_class="donnee",
            extraction_text=(
                "le seuil de dix mille euros déclenche le passage en assemblée"
            ),
            start_char=0, end_char=60,
        )

    def _creer_un_article_qui_cite(self, extraction, suffixe="rg"):
        markdown = f"Une affirmation sourcée.[[ext:{extraction.pk}]]\n"
        article = Page.objects.create(
            url=f"http://exemple.local/{suffixe}-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash=f"hash-{suffixe}-a",
            title="Synthèse RG", type_de_note=TypeDeNote.SYNTHESE,
        )
        bilan = indexer_les_citations(article, markdown, None)
        article.text_readability = bilan["texte_nettoye"]
        article.save(update_fields=["text_readability"])
        return article

    def _lien(self, article):
        return SourceLink.objects.get(
            page_cible=article, type_lien=TypeLien.CITE,
        )

    def _verifier(self, article, reponse_du_juge="1: soutient"):
        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_du_juge,
        ) as mock_llm:
            from core.services.verification import (
                verifier_les_citations_d_un_article,
            )
            bilan = verifier_les_citations_d_un_article(
                article, self.modele_ia,
            )
        return bilan, mock_llm

    # ----- B1 : les verdicts survivent a la re-indexation -----

    def test_les_verdicts_survivent_a_une_reindexation_inchangee(self):
        article = self._creer_un_article_qui_cite(self.extraction)
        self._verifier(article)
        self.assertEqual(
            self._lien(article).etat_de_verification,
            EtatDeVerification.VERIFIE,
        )

        # Re-indexation du MEME texte (un tour de wiki qui n'a pas
        # touche ce paragraphe). / Re-indexing the same paragraph.
        bilan = indexer_les_citations(
            article, article.text_readability, None,
        )

        lien = self._lien(article)
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.VERIFIE,
        )
        self.assertNotEqual(lien.verifie_par, "")
        self.assertEqual(bilan["verdicts_reportes"], 1)

    def test_une_contestation_sur_un_paragraphe_disparu_est_signalee(self):
        article = self._creer_un_article_qui_cite(self.extraction)
        SourceLink.objects.filter(page_cible=article).update(
            etat_de_verification=EtatDeVerification.CONTESTE,
            verifie_par="Amina (contestation humaine)",
        )

        # Le paragraphe change : la paire contestee n'existe plus. La
        # contestation ne peut pas etre reportee — mais JAMAIS perdue
        # en silence. / The contested pair vanished: loudly reported.
        nouveau_markdown = (
            f"Une toute autre affirmation.[[ext:{self.extraction.pk}]]\n"
        )
        bilan = indexer_les_citations(article, nouveau_markdown, None)

        self.assertEqual(len(bilan["contestations_perdues"]), 1)
        lien = self._lien(article)
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.NON_VERIFIE,
        )

    # ----- B2 : le parsing du juge refuse les reponses suspectes -----

    def test_des_indices_dupliques_invalident_tout_le_lot(self):
        # Un indice duplique est la signature d'une injection (ou d'un
        # juge deraille) : AUCUN verdict n'est pose.
        # / Duplicate indexes void the whole batch.
        article = self._creer_un_article_qui_cite(self.extraction)

        bilan, _mock = self._verifier(
            article, "1: ne_soutient_pas\n1: soutient",
        )

        self.assertEqual(
            self._lien(article).etat_de_verification,
            EtatDeVerification.NON_VERIFIE,
        )
        self.assertEqual(bilan["sans_verdict"], 1)

    def test_un_indice_hors_lot_invalide_tout_le_lot(self):
        article = self._creer_un_article_qui_cite(self.extraction)

        bilan, _mock = self._verifier(
            article, "1: soutient\n7: soutient",
        )

        self.assertEqual(
            self._lien(article).etat_de_verification,
            EtatDeVerification.NON_VERIFIE,
        )
        self.assertEqual(bilan["sans_verdict"], 1)

    # ----- I1 : une exception du juge ne laisse pas un demi-verdict -----

    def test_une_exception_du_juge_est_signalee_sans_degrader(self):
        article = self._creer_un_article_qui_cite(self.extraction)
        self._verifier(article)  # verdict initial VERIFIE
        with patch(
            "core.llm_providers.appeler_llm",
            side_effect=RuntimeError("timeout"),
        ):
            from core.services.verification import (
                verifier_les_citations_d_un_article,
            )
            bilan = verifier_les_citations_d_un_article(
                article, self.modele_ia,
            )

        # Le verdict precedent SURVIT a l'echec technique, et l'echec
        # est dans le bilan. / Prior verdicts survive a technical failure.
        self.assertEqual(
            self._lien(article).etat_de_verification,
            EtatDeVerification.VERIFIE,
        )
        self.assertIn("timeout", bilan["erreur_du_juge"])

    # ----- I2 : une source supprimee perd son verdict vert -----

    def test_une_source_supprimee_perd_son_verdict(self):
        article = self._creer_un_article_qui_cite(self.extraction)
        self._verifier(article)
        SourceLink.objects.filter(page_cible=article).update(
            extraction_source=None,
        )

        bilan, mock_llm = self._verifier(article, "")

        lien = self._lien(article)
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.NON_VERIFIE,
        )
        self.assertIn("supprim", lien.verifie_par.lower())
        self.assertEqual(bilan["sources_absentes"], 1)
        self.assertFalse(mock_llm.called)

    # ----- I3 : des bornes perimees ne sont jamais jugees -----

    def test_des_bornes_perimees_ne_sont_pas_jugees(self):
        article = self._creer_un_article_qui_cite(self.extraction)
        # Le corps a ete edite SANS re-indexation : les bornes pointent
        # du texte decale. / Body edited without re-indexing.
        article.text_readability = "Texte entièrement réécrit sans marqueur."
        article.save(update_fields=["text_readability"])

        bilan, mock_llm = self._verifier(article)

        self.assertFalse(mock_llm.called)
        self.assertEqual(bilan["bornes_perimees"], 1)
        self.assertEqual(
            self._lien(article).etat_de_verification,
            EtatDeVerification.NON_VERIFIE,
        )

    # ----- I4 : le debat aussi passe au juge -----

    def test_une_reprise_du_debat_infidele_est_faible(self):
        ExtractedEntity.objects.filter(pk=self.extraction.pk).update(
            extraction_text="un avenant écrit a été chiffré à trois cents euros",
        )
        CommentaireExtraction.objects.create(
            entity=self.extraction, user=self.utilisateur,
            commentaire="Précision : un avenant écrit a été chiffré à trois cents euros.",
        )
        article = self._creer_un_article_qui_cite(self.extraction)

        # Le juge dit que le commentaire NE soutient PAS le paragraphe.
        # / The judge says the comment does not support the claim.
        bilan, mock_llm = self._verifier(article, "1: ne_soutient_pas")

        self.assertTrue(mock_llm.called)
        self.assertEqual(
            self._lien(article).etat_de_verification,
            EtatDeVerification.FAIBLE,
        )

    def test_une_reprise_du_debat_fidele_est_source_debat(self):
        ExtractedEntity.objects.filter(pk=self.extraction.pk).update(
            extraction_text="un avenant écrit a été chiffré à trois cents euros",
        )
        CommentaireExtraction.objects.create(
            entity=self.extraction, user=self.utilisateur,
            commentaire="Précision : un avenant écrit a été chiffré à trois cents euros.",
        )
        article = self._creer_un_article_qui_cite(self.extraction)

        bilan, _mock = self._verifier(article, "1: soutient")

        self.assertEqual(
            self._lien(article).etat_de_verification,
            EtatDeVerification.SOURCE_DEBAT,
        )
        self.assertEqual(bilan["sourcees_debat"], 1)

    # ----- I6 : une extraction masquee n'est pas blanchie -----

    def test_une_extraction_masquee_n_est_pas_jugee(self):
        article = self._creer_un_article_qui_cite(self.extraction)
        ExtractedEntity.objects.filter(pk=self.extraction.pk).update(
            masquee=True,
        )

        bilan, mock_llm = self._verifier(article)

        self.assertFalse(mock_llm.called)
        self.assertEqual(bilan["non_jugeables"], 1)
        self.assertEqual(
            self._lien(article).etat_de_verification,
            EtatDeVerification.NON_VERIFIE,
        )

    # ----- I7 : commentaires_source suit le verdict -----

    def test_les_commentaires_source_obsoletes_sont_vides(self):
        ExtractedEntity.objects.filter(pk=self.extraction.pk).update(
            extraction_text="un avenant écrit a été chiffré à trois cents euros",
        )
        commentaire = CommentaireExtraction.objects.create(
            entity=self.extraction, user=self.utilisateur,
            commentaire="Précision : un avenant écrit a été chiffré à trois cents euros.",
        )
        article = self._creer_un_article_qui_cite(self.extraction)
        self._verifier(article, "1: soutient")  # SOURCE_DEBAT + commentaire
        self.assertEqual(
            self._lien(article).commentaires_source.count(), 1,
        )

        # Le commentaire est edite : plus aucun verbatim ne le porte.
        # / The comment was edited: nothing carries the quote anymore.
        CommentaireExtraction.objects.filter(pk=commentaire.pk).update(
            commentaire="Reformulé sans la citation.",
        )
        self._verifier(article, "")

        lien = self._lien(article)
        # INTROUVABLE et non FAIBLE : le texte cite n'est plus NULLE
        # PART — ni dans la source, ni dans le commentaire edite. La
        # chaine de preuve est rompue, ce n'est pas un soutien
        # insuffisant. / The quote is nowhere anymore: broken, not weak.
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.INTROUVABLE,
        )
        self.assertEqual(lien.commentaires_source.count(), 0)

    # ----- M2 : la typographie ne casse pas le verbatim -----

    def test_l_apostrophe_typographique_ne_casse_pas_le_verbatim(self):
        ExtractedEntity.objects.filter(pk=self.extraction.pk).update(
            extraction_text="l'ajournement répété est présenté comme un coût",
        )
        self.note_source.text_readability = (
            "Le compte rendu note que l’ajournement répété est "
            "présenté comme un coût en soi."
        )
        self.note_source.save(update_fields=["text_readability"])
        article = self._creer_un_article_qui_cite(self.extraction)

        self._verifier(article, "1: soutient")

        self.assertEqual(
            self._lien(article).etat_de_verification,
            EtatDeVerification.VERIFIE,
        )


class DeuxRoutesVersLEchecTest(TestCase):
    """
    « Citation introuvable » et « faible » sont deux signaux distincts.
    / "Quote not found" and "weak support" are two distinct signals.

    LOCALISATION : core/tests/test_verification.py

    Les deux echecs se confondaient sous un seul verdict FAIBLE. Ils ne
    disent pourtant pas la meme chose, et ne se reparent pas pareil :

    - INTROUVABLE — le texte que la citation pretend citer n'est plus
      dans la source. La CHAINE DE PREUVE est cassee : soit le modele a
      deforme la citation, soit la source a ete editee depuis
      l'extraction. C'est un signal d'INTEGRITE, et le controle est
      deterministe (aucun juge n'intervient).
    - FAIBLE — le passage existe bel et bien, mais il n'etablit pas ce
      que l'affirmation avance. C'est un signal d'ATTRIBUTION, et c'est
      un juge qui le pose.

    L'etat de l'art mesure que 80,6 % des affirmations invérifiables
    sont des erreurs d'attribution et non des hallucinations : savoir
    dans laquelle des deux populations on se trouve est precisement ce
    qui rend le chiffre actionnable.
    / Integrity vs attribution: different causes, different remedies.
    """

    def setUp(self):
        self.modele_ia = AIModel.objects.create(
            name="Juge de test", model_choice="mock_default", is_active=True,
        )
        self.note_source = Page.objects.create(
            url="http://exemple.local/deux-routes",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-deux-routes", title="Compte rendu",
        )
        self.job = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse", status="completed",
            ai_model=None,
        )

    def _extraction(self, texte):
        return ExtractedEntity.objects.create(
            job=self.job, extraction_class="donnee",
            extraction_text=texte, start_char=0, end_char=10,
        )

    def _article_citant(self, extractions):
        markdown = "\n\n".join(
            f"Affirmation numéro {numero}.[[ext:{extraction.pk}]]"
            for numero, extraction in enumerate(extractions, start=1)
        ) + "\n"
        article = Page.objects.create(
            url="http://exemple.local/deux-routes-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire",
            content_hash="hash-deux-routes-article",
            title="Synthèse", type_de_note=TypeDeNote.SYNTHESE,
        )
        bilan = indexer_les_citations(article, markdown, None)
        article.text_readability = bilan["texte_nettoye"]
        article.save(update_fields=["text_readability"])
        return article

    def test_le_bilan_compte_les_deux_routes_separement(self):
        # Une citation introuvable ET une citation refusee par le juge,
        # dans le meme article. / One of each, in the same article.
        introuvable = self._extraction("un texte qui n'existe pas ailleurs")
        refusee = self._extraction(
            "le seuil de dix mille euros déclenche le passage en assemblée"
        )
        article = self._article_citant([introuvable, refusee])

        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch(
            "core.llm_providers.appeler_llm",
            return_value="1: ne_soutient_pas",
        ):
            bilan = verifier_les_citations_d_un_article(
                article, self.modele_ia,
            )

        self.assertEqual(bilan["citations_introuvables"], 1)
        self.assertEqual(bilan["faibles"], 1)

    def test_les_deux_verdicts_ne_sont_pas_le_meme_etat(self):
        introuvable = self._extraction("un texte qui n'existe pas ailleurs")
        refusee = self._extraction(
            "le seuil de dix mille euros déclenche le passage en assemblée"
        )
        article = self._article_citant([introuvable, refusee])

        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch(
            "core.llm_providers.appeler_llm",
            return_value="1: ne_soutient_pas",
        ):
            verifier_les_citations_d_un_article(article, self.modele_ia)

        etats = {
            lien.extraction_source_id: lien.etat_de_verification
            for lien in SourceLink.objects.filter(
                page_cible=article, type_lien=TypeLien.CITE,
            )
        }
        self.assertEqual(
            etats[introuvable.pk], EtatDeVerification.INTROUVABLE,
        )
        self.assertEqual(etats[refusee.pk], EtatDeVerification.FAIBLE)

    def test_la_provenance_dit_laquelle_des_deux_routes(self):
        # Un verdict sans sa raison est un argument d'autorite : la
        # provenance doit nommer le controle qui a echoue.
        # / A verdict must name the check that failed.
        introuvable = self._extraction("un texte qui n'existe pas ailleurs")
        article = self._article_citant([introuvable])

        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch("core.llm_providers.appeler_llm"):
            verifier_les_citations_d_un_article(article, self.modele_ia)

        lien = SourceLink.objects.get(
            page_cible=article, type_lien=TypeLien.CITE,
        )
        self.assertIn("verbatim", lien.verifie_par.lower())
        self.assertIn("Juge de test", lien.verifie_par)

    def test_une_citation_introuvable_ne_coute_aucun_appel(self):
        introuvable = self._extraction("un texte qui n'existe pas ailleurs")
        article = self._article_citant([introuvable])

        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch("core.llm_providers.appeler_llm") as mock_llm:
            verifier_les_citations_d_un_article(article, self.modele_ia)

        self.assertFalse(mock_llm.called)


class LaSourceEstFaiteDElementsTest(TestCase):
    """
    Le verbatim doit chercher dans les ELEMENTS, pas dans text_readability.
    / The verbatim check must read the elements, not text_readability.

    LOCALISATION : core/tests/test_verification.py

    Le moteur ELEMENT est le SEUL moteur (decision du 10 aout 2026) : la
    verite du texte d'une note, ce sont ses ElementDocument. Or
    `Page.text_readability` est VIDE sur toute note ingeree par Docling.

    Chercher le verbatim dedans echouait donc a coup sur, et le verdict
    accusait la citation d'etre introuvable alors que son passage etait
    parfaitement present dans la source. Mesure du 17 aout 2026 sur le
    carnet etalon : 3 notes sur 4 ont un text_readability vide, et leurs
    81 extractions sont a 100 % dans leurs elements.
    / text_readability is empty on Docling-ingested notes, so the check
    failed systematically and blamed the citation.
    """

    def setUp(self):
        from core.models import ElementDocument

        self.modele_ia = AIModel.objects.create(
            name="Juge elements", model_choice="mock_default", is_active=True,
        )
        # Une note comme Docling la produit : elements remplis,
        # text_readability VIDE. / As Docling leaves it.
        self.note_source = Page.objects.create(
            url="http://exemple.local/note-docling",
            html_original="", html_readability="", text_readability="",
            content_hash="hash-docling", title="Étude ingérée par Docling",
        )
        ElementDocument.objects.create(
            page=self.note_source, ordre=0, label="text",
            texte="Le seuil de dix mille euros déclenche le passage en "
                  "assemblée générale.",
            empreinte_contenu="e0",
        )
        ElementDocument.objects.create(
            page=self.note_source, ordre=1, label="text",
            texte="L'ajournement répété est présenté comme un coût en soi.",
            empreinte_contenu="e1",
        )
        self.job = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse", status="completed",
            ai_model=None,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=self.job, extraction_class="donnee",
            extraction_text=(
                "Le seuil de dix mille euros déclenche le passage en "
                "assemblée générale."
            ),
            start_char=0, end_char=70,
        )

    def _article(self):
        markdown = f"Une affirmation.[[ext:{self.extraction.pk}]]\n"
        article = Page.objects.create(
            url="http://exemple.local/article-docling",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash="hash-art-docling",
            title="Synthèse", type_de_note=TypeDeNote.SYNTHESE,
        )
        bilan = indexer_les_citations(article, markdown, None)
        article.text_readability = bilan["texte_nettoye"]
        article.save(update_fields=["text_readability"])
        return article

    def test_le_verbatim_trouve_le_passage_dans_les_elements(self):
        article = self._article()

        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch(
            "core.llm_providers.appeler_llm", return_value="1: soutient",
        ) as mock_llm:
            bilan = verifier_les_citations_d_un_article(
                article, self.modele_ia,
            )

        lien = SourceLink.objects.get(
            page_cible=article, type_lien=TypeLien.CITE,
        )
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.VERIFIE,
            "le verbatim n'a pas trouvé le passage dans les éléments",
        )
        self.assertEqual(bilan["citations_introuvables"], 0)
        self.assertTrue(mock_llm.called, "le juge n'a même pas été appelé")

    def test_une_note_sans_element_retombe_sur_text_readability(self):
        # Une transcription Voxtral n'a pas d'element mais porte son
        # texte : le repli doit continuer de marcher.
        # / A note without elements still falls back on its flat text.
        from core.models import ElementDocument

        ElementDocument.objects.filter(page=self.note_source).delete()
        self.note_source.text_readability = (
            "Le seuil de dix mille euros déclenche le passage en "
            "assemblée générale."
        )
        self.note_source.save(update_fields=["text_readability"])
        article = self._article()

        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch(
            "core.llm_providers.appeler_llm", return_value="1: soutient",
        ):
            verifier_les_citations_d_un_article(article, self.modele_ia)

        lien = SourceLink.objects.get(
            page_cible=article, type_lien=TypeLien.CITE,
        )
        self.assertEqual(
            lien.etat_de_verification, EtatDeVerification.VERIFIE,
        )
