// ==========================================================================
// alignement.js — Alignement cross-documents par hypostases (PHASE-18)
// / Cross-document alignment by hypostases (PHASE-18)
//
// LOCALISATION : front/static/front/js/alignement.js
//
// Gere le mode selection dans l'arbre, la barre flottante, la modale
// d'alignement et l'export Markdown.
// / Manages selection mode in tree, floating bar, alignment modal,
// / and Markdown export.
//
// Expose : window.alignement = { activerSelection, desactiverSelection,
//                                 ouvrir, fermer, estOuvert, basculerSelection }
// ==========================================================================
(function() {
    'use strict';

    // --- Etat interne ---
    // / --- Internal state ---
    var modaleOuverte = false;
    var modeSelectionActif = false;
    var pagesSelectionnees = new Set();

    // Memorise le dernier dossier aligne et la position de scroll
    // pour restaurer la vue quand on revient avec le raccourci A
    // / Remembers last aligned folder and scroll position
    // / to restore the view when returning with the A shortcut
    var dernierDossierIdAligne = null;
    var dernierScrollTopModale = 0;


    // --- Utilitaires ---
    // / --- Utilities ---

    // Recupere tous les liens de page dans l'arbre
    // / Get all page links in the tree
    function tousLesLiensPages() {
        return document.querySelectorAll('#arbre a[data-page-id]');
    }


    // === Mode selection dans l'arbre ===
    // / === Selection mode in tree ===

    // Active le mode selection : injecte des checkboxes devant chaque page
    // / Activate selection mode: inject checkboxes before each page
    function activerSelection() {
        if (modeSelectionActif) return;
        modeSelectionActif = true;
        pagesSelectionnees.clear();

        // Injecte les checkboxes dans l'arbre
        // / Inject checkboxes into the tree
        injecterCheckboxes();

        // Affiche la barre flottante de selection
        // / Show floating selection bar
        afficherBarreSelection();

        // Change le bouton "Comparer" en "Annuler"
        // / Change "Compare" button to "Cancel"
        var boutonComparer = document.getElementById('btn-comparer-arbre');
        if (boutonComparer) {
            boutonComparer.textContent = 'Annuler';
            boutonComparer.classList.add('text-red-500');
            boutonComparer.classList.remove('text-slate-600');
        }
    }

    // Desactive le mode selection : retire les checkboxes
    // / Deactivate selection mode: remove checkboxes
    function desactiverSelection() {
        if (!modeSelectionActif) return;
        modeSelectionActif = false;
        pagesSelectionnees.clear();

        // Retire les checkboxes de l'arbre
        // / Remove checkboxes from tree
        retirerCheckboxes();

        // Masque la barre flottante
        // / Hide floating bar
        masquerBarreSelection();

        // Restaure le bouton "Comparer"
        // / Restore "Compare" button
        var boutonComparer = document.getElementById('btn-comparer-arbre');
        if (boutonComparer) {
            boutonComparer.textContent = 'Comparer';
            boutonComparer.classList.remove('text-red-500');
            boutonComparer.classList.add('text-slate-600');
        }
    }

    // Bascule le mode selection on/off
    // / Toggle selection mode on/off
    function basculerSelection() {
        if (modeSelectionActif) {
            desactiverSelection();
        } else {
            activerSelection();
        }
    }

    // Injecte une checkbox devant chaque lien de page dans l'arbre
    // / Inject a checkbox before each page link in the tree
    function injecterCheckboxes() {
        var liens = tousLesLiensPages();
        liens.forEach(function(lien) {
            // Evite les doublons / Avoid duplicates
            if (lien.parentElement.querySelector('.arbre-checkbox-selection')) return;

            var checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'arbre-checkbox-selection';
            checkbox.dataset.pageId = lien.dataset.pageId;

            // Empeche la propagation du clic vers le listener delegue de l'arbre
            // / Prevent click propagation to the tree's delegated listener
            checkbox.addEventListener('click', function(evenement) {
                evenement.stopPropagation();
                gererCochage(this);
            });

            // Insere avant le lien / Insert before the link
            lien.parentElement.insertBefore(checkbox, lien);

            // Empeche le clic de navigation sur le lien en mode selection
            // / Prevent navigation click on link in selection mode
            lien.dataset.selectionBloquee = 'true';
        });

        // Delegue : intercepte tous les clics sur les liens page en mode selection
        // / Delegate: intercept all clicks on page links in selection mode
        document.getElementById('arbre').addEventListener('click', gestionClicArbreSelection);
    }

    // Retire toutes les checkboxes injectees
    // / Remove all injected checkboxes
    function retirerCheckboxes() {
        var checkboxes = document.querySelectorAll('.arbre-checkbox-selection');
        checkboxes.forEach(function(cb) { cb.remove(); });

        // Retire le blocage de navigation / Remove navigation block
        var liens = tousLesLiensPages();
        liens.forEach(function(lien) {
            delete lien.dataset.selectionBloquee;
        });

        // Retire le listener delegue / Remove delegated listener
        var arbre = document.getElementById('arbre');
        if (arbre) {
            arbre.removeEventListener('click', gestionClicArbreSelection);
        }
    }

    // Intercepte les clics sur les liens de page en mode selection
    // / Intercept clicks on page links in selection mode
    function gestionClicArbreSelection(evenement) {
        if (!modeSelectionActif) return;

        var lienPage = evenement.target.closest('a[data-page-id]');
        if (!lienPage) return;

        // Si en mode selection, coche/decoche au lieu de naviguer
        // / In selection mode, check/uncheck instead of navigating
        if (lienPage.dataset.selectionBloquee === 'true') {
            evenement.preventDefault();
            evenement.stopPropagation();

            var checkbox = lienPage.parentElement.querySelector('.arbre-checkbox-selection');
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
                gererCochage(checkbox);
            }
        }
    }

    // Gere le cochage/decochage d'une page
    // / Handle page check/uncheck
    function gererCochage(checkbox) {
        var pageId = checkbox.dataset.pageId;

        if (checkbox.checked) {
            if (pagesSelectionnees.size >= 6) {
                checkbox.checked = false;
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        toast: true, position: 'top-end', icon: 'warning',
                        title: 'Maximum 6 pages',
                        showConfirmButton: false, timer: 2000, timerProgressBar: true,
                    });
                }
                return;
            }
            pagesSelectionnees.add(pageId);
        } else {
            pagesSelectionnees.delete(pageId);
        }

        mettreAJourBarreSelection();
    }


    // === Barre flottante de selection ===
    // / === Floating selection bar ===

    // Affiche la barre flottante en bas de l'arbre
    // / Show floating bar at bottom of tree
    function afficherBarreSelection() {
        var barreExistante = document.getElementById('barre-selection-alignement');
        if (barreExistante) {
            barreExistante.style.display = 'flex';
            mettreAJourBarreSelection();
            return;
        }

        var html = '<div id="barre-selection-alignement" class="barre-selection-alignement">'
            + '<span id="compteur-selection-alignement" class="text-sm text-slate-600">0 page sélectionnée</span>'
            + '<button id="btn-lancer-alignement" class="text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-1.5 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed" disabled>Aligner</button>'
            + '</div>';

        // Insere dans l'overlay arbre, avant le footer existant
        // / Insert in tree overlay, before existing footer
        var overlayArbre = document.getElementById('arbre-overlay');
        if (overlayArbre) {
            overlayArbre.insertAdjacentHTML('beforeend', html);

            // Listener du bouton "Aligner"
            // / "Align" button listener
            document.getElementById('btn-lancer-alignement').addEventListener('click', function() {
                lancerAlignement();
            });
        }
    }

    // Masque la barre flottante
    // / Hide floating bar
    function masquerBarreSelection() {
        var barre = document.getElementById('barre-selection-alignement');
        if (barre) {
            barre.style.display = 'none';
        }
    }

    // Met a jour le compteur et l'etat du bouton
    // / Update counter and button state
    function mettreAJourBarreSelection() {
        var compteur = document.getElementById('compteur-selection-alignement');
        var boutonAligner = document.getElementById('btn-lancer-alignement');
        var nombre = pagesSelectionnees.size;

        if (compteur) {
            compteur.textContent = nombre + ' page' + (nombre > 1 ? 's' : '') + ' sélectionnée' + (nombre > 1 ? 's' : '');
        }
        if (boutonAligner) {
            boutonAligner.disabled = nombre < 2;
        }
    }


    // === Modale d'alignement ===
    // / === Alignment modal ===

    // Lance l'alignement : ferme l'arbre, ouvre la modale, charge le contenu
    // / Launch alignment: close tree, open modal, load content
    function lancerAlignement() {
        if (pagesSelectionnees.size < 2) return;

        var identifiantsPages = Array.from(pagesSelectionnees).join(',');

        // Ferme l'arbre / Close tree
        if (window.arbreOverlay && window.arbreOverlay.estOuvert()) {
            window.arbreOverlay.fermer();
        }

        // Desactive le mode selection / Deactivate selection mode
        desactiverSelection();

        // Ouvre la modale / Open modal
        ouvrirModale(identifiantsPages);
    }

    // Ouvre la modale avec un loading skeleton, puis charge le contenu via HTMX
    // / Open modal with loading skeleton, then load content via HTMX
    function ouvrirModale(identifiantsPages) {
        if (modaleOuverte) return;
        modaleOuverte = true;

        // Cree le conteneur si absent / Create container if missing
        var conteneur = document.getElementById('alignement-modale-container');
        if (!conteneur) {
            conteneur = document.createElement('div');
            conteneur.id = 'alignement-modale-container';
            document.body.appendChild(conteneur);
        }

        var html = '<div class="alignement-modale-backdrop" id="alignement-modale-backdrop">'
            + '<div class="alignement-modale" id="alignement-modale">'
            + '<div class="alignement-header">'
            + '<div class="flex items-center gap-3"><h2 class="text-base font-semibold text-slate-800">Chargement...</h2></div>'
            + '<button id="btn-fermer-alignement-temp" class="flex items-center justify-center w-8 h-8 text-slate-400 hover:text-slate-700 rounded hover:bg-slate-100 transition-colors" title="Fermer">&times;</button>'
            + '</div>'
            + '<div class="alignement-body">'
            + '<div class="py-12 space-y-4 px-8">'
            + '<div class="skeleton h-6 w-48 mx-auto"></div>'
            + '<div class="skeleton h-4 w-full"></div>'
            + '<div class="skeleton h-4 w-5/6"></div>'
            + '<div class="skeleton h-4 w-4/6"></div>'
            + '<div class="skeleton h-4 w-full"></div>'
            + '<div class="skeleton h-4 w-3/4"></div>'
            + '</div>'
            + '</div>'
            + '</div>'
            + '</div>';

        conteneur.innerHTML = html;

        // Listener fermeture sur le backdrop / Close listener on backdrop
        document.getElementById('alignement-modale-backdrop').addEventListener('click', function(evenement) {
            if (evenement.target === this) {
                fermerModale();
            }
        });

        // Listener fermeture sur le bouton temporaire / Close listener on temp button
        document.getElementById('btn-fermer-alignement-temp').addEventListener('click', fermerModale);

        // Charge le contenu via HTMX / Load content via HTMX
        var urlAlignement = '/alignement/tableau/?page_ids=' + identifiantsPages;
        var modaleElement = document.getElementById('alignement-modale');

        // Stocke les page_ids sur la modale pour l'export
        // / Store page_ids on modal for export
        modaleElement.dataset.pageIds = identifiantsPages;

        htmx.ajax('GET', urlAlignement, {
            target: modaleElement,
            swap: 'innerHTML',
        }).then(function() {
            // Ajoute les listeners sur les boutons du contenu charge
            // / Add listeners on buttons of loaded content
            installerListenersModale();
        });
    }

    // Ferme la modale d'alignement en memorisant la position de scroll
    // / Close the alignment modal, remembering scroll position
    function fermerModale() {
        if (!modaleOuverte) return;

        // Sauvegarder la position de scroll avant fermeture
        // / Save scroll position before closing
        var corpsModale = document.querySelector('.alignement-body');
        if (corpsModale) {
            dernierScrollTopModale = corpsModale.scrollTop;
        }

        modaleOuverte = false;

        var conteneur = document.getElementById('alignement-modale-container');
        if (conteneur) {
            conteneur.innerHTML = '';
        }
    }

    // Ouvre la modale d'alignement pour un dossier entier.
    // Appele au clic sur le bouton "Aligner" dans l'arbre (.btn-aligner-dossier).
    // Flux : clic bouton → ferme l'arbre → cree modale skeleton → GET /alignement/tableau/?dossier_id=X
    // / Open alignment modal for an entire folder (called from tree button click)
    function ouvrirDossier(dossierId) {
        // Ferme l'arbre si ouvert / Close tree if open
        if (window.arbreOverlay && window.arbreOverlay.estOuvert()) {
            window.arbreOverlay.fermer();
        }

        // Empeche l'ouverture si deja ouverte / Prevent opening if already open
        if (modaleOuverte) return;
        modaleOuverte = true;

        // Memorise le dossier pour le raccourci A
        // / Remember folder for the A shortcut
        var estMemeDossier = (dernierDossierIdAligne === dossierId);
        dernierDossierIdAligne = dossierId;

        var conteneur = document.getElementById('alignement-modale-container');
        if (!conteneur) {
            conteneur = document.createElement('div');
            conteneur.id = 'alignement-modale-container';
            document.body.appendChild(conteneur);
        }

        var html = '<div class="alignement-modale-backdrop" id="alignement-modale-backdrop">'
            + '<div class="alignement-modale" id="alignement-modale">'
            + '<div class="alignement-header">'
            + '<div class="flex items-center gap-3"><h2 class="text-base font-semibold text-slate-800">Chargement...</h2></div>'
            + '<button id="btn-fermer-alignement-temp" class="flex items-center justify-center w-8 h-8 text-slate-400 hover:text-slate-700 rounded hover:bg-slate-100 transition-colors" title="Fermer">&times;</button>'
            + '</div>'
            + '<div class="alignement-body">'
            + '<div class="py-12 space-y-4 px-8">'
            + '<div class="skeleton h-6 w-48 mx-auto"></div>'
            + '<div class="skeleton h-4 w-full"></div>'
            + '<div class="skeleton h-4 w-5/6"></div>'
            + '<div class="skeleton h-4 w-4/6"></div>'
            + '</div>'
            + '</div>'
            + '</div>'
            + '</div>';

        conteneur.innerHTML = html;

        document.getElementById('alignement-modale-backdrop').addEventListener('click', function(evenement) {
            if (evenement.target === this) fermerModale();
        });
        document.getElementById('btn-fermer-alignement-temp').addEventListener('click', fermerModale);

        var modaleElement = document.getElementById('alignement-modale');
        modaleElement.dataset.dossierId = dossierId;

        // Charge le contenu via dossier_id / Load content via dossier_id
        var urlAlignement = '/alignement/tableau/?dossier_id=' + dossierId;

        htmx.ajax('GET', urlAlignement, {
            target: modaleElement,
            swap: 'innerHTML',
        }).then(function() {
            installerListenersModale();

            // Restaure la position de scroll si c'est le meme dossier qu'avant
            // / Restore scroll position if it's the same folder as before
            if (estMemeDossier && dernierScrollTopModale > 0) {
                var corpsModale = document.querySelector('.alignement-body');
                if (corpsModale) {
                    corpsModale.scrollTop = dernierScrollTopModale;
                }
            }
        });
    }

    // Installe les listeners sur les elements du contenu charge
    // / Install listeners on loaded content elements
    function installerListenersModale() {
        // Bouton fermer / Close button
        var boutonFermer = document.getElementById('btn-fermer-alignement');
        if (boutonFermer) {
            boutonFermer.addEventListener('click', fermerModale);
        }

        // Bouton export Markdown / Export Markdown button
        var boutonExport = document.getElementById('btn-export-alignement');
        if (boutonExport) {
            boutonExport.addEventListener('click', function() {
                var modale = document.getElementById('alignement-modale');
                if (!modale) return;
                // Utilise dossier_id ou page_ids selon le mode d'ouverture
                // / Use dossier_id or page_ids depending on opening mode
                var dossierId = modale.dataset.dossierId;
                var pageIds = modale.dataset.pageIds;
                if (dossierId) {
                    window.location = '/alignement/export_markdown/?dossier_id=' + dossierId;
                } else if (pageIds) {
                    window.location = '/alignement/export_markdown/?page_ids=' + pageIds;
                }
            });
        }

        // Bouton bascule Source / Resume / Toggle Source / Summary button
        var boutonBascule = document.getElementById('btn-bascule-source');
        if (boutonBascule) {
            boutonBascule.addEventListener('click', function() {
                var modale = document.getElementById('alignement-modale');
                if (!modale) return;
                modale.classList.toggle('alignement-mode-source');
                var label = document.getElementById('btn-bascule-source-label');
                if (label) {
                    var estModeSource = modale.classList.contains('alignement-mode-source');
                    label.textContent = estModeSource ? 'Résumé' : 'Source';
                }
            });
        }

        // Collapse/deplier les sections de famille dans le tableau
        // / Collapse/expand family sections in the table
        var headersFamille = document.querySelectorAll('.alignement-famille-header');
        headersFamille.forEach(function(headerFamille) {
            headerFamille.addEventListener('click', function() {
                this.classList.toggle('collapsed');
                // Bascule la fleche / Toggle arrow
                var fleche = this.querySelector('.tree-arrow');
                if (fleche) {
                    fleche.classList.toggle('open');
                }
                // Masque/affiche les lignes suivantes jusqu'au prochain header
                // / Hide/show following rows until next header
                var ligneSuivante = this.nextElementSibling;
                while (ligneSuivante && !ligneSuivante.classList.contains('alignement-famille-header')) {
                    ligneSuivante.style.display = ligneSuivante.style.display === 'none' ? '' : 'none';
                    ligneSuivante = ligneSuivante.nextElementSibling;
                }
            });
        });

        // Clic sur cellule remplie → navigation vers la page + scroll vers l'extraction
        // / Click on filled cell → navigate to page + scroll to extraction
        var cellules = document.querySelectorAll('.alignement-cell[data-page-id]');
        cellules.forEach(function(cellule) {
            cellule.addEventListener('click', function() {
                var pageId = this.dataset.pageId;
                if (!pageId) return;
                var extractionId = this.dataset.extractionId;

                // Ferme la modale / Close modal
                fermerModale();

                // Navigue vers la page via HTMX avec push-url
                // / Navigate to page via HTMX with push-url
                var urlLecture = '/lire/' + pageId + '/';
                htmx.ajax('GET', urlLecture, {
                    target: '#zone-lecture',
                    swap: 'innerHTML',
                }).then(function() {
                    history.pushState({}, '', urlLecture);

                    // Scroll vers l'extraction apres chargement / Scroll to extraction after load
                    if (extractionId) {
                        setTimeout(function() {
                            var spanExtraction = document.querySelector(
                                '.hl-extraction[data-extraction-id="' + extractionId + '"]'
                            );
                            if (spanExtraction) {
                                spanExtraction.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                spanExtraction.classList.add('ancre-active');
                            }
                        }, 300);
                    }
                });
            });
        });
    }


    // === Reinitialisation apres rechargement de l'arbre (HTMX swap) ===
    // / === Reinit after tree reload (HTMX swap) ===
    document.body.addEventListener('htmx:afterSwap', function(evenement) {
        var cible = evenement.detail.target;
        if (cible && cible.id === 'arbre' && modeSelectionActif) {
            // Reinjecte les checkboxes apres un reload de l'arbre
            // / Re-inject checkboxes after tree reload
            injecterCheckboxes();
        }
    });


    // === Initialisation au chargement ===
    // / === Initialization on load ===
    document.addEventListener('DOMContentLoaded', function() {
        // Listener du bouton "Comparer" dans le footer de l'arbre
        // Ouvre directement l'alignement du dossier courant (meme comportement que raccourci A)
        // / Listener on "Compare" button in tree footer
        // / Opens alignment for current folder directly (same as A shortcut)
        var boutonComparer = document.getElementById('btn-comparer-arbre');
        if (boutonComparer) {
            boutonComparer.addEventListener('click', function() {
                basculerAlignement();
            });
        }

        // Listener delegue sur les boutons "Aligner dossier" dans l'arbre
        // / Delegated listener on "Align folder" buttons in the tree
        document.body.addEventListener('click', function(evenement) {
            var boutonAligner = evenement.target.closest('.btn-aligner-dossier');
            if (!boutonAligner) return;

            evenement.stopPropagation();
            var dossierId = boutonAligner.dataset.dossierId;
            if (dossierId) {
                ouvrirDossier(dossierId);
            }
        });
    });


    // Ouvre l'alignement du dossier de la page actuellement affichee
    // Detecte le dossier-id depuis le data-attribute de la zone de lecture
    // / Open alignment for the folder of the currently displayed page
    // / Detects dossier-id from the data-attribute of the reading zone
    function ouvrirDossierCourant() {
        var zoneLecture = document.querySelector('[data-dossier-id]');
        if (!zoneLecture) return false;
        var dossierId = zoneLecture.dataset.dossierId;
        if (!dossierId) return false;
        ouvrirDossier(dossierId);
        return true;
    }

    // Toggle l'alignement : si ouvert → fermer, sinon → ouvrir le dossier courant
    // / Toggle alignment: if open → close, else → open current folder
    function basculerAlignement() {
        if (modaleOuverte) {
            fermerModale();
        } else {
            var ouvert = ouvrirDossierCourant();
            if (!ouvert && typeof Swal !== 'undefined') {
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'info',
                    title: 'Aucun dossier associ\u00e9',
                    showConfirmButton: false, timer: 2000,
                });
            }
        }
    }

    // Expose l'API publique
    // / Expose public API
    window.alignement = {
        activerSelection: activerSelection,
        desactiverSelection: desactiverSelection,
        basculerSelection: basculerSelection,
        ouvrir: ouvrirModale,
        ouvrirDossier: ouvrirDossier,
        ouvrirDossierCourant: ouvrirDossierCourant,
        basculerAlignement: basculerAlignement,
        fermer: fermerModale,
        estOuvert: function() { return modaleOuverte; },
    };

})();
