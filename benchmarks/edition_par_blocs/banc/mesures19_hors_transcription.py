"""
Le mode d'edition sur des documents QUI NE SONT PAS des transcriptions :
tableaux, images, legendes, code. AUCUNE ECRITURE : on ne fait pas Ctrl+S.
"""
import json
from playwright.sync_api import sync_playwright

BASE = "https://beta.hypostasia.org"
ATTENDUS = json.load(open("/tmp/attendus-non-textuels.json"))
sortie = {}
with sync_playwright() as p:
    n = p.chromium.launch()
    c = n.new_context(viewport={"width": 1440, "height": 1000}, ignore_https_errors=True)
    page = c.new_page()
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    page.goto(f"{BASE}/auth/login/", wait_until="networkidle")
    page.fill("input[name=username]", "jonas")
    page.fill("input[name=password]", "admin1234")
    page.click("button[type=submit], input[type=submit]")
    page.wait_for_load_state("networkidle")

    for pid in ("2", "5", "10"):
        page.goto(f"{BASE}/lire/{pid}/", wait_until="networkidle")
        page.wait_for_timeout(1800)
        page.evaluate("""() => { const d=document.getElementById('message-d-accueil'); if(d) d.remove(); }""")
        page.click('[data-testid="bouton-mode-edition"]')
        page.wait_for_timeout(900)
        # Ce que le mode ENVERRAIT, sans l'envoyer.
        charge = page.evaluate("""() => {
            const champ = document.querySelector('[data-testid=blocs-elements]');
            const out = [];
            champ.querySelectorAll('.bloc[data-element]').forEach(b => {
                const corps = b.querySelector('.corps');
                const i = corps ? corps.querySelector('[data-element-id]') : null;
                let texte = null;
                if (i) {
                    const c = i.cloneNode(true);
                    c.querySelectorAll('.actions-element').forEach(x => x.remove());
                    texte = c.textContent;
                }
                out.push({id: b.dataset.element, label: b.dataset.label, texte: texte,
                          fige: b.dataset.lectureSeule === 'oui',
                          modifiable: corps ? corps.isContentEditable : null});
            });
            return out;
        }""")
        envoyes = page.evaluate("window.__envoi = null; true")
        page.evaluate('''() => {
            // Ce que le mode enverrait VRAIMENT, par sa propre fonction.
            const champ = document.querySelector('[data-testid=blocs-elements]');
            window.__envoi = [];
            champ.querySelectorAll('.bloc[data-element]').forEach(b => {
                if (b.dataset.lectureSeule === 'oui') return;
                window.__envoi.push(b.dataset.element);
            });
        }''')
        envoyes = set(page.evaluate("window.__envoi"))
        attendus = ATTENDUS[pid]
        par_label = {}
        exemples = []
        for bloc in charge:
            a = attendus.get(bloc["id"])
            if not a:
                continue
            label = a["label"]
            par_label.setdefault(label, {"n": 0, "exact": 0, "different": 0,
                                         "sans_element": 0})
            par_label[label]["n"] += 1
            if bloc["texte"] is None:
                par_label[label]["sans_element"] += 1
            elif bloc["texte"] == a["texte"]:
                par_label[label]["exact"] += 1
            else:
                par_label[label]["different"] += 1
                if len(exemples) < 3:
                    exemples.append({"label": label,
                                     "en_base": a["texte"][:70],
                                     "ce_qui_partirait": (bloc["texte"] or "")[:70]})
        figes = [b for b in charge if b.get("fige")]
        tables_envoyees = [b for b in charge
                           if attendus.get(b["id"], {}).get("label") == "table"
                           and b["id"] in envoyes]
        sortie[f"page_{pid}"] = {
            "par_label": par_label, "blocs": len(charge),
            "blocs_figes": len(figes),
            "corps_non_modifiable": sum(1 for b in figes if b["modifiable"] is False),
            "TABLEAUX_ENVOYES": len(tables_envoyees),
        }
    sortie["erreurs_javascript"] = erreurs
    page.close(); n.close()
print("@@@JSON@@@")
print(json.dumps(sortie, ensure_ascii=False, indent=1))
