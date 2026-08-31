"""
LE CANAL `showToast` REND-IL DU HTML ?

Les vues envoient `HX-Trigger: {"showToast": {"message": ...}}`, et ces
messages portent des donnees ecrites par des humains : un nom de groupe,
le titre d'une base, et — depuis le 30 aout — le TITRE DE LA SYNTHESE
qui bloque une edition.

Si le client rend ce message en HTML, un titre de synthese suffit a
faire executer du script chez quiconque tente de corriger un passage
cite. Ce banc le mesure, sans rien creer en base : il envoie l'evenement
a la main, exactement comme le ferait une reponse du serveur.

AUCUNE ECRITURE. Aucune donnee piegee ne touche la base.
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_HYPOSTASIA", "https://beta.hypostasia.org")
UTILISATEUR = os.environ.get("BETA_UTILISATEUR", "jonas")
MOTDEPASSE = os.environ.get("BETA_MOTDEPASSE", "admin1234")

# Le piege : une balise que le navigateur EXECUTE s'il l'interprete, et
# qui laisse une trace mesurable. / A tag that leaves a measurable trace.
MESSAGE_PIEGE = (
    "Ce passage est cité par « <img src=x onerror=\"window.__balise_executee"
    "=true\"> ». Une synthèse adoptée ne doit pas changer."
)

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
    page.goto(f"{BASE}/lire/21/", wait_until="networkidle")
    page.wait_for_timeout(1200)

    page.evaluate(
        """(message) => {
            window.__balise_executee = false;
            document.body.dispatchEvent(new CustomEvent('showToast', {
                detail: {message: message, icon: 'warning'},
            }));
        }""", MESSAGE_PIEGE)
    page.wait_for_timeout(900)

    sortie["balise_executee"] = page.evaluate("() => !!window.__balise_executee")
    # DANS LE TITRE, et pas n'importe ou dans le toast : l'icone du
    # toast est elle-meme une image, et la chercher partout rend un
    # « vrai » qui ne veut rien dire.
    # / In the TITLE: the toast's own icon is an image.
    sortie["le_titre_porte_une_balise_img"] = page.evaluate(
        "() => !!document.querySelector('.swal2-toast .swal2-title img')")
    sortie["ce_que_le_toast_affiche"] = page.evaluate(
        """() => {
            const titre = document.querySelector('.swal2-toast .swal2-title');
            return titre ? titre.textContent.trim().slice(0, 120) : null;
        }""")
    sortie["html_du_titre"] = page.evaluate(
        """() => {
            const titre = document.querySelector('.swal2-toast .swal2-title');
            return titre ? titre.innerHTML.trim().slice(0, 160) : null;
        }""")
    sortie["erreurs_js"] = erreurs
    navigateur.close()

print(json.dumps(sortie, indent=2, ensure_ascii=False))
