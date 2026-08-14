/**
 * LE LECTEUR AUDIO — ecart n°2 de l'etalon (maquette.html § 19).
 * / The audio player — gap n°2 of the reference mockup.
 *
 * LOCALISATION : front/static/front/js/lecteur_audio.js
 *
 * CE QUI EXISTAIT AVANT, ET N'ETAIT PAS UN LECTEUR
 *
 * `transcription_rythme.js` porte, depuis PHASE-15, une « barre de
 * progression de lecture ». Le nom trompe : elle suit le DEFILEMENT du
 * texte, pas le son. On pouvait la voir avancer sans qu'aucun son ne
 * sorte. Les deux coexistent : l'une dit ou on LIT, celle-ci ou on
 * ECOUTE.
 *
 * LA DUREE VIENT DU FICHIER, JAMAIS DE LA TRANSCRIPTION
 *
 * Les bornes des tours de parole s'arretent au dernier mot prononce ;
 * le media, lui, peut courir plus loin — silence de fin, applaudis-
 * sements, respiration. Mettre le rail a l'echelle du dernier `fin`
 * ferait terminer la tete de lecture avant le bout du son. On attend
 * donc `loadedmetadata` et on utilise `audio.duration`.
 *
 * POURQUOI TOUT SE REBRANCHE APRES CHAQUE SWAP HTMX
 *
 * La barre est redeposee par OOB swap a chaque navigation : l'element
 * <audio> du DOM n'est plus le meme objet. Les ecouteurs poses sur
 * l'ancien seraient perdus avec lui. Ceux qui portent sur le DOCUMENT
 * (clic, clavier) sont delegues une seule fois ; ceux qui portent sur
 * l'element audio sont reposes a chaque rendu.
 * / The bar is re-deposited by OOB swap, so the <audio> element is a
 * new object each time: document-level listeners are delegated once,
 * audio-level ones are re-attached on every render.
 */
(function () {
    "use strict";

    // Le tour de parole en cours d'ecoute, garde d'un `timeupdate` a
    // l'autre : sans lui, on repeindrait tout le texte 4 fois par
    // seconde pour ne rien changer.
    // / The turn being played, kept between ticks to avoid repainting
    // the whole text four times a second for nothing.
    var elementDuTourCourant = null;

    /**
     * Rend « 04:12 » a partir d'un nombre de secondes.
     * Trois morceaux au-dela de l'heure, sinon deux — jamais « 64:12 »,
     * qu'on lirait de travers. Meme regle que `_minutage_lisible`
     * cote serveur (rendu_elements.py:353).
     * / Same rule as the server's _minutage_lisible.
     */
    function formaterLeMinutage(secondes) {
        if (!isFinite(secondes) || secondes < 0) return "00:00";
        var total = Math.floor(secondes);
        var heures = Math.floor(total / 3600);
        var minutes = Math.floor((total % 3600) / 60);
        var reste = total % 60;
        var deuxChiffres = function (n) { return n < 10 ? "0" + n : "" + n; };
        if (heures) {
            return heures + ":" + deuxChiffres(minutes) + ":" + deuxChiffres(reste);
        }
        return deuxChiffres(minutes) + ":" + deuxChiffres(reste);
    }

    function lElementAudio() {
        return document.getElementById("audio-source");
    }

    /**
     * Met les segments du rail a l'echelle de la duree REELLE du
     * fichier, et les peint a la couleur de leur locuteur.
     *
     * Appelee sur `loadedmetadata`, jamais avant : `audio.duration`
     * vaut NaN tant que les metadonnees ne sont pas la, et toutes les
     * largeurs vaudraient NaN%.
     * / Called on loadedmetadata: duration is NaN before that.
     */
    function mettreLeRailALEchelle(audio) {
        var rail = document.getElementById("rail");
        if (!rail || !isFinite(audio.duration) || audio.duration <= 0) return;

        rail.setAttribute("aria-valuemax", audio.duration.toFixed(2));

        var segments = rail.querySelectorAll(".segment-locuteur");
        for (var i = 0; i < segments.length; i++) {
            var segment = segments[i];
            var debut = parseFloat(segment.dataset.debut);
            var fin = parseFloat(segment.dataset.fin);
            if (!isFinite(debut) || !isFinite(fin)) continue;

            // Un tour peut deborder la duree annoncee du media si la
            // transcription a ete faite sur un autre fichier : on le
            // borne plutot que de le laisser sortir du rail.
            // / A turn may overrun the media's duration; clamp it.
            var gauche = Math.max(0, Math.min(debut, audio.duration));
            var droite = Math.max(gauche, Math.min(fin, audio.duration));

            segment.style.left = (gauche / audio.duration * 100) + "%";
            // Un tour tres court doit rester VISIBLE : sans plancher, un
            // tour de 0,4s sur un enregistrement d'une heure occuperait
            // un centieme de pixel et disparaitrait du rail.
            // / A 0.4s turn in a one-hour file would vanish without this.
            var largeur = (droite - gauche) / audio.duration * 100;
            segment.style.width = Math.max(largeur, 0.4) + "%";

            if (segment.dataset.couleur) {
                segment.style.background = segment.dataset.couleur;
            }
        }
    }

    /**
     * Le tour de parole qui contient cet instant, ou null.
     * / The turn containing this instant, or null.
     */
    function tourALInstant(instant) {
        var blocs = document.querySelectorAll("#readability-content .bloc[data-debut]");
        for (var i = 0; i < blocs.length; i++) {
            var debut = parseFloat(blocs[i].dataset.debut);
            var fin = parseFloat(blocs[i].dataset.fin);
            if (isFinite(debut) && isFinite(fin)
                    && instant >= debut && instant < fin) {
                return blocs[i];
            }
        }
        return null;
    }

    /**
     * Deplace la tete, ecrit le minutage, nomme le tour courant.
     * / Move the playhead, write the timecode, name the current turn.
     */
    function rafraichir(audio) {
        var duree = audio.duration;
        var minutage = document.getElementById("minutage");
        var tete = document.getElementById("tete-de-lecture");
        var rail = document.getElementById("rail");

        if (minutage) {
            minutage.textContent = formaterLeMinutage(audio.currentTime)
                + " / " + formaterLeMinutage(duree);
        }
        if (tete && isFinite(duree) && duree > 0) {
            tete.style.left = (audio.currentTime / duree * 100) + "%";
        }
        if (rail) {
            rail.setAttribute("aria-valuenow", audio.currentTime.toFixed(2));
            rail.setAttribute("aria-valuetext",
                formaterLeMinutage(audio.currentTime));
        }

        var tourCourant = tourALInstant(audio.currentTime);
        if (tourCourant !== elementDuTourCourant) {
            if (elementDuTourCourant) {
                elementDuTourCourant.classList.remove("bloc-en-lecture");
            }
            if (tourCourant) {
                tourCourant.classList.add("bloc-en-lecture");
            }
            elementDuTourCourant = tourCourant;

            var titre = document.getElementById("piste-titre");
            if (titre) {
                titre.textContent = tourCourant
                    ? (tourCourant.dataset.locuteur || "Tour de parole")
                    : "—";
            }

            // LE TEXTE NE SUIT L'OREILLE QUE PENDANT LA LECTURE.
            // Deplacer la page pendant qu'on la lit a l'arret serait
            // une page qui bouge toute seule. Et seulement au CHANGEMENT
            // de tour : defiler a chaque `timeupdate` empecherait toute
            // lecture en arriere.
            // / The text follows the ear only while playing, and only on
            // turn change: scrolling on every tick would fight the reader.
            if (tourCourant && !audio.paused) {
                tourCourant.scrollIntoView({block: "center", behavior: "smooth"});
            }
        }
    }

    function marquerLEtatDuBouton(audio) {
        var bouton = document.getElementById("bouton-lecture");
        if (!bouton) return;
        // ► et ❚❚ : le glyphe DIT ce que le clic va faire.
        // / The glyph says what the click will do.
        bouton.textContent = audio.paused ? "▶" : "❚❚";
        bouton.setAttribute("aria-label", audio.paused
            ? "Lire l'enregistrement" : "Mettre en pause");
    }

    /**
     * Rebranche les ecouteurs sur l'element <audio> courant.
     * Appelee au chargement et apres chaque OOB swap : l'element n'est
     * plus le meme objet, les anciens ecouteurs sont partis avec lui.
     * / Re-attach listeners to the current <audio>; the old element is
     * gone after each OOB swap.
     */
    function brancherLeLecteur() {
        var audio = lElementAudio();
        elementDuTourCourant = null;
        if (!audio || audio.dataset.branche === "oui") return;
        audio.dataset.branche = "oui";

        audio.addEventListener("loadedmetadata", function () {
            mettreLeRailALEchelle(audio);
            rafraichir(audio);
        });
        audio.addEventListener("timeupdate", function () { rafraichir(audio); });
        audio.addEventListener("play", function () { marquerLEtatDuBouton(audio); });
        audio.addEventListener("pause", function () { marquerLEtatDuBouton(audio); });
        audio.addEventListener("ended", function () { marquerLEtatDuBouton(audio); });

        // Le fichier peut deja etre en cache : `loadedmetadata` a alors
        // pu passer avant ce branchement. On rattrape.
        // / The file may be cached and the event already fired.
        if (audio.readyState >= 1) {
            mettreLeRailALEchelle(audio);
            rafraichir(audio);
        }
        marquerLEtatDuBouton(audio);
    }

    /**
     * Deplace la lecture a la position cliquee sur le rail.
     * / Seek to the clicked position on the rail.
     */
    function deplacerDepuisLeRail(rail, positionEnX) {
        var audio = lElementAudio();
        if (!audio || !isFinite(audio.duration) || audio.duration <= 0) return;
        var boite = rail.getBoundingClientRect();
        var proportion = (positionEnX - boite.left) / boite.width;
        proportion = Math.max(0, Math.min(1, proportion));
        audio.currentTime = proportion * audio.duration;
        rafraichir(audio);
    }

    // ================================================================
    // Les gestes, delegues sur le DOCUMENT — poses UNE fois, ils
    // survivent a tous les swaps HTMX.
    // / Document-level delegation: attached once, survives every swap.
    // ================================================================

    document.addEventListener("click", function (evenement) {
        var bouton = evenement.target.closest("#bouton-lecture");
        if (bouton) {
            var audio = lElementAudio();
            if (!audio) return;
            if (audio.paused) {
                // `play()` rend une promesse qui PEUT etre rejetee — le
                // navigateur refuse le son tant que rien n'a ete
                // clique, et un rejet non capture remonte en erreur de
                // console. Ici le clic EST le geste, donc le cas est
                // rare ; on le tait proprement plutot que de le laisser
                // salir la console.
                // / play() can reject; swallow it cleanly.
                var promesse = audio.play();
                if (promesse && promesse.catch) { promesse.catch(function () {}); }
            } else {
                audio.pause();
            }
            // LE GLYPHE BASCULE TOUT DE SUITE, sans attendre l'evenement.
            // `pause()` met `paused` a true immediatement, mais
            // l'evenement `pause` n'est distribue qu'au tour suivant :
            // entre les deux, le bouton affiche encore « en lecture »
            // alors que le son s'est deja tu. Court, mais c'est
            // exactement le moment ou l'on regarde le bouton.
            // / The glyph flips at once: `paused` is true immediately
            // while the event fires a tick later — and that tick is
            // precisely when the eye is on the button.
            marquerLEtatDuBouton(audio);
            return;
        }

        var rail = evenement.target.closest("#rail");
        if (rail) {
            deplacerDepuisLeRail(rail, evenement.clientX);
            return;
        }

        // ECOUTER DEPUIS UN TOUR DE PAROLE, par le bouton de la
        // gouttiere. Il est distinct du minutage : celui-ci reste un
        // repere qu'on lit, celui-la une action qu'on prend.
        // / Play from a turn, via the gutter button — distinct from the
        // timecode, which stays a marker you read.
        var boutonDEcoute = evenement.target.closest(".bouton-ecouter");
        if (boutonDEcoute) {
            var bloc = boutonDEcoute.closest(".bloc[data-debut]");
            var lecteur = lElementAudio();
            if (!bloc || !lecteur) return;
            var debut = parseFloat(bloc.dataset.debut);
            if (!isFinite(debut)) return;
            lecteur.currentTime = debut;
            var lancement = lecteur.play();
            if (lancement && lancement.catch) { lancement.catch(function () {}); }
        }
    });

    // LE RAIL AU CLAVIER. Il porte `role="slider"` : sans les fleches,
    // c'est une promesse non tenue — un slider qu'on peut atteindre au
    // clavier mais pas actionner.
    // / The rail claims role="slider"; arrows make that true.
    document.addEventListener("keydown", function (evenement) {
        if (!evenement.target.closest || !evenement.target.closest("#rail")) return;
        var audio = lElementAudio();
        if (!audio || !isFinite(audio.duration)) return;

        var pas = 0;
        if (evenement.key === "ArrowRight") pas = 5;
        else if (evenement.key === "ArrowLeft") pas = -5;
        else if (evenement.key === "Home") { audio.currentTime = 0; rafraichir(audio); evenement.preventDefault(); return; }
        else if (evenement.key === "End") { audio.currentTime = audio.duration; rafraichir(audio); evenement.preventDefault(); return; }
        else return;

        evenement.preventDefault();
        audio.currentTime = Math.max(
            0, Math.min(audio.duration, audio.currentTime + pas));
        rafraichir(audio);
    });

    // Au chargement direct, et apres chaque swap HTMX qui redepose la
    // barre. / On direct load, and after each swap that re-deposits it.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", brancherLeLecteur);
    } else {
        brancherLeLecteur();
    }
    document.body.addEventListener("htmx:afterSwap", brancherLeLecteur);
})();
