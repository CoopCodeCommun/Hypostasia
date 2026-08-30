"""
Le mode d'edition par blocs — ce que le SERVEUR en garantit.
/ The block editing mode: what the SERVER guarantees.

LOCALISATION : front/tests/test_mode_edition.py

SPEC-edition-par-blocs-et-stenotypie.md § 2 (deux modes) et § 8.1 (le
mode ne s'ouvre pas si une analyse tourne).

CE QUE CES TESTS COUVRENT, ET CE QU'ILS NE COUVRENT PAS

Le comportement du mode est du JAVASCRIPT : la garde `beforeinput`, la
parade a la composition, la pile d'annulation, `Ctrl+S`. Rien de tout
cela ne s'eprouve ici — un test Django n'execute pas de navigateur. Il
est mesure au navigateur, sur trois moteurs, par
`benchmarks/edition_par_blocs/banc/mesures16_mode_edition.py`.

Ce fichier verrouille ce qui depend du SERVEUR : le bouton existe, il
est DESACTIVE pendant une analyse, et la zone d'accueil du compte rendu
est la.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AppartenancePageDossier,
    Dossier,
    ElementDocument,
    Page,
    empreinte_du_texte,
)
from hypostasis_extractor.models import ExtractionJob

Utilisateur = get_user_model()


class BaseDuModeEdition(TestCase):
    """Socle : une note a trois blocs, que son proprietaire peut ecrire."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprietaire-mode", password="motdepasse",
        )
        self.dossier = Dossier.objects.create(
            name="Carnet du mode", owner=self.proprietaire,
        )
        self.page = Page.objects.create(
            url="http://exemple.local/le-mode",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-du-mode",
            owner=self.proprietaire, dossier=self.dossier,
        )
        AppartenancePageDossier.objects.create(
            page=self.page, dossier=self.dossier,
        )
        for ordre, texte in enumerate(("Premier passage.", "Deuxième passage.")):
            ElementDocument.objects.create(
                page=self.page, ordre=ordre, label="text", texte=texte,
                empreinte_contenu=empreinte_du_texte(texte),
            )
        self.client.force_login(self.proprietaire)

    def _lire(self):
        return self.client.get(f"/lire/{self.page.pk}/")

    def _balise_du_bouton(self, reponse):
        """
        Rend la BALISE OUVRANTE du bouton, et rien d'autre.

        Chercher « disabled » dans le HTML entier ne prouve rien : les
        classes Tailwind du bouton contiennent `disabled:opacity-40`,
        `disabled:cursor-not-allowed`... Seul l'ATTRIBUT compte.
        / The Tailwind classes contain "disabled:": only the attribute counts.
        """
        import re
        corps = reponse.content.decode()
        trouve = re.search(
            r"<button[^>]*id=\"bouton-mode-edition\"[^>]*>", corps,
        )
        self.assertIsNotNone(trouve, "le bouton du mode n'est pas rendu")
        return trouve.group(0)


class LeBoutonDuMode(BaseDuModeEdition):
    """§ 2 : le mode doit se voir, et son bouton dire son état."""

    def test_le_bouton_est_rendu_pour_qui_peut_ecrire(self):
        reponse = self._lire()
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'data-testid="bouton-mode-edition"')
        self.assertContains(reponse, "basculerModeEdition")

    def test_le_bouton_porte_aria_pressed(self):
        """
        Un mode invisible qui capture le clavier est une source de
        confusion (§ 2). Le bouton DIT dans quel mode on est.
        / A mode that captures the keyboard must say so.
        """
        self.assertIn('aria-pressed="false"',
                      self._balise_du_bouton(self._lire()))

    def test_la_zone_du_compte_rendu_existe(self):
        """
        Sans elle, le compte rendu du § 7.4 n'a nulle part où s'afficher
        — et il porte `aria-live`, donc il ne s'annoncerait pas non plus.
        / Without it, the report has nowhere to land.
        """
        self.assertContains(self._lire(), 'id="compte-rendu-du-lot"')

    def test_un_simple_lecteur_n_a_PAS_le_bouton(self):
        """Lire n'est pas écrire. / Reading is not writing."""
        tiers = Utilisateur.objects.create_user(
            username="lecteur-mode", password="motdepasse",
        )
        from core.models import VisibiliteDossier
        self.dossier.visibilite = VisibiliteDossier.PUBLIC
        self.dossier.save(update_fields=["visibilite"])
        self.client.force_login(tiers)
        self.assertNotContains(self._lire(), 'data-testid="bouton-mode-edition"')


class LeModeNeSOuvrePasPendantUneAnalyse(BaseDuModeEdition):
    """
    § 8.1 : le refus vit A L'ENTREE, pas seulement à l'écriture.

    Le refus existe aussi au moment d'enregistrer — les services
    reposent la garde eux-mêmes, et le lot entier est alors annulé.
    Mais un refus qui arrive APRÈS vingt minutes de frappe est le pire
    des deux mondes.
    / The refusal lives up front, not only at write time.
    """

    def test_le_bouton_est_DESACTIVE_pendant_une_analyse(self):
        ExtractionJob.objects.create(page=self.page, status="processing")
        import re
        balise = self._balise_du_bouton(self._lire())
        self.assertIsNotNone(
            re.search(r"\sdisabled[\s>]", balise),
            f"le bouton doit porter l'attribut disabled. Balise : {balise[:200]}",
        )

    def test_le_bouton_DIT_pourquoi_il_est_desactive(self):
        """
        Un bouton grisé sans raison est une impasse. Le projet exige
        qu'un refus soit bruyant.
        / A greyed-out button without a reason is a dead end.
        """
        ExtractionJob.objects.create(page=self.page, status="processing")
        self.assertContains(self._lire(), "Une analyse tourne sur cette note")

    def test_le_bouton_est_ACTIF_quand_aucune_analyse_ne_tourne(self):
        import re
        balise = self._balise_du_bouton(self._lire())
        self.assertIsNone(
            re.search(r"\sdisabled[\s>]", balise),
            f"le bouton ne doit PAS être désactivé. Balise : {balise[:200]}",
        )


class LeFiltreDeGarde(BaseDuModeEdition):
    """
    Le filtre est la SEULE source du bouton : une variable de contexte
    oubliée dans l'un des trois rendus de `lecture_principale.html`
    vaudrait « faux », donc un bouton actif pendant une analyse.
    / The filter is the single source: a forgotten context variable
    would read as False.
    """

    def test_le_filtre_dit_vrai_quand_une_analyse_tourne(self):
        from front.templatetags.corpus_permissions import une_analyse_tourne_sur
        self.assertFalse(une_analyse_tourne_sur(self.page))
        ExtractionJob.objects.create(page=self.page, status="processing")
        self.assertTrue(une_analyse_tourne_sur(self.page))


class LeScriptEstCharge(TestCase):
    """Sans le script, le bouton ne fait rien — et rien ne le dirait."""

    def test_mode_edition_js_est_charge_par_base_html(self):
        from pathlib import Path
        from django.conf import settings
        base = (Path(settings.BASE_DIR) / "front" / "templates" / "front"
                / "base.html").read_text(encoding="utf-8")
        self.assertIn("front/js/mode_edition.js", base)
        self.assertIn("mode_edition.js' %}?v=", base,
                      "le script doit porter un ?v= : sans lui, les "
                      "navigateurs servent l'ancien fichier")

    def test_le_script_existe_et_ne_pose_aucun_ecouteur_echap(self):
        """
        Échap appartient à la cascade de `keyboard.js`. Un écouteur ici
        rejouerait le défaut payé le 29 août.
        / Escape belongs to keyboard.js's cascade.
        """
        from pathlib import Path
        from django.conf import settings
        script = (Path(settings.BASE_DIR) / "front" / "static" / "front" / "js"
                  / "mode_edition.js").read_text(encoding="utf-8")
        for ligne in script.splitlines():
            if "'Escape'" in ligne or '"Escape"' in ligne:
                self.fail(
                    "mode_edition.js teste la touche Échap : elle appartient "
                    f"à la cascade. Ligne : {ligne.strip()[:80]}"
                )
