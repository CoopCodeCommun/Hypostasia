"""
Banc d'essai MANUEL : la chaine d'Hypostasia de bout en bout, sur un
meme texte, par plusieurs modeles et plusieurs passes.
/ MANUAL benchmark: the whole Hypostasia chain on one text, several
models, several passes.

LOCALISATION : benchmarks/chaine_complete/comparer_la_chaine.py

CE N'EST PAS UN TEST. C'est un script `__main__` qui appelle de vrais
modeles — donc FACTURE — et le dossier `benchmarks/` n'est pas une app
Django : `manage.py test` ne le collecte pas. Meme precedent que
`benchmarks/extraction_format/` et `benchmarks/juge_de_verification/`.

CE QU'IL N'ECRIT PAS, ET CE QU'IL ECRIT. Aucun `ExtractionJob`, aucune
`ExtractedEntity`, aucun `SourceLink`, aucun verdict : lancer les vraies
taches multiplierait les extractions du carnet etalon et deplacerait le
perimetre des articles, donc l'etalon des juges avec.

La SEULE ecriture est la creation des lignes `AIModel` manquantes, en
`is_active=False`. **Les lignes existantes ne sont jamais modifiees** —
en particulier leur temperature, qui est posee EN MEMOIRE (voir
`modele_de`). Une premiere version la sauvait, et reglait ainsi la
production a la temperature du banc.
/ The only write is creating missing (inactive) AIModel rows; existing
rows are never modified.

LES TROIS ETAGES, ET CE QUI LES RELIE :

  1. EXTRAIRE  — le texte source part a LangExtract avec le prompt et
     les exemples de l'analyseur de PRODUCTION. On mesure ce que chaque
     modele trouve, et ce qu'il retrouve d'une passe a l'autre.
  2. REDIGER   — les extractions deviennent un article, avec le prompt
     de production, ses marqueurs `[[ext:N]]` et sa ligne de controle
     `CITATIONS_USED`.
  3. VERIFIER  — chaque paire (affirmation, source) passe au juge, avec
     le prompt de production et son jeton imprevisible.

PLUSIEURS PASSES, PARCE QUE LA VARIANCE EST LE SUJET. Un seul appel par
modele donnerait un tableau qui a l'air net et qui ne l'est pas : mesure
du 17 aout, le juge de reference ne retrouve que 77 % de ses propres
verdicts d'une passe a l'autre.

Lancer depuis l'hote :

    docker exec -w /app hypostasia_web python \\
        benchmarks/chaine_complete/comparer_la_chaine.py

Options : `--passes N` (defaut 3), `--sortie chemin.json`.
"""

import json
import os
import sys
import time
import uuid

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."),
))
django.setup()

from core.llm_providers import appeler_llm  # noqa: E402
from core.models import AIModel, ElementDocument, Page  # noqa: E402
from core.services.verification import (  # noqa: E402
    _construire_le_prompt_du_juge, _scores_de_la_reponse,
    seuil_de_verification,
)
from hypostasis_extractor.models import (  # noqa: E402
    AnalyseurSyntaxique, ExtractedEntity,
)

# La note choisie : une TRANSCRIPTION DE DEBAT a deux voix. C'est l'objet
# meme du produit — un verbatim de deliberation — et elle est assez
# courte pour etre montree en entier dans le rapport.
# / A two-voice debate transcript: the product's very purpose, and short
# enough to be shown in full.
PAGE_DE_L_ECHANTILLON = 3

# Les elements montres au modele d'extraction. Bornes choisies pour
# tomber sur un echange complet, pas au milieu d'une phrase.
# / A complete exchange, not a sentence cut in half.
PREMIER_ELEMENT = 0
DERNIER_ELEMENT = 6

NOMBRE_DE_PASSES_PAR_DEFAUT = 3

# Les modeles compares. `peut_extraire` dit si LangExtract sait le
# piloter. Depuis le 17 aout, TOUS le sont : `resolve_model_params`
# passe un `ModelConfig` qui designe le provider par son NOM et
# court-circuite la table d'expressions regulieres de LangExtract — sans
# laquelle `mistral-small-latest` partait vers un Ollama local.
# / All can now be driven: resolve_model_params passes a ModelConfig
# naming the provider, bypassing LangExtract's regex table.
#
# `temperature` : 0 pour comparer a armes egales, mais les modeles de
# RAISONNEMENT d'OpenAI la refusent — « 400 : Unsupported value:
# 'temperature' does not support 0.0 with this model. Only the default
# (1) value is supported. » Pour eux, `None` : on ne transmet rien.
# / OpenAI's reasoning models reject any temperature but their own.
MODELES_COMPARES = [
    {"choix": "gemini-2.5-flash", "peut_extraire": True, "temperature": 0.0},
    {"choix": "gemini-3.1-flash-lite", "peut_extraire": True,
     "temperature": 0.0},
    {"choix": "gpt-5-mini", "peut_extraire": True, "temperature": None},
    {"choix": "gpt-5-nano", "peut_extraire": True, "temperature": None},
    {"choix": "mistral-small-latest", "peut_extraire": True,
     "temperature": 0.0,
     "base_url": "https://api.mistral.ai/v1",
     "variable_de_cle_api": "MISTRAL_API_KEY"},
]


def modele_de(definition):
    """
    Une ligne AIModel utilisable par le banc, SANS TOUCHER A LA BASE.
    / An AIModel usable by the bench, WITHOUT touching the database.

    LOCALISATION : benchmarks/chaine_complete/comparer_la_chaine.py

    LA TEMPERATURE EST POSEE EN MEMOIRE, JAMAIS ENREGISTREE, et c'est
    une correction de relecture adverse. Une premiere version faisait un
    `get_or_create` puis sauvait la temperature : le lookup
    `model_choice="gemini-2.5-flash"` retrouve LA LIGNE DE PRODUCTION —
    celle que `Configuration.ai_model` pointe et sur laquelle le
    redacteur se replie — et un simple lancement du banc faisait passer
    toute la redaction de production a la temperature du banc, sans un
    log, en ecrasant un reglage pose a la main.
    / A previous version saved the temperature onto the PRODUCTION row:
    one bench run silently re-tuned every production article.

    Les lignes qui n'existent pas sont creees NON ACTIVES — elles ne
    doivent pas devenir selectionnables comme modele d'extraction dans
    l'ecran de configuration IA.
    / Missing rows are created inactive.
    """
    from core.models import AIModelChoices, Provider

    if definition.get("base_url"):
        modele, _ = AIModel.objects.get_or_create(
            model_choice=definition["choix"],
            provider=Provider.COMPATIBLE_OPENAI,
            base_url=definition["base_url"],
            defaults={
                "name": definition["choix"],
                "variable_de_cle_api": definition["variable_de_cle_api"],
                "is_active": False,
            },
        )
    else:
        modele, _ = AIModel.objects.get_or_create(
            model_choice=definition["choix"],
            defaults={
                "name": dict(AIModelChoices.choices).get(
                    definition["choix"], definition["choix"],
                ),
                "is_active": False,
            },
        )
    # EN MEMOIRE SEULEMENT : pas de `save`. Les chemins d'appel lisent
    # `modele_ia.temperature` sur l'instance qu'on leur passe.
    # / In memory only: the call paths read the attribute we pass them.
    modele.temperature = definition["temperature"]
    return modele


# ---------------------------------------------------------------------------
# Étage 1 — extraire
# ---------------------------------------------------------------------------


def texte_de_l_echantillon():
    """Les elements choisis, colles comme le chunker de production le fait."""
    elements = list(
        ElementDocument.objects.filter(page_id=PAGE_DE_L_ECHANTILLON)
        .order_by("ordre")[PREMIER_ELEMENT:DERNIER_ELEMENT]
    )
    return "\n".join(element.texte for element in elements), elements


def extraire(modele_ia, texte):
    """
    Une extraction LangExtract, avec le prompt et les exemples de
    PRODUCTION, sans rien enregistrer.
    / One LangExtract run with the production prompt, persisting nothing.
    """
    import langextract as lx
    from hypostasis_extractor.services import (
        _construire_exemples_langextract, resolve_model_params,
    )
    from hypostasis_extractor.services.analyse_par_element import (
        MARGE_POUR_NEUTRALISER_LE_CHUNKER,
    )

    analyseur = AnalyseurSyntaxique.objects.filter(
        is_active=True, type_analyseur="analyser",
    ).first()
    prompt = "\n".join(
        piece.content
        for piece in analyseur.prompt_pieces.order_by("order")
    ) if hasattr(analyseur, "prompt_pieces") else None
    if not prompt:
        from hypostasis_extractor.models import PromptPiece
        prompt = "\n".join(
            piece.content
            for piece in PromptPiece.objects.filter(
                analyseur=analyseur,
            ).order_by("order")
        )

    resultat = lx.extract(
        text_or_documents=texte,
        prompt_description=prompt,
        examples=_construire_exemples_langextract(analyseur),
        max_char_buffer=len(texte) + MARGE_POUR_NEUTRALISER_LE_CHUNKER,
        fetch_urls=False,
        resolver_params={"suppress_parse_errors": True},
        **resolve_model_params(modele_ia),
    )
    return [
        {
            "classe": extraction.extraction_class,
            "texte": extraction.extraction_text,
            "attributs": dict(extraction.attributes or {}),
        }
        for extraction in (resultat.extractions or [])
    ]


# ---------------------------------------------------------------------------
# Étage 2 — rédiger
# ---------------------------------------------------------------------------


def prompt_de_redaction():
    """Le prompt de production, sur les extractions de la note choisie."""
    from front.tasks import (
        _blocs_d_extractions_par_note, _consignes_de_forme_d_article,
        _prompt_systeme_de_synthese,
    )

    note = Page.objects.get(pk=PAGE_DE_L_ECHANTILLON)
    blocs, identifiants = _blocs_d_extractions_par_note([note])
    return (
        _prompt_systeme_de_synthese() + "\n\n"
        "=== SUJET DE L'ARTICLE ===\n"
        "Ce que ce débat dit du rôle de l'intelligence artificielle\n\n"
        "=== EXTRACTIONS DU PÉRIMÈTRE ===\n" + blocs + "\n\n"
        "=== CONSIGNE ===\n"
        "Rédige un article de wiki sur ce sujet, nourri UNIQUEMENT des "
        "extractions ci-dessus. Le sujet oriente la rédaction ; il ne "
        "t'autorise pas à inventer.\n\n"
        + _consignes_de_forme_d_article()
    ), identifiants


def rediger(modele_ia, prompt, identifiants_du_perimetre):
    """Un article, et ce qu'on peut en mesurer sans rien enregistrer."""
    import re

    from front.tasks import _detacher_la_ligne_citations_used

    reponse = appeler_llm(modele_ia, prompt)
    try:
        texte, citations_annoncees = _detacher_la_ligne_citations_used(
            (reponse or "").strip(),
        )
        trailer_present = True
    except Exception:
        texte, citations_annoncees, trailer_present = reponse, [], False

    marqueurs = [int(n) for n in re.findall(r"\[\[ext:(\d+)\]\]", texte or "")]
    hallucines = [n for n in set(marqueurs)
                  if n not in set(identifiants_du_perimetre)]
    return {
        "caracteres": len(texte or ""),
        "sections": len(re.findall(r"^## ", texte or "", re.MULTILINE)),
        "marqueurs": len(marqueurs),
        "sources_distinctes": len(set(marqueurs)),
        "marqueurs_hallucines": len(hallucines),
        "trailer_present": trailer_present,
        "citations_annoncees": len(citations_annoncees or []),
        "texte": texte,
    }


# ---------------------------------------------------------------------------
# Étage 3 — vérifier
# ---------------------------------------------------------------------------


def paires_a_juger():
    """
    Les paires gelees d'UNE affirmation, choisie pour son multi-sources :
    c'est la que « juger par paire » se voit.
    / The frozen pairs of ONE multi-source claim.
    """
    chemin = os.path.join(
        os.path.dirname(__file__), "..", "juge_de_verification",
        "etalon-du-juge.json",
    )
    with open(chemin, encoding="utf-8") as fichier:
        etalon = json.load(fichier)

    par_affirmation = {}
    for paire in etalon["paires"]:
        par_affirmation.setdefault(paire["affirmation"], []).append(paire)
    # La plus fournie en sources : le cas ou la question posee au juge
    # est la plus discutable. / The most multi-sourced claim.
    return max(par_affirmation.values(), key=len)


def juger(modele_ia, paires):
    """Un lot de paires, avec le prompt et le jeton de production."""
    nonce = uuid.uuid4().hex[:12]
    paires_du_prompt = [
        (numero, paire["affirmation"], paire["texte_source"])
        for numero, paire in enumerate(paires, start=1)
    ]
    reponse = appeler_llm(
        modele_ia, _construire_le_prompt_du_juge(paires_du_prompt, nonce),
    )
    # LE JUGE REND UN DEGRE (addendum du 18 aout 2026). Ce banc compare
    # des juges entre eux : il lui faut un verdict comparable, donc une
    # conversion par le seuil courant. La conversion est nommee dans le
    # rapport, elle n'est jamais implicite.
    # / The judge returns a degree; converted by the current threshold so
    # judges stay comparable, and the conversion is named in the report.
    scores = _scores_de_la_reponse(reponse, len(paires))
    seuil = seuil_de_verification()

    def _verdict(numero):
        score = scores.get(numero) if scores else None
        if score is None:
            return None
        return "soutient" if score >= seuil else "ne_soutient_pas"

    return {
        str(paire["lien_id"]): _verdict(numero)
        for numero, paire in enumerate(paires, start=1)
    }


# ---------------------------------------------------------------------------


def main():
    nombre_de_passes = NOMBRE_DE_PASSES_PAR_DEFAUT
    if "--passes" in sys.argv:
        nombre_de_passes = int(sys.argv[sys.argv.index("--passes") + 1])
    chemin_de_sortie = os.path.join(
        os.path.dirname(__file__), "resultats.json",
    )
    if "--sortie" in sys.argv:
        chemin_de_sortie = sys.argv[sys.argv.index("--sortie") + 1]

    # ON N'ECRASE PAS `resultats.json` SANS LE VOULOIR.
    #
    # Ce fichier n'est pas seulement la sortie de ce banc : c'est aussi
    # l'ENTREE de `comparer_shieldstral.py`, qui lit ses quinze paires et
    # les compare a des verdicts relus a la main, INDEXES PAR POSITION
    # (1 a 15). Le reecrire sur une autre base — d'autres extractions,
    # un autre modele — detruit cet alignement en silence : l'AUC de
    # 0,923 publiee le 18 aout deviendrait non rejouable, et rien ne le
    # dirait.
    #
    # Ce banc lit d'ailleurs la BASE VIVANTE (page, elements, analyseur,
    # extractions du perimetre) : ses trois etages ne se rejouent pas a
    # l'identique apres un `docker compose down -v`. Seul l'etage
    # « juger » lit un fichier gele.
    # / This file is also the INPUT of comparer_shieldstral.py, whose
    # hand-read verdicts are indexed by position. Overwriting it on a
    # rebuilt database silently destroys that alignment.
    if os.path.exists(chemin_de_sortie) and "--forcer" not in sys.argv:
        raise SystemExit(
            f"\n{chemin_de_sortie} existe déjà.\n"
            f"  Il sert aussi d'ENTRÉE à comparer_shieldstral.py, dont "
            f"les quinze verdicts relus à la main sont indexés par "
            f"POSITION.\n"
            f"  L'écraser sur une base reconstruite détruirait cet "
            f"alignement sans erreur.\n\n"
            f"  --sortie AUTRE_FICHIER.json  pour écrire ailleurs\n"
            f"  --forcer                     pour écraser en connaissance "
            f"de cause\n",
        )

    texte, elements = texte_de_l_echantillon()
    prompt_article, identifiants = prompt_de_redaction()
    paires = paires_a_juger()

    print(f"\nÉchantillon : page {PAGE_DE_L_ECHANTILLON}, "
          f"éléments {PREMIER_ELEMENT}–{DERNIER_ELEMENT} "
          f"({len(texte)} caractères)")
    print(f"Rédaction   : {len(identifiants)} extractions au périmètre, "
          f"prompt de {len(prompt_article)} caractères")
    print(f"Vérification: {len(paires)} paires d'une même affirmation")
    print(f"Passes      : {nombre_de_passes}")
    print("\nAPPELS FACTURÉS. Rien ne sera écrit en base.\n")

    resultats = {
        "echantillon": {
            "page_id": PAGE_DE_L_ECHANTILLON,
            "titre": Page.objects.get(pk=PAGE_DE_L_ECHANTILLON).title,
            "texte": texte,
            "elements": [
                {"ordre": e.ordre, "label": e.label, "texte": e.texte,
                 "provenance": e.provenance}
                for e in elements
            ],
        },
        "perimetre_de_redaction": {
            "identifiants": sorted(identifiants),
            "extractions": [
                {"id": extraction.pk,
                 "classe": extraction.extraction_class,
                 "texte": extraction.extraction_text}
                for extraction in ExtractedEntity.objects.filter(
                    pk__in=identifiants,
                ).order_by("pk")
            ],
        },
        "affirmation_jugee": {
            "texte": paires[0]["affirmation"],
            "paires": [
                {"lien_id": p["lien_id"], "source": p["texte_source"],
                 "reference": p["reponse_de_reference"]}
                for p in paires
            ],
        },
        "passes": nombre_de_passes,
        "modeles": [],
    }

    for definition in MODELES_COMPARES:
        modele_ia = modele_de(definition)
        mesure = {
            "choix": definition["choix"],
            "tarif": modele_ia.cout_par_million_tokens(),
            "peut_extraire": definition["peut_extraire"],
            "extractions": [], "articles": [], "verdicts": [],
        }
        print(f"===== {definition['choix']} =====")

        for numero in range(1, nombre_de_passes + 1):
            if definition["peut_extraire"]:
                debut = time.time()
                try:
                    trouvees = extraire(modele_ia, texte)
                    mesure["extractions"].append({
                        "passe": numero, "duree": round(time.time() - debut, 1),
                        "trouvees": trouvees,
                    })
                    print(f"  extraction passe {numero} : "
                          f"{len(trouvees)} extractions "
                          f"({time.time() - debut:.0f} s)")
                except Exception as erreur:
                    mesure["extractions"].append({
                        "passe": numero, "erreur": str(erreur)[:300],
                    })
                    print(f"  extraction passe {numero} : ÉCHEC — "
                          f"{str(erreur)[:120]}")

            debut = time.time()
            try:
                article = rediger(modele_ia, prompt_article, identifiants)
                article["passe"] = numero
                article["duree"] = round(time.time() - debut, 1)
                mesure["articles"].append(article)
                print(f"  rédaction  passe {numero} : "
                      f"{article['caracteres']} car., "
                      f"{article['sources_distinctes']} sources, "
                      f"{article['marqueurs_hallucines']} hallucinés "
                      f"({article['duree']:.0f} s)")
            except Exception as erreur:
                mesure["articles"].append({
                    "passe": numero, "erreur": str(erreur)[:300],
                })
                print(f"  rédaction  passe {numero} : ÉCHEC — "
                      f"{str(erreur)[:120]}")

            debut = time.time()
            try:
                rendus = juger(modele_ia, paires)
                mesure["verdicts"].append({
                    "passe": numero, "duree": round(time.time() - debut, 1),
                    "rendus": rendus,
                })
                soutient = sum(1 for v in rendus.values() if v == "soutient")
                print(f"  jugement   passe {numero} : "
                      f"{soutient}/{len(paires)} « soutient »")
            except Exception as erreur:
                mesure["verdicts"].append({
                    "passe": numero, "erreur": str(erreur)[:300],
                })
                print(f"  jugement   passe {numero} : ÉCHEC — "
                      f"{str(erreur)[:120]}")

        resultats["modeles"].append(mesure)

    with open(chemin_de_sortie, "w", encoding="utf-8") as fichier:
        json.dump(resultats, fichier, ensure_ascii=False, indent=2)
    print(f"\nRésultats dans {chemin_de_sortie}")


if __name__ == "__main__":
    main()
