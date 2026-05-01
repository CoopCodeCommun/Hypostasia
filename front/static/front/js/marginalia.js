// ==========================================================================
// marginalia.js — Pastilles en marge droite + cartes inline (PHASE-09)
//                 + Mode focus lecture immersive (PHASE-17)
// / Right margin dots + inline cards (PHASE-09)
// / + Immersive focus reading mode (PHASE-17)
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
// Recoit : HX-Trigger contributeurFiltreChange -> filtre pastilles (PHASE-26a-bis)
//          avec mode_filtre 'inclure'|'exclure' pour inverser le dimming (PHASE-26a UX)
// Appelle : GET /extractions/carte_inline/?entity_id=N (front/views.py ExtractionViewSet)
// Exporte : window.marginalia = { construirePastillesMarginales, fermerCarteInline,
//           basculerModeFocus, desactiverModeFocus, modeFocusEstActif,
//           getContributeurFiltre, resetContributeurFiltre }
// Exporte : window.construirePastillesMarginales (alias global, utilise par drawer_vue_liste.js)
// ==========================================================================
(function() {
    'use strict';

    // Mapping des couleurs par statut de debat.
    // Les valeurs correspondent aux variables CSS --statut-*-accent de hypostasia.css
    // / Color mapping by debate status (matches CSS variables)
    var COULEURS_STATUT = {
        nouveau:       '#999999',
        consensuel:    '#009E73',
        discutable:    '#E69F00',
        discute:       '#56B4E9',
        controverse:   '#D55E00',
        non_pertinent: '#CC79A7',
    };

    // Cle localStorage pour persister le mode focus entre rechargements
    // / localStorage key to persist focus mode between reloads
    var CLE_LOCALSTORAGE_FOCUS = 'hypostasia-mode-focus';


    // === Mode focus (PHASE-17) ===
    // / === Focus mode (PHASE-17) ===

    // Active le mode focus : masque pastilles, desactive surlignage, centre le texte
    // / Activate focus mode: hide dots, disable highlights, center text
    function activerModeFocus() {
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
                pastille.dataset.statut = statut;
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

        // Clic sur le bouton focus dans la toolbar (PHASE-17)
        // / Click on focus button in toolbar (PHASE-17)
        var boutonFocus = document.getElementById('btn-toolbar-focus');
        if (boutonFocus) {
            boutonFocus.addEventListener('click', basculerModeFocus);
        }
    });


    // === Filtre multi-contributeurs sur les pastilles (PHASE-26a-bis) ===
    // / === Multi-contributor filter on pastilles (PHASE-26a-bis) ===

    // IDs des contributeurs filtres actuellement (tableau vide = pas de filtre)
    // / Currently filtered contributor IDs (empty array = no filter)
    var contributeursFiltresActuels = [];

    // Retourne les IDs des contributeurs filtres actuellement
    // / Returns the currently filtered contributor IDs
    function getContributeurFiltre() {
        return contributeursFiltresActuels;
    }

    // Reset le filtre contributeurs (retire les classes de dimming)
    // / Reset contributor filter (remove dimming classes)
    function resetContributeurFiltre() {
        contributeursFiltresActuels = [];
        document.querySelectorAll('.pastille-extraction.pastille-hors-filtre').forEach(function(pastille) {
            pastille.classList.remove('pastille-hors-filtre');
        });
    }

    // Applique le filtre multi-contributeurs sur les pastilles
    // Supporte le mode exclure : inverse le dimming (PHASE-26a UX)
    // / Apply multi-contributor filter on pastilles
    // / Supports exclude mode: inverts dimming (PHASE-26a UX)
    function appliquerFiltreContributeurs(listeContributeursIds, idsEntites, modeFiltre) {
        contributeursFiltresActuels = listeContributeursIds;

        if (!listeContributeursIds || !listeContributeursIds.length) {
            // Pas de filtre → retirer toutes les classes de dimming
            // / No filter → remove all dimming classes
            resetContributeurFiltre();
            return;
        }

        var setIdsEntites = new Set(idsEntites.map(String));
        var estModeExclure = (modeFiltre === 'exclure');

        document.querySelectorAll('.pastille-extraction').forEach(function(pastille) {
            var extractionId = pastille.dataset.extractionId;
            // En mode exclure, inverser la logique : dimmer les entites des contributeurs
            // / In exclude mode, invert logic: dim the contributor's entities
            var dansFiltre = setIdsEntites.has(extractionId);
            var doitDimmer = estModeExclure ? dansFiltre : !dansFiltre;
            if (doitDimmer) {
                pastille.classList.add('pastille-hors-filtre');
            } else {
                pastille.classList.remove('pastille-hors-filtre');
            }
        });
    }

    // Listener HX-Trigger contributeurFiltreChange (PHASE-26a-bis)
    // / HX-Trigger listener for contributeurFiltreChange (PHASE-26a-bis)
    document.body.addEventListener('contributeurFiltreChange', function(evenement) {
        var detail = evenement.detail;
        if (!detail) return;
        appliquerFiltreContributeurs(
            detail.contributeurs_ids || [],
            detail.ids_entites || [],
            detail.mode_filtre || 'inclure'
        );
    });


    // Expose l'API publique (PHASE-17)
    // / Expose public API (PHASE-17)
    window.marginalia = {
        construirePastillesMarginales: construirePastillesMarginales,
        fermerCarteInline: fermerCarteInline,
        basculerModeFocus: basculerModeFocus,
        desactiverModeFocus: desactiverModeFocus,
        modeFocusEstActif: modeFocusEstActif,
        getContributeurFiltre: getContributeurFiltre,
        resetContributeurFiltre: resetContributeurFiltre,
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
