/**
 * Logique principale de la popup de l'extension navigateur.
 * Choix du carnet, recolte du contenu, authentification par token.
 * / Main popup logic: notebook choice, content harvesting, token auth.
 *
 * LOCALISATION : extension/popup.js
 *
 * COMMUNICATION :
 * - GET  /api/pages/me/          verifie le serveur ET le token
 * - GET  /api/pages/mon_jeton/   recupere le jeton — SEUL appel avec cookies
 * - GET  /api/pages/mes_carnets/ remplit le menu des carnets
 * - GET  /api/pages/?url=        cherche un doublon dans MON perimetre
 * - POST /api/pages/             cree la note dans le carnet choisi
 *
 * LE CARNET SE CHOISIT AVANT LA CAPTURE, ET IL EST OBLIGATOIRE. La note
 * part directement a sa destination : `dossier_id` voyage avec le POST,
 * et le serveur refuse sans lui. L'ancien flux deposait la note dans un
 * carnet fourre-tout puis proposait des boutons de rangement — deux
 * gestes, et une note mal rangee si la popup se fermait entre les deux.
 * / The notebook is chosen before capture and is mandatory.
 */
document.addEventListener('DOMContentLoaded', async () => {
    const recolterBtn = document.getElementById('recolterBtn');
    const statusDiv = document.getElementById('status');
    const serverUrlInput = document.getElementById('serverUrl');
    const indicateur_point = document.getElementById('serverStatusDot');
    const indicateur_texte = document.getElementById('serverStatusText');
    const zone_auth = document.getElementById('authStatus');
    const menu_des_carnets = document.getElementById('carnetChoisi');
    const avertissement_carnet = document.getElementById('carnetAvertissement');
    const message_aucun_carnet = document.getElementById('carnetAucun');

    // Cle unique du souvenir de rangement. UN SEUL enregistrement, qui
    // porte un objet : une cle par couple serveur+compte ferait grossir
    // le stockage sans limite (chrome.storage.sync plafonne a 512
    // entrees) et rien ne viendrait jamais la purger.
    // / A single stored record holding a map: one key per server+account
    // would grow without bound against a 512-item quota, unpurged.
    const CLE_DU_SOUVENIR = 'dernierCarnetParCompte';
    const SOUVENIRS_GARDES = 20;

    // Charger l'adresse serveur et le token depuis le storage
    // / Load server URL and token from storage
    const config = await new Promise(resolve => {
        chrome.storage.sync.get({
            // LE DEFAUT NE VAUT QUE POUR UNE INSTALLATION NEUVE.
            // `storage.sync.get` ne rend cette valeur que si RIEN n'est
            // enregistre. Changer ce defaut un jour ne deplacera donc
            // personne qui a deja ouvert la popup une seule fois : il
            // faudra une migration explicite.
            // / The default applies to fresh installs only.
            serverUrl: 'https://beta.hypostasia.org/',
            apiKey: '',
            [CLE_DU_SOUVENIR]: {},
        }, resolve);
    });
    serverUrlInput.value = config.serverUrl;

    // Token d'authentification charge depuis le storage
    // / Authentication token loaded from storage
    var token_api = config.apiKey || '';

    // Le compte connecte, connu apres /api/pages/me/. Il entre dans la
    // cle du souvenir : deux comptes sur le meme serveur n'ont pas les
    // memes carnets, et un identifiant memorise pour l'un ne veut rien
    // dire pour l'autre.
    // / The logged-in account, part of the memory key: two accounts on
    // one server do not share notebooks.
    var nom_du_compte = '';

    // Les carnets rendus par le serveur, gardes pour la validation du
    // choix et l'avertissement « public ».
    // / The notebooks returned by the server.
    var carnets_recus = [];

    /**
     * Nettoie et normalise l'URL serveur :
     * - Ajoute http:// si pas de protocole
     * - Retire tout ce qui depasse le host+port (path, query, fragment)
     * - Garantit un / final
     * / Sanitize and normalize server URL.
     */
    function sanitiserUrlServeur(url_brute) {
        var url_nettoyee = url_brute.trim();

        if (!url_nettoyee) {
            return 'https://beta.hypostasia.org/';
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
     * / Normalize a page URL for comparison.
     *
     * Le serveur applique EXACTEMENT la meme normalisation
     * (`normaliser_url`, core/views.py) : les deux listes de parametres
     * de suivi doivent rester d'accord, sinon la pre-verification et
     * l'enregistrement ne parlent pas de la meme URL.
     * / The server applies the same normalisation; both tracking lists
     * must stay in agreement.
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
     * TOUTE REQUETE PART SANS LES COOKIES DU NAVIGATEUR.
     * / Every request goes out WITHOUT the browser's cookies.
     *
     * Firefox joint les cookies du site aux requetes emises depuis une
     * page d'extension qui a la permission de ce site ; Chrome ne le
     * fait pas. Sans cette consigne, les deux navigateurs se comportent
     * donc differemment, et Firefox produit un etat impossible :
     *
     *   GET  /api/pages/me/  -> 200 {authenticated: true, username: ...}
     *   GET  /api/pages/...  -> 200, la liste des carnets
     *   POST /api/pages/     -> 403 CSRF Failed: CSRF cookie not set
     *
     * parce que `SessionAuthentication` (DRF) exige un jeton CSRF sur
     * les methodes d'ecriture, que l'extension n'a pas et ne peut pas
     * avoir. La popup annoncait alors « Connecte : untel » a quelqu'un
     * qui ne pouvait rien capturer. Le `csrf_exempt` pose sur la vue
     * n'y change rien : le controle vit DANS la classe
     * d'authentification, pas dans le decorateur.
     *
     * En coupant les cookies, l'extension s'authentifie par son jeton et
     * par lui seul — deliberement, et pareil dans les deux navigateurs.
     * / Cutting cookies makes the extension authenticate by its token
     * alone, deliberately, and identically in both browsers.
     */
    const SANS_LES_COOKIES = 'omit';

    /**
     * L'UNIQUE EXCEPTION, ET ELLE EST DELIBEREE.
     * / The one deliberate exception.
     *
     * `recupererLeJetonDepuisLaSession()` envoie les cookies pour aller
     * chercher le jeton une seule fois. C'est une LECTURE : un GET n'est
     * pas soumis au controle CSRF, donc il passe la ou une ecriture
     * echouerait. Tout ce qui suit repasse par le jeton.
     * / Used once, to fetch the token: a GET is not CSRF-checked, so it
     * succeeds where a write would fail. Everything else uses the token.
     */
    const AVEC_LES_COOKIES = 'include';

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

    /**
     * Recupere l'URL serveur courante depuis l'input
     * / Get current server URL from input
     */
    function getBaseUrl() {
        return sanitiserUrlServeur(serverUrlInput.value);
    }

    /**
     * Affiche un message sous le bouton, avec son niveau.
     * / Shows a message under the button, with its level.
     */
    function afficherLeStatut(texte, niveau) {
        statusDiv.textContent = texte;
        statusDiv.className = niveau || '';
    }

    /**
     * Rend le bouton a son etat de repos.
     * / Returns the button to its resting state.
     */
    function reposerLeBouton() {
        recolterBtn.disabled = false;
        recolterBtn.textContent = 'Recolter';
    }

    // --- Serveur et authentification / Server and authentication ---

    /**
     * Montre ou cache le bouton de connexion.
     * / Shows or hides the connect button.
     *
     * Il n'apparait QUE quand le serveur repond et qu'aucun jeton ne
     * fonctionne : un bouton qui ne peut rien faire est pire qu'un
     * bouton absent — serveur hors ligne, il ne promettrait rien.
     * / Only when the server answers and no token works.
     */
    function montrerLeBoutonDeConnexion(il_faut_le_montrer) {
        document.getElementById('connecterBtn').hidden = !il_faut_le_montrer;
    }

    /**
     * Interroge /api/pages/me/ : c'est LE point qui repond aux deux
     * questions a la fois — le serveur est-il joignable, et le token
     * est-il bon.
     * / Asks /api/pages/me/, which answers both questions at once.
     *
     * POURQUOI PAS /api/pages/ : cet endpoint exige desormais un token.
     * L'indicateur y aurait lu un 401 et affiche « Serveur erreur » en
     * rouge chez tout utilisateur qui n'a pas encore colle son token —
     * c'est-a-dire exactement au premier lancement. Le serveur allait
     * bien ; seule la popup le declarait casse. `me/` est `AllowAny` et
     * repond `{authenticated: false}` sans jeton : il distingue « pas
     * de serveur » de « pas de compte ».
     * / Not /api/pages/: it now requires a token, so the indicator would
     * read 401 and cry "server error" at first launch. me/ is AllowAny
     * and tells "no server" apart from "no account".
     *
     * @returns {boolean} true si un compte est reconnu
     */
    async function verifierServeurEtCompte() {
        try {
            var reponse = await fetch(getBaseUrl() + 'api/pages/me/', {
                headers: construireHeaders(),
                credentials: SANS_LES_COOKIES,
                signal: AbortSignal.timeout(3000),
            });

            if (!reponse.ok) {
                indicateur_point.className = 'offline';
                indicateur_texte.textContent = 'Serveur erreur (' + reponse.status + ')';
                zone_auth.textContent = '';
                zone_auth.className = '';
                montrerLeBoutonDeConnexion(false);
                return false;
            }

            indicateur_point.className = 'online';
            indicateur_texte.textContent = 'Serveur connecte';

            var donnees = await reponse.json();
            if (donnees.authenticated) {
                nom_du_compte = donnees.username || '';
                zone_auth.textContent = 'Connecte : ' + nom_du_compte;
                zone_auth.className = 'auth-ok';
                montrerLeBoutonDeConnexion(false);
                return true;
            }

            nom_du_compte = '';
            zone_auth.textContent = token_api
                ? 'Token invalide — reconnectez l\'extension'
                : 'Non connecte a cette instance';
            zone_auth.className = 'auth-ko';
            montrerLeBoutonDeConnexion(true);
            return false;
        } catch (erreur) {
            indicateur_point.className = 'offline';
            indicateur_texte.textContent = 'Serveur hors ligne';
            zone_auth.textContent = '';
            zone_auth.className = '';
            montrerLeBoutonDeConnexion(false);
            return false;
        }
    }

    // --- Connexion en un clic / One-click connection ---

    /**
     * Va chercher le jeton du compte connecte au site, et le range.
     * / Fetches the token of the account logged into the site, stores it.
     *
     * LE GESTE QU'ON SUPPRIME : ouvrir la page du jeton, selectionner
     * quarante caracteres hexadecimaux, les copier, ouvrir les options,
     * les coller. Ici : un clic.
     * / Replaces: open the token page, select forty hex characters,
     * copy, open the options, paste.
     *
     * IL FAUT ETRE CONNECTE AU SITE DANS CE NAVIGATEUR — c'est la
     * session qui autorise l'appel. Si elle manque, le serveur repond
     * 401 et on le dit en clair, avec l'adresse ou aller.
     * / Requires being logged into the site in this browser.
     */
    async function recupererLeJetonDepuisLaSession() {
        const bouton = document.getElementById('connecterBtn');
        bouton.disabled = true;
        bouton.textContent = 'Connexion...';
        afficherLeStatut('', '');

        try {
            var reponse = await fetch(getBaseUrl() + 'api/pages/mon_jeton/', {
                headers: { 'Accept': 'application/json' },
                credentials: AVEC_LES_COOKIES,
                signal: AbortSignal.timeout(5000),
            });

            if (reponse.status === 401) {
                afficherLeStatut(
                    'Connectez-vous d\'abord à ' + getBaseUrl() + ' dans ce '
                    + 'navigateur, puis réessayez.',
                    'info',
                );
                return;
            }

            if (!reponse.ok) {
                afficherLeStatut(
                    'Le serveur a refusé (' + reponse.status + ').', 'error',
                );
                return;
            }

            var donnees = await reponse.json();
            token_api = donnees.token;

            // Meme cle que les options : les deux chemins de
            // configuration restent d'accord.
            // / Same key as the options page: both paths agree.
            await new Promise(function(resolve) {
                chrome.storage.sync.set({ apiKey: donnees.token }, resolve);
            });

            afficherLeStatut('Connectée en tant que ' + donnees.username, 'success');

            // Tout se rejoue avec le jeton : le compte, puis les carnets.
            // / Everything replays with the token.
            await verifierServeurEtCompte();
            await remplirLeMenuDesCarnets();
        } catch (erreur) {
            console.error('[Hypostasia] Connexion impossible:', erreur);
            afficherLeStatut('Serveur injoignable.', 'error');
        } finally {
            bouton.disabled = false;
            bouton.textContent = 'Connecter cette extension';
        }
    }

    document.getElementById('connecterBtn')
        .addEventListener('click', recupererLeJetonDepuisLaSession);

    // --- Le menu des carnets / The notebook dropdown ---

    /**
     * La cle du souvenir pour le serveur et le compte courants.
     * / The memory key for the current server and account.
     */
    function cleDuSouvenir() {
        return getBaseUrl() + '|' + nom_du_compte;
    }

    /**
     * Retient le carnet choisi, pour ce serveur et ce compte.
     * / Remembers the chosen notebook, per server and account.
     *
     * On borne le nombre de souvenirs gardes : sans cela, chaque serveur
     * essaye et chaque compte laisserait une entree pour toujours, et
     * l'enregistrement finirait par depasser la taille maximale d'un
     * element de `chrome.storage.sync` — qui echoue alors en silence.
     * / The map is capped: otherwise every server and account tried would
     * leave an entry forever, until the record silently exceeds quota.
     */
    function retenirLeCarnetChoisi(identifiant_du_carnet) {
        chrome.storage.sync.get({ [CLE_DU_SOUVENIR]: {} }, function(donnees_stockees) {
            var souvenirs = donnees_stockees[CLE_DU_SOUVENIR] || {};

            // Reecrire l'entree la remet en derniere position : les cles
            // d'un objet JS gardent leur ordre d'insertion.
            // / Re-inserting moves the entry last: JS objects keep
            // insertion order.
            delete souvenirs[cleDuSouvenir()];
            souvenirs[cleDuSouvenir()] = identifiant_du_carnet;

            var cles_gardees = Object.keys(souvenirs).slice(-SOUVENIRS_GARDES);
            var souvenirs_bornes = {};
            cles_gardees.forEach(function(cle) {
                souvenirs_bornes[cle] = souvenirs[cle];
            });

            chrome.storage.sync.set({ [CLE_DU_SOUVENIR]: souvenirs_bornes });
        });
    }

    /**
     * Le carnet retenu la derniere fois, ou une chaine vide.
     * / The notebook remembered last time, or an empty string.
     */
    async function carnetRetenu() {
        var donnees_stockees = await new Promise(function(resolve) {
            chrome.storage.sync.get({ [CLE_DU_SOUVENIR]: {} }, resolve);
        });
        var souvenirs = donnees_stockees[CLE_DU_SOUVENIR] || {};
        var identifiant_retenu = souvenirs[cleDuSouvenir()];
        return identifiant_retenu === undefined ? '' : String(identifiant_retenu);
    }

    /**
     * Remplit le menu des carnets depuis /api/pages/mes_carnets/.
     * / Fills the notebook dropdown from /api/pages/mes_carnets/.
     *
     * LE MENU NE PROPOSE QUE DE VRAIS CARNETS. Il s'ouvrait autrefois
     * sur « A ranger », un carnet que le serveur creait tout seul a la
     * premiere capture. Une destination inventee par le code n'en est
     * pas une : elle rendait normal le fait de ne rien choisir, et le
     * carnet ainsi cree ne se vidait jamais.
     * / The dropdown only offers real notebooks.
     *
     * QUAND IL N'Y EN A AUCUN, ON NE PROPOSE PAS LE GESTE. Le menu
     * disparait, un message dit ou aller, et « Recolter » s'eteint. Un
     * bouton qui echouerait est pire qu'un bouton eteint.
     * / When there is none, the gesture is not offered.
     */
    async function remplirLeMenuDesCarnets() {
        carnets_recus = [];

        try {
            var reponse = await fetch(getBaseUrl() + 'api/pages/mes_carnets/', {
                headers: construireHeaders(),
                credentials: SANS_LES_COOKIES,
                signal: AbortSignal.timeout(3000),
            });
            if (reponse.ok) {
                carnets_recus = await reponse.json();
            }
        } catch (erreur) {
            console.debug('[Hypostasia] Carnets indisponibles:', erreur);
        }

        menu_des_carnets.innerHTML = '';

        // AUCUN CARNET OU ECRIRE : ON LE DIT, ET ON N'OFFRE PAS LE
        // GESTE. Le menu s'ouvrait autrefois sur « A ranger (le
        // fourre-tout) », un carnet que le serveur creait tout seul a la
        // premiere capture. Ce carnet magique a disparu le 21 aout
        // 2026 : une note appartient toujours a un carnet, et ce carnet
        // est choisi par quelqu'un. Sans carnet, la capture ne peut pas
        // aboutir — un bouton qui echouerait est pire qu'un bouton
        // eteint.
        // / No writable notebook: say so, and do not offer the gesture.
        // The catch-all the server used to create is gone.
        var aucun_carnet = carnets_recus.length === 0;
        message_aucun_carnet.hidden = !aucun_carnet;
        menu_des_carnets.hidden = aucun_carnet;
        recolterBtn.disabled = aucun_carnet;
        if (aucun_carnet) {
            avertissement_carnet.classList.remove('visible');
            return;
        }

        carnets_recus.forEach(function(carnet) {
            var option = document.createElement('option');
            option.value = String(carnet.id);
            option.textContent = carnet.nom;
            menu_des_carnets.appendChild(option);
        });

        // Restaurer le dernier choix, s'il existe TOUJOURS. Un carnet
        // supprime ou dont le partage a ete retire disparait de la
        // liste : selectionner un identifiant absent laisserait le menu
        // sur sa premiere entree en donnant a croire que c'est un choix.
        // / Restore the last choice only if it still exists: a deleted or
        // un-shared notebook would silently fall back to the first entry.
        var identifiant_retenu = await carnetRetenu();
        var le_choix_existe_encore = Array.from(menu_des_carnets.options).some(
            function(option) { return option.value === identifiant_retenu; }
        );
        if (identifiant_retenu && le_choix_existe_encore) {
            menu_des_carnets.value = identifiant_retenu;
        }

        montrerLAvertissementSiCarnetPublic();
    }

    /**
     * Montre l'avertissement quand le carnet selectionne est public.
     * / Shows the warning when the selected notebook is public.
     *
     * Ranger dans un carnet public rend la note publique — avec ses
     * extractions et ses commentaires, nommes. Ca se dit AU MOMENT DU
     * GESTE, pas dans une page d'aide (SPEC-corpus § 7.3).
     * / Filing in a public notebook publishes the note, its extractions
     * and its named comments. Said at gesture time.
     */
    function montrerLAvertissementSiCarnetPublic() {
        var identifiant_choisi = menu_des_carnets.value;
        var carnet_choisi = carnets_recus.find(function(carnet) {
            return String(carnet.id) === identifiant_choisi;
        });
        var il_est_public = Boolean(carnet_choisi && carnet_choisi.est_public);
        avertissement_carnet.classList.toggle('visible', il_est_public);
    }

    menu_des_carnets.addEventListener('change', function() {
        montrerLAvertissementSiCarnetPublic();
        retenirLeCarnetChoisi(menu_des_carnets.value);
    });

    // --- Adresse du serveur / Server address ---

    var saveUrlBtn = document.getElementById('saveUrlBtn');

    /**
     * Demande l'autorisation de parler au serveur saisi.
     * / Asks permission to talk to the server that was typed in.
     *
     * LOCALISATION : extension/popup.js
     *
     * Le manifest n'accorde d'office que les deux instances officielles,
     * hypostasia.org et beta.hypostasia.org. Toute autre adresse — une
     * instance auto-hebergee, un serveur de developpement — vit dans
     * `optional_host_permissions` et doit etre autorisee par la personne
     * qui la saisit.
     *
     * L'APPEL PART DIRECTEMENT DU CLIC, SANS AUCUN `await` AVANT LUI.
     * Le navigateur refuse une demande de permission qui ne descend pas
     * d'un geste utilisateur, et le premier `await` perd ce geste. Ne
     * pas ajouter de `permissions.contains()` en amont pour « eviter la
     * fenetre » : une permission deja accordee est rendue vraie sans
     * rien afficher, et le detour couterait le geste.
     * / Called straight from the click, with no prior await: the browser
     * rejects a permission request that does not descend from a gesture.
     *
     * @param {string} url_du_serveur URL normalisee, terminee par un /
     * @return {Promise<boolean>} vrai si l'autorisation est acquise
     */
    function demanderLAutorisationDuServeur(url_du_serveur) {
        return chrome.permissions.request({ origins: [url_du_serveur + '*'] });
    }

    async function sauvegarderUrlServeur() {
        var url_propre = sanitiserUrlServeur(serverUrlInput.value);
        serverUrlInput.value = url_propre;

        // L'autorisation vient AVANT l'enregistrement. Sans elle, tous
        // les appels au serveur echoueraient sur une erreur de meme
        // origine, que le navigateur ne raconte qu'a la console : la
        // popup afficherait « Serveur injoignable » pour une adresse
        // pourtant vivante.
        // / Permission first: without it every call fails on a
        // same-origin error that only reaches the console.
        var autorisation_accordee = await demanderLAutorisationDuServeur(url_propre);
        if (!autorisation_accordee) {
            afficherLeStatut(
                'Sans autorisation, l\'extension ne peut pas joindre ce serveur.',
                'error',
            );
            return;
        }

        chrome.storage.sync.set({ serverUrl: url_propre });

        // Feedback visuel bref / Brief visual feedback
        saveUrlBtn.textContent = '✓';
        setTimeout(function() { saveUrlBtn.textContent = 'OK'; }, 800);

        // Nouveau serveur : nouveau compte, nouveaux carnets.
        // / New server: new account, new notebooks.
        await verifierServeurEtCompte();
        await remplirLeMenuDesCarnets();
    }

    saveUrlBtn.addEventListener('click', sauvegarderUrlServeur);

    // --- Bouton principal : recolter le contenu de la page ---
    // / Main button: harvest page content
    //
    // L'ECOUTE SE POSE AVANT LES APPELS RESEAU, ET C'EST VOULU. Les deux
    // interrogations du serveur ci-dessous ont chacune trois secondes de
    // patience : posee apres elles, cette ecoute laisserait le bouton
    // muet jusqu'a six secondes sur un serveur lent ou injoignable, sans
    // que rien ne l'indique.
    // / Registered before the network calls: placed after them, the
    // button would stay silently dead for up to six seconds.
    recolterBtn.addEventListener('click', async () => {
        recolterBtn.disabled = true;
        recolterBtn.textContent = 'Recolte...';
        afficherLeStatut('', '');

        try {
            await recolterContenuPage();
        } catch (erreur) {
            console.error('[Hypostasia] Erreur recolte:', erreur);
            afficherLeStatut(erreur.message, 'error');
            reposerLeBouton();
        }
    });

    // Au chargement : le serveur, le compte, puis les carnets. Les
    // carnets ont besoin du nom du compte pour retrouver le souvenir,
    // d'ou l'enchainement et non le parallele.
    // / On load: server, account, then notebooks — sequential because
    // the memory key needs the account name.
    await verifierServeurEtCompte();
    await remplirLeMenuDesCarnets();

    /**
     * Flux de recolte :
     * 1. Normaliser l'URL et chercher un doublon dans MON perimetre
     * 2. Extraire le contenu via Readability
     * 3. Envoyer, avec le carnet choisi
     * / Harvest flow: dedup pre-check, Readability, send with notebook.
     *
     * L'EMPREINTE DE CONTENU N'EST PLUS CALCULEE ICI. Elle l'etait, et
     * pas de la meme facon que le serveur : la popup hachait
     * `body.textContent`, le serveur hachait son propre extracteur de
     * texte, apres un `.strip()`. Les deux valeurs ne se rejoignaient
     * pas, donc le refus « contenu identique deja enregistre » ne se
     * declenchait pas. Une seule implementation, cote serveur.
     * / The content fingerprint is no longer computed here: the two
     * implementations disagreed, so content dedup never fired.
     */
    async function recolterContenuPage() {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const url_normalisee = normaliserUrlPage(tab.url);

        // 1. Chercher un doublon dans le perimetre du compte
        // / Look for a duplicate within the account's scope
        afficherLeStatut('Verification...', '');
        const verification_response = await fetch(
            `${getBaseUrl()}api/pages/?url=${encodeURIComponent(url_normalisee)}`,
            { headers: construireHeaders(), credentials: SANS_LES_COOKIES }
        );

        // 401 ICI VEUT DIRE « PAS DE COMPTE », PAS « SERVEUR CASSE ». La
        // pre-verification exige un token depuis que l'endpoint est
        // ferme. Sans ce cas particulier, la recolte s'arretait sur
        // « Erreur serveur: 401 » et le message utile — celui qui dit ou
        // coller son token — vivait plus loin, dans la branche 401 du
        // POST, que l'on n'atteignait jamais.
        // / A 401 here means "no account", not "broken server": without
        // this branch the useful message was unreachable.
        if (verification_response.status === 401) {
            afficherLeStatut(
                'Token manquant ou invalide. Collez-le dans les options de l\'extension.',
                'error',
            );
            reposerLeBouton();
            return;
        }

        if (!verification_response.ok) {
            throw new Error('Erreur serveur: ' + verification_response.status);
        }

        const pages_existantes = await verification_response.json();

        if (pages_existantes.length > 0) {
            afficherLeStatut(
                'Deja enregistree (note ' + pages_existantes[0].id + ')', 'success',
            );
            reposerLeBouton();
            return;
        }

        // 2. Injecter Readability et extraire le contenu
        // / Inject Readability and extract content
        afficherLeStatut('Extraction...', '');

        await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['lib/Readability.js'],
        });

        // Fonction d'extraction injectee dans la page. Elle est
        // SERIALISEE avant injection : elle ne peut fermer sur aucune
        // variable de ce fichier, tout doit vivre a l'interieur.
        // / Serialised before injection: it can close over nothing.
        const resultat_extraction = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => {
                try {
                    const document_clone = document.cloneNode(true);
                    const article_readability = new Readability(document_clone).parse();

                    if (!article_readability) {
                        return { error: "Readability n'a pas pu extraire le contenu." };
                    }

                    // Echappement par le DOM : un titre contenant « < »
                    // ne doit pas devenir une balise.
                    // / DOM escaping: a title with "<" must not become a tag.
                    const echapper = (valeur) => {
                        const noeud = document.createElement('span');
                        noeud.textContent = String(valeur || '');
                        return noeud.innerHTML;
                    };

                    // READABILITY REND DIX CHAMPS, ET `content` N'EN EST
                    // QU'UN. Le titre, la signature et le chapeau vivent
                    // dans `title`, `byline` et `excerpt` — des champs
                    // SEPARES, absents de `content`. Le mode lecture de
                    // Firefox les reaffiche en tete ; l'extension les
                    // jetait, et l'article arrivait decapite : sur un
                    // article du Monde diplomatique, la note commencait
                    // au premier intertitre, sans titre ni auteur.
                    // / Readability returns ten fields and `content` is
                    // only one: title, byline and excerpt live apart.
                    const morceaux = [];
                    const titre = article_readability.title || document.title;
                    if (titre) {
                        morceaux.push('<h1>' + echapper(titre) + '</h1>');
                    }
                    if (article_readability.byline) {
                        morceaux.push(
                            '<p><em>' + echapper(article_readability.byline) + '</em></p>'
                        );
                    }

                    // LE CHAPEAU, SEULEMENT S'IL N'EST PAS DEJA LA.
                    // `excerpt` vient tantot du chapeau de l'article,
                    // tantot de son premier paragraphe : dans le second
                    // cas, l'ajouter le ferait lire deux fois.
                    // / The standfirst, only if not already there:
                    // excerpt is sometimes the first paragraph itself.
                    const chapeau = (article_readability.excerpt || '').trim();
                    if (chapeau) {
                        const debut_du_corps = (article_readability.textContent || '')
                            .trim().slice(0, 400);
                        const empreinte = chapeau.slice(0, 60);
                        if (!debut_du_corps.includes(empreinte)) {
                            morceaux.push('<p>' + echapper(chapeau) + '</p>');
                        }
                    }

                    // La provenance : d'ou vient ce texte, et de quand.
                    // Dans un outil qui relie chaque affirmation a sa
                    // source, ces deux valeurs ne sont pas decoratives.
                    // / Provenance: where the text comes from, and when.
                    const provenance = [];
                    if (article_readability.siteName) {
                        provenance.push(echapper(article_readability.siteName));
                    }
                    if (article_readability.publishedTime) {
                        // ON NE REINTERPRETE PAS LA DATE DE L'EDITEUR.
                        // `new Date(...).toLocaleDateString()` la ramene
                        // dans le fuseau du navigateur : un article date
                        // `2003-01-01T00:00:00+01:00` s'affichait
                        // « 31/12/2002 » sur une machine en UTC. On
                        // reordonne les chiffres que l'editeur a ecrits,
                        // et rien de plus.
                        // / We do not re-interpret the publisher's date:
                        // converting to the browser's timezone moved it
                        // back a day. We only reorder its digits.
                        const iso = String(article_readability.publishedTime);
                        const jour = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
                        provenance.push(echapper(
                            jour ? `${jour[3]}/${jour[2]}/${jour[1]}` : iso
                        ));
                    }
                    if (provenance.length) {
                        morceaux.push('<p>' + provenance.join(' — ') + '</p>');
                    }

                    morceaux.push(article_readability.content || '');

                    return {
                        title: titre,
                        html_readability: morceaux.join('\n'),
                        html_original: document.documentElement.outerHTML,
                    };
                } catch (e) {
                    return { error: e.message };
                }
            },
        });

        const donnees_extraites = resultat_extraction[0].result;

        if (donnees_extraites.error) {
            throw new Error(donnees_extraites.error);
        }

        // 3. Envoyer, avec l'URL normalisee et le carnet choisi
        // / Send, with the normalised URL and the chosen notebook
        afficherLeStatut('Envoi...', '');

        var corps_de_la_requete = {
            url: url_normalisee,
            title: donnees_extraites.title,
            html_readability: donnees_extraites.html_readability,
            html_original: donnees_extraites.html_original,
        };

        // LE CARNET PART TOUJOURS. Le serveur n'a plus de destination
        // par defaut : sans `dossier_id`, il refuse.
        // / The notebook always travels: the server has no default.
        corps_de_la_requete.dossier_id = Number(menu_des_carnets.value);

        const creation_response = await fetch(`${getBaseUrl()}api/pages/`, {
            method: 'POST',
            headers: construireHeaders('application/json'),
            credentials: SANS_LES_COOKIES,
            body: JSON.stringify(corps_de_la_requete),
        });

        if (!creation_response.ok) {
            await traiterUnEchecDeCreation(creation_response);
            return;
        }

        const page_creee = await creation_response.json();
        var nom_du_carnet = menu_des_carnets.options[menu_des_carnets.selectedIndex].textContent;
        afficherLeStatut('Enregistree dans « ' + nom_du_carnet + ' »', 'success');
        reposerLeBouton();

        // Le choix n'est retenu qu'une fois qu'il a servi.
        // / The choice is remembered only once it has worked.
        retenirLeCarnetChoisi(menu_des_carnets.value);
    }

    /**
     * Traduit un echec de creation en message lisible.
     * / Turns a creation failure into a readable message.
     *
     * TROIS CONFLITS PARTAGENT LE CODE 409, ET ILS NE VEULENT PAS DIRE
     * LA MEME CHOSE. Deux sont des non-evenements paisibles — la note
     * est deja chez moi —, le troisieme est un echec : un inconnu a pris
     * cette URL et l'unicite est globale en base. La popup lisait
     * autrefois `existing_page_id` sans regarder le motif, et affichait
     * donc « deja enregistree (id: undefined) » EN VERT pour une capture
     * qui venait d'echouer. C'est le champ `code` qui les separe.
     * / Three conflicts share the 409 and do not mean the same thing;
     * the popup used to paint the failing one green.
     */
    async function traiterUnEchecDeCreation(reponse) {
        var texte_brut = await reponse.text();
        var donnees = {};
        try {
            donnees = JSON.parse(texte_brut);
        } catch (erreur) {
            donnees = {};
        }
        console.error('[Hypostasia] Echec creation:', reponse.status, texte_brut);

        if (reponse.status === 401) {
            afficherLeStatut(
                'Token manquant ou invalide. Collez-le dans les options de l\'extension.',
                'error',
            );
            reposerLeBouton();
            return;
        }

        if (reponse.status === 409) {
            if (donnees.code === 'url_prise_ailleurs') {
                // Un echec, pas un doublon paisible : la note n'est pas
                // enregistree et ne peut pas l'etre sous cette URL.
                // / A failure, not a peaceful duplicate.
                afficherLeStatut(
                    'Cette page est deja capturee sur ce serveur, dans un '
                    + 'carnet auquel vous n\'avez pas acces.',
                    'info',
                );
            } else {
                afficherLeStatut(
                    'Deja enregistree' + (donnees.existing_page_id
                        ? ' (note ' + donnees.existing_page_id + ')' : ''),
                    'success',
                );
            }
            reposerLeBouton();
            return;
        }

        if (reponse.status === 400 && donnees.dossier_id) {
            // Le carnet a disparu, ou le partage a ete retire entre
            // l'ouverture de la popup et le clic.
            // / The notebook vanished, or the share was revoked.
            afficherLeStatut(String(donnees.dossier_id[0]), 'error');
            await remplirLeMenuDesCarnets();
            reposerLeBouton();
            return;
        }

        afficherLeStatut('Erreur creation (' + reponse.status + ')', 'error');
        reposerLeBouton();
    }
});
