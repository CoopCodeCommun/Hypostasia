/**
 * LE SPINNER, LA OU LE CLIC A EU LIEU.
 * LOCALISATION : front/static/front/js/spinner_au_clic.js
 *
 * A QUOI IL SERT. Toute requete HTMX du projet passe par ici, sans que
 * le gabarit ait un mot a dire : aucun `hx-indicator` a poser, aucun
 * element a prevoir. Un ecran qui gagne un bouton gagne son attente.
 *
 * POURQUOI AU POINT DE CLIC, ET PAS AU CENTRE DE L'ECRAN. Le regard est
 * deja la ou le doigt vient de toucher. Un voile central oblige a
 * chercher, et il cache ce qu'on etait en train de lire — c'est
 * exactement le tiroir a voile que le mainteneur a fait retirer du
 * panneau de preuve.
 *
 * DEUX REGLES QUI COMPTENT :
 *
 * - **LE DELAI.** Une requete de 40 ms qui allume un spinner produit un
 *   clignotement, et un clignotement se lit comme un defaut. On
 *   n'affiche rien avant `DELAI_AVANT_AFFICHAGE` : en deca, l'ecran a
 *   deja repondu.
 * - **UN SPINNER PAR REQUETE, reconnu par son `xhr`.** Plusieurs
 *   requetes se chevauchent souvent — un `hx-trigger="revealed"`
 *   pendant qu'on clique ailleurs. Chaque spinner n'est retire que par
 *   SA reponse : reconnaitre la requete a son ELEMENT ferait disparaitre
 *   le spinner d'un bouton des qu'une autre de ses requetes repond.
 *
 * / Every HTMX request gets a spinner at the pointer, with no template
 * changes: a delay so fast requests do not blink, and one spinner per
 * request so overlapping calls do not cancel each other.
 */
(function () {
    "use strict";

    // En deca, l'ecran a deja repondu : montrer un spinner ferait
    // clignoter. / Below this, the screen has already answered.
    var DELAI_AVANT_AFFICHAGE = 220;

    // La derniere position du pointeur. `pointerdown` couvre la souris,
    // le doigt et le stylet d'un seul evenement.
    // / One event for mouse, finger and pen.
    var dernier_point = null;

    document.addEventListener("pointerdown", function (evenement) {
        dernier_point = { x: evenement.clientX, y: evenement.clientY };
    }, true);

    /**
     * Ou poser le spinner : le point de clic s'il est frais, sinon le
     * centre de l'element qui declenche.
     * / The click point when it is fresh, else the trigger's centre.
     *
     * POURQUOI LE REPLI EST INDISPENSABLE : une requete peut partir
     * sans clic — `hx-trigger="revealed"`, `every 3s`, une touche du
     * clavier. Poser alors le spinner a la derniere position connue de
     * la souris le mettrait n'importe ou, souvent hors de l'ecran.
     * / A request can fire without a click; the last mouse position
     * would then be meaningless.
     */
    function ou_poser(element, vient_d_un_clic) {
        if (vient_d_un_clic && dernier_point) { return dernier_point; }
        if (!element || !element.getBoundingClientRect) { return null; }
        var boite = element.getBoundingClientRect();
        if (!boite.width && !boite.height) { return null; }
        return { x: boite.left + boite.width / 2, y: boite.top + boite.height / 2 };
    }

    /* UNE NAVIGATION EFFACE TOUT SPINNER, sans condition.

       POURQUOI CETTE SECONDE VOIE EXISTE. Le spinner d'une requete est
       retire par LA REPONSE de cette requete. Or un retour arriere ne
       produit aucune reponse : htmx restaure la page depuis son cache,
       la requete en vol est abandonnee sans que `htmx:afterRequest` ne
       parte, et le spinner — qui vit sur `<body>`, donc hors de la zone
       echangee — restait a tourner sur un ecran deja arrive.
       / A back navigation produces no response: the in-flight request is
       dropped without afterRequest, and the spinner lives on <body>,
       outside the swapped zone, so it kept spinning on an arrived page. */
    function tout_effacer() {
        document.querySelectorAll(".spinner-au-clic").forEach(function (s) {
            if (s.parentNode) { s.parentNode.removeChild(s); }
        });
    }

    ["popstate", "pageshow", "htmx:historyRestore"].forEach(function (nom) {
        window.addEventListener(nom, tout_effacer);
    });

    document.body.addEventListener("htmx:beforeRequest", function (evenement) {
        var declencheur = evenement.detail.elt;
        // Les ecrans qui ont DEJA leur propre indicateur gardent le
        // leur : deux attentes pour une requete se contrediraient.
        // / Screens with their own indicator keep it.
        if (declencheur && declencheur.closest("[hx-indicator], [data-hx-indicator]")) {
            return;
        }

        var evenement_declencheur = evenement.detail.requestConfig &&
            evenement.detail.requestConfig.triggeringEvent;
        var vient_d_un_clic = !!evenement_declencheur &&
            /^(click|pointerdown|mousedown|submit)$/.test(evenement_declencheur.type);

        var spinner = null;
        var minuterie = window.setTimeout(function () {
            var point = ou_poser(declencheur, vient_d_un_clic);
            if (!point) { return; }
            spinner = document.createElement("span");
            spinner.className = "spinner-au-clic";
            // `aria-hidden` : les zones cibles portent deja
            // `aria-live="polite"` et annoncent le RESULTAT. Annoncer en
            // plus chaque attente rendrait la navigation au lecteur
            // d'ecran bavarde sans rien apprendre.
            // / Target zones already announce the result; announcing
            // every wait as well would only add noise.
            spinner.setAttribute("aria-hidden", "true");
            spinner.style.left = point.x + "px";
            spinner.style.top = point.y + "px";
            document.body.appendChild(spinner);
        }, DELAI_AVANT_AFFICHAGE);

        function retirer() {
            window.clearTimeout(minuterie);
            if (spinner && spinner.parentNode) {
                spinner.parentNode.removeChild(spinner);
            }
            spinner = null;
        }

        // ON RECONNAIT SA PROPRE REQUETE PAR SON `xhr`, jamais par
        // l'element : un meme bouton peut avoir deux requetes en vol, et
        // la premiere reponse retirerait alors le spinner de la seconde.
        // / Matched by its own xhr: one element can have two requests in
        // flight, and the first response would clear the second's spinner.
        var ma_requete = evenement.detail.xhr;

        // TROIS FINS POSSIBLES, ET IL FAUT LES TROIS. `afterRequest` ne
        // part pas quand la requete est annulee ni quand le reseau
        // tombe : sans les deux autres, un spinner resterait a tourner
        // sur la page, indefiniment.
        // / afterRequest does not fire on abort or network failure.
        ["htmx:afterRequest", "htmx:sendError", "htmx:sendAbort"].forEach(
            function (nom) {
                document.body.addEventListener(nom, function surveiller(fin) {
                    var la_mienne = ma_requete
                        ? fin.detail.xhr === ma_requete
                        : fin.detail.elt === declencheur;
                    if (!la_mienne) { return; }
                    document.body.removeEventListener(nom, surveiller);
                    retirer();
                });
            }
        );
    });
})();
