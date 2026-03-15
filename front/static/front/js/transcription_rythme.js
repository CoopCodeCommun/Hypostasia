/**
 * Rythme visuel de la transcription audio (PHASE-15)
 * / Audio transcription visual rhythm (PHASE-15)
 *
 * 3 fonctionnalites :
 * 1. Filtrage par locuteur (pilules cliquables)
 * 2. Timeline click-to-scroll (clic sur segment → scroll vers le bloc)
 * 3. Barre de progression de lecture (suit le scroll)
 *
 * Toutes les interactions utilisent la delegation d'evenements
 * sur #zone-lecture pour supporter le contenu charge via HTMX.
 * / All interactions use event delegation on #zone-lecture
 * to support content loaded via HTMX.
 */
(function () {
    "use strict";

    // Reference a la zone de lecture principale
    // / Reference to the main reading zone
    var zoneLecture = document.getElementById("zone-lecture");
    if (!zoneLecture) return;


    // ================================================================
    // 1. Filtrage par locuteur
    // / 1. Speaker filtering
    // ================================================================

    // Delegue les clics sur les pilules de filtre locuteur
    // / Delegate clicks on speaker filter pills
    zoneLecture.addEventListener("click", function (evenement) {
        var piluleCliquee = evenement.target.closest(".pilule-locuteur");
        if (!piluleCliquee) return;

        var filtreLocuteur = piluleCliquee.getAttribute("data-speaker-filter");
        if (!filtreLocuteur) return;

        // Mettre a jour l'etat actif des pilules
        // / Update the active state of pills
        var toutesPilules = zoneLecture.querySelectorAll(".pilule-locuteur");
        for (var indexPilule = 0; indexPilule < toutesPilules.length; indexPilule++) {
            toutesPilules[indexPilule].classList.remove("pilule-active");
        }
        piluleCliquee.classList.add("pilule-active");

        // Appliquer le filtre sur les blocs de transcription
        // / Apply filter on transcription blocks
        var tousLesBlocsLocuteur = zoneLecture.querySelectorAll(".speaker-block");
        var tousLesMarqueurs = zoneLecture.querySelectorAll(".marqueur-temporel");
        var tousLesSegmentsTimeline = zoneLecture.querySelectorAll(".timeline-segment");

        if (filtreLocuteur === "tous") {
            // Montrer tout / Show all
            for (var i = 0; i < tousLesBlocsLocuteur.length; i++) {
                tousLesBlocsLocuteur[i].classList.remove("masque-par-filtre");
            }
            for (var j = 0; j < tousLesMarqueurs.length; j++) {
                tousLesMarqueurs[j].classList.remove("masque-par-filtre");
            }
            for (var k = 0; k < tousLesSegmentsTimeline.length; k++) {
                tousLesSegmentsTimeline[k].classList.remove("masque-par-filtre");
            }
        } else {
            // Masquer les blocs qui ne correspondent pas au locuteur selectionne
            // / Hide blocks that don't match the selected speaker
            for (var ib = 0; ib < tousLesBlocsLocuteur.length; ib++) {
                var nomLocuteurBloc = tousLesBlocsLocuteur[ib].getAttribute("data-speaker");
                if (nomLocuteurBloc === filtreLocuteur) {
                    tousLesBlocsLocuteur[ib].classList.remove("masque-par-filtre");
                } else {
                    tousLesBlocsLocuteur[ib].classList.add("masque-par-filtre");
                }
            }
            // Masquer les marqueurs temporels quand un filtre est actif
            // / Hide time markers when a filter is active
            for (var jm = 0; jm < tousLesMarqueurs.length; jm++) {
                tousLesMarqueurs[jm].classList.add("masque-par-filtre");
            }
            // Griser les segments timeline qui ne correspondent pas
            // / Gray out timeline segments that don't match
            for (var kt = 0; kt < tousLesSegmentsTimeline.length; kt++) {
                var nomLocuteurSegment = tousLesSegmentsTimeline[kt].getAttribute("data-speaker");
                if (nomLocuteurSegment === filtreLocuteur) {
                    tousLesSegmentsTimeline[kt].classList.remove("masque-par-filtre");
                } else {
                    tousLesSegmentsTimeline[kt].classList.add("masque-par-filtre");
                }
            }
        }
    });


    // ================================================================
    // 2. Timeline click-to-scroll
    // / 2. Timeline click-to-scroll
    // ================================================================

    // Delegue les clics sur les segments de la timeline
    // / Delegate clicks on timeline segments
    zoneLecture.addEventListener("click", function (evenement) {
        var segmentClique = evenement.target.closest(".timeline-segment");
        if (!segmentClique) return;

        var indexBlocCible = segmentClique.getAttribute("data-block-index");
        if (indexBlocCible === null) return;

        // Trouver le bloc correspondant et scroller vers lui
        // / Find the matching block and scroll to it
        var blocCible = zoneLecture.querySelector("#speaker-block-" + indexBlocCible);
        if (!blocCible) return;

        blocCible.scrollIntoView({ behavior: "smooth", block: "center" });

        // Ajouter un flash visuel temporaire
        // / Add a temporary visual flash
        blocCible.classList.add("bloc-flash");
        setTimeout(function () {
            blocCible.classList.remove("bloc-flash");
        }, 1500);
    });


    // ================================================================
    // 3. Barre de progression de lecture
    // / 3. Reading progress bar
    // ================================================================

    // Met a jour la barre de progression en fonction du scroll
    // / Updates the progress bar based on scroll position
    function mettreAJourBarreProgression() {
        var barreRemplissage = zoneLecture.querySelector("#barre-progression-remplissage");
        if (!barreRemplissage) return;

        var hauteurScrollable = zoneLecture.scrollHeight - zoneLecture.clientHeight;
        if (hauteurScrollable <= 0) {
            barreRemplissage.style.width = "0%";
            return;
        }

        var pourcentageScroll = (zoneLecture.scrollTop / hauteurScrollable) * 100;
        barreRemplissage.style.width = Math.min(pourcentageScroll, 100) + "%";
    }

    // Ecouter le scroll sur la zone de lecture
    // / Listen to scroll on the reading zone
    zoneLecture.addEventListener("scroll", mettreAJourBarreProgression);

    // Clic sur la barre de progression → scroll proportionnel
    // / Click on progress bar → proportional scroll
    zoneLecture.addEventListener("click", function (evenement) {
        var barreProgression = evenement.target.closest("#barre-progression-audio");
        if (!barreProgression) return;

        // Calculer la position relative du clic dans la barre
        // / Calculate the relative click position in the bar
        var rectangleBarre = barreProgression.getBoundingClientRect();
        var positionRelative = (evenement.clientX - rectangleBarre.left) / rectangleBarre.width;
        positionRelative = Math.max(0, Math.min(1, positionRelative));

        // Scroller a la position proportionnelle
        // / Scroll to the proportional position
        var hauteurScrollable = zoneLecture.scrollHeight - zoneLecture.clientHeight;
        zoneLecture.scrollTo({
            top: positionRelative * hauteurScrollable,
            behavior: "smooth",
        });
    });

    // Recalculer apres chaque swap HTMX (contenu dynamique)
    // / Recalculate after each HTMX swap (dynamic content)
    document.body.addEventListener("htmx:afterSettle", function () {
        mettreAJourBarreProgression();
    });

})();
