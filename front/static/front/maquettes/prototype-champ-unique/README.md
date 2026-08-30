# Prototype — l'option C, le champ unique

**⚠️ Ce n'est PAS un étalon.** Les autres fichiers de `maquettes/` sont la
référence visuelle du projet, et le code s'y aligne. Celui-ci est le **prototype
jetable** qui a tranché la voie technique de l'édition par blocs le 23 août 2026 :
il est gardé pour qu'on puisse le remanipuler, **jamais pour qu'on s'y aligne**.

**Ouvrir** `index.html` — par le serveur de statiques, ou en local.

## Ce qu'il montre, en trois clics

Changez l'adresse :

| Paramètre | Effet |
|---|---|
| `?garde=0` | le navigateur nu, aucune interception |
| `?garde=1` | la garde par `keydown` — celle qui ne suffit pas |
| `?garde=2` | la garde par `beforeinput` — celle qui tient |
| `&ce=plaintext-only` | l'autre valeur de `contenteditable` |
| `&page=3` | la transcription (12 tours, 5 locuteurs) au lieu des 210 blocs |
| `&ecriture=exec` | les écritures par `document.execCommand` |
| `&boutons=1` | rend les boutons d'action **dans** le `<p>`, comme le vrai gabarit |
| `&compo=1` | la **parade à la composition IME** : normalise la sélection dès `compositionstart` |
| `&annulation=1` | la **pile d'annulation** de l'addendum A : `Ctrl+Z`, `Ctrl+Maj+Z`, `Ctrl+S` |

**La configuration éprouvée est `?garde=2&ce=plaintext-only&compo=1&annulation=1`.** Les trois
pièces sont nécessaires, et chacune couvre ce que les autres laissent passer :
la garde tient les gestes traversants, `plaintext-only` tient le collage **non**
traversant, et la parade tient la composition IME — que la garde voit passer sans
pouvoir l'arrêter (`insertCompositionText` n'est pas annulable). L'annulation,
elle, est **entièrement applicative** : la pile native meurt dès qu'une interception
écrit dans le DOM, et mélanger les deux rendrait l'ordre des annulations
imprévisible. Un `Ctrl+Z` = **un geste** — un mot tapé, ou une suppression de six
blocs.

**Le geste à essayer** : sélectionnez du bloc 3 au bloc 8, et tapez une lettre.
En `garde=0` **et** en `garde=1`, cinq blocs disparaissent. En `garde=2`, non.

`Ctrl+S` sérialise et affiche le POST. La console garde tout :
`window.PROTO.journalSentinelle` (les mutations de structure vues par le
`MutationObserver`), `window.PROTO.journalBeforeInput`,
`window.signatureDesFrontieres()`.

## Les données sont SYNTHÉTIQUES

`donnees.json` a la **même forme** que le corpus réel — 210 blocs, la même
répartition de labels, 8 tableaux à saut de ligne, 5 locuteurs — mais son texte est
fabriqué, à −3,2 % du volume. La page 19 qui a servi aux mesures appartient à un
tiers : son texte n'a pas sa place dans l'historique du dépôt.

Pour remesurer sur le vrai corpus, et pour les bancs Playwright :
**`benchmarks/edition_par_blocs/`**.

## Ce qu'il a décidé

`CHANGELOG/2026-08-23-le-champ-unique-tranche-l-edition-par-blocs.md` — avec ses
chiffres, ses six coûts, et ce qu'il ne prouve pas.
