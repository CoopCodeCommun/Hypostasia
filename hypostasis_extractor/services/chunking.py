"""
Construit les chunks envoyes a LangExtract, alignes sur les elements.
/ Builds the chunks sent to LangExtract, aligned on elements.

LOCALISATION : hypostasis_extractor/services/chunking.py

Implemente la section 4.1 de SPEC-ancrage-par-element-v2.md (phase C).

DEUX REGLES, DE PRIORITE DIFFERENTE

1. OBLIGATOIRE — on ne coupe JAMAIS au milieu d'un element.
   Mesure citee par la spec : ca coute 1 appel LLM de plus sur 30, et ca
   elimine 100 % des elements coupes en deux (6 sur 6 avec le chunker
   aveugle actuel). Un element coupe en deux, c'est un LLM qui lit une
   demi-phrase et invente la suite.

2. PREFERENCE — si un element ouvre un nouveau sous-titre ET que le chunk
   en cours a deja atteint un plancher, on coupe la, meme si le budget
   n'est pas epuise.
   Ce n'est qu'une preference, jamais une obligation. Mesure : le gain est
   marginal une fois l'alignement sur les elements garanti. Et une
   frontiere DURE ferait des degats : sur le document de test, 7 des 63
   « sous-titres » sont en realite des intros de liste (« L'IA ne doit pas
   remplacer : »). En frontiere dure, ces intros sont coupees de leur
   liste, et le LLM lit des puces sans savoir de quoi elles sont la liste.
   C'est exactement le defaut que l'ancre multi-elements existe pour
   eviter, reintroduit par la frontiere elle-meme.
   / A hard section boundary would cut list intros from their list.
"""

import logging

from .ancrage import SEPARATEUR_DE_JONCTION, construire_la_table_des_offsets

logger = logging.getLogger(__name__)

# Taille maximale visee pour un chunk, en caracteres.
# Reprise de l'ancien moteur (front/tasks.py) pour ne pas changer deux
# variables a la fois. / Same value as the old engine.
BUDGET_MAXIMUM_PAR_CHUNK = 1500

# En dessous de cette taille, on ne coupe pas a un sous-titre : un chunk
# trop petit gaspille un appel LLM.
# / Below this size, we do not cut at a section header.
PLANCHER_AVANT_COUPURE_PREFEREE = 900

# Le label Docling qui signale un sous-titre.
# / The Docling label marking a section header.
LABEL_DE_SECTION = "section_header"


def construire_les_chunks(elements_de_la_page):
    """
    Regroupe les elements d'une page en chunks prets pour LangExtract.
    / Groups a page's elements into chunks ready for LangExtract.

    LOCALISATION : hypostasis_extractor/services/chunking.py

    FLUX D'APPEL :
    1. L'ingestion (phase D) recupere les elements d'une page, tries.
    2. CETTE FONCTION les regroupe en chunks.
    3. Chaque chunk part au LLM, qui rend des spans.
    4. services/ancrage.py croise ces spans avec la table d'offsets rendue
       ici meme, et produit les portions d'ancrage.

    :param elements_de_la_page: les ElementDocument, DANS L'ORDRE DU
        DOCUMENT (page.elements.all() les trie deja par ordre).
    :return: liste de dicts, un par chunk :
        {
          "elements": [ElementDocument, ...],
          "texte": "le texte colle, separe par des sauts de ligne",
          "offsets": {element.pk: (debut, fin)},
        }
        La cle "offsets" est la table attendue par
        decouper_le_span_en_portions_par_element(). On la produit ICI,
        pendant le collage, pour ne pas la recalculer plus tard : recoller
        deux fois le meme texte, c'est deux occasions de se tromper.

    LES ELEMENTS MASQUES SONT EXCLUS
    Un element masque a ete retire du contenu utile (bruit de fond,
    doublon halluciné par la transcription). Il ne part pas au LLM.

    LE CAS DE L'ELEMENT PLUS GROS QUE LE BUDGET — DECISION PRISE

    La regle 1 est obligatoire : on ne coupe pas un element. Un element de
    4000 caracteres part donc seul dans un chunk de 4000 caracteres, qui
    depasse le budget.

    C'est un choix explicite : on laisse LangExtract se debrouiller avec
    les tres gros elements (un tableau serialise, par exemple), plutot que
    d'ajouter un decoupage qui reintroduirait le probleme que l'ancrage
    par element existe pour resoudre — un LLM qui lit un morceau de
    tableau sans savoir de quoi il est le morceau.
    Depasser le budget est un probleme de cout ; couper un element est un
    probleme de sens.
    / Deliberate: LangExtract handles oversized elements. Exceeding the
    budget costs money; cutting an element costs meaning.

    Un avertissement est journalise pour que ces cas restent visibles dans
    les logs, et qu'on puisse mesurer s'ils posent un probleme reel.

    Consequence : avec ce chunker, un chunk ne contient JAMAIS une
    sous-chaine d'element. Le parametre decalages_dans_l_element de
    services/ancrage.py n'est donc jamais utilise en pratique. Il reste en
    place — la section 2.3 de la spec prevoit ce cas, et le supprimer
    rendrait l'algorithme d'intersection faux le jour ou un decoupage
    serait ajoute.
    / decalages_dans_l_element is therefore never used in practice today.
    """
    chunks = []
    elements_du_chunk_en_cours = []

    def taille_du_chunk_en_cours():
        """Taille en caracteres du chunk en cours, separateurs compris.
        / Size in characters of the current chunk, separators included."""
        if not elements_du_chunk_en_cours:
            return 0
        total_des_textes = sum(
            len(element.texte) for element in elements_du_chunk_en_cours
        )
        nombre_de_separateurs = len(elements_du_chunk_en_cours) - 1
        return total_des_textes + nombre_de_separateurs * len(SEPARATEUR_DE_JONCTION)

    def cloturer_le_chunk_en_cours():
        """Colle les textes, note les offsets, et range le chunk.
        / Joins the texts, records offsets, and files the chunk.

        Le collage et la table sont produits par une SEULE fonction,
        construire_la_table_des_offsets (services/ancrage.py). Recoller le
        texte ici avec sa propre boucle donnerait deux versions de la meme
        logique : le jour ou l'une change de separateur et pas l'autre,
        toutes les ancres du document glissent en silence.
        / One single function joins and indexes, to avoid two divergent copies.
        """
        if not elements_du_chunk_en_cours:
            return

        texte_du_chunk, offsets_des_elements = construire_la_table_des_offsets(
            elements_du_chunk_en_cours,
        )

        chunks.append({
            "elements": list(elements_du_chunk_en_cours),
            "texte": texte_du_chunk,
            "offsets": offsets_des_elements,
        })

    for element in elements_de_la_page:
        # Les elements masques ne partent jamais au LLM.
        # / Hidden elements never go to the LLM.
        if element.masque:
            continue

        # Un element seul plus gros que le budget : on previent, mais on ne
        # le coupe pas. La regle 1 prime sur le budget.
        # / A single element bigger than the budget: warn, never cut.
        element_trop_gros = len(element.texte) > BUDGET_MAXIMUM_PAR_CHUNK
        if element_trop_gros:
            logger.warning(
                "Element %s de %s caracteres : depasse a lui seul le budget "
                "de %s. Il part entier dans son propre chunk — on ne coupe "
                "jamais un element (SPEC section 4.1, regle 1).",
                element.pk, len(element.texte), BUDGET_MAXIMUM_PAR_CHUNK,
            )

        if elements_du_chunk_en_cours:
            taille_actuelle = taille_du_chunk_en_cours()
            taille_avec_ce_nouvel_element = (
                taille_actuelle + len(SEPARATEUR_DE_JONCTION) + len(element.texte)
            )

            # Raison 1 : ajouter cet element ferait deborder le budget.
            # / Reason 1: adding this element would blow the budget.
            le_budget_deborderait = (
                taille_avec_ce_nouvel_element > BUDGET_MAXIMUM_PAR_CHUNK
            )

            # Raison 2 : cet element ouvre une section, et le chunk en
            # cours est deja assez gros pour valoir un appel LLM.
            # / Reason 2: this element opens a section and the chunk is big enough.
            cet_element_ouvre_une_section = element.label == LABEL_DE_SECTION
            le_plancher_est_atteint = (
                taille_actuelle >= PLANCHER_AVANT_COUPURE_PREFEREE
            )
            coupure_preferee = cet_element_ouvre_une_section and le_plancher_est_atteint

            if le_budget_deborderait or coupure_preferee:
                cloturer_le_chunk_en_cours()
                elements_du_chunk_en_cours = []

        elements_du_chunk_en_cours.append(element)

    cloturer_le_chunk_en_cours()
    return chunks
