/**
 * Menu utilisateur : fermeture au clic exterieur, a l'Echap, et etat
 * annonce (aria-expanded).
 * / User menu: close on outside click and on Escape, with aria-expanded.
 *
 * Le bouton porte aria-expanded : sans lui, un lecteur d'ecran annonce
 * un bouton sans jamais dire s'il a ouvert quelque chose. C'est un des
 * restes d'accessibilite de PLAN/archive/cahiers-des-charges/bascule-css-etat-2026-08-09.md.
 * / Without aria-expanded a screen reader never learns the menu opened.
 *
 * LOCALISATION : front/static/front/js/user_menu.js
 */
(function() {
    "use strict";

    function elements() {
        return {
            conteneur: document.getElementById('user-menu-container'),
            dropdown: document.getElementById('user-menu-dropdown'),
            bouton: document.getElementById('btn-user-menu')
        };
    }

    function fermer(rendreLeFocus) {
        var e = elements();
        if (!e.dropdown) { return; }
        e.dropdown.classList.add('hidden');
        if (e.bouton) {
            e.bouton.setAttribute('aria-expanded', 'false');
            if (rendreLeFocus) { e.bouton.focus(); }
        }
    }

    // L'ouverture est faite par un onclick inline dans base.html : on se
    // contente de refleter l'etat reel apres coup.
    // / Opening is done by an inline onclick; we mirror the state.
    document.addEventListener('click', function(evenement) {
        var e = elements();
        if (!e.conteneur || !e.dropdown) { return; }
        if (!e.conteneur.contains(evenement.target)) {
            fermer(false);
            return;
        }
        if (e.bouton && e.bouton.contains(evenement.target)) {
            var estOuvert = !e.dropdown.classList.contains('hidden');
            e.bouton.setAttribute('aria-expanded', estOuvert ? 'true' : 'false');
        }
    });

    // Echap ferme et REND le focus au bouton : sans cela, le focus reste
    // dans un panneau devenu invisible. / Escape closes and returns focus.
    document.addEventListener('keydown', function(evenement) {
        if (evenement.key !== 'Escape') { return; }
        var e = elements();
        if (!e.dropdown || e.dropdown.classList.contains('hidden')) { return; }
        fermer(true);
    });
})();
