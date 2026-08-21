#!/usr/bin/env python
"""
Banc MANUEL : REPETER la comparaison des redacteurs, pour mesurer le bruit.
/ MANUAL bench: REPEAT the writers' comparison to measure the noise.

LOCALISATION : benchmarks/redaction/lancer_les_passes.py

CE QU'IL REPOND, ET POURQUOI IL EXISTE. Toutes les campagnes precedentes
ont fait UNE passe par modele. Elles ne pouvaient donc pas distinguer un
ecart de modele d'un ecart de tirage : « Small 36 % contre Medium 41 % »
etait publiable, mais indefendable. Celui-ci repete chaque condition et
mesure l'ecart entre les repetitions.

DEUX SOURCES DE VARIATION, ET IL LES SEPARE :

- entre PASSES d'un meme modele sur un meme article : c'est le BRUIT.
  A temperature 0 il devrait etre nul ; il ne l'est jamais tout a fait ;
- entre ARTICLES d'un meme modele : c'est l'effet du SUJET. Un corpus
  peut avantager un modele sur un sujet et le desavantager sur un autre.

Un ecart entre modeles ne vaut que s'il depasse ces deux-la.

CE QU'IL ECRIT EN BASE. Il CREE les wikis manquants dans le carnet
etalon, puis reproduit tous les articles a chaque passe. Les wikis
crees restent apres coup — c'est voulu, ils sont le corpus du banc.
Pour les retirer : voir le CHANGELOG.

IL APPELLE DE VRAIS MODELES : C'EST FACTURE.
"""

import json
import os
import sys
import time
from collections import Counter, defaultdict

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."),
))

import django  # noqa: E402

django.setup()

from core.models import (  # noqa: E402
    Dossier, ModeleParRole, Page, RoleDeModele, SourceLink, TypeDeNote,
    TypeLien, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet  # noqa: E402
from core.services.modeles_par_role import modele_du_role  # noqa: E402
from hypostasis_extractor.models import ExtractionJob  # noqa: E402

NOM_DU_CARNET_ETALON = "Documents étalons"

# LES SUJETS SUPPLEMENTAIRES, choisis pour toucher des parties
# DIFFERENTES du corpus. Un seul sujet ne dirait rien de la variation
# entre articles — et c'est precisement ce qu'on veut mesurer.
#
# LE SUJET ETALON N'Y FIGURE PAS, et c'est deliberé :
# `produire_les_syntheses_etalons --forcer` le produit deja a chaque
# passe. L'y remettre le ferait produire DEUX FOIS, donc facturer deux
# fois, pour un resultat que la seconde production ecrase.
# / The reference subject is absent on purpose: the management command
#   already produces it every pass.
SUJETS_DES_WIKIS = [
    "Les limites de l'explicabilité des systèmes d'IA",
    "La gouvernance collective des outils numériques",
]

DELAI_ENTRE_DEUX_CONTROLES = 10
CONTROLES_MAXIMUM = 180


def _carnet():
    carnet = Dossier.objects.filter(name=NOM_DU_CARNET_ETALON).first()
    if carnet is None:
        raise SystemExit(f"Carnet « {NOM_DU_CARNET_ETALON} » absent.")
    return carnet


def preparer_les_wikis(carnet):
    """
    Cree les wikis manquants. / Creates the missing wikis.

    Idempotent : un sujet deja present est reutilise, jamais duplique.
    """
    wikis = []
    for sujet in SUJETS_DES_WIKIS:
        wiki = Wiki.objects.filter(dossier=carnet, sujet=sujet).first()
        if wiki is None:
            page = Page.objects.create(
                title=f"Wiki — {sujet}"[:500],
                text_readability="", html_readability="", html_original="",
                content_hash="", type_de_note=TypeDeNote.WIKI,
                owner=carnet.owner,
            )
            ranger_une_note_dans_un_carnet(page, carnet, carnet.owner)
            wiki = Wiki.objects.create(
                page=page, dossier=carnet, sujet=sujet,
            )
            print(f"    wiki créé : « {sujet[:50]} »")
        wikis.append(wiki)
    return wikis


def _attendre_les_jobs(identifiants):
    """Attend que ces jobs quittent pending/processing. / Waits."""
    for _ in range(CONTROLES_MAXIMUM):
        etats = dict(
            ExtractionJob.objects.filter(pk__in=identifiants)
            .values_list("pk", "status")
        )
        if not any(e in ("pending", "processing") for e in etats.values()):
            return etats
        time.sleep(DELAI_ENTRE_DEUX_CONTROLES)
    raise SystemExit(f"Jobs toujours en cours après attente : {identifiants}")


def produire_les_wikis(carnet, wikis, taille_du_perimetre):
    """Envoie chaque wiki au modele du role redacteur. / Sends each wiki."""
    from front.tasks import produire_un_wiki_task

    identifiants = []
    for wiki in wikis:
        job = ExtractionJob.objects.create(
            page=wiki.page,
            ai_model=modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE),
            name=f"Wiki — {wiki.sujet}"[:200],
            prompt_description="Banc des rédacteurs",
            status="pending",
            raw_result={
                "est_wiki": True, "wiki_id": wiki.pk,
                "demandeur_id": carnet.owner_id,
                "taille_du_perimetre": taille_du_perimetre,
            },
        )
        produire_un_wiki_task.delay(job.pk)
        # UN PAR UN, ET CE N'EST PAS UNE PRECAUTION. Envoyer les wikis
        # d'un coup met plusieurs appels en vol simultanement et l'API
        # repond « 429 Rate limit exceeded » : le job part en `error`,
        # la garde ecarte la passe entiere, et la campagne perd une
        # repetition — donc la mesure du bruit qu'on vient chercher.
        # / Parallel sends hit the rate limit and cost a whole pass.
        _attendre_les_jobs([job.pk])
        identifiants.append(job.pk)
    return identifiants


def controler_la_passe(modele_attendu):
    """
    Le dernier job de production de CHAQUE article doit etre completed,
    et du modele attendu. / Every article's last production job must be
    completed, and from the expected model.

    C'EST LA GARDE QUI MANQUAIT le 19 aout : un job en `error` satisfait
    « plus rien en attente », et la campagne avait mesure un article
    reste d'une passe anterieure.
    """
    problemes = []
    for page in Page.objects.filter(
        appartenances_dossiers__dossier__name=NOM_DU_CARNET_ETALON,
    ).exclude(type_de_note=TypeDeNote.NOTE).distinct():
        job = (
            ExtractionJob.objects.filter(page=page)
            .exclude(raw_result__contains={"est_verification": True})
            .order_by("-pk").select_related("ai_model").first()
        )
        if job is None or job.status != "completed":
            problemes.append(f"{page.title[:34]} : {job.status if job else 'aucun job'}")
        elif job.ai_model and job.ai_model.model_choice != modele_attendu:
            problemes.append(
                f"{page.title[:34]} : produit par {job.ai_model.model_choice}"
            )
    return problemes


def mesurer_les_articles_de_la_passe():
    """L'etat de chaque article, apres verification. / Per-article state."""
    import importlib.util

    specification = importlib.util.spec_from_file_location(
        "mesurer_les_redacteurs",
        os.path.join(os.path.dirname(__file__), "mesurer_les_redacteurs.py"),
    )
    banc = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(banc)

    articles = []
    for page in Page.objects.filter(
        appartenances_dossiers__dossier__name=NOM_DU_CARNET_ETALON,
    ).exclude(type_de_note=TypeDeNote.NOTE).distinct():
        liens = SourceLink.objects.filter(
            page_cible=page, type_lien=TypeLien.CITE,
        )
        etats = Counter(liens.values_list("etat_de_verification", flat=True))
        prose = banc.part_de_prose_sans_marqueur(page.text_readability or "")
        articles.append({
            "titre": page.title,
            "caracteres": len(page.text_readability or ""),
            "citations": liens.count(),
            "distinctes": liens.values("extraction_source_id").distinct().count(),
            "etats": dict(etats),
            "prose_nue": prose,
        })
    return articles


def main():
    modeles = json.loads(os.environ.get(
        "MODELES_DU_BANC",
        '{"small": 1, "medium": 5, "large": 4}',
    ))
    nombre_de_passes = int(os.environ.get("NOMBRE_DE_PASSES", "3"))

    carnet = _carnet()
    from core.services.synthese import (
        extractions_citables_de_la_note, notes_sources_du_carnet,
    )
    taille = sum(
        extractions_citables_de_la_note(note).count()
        for note in notes_sources_du_carnet(carnet)
    )
    print(f"Périmètre : {taille} extractions citables.")

    wikis = preparer_les_wikis(carnet)
    print(f"{len(wikis) + 1} wiki(s) + 1 synthèse × {len(modeles)} modèle(s) "
          f"× {nombre_de_passes} passe(s)\n")

    resultats = defaultdict(list)
    for nom, identifiant in modeles.items():
        from core.models import AIModel

        modele = AIModel.objects.get(pk=identifiant)
        ModeleParRole.objects.update_or_create(
            role=RoleDeModele.REDACTEUR_D_ARTICLE,
            defaults={"modele": modele},
        )
        for numero_de_passe in range(1, nombre_de_passes + 1):
            debut = time.time()
            print(f"  {nom} — passe {numero_de_passe}/{nombre_de_passes} …",
                  flush=True)

            # UNE PASSE ECARTEE EST REESSAYEE UNE FOIS. Un 429 est
            # transitoire ; perdre une repetition fausserait justement
            # la mesure du bruit qu'on vient chercher.
            # / A rate limit is transient; losing a repetition would
            #   distort the very noise we came to measure.
            problemes = ["premier essai"]
            for essai in (1, 2):
                if not problemes:
                    break
                if essai == 2:
                    print("    (nouvel essai)", flush=True)
                    time.sleep(30)
                jobs = produire_les_wikis(carnet, wikis, taille)
                from django.core.management import call_command
                call_command("produire_les_syntheses_etalons", forcer=True,
                             verbosity=0)
                jobs += list(
                    ExtractionJob.objects.exclude(
                        raw_result__contains={"est_verification": True},
                    ).order_by("-pk").values_list("pk", flat=True)[:2]
                )
                _attendre_les_jobs(jobs)
                problemes = controler_la_passe(modele.model_choice)

            if problemes:
                print(f"    ⚠️  PASSE ÉCARTÉE : {problemes}")
                continue

            call_command("verifier_les_citations_etalons", forcer=True,
                         verbosity=0)
            _attendre_les_jobs(list(
                ExtractionJob.objects.filter(
                    raw_result__contains={"est_verification": True},
                ).order_by("-pk").values_list("pk", flat=True)[:8]
            ))

            articles = mesurer_les_articles_de_la_passe()
            resultats[nom].append(articles)
            total = Counter()
            for article in articles:
                total.update(article["etats"])
            verifiees, faibles = total["verifie"], total["faible"]
            print(f"    {sum(total.values()):4} citations · "
                  f"{verifiees:3} vérifiées · "
                  f"{100 * verifiees / max(verifiees + faibles, 1):3.0f}% · "
                  f"{time.time() - debut:.0f} s", flush=True)

            chemin = os.path.join(
                os.path.dirname(__file__), "passes_repetees.json",
            )
            json.dump(resultats, open(chemin, "w"), indent=1,
                      ensure_ascii=False)

    print(f"\nÉcrit : passes_repetees.json")


if __name__ == "__main__":
    main()
