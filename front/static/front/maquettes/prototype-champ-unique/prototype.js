/**
 * PROTOTYPE JETABLE — option C, le champ unique.
 * / Throwaway prototype: option C, the single field.
 *
 * LOCALISATION : scratchpad de session. HORS DEPOT. Rien n'en est destine
 * a etre garde : on garde les CHIFFRES, pas ce code.
 *
 * Il reproduit la structure DOM REELLE d'un bloc de lecture
 * (front/templates/front/includes/_blocs_elements.html) :
 *     .bloc > .gouttiere + .filet-etat + .corps > <p|h2|li|...>
 * C'est important : la note TODO supposait « un conteneur avec un enfant
 * par bloc », c'est-a-dire une structure PLATE. Elle ne l'est pas, et une
 * selection du bloc 3 au bloc 8 traverse forcement les gouttieres de 4 a 8.
 *
 * LES DONNEES LIVREES ICI SONT SYNTHETIQUES. Le prototype a ete mesure sur
 * la vraie base — page 19 (210 blocs, 58 770 caracteres) et page 3 (la
 * transcription) —, mais la page 19 est un article qui appartient a un
 * tiers : son texte n'a pas sa place dans l'historique du depot. Le
 * `donnees.json` livre a donc la MEME FORME (210 blocs, meme repartition de
 * labels, 8 tableaux a saut de ligne, 5 locuteurs) avec du texte fabrique,
 * a 3 % du volume reel. Pour remesurer sur le vrai corpus :
 * `benchmarks/edition_par_blocs/banc/extraire_les_donnees_reelles.py`.
 * / The shipped data is synthetic, same shape as the real corpus.
 *
 * Parametres d'URL :
 *   ?ce=true|plaintext-only   la valeur de contenteditable sur le conteneur
 *   ?garde=1|0                les interceptions, ou le navigateur nu
 *   ?page=19|3                le jeu de donnees reel
 *   ?boutons=1                rend les boutons d'action DANS le corps
 */

const parametres = new URLSearchParams(location.search);
const VALEUR_CONTENTEDITABLE = parametres.get("ce") || "true";
const MODE_GARDE = parametres.get("garde") || "1";
// garde=0 : le navigateur nu. garde=1 : la garde par keydown.
// garde=2 : la garde par beforeinput.
// / 0: bare browser. 1: keydown guard. 2: beforeinput guard.
const GARDE_ACTIVE = MODE_GARDE !== "0";
const PAGE_DEMANDEE = parametres.get("page") || "19";
const RENDRE_LES_BOUTONS = parametres.get("boutons") === "1";
// ?ecriture=exec : les ecritures passent par document.execCommand, qui
// preserve la pile d'annulation native. ?ecriture=dom (defaut) ecrit
// directement dans le DOM, ce qui la detruit.
// / exec mode routes writes through execCommand, which keeps native undo.
const ECRITURE = parametres.get("ecriture") || "dom";
// ?compo=1 : normalise la selection des `compositionstart`, la parade
// au seul degat que la garde `beforeinput` ne peut pas arreter.
// / ?compo=1: normalize the selection at compositionstart.
const NORMALISER_A_LA_COMPOSITION = parametres.get("compo") === "1";
// ?annulation=1 : la pile applicative de l'addendum A.
// / ?annulation=1: the application-level undo stack of addendum A.
const ANNULATION_APPLICATIVE = parametres.get("annulation") === "1";
// La borne de la pile. 100 pas font 5,5 Mo sur 210 blocs (mesure du
// 28 aout 2026). Ce qu'elle ecarte est COMPTE, jamais oublie en silence.
// / The stack cap: what it drops is counted, never silently forgotten.
const BORNE_DE_LA_PILE = 100;
const PAUSE_AVANT_PHOTO = 500;

const champ = document.getElementById("champ");

// L'etat que le prototype rend observable depuis Playwright.
// / The state the prototype exposes to Playwright.
window.PROTO = {
  blocsInitiaux: [],
  journalSentinelle: [],
  journalGestes: [],
  mesures: {},
  pret: false,
};

/* ================================================================== */
/* 1. LE RENDU                                                         */
/* ================================================================== */

function baliseDuLabel(label) {
  if (label === "section_header" || label === "title") return "h2";
  if (label === "list_item") return "li";
  if (label === "code") return "pre";
  return "p";
}

function echapper(texte) {
  const noeud = document.createElement("div");
  noeud.textContent = texte;
  return noeud.innerHTML;
}

/**
 * Construit le HTML du corps d'un bloc.
 * Un bloc sur trois porte un <mark class="portion"> : 386 elements sur
 * 1 129 portent un ancrage dans la vraie base, et ces <mark> sont dans
 * le corps, donc dans le champ editable.
 * / One block in three carries a highlight mark, as in the real base.
 */
function corpsDuBloc(bloc, index) {
  const texte = bloc.texte;
  let interieur;
  if (index % 3 === 0 && texte.length > 40) {
    const debut = texte.slice(0, 10);
    const milieu = texte.slice(10, 30);
    const fin = texte.slice(30);
    interieur = echapper(debut)
      + '<mark class="portion">' + echapper(milieu) + "</mark>"
      + echapper(fin);
  } else {
    interieur = echapper(texte);
  }
  if (RENDRE_LES_BOUTONS) {
    // Le piege du § 7.1 de la spec : les boutons sont rendus DANS le <p>.
    // / The spec's trap: action buttons live inside the <p>.
    interieur += '<span class="actions-element">'
      + "<button>corriger</button><button>couper</button>"
      + "<button>recoller</button><button>masquer</button></span>";
  }
  return interieur;
}

function construireLeChamp(blocs) {
  const morceaux = [];
  blocs.forEach((bloc, index) => {
    const balise = baliseDuLabel(bloc.label);
    const locuteur = (bloc.provenance && bloc.provenance.locuteur) || "";
    const ouvrant = balise === "li" ? "<ul><li" : "<" + balise;
    const fermant = balise === "li" ? "</li></ul>" : "</" + balise + ">";
    morceaux.push(
      '<div class="bloc" data-element="' + bloc.identifiant_stable + '"'
      + ' data-ordre="' + bloc.ordre + '"'
      + ' data-label="' + bloc.label + '"'
      + ' data-testid="bloc-' + bloc.ordre + '">'
      + '<div class="gouttiere" contenteditable="false">'
      + (locuteur ? '<span class="etiquette-locuteur">' + echapper(locuteur) + "</span> " : "")
      + "#" + (index + 1)
      + "</div>"
      + '<div class="filet-etat" contenteditable="false"></div>'
      + '<div class="corps">'
      + ouvrant + ' data-corps-de="' + bloc.identifiant_stable + '">'
      + corpsDuBloc(bloc, index)
      + fermant
      + "</div></div>"
    );
  });
  champ.innerHTML = morceaux.join("");
}

/* ================================================================== */
/* 2. LA SENTINELLE — toute frontiere qui bouge est une violation      */
/* ================================================================== */

/**
 * Rend la signature des frontieres : identifiant_stable + ordre, dans
 * l'ordre du document. C'est l'invariant du § 3 de la spec.
 * / The frontier signature: stable ids and order, in document order.
 */
window.signatureDesFrontieres = function () {
  return Array.from(champ.querySelectorAll(".bloc")).map(
    (bloc) => bloc.dataset.element + ":" + bloc.dataset.ordre
  );
};

const observateur = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    if (mutation.type !== "childList") continue;
    const ajoutes = Array.from(mutation.addedNodes);
    const retires = Array.from(mutation.removedNodes);
    if (!ajoutes.length && !retires.length) continue;
    const decrire = (noeud) =>
      noeud.nodeType === 3
        ? "#texte(" + JSON.stringify(noeud.textContent.slice(0, 20)) + ")"
        : "<" + noeud.nodeName.toLowerCase()
          + (noeud.className ? "." + String(noeud.className).split(" ")[0] : "") + ">";
    const cible = mutation.target;
    const cibleDecrite =
      cible === champ
        ? "#champ"
        : "<" + cible.nodeName.toLowerCase()
          + (cible.className ? "." + String(cible.className).split(" ")[0] : "") + ">";
    // On ne retient que ce qui touche la STRUCTURE : le conteneur lui-meme,
    // un .bloc, une .gouttiere, un .corps. Le texte a l'interieur d'un
    // corps bouge legitimement.
    // / Only structural mutations count as violations.
    const toucheLaStructure =
      cible === champ
      || (cible.classList && (cible.classList.contains("bloc")
                              || cible.classList.contains("corps")))
      || ajoutes.concat(retires).some(
        (n) => n.nodeType === 1 && n.classList
               && (n.classList.contains("bloc") || n.classList.contains("gouttiere")
                   || n.classList.contains("corps") || n.classList.contains("filet-etat"))
      );
    window.PROTO.journalSentinelle.push({
      cible: cibleDecrite,
      ajoutes: ajoutes.map(decrire),
      retires: retires.map(decrire),
      structure: toucheLaStructure,
      geste: window.PROTO.gesteEnCours || null,
    });
  }
});

/* ================================================================== */
/* 3. LES INTERCEPTIONS                                                */
/* ================================================================== */

function corpsDuNoeud(noeud) {
  const element = noeud.nodeType === 3 ? noeud.parentElement : noeud;
  return element ? element.closest(".corps") : null;
}

function blocDuNoeud(noeud) {
  const element = noeud.nodeType === 3 ? noeud.parentElement : noeud;
  return element ? element.closest(".bloc") : null;
}

/** Offset en caracteres du point (noeud, offset) dans son corps. */
function offsetDansLeCorps(corps, noeud, offset) {
  const plage = document.createRange();
  plage.selectNodeContents(corps);
  plage.setEnd(noeud, offset);
  return plage.toString().length;
}

/**
 * Normalise la selection dans l'ordre du DOCUMENT, pas du geste.
 * Piege 3 de la note : une selection faite vers le haut inverse
 * anchorNode et focusNode.
 * / Normalize the selection in document order, not gesture order.
 */
function selectionNormalisee() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;
  const plage = selection.getRangeAt(0);
  return {
    debutNoeud: plage.startContainer,
    debutOffset: plage.startOffset,
    finNoeud: plage.endContainer,
    finOffset: plage.endOffset,
    repliee: plage.collapsed,
  };
}

function texteDuCorps(corps) {
  return corps.textContent;
}

function ecrireLeTexte(corps, texte) {
  if (ECRITURE === "exec") {
    ecrireParExecCommand(corps, texte);
    return;
  }
  const enfant = corps.firstElementChild;
  const identifiant = enfant ? enfant.dataset.corpsDe : null;
  enfant.textContent = texte;
  if (identifiant) enfant.dataset.corpsDe = identifiant;
  const bloc = corps.closest(".bloc");
  bloc.dataset.vide = texte.length === 0 ? "oui" : "non";
}

/**
 * Ecrit le texte d'un bloc par execCommand, en ne remplacant que la part
 * qui DIFFERE. On selectionne cette part, puis on la remplace.
 * execCommand est deprecie mais c'est le seul chemin qui alimente la pile
 * d'annulation native du navigateur.
 * / Writes through execCommand: the only path that feeds native undo.
 */
function ecrireParExecCommand(corps, texte) {
  const ancien = corps.textContent;
  if (ancien === texte) return;
  // Prefixe et suffixe communs : on ne touche qu'au milieu.
  // / Common prefix and suffix: only the middle is replaced.
  let debut = 0;
  while (debut < ancien.length && debut < texte.length
         && ancien[debut] === texte[debut]) debut += 1;
  let queue = 0;
  while (queue < ancien.length - debut && queue < texte.length - debut
         && ancien[ancien.length - 1 - queue] === texte[texte.length - 1 - queue]) queue += 1;
  const finAncien = ancien.length - queue;
  const remplacement = texte.slice(debut, texte.length - queue);

  selectionnerDansLeCorps(corps, debut, finAncien);
  if (remplacement.length > 0) {
    document.execCommand("insertText", false, remplacement);
  } else if (finAncien > debut) {
    document.execCommand("delete", false, null);
  }
  const bloc = corps.closest(".bloc");
  bloc.dataset.vide = corps.textContent.length === 0 ? "oui" : "non";
}

/** Selectionne [debut, fin[ en caracteres dans un corps. */
function selectionnerDansLeCorps(corps, debut, fin) {
  const marcheur = document.createTreeWalker(corps, NodeFilter.SHOW_TEXT);
  let parcouru = 0;
  let noeudDebut = null, offsetDebut = 0, noeudFin = null, offsetFin = 0;
  let noeud = marcheur.nextNode();
  while (noeud) {
    const longueur = noeud.textContent.length;
    if (noeudDebut === null && parcouru + longueur >= debut) {
      noeudDebut = noeud; offsetDebut = debut - parcouru;
    }
    if (parcouru + longueur >= fin) {
      noeudFin = noeud; offsetFin = fin - parcouru;
      break;
    }
    parcouru += longueur;
    noeud = marcheur.nextNode();
  }
  if (!noeudDebut) { noeudDebut = corps; offsetDebut = 0; }
  if (!noeudFin) { noeudFin = noeudDebut; offsetFin = offsetDebut; }
  const plage = document.createRange();
  plage.setStart(noeudDebut, Math.min(offsetDebut, noeudDebut.textContent.length));
  plage.setEnd(noeudFin, Math.min(offsetFin, noeudFin.textContent.length));
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(plage);
}

function poserLeCurseur(corps, offsetVoulu) {
  const marcheur = document.createTreeWalker(corps, NodeFilter.SHOW_TEXT);
  let reste = offsetVoulu;
  let noeud = marcheur.nextNode();
  while (noeud) {
    if (reste <= noeud.textContent.length) {
      const selection = window.getSelection();
      const plage = document.createRange();
      plage.setStart(noeud, reste);
      plage.collapse(true);
      selection.removeAllRanges();
      selection.addRange(plage);
      return;
    }
    reste -= noeud.textContent.length;
    noeud = marcheur.nextNode();
  }
  const selection = window.getSelection();
  const plage = document.createRange();
  plage.selectNodeContents(corps);
  plage.collapse(false);
  selection.removeAllRanges();
  selection.addRange(plage);
}

/**
 * LE GESTE CENTRAL : vider une selection multi-blocs SANS fusionner.
 * Chaque bloc de la plage perd exactement la part de son texte qui etait
 * selectionnee. Les frontieres ne bougent pas.
 * / The central gesture: clear a multi-block selection without merging.
 */
function viderLaSelectionBlocParBloc() {
  const normale = selectionNormalisee();
  if (!normale) return false;
  const corpsDebut = corpsDuNoeud(normale.debutNoeud);
  const corpsFin = corpsDuNoeud(normale.finNoeud);
  if (!corpsDebut || !corpsFin) return false;
  if (corpsDebut === corpsFin) return false;

  const blocs = Array.from(champ.querySelectorAll(".bloc"));
  const indexDebut = blocs.indexOf(corpsDebut.closest(".bloc"));
  const indexFin = blocs.indexOf(corpsFin.closest(".bloc"));

  const offsetDebut = offsetDansLeCorps(corpsDebut, normale.debutNoeud, normale.debutOffset);
  const offsetFin = offsetDansLeCorps(corpsFin, normale.finNoeud, normale.finOffset);

  // Premier bloc : on garde ce qui precede la selection.
  ecrireLeTexte(corpsDebut, texteDuCorps(corpsDebut).slice(0, offsetDebut));
  // Blocs intermediaires : vides entierement.
  for (let i = indexDebut + 1; i < indexFin; i += 1) {
    ecrireLeTexte(blocs[i].querySelector(".corps"), "");
  }
  // Dernier bloc : on garde ce qui suit la selection.
  ecrireLeTexte(corpsFin, texteDuCorps(corpsFin).slice(offsetFin));

  poserLeCurseur(corpsDebut, offsetDebut);
  return true;
}

function insererDuTexte(texte) {
  const normale = selectionNormalisee();
  if (!normale) return;
  const corps = corpsDuNoeud(normale.debutNoeud);
  if (!corps) return;
  if (!normale.repliee && corpsDuNoeud(normale.finNoeud) !== corps) {
    viderLaSelectionBlocParBloc();
    insererDuTexte(texte);
    return;
  }
  const contenu = texteDuCorps(corps);
  const debut = offsetDansLeCorps(corps, normale.debutNoeud, normale.debutOffset);
  const fin = offsetDansLeCorps(corps, normale.finNoeud, normale.finOffset);
  ecrireLeTexte(corps, contenu.slice(0, debut) + texte + contenu.slice(fin));
  poserLeCurseur(corps, debut + texte.length);
}

/**
 * LA GARDE PAR `beforeinput` — celle que la garde par `keydown` aurait du
 * etre. `beforeinput` voit TOUT ce qui va modifier le champ : la frappe,
 * le remplacement d'une selection, le couper, le coller, le glisser, la
 * correction orthographique, l'IME, l'annulation.
 * / The beforeinput guard: it sees every mutation before it happens.
 *
 * `getTargetRanges()` rend la plage QUE LE NAVIGATEUR VA TOUCHER. C'est
 * elle qui dit si le geste traverse des blocs — pas la selection, qui peut
 * en differer (Retour arriere replie, par exemple).
 */
function poserLaGardeBeforeInput() {
  champ.addEventListener("beforeinput", (evenement) => {
    const type = evenement.inputType;
    // `getTargetRanges()` rend une liste VIDE sous
    // contenteditable="plaintext-only" (Chromium 145, mesure du 23 aout
    // 2026) : pour insertText, insertFromPaste ET deleteContentForward.
    // Une garde qui s'y fie seule y est AVEUGLE, et laisse passer les
    // gestes qui traversent. On retombe donc sur la selection.
    // / getTargetRanges() is EMPTY under plaintext-only: fall back to
    // the selection, or the guard is blind there.
    let plages = evenement.getTargetRanges();
    if (!plages || !plages.length) {
      const selection = window.getSelection();
      plages = (selection && selection.rangeCount) ? [selection.getRangeAt(0)] : [];
    }
    const plage = plages.length ? plages[0] : null;

    const corpsDebut = plage ? corpsDuNoeud(plage.startContainer) : null;
    const corpsFin = plage ? corpsDuNoeud(plage.endContainer) : null;
    const traverse = corpsDebut && corpsFin && corpsDebut !== corpsFin;
    const horsDeTouteBloc = plage && (!corpsDebut || !corpsFin);

    window.PROTO.journalBeforeInput = window.PROTO.journalBeforeInput || [];
    window.PROTO.journalBeforeInput.push({
      type: type,
      traverse: !!traverse,
      hors_bloc: !!horsDeTouteBloc,
      annulable: evenement.cancelable,
    });

    // 1. Entree : jamais de nouveau bloc, un \n dans celui-ci.
    if (type === "insertParagraph" || type === "insertLineBreak") {
      evenement.preventDefault();
      empilerAvantUnGeste();
      insererDuTexte("\n");
      marquerCommeModifie();
      return;
    }

    // 2. Le geste ne traverse pas et reste dans un corps : on laisse faire.
    //    C'est la frappe ordinaire. Elle ne se photographie pas a chaque
    //    touche — on arme une photo qui partira apres une PAUSE.
    //    / Ordinary typing: arm a snapshot that lands after a pause.
    if (!traverse && !horsDeTouteBloc) {
      armerLaPhotoDeFrappe();
      marquerCommeModifie();
      if (type === "deleteContentBackward" && corpsDebut
          && offsetDansLeCorps(corpsDebut, plage.startContainer, plage.startOffset) === 0
          && plage.collapsed) {
        evenement.preventDefault();   // en tete de bloc : rien
      }
      return;
    }

    // 3. Le geste TRAVERSE, ou sort des blocs : on le fait nous-memes,
    //    bloc par bloc, sans jamais toucher aux frontieres.
    if (!evenement.cancelable) {
      // insertCompositionText n'est pas annulable : on le SIGNALE.
      // / insertCompositionText cannot be cancelled: report it.
      window.PROTO.gesteNonAnnulable = type;
      return;
    }
    evenement.preventDefault();
    // Un geste qui TRAVERSE est rare et destructeur : il se photographie
    // toujours, et tout de suite.
    // / A traversing gesture is rare and destructive: always snapshot it.
    empilerAvantUnGeste();
    marquerCommeModifie();
    const donnees = evenement.data
      || (evenement.dataTransfer && evenement.dataTransfer.getData("text/plain"))
      || "";
    if (horsDeTouteBloc) {
      // Ctrl+A : la plage part du conteneur lui-meme. On la ramene aux
      // blocs qu'elle couvre reellement.
      // / Ctrl+A: the range starts at the container. Map it to the blocks.
      viderTousLesBlocsDeLaPlage(plage);
    } else {
      viderLaPlageBlocParBloc(plage);
    }
    if (donnees) insererDuTexte(donnees);
  });
}

/**
 * LA PARADE A LA COMPOSITION IME.
 * / The IME composition workaround.
 *
 * `insertCompositionText` arrive avec `cancelable: false` : la garde
 * `beforeinput` le VOIT passer et ne peut rien en faire. Une composition
 * qui remplace une selection multi-blocs detruit donc des blocs, garde
 * comprise — et sur Android, TOUTE frappe est une composition.
 *
 * L'idee : ne pas essayer d'arreter la composition, mais lui retirer sa
 * matiere. `compositionstart` arrive AVANT que quoi que ce soit ne soit
 * ecrit, et la selection y est encore celle de l'utilisateur. On fait
 * donc le geste nous-memes, bloc par bloc, et on replie le curseur dans
 * un seul bloc. La composition n'a plus qu'un bloc devant elle.
 * / Don't fight the composition: take away what it would destroy.
 */
function poserLaParadeALaComposition() {
  champ.addEventListener("compositionstart", () => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    const plage = selection.getRangeAt(0);
    const corpsDebut = corpsDuNoeud(plage.startContainer);
    const corpsFin = corpsDuNoeud(plage.endContainer);
    window.PROTO.compositionsVues = (window.PROTO.compositionsVues || 0) + 1;
    if (!corpsDebut || !corpsFin || corpsDebut === corpsFin) return;
    // La selection traverse : on la vide nous-memes, MAINTENANT.
    // / It traverses: clear it ourselves, now.
    window.PROTO.compositionsNormalisees =
      (window.PROTO.compositionsNormalisees || 0) + 1;
    empilerAvantUnGeste();
    marquerCommeModifie();
    viderLaPlageBlocParBloc(plage);
  });
}

/** Vide, bloc par bloc, la part couverte par une plage qui traverse. */
function viderLaPlageBlocParBloc(plage) {
  const corpsDebut = corpsDuNoeud(plage.startContainer);
  const corpsFin = corpsDuNoeud(plage.endContainer);
  const blocs = Array.from(champ.querySelectorAll(".bloc"));
  const indexDebut = blocs.indexOf(corpsDebut.closest(".bloc"));
  const indexFin = blocs.indexOf(corpsFin.closest(".bloc"));
  const offsetDebut = offsetDansLeCorps(corpsDebut, plage.startContainer, plage.startOffset);
  const offsetFin = offsetDansLeCorps(corpsFin, plage.endContainer, plage.endOffset);
  ecrireLeTexte(corpsDebut, texteDuCorps(corpsDebut).slice(0, offsetDebut));
  for (let i = indexDebut + 1; i < indexFin; i += 1) {
    ecrireLeTexte(blocs[i].querySelector(".corps"), "");
  }
  ecrireLeTexte(corpsFin, texteDuCorps(corpsFin).slice(offsetFin));
  poserLeCurseur(corpsDebut, offsetDebut);
}

/** Vide TOUS les blocs couverts, quand la plage part du conteneur. */
function viderTousLesBlocsDeLaPlage(plage) {
  const vraiePlage = document.createRange();
  vraiePlage.setStart(plage.startContainer, plage.startOffset);
  vraiePlage.setEnd(plage.endContainer, plage.endOffset);
  const blocs = Array.from(champ.querySelectorAll(".bloc"));
  let premier = null;
  for (const bloc of blocs) {
    const corps = bloc.querySelector(".corps");
    if (!corps) continue;
    if (vraiePlage.intersectsNode(corps)) {
      if (premier === null) premier = corps;
      ecrireLeTexte(corps, "");
    }
  }
  if (premier) poserLeCurseur(premier, 0);
}

function poserLesInterceptions() {
  champ.addEventListener("keydown", (evenement) => {
    const normale = selectionNormalisee();
    if (!normale) return;
    const corpsDebut = corpsDuNoeud(normale.debutNoeud);
    const corpsFin = corpsDuNoeud(normale.finNoeud);
    const traverse = corpsDebut && corpsFin && corpsDebut !== corpsFin;

    if (evenement.key === "Enter") {
      // Entree n'ouvre JAMAIS un bloc : elle insere un \n dans le bloc.
      // / Enter never opens a block: it inserts a newline inside it.
      evenement.preventDefault();
      insererDuTexte("\n");
      return;
    }
    if (evenement.key === "Backspace") {
      if (traverse) { evenement.preventDefault(); viderLaSelectionBlocParBloc(); return; }
      if (normale.repliee && corpsDebut
          && offsetDansLeCorps(corpsDebut, normale.debutNoeud, normale.debutOffset) === 0) {
        // En tete de bloc : ne fait rien. Pas de fusion.
        // / At the head of a block: does nothing. No merge.
        evenement.preventDefault();
        return;
      }
    }
    if (evenement.key === "Delete") {
      if (traverse) { evenement.preventDefault(); viderLaSelectionBlocParBloc(); return; }
      if (normale.repliee && corpsDebut) {
        const offset = offsetDansLeCorps(corpsDebut, normale.debutNoeud, normale.debutOffset);
        if (offset >= texteDuCorps(corpsDebut).length) {
          // Suppr en FIN de bloc fusionnerait avec le suivant : c'est le
          // symetrique du Retour arriere en tete, et la note ne le nommait pas.
          // / Delete at the end of a block would merge with the next one.
          evenement.preventDefault();
          return;
        }
      }
    }
    if ((evenement.ctrlKey || evenement.metaKey) && evenement.key.toLowerCase() === "s") {
      evenement.preventDefault();
      enregistrer();
    }
  });

  champ.addEventListener("paste", (evenement) => {
    evenement.preventDefault();
    const texte = (evenement.clipboardData || window.clipboardData).getData("text/plain");
    insererDuTexte(texte);
  });

  champ.addEventListener("drop", (evenement) => {
    evenement.preventDefault();
    const texte = evenement.dataTransfer.getData("text/plain");
    if (texte) insererDuTexte(texte);
  });
}

/* ================================================================== */
/* 3 bis. L'ANNULATION APPLICATIVE (addendum A de la spec)             */
/* ================================================================== */

/**
 * LA PILE. Une photo est une table `identifiant_stable -> texte`, et
 * RIEN D'AUTRE : le mode interdisant la fusion et la scission, la liste
 * des blocs est invariante — il n'y a aucune structure a restaurer.
 * / A snapshot is a text map, nothing else: the block list is invariant.
 */
const pile = {
  passes: [],      // les etats d'AVANT, du plus ancien au plus recent
  refaits: [],     // la branche de retablissement
  ecartees: 0,     // les photos tombees hors de la borne — on les COMPTE
  minuterie: null,
};

/** Photographie l'etat courant : les textes, et la position du curseur. */
function photographier() {
  const textes = {};
  champ.querySelectorAll(".bloc").forEach((bloc) => {
    const corps = bloc.querySelector(".corps");
    if (corps) textes[bloc.dataset.element] = texteDuCorps(corps);
  });
  return {textes: textes, curseur: ouEstLeCurseur()};
}

function ouEstLeCurseur() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;
  const corps = corpsDuNoeud(selection.anchorNode);
  if (!corps) return null;
  return {
    bloc: corps.closest(".bloc").dataset.element,
    offset: offsetDansLeCorps(corps, selection.anchorNode, selection.anchorOffset),
  };
}

/**
 * Empile l'etat AVANT un geste. Toute photo neuve coupe la branche de
 * retablissement — c'est le comportement attendu partout.
 * / Pushing a new state cuts the redo branch.
 */
function empilerAvantUnGeste() {
  if (!ANNULATION_APPLICATIVE) return;
  clearTimeout(pile.minuterie);
  pile.minuterie = null;
  pile.passes.push(photographier());
  pile.refaits.length = 0;
  while (pile.passes.length > BORNE_DE_LA_PILE) {
    pile.passes.shift();
    pile.ecartees += 1;
  }
  window.PROTO.pile = {
    passes: pile.passes.length, refaits: pile.refaits.length,
    ecartees: pile.ecartees,
  };
}

/**
 * Une frappe ordinaire ne se photographie pas a chaque touche — ce
 * serait +2,6 ms sur les 6 ms qu'elle coute deja. On attend une PAUSE :
 * un mot tape fait ainsi UN pas d'annulation, pas dix.
 * / Coalesce typing: one word makes ONE undo step, not ten.
 */
function armerLaPhotoDeFrappe() {
  if (!ANNULATION_APPLICATIVE) return;
  if (pile.minuterie !== null) return;   // une photo est deja en attente
  const avant = photographier();
  pile.minuterie = setTimeout(() => {
    pile.minuterie = null;
    pile.passes.push(avant);
    pile.refaits.length = 0;
    while (pile.passes.length > BORNE_DE_LA_PILE) {
      pile.passes.shift();
      pile.ecartees += 1;
    }
    window.PROTO.pile = {
      passes: pile.passes.length, refaits: pile.refaits.length,
      ecartees: pile.ecartees,
    };
  }, PAUSE_AVANT_PHOTO);
}

/** Reecrit SEULEMENT les blocs dont le texte differe de l'etat courant. */
function restaurer(photo) {
  let reecrits = 0;
  champ.querySelectorAll(".bloc").forEach((bloc) => {
    const corps = bloc.querySelector(".corps");
    if (!corps) return;
    const voulu = photo.textes[bloc.dataset.element];
    if (voulu === undefined) return;
    if (texteDuCorps(corps) === voulu) return;
    ecrireLeTexte(corps, voulu);
    reecrits += 1;
  });
  // Le curseur se restaure aussi : une annulation qui le laisse ailleurs
  // desoriente. / Restore the caret too.
  if (photo.curseur) {
    const bloc = champ.querySelector(
      '.bloc[data-element="' + photo.curseur.bloc + '"]');
    if (bloc && bloc.querySelector(".corps")) {
      poserLeCurseur(bloc.querySelector(".corps"), photo.curseur.offset);
    }
  }
  return reecrits;
}

function annuler() {
  // Une photo de frappe en attente doit etre prise AVANT d'annuler,
  // sinon la derniere frappe echappe a la pile.
  // / A pending typing snapshot must land before undoing.
  if (pile.minuterie !== null) {
    clearTimeout(pile.minuterie);
    pile.minuterie = null;
  }
  if (!pile.passes.length) return 0;
  const courant = photographier();
  const photo = pile.passes.pop();
  const reecrits = restaurer(photo);
  pile.refaits.push(courant);
  window.PROTO.pile = {
    passes: pile.passes.length, refaits: pile.refaits.length,
    ecartees: pile.ecartees,
  };
  return reecrits;
}

function retablir() {
  if (!pile.refaits.length) return 0;
  const courant = photographier();
  const photo = pile.refaits.pop();
  const reecrits = restaurer(photo);
  pile.passes.push(courant);
  window.PROTO.pile = {
    passes: pile.passes.length, refaits: pile.refaits.length,
    ecartees: pile.ecartees,
  };
  return reecrits;
}

window.PROTO.annuler = annuler;
window.PROTO.retablir = retablir;

/* ================================================================== */
/* 4. LA SERIALISATION ET L'ENREGISTREMENT                             */
/* ================================================================== */

/**
 * Le contrat du § 7.1 : une liste de {identifiant_stable, texte}, le
 * texte DERIVE du DOM et non lu tel quel.
 * / The § 7.1 contract: text derived from the DOM, not read as-is.
 */
window.serialiser = function () {
  return Array.from(champ.querySelectorAll(".bloc")).map((bloc) => {
    const corps = bloc.querySelector(".corps");
    if (!corps) {
      // Le navigateur a detruit le corps de ce bloc. On le DIT au lieu
      // de planter : c'est precisement ce qu'on cherche a mesurer.
      // / The browser destroyed this block's body. Report it, don't crash.
      return {
        identifiant_stable: bloc.dataset.element,
        texte: null,
        corps_detruit: true,
      };
    }
    const copie = corps.cloneNode(true);
    // On retire ce qui n'est pas du texte d'origine. Un seul caractere
    // parasite decale tous les offsets.
    // / Strip what is not original text: one stray char shifts every offset.
    copie.querySelectorAll(".actions-element").forEach((n) => n.remove());
    return {
      identifiant_stable: bloc.dataset.element,
      texte: copie.textContent,
      texte_innerText: corps.innerText,
    };
  });
};

let ilYADesModificationsEnAttente = false;
let unEnvoiEstEnCours = false;

function marquerCommeModifie() {
  ilYADesModificationsEnAttente = true;
  window.PROTO.modifie = true;
  const bandeau = document.getElementById("etat-mode");
  if (bandeau && bandeau.textContent.indexOf(" •") === -1) {
    bandeau.textContent += " •";
  }
}

/**
 * Ne pas perdre ce qui n'est pas enregistre (addendum A.5).
 * `beforeunload` ne couvre PAS les navigations HTMX internes : dans
 * l'application, il faudra aussi un garde sur `htmx:beforeRequest`.
 * / beforeunload does not cover HTMX internal navigations.
 */
window.addEventListener("beforeunload", (evenement) => {
  if (!ilYADesModificationsEnAttente) return;
  evenement.preventDefault();
  evenement.returnValue = "";
});

function enregistrer() {
  // `Ctrl+S` est DESARME pendant l'envoi : deux lots qui se chevauchent
  // s'ecraseraient l'un l'autre (addendum A.4).
  // / Ctrl+S is disarmed while a save is in flight.
  if (unEnvoiEstEnCours) {
    document.getElementById("zone-annonces").textContent =
      "Enregistrement déjà en cours.";
    return;
  }
  unEnvoiEstEnCours = true;
  const charge = window.serialiser();
  window.PROTO.dernierPost = charge;

  // Un etat d'attente VISIBLE : le lot prend 295 ms au plancher et
  // ~1,2 s pour une session ordinaire (mesure du 26 aout).
  // / A visible pending state: the batch takes 295 ms to ~1.2 s.
  document.getElementById("compte-rendu").textContent = "Enregistrement…";
  document.getElementById("zone-annonces").textContent = "Enregistrement en cours.";

  // Le prototype n'a pas de serveur : il simule le voyage, puis rend la
  // main. Dans l'application, c'est POST /elements/corriger_en_lot/.
  // / The prototype has no server: it simulates the round trip.
  setTimeout(() => {
    unEnvoiEstEnCours = false;
    // La PILE EST CONSERVEE : seul le drapeau retombe. Annuler apres
    // avoir enregistre redevient une modification en attente.
    // / The stack is kept; only the dirty flag drops.
    ilYADesModificationsEnAttente = false;
    window.PROTO.modifie = false;
    const bandeau = document.getElementById("etat-mode");
    if (bandeau) bandeau.textContent = bandeau.textContent.replace(" •", "");
    document.getElementById("compte-rendu").textContent =
      "POST de " + charge.length + " blocs — "
      + charge.reduce((n, b) => n + b.texte.length, 0) + " caractères"
      + "  |  pile : " + pile.passes.length + " pas, "
      + pile.refaits.length + " à rétablir, " + pile.ecartees + " écartés";
    document.getElementById("zone-annonces").textContent =
      charge.length + " blocs envoyés.";
  }, 300);
}
window.enregistrer = enregistrer;

/* ================================================================== */
/* 5. LE DEMARRAGE                                                     */
/* ================================================================== */

fetch("donnees.json")
  .then((reponse) => reponse.json())
  .then((donnees) => {
    const blocs = donnees[PAGE_DEMANDEE];
    window.PROTO.blocsInitiaux = blocs.map((b) => ({
      identifiant_stable: b.identifiant_stable,
      ordre: b.ordre,
      texte: b.texte,
      label: b.label,
    }));

    const avantRendu = performance.now();
    construireLeChamp(blocs);
    champ.setAttribute("contenteditable", VALEUR_CONTENTEDITABLE);
    // Ce que le navigateur a REELLEMENT retenu : plaintext-only n'est pas
    // forcement accepte. On le lit, on ne le suppose pas.
    // / What the browser actually kept: plaintext-only may be rejected.
    const valeurRetenue = champ.getAttribute("contenteditable");
    const modeEffectif = champ.contentEditable;
    const apresRendu = performance.now();

    // Force un layout complet avant de lire l'horloge.
    // / Force a full layout before reading the clock.
    const hauteur = champ.getBoundingClientRect().height;
    const apresLayout = performance.now();

    window.PROTO.mesures.rendu_ms = apresRendu - avantRendu;
    window.PROTO.mesures.layout_ms = apresLayout - apresRendu;
    window.PROTO.mesures.hauteur_px = hauteur;
    window.PROTO.mesures.contenteditable_demande = VALEUR_CONTENTEDITABLE;
    window.PROTO.mesures.contenteditable_attribut = valeurRetenue;
    window.PROTO.mesures.contenteditable_propriete = modeEffectif;
    window.PROTO.mesures.nombre_de_blocs = blocs.length;
    window.PROTO.mesures.mode_ecriture = ECRITURE;
    window.PROTO.mesures.parade_composition = NORMALISER_A_LA_COMPOSITION;
    window.PROTO.mesures.caracteres = blocs.reduce((n, b) => n + b.texte.length, 0);

    observateur.observe(champ, { childList: true, subtree: true });
    if (MODE_GARDE === "1") poserLesInterceptions();
    if (MODE_GARDE === "2") {
      poserLaGardeBeforeInput();
      if (NORMALISER_A_LA_COMPOSITION) poserLaParadeALaComposition();
      // Le glisser-deposer est REFUSE a la source : c'est le seul geste
      // qui ne se rattrape pas au depot, la selection y etant encore
      // celle de l'origine.
      // / Dragging is refused at the source: it cannot be fixed at drop.
      champ.addEventListener("dragstart", (e) => e.preventDefault());
      champ.addEventListener("keydown", (e) => {
        if (!(e.ctrlKey || e.metaKey)) return;
        const touche = e.key.toLowerCase();
        if (touche === "s") {
          // preventDefault OBLIGATOIRE : c'est « enregistrer la page ».
          // / Mandatory: this is the browser's "save page".
          e.preventDefault();
          enregistrer();
          return;
        }
        if (!ANNULATION_APPLICATIVE) return;
        if (touche === "z" && !e.shiftKey) {
          // On intercepte TOUJOURS : melanger la pile native et la
          // notre rendrait l'ordre des annulations imprevisible.
          // / Always intercept: mixing the two stacks is unpredictable.
          e.preventDefault();
          const n = annuler();
          window.PROTO.dernierePileAnnulee = n;
          if (n) marquerCommeModifie();
          document.getElementById("zone-annonces").textContent =
            n ? n + " bloc(s) rétabli(s) par l'annulation."
              : "Rien à annuler.";
          return;
        }
        if ((touche === "z" && e.shiftKey) || touche === "y") {
          e.preventDefault();
          const n = retablir();
          if (n) marquerCommeModifie();
          document.getElementById("zone-annonces").textContent =
            n ? n + " bloc(s) rétabli(s)." : "Rien à rétablir.";
        }
      });
    }

    document.getElementById("etat-mode").textContent =
      "mode : ce=" + modeEffectif + " garde=" + (GARDE_ACTIVE ? "1" : "0");
    document.getElementById("compte-blocs").textContent =
      "blocs : " + blocs.length;
    document.getElementById("compte-caracteres").textContent =
      "caractères : " + window.PROTO.mesures.caracteres;

    window.PROTO.frontieresInitiales = window.signatureDesFrontieres();
    window.PROTO.pret = true;
  });
