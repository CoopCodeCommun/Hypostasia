"""
Taches Celery pour le traitement asynchrone (audio + analyse textuelle).
/ Celery tasks for asynchronous processing (audio + text analysis).
"""

import hashlib
import logging
import os
import re
import time

from celery import shared_task

logger = logging.getLogger(__name__)


def notifier_tache_terminee(user_pk, tache_id, tache_type, status):
    """
    Push au client une notification de fin de tache via le NotificationConsumer.
    Appele uniquement a la fin d'une tache Celery (analyse / synthese / transcription).
    Format unifie : {tache_id, tache_type, status} pousse au group user_<pk>.
    / Push a task-end notification via NotificationConsumer.
    Called only at the end of a Celery task.

    Args:
        user_pk : pk du proprietaire de la tache
        tache_id : pk du job (ExtractionJob ou TranscriptionJob)
        tache_type : "analyse" | "synthese" | "transcription"
        status : "completed" | "error"
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    couche_channels = get_channel_layer()
    if couche_channels is None:
        logger.debug("notifier_tache_terminee: channel layer non configure, skip")
        return

    async_to_sync(couche_channels.group_send)(
        f"user_{user_pk}",
        {
            "type": "tache_terminee",  # nom de la methode handler du consumer
            "tache_id": tache_id,
            "tache_type": tache_type,
            "status": status,
        },
    )


def _destinataires_de_notification(page):
    """
    Les destinataires d'une notification de fin de tache sur une note :
    son owner PLUS les proprietaires des carnets qui la contiennent,
    dedoublonnes (SPEC-corpus § 11, phase D).
    / Notification recipients: the note's owner PLUS the owners of the
    notebooks containing it, deduplicated.

    LOCALISATION : front/tasks.py

    Avant la phase D, seul page.owner (ou page.dossier.owner) etait
    notifie : le second carnet d'une note n'apprenait jamais qu'une
    synthese avait tourne.
    / Before phase D, only one owner was notified.

    :return: liste de pks d'utilisateurs ; [None] si aucun destinataire,
             pour conserver le comportement d'appel existant.
             / list of user pks; [None] when nobody, preserving the
             existing call behaviour.
    """
    pks_destinataires = set()
    if page.owner_id is not None:
        pks_destinataires.add(page.owner_id)

    pks_proprietaires_de_carnets = page.appartenances_dossiers.filter(
        dossier__owner__isnull=False,
    ).values_list("dossier__owner_id", flat=True)
    pks_destinataires.update(pks_proprietaires_de_carnets)

    if not pks_destinataires:
        return [None]
    return sorted(pks_destinataires)


# ---------------------------------------------------------------------------
# Sous-classe d'Annotator pour injecter un callback WebSocket par chunk.
# Couple a langextract v1.1.1 — annotation.py._annotate_documents_single_pass.
# / Annotator subclass to inject a WebSocket callback per chunk.
# / Coupled to langextract v1.1.1 — annotation.py._annotate_documents_single_pass.
# ---------------------------------------------------------------------------

import collections
from collections import defaultdict
from typing import Iterable, Iterator



def _recuperer_extractions_json_corrompu(
    texte_sortie_llm, resolver, format_handler, numero_chunk, debug, **kwargs
):
    """
    Tente de recuperer les extractions valides d'un JSON LLM corrompu.
    Cas typique : boucle de repetition Gemini qui produit un JSON tronque.
    Strategie : trouver le dernier objet JSON complet et re-parser.
    / Attempts to recover valid extractions from corrupted LLM JSON.
    / Typical case: Gemini repetition loop producing truncated JSON.
    / Strategy: find last complete JSON object and re-parse.
    """
    import json as json_stdlib

    logger.warning(
        "  [chunk %d] tentative de recuperation partielle du JSON corrompu (%d chars)",
        numero_chunk, len(texte_sortie_llm),
    )

    # Retirer les fences si presentes / Strip fences if present
    texte_nettoye = texte_sortie_llm.strip()
    if texte_nettoye.startswith("```"):
        lignes = texte_nettoye.split("\n")
        lignes = lignes[1:]
        if lignes and lignes[-1].strip() == "```":
            lignes = lignes[:-1]
        texte_nettoye = "\n".join(lignes).strip()

    # Strategie : trouver le tableau "extractions" dans le JSON (potentiellement tronque)
    # et en extraire les objets individuels complets.
    # / Strategy: find the "extractions" array in the JSON (potentially truncated)
    # / and extract complete individual objects from it.

    # Etape 1 : localiser le debut du tableau "extractions": [
    # / Step 1: locate the start of the "extractions": [ array
    position_tableau = texte_nettoye.find('"extractions"')
    if position_tableau == -1:
        # Pas de wrapper — chercher directement un tableau JSON au debut
        # / No wrapper — look for a direct JSON array at the start
        position_tableau = texte_nettoye.find('[')
    else:
        position_tableau = texte_nettoye.find('[', position_tableau)

    if position_tableau == -1:
        logger.warning(
            "  [chunk %d] recuperation partielle echouee : pas de tableau JSON trouve",
            numero_chunk,
        )
        return []

    # Etape 2 : extraire les objets {...} complets dans le tableau
    # On demarre apres le '[' du tableau d'extractions.
    # / Step 2: extract complete {...} objects from the array
    # / Start after the '[' of the extractions array.
    texte_tableau = texte_nettoye[position_tableau + 1:]
    objets_extraits = []
    profondeur = 0
    debut_objet = -1

    for position, caractere in enumerate(texte_tableau):
        if caractere == '{':
            if profondeur == 0:
                debut_objet = position
            profondeur += 1
        elif caractere == '}':
            profondeur -= 1
            if profondeur == 0 and debut_objet >= 0:
                fragment_json = texte_tableau[debut_objet:position + 1]
                try:
                    objet_parse = json_stdlib.loads(fragment_json)
                    objets_extraits.append(objet_parse)
                except json_stdlib.JSONDecodeError:
                    # Objet JSON incomplet ou corrompu — on le saute
                    # / Incomplete or corrupted JSON object — skip it
                    pass
                debut_objet = -1

    if not objets_extraits:
        logger.warning(
            "  [chunk %d] recuperation partielle echouee : aucun objet JSON valide",
            numero_chunk,
        )
        return []

    # Nettoyer les objets : forcer extraction_text en string si c'est une liste/dict.
    # Gemini renvoie parfois extraction_text comme liste ou objet,
    # ce qui fait crasher LangExtract avec ValueError.
    # / Clean objects: force extraction_text to string if it's a list/dict.
    # / Gemini sometimes returns extraction_text as list or object,
    # / which crashes LangExtract with ValueError.
    for objet in objets_extraits:
        if "extraction_text" in objet and not isinstance(objet["extraction_text"], (str, int, float)):
            valeur_brute = objet["extraction_text"]
            if isinstance(valeur_brute, list):
                objet["extraction_text"] = " ".join(str(item) for item in valeur_brute)
            else:
                objet["extraction_text"] = str(valeur_brute)
            logger.warning(
                "  [chunk %d] extraction_text force en string (etait %s)",
                numero_chunk, type(valeur_brute).__name__,
            )

    # Re-construire le JSON wrappé et le repasser au resolver
    # / Rebuild wrapped JSON and re-pass to resolver
    json_reconstruit = json_stdlib.dumps({"extractions": objets_extraits})
    try:
        extractions_recuperees = resolver.resolve(
            json_reconstruit, debug=debug, **kwargs
        )
        logger.info(
            "  [chunk %d] recuperation partielle reussie : %d/%d extraction(s) sauvees",
            numero_chunk, len(extractions_recuperees), len(objets_extraits),
        )
        return extractions_recuperees
    except Exception as erreur_recuperation:
        logger.warning(
            "  [chunk %d] recuperation partielle echouee au resolve : %s",
            numero_chunk, erreur_recuperation,
        )
        return []


def _creer_annotateur_avec_progression(
    modele_llm,
    prompt_template,
    format_handler,
    callback_par_chunk=None,
):
    """
    Cree un Annotator dont la boucle interne appelle callback_par_chunk
    apres chaque cycle resolve() + align() d'un chunk.
    Copie de annotation.py._annotate_documents_single_pass (langextract v1.1.1)
    avec injection du callback apres l'accumulation des extractions alignees.
    / Creates an Annotator whose inner loop calls callback_par_chunk
    / after each resolve() + align() cycle for a chunk.
    / Copy of annotation.py._annotate_documents_single_pass (langextract v1.1.1)
    / with callback injection after aligned extraction accumulation.
    """
    from langextract import annotation as annotation_lx
    from langextract import chunking as chunking_lx
    from langextract import progress as progress_lx
    from langextract import resolver as resolver_lx
    from langextract.core import data as data_lx
    from langextract.core import exceptions as exceptions_lx

    class AnnotateurAvecProgression(annotation_lx.Annotator):
        """
        Sous-classe d'Annotator qui injecte un callback apres chaque chunk.
        IMPORTANT : couple a langextract v1.1.1 — si la lib evolue, cette methode
        doit etre mise a jour en consequence.
        / Annotator subclass that injects a callback after each chunk.
        / IMPORTANT: coupled to langextract v1.1.1 — if the lib evolves, this method
        / must be updated accordingly.
        """

        def _annotate_documents_single_pass(
            self,
            documents,
            resolver,
            max_char_buffer,
            batch_length,
            debug,
            show_progress=True,
            tokenizer=None,
            **kwargs,
        ):
            """
            Copie de Annotator._annotate_documents_single_pass (annotation.py:278-426)
            avec injection de callback_par_chunk apres chaque chunk traite.
            / Copy of Annotator._annotate_documents_single_pass (annotation.py:278-426)
            / with callback_par_chunk injection after each processed chunk.
            """
            doc_order = []
            doc_text_by_id = {}
            per_doc = collections.defaultdict(list)
            next_emit_idx = 0

            def _capture_docs(src):
                for document in src:
                    document_id = document.document_id
                    if document_id in doc_text_by_id:
                        raise exceptions_lx.InvalidDocumentError(
                            f"Duplicate document_id: {document_id}"
                        )
                    doc_order.append(document_id)
                    doc_text_by_id[document_id] = document.text or ""
                    yield document

            def _emit_docs_iter(keep_last_doc):
                nonlocal next_emit_idx
                limit = max(0, len(doc_order) - 1) if keep_last_doc else len(doc_order)
                while next_emit_idx < limit:
                    document_id = doc_order[next_emit_idx]
                    yield data_lx.AnnotatedDocument(
                        document_id=document_id,
                        extractions=per_doc.get(document_id, []),
                        text=doc_text_by_id.get(document_id, ""),
                    )
                    per_doc.pop(document_id, None)
                    doc_text_by_id.pop(document_id, None)
                    next_emit_idx += 1

            chunk_iter = annotation_lx._document_chunk_iterator(
                _capture_docs(documents), max_char_buffer, tokenizer=tokenizer
            )
            batches = chunking_lx.make_batches_of_textchunk(chunk_iter, batch_length)

            model_info = progress_lx.get_model_info(self._language_model)
            batch_iter = progress_lx.create_extraction_progress_bar(
                batches, model_info=model_info, disable=not show_progress
            )

            caracteres_traites = 0
            numero_chunk = 0

            try:
                for batch in batch_iter:
                    if not batch:
                        continue

                    # Construire le prompt pour chaque chunk du batch.
                    # Le prompt = description + exemples few-shot + texte du chunk.
                    # / Build prompt for each chunk in the batch.
                    # / Prompt = description + few-shot examples + chunk text.
                    prompts = [
                        self._prompt_generator.render(
                            question=text_chunk.chunk_text,
                            additional_context=text_chunk.additional_context,
                        )
                        for text_chunk in batch
                    ]

                    # Envoyer les prompts au LLM. Avec batch_length > 1,
                    # les providers Gemini/OpenAI parallelisent via ThreadPoolExecutor.
                    # Le LLM repond avec du YAML/JSON contenant les extractions.
                    # / Send prompts to the LLM. With batch_length > 1,
                    # / Gemini/OpenAI providers parallelize via ThreadPoolExecutor.
                    # / The LLM responds with YAML/JSON containing extractions.
                    logger.debug(
                        "  [langextract] envoi batch de %d chunk(s) au LLM",
                        len(batch),
                    )
                    # Log des kwargs passes a infer (debug max_output_tokens)
                    # / Log kwargs passed to infer (debug max_output_tokens)
                    logger.info(
                        "  [langextract] kwargs infer: %s",
                        {k: v for k, v in kwargs.items() if k != 'debug'},
                    )
                    debut_appel_llm = time.time()
                    outputs = self._language_model.infer(
                        batch_prompts=prompts, **kwargs
                    )
                    if not isinstance(outputs, list):
                        outputs = list(outputs)
                    duree_appel_llm = time.time() - debut_appel_llm
                    logger.debug(
                        "  [langextract] reponse LLM recue en %.1fs pour %d chunk(s)",
                        duree_appel_llm, len(batch),
                    )

                    for text_chunk, scored_outputs in zip(batch, outputs):
                        numero_chunk += 1
                        if not isinstance(scored_outputs, list):
                            scored_outputs = list(scored_outputs)
                        if not scored_outputs:
                            raise exceptions_lx.InferenceOutputError(
                                "No scored outputs from language model."
                            )

                        # Taille du chunk, position et temps de reponse LLM
                        # / Chunk size, position and LLM response time
                        temps_fin_llm = time.time()
                        taille_chunk = len(text_chunk.chunk_text)
                        position_debut_chunk = (
                            text_chunk.char_interval.start_pos
                            if text_chunk.char_interval else 0
                        )
                        taille_reponse_llm = len(scored_outputs[0].output)
                        duree_llm_secondes = duree_appel_llm
                        logger.info(
                            "  [chunk %d] pos=%d len=%d — reponse LLM: %d chars en %.1fs",
                            numero_chunk, position_debut_chunk,
                            taille_chunk, taille_reponse_llm,
                            duree_llm_secondes,
                        )
                        # Collecter les warnings pour ce chunk (envoyes au callback → WS)
                        # / Collect warnings for this chunk (sent to callback → WS)
                        warnings_chunk = []
                        if duree_llm_secondes > 60:
                            logger.warning(
                                "  [chunk %d] reponse LLM anormalement lente: %.0fs",
                                numero_chunk, duree_llm_secondes,
                            )
                            warnings_chunk.append(
                                f"Réponse LLM très lente ({int(duree_llm_secondes)}s)"
                            )

                        # Etape 1 : Resolver — parse le YAML/JSON brut du LLM
                        # en objets Extraction structurés.
                        # Si le JSON est tronque et suppress_parse_errors=True,
                        # le resolver retourne une liste vide au lieu de crasher.
                        # / Step 1: Resolver — parse raw LLM YAML/JSON
                        # / into structured Extraction objects.
                        # / If JSON is truncated and suppress_parse_errors=True,
                        # / resolver returns empty list instead of crashing.

                        # Log du debut de la reponse LLM pour debug du format
                        # / Log start of LLM response for format debugging
                        texte_sortie_brut = scored_outputs[0].output
                        logger.info(
                            "  [chunk %d] debut reponse LLM (300 premiers chars): %s",
                            numero_chunk, texte_sortie_brut[:300],
                        )

                        # Correction : certains LLM renvoient un tableau JSON brut
                        # au lieu de {"extractions": [...]}.
                        # On wrappe automatiquement si c'est le cas.
                        # / Fix: some LLMs return a bare JSON array
                        # / instead of {"extractions": [...]}.
                        # / We auto-wrap if that's the case.
                        texte_sortie_llm = scored_outputs[0].output
                        texte_sortie_llm_stripped = texte_sortie_llm.strip()

                        # Retirer les fences ```json ... ``` si presentes
                        # / Remove ```json ... ``` fences if present
                        if texte_sortie_llm_stripped.startswith("```"):
                            lignes_sortie = texte_sortie_llm_stripped.split("\n")
                            lignes_sortie = lignes_sortie[1:]  # enlever ```json
                            if lignes_sortie and lignes_sortie[-1].strip() == "```":
                                lignes_sortie = lignes_sortie[:-1]
                            texte_sortie_llm_stripped = "\n".join(lignes_sortie).strip()

                        # Si la sortie est un tableau JSON nu, le wrapper
                        # dans {"extractions": [...]} pour que le Resolver l'accepte.
                        # / If output is a bare JSON array, wrap it
                        # / in {"extractions": [...]} so the Resolver accepts it.
                        if texte_sortie_llm_stripped.startswith("["):
                            import json as json_stdlib
                            try:
                                tableau_extractions_brut = json_stdlib.loads(
                                    texte_sortie_llm_stripped
                                )
                                texte_sortie_llm = json_stdlib.dumps(
                                    {"extractions": tableau_extractions_brut}
                                )
                                logger.info(
                                    "  [chunk %d] reponse LLM wrappee dans"
                                    " {'extractions': [...]}",
                                    numero_chunk,
                                )
                            except json_stdlib.JSONDecodeError:
                                # JSON tronque — laisser le resolver gerer
                                # / Truncated JSON — let the resolver handle it
                                pass

                        try:
                            resolved_extractions = resolver.resolve(
                                texte_sortie_llm, debug=debug, **kwargs
                            )
                        except (ValueError, TypeError) as erreur_resolve:
                            # Le LLM a renvoye un format inattendu (liste au lieu de string, etc.)
                            # On passe a la recuperation partielle au lieu de crasher le job.
                            # / LLM returned unexpected format (list instead of string, etc.)
                            # / Fall through to partial recovery instead of crashing the job.
                            logger.warning(
                                "  [chunk %d] resolver.resolve() a echoue: %s\n"
                                "  JSON complet (1000 premiers chars): %s",
                                numero_chunk, erreur_resolve,
                                texte_sortie_llm[:1000],
                            )
                            resolved_extractions = []

                        # Recuperation partielle si le resolve a echoue (0 extraction)
                        # mais que la reponse LLM contient du JSON parsable.
                        # Cas typique : boucle de repetition Gemini qui corrompt la fin du JSON,
                        # ou extraction_text non-string qui fait crasher le resolver.
                        # / Partial recovery if resolve failed (0 extractions)
                        # / but the LLM response contains parseable JSON.
                        # / Typical case: Gemini repetition loop corrupting end of JSON,
                        # / or non-string extraction_text crashing the resolver.
                        if not resolved_extractions and taille_reponse_llm > 200:
                            resolved_extractions = _recuperer_extractions_json_corrompu(
                                texte_sortie_llm, resolver, format_handler,
                                numero_chunk, debug, **kwargs,
                            )
                            if resolved_extractions:
                                warnings_chunk.append(
                                    f"Réponse LLM corrompue — {len(resolved_extractions)} extraction(s) récupérée(s)"
                                )
                            else:
                                warnings_chunk.append(
                                    "Réponse LLM corrompue — aucune extraction récupérable"
                                )

                        nombre_extractions_resolues = len(resolved_extractions)
                        logger.info(
                            "  [chunk %d] resolve → %d extraction(s) parsees depuis le YAML/JSON",
                            numero_chunk, nombre_extractions_resolues,
                        )

                        token_offset = (
                            text_chunk.token_interval.start_index
                            if text_chunk.token_interval
                            else 0
                        )
                        char_offset = (
                            text_chunk.char_interval.start_pos
                            if text_chunk.char_interval
                            else 0
                        )

                        # Etape 2 : Aligner — repositionne chaque extraction
                        # dans le texte original (pas relatif au chunk).
                        # Utilise le fuzzy matching si le texte exact n'est pas trouve.
                        # / Step 2: Align — repositions each extraction
                        # / in the original text (not relative to the chunk).
                        # / Uses fuzzy matching if exact text is not found.
                        aligned_extractions = resolver.align(
                            resolved_extractions,
                            text_chunk.chunk_text,
                            token_offset,
                            char_offset,
                            tokenizer_inst=tokenizer,
                            **kwargs,
                        )

                        # Materialiser le generateur pour pouvoir l'utiliser
                        # a la fois dans per_doc et dans le callback.
                        # / Materialize the generator to use it in both
                        # / per_doc and the callback.
                        liste_extractions_alignees = list(aligned_extractions)
                        nombre_extractions_alignees = len(liste_extractions_alignees)

                        if nombre_extractions_alignees != nombre_extractions_resolues:
                            logger.info(
                                "  [chunk %d] align → %d/%d (certaines n'ont pas pu "
                                "etre positionnees dans le texte)",
                                numero_chunk, nombre_extractions_alignees,
                                nombre_extractions_resolues,
                            )
                        else:
                            logger.info(
                                "  [chunk %d] align → %d extraction(s) positionnees OK",
                                numero_chunk, nombre_extractions_alignees,
                            )

                        for extraction in liste_extractions_alignees:
                            per_doc[text_chunk.document_id].append(extraction)

                        if text_chunk.char_interval is not None:
                            caracteres_traites += (
                                text_chunk.char_interval.end_pos
                                - text_chunk.char_interval.start_pos
                            )

                        # --- INJECTION DU CALLBACK ---
                        # Appelle le callback de la tache Celery pour creer
                        # les entites en DB et envoyer les notifications WS.
                        # / --- CALLBACK INJECTION ---
                        # / Calls the Celery task callback to create
                        # / entities in DB and send WS notifications.
                        if callback_par_chunk:
                            callback_par_chunk(
                                extractions_du_chunk=liste_extractions_alignees,
                                caracteres_traites=caracteres_traites,
                                warnings_chunk=warnings_chunk,
                            )

                    yield from _emit_docs_iter(keep_last_doc=True)

            finally:
                batch_iter.close()

            logger.info(
                "  [langextract] pipeline termine — %d chunk(s), %d chars traites",
                numero_chunk, caracteres_traites,
            )
            yield from _emit_docs_iter(keep_last_doc=False)

    return AnnotateurAvecProgression(
        language_model=modele_llm,
        prompt_template=prompt_template,
        format_handler=format_handler,
    )


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
    job_transcription.save(
        update_fields=["status", "celery_task_id", "updated_at"],
    )

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
        # (construire_html_diarise accepte un dict ou une list)
        # / Build colored HTML and plain text
        # (construire_html_diarise accepts a dict or a list)
        html_diarise, texte_brut = construire_html_diarise(segments_transcrits)

        # Calculer le hash du contenu / Compute content hash
        hash_contenu = hashlib.sha256(texte_brut.encode("utf-8")).hexdigest()

        # Stocker le dict complet (model + text + segments) dans transcription_raw
        # / Store the full dict (model + text + segments) in transcription_raw
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

        # Notifier le navigateur que la tache est terminee (succes)
        # / Notify the browser that the task is complete (success)
        notifier_tache_terminee(
            user_pk=page_associee.owner.pk if page_associee.owner else None,
            tache_id=job_transcription.pk,
            tache_type="transcription",
            status="completed",
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

        # Notifier le navigateur que la tache est terminee (erreur)
        # / Notify the browser that the task is complete (error)
        notifier_tache_terminee(
            user_pk=page_associee.owner.pk if page_associee.owner else None,
            tache_id=job_transcription.pk,
            tache_type="transcription",
            status="error",
        )

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


def _extractions_pour_la_synthese(page):
    """
    Les extractions qu'une synthese a le droit de citer sur cette note :
    TOUS ses jobs termines, non masquees (relecture D, B1 — le
    « dernier job » se faisait evincer par une extraction manuelle).
    / The extractions a synthesis may cite on this note: every completed
    job, not hidden.

    LOCALISATION : front/tasks.py

    UNE SEULE DEFINITION pour trois usages : le bloc HYPOSTASES du
    prompt, le perimetre passe a indexer_les_citations() (§ 4.4) et le
    perimetre FIGE sur la SyntheseDirigee (§ 8). Le filtre « citable »
    vit dans core/services/synthese.py ; ici on n'ajoute que l'ordre et
    les prefetch du prompt. Les extractions deja commentees (debattues)
    passent en tete.
    / One definition for the prompt block, the citation scope and the
    frozen § 8 scope; commented (debated) extractions first.
    """
    from django.db.models import Case, Value, When

    from core.services.synthese import extractions_citables_de_la_note

    return extractions_citables_de_la_note(
        page,
    ).prefetch_related("commentaires__user").order_by(
        Case(
            When(statut_debat="commente", then=Value(0)),
            default=Value(1),
        ),
        "pk",
    )


def _construire_prompt_synthese(page, dernier_job_analyse, analyseur_synthese):
    """
    Construit le prompt utilisateur pour la synthese deliberative.
    Les sections injectees dependent des bool de l'analyseur :
    - inclure_texte_original → bloc TEXTE ORIGINAL
    - inclure_extractions → bloc HYPOSTASES ET DEBAT (extractions + commentaires)
    Au moins l'un des deux doit etre actif (validation faite en amont).
    / Builds the user prompt for deliberative synthesis.
    Sections depend on the analyzer's bool flags.
    At least one of the two must be active (validation done upstream).

    SPEC-synthese phase C : chaque hypostase expose son identifiant
    (« Identifiant : ext:N ») pour que le modele produise les marqueurs
    [[ext:N]], et la consigne exige la ligne finale CITATIONS_USED —
    l'anti-troncature de l'addendum n°2.
    / Phase C: each extraction exposes its id for [[ext:N]] markers, and
    the final CITATIONS_USED control line is required.
    """
    sections_du_prompt = []

    # Bloc TEXTE ORIGINAL — inclus si l'analyseur le demande
    # / TEXT block — included if analyzer requests it
    if analyseur_synthese.inclure_texte_original:
        texte_original = page.text_readability or ""
        sections_du_prompt.append(f"=== TEXTE ORIGINAL ===\n{texte_original}")

    # Bloc HYPOSTASES ET DEBAT — extractions + commentaires si l'analyseur le demande
    # ET si un job d'analyse complet existe. Si pas de job, le bloc est omis silencieusement
    # (cas du previsualiser_synthese pour estimation avant qu'une analyse n'ait ete lancee).
    # / HYPOSTASES block — extractions + comments if analyzer requests it AND analysis job exists.
    # / If no job, block is omitted silently (preview synthesis case).
    if analyseur_synthese.inclure_extractions and dernier_job_analyse is not None:
        # Toutes les extractions visibles de la note (tous jobs termines
        # — analyse, manuelles, selection). / Every visible extraction.
        entites_du_job = _extractions_pour_la_synthese(page)

        # Construire les blocs pour chaque entite / Build blocks for each entity
        blocs_entites = []
        for entite in entites_du_job:
            # Resume IA depuis le JSONField attributes / AI summary from JSONField attributes
            attributs = entite.attributes or {}
            resume_ia = attributs.get("resume", "")

            # Statut formate en majuscules / Status formatted in uppercase
            statut_affiche = (entite.statut_debat or "nouveau").upper()

            # Hypostase (classe d'extraction) / Hypostasis (extraction class)
            classe_hypostase = entite.extraction_class or "hypostase"

            # Texte de la citation / Citation text
            texte_citation = entite.extraction_text or ""

            # Resume a afficher / Summary to display
            resume_affiche = resume_ia or texte_citation[:80]

            # Commentaires de chaque participant au debat
            # / Each participant's debate comments
            lignes_commentaires = []
            for commentaire in entite.commentaires.all():
                nom_auteur = commentaire.user.username if commentaire.user else "Anonyme"
                lignes_commentaires.append(f'  - {nom_auteur} : "{commentaire.commentaire}"')

            # Assemblage du bloc / Block assembly
            bloc = f'**[{statut_affiche}] {classe_hypostase} — {resume_affiche}**\n'
            # L'identifiant expose au modele pour le marqueur [[ext:N]]
            # (SPEC-synthese § 4.4). / The id exposed for [[ext:N]] markers.
            bloc += f'Identifiant : ext:{entite.pk}\n'
            bloc += f'Citation : "{texte_citation}"\n'
            if resume_ia:
                bloc += f'Résumé IA : "{resume_ia}"\n'
            if lignes_commentaires:
                bloc += "Commentaires :\n" + "\n".join(lignes_commentaires) + "\n"

            blocs_entites.append(bloc)

        blocs_formates = "\n\n".join(blocs_entites) if blocs_entites else "(aucune hypostase extraite)"
        sections_du_prompt.append(f"=== HYPOSTASES ET DEBAT ===\n{blocs_formates}")

    # Bloc CONSIGNE + FORMAT — toujours present
    # Format Markdown impose : on parse cote serveur via la lib `markdown`.
    # / INSTRUCTION + FORMAT block — always present.
    # / Markdown format imposed: parsed server-side via the `markdown` library.
    sections_du_prompt.append(
        "=== CONSIGNE ===\n"
        "Produis la synthèse délibérative de ce débat en intégrant les pondérations "
        "par statut définies dans tes instructions. Le texte produit doit être "
        "autonome et lisible.\n\n"
        "=== FORMAT DE SORTIE ===\n"
        "Réponds UNIQUEMENT en Markdown propre :\n"
        "- `# Titre` pour le titre principal (un seul)\n"
        "- `## Section` pour les sous-parties (UNIQUEMENT ce niveau : "
        "jamais de `###` ni plus profond)\n"
        "- `**gras**` pour les concepts clés\n"
        "- `*italique*` pour les nuances\n"
        "- Paragraphes courts séparés par des lignes vides\n"
        "- `> citation` pour les citations directes du texte source\n"
        "- `-` pour les listes à puces (rare, seulement si vraiment liste)\n"
        "- Pas de blocs de code, pas de tableaux, pas de HTML brut\n"
        "- Ne précède PAS ta réponse par « Voici la synthèse » ou un préambule : "
        "commence directement par le titre ou le premier paragraphe."
    )

    # Bloc SOURCAGE — le contrat de citation (SPEC-synthese § 4.4) et la
    # ligne de controle anti-troncature (addendum n°2). La ligne est
    # TOUJOURS exigee : sans elle, impossible de distinguer une reponse
    # complete d'une reponse coupee en plein milieu.
    # / SOURCING block — citation contract and anti-truncation line. The
    # line is ALWAYS required.
    consignes_de_sourcage = []
    if analyseur_synthese.inclure_extractions and dernier_job_analyse is not None:
        consignes_de_sourcage.append(
            "Chaque affirmation tirée d'une hypostase se termine par le "
            "marqueur de sa source, accolé à la fin de la phrase : "
            "`[[ext:N]]` où N est le nombre donné par « Identifiant : "
            "ext:N ». Plusieurs sources = plusieurs marqueurs consécutifs "
            "(`[[ext:12]][[ext:15]]`). Ne cite JAMAIS un identifiant qui "
            "n'apparaît pas dans la section HYPOSTASES ET DEBAT. Jamais "
            "de marqueur dans un titre."
        )
    consignes_de_sourcage.append(
        "Termine IMPÉRATIVEMENT ta réponse par une DERNIÈRE ligne de "
        "contrôle, seule sur sa ligne :\n"
        "`CITATIONS_USED: ` suivi des identifiants cités séparés par des "
        "virgules (exemple : `CITATIONS_USED: 12, 15`), ou "
        "`CITATIONS_USED: aucune` si tu n'as rien cité. Une réponse sans "
        "cette ligne finale sera rejetée comme incomplète."
    )
    sections_du_prompt.append(
        "=== SOURÇAGE ===\n" + "\n\n".join(consignes_de_sourcage)
    )

    return "\n\n".join(sections_du_prompt)


class SyntheseTronqueeError(ValueError):
    """
    Levee quand la reponse du modele n'a pas la ligne finale
    CITATIONS_USED : la generation est arrivee incomplete (addendum n°2).
    Jamais une synthese tronquee enregistree comme un succes.
    / Raised when the CITATIONS_USED control line is missing: the
    generation arrived truncated; never stored as a success.
    """


# La ligne de controle, meme habillee par le modele : backticks, gras,
# soulignes — le prompt la montre entre backticks, un modele qui recopie
# ce format ne doit pas etre rejete (relecture C, B1).
# / The control line, even wrapped in backticks/bold by the model.
MOTIF_DE_LIGNE_CITATIONS_USED = re.compile(
    r"^[`*_\s]*CITATIONS_USED[`*_\s]*:\s*(.*?)[`*_\s]*$"
)


def _detacher_la_ligne_citations_used(texte_brut):
    """
    Controle anti-troncature (SPEC-synthese addendum n°2) : la reponse
    doit se terminer par la ligne `CITATIONS_USED: ...`. On la retire du
    texte (elle est un controle, pas un contenu) et on retourne les deux.
    / Anti-truncation check: the response must end with the
    CITATIONS_USED control line; it is detached from the text.

    LOCALISATION : front/tasks.py

    TOLERANCE DE FORME (relecture C, B1) : la ligne peut etre habillee
    (`...`, **...**) ou enfermee dans un bloc de code — on la cherche
    dans les 3 dernieres lignes non vides, et les clotures de bloc
    residuelles sont nettoyees. Le FOND reste strict : pas de ligne =
    generation tronquee = echec bruyant.
    / Form-tolerant (backticks, bold, code fence — last 3 non-empty
    lines); the substance stays strict.

    :return: (texte_sans_la_ligne, contenu_de_la_ligne)
    :raises SyntheseTronqueeError: si la ligne manque / if missing
    """
    lignes = texte_brut.rstrip().split("\n")
    indices_non_vides = [
        indice for indice, ligne in enumerate(lignes) if ligne.strip()
    ]

    for indice in reversed(indices_non_vides[-3:]):
        correspondance = MOTIF_DE_LIGNE_CITATIONS_USED.match(
            lignes[indice].strip()
        )
        if correspondance is None:
            continue
        contenu_de_la_ligne = correspondance.group(1).strip()
        lignes_restantes = lignes[:indice] + lignes[indice + 1:]
        # Nettoie les restes d'habillage en fin de texte : lignes vides
        # et clotures de bloc de code (```). / Strip leftover fences.
        while lignes_restantes and (
            not lignes_restantes[-1].strip()
            or set(lignes_restantes[-1].strip()) <= set("`")
        ):
            lignes_restantes.pop()
        texte_sans_la_ligne = "\n".join(lignes_restantes).rstrip() + "\n"
        return texte_sans_la_ligne, contenu_de_la_ligne

    raise SyntheseTronqueeError(
        "La synthèse est arrivée incomplète : la ligne de contrôle "
        "CITATIONS_USED manque à la fin de la réponse (génération "
        "tronquée). Rien n'a été enregistré — relancez la synthèse. "
        "/ Truncated generation: the CITATIONS_USED control line is "
        "missing; nothing was saved."
    )


# Ce que le rendu markdown d'une synthese a le droit de produire. Tout
# le reste est retire, et les liens sont limites aux protocoles surs :
# html.escape ne touche pas [texte](url), donc markdown reconstruit des
# <a> APRES l'echappement — sans allowlist, un modele (ou une note
# hostile qui l'influence) glisserait un javascript: dans un href rendu
# |safe (relecture C, B2).
# / Allowlist for the synthesis markdown rendering; markdown rebuilds
# <a> tags AFTER escaping, so hrefs must be protocol-filtered.
BALISES_HTML_AUTORISEES = [
    "p", "br", "h1", "h2", "h3", "strong", "em", "blockquote",
    "ul", "ol", "li", "a", "code", "pre", "hr",
]
ATTRIBUTS_HTML_AUTORISES = {"a": ["href", "title"]}
PROTOCOLES_AUTORISES = ["http", "https", "mailto"]


def _nettoyer_le_html_de_synthese(html_rendu):
    """
    Passe la sortie markdown dans bleach : allowlist de balises et de
    protocoles. Defense en profondeur derriere html.escape.
    / Sanitizes the markdown output with bleach (tag and protocol
    allowlist). Defense in depth behind html.escape.

    LOCALISATION : front/tasks.py
    """
    import bleach

    return bleach.clean(
        html_rendu,
        tags=BALISES_HTML_AUTORISEES,
        attributes=ATTRIBUTS_HTML_AUTORISES,
        protocols=PROTOCOLES_AUTORISES,
        strip=False,
    )


def _remplacer_les_marqueurs_par_des_renvois(texte_markdown):
    """
    Remplace chaque marqueur [[ext:N]] par un renvoi [1], [2]... par
    ordre de premiere apparition — pour le RENDU seulement : le numero
    n'est jamais persiste, le markdown garde les marqueurs (§ 4.4).
    / Replaces markers with [N] footnote-style references, for RENDERING
    only; the number is never stored.

    LOCALISATION : front/tasks.py
    """
    from core.services.synthese import MOTIF_DE_MARQUEUR

    numero_par_identifiant = {}

    def _en_renvoi(correspondance):
        identifiant = int(correspondance.group(1))
        if identifiant not in numero_par_identifiant:
            numero_par_identifiant[identifiant] = len(numero_par_identifiant) + 1
        return f"[{numero_par_identifiant[identifiant]}]"

    return MOTIF_DE_MARQUEUR.sub(_en_renvoi, texte_markdown)


@shared_task(bind=True)
def synthetiser_page_task(self, job_id):
    """
    Tache Celery : lance la synthese deliberative sur une Page.
    / Celery task: runs deliberative synthesis on a Page.

    LOCALISATION : front/tasks.py

    SPEC-synthese phase C — la synthese N'EST PLUS une version de page.

    FLUX :
    1. Construit le prompt (texte + hypostases avec identifiants + debat)
    2. Appelle le LLM ; la reponse DOIT finir par la ligne CITATIONS_USED
       (sinon : generation tronquee, echec bruyant, rien n'est enregistre)
    3. Cree une Page type_de_note=SYNTHESE — sans parent_page, sans
       numero de version
    4. indexer_les_citations() avec le PERIMETRE des extractions envoyees
       au modele : les marqueurs [[ext:N]] deviennent des SourceLink, les
       marqueurs hallucines sont retires ET signales dans raw_result
    5. Range la note dans le carnet d'origine de la demande
       (raw_result["dossier_id"]), sinon dans les carnets de la source
    6. Cree l'acte date : SyntheseDirigee au perimetre fige
    / The synthesis is a TYPED NOTEBOOK NOTE: markers become SourceLinks,
    truncated generations fail loudly, the scope is frozen.
    """
    from core.models import (
        Configuration, Dossier, Page, SyntheseDirigee, TypeDeNote,
    )
    from core.services.corpus import ranger_une_note_dans_un_carnet
    from core.services.synthese import indexer_les_citations
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from hypostasis_extractor.models import (
        AnalyseurSyntaxique, ExtractionJob, PromptPiece,
    )

    debut_traitement = time.time()

    # Charger le job / Load the job
    try:
        job_synthese = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error("synthetiser_page_task: job_id=%s introuvable", job_id)
        return

    try:
        # Marquer comme en cours / Mark as processing
        job_synthese.status = "processing"
        job_synthese.save(update_fields=["status"])

        page_source = job_synthese.page
        if not page_source:
            raise ValueError("Le job n'a pas de page associee")

        # Garde § 3.3 en profondeur : on ne synthetise JAMAIS une
        # synthese ni un wiki — sinon au troisieme tour l'article se cite
        # lui-meme. La vue refuse deja ; un job forge echoue aussi.
        # / § 3.3 depth guard: never synthesize a synthesis or a wiki.
        if page_source.type_de_note != TypeDeNote.NOTE:
            raise ValueError(
                "Cette page est déjà une synthèse (ou un wiki) : on ne "
                "synthétise pas une synthèse. Choisissez une note "
                "ordinaire. / A synthesis is never synthesized."
            )

        # Charger l'analyseur depuis raw_result / Load analyzer from raw_result
        analyseur_id = job_synthese.raw_result.get("analyseur_id")
        analyseur_synthese = AnalyseurSyntaxique.objects.get(pk=analyseur_id)

        # Recuperer le modele IA actif / Get active AI model
        configuration = Configuration.get_solo()
        modele_ia = configuration.ai_model
        if not modele_ia:
            raise ValueError("Aucun modele IA selectionne dans la configuration")

        # Construire le prompt systeme depuis les pieces de l'analyseur
        # / Build system prompt from analyzer pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur_synthese,
        ).order_by("order")
        prompt_systeme = "\n".join(piece.content for piece in pieces_ordonnees)

        if not prompt_systeme.strip():
            raise ValueError(f"L'analyseur '{analyseur_synthese.name}' n'a aucune piece de prompt")

        # Trouver le dernier job d'analyse complete (pas de synthese) —
        # la MEME definition que le perimetre des ecartees § 8 (service
        # partage, phase D). / The latest completed analysis job — same
        # definition as the § 8 scope (shared service).
        from core.services.synthese import dernier_job_d_analyse_de_la_note
        dernier_job_analyse = dernier_job_d_analyse_de_la_note(page_source)

        if not dernier_job_analyse:
            raise ValueError("Aucun job d'analyse termine pour cette page. Lancez d'abord une analyse.")

        # Le perimetre des citations = EXACTEMENT les extractions
        # envoyees au modele, FIGE AVANT l'appel (relecture C, I6) : une
        # extraction masquee PENDANT la generation resterait une citation
        # legitime — sinon l'affirmation resterait et sa preuve serait
        # denoncee comme hallucination. Parametre OBLIGATOIRE ensuite.
        # / The citation scope = exactly the extractions sent to the
        # model, snapshotted BEFORE the call. Mandatory parameter.
        identifiants_du_perimetre = set()
        if analyseur_synthese.inclure_extractions:
            identifiants_du_perimetre = set(
                _extractions_pour_la_synthese(page_source)
                .values_list("pk", flat=True)
            )

        # Construire le prompt utilisateur en respectant les bool de l'analyseur
        # / Build user prompt respecting the analyzer's bool flags
        prompt_utilisateur = _construire_prompt_synthese(
            page_source, dernier_job_analyse, analyseur_synthese,
        )

        # Assemblage message complet / Full message assembly
        message_complet = prompt_systeme + "\n\n" + prompt_utilisateur

        logger.info(
            "synthetiser_page_task: job=%s page=%s model=%s msg_len=%d",
            job_id, page_source.pk, modele_ia.model_name, len(message_complet),
        )

        # Appel au LLM via la couche unifiee / Call LLM via unified layer
        from core.llm_providers import appeler_llm
        texte_synthese = appeler_llm(modele_ia, message_complet)

        if not texte_synthese or not texte_synthese.strip():
            raise ValueError("Le LLM a retourne une reponse vide")

        # Controle anti-troncature (addendum n°2) : la ligne finale
        # CITATIONS_USED doit etre la — sinon la generation est arrivee
        # coupee et RIEN n'est enregistre. Echec bruyant, jamais une
        # synthese tronquee rangee comme un succes.
        # / Anti-truncation check: no control line = loud failure.
        texte_brut, citations_annoncees = _detacher_la_ligne_citations_used(
            texte_synthese.strip()
        )

        # Le demandeur et le carnet d'origine de la demande, poses par la
        # vue dans raw_result. Replis : l'owner de la source, ses carnets.
        # / The requester and origin notebook, set by the view.
        Utilisateur = get_user_model()
        demandeur = None
        identifiant_demandeur = job_synthese.raw_result.get("demandeur_id")
        if identifiant_demandeur:
            demandeur = Utilisateur.objects.filter(
                pk=identifiant_demandeur,
            ).first()
        if demandeur is None:
            demandeur = page_source.owner

        carnet_d_origine = None
        identifiant_carnet = job_synthese.raw_result.get("dossier_id")
        if identifiant_carnet:
            carnet_d_origine = Dossier.objects.filter(
                pk=identifiant_carnet,
            ).first()

        page_racine = page_source.page_racine

        # Tout ou rien : la page, ses liens, ses appartenances et l'acte
        # date naissent ensemble — jamais une demi-synthese en base.
        # / All-or-nothing: never a half-recorded synthesis.
        with transaction.atomic():
            # La synthese est une NOTE TYPEE du carnet (§ 2.1) : pas de
            # parent_page, pas de numero de version. PAS de dossier= :
            # la FK n'est ecrite que par le service de rangement.
            # Le titre porte la date : trois syntheses de la meme note ne
            # doivent pas etre indistinguables dans la liste du carnet
            # (relecture C, M9). / Dated title: three syntheses of the
            # same note must be tellable apart.
            from django.utils import timezone as django_timezone
            date_du_jour = django_timezone.localdate().strftime("%d/%m/%Y")
            titre_de_synthese = (
                f"Synthèse du {date_du_jour} — {page_racine.title or ''}"[:500]
            )
            page_synthese = Page.objects.create(
                type_de_note=TypeDeNote.SYNTHESE,
                version_label=analyseur_synthese.name,
                source_type=page_racine.source_type,
                url=None,
                title=titre_de_synthese,
                html_original="",
                html_readability="",
                text_readability=texte_brut,
                content_hash="",
                owner=demandeur,
            )

            # Le markdown est la verite, les SourceLink son index : les
            # marqueurs legitimes deviennent des liens, les hallucines
            # sont RETIRES du texte et SIGNALES (§ 4.4).
            # / Markers become links; hallucinated ones are stripped and
            # reported.
            bilan_d_indexation = indexer_les_citations(
                page_synthese, texte_brut, identifiants_du_perimetre,
            )
            texte_definitif = bilan_d_indexation["texte_nettoye"]

            # Rendu HTML : les marqueurs deviennent des renvois [N] (le
            # numero ne se persiste jamais, § 4.4), puis echappement du
            # HTML brut (anti-XSS) AVANT le parser markdown : la syntaxe
            # markdown ne contient pas de < > & donc l'echappement la
            # preserve, mais tout <script> injecte par le LLM est
            # neutralise en &lt;script&gt;.
            # / [N] references for display, HTML-escape THEN markdown.
            import html
            import markdown
            texte_pour_le_rendu = _remplacer_les_marqueurs_par_des_renvois(
                texte_definitif
            )
            html_synthese = _nettoyer_le_html_de_synthese(
                markdown.markdown(
                    html.escape(texte_pour_le_rendu),
                    extensions=["extra", "nl2br"],
                )
            )

            page_synthese.text_readability = texte_definitif
            page_synthese.html_original = html_synthese
            page_synthese.html_readability = html_synthese
            page_synthese.content_hash = hashlib.sha256(
                texte_definitif.encode("utf-8")
            ).hexdigest()
            page_synthese.save(update_fields=[
                "text_readability", "html_original", "html_readability",
                "content_hash",
            ])

            # Rangement (§ 2.1) : le carnet d'origine de la demande ;
            # a defaut, les carnets de la note source (repli documente
            # en addendum), et la FK pour une racine anormale.
            # / File in the requesting notebook, else the source's ones.
            if carnet_d_origine is not None:
                ranger_une_note_dans_un_carnet(
                    page_synthese, carnet_d_origine, demandeur,
                )
            else:
                for appartenance_racine in (
                    page_racine.appartenances_dossiers.all()
                ):
                    ranger_une_note_dans_un_carnet(
                        page_synthese,
                        appartenance_racine.dossier,
                        demandeur,
                    )
                if (
                    page_synthese.dossier_id is None
                    and page_racine.dossier_id is not None
                ):
                    ranger_une_note_dans_un_carnet(
                        page_synthese, page_racine.dossier, demandeur,
                    )
                # Source hors de tout carnet : la synthese irait nulle
                # part — invisible de l'arbre comme des ecrans carnet.
                # Repli : le fourre-tout « A ranger » du demandeur,
                # retrouve par son ROLE (SPEC-corpus § 6.3 ; relecture
                # C, I3). / Orphan source: file in the requester's
                # "A ranger" inbox, found by its technical role.
                if page_synthese.dossier_id is None and demandeur is not None:
                    from core.models import RoleSpecialDossier
                    carnet_a_ranger, _cree = Dossier.objects.get_or_create(
                        role_special=RoleSpecialDossier.A_RANGER,
                        owner=demandeur,
                        defaults={"name": "A ranger"},
                    )
                    ranger_une_note_dans_un_carnet(
                        page_synthese, carnet_a_ranger, demandeur,
                    )

            # L'acte date (§ 3.2) : perimetre FIGE a la production — la
            # note ANALYSEE (celle dont les extractions sont parties au
            # modele), pas sa racine : le § 8 « ce qui n'a pas ete
            # repris » se calcule sur ce perimetre-la (relecture C, I1).
            # Jamais recalcule.
            # / The dated act: scope frozen on the ANALYZED note.
            synthese_dirigee = SyntheseDirigee.objects.create(
                page=page_synthese,
                dossier=carnet_d_origine or page_synthese.dossier,
                produite_par=demandeur,
                # Le perimetre d'extractions est fige MEME s'il est vide
                # (analyseur sans extractions) : c'est le flag qui dit
                # « l'instantane fait foi » (relecture D, B2/B3).
                # / Frozen even when empty; the flag says so.
                perimetre_d_extractions_fige=True,
            )
            synthese_dirigee.notes_du_perimetre.add(page_source)
            if identifiants_du_perimetre:
                # Re-requete plutot que les ids bruts (relecture E, B3) :
                # une purge legale pendant la generation a pu supprimer
                # une extraction — un id disparu ferait echouer le .set()
                # et perdrait toute la synthese dans le rollback.
                # / Re-query: a vanished id must not kill the synthesis.
                from hypostasis_extractor.models import ExtractedEntity
                synthese_dirigee.extractions_du_perimetre.set(
                    ExtractedEntity.objects.filter(
                        pk__in=identifiants_du_perimetre,
                    ),
                )

        # Stocker page_synthese_id dans raw_result pour le polling, et
        # les marqueurs retires pour que l'hallucination soit VISIBLE.
        # / Store the id for polling and stripped markers for visibility.
        donnees_resultat = job_synthese.raw_result or {}
        donnees_resultat["page_synthese_id"] = page_synthese.pk
        donnees_resultat["citations_creees"] = bilan_d_indexation["liens_crees"]
        donnees_resultat["marqueurs_retires"] = (
            bilan_d_indexation["marqueurs_retires"]
        )
        donnees_resultat["citations_annoncees"] = citations_annoncees
        job_synthese.raw_result = donnees_resultat
        job_synthese.status = "completed"
        job_synthese.save(update_fields=["raw_result", "status"])

        duree = time.time() - debut_traitement
        logger.info(
            "synthetiser_page_task: termine job=%s page_synthese=%s en %.1fs — %d chars",
            job_id, page_synthese.pk, duree, len(texte_synthese),
        )

        # Notifier le navigateur que la tache est terminee (succes).
        # Cibles : les proprietaires des carnets contenant LA SYNTHESE
        # (§ 2.1 — c'est la ou elle atterrit qui compte, pas d'ou elle
        # vient) PLUS le demandeur, a qui la vue a promis une
        # notification (relecture C, I2). Dedoublonnes.
        # / Targets: owners of the notebooks holding THE SYNTHESIS, plus
        # the requester the view promised to notify.
        pks_destinataires = set(_destinataires_de_notification(page_synthese))
        pks_destinataires.discard(None)
        if demandeur is not None:
            pks_destinataires.add(demandeur.pk)
        for pk_destinataire in sorted(pks_destinataires) or [None]:
            notifier_tache_terminee(
                user_pk=pk_destinataire,
                tache_id=job_synthese.pk,
                tache_type="synthese",
                status="completed",
            )

    except Exception as erreur_synthese:
        # Erreur : marquer le job en erreur / Error: mark job as error
        message_erreur = str(erreur_synthese)[:500]
        logger.error(
            "synthetiser_page_task: erreur job=%s — %s",
            job_id, message_erreur, exc_info=True,
        )
        job_synthese.status = "error"
        job_synthese.error_message = message_erreur
        job_synthese.save(update_fields=["status", "error_message"])

        # Notifier le navigateur que la tache est terminee (erreur).
        # On recupere le proprietaire via job_synthese.page (peut etre None
        # si l'erreur est arrivee tres tot avant que page_source soit defini).
        # / Notify the browser that the task is complete (error).
        # / We get the owner via job_synthese.page (may be None if error
        # / happened very early before page_source was defined).
        page_pour_notif = job_synthese.page
        destinataires_pour_notif = (
            _destinataires_de_notification(page_pour_notif)
            if page_pour_notif is not None
            else [None]
        )
        for pk_destinataire in destinataires_pour_notif:
            notifier_tache_terminee(
                user_pk=pk_destinataire,
                tache_id=job_synthese.pk,
                tache_type="synthese",
                status="error",
            )


class ModeleAvecCompteurTokens:
    """
    Proxy autour du modele LLM langextract qui accumule les tokens.
    Utilise len(texte) // 4 comme estimation generique (ratio caracteres/tokens).
    / Proxy around the langextract LLM model that accumulates tokens.
    / Uses len(text) // 4 as a generic estimate (chars/tokens ratio).

    LOCALISATION : front/tasks.py
    """
    def __init__(self, modele_llm_original):
        self._modele = modele_llm_original
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def infer(self, batch_prompts, **kwargs):
        # Compter tokens input (estimation) / Count input tokens (estimate)
        for prompt in batch_prompts:
            self.total_input_tokens += len(str(prompt)) // 4
        # Appeler le vrai modele / Call the real model
        outputs = self._modele.infer(batch_prompts=batch_prompts, **kwargs)
        resultats = list(outputs)
        # Compter tokens output (estimation) / Count output tokens (estimate)
        for scored_list in resultats:
            for scored in (scored_list if isinstance(scored_list, list) else [scored_list]):
                self.total_output_tokens += len(scored.output) // 4
        return resultats

    def __getattr__(self, name):
        return getattr(self._modele, name)


@shared_task(bind=True)
def analyser_page_task(self, job_id):
    """
    Tache Celery : lance l'extraction LangExtract sur une Page via un ExtractionJob.
    Le job doit deja exister en status PENDING avec page, ai_model et prompt_description remplis.
    / Celery task: runs LangExtract extraction on a Page via an ExtractionJob.
    The job must already exist in PENDING status with page, ai_model and prompt_description filled.
    """
    from hypostasis_extractor.models import (
        AnalyseurSyntaxique, ExtractionJob, ExtractedEntity, ExtractionJobStatus,
    )
    from hypostasis_extractor.services import (
        _construire_exemples_langextract, resolve_model_params, _try_map_to_hypostasis,
    )
    import langextract.prompting as prompting_lx
    import langextract.factory as factory_lx
    import langextract.resolver as resolver_lx
    from langextract.core import data as data_lx
    from langextract.core import format_handler as fh_lx

    TAILLE_MAX_CHUNK = 1500

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
    identifiant_utilisateur = page_associee.owner_id

    # Revalidation du moteur A L'EXECUTION (relecture BR-C, defaut n°2) :
    # le job a pu etre lance pendant qu'une ingestion Docling tournait —
    # au moment ou il s'execute, la page est devenue ELEMENT. L'analyser
    # ici ecrirait des extractions a offsets SANS portions sur une page
    # ELEMENT ; on delegue donc a la tache du bon moteur, dans ce meme
    # slot de worker. / Re-check the engine at run time: a job launched
    # during a Docling ingestion may execute on a now-ELEMENT page —
    # delegate to the right engine's task.
    from core.models import MoteurDePage
    if page_associee.moteur == MoteurDePage.ELEMENT:
        from hypostasis_extractor.tasks_element import (
            analyser_une_page_avec_le_moteur_element,
        )
        logger.info(
            "analyser_page_task: la page %s est devenue ELEMENT — "
            "delegation au moteur par element (job=%s).",
            page_associee.pk, job_id,
        )
        return analyser_une_page_avec_le_moteur_element(job_id)

    # Passer le job en PROCESSING
    # / Set job to PROCESSING
    job_extraction.status = ExtractionJobStatus.PROCESSING
    job_extraction.error_message = None
    # "updated_at" est liste explicitement : Django n'applique auto_now
    # qu'aux champs presents dans update_fields. Sans lui, la date reste
    # figee a la creation, et la garde d'edition
    # (hypostasis_extractor/services/garde_edition.py) ne peut pas savoir
    # si ce job est encore vivant.
    # / auto_now only applies to fields listed in update_fields.
    job_extraction.save(update_fields=["status", "error_message", "updated_at"])

    logger.info(
        "analyser_page_task: demarrage job=%s page=%s model=%s",
        job_id, page_associee.pk,
        job_extraction.ai_model.model_name if job_extraction.ai_model else "?",
    )

    try:
        texte_source = page_associee.text_readability
        if not texte_source:
            raise ValueError("La Page n'a pas de text_readability disponible")

        longueur_texte_total = len(texte_source)

        # Construire les exemples few-shot depuis l'analyseur stocke dans raw_result
        # / Build few-shot examples from the analyzer stored in raw_result
        analyseur_id = (job_extraction.raw_result or {}).get("analyseur_id")
        if analyseur_id:
            analyseur = AnalyseurSyntaxique.objects.get(pk=analyseur_id)
            liste_exemples_langextract = _construire_exemples_langextract(analyseur)

            # Rattacher la derniere version de l'analyseur au job (PHASE-26b)
            # Si aucune version n'existe, creer un snapshot initial automatique.
            # / Attach the latest analyzer version to the job (PHASE-26b)
            # / If no version exists, create an automatic initial snapshot.
            from hypostasis_extractor.models import AnalyseurVersion
            from hypostasis_extractor.services import creer_version_analyseur
            derniere_version_analyseur = (
                AnalyseurVersion.objects.filter(analyseur=analyseur)
                .order_by('-version_number').first()
            )
            if derniere_version_analyseur is None:
                derniere_version_analyseur = creer_version_analyseur(
                    analyseur, None, "Snapshot initial automatique",
                )
            job_extraction.analyseur_version = derniere_version_analyseur
            job_extraction.save(update_fields=["analyseur_version"])
        else:
            liste_exemples_langextract = []

        # Resoudre les parametres du modele / Resolve model params
        if job_extraction.ai_model:
            parametres_modele = resolve_model_params(job_extraction.ai_model)
        else:
            parametres_modele = {"model_id": "gemini-2.5-flash"}

        # --- Construction manuelle du pipeline langextract ---
        # On replique le setup de lx.extract() (extraction.py:213-327)
        # pour utiliser notre AnnotateurAvecProgression au lieu de Annotator.
        # / --- Manual langextract pipeline setup ---
        # / We replicate the lx.extract() setup (extraction.py:213-327)
        # / to use our AnnotateurAvecProgression instead of Annotator.

        # 1. PromptTemplate depuis les exemples few-shot
        # / 1. PromptTemplate from few-shot examples
        modele_prompt = prompting_lx.PromptTemplateStructured(
            description=job_extraction.prompt_description
        )
        modele_prompt.examples.extend(liste_exemples_langextract)

        # 2. Creer le modele LLM via la factory
        # Gemini 2.5 Flash utilise des "thinking tokens" qui comptent dans
        # max_output_tokens mais ne sont pas dans la reponse visible.
        # Avec 3000 tokens, le thinking peut consommer 2500 tokens et ne laisser
        # que 500 tokens pour la reponse JSON → JSON tronque.
        # On met 8192 pour laisser assez de marge au thinking + reponse.
        # La protection contre les boucles de repetition est assuree par la
        # normalisation (troncation a 500 chars + max 3 hypostases).
        # / 2. Create the LLM model via the factory
        # / Gemini 2.5 Flash uses "thinking tokens" that count toward
        # / max_output_tokens but are not in the visible response.
        # / With 3000 tokens, thinking can consume 2500 tokens and leave
        # / only 500 tokens for the JSON response → truncated JSON.
        # / We use 8192 to leave enough room for thinking + response.
        # / Protection against repetition loops is handled by normalization
        # / (truncation at 500 chars + max 3 hypostases).
        max_output_tokens_calcule = 8192
        kwargs_modele_llm = {
            "format_type": data_lx.FormatType.JSON,
            "max_output_tokens": max_output_tokens_calcule,
        }
        kwargs_modele_llm.update({
            k: v for k, v in parametres_modele.items()
            if k != "model_id" and v is not None
        })
        config_modele = factory_lx.ModelConfig(
            model_id=parametres_modele.get("model_id", "gemini-2.5-flash"),
            provider_kwargs=kwargs_modele_llm,
        )
        modele_llm_brut = factory_lx.create_model(
            config=config_modele,
            examples=modele_prompt.examples,
            use_schema_constraints=True,
        )
        # Wrapper le modele pour comptabiliser les tokens (PHASE-26b)
        # / Wrap the model to track tokens (PHASE-26b)
        modele_llm = ModeleAvecCompteurTokens(modele_llm_brut)

        # 3. FormatHandler et Resolver avec suppress_parse_errors
        # / 3. FormatHandler and Resolver with suppress_parse_errors
        parametres_resolution = {"suppress_parse_errors": True}
        handler_format, parametres_restants = fh_lx.FormatHandler.from_resolver_params(
            resolver_params=parametres_resolution,
            base_format_type=data_lx.FormatType.JSON,
            base_use_fences=modele_llm.requires_fence_output,
            base_attribute_suffix=data_lx.ATTRIBUTE_SUFFIX,
            base_use_wrapper=True,
            base_wrapper_key=data_lx.EXTRACTIONS_KEY,
        )

        # Extraire les kwargs d'alignement (fuzzy, threshold, suppress...)
        # / Extract alignment kwargs (fuzzy, threshold, suppress...)
        kwargs_alignement = {}
        for cle in resolver_lx.ALIGNMENT_PARAM_KEYS:
            valeur = parametres_restants.pop(cle, None)
            if valeur is not None:
                kwargs_alignement[cle] = valeur

        resolveur = resolver_lx.Resolver(
            format_handler=handler_format,
            **parametres_restants,
        )

        # Estimer le nombre de chunks que langextract va creer.
        # Ce n'est qu'une estimation — le ChunkIterator coupe aux frontieres de phrases.
        # / Estimate the number of chunks langextract will create.
        # / This is just an estimate — ChunkIterator cuts at sentence boundaries.
        import math
        nombre_chunks_estime = max(1, math.ceil(longueur_texte_total / TAILLE_MAX_CHUNK))

        # Nombre de chunks envoyes en parallele au LLM par batch.
        # Le callback WS se declenche toujours apres chaque chunk individuel
        # (boucle interne), seul l'appel LLM est parallelise.
        # / Number of chunks sent in parallel to the LLM per batch.
        # / The WS callback still fires after each individual chunk
        # / (inner loop), only the LLM call is parallelized.
        TAILLE_BATCH = 5

        logger.info(
            "analyser_page_task: pipeline langextract pret\n"
            "  job=%s | model=%s | text=%d chars | ~%d chunks (max_char_buffer=%d)\n"
            "  exemples=%d | suppress_parse_errors=True | max_output_tokens=%d\n"
            "  batch_length=%d (parallele, callback WS par chunk)",
            job_id, parametres_modele.get("model_id", "?"),
            longueur_texte_total, nombre_chunks_estime, TAILLE_MAX_CHUNK,
            len(liste_exemples_langextract), max_output_tokens_calcule,
            TAILLE_BATCH,
        )

        # Supprimer les anciennes entites AVANT de commencer l'extraction (re-extraction)
        # Garde § 4.2 : refus propre si une synthese dirigee cite.
        # / Delete old entities BEFORE re-extraction; § 4.2 guard first.
        from core.services.synthese import (
            verifier_qu_aucune_dirigee_ne_cite_les_extractions,
        )
        verifier_qu_aucune_dirigee_ne_cite_les_extractions(
            job_extraction.entities.all()
        )
        job_extraction.entities.all().delete()

        # 4. Callback appele apres chaque chunk resolve()+align()
        # Cree les entites en DB et envoie les notifications WS en temps reel.
        # / 4. Callback called after each chunk resolve()+align()
        # / Creates entities in DB and sends real-time WS notifications.
        nombre_entites_creees = 0
        numero_chunk_courant = 0

        def callback_extraction_chunk(extractions_du_chunk, caracteres_traites, warnings_chunk=None):
            """
            Appele apres chaque cycle resolve()+align() d'un chunk LangExtract.
            Cree les entites en DB et met a jour le compteur sur le job.
            / Called after each resolve()+align() cycle for a LangExtract chunk.
            / Creates entities in DB and updates the job counter.

            LOCALISATION : front/tasks.py (closure dans analyser_page_task)

            FLUX :
            1. Recoit les extractions alignees depuis AnnotateurAvecProgression
            2. Cree un ExtractedEntity en DB pour chaque extraction
            3. Sauvegarde entities_count pour le suivi en DB

            COMMUNICATION :
            Recoit : appel direct depuis AnnotateurAvecProgression._annotate_documents_single_pass
            """
            nonlocal nombre_entites_creees, numero_chunk_courant
            numero_chunk_courant += 1

            logger.info(
                "  [callback] %d extraction(s) recues, %d/%d chars traites (%d%%)",
                len(extractions_du_chunk), caracteres_traites,
                longueur_texte_total,
                int(100 * caracteres_traites / longueur_texte_total) if longueur_texte_total else 0,
            )

            for extraction in extractions_du_chunk:
                intervalle = extraction.char_interval
                position_debut = intervalle.start_pos if intervalle else 0
                position_fin = intervalle.end_pos if intervalle else 0

                # Normalise les attributs LLM vers les 4 cles canoniques avant stockage
                # / Normalize LLM attributes to 4 canonical keys before storage
                from front.normalisation import normaliser_attributs_entite
                attributs_normalises = normaliser_attributs_entite(extraction.attributes or {})

                entite_creee = ExtractedEntity.objects.create(
                    job=job_extraction,
                    extraction_class=extraction.extraction_class,
                    extraction_text=extraction.extraction_text,
                    start_char=position_debut,
                    end_char=position_fin,
                    attributes=attributs_normalises,
                )
                nombre_entites_creees += 1
                _try_map_to_hypostasis(entite_creee)

                logger.debug(
                    "  [callback] entite #%d creee: [%s] '%s' pos=%d-%d",
                    nombre_entites_creees,
                    extraction.extraction_class,
                    extraction.extraction_text[:60],
                    position_debut, position_fin,
                )

            # Sauvegarder le compteur d'entites pour le suivi en DB.
            # / Save entity counter for DB tracking.
            job_extraction.entities_count = nombre_entites_creees
            # "updated_at" : ce callback est appele a chaque chunk traite.
            # C'est le seul signe de vie regulier d'une analyse longue.
            # / This callback is a long analysis's only regular sign of life.
            job_extraction.save(
                update_fields=["entities_count", "updated_at"],
            )

        # 5. Creer l'annotateur avec callback et lancer l'extraction
        # batch_length=TAILLE_BATCH pour paralleliser les appels LLM.
        # Le callback se declenche toujours apres chaque chunk individuel.
        # / 5. Create the annotator with callback and run extraction
        # / batch_length=TAILLE_BATCH to parallelize LLM calls.
        # / The callback still fires after each individual chunk.
        annotateur = _creer_annotateur_avec_progression(
            modele_llm=modele_llm,
            prompt_template=modele_prompt,
            format_handler=handler_format,
            callback_par_chunk=callback_extraction_chunk,
        )

        # Passer max_output_tokens en runtime kwarg pour que Gemini le recoive.
        # Le constructeur GeminiLanguageModel filtre les kwargs par _API_CONFIG_KEYS
        # et supprime max_output_tokens — il faut le passer ici a annotate_text
        # pour qu'il arrive dans infer() → config['max_output_tokens'].
        # / Pass max_output_tokens as runtime kwarg so Gemini receives it.
        # / GeminiLanguageModel constructor filters kwargs by _API_CONFIG_KEYS
        # / and drops max_output_tokens — must pass it here to annotate_text
        # / so it reaches infer() → config['max_output_tokens'].
        kwargs_inference = {**kwargs_alignement, "max_output_tokens": max_output_tokens_calcule}

        resultat_annote = annotateur.annotate_text(
            text=texte_source,
            resolver=resolveur,
            max_char_buffer=TAILLE_MAX_CHUNK,
            batch_length=TAILLE_BATCH,
            show_progress=False,
            **kwargs_inference,
        )

        # Les entites ont deja ete creees dans le callback — on utilise le resultat
        # uniquement pour verifier la coherence (le nombre d'extractions).
        # / Entities were already created in the callback — we use the result
        # / only to verify consistency (extraction count).
        nombre_extractions_langextract = len(resultat_annote.extractions or [])
        if nombre_extractions_langextract != nombre_entites_creees:
            logger.warning(
                "analyser_page_task: incoherence — callback a cree %d entites, "
                "resultat_annote en contient %d",
                nombre_entites_creees, nombre_extractions_langextract,
            )

        # Mettre a jour le job (update_fields pour ne pas ecraser d'autres champs)
        # / Update the job (update_fields to avoid overwriting other fields)
        duree_traitement = time.time() - debut_traitement
        job_extraction.status = ExtractionJobStatus.COMPLETED
        job_extraction.entities_count = nombre_entites_creees
        job_extraction.processing_time_seconds = duree_traitement
        job_extraction.raw_result = {
            "extractions_count": nombre_entites_creees,
            "document_length": longueur_texte_total,
            "max_char_buffer": TAILLE_MAX_CHUNK,
        }

        # Capture des tokens reels et du cout (best-effort) — PHASE-26b
        # Le modele LLM peut exposer les tokens via usage_metadata ou total_tokens.
        # / Capture real tokens and cost (best-effort) — PHASE-26b
        champs_a_sauvegarder = [
            "status", "entities_count", "processing_time_seconds", "raw_result",
        ]
        try:
            tokens_input = getattr(modele_llm, 'total_input_tokens', None)
            tokens_output = getattr(modele_llm, 'total_output_tokens', None)
            if tokens_input is not None:
                job_extraction.tokens_input_reels = int(tokens_input)
                champs_a_sauvegarder.append("tokens_input_reels")
            if tokens_output is not None:
                job_extraction.tokens_output_reels = int(tokens_output)
                champs_a_sauvegarder.append("tokens_output_reels")
            # Estimation du cout reel via le modele IA si les tokens sont disponibles
            # / Estimate real cost via AI model if tokens available
            if tokens_input is not None and tokens_output is not None and job_extraction.ai_model:
                modele_ia = job_extraction.ai_model
                if hasattr(modele_ia, 'estimer_cout_euros'):
                    cout_estime = modele_ia.estimer_cout_euros(
                        int(tokens_input), int(tokens_output),
                    )
                    if cout_estime is not None:
                        job_extraction.cout_reel_euros = cout_estime
                        champs_a_sauvegarder.append("cout_reel_euros")
        except Exception as erreur_tokens:
            logger.warning(
                "analyser_page_task: impossible de capturer les tokens reels — %s",
                erreur_tokens,
            )

        job_extraction.save(update_fields=champs_a_sauvegarder)

        logger.info(
            "analyser_page_task: termine job=%s — %d entites en %.1fs",
            job_id, nombre_entites_creees, duree_traitement,
        )

        # Notifier le navigateur que la tache est terminee (succes)
        # / Notify the browser that the task is complete (success)
        notifier_tache_terminee(
            user_pk=page_associee.owner.pk if page_associee.owner else None,
            tache_id=job_extraction.pk,
            tache_type="analyse",
            status="completed",
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

        # Notifier le navigateur que la tache est terminee (erreur)
        # / Notify the browser that the task is complete (error)
        notifier_tache_terminee(
            user_pk=page_associee.owner.pk if page_associee.owner else None,
            tache_id=job_extraction.pk,
            tache_type="analyse",
            status="error",
        )


# =============================================================================
# LES TACHES DE LA COUCHE SYNTHESE AU NIVEAU CARNET (phase H)
# Wiki vivant, synthese dirigee multi-notes, proposition de mise a jour,
# verification a la demande. Toutes appliquent le contrat de la phase C :
# marqueurs [[ext:N]], ligne CITATIONS_USED, perimetre OBLIGATOIRE.
# / Notebook-level synthesis tasks (phase H), on the phase C contract.
# =============================================================================


def _blocs_d_extractions_par_note(pages):
    """
    Le corpus d'un article carnet-niveau : un bloc par note, chaque
    extraction avec son identifiant [ext:N] et ses commentaires.
    / One block per note; each extraction with its id and comments.

    LOCALISATION : front/tasks.py

    :return: (texte_des_blocs, identifiants_du_perimetre)
    """
    from core.services.synthese import extractions_citables_de_la_note

    blocs = []
    identifiants_du_perimetre = set()
    for page in pages:
        lignes = [f"=== NOTE : {page.title or f'Note {page.pk}'} ==="]
        extractions = list(
            extractions_citables_de_la_note(page)
            .prefetch_related("commentaires__user").order_by("pk")
        )
        for extraction in extractions:
            identifiants_du_perimetre.add(extraction.pk)
            lignes.append(
                f"Identifiant : ext:{extraction.pk}\n"
                f'Citation : "{extraction.extraction_text}"'
            )
            for commentaire in extraction.commentaires.all():
                nom = (
                    commentaire.user.username if commentaire.user
                    else "Anonyme"
                )
                lignes.append(f'  - {nom} : "{commentaire.commentaire}"')
        if len(lignes) == 1:
            lignes.append("(aucune extraction sur cette note)")
        blocs.append("\n".join(lignes))
    return "\n\n".join(blocs), identifiants_du_perimetre


def _consignes_de_forme_d_article():
    """Le contrat de forme commun (## + marqueurs + CITATIONS_USED).
    / The shared form contract."""
    return (
        "=== FORMAT DE SORTIE ===\n"
        "Réponds UNIQUEMENT en Markdown propre :\n"
        "- `## Section` pour les sous-parties (UNIQUEMENT ce niveau : "
        "jamais de `#` seul ni de `###`)\n"
        "- Paragraphes courts séparés par des lignes vides\n"
        "- Pas de blocs de code, pas de tableaux, pas de HTML brut\n\n"
        "=== SOURÇAGE (OBLIGATOIRE) ===\n"
        "CHAQUE paragraphe doit citer au moins une extraction : chaque "
        "affirmation se termine par le marqueur de sa source, accolé à "
        "la fin de la phrase : `[[ext:N]]` (exemple : « Le seuil est "
        "acté.[[ext:12]] »). Plusieurs sources = plusieurs marqueurs "
        "consécutifs. Ne cite JAMAIS un identifiant qui n'apparaît pas "
        "ci-dessus. Jamais de marqueur dans un titre. Un article sans "
        "marqueurs sera REJETÉ.\n\n"
        "Termine IMPÉRATIVEMENT ta réponse par une DERNIÈRE ligne de "
        "contrôle, seule sur sa ligne :\n"
        "`CITATIONS_USED: ` suivi des identifiants cités séparés par "
        "des virgules, ou `CITATIONS_USED: aucune`. Une réponse sans "
        "cette ligne sera rejetée comme incomplète."
    )


def _prompt_systeme_de_synthese():
    """
    Le prompt systeme : l'analyseur de synthese par defaut s'il existe,
    sinon une consigne generique honnete.
    / The default synthesis analyzer's prompt, or a plain fallback.
    """
    from hypostasis_extractor.models import AnalyseurSyntaxique, PromptPiece

    analyseur = AnalyseurSyntaxique.objects.filter(
        is_active=True, type_analyseur="synthetiser",
    ).order_by("-est_par_defaut", "name").first()
    if analyseur is not None:
        pieces = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        prompt = "\n".join(piece.content for piece in pieces)
        if prompt.strip():
            return prompt
    return (
        "Tu es un moteur de synthèse délibérative : tu rédiges des "
        "articles sobres, fidèles aux extractions fournies, sans rien "
        "inventer."
    )


def _ecrire_le_corps_d_un_article(page_d_article, texte_brut,
                                  identifiants_du_perimetre):
    """
    Le tronc commun d'ecriture d'un article (wiki ou synthese carnet) :
    indexation des citations avec le perimetre OBLIGATOIRE, rendu HTML
    en renvois [N], nettoyage bleach, hash.
    / Shared article write path: mandatory-scope indexing, [N] HTML
    rendering, bleach, hash.

    LOCALISATION : front/tasks.py

    :return: le bilan d'indexation / the indexing report
    :raises ValueError: si le perimetre offrait des extractions et que
        l'article n'en cite AUCUNE — un article sans preuve n'est pas un
        succes dans un systeme de synthese SOURCEE (constat reel du
        9 aout : GPT-4o-mini a redige un wiki entier sans un marqueur).
        / A citation-less article over a non-empty scope fails loudly.
    """
    import html

    import markdown

    from core.services.synthese import indexer_les_citations

    bilan_d_indexation = indexer_les_citations(
        page_d_article, texte_brut, identifiants_du_perimetre,
    )
    if identifiants_du_perimetre and bilan_d_indexation["liens_crees"] == 0:
        raise ValueError(
            "L'article est arrivé sans aucune citation alors que le "
            "périmètre offrait des extractions : un texte sans preuve "
            "n'est pas enregistré. Relancez la production. "
            "/ No citation over a non-empty scope: refused."
        )
    texte_definitif = bilan_d_indexation["texte_nettoye"]
    html_d_article = _nettoyer_le_html_de_synthese(
        markdown.markdown(
            html.escape(
                _remplacer_les_marqueurs_par_des_renvois(texte_definitif)
            ),
            extensions=["extra", "nl2br"],
        )
    )
    page_d_article.text_readability = texte_definitif
    page_d_article.html_original = html_d_article
    page_d_article.html_readability = html_d_article
    page_d_article.content_hash = hashlib.sha256(
        texte_definitif.encode("utf-8")
    ).hexdigest()
    page_d_article.save(update_fields=[
        "text_readability", "html_original", "html_readability",
        "content_hash", "updated_at",
    ])
    return bilan_d_indexation


def _terminer_un_job_d_article(job, page_d_article, bilan_d_indexation,
                               citations_annoncees, tache_type):
    """Cloture commune : raw_result + notifications. / Shared wrap-up."""
    donnees = job.raw_result or {}
    donnees["page_synthese_id"] = page_d_article.pk
    donnees["citations_creees"] = bilan_d_indexation["liens_crees"]
    donnees["marqueurs_retires"] = bilan_d_indexation["marqueurs_retires"]
    donnees["citations_annoncees"] = citations_annoncees
    job.raw_result = donnees
    job.status = "completed"
    job.save(update_fields=["raw_result", "status"])

    pks_destinataires = set(_destinataires_de_notification(page_d_article))
    pks_destinataires.discard(None)
    identifiant_demandeur = (job.raw_result or {}).get("demandeur_id")
    if identifiant_demandeur:
        pks_destinataires.add(identifiant_demandeur)
    for pk_destinataire in sorted(pks_destinataires) or [None]:
        notifier_tache_terminee(
            user_pk=pk_destinataire, tache_id=job.pk,
            tache_type=tache_type, status="completed",
        )


def _echouer_un_job_d_article(job, erreur, tache_type):
    """Cloture d'erreur commune. / Shared failure wrap-up."""
    message = str(erreur)[:500]
    logger.error(
        "%s: erreur job=%s — %s", tache_type, job.pk, message,
        exc_info=True,
    )
    job.status = "error"
    job.error_message = message
    job.save(update_fields=["status", "error_message"])
    identifiant_demandeur = (job.raw_result or {}).get("demandeur_id")
    notifier_tache_terminee(
        user_pk=identifiant_demandeur or None, tache_id=job.pk,
        tache_type=tache_type, status="error",
    )


@shared_task(bind=True)
def produire_un_wiki_task(self, job_id):
    """
    Produit (ou reproduit) l'article d'un Wiki : perimetre RECALCULE au
    moment de la production (§ 3.1.1), marqueurs + CITATIONS_USED.
    / Produces a Wiki article on its recomputed scope.

    LOCALISATION : front/tasks.py
    """
    from core.models import Wiki
    from core.services.synthese import notes_du_perimetre_d_un_wiki
    from hypostasis_extractor.models import ExtractionJob

    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error("produire_un_wiki_task: job=%s introuvable", job_id)
        return
    try:
        job.status = "processing"
        job.save(update_fields=["status"])

        wiki = Wiki.objects.get(pk=job.raw_result["wiki_id"])
        notes = list(notes_du_perimetre_d_un_wiki(wiki))
        blocs, identifiants_du_perimetre = _blocs_d_extractions_par_note(notes)

        prompt = (
            _prompt_systeme_de_synthese() + "\n\n"
            f"=== SUJET DE L'ARTICLE ===\n{wiki.sujet}\n\n"
            "=== EXTRACTIONS DU PÉRIMÈTRE ===\n" + blocs + "\n\n"
            "=== CONSIGNE ===\n"
            "Rédige un article de wiki sur ce sujet, nourri UNIQUEMENT "
            "des extractions ci-dessus. Le sujet oriente la rédaction ; "
            "il ne t'autorise pas à inventer.\n\n"
            + _consignes_de_forme_d_article()
        )
        from core.llm_providers import appeler_llm
        reponse = appeler_llm(job.ai_model, prompt)
        if not reponse or not reponse.strip():
            raise ValueError("Le LLM a retourne une reponse vide")
        texte_brut, citations_annoncees = _detacher_la_ligne_citations_used(
            reponse.strip()
        )
        bilan = _ecrire_le_corps_d_un_article(
            wiki.page, texte_brut, identifiants_du_perimetre,
        )
        # Le compteur de tours ne bouge pas ici : la production initiale
        # est le tour 1 (defaut du modele) ; seuls les tours de MISE A
        # JOUR l'incrementent. / Rounds only bump on updates.
        wiki.save(update_fields=["derniere_mise_a_jour"])
        _terminer_un_job_d_article(
            job, wiki.page, bilan, citations_annoncees, "wiki",
        )
    except Exception as erreur:
        _echouer_un_job_d_article(job, erreur, "wiki")


@shared_task(bind=True)
def produire_une_synthese_de_carnet_task(self, job_id):
    """
    Remplit une synthese dirigee de CARNET dont l'acte date (page +
    SyntheseDirigee, perimetre fige au moment du geste) existe deja —
    la vue cree, la tache remplit.
    / Fills a notebook-level synthesis whose frozen act already exists.

    LOCALISATION : front/tasks.py
    """
    from hypostasis_extractor.models import ExtractionJob

    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error(
            "produire_une_synthese_de_carnet_task: job=%s introuvable",
            job_id,
        )
        return
    try:
        job.status = "processing"
        job.save(update_fields=["status"])

        page_de_synthese = job.page
        synthese_dirigee = page_de_synthese.synthese_dirigee
        notes = list(synthese_dirigee.notes_du_perimetre.all())
        blocs, identifiants_du_perimetre = _blocs_d_extractions_par_note(notes)

        direction = ""
        if synthese_dirigee.categorie_de_direction is not None:
            direction = (
                f"\n=== DIRECTION ===\nLa synthèse porte sur la "
                f"catégorie « "
                f"{synthese_dirigee.categorie_de_direction.nom} ».\n"
            )
        prompt = (
            _prompt_systeme_de_synthese() + "\n\n"
            f"=== TITRE DEMANDÉ ===\n{page_de_synthese.title}\n"
            + direction + "\n"
            "=== EXTRACTIONS DU PÉRIMÈTRE ===\n" + blocs + "\n\n"
            "=== CONSIGNE ===\n"
            "Produis la synthèse délibérative de ce corpus : un texte "
            "autonome et lisible, nourri UNIQUEMENT des extractions "
            "ci-dessus.\n\n"
            + _consignes_de_forme_d_article()
        )
        from core.llm_providers import appeler_llm
        reponse = appeler_llm(job.ai_model, prompt)
        if not reponse or not reponse.strip():
            raise ValueError("Le LLM a retourne une reponse vide")
        texte_brut, citations_annoncees = _detacher_la_ligne_citations_used(
            reponse.strip()
        )
        bilan = _ecrire_le_corps_d_un_article(
            page_de_synthese, texte_brut, identifiants_du_perimetre,
        )
        # Le perimetre d'extractions fige = ce qui a ete montre au
        # modele (re-requete : jamais un id disparu, relecture E B3).
        # / Freeze exactly what the model saw, re-queried.
        from hypostasis_extractor.models import ExtractedEntity
        synthese_dirigee.extractions_du_perimetre.set(
            ExtractedEntity.objects.filter(pk__in=identifiants_du_perimetre),
        )
        _terminer_un_job_d_article(
            job, page_de_synthese, bilan, citations_annoncees, "synthese",
        )
    except Exception as erreur:
        _echouer_un_job_d_article(job, erreur, "synthese")


@shared_task(bind=True)
def proposer_une_maj_de_wiki_task(self, job_id):
    """
    Propose des operations de section (§ 6) sur les extractions que le
    wiki n'a pas encore reprises. La proposition N'EST PAS appliquee :
    elle attend l'humain (previsualiser -> accepter, phase I). Elle
    porte l'updated_at de l'article (addendum n°1).
    / Proposes section operations on the wiki's left-out extractions;
    never auto-applied; carries the article's updated_at.

    LOCALISATION : front/tasks.py
    """
    import json as json_module

    from core.models import Wiki
    from core.services.synthese import extractions_ecartees
    from hypostasis_extractor.models import ExtractionJob

    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error(
            "proposer_une_maj_de_wiki_task: job=%s introuvable", job_id,
        )
        return
    try:
        job.status = "processing"
        job.save(update_fields=["status"])

        wiki = Wiki.objects.get(pk=job.raw_result["wiki_id"])
        article = wiki.page
        ecartees = list(extractions_ecartees(article).order_by("pk"))
        if not ecartees:
            raise ValueError(
                "Rien à mettre à jour : toutes les extractions du "
                "périmètre sont déjà reprises par l'article. "
                "/ Nothing left out."
            )

        lignes_d_ecartees = []
        for extraction in ecartees:
            lignes_d_ecartees.append(
                f"Identifiant : ext:{extraction.pk}\n"
                f'Citation : "{extraction.extraction_text}"'
            )
        prompt = (
            _prompt_systeme_de_synthese() + "\n\n"
            "=== ARTICLE ACTUEL ===\n" + article.text_readability + "\n\n"
            "=== EXTRACTIONS NON REPRISES ===\n"
            + "\n\n".join(lignes_d_ecartees) + "\n\n"
            "=== CONSIGNE ===\n"
            "Propose des opérations de mise à jour de l'article pour "
            "intégrer ces extractions. Tu ne réécris JAMAIS l'article : "
            "tu proposes des opérations, un humain les acceptera une "
            "par une.\n\n"
            "=== FORMAT DE SORTIE ===\n"
            "Réponds UNIQUEMENT par un tableau JSON d'opérations, sans "
            "aucun texte autour :\n"
            '[{"type": "append_to_section", "section": "<titre ## '
            'exact>", "contenu": "<markdown avec [[ext:N]]>"}, ...]\n'
            "Types permis : no_change, append_to_section, "
            "replace_section, insert_section (avec \"titre\" et "
            "\"apres\"). Chaque contenu cite ses sources par [[ext:N]]. "
            "Les seuls titres valides sont ceux de l'article ci-dessus."
        )
        from core.llm_providers import appeler_llm
        reponse = appeler_llm(job.ai_model, prompt)

        # Contrat anti-troncature : la reponse DOIT etre un tableau
        # JSON parseable — echec bruyant sinon, jamais une proposition
        # a moitie lue. / Loud failure on unparseable JSON.
        texte_json = (reponse or "").strip()
        if texte_json.startswith("```"):
            texte_json = texte_json.strip("`")
            if texte_json.startswith("json"):
                texte_json = texte_json[4:]
        try:
            operations = json_module.loads(texte_json)
            if not isinstance(operations, list):
                raise ValueError("pas un tableau")
        except (ValueError, TypeError):
            raise ValueError(
                "La proposition est arrivée illisible (pas un tableau "
                "JSON d'opérations). Rien n'a été proposé — relancez "
                "la mise à jour. / Unparseable proposal."
            )

        donnees = job.raw_result or {}
        donnees["operations"] = operations
        # La fraicheur (addendum n°1) : l'application refusera si
        # l'article a bouge depuis. / Optimistic concurrency token.
        donnees["updated_at_de_l_article"] = (
            article.updated_at.isoformat()
        )
        job.raw_result = donnees
        job.status = "completed"
        job.save(update_fields=["raw_result", "status"])
        notifier_tache_terminee(
            user_pk=(job.raw_result or {}).get("demandeur_id") or None,
            tache_id=job.pk, tache_type="maj_wiki", status="completed",
        )
    except Exception as erreur:
        _echouer_un_job_d_article(job, erreur, "maj_wiki")


@shared_task(bind=True)
def verifier_les_citations_task(self, job_id):
    """
    La verification § 7 en asynchrone — un geste explicite, jamais
    automatique (decision Q3). / On-demand § 7 verification.

    LOCALISATION : front/tasks.py
    """
    from core.services.verification import verifier_les_citations_d_un_article
    from hypostasis_extractor.models import ExtractionJob

    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error(
            "verifier_les_citations_task: job=%s introuvable", job_id,
        )
        return
    try:
        job.status = "processing"
        job.save(update_fields=["status"])

        bilan = verifier_les_citations_d_un_article(job.page, job.ai_model)

        donnees = job.raw_result or {}
        donnees["bilan_de_verification"] = bilan
        job.raw_result = donnees
        job.status = "completed"
        job.save(update_fields=["raw_result", "status"])
        notifier_tache_terminee(
            user_pk=(job.raw_result or {}).get("demandeur_id") or None,
            tache_id=job.pk, tache_type="verification", status="completed",
        )
    except Exception as erreur:
        _echouer_un_job_d_article(job, erreur, "verification")
