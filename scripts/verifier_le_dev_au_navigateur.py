"""
Verifie l'application dev au navigateur, captures a l'appui.
/ Checks the dev application in a browser, with screenshots.

LOCALISATION : scripts/verifier_le_dev_au_navigateur.py

CE QUE CE SCRIPT VERIFIE

Les tests unitaires prouvent que les fonctions font ce qu'on croit. Ils ne
prouvent pas que l'application repond, que les pages s'affichent, ni que
la garde d'edition arrive vraiment jusqu'a l'utilisateur.

Ce script fait les deux a la fois : il regarde l'ecran ET la base de
donnees, sur le meme scenario. Une capture qui montre une page correcte
pendant que la base dit le contraire, ca se voit ici et nulle part ailleurs.
/ It watches the screen AND the database on the same scenario.

LANCER LE SCRIPT

    docker exec -e PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright \\
        hypostasia_dev_web uv run python scripts/verifier_le_dev_au_navigateur.py

Les captures sont ecrites dans /app/tmp/captures/.
"""

import os
import sys

import django

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")

# Playwright en mode synchrone tourne dans une boucle asyncio. Django
# refuse alors ses requetes ORM synchrones, par securite : dans une vraie
# vue async, une requete bloquante gelerait la boucle.
#
# Ici, on est dans un script de verification a un seul fil : il n'y a
# aucune boucle a geler. Django fournit exactement ce reglage pour ce cas.
# / Playwright sync API runs inside an asyncio loop; this flag is Django's
# supported escape hatch for single-threaded scripts.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from core.models import ElementDocument, Page, empreinte_du_texte  # noqa: E402
from hypostasis_extractor.models import (  # noqa: E402
    AncrageExtraction,
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)
from hypostasis_extractor.services.garde_edition import (  # noqa: E402
    une_analyse_tourne_sur_la_page,
)

ADRESSE_DU_SITE = "https://hyp.nasjo.fr"
DOSSIER_DES_CAPTURES = "/app/tmp/captures"

MOT_DE_PASSE_DE_TEST = "verif_navigateur_2026"
NOM_D_UTILISATEUR_DE_TEST = "verificateur_navigateur"


def preparer_le_jeu_de_donnees():
    """
    Cree un utilisateur, une page et ses elements ancres.
    / Creates a user, a page and its anchored elements.
    """
    Utilisateur = get_user_model()
    utilisateur = Utilisateur.objects.filter(
        username=NOM_D_UTILISATEUR_DE_TEST,
    ).first()
    if utilisateur is None:
        utilisateur = Utilisateur.objects.create_user(
            username=NOM_D_UTILISATEUR_DE_TEST,
            password=MOT_DE_PASSE_DE_TEST,
        )
    else:
        utilisateur.set_password(MOT_DE_PASSE_DE_TEST)
        utilisateur.save()

    page = Page.objects.create(
        url="http://verif.local/page-au-navigateur",
        html_original="<p>o</p>",
        html_readability=(
            "<p>L'IA ne doit pas remplacer :</p>"
            "<p>le jugement des personnes concernees</p>"
            "<p>la deliberation collective</p>"
        ),
        text_readability=(
            "L'IA ne doit pas remplacer :\n\n"
            "le jugement des personnes concernees\n\n"
            "la deliberation collective"
        ),
        content_hash="verif_navigateur",
        title="Page de verification au navigateur",
        owner=utilisateur,
    )

    elements = []
    for numero, texte in enumerate([
        "L'IA ne doit pas remplacer :",
        "le jugement des personnes concernees",
        "la deliberation collective",
    ]):
        elements.append(ElementDocument.objects.create(
            page=page, ordre=numero, label="text", texte=texte,
            empreinte_contenu=empreinte_du_texte(texte),
        ))

    return utilisateur, page, elements


def ancrer_une_extraction_sur_trois_elements(page, elements):
    """
    Cree une extraction ancree sur les trois elements.
    / Creates an extraction anchored across the three elements.
    """
    job = ExtractionJob.objects.create(
        page=page, name="Job de verification",
        prompt_description="Extraire",
        status=ExtractionJobStatus.COMPLETED,
    )
    extraction = ExtractedEntity.objects.create(
        job=job, extraction_class="hypostase",
        extraction_text="L'IA ne doit pas remplacer le jugement ni la deliberation",
        start_char=0, end_char=94,
    )
    for numero, element in enumerate(elements):
        AncrageExtraction.objects.create(
            extraction=extraction, element=element,
            ordre_dans_extraction=numero,
            debut_dans_element=0, fin_dans_element=len(element.texte),
        )
    return job, extraction


def verifier(intitule, condition, detail=""):
    """Affiche un resultat de verification. / Prints a check result."""
    marque = "OK  " if condition else "ECHEC"
    print(f"  [{marque}] {intitule}" + (f" — {detail}" if detail else ""))
    return condition


def main():
    os.makedirs(DOSSIER_DES_CAPTURES, exist_ok=True)
    utilisateur, page, elements = preparer_le_jeu_de_donnees()
    job, extraction = ancrer_une_extraction_sur_trois_elements(page, elements)
    tout_va_bien = True

    print("=" * 78)
    print("VERIFICATION AU NAVIGATEUR — application dev")
    print("=" * 78)
    print(f"\nPage de test : {page.pk} — {page.title}")
    print(f"Elements : {page.elements.count()} | "
          f"Extraction ancree sur {extraction.ancrages.count()} elements")

    try:
        with sync_playwright() as pilote:
            navigateur = pilote.chromium.launch()
            contexte = navigateur.new_context(viewport={
                "width": 1400, "height": 900,
            })
            onglet = contexte.new_page()

            # --- 1. La page d'accueil repond ---
            print("\n>>> 1. Page d'accueil")
            onglet.goto(ADRESSE_DU_SITE, wait_until="networkidle")
            onglet.screenshot(
                path=f"{DOSSIER_DES_CAPTURES}/1-accueil.png", full_page=True,
            )
            tout_va_bien &= verifier(
                "l'accueil s'affiche", "Hypostasia" in onglet.title(),
                onglet.title(),
            )

            # --- 2. Connexion ---
            print("\n>>> 2. Connexion")
            onglet.goto(
                f"{ADRESSE_DU_SITE}/auth/login/", wait_until="networkidle",
            )
            onglet.fill('input[name="username"]', NOM_D_UTILISATEUR_DE_TEST)
            onglet.fill('input[name="password"]', MOT_DE_PASSE_DE_TEST)
            onglet.click('button[type="submit"]')
            onglet.wait_for_load_state("networkidle")
            onglet.screenshot(
                path=f"{DOSSIER_DES_CAPTURES}/2-connecte.png", full_page=True,
            )
            tout_va_bien &= verifier(
                "connexion acceptee", "/auth/login" not in onglet.url,
                onglet.url,
            )

            # --- 3. La page de lecture s'affiche ---
            print("\n>>> 3. Page de lecture")
            onglet.goto(
                f"{ADRESSE_DU_SITE}/lire/{page.pk}/",
                wait_until="networkidle",
            )
            onglet.screenshot(
                path=f"{DOSSIER_DES_CAPTURES}/3-lecture.png", full_page=True,
            )
            contenu_affiche = onglet.content()
            tout_va_bien &= verifier(
                "le texte de la page est affiche",
                "jugement des personnes" in contenu_affiche,
            )

            # --- 4. La garde d'edition, ecran ET base ---
            print("\n>>> 4. Garde d'edition pendant une analyse")

            tout_va_bien &= verifier(
                "aucune analyse en cours au depart",
                not une_analyse_tourne_sur_la_page(page),
            )

            # On lance une analyse fictive : le job passe en cours.
            # / A fictitious analysis: the job goes to PROCESSING.
            job.status = ExtractionJobStatus.PROCESSING
            job.save(update_fields=["status", "updated_at"])

            tout_va_bien &= verifier(
                "la base voit l'analyse en cours",
                une_analyse_tourne_sur_la_page(page),
            )

            # L'edition doit maintenant etre refusee, avec un 409.
            # / The edit must now be refused with a 409.
            jeton_csrf = onglet.evaluate(
                "() => document.querySelector('[name=csrfmiddlewaretoken]')"
                "?.value || document.body.dataset.csrf || ''"
            )
            reponse = onglet.request.post(
                f"{ADRESSE_DU_SITE}/lire/{page.pk}/editer_bloc/",
                form={
                    "index_bloc": "0",
                    "nouveau_texte": "Texte modifie pendant l'analyse",
                    "csrfmiddlewaretoken": jeton_csrf,
                },
                headers={
                    "HX-Request": "true",
                    "Referer": f"{ADRESSE_DU_SITE}/lire/{page.pk}/",
                },
            )
            if reponse.status != 409:
                print(f"      diagnostic — corps : {reponse.text()[:200]!r}")
            tout_va_bien &= verifier(
                "l'edition est refusee pendant l'analyse",
                reponse.status == 409,
                f"HTTP {reponse.status} (409 attendu)",
            )
            entete_htmx = reponse.headers.get("hx-trigger", "")
            tout_va_bien &= verifier(
                "un message est renvoye a l'interface",
                "analyse est en cours" in entete_htmx,
                entete_htmx[:70] if entete_htmx else "(aucun HX-Trigger)",
            )

            # Le texte en base n'a pas bouge : le refus arrive AVANT
            # toute ecriture. / The refusal comes BEFORE any write.
            page.refresh_from_db()
            tout_va_bien &= verifier(
                "rien n'a ete ecrit en base malgre la tentative",
                "Texte modifie pendant l'analyse" not in page.text_readability,
            )

            # --- 5. Une fois l'analyse finie, l'edition repasse ---
            print("\n>>> 5. Retour a la normale")
            job.status = ExtractionJobStatus.COMPLETED
            job.save(update_fields=["status", "updated_at"])
            tout_va_bien &= verifier(
                "l'analyse n'est plus signalee comme en cours",
                not une_analyse_tourne_sur_la_page(page),
            )

            onglet.goto(
                f"{ADRESSE_DU_SITE}/lire/{page.pk}/",
                wait_until="networkidle",
            )
            onglet.screenshot(
                path=f"{DOSSIER_DES_CAPTURES}/4-apres-analyse.png",
                full_page=True,
            )
            tout_va_bien &= verifier(
                "la page de lecture repond toujours",
                onglet.title() != "",
            )

            # --- 6. L'etat des elements, en base ---
            print("\n>>> 6. Etat des elements en base")
            for element in page.elements.order_by("ordre"):
                print(
                    f"      element {element.ordre} | etat={element.etat} | "
                    f"{element.portions_d_extractions.count()} portion(s) | "
                    f"{element.texte[:38]!r}"
                )
            tout_va_bien &= verifier(
                "les trois elements portent une portion",
                all(
                    element.portions_d_extractions.count() == 1
                    for element in page.elements.all()
                ),
            )
            tout_va_bien &= verifier(
                "les trois elements sont a l'etat analyse",
                all(
                    element.etat == "analyse"
                    for element in page.elements.all()
                ),
            )

            navigateur.close()
    finally:
        AncrageExtraction.objects.filter(element__page=page).delete()
        ExtractedEntity.objects.filter(job=job).delete()
        page.elements.all().delete()
        job.delete()
        page.delete()

    print("\n" + "=" * 78)
    print("VERDICT :", "TOUT EST VERT" if tout_va_bien else "DES ECHECS")
    print(f"Captures : {DOSSIER_DES_CAPTURES}/")
    print("=" * 78)
    return 0 if tout_va_bien else 1


if __name__ == "__main__":
    sys.exit(main())
