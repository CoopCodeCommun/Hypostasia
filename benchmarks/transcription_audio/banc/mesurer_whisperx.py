#!/usr/bin/env python3
"""
Mesure WhisperX : Whisper + alignement wav2vec2 au mot + diarisation pyannote.
/ Measures WhisperX: Whisper + wav2vec2 word alignment + pyannote diarization.

LOCALISATION : benchmarks/transcription_audio/banc/mesurer_whisperx.py

POURQUOI CETTE PILE A SON PROPRE SCRIPT. Les autres candidats passent par
`mesurer_une_pile.py`, qui garde un ASR fixe et ne fait varier que le
diariseur. WhisperX ne se decoupe pas ainsi : c'est une chaine integree ou
l'ASR, l'alignement et la diarisation se passent des donnees dans un format qui
leur est propre. La mesurer avec le pilote reviendrait a la demonter — donc a
mesurer autre chose qu'elle.
/ WhisperX is an integrated chain: splitting it would measure something else.

CE QU'ELLE CHANGE PAR RAPPORT AU RESTE DU BANC, et qu'il faut savoir pour lire
le tableau :

- **L'ASR n'est pas le meme.** Toutes les autres lignes transcrivent avec
  Parakeet TDT v3 ; celle-ci avec Whisper. C'est la seule ou l'ASR varie, et le
  WER doit se lire en le sachant.
- **L'alignement est fait par un modele** (wav2vec2 force alignment), la ou
  notre collage aligne les horodatages du decodeur sur les tours de parole.
- **La diarisation est `pyannote/speaker-diarization-community-1`** — le meme
  pipeline que `--diariseur pyannote-community`, avec le meme jeton et les
  memes conditions a accepter.

LES TROIS ETAGES SONT CHRONOMETRES SEPAREMENT, comme dans le pilote : sans
cela, on ne saurait pas si le cout vient de Whisper, de l'alignement ou de la
diarisation.
/ The three stages are timed separately.

Usage :
    python3 mesurer_whisperx.py --audio audio/extrait.wav --modele large-v3 \\
        --etiquette T1-whisperx --etat-de-la-stack "workers Celery au repos"
"""
import argparse
import json
import os
import platform
import subprocess
import time


def lire_les_arguments():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--audio", required=True)
    analyseur.add_argument("--modele", default="large-v3",
                           help="modele Whisper : large-v3, medium, small...")
    analyseur.add_argument("--quantification", default="int8",
                           help="compute_type de CTranslate2 : int8, float32")
    analyseur.add_argument("--langue", default="fr",
                           help="code langue ; vide = detection automatique")
    analyseur.add_argument("--taille-de-lot", type=int, default=4,
                           help="batch_size de la transcription")
    analyseur.add_argument("--min-locuteurs", type=int, default=1)
    analyseur.add_argument("--max-locuteurs", type=int, default=8)
    analyseur.add_argument("--sans-diarisation", action="store_true",
                           help="mesurer l'ASR et l'alignement seuls")
    analyseur.add_argument("--etiquette", default="whisperx")
    analyseur.add_argument("--etat-de-la-stack", required=True)
    analyseur.add_argument("--forme-produit", action="store_true")
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


def regrouper_en_segments(segments_de_whisperx):
    """
    Ramene la sortie de WhisperX a la forme du banc, en regroupant les segments
    consecutifs de meme locuteur.
    / Normalises WhisperX output to the benchmark shape.

    Un segment sans locuteur reste INCONNU : WhisperX laisse le champ absent
    quand la diarisation ne recouvre pas le segment, et on ne le donne jamais au
    voisin — ce serait fabriquer une preuve.
    / A segment with no speaker stays INCONNU; we never guess.
    """
    segments_regroupes = []
    for segment in segments_de_whisperx:
        locuteur = segment.get("speaker") or "INCONNU"
        texte = (segment.get("text") or "").strip()
        if not texte:
            continue
        if segments_regroupes and segments_regroupes[-1]["locuteur"] == locuteur:
            segments_regroupes[-1]["texte"] += " " + texte
            segments_regroupes[-1]["fin"] = float(segment.get("end", 0.0))
        else:
            segments_regroupes.append({
                "debut": float(segment.get("start", 0.0)),
                "fin": float(segment.get("end", 0.0)),
                "locuteur": str(locuteur),
                "texte": texte,
            })
    return segments_regroupes


def main():
    arguments = lire_les_arguments()
    import whisperx

    duree_audio = mesurer_la_duree_audio(arguments.audio)
    print("=" * 62)
    print(f"WHISPERX — modele {arguments.modele} ({arguments.quantification}), CPU")
    print(f"audio     : {arguments.audio} ({duree_audio:.1f} s)")
    print(f"etiquette : {arguments.etiquette}")
    print("=" * 62)

    jeton = os.environ.get("HF_TOKEN_DIARIZATION", "")

    # ---------- Chargement (hors mesure d'inference) ----------
    debut_du_chargement = time.perf_counter()
    modele_whisper = whisperx.load_model(
        arguments.modele, device="cpu", compute_type=arguments.quantification,
        language=arguments.langue or None,
    )
    audio = whisperx.load_audio(arguments.audio)
    temps_de_chargement = time.perf_counter() - debut_du_chargement
    print(f"\nchargement du modele : {temps_de_chargement:.2f} s")

    # ---------- Etape 1 : transcription ----------
    print("\n### ETAPE 1 — TRANSCRIPTION (Whisper via faster-whisper)")
    debut = time.perf_counter()
    resultat = modele_whisper.transcribe(audio, batch_size=arguments.taille_de_lot)
    temps_de_transcription = time.perf_counter() - debut
    langue_detectee = resultat.get("language", arguments.langue)
    print(f"inference           : {temps_de_transcription:.2f} s "
          f"(RTFx {duree_audio / temps_de_transcription:.1f}x)")
    print(f"langue              : {langue_detectee}")
    print(f"segments            : {len(resultat.get('segments', []))}")

    # ---------- Etape 2 : alignement force au mot ----------
    print("\n### ETAPE 2 — ALIGNEMENT (wav2vec2, force alignment)")
    debut = time.perf_counter()
    modele_d_alignement, metadonnees = whisperx.load_align_model(
        language_code=langue_detectee, device="cpu",
    )
    resultat = whisperx.align(
        resultat["segments"], modele_d_alignement, metadonnees, audio, "cpu",
        return_char_alignments=False,
    )
    temps_d_alignement = time.perf_counter() - debut
    print(f"inference           : {temps_d_alignement:.2f} s "
          f"(RTFx {duree_audio / temps_d_alignement:.1f}x)")

    # ---------- Etape 3 : diarisation ----------
    temps_de_diarisation = 0.0
    nom_du_diariseur = "aucun"
    if not arguments.sans_diarisation:
        print("\n### ETAPE 3 — DIARISATION (pyannote community-1)")
        if not jeton:
            raise SystemExit(
                "HF_TOKEN_DIARIZATION absent : WhisperX diarise avec "
                "`pyannote/speaker-diarization-community-1`, qui exige un jeton "
                "et l'acceptation des conditions du depot."
            )
        os.environ.setdefault("HF_TOKEN", jeton)
        debut = time.perf_counter()
        # Le nom de la classe a change entre versions : `DiarizationPipeline`
        # dans les versions anciennes, `diarize.DiarizationPipeline` ensuite.
        # / The class moved between versions; try both names.
        fabrique = getattr(whisperx, "DiarizationPipeline", None)
        if fabrique is None:
            from whisperx.diarize import DiarizationPipeline as fabrique  # noqa: N813
        # Le nom de l'argument a change : `token=` en 3.8.x, `use_auth_token=`
        # avant. On essaie le nom courant, puis l'ancien.
        # / The argument was renamed: `token=` in 3.8.x, `use_auth_token=` before.
        try:
            diariseur = fabrique(token=jeton, device="cpu")
        except TypeError:
            diariseur = fabrique(use_auth_token=jeton, device="cpu")
        tours = diariseur(audio, min_speakers=arguments.min_locuteurs,
                          max_speakers=arguments.max_locuteurs)
        resultat = whisperx.assign_word_speakers(tours, resultat)
        temps_de_diarisation = time.perf_counter() - debut
        nom_du_diariseur = "pyannote community-1 (via WhisperX)"
        print(f"inference           : {temps_de_diarisation:.2f} s "
              f"(RTFx {duree_audio / temps_de_diarisation:.1f}x)")

    # ---------- Bilan ----------
    segments = regrouper_en_segments(resultat.get("segments", []))
    locuteurs = sorted({segment["locuteur"] for segment in segments} - {"INCONNU"})
    texte_complet = " ".join(segment["texte"] for segment in segments)
    mots_inconnus = sum(len(s["texte"].split()) for s in segments if s["locuteur"] == "INCONNU")
    total_des_mots = sum(len(s["texte"].split()) for s in segments)

    temps_total = temps_de_transcription + temps_d_alignement + temps_de_diarisation
    print("\n### BILAN")
    print(f"duree audio            : {duree_audio:.1f} s")
    print(f"chargement             : {temps_de_chargement:.2f} s (hors inference)")
    print(f"transcription          : {temps_de_transcription:.2f} s")
    print(f"alignement             : {temps_d_alignement:.2f} s")
    print(f"diarisation            : {temps_de_diarisation:.2f} s")
    print(f"inference totale       : {temps_total:.2f} s")
    print(f"RTFx global            : {duree_audio / temps_total:.1f}x le temps reel")
    print(f"=> pour 1 h d'audio    : {60 * temps_total / duree_audio:.1f} min de calcul")
    print(f"locuteurs detectes     : {len(locuteurs)} -> {locuteurs}")
    print(f"mots sans locuteur     : {mots_inconnus} / {total_des_mots}")

    resultat_a_ecrire = {
        "moteur_asr": f"WhisperX / Whisper {arguments.modele} ({arguments.quantification})",
        "moteur_diarisation": nom_du_diariseur,
        "diariseur": "pyannote-community" if not arguments.sans_diarisation else "aucun",
        "quantification": arguments.quantification,
        "machine": decrire_la_machine(arguments.etat_de_la_stack),
        "audio": arguments.audio,
        "duree_audio_s": round(duree_audio, 2),
        "chargement_asr_s": round(temps_de_chargement, 2),
        "transcription_s": round(temps_de_transcription + temps_d_alignement, 2),
        "alignement_s": round(temps_d_alignement, 2),
        "diarisation_s": round(temps_de_diarisation, 2),
        "locuteurs_detectes": len(locuteurs),
        "mots_total": total_des_mots,
        "mots_inconnu": mots_inconnus,
        "taux_mots_inconnu_pourcent": round(100 * mots_inconnus / total_des_mots, 2) if total_des_mots else 0.0,
        "langue_detectee": langue_detectee,
        "texte_brut": texte_complet,
        "segments": segments,
    }
    chemin = f"resultat_{arguments.etiquette}.json"
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(resultat_a_ecrire, fichier, ensure_ascii=False, indent=1)
    print(f"\nresultat ecrit dans {chemin}")

    if arguments.forme_produit:
        forme = [{"speaker": s["locuteur"], "start": s["debut"], "end": s["fin"], "text": s["texte"]}
                 for s in segments]
        with open(f"forme_produit_{arguments.etiquette}.json", "w", encoding="utf-8") as fichier:
            json.dump(forme, fichier, ensure_ascii=False, indent=1)
        print(f"forme du produit ecrite dans forme_produit_{arguments.etiquette}.json")


if __name__ == "__main__":
    main()
