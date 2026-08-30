/**
 * LA GARDE `beforeinput`, POSEE SUR LE VRAI DOM DE L'ECRAN DE LECTURE.
 * / The beforeinput guard, applied to the REAL reading screen DOM.
 *
 * LOCALISATION : benchmarks/edition_par_blocs/banc/garde_sur_le_vrai_dom.js
 *
 * Le prototype de l'option C tournait sur une REPLIQUE du gabarit. Une
 * relecture adverse a eu raison de dire que ca ne prouvait pas le cas
 * reel : le vrai `.corps` porte les BLANCS d'indentation Django, et le
 * vrai `<p>` contient le `<span class="actions-element">` avec ses quatre
 * boutons. Ce fichier s'injecte dans la page servie par Django, telle
 * quelle, et rejoue les memes gestes.
 *
 * Il n'est PAS destine a la production : c'est un instrument de mesure.
 */
(function () {
  const conteneur = document.querySelector('[data-testid="blocs-elements"]');
  if (!conteneur) { window.GARDE = {erreur: "conteneur introuvable"}; return; }

  window.GARDE = {journal: [], mutationsDeStructure: 0};

  /** Le corps EDITABLE d'un bloc : l'element interne, pas le .corps. */
  function elementDeTexte(bloc) {
    const corps = bloc.querySelector(".corps");
    if (!corps) return null;
    // Un bloc rend p, h2, h3, blockquote, pre, figure, ul>li ou
    // .cadre-tableau. Tous portent `data-element-id`.
    // / They all carry data-element-id.
    return corps.querySelector("[data-element-id]");
  }

  /**
   * DEUX serialisations, pour les comparer.
   * `.corps.textContent` prend les BLANCS du gabarit ; l'element interne,
   * debarrasse de ses boutons, rend le texte d'origine.
   * / Two serializations, to compare them.
   */
  window.serialiserParLeCorps = function () {
    return Array.from(conteneur.querySelectorAll(".bloc[data-element]")).map((b) => ({
      identifiant_stable: b.dataset.element,
      texte: (b.querySelector(".corps") || {textContent: ""}).textContent,
    }));
  };

  window.serialiserParLElementInterne = function () {
    return Array.from(conteneur.querySelectorAll(".bloc[data-element]")).map((b) => {
      const interne = elementDeTexte(b);
      if (!interne) return {identifiant_stable: b.dataset.element, texte: null};
      const copie = interne.cloneNode(true);
      // Les boutons ne sont PAS du texte d'origine. Un seul caractere
      // parasite decale tous les offsets.
      // / The buttons are not original text.
      copie.querySelectorAll(".actions-element").forEach((n) => n.remove());
      return {identifiant_stable: b.dataset.element, texte: copie.textContent};
    });
  };

  window.signatureDesFrontieres = function () {
    return Array.from(
      conteneur.querySelectorAll("[data-element]")
    ).map((n) => n.dataset.element + ":" + (n.classList.contains("bloc") ? "bloc" : "masque"));
  };

  const observateur = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type !== "childList") continue;
      const noeuds = Array.from(m.addedNodes).concat(Array.from(m.removedNodes));
      const touche = m.target === conteneur
        || (m.target.classList && (m.target.classList.contains("bloc")
                                   || m.target.classList.contains("corps")))
        || noeuds.some((n) => n.nodeType === 1 && n.classList
             && (n.classList.contains("bloc") || n.classList.contains("gouttiere")
                 || n.classList.contains("corps")));
      if (touche) window.GARDE.mutationsDeStructure += 1;
    }
  });
  observateur.observe(conteneur, {childList: true, subtree: true});

  /* ---------- la garde ---------- */

  function corpsDuNoeud(noeud) {
    const e = noeud && noeud.nodeType === 3 ? noeud.parentElement : noeud;
    return e && e.closest ? e.closest(".corps") : null;
  }

  function offsetDansLeCorps(corps, noeud, offset) {
    const p = document.createRange();
    p.selectNodeContents(corps);
    p.setEnd(noeud, offset);
    return p.toString().length;
  }

  function texteInterne(corps) {
    const interne = corps.querySelector("[data-element-id]") || corps;
    const copie = interne.cloneNode(true);
    copie.querySelectorAll(".actions-element").forEach((n) => n.remove());
    return copie.textContent;
  }

  function ecrireLeTexte(corps, texte) {
    const interne = corps.querySelector("[data-element-id]") || corps;
    const actions = interne.querySelector(".actions-element");
    interne.textContent = texte;
    // On REMET les boutons : ils font partie de l'ecran, pas du texte.
    // / Put the buttons back: they belong to the screen, not the text.
    if (actions) interne.appendChild(actions);
  }

  function poserLeCurseur(corps, offset) {
    const marcheur = document.createTreeWalker(corps, NodeFilter.SHOW_TEXT);
    let reste = offset, n = marcheur.nextNode();
    while (n) {
      if (reste <= n.textContent.length) {
        const p = document.createRange();
        p.setStart(n, reste); p.collapse(true);
        const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
        return;
      }
      reste -= n.textContent.length;
      n = marcheur.nextNode();
    }
  }

  function viderLaPlageBlocParBloc(plage) {
    const cd = corpsDuNoeud(plage.startContainer);
    const cf = corpsDuNoeud(plage.endContainer);
    const blocs = Array.from(conteneur.querySelectorAll(".bloc"));
    const id = blocs.indexOf(cd.closest(".bloc"));
    const iff = blocs.indexOf(cf.closest(".bloc"));
    const od = offsetDansLeCorps(cd, plage.startContainer, plage.startOffset);
    const of = offsetDansLeCorps(cf, plage.endContainer, plage.endOffset);
    ecrireLeTexte(cd, texteInterne(cd).slice(0, od));
    for (let i = id + 1; i < iff; i += 1) {
      const c = blocs[i].querySelector(".corps");
      if (c) ecrireLeTexte(c, "");
    }
    ecrireLeTexte(cf, texteInterne(cf).slice(of));
    poserLeCurseur(cd, od);
  }

  function insererDuTexte(texte) {
    const s = window.getSelection();
    if (!s || !s.rangeCount) return;
    const plage = s.getRangeAt(0);
    const corps = corpsDuNoeud(plage.startContainer);
    if (!corps) return;
    const contenu = texteInterne(corps);
    const d = offsetDansLeCorps(corps, plage.startContainer, plage.startOffset);
    const f = offsetDansLeCorps(corps, plage.endContainer, plage.endOffset);
    ecrireLeTexte(corps, contenu.slice(0, d) + texte + contenu.slice(f));
    poserLeCurseur(corps, d + texte.length);
  }

  conteneur.addEventListener("beforeinput", (e) => {
    const type = e.inputType;
    // `getTargetRanges()` rend une liste VIDE sous plaintext-only : on
    // retombe sur la selection, sinon la garde y est aveugle.
    // / Empty under plaintext-only: fall back to the selection.
    let plages = e.getTargetRanges();
    if (!plages || !plages.length) {
      const s = window.getSelection();
      plages = (s && s.rangeCount) ? [s.getRangeAt(0)] : [];
    }
    const plage = plages.length ? plages[0] : null;
    const cd = plage ? corpsDuNoeud(plage.startContainer) : null;
    const cf = plage ? corpsDuNoeud(plage.endContainer) : null;
    const traverse = cd && cf && cd !== cf;
    const horsBloc = plage && (!cd || !cf);

    window.GARDE.journal.push({type: type, traverse: !!traverse,
                               hors_bloc: !!horsBloc, annulable: e.cancelable});

    if (type === "insertParagraph" || type === "insertLineBreak") {
      e.preventDefault(); insererDuTexte("\n"); return;
    }
    if (!traverse && !horsBloc) {
      if (type === "deleteContentBackward" && cd && plage.collapsed
          && offsetDansLeCorps(cd, plage.startContainer, plage.startOffset) === 0) {
        e.preventDefault();
      }
      return;
    }
    if (!e.cancelable) { window.GARDE.nonAnnulable = type; return; }
    e.preventDefault();
    const donnees = e.data
      || (e.dataTransfer && e.dataTransfer.getData("text/plain")) || "";
    if (horsBloc) {
      const vraie = document.createRange();
      vraie.setStart(plage.startContainer, plage.startOffset);
      vraie.setEnd(plage.endContainer, plage.endOffset);
      let premier = null;
      for (const bloc of conteneur.querySelectorAll(".bloc")) {
        const c = bloc.querySelector(".corps");
        if (c && vraie.intersectsNode(c)) {
          if (!premier) premier = c;
          ecrireLeTexte(c, "");
        }
      }
      if (premier) poserLeCurseur(premier, 0);
    } else {
      viderLaPlageBlocParBloc(plage);
    }
    if (donnees) insererDuTexte(donnees);
  });

  conteneur.addEventListener("dragstart", (e) => e.preventDefault());
  conteneur.setAttribute("contenteditable", "true");
  window.GARDE.prete = true;
})();
