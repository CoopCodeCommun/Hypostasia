// ==========================================================================
// bottom_sheet.js — Bottom sheet mobile pour les extractions (PHASE-21)
// / Mobile bottom sheet for extractions (PHASE-21)
//
// LOCALISATION : front/static/front/js/bottom_sheet.js
//
// Composant bottom sheet qui monte depuis le bas de l'ecran sur mobile.
// Affiche une carte d'extraction chargee via HTMX depuis l'endpoint carte_mobile.
// Navigation swipe gauche/droite entre les extractions (ordre du texte).
// Scroll automatique du paragraphe source en vue a l'ouverture.
//
// COMMUNICATION :
// Appelle : GET /extractions/carte_mobile/?entity_id=N (front/views.py ExtractionViewSet)
// Lit : les spans .hl-extraction[data-extraction-id] dans #readability-content
// Exporte : window.bottomSheet = { ouvrir, fermer, estOuvert }
// ==========================================================================
(function() {
    'use strict';

    // References DOM / DOM references
    var backdrop = null;
    var sheet = null;
    var contenu = null;
    var ouvert = false;

    // Extraction actuellement affichee / Currently displayed extraction
    var extractionIdActuelle = null;

    // Classe CSS du body sauvegardee avant ouverture (pour restaurer le mode a la fermeture)
    // / Body CSS class saved before opening (to restore mode on close)
    var classeModeSauvegardee = null;

    // Liste ordonnee des extractions visibles (par position dans le texte)
    // / Ordered list of visible extractions (by position in text)
    var listeExtractionsOrdonnees = [];

    // Variables pour le swipe horizontal / Horizontal swipe variables
    var swipeEnCours = false;
    var swipeDebutX = 0;
    var swipeDebutY = 0;
    var swipeDeltaX = 0;

    // Initialise les references DOM au premier appel
    // / Initialize DOM references on first call
    function initialiserRefs() {
        if (backdrop) return;
        backdrop = document.getElementById('bottom-sheet-backdrop');
        sheet = document.getElementById('bottom-sheet');
        contenu = document.getElementById('bottom-sheet-contenu');
    }

    // Construit la liste ordonnee des extractions depuis les spans du texte
    // / Build ordered extraction list from text spans
    function construireListeExtractions() {
        listeExtractionsOrdonnees = [];
        var tousLesSpans = document.querySelectorAll('#readability-content .hl-extraction[data-extraction-id]');
        var idsDejaVus = {};
        for (var i = 0; i < tousLesSpans.length; i++) {
            var identifiant = tousLesSpans[i].dataset.extractionId;
            // Eviter les doublons (un meme extraction_id peut avoir plusieurs spans)
            // / Avoid duplicates (same extraction_id can have multiple spans)
            if (identifiant && !idsDejaVus[identifiant]) {
                idsDejaVus[identifiant] = true;
                listeExtractionsOrdonnees.push(identifiant);
            }
        }
    }

    // Isole visuellement une seule extraction (masque le surlignage des autres)
    // / Visually isolate a single extraction (hide highlighting on others)
    function isolerSurlignage(extractionId) {
        // Sauvegarder le mode actuel du body avant de le modifier
        // / Save current body mode before modifying it
        if (classeModeSauvegardee === null) {
            if (document.body.classList.contains('mode-lecture-mobile')) {
                classeModeSauvegardee = 'mode-lecture-mobile';
            } else if (document.body.classList.contains('mode-heatmap-mobile')) {
                classeModeSauvegardee = 'mode-heatmap-mobile';
            } else {
                classeModeSauvegardee = 'surlignage';
            }
        }

        // Ajouter la classe qui masque tout le surlignage
        // puis marquer l'extraction active avec une classe speciale
        // / Add class that hides all highlighting
        // then mark the active extraction with a special class
        document.body.classList.add('bottom-sheet-focus');
        document.body.classList.remove('mode-lecture-mobile', 'mode-heatmap-mobile');

        // Retirer l'ancien focus s'il y en a un
        // / Remove previous focus if any
        var ancienFocus = document.querySelector('.hl-extraction.hl-focus-actif');
        if (ancienFocus) {
            ancienFocus.classList.remove('hl-focus-actif');
        }

        // Marquer le span actif
        // / Mark the active span
        var spanActif = document.querySelector(
            '.hl-extraction[data-extraction-id="' + extractionId + '"]'
        );
        if (spanActif) {
            spanActif.classList.add('hl-focus-actif');
        }
    }

    // Restaure le mode de surlignage d'avant l'ouverture du bottom sheet
    // / Restore the highlighting mode from before the bottom sheet was opened
    function restaurerSurlignage() {
        document.body.classList.remove('bottom-sheet-focus');

        // Retirer la classe de focus actif
        // / Remove active focus class
        var spanFocus = document.querySelector('.hl-extraction.hl-focus-actif');
        if (spanFocus) {
            spanFocus.classList.remove('hl-focus-actif');
        }

        // Restaurer le mode precedent / Restore previous mode
        if (classeModeSauvegardee === 'mode-lecture-mobile') {
            document.body.classList.add('mode-lecture-mobile');
        } else if (classeModeSauvegardee === 'mode-heatmap-mobile') {
            document.body.classList.add('mode-heatmap-mobile');
        }
        // Si 'surlignage', rien a faire (c'est le defaut)
        // / If 'surlignage', nothing to do (it's the default)

        classeModeSauvegardee = null;
    }

    // Scrolle le paragraphe source de l'extraction en vue (au-dessus du bottom sheet)
    // L'element scrollable est #zone-lecture (overflow-y: auto), pas window
    // / Scroll the extraction's source paragraph into view (above the bottom sheet)
    // The scrollable element is #zone-lecture (overflow-y: auto), not window
    function scrollerVersExtraction(extractionId) {
        var spanSource = document.querySelector(
            '#readability-content .hl-extraction[data-extraction-id="' + extractionId + '"]'
        );
        if (!spanSource) return;

        var zoneLecture = document.getElementById('zone-lecture');
        if (!zoneLecture) return;

        // Calculer ou scroller pour que le texte source soit visible
        // On veut le placer juste sous la barre de navigation (56px du haut)
        // Le bottom sheet prend le bas de l'ecran, donc le texte doit etre en haut
        // / Calculate where to scroll so source text is visible
        // We want it placed just below the navbar (56px from top)
        // The bottom sheet takes the bottom of the screen, so text must be at top
        var rectSpan = spanSource.getBoundingClientRect();
        var rectZone = zoneLecture.getBoundingClientRect();
        var positionRelativeDansZone = rectSpan.top - rectZone.top + zoneLecture.scrollTop;
        // 56px = hauteur navbar (48px) + petit padding (8px)
        // / 56px = navbar height (48px) + small padding (8px)
        var hauteurCible = 56;
        var positionScroll = positionRelativeDansZone - hauteurCible;

        zoneLecture.scrollTo({
            top: Math.max(0, positionScroll),
            behavior: 'smooth',
        });
    }

    // Ouvre le bottom sheet et charge la carte d'extraction via HTMX
    // / Open bottom sheet and load extraction card via HTMX
    function ouvrir(extractionId) {
        initialiserRefs();
        if (!sheet || !backdrop || !contenu) return;

        extractionIdActuelle = String(extractionId);

        // Construire la liste des extractions si pas encore fait
        // / Build extraction list if not done yet
        if (listeExtractionsOrdonnees.length === 0) {
            construireListeExtractions();
        }

        // Isoler le surlignage sur l'extraction active
        // / Isolate highlighting on the active extraction
        isolerSurlignage(extractionId);

        // Montrer le backdrop et le sheet / Show backdrop and sheet
        backdrop.classList.add('visible');
        sheet.classList.add('ouvert');
        ouvert = true;

        // Charger le contenu via HTMX / Load content via HTMX
        htmx.ajax('GET', '/extractions/carte_mobile/?entity_id=' + extractionId, {
            target: '#bottom-sheet-contenu',
            swap: 'innerHTML',
        });

        // Scroller le paragraphe source en vue (avec un petit delai pour laisser le sheet s'ouvrir)
        // / Scroll source paragraph into view (with small delay to let sheet open)
        setTimeout(function() {
            scrollerVersExtraction(extractionId);
        }, 200);
    }

    // Ferme le bottom sheet avec animation
    // / Close bottom sheet with animation
    function fermer() {
        initialiserRefs();
        if (!sheet || !backdrop) return;

        sheet.classList.remove('ouvert');
        backdrop.classList.remove('visible');
        ouvert = false;
        extractionIdActuelle = null;

        // Restaurer le mode de surlignage precedent
        // / Restore previous highlighting mode
        restaurerSurlignage();

        // Reinitialiser le transform apres la transition
        // / Reset transform after transition
        sheet.style.transform = '';

        // Vider le contenu apres la transition de fermeture
        // / Empty content after close transition
        setTimeout(function() {
            if (contenu && !ouvert) {
                contenu.innerHTML = '';
            }
        }, 300);
    }

    // Navigue vers l'extraction suivante ou precedente
    // / Navigate to the next or previous extraction
    function naviguerExtraction(direction) {
        if (!extractionIdActuelle) return;
        if (listeExtractionsOrdonnees.length === 0) return;

        // Trouver l'index actuel dans la liste ordonnee
        // / Find current index in the ordered list
        var indexActuel = listeExtractionsOrdonnees.indexOf(extractionIdActuelle);
        if (indexActuel === -1) return;

        // Calculer le nouvel index (boucle) / Calculate new index (loop)
        var nouvelIndex = indexActuel + direction;
        if (nouvelIndex < 0) {
            nouvelIndex = listeExtractionsOrdonnees.length - 1;
        } else if (nouvelIndex >= listeExtractionsOrdonnees.length) {
            nouvelIndex = 0;
        }

        var nouvelleExtractionId = listeExtractionsOrdonnees[nouvelIndex];

        // Animer la transition horizontale (glissement)
        // / Animate horizontal transition (slide)
        if (contenu) {
            var directionCSS = direction > 0 ? '-100%' : '100%';
            contenu.style.transition = 'transform 0.15s ease-out, opacity 0.15s ease-out';
            contenu.style.transform = 'translateX(' + directionCSS + ')';
            contenu.style.opacity = '0';

            setTimeout(function() {
                // Charger la nouvelle carte / Load new card
                extractionIdActuelle = nouvelleExtractionId;
                htmx.ajax('GET', '/extractions/carte_mobile/?entity_id=' + nouvelleExtractionId, {
                    target: '#bottom-sheet-contenu',
                    swap: 'innerHTML',
                });

                // Animer l'entree depuis l'autre cote / Animate entry from the other side
                contenu.style.transition = 'none';
                contenu.style.transform = 'translateX(' + (direction > 0 ? '100%' : '-100%') + ')';
                contenu.style.opacity = '0';

                requestAnimationFrame(function() {
                    contenu.style.transition = 'transform 0.15s ease-out, opacity 0.15s ease-out';
                    contenu.style.transform = 'translateX(0)';
                    contenu.style.opacity = '1';
                });

                // Mettre a jour le focus sur la nouvelle extraction
                // / Update focus on the new extraction
                isolerSurlignage(nouvelleExtractionId);

                // Scroller le texte source en vue
                // / Scroll source text into view
                scrollerVersExtraction(nouvelleExtractionId);
            }, 150);
        }
    }

    // Retourne true si le bottom sheet est ouvert
    // / Returns true if bottom sheet is open
    function estOuvert() {
        return ouvert;
    }

    // === Swipe horizontal : gauche/droite pour naviguer entre extractions ===
    // / === Horizontal swipe: left/right to navigate between extractions ===

    document.addEventListener('touchstart', function(evenement) {
        initialiserRefs();
        if (!ouvert) return;
        // Ne reagir qu'aux touches dans le bottom sheet
        // / Only react to touches inside the bottom sheet
        if (!evenement.target.closest('#bottom-sheet')) return;

        swipeEnCours = true;
        swipeDebutX = evenement.touches[0].clientX;
        swipeDebutY = evenement.touches[0].clientY;
        swipeDeltaX = 0;
    });

    document.addEventListener('touchmove', function(evenement) {
        if (!swipeEnCours) return;

        var deltaX = evenement.touches[0].clientX - swipeDebutX;
        var deltaY = evenement.touches[0].clientY - swipeDebutY;

        // Verifier que le geste est principalement horizontal (pas vertical)
        // On veut que le deplacement horizontal soit au moins 2x le vertical
        // Sinon c'est un scroll normal de la page, pas un swipe de navigation
        // / Check gesture is mostly horizontal (not vertical)
        // Horizontal movement must be at least 2x the vertical
        // Otherwise it's a normal page scroll, not a navigation swipe
        if (Math.abs(deltaX) > 10 && Math.abs(deltaX) > Math.abs(deltaY) * 2) {
            swipeDeltaX = deltaX;
            // Empecher le scroll vertical pendant le swipe horizontal
            // / Prevent vertical scroll during horizontal swipe
            evenement.preventDefault();
        }
    }, { passive: false });

    document.addEventListener('touchend', function() {
        if (!swipeEnCours) return;
        swipeEnCours = false;

        // Seuil de 50px pour declencher la navigation
        // / 50px threshold to trigger navigation
        if (Math.abs(swipeDeltaX) > 50) {
            if (swipeDeltaX < 0) {
                // Swipe gauche → extraction suivante
                // / Swipe left → next extraction
                naviguerExtraction(1);
            } else {
                // Swipe droite → extraction precedente
                // / Swipe right → previous extraction
                naviguerExtraction(-1);
            }
        }
        swipeDeltaX = 0;
    });

    // Clic backdrop → fermer / Click backdrop → close
    document.addEventListener('click', function(evenement) {
        initialiserRefs();
        if (evenement.target === backdrop && ouvert) {
            fermer();
        }
    });

    // Clic bouton fermer (X) dans le bottom sheet → fermer
    // / Click close button (X) in bottom sheet → close
    document.addEventListener('click', function(evenement) {
        if (evenement.target.closest('.btn-fermer-bottom-sheet') && ouvert) {
            fermer();
        }
    });

    // Resize : fermer si > 768px / Resize: close if > 768px
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768 && ouvert) {
            fermer();
        }
    });

    // Reconstruire la liste quand le contenu de lecture change
    // / Rebuild list when reading content changes
    document.body.addEventListener('htmx:afterSwap', function(evenement) {
        var cible = evenement.detail.target;
        if (cible && (cible.id === 'zone-lecture' || cible.id === 'readability-content')) {
            listeExtractionsOrdonnees = [];
        }
    });

    // Traiter les attributs HTMX dans le contenu insere
    // / Process HTMX attributes in inserted content
    document.body.addEventListener('htmx:afterSettle', function(evenement) {
        var cible = evenement.detail.target;
        if (cible && cible.id === 'bottom-sheet-contenu') {
            htmx.process(cible);
        }
    });

    // Expose l'API publique / Expose public API
    window.bottomSheet = {
        ouvrir: ouvrir,
        fermer: fermer,
        estOuvert: estOuvert,
    };

})();
