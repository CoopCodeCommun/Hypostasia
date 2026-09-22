"""
MESURE 11 — la promesse fondatrice de l'option C, sur TROIS moteurs.
/ Measure 11: option C's founding promise, on THREE engines.

LOCALISATION : benchmarks/edition_par_blocs/banc/

C'est la derniere des mesures « navigateur » qui conditionnaient la
decision. Tout le prototype a ete mesure sur Chromium seul ; or ce dont
l'option C depend — une selection qui TRAVERSE des ilots
`contenteditable="false"` — est notoirement divergent entre moteurs.

Prealable : `python -m playwright install-deps firefox webkit` en root
dans le conteneur (les binaires y etaient deja, seules les dependances
systeme manquaient).
"""
import json
import os
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get(
    "BASE",
    "https://beta.hypostasia.org/static/front/maquettes/prototype-champ-unique/index.html",
)

SELECTIONNER = """([ia, oa, ib, ob]) => {
    const champ = document.getElementById('champ');
    champ.focus();
    const blocs = champ.querySelectorAll('.bloc');
    const point = (b, o) => {
        const c = b.querySelector('.corps');
        const m = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
        let r = o, n = m.nextNode();
        while (n && r > n.textContent.length) { r -= n.textContent.length; n = m.nextNode(); }
        return [n, Math.min(r, n.textContent.length)];
    };
    const [na, ra] = point(blocs[ia], oa);
    const [nb, rb] = point(blocs[ib], ob);
    const p = document.createRange();
    p.setStart(na, ra); p.setEnd(nb, rb);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
}"""

CURSEUR = """([i, o]) => {
    const champ = document.getElementById('champ');
    champ.focus();
    const c = champ.querySelectorAll('.bloc')[i].querySelector('.corps');
    const m = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
    let r = o, n = m.nextNode();
    while (n && r > n.textContent.length) { r -= n.textContent.length; n = m.nextNode(); }
    const p = document.createRange();
    p.setStart(n, Math.min(r, n.textContent.length)); p.collapse(true);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
}"""

BLOC_COURANT = """() => {
    const s = window.getSelection();
    const n = s.anchorNode && s.anchorNode.nodeType === 3
        ? s.anchorNode.parentElement : s.anchorNode;
    const b = n && n.closest ? n.closest('.bloc') : null;
    return b ? b.dataset.ordre : 'HORS BLOC';
}"""

resultats = {"horodatage": time.strftime("%Y-%m-%d %H:%M:%S"), "adresse": BASE}


def ouvrir(moteur, ce="true", garde="2"):
    page = moteur.new_page()
    page.goto(f"{BASE}?ce={ce}&garde={garde}&page=19", wait_until="load")
    page.wait_for_function("window.PROTO && window.PROTO.pret === true", timeout=90000)
    return page


with sync_playwright() as p:
    for nom in ("chromium", "firefox", "webkit"):
        bloc_de_resultats = {}
        navigateur = getattr(p, nom).launch()
        bloc_de_resultats["version"] = navigateur.version
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900},
                                          ignore_https_errors=True)

        # --- A. LA PROMESSE FONDATRICE : traverser les gouttieres ---
        page = ouvrir(contexte)
        page.evaluate(CURSEUR, [0, 5])
        depart = page.evaluate(BLOC_COURANT)
        for _ in range(8):
            page.keyboard.press("ArrowDown")
        arrivee = page.evaluate(BLOC_COURANT)
        bloc_de_resultats["fleche_bas_traverse"] = depart != arrivee
        bloc_de_resultats["bloc_depart_arrivee"] = [depart, arrivee]

        page.evaluate(CURSEUR, [1, 5])
        for _ in range(8):
            page.keyboard.press("Shift+ArrowDown")
        bloc_de_resultats["maj_bas_etend_a_travers"] = page.evaluate(
            """() => {
                const s = window.getSelection();
                const b = (n) => {
                    const e = n && n.nodeType === 3 ? n.parentElement : n;
                    return e && e.closest ? e.closest('.bloc') : null;
                };
                return b(s.anchorNode) !== b(s.focusNode);
            }""")
        bloc_de_resultats["la_gouttiere_entre_dans_la_selection"] = page.evaluate(
            """() => {
                const t = window.getSelection().toString();
                const g = document.querySelectorAll('.gouttiere')[2].textContent.trim();
                return g.length > 0 && t.includes(g);
            }""")

        page.evaluate(CURSEUR, [0, 5])
        page.keyboard.press("Control+End")
        bloc_de_resultats["ctrl_fin_va_au_dernier"] = page.evaluate(
            """() => {
                const s = window.getSelection();
                const n = s.anchorNode && s.anchorNode.nodeType === 3
                    ? s.anchorNode.parentElement : s.anchorNode;
                const b = n && n.closest ? n.closest('.bloc') : null;
                const tous = document.querySelectorAll('.bloc');
                return b === tous[tous.length - 1];
            }""")
        page.close()

        # --- B. LES GESTES SOUS LA GARDE `beforeinput` ---
        for etiquette, geste in (
            ("suppression_traversante", lambda pg: pg.keyboard.press("Delete")),
            ("frappe_de_remplacement", lambda pg: pg.keyboard.type("A")),
        ):
            for garde in ("2", "0"):
                page = ouvrir(contexte, garde=garde)
                avant = page.evaluate("window.signatureDesFrontieres()")
                page.evaluate(SELECTIONNER, [20, 15, 25, 20])
                geste(page)
                page.wait_for_timeout(400)
                apres = page.evaluate("window.signatureDesFrontieres()")
                bloc_de_resultats[f"{etiquette}_garde_{garde}"] = {
                    "frontieres_identiques": avant == apres,
                    "blocs_avant": len(avant), "blocs_apres": len(apres),
                }
                page.close()

        # --- C. plaintext-only, et le piege de getTargetRanges ---
        page = ouvrir(contexte, ce="plaintext-only", garde="0")
        bloc_de_resultats["plaintext_only_accepte"] = page.evaluate(
            "window.PROTO.mesures.contenteditable_propriete") == "plaintext-only"
        page.evaluate(
            """() => {
                window.SONDE = [];
                document.getElementById('champ').addEventListener('beforeinput', (e) => {
                    const pl = e.getTargetRanges();
                    window.SONDE.push({type: e.inputType,
                                       plages_rendues: pl ? pl.length : -1,
                                       annulable: e.cancelable});
                }, true);
            }""")
        page.evaluate(SELECTIONNER, [14, 10, 16, 10])
        page.keyboard.type("A")
        page.wait_for_timeout(300)
        bloc_de_resultats["getTargetRanges_sous_plaintext_only"] = page.evaluate(
            "window.SONDE")[:2]
        page.close()

        # --- D. la meme sonde sous contenteditable="true", pour comparer ---
        page = ouvrir(contexte, ce="true", garde="0")
        page.evaluate(
            """() => {
                window.SONDE = [];
                document.getElementById('champ').addEventListener('beforeinput', (e) => {
                    const pl = e.getTargetRanges();
                    window.SONDE.push({type: e.inputType,
                                       plages_rendues: pl ? pl.length : -1,
                                       annulable: e.cancelable});
                }, true);
            }""")
        page.evaluate(SELECTIONNER, [14, 10, 16, 10])
        page.keyboard.type("A")
        page.wait_for_timeout(300)
        bloc_de_resultats["getTargetRanges_sous_true"] = page.evaluate("window.SONDE")[:2]
        page.close()

        navigateur.close()
        resultats[nom] = bloc_de_resultats

print("@@@JSON@@@")
print(json.dumps(resultats, ensure_ascii=False, indent=1))
