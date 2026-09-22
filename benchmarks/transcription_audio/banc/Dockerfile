# Banc d'essai ASR local : Parakeet TDT v3 (ONNX) + Sortformer v2, CPU uniquement
# / Local ASR benchmark: Parakeet TDT v3 (ONNX) + Sortformer v2, CPU only

# Debian 13 (trixie) et pas 12 : les binaires ONNX Runtime telecharges par la crate `ort`
# reclament glibc >= 2.38 (__isoc23_strtoull) et libstdc++ >= 13 (_M_replace_cold).
# Sur bookworm, l'edition de liens echoue avec des symboles indefinis.
# / Debian 13 (trixie), not 12: the ONNX Runtime binaries fetched by the `ort` crate
# require glibc >= 2.38 and libstdc++ >= 13. On bookworm, linking fails.
FROM rust:1-trixie

# ffmpeg pour la conversion audio, time pour mesurer la RAM reellement consommee
# / ffmpeg for audio conversion, time to measure actual peak RAM
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl time python3 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
ENV CARGO_TERM_COLOR=never
