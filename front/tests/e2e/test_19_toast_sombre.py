"""
Tests E2E — Le toast doit se DETACHER de la page, en clair comme en sombre.
/ E2E tests — The toast must stand out from the page, in both themes.

LOCALISATION : front/tests/e2e/test_19_toast_sombre.py

CE QUE CES TESTS EPROUVENT

Mesure du 12 aout, mode sombre, reproduite au navigateur :

  texte du toast   rgb(236, 234, 228)
  fond du toast    rgb(22, 21, 26)
  fond de la page  rgb(22, 21, 26)   <- le MEME
  bordure          0px none
  ombre            noire a 18 % — invisible sur fond noir

Le contraste du TEXTE etait excellent (~14,8:1). Ce n'etait pas le
probleme. Le probleme est qu'un rectangle sans contour, du meme fond que
ce qu'il recouvre, n'est pas percu comme un objet : on lisait son texte
superpose au panneau, sans voir qu'il s'agissait d'un message.

En clair, l'ombre portee suffisait a le detacher. En sombre, une ombre
noire sur un fond noir ne separe rien. Il faut un fond distinct ET un
contour.
/ Excellent text contrast was never the issue: an unbordered box on an
identical background does not read as an object at all.
"""

from front.tests.e2e.base import PlaywrightLiveTestCase

# WCAG 1.4.11 demande 3:1 pour delimiter un composant quand le contour
# est son seul indice visuel. / WCAG 1.4.11 asks 3:1 for such a boundary.
CONTRASTE_MINIMAL_DU_CONTOUR = 3.0

# Le corps du message doit rester tres lisible : on vise le AAA du texte
# normal. / The message body targets AAA for normal text.
CONTRASTE_MINIMAL_DU_TEXTE = 7.0

# Fonction de contraste WCAG, evaluee dans la page.
# / WCAG contrast helper, evaluated in-page.
OUTILS_DE_CONTRASTE = """
    /* Deux formats sortent de getComputedStyle, et ils n'ont PAS la meme
       echelle : `rgb(129, 125, 120)` compte en 0-255, tandis que
       `color(srgb 0.505 0.489 0.471)` — ce que rend `color-mix()` —
       compte en 0-1. Les lire pareil donne un contraste faux d'un ordre
       de grandeur : la premiere version de ce test annoncait 1,15:1 la
       ou la vraie valeur etait 4,13:1, et accusait le CSS a tort.
       / color-mix() returns 0-1 channels; rgb() returns 0-255. */
    const versCanaux = (couleur) => {
        const nombres = couleur.match(/[\\d.]+/g).slice(0, 3).map(Number);
        return couleur.includes('color(')
            ? nombres.map((canal) => canal * 255)
            : nombres;
    };
    const luminance = (couleur) => {
        const [r, v, b] = versCanaux(couleur).map((canal) => {
            const proportion = canal / 255;
            return proportion <= 0.03928
                ? proportion / 12.92
                : Math.pow((proportion + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * r + 0.7152 * v + 0.0722 * b;
    };
    const contraste = (premiere, seconde) => {
        const a = luminance(premiere), b = luminance(seconde);
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    };
"""


class E2EToastSombreTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_19_toast_sombre.py
    """

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")
        self.note = self.creer_page_demo(
            "Note du toast", "<p>Support du toast.</p>", owner=self.utilisateur_test
        )

    def mesurer_le_toast_en(self, theme):
        """
        Force le theme, leve un toast, et rend ses mesures.
        / Force the theme, raise a toast, return its measurements.
        """
        self.page.set_viewport_size({"width": 1600, "height": 1000})
        self.naviguer_vers(f"/lire/{self.note.pk}/")
        # Le contraste se mesure sur des couleurs calculees : la page
        # doit avoir fini de se peindre, polices comprises.
        # / Contrast is read from computed colors: the page must have
        # finished painting, fonts included.
        self.attendre_la_mise_en_page("#zone-lecture")

        return self.page.evaluate(
            OUTILS_DE_CONTRASTE
            + """
            (theme) => {
                document.documentElement.setAttribute('data-theme', theme);
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'success',
                    title: 'Extraction créée', showConfirmButton: false,
                    timer: 30000,
                });
                const toast = document.querySelector('.swal2-popup');
                const titre = document.querySelector('.swal2-title');
                const styleDuToast = getComputedStyle(toast);
                const fondDuToast = styleDuToast.backgroundColor;
                const fondDeLaPage = getComputedStyle(document.body).backgroundColor;
                return {
                    fondDuToast,
                    fondDeLaPage,
                    largeurDeLaBordure: parseFloat(styleDuToast.borderTopWidth),
                    contrasteDuContour: contraste(
                        styleDuToast.borderTopColor, fondDeLaPage
                    ),
                    contrasteDuTexte: contraste(
                        getComputedStyle(titre).color, fondDuToast
                    ),
                    contrasteDesFonds: contraste(fondDuToast, fondDeLaPage),
                };
            }""",
            theme,
        )

    def verifier_que_le_toast_se_detache(self, theme):
        """
        Un toast se detache s'il a un contour percevable OU un fond
        franchement distinct — et son texte doit rester lisible dessus.
        / A toast stands out through a visible boundary or a distinct fill.
        """
        mesures = self.mesurer_le_toast_en(theme)

        self.assertGreater(
            mesures["largeurDeLaBordure"],
            0,
            f"[{theme}] Le toast n'a aucune bordure : "
            f"{mesures['largeurDeLaBordure']}px.",
        )
        self.assertGreaterEqual(
            mesures["contrasteDuContour"],
            CONTRASTE_MINIMAL_DU_CONTOUR,
            f"[{theme}] Le contour du toast ne se détache pas de la page : "
            f"{mesures['contrasteDuContour']:.2f}:1 pour "
            f"{CONTRASTE_MINIMAL_DU_CONTOUR}:1 demandés.",
        )
        self.assertNotEqual(
            mesures["fondDuToast"],
            mesures["fondDeLaPage"],
            f"[{theme}] Le toast a exactement le fond de la page "
            f"({mesures['fondDuToast']}) : il ne se lit pas comme un objet.",
        )
        self.assertGreaterEqual(
            mesures["contrasteDuTexte"],
            CONTRASTE_MINIMAL_DU_TEXTE,
            f"[{theme}] Texte du toast peu lisible : "
            f"{mesures['contrasteDuTexte']:.2f}:1.",
        )

    def test_le_toast_se_detache_en_mode_sombre(self):
        """C'est le defaut mesure : fond identique, aucune bordure."""
        self.verifier_que_le_toast_se_detache("dark")

    def test_le_toast_se_detache_en_mode_clair(self):
        """
        En clair l'ombre suffisait. On verifie qu'en reparant le sombre on
        n'a rien casse ici. / Check the light theme did not regress.
        """
        self.verifier_que_le_toast_se_detache("light")
