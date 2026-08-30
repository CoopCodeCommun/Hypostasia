"""
BANC, huitieme volet — LE COLLAGE SOUS LA GARDE `beforeinput`.
/ Eighth bench: pasting under the beforeinput guard.

LOCALISATION : scratchpad de session, HORS DEPOT.

Une relecture adverse a vu ce que le banc n'avait pas mesure : la garde 2
laisse passer NATIVEMENT tout geste qui ne traverse pas. Un collage de
HTML riche a l'interieur d'UN SEUL bloc n'est donc pas nettoye par elle.
On le mesure, avec `contenteditable="true"` puis `plaintext-only`.
"""
import json
import time

from playwright.sync_api import sync_playwright

ADRESSE = "http://127.0.0.1:8899/prototype.html"
resultats = {}


def charge():
    with open("/proc/loadavg") as f:
        return f.read().split()[0:3]


def poser_le_curseur(page, i, offset):
    page.evaluate(
        """([i, offset]) => {
            const champ = document.getElementById('champ');
            champ.focus();
            const corps = champ.querySelectorAll('.bloc')[i].querySelector('.corps');
            const m = document.createTreeWalker(corps, NodeFilter.SHOW_TEXT);
            let reste = offset, n = m.nextNode();
            while (n && reste > n.textContent.length) { reste -= n.textContent.length; n = m.nextNode(); }
            const p = document.createRange();
            p.setStart(n, Math.min(reste, n.textContent.length)); p.collapse(true);
            const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
        }""", [i, offset])


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


def etat(page, i):
    return page.evaluate(
        """(i) => {
            const c = document.querySelectorAll('.bloc')[i].querySelector('.corps');
            return {enfants: c.children.length,
                    balises: Array.from(c.children).map(e => e.tagName.toLowerCase()),
                    html: c.innerHTML.slice(0, 200)};
        }""", i)


def principal():
    resultats["horodatage"] = time.strftime("%Y-%m-%d %H:%M:%S")
    resultats["charge_au_debut"] = charge()
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        resultats["navigateur"] = "Chromium " + navigateur.version
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900})
        contexte.grant_permissions(["clipboard-read", "clipboard-write"])

        for ce in ("true", "plaintext-only"):
            for traversant in (False, True):
                page = contexte.new_page()
                page.goto(f"{ADRESSE}?ce={ce}&garde=2&page=19")
                page.wait_for_function("window.PROTO && window.PROTO.pret === true",
                                       timeout=60000)
                avant = page.evaluate("window.signatureDesFrontieres()")
                page.evaluate(
                    """async () => {
                        const item = new ClipboardItem({
                            'text/html': new Blob(
                                ['<h1>TITRE</h1><p><b>gras</b> et <i>italique</i></p><p>second</p>'],
                                {type: 'text/html'}),
                            'text/plain': new Blob(['TITRE\\n\\ngras et italique\\n\\nsecond'],
                                {type: 'text/plain'}),
                        });
                        await navigator.clipboard.write([item]);
                    }"""
                )
                if traversant:
                    selectionner_entre(page, 14, 10, 16, 10)
                else:
                    poser_le_curseur(page, 14, 10)
                page.keyboard.press("Control+v")
                page.wait_for_timeout(300)
                apres = etat(page, 14)
                cle = f"ce={ce}_{'traversant' if traversant else 'mono_bloc'}"
                resultats[cle] = {
                    "frontieres_identiques": avant == page.evaluate(
                        "window.signatureDesFrontieres()"),
                    "blocs_apres": len(page.evaluate("window.signatureDesFrontieres()")),
                    "enfants_du_corps": apres["enfants"],
                    "balises": apres["balises"],
                    "style_survivant": any(
                        b in apres["html"] for b in ("<b>", "<i>", "<h1>", "<strong>", "<em>")),
                    "html": apres["html"],
                    "journal_beforeinput": page.evaluate(
                        "window.PROTO.journalBeforeInput || []")[:3],
                }
                page.close()
        navigateur.close()
    resultats["charge_a_la_fin"] = charge()
    with open("/tmp/proto/resultats-volet8.json", "w") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=1)
    print("OK — resultats-volet8.json")


if __name__ == "__main__":
    principal()
