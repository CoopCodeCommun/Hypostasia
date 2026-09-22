# Les deux gestes qui manquent à l'édition par blocs

**Décidé par le mainteneur le 23 août 2026. Rien n'est codé.**

> **📘 La spec fait foi désormais.**
> `PLAN/specs/SPEC-edition-par-blocs-et-stenotypie.md` (23 août 2026) absorbe cette
> note. Celle-ci garde ses **mesures** et son historique de décision ; en cas de
> désaccord, c'est la spec qui compte — sauf sur le choix de la voie technique, que
> le prototype tranche.

Sert `2026-08-23-le-mode-edition-et-son-clavier.md`, qui ne peut pas être écrit sans.

> **Cette note sert les DEUX voies d'édition** — le clavier maison
> (`2026-08-23-le-mode-edition-et-son-clavier.md`) comme BlockNote
> (`2026-08-23-le-prototype-blocknote-sur-notre-back.md`). Masquer une plage et
> corriger un locuteur manquent au back quel que soit le front qui les appelle :
> **elle peut donc avancer sans attendre la décision.**


## Ce que le back porte déjà

`ElementViewSet` (`hypostasis_extractor/views_element.py`, 606 lignes) porte cinq
gestes, chacun avec le bon verrou :

| Geste | Verrou | Pourquoi |
|---|---|---|
| `corriger` | ligne (`select_for_update` sur l'élément) | ne touche pas aux ordres |
| `masquer` / `demasquer` | ligne | idem |
| `scinder` | **page** | renumérote toute la page (`ordre__gt`) |
| `fusionner_avec_le_suivant` | **page** | idem |

Le verrou de page existe parce que deux opérations de structure simultanées sur des
éléments différents de la même page se percutaient au commit — contrainte d'ordre
`DEFERRED`, `IntegrityError`, 500. C'est écrit dans
`_page_verrouillee_pour_la_structure`, et ça ne se défait pas.

S'y ajoutent les refus déjà en place : droit d'écriture sur la note, verrouillage
pendant une analyse (`services/garde_edition.py`), et blocage si une synthèse figée
cite le passage.

## Ce qui manque — 1. Masquer une plage

**Le geste que le mode édition réclame, et qu'aucun endpoint ne sert.** Toutes les
actions sont `detail=True` : nettoyer trente blocs d'en-têtes après une ingestion
Docling, c'est trente requêtes, trente confirmations et trente rechargements.

Ce qui est décidé :

- **une plage contiguë**, désignée par ses deux bornes ou par la liste de ses
  identifiants — pas de sélection discontinue ;
- **`masquer` uniquement.** Pas de fusion en lot : elle renumérote la page et touche
  aux ancres, c'est un risque d'une autre nature. Décision du mainteneur, 23 août.
- **une transaction, un verrou de ligne** — masquer ne touche pas aux ordres, le
  verrou de page n'est pas nécessaire ;
- **un compte rendu, jamais un silence** : combien masqués, et combien refusés avec
  leur motif. Un lot où trois blocs sont cités par une synthèse figée doit masquer
  les vingt-sept autres **et le dire** — c'est la règle déjà appliquée par l'applieur
  d'opérations (rejet visible, par opération) et par le `--maximum` de la passe de
  nuit ;
- **réversible en un geste** : le lot doit pouvoir se `demasquer` en bloc, sinon
  l'annulation promise par le mode édition n'existe pas.

À trancher : **un lot partiellement refusé est-il un succès ou un échec ?** Le projet
penche pour « on fait ce qu'on peut, et on le dit » — mais c'est à confirmer, parce
que l'inverse (tout ou rien) est plus facile à annuler.

## Ce qui manque — 2. Corriger le locuteur

> **⚠️ Corrigé le 23 août 2026, en relecture adverse : LE GESTE EXISTE.**
> `PageViewSet.renommer_locuteur` (`front/views.py:3263`, formulaire l. 3241) renomme
> dans `transcription_raw`, reconstruit le HTML et le texte, met à jour
> `provenance["locuteur"]` sur les éléments par `bulk_update`, et écrit un `PageEdit`
> de type `locuteur` (`TypeEdit.LOCUTEUR`, PHASE-27a). **Trois portées** : `tous`,
> `ce_bloc_seul`, `ce_bloc_et_suivants` — et `ce_bloc_seul` **est** la réattribution
> d'un tour.
>
> **Ce qui manque n'est donc pas le geste, c'est son accès au clavier** depuis le mode
> édition, sans passer par une modale. La section ci-dessous garde sa mesure et son
> raisonnement ; sa conclusion est fausse.
>
> Et le vocabulaire de cette section est faux aussi : la clé est **`locuteur`**, pas
> `voice`. Le défaut de production que cette erreur a révélé — une fusion de deux tours
> qui gardait le locuteur du premier — est **corrigé** depuis le 23 août 2026 :
> `CHANGELOG/2026-08-23-la-fusion-de-deux-tours-gardait-le-mauvais-locuteur.md`.

`ElementDocument.provenance` porte `{start_time, end_time, voice}` pour un tour de
parole. Il existe un **filtre** par locuteur en lecture
(`front/services/transcription_audio.py:415`, « une pastille cliquable par voix »),
mais **aucun geste pour corriger `voice`** — vérifié le 23 août, ni dans
`views_element.py`, ni ailleurs.

C'est pourtant la correction la plus fréquente après une diarisation. La mémoire du
projet le dit : **six voix réelles, Sortformer en rend quatre, `diarize` cinq, et 0 %
d'INCONNU** — le taux d'inconnus n'est pas un garde-fou, les tours sont attribués à
tort et il faut pouvoir les rectifier à la main.

Le geste : sur un tour, changer `provenance["voice"]`. Verrou de **ligne** — ni les
ordres, ni le texte, ni les ancres ne bougent.

Deux points à traiter :

1. **La fusion retire déjà le locuteur quand il diverge.**
   `services/moteur_structure.py:485-488` : si deux tours fusionnés n'ont pas la même
   `voice`, la clé est **retirée** de la provenance fusionnée. C'est juste — un tour
   ne peut pas avoir deux voix — mais ça veut dire qu'un bloc peut se retrouver
   **sans locuteur**. Le geste de correction est aussi ce qui répare ce cas.
2. **Renommer une voix partout.** Corriger tour par tour est le geste unitaire ;
   « SPEAKER_02, c'est Paul » est un geste de note entière. Le second est plus utile
   et plus dangereux. À trancher : le premier jet s'en tient-il au tour ?

## Ce qui manque — 3. Un partial de bloc rendu

Le mode édition remplace `lectureReload` (qui recharge toute la zone de lecture) par
un swap ciblé. Il faut donc un endpoint qui rende **un bloc**, dans le même HTML que
`_blocs_elements.html` produit — les deux rendus ne doivent jamais diverger, sinon un
bloc corrigé n'aura pas la même apparence que ses voisins.

Le back rend déjà des partials par élément (`formulaire_correction`,
`formulaire_scission`) : c'est le même patron.

## Ce qu'il faut mesurer

- **Aucun appel LLM.** Ces gestes ne touchent aucun modèle : **pas de
  `make test-llm`, pas de facture.**
- **Des tests pytest**, parce que tout est serveur : le lot partiel, les verrous, le
  refus par la garde d'analyse, le refus par une synthèse figée, la réversibilité, et
  la fusion qui retire le locuteur.
- **Un test de concurrence** sur le lot : deux masquages qui se chevauchent ne doivent
  ni lever un 500, ni masquer deux fois. Le précédent est documenté — c'est
  exactement ce qui a imposé le verrou de page pour la scission.
- **Fixtures étalons à écrire** : une transcription à plusieurs locuteurs, dont un
  tour issu d'une fusion **sans `voice`**, et une ingestion Docling avec ses en-têtes
  répétés. Sans elles, on teste sur trois blocs, c'est-à-dire sur le cas qui marchait
  déjà.

## Ce qui casse si on ne fait rien

Le mode édition ne peut pas exister : sans lot, la sélection contiguë ne sert à rien,
et sans correction du locuteur, la moitié du travail sur une transcription reste
impossible — on peut couper, recoller et corriger le texte, mais pas dire qui parle.

## Coût de mise en œuvre

Deux actions de ViewSet, un partial, leurs serializers de validation, et les tests.
Une à deux journées. **À faire avant ou avec le front**, jamais après.
