/*
Banc d'essai : Parakeet TDT v3 (transcription) + Sortformer v2 (diarisation), CPU uniquement.
/ Benchmark: Parakeet TDT v3 (transcription) + Sortformer v2 (diarization), CPU only.

Difference avec examples/diarization.rs du depot :
  1. cet exemple DECOUPE l'audio pour TDT (le README previent que TDT plafonne
     autour de 4-5 minutes ; l'exemple officiel ne gere pas ce cas) ;
  2. l'attribution cumule le recouvrement PAR LOCUTEUR au lieu de comparer
     segment par segment.
Sortformer, lui, tourne sur l'integralite de l'audio d'un seul tenant puisqu'il
est nativement en streaming.
/ Differences with the repo's examples/diarization.rs: (1) this one CHUNKS the audio
for TDT; (2) attribution sums overlap PER SPEAKER instead of comparing segment by
segment. Sortformer runs on the whole audio at once since it is natively streaming.

Usage: bench <audio.wav> <dossier_tdt> <secondes_par_chunk> <sortie.json> [modele_sortformer]
*/

use parakeet_rs::sortformer::{DiarizationConfig, Sortformer};
use parakeet_rs::{ParakeetTDT, TimestampMode, Transcriber};
use std::collections::HashMap;
use std::env;
use std::fs::File;
use std::io::Write;
use std::time::Instant;

const TAUX_ECHANTILLONNAGE: u32 = 16_000;

/// Un morceau de transcription attribue a un locuteur
/// / A transcript chunk attributed to a speaker
struct SegmentAttribue {
    debut: f32,
    fin: f32,
    locuteur: String,
    texte: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let arguments: Vec<String> = env::args().collect();
    let chemin_audio = arguments.get(1)
        .expect("usage: bench <audio.wav> <dossier_tdt> <sec_par_chunk> <sortie.json> [sortformer.onnx]");
    let dossier_tdt = arguments.get(2).expect("dossier du modele TDT manquant");
    let secondes_par_chunk: f32 = arguments
        .get(3)
        .map(|valeur| valeur.parse().expect("le 3e argument doit etre un nombre de secondes"))
        .unwrap_or(240.0);
    let chemin_sortie = arguments.get(4).map(|s| s.as_str()).unwrap_or("resultat.json");
    // Passe en argument pour permettre d'essayer Ultra-Sortformer 5 ou 8 locuteurs
    // / Passed as an argument so Ultra-Sortformer 5/8-speaker can be tried
    let modele_sortformer = arguments
        .get(5)
        .map(|s| s.as_str())
        .unwrap_or("diar_streaming_sortformer_4spk-v2.onnx");

    // ---------- Lecture de l'audio / Read the audio ----------
    let mut lecteur = hound::WavReader::open(chemin_audio)?;
    let specification = lecteur.spec();

    // Le reste du programme suppose 16 kHz mono : le decoupage, le decalage et la
    // conversion des bornes de Sortformer utilisent la constante, pas l'en-tete du
    // fichier. Un WAV 44,1 kHz ou stereo donnerait des horodatages faux EN SILENCE.
    // / The rest assumes 16 kHz mono: chunking, offsets and Sortformer bounds use the
    // constant, not the file header. Another rate or channel count would be silently wrong.
    assert_eq!(
        specification.sample_rate, TAUX_ECHANTILLONNAGE,
        "audio attendu en 16 kHz — convertir avec ffmpeg -ar 16000"
    );
    assert_eq!(
        specification.channels, 1,
        "audio attendu en mono — convertir avec ffmpeg -ac 1"
    );

    let echantillons: Vec<f32> = match specification.sample_format {
        hound::SampleFormat::Float => lecteur.samples::<f32>().collect::<Result<Vec<_>, _>>()?,
        hound::SampleFormat::Int => lecteur
            .samples::<i16>()
            .map(|s| s.map(|s| s as f32 / 32768.0))
            .collect::<Result<Vec<_>, _>>()?,
    };
    assert!(!echantillons.is_empty(), "le fichier audio est vide");
    let duree_audio_secondes = echantillons.len() as f32 / TAUX_ECHANTILLONNAGE as f32;

    println!("### AUDIO");
    println!("fichier            : {}", chemin_audio);
    println!("echantillons       : {}", echantillons.len());
    println!("duree              : {:.1} s ({:.1} min)", duree_audio_secondes, duree_audio_secondes / 60.0);
    println!("modele TDT         : {}", dossier_tdt);
    println!("modele diarisation : {}", modele_sortformer);
    println!("decoupage TDT      : {:.0} s par morceau", secondes_par_chunk);
    println!();

    // ---------- Etape 1 : diarisation sur l'audio complet ----------
    println!("### ETAPE 1 — DIARISATION (Sortformer v2, audio entier)");
    let chrono_chargement_sortformer = Instant::now();
    // Prereglage callhome : c'est celui de l'exemple officiel. La crate offre aussi
    // dihard3(). CALLHOME est un corpus telephonique a deux voix, notre materiau est
    // une table ronde a quatre : essayer les deux si les resultats decoivent.
    // / callhome preset: the one from the official example. dihard3() also exists.
    let mut sortformer = Sortformer::with_config(
        modele_sortformer,
        None,
        DiarizationConfig::callhome(),
    )?;
    let temps_chargement_sortformer = chrono_chargement_sortformer.elapsed().as_secs_f32();
    println!("chargement modele  : {:.2} s", temps_chargement_sortformer);
    println!(
        "config             : chunk_len={} fifo_len={} spkcache_len={} right_context={} (latence {:.2} s)",
        sortformer.chunk_len, sortformer.fifo_len, sortformer.spkcache_len,
        sortformer.right_context, sortformer.latency()
    );

    let chrono_diarisation = Instant::now();
    let segments_locuteurs = sortformer.diarize(
        echantillons.clone(),
        specification.sample_rate,
        specification.channels,
    )?;
    let temps_diarisation = chrono_diarisation.elapsed().as_secs_f32();

    // Compte des locuteurs distincts et du temps de parole de chacun
    // / Count distinct speakers and each one's speaking time
    let mut identifiants_locuteurs: Vec<usize> = segments_locuteurs.iter().map(|s| s.speaker_id).collect();
    identifiants_locuteurs.sort_unstable();
    identifiants_locuteurs.dedup();

    println!("inference          : {:.2} s", temps_diarisation);
    println!("RTFx               : {:.1}x le temps reel", duree_audio_secondes / temps_diarisation);
    println!("segments trouves   : {}", segments_locuteurs.len());
    println!("locuteurs distincts: {} -> {:?}", identifiants_locuteurs.len(), identifiants_locuteurs);

    for identifiant in &identifiants_locuteurs {
        let temps_de_parole: f64 = segments_locuteurs
            .iter()
            .filter(|s| s.speaker_id == *identifiant)
            .map(|s| (s.end - s.start) as f64 / TAUX_ECHANTILLONNAGE as f64)
            .sum();
        let nombre_de_tours = segments_locuteurs.iter().filter(|s| s.speaker_id == *identifiant).count();
        println!(
            "  locuteur {} : {:.1} s de parole ({:.1} %), {} tours",
            identifiant, temps_de_parole,
            100.0 * temps_de_parole / duree_audio_secondes as f64,
            nombre_de_tours
        );
    }
    println!();

    // ---------- Etape 2 : transcription par morceaux ----------
    println!("### ETAPE 2 — TRANSCRIPTION (Parakeet TDT v3, par morceaux)");
    let chrono_chargement_tdt = Instant::now();
    let mut parakeet = ParakeetTDT::from_pretrained(dossier_tdt, None)?;
    let temps_chargement_tdt = chrono_chargement_tdt.elapsed().as_secs_f32();
    println!("chargement modele  : {:.2} s", temps_chargement_tdt);

    let echantillons_par_chunk = (secondes_par_chunk * TAUX_ECHANTILLONNAGE as f32) as usize;
    let nombre_de_chunks = echantillons.len().div_ceil(echantillons_par_chunk);
    println!("morceaux a traiter : {}", nombre_de_chunks);

    let chrono_transcription = Instant::now();
    let mut phrases_horodatees: Vec<(f32, f32, String)> = Vec::new();
    let mut texte_complet = String::new();

    for (indice, morceau) in echantillons.chunks(echantillons_par_chunk).enumerate() {
        // Decalage a rajouter aux horodatages, qui sont relatifs au morceau
        // / Offset to add to timestamps, which are relative to the chunk
        let decalage_secondes = (indice * echantillons_par_chunk) as f32 / TAUX_ECHANTILLONNAGE as f32;
        let chrono_morceau = Instant::now();

        match parakeet.transcribe_samples(
            morceau.to_vec(),
            specification.sample_rate,
            specification.channels,
            Some(TimestampMode::Sentences),
        ) {
            Ok(resultat) => {
                let duree_morceau = morceau.len() as f32 / TAUX_ECHANTILLONNAGE as f32;
                let temps_morceau = chrono_morceau.elapsed().as_secs_f32();
                println!(
                    "  morceau {}/{} ({:.0} s d'audio) : {:.2} s -> {:.1}x, {} phrases",
                    indice + 1, nombre_de_chunks, duree_morceau,
                    temps_morceau, duree_morceau / temps_morceau,
                    resultat.tokens.len()
                );
                if !texte_complet.is_empty() {
                    texte_complet.push(' ');
                }
                texte_complet.push_str(resultat.text.trim());
                for phrase in resultat.tokens {
                    phrases_horodatees.push((
                        phrase.start + decalage_secondes,
                        phrase.end + decalage_secondes,
                        phrase.text,
                    ));
                }
            }
            Err(erreur) => {
                println!("  morceau {}/{} : ECHEC — {}", indice + 1, nombre_de_chunks, erreur);
            }
        }
    }
    let temps_transcription = chrono_transcription.elapsed().as_secs_f32();
    println!("inference totale   : {:.2} s", temps_transcription);
    println!("RTFx               : {:.1}x le temps reel", duree_audio_secondes / temps_transcription);
    println!("phrases obtenues   : {}", phrases_horodatees.len());
    println!("caracteres         : {}", texte_complet.len());
    println!();

    // ---------- Etape 3 : attribution par recouvrement cumule ----------
    println!("### ETAPE 3 — ATTRIBUTION (recouvrement temporel cumule par locuteur)");
    let mut segments_attribues: Vec<SegmentAttribue> = Vec::new();
    let mut phrases_sans_locuteur = 0usize;

    for (debut, fin, texte) in &phrases_horodatees {
        // On SOMME le recouvrement par locuteur au lieu de prendre le meilleur segment :
        // Sortformer hache la parole, et quatre segments courts d'un meme locuteur
        // doivent l'emporter sur un seul long segment d'un autre.
        // / We SUM overlap per speaker instead of taking the single best segment.
        let mut recouvrement_par_locuteur: HashMap<usize, f32> = HashMap::new();
        for segment in &segments_locuteurs {
            let segment_debut = segment.start as f32 / TAUX_ECHANTILLONNAGE as f32;
            let segment_fin = segment.end as f32 / TAUX_ECHANTILLONNAGE as f32;
            let recouvrement = (fin.min(segment_fin) - debut.max(segment_debut)).max(0.0);
            if recouvrement > 0.0 {
                *recouvrement_par_locuteur.entry(segment.speaker_id).or_insert(0.0) += recouvrement;
            }
        }

        // En cas d'egalite parfaite, on prend le plus petit identifiant pour rester
        // deterministe d'une execution a l'autre (l'ordre d'un HashMap ne l'est pas).
        // / On an exact tie, take the lowest id to stay deterministic across runs.
        let locuteur = recouvrement_par_locuteur
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap().then(b.0.cmp(a.0)))
            .map(|(identifiant, _)| format!("locuteur_{}", identifiant));

        if locuteur.is_none() {
            phrases_sans_locuteur += 1;
        }
        segments_attribues.push(SegmentAttribue {
            debut: *debut,
            fin: *fin,
            locuteur: locuteur.unwrap_or_else(|| "INCONNU".to_string()),
            texte: texte.clone(),
        });
    }

    println!("phrases attribuees : {}", segments_attribues.len() - phrases_sans_locuteur);
    println!("phrases INCONNU    : {} ({:.1} %)",
        phrases_sans_locuteur,
        100.0 * phrases_sans_locuteur as f32 / segments_attribues.len().max(1) as f32);
    println!("  ATTENTION : ce taux ne detecte PAS le depassement des 4 locuteurs.");
    println!("  Les voix surnumeraires sont ABSORBEES dans les slots existants (cf. spec 4.5).");
    println!();

    // ---------- Bilan ----------
    let temps_total_inference = temps_diarisation + temps_transcription;
    println!("### BILAN");
    println!("duree audio            : {:.1} s", duree_audio_secondes);
    println!("chargement des modeles : {:.2} s (hors mesure d'inference)", temps_chargement_sortformer + temps_chargement_tdt);
    println!("diarisation            : {:.2} s", temps_diarisation);
    println!("transcription          : {:.2} s", temps_transcription);
    println!("inference totale       : {:.2} s", temps_total_inference);
    println!("RTFx global            : {:.1}x le temps reel", duree_audio_secondes / temps_total_inference);
    println!("=> pour 1 h d'audio    : {:.1} min de calcul", temps_total_inference / duree_audio_secondes * 60.0);

    // ---------- Ecriture du resultat ----------
    let mut fichier = File::create(chemin_sortie)?;
    writeln!(fichier, "{{")?;
    writeln!(fichier, "  \"duree_audio_s\": {:.2},", duree_audio_secondes)?;
    writeln!(fichier, "  \"chargement_sortformer_s\": {:.2},", temps_chargement_sortformer)?;
    writeln!(fichier, "  \"chargement_tdt_s\": {:.2},", temps_chargement_tdt)?;
    writeln!(fichier, "  \"diarisation_s\": {:.2},", temps_diarisation)?;
    writeln!(fichier, "  \"transcription_s\": {:.2},", temps_transcription)?;
    writeln!(fichier, "  \"locuteurs_detectes\": {},", identifiants_locuteurs.len())?;
    writeln!(fichier, "  \"phrases_inconnu\": {},", phrases_sans_locuteur)?;
    writeln!(fichier, "  \"texte_brut\": {},", echapper_json(&texte_complet))?;
    writeln!(fichier, "  \"segments\": [")?;
    for (indice, segment) in segments_attribues.iter().enumerate() {
        writeln!(
            fichier,
            "    {{\"debut\": {:.2}, \"fin\": {:.2}, \"locuteur\": \"{}\", \"texte\": {}}}{}",
            segment.debut, segment.fin, segment.locuteur,
            echapper_json(&segment.texte),
            if indice + 1 == segments_attribues.len() { "" } else { "," }
        )?;
    }
    writeln!(fichier, "  ]")?;
    writeln!(fichier, "}}")?;
    println!("\nresultat ecrit dans {}", chemin_sortie);

    Ok(())
}

/// Echappe une chaine pour l'inserer telle quelle dans du JSON
/// / Escapes a string so it can be inserted as-is into JSON
fn echapper_json(chaine: &str) -> String {
    let mut sortie = String::with_capacity(chaine.len() + 2);
    sortie.push('"');
    for caractere in chaine.chars() {
        match caractere {
            '"' => sortie.push_str("\\\""),
            '\\' => sortie.push_str("\\\\"),
            '\n' => sortie.push_str("\\n"),
            '\r' => sortie.push_str("\\r"),
            '\t' => sortie.push_str("\\t"),
            c if (c as u32) < 0x20 => sortie.push_str(&format!("\\u{:04x}", c as u32)),
            c => sortie.push(c),
        }
    }
    sortie.push('"');
    sortie
}
