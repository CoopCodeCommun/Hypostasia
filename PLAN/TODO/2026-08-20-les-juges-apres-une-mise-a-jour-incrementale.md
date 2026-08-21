# Les juges doivent noter les paragraphes neufs d'une mise à jour

**Intention posée par le mainteneur le 20 août 2026.**

## Ce qui est voulu

> « Un wiki n'est jamais censé se régénérer dans sa totalité. Le wiki est mis à
> jour de façon incrémentielle, en modifiant ou ajoutant de nouveaux
> paragraphes. Donc oui, si la paire est intacte, on garde. **Si de nouvelles
> paires sont insérées pour l'utilité du wiki, on lance les juges.** Mais
> attention, un wiki ne doit jamais être effacé pour repartir de zéro. »

## Ce que le code fait déjà, et bien

**Le mécanisme incrémental EXISTE** (`core/services/section_ops.py`,
SPEC-synthese § 6). Le modèle ne réécrit jamais l'article : il propose des
opérations — `no_change`, `append_to_section`, `replace_section`,
`insert_section` — qu'un applieur fusionne et qu'un **humain accepte une par
une**. Le modèle `Wiki` le dit : *« Il n'a pas de version : il a un ÉTAT, et un
compteur de tours. Un wiki ne s'adopte pas, il se suit. »*

**Le report des avis existe aussi** : à chaque réindexation, un avis dont la
paire (extraction, paragraphe) est **strictement identique** est reporté sur le
nouveau lien (`core/services/synthese.py`, `_cle_de_paire`). Une paire intacte
garde donc bien ses notes.

## Ce qui manque

**Une opération de section ne déclenche AUCUN juge.** Ni le juge de production,
ni les quatre juges locaux. Les paragraphes que le tour vient d'ajouter ou de
remplacer portent donc des citations **sans aucune note**, et rien ne le dit :
la fiche de preuve affiche « aucun avis », exactement comme si les juges
n'avaient jamais tourné.

L'utilisateur doit s'en apercevoir seul et cliquer deux boutons — un pour la
vérification, un pour le second avis — sur un article qu'il vient pourtant de
mettre à jour.

## Ce qui casse si on ne le fait pas

Un wiki suivi sur plusieurs tours se remplit progressivement de paragraphes non
notés, **mélangés** à des paragraphes notés au premier tour. Le lecteur ne peut
pas distinguer « cette citation n'a pas été jugée » de « cette citation a été
jugée et n'a rien donné » — et c'est précisément la distinction que toute la
couche de vérification existe pour porter.

## La forme attendue

Après l'application d'un lot d'opérations, mettre en file **les paires
nouvellement créées seulement** — pas l'article entier. Le compte des paires
sans avis est déjà calculable (`paires_sans_avis`), et les deux tâches sont
idempotentes paire par paire : le coût est proportionnel à ce qui a bougé.

## Le piège à ne pas reproduire

`produire_les_syntheses_etalons --forcer` **court-circuite l'incrémental** : il
régénère l'article en entier. C'est légitime pour une *première* production,
mais le 19 août 2026 un banc de comparaison de rédacteurs l'a appelé **neuf
fois** — les 165 avis des juges locaux sont partis par CASCADE, en silence. Les
avis perdus sont **comptés** depuis (`avis_perdus` au bilan) ; le drapeau, lui,
reste aussi dangereux.
