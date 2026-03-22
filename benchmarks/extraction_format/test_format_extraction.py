"""
Script de test : comparer 2 approches de format d'extraction x 2 modeles LLM.
/ Test script: compare 2 extraction format approaches x 2 LLM models.

LOCALISATION : tmp/test_format_extraction.py

Approche A : extraction_class = "hypostase" (classe unique, hypostase specifique dans attributes)
Approche B : extraction_class = nom de l'hypostase (classe variable : "théorie", "problème"...)

Modeles : Gemini 2.5 Flash + GPT-4o Mini

Lancer depuis le conteneur Docker :
  docker exec hypostasia_web uv run python tmp/test_format_extraction.py
"""

import os
import sys
import time
import json
import django

# Setup Django / Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
sys.path.insert(0, "/app")
django.setup()

import langextract as lx
from langextract import prompting as prompting_lx
from langextract import resolver as resolver_lx
from langextract import factory as factory_lx
from langextract.core import data as data_lx
from langextract.core import format_handler as fh_lx

from core.models import Page


# ---------------------------------------------------------------------------
# Configuration du test
# / Test configuration
# ---------------------------------------------------------------------------

PAGE_ID = 15  # 19726 chars, ~13 chunks
TAILLE_MAX_CHUNK = 1500
BATCH_LENGTH = 1  # Sequentiel pour isoler les erreurs par chunk / Sequential to isolate errors per chunk
MAX_OUTPUT_TOKENS = 8192

# Prompt commun (pieces 0 a 4 — identiques pour les deux approches)
# / Common prompt (pieces 0-4 — identical for both approaches)
PROMPT_COMMUN = """Tu es Hypostasia, un expert mondial en analyse syntaxique et en logique argumentative.
Ta mission est de déconstruire le texte fourni pour en extraire l'ossature argumentative via les hypostases (définitions plus bas).
Tu agis avec une neutralité absolue et une précision chirurgicale.

# Définitions des 30 hypostases

- classification, aporie, approximation, paradoxe, formalisme
- événement, variation, dimension, mode, croyance
- invariant, valeur, structure, axiome, conjecture
- paradigme, objet, principe, domaine, loi
- phénomène, variable, variance, indice, donnée
- méthode, définition, hypothèse, problème, théorie

ANALYSE MAINTENANT LE TEXTE SUIVANT.
Instructions :
1. Identifie 5 à 15 arguments pertinents.
2. Pour chaque argument, extrais la citation EXACTE. Ne pas reformuler.
3. Synthétise l'idée en une phrase (résumé).
4. Associe 1 à 3 hypostases parmi les 30 définies.
5. Ignore le bruit, menus, pubs, copyright.
"""

# Piece 5 specifique a chaque approche
# / Piece 5 specific to each approach
PIECE_5_APPROCHE_A = """RÈGLES DE FORMAT STRICTES — chaque extraction DOIT suivre ce schéma :

{
  "hypostase": "citation exacte du texte source",
  "hypostase_attributes": {
    "resume": "synthèse en une phrase",
    "hypostases": "hypothèse, théorie",
    "mots_cles": "mot1, mot2"
  }
}

- La clé est TOUJOURS "hypostase"
- "hypostases" dans les attributs : 1 à 3 parmi les 30. Ne JAMAIS lister les 30.
- Ne JAMAIS répéter la même extraction ni boucler.
"""

PIECE_5_APPROCHE_B = """RÈGLES DE FORMAT STRICTES — chaque extraction DOIT suivre ce schéma :

{
  "théorie": "citation exacte du texte source",
  "théorie_attributes": {
    "resume": "synthèse en une phrase",
    "hypostases": "théorie, conjecture",
    "mots_cles": "mot1, mot2"
  }
}

- La clé est le NOM de l'hypostase principale (théorie, problème, hypothèse...)
- Chaque extraction peut avoir une clé différente selon l'hypostase identifiée.
- "hypostases" dans les attributs : 1 à 3 parmi les 30. Ne JAMAIS lister les 30.
- Ne JAMAIS répéter la même extraction ni boucler.
"""

# Few-shot exemples pour chaque approche
# / Few-shot examples for each approach
TEXTE_EXEMPLE = (
    "L'intelligence artificielle est la révolution la plus importante "
    "depuis l'invention de l'écriture. On nous présente l'IA comme une "
    "fatalité historique, alors qu'il s'agit d'un choix politique."
)

EXEMPLES_APPROCHE_A = [
    lx.data.ExampleData(
        text=TEXTE_EXEMPLE,
        extractions=[
            lx.data.Extraction(
                extraction_class="hypostase",
                extraction_text="L'intelligence artificielle est la révolution la plus importante depuis l'invention de l'écriture.",
                attributes={"resume": "L'IA comparée à l'écriture.", "hypostases": "théorie, conjecture", "mots_cles": "IA, révolution"},
            ),
            lx.data.Extraction(
                extraction_class="hypostase",
                extraction_text="On nous présente l'IA comme une fatalité historique, alors qu'il s'agit d'un choix politique.",
                attributes={"resume": "L'IA est un choix politique.", "hypostases": "problème, définition", "mots_cles": "choix, politique"},
            ),
        ],
    ),
]

EXEMPLES_APPROCHE_B = [
    lx.data.ExampleData(
        text=TEXTE_EXEMPLE,
        extractions=[
            lx.data.Extraction(
                extraction_class="théorie",
                extraction_text="L'intelligence artificielle est la révolution la plus importante depuis l'invention de l'écriture.",
                attributes={"resume": "L'IA comparée à l'écriture.", "hypostases": "théorie, conjecture", "mots_cles": "IA, révolution"},
            ),
            lx.data.Extraction(
                extraction_class="problème",
                extraction_text="On nous présente l'IA comme une fatalité historique, alors qu'il s'agit d'un choix politique.",
                attributes={"resume": "L'IA est un choix politique.", "hypostases": "problème, définition", "mots_cles": "choix, politique"},
            ),
        ],
    ),
]

# Charger les parametres des modeles depuis la DB (inclut les API keys)
# / Load model params from DB (includes API keys)
from core.models import AIModel
from hypostasis_extractor.services import resolve_model_params

MODELES = []
for ai_model in AIModel.objects.filter(is_active=True):
    parametres = resolve_model_params(ai_model)
    model_id = parametres.pop("model_id")
    MODELES.append({
        "nom": ai_model.get_display_name(),
        "model_id": model_id,
        "provider_kwargs": parametres,
    })


# ---------------------------------------------------------------------------
# Fonction de test
# / Test function
# ---------------------------------------------------------------------------

def lancer_test(nom_test, prompt_description, exemples, modele_config, texte_source):
    """
    Lance une extraction LangExtract complete et mesure les resultats.
    / Run a complete LangExtract extraction and measure results.
    """
    print(f"\n{'='*70}")
    print(f"  TEST : {nom_test}")
    print(f"  Modele : {modele_config['nom']}")
    print(f"  Texte : {len(texte_source)} chars (~{len(texte_source)//TAILLE_MAX_CHUNK} chunks)")
    print(f"{'='*70}")

    # 1. Construire le prompt template avec les few-shot
    # / 1. Build prompt template with few-shot examples
    modele_prompt = prompting_lx.PromptTemplateStructured(description=prompt_description)
    modele_prompt.examples.extend(exemples)

    # 2. Creer le modele LLM
    # / 2. Create LLM model
    kwargs_modele = {
        "format_type": data_lx.FormatType.JSON,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }
    kwargs_modele.update(modele_config["provider_kwargs"])
    config_modele = factory_lx.ModelConfig(
        model_id=modele_config["model_id"],
        provider_kwargs=kwargs_modele,
    )
    modele_llm = factory_lx.create_model(config=config_modele, examples=modele_prompt.examples, use_schema_constraints=True)

    # 3. FormatHandler et Resolver
    # / 3. FormatHandler and Resolver
    handler_format, _ = fh_lx.FormatHandler.from_resolver_params(
        resolver_params={},
        base_format_type=data_lx.FormatType.JSON,
        base_use_fences=modele_llm.requires_fence_output,
        base_attribute_suffix=data_lx.ATTRIBUTE_SUFFIX,
        base_use_wrapper=True,
        base_wrapper_key=data_lx.EXTRACTIONS_KEY,
    )
    resolveur = resolver_lx.Resolver(format_handler=handler_format)

    # 4. Creer l'annotateur standard (pas notre override, pour tester LangExtract pur)
    # / 4. Create standard annotator (not our override, to test pure LangExtract)
    from langextract import annotation as annotation_lx
    annotateur = annotation_lx.Annotator(
        language_model=modele_llm,
        prompt_template=modele_prompt,
        format_handler=handler_format,
    )

    # 5. Lancer l'extraction
    # / 5. Run extraction
    debut = time.time()
    try:
        resultat = annotateur.annotate_text(
            text=texte_source,
            resolver=resolveur,
            max_char_buffer=TAILLE_MAX_CHUNK,
            batch_length=BATCH_LENGTH,
            show_progress=False,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            suppress_parse_errors=True,
        )

        duree = time.time() - debut
        nombre_extractions = len(resultat.extractions or [])

        # Afficher les resultats / Display results
        print(f"\n  RESULTAT : {nombre_extractions} extractions en {duree:.1f}s")
        print(f"  ---")

        # Lister les classes trouvees / List found classes
        classes_trouvees = {}
        for ext in (resultat.extractions or []):
            classe = ext.extraction_class
            classes_trouvees[classe] = classes_trouvees.get(classe, 0) + 1
            print(f"    [{classe}] {ext.extraction_text[:70]}...")
            if ext.attributes:
                hypostases_attr = ext.attributes.get("hypostases", "—")
                print(f"      hypostases: {hypostases_attr}")

        print(f"\n  CLASSES : {dict(classes_trouvees)}")
        print(f"  TOTAL : {nombre_extractions} extractions, {duree:.1f}s")

        return {
            "nom": nom_test,
            "modele": modele_config["nom"],
            "extractions": nombre_extractions,
            "duree": duree,
            "classes": classes_trouvees,
            "erreur": None,
        }

    except Exception as erreur:
        duree = time.time() - debut
        print(f"\n  ERREUR : {erreur}")
        print(f"  Duree avant erreur : {duree:.1f}s")
        return {
            "nom": nom_test,
            "modele": modele_config["nom"],
            "extractions": 0,
            "duree": duree,
            "classes": {},
            "erreur": str(erreur),
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Charger le texte source depuis la DB
    # / Load source text from DB
    page = Page.objects.get(pk=PAGE_ID)
    texte_source = page.text_readability
    print(f"Texte source : page {PAGE_ID} — {page.title}")
    print(f"Longueur : {len(texte_source)} chars (~{len(texte_source)//TAILLE_MAX_CHUNK} chunks)")

    resultats = []

    # 4 tests : 2 approches x 2 modeles
    # / 4 tests: 2 approaches x 2 models
    for modele_config in MODELES:
        # Approche A : classe unique "hypostase"
        # / Approach A: single class "hypostase"
        prompt_a = PROMPT_COMMUN + PIECE_5_APPROCHE_A
        resultats.append(lancer_test(
            nom_test="Approche A (classe unique 'hypostase')",
            prompt_description=prompt_a,
            exemples=EXEMPLES_APPROCHE_A,
            modele_config=modele_config,
            texte_source=texte_source,
        ))

        # Approche B : classe specifique (théorie, problème...)
        # / Approach B: specific class (théorie, problème...)
        prompt_b = PROMPT_COMMUN + PIECE_5_APPROCHE_B
        resultats.append(lancer_test(
            nom_test="Approche B (classe spécifique)",
            prompt_description=prompt_b,
            exemples=EXEMPLES_APPROCHE_B,
            modele_config=modele_config,
            texte_source=texte_source,
        ))

    # Resume final / Final summary
    print(f"\n\n{'='*70}")
    print(f"  RESUME COMPARATIF")
    print(f"{'='*70}")
    print(f"{'Test':<45} {'Modele':<20} {'Extr':>5} {'Temps':>7} {'Classes':>10}")
    print(f"{'-'*45} {'-'*20} {'-'*5} {'-'*7} {'-'*10}")
    for r in resultats:
        nb_classes = len(r["classes"])
        erreur_str = " ERREUR!" if r["erreur"] else ""
        print(f"{r['nom']:<45} {r['modele']:<20} {r['extractions']:>5} {r['duree']:>6.1f}s {nb_classes:>10}{erreur_str}")

    print(f"\nDetail des classes par test :")
    for r in resultats:
        print(f"  {r['nom']} / {r['modele']} : {r['classes']}")
