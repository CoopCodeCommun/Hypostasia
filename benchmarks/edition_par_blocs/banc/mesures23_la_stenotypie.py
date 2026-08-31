"""
LA STENOTYPIE AU CLAVIER (SPEC-edition-par-blocs § 4.3, § 4.4, § 6).

Ce que ce banc mesure, sur une VRAIE note transcrite (/lire/4/, neuf
tours, deux locuteurs) :

  1. les reglages du § 6.3 sont dans la barre, et ils se voient ;
  2. la VITESSE change par les touches, s'affiche, et SURVIT a un swap
     — la spec l'exige explicitement ;
  3. le RECUL A LA REPRISE recule bien a la reprise, et pas ailleurs :
     un saut volontaire ne doit pas etre deplace ;
  4. « ecouter a partir du passage du curseur » place la lecture au
     `data-debut` du bloc, sans souris ;
  5. le transport ±5 s ;
  6. le bandeau du mode ANNONCE les touches de son, et les annonce
     seulement quand il y a du son.

AUCUNE ECRITURE : on ne fait pas de Ctrl+S ici. On ecoute, on deplace,
on ralentit — rien de tout cela ne touche la base.
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_HYPOSTASIA", "https://beta.hypostasia.org")
UTILISATEUR = os.environ.get("BETA_UTILISATEUR", "jonas")
MOTDEPASSE = os.environ.get("BETA_MOTDEPASSE", "admin1234")
NOTE_TRANSCRITE = "/lire/4/"
NOTE_ECRITE = "/lire/21/"

ETAT_DU_SON = """() => {
    const audio = document.getElementById('audio-source');
    if (!audio) return null;
    return {
        readyState: audio.readyState,
        duree: isFinite(audio.duration) ? Math.round(audio.duration) : null,
        vitesse: audio.playbackRate,
        instant: Math.round(audio.currentTime * 100) / 100,
        en_pause: audio.paused,
        vitesse_affichee: (document.getElementById('vitesse-de-lecture')
                           || {}).textContent,
        recul_choisi: (document.getElementById('recul-a-la-reprise')
                       || {}).value,
    };
}"""


def poser_le_curseur_dans_le_bloc(page, rang):
    """
    Place le curseur DANS LE TEXTE du bloc de rang donne.

    ATTENTION AU PREMIER `[data-element-id]` DU BLOC : ce n'est pas le
    texte, c'est le bouton « compteur d'idees » de la GOUTTIERE, qui
    porte le meme attribut. Un curseur pose la est dans une zone
    `contenteditable="false"` — et a la premiere frappe, le navigateur
    le REPLACE au debut du champ. Le banc mesurait alors le bloc 0 et
    croyait le code fautif (mesure du 30 aout 2026 : `ecouterDepuis(0)`
    au lieu de 3,2 s). On vise donc `.corps`, comme le fait un clic.
    / The block's first [data-element-id] is the gutter's idea counter,
    inside a non-editable area: a caret there is moved to the field's
    start on the first keystroke.
    """
    page.evaluate("""(rang) => {
        const champ = document.querySelector('[data-testid=blocs-elements]');
        const bloc = champ.querySelectorAll('.bloc[data-element]')[rang];
        const interne = bloc.querySelector('.corps [data-element-id]') || bloc;
        const marcheur = document.createTreeWalker(interne, NodeFilter.SHOW_TEXT);
        const noeud = marcheur.nextNode();
        const plage = document.createRange();
        plage.setStart(noeud, 0);
        plage.collapse(true);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(plage);
    }""", rang)


sortie = {}
with sync_playwright() as p:
    navigateur = p.chromium.launch()
    contexte = navigateur.new_context(
        viewport={"width": 1400, "height": 1000}, ignore_https_errors=True)
    page = contexte.new_page()
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))

    page.goto(f"{BASE}/auth/login/", wait_until="networkidle")
    page.fill("input[name=username]", UTILISATEUR)
    page.fill("input[name=password]", MOTDEPASSE)
    page.click("button[type=submit], input[type=submit]")
    page.wait_for_load_state("networkidle")
    page.goto(f"{BASE}{NOTE_TRANSCRITE}", wait_until="networkidle")
    page.wait_for_timeout(1800)
    page.evaluate("""() => {
        const d = document.getElementById('message-d-accueil'); if (d) d.remove();
        if (window.drawerVueListe && window.drawerVueListe.fermer)
            window.drawerVueListe.fermer();
    }""")
    page.wait_for_timeout(400)

    sortie["les_reglages_sont_la"] = page.evaluate(
        """() => {
            const r = document.querySelector('[data-testid=reglages-de-lecture]');
            if (!r) return null;
            const boite = r.getBoundingClientRect();
            return {visible: boite.height > 0,
                    hauteur: Math.round(boite.height)};
        }""")
    sortie["au_depart"] = page.evaluate(ETAT_DU_SON)

    page.click('[data-testid="bouton-mode-edition"]')
    page.wait_for_timeout(600)
    sortie["bandeau_note_transcrite"] = page.evaluate(
        """() => document.querySelector('[data-testid=blocs-elements]')
                 .dataset.bandeau""")

    # --- ECOUTER A PARTIR DU PASSAGE DU CURSEUR (F2) ---
    poser_le_curseur_dans_le_bloc(page, 3)
    sortie["debut_du_bloc_vise"] = page.evaluate(
        """() => parseFloat(document.querySelectorAll(
               '[data-testid=blocs-elements] .bloc[data-element]')[3].dataset.debut)""")
    # OU LE CURSEUR EST-IL VRAIMENT, juste avant la frappe ?
    sortie["ou_est_le_curseur"] = page.evaluate("""() => {
        const s = window.getSelection();
        if (!s || !s.rangeCount) return 'aucune selection';
        let n = s.getRangeAt(0).startContainer;
        const e = n.nodeType === 3 ? n.parentElement : n;
        const bloc = e.closest('.bloc');
        return {
            type_du_noeud: n.nodeType,
            texte: (n.textContent || '').slice(0, 30),
            debut_du_bloc_trouve: bloc ? bloc.dataset.debut : null,
            le_champ_a_le_focus:
                document.activeElement === document.querySelector(
                    '[data-testid=blocs-elements]'),
        };
    }""")
    page.keyboard.press("F2")
    page.wait_for_timeout(700)
    sortie["apres_F2"] = page.evaluate(ETAT_DU_SON)

    # LE BOUTON « ECOUTER » D'UN BLOC, pour comparer : s'il saute,
    # lui, c'est que le geste F2 a un defaut propre ; s'il ne saute pas
    # non plus, le defaut est ANTERIEUR et vaut pour la souris aussi.
    sortie["etat_avant_le_bouton_ecouter"] = page.evaluate(ETAT_DU_SON)
    page.evaluate("""() => {
        const blocs = document.querySelectorAll(
            '[data-testid=blocs-elements] .bloc[data-element]');
        const b = blocs[5].querySelector('.bouton-ecouter');
        if (b) b.click();
    }""")
    page.wait_for_timeout(700)
    sortie["debut_du_bloc_5"] = page.evaluate(
        """() => parseFloat(document.querySelectorAll(
               '[data-testid=blocs-elements] .bloc[data-element]')[5].dataset.debut)""")
    sortie["apres_le_bouton_ecouter"] = page.evaluate(ETAT_DU_SON)

    # --- TRANSPORT (F7 / F8) ---
    page.keyboard.press("F8")
    page.wait_for_timeout(400)
    sortie["apres_F8_avance"] = page.evaluate(ETAT_DU_SON)
    page.keyboard.press("F7")
    page.keyboard.press("F7")
    page.wait_for_timeout(400)
    sortie["apres_deux_F7_recul"] = page.evaluate(ETAT_DU_SON)

    # --- VITESSE (F9 / F10) ---
    page.keyboard.press("F10")
    page.keyboard.press("F10")
    page.wait_for_timeout(400)
    sortie["apres_deux_F10"] = page.evaluate(ETAT_DU_SON)
    page.keyboard.press("F9")
    page.wait_for_timeout(400)
    sortie["apres_un_F9"] = page.evaluate(ETAT_DU_SON)

    # --- LE RECUL A LA REPRISE (F4 pause, puis F4 reprise) ---
    page.evaluate("""() => {
        const c = document.getElementById('recul-a-la-reprise');
        c.value = '3';
        c.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    page.wait_for_timeout(200)
    page.keyboard.press("F4")            # pause
    page.wait_for_timeout(500)
    sortie["a_la_pause"] = page.evaluate(ETAT_DU_SON)
    page.keyboard.press("F4")            # reprise : doit reculer de 3 s
    page.wait_for_timeout(600)
    sortie["a_la_reprise"] = page.evaluate(ETAT_DU_SON)
    page.keyboard.press("F4")            # on repose le son
    page.wait_for_timeout(300)

    # --- LE RECUL NE DOIT PAS DEPLACER UN POINT QU'ON VIENT DE VISER ---
    # Pause, puis saut volontaire au rail, puis reprise : la reprise doit
    # repartir EXACTEMENT du point vise (§ 6.3).
    page.keyboard.press("F4")            # pause
    page.wait_for_timeout(400)
    page.evaluate("""() => {
        const a = document.getElementById('audio-source');
        window.lecteurAudio.element().pause();
        a.currentTime = 9;
        a.dataset.sautVolontaire = 'oui';
    }""")
    page.wait_for_timeout(200)
    sortie["apres_un_saut_volontaire"] = page.evaluate(ETAT_DU_SON)
    page.keyboard.press("F4")            # reprise : PAS de recul attendu
    page.wait_for_timeout(500)
    sortie["reprise_apres_un_saut"] = page.evaluate(ETAT_DU_SON)
    page.keyboard.press("F4")
    page.wait_for_timeout(200)

    # --- LE FOCUS HORS DU CHAMP : les gestes de TEXTE se taisent ---
    # Ctrl+Z avec le focus sur le rail annulait le texte de la note,
    # invisiblement, derriere.
    page.evaluate("() => document.getElementById('rail').focus()")
    sortie["texte_avant_ctrl_z_hors_champ"] = page.evaluate(
        """() => document.querySelectorAll(
               '[data-testid=blocs-elements] .bloc[data-element]')[0]
               .querySelector('.corps [data-element-id]').textContent.trim()
               .slice(0, 40)""")
    page.keyboard.press("Control+z")
    page.wait_for_timeout(300)
    sortie["texte_apres_ctrl_z_hors_champ"] = page.evaluate(
        """() => document.querySelectorAll(
               '[data-testid=blocs-elements] .bloc[data-element]')[0]
               .querySelector('.corps [data-element-id]').textContent.trim()
               .slice(0, 40)""")
    # ... et la touche « z » nue ne doit pas remplacer la zone de lecture
    page.keyboard.press("z")
    page.wait_for_timeout(500)
    sortie["le_champ_survit_a_la_touche_z"] = page.evaluate(
        """() => {
            const c = document.querySelector('[data-testid=blocs-elements]');
            return !!c && c.getAttribute('contenteditable') === 'plaintext-only';
        }""")

    # --- CLIQUER UN PASSAGE SURLIGNE NE DOIT PAS OUVRIR LE TIROIR ---
    sortie["clic_sur_un_surlignage"] = page.evaluate("""() => {
        const marque = document.querySelector(
            '[data-testid=blocs-elements] mark.hl-extraction[data-extraction-id]');
        if (!marque) return 'aucun surlignage sur cette note';
        marque.click();
        return {
            drawer_ouvert: document.body.classList.contains('panneau-integre'),
        };
    }""")
    page.wait_for_timeout(400)

    # --- LA VITESSE SURVIT-ELLE A UN SWAP ? ---
    # Le mode ferme, la note rechargee : le reglage doit tenir.
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    page.goto(f"{BASE}{NOTE_TRANSCRITE}", wait_until="networkidle")
    page.wait_for_timeout(1500)
    sortie["apres_rechargement"] = page.evaluate(ETAT_DU_SON)

    # --- UNE NOTE SANS SON N'ANNONCE PAS LES TOUCHES DE SON ---
    page.goto(f"{BASE}{NOTE_ECRITE}", wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.evaluate("""() => {
        const d = document.getElementById('message-d-accueil'); if (d) d.remove();
    }""")
    page.click('[data-testid="bouton-mode-edition"]')
    page.wait_for_timeout(600)
    sortie["bandeau_note_ecrite"] = page.evaluate(
        """() => document.querySelector('[data-testid=blocs-elements]')
                 .dataset.bandeau""")
    sortie["reglages_sur_note_ecrite"] = page.evaluate(
        """() => !!document.querySelector('[data-testid=reglages-de-lecture]')""")

    sortie["erreurs_js"] = erreurs
    navigateur.close()

print(json.dumps(sortie, indent=2, ensure_ascii=False))
