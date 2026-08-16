"""
Les idees sans passage sont ANNONCEES comme telles dans le panneau.
/ Ideas with no passage are LABELLED as such in the panel.

LOCALISATION : front/tests/test_ancres_detachees_drawer.py

POURQUOI CES TESTS EXISTENT

La reconversion du 10 aout 2026 a detache 1 402 ancres qui surlignaient
un passage sans rapport avec leur citation, en promettant qu'« un humain
trancherait ». Verification au navigateur : ces extractions sont bien
dans le panneau — rien n'a disparu — mais elles y sont INDISCERNABLES
des autres. Meme classe, aucun badge, aucun mot. L'humain cense trancher
n'a aucun moyen de savoir lesquelles trancher : la promesse est creuse.

L'etalon `front/static/front/maquettes/maquette.html` (l. 1671-1682) prevoit une carte
`est-masquee` portant l'etiquette « ancre detachee » et l'origine
« aucun element — a replacer ».
/ Nothing vanished, but nothing was labelled either.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import ElementDocument, Page, empreinte_du_texte
from hypostasis_extractor.models import (
    AncrageExtraction,
    EtatAncrage,
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)

Utilisateur = get_user_model()

TEXTE = "Le conseil a vote le budget."


class AncresDetacheesDansLePanneauTest(TestCase):
    """Le panneau distingue les idees placees de celles qui ne le sont pas."""

    def setUp(self):
        self.lecteur = Utilisateur.objects.create_user(
            username="lectrice", password="motdepasse",
        )
        self.page = Page.objects.create(
            url="http://exemple.local/detachees",
            html_original="x", html_readability="x",
            text_readability=TEXTE, content_hash="empreinte-detachees",
            title="Note a ancres detachees",
            owner=self.lecteur,
        )
        self.element = ElementDocument.objects.create(
            page=self.page, ordre=0, label="text", texte=TEXTE,
            empreinte_contenu=empreinte_du_texte(TEXTE),
        )
        self.job = ExtractionJob.objects.create(
            page=self.page, name="Job", prompt_description="p",
            status=ExtractionJobStatus.COMPLETED,
        )
        self.client.force_login(self.lecteur)

    def _creer_une_extraction(self, texte):
        return ExtractedEntity.objects.create(
            job=self.job, extraction_class="idee",
            extraction_text=texte, start_char=0, end_char=len(texte),

    )

    def _ouvrir_le_panneau(self):
        return self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",

    )

    def test_une_idee_detachee_est_annoncee_dans_sa_carte(self):
        extraction = self._creer_une_extraction("budget")
        AncrageExtraction.objects.create(
            extraction=extraction, element=self.element,
            debut_dans_element=0, fin_dans_element=3,
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.DETACHEE,

        )

        reponse = self._ouvrir_le_panneau()

        self.assertContains(reponse, "ancre détachée",

    )

    def test_une_idee_sans_aucune_ancre_est_annoncee_aussi(self):
        # Du point de vue du lecteur, c'est la meme situation : une idee
        # que rien ne montre dans le texte. 1 715 extractions de la base
        # sont dans ce cas apres la reconversion.
        # / Same situation for the reader: an idea shown nowhere.
        self._creer_une_extraction("une idee sans passage",

        )

        reponse = self._ouvrir_le_panneau()

        self.assertContains(reponse, "ancre détachée",

    )

    def test_une_idee_bien_ancree_n_est_pas_annoncee_detachee(self):
        extraction = self._creer_une_extraction("budget")
        AncrageExtraction.objects.create(
            extraction=extraction, element=self.element,
            debut_dans_element=0, fin_dans_element=3,
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,

        )

        reponse = self._ouvrir_le_panneau()

        self.assertNotContains(reponse, "ancre détachée",

    )

    def test_l_avis_de_plafond_est_bien_RENDU_dans_le_bloc(self):
        # Les tests du plafond ne verifiaient que la valeur calculee par
        # le service (`idees_non_surlignees`) : on pouvait retirer le
        # bloc {% if %} du gabarit sans qu'un seul tombe. L'avis n'etait
        # prouve que par un passage au navigateur, qui ne se rejoue pas.
        #
        # La classe est celle de l'ETALON (`avertissement-plafond`,
        # maquette.html § 8) : la maquette prevoyait deja ce cas, et
        # deux vocabulaires pour la meme chose est l'ecart qu'on
        # cherche a supprimer.
        # / The class name is the mock's own.
        from django.template.loader import render_to_string

        html = render_to_string(
            "front/includes/_blocs_elements.html",
            {
                "blocs_de_lecture": [{
                    "element": self.element,
                    "balise": "p",
                    "html_du_texte": TEXTE,
                    "nombre_d_idees": 623,
                    "idees_non_surlignees": 623,
                    "est_masque": False,
                    "fusion_possible": False,
                }],
                "la_note_est_modifiable": False,
            },

        )

        self.assertIn("avertissement-plafond", html)
        self.assertIn("623", html,

    )

    def test_un_bloc_ordinaire_ne_porte_aucun_avis(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "front/includes/_blocs_elements.html",
            {
                "blocs_de_lecture": [{
                    "element": self.element,
                    "balise": "p",
                    "html_du_texte": TEXTE,
                    "nombre_d_idees": 3,
                    "idees_non_surlignees": 0,
                    "est_masque": False,
                    "fusion_possible": False,
                }],
                "la_note_est_modifiable": False,
            },

        )

        self.assertNotIn("avertissement-plafond", html)

    def test_une_idee_ancree_reste_non_detachee_parmi_des_detachees(self):
        """
        L'etiquette suit l'ancre de CHAQUE idee.

        Ce test verifiait qu'une page de l'ANCIEN moteur n'etiquetait
        rien. Ce moteur n'existe plus, ni le flag qui le designait : ce
        qui reste a prouver est que l'etiquette se decide idee par idee,
        et non par un etat global de la page.
        / The label is decided per idea, not by a page-wide state.
        """
        ancree = self._creer_une_extraction("budget")
        AncrageExtraction.objects.create(
            extraction=ancree, element=self.element,
            debut_dans_element=0, fin_dans_element=3,
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
        )
        self._creer_une_extraction("une idee sans passage")

        reponse = self._ouvrir_le_panneau()

        # Une seule etiquette, pour la seule idee sans ancre.
        # / One label, for the one idea without an anchor.
        self.assertEqual(reponse.content.decode().count("ancre détachée"), 1)


class LaGouttiereEstRendueDansLeBlocTest(TestCase):
    """
    Le markup de la gouttiere (etalon `maquette.html` § .bloc).
    / The gutter markup.

    LOCALISATION : front/tests/test_ancres_detachees_drawer.py

    Confrontation au navigateur du 10 aout : l'etalon compte 14 elements
    de gouttiere, l'application ZERO. Ces tests figent ce qui doit s'y
    trouver, et surtout LE COMPTEUR D'IDEES — le seul habitant de la
    gouttiere qui s'adresse au lecteur, les autres etant du diagnostic
    reserve au mode structure.
    / Measured: 14 gutter elements in the mock, zero in the app.
    """

    def _rendre(self, **surcharges):
        from django.template.loader import render_to_string

        bloc = {
            "element": type("E", (), {
                "pk": 7, "ordre": 0, "label": "text", "texte": "Un passage.",
            })(),
            "balise": "p",
            "html_du_texte": "Un passage.",
            "nombre_d_idees": 3,
            "idees_non_surlignees": 0,
            "est_masque": False,
            "fusion_possible": False,
            "numero": 1,
            "est_debattu": False,
            "empreinte_courte": "a1b2c3d4",
        }
        bloc.update(surcharges)
        return render_to_string(
            "front/includes/_blocs_elements.html",
            {"blocs_de_lecture": [bloc], "la_note_est_modifiable": False},
        )

    def test_le_bloc_est_une_grille_gouttiere_corps(self):
        html = self._rendre()

        self.assertIn('class="bloc"', html)
        self.assertIn('class="gouttiere"', html)
        self.assertIn('class="filet-etat"', html)
        self.assertIn('class="corps"', html)

    def test_le_compteur_d_idees_affiche_leur_nombre(self):
        html = self._rendre(nombre_d_idees=3)

        self.assertIn('class="compteur-idees"', html)
        self.assertIn("3 idées extraites de ce passage", html)

    def test_un_passage_sans_idee_n_a_pas_de_compteur(self):
        # Un « 0 » dans la gouttiere serait du bruit : l'absence se lit
        # deja a l'absence de surlignage.
        # / A zero would be noise; absence already reads as absence.
        html = self._rendre(nombre_d_idees=0)

        self.assertNotIn("compteur-idees", html)

    def test_une_seule_idee_se_dit_au_singulier(self):
        html = self._rendre(nombre_d_idees=1)

        self.assertIn("1 idée extraite de ce passage", html)

    def test_un_passage_debattu_le_dit_dans_son_etat(self):
        html = self._rendre(est_debattu=True)

        self.assertIn('data-etat="debattu"', html)

    def test_un_passage_tranquille_ne_se_dit_pas_debattu(self):
        html = self._rendre(est_debattu=False)

        self.assertIn('data-etat="analyse"', html)

    def test_le_numero_et_l_empreinte_sont_dans_la_gouttiere(self):
        # Presents dans le DOM, mais caches en lecture par le CSS : le
        # mode structure les revele. / In the DOM, hidden by CSS.
        html = self._rendre(numero=4, empreinte_courte="deadbeef")

        self.assertIn("#4", html)
        self.assertIn("deadbeef", html)
