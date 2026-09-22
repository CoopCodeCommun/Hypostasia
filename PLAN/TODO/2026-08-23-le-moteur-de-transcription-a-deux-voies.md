# Le moteur de transcription a deux voies : Voxtral, ou notre conteneur sur GPU loué

> ## ⚖️ TRANCHÉ par le mainteneur le 30 août 2026 — LES DEUX VOIES SONT NOMMÉES
>
> | voie | ce qu'on lui demande |
> |---|---|
> | **Voxtral** (API Mistral) | **rapide et bon marché** — c'est son seul rôle, et il suffit |
> | **notre conteneur sur GPU loué** | **la souveraineté** : la donnée reste dans notre périmètre, aucun éditeur de LLM n'y a accès, nos poids, notre code |
>
> **La seconde voie n'est PLUS « le local sur notre VPS ».** Le protocole et les
> contraintes vivent dans `2026-08-23-la-transcription-sur-gpu-loue-a-la-minute.md`
> et `PLAN/specs/SPEC-transcription-sur-gpu-loue.md` — cette note-ci décrit le
> **choix** entre les deux voies et son point d'ancrage dans le code.
>
> **Ce que ce déplacement CHANGE dans les sections ci-dessous** — à lire avant de
> les suivre :
>
> 1. **Le worker à concurrence 1 sous `nice -n 19` n'a plus de raison d'être telle
>    qu'elle est écrite.** Sa justification était la mémoire : deux transcriptions
>    simultanées, 7 Go sur notre machine. Le calcul ne tourne plus ici. Il faut
>    toujours un worker dédié, mais il **orchestre** : il pousse l'audio sur
>    l'Object Storage, lance le job, attend, récupère le JSON. La concurrence 1 y
>    devient un **contrôle de dépense**, plus un garde-fou mémoire — et le `nice`
>    n'a plus d'objet.
> 2. **Le curseur de la taille de Whisper se rouvre.** `large-v3` (le meilleur WER
>    mesuré, 30,5 %) était écarté parce que ses **8,27 Go** ne tiennent pas à côté
>    des juges NLI sur un VPS 16 Go. Sur un GPU loué, cette contrainte disparaît :
>    c'est le **point mort économique** qui décide désormais, pas la RAM de la
>    machine.
> 3. **Le point bloquant d'idempotence est LEVÉ, et c'est un gain net.** La note
>    ci-dessous établit que `bin/install.sh` ne peut plus être idempotent, parce
>    que pyannote exige un jeton HuggingFace et l'acceptation manuelle de
>    conditions. Avec le GPU loué, **les poids ne sont plus téléchargés sur nos
>    machines** : ils vivent sur l'Object Storage, poussés une fois. Un clone frais
>    n'a besoin d'aucun jeton, et `bin/install.sh` reste idempotent. Le jeton
>    redevient une opération d'administration, faite une fois, pas une dépendance
>    d'installation.
>
> **Une précision de vocabulaire, pour ne pas promettre plus que ce qui est vrai.**
> « Souverain » désigne ici l'**usage** de la donnée, pas son isolement physique :
> l'audio quitte notre machine et transite chez l'hébergeur du GPU, dans notre
> conteneur et sur notre Object Storage. Ce qui est acquis, et qui est le motif de
> la décision : **aucun éditeur de modèle n'y a accès**, les poids sont les nôtres
> et figés, rien n'est réutilisé pour entraîner quoi que ce soit, et la sortie est
> **déterministe** — ce que Voxtral n'est pas (26,90 % puis 27,07 % de WER sur le
> même audio). Un compte rendu de délibération confidentiel reste chez un tiers
> pendant son traitement, et c'est à dire tel quel à qui le demandera.
>
> **Ce qui reste à trancher, et qui n'a pas bougé** : la taille de Whisper (point
> 1 ci-dessous, désormais arbitré par le point mort), WhisperX tel quel ou démonté
> (point 2 — toujours décisif : 5/6 voix contre 6/6), et le nombre de voix réelles
> (point 3).
>
> **La question que la nouvelle voie créait est tranchée le 30 août 2026 :
> quand le GPU n'est pas joignable, ON AFFICHE L'ERREUR.** Ni repli
> silencieux sur Voxtral, ni attente indéfinie. C'est cohérent avec le motif
> même de la voie : quelqu'un qui a choisi la souveraineté ne doit **jamais**
> voir son enregistrement partir chez un tiers parce qu'une machine ne
> répondait pas. Un repli automatique serait exactement la panne invisible que
> ce produit s'interdit partout ailleurs.
>
> Ce que ça impose au code : la tâche marque la note en échec avec un motif
> **lisible** — le patron existe, c'est `TourDeWiki.message_d_echec` pour les
> articles — et l'écran d'import le dit. **Un nouvel essai est un geste
> humain**, comme le choix du moteur l'est déjà.

**Intention prise le 23 août 2026** par le mainteneur, après la campagne de
mesure. Rien n'est codé. Les chiffres sont dans
`benchmarks/transcription_audio/2026-08-23_neuf-piles-contre-la-transcription-humaine.md` ;
cette note ne les recopie pas, elle dit ce qui est **voulu**.

---

## Ce qui est voulu

**Deux moteurs de transcription, et un choix explicite entre eux :**

| moteur | ce qu'il vaut | ce qu'il coûte |
|---|---|---|
| **Voxtral** (API Mistral) — *rapide, payant, non souverain* | 31,9 % de WER, compte juste à 4 voix | 0,003 $/min, les délibérations partent chez un tiers |
| **local** (Whisper + pyannote) — *lent, gratuit, souverain* | 30,5 à 36,0 % de WER selon la taille, **seul à compter juste à 6 voix** | 80 à 105 min de calcul par heure d'audio |

**Ce que ce découpage supprime, et c'est son principal mérite** : les sept autres
piles mesurées reposaient sur **Parakeet**, que la campagne disqualifie. Les
retenir aurait voulu dire maintenir une crate Rust patchée, un second binaire,
des modèles ONNX renommés et quatre images Docker. Ici il reste **une image
Python et un appel d'API**.

---

## Ce que le code fait aujourd'hui

- `front/tasks.py:177` **dispatche déjà par provider** — `voxtral` ou `mock`.
  **Le point d'extension existe** : ajouter la voie locale est une branche de
  plus et une valeur de `TranscriptionModelChoices`, pas une refonte.
- `TranscriptionConfig` (`core/models.py:1338`) porte `model_choice`, dont
  `provider` et `model_name` sont déduits. C'est là que le choix se poserait.
- `construire_html_diarise()` (`front/services/transcription_audio.py:271`)
  consomme `[{speaker, start, end, text}]` — **les deux moteurs savent déjà
  rendre cette forme**, vérifié pour de vrai sur la sortie du banc.
- Rien d'autre : aucun modèle local n'est téléchargé, aucun worker ne leur est
  dédié.

---

## Ce qu'il faudra coder

1. **Un troisième provider**, `local`, et sa branche dans le dispatcher.
2. **Un service `transcrire_audio_en_local()`**, calqué sur le collage du banc :
   Whisper pour l'ASR, pyannote pour la diarisation, **attribution au point
   milieu de chaque mot**, mot non recouvert marqué `INCONNU` et jamais donné au
   voisin.
3. **Un worker Celery dédié**, sur le modèle de `celery_worker_juge_local` :
   file propre, **concurrence 1**, `nice -n 19`. La concurrence 1 est ce qui
   borne la mémoire — deux transcriptions simultanées, c'est 7 Go.
4. **Le téléchargement des poids**, sans casser l'idempotence de
   `bin/install.sh` — voir le point bloquant ci-dessous.

---

## Les trois choses à trancher avant de coder

**1. La taille de Whisper — un curseur, pas une falaise.**

| | WER | min/h | pic RSS |
|---|---|---|---|
| `large-v3-turbo` | 31,5 % | 41 | 3,66 Go |
| `small` | 36,0 % | 17 | 3,15 Go |

`large-v3` (30,5 %) est écarté : **8,27 Go** ne tiennent pas à côté des juges NLI
sur un VPS 16 Go. `medium` est dominé par turbo sur les deux axes.
**Ajouter ~65 min/h dans tous les cas pour la diarisation** — c'est elle qui
domine le coût, pas l'ASR.

**2. WhisperX tel quel, ou WhisperX démonté ?** WhisperX est prêt à l'emploi mais
**rate le comptage à six voix (5/6)** là où `community-1` seul fait 6/6 — même
modèle, même audio : c'est son **assignation par segment** qui perd le locuteur.
Notre collage au point milieu ne perd pas. La seconde voie coûte une centaine de
lignes déjà écrites dans le banc, et satisfait le critère qui disqualifie.

**3. Combien de voix dans les enregistrements réels ?** La question du § 6 reste
ouverte, et elle décide : à 4 voix presque tout marche, à 6 seul pyannote compte
juste.

---

## Le point qui bloque l'idempotence, et qu'il faut décider en le sachant

**pyannote exige un jeton HuggingFace ET l'acceptation manuelle de conditions**
sur `pyannote/speaker-diarization-community-1`. Conséquences mesurées :

- **`bin/install.sh` ne peut plus être idempotent** : un clone frais sur une
  machine neuve s'arrête tant qu'un humain n'a pas cliqué sur un site tiers.
  Le critère § 8.4 de la spec compte exactement ce coût.
- **L'accès se vérifie sur un FICHIER, jamais sur le dépôt** : l'API des
  métadonnées répond 200 pendant que les poids sont refusés en 403. Un contrôle
  d'installation qui interroge le dépôt annoncerait donc « tout va bien » sur une
  machine où rien ne marchera.
- La voie « pyannote sans jeton » a été cherchée et **n'existe pas** :
  `sherpa-onnx` exécute bien les mêmes modèles en ONNX, mais son seuil de
  clustering dépend de l'enregistrement — aucune valeur ne convient à trois
  extraits différents.

**Le moteur local est donc souverain à l'exécution, pas à l'installation.**

---

## Ce qui casse si on ne fait rien

Rien ne casse : Voxtral fonctionne. Ce qu'on garde, c'est la dépendance — **les
délibérations transitent par un tiers**, ce qui est précisément ce que le § 4.6
de la spec désigne comme le motif de la bascule (« la souveraineté, pas le
coût »). Et on garde un second défaut, mesuré : **Voxtral n'est pas
déterministe** — deux appels sur le même audio ont rendu 26,90 % puis 27,07 % de
WER. Pour une chaîne de preuve, deux transcriptions différentes du même
enregistrement sont un problème en soi.
