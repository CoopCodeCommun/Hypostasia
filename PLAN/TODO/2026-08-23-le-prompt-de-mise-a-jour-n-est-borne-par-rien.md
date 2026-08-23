# Le prompt de mise à jour n'est borné par rien

**Mesuré le 23 août 2026 sur les cinq wikis de la base de dev. Rien n'est codé.**

## Ce que le code fait aujourd'hui

`construire_la_proposition_d_operations` (`front/tasks.py:2170-2178`) met **toutes**
les extractions écartées dans le prompt, une par une, avec leur verbatim :

```python
ecartees = list(extractions_ecartees(article).order_by("pk"))
for extraction in ecartees:
    lignes_d_ecartees.append(
        f"Identifiant : ext:{extraction.pk}\n"
        f'Citation : "{extraction.extraction_text}"'
    )
```

Aucun `[:N]`, aucun plafond, aucun échantillonnage.

## Ce qui a été mesuré

| wiki | écartées | bloc des écartées | prompt de mise à jour | prompt de création |
|---|---|---|---|---|
| 1 | 91 | 13 387 c | ~23 200 c | ~25 800 c |
| 2 | 97 | 14 014 c | ~23 800 c | ~25 800 c |
| **3** | **350** | **58 215 c** | **~68 700 c** | **~81 500 c** |
| 4 | 373 | 63 107 c | ~69 900 c | ~81 500 c |
| 5 | 353 | 59 067 c | ~68 500 c | ~81 400 c |

Le carnet « Thales » compte **2 notes et 397 extractions** : la taille ne vient pas
du nombre de notes, elle vient du corpus. Le terme croît **linéairement**, et rien
ne le retient.

Coût mesuré avec `AIModel.estimer_cout_euros`, rédacteur `mistral-medium-latest` :
les cinq wikis d'aujourd'hui représentent **254 116 caractères ≈ 63 500 tokens**, soit
**0,122 € par nuit**, ou **45 € par an**. Ce n'est pas le juge qui coûte (~0,0014 €
par paquet de 20 paires) : **c'est le prompt du rédacteur**.

## Ce qui casse si on ne fait rien

À vingt notes, on est vers 200 ko de prompt (~50 000 tokens). Le jour où ça dépasse
la fenêtre du rédacteur :

1. `appeler_llm` lève ;
2. `_ecrire_un_tour_d_echec` (`front/tasks.py:1775`) écrit un tour d'échec ;
3. **`borne_du_dernier_essai` avance** — c'est le comportement voulu contre les
   boucles nocturnes ;
4. le wiki se tait jusqu'à la nouveauté suivante, où il échouera de la même façon,
   un peu plus gros.

Le symptôme est un article qui cesse silencieusement d'être suivi. Le journal du
worker le dit ; l'écran, non.

C'est aussi **le seul terme non borné du système** : toutes les autres notes de la
série du 23 août empilent leurs termes par-dessus celui-ci.

## Ce qui est voulu

Une borne sur les écartées envoyées, **et le compte de ce qui est écarté par la
borne** — jamais une troncature muette. C'est la règle que la passe de nuit applique
déjà pour son `--maximum` :

> Ce qui est écarté par cette borne est **COMPTÉ** — une troncature muette se
> lirait comme une couverture complète. (`front/tasks.py:1607`)

Trois choses à trancher :

1. **Le critère.** Les N plus récentes ? Les N plus anciennes ? Un budget en
   caractères plutôt qu'en nombre ? Un budget est plus juste (les extractions n'ont
   pas la même longueur) mais moins lisible à l'écran.
2. **Le seuil.** Aucune mesure ne le donne aujourd'hui : c'est précisément ce que le
   banc ci-dessous doit établir.
3. **Le même traitement pour la création ?** `produire_un_wiki_task` a le même
   défaut, en pire (~81 500 c). Mais une création tronquée produit un article qui
   ignore une partie du corpus **sans jamais y revenir**, là où une mise à jour
   tronquée reprendra le reste au tour suivant. Ce n'est pas le même risque.

## Ce qu'il faut mesurer

- **Fixtures étalons à écrire** : un carnet étalon à corpus **croissant** — 50, 100,
  200, 400 extractions écartées — pour mesurer où la qualité décroche. Sans lui, le
  seuil serait un chiffre inventé, ce que la méthode du projet interdit.
- **Un banc LLM réel** (`make test-llm`, tag `llm_reel`, **facturé**) : à chaque
  palier, le nombre d'opérations proposées, le taux de rejet par l'applieur, et la
  part d'extractions effectivement reprises. L'hypothèse à éprouver est qu'au-delà
  d'un certain nombre d'écartées, le modèle en reprend une part **décroissante** —
  auquel cas la borne ne coûte rien en qualité et divise la facture.
- **Attention au bruit** : `PLAN/PASSATION.md` § 6 mesure **11 points d'amplitude
  intra-modèle** sur ce type de taux. Toute mesure doit être **répétée**, et un
  écart inférieur à cette amplitude ne conclut rien.

## Coût de mise en œuvre

Le code est trivial (une borne, un compteur, une ligne à l'écran) : une demi-journée.
Le banc et son étalon sont le vrai travail, et ils servent aussi
`2026-08-22-borner-la-reecriture-nocturne-d-un-wiki.md`.
