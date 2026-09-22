# Garder le texte intégral d'un prompt — optionnel, avec rétention

**Discuté le 23 août 2026. Deuxième moitié de
`2026-08-23-la-provenance-d-un-prompt-n-est-ecrite-nulle-part.md`, et la seule qui ne
soit pas bloquante.**

## La distinction, et pourquoi elle décide

Deux questions se ressemblent et ne coûtent pas le même prix :

| La question | Ce qu'il faut pour y répondre | Poids |
|---|---|---|
| « quel prompt a écrit ce paragraphe ? » | analyseur + version + **empreinte** | **~100 octets** |
| « le prompt a-t-il changé entre ces deux tours ? » | la comparaison de deux empreintes | 0 |
| « qu'y avait-il **dedans**, exactement ? » | **le texte entier** | **25 à 80 ko** |

Les deux premières commandent tous les bancs : sans elles, un résultat n'est
rattachable à aucune cause. La troisième sert à **déboguer un cas précis** — pourquoi
ce tour-là a produit ce texte-là — et c'est un besoin réel, mais épisodique.

D'où la séparation : la provenance d'abord, obligatoire et légère ; le texte intégral
ensuite, optionnel et borné.

## Ce que le texte intégral coûte, mesuré

Compression PostgreSQL mesurée le 23 août : **environ ×2** (4 999 car. → 2 451 o ;
59 188 car. → 26 547 o). Un prompt de 80 ko tient donc ~35 ko en base.

| Régime | Volume |
|---|---|
| 5 wikis modifiés par nuit | ~175 ko / nuit ⇒ **~64 Mo / an** |
| 50 wikis, prompts plus gros | **~1 Go / an** |

Sur la cible de déploiement — un VPS CPU, pas une machine élastique — ce n'est pas
neutre. Et ça s'ajoute à ce qui est **déjà** stocké : `TourDeWiki` garde `texte_avant`
**et** `texte_apres`, deux instantanés complets de l'article à chaque tour, et
l'écran d'historique en charge **20 sans `defer()`** (`front/views_synthese.py:956-959`)
pour n'en tirer qu'un booléen « inchangé ».

## Ce qui est voulu

- le texte va dans la **table dédiée** de la note sur la provenance, jamais dans
  `ExtractionJob.prompt_description` — cet objet est rendu par
  `/api/extraction-jobs/<pk>/`, fermé aux inconnus depuis le 23 août 2026
  (`CHANGELOG/2026-08-23-fermer-l-api-d-extraction.md`) mais toujours lisible par
  qui accède à la note, et chargé par paquets de 30 dans le menu des tâches ;
- **une rétention** : les N derniers prompts par article, ou une durée. Au-delà,
  l'empreinte reste, le texte part. Une trace qui grossit sans fin finit par être
  purgée à la main, en urgence, et on perd alors aussi celles qu'on voulait garder ;
- **la purge doit être visible** : un compte, pas un silence. C'est la règle du projet
  sur toute troncature.

## Ce qui casse si on ne fait rien

Rien, tant que la provenance existe : on sait quel prompt a produit quoi, on sait
qu'il a changé, on peut **le reconstruire** en rejouant l'assemblage avec la version
d'analyseur enregistrée — c'est même la meilleure preuve que la trace est juste.

Ce qu'on perd est le cas pathologique : un prompt assemblé à partir d'un état de base
qui n'existe plus (des extractions supprimées depuis, un article réécrit). Là,
l'empreinte dit qu'il a changé, et rien ne dit **en quoi**.

## Ce qu'il faut mesurer

- **Un test sans aucun appel LLM** : rejouer l'assemblage à partir de la version
  d'analyseur enregistrée doit rendre **la même empreinte**. C'est ce test qui décide
  si le texte intégral est vraiment nécessaire — s'il passe toujours, la rétention peut
  être courte.
- **Fixtures étalons à écrire** : le même jeu gelé que la note sur la provenance ; il
  n'en faut pas d'autre.
- **Aucun banc facturé n'est requis ici.** Si l'on en lance un (`make test-llm`, tag
  `llm_reel`), ce sera pour la note sur la provenance, pas pour celle-ci.

## Coût de mise en œuvre

Un champ, une commande de purge, un réglage de rétention, deux tests. Une demi-journée
— **à ne faire qu'après** que la provenance ait tourné assez longtemps pour dire si le
texte manque vraiment.
