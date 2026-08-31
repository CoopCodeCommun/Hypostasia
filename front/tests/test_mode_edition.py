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


class LePanneauDesPassagesMasques(BaseDuModeEdition):
    """
    § 5.3, cas 4 : le mode CREE des passages masques — un bloc vide est
    masque a l'enregistrement. Il doit donc pouvoir les RETABLIR sans
    qu'on en sorte.
    / The mode creates hidden blocks: it must be able to restore them.

    POURQUOI UN PANNEAU, ET PAS LE PLACEHOLDER DEJA RENDU

    Le placeholder « Passage masque » existe dans le champ, avec son
    bouton — mais il est `display: none` hors du mode STRUCTURE
    (decision U1, `maquette.css`). Mesure du 30 aout 2026 sur
    `/lire/29/` : hauteur 0 px, bouton 0x0, hors de l'arbre
    d'accessibilite. Depuis le mode d'edition, il est donc invisible ET
    inatteignable au clavier.

    Le panneau les rassemble AILLEURS QUE DANS LE TEXTE : le champ reste
    ce qu'on lit et corrige, et les passages retires se retrouvent la ou
    on va les chercher — dans une commande, pas au fil des lignes.
    """

    def setUp(self):
        super().setUp()
        self.texte_masque = "Pied de page répété, masqué en session."
        self.masque = ElementDocument.objects.create(
            page=self.page, ordre=2, label="text", texte=self.texte_masque,
            empreinte_contenu=empreinte_du_texte(self.texte_masque),
            masque=True,
        )

    def test_le_panneau_est_rendu_quand_un_passage_est_masque(self):
        self.assertContains(
            self._lire(), 'data-testid="panneau-des-passages-masques"',
        )

    def test_le_panneau_porte_le_COMPTE(self):
        """
        Sans le nombre, il faut deplier pour savoir s'il y a quelque
        chose — donc on ne deplie jamais.
        / Without the count, one must open it to know: so one never does.
        """
        self.assertContains(self._lire(), 'data-testid="compte-des-masques"')
        self.assertContains(self._lire(), "1 passage masqué")

    def _panneau(self, reponse):
        """
        Rend le PANNEAU SEUL, jamais la page entiere.
        / Returns the PANEL alone, never the whole page.

        Chercher « /demasquer/ » dans toute la page ne prouve rien : le
        placeholder du mode structure porte deja ce POST et deja ce
        texte. Un test qui lit la page entiere resterait vert sans
        aucun panneau.
        / The structure-mode placeholder already carries both: a
        page-wide search would stay green with no panel at all.
        """
        import re
        trouve = re.search(
            r'<details id="panneau-des-passages-masques".*?</details>',
            reponse.content.decode(), re.DOTALL,
        )
        self.assertIsNotNone(trouve, "le panneau des masqués n'est pas rendu")
        return trouve.group(0)

    def test_chaque_ligne_porte_le_POST_de_demasquage(self):
        self.assertIn(
            f"/elements/{self.masque.pk}/demasquer/",
            self._panneau(self._lire()),
        )

    def test_chaque_ligne_DIT_ce_qu_on_retablirait(self):
        """
        Un identifiant ne dit rien a personne : c'est le TEXTE qui
        permet de choisir. / An id tells nobody anything; the text does.
        """
        self.assertIn("Pied de page répété", self._panneau(self._lire()))

    def test_le_panneau_est_HORS_du_champ_modifiable(self):
        """
        Le champ est `[data-testid="blocs-elements"]`, et tout ce qui s'y
        trouve devient modifiable en mode edition. Un panneau dedans
        serait edite par megarde — et ses boutons partiraient dans la
        serialisation du § 7.1.
        / Anything inside the field becomes editable: the panel must not be.
        """
        corps = self._lire().content.decode()
        position_du_panneau = corps.index('id="panneau-des-passages-masques"')
        position_du_champ = corps.index('data-testid="blocs-elements"')
        self.assertLess(
            position_du_panneau, position_du_champ,
            "le panneau doit être rendu AVANT le champ, donc hors de lui",
        )

    def test_AUCUN_panneau_quand_rien_n_est_masque(self):
        """
        Un panneau vide serait du bruit permanent dans un mode qui doit
        laisser voir le texte. / An empty panel is permanent noise.
        """
        self.masque.delete()
        self.assertNotContains(
            self._lire(), 'data-testid="panneau-des-passages-masques"',
        )

    def test_un_simple_lecteur_n_a_PAS_le_panneau(self):
        """
        Il ne peut ni editer ni demasquer : lui montrer ce qui a ete
        retire lui donnerait un texte qu'il n'a pas a lire.
        / A reader cannot unhide, and must not see what was removed.
        """
        tiers = Utilisateur.objects.create_user(
            username="lecteur-du-panneau", password="motdepasse",
        )
        from core.models import VisibiliteDossier
        self.dossier.visibilite = VisibiliteDossier.PUBLIC
        self.dossier.save(update_fields=["visibilite"])
        self.client.force_login(tiers)
        reponse = self._lire()
        self.assertNotContains(
            reponse, 'data-testid="panneau-des-passages-masques"',
        )
        self.assertNotContains(reponse, "Pied de page répété")


class LEndpointDuPanneauDesMasques(BaseDuModeEdition):
    """
    Le panneau doit dire la VERITE APRES un enregistrement, pas
    seulement au chargement de la page.
    / The panel must tell the truth AFTER a save, not only on page load.

    POURQUOI UN ENDPOINT, ET PAS UN RECALCUL COTE CLIENT

    Le mode masque un bloc **pendant** la session : le panneau rendu au
    chargement ne le connait pas. Le recalculer en JavaScript
    demanderait de reconstruire cote client ce que le serveur sait deja
    — le texte conserve du bloc masque, son ordre, le pluriel — et cette
    copie divergerait. Le serveur rend le panneau ; le client le
    remplace.

    Cela repare AUSSI la ligne perimee : un passage demasque ailleurs
    (mode structure, ou un tiers) disparait du panneau au premier
    rafraichissement, au lieu d'y rester et d'offrir un « retablir » qui
    ecraserait le bloc vivant.
    """

    def setUp(self):
        super().setUp()
        self.chemin = "/elements/panneau_des_masques/"

    def _masquer(self, texte, ordre):
        return ElementDocument.objects.create(
            page=self.page, ordre=ordre, label="text", texte=texte,
            empreinte_contenu=empreinte_du_texte(texte), masque=True,
        )

    def test_l_endpoint_rend_le_panneau_a_jour(self):
        """
        Le bloc est masqué APRÈS le premier rendu de la page : c'est
        exactement ce que le mode fait à l'enregistrement.
        / The block is hidden AFTER the page was first rendered.
        """
        self._masquer("Un pied de page masqué en session.", 2)
        reponse = self.client.get(f"{self.chemin}?page={self.page.pk}")
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        self.assertIn('data-testid="panneau-des-passages-masques"', corps)
        self.assertIn("Un pied de page masqué en session.", corps)

    def test_le_panneau_est_VIDE_quand_plus_rien_n_est_masque(self):
        """
        Après le dernier rétablissement, le panneau doit disparaître —
        un panneau vide serait du bruit permanent.
        / After the last restore, the panel must go.
        """
        reponse = self.client.get(f"{self.chemin}?page={self.page.pk}")
        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn(
            'data-testid="panneau-des-passages-masques"',
            reponse.content.decode(),
        )

    def test_les_passages_sont_dans_l_ORDRE_DE_LECTURE(self):
        """
        L'ordre du panneau est celui du texte : c'est ce qui permet de
        reconnaître un passage sans le lire en entier.
        / The panel's order is the text's order.
        """
        # Créés dans le DÉSORDRE : c'est le seul moyen de prouver que
        # l'ordre vient du champ `ordre`, et non de la date de création.
        # / Created out of order: otherwise creation date would do.
        self._masquer("Le passage du milieu.", 5)
        self._masquer("Le passage du début.", 4)
        corps = self.client.get(f"{self.chemin}?page={self.page.pk}").content.decode()
        self.assertLess(
            corps.index("Le passage du début."),
            corps.index("Le passage du milieu."),
        )

    def test_le_compte_s_accorde_au_PLURIEL(self):
        self._masquer("Le premier masqué.", 4)
        self._masquer("Le second masqué.", 5)
        corps = self.client.get(f"{self.chemin}?page={self.page.pk}").content.decode()
        self.assertIn("2 passages masqués", corps)

    def test_un_tiers_qui_ne_peut_pas_ECRIRE_recoit_404(self):
        """
        Doctrine du 404 : le panneau montre du texte RETIRE de la
        lecture. Qui ne peut pas écrire n'a pas à savoir qu'il existe.
        / The panel shows text removed from reading: 404, never 403.
        """
        tiers = Utilisateur.objects.create_user(
            username="tiers-du-panneau", password="motdepasse",
        )
        from core.models import VisibiliteDossier
        self.dossier.visibilite = VisibiliteDossier.PUBLIC
        self.dossier.save(update_fields=["visibilite"])
        self._masquer("Un pied de page masqué.", 2)
        self.client.force_login(tiers)
        reponse = self.client.get(f"{self.chemin}?page={self.page.pk}")
        self.assertEqual(reponse.status_code, 404)
        self.assertNotIn("Un pied de page masqué.", reponse.content.decode())

    def test_une_page_INCONNUE_rend_404(self):
        self.assertEqual(
            self.client.get(f"{self.chemin}?page=999999").status_code, 404,
        )

    def test_une_page_NON_NUMERIQUE_rend_404_et_pas_500(self):
        """
        Le troisième piège de la doctrine : un paramètre qui n'est pas
        un nombre fait `filter(pk="abc")`, donc un 500.
        / A non-numeric id must be a 404, never a 500.
        """
        self.assertEqual(
            self.client.get(f"{self.chemin}?page=abc").status_code, 404,
        )


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

    def _le_script_du_mode(self):
        from pathlib import Path

        from django.conf import settings
        return (Path(settings.BASE_DIR) / "front" / "static" / "front" / "js"
                / "mode_edition.js").read_text(encoding="utf-8")

    def test_le_script_existe_et_ne_pose_aucun_ecouteur_echap(self):
        """
        Échap appartient à la cascade de `keyboard.js`. Un écouteur ici
        rejouerait le défaut payé le 29 août — avec le drawer ouvert
        par-dessus un éditeur, **un seul `Échap` fermait les deux** et
        jetait la correction en cours de frappe.
        / Escape belongs to keyboard.js's cascade.

        LA GARDE A ÉTÉ AFFINÉE LE 30 AOÛT, PAS AFFAIBLIE. Elle
        interdisait toute mention de la chaîne « Escape » ; depuis que
        les raccourcis sont une TABLE (§ 4.4), la touche doit pouvoir y
        être **déclarée** — c'est ainsi que le bandeau du mode annonce
        « Échap sortir » sans recopier une liste. Ce qui reste interdit
        est ce qui fait le dégât : **comparer** une touche à Escape,
        c'est-à-dire la traiter ici.
        / Refined, not weakened: declaring the key in the table is
        allowed; COMPARING a key to it — that is, handling it — is not.
        """
        script = self._le_script_du_mode()
        for ligne in script.splitlines():
            depouillee = ligne.replace(" ", "")
            if "==='Escape'" in depouillee or '=="Escape"' in depouillee:
                self.fail(
                    "mode_edition.js compare une touche à Échap : elle "
                    f"appartient à la cascade. Ligne : {ligne.strip()[:80]}"
                )

    def test_le_mode_ECARTE_explicitement_le_geste_de_sortie(self):
        """
        La table déclare `Échap`, donc le listener DOIT l'écarter — et
        le dire. Sans cette ligne, le jour où l'on ajoutera un cas au
        listener, la touche déclarée deviendrait une touche traitée,
        et le double `Échap` du 29 août reviendrait.
        / The table declares Escape, so the listener must skip it.
        """
        script = self._le_script_du_mode()
        depouille = script.replace(" ", "").replace("\n", "")
        self.assertIn(
            "geste==='sortir')return", depouille,
            "le listener du mode doit écarter le geste « sortir » : "
            "Échap se traite dans la cascade de keyboard.js, jamais ici",
        )
