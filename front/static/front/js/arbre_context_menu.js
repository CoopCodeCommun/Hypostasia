/**
 * Menu contextuel de l'arbre de dossiers et pages (PHASE-25 UX).
 * Remplace les boutons hover-only par un menu contextuel accessible.
 * / Context menu for folder/page tree (PHASE-25 UX).
 * Replaces hover-only buttons with an accessible context menu.
 *
 * LOCALISATION : front/static/front/js/arbre_context_menu.js
 *
 * COMMUNICATION :
 * Ecoute : clic sur .btn-ctx-menu (bouton kebab "...")
 * Ecoute : contextmenu (clic droit) sur [data-ctx-type]
 * Ecoute : touchstart/touchend (appui long mobile) sur [data-ctx-type]
 * Declenche : les memes actions que les anciens boutons hover
 *   - .btn-renommer-dossier, .btn-supprimer-dossier, .btn-classer, .btn-supprimer-page
 *   - HTMX GET pour le partage
 *
 * DEPENDENCIES :
 * - hypostasia.js (handlers existants pour renommer, supprimer, classer)
 * - SweetAlert2 (pour les confirmations)
 * - HTMX (pour le partage)
 */
(function() {
    'use strict';

    var menuContextuel = document.getElementById('arbre-ctx-menu');
    if (!menuContextuel) return;

    // Delai pour l'appui long mobile (ms)
    // / Long press delay for mobile (ms)
    var DELAI_APPUI_LONG = 500;
    var timerAppuiLong = null;

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

    // Ferme le menu contextuel
    // / Close the context menu
    function fermerMenu() {
        menuContextuel.classList.add('hidden');
        menuContextuel.innerHTML = '';
    }

    // Positionne et affiche le menu contextuel a cote d'un element
    // Le menu s'affiche en dessous du clic, ou au-dessus si pas de place
    // / Position and show the context menu next to an element
    // Menu appears below click, or above if no room
    function afficherMenu(positionX, positionY, contenuHtml) {
        menuContextuel.innerHTML = contenuHtml;
        menuContextuel.classList.remove('hidden');

        // Calcule la position finale en tenant compte des bords de l'ecran
        // / Calculate final position considering screen edges
        var largeurMenu = menuContextuel.offsetWidth;
        var hauteurMenu = menuContextuel.offsetHeight;
        var largeurEcran = window.innerWidth;
        var hauteurEcran = window.innerHeight;

        var positionFinaleX = positionX;
        var positionFinaleY = positionY;

        // Si le menu depasse a droite, le decaler a gauche
        // / If menu overflows right, shift left
        if (positionFinaleX + largeurMenu > largeurEcran - 8) {
            positionFinaleX = largeurEcran - largeurMenu - 8;
        }

        // Si le menu depasse en bas, l'afficher au-dessus du clic
        // / If menu overflows bottom, show above click
        if (positionFinaleY + hauteurMenu > hauteurEcran - 8) {
            positionFinaleY = positionY - hauteurMenu;
        }

        // Empeche les positions negatives
        // / Prevent negative positions
        if (positionFinaleX < 4) positionFinaleX = 4;
        if (positionFinaleY < 4) positionFinaleY = 4;

        menuContextuel.style.left = positionFinaleX + 'px';
        menuContextuel.style.top = positionFinaleY + 'px';
    }

    // Construit le HTML du menu pour un dossier
    // / Build menu HTML for a folder
    function construireMenuDossier(dossierId, dossierNom, nombrePages, estProprietaire, visibiliteActuelle) {
        var items = '';

        // Renommer, Supprimer, Partager, Visibilite → reserve au proprietaire
        // / Rename, Delete, Share, Visibility → owner only
        if (estProprietaire) {
            items += boutonMenuItem('Renommer', 'btn-action-renommer', dossierId);
            items += boutonMenuItem('Supprimer', 'btn-action-supprimer-dossier', dossierId, 'text-red-600');
            items += '<hr class="my-1 border-slate-100">';
            items += boutonMenuItem('Partager', 'btn-action-partager', dossierId);

            // Sous-section visibilite avec 3 items radio-like
            // / Visibility sub-section with 3 radio-like items
            items += '<hr class="my-1 border-slate-100">';
            items += '<p class="px-3 py-1 text-[10px] text-slate-400 uppercase tracking-wider font-medium">Visibilite</p>';
            var niveaux = [
                { valeur: 'prive', label: '🔒 Prive' },
                { valeur: 'partage', label: '👥 Partage' },
                { valeur: 'public', label: '🌐 Public' },
            ];
            for (var i = 0; i < niveaux.length; i++) {
                var estActif = (niveaux[i].valeur === visibiliteActuelle);
                var classeActive = estActif ? 'bg-blue-50 font-medium text-blue-700' : 'text-slate-700';
                var prefixe = estActif ? '✓ ' : '  ';
                items += '<button class="btn-action-visibilite w-full text-left px-3 py-1.5 text-sm ' + classeActive + ' hover:bg-slate-50 transition-colors" '
                       + 'data-item-id="' + dossierId + '" data-visibilite="' + niveaux[i].valeur + '" role="menuitem">'
                       + prefixe + niveaux[i].label
                       + '</button>';
            }
        }

        return items;
    }

    // Construit le HTML du menu pour une page
    // Deplacer et supprimer sont reserves au proprietaire du dossier
    // / Build menu HTML for a page
    // / Move and delete are owner-only
    function construireMenuPage(pageId, estProprietaire) {
        var items = '';
        if (estProprietaire) {
            items += boutonMenuItem('Deplacer', 'btn-action-deplacer', pageId);
            items += boutonMenuItem('Supprimer', 'btn-action-supprimer-page', pageId, 'text-red-600');
        }
        return items;
    }

    // Genere un item de menu
    // / Generate a menu item
    function boutonMenuItem(label, actionClass, itemId, couleurExtra) {
        var classesCouleur = couleurExtra || 'text-slate-700';
        return '<button class="' + actionClass + ' w-full text-left px-3 py-1.5 text-sm ' + classesCouleur + ' hover:bg-slate-50 transition-colors" '
             + 'data-item-id="' + itemId + '" role="menuitem">'
             + label
             + '</button>';
    }

    // Ouvre le menu contextuel pour un element de l'arbre
    // / Open context menu for a tree element
    function ouvrirMenuPourElement(elementCible, positionX, positionY) {
        var typeCible = elementCible.getAttribute('data-ctx-type');
        var idCible = elementCible.getAttribute('data-ctx-id');
        var nomCible = elementCible.getAttribute('data-ctx-nom');

        if (!typeCible || !idCible) return;

        var contenuMenu = '';

        if (typeCible === 'dossier') {
            var nombrePages = elementCible.getAttribute('data-ctx-pages') || '0';
            var estProprietaire = elementCible.hasAttribute('data-ctx-owner');
            var visibiliteActuelle = elementCible.getAttribute('data-ctx-visibilite') || 'prive';
            contenuMenu = construireMenuDossier(idCible, nomCible, nombrePages, estProprietaire, visibiliteActuelle);
        } else if (typeCible === 'page') {
            var estProprietairePage = elementCible.hasAttribute('data-ctx-owner');
            contenuMenu = construireMenuPage(idCible, estProprietairePage);
        }

        if (!contenuMenu) return;

        afficherMenu(positionX, positionY, contenuMenu);
    }

    // --- Delegation d'evenements pour les actions du menu ---
    // --- Event delegation for menu actions ---

    menuContextuel.addEventListener('click', function(evenement) {
        var boutonAction = evenement.target.closest('[data-item-id]');
        if (!boutonAction) return;

        var itemId = boutonAction.getAttribute('data-item-id');
        fermerMenu();

        // Renommer un dossier — declenche le SweetAlert existant
        // / Rename folder — triggers existing SweetAlert
        if (boutonAction.classList.contains('btn-action-renommer')) {
            var noeudDossier = document.querySelector('[data-dossier-id="' + itemId + '"]');
            var nomActuel = noeudDossier ? noeudDossier.querySelector('[data-ctx-nom]') : null;
            var valeurNom = nomActuel ? nomActuel.getAttribute('data-ctx-nom') : '';

            Swal.fire({
                title: 'Renommer le dossier',
                input: 'text',
                inputValue: valeurNom,
                showCancelButton: true,
                confirmButtonText: 'Renommer',
                cancelButtonText: 'Annuler',
                inputValidator: function(valeur) {
                    if (!valeur || !valeur.trim()) return 'Le nom ne peut pas etre vide';
                }
            }).then(function(resultat) {
                if (resultat.isConfirmed && resultat.value) {
                    htmx.ajax('POST', '/dossiers/' + itemId + '/renommer/', {
                        target: '#arbre',
                        swap: 'innerHTML',
                        values: { nouveau_nom: resultat.value.trim() },
                        headers: { 'X-CSRFToken': extraireTokenCsrf() }
                    });
                }
            });
        }

        // Supprimer un dossier — confirmation SweetAlert puis DELETE
        // / Delete folder — SweetAlert confirmation then DELETE
        if (boutonAction.classList.contains('btn-action-supprimer-dossier')) {
            Swal.fire({
                title: 'Supprimer ce dossier ?',
                text: 'Les pages du dossier ne seront pas supprimees.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Supprimer',
                cancelButtonText: 'Annuler',
                confirmButtonColor: '#ef4444',
            }).then(function(resultat) {
                if (resultat.isConfirmed) {
                    htmx.ajax('DELETE', '/dossiers/' + itemId + '/', {
                        target: '#arbre',
                        swap: 'innerHTML',
                        headers: { 'X-CSRFToken': extraireTokenCsrf() }
                    });
                }
            });
        }

        // Partager un dossier — charge le formulaire HTMX
        // / Share folder — load HTMX form
        if (boutonAction.classList.contains('btn-action-partager')) {
            htmx.ajax('GET', '/dossiers/' + itemId + '/partager/', {
                target: '#partage-contenu-' + itemId,
                swap: 'innerHTML',
            });
        }

        // Deplacer une page — SweetAlert avec select dossier
        // / Move page — SweetAlert with folder select
        if (boutonAction.classList.contains('btn-action-deplacer')) {
            // Simule un clic sur le bouton .btn-classer existant si present
            // Sinon, fait l'appel directement
            // / Simulate click on existing .btn-classer button if present
            // Otherwise, make the call directly
            fetch('/dossiers/').then(function(resp) { return resp.json(); }).then(function(dossiers) {
                if (Object.keys(dossiers).length === 0) {
                    Swal.fire({ title: 'Aucun dossier', text: 'Creez d\'abord un dossier.', icon: 'info' });
                    return;
                }
                var options = { '': '— Aucun dossier —' };
                for (var cle in dossiers) { options[cle] = dossiers[cle]; }

                Swal.fire({
                    title: 'Deplacer vers…',
                    input: 'select',
                    inputOptions: options,
                    showCancelButton: true,
                    cancelButtonText: 'Annuler',
                    confirmButtonText: 'Deplacer',
                }).then(function(resultat) {
                    if (resultat.isDismissed) return;
                    fetch('/pages/' + itemId + '/classer/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': extraireTokenCsrf() },
                        body: JSON.stringify({ dossier_id: resultat.value || null }),
                    }).then(function(reponseClassement) {
                        if (reponseClassement.ok) {
                            reponseClassement.text().then(function(html) {
                                var arbreEl = document.getElementById('arbre');
                                arbreEl.innerHTML = html;
                                htmx.process(arbreEl);
                            });
                        }
                    });
                });
            });
        }

        // Changer la visibilite d'un dossier — flash visuel apres le swap
        // / Change folder visibility — visual flash after the swap
        if (boutonAction.classList.contains('btn-action-visibilite')) {
            var nouvelleVisibilite = boutonAction.getAttribute('data-visibilite');
            var dossierIdFlash = itemId;
            htmx.ajax('POST', '/dossiers/' + itemId + '/visibilite/', {
                target: '#arbre',
                swap: 'innerHTML',
                values: { visibilite: nouvelleVisibilite },
                headers: { 'X-CSRFToken': extraireTokenCsrf() }
            }).then(function() {
                // Flash vert temporaire sur le dossier modifie
                // / Temporary green flash on the modified folder
                var noeudModifie = document.querySelector('[data-dossier-id="' + dossierIdFlash + '"] .dossier-toggle');
                if (noeudModifie) {
                    noeudModifie.style.transition = 'background-color 0.3s ease';
                    noeudModifie.style.backgroundColor = '#dcfce7';
                    setTimeout(function() {
                        noeudModifie.style.backgroundColor = '';
                    }, 1200);
                }
            });
        }

        // Supprimer une page — confirmation SweetAlert
        // / Delete page — SweetAlert confirmation
        if (boutonAction.classList.contains('btn-action-supprimer-page')) {
            Swal.fire({
                title: 'Supprimer cette page ?',
                text: 'Cette action est irreversible.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Supprimer',
                cancelButtonText: 'Annuler',
                confirmButtonColor: '#ef4444',
            }).then(function(resultat) {
                if (resultat.isConfirmed) {
                    htmx.ajax('POST', '/pages/' + itemId + '/supprimer/', {
                        target: '#arbre',
                        swap: 'innerHTML',
                        headers: { 'X-CSRFToken': extraireTokenCsrf() }
                    });
                }
            });
        }
    });

    // --- Ouverture du menu ---
    // --- Menu opening ---

    // Clic sur le bouton kebab "..." → ouvre le menu
    // Utilise la phase capture pour intercepter AVANT les handlers bulle (hypostasia.js)
    // / Click on kebab "..." button → opens menu
    // Uses capture phase to intercept BEFORE bubble handlers (hypostasia.js)
    document.addEventListener('click', function(evenement) {
        var boutonKebab = evenement.target.closest('.btn-ctx-menu');
        if (!boutonKebab) return;
        evenement.stopImmediatePropagation();
        evenement.preventDefault();

        // Trouve l'element parent qui porte les data-ctx-*
        // / Find parent element carrying data-ctx-* attributes
        var elementCible = boutonKebab.closest('[data-ctx-type]');
        if (!elementCible) return;

        var rect = boutonKebab.getBoundingClientRect();
        ouvrirMenuPourElement(elementCible, rect.left, rect.bottom + 4);
    }, true);

    // Clic droit (contextmenu) sur un dossier ou une page → ouvre le menu
    // / Right-click on folder or page → opens menu
    document.addEventListener('contextmenu', function(evenement) {
        var elementCible = evenement.target.closest('[data-ctx-type]');
        if (!elementCible) return;
        // Verifie qu'on est bien dans l'arbre
        // / Check we're inside the tree
        if (!elementCible.closest('#arbre')) return;

        evenement.preventDefault();
        ouvrirMenuPourElement(elementCible, evenement.clientX, evenement.clientY);
    });

    // Appui long mobile (touchstart + touchend) → ouvre le menu
    // / Long press mobile (touchstart + touchend) → opens menu
    document.addEventListener('touchstart', function(evenement) {
        var elementCible = evenement.target.closest('[data-ctx-type]');
        if (!elementCible || !elementCible.closest('#arbre')) return;

        timerAppuiLong = setTimeout(function() {
            timerAppuiLong = null;
            var touchData = evenement.touches[0];
            ouvrirMenuPourElement(elementCible, touchData.clientX, touchData.clientY);
        }, DELAI_APPUI_LONG);
    }, { passive: true });

    document.addEventListener('touchend', function() {
        if (timerAppuiLong) {
            clearTimeout(timerAppuiLong);
            timerAppuiLong = null;
        }
    });

    document.addEventListener('touchmove', function() {
        if (timerAppuiLong) {
            clearTimeout(timerAppuiLong);
            timerAppuiLong = null;
        }
    }, { passive: true });

    // Ferme le menu au clic exterieur (mousedown au lieu de click pour eviter les conflits)
    // / Close menu on outside click (mousedown instead of click to avoid conflicts)
    document.addEventListener('mousedown', function(evenement) {
        if (!menuContextuel.classList.contains('hidden')) {
            var clicDansMenu = menuContextuel.contains(evenement.target);
            var clicSurKebab = evenement.target.closest('.btn-ctx-menu');
            if (!clicDansMenu && !clicSurKebab) {
                fermerMenu();
            }
        }
    });

    // Ferme le menu sur Escape
    // / Close menu on Escape
    document.addEventListener('keydown', function(evenement) {
        if (evenement.key === 'Escape' && !menuContextuel.classList.contains('hidden')) {
            fermerMenu();
        }
    });

})();
