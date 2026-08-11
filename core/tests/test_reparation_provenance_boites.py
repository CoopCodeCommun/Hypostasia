"""
Tests de la reparation du prefixe d'enumeration dans coord_origin
(commande reparer_la_provenance_des_boites).
/ Tests for stripping the enum class prefix from coord_origin.

LOCALISATION : core/tests/test_reparation_provenance_boites.py

CE QUE CETTE COMMANDE CORRIGE

`hypostasis_extractor/services/ingestion_docling.py` faisait `str()` sur
le membre d'enumeration CoordOrigin de docling-core, ce qui ecrivait
"CoordOrigin.BOTTOMLEFT" en base au lieu de "BOTTOMLEFT". Le service est
corrige, mais les boites deja en base portent encore le defaut : cette
commande le repare, sans toucher aux coordonnees ni au reste de la
provenance.
/ The service is fixed; this command repairs the data already written
with the bug.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.models import ElementDocument, Page


def creer_une_page(suffixe):
    return Page.objects.create(
        url=f"http://exemple.local/reparation-{suffixe}",
        html_original="<p>o</p>", html_readability="<p>l</p>",
        text_readability="Un contenu.",
        content_hash=f"hash-reparation-{suffixe}",
    )


def creer_un_element(page, ordre, provenance):
    return ElementDocument.objects.create(
        page=page, ordre=ordre, label="text", texte="Un paragraphe.",
        empreinte_contenu=f"empreinte-{ordre}", provenance=provenance,
    )


def provenance_avec_prefixe(page_no=3):
    return {
        "page_no": page_no,
        "boites": [{
            "l": 46.0, "t": 739.2, "r": 472.8, "b": 661.0,
            "coord_origin": "CoordOrigin.BOTTOMLEFT",
            "page_no": page_no,
        }],
    }


class LaReparationCorrigeLeDefautTest(TestCase):
    def test_le_prefixe_de_classe_est_retire(self):
        page = creer_une_page("prefixe")
        element = creer_un_element(page, 0, provenance_avec_prefixe())

        call_command("reparer_la_provenance_des_boites", stdout=StringIO())

        element.refresh_from_db()
        self.assertEqual(
            element.provenance["boites"][0]["coord_origin"], "BOTTOMLEFT",
        )

    def test_les_coordonnees_ne_bougent_pas(self):
        """
        Seul coord_origin change : les boites, le numero de page, tout le
        reste de la provenance doit rester identique.
        / Only coord_origin changes; everything else stays put.
        """
        page = creer_une_page("coords")
        provenance = provenance_avec_prefixe(page_no=7)
        element = creer_un_element(page, 0, provenance)

        call_command("reparer_la_provenance_des_boites", stdout=StringIO())

        element.refresh_from_db()
        boite = element.provenance["boites"][0]
        self.assertEqual(element.provenance["page_no"], 7)
        self.assertEqual(boite["l"], 46.0)
        self.assertEqual(boite["t"], 739.2)
        self.assertEqual(boite["r"], 472.8)
        self.assertEqual(boite["b"], 661.0)
        self.assertEqual(boite["page_no"], 7)

    def test_une_valeur_deja_propre_est_laissee_intacte(self):
        page = creer_une_page("propre")
        provenance = {
            "page_no": 1,
            "boites": [{
                "l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0,
                "coord_origin": "BOTTOMLEFT", "page_no": 1,
            }],
        }
        element = creer_un_element(page, 0, provenance)

        call_command("reparer_la_provenance_des_boites", stdout=StringIO())

        element.refresh_from_db()
        self.assertEqual(
            element.provenance["boites"][0]["coord_origin"], "BOTTOMLEFT",
        )

    def test_une_provenance_sans_boite_est_laissee_intacte(self):
        page = creer_une_page("vide")
        element = creer_un_element(page, 0, {})

        call_command("reparer_la_provenance_des_boites", stdout=StringIO())

        element.refresh_from_db()
        self.assertEqual(element.provenance, {})

    def test_la_reparation_est_idempotente(self):
        page = creer_une_page("idempotence")
        element = creer_un_element(page, 0, provenance_avec_prefixe())

        call_command("reparer_la_provenance_des_boites", stdout=StringIO())

        sortie_second_passage = StringIO()
        call_command(
            "reparer_la_provenance_des_boites", stdout=sortie_second_passage,
        )

        element.refresh_from_db()
        self.assertEqual(
            element.provenance["boites"][0]["coord_origin"], "BOTTOMLEFT",
        )
        self.assertIn("0", sortie_second_passage.getvalue())

    def test_a_blanc_n_ecrit_rien(self):
        page = creer_une_page("a-blanc")
        element = creer_un_element(page, 0, provenance_avec_prefixe())

        call_command(
            "reparer_la_provenance_des_boites", "--a-blanc", stdout=StringIO(),
        )

        element.refresh_from_db()
        self.assertEqual(
            element.provenance["boites"][0]["coord_origin"],
            "CoordOrigin.BOTTOMLEFT",
        )


class LaReparationSurvitAUneDonneeAbimeeTest(TestCase):
    """
    Une commande de reparation est exactement l'outil qu'on lance sur une
    base dont on soupconne les donnees d'etre abimees : elle ne doit pas
    planter au premier cas inattendu.
    / A repair command must not crash on the first malformed record.
    """

    def test_une_provenance_qui_n_est_pas_un_dict_ne_fait_pas_planter(self):
        """
        `element.provenance or {}` ne protege pas si `provenance` est une
        LISTE non vide : elle est truthy, `or {}` ne s'applique pas, et
        `.get("boites")` leve. Meme defaut qu'une boite non-dict, un
        niveau au-dessus — meme categorie de bilan.
        / A truthy non-dict `provenance` bypasses `or {}` and crashes
        `.get()`; same bucket as the other unexpected-shape cases.
        """
        page = creer_une_page("provenance-pas-dict")
        element = creer_un_element(page, 0, ["pas un dict"])

        sortie = StringIO()
        call_command("reparer_la_provenance_des_boites", stdout=sortie)

        element.refresh_from_db()
        self.assertEqual(element.provenance, ["pas un dict"])
        self.assertIn("provenance inattendue", sortie.getvalue())

    def test_boites_n_etant_pas_une_liste_est_ignoree_et_comptee(self):
        page = creer_une_page("boites-pas-liste")
        element = creer_un_element(page, 0, {
            "page_no": 1, "boites": "pas une liste",
        })

        sortie = StringIO()
        call_command("reparer_la_provenance_des_boites", stdout=sortie)

        element.refresh_from_db()
        self.assertEqual(element.provenance["boites"], "pas une liste")
        self.assertIn("provenance inattendue", sortie.getvalue())
        self.assertIn("1", sortie.getvalue())

    def test_une_boite_qui_n_est_pas_un_dict_ne_fait_pas_planter(self):
        page = creer_une_page("boite-pas-dict")
        element = creer_un_element(page, 0, {
            "page_no": 1,
            "boites": [
                "pas un dict",
                {
                    "l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0,
                    "coord_origin": "CoordOrigin.BOTTOMLEFT", "page_no": 1,
                },
            ],
        })

        sortie = StringIO()
        call_command("reparer_la_provenance_des_boites", stdout=sortie)

        element.refresh_from_db()
        boites = element.provenance["boites"]
        self.assertEqual(boites[0], "pas un dict")
        self.assertEqual(boites[1]["coord_origin"], "BOTTOMLEFT")
        self.assertIn("ignor", sortie.getvalue())

    def test_une_boite_sans_coord_origin_n_est_pas_comptee_comme_propre(self):
        """
        Absente n'est pas propre, c'est muette — nuance qui compte.
        / Missing is not clean, it is silent — a different case.
        """
        page = creer_une_page("boite-muette")
        element = creer_un_element(page, 0, {
            "page_no": 1,
            "boites": [{"l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0, "page_no": 1}],
        })

        sortie = StringIO()
        call_command("reparer_la_provenance_des_boites", stdout=sortie)

        element.refresh_from_db()
        self.assertNotIn("coord_origin", element.provenance["boites"][0])
        contenu = sortie.getvalue()
        self.assertIn("Boites deja propres                : 0", contenu)
        self.assertIn("muette", contenu)
