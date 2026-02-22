"""
Utilitaires pour l'annotation HTML cote serveur.
/ Server-side HTML annotation utilities.

Principe : on annote les tags conteneurs (<p>, <div>, <blockquote>, etc.)
avec des attributs data-extraction-ids et des classes CSS pour afficher
des barres verticales colorees en marge gauche.
/ Principle: annotate container tags with data-extraction-ids attributes
and CSS classes to display colored vertical bars in the left margin.

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


def _trouver_tag_conteneur_englobant(html_brut, html_pos):
    """
    Depuis une position dans le HTML, remonte pour trouver le tag conteneur englobant.
    Retourne (debut_tag, fin_chevron_ouvrant) ou None si introuvable.
    Tags reconnus : p, div, blockquote, li, h1-h6, td, section, article.
    / From a position in HTML, scan backwards to find the enclosing container tag.
    Returns (tag_start, opening_chevron_end) or None if not found.
    """
    # Tags HTML reconnus comme conteneurs de texte
    # / HTML tags recognized as text containers
    tags_conteneurs = {
        'p', 'div', 'blockquote', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'td', 'section', 'article',
    }

    # Scanner en arriere pour trouver le '<' d'ouverture du tag englobant
    # / Scan backwards to find the '<' of the enclosing opening tag
    pos = html_pos - 1
    while pos >= 0:
        if html_brut[pos] == '<':
            # Verifier que c'est un tag ouvrant (pas </xxx>)
            # / Check it's an opening tag (not </xxx>)
            if pos + 1 < len(html_brut) and html_brut[pos + 1] == '/':
                pos -= 1
                continue

            # Extraire le nom du tag / Extract tag name
            match_tag = re.match(r'<(\w+)', html_brut[pos:])
            if match_tag:
                nom_tag = match_tag.group(1).lower()
                if nom_tag in tags_conteneurs:
                    # Trouver la fin du chevron ouvrant '>'
                    # / Find the end of the opening chevron '>'
                    fin_chevron = html_brut.find('>', pos)
                    if fin_chevron != -1:
                        return (pos, fin_chevron)
        pos -= 1

    return None


def annoter_html_avec_barres(html_brut, text_readability, entites, ids_entites_commentees=None):
    """
    Annote les tags conteneurs du HTML avec des attributs data-extraction-ids
    et des classes CSS pour afficher des barres verticales colorees en marge.
    / Annotate HTML container tags with data-extraction-ids attributes
    and CSS classes to display colored vertical margin bars.
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

    # 3. Pour chaque entite, trouver la position HTML puis le tag conteneur
    # / For each entity, find HTML position then the container tag
    ids_commentees = ids_entites_commentees or set()

    # Dictionnaire : (debut_tag, fin_chevron) → set d'IDs d'entites
    # / Dict: (tag_start, chevron_end) → set of entity IDs
    conteneurs_trouves = {}
    # Meme chose pour savoir si le conteneur a des entites commentees
    # / Same for tracking if container has commented entities
    conteneurs_avec_commentaire = {}

    for entite in entites:
        entite_pk = entite.pk
        start_char = entite.start_char
        end_char = entite.end_char
        extraction_text = entite.extraction_text or ''

        positions_valides = (start_char > 0 or end_char > 0) and end_char > start_char
        html_pos_insertion = None

        if positions_valides:
            # Convertir position text_readability → position texte_extrait
            # / Convert text_readability position → texte_extrait position
            pos_extrait = start_char + leading_offset

            # Verifier la coherence : le texte doit COMMENCER a cette position
            # / Sanity check: text must START at this position
            if extraction_text and len(extraction_text) > 5:
                texte_a_position = texte_extrait[pos_extrait:pos_extrait + 30].replace('\xa0', ' ')
                debut_attendu = extraction_text[:15].replace('\xa0', ' ')
                if debut_attendu and not texte_a_position.startswith(debut_attendu):
                    positions_valides = False

            if positions_valides and pos_extrait in mapping_debut:
                html_pos_insertion = mapping_debut[pos_extrait]

        if html_pos_insertion is None:
            # Fallback : recherche textuelle dans texte_extrait
            # / Fallback: text search in texte_extrait
            pos_trouvee = _rechercher_texte_dans_contenu(
                texte_extrait, extraction_text,
                hint_position=start_char + leading_offset if positions_valides else None,
            )
            if pos_trouvee is not None and pos_trouvee in mapping_debut:
                html_pos_insertion = mapping_debut[pos_trouvee]
            elif pos_trouvee is not None:
                # Position trouvee mais pas exactement dans le mapping
                # Prendre la position mappee la plus proche (inferieure)
                # / Found position not in mapping, take closest lower mapped position
                positions_inferieures = [p for p in mapping_debut if p <= pos_trouvee]
                if positions_inferieures:
                    pos_proche = max(positions_inferieures)
                    html_pos_insertion = mapping_debut[pos_proche]

        if html_pos_insertion is None:
            logger.warning(
                "annoter_html: texte introuvable pour entite pk=%s — '%s'",
                entite_pk, extraction_text[:60],
            )
            continue

        # Trouver le tag conteneur englobant cette position
        # / Find the container tag enclosing this position
        resultat_conteneur = _trouver_tag_conteneur_englobant(html_brut, html_pos_insertion)
        if resultat_conteneur is None:
            logger.warning(
                "annoter_html: tag conteneur introuvable pour entite pk=%s",
                entite_pk,
            )
            continue

        # Regrouper les entites par conteneur (un meme bloc peut contenir plusieurs extractions)
        # / Group entities by container (a single block can contain multiple extractions)
        position_conteneur = resultat_conteneur
        if position_conteneur not in conteneurs_trouves:
            conteneurs_trouves[position_conteneur] = set()
            conteneurs_avec_commentaire[position_conteneur] = False

        conteneurs_trouves[position_conteneur].add(entite_pk)
        if entite_pk in ids_commentees:
            conteneurs_avec_commentaire[position_conteneur] = True

    if not conteneurs_trouves:
        return html_brut

    # 4. Trier par position decroissante pour modifier de la fin vers le debut
    # / Sort by descending position to modify from end to start
    conteneurs_tries = sorted(conteneurs_trouves.keys(), key=lambda t: t[0], reverse=True)

    # 5. Injecter les attributs dans chaque tag conteneur
    # / Inject attributes into each container tag
    html_modifie = html_brut
    for (debut_tag, fin_chevron) in conteneurs_tries:
        ids_entites = conteneurs_trouves[(debut_tag, fin_chevron)]
        a_commentaire = conteneurs_avec_commentaire[(debut_tag, fin_chevron)]

        # Construire la liste des IDs separee par des virgules
        # / Build comma-separated ID list
        ids_str = ",".join(str(pk) for pk in sorted(ids_entites))

        # Determiner les classes a ajouter / Determine classes to add
        classe_barre = "bloc-avec-extraction"
        if a_commentaire:
            classe_barre += " bloc-avec-commentaire"

        # Extraire le tag ouvrant actuel / Extract current opening tag
        tag_ouvrant = html_modifie[debut_tag:fin_chevron + 1]

        # Injecter class et data-extraction-ids dans le tag
        # / Inject class and data-extraction-ids into the tag
        if 'class="' in tag_ouvrant:
            # Ajouter aux classes existantes / Append to existing classes
            tag_modifie = tag_ouvrant.replace(
                'class="',
                f'class="{classe_barre} ',
            )
        else:
            # Inserer apres le nom du tag / Insert after tag name
            tag_modifie = tag_ouvrant.replace('>', f' class="{classe_barre}">', 1)

        # Ajouter data-extraction-ids / Add data-extraction-ids
        tag_modifie = tag_modifie.replace('>', f' data-extraction-ids="{ids_str}">', 1)

        html_modifie = html_modifie[:debut_tag] + tag_modifie + html_modifie[fin_chevron + 1:]

    return html_modifie


# Alias pour compatibilite / Alias for backward compatibility
annoter_html_avec_ancres = annoter_html_avec_barres
