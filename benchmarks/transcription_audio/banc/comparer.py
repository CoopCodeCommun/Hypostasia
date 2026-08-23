#!/usr/bin/env python3
"""
Compare la sortie machine a la transcription humaine de reference.
/ Compares machine output against the human reference transcript.

Calcule un WER par alignement semi-global : la reference peut etre tronquee
a la fin sans penalite, puisqu'on ne transcrit qu'un extrait du debut du segment.
/ Computes WER via semi-global alignment: the reference may be truncated at the
end without penalty, since we only transcribe an extract from the segment start.

ATTENTION : la reference n'a PAS d'horodatage, donc aucun DER n'est calculable.
On ne compare que le nombre de locuteurs et la repartition de la parole.
/ NOTE: the reference has NO timestamps, so no DER can be computed.

Usage: comparer.py [resultat_*.json] [reference.json] [tour_de_depart]
"""
import json
import re
import sys
import unicodedata

CHEMIN_HYPOTHESE = sys.argv[1] if len(sys.argv) > 1 else "resultat_fp32.json"
CHEMIN_REFERENCE = sys.argv[2] if len(sys.argv) > 2 else "reference.json"
# La page de reference couvre toute l'emission (chroniques comprises) ; le fichier
# audio ne couvre que le sujet principal. On demarre donc la reference a ce tour-la.
# / The reference page covers the whole show; the audio file only covers the main
# topic, so we start the reference at that turn.
TOUR_DE_DEPART = int(sys.argv[3]) if len(sys.argv) > 3 else 10

# Le meme intervenant est ecrit de deux facons dans la page / same person, two spellings
ALIAS_LOCUTEURS = {"Celo": "Célo"}


def normaliser(texte):
    """
    Minuscules, ponctuation remplacee par une espace, espaces normalises.
    Les accents sont GARDES : c'est du francais, ils portent du sens.
    / Lowercase, punctuation replaced by a space, whitespace normalised.
    Accents are KEPT.
    """
    texte = texte.lower()
    # Les apostrophes typographiques deviennent des apostrophes simples
    # / Typographic apostrophes become plain ones
    texte = texte.replace("’", "'").replace("‘", "'")
    # La ponctuation est REMPLACEE par une espace, jamais supprimee : sinon
    # "peut-etre" deviendrait "peutetre" et ne s'alignerait plus sur "peut etre".
    # / Punctuation is REPLACED by a space, never removed.
    texte = "".join(
        " " if unicodedata.category(caractere).startswith("P") else caractere
        for caractere in texte
    )
    return re.sub(r"\s+", " ", texte).strip()


def mots(texte):
    return normaliser(texte).split()


def wer_semi_global(hypothese, reference):
    """
    Distance d'edition au niveau des mots, fin de reference libre.
    / Word-level edit distance, reference end free.
    Retourne (wer, erreurs, longueur_reference_utilisee, S, D, I).
    """
    n, m = len(hypothese), len(reference)
    if n == 0:
        return 1.0, m, m, 0, m, 0
    if m == 0:
        return 1.0, n, 0, 0, 0, n

    # d[j] pour la ligne courante ; on garde aussi le decompte des operations
    # / d[j] for the current row, plus the per-operation tally
    precedente = list(range(m + 1))
    ops_precedente = [(0, j, 0) for j in range(m + 1)]  # (subs, del, ins)

    for i in range(1, n + 1):
        courante = [i] + [0] * m
        ops_courante = [(0, 0, i)] + [(0, 0, 0)] * m
        for j in range(1, m + 1):
            cout_substitution = 0 if hypothese[i - 1] == reference[j - 1] else 1
            candidat_diag = precedente[j - 1] + cout_substitution
            candidat_suppr = courante[j - 1] + 1      # mot de reference non produit
            candidat_inser = precedente[j] + 1        # mot en trop dans l'hypothese
            meilleur = min(candidat_diag, candidat_suppr, candidat_inser)
            courante[j] = meilleur
            if meilleur == candidat_diag:
                s, d, ins = ops_precedente[j - 1]
                ops_courante[j] = (s + cout_substitution, d, ins)
            elif meilleur == candidat_suppr:
                s, d, ins = ops_courante[j - 1]
                ops_courante[j] = (s, d + 1, ins)
            else:
                s, d, ins = ops_precedente[j]
                ops_courante[j] = (s, d, ins + 1)
        precedente, ops_precedente = courante, ops_courante

    # Fin de reference libre : on prend le j qui minimise le WER, pas la distance brute.
    # La borne basse a n//2 evite de retenir une troncature absurdement courte ; si
    # l'hypothese fait plus du double de la reference, on balaie tout l'intervalle.
    # / Free reference end: pick the j minimising WER. The n//2 floor avoids absurdly
    # short truncations; if the hypothesis is more than twice the reference, scan all.
    borne_basse = min(max(1, n // 2), m)
    meilleur_wer, meilleur_j = None, m
    for j in range(borne_basse, m + 1):
        wer_ici = precedente[j] / j
        if meilleur_wer is None or wer_ici < meilleur_wer:
            meilleur_wer, meilleur_j = wer_ici, j

    s, d, ins = ops_precedente[meilleur_j]
    return meilleur_wer, precedente[meilleur_j], meilleur_j, s, d, ins


def tronquer_les_tours(tours, nombre_de_mots_voulu):
    """
    Ne garde que les tours couvrant les N premiers mots normalises.
    Sans cela, on comparerait 15 min de machine a tout le reste de la page.
    / Keeps only the turns covering the first N normalised words.
    """
    retenus = []
    cumul = 0
    for tour in tours:
        compte = len(mots(tour["texte"]))
        if cumul >= nombre_de_mots_voulu:
            break
        retenus.append(tour)
        cumul += compte
    return retenus


def main():
    with open(CHEMIN_HYPOTHESE, encoding="utf-8") as fichier:
        resultat = json.load(fichier)
    with open(CHEMIN_REFERENCE, encoding="utf-8") as fichier:
        reference = json.load(fichier)

    if TOUR_DE_DEPART >= len(reference):
        print(f"ERREUR : tour de depart {TOUR_DE_DEPART} au-dela des {len(reference)} tours.")
        sys.exit(1)

    reference = reference[TOUR_DE_DEPART:]
    for tour in reference:
        tour["locuteur"] = ALIAS_LOCUTEURS.get(tour["locuteur"], tour["locuteur"])
    print(f"reference demarree au tour {TOUR_DE_DEPART} "
          f"({len(reference)} tours retenus, premier locuteur : {reference[0]['locuteur']})")

    texte_hypothese = resultat["texte_brut"]
    texte_reference = " ".join(tour["texte"] for tour in reference)

    hypothese_mots = mots(texte_hypothese)
    reference_mots = mots(texte_reference)

    print("=" * 78)
    print("COMPARAISON A LA TRANSCRIPTION HUMAINE")
    print("=" * 78)
    print(f"mots produits par la machine : {len(hypothese_mots)}")
    print(f"mots dans la reference       : {len(reference_mots)}")
    print()

    wer, erreurs, longueur_utilisee, subs, dels, inserts = wer_semi_global(
        hypothese_mots, reference_mots
    )
    print(f"reference alignee sur        : {longueur_utilisee} mots "
          f"({100.0 * longueur_utilisee / max(1, len(reference_mots)):.0f} % du total)")
    print(f"erreurs                      : {erreurs}")
    print(f"  substitutions              : {subs}")
    print(f"  omissions                  : {dels}")
    print(f"  insertions                 : {inserts}")
    print()
    print(f"  >>> WER = {100.0 * wer:.2f} %   (borne INFERIEURE, cf. spec 5.4)")
    print()

    print("-" * 78)
    print("LOCUTEURS")
    print("-" * 78)
    # On ne compte que la portion de reference reellement alignee, sinon on
    # comparerait l'extrait transcrit a tout ce qui suit dans la page.
    # / Only count the reference portion actually aligned.
    reference_alignee = tronquer_les_tours(reference, longueur_utilisee)
    print(f"(portion alignee : {len(reference_alignee)} tours sur {len(reference)})")

    locuteurs_reference = {}
    for tour in reference_alignee:
        locuteurs_reference.setdefault(tour["locuteur"], 0)
        locuteurs_reference[tour["locuteur"]] += len(tour["texte"].split())
    print(f"reference : {len(locuteurs_reference)} locuteurs")
    for nom, nombre in sorted(locuteurs_reference.items(), key=lambda x: -x[1]):
        print(f"  {nom} : {nombre} mots")

    compte_machine = {}
    for segment in resultat["segments"]:
        compte_machine.setdefault(segment["locuteur"], 0)
        compte_machine[segment["locuteur"]] += len(segment["texte"].split())
    print(f"\nmachine   : {resultat['locuteurs_detectes']} locuteurs detectes par Sortformer")
    for nom, nombre in sorted(compte_machine.items(), key=lambda x: -x[1]):
        print(f"  {nom} : {nombre} mots")

    print()
    print("NOTE : la reference n'ayant aucun horodatage, le DER n'est pas calculable.")
    print("       Seuls le nombre de locuteurs et la repartition de parole sont comparables.")
    print("       Le taux d'INCONNU ne detecte pas le depassement des 4 locuteurs (spec 4.5).")


if __name__ == "__main__":
    main()
