// ==========================================================================
// ws_toast_autohide.js — Auto-suppression des toasts WebSocket
// / Auto-dismiss WebSocket toasts
//
// LOCALISATION : front/static/front/js/ws_toast_autohide.js
//
// Ecoute htmx:wsAfterMessage sur #ws-hub : chaque nouveau toast recoit
// un setTimeout qui ajoute ws-toast--sortie (fondu CSS) puis supprime le noeud.
// / Listens to htmx:wsAfterMessage on #ws-hub: each new toast gets a setTimeout
// / that adds ws-toast--sortie (CSS fade) then removes the node.
// ==========================================================================
(function () {
    'use strict';

    var delai_auto_suppression_ms = 6000;
    var hub_websocket = document.getElementById('ws-hub');
    if (!hub_websocket) { return; }

    hub_websocket.addEventListener('htmx:wsAfterMessage', function () {
        /* Trouve tous les toasts sans timer deja en cours */
        /* / Find all toasts without a timer already running */
        var tous_les_toasts = document.querySelectorAll('.ws-toast:not([data-autohide-set])');
        tous_les_toasts.forEach(function (toast_element) {
            toast_element.setAttribute('data-autohide-set', '1');
            setTimeout(function () {
                toast_element.classList.add('ws-toast--sortie');
                /* Supprime le noeud apres la fin de la transition CSS (300ms) */
                /* / Remove the node after the CSS transition ends (300ms) */
                setTimeout(function () {
                    if (toast_element.parentNode) {
                        toast_element.parentNode.removeChild(toast_element);
                    }
                }, 300);
            }, delai_auto_suppression_ms);
        });
    });
}());
