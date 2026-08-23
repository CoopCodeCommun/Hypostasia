# Le banc de transcription ailleurs : orchestrateur en conteneur, GPU, Meteor Lake

**Intention prise le 23 août 2026**, en explorant trois questions du mainteneur.
Rien de tout cela n'est codé. Ce qui est mesuré vit dans
`benchmarks/transcription_audio/` ; cette note ne dit que ce qui est **voulu**.

---

## 1. L'orchestrateur dans un conteneur

**Ce qui est voulu** : lancer la campagne entière sans rien exécuter sur l'hôte.

**Ce que le code fait aujourd'hui** : `docker-compose.banc.yml` monte déjà les
**sept** conteneurs des piles. Seul `lancer_la_campagne.sh` tourne sur l'hôte et
pilote les autres par `docker exec`.

**Le geste** : un huitième service, « chef d'orchestre », avec
`/var/run/docker.sock` monté et le dossier de travail en volume. Il exécute le
script inchangé.

**Ce que ça coûte, et il faut le décider en le sachant** : un conteneur qui
monte le socket Docker peut créer un conteneur privilégié — c'est l'équivalent
de root sur l'hôte. Sur une machine de mesure c'est sans conséquence ; sur la
machine de production, c'en a une.

> **Ce qui casse si on cherche à faire mieux — une image unique est IMPOSSIBLE.**
> Ce n'est pas une préférence d'architecture, ce sont des conflits heurtés le
> 23 août : `pyannote.audio` 3.3.2 appelle un paramètre retiré de
> `huggingface_hub` ≥ 1.0 (donc exige `<1.0`) et casse avec `torchaudio` ≥ 2.9
> (`AudioMetaData` retiré) ; la 4.x tourne sur `huggingface_hub` 1.x et
> torch 2.13. **Les deux versions de pyannote ne peuvent pas coexister dans un
> même environnement Python.** La séparation en conteneurs est ce qui rend la
> comparaison possible, pas une mise en scène.

---

## 2. Le banc sur GPU

**Ce qui est voulu** : pouvoir rejouer la même campagne sur une machine à carte
graphique, pour savoir ce que le GPU déplace réellement.

**Ce que le code fait aujourd'hui** : tout est CPU, et c'est écrit en dur dans
les images. Mais **le support existe déjà dans les bibliothèques**, vérifié le
23 août :

| pile | ce qu'elle expose | ce qu'il faudrait |
|---|---|---|
| `parakeet-rs` (voie A) | features `cuda`, `tensorrt`, `directml`, `openvino`, `coreml` | changer `Cargo.toml`, pas le code |
| `onnx-asr` (pilote) | `CUDAExecutionProvider`, `TensorrtExecutionProvider`, `DmlExecutionProvider`, `WebGpuExecutionProvider` — **pas OpenVINO** | un argument `--peripherique` à passer à `load_model(providers=…)` |
| WhisperX | `--device cuda`, `compute_type float16` | deux arguments |
| pyannote (3.1 et community-1) | `pipeline.to(torch.device("cuda"))` | une ligne |
| `diarize` | — | **rien à faire : son cœur est du scikit-learn (GMM+BIC, clustering spectral), CPU par nature** |

Le vrai travail est ailleurs : **trois images à base CUDA** (`onnxruntime-gpu`,
torch CUDA, `ort` compilé avec la feature), et un `docker-compose.banc.gpu.yml`.

### La régression mémoire de pyannote 4.x ne se voit pas ici, et c'est normal

Le mainteneur signale une régression de **VRAM** entre pyannote 3.x et 4.x.
Mesuré le 23 août sur CPU, sur la tranche T1 :

| | pic RSS du processus | diarisation |
|---|---|---|
| pyannote 3.1 (legacy) | **3,79 Go** | 818,9 s |
| `community-1` (courant) | **3,81 Go** | 821,3 s |

Soit **0,5 % d'écart en mémoire et 0,3 % en temps** — rien. Deux raisons, et la
seconde compte pour la suite :

1. **Sur CPU il n'y a pas de VRAM.** Une régression d'allocation graphique n'a
   simplement pas d'objet ici ; ce qui se mesure est le RSS.
2. **Ces deux chiffres ne prouvent pourtant pas l'absence de régression**, parce
   que le pic RSS porte sur le **processus entier** — Parakeet et son VAD
   compris, soit 1,5 à 2 Go. Un écart de quelques centaines de méga-octets entre
   les deux versions y serait noyé. L'option `--sans-asr` du pilote existe pour
   cela : elle ne charge pas l'ASR, et le pic ne porte alors que sur le
   diariseur. **À mesurer.**

**Ce que ça implique le jour où un GPU entre dans l'infrastructure** : la
comparaison 3.x contre 4.x redeviendrait un critère à part entière, et il
faudrait relever la VRAM et non le RSS. Le banc ne sait pas le faire aujourd'hui
— aucune de ses images n'est CUDA. À ajouter en même temps que le reste de cette
note, pas après.

> **La nuance que le § 4.3 de la spec n'a pas, et qu'il faut y ajouter.** Ce
> paragraphe conclut « un GPU n'apporte presque rien » — ×1,6 sur Parakeet via
> ONNX Runtime CUDA, ×9 seulement avec TensorRT. C'est juste, **mais il a été
> écrit avant que pyannote et WhisperX entrent au banc**. Or ce sont eux les
> postes lourds — pyannote tourne au temps réel, WhisperX large-v3 davantage —
> et tous deux sont du **PyTorch pur**. Le GPU ne change donc pas le verdict
> pour la pile la moins chère : il le change pour **la plus chère**. Tant que
> cette mesure n'existe pas, on ne sait pas si un GPU ferait passer pyannote
> sous le coût de `sherpa` ou non.

---

## 3. Le banc sur Meteor Lake (Framework Laptop 13, Core Ultra 7 155H)

**Ce qui est voulu** : rejouer la campagne sur le portable du mainteneur, et
comparer.

**Ce que le code fait aujourd'hui** : **rien à changer.** C'est du x86-64 sous
Docker ; les six commandes du `README.md` du banc suffisent. Le pilote écrit
déjà `vnni_ou_amx` dans chaque fichier de résultat, et `agreger_la_campagne.py`
porte la colonne « machine » — la comparaison se fait donc toute seule.

**Pourquoi cette mesure est la plus intéressante qui reste** : sur la VM Haswell
du 22 août, l'int8 est **1,6× plus LENT** que le fp32, faute de VNNI. Meteor
Lake **a AVX-VNNI**. Si l'int8 y redevient avantageux — ce qui est attendu mais
non mesuré — alors la recommandation « prendre le fp32 » de la note du 22 août
ne vaut que pour les processeurs anciens, et il faut le dire explicitement dans
cette note. **C'est le genre de conclusion qu'une seule machine ne peut pas
donner.**

### La voie NPU / iGPU, et pourquoi elle reste non prioritaire

- `parakeet-rs` a une feature **`openvino`** : pas de réécriture côté Rust.
- Le modèle converti existe : **`FluidInference/parakeet-tdt-0.6b-v3-ov`**
  (format IR, encodeur de 1,13 Go, accessible avec notre jeton — vérifié).
- `onnx-asr` **n'expose pas** OpenVINO : la voie Python demanderait
  `onnxruntime-openvino` ou `optimum-intel`, donc une image de plus.
- Le § 4.3 chiffre le gain à **1,3×** sur iGPU, et l'iGPU Xe-LPG de la série 1
  n'a **pas d'unités XMX** (~16 TOPS INT8 en DP4a ; NPU AI Boost ~11 TOPS). Ce
  sont les XMX de Lunar Lake qui font le saut.

**L'intérêt véritable de cette voie est la consommation électrique, pas la
vitesse.** À rouvrir si la cible de déploiement devient un portable ou un
mini-PC qui tourne en permanence, pas pour gagner 30 % sur un lot de nuit.

---

## Ce qui casse si on ne fait rien

Rien ne casse : le banc tourne et mesure. Ce qu'on perd, c'est la **portée** des
conclusions. Les chiffres du 22-23 août valent pour **une VM Haswell 8 vCPU sans
VNNI**, et deux des recommandations qu'ils portent — « prendre le fp32 »,
« pyannote coûte trop cher » — pourraient s'inverser sur un processeur récent ou
avec une carte graphique. **Tant qu'une seconde machine n'a pas tourné, aucune
de ces deux lignes ne devrait être écrite comme une décision d'architecture.**
