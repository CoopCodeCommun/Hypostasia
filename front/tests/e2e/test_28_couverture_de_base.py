"""
Tests E2E — La couverture d'une base s'affiche vraiment.
/ E2E tests — A knowledge base cover actually renders.

LOCALISATION : front/tests/e2e/test_28_couverture_de_base.py

CE QUE CES TESTS EPROUVENT

Verifier qu'une balise `<img>` est PRESENTE dans le DOM ne dit rien de
son affichage. Mesure du 12 aout : la couverture etait bien rendue, avec
sa boite de 313x176 au bon rapport 16/9 — et `naturalWidth` valait 0.
L'image n'avait jamais ete chargee.

LA CAUSE, ET POURQUOI ELLE EST DIFFICILE A VOIR

`loading="lazy"` delegue le chargement a l'observation de l'intersection
avec le conteneur de defilement le plus proche. Or la liste des bases vit
dans `#zone-lecture`, qui porte `overflow-y: auto` : c'est un scroller
IMBRIQUE, et l'observation y est peu fiable. L'image restait a 0x0 alors
qu'elle occupait le haut de l'ecran.

Le fichier etait pourtant servi — 200, `image/png`, 5 566 octets, verifie
au `curl` et par un `new Image()` hors du DOM. Tout allait bien sauf ce
qui comptait.

D'ou ces tests, qui mesurent `naturalWidth` et le RAPPORT rendu, pas la
presence d'une balise.
/ Checking that an <img> exists says nothing about it rendering:
`loading="lazy"` inside a nested scroller never fired.
"""

import io

from django.core.files.base import ContentFile

from core.models import BaseDeConnaissances, VisibiliteDossier
from front.tests.e2e.base import PlaywrightLiveTestCase

# La carte dessine sa couverture en 16/9. / The card draws its cover 16:9.
RAPPORT_ATTENDU = 16 / 9
TOLERANCE_DU_RAPPORT = 0.03


def fabriquer_une_couverture(largeur, hauteur):
    """
    Rend les octets d'un PNG uni aux dimensions demandees.
    / Return the bytes of a plain PNG at the requested size.

    LOCALISATION : front/tests/e2e/test_28_couverture_de_base.py
    """
    from PIL import Image

    image = Image.new("RGB", (largeur, hauteur), (28, 27, 25))
    tampon = io.BytesIO()
    image.save(tampon, format="PNG")
    return tampon.getvalue()


class E2ECouvertureDeBaseTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_28_couverture_de_base.py
    """

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        # Une couverture DELIBEREMENT hors rapport : 1600x600, soit 8/3.
        # Une image deja en 16/9 ne prouverait rien du cadrage.
        # / Deliberately off-ratio: an already-16/9 image proves nothing.
        self.base = BaseDeConnaissances.objects.create(
            nom="Base à couverture",
            slug="base-a-couverture",
            description="Une base qui porte une image de couverture.",
            owner=self.utilisateur_test,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.base.image_de_couverture.save(
            "couverture-essai.png",
            ContentFile(fabriquer_une_couverture(1600, 600)),
            save=True,
        )

    def mesurer_la_couverture(self):
        """Rend les mesures de l'image. / Return the image's measurements."""
        self.page.set_viewport_size({"width": 1600, "height": 1000})
        self.naviguer_vers("/bases/")
        # `naviguer_vers` attend l'evenement `load`, qui inclut les
        # images : la couverture est donc chargee. Il reste a attendre
        # que sa boite soit posee avant de la mesurer.
        # / naviguer_vers waits for `load`, images included; what remains
        # is the box settling.
        self.attendre_la_mise_en_page(".couverture-base")

        return self.page.evaluate(
            """() => {
                const image = document.querySelector('.couverture-base');
                if (!image) return null;
                const boite = image.getBoundingClientRect();
                return {
                    chargee: image.complete && image.naturalWidth > 0,
                    largeurNaturelle: image.naturalWidth,
                    hauteurNaturelle: image.naturalHeight,
                    largeurRendue: boite.width,
                    hauteurRendue: boite.height,
                    cadrage: getComputedStyle(image).objectFit,
                    chargementDiffere: image.getAttribute('loading'),
                };
            }"""
        )

    def test_la_couverture_est_reellement_chargee(self):
        """
        Le test central. Une balise presente mais jamais chargee laisse un
        rectangle vide a la place de l'image, sans rien signaler.
        / A present but never-loaded tag leaves an empty rectangle.
        """
        mesures = self.mesurer_la_couverture()

        self.assertIsNotNone(mesures, "Aucune couverture rendue.")
        self.assertTrue(
            mesures["chargee"],
            f"La couverture n'est pas chargée : "
            f"naturalWidth={mesures['largeurNaturelle']}, "
            f"loading={mesures['chargementDiffere']}.",
        )
        self.assertEqual(mesures["largeurNaturelle"], 1600)
        self.assertEqual(mesures["hauteurNaturelle"], 600)

    def test_la_couverture_est_cadree_en_seize_neuvieme(self):
        """
        L'image source est en 8/3. La carte doit la RECADRER en 16/9 sans
        la deformer — d'ou `object-fit: cover`.
        / The source is 8:3; the card must crop it to 16:9 without
        distorting it.
        """
        mesures = self.mesurer_la_couverture()

        self.assertIsNotNone(mesures)
        rapport_rendu = mesures["largeurRendue"] / mesures["hauteurRendue"]
        self.assertAlmostEqual(
            rapport_rendu, RAPPORT_ATTENDU, delta=TOLERANCE_DU_RAPPORT
        )
        self.assertEqual(
            mesures["cadrage"],
            "cover",
            "Sans `cover`, une image hors rapport se déforme.",
        )

    def test_une_base_sans_couverture_n_affiche_aucune_image(self):
        """
        La carte doit tenir sans image — c'est l'etat de toute base
        existante. Un cadre vide serait pire que rien.
        / The card must hold without an image: an empty frame is worse
        than none.
        """
        BaseDeConnaissances.objects.create(
            nom="Base sans couverture",
            slug="base-sans-couverture",
            description="Cette base n'a pas d'image.",
            owner=self.utilisateur_test,
            visibilite=VisibiliteDossier.PUBLIC,
        )

        self.page.set_viewport_size({"width": 1600, "height": 1000})
        self.naviguer_vers("/bases/")
        # Le test recense les cartes : il faut qu'au moins une soit la,
        # sinon il recenserait le vide et passerait pour de bonnes
        # raisons apparentes.
        # / The test surveys the cards: at least one must be there, or it
        # would survey emptiness and pass for the wrong reason.
        self.page.wait_for_selector(".carte-base")

        couvertures_par_carte = self.page.evaluate(
            """() => [...document.querySelectorAll('.carte-base')].map((carte) => ({
                slug: carte.dataset.baseSlug,
                aUneCouverture: !!carte.querySelector('.couverture-base'),
            }))"""
        )

        par_slug = {c["slug"]: c["aUneCouverture"] for c in couvertures_par_carte}
        self.assertTrue(par_slug.get("base-a-couverture"))
        self.assertFalse(par_slug.get("base-sans-couverture"))
