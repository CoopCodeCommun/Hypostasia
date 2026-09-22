"""
BANC, neuvieme volet — `getTargetRanges()` MENT-IL SOUS plaintext-only ?
/ Ninth bench: does getTargetRanges() lie under plaintext-only?

LOCALISATION : scratchpad de session, HORS DEPOT.

Le volet 8 a montre qu'un collage traversant, sous `plaintext-only` ET la
garde `beforeinput`, DETRUIT un bloc — alors que la meme garde tient sous
`contenteditable="true"`. Le journal dit pourquoi : `getTargetRanges()`
annonce `traverse: false`.

Ici on confronte, au moment exact du `beforeinput`, ce que disent :
  - `getTargetRanges()` — sur quoi la garde s'appuie ;
  - `window.getSelection()` — ce que l'utilisateur a reellement selectionne.
"""
import json
import time

from playwright.sync_api import sync_playwright

ADRESSE = "http://127.0.0.1:8899/prototype.html"
resultats = {}

SONDE = """() => {
    window.SONDE = [];
    const bloc = (n) => {
        const e = n && n.nodeType === 3 ? n.parentElement : n;
        const b = e && e.closest ? e.closest('.bloc') : null;
        return b ? b.dataset.ordre : 'HORS';
    };
    document.getElementById('champ').addEventListener('beforeinput', (e) => {
        const plages = e.getTargetRanges();
        const p = plages && plages.length ? plages[0] : null;
        const s = window.getSelection();
        window.SONDE.push({
            type: e.inputType,
            cible_debut: p ? bloc(p.startContainer) : null,
            cible_fin: p ? bloc(p.endContainer) : null,
            cible_traverse: p ? bloc(p.startContainer) !== bloc(p.endContainer) : null,
            selection_debut: bloc(s.anchorNode),
            selection_fin: bloc(s.focusNode),
            selection_traverse: bloc(s.anchorNode) !== bloc(s.focusNode),
            selection_repliee: s.isCollapsed,
        });
    }, true);
}"""


def charge():
    with open("/proc/loadavg") as f:
        return f.read().split()[0:3]


def selectionner_entre(page, ia, oa, ib, ob):
    page.evaluate(
        """([ia, oa, ib, ob]) => {
            const champ = document.getElementById('champ');
            champ.focus();
            const blocs = champ.querySelectorAll('.bloc');
            const point = (bloc, offset) => {
                const corps = bloc.querySelector('.corps');
                const m = document.createTreeWalker(corps, NodeFilter.SHOW_TEXT);
                let reste = offset, n = m.nextNode();
                while (n && reste > n.textContent.length) { reste -= n.textContent.length; n = m.nextNode(); }
                return [n, Math.min(reste, n.textContent.length)];
            };
            const [na, ra] = point(blocs[ia], oa);
            const [nb, rb] = point(blocs[ib], ob);
            const p = document.createRange();
            p.setStart(na, ra); p.setEnd(nb, rb);
            const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
        }""", [ia, oa, ib, ob])


def principal():
    resultats["horodatage"] = time.strftime("%Y-%m-%d %H:%M:%S")
    resultats["charge_au_debut"] = charge()
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        resultats["navigateur"] = "Chromium " + navigateur.version
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900})
        contexte.grant_permissions(["clipboard-read", "clipboard-write"])
        for ce in ("true", "plaintext-only"):
            for geste in ("collage", "frappe", "suppression"):
                page = contexte.new_page()
                # garde=0 : on OBSERVE, on n'intervient pas.
                # / garde=0: observe, do not intervene.
                page.goto(f"{ADRESSE}?ce={ce}&garde=0&page=19")
                page.wait_for_function("window.PROTO && window.PROTO.pret === true",
                                       timeout=60000)
                page.evaluate(SONDE)
                if geste == "collage":
                    page.evaluate(
                        """async () => {
                            const item = new ClipboardItem({
                                'text/html': new Blob(['<p>UN</p><p>DEUX</p>'], {type: 'text/html'}),
                                'text/plain': new Blob(['UN\\n\\nDEUX'], {type: 'text/plain'}),
                            });
                            await navigator.clipboard.write([item]);
                        }"""
                    )
                selectionner_entre(page, 14, 10, 16, 10)
                if geste == "collage":
                    page.keyboard.press("Control+v")
                elif geste == "frappe":
                    page.keyboard.type("A")
                else:
                    page.keyboard.press("Delete")
                page.wait_for_timeout(300)
                resultats[f"ce={ce}_{geste}"] = page.evaluate("window.SONDE")[:3]
                page.close()
        navigateur.close()
    resultats["charge_a_la_fin"] = charge()
    with open("/tmp/proto/resultats-volet9.json", "w") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=1)
    print("OK — resultats-volet9.json")


if __name__ == "__main__":
    principal()
