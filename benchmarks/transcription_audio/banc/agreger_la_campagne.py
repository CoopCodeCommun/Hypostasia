#!/usr/bin/env python3
"""
Agrege les resultats d'une campagne en UN tableau comparatif.
/ Aggregates a campaign's results into ONE comparison table.

LOCALISATION : benchmarks/transcription_audio/banc/agreger_la_campagne.py

CE QUE CE SCRIPT PRODUIT : une ligne par (pile, tranche, machine), avec le
cout, le nombre de locuteurs trouve contre le nombre reel, le taux d'INCONNU et
le WER contre la transcription humaine.

LA COLONNE « MACHINE » N'EST PAS DECORATIVE. Les memes mesures seront refaites
sur une autre machine ; deux chiffres de deux machines dans un tableau sans
cette colonne sont un piege, pas un resultat. Elle est lue dans chaque fichier
de resultat, jamais saisie a la main.
/ The « machine » column is not decorative: the same measurements will be rerun
elsewhere, and two numbers from two machines without it are a trap.

Usage : python3 agreger_la_campagne.py [dossier] [--sortie tableau.md]
"""
import argparse
import glob
import json
import os
import re
import sys

# Le nombre REEL de voix par tranche, etabli en lisant la transcription humaine —
# pas en croyant une pile sur parole. Et le tour ou la reference commence.
# / The REAL voice count per slice, established from the human transcript.
TRANCHES_CONNUES = {
    "T1": {"reference": "reference.json", "tour_de_depart": 10, "voix_reelles": 4,
           "description": "Tactic 0-900 s — 4 voix, dont une a 90 mots"},
    "T2": {"reference": "reference_cafe_libre.json", "tour_de_depart": 35, "voix_reelles": 4,
           "description": "Cafe libre 600-1500 s — 4 voix equilibrees"},
    "T3": {"reference": "reference_cafe_libre.json", "tour_de_depart": 128, "voix_reelles": 4,
           "description": "Cafe libre 2790-3690 s — 4 voix"},
    "T4": {"reference": "reference_cafe_libre.json", "tour_de_depart": 143, "voix_reelles": 6,
           "description": "Emission entiere 4100-5000 s — SIX voix"},
}

# Le nom lisible de chaque pile, dans l'ordre ou on veut les lire.
# / The readable name of each stack, in reading order.
NOMS_DES_PILES = [
    ("voieA-sortformer", "voie A — parakeet-rs + Sortformer v2 (plafond 4)"),
    ("voieA-ultra8", "voie A — parakeet-rs patche + Ultra-Sortformer 8spk"),
    ("pilote-diarize", "pilote — onnx-asr + diarize (WeSpeaker)"),
    ("pilote-sherpa", "pilote — onnx-asr + sherpa-onnx (pyannote ONNX)"),
    ("pilote-pyannote", "pilote — onnx-asr + pyannote 3.1 (legacy, PyTorch)"),
    ("pilote-community", "pilote — onnx-asr + pyannote community-1 (courant)"),
    ("whisperx", "WhisperX — Whisper large-v3 + wav2vec2 + community-1"),
    ("whisperx-turbo", "WhisperX — Whisper large-v3-turbo (ASR seul)"),
    ("whisperx-medium", "WhisperX — Whisper medium (ASR seul)"),
    ("whisperx-small", "WhisperX — Whisper small (ASR seul)"),
    ("achetronic", "achetronic/parakeet (serveur Go, sans diarisation)"),
    ("loudpage", "loudpage/parakeet-v3-diarized (NeMo + pyannote)"),
    ("voxtral", "Voxtral (API Mistral)"),
]


# Une quarantaine de mots anglais tres courants. Ce n'est PAS un detecteur de
# langue : c'est un indicateur du phenomene de bascule mesure le 22 aout 2026,
# ou Parakeet nourri par blocs de 240 s rendait « We are donc in Belgique
# already ». La valeur de reference est celle de la transcription HUMAINE
# (0,10 %) : au-dessus, la pile part en anglais.
# / Not a language detector: an indicator of the code-switching failure mode.
MOTS_ANGLAIS_COURANTS = {
    "the", "and", "that", "this", "with", "of", "is", "was", "are", "were", "it",
    "its", "we", "you", "they", "their", "have", "has", "for", "but", "not",
    "what", "which", "there", "would", "could", "should", "about", "from",
    "when", "where", "because", "something", "things", "people", "very",
    "really", "also", "already", "suppose", "think",
}


def taux_de_mots_anglais(texte):
    """
    Part des mots anglais tres courants, en pourcentage.
    / Share of very common English words, as a percentage.
    """
    mots_du_texte = re.findall(r"[a-zàâçéèêëîïôûùüÿñæœ']+", texte.lower())
    if not mots_du_texte:
        return None
    anglais = sum(1 for mot in mots_du_texte if mot in MOTS_ANGLAIS_COURANTS)
    return round(100 * anglais / len(mots_du_texte), 2)


def lire_le_pic_memoire(dossier, etiquette):
    """
    Lit le pic RSS dans la sortie de `/usr/bin/time -v`.
    / Reads peak RSS from `/usr/bin/time -v` output.

    Rend None quand le fichier n'existe pas : une pile mesuree sans
    `/usr/bin/time` n'a pas de pic, et il vaut mieux une case vide qu'un zero
    qu'on lirait comme « ne consomme rien ».
    / Returns None when absent: an empty cell beats a zero read as "uses nothing".
    """
    chemin = os.path.join(dossier, f"mesures_{etiquette}.txt")
    if not os.path.exists(chemin):
        return None
    with open(chemin, encoding="utf-8", errors="replace") as fichier:
        for ligne in fichier:
            if "Maximum resident set size" in ligne:
                kilo_octets = int(ligne.strip().split()[-1])
                return round(kilo_octets / 1048576, 2)
    return None


def calculer_le_wer(dossier, resultat, nom_de_la_tranche):
    """
    WER contre la transcription humaine, par le MEME code que `comparer.py`.
    / WER against the human transcript, using the SAME code as `comparer.py`.
    """
    if nom_de_la_tranche not in TRANCHES_CONNUES:
        return None
    parametres = TRANCHES_CONNUES[nom_de_la_tranche]
    chemin_reference = os.path.join(dossier, parametres["reference"])
    if not os.path.exists(chemin_reference):
        return None

    sys.path.insert(0, dossier)
    import comparer  # noqa: E402  — le module vit a cote des resultats

    with open(chemin_reference, encoding="utf-8") as fichier:
        tours = json.load(fichier)[parametres["tour_de_depart"]:]
    mots_de_reference = comparer.mots(" ".join(tour["texte"] for tour in tours))
    mots_de_la_machine = comparer.mots(resultat.get("texte_brut", ""))
    if not mots_de_la_machine or not mots_de_reference:
        return None
    taux, *_ = comparer.wer_semi_global(mots_de_la_machine, mots_de_reference)
    return round(100 * taux, 2)


def main():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("dossier", nargs="?", default=".",
                           help="dossier de travail contenant les resultat_*.json")
    analyseur.add_argument("--sortie", default="tableau_comparatif.md")
    arguments = analyseur.parse_args()
    dossier = arguments.dossier

    # LA MACHINE DE REPLI. Le banc Rust et le script Voxtral n'ecrivent pas de
    # bloc `machine` : le premier est un binaire qui ne lit pas /proc, le second
    # tourne dans le conteneur du projet. Leurs lignes afficheraient « None
    # vCPU » — soit un trou dans la colonne qui sert justement a comparer deux
    # machines. On reprend donc la machine relevee par les piles Python de la
    # MEME campagne : elles ont tourne sur le meme materiel, a la suite.
    # C'est une deduction, et elle est marquee comme telle dans campagne.json.
    # / The Rust bench and the Voxtral script write no `machine` block; we reuse
    # the one the Python stacks recorded in the SAME campaign, and flag it.
    machine_de_repli = {}
    for chemin in sorted(glob.glob(os.path.join(dossier, "resultat_*.json"))):
        with open(chemin, encoding="utf-8") as fichier:
            candidate = json.load(fichier).get("machine")
        if candidate and candidate.get("coeurs_visibles"):
            machine_de_repli = candidate
            break

    lignes_du_tableau = []
    for chemin in sorted(glob.glob(os.path.join(dossier, "resultat_*.json"))):
        etiquette = re.sub(r"^resultat_|\.json$", "", os.path.basename(chemin))
        correspondance = re.match(r"^(T\d+)-(.+)$", etiquette)
        if not correspondance:
            continue  # les essais et les anciens noms ne sont pas de la campagne
        nom_de_la_tranche, cle_de_la_pile = correspondance.groups()

        with open(chemin, encoding="utf-8") as fichier:
            resultat = json.load(fichier)

        locuteurs_trouves = resultat.get("locuteurs_detectes")
        if locuteurs_trouves is None:
            locuteurs_trouves = len({s.get("locuteur") for s in resultat.get("segments", [])})

        machine = resultat.get("machine") or {}
        machine_deduite = False
        if not machine.get("coeurs_visibles") and machine_de_repli:
            machine, machine_deduite = machine_de_repli, True
        diarisation = resultat.get("diarisation_s")
        transcription = resultat.get("transcription_s")
        bout_en_bout = resultat.get("appel_http_bout_en_bout_s") or resultat.get("appel_api_s")
        duree_audio = resultat.get("duree_audio_s") or 0

        total = None
        if diarisation is not None and transcription is not None:
            total = round(diarisation + transcription, 2)
        elif bout_en_bout is not None:
            total = bout_en_bout

        lignes_du_tableau.append({
            "tranche": nom_de_la_tranche,
            "pile": cle_de_la_pile,
            "nom_lisible": dict(NOMS_DES_PILES).get(cle_de_la_pile, cle_de_la_pile),
            "machine": machine.get("processeur", "?"),
            "coeurs": machine.get("coeurs_visibles"),
            "vnni_ou_amx": machine.get("vnni_ou_amx"),
            "etat_de_la_stack": machine.get("etat_de_la_stack", ""),
            "machine_deduite": machine_deduite,
            "duree_audio_s": duree_audio,
            "diarisation_s": diarisation,
            "transcription_s": transcription,
            "inference_totale_s": total,
            "minutes_par_heure_audio": round(60 * total / duree_audio, 1) if total and duree_audio else None,
            "pic_rss_go": lire_le_pic_memoire(dossier, etiquette),
            "voix_reelles": TRANCHES_CONNUES.get(nom_de_la_tranche, {}).get("voix_reelles"),
            "locuteurs_trouves": locuteurs_trouves,
            "taux_inconnu": resultat.get("taux_mots_inconnu_pourcent"),
            "wer": calculer_le_wer(dossier, resultat, nom_de_la_tranche),
            "mots": resultat.get("mots_total") or len(resultat.get("texte_brut", "").split()),
            "mots_anglais_pourcent": taux_de_mots_anglais(resultat.get("texte_brut", "")),
        })

    ordre_des_piles = {cle: rang for rang, (cle, _) in enumerate(NOMS_DES_PILES)}
    lignes_du_tableau.sort(key=lambda ligne: (ligne["tranche"],
                                              ordre_des_piles.get(ligne["pile"], 99)))

    with open(os.path.join(dossier, "campagne.json"), "w", encoding="utf-8") as fichier:
        json.dump(lignes_du_tableau, fichier, ensure_ascii=False, indent=1)

    sortie = ["| tranche | pile | machine | diar. | transcr. | total | min/h | pic RSS | locuteurs | INCONNU | WER | mots | anglais |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for ligne in lignes_du_tableau:
        def formater(valeur, unite="", decimales=1):
            return "—" if valeur is None else f"{valeur:.{decimales}f}{unite}"
        locuteurs = f"{ligne['locuteurs_trouves']} / {ligne['voix_reelles']}"
        sortie.append(
            f"| {ligne['tranche']} | {ligne['nom_lisible']} | {ligne['coeurs']} vCPU "
            f"{'sans VNNI' if not ligne['vnni_ou_amx'] else 'VNNI'}"
            f"{'*' if ligne['machine_deduite'] else ''} "
            f"| {formater(ligne['diarisation_s'], ' s')} | {formater(ligne['transcription_s'], ' s')} "
            f"| {formater(ligne['inference_totale_s'], ' s')} | {formater(ligne['minutes_par_heure_audio'], ' min')} "
            f"| {formater(ligne['pic_rss_go'], ' Go', 2)} | {locuteurs} "
            f"| {formater(ligne['taux_inconnu'], ' %')} | {formater(ligne['wer'], ' %', 2)} "
            f"| {ligne['mots']} | {formater(ligne['mots_anglais_pourcent'], ' %', 2)} |"
        )

    texte = "\n".join(sortie)
    with open(os.path.join(dossier, arguments.sortie), "w", encoding="utf-8") as fichier:
        fichier.write(texte + "\n")
    print(texte)
    print(f"\n{len(lignes_du_tableau)} lignes — ecrites dans {arguments.sortie} et campagne.json")


if __name__ == "__main__":
    main()
