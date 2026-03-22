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


def envoyer_progression_websocket(nom_groupe, type_message, donnees):
    """
    Envoie un message au channel layer depuis une tache Celery (contexte sync).
    / Send a message to the channel layer from a Celery task (sync context).
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    couche_channels = get_channel_layer()
    if couche_channels is None:
        logger.debug("envoyer_progression_websocket: channel layer non configure, skip")
        return

    async_to_sync(couche_channels.group_send)(
        nom_groupe,
        {'type': type_message, **donnees},
    )




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
    job_transcription.save(update_fields=["status", "celery_task_id"])

    # Notifier le navigateur que la transcription a demarre
    # / Notify the browser that transcription has started
    nom_groupe_transcription = f"tache_{self.request.id}"
    envoyer_progression_websocket(nom_groupe_transcription, "progression", {
        "pourcentage": 5,
        "message": "Transcription audio démarrée",
        "status": "en_cours",
    })

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

        # Debit post-completion (PHASE-26h) — debiter le cout de la transcription audio
        # Le cout est base sur la duree de traitement (tarif par minute selon le modele)
        # / Post-completion debit (PHASE-26h) — debit audio transcription cost
        # / Cost is based on processing time (per-minute rate for the model)
        from django.conf import settings as django_settings
        if django_settings.STRIPE_ENABLED and config_transcription:
            try:
                from core.models import CreditAccount, SoldeInsuffisantError
                cout_transcription = config_transcription.estimer_cout_euros(
                    duree_traitement,
                ) if hasattr(config_transcription, 'estimer_cout_euros') else None

                if cout_transcription and cout_transcription > 0:
                    proprietaire_audio = page_associee.owner or (
                        page_associee.dossier.owner if page_associee.dossier else None
                    )
                    if proprietaire_audio and not proprietaire_audio.is_superuser:
                        compte_credits_audio = CreditAccount.get_ou_creer(proprietaire_audio)
                        compte_credits_audio.debiter(
                            montant=cout_transcription,
                            description=f"Transcription audio #{job_id} — {duree_traitement:.0f}s",
                        )
                        logger.info(
                            "transcrire_audio_task: debite %s EUR du compte de %s pour job=%s",
                            cout_transcription, proprietaire_audio.username, job_id,
                        )
            except SoldeInsuffisantError:
                logger.warning(
                    "transcrire_audio_task: solde insuffisant post-completion job=%s",
                    job_id,
                )
            except Exception as erreur_debit_audio:
                logger.error(
                    "transcrire_audio_task: erreur debit credits job=%s — %s",
                    job_id, erreur_debit_audio,
                )

        # Notifier le navigateur que la transcription est terminee
        # / Notify the browser that transcription is complete
        envoyer_progression_websocket(nom_groupe_transcription, "terminee", {
            "status": "completed",
            "message": f"Transcription terminée — {len(segments_transcrits)} segments",
            "resultat": {"page_id": page_associee.pk, "segments": len(segments_transcrits)},
        })

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

        # Notifier le navigateur de l'erreur
        # / Notify the browser of the error
        envoyer_progression_websocket(nom_groupe_transcription, "terminee", {
            "status": "error",
            "message": f"Erreur de transcription : {message_erreur[:200]}",
            "resultat": {},
        })

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

        # Appel au LLM via la couche unifiee / Call LLM via unified layer
        from core.llm_providers import appeler_llm
        texte_reformule = appeler_llm(modele_ia, message_complet)

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

        # Notifier le navigateur que la reformulation est terminee
        # / Notify the browser that reformulation is complete
        envoyer_progression_websocket(f"tache_{self.request.id}", "terminee", {
            "status": "completed",
            "message": "Reformulation terminée",
            "resultat": {"entity_id": entity_id},
        })

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

        # Appel au LLM via la couche unifiee / Call LLM via unified layer
        from core.llm_providers import appeler_llm
        texte_restitution = appeler_llm(modele_ia, message_complet)

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

        # Notifier le navigateur que la restitution est terminee
        # / Notify the browser that restitution is complete
        envoyer_progression_websocket(f"tache_{self.request.id}", "terminee", {
            "status": "completed",
            "message": "Restitution du débat terminée",
            "resultat": {"entity_id": entity_id},
        })

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


def _construire_prompt_synthese(page, dernier_job_analyse):
    """
    Construit le prompt utilisateur pour la synthese deliberative.
    Rassemble texte original + hypostases triees par statut + commentaires.
    / Builds the user prompt for deliberative synthesis.
    Gathers original text + hypostases sorted by status + comments.
    """
    from django.db.models import Case, Value, When
    from hypostasis_extractor.models import ExtractedEntity

    # Recuperer les entites du dernier job d'analyse, exclure non_pertinent et masquees
    # / Get entities from latest analysis job, exclude non_pertinent and hidden
    entites_du_job = ExtractedEntity.objects.filter(
        job=dernier_job_analyse,
        masquee=False,
    ).exclude(
        statut_debat="non_pertinent",
    ).prefetch_related("commentaires__user").order_by(
        Case(
            When(statut_debat="consensuel", then=Value(0)),
            When(statut_debat="discutable", then=Value(1)),
            When(statut_debat="discute", then=Value(2)),
            When(statut_debat="controverse", then=Value(3)),
            When(statut_debat="nouveau", then=Value(4)),
            default=Value(5),
        ),
    )

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

        # Commentaires / Comments
        lignes_commentaires = []
        for commentaire in entite.commentaires.all():
            nom_auteur = commentaire.user.username if commentaire.user else "Anonyme"
            lignes_commentaires.append(f'  - {nom_auteur} : "{commentaire.commentaire}"')

        # Assemblage du bloc / Block assembly
        bloc = f'**[{statut_affiche}] {classe_hypostase} — {resume_affiche}**\n'
        bloc += f'Citation : "{texte_citation}"\n'
        if resume_ia:
            bloc += f'Résumé IA : "{resume_ia}"\n'
        if lignes_commentaires:
            bloc += "Commentaires :\n" + "\n".join(lignes_commentaires) + "\n"

        blocs_entites.append(bloc)

    # Assemblage final du prompt / Final prompt assembly
    texte_original = page.text_readability or ""
    blocs_formates = "\n\n".join(blocs_entites) if blocs_entites else "(aucune hypostase extraite)"

    prompt_utilisateur = (
        f"=== TEXTE ORIGINAL ===\n{texte_original}\n\n"
        f"=== HYPOSTASES ET DEBAT ===\n{blocs_formates}\n\n"
        f"=== CONSIGNE ===\n"
        f"Produis la synthèse délibérative de ce débat en intégrant les pondérations "
        f"par statut définies dans tes instructions. Le texte produit doit être une "
        f"nouvelle version autonome et lisible du document."
    )

    return prompt_utilisateur


@shared_task(bind=True)
def synthetiser_page_task(self, job_id):
    """
    Tache Celery : lance la synthese deliberative sur une Page.
    Construit un prompt a partir du texte + hypostases + commentaires,
    appelle le LLM, et cree une Page enfant (nouvelle version).
    / Celery task: runs deliberative synthesis on a Page.
    Builds a prompt from text + hypostases + comments,
    calls the LLM, and creates a child Page (new version).
    """
    from django.utils.html import escape as html_escape

    from core.models import Configuration, Page
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

        # Trouver le dernier job d'analyse complete (pas de synthese)
        # / Find the latest completed analysis job (not a synthesis)
        # NOTE : on utilise __contains au lieu de __est_synthese car .exclude()
        # sur un lookup JSONField standard exclut aussi les lignes ou la cle est absente
        # (le lookup renvoie NULL, et NOT NULL = NULL est falsy).
        # / NOTE: we use __contains instead of __est_synthese because .exclude()
        # on a standard JSONField lookup also excludes rows where the key is absent.
        dernier_job_analyse = ExtractionJob.objects.filter(
            page=page_source, status="completed",
        ).exclude(
            raw_result__contains={"est_synthese": True},
        ).order_by("-created_at").first()

        if not dernier_job_analyse:
            raise ValueError("Aucun job d'analyse termine pour cette page. Lancez d'abord une analyse.")

        # Construire le prompt utilisateur / Build user prompt
        prompt_utilisateur = _construire_prompt_synthese(page_source, dernier_job_analyse)

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

        # Formater en HTML : split paragraphes → balises <p>
        # / Format as HTML: split paragraphs → <p> tags
        paragraphes = texte_synthese.strip().split("\n\n")
        html_synthese = "\n".join(
            f"<p>{html_escape(paragraphe.strip())}</p>"
            for paragraphe in paragraphes
            if paragraphe.strip()
        )
        texte_brut = texte_synthese.strip()

        # Creer la Page enfant (nouvelle version) / Create child Page (new version)
        page_racine = page_source.page_racine
        prochain_numero = page_racine.restitutions.count() + 2
        hash_contenu = hashlib.sha256(texte_brut.encode("utf-8")).hexdigest()

        page_synthese = Page.objects.create(
            parent_page=page_racine,
            version_number=prochain_numero,
            version_label="Synthèse délibérative",
            dossier=page_racine.dossier,
            source_type=page_racine.source_type,
            url=None,
            title=page_racine.title,
            html_original=html_synthese,
            html_readability=html_synthese,
            text_readability=texte_brut,
            content_hash=hash_contenu,
            owner=page_source.owner,
        )

        # Stocker page_synthese_id dans raw_result pour le polling
        # / Store page_synthese_id in raw_result for polling
        donnees_resultat = job_synthese.raw_result or {}
        donnees_resultat["page_synthese_id"] = page_synthese.pk
        donnees_resultat["version_number"] = prochain_numero
        job_synthese.raw_result = donnees_resultat
        job_synthese.status = "completed"
        job_synthese.save(update_fields=["raw_result", "status"])

        duree = time.time() - debut_traitement
        logger.info(
            "synthetiser_page_task: termine job=%s page_synthese=%s en %.1fs — %d chars",
            job_id, page_synthese.pk, duree, len(texte_synthese),
        )

        # Notifier le navigateur via WebSocket
        # / Notify browser via WebSocket
        envoyer_progression_websocket(f"tache_{self.request.id}", "terminee", {
            "status": "completed",
            "message": "Synthèse délibérative terminée",
            "resultat": {"page_synthese_id": page_synthese.pk},
        })

        # Debit post-completion (PHASE-26h) — debiter le compte du proprietaire
        # Utilise le modele IA pour estimer le cout reel a partir des tokens
        # / Post-completion debit (PHASE-26h) — debit owner's account
        # / Uses the AI model to estimate real cost from tokens
        from django.conf import settings as django_settings
        if django_settings.STRIPE_ENABLED:
            try:
                from core.models import CreditAccount, SoldeInsuffisantError
                tokens_input_estimes = len(message_complet) // 4
                tokens_output_estimes = len(texte_synthese) // 4
                cout_reel = modele_ia.estimer_cout_euros(
                    tokens_input_estimes, tokens_output_estimes,
                ) if hasattr(modele_ia, 'estimer_cout_euros') else None

                if cout_reel and cout_reel > 0:
                    proprietaire_synthese = page_source.owner or (
                        page_source.dossier.owner if page_source.dossier else None
                    )
                    if proprietaire_synthese and not proprietaire_synthese.is_superuser:
                        compte_credits = CreditAccount.get_ou_creer(proprietaire_synthese)
                        compte_credits.debiter(
                            montant=cout_reel,
                            extraction_job=job_synthese,
                            description=f"Synthèse #{job_synthese.pk} — {tokens_input_estimes}+{tokens_output_estimes} tokens",
                        )
                        logger.info(
                            "synthetiser_page_task: debite %s EUR du compte de %s pour job=%s",
                            cout_reel, proprietaire_synthese.username, job_id,
                        )
            except SoldeInsuffisantError:
                logger.warning(
                    "synthetiser_page_task: solde insuffisant post-completion job=%s",
                    job_id,
                )
            except Exception as erreur_credits:
                logger.error(
                    "synthetiser_page_task: erreur debit credits job=%s — %s",
                    job_id, erreur_credits,
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

    # Passer le job en PROCESSING
    # / Set job to PROCESSING
    job_extraction.status = ExtractionJobStatus.PROCESSING
    job_extraction.error_message = None
    job_extraction.save(update_fields=["status", "error_message"])

    # Notifier le navigateur que l'analyse a demarre
    # / Notify the browser that analysis has started
    nom_groupe_analyse = f"tache_{self.request.id}"
    envoyer_progression_websocket(nom_groupe_analyse, "progression", {
        "pourcentage": 5,
        "message": "Analyse IA démarrée",
        "status": "en_cours",
    })

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
        # / Delete old entities BEFORE starting extraction (re-extraction case)
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
            Cree les entites en DB, signale le front pour rafraichir, met a jour la progression.
            / Called after each resolve()+align() cycle for a LangExtract chunk.
            / Creates entities in DB, signals front to refresh, updates progress.

            LOCALISATION : front/tasks.py (closure dans analyser_page_task)

            FLUX :
            1. Recoit les extractions alignees depuis AnnotateurAvecProgression
            2. Cree un ExtractedEntity en DB pour chaque extraction
            3. Envoie rafraichir_drawer WS → le JS recharge le drawer depuis la DB
            4. Envoie analyse_progression WS → la barre de progression se met a jour
            5. Sauvegarde entities_count → rafraichit updated_at pour le timeout

            COMMUNICATION :
            Recoit : appel direct depuis AnnotateurAvecProgression._annotate_documents_single_pass
            Emet : rafraichir_drawer + analyse_progression via envoyer_progression_websocket
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

            # Signaler au front qu'il y a de nouvelles entites en DB (une fois par chunk).
            # Le consumer envoie un hx-get auto-load vers analyse_status?cartes_only=1
            # qui met a jour uniquement les cartes (#drawer-cartes-liste) sans ecraser
            # le bandeau de progression (#barre-progression-analyse).
            # / Notify the front that new entities are in DB (once per chunk).
            # / Consumer sends auto-load hx-get to analyse_status?cartes_only=1
            # / which updates only the cards (#drawer-cartes-liste) without overwriting
            # / the progress banner (#barre-progression-analyse).
            if identifiant_utilisateur:
                envoyer_progression_websocket(
                    f"notifications_user_{identifiant_utilisateur}",
                    "rafraichir_drawer",
                    {"page_id": job_extraction.page_id},
                )

            # Mettre a jour la progression dans le panneau E.
            # Le pourcentage est base sur les caracteres traites par rapport au total.
            # / Update progress in the E panel.
            # / Percentage is based on chars processed vs total.
            pourcentage = 5 + int(
                90 * caracteres_traites / longueur_texte_total
            ) if longueur_texte_total > 0 else 50

            if identifiant_utilisateur:
                # Construire le message de progression, avec warnings si presents
                # / Build progress message, with warnings if any
                message_progression = f"{nombre_entites_creees} entités trouvées"
                if warnings_chunk:
                    message_progression += " — " + " | ".join(warnings_chunk)

                envoyer_progression_websocket(
                    f"notifications_user_{identifiant_utilisateur}",
                    "analyse_progression",
                    {
                        "pourcentage": pourcentage,
                        "message": message_progression,
                        "chunk_courant": numero_chunk_courant,
                        "chunks_total": nombre_chunks_estime,
                    },
                )

            # Rafraichir updated_at pour le detecteur de timeout dans analyse_status.
            # Le polling verifie updated_at toutes les 3s. Si pas de save() depuis 10min,
            # il considere le job comme bloque.
            # / Refresh updated_at for the timeout detector in analyse_status.
            # / Polling checks updated_at every 3s. If no save() for 10min, job is stalled.
            job_extraction.entities_count = nombre_entites_creees
            job_extraction.save(update_fields=["entities_count"])

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

        # Debit post-completion (PHASE-26h) — debiter le compte du proprietaire
        # si STRIPE_ENABLED et cout_reel_euros disponible
        # / Post-completion debit (PHASE-26h) — debit owner's account
        # if STRIPE_ENABLED and cout_reel_euros available
        from django.conf import settings as django_settings
        if django_settings.STRIPE_ENABLED and job_extraction.cout_reel_euros:
            try:
                from core.models import CreditAccount, SoldeInsuffisantError
                proprietaire_page = page.owner or (
                    page.dossier.owner if page.dossier else None
                )
                if proprietaire_page and not proprietaire_page.is_superuser:
                    compte_credits_proprietaire = CreditAccount.get_ou_creer(proprietaire_page)
                    compte_credits_proprietaire.debiter(
                        montant=job_extraction.cout_reel_euros,
                        extraction_job=job_extraction,
                        description=f"Analyse #{job_extraction.pk} — {job_extraction.name}",
                    )
                    logger.info(
                        "analyser_page_task: debite %s EUR du compte de %s pour job=%s",
                        job_extraction.cout_reel_euros,
                        proprietaire_page.username,
                        job_id,
                    )
            except SoldeInsuffisantError:
                logger.warning(
                    "analyser_page_task: solde insuffisant post-completion pour job=%s "
                    "(l'analyse est deja faite, pas de blocage)",
                    job_id,
                )
            except Exception as erreur_debit:
                logger.error(
                    "analyser_page_task: erreur debit credits job=%s — %s",
                    job_id, erreur_debit,
                )

        logger.info(
            "analyser_page_task: termine job=%s — %d entites en %.1fs",
            job_id, nombre_entites_creees, duree_traitement,
        )

        # Notifier le navigateur que l'analyse est terminee
        # / Notify the browser that analysis is complete
        envoyer_progression_websocket(nom_groupe_analyse, "terminee", {
            "status": "completed",
            "message": f"Analyse terminée — {nombre_entites_creees} entités extraites",
            "resultat": {"job_id": job_id, "entites": nombre_entites_creees},
        })

        # Envoyer aussi via le NotificationConsumer pour que le drawer se mette a jour.
        # Le consumer renvoie un OOB qui declenche le chargement du drawer final.
        # / Also send via NotificationConsumer so the drawer updates.
        # / The consumer returns an OOB that triggers loading the final drawer.
        if identifiant_utilisateur:
            envoyer_progression_websocket(
                f"notifications_user_{identifiant_utilisateur}",
                "analyse_terminee",
                {
                    "page_id": page_associee.pk,
                    "job_id": job_id,
                    "nombre_entites": nombre_entites_creees,
                },
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

        # Notifier le navigateur de l'erreur d'analyse
        # / Notify the browser of the analysis error
        envoyer_progression_websocket(nom_groupe_analyse, "terminee", {
            "status": "error",
            "message": f"Erreur d'analyse : {message_erreur[:200]}",
            "resultat": {},
        })

        # Envoyer aussi via le NotificationConsumer pour mettre a jour le drawer
        # / Also send via NotificationConsumer to update the drawer
        if identifiant_utilisateur:
            envoyer_progression_websocket(
                f"notifications_user_{identifiant_utilisateur}",
                "analyse_terminee",
                {
                    "page_id": page_associee.pk,
                    "job_id": job_id,
                    "erreur": True,
                },
            )
