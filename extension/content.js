// Hypostasia Content Script
(function () {
    // Écoute des messages venant du background script
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === "toggle_sidebar") {
            toggleSidebar();
        }
    });

    let sidebarVisible = false;

    // Création des styles CSS
    function createStyles() {
        if (document.getElementById('hypostasia-styles')) return;
        const style = document.createElement('style');
        style.id = 'hypostasia-styles';
        style.textContent = `
            #hypostasia-sidebar-container {
                position: fixed;
                top: 0;
                right: -350px;
                width: 350px;
                height: 100vh;
                z-index: 2147483647; /* Max Z-index */
                transition: right 0.3s ease;
                box-shadow: -2px 0 5px rgba(0,0,0,0.1);
                background: white;
            }
            #hypostasia-sidebar-container.visible { right: 0; }
            
            #hypostasia-sidebar-iframe {
                width: 100%;
                height: 100%;
                border: none;
                display: block;
            }

            .ag-highlight { background-color: rgba(255, 235, 59, 0.4); border-bottom: 2px solid #fbc02d; transition: background 0.5s; }
        `;
        document.head.appendChild(style);
    }

    // Gestion de l'affichage de la sidebar
    function toggleSidebar() {
        // Injection initiale si nécessaire
        if (!document.getElementById('hypostasia-sidebar-container')) {
            createStyles();
            injectSidebarIframe();
            setupMessageListener();
        }

        sidebarVisible = !sidebarVisible;
        const container = document.getElementById('hypostasia-sidebar-container');
        if (sidebarVisible) {
            container.classList.add('visible');
        } else {
            container.classList.remove('visible');
        }
    }

    // Création du container et de l'iframe
    function injectSidebarIframe() {
        const container = document.createElement('div');
        container.id = 'hypostasia-sidebar-container';

        const iframe = document.createElement('iframe');
        iframe.id = 'hypostasia-sidebar-iframe';
        // On passe l'URL courante en paramètre pour que la sidebar sache quoi analyser
        const sidebarUrl = chrome.runtime.getURL('sidebar.html') + `?parentUrl=${encodeURIComponent(window.location.href)}`;
        iframe.src = sidebarUrl;

        container.appendChild(iframe);
        document.body.appendChild(container);
    }

    // Ecoute des messages venant de l'iframe (Scroll, Close)
    function setupMessageListener() {
        window.addEventListener('message', (event) => {
            // Sécurité basique : on pourrait vérifier event.origin mais c'est chrome-extension://...
            if (!event.data) return;

            if (event.data.action === 'close_sidebar') {
                toggleSidebar();
            }
            else if (event.data.action === 'scroll_to_text') {
                scrollToText(event.data.text);
            }
        });
    }

    // --- Fonctions utilitaires (Scroll) ---

    function scrollToText(textSnippet) {
        // (Copie simplifiée de la logique de scroll précédente)
        console.log("Hypostasia: Scrolling...", textSnippet.substring(0, 20));

        const cleanSnippet = textSnippet.trim().replace(/\s+/g, ' ');

        // On reset la sélection pour utiliser window.find proprement
        window.getSelection().removeAllRanges();

        // Stratégie simple : window.find
        const found = window.find(cleanSnippet, false, false, true, false, false, false);

        if (found) {
            const selection = window.getSelection();
            if (selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                const element = range.commonAncestorContainer.parentElement;
                if (element) {
                    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    element.classList.add('ag-highlight');
                    setTimeout(() => element.classList.remove('ag-highlight'), 2000);
                }
            }
        } else {
            console.warn("Texte non trouvé via window.find");
        }
        window.getSelection().removeAllRanges();
    }

    // Exposure globale
    window.hypostasiaScrollToText = scrollToText;

})();
