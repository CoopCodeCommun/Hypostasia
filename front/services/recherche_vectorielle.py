"""
Service de recherche semantique par vecteurs (Zvec + sentence-transformers).
Une collection Zvec par dossier, stockee dans db/zvec/.
/ Semantic vector search service (Zvec + sentence-transformers).
One Zvec collection per folder, stored in db/zvec/.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Singleton du modele d'embedding — charge une seule fois au premier appel
# / Embedding model singleton — loaded once on first call
_modele_embedding = None

# Dimensions du modele all-MiniLM-L6-v2
# / Dimensions for the all-MiniLM-L6-v2 model
DIMENSION_EMBEDDING = 384

# Repertoire de stockage des collections Zvec
# / Storage directory for Zvec collections
CHEMIN_BASE_ZVEC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "db", "zvec",
)


def _get_modele_embedding():
    """
    Charge le modele d'embedding une seule fois (lazy singleton).
    Utilise all-MiniLM-L6-v2 : gratuit, local, ~80 Mo, 384 dimensions.
    / Load embedding model once (lazy singleton).
    Uses all-MiniLM-L6-v2: free, local, ~80 MB, 384 dimensions.
    """
    global _modele_embedding
    if _modele_embedding is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Chargement du modele d'embedding all-MiniLM-L6-v2...")
        _modele_embedding = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Modele d'embedding charge.")
    return _modele_embedding


def _get_ou_creer_collection(dossier_id, lecture_seule=False):
    """
    Ouvre (ou cree) la collection Zvec pour un dossier donne.
    Chaque dossier a sa propre collection dans db/zvec/dossier_{id}/.
    / Open (or create) the Zvec collection for a given folder.
    Each folder has its own collection in db/zvec/dossier_{id}/.
    """
    import zvec

    chemin_collection = os.path.join(CHEMIN_BASE_ZVEC, f"dossier_{dossier_id}")

    option_collection = zvec.CollectionOption(
        read_only=lecture_seule,
        enable_mmap=True,
    )

    # Si la collection existe deja, on l'ouvre
    # / If the collection already exists, open it
    if os.path.exists(chemin_collection):
        collection_ouverte = zvec.open(
            path=chemin_collection,
            option=option_collection,
        )
        return collection_ouverte

    # Sinon, on la cree avec le schema
    # / Otherwise, create it with the schema
    os.makedirs(chemin_collection, exist_ok=True)

    schema_champ_page_id = zvec.FieldSchema(
        name="page_id",
        data_type=zvec.DataType.STRING,
        nullable=False,
    )
    schema_champ_page_title = zvec.FieldSchema(
        name="page_title",
        data_type=zvec.DataType.STRING,
        nullable=True,
    )
    schema_champ_extraction_class = zvec.FieldSchema(
        name="extraction_class",
        data_type=zvec.DataType.STRING,
        nullable=True,
    )
    schema_champ_extraction_text = zvec.FieldSchema(
        name="extraction_text",
        data_type=zvec.DataType.STRING,
        nullable=True,
    )

    schema_vecteur_embedding = zvec.VectorSchema(
        name="embedding",
        data_type=zvec.DataType.VECTOR_FP32,
        dimension=DIMENSION_EMBEDDING,
        index_param=zvec.HnswIndexParam(
            metric_type=zvec.MetricType.COSINE,
        ),
    )

    schema_collection = zvec.CollectionSchema(
        name=f"dossier_{dossier_id}",
        fields=[
            schema_champ_page_id,
            schema_champ_page_title,
            schema_champ_extraction_class,
            schema_champ_extraction_text,
        ],
        vectors=[schema_vecteur_embedding],
    )

    collection_creee = zvec.create_and_open(
        path=chemin_collection,
        schema=schema_collection,
        option=option_collection,
    )

    logger.info(
        "Collection Zvec creee pour dossier_id=%s dans %s",
        dossier_id, chemin_collection,
    )
    return collection_creee


def indexer_entite(entite):
    """
    Calcule l'embedding d'une ExtractedEntity et l'insere dans la collection Zvec du dossier.
    Ne fait rien si l'entite n'appartient pas a un dossier.
    / Compute embedding for an ExtractedEntity and insert it into the folder's Zvec collection.
    Does nothing if the entity doesn't belong to a folder.
    """
    import zvec

    # Remonter : entite → job → page → dossier
    # / Walk up: entity → job → page → folder
    page_de_entite = entite.job.page
    dossier_de_page = page_de_entite.dossier
    if not dossier_de_page:
        logger.debug(
            "indexer_entite: entite=%s ignoree (page sans dossier)",
            entite.pk,
        )
        return

    texte_a_encoder = entite.extraction_text or ""
    if not texte_a_encoder.strip():
        return

    # Calcul de l'embedding / Compute embedding
    modele = _get_modele_embedding()
    vecteur_embedding = modele.encode(texte_a_encoder).tolist()

    # Insertion dans la collection / Insert into collection
    collection = _get_ou_creer_collection(dossier_de_page.pk)

    document_a_inserer = zvec.Doc(
        id=str(entite.pk),
        vectors={"embedding": vecteur_embedding},
        fields={
            "page_id": str(page_de_entite.pk),
            "page_title": page_de_entite.title or "",
            "extraction_class": entite.extraction_class or "",
            "extraction_text": texte_a_encoder[:500],
        },
    )

    resultat_insertion = collection.insert(document_a_inserer)
    collection.optimize()

    logger.debug(
        "indexer_entite: entite=%s indexee dans dossier=%s — %s",
        entite.pk, dossier_de_page.pk, resultat_insertion,
    )


def supprimer_entite(entite):
    """
    Retire une ExtractedEntity de la collection Zvec de son dossier.
    Ne fait rien si l'entite n'appartient pas a un dossier.
    / Remove an ExtractedEntity from its folder's Zvec collection.
    Does nothing if the entity doesn't belong to a folder.
    """
    page_de_entite = entite.job.page
    dossier_de_page = page_de_entite.dossier
    if not dossier_de_page:
        return

    chemin_collection = os.path.join(CHEMIN_BASE_ZVEC, f"dossier_{dossier_de_page.pk}")
    if not os.path.exists(chemin_collection):
        return

    collection = _get_ou_creer_collection(dossier_de_page.pk)
    collection.delete(ids=str(entite.pk))

    logger.debug(
        "supprimer_entite: entite=%s retiree de dossier=%s",
        entite.pk, dossier_de_page.pk,
    )


def rechercher(dossier_id, texte_requete, top_k=10):
    """
    Recherche les entites les plus proches du texte dans la collection Zvec du dossier.
    Retourne une liste de dicts : {entity_id, page_id, page_title, extraction_class, extraction_text, score}.
    / Search for entities closest to the text in the folder's Zvec collection.
    Returns a list of dicts: {entity_id, page_id, page_title, extraction_class, extraction_text, score}.
    """
    import zvec

    chemin_collection = os.path.join(CHEMIN_BASE_ZVEC, f"dossier_{dossier_id}")
    if not os.path.exists(chemin_collection):
        logger.debug(
            "rechercher: pas de collection pour dossier_id=%s", dossier_id,
        )
        return []

    # Calculer l'embedding de la requete / Compute query embedding
    modele = _get_modele_embedding()
    vecteur_requete = modele.encode(texte_requete).tolist()

    # Ouvrir la collection en lecture seule / Open collection read-only
    collection = _get_ou_creer_collection(dossier_id, lecture_seule=True)

    # Lancer la recherche / Run the search
    resultats_bruts = collection.query(
        vectors=zvec.VectorQuery(
            field_name="embedding",
            vector=vecteur_requete,
        ),
        topk=top_k,
    )

    # Formater les resultats / Format results
    resultats_formates = []
    for document_resultat in resultats_bruts:
        champs = document_resultat.fields if hasattr(document_resultat, "fields") else {}
        score_similarite = document_resultat.score if hasattr(document_resultat, "score") else 0.0

        resultats_formates.append({
            "entity_id": int(document_resultat.id),
            "page_id": int(champs.get("page_id", 0)),
            "page_title": champs.get("page_title", ""),
            "extraction_class": champs.get("extraction_class", ""),
            "extraction_text": champs.get("extraction_text", ""),
            "score": round(score_similarite * 100, 1),
        })

    logger.info(
        "rechercher: dossier=%s query='%s' → %d resultats",
        dossier_id, texte_requete[:50], len(resultats_formates),
    )

    return resultats_formates
