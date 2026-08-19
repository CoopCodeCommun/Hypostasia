# Première campagne à deux juges — 29 citations comparables

**18 août 2026**, sur une base **reconstruite de zéro** (`docker compose down -v`),
extraction et rédaction par `mistral-small-latest`, LangExtract 1.6.0.

Rejouable : `manage.py comparer_les_deux_juges`. Lecture seule.

---

## Ce que la base porte

| | |
|---|---|
| citations | 35 |
| avec un degré de production | 29 |
| avec un second avis | 30 |
| **comparables (les deux)** | **29** |

Les 6 sans degré de production sont 5 `INTROUVABLE` — verbatim absent de la
source, aucun juge ne s'est prononcé — et 1 restée sans verdict.

## Le résultat

| | |
|---|---|
| juge de production | `verbatim+nli-score v3 — Mistral Small`, seuil **45** |
| second juge | `shieldstral-logits v1 (large) — ShieldStral 1.0 3B`, seuil **38** |
| **accord** | **20/29 — 69 %** |
| **AUC du second juge** | **0,867** |

L'AUC est nettement au-dessus des **0,734** mesurés contre l'étalon gelé de
145 paires (référence : `gemini-2.5-flash`). Deux références différentes, deux
chiffres différents — ce qui est en soi une information sur les références.

## Les quatre crans, confirmés sur données de production

Les degrés rendus par le juge de production, sur 29 citations réelles :

```
{0: 1, 40: 14, 70: 13, 100: 1}
```

**Aucune valeur intermédiaire.** Le banc du 18 août l'avait mesuré sur quinze
paires d'une seule affirmation ; c'est confirmé ici sur un autre corpus, un
autre jour. Les quatre crans sont une propriété du **protocole texte**, pas du
sujet — et c'est ce qui justifie après coup d'avoir stocké un **flottant** :
un juge local à logits, lui, rend 8,5 · 37,8 · 46,9 · 75,5 · 99,0.

## Les neuf désaccords vont TOUS dans le même sens

| lien | production | local |
|---|---|---|
| 3 | 40 (non) | 79,8 (oui) |
| 9 | 40 (non) | 53,1 (oui) |
| 12 | 40 (non) | 81,8 (oui) |
| 15 | 40 (non) | 75,5 (oui) |
| 17 | 40 (non) | 56,2 (oui) |
| 22 | 40 (non) | 46,9 (oui) |
| 25 | 40 (non) | 46,9 (oui) |
| 26 | 40 (non) | 85,2 (oui) |
| 32 | 40 (non) | 56,2 (oui) |

**Ce n'est pas du bruit : c'est un décalage systématique de calibration.** Dans
les neuf cas, Mistral a posé son cran « 40 » — *« elle appuie l'affirmation de
loin — contexte, entité nommée, conséquence — sans rien établir »* — là où le
juge local voit un soutien franc.

## Le seuil de 38 ne transfère pas — et il ne faut PAS le déplacer

| seuil local | accord |
|---|---|
| 38 (mesuré sur 15 paires relues à la main) | 20/29 — 69 % |
| 60 | 22/29 |
| **85** | **24/29 — 83 %** |

Distributions, qui se chevauchent largement :

- ce que la production **refuse** : 8,5 · 10,7 · 14,8 · 37,8 ×3 · 46,9 ×2 ·
  53,1 · 56,2 ×2 · 75,5 · 79,8 · 81,8 · 85,2
- ce qu'elle **accepte** : 40,7 · 46,9 · 53,1 · 62,2 · 85,2 · 89,3 · 90,5 ×2 ·
  96,3 · 97,1 · 97,4 · 97,7 · 98,0 · 99,0

**Trois raisons de ne pas ajuster le seuil local à 85 :**

1. **Ce serait ajuster le second juge sur le premier**, c'est-à-dire l'inverse
   de ce à quoi sert un second avis. Un juge qui s'accorde à 100 % avec l'autre
   n'apprend plus rien, et la campagne n'aurait plus d'objet.
2. **La « vérité » de cette mesure est Mistral**, qui ne rend que quatre crans.
   Tout ce qu'il note 40 est « non », tout ce qu'il note 70 est « oui » : la
   référence est grossière, et l'optimum de 85 est peut-être un artefact de
   cette grossièreté plus qu'une propriété du juge local.
3. **29 points, seuil choisi après coup** — sur-ajusté, exactement la réserve
   déjà posée sur les quinze paires.

## Ce qu'il faut en faire

**Relire les neuf désaccords à la main.** C'est le livrable de cette campagne,
et c'est ainsi — et pas autrement — que se construira la référence humaine à
grande échelle qui manque depuis le début. Le taux d'accord, lui, ne dit rien
de la vérité : ni l'un ni l'autre des deux juges ne la détient.

## Réserves

- **Une seule passe.** Les deux étages en amont — extraction et rédaction — ont
  changé de modèle en même temps que la base était reconstruite.
- **Deux articles**, 35 citations. C'est peu.
- Le juge de production a jugé **29** paires, le juge local **30** : l'écart
  d'une paire vient d'un verdict que le lot de Mistral n'a pas rendu.
