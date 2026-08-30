"""
BANC DE MESURE, quatrieme volet — LES SURLIGNAGES D'ANCRAGE.
/ Fourth bench: the anchor highlights.

LOCALISATION : scratchpad de session, HORS DEPOT.

Les <mark class="portion"> vivent DANS le corps du bloc, donc DANS la zone
editable. 386 elements sur 1 129 portent un ancrage. Editer a l'interieur
d'une marque, ou en travers de sa frontiere, est donc un geste ordinaire —
pas un cas limite.

Ce que ce volet mesure :
  - le texte survit-il exactement a une frappe DANS une marque, et sur ses
    deux frontieres ;
  - combien de marques une interception detruit au passage.

Dans le prototype, un bloc sur trois porte une marque sur [10, 30).
"""
import json
import time

from playwright.sync_api import sync_playwright

ADRESSE = "http://127.0.0.1:8899/prototype.html"
resultats = {}


def charge_machine():
    with open("/proc/loadavg") as fichier:
        return fichier.read().split()[0:3]


def ouvrir(contexte, garde="1", page_id="19"):
    page = contexte.new_page()
    page.goto(f"{ADRESSE}?ce=true&garde={garde}&page={page_id}")
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


def etat(page, index):
    return page.evaluate(
        """(i) => {
            const corps = document.querySelectorAll('.bloc')[i].querySelector('.corps');
            const marques = corps.querySelectorAll('mark.portion');
            return {
                nb_marques: marques.length,
                texte_des_marques: Array.from(marques).map(m => m.textContent),
                texte: corps.textContent,
                html: corps.innerHTML.slice(0, 200),
            };
        }""",
        index,
    )


def compter_les_marques(page):
    return page.evaluate("document.querySelectorAll('mark.portion').length")


def frontieres(page):
    return page.evaluate("window.signatureDesFrontieres()")


def principal():
    resultats["horodatage"] = time.strftime("%Y-%m-%d %H:%M:%S")
    resultats["charge_au_debut"] = charge_machine()
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        resultats["navigateur"] = "Chromium " + navigateur.version
        contexte = navigateur.new_context(viewport={"width": 1280, "height": 900})

        page = ouvrir(contexte)
        resultats["marques_au_depart"] = compter_les_marques(page)
        resultats["blocs_au_depart"] = len(frontieres(page))

        # 1. Frappe A L'INTERIEUR d'une marque (offset 20, la marque couvre 10..30).
        avant = etat(page, 9)
        poser_le_curseur(page, 9, 20)
        page.keyboard.type("XX")
        page.wait_for_timeout(120)
        apres = etat(page, 9)
        attendu = avant["texte"][:20] + "XX" + avant["texte"][20:]
        resultats["frappe_dans_la_marque"] = {
            "marques_avant": avant["nb_marques"],
            "marques_apres": apres["nb_marques"],
            "texte_exact": apres["texte"] == attendu,
            "la_marque_contient_la_frappe": any("XX" in t for t in apres["texte_des_marques"]),
            "extrait": apres["html"][:150],
        }

        # 2. Frappe sur la frontiere GAUCHE de la marque (offset 10).
        avant2 = etat(page, 12)
        poser_le_curseur(page, 12, 10)
        page.keyboard.type("YY")
        page.wait_for_timeout(120)
        apres2 = etat(page, 12)
        attendu2 = avant2["texte"][:10] + "YY" + avant2["texte"][10:]
        resultats["frappe_frontiere_gauche"] = {
            "marques_avant": avant2["nb_marques"],
            "marques_apres": apres2["nb_marques"],
            "texte_exact": apres2["texte"] == attendu2,
            "la_frappe_est_entree_DANS_la_marque": any(
                "YY" in t for t in apres2["texte_des_marques"]
            ),
        }

        # 3. Frappe sur la frontiere DROITE (offset 30).
        avant3 = etat(page, 15)
        poser_le_curseur(page, 15, 30)
        page.keyboard.type("ZZ")
        page.wait_for_timeout(120)
        apres3 = etat(page, 15)
        attendu3 = avant3["texte"][:30] + "ZZ" + avant3["texte"][30:]
        resultats["frappe_frontiere_droite"] = {
            "marques_avant": avant3["nb_marques"],
            "marques_apres": apres3["nb_marques"],
            "texte_exact": apres3["texte"] == attendu3,
            "la_frappe_est_entree_DANS_la_marque": any(
                "ZZ" in t for t in apres3["texte_des_marques"]
            ),
        }

        # 4. Selection qui couvre entierement une marque, puis Suppr.
        avant4 = etat(page, 18)
        selectionner_entre(page, 18, 5, 18, 35)
        page.keyboard.press("Delete")
        page.wait_for_timeout(120)
        apres4 = etat(page, 18)
        resultats["suppression_couvrant_la_marque"] = {
            "marques_avant": avant4["nb_marques"],
            "marques_apres": apres4["nb_marques"],
            "texte_exact": apres4["texte"] == avant4["texte"][:5] + avant4["texte"][35:],
        }

        # 5. Combien de marques une suppression multi-blocs detruit-elle ?
        page2 = ouvrir(contexte)
        marques_avant = compter_les_marques(page2)
        marques_dans_la_plage = page2.evaluate(
            """() => {
                let n = 0;
                const blocs = document.querySelectorAll('.bloc');
                for (let i = 20; i <= 25; i += 1) {
                    n += blocs[i].querySelectorAll('mark.portion').length;
                }
                return n;
            }"""
        )
        selectionner_entre(page2, 20, 15, 25, 20)
        page2.keyboard.press("Delete")
        page2.wait_for_timeout(150)
        marques_apres = compter_les_marques(page2)
        resultats["marques_detruites_par_la_suppression_multi_blocs"] = {
            "marques_avant": marques_avant,
            "marques_apres": marques_apres,
            "detruites": marques_avant - marques_apres,
            "marques_qui_etaient_dans_la_plage": marques_dans_la_plage,
            "frontieres_identiques": len(frontieres(page2)) == 210,
        }

        # 6. Les blocs NON touches gardent-ils leurs marques ?
        resultats["marques_hors_plage_intactes"] = page2.evaluate(
            """() => {
                let n = 0;
                const blocs = document.querySelectorAll('.bloc');
                for (let i = 0; i < blocs.length; i += 1) {
                    if (i >= 20 && i <= 25) continue;
                    n += blocs[i].querySelectorAll('mark.portion').length;
                }
                return n;
            }"""
        )
        page.close()
        page2.close()
        navigateur.close()
    resultats["charge_a_la_fin"] = charge_machine()
    with open("/tmp/proto/resultats-volet4.json", "w") as fichier:
        json.dump(resultats, fichier, ensure_ascii=False, indent=1)
    print("OK — resultats-volet4.json")


if __name__ == "__main__":
    principal()
