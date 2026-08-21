/**
 * LE THEME A DEUX ETATS, ET LE CLAIR EST LE DEFAUT.
 * LOCALISATION : front/static/front/js/theme.js
 *
 *   "light"  -> clair (le defaut, TOUJOURS)
 *   "dark"   -> sombre, parce que l'utilisateur l'a demande
 *
 * POURQUOI PLUS DE TROISIEME ETAT « systeme ». Il y en avait un, et il
 * etait le defaut : une machine reglee en sombre ouvrait Hypostasia en
 * sombre sans que personne ne l'ait choisi. Decision du mainteneur : le
 * clair est le mode de reference du produit — c'est celui sur lequel la
 * charte et l'etalon sont calibres — et passer en sombre est un GESTE.
 *
 * L'etalon fait deja exactement cela : ses trois fichiers s'ouvrent sur
 * `<html lang="fr" data-theme="light">`.
 *
 * LE DEFAUT EST ECRIT DANS LE HTML, pas seulement ici : `base.html`
 * porte `data-theme="light"` en dur. Sans JavaScript — ou avant qu'il
 * ne s'execute — la page reste donc claire, au lieu de suivre le
 * `@media (prefers-color-scheme: dark)` de la feuille de style.
 * Ce fichier ne fait que remplacer cette valeur par le choix stocke.
 *
 * / Two states, light by default: a dark-set machine used to open
 * Hypostasia in dark without anyone choosing it. The default is written
 * in the HTML too, so it holds without JavaScript.
 */
(function () {
    "use strict";

    var CLE = "hypostasia-theme";
    var DEFAUT = "light";
    var ETATS = ["light", "dark"];
    var LIBELLES = {
        "light": { glyphe: "○", mot: "clair" },
        "dark":  { glyphe: "●", mot: "sombre" }
    };

    function lireThemeStocke() {
        try {
            var valeur = window.localStorage.getItem(CLE);
            return ETATS.indexOf(valeur) === -1 ? DEFAUT : valeur;
        } catch (erreur) {
            // Navigation privee, stockage refuse : on reste au defaut.
            // / Private browsing or storage denied: stay on the default.
            return DEFAUT;
        }
    }

    /* L'attribut est TOUJOURS pose, jamais retire : c'est lui qui bat le
       `@media (prefers-color-scheme: dark)` de la feuille de style.
       / Always set, never removed: it is what beats the media query. */
    function appliquerTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
    }

    function rafraichirBouton(theme) {
        var bouton = document.getElementById("bascule-theme");
        if (!bouton) { return; }
        var libelle = LIBELLES[theme];
        var vers = theme === "dark" ? LIBELLES.light : LIBELLES.dark;
        bouton.textContent = libelle.glyphe;
        // Le titre dit l'etat ET le geste : un glyphe seul ne dit ni
        // l'un ni l'autre. / State and gesture, not just a glyph.
        bouton.title = "Thème " + libelle.mot + " — passer en " + vers.mot;
        bouton.setAttribute(
            "aria-label", "Thème " + libelle.mot + ". Passer en " + vers.mot + "."
        );
        // `aria-pressed` dit l'etat aux lecteurs d'ecran sans dependre du
        // libelle. / aria-pressed states it without relying on wording.
        bouton.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    }

    function basculerTheme() {
        var suivant = lireThemeStocke() === "dark" ? "light" : "dark";
        try {
            window.localStorage.setItem(CLE, suivant);
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
