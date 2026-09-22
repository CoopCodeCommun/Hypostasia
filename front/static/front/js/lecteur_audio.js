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
     * Place la lecture a un instant, MEME si les donnees n'y sont pas
     * encore.
     * / Seek to an instant, even if the data is not there yet.
     *
     * LE BUG QUE CETTE FONCTION CORRIGE (signale le 14 aout) : cliquer
     * un play dans le texte lancait l'audio DEPUIS LE DEBUT.
     *
     * Un navigateur IGNORE SILENCIEUSEMENT une affectation de
     * `currentTime` quand il n'a pas de quoi se placer la : ni erreur,
     * ni exception, la valeur retombe simplement a ce qu'elle etait. Or
     * la barre demande `preload="metadata"` — elle ne telecharge donc
     * que l'en-tete —, et `/media/` est servi en dev par
     * `django.views.static`, qui NE GERE PAS les requetes `Range` : le
     * navigateur ne peut pas aller chercher le morceau qui l'interesse.
     * Resultat : l'instant demande etait perdu, et la lecture partait
     * de zero.
     *
     * CE QUI A ETE ESSAYE, ET QU'IL NE FAUT PAS REFAIRE
     *
     * Une premiere correction rejouait l'affectation a chaque `canplay`,
     * et basculait `preload` a `auto` avec un `load()`. Le mainteneur a
     * entendu « un gresillement dans l'oreille a la place de l'audio » :
     * `load()` vide le tampon sous une lecture en cours, et le
     * repositionnement rejoue en boucle faisait sauter le decodeur
     * plusieurs fois par seconde. Un bricolage cote client ne repare pas
     * un serveur qui ne sait pas envoyer un morceau de fichier — il
     * ajoute un defaut au premier.
     *
     * LA CAUSE EST SERVEUR, ET C'EST LA QU'ELLE EST CORRIGEE :
     * `/media/` est desormais servi par nginx (nginx/dev.conf), qui
     * repond aux requetes `Range` en 206. Le navigateur va chercher le
     * morceau qui l'interesse, et `currentTime` prend du premier coup.
     *
     * Cette fonction reste le point de passage unique de tout
     * deplacement : un seul endroit a regarder le jour ou un navigateur
     * se comportera autrement.
     * / An earlier fix replayed the seek on every `canplay` and forced a
     * full `load()`; it produced audible crackling — load() empties the
     * buffer under a playing stream. The cause was the server, and that
     * is where it is fixed: nginx now serves /media/ and answers Range
     * with 206.
     */
    function deplacerLaLecture(audio, instantVise) {
        audio.currentTime = instantVise;
        // ON VIENT DE DESIGNER UN POINT : la prochaine reprise ne doit
        // pas le deplacer. Le drapeau vit sur l'element, comme l'etat de
        // branchement — il survit ainsi a tout ce qui vit dans ce
        // module. / A point was just designated: the next resume must
        // not move it.
        audio.dataset.sautVolontaire = 'oui';
    }

    // =================================================================
    // LES DEUX REGLAGES DE LA STENOTYPIE (SPEC-edition-par-blocs § 6.3)
    //
    // La VITESSE et le RECUL A LA REPRISE. Ils vivent ici, dans le
    // lecteur, et non dans le mode d'edition : ils servent aussi a qui
    // ecoute sans corriger, et le bouton ▶ de la barre doit en
    // beneficier autant que le clavier.
    //
    // ILS SURVIVENT AU SWAP. `brancherLeLecteur` est rappele a chaque
    // swap HTMX qui redepose la barre ; sans reapplication, la vitesse
    // choisie retomberait a 1× au premier rafraichissement — la spec
    // demande explicitement qu'elle « survive au changement de bloc ».
    //
    // ILS SONT DANS `localStorage`, PAS EN BASE : c'est un confort de
    // poste de travail. Deux personnes qui corrigent la meme note n'ont
    // aucune raison de partager leur vitesse d'ecoute.
    // / The two § 6.3 settings live in the player, survive HTMX swaps,
    // and are per-browser conveniences, never corpus data.
    // =================================================================

    var CLE_DE_LA_VITESSE = "hypostasia.lecteur.vitesse";
    var CLE_DU_RECUL = "hypostasia.lecteur.reculALaReprise";
    var VITESSES = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];
    var RECUL_PAR_DEFAUT = 2;
    // Les valeurs du menu de `_lecteur_audio.html`, et rien d'autre.
    // / The template's menu values, and nothing else.
    var RECULS_OFFERTS = [0, 1, 2, 3, 5];

    /**
     * Lit un reglage persiste, avec son defaut.
     * / Reads a persisted setting, with its default.
     *
     * `localStorage` peut lever — navigation privee, stockage refuse.
     * Un reglage de confort ne doit jamais empecher d'ecouter.
     * / localStorage can throw; a comfort setting must never block.
     */
    function lireLeReglage(cle, defaut) {
        try {
            var brut = window.localStorage.getItem(cle);
            if (brut === null) return defaut;
            var valeur = parseFloat(brut);
            return isFinite(valeur) ? valeur : defaut;
        } catch (erreur) {
            return defaut;
        }
    }

    function ecrireLeReglage(cle, valeur) {
        try {
            window.localStorage.setItem(cle, String(valeur));
        } catch (erreur) {
            // Rien : le reglage vaut pour cette session, c'est tout.
            // / Nothing: the setting holds for this session only.
        }
    }

    /**
     * La vitesse retenue, RAMENEE A UN PALIER CONNU.
     * / The stored speed, snapped to a known step.
     *
     * `localStorage` n'est pas une source sure : une valeur ecrite a la
     * console, par un autre code du meme domaine, ou par un futur
     * changement de format, y arrive telle quelle. Une vitesse hors
     * plage passee a `playbackRate` LEVE — et l'exception tomberait
     * dans `brancherLeLecteur`, a chaque chargement, en laissant la
     * barre a moitie branchee.
     * / localStorage is not a trusted source, and an out-of-range
     * playbackRate throws inside the binding.
     */
    function vitesseCourante() {
        var retenue = lireLeReglage(CLE_DE_LA_VITESSE, 1);
        return VITESSES.indexOf(retenue) === -1 ? 1 : retenue;
    }

    /**
     * Le recul retenu, RAMENE AUX VALEURS OFFERTES.
     * / The stored rewind, snapped to the offered values.
     *
     * Un recul enorme ferait repartir chaque reprise au debut du
     * fichier ; un recul negatif AVANCERAIT a la reprise.
     */
    function reculALaReprise() {
        var retenu = lireLeReglage(CLE_DU_RECUL, RECUL_PAR_DEFAUT);
        return RECULS_OFFERTS.indexOf(retenu) === -1 ? RECUL_PAR_DEFAUT : retenu;
    }

    /**
     * Affiche la vitesse, et l'applique a l'element audio.
     * / Shows the speed, and applies it to the audio element.
     */
    function appliquerLaVitesse(audio, facteur) {
        if (audio) audio.playbackRate = facteur;
        var affichage = document.getElementById("vitesse-de-lecture");
        if (affichage) {
            // « 1× », « 1,5× » — la virgule, pas le point : c'est du
            // francais. / A comma, not a dot: this is French.
            affichage.textContent =
                String(facteur).replace(".", ",") + "\u00d7";
        }
    }

    /**
     * Passe a la vitesse suivante ou precedente de la table.
     * / Steps to the next or previous speed in the table.
     *
     * Une TABLE de paliers, pas une multiplication : « 0,5 a 2 par pas
     * visibles » (§ 6.3). Multiplier par 1,1 donnerait 1,331× — un
     * nombre qu'on ne sait ni lire ni retrouver.
     */
    function changerLaVitesse(sens) {
        var audio = lElementAudio();
        var courante = vitesseCourante();
        var rang = VITESSES.indexOf(courante);
        if (rang === -1) rang = VITESSES.indexOf(1);
        var suivant = Math.max(0, Math.min(VITESSES.length - 1, rang + sens));
        var facteur = VITESSES[suivant];
        ecrireLeReglage(CLE_DE_LA_VITESSE, facteur);
        appliquerLaVitesse(audio, facteur);
        return facteur;
    }

    /**
     * Lance la lecture EN RECULANT du reglage de reprise.
     * / Starts playback, rewound by the resume setting.
     *
     * « On met en pause pour ecrire, et on a toujours perdu le debut de
     * la phrase » (§ 6.3). Le recul ne s'applique qu'a une REPRISE —
     * jamais a un saut volontaire, ou il deplacerait la cible qu'on
     * vient de designer.
     * / The rewind applies to a RESUME only, never to a deliberate seek.
     */
    function reprendreLaLecture(audio) {
        var recul = reculALaReprise();
        // TROIS CAS OU IL NE FAUT PAS RECULER, et chacun a coute une
        // mesure ou une relecture :
        //
        // 1. un SAUT VOLONTAIRE vient d'avoir lieu — clic sur le rail,
        //    « écouter ce passage », F2. On vient de DESIGNER un point :
        //    le deplacer de deux secondes est le contraire du service
        //    rendu. Le § 6.3 le dit, encore fallait-il le coder ;
        // 2. le fichier est FINI : `play()` sur un media termine repart
        //    du debut, et poser `currentTime = duree - recul` effacerait
        //    cet etat pour ne rejouer que les deux dernieres secondes ;
        // 3. on n'a jamais joue (`currentTime` a 0).
        // / Three cases where the rewind must not apply: after a
        // deliberate seek, on a finished file, and before the first play.
        var apresUnSaut = audio.dataset.sautVolontaire === 'oui';
        audio.dataset.sautVolontaire = 'non';
        if (recul > 0 && audio.currentTime > 0 && !audio.ended && !apresUnSaut) {
            deplacerLaLecture(audio, Math.max(0, audio.currentTime - recul));
        }
        var promesse = audio.play();
        if (promesse && promesse.catch) { promesse.catch(function () {}); }
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
     * Le tour de parole ou une idee est marquee, ou null.
     * / The turn where an idea is marked, or null.
     *
     * Une idee peut avoir PLUSIEURS ancres — elle enjambe deux tours, ou
     * revient plus loin. On prend la PREMIERE dans l'ordre du document :
     * c'est la ou l'idee apparait, et c'est de la qu'on veut ecouter.
     * / An idea may have several anchors; take the first in document
     * order — where it appears is where one wants to listen from.
     */
    function blocDUneIdee(identifiantDeLIdee) {
        if (!identifiantDeLIdee) return null;
        var marque = document.querySelector(
            '#readability-content mark[data-extraction-id="'
            + identifiantDeLIdee + '"]');
        return marque ? marque.closest(".bloc[data-debut]") : null;
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

        // ON OUBLIE LE TOUR COURANT, DONC ON EFFACE SA MARQUE.
        //
        // Remettre la variable a null sans nettoyer le DOM laissait un
        // SURLIGNAGE ORPHELIN : le bloc gardait sa teinte pour toujours,
        // et le tour suivant en recevait une seconde. Deux tours
        // surlignes a la fois ne designent plus rien.
        //
        // Le cas se produit a chaque swap HTMX PENDANT la lecture — par
        // exemple quand on clique « Écouter » sur une carte, ce qui
        // rafraichit le panneau. Mesure du 14 aout : la lecture etait a
        // 4,63s et le bloc surligne etait celui de 0,0s.
        // / Clearing the variable without clearing the DOM left an
        // orphan wash: the block kept its tint forever and the next turn
        // got a second one. Happens on every HTMX swap during playback.
        var dejaMarques = document.querySelectorAll(
            "#readability-content .bloc.bloc-en-lecture");
        for (var rang = 0; rang < dejaMarques.length; rang++) {
            dejaMarques[rang].classList.remove("bloc-en-lecture");
        }
        elementDuTourCourant = null;

        if (!audio || audio.dataset.branche === "oui") return;
        audio.dataset.branche = "oui";

        audio.addEventListener("loadedmetadata", function () {
            mettreLeRailALEchelle(audio);
            rafraichir(audio);
        });
        audio.addEventListener("timeupdate", function () {
            // LE SAUT S'OUBLIE DES QUE LE SON AVANCE. Sans cela, un
            // « reculer de 5 s » fait au debut d'une ecoute priverait de
            // recul la pause suivante, une demi-heure plus tard. Ce
            // qu'on veut retenir, c'est « un point vient d'etre
            // designe », pas « un point l'a ete un jour ».
            // / The seek is forgotten as soon as playback moves on.
            if (!audio.paused) audio.dataset.sautVolontaire = "non";
            rafraichir(audio);
        });
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
        // LES REGLAGES SE REAPPLIQUENT A CHAQUE BRANCHEMENT.
        //
        // `brancherLeLecteur` est rappele apres chaque swap HTMX qui
        // redepose la barre : sans cette ligne, la vitesse choisie
        // retomberait a 1x au premier rafraichissement, alors que le
        // § 6.3 demande qu'elle SURVIVE au changement de bloc.
        // / Reapplied on every re-bind: the speed must survive swaps.
        appliquerLaVitesse(audio, vitesseCourante());
        var choixDuRecul = document.getElementById("recul-a-la-reprise");
        if (choixDuRecul) choixDuRecul.value = String(reculALaReprise());
    }

    // Le reglage du recul se retient : on le choisit une fois, pas a
    // chaque note. / The rewind setting is remembered.
    document.addEventListener("change", function (evenement) {
        var choix = evenement.target.closest("#recul-a-la-reprise");
        if (!choix) return;
        ecrireLeReglage(CLE_DU_RECUL, parseFloat(choix.value));
    });

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
        deplacerLaLecture(audio, proportion * audio.duration);
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
                // PAR `reprendreLaLecture`, donc AVEC le recul du § 6.3 :
                // le bouton de la barre est une reprise comme une autre.
                // (Elle avale aussi le rejet possible de `play()` — le
                // navigateur refuse le son tant que rien n'a ete clique,
                // et un rejet non capture salit la console.)
                // / Through reprendreLaLecture, so the § 6.3 rewind
                // applies to the bar's button too.
                reprendreLaLecture(audio);
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
        // ECOUTER DEPUIS LA CARTE D'UNE IDEE. Le bouton ne porte que
        // l'identifiant : on retrouve la marque de l'idee dans le texte,
        // et c'est le bloc qui la contient qui donne l'instant. Rien
        // n'est recopie, donc rien ne peut diverger.
        // / The card's button carries only the id; the mark in the text
        // gives the instant. Nothing is copied, so nothing can drift.
        var boutonDeCarte = evenement.target.closest(".btn-ecouter-extraction");
        if (boutonDeCarte) {
            var lecteurDeCarte = lElementAudio();
            var blocDeLIdee = blocDUneIdee(boutonDeCarte.dataset.extractionId);
            if (!lecteurDeCarte || !blocDeLIdee) return;
            var instantDeLIdee = parseFloat(blocDeLIdee.dataset.debut);
            if (!isFinite(instantDeLIdee)) return;
            deplacerLaLecture(lecteurDeCarte, instantDeLIdee);
            var lectureDeCarte = lecteurDeCarte.play();
            if (lectureDeCarte && lectureDeCarte.catch) {
                lectureDeCarte.catch(function () {});
            }
            return;
        }

        if (evenement.target.closest("#bouton-ralentir")) {
            changerLaVitesse(-1);
            return;
        }
        if (evenement.target.closest("#bouton-accelerer")) {
            changerLaVitesse(1);
            return;
        }

        var boutonDEcoute = evenement.target.closest(".bouton-ecouter");
        if (boutonDEcoute) {
            var bloc = boutonDEcoute.closest(".bloc[data-debut]");
            var lecteur = lElementAudio();
            if (!bloc || !lecteur) return;
            var debut = parseFloat(bloc.dataset.debut);
            if (!isFinite(debut)) return;
            deplacerLaLecture(lecteur, debut);
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
        else if (evenement.key === "Home") { deplacerLaLecture(audio, 0); rafraichir(audio); evenement.preventDefault(); return; }
        else if (evenement.key === "End") { deplacerLaLecture(audio, audio.duration); rafraichir(audio); evenement.preventDefault(); return; }
        else return;

        evenement.preventDefault();
        deplacerLaLecture(audio, Math.max(
            0, Math.min(audio.duration, audio.currentTime + pas)));
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

    /**
     * L'API DU LECTEUR, pour qui veut le piloter sans le recopier.
     *
     * LOCALISATION : front/static/front/js/lecteur_audio.js
     *
     * Le mode d'edition (§ 6, la stenotypie) doit lancer, arreter,
     * reculer et ralentir le son SANS quitter le champ. Il pourrait
     * atteindre `document.querySelector('audio')` lui-meme — et il
     * refabriquerait alors le recul a la reprise, la table des
     * vitesses, l'avalement du rejet de `play()`, le rafraichissement
     * du rail. Quatre choses qui divergeraient.
     *
     * La regle du lecteur, deja ecrite au § 6.1 de la spec : « Rien
     * n'est recopie, donc rien ne peut diverger. »
     * / The editing mode drives the player through this API, never by
     * reaching for the audio element itself.
     */
    window.lecteurAudio = {
        /** L'element <audio>, ou null si la note n'a pas de son. */
        element: lElementAudio,
        /** Y a-t-il un son a piloter ? / Is there any sound to drive? */
        estDisponible: function () { return !!lElementAudio(); },
        /**
         * Bascule lecture/pause. La reprise applique le recul du § 6.3.
         * @return {boolean} vrai si le son joue apres le geste
         */
        lireOuPause: function () {
            var audio = lElementAudio();
            if (!audio) return false;
            if (audio.paused) {
                reprendreLaLecture(audio);
                marquerLEtatDuBouton(audio);
                return true;
            }
            audio.pause();
            marquerLEtatDuBouton(audio);
            return false;
        },
        /**
         * Ecoute a partir d'un instant PRECIS — un saut volontaire,
         * donc SANS le recul de reprise : il deplacerait la cible qu'on
         * vient de designer.
         * / A deliberate seek: no resume rewind.
         */
        ecouterDepuis: function (instant) {
            var audio = lElementAudio();
            if (!audio || !isFinite(instant)) return false;
            deplacerLaLecture(audio, Math.max(0, instant));
            var promesse = audio.play();
            if (promesse && promesse.catch) { promesse.catch(function () {}); }
            marquerLEtatDuBouton(audio);
            return true;
        },
        /** Recule ou avance de N secondes, sans sortir des bornes. */
        decaler: function (secondes) {
            var audio = lElementAudio();
            if (!audio || !isFinite(audio.duration)) return false;
            deplacerLaLecture(audio, Math.max(
                0, Math.min(audio.duration, audio.currentTime + secondes)));
            rafraichir(audio);
            return true;
        },
        /** Palier de vitesse suivant (+1) ou precedent (-1). */
        changerLaVitesse: changerLaVitesse,
        /** La vitesse courante, telle qu'elle est retenue. */
        vitesse: vitesseCourante,
        /** Le recul applique a la reprise, en secondes (0 = aucun). */
        reculALaReprise: reculALaReprise,
    };
})();
