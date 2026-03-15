/**
 * Drawer vue liste des extractions — PHASE-10
 * Gere l'ouverture et la fermeture du drawer droit avec la liste compacte
 * de toutes les extractions d'une page. Supporte tri, masquer/restaurer,
 * et scroll bidirectionnel avec le texte.
 * / Drawer extraction list view — PHASE-10
 * / Manages the right drawer with compact list of all extractions for a page.
 * / Supports sort, hide/restore, and bidirectional scrolling with text.
 *
 * LOCALISATION : front/static/front/js/drawer_vue_liste.js
 *
 * COMMUNICATION :
 * Ecoute : clic sur #btn-toolbar-drawer, #btn-fermer-drawer, #drawer-backdrop
 * Ecoute : keydown E (toggle drawer), Escape (ferme drawer si ouvert)
 * Ecoute : clic delegue sur .drawer-carte-compacte (scroll texte + carte inline)
 * Note : .btn-masquer-drawer et .btn-restaurer-drawer sont geres par HTMX (hx-post dans le template)
 * Ecoute : change sur #drawer-select-tri (recharge contenu)
 * Ecoute : clic delegue sur #btn-toggle-masquees (affiche/cache section masquees)
 * Ecoute : htmx event drawerContenuChange (recharge contenu apres masquer/restaurer)
 * Expose : window.drawerVueListe = { ouvrir, fermer, basculer, estOuvert }
 */
(function() {
    'use strict';

    var boutonToolbar = document.getElementById('btn-toolbar-drawer');
    var boutonFermer = document.getElementById('btn-fermer-drawer');
    var backdrop = document.getElementById('drawer-backdrop');
    var overlay = document.getElementById('drawer-overlay');
    var contenu = document.getElementById('drawer-contenu');

    var drawerEstOuvert = false;
    var contenuCharge = false;

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

    // Recupere le page_id depuis la zone de lecture
    // / Get page_id from reading zone
    function getPageId() {
        var elementPage = document.querySelector('#zone-lecture [data-page-id]');
        if (!elementPage) return null;
        return elementPage.dataset.pageId;
    }

    // Recharge la zone de lecture pour rafraichir les pastilles apres masquer/restaurer
    // Utilise fetch + innerHTML car htmx.ajax ne fait pas le swap de maniere fiable
    // La reponse HTMX de /lire/{id}/ contient 2 morceaux :
    //   1. Le partial lecture_principale (contenu principal)
    //   2. Un div OOB pour #panneau-extractions (a ignorer ici)
    // On extrait seulement le premier morceau grace a un DOMParser.
    // Apres le swap, on reconstruit les pastilles marginales (marginalia.js).
    // / Reload reading zone to refresh pastilles after hide/restore
    // / Uses fetch + innerHTML because htmx.ajax doesn't reliably swap
    function rechargerZoneLecture(pageId) {
        if (!pageId) return;
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
    }

    // Charge le contenu du drawer via HTMX
    // / Load drawer content via HTMX
    function chargerContenu(triOptional) {
        var pageId = getPageId();
        if (!pageId) {
            contenu.innerHTML = '<p class="text-xs text-slate-400 text-center py-8">Aucune page s\u00e9lectionn\u00e9e.</p>';
            return;
        }

        var url = '/extractions/drawer_contenu/?page_id=' + pageId;
        if (triOptional) {
            url += '&tri=' + triOptional;
        }

        htmx.ajax('GET', url, {
            target: '#drawer-contenu',
            swap: 'innerHTML',
        });
        contenuCharge = true;
    }

    // Ouvre le drawer avec animation
    // / Open drawer with animation
    function ouvrirDrawer() {
        if (drawerEstOuvert) return;

        var pageId = getPageId();
        if (!pageId) {
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'warning',
                title: 'Aucune page s\u00e9lectionn\u00e9e',
                showConfirmButton: false,
                timer: 2000,
                timerProgressBar: true,
            });
            return;
        }

        drawerEstOuvert = true;

        // Affiche le backdrop et force un reflow avant de retirer opacity-0
        // / Show backdrop and force reflow before removing opacity-0
        backdrop.classList.remove('hidden');
        void backdrop.offsetWidth;
        backdrop.classList.remove('opacity-0');

        // Glisse le drawer depuis la droite et reactive les clics
        // / Slide drawer in from the right and re-enable pointer events
        overlay.classList.remove('translate-x-full');
        overlay.classList.remove('pointer-events-none');

        // Charger le contenu au premier open (ou si la page a change)
        // / Load content on first open (or if page changed)
        chargerContenu();

        // Focus sur le bouton fermer pour accessibilite
        // / Focus close button for accessibility
        boutonFermer.focus();
    }

    // Ferme le drawer avec animation
    // / Close drawer with animation
    function fermerDrawer() {
        if (!drawerEstOuvert) return;
        drawerEstOuvert = false;

        // Anime la fermeture du backdrop
        // / Animate backdrop closing
        backdrop.classList.add('opacity-0');

        // Glisse le drawer vers la droite et desactive les clics
        // / Slide drawer out to the right and disable pointer events
        overlay.classList.add('translate-x-full');
        overlay.classList.add('pointer-events-none');

        // Apres la transition, cache completement le backdrop
        // / After transition, fully hide the backdrop
        setTimeout(function() {
            backdrop.classList.add('hidden');
        }, 250);

        // Remet le focus sur le bouton toolbar
        // / Return focus to toolbar button
        boutonToolbar.focus();
    }

    // Bascule ouvert/ferme
    // / Toggle open/close
    function basculerDrawer() {
        if (drawerEstOuvert) {
            fermerDrawer();
        } else {
            ouvrirDrawer();
        }
    }

    // --- Evenements ---
    // --- Events ---

    // Clic bouton toolbar → bascule
    // / Toolbar button click → toggle
    boutonToolbar.addEventListener('click', basculerDrawer);

    // Clic fermer → ferme
    // / Close click → close
    boutonFermer.addEventListener('click', fermerDrawer);

    // Clic backdrop → ferme
    // / Backdrop click → close
    backdrop.addEventListener('click', fermerDrawer);

    // NOTE : Les raccourcis clavier (E, Escape) sont geres par keyboard.js (PHASE-17)
    // / NOTE: Keyboard shortcuts (E, Escape) are handled by keyboard.js (PHASE-17)

    // Clic delegue sur une carte compacte → scroll texte + carte inline
    // / Delegated click on compact card → scroll text + inline card
    document.getElementById('drawer-contenu').addEventListener('click', function(evenement) {
        // Ignorer les clics sur les boutons masquer/restaurer/toggle
        // / Ignore clicks on hide/restore/toggle buttons
        if (evenement.target.closest('.btn-masquer-drawer') ||
            evenement.target.closest('.btn-restaurer-drawer') ||
            evenement.target.closest('#btn-toggle-masquees')) {
            return;
        }

        var carte = evenement.target.closest('.drawer-carte-compacte');
        if (!carte) return;

        var extractionId = carte.dataset.extractionId;
        if (!extractionId) return;

        // Retirer le surlignage precedent dans le drawer
        // / Remove previous highlight in drawer
        document.querySelectorAll('.drawer-carte-compacte.drawer-carte-active').forEach(function(el) {
            el.classList.remove('drawer-carte-active');
        });
        carte.classList.add('drawer-carte-active');

        // Chercher le span correspondant dans le texte
        // / Find the corresponding span in the text
        var spanDansTexte = document.querySelector(
            '#readability-content .hl-extraction[data-extraction-id="' + extractionId + '"]'
        );

        if (spanDansTexte) {
            // Scroll vers le span
            // / Scroll to the span
            spanDansTexte.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Activer le surlignage
            // / Activate highlighting
            document.querySelectorAll('.hl-extraction.ancre-active').forEach(function(el) {
                el.classList.remove('ancre-active');
            });
            spanDansTexte.classList.add('ancre-active');

            // Charger la carte inline
            // / Load inline card
            var blocParent = spanDansTexte.closest('p, div, blockquote, li, h1, h2, h3, h4, h5, h6');
            if (blocParent && blocParent.id !== 'readability-content') {
                // Verifier si une carte inline existe deja pour cette extraction
                // / Check if an inline card already exists for this extraction
                var carteExistante = document.querySelector('.carte-inline[data-extraction-id="' + extractionId + '"]');
                if (!carteExistante) {
                    var divTemporaire = document.createElement('div');
                    divTemporaire.style.display = 'none';
                    document.body.appendChild(divTemporaire);

                    htmx.ajax('GET', '/extractions/carte_inline/?entity_id=' + extractionId, {
                        target: divTemporaire,
                        swap: 'innerHTML',
                    }).then(function() {
                        var contenuCarte = divTemporaire.firstElementChild;
                        if (contenuCarte) {
                            blocParent.insertAdjacentElement('afterend', contenuCarte);
                            htmx.process(contenuCarte);
                        }
                        divTemporaire.remove();
                    });
                }
            }
        }
    });

    // Les boutons masquer et restaurer sont geres par HTMX dans le template HTML.
    // Quand l'utilisateur clique "masquer" :
    //   1. HTMX envoie un POST au serveur (hx-post sur le bouton)
    //   2. Le serveur masque l'extraction et repond avec un signal (HX-Trigger)
    //   3. Le signal "drawerContenuChange" recharge la liste du panneau lateral
    //   4. Le signal "lectureReload" recharge le texte avec le surlignage mis a jour
    // / Hide and restore buttons are handled by HTMX in the HTML template.
    // When the user clicks "hide":
    //   1. HTMX sends a POST to the server (hx-post on the button)
    //   2. The server hides the extraction and responds with a signal (HX-Trigger)
    //   3. The "drawerContenuChange" signal reloads the side panel list
    //   4. The "lectureReload" signal reloads the text with updated highlighting

    // Change sur le select de tri → recharge le contenu
    // / Change on sort select → reload content
    document.getElementById('drawer-contenu').addEventListener('change', function(evenement) {
        if (evenement.target.id !== 'drawer-select-tri') return;

        var triChoisi = evenement.target.value;
        chargerContenu(triChoisi);
    });

    // Toggle section masquees
    // / Toggle hidden section
    document.getElementById('drawer-contenu').addEventListener('click', function(evenement) {
        var boutonToggle = evenement.target.closest('#btn-toggle-masquees');
        if (!boutonToggle) return;

        var sectionMasquees = document.getElementById('drawer-section-masquees');
        if (!sectionMasquees) return;

        if (sectionMasquees.classList.contains('hidden')) {
            sectionMasquees.classList.remove('hidden');
            boutonToggle.textContent = boutonToggle.textContent.replace('Afficher', 'Masquer');
        } else {
            sectionMasquees.classList.add('hidden');
            boutonToggle.textContent = boutonToggle.textContent.replace('Masquer', 'Afficher');
        }
    });

    // Recharger le contenu du drawer via HX-Trigger drawerContenuChange
    // (emis par changer_statut, masquer, restaurer cote serveur)
    // / Reload drawer content via HX-Trigger drawerContenuChange
    // / (emitted by changer_statut, masquer, restaurer server-side)
    document.body.addEventListener('drawerContenuChange', function() {
        if (drawerEstOuvert) {
            var selectTri = document.getElementById('drawer-select-tri');
            var triActuel = selectTri ? selectTri.value : 'position';
            chargerContenu(triActuel);
        } else {
            // Marquer comme non charge pour forcer le rechargement au prochain open
            // / Mark as not loaded to force reload on next open
            contenuCharge = false;
        }
    });

    // Recharger le contenu du drawer apres un swap HTMX sur la zone de lecture
    // (ex: quand on navigue vers une autre page ou relance une analyse)
    // / Reload drawer content after HTMX swap on reading zone
    document.body.addEventListener('htmx:afterSwap', function(evenement) {
        var cible = evenement.detail.target;
        if (cible && cible.id === 'zone-lecture') {
            // Marquer comme non charge pour forcer le rechargement au prochain open
            // / Mark as not loaded to force reload on next open
            contenuCharge = false;
            if (drawerEstOuvert) {
                chargerContenu();
            }
        }
    });

    // Scroll bidirectionnel : quand une pastille est cliquee dans le texte,
    // surligner la carte correspondante dans le drawer
    // / Bidirectional scroll: when a dot is clicked in text,
    // highlight the corresponding card in the drawer
    document.addEventListener('click', function(evenement) {
        var pastille = evenement.target.closest('.pastille-extraction');
        if (!pastille || !drawerEstOuvert) return;

        var extractionId = pastille.dataset.extractionId;
        if (!extractionId) return;

        // Retirer le surlignage precedent dans le drawer
        // / Remove previous highlight in drawer
        document.querySelectorAll('.drawer-carte-compacte.drawer-carte-active').forEach(function(el) {
            el.classList.remove('drawer-carte-active');
        });

        // Surligner et scroller vers la carte dans le drawer
        // / Highlight and scroll to the card in the drawer
        var carteDansDrawer = contenu.querySelector(
            '.drawer-carte-compacte[data-extraction-id="' + extractionId + '"]'
        );
        if (carteDansDrawer) {
            carteDansDrawer.classList.add('drawer-carte-active');
            carteDansDrawer.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });

    // Bidirectionnel carte inline → drawer : quand une carte inline est depliee,
    // surligner la carte correspondante dans le drawer
    // / Bidirectional inline card → drawer: when an inline card is expanded,
    // / highlight the corresponding card in the drawer
    document.addEventListener('click', function(evenement) {
        var boutonVoirExtraction = evenement.target.closest('.pastille-extraction, [data-extraction-id]');
        if (!boutonVoirExtraction || !drawerEstOuvert) return;

        // Chercher l'extraction-id sur l'element clique ou son parent
        // / Find extraction-id on clicked element or its parent
        var extractionId = boutonVoirExtraction.dataset.extractionId;
        if (!extractionId) return;

        // Ne pas traiter les cartes du drawer (deja gere plus haut)
        // / Don't process drawer cards (already handled above)
        if (boutonVoirExtraction.closest('#drawer-contenu')) return;

        // Retirer le surlignage precedent dans le drawer
        // / Remove previous highlight in drawer
        document.querySelectorAll('.drawer-carte-compacte.drawer-carte-active').forEach(function(el) {
            el.classList.remove('drawer-carte-active');
        });

        // Surligner et scroller vers la carte dans le drawer
        // / Highlight and scroll to the card in the drawer
        var carteDansDrawer = contenu.querySelector(
            '.drawer-carte-compacte[data-extraction-id="' + extractionId + '"]'
        );
        if (carteDansDrawer) {
            carteDansDrawer.classList.add('drawer-carte-active');
            carteDansDrawer.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });

    // Expose l'API publique
    // / Expose public API
    window.drawerVueListe = {
        ouvrir: ouvrirDrawer,
        fermer: fermerDrawer,
        basculer: basculerDrawer,
        estOuvert: function() { return drawerEstOuvert; },
    };

})();
