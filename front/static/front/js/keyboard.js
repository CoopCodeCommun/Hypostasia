// ==========================================================================
// keyboard.js — Dispatcher centralise des raccourcis clavier (PHASE-17)
// / Centralized keyboard shortcut dispatcher (PHASE-17)
//
// LOCALISATION : front/static/front/js/keyboard.js
//
// Ce fichier est le SEUL listener keydown de l'application.
// Il appelle les APIs publiques des autres modules :
//   - window.arbreOverlay    (arbre_overlay.js)
//   - window.drawerVueListe  (drawer_vue_liste.js)
//   - window.dashboardConsensus (dashboard_consensus.js)
//   - window.marginalia      (marginalia.js)
//
// RACCOURCIS :
//   T       → Toggle arbre de navigation
//   E       → Toggle drawer vue liste
//   L       → Toggle mode focus lecture
//   J       → Extraction suivante
//   K       → Extraction precedente
//   C       → Commenter extraction selectionnee
//   S       → Marquer consensuelle
//   X       → Masquer extraction selectionnee
//   H       → Toggle heat map du debat
//   A       → Toggle mode selection alignement / ouvrir modale
//   /       → Recherche (placeholder)
//   ?       → Modale aide raccourcis
//   Escape  → Cascade fermeture (modale alignement > modale aide > focus > dashboard > drawer > arbre > carte > selection)
//
// Expose : window.raccourcisClavier = { ouvrirAide, fermerAide }
// ==========================================================================
(function() {
    'use strict';

    // --- Etat interne ---
    // / --- Internal state ---
    var modaleAideOuverte = false;
    var indexExtractionSelectionnee = -1;
    var listeExtractionsVisibles = [];


    // --- Utilitaires ---
    // / --- Utilities ---

    // Verifie si le focus est dans un champ de saisie (input, textarea, select, contentEditable)
    // / Check if focus is on an input field (input, textarea, select, contentEditable)
    function estDansChampSaisie() {
        var elementActif = document.activeElement;
        if (!elementActif) return false;
        return (
            elementActif.tagName === 'INPUT' ||
            elementActif.tagName === 'TEXTAREA' ||
            elementActif.tagName === 'SELECT' ||
            elementActif.isContentEditable
        );
    }

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


    // === Navigation J/K entre extractions ===
    // / === J/K navigation between extractions ===

    // Reconstruit la liste des extractions visibles dans le texte
    // Deduplique par extraction-id (un meme id peut avoir plusieurs spans)
    // / Rebuild list of visible extractions in text
    // / Deduplicate by extraction-id (same id may have multiple spans)
    function reconstruireListeExtractions() {
        var tousLesSpans = document.querySelectorAll('#readability-content .hl-extraction[data-extraction-id]');
        var idsVus = {};
        listeExtractionsVisibles = [];

        tousLesSpans.forEach(function(span) {
            var extractionId = span.dataset.extractionId;
            if (!extractionId || idsVus[extractionId]) return;
            idsVus[extractionId] = true;
            listeExtractionsVisibles.push({
                extractionId: extractionId,
                premierSpan: span,
            });
        });
    }

    // Selectionne une extraction par index : surligne, scroll, charge carte inline
    // / Select extraction by index: highlight, scroll, load inline card
    function selectionnerExtraction(index) {
        if (index < 0 || index >= listeExtractionsVisibles.length) return;

        // Deselectionner la precedente / Deselect previous
        deselectionnerExtraction();

        indexExtractionSelectionnee = index;
        var extraction = listeExtractionsVisibles[index];
        var span = extraction.premierSpan;

        // Ajouter la classe de selection visuelle / Add visual selection class
        span.classList.add('extraction-selectionnee');

        // Scroll vers le span / Scroll to span
        span.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Activer le surlignage / Activate highlighting
        document.querySelectorAll('.hl-extraction.ancre-active').forEach(function(el) {
            el.classList.remove('ancre-active');
        });
        span.classList.add('ancre-active');

        // Charger la carte inline (meme pattern que marginalia.js)
        // / Load inline card (same pattern as marginalia.js)
        var blocParent = span.closest('p, div, blockquote, li, h1, h2, h3, h4, h5, h6');
        if (blocParent && blocParent.id !== 'readability-content') {
            var carteExistante = document.querySelector('.carte-inline[data-extraction-id="' + extraction.extractionId + '"]');
            if (!carteExistante) {
                var divTemporaire = document.createElement('div');
                divTemporaire.style.display = 'none';
                document.body.appendChild(divTemporaire);

                htmx.ajax('GET', '/extractions/carte_inline/?entity_id=' + extraction.extractionId, {
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

    // Retire la selection visuelle de l'extraction courante
    // / Remove visual selection from current extraction
    function deselectionnerExtraction() {
        document.querySelectorAll('.extraction-selectionnee').forEach(function(el) {
            el.classList.remove('extraction-selectionnee');
        });
        indexExtractionSelectionnee = -1;
    }

    // Passe a l'extraction suivante (J)
    // / Move to next extraction (J)
    function extractionSuivante() {
        if (listeExtractionsVisibles.length === 0) return;
        var nouvelIndex = indexExtractionSelectionnee + 1;
        if (nouvelIndex >= listeExtractionsVisibles.length) {
            nouvelIndex = 0; // Boucle / Loop
        }
        selectionnerExtraction(nouvelIndex);
    }

    // Passe a l'extraction precedente (K)
    // / Move to previous extraction (K)
    function extractionPrecedente() {
        if (listeExtractionsVisibles.length === 0) return;
        var nouvelIndex = indexExtractionSelectionnee - 1;
        if (nouvelIndex < 0) {
            nouvelIndex = listeExtractionsVisibles.length - 1; // Boucle / Loop
        }
        selectionnerExtraction(nouvelIndex);
    }


    // === Modale aide raccourcis (?) ===
    // / === Keyboard shortcuts help modal (?) ===

    // Ouvre la modale d'aide — contenu adapte au contexte (mobile ou desktop)
    // / Open help modal — content adapted to context (mobile or desktop)
    function ouvrirAideRaccourcis() {
        if (modaleAideOuverte) return;
        modaleAideOuverte = true;

        // Detecter si on est en contexte mobile (< 768px)
        // / Detect if we're in mobile context (< 768px)
        var estMobile = window.innerWidth <= 768;

        var contenuAide = '';
        if (estMobile) {
            contenuAide = construireAideMobile();
        } else {
            contenuAide = construireAideDesktop();
        }

        var html = '<div class="modale-raccourcis-backdrop" id="modale-raccourcis">'
            + '<div class="modale-raccourcis">'
            + contenuAide
            + '</div>'
            + '</div>';

        document.body.insertAdjacentHTML('beforeend', html);

        // Clic sur le bouton fermer ou sur le backdrop / Click close button or backdrop
        var modale = document.getElementById('modale-raccourcis');
        modale.addEventListener('click', function(evenement) {
            if (evenement.target === modale || evenement.target.id === 'btn-fermer-modale-raccourcis') {
                fermerAideRaccourcis();
            }
        });
    }

    // Genere une ligne de raccourci HTML (touche + description)
    // / Generate a shortcut HTML line (key + description)
    function ligneRaccourci(touche, description) {
        return '<div class="flex items-center gap-3">'
            + '<span class="raccourci-touche">' + touche + '</span>'
            + '<span>' + description + '</span>'
            + '</div>';
    }

    // Genere une ligne de geste mobile HTML (icone emoji + description)
    // / Generate a mobile gesture HTML line (emoji icon + description)
    function ligneGesteMobile(icone, description) {
        return '<div class="flex items-start gap-3 py-1">'
            + '<span class="text-lg shrink-0 w-6 text-center">' + icone + '</span>'
            + '<span class="text-sm text-slate-700">' + description + '</span>'
            + '</div>';
    }

    // Construit le contenu de l'aide mobile (gestes tactiles)
    // / Build mobile help content (touch gestures)
    function construireAideMobile() {
        return '<div class="flex items-center justify-between mb-4">'
            + '<h2 class="text-base font-semibold text-slate-800">Aide Hypostasia</h2>'
            + '<button id="btn-fermer-modale-raccourcis" class="text-slate-400 hover:text-slate-700 text-2xl leading-none p-1">&times;</button>'
            + '</div>'
            + '<p class="text-xs text-slate-500 mb-3">Comment utiliser Hypostasia sur mobile</p>'
            + '<div class="space-y-1">'
            + ligneGesteMobile('\ud83d\udc46', '<strong>Tapez sur un texte soulign\u00e9</strong> pour voir l\u2019extraction (carte en bas)')
            + ligneGesteMobile('\u2b07\ufe0f', '<strong>Glissez la poign\u00e9e vers le bas</strong> pour fermer la carte')
            + ligneGesteMobile('\ud83d\udcac', '<strong>Tapez Commenter</strong> dans la carte pour r\u00e9agir')
            + ligneGesteMobile('\u2261', '<strong>Hamburger</strong> (en haut \u00e0 gauche) pour ouvrir la biblioth\u00e8que')
            + ligneGesteMobile('\u2728', '<strong>Analyser</strong> pour lancer l\u2019analyse IA')
            + ligneGesteMobile('\u2b50', 'Boutons <strong>Consensuel / Controvers\u00e9</strong> pour voter sur une extraction')
            + ligneGesteMobile('\ud83d\udcc1', '<strong>Extractions</strong> pour voir la liste compl\u00e8te')
            + '</div>'
            + '<p class="text-[10px] text-slate-400 mt-4 border-t border-slate-100 pt-2">Les textes soulign\u00e9s dans l\u2019article sont des extractions IA. Tapez dessus pour les explorer.</p>';
    }

    // Construit le contenu de l'aide desktop (raccourcis clavier)
    // / Build desktop help content (keyboard shortcuts)
    function construireAideDesktop() {
        return '<div class="flex items-center justify-between mb-4">'
            + '<h2 class="text-base font-semibold text-slate-800">Raccourcis clavier</h2>'
            + '<button id="btn-fermer-modale-raccourcis" class="text-slate-400 hover:text-slate-700 text-lg leading-none">&times;</button>'
            + '</div>'
            + '<div class="space-y-2 text-sm text-slate-600">'
            + ligneRaccourci('T', 'Ouvrir/fermer la biblioth\u00e8que')
            + ligneRaccourci('E', 'Ouvrir/fermer le panneau extractions')
            + ligneRaccourci('L', 'Mode focus lecture')
            + ligneRaccourci('J', 'Extraction suivante')
            + ligneRaccourci('K', 'Extraction pr\u00e9c\u00e9dente')
            + ligneRaccourci('C', 'Commenter l\u2019extraction s\u00e9lectionn\u00e9e')
            + ligneRaccourci('S', 'Marquer consensuelle')
            + ligneRaccourci('X', 'Masquer l\u2019extraction')
            + ligneRaccourci('H', 'Heat map du d\u00e9bat')
            + ligneRaccourci('A', 'Comparer / Aligner des pages')
            + ligneRaccourci('?', 'Afficher cette aide')
            + ligneRaccourci('Esc', 'Fermer le panneau actif')
            + '</div>';
    }

    // Ferme la modale d'aide
    // / Close help modal
    function fermerAideRaccourcis() {
        if (!modaleAideOuverte) return;
        modaleAideOuverte = false;

        var modale = document.getElementById('modale-raccourcis');
        if (modale) {
            modale.remove();
        }
    }


    // === Actions sur extraction selectionnee ===
    // / === Actions on selected extraction ===

    // Clique le bouton commenter de la carte inline ouverte (C)
    // / Click the comment button of the open inline card (C)
    function commenterExtractionSelectionnee() {
        if (indexExtractionSelectionnee < 0) return;
        var extraction = listeExtractionsVisibles[indexExtractionSelectionnee];
        if (!extraction) return;

        var carte = document.querySelector('.carte-inline[data-extraction-id="' + extraction.extractionId + '"]');
        if (!carte) return;

        var boutonCommenter = carte.querySelector('.btn-commenter-extraction');
        if (boutonCommenter) {
            boutonCommenter.click();
        }
    }

    // Marque l'extraction selectionnee comme consensuelle (S)
    // Verifie d'abord que l'utilisateur est proprietaire du dossier (PHASE-26c)
    // / Mark selected extraction as consensual (S)
    // / First check that user is the folder owner (PHASE-26c)
    function marquerConsensuelleExtraction() {
        if (indexExtractionSelectionnee < 0) return;
        var extraction = listeExtractionsVisibles[indexExtractionSelectionnee];
        if (!extraction) return;

        // Verifier ownership via data-est-proprietaire sur #zone-lecture
        // Toast feedback si non-owner / Toast feedback if non-owner
        var zoneLecture = document.getElementById('zone-lecture');
        if (zoneLecture && zoneLecture.dataset.estProprietaire !== 'true') {
            Swal.fire({
                toast: true, position: 'top-end', icon: 'info',
                title: 'R\u00e9serv\u00e9 au propri\u00e9taire',
                showConfirmButton: false, timer: 2000,
            });
            return;
        }

        var pageId = getPageId();
        if (!pageId) return;

        fetch('/extractions/changer_statut/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': extraireTokenCsrf(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'entity_id=' + extraction.extractionId + '&page_id=' + pageId + '&nouveau_statut=consensuel',
        }).then(function(reponse) {
            if (reponse.ok) {
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'success',
                    title: 'Marqu\u00e9e consensuelle',
                    showConfirmButton: false, timer: 2000, timerProgressBar: true,
                });
            }
        });
    }

    // Masque l'extraction selectionnee (X)
    // / Hide selected extraction (X)
    function masquerExtractionSelectionnee() {
        if (indexExtractionSelectionnee < 0) return;
        var extraction = listeExtractionsVisibles[indexExtractionSelectionnee];
        if (!extraction) return;

        var pageId = getPageId();
        if (!pageId) return;

        fetch('/extractions/masquer/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': extraireTokenCsrf(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'entity_id=' + extraction.extractionId + '&page_id=' + pageId,
        }).then(function(reponse) {
            if (reponse.ok) {
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'success',
                    title: 'Extraction masqu\u00e9e',
                    showConfirmButton: false, timer: 2000, timerProgressBar: true,
                });
                // Deselectionner et reconstruire / Deselect and rebuild
                deselectionnerExtraction();
                reconstruireListeExtractions();
            }
        });
    }

    // Placeholder recherche (/)
    // / Search placeholder (/)
    function placeholderRecherche() {
        Swal.fire({
            toast: true,
            position: 'top-end',
            icon: 'info',
            title: 'Recherche \u2014 bient\u00f4t disponible',
            showConfirmButton: false,
            timer: 2000,
            timerProgressBar: true,
        });
    }


    // === Cascade Escape ===
    // Ferme le panneau le plus "proche" de l'utilisateur en premier
    // / Close the panel closest to the user first
    function gererEscape() {
        // 0.0 Bottom sheet mobile ouvert → fermer (PHASE-21)
        // / 0.0 Mobile bottom sheet open → close (PHASE-21)
        if (window.bottomSheet && window.bottomSheet.estOuvert()) {
            window.bottomSheet.fermer();
            return true;
        }

        // 0. Modale alignement ouverte → fermer
        // / 0. Alignment modal open → close
        if (window.alignement && window.alignement.estOuvert()) {
            window.alignement.fermer();
            return true;
        }

        // 1. Modale aide ouverte → fermer
        // / 1. Help modal open → close
        if (modaleAideOuverte) {
            fermerAideRaccourcis();
            return true;
        }

        // 1.5 Bandeau notification ouvert → fermer et marquer vu
        // / 1.5 Notification banner open → close and mark as viewed
        var bandeauNotification = document.getElementById('bandeau-notifications');
        if (bandeauNotification && bandeauNotification.querySelector('.bandeau-notification')) {
            bandeauNotification.innerHTML = '';
            if (window.notificationsProgression) {
                window.notificationsProgression.marquerVu();
            }
            return true;
        }

        // 2. Mode focus actif → desactiver
        // / 2. Focus mode active → deactivate
        if (window.marginalia && window.marginalia.modeFocusEstActif()) {
            window.marginalia.desactiverModeFocus();
            return true;
        }

        // 3. Dashboard ouvert → fermer
        // / 3. Dashboard open → close
        if (window.dashboardConsensus && window.dashboardConsensus.estOuvert()) {
            window.dashboardConsensus.fermer();
            return true;
        }

        // 4. Drawer ouvert → fermer
        // / 4. Drawer open → close
        if (window.drawerVueListe && window.drawerVueListe.estOuvert()) {
            window.drawerVueListe.fermer();
            return true;
        }

        // 5. Arbre ouvert → fermer
        // / 5. Tree open → close
        if (window.arbreOverlay && window.arbreOverlay.estOuvert()) {
            window.arbreOverlay.fermer();
            return true;
        }

        // 6. Carte inline ouverte → fermer
        // / 6. Inline card open → close
        var carteInlineOuverte = document.querySelector('.carte-inline');
        if (carteInlineOuverte) {
            var extractionIdCarte = carteInlineOuverte.dataset.extractionId;
            if (window.marginalia) {
                window.marginalia.fermerCarteInline(carteInlineOuverte, extractionIdCarte);
            } else if (typeof fermerCarteInline === 'function') {
                fermerCarteInline(carteInlineOuverte, extractionIdCarte);
            }
            return true;
        }

        // 7. Extraction selectionnee → deselectionner
        // / 7. Extraction selected → deselect
        if (indexExtractionSelectionnee >= 0) {
            deselectionnerExtraction();
            return true;
        }

        return false;
    }


    // === Listener unique keydown ===
    // / === Single keydown listener ===
    document.addEventListener('keydown', function(evenement) {
        var touche = evenement.key;

        // Escape fonctionne toujours (meme dans un champ de saisie)
        // / Escape always works (even in an input field)
        if (touche === 'Escape') {
            var gere = gererEscape();
            if (gere) {
                evenement.preventDefault();
            }
            return;
        }

        // Ignorer les raccourcis si dans un champ de saisie
        // / Ignore shortcuts if in an input field
        if (estDansChampSaisie()) return;

        // Ignorer si Ctrl, Meta ou Alt est enfonce (raccourcis navigateur)
        // / Ignore if Ctrl, Meta or Alt is pressed (browser shortcuts)
        if (evenement.ctrlKey || evenement.metaKey || evenement.altKey) return;

        switch (touche) {
            // T → Toggle arbre de navigation
            // / T → Toggle navigation tree
            case 't':
                if (window.arbreOverlay) {
                    window.arbreOverlay.basculer();
                }
                evenement.preventDefault();
                break;

            // E → Toggle drawer vue liste
            // / E → Toggle list view drawer
            case 'e':
                if (window.drawerVueListe) {
                    window.drawerVueListe.basculer();
                }
                evenement.preventDefault();
                break;

            // L → Toggle mode focus lecture
            // / L → Toggle focus reading mode
            case 'l':
                if (window.marginalia) {
                    window.marginalia.basculerModeFocus();
                }
                evenement.preventDefault();
                break;

            // J → Extraction suivante
            // / J → Next extraction
            case 'j':
                extractionSuivante();
                evenement.preventDefault();
                break;

            // K → Extraction precedente
            // / K → Previous extraction
            case 'k':
                extractionPrecedente();
                evenement.preventDefault();
                break;

            // C → Commenter extraction selectionnee
            // / C → Comment selected extraction
            case 'c':
                commenterExtractionSelectionnee();
                evenement.preventDefault();
                break;

            // S → Marquer consensuelle
            // / S → Mark as consensual
            case 's':
                marquerConsensuelleExtraction();
                evenement.preventDefault();
                break;

            // X → Masquer extraction selectionnee
            // / X → Hide selected extraction
            case 'x':
                masquerExtractionSelectionnee();
                evenement.preventDefault();
                break;

            // A → Toggle alignement du dossier courant
            // / A → Toggle alignment for current folder
            case 'a':
                if (window.alignement) {
                    window.alignement.basculerAlignement();
                }
                evenement.preventDefault();
                break;

            // H → Toggle heat map du debat (PHASE-19)
            // / H → Toggle debate heat map (PHASE-19)
            case 'h':
                if (window.marginalia) {
                    window.marginalia.basculerHeatmap();
                }
                evenement.preventDefault();
                break;

            // / → Recherche (placeholder)
            // / / → Search (placeholder)
            case '/':
                placeholderRecherche();
                evenement.preventDefault();
                break;

            // ? → Modale aide (chargee via HTMX depuis le serveur)
            // / ? → Help modal (loaded via HTMX from the server)
            case '?':
                // Eviter d'ouvrir un doublon si deja ouverte
                // / Avoid opening a duplicate if already open
                if (!document.getElementById('modale-raccourcis')) {
                    htmx.ajax('GET', '/lire/aide/', {
                        target: 'body',
                        swap: 'beforeend',
                    });
                }
                evenement.preventDefault();
                break;
        }
    });


    // === Initialisation au chargement ===
    // / === Initialization on load ===
    document.addEventListener('DOMContentLoaded', function() {
        reconstruireListeExtractions();

        // Le bouton aide est desormais gere par HTMX (hx-get dans le template)
        // / Help button is now handled by HTMX (hx-get in the template)

        // Empecher d'ouvrir 2 modales d'aide (via HTMX beforeend)
        // / Prevent opening 2 help modals (via HTMX beforeend)
        document.body.addEventListener('click', function(evenement) {
            var boutonAide = evenement.target.closest('#btn-toolbar-aide, #btn-toolbar-aide-mobile');
            if (!boutonAide) return;
            // Si la modale est deja ouverte, la fermer au lieu d'en creer une deuxieme
            // / If modal is already open, close it instead of creating a second one
            var modaleExistante = document.getElementById('modale-raccourcis');
            if (modaleExistante) {
                evenement.preventDefault();
                evenement.stopPropagation();
                modaleExistante.remove();
            }
        });

        // Toggle mode mobile : cycle entre 3 modes d'affichage
        // Le bouton oeil dans la toolbar change le mode a chaque tap :
        //   surlignage → lecture pure → heat map → retour au surlignage
        // - surlignage : le texte extrait a un fond colore (par statut de debat)
        // - lecture pure : pas de surlignage, texte brut pour lire sans distraction
        // - heat map : couleurs d'intensite du debat (rouge = beaucoup de commentaires)
        // / Mobile mode toggle: cycles between 3 display modes
        // The eye button in the toolbar changes mode on each tap:
        //   highlight → reading → heatmap → back to highlight
        var modeActuel = 'surlignage'; // surlignage | lecture | heatmap
        var boutonModeMobile = document.getElementById('btn-toolbar-mode-mobile');
        if (boutonModeMobile) {
            boutonModeMobile.addEventListener('click', function() {
                // Passer au mode suivant / Switch to next mode
                // Nettoyer les classes du mode precedent
                // / Clean classes from previous mode
                document.body.classList.remove('mode-lecture-mobile', 'mode-heatmap-mobile');

                if (modeActuel === 'surlignage') {
                    // Surlignage → Lecture : masquer le surlignage, eteindre la heatmap
                    // / Highlight → Reading: hide highlighting, turn off heatmap
                    modeActuel = 'lecture';
                    document.body.classList.add('mode-lecture-mobile');
                    if (window.marginalia && window.marginalia.heatmapEstActive()) {
                        window.marginalia.basculerHeatmap();
                    }
                } else if (modeActuel === 'lecture') {
                    // Lecture → Heatmap : activer la heatmap, masquer le surlignage individuel
                    // / Reading → Heatmap: activate heatmap, hide individual highlighting
                    modeActuel = 'heatmap';
                    document.body.classList.add('mode-heatmap-mobile');
                    if (window.marginalia && !window.marginalia.heatmapEstActive()) {
                        window.marginalia.basculerHeatmap();
                    }
                } else {
                    // Heatmap → Surlignage : eteindre la heatmap, remettre le surlignage
                    // / Heatmap → Highlight: turn off heatmap, restore highlighting
                    modeActuel = 'surlignage';
                    if (window.marginalia && window.marginalia.heatmapEstActive()) {
                        window.marginalia.basculerHeatmap();
                    }
                }

                // Mettre a jour le title du bouton pour indiquer le mode actif
                // / Update button title to indicate active mode
                var titresParMode = {
                    'surlignage': 'Mode : Surlignage (tap pour changer)',
                    'lecture': 'Mode : Lecture pure (tap pour changer)',
                    'heatmap': 'Mode : Heat map (tap pour changer)',
                };
                boutonModeMobile.title = titresParMode[modeActuel];
            });
        }
    });

    document.body.addEventListener('htmx:afterSwap', function(evenement) {
        var cible = evenement.detail.target;
        if (cible && (cible.id === 'zone-lecture' || cible.closest('#zone-lecture'))) {
            // Reinitialiser la selection et reconstruire la liste
            // / Reset selection and rebuild list
            deselectionnerExtraction();
            reconstruireListeExtractions();
        }
    });


    // Expose l'API publique
    // / Expose public API
    window.raccourcisClavier = {
        ouvrirAide: ouvrirAideRaccourcis,
        fermerAide: fermerAideRaccourcis,
    };

})();
