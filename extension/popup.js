// Popup logic — Recolte de contenu uniquement, pas d'analyse LLM
// / Popup logic — Content harvesting only, no LLM analysis
document.addEventListener('DOMContentLoaded', async () => {
    const recolterBtn = document.getElementById('recolterBtn');
    const statusDiv = document.getElementById('status');
    const serverUrlInput = document.getElementById('serverUrl');

    // Charger l'adresse serveur depuis le storage / Load server URL from storage
    const config = await new Promise(resolve => {
        chrome.storage.sync.get({
            serverUrl: 'http://127.0.0.1:8000/'
        }, resolve);
    });
    serverUrlInput.value = config.serverUrl;

    /**
     * Nettoie et normalise l'URL serveur :
     * - Ajoute http:// si pas de protocole
     * - Retire tout ce qui depasse le host+port (path, query, fragment)
     * - Garantit un / final
     * / Sanitize and normalize server URL:
     * - Add http:// if no protocol
     * - Strip everything beyond host+port
     * - Ensure trailing /
     */
    function sanitiserUrlServeur(url_brute) {
        var url_nettoyee = url_brute.trim();

        if (!url_nettoyee) {
            return 'http://127.0.0.1:8000/';
        }

        // Ajouter le protocole si absent / Add protocol if missing
        if (!url_nettoyee.match(/^https?:\/\//)) {
            url_nettoyee = 'http://' + url_nettoyee;
        }

        // Parser pour ne garder que origin (protocole + host + port)
        // / Parse to keep only origin (protocol + host + port)
        try {
            var url_parsee = new URL(url_nettoyee);
            url_nettoyee = url_parsee.origin + '/';
        } catch (e) {
            // URL invalide, on garde telle quelle avec un / final
            // / Invalid URL, keep as-is with trailing /
            if (!url_nettoyee.endsWith('/')) {
                url_nettoyee = url_nettoyee + '/';
            }
        }

        return url_nettoyee;
    }

    var saveUrlBtn = document.getElementById('saveUrlBtn');

    // Sanitiser et sauvegarder au clic sur OK
    // / Sanitize and save on OK click
    function sauvegarderUrlServeur() {
        var url_propre = sanitiserUrlServeur(serverUrlInput.value);
        serverUrlInput.value = url_propre;
        chrome.storage.sync.set({ serverUrl: url_propre });
        console.debug('[Hypostasia] serverUrl sauvegarde:', url_propre);

        // Feedback visuel bref / Brief visual feedback
        saveUrlBtn.textContent = '✓';
        setTimeout(function() { saveUrlBtn.textContent = 'OK'; }, 800);
    }

    saveUrlBtn.addEventListener('click', sauvegarderUrlServeur);

    /**
     * Recupere l'URL serveur courante depuis l'input
     * / Get current server URL from input
     */
    function getBaseUrl() {
        return sanitiserUrlServeur(serverUrlInput.value);
    }

    console.debug('[Hypostasia] BASE_URL:', getBaseUrl());

    // --- Bouton principal : recolter le contenu de la page ---
    // / Main button: harvest page content
    recolterBtn.addEventListener('click', async () => {
        recolterBtn.disabled = true;
        recolterBtn.textContent = "Recolte...";
        statusDiv.textContent = "";
        statusDiv.className = "";

        try {
            await recolterContenuPage();
        } catch (erreur) {
            console.error('[Hypostasia] Erreur recolte:', erreur);
            statusDiv.textContent = erreur.message;
            statusDiv.className = "error";
            recolterBtn.disabled = false;
            recolterBtn.textContent = "Recolter";
        }
    });

    /**
     * Flux principal de recolte :
     * 1. Verifier si la page existe deja sur le serveur
     * 2. Si non, extraire le contenu via Readability et l'envoyer
     * / Main harvesting flow:
     * 1. Check if page already exists on server
     * 2. If not, extract content via Readability and send it
     */
    async function recolterContenuPage() {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const url_courante = tab.url;

        console.debug('[Hypostasia] URL courante:', url_courante);

        // 1. Verifier si la page existe deja / Check if page already exists
        statusDiv.textContent = "Verification...";
        const verification_response = await fetch(
            `${getBaseUrl()}api/pages/?url=${encodeURIComponent(url_courante)}`,
            { headers: { 'Accept': 'application/json' } }
        );

        if (!verification_response.ok) {
            throw new Error("Erreur serveur: " + verification_response.status);
        }

        const pages_existantes = await verification_response.json();
        console.debug('[Hypostasia] Pages existantes:', pages_existantes.length);

        if (pages_existantes.length > 0) {
            // La page existe deja — on informe l'utilisateur
            // / Page already exists — inform user
            statusDiv.textContent = "Deja enregistree (id: " + pages_existantes[0].id + ")";
            statusDiv.className = "success";
            recolterBtn.disabled = false;
            recolterBtn.textContent = "Recolter";
            return;
        }

        // 2. Injecter Readability et extraire le contenu
        // / Inject Readability and extract content
        statusDiv.textContent = "Extraction...";
        console.debug('[Hypostasia] Injection Readability');

        await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['lib/Readability.js']
        });

        // Fonction d'extraction injectee dans la page
        // / Extraction function injected into the page
        const resultat_extraction = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => {
                try {
                    const document_clone = document.cloneNode(true);
                    const article_readability = new Readability(document_clone).parse();

                    if (!article_readability) {
                        return { error: "Readability n'a pas pu extraire le contenu." };
                    }

                    return {
                        url: window.location.href,
                        title: article_readability.title || document.title,
                        html_readability: article_readability.content || '',
                        html_original: document.documentElement.outerHTML
                    };
                } catch (e) {
                    return { error: e.message };
                }
            }
        });

        const donnees_extraites = resultat_extraction[0].result;
        console.debug('[Hypostasia] Donnees extraites:', {
            url: donnees_extraites.url,
            title: donnees_extraites.title,
            html_readability_length: donnees_extraites.html_readability?.length,
            html_original_length: donnees_extraites.html_original?.length,
        });

        if (donnees_extraites.error) {
            throw new Error(donnees_extraites.error);
        }

        // 3. Envoyer au serveur (stockage uniquement, pas d'analyse LLM)
        // / Send to server (storage only, no LLM analysis)
        statusDiv.textContent = "Envoi...";
        console.debug('[Hypostasia] POST /api/pages/');

        const creation_response = await fetch(`${getBaseUrl()}api/pages/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(donnees_extraites)
        });

        if (!creation_response.ok) {
            const texte_erreur = await creation_response.text();
            console.error('[Hypostasia] Erreur creation:', creation_response.status, texte_erreur);
            throw new Error("Erreur creation (" + creation_response.status + ")");
        }

        const page_creee = await creation_response.json();
        console.debug('[Hypostasia] Page creee:', page_creee.id);

        // Succes / Success
        statusDiv.textContent = "Page enregistree (id: " + page_creee.id + ")";
        statusDiv.className = "success";
        recolterBtn.textContent = "Recolte";
        recolterBtn.disabled = false;
    }
});
