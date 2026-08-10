"""
Tests de la tache de synthese reecrite (SPEC-synthese phase C).
/ Rewritten synthesis task tests (phase C).

LOCALISATION : front/tests/test_synthese_phase_c.py

SPEC-synthese § 2.1 : la synthese N'EST PLUS une version de page — c'est
une note typee du carnet. Le prompt produit des marqueurs [[ext:id]] et
une ligne finale CITATIONS_USED (addendum n°2 : pas de ligne = generation
tronquee = echec bruyant). Les SourceLink sont derives du texte, avec le
perimetre des extractions envoyees au modele — OBLIGATOIRE.
/ § 2.1: the synthesis is a typed notebook note, never a page version;
markers + CITATIONS_USED line; links derived with a mandatory scope.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Configuration, Dossier, Page, SourceLink, SyntheseDirigee, TypeDeNote,
    TypeLien,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from hypostasis_extractor.models import (
    AIModel, AnalyseurSyntaxique, ExtractedEntity, ExtractionJob, PromptPiece,
)

User = get_user_model()


def creer_fixtures_phase_c():
    """
    Fixtures de la tache reecrite : une note source RANGEE dans un carnet
    (appartenance, pas seulement la FK) avec deux extractions analysees.
    / Fixtures: a source note properly FILED in a notebook, two analyzed
    extractions.
    """
    demandeur = User.objects.create_user(
        username="demandeur_synthese", password="test1234",
    )
    carnet = Dossier.objects.create(name="Carnet du conseil", owner=demandeur)

    note_source = Page.objects.create(
        title="Conseil du 12 mars",
        text_readability="Le seuil declenche l'assemblee. L'ajournement coute.",
        html_readability="<p>Le seuil declenche l'assemblee.</p>",
        html_original="<p>Le seuil declenche l'assemblee.</p>",
        content_hash="hash-phase-c-source",
        source_type="web",
        owner=demandeur,
    )
    ranger_une_note_dans_un_carnet(note_source, carnet, demandeur)

    modele_ia = AIModel.objects.create(
        name="Mock synthese C", model_choice="mock_default", is_active=True,
    )
    Configuration.objects.all().delete()
    Configuration.objects.create(ai_active=True, ai_model=modele_ia)

    analyseur = AnalyseurSyntaxique.objects.create(
        name="Synthese phase C",
        is_active=True,
        type_analyseur="synthetiser",
        inclure_extractions=True,
        inclure_texte_original=True,
    )
    PromptPiece.objects.create(
        analyseur=analyseur, name="Contexte", role="context",
        content="Tu es un moteur de synthese deliberative.", order=0,
    )

    job_analyse = ExtractionJob.objects.create(
        page=note_source, ai_model=modele_ia, name="Analyse",
        prompt_description="p", status="completed",
        raw_result={"analyseur_id": analyseur.pk},
    )
    extraction_seuil = ExtractedEntity.objects.create(
        job=job_analyse, extraction_class="donnee",
        extraction_text="Le seuil declenche l'assemblee.",
        start_char=0, end_char=31, statut_debat="commente",
    )
    extraction_cout = ExtractedEntity.objects.create(
        job=job_analyse, extraction_class="hypothese",
        extraction_text="L'ajournement coute.",
        start_char=32, end_char=52, statut_debat="nouveau",
    )

    return {
        "demandeur": demandeur,
        "carnet": carnet,
        "note_source": note_source,
        "modele_ia": modele_ia,
        "analyseur": analyseur,
        "job_analyse": job_analyse,
        "extraction_seuil": extraction_seuil,
        "extraction_cout": extraction_cout,
    }


def creer_le_job_de_synthese(fixtures, **raw_result_en_plus):
    """Cree le job PENDING comme la vue le fait. / The PENDING job."""
    contenu_raw_result = {
        "analyseur_id": fixtures["analyseur"].pk,
        "est_synthese": True,
        "demandeur_id": fixtures["demandeur"].pk,
    }
    contenu_raw_result.update(raw_result_en_plus)
    return ExtractionJob.objects.create(
        page=fixtures["note_source"],
        ai_model=fixtures["modele_ia"],
        name="Synthese deliberative",
        prompt_description="test",
        status="pending",
        raw_result=contenu_raw_result,
    )


def reponse_llm_correcte(fixtures):
    """
    Une reponse conforme au contrat : marqueurs + ligne CITATIONS_USED.
    / A contract-compliant response: markers + CITATIONS_USED line.
    """
    pk_seuil = fixtures["extraction_seuil"].pk
    pk_cout = fixtures["extraction_cout"].pk
    return (
        "# Synthese du conseil\n\n"
        "## Le seuil\n\n"
        f"Le seuil declenche le passage en assemblee.[[ext:{pk_seuil}]]\n\n"
        "## Les couts\n\n"
        f"L'ajournement repete est un cout en soi.[[ext:{pk_cout}]]\n\n"
        f"CITATIONS_USED: {pk_seuil}, {pk_cout}\n"
    )


class TacheSyntheseNoteTypeeTest(TestCase):
    """§ 2.1 : la synthese est une note typee, plus une version."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()

    def _lancer(self, reponse_llm, **raw_result_en_plus):
        job = creer_le_job_de_synthese(self.fixtures, **raw_result_en_plus)
        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_llm,
        ):
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job.pk)
        job.refresh_from_db()
        return job

    def test_la_synthese_est_une_note_typee_sans_version(self):
        job = self._lancer(reponse_llm_correcte(self.fixtures))

        self.assertEqual(job.status, "completed")
        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertEqual(page_synthese.type_de_note, TypeDeNote.SYNTHESE)
        # Plus une version : pas de parent, numero 1.
        # / No longer a version: no parent, number 1.
        self.assertIsNone(page_synthese.parent_page)
        self.assertEqual(page_synthese.version_number, 1)

    def test_la_synthese_reprend_les_carnets_de_la_source(self):
        # Sans carnet d'origine explicite, la synthese vit dans les memes
        # carnets que la note source (repli documente en addendum).
        # / Fallback: the synthesis lives in the source note's notebooks.
        job = self._lancer(reponse_llm_correcte(self.fixtures))

        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertEqual(
            [a.dossier_id for a in page_synthese.appartenances_dossiers.all()],
            [self.fixtures["carnet"].pk],
        )

    def test_le_carnet_d_origine_de_la_demande_est_utilise(self):
        # § 2.1 : « une appartenance au carnet d'origine de la demande ».
        # / § 2.1: one membership, in the requesting notebook.
        autre_carnet = Dossier.objects.create(
            name="Autre carnet", owner=self.fixtures["demandeur"],
        )
        job = self._lancer(
            reponse_llm_correcte(self.fixtures), dossier_id=autre_carnet.pk,
        )

        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertEqual(
            [a.dossier_id for a in page_synthese.appartenances_dossiers.all()],
            [autre_carnet.pk],
        )
        self.assertEqual(
            page_synthese.synthese_dirigee.dossier_id, autre_carnet.pk,
        )

    def test_une_synthese_dirigee_figee_est_creee(self):
        job = self._lancer(reponse_llm_correcte(self.fixtures))

        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        dirigee = SyntheseDirigee.objects.get(page=page_synthese)
        self.assertEqual(dirigee.dossier_id, self.fixtures["carnet"].pk)
        self.assertEqual(dirigee.produite_par, self.fixtures["demandeur"])
        # Le perimetre fige : la note source de la demande.
        # / The frozen scope: the requesting source note.
        self.assertEqual(
            [page.pk for page in dirigee.notes_du_perimetre.all()],
            [self.fixtures["note_source"].pk],
        )


class TacheSyntheseCitationsTest(TestCase):
    """§ 4 : les marqueurs deviennent des SourceLink, dans le perimetre."""

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

    def test_les_marqueurs_produisent_des_sourcelinks(self):
        job = self._lancer(reponse_llm_correcte(self.fixtures))

        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        liens = SourceLink.objects.filter(
            page_cible=page_synthese, type_lien=TypeLien.CITE,
        ).order_by("start_char_cible")
        self.assertEqual(liens.count(), 2)
        self.assertEqual(
            liens[0].extraction_source_id, self.fixtures["extraction_seuil"].pk,
        )
        self.assertEqual(liens[0].section, "Le seuil")
        self.assertEqual(
            liens[1].extraction_source_id, self.fixtures["extraction_cout"].pk,
        )

    def test_un_marqueur_hors_perimetre_est_retire_et_signale(self):
        # Une extraction d'une AUTRE note : la citer est une
        # hallucination — jamais gardee en silence (§ 4.4).
        # / An out-of-scope extraction: stripped and loudly reported.
        autre_note = Page.objects.create(
            title="Autre note", text_readability="t",
            html_readability="<p>t</p>", html_original="<p>t</p>",
            content_hash="hash-autre-note-c",
        )
        autre_job = ExtractionJob.objects.create(
            page=autre_note, name="Autre analyse", status="completed",
            ai_model=self.fixtures["modele_ia"],
        )
        extraction_etrangere = ExtractedEntity.objects.create(
            job=autre_job, extraction_class="donnee",
            extraction_text="hors perimetre", start_char=0, end_char=14,
        )
        pk_seuil = self.fixtures["extraction_seuil"].pk
        reponse = (
            "## Section\n\n"
            f"Affirmation sourcee.[[ext:{pk_seuil}]] "
            f"Affirmation hallucinee.[[ext:{extraction_etrangere.pk}]]\n\n"
            f"CITATIONS_USED: {pk_seuil}, {extraction_etrangere.pk}\n"
        )

        job = self._lancer(reponse)

        self.assertEqual(job.status, "completed")
        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertNotIn(
            f"[[ext:{extraction_etrangere.pk}]]", page_synthese.text_readability,
        )
        self.assertFalse(
            SourceLink.objects.filter(
                page_cible=page_synthese,
                extraction_source=extraction_etrangere,
            ).exists()
        )
        # Le fait est signale, jamais avale. / Reported, never swallowed.
        self.assertEqual(
            job.raw_result.get("marqueurs_retires"),
            [extraction_etrangere.pk],
        )

    def test_sans_ligne_citations_used_echec_bruyant(self):
        # Addendum n°2 : pas de ligne = generation tronquee = echec —
        # jamais une synthese tronquee enregistree comme un succes.
        # / No control line = truncated generation = loud failure.
        pk_seuil = self.fixtures["extraction_seuil"].pk
        reponse_tronquee = (
            "## Section\n\n"
            f"Une affirmation.[[ext:{pk_seuil}]] Et la suite qui s'arrete au mil"
        )

        job = self._lancer(reponse_tronquee)

        self.assertEqual(job.status, "error")
        self.assertIn("tronqu", job.error_message.lower())
        # Aucune page fantome. / No ghost page.
        self.assertIsNone(job.raw_result.get("page_synthese_id"))
        self.assertFalse(
            Page.objects.filter(type_de_note=TypeDeNote.SYNTHESE).exists()
        )

    def test_la_ligne_citations_used_est_retiree_du_texte(self):
        job = self._lancer(reponse_llm_correcte(self.fixtures))

        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertNotIn("CITATIONS_USED", page_synthese.text_readability)
        self.assertNotIn("CITATIONS_USED", page_synthese.html_readability)

    def test_le_html_rend_des_renvois_numerotes(self):
        # § 4.4 : le numero [N] s'affiche, le marqueur se stocke.
        # / § 4.4: [N] is displayed, the marker is stored.
        job = self._lancer(reponse_llm_correcte(self.fixtures))

        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertIn("[[ext:", page_synthese.text_readability)
        self.assertNotIn("[[ext:", page_synthese.html_readability)
        self.assertIn("[1]", page_synthese.html_readability)
        self.assertIn("[2]", page_synthese.html_readability)

    def test_le_html_echappe_toujours_le_script(self):
        # Non-regression XSS de l'ancienne tache. / XSS non-regression.
        pk_seuil = self.fixtures["extraction_seuil"].pk
        reponse = (
            f"Premier.[[ext:{pk_seuil}]]\n\n"
            "Deuxieme <script>alert('xss')</script>.\n\n"
            f"CITATIONS_USED: {pk_seuil}\n"
        )

        job = self._lancer(reponse)

        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertNotIn("<script>", page_synthese.html_readability)
        self.assertIn("&lt;script&gt;", page_synthese.html_readability)


class VueSynthetiserPhaseCTest(TestCase):
    """La vue pose le demandeur et le carnet d'origine dans le job."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.client.login(username="demandeur_synthese", password="test1234")

    @patch("front.tasks.synthetiser_page_task.delay")
    def test_la_vue_pose_le_demandeur_et_le_carnet(self, mock_delay):
        reponse = self.client.post(
            f"/lire/{self.fixtures['note_source'].pk}/synthetiser/",
            {"dossier_id": self.fixtures["carnet"].pk},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        job = ExtractionJob.objects.filter(
            raw_result__est_synthese=True,
        ).latest("created_at")
        self.assertEqual(
            job.raw_result.get("demandeur_id"), self.fixtures["demandeur"].pk,
        )
        self.assertEqual(
            job.raw_result.get("dossier_id"), self.fixtures["carnet"].pk,
        )

    @patch("front.tasks.synthetiser_page_task.delay")
    def test_un_carnet_illisible_n_est_pas_accepte_comme_origine(self, mock_delay):
        # Le carnet d'origine doit etre un carnet ou le demandeur ECRIT :
        # sinon n'importe qui rangerait sa synthese chez autrui.
        # / The origin notebook requires write access.
        autre_utilisateur = User.objects.create_user(
            username="autre_proprio", password="test1234",
        )
        carnet_d_autrui = Dossier.objects.create(
            name="Carnet prive d'autrui", owner=autre_utilisateur,
        )

        reponse = self.client.post(
            f"/lire/{self.fixtures['note_source'].pk}/synthetiser/",
            {"dossier_id": carnet_d_autrui.pk},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 400)
        self.assertFalse(
            ExtractionJob.objects.filter(
                raw_result__est_synthese=True,
            ).exists()
        )


class CorrectifsRelectureCTest(TestCase):
    """
    Correctifs de la relecture adverse du 9 aout (phase C).
    / Fixes from the adversarial review of Aug 9 (phase C).
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()

    def _lancer(self, reponse_llm, **raw_result_en_plus):
        job = creer_le_job_de_synthese(self.fixtures, **raw_result_en_plus)
        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_llm,
        ):
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job.pk)
        job.refresh_from_db()
        return job

    # ----- B1 : la ligne de controle habillee en markdown est acceptee -----

    def test_la_ligne_citations_used_habillee_est_acceptee(self):
        # Le prompt montre la ligne entre backticks : un modele qui
        # recopie ce format ne doit PAS etre rejete comme tronque.
        # / A model copying the backtick format must not be rejected.
        pk_seuil = self.fixtures["extraction_seuil"].pk
        habillages = [
            f"`CITATIONS_USED: {pk_seuil}`",
            f"**CITATIONS_USED:** {pk_seuil}",
            f"```\nCITATIONS_USED: {pk_seuil}\n```",
        ]
        for habillage in habillages:
            with self.subTest(habillage=habillage):
                reponse = (
                    f"Affirmation.[[ext:{pk_seuil}]]\n\n{habillage}\n"
                )
                job = self._lancer(reponse)
                self.assertEqual(job.status, "completed", habillage)
                page_synthese = Page.objects.get(
                    pk=job.raw_result["page_synthese_id"],
                )
                self.assertNotIn(
                    "CITATIONS_USED", page_synthese.text_readability,
                )
                page_synthese.delete()

    # ----- B2 : les liens a schema dangereux sont neutralises -----

    def test_un_lien_javascript_est_neutralise(self):
        # html.escape ne touche pas [texte](url) : markdown reconstruit
        # un <a> APRES l'echappement. Le HTML est rendu |safe — il faut
        # une allowlist de protocoles. / Stored XSS via markdown links.
        pk_seuil = self.fixtures["extraction_seuil"].pk
        reponse = (
            f"Voir [ici](javascript:alert(1)) fin.[[ext:{pk_seuil}]]\n\n"
            "Aussi [la reference][1].\n\n"
            "[1]: javascript:alert(3)\n\n"
            f"Mais [le site](https://exemple.org) reste un lien.\n\n"
            f"CITATIONS_USED: {pk_seuil}\n"
        )

        job = self._lancer(reponse)

        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertNotIn("javascript:", page_synthese.html_readability)
        self.assertIn("https://exemple.org", page_synthese.html_readability)

    # ----- B3 : on ne synthetise JAMAIS une synthese (§ 3.3) -----

    def test_la_vue_refuse_de_synthetiser_une_synthese(self):
        page_de_synthese = Page.objects.create(
            title="Une synthese existante", text_readability="s",
            html_readability="<p>s</p>", html_original="<p>s</p>",
            content_hash="hash-b3-vue", type_de_note=TypeDeNote.SYNTHESE,
            owner=self.fixtures["demandeur"],
        )
        self.client.login(username="demandeur_synthese", password="test1234")

        reponse = self.client.post(
            f"/lire/{page_de_synthese.pk}/synthetiser/",
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 400)
        self.assertFalse(
            ExtractionJob.objects.filter(
                page=page_de_synthese, raw_result__est_synthese=True,
            ).exists()
        )

    def test_la_tache_refuse_de_synthetiser_une_synthese(self):
        # Garde en profondeur : meme un job forge echoue. / Depth guard.
        self.fixtures["note_source"].type_de_note = TypeDeNote.SYNTHESE
        self.fixtures["note_source"].save(update_fields=["type_de_note"])

        job = self._lancer(reponse_llm_correcte(self.fixtures))

        self.assertEqual(job.status, "error")
        self.assertIsNone(job.raw_result.get("page_synthese_id"))

    # ----- I1 : le perimetre fige est la note ANALYSEE -----

    def test_le_perimetre_fige_est_la_note_analysee(self):
        # Si la note source a un parent (versionnage historique), le
        # perimetre doit rester la note dont les extractions ont ete
        # envoyees au modele — pas sa racine (§ 8 en depend).
        # / The frozen scope is the analyzed note, not its root.
        racine_historique = Page.objects.create(
            title="Racine historique", text_readability="r",
            html_readability="<p>r</p>", html_original="<p>r</p>",
            content_hash="hash-i1-racine",
        )
        self.fixtures["note_source"].parent_page = racine_historique
        self.fixtures["note_source"].save(update_fields=["parent_page"])

        job = self._lancer(reponse_llm_correcte(self.fixtures))

        self.assertEqual(job.status, "completed")
        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertEqual(
            [p.pk for p in page_synthese.synthese_dirigee.notes_du_perimetre.all()],
            [self.fixtures["note_source"].pk],
        )

    # ----- I2 : le demandeur et les owners du carnet CIBLE sont notifies -----

    def test_le_demandeur_et_l_owner_du_carnet_cible_sont_notifies(self):
        # Le demandeur n'est ni l'owner de la note ni celui du carnet
        # source ; la vue lui a promis une notification.
        # / The requester was promised a notification.
        demandeur_tiers = User.objects.create_user(
            username="collaborateur_tiers", password="test1234",
        )
        carnet_du_tiers = Dossier.objects.create(
            name="Carnet du tiers", owner=demandeur_tiers,
        )

        with patch("front.tasks.notifier_tache_terminee") as mock_notifier:
            job = self._lancer(
                reponse_llm_correcte(self.fixtures),
                demandeur_id=demandeur_tiers.pk,
                dossier_id=carnet_du_tiers.pk,
            )

        self.assertEqual(job.status, "completed")
        pks_notifies = {
            appel.kwargs["user_pk"] for appel in mock_notifier.call_args_list
        }
        self.assertIn(demandeur_tiers.pk, pks_notifies)

    # ----- I3 : une source hors carnet -> le « A ranger » du demandeur -----

    def test_une_source_hors_carnet_range_la_synthese_dans_a_ranger(self):
        from core.models import RoleSpecialDossier

        note_orpheline = Page.objects.create(
            title="Note orpheline", text_readability="o",
            html_readability="<p>o</p>", html_original="<p>o</p>",
            content_hash="hash-i3-orpheline",
            owner=self.fixtures["demandeur"],
        )
        job_analyse = ExtractionJob.objects.create(
            page=note_orpheline, name="Analyse orpheline",
            status="completed", ai_model=self.fixtures["modele_ia"],
        )
        extraction = ExtractedEntity.objects.create(
            job=job_analyse, extraction_class="donnee",
            extraction_text="fait isole", start_char=0, end_char=10,
        )
        job = ExtractionJob.objects.create(
            page=note_orpheline,
            ai_model=self.fixtures["modele_ia"],
            name="Synthese deliberative", prompt_description="t",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
                "demandeur_id": self.fixtures["demandeur"].pk,
            },
        )
        reponse = (
            f"Un fait.[[ext:{extraction.pk}]]\n\n"
            f"CITATIONS_USED: {extraction.pk}\n"
        )
        with patch("core.llm_providers.appeler_llm", return_value=reponse):
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job.pk)
        job.refresh_from_db()

        self.assertEqual(job.status, "completed")
        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        appartenance = page_synthese.appartenances_dossiers.get()
        self.assertEqual(
            appartenance.dossier.role_special, RoleSpecialDossier.A_RANGER,
        )
        self.assertEqual(
            appartenance.dossier.owner, self.fixtures["demandeur"],
        )

    # ----- I6 : le perimetre est fige AVANT l'appel LLM -----

    def test_le_perimetre_est_fige_avant_l_appel_llm(self):
        # Un participant masque une extraction PENDANT la generation :
        # le marqueur correspondant reste une citation legitime — sinon
        # l'affirmation resterait et sa preuve serait denoncee comme
        # hallucination. / Scope snapshot taken before the LLM call.
        extraction_cout = self.fixtures["extraction_cout"]

        def _masquer_pendant_l_appel(modele, message):
            ExtractedEntity.objects.filter(pk=extraction_cout.pk).update(
                masquee=True,
            )
            return reponse_llm_correcte(self.fixtures)

        job = creer_le_job_de_synthese(self.fixtures)
        with patch(
            "core.llm_providers.appeler_llm",
            side_effect=_masquer_pendant_l_appel,
        ):
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job.pk)
        job.refresh_from_db()

        self.assertEqual(job.status, "completed")
        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertIn(
            f"[[ext:{extraction_cout.pk}]]", page_synthese.text_readability,
        )
        self.assertEqual(job.raw_result.get("marqueurs_retires"), [])


class CorrectifsRelectureETest(TestCase):
    """Correctifs de la relecture des lots D+E. / D+E review fixes."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()

    # ----- B3 : figer le perimetre ne casse pas sur un id disparu -----

    def test_une_extraction_supprimee_pendant_l_appel_ne_detruit_pas_la_synthese(self):
        # Une purge legale pendant la generation (aucun SourceLink
        # n'existe encore) supprime une extraction du perimetre : le
        # figement ne doit pas exploser sur un id disparu et perdre
        # l'appel LLM paye. / A legal purge during generation must not
        # blow up the frozen-scope set().
        extraction_cout = self.fixtures["extraction_cout"]
        pk_seuil = self.fixtures["extraction_seuil"].pk

        def _purger_pendant_l_appel(modele, message):
            ExtractedEntity.objects.filter(pk=extraction_cout.pk).delete()
            return (
                f"Affirmation.[[ext:{pk_seuil}]]\n\n"
                f"CITATIONS_USED: {pk_seuil}\n"
            )

        job = creer_le_job_de_synthese(self.fixtures)
        with patch(
            "core.llm_providers.appeler_llm",
            side_effect=_purger_pendant_l_appel,
        ):
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job.pk)
        job.refresh_from_db()

        self.assertEqual(job.status, "completed")
        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        dirigee = page_synthese.synthese_dirigee
        self.assertTrue(dirigee.perimetre_d_extractions_fige)
        # Seule l'extraction survivante est figee. / Only the survivor.
        self.assertEqual(
            [e.pk for e in dirigee.extractions_du_perimetre.all()],
            [pk_seuil],
        )

    # ----- B2 : « nettoyer les extractions IA » ne fait plus de 500 -----

    def test_nettoyer_ia_sur_une_page_citee_repond_un_refus_propre(self):
        from core.models import SyntheseDirigee

        # Une dirigee cite une extraction IA non commentee de la note.
        # / A frozen synthesis cites an uncommented AI extraction.
        page_de_synthese = Page.objects.create(
            title="Synthese citante", text_readability="s",
            html_readability="<p>s</p>", html_original="<p>s</p>",
            content_hash="hash-b2-citante",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        SyntheseDirigee.objects.create(
            page=page_de_synthese, dossier=self.fixtures["carnet"],
        )
        from core.services.synthese import indexer_les_citations
        indexer_les_citations(
            page_de_synthese,
            f"Affirmation.[[ext:{self.fixtures['extraction_seuil'].pk}]]\n",
            None,
        )

        # Un analyseur « analyser » actif, sinon la vue repond AVANT le
        # bloc de nettoyage et le test serait creux. / An active
        # analyzer, otherwise the view answers before the cleanup block.
        analyseur_d_analyse = AnalyseurSyntaxique.objects.create(
            name="Analyseur test B2", is_active=True,
            type_analyseur="analyser",
        )
        PromptPiece.objects.create(
            analyseur=analyseur_d_analyse, name="Consigne", role="context",
            content="Extrais les hypostases.", order=0,
        )

        self.client.login(username="demandeur_synthese", password="test1234")
        with patch("front.tasks.analyser_page_task.delay"):
            reponse = self.client.post(
                f"/lire/{self.fixtures['note_source'].pk}/analyser/",
                {"nettoyer_ia": "1", "analyseur_id": analyseur_d_analyse.pk},
                HTTP_HX_REQUEST="true",
            )

        # Refus propre, jamais un 500 ; l'extraction citee survit.
        # / Clean refusal, never a 500; the cited extraction survives.
        self.assertLess(reponse.status_code, 500)
        self.assertTrue(
            ExtractedEntity.objects.filter(
                pk=self.fixtures["extraction_seuil"].pk,
            ).exists()
        )
