"""
L'ACCESSIBILITE DU MODE, DE BOUT EN BOUT (SPEC-edition-par-blocs § 9).

CE QUE CE BANC EST, ET CE QU'IL N'EST PAS.

Il mesure l'ARBRE D'ACCESSIBILITE — ce que Chromium expose aux
technologies d'assistance : roles, noms accessibles, etats. C'est la
matiere premiere d'un lecteur d'ecran, et elle se mesure.

CE N'EST PAS UN LECTEUR D'ECRAN. NVDA, VoiceOver et Orca ont chacun
leur facon de restituer un `contenteditable` multi-blocs, d'annoncer une
region live, de nommer un `<details>`. Le § 9 dit « a eprouver avec un
vrai lecteur d'ecran, jamais en le supposant » : ce banc reduit ce qu'il
reste a eprouver a la main, il ne le remplace pas.

LA CHAINE DU § 9, dans l'ordre : entrer dans le mode -> atteindre le
champ -> naviguer -> etendre une selection -> vider -> enregistrer ->
LIRE LE COMPTE RENDU -> sortir. On mesure ce qui est ANNONCE a chaque
etape, et ce qu'un lecteur trouverait dans l'arbre.

AUCUNE ECRITURE : pas de Ctrl+S ici. L'annonce de l'enregistrement est
mesuree sur la note jetable du banc 21.
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_HYPOSTASIA", "https://beta.hypostasia.org")
UTILISATEUR = os.environ.get("BETA_UTILISATEUR", "jonas")
MOTDEPASSE = os.environ.get("BETA_MOTDEPASSE", "admin1234")
NOTE_TRANSCRITE = "/lire/4/"

# Ce que l'assistance lit du champ : role, nom, etat multiligne.
LE_CHAMP_DANS_L_ARBRE = """() => {
    const champ = document.querySelector('[data-testid=blocs-elements]');
    if (!champ) return null;
    return {
        role: champ.getAttribute('role'),
        nom_accessible: champ.getAttribute('aria-label'),
        multiligne: champ.getAttribute('aria-multiline'),
        modifiable: champ.getAttribute('contenteditable'),
    };
}"""

# Le repere de chaque bloc : « savoir ou l'on est sans regarder ».
LES_REPERES_DES_BLOCS = """() => {
    const blocs = document.querySelectorAll(
        '[data-testid=blocs-elements] .bloc[data-element]');
    let avecNumero = 0, avecLocuteur = 0;
    const premiers = [];
    blocs.forEach(function (bloc, rang) {
        const numero = bloc.querySelector('.numero-element');
        const locuteur = bloc.querySelector('.etiquette-locuteur');
        if (numero && numero.textContent.trim()) avecNumero += 1;
        if (locuteur && locuteur.textContent.trim()) avecLocuteur += 1;
        if (rang < 3) {
            premiers.push({
                numero: numero ? numero.textContent.trim() : null,
                locuteur: locuteur ? locuteur.textContent.trim() : null,
                // La gouttiere est-elle LUE ? Elle est hors du champ
                // modifiable, mais dans l'arbre.
                gouttiere_masquee_a_l_assistance:
                    !!bloc.querySelector('.gouttiere[aria-hidden="true"]'),
            });
        }
    });
    return {blocs: blocs.length, avecNumero: avecNumero,
            avecLocuteur: avecLocuteur, premiers: premiers};
}"""

# La region qui porte les annonces du mode.
LA_REGION_D_ANNONCES = """() => {
    const zone = document.getElementById('zone-annonces');
    if (!zone) return null;
    return {
        role: zone.getAttribute('role'),
        live: zone.getAttribute('aria-live'),
        atomique: zone.getAttribute('aria-atomic'),
        visible_a_l_ecran: zone.getBoundingClientRect().height > 1,
        contenu: zone.textContent.trim().slice(0, 120),
    };
}"""


def annonces_observees(page):
    """Ce que la region live a recu depuis la pose de l'observateur."""
    return page.evaluate("() => window.__annonces || []")


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
    page.wait_for_timeout(1500)
    page.evaluate("""() => {
        const d = document.getElementById('message-d-accueil'); if (d) d.remove();
        if (window.drawerVueListe && window.drawerVueListe.fermer)
            window.drawerVueListe.fermer();
    }""")

    # L'observateur des annonces, pose AVANT tout geste.
    page.evaluate("""() => {
        window.__annonces = [];
        const zone = document.getElementById('zone-annonces');
        if (!zone) return;
        new MutationObserver(function () {
            const dit = zone.textContent.trim();
            if (dit && window.__annonces[window.__annonces.length - 1] !== dit) {
                window.__annonces.push(dit);
            }
        }).observe(zone, {childList: true, subtree: true, characterData: true});
    }""")

    sortie["la_region_d_annonces"] = page.evaluate(LA_REGION_D_ANNONCES)

    # --- 1. ENTRER DANS LE MODE, au clavier seul ---
    sortie["le_bouton_du_mode"] = page.evaluate(
        """() => {
            const b = document.querySelector('[data-testid=bouton-mode-edition]');
            if (!b) return null;
            return {nom_accessible: (b.textContent || '').trim(),
                    pressé: b.getAttribute('aria-pressed'),
                    atteignable: b.tabIndex >= 0};
        }""")
    page.click('[data-testid="bouton-mode-edition"]')
    page.wait_for_timeout(700)
    sortie["annonce_a_l_entree"] = annonces_observees(page)
    sortie["le_champ_dans_l_arbre"] = page.evaluate(LE_CHAMP_DANS_L_ARBRE)
    sortie["aria_pressed_apres_entree"] = page.evaluate(
        """() => document.querySelector('[data-testid=bouton-mode-edition]')
                 .getAttribute('aria-pressed')""")

    # --- 2. SAVOIR OU L'ON EST SANS REGARDER ---
    sortie["les_reperes_des_blocs"] = page.evaluate(LES_REPERES_DES_BLOCS)

    # --- 3. LES GESTES DE STENOTYPIE S'ANNONCENT ---
    page.evaluate("() => window.__annonces = []")
    page.keyboard.press("F4")
    page.wait_for_timeout(400)
    page.keyboard.press("F10")
    page.wait_for_timeout(400)
    page.keyboard.press("F7")
    page.wait_for_timeout(400)
    page.keyboard.press("F4")
    page.wait_for_timeout(300)
    sortie["annonces_des_gestes_de_son"] = annonces_observees(page)

    # --- 4. L'ARBRE D'ACCESSIBILITE, TEL QUE CHROMIUM LE PUBLIE ---
    #
    # Pas `page.accessibility` : cette API a disparu du Playwright
    # Python. On passe par CDP, qui donne l'arbre COMPLET — celui que le
    # navigateur remet aux technologies d'assistance, et non ce que les
    # attributs promettent.
    # / Through CDP: the tree the browser hands to assistive tech.
    session = contexte.new_cdp_session(page)
    session.send("Accessibility.enable")
    noeuds = session.send("Accessibility.getFullAXTree").get("nodes", [])

    def noeuds_du_role(role_vise):
        """Les noeuds d'un role, avec leur nom accessible."""
        trouves = []
        for noeud in noeuds:
            role = (noeud.get("role") or {}).get("value")
            if role != role_vise:
                continue
            nom = (noeud.get("name") or {}).get("value") or ""
            trouves.append(nom.strip()[:80])
        return trouves

    sortie["le_champ_vu_par_chromium"] = noeuds_du_role("textbox")
    sortie["les_regions_live_vues_par_chromium"] = noeuds_du_role("status")
    sortie["combien_de_noeuds_dans_l_arbre"] = len(noeuds)

    # --- 5. SORTIR ---
    page.evaluate("() => window.__annonces = []")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    sortie["annonce_a_la_sortie"] = annonces_observees(page)
    sortie["aria_pressed_apres_sortie"] = page.evaluate(
        """() => document.querySelector('[data-testid=bouton-mode-edition]')
                 .getAttribute('aria-pressed')""")

    # --- 6. L'AIDE REND-ELLE LA TABLE ? (chantier 11) ---
    page.keyboard.press("?")
    page.wait_for_timeout(1200)
    sortie["l_aide"] = page.evaluate(
        """() => {
            const section = document.getElementById('aide-raccourcis-du-mode');
            const marqueurs = Array.from(
                document.querySelectorAll('[data-raccourci]'))
                .map(function (m) { return m.textContent.trim(); });
            if (!section) return {section: false, marqueurs: marqueurs};
            const lignes = Array.from(
                section.querySelectorAll('dt')).map(function (dt) {
                    return dt.textContent.trim();
                });
            return {
                section: true,
                cachee: section.hidden,
                touches_listees: lignes,
                marqueurs_dans_la_prose: marqueurs,
            };
        }""")

    sortie["erreurs_js"] = erreurs
    navigateur.close()

print(json.dumps(sortie, indent=2, ensure_ascii=False))
