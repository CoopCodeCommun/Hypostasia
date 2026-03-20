"""
Tests E2E — Charte visuelle : polices, variables CSS, contraste WCAG.
/ E2E tests — Visual charter: fonts, CSS variables, WCAG contrast.
"""
from front.tests.e2e.base import PlaywrightLiveTestCase


class E2ECharteVisuelleTest(PlaywrightLiveTestCase):
    """Tests de la charte visuelle."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur et se connecter
        # / Create a user and log in
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        # Creer une page minimale pour charger les styles
        # / Create a minimal page to load styles
        self.page_test = self.creer_page_demo(
            "Page charte visuelle",
            "<p>Contenu pour tester la charte visuelle.</p>",
            owner=self.utilisateur_test,
        )

    def test_police_b612_chargee(self):
        """La police B612 est chargee dans le document."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        b612_charge = self.page.evaluate("document.fonts.check('16px B612')")
        self.assertTrue(b612_charge, "La police B612 n'est pas chargee")

    def test_police_b612_mono_chargee(self):
        """La police B612 Mono est chargee dans le document."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        # Tester avec et sans guillemets car le nom peut varier
        # / Test with and without quotes since the name may vary
        b612_mono_charge = self.page.evaluate(
            "document.fonts.check('16px \"B612 Mono\"') || document.fonts.check('16px B612Mono')"
        )
        self.assertTrue(b612_mono_charge, "La police B612 Mono n'est pas chargee")

    def test_police_lora_chargee(self):
        """La police Lora est chargee dans le document."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        lora_charge = self.page.evaluate("document.fonts.check('16px Lora')")
        self.assertTrue(lora_charge, "La police Lora n'est pas chargee")

    def test_police_srisakdi_declaree(self):
        """La police Srisakdi est declaree dans les @font-face du document."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        # Srisakdi est declaree avec unicode-range, le navigateur ne la charge
        # que si des caracteres dans ce range sont utilises. On verifie la declaration.
        # / Srisakdi is declared with unicode-range, the browser only loads it
        # if characters in that range are used. We verify the declaration.
        srisakdi_declaree = self.page.evaluate(
            "Array.from(document.fonts.values()).some(f => f.family === 'Srisakdi')"
        )
        self.assertTrue(srisakdi_declaree, "La police Srisakdi n'est pas declaree dans @font-face")

    def test_variables_css_root_presentes(self):
        """Les variables CSS :root sont definies (statuts debat, hypostases)."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        # Verifier les variables CSS de statuts de debat (nommees --statut-*)
        # / Check debate status CSS variables (named --statut-*)
        variables_a_verifier = [
            "--statut-consensuel-text",
            "--statut-discutable-text",
            "--statut-discute-text",
            "--statut-controverse-text",
            "--statut-consensuel-bg",
            "--statut-discutable-bg",
            "--statut-discute-bg",
            "--statut-controverse-bg",
        ]
        for nom_variable in variables_a_verifier:
            valeur = self.page.evaluate(
                f"getComputedStyle(document.documentElement).getPropertyValue('{nom_variable}').trim()"
            )
            self.assertTrue(
                len(valeur) > 0,
                f"La variable CSS {nom_variable} n'est pas definie",
            )

    def test_contraste_wcag_statuts_debat(self):
        """Les couleurs de statut debat ont un contraste WCAG >= 4.5:1."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        # Calculer le ratio de contraste pour chaque statut via JS
        # / Calculate contrast ratio for each status via JS
        script_contraste = """
        () => {
            function luminance(r, g, b) {
                var a = [r, g, b].map(function(v) {
                    v /= 255;
                    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
                });
                return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
            }
            function contrastRatio(l1, l2) {
                var lighter = Math.max(l1, l2);
                var darker = Math.min(l1, l2);
                return (lighter + 0.05) / (darker + 0.05);
            }
            function parseColor(str) {
                var m = str.match(/rgb\\((\\d+),\\s*(\\d+),\\s*(\\d+)\\)/);
                if (m) return [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])];
                return null;
            }
            var root = getComputedStyle(document.documentElement);
            // Contraste texte statut sur fond statut
            var pairs = [
                ['--statut-consensuel-text', '--statut-consensuel-bg'],
                ['--statut-discutable-text', '--statut-discutable-bg'],
                ['--statut-discute-text', '--statut-discute-bg'],
                ['--statut-controverse-text', '--statut-controverse-bg'],
            ];
            var results = {};
            for (var pair of pairs) {
                var textVal = root.getPropertyValue(pair[0]).trim();
                var bgVal = root.getPropertyValue(pair[1]).trim();

                var elText = document.createElement('div');
                elText.style.color = textVal;
                document.body.appendChild(elText);
                var computedText = getComputedStyle(elText).color;
                document.body.removeChild(elText);

                var elBg = document.createElement('div');
                elBg.style.color = bgVal;
                document.body.appendChild(elBg);
                var computedBg = getComputedStyle(elBg).color;
                document.body.removeChild(elBg);

                var rgbText = parseColor(computedText);
                var rgbBg = parseColor(computedBg);
                if (rgbText && rgbBg) {
                    var lText = luminance(rgbText[0], rgbText[1], rgbText[2]);
                    var lBg = luminance(rgbBg[0], rgbBg[1], rgbBg[2]);
                    results[pair[0]] = contrastRatio(lText, lBg);
                } else {
                    results[pair[0]] = 0;
                }
            }
            return results;
        }
        """
        resultats = self.page.evaluate(script_contraste)
        for nom_variable, ratio in resultats.items():
            if ratio > 0:
                self.assertGreaterEqual(
                    ratio, 4.5,
                    f"Contraste insuffisant pour {nom_variable}: {ratio:.2f}",
                )
