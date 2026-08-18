"""
Banc d'essai MANUEL : rejouer l'etalon des paires jugees contre un juge
candidat. / MANUAL benchmark: replay the frozen pairs against a
candidate judge.

LOCALISATION : benchmarks/juge_de_verification/comparer_un_juge.py

CE N'EST PAS UN TEST. C'est un script `__main__` qui appelle un vrai
modele, donc FACTURE, et qui ne peut pas tourner dans une suite. Le
dossier `benchmarks/` n'est pas une app Django et n'a pas de
`__init__.py` : `manage.py test` ne le collecte pas.

IL N'ECRIT RIEN EN BASE, ET C'EST SA PROPRIETE CENTRALE. Il lit le
fichier gele par `manage.py geler_l_etalon_du_juge` et n'ouvre jamais un
`SourceLink` en ecriture. Comparer deux juges en rejouant la
verification detruirait l'etalon a la premiere execution : le bouton
« Vérifier les citations » rejuge tout l'article et REECRIT les
verdicts.

CE QU'IL MESURE. L'ACCORD, pas la verite. Ni le juge de reference ni le
candidat ne detiennent la bonne reponse : ce que ce banc produit, c'est
une matrice de desaccords — et un desaccord sur une citation est en
lui-meme une information, celle qui rend l'etat contestable.

LA QUESTION POSEE EST EXACTEMENT LA MEME. Le prompt, le jeton
impredictible et l'analyse de la reponse viennent de
`core/services/verification.py`, sans copie : deux copies du prompt
finiraient par poser deux questions differentes et la comparaison ne
voudrait plus rien dire.

Lancer depuis l'hote :

    docker exec -w /app hypostasia_web python \\
        benchmarks/juge_de_verification/comparer_un_juge.py <id_du_modele>

L'identifiant est celui d'un `AIModel` — `manage.py
affecter_un_modele_a_un_role --lister` les nomme.
"""

import json
import os
import sys
import time

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."),
))
django.setup()

from core.llm_providers import appeler_llm  # noqa: E402
from core.models import AIModel  # noqa: E402
from core.services.verification import (  # noqa: E402
    TAILLE_DE_PAQUET, _construire_le_prompt_du_juge, _verdicts_de_la_reponse,
)

CHEMIN_DE_L_ETALON = os.path.join(
    os.path.dirname(__file__), "etalon-du-juge.json",
)


def charger_l_etalon():
    """Lit le fichier gele. / Reads the frozen file."""
    if not os.path.exists(CHEMIN_DE_L_ETALON):
        raise SystemExit(
            f"Étalon introuvable : {CHEMIN_DE_L_ETALON}\n"
            f"Gelez-le d'abord : manage.py geler_l_etalon_du_juge",
        )
    with open(CHEMIN_DE_L_ETALON, encoding="utf-8") as fichier:
        return json.load(fichier)


def juger_les_paires(modele_ia, paires_gelees):
    """
    Fait juger les paires par le candidat, par paquets, sans rien
    ecrire. / Has the candidate judge the pairs, batch by batch.

    :return: {lien_id: "soutient" | "ne_soutient_pas" | None}
    """
    import uuid

    reponses_du_candidat = {}
    nombre_de_paquets = (
        (len(paires_gelees) + TAILLE_DE_PAQUET - 1) // TAILLE_DE_PAQUET
    )
    for numero_de_paquet, debut in enumerate(
        range(0, len(paires_gelees), TAILLE_DE_PAQUET), start=1,
    ):
        paquet = paires_gelees[debut:debut + TAILLE_DE_PAQUET]
        nonce = uuid.uuid4().hex[:12]
        paires_du_prompt = [
            (numero, paire["affirmation"], paire["texte_source"])
            for numero, paire in enumerate(paquet, start=1)
        ]
        print(
            f"  paquet {numero_de_paquet}/{nombre_de_paquets} "
            f"({len(paquet)} paires)…", flush=True,
        )
        try:
            reponse = appeler_llm(
                modele_ia,
                _construire_le_prompt_du_juge(paires_du_prompt, nonce),
            )
        except Exception as erreur:
            print(f"    échec du juge : {erreur}")
            for paire in paquet:
                reponses_du_candidat[paire["lien_id"]] = None
            continue

        verdicts = _verdicts_de_la_reponse(reponse, len(paquet))
        for numero, paire in enumerate(paquet, start=1):
            reponses_du_candidat[paire["lien_id"]] = (
                verdicts.get(numero) if verdicts else None
            )
    return reponses_du_candidat


def afficher_la_matrice(paires_gelees, reponses_du_candidat, duree):
    """La matrice d'accord, et rien de plus. / The agreement matrix."""
    comptes = {}
    for paire in paires_gelees:
        reference = paire["reponse_de_reference"]
        candidat = reponses_du_candidat.get(paire["lien_id"]) or "aucune"
        comptes[(reference, candidat)] = comptes.get(
            (reference, candidat), 0,
        ) + 1

    nombre_total = len(paires_gelees)
    accords = sum(
        nombre for (reference, candidat), nombre in comptes.items()
        if reference == candidat
    )
    sans_reponse = sum(
        nombre for (_reference, candidat), nombre in comptes.items()
        if candidat == "aucune"
    )

    print(f"\n  {nombre_total} paires rejouées en {duree:.0f} s")
    print(f"  accord      : {accords}/{nombre_total} "
          f"({100 * accords / nombre_total:.0f} %)")
    print(f"  sans réponse: {sans_reponse}")
    print("\n  référence → candidat")
    for (reference, candidat), nombre in sorted(comptes.items()):
        marque = " " if reference == candidat else "≠"
        print(f"   {marque} {reference:>16} → {candidat:<16} {nombre:>4}")

    desaccords = [
        paire for paire in paires_gelees
        if reponses_du_candidat.get(paire["lien_id"])
        and reponses_du_candidat[paire["lien_id"]]
        != paire["reponse_de_reference"]
    ]
    if desaccords:
        print(f"\n  Les {len(desaccords)} désaccords, par lien :")
        for paire in desaccords[:20]:
            print(
                f"   lien {paire['lien_id']:>5} : "
                f"{paire['reponse_de_reference']} vs "
                f"{reponses_du_candidat[paire['lien_id']]} — "
                f"« {paire['affirmation'][:70]}… »"
            )
        if len(desaccords) > 20:
            print(f"   … et {len(desaccords) - 20} autres.")


def main():
    """
    Usage :
      comparer_un_juge.py <id> [--enregistrer F] [--reference F]

    `--enregistrer` écrit les réponses du candidat dans un fichier.
    `--reference` compare contre CE fichier au lieu de l'étalon.

    LES DEUX ENSEMBLE MESURENT LE PLANCHER DE BRUIT — la reproductibilité
    d'un juge contre LUI-MÊME. Sans ce chiffre, un taux d'accord entre
    deux modèles ne veut rien dire : on ne sait pas quelle part du
    désaccord vient du modèle et quelle part vient du hasard.
    / Together they measure the noise floor: a judge against itself.
    Without it, an agreement rate between two models is uninterpretable.
    """
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        raise SystemExit(
            "Usage : comparer_un_juge.py <id_du_modele> "
            "[--enregistrer FICHIER] [--reference FICHIER]\n"
            "Les identifiants : manage.py affecter_un_modele_a_un_role "
            "--lister",
        )
    modele_ia = AIModel.objects.filter(pk=int(sys.argv[1])).first()
    if modele_ia is None:
        raise SystemExit(f"Aucun AIModel d'identifiant {sys.argv[1]}.")

    def _option(nom):
        return (
            sys.argv[sys.argv.index(nom) + 1] if nom in sys.argv else None
        )

    fichier_a_enregistrer = _option("--enregistrer")
    fichier_de_reference = _option("--reference")

    etalon = charger_l_etalon()
    paires_gelees = etalon["paires"]

    if fichier_de_reference:
        # La reference devient un run PRECEDENT : on mesure alors la
        # reproductibilite, pas l'accord avec le juge d'origine.
        # / The reference becomes a previous run: this measures
        # reproducibility, not agreement with the original judge.
        with open(fichier_de_reference, encoding="utf-8") as fichier:
            reponses_de_reference = json.load(fichier)
        paires_gelees = [
            dict(paire,
                 reponse_de_reference=reponses_de_reference[
                     str(paire["lien_id"])
                 ])
            for paire in paires_gelees
            if reponses_de_reference.get(str(paire["lien_id"]))
        ]
        nom_de_la_reference = f"le run enregistré {fichier_de_reference}"
    else:
        provenances = {paire["verifie_par"] for paire in paires_gelees}
        nom_de_la_reference = ", ".join(sorted(provenances))

    print(f"\nÉtalon gelé le {etalon['gele_le'][:10]} — "
          f"{len(paires_gelees)} paires")
    print(f"  référence     : {nom_de_la_reference}")
    print(f"  juge candidat : {modele_ia} (id {modele_ia.pk}, "
          f"température {modele_ia.temperature})")
    print("\n  APPELS FACTURÉS. Rien ne sera écrit en base.\n")

    debut = time.time()
    reponses_du_candidat = juger_les_paires(modele_ia, paires_gelees)

    if fichier_a_enregistrer:
        with open(fichier_a_enregistrer, "w", encoding="utf-8") as fichier:
            json.dump(
                {str(lien): reponse
                 for lien, reponse in reponses_du_candidat.items()},
                fichier, ensure_ascii=False, indent=2,
            )
        print(f"  réponses enregistrées dans {fichier_a_enregistrer}")

    afficher_la_matrice(
        paires_gelees, reponses_du_candidat, time.time() - debut,
    )


if __name__ == "__main__":
    main()
