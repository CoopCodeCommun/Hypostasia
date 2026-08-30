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

    function marquerCommeModifie() {
        ilYADesModificationsEnAttente = true;
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

    function jetonCsrf() {
        var brut = document.body.getAttribute('hx-headers');
        if (!brut) return '';
        try { return JSON.parse(brut)['X-CSRFToken']; } catch (e) { return ''; }
    }

    function serialiser() {
        var charge = [];
        var blocs = conteneur().querySelectorAll('.bloc[data-element]');
        for (var i = 0; i < blocs.length; i += 1) {
            var texte = texteDuBloc(blocs[i]);
            if (texte === null) continue;
            charge.push({
                identifiant_stable: blocs[i].dataset.element,
                texte: texte,
            });
        }
        return charge;
    }

    function enregistrer() {
        // Ctrl+S est DESARME pendant l'envoi : deux lots qui se
        // chevauchent s'ecraseraient l'un l'autre.
        // / Disarmed while a save is in flight.
        if (unEnvoiEstEnCours) {
            annoncer('Enregistrement déjà en cours.');
            return;
        }
        var charge = serialiser();
        if (!charge.length) return;
        unEnvoiEstEnCours = true;
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
                return {statut: reponse.status, corps: corps};
            });
        }).then(function (resultat) {
            unEnvoiEstEnCours = false;
            if (zone) zone.classList.remove('enregistrement-en-cours');
            var accueil = document.getElementById('compte-rendu-du-lot');
            if (resultat.statut === 200) {
                // La pile d'annulation est CONSERVEE : seul le drapeau
                // retombe. Annuler apres avoir enregistre redevient une
                // modification en attente.
                // / The stack is kept; only the dirty flag drops.
                ilYADesModificationsEnAttente = false;
                if (zone) zone.classList.remove('a-des-modifications');
                if (accueil) accueil.innerHTML = resultat.corps;
                annoncer('Enregistré.');
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

    function ouvrir() {
        var zone = zoneDeLecture();
        var champ = conteneur();
        if (!zone || !champ) return false;
        zone.classList.add('mode-edition');
        // `plaintext-only` tient le collage NON traversant, que la garde
        // laisse passer par construction. Les trois moteurs l'acceptent.
        // / plaintext-only handles the non-traversing paste.
        champ.setAttribute('contenteditable', 'plaintext-only');
        // Les gouttieres restent HORS du champ : elles portent le
        // reperage (numero, locuteur, minutage), pas le texte.
        // / The gutters stay out of the editable area.
        var gouttieres = champ.querySelectorAll('.gouttiere, .filet-etat');
        for (var i = 0; i < gouttieres.length; i += 1) {
            gouttieres[i].setAttribute('contenteditable', 'false');
        }
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

    function fermer() {
        var zone = zoneDeLecture();
        var champ = conteneur();
        if (!zone || !zone.classList.contains('mode-edition')) return false;
        zone.classList.remove('mode-edition');
        if (champ) {
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
    document.addEventListener('keydown', function (evenement) {
        if (!estOuvert()) return;
        if (!(evenement.ctrlKey || evenement.metaKey)) return;
        var touche = evenement.key.toLowerCase();
        if (touche === 's') {
            // preventDefault OBLIGATOIRE : c'est « enregistrer la page ».
            evenement.preventDefault();
            enregistrer();
            return;
        }
        if (touche === 'z' && !evenement.shiftKey) {
            // On intercepte TOUJOURS : melanger la pile native et la
            // notre rendrait l'ordre des annulations imprevisible.
            // / Always intercept: mixing the two stacks is unpredictable.
            evenement.preventDefault();
            var rendus = annuler();
            if (rendus) marquerCommeModifie();
            annoncer(rendus ? rendus + ' passage(s) rétabli(s).'
                            : 'Rien à annuler.');
            return;
        }
        if ((touche === 'z' && evenement.shiftKey) || touche === 'y') {
            evenement.preventDefault();
            var refaits = retablir();
            if (refaits) marquerCommeModifie();
            annoncer(refaits ? refaits + ' passage(s) rétabli(s).'
                             : 'Rien à rétablir.');
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

    window.modeEdition = {
        estOuvert: estOuvert,
        fermer: fermer,
        basculer: basculer,
    };
})();

// Appele par l'attribut onclick du bouton (meme patron que le mode
// structure). / Called by the button's onclick, like the structure mode.
function basculerModeEdition(bouton) {
    if (window.modeEdition) window.modeEdition.basculer(bouton);
}
