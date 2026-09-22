"""
BANC DE MESURE, sixieme volet — LES TROUS DE LA GARDE.
/ Sixth bench: the holes in the guard.

LOCALISATION : scratchpad de session, HORS DEPOT.

Une relecture adverse a montre que la garde du prototype n'intercepte que
quatre touches. Elle laisse donc passer les gestes suivants, qui font tous
une suppression de plage :

  - TAPER UNE LETTRE sur une selection multi-blocs (le remplacement — le
    geste le plus ordinaire d'un correcteur) ;
  - Ctrl+X sur une selection multi-blocs (aucun ecouteur `cut`) ;
  - Ctrl+A puis une frappe (l'ancre de selection n'est plus dans un
    `.corps`, donc la garde ne voit pas qu'elle traverse).

Et aucune plage eprouvee ne traversait de `list_item` — or 41 blocs sur
210 en sont, et une puce est `.corps > ul > li`, donc un niveau de plus.

La SENTINELLE est renforcee : on compare une signature de structure
COMPLETE, jusqu'aux balises a l'interieur du corps.
"""
import json
import time

from playwright.sync_api import sync_playwright

ADRESSE = "http://127.0.0.1:8899/prototype.html"
resultats = {}

SIGNATURE = """() => {
    return Array.from(document.querySelectorAll('#champ .bloc')).map((bloc) => {
        const corps = bloc.querySelector('.corps');
        return [
            bloc.dataset.element,
            bloc.dataset.ordre,
            bloc.querySelector('.gouttiere') ? 'g' : 'SANS-GOUTTIERE',
            bloc.querySelector('.filet-etat') ? 'f' : 'SANS-FILET',
            corps ? Array.from(corps.children).map(e => e.tagName.toLowerCase()).join('+')
                  : 'SANS-CORPS',
        ].join('|');
    });
}"""


def charge_machine():
    with open("/proc/loadavg") as fichier:
        return fichier.read().split()[0:3]


def ouvrir(contexte, garde="1", ce="true"):
    page = contexte.new_page()
    page.goto(f"{ADRESSE}?ce={ce}&garde={garde}&page=19")
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
                const marcheur = document.createTreeWalker(corps, NodeFilter.SHOW_TEXT);
                let reste = offset, noeud = marcheur.nextNode();
                while (noeud && reste > noeud.textContent.length) {
                    reste -= noeud.textContent.length;
                    noeud = marcheur.nextNode();
                }
                return [noeud, Math.min(reste, noeud.textContent.length)];
            };
            const [na, ra] = point(blocs[ia], oa);
            const [nb, rb] = point(blocs[ib], ob);
            const plage = document.createRange();
            plage.setStart(na, ra); plage.setEnd(nb, rb);
            const s = window.getSelection();
            s.removeAllRanges(); s.addRange(plage);
        }""",
        [ia, oa, ib, ob],
    )


def signature(page):
    return page.evaluate(SIGNATURE)


def compare(avant, apres):
    perdues = [s for s in avant if s not in apres]
    return {
        "identique": avant == apres,
        "blocs_avant": len(avant),
        "blocs_apres": len(apres),
        "lignes_perdues": perdues[:5],
        "nb_lignes_perdues": len(perdues),
    }


def principal():
    resultats["horodatage"] = time.strftime("%Y-%m-%d %H:%M:%S")
    resultats["charge_au_debut"] = charge_machine()
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        resultats["navigateur"] = "Chromium " + navigateur.version
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900})
        contexte.grant_permissions(["clipboard-read", "clipboard-write"])

        # --- 1. FRAPPE DE REMPLACEMENT sur une selection multi-blocs ---
        for garde in ("2", "1", "0"):
            page = ouvrir(contexte, garde=garde)
            avant = signature(page)
            selectionner_entre(page, 20, 15, 25, 20)
            page.keyboard.type("A")
            page.wait_for_timeout(200)
            resultats["frappe_de_remplacement_garde_" + garde] = compare(avant, signature(page))
            resultats["frappe_de_remplacement_garde_" + garde]["mutations_de_structure"] = (
                page.evaluate("window.PROTO.journalSentinelle.filter(m => m.structure).length"))
            resultats["frappe_de_remplacement_garde_" + garde]["journal_beforeinput"] = (
                page.evaluate("window.PROTO.journalBeforeInput || []"))
            page.close()

        # --- 2. Ctrl+X sur une selection multi-blocs ---
        for garde in ("2", "1", "0"):
            page = ouvrir(contexte, garde=garde)
            avant = signature(page)
            selectionner_entre(page, 20, 15, 25, 20)
            page.keyboard.press("Control+x")
            page.wait_for_timeout(250)
            resultats["couper_garde_" + garde] = compare(avant, signature(page))
            page.close()

        # --- 3. Ctrl+A puis une frappe ---
        for garde in ("2", "1", "0"):
            page = ouvrir(contexte, garde=garde)
            avant = signature(page)
            page.evaluate("document.getElementById('champ').focus()")
            page.keyboard.press("Control+a")
            page.keyboard.type("A")
            page.wait_for_timeout(250)
            apres = signature(page)
            resultats["tout_selectionner_puis_frappe_garde_" + garde] = compare(avant, apres)
            resultats["tout_selectionner_puis_frappe_garde_" + garde]["gouttieres_restantes"] = (
                page.evaluate("document.querySelectorAll('#champ .gouttiere').length"))
            page.close()

        # --- 4. Une plage qui traverse des PUCES (list_item) ---
        page = ouvrir(contexte, garde="1")
        indices_puces = page.evaluate(
            """() => {
                const blocs = Array.from(document.querySelectorAll('.bloc'));
                const idx = [];
                for (let i = 0; i < blocs.length - 3; i += 1) {
                    if ([0,1,2,3].every(k => blocs[i+k].dataset.label === 'list_item')) {
                        idx.push(i);
                    }
                }
                return idx.slice(0, 3);
            }"""
        )
        resultats["premieres_series_de_puces"] = indices_puces
        page.close()
        if indices_puces:
            depart = indices_puces[0]
            for garde in ("2", "1", "0"):
                page = ouvrir(contexte, garde=garde)
                avant = signature(page)
                selectionner_entre(page, depart, 5, depart + 3, 5)
                page.keyboard.press("Delete")
                page.wait_for_timeout(200)
                cle = "suppression_a_travers_des_puces_garde_" + garde
                resultats[cle] = compare(avant, signature(page))
                resultats[cle]["indice_de_depart"] = depart
                resultats[cle]["mutations_de_structure"] = page.evaluate(
                    "window.PROTO.journalSentinelle.filter(m => m.structure).length")
                page.close()

            # --- 5. Entree NUE dans une puce : la sentinelle la voit-elle ? ---
            page = ouvrir(contexte, garde="0")
            avant = signature(page)
            page.evaluate(
                """(i) => {
                    const corps = document.querySelectorAll('.bloc')[i].querySelector('.corps');
                    const marcheur = document.createTreeWalker(corps, NodeFilter.SHOW_TEXT);
                    const noeud = marcheur.nextNode();
                    const plage = document.createRange();
                    plage.setStart(noeud, Math.min(10, noeud.textContent.length));
                    plage.collapse(true);
                    const s = window.getSelection();
                    s.removeAllRanges(); s.addRange(plage);
                    document.getElementById('champ').focus();
                }""",
                depart,
            )
            page.keyboard.press("Enter")
            page.wait_for_timeout(200)
            apres = signature(page)
            resultats["entree_nue_dans_une_puce"] = compare(avant, apres)
            resultats["entree_nue_dans_une_puce"]["signature_du_bloc_apres"] = apres[depart]
            resultats["entree_nue_dans_une_puce"]["mutations_vues_par_la_sentinelle"] = (
                page.evaluate("window.PROTO.journalSentinelle.filter(m => m.structure).length"))
            resultats["entree_nue_dans_une_puce"]["mutations_TOTALES"] = page.evaluate(
                "window.PROTO.journalSentinelle.length")
            page.close()

        navigateur.close()
    resultats["charge_a_la_fin"] = charge_machine()
    with open("/tmp/proto/resultats-volet6bis.json", "w") as fichier:
        json.dump(resultats, fichier, ensure_ascii=False, indent=1)
    print("OK — resultats-volet6bis.json")


if __name__ == "__main__":
    principal()
