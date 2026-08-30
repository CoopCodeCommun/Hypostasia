"""
BANC DE MESURE, troisieme volet.
/ Third bench.

LOCALISATION : scratchpad de session, HORS DEPOT.

Deux questions que les deux premiers volets ont ouvertes :

F. Le glisser-deposer d'une selection MULTI-BLOCS. Deplacer, c'est
   supprimer a la source : le geste dangereux n'est pas le glisser d'un
   morceau d'un seul bloc, c'est celui qui traverse.
G. `document.execCommand` preserve-t-il la pile d'annulation native, ET
   les frontieres ? Si oui, l'option C n'a pas besoin d'ecrire sa propre
   annulation. Si non, il faut la compter dans son cout.
"""
import json
import time

from playwright.sync_api import sync_playwright

ADRESSE = "http://127.0.0.1:8899/prototype.html"
resultats = {}


def charge_machine():
    with open("/proc/loadavg") as fichier:
        return fichier.read().split()[0:3]


def ouvrir(contexte, ce="true", garde="1", page_id="19", ecriture="dom"):
    page = contexte.new_page()
    page.goto(f"{ADRESSE}?ce={ce}&garde={garde}&page={page_id}&ecriture={ecriture}")
    page.wait_for_function("window.PROTO && window.PROTO.pret === true", timeout=60000)
    return page


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


def frontieres(page):
    return page.evaluate("window.signatureDesFrontieres()")


def textes(page):
    return page.evaluate(
        "window.serialiser().map(b => b.texte === null ? '<<CORPS DETRUIT>>' : b.texte)"
    )


# ==================================================================
# F. GLISSER-DEPOSER D'UNE SELECTION MULTI-BLOCS
# ==================================================================
def f_glisser_multi_blocs(contexte):
    sortie = {}
    for garde in ("0", "1"):
        page = ouvrir(contexte, ce="true", garde=garde, page_id="3")
        avant = frontieres(page)
        textes_avant = textes(page)
        # Une selection qui va du bloc 1 au bloc 3, glissee dans le bloc 7.
        # / A selection from block 1 to block 3, dragged into block 7.
        selectionner_entre(page, 1, 10, 3, 20)
        boites = page.evaluate(
            """() => {
                const s = window.getSelection();
                const r = s.getRangeAt(0).getBoundingClientRect();
                const cible = document.querySelectorAll('.bloc')[7]
                    .querySelector('.corps').getBoundingClientRect();
                return {source: {x: r.x + 40, y: r.y + r.height / 2},
                        cible: {x: cible.x + 30, y: cible.y + 8},
                        traverse: true};
            }"""
        )
        page.mouse.move(boites["source"]["x"], boites["source"]["y"])
        page.mouse.down()
        page.mouse.move(boites["cible"]["x"], boites["cible"]["y"], steps=20)
        page.mouse.up()
        page.wait_for_timeout(500)
        apres = frontieres(page)
        textes_apres = textes(page)
        sortie["garde_" + garde] = {
            "frontieres_identiques": avant == apres,
            "blocs_avant": len(avant),
            "blocs_apres": len(apres),
            "frontieres_perdues": [f for f in avant if f not in apres],
            "blocs_dont_le_texte_a_change": [
                i for i, t in enumerate(textes_apres)
                if i < len(textes_avant) and t != textes_avant[i]
            ],
            "mutations_de_structure": page.evaluate(
                "window.PROTO.journalSentinelle.filter(m => m.structure).length"
            ),
        }
        page.close()
    return sortie


# ==================================================================
# G. execCommand : l'annulation native survit-elle, et les frontieres ?
# ==================================================================
def g_execcommand(contexte):
    sortie = {}
    for ecriture in ("dom", "exec"):
        page = ouvrir(contexte, ce="true", garde="1", page_id="19", ecriture=ecriture)
        avant = frontieres(page)

        # G1 : Entree interceptee, puis Ctrl+Z.
        poser_le_curseur(page, 10, 25)
        page.keyboard.type("ABC")
        page.wait_for_timeout(80)
        page.keyboard.press("Enter")
        page.wait_for_timeout(120)
        avec = textes(page)[10]
        page.keyboard.press("Control+z")
        page.wait_for_timeout(250)
        apres_une = textes(page)[10]
        page.keyboard.press("Control+z")
        page.wait_for_timeout(250)
        apres_deux = textes(page)[10]

        # G2 : suppression multi-blocs, puis Ctrl+Z.
        selectionner_entre(page, 20, 15, 25, 20)
        page.keyboard.press("Delete")
        page.wait_for_timeout(200)
        frontieres_apres_suppression = frontieres(page)
        textes_apres_suppression = textes(page)
        page.keyboard.press("Control+z")
        page.wait_for_timeout(300)
        textes_apres_annulation = textes(page)

        sortie[ecriture] = {
            "mode_ecriture_relu": page.evaluate("window.PROTO.mesures.mode_ecriture"),
            "entree_texte_avec": avec[:45],
            "entree_apres_un_ctrl_z": apres_une[:45],
            "entree_apres_deux_ctrl_z": apres_deux[:45],
            "le_saut_de_ligne_a_ete_annule": "\n" in avec and "\n" not in apres_une,
            "l_annulation_a_change_quelque_chose": avec != apres_une or apres_une != apres_deux,
            "suppression_frontieres_identiques": avant == frontieres_apres_suppression,
            "suppression_blocs_apres": len(frontieres_apres_suppression),
            "suppression_21_24_vides": [
                textes_apres_suppression[i] == "" for i in (21, 22, 23, 24)
            ],
            "annulation_apres_suppression_a_marche": (
                textes_apres_suppression != textes_apres_annulation
            ),
            "annulation_a_rendu_les_blocs_21_24": [
                textes_apres_annulation[i] != "" for i in (21, 22, 23, 24)
            ],
            "frontieres_finales_identiques": avant == frontieres(page),
            "mutations_de_structure": page.evaluate(
                "window.PROTO.journalSentinelle.filter(m => m.structure).length"
            ),
        }
        page.close()
    return sortie


# ==================================================================
# H. LE COUT DE execCommand SUR 210 BLOCS
# ==================================================================
def h_cout(contexte):
    sortie = {}
    for ecriture in ("dom", "exec"):
        page = ouvrir(contexte, ce="true", garde="1", page_id="19", ecriture=ecriture)
        selectionner_entre(page, 20, 15, 25, 20)
        depart = time.perf_counter()
        page.keyboard.press("Delete")
        page.wait_for_timeout(0)
        page.evaluate("() => document.getElementById('champ').getBoundingClientRect().height")
        duree = time.perf_counter() - depart
        sortie[ecriture] = {
            "suppression_6_blocs_ms": round(duree * 1000, 1),
            "frontieres_identiques": len(frontieres(page)) == 210,
        }
        page.close()
    return sortie


def principal():
    resultats["horodatage"] = time.strftime("%Y-%m-%d %H:%M:%S")
    resultats["charge_au_debut"] = charge_machine()
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        resultats["navigateur"] = "Chromium " + navigateur.version
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900})
        resultats["f_glisser_multi_blocs"] = f_glisser_multi_blocs(contexte)
        resultats["g_execcommand"] = g_execcommand(contexte)
        resultats["h_cout"] = h_cout(contexte)
        navigateur.close()
    resultats["charge_a_la_fin"] = charge_machine()
    with open("/tmp/proto/resultats-volet3.json", "w") as fichier:
        json.dump(resultats, fichier, ensure_ascii=False, indent=1)
    print("OK — resultats-volet3.json")


if __name__ == "__main__":
    principal()
