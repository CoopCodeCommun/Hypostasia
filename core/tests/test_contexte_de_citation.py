"""
Le texte qui ENTOURE une citation, pris dans le document source.
/ The document text SURROUNDING a quote.

LOCALISATION : core/tests/test_contexte_de_citation.py

POURQUOI CE SERVICE EXISTE. Une citation sortie de son paragraphe se
lit mal, et parfois se lit faux : « ce n'est pas suffisant » ne veut
rien dire sans la phrase qui precede. Le panneau de preuve montre donc
un peu du texte d'avant et un peu du texte d'apres, en gris, autour de
la citation exacte.

DEUX MESURES ONT DECIDE DE LA FORME (225 citations reelles, 20 aout 2026) :

1. **Le repli sur l'element voisin est INDISPENSABLE.** L'extraction
   couvre souvent l'element entier : **94 citations sur 225 n'ont AUCUN
   caractere avant elles** dans leur propre element, et **116 sur 225
   aucun apres**. Un contexte pris dans le seul element d'ancrage serait
   donc vide une fois sur deux. Avec le repli sur l'element voisin, il
   ne reste que **2 citations sans avant et 4 sans apres**.

2. **La jonction entre deux elements doit SE VOIR.** Coller le
   paragraphe precedent a la citation ferait lire deux paragraphes
   comme un seul. Le service pose un saut de ligne a la jonction, et le
   gabarit le rend (`white-space: pre-line`).

ET UNE GARDE QUI N'EST PAS UN CAS LIMITE : une ancre DETACHEE porte des
positions perimees. Decouper le texte dessus fabriquerait un contexte
faux, presente comme une preuve — le service rend deux chaines vides.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import ElementDocument, Page, TypeDeNote
from core.services.contexte_de_citation import passage_autour_de_la_citation


def _passage(extraction):
    """Le passage, en couple (avant, apres). / The passage as a pair."""
    rendu = passage_autour_de_la_citation(extraction)
    return rendu["avant"], rendu["apres"]


class BaseDuContexte(TestCase):
    """Une note de trois elements, et une extraction ancree dedans."""

    def setUp(self):
        from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

        self.utilisateur = get_user_model().objects.create_user(
            username="lecteur", password="motdepasse",
        )
        self.note = Page.objects.create(
            title="La note source", owner=self.utilisateur,
            type_de_note=TypeDeNote.NOTE,
        )
        self.avant, self.porteur, self.apres = [
            ElementDocument.objects.create(
                page=self.note, ordre=ordre, label="text", texte=texte,
                empreinte_contenu=f"empreinte-{ordre}",
            )
            for ordre, texte in enumerate([
                "Le paragraphe qui precede, assez long pour etre utile.",
                "Un debut. La citation exacte. Une fin.",
                "Le paragraphe qui suit, lui aussi assez long.",
            ])
        ]
        self.job = ExtractionJob.objects.create(
            page=self.note, name="analyse", prompt_description="p",
            status="completed",
        )
        self.extraction = ExtractedEntity.objects.create(
            job=self.job, extraction_class="hypostase",
            extraction_text="La citation exacte.",
            start_char=0, end_char=0,
        )

    def _ancrer(self, element, debut, fin, ordre=0, etat="ancree"):
        from hypostasis_extractor.models import AncrageExtraction

        return AncrageExtraction.objects.create(
            extraction=self.extraction, element=element,
            ordre_dans_extraction=ordre,
            debut_dans_element=debut, fin_dans_element=fin,
            etat_ancrage=etat,
        )


class LeContexteVientDuMemeElementQuandIlYEnA(BaseDuContexte):
    """Le cas nominal : la citation est au milieu d'un paragraphe."""

    def test_le_texte_d_avant_et_d_apres_sont_rendus(self):
        # « Un debut. La citation exacte. Une fin. »
        #    0        11                 31
        self._ancrer(self.porteur, 11, 30)

        avant, apres = _passage(self.extraction)

        self.assertIn("Un debut.", avant)
        self.assertIn("Une fin.", apres)

    def test_la_citation_elle_meme_n_est_JAMAIS_dans_le_contexte(self):
        """
        Le gabarit affiche contexte + citation + contexte. Si le service
        rendait aussi la citation, elle apparaitrait deux fois.
        / The quote is rendered separately; it must not be duplicated.
        """
        self._ancrer(self.porteur, 11, 30)

        avant, apres = _passage(self.extraction)

        self.assertNotIn("La citation exacte", avant)
        self.assertNotIn("La citation exacte", apres)


class LeRepliSurLElementVoisin(BaseDuContexte):
    """
    94 citations sur 225 n'ont AUCUN caractere avant elles dans leur
    propre element : sans ce repli, le contexte serait vide une fois sur
    deux. / Without this fallback the context is empty half the time.
    """

    def test_une_citation_qui_couvre_tout_son_element_prend_le_voisin(self):
        self._ancrer(self.porteur, 0, len(self.porteur.texte))

        avant, apres = _passage(self.extraction)

        self.assertIn("Le paragraphe qui precede", avant)
        self.assertIn("Le paragraphe qui suit", apres)

    def test_la_jonction_entre_deux_elements_pose_un_SAUT_DE_LIGNE(self):
        """
        Sans lui, le paragraphe precedent et la citation se lisent comme
        un seul paragraphe — le contexte mentirait sur la structure du
        document. / Otherwise two paragraphs read as one.
        """
        self._ancrer(self.porteur, 3, len(self.porteur.texte))

        avant, _ = _passage(self.extraction)

        self.assertIn("\n", avant)

    def test_un_element_MASQUE_n_est_jamais_pris_comme_contexte(self):
        """
        Un element masque est retire du contenu utile (transcription qui
        invente un segment). Le donner pour contexte le remettrait dans
        la preuve par la bande. / A hidden element is not evidence.
        """
        self.avant.masque = True
        self.avant.save(update_fields=["masque"])
        self._ancrer(self.porteur, 0, len(self.porteur.texte))

        avant, _ = _passage(self.extraction)

        self.assertEqual(avant, "")

    def test_sans_voisin_le_contexte_est_VIDE_et_non_invente(self):
        self.avant.delete()
        self.apres.delete()
        self._ancrer(self.porteur, 0, len(self.porteur.texte))

        avant, apres = _passage(self.extraction)

        self.assertEqual(avant, "")
        self.assertEqual(apres, "")


class QuandLeDocumentNEntoureLaCitationDeRien(BaseDuContexte):
    """
    Le gabarit ne doit pas proposer d'ouvrir un depliant VIDE :
    promettre un passage et n'en montrer aucun est pire que le silence.
    / An accordion that reveals nothing is worse than none at all.
    """

    def test_il_y_a_un_passage_est_VRAI_quand_le_document_en_offre_un(self):
        self._ancrer(self.porteur, 11, 30)

        self.assertTrue(
            passage_autour_de_la_citation(self.extraction)["il_y_a_un_passage"]
        )

    def test_il_est_FAUX_quand_la_citation_est_seule_au_monde(self):
        self.avant.delete()
        self.apres.delete()
        self.porteur.texte = "La citation exacte."
        self.porteur.save(update_fields=["texte"])
        self._ancrer(self.porteur, 0, len(self.porteur.texte))

        self.assertFalse(
            passage_autour_de_la_citation(self.extraction)["il_y_a_un_passage"]
        )

    def test_il_est_FAUX_sur_une_ancre_DETACHEE(self):
        """Ses positions sont perimees : rien d'honnete a ouvrir."""
        self._ancrer(self.porteur, 11, 30, etat="detachee")

        self.assertFalse(
            passage_autour_de_la_citation(self.extraction)["il_y_a_un_passage"]
        )


class LesGardesQuiEmpechentUnFauxContexte(BaseDuContexte):

    def test_une_ancre_DETACHEE_ne_rend_aucun_contexte(self):
        """
        LA GARDE QUI COMPTE. Une ancre detachee porte des positions
        PERIMEES : le document a change sous elle. Decouper le texte
        dessus fabriquerait un contexte faux — donne pour une preuve,
        dans un panneau dont c'est tout le propos.
        / A detached anchor carries stale offsets: slicing on them would
        fabricate context and present it as evidence.
        """
        self._ancrer(self.porteur, 11, 30, etat="detachee")

        self.assertEqual(_passage(self.extraction), ("", ""))

    def test_une_extraction_SANS_ancre_ne_rend_aucun_contexte(self):
        self.assertEqual(_passage(self.extraction), ("", ""))

    def test_sans_extraction_du_tout_le_service_ne_leve_pas(self):
        """La citation peut survivre a la suppression de sa source."""
        self.assertEqual(_passage(None), ("", ""))


class LeContexteEstBORNE(BaseDuContexte):
    """
    Le panneau fait 416px. Un element de 3 251 caracteres — le maximum
    mesure le 20 aout — noierait la citation qu'il doit eclairer.
    / The panel is 416px wide; the longest element measured is 3 251
    characters and would drown the quote it exists to light up.
    """

    def setUp(self):
        super().setUp()
        self.porteur.texte = ("mot " * 400) + "La citation exacte." + (" mot" * 400)
        self.porteur.save(update_fields=["texte"])
        debut = self.porteur.texte.index("La citation exacte.")
        self._ancrer(self.porteur, debut, debut + len("La citation exacte."))

    def test_le_contexte_ne_depasse_pas_la_borne(self):
        from core.services.contexte_de_citation import SIGNES_DE_CONTEXTE

        avant, apres = _passage(self.extraction)

        # La borne, plus la marge d'une coupe sur une frontiere de mot.
        # / The bound, plus the slack of a word-boundary cut.
        self.assertLessEqual(len(avant), SIGNES_DE_CONTEXTE + 20)
        self.assertLessEqual(len(apres), SIGNES_DE_CONTEXTE + 20)

    def test_une_coupe_est_SIGNALEE_par_des_points_de_suspension(self):
        """
        Sans marque, le lecteur croit lire le debut du paragraphe.
        / Unmarked, the reader believes they see the paragraph's start.
        """
        avant, apres = _passage(self.extraction)

        self.assertTrue(avant.startswith("…"), avant[:30])
        self.assertTrue(apres.endswith("…"), apres[-30:])

    def test_une_coupe_ne_tombe_pas_AU_MILIEU_d_un_mot(self):
        self.porteur.texte = (
            "commencement " + ("anticonstitutionnellement " * 40)
            + "La citation exacte. " + ("anticonstitutionnellement " * 40)
        )
        self.porteur.save(update_fields=["texte"])
        debut = self.porteur.texte.index("La citation exacte.")
        self.extraction.ancrages.all().delete()
        self._ancrer(self.porteur, debut, debut + len("La citation exacte."))

        avant, apres = _passage(self.extraction)

        # Ce qui suit le « … » d'ouverture est un mot entier, et ce qui
        # precede le « … » de fermeture aussi.
        # / What follows the opening ellipsis is a whole word.
        self.assertTrue(avant.lstrip("… ").startswith("anticonstitutionnellement"))
        self.assertTrue(apres.rstrip("… ").endswith("anticonstitutionnellement"))
