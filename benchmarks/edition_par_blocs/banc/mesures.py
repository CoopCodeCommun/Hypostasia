"""
BANC DE MESURE — prototype de l'option C (le champ unique).
/ Measurement bench for option C (the single field).

LOCALISATION : scratchpad de session, HORS DEPOT.
Ne touche a rien du depot. N'appelle aucun modele. Ne fait aucune ecriture
en base : les donnees ont ete extraites une fois, en lecture seule.

Il rend un JSON de resultats. Chaque chiffre porte sa machine et sa date,
ecrites par l'appelant.
"""
import json
import os
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

ADRESSE = "http://127.0.0.1:8899/prototype.html"
resultats = {}


def charge_machine():
    with open("/proc/loadavg") as fichier:
        return fichier.read().split()[0:3]


def ouvrir(navigateur, ce="true", garde="1", page_id="19", boutons="0"):
    page = navigateur.new_page(viewport={"width": 1280, "height": 900})
    page.goto(f"{ADRESSE}?ce={ce}&garde={garde}&page={page_id}&boutons={boutons}")
    page.wait_for_function("window.PROTO && window.PROTO.pret === true", timeout=60000)
    return page


def poser_le_curseur(page, index_bloc, offset):
    """Place le curseur dans le corps du bloc d'index donne, a l'offset donne."""
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
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(plage);
        }""",
        [index_bloc, offset],
    )


def selectionner_entre(page, index_debut, offset_debut, index_fin, offset_fin):
    """Selection programmatique du bloc A offset a au bloc B offset b."""
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
            plage.setStart(na, ra);
            plage.setEnd(nb, rb);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(plage);
        }""",
        [index_debut, offset_debut, index_fin, offset_fin],
    )


def textes(page):
    return page.evaluate("window.serialiser().map(b => b.texte)")


def frontieres(page):
    return page.evaluate("window.signatureDesFrontieres()")


# ==================================================================
# MESURE 6 — contenteditable="plaintext-only" : verifie, pas suppose
# ==================================================================
def mesure_6_plaintext_only(navigateur, nom_du_moteur):
    sortie = {"moteur": nom_du_moteur}
    for valeur in ("true", "plaintext-only"):
        page = ouvrir(navigateur, ce=valeur, garde="0", page_id="3")
        mesures = page.evaluate("window.PROTO.mesures")
        sortie[valeur] = {
            "attribut_relu": mesures["contenteditable_attribut"],
            "propriete_relue": mesures["contenteditable_propriete"],
            "accepte": mesures["contenteditable_propriete"] == valeur,
        }
        # Comportement NU : Entree, sans aucune interception.
        # / Native behaviour: Enter, with no interception at all.
        avant = frontieres(page)
        poser_le_curseur(page, 2, 20)
        page.keyboard.press("Enter")
        apres = frontieres(page)
        sortie[valeur]["entree_nue_casse_les_frontieres"] = (avant != apres)
        sortie[valeur]["entree_nue_blocs_avant_apres"] = [len(avant), len(apres)]
        sortie[valeur]["entree_nue_mutations_de_structure"] = page.evaluate(
            "window.PROTO.journalSentinelle.filter(m => m.structure).length"
        )
        # Collage de HTML riche, sans interception.
        # / Rich HTML paste, with no interception.
        page.evaluate("window.PROTO.journalSentinelle = []")
        avant2 = frontieres(page)
        poser_le_curseur(page, 4, 10)
        page.evaluate(
            """() => {
                const dt = new DataTransfer();
                dt.setData('text/html', '<p><b>gras</b></p><p>deuxieme paragraphe</p>');
                dt.setData('text/plain', 'gras\\n\\ndeuxieme paragraphe');
                document.getElementById('champ').dispatchEvent(
                    new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})
                );
            }"""
        )
        page.wait_for_timeout(120)
        apres2 = frontieres(page)
        html_bloc = page.evaluate(
            "document.querySelectorAll('.bloc')[4].querySelector('.corps').innerHTML"
        )
        sortie[valeur]["collage_nu_casse_les_frontieres"] = (avant2 != apres2)
        sortie[valeur]["collage_nu_a_laisse_du_gras"] = ("<b>" in html_bloc or "<strong>" in html_bloc)
        sortie[valeur]["collage_nu_extrait_html"] = html_bloc[:200]
        page.close()
    return sortie


# ==================================================================
# MESURE 1 — le champ tient-il a 59 000 caracteres / 210 blocs
# ==================================================================
def mesure_1_tenue(navigateur):
    sortie = {}
    for page_id, etiquette in (("19", "210_blocs"), ("3", "12_blocs")):
        page = ouvrir(navigateur, ce="true", garde="1", page_id=page_id)
        mesures = page.evaluate("window.PROTO.mesures")

        # Instrumentation de la frappe : keydown -> input -> frame suivante.
        # / Typing instrumentation: keydown -> input -> next frame.
        page.evaluate(
            """() => {
                window.LAT = [];
                let t0 = null;
                const champ = document.getElementById('champ');
                champ.addEventListener('keydown', () => { t0 = performance.now(); }, true);
                champ.addEventListener('input', () => {
                    const t1 = performance.now();
                    requestAnimationFrame(() => {
                        window.LAT.push({saisie: t1 - t0, frame: performance.now() - t1});
                    });
                }, true);
            }"""
        )
        milieu = 105 if page_id == "19" else 6
        poser_le_curseur(page, milieu, 20)
        depart = time.perf_counter()
        page.keyboard.type("le renard brun saute par-dessus le chien", delay=12)
        duree_frappe = time.perf_counter() - depart
        page.wait_for_timeout(300)
        latences = page.evaluate("window.LAT")
        saisies = sorted(x["saisie"] for x in latences)
        frames = sorted(x["frame"] for x in latences)

        def percentile(valeurs, part):
            if not valeurs:
                return None
            return round(valeurs[min(len(valeurs) - 1, int(len(valeurs) * part))], 2)

        # Cout de l'Entree interceptee : elle REECRIT le texte du bloc entier.
        # / Cost of the intercepted Enter: it rewrites the whole block's text.
        poser_le_curseur(page, milieu, 20)
        cout_entree = page.evaluate(
            """() => {
                const t = performance.now();
                document.getElementById('champ').dispatchEvent(
                    new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));
                return performance.now() - t;
            }"""
        )
        cout_serialisation = page.evaluate(
            "() => { const t = performance.now(); window.serialiser(); return performance.now() - t; }"
        )
        sortie[etiquette] = {
            "blocs": mesures["nombre_de_blocs"],
            "caracteres": mesures["caracteres"],
            "rendu_ms": round(mesures["rendu_ms"], 2),
            "layout_ms": round(mesures["layout_ms"], 2),
            "hauteur_px": round(mesures["hauteur_px"]),
            "frappe_n": len(latences),
            "frappe_saisie_median_ms": percentile(saisies, 0.5),
            "frappe_saisie_p95_ms": percentile(saisies, 0.95),
            "frappe_saisie_max_ms": round(saisies[-1], 2) if saisies else None,
            "frappe_frame_median_ms": percentile(frames, 0.5),
            "frappe_frame_p95_ms": percentile(frames, 0.95),
            "duree_totale_frappe_s": round(duree_frappe, 2),
            "cout_entree_interceptee_ms": round(cout_entree, 2),
            "cout_serialisation_ms": round(cout_serialisation, 2),
        }
        page.close()
    return sortie


# ==================================================================
# MESURE 4 — la suppression multi-blocs ne fusionne pas
# ==================================================================
def mesure_4_suppression_multi_blocs(navigateur):
    sortie = {}
    for garde in ("0", "1"):
        page = ouvrir(navigateur, ce="true", garde=garde, page_id="19")
        avant = frontieres(page)
        textes_avant = textes(page)
        selectionner_entre(page, 20, 15, 25, 20)
        page.keyboard.press("Delete")
        page.wait_for_timeout(150)
        apres = frontieres(page)
        textes_apres = textes(page)
        sortie["garde_" + garde] = {
            "frontieres_identiques": avant == apres,
            "blocs_avant": len(avant),
            "blocs_apres": len(apres),
            "frontieres_perdues": [f for f in avant if f not in apres][:6],
            "bloc20_avant": textes_avant[20][:45],
            "bloc20_apres": textes_apres[20][:45] if len(textes_apres) > 20 else None,
            "bloc25_apres": textes_apres[25][:45] if len(textes_apres) > 25 else None,
            "blocs_21_24_vides": (
                [textes_apres[i] == "" for i in (21, 22, 23, 24)]
                if len(textes_apres) > 25 else None
            ),
            "mutations_de_structure": page.evaluate(
                "window.PROTO.journalSentinelle.filter(m => m.structure).length"
            ),
        }
        # Meme geste au CLAVIER SEUL (Maj+Bas), pas par selection programmatique.
        # / Same gesture with the keyboard alone.
        page2 = ouvrir(navigateur, ce="true", garde=garde, page_id="19")
        avant2 = frontieres(page2)
        poser_le_curseur(page2, 30, 5)
        for _ in range(12):
            page2.keyboard.press("Shift+ArrowDown")
        traverse = page2.evaluate(
            """() => {
                const s = window.getSelection();
                const bloc = (n) => (n.nodeType === 3 ? n.parentElement : n).closest('.bloc');
                return bloc(s.anchorNode) !== bloc(s.focusNode);
            }"""
        )
        page2.keyboard.press("Backspace")
        page2.wait_for_timeout(150)
        sortie["garde_" + garde]["clavier_seul_selection_traverse"] = traverse
        sortie["garde_" + garde]["clavier_seul_frontieres_identiques"] = (
            avant2 == frontieres(page2)
        )
        page.close()
        page2.close()
    return sortie


# ==================================================================
# MESURE 3 — les interceptions tiennent-elles au collage, glisser,
#            correcteur, Ctrl+Z
# ==================================================================
def mesure_3_les_gestes_qui_creent_des_noeuds(navigateur):
    sortie = {}

    def neuf(garde="1"):
        return ouvrir(navigateur, ce="true", garde=garde, page_id="19")

    # a) Entree au milieu d'un bloc
    page = neuf()
    avant = frontieres(page)
    poser_le_curseur(page, 10, 25)
    page.keyboard.press("Enter")
    page.wait_for_timeout(80)
    t = textes(page)
    sortie["entree"] = {
        "frontieres_identiques": avant == frontieres(page),
        "saut_de_ligne_dans_le_bloc": "\n" in t[10],
        "html_du_bloc": page.evaluate(
            "document.querySelectorAll('.bloc')[10].querySelector('.corps').innerHTML"
        )[:120],
    }
    page.close()

    # b) Retour arriere en tete de bloc
    page = neuf()
    avant = frontieres(page)
    textes_avant = textes(page)
    poser_le_curseur(page, 12, 0)
    page.keyboard.press("Backspace")
    page.wait_for_timeout(80)
    textes_apres = textes(page)
    sortie["retour_arriere_en_tete"] = {
        "frontieres_identiques": avant == frontieres(page),
        "aucun_texte_modifie": textes_avant == textes_apres,
    }
    page.close()

    # c) Collage de HTML riche multi-paragraphes
    for garde in ("0", "1"):
        page = neuf(garde)
        avant = frontieres(page)
        poser_le_curseur(page, 14, 10)
        page.evaluate(
            """() => {
                const dt = new DataTransfer();
                dt.setData('text/html',
                  '<h1>TITRE</h1><p><b>gras</b> et <i>italique</i></p><p>second</p>');
                dt.setData('text/plain', 'TITRE\\n\\ngras et italique\\n\\nsecond');
                document.getElementById('champ').dispatchEvent(
                    new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
            }"""
        )
        page.wait_for_timeout(150)
        html = page.evaluate(
            "document.querySelectorAll('.bloc')[14].querySelector('.corps').innerHTML"
        )
        sortie["collage_garde_" + garde] = {
            "frontieres_identiques": avant == frontieres(page),
            "blocs_apres": len(frontieres(page)),
            "style_survivant": any(b in html for b in ("<b>", "<i>", "<h1>", "<strong>", "<em>")),
            "extrait": html[:160],
        }
        page.close()

    # d) Glisser-deposer d'une selection
    for garde in ("0", "1"):
        page = neuf(garde)
        avant = frontieres(page)
        poser_le_curseur(page, 16, 5)
        page.evaluate(
            """() => {
                const dt = new DataTransfer();
                dt.setData('text/html', '<p>un</p><p>deux</p>');
                dt.setData('text/plain', 'un\\n\\ndeux');
                const cible = document.querySelectorAll('.bloc')[16].querySelector('.corps');
                cible.dispatchEvent(new DragEvent('drop',
                    {dataTransfer: dt, bubbles: true, cancelable: true}));
            }"""
        )
        page.wait_for_timeout(150)
        sortie["glisser_deposer_garde_" + garde] = {
            "frontieres_identiques": avant == frontieres(page),
            "blocs_apres": len(frontieres(page)),
        }
        page.close()

    # e) Le correcteur du navigateur : il ne passe PAS par keydown.
    #    On dispatche l'evenement qu'il produit reellement.
    #    / The spellchecker does not go through keydown.
    page = neuf("1")
    sortie["correcteur_orthographique"] = {
        "spellcheck_actif_sur_le_champ": page.evaluate(
            "document.getElementById('champ').spellcheck"
        ),
        "beforeinput_insertReplacementText_intercepte": page.evaluate(
            """() => {
                let vu = false;
                const champ = document.getElementById('champ');
                champ.addEventListener('beforeinput', (e) => {
                    if (e.defaultPrevented) vu = true;
                }, false);
                const e = new InputEvent('beforeinput', {
                    inputType: 'insertReplacementText', bubbles: true, cancelable: true,
                    data: 'corrige'});
                champ.dispatchEvent(e);
                return vu;
            }"""
        ),
        "keydown_recu_pour_ce_geste": False,
        "note": "headless : le vrai correcteur ne peut pas etre declenche",
    }
    page.close()

    # f) Ctrl+Z, l'annulation native
    page = neuf("1")
    avant = frontieres(page)
    poser_le_curseur(page, 18, 10)
    page.keyboard.type("XYZ")          # frappe NATIVE, elle entre dans la pile d'annulation
    page.keyboard.press("Enter")       # geste INTERCEPTE, ecrit a la main : hors pile
    page.wait_for_timeout(100)
    textes_avant_annulation = textes(page)
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    page.wait_for_timeout(200)
    textes_apres_annulation = textes(page)
    sortie["ctrl_z"] = {
        "frontieres_identiques": avant == frontieres(page),
        "blocs_apres": len(frontieres(page)),
        "texte_bloc18_avant_annulation": textes_avant_annulation[18][:60],
        "texte_bloc18_apres_annulation": textes_apres_annulation[18][:60],
        "annulation_a_efface_le_saut_de_ligne": (
            "\n" in textes_avant_annulation[18] and "\n" not in textes_apres_annulation[18]
        ),
        "annulation_a_rendu_le_xyz": "XYZ" in textes_apres_annulation[18],
        "mutations_de_structure": page.evaluate(
            "window.PROTO.journalSentinelle.filter(m => m.structure).length"
        ),
    }
    page.close()
    return sortie


# ==================================================================
# MESURE 5 — le parcours 100 % clavier, et ce qu'un lecteur d'ecran voit
# ==================================================================
def mesure_5_clavier_et_lecteur(navigateur):
    page = ouvrir(navigateur, ce="true", garde="1", page_id="3")
    sortie = {}

    # Atteindre le champ au clavier seul, depuis le debut du document.
    page.evaluate("document.body.focus(); document.activeElement.blur();")
    page.keyboard.press("Tab")
    sortie["tab_atteint_le_champ"] = page.evaluate(
        "document.activeElement === document.getElementById('champ')"
    )

    poser_le_curseur(page, 0, 5)
    bloc_avant = page.evaluate(
        """() => {
            const s = window.getSelection();
            const n = s.anchorNode.nodeType === 3 ? s.anchorNode.parentElement : s.anchorNode;
            return n.closest('.bloc').dataset.ordre;
        }"""
    )
    for _ in range(6):
        page.keyboard.press("ArrowDown")
    bloc_apres = page.evaluate(
        """() => {
            const s = window.getSelection();
            const n = s.anchorNode.nodeType === 3 ? s.anchorNode.parentElement : s.anchorNode;
            const b = n.closest('.bloc');
            return b ? b.dataset.ordre : 'HORS BLOC';
        }"""
    )
    sortie["fleche_bas_traverse_les_blocs"] = bloc_avant != bloc_apres
    sortie["bloc_avant_apres_fleche"] = [bloc_avant, bloc_apres]

    poser_le_curseur(page, 0, 5)
    page.keyboard.press("Control+End")
    sortie["ctrl_fin_va_au_dernier_bloc"] = page.evaluate(
        """() => {
            const s = window.getSelection();
            const n = s.anchorNode.nodeType === 3 ? s.anchorNode.parentElement : s.anchorNode;
            const b = n.closest('.bloc');
            const tous = document.querySelectorAll('.bloc');
            return b === tous[tous.length - 1];
        }"""
    )

    poser_le_curseur(page, 1, 5)
    for _ in range(8):
        page.keyboard.press("Shift+ArrowDown")
    sortie["maj_bas_etend_a_travers_les_blocs"] = page.evaluate(
        """() => {
            const s = window.getSelection();
            const bloc = (n) => (n.nodeType === 3 ? n.parentElement : n).closest('.bloc');
            return bloc(s.anchorNode) !== bloc(s.focusNode);
        }"""
    )
    # La selection etendue au clavier avale-t-elle la GOUTTIERE ?
    # / Does the keyboard-extended selection swallow the gutter?
    sortie["la_selection_contient_le_texte_de_la_gouttiere"] = page.evaluate(
        """() => {
            const s = window.getSelection();
            const texte = s.toString();
            const gouttiere = document.querySelectorAll('.gouttiere')[2].textContent.trim();
            return gouttiere.length > 0 && texte.includes(gouttiere);
        }"""
    )
    sortie["extrait_de_la_selection"] = page.evaluate(
        "window.getSelection().toString().slice(0, 120)"
    )

    page.keyboard.press("Control+s")
    page.wait_for_timeout(120)
    sortie["ctrl_s_intercepte"] = page.evaluate("!!window.PROTO.dernierPost")
    sortie["compte_rendu_annonce"] = page.evaluate(
        "document.getElementById('zone-annonces').textContent"
    )

    # Ce qu'un lecteur d'ecran EXPOSE — arbre d'accessibilite Chromium.
    # Ce n'est PAS un lecteur d'ecran reel.
    # / What the AX tree exposes. This is NOT a real screen reader.
    session = page.context.new_cdp_session(page)
    session.send("Accessibility.enable")
    brut = session.send("Accessibility.getFullAXTree")
    plat = []
    for noeud in brut.get("nodes", []):
        if noeud.get("ignored"):
            continue
        role = (noeud.get("role") or {}).get("value")
        nom = ((noeud.get("name") or {}).get("value") or "")
        plat.append({"role": role, "name": nom[:70]})
    sortie["ax_nombre_de_noeuds"] = len(plat)
    sortie["ax_premiers_noeuds"] = plat[:14]
    sortie["ax_expose_un_numero_de_bloc"] = any("#" in n["name"] for n in plat)
    sortie["ax_expose_un_locuteur"] = any(
        n["name"].strip() in ("Elinor", "Eric", "Laurent", "speaker_1", "speaker_2")
        for n in plat
    )
    page.close()
    return sortie


# ==================================================================
# MESURE 2 — vingt gestes enchaines, puis le diff par identifiant_stable
# ==================================================================
def mesure_2_vingt_gestes(navigateur):
    page = ouvrir(navigateur, ce="true", garde="1", page_id="19")
    initiaux = page.evaluate("window.PROTO.blocsInitiaux")
    frontieres_avant = frontieres(page)
    journal = []

    photo = {"precedente": [b["texte"] for b in initiaux]}

    def geste(numero, description, action):
        page.evaluate(f"window.PROTO.gesteEnCours = {json.dumps(description)}")
        action()
        page.wait_for_timeout(60)
        # Attribution : quels blocs ce geste a-t-il REELLEMENT changes ?
        # / Attribution: which blocks did this gesture actually change?
        courante = textes(page)
        touches = [
            i for i, t in enumerate(courante)
            if i >= len(photo["precedente"]) or t != photo["precedente"][i]
        ]
        photo["precedente"] = courante
        journal.append({"n": numero, "geste": description, "blocs_touches": touches})

    # 1-3 : trois corrections de nature differente
    geste(1, "frappe simple dans le bloc 5", lambda: (
        poser_le_curseur(page, 5, 10), page.keyboard.type("ABC")))
    geste(2, "correction de CASSE au debut du bloc 7", lambda: (
        selectionner_entre(page, 7, 0, 7, 1), page.keyboard.type("Z")))
    geste(3, "double ESPACE insere dans le bloc 9", lambda: (
        poser_le_curseur(page, 9, 8), page.keyboard.type("  ")))
    # 4-6 : les trois gestes de structure interdits
    geste(4, "Entree au milieu du bloc 11", lambda: (
        poser_le_curseur(page, 11, 15), page.keyboard.press("Enter")))
    geste(5, "Retour arriere en TETE du bloc 13", lambda: (
        poser_le_curseur(page, 13, 0), page.keyboard.press("Backspace")))
    geste(6, "Suppr en FIN du bloc 15", lambda: (
        page.evaluate("""() => {
            const b = document.querySelectorAll('.bloc')[15];
            const corps = b.querySelector('.corps');
            const plage = document.createRange();
            plage.selectNodeContents(corps);
            plage.collapse(false);
            const s = window.getSelection();
            s.removeAllRanges(); s.addRange(plage);
            document.getElementById('champ').focus();
        }"""), page.keyboard.press("Delete")))
    # 7 : la suppression multi-blocs
    geste(7, "selection du bloc 20 au bloc 25, Suppr", lambda: (
        selectionner_entre(page, 20, 15, 25, 20), page.keyboard.press("Delete")))
    # 8-9 : les collages
    geste(8, "collage de HTML riche dans le bloc 30", lambda: page.evaluate(
        """() => {
            const dt = new DataTransfer();
            dt.setData('text/html', '<h1>T</h1><p><b>gras</b></p>');
            dt.setData('text/plain', 'T\\n\\ngras');
            document.getElementById('champ').dispatchEvent(
                new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
        }"""))
    geste(9, "collage multi-paragraphes dans le bloc 32", lambda: (
        poser_le_curseur(page, 32, 5),
        page.evaluate("""() => {
            const dt = new DataTransfer();
            dt.setData('text/plain', 'alpha\\n\\nbeta\\n\\ngamma');
            document.getElementById('champ').dispatchEvent(
                new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
        }""")))
    # 10 : glisser-deposer
    geste(10, "glisser-deposer dans le bloc 35", lambda: (
        poser_le_curseur(page, 35, 3),
        page.evaluate("""() => {
            const dt = new DataTransfer();
            dt.setData('text/plain', 'depose\\n\\ndeux');
            const cible = document.querySelectorAll('.bloc')[35].querySelector('.corps');
            cible.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
        }""")))
    # 11 : Ctrl+Z
    geste(11, "frappe puis Ctrl+Z dans le bloc 38", lambda: (
        poser_le_curseur(page, 38, 6), page.keyboard.type("QQQ"),
        page.keyboard.press("Control+z")))
    # 12 : vider un bloc entier
    geste(12, "vider entierement le bloc 40", lambda: page.evaluate(
        """() => {
            const corps = document.querySelectorAll('.bloc')[40].querySelector('.corps');
            const plage = document.createRange();
            plage.selectNodeContents(corps);
            const s = window.getSelection(); s.removeAllRanges(); s.addRange(plage);
            document.getElementById('champ').focus();
        }"""))
    geste(13, "Suppr sur le bloc 40 selectionne", lambda: page.keyboard.press("Delete"))
    # 14 : vider puis re-remplir (doit finir NON masque)
    geste(14, "vider puis re-remplir le bloc 45", lambda: (
        page.evaluate("""() => {
            const corps = document.querySelectorAll('.bloc')[45].querySelector('.corps');
            const plage = document.createRange();
            plage.selectNodeContents(corps);
            const s = window.getSelection(); s.removeAllRanges(); s.addRange(plage);
            document.getElementById('champ').focus();
        }"""),
        page.keyboard.press("Delete"),
        page.keyboard.type("texte remis")))
    # 15 : editer un TABLEAU
    geste(15, "frappe dans un bloc table", lambda: (
        page.evaluate("""() => {
            const blocs = Array.from(document.querySelectorAll('.bloc'));
            const t = blocs.find(b => b.dataset.label === 'table');
            window.__indexTable = blocs.indexOf(t);
        }"""),
        poser_le_curseur(page, page.evaluate("window.__indexTable"), 5),
        page.keyboard.type("TT")))
    # 16-18 : au clavier seul
    geste(16, "Maj+Bas x10 puis Retour arriere depuis le bloc 50", lambda: (
        poser_le_curseur(page, 50, 4),
        [page.keyboard.press("Shift+ArrowDown") for _ in range(10)],
        page.keyboard.press("Backspace")))
    geste(17, "Entree dans un titre (section_header)", lambda: (
        page.evaluate("""() => {
            const blocs = Array.from(document.querySelectorAll('.bloc'));
            const t = blocs.find((b, i) => i > 60 && b.dataset.label === 'section_header');
            window.__indexTitre = blocs.indexOf(t);
        }"""),
        poser_le_curseur(page, page.evaluate("window.__indexTitre"), 3),
        page.keyboard.press("Enter")))
    geste(18, "frappe dans le dernier bloc", lambda: (
        poser_le_curseur(page, 209, 3), page.keyboard.type("FIN")))
    # 19 : un bloc a saut de ligne interne
    geste(19, "frappe dans un bloc a saut de ligne interne", lambda: (
        page.evaluate("""() => {
            const blocs = Array.from(document.querySelectorAll('.bloc'));
            const t = blocs.find(b => b.querySelector('.corps').textContent.includes('\\n'));
            window.__indexSaut = t ? blocs.indexOf(t) : 0;
        }"""),
        poser_le_curseur(page, page.evaluate("window.__indexSaut"), 2),
        page.keyboard.type("SS")))
    # 20 : Ctrl+S
    geste(20, "Ctrl+S", lambda: page.keyboard.press("Control+s"))

    charge = page.evaluate("window.PROTO.dernierPost")
    frontieres_apres = frontieres(page)
    mutations = page.evaluate("window.PROTO.journalSentinelle")
    page.close()
    return {
        "journal_des_gestes": journal,
        "frontieres_identiques": frontieres_avant == frontieres_apres,
        "blocs_avant": len(frontieres_avant),
        "blocs_apres": len(frontieres_apres),
        "mutations_de_structure": [m for m in mutations if m["structure"]][:10],
        "nombre_de_mutations_de_structure": sum(1 for m in mutations if m["structure"]),
        "post": charge,
        "initiaux": initiaux,
    }


# ==================================================================
def principal():
    resultats["machine"] = {
        "hote": os.uname().nodename,
        "charge_1_5_15": charge_machine(),
        "horodatage": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    demandees = sys.argv[1:] or ["6", "1", "4", "3", "5", "2"]
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        resultats["navigateur"] = "Chromium " + navigateur.version
        if "6" in demandees:
            resultats["mesure_6_plaintext_only"] = mesure_6_plaintext_only(navigateur, "chromium")
        if "1" in demandees:
            resultats["mesure_1_tenue"] = mesure_1_tenue(navigateur)
        if "4" in demandees:
            resultats["mesure_4_suppression_multi_blocs"] = mesure_4_suppression_multi_blocs(navigateur)
        if "3" in demandees:
            resultats["mesure_3_gestes_creant_des_noeuds"] = mesure_3_les_gestes_qui_creent_des_noeuds(navigateur)
        if "5" in demandees:
            resultats["mesure_5_clavier"] = mesure_5_clavier_et_lecteur(navigateur)
        if "2" in demandees:
            resultats["mesure_2_vingt_gestes"] = mesure_2_vingt_gestes(navigateur)
        navigateur.close()
    resultats["charge_a_la_fin"] = charge_machine()
    nom = "/tmp/proto/resultats-" + "-".join(demandees) + ".json"
    with open(nom, "w") as fichier:
        json.dump(resultats, fichier, ensure_ascii=False, indent=1)
    print("OK — " + nom)


if __name__ == "__main__":
    principal()
