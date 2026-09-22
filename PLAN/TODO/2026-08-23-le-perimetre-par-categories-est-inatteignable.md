# Le périmètre par catégories d'un wiki est inatteignable à l'écran

**Mesuré le 23 août 2026. Rien n'est codé.**

## Ce que le code fait aujourd'hui

`Wiki.categories_du_perimetre` (`core/models.py:3013`) est le mécanisme par lequel un
wiki restreint son périmètre à une partie du carnet. La spec en fait une décision de
premier rang :

> Le périmètre d'un wiki est défini par des **facettes**, pas par son sujet
> (`SPEC-synthese-carnet.md`, § 3.1.1, décision n°13)

et `notes_du_perimetre_d_un_wiki` (`core/services/synthese.py:41`) l'applique
correctement : les catégories d'un même axe se combinent en OU, les axes entre eux en
ET, exactement comme le filtre de l'écran carnet.

**La vue accepte le paramètre** — `front/views_synthese.py:695-705` lit
`request.data.getlist("categorie")` et fait le `set()`.

**Le formulaire ne l'envoie jamais.** `front/templates/front/corpus/liste_wikis.html`
ne contient **aucune** occurrence de `name="categorie"` : le seul champ posté est
`sujet` (l. 64).

En base, le 23 août : **les cinq wikis ont zéro catégorie de périmètre.** Tous
prennent donc le carnet entier.

## Ce qui casse — c'est déjà cassé

Un « périmètre par facettes » qu'aucun écran ne permet de régler est une gouvernance
de façade : le code la porte, la spec la revendique, personne ne peut s'en servir.

Et ça se paie ailleurs, de trois façons mesurées :

1. **La taille du prompt.** Le carnet « Thales » compte 2 notes et 397 extractions ;
   le prompt de mise à jour du wiki 3 fait **~68 700 caractères** parce qu'il embarque
   ses 350 écartées. Restreindre le périmètre est le levier le plus direct sur ce
   chiffre — voir `2026-08-23-le-prompt-de-mise-a-jour-n-est-borne-par-rien.md`.
2. **Le bruit du critère de reprise nocturne.** `_le_wiki_a_une_raison_d_etre_repris`
   se déclenche sur toute nouveauté du périmètre. Périmètre = carnet entier ⇒ toute
   note ajoutée au carnet réveille **tous** ses wikis.
3. **Le cas d'usage du 23 août.** « Réponds à cet appel à projet en te sourçant sur
   les autres documents du carnet » suppose précisément de pouvoir exclure l'appel à
   projet lui-même du corpus citable — ce que les catégories permettraient, et
   qu'aucun écran ne permet aujourd'hui.

## Ce qui est voulu

Un sélecteur de catégories dans le formulaire de création d'un wiki, et un moyen de
le **changer après coup** — un wiki est vivant, son périmètre doit pouvoir se
resserrer. Le vocabulaire à l'écran est celui de la spec corpus (§ 8.2) : des axes,
et des catégories dans chaque axe.

Deux points à trancher :

1. **Changer le périmètre d'un wiki existant, est-ce un tour ?** Ça modifie ce que
   l'article peut citer, donc ce que « non repris » veut dire, sans toucher au texte.
   L'historique doit-il le porter — un motif de plus dans `MotifDeTourDeWiki` — ou
   est-ce un réglage hors histoire ?
2. **Un périmètre resserré rend des citations existantes hors périmètre.** À la
   réindexation suivante, leurs marqueurs seront retirés du texte (c'est le
   comportement documenté d'`indexer_les_citations`). Faut-il le dire avant, à
   l'écran, avec le compte exact ?

## Ce qu'il faut mesurer

- **Fixtures étalons à écrire** : un carnet étalon **à plusieurs axes** — au moins
  deux axes et trois catégories chacun — pour éprouver la combinaison OU/ET, qui
  n'est aujourd'hui exercée par aucun wiki réel.
- **Aucun appel LLM n'est nécessaire** pour tester la sélection elle-même : c'est du
  SQL et un formulaire. Un test suffit.
- **Un banc LLM réel** (`make test-llm`, **facturé**) n'est utile que pour la question
  d'aval : à périmètre resserré, l'article est-il meilleur ? C'est la même mesure que
  celle de la borne du prompt — les deux bancs peuvent partager leur étalon.

## Coût de mise en œuvre

Un `<select multiple>` ou une liste de cases, le `getlist` déjà écrit côté vue, un
écran de modification, et les tests. Une journée si l'on s'en tient à la création ;
deux si l'on traite la modification et ses conséquences sur les citations.
