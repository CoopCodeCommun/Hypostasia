"""
Tests du gel de l'etalon du juge.
/ Judge benchmark freezing tests.

LOCALISATION : front/tests/test_gel_de_l_etalon_du_juge.py

Les verdicts vivent dans une colonne qu'on reecrit. Le fichier gele est
donc la SEULE trace stable de ce qu'un juge a repondu, et de la question
exacte qu'on lui a posee.

CE QUE CES TESTS VERROUILLENT :
- la commande n'ecrit RIEN en base et n'appelle AUCUN modele ;
- la reponse de reference est deduite de l'etat : « verifie » et
  « sourcee par le debat » disent tous deux « soutient », « faible » dit
  « ne_soutient_pas » ;
- une paire dont la question a DERIVE depuis son verdict (bornes
  perimees, verbatim devenu introuvable) est EXCLUE et comptee a part —
  la geler produirait une comparaison fausse ;
- l'affirmation gelee est nettoyee de ses marqueurs, comme celle qui
  part au juge.
/ The command writes nothing, derives the reference answer from the
state, and excludes pairs whose question has drifted.
"""

import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from core.models import (
    EtatDeVerification, Page, SourceLink, TypeDeNote, TypeLien,
)
from core.services.synthese import indexer_les_citations
from hypostasis_extractor.models import (
    AIModel, ExtractedEntity, ExtractionJob,
)

Utilisateur = get_user_model()

TEXTE_DE_LA_NOTE = (
    "Le compte rendu note que le seuil de dix mille euros déclenche le "
    "passage en assemblée. L'ajournement répété est présenté comme un "
    "coût en soi."
)


class GelDeLEtalonTest(TestCase):
    """Le gel produit la question et la reponse. / Question and answer."""

    def setUp(self):
        self.modele_ia = AIModel.objects.create(
            name="Juge de référence", model_choice="mock_default",
            is_active=True,
        )
        self.note_source = Page.objects.create(
            url="http://exemple.local/gel-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_NOTE,
            content_hash="hash-gel-source", title="Compte rendu",
        )
        self.job = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse", status="completed",
            ai_model=None,
        )
        self.extraction_seuil = ExtractedEntity.objects.create(
            job=self.job, extraction_class="donnee",
            extraction_text=(
                "le seuil de dix mille euros déclenche le passage en assemblée"
            ),
            start_char=0, end_char=60,
        )
        self.extraction_cout = ExtractedEntity.objects.create(
            job=self.job, extraction_class="argument",
            extraction_text="L'ajournement répété est présenté comme un coût",
            start_char=61, end_char=108,
        )
        self.article = self._creer_l_article(
            [self.extraction_seuil, self.extraction_cout],
        )

    def _creer_l_article(self, extractions):
        markdown = "\n\n".join(
            f"Affirmation numéro {numero}.[[ext:{extraction.pk}]]"
            for numero, extraction in enumerate(extractions, start=1)
        ) + "\n"
        article = Page.objects.create(
            url="http://exemple.local/gel-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash="hash-gel-article",
            title="Synthèse à geler", type_de_note=TypeDeNote.SYNTHESE,
        )
        bilan = indexer_les_citations(article, markdown, None)
        article.text_readability = bilan["texte_nettoye"]
        article.save(update_fields=["text_readability"])
        return article

    def _poser_les_verdicts(self, etats):
        """Pose un verdict par lien, dans l'ordre de l'article."""
        liens = list(
            SourceLink.objects.filter(
                page_cible=self.article, type_lien=TypeLien.CITE,
            ).order_by("start_char_cible", "pk")
        )
        for lien, etat in zip(liens, etats):
            lien.etat_de_verification = etat
            lien.verifie_par = "verbatim+nli-lot v2 — Juge de référence"
            lien.save(update_fields=["etat_de_verification", "verifie_par"])
        return liens

    def _geler(self):
        """Lance la commande dans un dossier temporaire et rend le JSON."""
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "etalon.json"
            call_command("geler_l_etalon_du_juge", sortie=str(chemin))
            return json.loads(chemin.read_text(encoding="utf-8"))

    def test_les_deux_verdicts_sont_geles_avec_leur_reponse(self):
        """« vérifié » dit « soutient », « faible » dit « ne_soutient_pas »."""
        self._poser_les_verdicts([
            EtatDeVerification.VERIFIE, EtatDeVerification.FAIBLE,
        ])

        etalon = self._geler()

        self.assertEqual(etalon["nombre_de_paires"], 2)
        reponses = {
            paire["verdict_de_reference"]: paire["reponse_de_reference"]
            for paire in etalon["paires"]
        }
        self.assertEqual(reponses[EtatDeVerification.VERIFIE], "soutient")
        self.assertEqual(
            reponses[EtatDeVerification.FAIBLE], "ne_soutient_pas",
        )

    def test_la_question_gelee_porte_l_affirmation_et_la_source(self):
        """La paire gelée contient les deux textes que le juge a lus."""
        self._poser_les_verdicts([
            EtatDeVerification.VERIFIE, EtatDeVerification.VERIFIE,
        ])

        etalon = self._geler()

        premiere_paire = etalon["paires"][0]
        self.assertIn("Affirmation numéro", premiere_paire["affirmation"])
        # Le marqueur est du bruit pour le juge : il ne doit pas etre gele.
        # / The marker is noise for the judge; it must not be frozen.
        self.assertNotIn("[[ext:", premiere_paire["affirmation"])
        self.assertEqual(
            premiere_paire["texte_source"],
            self.extraction_seuil.extraction_text,
        )

    def test_le_gel_n_ecrit_rien_en_base(self):
        """Aucun verdict n'est modifié par le gel."""
        liens = self._poser_les_verdicts([
            EtatDeVerification.VERIFIE, EtatDeVerification.FAIBLE,
        ])
        etats_avant = [
            (lien.pk, lien.etat_de_verification, lien.verifie_par)
            for lien in liens
        ]

        self._geler()

        etats_apres = [
            (lien.pk, lien.etat_de_verification, lien.verifie_par)
            for lien in SourceLink.objects.filter(
                pk__in=[lien.pk for lien in liens],
            ).order_by("start_char_cible", "pk")
        ]
        self.assertEqual(etats_avant, etats_apres)

    def test_une_paire_dont_la_question_a_derive_est_exclue(self):
        """
        Un verdict rendu sur un verbatim qui n'existe plus ne se gèle
        pas : la question a changé depuis, et la comparer serait
        comparer deux questions différentes.
        """
        self._poser_les_verdicts([
            EtatDeVerification.VERIFIE, EtatDeVerification.VERIFIE,
        ])
        # La source ne contient plus le passage de la premiere citation.
        # / The first quote no longer exists in its source.
        ExtractedEntity.objects.filter(pk=self.extraction_seuil.pk).update(
            extraction_text="un passage qui n'existe nulle part",
        )

        etalon = self._geler()

        self.assertEqual(etalon["nombre_de_paires"], 1)
        self.assertEqual(len(etalon["derives"]), 1)
        self.assertEqual(
            etalon["derives"][0]["raison"], "verbatim_introuvable",
        )

    def test_une_paire_jamais_jugee_n_est_pas_gelee(self):
        """Sans verdict, il n'y a rien à comparer."""
        self._poser_les_verdicts([
            EtatDeVerification.VERIFIE, EtatDeVerification.NON_VERIFIE,
        ])

        etalon = self._geler()

        self.assertEqual(etalon["nombre_de_paires"], 1)

    def test_sans_aucun_verdict_la_commande_refuse(self):
        """Geler un étalon vide serait geler une mesure inexistante."""
        SourceLink.objects.filter(type_lien=TypeLien.CITE).update(
            etat_de_verification=EtatDeVerification.NON_VERIFIE,
        )

        with self.assertRaises(CommandError):
            self._geler()
