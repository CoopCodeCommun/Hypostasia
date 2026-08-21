# Typer le mode d'échec du verbatim / Typing the verbatim failure mode

**Date :** 2026-08-19
**Migration :** Non

## Resume / Summary

**Quoi / What :** un outil de banc qui dit **de quelle nature** est l'écart
entre une extraction et sa source — et quelle retouche de forme la
retrouverait. Il ne remplace rien : le banc existant annonce un *taux* de
verbatim, celui-ci en donne la *cause*.
/ A bench tool that types the gap between an extraction and its source, and
names the smallest shape fix that would find the quote again.

**Pourquoi / Why :** le taux de verbatim (83-87 % chez les trois Mistral)
pilotait une décision sur le prompt d'extraction, sans que personne ne sache
COMMENT les modèles échouent. La mesure montre que ce n'est pas la
concaténation supposée : c'est la retouche typographique, et une part vient de
nos propres sources.
/ The verbatim rate drove a prompt decision without anyone knowing HOW the
models fail. It is not concatenation: it is typographic touch-up.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `benchmarks/extraction_format/typer_les_non_verbatim.py` | **Neuf.** Typage des écarts, règles de réparation, table des `INTROUVABLE` par cause |
| `hypostasis_extractor/tests/test_typage_des_non_verbatim.py` | **Neuf.** 22 tests : les 6 types d'écart, les 3 règles, le compteur de retouches, et cinq cas qui ne doivent JAMAIS passer |
| `benchmarks/extraction_format/2026-08-19_le-mode-d-echec-du-verbatim.md` | **Neuf.** Le rapport de mesure |

**Aucun fichier de production n'est touché.** L'outil lit la base et n'y écrit
rien ; il n'appelle aucun modèle.

### Ce que la mesure a trouvé / What it found

- La concaténation fait **3 cas sur 21** chez `mistral-small`, pas la majorité.
- **Zéro ellipse** : aucun modèle n'annonce son élision.
- Sur les 60 `INTROUVABLE` en base : **34 (57 %)** tiennent à un espace de
  ponctuation, un point ajouté ou une majuscule d'amorce ; **11 (18 %)**
  seulement sont un vrai saut de passage.
- **La cause dominante est notre INGESTION, pas le prompt** : 20 liens sur 34
  viennent d'un espace parasite de la source (« IMS Global , un consortium »,
  « territoire . Soutenu »), que les trois modèles corrigent au même endroit.
- Le levier « durcir le prompt » ne porte que sur **8 liens sur 60**.

---

## Comment tester (a la main) / Manual test

### Test 1 — les tests automatiques
```bash
docker compose exec -T web python manage.py test \
    hypostasis_extractor.tests.test_typage_des_non_verbatim
```
Attendu : **22 tests OK**.

Les tests qui comptent le plus sont ceux qui vérifient qu'une règle de forme
ne blanchit JAMAIS un changement de fond, ni n'attribue une cause à la place
d'une autre :
- `test_une_enumeration_ne_doit_JAMAIS_blanchir_un_nombre_decimal` — sans la
  garde des chiffres, « les niveaux 3, 5 et 8 » accepterait « les niveaux
  3,5 », un décimal que la source n'avance nulle part ;
- `test_une_enumeration_entre_parentheses_ne_blanchit_pas_un_decimal` et
  `test_une_enumeration_de_trois_nombres_ne_blanchit_pas_un_decimal` — deux
  dispositions qui perçaient la garde parce que l'écrasement CONSOMMAIT le
  chiffre dont la ponctuation suivante avait besoin ;
- `test_un_point_d_interrogation_change_en_point_reste_irrecuperable` — une
  question devenue affirmation n'est pas un « point ajouté » ;
- `test_un_point_deja_dans_la_source_n_est_pas_un_point_AJOUTE` — celui qui
  renverse la conclusion : sans lui, 13 cas sur 21 sont attribués au prompt
  alors qu'ils viennent de notre ingestion.

### Test 2 — la mesure sur la base
```bash
docker compose exec -T web python \
    benchmarks/extraction_format/typer_les_non_verbatim.py
```
Attendu, quatre blocs :
1. le typage par modèle (six colonnes) ;
2. les retouches caractère par caractère — **descriptives**, elles ne disent
   pas qui a mis le caractère là ;
3. les `INTROUVABLE` par cause, **avec le nom du rédacteur qui a produit les
   articles mesurés** — sans cette ligne, on lirait « les articles » pour un
   seul modèle ;
4. le détail de chaque écart, avec le passage en clair.

### Test 3 — que rien n'a été écrit
```bash
docker compose exec -T web python manage.py shell -c "
from hypostasis_extractor.models import ExtractedEntity
print(ExtractedEntity.objects.filter(masquee=True).count())"
```
Attendu : **0**. L'outil ne masque rien, ne supprime rien, ne rejuge rien.
