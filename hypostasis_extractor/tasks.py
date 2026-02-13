"""
Taches Celery pour l'entrainement des analyseurs syntaxiques (test LLM).
/ Celery tasks for training syntactic analyzers (LLM test).
"""

import logging
import time

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def entrainer_analyseur_task(self, test_run_id):
    """
    Tache Celery : lance un test LangExtract sur un exemple d'analyseur.
    Le AnalyseurTestRun doit deja exister en status PENDING avec
    analyseur, example, ai_model et prompt_snapshot remplis.
    / Celery task: runs a LangExtract test on an analyzer example.
    The AnalyseurTestRun must already exist in PENDING status with
    analyseur, example, ai_model and prompt_snapshot filled.
    """
    from hypostasis_extractor.models import (
        AnalyseurTestRun, AnalyseurExample, TestRunExtraction,
        ExtractionJobStatus,
    )
    from hypostasis_extractor.services import resolve_model_params
    import langextract as lx

    debut_traitement = time.time()

    # Charger le test run / Load the test run
    try:
        test_run = AnalyseurTestRun.objects.select_related(
            "analyseur", "example", "ai_model",
        ).get(pk=test_run_id)
    except AnalyseurTestRun.DoesNotExist:
        logger.error("entrainer_analyseur_task: test_run_id=%s introuvable", test_run_id)
        return

    analyseur = test_run.analyseur
    exemple_teste = test_run.example

    # Passer le test run en PROCESSING
    # / Set test run to PROCESSING
    test_run.status = ExtractionJobStatus.PROCESSING
    test_run.save(update_fields=["status"])

    logger.info(
        "entrainer_analyseur_task: demarrage test_run=%s analyseur=%s example=%s model=%s",
        test_run_id, analyseur.pk, exemple_teste.pk,
        test_run.ai_model.model_name if test_run.ai_model else "?",
    )

    try:
        # Construire les exemples few-shot SANS l'exemple teste (anti data-leakage)
        # / Build few-shot examples WITHOUT the tested example (anti data-leakage)
        autres_exemples = AnalyseurExample.objects.filter(
            analyseur=analyseur,
        ).exclude(pk=exemple_teste.pk).order_by("order").prefetch_related("extractions__attributes")

        if not autres_exemples.exists():
            # Fallback : inclure l'exemple teste (LangExtract exige >= 1 exemple)
            # / Fallback: include tested example (LangExtract requires >= 1 example)
            logger.warning(
                "entrainer_analyseur_task: aucun autre exemple — fallback sur l'exemple teste",
            )
            autres_exemples = AnalyseurExample.objects.filter(
                pk=exemple_teste.pk,
            ).prefetch_related("extractions__attributes")

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

        # Resoudre les parametres du modele / Resolve model params
        parametres_modele = resolve_model_params(test_run.ai_model)

        # Appel LangExtract / Call LangExtract
        parametres_extraction = {
            "text_or_documents": exemple_teste.example_text,
            "prompt_description": test_run.prompt_snapshot,
            "examples": liste_exemples_langextract,
        }
        parametres_extraction.update(parametres_modele)

        logger.info(
            "entrainer_analyseur_task: appel lx.extract() model=%s text_len=%d examples=%d",
            parametres_extraction.get("model_id", "?"),
            len(exemple_teste.example_text),
            len(liste_exemples_langextract),
        )
        resultat = lx.extract(**parametres_extraction)

        # Creer les TestRunExtraction / Create TestRunExtraction records
        nombre_extractions_creees = 0
        for ordre, extraction in enumerate(resultat.extractions or []):
            intervalle_caracteres = extraction.char_interval
            TestRunExtraction.objects.create(
                test_run=test_run,
                extraction_class=extraction.extraction_class,
                extraction_text=extraction.extraction_text,
                start_pos=intervalle_caracteres.start_pos if intervalle_caracteres else 0,
                end_pos=intervalle_caracteres.end_pos if intervalle_caracteres else 0,
                attributes=extraction.attributes or {},
                order=ordre,
            )
            nombre_extractions_creees += 1

        # Mettre a jour le test run (update_fields pour ne pas ecraser d'autres champs)
        # / Update the test run (update_fields to avoid overwriting other fields)
        duree_traitement = time.time() - debut_traitement
        test_run.status = ExtractionJobStatus.COMPLETED
        test_run.processing_time_seconds = round(duree_traitement, 2)
        test_run.extractions_count = nombre_extractions_creees
        test_run.raw_result = {
            "extractions_count": nombre_extractions_creees,
            "text_length": len(exemple_teste.example_text),
        }
        test_run.save(update_fields=[
            "status", "processing_time_seconds", "extractions_count", "raw_result",
        ])

        logger.info(
            "entrainer_analyseur_task: termine test_run=%s — %d extractions en %.1fs",
            test_run_id, nombre_extractions_creees, duree_traitement,
        )

    except Exception as erreur_entrainement:
        duree_traitement = time.time() - debut_traitement
        message_erreur = str(erreur_entrainement)

        logger.error(
            "entrainer_analyseur_task: erreur test_run=%s — %s",
            test_run_id, message_erreur, exc_info=True,
        )

        test_run.status = ExtractionJobStatus.ERROR
        test_run.error_message = message_erreur
        test_run.processing_time_seconds = round(duree_traitement, 2)
        test_run.save(update_fields=[
            "status", "error_message", "processing_time_seconds",
        ])
