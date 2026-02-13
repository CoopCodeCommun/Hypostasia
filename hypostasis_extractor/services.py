"""
Services pour l'integration LangExtract.
Wrapper autour de la librairie langextract pour s'integrer avec Hypostasia.
"""

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
    Pour Mistral, utilise le provider OpenAI avec base_url Mistral API
    (l'API Mistral est compatible OpenAI).
    / Converts an AIModel config into LangExtract parameters.
    For Mistral, uses the OpenAI provider with Mistral API base_url
    (Mistral API is OpenAI-compatible).
    """
    logger.debug("resolve_model_params: provider=%s model=%s", ai_model.provider, ai_model.model_name)
    params = {
        'model_id': ai_model.model_name or 'gemini-2.5-flash',
    }

    # Configuration specifique par provider
    # / Provider-specific configuration
    if ai_model.provider == Provider.GOOGLE:
        # Utilise la cle API stockee ou celle de l'environnement
        # / Use stored API key or environment variable
        if ai_model.api_key:
            params['api_key'] = ai_model.api_key

    elif ai_model.provider == Provider.OPENAI:
        params['api_key'] = ai_model.api_key
        # OpenAI necessite des parametres specifiques dans LangExtract
        # / OpenAI requires specific params in LangExtract
        params['fence_output'] = True
        params['use_schema_constraints'] = False

    elif ai_model.provider == Provider.MOCK:
        # Pour le mock, on utilise un provider qui existe
        # / For mock, use an existing provider
        params['model_id'] = 'gemini-2.5-flash'

    else:
        # LangExtract ne supporte que Google Gemini et OpenAI GPT
        # / LangExtract only supports Google Gemini and OpenAI GPT
        raise ValueError(
            f"Le provider '{ai_model.provider}' n'est pas supporté par LangExtract. "
            f"Seuls Google (Gemini) et OpenAI (GPT) sont disponibles pour l'extraction."
        )

    return params


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
        PromptPiece, AnalyseurExample
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
    # Anti data-leakage : exclure l'exemple teste, SAUF s'il est le seul
    # / Anti data-leakage: exclude tested example, UNLESS it's the only one
    autres_exemples = AnalyseurExample.objects.filter(
        analyseur=analyseur
    ).exclude(pk=example.pk).order_by('order').prefetch_related('extractions__attributes')

    if not autres_exemples.exists():
        # Fallback : inclure l'exemple teste (LangExtract exige >= 1 exemple)
        logger.warning("run_analyseur_test: aucun autre exemple — fallback sur l'exemple teste (anti data-leakage desactive)")
        autres_exemples = AnalyseurExample.objects.filter(
            pk=example.pk
        ).prefetch_related('extractions__attributes')

    logger.debug("run_analyseur_test: %d exemples few-shot (excluant pk=%d)",
                 autres_exemples.count(), example.pk)
    liste_exemples_langextract = []
    for exemple_django in autres_exemples:
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
        PromptPiece, AnalyseurExample
    )

    # 1. Construire le prompt depuis les pieces / Build prompt from pieces
    pieces_ordonnees = PromptPiece.objects.filter(
        analyseur=analyseur
    ).order_by('order')
    prompt_snapshot = "\n".join(piece.content for piece in pieces_ordonnees)

    # 2. Construire les exemples few-shot (TOUS) / Build all few-shot examples
    tous_les_exemples = AnalyseurExample.objects.filter(
        analyseur=analyseur
    ).order_by('order').prefetch_related('extractions__attributes')

    liste_exemples_langextract = []
    for exemple_django in tous_les_exemples:
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
