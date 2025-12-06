// Popup logic
document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyzeBtn');
    const status = document.getElementById('status');
    const actionsDiv = document.getElementById('actions');
    const viewArgsBtn = document.getElementById('viewArgsBtn');
    const relaunchBtn = document.getElementById('relaunchBtn');

    // Helper to set state
    function setUIState(state, message) {
        status.textContent = message;
        status.className = state === 'error' ? 'error' : (state === 'success' ? 'success' : '');

        if (state === 'processing') {
            analyzeBtn.disabled = true;
            analyzeBtn.textContent = "Analyse en cours...";
            actionsDiv.style.display = 'none';
        } else if (state === 'initial') {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = "Récolter & Analyser";
            actionsDiv.style.display = 'none';
        } else if (state === 'completed' || state === 'error_retry') {
            analyzeBtn.style.display = 'none'; // Hide main button once we know page exists
            actionsDiv.style.display = 'block';

            if (state === 'completed') {
                viewArgsBtn.style.display = 'block';
                relaunchBtn.textContent = "⚡ Relancer l'analyse";
            } else {
                viewArgsBtn.style.display = 'none';
                relaunchBtn.textContent = "🔄 Réessayer l'analyse";
            }
        }
    }

    // Main Entry Point
    analyzeBtn.addEventListener('click', async () => {
        setUIState('processing', "Vérification de la page...");
        try {
            await handleAnalysisFlow();
        } catch (e) {
            console.error(e);
            setUIState('error', "Erreur: " + e.message);
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = "Récolter & Analyser";
        }
    });

    // Sub-actions
    viewArgsBtn.addEventListener('click', async () => {
        if (window.currentPageId) {
            try {
                // Fetch arguments
                status.textContent = "Récupération des arguments...";
                const res = await fetch(`http://127.0.0.1:8000/api/pages/${window.currentPageId}/arguments/`);
                if (!res.ok) throw new Error("Erreur récupération arguments");
                const args = await res.json();

                // Inject UI with args
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                await injectUI(tab.id, args);

                window.close(); // Close popup
            } catch (e) {
                console.error(e);
                status.textContent = "Erreur: " + e.message;
                status.className = "error";
            }
        } else {
            status.textContent = "Erreur: ID de page manquant.";
            status.className = "error";
        }
    });

    relaunchBtn.addEventListener('click', async () => {
        status.textContent = "Relance de l'analyse...";
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            // We need pageId. It should be stored or re-fetched.
            // Simplified: we re-run flow but force analyze.
            // Better: store pageId in a global or attribute.
            if (window.currentPageId) {
                await fetch(`http://127.0.0.1:8000/api/pages/${window.currentPageId}/analyze/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                status.textContent = "Analyse lancée !";
                setTimeout(() => window.close(), 1000);
            } else {
                throw new Error("ID de page perdu. Veuillez recharger.");
            }
        } catch (e) {
            status.textContent = "Erreur: " + e.message;
            status.className = "error";
        }
    });

    // Core Logic
    async function handleAnalysisFlow() {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const currentUrl = tab.url;

        // 1. Check if page exists
        const checkRes = await fetch(`http://127.0.0.1:8000/api/pages/?url=${encodeURIComponent(currentUrl)}`, {
            headers: { 'Accept': 'application/json' }
        });

        if (!checkRes.ok) throw new Error("Erreur serveur (vérification)");

        const existingPages = await checkRes.json();

        if (existingPages.length > 0) {
            const page = existingPages[0];
            window.currentPageId = page.id;

            if (page.status === 'processing') {
                setUIState('processing', "Analyse en cours côté serveur...");
                return;
            }

            if (page.status === 'error') {
                setUIState('error_retry', `Erreur précédente : ${page.error_message}`);
                return;
            }

            // Completed / Pending
            setUIState('completed', "Page déjà analysée.");
            // We could fetch arg count here to be nice:
            const argsRes = await fetch(`http://127.0.0.1:8000/api/pages/${page.id}/arguments/`);
            const args = await argsRes.json();
            status.textContent = `${args.length} arguments disponibles.`;

        } else {
            // New Page
            status.textContent = "Extraction du contenu...";

            // Inject Readability then content script
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: ['lib/Readability.js', 'content.js']
            });

            const extractionResult = await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => { return window.hypostasiaExtract(); }
            });

            const data = extractionResult[0].result;
            if (data.error) throw new Error(data.error);

            status.textContent = "Création de la page...";
            const createRes = await fetch('http://127.0.0.1:8000/api/pages/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!createRes.ok) throw new Error("Erreur création page");
            const newPage = await createRes.json();
            window.currentPageId = newPage.id;

            status.textContent = "Lancement de l'analyse...";
            await fetch(`http://127.0.0.1:8000/api/pages/${newPage.id}/analyze/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            status.textContent = "Analyse lancée !";
            // We can close or switch to processing state
            setUIState('processing', "Analyse lancée. Vous pouvez fermer.");
            setTimeout(() => window.close(), 2000);
        }
    }

    async function injectUI(tabId, args) {
        // Ensure scripts are injected first.
        // It's safe to re-inject (content.js has a guard)
        try {
            await chrome.scripting.executeScript({
                target: { tabId: tabId },
                files: ['lib/Readability.js', 'content.js']
            });
        } catch (e) {
            console.warn("Script injection failed or already present:", e);
        }

        // Now trigger UI
        await chrome.scripting.executeScript({
            target: { tabId: tabId },
            func: (args) => {
                if (window.hypostasiaInjectUI) {
                    window.hypostasiaInjectUI(args);
                } else {
                    console.error("Hypostasia: injectUI not found even after injection attempt.");
                }
            },
            args: [args]
        });
    }

});
