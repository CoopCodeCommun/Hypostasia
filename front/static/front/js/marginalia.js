// ==========================================================================
// marginalia.js — Pastilles en marge droite + ouverture drawer (A.8 drawer-only)
// / Right margin dots + drawer opening (A.8 drawer-only)
//
// LOCALISATION : front/static/front/js/marginalia.js
//
// Ce fichier gere l'interaction avec les ANCRES INLINE du texte
// (`mark.portion.hl-extraction`) : clic pour ouvrir le panneau sur la
// bonne carte, et estompage par contributeur.
//
// Son nom est un vestige : il gerait des pastilles en marge droite,
// supprimees avec l'ancien moteur (la maquette n'en a jamais eu).
// Un clic sur une ancre
// ouvre le drawer Analyses et scrolle vers la carte concernee a l'interieur
// du drawer (refonte drawer-only — plus de carte inline sous le paragraphe).
// / On click: open drawer + scroll to corresponding card (no inline card).
//
// COMMUNICATION :
// Recoit : HX-Trigger contributeurFiltreChange -> estompe les ancres
//          avec mode_filtre 'inclure'|'exclure' pour inverser le dimming (PHASE-26a UX)
// Appelle : window.drawerVueListe.ouvrir() pour ouvrir le drawer
// Exporte : window.marginalia = { getContributeurFiltre,
//           resetContributeurFiltre, ouvrirDrawerEtScrollerVersCarte }
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
        var spanCorrespondant = document.querySelector(
            '#readability-content .hl-extraction[data-extraction-id="' + extractionId + '"]'
        );
        if (spanCorrespondant) {
            spanCorrespondant.classList.add('ancre-active');
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
    // allumerIdee dans maquette.html), plus sur une pastille en marge.
    // sans effet nuisible. / Interaction now happens on a click on the
    // inline highlight itself, matching the mock.
    document.addEventListener('click', function(evenement) {
        var ancre = evenement.target.closest(
            '#readability-content .hl-extraction[data-extraction-id]'
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

    // Reset le filtre contributeurs (retire les classes d'estompage)
    // / Reset contributor filter (remove dimming classes)
    function resetContributeurFiltre() {
        contributeursFiltresActuels = [];
        document.querySelectorAll('.hl-extraction.ancre-hors-filtre').forEach(
            function (ancre) { ancre.classList.remove('ancre-hors-filtre'); }
        );
    }

    // Applique le filtre multi-contributeurs sur les ANCRES INLINE.
    //
    // Il estompait les pastilles en marge (PHASE-26a-bis). Celles-ci
    // ayant disparu avec l'ancien moteur, la fonction ne trouvait plus
    // un seul noeud : le filtre etait devenu INERTE, sans que rien ne le
    // dise. Il agit desormais sur `mark.hl-extraction`, la seule ancre
    // qui existe. Mode exclure : le dimming s'inverse.
    // / Rewired onto the inline anchors; the dots it dimmed are gone.
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

        document.querySelectorAll(
            '#readability-content .hl-extraction[data-extraction-id]'
        ).forEach(function (ancre) {
            var extractionId = ancre.dataset.extractionId;
            // En mode exclure, inverser la logique : estomper les entites
            // des contributeurs. / Exclude mode inverts the logic.
            var dansFiltre = setIdsEntites.has(extractionId);
            var doitEstomper = estModeExclure ? dansFiltre : !dansFiltre;
            if (doitEstomper) {
                ancre.classList.add('ancre-hors-filtre');
            } else {
                ancre.classList.remove('ancre-hors-filtre');
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


})();
