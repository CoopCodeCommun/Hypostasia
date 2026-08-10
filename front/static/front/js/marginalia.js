// ==========================================================================
// marginalia.js — Pastilles en marge droite + ouverture drawer (A.8 drawer-only)
// / Right margin dots + drawer opening (A.8 drawer-only)
//
// LOCALISATION : front/static/front/js/marginalia.js
//
// Ce fichier gere les pastilles colorees en marge droite du texte.
// Chaque pastille represente une extraction. Sa couleur reflete le statut binaire
// (nouveau / commente). Un clic sur une pastille (ou sur un span surligne)
// ouvre le drawer Analyses et scrolle vers la carte concernee a l'interieur
// du drawer (refonte drawer-only — plus de carte inline sous le paragraphe).
// / On click: open drawer + scroll to corresponding card (no inline card).
//
// COMMUNICATION :
// Recoit : htmx:afterSwap sur #zone-lecture -> reconstruit les pastilles
// Recoit : HX-Trigger contributeurFiltreChange -> filtre pastilles (PHASE-26a-bis)
//          avec mode_filtre 'inclure'|'exclure' pour inverser le dimming (PHASE-26a UX)
// Appelle : window.drawerVueListe.ouvrir() pour ouvrir le drawer
// Exporte : window.marginalia = { construirePastillesMarginales,
//           getContributeurFiltre, resetContributeurFiltre }
// Exporte : window.construirePastillesMarginales (alias global, utilise par drawer_vue_liste.js)
// ==========================================================================
(function() {
    'use strict';

    // Mapping des couleurs par statut de debat (binaire A.8 : nouveau / commente).
    // Les valeurs correspondent aux variables CSS --statut-*-accent de hypostasia.css
    // / Color mapping by debate status (A.8 binary: new / commented), matches CSS variables
    var COULEURS_STATUT = {
        nouveau:  '#999999',
        commente: '#E69F00',
    };

    // === Construction des pastilles en marge droite ===
    // Scanne les spans hl-extraction, groupe par bloc parent, cree les pastilles
    // / Scan hl-extraction spans, group by parent block, create dots
    function construirePastillesMarginales() {
        // CONFORMITE MAQUETTE (10 aout) : la maquette n'a PAS de pastilles
        // en marge. Les ancres sont le SURLIGNAGE INLINE
        // (mark.portion.hl-extraction, pose par BR-D) et l'interaction se
        // fait au CLIC sur l'ancre elle-meme (voir le handler plus bas,
        // equivalent de allumerIdee de la maquette). On ne cree donc plus
        // aucune pastille ; on se contente de nettoyer d'eventuels
        // residus (anciennes pastilles laissees par un cache).
        // / The mock has no margin dots: anchors are the inline highlight
        // and interaction is a click on the anchor. We only clean leftovers.
        document.querySelectorAll('.pastilles-marge').forEach(function(el) {
            el.remove();
        });
    }


    // Ouvre le drawer + scrolle vers la carte de l'extraction donnee
    // Refonte A.8 drawer-only : plus de carte inline sous le paragraphe.
    // / Open drawer + scroll to the card for the given extraction.
    // / A.8 drawer-only refactor: no more inline card below the paragraph.
    function ouvrirDrawerEtScrollerVersCarte(extractionId) {
        // Activer le span correspondant dans le texte (surlignage)
        // / Activate corresponding span in text (highlight)
        document.querySelectorAll('.hl-extraction.ancre-active').forEach(function(el) {
            el.classList.remove('ancre-active');
        });
        document.querySelectorAll('.pastille-extraction.pastille-active').forEach(function(el) {
            el.classList.remove('pastille-active');
        });
        var spanCorrespondant = document.querySelector(
            '#readability-content .hl-extraction[data-extraction-id="' + extractionId + '"]'
        );
        if (spanCorrespondant) {
            spanCorrespondant.classList.add('ancre-active');
        }
        var pastilleCorrespondante = document.querySelector(
            '.pastille-extraction[data-extraction-id="' + extractionId + '"]'
        );
        if (pastilleCorrespondante) {
            pastilleCorrespondante.classList.add('pastille-active');
        }

        // Ouvrir le drawer s'il est ferme (le drawer rechargera son contenu via chargerContenu)
        // / Open drawer if closed (drawer will reload content via chargerContenu)
        if (window.drawerVueListe && !window.drawerVueListe.estOuvert()) {
            window.drawerVueListe.ouvrir();
        }

        // Scroller vers la carte dans le drawer (laisser le temps au contenu de se charger
        // si le drawer vient juste de s'ouvrir).
        // / Scroll to the card inside the drawer (give time to load if just opened).
        function scrollerVersCarte() {
            document.querySelectorAll('.drawer-carte-compacte.drawer-carte-active').forEach(function(el) {
                el.classList.remove('drawer-carte-active');
            });
            var carteDansDrawer = document.querySelector(
                '#drawer-contenu .drawer-carte-compacte[data-extraction-id="' + extractionId + '"]'
            );
            if (carteDansDrawer) {
                carteDansDrawer.classList.add('drawer-carte-active');
                carteDansDrawer.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
        // Si la carte est deja la (drawer deja ouvert), scroller tout de suite.
        // Sinon, attendre le swap HTMX du contenu (afterSwap sur #drawer-contenu).
        // / If card already there (drawer already open), scroll immediately.
        // / Otherwise, wait for HTMX swap on #drawer-contenu.
        var carteDejaPresente = document.querySelector(
            '#drawer-contenu .drawer-carte-compacte[data-extraction-id="' + extractionId + '"]'
        );
        if (carteDejaPresente) {
            scrollerVersCarte();
        } else {
            var contenuDrawer = document.getElementById('drawer-contenu');
            if (contenuDrawer) {
                var handlerUneFois = function() {
                    scrollerVersCarte();
                    contenuDrawer.removeEventListener('htmx:afterSwap', handlerUneFois);
                };
                contenuDrawer.addEventListener('htmx:afterSwap', handlerUneFois);
            }
        }
    }


    // --- Clic sur une ANCRE (surlignage inline) : ouvre le drawer + scroll ---
    // CONFORMITE MAQUETTE (10 aout) : l'interaction se fait desormais au clic
    // sur l'ancre inline `mark.hl-extraction` elle-meme (equivalent de
    // allumerIdee dans maquette.html), plus sur une pastille en marge. Le
    // fallback `.pastille-extraction` reste au cas ou un residu subsiste,
    // sans effet nuisible. / Interaction now happens on a click on the
    // inline highlight itself, matching the mock.
    document.addEventListener('click', function(evenement) {
        var ancre = evenement.target.closest(
            '#readability-content .hl-extraction[data-extraction-id], .pastille-extraction'
        );
        if (!ancre) return;
        // Ne pas traiter les pilules contributeur / Skip contributor pills
        if (ancre.classList.contains('pilule-contributeur')) return;

        var extractionId = ancre.dataset.extractionId;
        if (!extractionId) return;

        // Ne pas voler une SELECTION de texte en cours : si l'utilisateur
        // vient de surligner du texte (drag), on le laisse tranquille.
        // / Don't steal an in-progress text selection.
        var selection = window.getSelection && window.getSelection();
        if (selection && selection.toString().length > 0) return;

        // Si mobile, ouvrir le bottom sheet (PHASE-21)
        // / If mobile, open bottom sheet (PHASE-21)
        if (window.innerWidth <= 768 && window.bottomSheet) {
            window.bottomSheet.ouvrir(extractionId);
            return;
        }

        ouvrirDrawerEtScrollerVersCarte(extractionId);
    });


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


    // Expose l'API publique
    // / Expose public API
    window.marginalia = {
        construirePastillesMarginales: construirePastillesMarginales,
        getContributeurFiltre: getContributeurFiltre,
        resetContributeurFiltre: resetContributeurFiltre,
        ouvrirDrawerEtScrollerVersCarte: ouvrirDrawerEtScrollerVersCarte,
    };

    // --- Tap sur .hl-extraction sur mobile → ouvrir bottom sheet (PHASE-21) ---
    // Sur desktop : clic sur .hl-extraction → ouvrir le drawer (drawer-only A.8)
    // / Tap on .hl-extraction on mobile → open bottom sheet (PHASE-21)
    // / On desktop: click on .hl-extraction → open drawer (A.8 drawer-only)
    document.addEventListener('click', function(evenement) {
        var spanExtraction = evenement.target.closest('.hl-extraction[data-extraction-id]');
        if (!spanExtraction) return;
        var extractionId = spanExtraction.dataset.extractionId;
        if (!extractionId) return;
        if (window.innerWidth <= 768) {
            if (window.bottomSheet) window.bottomSheet.ouvrir(extractionId);
            return;
        }
        // Desktop : ouvrir le drawer + scroller vers la carte
        // / Desktop: open drawer + scroll to card
        ouvrirDrawerEtScrollerVersCarte(extractionId);
    });


    // Alias global pour compatibilite (utilise par drawer_vue_liste.js l86)
    // / Global alias for compatibility (used by drawer_vue_liste.js l86)
    window.construirePastillesMarginales = construirePastillesMarginales;

})();
