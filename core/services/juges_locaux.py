"""
Les juges LOCAUX : plusieurs seconds avis, calcules sur cette machine.
/ The LOCAL judges: several second opinions, computed on this machine.

LOCALISATION : core/services/juges_locaux.py

CE QU'ILS SONT. Des encodeurs de 68 a 279 millions de parametres,
entrainés pour l'inference textuelle (NLI). On leur donne la SOURCE
comme premisse et l'AFFIRMATION comme hypothese, et on lit deux
probabilites : « ca decoule » et « ca se contredit ».

Ils tournent sur PROCESSEUR, sans clef d'API, et rien ne sort de la
machine. Pour un outil de deliberation qui traite des verbatims
d'assemblee, ce dernier point n'est pas un detail.

CE QU'ILS NE SONT PAS. Ce ne sont PAS des `AIModel`. Ils ne parlent pas
la meme langue : `appeler_llm` rend du texte, ceux-ci rendent un score.
Les forcer dans le referentiel les ferait PROPOSER AU CLIC comme modeles
d'extraction sur l'ecran de configuration IA, alors que LangExtract ne
sait pas les piloter.

ET ILS NE PILOTENT RIEN. Ce sont des SECONDS AVIS : ils n'ecrivent ni
`etat_de_verification`, ni `score_de_verification`, ni le libelle
affiche. Ils tournent a cote du juge de production pour etre compares a
lui sur des donnees reelles.

## POURQUOI CEUX-LA, ET POURQUOI PAS SHIELDSTRAL

ShieldStral 1.0 3B a tenu ce role du 18 au 19 aout 2026. Il coutait
**~24 000 ms de processeur par paire** et 7,7 Go de memoire. Les quatre
juges ci-dessous coutent **45 a 352 ms**, pour un pouvoir de detection
au moins egal — mesure du 19 aout, `benchmarks/juge_de_verification/`.

Le choix ne vient PAS de leur accord avec l'etalon gele : sur ce jeu, un
simple comptage de mots obtient 0,889, au-dessus de tous les modeles.
Il vient du **jeu adverse**, ou l'affirmation vraie est perturbee
mecaniquement sans que son vocabulaire change — un comptage de mots y
obtient 0,500 par construction. Sur ce jeu, et sur DEUX types d'erreur
independants :

| juge | negation | quantificateur |
|---|---|---|
| CamemBERTa v2 XNLI | 0,789 | 0,551 |
| mDeBERTa v3 XNLI | 0,766 | 0,698 |
| bge-m3 zeroshot | 0,762 | 0,664 |
| distilCamemBERT NLI | 0,678 | 0,606 |
| *les deux LettuceDetect francais* | *0,473 et 0,485* | *0,449 et 0,475* |

Les deux derniers sont **sous le hasard** : ecartes.

## LE CADRAGE FAIT TOUT, ET IL EST ICI, EN UN SEUL ENDROIT

Mesure du 19 aout : demander la question sur le PARAGRAPHE ENTIER
(`directe`) bat de loin le maximum pris phrase par phrase — 0,762 contre
0,638 pour mDeBERTa sur le jeu adverse. La raison est mecanique : un
maximum laisse une phrase NON perturbee sauver la paire.

C'est l'inverse de ce que dit l'etalon gele, ou le maximum par phrase
gagne. **L'agregation qui epouse le mieux une reference lexicalement
saturee est la mauvaise pour verifier.**

Le banc importe cette construction d'ici : deux copies poseraient deux
questions differentes, et la comparaison ne voudrait plus rien dire.
/ The framing lives here, once; the bench imports it.
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)

VERSION = "xnli-directe v1"

# LES QUATRE JUGES, ET CE QUI LES DEFINIT.
#
# `seuil` : le degre de bascule, sur 100, PROPRE a ce juge. Il est fige
# sur chaque avis au moment ou l'avis est rendu — les juges ne sont pas
# sur la meme regle, et relire un degre avec le seuil d'un autre ferait
# conclure au desaccord la ou il y a accord.
#
# `contradiction` : faut-il soustraire P(contradiction) de
# P(entailment) ? C'est le SEUL signal qu'un comptage de mots ne peut
# pas imiter — deux textes qui se contredisent partagent leur
# vocabulaire. Mesure du 19 aout : il vaut **+0,174 d'AUC** chez
# CamemBERTa comme chez mDeBERTa. `bge-m3` n'a que deux classes
# (entailment / not_entailment) et n'en dispose donc pas.
# / Contradiction is the one signal word-overlap cannot fake.
JUGES = {
    "camembertav2": {
        "depot": "almanach/camembertav2-base-xnli",
        "libelle": "CamemBERTa v2",
        "contradiction": True,
        # SON TOKENISEUR EST MAL DECLARE, ET L'OUBLIER NE LEVE AUCUNE
        # ERREUR. Son `tokenizer_config.json` annonce `RobertaTokenizer`
        # alors que son `tokenizer.json` porte un vocabulaire WordPiece.
        # `AutoTokenizer` suit la declaration, se retrouve sans table de
        # fusions, et decoupe CARACTERE PAR CARACTERE : 109 tokens la ou
        # il en faut 11, en silence. `PreTrainedTokenizerFast` lit le
        # `tokenizer.json` directement.
        # / Its config mis-declares the tokenizer class; AutoTokenizer
        # silently falls back to character level.
        "tokeniseur_brut": True,
    },
    "mdeberta": {
        "depot": "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
        "libelle": "mDeBERTa v3",
        "contradiction": True,
    },
    "bge-m3": {
        "depot": "MoritzLaurer/bge-m3-zeroshot-v2.0",
        "libelle": "bge-m3",
        "contradiction": False,
    },
    "distilcamembert": {
        "depot": "cmarkea/distilcamembert-base-nli",
        "libelle": "distilCamemBERT",
        "contradiction": True,
    },
}

# Le verrou protege le cache de chargement : le worker est a concurrence
# 1, mais rien ne garantit qu'il le restera, et deux chargements
# simultanes du meme modele doubleraient la memoire.
# / Guards the load cache: two concurrent loads would double the memory.
_verrou_de_chargement = threading.Lock()
_modeles_charges = {}


def methode(nom_du_juge):
    """
    Le libelle qui identifie un juge dans un avis.
    / The label identifying a judge in an opinion.

    LE CADRAGE FAIT PARTIE DU NOM, pas du reglage. `directe` et
    `par_phrase` ne posent pas la meme question, et la mesure a montre
    que l'ecart vaut plus de dix points d'AUC. Un avis dont on ignore le
    cadrage n'est pas relisable.
    / The framing belongs in the name: it is part of the question.
    """
    return f"{VERSION} — {JUGES[nom_du_juge]['libelle']}"


def seuil_du_juge(nom_du_juge):
    """
    Le seuil de bascule d'un juge, sur 100. / A judge's threshold.

    LOCALISATION : core/services/juges_locaux.py

    IL SE REGLE PAR L'ENVIRONNEMENT, ET C'EST DELIBERE. Un seuil ecrit
    en dur serait fige au moment du jugement : en changer exigerait de
    tout rejuger. Ici il est lu a chaque avis, et fige SUR L'AVIS — le
    changer ne rejuge donc rien de ce qui est deja en base, et le
    comparer reste possible.
    / Read from the environment, frozen on each opinion: changing it
    re-judges nothing.

    LE DEFAUT EST MESURE sur le JEU ADVERSE, seul jeu equilibre du
    dossier — voir `SEUILS_PAR_DEFAUT` en bas de fichier pour les quatre
    chiffres, leur reserve de sur-ajustement, et la conversion d'echelle
    qui les separe de ceux du banc.
    / The default is measured on the balanced adversarial set.
    """
    variable = f"SEUIL_{nom_du_juge.upper().replace('-', '_')}"
    demande = os.environ.get(variable)
    if demande:
        return float(demande)
    return SEUILS_PAR_DEFAUT[nom_du_juge]


def nombre_de_threads():
    """
    Les threads du calcul. / The compute threads.

    « Tout moins deux » par defaut : Docling et le serveur de dev vivent
    sur la meme machine, et l'ingestion doit garder de quoi tourner.
    / All but two: Docling shares this box.
    """
    demande = os.environ.get("JUGES_LOCAUX_THREADS")
    if demande:
        return int(demande)
    return max(1, (os.cpu_count() or 4) - 2)


def _charger(nom_du_juge):
    """
    Charge un juge, une seule fois, et le garde. / Loads once, keeps.

    LOCALISATION : core/services/juges_locaux.py

    LES QUATRE MODELES RESTENT RESIDENTS, et c'est un arbitrage assume :
    la memoire contre ~20 s de chargement par modele et par article. Le
    worker est long-vecu et dedie ; payer le chargement a chaque article
    coutait plus cher que la memoire.

    **CE QUE CELA COUTE, MESURE LE 19 AOUT 2026** (RSS du processus,
    `/proc/self/status`, apres une paire notee par chacun) :

    | apres chargement de | RSS courant | pic |
    |---|---|---|
    | python + torch | 0,11 Go | 0,11 Go |
    | + camembertav2 | 1,24 Go | 1,24 Go |
    | + mdeberta | 2,56 Go | 3,07 Go |
    | + bge-m3 | 4,96 Go | **6,01 Go** |
    | + distilcamembert | **5,13 Go** | 6,01 Go |

    **5,13 Go residents, 6,01 Go de pic au chargement.** C'est bien
    au-dela de la somme des poids (~4,1 Go en float32) : l'allocateur de
    torch et les tampons intermediaires font le reste.

    **La consequence est un choix d'hebergement, pas un detail.** Le pic
    de 6 Go, ajoute a une conversion Docling (~2 Go), a PostgreSQL et au
    serveur web, exclut un VPS a 4 ou 8 Go — et `nice` ne protege pas de
    l'OOM killer. Le levier principal est `bge-m3` : il coute a lui seul
    **2,40 Go** (4,96 − 2,56), soit plus que les trois autres reunis, et
    c'est aussi le plus lent des quatre.
    / Measured: 5.13 GB resident, 6.01 GB peak — far above the ~4.1 GB
    of weights. bge-m3 alone accounts for 2.40 GB.
    """
    if nom_du_juge in _modeles_charges:
        return _modeles_charges[nom_du_juge]

    with _verrou_de_chargement:
        # Un second fil a pu charger pendant l'attente du verrou.
        # / Another thread may have loaded while we waited.
        if nom_du_juge in _modeles_charges:
            return _modeles_charges[nom_du_juge]

        import torch
        from transformers import (
            AutoConfig, AutoModelForSequenceClassification, AutoTokenizer,
            PreTrainedTokenizerFast,
        )

        torch.set_num_threads(nombre_de_threads())
        juge = JUGES[nom_du_juge]
        logger.info("juges_locaux: chargement de %s…", juge["depot"])

        configuration = AutoConfig.from_pretrained(juge["depot"])
        if juge.get("tokeniseur_brut"):
            tokeniseur = PreTrainedTokenizerFast.from_pretrained(juge["depot"])
        else:
            tokeniseur = AutoTokenizer.from_pretrained(juge["depot"])

        modele = AutoModelForSequenceClassification.from_pretrained(
            juge["depot"], dtype=torch.float32,
        )
        modele.eval()

        # L'ORDRE DES ETIQUETTES CHANGE D'UN MODELE A L'AUTRE, et le
        # coder en dur donnerait un resultat INVERSE sans lever
        # d'erreur : `camembertav2` range `entailment` en 0,
        # `distilcamembert` le range en 1. On lit donc `id2label`.
        # / Label order differs per model; read id2label, never hardcode.
        libelles = {
            indice: str(nom).lower()
            for indice, nom in configuration.id2label.items()
        }
        indice_entailment = next(
            (indice for indice, nom in libelles.items()
             if nom.startswith("entail")), None,
        )
        if indice_entailment is None:
            raise RuntimeError(
                f"{juge['depot']} : aucune étiquette « entailment » dans "
                f"id2label ({configuration.id2label}).",
            )
        indice_contradiction = next(
            (indice for indice, nom in libelles.items()
             if nom.startswith("contradic")), None,
        )
        plafond = min(
            (getattr(modele.config, "max_position_embeddings", None) or 512)
            - 2,
            4096,
        )

        _modeles_charges[nom_du_juge] = (
            tokeniseur, modele, indice_entailment, indice_contradiction,
            plafond,
        )
        return _modeles_charges[nom_du_juge]


def probabilites_nli(nom_du_juge, source, affirmation):
    """
    P(entailment) et P(contradiction) pour une paire.
    / P(entailment) and P(contradiction) for one pair.

    LOCALISATION : core/services/juges_locaux.py

    LA PREMISSE EST LA SOURCE, L'HYPOTHESE EST L'AFFIRMATION : on demande
    si la source implique ce que l'affirmation avance. C'est l'ordre que
    tous les modeles NLI attendent, et l'inverser poserait une autre
    question.

    On juge le PARAGRAPHE ENTIER — cadrage `directe`. Voir la docstring
    du module : decouper en phrases et garder le maximum laisse une
    phrase non perturbee sauver la paire.
    / Source is the premise, claim the hypothesis, judged whole.

    :return: (p_entailment, p_contradiction ou None)
    """
    import torch

    (tokeniseur, modele, indice_entailment, indice_contradiction,
     plafond) = _charger(nom_du_juge)

    entrees = tokeniseur(
        source, affirmation, truncation="longest_first",
        max_length=plafond, return_tensors="pt",
    )
    with torch.no_grad():
        logits = modele(**entrees).logits[0]
    probabilites = torch.softmax(logits.float(), dim=-1)

    p_entailment = probabilites[indice_entailment].item()
    p_contradiction = (
        None if indice_contradiction is None
        else probabilites[indice_contradiction].item()
    )
    return p_entailment, p_contradiction


def noter_une_paire(nom_du_juge, affirmation, source):
    """
    Le degre d'un juge sur une paire, de 0 a 100.
    / One judge's degree on one pair, 0 to 100.

    LOCALISATION : core/services/juges_locaux.py

    DEUX ECHELLES, RAMENEES A UNE SEULE. Sans contradiction, le score est
    P(entailment), deja dans [0, 1]. Avec contradiction, il vaut
    P(entailment) − P(contradiction), qui vit dans [−1, 1] : on le
    ramene par (x + 1) / 2. Les deux sortent donc sur 100, et le SEUIL
    de chaque juge est lu sur cette echelle-la.
    / Two scales folded into one, so every degree reads out of 100.
    """
    p_entailment, p_contradiction = probabilites_nli(
        nom_du_juge, source, affirmation,
    )
    if JUGES[nom_du_juge]["contradiction"] and p_contradiction is not None:
        brut = (p_entailment - p_contradiction + 1.0) / 2.0
    else:
        brut = p_entailment
    return 100.0 * brut


# LES SEUILS PAR DEFAUT — MESURES LE 19 AOUT 2026 SUR LE JEU ADVERSE.
#
# Le jeu adverse est le SEUL jeu equilibre du dossier : 117 affirmations
# vraies et 156 versions perturbees des memes. Un « meilleur seuil » y
# veut donc dire quelque chose. Sur l'etalon gele il n'aurait aucun sens
# — 118 positives pour 27 negatives, et accepter tout donne deja 118/145.
#
# | juge | AUC | appariee | seuil | accord |
# |---|---|---|---|---|
# | camembertav2 | 0,728 | **0,853** | **49,7** | 190/273 |
# | mdeberta | **0,743** | 0,840 | **50,0** | 193/273 |
# | bge-m3 | 0,737 | 0,801 | **70,0** | 188/273 |
# | distilcamembert | 0,656 | 0,737 | **63,7** | 169/273 |
#
# **CE QUE CES CHIFFRES DISENT, ET QU'ON N'AURAIT PAS DEVINE.** Les deux
# juges qui lisent la contradiction optimisent EXACTEMENT au point
# neutre — logique apres coup : c'est le point ou P(entailment) egale
# P(contradiction). Mais `bge-m3`, qui n'a pas de classe contradiction
# et rend P(entailment) brut, optimise a **70**. Lui poser 50 le ferait
# confirmer bien trop de citations, **sans qu'aucune erreur ne le dise**.
# C'est precisement pour cette raison qu'un seuil se mesure par juge.
#
# **ILS SONT SUR-AJUSTES**, comme tout seuil choisi apres coup sur les
# points qui servent a l'evaluer. Ils valent comme point de depart, pas
# comme verite ; c'est l'AUC qui se lit sans cette reserve. Et le jeu
# adverse n'eprouve que DEUX types d'erreur — la negation et le
# quantificateur.
#
# **Attention a la conversion en les remesurant.** Le banc range le
# score a contradiction dans [−1, 1] ; la production le ramene sur 100
# par (x + 1) / 2 × 100. Un meilleur seuil de −0,006 au banc vaut donc
# 49,7 ici. Reporter le chiffre brut donnerait un seuil absurde, sans
# erreur.
# / Measured on the balanced adversarial set. Note bge-m3 optimises at
# 70, not at the neutral 50: thresholds are per judge, and mind the
# scale conversion.
SEUILS_PAR_DEFAUT = {
    "camembertav2": 49.7,
    "mdeberta": 50.0,
    "bge-m3": 70.0,
    "distilcamembert": 63.7,
}
