// Récupérer l'URL de la page parente via les paramètres URL de l'iframe
const urlParams = new URLSearchParams(window.location.search);
const parentUrl = urlParams.get('parentUrl');

// Configurer le bouton
document.addEventListener('DOMContentLoaded', () => {
    // Configurer le bouton
    const btn = document.getElementById('btn-analyze');
    if (parentUrl && btn) {
        const targetUrl = `http://127.0.0.1:8000/api/test-sidebar/?url=${encodeURIComponent(parentUrl)}`;

        btn.addEventListener('click', () => {
            const loader = document.getElementById('ag-loading');
            if (loader) loader.style.opacity = '1';

            fetch(targetUrl)
                .then(response => {
                    if (!response.ok) throw new Error('Network response was not ok');
                    return response.text();
                })
                .then(html => {
                    const container = document.getElementById('sidebar-content');
                    container.innerHTML = html;
                    // On tente d'activer HTMX pour les interactions internes (bouton relancer)
                    // Mais on le fait sans push d'URL
                    if (window.htmx) {
                        try {
                            window.htmx.process(container);
                        } catch (e) { console.warn("HTMX process failed", e); }
                    }
                })
                .catch(err => {
                    console.error("Fetch error:", err);
                    const container = document.getElementById('sidebar-content');
                    container.innerHTML = `<div style="padding:20px; color:red;">Erreur: ${err.message}</div>`;
                });
        });
    }

    const closeBtn = document.querySelector('.ag-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeSidebar);
    }
});

function closeSidebar() {
    // Envoyer un message au parent pour fermer
    window.parent.postMessage({ action: 'close_sidebar' }, '*');
}

// Event delegation for scrolling - CSP Compliant
document.body.addEventListener('click', (e) => {
    const trigger = e.target.closest('.ag-scroll-trigger');
    if (trigger) {
        const text = trigger.dataset.scrollText;
        if (text) {
            console.log("PostMessage Scroll Triggered:", text.substring(0, 20) + "...");
            window.parent.postMessage({ action: 'scroll_to_text', text: text }, '*');
        }
    }
});

// Mock global function - No longer needed for clicks but kept for backward compat if needed
window.hypostasiaScrollToText = function (textSnippet) {
    // ... kept just in case
};


