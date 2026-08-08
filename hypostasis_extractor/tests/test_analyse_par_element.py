"""
Tests du pipeline d'analyse par element — SPEC v2 section 4 (phase D).
/ Tests for the element-based analysis pipeline — SPEC v2 section 4.

LOCALISATION : hypostasis_extractor/tests/test_analyse_par_element.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor.tests.test_analyse_par_element

La mecanique est testee avec un LLM SIMULE : on injecte une fonction qui
rend des spans choisis, ce qui permet de verifier exactement ou les
portions atterrissent. Un test d'integration contre un vrai LLM existe
separement (test_analyse_llm_reel.py), il n'est pas lance par defaut.
/ The mechanics are tested with a simulated LLM so spans are exact.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import ElementDocument, EtatElement, Page, empreinte_du_texte
from hypostasis_extractor.models import (
    AncrageExtraction,
    EtatAncrage,
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)
from hypostasis_extractor.services.analyse_par_element import (
    _traduire_les_extractions_de_langextract,
    analyser_une_page_par_element,
    lancer_l_analyse_d_une_page,
)


class BaseAnalyseTestCase(TestCase):
    """Socle commun : une page, des elements, un job.
    / Common ground: a page, elements, a job."""

    def setUp(self):
        self.utilisateur_de_test = get_user_model().objects.create_user(
            username="testeur_analyse", password="motdepasse_de_test_123",
        )
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-analyse",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="empreinte_page_analyse",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page_de_test, name="Job d'analyse",
            prompt_description="Extraire les principes",
            status=ExtractionJobStatus.COMPLETED,
        )
        self.prochain_ordre = 0

    def _ajouter_un_element(self, texte, label="text", masque=False):
        element = ElementDocument.objects.create(
            page=self.page_de_test, ordre=self.prochain_ordre, label=label,
            texte=texte, empreinte_contenu=empreinte_du_texte(texte),
            masque=masque,
        )
        self.prochain_ordre += 1
        return element

    def _llm_qui_rend(self, extractions_par_chunk):
        """
        Fabrique un faux LLM qui rend des extractions choisies.
        / Builds a fake LLM returning chosen extractions.

        :param extractions_par_chunk: liste de listes, une par chunk
        """
        appels = {"numero": 0, "textes_recus": []}

        def faux_llm(texte_du_chunk, job):
            appels["textes_recus"].append(texte_du_chunk)
            numero = appels["numero"]
            appels["numero"] += 1
            if numero < len(extractions_par_chunk):
                return extractions_par_chunk[numero]
            return []

        faux_llm.appels = appels
        return faux_llm


class AnalyseSimpleTest(BaseAnalyseTestCase):
    """Le cas nominal. / The nominal case."""

    def test_une_extraction_dans_un_seul_element(self):
        """Le cas le plus simple : un span dans un element."""
        element = self._ajouter_un_element("Le jugement des personnes compte.")
        faux_llm = self._llm_qui_rend([[{
            "extraction_class": "principe",
            "extraction_text": "jugement",
            "debut": 3, "fin": 11,
            "attributes": {"importance": "haute"},
        }]])

        resultat = analyser_une_page_par_element(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        self.assertEqual(resultat["extractions"], 1)
        self.assertEqual(resultat["portions"], 1)
        extraction = ExtractedEntity.objects.get(job=self.job)
        self.assertEqual(extraction.extraction_class, "principe")
        self.assertEqual(extraction.attributes, {"importance": "haute"})
        portion = extraction.ancrages.get()
        self.assertEqual(portion.element, element)
        self.assertEqual(portion.texte_de_la_portion(), "jugement")

    def test_une_extraction_qui_traverse_trois_elements(self):
        """
        Le cas qui justifie tout le moteur : le span couvre une liste a
        puces entiere, on obtient trois portions ordonnees.
        / The span covers a whole bulleted list: three ordered portions.
        """
        premier = self._ajouter_un_element("L'IA ne doit pas remplacer :")
        deuxieme = self._ajouter_un_element("le jugement des personnes")
        troisieme = self._ajouter_un_element("la deliberation collective")
        # Le chunk fait 28 + 2 + 25 + 2 + 26 = 83 caracteres.
        faux_llm = self._llm_qui_rend([[{
            "extraction_class": "principe",
            "extraction_text": "toute la liste",
            "debut": 0, "fin": 83,
            "attributes": {},
        }]])

        resultat = analyser_une_page_par_element(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        self.assertEqual(resultat["extractions"], 1)
        self.assertEqual(resultat["portions"], 3)
        portions = list(ExtractedEntity.objects.get(job=self.job).ancrages.all())
        self.assertEqual(
            [portion.element for portion in portions],
            [premier, deuxieme, troisieme],
        )
        self.assertEqual(
            [portion.ordre_dans_extraction for portion in portions], [0, 1, 2],
        )

    def test_l_etat_des_elements_est_recalcule(self):
        """Le signal de la phase A s'applique aussi aux ancres du pipeline."""
        element = self._ajouter_un_element("Le jugement des personnes compte.")
        faux_llm = self._llm_qui_rend([[{
            "extraction_class": "principe", "extraction_text": "jugement",
            "debut": 3, "fin": 11, "attributes": {},
        }]])

        analyser_une_page_par_element(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        element.refresh_from_db()
        self.assertEqual(element.etat, EtatElement.ANALYSE)

    def test_les_elements_masques_ne_partent_pas_au_llm(self):
        """Integration avec le chunking : le masque est absent du texte envoye."""
        self._ajouter_un_element("Un vrai passage.")
        self._ajouter_un_element("Du bruit invente.", masque=True)
        faux_llm = self._llm_qui_rend([[]])

        analyser_une_page_par_element(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        texte_envoye = faux_llm.appels["textes_recus"][0]
        self.assertIn("Un vrai passage.", texte_envoye)
        self.assertNotIn("Du bruit invente.", texte_envoye)

    def test_une_page_vide_ne_fait_aucun_appel(self):
        """Rien a analyser : aucun appel LLM, donc aucun cout."""
        faux_llm = self._llm_qui_rend([[]])

        resultat = analyser_une_page_par_element(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        self.assertEqual(resultat["chunks"], 0)
        self.assertEqual(faux_llm.appels["numero"], 0)


class ExtractionsIgnoreesTest(BaseAnalyseTestCase):
    """
    Ce qu'on refuse d'ancrer plutot que d'ancrer faux.
    / What we refuse to anchor rather than anchoring wrong.
    """

    def test_une_extraction_sans_position_est_ignoree(self):
        """
        LangExtract n'a pas pu aligner le texte. Le moteur ANCIEN persiste
        ces cas en start=0, end=0 : une ancre qui pointe le debut du
        document, donc fausse, et que rien ne signale. Ici, on n'ecrit rien.
        / The old engine anchors these at 0-0, silently wrong.
        """
        self._ajouter_un_element("Un passage quelconque.")
        faux_llm = self._llm_qui_rend([[{
            "extraction_class": "principe",
            "extraction_text": "un texte que le LLM a invente",
            "debut": None, "fin": None, "attributes": {},
        }]])

        resultat = analyser_une_page_par_element(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        self.assertEqual(resultat["extractions"], 0)
        self.assertEqual(ExtractedEntity.objects.count(), 0)
        self.assertEqual(AncrageExtraction.objects.count(), 0)

    def test_une_extraction_dans_un_separateur_est_ignoree(self):
        """
        Le span ne recoupe aucun element : il tombe entierement dans la
        jonction entre deux elements.
        / The span falls entirely inside a joining separator.
        """
        self._ajouter_un_element("Premier.")
        self._ajouter_un_element("Second.")
        # Le separateur occupe les positions 8 et 9.
        faux_llm = self._llm_qui_rend([[{
            "extraction_class": "principe", "extraction_text": "\n\n",
            "debut": 8, "fin": 10, "attributes": {},
        }]])

        resultat = analyser_une_page_par_element(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        self.assertEqual(resultat["extractions"], 0)
        self.assertEqual(ExtractedEntity.objects.count(), 0)


class ResistanceAuxPannesTest(BaseAnalyseTestCase):
    """
    Un chunk qui echoue ne fait pas perdre les autres.
    / A failed chunk does not lose the others.
    """

    def test_un_chunk_en_erreur_n_arrete_pas_l_analyse(self):
        """
        Perdre quinze chunks deja payes parce que le seizieme a echoue
        serait absurde. / Losing fifteen paid chunks over the sixteenth.
        """
        # 1000 caracteres chacun : deux ne tiennent pas dans un chunk de
        # 1500, donc chaque element forme son propre chunk.
        # / 1000 chars each, so each element forms its own chunk.
        for numero in range(4):
            self._ajouter_un_element(f"Paragraphe {numero}. " + "x" * 980)

        appels = {"numero": 0}

        def llm_qui_echoue_au_deuxieme(texte_du_chunk, job):
            numero = appels["numero"]
            appels["numero"] += 1
            if numero == 1:
                raise RuntimeError("Panne simulee du fournisseur LLM.")
            return [{
                "extraction_class": "principe", "extraction_text": "Paragraphe",
                "debut": 0, "fin": 10, "attributes": {},
            }]

        resultat = analyser_une_page_par_element(
            self.page_de_test, self.job,
            appeler_le_llm=llm_qui_echoue_au_deuxieme,
        )

        self.assertEqual(resultat["chunks"], 4)
        self.assertEqual(resultat["chunks_en_erreur"], 1)
        # Les trois autres chunks ont bien produit leurs extractions.
        # / The other three chunks did produce their extractions.
        self.assertEqual(resultat["extractions"], 3)


class ProtectionsDuPipelineTest(BaseAnalyseTestCase):
    """
    Les garde-fous : purge, echec total, extraction refusee.
    / The safeguards: purge, total failure, refused extraction.
    """

    def test_relancer_un_job_ne_duplique_pas_les_extractions(self):
        """
        Un retry Celery ou une relance manuelle ne doit pas empiler deux
        series d'extractions. Les cartes apparaitraient en double, et
        entities_count, ecrit avec le compte de la derniere passe
        seulement, deviendrait faux.
        / A retry must not stack two sets of extractions.
        """
        self._ajouter_un_element("Le jugement des personnes compte.")
        extraction_attendue = [{
            "extraction_class": "principe", "extraction_text": "jugement",
            "debut": 3, "fin": 11, "attributes": {},
        }]

        analyser_une_page_par_element(
            self.page_de_test, self.job,
            appeler_le_llm=self._llm_qui_rend([extraction_attendue]),
        )
        self.assertEqual(ExtractedEntity.objects.count(), 1)

        # Deuxieme passe du MEME job.
        # / Second pass of the SAME job.
        analyser_une_page_par_element(
            self.page_de_test, self.job,
            appeler_le_llm=self._llm_qui_rend([extraction_attendue]),
        )

        self.assertEqual(ExtractedEntity.objects.count(), 1)
        self.assertEqual(AncrageExtraction.objects.count(), 1)

    def test_un_echec_total_met_le_job_en_erreur(self):
        """
        Si TOUS les chunks echouent, la page n'a rien produit. Marquer le
        job « termine » afficherait « analyse terminee, 0 extraction »,
        indiscernable d'une page sans rien a extraire.
        / A total failure must not look like an empty page.
        """
        self._ajouter_un_element("Un passage a analyser.")

        def llm_toujours_en_panne(texte_du_chunk, job):
            raise RuntimeError("Cle d'API expiree.")

        resultat = lancer_l_analyse_d_une_page(
            self.page_de_test, self.job, appeler_le_llm=llm_toujours_en_panne,
        )

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExtractionJobStatus.ERROR)
        self.assertEqual(resultat["chunks_en_erreur"], resultat["chunks"])
        self.assertIn("ont echoue", self.job.error_message)

    def test_un_echec_partiel_reste_un_succes_mais_laisse_une_trace(self):
        """
        La moitie des chunks perdus, ce n'est pas un echec — le travail
        fait est reel — mais ca ne doit pas disparaitre dans les logs.
        / Half the chunks lost is not a failure, but must leave a trace.
        """
        for numero in range(2):
            self._ajouter_un_element(f"Paragraphe {numero}. " + "x" * 980)

        appels = {"numero": 0}

        def llm_qui_echoue_une_fois_sur_deux(texte_du_chunk, job):
            numero = appels["numero"]
            appels["numero"] += 1
            if numero % 2 == 0:
                raise RuntimeError("Panne passagere.")
            return [{
                "extraction_class": "principe", "extraction_text": "Paragraphe",
                "debut": 0, "fin": 10, "attributes": {},
            }]

        lancer_l_analyse_d_une_page(
            self.page_de_test, self.job,
            appeler_le_llm=llm_qui_echoue_une_fois_sur_deux,
        )

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExtractionJobStatus.COMPLETED)
        bilan = self.job.raw_result["bilan_de_l_analyse"]
        self.assertEqual(bilan["chunks_en_erreur"], 1)
        self.assertEqual(self.job.raw_result["moteur"], "element")

    def test_une_extraction_incoherente_ne_tue_pas_l_analyse(self):
        """
        Les gardes de services/ancrage.py levent sur un span a l'envers.
        C'est voulu — mieux vaut refuser que d'ancrer faux — mais une
        seule extraction douteuse ne doit pas emporter tout le reste.
        / One bad extraction must not discard the whole run.
        """
        self._ajouter_un_element("Le jugement des personnes compte.")
        faux_llm = self._llm_qui_rend([[
            # Span a l'envers : la garde de ancrage.py va lever.
            # / Inverted span: the ancrage.py guard will raise.
            {"extraction_class": "principe", "extraction_text": "casse",
             "debut": 11, "fin": 3, "attributes": {}},
            # Celle-ci est valide et doit passer malgre la precedente.
            # / This one is valid and must still go through.
            {"extraction_class": "principe", "extraction_text": "jugement",
             "debut": 3, "fin": 11, "attributes": {}},
        ]])

        resultat = analyser_une_page_par_element(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        self.assertEqual(resultat["extractions_refusees"], 1)
        self.assertEqual(resultat["extractions"], 1)
        extraction_creee = ExtractedEntity.objects.get()
        self.assertEqual(extraction_creee.extraction_text, "jugement")


class SuiviDuJobTest(BaseAnalyseTestCase):
    """
    Le job passe par ses etats, pour que la garde d'edition le voie.
    / The job goes through its states so the edit guard sees it.
    """

    def test_le_job_finit_termine(self):
        self._ajouter_un_element("Le jugement des personnes compte.")
        faux_llm = self._llm_qui_rend([[{
            "extraction_class": "principe", "extraction_text": "jugement",
            "debut": 3, "fin": 11, "attributes": {},
        }]])

        lancer_l_analyse_d_une_page(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExtractionJobStatus.COMPLETED)
        self.assertEqual(self.job.entities_count, 1)

    def test_le_job_passe_en_erreur_si_l_analyse_casse(self):
        self._ajouter_un_element("Un passage.")

        def llm_qui_casse_tout(texte_du_chunk, job):
            raise RuntimeError("Panne")

        # analyser_une_page_par_element absorbe les pannes par chunk : on
        # casse donc plus haut, au chunking, pour tester le chemin d'erreur.
        # / Chunk failures are absorbed, so we break higher up.
        def analyse_qui_casse(page, job, appeler_le_llm=None):
            raise ValueError("Panne au niveau de l'analyse.")

        import hypostasis_extractor.services.analyse_par_element as module
        analyse_d_origine = module.analyser_une_page_par_element
        module.analyser_une_page_par_element = analyse_qui_casse
        try:
            with self.assertRaises(ValueError):
                lancer_l_analyse_d_une_page(
                    self.page_de_test, self.job, appeler_le_llm=llm_qui_casse_tout,
                )
        finally:
            module.analyser_une_page_par_element = analyse_d_origine

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExtractionJobStatus.ERROR)
        self.assertIn("Panne au niveau de l'analyse.", self.job.error_message)

    def test_le_battement_de_coeur_est_ecrit(self):
        """
        La garde d'edition se sert de updated_at pour savoir si le job est
        vivant. Django n'applique auto_now qu'aux champs listes dans
        update_fields : s'ils oubliaient "updated_at", la date resterait
        figee a la creation.
        / auto_now only applies to fields listed in update_fields.
        """
        self._ajouter_un_element("Un passage.")
        ExtractionJob.objects.filter(pk=self.job.pk).update(
            updated_at="2020-01-01T00:00:00Z",
        )
        faux_llm = self._llm_qui_rend([[]])

        lancer_l_analyse_d_une_page(
            self.page_de_test, self.job, appeler_le_llm=faux_llm,
        )

        self.job.refresh_from_db()
        self.assertGreater(self.job.updated_at.year, 2020)


class TraductionDeLangExtractTest(TestCase):
    """
    La frontiere avec LangExtract.
    / The LangExtract boundary.

    LOCALISATION : hypostasis_extractor/tests/test_analyse_par_element.py

    On ne fait pas circuler les objets de LangExtract dans le reste du
    code : une montee de version ne doit pas obliger a reecrire l'ancrage.
    """

    class FauxIntervalle:
        def __init__(self, start_pos, end_pos):
            self.start_pos = start_pos
            self.end_pos = end_pos

    class FausseExtraction:
        def __init__(self, texte, intervalle, classe="principe", attributs=None):
            self.extraction_text = texte
            self.char_interval = intervalle
            self.extraction_class = classe
            self.attributes = attributs

    class FauxResultat:
        def __init__(self, extractions):
            self.extractions = extractions

    def test_une_extraction_alignee_est_traduite(self):
        resultat = self.FauxResultat([
            self.FausseExtraction(
                "jugement", self.FauxIntervalle(3, 11), attributs={"a": 1},
            ),
        ])

        traduites = _traduire_les_extractions_de_langextract(resultat)

        self.assertEqual(len(traduites), 1)
        self.assertEqual(traduites[0]["extraction_text"], "jugement")
        self.assertEqual(traduites[0]["debut"], 3)
        self.assertEqual(traduites[0]["fin"], 11)
        self.assertEqual(traduites[0]["attributes"], {"a": 1})

    def test_une_extraction_non_alignee_rend_debut_none(self):
        """
        char_interval absent : LangExtract n'a pas retrouve le texte.
        L'appelant l'ignorera plutot que de l'ancrer au debut du document.
        / No char_interval: the caller will skip it.
        """
        resultat = self.FauxResultat([
            self.FausseExtraction("texte invente", None),
        ])

        traduites = _traduire_les_extractions_de_langextract(resultat)

        self.assertIsNone(traduites[0]["debut"])

    def test_un_resultat_vide_ne_casse_pas(self):
        self.assertEqual(
            _traduire_les_extractions_de_langextract(self.FauxResultat([])), [],
        )
        self.assertEqual(
            _traduire_les_extractions_de_langextract(self.FauxResultat(None)), [],
        )

    def test_les_attributs_absents_deviennent_un_dictionnaire_vide(self):
        """attributes=None casserait le JSONField du modele."""
        resultat = self.FauxResultat([
            self.FausseExtraction("jugement", self.FauxIntervalle(0, 8)),
        ])

        traduites = _traduire_les_extractions_de_langextract(resultat)

        self.assertEqual(traduites[0]["attributes"], {})
