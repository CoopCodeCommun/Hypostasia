/**
 * Logique de la sidebar de l'extension navigateur.
 * Affiche les arguments/extractions d'une page via l'endpoint /api/sidebar/.
 * Charge serverUrl et token depuis chrome.storage.sync.
 * / Browser extension sidebar logic.
 * Displays page arguments/extractions via /api/sidebar/ endpoint.
 * Loads serverUrl and token from chrome.storage.sync.
 *
 * LOCALISATION : extension/sidebar.js
 *
 * COMMUNICATION :
 * - Appelle GET /api/sidebar/?url=... pour recuperer le HTML sidebar
 * - Envoie postMessage('close_sidebar') au parent pour fermer
 * - Envoie postMessage('scroll_to_text') au parent pour scroller
 */

// Recuperer l'URL de la page parente via les parametres URL de l'iframe
// / Get parent page URL from iframe URL parameters
const urlParams = new URLSearchParams(window.location.search);
const parentUrl = urlParams.get('parentUrl');

// Configurer le bouton
document.addEventListener('DOMContentLoaded', async () => {
    // Charger serverUrl et token depuis le storage
    // / Load serverUrl and token from storage
    const config = await new Promise(resolve => {
        chrome.storage.sync.get({
            serverUrl: 'https://beta.hypostasia.org/',
            apiKey: '',
        }, resolve);
    });

    const url_serveur = config.serverUrl || 'https://beta.hypostasia.org/';
    const token_api = config.apiKey || '';

    const bouton_analyser = document.getElementById('btn-analyze');
    if (parentUrl && bouton_analyser) {
        // Construire l'URL vers l'endpoint sidebar avec l'URL du serveur configuree
        // / Build URL to sidebar endpoint with configured server URL
        const url_endpoint_sidebar = `${url_serveur}api/sidebar/?url=${encodeURIComponent(parentUrl)}`;

        bouton_analyser.addEventListener('click', () => {
            const indicateur_chargement = document.getElementById('ag-loading');
            if (indicateur_chargement) indicateur_chargement.style.opacity = '1';

            // Construire les headers avec le token si present
            // / Build headers with token if available
            var headers_fetch = {};
            if (token_api) {
                headers_fetch['Authorization'] = 'Token ' + token_api;
            }

            fetch(url_endpoint_sidebar, { headers: headers_fetch })
                .then(function(reponse_fetch) {
                    if (!reponse_fetch.ok) throw new Error('Network response was not ok');
                    return reponse_fetch.text();
                })
                .then(function(html_sidebar) {
                    var conteneur_sidebar = document.getElementById('sidebar-content');
                    conteneur_sidebar.innerHTML = html_sidebar;
                    // On tente d'activer HTMX pour les interactions internes (bouton relancer)
                    // / Try to activate HTMX for internal interactions (relaunch button)
                    if (window.htmx) {
                        try {
                            window.htmx.process(conteneur_sidebar);
                        } catch (erreur_htmx) { console.warn("HTMX process failed", erreur_htmx); }
                    }
                })
                .catch(function(erreur_fetch) {
                    console.error("Fetch error:", erreur_fetch);
                    var conteneur_sidebar = document.getElementById('sidebar-content');
                    conteneur_sidebar.innerHTML = `<div style="padding:20px; color:red;">Erreur: ${erreur_fetch.message}</div>`;
                });
        });
    }

    const bouton_fermer = document.querySelector('.ag-close');
    if (bouton_fermer) {
        bouton_fermer.addEventListener('click', closeSidebar);
    }
});

function closeSidebar() {
    // Envoyer un message au parent pour fermer
    window.parent.postMessage({ action: 'close_sidebar' }, '*');
}

// Delegation d'evenements pour le scroll vers un passage — compatible CSP
// / Event delegation for scrolling to a passage — CSP compliant
document.body.addEventListener('click', function(evenement_clic) {
    var element_declencheur = evenement_clic.target.closest('.ag-scroll-trigger');
    if (element_declencheur) {
        var texte_passage = element_declencheur.dataset.scrollText;
        if (texte_passage) {
            console.log("PostMessage Scroll Triggered:", texte_passage.substring(0, 20) + "...");
            window.parent.postMessage({ action: 'scroll_to_text', text: texte_passage }, '*');
        }
    }
});
