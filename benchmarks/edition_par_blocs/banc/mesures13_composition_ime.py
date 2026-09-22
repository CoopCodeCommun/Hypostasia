"""
MESURE 13 — la composition IME sur une selection multi-blocs.
/ Measure 13: IME composition over a multi-block selection.

LOCALISATION : benchmarks/edition_par_blocs/banc/

C'est la DERNIERE des trois mesures qui conditionnaient la decision.

LE PROBLEME, ETABLI : `insertCompositionText` arrive avec
`cancelable: false`. La garde `beforeinput` le voit passer et ne peut rien
en faire. Une composition qui remplace une selection multi-blocs detruit
donc des blocs MALGRE la garde — et sur Android, toute frappe est une
composition.

LA PARADE A EPROUVER : ne pas essayer d'arreter la composition, mais lui
retirer sa matiere. `compositionstart` arrive AVANT toute ecriture, et la
selection y est encore celle de l'utilisateur : on vide bloc par bloc et
on replie le curseur dans un seul bloc.

CE QUE CE BANC PEUT ET NE PEUT PAS FAIRE
Une VRAIE composition se declenche par CDP (`Input.imeSetComposition`),
donc **sur Chromium seulement** — Playwright n'expose pas d'equivalent
pour Firefox ni WebKit. Sur ces deux-la, on ne peut qu'observer si le
gestionnaire s'arme et si les evenements de composition synthetiques le
declenchent : c'est la moitie de la reponse, et elle est dite comme telle.
"""
import json
import time

from playwright.sync_api import sync_playwright

BASE = ("https://beta.hypostasia.org/static/front/maquettes/"
        "prototype-champ-unique/index.html")

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

resultats = {"horodatage": time.strftime("%Y-%m-%d %H:%M:%S")}


def ouvrir(contexte, compo, garde="2"):
    page = contexte.new_page()
    page.goto(f"{BASE}?ce=true&garde={garde}&page=19&compo={compo}",
              wait_until="load")
    page.wait_for_function("window.PROTO && window.PROTO.pret === true", timeout=90000)
    return page


with sync_playwright() as p:
    # --- A. LA VRAIE COMPOSITION, sur Chromium (CDP) ---
    navigateur = p.chromium.launch()
    contexte = navigateur.new_context(viewport={"width": 1280, "height": 900},
                                      ignore_https_errors=True)
    for compo in ("0", "1"):
        page = ouvrir(contexte, compo)
        session = page.context.new_cdp_session(page)
        avant = page.evaluate("window.signatureDesFrontieres()")
        gouttieres_avant = page.evaluate(
            "document.querySelectorAll('#champ .gouttiere').length")
        page.evaluate(SELECTIONNER, [20, 15, 25, 20])
        # Une composition en trois temps, puis sa validation.
        # / A three-step composition, then its commit.
        session.send("Input.imeSetComposition",
                     {"text": "に", "selectionStart": 1, "selectionEnd": 1})
        page.wait_for_timeout(80)
        session.send("Input.imeSetComposition",
                     {"text": "にほん", "selectionStart": 3, "selectionEnd": 3})
        page.wait_for_timeout(80)
        session.send("Input.insertText", {"text": "日本"})
        page.wait_for_timeout(400)
        apres = page.evaluate("window.signatureDesFrontieres()")
        textes = page.evaluate("window.serialiser().map(b => b.texte)")
        resultats[f"chromium_vraie_composition_parade_{compo}"] = {
            "parade_active": page.evaluate("window.PROTO.mesures.parade_composition"),
            "frontieres_identiques": avant == apres,
            "blocs_avant_apres": [len(avant), len(apres)],
            "gouttieres_avant_apres": [
                gouttieres_avant,
                page.evaluate("document.querySelectorAll('#champ .gouttiere').length"),
            ],
            "compositions_vues": page.evaluate("window.PROTO.compositionsVues || 0"),
            "compositions_normalisees": page.evaluate(
                "window.PROTO.compositionsNormalisees || 0"),
            "le_texte_compose_est_arrive": any(
                "日本" in (t or "") for t in textes),
            "bloc20_apres": (textes[20] or "")[:55] if len(textes) > 20 else None,
            "geste_non_annulable_signale": page.evaluate(
                "window.PROTO.gesteNonAnnulable || null"),
        }
        page.close()
    navigateur.close()

    # --- B. LE GESTIONNAIRE S'ARME-T-IL SUR LES TROIS MOTEURS ? ---
    #     (evenements de composition SYNTHETIQUES : ils ne modifient pas
    #      le DOM, ils disent seulement si le gestionnaire est atteint.)
    for nom in ("chromium", "firefox", "webkit"):
        navigateur = getattr(p, nom).launch()
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900},
                                          ignore_https_errors=True)
        page = ouvrir(contexte, "1")
        avant = page.evaluate("window.signatureDesFrontieres()")
        page.evaluate(SELECTIONNER, [20, 15, 25, 20])
        page.evaluate(
            """() => {
                document.getElementById('champ').dispatchEvent(
                    new CompositionEvent('compositionstart', {bubbles: true}));
            }""")
        page.wait_for_timeout(300)
        apres = page.evaluate("window.signatureDesFrontieres()")
        textes = page.evaluate("window.serialiser().map(b => b.texte)")
        resultats[f"{nom}_compositionstart_synthetique"] = {
            "version": navigateur.version,
            "gestionnaire_atteint": page.evaluate(
                "(window.PROTO.compositionsVues || 0) > 0"),
            "selection_normalisee": page.evaluate(
                "(window.PROTO.compositionsNormalisees || 0) > 0"),
            "frontieres_identiques": avant == apres,
            "blocs_21_a_24_vides": [
                (textes[i] or "") == "" for i in (21, 22, 23, 24)
            ] if len(textes) > 24 else None,
        }
        page.close()
        navigateur.close()

print("@@@JSON@@@")
print(json.dumps(resultats, ensure_ascii=False, indent=1))
