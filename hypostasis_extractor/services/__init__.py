"""
Services pour l'integration LangExtract.
Wrapper autour de la librairie langextract pour s'integrer avec Hypostasia.
"""

import os
import logging
import langextract as lx
from typing import Dict

from core.models import AIModel, Provider

logger = logging.getLogger(__name__)


def resolve_model_params(ai_model: AIModel) -> Dict:
    """
    Convertit une configuration AIModel en parametres pour LangExtract.
    Supporte Google, OpenAI, Ollama (natif LangExtract) et Mock.
    Anthropic leve une ValueError car non supporte par LangExtract.
    / Converts an AIModel config into LangExtract parameters.
    Supports Google, OpenAI, Ollama (native LangExtract), Mock.
    Anthropic raises ValueError (not supported by LangExtract).

    LOCALISATION : hypostasis_extractor/services/__init__.py
    """
    logger.debug("resolve_model_params: provider=%s model=%s", ai_model.provider, ai_model.model_name)
    params = {
        'model_id': ai_model.model_name or 'gemini-2.5-flash',
    }

    # Configuration specifique par provider
    # Cles API lues exclusivement depuis les variables d'environnement (.env)
    # / Provider-specific configuration
    # / API keys read exclusively from environment variables (.env)
    if ai_model.provider == Provider.GOOGLE:
        cle_api_google = os.environ.get("GOOGLE_API_KEY", "")
        if cle_api_google:
            params['api_key'] = cle_api_google

    elif ai_model.provider == Provider.OPENAI:
        cle_api_openai = os.environ.get("OPENAI_API_KEY", "")
        if not cle_api_openai:
            raise ValueError("Clé API OpenAI manquante. Renseignez OPENAI_API_KEY dans .env.")
        params['api_key'] = cle_api_openai
        # OpenAI necessite des parametres specifiques dans LangExtract
        # / OpenAI requires specific params in LangExtract
        params['fence_output'] = True
        params['use_schema_constraints'] = False

    elif ai_model.provider == Provider.OLLAMA:
        # Ollama est supporte nativement par LangExtract (OllamaLanguageModel)
        # / Ollama is natively supported by LangExtract (OllamaLanguageModel)
        base_url_ollama = ai_model.base_url or "http://localhost:11434"
        params['model_url'] = base_url_ollama
        cle_api_ollama = os.environ.get("OLLAMA_API_KEY", "")
        if cle_api_ollama:
            params['api_key'] = cle_api_ollama

    elif ai_model.provider == Provider.COMPATIBLE_OPENAI:
        # LANGEXTRACT CHOISIT SON MOTEUR PAR EXPRESSION REGULIERE SUR LE
        # NOM DU MODELE (`providers/patterns.py`), et c'est un piege :
        # `mistral-small-latest` matche `^mistral` et partirait vers
        # `OllamaLanguageModel`, qui parle l'API PROPRIETAIRE d'Ollama
        # (`POST {base}/api/generate`). Pointe sur api.mistral.ai, ce
        # moteur echoue — et rien dans le nom ne le laissait deviner.
        # Meme piege pour `^qwen`, `^llama`, `^gemma`, `^phi`,
        # `^deepseek`.
        #
        # `config` resout le provider par son NOM et court-circuite la
        # table. C'est une API PUBLIQUE de la bibliotheque : aucun fork,
        # rien a surcharger, contrairement au reste de notre dette
        # LangExtract.
        # / LangExtract routes by regex on the model name; ModelConfig
        # resolves by provider name instead, and is public API.
        from langextract import factory as fabrique_langextract

        nom_de_la_variable = (ai_model.variable_de_cle_api or "").strip()
        if not nom_de_la_variable:
            raise ValueError(
                f"Le modèle « {ai_model} » ne dit pas quelle variable "
                f"d'environnement porte sa clé : renseignez "
                f"`variable_de_cle_api` (ex: MISTRAL_API_KEY)."
            )
        cle_api = os.environ.get(nom_de_la_variable, "")
        if not cle_api:
            raise ValueError(
                f"Clé API manquante : la variable {nom_de_la_variable} "
                f"est vide ou absente du .env."
            )
        if not ai_model.base_url:
            raise ValueError(
                f"Le modèle « {ai_model} » n'a pas de `base_url` : c'est "
                f"elle qui désigne la plateforme à appeler."
            )

        params['config'] = fabrique_langextract.ModelConfig(
            model_id=ai_model.technical_model_name,
            # Le nom de CLASSE, pas « openai » : la resolution se fait
            # par sous-chaine, et un nom exact reste sans ambiguite le
            # jour ou un autre provider contiendra « openai ».
            # / The class name: resolution is by substring.
            provider="OpenAILanguageModel",
            provider_kwargs={
                "api_key": cle_api,
                "base_url": ai_model.base_url,
            },
        )
        # Ce provider n'expose AUCUN schema structure : la contrainte ne
        # s'appliquerait pas, et la laisser active fait emettre un
        # avertissement a chaque chunk. La seule contrainte de forme est
        # le `response_format` que le provider pose lui-meme.
        # / This provider exposes no structured schema; leaving the
        # constraint on only emits a warning per chunk.
        params['use_schema_constraints'] = False

    elif ai_model.provider == Provider.ANTHROPIC:
        # Anthropic n'est pas supporte par LangExtract pour l'extraction
        # / Anthropic is not supported by LangExtract for extraction
        raise ValueError(
            "Anthropic ne supporte pas l'extraction. "
            "Utilisez Gemini, OpenAI ou Ollama pour l'extraction. "
            "Anthropic est disponible pour la synthese."
        )

    elif ai_model.provider == Provider.MOCK:
        # Pour le mock, on utilise un provider qui existe
        # / For mock, use an existing provider
        params['model_id'] = 'gemini-2.5-flash'

    else:
        # Provider inconnu / Unknown provider
        raise ValueError(
            f"Le provider '{ai_model.provider}' n'est pas supporte par LangExtract."
        )

    return params


def _construire_exemples_langextract(analyseur, exclude_example_pk=None):
    """
    Construit la liste des exemples LangExtract depuis un AnalyseurSyntaxique.
    Optionnellement exclut un exemple (anti data-leakage pour les tests).
    / Build LangExtract examples list from an AnalyseurSyntaxique.
    Optionally excludes an example (anti data-leakage for tests).
    """
    from ..models import AnalyseurExample

    # Recuperer tous les exemples de l'analyseur, avec prefetch des extractions et attributs
    # / Fetch all analyzer examples, with prefetch of extractions and attributes
    queryset_exemples = AnalyseurExample.objects.filter(
        analyseur=analyseur,
    ).order_by("order").prefetch_related("extractions__attributes")

    if exclude_example_pk is not None:
        # Anti data-leakage : exclure l'exemple teste, SAUF s'il est le seul
        # / Anti data-leakage: exclude tested example, UNLESS it's the only one
        queryset_exemples_filtres = queryset_exemples.exclude(pk=exclude_example_pk)
        if not queryset_exemples_filtres.exists():
            logger.warning(
                "_construire_exemples_langextract: aucun autre exemple — "
                "fallback sur l'exemple teste (anti data-leakage desactive)"
            )
            queryset_exemples_filtres = queryset_exemples.filter(pk=exclude_example_pk)
        queryset_exemples = queryset_exemples_filtres

    liste_exemples_langextract = []
    for exemple_django in queryset_exemples:
        liste_extractions = []
        for extraction_django in exemple_django.extractions.all():
            dictionnaire_attributs = {}
            for attribut in extraction_django.attributes.all():
                dictionnaire_attributs[attribut.key] = attribut.value
            liste_extractions.append(
                lx.data.Extraction(
                    extraction_class=extraction_django.extraction_class,
                    extraction_text=extraction_django.extraction_text,
                    attributes=dictionnaire_attributs,
                )
            )
        liste_exemples_langextract.append(
            lx.data.ExampleData(
                text=exemple_django.example_text,
                extractions=liste_extractions,
            )
        )

    return liste_exemples_langextract


def verifier_utilisabilite_analyseur(analyseur):
    """
    Verifie qu'un analyseur d'extraction est exploitable par LangExtract.
    / Check that an extraction analyzer is usable by LangExtract.

    LOCALISATION : hypostasis_extractor/services.py

    Un analyseur d'extraction sert a montrer au LLM ce qu'il doit extraire.
    Pour cela, il a besoin d'au moins un exemple complet : un texte source
    rempli ET au moins une extraction avec une classe et un texte remplis.
    Sans cet exemple, LangExtract n'envoie aucun cadre au LLM. Le LLM invente
    alors son propre format de reponse et les extractions sont perdues
    (c'est le bug "exemples=0" vu dans les logs).

    Cette fonction ne modifie rien et ne bloque rien. Elle dit juste si
    l'analyseur est pret a etre utilise, et pourquoi il ne l'est pas.

    Les analyseurs de synthese ne s'appuient pas sur des exemples few-shot :
    ils sont toujours consideres utilisables ici (leur propre blocage est
    gere dans la vue de synthese via inclure_extractions / inclure_texte_original).

    / An extraction analyzer teaches the LLM what to extract. It needs at least
    / one complete example: a filled source text AND at least one extraction with
    / a filled class and text. Without it LangExtract sends no frame to the LLM,
    / which invents its own format and extractions are lost. Read-only diagnostic,
    / never blocks. Synthesis analyzers don't rely on examples and are always
    / considered usable here.

    :param analyseur: instance AnalyseurSyntaxique
    :return: tuple (utilisable: bool, problemes: list[str])
    """
    from ..models import AnalyseurSyntaxique

    # Le critere few-shot ne concerne que les analyseurs d'extraction.
    # / The few-shot rule only applies to extraction analyzers.
    if analyseur.type_analyseur != AnalyseurSyntaxique.TypeAnalyseur.ANALYSER:
        return True, []

    # On parcourt les exemples (le prefetch est reutilise s'il a ete fait par l'appelant).
    # / Iterate over examples (reuses caller's prefetch if any).
    exemples_de_l_analyseur = analyseur.examples.all()

    if not exemples_de_l_analyseur:
        return False, ["L'analyseur n'a aucun exemple few-shot."]

    # On cherche un seul exemple complet : texte source + une extraction remplie.
    # / Look for a single complete example: source text + one filled extraction.
    au_moins_un_exemple_avec_texte = False
    au_moins_un_exemple_complet = False

    for exemple in exemples_de_l_analyseur:
        texte_source_present = bool((exemple.example_text or "").strip())
        if not texte_source_present:
            continue
        au_moins_un_exemple_avec_texte = True

        for extraction in exemple.extractions.all():
            classe_presente = bool((extraction.extraction_class or "").strip())
            texte_present = bool((extraction.extraction_text or "").strip())
            if classe_presente and texte_present:
                au_moins_un_exemple_complet = True
                break

        if au_moins_un_exemple_complet:
            break

    # On construit les messages d'explication selon ce qui manque.
    # / Build explanation messages depending on what is missing.
    problemes = []
    if not au_moins_un_exemple_avec_texte:
        problemes.append("Aucun exemple n'a de texte source.")
    elif not au_moins_un_exemple_complet:
        problemes.append(
            "Aucun exemple ne contient d'extraction exploitable (classe + texte)."
        )

    return au_moins_un_exemple_complet, problemes


def _check_ia_active():
    """
    Verifie que l'IA est activee dans la configuration singleton.
    Leve une RuntimeError si desactivee.
    / Check AI is enabled in singleton config. Raises RuntimeError if disabled.
    """
    from core.models import Configuration
    if not Configuration.get_solo().ai_active:
        raise RuntimeError("IA desactivee. Activez l'IA depuis le panneau de gauche.")


def _try_map_to_hypostasis(entity):
    """
    Tente de mapper une entite extraite vers une HypostasisTag existante.
    Utilise le extraction_class pour trouver une correspondance.
    """
    from core.models import HypostasisTag
    
    # Normalise le nom de la classe d'extraction
    class_name = entity.extraction_class.lower().strip()
    
    # Cherche une hypostasis avec le meme nom
    try:
        hypostasis = HypostasisTag.objects.filter(
            name__iexact=class_name
        ).first()
        
        if hypostasis:
            entity.hypostasis_tag = hypostasis
            entity.save(update_fields=['hypostasis_tag'])
    except Exception:
        # On ignore silencieusement les erreurs de mapping
        pass


def creer_snapshot_analyseur(analyseur):
    """
    Cree un snapshot JSON complet d'un analyseur.
    Le snapshot contient les pieces du prompt, les exemples few-shot,
    les extractions attendues et leurs attributs.
    Utilise pour l'historique des versions (AnalyseurVersion).
    / Create a full JSON snapshot of an analyzer (pieces, examples, extractions, attributes).

    LOCALISATION : hypostasis_extractor/services/__init__.py
    """
    from ..models import PromptPiece, AnalyseurExample

    # Recuperer toutes les pieces du prompt ordonnees par position
    # / Fetch all prompt pieces ordered by position
    toutes_les_pieces_ordonnees = PromptPiece.objects.filter(
        analyseur=analyseur,
    ).order_by('order')
    toutes_les_pieces_snapshot = []
    for piece in toutes_les_pieces_ordonnees:
        toutes_les_pieces_snapshot.append({
            'name': piece.name,
            'role': piece.role,
            'content': piece.content,
            'order': piece.order,
        })

    # Recuperer tous les exemples avec leurs extractions et attributs pre-charges
    # / Fetch all examples with prefetched extractions and attributes
    tous_les_exemples_ordonnes = AnalyseurExample.objects.filter(
        analyseur=analyseur,
    ).order_by('order').prefetch_related('extractions__attributes')
    tous_les_exemples_snapshot = []
    for exemple in tous_les_exemples_ordonnes:
        toutes_les_extractions_de_exemple = []
        for extraction in exemple.extractions.all():
            tous_les_attributs_de_extraction = []
            for attribut in extraction.attributes.all():
                tous_les_attributs_de_extraction.append({
                    'key': attribut.key,
                    'value': attribut.value,
                    'order': attribut.order,
                })
            toutes_les_extractions_de_exemple.append({
                'extraction_class': extraction.extraction_class,
                'extraction_text': extraction.extraction_text,
                'order': extraction.order,
                'attributes': tous_les_attributs_de_extraction,
            })
        tous_les_exemples_snapshot.append({
            'name': exemple.name,
            'example_text': exemple.example_text,
            'order': exemple.order,
            'extractions': toutes_les_extractions_de_exemple,
        })

    return {
        'name': analyseur.name,
        'description': analyseur.description,
        'type_analyseur': analyseur.type_analyseur,
        'inclure_extractions': analyseur.inclure_extractions,
        'inclure_texte_original': analyseur.inclure_texte_original,
        'pieces': toutes_les_pieces_snapshot,
        'examples': tous_les_exemples_snapshot,
    }


def creer_version_analyseur(analyseur, user, description=""):
    """
    Cree une AnalyseurVersion avec numero de version auto-incremente.
    Prend un snapshot complet de l'analyseur et le stocke en JSON.
    / Create an AnalyseurVersion with auto-incremented version number.

    LOCALISATION : hypostasis_extractor/services/__init__.py
    """
    from ..models import AnalyseurVersion
    from django.db.models import Max

    # Calculer le prochain numero de version a partir du max existant
    # / Compute next version number from existing max
    dernier_numero_version = analyseur.versions.aggregate(
        max_num=Max('version_number'),
    )['max_num'] or 0
    prochain_numero_version = dernier_numero_version + 1

    # Creer le snapshot complet et l'enregistrer en base
    # / Create full snapshot and save to database
    snapshot_complet = creer_snapshot_analyseur(analyseur)
    nouvelle_version = AnalyseurVersion.objects.create(
        analyseur=analyseur,
        version_number=prochain_numero_version,
        snapshot=snapshot_complet,
        modified_by=user if user and user.is_authenticated else None,
        description_modification=description[:500],
    )
    logger.info(
        "creer_version_analyseur: analyseur=%d v%d par %s — %s",
        analyseur.pk, prochain_numero_version,
        user.username if user and user.is_authenticated else "anonyme",
        description[:80],
    )
    return nouvelle_version
