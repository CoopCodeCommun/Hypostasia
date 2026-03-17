// ==========================================================================
// alignement.js — Alignement cross-documents par hypostases (PHASE-18)
// / Cross-document alignment by hypostases (PHASE-18)
//
// LOCALISATION : front/static/front/js/alignement.js
//
// Gere la modale d'alignement et la navigation vers les extractions.
// Le raccourci A ouvre l'alignement du dossier de la page courante.
// / Manages the alignment modal and navigation to extractions.
// / The A shortcut opens the alignment for the current page's folder.
//
// Expose : window.alignement = { ouvrirDossier, ouvrirDossierCourant,
//                                 basculerAlignement, fermer, estOuvert }
// ==========================================================================
(function() {
    'use strict';

    // --- Etat interne ---
    // / --- Internal state ---
    var modaleOuverte = false;

    // Memorise le dernier dossier aligne et la position de scroll
    // pour restaurer la vue quand on revient avec le raccourci A
    // / Remembers last aligned folder and scroll position
    // / to restore the view when returning with the A shortcut
    var dernierDossierIdAligne = null;
    var dernierScrollTopModale = 0;


    // === Modale d'alignement ===
    // / === Alignment modal ===

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
    // Flux : ferme l'arbre → cree modale skeleton → GET /alignement/tableau/?dossier_id=X
    // / Open alignment modal for an entire folder
    // / Flow: close tree → create skeleton modal → GET /alignement/tableau/?dossier_id=X
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
                var dossierId = modale.dataset.dossierId;
                if (dossierId) {
                    window.location = '/alignement/export_markdown/?dossier_id=' + dossierId;
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


    // === Initialisation au chargement ===
    // / === Initialization on load ===
    document.addEventListener('DOMContentLoaded', function() {
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
        ouvrirDossier: ouvrirDossier,
        ouvrirDossierCourant: ouvrirDossierCourant,
        basculerAlignement: basculerAlignement,
        fermer: fermerModale,
        estOuvert: function() { return modaleOuverte; },
    };

})();
