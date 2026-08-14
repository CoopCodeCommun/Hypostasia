/**
 * Filtre par locuteur d'une transcription audio (PHASE-15).
 * / Speaker filter for an audio transcription (PHASE-15).
 *
 * LOCALISATION : front/static/front/js/transcription_rythme.js
 *
 * CE FICHIER PORTAIT TROIS DISPOSITIFS. DEUX ONT ETE RETIRES LE
 * 14 AOUT 2026, A LA DEMANDE DU MAINTENEUR — ET AUCUN DES TROIS NE
 * FONCTIONNAIT ENCORE.
 *
 * Tous visaient `.speaker-block` / `#speaker-block-N`, c'est-a-dire le
 * HTML DIARISE FIGE que `construire_html_diarise` produisait a
 * l'ingestion. Les pages passees au moteur ELEMENT ne rendent plus ce
 * HTML : elles rendent leurs `ElementDocument`, en blocs `.bloc`.
 * Mesure du 14 aout sur la note 8 : `speaker-block-` y apparait ZERO
 * fois.
 *
 *   · TIMELINE click-to-scroll — retiree. Son clic cherchait
 *     `#speaker-block-N`, introuvable : il ne se passait rien. Le rail
 *     du lecteur audio (maquette § 19) fait ce qu'elle promettait, et
 *     davantage : il montre la forme du debat ET deplace la lecture.
 *   · BARRE DE PROGRESSION — retiree. Elle suivait le DEFILEMENT du
 *     texte, pas le son, et doublait la barre du navigateur. Son nom,
 *     « progression de lecture », a longtemps fait croire qu'un lecteur
 *     audio existait deja.
 *   · FILTRE PAR LOCUTEUR — REPARE, et non retire. Il masquait des
 *     `.speaker-block` absents : cliquer « speaker_1 » ne masquait
 *     AUCUN texte (9 blocs visibles sur 9), alors que la pilule
 *     s'allumait. Un controle qui ne fait rien est pire qu'un controle
 *     absent : on croit avoir filtre. Il vise desormais les blocs
 *     reels.
 *
 * Suivre une voix a travers un echange a un sens : c'est pourquoi ce
 * troisieme dispositif est repare plutot que supprime avec les autres.
 * / All three targeted the frozen diarised HTML that ELEMENT pages no
 * longer render. Two removed; the speaker filter repaired, because
 * following one voice through a debate is worth having.
 */
(function () {
    "use strict";

    var zoneLecture = document.getElementById("zone-lecture");
    if (!zoneLecture) return;

    // Delegue les clics sur les pilules de filtre locuteur : les blocs
    // arrivent par HTMX, un ecouteur par bloc serait perdu au premier
    // rechargement. / Delegated: blocks arrive via HTMX.
    zoneLecture.addEventListener("click", function (evenement) {
        var piluleCliquee = evenement.target.closest(".pilule-locuteur");
        if (!piluleCliquee) return;

        var filtreLocuteur = piluleCliquee.getAttribute("data-speaker-filter");
        if (!filtreLocuteur) return;

        var toutesPilules = zoneLecture.querySelectorAll(".pilule-locuteur");
        for (var indexPilule = 0; indexPilule < toutesPilules.length; indexPilule++) {
            toutesPilules[indexPilule].classList.remove("pilule-active");
        }
        piluleCliquee.classList.add("pilule-active");

        // LES BLOCS REELS, et non `.speaker-block`. C'est la correction
        // du 14 aout : le filtre visait un HTML que la page ne rend
        // plus, et ne masquait donc rien.
        // / The real blocks, not the frozen diarised ones.
        var tousLesTours = zoneLecture.querySelectorAll(
            "#readability-content .bloc[data-locuteur]");

        for (var i = 0; i < tousLesTours.length; i++) {
            var estLeBonLocuteur = filtreLocuteur === "tous"
                || tousLesTours[i].getAttribute("data-locuteur") === filtreLocuteur;
            tousLesTours[i].classList.toggle(
                "masque-par-filtre", !estLeBonLocuteur);
        }
    });

})();
