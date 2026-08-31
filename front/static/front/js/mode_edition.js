// ==========================================================================
// mode_edition.js — le mode d'edition par blocs (SPEC-edition-par-blocs)
// / Block editing mode
//
// LOCALISATION : front/static/front/js/mode_edition.js
//
// CE QUE CE MODE FAIT, ET CE QU'IL REFUSE DE FAIRE
//
// Il rend le texte de TOUS les blocs modifiable d'un coup, comme un seul
// document — mais les blocs restent des blocs. On edite leur TEXTE,
// jamais leur DECOUPAGE : ni fusion, ni scission (§ 3). C'est ce
// renoncement qui rend le mode tenable, et c'est lui qui desamorce le
// piege du `contenteditable` multi-enfants.
//
// LA CONFIGURATION EST CELLE QUE LE PROTOTYPE A EPROUVEE, sur trois
// moteurs (Chromium 145, Firefox 146, WebKit 26) :
//   1. `contenteditable="plaintext-only"` sur le conteneur ;
//   2. une garde sur `beforeinput`, AVEC repli sur la selection ;
//   3. une parade sur `compositionstart` ;
//   4. une pile d'annulation APPLICATIVE.
// Chacune couvre ce que les autres laissent passer. Les chiffres :
// CHANGELOG/2026-08-23-le-champ-unique-tranche-l-edition-par-blocs.md
//
// TROIS PIEGES MESURES, ET POURQUOI CHAQUE PIECE EST LA
//
// - `plaintext-only` N'EMPECHE PAS la fusion multi-blocs : 210 blocs
//   deviennent 205. La garde est donc obligatoire.
// - Une garde par `keydown` ne protege QUE les touches auxquelles on a
//   pense : taper une lettre sur une selection traversante, Ctrl+X, ou
//   Ctrl+A puis frapper detruisaient 5, 5 et 209 blocs. `beforeinput`
//   voit le GESTE, pas la touche.
// - `getTargetRanges()` rend une LISTE VIDE sous `plaintext-only` sur
//   Chromium (pas sur Firefox ni WebKit). Une garde qui s'y fie seule y
//   est aveugle : d'ou le repli sur `window.getSelection()`.
//
// COMMUNICATION :
// Recoit : le clic sur #bouton-mode-edition -> basculerModeEdition()
// Appelle : POST /elements/corriger_en_lot/ (Ctrl+S)
// Exporte : window.modeEdition = { estOuvert, fermer, basculer }
// Appele par : keyboard.js:gererEscape() -> window.modeEdition.fermer()
// ==========================================================================
(function () {
    'use strict';

    // La borne de la pile. Une photo pese ~57 Ko sur 210 blocs : 100 pas
    // font ~5,5 Mo. Ce que la borne ecarte est COMPTE, jamais oublie.
    // / The stack cap: what it drops is counted.
    var BORNE_DE_LA_PILE = 100;
    // On ne photographie pas a chaque frappe — ce serait +3 ms sur les
    // 6 ms qu'une frappe coute deja a 210 blocs. On attend une pause :
    // un mot tape fait ainsi UN pas d'annulation.
    // / Coalesce typing: one word makes one undo step.
    var PAUSE_AVANT_PHOTO = 500;

    var pile = {passes: [], refaits: [], ecartees: 0, minuterie: null};
    var ilYADesModificationsEnAttente = false;
    var unEnvoiEstEnCours = false;

    // LES LABELS QUI NE SE RELISENT PAS. Pour l'instant : le tableau.
    //
    // Le `texte` d'un `table` est du markdown « pipe » ; ce qui s'affiche
    // est un vrai <table>, construit APRES le marquage des ancres. Aucun
    // chemin HTML -> markdown n'existe dans le depot : lire le tableau
    // rendu donne « CategorieArgument » la ou la base porte
    // « | Categorie | Argument | ». L'envoyer ECRASERAIT le tableau.
    //
    // Mesure du 30 aout 2026, sur cinq notes et 387 blocs : `table`
    // echoue 20 fois sur 20 ; `code`, `picture`, `caption`, `title`,
    // `section_header`, `list_item` et `text` bouclent TOUS exactement.
    // La liste ne contient donc que `table` — pas les « 58 elements non
    // textuels » qu'on pouvait croire concernes.
    //
    // La spec l'a tranche le 26 aout (§ 12) : lecture seule dans le mode.
    // / Only `table` fails the round trip: its text is pipe markdown and
    // the rendered <table> cannot be read back.
    var LABELS_EN_LECTURE_SEULE = ['table'];

    // =================================================================
    // LA TABLE DES RACCOURCIS (SPEC-edition-par-blocs § 4.4)
    //
    // « Les raccourcis sont une table, pas des touches en dur. » Trois
    // raisons, toutes payees ailleurs :
    //
    // 1. LES COLLISIONS SYSTEME. `Ctrl+Espace` — le premier candidat —
    //    est pris par le changement de methode de saisie sous
    //    Linux/GNOME (IBus) et par le selecteur de source de saisie
    //    sous macOS : il peut ne JAMAIS atteindre la page. Les touches
    //    F sont libres et ne se disputent rien avec un champ de saisie.
    //    On evite F1 (aide), F3 (recherche), F5 (rechargement),
    //    F6 (barre d'adresse), F11 (plein ecran) et F12 (outils).
    // 2. LA PEDALE. Un footswitch USB emet des codes media
    //    (`MediaPlayPause`, `MediaTrackPrevious`…) ou des touches
    //    F13-F15. Les reconnaitre coute une ligne par geste ; ne pas
    //    les reconnaitre exclut l'outil de metier de la stenotypie.
    // 3. LA TABLE SE LIT, DONC ELLE S'AFFICHE. L'aide rend CETTE table,
    //    jamais une liste recopiee qui divergerait au premier
    //    changement de touche.
    //
    // Chaque geste porte PLUSIEURS touches : la premiere est celle
    // qu'on montre, les suivantes sont des equivalents (pedale).
    // / The § 4.4 table: system collisions, the USB footswitch, and one
    // single source that the help screen renders as-is.
    // =================================================================
    var RACCOURCIS = {
        enregistrer: {
            touches: ['Control+s'],
            libelle: 'Ctrl+S',
            geste: 'Enregistrer',
        },
        annuler: {
            touches: ['Control+z'],
            libelle: 'Ctrl+Z',
            geste: 'Annuler le dernier geste',
        },
        retablir: {
            touches: ['Control+Shift+z', 'Control+y'],
            libelle: 'Ctrl+Maj+Z',
            geste: 'Rétablir',
        },
        sortir: {
            touches: ['Escape'],
            libelle: 'Échap',
            geste: 'Sortir du mode',
        },
        lireOuPause: {
            touches: ['F4', 'MediaPlayPause', 'F13'],
            libelle: 'F4',
            geste: 'Lire ou mettre en pause',
            son: true,
        },
        ecouterLeBloc: {
            touches: ['F2'],
            libelle: 'F2',
            geste: 'Écouter à partir du passage du curseur',
            son: true,
        },
        reculer: {
            touches: ['F7', 'MediaTrackPrevious', 'F14'],
            libelle: 'F7',
            // Le pas vient de `PAS_DE_TRANSPORT`, jamais d'un nombre
            // recopie ici : le changer ferait mentir le bandeau.
            // / The step comes from the constant, never from a copy.
            geste: 'Reculer de {pas} secondes',
            son: true,
        },
        avancer: {
            touches: ['F8', 'MediaTrackNext', 'F15'],
            libelle: 'F8',
            geste: 'Avancer de {pas} secondes',
            son: true,
        },
        ralentir: {
            touches: ['F9'],
            libelle: 'F9',
            geste: 'Ralentir la lecture',
            son: true,
        },
        accelerer: {
            touches: ['F10'],
            libelle: 'F10',
            geste: 'Accélérer la lecture',
            son: true,
        },
    };

    var PAS_DE_TRANSPORT = 5;

    /**
     * Rend la NOTATION d'un evenement clavier, telle que la table
     * l'ecrit. / Renders a key event the way the table spells it.
     *
     * `Control+Shift+z` : les modificateurs d'abord, dans un ordre
     * fixe, puis la touche. Sans ordre fixe, la meme frappe s'ecrirait
     * de deux facons et la table ne la retrouverait pas.
     */
    function notationDe(evenement) {
        var morceaux = [];
        if (evenement.ctrlKey || evenement.metaKey) morceaux.push('Control');
        if (evenement.shiftKey) morceaux.push('Shift');
        if (evenement.altKey) morceaux.push('Alt');
        var touche = evenement.key;
        // Les lettres se comparent en minuscules : `Ctrl+Maj+Z` arrive
        // avec `key === 'Z'`. / Letters compare lowercase.
        if (touche.length === 1) touche = touche.toLowerCase();
        morceaux.push(touche);
        return morceaux.join('+');
    }

    /**
     * Quel geste de la table cette frappe declenche-t-elle ?
     * / Which table gesture does this keystroke trigger?
     *
     * @return {string|null} le nom du geste, ou null
     */
    function gesteDeLaFrappe(evenement) {
        var notation = notationDe(evenement);
        var noms = Object.keys(RACCOURCIS);
        for (var i = 0; i < noms.length; i += 1) {
            if (RACCOURCIS[noms[i]].touches.indexOf(notation) !== -1) {
                return noms[i];
            }
        }
        return null;
    }

    function estEnLectureSeule(bloc) {
        return LABELS_EN_LECTURE_SEULE.indexOf(bloc.dataset.label) !== -1;
    }

    function zoneDeLecture() { return document.getElementById('zone-lecture'); }
    function conteneur() {
        return document.querySelector('[data-testid="blocs-elements"]');
    }
    function estOuvert() {
        var zone = zoneDeLecture();
        return !!(zone && zone.classList.contains('mode-edition'));
    }

    function annoncer(message) {
        var zone = document.getElementById('zone-annonces');
        if (zone) zone.textContent = message;
    }

    // ---------------------------------------------------------------
    // LIRE ET ECRIRE LE TEXTE D'UN BLOC
    // ---------------------------------------------------------------
    //
    // ON NE LIT JAMAIS `.corps.textContent`. Mesure du 26 aout sur la
    // vraie page : sur 189 blocs, cette lecture en rend ZERO d'exact —
    // elle emporte les blancs d'indentation du gabarit ET le mot
    // « corriger » des boutons d'action. Lire l'element interne, ses
    // boutons retires, en rend 189 sur 189.
    // / Never read .corps.textContent: 0/189 exact. Read the inner element.

    function elementDeTexte(bloc) {
        var corps = bloc.querySelector('.corps');
        return corps ? corps.querySelector('[data-element-id]') : null;
    }

    function texteDuBloc(bloc) {
        var interne = elementDeTexte(bloc);
        if (!interne) return null;
        var copie = interne.cloneNode(true);
        var actions = copie.querySelectorAll('.actions-element');
        for (var i = 0; i < actions.length; i += 1) actions[i].remove();
        return copie.textContent;
    }

    function ecrireLeTexteDuBloc(bloc, texte) {
        var interne = elementDeTexte(bloc);
        if (!interne) return;
        // Les boutons font partie de l'ECRAN, pas du texte : on les
        // remet apres avoir reecrit. / The buttons belong to the screen.
        var actions = interne.querySelector('.actions-element');
        interne.textContent = texte;
        if (actions) interne.appendChild(actions);
        // Le CSS ne peut pas voir qu'un bloc est vide : l'element
        // interne garde le <span> des boutons, meme cache, donc `:empty`
        // est toujours faux. On le DIT par un attribut.
        // / CSS cannot see it: the hidden buttons keep it non-empty.
        var bloc = interne.closest('.bloc');
        if (bloc) bloc.dataset.vide = (texte === '') ? 'oui' : 'non';
    }

    // TOUT SE RESOUT SUR L'ELEMENT INTERNE, JAMAIS SUR `.corps`.
    //
    // `.corps` contient l'element interne ET les blancs d'indentation du
    // gabarit. Un curseur pose a la fin de `.corps` est APRES le <p> :
    // ce qu'on y tape devient un noeud texte frere, hors du texte du
    // bloc — donc invisible a la serialisation, et perdu au Ctrl+S.
    // Mesure du 29 aout : « CORRIGE » tape ainsi n'arrivait jamais au
    // serveur, et le compte rendu annoncait « 0 modifie ».
    // / Everything resolves on the inner element, never on .corps: text
    // typed at the edge of .corps lands outside the block's text.

    function elementInterneDuNoeud(noeud) {
        var element = (noeud && noeud.nodeType === 3) ? noeud.parentElement : noeud;
        if (!element || !element.closest) return null;
        // Un point DANS les boutons d'action n'est pas du texte de bloc.
        // / A point inside the action buttons is not block text.
        if (element.closest('.actions-element')) return null;
        var interne = element.closest('[data-element-id]');
        if (interne) return interne;
        // LE POINT EST DANS LE BLOC MAIS A COTE DU TEXTE — dans `.corps`,
        // ou sur le `.bloc` lui-meme. `closest` REMONTE, il ne descend
        // pas : sans ce rattachement, un curseur pose a la fin de
        // `.corps` ne resout vers rien, la garde croit le geste « hors
        // de tout bloc », et la frappe est perdue (mesure du 29 aout :
        // « 0 blocs modifiés » alors qu'on venait d'ecrire).
        // / closest() walks UP: attach the point to this block's inner
        // element, or a caret at the end of .corps resolves to nothing.
        var bloc = element.closest('.bloc');
        return bloc ? elementDeTexte(bloc) : null;
    }

    function blocDuNoeud(noeud) {
        var interne = elementInterneDuNoeud(noeud);
        return interne ? interne.closest('.bloc') : null;
    }

    // Un point n'est utilisable QUE s'il est dans un noeud TEXTE a
    // l'interieur de l'element interne. Partout ailleurs, la garde doit
    // faire le geste elle-meme.
    // / A point is usable only inside a TEXT node of the inner element.
    function estDansLeTexteDuBloc(noeud) {
        return !!(noeud && noeud.nodeType === 3 && elementInterneDuNoeud(noeud));
    }

    function offsetDansLeTexte(interne, noeud, offset) {
        var plage = document.createRange();
        plage.selectNodeContents(interne);
        plage.setEnd(noeud, offset);
        return plage.toString().length;
    }

    function poserLeCurseur(interne, offsetVoulu) {
        var marcheur = document.createTreeWalker(interne, NodeFilter.SHOW_TEXT);
        var reste = offsetVoulu;
        var noeud = marcheur.nextNode();
        while (noeud) {
            if (noeud.parentElement
                && noeud.parentElement.closest('.actions-element')) {
                noeud = marcheur.nextNode();
                continue;
            }
            if (reste <= noeud.textContent.length) {
                var plage = document.createRange();
                plage.setStart(noeud, reste);
                plage.collapse(true);
                var selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(plage);
                return;
            }
            reste -= noeud.textContent.length;
            noeud = marcheur.nextNode();
        }
    }

    // ---------------------------------------------------------------
    // LA PILE D'ANNULATION (addendum A de la spec)
    // ---------------------------------------------------------------
    //
    // ELLE EST APPLICATIVE, ET ELLE L'EST ENTIEREMENT. La frappe
    // ordinaire passe nativement — donc dans la pile du navigateur —
    // mais tout geste traversant ecrit dans le DOM a la main, et cela
    // TUE la pile native : mesure, apres une interception Ctrl+Z ne rend
    // plus rien, ni le geste ni la frappe qui le precedait. Melanger les
    // deux rendrait l'ordre des annulations imprevisible.
    //
    // UNE PHOTO NE CONTIENT QUE DES TEXTES : le mode interdisant la
    // fusion et la scission, la liste des blocs est INVARIANTE. Il n'y a
    // aucune structure a restaurer.
    // / Application-level undo; a snapshot is a text map, nothing else.

    function photographier() {
        var textes = {};
        var blocs = conteneur() ? conteneur().querySelectorAll('.bloc') : [];
        for (var i = 0; i < blocs.length; i += 1) {
            var texte = texteDuBloc(blocs[i]);
            if (texte !== null) textes[blocs[i].dataset.element] = texte;
        }
        return {textes: textes, curseur: ouEstLeCurseur()};
    }

    function ouEstLeCurseur() {
        var selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) return null;
        var interne = elementInterneDuNoeud(selection.anchorNode);
        if (!interne) return null;
        var bloc = interne.closest('.bloc');
        if (!bloc) return null;
        return {
            bloc: bloc.dataset.element,
            offset: offsetDansLeTexte(interne, selection.anchorNode,
                                      selection.anchorOffset),
        };
    }

    function empiler(photo) {
        pile.passes.push(photo);
        // Toute photo neuve coupe la branche de retablissement — c'est
        // le comportement attendu partout.
        // / A new snapshot cuts the redo branch.
        pile.refaits.length = 0;
        while (pile.passes.length > BORNE_DE_LA_PILE) {
            pile.passes.shift();
            pile.ecartees += 1;
        }
    }

    function empilerAvantUnGeste() {
        clearTimeout(pile.minuterie);
        pile.minuterie = null;
        empiler(photographier());
    }

    function armerLaPhotoDeFrappe() {
        if (pile.minuterie !== null) return;
        var avant = photographier();
        pile.minuterie = setTimeout(function () {
            pile.minuterie = null;
            empiler(avant);
        }, PAUSE_AVANT_PHOTO);
    }

    function restaurer(photo) {
        var reecrits = 0;
        var blocs = conteneur().querySelectorAll('.bloc');
        for (var i = 0; i < blocs.length; i += 1) {
            var voulu = photo.textes[blocs[i].dataset.element];
            if (voulu === undefined) continue;
            if (texteDuBloc(blocs[i]) === voulu) continue;
            ecrireLeTexteDuBloc(blocs[i], voulu);
            reecrits += 1;
        }
        // Le curseur se restaure aussi : une annulation qui le laisse
        // ailleurs desoriente. / Restore the caret too.
        if (photo.curseur) {
            var bloc = conteneur().querySelector(
                '.bloc[data-element="' + photo.curseur.bloc + '"]');
            var interne = bloc ? elementDeTexte(bloc) : null;
            if (interne) poserLeCurseur(interne, photo.curseur.offset);
        }
        return reecrits;
    }

    function annuler() {
        // Une photo de frappe en attente doit etre prise AVANT d'annuler,
        // sinon la derniere frappe echappe a la pile.
        // / A pending typing snapshot must land first.
        if (pile.minuterie !== null) {
            clearTimeout(pile.minuterie);
            pile.minuterie = null;
        }
        if (!pile.passes.length) return 0;
        var courant = photographier();
        var reecrits = restaurer(pile.passes.pop());
        pile.refaits.push(courant);
        return reecrits;
    }

    function retablir() {
        if (!pile.refaits.length) return 0;
        var courant = photographier();
        var reecrits = restaurer(pile.refaits.pop());
        pile.passes.push(courant);
        return reecrits;
    }

    // ---------------------------------------------------------------
    // LA GARDE — sur `beforeinput`, jamais sur `keydown`
    // ---------------------------------------------------------------

    function viderLaPlageBlocParBloc(plage) {
        var interneDebut = elementInterneDuNoeud(plage.startContainer);
        var interneFin = elementInterneDuNoeud(plage.endContainer);
        var blocs = Array.prototype.slice.call(
            conteneur().querySelectorAll('.bloc'));
        var indexDebut = blocs.indexOf(interneDebut.closest('.bloc'));
        var indexFin = blocs.indexOf(interneFin.closest('.bloc'));
        var offsetDebut = offsetDansLeTexte(
            interneDebut, plage.startContainer, plage.startOffset);
        var offsetFin = offsetDansLeTexte(
            interneFin, plage.endContainer, plage.endOffset);
        // Chaque bloc perd EXACTEMENT la part de son texte qui etait
        // selectionnee. Les frontieres ne bougent pas.
        // / Each block loses exactly its selected part; borders hold.
        ecrireLeTexteDuBloc(blocs[indexDebut],
                            texteDuBloc(blocs[indexDebut]).slice(0, offsetDebut));
        for (var i = indexDebut + 1; i < indexFin; i += 1) {
            ecrireLeTexteDuBloc(blocs[i], '');
        }
        ecrireLeTexteDuBloc(blocs[indexFin],
                            texteDuBloc(blocs[indexFin]).slice(offsetFin));
        poserLeCurseur(interneDebut, offsetDebut);
    }

    function viderTousLesBlocsDeLaPlage(plage) {
        var vraie = document.createRange();
        vraie.setStart(plage.startContainer, plage.startOffset);
        vraie.setEnd(plage.endContainer, plage.endOffset);
        var blocs = conteneur().querySelectorAll('.bloc');
        var premier = null;
        for (var i = 0; i < blocs.length; i += 1) {
            var interne = elementDeTexte(blocs[i]);
            if (interne && vraie.intersectsNode(interne)) {
                if (!premier) premier = interne;
                ecrireLeTexteDuBloc(blocs[i], '');
            }
        }
        if (premier) poserLeCurseur(premier, 0);
    }

    // LES DEUX BORNES D'UNE PLAGE, RAMENEES A DES OFFSETS DE TEXTE.
    //
    // Une borne peut ne PAS etre dans le texte : le curseur pose a la
    // fin de `.corps`, ou une selection qui prend tout le contenu de
    // `.corps` d'un coup. On ne peut pas la ramener a une constante — la
    // mettre systematiquement a la fin faisait que « selectionner tout
    // le bloc puis Suppr » ne supprimait RIEN. On compare donc la
    // position de la plage a celle du texte.
    // / An out-of-text bound is resolved by comparing boundary points,
    // not by clamping to a constant: "select all then delete" did nothing.
    function offsetsDeLaPlage(plage, interne, contenu) {
        var plageDuTexte = document.createRange();
        plageDuTexte.selectNodeContents(interne);
        var debut;
        if (estDansLeTexteDuBloc(plage.startContainer)) {
            debut = offsetDansLeTexte(interne, plage.startContainer,
                                      plage.startOffset);
        } else {
            debut = (plage.compareBoundaryPoints(
                Range.START_TO_START, plageDuTexte) <= 0) ? 0 : contenu.length;
        }
        var fin;
        if (estDansLeTexteDuBloc(plage.endContainer)) {
            fin = offsetDansLeTexte(interne, plage.endContainer, plage.endOffset);
        } else {
            fin = (plage.compareBoundaryPoints(
                Range.END_TO_END, plageDuTexte) >= 0) ? contenu.length : 0;
        }
        if (fin < debut) { var t = debut; debut = fin; fin = t; }
        return {debut: debut, fin: fin};
    }

    // Vider une plage qui reste DANS UN SEUL bloc. Le chemin
    // `viderLaPlageBlocParBloc` suppose deux blocs distincts : applique
    // a un seul, sa seconde ecriture ecraserait la premiere et la tete
    // du bloc serait perdue.
    // / A range inside ONE block: the multi-block path would lose its head.
    function viderDansUnSeulBloc(plage) {
        var interne = elementInterneDuNoeud(plage.startContainer)
            || elementInterneDuNoeud(plage.endContainer);
        if (!interne) return;
        var bloc = interne.closest('.bloc');
        var contenu = texteDuBloc(bloc);
        var bornes = offsetsDeLaPlage(plage, interne, contenu);
        ecrireLeTexteDuBloc(
            bloc, contenu.slice(0, bornes.debut) + contenu.slice(bornes.fin));
        poserLeCurseur(interne, bornes.debut);
    }

    function insererDuTexte(texte) {
        var selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) return;
        var plage = selection.getRangeAt(0);
        var interne = elementInterneDuNoeud(plage.startContainer)
            || elementInterneDuNoeud(plage.endContainer);
        if (!interne) return;
        var bloc = interne.closest('.bloc');
        var contenu = texteDuBloc(bloc);
        var bornes = offsetsDeLaPlage(plage, interne, contenu);
        ecrireLeTexteDuBloc(
            bloc,
            contenu.slice(0, bornes.debut) + texte + contenu.slice(bornes.fin));
        poserLeCurseur(interne, bornes.debut + texte.length);
    }

    // COMBIEN DE GESTES ONT TOUCHE LE TEXTE. Ce n'est pas un compte a
    // afficher : c'est un TEMOIN, lu avant et apres un enregistrement.
    // Un lot part avec le texte tel qu'il etait au `Ctrl+S` ; ce qu'on
    // tape pendant son vol (0,3 a 1,2 s) n'y est PAS. Baisser le
    // drapeau au retour desarmerait alors la garde de sortie, et ces
    // frappes-la partiraient sans un mot.
    // / A witness, not a counter: keystrokes typed while the batch flies
    // are not in it, so the flag must not drop on its return.
    var gestesSurLeTexte = 0;

    function marquerCommeModifie() {
        ilYADesModificationsEnAttente = true;
        gestesSurLeTexte += 1;
        var zone = zoneDeLecture();
        if (zone) zone.classList.add('a-des-modifications');
    }

    function surBeforeInput(evenement) {
        if (!estOuvert()) return;
        var type = evenement.inputType;
        // `getTargetRanges()` rend une liste VIDE sous plaintext-only sur
        // Chromium : sans ce repli, la garde y est AVEUGLE et laisse
        // passer les gestes traversants. Mesure du 23 aout.
        // / Empty under plaintext-only on Chromium: fall back.
        var plages = evenement.getTargetRanges();
        if (!plages || !plages.length) {
            var selection = window.getSelection();
            plages = (selection && selection.rangeCount)
                ? [selection.getRangeAt(0)] : [];
        }
        var plage = plages.length ? plages[0] : null;
        var interneDebut = plage ? elementInterneDuNoeud(plage.startContainer) : null;
        var interneFin = plage ? elementInterneDuNoeud(plage.endContainer) : null;
        var traverse = interneDebut && interneFin && interneDebut !== interneFin;
        var horsDeTouteBloc = plage && (!interneDebut || !interneFin);
        // LES DEUX BORNES DOIVENT ETRE DANS DU TEXTE DE BLOC pour qu'on
        // laisse faire le navigateur. Sinon ce qu'il ecrirait tomberait
        // A COTE du texte — dans `.corps`, apres le <p> — et serait
        // perdu a l'enregistrement.
        // / Both ends must sit in block text, or the browser writes beside it.
        var bornesSaines = estDansLeTexteDuBloc(plage && plage.startContainer)
            && estDansLeTexteDuBloc(plage && plage.endContainer);

        // Entree n'ouvre JAMAIS un bloc : elle insere un \n dans le bloc.
        // / Enter never opens a block.
        if (type === 'insertParagraph' || type === 'insertLineBreak') {
            evenement.preventDefault();
            empilerAvantUnGeste();
            insererDuTexte('\n');
            marquerCommeModifie();
            return;
        }

        // Le geste ne traverse pas : on laisse faire. C'est ce qui garde
        // la frappe ordinaire native — donc son cout et son comportement.
        // / Non-traversing gestures pass natively.
        if (!traverse && !horsDeTouteBloc && bornesSaines) {
            if (type === 'deleteContentBackward' && plage.collapsed
                && offsetDansLeTexte(interneDebut, plage.startContainer,
                                     plage.startOffset) === 0) {
                // En tete de bloc : rien. Pas de fusion.
                evenement.preventDefault();
                return;
            }
            armerLaPhotoDeFrappe();
            marquerCommeModifie();
            return;
        }

        // Le geste TRAVERSE : on le fait nous-memes, bloc par bloc.
        if (!evenement.cancelable) {
            // `insertCompositionText` n'est pas annulable. La parade
            // vit sur `compositionstart`, ci-dessous.
            // / Not cancelable: the workaround lives in compositionstart.
            return;
        }
        evenement.preventDefault();
        empilerAvantUnGeste();
        marquerCommeModifie();
        var donnees = evenement.data
            || (evenement.dataTransfer
                && evenement.dataTransfer.getData('text/plain'))
            || '';
        if (horsDeTouteBloc) {
            viderTousLesBlocsDeLaPlage(plage);
        } else if (traverse) {
            viderLaPlageBlocParBloc(plage);
        } else {
            // Meme bloc, mais une borne hors du texte : on fait le geste
            // nous-memes pour que ce qu'on ecrit atterrisse DANS le
            // texte du bloc, jamais a cote.
            // / Same block, unsound bound: do it ourselves.
            viderDansUnSeulBloc(plage);
        }
        if (donnees) insererDuTexte(donnees);
    }

    // LA PARADE A LA COMPOSITION IME.
    //
    // `insertCompositionText` arrive avec `cancelable: false` : la garde
    // le VOIT passer et ne peut rien en faire. Une composition qui
    // remplace une selection multi-blocs detruit donc des blocs — 210
    // deviennent 205, mesure. Sur Android, TOUTE frappe est une
    // composition.
    //
    // On ne combat pas la composition : on lui RETIRE SA MATIERE.
    // `compositionstart` arrive AVANT toute ecriture, et la selection y
    // est encore celle de l'utilisateur.
    // / Don't fight the composition: take away what it would destroy.
    function surCompositionStart() {
        if (!estOuvert()) return;
        var selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) return;
        var plage = selection.getRangeAt(0);
        var interneDebut = elementInterneDuNoeud(plage.startContainer);
        var interneFin = elementInterneDuNoeud(plage.endContainer);
        if (!interneDebut || !interneFin || interneDebut === interneFin) return;
        empilerAvantUnGeste();
        marquerCommeModifie();
        viderLaPlageBlocParBloc(plage);
    }

    // ---------------------------------------------------------------
    // L'ENREGISTREMENT (Ctrl+S)
    // ---------------------------------------------------------------

    /**
     * SIGNALE LES BLOCS REFUSES, LA OU ILS SONT.
     *
     * Le compte rendu du § 7.4 les NOMME par leur identifiant — mais un
     * identifiant ne dit pas OU regarder, et le compte rendu s'affiche
     * en tete de la note : sur une note longue, on ne le voit meme pas.
     *
     * Le defaut a ete constate en usage : deux corrections, une passee
     * et une refusee (le passage etait cite par une synthese figee), et
     * l'impression que « la sauvegarde ne marche pas » — alors que la
     * moitie du travail etait bien enregistree.
     *
     * On marque donc le bloc, on l'amene a l'ecran, et on rappelle que
     * le texte refuse est TOUJOURS LA : rien n'a ete perdu.
     * / An id does not say WHERE to look, and the report sits off-screen.
     *
     * :return: les identifiants refuses.
     */
    function marquerLesBlocsRefuses(accueil) {
        var champ = conteneur();
        if (champ) {
            var anciens = champ.querySelectorAll('.bloc.a-ete-refuse');
            for (var i = 0; i < anciens.length; i += 1) {
                anciens[i].classList.remove('a-ete-refuse');
            }
        }
        if (!accueil || !champ) return [];
        var lignes = accueil.querySelectorAll('[data-testid^="refus-"]');
        var identifiants = [];
        var premier = null;
        for (var j = 0; j < lignes.length; j += 1) {
            var identifiant = lignes[j].getAttribute('data-testid')
                .replace('refus-', '');
            identifiants.push(identifiant);
            var bloc = champ.querySelector(
                '.bloc[data-element="' + identifiant + '"]');
            if (bloc) {
                bloc.classList.add('a-ete-refuse');
                if (!premier) premier = bloc;
            }
        }
        // On amene le PREMIER refus a l'ecran : c'est ce que l'on doit
        // aller retaper. / Bring the first refusal into view.
        if (premier && premier.scrollIntoView) {
            premier.scrollIntoView({block: 'center', behavior: 'smooth'});
        }
        return identifiants;
    }

    /**
     * DIT LES REFUS DANS UNE MODALE, parce qu'une ligne ne suffit pas.
     *
     * Le compte rendu s'affiche EN TETE de la note : quand on edite plus
     * bas, on ne le voit pas. Constate en usage : deux corrections, une
     * passee, une refusee (le passage etait cite par une synthese
     * figee) — et l'impression que « la sauvegarde ne marche pas »,
     * alors que la moitie du travail etait bien enregistree.
     *
     * Une modale ARRETE le regard. `annonces.js` enveloppe `Swal.fire`,
     * donc elle est aussi annoncee aux lecteurs d'ecran.
     * / A line above the text is not seen; a modal stops the eye.
     */
    function direLesRefus(accueil, refuses) {
        var motifs = [];
        var lignes = accueil.querySelectorAll('[data-testid^="refus-"]');
        for (var i = 0; i < lignes.length; i += 1) {
            var texte = lignes[i].textContent.replace(/\s+/g, ' ').trim();
            // La ligne vaut « <identifiant> — <motif> » : l'identifiant
            // ne dit rien a personne, on ne garde que le motif.
            // / The id means nothing to a human: keep the reason.
            var separateur = texte.indexOf('—');
            motifs.push(separateur > -1
                ? texte.slice(separateur + 1).trim() : texte);
        }
        var uniques = motifs.filter(function (m, i) {
            return motifs.indexOf(m) === i;
        });
        var message = refuses.length + ' passage'
            + (refuses.length > 1 ? 's n\'ont' : ' n\'a')
            + ' pas pu être enregistré' + (refuses.length > 1 ? 's' : '')
            + '. Votre texte est toujours à l\'écran, et '
            + (refuses.length > 1 ? 'ils sont signalés' : 'il est signalé')
            + ' en rouge dans la note.';
        annoncer(message);
        if (!window.Swal || typeof window.Swal.fire !== 'function') return;
        // LE CORPS DE LA MODALE SE CONSTRUIT EN DOM, JAMAIS EN CHAINE.
        //
        // Un motif de refus porte le TITRE de la synthese qui bloque, et
        // ce titre est saisi par un humain. Concatene dans du HTML, un
        // titre comme « <img src=x onerror=...> » s'executerait ici : le
        // serveur l'echappe pour la page, mais `textContent` le rend
        // DECODE, et le reinjecter en `html` le rendrait actif.
        // `Swal.fire` accepte un element : on le lui donne.
        // / A refusal reason carries a human-written synthesis title:
        // build the modal body as DOM nodes, never by string concat.
        var corpsDeLaModale = document.createElement('div');
        corpsDeLaModale.style.textAlign = 'left';
        var paragraphe = document.createElement('p');
        paragraphe.textContent = message;
        corpsDeLaModale.appendChild(paragraphe);
        var listeDesMotifs = document.createElement('ul');
        listeDesMotifs.style.marginTop = '.75rem';
        for (var k = 0; k < uniques.length; k += 1) {
            var ligneDuMotif = document.createElement('li');
            ligneDuMotif.textContent = uniques[k];
            listeDesMotifs.appendChild(ligneDuMotif);
        }
        corpsDeLaModale.appendChild(listeDesMotifs);
        window.Swal.fire({
            icon: 'warning',
            title: refuses.length > 1
                ? refuses.length + ' passages refusés' : 'Un passage refusé',
            html: corpsDeLaModale,
            confirmButtonText: 'Aller au premier',
        }).then(function () {
            var champ = conteneur();
            var premier = champ
                ? champ.querySelector('.bloc.a-ete-refuse') : null;
            if (premier && premier.scrollIntoView) {
                premier.scrollIntoView({block: 'center', behavior: 'smooth'});
            }
        });
    }

    /**
     * REDEMANDE AU SERVEUR LE PANNEAU DES PASSAGES MASQUES.
     *
     * LOCALISATION : front/static/front/js/mode_edition.js
     *
     * POURQUOI IL FAUT LE REDEMANDER, ET NE PAS LE RECALCULER ICI
     *
     * Le mode MASQUE des blocs pendant la session : un bloc vide est
     * masque a l'enregistrement. Le panneau rendu au chargement de la
     * page ne les connait pas. Le reconstruire en JavaScript
     * demanderait de recopier ce que le serveur sait deja — le texte
     * conserve du bloc, son ordre, le pluriel du compte —, et cette
     * copie divergerait.
     *
     * IL REPARE AUSSI LA LIGNE PERIMEE : un passage demasque ailleurs
     * (mode structure, ou un tiers) laissait une ligne dont le
     * « retablir » aurait fait revenir la version EN BASE du bloc,
     * ecrasant ce qui etait en train d'etre tape.
     *
     * Un echec ne casse rien : le panneau reste ce qu'il etait. C'est un
     * confort, jamais le chemin d'une ecriture.
     * / Ask the server for the panel; never rebuild it here.
     */
    function rafraichirLePanneauDesMasques() {
        var accueil = document.getElementById('accueil-du-panneau-des-masques');
        if (!accueil) return;
        var note = accueil.getAttribute('data-page');
        if (!note) return;
        // L'ETAT DU PLI SE CONSERVE. Le serveur rend un panneau ferme ;
        // le remplacer tel quel refermerait sous les doigts celui qu'on
        // venait d'ouvrir — mesure du 30 aout : le bouton « retablir »
        // devenait injoignable juste apres un enregistrement.
        // / Keep the open/closed state: the server always renders it
        // closed, and it would snap shut right after a save.
        var ancien = document.getElementById('panneau-des-passages-masques');
        var etaitOuvert = !!(ancien && ancien.open);
        fetch('/elements/panneau_des_masques/?page=' + encodeURIComponent(note), {
            headers: {'X-Requested-With': 'XMLHttpRequest'},
        }).then(function (reponse) {
            return reponse.ok ? reponse.text() : null;
        }).then(function (html) {
            if (html === null) return;
            accueil.innerHTML = html;
            // HTMX NE VOIT PAS CE QU'IL N'A PAS INSERE LUI-MEME.
            //
            // Les boutons « retablir » portent `hx-post` : poses par un
            // `innerHTML` a la main, ils sont INERTES — le clic ne part
            // pas, et rien ne le signale. Mesure du 30 aout : apres un
            // enregistrement, aucun retablissement ne fonctionnait plus.
            // `htmx.process` arme le fragment neuf.
            // / htmx does not scan what it did not insert: hx-post on a
            // hand-injected fragment is inert until htmx.process().
            if (window.htmx && typeof window.htmx.process === 'function') {
                window.htmx.process(accueil);
            }
            var neuf = document.getElementById('panneau-des-passages-masques');
            if (neuf && etaitOuvert) neuf.open = true;
        }).catch(function () {
            // Le panneau reste ce qu'il etait : rien a dire.
            // / The panel stays as it was.
        });
    }

    /**
     * DECLENCHE LE TOAST QUE LA REPONSE PORTE DANS SON EN-TETE.
     *
     * LOCALISATION : front/static/front/js/mode_edition.js
     *
     * `corriger_en_lot` pose `HX-Trigger: {"showToast": {...}}`, comme
     * toutes les vues du projet. Mais son seul appelant est un
     * `fetch()` : htmx ne voit pas cette reponse, donc l'en-tete
     * n'atteignait personne — un resume ecrit cote serveur, jamais
     * affiche.
     *
     * On rejoue donc l'evenement que htmx aurait emis. `hypostasia.js`
     * l'ecoute sur `document.body` et rend le toast, avec
     * l'echappement qui va avec (`titleText`).
     * / Replay the event htmx would have fired; hypostasia.js listens.
     *
     * @param {string|null} enTete - la valeur brute de `HX-Trigger`
     */
    function faireVivreLeToast(enTete) {
        if (!enTete) return;
        var declencheurs;
        try {
            declencheurs = JSON.parse(enTete);
        } catch (erreur) {
            // Un en-tete illisible n'est pas une raison de perdre
            // l'enregistrement qui, lui, a reussi.
            // / An unreadable header is no reason to lose a good save.
            return;
        }
        if (!declencheurs) return;
        // TOUS LES DECLENCHEURS, pas seulement le toast. La reponse pose
        // aussi `tachesChanged`, que `hypostasia.js` ecoute pour
        // rafraichir le bouton des taches. N'en rejouer qu'un laissait
        // l'autre mort — et un en-tete a moitie honore est pire qu'un
        // en-tete ignore : on ne sait plus lequel des deux vaut.
        // / Replay every trigger: honouring half a header is worse than
        // ignoring it.
        var noms = Object.keys(declencheurs);
        for (var i = 0; i < noms.length; i += 1) {
            document.body.dispatchEvent(new CustomEvent(noms[i], {
                detail: declencheurs[noms[i]],
            }));
        }
    }

    function jetonCsrf() {
        var brut = document.body.getAttribute('hx-headers');
        if (!brut) return '';
        try { return JSON.parse(brut)['X-CSRFToken']; } catch (e) { return ''; }
    }

    function serialiser() {
        var charge = [];
        var blocs = conteneur().querySelectorAll('.bloc[data-element]');
        for (var i = 0; i < blocs.length; i += 1) {
            // UN BLOC EN LECTURE SEULE N'EST JAMAIS ENVOYE.
            //
            // Ce qu'on lirait de lui differe TOUJOURS de ce que porte la
            // base : le serveur le verrait « modifie » et l'ecraserait,
            // meme si personne n'y a touche.
            // / Never send a read-only block: the server would see it as
            // modified and overwrite it, untouched.
            if (estEnLectureSeule(blocs[i])) continue;
            var texte = texteDuBloc(blocs[i]);
            if (texte === null) continue;
            charge.push({
                identifiant_stable: blocs[i].dataset.element,
                texte: texte,
            });
        }
        return charge;
    }

    function enregistrer(ensuite) {
        // Ctrl+S est DESARME pendant l'envoi : deux lots qui se
        // chevauchent s'ecraseraient l'un l'autre.
        // / Disarmed while a save is in flight.
        if (unEnvoiEstEnCours) {
            annoncer('Enregistrement déjà en cours.');
            return;
        }
        var charge = serialiser();
        if (!charge.length) {
            // Une note qui n'a que des tableaux, par exemple : le mode
            // n'envoie rien, et se taire ferait croire a une panne. Un
            // geste qui ne fait rien sans un mot est pire que pas de
            // geste. / Saying nothing would read as a failure.
            annoncer("Aucun passage modifiable dans cette note.");
            return;
        }
        unEnvoiEstEnCours = true;
        var gestesAuDepart = gestesSurLeTexte;
        var zone = zoneDeLecture();
        if (zone) zone.classList.add('enregistrement-en-cours');
        // Un etat d'attente VISIBLE : le lot prend ~300 ms au plancher et
        // ~1,2 s pour une session ordinaire (mesure du 26 aout).
        // / A visible pending state.
        annoncer('Enregistrement en cours…');

        fetch('/elements/corriger_en_lot/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': jetonCsrf(),
            },
            body: JSON.stringify({blocs: charge}),
        }).then(function (reponse) {
            return reponse.text().then(function (corps) {
                return {
                    statut: reponse.status,
                    corps: corps,
                    // L'EN-TETE `HX-Trigger` PORTE LE RESUME, et personne
                    // ne le lisait : `fetch` ne declenche aucun evenement
                    // htmx. On le lit donc ici, et on le fait vivre.
                    // / fetch fires no htmx event: read the header here.
                    declencheurs: reponse.headers.get('HX-Trigger'),
                };
            });
        }).then(function (resultat) {
            unEnvoiEstEnCours = false;
            if (zone) zone.classList.remove('enregistrement-en-cours');
            var accueil = document.getElementById('compte-rendu-du-lot');
            if (resultat.statut === 200) {
                if (accueil) accueil.innerHTML = resultat.corps;
                var refuses = marquerLesBlocsRefuses(accueil);
                // LE DRAPEAU NE RETOMBE QUE SI TOUT EST PASSE.
                //
                // Un bloc refuse garde a l'ecran un texte qui n'est PAS
                // en base. Baisser le drapeau ferait sortir du mode sans
                // rien demander, et ce texte-la serait perdu — alors
                // qu'il est precisement celui qu'il faut retaper
                // ailleurs, ou renoncer sciemment.
                // La pile d'annulation, elle, est CONSERVEE dans tous
                // les cas : annuler apres un enregistrement redevient
                // une modification en attente.
                // / The flag drops only if everything went through: a
                // refused block still holds text that is not in the base.
                var ilYAEuDesFrappesPendantLEnvoi =
                    gestesSurLeTexte !== gestesAuDepart;
                if (!refuses.length && !ilYAEuDesFrappesPendantLEnvoi) {
                    ilYADesModificationsEnAttente = false;
                    if (zone) zone.classList.remove('a-des-modifications');
                    annoncer('Enregistré.');
                    // UN SUCCES DOIT SE VOIR, ET PAS SEULEMENT EN TETE
                    // DE NOTE.
                    //
                    // Le compte rendu s'affiche au-dessus du texte : en
                    // bas d'une note de 200 blocs, un `Ctrl+S` reussi
                    // n'avait aucun retour visible — l'annonce est
                    // `sr-only`, et la modale n'existe que pour les
                    // refus. Le toast, lui, est en haut a droite quel
                    // que soit le defilement.
                    //
                    // LE MESSAGE VIENT DU SERVEUR, tel quel : c'est lui
                    // qui compte les blocs. En composer un second ici
                    // ferait deux versions du meme resume, qui
                    // divergeraient au premier changement de libelle.
                    // / A success must be visible where the eye is: the
                    // toast. The wording stays the server's.
                    faireVivreLeToast(resultat.declencheurs);
                } else if (refuses.length) {
                    // LE RESUME D'ABORD : c'est le seul message qui dit
                    // que la moitie EST enregistree. La modale, elle, ne
                    // parle que de ce qui a ete refuse — et c'est
                    // exactement l'impression « la sauvegarde ne marche
                    // pas » qui a motive cette modale.
                    // / The summary says what DID go through; the modal
                    // only speaks of refusals.
                    faireVivreLeToast(resultat.declencheurs);
                    direLesRefus(accueil, refuses);
                } else {
                    // Tout est passe, mais on a tape PENDANT le vol : ce
                    // qui vient d'etre ecrit n'etait pas dans le lot. Le
                    // drapeau reste leve, et on le dit — sinon la sortie
                    // ne demanderait rien et ces frappes seraient
                    // perdues.
                    // / Everything went through, but new keystrokes came
                    // after the batch left: the flag stays up.
                    annoncer('Enregistré — mais ce que vous avez tapé '
                             + 'pendant l\'envoi ne l\'est pas encore.');
                }
                // Un bloc vide vient d'etre MASQUE : le panneau doit le
                // porter, sinon le geste que le mode vient de faire
                // resterait irreversible jusqu'au rechargement.
                // / A block was just hidden: the panel must show it.
                rafraichirLePanneauDesMasques();
                if (typeof ensuite === 'function') ensuite();
            } else {
                // Un refus ne recharge RIEN : le texte non enregistre
                // doit rester a l'ecran pour etre retape.
                // / A refusal reloads nothing: the text must stay.
                if (accueil) {
                    accueil.textContent =
                        "L'enregistrement a été refusé. Votre texte est "
                        + 'toujours là.';
                }
                annoncer("L'enregistrement a été refusé. Votre texte est "
                         + 'toujours là.');
                // ET LE MOTIF DU SERVEUR, QUI EST LE SEUL ACTIONNABLE.
                //
                // Un 409 porte « Une analyse est en cours sur cette
                // note… réessayez dans un instant » ; un 400, « cet
                // envoi mélange deux notes ». Ces messages ne vivent que
                // dans l'en-tete — le corps est vide. Sans ce rejeu, la
                // personne lit un refus generique et ne sait pas quoi
                // faire.
                // / The actionable reason lives in the header alone.
                faireVivreLeToast(resultat.declencheurs);
            }
        }).catch(function () {
            unEnvoiEstEnCours = false;
            if (zone) zone.classList.remove('enregistrement-en-cours');
            annoncer("L'enregistrement n'a pas abouti. Votre texte est "
                     + 'toujours là.');
        });
    }

    // ---------------------------------------------------------------
    // OUVRIR ET FERMER
    // ---------------------------------------------------------------

    // LES BLANCS DU GABARIT DOIVENT PARTIR AVANT D'OUVRIR LE CHAMP.
    //
    // `contenteditable="plaintext-only"` impose `white-space: pre-wrap`
    // a tout le champ, et AUCUN CSS d'auteur ne peut le contredire —
    // mesure du 30 aout : `white-space: normal !important` pose en ligne
    // reste calcule `pre-wrap`. Or `.corps` contient les blancs
    // d'indentation du gabarit Django. Jusque-la collapses, ils
    // deviennent de vraies lignes vides : un bloc passait de 24 px a
    // 197 px, et la note de 17 259 px a 154 062 px. Le mode etait
    // inutilisable, sans la moindre erreur.
    //
    // On les retire du DOM. Ils ne portent RIEN : ce sont les retours a
    // la ligne du gabarit, invisibles en lecture parce que le
    // `white-space` normal les collapse. Les retirer ne change donc
    // rien a la lecture — et cela supprime au passage le risque qu'ils
    // entrent dans une serialisation.
    // / The browser forces pre-wrap and CSS cannot fight it: remove the
    // template's whitespace-only text nodes from the DOM.
    function retirerLesBlancsDuGabarit(racine) {
        // ON PARCOURT TOUT LE CHAMP, depuis sa racine.
        //
        // Le gabarit indente a TROIS niveaux, et les trois comptent :
        // entre les `.bloc` (la boucle `{% for %}`), dans `.corps`, et
        // dans le `<ul>` d'une puce. Ne nettoyer que `.corps` laissait
        // les blancs INTER-BLOCS, et la note restait haute de 111 108 px
        // au lieu de 17 259 — mesure du 30 aout.
        // / The template indents at three levels, and all three count.
        var marcheur = document.createTreeWalker(racine, NodeFilter.SHOW_TEXT);
        var blancs = [];
        var noeud = marcheur.nextNode();
        while (noeud) {
            // ON NE TOUCHE JAMAIS AU TEXTE DU BLOC. Un blanc a
            // l'INTERIEUR de l'element interne appartient au texte —
            // c'est peut-etre le saut de ligne qu'on vient de taper.
            // / Whitespace INSIDE the inner element is the text itself.
            var dansLeTexte = noeud.parentElement
                && noeud.parentElement.closest('[data-element-id]');
            if (!dansLeTexte && !noeud.textContent.trim()) {
                blancs.push(noeud);
            }
            noeud = marcheur.nextNode();
        }
        for (var i = 0; i < blancs.length; i += 1) {
            blancs[i].remove();
        }
        return blancs.length;
    }

    /**
     * SORT DU CHAMP MODIFIABLE LES GOUTTIERES.
     *
     * Elles portent le REPERAGE — numero, locuteur, minutage —, pas le
     * texte. Une frappe qui y tombe est acceptee par le navigateur,
     * jamais serialisee (`texteDuBloc` ne lit que l'element interne), et
     * donc perdue au premier `Ctrl+S` : le pire des cas, un geste qui a
     * l'air de marcher et qui ne fait rien.
     *
     * APPELEE A L'OUVERTURE ET APRES CHAQUE SWAP, pour la meme raison
     * que `figerLesBlocsEnLectureSeule` : un bloc revenu par un swap
     * cible arrive avec le gabarit nu, gouttiere modifiable comprise.
     * / The gutters carry the landmarks, not the text: a keystroke there
     * is never serialized. Reapplied after every swap.
     */
    function sortirLesGouttieresDuChamp(champ) {
        var gouttieres = champ.querySelectorAll('.gouttiere, .filet-etat');
        for (var i = 0; i < gouttieres.length; i += 1) {
            gouttieres[i].setAttribute('contenteditable', 'false');
        }
    }

    /**
     * SORT DU CHAMP MODIFIABLE LES BLOCS QUI NE SE RELISENT PAS.
     *
     * On ne se contente pas de ne pas les envoyer : les laisser
     * modifiables ferait croire qu'on les corrige, et le travail serait
     * perdu au premier Ctrl+S. Un geste qui ne fait rien est pire que
     * pas de geste.
     *
     * APPELEE DEUX FOIS, et les deux comptent : a l'ouverture du mode,
     * et apres chaque swap htmx. Un bloc revenu par un swap cible — le
     * retablissement d'un passage masque, par exemple — arrive avec le
     * gabarit nu : sans ce second appel, un tableau retabli en pleine
     * session redeviendrait modifiable.
     * / Called on open AND after every swap: a block returning from a
     * targeted swap comes back with the bare template.
     */
    function figerLesBlocsEnLectureSeule(champ) {
        var blocsDuChamp = champ.querySelectorAll('.bloc[data-element]');
        for (var i = 0; i < blocsDuChamp.length; i += 1) {
            if (!estEnLectureSeule(blocsDuChamp[i])) continue;
            blocsDuChamp[i].dataset.lectureSeule = 'oui';
            var corpsFige = blocsDuChamp[i].querySelector('.corps');
            if (corpsFige) corpsFige.setAttribute('contenteditable', 'false');
        }
    }

    function ouvrir() {
        var zone = zoneDeLecture();
        var champ = conteneur();
        if (!zone || !champ) return false;
        // AVANT toute chose : les blancs du gabarit, sinon le champ
        // s'ouvre avec des lignes vides partout.
        // / Before anything: strip the template whitespace.
        retirerLesBlancsDuGabarit(champ);
        zone.classList.add('mode-edition');
        // LE MODE EST SEUL A L'ECRAN.
        //
        // Le panneau d'analyses et le drawer vivent HORS de
        // `#zone-lecture` : aucune regle partant de lui ne les atteint.
        // On marque donc le `body`, et le CSS les retire de la vue.
        // Editer, c'est regarder le texte — pas ce qu'on en a extrait.
        // / The panel and drawer live outside #zone-lecture: mark body.
        document.body.classList.add('en-mode-edition');
        if (window.drawerVueListe && window.drawerVueListe.estOuvert
            && window.drawerVueListe.estOuvert()) {
            window.drawerVueListe.fermer();
        }
        // `plaintext-only` tient le collage NON traversant, que la garde
        // laisse passer par construction. Les trois moteurs l'acceptent.
        // / plaintext-only handles the non-traversing paste.
        champ.setAttribute('contenteditable', 'plaintext-only');
        sortirLesGouttieresDuChamp(champ);
        figerLesBlocsEnLectureSeule(champ);
        composerLeBandeau(champ);
        champ.setAttribute('role', 'textbox');
        champ.setAttribute('aria-multiline', 'true');
        champ.setAttribute('aria-label',
            'Texte de la note, modifiable passage par passage');
        pile.passes.length = 0;
        pile.refaits.length = 0;
        pile.ecartees = 0;
        ilYADesModificationsEnAttente = false;
        champ.focus();
        // Le curseur se pose DANS le texte du premier bloc. Sans cela il
        // reste ou le clic l'a laisse — souvent hors de l'element
        // interne, la ou une frappe tomberait a cote du texte.
        // / Place the caret inside the first block's text.
        var premier = champ.querySelector('.bloc');
        var interne = premier ? elementDeTexte(premier) : null;
        if (interne) poserLeCurseur(interne, 0);
        annoncer('Mode édition ouvert. Ctrl+S enregistre, Échap sort.');
        return true;
    }

    function fermer(sansDemander) {
        var zone = zoneDeLecture();
        var champ = conteneur();
        if (!zone || !zone.classList.contains('mode-edition')) return false;

        // ON NE SORT PAS SUR DU TRAVAIL NON ENREGISTRE.
        //
        // Le mode ne garde rien : sortir avec des modifications en
        // attente les perd, et le simple fait de recharger la note
        // suffirait a les effacer. On demande donc — et tant qu'on n'a
        // pas repondu, LE MODE RESTE OUVERT.
        // / Leaving with unsaved work would lose it: ask first.
        if (ilYADesModificationsEnAttente && !sansDemander) {
            demanderQuoiFaireDesModifications();
            return true;   // la touche EST traitee : la cascade s'arrete
        }

        zone.classList.remove('mode-edition');
        document.body.classList.remove('en-mode-edition');
        if (champ) {
            var figes = champ.querySelectorAll('.bloc[data-lecture-seule]');
            for (var k = 0; k < figes.length; k += 1) {
                delete figes[k].dataset.lectureSeule;
                var corpsRendu = figes[k].querySelector('.corps');
                if (corpsRendu) corpsRendu.removeAttribute('contenteditable');
            }
            champ.removeAttribute('contenteditable');
            champ.removeAttribute('role');
            champ.removeAttribute('aria-multiline');
            champ.removeAttribute('aria-label');
        }
        var bouton = document.getElementById('bouton-mode-edition');
        if (bouton) {
            bouton.setAttribute('aria-pressed', 'false');
            // Rendre le focus au bouton : sans cela il reste dans une
            // zone qui n'est plus modifiable.
            // / Return the focus to the button.
            bouton.focus();
        }
        annoncer(ilYADesModificationsEnAttente
            ? 'Mode édition fermé. Des modifications ne sont PAS enregistrées.'
            : 'Mode édition fermé.');
        return true;
    }

    /**
     * Trois issues, et aucune ne perd le texte en silence.
     * / Three ways out, none of them silent.
     */
    function demanderQuoiFaireDesModifications() {
        annoncer('Des modifications ne sont pas enregistrées.');
        if (!window.Swal || typeof window.Swal.fire !== 'function') {
            // Sans SweetAlert, on ne sort pas en silence pour autant.
            // / Without SweetAlert, still do not leave silently.
            if (window.confirm('Des modifications ne sont pas enregistrées. '
                               + 'Sortir quand même ?')) {
                fermer(true);
            }
            return;
        }
        window.Swal.fire({
            icon: 'question',
            title: 'Des modifications ne sont pas enregistrées',
            text: 'Que voulez-vous en faire ?',
            showDenyButton: true,
            showCancelButton: true,
            confirmButtonText: 'Enregistrer et sortir',
            denyButtonText: 'Sortir sans enregistrer',
            cancelButtonText: 'Rester',
        }).then(function (choix) {
            if (choix.isConfirmed) {
                // On ne sort QUE si l'enregistrement a tout fait passer.
                // Sinon on reste, et la modale des refus prend le relais.
                // / Leave only if everything went through.
                enregistrer(function () {
                    if (!ilYADesModificationsEnAttente) fermer(true);
                });
            } else if (choix.isDenied) {
                fermer(true);
            }
            // « Rester » : on ne fait rien, le mode reste ouvert.
        });
    }

    /**
     * ECOUTE A PARTIR DU PASSAGE OU EST LE CURSEUR.
     *
     * LOCALISATION : front/static/front/js/mode_edition.js
     *
     * C'est le geste central de la stenotypie : on lit une phrase mal
     * transcrite, on veut l'entendre. Sans lui, il faut lacher le
     * clavier, viser le bouton « écouter » du bon bloc a la souris,
     * puis revenir — trois gestes pour une correction qui en vaut un.
     *
     * LE MINUTAGE EST DEJA DANS LE DOM : chaque bloc porte `data-debut`
     * (`_un_bloc_element.html`). On ne recalcule rien, on ne demande
     * rien au serveur — et l'ECOUTE elle-meme passe par l'API du
     * lecteur, jamais par l'element <audio> en direct.
     * / The turn's timestamp is already on the block; the listening
     * goes through the player's API, never the raw audio element.
     */
    /**
     * COMPOSE LE BANDEAU DU MODE DEPUIS LA TABLE DES RACCOURCIS.
     *
     * LOCALISATION : front/static/front/js/mode_edition.js
     *
     * Le bandeau annoncait ses touches en dur, dans le `content:` d'une
     * regle CSS — une recopie de la table, qui aurait menti au premier
     * changement de touche. Le CSS lit maintenant `attr(data-bandeau)`,
     * et c'est la table qui l'ecrit.
     *
     * LES TOUCHES DE SON N'APPARAISSENT QUE S'IL Y A DU SON : sur une
     * note ecrite, annoncer « F4 lit » promettrait un geste qui ne fait
     * rien. / Sound keys appear only when there is sound.
     */
    function composerLeBandeau(champ) {
        var lecteur = window.lecteurAudio;
        var ilYADuSon = !!(lecteur && lecteur.estDisponible());
        var gestes = ['enregistrer', 'annuler', 'sortir'];
        if (ilYADuSon) gestes = gestes.concat(['lireOuPause', 'ecouterLeBloc']);
        var morceaux = [];
        for (var i = 0; i < gestes.length; i += 1) {
            var raccourci = RACCOURCIS[gestes[i]];
            var dit = raccourci.geste.replace('{pas}', PAS_DE_TRANSPORT);
            morceaux.push(raccourci.libelle + ' ' + dit.toLowerCase());
        }
        champ.dataset.bandeau = 'Mode édition — ' + morceaux.join(' · ');
    }

    function ecouterLeBlocDuCurseur() {
        var selection = window.getSelection();
        if (!selection || !selection.rangeCount) {
            annoncer('Placez le curseur dans un passage.');
            return;
        }
        var bloc = blocDuNoeud(selection.getRangeAt(0).startContainer);
        if (!bloc) {
            annoncer('Placez le curseur dans un passage.');
            return;
        }
        var debut = parseFloat(bloc.dataset.debut);
        if (!isFinite(debut)) {
            // Un bloc sans minutage : une note ecrite, ou un passage
            // ajoute apres coup. On le DIT — un geste qui ne fait rien
            // sans un mot est pire que pas de geste.
            // / A block without a timestamp says so.
            annoncer("Ce passage n'a pas de minutage.");
            return;
        }
        window.lecteurAudio.ecouterDepuis(debut);
        annoncer('Lecture du passage.');
    }

    function basculer(bouton) {
        var actif;
        if (estOuvert()) {
            fermer();
            actif = false;
        } else {
            actif = ouvrir();
        }
        if (bouton) bouton.setAttribute('aria-pressed', actif ? 'true' : 'false');
    }

    // ---------------------------------------------------------------
    // LE BRANCHEMENT
    // ---------------------------------------------------------------

    // Delegue sur `document` : la zone de lecture est remplacee par HTMX
    // a chaque rechargement, un ecouteur pose dessus disparaitrait avec
    // elle. / Delegated: the reading zone is swapped by HTMX.
    document.addEventListener('beforeinput', surBeforeInput, true);
    document.addEventListener('compositionstart', surCompositionStart, true);

    // Le glisser-deposer est REFUSE A LA SOURCE : au moment du depot, la
    // selection est encore celle de l'origine, et le « traiter »
    // insererait au mauvais endroit (mesure du 23 aout).
    // / Dragging is refused at the source.
    document.addEventListener('dragstart', function (evenement) {
        if (estOuvert()) evenement.preventDefault();
    }, true);

    // Ctrl+S, Ctrl+Z, Ctrl+Maj+Z. `keyboard.js` ignore tout ce qui porte
    // Ctrl (sa ligne 392) : ces trois-la ne l'atteindraient jamais, d'ou
    // cet ecouteur — le SEUL de ce fichier, et il ne touche PAS a Echap,
    // qui appartient a la cascade.
    // / keyboard.js ignores anything with Ctrl; Escape stays in the cascade.
    /**
     * LE CLAVIER DU MODE — tout passe par la table du § 4.4.
     *
     * LOCALISATION : front/static/front/js/mode_edition.js
     *
     * `Échap` n'est PAS traite ici : il vit dans la cascade de
     * `keyboard.js`, au rang 4.6, parce que sa PLACE compte — tout ce
     * qui s'ouvre par-dessus le mode se ferme d'abord. Un second
     * ecouteur `Échap` ferait fermer deux choses d'un coup, ce qui a
     * deja ete paye ici le 29 aout.
     * / Escape lives in keyboard.js's cascade: its RANK matters.
     */
    document.addEventListener('keydown', function (evenement) {
        if (!estOuvert()) return;
        var geste = gesteDeLaFrappe(evenement);
        if (!geste || geste === 'sortir') return;

        // LES GESTES DE TEXTE EXIGENT LE FOCUS DANS LE CHAMP.
        //
        // Le mode reste « ouvert » alors que le focus peut etre
        // ailleurs : dans le menu du recul a la reprise, sur le rail du
        // lecteur (`tabindex="0"`), sur un bouton du panneau des
        // masques, dans une modale. Un `Ctrl+Z` frappe la annulait le
        // texte de la note DERRIERE, sans que rien ne le montre.
        //
        // Les gestes de SON, eux, restent atteignables de partout :
        // regler la vitesse puis reprendre l'ecoute sans revenir au
        // texte est precisement l'usage.
        // / Text gestures require focus inside the field; sound gestures
        // stay reachable from anywhere in the page.
        var champ = conteneur();
        var focusDansLeChamp = !!(champ && champ.contains(document.activeElement));
        if (!RACCOURCIS[geste].son && !focusDansLeChamp) return;

        // LES GESTES DE SON NE FONT RIEN SANS SON. Sur une note ecrite,
        // `F4` doit garder son sens navigateur plutot que d'etre avale
        // par un mode qui n'a rien a en faire.
        // / Sound gestures do nothing without sound: don't swallow the key.
        var lecteur = window.lecteurAudio;
        if (RACCOURCIS[geste].son
            && !(lecteur && lecteur.estDisponible())) return;

        evenement.preventDefault();

        if (geste === 'enregistrer') {
            enregistrer();
            return;
        }
        if (geste === 'annuler') {
            // On intercepte TOUJOURS : melanger la pile native et la
            // notre rendrait l'ordre des annulations imprevisible.
            // / Always intercept: mixing the two stacks is unpredictable.
            var rendus = annuler();
            if (rendus) marquerCommeModifie();
            annoncer(rendus ? rendus + ' passage(s) rétabli(s).'
                            : 'Rien à annuler.');
            return;
        }
        if (geste === 'retablir') {
            var refaits = retablir();
            if (refaits) marquerCommeModifie();
            annoncer(refaits ? refaits + ' passage(s) rétabli(s).'
                             : 'Rien à rétablir.');
            return;
        }
        if (geste === 'lireOuPause') {
            annoncer(lecteur.lireOuPause() ? 'Lecture.' : 'Pause.');
            return;
        }
        if (geste === 'ecouterLeBloc') {
            ecouterLeBlocDuCurseur();
            return;
        }
        if (geste === 'reculer' || geste === 'avancer') {
            // ON ANNONCE CE QUI S'EST PASSE, pas ce qu'on a demande.
            // `decaler` rend faux quand la duree n'est pas connue —
            // media casse, metadonnees absentes : dire « recul de 5
            // secondes » serait alors faux, et ce genre de mensonge
            // rend l'annonce entiere inutile.
            // / Announce what happened, not what was asked.
            var sens = geste === 'avancer' ? 1 : -1;
            var aBouge = lecteur.decaler(sens * PAS_DE_TRANSPORT);
            if (!aBouge) {
                annoncer("L'enregistrement n'est pas prêt.");
                return;
            }
            annoncer((sens > 0 ? 'Avance de ' : 'Recul de ')
                     + PAS_DE_TRANSPORT + ' secondes.');
            return;
        }
        if (geste === 'ralentir' || geste === 'accelerer') {
            var facteur = lecteur.changerLaVitesse(
                geste === 'accelerer' ? 1 : -1);
            annoncer('Vitesse ' + String(facteur).replace('.', ',') + ' fois.');
        }
    });

    // Ne pas perdre ce qui n'est pas enregistre.
    // BORNE CONNUE : `beforeunload` ne couvre PAS les navigations HTMX
    // internes — d'ou le second garde, sur `htmx:beforeRequest`.
    // / beforeunload misses HTMX internal navigations: hence the second.
    window.addEventListener('beforeunload', function (evenement) {
        if (!estOuvert() || !ilYADesModificationsEnAttente) return;
        evenement.preventDefault();
        evenement.returnValue = '';
    });

    document.body.addEventListener('htmx:beforeRequest', function (evenement) {
        if (!estOuvert() || !ilYADesModificationsEnAttente) return;
        // On ne bloque QUE la navigation, jamais l'enregistrement.
        // / Block navigation only, never the save itself.
        var chemin = (evenement.detail && evenement.detail.pathInfo
                      && evenement.detail.pathInfo.requestPath) || '';
        if (chemin.indexOf('/elements/') === 0) return;
        if (!window.confirm(
            'Des modifications ne sont pas enregistrées. Quitter quand même ?')) {
            evenement.preventDefault();
        }
    });

    // UN BLOC ECHANGE PAR HTMX REVIENT AVEC SES BLANCS. Le swap cible
    // (`hx-swap-oob` d'une operation d'element) reinjecte le gabarit tel
    // quel : sans ce rattrapage, ce bloc-la seul redeviendrait haut de
    // 197 px au milieu des autres.
    // / A block swapped back by HTMX brings its whitespace along.
    document.body.addEventListener('htmx:afterSwap', function () {
        if (!estOuvert()) return;
        var champ = conteneur();
        if (!champ) return;
        retirerLesBlancsDuGabarit(champ);
        // Et le bloc revenu retrouve son regime ENTIER : gouttiere hors
        // du champ, et lecture seule si c'est un tableau. Sans ces deux
        // appels, un bloc retabli en pleine session revient modifiable
        // la ou il ne doit pas l'etre — et ce qu'on y taperait serait
        // perdu sans un mot.
        // / The returning block regains its FULL regime.
        sortirLesGouttieresDuChamp(champ);
        figerLesBlocsEnLectureSeule(champ);
    });

    /**
     * LE PANNEAU DES MASQUES SE MET A JOUR QUAND UN PASSAGE REVIENT.
     *
     * LOCALISATION : front/static/front/js/mode_edition.js
     *
     * Le bouton « retablir » du panneau poste
     * `/elements/<pk>/demasquer/`, et la reponse remplace LE BLOC dans
     * le texte (swap OOB, § 11.3). Le panneau, lui, n'est pas dans
     * cette reponse : sans ce rattrapage, sa ligne resterait et son
     * compte mentirait jusqu'au prochain chargement — on croirait avoir
     * encore des passages masques qui sont deja revenus.
     *
     * C'est de l'AFFICHAGE, pas du metier : le geste, son droit et son
     * ecriture sont entierement du cote serveur.
     *
     * FLUX : clic « retablir » -> htmx POST -> le serveur rend le bloc
     * en `hx-swap-oob` -> `htmx:afterSwap` le denettoie et le fige au
     * besoin -> CET ECOUTEUR retire la ligne et refait le compte.
     * / The OOB response replaces the block, never the panel: update it
     * here. Display only; the gesture itself is server-side.
     */
    document.body.addEventListener('htmx:afterRequest', function (evenement) {
        var bouton = evenement.target;
        if (!bouton || !bouton.closest) return;
        if (!bouton.closest('#panneau-des-passages-masques li')) return;
        // Un echec laisse le panneau tel quel : le passage est toujours
        // masque, et dire le contraire serait pire que se taire.
        // / A failure leaves the panel as it is.
        if (!evenement.detail || !evenement.detail.successful) return;
        // LE SERVEUR REND LA VERITE — compte, pluriel et ordre compris.
        // Retirer la ligne ici marcherait aussi, mais il faudrait alors
        // recalculer le compte cote client, et cette copie divergerait
        // du jour ou le gabarit changera.
        // / The server tells the truth; no client-side recount.
        annoncer('Passage rétabli.');
        rafraichirLePanneauDesMasques();
    });

    window.modeEdition = {
        estOuvert: estOuvert,
        fermer: fermer,
        basculer: basculer,
        // LA TABLE EST PUBLIQUE : l'aide la rend telle qu'elle est, et
        // ne recopie jamais une liste qui divergerait (§ 4.4).
        // / The table is public: the help screen renders it as-is.
        raccourcis: RACCOURCIS,
    };
})();

// Appele par l'attribut onclick du bouton (meme patron que le mode
// structure). / Called by the button's onclick, like the structure mode.
function basculerModeEdition(bouton) {
    if (window.modeEdition) window.modeEdition.basculer(bouton);
}
