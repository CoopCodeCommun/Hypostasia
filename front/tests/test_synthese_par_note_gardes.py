"""
La synthese PAR NOTE passe par les memes gardes que les articles carnet.
/ The per-note synthesis goes through the same guards as notebook articles.

LOCALISATION : front/tests/test_synthese_par_note_gardes.py

Il existe TROIS producteurs d'articles vivants : `produire_un_wiki_task`,
`produire_une_synthese_de_carnet_task` et `synthetiser_page_task` (le
bouton de synthese d'une note). Les deux premiers passent par le tronc
commun `_ecrire_le_corps_d_un_article` ; le troisieme dupliquait sa
propre ecriture, et echappait donc a TOUTES ses gardes :

- la normalisation des niveaux de titre — un modele qui rend des `###`
  recreait dans les syntheses par note l'etat que l'applieur ne sait
  pas resoudre (mesure du 16 aout 2026 sur Gemini 2.5 Flash) ;
- le refus des titres en collision, qui rendrait deux sections
  ambigues pour toujours ;
- la garde « zero citation », qui refuse d'enregistrer un article sans
  aucune preuve sur un perimetre non vide.

Une garde qui ne couvre que deux producteurs sur trois n'est pas une
garde.
/ Three live article producers; the third bypassed every guard.
"""

from unittest.mock import patch

from django.test import TestCase

from core.models import Page
from front.tests.test_synthese_phase_c import (
    creer_fixtures_phase_c, creer_le_job_de_synthese,
)


class GardesDeLaSyntheseParNoteTest(TestCase):
    """Les trois gardes du tronc commun s'appliquent aussi ici."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()

    def _lancer(self, reponse_llm):
        job = creer_le_job_de_synthese(self.fixtures)
        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_llm,
        ):
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job.pk)
        job.refresh_from_db()
        return job

    def test_les_sous_titres_sont_normalises(self):
        pk_seuil = self.fixtures["extraction_seuil"].pk
        job = self._lancer(
            "## Le seuil\n"
            "\n"
            "### Un sous-titre que l'applieur ne résout pas\n"
            "\n"
            f"Le seuil déclenche l'assemblée.[[ext:{pk_seuil}]]\n"
            "\n"
            f"CITATIONS_USED: {pk_seuil}\n"
        )

        self.assertEqual(job.status, "completed")
        page_synthese = Page.objects.get(
            pk=job.raw_result["page_synthese_id"],
        )
        self.assertNotIn("###", page_synthese.text_readability)

    def test_deux_titres_en_collision_sont_refuses(self):
        pk_seuil = self.fixtures["extraction_seuil"].pk
        job = self._lancer(
            "## Conclusion\n"
            "\n"
            f"Un paragraphe.[[ext:{pk_seuil}]]\n"
            "\n"
            "### Conclusion\n"
            "\n"
            f"Un autre paragraphe.[[ext:{pk_seuil}]]\n"
            "\n"
            f"CITATIONS_USED: {pk_seuil}\n"
        )

        self.assertEqual(job.status, "error")
        self.assertIn("Conclusion", job.error_message)

    def test_un_article_sans_aucune_citation_est_refuse(self):
        # Constat reel du 9 aout : GPT-4o-mini a redige un wiki entier
        # sans un seul marqueur. Un texte sans preuve n'est pas un
        # succes. / A citation-less article is not a success.
        job = self._lancer(
            "## Le seuil\n"
            "\n"
            "Une affirmation sans la moindre source.\n"
            "\n"
            "CITATIONS_USED: aucune\n"
        )

        self.assertEqual(job.status, "error")
        self.assertIn("citation", job.error_message.lower())


class TexteOriginalDepuisLesElementsTest(TestCase):
    """
    Le bloc « TEXTE ORIGINAL » du prompt vient des ELEMENTS.
    / The prompt's original-text block comes from the elements.

    LOCALISATION : front/tests/test_synthese_par_note_gardes.py

    `_construire_prompt_synthese` lisait `page.text_readability`. Ce
    champ est VIDE sur toute note ingeree par Docling : le drapeau
    `inclure_texte_original` de l'analyseur etait donc vivant et
    n'injectait RIEN — un bloc vide, en silence. Ni « config morte », ni
    fonction qui marche : fonction sans effet, ce qui est pire que les
    deux. Mesure du 17 aout 2026.
    / The flag was live and injected an empty block on Docling notes.
    """

    def setUp(self):
        from core.models import ElementDocument

        self.fixtures = creer_fixtures_phase_c()
        self.note = self.fixtures["note_source"]
        # Comme Docling la laisse : elements remplis, texte plat vide.
        # / As Docling leaves it.
        self.note.text_readability = ""
        self.note.save(update_fields=["text_readability"])
        ElementDocument.objects.create(
            page=self.note, ordre=0, label="text",
            texte="Le premier paragraphe du document ingéré.",
            empreinte_contenu="p0",
        )
        ElementDocument.objects.create(
            page=self.note, ordre=1, label="text",
            texte="Le second paragraphe du document ingéré.",
            empreinte_contenu="p1",
        )

    def _prompt(self):
        from core.services.synthese import dernier_job_d_analyse_de_la_note
        from front.tasks import _construire_prompt_synthese

        analyseur = self.fixtures["analyseur"]
        analyseur.inclure_texte_original = True
        analyseur.save(update_fields=["inclure_texte_original"])
        return _construire_prompt_synthese(
            self.note, dernier_job_d_analyse_de_la_note(self.note), analyseur,
        )

    def test_le_bloc_texte_original_porte_les_elements(self):
        prompt = self._prompt()

        self.assertIn("Le premier paragraphe du document ingéré.", prompt)
        self.assertIn("Le second paragraphe du document ingéré.", prompt)

    def test_le_bloc_n_est_jamais_vide_quand_la_note_a_des_elements(self):
        prompt = self._prompt()

        debut = prompt.index("=== TEXTE ORIGINAL ===")
        bloc = prompt[debut + len("=== TEXTE ORIGINAL ==="):]
        # Ce qui suit l'en-tete, avant le bloc suivant, doit porter du texte.
        # / What follows the header must carry actual text.
        corps = bloc.split("===")[0].strip()
        self.assertTrue(corps, "le bloc TEXTE ORIGINAL est vide")
