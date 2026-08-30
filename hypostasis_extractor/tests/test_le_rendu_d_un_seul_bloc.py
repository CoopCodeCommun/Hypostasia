"""
Tests du rendu d'UN SEUL bloc — le swap cible qui remplace lectureReload.
/ Tests for rendering ONE block: the targeted swap replacing lectureReload.

LOCALISATION : hypostasis_extractor/tests/test_le_rendu_d_un_seul_bloc.py

SPEC-edition-par-blocs-et-stenotypie.md § 11, point 3.

POURQUOI CET ENDPOINT EXISTE

Aujourd'hui, toute operation d'element repond avec un HX-Trigger
`lectureReload`, et le front refait `zoneLecture.innerHTML = ...`
(hypostasia.js:494-512). Il remplace donc TOUTE la zone de lecture pour
un bloc qui a change. Deux consequences : le defilement et le focus sont
perdus a chaque geste, et une session d'edition en cours est DETRUITE.

LE TEST QUI COMPTE EST `test_le_bloc_rendu_seul_est_identique_a_celui_de_la_page`.
Un bloc echange doit etre au caractere pres celui que la page entiere
aurait rendu. Sinon les deux rendus derivent, et le bloc echange finit par
ne plus ressembler a ses voisins — sans que rien ne le signale.
"""

import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AppartenancePageDossier,
    Dossier,
    ElementDocument,
    Page,
    VisibiliteDossier,
    empreinte_du_texte,
)

Utilisateur = get_user_model()


def sans_jeton_csrf(html):
    """
    Remplace le jeton CSRF par une constante.
    / Replaces the CSRF token with a constant.

    Il change a chaque requete : deux rendus du meme bloc different donc
    toujours par lui. Ce qu'on compare, c'est le MARKUP.
    """
    return re.sub(r'"X-CSRFToken": "[^"]*"', '"X-CSRFToken": "JETON"', html)


class BaseDuRenduDUnBloc(TestCase):
    """Socle : une page a trois blocs, son proprietaire, un tiers."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprietaire-bloc", password="motdepasse",
        )
        self.tiers = Utilisateur.objects.create_user(
            username="tiers-bloc", password="motdepasse",
        )
        self.dossier = Dossier.objects.create(
            name="Carnet du rendu", owner=self.proprietaire,
        )
        self.page = Page.objects.create(
            url="http://exemple.local/rendu-d-un-bloc",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-rendu-bloc",
            owner=self.proprietaire, dossier=self.dossier,
        )
        # Le rattachement a un carnet passe par AppartenancePageDossier,
        # PAS par le champ `Page.dossier` : c'est cette table que lit
        # `_dossiers_contenant_la_page`, donc c'est elle qui decide de
        # l'acces. Poser le seul FK laisserait la note « sans carnet ».
        # / Membership goes through the join table, not the FK.
        AppartenancePageDossier.objects.create(
            page=self.page, dossier=self.dossier,
        )
        self.premier = self._element("Le premier passage de la note.", 0)
        self.titre = self._element("Un titre de section", 1, label="section_header")
        self.dernier = self._element("Le dernier passage de la note.", 2)
        self.client.force_login(self.proprietaire)

    def _element(self, texte, ordre, label="text", masque=False):
        return ElementDocument.objects.create(
            page=self.page, ordre=ordre, label=label, texte=texte,
            empreinte_contenu=empreinte_du_texte(texte), masque=masque,
        )

    def _bloc_extrait_de_la_page(self, element):
        """
        Rend la page entiere, et en decoupe le bloc de cet element.
        / Renders the whole page and cuts out this element's block.
        """
        from front.services.rendu_elements import construire_les_blocs_de_lecture
        from django.template.loader import render_to_string

        blocs = construire_les_blocs_de_lecture(self.page)
        vise = [b for b in blocs if b["element"].pk == element.pk]
        return render_to_string(
            "front/includes/_un_bloc_element.html",
            {"bloc": vise[0], "la_note_est_modifiable": True},
        )


class LeBlocRenduSeul(BaseDuRenduDUnBloc):
    """L'endpoint rend un bloc, et le rend comme la page le rendrait."""

    def test_le_bloc_rendu_seul_est_identique_a_celui_de_la_page(self):
        """
        LE test du chantier. Le bloc servi seul doit etre au caractere
        pres celui que la page entiere rend pour le meme element.
        / The block served alone must match the one the full page renders.
        """
        reponse = self.client.get(f"/elements/{self.titre.pk}/bloc/")
        self.assertEqual(reponse.status_code, 200)
        rendu_seul = sans_jeton_csrf(reponse.content.decode())
        rendu_dans_la_page = sans_jeton_csrf(
            self._bloc_extrait_de_la_page(self.titre)
        )
        self.assertEqual(rendu_seul.strip(), rendu_dans_la_page.strip())

    def test_le_bloc_porte_son_identifiant_stable(self):
        """
        Le contrat du § 7.1 designe un bloc par son `identifiant_stable`,
        jamais par son pk. Aucun gabarit ne le portait.
        / The § 7.1 contract identifies a block by its stable id.
        """
        reponse = self.client.get(f"/elements/{self.premier.pk}/bloc/")
        self.assertContains(reponse, str(self.premier.identifiant_stable))

    def test_le_bloc_rendu_ne_porte_pas_le_conteneur_de_la_page(self):
        """
        On rend UN bloc, pas la liste : le conteneur `blocs-elements`
        appartient a la page. L'inclure ferait un conteneur imbrique a
        chaque swap. / One block, not the list wrapper.
        """
        reponse = self.client.get(f"/elements/{self.premier.pk}/bloc/")
        self.assertNotContains(reponse, 'data-testid="blocs-elements"')

    def test_un_element_inconnu_rend_404(self):
        """Doctrine du projet : 404, jamais 403. / 404, never 403."""
        reponse = self.client.get("/elements/999999/bloc/")
        self.assertEqual(reponse.status_code, 404)

    def test_un_tiers_sans_droit_de_lecture_recoit_404(self):
        """
        Le perimetre de lecture vaut ici comme ailleurs, et il rend 404 —
        un 403 dirait au tiers que la note existe.
        / The reading scope applies, and it answers 404.
        """
        self.client.force_login(self.tiers)
        reponse = self.client.get(f"/elements/{self.premier.pk}/bloc/")
        self.assertEqual(reponse.status_code, 404)

    def test_un_anonyme_recoit_404_sur_une_note_privee(self):
        """/ An anonymous visitor gets 404 on a private note."""
        self.client.logout()
        reponse = self.client.get(f"/elements/{self.premier.pk}/bloc/")
        self.assertEqual(reponse.status_code, 404)

    def test_un_anonyme_lit_le_bloc_d_un_carnet_public(self):
        """
        Un carnet PUBLIC se lit sans compte — la regle du projet, et
        l'ecran de lecture l'applique deja. Cet endpoint rend un morceau
        de cette page : il doit s'ouvrir exactement autant, sinon
        l'echange de bloc casserait chez le lecteur anonyme d'une note
        qu'il a sous les yeux.
        / A public notebook is readable without an account; this endpoint
        must open exactly as much as the page it serves a piece of.
        """
        self.dossier.visibilite = VisibiliteDossier.PUBLIC
        self.dossier.save(update_fields=["visibilite"])
        self.client.logout()
        reponse = self.client.get(f"/elements/{self.premier.pk}/bloc/")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Le premier passage")

    def test_un_anonyme_sur_un_carnet_public_n_a_PAS_les_boutons(self):
        """
        Lire n'est pas ecrire. Le bloc servi a un anonyme ne porte aucun
        bouton d'operation, meme sur un carnet public.
        / Reading is not writing: no action buttons for an anonymous visitor.
        """
        self.dossier.visibilite = VisibiliteDossier.PUBLIC
        self.dossier.save(update_fields=["visibilite"])
        self.client.logout()
        reponse = self.client.get(f"/elements/{self.premier.pk}/bloc/")
        self.assertNotContains(reponse, "/corriger/")
        self.assertNotContains(reponse, "/masquer/")


class LeBlocMasque(BaseDuRenduDUnBloc):
    """Un element masque rend son placeholder, pas un bloc de texte."""

    def test_un_element_masque_rend_son_placeholder_pour_qui_peut_ecrire(self):
        """
        / A hidden element renders its placeholder for a writer.
        """
        self.premier.masque = True
        self.premier.save(update_fields=["masque"])
        reponse = self.client.get(f"/elements/{self.premier.pk}/bloc/")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "element-masque")
        self.assertContains(reponse, "demasquer")


class LeSwapCibleRemplaceLeRechargement(BaseDuRenduDUnBloc):
    """
    Les gestes de LIGNE renvoient le bloc, jamais un rechargement.
    / Line-level gestures return the block, never a full reload.

    Les gestes de PAGE — scinder, fusionner — le gardent : ils
    renumerotent, donc plusieurs blocs changent d'un coup.
    """

    def _declencheurs(self, reponse):
        import json as json_module
        return json_module.loads(reponse["HX-Trigger"])

    def test_corriger_renvoie_le_bloc_en_swap_oob(self):
        """
        / Correcting returns the block as an out-of-band swap.
        """
        reponse = self.client.post(
            f"/elements/{self.premier.pk}/corriger/",
            {"texte": "Le premier passage, corrigé."},
        )
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        self.assertIn("hx-swap-oob", corps)
        self.assertIn(f'id="bloc-{self.premier.identifiant_stable}"', corps)
        self.assertIn("corrigé", corps)

    def test_corriger_ne_declenche_PLUS_de_rechargement(self):
        """
        LE test du chantier. `lectureReload` refait toute la zone de
        lecture : le defilement, le focus et — demain — la session
        d'edition y passent.
        / The point of the whole thing: no more full reload.
        """
        reponse = self.client.post(
            f"/elements/{self.premier.pk}/corriger/",
            {"texte": "Un autre texte."},
        )
        declencheurs = self._declencheurs(reponse)
        self.assertNotIn("lectureReload", declencheurs)
        self.assertIn("showToast", declencheurs)

    def test_le_bloc_renvoye_par_corriger_est_celui_que_la_page_rendrait(self):
        """
        Meme garantie que pour l'endpoint : le bloc echange ne derive
        pas de ses voisins.
        / The swapped block does not drift from the page rendering.
        """
        self.client.post(
            f"/elements/{self.premier.pk}/corriger/",
            {"texte": "Texte de contrôle."},
        )
        reponse = self.client.get(f"/elements/{self.premier.pk}/bloc/")
        self.premier.refresh_from_db()
        rendu_endpoint = sans_jeton_csrf(reponse.content.decode())
        rendu_page = sans_jeton_csrf(self._bloc_extrait_de_la_page(self.premier))
        # L'endpoint ne pose pas l'attribut de swap ; on le retire du
        # comparatif, c'est la seule difference attendue.
        # / The endpoint does not set the swap attribute.
        self.assertEqual(rendu_endpoint.strip(), rendu_page.strip())

    def test_masquer_renvoie_le_placeholder_sans_rechargement(self):
        """
        / Hiding returns the placeholder, with no reload.
        """
        reponse = self.client.post(f"/elements/{self.premier.pk}/masquer/", {})
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        self.assertIn("hx-swap-oob", corps)
        self.assertIn(f'id="bloc-{self.premier.identifiant_stable}"', corps)
        self.assertIn("element-masque", corps)
        self.assertNotIn("lectureReload", self._declencheurs(reponse))

    def test_demasquer_renvoie_le_bloc_sans_rechargement(self):
        """/ Un-hiding returns the block, with no reload."""
        self.premier.masque = True
        self.premier.save(update_fields=["masque"])
        reponse = self.client.post(f"/elements/{self.premier.pk}/demasquer/", {})
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        self.assertIn(f'id="bloc-{self.premier.identifiant_stable}"', corps)
        self.assertNotIn("lectureReload", self._declencheurs(reponse))

    def test_scinder_GARDE_le_rechargement(self):
        """
        Scinder renumerote la page : plusieurs blocs changent d'ordre, et
        deux elements neufs remplacent l'ancien. Un swap d'un seul bloc
        ne peut pas le montrer.
        / Splitting renumbers the page: the full reload stays.
        """
        reponse = self.client.post(
            f"/elements/{self.premier.pk}/scinder/",
            {"position_de_coupe": 3},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("lectureReload", self._declencheurs(reponse))

    def test_fusionner_GARDE_le_rechargement(self):
        """/ Merging renumbers too: the full reload stays."""
        reponse = self.client.post(
            f"/elements/{self.premier.pk}/fusionner_avec_le_suivant/", {},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("lectureReload", self._declencheurs(reponse))

    def test_un_pk_mort_GARDE_le_rechargement(self):
        """
        Un pk mort veut dire qu'un tiers a restructure la page : la vue
        du client est perimee pour de bon, et la recharger est juste.
        C'est le seul cas ou le rechargement reste le bon geste.
        / A dead pk means a third party restructured the page.
        """
        reponse = self.client.post("/elements/999999/masquer/", {})
        self.assertEqual(reponse.status_code, 404)
        self.assertIn("lectureReload", self._declencheurs(reponse))
