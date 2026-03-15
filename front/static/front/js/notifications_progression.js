/**
 * Notifications de progression (PHASE-20)
 * Gere le bandeau de notification via localStorage + HTMX.
 *
 * COMMUNICATION :
 * Lit : localStorage 'hypostasia-derniere-visite-{pageId}'
 * Appelle : GET /lire/{pageId}/notifications/?derniere_visite=ISO (via htmx.ajax)
 * Ecrit : #bandeau-notifications (outerHTML swap)
 * Expose : window.notificationsProgression = { marquerVu }
 *
 * / Progression notifications (PHASE-20)
 * / Manages the notification banner via localStorage + HTMX.
 */
(function() {
    'use strict';

    // Cle localStorage prefixee par l'ID de page
    // / localStorage key prefixed by page ID
    var CLE_PREFIX = 'hypostasia-derniere-visite-';

    /**
     * Recupere l'ID de la page courante depuis data-page-id
     * / Retrieve current page ID from data-page-id
     */
    function obtenirPageId() {
        // Cible la zone de lecture principale (pas l'arbre de dossiers qui a aussi data-page-id)
        // / Target the main reading zone (not the folder tree which also has data-page-id)
        var zoneLecture = document.querySelector('[data-testid="lecture-zone-principale"]');
        if (zoneLecture) {
            return zoneLecture.dataset.pageId;
        }
        return null;
    }

    /**
     * Marque la page comme vue en posant le timestamp actuel dans localStorage.
     * Appelee a la fermeture du bandeau ou quand l'utilisateur quitte.
     * / Mark page as viewed by setting current timestamp in localStorage.
     * / Called when banner is closed or user leaves.
     */
    function marquerVu() {
        var pageId = obtenirPageId();
        if (pageId) {
            localStorage.setItem(CLE_PREFIX + pageId, new Date().toISOString());
        }
    }

    /**
     * Charge le bandeau de notification via HTMX pour la page courante.
     * Si c'est la premiere visite, pose le timestamp sans charger le bandeau.
     * / Load notification banner via HTMX for current page.
     * / On first visit, set timestamp without loading banner.
     */
    function chargerBandeauNotification() {
        var pageId = obtenirPageId();
        if (!pageId) {
            return;
        }

        var cle = CLE_PREFIX + pageId;
        var timestampDerniereVisite = localStorage.getItem(cle);

        // Premiere visite : on pose le timestamp, pas de bandeau
        // / First visit: set timestamp, no banner
        if (!timestampDerniereVisite) {
            localStorage.setItem(cle, new Date().toISOString());
            return;
        }

        // Visite suivante : requete HTMX pour charger le bandeau
        // / Subsequent visit: HTMX request to load banner
        var conteneur = document.getElementById('bandeau-notifications');
        if (!conteneur) {
            return;
        }

        if (typeof htmx !== 'undefined') {
            htmx.ajax('GET',
                '/lire/' + pageId + '/notifications/?derniere_visite=' + encodeURIComponent(timestampDerniereVisite),
                {
                    target: '#bandeau-notifications',
                    swap: 'outerHTML'
                }
            );
        }
    }

    // Charge le bandeau avec un petit delai apres le chargement du DOM
    // / Load banner with a small delay after DOM load
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(chargerBandeauNotification, 200);
    });

    // Apres navigation HTMX dans la zone lecture, recharger le bandeau
    // / After HTMX navigation in reading zone, reload banner
    document.addEventListener('htmx:afterSwap', function(evenement) {
        if (evenement.detail.target && evenement.detail.target.id === 'zone-lecture') {
            setTimeout(chargerBandeauNotification, 300);
        }
    });

    // API publique
    // / Public API
    window.notificationsProgression = {
        marquerVu: marquerVu,
        chargerBandeau: chargerBandeauNotification
    };

})();
