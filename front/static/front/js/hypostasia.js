// ==========================================================================
// hypostasia.js — JS principal extrait de base.html
// / Main JS extracted from base.html
// ==========================================================================

// --- Onglets du panneau droit (garde null car panneau cache en PHASE-07) ---
// / Right panel tabs handler (null guard since panel hidden in PHASE-07)
var ongletsPanneau = document.getElementById('onglets-panneau');
if (ongletsPanneau) {
    ongletsPanneau.addEventListener('click', function(event) {
        var bouton = event.target.closest('.onglet-panneau:not([disabled])');
        if (!bouton) return;

        var ongletChoisi = bouton.dataset.onglet;

        // Lire le page_id depuis la zone de lecture / Read page_id from reading zone
        var elementPage = document.querySelector('#zone-lecture [data-page-id]');
        if (!elementPage) {
            document.body.dispatchEvent(new CustomEvent('showToast', {
                detail: { message: 'Sélectionnez une page' }
            }));
            return;
        }
        var pageId = elementPage.dataset.pageId;

        // Mise a jour des styles des onglets / Update tab styles
        var tousLesOnglets = this.querySelectorAll('.onglet-panneau:not([disabled])');
        tousLesOnglets.forEach(function(onglet) {
            onglet.className = 'onglet-panneau text-sm px-3 py-1.5 rounded-t font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-100';
        });
        bouton.className = 'onglet-panneau text-sm px-3 py-1.5 rounded-t font-medium bg-white text-blue-600 border border-b-0 border-slate-200';

        // Charger le contenu selon l'onglet / Load content based on tab
        if (ongletChoisi === 'extractions') {
            htmx.ajax('POST', '/extractions/panneau/', {
                target: '#panneau-extractions',
                swap: 'innerHTML',
                values: { page_id: pageId }
            });
        } else if (ongletChoisi === 'commentaires') {
            htmx.ajax('GET', '/extractions/vue_commentaires/?page_id=' + pageId, {
                target: '#panneau-extractions',
                swap: 'innerHTML'
            });
        }
    });
}

// Expand/collapse dossiers (client-side) — clic sur la ligne entière
// Ignore les clics sur le bouton kebab menu contextuel (PHASE-25)
// / Ignores clicks on the kebab context menu button (PHASE-25)
document.addEventListener('click', function(e) {
    // Si le clic est sur le bouton kebab ou marque comme gere par le menu contextuel,
    // ne pas toggler le dossier
    // / If click is on kebab button or marked as handled by context menu, don't toggle
    if (e.target.closest('.btn-ctx-menu')) return;
    if (e._ctxMenuHandled) return;
    const row = e.target.closest('.dossier-toggle');
    if (!row) return;
    const node = row.closest('.dossier-node');
    const arrow = node.querySelector('.tree-arrow');
    const list = node.querySelector('.dossier-pages');
    if (arrow) arrow.classList.toggle('open');
    if (list) list.classList.toggle('hidden');
});

// Classer une page dans un dossier via SweetAlert
document.addEventListener('click', async function(e) {
    const btn = e.target.closest('.btn-classer');
    if (!btn) return;
    e.preventDefault();
    const pageId = btn.dataset.pageId;

    const resp = await fetch('/dossiers/');
    const dossiers = await resp.json();

    if (Object.keys(dossiers).length === 0) {
        Swal.fire({title: 'Aucun dossier', text: 'Créez d\'abord un dossier.', icon: 'info'});
        return;
    }

    const options = {'': '— Aucun dossier —', ...dossiers};

    const {value: dossierId, isDismissed} = await Swal.fire({
        title: 'Déplacer vers…',
        input: 'select',
        inputOptions: options,
        inputPlaceholder: 'Choisir un dossier',
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Déplacer',
    });

    if (isDismissed) return;

    // Recupere le token CSRF depuis hx-headers du body
    // / Retrieve CSRF token from body's hx-headers attribute
    var headersBrut = document.querySelector('body').getAttribute('hx-headers');
    var csrfToken = '';
    try { csrfToken = JSON.parse(headersBrut)['X-CSRFToken']; } catch (e) {}

    const classerResp = await fetch(`/pages/${pageId}/classer/`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
        body: JSON.stringify({dossier_id: dossierId || null}),
    });

    if (classerResp.ok) {
        const arbreEl = document.getElementById('arbre');
        arbreEl.innerHTML = await classerResp.text();
        htmx.process(arbreEl);
    }
});
// --- Les items analyseur utilisent hx-get directement ---
// / Analyzer items use hx-get directly

// --- Import de fichier ---
// Si audio → affiche confirmation avec cout, sinon → import direct
// / If audio → show confirmation with cost, otherwise → direct import
var EXTENSIONS_AUDIO = ['.mp3','.wav','.m4a','.ogg','.flac','.webm','.aac','.wma','.opus','.aiff'];

function estFichierAudio(nomFichier) {
    var ext = nomFichier.toLowerCase().match(/\.[^.]+$/);
    return ext && EXTENSIONS_AUDIO.indexOf(ext[0]) !== -1;
}

// Fonction utilitaire : traite une reponse HTML avec OOB swaps
// / Utility: process HTML response with OOB swaps
function traiterReponseAvecOob(htmlComplet) {
    var conteneur = document.createElement('div');
    conteneur.innerHTML = htmlComplet;
    conteneur.querySelectorAll('[hx-swap-oob]').forEach(function(elementOob) {
        var attributOob = elementOob.getAttribute('hx-swap-oob');
        var selecteur = attributOob.split(':')[1];
        if (selecteur) {
            var cible = document.querySelector(selecteur);
            if (cible) {
                cible.innerHTML = elementOob.innerHTML;
                htmx.process(cible);
            }
        }
        elementOob.remove();
    });
    document.getElementById('zone-lecture').innerHTML = conteneur.innerHTML;
    htmx.process(document.getElementById('zone-lecture'));
}

// Guard authentification : bloque l'import si l'utilisateur n'est pas connecte.
// Dispatch l'event 'authRequise' qui ouvre le SweetAlert "Connexion requise" deja
// existant. Reset l'input pour permettre un nouvel essai apres connexion.
// / Auth guard: blocks import if user not logged in.
// / Dispatches 'authRequise' event that opens the existing "Connexion requise" SweetAlert.
function utilisateurEstAuthentifie() {
    return document.body.dataset.userAuthenticated === '1';
}
function bloquerSiNonAuthentifie(inputFichier) {
    if (utilisateurEstAuthentifie()) return false;
    inputFichier.value = '';
    document.body.dispatchEvent(new CustomEvent('authRequise', {
        detail: {
            titre: 'Connexion requise',
            message: 'Connectez-vous pour importer un fichier.',
            url_login: '/auth/login/',
        },
    }));
    return true;
}

document.getElementById('input-import-fichier').addEventListener('change', function() {
    var inputFichier = this;
    var fichierSelectionne = inputFichier.files[0];
    if (!fichierSelectionne) return;
    if (bloquerSiNonAuthentifie(inputFichier)) return;

    var formulaireDonnees = new FormData();
    formulaireDonnees.append('fichier', fichierSelectionne);

    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');

    // Aiguillage : audio → previsualisation, document → import direct
    // / Routing: audio → preview, document → direct import
    var urlImport = estFichierAudio(fichierSelectionne.name)
        ? '/import/previsualiser_audio/'
        : '/import/fichier/';

    // Afficher la barre de progression dans zone-lecture
    // / Show progress bar in zone-lecture
    var zoneLecture = document.getElementById('zone-lecture');
    zoneLecture.innerHTML = ''
        + '<div class="max-w-xl mx-auto p-6">'
        + '  <div class="bg-white rounded-lg border border-blue-200 p-4 space-y-3">'
        + '    <div class="flex items-center gap-2">'
        + '      <svg class="w-5 h-5 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">'
        + '        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>'
        + '        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>'
        + '      </svg>'
        + '      <span class="text-sm font-medium text-slate-700">Envoi en cours\u2026</span>'
        + '      <span id="upload-pourcentage" class="text-xs text-slate-500 ml-auto">0%</span>'
        + '    </div>'
        + '    <div class="w-full bg-slate-200 rounded-full h-2 overflow-hidden">'
        + '      <div id="upload-barre" class="bg-blue-500 h-2 rounded-full transition-all duration-200" style="width: 0%"></div>'
        + '    </div>'
        + '    <p id="upload-detail" class="text-xs text-slate-400">' + fichierSelectionne.name + '</p>'
        + '  </div>'
        + '</div>';

    // Utiliser XMLHttpRequest pour suivre la progression de l'upload
    // / Use XMLHttpRequest to track upload progress
    var requeteUpload = new XMLHttpRequest();
    requeteUpload.open('POST', urlImport);

    if (csrfToken) requeteUpload.setRequestHeader('X-CSRFToken', csrfToken.value);
    requeteUpload.setRequestHeader('HX-Request', 'true');

    // Progression de l'upload / Upload progress
    requeteUpload.upload.addEventListener('progress', function(evenementProgression) {
        if (evenementProgression.lengthComputable) {
            var pourcentage = Math.round((evenementProgression.loaded / evenementProgression.total) * 100);
            var barreProgression = document.getElementById('upload-barre');
            var textePourcentage = document.getElementById('upload-pourcentage');
            if (barreProgression) barreProgression.style.width = pourcentage + '%';
            if (textePourcentage) textePourcentage.textContent = pourcentage + '%';

            // Quand l'envoi est termine, afficher le spinner d'analyse
            // / When upload is done, show analysis spinner
            if (pourcentage >= 100) {
                var detailUpload = document.getElementById('upload-detail');
                if (detailUpload) detailUpload.textContent = 'Analyse du fichier\u2026';
            }
        }
    });

    requeteUpload.addEventListener('load', function() {
        if (requeteUpload.status >= 200 && requeteUpload.status < 300) {
            var htmlComplet = requeteUpload.responseText;
            // Le serveur indique l'URL a pusher dans l'historique navigateur via
            // un header custom X-Hypostasia-Page-Url. On l'applique apres le swap.
            // / Server tells the URL to push via X-Hypostasia-Page-Url header.
            var urlACTuelle = requeteUpload.getResponseHeader('X-Hypostasia-Page-Url');
            if (estFichierAudio(fichierSelectionne.name)) {
                // Audio : afficher la confirmation dans zone-lecture
                // / Audio: show confirmation in zone-lecture
                zoneLecture.innerHTML = htmlComplet;
                htmx.process(zoneLecture);
            } else {
                // Document : traiter les OOB + toast
                // / Document: process OOB + toast
                traiterReponseAvecOob(htmlComplet);
                if (urlACTuelle) {
                    history.pushState({}, '', urlACTuelle);
                }
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'success',
                    title: 'Fichier import\u00e9', showConfirmButton: false, timer: 2500,
                });
            }
        } else {
            zoneLecture.innerHTML = requeteUpload.responseText;
        }
    });

    requeteUpload.addEventListener('error', function() {
        console.error('[Import fichier] erreur reseau');
        Swal.fire({icon: 'error', title: 'Erreur', text: 'Erreur lors de l\'envoi du fichier.'});
        zoneLecture.innerHTML = '';
    });

    requeteUpload.send(formulaireDonnees);

    // Reset l'input pour permettre de reimporter le meme fichier
    // / Reset input to allow reimporting the same file
    inputFichier.value = '';
});

// Import fichier depuis l'onboarding → relaye vers l'input principal
// / File import from onboarding → relay to main input
document.addEventListener('change', function(evenement) {
    if (evenement.target.id !== 'input-import-fichier-onboarding') return;
    var fichierOnboarding = evenement.target.files[0];
    if (!fichierOnboarding) return;

    var transfert = new DataTransfer();
    transfert.items.add(fichierOnboarding);

    var inputPrincipal = document.getElementById('input-import-fichier');
    inputPrincipal.files = transfert.files;
    inputPrincipal.dispatchEvent(new Event('change', { bubbles: true }));

    evenement.target.value = '';
});

// Creation d'un analyseur syntaxique via SweetAlert (delegation d'evenement)
// Le bouton #btn-new-analyseur est dans la vue config LLM, chargee dynamiquement
// / Analyzer creation via SweetAlert (event delegation)
// / The #btn-new-analyseur button is in the LLM config view, loaded dynamically
document.addEventListener('click', async function(evenement) {
    var boutonNouvelAnalyseur = evenement.target.closest('#btn-new-analyseur');
    if (!boutonNouvelAnalyseur) return;

    var htmlFormulaire = ''
        + '<input id="swal-name" class="swal2-input" placeholder="Nom de l\'analyseur">'
        + '<select id="swal-type" class="swal2-select" style="margin-top:0.5rem">'
        + '  <option value="analyser">Analyser</option>'
        + '  <option value="synthetiser">Synthétiser</option>'
        + '</select>';

    var resultatSwal = await Swal.fire({
        title: 'Nouvel analyseur',
        html: htmlFormulaire,
        focusConfirm: false,
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Créer',
        preConfirm: function() {
            var nom = document.getElementById('swal-name').value.trim();
            var typeAnalyseur = document.getElementById('swal-type').value;
            if (!nom) { Swal.showValidationMessage('Le nom est requis'); return false; }
            return {name: nom, type_analyseur: typeAnalyseur};
        }
    });
    if (resultatSwal.isDismissed || !resultatSwal.value) return;

    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    var headers = {'Content-Type': 'application/json'};
    if (csrfToken) headers['X-CSRFToken'] = csrfToken.value;

    var reponseCreation = await fetch('/api/analyseurs/', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({name: resultatSwal.value.name, type_analyseur: resultatSwal.value.type_analyseur}),
    });

    if (reponseCreation.ok) {
        // Charger l'editeur du nouvel analyseur dans zone-lecture
        // / Load the new analyzer's editor in reading zone
        var htmlReponse = await reponseCreation.text();
        var conteneurTemp = document.createElement('div');
        conteneurTemp.innerHTML = htmlReponse;
        var lienEditeur = conteneurTemp.querySelector('[hx-get]');
        if (lienEditeur) {
            var urlEditeur = lienEditeur.getAttribute('hx-get');
            htmx.ajax('GET', urlEditeur, {target: '#zone-lecture', swap: 'innerHTML'}).then(function() {
                history.pushState({}, '', urlEditeur);
            });
        }
    }
});

// ==========================================================================
// Panneau droit : ouverture / fermeture
// / Right panel: open / close
// ==========================================================================

// Panneau droit : delegue au drawer vue liste.
// PHASE-29 : on appelle ouvrir(false) car le caller HTMX (synthetiser, analyser,
// previsualiser_synthese) a deja swappe le contenu dans #drawer-contenu via
// hx-target. Si on rechargeait le contenu, on ecraserait le partial specifique.
// / Right panel: delegates to drawer list view.
// / PHASE-29: we call ouvrir(false) because the HTMX caller has already swapped
// / content into #drawer-contenu via hx-target. Reloading would overwrite it.
function ouvrirPanneauDroit() {
    if (window.drawerVueListe) {
        window.drawerVueListe.ouvrir(false);
    }
}

// Symetrique : fermer le drawer (utilise par PHASE-29 fin de synthese)
// / Symmetric: close the drawer (used by PHASE-29 end of synthesis)
function fermerPanneauDroit() {
    if (window.drawerVueListe) {
        window.drawerVueListe.fermer();
    }
}

// Ecoute l'evenement HTMX custom "ouvrirPanneauDroit"
// envoye par le controleur via HX-Trigger dans la reponse
// / Listens for HTMX custom event "ouvrirPanneauDroit"
// / sent by the controller via HX-Trigger in the response
document.body.addEventListener('ouvrirPanneauDroit', function() {
    ouvrirPanneauDroit();
});

// Ecoute l'evenement HTMX custom "ouvrirDrawer"
// envoye par analyser() via HX-Trigger pour ouvrir le drawer apres lancement
// / Listens for HTMX custom event "ouvrirDrawer"
// / sent by analyser() via HX-Trigger to open drawer after launch
document.body.addEventListener('ouvrirDrawer', function() {
    ouvrirPanneauDroit();
});

// Ecoute l'evenement HTMX custom "fermerDrawer"
// / Listens for HTMX custom event "fermerDrawer"
document.body.addEventListener('fermerDrawer', function() {
    fermerPanneauDroit();
});

// --- SweetAlert sur erreur HTMX ---
// Les 403 d'authentification sont gerees par l'evenement authRequise (ci-dessous)
// Les autres erreurs (500, 404, etc.) affichent un SweetAlert generique
// / HTMX error handler
// / Auth 403s are handled by the authRequise event (below)
// / Other errors (500, 404, etc.) show a generic SweetAlert
document.body.addEventListener('htmx:responseError', function(evenement) {
    var codeHttp = evenement.detail.xhr.status;
    // Ignorer les 403 d'auth — gerees par HX-Trigger authRequise
    // / Skip auth 403s — handled by HX-Trigger authRequise
    if (codeHttp === 403) return;
    var texteErreur = evenement.detail.xhr.responseText || 'Erreur inconnue';
    Swal.fire({
        icon: 'error',
        title: 'Erreur ' + codeHttp,
        text: texteErreur.substring(0, 300),
    });
});

// --- SweetAlert pour authentification requise (403) ---
// Declenche par HX-Trigger authRequise depuis _exiger_authentification()
// Affiche un SweetAlert avec un bouton de connexion
// / Auth required SweetAlert (403)
// / Triggered by HX-Trigger authRequise from _exiger_authentification()
document.body.addEventListener('authRequise', function(evenement) {
    var detail = evenement.detail || {};
    Swal.fire({
        icon: 'info',
        title: detail.titre || 'Connexion requise',
        text: detail.message || 'Connectez-vous pour effectuer cette action.',
        confirmButtonText: 'Se connecter',
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonColor: '#2563eb',
    }).then(function(resultat) {
        if (resultat.isConfirmed) {
            window.location.href = detail.url_login || '/auth/login/';
        }
    });
});

// --- Toast de confirmation via HX-Trigger showToast ---
// Les vues envoient HX-Trigger: {"showToast": {"message": "...", "icon": "success"}}
// / Confirmation toast via HX-Trigger showToast
document.body.addEventListener('showToast', function(evenement) {
    var detail = evenement.detail || {};
    Swal.fire({
        toast: true,
        position: 'top-end',
        icon: detail.icon || 'success',
        title: detail.message || 'OK',
        showConfirmButton: false,
        timer: 2500,
        // Decalage vertical pour passer SOUS la navbar (h-12 = 3rem = 48px)
        // sinon le toast cache le bouton 'taches' dans la toolbar.
        // / Vertical offset to go BELOW the navbar (h-12 = 3rem = 48px)
        // / otherwise the toast hides the 'tasks' button in the toolbar.
        customClass: { popup: 'toast-sous-navbar' },
    });
});

// --- Rechargement de la zone de lecture via HX-Trigger lectureReload ---
// Les vues envoient HX-Trigger: {"lectureReload": {"page_id": "42"}}
// / Reading zone reload via HX-Trigger lectureReload
document.body.addEventListener('lectureReload', function(evenement) {
    var detail = evenement.detail || {};
    var pageId = detail.page_id;
    if (!pageId) {
        // Fallback : lire le page_id depuis la zone de lecture
        // / Fallback: read page_id from reading zone
        var elementPage = document.querySelector('#zone-lecture [data-page-id]');
        if (elementPage) pageId = elementPage.dataset.pageId;
    }
    if (!pageId) return;

    // Recharger la zone de lecture via fetch + innerHTML (meme pattern que drawer)
    // / Reload reading zone via fetch + innerHTML (same pattern as drawer)
    fetch('/lire/' + pageId + '/', {
        headers: { 'HX-Request': 'true' },
    })
    .then(function(reponse) { return reponse.text(); })
    .then(function(html) {
        var zoneLecture = document.getElementById('zone-lecture');
        if (!zoneLecture) return;

        // Extraire seulement le partial de lecture, sans le div OOB panneau
        // / Extract only the lecture partial, without the OOB panneau div
        var parseur = new DOMParser();
        var doc = parseur.parseFromString('<div>' + html + '</div>', 'text/html');
        // Retirer TOUS les divs OOB (panneau-extractions, titre-toolbar, etc.)
        // / Remove ALL OOB divs (panneau-extractions, titre-toolbar, etc.)
        doc.querySelectorAll('[hx-swap-oob]').forEach(function(divOob) {
            divOob.remove();
        });

        zoneLecture.innerHTML = doc.body.firstElementChild.innerHTML;
        htmx.process(zoneLecture);

        // Reconstruire les pastilles marginales apres le remplacement du contenu
        // / Rebuild margin pastilles after content replacement
        if (typeof construirePastillesMarginales === 'function') {
            construirePastillesMarginales();
        }
    });
});

// --- Indication de la page active dans l'arbre ---
// Apres chaque swap dans #zone-lecture, on surligne le lien correspondant
// / Active page indicator in tree after each swap in #zone-lecture
document.getElementById('zone-lecture').addEventListener('htmx:afterSwap', function() {
    var conteneur = document.querySelector('#zone-lecture [data-page-id]');
    if (!conteneur) return;
    var pageIdActif = conteneur.dataset.pageId;

    // Retirer la classe active de tous les liens / Remove active class from all links
    document.querySelectorAll('#arbre .lien-page').forEach(function(lien) {
        lien.classList.remove('bg-blue-50', 'text-blue-700', 'font-medium', 'rounded');
    });

    // Ajouter la classe active au lien correspondant / Add active class to matching link
    var lienActif = document.querySelector('#arbre .lien-page[data-page-id="' + pageIdActif + '"]');
    if (lienActif) {
        lienActif.classList.add('bg-blue-50', 'text-blue-700', 'font-medium', 'rounded');
    }

});

// === Focus extraction depuis URL (PHASE-25d-v2) ===
// Apres chaque navigation HTMX avec push URL, on verifie si l'URL contient
// ?extraction={id}. Si oui, on scroll vers le passage surligne et on l'ouvre.
// On ecoute 'htmx:pushedIntoHistory' car c'est l'evenement qui se declenche
// APRES que l'URL soit mise a jour (afterSwap se declenche avant le push URL).
// / After each HTMX navigation with push URL, check if URL contains
// / ?extraction={id}. If so, scroll to highlighted passage and open it.
// / We listen to 'htmx:pushedIntoHistory' because it fires AFTER the URL is updated.
// Flag pour eviter que _focusExtractionDepuisUrl s'execute deux fois
// (htmx:afterSettle et htmx:pushedIntoHistory se declenchent tous les deux)
// / Flag to prevent _focusExtractionDepuisUrl from running twice
var _focusExtractionDejaExecute = false;

// Fonction reutilisable pour scroller vers une extraction cible
// / Reusable function to scroll to a target extraction
function _focusExtractionDepuisUrl() {
    if (_focusExtractionDejaExecute) return;

    var parametresUrl = new URLSearchParams(window.location.search);
    var extractionCible = parametresUrl.get('extraction');
    if (!extractionCible) return;

    _focusExtractionDejaExecute = true;
    // Reset le flag apres 3 secondes pour permettre de re-naviguer
    // / Reset flag after 3 seconds to allow re-navigation
    setTimeout(function() { _focusExtractionDejaExecute = false; }, 3000);

    var spanDansTexte = document.querySelector(
        '#readability-content .hl-extraction[data-extraction-id="' + extractionCible + '"]'
    );
    if (!spanDansTexte) return;

    // Surligner et scroller vers le passage
    // / Highlight and scroll to the passage
    spanDansTexte.classList.remove('ancre-active');
    void spanDansTexte.offsetWidth;
    spanDansTexte.classList.add('ancre-active');
    spanDansTexte.scrollIntoView({ behavior: 'instant', block: 'center' });

    // Ouvrir la carte inline via la pastille en marge, puis ouvrir les commentaires
    // et focus sur l'input. La pastille declenche un chargement HTMX — on attend
    // que la carte inline apparaisse dans le DOM avant de cliquer sur "Commenter".
    // / Open inline card via the margin dot, then open comments and focus input.
    // / The dot triggers an HTMX load — we wait for the inline card to appear
    // / in the DOM before clicking "Comment".
    var pastille = document.querySelector(
        '.pastille-extraction[data-extraction-id="' + extractionCible + '"]'
    );
    if (pastille) {
        setTimeout(function() {
            // Ne cliquer que si la carte inline n'est pas deja ouverte (evite le toggle fermer)
            // / Only click if inline card is not already open (avoids toggle close)
            var carteDejaOuverte = document.querySelector(
                '.carte-inline[data-extraction-id="' + extractionCible + '"]'
            );
            if (!carteDejaOuverte) {
                pastille.click();
            }
            // Attendre que la carte inline soit chargee (HTMX async)
            // puis cliquer sur le bouton commenter et focus l'input
            // / Wait for inline card to load (HTMX async)
            // / then click comment button and focus input
            var tentatives = 0;
            var intervalVerification = setInterval(function() {
                tentatives++;
                var carteInline = document.querySelector(
                    '.carte-inline[data-extraction-id="' + extractionCible + '"]'
                );
                if (carteInline) {
                    clearInterval(intervalVerification);
                    // Cliquer sur le bouton commenter dans la carte
                    // / Click the comment button in the card
                    var boutonCommenter = carteInline.querySelector('.btn-commenter-extraction');
                    if (boutonCommenter) {
                        boutonCommenter.click();
                        // Attendre que le fil de discussion s'ouvre puis focus l'input
                        // / Wait for discussion thread to open then focus input
                        setTimeout(function() {
                            var inputCommentaire = carteInline.querySelector('textarea, input[type="text"]');
                            if (inputCommentaire) {
                                inputCommentaire.focus();
                            }
                        }, 500);
                    }
                }
                // Abandonner apres 3 secondes (15 tentatives x 200ms)
                // / Give up after 3 seconds (15 attempts x 200ms)
                if (tentatives > 15) clearInterval(intervalVerification);
            }, 200);
        }, 400);
    }
}

// Ecouter htmx:pushedIntoHistory (navigation HTMX)
// / Listen to htmx:pushedIntoHistory (HTMX navigation)
document.body.addEventListener('htmx:pushedIntoHistory', function() {
    setTimeout(_focusExtractionDepuisUrl, 800);
});

// Ecouter aussi htmx:afterSettle sur zone-lecture (backup si pushedIntoHistory rate)
// / Also listen to htmx:afterSettle on zone-lecture (backup if pushedIntoHistory misses)
document.getElementById('zone-lecture').addEventListener('htmx:afterSettle', function() {
    setTimeout(_focusExtractionDepuisUrl, 500);
});

// ==========================================================================
// Menu contextuel de selection de texte
// / Text selection context menu
// ==========================================================================

(function() {
    const menu = document.getElementById('selection-menu');
    const zoneLecture = document.getElementById('zone-lecture');

    // Afficher le menu quand l'utilisateur sélectionne du texte dans la zone de lecture
    zoneLecture.addEventListener('mouseup', function(e) {
        const selection = window.getSelection();
        const text = selection.toString().trim();
        if (!text) return;

        // Positionner le menu a cote de la selection (viewport-safe)
        // / Position menu next to selection (viewport-safe)
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        menu.style.display = 'flex';

        // Gardes viewport : si trop haut → placer en dessous
        // / Viewport guards: if too high → place below
        var menuTop = rect.top - 44;
        if (menuTop < 8) menuTop = rect.bottom + 8;
        menu.style.top = menuTop + 'px';

        // Gardes viewport : clamper horizontalement
        // / Viewport guards: clamp horizontally
        var menuWidth = menu.offsetWidth || 80;
        var leftPos = rect.left + (rect.width / 2) - (menuWidth / 2);
        if (leftPos + menuWidth > window.innerWidth - 8) leftPos = window.innerWidth - menuWidth - 8;
        if (leftPos < 8) leftPos = 8;
        menu.style.left = leftPos + 'px';
    });

    // Cacher le menu au clic hors du menu
    document.addEventListener('mousedown', function(e) {
        if (!menu.contains(e.target)) {
            menu.style.display = 'none';
        }
    });

    // Recupere le page_id et le texte selectionne
    // / Get page_id and selected text
    function recupererContexteSelection() {
        var texteSelectionne = window.getSelection().toString().trim();
        var conteneurPage = zoneLecture.querySelector('[data-page-id]');
        var pageId = conteneurPage ? conteneurPage.dataset.pageId : null;
        return { texte: texteSelectionne, pageId: pageId };
    }

    // --- Bouton extraction manuelle (crayon) ---
    // Ouvre le formulaire simplifie dans le panneau droit
    // / --- Manual extraction button (pencil) ---
    // / Opens simplified form in the right panel
    document.getElementById('btn-extraction-manuelle').addEventListener('click', function() {
        var contexte = recupererContexteSelection();
        if (!contexte.texte || !contexte.pageId) return;

        htmx.ajax('POST', '/extractions/manuelle/', {
            target: '#panneau-extractions',
            swap: 'innerHTML',
            values: { text: contexte.texte, page_id: contexte.pageId },
        });
        menu.style.display = 'none';
    });

    // --- Bouton extraction IA (sparkle) ---
    // Lance une extraction IA sur le texte selectionne, affiche un toast pendant le traitement
    // Peut creer plusieurs extractions si le LLM en detecte plusieurs
    // / --- AI extraction button (sparkle) ---
    // / Launches AI extraction on selected text, shows toast during processing
    // / Can create multiple extractions if the LLM detects several
    var boutonExtractionIa = document.getElementById('btn-extraction-ia');
    if (boutonExtractionIa) {
        boutonExtractionIa.addEventListener('click', function() {
            var contexte = recupererContexteSelection();
            if (!contexte.texte || !contexte.pageId) return;

            menu.style.display = 'none';

            // Toast de chargement / Loading toast
            Swal.fire({
                toast: true, position: 'top-end', icon: 'info',
                title: 'Extraction IA en cours\u2026',
                showConfirmButton: false, timer: 30000, timerProgressBar: true,
                didOpen: function(toast) { toast.dataset.swalExtractionIa = 'true'; },
            });

            // Appel HTMX vers la vue d'extraction IA
            // La vue re-rend le panneau + OOB swap du texte annote
            // / HTMX call to the AI extraction view
            // / The view re-renders the panel + OOB swap of annotated text
            htmx.ajax('POST', '/extractions/ia/', {
                target: '#panneau-extractions',
                swap: 'innerHTML',
                values: { text: contexte.texte, page_id: contexte.pageId },
            });
        });
    }
})();

// ==========================================================================
// Navigation bidirectionnelle : carte <-> barre dans le texte
// Les tags conteneurs sont annotes avec data-extraction-ids cote serveur
// / Bidirectional navigation: card <-> margin bar in text
// ==========================================================================

/**
 * Carte → Span : scroll vers le span surligne dans le texte et le met en surbrillance.
 * / Card → Span: scroll to highlighted span in text and highlight it.
 */
function scrollToExtraction(elementCarte) {
    // Nettoyer les spans actifs precedents / Clean previous active spans
    document.querySelectorAll('.hl-extraction.ancre-active').forEach(function(el) {
        el.classList.remove('ancre-active');
    });

    var extractionId = elementCarte.dataset.extractionId;
    if (!extractionId) return;

    // Chercher le span qui contient cet ID d'extraction
    // / Find the span that contains this extraction ID
    var spanExtraction = document.querySelector(
        '#readability-content .hl-extraction[data-extraction-id="' + extractionId + '"]'
    );

    if (!spanExtraction) {
        console.warn('[scrollToExtraction] Span introuvable pour extraction id=' + extractionId);
        return;
    }

    // Reset animation : retirer la classe, forcer un reflow, puis remettre
    // / Reset animation: remove class, force reflow, then re-add
    spanExtraction.classList.remove('ancre-active');
    void spanExtraction.offsetWidth;
    spanExtraction.classList.add('ancre-active');
    spanExtraction.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

/**
 * Span → Carte : clic sur un span surligne fait clignoter
 * la carte correspondante dans le panneau droit et l'ouvre si ferme.
 * / Span → Card: click on highlighted span flashes the corresponding card
 * in the right panel and opens it if closed.
 */
function scrollToCarteDepuisBloc(extractionId) {
    // D'abord chercher une carte inline deja ouverte (PHASE-09)
    // / First look for an already open inline card (PHASE-09)
    var carteInline = document.querySelector('.carte-inline[data-extraction-id="' + extractionId + '"]');
    if (carteInline) {
        carteInline.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
    }

    // Sinon declencher le clic pastille pour ouvrir la carte inline (PHASE-09)
    // / Otherwise trigger dot click to open inline card (PHASE-09)
    var pastille = document.querySelector('.pastille-extraction[data-extraction-id="' + extractionId + '"]');
    if (pastille) {
        pastille.click();
        return;
    }

    // Fallback : panneau droit (si pas de pastille)
    // / Fallback: right panel (if no dot)
    ouvrirPanneauDroit();

    // Nettoyer les cartes en flash precedentes / Clean previous flashing cards
    document.querySelectorAll('.extraction-card.carte-flash').forEach(function(el) {
        el.classList.remove('carte-flash');
    });

    var carte = document.querySelector(
        '#extraction-results .extraction-card[data-extraction-id="' + extractionId + '"]'
    );

    if (!carte) {
        console.warn('[scrollToCarteDepuisBloc] Carte introuvable pour extraction id=' + extractionId);
        return;
    }

    // Reset animation pour re-clic / Reset animation for re-click
    carte.classList.remove('carte-flash');
    void carte.offsetWidth;
    carte.classList.add('carte-flash');
    carte.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// --- Edition inline du titre de la page ---
// Clic sur le titre → remplace par un input, sauvegarde au blur/Entree, annule a Echap
// / Inline title editing —
// Click on title → replace with input, save on blur/Enter, cancel on Escape
document.addEventListener('click', function(evenement) {
    var titrePage = evenement.target.closest('.titre-page-cliquable');
    if (!titrePage) return;

    // Ne pas ouvrir si un formulaire de titre est deja ouvert
    // / Don't open if a title form is already open
    if (document.querySelector('.formulaire-edition-titre')) return;

    var pageId = titrePage.dataset.pageId;
    var titreActuel = titrePage.textContent.trim();

    // Remplacer le h1 par un input inline
    // / Replace h1 with inline input
    var formulaireTitre = document.createElement('form');
    formulaireTitre.className = 'formulaire-edition-titre mb-1';
    formulaireTitre.setAttribute('hx-post', '/lire/' + pageId + '/modifier_titre/');
    formulaireTitre.setAttribute('hx-target', '#zone-lecture');
    formulaireTitre.setAttribute('hx-swap', 'innerHTML');
    htmx.process(formulaireTitre);

    var inputTitre = document.createElement('input');
    inputTitre.type = 'text';
    inputTitre.name = 'nouveau_titre';
    inputTitre.value = titreActuel;
    inputTitre.className = 'w-full text-2xl font-bold text-slate-900 bg-transparent border-b-2 border-blue-400 outline-none py-0.5';
    inputTitre.style.fontFamily = "'Inter', sans-serif";

    formulaireTitre.appendChild(inputTitre);
    titrePage.replaceWith(formulaireTitre);
    inputTitre.focus();
    inputTitre.select();

    // Entree → soumettre / Enter → submit
    inputTitre.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            htmx.trigger(formulaireTitre, 'submit');
        } else if (e.key === 'Escape') {
            // Echap → annuler, recharger la page avec push-url
            // / Escape → cancel, reload the page with push-url
            var urlLecture = '/lire/' + pageId + '/';
            htmx.ajax('GET', urlLecture, {
                target: '#zone-lecture',
                swap: 'innerHTML',
            }).then(function() {
                history.pushState({}, '', urlLecture);
            });
        }
    });
});

// Clic en dehors du formulaire de titre → sauvegarde auto
// / Click outside title form → auto-save
document.addEventListener('mousedown', function(evenement) {
    var formulaireTitre = document.querySelector('.formulaire-edition-titre');
    if (!formulaireTitre) return;
    if (formulaireTitre.contains(evenement.target)) return;

    htmx.trigger(formulaireTitre, 'submit');
});

// --- Fermer les menus dropdown d'export au clic en dehors ---
// / Close export dropdown menus on outside click
document.addEventListener('click', function(evenement) {
    if (evenement.target.closest('[title="Exporter"]')) return;
    if (evenement.target.closest('.btn-copier-markdown')) return;
    document.querySelectorAll('[title="Exporter"] + div').forEach(function(menu) {
        menu.classList.add('hidden');
    });
});

// --- Copier le contenu Markdown dans le presse-papier ---
// / Copy Markdown content to clipboard
document.addEventListener('click', function(evenement) {
    var boutonCopier = evenement.target.closest('.btn-copier-markdown');
    if (!boutonCopier) return;

    var pageId = boutonCopier.dataset.pageId;
    var urlExportMarkdown = '/lire/' + pageId + '/exporter/?type_export=markdown';

    // Fermer le menu dropdown / Close the dropdown menu
    var menuDropdown = boutonCopier.closest('[title="Exporter"] + div') || boutonCopier.closest('.hidden, div');
    if (menuDropdown) menuDropdown.classList.add('hidden');

    // Recuperer le contenu Markdown depuis l'endpoint existant
    // / Fetch Markdown content from the existing endpoint
    fetch(urlExportMarkdown)
        .then(function(reponse) {
            if (!reponse.ok) throw new Error('Erreur ' + reponse.status);
            return reponse.text();
        })
        .then(function(contenuMarkdown) {
            return navigator.clipboard.writeText(contenuMarkdown);
        })
        .then(function() {
            Swal.fire({
                toast: true, position: 'top-end', icon: 'success',
                title: 'Markdown copié', showConfirmButton: false, timer: 2000,
            });
        })
        .catch(function(erreur) {
            console.error('[Copier Markdown]', erreur);
            Swal.fire({
                toast: true, position: 'top-end', icon: 'error',
                title: 'Erreur lors de la copie', showConfirmButton: false, timer: 2500,
            });
        });
});

// Delegation d'evenement : clic sur un nom de locuteur pour le renommer
// / Event delegation: click on speaker name to rename it
document.addEventListener('click', function(evenement) {
    var nomLocuteur = evenement.target.closest('.speaker-name');
    if (!nomLocuteur) return;

    var elementPage = document.querySelector('#zone-lecture [data-page-id]');
    if (!elementPage) return;
    var pageId = elementPage.dataset.pageId;

    var speakerName = nomLocuteur.dataset.speaker;
    var blockIndex = nomLocuteur.dataset.blockIndex || '0';

    var urlFormulaire = '/lire/' + pageId + '/formulaire_renommer_locuteur/'
        + '?speaker=' + encodeURIComponent(speakerName)
        + '&block_index=' + encodeURIComponent(blockIndex);

    htmx.ajax('GET', urlFormulaire, {
        target: '#zone-modal-locuteur',
        swap: 'innerHTML',
    });
});

// Fermer la modale de renommage apres un renommage reussi
// / Close the rename modal after a successful rename
document.body.addEventListener('fermerModaleRenommer', function() {
    var zoneModale = document.getElementById('zone-modal-locuteur');
    if (zoneModale) zoneModale.innerHTML = '';
    var modale = document.getElementById('modal-renommer-locuteur');
    if (modale) modale.remove();
});

// --- Edition inline des blocs de transcription ---
// Sauvegarde auto : on submit le formulaire ouvert quand on clique en dehors
// ou quand on ouvre un autre bloc. Le bloc precedent se sauve et se ferme.
// / Inline block editing —
// Auto-save: submit the open form when clicking outside
// or when opening another block. The previous block saves and closes.

/**
 * Soumet le formulaire d'edition inline ouvert (s'il existe).
 * Retourne true si un formulaire a ete soumis, false sinon.
 * / Submits the open inline editing form (if any).
 * Returns true if a form was submitted, false otherwise.
 */
function sauvegarderBlocEditionOuvert() {
    var formulaireOuvert = document.querySelector('.formulaire-edition-bloc');
    if (!formulaireOuvert) return false;

    // Declencher le submit HTMX du formulaire ouvert
    // / Trigger HTMX submit of the open form
    htmx.trigger(formulaireOuvert, 'submit');
    return true;
}

// --- Double-clic pour editer un bloc de transcription ---
// Le simple clic reste libre pour la selection de texte et les pastilles.
// Le double-clic ouvre l'edition inline du bloc.
// / Double-click to edit a transcription block —
// Single click stays free for text selection and extraction dots.
// Double-click opens the inline block editor.
document.addEventListener('dblclick', function(evenement) {
    var paragraphe = evenement.target.closest('.texte-bloc-cliquable');
    if (!paragraphe) return;

    // Ignorer si du texte est selectionne (triple-clic = selection de paragraphe)
    // / Ignore if text is selected (triple-click = paragraph selection)
    var selectionActive = window.getSelection();
    var texteSelectionne = selectionActive ? selectionActive.toString().trim() : '';
    if (texteSelectionne.length > 0) {
        selectionActive.removeAllRanges();
    }

    var elementPage = document.querySelector('#zone-lecture [data-page-id]');
    if (!elementPage) return;
    var pageId = elementPage.dataset.pageId;
    var blockIndex = paragraphe.dataset.blockIndex || '0';

    // Sauvegarder le bloc en cours d'edition s'il y en a un
    // / Save the currently editing block if there is one
    var formulaireExistant = document.querySelector('.formulaire-edition-bloc');
    if (formulaireExistant) {
        htmx.trigger(formulaireExistant, 'submit');
        // Attendre que le swap HTMX soit termine avant d'ouvrir le nouveau
        // / Wait for HTMX swap to finish before opening the new one
        setTimeout(function() {
            ouvrirEditionBloc(pageId, blockIndex);
        }, 300);
        return;
    }

    ouvrirEditionBloc(pageId, blockIndex);
});

/**
 * Ouvre le formulaire d'edition inline pour un bloc donne.
 * / Opens the inline editing form for a given block.
 */
function ouvrirEditionBloc(pageId, blockIndex) {
    var urlFormulaire = '/lire/' + pageId + '/formulaire_editer_bloc/'
        + '?block_index=' + encodeURIComponent(blockIndex);

    // Remplacer le bloc entier par le formulaire inline
    // / Replace the entire block with the inline form
    htmx.ajax('GET', urlFormulaire, {
        target: '#speaker-block-' + blockIndex,
        swap: 'outerHTML',
    });
}

// Clic en dehors d'un bloc en edition → sauvegarde auto et fermeture
// On ignore les clics sur les elements du formulaire lui-meme,
// sur les boutons d'action, et sur les modals SweetAlert
// / Click outside an editing block → auto-save and close
// Ignore clicks on the form itself, action buttons, and SweetAlert modals
document.addEventListener('mousedown', function(evenement) {
    var formulaireOuvert = document.querySelector('.formulaire-edition-bloc');
    if (!formulaireOuvert) return;

    // Si le clic est dans le formulaire, on ne fait rien
    // / If click is inside the form, do nothing
    if (formulaireOuvert.contains(evenement.target)) return;

    // Si le clic est sur un autre bloc cliquable, le listener ci-dessus gere deja
    // / If click is on another clickable block, the listener above handles it
    if (evenement.target.closest('.texte-bloc-cliquable')) return;

    // Si le clic est sur un modal SweetAlert, on ne fait rien
    // / If click is on a SweetAlert modal, do nothing
    if (evenement.target.closest('.swal2-container')) return;

    // Si le clic est sur un nom de locuteur (renommage), sauvegarder d'abord
    // / If click is on a speaker name (rename), save first
    if (evenement.target.closest('.speaker-name')) {
        sauvegarderBlocEditionOuvert();
        return;
    }

    // Clic ailleurs → sauvegarde auto
    // / Click elsewhere → auto-save
    sauvegarderBlocEditionOuvert();
});

// Delegation d'evenement : annuler l'edition inline d'un bloc (recharge la page)
// / Event delegation: cancel inline block editing (reload the page)
document.addEventListener('click', function(evenement) {
    var boutonAnnuler = evenement.target.closest('.btn-annuler-edition-bloc');
    if (!boutonAnnuler) return;

    var elementPage = document.querySelector('#zone-lecture [data-page-id]');
    if (!elementPage) return;
    var pageId = elementPage.dataset.pageId;

    // Recharger la lecture complete pour restaurer le bloc original avec push-url
    // / Reload the full reading to restore the original block with push-url
    var urlLecture = '/lire/' + pageId + '/';
    htmx.ajax('GET', urlLecture, {
        target: '#zone-lecture',
        swap: 'innerHTML',
    }).then(function() {
        history.pushState({}, '', urlLecture);
    });
});

// Delegation d'evenement : clic sur le bouton supprimer un bloc (avec confirmation SweetAlert)
// / Event delegation: click on delete block button (with SweetAlert confirmation)
document.addEventListener('click', async function(evenement) {
    var boutonSupprimer = evenement.target.closest('.btn-supprimer-bloc');
    if (!boutonSupprimer) return;
    evenement.preventDefault();

    var pageId = boutonSupprimer.dataset.pageId;
    var blockIndex = boutonSupprimer.dataset.blockIndex;

    var resultat = await Swal.fire({
        title: 'Supprimer ce bloc ?',
        text: 'Cette action est irréversible.',
        icon: 'warning',
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Supprimer',
        confirmButtonColor: '#ef4444',
    });
    if (!resultat.isConfirmed) return;

    htmx.ajax('POST', '/lire/' + pageId + '/supprimer_bloc/', {
        target: '#zone-lecture',
        swap: 'innerHTML',
        values: { index_bloc: blockIndex },
    });
});

// Delegation d'evenement : clic sur le bouton editer d'une carte
// Ouvre la modale d'edition via HTMX (PHASE-26f)
// / Event delegation: click on card edit button, opens edit modal via HTMX (PHASE-26f)
document.addEventListener('click', function(evenement) {
    var boutonEditer = evenement.target.closest('.btn-editer-extraction');
    if (!boutonEditer) return;
    evenement.stopPropagation();

    var entityId = boutonEditer.dataset.entityId;
    var pageId = boutonEditer.dataset.pageId;
    console.log('[Edition extraction modale] entity_id=' + entityId + ' page_id=' + pageId);

    // Fermer le bottom sheet mobile s'il est ouvert (PHASE-26f)
    // / Close mobile bottom sheet if open (PHASE-26f)
    if (window.bottomSheet && window.bottomSheet.estOuvert()) {
        window.bottomSheet.fermer();
    }

    // Ouvrir la modale d'edition (append au body via HX-Retarget)
    // / Open edit modal (appended to body via HX-Retarget)
    htmx.ajax('POST', '/extractions/editer/', {
        target: 'body',
        swap: 'beforeend',
        values: {entity_id: entityId, page_id: pageId},
    });
});

// --- Modale edition extraction : fermeture et focus trap (PHASE-26f) ---
// / Edit extraction modal: close and focus trap (PHASE-26f)

// Fonction utilitaire : fermer et supprimer la modale d'edition
// / Utility: close and remove the edit modal
function fermerModaleExtraction() {
    var modale = document.getElementById('modale-edition-extraction');
    if (modale) modale.remove();
}

// Intercepter le bouton Annuler dans la modale — ferme la modale au lieu du hx-post inline
// Le formulaire inclus a un hx-post="/extractions/panneau/" qui est valide en inline
// mais dans la modale on veut juste fermer sans recharger le panneau.
// Capture phase (3e arg true) pour intercepter avant HTMX.
// / Intercept Cancel button inside modal — close modal instead of inline hx-post
// / The included form has an hx-post that works inline but in modal we just close.
document.addEventListener('click', function(evenement) {
    var modale = document.getElementById('modale-edition-extraction');
    if (!modale) return;
    var boutonAnnuler = evenement.target.closest('[hx-post="/extractions/panneau/"]');
    if (boutonAnnuler && modale.contains(boutonAnnuler)) {
        evenement.preventDefault();
        evenement.stopImmediatePropagation();
        fermerModaleExtraction();
    }
}, true);

// Fermer via Escape / Close via Escape
document.addEventListener('keydown', function(evenement) {
    if (evenement.key === 'Escape') {
        fermerModaleExtraction();
    }
});

// Fermer via clic sur le backdrop / Close via backdrop click
document.addEventListener('click', function(evenement) {
    if (evenement.target.id === 'modale-edition-extraction') {
        fermerModaleExtraction();
    }
});

// Fermer via bouton × / Close via × button
document.addEventListener('click', function(evenement) {
    var boutonFermer = evenement.target.closest('.btn-fermer-modale-extraction');
    if (boutonFermer) {
        fermerModaleExtraction();
    }
});

// Fermer via HX-Trigger 'fermerModaleExtraction' (apres soumission du formulaire)
// Rafraichit la carte inline ouverte via un GET separe sur carte_inline.
// / Close via HX-Trigger 'fermerModaleExtraction' (after form submission)
// / Refreshes the open inline card via a separate GET on carte_inline.
document.body.addEventListener('fermerModaleExtraction', function(evenement) {
    fermerModaleExtraction();

    // Recuperer l'entity_id depuis le detail du trigger
    // / Get entity_id from trigger detail
    var detail = evenement.detail || {};
    var entityId = detail.entityId;
    if (!entityId) return;

    // Rafraichir la carte inline si elle est ouverte dans le DOM
    // / Refresh the inline card if it's open in the DOM
    var carteExistante = document.getElementById('carte-inline-' + entityId);
    if (carteExistante) {
        htmx.ajax('GET', '/extractions/carte_inline/?entity_id=' + entityId, {
            target: carteExistante,
            swap: 'outerHTML',
        });
    }
});

// Focus trap dans la modale : piege Tab/Shift+Tab
// / Focus trap in the modal: trap Tab/Shift+Tab
document.addEventListener('keydown', function(evenement) {
    if (evenement.key !== 'Tab') return;
    var modale = document.getElementById('modale-edition-extraction');
    if (!modale) return;

    var elementsFocusables = modale.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (elementsFocusables.length === 0) return;

    var premierElement = elementsFocusables[0];
    var dernierElement = elementsFocusables[elementsFocusables.length - 1];

    if (evenement.shiftKey) {
        if (document.activeElement === premierElement) {
            evenement.preventDefault();
            dernierElement.focus();
        }
    } else {
        if (document.activeElement === dernierElement) {
            evenement.preventDefault();
            premierElement.focus();
        }
    }
});

// Autofocus + neutralisation du bouton Annuler a l'ouverture de la modale
// Le formulaire inclus a un bouton Annuler avec hx-post="/extractions/panneau/"
// qui est valide en contexte inline mais doit juste fermer la modale ici.
// / Autofocus + Cancel button neutralization when modal opens
// / The included form has a Cancel button with hx-post that works inline
// / but should just close the modal here.
document.body.addEventListener('htmx:afterSwap', function(evenement) {
    var modale = document.getElementById('modale-edition-extraction');
    if (!modale) return;

    // Autofocus le premier champ / Autofocus the first field
    var premierChamp = modale.querySelector('input:not([type="hidden"]), select, textarea');
    if (premierChamp) {
        setTimeout(function() { premierChamp.focus(); }, 50);
    }

    // Neutraliser le bouton Annuler : retirer hx-post et ajouter onclick fermer
    // / Neutralize Cancel button: remove hx-post and add onclick close
    var boutonAnnuler = modale.querySelector('[hx-post="/extractions/panneau/"]');
    if (boutonAnnuler) {
        boutonAnnuler.removeAttribute('hx-post');
        boutonAnnuler.removeAttribute('hx-target');
        boutonAnnuler.removeAttribute('hx-swap');
        boutonAnnuler.removeAttribute('hx-vals');
        boutonAnnuler.addEventListener('click', function() {
            fermerModaleExtraction();
        });
    }
});

// Delegation d'evenement : clic sur une carte d'extraction dans le panneau droit
// Remplace le onclick inline pour survivre aux swaps HTMX
// / Event delegation: click on extraction card in right panel
document.addEventListener('click', function(evenement) {
    var carte = evenement.target.closest('.extraction-card[data-extraction-id]');
    if (!carte) return;
    // Ne pas scroller si on clique sur un bouton d'action
    // / Don't scroll if clicking an action button
    if (evenement.target.closest('.btn-editer-extraction, .btn-commenter-extraction, .btn-supprimer-extraction')) return;
    scrollToExtraction(carte);
});

// ==========================================================================
// Navigation depuis les tableaux d'alignement (cross-documents + versions)
// Clic sur une cellule .alignement-cell → charge la page, scroll + surligne l'extraction
// / Navigation from alignment tables (cross-documents + versions)
// / Click on a .alignement-cell → load page, scroll + highlight the extraction
// ==========================================================================
document.addEventListener('click', function(evenement) {
    var cellule = evenement.target.closest('.alignement-cell[data-extraction-id]');
    if (!cellule) return;

    var pageId = cellule.getAttribute('data-page-id');
    var extractionId = cellule.getAttribute('data-extraction-id');
    if (!pageId || !extractionId) return;

    // Verifier si on est deja sur cette page (conteneur de lecture, pas les cellules d'alignement)
    // / Check if we're already on this page (reading container, not alignment cells)
    var elementPageActuel = document.querySelector('#zone-lecture .lecture-zone-conteneur[data-page-id]');
    var surMemePageDeja = elementPageActuel && elementPageActuel.dataset.pageId === pageId;

    if (surMemePageDeja) {
        // Deja sur la bonne page : scroll direct + ouvrir l'extraction
        // / Already on the right page: direct scroll + open extraction
        _naviguerVersExtraction(extractionId);
        return;
    }

    // Charger la page puis, apres le swap, scroller vers l'extraction
    // / Load the page then, after swap, scroll to the extraction
    var zoneLecture = document.getElementById('zone-lecture');
    if (!zoneLecture) return;

    // Charger la page puis attendre que marginalia.js ait injecte les spans
    // / Load the page then wait for marginalia.js to inject the spans
    htmx.ajax('GET', '/lire/' + pageId + '/', {target: '#zone-lecture', swap: 'innerHTML', pushUrl: true});

    // Polling : attendre que le span ou la pastille apparaisse (marginalia.js les cree apres le swap)
    // / Polling: wait for the span or dot to appear (marginalia.js creates them after swap)
    _attendreEtNaviguer(extractionId, 0);
});

/**
 * Attend que le span hl-extraction ou la pastille apparaisse dans le DOM, puis navigue.
 * Retry toutes les 200ms, max 15 tentatives (3 secondes).
 * / Waits for the hl-extraction span or dot to appear in the DOM, then navigates.
 * / Retries every 200ms, max 15 attempts (3 seconds).
 */
function _attendreEtNaviguer(extractionId, tentative) {
    var maxTentatives = 15;
    var spanTrouve = document.querySelector(
        '#readability-content .hl-extraction[data-extraction-id="' + extractionId + '"]'
    );
    var pastilleTrouvee = document.querySelector(
        '.pastille-extraction[data-extraction-id="' + extractionId + '"]'
    );

    if (spanTrouve || pastilleTrouvee) {
        _naviguerVersExtraction(extractionId);
        return;
    }

    if (tentative < maxTentatives) {
        setTimeout(function() {
            _attendreEtNaviguer(extractionId, tentative + 1);
        }, 200);
    }
}

/**
 * Scroll vers le span surligne dans le texte + ouvre la carte inline de l'extraction.
 * Positionne le texte en haut de la fenetre (block: start).
 * / Scroll to the highlighted span in text + open the inline extraction card.
 * / Positions the text at the top of the viewport (block: start).
 */
function _naviguerVersExtraction(extractionId) {
    // 1. Surligner le span dans le texte (ancre-active avec animation)
    // / 1. Highlight the span in text (ancre-active with animation)
    document.querySelectorAll('.hl-extraction.ancre-active').forEach(function(el) {
        el.classList.remove('ancre-active');
    });

    var spanExtraction = document.querySelector(
        '#readability-content .hl-extraction[data-extraction-id="' + extractionId + '"]'
    );

    if (spanExtraction) {
        spanExtraction.classList.remove('ancre-active');
        void spanExtraction.offsetWidth;
        spanExtraction.classList.add('ancre-active');
        spanExtraction.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // 2. Ouvrir la carte inline via la pastille (si elle existe)
    // / 2. Open the inline card via the dot (if it exists)
    var pastille = document.querySelector('.pastille-extraction[data-extraction-id="' + extractionId + '"]');
    if (pastille) {
        // Delai pour laisser le scroll se terminer avant d'ouvrir la carte
        // / Delay to let scroll finish before opening the card
        setTimeout(function() {
            pastille.click();
        }, 500);
    }
}

// --- Supprimer une page via SweetAlert ---
// / Delete a page via SweetAlert
document.addEventListener('click', async function(evenement) {
    var bouton = evenement.target.closest('.btn-supprimer-page');
    if (!bouton) return;
    evenement.preventDefault();
    evenement.stopPropagation();

    var pageId = bouton.dataset.pageId;
    var resultat = await Swal.fire({
        title: 'Supprimer cette page ?',
        text: 'Cette action est irréversible.',
        icon: 'warning',
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Supprimer',
        confirmButtonColor: '#ef4444',
    });
    if (!resultat.isConfirmed) return;

    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    var reponse = await fetch('/pages/' + pageId + '/supprimer/', {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken},
    });
    if (reponse.ok) {
        var arbreEl = document.getElementById('arbre');
        arbreEl.innerHTML = await reponse.text();
        htmx.process(arbreEl);
    }
});

// --- Supprimer une extraction individuelle via SweetAlert ---
// / Delete a single extraction via SweetAlert
document.addEventListener('click', async function(evenement) {
    var bouton = evenement.target.closest('.btn-supprimer-extraction');
    if (!bouton) return;
    evenement.preventDefault();
    evenement.stopPropagation();

    var entityId = bouton.dataset.entityId;
    var pageId = bouton.dataset.pageId;
    var hasComments = bouton.dataset.hasComments === 'true';

    if (hasComments) {
        Swal.fire({
            title: 'Suppression impossible',
            text: 'Cette extraction a des commentaires. Supprimez-les d\'abord.',
            icon: 'info',
        });
        return;
    }

    var resultat = await Swal.fire({
        title: 'Supprimer cette extraction ?',
        icon: 'warning',
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Supprimer',
        confirmButtonColor: '#ef4444',
    });
    if (!resultat.isConfirmed) return;

    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // Retirer la carte inline du DOM immediatement (PHASE-26f)
    // / Remove inline card from DOM immediately (PHASE-26f)
    var carteInline = document.getElementById('carte-inline-' + entityId);
    if (carteInline) {
        carteInline.remove();
    }

    // Fermer le bottom sheet mobile s'il est ouvert (PHASE-26f)
    // / Close mobile bottom sheet if open (PHASE-26f)
    if (window.bottomSheet && window.bottomSheet.estOuvert()) {
        window.bottomSheet.fermer();
    }

    htmx.ajax('POST', '/extractions/supprimer_entite/', {
        target: '#panneau-extractions',
        swap: 'innerHTML',
        values: {entity_id: entityId, page_id: pageId},
    });
});

// --- Supprimer toutes les extractions IA via SweetAlert ---
// / Delete all AI extractions via SweetAlert
document.addEventListener('click', async function(evenement) {
    var bouton = evenement.target.closest('.btn-supprimer-extractions-ia');
    if (!bouton) return;
    evenement.preventDefault();

    var pageId = bouton.dataset.pageId;
    var resultat = await Swal.fire({
        title: 'Supprimer les extractions IA ?',
        text: 'Les extractions manuelles seront conservées.',
        icon: 'warning',
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Supprimer',
        confirmButtonColor: '#ef4444',
    });
    if (!resultat.isConfirmed) return;

    htmx.ajax('POST', '/extractions/supprimer_ia/', {
        target: '#panneau-extractions',
        swap: 'innerHTML',
        values: {page_id: pageId},
    });
});

// --- Promouvoir les extractions en donnees d'entrainement ---
// Le bouton charge le formulaire via HTMX (GET /extractions/formulaire_promouvoir/)
// Les boutons Confirmer/Annuler du partial sont geres ici par delegation
// / The button loads the form via HTMX (GET /extractions/formulaire_promouvoir/)
// / Confirm/Cancel buttons in the partial are handled here via delegation
document.addEventListener('click', function(evenement) {
    // Bouton Annuler : vide la zone du formulaire
    // / Cancel button: clear the form zone
    var boutonAnnuler = evenement.target.closest('.btn-annuler-promotion');
    if (boutonAnnuler) {
        var zoneFormulaire = document.getElementById('zone-promouvoir-entrainement');
        if (zoneFormulaire) zoneFormulaire.innerHTML = '';
        return;
    }

    // Bouton Confirmer : envoie le POST avec les valeurs du select
    // / Confirm button: send POST with select values
    var boutonConfirmer = evenement.target.closest('.btn-confirmer-promotion');
    if (!boutonConfirmer) return;

    var pageId = boutonConfirmer.dataset.pageId;
    var selectAnalyseur = document.getElementById('select-analyseur-promotion');
    if (!selectAnalyseur || !selectAnalyseur.value) return;

    htmx.ajax('POST', '/extractions/promouvoir_entrainement/', {
        target: '#panneau-extractions',
        swap: 'innerHTML',
        values: {page_id: pageId, analyseur_id: selectAnalyseur.value},
    });
});

// --- Confirmation transcription audio ---
// Bouton Confirmer : lance la transcription via POST /import/confirmer_audio/
// Bouton Annuler : vide la zone-lecture
// / Confirm button: launches transcription via POST /import/confirmer_audio/
// / Cancel button: clears zone-lecture
document.addEventListener('click', function(evenement) {
    // Annuler la transcription / Cancel transcription
    var boutonAnnulerTranscription = evenement.target.closest('.btn-annuler-transcription');
    if (boutonAnnulerTranscription) {
        var zoneConfirmation = document.getElementById('confirmation-audio');
        if (zoneConfirmation) zoneConfirmation.closest('.max-w-xl').remove();
        return;
    }

    // Confirmer la transcription / Confirm transcription
    var boutonConfirmerTranscription = evenement.target.closest('.btn-confirmer-transcription');
    if (!boutonConfirmerTranscription) return;

    var cheminTemp = boutonConfirmerTranscription.dataset.cheminTemp;
    var nomFichier = boutonConfirmerTranscription.dataset.nomFichier;

    // Recuperer la langue choisie par l'utilisateur
    // / Get the language chosen by the user
    var selectLangue = document.getElementById('langue-audio-select');
    var langueAudio = selectLangue ? selectLangue.value : '';

    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    var headers = {'Content-Type': 'application/x-www-form-urlencoded'};
    if (csrfToken) headers['X-CSRFToken'] = csrfToken.value;
    headers['HX-Request'] = 'true';

    fetch('/import/confirmer_audio/', {
        method: 'POST',
        headers: headers,
        body: 'chemin_fichier_temp=' + encodeURIComponent(cheminTemp)
            + '&nom_fichier=' + encodeURIComponent(nomFichier)
            + '&language=' + encodeURIComponent(langueAudio),
    })
    .then(function(reponse) {
        if (!reponse.ok) {
            return reponse.text().then(function(texte) {
                document.getElementById('zone-lecture').innerHTML = texte;
            });
        }
        return reponse.text().then(function(htmlComplet) {
            traiterReponseAvecOob(htmlComplet);
            Swal.fire({
                toast: true, position: 'top-end', icon: 'info',
                title: 'Transcription lancée...', showConfirmButton: false, timer: 2500,
            });
        });
    })
    .catch(function(erreur) {
        console.error('[Confirmer audio]', erreur);
        Swal.fire({icon: 'error', title: 'Erreur', text: 'Erreur lors du lancement de la transcription.'});
    });
});

// ==========================================================================
// PHASE-04 — CRUD manquants : dossiers (renommer, supprimer) + commentaires
// / PHASE-04 — Missing CRUDs: folders (rename, delete) + comments
// ==========================================================================

// --- Renommer un dossier via SweetAlert ---
// / Rename a folder via SweetAlert
document.addEventListener('click', async function(evenement) {
    var bouton = evenement.target.closest('.btn-renommer-dossier');
    if (!bouton) return;
    evenement.preventDefault();
    evenement.stopPropagation();

    var dossierId = bouton.dataset.dossierId;
    var nomActuel = bouton.dataset.dossierNom;

    var resultat = await Swal.fire({
        title: 'Renommer le dossier',
        input: 'text',
        inputValue: nomActuel,
        inputPlaceholder: 'Nouveau nom',
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Renommer',
        inputValidator: function(valeur) {
            if (!valeur || !valeur.trim()) return 'Le nom ne peut pas être vide';
        },
    });
    if (!resultat.isConfirmed) return;

    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    var reponse = await fetch('/dossiers/' + dossierId + '/renommer/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'nouveau_nom=' + encodeURIComponent(resultat.value.trim()),
    });
    if (reponse.ok) {
        var arbreEl = document.getElementById('arbre');
        arbreEl.innerHTML = await reponse.text();
        htmx.process(arbreEl);
    }
});

// --- Supprimer un dossier via SweetAlert (avec avertissement si pages) ---
// / Delete a folder via SweetAlert (with warning if it contains pages)
document.addEventListener('click', async function(evenement) {
    var bouton = evenement.target.closest('.btn-supprimer-dossier');
    if (!bouton) return;
    evenement.preventDefault();
    evenement.stopPropagation();

    var dossierId = bouton.dataset.dossierId;
    var nomDossier = bouton.dataset.dossierNom;
    var nombrePages = parseInt(bouton.dataset.pagesCount, 10) || 0;

    var texteConfirmation = 'Cette action est irréversible.';
    if (nombrePages > 0) {
        texteConfirmation = 'Ce dossier contient ' + nombrePages + ' page(s). Elles seront reclassées en non classées.';
    }

    var resultat = await Swal.fire({
        title: 'Supprimer « ' + nomDossier + ' » ?',
        text: texteConfirmation,
        icon: 'warning',
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Supprimer',
        confirmButtonColor: '#ef4444',
    });
    if (!resultat.isConfirmed) return;

    var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    var reponse = await fetch('/dossiers/' + dossierId + '/', {
        method: 'DELETE',
        headers: {'X-CSRFToken': csrfToken},
    });
    if (reponse.ok) {
        var arbreEl = document.getElementById('arbre');
        arbreEl.innerHTML = await reponse.text();
        htmx.process(arbreEl);
    }
});

// --- Modifier un commentaire via SweetAlert ---
// / Edit a comment via SweetAlert
document.addEventListener('click', async function(evenement) {
    var bouton = evenement.target.closest('.btn-modifier-commentaire');
    if (!bouton) return;
    evenement.preventDefault();
    evenement.stopPropagation();

    var commentaireId = bouton.dataset.commentaireId;
    var texteActuel = bouton.dataset.commentaireTexte;

    var resultat = await Swal.fire({
        title: 'Modifier le commentaire',
        input: 'textarea',
        inputValue: texteActuel,
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Enregistrer',
        inputValidator: function(valeur) {
            if (!valeur || !valeur.trim()) return 'Le commentaire ne peut pas être vide';
        },
    });
    if (!resultat.isConfirmed) return;

    htmx.ajax('POST', '/extractions/modifier_commentaire/', {
        target: '#panneau-extractions',
        swap: 'innerHTML',
        values: {commentaire_id: commentaireId, commentaire: resultat.value.trim()},
    });
});

// --- Supprimer un commentaire via SweetAlert ---
// / Delete a comment via SweetAlert
document.addEventListener('click', async function(evenement) {
    var bouton = evenement.target.closest('.btn-supprimer-commentaire');
    if (!bouton) return;
    evenement.preventDefault();
    evenement.stopPropagation();

    var commentaireId = bouton.dataset.commentaireId;

    var resultat = await Swal.fire({
        title: 'Supprimer ce commentaire ?',
        text: 'Cette action est irréversible.',
        icon: 'warning',
        showCancelButton: true,
        cancelButtonText: 'Annuler',
        confirmButtonText: 'Supprimer',
        confirmButtonColor: '#ef4444',
    });
    if (!resultat.isConfirmed) return;

    htmx.ajax('POST', '/extractions/supprimer_commentaire/', {
        target: '#panneau-extractions',
        swap: 'innerHTML',
        values: {commentaire_id: commentaireId},
    });
});


// ==========================================================================
// Focus extraction au chargement initial (F5 avec ?extraction={id}) — PHASE-25d-v2
// / Focus extraction on initial page load (F5 with ?extraction={id}) — PHASE-25d-v2
// ==========================================================================
(function() {
    var parametresUrl = new URLSearchParams(window.location.search);
    if (!parametresUrl.get('extraction')) return;

    // Attendre que le DOM soit completement rendu
    // / Wait for the DOM to be fully rendered
    window.addEventListener('load', function() {
        setTimeout(_focusExtractionDepuisUrl, 800);
    });
})();


// ===========================================================================
// === A.6 — WebSocket notifications + dropdown taches ===
// / A.6 — WebSocket notifications + tasks dropdown
// ===========================================================================
//
// Une seule connexion WebSocket par session vers le NotificationConsumer.
// Le consumer ne pousse plus que des messages 'tache_terminee' (refonte A.6) :
// a chaque message recu, on refetch le bouton pour mettre a jour son etat
// (couleur + badge). Le dropdown s'ouvre au clic sur le bouton et fetch
// la liste des 10 dernieres taches.
//
// / One WebSocket connection per session to NotificationConsumer.
// / Consumer only pushes 'tache_terminee' messages (A.6 refactor):
// / on each message, refetch button to update state (color + badge).
// / Dropdown opens on button click and fetches last 10 tasks.
// ---------------------------------------------------------------------------

(function() {
    // Ne lance la connexion que si l'utilisateur est authentifie.
    // Le bouton est rendu conditionnellement dans base.html ;
    // son absence signifie 'pas de session' donc pas de WS a ouvrir.
    // / Only open connection if user is authenticated.
    // / Button is conditionally rendered in base.html;
    // / its absence means 'no session' so no WS to open.
    if (!document.getElementById('btn-taches')) return;

    // Connexion au consumer NotificationConsumer (1 seule connexion par session).
    // / Connect to NotificationConsumer (1 connection per session).
    var protocoleWebSocket = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    var urlWebSocket = protocoleWebSocket + window.location.host + '/ws/notifications/';
    var connexionTaches = new WebSocket(urlWebSocket);

    // Logs de debug : connexion ouverte / fermee / erreur / message recu.
    // Utiles pour diagnostiquer les problemes de notifications.
    // / Debug logs: connection open / closed / error / message received.
    connexionTaches.addEventListener('open', function() {
        console.log('[A.6] WebSocket taches : connecte sur', urlWebSocket);
    });
    connexionTaches.addEventListener('close', function(evenement) {
        console.log('[A.6] WebSocket taches : ferme (code=' + evenement.code + ')');
    });
    connexionTaches.addEventListener('error', function(evenement) {
        console.error('[A.6] WebSocket taches : erreur', evenement);
    });

    // Helper : refetch le bouton + le dropdown si ouvert.
    // Utilise par le WS handler ET par le HX-Trigger 'tachesChanged'
    // (declenche quand on lance une analyse/synthese pour reflet immediat).
    // / Helper: refetch button + dropdown if open.
    // / Used by WS handler AND by HX-Trigger 'tachesChanged'
    // / (fired on analyse/synthese launch for immediate reflection).
    function rafraichirBoutonTaches() {
        htmx.ajax('GET', '/taches/bouton/', {
            target: '#btn-taches',
            swap: 'outerHTML'
        });
        var dropdownOuvert = document.getElementById('taches-dropdown-wrapper');
        if (dropdownOuvert && !dropdownOuvert.classList.contains('hidden')) {
            htmx.ajax('GET', '/taches/dropdown/', {
                target: '#taches-dropdown-content',
                swap: 'innerHTML'
            });
        }
    }

    // A la reception d'un message 'tache_terminee', refetch le bouton
    // pour mettre a jour son etat (couleur + badge).
    // / On 'tache_terminee', refetch button to update state.
    connexionTaches.addEventListener('message', function(evenement) {
        var donneesMessage = JSON.parse(evenement.data);
        console.log('[A.6] WebSocket taches : message recu', donneesMessage);
        if (donneesMessage.type === 'tache_terminee') {
            rafraichirBoutonTaches();
        }
    });

    // Ecoute l'event HTMX 'tachesChanged' (envoye par le serveur via HX-Trigger
    // dans la reponse a /lire/{pk}/analyser/ et /lire/{pk}/synthetiser/).
    // Permet au bouton de passer immediatement a l'etat 'en_cours' au lancement
    // d'une tache (sans attendre le prochain WS push qui ne vient qu'a la fin).
    // / Listen to HTMX 'tachesChanged' event (sent by server via HX-Trigger
    // / in response to /lire/{pk}/analyser/ and /lire/{pk}/synthetiser/).
    // / Lets the button immediately switch to 'en_cours' state on task launch
    // / (without waiting for next WS push which only fires at end).
    document.body.addEventListener('tachesChanged', function() {
        console.log('[A.6] HX-Trigger tachesChanged : refetch bouton');
        rafraichirBoutonTaches();
    });

    // Toggle dropdown au clic sur le bouton.
    // Click ailleurs = fermer le dropdown.
    // / Toggle dropdown on button click.
    // / Click elsewhere = close dropdown.
    document.body.addEventListener('click', function(evenement) {
        var boutonTaches = evenement.target.closest('#btn-taches');
        var dropdownTaches = document.getElementById('taches-dropdown-wrapper');
        if (!dropdownTaches) return;

        if (boutonTaches) {
            evenement.preventDefault();
            dropdownTaches.classList.toggle('hidden');
            // Si on vient d'ouvrir : fetch la liste fraiche
            // / If just opened: fetch fresh list
            if (!dropdownTaches.classList.contains('hidden')) {
                htmx.ajax('GET', '/taches/dropdown/', {
                    target: '#taches-dropdown-content',
                    swap: 'innerHTML'
                });
            }
        } else if (!evenement.target.closest('#taches-dropdown-wrapper')) {
            // Click ailleurs : fermer le dropdown
            // / Click elsewhere: close dropdown
            dropdownTaches.classList.add('hidden');
        }
    });

    // Au chargement : fetch initial du bouton pour avoir l'etat reel
    // (les compteurs/couleur dependent de la DB).
    // / On load: initial fetch of button to get real state from DB.
    document.addEventListener('DOMContentLoaded', function() {
        if (document.getElementById('btn-taches')) {
            htmx.ajax('GET', '/taches/bouton/', {
                target: '#btn-taches',
                swap: 'outerHTML'
            });
        }
    });
})();
