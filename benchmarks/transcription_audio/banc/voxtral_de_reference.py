#!/usr/bin/env python3
"""
Produit la base de comparaison Voxtral, sur le MEME extrait que les voies locales.
/ Produces the Voxtral baseline, on the SAME extract as the local paths.

LOCALISATION : benchmarks/transcription_audio/banc/voxtral_de_reference.py

POURQUOI CE SCRIPT EXISTE. Le critere 2 de la spec (§ 8) demande si le WER local
tient la comparaison avec ce que rend Voxtral aujourd'hui. Rien dans le depot ne
fournit ce chiffre : il faut appeler l'API une fois, sur le meme extrait, et
passer sa sortie dans le meme `comparer.py`.

CET APPEL EST FACTURE — 0,003 $/min d'audio (`core/models.py:1141`). Il ne se
relance pas pour rien : si le fichier de sortie existe deja, le script s'arrete.

CE SCRIPT S'EXECUTE DANS LE CONTENEUR `web`, pas dans celui du banc : il a besoin
de Django et de `front/services/transcription_audio.py`.
/ This script runs inside the `web` container: it needs Django.

Usage (depuis l'hote) :
    docker cp voxtral_de_reference.py hypostasia_web:/tmp/
    docker cp audio/extrait_0_900s.wav hypostasia_web:/tmp/
    docker exec hypostasia_web python /tmp/voxtral_de_reference.py \\
        /tmp/extrait_0_900s.wav /tmp/resultat_voxtral.json
"""
import json
import os
import sys
import time

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
django.setup()


def main():
    chemin_audio = sys.argv[1] if len(sys.argv) > 1 else "/tmp/extrait_0_900s.wav"
    chemin_sortie = sys.argv[2] if len(sys.argv) > 2 else "/tmp/resultat_voxtral.json"

    # L'appel est facture : on ne le relance jamais par accident.
    # / The call is billed: never re-run it by accident.
    if os.path.exists(chemin_sortie):
        print(f"{chemin_sortie} existe deja — rien n'est appele. Supprimer le fichier "
              f"pour refacturer un appel.")
        return

    from core.models import TranscriptionConfig
    from front.services.transcription_audio import (
        calculer_duree_audio, transcrire_audio_via_voxtral,
    )

    config_de_transcription = TranscriptionConfig.objects.first()
    duree_audio = calculer_duree_audio(chemin_audio)
    print(f"audio  : {chemin_audio} ({duree_audio:.1f} s)")
    print(f"modele : {config_de_transcription.model_name} "
          f"(diarisation : {config_de_transcription.diarization_enabled}, "
          f"max_speakers : {config_de_transcription.max_speakers})")
    print(f"cout attendu : {duree_audio / 60 * 0.003:.4f} $")

    debut_de_l_appel = time.perf_counter()
    reponse_de_l_api = transcrire_audio_via_voxtral(
        chemin_audio,
        config_de_transcription,
        max_locuteurs=config_de_transcription.max_speakers,
    )
    temps_de_l_appel = time.perf_counter() - debut_de_l_appel
    print(f"appel termine en {temps_de_l_appel:.1f} s")

    # Conversion au format que `comparer.py` sait lire : il attend `texte_brut`,
    # `locuteurs_detectes`, et des segments a clefs francaises.
    # / Conversion to the format `comparer.py` reads.
    segments_de_l_api = reponse_de_l_api.get("segments") or []
    segments_convertis = []
    for segment in segments_de_l_api:
        nom_du_locuteur = segment.get("speaker") or segment.get("speaker_id") or "INCONNU"
        segments_convertis.append({
            "debut": segment.get("start", 0.0),
            "fin": segment.get("end", 0.0),
            "locuteur": str(nom_du_locuteur),
            "texte": segment.get("text", ""),
        })

    locuteurs_distincts = {segment["locuteur"] for segment in segments_convertis}
    resultat = {
        "moteur": "Voxtral (API Mistral)",
        "modele": reponse_de_l_api.get("model", config_de_transcription.model_name),
        "duree_audio_s": round(duree_audio, 2),
        "appel_api_s": round(temps_de_l_appel, 2),
        "cout_dollars": round(duree_audio / 60 * 0.003, 4),
        "locuteurs_detectes": len(locuteurs_distincts),
        "texte_brut": reponse_de_l_api.get("text", ""),
        "segments": segments_convertis,
    }
    with open(chemin_sortie, "w", encoding="utf-8") as fichier_de_sortie:
        json.dump(resultat, fichier_de_sortie, ensure_ascii=False, indent=1)

    print(f"locuteurs detectes : {len(locuteurs_distincts)} -> {sorted(locuteurs_distincts)}")
    print(f"segments           : {len(segments_convertis)}")
    print(f"caracteres         : {len(resultat['texte_brut'])}")
    print(f"resultat ecrit dans {chemin_sortie}")


if __name__ == "__main__":
    main()
