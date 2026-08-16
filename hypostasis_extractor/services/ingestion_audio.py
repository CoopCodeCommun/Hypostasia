"""
Ingestion d'une transcription diarisee en elements de document.
/ Ingesting a diarised transcript into document elements.

LOCALISATION : hypostasis_extractor/services/ingestion_audio.py

CE QUE FAIT CE SERVICE

Il transforme la transcription d'un enregistrement — un JSON diarise,
produit par le modele de transcription — en ElementDocument, pour que le
moteur ELEMENT traite un entretien comme il traite un document ecrit :
un bloc par unite de sens, des idees ancrees dedans.

L'unite de sens d'un enregistrement, c'est le TOUR DE PAROLE.

    {"segments": [
        {"start": 0.0, "end": 2.5, "text": "Bonjour.", "speaker": "Ian"},
        ...
    ]}

POURQUOI LE TOUR DE PAROLE, ET PAS AUTRE CHOSE

C'est la mesure D3 qui tranche (PLAN/archive/mesures-et-recettes/mesure-D3-frontiere-audio-2026-08-10),
pas une intuition : le changement de locuteur fait une MAUVAISE frontiere
de chunk — l'imposer coupe des echanges au milieu et gonfle le nombre
d'appels — mais une EXCELLENTE frontiere d'element, parce qu'un tour de
parole est ce qu'on cite, ce qu'on commente et ce qu'on attribue.

Un tour de plus de 1 500 caracteres est scinde : la regle « on ne coupe
jamais un element pour faire un chunk » resterait sinon impossible a
tenir face a un monologue de dix minutes. La coupe tombe entre deux
phrases, jamais au milieu de l'une.
/ D3 measured it: speaker change is a poor chunk boundary but an
excellent element boundary.

CE QU'IL N'INVENTE PAS

Une diarisation qui ne nomme pas ses locuteurs reste sans locuteur : la
gouttiere affichera un tour de parole sans nom plutot qu'un « Locuteur 1 »
qui n'existe nulle part.
/ An unnamed speaker stays unnamed.
"""

import logging

from django.db import transaction

logger = logging.getLogger(__name__)

# Au-dela de cette longueur, un tour de parole est scinde.
#
# C'est le budget d'un chunk (`BUDGET_MAXIMUM_PAR_CHUNK`, services/
# chunking.py). Un element plus gros que le budget ne pourrait tenir
# dans aucun chunk, et la regle « ne jamais couper un element » ne
# serait plus tenable — c'est le seul motif de la scission.
# / An element larger than a chunk budget breaks the never-cut rule.
BUDGET_MAXIMUM_PAR_ELEMENT_AUDIO = 1500


def ingerer_une_transcription_diarisee(page):
    """
    Cree un element par tour de parole, depuis `page.transcription_raw`.
    / Creates one element per speaker turn.

    LOCALISATION : hypostasis_extractor/services/ingestion_audio.py

    :param page: la Page audio a peupler
    :return: {"elements_crees": N} ou {"erreur": "..."} — jamais une
        exception pour un cas normal, cette fonction est appelee depuis
        une tache Celery qui doit pouvoir rapporter proprement.
    """
    from hypostasis_extractor.services.ingestion_docling import (
        creer_les_elements_d_une_page,
    )

    if page.elements.exists():
        # Meme garde que l'ingestion Docling : re-ingerer detacherait
        # les ancres deja posees. La re-ingestion a son propre service,
        # qui reconnait les elements inchanges par leur empreinte.
        # / Same guard as Docling: re-ingesting would detach anchors.
        logger.warning(
            "Page %s a deja des elements : ingestion audio refusee.", page.pk,
        )
        return {"erreur": "page deja ingeree"}

    tours = _lire_les_tours_de_parole(page.transcription_raw)
    if not tours:
        logger.warning(
            "Page %s : aucune transcription diarisee exploitable.", page.pk,
        )
        return {"erreur": "aucun tour de parole"}

    elements_bruts = []
    for tour in tours:
        elements_bruts.extend(_decouper_un_tour_trop_long(tour))

    with transaction.atomic():
        elements_crees = creer_les_elements_d_une_page(page, elements_bruts)

        # `text_readability` porte la transcription a plat : c'est lui
        # que lit le repli d'affichage d'une page sans bloc, et lui que
        # les estimations de cout prennent quand il n'y a pas d'element.
        # Le laisser vide ferait mentir les deux.
        # / The flat text backs the display fallback and the estimates.
        page.text_readability = "\n\n".join(
            element["texte"] for element in elements_bruts
        )
        page.save(update_fields=["text_readability"])

    logger.info(
        "Page %s : %s element(s) crees depuis %s tour(s) de parole.",
        page.pk, len(elements_crees), len(tours),
    )
    return {"elements_crees": len(elements_crees)}


def _lire_les_tours_de_parole(transcription):
    """
    Rend les tours de parole exploitables d'une transcription.
    / Returns a transcript's usable speaker turns.

    LOCALISATION : hypostasis_extractor/services/ingestion_audio.py

    Un segment sans texte — une respiration, un bruit que la diarisation
    a decoupe — n'est pas un tour de parole : il ne donnera pas de bloc.
    / A diarised silence is not a turn.
    """
    if not isinstance(transcription, dict):
        return []

    segments = transcription.get("segments") or []
    if not isinstance(segments, list):
        return []

    tours = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        texte = (segment.get("text") or "").strip()
        if not texte:
            continue
        tours.append({
            "texte": texte,
            "locuteur": segment.get("speaker") or None,
            "debut": segment.get("start"),
            "fin": segment.get("end"),
        })
    return tours


def _decouper_un_tour_trop_long(tour):
    """
    Rend les elements bruts d'un tour, scinde s'il depasse le budget.
    / Returns a turn's raw elements, split if it exceeds the budget.

    LOCALISATION : hypostasis_extractor/services/ingestion_audio.py

    LA COUPE TOMBE ENTRE DEUX PHRASES

    Couper au caractere pres donnerait des blocs qui commencent au
    milieu d'un mot : illisibles, et incitables. On accumule donc les
    phrases jusqu'au budget, et on coupe avant celle qui deborde. Une
    phrase plus longue que le budget a elle seule part telle quelle —
    mieux vaut un bloc trop gros qu'une phrase mutilee.
    / Split between sentences; an oversized lone sentence stays whole.

    Tous les morceaux gardent le locuteur et le minutage du tour : ils
    viennent du meme moment et de la meme bouche.
    / Every piece keeps the turn's speaker and timing.
    """
    provenance = {
        "locuteur": tour["locuteur"],
        "debut": tour["debut"],
        "fin": tour["fin"],
    }

    if len(tour["texte"]) <= BUDGET_MAXIMUM_PAR_ELEMENT_AUDIO:
        return [{
            "texte": tour["texte"], "label": "text", "provenance": provenance,
        }]

    morceaux = []
    phrase_en_cours = []
    longueur = 0
    for phrase in _couper_en_phrases(tour["texte"]):
        if phrase_en_cours and longueur + len(phrase) > BUDGET_MAXIMUM_PAR_ELEMENT_AUDIO:
            morceaux.append(" ".join(phrase_en_cours))
            phrase_en_cours, longueur = [], 0
        phrase_en_cours.append(phrase)
        longueur += len(phrase) + 1
    if phrase_en_cours:
        morceaux.append(" ".join(phrase_en_cours))

    return [
        {"texte": morceau, "label": "text", "provenance": dict(provenance)}
        for morceau in morceaux
    ]


def _couper_en_phrases(texte):
    """
    Coupe un texte en phrases, sur la ponctuation forte.
    / Splits a text into sentences, on strong punctuation.

    LOCALISATION : hypostasis_extractor/services/ingestion_audio.py
    """
    import re

    phrases = re.split(r"(?<=[.!?…])\s+", texte)
    return [phrase for phrase in phrases if phrase.strip()]
