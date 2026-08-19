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

1. **Il rend un SCORE, pas un verdict.** En demandant les logits du
   premier token et en renormalisant `yes` contre `no`, on obtient une
   probabilite continue. Le SEUIL cesse alors d'etre cache dans une
   tournure de prompt : il devient un nombre qu'on pose, qu'on affiche,
   et qu'on peut changer sans rien rejuger. C'est la voie que les deux
   API refusent — « Logprobs are not enabled for this model » chez
   Mistral, 403 chez OpenAI sur les modeles de raisonnement.
2. **Sa consigne prevoit explicitement un NIVEAU DE SEVERITE** (« strict
   / moderate / lenient », dit sa fiche). C'est exactement la variable
   dont tout ce banc a montre qu'elle manquait.

Poids Apache 2.0, 3,8 milliards de parametres, ~7,7 Go en bf16 : il
tourne sur processeur, sans clef d'API et sans que rien ne sorte de la
machine. Pour un outil de deliberation qui traite des verbatims
d'assemblee, ce dernier point n'est pas un detail.

## LE CADRAGE FAIT TOUT, ET C'EST LA LECON DE CE BANC

Ce script compare DEUX facons de poser la meme question. Ce n'est pas de
la coquetterie : le premier essai de ce banc rendait un resultat si
mauvais qu'une conclusion negative avait ete ecrite — et elle etait
fausse. Le modele n'y etait pour rien.

| cadrage | ce qu'on met ou |
|---|---|
| `ENSEMBLE` | l'affirmation ET la source, toutes deux dans `<Document>` |
| `SEPARE`   | `<Query>` porte l'affirmation, `<Document>` porte la source seule |

La fiche du modele decrit un triplet `<Instruct>` / `<Query>` /
`<Document>` : la question va dans `Query`, le texte a evaluer va dans
`Document`. Le cadrage `ENSEMBLE` viole cette structure — il donne au
modele deux textes la ou il en attend un, et lui demande de deviner
lequel juger. Le cadrage `SEPARE` la respecte.

**Les deux sont laisses dans ce fichier exprès.** Retirer le mauvais
laisserait le bon sans point de comparaison, et la prochaine personne
qui doute referait l'erreur. C'est la mesure qui tranche, pas la
docstring.

## CE QUE CE SCRIPT NE FAIT PAS

Il n'ecrit RIEN en base, n'appelle AUCUNE API, et ne sort pas de la
machine. Le modele est charge depuis le cache local de HuggingFace.

    # les 15 paires relues a la main, les deux cadrages, les deux severites
    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_de_verification/comparer_shieldstral.py

    # l'ETALON GELE des 145 paires, cadrage separe, severite large
    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_de_verification/comparer_shieldstral.py --etalon
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."),
))

# LE CADRAGE, LES SEVERITES ET LA CONSIGNE VIENNENT DE LA PRODUCTION,
# SANS COPIE. `core/services/juge_local.py` est le juge reellement
# branche ; deux copies du cadrage poseraient deux questions
# differentes, et ce banc ne mesurerait plus ce que la production fait.
# C'est la meme regle que pour `comparer_un_juge.py`, qui importe le
# prompt du juge de production.
# / The framing comes from production, uncopied: two copies would ask
# two different questions and this bench would stop measuring the thing.
from core.services.juge_local import (  # noqa: E402
    CONSIGNE_SYSTEME, INSTRUCTIONS as SEVERITES, MODELE, MOTS_NON, MOTS_OUI,
    message_pour_le_juge,
)

# La question du cadrage ENSEMBLE. Elle ne sert QU'A lui : dans le
# cadrage SEPARE, c'est l'affirmation elle-meme qui occupe <Query>.
# / Only the ENSEMBLE framing needs a stand-in question in <Query>.
QUESTION_DU_CADRAGE_ENSEMBLE = (
    "La SOURCE établit-elle ce que l'AFFIRMATION avance, au sens de "
    "l'instruction ci-dessus ?"
)

CADRAGE_ENSEMBLE = "ensemble"
CADRAGE_SEPARE = "separe"

MES_VERDICTS = {
    1: True, 2: True, 3: True, 4: True, 5: True, 6: True, 7: True, 8: True,
    9: True, 10: True, 11: True, 12: True, 13: False, 14: False, 15: True,
}


def message_utilisateur(cadrage, instruction, affirmation, source):
    """
    Le message selon le cadrage. C'est LA variable de cette experience.
    / The user message, per framing. This is the experiment's variable.

    LOCALISATION : benchmarks/juge_de_verification/comparer_shieldstral.py

    Dans le cadrage SEPARE, `<Query>` porte l'AFFIRMATION et `<Document>`
    la SOURCE SEULE : c'est la structure que decrit la fiche du modele —
    on lui demande si le Document satisfait la Query. Dans le cadrage
    ENSEMBLE, les deux textes sont dans `<Document>` et `<Query>` ne
    porte qu'une question generique : le modele doit deviner lequel des
    deux textes il juge.
    / SEPARE follows the model card: Query holds the claim, Document holds
    the source. ENSEMBLE crams both into Document.
    """
    if cadrage == CADRAGE_SEPARE:
        # Le cadrage de PRODUCTION, importe, jamais recopie.
        # / Production's framing, imported.
        severite = next(
            nom for nom, texte in SEVERITES.items() if texte == instruction
        )
        return message_pour_le_juge(affirmation, source, severite)
    return (
        f"<Instruct>: {instruction}\n"
        f"<Query>: {QUESTION_DU_CADRAGE_ENSEMBLE}\n"
        f"<Document>: AFFIRMATION : {affirmation}\n\n"
        f"SOURCE : {source}"
    )


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


def score_de_soutien(tokeniseur, modele, cadrage, instruction,
                     affirmation, source):
    """
    La probabilite renormalisee de « oui » sur le PREMIER token.
    / The renormalised probability of "yes" on the FIRST token.
    """
    import torch

    entrees = tokeniseur.apply_chat_template(
        [
            {"role": "system", "content": CONSIGNE_SYSTEME},
            {"role": "user", "content": message_utilisateur(
                cadrage, instruction, affirmation, source,
            )},
        ],
        add_generation_prompt=True, return_tensors="pt",
        return_dict=True, tokenize=True,
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


def aire_sous_la_courbe(scores, verites):
    """
    L'AUC, calculee par comptage de paires concordantes (Mann-Whitney).
    / AUC by concordant-pair counting.

    LOCALISATION : benchmarks/juge_de_verification/comparer_shieldstral.py

    POURQUOI L'AUC PLUTOT QU'UN TAUX D'ACCORD. Un taux d'accord depend du
    seuil qu'on a choisi, et ce banc existe justement parce que le seuil
    etait le probleme. L'AUC ne depend d'AUCUN seuil : elle dit la
    probabilite qu'une paire vraie recoive un score plus haut qu'une
    paire fausse. 0,5 = le hasard. 1,0 = toutes les vraies au-dessus de
    toutes les fausses.
    / AUC is threshold-free; the whole point of this bench is that the
    threshold was the problem.

    :return: l'AUC, ou None si une des deux classes est vide
    """
    positifs = [s for s, v in zip(scores, verites) if v]
    negatifs = [s for s, v in zip(scores, verites) if not v]
    if not positifs or not negatifs:
        return None
    concordantes = 0.0
    for score_positif in positifs:
        for score_negatif in negatifs:
            if score_positif > score_negatif:
                concordantes += 1.0
            elif score_positif == score_negatif:
                concordantes += 0.5
    return concordantes / (len(positifs) * len(negatifs))


def meilleur_seuil(scores, verites):
    """
    Le seuil qui maximise l'accord, et cet accord.
    / The accuracy-maximising threshold, and that accuracy.

    ATTENTION A LA LECTURE : ce seuil est choisi APRES COUP sur les
    memes points qu'il sert a evaluer. Il est donc SUR-AJUSTE, et ne dit
    pas ce que vaudrait ce seuil sur d'autres paires. C'est l'AUC qui se
    lit sans cette reserve.
    / Chosen post hoc on the same points: overfitted. Read the AUC.
    """
    couples = sorted(zip(scores, verites))
    candidats = [0.0] + [s for s, _ in couples] + [1.01]
    meilleur = (None, -1)
    for seuil in candidats:
        accord = sum(1 for s, v in zip(scores, verites) if (s >= seuil) == v)
        if accord > meilleur[1]:
            meilleur = (seuil, accord)
    return meilleur


def paires_relues_a_la_main():
    """Les 15 paires d'une meme affirmation, relues a la main."""
    chemin = os.path.join(
        os.path.dirname(__file__), "..", "chaine_complete", "resultats.json",
    )
    with open(chemin, encoding="utf-8") as fichier:
        mesures = json.load(fichier)
    affirmation = mesures["affirmation_jugee"]
    return [
        {
            "numero": numero,
            "affirmation": affirmation["texte"],
            "source": paire["source"],
            "verite": MES_VERDICTS[numero],
        }
        for numero, paire in enumerate(affirmation["paires"], start=1)
    ]


def paires_de_l_etalon():
    """
    Les 145 paires GELEES, avec le verdict du juge de reference.
    / The 145 FROZEN pairs, with the reference judge's verdict.

    CE QUE CETTE COMPARAISON MESURE, ET CE QU'ELLE NE MESURE PAS. La
    « verite » est ici le verdict de `gemini-2.5-flash`, dont la
    reproductibilite mesuree est de 77 % : ce n'est PAS la verite, c'est
    un second avis. Un desaccord n'est donc pas une erreur de
    Shieldstral — c'est un desaccord, et c'est deja une information.
    / The "truth" here is another judge's verdict, not truth.
    """
    chemin = os.path.join(os.path.dirname(__file__), "etalon-du-juge.json")
    with open(chemin, encoding="utf-8") as fichier:
        etalon = json.load(fichier)
    return [
        {
            "numero": numero,
            "affirmation": paire["affirmation"],
            "source": paire["texte_source"],
            "verite": paire["reponse_de_reference"] == "soutient",
        }
        for numero, paire in enumerate(etalon["paires"], start=1)
    ]


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument(
        "--etalon", action="store_true",
        help="les 145 paires gelées au lieu des 15 relues à la main",
    )
    analyseur.add_argument(
        "--cadrage", choices=[CADRAGE_ENSEMBLE, CADRAGE_SEPARE], default=None,
        help="n'en jouer qu'un seul (défaut : les deux)",
    )
    analyseur.add_argument(
        "--severite", choices=sorted(SEVERITES), default=None,
        help="n'en jouer qu'une seule (défaut : les deux)",
    )
    options = analyseur.parse_args()

    paires = paires_de_l_etalon() if options.etalon \
        else paires_relues_a_la_main()
    cadrages = [options.cadrage] if options.cadrage \
        else [CADRAGE_ENSEMBLE, CADRAGE_SEPARE]
    severites = [options.severite] if options.severite else list(SEVERITES)

    tokeniseur, modele = charger()
    print(
        f"\n{len(paires)} paires × {len(cadrages)} cadrage(s) × "
        f"{len(severites)} sévérité(s). "
        f"Aucun appel réseau, aucune écriture en base.\n",
        flush=True,
    )

    resultats = {}
    for cadrage in cadrages:
        for nom_de_severite in severites:
            scores, verites = [], []
            for paire in paires:
                score = score_de_soutien(
                    tokeniseur, modele, cadrage,
                    SEVERITES[nom_de_severite],
                    paire["affirmation"], paire["source"],
                )
                if score is None:
                    continue
                scores.append(score)
                verites.append(paire["verite"])
                resultats[f"{paire['numero']}|{cadrage}|{nom_de_severite}"] = \
                    score
            auc = aire_sous_la_courbe(scores, verites)
            seuil, accord = meilleur_seuil(scores, verites)
            accord_a_un_demi = sum(
                1 for s, v in zip(scores, verites) if (s >= 0.5) == v
            )
            print(
                f"  {cadrage:9} / {nom_de_severite:7} : "
                f"AUC {auc if auc is None else round(auc, 3)!s:>5} | "
                f"accord au seuil 0,5 : {accord_a_un_demi:3}/{len(scores)} | "
                f"meilleur seuil {seuil:.3f} → {accord:3}/{len(scores)}",
                flush=True,
            )

    nom_de_sortie = "shieldstral-etalon.json" if options.etalon \
        else "shieldstral.json"
    chemin_sortie = os.path.join(os.path.dirname(__file__), nom_de_sortie)
    with open(chemin_sortie, "w", encoding="utf-8") as fichier:
        json.dump(resultats, fichier, ensure_ascii=False, indent=2)
    print(f"\nDétail dans {chemin_sortie}")


if __name__ == "__main__":
    sys.exit(main())
