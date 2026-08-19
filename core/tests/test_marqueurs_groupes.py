"""
Le repli sur les marqueurs GROUPES : `[[ext:1, ext:2]]`.
/ The fallback for GROUPED citation markers.

LOCALISATION : core/tests/test_marqueurs_groupes.py

CE QUE CE REPLI REPARE, ET COMBIEN CA COUTAIT. Le prompt de redaction
demande des marqueurs CONSECUTIFS (`[[ext:12]][[ext:15]]`) et le dit
avec un exemple. `mistral-small-latest` desobeit : il ecrit
`[[ext:14, ext:15, ext:16]]`.

Le motif de l'indexeur, `\\[\\[ext:(\\d+)\\]\\]`, ne les voyait meme pas.
Consequences, mesurees le 18 aout 2026 sur deux articles reels :

- **107 citations perdues** — 57 dans le wiki, 50 dans la synthese —
  contre 35 reconnues. Le modele en avait produit 142 ;
- le balisage BRUT restait dans le texte affiche : huit
  `[[ext:14, ext:15, …]]` en clair dans le HTML du wiki, illisibles et
  non cliquables ;
- et rien ne le signalait. L'indexeur denonce bruyamment un marqueur
  HALLUCINE, mais il etait AVEUGLE a celui-la : une perte silencieuse.

CE N'EST PAS UNE TOLERANCE DE COMPLAISANCE. Un modele qui desobeit au
format reste un defaut de ce modele — et le bilan le compte, pour qu'on
puisse le lui reprocher. Mais perdre les trois quarts des preuves d'un
article parce qu'une virgule remplace deux crochets n'est pas une
sanction proportionnee.
/ 107 of 142 citations were silently lost because one model groups its
markers. The fallback recovers them and COUNTS them, so the model's
disobedience stays visible.
"""

from django.test import TestCase

from core.models import Page, SourceLink, TypeDeNote, TypeLien
from core.services.synthese import (
    indexer_les_citations, normaliser_les_marqueurs_groupes,
)
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

TEXTE_DE_LA_SOURCE = (
    "Le compte rendu note que le seuil de dix mille euros déclenche le "
    "passage en assemblée. L'ajournement répété est présenté comme un "
    "coût en soi. La question du quorum reste ouverte."
)


class LaNormalisationDesMarqueursTest(TestCase):
    """La fonction pure, sans base. / The pure function, no database."""

    def test_un_groupe_devient_des_marqueurs_consecutifs(self):
        texte, groupes = normaliser_les_marqueurs_groupes(
            "Une affirmation.[[ext:14, ext:15, ext:16]]",
        )

        self.assertEqual(
            texte, "Une affirmation.[[ext:14]][[ext:15]][[ext:16]]",
        )
        self.assertEqual(groupes, 1)

    def test_les_espaces_autour_des_virgules_sont_tolerés(self):
        texte, _ = normaliser_les_marqueurs_groupes(
            "A.[[ext:1,ext:2]] B.[[ext:3 , ext:4]]",
        )

        self.assertEqual(texte, "A.[[ext:1]][[ext:2]] B.[[ext:3]][[ext:4]]")

    def test_un_marqueur_seul_n_est_pas_touche(self):
        # Le format ATTENDU doit traverser la normalisation sans changer
        # d'un octet. / The expected format must pass through untouched.
        original = "Une affirmation.[[ext:14]][[ext:15]] Une autre.[[ext:9]]"

        texte, groupes = normaliser_les_marqueurs_groupes(original)

        self.assertEqual(texte, original)
        self.assertEqual(groupes, 0)

    def test_un_texte_sans_marqueur_traverse_intact(self):
        original = "Un paragraphe ordinaire, avec une virgule, et rien."

        texte, groupes = normaliser_les_marqueurs_groupes(original)

        self.assertEqual(texte, original)
        self.assertEqual(groupes, 0)

    def test_les_groupes_sont_COMPTES_pas_seulement_reparés(self):
        # Le compte est le point : un modele qui desobeit doit rester
        # visible. Reparer en silence excuserait le defaut.
        # / Counting is the point: a disobedient model must stay visible.
        _texte, groupes = normaliser_les_marqueurs_groupes(
            "A.[[ext:1, ext:2]] B.[[ext:3]] C.[[ext:4, ext:5, ext:6]]",
        )

        self.assertEqual(groupes, 2)


class LIndexationRecupereLesGroupesTest(TestCase):
    """De bout en bout : les liens sont bien créés. / End to end."""

    def setUp(self):
        note_source = Page.objects.create(
            url="http://exemple.local/groupes-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-groupes-source", title="Compte rendu",
        )
        job = ExtractionJob.objects.create(
            page=note_source, name="Analyse groupes", status="completed",
            ai_model=None,
        )
        self.extractions = [
            ExtractedEntity.objects.create(
                job=job, extraction_class="donnee",
                extraction_text=texte, start_char=0, end_char=10,
            )
            for texte in (
                "le seuil de dix mille euros déclenche le passage en assemblée",
                "L'ajournement répété est présenté comme un coût",
                "La question du quorum reste ouverte",
            )
        ]
        self.article = Page.objects.create(
            url="http://exemple.local/groupes-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash="hash-groupes-article",
            title="Synthèse groupée", type_de_note=TypeDeNote.SYNTHESE,
        )

    def _liens(self):
        return SourceLink.objects.filter(
            page_cible=self.article, type_lien=TypeLien.CITE,
        )

    def test_un_groupe_de_trois_cree_TROIS_liens(self):
        marqueur = "[[ext:{}, ext:{}, ext:{}]]".format(
            *[e.pk for e in self.extractions],
        )

        bilan = indexer_les_citations(
            self.article, f"Une affirmation groupée.{marqueur}\n", None,
        )

        self.assertEqual(self._liens().count(), 3)
        self.assertEqual(bilan["liens_crees"], 3)
        self.assertEqual(
            set(self._liens().values_list("extraction_source_id", flat=True)),
            {e.pk for e in self.extractions},
        )

    def test_le_bilan_compte_les_groupes_normalises(self):
        marqueur = "[[ext:{}, ext:{}]]".format(
            self.extractions[0].pk, self.extractions[1].pk,
        )

        bilan = indexer_les_citations(
            self.article, f"Une affirmation.{marqueur}\n", None,
        )

        self.assertEqual(bilan["marqueurs_groupes_normalises"], 1)

    def test_le_texte_enregistre_ne_porte_plus_de_groupe(self):
        # LE BALISAGE BRUT NE DOIT PLUS ATTEINDRE L'ECRAN. Avant ce
        # repli, huit `[[ext:14, ext:15, …]]` s'affichaient en clair dans
        # le HTML du wiki. / Raw markup must never reach the screen.
        marqueur = "[[ext:{}, ext:{}]]".format(
            self.extractions[0].pk, self.extractions[1].pk,
        )

        bilan = indexer_les_citations(
            self.article, f"Une affirmation.{marqueur}\n", None,
        )

        self.assertNotIn(", ext:", bilan["texte_nettoye"])
        self.assertIn(f"[[ext:{self.extractions[0].pk}]]",
                      bilan["texte_nettoye"])

    def test_un_groupe_melangeant_connu_et_halluciné_garde_le_connu(self):
        # La regle des marqueurs hallucines ne change pas : l'inconnu est
        # retire et SIGNALE, le connu est indexe.
        # / The hallucination rule is unchanged: unknown ones are
        # stripped and reported, known ones are indexed.
        marqueur = f"[[ext:{self.extractions[0].pk}, ext:999999]]"

        bilan = indexer_les_citations(
            self.article, f"Une affirmation.{marqueur}\n", None,
        )

        self.assertEqual(self._liens().count(), 1)
        self.assertEqual(bilan["marqueurs_retires"], [999999])
