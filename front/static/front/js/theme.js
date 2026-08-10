/**
 * LE THEME A TROIS ETATS (lot T7 de la bascule CSS, 9 aout 2026).
 * LOCALISATION : front/static/front/js/theme.js
 *
 * Trois etats, comme l'etalon (tmp/maquettes/corpus.html) :
 *   "light"  -> clair force
 *   "dark"   -> sombre force
 *   ""       -> systeme (aucun attribut : le @media decide)
 *
 * Ce que l'etalon n'a PAS et qu'on ajoute : la PERSISTANCE. Un theme
 * qu'il faut rechoisir a chaque page n'est pas un theme.
 *
 * Ce fichier est charge dans le <head>, AVANT le rendu : sinon la page
 * s'affiche en clair puis clignote vers le sombre.
 *
 * / Three-state theme with the persistence the mockup lacks. Loaded in
 * the head, before paint, to avoid a flash of the wrong theme.
 */
(function () {
    "use strict";

    var CLE = "hypostasia-theme";
    var ETATS = ["", "light", "dark"];
    var LIBELLES = {
        "":      { glyphe: "◑", mot: "système" },
        "light": { glyphe: "○", mot: "clair" },
        "dark":  { glyphe: "●", mot: "sombre" }
    };

    function lireThemeStocke() {
        try {
            var valeur = window.localStorage.getItem(CLE);
            return ETATS.indexOf(valeur) === -1 ? "" : valeur;
        } catch (erreur) {
            // Navigation privee, stockage refuse : on retombe sur le systeme.
            // / Private browsing or storage denied: fall back to system.
            return "";
        }
    }

    function appliquerTheme(theme) {
        if (theme === "") {
            document.documentElement.removeAttribute("data-theme");
        } else {
            document.documentElement.setAttribute("data-theme", theme);
        }
    }

    function rafraichirBouton(theme) {
        var bouton = document.getElementById("bascule-theme");
        if (!bouton) { return; }
        var libelle = LIBELLES[theme];
        bouton.textContent = libelle.glyphe;
        bouton.title = "Thème : " + libelle.mot + " (cliquer pour changer)";
        // Le glyphe seul ne dit rien a un lecteur d'ecran.
        // / The glyph alone means nothing to a screen reader.
        bouton.setAttribute("aria-label", "Thème : " + libelle.mot + ". Changer de thème.");
    }

    function basculerTheme() {
        var courant = lireThemeStocke();
        var suivant = ETATS[(ETATS.indexOf(courant) + 1) % ETATS.length];
        try {
            if (suivant === "") {
                window.localStorage.removeItem(CLE);
            } else {
                window.localStorage.setItem(CLE, suivant);
            }
        } catch (erreur) {
            // Sans stockage, la bascule ne vaut que pour cette page.
            // / Without storage the toggle only lasts for this page.
        }
        appliquerTheme(suivant);
        rafraichirBouton(suivant);
    }

    // 1. Application immediate, avant le premier rendu.
    // / Apply before first paint.
    appliquerTheme(lireThemeStocke());

    // 2. Branchement du bouton quand le DOM existe.
    // / Wire the button once the DOM exists.
    document.addEventListener("DOMContentLoaded", function () {
        var bouton = document.getElementById("bascule-theme");
        rafraichirBouton(lireThemeStocke());
        if (bouton) {
            bouton.addEventListener("click", basculerTheme);
        }
    });

    window.themeHypostasia = { basculer: basculerTheme, lire: lireThemeStocke };
})();
