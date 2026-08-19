"""
Combien de threads donner au juge local ? La mesure, pas l'intuition.
/ How many threads for the local judge? Measured, not guessed.

LOCALISATION : benchmarks/juge_local/mesurer_les_threads.py

CE QU'IL MESURE. Le modele est charge UNE fois, puis les memes paires
sont chronometrees a 2, 3, 4, 6 et 8 threads. Ce qui decide n'est pas le
temps brut : c'est le RENDEMENT — combien on gagne en donnant un thread
de plus, et a partir d'ou on ne gagne plus rien.

MESURE DU 18 AOUT 2026, machine a 8 coeurs, 3 paires par reglage :

    threads   s/paire   acceleration   rendement/thread
          2      62,3          1,00x               1,00
          3      46,4          1,34x               0,90
          4      36,1          1,73x               0,86
          6      25,7          2,42x               0,81
          8      20,2          3,09x               0,77

ELLE A CORRIGE UNE INTUITION FAUSSE. On avait suppose qu'une inference
CPU passait mal a l'echelle et que « payer six threads pour 30 % de gain
coutait cher » : six threads rendent **2,42x**. Ce qui reste vrai, plus
faiblement, c'est la decroissance du gain MARGINAL — 15,9 s gagnees par
le 3e thread, 5,2 s par les 5e-6e, 2,75 s par les 7e-8e.

D'ou le defaut retenu : **6 threads**, « tout moins deux ».
`SHIELDSTRAL_THREADS` le change sans toucher au code.

MESURER LE VOISINAGE DE DOCLING. `nice` pondere le temps processeur,
PAS la bande passante memoire — et c'est la seule raison qui reste de
brider les threads. L'option `--threads N` fige un seul reglage : on
mesure alors A VIDE, puis PENDANT une conversion Docling, et on compare.

    # a vide, six threads
    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_local/mesurer_les_threads.py --threads 6

    # (autre terminal) une conversion Docling reelle, ~85 s
    make test-docling

    # pendant qu'elle tourne, relancer la meme mesure
    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_local/mesurer_les_threads.py --threads 6

L'ecart entre les deux est le cout reel du voisinage — celui que `nice`
ne peut pas effacer.

LE CADRAGE VIENT DE LA PRODUCTION, sans copie : ce banc mesure le cout
de la question REELLEMENT posee, pas d'une approximation.

CE SCRIPT N'ECRIT RIEN EN BASE et n'appelle aucune API. Il charge 7,7 Go
depuis le cache local de HuggingFace.

    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_local/mesurer_les_threads.py
"""

import argparse
import json
import os
import sys
import time

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RACINE)

from core.services.juge_local import (  # noqa: E402
    _charger_le_modele, noter_une_paire,
)

NOMBRE_DE_PAIRES = 3
THREADS_A_ESSAYER = [2, 3, 4, 6, 8]

CHEMIN_DE_L_ETALON = os.path.join(
    RACINE, "benchmarks", "juge_de_verification", "etalon-du-juge.json",
)


def charger_les_paires(combien=NOMBRE_DE_PAIRES):
    """
    Les premieres paires de l'etalon gele. / The frozen pairs.

    LECTURE SEULE du fichier gele : ce banc ne touche jamais la base, et
    mesure donc la meme chose avant et apres une reconstruction.
    / Read-only on the frozen file: the same measurement before and
    after a rebuild.
    """
    with open(CHEMIN_DE_L_ETALON, encoding="utf-8") as fichier:
        etalon = json.load(fichier)
    return etalon["paires"][:combien]


def main():
    import torch

    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument(
        "--threads", type=int, default=None,
        help="Ne mesurer QU'A ce réglage (pour la mesure de voisinage).",
    )
    analyseur.add_argument(
        "--paires", type=int, default=NOMBRE_DE_PAIRES,
        help=f"Combien de paires par réglage (défaut : {NOMBRE_DE_PAIRES}).",
    )
    options = analyseur.parse_args()
    reglages = [options.threads] if options.threads else THREADS_A_ESSAYER

    paires = charger_les_paires(options.paires)

    # LE CHARGEMENT VIENT AVANT LA BOUCLE, ET C'EST INDISPENSABLE.
    # `_charger_le_modele` RE-FIXE `torch.set_num_threads` depuis
    # l'environnement. Charge a l'interieur de la boucle, il ecraserait
    # le reglage qu'on vient de poser : la ligne « 2 threads » — celle
    # qui sert de REFERENCE a toute la colonne d'acceleration —
    # mesurerait en realite le defaut. Le banc ne reproduirait pas son
    # propre premier chiffre.
    # / The load re-sets the thread count from the environment: doing it
    #   inside the loop would silently measure the default instead.
    _charger_le_modele()

    print(f"\n{len(paires)} paires par réglage, "
          f"{len(reglages)} réglage(s), "
          f"{os.cpu_count()} cœurs.\n", flush=True)
    print(f"{'threads':>8} {'s/paire':>9} {'accélération':>13} "
          f"{'rendement/thread':>17}", flush=True)

    reference = None
    for nombre_de_threads in reglages:
        torch.set_num_threads(nombre_de_threads)
        # Une passe a blanc : le premier appel d'un reglage paie la
        # reallocation du pool de threads.
        # / A warm-up pass: the first call of a setting pays for the
        # thread-pool reallocation.
        noter_une_paire(
            paires[0]["affirmation"], paires[0]["texte_source"],
        )
        debut = time.time()
        for paire in paires:
            noter_une_paire(paire["affirmation"], paire["texte_source"])
        duree = (time.time() - debut) / len(paires)

        if reference is None:
            reference = duree
        acceleration = reference / duree
        # Rendement rapporte au reglage le plus bas : 1,00 au depart, et
        # ce qu'on garde en multipliant les threads.
        # / Efficiency relative to the lowest setting.
        rendement = acceleration / nombre_de_threads * reglages[0]
        print(f"{nombre_de_threads:>8} {duree:>9.1f} "
              f"{acceleration:>12.2f}× {rendement:>16.2f}", flush=True)


if __name__ == "__main__":
    main()
