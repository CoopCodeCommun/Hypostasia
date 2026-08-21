/**
 * Logique principale de la popup de l'extension navigateur.
 * Choix du carnet, recolte du contenu, authentification par token.
 * / Main popup logic: notebook choice, content harvesting, token auth.
 *
 * LOCALISATION : extension/popup.js
 *
 * COMMUNICATION :
 * - GET  /api/pages/me/          verifie le serveur ET le token
 * - GET  /api/pages/mes_carnets/ remplit le menu des carnets
 * - GET  /api/pages/?url=        cherche un doublon dans MON perimetre
 * - POST /api/pages/             cree la note dans le carnet choisi
 *
 * LE CARNET SE CHOISIT AVANT LA CAPTURE. La note part directement a sa
 * destination : `dossier_id` voyage avec le POST. L'ancien flux creait
 * la note dans le fourre-tout puis proposait des boutons de rangement,
 * ce qui laissait la note mal rangee si la popup se fermait entre les
 * deux gestes.
 * / The notebook is chosen before capture and travels with the POST.
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
            serverUrl: 'http://127.0.0.1:8000/',
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
                signal: AbortSignal.timeout(3000),
            });

            if (!reponse.ok) {
                indicateur_point.className = 'offline';
                indicateur_texte.textContent = 'Serveur erreur (' + reponse.status + ')';
                zone_auth.textContent = '';
                zone_auth.className = '';
                return false;
            }

            indicateur_point.className = 'online';
            indicateur_texte.textContent = 'Serveur connecte';

            var donnees = await reponse.json();
            if (donnees.authenticated) {
                nom_du_compte = donnees.username || '';
                zone_auth.textContent = 'Connecte : ' + nom_du_compte;
                zone_auth.className = 'auth-ok';
                return true;
            }

            nom_du_compte = '';
            zone_auth.textContent = token_api
                ? 'Token invalide — a regenerer sur /auth/token/'
                : 'Non connecte : collez votre token dans les options';
            zone_auth.className = 'auth-ko';
            return false;
        } catch (erreur) {
            indicateur_point.className = 'offline';
            indicateur_texte.textContent = 'Serveur hors ligne';
            zone_auth.textContent = '';
            zone_auth.className = '';
            return false;
        }
    }

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
     * LE FOURRE-TOUT EST TOUJOURS EN TETE, ET IL EST LE DEFAUT. Deux
     * cas se rejoignent la : le compte qui possede deja un carnet
     * « A ranger », et celui qui n'en a pas encore — le serveur le cree
     * a la premiere capture qui en a besoin, jamais a l'ouverture de ce
     * menu. Dans les deux cas l'utilisateur a une destination valide des
     * la premiere seconde, meme sans avoir jamais cree de carnet.
     * / The inbox is always first and is the default: it covers both the
     * account that already owns one and the account that owns none, the
     * server creating it lazily on first capture.
     *
     * IL SE RECONNAIT PAR SON ROLE, JAMAIS PAR SON NOM. La popup
     * comparait `dossier.name === 'A ranger'` ; un utilisateur qui
     * renommait son fourre-tout le voyait reapparaitre en double dans la
     * liste. Le serveur a un champ pour ca — `role_special`.
     * / Recognised by its ROLE, never its name: a renamed inbox used to
     * show up twice.
     */
    async function remplirLeMenuDesCarnets() {
        carnets_recus = [];

        try {
            var reponse = await fetch(getBaseUrl() + 'api/pages/mes_carnets/', {
                headers: construireHeaders(),
                signal: AbortSignal.timeout(3000),
            });
            if (reponse.ok) {
                carnets_recus = await reponse.json();
            }
        } catch (erreur) {
            console.debug('[Hypostasia] Carnets indisponibles:', erreur);
        }

        var carnet_fourre_tout = carnets_recus.find(function(carnet) {
            return carnet.role_special === 'a_ranger';
        });
        var carnets_ordinaires = carnets_recus.filter(function(carnet) {
            return carnet.role_special !== 'a_ranger';
        });

        menu_des_carnets.innerHTML = '';

        // Le fourre-tout, avec son vrai nom s'il existe deja. Valeur
        // vide quand il n'existe pas : le POST part alors sans
        // `dossier_id` et le serveur s'en charge.
        // / The inbox, with its real name if it exists; empty value
        // otherwise, letting the server resolve it.
        var option_fourre_tout = document.createElement('option');
        option_fourre_tout.value = carnet_fourre_tout ? String(carnet_fourre_tout.id) : '';
        option_fourre_tout.textContent = carnet_fourre_tout
            ? carnet_fourre_tout.nom + ' (fourre-tout)'
            : 'A ranger (le fourre-tout)';
        menu_des_carnets.appendChild(option_fourre_tout);

        carnets_ordinaires.forEach(function(carnet) {
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

    async function sauvegarderUrlServeur() {
        var url_propre = sanitiserUrlServeur(serverUrlInput.value);
        serverUrlInput.value = url_propre;
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
            { headers: construireHeaders() }
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
                        title: article_readability.title || document.title,
                        html_readability: article_readability.content || '',
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

        // Menu sur le fourre-tout inexistant : on n'envoie rien et le
        // serveur resout la destination lui-meme.
        // / Empty value means "let the server resolve the inbox".
        if (menu_des_carnets.value) {
            corps_de_la_requete.dossier_id = Number(menu_des_carnets.value);
        }

        const creation_response = await fetch(`${getBaseUrl()}api/pages/`, {
            method: 'POST',
            headers: construireHeaders('application/json'),
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
