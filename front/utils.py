"""
Utilitaires pour l'annotation HTML cote serveur.
/ Server-side HTML annotation utilities.

Principe : on enveloppe le texte exact de chaque extraction dans un <span>
avec classe hl-extraction et data-extraction-id pour surlignage inline + pastille en marge.
/ Principle: wrap the exact extraction text in a <span> with hl-extraction class
and data-extraction-id for inline highlighting + margin dot.

Principe cle : text_readability = texte_extrait.strip()
Les positions des entites (start_char/end_char) sont relatives a text_readability.
On calcule le leading_offset (whitespace en tete du HTML) pour convertir
positions text_readability → positions texte_extrait → positions HTML.
/ Key principle: text_readability = texte_extrait.strip()
Entity positions are relative to text_readability.
We compute leading_offset to convert positions accordingly.
"""

import html as html_module
import logging
import re

logger = logging.getLogger(__name__)

# Regex pour detecter les entites HTML (&amp; &nbsp; &#123; &#x1F; etc.)
# / Regex to detect HTML entities
REGEX_ENTITE_HTML = re.compile(r'&(?:#[xX]?[0-9a-fA-F]+|[a-zA-Z]+);')


def _construire_mapping_text_vers_html(html_brut):
    """
    Parcourt le HTML brut et construit :
    - texte_extrait : le textContent reconstitue (avec whitespace HTML)
    - mapping_debut : dict {text_pos: html_pos} pour chaque position texte

    Logique :
    - Dans un tag <...> : avancer html_pos seulement
    - Dans du texte : avancer les deux compteurs
    - Entites HTML (&amp;, &nbsp;) : un seul char texte = plusieurs chars HTML

    / Walks through raw HTML and builds:
    - texte_extrait: reconstructed textContent (with HTML whitespace)
    - mapping_debut: dict {text_pos: html_pos} for each text position
    """
    texte_extrait = []
    mapping_debut = {}

    html_pos = 0
    text_pos = 0
    longueur_html = len(html_brut)

    while html_pos < longueur_html:
        char_courant = html_brut[html_pos]

        # --- Tag HTML : on avance html_pos sans toucher text_pos ---
        if char_courant == '<':
            fin_tag = html_brut.find('>', html_pos)
            if fin_tag == -1:
                break
            html_pos = fin_tag + 1
            continue

        # --- Entite HTML (&amp; &nbsp; &#123; etc.) ---
        if char_courant == '&':
            match_entite = REGEX_ENTITE_HTML.match(html_brut, html_pos)
            if match_entite:
                entite_brute = match_entite.group(0)
                caractere_decode = html_module.unescape(entite_brute)

                for i, char_decode in enumerate(caractere_decode):
                    mapping_debut[text_pos] = html_pos
                    texte_extrait.append(char_decode)
                    text_pos += 1

                html_pos += len(entite_brute)
                continue

        # --- Caractere texte normal ---
        mapping_debut[text_pos] = html_pos
        texte_extrait.append(char_courant)
        text_pos += 1
        html_pos += 1

    # Position sentinelle pour end_char qui pointe apres le dernier caractere
    # / Sentinel position for end_char pointing past last character
    mapping_debut[text_pos] = html_pos

    return ''.join(texte_extrait), mapping_debut


def extraire_texte_depuis_html(html_brut):
    """
    Extrait le texte lisible depuis du HTML, equivalent a element.textContent.strip().
    Utilise le meme parseur que l'annotation pour garantir la coherence des positions.
    Utilisee par PageCreateSerializer pour deriver text_readability depuis html_readability.
    / Extract readable text from HTML, equivalent to element.textContent.strip().
    Uses the same parser as annotation to guarantee position consistency.
    """
    if not html_brut:
        return ''
    texte_extrait, _ = _construire_mapping_text_vers_html(html_brut)
    return texte_extrait.strip()


def _calculer_leading_offset(texte_extrait):
    """
    Calcule le nombre de caracteres de whitespace en tete de texte_extrait.
    text_readability = texte_extrait[leading_offset:]  (apres rstrip aussi)
    Donc : position dans text_readability + leading_offset = position dans texte_extrait.
    / Compute leading whitespace char count.
    text_readability position + leading_offset = texte_extrait position.
    """
    for i, char in enumerate(texte_extrait):
        if not char.isspace():
            return i
    return len(texte_extrait)


def _rechercher_texte_dans_contenu(texte_cible, extraction_text, hint_position=None):
    """
    Recherche extraction_text dans texte_cible.
    Essaie : exacte, puis soft (\xa0 → espace), puis debut de texte (30 premiers chars).
    Si hint_position est fourni et qu'il y a plusieurs matchs, prefere le plus proche.
    Retourne la position de debut ou None.
    / Search for extraction_text in texte_cible.
    Tries: exact, then soft (nbsp → space), then prefix search (first 30 chars).
    Returns start position or None.
    """
    if not extraction_text or len(extraction_text) < 3:
        return None

    # --- Strategie 1 : recherche exacte ---
    # / Strategy 1: exact search
    index_exact = texte_cible.find(extraction_text)
    if index_exact != -1:
        return index_exact

    # --- Strategie 2 : remplacer \xa0 par espace dans les deux textes ---
    # C'est la cause #1 de mismatch (guillemets francais « \xa0texte\xa0 »)
    # Le remplacement ne change PAS les longueurs (1 char → 1 char)
    # donc les positions restent valides dans le texte original.
    # / Strategy 2: replace \xa0 with space in both (most common mismatch)
    texte_soft = texte_cible.replace('\xa0', ' ')
    search_soft = extraction_text.replace('\xa0', ' ')
    index_soft = texte_soft.find(search_soft)
    if index_soft != -1:
        return index_soft

    # --- Strategie 3 : recherche du debut (30 chars) ---
    # Pour les cas ou le texte a ete legerement tronque/modifie par le LLM
    # / Strategy 3: search first 30 chars (handles LLM truncation)
    prefixe = search_soft[:30]
    if len(prefixe) >= 10:
        index_prefixe = texte_soft.find(prefixe)
        if index_prefixe != -1:
            return index_prefixe

    logger.debug(
        "_rechercher_texte: aucun match pour '%s'",
        extraction_text[:50],
    )
    return None


def _trouver_position_html_mapped(pos_texte, mapping_debut):
    """
    Trouve la position HTML correspondant a pos_texte dans le mapping.
    Si pos_texte n'est pas exactement dans le mapping, prend la position mappee la plus proche (inferieure).
    Retourne la position HTML ou None.
    / Find the HTML position for pos_texte in the mapping.
    If not exactly in the mapping, take the closest lower mapped position.
    Returns the HTML position or None.
    """
    if pos_texte in mapping_debut:
        return mapping_debut[pos_texte]

    # Prendre la position mappee la plus proche (inferieure)
    # / Take the closest lower mapped position
    positions_inferieures = [p for p in mapping_debut if p <= pos_texte]
    if positions_inferieures:
        pos_proche = max(positions_inferieures)
        return mapping_debut[pos_proche]

    return None


def _est_dans_tag_html(html_brut, position):
    """
    Verifie si une position dans le HTML tombe a l'interieur d'un tag <...>.
    Remonte en arriere pour trouver le dernier '<' ou '>' avant la position.
    Si c'est '<', on est dans un tag. Si c'est '>', on est dans du texte.
    / Check if a position in HTML falls inside a <...> tag.
    Scan backwards for the last '<' or '>' before position.
    If '<', we're inside a tag. If '>', we're in text content.
    """
    for i in range(position - 1, -1, -1):
        if html_brut[i] == '>':
            return False
        if html_brut[i] == '<':
            return True
    return False


def annoter_html_avec_barres(html_brut, text_readability, entites, ids_entites_commentees=None):
    """
    Annote le HTML en enveloppant le texte exact de chaque extraction
    dans un <span class="hl-extraction"> pour surlignage inline + pastille en marge.
    / Annotate HTML by wrapping exact extraction text in
    <span class="hl-extraction"> for inline highlighting + margin dot.
    """
    if not html_brut or not entites:
        return html_brut

    # 1. Construire le mapping texte_extrait_pos → html_pos
    # / Build the texte_extrait_pos → html_pos mapping
    texte_extrait, mapping_debut = _construire_mapping_text_vers_html(html_brut)

    # 2. Calculer le decalage entre text_readability et texte_extrait
    # text_readability = texte_extrait.strip()
    # / Calculate offset: text_readability = texte_extrait.strip()
    leading_offset = _calculer_leading_offset(texte_extrait)

    # 3. Pour chaque entite, calculer les positions HTML de debut et fin du span
    # / For each entity, compute HTML start and end positions for the span
    ids_commentees = ids_entites_commentees or set()

    # Liste des insertions : (html_pos_debut, html_pos_fin, entite_pk, a_commentaire)
    # / List of insertions: (html_start, html_end, entity_pk, has_comment)
    insertions_spans = []

    for entite in entites:
        # Securite : s'assurer que le pk est un entier (evite toute injection HTML)
        # / Safety: ensure pk is an integer (prevents any HTML injection)
        entite_pk = int(entite.pk)
        start_char = entite.start_char
        end_char = entite.end_char
        extraction_text = entite.extraction_text or ''

        positions_valides = (start_char > 0 or end_char > 0) and end_char > start_char
        pos_debut_texte = None
        pos_fin_texte = None

        if positions_valides:
            # Convertir position text_readability → position texte_extrait
            # / Convert text_readability position → texte_extrait position
            pos_debut_extrait = start_char + leading_offset
            pos_fin_extrait = end_char + leading_offset

            # Verifier la coherence : le texte doit COMMENCER a cette position
            # / Sanity check: text must START at this position
            if extraction_text and len(extraction_text) > 5:
                texte_a_position = texte_extrait[pos_debut_extrait:pos_debut_extrait + 30].replace('\xa0', ' ')
                debut_attendu = extraction_text[:15].replace('\xa0', ' ')
                if debut_attendu and not texte_a_position.startswith(debut_attendu):
                    positions_valides = False

            if positions_valides:
                pos_debut_texte = pos_debut_extrait
                pos_fin_texte = pos_fin_extrait

        # Fallback : recherche textuelle dans texte_extrait
        # / Fallback: text search in texte_extrait
        if pos_debut_texte is None:
            pos_trouvee = _rechercher_texte_dans_contenu(
                texte_extrait, extraction_text,
                hint_position=start_char + leading_offset if (start_char > 0 or end_char > 0) else None,
            )
            if pos_trouvee is not None:
                pos_debut_texte = pos_trouvee
                pos_fin_texte = pos_trouvee + len(extraction_text)

        if pos_debut_texte is None:
            logger.warning(
                "annoter_html: texte introuvable pour entite pk=%s — '%s'",
                entite_pk, extraction_text[:60],
            )
            continue

        # Convertir positions texte → positions HTML via le mapping
        # / Convert text positions → HTML positions via mapping
        html_pos_debut = _trouver_position_html_mapped(pos_debut_texte, mapping_debut)
        html_pos_fin = _trouver_position_html_mapped(pos_fin_texte, mapping_debut)

        if html_pos_debut is None or html_pos_fin is None:
            logger.warning(
                "annoter_html: mapping HTML introuvable pour entite pk=%s",
                entite_pk,
            )
            continue

        # Garde defensive : verifier que les positions ne tombent pas dans un tag HTML
        # Le mapping ne devrait jamais pointer dans un tag, mais on verifie par securite
        # / Defensive guard: verify positions don't fall inside an HTML tag
        # The mapping should never point inside a tag, but we check for safety
        if html_pos_debut > 0 and _est_dans_tag_html(html_brut, html_pos_debut):
            logger.warning(
                "annoter_html: position debut dans un tag HTML pour entite pk=%s",
                entite_pk,
            )
            continue
        if html_pos_fin > 0 and _est_dans_tag_html(html_brut, html_pos_fin):
            logger.warning(
                "annoter_html: position fin dans un tag HTML pour entite pk=%s",
                entite_pk,
            )
            continue

        a_commentaire = entite_pk in ids_commentees
        insertions_spans.append((html_pos_debut, html_pos_fin, entite_pk, a_commentaire))

    if not insertions_spans:
        return html_brut

    # 4. Trier par position decroissante (fin → debut) pour ne pas decaler les positions
    # On trie d'abord par html_pos_fin decroissant, puis html_pos_debut decroissant
    # / Sort by descending position (end → start) to avoid offset shifting
    insertions_spans.sort(key=lambda t: (t[1], t[0]), reverse=True)

    # 5. Injecter les spans dans le HTML
    # / Inject spans into HTML
    html_modifie = html_brut
    for (html_pos_debut, html_pos_fin, entite_pk, a_commentaire) in insertions_spans:
        # Construire la classe CSS du span
        # / Build the span CSS class
        classe_span = "hl-extraction"
        if a_commentaire:
            classe_span += " hl-commentee"

        span_ouvrant = f'<span class="{classe_span}" data-extraction-id="{entite_pk}">'
        span_fermant = '</span>'

        # Inserer le span fermant d'abord (position plus loin), puis le span ouvrant
        # / Insert closing span first (further position), then opening span
        html_modifie = html_modifie[:html_pos_fin] + span_fermant + html_modifie[html_pos_fin:]
        html_modifie = html_modifie[:html_pos_debut] + span_ouvrant + html_modifie[html_pos_debut:]

    return html_modifie


# Alias pour compatibilite / Alias for backward compatibility
annoter_html_avec_ancres = annoter_html_avec_barres
