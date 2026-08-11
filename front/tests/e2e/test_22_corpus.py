"""
Tests E2E de la couche corpus (spec § 10, test_22_corpus.py).
/ Corpus layer E2E tests (spec § 10).

LOCALISATION : front/tests/e2e/test_22_corpus.py

Les cinq scenarios de la spec, joues dans un vrai navigateur.
/ The spec's five scenarios, played in a real browser.
"""

from django.contrib.auth.models import User

from core.models import CategorieDossier, Dossier, ListeDeCategories
from core.services.corpus import ranger_une_note_dans_un_carnet

from .base import PlaywrightLiveTestCase


class E2ECorpusTest(PlaywrightLiveTestCase):
    """Les scenarios § 10 de la spec corpus. / The spec's § 10 scenarios."""

    def setUp(self):
        super().setUp()
        self.utilisateur = User.objects.create_user(
            username="e2e_corpus", password="test1234"
        )
        self.carnet_un = self.creer_dossier_demo(
            "Carnet e2e un", owner=self.utilisateur
        )
        self.carnet_deux = self.creer_dossier_demo(
            "Carnet e2e deux", owner=self.utilisateur
        )
        self.note = self.creer_page_demo(
            "Note e2e corpus", "<p>Contenu corpus e2e.</p>",
            owner=self.utilisateur, dossier=self.carnet_un,
        )
        self.axe = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet_un,
        )
        self.categorie = CategorieDossier.objects.create(
            liste=self.axe, nom="Budget",
        )
        self.connecter(self.utilisateur.username, "test1234")

    def connecter(self, nom, mot_de_passe):
        """Connexion par le formulaire. / Login through the form."""
        self.naviguer_vers("/auth/login/")
        self.page.fill('[data-testid="input-username"]', nom)
        self.page.fill('[data-testid="input-password"]', mot_de_passe)
        self.page.click('[data-testid="btn-submit-login"]')
        self.page.wait_for_url("**/")

    def test_ajouter_une_note_a_un_second_carnet(self):
        # Le bloc passe de 1 a 2 lignes (spec § 10).
        # / The block goes from 1 to 2 rows.
        self.page.goto(f"{self.live_server_url}/lire/{self.note.pk}/")
        bloc = self.page.wait_for_selector('[data-testid="corpus-bloc-carnets"]')
        self.assertIn("Dans 1 carnet", bloc.inner_text())

        self.page.select_option(
            '[data-testid="corpus-bloc-ajouter-select"]',
            str(self.carnet_deux.pk),
        )
        self.page.click('[data-testid="corpus-bloc-ajouter-bouton"]')
        self.page.wait_for_selector(
            '[data-testid="corpus-bloc-carnets"]:has-text("Dans 2 carnets")'
        )
        lignes = self.page.query_selector_all(
            '[data-testid="corpus-bloc-carnet-ligne"]'
        )
        self.assertEqual(len(lignes), 2)

    def test_categoriser_dans_un_carnet_seulement(self):
        # Les categories de l'autre carnet ne bougent pas (spec § 10).
        # / The other notebook's categories stay untouched.
        ranger_une_note_dans_un_carnet(self.note, self.carnet_deux, self.utilisateur)
        self.page.goto(f"{self.live_server_url}/lire/{self.note.pk}/")
        self.page.wait_for_selector('[data-testid="corpus-bloc-carnets"]')

        # Ouvre le crayon du carnet UN (le seul avec des axes) et coche.
        # / Open notebook ONE's pencil and tick.
        self.page.click('[data-testid="corpus-bloc-crayon"]')
        self.page.check('[data-testid="corpus-bloc-case-categorie"]')
        self.page.click('[data-testid="corpus-bloc-enregistrer-categories"]')
        self.page.wait_for_selector(
            '[data-testid="corpus-bloc-categorie"]:has-text("Budget")'
        )

        ligne_carnet_deux = self.page.query_selector(
            f'[data-testid="corpus-bloc-carnet-ligne"][data-carnet-id="{self.carnet_deux.pk}"]'
        )
        self.assertNotIn("Budget", ligne_carnet_deux.inner_text())

    def test_filtres_combines_et_ou(self):
        # ET entre listes, OU dans une liste (spec § 10) — la phrase du
        # resume l'ecrit en toutes lettres. / The summary spells it out.
        appartenance = self.note.appartenances_dossiers.get(dossier=self.carnet_un)
        appartenance.categories.add(self.categorie)

        self.page.goto(f"{self.live_server_url}/carnets/{self.carnet_un.pk}/")
        self.page.wait_for_selector('[data-testid="corpus-filtres"]')
        # On clique la PUCE, pas la case : depuis le portage du design de
        # la maquette, la case native est masquee (opacity:0) et c'est le
        # label qui la porte — exactement ce que fait un utilisateur.
        # Playwright.check() refuse un input invisible.
        # / Click the pill, not the (visually hidden) native checkbox.
        self.page.click(
            'label.puce-categorie:has([data-testid="corpus-filtre-categorie"])'
        )
        self.page.wait_for_selector('[data-testid="corpus-resume-filtres"]')
        resume = self.page.inner_text('[data-testid="corpus-resume-filtres"]')
        self.assertIn("Type : Budget", resume)
        self.assertIn("1 sur 1", resume)

    def test_avertissement_dernier_carnet(self):
        # Retirer la derniere appartenance avertit (spec § 10).
        # / Removing the last membership warns.
        self.page.goto(f"{self.live_server_url}/lire/{self.note.pk}/")
        self.page.wait_for_selector('[data-testid="corpus-bloc-retirer"]')
        confirmation = self.page.get_attribute(
            '[data-testid="corpus-bloc-retirer"]', "hx-confirm"
        )
        self.assertIn("DERNIER carnet", confirmation)

    def test_ordre_manuel_au_clavier(self):
        # Monter/descendre sans souris (spec § 10) : les boutons sont de
        # vrais <button> focusables et actionnables au clavier.
        # / Up/down without a mouse: real focusable buttons.
        seconde_note = self.creer_page_demo(
            "Seconde note e2e", "<p>Autre contenu.</p>",
            owner=self.utilisateur, dossier=self.carnet_un,
        )
        self.page.goto(f"{self.live_server_url}/carnets/{self.carnet_un.pk}/")
        self.page.wait_for_selector('[data-testid="corpus-note-monter"]')

        # Active au CLAVIER le bouton « monter » de la note du bas.
        # / Keyboard-activate the bottom note's "up" button.
        boutons_monter = self.page.query_selector_all(
            '[data-testid="corpus-note-monter"]'
        )
        boutons_monter[-1].focus()
        self.page.keyboard.press("Enter")
        self.page.wait_for_selector('[data-testid="corpus-message-ordre"]')
        message = self.page.inner_text('[data-testid="corpus-message-ordre"]')
        self.assertIn("Ordre modifié", message)
