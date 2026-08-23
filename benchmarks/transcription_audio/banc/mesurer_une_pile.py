#!/usr/bin/env python3
"""
Le pilote du banc : un ASR fixe, un diariseur INTERCHANGEABLE.
/ The benchmark driver: one fixed ASR, one INTERCHANGEABLE diarizer.

LOCALISATION : benchmarks/transcription_audio/banc/mesurer_une_pile.py

POURQUOI UN SEUL PILOTE. Ce qui separe les candidats, c'est la diarisation —
pas la transcription. Si chaque candidat apportait son propre ASR, son propre
alignement et son propre regroupement, on comparerait des chaines entieres et
on ne saurait jamais d'ou vient l'ecart. Ici l'ASR, l'alignement mot a mot, le
marquage INCONNU et le regroupement sont les MEMES pour tous : seule la
fonction de diarisation change.
/ One driver: same ASR, same alignment, same grouping — only the diarizer changes.

LES DIARISEURS DISPONIBLES :

| --diariseur | ce que c'est | token HuggingFace |
|---|---|---|
| `diarize` | Silero VAD + WeSpeaker ResNet34-LM + GMM/BIC + spectral | non |
| `sherpa` | segmentation pyannote 3.0 en ONNX + CAM++ + clustering | **non** |
| `pyannote` | `speaker-diarization-3.1`, marque **legacy** en amont | **OUI** |
| `pyannote-community` | `speaker-diarization-community-1`, le pipeline courant | **OUI** + conditions |

`sherpa` et `pyannote` partagent le meme modele de segmentation : le premier
l'execute en ONNX sans rien demander, le second passe par PyTorch et exige un
jeton plus l'acceptation de conditions sur un site tiers. Le critere 4 de la
spec compte ce cout, et c'est pour le mesurer qu'ils sont tous les deux la.

LES CINQ PIEGES DU COLLAGE, et comment ils sont traites :

- **Le decoupage aveugle detruit la transcription.** Parakeet TDT v3 nourri par
  blocs de 240 s rend un charabia franco-anglais et perd les trois quarts du
  texte ; nourri par segments de parole, il rend du francais correct. Le VAD
  n'est pas un confort, c'est la condition de fonctionnement.
- **Les horodatages rendus par onnx-asr sont RELATIFS au segment VAD.** Sans
  ajouter `segment.start`, l'attribution est fausse des le deuxieme segment.
- **L'unite d'alignement est le mot, et son POINT MILIEU.** Aligner sur le debut
  ferait basculer de locuteur tout mot a cheval sur une frontiere de tour.
- **Un mot que aucun tour ne recouvre est INCONNU**, jamais donne au voisin.
  Ce taux est un resultat, pas un detail.
- **Le taux d'INCONNU ne detecte PAS le depassement du plafond de locuteurs**
  (spec § 4.5) : mesure le 22 aout 2026, il vaut 0,0 % pendant qu'une pile perd
  un locuteur entier. Il ne peut pas servir de garde-fou.

Usage :
    python3 mesurer_une_pile.py --audio audio/extrait.wav --modeles ./hf-parakeet \\
        --diariseur sherpa --etiquette t1-sherpa \\
        --etat-de-la-stack "workers Celery au repos"
"""
import argparse
import json
import os
import platform
import subprocess
import time


def lire_les_arguments():
    """
    Tous les parametres sont des arguments : le banc doit se rejouer a
    l'identique sur une autre machine.
    / Every parameter is an argument: the benchmark must replay identically elsewhere.
    """
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--audio", required=True,
                           help="fichier WAV 16 kHz mono a transcrire")
    analyseur.add_argument("--modeles", required=True,
                           help="dossier contenant les fichiers ONNX de Parakeet")
    analyseur.add_argument("--diariseur", default="diarize",
                           choices=["diarize", "sherpa", "pyannote", "pyannote-community", "aucun"],
                           help="quel etage de diarisation mesurer")
    analyseur.add_argument("--quantification", default="int8", choices=["int8", "fp32"])
    analyseur.add_argument("--min-locuteurs", type=int, default=1)
    analyseur.add_argument("--max-locuteurs", type=int, default=8)
    analyseur.add_argument("--duree-max-de-parole", type=float, default=20.0,
                           help="duree maximale d'un segment VAD, en secondes")
    analyseur.add_argument("--modeles-sherpa", default="./modeles_sherpa",
                           help="dossier des modeles ONNX de sherpa-onnx")
    analyseur.add_argument("--embedding-sherpa",
                           default="3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx",
                           help="extracteur d'empreintes de sherpa-onnx. "
                                "`wespeaker_en_voxceleb_resnet34_LM.onnx` est CELUI de "
                                "pyannote 3.1 : avec la segmentation pyannote deja en "
                                "ONNX, sherpa reproduit alors le pipeline officiel "
                                "sans jeton ni conditions")
    analyseur.add_argument("--seuil-sherpa", type=float, default=0.5,
                           help="seuil de clustering de sherpa-onnx. C'est LE parametre "
                                "qui decide du nombre de locuteurs quand on ne le connait "
                                "pas d'avance : trop bas, il en invente")
    analyseur.add_argument("--etiquette", default="pile",
                           help="suffixe des fichiers de sortie")
    analyseur.add_argument("--etat-de-la-stack", required=True,
                           help="ce que faisait la machine pendant la mesure "
                                "(un RTFx sans son contexte ne veut rien dire)")
    analyseur.add_argument("--sans-asr", action="store_true",
                           help="ne mesurer QUE la diarisation, sans charger l'ASR — "
                                "c'est le seul moyen d'isoler le pic memoire du diariseur")
    analyseur.add_argument("--forme-produit", action="store_true",
                           help="ecrit aussi la forme {speaker,start,end,text} "
                                "que construire_html_diarise() consomme")
    return analyseur.parse_args()


def decrire_la_machine(etat_de_la_stack):
    """
    Rend la carte d'identite de la machine de mesure.
    / Returns the identity card of the measuring machine.

    Un RTFx sans sa machine ne veut rien dire, et deux chiffres de deux machines
    dans un meme tableau sans colonne « machine » sont un piege.
    """
    modele_de_processeur = "inconnu"
    drapeaux_du_processeur = ""
    with open("/proc/cpuinfo", encoding="utf-8") as fichier_cpuinfo:
        for ligne in fichier_cpuinfo:
            if ligne.startswith("model name") and modele_de_processeur == "inconnu":
                modele_de_processeur = ligne.split(":", 1)[1].strip()
            if ligne.startswith("flags") and not drapeaux_du_processeur:
                drapeaux_du_processeur = ligne.split(":", 1)[1]

    memoire_disponible_go = 0.0
    with open("/proc/meminfo", encoding="utf-8") as fichier_meminfo:
        for ligne in fichier_meminfo:
            if ligne.startswith("MemAvailable"):
                memoire_disponible_go = int(ligne.split()[1]) / 1048576

    # Sans VNNI ni AMX, les gains INT8 publies ne sont pas atteignables : le
    # chiffre mesure ici est un plancher, pas un verdict sur la pile.
    jeux_d_instructions = [nom for nom in ("avx512_vnni", "avx_vnni", "amx_int8", "amx_bf16")
                           if nom in drapeaux_du_processeur]

    return {
        "processeur": modele_de_processeur,
        "coeurs_visibles": os.cpu_count(),
        "memoire_disponible_go": round(memoire_disponible_go, 1),
        "vnni_ou_amx": jeux_d_instructions or None,
        "systeme": platform.platform(),
        "etat_de_la_stack": etat_de_la_stack,
    }


def mesurer_la_duree_audio(chemin_audio):
    """Duree du fichier, par ffprobe. / File duration, via ffprobe."""
    sortie_de_ffprobe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", chemin_audio],
        capture_output=True, text=True, check=True,
    )
    return float(sortie_de_ffprobe.stdout.strip())


# ---------------------------------------------------------------------------
# LES DIARISEURS. Chacun rend la MEME chose : une liste de tours de parole
# {debut, fin, locuteur}, plus le nom de ce qui a tourne.
# / Each diarizer returns the SAME thing: a list of turns, plus its own name.
#
# CHARGEMENT DE L'AUDIO, ET EQUITE DE LA MESURE. pyannote 4.x refuse un chemin
# de fichier sans `torchcodec` installe, et demande alors l'audio en memoire.
# On le lui donne — mais on charge le fichier A L'INTERIEUR du chrono, comme
# `diarize` et `sherpa` le font pour eux-memes. Pre-charger hors chrono
# offrirait a pyannote un decodage gratuit que les autres paient.
# / pyannote 4.x needs in-memory audio; we load it INSIDE the timer so that no
# diarizer gets a free decode the others pay for.
# ---------------------------------------------------------------------------


def charger_le_wav_en_memoire(chemin_audio):
    """
    Lit un WAV 16 kHz mono et rend un tenseur (canal, temps) en float32.
    / Reads a 16 kHz mono WAV and returns a (channel, time) float32 tensor.
    """
    import numpy as np
    import torch
    import wave

    with wave.open(chemin_audio) as fichier_wav:
        frequence = fichier_wav.getframerate()
        echantillons_bruts = fichier_wav.readframes(fichier_wav.getnframes())
    echantillons = np.frombuffer(echantillons_bruts, dtype=np.int16).astype(np.float32) / 32768
    return torch.from_numpy(echantillons.copy()).unsqueeze(0), frequence
# ---------------------------------------------------------------------------

def diariser_avec_diarize(arguments):
    """
    FoxNoseTech/diarize : Silero VAD -> WeSpeaker ResNet34-LM -> GMM/BIC ->
    clustering spectral. Aucun token. Ne modelise PAS la parole superposee.
    / No token. Does NOT model overlapping speech.
    """
    from diarize import diarize

    resultat = diarize(
        arguments.audio,
        min_speakers=arguments.min_locuteurs,
        max_speakers=arguments.max_locuteurs,
    )
    tours = [{"debut": segment.start, "fin": segment.end, "locuteur": segment.speaker}
             for segment in resultat.segments]
    return tours, "diarize (WeSpeaker ResNet34-LM + spectral)"


def diariser_avec_sherpa(arguments):
    """
    sherpa-onnx : la MEME segmentation pyannote 3.0 que le pipeline officiel,
    mais executee en ONNX, plus un extracteur d'empreintes CAM++.
    **Aucun token, aucune condition a accepter.**
    / Same pyannote 3.0 segmentation as the official pipeline, run in ONNX.

    `num_clusters = -1` laisse le clustering decider du nombre de locuteurs a
    partir d'un seuil : c'est le mode qu'il faut mesurer, puisque c'est celui
    ou l'on ne connait pas le nombre de voix a l'avance.
    / num_clusters = -1 lets the clustering decide, which is the case we care about.
    """
    import numpy as np
    import sherpa_onnx
    import wave

    dossier = arguments.modeles_sherpa
    configuration = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=f"{dossier}/sherpa-onnx-pyannote-segmentation-3-0/model.onnx"),
            num_threads=1,
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=f"{dossier}/{arguments.embedding_sherpa}",
            num_threads=1,
        ),
        # `num_clusters = -1` laisse le SEUIL decider du nombre de locuteurs.
        # Mesure du 23 aout 2026 : a 0,5 il en rend 15 a 24 pour 4 reels. Ce
        # parametre ne se devine pas — il se balaie, et il depend de l'extracteur
        # d'empreintes autant que de l'audio.
        # / The threshold decides the speaker count; at 0.5 it invented 15 to 24.
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1,
                                                    threshold=arguments.seuil_sherpa),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not configuration.validate():
        raise RuntimeError("Configuration sherpa-onnx invalide : verifier les chemins de modeles.")

    diariseur = sherpa_onnx.OfflineSpeakerDiarization(configuration)

    with wave.open(arguments.audio) as fichier_wav:
        echantillons_bruts = fichier_wav.readframes(fichier_wav.getnframes())
    echantillons = np.frombuffer(echantillons_bruts, dtype=np.int16).astype(np.float32) / 32768

    resultat = diariseur.process(echantillons).sort_by_start_time()
    tours = [{"debut": segment.start, "fin": segment.end, "locuteur": f"SPEAKER_{segment.speaker:02d}"}
             for segment in resultat]
    nom_court_de_l_extracteur = arguments.embedding_sherpa.replace(".onnx", "")
    return tours, (f"sherpa-onnx (segmentation pyannote 3.0 ONNX + "
                   f"{nom_court_de_l_extracteur}, seuil {arguments.seuil_sherpa})")


def diariser_avec_pyannote(arguments):
    """
    Le pipeline officiel `pyannote/speaker-diarization-3.1`, sur PyTorch.
    / The official pipeline, on PyTorch.

    **Le jeton est lu dans l'environnement, JAMAIS ecrit dans ce fichier.** Un
    script est fait pour etre versionne : un secret ecrit dedans finit pousse
    sur la forge au premier `git add -A` distrait.
    / The token is read from the environment, NEVER written in this file.
    """
    import torch
    from pyannote.audio import Pipeline

    jeton = os.environ.get("HF_TOKEN_DIARIZATION", "")
    if not jeton:
        raise SystemExit(
            "HF_TOKEN_DIARIZATION absent de l'environnement du conteneur.\n"
            "env_file est lu au DEMARRAGE : recreer le conteneur avec "
            "--env-file, ne pas passer le jeton en argument de ligne de commande."
        )

    # LE JETON PASSE PAR L'ENVIRONNEMENT, jamais par un argument. Deux raisons :
    # `huggingface_hub` lit `HF_TOKEN` tout seul, et les noms d'arguments ont
    # change trois fois (`use_auth_token=` en pyannote 3.x, `token=` en 4.x, et
    # `hf_hub_download()` a fini par refuser le premier). Passer par
    # l'environnement traverse ces trois versions sans rien casser.
    # / The token goes through the environment: huggingface_hub reads HF_TOKEN
    # by itself, and the argument names changed three times across versions.
    os.environ.setdefault("HF_TOKEN", jeton)
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
    pipeline.to(torch.device("cpu"))

    # Meme mode d'entree que community-1 : sans cela, les deux versions de
    # pyannote ne seraient pas comparables entre elles.
    # / Same input mode as community-1, so both versions stay comparable.
    forme_d_onde, frequence = charger_le_wav_en_memoire(arguments.audio)
    annotation = pipeline(
        {"waveform": forme_d_onde, "sample_rate": frequence},
        min_speakers=arguments.min_locuteurs,
        max_speakers=arguments.max_locuteurs,
    )
    tours = [{"debut": tour.start, "fin": tour.end, "locuteur": locuteur}
             for tour, _, locuteur in annotation.itertracks(yield_label=True)]
    return tours, "pyannote 3.1 (PyTorch, jeton HuggingFace requis)"


def diariser_avec_pyannote_community(arguments):
    """
    `pyannote/speaker-diarization-community-1`, sur pyannote.audio 4.x.
    / The pipeline pyannote recommends today.

    C'EST LE PIPELINE COURANT, et `speaker-diarization-3.1` est desormais
    marque **legacy** par la documentation officielle. Les deux sont mesures :
    sans cela, un chiffre de 2024 passerait pour l'etat de l'art.
    / This is the current pipeline; 3.1 is now labelled legacy upstream.

    L'ACCES SE VERIFIE SUR UN FICHIER, PAS SUR LE DEPOT. L'API des metadonnees
    de `community-1` rend 200 meme quand les poids sont refuses en 403 : seul
    l'utilisateur ayant accepte les conditions du depot peut les telecharger.
    / Access must be checked on a FILE: the metadata API answers 200 even when
    the weights are refused with 403.
    """
    import torch
    from pyannote.audio import Pipeline

    jeton = os.environ.get("HF_TOKEN_DIARIZATION", "")
    if not jeton:
        raise SystemExit(
            "HF_TOKEN_DIARIZATION absent de l'environnement du conteneur.\n"
            "env_file est lu au DEMARRAGE : recreer le conteneur avec "
            "--env-file, ne pas passer le jeton en argument de ligne de commande."
        )
    os.environ.setdefault("HF_TOKEN", jeton)

    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1")
    pipeline.to(torch.device("cpu"))

    forme_d_onde, frequence = charger_le_wav_en_memoire(arguments.audio)
    sortie = pipeline(
        {"waveform": forme_d_onde, "sample_rate": frequence},
        min_speakers=arguments.min_locuteurs,
        max_speakers=arguments.max_locuteurs,
    )
    # pyannote 4.x rend un objet a plusieurs pistes ; la diarisation est dans
    # `.speaker_diarization`. La 3.x rendait l'Annotation directement.
    # / pyannote 4.x returns a multi-track output; 3.x returned the Annotation.
    annotation = getattr(sortie, "speaker_diarization", sortie)
    tours = [{"debut": tour.start, "fin": tour.end, "locuteur": str(locuteur)}
             for tour, _, locuteur in annotation.itertracks(yield_label=True)]
    return tours, "pyannote community-1 (pyannote.audio 4.x, jeton + conditions)"


DIARISEURS = {
    "diarize": diariser_avec_diarize,
    "sherpa": diariser_avec_sherpa,
    "pyannote": diariser_avec_pyannote,
    "pyannote-community": diariser_avec_pyannote_community,
}


# ---------------------------------------------------------------------------
# L'ALIGNEMENT — identique pour tous les diariseurs.
# ---------------------------------------------------------------------------

def reconstruire_les_mots(segments_de_parole):
    """
    Reconstruit des mots horodates a partir des sous-mots rendus par l'ASR.
    / Rebuilds timestamped words from the sub-word tokens returned by the ASR.

    onnx-asr rend des tokens SentencePiece : un nouveau mot commence a chaque
    token qui debute par une espace. Le timestamp d'un token est son DEBUT ;
    la fin d'un mot est donc le debut du mot suivant.

    ATTENTION : les timestamps sont RELATIFS au segment VAD. On y ajoute
    `segment.start` pour revenir au temps absolu du fichier.
    """
    mots_horodates = []

    for segment in segments_de_parole:
        decalage_du_segment = segment.start
        mot_en_cours = ""
        debut_du_mot_en_cours = None

        for token, horodatage_relatif in zip(segment.tokens, segment.timestamps):
            horodatage_absolu = decalage_du_segment + horodatage_relatif
            commence_un_nouveau_mot = token.startswith(" ")

            if commence_un_nouveau_mot and mot_en_cours.strip():
                mots_horodates.append({
                    "texte": mot_en_cours.strip(),
                    "debut": debut_du_mot_en_cours,
                    "fin": horodatage_absolu,
                })
                mot_en_cours = ""
                debut_du_mot_en_cours = None

            if debut_du_mot_en_cours is None:
                debut_du_mot_en_cours = horodatage_absolu
            mot_en_cours += token

        # Le dernier mot du segment se termine a la fin du segment
        if mot_en_cours.strip():
            mots_horodates.append({
                "texte": mot_en_cours.strip(),
                "debut": debut_du_mot_en_cours,
                "fin": segment.end,
            })

    return mots_horodates


def attribuer_les_mots_aux_locuteurs(mots_horodates, tours_de_parole):
    """
    Attribue chaque mot au tour de parole qui recouvre son POINT MILIEU.
    / Assigns each word to the speaker turn covering its MIDPOINT.

    Un mot que AUCUN tour ne recouvre reste INCONNU : on ne le donne jamais au
    voisin le plus proche — ce serait fabriquer une preuve.
    / A word covered by no turn stays INCONNU: we never guess.
    """
    for mot in mots_horodates:
        point_milieu_du_mot = (mot["debut"] + mot["fin"]) / 2
        mot["locuteur"] = "INCONNU"

        for tour in tours_de_parole:
            if tour["debut"] <= point_milieu_du_mot <= tour["fin"]:
                mot["locuteur"] = tour["locuteur"]
                break

    return mots_horodates


def regrouper_en_segments(mots_attribues):
    """
    Regroupe les mots consecutifs de meme locuteur en un seul segment.
    / Groups consecutive words of the same speaker into one segment.
    """
    segments_regroupes = []

    for mot in mots_attribues:
        meme_locuteur_que_le_precedent = (
            segments_regroupes and segments_regroupes[-1]["locuteur"] == mot["locuteur"]
        )
        if meme_locuteur_que_le_precedent:
            segments_regroupes[-1]["texte"] += " " + mot["texte"]
            segments_regroupes[-1]["fin"] = mot["fin"]
        else:
            segments_regroupes.append({
                "debut": mot["debut"], "fin": mot["fin"],
                "locuteur": mot["locuteur"], "texte": mot["texte"],
            })

    return segments_regroupes


def main():
    arguments = lire_les_arguments()
    import onnx_asr

    duree_audio = mesurer_la_duree_audio(arguments.audio)
    print("=" * 62)
    print(f"PILE : onnx-asr ({arguments.quantification}) + diariseur « {arguments.diariseur} »")
    print(f"audio     : {arguments.audio} ({duree_audio:.1f} s)")
    print(f"etiquette : {arguments.etiquette}")
    print("=" * 62)

    # ---------- Chargement des modeles (hors mesure d'inference) ----------
    # AVEC --sans-asr, ON NE CHARGE RIEN DE L'ASR. Le pic RSS releve par
    # `/usr/bin/time -v` porte sur le PROCESSUS ENTIER : tant que Parakeet est
    # en memoire a cote, on mesure la somme des deux et non le diariseur. C'est
    # le seul moyen de comparer honnetement la memoire de deux diariseurs.
    # / With --sans-asr nothing of the ASR is loaded: peak RSS covers the whole
    # process, so the ASR would otherwise be counted in the diarizer's figure.
    detecteur_de_parole = None
    modele_de_transcription = None
    temps_de_chargement = 0.0
    if not arguments.sans_asr:
        debut_du_chargement = time.perf_counter()
        detecteur_de_parole = onnx_asr.load_vad("silero")
        modele_de_transcription = onnx_asr.load_model(
            "nemo-parakeet-tdt-0.6b-v3", arguments.modeles,
            quantization=None if arguments.quantification == "fp32" else "int8",
        )
        temps_de_chargement = time.perf_counter() - debut_du_chargement
        print(f"\nchargement de l'ASR : {temps_de_chargement:.2f} s")
    else:
        print("\nASR NON CHARGE (--sans-asr) : on ne mesure que la diarisation.")

    # ---------- Etape 1 : diarisation, sur l'audio ENTIER ----------
    print(f"\n### ETAPE 1 — DIARISATION ({arguments.diariseur})")
    tours_de_parole, nom_du_diariseur = [], "aucun"
    temps_de_diarisation = 0.0

    if arguments.diariseur != "aucun":
        debut_de_la_diarisation = time.perf_counter()
        tours_de_parole, nom_du_diariseur = DIARISEURS[arguments.diariseur](arguments)
        temps_de_diarisation = time.perf_counter() - debut_de_la_diarisation

        locuteurs_distincts = sorted({tour["locuteur"] for tour in tours_de_parole})
        print(f"moteur              : {nom_du_diariseur}")
        print(f"inference           : {temps_de_diarisation:.2f} s "
              f"(RTFx {duree_audio / max(temps_de_diarisation, 1e-9):.1f}x)")
        print(f"tours de parole     : {len(tours_de_parole)}")
        print(f"locuteurs detectes  : {len(locuteurs_distincts)} -> {locuteurs_distincts}")

        temps_par_locuteur = {}
        for tour in tours_de_parole:
            temps_par_locuteur.setdefault(tour["locuteur"], 0.0)
            temps_par_locuteur[tour["locuteur"]] += tour["fin"] - tour["debut"]
        for nom, secondes in sorted(temps_par_locuteur.items(), key=lambda paire: -paire[1]):
            print(f"  {nom} : {secondes:.1f} s ({100 * secondes / duree_audio:.1f} %)")

    # ---------- Etape 2 : transcription, par segments de parole ----------
    if arguments.sans_asr:
        segments_attribues, mots_attribues, segments_de_parole = [], [], []
        temps_de_transcription = 0.0
        texte_complet = ""
        nombre_de_mots_inconnus, taux_de_mots_inconnus = 0, 0.0
        print("\n### ETAPE 2 — TRANSCRIPTION : ignoree (--sans-asr)")
        print("### ETAPE 3 — ATTRIBUTION : sans objet, il n'y a pas de mots a attribuer")
    else:
        print("\n### ETAPE 2 — TRANSCRIPTION (Parakeet TDT v3, segments du VAD)")
        debut_de_la_transcription = time.perf_counter()
        # `recognize` rend un generateur paresseux : on le materialise DANS le chrono,
        # sinon on mesurerait zero seconde.
        segments_de_parole = list(
            modele_de_transcription
            .with_vad(detecteur_de_parole, max_speech_duration_s=arguments.duree_max_de_parole)
            .with_timestamps()
            .recognize(arguments.audio)
        )
        temps_de_transcription = time.perf_counter() - debut_de_la_transcription
        print(f"inference           : {temps_de_transcription:.2f} s "
              f"(RTFx {duree_audio / temps_de_transcription:.1f}x)")
        print(f"segments de parole  : {len(segments_de_parole)}")

        # ---------- Etape 3 : alignement mot a mot ----------
        print("\n### ETAPE 3 — ATTRIBUTION (point milieu de chaque mot)")
        mots_attribues = attribuer_les_mots_aux_locuteurs(
            reconstruire_les_mots(segments_de_parole), tours_de_parole,
        )
        segments_attribues = regrouper_en_segments(mots_attribues)

        nombre_de_mots_inconnus = sum(1 for mot in mots_attribues if mot["locuteur"] == "INCONNU")
        taux_de_mots_inconnus = (100 * nombre_de_mots_inconnus / len(mots_attribues)) if mots_attribues else 0.0
        print(f"mots horodates      : {len(mots_attribues)}")
        print(f"mots INCONNU        : {nombre_de_mots_inconnus} ({taux_de_mots_inconnus:.1f} %)")
        print(f"segments produits   : {len(segments_attribues)}")
        print("  ATTENTION : ce taux ne detecte PAS le depassement du plafond de locuteurs.")

        texte_complet = " ".join(mot["texte"] for mot in mots_attribues)
    locuteurs_distincts = sorted({tour["locuteur"] for tour in tours_de_parole})

    # ---------- Bilan et ecriture ----------
    temps_total_d_inference = temps_de_diarisation + temps_de_transcription
    print("\n### BILAN")
    print(f"duree audio            : {duree_audio:.1f} s")
    print(f"chargement de l'ASR    : {temps_de_chargement:.2f} s (hors inference)")
    print(f"diarisation            : {temps_de_diarisation:.2f} s")
    print(f"transcription          : {temps_de_transcription:.2f} s")
    print(f"inference totale       : {temps_total_d_inference:.2f} s")
    print(f"RTFx global            : {duree_audio / temps_total_d_inference:.1f}x le temps reel")
    print(f"=> pour 1 h d'audio    : {60 * temps_total_d_inference / duree_audio:.1f} min de calcul")

    resultat = {
        "moteur_asr": f"onnx-asr / Parakeet TDT v3 ({arguments.quantification})",
        "moteur_diarisation": nom_du_diariseur,
        "diariseur": arguments.diariseur,
        "quantification": arguments.quantification,
        "machine": decrire_la_machine(arguments.etat_de_la_stack),
        "audio": arguments.audio,
        "duree_audio_s": round(duree_audio, 2),
        "chargement_asr_s": round(temps_de_chargement, 2),
        "diarisation_s": round(temps_de_diarisation, 2),
        "transcription_s": round(temps_de_transcription, 2),
        "locuteurs_detectes": len(locuteurs_distincts),
        "mots_total": len(mots_attribues),
        "mots_inconnu": nombre_de_mots_inconnus,
        "taux_mots_inconnu_pourcent": round(taux_de_mots_inconnus, 2),
        "texte_brut": texte_complet,
        "segments": segments_attribues,
    }
    chemin_du_resultat = f"resultat_{arguments.etiquette}.json"
    with open(chemin_du_resultat, "w", encoding="utf-8") as fichier_de_sortie:
        json.dump(resultat, fichier_de_sortie, ensure_ascii=False, indent=1)
    print(f"\nresultat ecrit dans {chemin_du_resultat}")

    # La forme que le produit consomme deja : {speaker, start, end, text}
    # (front/services/transcription_audio.py:271).
    if arguments.forme_produit:
        segments_pour_le_produit = [
            {"speaker": segment["locuteur"], "start": segment["debut"],
             "end": segment["fin"], "text": segment["texte"]}
            for segment in segments_attribues
        ]
        chemin_forme_produit = f"forme_produit_{arguments.etiquette}.json"
        with open(chemin_forme_produit, "w", encoding="utf-8") as fichier_du_produit:
            json.dump(segments_pour_le_produit, fichier_du_produit,
                      ensure_ascii=False, indent=1)
        print(f"forme du produit ecrite dans {chemin_forme_produit}")


if __name__ == "__main__":
    main()
