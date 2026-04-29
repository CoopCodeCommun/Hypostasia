"""
Tests pour le flux d'analyse unifie (drawer unique pendant et apres l'analyse).
Verifie que analyse_status retourne le meme template (drawer_vue_liste.html)
dans les deux etats, et que cartes_only=1 retourne les cartes partielles.
/ Tests for the unified analysis flow (single drawer during and after analysis).
/ Verifies that analyse_status returns the same template (drawer_vue_liste.html)
/ in both states, and that cartes_only=1 returns partial cards.

LOCALISATION : front/tests/test_analyse_drawer_unifie.py

PIEGES RESOLUS DANS CETTE SESSION (2026-03-22) :

1. MutationObserver ne detecte pas les OOB swaps HTMX-WS
   Le consumer envoyait un OOB swap sur #signal-rafraichir-drawer et un
   MutationObserver JS devait detecter le changement. Ca ne fonctionnait pas
   car HTMX-WS applique les swaps sans declencher les MutationObserver.
   SOLUTION : remplacer le MutationObserver par un hx-get + hx-trigger="load"
   dans le fragment OOB. HTMX traite l'attribut et lance la requete auto.

2. Deux templates differents pendant et apres l'analyse
   panneau_analyse_en_cours.html (cards simples via _card_body.html) vs
   drawer_vue_liste.html (cards riches avec pastille, citation, masquer).
   L'utilisateur voyait un template different selon le moment.
   SOLUTION : un seul template drawer_vue_liste.html avec analyse_en_cours=True
   qui affiche le bandeau de progression au lieu du bandeau vert.

3. rafraichir_drawer (cartes) ecrasait analyse_progression (barre)
   Les deux signaux WS ciblaient #drawer-contenu. Le refresh des cartes
   (rafraichir_drawer → analyse_status) ecrasait la barre de progression
   (analyse_progression → OOB #barre-progression-analyse).
   SOLUTION : rafraichir_drawer cible #drawer-cartes-liste (sous-zone)
   via analyse_status?cartes_only=1. La barre reste intacte.

4. "Aucune analyse pour cette page" visible pendant l'analyse
   Le template affichait l'etat vide meme avec analyse_en_cours=True.
   SOLUTION : {% if analyse_en_cours %} dans le {% empty %} du for loop.
"""

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from core.models import Page
from hypostasis_extractor.models import (
    ExtractionJob,
    ExtractedEntity,
)


class AnalyseStatusEnCoursTest(TestCase):
    """
    Verifie que analyse_status retourne drawer_vue_liste.html (pas panneau_analyse_en_cours)
    quand un job est en cours, avec le bandeau de progression.
    / Verifies analyse_status returns drawer_vue_liste.html (not panneau_analyse_en_cours)
    / when a job is running, with the progress banner.
    """

    def setUp(self):
        # Creer un utilisateur et une page de test
        # / Create a test user and page
        self.utilisateur_test = User.objects.create_user(
            username="test_analyse_unifie", password="test1234",
        )
        self.page_test = Page.objects.create(
            title="Page test analyse unifie",
            html_readability="<p>Texte de test pour l'analyse.</p>",
            text_readability="Texte de test pour l'analyse.",
            source_type="file",
            status="completed",
        )

        # Creer un job en cours (processing) avec quelques entites
        # / Create a processing job with some entities
        self.job_en_cours = ExtractionJob.objects.create(
            page=self.page_test,
            status="processing",
            name="Test job en cours",
        )

        # Creer 3 entites deja trouvees pendant l'analyse
        # / Create 3 entities already found during analysis
        for numero_entite in range(3):
            ExtractedEntity.objects.create(
                job=self.job_en_cours,
                extraction_class="hypostase",
                extraction_text=f"Extraction test {numero_entite}",
                start_char=numero_entite * 10,
                end_char=numero_entite * 10 + 8,
                attributes={
                    "resume": f"Resume {numero_entite}",
                    "hypostases": "theorie, probleme",
                    "mots_cles": f"mot{numero_entite}",
                },
            )

        self.client.login(username="test_analyse_unifie", password="test1234")

    def test_analyse_status_en_cours_contient_bandeau_progression(self):
        """Le drawer en cours affiche le bandeau de progression indigo."""
        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        # Doit contenir le bandeau de progression (data-testid)
        # / Must contain the progress banner (data-testid)
        self.assertIn("bandeau-analyse-en-cours", contenu)

    def test_analyse_status_en_cours_ne_contient_pas_aucune_analyse(self):
        """Le drawer en cours ne doit PAS afficher 'Aucune analyse pour cette page'."""
        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        contenu = reponse.content.decode()
        self.assertNotIn("Aucune analyse pour cette page", contenu)

    def test_analyse_status_en_cours_contient_cartes_entites(self):
        """Le drawer en cours affiche les cartes des entites deja trouvees."""
        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        contenu = reponse.content.decode()
        # Doit contenir les cartes avec le data-testid
        # / Must contain cards with data-testid
        self.assertIn("drawer-carte", contenu)

    def test_analyse_status_en_cours_utilise_drawer_vue_liste(self):
        """Le drawer en cours utilise drawer_vue_liste (pas panneau_analyse_en_cours)."""
        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        contenu = reponse.content.decode()
        # drawer_vue_liste contient drawer-contenu-inner
        # / drawer_vue_liste contains drawer-contenu-inner
        self.assertIn("drawer-contenu-inner", contenu)

    def test_analyse_status_en_cours_ne_contient_pas_bandeau_vert(self):
        """Le drawer en cours ne doit PAS afficher le bandeau vert de succes."""
        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        contenu = reponse.content.decode()
        self.assertNotIn("bandeau-resume-analyse", contenu)

    def test_analyse_status_en_cours_affiche_message_attente_si_zero_entite(self):
        """Si aucune entite n'est encore creee, afficher un message d'attente."""
        # Supprimer les entites du job
        # / Delete job entities
        ExtractedEntity.objects.filter(job=self.job_en_cours).delete()

        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        contenu = reponse.content.decode()
        self.assertIn("drawer-attente-extractions", contenu)
        self.assertNotIn("Aucune analyse pour cette page", contenu)


class AnalyseStatusCartesOnlyTest(TestCase):
    """
    Verifie que analyse_status?cartes_only=1 retourne uniquement les cartes
    (drawer_cartes_partielles.html) sans le header ni le bandeau.
    / Verifies analyse_status?cartes_only=1 returns only cards
    / (drawer_cartes_partielles.html) without header or banner.
    """

    def setUp(self):
        self.utilisateur_test = User.objects.create_user(
            username="test_cartes_only", password="test1234",
        )
        self.page_test = Page.objects.create(
            title="Page test cartes only",
            html_readability="<p>Test cartes only.</p>",
            text_readability="Test cartes only.",
            source_type="file",
            status="completed",
        )
        self.job_en_cours = ExtractionJob.objects.create(
            page=self.page_test,
            status="processing",
            name="Test cartes only job",
        )
        ExtractedEntity.objects.create(
            job=self.job_en_cours,
            extraction_class="hypostase",
            extraction_text="Citation cartes only",
            start_char=0,
            end_char=20,
            attributes={
                "resume": "Resume cartes only",
                "hypostases": "definition",
                "mots_cles": "test",
            },
        )
        self.client.login(username="test_cartes_only", password="test1234")

    def test_cartes_only_ne_contient_pas_bandeau(self):
        """cartes_only=1 ne doit pas contenir le bandeau de progression."""
        reponse = self.client.get(
            f"/lire/{self.page_test.pk}/analyse_status/?cartes_only=1",
        )
        contenu = reponse.content.decode()
        self.assertNotIn("bandeau-analyse-en-cours", contenu)
        self.assertNotIn("drawer-contenu-inner", contenu)

    def test_cartes_only_contient_les_cartes(self):
        """cartes_only=1 retourne les cartes d'extraction."""
        reponse = self.client.get(
            f"/lire/{self.page_test.pk}/analyse_status/?cartes_only=1",
        )
        contenu = reponse.content.decode()
        self.assertIn("drawer-carte", contenu)
        self.assertIn("Citation cartes only", contenu)

    def test_cartes_only_contient_oob_texte_annote(self):
        """cartes_only=1 retourne aussi l'OOB du texte annote."""
        reponse = self.client.get(
            f"/lire/{self.page_test.pk}/analyse_status/?cartes_only=1",
        )
        contenu = reponse.content.decode()
        self.assertIn("readability-content", contenu)
        self.assertIn("hx-swap-oob", contenu)

    def test_cartes_only_message_attente_si_zero_entite(self):
        """cartes_only=1 avec 0 entites affiche le message d'attente."""
        ExtractedEntity.objects.filter(job=self.job_en_cours).delete()
        reponse = self.client.get(
            f"/lire/{self.page_test.pk}/analyse_status/?cartes_only=1",
        )
        contenu = reponse.content.decode()
        self.assertIn("drawer-attente-extractions", contenu)


class AnalyseStatusTermineeTest(TestCase):
    """
    Verifie que analyse_status avec un job completed retourne drawer_vue_liste
    avec le bandeau vert et les cartes riches.
    / Verifies analyse_status with a completed job returns drawer_vue_liste
    / with green banner and rich cards.
    """

    def setUp(self):
        self.utilisateur_test = User.objects.create_user(
            username="test_analyse_finie", password="test1234",
        )
        self.page_test = Page.objects.create(
            title="Page test terminee",
            html_readability="<p>Test terminee.</p>",
            text_readability="Test terminee.",
            source_type="file",
            status="completed",
        )
        self.job_termine = ExtractionJob.objects.create(
            page=self.page_test,
            status="completed",
            name="Test job termine",
        )
        ExtractedEntity.objects.create(
            job=self.job_termine,
            extraction_class="hypostase",
            extraction_text="Test terminee.",
            start_char=0,
            end_char=14,
            attributes={
                "resume": "Resume test",
                "hypostases": "theorie",
                "mots_cles": "test",
            },
        )
        self.client.login(username="test_analyse_finie", password="test1234")

    def test_analyse_terminee_contient_bandeau_vert(self):
        """Un job completed affiche le bandeau vert de succes."""
        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        contenu = reponse.content.decode()
        self.assertIn("bandeau-resume-analyse", contenu)

    def test_analyse_terminee_ne_contient_pas_bandeau_progression(self):
        """Un job completed ne doit PAS afficher le bandeau de progression."""
        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        contenu = reponse.content.decode()
        self.assertNotIn("bandeau-analyse-en-cours", contenu)

    def test_analyse_terminee_utilise_drawer_vue_liste(self):
        """Un job completed utilise aussi drawer_vue_liste."""
        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        contenu = reponse.content.decode()
        self.assertIn("drawer-contenu-inner", contenu)

    def test_analyse_terminee_contient_cartes(self):
        """Un job completed affiche les cartes d'extraction."""
        reponse = self.client.get(f"/lire/{self.page_test.pk}/analyse_status/")
        contenu = reponse.content.decode()
        self.assertIn("drawer-carte", contenu)


class AnalyseConsumerSignalTest(TestCase):
    """
    Verifie que les fragments HTML generes par le consumer sont corrects
    (hx-trigger='load', cible correcte selon le type de signal).
    / Verifies that HTML fragments generated by the consumer are correct
    / (hx-trigger='load', correct target depending on signal type).
    """

    def test_rafraichir_drawer_cible_drawer_cartes_liste(self):
        """Le consumer rafraichir_drawer doit cibler #drawer-cartes-liste via cartes_only=1."""
        import asyncio
        from front.consumers import NotificationConsumer

        consumer = NotificationConsumer()
        fragments_envoyes = []

        async def mock_send(text_data):
            fragments_envoyes.append(text_data)

        consumer.send = mock_send
        asyncio.run(consumer.rafraichir_drawer({"page_id": 42}))

        self.assertEqual(len(fragments_envoyes), 1)
        fragment_html = fragments_envoyes[0]
        # Doit cibler #drawer-cartes-liste (pas #drawer-contenu)
        # / Must target #drawer-cartes-liste (not #drawer-contenu)
        self.assertIn('hx-target="#drawer-cartes-liste"', fragment_html)
        self.assertIn("cartes_only=1", fragment_html)
        self.assertIn('hx-trigger="load"', fragment_html)

    def test_analyse_terminee_cible_drawer_contenu(self):
        """Le consumer analyse_terminee doit cibler #drawer-contenu (refresh complet)."""
        import asyncio
        from front.consumers import NotificationConsumer

        consumer = NotificationConsumer()
        fragments_envoyes = []

        async def mock_send(text_data):
            fragments_envoyes.append(text_data)

        consumer.send = mock_send
        asyncio.run(consumer.analyse_terminee({"page_id": 42}))

        self.assertEqual(len(fragments_envoyes), 1)
        fragment_html = fragments_envoyes[0]
        # Doit cibler #drawer-contenu (pas #drawer-cartes-liste)
        # / Must target #drawer-contenu (not #drawer-cartes-liste)
        self.assertIn('hx-target="#drawer-contenu"', fragment_html)
        self.assertNotIn("cartes_only", fragment_html)
        self.assertIn('hx-trigger="load"', fragment_html)
