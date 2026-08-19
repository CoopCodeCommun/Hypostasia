"""
Banc d'essai MANUEL : des ENCODEURS comme juges d'implication.
/ MANUAL benchmark: ENCODERS as entailment judges.

LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

CE N'EST PAS UN TEST. C'est un script `__main__`, comme les deux autres
bancs de ce dossier. Il n'ecrit RIEN en base, n'appelle AUCUNE API, ne
facture rien : les modeles tournent sur processeur depuis le cache local
de HuggingFace.

## CE QU'UN ENCODEUR EST, ET POURQUOI C'EST DIFFERENT DES DEUX AUTRES BANCS

`comparer_un_juge.py` interroge un LLM par un PROMPT et lit du texte.
`comparer_shieldstral.py` interroge un LLM local et lit les LOGITS d'un
token unique. Ce banc-ci interroge des modeles qui ne sont pas des LLM :
des encodeurs de 68 a 608 millions de parametres, entraines POUR CETTE
TACHE — verifier qu'un texte est fonde sur un autre.

Deux familles, deux sorties differentes :

| famille | ce que le modele rend | exemples |
|---|---|---|
| `spans` | une etiquette PAR TOKEN de l'affirmation | LettuceDetect |
| `nli`   | trois ou deux classes pour la PAIRE entiere | XNLI, bge-m3 |

Consequence directe : un modele `spans` dit QUELLE PART de l'affirmation
la source ne fonde pas. Un modele `nli` ne dit que « oui / non / neutre ».

## LE CADRAGE FAIT TOUT — TROISIEME MESURE, TROISIEME CONFIRMATION

Le 18 aout, ShieldStral passait d'une AUC de 0,538 a 0,923 selon qu'on
mettait l'affirmation et la source dans le meme champ ou dans deux.
La meme chose se produit ici, et elle a ete MESUREE avant d'ecrire ce
banc, sur l'exemple publie par la carte de `lettucedect-210m-eurobert-fr-v1` :

| cadrage | ce que le modele repond sur l'exemple de sa propre carte |
|---|---|
| `nu` — la source et l'affirmation, rien autour | il ne signale RIEN |
| `resume` — le gabarit « Resume le texte suivant » | P(non soutenu) = 0,571, spans bancals |
| `qa` — le gabarit « Reponds brievement a la question » | P = 0,951, **le span exact de la carte** |

Les TROIS cadrages restent donc dans ce banc, exactement comme les deux
cadrages de ShieldStral y restent : retirer les mauvais laisserait le bon
sans point de comparaison, et la prochaine personne qui doute referait
l'erreur.

Les gabarits sont ceux de la bibliotheque `lettucedetect` elle-meme
(`lettucedetect/prompts/summary_prompt_fr.txt` et `qa_prompt_fr.txt`).
Ils sont recopies ici parce que la bibliotheque n'est PAS installee : ce
banc n'utilise que `transformers`. C'est la seule copie que ce fichier
s'autorise, et elle est marquee comme telle a l'endroit ou elle vit.

## L'AGREGATION EST LA SEVERITE, TRANSPOSEE

Un modele `spans` etiquette chaque token. Il faut en tirer UN score. Ce
choix n'est pas technique : c'est le meme arbitrage que « large » contre
« strict » chez le juge local, et l'addendum du 18 aout a mesure qu'il
decide de tout (de 0/15 a 15/15 selon la consigne).

| agregation | ce qu'elle demande | la severite correspondante |
|---|---|---|
| `meilleure_phrase` | la source fonde-t-elle AU MOINS UNE phrase ? | large |
| `couverture` | quelle PART de l'affirmation fonde-t-elle ? | intermediaire |
| `pire_token` | fonde-t-elle TOUT, jusqu'au dernier mot ? | strict |

Les trois se calculent d'une SEULE passe avant : les etiquettes par token
sont deja la. Les jouer toutes ne coute donc rien.

## POURQUOI L'AUC, ET RIEN D'AUTRE

Un taux d'accord depend du seuil qu'on a choisi, et tout ce dossier
existe parce que le seuil etait le probleme. L'AUC n'en depend pas.
Elle est importee de `comparer_shieldstral.py`, sans copie — deux
implementations de la meme metrique finiraient par ne plus mesurer la
meme chose, et les chiffres de ce banc doivent se lire A COTE de ceux de
ShieldStral, pas en face.

## ENTRE QUELLES BORNES UNE AUC SE LIT ICI — ET CE N'EST NI 0,5 NI 1,0

Deux chiffres mesures le 19 aout 2026 encadrent tout ce que ce banc
produit. Les lire de travers ferait conclure l'inverse de la mesure.

| borne | valeur | ce qu'elle veut dire |
|---|---|---|
| **le PLAFOND** | **0,690** | `gemini-2.5-flash`, le modele qui a PRODUIT l'etalon, rejouant les 145 paires, contre ses propres verdicts geles. Mesure par `mesurer_le_plafond_de_l_etalon.py`. |
| **le PLANCHER UTILE** | **0,889** | un simple recouvrement de mots entre la source et l'affirmation (`score_lexical`). |

**Le plafond est SOUS le plancher utile**, et ce n'est pas une faute de
frappe. Il faut donc lire les deux ensemble :

1. **Depasser 0,690 ne prouve pas grand-chose.** La reference elle-meme
   n'y arrive pas. Elle n'y arrive pas parce que le protocole texte ne
   rend que QUATRE crans — sur ces 145 paires, **120 recoivent
   exactement 70** : un juge qui donne la meme note a 83 % des paires ne
   peut pas les classer, et son AUC s'effondre sur les ex aequo. C'est
   une limite du PROTOCOLE, pas de la tache, et c'est l'argument meme
   pour un juge a score continu.
2. **Ne pas depasser 0,889 est le vrai constat.** Aucun candidat mesure
   le 19 aout ne bat le compteur de mots, parce que les deux references
   sont lexicalement SATUREES : le paragraphe a ete ecrit A PARTIR de
   ses sources et en reprend le vocabulaire. **Une AUC contre ces
   references ne distingue donc pas un juge d'implication d'un `grep`.**

## CE QUE CE BANC NE MESURE PAS

La VERITE. La reference des 145 paires gelees est `gemini-2.5-flash`,
dont la reproductibilite mesuree est de 77 % et dont l'etalon a ete
produit a temperature 0,7 — donc en echantillonnant, un tirage parmi
d'autres (de 105 a 133 positifs sur cinq executions). Celle des 15
paires relues a la main est un avis humain sur UNE SEULE affirmation.
Un desaccord n'est pas une erreur du candidat : c'est un desaccord.

## LE JEU ADVERSE — LA SEULE MESURE QUI TRANCHE

Puisqu'une AUC contre les deux references ne separe pas un juge d'un
`grep`, ce banc porte un troisieme jeu, `--adverse`, construit pour que
le `grep` n'y puisse RIEN.

On prend chaque paire que la reference declare « soutient », et on NIE
l'affirmation — dans la phrase que la source etablit, pas dans une
phrase au hasard (voir `nier_l_affirmation`). La negation :

- **n'enleve aucun mot** de l'affirmation ;
- n'ajoute que « ne » / « n' » et « pas », tous sous quatre caracteres,
  donc **invisibles pour `score_lexical`** ;
- **fait basculer la verite** : une source qui etablissait l'affirmation
  ne peut pas etablir sa negation.

**Verifie le 19 aout 2026 : le recouvrement de mots rend un score
RIGOUREUSEMENT IDENTIQUE sur les 114 paires avant et apres negation,
donc une AUC de 0,500 exactement.** Tout ce qui depasse 0,5 sur ce jeu
est une detection que le comptage de mots ne peut pas produire.

Le jeu est en outre **equilibre** — 114 positives, 114 negatives — la ou
l'etalon porte 118 contre 27. L'accord y redevient lisible.

    # le plancher de bruit d'abord, TOUJOURS — deux passes comparees
    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_de_verification/comparer_un_encodeur.py \\
        lettucedect-v2-mmbert-base --plancher

    # puis l'accord et l'AUC, sur les 145 paires gelees
    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_de_verification/comparer_un_encodeur.py \\
        lettucedect-v2-mmbert-base --etalon

    # LE JEU ADVERSE — celui ou le compteur de mots est a 0,500
    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_de_verification/comparer_un_encodeur.py \\
        --tous --adverse

    # tous les candidats, l'etalon gele
    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_de_verification/comparer_un_encodeur.py --tous --etalon
"""

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."),
))

# LA METRIQUE ET LES DEUX JEUX DE PAIRES VIENNENT DU BANC SHIELDSTRAL,
# SANS COPIE. Les chiffres de ce banc-ci doivent se lire A COTE des
# siens : deux implementations de l'AUC, ou deux chargeurs de l'etalon,
# finiraient par ne plus mesurer la meme chose.
# / The metric and both pair sets are imported from the ShieldStral
# bench, never copied: these numbers must be readable next to its own.
from comparer_shieldstral import (  # noqa: E402
    aire_sous_la_courbe, meilleur_seuil, paires_de_l_etalon,
    paires_relues_a_la_main,
)

# Les candidats, tels que le recap du 19 aout 2026 les liste.
# `famille` decide de la facon d'interroger le modele, pas sa taille.
# / The candidates. `famille` decides how the model is queried.
CANDIDATS = {
    "lettucedect-v2-mmbert-base": {
        "depot": "KRLabsOrg/lettucedect-v2-mmbert-base",
        "famille": "spans",
    },
    "lettucedect-210m-eurobert-fr": {
        "depot": "KRLabsOrg/lettucedect-210m-eurobert-fr-v1",
        "famille": "spans",
    },
    "lettucedect-610m-eurobert-fr": {
        "depot": "KRLabsOrg/lettucedect-610m-eurobert-fr-v1",
        "famille": "spans",
    },
    "camembertav2-base-xnli": {
        "depot": "almanach/camembertav2-base-xnli",
        "famille": "nli",
        # SON TOKENISEUR EST MAL DECLARE, ET L'OUBLIER NE LEVE AUCUNE
        # ERREUR. Son `tokenizer_config.json` annonce `RobertaTokenizer`
        # alors que son `tokenizer.json` porte un vocabulaire WordPiece.
        # `AutoTokenizer` suit la declaration, se retrouve sans table de
        # fusions, et decoupe alors CARACTERE PAR CARACTERE : 109 tokens
        # la ou il en faut 11, en silence. `PreTrainedTokenizerFast` lit
        # le `tokenizer.json` directement et rend le bon decoupage.
        # / Its config mis-declares the tokenizer class; AutoTokenizer
        # then silently falls back to character-level. Read tokenizer.json.
        "tokeniseur": "fast_brut",
    },
    "distilcamembert-base-nli": {
        "depot": "cmarkea/distilcamembert-base-nli",
        "famille": "nli",
    },
    "mdeberta-v3-base-mnli-xnli": {
        "depot": "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
        "famille": "nli",
    },
    "bge-m3-zeroshot": {
        "depot": "MoritzLaurer/bge-m3-zeroshot-v2.0",
        "famille": "nli",
    },
}

# LES GABARITS DE LETTUCEDETECT, RECOPIES DE LA BIBLIOTHEQUE.
# Source : `lettucedetect/prompts/summary_prompt_fr.txt` et
# `qa_prompt_fr.txt`, assembles par `PromptUtils.format_context`. La
# bibliotheque n'est pas installee — ce banc n'utilise que
# `transformers` — donc ces deux chaines sont la SEULE copie que ce
# fichier s'autorise. Si un chiffre de ce banc surprend, c'est ici qu'il
# faut verifier que la copie n'a pas derive de l'original.
# / The two lettucedetect FR templates, copied because the library is not
# installed. This is the only copy this file allows itself.
GABARIT_RESUME = "Résume le texte suivant :\npassage 1: {source}\nSortie : "

# La QUESTION du gabarit QA. Notre tache n'en a pas : une affirmation de
# synthese ne repond pas a une question posee, elle resume un debat.
# Celle-ci est donc une VARIABLE de l'experience, pas une donnee — d'ou
# sa presence ici, visible, et non enfouie dans une f-string.
# / Our task has no question; this one is an experimental variable.
QUESTION_DU_GABARIT_QA = "Que dit le débat à ce sujet ?"

GABARIT_QA = (
    "Réponds brièvement à la question suivante :\n"
    "{question}\n"
    "Note que ta réponse doit être basée uniquement sur les 1 passages "
    "suivants :\n"
    "passage 1: {source}\n"
    "Si les passages ne contiennent pas les informations nécessaires pour "
    "répondre à la question, réponds s'il te plaît par : \"Impossible de "
    "répondre sur la base des passages fournis.\"\nSortie :"
)

# L'ECART MINIMAL exige au controle d'orientation. Un modele qui
# ordonne bien la paire vraie et la paire fausse mais ne les separe
# que de quelques millemes n'a rien demontre : son AUC se calculera
# sur une plage ou tout se vaut.
# / The minimum gap the orientation check demands.
MARGE_D_ORIENTATION = 0.10

CADRAGES_SPANS = ["nu", "resume", "qa"]
CADRAGES_NLI = ["directe", "par_phrase"]
AGREGATIONS_SPANS = ["meilleure_phrase", "couverture", "pire_token"]


def nombre_de_threads():
    """
    Les threads du calcul. / The compute threads.

    Le defaut est « tout moins deux », comme le juge local : il faut
    laisser de quoi tourner a Docling et au serveur de dev, qui vivent
    sur la meme machine.
    / Default is "all but two": Docling and the dev server share this box.
    """
    demande = os.environ.get("ENCODEUR_THREADS")
    if demande:
        return int(demande)
    return max(1, (os.cpu_count() or 4) - 2)


def phrases_de(texte):
    """
    Decoupe une affirmation en phrases. / Splits a claim into sentences.

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    Le decoupage sert l'agregation `meilleure_phrase` et le cadrage
    `par_phrase` : tous deux demandent « la source fonde-t-elle AU MOINS
    UNE des choses que l'affirmation avance ». Une phrase est
    l'approximation la plus simple d'« une chose avancee ».

    Le decoupage est volontairement grossier — un point suivi d'une
    espace. Un decoupeur savant ferait mieux sur les abreviations, mais
    il ajouterait une dependance, et l'erreur qu'il eviterait porterait
    sur quelques caracteres.

    :param texte: l'affirmation entiere
    :return: la liste des (debut, fin) de chaque phrase, en caracteres
    """
    bornes = []
    debut = 0
    for separateur in re.finditer(r"[.!?]+[\s\n]+|\n+", texte):
        fin = separateur.end()
        if fin - debut > 1:
            bornes.append((debut, fin))
        debut = fin
    if debut < len(texte):
        bornes.append((debut, len(texte)))
    return bornes or [(0, len(texte))]


def texte_de_premier_segment(cadrage, source):
    """
    Le premier segment envoye au modele, selon le cadrage.
    / The first segment sent to the model, per framing.
    """
    if cadrage == "resume":
        return GABARIT_RESUME.format(source=source)
    if cadrage == "qa":
        return GABARIT_QA.format(
            question=QUESTION_DU_GABARIT_QA, source=source,
        )
    return source


def charger(candidat):
    """
    Charge un candidat sur processeur. / Loads a candidate on CPU.

    :return: (tokeniseur, modele, index de l'etiquette utile)
    """
    import torch
    from transformers import (
        AutoConfig, AutoModelForSequenceClassification,
        AutoModelForTokenClassification, AutoTokenizer,
        PreTrainedTokenizerFast,
    )

    depot = candidat["depot"]
    configuration = AutoConfig.from_pretrained(depot)

    if candidat.get("tokeniseur") == "fast_brut":
        tokeniseur = PreTrainedTokenizerFast.from_pretrained(depot)
    else:
        tokeniseur = AutoTokenizer.from_pretrained(depot)

    if candidat["famille"] == "spans":
        modele = AutoModelForTokenClassification.from_pretrained(
            depot, dtype=torch.float32,
        )
        # LES DEUX MODELES EUROBERT N'ONT PAS D'`id2label` : leur config
        # ne porte que `LABEL_0` / `LABEL_1`. La convention LettuceDetect
        # est 1 = « non soutenu », et le modele v2 la confirme dans sa
        # propre config. `verifier_l_orientation` la CONTROLE avant toute
        # mesure, au lieu de la supposer.
        # / EuroBERT ships no id2label; the convention is checked, not assumed.
        etiquette_utile = 1
        # Un modele a spans n'a pas de classe « contradiction » : il
        # etiquette « soutenu / non soutenu », et « non soutenu »
        # confond l'absence et la negation.
        # / Span models have no contradiction class.
        etiquette_contraire = None
    else:
        modele = AutoModelForSequenceClassification.from_pretrained(
            depot, dtype=torch.float32,
        )
        # L'ORDRE DES ETIQUETTES CHANGE D'UN MODELE A L'AUTRE, et le
        # coder en dur donnerait un resultat inverse sans lever
        # d'erreur : `camembertav2` range `entailment` en 0,
        # `distilcamembert` le range en 1. On lit donc `id2label`.
        # / Label order differs per model; read id2label, never hardcode.
        libelles = {
            indice: str(nom).lower()
            for indice, nom in configuration.id2label.items()
        }
        etiquette_utile = next(
            (indice for indice, nom in libelles.items()
             if nom.startswith("entail")),
            None,
        )
        if etiquette_utile is None:
            raise SystemExit(
                f"{depot} : aucune etiquette « entailment » dans "
                f"id2label ({configuration.id2label}).",
            )
        # LA CONTRADICTION EST LE SEUL SIGNAL QU'UN COMPTEUR DE MOTS NE
        # PEUT PAS IMITER. « 67 millions » et « 69 millions » partagent
        # tout leur vocabulaire ; seule une tete NLI sait que l'un nie
        # l'autre. Ne lire que P(entailment), c'est jeter exactement ce
        # qui distingue un juge de verification d'un `grep` — et la
        # baseline lexicale montre que ce `grep` fait deja 0,889.
        # Les modeles a DEUX classes (bge-m3 : entailment /
        # not_entailment) n'en ont pas : la valeur reste None.
        # / Contradiction is the one signal word-overlap cannot fake.
        etiquette_contraire = next(
            (indice for indice, nom in libelles.items()
             if nom.startswith("contradic")),
            None,
        )

    modele.eval()
    return tokeniseur, modele, etiquette_utile, etiquette_contraire


def scores_par_token(tokeniseur, modele, etiquette_utile, premier_segment,
                     affirmation, longueur_maximale):
    """
    P(soutenu) pour chaque caractere de l'affirmation.
    / P(supported) for each character of the claim.

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    Le modele etiquette des TOKENS ; les agregations raisonnent en
    PHRASES. On projette donc chaque token sur les caracteres qu'il
    couvre, ce que `return_offsets_mapping` donne directement.

    Seuls les tokens du SECOND segment comptent — `sequence_ids` vaut 1
    pour eux. Les tokens du premier segment (la source, gabarit compris)
    sont masques a l'entrainement : leur etiquette ne veut rien dire.
    / Only the second segment's tokens carry meaning.

    :return: (liste de (debut, fin, proba_soutenu), le texte a-t-il ete tronque)
    """
    import torch

    entrees = tokeniseur(
        premier_segment, affirmation,
        truncation="only_first", max_length=longueur_maximale,
        return_offsets_mapping=True, return_tensors="pt",
    )
    identifiants_de_segment = entrees.sequence_ids(0)
    decalages = entrees["offset_mapping"][0].tolist()

    with torch.no_grad():
        logits = modele(
            input_ids=entrees["input_ids"],
            attention_mask=entrees["attention_mask"],
        ).logits[0]
    probabilites = torch.softmax(logits.float(), dim=-1)

    par_token = []
    for rang, (segment, (debut, fin)) in enumerate(
        zip(identifiants_de_segment, decalages),
    ):
        if segment != 1 or debut == fin:
            continue
        proba_non_soutenu = probabilites[rang][etiquette_utile].item()
        par_token.append((debut, fin, 1.0 - proba_non_soutenu))

    dernier_caractere_vu = par_token[-1][1] if par_token else 0
    a_ete_tronque = dernier_caractere_vu < len(affirmation) - 1
    return par_token, a_ete_tronque


def agreger(par_token, affirmation, agregation):
    """
    Un score unique a partir des etiquettes par token.
    / A single score from the per-token labels.

    Voir la docstring du module : cette fonction EST la severite.
    """
    if not par_token:
        return None

    if agregation == "pire_token":
        return min(proba for _debut, _fin, proba in par_token)

    if agregation == "couverture":
        return sum(p for _d, _f, p in par_token) / len(par_token)

    # `meilleure_phrase` : la phrase la mieux soutenue de l'affirmation.
    # C'est la severite « large » : il suffit que la source etablisse
    # UNE des choses que l'affirmation avance.
    # / The best-supported sentence: the "lenient" severity.
    #
    # CHAQUE TOKEN VA A LA PHRASE QU'IL RECOUVRE LE PLUS, et surtout pas
    # a celle qui le CONTIENT entierement. Exiger l'inclusion perd le
    # PREMIER MOT DE CHAQUE PHRASE : les tokeniseurs SentencePiece
    # attachent l'espace precedent au token (« ▁Les »), dont l'empan
    # chevauche alors la frontiere et n'est inclus dans aucune des deux
    # phrases. Mesure du 19 aout : **503 tokens sur 29 264 (1,7 %)**
    # disparaissaient ainsi, jusqu'a 6 sur une meme affirmation — et le
    # mot perdu etait a chaque fois celui qui ouvre la phrase.
    # / Assign each token to the sentence it overlaps most: requiring
    # containment silently drops each sentence's first word.
    bornes = phrases_de(affirmation)
    probas_par_phrase = [[] for _ in bornes]
    for debut, fin, proba in par_token:
        recouvrements = [
            min(fin, fin_de_phrase) - max(debut, debut_de_phrase)
            for debut_de_phrase, fin_de_phrase in bornes
        ]
        meilleur_recouvrement = max(recouvrements)
        if meilleur_recouvrement <= 0:
            continue
        probas_par_phrase[recouvrements.index(meilleur_recouvrement)].append(
            proba,
        )

    meilleure = None
    for probas_de_la_phrase in probas_par_phrase:
        if not probas_de_la_phrase:
            continue
        moyenne = sum(probas_de_la_phrase) / len(probas_de_la_phrase)
        meilleure = moyenne if meilleure is None else max(meilleure, moyenne)
    return meilleure


def score_nli(tokeniseur, modele, etiquette_utile, etiquette_contraire,
              source, affirmation, cadrage, longueur_maximale):
    """
    P(entailment) pour une paire, selon le cadrage.
    / P(entailment) for one pair, per framing.

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    La PREMISSE est la source, l'HYPOTHESE est l'affirmation : on demande
    si la source implique ce que l'affirmation avance. C'est l'ordre que
    tous les modeles NLI attendent, et l'inverser demanderait autre chose.

    Le cadrage `par_phrase` pose la MEME question, phrase par phrase, et
    garde le maximum : c'est la severite « large » — il suffit que la
    source etablisse une des choses avancees. Le cadrage `directe` pose
    la question sur le paragraphe entier, c'est-a-dire la severite
    stricte, celle dont l'addendum du 18 aout a mesure qu'elle ne
    retient presque rien.
    / `par_phrase` is the lenient severity, `directe` the strict one.

    :return: (le score, le nombre de passes avant, texte tronque ou non)
    """
    import torch

    if cadrage == "par_phrase":
        morceaux = [
            affirmation[debut:fin].strip()
            for debut, fin in phrases_de(affirmation)
        ]
        morceaux = [morceau for morceau in morceaux if morceau]
    else:
        morceaux = [affirmation]

    meilleur, meilleur_net, tronque = None, None, False
    for morceau in morceaux:
        entrees = tokeniseur(
            source, morceau, truncation="longest_first",
            max_length=longueur_maximale, return_tensors="pt",
        )
        if entrees["input_ids"].shape[1] >= longueur_maximale:
            tronque = True
        with torch.no_grad():
            logits = modele(**entrees).logits[0]
        probabilites = torch.softmax(logits.float(), dim=-1)
        proba = probabilites[etiquette_utile].item()
        meilleur = proba if meilleur is None else max(meilleur, proba)
        if etiquette_contraire is not None:
            # P(entailment) MOINS P(contradiction). C'est le seul score
            # de ce banc qu'un compteur de mots ne peut pas imiter : deux
            # textes qui se contredisent partagent leur vocabulaire.
            # / The one score word-overlap cannot fake.
            net = proba - probabilites[etiquette_contraire].item()
            meilleur_net = net if meilleur_net is None \
                else max(meilleur_net, net)
    return meilleur, meilleur_net, len(morceaux), tronque


def verifier_l_orientation(candidat, tokeniseur, modele, etiquette_utile,
                           etiquette_contraire, longueur_maximale):
    """
    Le modele repond-il DANS LE BON SENS ? / Does the model answer the
    right way round?

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    CE CONTROLE EXISTE PARCE QU'UNE ETIQUETTE INVERSEE NE LEVE AUCUNE
    ERREUR. Les deux modeles EuroBERT ne declarent pas leurs etiquettes
    (`LABEL_0` / `LABEL_1`) : rien, dans leur config, ne dit laquelle
    vaut « non soutenu ». Un banc qui se tromperait de sens rendrait une
    AUC symetrique — 0,27 au lieu de 0,73 — et le chiffre aurait l'air
    d'un mauvais modele plutot que d'une erreur de lecture.

    On pose donc au modele une paire dont la reponse est connue : une
    source qui dit 67 millions, une affirmation qui dit 69. Un modele
    oriente correctement doit noter cette paire PLUS BAS qu'une paire ou
    l'affirmation recopie la source.
    / A reversed label raises no error; this pins the direction against a
    pair whose answer is known.

    :return: (l'orientation est-elle correcte, le score faux, le score vrai)
    """
    source = (
        "La France est un pays d'Europe. La capitale de la France est "
        "Paris. La population de la France est de 67 millions."
    )
    affirmation_fausse = (
        "La capitale de la France est Paris. La population de la France "
        "est de 69 millions."
    )
    affirmation_vraie = (
        "La capitale de la France est Paris. La population de la France "
        "est de 67 millions."
    )

    scores = []
    for affirmation in (affirmation_fausse, affirmation_vraie):
        if candidat["famille"] == "spans":
            par_token, _ = scores_par_token(
                tokeniseur, modele, etiquette_utile,
                texte_de_premier_segment("qa", source), affirmation,
                longueur_maximale,
            )
            scores.append(agreger(par_token, affirmation, "couverture"))
        else:
            score, _net, _passes, _tronque = score_nli(
                tokeniseur, modele, etiquette_utile, etiquette_contraire,
                source, affirmation, "directe", longueur_maximale,
            )
            scores.append(score)

    score_faux, score_vrai = scores

    # UNE MARGE, PAS UN SIGNE. Sans marge, un modele qui note 0,964 la
    # paire fausse et 0,994 la vraie passe « correct » : il ORDONNE bien
    # deux points, mais il ne les SEPARE pas, et son AUC se calculera
    # ensuite sur une plage ou tout se vaut. C'est exactement l'etat du
    # 610m, mesure le 19 aout. La marge le fait dire.
    # / A sign is not enough: 0.964 vs 0.994 orders without separating.
    ecart = score_vrai - score_faux
    return ecart >= MARGE_D_ORIENTATION, score_faux, score_vrai, ecart


def longueur_maximale_de(tokeniseur, modele):
    """
    Le plafond de tokens du modele. / The model's token ceiling.

    On lit la config du MODELE, pas celle du tokeniseur : plusieurs
    candidats declarent `model_max_length` a 1e30, ce qui ferait
    depasser la table de positions et lever une erreur d'index en pleine
    mesure.
    / Read the model's ceiling, not the tokenizer's: several candidates
    declare 1e30 and would overflow the position table.
    """
    plafond = getattr(modele.config, "max_position_embeddings", None) or 512
    return min(plafond - 2, 4096)


def mesurer(nom, candidat, paires, cadrages, agregations):
    """
    Fait noter toutes les paires par un candidat. / Scores all pairs.

    :return: ({"cadrage|agregation": [scores]}, duree, nombre de passes)
    """
    import torch

    torch.set_num_threads(nombre_de_threads())
    print(f"\n  Chargement de {candidat['depot']}…", flush=True)
    tokeniseur, modele, etiquette_utile, etiquette_contraire = \
        charger(candidat)
    longueur_maximale = longueur_maximale_de(tokeniseur, modele)

    correcte, score_faux, score_vrai, ecart = verifier_l_orientation(
        candidat, tokeniseur, modele, etiquette_utile, etiquette_contraire,
        longueur_maximale,
    )
    marque = "✓" if correcte else "⚠ NON SÉPARÉE"
    print(
        f"  orientation : {marque} — la paire fausse note "
        f"{score_faux:.3f}, la paire vraie {score_vrai:.3f}, "
        f"écart {ecart:+.3f} (marge exigée {MARGE_D_ORIENTATION:.2f})",
        flush=True,
    )
    if not correcte:
        print(
            "    Ce candidat ne SÉPARE pas une affirmation exacte d'une "
            "affirmation fausse sur l'exemple\n    de sa propre carte. "
            "Ses chiffres ci-dessous ne sont pas concluants : ils peuvent "
            "venir\n    du modèle comme du chemin de chargement.",
            flush=True,
        )

    debut = time.time()
    nombre_de_passes = 0
    resultats = {}

    for cadrage in cadrages:
        if candidat["famille"] == "spans":
            par_agregation = {agregation: [] for agregation in agregations}
            tronquees = 0
            for paire in paires:
                par_token, tronque = scores_par_token(
                    tokeniseur, modele, etiquette_utile,
                    texte_de_premier_segment(cadrage, paire["source"]),
                    paire["affirmation"], longueur_maximale,
                )
                nombre_de_passes += 1
                tronquees += 1 if tronque else 0
                for agregation in agregations:
                    par_agregation[agregation].append(
                        agreger(par_token, paire["affirmation"], agregation),
                    )
            for agregation, scores in par_agregation.items():
                resultats[f"{cadrage}|{agregation}"] = scores
            if tronquees:
                print(f"    ⚠ {tronquees} affirmation(s) tronquée(s) "
                      f"en cadrage {cadrage}", flush=True)
        else:
            scores, scores_nets, tronquees = [], [], 0
            for paire in paires:
                score, net, passes, tronque = score_nli(
                    tokeniseur, modele, etiquette_utile, etiquette_contraire,
                    paire["source"], paire["affirmation"], cadrage,
                    longueur_maximale,
                )
                nombre_de_passes += passes
                tronquees += 1 if tronque else 0
                scores.append(score)
                scores_nets.append(net)
            resultats[f"{cadrage}|entiere"] = scores
            if any(net is not None for net in scores_nets):
                resultats[f"{cadrage}|moins_contradiction"] = scores_nets
            if tronquees:
                print(f"    ⚠ {tronquees} paire(s) tronquée(s) "
                      f"en cadrage {cadrage}", flush=True)

    return resultats, time.time() - debut, nombre_de_passes


def afficher(nom, resultats, paires, duree, nombre_de_passes):
    """
    Le tableau d'un candidat. / One candidate's table.

    LES DEUX AUC SE LISENT ENSEMBLE. La globale se compare aux 0,734 de
    ShieldStral sur ces memes paires ; la stratifiee dit ce que vaut le
    juge une fois retire tout ce qui distingue les 23 paragraphes entre
    eux. Un ecart large entre les deux est en lui-meme le resultat : il
    signale que la globale mesurait le paragraphe, pas le jugement.
    / Read both: a wide gap means the global AUC was measuring the
    paragraph rather than the judgement.
    """
    verites = [paire["verite"] for paire in paires]
    # Le groupe est EXPLICITE quand le jeu en pose un (cas adverse),
    # sinon c'est l'affirmation : deux sources du meme paragraphe.
    # / Explicit group when the set defines one, else the claim.
    groupes = [
        paire.get("groupe", paire["affirmation"]) for paire in paires
    ]

    if duree is not None:
        print(f"\n  {nom} — {nombre_de_passes} passes avant en {duree:.0f} s "
              f"({1000 * duree / max(nombre_de_passes, 1):.0f} ms/passe)")
    else:
        print(f"\n  {nom}")

    def une_ligne(intitule, valeurs):
        """Une ligne du tableau, candidat ou baseline. / One table row."""
        utiles = [
            (score, verite, groupe)
            for score, verite, groupe in zip(valeurs, verites, groupes)
            if score is not None
        ]
        if not utiles:
            return None
        notes = [score for score, _v, _g in utiles]
        verdicts = [verite for _s, verite, _g in utiles]
        appartenances = [groupe for _s, _v, groupe in utiles]
        auc = aire_sous_la_courbe(notes, verdicts)
        strat, macro, _couples, _n, mini, maxi = auc_stratifiee(
            notes, verdicts, appartenances,
        )
        # L'AMPLITUDE DES SCORES DECIDE SI L'AUC VEUT DIRE QUELQUE CHOSE.
        # Une AUC calculee sur une plage de 0,004 est du bruit
        # arithmetique, et trois decimales lui donnent une autorite
        # qu'elle n'a pas. Le 610m, satur 0,96–1,00, est exactement ce
        # cas. / A tiny score range makes the AUC arithmetic noise.
        amplitude = max(notes) - min(notes)
        return (intitule, auc, strat, macro, mini, maxi, amplitude,
                len(utiles))

    print(f"  {'cadrage / agrégation':30} {'AUC':>6} {'strat.':>7} "
          f"{'macro':>6} {'étendue groupes':>17} {'ampl.':>7}")

    lignes = []
    for cle, scores in resultats.items():
        cadrage, agregation = cle.split("|")
        ligne = une_ligne(f"{cadrage:10} {agregation}", scores)
        if ligne:
            lignes.append(ligne)

    for (intitule, auc, strat, macro, mini, maxi, amplitude,
         _total) in sorted(lignes, key=lambda l: -(l[1] or 0)):
        print(f"  {intitule:30} {auc:>6.3f} {strat:>7.3f} {macro:>6.3f} "
              f"{f'{mini:.2f} – {maxi:.2f}':>17} {amplitude:>7.3f}")

    # LA BASELINE LEXICALE, DANS CHAQUE TABLEAU, SANS EXCEPTION.
    # C'est elle le comparateur, pas 0,5. Un candidat qui ne la depasse
    # pas n'a pas montre qu'il verifie : il a pu compter des mots.
    # / The lexical baseline belongs in every table: it is the comparator.
    baseline = une_ligne(
        "RECOUVREMENT DE MOTS",
        [score_lexical(paire["source"], paire["affirmation"])
         for paire in paires],
    )
    if baseline:
        intitule, auc, strat, macro, mini, maxi, amplitude, _t = baseline
        print(f"  {'':30} {'':>6} {'':>7} {'':>6} {'':>17} {'':>7}")
        print(f"  {intitule:30} {auc:>6.3f} {strat:>7.3f} {macro:>6.3f} "
              f"{f'{mini:.2f} – {maxi:.2f}':>17} {amplitude:>7.3f}")

    _a, _m, couples, groupes_utiles, _mi, _ma = auc_stratifiee(
        list(range(len(verites))), verites, groupes,
    )
    print(f"  → l'AUC stratifiée repose sur {couples} couples dans "
          f"{groupes_utiles} affirmations mixtes ; un écart de moins de "
          f"0,1 n'y est pas résolu.")


# LES VERBES QUE LA NEGATION MECANIQUE SAIT TRAITER. Liste volontairement
# COURTE : mieux vaut ne transformer qu'une partie des paires, et savoir
# laquelle, que d'en transformer toutes et d'en abimer certaines.
# / A deliberately short verb list: better to transform fewer pairs and
# know which, than to transform all and mangle some.
VERBES_NIABLES = (
    "est", "sont", "a", "ont", "peut", "peuvent", "doit", "doivent",
    "permet", "permettent", "represente", "représente", "représentent",
    "constitue", "constituent", "vise", "visent", "favorise", "favorisent",
    "reconnait", "reconnaît", "reconnaissent", "offre", "offrent",
    "apporte", "apportent", "existe", "existent", "reste", "restent",
)


def nier_l_affirmation(source, affirmation):
    """
    Nie mecaniquement la premiere proposition de l'affirmation.
    / Mechanically negates the claim's first proposition.

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    POURQUOI CETTE TRANSFORMATION-LA, ET PAS UNE AUTRE. Le probleme
    central de ce banc est que ses deux references sont lexicalement
    saturees : un simple recouvrement de mots les predit a 0,889 et
    0,981. Une AUC elevee y est donc compatible avec un juge qui ne fait
    que compter du vocabulaire commun.

    La negation coupe ce noeud, et elle le coupe PROPREMENT :

    - elle **n'enleve aucun mot** de l'affirmation ;
    - elle n'ajoute que « ne » / « n' » et « pas », tous deux de moins de
      quatre caracteres, donc **ignores par `score_lexical`** ;
    - la verite, elle, **bascule** : une source qui etablissait
      l'affirmation ne peut pas etablir sa negation.

    **Consequence, et c'est tout l'interet : le recouvrement de mots rend
    exactement le MEME score avant et apres, donc une AUC de 0,500 par
    construction.** Tout juge qui depasse 0,5 sur ce jeu detecte quelque
    chose qu'un compteur de mots ne peut pas voir. C'est la seule mesure
    de ce dossier qui puisse le prouver.
    / Word overlap scores identically before and after, so its AUC is
    0.500 by construction. Anything above that is real detection.

    ON NIE LA PHRASE QUE LA SOURCE ETABLIT, PAS UNE PHRASE AU HASARD.
    C'est ce qui rend l'etiquette « fausse » vraiment fausse. Une
    affirmation porte jusqu'a sept assertions et la source n'en etablit
    qu'une part : nier une phrase SANS RAPPORT avec la source laisserait
    la paire soutenue au sens large — « la source etablit au moins une
    des choses avancees » reste vrai — et l'etiquette mentirait.

    On choisit donc la phrase dont le vocabulaire recoupe le plus celui
    de la source, et on nie DEDANS. C'est deterministe, et ca vise ce
    que la source revendique.
    / Negate the sentence the source actually establishes, else the
    "false" label would be wrong under the lenient reading.

    :param source: sert a choisir QUELLE phrase nier
    :return: l'affirmation niee, ou None si aucune regle ne s'applique
    """
    def mots_de(texte):
        return {
            mot for mot in re.findall(r"\w+", texte.lower())
            if len(mot) > 3
        }

    mots_de_la_source = mots_de(source)
    bornes = phrases_de(affirmation)

    # Les phrases, de la plus proche de la source a la plus lointaine.
    # / Sentences, closest to the source first.
    def proximite(borne):
        debut, fin = borne
        mots = mots_de(affirmation[debut:fin])
        if not mots:
            return 0.0
        return len(mots & mots_de_la_source) / len(mots)

    for debut, fin in sorted(bornes, key=proximite, reverse=True):
        phrase = affirmation[debut:fin]
        # Le verbe le plus PRECOCE de la phrase, pas le premier de la
        # liste : nier le verbe principal plutot qu'une subordonnee.
        # / The earliest verb in the sentence, not the first in the list.
        rencontres = [
            rencontre
            for verbe in VERBES_NIABLES
            for rencontre in [re.search(rf"\b{re.escape(verbe)}\b", phrase)]
            if rencontre
        ]
        if not rencontres:
            continue
        rencontre = min(rencontres, key=lambda trouve: trouve.start())
        verbe = rencontre.group(0)
        # L'ELISION : « ne est » est faux, « n'est » est juste.
        # / Elision before a vowel.
        prefixe = "n'" if verbe[0] in "aeiouyéèêà" else "ne "
        phrase_niee = (
            phrase[:rencontre.start()]
            + f"{prefixe}{verbe} pas"
            + phrase[rencontre.end():]
        )
        return affirmation[:debut] + phrase_niee + affirmation[fin:]
    return None


def paires_adverses():
    """
    Le jeu ADVERSE : chaque paire positive, et sa negation.
    / The ADVERSARIAL set: each positive pair, and its negation.

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    Construit depuis l'etalon gele — donc depuis de VRAIS paragraphes de
    synthese et de VRAIES sources de debat, jamais depuis du texte
    invente. Seules les paires que la reference declare « soutient »
    servent de base : nier une paire deja negative ne donnerait pas une
    verite connue.

    Ce jeu est **equilibre par construction** (autant de positives que de
    negatives), ce qui le distingue de l'etalon et de ses 118 contre 27 :
    l'accord y redevient lisible, et le « meilleur seuil » cesse d'etre
    un artefact.
    / Balanced by construction, unlike the 118/27 etalon.
    """
    adverses = []
    for paire in paires_de_l_etalon():
        if not paire["verite"]:
            continue
        niee = nier_l_affirmation(paire["source"], paire["affirmation"])
        if niee is None:
            continue
        # LES DEUX VERSIONS PARTAGENT LEUR GROUPE, et c'est ce qui rend
        # l'AUC stratifiee lisible ici : elle devient une comparaison
        # APPARIEE — « pour cette paire-ci, le juge note-t-il la version
        # vraie au-dessus de sa negation ? ». Sans cle explicite, le
        # regroupement se ferait sur le texte de l'affirmation, qui
        # DIFFERE entre les deux, et chaque groupe n'aurait qu'une seule
        # classe : l'AUC stratifiee serait indefinie.
        # / Both versions share a group key, making the stratified AUC a
        # paired comparison. Grouping on the claim text would break it.
        groupe = f"{paire['numero']}"
        adverses.append(dict(paire, verite=True, groupe=groupe))
        adverses.append(
            dict(paire, affirmation=niee, verite=False, groupe=groupe),
        )
    return adverses


def score_lexical(source, affirmation):
    """
    LA BASELINE QUI DOIT FIGURER DANS CHAQUE TABLEAU : la part des mots
    de la source qu'on retrouve dans l'affirmation.
    / The baseline that must appear in every table: word overlap.

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    POURQUOI CE COMPTEUR DE MOTS EST LE SEUL COMPARATEUR HONNETE.
    Mesure du 19 aout 2026, relecture adverse : ce recouvrement obtient
    une AUC de **0,889** sur les 145 paires gelees et de **0,981** sur
    les 15 relues a la main — au-dessus de ShieldStral (0,734 et 0,923)
    et au-dessus de tous les encodeurs mesures ce jour-la.

    Ce n'est pas un artefact : le paragraphe de synthese a ete ECRIT A
    PARTIR des sources qui le soutiennent, il en reprend le vocabulaire.
    Les deux references sont donc lexicalement SATUREES.

    La consequence commande la lecture de tout ce banc : **une AUC ne se
    lit pas par rapport a 0,5, ni par rapport a ShieldStral, mais par
    rapport a cette ligne.** Un juge qui ne la depasse pas n'a pas
    demontre qu'il verifie quoi que ce soit — il peut n'avoir compte que
    des mots. Aucun candidat mesure le 19 aout ne la depasse.
    / An AUC here must be read against this line, not against 0.5.

    Il est deterministe et gratuit, ce qui prive au passage le
    determinisme des encodeurs de toute valeur d'argument : ce compteur
    est lui aussi reproductible a 100 %, et il score plus haut.
    / It is deterministic too — which is why determinism alone proves
    nothing about quality.

    :return: la part des mots de plus de 3 caracteres de la source
        presents dans l'affirmation, entre 0 et 1
    """
    def mots_de(texte):
        return {
            mot for mot in re.findall(r"\w+", texte.lower())
            if len(mot) > 3
        }

    mots_de_la_source = mots_de(source)
    if not mots_de_la_source:
        return 0.0
    mots_de_l_affirmation = mots_de(affirmation)
    retrouves = mots_de_la_source & mots_de_l_affirmation
    return len(retrouves) / len(mots_de_la_source)


def auc_stratifiee(scores, verites, groupes):
    """
    L'AUC calculee A AFFIRMATION CONSTANTE. / AUC computed within claims.

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    POURQUOI L'AUC GLOBALE NE SUFFIT PAS ICI. Les 145 paires ne portent
    que sur **23 affirmations** : chaque paragraphe est confronte a 2 a
    15 sources. Sur les 3 186 couples de l'AUC globale, **128
    seulement — 4 %** — opposent deux sources d'un MEME paragraphe. Les
    96 % restants comparent une source du paragraphe A a une source du
    paragraphe B : une question que personne ne pose, et dans laquelle
    tout ce qui distingue les paragraphes entre eux entre sans avoir
    rien a voir avec le jugement.

    A affirmation constante, ces differences disparaissent. Ce que
    mesure alors l'AUC est exactement la question utile : POUR CE
    PARAGRAPHE, le juge classe-t-il la source qui l'etablit au-dessus de
    celle qui ne l'etablit pas ?
    / Only 4 % of the global AUC's couples are within-claim.

    UN SOUPCON QUE LA MESURE A RETOURNE. On pouvait craindre que
    l'agregation `meilleure_phrase` — un MAXIMUM sur N phrases, qui
    croit avec N — ne fabrique de l'AUC en ne mesurant que la longueur
    des paragraphes. **Mesure du 19 aout : l'AUC du seul nombre de
    phrases vaut 0,426**, les negatives ayant en moyenne PLUS de phrases
    que les positives (4,89 contre 4,37). Le biais deflate donc
    legerement l'AUC globale, il ne la gonfle pas. La stratification
    reste la bonne mesure — mais pour la raison ci-dessus, pas pour
    celle-la.
    / Feared bias measured at 0.426: it deflates, it does not inflate.

    :param groupes: la cle de regroupement de chaque paire, ici l'affirmation
    :return: (AUC ponderee par les couples, AUC MACRO — moyenne des AUC
        par groupe, a poids egaux —, nombre de couples, nombre de
        groupes, la plus petite et la plus grande AUC de groupe)
    """
    par_groupe = {}
    for score, verite, groupe in zip(scores, verites, groupes):
        if score is None:
            continue
        par_groupe.setdefault(groupe, []).append((score, verite))

    concordantes, couples = 0.0, 0
    aucs_de_groupe = []
    for paires_du_groupe in par_groupe.values():
        positifs = [s for s, v in paires_du_groupe if v]
        negatifs = [s for s, v in paires_du_groupe if not v]
        if not positifs or not negatifs:
            continue
        concordantes_du_groupe, couples_du_groupe = 0.0, 0
        for score_positif in positifs:
            for score_negatif in negatifs:
                couples_du_groupe += 1
                if score_positif > score_negatif:
                    concordantes_du_groupe += 1.0
                elif score_positif == score_negatif:
                    concordantes_du_groupe += 0.5
        aucs_de_groupe.append(concordantes_du_groupe / couples_du_groupe)
        concordantes += concordantes_du_groupe
        couples += couples_du_groupe

    if not couples:
        return None, None, 0, 0, None, None

    # LA PONDEREE ET LA MACRO NE DISENT PAS LA MEME CHOSE, ET L'ECART
    # ENTRE ELLES EST UNE INFORMATION. Un seul paragraphe porte 56 des
    # 128 couples — 44 % : la ponderee est donc a moitie decidee par lui.
    # La macro donne le meme poids aux 11 paragraphes, et l'etendue dit
    # a quel point ils se contredisent.
    # / One paragraph carries 44 % of the couples; the macro re-balances.
    macro = sum(aucs_de_groupe) / len(aucs_de_groupe)
    return (concordantes / couples, macro, couples, len(aucs_de_groupe),
            min(aucs_de_groupe), max(aucs_de_groupe))


def comparer_deux_passes(premiere, seconde):
    """
    Le PLANCHER DE BRUIT : deux passes du meme modele, comparees.
    / The NOISE FLOOR: two runs of the same model, compared.

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    POURQUOI CE CHIFFRE PASSE AVANT TOUS LES AUTRES. Le juge de
    reference des 145 paires gelees ne retrouve que 77 % de ses propres
    verdicts a temperature 0. Tant qu'on ignore ce que vaut le candidat
    sur ce terrain-la, son taux d'accord ne veut rien dire.

    Un encodeur DEVRAIT etre parfaitement deterministe : pas
    d'echantillonnage, pas de jeton imprevisible, une seule passe avant.
    « Devrait » n'est pas « est » : c'est ce que cette fonction verifie.
    / Encoders *should* be deterministic. Should is not is.
    """
    identiques, total, ecart_maximal = 0, 0, 0.0
    for cle, scores_a in premiere.items():
        for score_a, score_b in zip(scores_a, seconde.get(cle, [])):
            if score_a is None or score_b is None:
                continue
            total += 1
            ecart = abs(score_a - score_b)
            ecart_maximal = max(ecart_maximal, ecart)
            if score_a == score_b:
                identiques += 1
    return identiques, total, ecart_maximal


def nom_du_jeu(options):
    """Le nom du jeu de paires choisi. / The chosen pair set's name."""
    if options.adverse:
        return "adverse-negations"
    return "etalon-gele-145" if options.etalon else "relues-a-la-main-15"


def empreinte_du_jeu(paires, nom_du_jeu):
    """
    L'identite du jeu de paires, a ecrire DANS le JSON de sortie.
    / The pair set's identity, written INTO the output JSON.

    LOCALISATION : benchmarks/juge_de_verification/comparer_un_encodeur.py

    UN ARTEFACT QUI A PERDU SA QUESTION NE VAUT RIEN, et ce depot en a
    deja fait les frais : `shieldstral.json` etait la sortie du cadrage
    declare FAUTIF, sans que le fichier le dise — qui l'aurait relu
    aurait conclu l'inverse du rapport.

    Ici le risque est plus sournois encore : `zip` tronque en silence.
    Relire 145 scores contre les 15 verites des paires relues a la main
    ne leve aucune erreur — cela rend des nombres plausibles, calcules
    sur les 15 premieres paires. L'empreinte permet de le refuser.
    / zip truncates silently; the fingerprint lets us refuse.
    """
    import hashlib

    empreinte = hashlib.md5()
    for paire in paires:
        empreinte.update(paire["affirmation"].encode("utf-8"))
        empreinte.update(paire["source"].encode("utf-8"))
    return {
        "jeu": nom_du_jeu,
        "nombre_de_paires": len(paires),
        "md5_des_textes": empreinte.hexdigest(),
        "positives": sum(1 for paire in paires if paire["verite"]),
    }


def main():
    analyseur = argparse.ArgumentParser(
        description="Comparer un encodeur de vérification de sourçage.",
    )
    analyseur.add_argument(
        "candidat", nargs="?", choices=sorted(CANDIDATS),
        help="le candidat à mesurer",
    )
    analyseur.add_argument(
        "--tous", action="store_true", help="tous les candidats, à la suite",
    )
    analyseur.add_argument(
        "--etalon", action="store_true",
        help="les 145 paires gelées au lieu des 15 relues à la main",
    )
    analyseur.add_argument(
        "--adverse", action="store_true",
        help="le jeu adverse : chaque paire positive et sa NÉGATION",
    )
    analyseur.add_argument(
        "--plancher", action="store_true",
        help="deux passes comparées entre elles, avant tout accord",
    )
    analyseur.add_argument(
        "--cadrage", default=None, help="n'en jouer qu'un seul",
    )
    analyseur.add_argument(
        "--sortie", default=None, help="le fichier JSON des scores",
    )
    analyseur.add_argument(
        "--depuis", default=None,
        help="relire un JSON déjà mesuré, sans charger aucun modèle",
    )
    options = analyseur.parse_args()

    if not options.candidat and not options.tous and not options.depuis:
        analyseur.error("nommez un candidat, ou passez --tous, ou --depuis.")

    a_mesurer = sorted(CANDIDATS) if options.tous else [options.candidat]
    if options.adverse:
        paires = paires_adverses()
    elif options.etalon:
        paires = paires_de_l_etalon()
    else:
        paires = paires_relues_a_la_main()
    verites = [paire["verite"] for paire in paires]

    if options.depuis:
        # RELIRE SANS REMESURER. Les scores d'un encodeur sont
        # deterministes : les recalculer donnerait exactement les memes
        # nombres, pour des heures de processeur. Cette porte sert a
        # ajouter une METRIQUE a une campagne deja faite, pas a en
        # refaire une.
        # / Encoder scores are deterministic; re-running would cost hours
        # for identical numbers. This adds a metric to a past campaign.
        with open(options.depuis, encoding="utf-8") as fichier:
            deja_mesure = json.load(fichier)

        attendu = empreinte_du_jeu(paires, nom_du_jeu(options))
        trouve = deja_mesure.pop("_jeu", None)
        if trouve is None:
            print(
                f"\n  ⚠ {options.depuis} ne porte pas d'empreinte de jeu : "
                f"il est ANTÉRIEUR à ce contrôle.\n"
                f"    Vérifiez vous-même qu'il a bien été produit sur "
                f"« {attendu['jeu']} » — rien ici ne peut le garantir.",
            )
        elif trouve != attendu:
            raise SystemExit(
                f"\n  REFUS : ce fichier a été mesuré sur "
                f"« {trouve.get('jeu')} » ({trouve.get('nombre_de_paires')} "
                f"paires),\n  et vous le relisez contre "
                f"« {attendu['jeu']} » ({attendu['nombre_de_paires']} "
                f"paires).\n  Les deux séries seraient appariées par `zip`, "
                f"qui tronque SANS ERREUR.\n  Ajoutez ou retirez --etalon.",
            )
        print(f"\n  Relecture de {options.depuis} — aucun modèle chargé.")
        for nom, resultats in deja_mesure.items():
            print("\n" + "=" * 72)
            print(nom)
            afficher(nom, resultats, paires, None, 0)
        return

    print(f"\n{len(paires)} paires — {nom_du_jeu(options)}")
    print(f"  positives : {sum(verites)} · négatives : "
          f"{len(verites) - sum(verites)}")
    print(f"  threads   : {nombre_de_threads()}")
    print("\n  Aucun appel réseau une fois les poids en cache, aucune "
          "écriture en base, aucune facturation.")
    if options.etalon:
        # L'ETALON EST DESEQUILIBRE, ET L'ACCORD Y EST TROMPEUR : 118
        # « soutient » pour 27 « ne_soutient_pas ». Accepter tout donne
        # deja 118/145. Seule l'AUC se lit sur ce jeu.
        # / The etalon is imbalanced; only the AUC is readable there.
        print("  ⚠ 118 positives pour 27 négatives : accepter TOUT donne "
              "déjà 118/145.\n    Sur ce jeu, seule l'AUC se lit — le "
              "« meilleur seuil » est un artefact de métrique.")

    tout = {}
    for nom in a_mesurer:
        candidat = CANDIDATS[nom]
        cadrages = [options.cadrage] if options.cadrage else (
            CADRAGES_SPANS if candidat["famille"] == "spans" else CADRAGES_NLI
        )
        print("\n" + "=" * 72)
        print(f"{nom}  ({candidat['famille']})")
        try:
            resultats, duree, passes = mesurer(
                nom, candidat, paires, cadrages, AGREGATIONS_SPANS,
            )
        except Exception as erreur:
            print(f"  ÉCHEC : {type(erreur).__name__} : "
                  f"{str(erreur)[:300]}", flush=True)
            continue

        afficher(nom, resultats, paires, duree, passes)
        tout[nom] = resultats

        if options.plancher:
            print("\n  Plancher de bruit — seconde passe…", flush=True)
            seconde, duree_b, _passes_b = mesurer(
                nom, candidat, paires, cadrages, AGREGATIONS_SPANS,
            )
            identiques, total, ecart = comparer_deux_passes(
                resultats, seconde,
            )
            part = 100 * identiques / total if total else 0
            print(f"  reproductibilité : {identiques}/{total} scores "
                  f"identiques au bit près ({part:.1f} %) — "
                  f"écart maximal {ecart:.2e}")
            tout[f"{nom}|seconde_passe"] = seconde

    if options.sortie:
        tout["_jeu"] = empreinte_du_jeu(paires, nom_du_jeu(options))
        with open(options.sortie, "w", encoding="utf-8") as fichier:
            json.dump(tout, fichier, ensure_ascii=False, indent=2)
        print(f"\nDétail dans {options.sortie}")
    else:
        # PAS DE NOM DE FICHIER PAR DEFAUT, ET C'EST DELIBERE. Un banc
        # voisin ecrivait `resultats.json` sans qu'on le lui demande, et
        # ce fichier etait l'ENTREE d'une autre mesure : le relancer
        # detruisait la mesure precedente. Ici, rien ne s'ecrit sans
        # `--sortie`.
        # / No default output path: a neighbouring bench overwrote another
        # measure's input by having one.
        print("\n  (aucun fichier écrit — passez --sortie pour le détail)")


if __name__ == "__main__":
    main()
