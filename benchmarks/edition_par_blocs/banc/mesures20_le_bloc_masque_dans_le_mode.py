"""
UN BLOC MASQUE, VU DEPUIS LE MODE D'EDITION (SPEC § 5.3, cas 4).

La question, et elle n'a jamais ete mesuree : le mode cree des blocs
masques (un bloc vide est masque, § 7.3) — peut-on les RETABLIR sans
sortir du mode ?

Le gabarit `_un_bloc_element.html` rend deja un placeholder avec un
bouton « demasquer ». Reste a savoir ce que le mode en fait : le CSS du
mode cache `.actions-element`, mais ce bouton-la n'en fait pas partie.

AUCUNE ECRITURE. On ne clique pas sur « demasquer » : on mesure sa
presence, sa visibilite, sa taille, son atteignabilite au clavier, et si
le placeholder est dans le champ modifiable ou hors de lui.

Terrain : /lire/29/ — la seule note de la base qui porte des blocs
masques (2 sur 99, mesure du 30 aout 2026).
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_HYPOSTASIA", "https://beta.hypostasia.org")
UTILISATEUR = os.environ.get("BETA_UTILISATEUR", "jonas")
MOTDEPASSE = os.environ.get("BETA_MOTDEPASSE", "admin1234")
NOTE = "/lire/29/"

ETAT_DES_PLACEHOLDERS = """() => {
    const champ = document.querySelector('[data-testid=blocs-elements]');
    const masques = Array.from(document.querySelectorAll('.element-masque'));
    return masques.map(function (bloc) {
        const bouton = bloc.querySelector('[data-testid=btn-element-demasquer]');
        const boite = bloc.getBoundingClientRect();
        const style = getComputedStyle(bloc);
        const resultat = {
            identifiant: bloc.dataset.element || null,
            dans_le_champ: champ ? champ.contains(bloc) : null,
            bloc_visible: style.display !== 'none' && style.visibility !== 'hidden'
                          && boite.height > 0,
            hauteur_du_bloc: Math.round(boite.height),
            bouton_present: !!bouton,
        };
        if (bouton) {
            const b = bouton.getBoundingClientRect();
            const s = getComputedStyle(bouton);
            resultat.bouton_visible = s.display !== 'none' && s.visibility !== 'hidden'
                                      && b.height > 0 && s.opacity !== '0';
            resultat.bouton_taille = [Math.round(b.width), Math.round(b.height)];
            resultat.bouton_pointer_events = s.pointerEvents;
            resultat.bouton_tabindex = bouton.tabIndex;
        }
        return resultat;
    });
}"""

# Le champ est-il modifiable, et le placeholder est-il DEDANS ? Un bouton
# pose a l'interieur d'un contenteditable est atteignable a la souris,
# mais le clavier y navigue en texte, pas en widgets.
CONTEXTE_DU_CHAMP = """() => {
    const champ = document.querySelector('[data-testid=blocs-elements]');
    if (!champ) return null;
    return {
        contenteditable: champ.getAttribute('contenteditable'),
        mode_ouvert: document.getElementById('zone-lecture')
                     .classList.contains('mode-edition'),
    };
}"""


def sequence_de_tabulations(page, combien):
    """Ou va le focus apres N tabulations depuis le champ ?
    / Where does focus land after N tabs from the field?"""
    page.evaluate(
        "() => document.querySelector('[data-testid=blocs-elements]').focus()")
    atteints = []
    for _ in range(combien):
        page.keyboard.press("Tab")
        atteints.append(page.evaluate("""() => {
            const a = document.activeElement;
            if (!a) return null;
            return (a.dataset && a.dataset.testid)
                   || a.tagName.toLowerCase() + (a.id ? '#' + a.id : '');
        }"""))
    return atteints


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
    page.goto(f"{BASE}{NOTE}", wait_until="networkidle")
    page.wait_for_timeout(1800)
    page.evaluate("""() => {
        const d = document.getElementById('message-d-accueil'); if (d) d.remove();
        if (window.drawerVueListe && window.drawerVueListe.fermer)
            window.drawerVueListe.fermer();
    }""")
    page.wait_for_timeout(400)

    sortie["hors_du_mode"] = {
        "placeholders": page.evaluate(ETAT_DES_PLACEHOLDERS),
        "champ": page.evaluate(CONTEXTE_DU_CHAMP),
    }

    page.click('[data-testid="bouton-mode-edition"]')
    page.wait_for_timeout(700)

    sortie["dans_le_mode"] = {
        "placeholders": page.evaluate(ETAT_DES_PLACEHOLDERS),
        "champ": page.evaluate(CONTEXTE_DU_CHAMP),
        "tabulations_depuis_le_champ": sequence_de_tabulations(page, 4),
    }

    # Le placeholder porte-t-il du texte que le mode ENVERRAIT ? Un
    # placeholder serialise comme un bloc ecraserait le texte conserve.
    sortie["dans_le_mode"]["blocs_serialises"] = page.evaluate("""() => {
        const champ = document.querySelector('[data-testid=blocs-elements]');
        return champ
            ? champ.querySelectorAll('.bloc[data-element]').length : null;
    }""")
    sortie["dans_le_mode"]["placeholders_comptes_comme_blocs"] = page.evaluate(
        """() => document.querySelectorAll(
               '.element-masque.bloc[data-element]').length""")

    sortie["erreurs_js"] = erreurs
    navigateur.close()

print(json.dumps(sortie, indent=2, ensure_ascii=False))
