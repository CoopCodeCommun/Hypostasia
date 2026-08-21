#!/usr/bin/env python
"""
Banc MANUEL : separer le BRUIT, l'effet du SUJET et l'effet du MODELE.
/ MANUAL bench: separate NOISE, SUBJECT effect and MODEL effect.

LOCALISATION : benchmarks/redaction/analyser_les_passes.py

CE QU'IL REPOND. Toutes les campagnes precedentes ont fait UNE passe par
modele : elles ne pouvaient pas distinguer un ecart de modele d'un ecart
de tirage. Celui-ci lit `passes_repetees.json` et rend, pour chaque
mesure, l'ETENDUE entre les repetitions d'une meme condition.

LA REGLE DE LECTURE, ET ELLE EST SIMPLE : **un ecart entre deux modeles
ne veut rien dire s'il ne depasse pas l'etendue observee entre deux
passes d'un meme modele.** C'est tout ce que cette analyse sert a dire.

Il ne lit aucun modele et n'ecrit rien en base.
"""

import json
import os
import statistics
import sys
from collections import Counter, defaultdict

CHEMIN_DES_PASSES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "passes_repetees.json",
)


def _mesures_d_une_passe(articles):
    """Les mesures agregees d'une passe. / One pass, aggregated."""
    etats = Counter()
    caracteres = citations = distinctes = 0
    phrases = phrases_nues = 0
    for article in articles:
        etats.update(article["etats"])
        caracteres += article["caracteres"]
        citations += article["citations"]
        distinctes += article["distinctes"]
        phrases += article["prose_nue"]["phrases"]
        phrases_nues += article["prose_nue"]["phrases_sans_marqueur"]
    verifiees, faibles = etats["verifie"], etats["faible"]
    return {
        "citations": citations,
        "vérifiées": verifiees,
        "% vérifiées": 100 * verifiees / max(verifiees + faibles, 1),
        "introuvables": etats["introuvable"],
        "% prose nue": 100 * phrases_nues / max(phrases, 1),
        "caractères": caracteres,
        "distinctes": distinctes,
    }


def _etendue(valeurs):
    """max - min. L'etendue, pas l'ecart-type : sur trois passes, il
    ferait croire a une precision que trois points ne donnent pas.
    / Range, not standard deviation: three points do not earn one."""
    return max(valeurs) - min(valeurs)


def main():
    if not os.path.exists(CHEMIN_DES_PASSES):
        raise SystemExit(f"Absent : {CHEMIN_DES_PASSES}")
    passes_par_modele = json.load(open(CHEMIN_DES_PASSES))

    mesures = defaultdict(lambda: defaultdict(list))
    for modele, passes in passes_par_modele.items():
        for articles in passes:
            for nom, valeur in _mesures_d_une_passe(articles).items():
                mesures[nom][modele].append(valeur)

    print("\n=== CHAQUE MESURE, PASSE PAR PASSE ===\n")
    for nom in mesures:
        print(f"  {nom}")
        for modele, valeurs in mesures[nom].items():
            valeurs_affichees = " · ".join(f"{v:7.1f}" for v in valeurs)
            print(f"    {modele:8} {valeurs_affichees}   "
                  f"médiane {statistics.median(valeurs):7.1f}   "
                  f"étendue {_etendue(valeurs):6.1f}")
        print()

    print("=== L'ÉCART ENTRE MODÈLES SURVIT-IL AU BRUIT ? ===\n")
    print("  Un écart ne compte que s'il dépasse la PLUS GRANDE étendue")
    print("  observée entre deux passes d'un même modèle.\n")
    for nom, par_modele in mesures.items():
        if len(par_modele) < 2:
            continue
        bruit = max(_etendue(v) for v in par_modele.values())
        medianes = {m: statistics.median(v) for m, v in par_modele.items()}
        meilleur = max(medianes, key=medianes.get)
        pire = min(medianes, key=medianes.get)
        ecart = medianes[meilleur] - medianes[pire]
        verdict = "TRANCHE" if ecart > bruit else "dans le bruit"
        print(f"  {nom:14} {pire} {medianes[pire]:.1f} → "
              f"{meilleur} {medianes[meilleur]:.1f} · "
              f"écart {ecart:.1f} · bruit {bruit:.1f} · **{verdict}**")

    print("\n=== L'EFFET DU SUJET ===\n")
    print("  Un modèle peut être bon sur un sujet et mauvais sur un autre :")
    print("  l'agrégat le cacherait.\n")
    for modele, passes in passes_par_modele.items():
        par_article = defaultdict(list)
        for articles in passes:
            for article in articles:
                prose = article["prose_nue"]
                par_article[article["titre"][:40]].append(
                    100 * prose["phrases_sans_marqueur"]
                    / max(prose["phrases"], 1)
                )
        print(f"  {modele} — % de prose sans marqueur, par article :")
        for titre, valeurs in par_article.items():
            print(f"    {titre:42} {statistics.median(valeurs):5.1f} % "
                  f"(étendue {_etendue(valeurs):4.1f})")
        print()


if __name__ == "__main__":
    main()
