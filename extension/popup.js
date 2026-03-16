/**
 * Logique principale de la popup de l'extension navigateur.
 * Gere la recolte de contenu, l'authentification par token,
 * et le classement dans les dossiers apres recolte.
 * / Main popup logic for the browser extension.
 * Handles content harvesting, token authentication,
 * and folder classification after harvest.
 *
 * LOCALISATION : extension/popup.js
 *
 * COMMUNICATION :
 * - Appelle GET /api/pages/ pour verifier les doublons
 * - Appelle GET /api/pages/me/ pour verifier le token
 * - Appelle POST /api/pages/ pour creer une page
 * - Appelle GET /api/pages/mes_dossiers/ pour lister les dossiers
 * - Appelle POST /api/pages/{id}/classer_depuis_extension/ pour classer
 */
document.addEventListener('DOMContentLoaded', async () => {
    const recolterBtn = document.getElementById('recolterBtn');
    const statusDiv = document.getElementById('status');
    const serverUrlInput = document.getElementById('serverUrl');
    const indicateur_point = document.getElementById('serverStatusDot');
    const indicateur_texte = document.getElementById('serverStatusText');
    const zone_auth = document.getElementById('authStatus');
    const zone_dossiers = document.getElementById('dossiersChoix');
    const liste_dossiers = document.getElementById('dossiersListe');

    // Charger l'adresse serveur et le token depuis le storage
    // / Load server URL and token from storage
    const config = await new Promise(resolve => {
        chrome.storage.sync.get({
            serverUrl: 'http://127.0.0.1:8000/',
            apiKey: '',
        }, resolve);
    });
    serverUrlInput.value = config.serverUrl;

    // Token d'authentification charge depuis le storage
    // / Authentication token loaded from storage
    var token_api = config.apiKey || '';

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

    /**
     * Normalise une URL de page pour la comparaison :
     * - Retire les parametres UTM (utm_source, utm_medium, utm_campaign, etc.)
     * - Retire le fragment (#...)
     * - Retire le trailing slash
     * / Normalize a page URL for comparison:
     * - Remove UTM parameters (utm_source, utm_medium, utm_campaign, etc.)
     * - Remove fragment (#...)
     * - Remove trailing slash
     */
    function normaliserUrlPage(url_brute) {
        try {
            var url_parsee = new URL(url_brute);

            // Retirer le fragment / Remove fragment
            url_parsee.hash = '';

            // Retirer les parametres UTM et de tracking courants
            // / Remove UTM and common tracking parameters
            var parametres_tracking = [
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'ref', 'mc_cid', 'mc_eid',
            ];
            parametres_tracking.forEach(function(param) {
                url_parsee.searchParams.delete(param);
            });

            var url_normalisee = url_parsee.toString();

            // Retirer le trailing slash (sauf si l'URL est juste l'origin + /)
            // / Remove trailing slash (unless URL is just origin + /)
            if (url_normalisee.endsWith('/') && url_parsee.pathname !== '/') {
                url_normalisee = url_normalisee.slice(0, -1);
            }

            return url_normalisee;
        } catch (e) {
            // URL invalide, retourner telle quelle
            // / Invalid URL, return as-is
            return url_brute;
        }
    }

    /**
     * Calcule le hash SHA-256 d'une chaine de texte.
     * Utilise l'API Web Crypto disponible dans les extensions Chrome.
     * / Compute SHA-256 hash of a text string.
     * / Uses the Web Crypto API available in Chrome extensions.
     */
    async function calculerHashContenu(texte) {
        var donnees_encodees = new TextEncoder().encode(texte);
        var buffer_hash = await crypto.subtle.digest('SHA-256', donnees_encodees);
        var tableau_octets = Array.from(new Uint8Array(buffer_hash));
        var hash_hexadecimal = tableau_octets.map(function(octet) {
            return octet.toString(16).padStart(2, '0');
        }).join('');
        return hash_hexadecimal;
    }

    /**
     * Extrait le texte brut depuis du HTML (retire les balises).
     * Utilise un DOMParser cote extension pour mimer le comportement serveur.
     * / Extract plain text from HTML (strip tags).
     * / Uses DOMParser on the extension side to mimic server behavior.
     */
    function extraireTexteBrut(html) {
        var parser = new DOMParser();
        var document_parse = parser.parseFromString(html, 'text/html');
        return document_parse.body.textContent || '';
    }

    /**
     * Construit les headers HTTP avec le token d'authentification si present.
     * / Build HTTP headers with authentication token if available.
     */
    function construireHeaders(content_type) {
        var headers = { 'Accept': 'application/json' };
        if (content_type) {
            headers['Content-Type'] = content_type;
        }
        if (token_api) {
            headers['Authorization'] = 'Token ' + token_api;
        }
        return headers;
    }

    // --- Indicateur de statut serveur / Server status indicator ---

    /**
     * Verifie si le serveur est joignable via un appel GET /api/pages/
     * et met a jour l'indicateur visuel dans la popup.
     * / Check if the server is reachable via GET /api/pages/
     * / and update the visual indicator in the popup.
     */
    async function verifierStatutServeur() {
        try {
            var reponse = await fetch(getBaseUrl() + 'api/pages/', {
                headers: construireHeaders(),
                signal: AbortSignal.timeout(3000),
            });
            if (reponse.ok) {
                indicateur_point.className = 'online';
                indicateur_texte.textContent = 'Serveur connecte';
            } else {
                indicateur_point.className = 'offline';
                indicateur_texte.textContent = 'Serveur erreur (' + reponse.status + ')';
            }
        } catch (erreur) {
            indicateur_point.className = 'offline';
            indicateur_texte.textContent = 'Serveur hors ligne';
        }
    }

    /**
     * Verifie l'authentification via /api/pages/me/ et affiche le statut.
     * / Check authentication via /api/pages/me/ and display status.
     */
    async function verifierAuthentification() {
        if (!token_api) {
            zone_auth.textContent = 'Non connecte (pas de token)';
            zone_auth.className = 'auth-ko';
            return;
        }
        try {
            var reponse = await fetch(getBaseUrl() + 'api/pages/me/', {
                headers: construireHeaders(),
                signal: AbortSignal.timeout(3000),
            });
            if (reponse.ok) {
                var donnees = await reponse.json();
                if (donnees.authenticated) {
                    zone_auth.textContent = 'Connecte : ' + donnees.username;
                    zone_auth.className = 'auth-ok';
                } else {
                    zone_auth.textContent = 'Non connecte';
                    zone_auth.className = 'auth-ko';
                }
            } else {
                zone_auth.textContent = 'Token invalide';
                zone_auth.className = 'auth-ko';
            }
        } catch (erreur) {
            zone_auth.textContent = '';
        }
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
        saveUrlBtn.textContent = '\u2713';
        setTimeout(function() { saveUrlBtn.textContent = 'OK'; }, 800);

        // Re-verifier le statut avec la nouvelle URL
        // / Re-check status with the new URL
        verifierStatutServeur();
        verifierAuthentification();
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

    // Verifier le statut et l'auth au chargement de la popup
    // / Check status and auth on popup load
    verifierStatutServeur();
    verifierAuthentification();

    // --- Bouton principal : recolter le contenu de la page ---
    // / Main button: harvest page content
    recolterBtn.addEventListener('click', async () => {
        recolterBtn.disabled = true;
        recolterBtn.textContent = "Recolte...";
        statusDiv.textContent = "";
        statusDiv.className = "";
        zone_dossiers.style.display = 'none';

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
     * 1. Normaliser l'URL et verifier si la page existe deja sur le serveur
     * 2. Si non, extraire le contenu via Readability, calculer le content_hash et l'envoyer
     * 3. Le serveur verifie le doublon par URL normalisee et par content_hash
     * / Main harvesting flow:
     * 1. Normalize URL and check if page already exists on server
     * 2. If not, extract content via Readability, compute content_hash and send it
     * 3. Server checks for duplicates by normalized URL and content_hash
     */
    async function recolterContenuPage() {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const url_courante = tab.url;
        const url_normalisee = normaliserUrlPage(url_courante);

        console.debug('[Hypostasia] URL courante:', url_courante);
        console.debug('[Hypostasia] URL normalisee:', url_normalisee);

        // 1. Verifier si la page existe deja (par URL normalisee)
        // / Check if page already exists (by normalized URL)
        statusDiv.textContent = "Verification...";
        const verification_response = await fetch(
            `${getBaseUrl()}api/pages/?url=${encodeURIComponent(url_normalisee)}`,
            { headers: construireHeaders() }
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

        // 3. Normaliser l'URL et calculer le content_hash cote extension
        // / Normalize the URL and compute content_hash on the extension side
        donnees_extraites.url = url_normalisee;

        var texte_brut_pour_hash = extraireTexteBrut(donnees_extraites.html_readability);
        var content_hash_calcule = await calculerHashContenu(texte_brut_pour_hash);
        donnees_extraites.content_hash = content_hash_calcule;

        console.debug('[Hypostasia] content_hash:', content_hash_calcule.substring(0, 16) + '...');

        // 4. Envoyer au serveur avec le token d'authentification
        // / Send to server with authentication token
        statusDiv.textContent = "Envoi...";
        console.debug('[Hypostasia] POST /api/pages/');

        const creation_response = await fetch(`${getBaseUrl()}api/pages/`, {
            method: 'POST',
            headers: construireHeaders('application/json'),
            body: JSON.stringify(donnees_extraites)
        });

        if (!creation_response.ok) {
            const texte_erreur = await creation_response.text();
            console.error('[Hypostasia] Erreur creation:', creation_response.status, texte_erreur);

            // Gerer le cas de doublon detecte par content_hash (409 Conflict)
            // / Handle duplicate detected by content_hash (409 Conflict)
            if (creation_response.status === 409) {
                var donnees_conflit = JSON.parse(texte_erreur);
                statusDiv.textContent = "Contenu identique deja enregistre (id: " + donnees_conflit.existing_page_id + ")";
                statusDiv.className = "success";
                recolterBtn.disabled = false;
                recolterBtn.textContent = "Recolter";
                return;
            }

            // Gerer le 401 (pas authentifie)
            // / Handle 401 (not authenticated)
            if (creation_response.status === 401) {
                statusDiv.textContent = "Token manquant ou invalide. Configurez-le dans les options.";
                statusDiv.className = "error";
                recolterBtn.disabled = false;
                recolterBtn.textContent = "Recolter";
                return;
            }

            throw new Error("Erreur creation (" + creation_response.status + ")");
        }

        const page_creee = await creation_response.json();
        console.debug('[Hypostasia] Page creee:', page_creee.id);

        // Succes / Success
        statusDiv.textContent = "Page enregistree (id: " + page_creee.id + ")";
        statusDiv.className = "success";
        recolterBtn.textContent = "Recolter";
        recolterBtn.disabled = false;

        // 5. Apres recolte reussie, afficher les dossiers pour classement
        // / After successful harvest, show folders for classification
        afficherDossiersPostRecolte(page_creee.id);
    }

    /**
     * Recupere les dossiers de l'utilisateur et les affiche comme boutons.
     * / Fetch user's folders and display them as buttons.
     */
    async function afficherDossiersPostRecolte(page_id) {
        if (!token_api) return;

        try {
            var reponse = await fetch(getBaseUrl() + 'api/pages/mes_dossiers/', {
                headers: construireHeaders(),
                signal: AbortSignal.timeout(3000),
            });
            if (!reponse.ok) return;

            var dossiers = await reponse.json();
            if (!dossiers || dossiers.length === 0) return;

            // Vider et remplir la liste de boutons
            // / Clear and populate button list
            liste_dossiers.innerHTML = '';
            dossiers.forEach(function(dossier) {
                // Ne pas afficher le dossier "A ranger" car c'est deja le defaut
                // / Don't show "A ranger" folder since it's already the default
                if (dossier.name === 'A ranger') return;

                var bouton = document.createElement('button');
                bouton.className = 'btn-dossier';
                bouton.textContent = dossier.name;
                bouton.addEventListener('click', function() {
                    classerPage(page_id, dossier.id, bouton);
                });
                liste_dossiers.appendChild(bouton);
            });

            // Afficher la zone seulement s'il y a des boutons
            // / Show zone only if there are buttons
            if (liste_dossiers.children.length > 0) {
                zone_dossiers.style.display = 'block';
            }
        } catch (erreur) {
            console.debug('[Hypostasia] Erreur chargement dossiers:', erreur);
        }
    }

    /**
     * Deplace une page dans un dossier via l'API.
     * / Move a page into a folder via API.
     */
    async function classerPage(page_id, dossier_id, bouton_clique) {
        try {
            var reponse = await fetch(
                getBaseUrl() + 'api/pages/' + page_id + '/classer_depuis_extension/',
                {
                    method: 'POST',
                    headers: construireHeaders('application/json'),
                    body: JSON.stringify({ dossier_id: dossier_id }),
                }
            );
            if (reponse.ok) {
                var donnees = await reponse.json();
                bouton_clique.className = 'btn-dossier selected';
                statusDiv.textContent = 'Classee dans "' + donnees.dossier_name + '"';

                // Desactiver tous les boutons apres classement
                // / Disable all buttons after classification
                var tous_les_boutons = liste_dossiers.querySelectorAll('.btn-dossier');
                tous_les_boutons.forEach(function(btn) {
                    btn.disabled = true;
                    btn.style.cursor = 'default';
                });
            } else {
                console.error('[Hypostasia] Erreur classement:', reponse.status);
            }
        } catch (erreur) {
            console.error('[Hypostasia] Erreur classement:', erreur);
        }
    }
});
