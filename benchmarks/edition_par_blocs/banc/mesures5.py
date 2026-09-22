"""
BANC DE MESURE, cinquieme volet — LA COMPOSITION IME.
/ Fifth bench: IME composition.

LOCALISATION : scratchpad de session, HORS DEPOT.

Le § 5.2 de la spec liste six gestes qui creent ou suppriment des noeuds.
Le sixieme est la composition IME — la saisie accentuee et non latine. Elle
ne passe PAS par keydown : le navigateur ecrit dans le DOM lui-meme, entre
un compositionstart et un compositionend.

CDP sait la declencher pour de vrai (`Input.imeSetComposition`), donc elle
n'est pas condamnee au « non eprouvable en headless ».
"""
import json
import time

from playwright.sync_api import sync_playwright

ADRESSE = "http://127.0.0.1:8899/prototype.html"
resultats = {}


def charge_machine():
    with open("/proc/loadavg") as fichier:
        return fichier.read().split()[0:3]


def poser_le_curseur(page, index_bloc, offset):
    page.evaluate(
        """([index, offset]) => {
            const champ = document.getElementById('champ');
            champ.focus();
            const corps = champ.querySelectorAll('.bloc')[index].querySelector('.corps');
            const marcheur = document.createTreeWalker(corps, NodeFilter.SHOW_TEXT);
            let reste = offset, noeud = marcheur.nextNode();
            while (noeud && reste > noeud.textContent.length) {
                reste -= noeud.textContent.length;
                noeud = marcheur.nextNode();
            }
            const plage = document.createRange();
            plage.setStart(noeud, Math.min(reste, noeud.textContent.length));
            plage.collapse(true);
            const s = window.getSelection();
            s.removeAllRanges(); s.addRange(plage);
        }""",
        [index_bloc, offset],
    )


def principal():
    resultats["horodatage"] = time.strftime("%Y-%m-%d %H:%M:%S")
    resultats["charge_au_debut"] = charge_machine()
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        resultats["navigateur"] = "Chromium " + navigateur.version
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900})
        for valeur, garde in (("true", "1"), ("true", "0"), ("plaintext-only", "1")):
            page = contexte.new_page()
            page.goto(f"{ADRESSE}?ce={valeur}&garde={garde}&page=19")
            page.wait_for_function("window.PROTO && window.PROTO.pret === true", timeout=60000)
            session = page.context.new_cdp_session(page)

            avant_frontieres = page.evaluate("window.signatureDesFrontieres()")
            avant_texte = page.evaluate(
                "document.querySelectorAll('.bloc')[8].querySelector('.corps').textContent"
            )
            # On note les evenements de composition que la page recoit.
            # / Record the composition events the page receives.
            page.evaluate(
                """() => {
                    window.COMPO = [];
                    const champ = document.getElementById('champ');
                    for (const nom of ['compositionstart', 'compositionupdate', 'compositionend']) {
                        champ.addEventListener(nom, (e) => window.COMPO.push(nom + ':' + (e.data || '')));
                    }
                    window.BEFOREINPUT = [];
                    champ.addEventListener('beforeinput', (e) => {
                        window.BEFOREINPUT.push(e.inputType + ':' + (e.data || ''));
                    });
                }"""
            )
            poser_le_curseur(page, 8, 12)
            # Une vraie composition : « にほん » construite en trois temps.
            # / A real composition, built in three steps.
            session.send("Input.imeSetComposition", {
                "text": "に", "selectionStart": 1, "selectionEnd": 1})
            page.wait_for_timeout(60)
            session.send("Input.imeSetComposition", {
                "text": "にほ", "selectionStart": 2, "selectionEnd": 2})
            page.wait_for_timeout(60)
            session.send("Input.imeSetComposition", {
                "text": "にほん", "selectionStart": 3, "selectionEnd": 3})
            page.wait_for_timeout(60)
            session.send("Input.insertText", {"text": "日本"})
            page.wait_for_timeout(200)

            apres_texte = page.evaluate(
                "document.querySelectorAll('.bloc')[8].querySelector('.corps').textContent"
            )
            resultats[f"ce={valeur}_garde={garde}"] = {
                "frontieres_identiques": avant_frontieres == page.evaluate(
                    "window.signatureDesFrontieres()"),
                "blocs_apres": len(page.evaluate("window.signatureDesFrontieres()")),
                "evenements_de_composition": page.evaluate("window.COMPO"),
                "beforeinput_vus": page.evaluate("window.BEFOREINPUT"),
                "le_texte_compose_est_arrive": "日本" in apres_texte,
                "texte_exact_attendu": apres_texte == avant_texte[:12] + "日本" + avant_texte[12:],
                "extrait_apres": apres_texte[:60],
                "enfants_du_corps": page.evaluate(
                    "document.querySelectorAll('.bloc')[8].querySelector('.corps').children.length"),
                "mutations_de_structure": page.evaluate(
                    "window.PROTO.journalSentinelle.filter(m => m.structure).length"),
            }
            page.close()
        navigateur.close()
    resultats["charge_a_la_fin"] = charge_machine()
    with open("/tmp/proto/resultats-volet5.json", "w") as fichier:
        json.dump(resultats, fichier, ensure_ascii=False, indent=1)
    print("OK — resultats-volet5.json")


if __name__ == "__main__":
    principal()
