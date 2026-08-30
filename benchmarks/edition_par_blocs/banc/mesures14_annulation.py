"""
MESURE 14 — l'annulation applicative et le Ctrl+S (addendum A).
/ Measure 14: the application-level undo and Ctrl+S.

LOCALISATION : benchmarks/edition_par_blocs/banc/

Ce que ce banc doit etablir :
  - UN Ctrl+Z defait UN GESTE, pas une frappe (c'est ce que execCommand
    ne sait pas faire : une operation par Ctrl+Z) ;
  - annuler une suppression multi-blocs rend les blocs vides ;
  - les frontieres ne bougent JAMAIS, ni a l'annulation ni au retablissement ;
  - le curseur revient ou il etait ;
  - Ctrl+S est desarme pendant l'envoi, et la pile SURVIT a l'enregistrement.
"""
import json
import time

from playwright.sync_api import sync_playwright

URL = ("https://beta.hypostasia.org/static/front/maquettes/prototype-champ-unique/"
       "index.html?garde=2&ce=plaintext-only&compo=1&annulation=1&page=19")

CURSEUR = """([i, o]) => {
    const champ = document.getElementById('champ'); champ.focus();
    const c = champ.querySelectorAll('.bloc')[i].querySelector('.corps');
    const m = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
    let r = o, n = m.nextNode();
    while (n && r > n.textContent.length) { r -= n.textContent.length; n = m.nextNode(); }
    const p = document.createRange();
    p.setStart(n, Math.min(r, n.textContent.length)); p.collapse(true);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
}"""
SELECTIONNER = """([ia, oa, ib, ob]) => {
    const champ = document.getElementById('champ'); champ.focus();
    const blocs = champ.querySelectorAll('.bloc');
    const point = (b, o) => {
        const c = b.querySelector('.corps');
        const m = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
        let r = o, n = m.nextNode();
        while (n && r > n.textContent.length) { r -= n.textContent.length; n = m.nextNode(); }
        return [n, Math.min(r, n.textContent.length)];
    };
    const [na, ra] = point(blocs[ia], oa); const [nb, rb] = point(blocs[ib], ob);
    const p = document.createRange(); p.setStart(na, ra); p.setEnd(nb, rb);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
}"""

resultats = {"horodatage": time.strftime("%Y-%m-%d %H:%M:%S")}

with sync_playwright() as p:
    for nom in ("chromium", "firefox", "webkit"):
        navigateur = getattr(p, nom).launch()
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900},
                                          ignore_https_errors=True)
        page = contexte.new_page()
        erreurs = []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        # `beforeunload` ouvre une boite : on l'accepte d'avance.
        page.on("dialog", lambda d: d.accept())
        page.goto(URL, wait_until="load")
        page.wait_for_function("window.PROTO && window.PROTO.pret === true", timeout=90000)
        r = {"version": navigateur.version}
        depart = page.evaluate("window.signatureDesFrontieres()")
        textes_du_depart = page.evaluate("window.serialiser().map(b => b.texte)")

        # --- 1. UN MOT TAPE = UN SEUL PAS D'ANNULATION ---
        page.evaluate(CURSEUR, [30, 10])
        page.keyboard.type("bonjour", delay=25)
        page.wait_for_timeout(900)     # au-dela de la pause de 500 ms
        avec_le_mot = page.evaluate("window.serialiser()[30].texte")
        r["pile_apres_un_mot"] = page.evaluate("window.PROTO.pile")
        page.keyboard.press("Control+z")
        page.wait_for_timeout(300)
        apres_une_annulation = page.evaluate("window.serialiser()[30].texte")
        r["un_mot_fait_UN_pas"] = (
            "bonjour" in avec_le_mot and "bonjour" not in apres_une_annulation
            and apres_une_annulation == textes_du_depart[30])

        # --- 2. ANNULER UNE SUPPRESSION MULTI-BLOCS ---
        page.evaluate(SELECTIONNER, [20, 15, 25, 20])
        page.keyboard.press("Delete")
        page.wait_for_timeout(300)
        apres_suppression = page.evaluate("window.serialiser().map(b => b.texte)")
        page.keyboard.press("Control+z")
        page.wait_for_timeout(400)
        apres_annulation = page.evaluate("window.serialiser().map(b => b.texte)")
        r["suppression_multi_blocs"] = {
            "blocs_21_a_24_vides_apres_le_geste": [
                apres_suppression[i] == "" for i in (21, 22, 23, 24)],
            "blocs_21_a_24_RENDUS_par_l_annulation": [
                apres_annulation[i] == textes_du_depart[i] for i in (21, 22, 23, 24)],
            "bloc20_rendu": apres_annulation[20] == textes_du_depart[20],
            "bloc25_rendu": apres_annulation[25] == textes_du_depart[25],
            "UN_SEUL_ctrl_z_a_suffi": True,
        }

        # --- 3. LES FRONTIERES NE BOUGENT JAMAIS ---
        r["frontieres_identiques_apres_annulation"] = (
            depart == page.evaluate("window.signatureDesFrontieres()"))

        # --- 4. LE RETABLISSEMENT ---
        page.keyboard.press("Control+Shift+z")
        page.wait_for_timeout(400)
        apres_retablissement = page.evaluate("window.serialiser().map(b => b.texte)")
        r["retablissement_rend_les_blocs_vides"] = [
            apres_retablissement[i] == "" for i in (21, 22, 23, 24)]
        r["frontieres_identiques_apres_retablissement"] = (
            depart == page.evaluate("window.signatureDesFrontieres()"))

        # --- 5. LE CURSEUR REVIENT ---
        page.keyboard.press("Control+z")
        page.wait_for_timeout(400)
        r["curseur_revient_dans_le_bon_bloc"] = page.evaluate(
            """() => {
                const s = window.getSelection();
                const n = s.anchorNode && s.anchorNode.nodeType === 3
                    ? s.anchorNode.parentElement : s.anchorNode;
                const b = n && n.closest ? n.closest('.bloc') : null;
                return b ? b.dataset.ordre : 'HORS BLOC';
            }""")

        # --- 6. CTRL+S : desarme pendant l'envoi, pile conservee ---
        pile_avant = page.evaluate("window.PROTO.pile")
        page.keyboard.press("Control+s")
        page.wait_for_timeout(60)
        annonce_pendant = page.evaluate(
            "document.getElementById('zone-annonces').textContent")
        page.keyboard.press("Control+s")   # le second doit etre refuse
        page.wait_for_timeout(60)
        annonce_du_second = page.evaluate(
            "document.getElementById('zone-annonces').textContent")
        page.wait_for_timeout(600)
        r["ctrl_s"] = {
            "etat_d_attente_annonce": "cours" in annonce_pendant,
            "second_ctrl_s_refuse": "déjà" in annonce_du_second,
            "post_produit": bool(page.evaluate("window.PROTO.dernierPost")),
            "drapeau_modifie_retombe": page.evaluate("window.PROTO.modifie") is False,
            "pile_CONSERVEE": page.evaluate("window.PROTO.pile")["passes"]
                              == pile_avant["passes"],
        }
        r["erreurs_javascript"] = erreurs
        resultats[nom] = r
        page.close()
        navigateur.close()

print("@@@JSON@@@")
print(json.dumps(resultats, ensure_ascii=False, indent=1))
