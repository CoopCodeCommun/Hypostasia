/**
 * Dashboard consensus — PHASE-14
 * Gere l'ouverture, la fermeture et le rechargement du dropdown dashboard
 * ancre au bouton toolbar "Dashboard". Charge le contenu via HTMX GET.
 * / Consensus dashboard — PHASE-14
 * / Manages open, close and reload of the dashboard dropdown
 * / anchored to the "Dashboard" toolbar button. Loads content via HTMX GET.
 *
 * LOCALISATION : front/static/front/js/dashboard_consensus.js
 *
 * COMMUNICATION :
 * Ecoute : clic sur #btn-toolbar-dashboard (toggle)
 * Ecoute : keydown Escape (ferme si ouvert, capture phase, apres drawer)
 * Ecoute : clic outside (ferme)
 * Ecoute : clic delegue sur .dashboard-bloquant (scroll texte + carte inline)
 * Ecoute : htmx event dashboardReload (recharge si ouvert)
 * Expose : window.dashboardConsensus = { ouvrir, fermer, basculer, estOuvert }
 */
(function() {
    'use strict';

    var boutonToolbar = document.getElementById('btn-toolbar-dashboard');
    var dropdown = document.getElementById('dashboard-consensus-dropdown');
    var contenu = document.getElementById('dashboard-consensus-contenu');

    var dashboardEstOuvert = false;

    // Recupere le page_id depuis la zone de lecture
    // / Get page_id from reading zone
    function getPageId() {
        var elementPage = document.querySelector('#zone-lecture [data-page-id]');
        if (!elementPage) return null;
        return elementPage.dataset.pageId;
    }

    // Charge le contenu du dashboard via HTMX
    // / Load dashboard content via HTMX
    function chargerContenu() {
        var pageId = getPageId();
        if (!pageId) {
            contenu.innerHTML = '<p class="text-xs text-slate-400 text-center py-4">Aucune page s\u00e9lectionn\u00e9e.</p>';
            return;
        }

        htmx.ajax('GET', '/extractions/dashboard/?page_id=' + pageId, {
            target: '#dashboard-consensus-contenu',
            swap: 'innerHTML',
        });
    }

    // Ouvre le dropdown dashboard
    // / Open the dashboard dropdown
    function ouvrirDashboard() {
        if (dashboardEstOuvert) return;

        var pageId = getPageId();
        if (!pageId) {
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'warning',
                title: 'Aucune page s\u00e9lectionn\u00e9e',
                showConfirmButton: false,
                timer: 2000,
                timerProgressBar: true,
            });
            return;
        }

        dashboardEstOuvert = true;
        dropdown.classList.remove('hidden');
        chargerContenu();
    }

    // Ferme le dropdown dashboard
    // / Close the dashboard dropdown
    function fermerDashboard() {
        if (!dashboardEstOuvert) return;
        dashboardEstOuvert = false;
        dropdown.classList.add('hidden');
        boutonToolbar.focus();
    }

    // Bascule ouvert/ferme
    // / Toggle open/close
    function basculerDashboard() {
        if (dashboardEstOuvert) {
            fermerDashboard();
        } else {
            ouvrirDashboard();
        }
    }

    // --- Evenements ---
    // --- Events ---

    // Clic bouton toolbar → bascule
    // / Toolbar button click → toggle
    boutonToolbar.addEventListener('click', basculerDashboard);

    // NOTE : Le raccourci Escape est gere par keyboard.js (PHASE-17)
    // / NOTE: Escape shortcut is handled by keyboard.js (PHASE-17)

    // Clic en dehors du dropdown → ferme
    // / Click outside dropdown → close
    document.addEventListener('click', function(evenement) {
        if (!dashboardEstOuvert) return;

        // Ne pas fermer si le clic est dans le dropdown ou sur le bouton toolbar
        // / Don't close if click is inside dropdown or on toolbar button
        if (dropdown.contains(evenement.target) || boutonToolbar.contains(evenement.target)) {
            return;
        }

        fermerDashboard();
    });

    // Clic delegue sur un bloquant → scroll texte + carte inline
    // / Delegated click on blocker → scroll text + inline card
    dropdown.addEventListener('click', function(evenement) {
        var boutonBloquant = evenement.target.closest('.dashboard-bloquant');
        if (!boutonBloquant) return;

        var extractionId = boutonBloquant.dataset.extractionId;
        if (!extractionId) return;

        // Chercher le span correspondant dans le texte
        // / Find the corresponding span in the text
        var spanDansTexte = document.querySelector(
            '#readability-content .hl-extraction[data-extraction-id="' + extractionId + '"]'
        );

        if (spanDansTexte) {
            // Scroll vers le span / Scroll to span
            spanDansTexte.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Activer le surlignage / Activate highlighting
            document.querySelectorAll('.hl-extraction.ancre-active').forEach(function(el) {
                el.classList.remove('ancre-active');
            });
            spanDansTexte.classList.add('ancre-active');

            // Charger la carte inline / Load inline card
            var blocParent = spanDansTexte.closest('p, div, blockquote, li, h1, h2, h3, h4, h5, h6');
            if (blocParent && blocParent.id !== 'readability-content') {
                var carteExistante = document.querySelector('.carte-inline[data-extraction-id="' + extractionId + '"]');
                if (!carteExistante) {
                    var divTemporaire = document.createElement('div');
                    divTemporaire.style.display = 'none';
                    document.body.appendChild(divTemporaire);

                    htmx.ajax('GET', '/extractions/carte_inline/?entity_id=' + extractionId, {
                        target: divTemporaire,
                        swap: 'innerHTML',
                    }).then(function() {
                        var contenuCarte = divTemporaire.firstElementChild;
                        if (contenuCarte) {
                            blocParent.insertAdjacentElement('afterend', contenuCarte);
                            htmx.process(contenuCarte);
                        }
                        divTemporaire.remove();
                    });
                }
            }
        }

        // Fermer le dashboard apres navigation
        // / Close dashboard after navigation
        fermerDashboard();
    });

    // Event listener dashboardReload : si dashboard ouvert, recharge contenu
    // / dashboardReload event listener: if dashboard open, reload content
    document.body.addEventListener('dashboardReload', function() {
        if (dashboardEstOuvert) {
            chargerContenu();
        }
    });

    // Recharger apres un swap HTMX sur la zone de lecture (changement de page)
    // / Reload after HTMX swap on reading zone (page change)
    document.body.addEventListener('htmx:afterSwap', function(evenement) {
        var cible = evenement.detail.target;
        if (cible && cible.id === 'zone-lecture' && dashboardEstOuvert) {
            chargerContenu();
        }
    });

    // Expose l'API publique
    // / Expose public API
    window.dashboardConsensus = {
        ouvrir: ouvrirDashboard,
        fermer: fermerDashboard,
        basculer: basculerDashboard,
        estOuvert: function() { return dashboardEstOuvert; },
    };

})();

/**
 * Ouvre une modale de confirmation avant de lancer la synthese deliberative.
 * Si le seuil est atteint : message simple. Sinon : avertissement renforce.
 * / Opens a confirmation modal before launching deliberative synthesis.
 * / If threshold is met: simple message. Otherwise: reinforced warning.
 *
 * LOCALISATION : front/static/front/js/dashboard_consensus.js
 */
function ouvrirModaleSynthese(pageId, seuilAtteint, pourcentage, seuil) {
    'use strict';

    // Supprimer une eventuelle modale existante / Remove any existing modal
    var modaleExistante = document.getElementById('modale-synthese');
    if (modaleExistante) modaleExistante.remove();

    // Construire le message selon le seuil / Build message based on threshold
    var titreModale = seuilAtteint
        ? 'Lancer la synthèse délibérative'
        : '⚠ Seuil de consensus non atteint';

    var messageModale = seuilAtteint
        ? '<p class="text-sm text-slate-600 mb-3">Vous allez générer une nouvelle version du texte intégrant le débat structuré (hypostases + commentaires + statuts).</p>'
        : '<p class="text-sm text-amber-700 mb-2 font-semibold">Le seuil de consensus n\'est pas atteint (' + pourcentage + '% / ' + seuil + '%).</p>'
          + '<p class="text-sm text-slate-600 mb-3">Le cycle de débat est encore vierge ou incomplet. La synthèse générée sera basée sur des données partielles. Vous pouvez continuer la curation avant de synthétiser.</p>';

    // Construire le HTML de la modale / Build modal HTML
    var htmlModale = ''
        + '<div id="modale-synthese" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" role="dialog" aria-modal="true" aria-labelledby="titre-modale-synthese">'
        + '  <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">'
        + '    <h3 id="titre-modale-synthese" class="text-lg font-semibold text-slate-800 mb-3">' + titreModale + '</h3>'
        + '    ' + messageModale
        + '    <div class="flex justify-end gap-2 mt-4">'
        + '      <button onclick="fermerModaleSynthese()" class="px-4 py-2 text-sm text-slate-600 bg-slate-100 rounded hover:bg-slate-200">Annuler</button>'
        + '      <button class="px-4 py-2 text-sm text-white rounded ' + (seuilAtteint ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-amber-600 hover:bg-amber-700') + '"'
        + '              hx-post="/lire/' + pageId + '/synthetiser/"'
        + '              hx-target="#zone-btn-synthese"'
        + '              hx-swap="outerHTML"'
        + '              hx-on::after-request="fermerModaleSynthese()">'
        + '        Confirmer la synthèse'
        + '      </button>'
        + '    </div>'
        + '  </div>'
        + '</div>';

    // Inserer dans le DOM et activer HTMX / Insert into DOM and activate HTMX
    document.body.insertAdjacentHTML('beforeend', htmlModale);
    var elementModale = document.getElementById('modale-synthese');
    htmx.process(elementModale);

    // Fermer via clic sur le backdrop / Close on backdrop click
    elementModale.addEventListener('click', function(evenement) {
        if (evenement.target === elementModale) {
            fermerModaleSynthese();
        }
    });
}

/**
 * Ferme la modale de synthese / Close the synthesis modal
 */
function fermerModaleSynthese() {
    var modale = document.getElementById('modale-synthese');
    if (modale) modale.remove();
}
