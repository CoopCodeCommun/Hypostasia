# Banc d'essai — le juge de vérification

Comparer des juges d'implication (NLI) sur des paires **déjà jugées**, sans rien réécrire.

> **Ce dossier ne contient aucun test automatisé.** `comparer_un_juge.py` est un script
> `__main__` qui appelle un vrai modèle — **c'est facturé** — et le dossier `benchmarks/`
> n'est pas une app Django : `manage.py test` ne le collecte pas. Même précédent, mêmes
> raisons que `benchmarks/extraction_format/`.
>
> Ce qui EST couvert par la suite : `front/tests/test_gel_de_l_etalon_du_juge.py` (la
> commande de gel), `core/tests/test_verification.py` (la cascade, la non-dégradation et
> la dichotomie).

## Pourquoi un étalon gelé

Les verdicts vivent dans une colonne **qu'on réécrit**. Le bouton « Vérifier les
citations » rejuge tout l'article, `verifier_les_citations_etalons` en fait autant dès
qu'une seule paire a perdu son verdict, et `--forcer` rejuge sans condition. Une mesure
qui ne vit que dans une colonne réécrivable n'est pas une mesure : c'est un état.

`etalon-du-juge.json` est donc la seule trace stable de ce qu'un juge a répondu — **et de
la question exacte qu'on lui a posée**. Ce n'est pas une fixture : rien ne le charge en
base, et le banc le lit à chaque exécution.

## Ce que le banc mesure

**L'accord, pas la vérité.** Ni le juge de référence ni le candidat ne détiennent la bonne
réponse. Ce que produit ce banc, c'est une matrice de désaccords — et un désaccord entre
deux juges sur une citation est en lui-même une information : c'est ce qui rend l'état
*contestable* plutôt qu'asséné.

### Commencer TOUJOURS par le plancher de bruit

Un juge ne se reproduit pas lui-même. Mesuré le 17 août : le modèle de référence rejouant
ses propres 145 paires ne retrouve que **77 %** de ses verdicts, à température 0, à trois
minutes d'écart — et le nombre de citations « vérifiées » a varié de **105 à 133 sur cinq
exécutions**.

**Mais ce plancher dépend du MODÈLE, pas du dispositif.** Les candidats mesurés le même jour
atteignent **95 %**, avec le même prompt et le même jeton imprévisible. Le jeton — la défense
anti-injection, tirée à chaque appel — interdit le déterminisme parfait, et rien de plus :
l'écart de 18 points vient du modèle, pas de lui.

**Conséquence : un taux d'accord avec l'étalon ne veut rien dire tant qu'on n'a pas ce
plancher.** Un candidat à 82 % n'est pas « moins bon » qu'une référence dont la propre
reproductibilité est de 77 %.

```bash
# le plancher de bruit d'un modèle : deux exécutions, comparées entre elles
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_juge.py <id> --enregistrer /tmp/run_a.json
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_juge.py <id> --reference /tmp/run_a.json
```

C'est **la stabilité** qui décide, pas l'accord : un verdict opposable qui change à chaque
relance n'est pas opposable.

## Geler l'étalon

```bash
docker exec -w /app hypostasia_web python manage.py geler_l_etalon_du_juge
```

Lecture seule : aucun appel de modèle, aucune écriture en base. La commande **exclut** les
paires dont la question a dérivé depuis leur verdict (bornes périmées, verbatim devenu
introuvable) et les compte à part : les geler produirait une comparaison entre deux
questions différentes.

## Rejouer un juge candidat

```bash
# les modèles et leur identifiant
docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role --lister

# le banc — APPELS FACTURÉS
docker exec -w /app hypostasia_web python \
    benchmarks/juge_de_verification/comparer_un_juge.py <id_du_modele>
```

Le prompt, le jeton imprévisible et l'analyse de la réponse sont importés de
`core/services/verification.py`, **sans copie** : deux copies du prompt finiraient par
poser deux questions différentes, et la comparaison ne voudrait plus rien dire.

## Les mesures

| Date | Juge | Paires | Stabilité | Accord | Durée | Rapport |
|---|---|---|---|---|---|---|
| 2026-08-17 | `gemini-2.5-flash` (référence) | 145 | **77 %** | 72–88 % | 136–154 s | [stabilité des juges Gemini](2026-08-17_stabilite-des-juges-gemini.md) |
| 2026-08-17 | `gemini-3.1-flash-lite` | 145 | **95 %** | 81 % | **8 s** | idem — **juge retenu** |
| 2026-08-17 | `gemini-3.5-flash-lite` | 145 | 94 % | 82 % | 8 s | idem |
| 2026-08-17 | `mistral-small-latest` | 145 | **95 %** | **57 %** | 9 s | idem — stable et **beaucoup plus sévère** |
| 2026-08-17 | `ministral-3b-latest` | 145 | 89 % | 79 % | 8 s | idem — laisse tomber 1 à 4 paires sans verdict |
| 2026-08-17 | `gemini-2.5-flash-lite` | — | — | — | — | **404 : plus servi aux nouveaux comptes** |

Ranger ici le compte rendu de chaque comparaison, et ajouter sa ligne au tableau.
