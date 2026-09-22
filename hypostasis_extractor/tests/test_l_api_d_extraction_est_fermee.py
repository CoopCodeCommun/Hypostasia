"""
Tests de fermeture de l'API d'extraction — les trois ViewSets JSON de
`hypostasis_extractor/views.py` ne servent plus rien a un inconnu.
/ Closing tests for the extraction API: the three JSON ViewSets serve
nothing to a stranger anymore.

LOCALISATION : hypostasis_extractor/tests/test_l_api_d_extraction_est_fermee.py

CE QUE CE FICHIER VERROUILLE

Trois collections etaient lisibles sans aucun cookie :
`/api/extraction-jobs/`, `/api/extracted-entities/` et
`/api/extraction-examples/`. Elles rendaient le prompt d'un job, son
`raw_result` et le verbatim de chaque extraction de la base.
/ Three collections used to answer without any cookie.

LA DOCTRINE EST CELLE DU 404, JAMAIS DU 403 (AGENTS.md). Un objet
auquel on n'a pas droit doit repondre EXACTEMENT comme un objet qui
n'existe pas : sinon la difference entre les deux reponses dit, un
identifiant apres l'autre, ce que l'instance contient.
/ 404 doctrine: a forbidden object must answer exactly like a missing one.

DEUX COUCHES, ET LES DEUX SONT TESTEES ICI :
1. un visiteur non connecte n'obtient rien — meme sur un carnet PUBLIC,
   parce que ces endpoints exposent le prompt et le resultat brut, qui
   ne sont pas du corpus ;
2. un visiteur connecte ne voit que les notes de son perimetre.
/ Two layers: no anonymous access at all, then per-user scoping.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AppartenancePageDossier,
    Dossier,
    Page,
    VisibiliteDossier,
)
from hypostasis_extractor.models import (
    ExtractedEntity,
    ExtractionExample,
    ExtractionJob,
    JobExampleMapping,
)

Utilisateur = get_user_model()


class SocleDeLApiDExtraction(TestCase):
    """
    Un proprietaire, un tiers, un membre du staff, et une note privee
    qui porte un job et une extraction.
    / An owner, a stranger, a staff member, and a private note.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprietaire-api", password="motdepasse",
        )
        self.tiers = Utilisateur.objects.create_user(
            username="tiers-api", password="motdepasse",
        )
        self.membre_du_staff = Utilisateur.objects.create_user(
            username="staff-api", password="motdepasse", is_staff=True,
        )

        self.note_privee = Page.objects.create(
            url="http://exemple.local/note-privee",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="le texte de la note privee",
            content_hash="hash-note-privee",
            owner=self.proprietaire,
        )
        self.job_prive = ExtractionJob.objects.create(
            page=self.note_privee,
            name="Analyse de la note privee",
            prompt_description="le prompt entier, qui ne regarde personne",
            status="completed",
        )
        self.extraction_privee = ExtractedEntity.objects.create(
            job=self.job_prive,
            extraction_class="phenomene",
            extraction_text="le verbatim qui ne regarde personne",
            start_char=0,
            end_char=10,
        )

        self.exemple_few_shot = ExtractionExample.objects.create(
            name="Un exemple few-shot",
            example_text="le texte d'exemple, qui est de la configuration",
            example_extractions=[{"extraction_class": "phenomene"}],
            is_active=True,
        )
        # L'exemple est ATTACHE au job prive : c'est par ce chemin-la
        # qu'un lecteur de job pourrait lire une collection reservee au
        # staff. / The example is attached to the private job: that is
        # the side door into a staff-only collection.
        JobExampleMapping.objects.create(
            job=self.job_prive, example=self.exemple_few_shot, order=0,
        )

    def _ranger_dans_un_carnet_public(self, page):
        """
        Range une note dans un carnet public — le cas le plus permissif
        que connaisse le projet.
        / Files a note into a public notebook, the most permissive case.
        """
        carnet_public = Dossier.objects.create(
            name="Carnet public",
            owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        AppartenancePageDossier.objects.create(page=page, dossier=carnet_public)
        return carnet_public


class LesJobsSontFermesAuxInconnus(SocleDeLApiDExtraction):
    """`/api/extraction-jobs/` — la collection et le detail."""

    def test_un_anonyme_n_obtient_pas_la_liste_des_jobs(self):
        reponse = self.client.get("/api/extraction-jobs/")
        self.assertEqual(reponse.status_code, 404)

    def test_un_anonyme_n_obtient_pas_le_detail_d_un_job(self):
        reponse = self.client.get(f"/api/extraction-jobs/{self.job_prive.pk}/")
        self.assertEqual(reponse.status_code, 404)

    def test_un_anonyme_n_obtient_rien_meme_sur_un_carnet_public(self):
        """
        Le carnet public ouvre l'ECRAN de lecture, jamais cette API :
        elle rend le prompt et le resultat brut du modele.
        / A public notebook opens the reading screen, never this API.
        """
        self._ranger_dans_un_carnet_public(self.note_privee)

        reponse = self.client.get(f"/api/extraction-jobs/{self.job_prive.pk}/")
        self.assertEqual(reponse.status_code, 404)

    def test_un_tiers_connecte_ne_voit_pas_le_job_d_une_note_privee(self):
        self.client.force_login(self.tiers)

        reponse = self.client.get(f"/api/extraction-jobs/{self.job_prive.pk}/")
        self.assertEqual(reponse.status_code, 404)

    def test_un_tiers_connecte_a_une_liste_de_jobs_vide(self):
        self.client.force_login(self.tiers)

        reponse = self.client.get("/api/extraction-jobs/")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json(), [])

    def test_le_proprietaire_voit_toujours_son_job(self):
        """
        La fermeture ne doit pas fermer la porte a qui a le droit.
        / Closing must not lock out the rightful reader.
        """
        self.client.force_login(self.proprietaire)

        reponse_de_la_liste = self.client.get("/api/extraction-jobs/")
        reponse_du_detail = self.client.get(
            f"/api/extraction-jobs/{self.job_prive.pk}/"
        )

        self.assertEqual(reponse_de_la_liste.status_code, 200)
        identifiants_listes = [job["id"] for job in reponse_de_la_liste.json()]
        self.assertIn(self.job_prive.pk, identifiants_listes)
        self.assertEqual(reponse_du_detail.status_code, 200)

    def test_un_anonyme_ne_peut_pas_creer_un_job(self):
        reponse = self.client.post(
            "/api/extraction-jobs/",
            data={
                "page": self.note_privee.pk,
                "name": "job pose par un inconnu",
                "prompt_description": "extraire ce qu'on veut",
            },
        )
        self.assertEqual(reponse.status_code, 404)

    def test_un_tiers_ne_peut_pas_creer_un_job_sur_la_note_d_autrui(self):
        self.client.force_login(self.tiers)

        reponse = self.client.post(
            "/api/extraction-jobs/",
            data={
                "page": self.note_privee.pk,
                "name": "job pose par un tiers",
                "prompt_description": "extraire ce qu'on veut",
            },
        )

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(
            ExtractionJob.objects.filter(name="job pose par un tiers").count(),
            0,
        )


class LesExemplesNeSortentPasParLaPorteDUnJob(SocleDeLApiDExtraction):
    """
    Un exemple few-shot est réservé au staff. Le détail d'un job en
    attache — c'est la porte d'à côté, et elle doit être fermée aussi.
    / A few-shot example is staff-only; a job's detail attaches some,
    and that side door must be closed too.
    """

    def test_le_proprietaire_du_job_ne_lit_pas_le_contenu_des_exemples(self):
        self.client.force_login(self.proprietaire)

        reponse = self.client.get(f"/api/extraction-jobs/{self.job_prive.pk}/")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()["examples"], [])
        self.assertNotIn(
            self.exemple_few_shot.example_text, reponse.content.decode()
        )

    def test_le_staff_lit_le_contenu_des_exemples_de_SON_job(self):
        """
        ÊTRE STAFF NE DONNE AUCUN DROIT DE LECTURE SUR LES NOTES DES
        AUTRES : seul le superuser a ce contournement
        (`notes_visibles_par`, SPEC-corpus § 5.2). Le staff lit donc le
        contenu des exemples **de ses propres jobs** — le droit sur
        l'exemple et le droit sur la note se cumulent, ils ne se
        remplacent pas.
        / Being staff grants no read access to other people's notes:
        only the superuser has that bypass. The two rights stack.
        """
        self.client.force_login(self.membre_du_staff)
        note_du_staff = Page.objects.create(
            url="http://exemple.local/note-du-staff-lecture",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="hash-note-staff-lecture",
            owner=self.membre_du_staff,
        )
        job_du_staff = ExtractionJob.objects.create(
            page=note_du_staff,
            name="Analyse du staff",
            prompt_description="le prompt",
            status="completed",
        )
        JobExampleMapping.objects.create(
            job=job_du_staff, example=self.exemple_few_shot, order=0,
        )

        reponse = self.client.get(f"/api/extraction-jobs/{job_du_staff.pk}/")

        self.assertEqual(reponse.status_code, 200)
        exemples_rendus = reponse.json()["examples"]
        self.assertEqual(len(exemples_rendus), 1)
        self.assertEqual(
            exemples_rendus[0]["example_text"],
            self.exemple_few_shot.example_text,
        )

    def test_le_staff_ne_lit_pas_le_job_d_une_note_qui_n_est_pas_a_lui(self):
        """
        Le pendant du test ci-dessus, écrit pour que la règle soit vue :
        `is_staff` ouvre la configuration du moteur, jamais le corpus
        d'autrui.
        / Its counterpart: is_staff opens engine configuration, never
        someone else's corpus.
        """
        self.client.force_login(self.membre_du_staff)

        reponse = self.client.get(f"/api/extraction-jobs/{self.job_prive.pk}/")

        self.assertEqual(reponse.status_code, 404)

    def test_un_utilisateur_ordinaire_ne_peut_pas_attacher_un_exemple(self):
        """
        Poster une liste d'identifiants sur SA PROPRE note ne doit pas
        suffire à attacher un exemple de l'instance.
        / Posting ids onto one's OWN note must not attach an example.
        """
        self.client.force_login(self.proprietaire)

        reponse = self.client.post(
            "/api/extraction-jobs/",
            data={
                "page": self.note_privee.pk,
                "name": "job avec un exemple volé",
                "prompt_description": "extraire",
                "example_ids": [self.exemple_few_shot.pk],
            },
            content_type="application/json",
        )

        self.assertEqual(reponse.status_code, 400)
        self.assertIn("example_ids", reponse.json())
        self.assertEqual(
            JobExampleMapping.objects.filter(
                job__name="job avec un exemple volé"
            ).count(),
            0,
        )

    def test_le_staff_peut_attacher_un_exemple(self):
        self.client.force_login(self.membre_du_staff)
        note_du_staff = Page.objects.create(
            url="http://exemple.local/note-du-staff",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="hash-note-staff",
            owner=self.membre_du_staff,
        )

        reponse = self.client.post(
            "/api/extraction-jobs/",
            data={
                "page": note_du_staff.pk,
                "name": "job du staff",
                "prompt_description": "extraire",
                "example_ids": [self.exemple_few_shot.pk],
            },
            content_type="application/json",
        )

        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(
            JobExampleMapping.objects.filter(job__name="job du staff").count(),
            1,
        )


class LaCreationNEnumerePasLesNotes(SocleDeLApiDExtraction):
    """
    Le piège de `create` : le champ `page` d'un `ModelSerializer` voit
    TOUTES les notes. Laisser le serializer trancher rendrait 400 pour
    une note absente et 404 pour une note interdite — et la différence
    entre ces deux réponses énumère les notes de l'instance.
    / The create trap: letting the serializer decide answers 400 for a
    missing note and 404 for a forbidden one, which enumerates them all.
    """

    def test_la_note_interdite_repond_comme_une_note_inexistante(self):
        self.client.force_login(self.tiers)

        corps_de_la_requete = {
            "name": "job sondeur",
            "prompt_description": "extraire",
        }
        reponse_pour_l_interdite = self.client.post(
            "/api/extraction-jobs/",
            data={**corps_de_la_requete, "page": self.note_privee.pk},
            content_type="application/json",
        )
        reponse_pour_l_inexistante = self.client.post(
            "/api/extraction-jobs/",
            data={**corps_de_la_requete, "page": 999999},
            content_type="application/json",
        )

        self.assertEqual(reponse_pour_l_interdite.status_code, 404)
        self.assertEqual(
            reponse_pour_l_interdite.status_code,
            reponse_pour_l_inexistante.status_code,
        )
        self.assertEqual(
            reponse_pour_l_interdite.content,
            reponse_pour_l_inexistante.content,
        )

    def test_un_identifiant_de_note_qui_n_est_pas_un_nombre_rend_404(self):
        """
        `filter(pk="abc")` lève `ValueError`, donc un 500 — qui dit au
        passage que la vue existe.
        / A non-numeric id would raise ValueError, hence a 500.
        """
        self.client.force_login(self.tiers)

        reponse = self.client.post(
            "/api/extraction-jobs/",
            data={
                "page": "abc",
                "name": "job sondeur",
                "prompt_description": "extraire",
            },
            content_type="application/json",
        )

        self.assertEqual(reponse.status_code, 404)


class UnIdentifiantQuiNEstPasUnNombreRend404(SocleDeLApiDExtraction):
    """
    Le routeur DRF accepte `[^/.]+` comme identifiant : une chaîne
    arrive donc jusqu'au queryset, où elle lèverait `ValueError`.
    / The DRF router accepts non-numeric ids, which would raise.
    """

    def test_sur_le_detail_d_un_job(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.get("/api/extraction-jobs/abc/")
        self.assertEqual(reponse.status_code, 404)

    def test_sur_le_detail_d_une_extraction(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.get("/api/extracted-entities/abc/")
        self.assertEqual(reponse.status_code, 404)

    def test_sur_le_detail_d_un_exemple(self):
        self.client.force_login(self.membre_du_staff)
        reponse = self.client.get("/api/extraction-examples/abc/")
        self.assertEqual(reponse.status_code, 404)


class UnCorpsOuUnFiltreMalFormeNeFaitPasTomberLaVue(SocleDeLApiDExtraction):
    """
    Ces trois entrées contournent le chemin des identifiants d'URL et
    atteignent le queryset ou le corps de la vue. Chacune produisait un
    **500** — qui dit au passage que la vue existe.
    / Three inputs that bypass the URL-id path and used to raise a 500.
    """

    def test_un_filtre_de_job_qui_n_est_pas_un_nombre_ne_leve_pas(self):
        self.client.force_login(self.proprietaire)

        reponse = self.client.get("/api/extraction-jobs/?page=abc")

        self.assertEqual(reponse.status_code, 200)

    def test_un_filtre_d_extraction_qui_n_est_pas_un_nombre_ne_leve_pas(self):
        self.client.force_login(self.proprietaire)

        reponse = self.client.get("/api/extracted-entities/?job=abc")

        self.assertEqual(reponse.status_code, 200)

    def test_un_filtre_ignore_ne_montre_jamais_hors_du_perimetre(self):
        """
        Ignorer un filtre élargit la liste — mais **jamais au-delà du
        périmètre**, qui est posé avant lui.
        / Ignoring a filter widens the list, never past the scope.
        """
        self.client.force_login(self.tiers)

        reponse = self.client.get("/api/extraction-jobs/?page=abc")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json(), [])

    def test_un_corps_json_qui_n_est_pas_un_objet_ne_leve_pas(self):
        """
        `request.data` n'est pas toujours un dictionnaire : un corps
        JSON qui vaut `[1]` arrive tel quel, et `.get` lèverait.
        / request.data is not always a dict.
        """
        self.client.force_login(self.tiers)

        reponse = self.client.post(
            "/api/extraction-jobs/",
            data="[1]",
            content_type="application/json",
        )

        self.assertEqual(reponse.status_code, 404)

    def test_un_corps_sans_note_rend_404(self):
        self.client.force_login(self.tiers)

        reponse = self.client.post(
            "/api/extraction-jobs/",
            data={"name": "job sans note", "prompt_description": "extraire"},
            content_type="application/json",
        )

        self.assertEqual(reponse.status_code, 404)


class UnCarnetPublicOuvreAussiCetteApi(SocleDeLApiDExtraction):
    """
    CE COMPORTEMENT EST VOULU, et ce test existe pour qu'il soit vu.
    Le périmètre est celui du projet (`notes_visibles_par`,
    SPEC-corpus § 5.2) : ranger une note dans un carnet public LA REND
    PUBLIQUE, ses jobs compris — donc son prompt et son `raw_result`.
    Seul l'anonyme est tenu plus court.
    / Deliberate: filing a note into a public notebook makes it public,
    jobs included. Only the anonymous visitor is held shorter.
    """

    def test_un_tiers_connecte_lit_le_job_d_une_note_en_carnet_public(self):
        self._ranger_dans_un_carnet_public(self.note_privee)
        self.client.force_login(self.tiers)

        reponse = self.client.get(f"/api/extraction-jobs/{self.job_prive.pk}/")

        self.assertEqual(reponse.status_code, 200)

    def test_mais_il_ne_peut_pas_valider_l_extraction_qu_il_lit(self):
        """
        Lire n'est pas écrire : un carnet public se lit sans se
        corriger. / Reading is not writing.
        """
        self._ranger_dans_un_carnet_public(self.note_privee)
        self.client.force_login(self.tiers)

        reponse_de_lecture = self.client.get(
            f"/api/extracted-entities/{self.extraction_privee.pk}/"
        )
        reponse_de_validation = self.client.post(
            f"/api/extracted-entities/{self.extraction_privee.pk}/validate/",
            data={"user_validated": True},
        )

        self.assertEqual(reponse_de_lecture.status_code, 200)
        self.assertEqual(reponse_de_validation.status_code, 404)
        self.extraction_privee.refresh_from_db()
        self.assertFalse(self.extraction_privee.user_validated)

    def test_le_refus_d_ecriture_repond_comme_une_extraction_inexistante(self):
        """
        Le cas le plus fin : le visiteur PEUT lire l'objet, mais pas
        l'écrire. Les deux corps doivent rester identiques.
        / The finest case: readable but not writable, same body.
        """
        self._ranger_dans_un_carnet_public(self.note_privee)
        self.client.force_login(self.tiers)

        reponse_pour_l_interdite = self.client.post(
            f"/api/extracted-entities/{self.extraction_privee.pk}/validate/",
            data={"user_validated": True},
        )
        reponse_pour_l_inexistante = self.client.post(
            "/api/extracted-entities/999999/validate/",
            data={"user_validated": True},
        )

        self.assertEqual(
            reponse_pour_l_interdite.content,
            reponse_pour_l_inexistante.content,
        )


class LeRefusNeSeDistinguePasDeLAbsence(SocleDeLApiDExtraction):
    """
    Le coeur de la doctrine : deux reponses IDENTIQUES, au corps pres.
    Si le refus et l'absence differaient d'un octet, la difference
    suffirait a enumerer ce que l'instance contient.
    / The heart of the doctrine: refusal and absence answer identically.
    """

    IDENTIFIANT_QUI_N_EXISTE_PAS = 999999

    def test_le_job_interdit_repond_comme_un_job_inexistant(self):
        self.client.force_login(self.tiers)

        reponse_pour_l_interdit = self.client.get(
            f"/api/extraction-jobs/{self.job_prive.pk}/"
        )
        reponse_pour_l_inexistant = self.client.get(
            f"/api/extraction-jobs/{self.IDENTIFIANT_QUI_N_EXISTE_PAS}/"
        )

        self.assertEqual(
            reponse_pour_l_interdit.status_code,
            reponse_pour_l_inexistant.status_code,
        )
        self.assertEqual(
            reponse_pour_l_interdit.content,
            reponse_pour_l_inexistant.content,
        )

    def test_l_extraction_interdite_repond_comme_une_inexistante(self):
        self.client.force_login(self.tiers)

        reponse_pour_l_interdite = self.client.get(
            f"/api/extracted-entities/{self.extraction_privee.pk}/"
        )
        reponse_pour_l_inexistante = self.client.get(
            f"/api/extracted-entities/{self.IDENTIFIANT_QUI_N_EXISTE_PAS}/"
        )

        self.assertEqual(
            reponse_pour_l_interdite.status_code,
            reponse_pour_l_inexistante.status_code,
        )
        self.assertEqual(
            reponse_pour_l_interdite.content,
            reponse_pour_l_inexistante.content,
        )

    def test_l_exemple_interdit_repond_comme_un_exemple_inexistant(self):
        self.client.force_login(self.tiers)

        reponse_pour_l_interdit = self.client.get(
            f"/api/extraction-examples/{self.exemple_few_shot.pk}/"
        )
        reponse_pour_l_inexistant = self.client.get(
            f"/api/extraction-examples/{self.IDENTIFIANT_QUI_N_EXISTE_PAS}/"
        )

        self.assertEqual(
            reponse_pour_l_interdit.status_code,
            reponse_pour_l_inexistant.status_code,
        )
        self.assertEqual(
            reponse_pour_l_interdit.content,
            reponse_pour_l_inexistant.content,
        )


class LesExtractionsSontFermeesAuxInconnus(SocleDeLApiDExtraction):
    """`/api/extracted-entities/` — la collection, le detail, la validation."""

    def test_un_anonyme_n_obtient_pas_la_liste_des_extractions(self):
        reponse = self.client.get("/api/extracted-entities/")
        self.assertEqual(reponse.status_code, 404)

    def test_un_anonyme_n_obtient_pas_le_detail_d_une_extraction(self):
        reponse = self.client.get(
            f"/api/extracted-entities/{self.extraction_privee.pk}/"
        )
        self.assertEqual(reponse.status_code, 404)

    def test_un_tiers_connecte_ne_voit_pas_l_extraction_d_une_note_privee(self):
        self.client.force_login(self.tiers)

        reponse = self.client.get(
            f"/api/extracted-entities/{self.extraction_privee.pk}/"
        )
        self.assertEqual(reponse.status_code, 404)

    def test_un_tiers_connecte_a_une_liste_d_extractions_vide(self):
        self.client.force_login(self.tiers)

        reponse = self.client.get("/api/extracted-entities/")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json(), [])

    def test_le_proprietaire_voit_toujours_son_extraction(self):
        self.client.force_login(self.proprietaire)

        reponse_de_la_liste = self.client.get("/api/extracted-entities/")
        reponse_du_detail = self.client.get(
            f"/api/extracted-entities/{self.extraction_privee.pk}/"
        )

        self.assertEqual(reponse_de_la_liste.status_code, 200)
        identifiants_listes = [
            extraction["id"] for extraction in reponse_de_la_liste.json()
        ]
        self.assertIn(self.extraction_privee.pk, identifiants_listes)
        self.assertEqual(reponse_du_detail.status_code, 200)

    def test_un_anonyme_ne_peut_pas_valider_une_extraction(self):
        reponse = self.client.post(
            f"/api/extracted-entities/{self.extraction_privee.pk}/validate/",
            data={"user_validated": True},
        )

        self.assertEqual(reponse.status_code, 404)
        self.extraction_privee.refresh_from_db()
        self.assertFalse(self.extraction_privee.user_validated)

    def test_un_tiers_ne_peut_pas_valider_l_extraction_d_autrui(self):
        self.client.force_login(self.tiers)

        reponse = self.client.post(
            f"/api/extracted-entities/{self.extraction_privee.pk}/validate/",
            data={"user_validated": True},
        )

        self.assertEqual(reponse.status_code, 404)
        self.extraction_privee.refresh_from_db()
        self.assertFalse(self.extraction_privee.user_validated)


class LesExemplesFewShotSontReservesAuStaff(SocleDeLApiDExtraction):
    """
    `/api/extraction-examples/` — un exemple few-shot n'appartient a
    aucune note : il est de la configuration du moteur, comme un
    analyseur. Il suit donc la meme regle que `/api/analyseurs/` — le
    staff, et personne d'autre — mais en 404, pas en 403.
    / A few-shot example belongs to no note: it is engine configuration,
    staff-only, answered with 404 instead of 403.
    """

    def test_un_anonyme_n_obtient_pas_la_liste_des_exemples(self):
        reponse = self.client.get("/api/extraction-examples/")
        self.assertEqual(reponse.status_code, 404)

    def test_un_anonyme_n_obtient_pas_le_detail_d_un_exemple(self):
        reponse = self.client.get(
            f"/api/extraction-examples/{self.exemple_few_shot.pk}/"
        )
        self.assertEqual(reponse.status_code, 404)

    def test_un_utilisateur_ordinaire_n_obtient_pas_les_exemples(self):
        self.client.force_login(self.tiers)

        reponse = self.client.get("/api/extraction-examples/")

        self.assertEqual(reponse.status_code, 404)

    def test_un_anonyme_ne_peut_pas_creer_un_exemple(self):
        reponse = self.client.post(
            "/api/extraction-examples/",
            data={
                "name": "exemple pose par un inconnu",
                "example_text": "texte",
                "example_extractions": [],
            },
            content_type="application/json",
        )

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(
            ExtractionExample.objects.filter(
                name="exemple pose par un inconnu"
            ).count(),
            0,
        )

    def test_le_staff_voit_toujours_les_exemples(self):
        self.client.force_login(self.membre_du_staff)

        reponse_de_la_liste = self.client.get("/api/extraction-examples/")
        reponse_du_detail = self.client.get(
            f"/api/extraction-examples/{self.exemple_few_shot.pk}/"
        )

        self.assertEqual(reponse_de_la_liste.status_code, 200)
        self.assertEqual(len(reponse_de_la_liste.json()), 1)
        self.assertEqual(reponse_du_detail.status_code, 200)


class LaSidebarNeFuitPas(SocleDeLApiDExtraction):
    """
    `/api/sidebar/` (core/views.py) reste volontairement `AllowAny` :
    l'extension navigateur l'interroge parfois sans session. Sa
    recherche est bornee par `notes_visibles_par`, et sa reponse ne dit
    jamais si la note existe.
    / The sidebar endpoint stays AllowAny on purpose; its lookup is
    scoped and its answer never reveals existence.
    """

    def test_un_anonyme_n_obtient_pas_le_contenu_d_une_note_privee(self):
        reponse = self.client.get(
            "/api/sidebar/", {"url": self.note_privee.url}
        )

        self.assertEqual(reponse.status_code, 200)
        corps_de_la_reponse = reponse.content.decode()
        self.assertIn("Aucune analyse", corps_de_la_reponse)
        self.assertNotIn(
            self.extraction_privee.extraction_text, corps_de_la_reponse
        )
