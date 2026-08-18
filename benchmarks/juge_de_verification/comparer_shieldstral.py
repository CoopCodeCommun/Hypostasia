"""
Banc d'essai MANUEL : Shieldstral comme juge d'implication.
/ MANUAL benchmark: Shieldstral as an entailment judge.

LOCALISATION : benchmarks/juge_de_verification/comparer_shieldstral.py

POURQUOI CE MODELE-LA, ET PAS UN AUTRE MODELE DE MODERATION.

Un modele de moderation ordinaire classe un texte dans des categories
FIGEES — haine, violence, contenu sexuel. On ne peut pas lui poser notre
question. `mistral-moderation-2603`, dans le catalogue de l'API, est de
ce type : l'employer ici serait un contresens.

Shieldstral est autre chose. L'operateur y ecrit LUI-MEME sa question
binaire, et le modele rend UN SEUL token, `yes` ou `no`. Deux proprietes
en decoulent, et ce sont elles qui interessent ce projet :

1. **Il rend un SCORE, pas un verdict.** En demandant les logprobs du
   premier token et en renormalisant `yes` contre `no`, on obtient une
   probabilite continue. Le SEUIL cesse alors d'etre cache dans une
   tournure de prompt : il devient un nombre qu'on pose, qu'on affiche,
   et qu'on peut changer sans rien rejuger.
2. **Sa consigne prevoit explicitement un NIVEAU DE SEVERITE** (« strict
   / moderate / lenient », dit sa fiche). C'est exactement la variable
   dont tout ce banc a montre qu'elle manquait.

Poids Apache 2.0, 3,8 milliards de parametres, ~7,7 Go en bf16 : il
tourne sur processeur, sans clef d'API et sans que rien ne sorte de la
machine. Pour un outil de deliberation qui traite des verbatims
d'assemblee, ce dernier point n'est pas un detail.

CE SCRIPT N'ECRIT RIEN EN BASE et n'appelle aucune API.

    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_de_verification/comparer_shieldstral.py
"""

import json
import os
import sys

MODELE = "mistralai/Shieldstral-1.0-3B"

# La consigne systeme est FIXE : elle vient de la fiche du modele.
# / The system prompt is fixed; it comes from the model card.
CONSIGNE_SYSTEME = (
    "Judge whether the Document meets the requirements based on the Query "
    'and the Instruction provided. Note that the answer can only be "yes" '
    'or "no".'
)

# Les deux severites comparees, ecrites dans le <Instruct> comme la fiche
# du modele le prevoit. C'est la meme experience que
# `comparer_les_seuils.py`, mais sur un modele qui rend un score.
# / The two strictness levels, written where the model card says to.
SEVERITES = {
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

QUESTION = (
    "La SOURCE établit-elle ce que l'AFFIRMATION avance, au sens de "
    "l'instruction ci-dessus ?"
)

MES_VERDICTS = {
    1: True, 2: True, 3: True, 4: True, 5: True, 6: True, 7: True, 8: True,
    9: True, 10: True, 11: True, 12: True, 13: False, 14: False, 15: True,
}

MOTS_OUI = {"yes", "yes.", '"yes"', "'yes'", "oui"}
MOTS_NON = {"no", "no.", '"no"', "'no'", "non"}


def charger():
    """Charge le modele sur processeur, en bf16. / Loads on CPU, bf16."""
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    print(f"Chargement de {MODELE} (~7,7 Go au premier passage)…",
          flush=True)
    tokeniseur = AutoProcessor.from_pretrained(MODELE)
    modele = AutoModelForImageTextToText.from_pretrained(
        MODELE, dtype=torch.bfloat16, low_cpu_mem_usage=True,
    )
    modele.eval()
    return tokeniseur, modele


def score_de_soutien(tokeniseur, modele, instruction, affirmation, source):
    """
    La probabilite renormalisee de « oui » sur le PREMIER token.
    / The renormalised probability of "yes" on the FIRST token.
    """
    import torch

    message_utilisateur = (
        f"<Instruct>: {instruction}\n"
        f"<Query>: {QUESTION}\n"
        f"<Document>: AFFIRMATION : {affirmation}\n\n"
        f"SOURCE : {source}"
    )
    entrees = tokeniseur.apply_chat_template(
        [
            {"role": "system", "content": CONSIGNE_SYSTEME},
            {"role": "user", "content": message_utilisateur},
        ],
        add_generation_prompt=True, return_tensors="pt", return_dict=True, tokenize=True,
    )
    with torch.no_grad():
        logits = modele(**entrees).logits[0, -1].float()

    # On ne renormalise QUE sur oui/non : le modele n'a le droit de dire
    # que ca, et un troisieme token serait du bruit.
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
        return None
    paire = torch.tensor([logit_oui, logit_non])
    return torch.softmax(paire, dim=0)[0].item()


def main():
    chemin = os.path.join(
        os.path.dirname(__file__), "..", "chaine_complete", "resultats.json",
    )
    with open(chemin, encoding="utf-8") as fichier:
        mesures = json.load(fichier)
    affirmation = mesures["affirmation_jugee"]

    tokeniseur, modele = charger()
    print(f"\n{len(affirmation['paires'])} paires × {len(SEVERITES)} "
          f"sévérités. Aucun appel réseau, aucune écriture.\n")

    resultats = {}
    entete = "paire   " + "".join(f"{nom:>12}" for nom in SEVERITES) + "   moi"
    print(entete)
    for numero, paire in enumerate(affirmation["paires"], start=1):
        ligne = f"  {numero:2}   "
        for nom_de_severite, instruction in SEVERITES.items():
            score = score_de_soutien(
                tokeniseur, modele, instruction,
                affirmation["texte"], paire["source"],
            )
            resultats[(numero, nom_de_severite)] = score
            ligne += f"{score:>11.2f} " if score is not None else "          ? "
        ligne += f"   {'oui' if MES_VERDICTS[numero] else 'non'}"
        print(ligne, flush=True)

    print("\nScore = probabilité de « oui ». Verdict au seuil de 0,5 :")
    for nom_de_severite in SEVERITES:
        scores = [
            resultats[(n, nom_de_severite)] for n in range(1, 16)
            if resultats.get((n, nom_de_severite)) is not None
        ]
        if not scores:
            continue
        oui = sum(1 for s in scores if s >= 0.5)
        accord = sum(
            1 for n in range(1, 16)
            if resultats.get((n, nom_de_severite)) is not None
            and (resultats[(n, nom_de_severite)] >= 0.5) == MES_VERDICTS[n]
        )
        print(f"  {nom_de_severite:8} : {oui:2}/15 « soutient », "
              f"accord avec mes verdicts {accord}/15")

    chemin_sortie = os.path.join(
        os.path.dirname(__file__), "shieldstral.json",
    )
    with open(chemin_sortie, "w", encoding="utf-8") as fichier:
        json.dump(
            {f"{n}|{s}": v for (n, s), v in resultats.items()},
            fichier, ensure_ascii=False, indent=2,
        )
    print(f"\nDétail dans {chemin_sortie}")


if __name__ == "__main__":
    main()
