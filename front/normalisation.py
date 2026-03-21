"""
Normalisation deterministe des attributs d'extraction LLM.
/ Deterministic normalization of LLM extraction attributes.

LOCALISATION : front/normalisation.py

Les LLM retournent des cles variantes (Resume, résumé, resume, Hypostases, hypostase...).
Ce module normalise UNE FOIS au stockage vers 4 cles canoniques :
    resume, hypostases, statut, mots_cles

Appele avant ExtractedEntity.objects.create() dans analyser_page_task().
"""
import difflib
import logging
import unicodedata

logger = logging.getLogger("front")


# --- Helper de normalisation de texte (reutilisable) ---
# / --- Reusable text normalization helper ---
def _normaliser_texte(texte):
    """
    Minuscule + NFKD + supprime diacritiques + remplace tirets par underscores.
    / Lowercase + NFKD + strip diacritics + replace dashes with underscores.
    """
    texte = str(texte).strip().lower()
    texte_nfkd = unicodedata.normalize('NFKD', texte)
    sans_accents = ''.join(c for c in texte_nfkd if not unicodedata.combining(c))
    return sans_accents.replace('-', '_')


# --- Mapping de toutes les variantes connues vers les 4 cles canoniques ---
# / --- Mapping of all known variants to the 4 canonical keys ---
SYNONYMES_CLES = {
    # hypostases
    'hypostase': 'hypostases',
    'hypostases': 'hypostases',
    'hypostasis': 'hypostases',
    # resume
    'resume': 'resume',
    'résumé': 'resume',
    'summary': 'resume',
    # statut
    'statut': 'statut',
    'statut_debat': 'statut',
    'status': 'statut',
    # mots_cles
    'mots_cles': 'mots_cles',
    'mots_clés': 'mots_cles',
    'mots-cles': 'mots_cles',
    'mots-clés': 'mots_cles',
    'keywords': 'mots_cles',
    'hashtags': 'mots_cles',
}


# --- Set des 30 hypostases connues (cles normalisees, sans accents) ---
# / --- Set of 30 known hypostases (normalized keys, no accents) ---
HYPOSTASES_CONNUES = {
    'classification', 'axiome', 'theorie', 'definition', 'formalisme',
    'phenomene', 'evenement', 'donnee', 'variable', 'indice',
    'hypothese', 'conjecture', 'approximation',
    'structure', 'invariant', 'dimension', 'domaine',
    'loi', 'principe', 'valeur', 'croyance',
    'aporie', 'paradoxe', 'probleme',
    'mode', 'variation', 'variance', 'paradigme',
    'objet', 'methode',
}

# Synonymes courants que les LLM produisent a la place des 30 hypostases.
# Mapping semantique : le LLM pense "proposition" mais l'hypostase est "hypothese".
# / Common synonyms that LLMs produce instead of the 30 hypostases.
# / Semantic mapping: the LLM thinks "proposition" but the hypostasis is "hypothese".
SYNONYMES_HYPOSTASES = {
    'proposition': 'hypothese',
    'prediction': 'conjecture',
    'consequence': 'conjecture',
    'reference': 'donnee',
    'influence': 'phenomene',
    'defi': 'probleme',
    'condition': 'principe',
    'argument': 'hypothese',
    'these': 'theorie',
    'constat': 'phenomene',
    'critique': 'probleme',
    'alerte': 'conjecture',
    'synthese': 'theorie',
    'objection': 'probleme',
    'regle': 'loi',
    'concept': 'definition',
    'categorie': 'classification',
    'preuve': 'donnee',
    'observation': 'phenomene',
    'conviction': 'croyance',
    'dilemme': 'aporie',
    'contradiction': 'paradoxe',
    'tendance': 'variation',
    'modele': 'paradigme',
    'processus': 'methode',
    'limite': 'dimension',
    'norme': 'loi',
    'postulat': 'axiome',
    'supposition': 'hypothese',
    'estimation': 'approximation',
}


def normaliser_valeur_hypostase(valeur_brute):
    """
    Normalise une valeur d'hypostase (potentiellement multi-valeurs separees par virgule).
    Supprime les hypostases hallucinees, corrige les typos via fuzzy match.
    / Normalize a hypostase value (potentially multi-value, comma-separated).
    / Removes hallucinated hypostases, corrects typos via fuzzy match.
    """
    if not valeur_brute:
        return ""

    fragments = str(valeur_brute).split(',')
    hypostases_normalisees = []

    for fragment in fragments:
        fragment_normalise = _normaliser_texte(fragment)
        if not fragment_normalise:
            continue

        # Correspondance exacte dans les hypostases connues
        # / Exact match in known hypostases
        if fragment_normalise in HYPOSTASES_CONNUES:
            hypostases_normalisees.append(fragment_normalise)
            continue

        # Correspondance via synonymes courants (le LLM pense "proposition" → "hypothese")
        # / Match via common synonyms (LLM thinks "proposition" → "hypothese")
        if fragment_normalise in SYNONYMES_HYPOSTASES:
            hypostase_mappee = SYNONYMES_HYPOSTASES[fragment_normalise]
            logger.info(
                "Hypostase '%s' mappee vers '%s' via synonyme",
                fragment_normalise, hypostase_mappee,
            )
            hypostases_normalisees.append(hypostase_mappee)
            continue

        # Tentative de correction par fuzzy match (seuil 0.8)
        # / Fuzzy match correction attempt (threshold 0.8)
        correspondances = difflib.get_close_matches(
            fragment_normalise,
            list(HYPOSTASES_CONNUES),
            n=1,
            cutoff=0.8,
        )
        if correspondances:
            hypostase_corrigee = correspondances[0]
            logger.info(
                "Hypostase '%s' corrigee en '%s' par fuzzy match",
                fragment_normalise, hypostase_corrigee,
            )
            hypostases_normalisees.append(hypostase_corrigee)
        else:
            # Hypostase inconnue / hallucinee — on la supprime
            # / Unknown / hallucinated hypostase — remove it
            logger.warning(
                "Hypostase '%s' supprimee (inconnue, pas de correspondance proche)",
                fragment_normalise,
            )

    return ", ".join(hypostases_normalisees)


def normaliser_attributs_entite(attributes_dict):
    """
    Normalise les cles d'un dict d'attributs LLM vers les 4 cles canoniques.
    Appelle normaliser_valeur_hypostase() sur la valeur de 'hypostases' si presente.
    / Normalize LLM attribute dict keys to the 4 canonical keys.
    / Calls normaliser_valeur_hypostase() on the 'hypostases' value if present.
    """
    if not attributes_dict:
        return {}

    resultat = {}
    for cle_brute, valeur in attributes_dict.items():
        # Normalise la cle : strip accents + lowercase + tirets → underscores
        # / Normalize key: strip accents + lowercase + dashes → underscores
        cle_normalisee = _normaliser_texte(cle_brute)

        # Mapper via SYNONYMES_CLES vers la cle canonique
        # / Map via SYNONYMES_CLES to canonical key
        cle_canonique = SYNONYMES_CLES.get(cle_normalisee)

        if cle_canonique:
            # Collision : si la cle canonique existe deja, garder la premiere valeur non vide
            # / Collision: if canonical key already exists, keep first non-empty value
            if cle_canonique in resultat and resultat[cle_canonique]:
                continue
            resultat[cle_canonique] = valeur
        else:
            # Cle inconnue : conserver telle quelle + warning
            # / Unknown key: keep as-is + warning
            logger.warning(
                "Cle d'attribut inconnue '%s' (normalisee: '%s') conservee telle quelle",
                cle_brute, cle_normalisee,
            )
            resultat[cle_normalisee] = valeur

    # Normaliser la valeur d'hypostase si presente
    # / Normalize hypostase value if present
    if 'hypostases' in resultat and resultat['hypostases']:
        resultat['hypostases'] = normaliser_valeur_hypostase(resultat['hypostases'])

    return resultat
