/**
 * Arbre overlay — PHASE-08
 * Gere l'ouverture et la fermeture du panneau lateral de navigation.
 * Le panneau contient l'arbre de dossiers (bibliotheque).
 * Il s'ouvre en overlay avec backdrop assombri.
 * / Tree overlay — PHASE-08
 * / Manages the side navigation panel (library/folder tree) open/close.
 *
 * LOCALISATION : front/static/front/js/arbre_overlay.js
 *
 * COMMUNICATION :
 * Ecoute : clic sur #btn-hamburger-arbre, #btn-fermer-arbre, #arbre-backdrop
 * Ecoute : clic delegue sur #arbre .lien-page (ferme apres navigation)
 * Ecoute : clic delegue sur [data-placeholder] (toast phase future)
 * Note : #btn-toolbar-analyser est gere par HTMX (OOB swap dans lecture_principale.html)
 * Ecoute : clic sur #btn-creer-dossier-overlay (SweetAlert + HTMX POST /dossiers/)
 * Ecoute : change sur #input-import-fichier-overlay (relaye vers input principal)
 * Ecoute : keydown T (toggle arbre), Escape (ferme arbre)
 * Expose : window.arbreOverlay = { ouvrir, fermer, basculer, estOuvert }
 */
(function() {
    'use strict';

    var boutonHamburger = document.getElementById('btn-hamburger-arbre');
    var boutonFermer = document.getElementById('btn-fermer-arbre');
    var backdrop = document.getElementById('arbre-backdrop');
    var overlay = document.getElementById('arbre-overlay');

    var arbreEstOuvert = false;

    // Extrait le token CSRF depuis le header hx-headers du body
    // / Extract CSRF token from body's hx-headers attribute
    function extraireTokenCsrf() {
        var headersBrut = document.querySelector('body').getAttribute('hx-headers');
        if (!headersBrut) return '';
        try {
            return JSON.parse(headersBrut)['X-CSRFToken'];
        } catch (erreur) {
            return '';
        }
    }

    // Ouvre l'overlay arbre avec animation
    // / Open the tree overlay with animation
    function ouvrirArbre() {
        if (arbreEstOuvert) return;
        arbreEstOuvert = true;

        // Affiche le backdrop et force un reflow avant de retirer opacity-0
        // / Show backdrop and force reflow before removing opacity-0
        backdrop.classList.remove('hidden');
        void backdrop.offsetWidth;
        backdrop.classList.remove('opacity-0');

        // Glisse l'overlay depuis la gauche et reactive les clics
        // / Slide overlay in from the left and re-enable pointer events
        overlay.classList.remove('-translate-x-full');
        overlay.classList.remove('pointer-events-none');

        // Focus sur le bouton fermer pour accessibilite
        // / Focus close button for accessibility
        boutonFermer.focus();
    }

    // Ferme l'overlay arbre avec animation
    // / Close the tree overlay with animation
    function fermerArbre() {
        if (!arbreEstOuvert) return;
        arbreEstOuvert = false;

        // Anime la fermeture du backdrop
        // / Animate backdrop closing
        backdrop.classList.add('opacity-0');

        // Glisse l'overlay vers la gauche et desactive les clics
        // / Slide overlay out to the left and disable pointer events
        overlay.classList.add('-translate-x-full');
        overlay.classList.add('pointer-events-none');

        // Apres la transition, cache completement le backdrop
        // / After transition, fully hide the backdrop
        setTimeout(function() {
            backdrop.classList.add('hidden');
        }, 200);

        // Remet le focus sur le hamburger
        // / Return focus to hamburger
        boutonHamburger.focus();
    }

    // Bascule ouvert/ferme
    // / Toggle open/close
    function basculerArbre() {
        if (arbreEstOuvert) {
            fermerArbre();
        } else {
            ouvrirArbre();
        }
    }

    // --- Evenements ---
    // --- Events ---

    // Clic hamburger → bascule
    // / Hamburger click → toggle
    boutonHamburger.addEventListener('click', basculerArbre);

    // Clic fermer → ferme
    // / Close click → close
    boutonFermer.addEventListener('click', fermerArbre);

    // Clic backdrop → ferme
    // / Backdrop click → close
    backdrop.addEventListener('click', fermerArbre);

    // NOTE : Les raccourcis clavier (T, Escape) sont geres par keyboard.js (PHASE-17)
    // / NOTE: Keyboard shortcuts (T, Escape) are handled by keyboard.js (PHASE-17)

    // Clic delegue sur un lien de page dans l'arbre → ferme apres un court delai
    // / Delegated click on page link in tree → close after short delay
    document.getElementById('arbre').addEventListener('click', function(evenement) {
        var lienPage = evenement.target.closest('.lien-page');
        if (lienPage) {
            setTimeout(fermerArbre, 100);
        }
    });

    // Bouton creer dossier dans l'overlay → SweetAlert + HTMX
    // / Create folder button in overlay → SweetAlert + HTMX
    document.getElementById('btn-creer-dossier-overlay').addEventListener('click', function() {
        Swal.fire({
            title: 'Nouveau dossier',
            input: 'text',
            inputPlaceholder: 'Nom du dossier',
            showCancelButton: true,
            confirmButtonText: 'Créer',
            cancelButtonText: 'Annuler',
            inputValidator: function(valeur) {
                if (!valeur || !valeur.trim()) {
                    return 'Le nom du dossier est requis';
                }
            }
        }).then(function(resultat) {
            if (resultat.isConfirmed && resultat.value) {
                htmx.ajax('POST', '/dossiers/', {
                    target: '#arbre',
                    swap: 'innerHTML',
                    values: { nom: resultat.value.trim() },
                    headers: { 'X-CSRFToken': extraireTokenCsrf() }
                });
            }
        });
    });

    // Import fichier depuis l'overlay → relaye vers l'input principal
    // / File import from overlay → relay to main input
    document.getElementById('input-import-fichier-overlay').addEventListener('change', function() {
        var fichierOverlay = this.files[0];
        if (!fichierOverlay) return;

        // Copie le fichier vers l'input principal via DataTransfer
        // / Copy file to main input via DataTransfer
        var transfert = new DataTransfer();
        transfert.items.add(fichierOverlay);

        var inputPrincipal = document.getElementById('input-import-fichier');
        inputPrincipal.files = transfert.files;

        // Declenche le change sur l'input principal
        // / Trigger change on main input
        inputPrincipal.dispatchEvent(new Event('change', { bubbles: true }));

        // Reset l'input overlay et ferme
        // / Reset overlay input and close
        this.value = '';
        fermerArbre();
    });

    // Clic delegue sur boutons placeholder → toast "Prevu en PHASE-XX"
    // / Delegated click on placeholder buttons → toast "Planned for PHASE-XX"
    document.addEventListener('click', function(evenement) {
        var boutonPlaceholder = evenement.target.closest('[data-placeholder]');
        if (boutonPlaceholder) {
            var phase = boutonPlaceholder.getAttribute('data-placeholder');
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'info',
                title: 'Prévu en ' + phase,
                showConfirmButton: false,
                timer: 2000,
                timerProgressBar: true
            });
            evenement.preventDefault();
        }
    });

    // Le bouton Analyser est desormais gere par HTMX (attributs hx-get sur le bouton)
    // Ses attributs sont mis a jour via OOB swap dans lecture_principale.html
    // / The Analyze button is now handled by HTMX (hx-get attributes on the button)
    // Its attributes are updated via OOB swap in lecture_principale.html

    // Accordeon sections arbre — delegation d'evenements (PHASE-25c)
    // / Accordion tree sections — event delegation (PHASE-25c)
    document.getElementById('arbre').addEventListener('click', function(evenement) {
        var boutonSection = evenement.target.closest('.arbre-section-toggle');
        if (!boutonSection) return;

        var idContenu = boutonSection.getAttribute('aria-controls');
        var contenuSection = document.getElementById(idContenu);
        if (!contenuSection) return;

        var estExpanse = boutonSection.getAttribute('aria-expanded') === 'true';

        // Basculer l'etat / Toggle state
        boutonSection.setAttribute('aria-expanded', estExpanse ? 'false' : 'true');
        contenuSection.classList.toggle('hidden');

        // Rotation du chevron / Chevron rotation
        var chevron = boutonSection.querySelector('.arbre-section-chevron');
        if (chevron) {
            chevron.classList.toggle('rotate-90');
        }
    });

    // Bouton quitter partage — delegation d'evenements avec confirmation (PHASE-25c)
    // / Leave share button — event delegation with confirmation (PHASE-25c)
    document.getElementById('arbre').addEventListener('click', function(evenement) {
        var boutonQuitter = evenement.target.closest('.btn-quitter-partage');
        if (!boutonQuitter) return;

        evenement.stopPropagation();
        var dossierId = boutonQuitter.getAttribute('data-dossier-id');

        // Confirmation SweetAlert avant de quitter le partage
        // / SweetAlert confirmation before leaving the share
        Swal.fire({
            title: 'Quitter ce partage ?',
            text: 'Vous perdrez l\'acces a ce dossier. Le proprietaire devra re-partager.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Quitter',
            cancelButtonText: 'Annuler',
            confirmButtonColor: '#ef4444',
        }).then(function(resultat) {
            if (resultat.isConfirmed) {
                htmx.ajax('POST', '/dossiers/' + dossierId + '/quitter/', {
                    target: '#arbre',
                    swap: 'innerHTML',
                    headers: { 'X-CSRFToken': extraireTokenCsrf() }
                });
            }
        });
    });

    // Expose l'API publique pour les tests
    // / Expose public API for testing
    window.arbreOverlay = {
        ouvrir: ouvrirArbre,
        fermer: fermerArbre,
        basculer: basculerArbre,
        estOuvert: function() { return arbreEstOuvert; }
    };

})();
