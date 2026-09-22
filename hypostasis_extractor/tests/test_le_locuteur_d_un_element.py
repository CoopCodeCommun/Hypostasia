"""
Corriger le LOCUTEUR d'un tour de parole, sur le moteur ELEMENT.
/ Fixing a turn's SPEAKER, on the ELEMENT engine.

LOCALISATION : hypostasis_extractor/tests/test_le_locuteur_d_un_element.py

SPEC-edition-par-blocs-et-stenotypie.md § 6.2.

POURQUOI CE GESTE A DU ETRE REECRIT

`PageViewSet.renommer_locuteur` existe depuis PHASE-27a et porte les
trois portees — mais il REFUSE EN 409 toute note qui porte des elements
(`front/views.py`), et le moteur ELEMENT est le seul moteur depuis le
10 aout 2026. Le geste n'existait donc pour AUCUNE note reelle.

Il refuse pour une bonne raison, qu'il enonce lui-meme : un BLOC groupe
les segments consecutifs d'un meme locuteur, alors que l'ingestion cree
UN ELEMENT PAR SEGMENT et saute les vides. « bloc N = element ordre N »
n'est vrai que sur un corpus qui alterne les locuteurs. Le geste natif
vise donc l'element PAR SON PK, jamais par un index.

CE QUE CE GESTE NE TOUCHE PAS, ET C'EST L'ESSENTIEL : ni le texte, ni
l'empreinte, ni l'ordre, ni les ancres. Il ecrit une seule cle de
`provenance`. C'est pourquoi il ne passe pas par la reconciliation.
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AppartenancePageDossier,
    Dossier,
    ElementDocument,
    Page,
    PageEdit,
    empreinte_du_texte,
)

Utilisateur = get_user_model()


class BaseDuLocuteur(TestCase):
    """
    Une transcription de cinq tours, deux locuteurs, dans l'ordre
    A B A B — plus un tour SANS locuteur, celui qu'une fusion de deux
    voix divergentes laisse derriere elle.
    / Five turns, two speakers, plus one with no speaker at all.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprietaire-locuteur", password="motdepasse",
        )
        self.tiers = Utilisateur.objects.create_user(
            username="tiers-locuteur", password="motdepasse",
        )
        self.dossier = Dossier.objects.create(
            name="Carnet du locuteur", owner=self.proprietaire,
        )
        self.page = Page.objects.create(
            url="http://exemple.local/la-transcription",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-locuteur",
            owner=self.proprietaire, dossier=self.dossier,
            source_type="audio",
        )
        AppartenancePageDossier.objects.create(
            page=self.page, dossier=self.dossier,
        )
        self.tours = [
            self._tour("Bonjour à tous.", 0, "SPEAKER_00", 0.0, 2.0),
            self._tour("Merci de m'accueillir.", 1, "SPEAKER_01", 2.0, 4.0),
            self._tour("Revenons au sujet.", 2, "SPEAKER_00", 4.0, 6.0),
            self._tour("Je ne suis pas d'accord.", 3, "SPEAKER_01", 6.0, 8.0),
            self._tour("Sans voix attribuée.", 4, None, 8.0, 10.0),
        ]
        self.client.force_login(self.proprietaire)

    def _tour(self, texte, ordre, locuteur, debut, fin):
        provenance = {"debut": debut, "fin": fin}
        if locuteur is not None:
            provenance["locuteur"] = locuteur
        return ElementDocument.objects.create(
            page=self.page, ordre=ordre, label="text", texte=texte,
            empreinte_contenu=empreinte_du_texte(texte),
            provenance=provenance,
        )

    def _renommer(self, element, nom, portee="ce_bloc_seul"):
        return self.client.post(
            f"/elements/{element.pk}/renommer_le_locuteur/",
            data=json.dumps({"nouveau_locuteur": nom, "portee": portee}),
            content_type="application/json",
        )

    def _locuteurs(self):
        """Les locuteurs de la page, dans l'ordre de lecture."""
        return [
            (element.provenance or {}).get("locuteur")
            for element in ElementDocument.objects.filter(
                page=self.page,
            ).order_by("ordre")
        ]


class LesTroisPortees(BaseDuLocuteur):
    """§ 6.2 : `ce_bloc_seul` EST la réattribution d'un tour."""

    def test_CE_BLOC_SEUL_ne_touche_que_lui(self):
        reponse = self._renommer(self.tours[0], "Paul")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            self._locuteurs(),
            ["Paul", "SPEAKER_01", "SPEAKER_00", "SPEAKER_01", None],
        )

    def test_CE_BLOC_ET_SUIVANTS_ne_prend_que_LE_MEME_locuteur(self):
        """
        « À partir d'ici, SPEAKER_00 c'est Paul. » Prendre TOUS les
        blocs suivants écraserait la voix de l'autre — c'est-à-dire
        détruirait la diarisation au lieu de la corriger.
        / Only the SAME speaker's later turns, never everyone's.
        """
        reponse = self._renommer(
            self.tours[0], "Paul", portee="ce_bloc_et_suivants",
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            self._locuteurs(),
            ["Paul", "SPEAKER_01", "Paul", "SPEAKER_01", None],
        )

    def test_TOUS_prend_aussi_ce_qui_PRECEDE(self):
        """
        La portée « tous » part du milieu et remonte : sinon elle ne
        serait qu'un « et suivants » déguisé.
        / "All" reaches backwards too, or it is just "and following".
        """
        reponse = self._renommer(self.tours[2], "Paul", portee="tous")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            self._locuteurs(),
            ["Paul", "SPEAKER_01", "Paul", "SPEAKER_01", None],
        )

    def test_le_compte_rendu_dit_COMBIEN_de_tours_ont_change(self):
        reponse = self._renommer(self.tours[0], "Paul", portee="tous")
        message = json.loads(reponse["HX-Trigger"])["showToast"]["message"]
        self.assertIn("2", message)


class UnTourSansVoix(BaseDuLocuteur):
    """
    La fusion de deux tours de voix différentes RETIRE la clé
    (`moteur_structure.py`) : un bloc peut donc n'avoir aucun locuteur.
    Ce geste est aussi ce qui répare ce cas.
    / A merge of two diverging turns drops the key entirely.
    """

    def test_un_tour_SANS_locuteur_peut_en_recevoir_un(self):
        reponse = self._renommer(self.tours[4], "Paul")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self._locuteurs()[4], "Paul")

    def test_les_portees_LARGES_sont_refusees_sur_un_tour_sans_voix(self):
        """
        « Tous les blocs sans locuteur » n'est pas un groupe : ces blocs
        n'ont rien en commun qu'une absence. Les renommer ensemble
        inventerait une voix là où l'information manque.
        / Blocks with no speaker share nothing but an absence.
        """
        reponse = self._renommer(self.tours[4], "Paul", portee="tous")
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self._locuteurs()[4], None)


class CeQueLeGesteNeTOUCHE_PAS(BaseDuLocuteur):
    """
    Ni le texte, ni l'empreinte, ni l'ordre, ni le minutage.
    / Neither the text, nor the fingerprint, order or timing.
    """

    def test_le_texte_et_l_empreinte_sont_INTACTS(self):
        avant = [(t.texte, t.empreinte_contenu) for t in self.tours]
        self._renommer(self.tours[0], "Paul", portee="tous")
        for tour, (texte, empreinte) in zip(self.tours, avant):
            tour.refresh_from_db()
            self.assertEqual(tour.texte, texte)
            self.assertEqual(tour.empreinte_contenu, empreinte)

    def test_le_MINUTAGE_survit_au_renommage(self):
        """
        `provenance` porte aussi `debut` et `fin` : les écraser
        casserait « écouter à partir de ce passage » (§ 6.1).
        / provenance also carries the timing: it must survive.
        """
        self._renommer(self.tours[0], "Paul")
        self.tours[0].refresh_from_db()
        self.assertEqual(self.tours[0].provenance.get("debut"), 0.0)
        self.assertEqual(self.tours[0].provenance.get("fin"), 2.0)


class LeJournalDuLocuteur(BaseDuLocuteur):
    """§ 10 : le geste que l'humain a fait s'écrit."""

    def test_un_PageEdit_de_type_locuteur_est_ecrit(self):
        self._renommer(self.tours[0], "Paul")
        journal = PageEdit.objects.get(page=self.page)
        self.assertEqual(journal.type_edit, "locuteur")

    def test_le_journal_porte_l_AVANT_et_l_APRES(self):
        self._renommer(self.tours[0], "Paul", portee="tous")
        journal = PageEdit.objects.get(page=self.page)
        self.assertEqual(journal.donnees_avant["locuteur"], "SPEAKER_00")
        self.assertEqual(journal.donnees_apres["locuteur"], "Paul")
        self.assertEqual(journal.donnees_apres["tours_touches"], 2)

    def test_renommer_a_l_IDENTIQUE_n_ecrit_AUCUN_journal(self):
        """
        Un non-geste ne s'écrit pas : un journal qui note ce qui n'a pas
        changé rend l'historique illisible.
        / A no-op leaves no trace.
        """
        reponse = self._renommer(self.tours[0], "SPEAKER_00")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(PageEdit.objects.filter(page=self.page).count(), 0)


class LesRefusDuLocuteur(BaseDuLocuteur):
    """La doctrine du dépôt, appliquée à ce geste."""

    def test_un_nom_VIDE_est_refuse(self):
        reponse = self._renommer(self.tours[0], "   ")
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self._locuteurs()[0], "SPEAKER_00")

    def test_un_tiers_qui_ne_peut_pas_LIRE_recoit_404(self):
        self.client.force_login(self.tiers)
        reponse = self._renommer(self.tours[0], "Paul")
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(self._locuteurs()[0], "SPEAKER_00")

    def test_un_tiers_qui_peut_LIRE_mais_pas_ecrire_recoit_403(self):
        from core.models import VisibiliteDossier
        self.dossier.visibilite = VisibiliteDossier.PUBLIC
        self.dossier.save(update_fields=["visibilite"])
        self.client.force_login(self.tiers)
        reponse = self._renommer(self.tours[0], "Paul")
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(self._locuteurs()[0], "SPEAKER_00")

    def test_une_ANALYSE_qui_tourne_refuse_le_geste(self):
        """
        Une transcription en cours va remplacer TOUS les éléments de la
        note : renommer maintenant écrirait dans ce qui va disparaître.
        / A running transcription will replace every element.
        """
        from hypostasis_extractor.models import ExtractionJob
        ExtractionJob.objects.create(page=self.page, status="processing")
        reponse = self._renommer(self.tours[0], "Paul")
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(self._locuteurs()[0], "SPEAKER_00")


class LeSwapDesToursTouches(BaseDuLocuteur):
    """
    § 11.3 : le geste rend les blocs touchés, JAMAIS un rechargement —
    il sera appelé depuis le mode d'édition, où `lectureReload`
    détruirait la session de frappe.
    / It renders the touched blocks, never a reload.
    """

    def test_la_reponse_rend_les_blocs_touches_en_swap(self):
        reponse = self._renommer(self.tours[0], "Paul", portee="tous")
        corps = reponse.content.decode()
        self.assertIn('hx-swap-oob="true"', corps)
        self.assertIn(str(self.tours[0].identifiant_stable), corps)
        self.assertIn(str(self.tours[2].identifiant_stable), corps)

    def test_AUCUN_rechargement_n_est_declenche(self):
        reponse = self._renommer(self.tours[0], "Paul")
        self.assertNotIn("lectureReload", reponse["HX-Trigger"])
