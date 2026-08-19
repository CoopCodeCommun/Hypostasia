"""
Jusqu'ou l'etalon peut-il etre predit ? Le PLAFOND, mesure.
/ How well can the etalon be predicted at all? The CEILING, measured.

LOCALISATION : benchmarks/juge_de_verification/mesurer_le_plafond_de_l_etalon.py

⚠ **CE SCRIPT APPELLE UNE API. IL EST FACTURE.** C'est la seule
difference qui compte avec `comparer_un_encodeur.py`, lequel promet
l'inverse — et c'est pourquoi les deux ne sont pas dans le meme fichier.
Le cout reste minuscule : 145 paires en 8 appels.

## LA QUESTION QUE CE SCRIPT REPOND

Tout ce dossier compare des juges a l'etalon gele par une AUC. Personne
n'a jamais mesure **jusqu'ou cette AUC peut monter**. Sans ce chiffre,
0,734 et 0,738 ne se lisent pas : on ignore s'ils sont mediocres ou
proches du maximum atteignable.

Or on sait deja que le maximum n'est PAS 1,0 :

- les 118 « soutient » et 27 « ne_soutient_pas » de l'etalon sont **un
  tirage**. Le meme modele, sur les memes paires, a rendu de **105 a
  133** verdicts positifs sur cinq executions (mesure du 17 aout) ;
- rejoue contre lui-meme a temperature 0, il ne retrouve que **77 %** de
  ses propres verdicts ;
- l'etalon lui-meme a ete produit a la temperature **par defaut**, soit
  **0,7** pour ce modele dans le referentiel — donc en echantillonnant.

## COMMENT LE PLAFOND SE MESURE

On fait rejouer les 145 paires **au modele meme qui a produit
l'etalon**, et on calcule l'AUC de ses degres d'aujourd'hui contre ses
verdicts geles d'hier. C'est litteralement « jusqu'ou la reference se
predit elle-meme ».

Aucun juge — ni ShieldStral, ni un encodeur, ni un humain — ne peut
raisonnablement esperer faire mieux sur ce jeu, puisque ce plafond
mesure la part de l'etalon qui est REPRODUCTIBLE plutot qu'accidentelle.

## CE QUE CE SCRIPT N'ECRIT PAS

Rien en base. Il lit l'etalon gele et n'ouvre aucun `SourceLink` en
ecriture, exactement comme `comparer_un_juge.py`.

    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_de_verification/mesurer_le_plafond_de_l_etalon.py 2
"""

import os
import sys
import time
import uuid

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."),
))
django.setup()

# LE PROMPT ET LE PARSEUR VIENNENT DE LA PRODUCTION, SANS COPIE, et la
# metrique vient du banc voisin, sans copie non plus. Ce plafond doit
# etre comparable AU CHIFFRE PRES aux AUC des autres bancs : une seconde
# implementation de l'une ou de l'autre le rendrait incomparable, donc
# inutile.
# / Prompt, parser and metric all imported, never copied: this ceiling
# must be comparable to the other benches' AUC to the digit.
from comparer_shieldstral import (  # noqa: E402
    aire_sous_la_courbe, paires_de_l_etalon,
)
from core.llm_providers import appeler_llm  # noqa: E402
from core.models import AIModel  # noqa: E402
from core.services.verification import (  # noqa: E402
    TAILLE_DE_PAQUET, _construire_le_prompt_du_juge, _scores_de_la_reponse,
)


def degres_du_juge(modele_ia, paires):
    """
    Fait rejouer les paires et rend le DEGRE de chacune, sans seuil.
    / Replays the pairs and returns each degree, unthresholded.

    Le seuil est justement ce qu'on ne veut pas ici : l'AUC s'en passe,
    et c'est sa raison d'etre dans ce dossier.
    / No threshold: the AUC does not need one, which is its whole point.

    :return: la liste des degres, dans l'ordre des paires, None si perdu
    """
    degres = [None] * len(paires)
    nombre_de_paquets = (
        (len(paires) + TAILLE_DE_PAQUET - 1) // TAILLE_DE_PAQUET
    )
    for numero_de_paquet, debut in enumerate(
        range(0, len(paires), TAILLE_DE_PAQUET), start=1,
    ):
        paquet = paires[debut:debut + TAILLE_DE_PAQUET]
        nonce = uuid.uuid4().hex[:12]
        paires_du_prompt = [
            (rang, paire["affirmation"], paire["source"])
            for rang, paire in enumerate(paquet, start=1)
        ]
        print(f"  paquet {numero_de_paquet}/{nombre_de_paquets} "
              f"({len(paquet)} paires)…", flush=True)
        try:
            reponse = appeler_llm(
                modele_ia,
                _construire_le_prompt_du_juge(paires_du_prompt, nonce),
            )
        except Exception as erreur:
            print(f"    échec du juge : {erreur}")
            continue
        scores = _scores_de_la_reponse(reponse, len(paquet)) or {}
        for rang, _paire in enumerate(paquet, start=1):
            degres[debut + rang - 1] = scores.get(rang)
    return degres


def main():
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        raise SystemExit(
            "Usage : mesurer_le_plafond_de_l_etalon.py <id_du_modele>\n"
            "Prenez celui qui a PRODUIT l'étalon — sinon ce n'est plus un "
            "plafond,\nc'est un accord entre deux juges différents.\n"
            "Les identifiants : manage.py affecter_un_modele_a_un_role "
            "--lister",
        )
    modele_ia = AIModel.objects.filter(pk=int(sys.argv[1])).first()
    if modele_ia is None:
        raise SystemExit(f"Aucun AIModel d'identifiant {sys.argv[1]}.")

    paires = paires_de_l_etalon()
    verites = [paire["verite"] for paire in paires]

    print(f"\n  {len(paires)} paires gelées — "
          f"{sum(verites)} positives, {len(verites) - sum(verites)} négatives")
    print(f"  juge         : {modele_ia} (température {modele_ia.temperature})")
    print("\n  ⚠ APPELS FACTURÉS. Rien ne sera écrit en base.\n")

    debut = time.time()
    degres = degres_du_juge(modele_ia, paires)
    duree = time.time() - debut

    utiles = [
        (degre, verite) for degre, verite in zip(degres, verites)
        if degre is not None
    ]
    if not utiles:
        raise SystemExit("Aucun degré exploitable : rien à mesurer.")

    notes = [degre for degre, _verite in utiles]
    verdicts = [verite for _degre, verite in utiles]
    auc = aire_sous_la_courbe(notes, verdicts)

    print(f"\n  {len(utiles)}/{len(paires)} paires notées en {duree:.0f} s")
    print(f"  crans rendus : "
          f"{ {note: notes.count(note) for note in sorted(set(notes))} }")
    print(f"\n  ★ PLAFOND — AUC des degrés d'aujourd'hui contre les "
          f"verdicts gelés : {auc:.3f}")
    print(
        "\n  C'est le maximum qu'un juge peut raisonnablement viser sur ce "
        "jeu.\n  Toute AUC des autres bancs se lit PAR RAPPORT à ce "
        "chiffre, pas par rapport à 1,0.",
    )


if __name__ == "__main__":
    main()
