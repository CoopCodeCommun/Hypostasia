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


def _interpoler_couleur_heatmap(score_normalise):
    """
    Interpole une couleur de fond entre vert pale et rouge pale.
    Score 0 = #f0fdf4, Score 0.33 = #fefce8, Score 0.66 = #fff7ed, Score 1.0 = #fef2f2
    / Interpolate a background color between pale green and pale red.
    """
    # Paliers (seuil, (R, G, B)) pour chaque niveau de temperature
    # / Threshold levels (threshold, (R, G, B)) for each temperature level
    paliers = [
        (0.0, (236, 253, 245)),   # vert pale — consensus (consensuel bg)
        (0.33, (240, 249, 255)),  # bleu pale — discussion moderee (discute bg)
        (0.66, (255, 251, 235)),  # orange pale — debat actif (discutable bg)
        (1.0, (255, 247, 237)),   # vermillon pale — controverse forte (controverse bg)
    ]

    # Borner le score entre 0 et 1 / Clamp score to [0, 1]
    score_normalise = max(0.0, min(1.0, score_normalise))

    # Trouver les deux paliers encadrants / Find the two surrounding thresholds
    for i in range(len(paliers) - 1):
        seuil_bas, couleur_bas = paliers[i]
        seuil_haut, couleur_haut = paliers[i + 1]
        if score_normalise <= seuil_haut:
            # Facteur d'interpolation entre les deux paliers
            # / Interpolation factor between the two thresholds
            if seuil_haut == seuil_bas:
                facteur = 0.0
            else:
                facteur = (score_normalise - seuil_bas) / (seuil_haut - seuil_bas)
            r = int(couleur_bas[0] + facteur * (couleur_haut[0] - couleur_bas[0]))
            g = int(couleur_bas[1] + facteur * (couleur_haut[1] - couleur_bas[1]))
            b = int(couleur_bas[2] + facteur * (couleur_haut[2] - couleur_bas[2]))
            return f"#{r:02x}{g:02x}{b:02x}"

    # Fallback : derniere couleur / Fallback: last color
    r, g, b = paliers[-1][1]
    return f"#{r:02x}{g:02x}{b:02x}"


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


def _retrouver_position_avant_normalisation(texte_original, index_dans_normalise):
    """
    Quand on trouve un match a la position index_dans_normalise dans le texte
    normalise (whitespace compresses en un seul espace), on veut retrouver la
    position correspondante dans texte_original (qui a encore ses \n, doubles espaces, etc.).
    On parcourt texte_original caractere par caractere en comptant combien de
    caracteres normalises on a produits, jusqu'a atteindre index_dans_normalise.
    / When a match is found at index_dans_normalise in the normalized text,
    / find the corresponding position in the original text (with \n, multiple spaces).
    """
    import re
    compteur_normalise = 0
    i = 0
    longueur = len(texte_original)
    en_whitespace = False

    while i < longueur and compteur_normalise < index_dans_normalise:
        caractere = texte_original[i]
        est_whitespace = caractere in (' ', '\n', '\t', '\r', '\xa0')

        if est_whitespace:
            if not en_whitespace:
                # Premier whitespace d'une sequence → compte comme 1 espace normalise
                # / First whitespace in a sequence → counts as 1 normalized space
                compteur_normalise += 1
                en_whitespace = True
            # Les whitespace suivants dans la sequence sont ignores (comprimes)
            # / Subsequent whitespace in the sequence are ignored (compressed)
        else:
            compteur_normalise += 1
            en_whitespace = False

        i += 1

    if compteur_normalise == index_dans_normalise:
        return i
    return None


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

    # --- Strategie 4 : normalisation complete (whitespace + ponctuation typographique) ---
    # Le LLM normalise souvent le texte quand il le recopie dans sa reponse :
    #   - \n et \t deviennent des espaces
    #   - les doubles espaces deviennent des espaces simples
    #   - les apostrophes typographiques ' (U+2019) deviennent ' (U+0027)
    #   - les guillemets typographiques " " deviennent "
    #   - les tirets longs — – deviennent -
    # On applique les memes normalisations aux deux textes pour la comparaison.
    # ATTENTION : apres normalisation, les positions ne correspondent plus 1:1
    # au texte original (un \n supprime = decalage). On retourne donc la position
    # trouvee dans le texte ORIGINAL en recherchant le prefixe normalise.
    # / Strategy 4: full normalization (whitespace + typographic punctuation)
    # / The LLM normalizes text when copying it into its response.
    # / We apply the same normalizations to both texts for comparison.
    import re

    def normaliser_texte_complet(texte):
        """Normalise whitespace + ponctuation typographique pour comparaison."""
        resultat = texte
        # Ponctuation typographique → ASCII
        # / Typographic punctuation → ASCII
        resultat = resultat.replace('\u2019', "'")   # ' → apostrophe droite
        resultat = resultat.replace('\u2018', "'")   # ' → apostrophe droite
        resultat = resultat.replace('\u201c', '"')   # " → guillemet droit
        resultat = resultat.replace('\u201d', '"')   # " → guillemet droit
        resultat = resultat.replace('\u2013', '-')   # – → tiret
        resultat = resultat.replace('\u2014', '-')   # — → tiret
        # Whitespace : \n, \t, espaces multiples → un seul espace
        # / Whitespace: \n, \t, multiple spaces → single space
        resultat = re.sub(r'\s+', ' ', resultat)
        return resultat

    texte_normalise = normaliser_texte_complet(texte_soft)
    search_normalise = normaliser_texte_complet(search_soft)

    # Recherche exacte sur textes normalises.
    # Si le match est trouve, on doit retrouver la position dans le texte ORIGINAL.
    # On utilise le prefixe pour localiser dans le texte non-normalise.
    # / Exact search on normalized texts.
    # / If match found, we need the position in the ORIGINAL text.
    # / We use the prefix to locate in the non-normalized text.
    index_normalise = texte_normalise.find(search_normalise)
    if index_normalise != -1:
        # Retrouver la position originale : le caractere a index_normalise dans
        # le texte normalise correspond a un caractere dans texte_soft.
        # On parcourt texte_soft en comptant les caracteres normalises.
        # / Find original position by walking texte_soft and counting normalized chars.
        position_originale = _retrouver_position_avant_normalisation(
            texte_soft, index_normalise
        )
        if position_originale is not None:
            return position_originale

    # Recherche du prefixe normalise (30 chars)
    # / Normalized prefix search (30 chars)
    prefixe_normalise = search_normalise[:30]
    if len(prefixe_normalise) >= 10:
        index_prefixe_normalise = texte_normalise.find(prefixe_normalise)
        if index_prefixe_normalise != -1:
            position_originale = _retrouver_position_avant_normalisation(
                texte_soft, index_prefixe_normalise
            )
            if position_originale is not None:
                return position_originale

    # --- Strategie 5 : sous-sequence de mots (PDF multi-colonnes) ---
    # L'extraction PDF reordonne parfois les mots (layout multi-colonnes).
    # Le LLM reconstruit l'ordre logique, mais les mots stockes sont melanges.
    # On cherche la plus longue sous-sequence contigue de mots de l'extraction
    # qui apparait dans le texte source. Si elle couvre >= 60% des mots, on ancre.
    # / Strategy 5: word subsequence (multi-column PDF)
    # / PDF extraction sometimes reorders words. The LLM reconstructs logical order,
    # / but stored words are scrambled. We find the longest contiguous word subsequence
    # / from the extraction that appears in the source. If >= 60% of words, we anchor.
    mots_extraction = search_normalise.split()
    if len(mots_extraction) >= 4:
        meilleure_position = None
        meilleure_longueur = 0
        seuil_mots = max(4, int(len(mots_extraction) * 0.6))

        # Fenetre glissante decroissante : on essaie d'abord les plus longs blocs
        # / Decreasing sliding window: try longest blocks first
        for taille_fenetre in range(len(mots_extraction), seuil_mots - 1, -1):
            if meilleure_longueur >= taille_fenetre:
                break
            for debut_fenetre in range(len(mots_extraction) - taille_fenetre + 1):
                bloc = ' '.join(mots_extraction[debut_fenetre:debut_fenetre + taille_fenetre])
                index_bloc = texte_normalise.find(bloc)
                if index_bloc != -1 and taille_fenetre > meilleure_longueur:
                    meilleure_longueur = taille_fenetre
                    meilleure_position = index_bloc
                    break
            if meilleure_longueur >= taille_fenetre:
                break

        if meilleure_position is not None:
            logger.debug(
                "_rechercher_texte: match partiel (strategie 5, %d/%d mots) pour '%s'",
                meilleure_longueur, len(mots_extraction), extraction_text[:50],
            )
            position_originale = _retrouver_position_avant_normalisation(
                texte_soft, meilleure_position
            )
            if position_originale is not None:
                return position_originale

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


def annoter_html_avec_barres(html_brut, text_readability, entites, ids_entites_commentees=None, scores_temperature_normalises=None):
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

            # Verifier la coherence : le texte doit COMMENCER a cette position.
            # On normalise les whitespace et la ponctuation pour la comparaison
            # car le LLM compresse souvent les \n et doubles espaces.
            # / Sanity check: text must START at this position.
            # / We normalize whitespace and punctuation for comparison
            # / because the LLM often compresses \n and double spaces.
            if extraction_text and len(extraction_text) > 5:
                import re
                texte_a_position = re.sub(r'\s+', ' ', texte_extrait[pos_debut_extrait:pos_debut_extrait + 30])
                debut_attendu = re.sub(r'\s+', ' ', extraction_text[:15])
                if debut_attendu and not texte_a_position.startswith(debut_attendu):
                    positions_valides = False

            if positions_valides:
                pos_debut_texte = pos_debut_extrait
                pos_fin_texte = pos_fin_extrait

        # Fallback : recherche textuelle dans texte_extrait.
        # Si la recherche normalise les whitespace pour trouver le match,
        # la fin du span doit couvrir les \n et doubles espaces du texte original.
        # On utilise end_char - start_char (etendue originale) si positions valides.
        # / Fallback: text search in texte_extrait.
        # / If search normalizes whitespace, span end must cover \n and double spaces.
        if pos_debut_texte is None:
            pos_trouvee = _rechercher_texte_dans_contenu(
                texte_extrait, extraction_text,
                hint_position=start_char + leading_offset if (start_char > 0 or end_char > 0) else None,
            )
            if pos_trouvee is not None:
                pos_debut_texte = pos_trouvee
                # Utiliser l'etendue originale (end_char - start_char) si disponible.
                # Sinon, estimer en marchant dans le texte original.
                # / Use original span (end_char - start_char) if available.
                etendue_originale = end_char - start_char if (end_char > start_char) else 0
                if etendue_originale > 0:
                    pos_fin_texte = pos_trouvee + etendue_originale
                else:
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
        statut_debat = entite.statut_debat or "discutable"

        # Couleur heat map si les scores sont fournis (PHASE-19)
        # / Heat map color if scores are provided (PHASE-19)
        couleur_heatmap = None
        if scores_temperature_normalises and entite_pk in scores_temperature_normalises:
            couleur_heatmap = _interpoler_couleur_heatmap(scores_temperature_normalises[entite_pk])

        insertions_spans.append((html_pos_debut, html_pos_fin, entite_pk, a_commentaire, statut_debat, couleur_heatmap))

    if not insertions_spans:
        return html_brut

    # 4. Trier par position decroissante (fin → debut) pour ne pas decaler les positions
    # On trie d'abord par html_pos_fin decroissant, puis html_pos_debut decroissant
    # / Sort by descending position (end → start) to avoid offset shifting
    insertions_spans.sort(key=lambda t: (t[1], t[0]), reverse=True)

    # 5. Injecter les spans dans le HTML
    # / Inject spans into HTML
    html_modifie = html_brut
    for (html_pos_debut, html_pos_fin, entite_pk, a_commentaire, statut_debat, couleur_heatmap) in insertions_spans:
        # Construire la classe CSS du span
        # / Build the span CSS class
        classe_span = "hl-extraction"
        if a_commentaire:
            classe_span += " hl-commentee"

        # Attribut data-heat-color pour la heat map du debat (PHASE-19)
        # / data-heat-color attribute for debate heat map (PHASE-19)
        attribut_heatmap = f' data-heat-color="{couleur_heatmap}"' if couleur_heatmap else ''

        span_ouvrant = f'<span class="{classe_span}" data-extraction-id="{entite_pk}" data-statut="{statut_debat}"{attribut_heatmap}>'
        span_fermant = '</span>'

        # Inserer le span fermant d'abord (position plus loin), puis le span ouvrant
        # / Insert closing span first (further position), then opening span
        html_modifie = html_modifie[:html_pos_fin] + span_fermant + html_modifie[html_pos_fin:]
        html_modifie = html_modifie[:html_pos_debut] + span_ouvrant + html_modifie[html_pos_debut:]

    return html_modifie


# Alias pour compatibilite / Alias for backward compatibility
annoter_html_avec_ancres = annoter_html_avec_barres
