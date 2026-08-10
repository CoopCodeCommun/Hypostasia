/**
 * LES ANNONCES AUX LECTEURS D'ECRAN (dernier reste d'accessibilite de
 * la bascule CSS, 9 aout 2026).
 * LOCALISATION : front/static/front/js/annonces.js
 *
 * LE PROBLEME. L'application confirme ses actions par des toasts
 * SweetAlert (« Note supprimee », « Analyse lancee »…). SweetAlert pose
 * bien role=dialog et deplace le focus sur ses MODALES, mais un toast
 * n'est ni modal ni focalise : il apparait, vit trois secondes et
 * disparait, sans qu'aucun lecteur d'ecran ne le mentionne. Une
 * personne qui n'a pas les yeux sur l'ecran ne sait donc jamais si son
 * action a reussi. L'etalon de design n'a pas d'aria-live non plus —
 * c'est un point ou la bascule doit faire MIEUX que lui.
 *
 * LE CHOIX. On n'annonce pas depuis le toast lui-meme : une region live
 * creee en meme temps que son contenu n'est pas annoncee de facon
 * fiable. On ecrit dans une region PERSISTANTE, presente dans le DOM
 * des le rendu (#zone-annonces, base.html), que la technologie
 * d'assistance surveille depuis le debut.
 *
 * POURQUOI ENVELOPPER Swal.fire. Les appels sont disperses dans sept
 * fichiers (hypostasia, keyboard, arbre_overlay, arbre_context_menu,
 * drawer_vue_liste, dashboard_consensus, alignement). Les modifier un a
 * un aurait laisse le prochain appel ecrit ailleurs sans annonce. Ici,
 * un seul point d'entree couvre l'existant ET le futur.
 *
 * Les MODALES sont volontairement exclues : SweetAlert les annonce deja
 * (role=dialog + focus). Les annoncer en plus ferait un doublon.
 *
 * / Screen-reader announcements for SweetAlert toasts. Toasts are
 * neither modal nor focused, so nothing announces them. We write into
 * a PERSISTENT live region (created with the page, not with the toast)
 * and wrap Swal.fire once instead of touching seven call sites.
 */
(function () {
    "use strict";

    if (!window.Swal || typeof window.Swal.fire !== "function") { return; }

    /* La region est declaree dans base.html mais ce script vit dans le
       <head> : on la resout au moment de s'en servir, pas maintenant.
       / Resolve the region lazily: this script runs before the body. */
    function regionDAnnonce() {
        return document.getElementById("zone-annonces");
    }

    /**
     * Extrait le texte a annoncer, quelle que soit la forme de l'appel.
     * SweetAlert accepte un objet d'options ou la signature courte
     * (titre, texte, icone). / Handles both call signatures.
     */
    function texteDuToast(options, argumentsBruts) {
        if (typeof options === "string") {
            return [options, argumentsBruts[1]].filter(Boolean).join(". ");
        }
        if (!options || typeof options !== "object") { return ""; }
        var morceaux = [options.title, options.text].filter(function (morceau) {
            return typeof morceau === "string" && morceau.trim() !== "";
        });
        if (!morceaux.length && typeof options.html === "string") {
            /* Un html= peut contenir du balisage : on ne garde que le texte.
               / html= may contain markup; keep the text only. */
            var boite = document.createElement("div");
            boite.innerHTML = options.html;
            morceaux = [boite.textContent.trim()];
        }
        return morceaux.join(". ");
    }

    /**
     * Ecrit dans la region live. Le vidage prealable puis l'ecriture
     * differee sont necessaires : deux messages IDENTIQUES a la suite
     * (« Commentaire ajoute » deux fois) ne declenchent aucune nouvelle
     * annonce si le texte du noeud ne change pas.
     * / Clear then write on the next tick: an identical message would
     * otherwise not be re-announced.
     */
    function annoncer(texte) {
        var region = regionDAnnonce();
        if (!region || !texte) { return; }
        region.textContent = "";
        window.setTimeout(function () { region.textContent = texte; }, 50);
    }

    var fireOriginal = window.Swal.fire;

    window.Swal.fire = function (options) {
        try {
            /* Les modales sont deja annoncees par SweetAlert (role=dialog
               + focus) : seuls les toasts ont besoin de nous. */
            if (options && typeof options === "object" && options.toast === true) {
                annoncer(texteDuToast(options, arguments));
            }
        } catch (erreur) {
            /* Une annonce ratee ne doit jamais empecher le toast de
               s'afficher. / A failed announcement must never break the
               toast itself. */
        }
        return fireOriginal.apply(window.Swal, arguments);
    };

    /* Reutilisable ailleurs : les toasts WebSocket ou tout code qui
       voudrait annoncer sans passer par SweetAlert.
       / Exposed for any code that needs to announce without SweetAlert. */
    window.annoncerAuxLecteursDEcran = annoncer;
})();
