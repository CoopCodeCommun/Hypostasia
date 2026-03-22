"""
Script de test : comparer 2 approches de format d'extraction x N modeles LLM.
/ Test script: compare 2 extraction format approaches x N LLM models.

LOCALISATION : benchmarks/extraction_format/test_format_extraction.py

Approche A : extraction_class = "hypostase" (classe unique, hypostase specifique dans attributes)
Approche B : extraction_class = nom de l'hypostase (classe variable : "théorie", "problème"...)

Les few-shot couvrent les 30 hypostases pour ne pas biaiser les resultats.
/ Few-shots cover all 30 hypostases to avoid biasing results.

Lancer depuis le conteneur Docker :
  docker exec hypostasia_web uv run python benchmarks/extraction_format/test_format_extraction.py
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
from langextract import annotation as annotation_lx
from langextract.core import data as data_lx
from langextract.core import format_handler as fh_lx

from core.models import Page, AIModel
from hypostasis_extractor.services import resolve_model_params

# Import des prompts et few-shot depuis les modules du benchmark
# / Import prompts and few-shots from benchmark modules
sys.path.insert(0, "/app/benchmarks/extraction_format")
from prompts import construire_prompt
from fewshot_30_hypostases import EXEMPLE_30_HYPOSTASES, EXTRACTIONS_30, TEXTE_FEWSHOT_30


# ---------------------------------------------------------------------------
# Configuration du test / Test configuration
# ---------------------------------------------------------------------------

PAGE_ID = 15  # "La Ronde des Intelligences" — 19726 chars, ~13 chunks
TAILLE_MAX_CHUNK = 1500
BATCH_LENGTH = 1  # Sequentiel pour isoler les erreurs / Sequential to isolate errors
MAX_OUTPUT_TOKENS = 8192


# ---------------------------------------------------------------------------
# Construire les few-shot pour chaque approche
# Les 30 extractions sont les memes, seul extraction_class change.
# / Build few-shots for each approach.
# / Same 30 extractions, only extraction_class differs.
# ---------------------------------------------------------------------------

def construire_fewshot_approche_a():
    """
    Approche A : toutes les extractions ont extraction_class = "hypostase".
    L'hypostase specifique est dans attributes["hypostases"].
    / Approach A: all extractions have extraction_class = "hypostase".
    / Specific hypostase is in attributes["hypostases"].
    """
    extractions_approche_a = []
    for ext in EXTRACTIONS_30:
        extractions_approche_a.append(
            lx.data.Extraction(
                extraction_class="hypostase",
                extraction_text=ext.extraction_text,
                attributes=ext.attributes,
            )
        )
    return [lx.data.ExampleData(text=TEXTE_FEWSHOT_30, extractions=extractions_approche_a)]


def construire_fewshot_approche_b():
    """
    Approche B : extraction_class = nom de l'hypostase specifique.
    Les 30 classes differentes sont montrees dans les few-shot.
    / Approach B: extraction_class = specific hypostase name.
    / All 30 different classes are shown in the few-shots.
    """
    return [EXEMPLE_30_HYPOSTASES]


# ---------------------------------------------------------------------------
# Charger les modeles depuis la DB / Load models from DB
# ---------------------------------------------------------------------------

def charger_modeles():
    """
    Charge les parametres des modeles actifs depuis la DB.
    / Load active model params from DB.
    """
    modeles = []
    for ai_model in AIModel.objects.filter(is_active=True):
        parametres = resolve_model_params(ai_model)
        model_id = parametres.pop("model_id")
        modeles.append({
            "nom": ai_model.get_display_name(),
            "model_id": model_id,
            "provider_kwargs": parametres,
        })
    return modeles


# ---------------------------------------------------------------------------
# Fonction de test / Test function
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
    print(f"  Few-shot : {sum(len(ex.extractions) for ex in exemples)} extractions")
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
    modele_llm = factory_lx.create_model(
        config=config_modele,
        examples=modele_prompt.examples,
        use_schema_constraints=True,
    )

    # 3. FormatHandler et Resolver (natif LangExtract, pas notre override)
    # / 3. FormatHandler and Resolver (native LangExtract, not our override)
    handler_format, _ = fh_lx.FormatHandler.from_resolver_params(
        resolver_params={},
        base_format_type=data_lx.FormatType.JSON,
        base_use_fences=modele_llm.requires_fence_output,
        base_attribute_suffix=data_lx.ATTRIBUTE_SUFFIX,
        base_use_wrapper=True,
        base_wrapper_key=data_lx.EXTRACTIONS_KEY,
    )
    resolveur = resolver_lx.Resolver(format_handler=handler_format)

    # 4. Creer l'annotateur natif LangExtract
    # / 4. Create native LangExtract annotator
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

        # Lister les extractions avec leur classe et hypostases
        # Compter separement les classes (extraction_class) et les hypostases (dans attributes)
        # / List extractions with their class and hypostases
        # / Count separately: classes (extraction_class) and hypostases (in attributes)
        classes_trouvees = {}
        hypostases_dans_attributs = {}
        nombre_total_hypostases_attribuees = 0

        for ext in (resultat.extractions or []):
            classe = ext.extraction_class
            classes_trouvees[classe] = classes_trouvees.get(classe, 0) + 1

            # Compter les hypostases dans les attributs
            # / Count hypostases in attributes
            hypostases_attr = ext.attributes.get("hypostases", "") if ext.attributes else ""
            if hypostases_attr and hypostases_attr != "—":
                for hypostase_brute in hypostases_attr.split(","):
                    hypostase_nettoyee = hypostase_brute.strip().lower()
                    if hypostase_nettoyee:
                        hypostases_dans_attributs[hypostase_nettoyee] = (
                            hypostases_dans_attributs.get(hypostase_nettoyee, 0) + 1
                        )
                        nombre_total_hypostases_attribuees += 1

            print(f"    [{classe}] {ext.extraction_text[:70]}...")
            print(f"      hypostases: {hypostases_attr}")

        # Trier par frequence decroissante / Sort by decreasing frequency
        classes_triees = dict(sorted(classes_trouvees.items(), key=lambda x: -x[1]))
        hypostases_triees = dict(sorted(hypostases_dans_attributs.items(), key=lambda x: -x[1]))

        print(f"\n  CLASSES (extraction_class) : {classes_triees}")
        print(f"  HYPOSTASES (dans attributes) : {hypostases_triees}")
        print(f"  TOTAL : {nombre_extractions} extractions, {duree:.1f}s")
        print(f"  RICHESSE : {len(classes_trouvees)} classes distinctes, {len(hypostases_dans_attributs)} hypostases distinctes dans attributs")
        print(f"  COUVERTURE : {len(hypostases_dans_attributs)}/30 hypostases utilisees, {nombre_total_hypostases_attribuees} attributions totales")

        return {
            "nom": nom_test,
            "modele": modele_config["nom"],
            "extractions": nombre_extractions,
            "duree": duree,
            "classes": classes_trouvees,
            "hypostases_attributs": hypostases_dans_attributs,
            "nombre_classes_distinctes": len(classes_trouvees),
            "nombre_hypostases_distinctes": len(hypostases_dans_attributs),
            "couverture_30": len(hypostases_dans_attributs),
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

    modeles = charger_modeles()
    print(f"Modeles : {', '.join(m['nom'] for m in modeles)}")

    # Construire les few-shot / Build few-shots
    fewshot_a = construire_fewshot_approche_a()
    fewshot_b = construire_fewshot_approche_b()
    print(f"Few-shot A : {sum(len(ex.extractions) for ex in fewshot_a)} extractions (classe unique)")
    print(f"Few-shot B : {sum(len(ex.extractions) for ex in fewshot_b)} extractions (30 classes)")

    resultats = []

    # Lancer les tests : 2 approches x N modeles
    # / Run tests: 2 approaches x N models
    for modele_config in modeles:
        # Approche A : classe unique "hypostase"
        # / Approach A: single class "hypostase"
        prompt_a = construire_prompt(approche="A")
        resultats.append(lancer_test(
            nom_test="Approche A (classe unique, 30 few-shot)",
            prompt_description=prompt_a,
            exemples=fewshot_a,
            modele_config=modele_config,
            texte_source=texte_source,
        ))

        # Approche B : classe specifique (théorie, problème...)
        # / Approach B: specific class (théorie, problème...)
        prompt_b = construire_prompt(approche="B")
        resultats.append(lancer_test(
            nom_test="Approche B (classe spécifique, 30 few-shot)",
            prompt_description=prompt_b,
            exemples=fewshot_b,
            modele_config=modele_config,
            texte_source=texte_source,
        ))

    # Resume final / Final summary
    print(f"\n\n{'='*80}")
    print(f"  RESUME COMPARATIF")
    print(f"{'='*80}")
    print(f"{'Test':<50} {'Modele':<20} {'Extr':>5} {'Temps':>7} {'Cl.':>4} {'Hyp.attr':>9} {'Couv/30':>8}")
    print(f"{'-'*50} {'-'*20} {'-'*5} {'-'*7} {'-'*4} {'-'*9} {'-'*8}")
    for r in resultats:
        nb_classes = r.get("nombre_classes_distinctes", len(r["classes"]))
        nb_hyp_attr = r.get("nombre_hypostases_distinctes", 0)
        couverture = r.get("couverture_30", 0)
        erreur_str = " ERREUR!" if r["erreur"] else ""
        print(
            f"{r['nom']:<50} {r['modele']:<20} "
            f"{r['extractions']:>5} {r['duree']:>6.1f}s "
            f"{nb_classes:>4} {nb_hyp_attr:>9} {couverture:>7}/30"
            f"{erreur_str}"
        )

    # Legende / Legend
    print(f"\n  Cl. = classes distinctes dans extraction_class")
    print(f"  Hyp.attr = hypostases distinctes dans attributes['hypostases']")
    print(f"  Couv/30 = couverture des 30 hypostases (dans attributs)")

    print(f"\nDetail des classes (extraction_class) :")
    for r in resultats:
        classes_triees = dict(sorted(r["classes"].items(), key=lambda x: -x[1]))
        print(f"  {r['nom'][:30]}... / {r['modele']} : {classes_triees}")

    print(f"\nDetail des hypostases (dans attributs) :")
    for r in resultats:
        hyp_attr = r.get("hypostases_attributs", {})
        hyp_triees = dict(sorted(hyp_attr.items(), key=lambda x: -x[1]))
        print(f"  {r['nom'][:30]}... / {r['modele']} : {hyp_triees}")
