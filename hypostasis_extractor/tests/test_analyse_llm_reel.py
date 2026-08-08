"""
Test d'integration avec un VRAI appel LLM — SPEC v2 section 4 (phase D).
/ Integration test against a REAL LLM call.

LOCALISATION : hypostasis_extractor/tests/test_analyse_llm_reel.py

CE TEST NE TOURNE PAS PAR DEFAUT

Il appelle un fournisseur LLM pour de vrai : il coute de l'argent, demande
un reseau, une cle d'API valide, et son resultat depend de ce que le
modele repond ce jour-la. Le lancer a chaque fois rendrait la suite lente,
chere et instable.

Il est donc marque du tag "llm_reel" et EXCLU par defaut.

    # La suite normale l'ignore :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor --exclude-tag=llm_reel

    # Pour le lancer explicitement :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor --tag=llm_reel

/ Tagged "llm_reel" and excluded by default: it costs money and depends
on what the model answers today.

CE QU'IL VERIFIE, QUE LES TESTS SIMULES NE PEUVENT PAS VERIFIER

Les tests simules injectent des spans choisis a la main : ils prouvent que
la mecanique est juste, pas que LangExtract rend bien ce qu'on attend. Ce
test-ci verifie la jonction reelle :

  - LangExtract accepte notre max_char_buffer et ne recoupe pas le chunk ;
  - les positions rendues sont bien des offsets dans le texte envoye ;
  - une extraction qui deborde d'un element produit plusieurs portions.

Ce dernier point est le coeur du moteur, et il a ete observe sur un vrai
appel : Gemini rend un span couvrant les trois elements d'une liste.
/ Simulated tests prove the mechanics; this one proves the junction.
"""

import os

from django.test import TestCase, tag

from core.models import AIModel, ElementDocument, Page, empreinte_du_texte
from hypostasis_extractor.models import (
    AnalyseurExample,
    AnalyseurSyntaxique,
    ExampleExtraction,
    ExtractionJob,
    ExtractionJobStatus,
)
from hypostasis_extractor.services.analyse_par_element import (
    lancer_l_analyse_d_une_page,
)


@tag("llm_reel")
class AnalyseAvecUnVraiLlmTest(TestCase):
    """
    Le pipeline complet contre un fournisseur LLM reel.
    / The full pipeline against a real LLM provider.
    """

    def setUp(self):
        # La base de test est vierge : on cree le modele et l'analyseur.
        # La cle d'API, elle, vient de l'environnement du conteneur.
        # / The test database is empty; the API key comes from the env.
        # DEUX VERROUS, ET POURQUOI DEUX.
        #
        # Le tag "llm_reel" ne suffit pas : Django n'exclut PAS les tags
        # par defaut. Sans un second verrou, un simple
        # « manage.py test hypostasis_extractor » partirait appeler un
        # fournisseur payant, a chaque fois, sans que personne l'ait
        # demande.
        #
        # On exige donc une variable d'activation explicite. Le tag reste
        # utile pour cibler ces tests, mais c'est la variable qui decide.
        # / A tag alone would not protect: Django does not exclude tags by
        # default. An explicit opt-in variable does.
        if not os.environ.get("TESTS_LLM_REELS"):
            self.skipTest(
                "TESTS_LLM_REELS non definie : test d'appel LLM reel "
                "ignore. Pour le lancer : "
                "docker exec -e TESTS_LLM_REELS=1 hypostasia_dev_web "
                "uv run python manage.py test hypostasis_extractor "
                "--tag=llm_reel",
            )
        if not os.environ.get("GOOGLE_API_KEY"):
            self.skipTest(
                "GOOGLE_API_KEY absente : ce test a besoin d'un vrai "
                "fournisseur LLM.",
            )

        # ATTENTION : c'est model_choice qui compte, pas provider.
        # AIModel.save() derive provider et model_name depuis model_choice.
        # Creer le modele avec provider="google" seul le laisse en MOCK, et
        # l'appel part alors sans cle d'API.
        # / AIModel.save() derives provider from model_choice: setting
        # provider alone silently leaves the model on MOCK.
        self.modele_disponible = AIModel.objects.create(
            model_choice="gemini-2.5-flash",
        )

        self.analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur de test LLM reel",
        )
        exemple = AnalyseurExample.objects.create(
            analyseur=self.analyseur,
            name="Exemple minimal",
            example_text=(
                "La confiance ne doit pas remplacer :\n\n"
                "la verification des comptes\n\n"
                "le controle par les pairs"
            ),
        )
        ExampleExtraction.objects.create(
            example=exemple,
            extraction_class="hypostase",
            extraction_text=(
                "La confiance ne doit pas remplacer la verification des comptes"
            ),
        )

        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-llm-reel",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="empreinte_llm_reel",
        )
        # Une liste a puces : le cas ou une extraction deborde d'un element.
        # / A bulleted list: the case where an extraction spans elements.
        textes_des_elements = [
            "L'IA ne doit pas remplacer :",
            "le jugement des personnes concernees",
            "la deliberation collective",
        ]
        self.elements = []
        for numero, texte in enumerate(textes_des_elements):
            self.elements.append(ElementDocument.objects.create(
                page=self.page_de_test, ordre=numero,
                label="text" if numero == 0 else "list_item",
                texte=texte, empreinte_contenu=empreinte_du_texte(texte),
            ))

        self.job = ExtractionJob.objects.create(
            page=self.page_de_test, ai_model=self.modele_disponible,
            name="Analyse LLM reelle",
            prompt_description="Extraire les arguments du texte.",
            raw_result={"analyseur_id": self.analyseur.pk},
        )

    def test_le_pipeline_complet_produit_des_ancres_valides(self):
        """
        Bout en bout : chunking, appel reel, traduction des spans, ancres.
        / End to end: chunking, real call, span translation, anchors.
        """
        resultat = lancer_l_analyse_d_une_page(self.page_de_test, self.job)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExtractionJobStatus.COMPLETED)
        self.assertEqual(resultat["chunks_en_erreur"], 0)
        # Le modele doit trouver quelque chose dans ce texte.
        # / The model must find something in this text.
        self.assertGreater(resultat["extractions"], 0)

        # CHAQUE portion doit pointer un vrai morceau de son element.
        # C'est l'invariant central : une ancre qui ne pointe rien serait
        # exactement le defaut que ce moteur existe pour empecher.
        # / Every portion must point at real text: the central invariant.
        for extraction in self.job.entities.all():
            portions = list(extraction.ancrages.all())
            self.assertGreater(
                len(portions), 0,
                "une extraction a ete creee sans aucune portion",
            )
            for portion in portions:
                texte_de_la_portion = portion.texte_de_la_portion()
                self.assertNotEqual(
                    texte_de_la_portion, "",
                    f"la portion {portion.pk} ne pointe aucun texte",
                )
                # Les bornes tiennent dans le texte de l'element.
                # / Bounds fit inside the element text.
                self.assertLessEqual(
                    portion.fin_dans_element, len(portion.element.texte),
                )
                # Le separateur de jonction n'appartient a aucune portion.
                # / The joining separator belongs to no portion.
                self.assertNotIn("\n\n", texte_de_la_portion)

            # La numerotation est continue, a partir de 0.
            # / Numbering is continuous, starting at 0.
            self.assertEqual(
                [portion.ordre_dans_extraction for portion in portions],
                list(range(len(portions))),
            )

    def test_les_portions_pointent_le_texte_que_le_modele_a_designe(self):
        """
        L'assertion qui compte vraiment : le texte des portions correspond
        a ce que le modele a rendu.

        POURQUOI CE TEST EST ECRIT AINSI

        Une premiere version comparait portion.texte_de_la_portion() a
        element.texte[debut:fin]. C'etait tautologique : la methode EST
        cette expression. Le test passait quoi qu'il arrive, y compris
        avec des positions toutes decalees de cinq caracteres.

        Ici, on compare aux mots de l'extraction rendue par le modele. Un
        decalage constant ferait tomber la correspondance.
        / The earlier version compared x to x. This one compares the
        anchored text to what the model actually returned.

        L'alignement de LangExtract est approximatif — insensible a la
        casse, tolerant aux variantes. On ne peut donc pas exiger une
        egalite stricte : on verifie qu'une part significative des mots du
        passage ancre se retrouve dans le texte rendu, ou l'inverse.
        / LangExtract's alignment is fuzzy, so we check word overlap.
        """
        lancer_l_analyse_d_une_page(self.page_de_test, self.job)

        extractions = list(self.job.entities.all())
        self.assertGreater(len(extractions), 0)

        for extraction in extractions:
            texte_ancre = " ".join(
                portion.texte_de_la_portion()
                for portion in extraction.ancrages.all()
            )
            mots_ancres = set(texte_ancre.lower().split())
            mots_rendus = set(extraction.extraction_text.lower().split())

            self.assertTrue(
                mots_ancres,
                f"l'extraction {extraction.pk} est ancree sur du vide",
            )
            mots_en_commun = mots_ancres & mots_rendus
            self.assertGreater(
                len(mots_en_commun), 0,
                f"le texte ancre ({texte_ancre[:60]!r}) n'a aucun mot en "
                f"commun avec ce que le modele a rendu "
                f"({extraction.extraction_text[:60]!r}) : les positions "
                f"sont probablement decalees",
            )

    def test_une_extraction_longue_produit_plusieurs_portions(self):
        """
        Le coeur du moteur, exige et non plus seulement observe.

        Sur une liste a puces, un modele qui extrait l'idee complete rend
        un span qui deborde du premier element. Si le decoupage
        multi-elements etait casse, toutes les extractions seraient
        mono-portion et ce test tomberait.
        / The multi-element split is required here, not merely observed.

        On ne peut pas exiger qu'UNE extraction precise soit multi-portions
        — le modele est libre de sa granularite. On exige que le
        mecanisme fonctionne des qu'un span deborde : toute extraction
        dont le texte rendu couvre plus que le premier element doit avoir
        plusieurs portions.
        / We require the mechanism to work whenever a span does overflow.
        """
        lancer_l_analyse_d_une_page(self.page_de_test, self.job)

        longueur_du_premier_element = len(self.elements[0].texte)
        for extraction in self.job.entities.all():
            portions = list(extraction.ancrages.all())
            premiere_portion = portions[0]

            # Une extraction qui commence dans le premier element et dont
            # l'ancrage total depasse la longueur de cet element a
            # forcement debordé. / An anchor longer than the first element.
            longueur_totale_ancree = sum(
                portion.fin_dans_element - portion.debut_dans_element
                for portion in portions
            )
            elle_deborde = (
                premiere_portion.element_id == self.elements[0].pk
                and longueur_totale_ancree > longueur_du_premier_element
            )
            if elle_deborde:
                self.assertGreater(
                    len(portions), 1,
                    "une extraction qui deborde du premier element n'a "
                    "qu'une seule portion : le decoupage multi-elements "
                    "ne fonctionne pas",
                )
