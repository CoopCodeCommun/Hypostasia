"""
Tests de l'ElementViewSet (BR-E) — endpoints du moteur ELEMENT.
/ ElementViewSet tests (wiring phase BR-E).

LOCALISATION : hypostasis_extractor/tests/test_views_element.py

SPEC-ancrage-par-element-v2 § 7 (verrou par ligne) et § 8.4 (endpoints,
un serializer par action) + cahier BR-E : corriger, scinder,
fusionner_avec_le_suivant, masquer, demasquer. Les gardes des services
(analyse en cours, synthese figee qui cite) remontent en 409 avec le
message FALC de l'exception — jamais un 500.
/ Element endpoints; service guards surface as 409 with FALC messages.
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Configuration,
    ElementDocument,
    MoteurDePage,
    Page,
    empreinte_du_texte,
)
from hypostasis_extractor.models import (
    AncrageExtraction,
    ExtractedEntity,
    ExtractionJob,
)

Utilisateur = get_user_model()


class BaseElementViewSetTest(TestCase):
    """Socle : une page ELEMENT, son proprietaire, un tiers."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprietaire-el", password="motdepasse",
        )
        self.tiers = Utilisateur.objects.create_user(
            username="tiers-el", password="motdepasse",
        )
        self.page = Page.objects.create(
            url="http://exemple.local/bre-page",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-bre",
            owner=self.proprietaire, moteur=MoteurDePage.ELEMENT,
        )
        self.client.force_login(self.proprietaire)

    def _element(self, texte, ordre=0, masque=False):
        return ElementDocument.objects.create(
            page=self.page, ordre=ordre, label="text", texte=texte,
            empreinte_contenu=empreinte_du_texte(texte), masque=masque,
        )

    def _portion(self, element, debut, fin):
        job = ExtractionJob.objects.create(page=self.page, status="completed")
        extraction = ExtractedEntity.objects.create(
            job=job, extraction_class="principe",
            extraction_text=element.texte[debut:fin],
            start_char=debut, end_char=fin,
        )
        return AncrageExtraction.objects.create(
            extraction=extraction, element=element,
            ordre_dans_extraction=0,
            debut_dans_element=debut, fin_dans_element=fin,
        )


class CorrectionDElementTest(BaseElementViewSetTest):
    """POST /elements/<pk>/corriger/ — texte + reconciliation."""

    def test_corriger_ecrit_le_texte_et_reconcilie(self):
        element = self._element("Le jugement des persones compte.")
        portion = self._portion(element, 3, 11)  # « jugement »

        reponse = self.client.post(
            f"/elements/{element.pk}/corriger/",
            {"texte": "Le jugement des personnes compte."},
        )

        self.assertEqual(reponse.status_code, 200)
        element.refresh_from_db()
        self.assertEqual(element.texte, "Le jugement des personnes compte.")
        self.assertEqual(
            element.empreinte_contenu,
            empreinte_du_texte("Le jugement des personnes compte."),
        )
        # La portion « jugement » n'a pas bouge : elle reste ancree.
        # / The "jugement" portion did not move: still anchored.
        portion.refresh_from_db()
        self.assertEqual(portion.debut_dans_element, 3)

        # Le client est prevenu : toast + rechargement de la lecture.
        # / The client gets a toast and a reading reload.
        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertIn("showToast", declencheurs)
        self.assertEqual(
            str(declencheurs["lectureReload"]["page_id"]), str(self.page.pk),
        )

    def test_corriger_journalise_dans_page_edit(self):
        from core.models import PageEdit

        element = self._element("Texte avant.")
        self.client.post(
            f"/elements/{element.pk}/corriger/", {"texte": "Texte après."},
        )

        edition = PageEdit.objects.get(page=self.page)
        self.assertEqual(edition.user, self.proprietaire)
        self.assertEqual(edition.donnees_avant["texte"], "Texte avant.")
        self.assertEqual(edition.donnees_apres["texte"], "Texte après.")

    def test_corriger_refuse_un_texte_vide(self):
        element = self._element("Du texte.")

        reponse = self.client.post(
            f"/elements/{element.pk}/corriger/", {"texte": "   "},
        )

        self.assertEqual(reponse.status_code, 400)
        element.refresh_from_db()
        self.assertEqual(element.texte, "Du texte.")

    def test_corriger_par_un_tiers_est_refuse(self):
        element = self._element("Du texte.")
        self.client.force_login(self.tiers)

        reponse = self.client.post(
            f"/elements/{element.pk}/corriger/", {"texte": "Sabotage."},
        )

        self.assertEqual(reponse.status_code, 403)
        element.refresh_from_db()
        self.assertEqual(element.texte, "Du texte.")

    def test_corriger_pendant_une_analyse_repond_409(self):
        element = self._element("Du texte.")
        ExtractionJob.objects.create(page=self.page, status="processing")

        reponse = self.client.post(
            f"/elements/{element.pk}/corriger/", {"texte": "Autre texte."},
        )

        self.assertEqual(reponse.status_code, 409)
        # Le message FALC explique, il n'accuse pas.
        # / The FALC message explains.
        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertIn("analyse", declencheurs["showToast"]["message"].lower())


class ScissionDElementTest(BaseElementViewSetTest):
    """POST /elements/<pk>/scinder/ — coupe en deux."""

    def test_scinder_coupe_l_element_en_deux(self):
        element = self._element("Premiere phrase. Seconde phrase.")

        reponse = self.client.post(
            f"/elements/{element.pk}/scinder/", {"position_de_coupe": 17},
        )

        self.assertEqual(reponse.status_code, 200)
        elements = list(self.page.elements.order_by("ordre"))
        self.assertEqual(len(elements), 2)
        self.assertEqual(elements[0].texte, "Premiere phrase. ")
        self.assertEqual(elements[1].texte, "Seconde phrase.")

    def test_scinder_hors_bornes_repond_400(self):
        element = self._element("Court.")

        reponse = self.client.post(
            f"/elements/{element.pk}/scinder/", {"position_de_coupe": 999},
        )

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self.page.elements.count(), 1)

    def test_scinder_un_element_cite_par_une_synthese_figee_repond_409(self):
        from core.models import SourceLink, TypeDeNote, TypeLien

        element = self._element("Un passage cite par une synthese.")
        portion = self._portion(element, 3, 10)

        # Une synthese dirigee (acte fige) cite cette extraction.
        # / A frozen directed synthesis cites this extraction.
        note_de_synthese = Page.objects.create(
            url="http://exemple.local/bre-synthese",
            html_original="<p>s</p>", html_readability="<p>s</p>",
            text_readability="synthese", content_hash="hash-bre-syn",
            owner=self.proprietaire, type_de_note=TypeDeNote.SYNTHESE,
        )
        SourceLink.objects.create(
            page_cible=note_de_synthese,
            start_char_cible=0, end_char_cible=7,
            page_source=self.page,
            extraction_source=portion.extraction,
            type_lien=TypeLien.CITE,
        )

        reponse = self.client.post(
            f"/elements/{element.pk}/scinder/", {"position_de_coupe": 10},
        )

        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(self.page.elements.count(), 1)


class FusionDElementsTest(BaseElementViewSetTest):
    """POST /elements/<pk>/fusionner_avec_le_suivant/."""

    def test_fusionner_recolle_deux_elements_adjacents(self):
        premier = self._element("Debut de phrase", ordre=0)
        self._element("coupee en deux.", ordre=1)

        reponse = self.client.post(
            f"/elements/{premier.pk}/fusionner_avec_le_suivant/",
        )

        self.assertEqual(reponse.status_code, 200)
        # La fusion cree un NOUVEL element et supprime les deux
        # originaux (contrat du service). / The merge creates a NEW
        # element; both originals are deleted.
        survivant = self.page.elements.get()
        self.assertNotEqual(survivant.pk, premier.pk)
        self.assertIn("Debut de phrase", survivant.texte)
        self.assertIn("coupee en deux.", survivant.texte)

    def test_fusionner_le_dernier_element_repond_400(self):
        dernier = self._element("Tout seul.", ordre=0)

        reponse = self.client.post(
            f"/elements/{dernier.pk}/fusionner_avec_le_suivant/",
        )

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self.page.elements.count(), 1)


class MasquageDElementTest(BaseElementViewSetTest):
    """POST /elements/<pk>/masquer/ et /demasquer/."""

    def test_masquer_puis_demasquer_rattache_les_portions(self):
        element = self._element("Un passage avec une portion.")
        portion = self._portion(element, 3, 10)

        reponse = self.client.post(
            f"/elements/{element.pk}/masquer/",
            {"justification": "Pied de page répété"},
        )
        self.assertEqual(reponse.status_code, 200)
        element.refresh_from_db()
        portion.refresh_from_db()
        self.assertTrue(element.masque)
        self.assertEqual(portion.etat_ancrage, "detachee")

        reponse = self.client.post(f"/elements/{element.pk}/demasquer/")
        self.assertEqual(reponse.status_code, 200)
        element.refresh_from_db()
        portion.refresh_from_db()
        self.assertFalse(element.masque)
        self.assertNotEqual(portion.etat_ancrage, "detachee")

    def test_masquer_par_un_tiers_est_refuse(self):
        element = self._element("Du texte.")
        self.client.force_login(self.tiers)

        reponse = self.client.post(f"/elements/{element.pk}/masquer/")

        self.assertEqual(reponse.status_code, 403)
        element.refresh_from_db()
        self.assertFalse(element.masque)

    def test_sans_authentification_c_est_refuse(self):
        element = self._element("Du texte.")
        self.client.logout()

        reponse = self.client.post(f"/elements/{element.pk}/masquer/")

        self.assertIn(reponse.status_code, [302, 401, 403])
        element.refresh_from_db()
        self.assertFalse(element.masque)


class CorrectifsRelectureBRETest(BaseElementViewSetTest):
    """
    Correctifs de la relecture adverse BR-E (10 aout).
    / Fixes from the BR-E adversarial review.
    """

    def test_une_justification_trop_longue_est_refusee_pas_avalee(self):
        # Defaut n°2 : la justification > 500 caracteres etait jetee en
        # silence — l'element se masquait avec un journal vide.
        # / An over-long justification was silently dropped.
        element = self._element("Du texte.")

        reponse = self.client.post(
            f"/elements/{element.pk}/masquer/",
            {"justification": "x" * 600},
        )

        self.assertEqual(reponse.status_code, 400)
        element.refresh_from_db()
        self.assertFalse(element.masque)

    def test_la_justification_de_scission_passe_par_le_serializer(self):
        # Defaut n°3 : scinder prenait la justification en brut ; un
        # POST JSON avec un dict filait jusqu'a psycopg -> 500.
        # / Split took the raw justification; a dict crashed psycopg.
        element = self._element("Premiere phrase. Seconde phrase.")

        reponse = self.client.post(
            f"/elements/{element.pk}/scinder/",
            data=json.dumps({
                "position_de_coupe": 17,
                "justification": {"a": 1},
            }),
            content_type="application/json",
        )

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self.page.elements.count(), 1)

    def test_corriger_sans_changement_ne_journalise_pas(self):
        # Defaut n°5 : re-soumettre le meme texte creait un PageEdit
        # avant == apres. / Same-text resubmit polluted the journal.
        from core.models import PageEdit

        element = self._element("Texte inchange.")

        reponse = self.client.post(
            f"/elements/{element.pk}/corriger/",
            {"texte": "Texte inchange."},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(PageEdit.objects.filter(page=self.page).count(), 0)

    def test_le_message_de_blocage_par_analyse_est_falc(self):
        # Defaut n°4 : le toast montrait le pk de la page et « job(s) ».
        # Le message doit expliquer sans jargon ni identifiant interne.
        # / The toast leaked internal ids and jargon.
        element = self._element("Du texte.")
        ExtractionJob.objects.create(page=self.page, status="processing")

        reponse = self.client.post(
            f"/elements/{element.pk}/corriger/", {"texte": "Autre."},
        )

        self.assertEqual(reponse.status_code, 409)
        message = json.loads(reponse["HX-Trigger"])["showToast"]["message"]
        self.assertNotIn("job", message.lower())
        self.assertNotIn(str(self.page.pk), message)
        self.assertIn("analyse", message.lower())

    def test_le_journal_porte_l_identifiant_stable(self):
        # Defaut n°9 : « Élément 3 » ne veut plus rien dire apres une
        # renumerotation ; l'identifiant stable, si.
        # / The journal now carries the stable identifier.
        from core.models import PageEdit

        element = self._element("Texte avant.")
        self.client.post(
            f"/elements/{element.pk}/corriger/", {"texte": "Texte après."},
        )

        edition = PageEdit.objects.get(page=self.page)
        self.assertEqual(
            edition.donnees_apres.get("identifiant_stable"),
            str(element.identifiant_stable),
        )


class FormulairesDElementTest(BaseElementViewSetTest):
    """
    GET /elements/<pk>/formulaire_correction|formulaire_scission/ (U1).

    Les boutons de la lecture ouvrent des formulaires RENDUS PAR LE
    SERVEUR (stack du depot : HTML partiel, jamais de JSON d'UI). Le
    droit est le MEME que pour agir : qui ne peut pas ecrire ne recoit
    pas le formulaire.
    / The reading buttons fetch server-rendered forms; same write rule
    as the actions themselves.
    """

    def test_le_formulaire_de_correction_porte_le_texte_de_l_element(self):
        element = self._element("Le texte a corriger.")

        reponse = self.client.get(
            f"/elements/{element.pk}/formulaire_correction/",
        )

        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Le texte a corriger.", contenu)
        self.assertIn(f"/elements/{element.pk}/corriger/", contenu)

    def test_le_formulaire_de_correction_pour_un_tiers_est_refuse(self):
        element = self._element("Le texte a corriger.")
        self.client.force_login(self.tiers)

        reponse = self.client.get(
            f"/elements/{element.pk}/formulaire_correction/",
        )

        self.assertEqual(reponse.status_code, 403)

    def test_le_formulaire_de_scission_permet_de_placer_le_curseur(self):
        element = self._element("Premiere phrase. Seconde phrase.")

        reponse = self.client.get(
            f"/elements/{element.pk}/formulaire_scission/",
        )

        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Premiere phrase. Seconde phrase.", contenu)
        self.assertIn(f"/elements/{element.pk}/scinder/", contenu)
        # La position de coupe est portee par un champ dedie, rempli au
        # moment de l'envoi depuis la position du curseur.
        # / The cut position travels in a dedicated field.
        self.assertIn('name="position_de_coupe"', contenu)

    def test_le_formulaire_de_scission_pour_un_tiers_est_refuse(self):
        element = self._element("Premiere phrase. Seconde phrase.")
        self.client.force_login(self.tiers)

        reponse = self.client.get(
            f"/elements/{element.pk}/formulaire_scission/",
        )

        self.assertEqual(reponse.status_code, 403)


class CorrectifsRelectureU1Test(BaseElementViewSetTest):
    """
    Correctifs de la relecture adverse U1 (10 aout), cote endpoints.
    / U1 adversarial-review fixes, endpoint side.
    """

    def _message_du_toast(self, reponse):
        return json.loads(reponse["HX-Trigger"])["showToast"]["message"]

    def test_le_formulaire_de_scission_prefixe_le_textarea_d_un_retour(self):
        # H1 : le parseur HTML avale le premier retour a la ligne apres
        # <textarea> — sans prefixe, un texte commencant par \n decale
        # TOUS les offsets d'un cran. / The parser eats the first
        # newline after <textarea>; we prepend one on purpose.
        element = self._element("Premiere phrase. Seconde phrase.")
        reponse = self.client.get(
            f"/elements/{element.pk}/formulaire_scission/",
        )
        self.assertIn(
            ">\nPremiere phrase. Seconde phrase.</textarea>",
            reponse.content.decode(),
        )

    def test_le_formulaire_de_correction_prefixe_le_textarea_d_un_retour(self):
        element = self._element("Le texte a corriger.")
        reponse = self.client.get(
            f"/elements/{element.pk}/formulaire_correction/",
        )
        self.assertIn(
            ">\nLe texte a corriger.</textarea>",
            reponse.content.decode(),
        )

    def test_le_formulaire_de_scission_porte_l_empreinte_du_texte(self):
        # H2 : la coupe s'applique au texte AFFICHE — l'empreinte
        # voyage avec le formulaire pour le prouver a l'envoi.
        # / The split form carries the displayed text's fingerprint.
        element = self._element("Premiere phrase. Seconde phrase.")
        reponse = self.client.get(
            f"/elements/{element.pk}/formulaire_scission/",
        )
        contenu = reponse.content.decode()
        self.assertIn('name="empreinte_du_texte"', contenu)
        self.assertIn(element.empreinte_contenu, contenu)

    def test_scinder_avec_une_empreinte_perimee_repond_409(self):
        # H2 : le texte a change entre l'ouverture du formulaire et
        # l'envoi — la coupe serait posee sur un autre texte.
        # / Stale fingerprint means the text changed meanwhile: 409.
        element = self._element("Premiere phrase. Seconde phrase.")
        reponse = self.client.post(
            f"/elements/{element.pk}/scinder/",
            {"position_de_coupe": 17, "empreinte_du_texte": "perimee"},
        )
        self.assertEqual(reponse.status_code, 409)
        self.assertIn("modifié entre-temps", self._message_du_toast(reponse))
        # Rien n'a ete coupe. / Nothing was split.
        self.assertEqual(
            ElementDocument.objects.filter(page=self.page).count(), 1,
        )

    def test_scinder_avec_la_bonne_empreinte_coupe(self):
        element = self._element("Premiere phrase. Seconde phrase.")
        reponse = self.client.post(
            f"/elements/{element.pk}/scinder/",
            {"position_de_coupe": 17,
             "empreinte_du_texte": element.empreinte_contenu},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            ElementDocument.objects.filter(page=self.page).count(), 2,
        )

    def test_scinder_sans_position_parle_du_curseur(self):
        # M6 : le message du 400 doit dire QUOI FAIRE (placer le
        # curseur), pas parler de « position entiere obligatoire ».
        # / The 400 message must say what to do, in plain words.
        element = self._element("Premiere phrase. Seconde phrase.")
        reponse = self.client.post(
            f"/elements/{element.pk}/scinder/", {},
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("curseur", self._message_du_toast(reponse).lower())

    def test_scinder_au_bord_du_texte_a_un_message_falc(self):
        # M6 : jamais str(erreur) brut (jargon, sans accents) vers
        # l'utilisateur. / Never raw str(error) to the user.
        element = self._element("Petit texte.")
        reponse = self.client.post(
            f"/elements/{element.pk}/scinder/",
            {"position_de_coupe": len("Petit texte."),
             "empreinte_du_texte": element.empreinte_contenu},
        )
        self.assertEqual(reponse.status_code, 400)
        message = self._message_du_toast(reponse)
        self.assertNotIn("Position de coupe", message)
        self.assertIn("couper", message.lower())

    def test_fusionner_vers_un_masque_a_un_message_falc(self):
        # M6/M8 : si le bouton a quand meme ete envoye (vieux rendu),
        # le refus nomme le masquage en francais simple.
        # / Merging into a hidden element gets a plain-words refusal.
        element = self._element("Visible.", ordre=0)
        self._element("Masque.", ordre=1, masque=True)
        reponse = self.client.post(
            f"/elements/{element.pk}/fusionner_avec_le_suivant/", {},
        )
        self.assertEqual(reponse.status_code, 400)
        message = self._message_du_toast(reponse)
        self.assertIn("masqué", message)
        self.assertNotIn("element masque avec un element visible", message)

    def test_un_element_disparu_repond_un_toast_et_recharge(self):
        # M4 : en collaboration, les pk meurent a chaque scission ou
        # fusion d'autrui. Le 404 doit porter un toast FALC et
        # declencher le rechargement — jamais la page 404 brute dans un
        # SweetAlert. / Dead pks get a FALC toast + reload trigger.
        reponse = self.client.post("/elements/999999/masquer/", {})
        self.assertEqual(reponse.status_code, 404)
        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertIn("lectureReload", declencheurs)
        self.assertIn("recharg", declencheurs["showToast"]["message"].lower())
