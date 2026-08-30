"""
BANC DE MESURE, second volet — ce que le premier avait mesure DE TRAVERS.
/ Second bench: what the first one measured wrongly.

LOCALISATION : scratchpad de session, HORS DEPOT.

Le premier banc dispatchait des ClipboardEvent et des DragEvent construits
en JavaScript. Un evenement synthetique n'est PAS de confiance : le
navigateur n'execute pas son action par defaut. Le « collage sans garde »
ne collait donc rien, et mesurait zero.

Ici : vrai presse-papier (navigator.clipboard + Ctrl+V, qui est une vraie
frappe passee par CDP) et vrai glisser-deposer a la souris.
"""
import json
import time

from playwright.sync_api import sync_playwright

ADRESSE = "http://127.0.0.1:8899/prototype.html"
resultats = {}


def charge_machine():
    with open("/proc/loadavg") as fichier:
        return fichier.read().split()[0:3]


def ouvrir(contexte, ce="true", garde="1", page_id="19"):
    page = contexte.new_page()
    page.goto(f"{ADRESSE}?ce={ce}&garde={garde}&page={page_id}")
    page.wait_for_function("window.PROTO && window.PROTO.pret === true", timeout=60000)
    return page


def poser_le_curseur(page, index_bloc, offset):
    page.evaluate(
        """([index, offset]) => {
            const champ = document.getElementById('champ');
            champ.focus();
            const bloc = champ.querySelectorAll('.bloc')[index];
            const corps = bloc.querySelector('.corps');
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
    return page.evaluate("window.serialiser().map(b => b.texte)")


def etat_du_corps(page, index):
    return page.evaluate(
        """(i) => {
            const corps = document.querySelectorAll('.bloc')[i].querySelector('.corps');
            return {
                enfants: corps.children.length,
                balises: Array.from(corps.children).map(e => e.tagName.toLowerCase()),
                html: corps.innerHTML.slice(0, 180),
                texte: corps.textContent.slice(0, 80),
            };
        }""",
        index,
    )


# ==================================================================
# A. ENTREE SANS GARDE : ce=true contre ce=plaintext-only
# ==================================================================
def a_entree_sans_garde(contexte):
    sortie = {}
    for valeur in ("true", "plaintext-only"):
        page = ouvrir(contexte, ce=valeur, garde="0", page_id="19")
        avant = frontieres(page)
        avant_corps = etat_du_corps(page, 10)
        poser_le_curseur(page, 10, 25)
        page.keyboard.press("Enter")
        page.wait_for_timeout(120)
        apres_corps = etat_du_corps(page, 10)
        sortie[valeur] = {
            "frontieres_de_bloc_identiques": avant == frontieres(page),
            "enfants_du_corps_avant": avant_corps["enfants"],
            "enfants_du_corps_apres": apres_corps["enfants"],
            "balises_apres": apres_corps["balises"],
            "le_paragraphe_a_ete_scinde": apres_corps["enfants"] > avant_corps["enfants"],
            "html_apres": apres_corps["html"],
            "mutations_de_structure": page.evaluate(
                "window.PROTO.journalSentinelle.filter(m => m.structure).length"
            ),
        }
        page.close()
    return sortie


# ==================================================================
# B. plaintext-only SUFFIT-IL a empecher la fusion multi-blocs ?
# ==================================================================
def b_plaintext_only_et_la_fusion(contexte):
    sortie = {}
    for valeur in ("true", "plaintext-only"):
        page = ouvrir(contexte, ce=valeur, garde="0", page_id="19")
        avant = frontieres(page)
        selectionner_entre(page, 20, 15, 25, 20)
        page.keyboard.press("Delete")
        page.wait_for_timeout(150)
        apres = frontieres(page)
        t = textes(page)
        sortie[valeur] = {
            "frontieres_identiques": avant == apres,
            "blocs_avant": len(avant),
            "blocs_apres": len(apres),
            "blocs_detruits": len(avant) - len(apres),
            "bloc20_apres": t[20][:60] if len(t) > 20 else None,
        }
        page.close()
    return sortie


# ==================================================================
# C. LE VRAI COLLAGE — presse-papier reel, Ctrl+V reel
# ==================================================================
def c_vrai_collage(contexte):
    sortie = {}
    cas = [
        ("true", "0"),
        ("plaintext-only", "0"),
        ("true", "1"),
        ("plaintext-only", "1"),
    ]
    for valeur, garde in cas:
        page = ouvrir(contexte, ce=valeur, garde=garde, page_id="19")
        avant = frontieres(page)
        avant_corps = etat_du_corps(page, 14)
        # On remplit le vrai presse-papier avec du HTML riche multi-paragraphes.
        # / Fill the real clipboard with rich multi-paragraph HTML.
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
        poser_le_curseur(page, 14, 10)
        page.keyboard.press("Control+v")
        page.wait_for_timeout(250)
        apres_corps = etat_du_corps(page, 14)
        html = apres_corps["html"]
        sortie[f"ce={valeur}_garde={garde}"] = {
            "frontieres_de_bloc_identiques": avant == frontieres(page),
            "blocs_apres": len(frontieres(page)),
            "enfants_du_corps_avant": avant_corps["enfants"],
            "enfants_du_corps_apres": apres_corps["enfants"],
            "balises_apres": apres_corps["balises"],
            "style_survivant": any(
                b in html for b in ("<b>", "<i>", "<h1>", "<strong>", "<em>")
            ),
            "le_texte_colle_est_arrive": "TITRE" in apres_corps["texte"]
            or "TITRE" in html,
            "html_apres": html,
        }
        page.close()
    return sortie


# ==================================================================
# D. LE VRAI GLISSER-DEPOSER — a la souris
# ==================================================================
def d_vrai_glisser_deposer(contexte):
    sortie = {}
    for garde in ("0", "1"):
        page = ouvrir(contexte, ce="true", garde=garde, page_id="3")
        avant = frontieres(page)
        textes_avant = textes(page)
        # Selectionne un morceau du bloc 1, puis le glisse dans le bloc 4.
        # / Select a chunk of block 1, drag it into block 4.
        selectionner_entre(page, 1, 5, 1, 30)
        boites = page.evaluate(
            """() => {
                const s = window.getSelection();
                const r = s.getRangeAt(0).getBoundingClientRect();
                const cible = document.querySelectorAll('.bloc')[4]
                    .querySelector('.corps').getBoundingClientRect();
                return {source: {x: r.x + r.width / 2, y: r.y + r.height / 2},
                        cible: {x: cible.x + 30, y: cible.y + 8}};
            }"""
        )
        page.mouse.move(boites["source"]["x"], boites["source"]["y"])
        page.mouse.down()
        page.mouse.move(boites["cible"]["x"], boites["cible"]["y"], steps=15)
        page.mouse.up()
        page.wait_for_timeout(400)
        textes_apres = textes(page)
        sortie["garde_" + garde] = {
            "frontieres_identiques": avant == frontieres(page),
            "blocs_apres": len(frontieres(page)),
            "un_texte_a_bouge": textes_avant != textes_apres,
            "bloc1_change": textes_avant[1] != textes_apres[1],
            "bloc4_change": textes_avant[4] != textes_apres[4],
            "enfants_du_corps_4": etat_du_corps(page, 4)["enfants"],
        }
        page.close()
    return sortie


# ==================================================================
# E. CTRL+Z — isoler la cause
# ==================================================================
def e_ctrl_z(contexte):
    sortie = {}

    # E1 : frappe NATIVE seule, puis Ctrl+Z. La pile d'annulation est intacte.
    page = ouvrir(contexte, ce="true", garde="1", page_id="19")
    poser_le_curseur(page, 18, 10)
    page.keyboard.type("XYZ")
    page.wait_for_timeout(100)
    avec = textes(page)[18]
    page.keyboard.press("Control+z")
    page.wait_for_timeout(250)
    sans = textes(page)[18]
    sortie["frappe_native_seule"] = {
        "avant_annulation": avec[:50],
        "apres_annulation": sans[:50],
        "annulation_a_marche": "XYZ" not in sans and "XYZ" in avec,
    }
    page.close()

    # E2 : frappe native, PUIS un geste intercepte (ecriture DOM a la main),
    #      puis Ctrl+Z. C'est le cas reel de l'option C.
    page = ouvrir(contexte, ce="true", garde="1", page_id="19")
    poser_le_curseur(page, 18, 10)
    page.keyboard.type("XYZ")
    page.wait_for_timeout(80)
    page.keyboard.press("Enter")   # intercepte : reecrit le texte du bloc
    page.wait_for_timeout(80)
    avec2 = textes(page)[18]
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    page.wait_for_timeout(250)
    sans2 = textes(page)[18]
    sortie["frappe_puis_geste_intercepte"] = {
        "avant_annulation": avec2[:50],
        "apres_annulation": sans2[:50],
        "annulation_a_marche": avec2 != sans2,
        "le_saut_de_ligne_a_ete_annule": "\n" in avec2 and "\n" not in sans2,
        "le_xyz_a_ete_annule": "XYZ" in avec2 and "XYZ" not in sans2,
        "frontieres_identiques": len(frontieres(page)) == 210,
    }
    page.close()

    # E3 : Ctrl+Z apres une suppression multi-blocs interceptee.
    page = ouvrir(contexte, ce="true", garde="1", page_id="19")
    avant = frontieres(page)
    selectionner_entre(page, 20, 15, 25, 20)
    page.keyboard.press("Delete")
    page.wait_for_timeout(120)
    apres_suppression = textes(page)
    page.keyboard.press("Control+z")
    page.wait_for_timeout(250)
    apres_annulation = textes(page)
    sortie["apres_suppression_multi_blocs"] = {
        "frontieres_identiques": avant == frontieres(page),
        "blocs_apres": len(frontieres(page)),
        "annulation_a_change_quelque_chose": apres_suppression != apres_annulation,
        "les_blocs_21_24_sont_toujours_vides": [
            apres_annulation[i] == "" for i in (21, 22, 23, 24)
        ],
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
        contexte.grant_permissions(["clipboard-read", "clipboard-write"])
        resultats["a_entree_sans_garde"] = a_entree_sans_garde(contexte)
        resultats["b_plaintext_only_et_la_fusion"] = b_plaintext_only_et_la_fusion(contexte)
        resultats["c_vrai_collage"] = c_vrai_collage(contexte)
        resultats["d_vrai_glisser_deposer"] = d_vrai_glisser_deposer(contexte)
        resultats["e_ctrl_z"] = e_ctrl_z(contexte)
        navigateur.close()
    resultats["charge_a_la_fin"] = charge_machine()
    with open("/tmp/proto/resultats-volet2.json", "w") as fichier:
        json.dump(resultats, fichier, ensure_ascii=False, indent=1)
    print("OK — resultats-volet2.json")


if __name__ == "__main__":
    principal()
