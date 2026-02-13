"""
Taches Celery pour le traitement asynchrone (audio + analyse textuelle).
/ Celery tasks for asynchronous processing (audio + text analysis).
"""

import hashlib
import logging
import os
import time

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def transcrire_audio_task(self, job_id, chemin_fichier_audio):
    """
    Tache Celery : transcrit un fichier audio et met a jour la Page associee.
    / Celery task: transcribes an audio file and updates the associated Page.

    1. Charge le TranscriptionJob → status=PROCESSING
    2. Appelle Voxtral ou Mock selon le provider
    3. Construit le HTML diarise + texte brut
    4. Met a jour la Page (html_readability, text_readability, content_hash, status)
    5. Met a jour le Job (raw_result, status, processing_time)
    6. Supprime le fichier audio temporaire
    """
    from core.models import TranscriptionJob, TranscriptionJobStatus, PageStatus
    from front.services.transcription_audio import (
        transcrire_audio_via_voxtral,
        transcrire_audio_mock,
        construire_html_diarise,
    )

    debut_traitement = time.time()

    # Charger le job de transcription
    # / Load the transcription job
    try:
        job_transcription = TranscriptionJob.objects.select_related(
            "page", "transcription_config",
        ).get(pk=job_id)
    except TranscriptionJob.DoesNotExist:
        logger.error("transcrire_audio_task: job_id=%s introuvable", job_id)
        return

    page_associee = job_transcription.page
    config_transcription = job_transcription.transcription_config

    # Passer le job en PROCESSING
    # / Set job to PROCESSING
    job_transcription.status = TranscriptionJobStatus.PROCESSING
    job_transcription.celery_task_id = self.request.id or ""
    job_transcription.save(update_fields=["status", "celery_task_id"])

    logger.info(
        "transcrire_audio_task: demarrage job=%s page=%s fichier=%s provider=%s",
        job_id, page_associee.pk, chemin_fichier_audio,
        config_transcription.provider if config_transcription else "aucun",
    )

    try:
        # Dispatcher selon le provider de la config
        # / Dispatch based on config provider
        if config_transcription and config_transcription.provider == "voxtral":
            segments_transcrits = transcrire_audio_via_voxtral(
                chemin_fichier_audio, config_transcription,
            )
        else:
            # Mock par defaut / Mock by default
            segments_transcrits = transcrire_audio_mock(
                chemin_fichier_audio, config_transcription,
            )

        # Construire le HTML colore et le texte brut
        # / Build colored HTML and plain text
        html_diarise, texte_brut = construire_html_diarise(segments_transcrits)

        # Calculer le hash du contenu / Compute content hash
        hash_contenu = hashlib.sha256(texte_brut.encode("utf-8")).hexdigest()

        # Mettre a jour la Page / Update the Page
        page_associee.html_readability = html_diarise
        page_associee.text_readability = texte_brut
        page_associee.content_hash = hash_contenu
        page_associee.status = PageStatus.COMPLETED
        page_associee.save(update_fields=[
            "html_readability", "text_readability", "content_hash", "status",
        ])

        # Mettre a jour le Job / Update the Job
        duree_traitement = time.time() - debut_traitement
        job_transcription.raw_result = segments_transcrits
        job_transcription.status = TranscriptionJobStatus.COMPLETED
        job_transcription.processing_time_seconds = round(duree_traitement, 2)
        job_transcription.save(update_fields=[
            "raw_result", "status", "processing_time_seconds",
        ])

        logger.info(
            "transcrire_audio_task: termine job=%s page=%s segments=%d duree=%.1fs",
            job_id, page_associee.pk, len(segments_transcrits), duree_traitement,
        )

    except Exception as erreur_transcription:
        # En cas d'erreur, marquer le job et la page en erreur
        # / On error, mark both job and page as error
        duree_traitement = time.time() - debut_traitement
        message_erreur = str(erreur_transcription)

        logger.error(
            "transcrire_audio_task: erreur job=%s — %s",
            job_id, message_erreur, exc_info=True,
        )

        page_associee.status = PageStatus.ERROR
        page_associee.error_message = message_erreur[:1000]
        page_associee.save(update_fields=["status", "error_message"])

        job_transcription.status = TranscriptionJobStatus.ERROR
        job_transcription.error_message = message_erreur
        job_transcription.processing_time_seconds = round(duree_traitement, 2)
        job_transcription.save(update_fields=[
            "status", "error_message", "processing_time_seconds",
        ])

    finally:
        # Supprimer le fichier audio temporaire (qu'il y ait eu erreur ou non)
        # / Delete the temporary audio file (whether there was an error or not)
        if os.path.exists(chemin_fichier_audio):
            try:
                os.unlink(chemin_fichier_audio)
                logger.debug("transcrire_audio_task: fichier temp supprime %s", chemin_fichier_audio)
            except OSError as erreur_suppression:
                logger.warning(
                    "transcrire_audio_task: impossible de supprimer %s — %s",
                    chemin_fichier_audio, erreur_suppression,
                )


@shared_task(bind=True)
def analyser_page_task(self, job_id):
    """
    Tache Celery : lance l'extraction LangExtract sur une Page via un ExtractionJob.
    Le job doit deja exister en status PENDING avec page, ai_model et prompt_description remplis.
    / Celery task: runs LangExtract extraction on a Page via an ExtractionJob.
    The job must already exist in PENDING status with page, ai_model and prompt_description filled.
    """
    from hypostasis_extractor.models import (
        ExtractionJob, ExtractedEntity, ExtractionJobStatus,
    )
    from hypostasis_extractor.services import resolve_model_params, _try_map_to_hypostasis
    import langextract as lx

    debut_traitement = time.time()

    # Charger le job d'extraction
    # / Load the extraction job
    try:
        job_extraction = ExtractionJob.objects.select_related(
            "page", "ai_model",
        ).get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error("analyser_page_task: job_id=%s introuvable", job_id)
        return

    page_associee = job_extraction.page

    # Passer le job en PROCESSING
    # / Set job to PROCESSING
    job_extraction.status = ExtractionJobStatus.PROCESSING
    job_extraction.error_message = None
    job_extraction.save(update_fields=["status", "error_message"])

    logger.info(
        "analyser_page_task: demarrage job=%s page=%s model=%s",
        job_id, page_associee.pk,
        job_extraction.ai_model.model_name if job_extraction.ai_model else "?",
    )

    try:
        texte_source = page_associee.text_readability
        if not texte_source:
            raise ValueError("La Page n'a pas de text_readability disponible")

        # Reconstruire les exemples few-shot depuis le prompt_description du job
        # Le job stocke deja le prompt_snapshot et les exemples sont passes via raw_result
        # / Rebuild few-shot examples from job's stored data
        exemples_serialises = (job_extraction.raw_result or {}).get("examples_data", [])
        liste_exemples_langextract = []
        for exemple_dict in exemples_serialises:
            liste_extractions = []
            for ext_dict in exemple_dict.get("extractions", []):
                liste_extractions.append(
                    lx.data.Extraction(
                        extraction_class=ext_dict.get("extraction_class", ""),
                        extraction_text=ext_dict.get("extraction_text", ""),
                        attributes=ext_dict.get("attributes", {}),
                    )
                )
            liste_exemples_langextract.append(
                lx.data.ExampleData(
                    text=exemple_dict.get("text", ""),
                    extractions=liste_extractions,
                )
            )

        # Resoudre les parametres du modele / Resolve model params
        if job_extraction.ai_model:
            parametres_modele = resolve_model_params(job_extraction.ai_model)
        else:
            parametres_modele = {"model_id": "gemini-2.5-flash"}

        parametres_extraction = {
            "text_or_documents": texte_source,
            "prompt_description": job_extraction.prompt_description,
            "examples": liste_exemples_langextract,
        }
        parametres_extraction.update(parametres_modele)

        logger.info(
            "analyser_page_task: appel lx.extract() job=%s model=%s text_len=%d examples=%d",
            job_id, parametres_extraction.get("model_id", "?"),
            len(texte_source), len(liste_exemples_langextract),
        )
        resultat = lx.extract(**parametres_extraction)

        # Supprimer les anciennes entites si re-extraction
        # / Delete old entities if re-extraction
        job_extraction.entities.all().delete()

        # Creer les entites extraites / Create extracted entities
        nombre_entites_creees = 0
        for extraction in resultat.extractions or []:
            intervalle_caracteres = extraction.char_interval
            entite_creee = ExtractedEntity.objects.create(
                job=job_extraction,
                extraction_class=extraction.extraction_class,
                extraction_text=extraction.extraction_text,
                start_char=intervalle_caracteres.start_pos if intervalle_caracteres else 0,
                end_char=intervalle_caracteres.end_pos if intervalle_caracteres else 0,
                attributes=extraction.attributes or {},
            )
            nombre_entites_creees += 1
            _try_map_to_hypostasis(entite_creee)

        # Mettre a jour le job (update_fields pour ne pas ecraser d'autres champs)
        # / Update the job (update_fields to avoid overwriting other fields)
        duree_traitement = time.time() - debut_traitement
        job_extraction.status = ExtractionJobStatus.COMPLETED
        job_extraction.entities_count = nombre_entites_creees
        job_extraction.processing_time_seconds = duree_traitement
        job_extraction.raw_result = {
            "extractions_count": nombre_entites_creees,
            "document_length": len(texte_source),
        }
        job_extraction.save(update_fields=[
            "status", "entities_count", "processing_time_seconds", "raw_result",
        ])

        logger.info(
            "analyser_page_task: termine job=%s — %d entites en %.1fs",
            job_id, nombre_entites_creees, duree_traitement,
        )

    except Exception as erreur_extraction:
        duree_traitement = time.time() - debut_traitement
        message_erreur = str(erreur_extraction)

        logger.error(
            "analyser_page_task: erreur job=%s — %s",
            job_id, message_erreur, exc_info=True,
        )

        job_extraction.status = ExtractionJobStatus.ERROR
        job_extraction.error_message = message_erreur
        job_extraction.processing_time_seconds = duree_traitement
        job_extraction.save(update_fields=[
            "status", "error_message", "processing_time_seconds",
        ])
