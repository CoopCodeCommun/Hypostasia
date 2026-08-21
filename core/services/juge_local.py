"""
ShieldStral — DEBRANCHE DE LA PRODUCTION LE 19 AOUT 2026.
/ ShieldStral — UNPLUGGED FROM PRODUCTION ON 19 AUGUST 2026.

LOCALISATION : core/services/juge_local.py

⚠ **CE MODULE N'EST PLUS APPELE PAR LA PRODUCTION.** Le second avis est
rendu depuis le 19 aout 2026 par `core/services/juges_locaux.py` —
quatre encodeurs a 45-352 ms la paire, contre ~24 000 ms ici, pour un
pouvoir de detection au moins egal (mesure du 19 aout,
`benchmarks/juge_de_verification/2026-08-19_des-encodeurs-contre-l-etalon.md`).

**Il n'est PAS supprime, et c'est deliberé.** Il porte le cadrage exact
avec lequel ShieldStral a ete mesure les 18 et 19 aout, et
`benchmarks/juge_de_verification/comparer_shieldstral.py` l'importe sans
copie. Le supprimer rendrait ces mesures irrejouables — et une mesure
qu'on ne peut plus rejouer n'est plus une mesure.

**Ne le rebranchez pas sans remesurer** : il charge 7,7 Go et coute
~24 000 ms de temps processeur par paire — le meme chiffre qu'en tete
de ce fichier, et non les « deux minutes » qu'annoncaient les mesures
d'avant le 19 aout.

---

Ce qui suit decrit le juge tel qu'il etait branche.

CE QU'IL EST. ShieldStral, modele de moderation de Mistral, poids Apache
2.0, 3,8 milliards de parametres, 7,7 Go en bf16. L'operateur ecrit sa
PROPRE question binaire, le modele rend UN SEUL token — `yes` ou `no` —
et on lit ses logits. On obtient donc un score CONTINU et vraiment
calibre, la ou les deux API refusent les logprobs (« Logprobs are not
enabled for this model » chez Mistral, 403 chez OpenAI).

Il tourne sur PROCESSEUR, sans clef d'API, et rien ne sort de la
machine. Pour un outil de deliberation qui traite des verbatims
d'assemblee, ce dernier point n'est pas un detail.

CE QU'IL N'EST PAS. Ce n'est PAS un `AIModel`. Il ne parle pas la meme
langue : `appeler_llm` rend du texte, celui-ci rend un score. Le forcer
dans le referentiel le ferait PROPOSER AU CLIC comme modele
d'extraction sur l'ecran de configuration IA, alors que LangExtract ne
sait pas le piloter — le piege documente le 17 aout 2026 pour les
modeles de plateforme.

ET IL NE PILOTE RIEN. C'est un SECOND AVIS : il n'ecrit ni
`etat_de_verification`, ni `score_de_verification`, ni le libelle
affiche. Il tourne a cote du juge de production pour etre compare a lui
sur des donnees reelles.

LE CADRAGE FAIT TOUT, ET IL EST ICI, EN UN SEUL ENDROIT. Mesure du
18 aout 2026 : mettre l'affirmation ET la source dans le meme
`<Document>` donne une AUC de **0,538** — le hasard. Respecter la
structure `<Instruct>` / `<Query>` / `<Document>` de la fiche du modele
donne **0,923** sur quinze paires relues a la main, et **0,734** sur les
145 paires gelees. Le banc importe cette construction d'ici : deux
copies poseraient deux questions differentes, et la comparaison ne
voudrait plus rien dire.
/ The framing is everything, and it lives here, once. The bench imports
it rather than copying it.
"""

import logging
import os

logger = logging.getLogger(__name__)

MODELE = "mistralai/Shieldstral-1.0-3B"

# La consigne systeme est FIXE : elle vient de la fiche du modele.
# / The system prompt is fixed; it comes from the model card.
CONSIGNE_SYSTEME = (
    "Judge whether the Document meets the requirements based on the Query "
    'and the Instruction provided. Note that the answer can only be "yes" '
    'or "no".'
)

# LA SEVERITE FAIT PARTIE DE LA QUESTION, pas du reglage. « large » et
# « strict » ne demandent pas la meme chose, et la mesure a montre que
# c'est decisif — d'ou sa presence dans le NOM de la methode, et pas
# seulement dans le code.
# / Strictness is part of the question, hence part of the method's name.
INSTRUCTIONS = {
    "large": (
        "Tu vérifies le sourçage d'une synthèse de délibération. "
        "L'AFFIRMATION avance plusieurs choses à la fois et cite plusieurs "
        "sources : chacune n'en établit qu'une part. Sois INDULGENT : "
        "réponds oui dès que la SOURCE établit au moins une des choses que "
        "l'affirmation avance, sans en contredire aucune."
    ),
    "strict": (
        "Tu vérifies le sourçage d'une synthèse de délibération. Sois "
        "STRICT : réponds oui seulement si la SOURCE établit à elle seule "
        "tout ce que l'AFFIRMATION avance, sans qu'aucune autre source ne "
        "soit nécessaire."
    ),
}

SEVERITE = "large"
VERSION = "shieldstral-logits v1"

MOTS_OUI = {"yes", "yes.", '"yes"', "'yes'", "oui"}
MOTS_NON = {"no", "no.", '"no"', "'no'", "non"}

# LE SEUIL EST PROVISOIRE, ET SA PROPRE MESURE LE DIT. 0,378 — soit
# 37,8 sur 100 — est le meilleur seuil sur QUINZE points d'UNE SEULE
# affirmation, choisi APRES COUP : sur-ajuste par construction. Il est
# donc une variable d'environnement, comme le seuil du juge de
# production est un champ : remettre un seuil en dur referait la faute
# que le chantier du 18 aout a corrigee.
# / Provisional by construction: chosen post hoc on fifteen points.
SEUIL_UTILE_PAR_DEFAUT = 38.0

# SIX THREADS — « tout moins deux » sur les huit coeurs de cette
# machine. Mesure du 18 aout, modele charge une seule fois :
#   2 threads 62,3 s/paire · 3 : 46,4 · 4 : 36,1 · 6 : 25,7 · 8 : 20,2
# Le rendement par thread ne tombe qu'a 0,81 a six : le passage a
# l'echelle est bon, contrairement a ce qu'on avait suppose.
#
# CE QUE `nice` NE FAIT PAS. Il pondere le temps processeur, PAS la
# bande passante memoire — et rien ici ne partitionne cette derniere.
# Baisser le nombre de threads est le seul levier sur cette pression-la.
# De combien Docling ralentit reellement n'a PAS ete mesure : si on
# l'observe trainer, on descend, sans toucher au code.
# / Six threads: measured. nice arbitrates CPU time, never memory
# bandwidth — fewer threads is the only lever on that.
NOMBRE_DE_THREADS_PAR_DEFAUT = 6

# Le modele charge, garde entre les paires. 7,7 Go recharges a chaque
# paire rendraient la tache absurde. Le worker dedie etant a
# concurrence 1, une seule copie vit a la fois.
# / Loaded once and kept: 7.7 GB per pair would be absurd.
_modele_charge = None


def methode():
    """
    Qui a rendu l'avis — version, severite et modele.
    / Who rendered the opinion: version, strictness and model.

    LOCALISATION : core/services/juge_local.py

    La severite est DANS le nom : « large » et « strict » ne posent pas
    la meme question, et deux avis rendus sous deux severites ne se
    comparent pas.
    """
    return f"{VERSION} ({SEVERITE}) — ShieldStral 1.0 3B"


def seuil_utile():
    """Le seuil propre a ce juge, de 0 a 100. / This judge's threshold."""
    valeur = os.environ.get("SHIELDSTRAL_SEUIL", "").strip()
    if not valeur:
        return SEUIL_UTILE_PAR_DEFAUT
    try:
        return float(valeur)
    except ValueError:
        logger.warning(
            "juge_local: SHIELDSTRAL_SEUIL=%r illisible — repli sur %s.",
            valeur, SEUIL_UTILE_PAR_DEFAUT,
        )
        return SEUIL_UTILE_PAR_DEFAUT


def nombre_de_threads():
    """Combien de threads laisser a l'inference. / Inference thread cap."""
    valeur = os.environ.get("SHIELDSTRAL_THREADS", "").strip()
    if not valeur:
        return NOMBRE_DE_THREADS_PAR_DEFAUT
    try:
        return max(1, int(valeur))
    except ValueError:
        logger.warning(
            "juge_local: SHIELDSTRAL_THREADS=%r illisible — repli sur %s.",
            valeur, NOMBRE_DE_THREADS_PAR_DEFAUT,
        )
        return NOMBRE_DE_THREADS_PAR_DEFAUT


def message_pour_le_juge(affirmation, source, severite=SEVERITE):
    """
    Le message, dans la structure que la fiche du modele decrit.
    / The message, in the structure the model card describes.

    LOCALISATION : core/services/juge_local.py

    `<Query>` porte l'AFFIRMATION, `<Document>` porte la SOURCE SEULE.
    On demande au modele si le Document satisfait la Query — c'est sa
    structure, et la respecter n'est pas un detail de forme : mettre les
    deux textes dans `<Document>` fait tomber l'AUC de 0,92 a 0,54,
    parce que le modele doit alors DEVINER lequel des deux il juge.
    / Query holds the claim, Document the source alone. Cramming both
    into Document drops the AUC from 0.92 to 0.54.
    """
    return (
        f"<Instruct>: {INSTRUCTIONS[severite]}\n"
        f"<Query>: {affirmation}\n"
        f"<Document>: {source}"
    )


def _charger_le_modele():
    """
    Charge le modele une fois, et le garde. / Loads once, keeps it.

    L'import de torch et transformers est LOCAL a cette fonction : le
    module doit pouvoir etre importe — pour lire `methode()` ou
    `seuil_utile()` — sans payer le chargement de torch.
    / Local imports: reading methode() must not cost a torch import.
    """
    global _modele_charge
    if _modele_charge is not None:
        return _modele_charge

    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    torch.set_num_threads(nombre_de_threads())
    logger.info(
        "juge_local: chargement de %s sur processeur, %s threads.",
        MODELE, nombre_de_threads(),
    )
    tokeniseur = AutoProcessor.from_pretrained(MODELE)
    modele = AutoModelForImageTextToText.from_pretrained(
        MODELE, dtype=torch.bfloat16, low_cpu_mem_usage=True,
    )
    modele.eval()
    _modele_charge = (tokeniseur, modele)
    return _modele_charge


def noter_une_paire(affirmation, source, severite=SEVERITE):
    """
    Le degre de soutien d'une paire, de 0 a 100.
    / One pair's support degree, from 0 to 100.

    LOCALISATION : core/services/juge_local.py

    LA CONVERSION D'ECHELLE VIT ICI, ET NULLE PART AILLEURS. Le modele
    rend une probabilite entre 0 et 1 ; la base stocke un degre entre 0
    et 100. Une conversion oubliee ferait lire 0,41 comme un degre de
    zero — SANS UNE ERREUR. C'est le mode d'echec exact que le parseur
    entier du juge de production a ete ecrit pour fermer.
    / The scale conversion lives here and nowhere else: a forgotten one
    would read 0.41 as a degree of zero, silently.

    :return: un degre de 0 a 100, ou None si le modele n'a rendu ni oui
        ni non parmi ses tokens les plus probables
    """
    import torch

    tokeniseur, modele = _charger_le_modele()
    entrees = tokeniseur.apply_chat_template(
        [
            {"role": "system", "content": CONSIGNE_SYSTEME},
            {"role": "user", "content": message_pour_le_juge(
                affirmation, source, severite,
            )},
        ],
        add_generation_prompt=True, return_tensors="pt",
        return_dict=True, tokenize=True,
    )
    with torch.no_grad():
        logits = modele(**entrees).logits[0, -1].float()

    # On renormalise UNIQUEMENT sur oui/non : le modele n'a le droit de
    # dire que ca, et un troisieme token serait du bruit.
    # / Renormalise over yes/no only.
    meilleurs = torch.topk(logits, 40)
    logit_oui, logit_non = None, None
    for valeur, indice in zip(meilleurs.values, meilleurs.indices):
        mot = tokeniseur.decode([indice]).strip().lower()
        if mot in MOTS_OUI and logit_oui is None:
            logit_oui = valeur
        elif mot in MOTS_NON and logit_non is None:
            logit_non = valeur
    if logit_oui is None or logit_non is None:
        logger.warning(
            "juge_local: ni « yes » ni « no » parmi les 40 tokens les "
            "plus probables — cette paire reste sans avis.",
        )
        return None

    probabilite = torch.softmax(
        torch.tensor([logit_oui, logit_non]), dim=0,
    )[0].item()
    return probabilite * 100.0
