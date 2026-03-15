// ==========================================================================
// marginalia.js — Pastilles en marge droite + cartes inline (PHASE-09)
//                 + Mode focus lecture immersive (PHASE-17)
//                 + Heat map du debat (PHASE-19)
// / Right margin dots + inline cards (PHASE-09)
// / + Immersive focus reading mode (PHASE-17)
// / + Debate heat map (PHASE-19)
//
// LOCALISATION : front/static/front/js/marginalia.js
//
// Ce fichier gere les pastilles colorees en marge droite du texte.
// Chaque pastille represente une extraction. Sa couleur reflete le statut de debat.
// Un clic sur une pastille charge une carte inline via HTMX (endpoint carte_inline).
// La carte s'insere sous le paragraphe concerne avec une animation.
// Le mode focus (PHASE-17) masque les pastilles et centre le texte.
//
// COMMUNICATION :
// Recoit : htmx:afterSwap sur #zone-lecture -> reconstruit les pastilles
// Appelle : GET /extractions/carte_inline/?entity_id=N (front/views.py ExtractionViewSet)
// Exporte : window.marginalia = { construirePastillesMarginales, fermerCarteInline,
//           basculerModeFocus, desactiverModeFocus, modeFocusEstActif,
//           basculerHeatmap, heatmapEstActive }
// Exporte : window.construirePastillesMarginales (alias global, utilise par drawer_vue_liste.js)
// ==========================================================================
(function() {
    'use strict';

    // Mapping des couleurs par statut de debat.
    // Les valeurs correspondent aux variables CSS --statut-*-accent de hypostasia.css
    // / Color mapping by debate status (matches CSS variables)
    var COULEURS_STATUT = {
        consensuel:  '#429900',
        discutable:  '#B61601',
        discute:     '#D97706',
        controverse: '#FF4000',
    };

    // Cle localStorage pour persister le mode focus entre rechargements
    // / localStorage key to persist focus mode between reloads
    var CLE_LOCALSTORAGE_FOCUS = 'hypostasia-mode-focus';

    // Cle localStorage pour persister la heat map entre rechargements (PHASE-19)
    // / localStorage key to persist heat map between reloads (PHASE-19)
    var CLE_LOCALSTORAGE_HEATMAP = 'hypostasia-heatmap-actif';


    // === Mode focus (PHASE-17) ===
    // / === Focus mode (PHASE-17) ===

    // Active le mode focus : masque pastilles, desactive surlignage, centre le texte
    // / Activate focus mode: hide dots, disable highlights, center text
    function activerModeFocus() {
        // Desactiver la heat map si active (les deux sont incompatibles) (PHASE-19)
        // / Deactivate heat map if active (both are incompatible) (PHASE-19)
        if (heatmapEstActive()) {
            desactiverHeatmap();
        }

        document.body.classList.add('mode-focus');
        localStorage.setItem(CLE_LOCALSTORAGE_FOCUS, 'actif');

        // Met a jour le bouton toolbar / Update toolbar button
        var boutonFocus = document.getElementById('btn-toolbar-focus');
        if (boutonFocus) {
            boutonFocus.classList.add('btn-toolbar-actif');
        }
    }

    // Desactive le mode focus : restaure pastilles, surlignage et layout
    // / Deactivate focus mode: restore dots, highlights and layout
    function desactiverModeFocus() {
        document.body.classList.remove('mode-focus');
        localStorage.removeItem(CLE_LOCALSTORAGE_FOCUS);

        // Recalculer les pastilles marginales (positions changent au retour)
        // / Recalculate margin dots (positions change on return)
        construirePastillesMarginales();

        // Met a jour le bouton toolbar / Update toolbar button
        var boutonFocus = document.getElementById('btn-toolbar-focus');
        if (boutonFocus) {
            boutonFocus.classList.remove('btn-toolbar-actif');
        }
    }

    // Bascule le mode focus on/off
    // / Toggle focus mode on/off
    function basculerModeFocus() {
        if (modeFocusEstActif()) {
            desactiverModeFocus();
        } else {
            activerModeFocus();
        }
    }

    // Retourne true si le mode focus est actif
    // / Returns true if focus mode is active
    function modeFocusEstActif() {
        return document.body.classList.contains('mode-focus');
    }


    // === Heat map du debat (PHASE-19) ===
    // / === Debate heat map (PHASE-19) ===

    // Retourne true si la heat map est active
    // / Returns true if heat map is active
    function heatmapEstActive() {
        return document.body.classList.contains('mode-heatmap');
    }

    // Construit un calque underlay avec des halos radial-gradient
    // positionne en z-index sous le contenu de lecture.
    // Chaque bloc contenant des extractions genere un halo diffus
    // dont la couleur et l'opacite refletent l'intensite du debat.
    // / Build an underlay layer with radial-gradient halos
    // / positioned behind the reading content (z-index under text).
    // / Each block with extractions generates a diffuse halo
    // / whose color and opacity reflect debate intensity.
    function appliquerCouleursHeatmap() {
        // Le calque est place dans #zone-lecture (le <main> scrollable)
        // pour deborder sur toute la largeur de la page, pas seulement le texte.
        // / The overlay is placed in #zone-lecture (the scrollable <main>)
        // / to overflow across the full page width, not just the text.
        var zoneLecture = document.getElementById('zone-lecture');
        if (!zoneLecture) return;

        // Supprimer un eventuel calque precedent / Remove any previous overlay
        var ancienCalque = document.getElementById('heatmap-underlay');
        if (ancienCalque) ancienCalque.remove();

        var tousLesSpans = document.querySelectorAll('.hl-extraction[data-heat-color]');
        if (!tousLesSpans.length) return;

        // Grouper les spans par bloc parent pour trouver la couleur la plus chaude
        // / Group spans by parent block to find the hottest color
        var blocsAvecCouleurs = new Map();

        tousLesSpans.forEach(function(span) {
            var blocParent = span.closest('p, div.speaker-block, blockquote, li, h1, h2, h3, h4, h5, h6');
            if (!blocParent) return;
            if (blocParent.id === 'readability-content') return;

            var couleurHex = span.dataset.heatColor;
            if (!blocsAvecCouleurs.has(blocParent)) {
                blocsAvecCouleurs.set(blocParent, couleurHex);
            } else {
                // Garder la couleur la plus chaude (composante verte la plus basse)
                // / Keep the hottest color (lowest green component)
                var couleurExistante = blocsAvecCouleurs.get(blocParent);
                var gExistante = parseInt(couleurExistante.substring(3, 5), 16);
                var gNouvelle = parseInt(couleurHex.substring(3, 5), 16);
                if (gNouvelle < gExistante) {
                    blocsAvecCouleurs.set(blocParent, couleurHex);
                }
            }
        });

        if (!blocsAvecCouleurs.size) return;

        // Creer le calque underlay / Create the underlay layer
        var calqueHeatmap = document.createElement('div');
        calqueHeatmap.id = 'heatmap-underlay';

        // Le calque couvre toute la zone de lecture scrollable
        // / The overlay covers the entire scrollable reading zone
        var hauteurZone = zoneLecture.scrollHeight;
        var largeurZone = zoneLecture.offsetWidth;

        calqueHeatmap.style.position = 'absolute';
        calqueHeatmap.style.top = '0';
        calqueHeatmap.style.left = '0';
        calqueHeatmap.style.width = '100%';
        calqueHeatmap.style.height = hauteurZone + 'px';
        calqueHeatmap.style.pointerEvents = 'none';
        calqueHeatmap.style.zIndex = '1';
        calqueHeatmap.style.mixBlendMode = 'multiply';

        // Construire la liste des gradients radiaux / Build the list of radial gradients
        var gradientsRadiaux = [];

        blocsAvecCouleurs.forEach(function(couleurHex, bloc) {
            var rectBloc = bloc.getBoundingClientRect();
            var rectZone = zoneLecture.getBoundingClientRect();
            // Position du centre du halo par rapport a la zone de lecture entiere
            // / Center of the halo relative to the entire reading zone
            var centreX = largeurZone / 2;
            var centreY = (rectBloc.top - rectZone.top) + zoneLecture.scrollTop + (rectBloc.height / 2);

            // Score de chaleur normalise depuis data-heat-color (composante verte)
            // 253 (vert pale = froid) → 242 (rouge pale = chaud) → [0, 1]
            // / Normalized heat score from data-heat-color (green component)
            var gSource = parseInt(couleurHex.substring(3, 5), 16);
            var chaleurNormalisee = 1.0 - ((gSource - 242) / (253 - 242));
            chaleurNormalisee = Math.max(0.0, Math.min(1.0, chaleurNormalisee));

            // Palette lisible : vert franc → ambre → rouge rosé
            // Le vert doit etre clairement vert (consensus), le rouge contenu.
            // / Readable palette: clear green → amber → rosy red.
            // / Green must be clearly green (consensus), red stays contained.
            var r, gC, b;
            if (chaleurNormalisee < 0.4) {
                // Froid → tiede : vert (160, 220, 180) → ambre (220, 200, 140)
                // / Cold → warm: green → amber
                var t = chaleurNormalisee / 0.4;
                r = Math.round(160 + t * 60);
                gC = Math.round(220 - t * 20);
                b = Math.round(180 - t * 40);
            } else {
                // Tiede → chaud : ambre (220, 200, 140) → rose (235, 170, 160)
                // / Warm → hot: amber → rose
                var t = (chaleurNormalisee - 0.4) / 0.6;
                r = Math.round(220 + t * 15);
                gC = Math.round(200 - t * 30);
                b = Math.round(140 + t * 20);
            }

            // Opacite : [0.20 → 0.50] — visible sans ecraser le texte
            // / Opacity: [0.20 → 0.50] — visible without crushing the text
            var opacite = 0.20 + (chaleurNormalisee * 0.30);

            // Rayons resseres : le halo epouse la zone du bloc + debordement modere
            // / Tighter radii: halo hugs the block zone + moderate overflow
            var rayonVertical = rectBloc.height * 0.9 + 80;
            var rayonHorizontal = largeurZone * 0.8;

            gradientsRadiaux.push(
                'radial-gradient(ellipse ' + rayonHorizontal + 'px ' + rayonVertical + 'px at '
                + centreX + 'px ' + centreY + 'px, '
                + 'rgba(' + r + ',' + gC + ',' + b + ',' + opacite.toFixed(2) + ') 0%, '
                + 'rgba(' + r + ',' + gC + ',' + b + ',0) 100%)'
            );
        });

        calqueHeatmap.style.background = gradientsRadiaux.join(', ');

        // S'assurer que la zone de lecture est en position relative
        // / Ensure reading zone is position:relative
        var positionZone = getComputedStyle(zoneLecture).position;
        if (positionZone === 'static') {
            zoneLecture.style.position = 'relative';
        }

        // Inserer le calque en dernier enfant (au-dessus du contenu, blend multiply)
        // / Insert overlay as last child (above content, blend multiply)
        zoneLecture.appendChild(calqueHeatmap);
    }

    // Retire le calque heat map / Remove the heat map overlay
    function retirerCouleursHeatmap() {
        var calque = document.getElementById('heatmap-underlay');
        if (calque) calque.remove();
    }

    // Active la heat map : colore les blocs et spans selon l'intensite du debat
    // / Activate heat map: color blocks and spans by debate intensity
    function activerHeatmap() {
        document.body.classList.add('mode-heatmap');
        localStorage.setItem(CLE_LOCALSTORAGE_HEATMAP, 'actif');

        appliquerCouleursHeatmap();

        // Bouton toolbar actif / Active toolbar button
        var boutonHeatmap = document.getElementById('btn-toolbar-heatmap');
        if (boutonHeatmap) boutonHeatmap.classList.add('btn-toolbar-actif');
    }

    // Desactive la heat map : retire toutes les couleurs
    // / Deactivate heat map: remove all colors
    function desactiverHeatmap() {
        document.body.classList.remove('mode-heatmap');
        localStorage.removeItem(CLE_LOCALSTORAGE_HEATMAP);

        retirerCouleursHeatmap();

        // Bouton toolbar normal / Normal toolbar button
        var boutonHeatmap = document.getElementById('btn-toolbar-heatmap');
        if (boutonHeatmap) boutonHeatmap.classList.remove('btn-toolbar-actif');
    }

    // Bascule la heat map on/off
    // / Toggle heat map on/off
    function basculerHeatmap() {
        if (heatmapEstActive()) {
            desactiverHeatmap();
        } else {
            // Desactiver le mode focus si actif (les deux sont incompatibles)
            // / Deactivate focus mode if active (both are incompatible)
            if (modeFocusEstActif()) desactiverModeFocus();
            activerHeatmap();
        }
    }


    // === Construction des pastilles en marge droite ===
    // Scanne les spans hl-extraction, groupe par bloc parent, cree les pastilles
    // / Scan hl-extraction spans, group by parent block, create dots
    function construirePastillesMarginales() {
        // Nettoyer les pastilles existantes / Clean existing dots
        document.querySelectorAll('.pastilles-marge').forEach(function(el) {
            el.remove();
        });

        var tousLesSpans = document.querySelectorAll('#readability-content .hl-extraction[data-statut]');
        if (!tousLesSpans.length) return;

        // Grouper les spans par element bloc parent
        // / Group spans by parent block element
        var spansParBloc = new Map();
        tousLesSpans.forEach(function(span) {
            var blocParent = span.closest('p, div, blockquote, li, h1, h2, h3, h4, h5, h6');
            if (!blocParent) return;

            // Exclure le conteneur #readability-content lui-meme (c'est un div)
            // / Exclude the #readability-content container itself (it's a div)
            if (blocParent.id === 'readability-content') return;

            if (!spansParBloc.has(blocParent)) {
                spansParBloc.set(blocParent, []);
            }
            spansParBloc.get(blocParent).push(span);
        });

        // Pour chaque bloc parent, creer un conteneur de pastilles
        // / For each parent block, create a dot container
        spansParBloc.forEach(function(spans, blocParent) {
            var conteneurPastilles = document.createElement('div');
            conteneurPastilles.className = 'pastilles-marge';

            // Position verticale alignee avec le premier span du bloc
            // / Vertical position aligned with the first span in the block
            var rectBloc = blocParent.getBoundingClientRect();
            var rectPremierSpan = spans[0].getBoundingClientRect();
            var decalageHaut = rectPremierSpan.top - rectBloc.top;
            conteneurPastilles.style.top = decalageHaut + 'px';

            spans.forEach(function(span) {
                var extractionId = span.dataset.extractionId;
                var statut = span.dataset.statut || 'discutable';
                var couleur = COULEURS_STATUT[statut] || COULEURS_STATUT.discutable;

                var pastille = document.createElement('button');
                pastille.className = 'pastille-extraction';
                pastille.dataset.extractionId = extractionId;
                pastille.style.backgroundColor = couleur;
                pastille.title = 'Extraction #' + extractionId + ' — ' + statut;
                pastille.setAttribute('aria-label', 'Voir extraction ' + extractionId);

                conteneurPastilles.appendChild(pastille);
            });

            blocParent.appendChild(conteneurPastilles);
        });
    }


    // --- Clic sur une pastille : toggle carte inline ---
    // / Click on a dot: toggle inline card
    document.addEventListener('click', function(evenement) {
        var pastille = evenement.target.closest('.pastille-extraction');
        if (!pastille) return;

        var extractionId = pastille.dataset.extractionId;
        if (!extractionId) return;

        // Si mobile, ouvrir le bottom sheet (PHASE-21)
        // / If mobile, open bottom sheet (PHASE-21)
        if (window.innerWidth <= 768 && window.bottomSheet) {
            window.bottomSheet.ouvrir(extractionId);
            return;
        }

        // Trouver le bloc parent du span correspondant
        // / Find the parent block of the corresponding span
        var spanCorrespondant = document.querySelector(
            '#readability-content .hl-extraction[data-extraction-id="' + extractionId + '"]'
        );
        if (!spanCorrespondant) return;

        var blocParent = spanCorrespondant.closest('p, div, blockquote, li, h1, h2, h3, h4, h5, h6');
        if (!blocParent || blocParent.id === 'readability-content') return;

        // Toggle : si carte deja ouverte pour cet extraction-id → la fermer
        // / Toggle: if card already open for this extraction-id → close it
        var carteExistante = document.querySelector('.carte-inline[data-extraction-id="' + extractionId + '"]');
        if (carteExistante) {
            fermerCarteInline(carteExistante, extractionId);
            return;
        }

        // Nettoyer le surlignage precedent / Clean previous highlighting
        document.querySelectorAll('.hl-extraction.ancre-active').forEach(function(el) {
            el.classList.remove('ancre-active');
        });
        document.querySelectorAll('.pastille-extraction.pastille-active').forEach(function(el) {
            el.classList.remove('pastille-active');
        });

        // Activer le span et la pastille / Activate span and dot
        spanCorrespondant.classList.add('ancre-active');
        pastille.classList.add('pastille-active');

        // Charger la carte via HTMX / Load card via HTMX
        var divTemporaire = document.createElement('div');
        divTemporaire.style.display = 'none';
        document.body.appendChild(divTemporaire);

        htmx.ajax('GET', '/extractions/carte_inline/?entity_id=' + extractionId, {
            target: divTemporaire,
            swap: 'innerHTML',
        }).then(function() {
            var contenuCarte = divTemporaire.firstElementChild;
            if (contenuCarte) {
                // Inserer la carte apres le bloc parent / Insert card after parent block
                blocParent.insertAdjacentElement('afterend', contenuCarte);
                // Traiter les attributs HTMX dans la carte inseree
                // / Process HTMX attributes in the inserted card
                htmx.process(contenuCarte);
            }
            divTemporaire.remove();
        });
    });


    // --- Fermeture carte inline (bouton ▴ via event delegation) ---
    // / Close inline card (▴ button via event delegation)
    document.addEventListener('click', function(evenement) {
        var boutonReplier = evenement.target.closest('.btn-replier-carte');
        if (!boutonReplier) return;

        var extractionId = boutonReplier.dataset.extractionId;
        var carte = boutonReplier.closest('.carte-inline');
        if (carte) {
            fermerCarteInline(carte, extractionId);
        }
    });


    // Fonction utilitaire pour fermer une carte avec animation
    // / Utility function to close a card with animation
    function fermerCarteInline(carte, extractionId) {
        // Desactiver la pastille et le span / Deactivate dot and span
        if (extractionId) {
            var pastilleActive = document.querySelector(
                '.pastille-extraction.pastille-active[data-extraction-id="' + extractionId + '"]'
            );
            if (pastilleActive) {
                pastilleActive.classList.remove('pastille-active');
            }
            var spanActif = document.querySelector(
                '.hl-extraction.ancre-active[data-extraction-id="' + extractionId + '"]'
            );
            if (spanActif) {
                spanActif.classList.remove('ancre-active');
            }
        }

        // Animation de sortie puis suppression / Exit animation then removal
        carte.classList.remove('carte-inline-entree');
        carte.classList.add('carte-inline-sortie');
        carte.addEventListener('animationend', function() {
            carte.remove();
        }, { once: true });
    }


    // --- Recalcul automatique apres swap HTMX ---
    // / Automatic recalculation after HTMX swap
    document.body.addEventListener('htmx:afterSwap', function(evenement) {
        // Reconstruire si le swap touche la zone de lecture
        // / Rebuild if swap touches the reading zone
        var cible = evenement.detail.target;
        if (cible && (cible.id === 'zone-lecture' || cible.closest('#zone-lecture'))) {
            construirePastillesMarginales();
            // Reappliquer la heat map si active sur les nouveaux spans (PHASE-19)
            // / Reapply heat map if active on new spans (PHASE-19)
            if (heatmapEstActive()) {
                appliquerCouleursHeatmap();
            }
        }
    });


    // --- Initialisation au chargement de la page ---
    // / Initialization on page load
    document.addEventListener('DOMContentLoaded', function() {
        construirePastillesMarginales();

        // Restaurer le mode focus si actif dans localStorage (PHASE-17)
        // / Restore focus mode if active in localStorage (PHASE-17)
        if (localStorage.getItem(CLE_LOCALSTORAGE_FOCUS) === 'actif') {
            activerModeFocus();
        }

        // Restaurer la heat map si active dans localStorage (PHASE-19)
        // / Restore heat map if active in localStorage (PHASE-19)
        if (localStorage.getItem(CLE_LOCALSTORAGE_HEATMAP) === 'actif') {
            activerHeatmap();
        }

        // Clic sur le bouton focus dans la toolbar (PHASE-17)
        // / Click on focus button in toolbar (PHASE-17)
        var boutonFocus = document.getElementById('btn-toolbar-focus');
        if (boutonFocus) {
            boutonFocus.addEventListener('click', basculerModeFocus);
        }

        // Clic sur le bouton heat map dans la toolbar (PHASE-19)
        // / Click on heat map button in toolbar (PHASE-19)
        var boutonHeatmap = document.getElementById('btn-toolbar-heatmap');
        if (boutonHeatmap) {
            boutonHeatmap.addEventListener('click', basculerHeatmap);
        }
    });


    // Expose l'API publique (PHASE-17)
    // / Expose public API (PHASE-17)
    window.marginalia = {
        construirePastillesMarginales: construirePastillesMarginales,
        fermerCarteInline: fermerCarteInline,
        basculerModeFocus: basculerModeFocus,
        desactiverModeFocus: desactiverModeFocus,
        modeFocusEstActif: modeFocusEstActif,
        basculerHeatmap: basculerHeatmap,
        heatmapEstActive: heatmapEstActive,
    };

    // --- Tap sur .hl-extraction sur mobile → ouvrir bottom sheet (PHASE-21) ---
    // / Tap on .hl-extraction on mobile → open bottom sheet (PHASE-21)
    document.addEventListener('click', function(evenement) {
        var spanExtraction = evenement.target.closest('.hl-extraction[data-extraction-id]');
        if (!spanExtraction) return;
        if (window.innerWidth > 768) return;
        if (!window.bottomSheet) return;
        window.bottomSheet.ouvrir(spanExtraction.dataset.extractionId);
    });


    // Alias global pour compatibilite (utilise par drawer_vue_liste.js l86)
    // / Global alias for compatibility (used by drawer_vue_liste.js l86)
    window.construirePastillesMarginales = construirePastillesMarginales;
    window.fermerCarteInline = fermerCarteInline;

})();
