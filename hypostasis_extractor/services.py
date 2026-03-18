"""
Services pour l'integration LangExtract.
Wrapper autour de la librairie langextract pour s'integrer avec Hypostasia.
"""

import os
import time
import logging
import langextract as lx
from typing import List, Dict, Optional

from core.models import AIModel, Provider

logger = logging.getLogger(__name__)


def build_langextract_examples(job) -> List[lx.data.ExampleData]:
    """
    Construit les exemples few-shot pour LangExtract
    a partir des ExtractionExample associes au job.
    """
    from .models import JobExampleMapping
    
    examples = []
    mappings = JobExampleMapping.objects.filter(
        job=job
    ).select_related('example').order_by('order')
    
    for mapping in mappings:
        example_data = mapping.example
        
        # Convertit les extractions JSON en objets lx.data.Extraction
        extractions = []
        for ext in example_data.example_extractions:
            extractions.append(
                lx.data.Extraction(
                    extraction_class=ext['extraction_class'],
                    extraction_text=ext['extraction_text'],
                    attributes=ext.get('attributes', {})
                )
            )
        
        examples.append(
            lx.data.ExampleData(
                text=example_data.example_text,
                extractions=extractions
            )
        )
    
    return examples


def resolve_model_params(ai_model: AIModel) -> Dict:
    """
    Convertit une configuration AIModel en parametres pour LangExtract.
    Supporte Google, OpenAI, Ollama (natif LangExtract) et Mock.
    Anthropic leve une ValueError car non supporte par LangExtract.
    / Converts an AIModel config into LangExtract parameters.
    Supports Google, OpenAI, Ollama (native LangExtract), Mock.
    Anthropic raises ValueError (not supported by LangExtract).

    LOCALISATION : hypostasis_extractor/services.py
    """
    logger.debug("resolve_model_params: provider=%s model=%s", ai_model.provider, ai_model.model_name)
    params = {
        'model_id': ai_model.model_name or 'gemini-2.5-flash',
    }

    # Configuration specifique par provider
    # Cle API : priorite au champ DB, fallback sur variable d'environnement
    # / Provider-specific configuration
    # / API key: DB field priority, fallback to environment variable
    if ai_model.provider == Provider.GOOGLE:
        cle_api_google = ai_model.api_key or os.environ.get("GOOGLE_API_KEY", "")
        if cle_api_google:
            params['api_key'] = cle_api_google

    elif ai_model.provider == Provider.OPENAI:
        cle_api_openai = ai_model.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not cle_api_openai:
            raise ValueError("Clé API OpenAI manquante. Renseignez OPENAI_API_KEY dans .env ou dans l'admin (AIModel).")
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
        cle_api_ollama = ai_model.api_key or os.environ.get("OLLAMA_API_KEY", "")
        if cle_api_ollama:
            params['api_key'] = cle_api_ollama

    elif ai_model.provider == Provider.ANTHROPIC:
        # Anthropic n'est pas supporte par LangExtract pour l'extraction
        # / Anthropic is not supported by LangExtract for extraction
        raise ValueError(
            "Anthropic ne supporte pas l'extraction. "
            "Utilisez Gemini, OpenAI ou Ollama pour l'extraction. "
            "Anthropic est disponible pour la reformulation et la restitution."
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
    from .models import AnalyseurExample

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


def _check_ia_active():
    """
    Verifie que l'IA est activee dans la configuration singleton.
    Leve une RuntimeError si desactivee.
    / Check AI is enabled in singleton config. Raises RuntimeError if disabled.
    """
    from core.models import Configuration
    if not Configuration.get_solo().ai_active:
        raise RuntimeError("IA desactivee. Activez l'IA depuis le panneau de gauche.")


def run_langextract_job(job, use_chunking: bool = False, max_workers: int = 1):
    """
    Execute un job d'extraction avec LangExtract.

    Args:
        job: Instance ExtractionJob
        use_chunking: Active le decoupage pour les longs documents
        max_workers: Nombre de workers paralleles

    Returns:
        Tuple (nombre_entites_creees, temps_execution)
    """
    _check_ia_active()
    from .models import ExtractedEntity, ExtractionJobStatus
    
    # Marque le job comme en cours
    job.status = ExtractionJobStatus.PROCESSING
    job.error_message = None
    job.save(update_fields=['status', 'error_message'])
    
    start_time = time.time()
    
    try:
        # Recupere le texte a analyser depuis la Page
        text_source = job.page.text_readability
        if not text_source:
            raise ValueError("La Page n'a pas de text_readability disponible")
        
        # Construit les exemples few-shot
        examples = build_langextract_examples(job)
        
        # Resolve la configuration du modele
        if job.ai_model:
            model_params = resolve_model_params(job.ai_model)
        else:
            # Fallback sur Gemini par defaut
            model_params = {'model_id': 'gemini-2.5-flash'}
        
        # Parametres d'extraction
        extract_params = {
            'text_or_documents': text_source,
            'prompt_description': job.prompt_description,
            'examples': examples,
        }
        
        # Ajoute le chunking si demande
        if use_chunking and len(text_source) > 4000:
            extract_params['extraction_passes'] = 3
            extract_params['max_workers'] = max_workers
            extract_params['max_char_buffer'] = 1000
        
        # Fusionne avec les parametres du modele
        extract_params.update(model_params)
        
        # Execute l'extraction
        logger.info("run_langextract_job: lancement job=%d model=%s text_len=%d",
                     job.id, extract_params.get('model_id', '?'), len(text_source))
        result = lx.extract(**extract_params)
        
        # Supprime les anciennes entites si re-extraction
        job.entities.all().delete()
        
        # Cree les entites extraites
        entities_created = 0
        for extraction in result.extractions:
            ci = extraction.char_interval
            entity = ExtractedEntity.objects.create(
                job=job,
                extraction_class=extraction.extraction_class,
                extraction_text=extraction.extraction_text,
                start_char=ci.start_pos if ci else 0,
                end_char=ci.end_pos if ci else 0,
                attributes=extraction.attributes
            )
            entities_created += 1
            
            # Tente de mapper vers une HypostasisTag existante
            _try_map_to_hypostasis(entity)
        
        # Met a jour le job
        job.raw_result = {
            'extractions_count': len(result.extractions),
            'document_length': len(text_source),
            'processing_params': {
                'chunking': use_chunking,
                'max_workers': max_workers if use_chunking else 1
            }
        }
        job.entities_count = entities_created
        job.status = ExtractionJobStatus.COMPLETED
        job.processing_time_seconds = time.time() - start_time
        job.save()
        
        logger.info("run_langextract_job: job=%d termine — %d entites en %.2fs",
                     job.id, entities_created, job.processing_time_seconds)
        
        return entities_created, job.processing_time_seconds
        
    except Exception as e:
        # Gestion des erreurs
        error_msg = str(e)
        logger.error("run_langextract_job: ERREUR job=%d — %s", job.id, error_msg, exc_info=True)
        
        job.status = ExtractionJobStatus.ERROR
        job.error_message = error_msg
        job.processing_time_seconds = time.time() - start_time
        job.save(update_fields=['status', 'error_message', 'processing_time_seconds'])
        
        raise


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


def run_analyseur_test(analyseur, example, ai_model):
    """
    Lance LangExtract sur le texte d'un exemple, en excluant cet exemple des few-shot.
    Cree un AnalyseurTestRun + TestRunExtraction pour chaque resultat.
    / Run LangExtract on an example's text, excluding that example from few-shot.
    Creates AnalyseurTestRun + TestRunExtraction for each result.
    """
    _check_ia_active()
    from .models import (
        AnalyseurTestRun, TestRunExtraction, ExtractionJobStatus,
        PromptPiece,
    )

    # 1. Construire le prompt snapshot / Build prompt snapshot
    logger.info("run_analyseur_test: analyseur=%d example=%d ai_model=%s",
                analyseur.pk, example.pk, ai_model.model_name)
    pieces_ordonnees = PromptPiece.objects.filter(
        analyseur=analyseur
    ).order_by('order')
    prompt_snapshot = "\n".join(piece.content for piece in pieces_ordonnees)
    logger.debug("run_analyseur_test: prompt_snapshot=%d chars, %d pieces",
                 len(prompt_snapshot), len(pieces_ordonnees))

    # 2. Construire les exemples few-shot SANS l'exemple teste (anti data-leakage)
    # / Build few-shot examples WITHOUT the tested example (anti data-leakage)
    liste_exemples_langextract = _construire_exemples_langextract(
        analyseur, exclude_example_pk=example.pk,
    )
    logger.debug("run_analyseur_test: %d exemples few-shot (excluant pk=%d)",
                 len(liste_exemples_langextract), example.pk)

    # 3. Resoudre les parametres du modele / Resolve model params
    model_params = resolve_model_params(ai_model)
    ai_model_display_name = f"{ai_model.provider} / {ai_model.model_name}"

    # 4. Creer le TestRun en status processing
    test_run = AnalyseurTestRun.objects.create(
        analyseur=analyseur,
        example=example,
        ai_model=ai_model,
        ai_model_display_name=ai_model_display_name,
        prompt_snapshot=prompt_snapshot,
        status=ExtractionJobStatus.PROCESSING,
    )

    start_time = time.time()

    try:
        # 5. Appel LangExtract
        extract_params = {
            'text_or_documents': example.example_text,
            'prompt_description': prompt_snapshot,
            'examples': liste_exemples_langextract,
        }
        extract_params.update(model_params)

        logger.info("run_analyseur_test: appel lx.extract() model=%s text_len=%d examples=%d",
                    extract_params.get('model_id', '?'), len(example.example_text),
                    len(liste_exemples_langextract))
        resultat = lx.extract(**extract_params)
        logger.info("run_analyseur_test: LLM termine — %d extractions recues",
                    len(resultat.extractions or []))

        # 6. Creer les TestRunExtraction
        for ordre, extraction in enumerate(resultat.extractions or []):
            ci = extraction.char_interval
            TestRunExtraction.objects.create(
                test_run=test_run,
                extraction_class=extraction.extraction_class,
                extraction_text=extraction.extraction_text,
                start_pos=ci.start_pos if ci else 0,
                end_pos=ci.end_pos if ci else 0,
                attributes=extraction.attributes or {},
                order=ordre,
            )

        test_run.status = ExtractionJobStatus.COMPLETED
        test_run.processing_time_seconds = time.time() - start_time
        test_run.extractions_count = len(resultat.extractions or [])
        test_run.raw_result = {
            'extractions_count': test_run.extractions_count,
            'text_length': len(example.example_text),
        }
        test_run.save()
        logger.info("run_analyseur_test: test_run=%d COMPLETED — %d extractions en %.1fs",
                    test_run.pk, test_run.extractions_count, test_run.processing_time_seconds)

    except Exception as e:
        test_run.status = ExtractionJobStatus.ERROR
        test_run.error_message = str(e)
        test_run.processing_time_seconds = time.time() - start_time
        test_run.save()
        logger.error("run_analyseur_test: test_run=%d ERROR — %s", test_run.pk, str(e), exc_info=True)
        raise

    return test_run


def run_analyseur_on_page(analyseur, page, ai_model):
    """
    Lance LangExtract sur une Page en utilisant un AnalyseurSyntaxique.
    Cree un ExtractionJob + ExtractedEntity pour chaque resultat.
    / Run LangExtract on a Page using an AnalyseurSyntaxique.
    Creates ExtractionJob + ExtractedEntity for each result.
    """
    from .models import (
        ExtractionJob, ExtractedEntity, ExtractionJobStatus,
        PromptPiece,
    )

    # 1. Construire le prompt depuis les pieces / Build prompt from pieces
    pieces_ordonnees = PromptPiece.objects.filter(
        analyseur=analyseur
    ).order_by('order')
    prompt_snapshot = "\n".join(piece.content for piece in pieces_ordonnees)

    # 2. Construire les exemples few-shot (TOUS) via la fonction commune
    # / Build all few-shot examples via the shared function
    liste_exemples_langextract = _construire_exemples_langextract(analyseur)

    # 3. Resoudre les parametres du modele / Resolve model params
    model_params = resolve_model_params(ai_model)

    # 4. Creer le job / Create the job
    job = ExtractionJob.objects.create(
        page=page,
        ai_model=ai_model,
        name=f"Analyseur: {analyseur.name}",
        prompt_description=prompt_snapshot,
        status=ExtractionJobStatus.PROCESSING,
    )

    start_time = time.time()

    try:
        text_source = page.text_readability
        if not text_source:
            raise ValueError("La Page n'a pas de text_readability disponible")

        extract_params = {
            'text_or_documents': text_source,
            'prompt_description': prompt_snapshot,
            'examples': liste_exemples_langextract,
        }
        extract_params.update(model_params)

        logger.info("run_analyseur_on_page: job=%d analyseur=%s model=%s text_len=%d",
                     job.id, analyseur.name, extract_params.get('model_id', '?'), len(text_source))
        resultat = lx.extract(**extract_params)

        # 5. Creer les entites / Create entities
        entities_created = 0
        for extraction in resultat.extractions or []:
            ci = extraction.char_interval
            entity = ExtractedEntity.objects.create(
                job=job,
                extraction_class=extraction.extraction_class,
                extraction_text=extraction.extraction_text,
                start_char=ci.start_pos if ci else 0,
                end_char=ci.end_pos if ci else 0,
                attributes=extraction.attributes or {},
            )
            entities_created += 1
            _try_map_to_hypostasis(entity)

        job.status = ExtractionJobStatus.COMPLETED
        job.entities_count = entities_created
        job.processing_time_seconds = time.time() - start_time
        job.raw_result = {
            'extractions_count': entities_created,
            'document_length': len(text_source),
            'analyseur_id': analyseur.pk,
        }
        job.save()
        logger.info("run_analyseur_on_page: job=%d COMPLETED — %d entites en %.1fs",
                     job.id, entities_created, job.processing_time_seconds)

    except Exception as e:
        job.status = ExtractionJobStatus.ERROR
        job.error_message = str(e)
        job.processing_time_seconds = time.time() - start_time
        job.save(update_fields=['status', 'error_message', 'processing_time_seconds'])
        logger.error("run_analyseur_on_page: job=%d ERROR — %s", job.id, str(e), exc_info=True)
        raise

    return job


def generate_visualization_html(job) -> str:
    """
    Genere le HTML de visualisation pour un job.
    Utilise la fonction visualize de LangExtract.
    """
    import json

    # Construit les objets LangExtract natifs
    extractions = []
    for entity in job.entities.all():
        char_interval = lx.data.CharInterval(
            start_pos=entity.start_char,
            end_pos=entity.end_char
        )
        extractions.append(lx.data.Extraction(
            extraction_class=entity.extraction_class,
            extraction_text=entity.extraction_text,
            char_interval=char_interval,
            attributes=entity.attributes or {}
        ))

    doc = lx.data.AnnotatedDocument(
        text=job.page.text_readability,
        extractions=extractions
    )

    # Serialise au format JSONL attendu par lx.visualize
    doc_dict = lx.data_lib.annotated_document_to_dict(doc)
    temp_file = f"/tmp/langextract_job_{job.id}.jsonl"
    with open(temp_file, 'w') as f:
        f.write(json.dumps(doc_dict))

    html_content = lx.visualize(temp_file)

    return html_content


def creer_snapshot_analyseur(analyseur):
    """
    Cree un snapshot JSON complet d'un analyseur.
    Le snapshot contient les pieces du prompt, les exemples few-shot,
    les extractions attendues et leurs attributs.
    Utilise pour l'historique des versions (AnalyseurVersion).
    / Create a full JSON snapshot of an analyzer (pieces, examples, extractions, attributes).

    LOCALISATION : hypostasis_extractor/services.py
    """
    from .models import PromptPiece, AnalyseurExample

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

    LOCALISATION : hypostasis_extractor/services.py
    """
    from .models import AnalyseurVersion
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
