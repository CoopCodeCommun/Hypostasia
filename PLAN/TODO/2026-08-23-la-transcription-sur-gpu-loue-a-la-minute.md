# La transcription sur GPU loué à la minute (OVHcloud AI Training)

**Piste ouverte le 23 août 2026** par le mainteneur, après la campagne de mesure.
Rien n'est codé, et **rien n'est mesuré sur GPU**.

> **Le protocole de test complet est dans `PLAN/specs/SPEC-transcription-sur-gpu-loue.md`** —
> commandes `ovhai`, contraintes d'image, Dockerfile CUDA et script de job en
> annexes intégrales. Cette note-ci ne dit que l'intention et ce qui la commande.

---

## Ce qui est voulu

Exécuter **notre** conteneur WhisperX sur un GPU **loué à la minute**, au lieu de
l'héberger ou d'appeler une API. L'intention du mainteneur : « avoir une maîtrise
comme si on était en local ».

Cela déplace le curseur d'une façon que ni Voxtral ni l'auto-hébergement ne
permettent :

| | Voxtral | local sur notre VPS | **GPU loué** |
|---|---|---|---|
| qui exécute | un tiers | nous | nous, sur une machine louée |
| quels poids | opaques, peuvent changer | les nôtres, figés | les nôtres, figés |
| déterminisme | **non** (26,90 % puis 27,07 % sur le même audio) | oui | oui |
| coût | 0,18 $/h d'audio | matériel + 105 min de calcul/h | à la minute de GPU |
| tient à côté de la stack | — | **non** (8,3 Go contre les juges NLI) | oui, ailleurs |

> **L'argument est la souveraineté DE LA DONNÉE, et il est décisif.** Le projet
> transcrit des **comptes rendus de délibération confidentiels**. Envoyés à une
> API, ils nourrissent l'entraînement du fournisseur — ce que les conditions de
> Mistral autorisent. Sur un GPU loué, **la donnée ne sort pas de notre
> conteneur** : elle transite par un Object Storage que nous contrôlons, elle est
> traitée par nos poids, et rien n'est réutilisé par personne. La juridiction
> n'est pas le sujet (Mistral est français) ; **l'usage de la donnée l'est.**
>
> S'y ajoute un gain second, mesuré : Voxtral **n'est pas déterministe** — deux
> appels sur le même audio ont rendu 26,90 % puis 27,07 % de WER. Pour une chaîne
> de preuve, deux transcriptions différentes du même enregistrement sont un
> problème en soi.

---

## Le calcul qui décide : le point mort

Voxtral coûte **0,18 $/h d'audio**, soit environ **0,17 €**. Un GPU loué doit
donc traiter une heure d'audio en moins de :

| GPU | prix horaire annoncé | temps de calcul maximal par heure d'audio |
|---|---|---|
| **L4** | 0,75 €/h | **13,6 min** |
| L40S | 1,40 €/h | 7,3 min |
| H100 PCIe | 2,80 €/h (3,10 € en AI managé) | 3,6 min |

**Ce qu'il faut donc gagner** : notre mesure CPU donne **100 à 112 min de calcul
par heure d'audio** pour WhisperX large-v3 complet. Atteindre le point mort sur un
L4 demande un facteur **×7,4**. C'est plausible — l'ASR passe en float16 avec du
batch, ce que CTranslate2 fait bien — mais **ce n'est pas mesuré, et le banc ne
sait pas encore le mesurer** : aucune de ses images n'est CUDA.

**Attention au poste qui domine.** Sur CPU, la diarisation pèse ~55 min/h et
l'ASR ~60. Si le GPU accélère l'ASR d'un facteur 20 et pyannote d'un facteur 5,
le total ne descend pas comme on l'espère — **c'est pyannote qui décidera de la
facture**, pas Whisper. À vérifier avant tout chiffrage.

---

## Ce que le code fait aujourd'hui

Rien de tout cela. `front/tasks.py:177` dispatche par provider (`voxtral` ou
`mock`) ; le moteur local n'existe pas encore — voir
`2026-08-23-le-moteur-de-transcription-a-deux-voies.md`, dont cette note est une
**variante d'hébergement**, pas une alternative.

---

## Les contraintes d'OVHcloud AI Training, vérifiées

`ovhai job run <image>` lance un job batch **facturé à la minute**, ce qui
correspond exactement à notre usage : personne n'attend devant l'écran.

| contrainte | ce qu'elle impose |
|---|---|
| **l'image ne tourne pas en root** — un utilisateur OVHcloud d'UID **42420** | nos Dockerfiles écrivent dans `/work` en root : à reprendre |
| **`HOME` doit valoir `/workspace`** | à déclarer dans l'image |
| **les données passent par l'Object Storage**, monté par `--volume <conteneur>@<région>:/data:rw` | il faut y pousser l'audio, et en récupérer le JSON de sortie |
| **image Docker personnalisée acceptée** | notre image WhisperX peut servir de base |

**Deux pièges de facturation à instruire avant de chiffrer quoi que ce soit :**

1. **Le temps de démarrage.** Notre image WhisperX pèse **14,3 Go**. Si le pull
   est facturé, un job de cinq minutes peut coûter le double. Il faut une image
   **mince** — WhisperX sans les poids, qui sont sur l'Object Storage.
2. **Les poids.** large-v3 pèse 2,9 Go, turbo 1,6 Go, pyannote 38 Mo. Les
   retélécharger à chaque job serait payé en minutes de GPU. Ils doivent être sur
   un volume monté, pas dans l'image ni sur le hub.

---

## Ce qu'il faut mesurer avant de décider

Dans cet ordre, parce que le premier peut clore la question :

1. **Le RTFx réel sur un L4**, séparément pour l'ASR et pour pyannote. Sans ces
   deux chiffres, le point mort ci-dessus n'est qu'une équation.
2. **Le temps facturé d'un job à vide** — pull de l'image, montage du volume,
   chargement des poids. C'est le coût fixe, et il décide de la taille de lot :
   s'il vaut 3 minutes, traiter les enregistrements **par paquets** et non un par
   un change tout.
3. **Le WER sur nos trois tranches**, pour vérifier que float16 sur GPU rend le
   même texte que int8 sur CPU. Le banc sait déjà le faire : `comparer.py` et les
   références humaines ne changent pas.

**Le banc est réutilisable tel quel pour cela** — c'est même son intérêt : il
suffit d'une image CUDA et d'un `--peripherique cuda`, prévus dans
`2026-08-23-le-banc-de-transcription-sur-gpu-et-sur-npu.md`.

---

## Ce qui casse si on ne fait rien

Rien. Voxtral marche. Mais on garde ses deux défauts mesurés — **le
non-déterminisme** et l'opacité du modèle — et on renonce à la seule
configuration qui compte juste à six voix, faute de pouvoir la faire tourner :
sur notre VPS, WhisperX + pyannote demande **8,3 Go**, à côté des 5,13 Go des
juges NLI et des 2 Go de Docling. **Le GPU loué est aujourd'hui la seule voie
connue qui permette d'exécuter cette configuration sans acheter de matériel.**
