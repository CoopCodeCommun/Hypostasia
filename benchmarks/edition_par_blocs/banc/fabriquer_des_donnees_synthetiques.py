"""
Fabrique un jeu de blocs SYNTHETIQUE de la meme forme que le corpus reel.
/ Builds a SYNTHETIC block set shaped like the real corpus.

LOCALISATION : benchmarks/edition_par_blocs/banc/

POURQUOI CE FICHIER EXISTE

Le prototype a ete mesure sur la vraie base : page 19 (210 blocs, 58 770
caracteres) et page 3 (la transcription, 12 blocs). Mais la page 19 est un
article qui appartient a un tiers : verser son texte dans le depot le
poserait dans l'historique git pour toujours.

Ce script rend donc un jeu de MEME FORME — meme nombre de blocs, meme
repartition de labels, meme total de caracteres a peu pres, memes 8 blocs a
saut de ligne interne, memes 5 locuteurs — avec du texte fabrique. Le
prototype s'ouvre ainsi au navigateur sans rien extraire, et les mesures de
FLUIDITE restent comparables.

Ce qu'il ne remplace PAS : les mesures qui dependent du CONTENU reel — le
diff sur vingt gestes, et surtout la mesure des ancres, qui a besoin des
vraies portions en base. Pour celles-la, re-extraire avec
`extraire_les_donnees_reelles.py`.

Usage : python fabriquer_des_donnees_synthetiques.py > donnees.json
"""
import json
import random
import uuid

# La forme mesuree du corpus reel, le 23 aout 2026.
# / The real corpus shape, measured 23 Aug 2026.
FORME_DE_LA_PAGE_19 = {
    "text": 116,
    "section_header": 43,
    "list_item": 41,
    "table": 8,
    "caption": 2,
}
CARACTERES_VISES = 58770
# Dans le corpus reel, les SEULS blocs a saut de ligne interne sont les 8
# `table` — leur texte est du markdown « pipe ». Aucun bloc de prose n'en
# porte. Verifie le 23 aout 2026 sur la page 19.
# / In the real corpus, only the 8 tables carry an internal newline.
BLOCS_A_SAUT_DE_LIGNE = 0
LOCUTEURS = ["Elinor", "Eric", "Laurent", "speaker_1", "speaker_2"]

MOTS = (
    "deliberation source ancrage passage extraction hypostase carnet note "
    "bloc frontiere gouttiere selection correction transcription locuteur "
    "verification citation synthese wiki preuve offset empreinte element "
    "portion ingestion analyse moteur structure lecture ecriture verrou "
    "consensus argument principe definition invariant evenement conjecture"
).split()


def phrase(alea, mots_voulus):
    mots = [alea.choice(MOTS) for _ in range(mots_voulus)]
    return mots[0].capitalize() + " " + " ".join(mots[1:]) + "."


def texte_de(alea, longueur_visee):
    morceaux = []
    total = 0
    while total < longueur_visee:
        p = phrase(alea, alea.randint(6, 18))
        morceaux.append(p)
        total += len(p) + 1
    return " ".join(morceaux)[:longueur_visee]


def tableau_markdown(alea):
    lignes = ["| Colonne A | Colonne B |", "| --- | --- |"]
    for _ in range(alea.randint(2, 4)):
        lignes.append(f"| {alea.choice(MOTS)} | {alea.choice(MOTS)} |")
    # Deux tableaux du corpus reel portent une LIGNE VIDE interne.
    # / Two real tables carry an internal blank line.
    if alea.random() < 0.25:
        lignes.insert(2, "|  |  |")
    return "\n".join(lignes)


def fabriquer():
    alea = random.Random(19)  # graine fixe : le jeu est reproductible
    labels = []
    for label, nombre in FORME_DE_LA_PAGE_19.items():
        labels.extend([label] * nombre)
    alea.shuffle(labels)

    # Une longueur par bloc, dont la somme approche le total reel.
    longueur_moyenne = CARACTERES_VISES // len(labels)
    blocs = []
    for ordre, label in enumerate(labels):
        if label == "section_header":
            longueur = alea.randint(18, 60)
        elif label == "caption":
            longueur = alea.randint(40, 110)
        elif label == "list_item":
            longueur = alea.randint(60, 220)
        else:
            longueur = alea.randint(longueur_moyenne, longueur_moyenne * 2)
        if label == "table":
            corps = tableau_markdown(alea)
        else:
            corps = texte_de(alea, longueur)
        blocs.append({
            "identifiant_stable": str(uuid.UUID(int=alea.getrandbits(128), version=4)),
            "ordre": ordre,
            "label": label,
            "texte": corps,
            "masque": False,
            "provenance": {"page_no": 1 + ordre // 8, "boites": []},
        })

    # On n'injecte AUCUN saut de ligne dans la prose : dans le corpus reel
    # les seuls blocs qui en portent sont les tableaux, et ils en ont deja
    # par leur markdown.
    # / No newline is injected into prose: only tables carry them.
    if BLOCS_A_SAUT_DE_LIGNE:
        indices = alea.sample(
            [i for i, b in enumerate(blocs) if b["label"] == "text"],
            BLOCS_A_SAUT_DE_LIGNE,
        )
        for i in indices:
            t = blocs[i]["texte"]
            milieu = len(t) // 2
            blocs[i]["texte"] = t[:milieu] + "\n" + t[milieu:]

    # La transcription : 12 tours, 5 locuteurs, des bornes de temps.
    # / The transcription: 12 turns, 5 speakers, time bounds.
    transcription = []
    instant = 0.0
    for ordre in range(12):
        duree = alea.uniform(12.0, 40.0)
        transcription.append({
            "identifiant_stable": str(uuid.UUID(int=alea.getrandbits(128), version=4)),
            "ordre": ordre,
            "label": "text",
            "texte": texte_de(alea, alea.randint(200, 520)),
            "masque": False,
            "provenance": {
                "locuteur": LOCUTEURS[ordre % len(LOCUTEURS)],
                "debut": round(instant, 1),
                "fin": round(instant + duree, 1),
            },
        })
        instant += duree

    return {"19": blocs, "3": transcription}


if __name__ == "__main__":
    jeu = fabriquer()
    print(json.dumps(jeu, ensure_ascii=False))
