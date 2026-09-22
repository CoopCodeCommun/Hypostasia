"""
MESURE 10 — l'option C sur le VRAI DOM de l'ecran de lecture.
/ Measure 10: option C against the REAL reading screen DOM.

LOCALISATION : benchmarks/edition_par_blocs/banc/

C'est la deuxieme des trois mesures qui conditionnent la decision. Le
prototype tournait sur une REPLIQUE du gabarit ; ici on ouvre la vraie
page servie par Django, on y injecte la garde, et on rejoue les gestes.

Ce qu'on cherche, et que la replique ne pouvait pas dire :
  - `.corps.textContent` prend-il les BLANCS d'indentation du gabarit ?
  - les quatre boutons de `_actions_element.html`, rendus DANS le `<p>`,
    polluent-ils la serialisation ?
  - les frontieres tiennent-elles sur un DOM qui porte aussi des
    gouttieres a boutons, des `.element-masque` et de vrais `<table>` ?

AUCUNE ECRITURE : la garde n'appelle aucun endpoint, elle ne fait que
manipuler le DOM du navigateur.
"""
import json
import os
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "https://beta.hypostasia.org")
PAGE = int(os.environ.get("PAGE", "21"))
IDENTIFIANT = os.environ.get("UTILISATEUR", "jonas")
MOTDEPASSE = os.environ.get("MOTDEPASSE", "admin1234")

with open(os.path.join(os.path.dirname(__file__), "garde_sur_le_vrai_dom.js")) as f:
    GARDE = f.read()

# Les textes attendus, extraits de la base (lecture seule) par l'appelant.
with open("/tmp/textes-attendus.json") as f:
    TEXTES_ATTENDUS = json.load(f)

resultats = {"base": BASE, "page": PAGE,
             "horodatage": time.strftime("%Y-%m-%d %H:%M:%S")}

with sync_playwright() as p:
    navigateur = p.chromium.launch()
    contexte = navigateur.new_context(viewport={"width": 1400, "height": 1000},
                                      ignore_https_errors=True)
    page = contexte.new_page()
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))

    page.goto(f"{BASE}/auth/login/", wait_until="networkidle")
    page.fill("input[name=username]", IDENTIFIANT)
    page.fill("input[name=password]", MOTDEPASSE)
    page.click("button[type=submit], input[type=submit]")
    page.wait_for_load_state("networkidle")

    # Une connexion qui echoue en silence fausse tout : le premier
    # passage de ce banc a mesure la page en ANONYME sans le dire, et les
    # boutons d'action, qui sont l'objet de la mesure, etaient absents.
    # / A silently failed login ruined the first run: verify it.
    resultats["connexion_reussie"] = any(
        k["name"] == "sessionid" for k in contexte.cookies())
    if not resultats["connexion_reussie"]:
        raise SystemExit("CONNEXION ECHOUEE — mesure abandonnee")

    page.goto(f"{BASE}/lire/{PAGE}/", wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.evaluate("""() => {
        const d = document.getElementById('message-d-accueil');
        if (d) d.remove();
    }""")
    page.evaluate(GARDE)
    resultats["garde_prete"] = page.evaluate("window.GARDE && window.GARDE.prete === true")
    resultats["blocs_dans_le_vrai_dom"] = page.evaluate(
        "document.querySelectorAll('[data-testid=blocs-elements] .bloc[data-element]').length")
    resultats["boutons_d_action_presents"] = page.evaluate(
        "document.querySelectorAll('.actions-element').length")

    # --- 1. LES DEUX SERIALISATIONS, comparees au texte de la base ---
    verdict = page.evaluate(
        """(attendus) => {
            const parCorps = window.serialiserParLeCorps();
            const parInterne = window.serialiserParLElementInterne();
            const compter = (liste) => {
                let exacts = 0, differents = 0;
                const exemples = [];
                for (const bloc of liste) {
                    const attendu = attendus[bloc.identifiant_stable];
                    if (attendu === undefined) continue;
                    if (bloc.texte === attendu) { exacts += 1; }
                    else {
                        differents += 1;
                        if (exemples.length < 2) {
                            exemples.push({attendu: attendu.slice(0, 40),
                                           obtenu: (bloc.texte || '').slice(0, 60)});
                        }
                    }
                }
                return {exacts, differents, exemples};
            };
            return {par_le_corps: compter(parCorps),
                    par_l_element_interne: compter(parInterne)};
        }""", TEXTES_ATTENDUS)
    resultats["serialisation"] = verdict

    # --- 2. LES GESTES, sur le vrai DOM ---
    def signature():
        return page.evaluate("window.signatureDesFrontieres()")

    def selectionner(ia, oa, ib, ob):
        page.evaluate(
            """([ia, oa, ib, ob]) => {
                const c = document.querySelector('[data-testid="blocs-elements"]');
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
                const pl = document.createRange();
                pl.setStart(na, ra); pl.setEnd(nb, rb);
                const s = window.getSelection(); s.removeAllRanges(); s.addRange(pl);
            }""", [ia, oa, ib, ob])

    gestes = {}
    avant = signature()

    selectionner(20, 15, 25, 20)
    page.keyboard.type("A")
    page.wait_for_timeout(300)
    gestes["frappe_de_remplacement_20_a_25"] = {
        "frontieres_identiques": avant == signature(),
        "blocs_avant": len(avant), "blocs_apres": len(signature()),
    }

    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.evaluate("""() => { const d = document.getElementById('message-d-accueil'); if (d) d.remove(); }""")
    page.evaluate(GARDE)
    avant2 = signature()
    page.evaluate("""() => document.querySelector('[data-testid="blocs-elements"]').focus()""")
    page.keyboard.press("Control+a")
    page.keyboard.type("A")
    page.wait_for_timeout(400)
    gestes["tout_selectionner_puis_frappe"] = {
        "frontieres_identiques": avant2 == signature(),
        "blocs_avant": len(avant2), "blocs_apres": len(signature()),
        "gouttieres_restantes": page.evaluate(
            "document.querySelectorAll('[data-testid=blocs-elements] .gouttiere').length"),
    }

    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.evaluate("""() => { const d = document.getElementById('message-d-accueil'); if (d) d.remove(); }""")
    page.evaluate(GARDE)
    avant3 = signature()
    selectionner(20, 15, 25, 20)
    page.keyboard.press("Delete")
    page.wait_for_timeout(300)
    gestes["suppression_20_a_25"] = {
        "frontieres_identiques": avant3 == signature(),
        "blocs_avant": len(avant3), "blocs_apres": len(signature()),
        "mutations_de_structure": page.evaluate("window.GARDE.mutationsDeStructure"),
    }

    resultats["gestes"] = gestes
    resultats["journal_beforeinput"] = page.evaluate("window.GARDE.journal")[:4]
    resultats["erreurs_javascript"] = erreurs
    page.close()
    navigateur.close()

print("@@@JSON@@@")
print(json.dumps(resultats, ensure_ascii=False, indent=1))
