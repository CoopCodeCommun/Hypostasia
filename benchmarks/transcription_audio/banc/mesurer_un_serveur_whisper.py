#!/usr/bin/env python3
"""
Mesure une pile servie derriere une API compatible OpenAI Whisper.
/ Measures a stack served behind an OpenAI-Whisper-compatible API.

LOCALISATION : benchmarks/transcription_audio/banc/mesurer_un_serveur_whisper.py

DEUX CANDIDATS DE LA SPEC PASSENT PAR LA :

| serveur | ce qu'il fait | diarisation |
|---|---|---|
| `achetronic/parakeet` | serveur Go, Parakeet TDT v3 en ONNX, sorties VTT/SRT | **non** |
| `loudpage/parakeet-v3-diarized` | Parakeet (NeMo/PyTorch) + pyannote | oui, jeton requis |

CE QUE CE SCRIPT NE MESURE PAS, ET POURQUOI. Le chrono porte sur l'appel HTTP
complet, chargement des modeles compris si le serveur les charge a la demande.
Ce n'est donc pas comparable au RTFx d'inference pure de `mesurer_une_pile.py` —
c'est un temps de bout en bout, et il est etiquete comme tel dans le resultat.
/ The timer covers the whole HTTP call: end-to-end, not pure inference.

UN SERVEUR SANS DIARISATION REND UN SEUL LOCUTEUR. Ce n'est pas un echec de
mesure, c'est le constat : la pile ne repond pas au critere 1 de la spec, et
`locuteurs_detectes` vaut 1 pour le dire.

Usage :
    python3 mesurer_un_serveur_whisper.py --url http://localhost:5092 \\
        --audio audio/extrait.wav --etiquette t1-achetronic \\
        --etat-de-la-stack "workers Celery au repos"
"""
import argparse
import json
import os
import platform
import re
import subprocess
import time
import urllib.request
import uuid


def lire_les_arguments():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--url", required=True,
                           help="racine du serveur, par exemple http://localhost:5092")
    analyseur.add_argument("--audio", required=True)
    analyseur.add_argument("--format", default="verbose_json",
                           help="response_format demande au serveur")
    analyseur.add_argument("--diarisation", action="store_true",
                           help="demander la diarisation quand le serveur la propose")
    analyseur.add_argument("--etiquette", default="serveur")
    analyseur.add_argument("--nom-de-la-pile", default="",
                           help="nom lisible du candidat, pour le tableau comparatif")
    analyseur.add_argument("--etat-de-la-stack", required=True)
    analyseur.add_argument("--delai-maximum", type=float, default=1800.0)
    return analyseur.parse_args()


def decrire_la_machine(etat_de_la_stack):
    """Carte d'identite de la machine. / Machine identity card."""
    modele_de_processeur, drapeaux = "inconnu", ""
    with open("/proc/cpuinfo", encoding="utf-8") as fichier:
        for ligne in fichier:
            if ligne.startswith("model name") and modele_de_processeur == "inconnu":
                modele_de_processeur = ligne.split(":", 1)[1].strip()
            if ligne.startswith("flags") and not drapeaux:
                drapeaux = ligne.split(":", 1)[1]
    memoire_disponible_go = 0.0
    with open("/proc/meminfo", encoding="utf-8") as fichier:
        for ligne in fichier:
            if ligne.startswith("MemAvailable"):
                memoire_disponible_go = int(ligne.split()[1]) / 1048576
    return {
        "processeur": modele_de_processeur,
        "coeurs_visibles": os.cpu_count(),
        "memoire_disponible_go": round(memoire_disponible_go, 1),
        "vnni_ou_amx": [n for n in ("avx512_vnni", "avx_vnni", "amx_int8") if n in drapeaux] or None,
        "systeme": platform.platform(),
        "etat_de_la_stack": etat_de_la_stack,
    }


def mesurer_la_duree_audio(chemin_audio):
    sortie = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", chemin_audio],
        capture_output=True, text=True, check=True,
    )
    return float(sortie.stdout.strip())


def envoyer_le_fichier(url, chemin_audio, format_demande, avec_diarisation, delai_maximum):
    """
    Poste le fichier en multipart, a la main.
    / Posts the file as multipart, by hand.

    On n'utilise ni `requests` ni le client OpenAI : le banc doit tourner dans
    une image minimale, et une dependance de plus est une friction de plus a
    porter d'une machine a l'autre.
    / No `requests`, no OpenAI client: the benchmark must run in a minimal image.
    """
    frontiere = f"----banc{uuid.uuid4().hex}"
    champs = [("model", "whisper-1"), ("response_format", format_demande)]
    if avec_diarisation:
        champs += [("diarize", "true"), ("timestamps", "true")]

    corps = b""
    for nom, valeur in champs:
        corps += (f"--{frontiere}\r\n"
                  f'Content-Disposition: form-data; name="{nom}"\r\n\r\n{valeur}\r\n').encode()
    with open(chemin_audio, "rb") as fichier_audio:
        contenu = fichier_audio.read()
    corps += (f"--{frontiere}\r\n"
              f'Content-Disposition: form-data; name="file"; '
              f'filename="{os.path.basename(chemin_audio)}"\r\n'
              f"Content-Type: audio/wav\r\n\r\n").encode() + contenu + b"\r\n"
    corps += f"--{frontiere}--\r\n".encode()

    requete = urllib.request.Request(
        f"{url.rstrip('/')}/v1/audio/transcriptions", data=corps,
        headers={"Content-Type": f"multipart/form-data; boundary={frontiere}"},
    )
    with urllib.request.urlopen(requete, timeout=delai_maximum) as reponse:
        return reponse.read().decode("utf-8", errors="replace")


def convertir_en_segments(reponse_brute):
    """
    Ramene la reponse du serveur a la forme du banc : {debut, fin, locuteur, texte}.
    / Normalises the server response to the benchmark shape.

    Trois formes possibles, dans l'ordre ou on les essaie :
    1. `verbose_json` avec des segments — le cas ordinaire ;
    2. du JSON qui ne porte que `text` — pas d'horodatage, un seul segment ;
    3. du texte brut.

    Quand le serveur prefixe le texte par « Speaker 1: », on en fait des
    locuteurs : c'est ce que rend `loudpage/parakeet-v3-diarized`.
    / When the server prefixes text with "Speaker 1:", we turn that into speakers.
    """
    try:
        reponse = json.loads(reponse_brute)
    except json.JSONDecodeError:
        return [{"debut": 0.0, "fin": 0.0, "locuteur": "SPEAKER_00",
                 "texte": reponse_brute.strip()}], reponse_brute.strip()

    texte_complet = reponse.get("text", "") if isinstance(reponse, dict) else ""
    segments_bruts = reponse.get("segments") if isinstance(reponse, dict) else None

    if segments_bruts:
        segments = []
        for segment in segments_bruts:
            texte_du_segment = (segment.get("text") or "").strip()
            # « Speaker 2: bonjour » -> locuteur SPEAKER_02, texte « bonjour »
            correspondance = re.match(r"^\s*Speaker\s+(\d+)\s*:\s*(.*)$", texte_du_segment,
                                      flags=re.IGNORECASE | re.DOTALL)
            if correspondance:
                locuteur = f"SPEAKER_{int(correspondance.group(1)):02d}"
                texte_du_segment = correspondance.group(2).strip()
            else:
                locuteur = segment.get("speaker") or "SPEAKER_00"
            segments.append({
                "debut": float(segment.get("start", 0.0)),
                "fin": float(segment.get("end", 0.0)),
                "locuteur": str(locuteur),
                "texte": texte_du_segment,
            })
        return segments, texte_complet or " ".join(s["texte"] for s in segments)

    return [{"debut": 0.0, "fin": 0.0, "locuteur": "SPEAKER_00", "texte": texte_complet}], texte_complet


def main():
    arguments = lire_les_arguments()
    duree_audio = mesurer_la_duree_audio(arguments.audio)
    nom_de_la_pile = arguments.nom_de_la_pile or arguments.url

    print("=" * 62)
    print(f"SERVEUR COMPATIBLE WHISPER : {nom_de_la_pile}")
    print(f"audio     : {arguments.audio} ({duree_audio:.1f} s)")
    print(f"diarisation demandee : {arguments.diarisation}")
    print("=" * 62)

    debut_de_l_appel = time.perf_counter()
    reponse_brute = envoyer_le_fichier(
        arguments.url, arguments.audio, arguments.format,
        arguments.diarisation, arguments.delai_maximum,
    )
    temps_de_l_appel = time.perf_counter() - debut_de_l_appel

    segments, texte_complet = convertir_en_segments(reponse_brute)
    locuteurs = sorted({segment["locuteur"] for segment in segments})

    print(f"\nappel HTTP complet  : {temps_de_l_appel:.2f} s "
          f"(RTFx {duree_audio / temps_de_l_appel:.1f}x, bout en bout)")
    print(f"segments            : {len(segments)}")
    print(f"locuteurs           : {len(locuteurs)} -> {locuteurs}")
    print(f"caracteres          : {len(texte_complet)}")
    if len(locuteurs) <= 1:
        print("  NOTE : un seul locuteur — cette pile ne diarise pas, "
              "elle ne peut pas repondre au critere 1.")

    resultat = {
        "moteur_asr": nom_de_la_pile,
        "moteur_diarisation": nom_de_la_pile if len(locuteurs) > 1 else "aucun",
        "type": "serveur HTTP compatible Whisper",
        "machine": decrire_la_machine(arguments.etat_de_la_stack),
        "audio": arguments.audio,
        "duree_audio_s": round(duree_audio, 2),
        "appel_http_bout_en_bout_s": round(temps_de_l_appel, 2),
        "locuteurs_detectes": len(locuteurs),
        "texte_brut": texte_complet,
        "segments": segments,
    }
    chemin_du_resultat = f"resultat_{arguments.etiquette}.json"
    with open(chemin_du_resultat, "w", encoding="utf-8") as fichier:
        json.dump(resultat, fichier, ensure_ascii=False, indent=1)
    print(f"\nresultat ecrit dans {chemin_du_resultat}")


if __name__ == "__main__":
    main()
