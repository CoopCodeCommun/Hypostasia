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
def transcrire_audio_task(self, job_id, chemin_fichier_audio, max_locuteurs=5, langue=""):
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
                chemin_fichier_audio, config_transcription, max_locuteurs, langue,
            )
        else:
            # Mock par defaut / Mock by default
            segments_transcrits = transcrire_audio_mock(
                chemin_fichier_audio, config_transcription, max_locuteurs, langue,
            )

        # Construire le HTML colore et le texte brut
        # / Build colored HTML and plain text
        html_diarise, texte_brut = construire_html_diarise(segments_transcrits)

        # Calculer le hash du contenu / Compute content hash
        hash_contenu = hashlib.sha256(texte_brut.encode("utf-8")).hexdigest()

        # Mettre a jour la Page / Update the Page
        page_associee.transcription_raw = segments_transcrits
        page_associee.html_readability = html_diarise
        page_associee.text_readability = texte_brut
        page_associee.content_hash = hash_contenu
        page_associee.status = PageStatus.COMPLETED
        page_associee.save(update_fields=[
            "transcription_raw", "html_readability", "text_readability",
            "content_hash", "status",
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
def reformuler_entite_task(self, entity_id, analyseur_id):
    """
    Tache Celery : reformule le texte d'une ExtractedEntity via un analyseur de type reformuler.
    Appelle le LLM directement (pas LangExtract) et stocke le resultat dans entity.texte_reformule.
    En cas d'erreur (exception, crash, timeout), l'entite est remise en etat stable.
    / Celery task: reformulates an ExtractedEntity's text via a reformuler-type analyzer.
    Calls the LLM directly (not LangExtract) and stores the result in entity.texte_reformule.
    On error (exception, crash, timeout), the entity is reset to a stable state.
    """
    from core.models import Configuration
    from hypostasis_extractor.models import (
        AnalyseurSyntaxique, ExtractedEntity, PromptPiece,
    )

    debut_traitement = time.time()

    # Charger l'entite — si introuvable, rien a faire
    # / Load entity — if not found, nothing to do
    try:
        entite = ExtractedEntity.objects.get(pk=entity_id)
    except ExtractedEntity.DoesNotExist:
        logger.error("reformuler_entite_task: entity_id=%s introuvable", entity_id)
        return

    # Charger l'analyseur — si introuvable, reset l'entite et sortir
    # / Load analyzer — if not found, reset entity and exit
    try:
        analyseur = AnalyseurSyntaxique.objects.get(pk=analyseur_id)
    except AnalyseurSyntaxique.DoesNotExist:
        logger.error("reformuler_entite_task: analyseur_id=%s introuvable", analyseur_id)
        entite.reformulation_en_cours = False
        entite.reformulation_erreur = f"Analyseur introuvable (id={analyseur_id})"
        entite.save(update_fields=["reformulation_en_cours", "reformulation_erreur"])
        return

    try:
        # Recuperer le modele IA actif / Get active AI model
        configuration = Configuration.get_solo()
        modele_ia = configuration.ai_model
        if not modele_ia:
            raise ValueError("Aucun modele IA selectionne dans la configuration")

        # Construire le prompt depuis les pieces de l'analyseur
        # / Build prompt from analyzer pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        texte_prompt = "\n".join(piece.content for piece in pieces_ordonnees)

        if not texte_prompt.strip():
            raise ValueError(f"L'analyseur '{analyseur.name}' n'a aucune piece de prompt")

        # Texte source a reformuler : le texte de l'extraction
        # / Source text to reformulate: the extraction text
        texte_a_reformuler = entite.extraction_text
        if not texte_a_reformuler.strip():
            raise ValueError("Le texte de l'extraction est vide")

        # Assemblage du message complet / Full message assembly
        message_complet = f"{texte_prompt}\n\n=== TEXTE A REFORMULER ===\n{texte_a_reformuler}"

        logger.info(
            "reformuler_entite_task: entity=%s analyseur=%s model=%s text_len=%d",
            entity_id, analyseur.name, modele_ia.model_name, len(texte_a_reformuler),
        )

        # Appel au LLM selon le provider / Call LLM based on provider
        texte_reformule = _appeler_llm_reformulation(modele_ia, message_complet)

        if not texte_reformule or not texte_reformule.strip():
            raise ValueError("Le LLM a retourne une reponse vide")

        # Succes : stocker le resultat et remettre l'entite en etat stable
        # / Success: store result and reset entity to stable state
        entite.texte_reformule = texte_reformule.strip()
        entite.reformule_par = analyseur.name
        entite.reformulation_en_cours = False
        entite.reformulation_erreur = ""
        entite.save(update_fields=[
            "texte_reformule", "reformule_par",
            "reformulation_en_cours", "reformulation_erreur",
        ])

        duree = time.time() - debut_traitement
        logger.info(
            "reformuler_entite_task: termine entity=%s en %.1fs — %d chars",
            entity_id, duree, len(texte_reformule),
        )

    except Exception as erreur_reformulation:
        # Erreur : remettre l'entite en etat stable + stocker le message d'erreur
        # / Error: reset entity to stable state + store error message
        message_erreur = str(erreur_reformulation)[:500]
        logger.error(
            "reformuler_entite_task: erreur entity=%s — %s",
            entity_id, message_erreur, exc_info=True,
        )
        entite.reformulation_en_cours = False
        entite.reformulation_erreur = message_erreur
        entite.save(update_fields=["reformulation_en_cours", "reformulation_erreur"])


def _appeler_llm_reformulation(modele_ia, message_complet):
    """
    Appelle le LLM pour une reformulation (texte libre, pas extraction).
    Supporte Google Gemini et OpenAI GPT.
    / Calls the LLM for reformulation (free text, not extraction).
    Supports Google Gemini and OpenAI GPT.
    """
    from core.models import Provider

    if modele_ia.provider == Provider.GOOGLE:
        import google.generativeai as genai
        if modele_ia.api_key:
            genai.configure(api_key=modele_ia.api_key)
        modele_genai = genai.GenerativeModel(modele_ia.model_name)
        reponse = modele_genai.generate_content(message_complet)
        return reponse.text

    elif modele_ia.provider == Provider.OPENAI:
        from openai import OpenAI
        client = OpenAI(api_key=modele_ia.api_key)
        reponse = client.chat.completions.create(
            model=modele_ia.model_name,
            messages=[{"role": "user", "content": message_complet}],
        )
        return reponse.choices[0].message.content

    elif modele_ia.provider == Provider.MOCK:
        # Mock : retourne un texte factice / Mock: return dummy text
        return f"[MOCK] Reformulation de : {message_complet[:200]}..."

    else:
        raise ValueError(f"Provider '{modele_ia.provider}' non supporte pour la reformulation")


@shared_task(bind=True)
def restituer_debat_task(self, entity_id, analyseur_id):
    """
    Tache Celery : genere une restitution IA du debat pour une ExtractedEntity.
    Assemble le prompt + extraction + commentaires + reformulation, appelle le LLM,
    et stocke le resultat dans entity.texte_restitution_ia.
    / Celery task: generates an AI restitution of the debate for an ExtractedEntity.
    Assembles prompt + extraction + comments + reformulation, calls LLM,
    and stores the result in entity.texte_restitution_ia.
    """
    from core.models import Configuration
    from hypostasis_extractor.models import (
        AnalyseurSyntaxique, CommentaireExtraction, ExtractedEntity, PromptPiece,
    )

    debut_traitement = time.time()

    # Charger l'entite — si introuvable, rien a faire
    # / Load entity — if not found, nothing to do
    try:
        entite = ExtractedEntity.objects.get(pk=entity_id)
    except ExtractedEntity.DoesNotExist:
        logger.error("restituer_debat_task: entity_id=%s introuvable", entity_id)
        return

    # Charger l'analyseur — si introuvable, reset l'entite et sortir
    # / Load analyzer — if not found, reset entity and exit
    try:
        analyseur = AnalyseurSyntaxique.objects.get(pk=analyseur_id)
    except AnalyseurSyntaxique.DoesNotExist:
        logger.error("restituer_debat_task: analyseur_id=%s introuvable", analyseur_id)
        entite.restitution_ia_en_cours = False
        entite.restitution_ia_erreur = f"Analyseur introuvable (id={analyseur_id})"
        entite.save(update_fields=["restitution_ia_en_cours", "restitution_ia_erreur"])
        return

    try:
        # Recuperer le modele IA actif / Get active AI model
        configuration = Configuration.get_solo()
        modele_ia = configuration.ai_model
        if not modele_ia:
            raise ValueError("Aucun modele IA selectionne dans la configuration")

        # Construire le prompt depuis les pieces de l'analyseur
        # / Build prompt from analyzer pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        texte_prompt = "\n".join(piece.content for piece in pieces_ordonnees)

        if not texte_prompt.strip():
            raise ValueError(f"L'analyseur '{analyseur.name}' n'a aucune piece de prompt")

        # Texte source : l'extraction / Source text: the extraction
        texte_extraction = entite.extraction_text
        if not texte_extraction.strip():
            raise ValueError("Le texte de l'extraction est vide")

        # Commentaires du debat / Debate comments
        tous_les_commentaires = CommentaireExtraction.objects.filter(entity=entite)
        lignes_commentaires = []
        for commentaire in tous_les_commentaires:
            lignes_commentaires.append(f"{commentaire.prenom}: {commentaire.commentaire}")
        texte_commentaires = "\n".join(lignes_commentaires)

        # Reformulation existante si disponible / Existing reformulation if available
        texte_reformulation = entite.texte_reformule or ""

        # Assemblage du message complet / Full message assembly
        message_complet = texte_prompt
        message_complet += f"\n\n=== EXTRACTION SOURCE ===\n{texte_extraction}"
        if texte_commentaires:
            message_complet += f"\n\n=== COMMENTAIRES DU DEBAT ===\n{texte_commentaires}"
        if texte_reformulation:
            message_complet += f"\n\n=== REFORMULATION ===\n{texte_reformulation}"

        logger.info(
            "restituer_debat_task: entity=%s analyseur=%s model=%s msg_len=%d",
            entity_id, analyseur.name, modele_ia.model_name, len(message_complet),
        )

        # Appel au LLM / Call LLM
        texte_restitution = _appeler_llm_reformulation(modele_ia, message_complet)

        if not texte_restitution or not texte_restitution.strip():
            raise ValueError("Le LLM a retourne une reponse vide")

        # Succes : stocker le resultat et remettre l'entite en etat stable
        # / Success: store result and reset entity to stable state
        entite.texte_restitution_ia = texte_restitution.strip()
        entite.restitution_ia_en_cours = False
        entite.restitution_ia_erreur = ""
        entite.save(update_fields=[
            "texte_restitution_ia",
            "restitution_ia_en_cours", "restitution_ia_erreur",
        ])

        duree = time.time() - debut_traitement
        logger.info(
            "restituer_debat_task: termine entity=%s en %.1fs — %d chars",
            entity_id, duree, len(texte_restitution),
        )

    except Exception as erreur_restitution:
        # Erreur : remettre l'entite en etat stable + stocker le message d'erreur
        # / Error: reset entity to stable state + store error message
        message_erreur = str(erreur_restitution)[:500]
        logger.error(
            "restituer_debat_task: erreur entity=%s — %s",
            entity_id, message_erreur, exc_info=True,
        )
        entite.restitution_ia_en_cours = False
        entite.restitution_ia_erreur = message_erreur
        entite.save(update_fields=["restitution_ia_en_cours", "restitution_ia_erreur"])


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
