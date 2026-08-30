"""
LE MODE D'EDITION, sur la vraie application.
Aucune ECRITURE en base : on n'appuie pas sur Ctrl+S ici.
"""
import json
from playwright.sync_api import sync_playwright

BASE = "https://beta.hypostasia.org"
SIGNATURE = """() => Array.from(
    document.querySelectorAll('[data-testid=blocs-elements] .bloc[data-element]')
).map(b => b.dataset.element)"""

def selectionner(page, ia, oa, ib, ob):
    page.evaluate("""([ia, oa, ib, ob]) => {
        const c = document.querySelector('[data-testid=blocs-elements]');
        c.focus();
        const blocs = c.querySelectorAll('.bloc');
        const point = (b, o) => {
            const corps = b.querySelector('.corps');
            const m = document.createTreeWalker(corps, NodeFilter.SHOW_TEXT);
            let r = o, n = m.nextNode();
            while (n && r > n.textContent.length) { r -= n.textContent.length; n = m.nextNode(); }
            return [n, Math.min(r, n.textContent.length)];
        };
        const [na, ra] = point(blocs[ia], oa);
        const [nb, rb] = point(blocs[ib], ob);
        const p = document.createRange(); p.setStart(na, ra); p.setEnd(nb, rb);
        const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
    }""", [ia, oa, ib, ob])

sortie = {}
with sync_playwright() as p:
    for nom in ("chromium", "firefox", "webkit"):
        n = getattr(p, nom).launch()
        c = n.new_context(viewport={"width": 1400, "height": 1000}, ignore_https_errors=True)
        page = c.new_page()
        erreurs = []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.goto(f"{BASE}/auth/login/", wait_until="networkidle")
        page.fill("input[name=username]", "jonas")
        page.fill("input[name=password]", "admin1234")
        page.click("button[type=submit], input[type=submit]")
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE}/lire/21/", wait_until="networkidle")
        page.wait_for_timeout(1800)
        page.evaluate("""() => {
            const d = document.getElementById('message-d-accueil'); if (d) d.remove();
            if (window.drawerVueListe && window.drawerVueListe.fermer) window.drawerVueListe.fermer();
        }""")
        page.wait_for_timeout(400)
        r = {"version": n.version}
        r["bouton_present"] = page.query_selector('[data-testid="bouton-mode-edition"]') is not None
        r["bouton_actif"] = page.evaluate(
            """() => { const b = document.querySelector('[data-testid=bouton-mode-edition]');
                       return b ? !b.disabled : null; }""")
        depart = page.evaluate(SIGNATURE)
        r["blocs"] = len(depart)

        # --- ouvrir ---
        page.click('[data-testid="bouton-mode-edition"]')
        page.wait_for_timeout(600)
        r["ouverture"] = page.evaluate(
            """() => ({
                classe: document.getElementById('zone-lecture').classList.contains('mode-edition'),
                contenteditable: document.querySelector('[data-testid=blocs-elements]').contentEditable,
                aria_pressed: document.querySelector('[data-testid=bouton-mode-edition]').getAttribute('aria-pressed'),
                gouttiere_hors_champ: document.querySelector('.gouttiere').getAttribute('contenteditable'),
                annonce: document.getElementById('zone-annonces').textContent.slice(0, 40),
            })""")

        # --- le geste decisif : frappe de remplacement multi-blocs ---
        selectionner(page, 20, 15, 25, 20)
        page.keyboard.type("A")
        page.wait_for_timeout(400)
        r["frappe_de_remplacement"] = {
            "blocs_apres": len(page.evaluate(SIGNATURE)),
            "frontieres_identiques": depart == page.evaluate(SIGNATURE),
        }

        # --- Ctrl+Z : un geste, un pas ---
        page.keyboard.press("Control+z")
        page.wait_for_timeout(400)
        r["ctrl_z"] = {
            "blocs": len(page.evaluate(SIGNATURE)),
            "annonce": page.evaluate("document.getElementById('zone-annonces').textContent")[:40],
        }

        # --- Ctrl+A puis frappe ---
        page.evaluate("""() => document.querySelector('[data-testid=blocs-elements]').focus()""")
        page.keyboard.press("Control+a")
        page.keyboard.type("B")
        page.wait_for_timeout(400)
        r["ctrl_a_puis_frappe"] = {
            "blocs": len(page.evaluate(SIGNATURE)),
            "gouttieres": page.evaluate(
                "document.querySelectorAll('[data-testid=blocs-elements] .gouttiere').length"),
        }

        # --- Echap sort du mode ---
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        r["echap_sort"] = page.evaluate(
            """() => ({
                mode_ferme: !document.getElementById('zone-lecture').classList.contains('mode-edition'),
                contenteditable: document.querySelector('[data-testid=blocs-elements]').getAttribute('contenteditable'),
                aria_pressed: document.querySelector('[data-testid=bouton-mode-edition]').getAttribute('aria-pressed'),
                annonce: document.getElementById('zone-annonces').textContent.slice(0, 60),
            })""")
        r["erreurs_javascript"] = erreurs
        sortie[nom] = r
        page.close(); n.close()
print("@@@JSON@@@")
print(json.dumps(sortie, ensure_ascii=False, indent=1))
