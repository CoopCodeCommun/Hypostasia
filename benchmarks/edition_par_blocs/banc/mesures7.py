"""
BANC, septieme volet — les deux questions que la garde `beforeinput` laisse.
/ Seventh bench: the two questions the beforeinput guard leaves open.

1. `insertCompositionText` n'est PAS annulable. Que se passe-t-il si une
   composition IME remplace une selection MULTI-BLOCS ?
2. La garde 2 laisse passer la frappe ordinaire (elle ne la reecrit pas) :
   l'annulation native survit-elle ?
"""
import json
import time

from playwright.sync_api import sync_playwright

ADRESSE = "http://127.0.0.1:8899/prototype.html"
resultats = {}

SIGNATURE = """() => Array.from(document.querySelectorAll('#champ .bloc')).map((b) => {
    const c = b.querySelector('.corps');
    return [b.dataset.element, b.dataset.ordre,
            c ? Array.from(c.children).map(e => e.tagName.toLowerCase()).join('+') : 'SANS-CORPS'
           ].join('|');
})"""


def charge():
    with open("/proc/loadavg") as f:
        return f.read().split()[0:3]


def ouvrir(contexte, garde):
    page = contexte.new_page()
    page.goto(f"{ADRESSE}?ce=true&garde={garde}&page=19")
    page.wait_for_function("window.PROTO && window.PROTO.pret === true", timeout=60000)
    return page


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


def principal():
    resultats["horodatage"] = time.strftime("%Y-%m-%d %H:%M:%S")
    resultats["charge_au_debut"] = charge()
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        resultats["navigateur"] = "Chromium " + navigateur.version
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900})

        # 1. Composition IME sur une selection MULTI-BLOCS.
        for garde in ("2", "0"):
            page = ouvrir(contexte, garde)
            session = page.context.new_cdp_session(page)
            avant = page.evaluate(SIGNATURE)
            selectionner_entre(page, 20, 15, 25, 20)
            session.send("Input.imeSetComposition",
                         {"text": "に", "selectionStart": 1, "selectionEnd": 1})
            page.wait_for_timeout(80)
            session.send("Input.insertText", {"text": "日本"})
            page.wait_for_timeout(250)
            apres = page.evaluate(SIGNATURE)
            resultats["ime_sur_selection_multi_blocs_garde_" + garde] = {
                "identique": avant == apres,
                "blocs_avant": len(avant),
                "blocs_apres": len(apres),
                "geste_non_annulable_signale": page.evaluate(
                    "window.PROTO.gesteNonAnnulable || null"),
                "journal_beforeinput": page.evaluate("window.PROTO.journalBeforeInput || []")[:5],
            }
            page.close()

        # 2. L'annulation native survit-elle a la garde 2 ?
        for garde in ("2", "1"):
            page = ouvrir(contexte, garde)
            poser_le_curseur(page, 18, 10)
            page.keyboard.type("XYZ")
            page.wait_for_timeout(150)
            avec = page.evaluate("window.serialiser()[18].texte")
            page.keyboard.press("Control+z")
            page.wait_for_timeout(300)
            sans = page.evaluate("window.serialiser()[18].texte")
            # Puis une Entree (interceptee dans les deux gardes), puis Ctrl+Z.
            poser_le_curseur(page, 19, 10)
            page.keyboard.type("QQQ")
            page.wait_for_timeout(100)
            page.keyboard.press("Enter")
            page.wait_for_timeout(120)
            avec2 = page.evaluate("window.serialiser()[19].texte")
            page.keyboard.press("Control+z")
            page.wait_for_timeout(300)
            sans2 = page.evaluate("window.serialiser()[19].texte")
            resultats["annulation_garde_" + garde] = {
                "frappe_simple_annulee": "XYZ" in avec and "XYZ" not in sans,
                "apres_une_entree_annulation_a_change_quelque_chose": avec2 != sans2,
                "extrait_avant": avec2[:40],
                "extrait_apres": sans2[:40],
            }
            page.close()
        navigateur.close()
    resultats["charge_a_la_fin"] = charge()
    with open("/tmp/proto/resultats-volet7.json", "w") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=1)
    print("OK — resultats-volet7.json")


if __name__ == "__main__":
    principal()
