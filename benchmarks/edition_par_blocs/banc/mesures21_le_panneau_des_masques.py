"""
LE PANNEAU DES PASSAGES MASQUES, dans le mode d'edition (SPEC § 5.3, cas 4).

Ce banc ECRIT en base — le retablissement est un vrai POST. Il travaille
donc sur une NOTE JETABLE, creee au debut et supprimee a la fin : les
notes reelles portent des ancrages qu'une fausse manoeuvre detacherait.

CE QU'IL MESURE
  1. le panneau se voit dans le mode, et NULLE PART ailleurs ;
  2. son compte dit le vrai nombre ;
  3. les contrastes, EN CLAIR ET EN SOMBRE, calcules — pas jauges ;
  4. le geste complet, DANS LES DEUX SENS :
     - vider un bloc puis Ctrl+S -> le passage masque APPARAIT dans le
       panneau, sans rechargement (c'est le cas d'usage fondateur du
       § 5.3 cas 4 : le mode masque, donc le mode doit pouvoir defaire) ;
     - clic « retablir » -> le bloc revient dans le champ, la ligne
       quitte le panneau, le compte suit ;
  5. le panneau est HORS du champ modifiable (il n'est pas serialise) ;
  6. zero erreur JavaScript.
"""
import json
import os
import subprocess

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_HYPOSTASIA", "https://beta.hypostasia.org")
UTILISATEUR = os.environ.get("BETA_UTILISATEUR", "jonas")
MOTDEPASSE = os.environ.get("BETA_MOTDEPASSE", "admin1234")

CREER = """
from core.models import (AppartenancePageDossier, Dossier, ElementDocument,
                         Page, empreinte_du_texte)
from django.contrib.auth import get_user_model
jonas = get_user_model().objects.get(username="%s")
carnet = Dossier.objects.filter(owner=jonas).first()
page = Page.objects.create(
    url="http://exemple.local/jetable-panneau-des-masques",
    html_original="<p>o</p>", html_readability="<p>l</p>",
    text_readability="texte", content_hash="hash-jetable-panneau",
    owner=jonas, dossier=carnet, title="Note jetable — panneau des masqués",
)
AppartenancePageDossier.objects.create(page=page, dossier=carnet)
for ordre, (texte, masque) in enumerate([
    ("Le premier passage, bien visible.", False),
    ("Le pied de page repete, masque pendant une session.", True),
    ("Le bandeau de cookies, masque lui aussi.", True),
    ("Le dernier passage, bien visible lui aussi.", False),
]):
    ElementDocument.objects.create(
        page=page, ordre=ordre, label="text", texte=texte,
        empreinte_contenu=empreinte_du_texte(texte), masque=masque,
    )
print("PAGE_JETABLE=%%s" %% page.pk)
""" % UTILISATEUR

SUPPRIMER = """
from core.models import Page
Page.objects.filter(url="http://exemple.local/jetable-panneau-des-masques").delete()
print("SUPPRIMEE")
"""


def shell(script):
    """Passe par le manage.py du conteneur — on y est deja."""
    resultat = subprocess.run(
        ["python", "manage.py", "shell", "-c", script],
        capture_output=True, text=True, cwd="/app",
    )
    return resultat.stdout + resultat.stderr


# Le contraste se CALCULE (WCAG 2.1), il ne se juge pas a l'oeil.
CONTRASTES = """() => {
    // DEUX FORMATS, ET LES CONFONDRE FAUSSE TOUT.
    // `color-mix()` (nos tokens de filet) est rendu par Chromium en
    // `color(srgb 0.42 0.41 0.38)` — des composantes 0..1 — alors que
    // `color`/`backgroundColor` viennent en `rgb(107, 104, 98)`, en
    // 0..255. Lire les deux avec la meme echelle rendait un filet a
    // 19,73:1 la ou il vaut ~5 : un contraste invente.
    const composantes = (couleur) => {
        const nombres = couleur.match(/-?\\d+(\\.\\d+)?/g).map(Number);
        const enFraction = couleur.indexOf('color(') === 0;
        return nombres.slice(0, 3).map(v => enFraction ? v : v / 255);
    };
    const luminance = (couleur) => {
        const c = composantes(couleur).map(v => {
            return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    };
    const ratio = (a, b) => {
        const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
        return Math.round(((x + 0.05) / (y + 0.05)) * 100) / 100;
    };
    const panneau = document.getElementById('panneau-des-passages-masques');
    if (!panneau) return null;
    const stylePanneau = getComputedStyle(panneau);
    const resume = panneau.querySelector('summary');
    const bouton = panneau.querySelector('button');
    const fond = stylePanneau.backgroundColor;
    const mesures = {
        fond_du_panneau: fond,
        resume_sur_le_fond: ratio(getComputedStyle(resume).color, fond),
        extrait_sur_le_fond: ratio(
            getComputedStyle(panneau.querySelector('.extrait')).color, fond),
    };
    if (bouton) {
        const styleBouton = getComputedStyle(bouton);
        mesures.texte_du_bouton = ratio(styleBouton.color,
                                        styleBouton.backgroundColor);
        mesures.filet_du_bouton = ratio(styleBouton.borderTopColor, fond);
        mesures.couleur_du_filet = styleBouton.borderTopColor;
        mesures.couleur_du_texte = styleBouton.color;
        const boite = bouton.getBoundingClientRect();
        mesures.taille_du_bouton = [Math.round(boite.width),
                                    Math.round(boite.height)];
    }
    return mesures;
}"""

ETAT_DU_PANNEAU = """() => {
    const panneau = document.getElementById('panneau-des-passages-masques');
    const champ = document.querySelector('[data-testid=blocs-elements]');
    if (!panneau) return {present: false};
    const boite = panneau.getBoundingClientRect();
    return {
        present: true,
        visible: getComputedStyle(panneau).display !== 'none' && boite.height > 0,
        hauteur: Math.round(boite.height),
        compte: panneau.querySelector('[data-testid=compte-des-masques]')
                .textContent.trim(),
        lignes: panneau.querySelectorAll('li').length,
        dans_le_champ: champ ? champ.contains(panneau) : null,
        blocs_du_champ: champ
            ? champ.querySelectorAll('.bloc[data-element]').length : null,
    };
}"""

creation = shell(CREER)
identifiant = [ligne for ligne in creation.splitlines()
               if ligne.startswith("PAGE_JETABLE=")]
if not identifiant:
    raise SystemExit("La note jetable n'a pas pu être créée :\n" + creation)
page_jetable = identifiant[0].split("=")[1]

sortie = {"page_jetable": page_jetable}
try:
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
        page.goto(f"{BASE}/lire/{page_jetable}/", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.evaluate("""() => {
            const d = document.getElementById('message-d-accueil'); if (d) d.remove();
            if (window.drawerVueListe && window.drawerVueListe.fermer)
                window.drawerVueListe.fermer();
        }""")
        page.wait_for_timeout(300)

        sortie["hors_du_mode"] = page.evaluate(ETAT_DU_PANNEAU)

        page.click('[data-testid="bouton-mode-edition"]')
        page.wait_for_timeout(600)
        sortie["dans_le_mode"] = page.evaluate(ETAT_DU_PANNEAU)
        page.evaluate(
            "() => document.getElementById('panneau-des-passages-masques')"
            ".setAttribute('open', 'open')")
        page.wait_for_timeout(200)
        sortie["contrastes_en_clair"] = page.evaluate(CONTRASTES)

        # LE SOMBRE, sur la meme page et le meme panneau.
        page.evaluate(
            "() => document.documentElement.setAttribute('data-theme', 'dark')")
        page.wait_for_timeout(300)
        sortie["contrastes_en_sombre"] = page.evaluate(CONTRASTES)
        page.evaluate(
            "() => document.documentElement.setAttribute('data-theme', 'light')")

        # PREMIER SENS : MASQUER PENDANT LA SESSION.
        #
        # On vide un bloc au clavier — le vrai chemin, celui qui passe
        # par la garde `beforeinput` — puis on enregistre. Le passage
        # masque doit ENTRER dans le panneau sans rechargement.
        # / First direction: hide during the session, via the keyboard.
        page.evaluate("""() => {
            const champ = document.querySelector('[data-testid=blocs-elements]');
            const bloc = champ.querySelector('.bloc[data-element]');
            const interne = bloc.querySelector('[data-element-id]') || bloc;
            const plage = document.createRange();
            plage.selectNodeContents(interne);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(plage);
        }""")
        page.keyboard.press("Delete")
        page.wait_for_timeout(300)
        page.keyboard.press("Control+s")
        page.wait_for_timeout(2500)
        sortie["apres_avoir_masque_en_session"] = page.evaluate(ETAT_DU_PANNEAU)
        # LE SUCCES SE VOIT-IL ? Le compte rendu s'affiche EN TETE de la
        # note ; le toast, lui, est en haut a droite quel que soit le
        # defilement. C'est le seul retour visible d'un Ctrl+S reussi.
        # / Is the success visible where the eye is?
        sortie["toast_apres_un_enregistrement"] = page.evaluate(
            """() => {
                const t = document.querySelector('.swal2-toast .swal2-title');
                return t ? t.textContent.trim().slice(0, 120) : null;
            }""")
        sortie["le_panneau_est_reste_ouvert"] = page.evaluate(
            """() => {
                const p = document.getElementById('panneau-des-passages-masques');
                return p ? p.open : null;
            }""")
        sortie["compte_rendu_affiche"] = page.evaluate(
            r"""() => {
                const a = document.getElementById('compte-rendu-du-lot');
                return a ? a.textContent.replace(/\s+/g, ' ').trim().slice(0, 160)
                         : null;
            }""")

        # LE GESTE COMPLET, EN DEUX TEMPS.
        #
        # Le premier retablissement laisse un masque : c'est le chemin ou
        # le compte se DECREMENTE. Le second est le dernier : c'est le
        # chemin ou le panneau DISPARAIT. Mesurer le second seul
        # laisserait le recalcul du compte non eprouve.
        # / Two steps: the count decrements, then the panel goes.
        page.click('[data-testid="btn-retablir-1"]')
        page.wait_for_timeout(1500)
        sortie["apres_le_premier"] = page.evaluate(ETAT_DU_PANNEAU)
        sortie["blocs_du_champ_apres_le_premier"] = page.evaluate(
            """() => document.querySelectorAll(
                   '[data-testid=blocs-elements] .bloc[data-element]').length""")

        page.click('[data-testid="btn-retablir-2"]')
        page.wait_for_timeout(1500)
        sortie["apres_le_retablissement"] = page.evaluate(ETAT_DU_PANNEAU)
        sortie["blocs_du_champ_apres"] = page.evaluate(
            """() => document.querySelectorAll(
                   '[data-testid=blocs-elements] .bloc[data-element]').length""")
        sortie["mode_toujours_ouvert"] = page.evaluate(
            """() => document.getElementById('zone-lecture')
                   .classList.contains('mode-edition')""")
        sortie["erreurs_js"] = erreurs
        navigateur.close()
finally:
    sortie["nettoyage"] = shell(SUPPRIMER).strip().splitlines()[-1:]

print(json.dumps(sortie, indent=2, ensure_ascii=False))
