"""
Analyse une page avec le moteur ELEMENT : chunks -> LangExtract -> ancres.
/ Analyses a page with the ELEMENT engine: chunks -> LangExtract -> anchors.

LOCALISATION : hypostasis_extractor/services/analyse_par_element.py

Implemente la section 4 de SPEC-ancrage-par-element-v2.md (phase D).

CE QUI CHANGE PAR RAPPORT AU MOTEUR ANCIEN

Le moteur ANCIEN (front/tasks.py) envoie la page entiere a LangExtract et
laisse son ChunkIterator la decouper. Le decoupage se fait donc a
l'aveugle, au milieu des paragraphes, et les positions rendues sont des
offsets dans le texte global de la page.

Le moteur ELEMENT fait l'inverse : on decoupe NOUS-MEMES, sur les
frontieres d'elements (services/chunking.py), puis on envoie chaque chunk
separement. Les positions rendues sont alors des offsets dans un chunk
dont on connait exactement la composition, et
services/ancrage.py les traduit en portions par element.
/ We chunk ourselves on element boundaries, then send each chunk alone.

POURQUOI ON NEUTRALISE LE CHUNKER DE LANGEXTRACT

LangExtract redecoupe tout texte qui depasse son max_char_buffer, jusqu'au
niveau du token si besoin. On lui passe donc un max_char_buffer plus grand
que notre chunk : il le recoit tel quel, en un seul morceau.

CE QUE CA NE FAIT PAS : ca ne protege PAS les positions. Verifie dans le
code de langextract (annotation.py passe char_offset a resolver.align) :
meme quand il redecoupe, les positions rendues sont re-basees dans le
texte qu'on a envoye. Elles resteraient donc justes.

CE QUE CA FAIT VRAIMENT : le LLM lit chaque element ENTIER, dans son
contexte. Un element coupe en deux morceaux analyses separement, c'est un
modele qui lit une demi-phrase et complete de lui-meme — le defaut que
l'ancrage par element existe pour eviter, reintroduit une couche plus bas.
L'enjeu est la qualite de la lecture, pas l'exactitude des offsets.
/ Neutralizing the chunker does NOT protect positions (they are re-based
anyway). It ensures the model reads each element whole, in context.

POURQUOI UNE EXTRACTION NE PEUT PAS ENJAMBER DEUX CHUNKS

Le LLM ne voit qu'un chunk a la fois : il ne peut pas rendre un span qui
deborde sur le suivant. Chaque ExtractedEntity est donc creee avec TOUTES
ses portions en un seul appel, numerotees 0..N d'un coup. La contrainte
d'unicite (extraction, ordre_dans_extraction) ne peut pas etre violee par
un second appel qui repartirait de zero.
/ The LLM sees one chunk at a time, so all portions of an extraction are
always created in a single pass.
"""

import logging

from django.db import transaction

from ..models import (
    AncrageExtraction,
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)
from .ancrage import decouper_le_span_en_portions_par_element
from .chunking import construire_les_chunks

logger = logging.getLogger(__name__)

# Marge ajoutee a la taille du chunk pour calculer max_char_buffer.
# Il suffit que la valeur depasse la taille du chunk : LangExtract ne
# redecoupe alors rien du tout.
# / Any value above the chunk size prevents LangExtract from re-cutting.
MARGE_POUR_NEUTRALISER_LE_CHUNKER = 1000


def analyser_une_page_par_element(page, job_extraction, appeler_le_llm=None):
    """
    Analyse tous les elements d'une page et cree les ancres.
    / Analyses every element of a page and creates the anchors.

    LOCALISATION : hypostasis_extractor/services/analyse_par_element.py

    FLUX :
    1. On recupere les elements du contenu utile, dans l'ordre.
    2. services/chunking.py les groupe en chunks, sans en couper aucun.
    3. Chaque chunk part au LLM, seul.
    4. Chaque span rendu est traduit en portions par services/ancrage.py.
    5. Une ExtractedEntity et ses AncrageExtraction sont creees.

    :param page: la Page a analyser
    :param job_extraction: l'ExtractionJob qui porte le suivi et le prompt
    :param appeler_le_llm: fonction (texte_du_chunk, job) -> liste de
        {"extraction_class", "extraction_text", "debut", "fin", "attributes"}.
        Injectee pour que la mecanique soit testable sans appel reel.
        Par defaut, appeler_langextract_sur_un_chunk.
        / Injected so the mechanics are testable without a real call.
    :return: {"chunks": int, "extractions": int, "portions": int,
              "chunks_en_erreur": int}

    UN CHUNK QUI ECHOUE NE FAIT PAS TOMBER L'ANALYSE

    Un appel LLM peut echouer pour mille raisons passageres. Perdre les
    quinze chunks deja traites — et payes — parce que le seizieme a
    echoue serait absurde. On journalise, on compte, et on continue.
    / A failed chunk does not discard the fifteen already paid for.
    """
    if appeler_le_llm is None:
        appeler_le_llm = appeler_langextract_sur_un_chunk

    # ON REPART D'UNE PAGE PROPRE POUR CE JOB.
    #
    # Sans ca, relancer un job — retry Celery apres un worker tue, ou
    # relance manuelle d'un job en erreur — ajouterait une seconde serie
    # d'extractions a cote de la premiere. Les cartes apparaitraient en
    # double, et entities_count, ecrit avec le compte de la derniere
    # passe seulement, deviendrait faux.
    #
    # Le moteur ANCIEN fait la meme chose (front/tasks.py).
    # / Re-running a job would otherwise duplicate every extraction.
    nombre_d_extractions_purgees = job_extraction.entities.count()
    if nombre_d_extractions_purgees:
        # Garde § 4.2 : une note citee par une synthese dirigee ne se
        # re-analyse pas — refus PROPRE avant la purge, pas une exception
        # au milieu. / § 4.2 guard: clean refusal before the purge.
        from core.services.synthese import (
            verifier_qu_aucune_dirigee_ne_cite_les_extractions,
        )
        verifier_qu_aucune_dirigee_ne_cite_les_extractions(
            job_extraction.entities.all()
        )
        job_extraction.entities.all().delete()
        logger.info(
            "Job %s relance : %s extraction(s) de la passe precedente "
            "supprimee(s) avant de recommencer.",
            job_extraction.pk, nombre_d_extractions_purgees,
        )

    elements_du_contenu_utile = list(
        page.elements.filter(masque=False).order_by("ordre")
    )
    chunks = construire_les_chunks(elements_du_contenu_utile)

    resultat = {
        "chunks": len(chunks),
        "extractions": 0,
        "portions": 0,
        "chunks_en_erreur": 0,
        "extractions_refusees": 0,
    }

    if not chunks:
        logger.info(
            "Page %s : aucun element a analyser (page vide ou tout masque).",
            page.pk,
        )
        return resultat

    for numero_du_chunk, chunk in enumerate(chunks):
        # Battement de coeur (relecture BR-C) : la vue tue tout job
        # PROCESSING dont updated_at n'a pas bouge depuis 5 minutes.
        # Sans ce battement par chunk, une longue analyse se faisait
        # marquer « Timeout » en plein travail, puis relancer en double.
        # / Heartbeat: refresh updated_at before each chunk, or the
        # staleness check kills a perfectly healthy long analysis.
        job_extraction.save(update_fields=["updated_at"])
        try:
            extractions_brutes = appeler_le_llm(chunk["texte"], job_extraction)
        except Exception as erreur:
            # On attrape large : une panne LLM ne doit pas faire perdre le
            # travail deja fait. / A broad catch: keep the work already done.
            resultat["chunks_en_erreur"] += 1
            logger.warning(
                "Page %s, chunk %s/%s : l'appel au LLM a echoue (%s). "
                "Les autres chunks continuent.",
                page.pk, numero_du_chunk + 1, len(chunks), erreur,
            )
            continue

        for extraction_brute in extractions_brutes:
            try:
                nombre_de_portions = _creer_une_extraction_et_ses_ancres(
                    extraction_brute, chunk, job_extraction,
                )
            except Exception as erreur:
                # Les gardes de services/ancrage.py levent sur une entree
                # incoherente — un span a l'envers, des bornes hors du
                # texte. C'est voulu : mieux vaut refuser une extraction
                # que l'ancrer faux. Mais une extraction douteuse ne doit
                # pas emporter les quinze chunks deja analyses.
                # / A single bad extraction must not discard the whole run.
                resultat["extractions_refusees"] += 1
                logger.warning(
                    "Page %s, chunk %s : extraction refusee (%s) — %r",
                    page.pk, numero_du_chunk + 1, erreur,
                    extraction_brute.get("extraction_text", "")[:60],
                )
                continue

            if nombre_de_portions:
                resultat["extractions"] += 1
                resultat["portions"] += nombre_de_portions

    logger.info(
        "Page %s analysee par le moteur ELEMENT : %s chunk(s), "
        "%s extraction(s), %s portion(s), %s chunk(s) en erreur.",
        page.pk, resultat["chunks"], resultat["extractions"],
        resultat["portions"], resultat["chunks_en_erreur"],
    )
    return resultat


def _creer_une_extraction_et_ses_ancres(extraction_brute, chunk, job_extraction):
    """
    Cree une ExtractedEntity et ses portions d'ancrage.
    / Creates an ExtractedEntity and its anchor portions.

    LOCALISATION : hypostasis_extractor/services/analyse_par_element.py

    :param extraction_brute: le dict rendu par l'appel au LLM
    :param chunk: le chunk d'ou vient l'extraction (elements + offsets)
    :param job_extraction: le job auquel rattacher l'extraction
    :return: le nombre de portions creees, 0 si l'extraction est ignoree

    UNE EXTRACTION SANS ANCRE N'EST PAS CREEE

    Si le span rendu ne recoupe aucun element — il tombe entierement dans
    un separateur, ou le LLM a rendu des positions incoherentes — on ne
    cree rien. Le moteur ANCIEN, lui, persiste ces cas en start=0, end=0 :
    une ancre qui pointe le debut du document, donc une ancre fausse que
    rien ne signale. On prefere ne rien ecrire.
    / The old engine persists unalignable extractions at 0-0, a silently
    wrong anchor. Here, nothing is written at all.
    """
    debut_dans_le_chunk = extraction_brute.get("debut")
    fin_dans_le_chunk = extraction_brute.get("fin")

    positions_absentes = debut_dans_le_chunk is None or fin_dans_le_chunk is None
    if positions_absentes:
        logger.debug(
            "Extraction sans position rendue par le LLM, ignoree : %r",
            extraction_brute.get("extraction_text", "")[:60],
        )
        return 0

    portions = decouper_le_span_en_portions_par_element(
        span_dans_le_chunk=(debut_dans_le_chunk, fin_dans_le_chunk),
        elements_du_chunk=chunk["elements"],
        offsets_des_elements_dans_le_chunk=chunk["offsets"],
    )

    if not portions:
        logger.debug(
            "Extraction dont le span ne recoupe aucun element, ignoree : %r",
            extraction_brute.get("extraction_text", "")[:60],
        )
        return 0

    # LES ATTRIBUTS SONT NORMALISES AVANT D'ETRE STOCKES.
    #
    # Le moteur ANCIEN applique normaliser_attributs_entite : elle ramene
    # les cles a leur forme canonique (« hypostases »), tronque les
    # valeurs a 500 caracteres et en garde trois au plus — une protection
    # contre les boucles de repetition que les modeles produisent parfois.
    #
    # Sans elle, les attributs arrivent bruts. La vue d'alignement
    # (front/views_alignement.py) lit la cle canonique sans repli : elle
    # ne verrait rien. / Without it, the alignment view finds nothing.
    from front.normalisation import normaliser_attributs_entite

    attributs_normalises = normaliser_attributs_entite(
        extraction_brute.get("attributes") or {},
    )

    with transaction.atomic():
        extraction = ExtractedEntity.objects.create(
            job=job_extraction,
            extraction_class=extraction_brute.get("extraction_class", ""),
            extraction_text=extraction_brute.get("extraction_text", ""),
            attributes=attributs_normalises,
            # Les anciens champs restent obligatoires : les deux moteurs
            # coexistent. On y met les offsets DANS LE CHUNK, qui n'ont
            # pas de sens hors de lui — le moteur ELEMENT ne les lit
            # jamais, il lit les portions.
            # / Old fields stay mandatory; the ELEMENT engine never reads them.
            start_char=debut_dans_le_chunk,
            end_char=fin_dans_le_chunk,
        )

        for portion in portions:
            AncrageExtraction.objects.create(extraction=extraction, **portion)

        # LE TAG D'HYPOSTASE EST RATTACHE, COMME DANS LE MOTEUR ANCIEN.
        #
        # hypostasis_tag est affiche comme badge sur chaque carte
        # d'extraction (entity_card.html). Sans ce rattachement, les
        # extractions du moteur ELEMENT n'auraient jamais de badge :
        # une regression visible, et silencieuse.
        # / Without this, ELEMENT extractions would never get their badge.
        from . import _try_map_to_hypostasis

        try:
            tag_trouve = _try_map_to_hypostasis(extraction)
        except Exception as erreur:
            # Un echec de mapping ne doit pas faire perdre l'extraction et
            # son ancrage, qui sont, eux, corrects.
            # / A mapping failure must not discard a correct extraction.
            tag_trouve = None
            logger.warning(
                "Mapping hypostase impossible pour l'extraction %s : %s",
                extraction.pk, erreur,
            )

        if tag_trouve is not None:
            extraction.hypostasis_tag = tag_trouve
            extraction.save(update_fields=["hypostasis_tag"])

    return len(portions)


def appeler_langextract_sur_un_chunk(texte_du_chunk, job_extraction):
    """
    Envoie UN chunk a LangExtract et rend ses extractions.
    / Sends ONE chunk to LangExtract and returns its extractions.

    LOCALISATION : hypostasis_extractor/services/analyse_par_element.py

    :param texte_du_chunk: le texte a analyser, deja decoupe par nos soins
    :param job_extraction: le job, qui porte le prompt et le modele
    :return: liste de dicts {"extraction_class", "extraction_text",
             "debut", "fin", "attributes"}, positions relatives AU CHUNK

    POURQUOI max_char_buffer EST CALCULE SUR LA TAILLE DU CHUNK

    Voir l'en-tete du fichier : sans ca, LangExtract redecoupe notre chunk
    et la coupe au milieu d'un element reapparait une couche plus bas.
    / Without this, LangExtract re-cuts our carefully cut chunk.
    """
    import langextract as lx

    from . import _construire_exemples_langextract, resolve_model_params

    exemples = _construire_les_exemples_du_job(job_extraction)
    parametres_du_modele = resolve_model_params(job_extraction.ai_model)

    # Plus grand que le chunk : LangExtract ne redecoupe rien.
    # / Larger than the chunk: LangExtract re-cuts nothing.
    taille_a_ne_pas_decouper = (
        len(texte_du_chunk) + MARGE_POUR_NEUTRALISER_LE_CHUNKER
    )

    parametres_d_extraction = {
        "text_or_documents": texte_du_chunk,
        "prompt_description": job_extraction.prompt_description,
        "examples": exemples,
        "max_char_buffer": taille_a_ne_pas_decouper,

        # fetch_urls=False EST OBLIGATOIRE ICI.
        #
        # Par defaut, lx.extract TELECHARGE le texte qu'on lui passe s'il
        # ressemble a une URL — une chaine sans espace commencant par
        # http:// ou https://. Un element de document qui est un lien nu
        # sur sa propre ligne suffit a declencher ce comportement.
        #
        # Deux consequences, toutes deux graves :
        #  - les positions rendues seraient des offsets dans la page
        #    telechargee, pas dans notre chunk. L'intersection les
        #    rognerait aux bornes de l'element et creerait des ancres
        #    fausses, en silence.
        #  - le serveur irait chercher n'importe quelle URL presente dans
        #    un document ingere, sur simple depot de fichier.
        # / By default lx.extract DOWNLOADS a text that looks like a URL.
        # That would both fake the anchors and turn ingested documents
        # into server-side requests.
        "fetch_urls": False,

        # Un JSON tronque a max_output_tokens ne doit pas faire perdre le
        # chunk entier : le resolver rend ce qu'il a pu lire. La spec
        # section 4.2 signale que la troncature reste possible meme avec
        # un schema structure.
        #
        # Ce reglage n'est PAS un parametre direct de lx.extract : il se
        # passe par resolver_params, qui est transmis au resolver.
        # / Not a direct parameter: it goes through resolver_params.
        "resolver_params": {"suppress_parse_errors": True},

        **parametres_du_modele,
    }

    resultat = lx.extract(**parametres_d_extraction)

    return _traduire_les_extractions_de_langextract(resultat)


def _construire_les_exemples_du_job(job_extraction):
    """
    Recupere les exemples few-shot de l'analyseur rattache a un job.
    / Fetches the few-shot examples of a job's analyzer.

    LOCALISATION : hypostasis_extractor/services/analyse_par_element.py

    L'analyseur n'est pas une cle etrangere sur ExtractionJob : il est
    range dans raw_result["analyseur_id"]. C'est la convention du moteur
    ANCIEN (front/tasks.py), reprise ici telle quelle pour que les deux
    moteurs puissent lire les memes jobs.
    / The analyzer lives in raw_result["analyseur_id"], as in the old engine.

    UN JOB SANS EXEMPLE NE PEUT PAS TOURNER

    LangExtract refuse de travailler sans au moins un exemple : il leve
    « Examples are required for reliable extraction ». Verifie par un
    appel reel — sans cette garde, l'erreur remonterait telle quelle, sans
    dire QUEL job est mal configure ni pourquoi.

    On leve donc nous-memes, avec un message qui nomme le job et
    l'analyseur manquant.
    / LangExtract refuses to run without examples; we raise a clear error
    naming the job instead of letting an opaque one bubble up.

    :param job_extraction: l'ExtractionJob
    :return: la liste des exemples LangExtract
    :raises ValueError: si le job n'a pas d'analyseur, ou aucun exemple
    """
    from ..models import AnalyseurSyntaxique
    from . import _construire_exemples_langextract

    identifiant_de_l_analyseur = (job_extraction.raw_result or {}).get(
        "analyseur_id",
    )
    if not identifiant_de_l_analyseur:
        raise ValueError(
            f"Le job {job_extraction.pk} n'a pas d'analyseur "
            f"(raw_result['analyseur_id'] absent). LangExtract exige au "
            f"moins un exemple few-shot pour extraire."
        )

    analyseur = AnalyseurSyntaxique.objects.filter(
        pk=identifiant_de_l_analyseur,
    ).first()
    if analyseur is None:
        raise ValueError(
            f"Le job {job_extraction.pk} pointe l'analyseur "
            f"{identifiant_de_l_analyseur}, qui n'existe plus."
        )

    exemples = _construire_exemples_langextract(analyseur)
    if not exemples:
        raise ValueError(
            f"L'analyseur « {analyseur} » n'a aucun exemple. LangExtract "
            f"exige au moins un exemple few-shot pour extraire de facon "
            f"fiable."
        )

    return exemples


def _traduire_les_extractions_de_langextract(resultat_de_langextract):
    """
    Traduit la reponse de LangExtract en dicts simples.
    / Translates the LangExtract response into plain dicts.

    LOCALISATION : hypostasis_extractor/services/analyse_par_element.py

    On ne fait pas circuler les objets de LangExtract dans le reste du
    code : une bibliotheque qui change de version ne doit pas obliger a
    reecrire l'ancrage. Cette fonction est la seule frontiere.
    / A single translation boundary keeps LangExtract's types out of the
    rest of the code.

    Une extraction dont char_interval est absent n'a pas pu etre alignee
    dans le texte. On rend debut=None : l'appelant l'ignorera plutot que
    de l'ancrer au debut du document.
    / An unaligned extraction yields debut=None and will be skipped.
    """
    extractions_traduites = []

    for extraction in getattr(resultat_de_langextract, "extractions", []) or []:
        intervalle = getattr(extraction, "char_interval", None)
        debut = getattr(intervalle, "start_pos", None) if intervalle else None
        fin = getattr(intervalle, "end_pos", None) if intervalle else None

        extractions_traduites.append({
            "extraction_class": getattr(extraction, "extraction_class", "") or "",
            "extraction_text": getattr(extraction, "extraction_text", "") or "",
            "debut": debut,
            "fin": fin,
            "attributes": getattr(extraction, "attributes", None) or {},
        })

    return extractions_traduites


def lancer_l_analyse_d_une_page(page, job_extraction, appeler_le_llm=None):
    """
    Enchaine l'analyse complete d'une page et tient le job a jour.
    / Runs a page's full analysis and keeps the job up to date.

    LOCALISATION : hypostasis_extractor/services/analyse_par_element.py

    C'est le point d'entree que la tache Celery appellera. Il fait passer
    le job par ses etats, pour que la garde d'edition
    (services/garde_edition.py) sache qu'une analyse tourne.

    :param page: la Page a analyser
    :param job_extraction: l'ExtractionJob a suivre
    :param appeler_le_llm: voir analyser_une_page_par_element
    :return: le dictionnaire de resultat de l'analyse
    """
    job_extraction.status = ExtractionJobStatus.PROCESSING
    job_extraction.error_message = None
    # "updated_at" liste explicitement : Django n'applique auto_now qu'aux
    # champs presents dans update_fields, et la garde d'edition s'en sert
    # pour savoir si ce job est encore vivant.
    # / auto_now only applies to fields listed in update_fields.
    job_extraction.save(
        update_fields=["status", "error_message", "updated_at"],
    )

    try:
        resultat = analyser_une_page_par_element(
            page, job_extraction, appeler_le_llm=appeler_le_llm,
        )
    except Exception as erreur:
        job_extraction.status = ExtractionJobStatus.ERROR
        job_extraction.error_message = str(erreur)
        job_extraction.save(
            update_fields=["status", "error_message", "updated_at"],
        )
        logger.exception("Analyse de la page %s interrompue.", page.pk)
        raise

    # UN ECHEC TOTAL N'EST PAS UN SUCCES.
    #
    # analyser_une_page_par_element absorbe les pannes chunk par chunk,
    # pour ne pas perdre le travail deja paye. Mais si TOUS les chunks ont
    # echoue — cle d'API expiree, fournisseur en panne, modele absent — la
    # page n'a rien produit du tout. La marquer COMPLETED afficherait
    # « analyse terminee, 0 extraction » a l'utilisateur, indiscernable
    # d'une page sans rien a extraire.
    # / If EVERY chunk failed, the job failed. "Completed, 0 extractions"
    # would be indistinguishable from a page with nothing to extract.
    tous_les_chunks_ont_echoue = (
        resultat["chunks"] > 0
        and resultat["chunks_en_erreur"] == resultat["chunks"]
    )
    if tous_les_chunks_ont_echoue:
        job_extraction.status = ExtractionJobStatus.ERROR
        job_extraction.error_message = (
            f"Les {resultat['chunks']} chunk(s) de la page ont echoue. "
            f"Aucune extraction n'a pu etre produite. Voir les logs pour "
            f"le detail des erreurs."
        )
        job_extraction.save(
            update_fields=["status", "error_message", "updated_at"],
        )
        logger.error(
            "Page %s : les %s chunks ont echoue, job %s en erreur.",
            page.pk, resultat["chunks"], job_extraction.pk,
        )
        return resultat

    job_extraction.status = ExtractionJobStatus.COMPLETED
    job_extraction.entities_count = resultat["extractions"]
    # Le detail de l'analyse est range dans raw_result : sans ca, le
    # nombre de chunks en erreur ne vit que dans les logs, et personne ne
    # saurait qu'une analyse « terminee » a perdu la moitie de ses chunks.
    # / Persisted, or a partially failed run leaves no trace but logs.
    raw_result_du_job = job_extraction.raw_result or {}
    raw_result_du_job["moteur"] = "element"
    raw_result_du_job["bilan_de_l_analyse"] = resultat
    job_extraction.raw_result = raw_result_du_job
    job_extraction.save(
        update_fields=[
            "status", "entities_count", "raw_result", "updated_at",
        ],
    )
    return resultat
