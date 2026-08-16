# Couche synthese, phase D : ecartees et couverture (calculs purs)

**Date :** 2026-08-09
**Migration :** Oui

**Quoi / What :** les deux controles que personne n'offre (SPEC-synthese
§ 8-9), calculables sans aucun appel au modele :
- `extractions_ecartees(article)` : ce qu'une synthese N'A PAS repris —
  difference d'ensembles (perimetre − citees), JAMAIS une liste
  stockee. Perimetre : notes figees pour une dirigee, notes sources du
  carnet AU MOMENT DU CALCUL pour un wiki ; par note, les extractions
  citables de son dernier job d'analyse — la MEME definition que le
  prompt de la tache (`extractions_citables_d_un_job` et
  `dernier_job_d_analyse_de_la_note`, extraites en service partage,
  front/tasks.py refactore pour les utiliser).
- `couverture_de_la_note(page)` : quels elements portent au moins une
  extraction — une jointure, pas une estimation. Separe « le modele a
  invente » de « le passage n'a jamais ete extrait » (§ 9.1).
- Une page ni wiki ni dirigee n'a pas de perimetre : ValueError
  explicite, pas un resultat vide trompeur.

| Fichier | Changement |
|---|---|
| `core/services/synthese.py` | + 5 fonctions (section PHASE D) |
| `front/tasks.py` | Refactor : definitions partagees avec le service |
| `core/tests/test_synthese_citations.py` | + 7 tests (3 configurations d'ecartees, wiki qui suit le carnet, refus des pages sans genre, jointure vs LEFT JOIN manuel) |

### Relecture / Review
Relecture adverse passee (9 aout soir) : 3 bloquants corriges avec
leurs tests (+ 8 tests, classes CorrectifsRelectureDTest et
CouvertureFiltreeTest) :
- **B1** : « le dernier job » attrapait les jobs d'extraction manuelle
  et de selection — UNE extraction ajoutee a la main evincait les 40 de
  l'analyse et le § 8 devenait un blanc-seing. Nouvelle definition :
  TOUS les jobs termines non-synthese de la note (celle de l'ecran
  d'analyse), partagee par le prompt, le perimetre de citation et les
  ecartees.
- **B2** : le perimetre d'une dirigee n'etait pas vraiment fige — une
  re-analyse posterieure reecrivait ses ecartees. La production fige
  desormais AUSSI les extractions (M2M `extractions_du_perimetre` +
  flag, migration core.0051, appliquee sur dev). Les 292 historiques
  restent en recalcul dynamique assume (flag False).
- **B3** : analyseur sans extractions -> perimetre fige VIDE -> rien
  n'est declare « ecarte » (rien n'avait ete propose).
- **I4** : filtre § 3.3 mecanique sur notes_du_perimetre (une synthese
  glissee dans le perimetre fige est ignoree). **I6** : la couverture
  ne compte plus les masquees, les ancres DETACHEE ni les jobs
  inacheves. **I8** : le filtre non_pertinent etait MORT (fusionne dans
  masquee par extractor 0029) — retire, tests et fixtures corriges, le
  tri du prompt reduit a commente-d'abord. **M10/M11** : plus de N+1
  (une requete), departage -pk. Addendums n°11-13 consignes.

### Migration
- **Migration necessaire / Migration required :** Oui — core.0051
  (perimetre d'extractions fige, appliquee sur dev).

---

## Ce qui a été fait

Calculs purs, sans UI (l'affichage arrive en phase H) :

- `extractions_ecartees(article)` (core/services/synthese.py) :
  périmètre − citées. Dirigée = notes figées ; wiki = notes sources du
  carnet au moment du calcul. Par note : les extractions citables
  (non masquées, non « non pertinent ») de son DERNIER job d'analyse —
  définition partagée avec le prompt de la tâche.
- `couverture_de_la_note(page)` : {"total": N, "couverts": M} par
  jointure elements ↔ portions d'extractions.
- Refactor de front/tasks.py : `dernier_job_d_analyse_de_la_note` et
  `extractions_citables_d_un_job` vivent dans le service, la tâche les
  consomme.

## Tests a réaliser

### Suites automatiques
```bash
docker exec hypostasia_dev_web python manage.py test \
  core.tests.test_synthese_citations --noinput
```

### Vérification sur données réelles (dev = copie de prod)
```bash
docker exec hypostasia_dev_web python manage.py shell -c "
from core.models import SyntheseDirigee
from core.services.synthese import extractions_ecartees, extractions_du_perimetre, couverture_de_la_note
d = SyntheseDirigee.objects.filter(notes_du_perimetre__isnull=False).first()
print('perimetre:', extractions_du_perimetre(d.page).count())
print('ecartees:', extractions_ecartees(d.page).count())
note = d.notes_du_perimetre.first()
print('couverture:', couverture_de_la_note(note))"
```
Attendu : pour les 292 synthèses historiques, écartées = périmètre
entier (aucun SourceLink n'existait avant la phase C) — c'est honnête,
pas un bug.

## Relecture adverse (9 août soir) — corrigé

3 bloquants corrigés avec leurs tests : « le dernier job » évincé par
une extraction manuelle (B1 → définition « tous les jobs terminés de la
note », partagée prompt/citations/écartées) ; périmètre d'extractions
d'une dirigée désormais FIGÉ à la production (B2 → M2M
`extractions_du_perimetre` + flag, migration core.0051) ; analyseur
sans extractions → rien n'est déclaré écarté (B3). Plus : filtre § 3.3
mécanique sur le périmètre figé (I4), couverture sans masquées /
détachées / jobs inachevés (I6), filtre `non_pertinent` mort retiré
partout (I8, fusionné dans `masquee` par extractor 0029), plus de N+1
(M10), départage -pk (M11). Addendums n°11-13.

## Limites connues (dites par la spec, à afficher en phase H)
- N'audite que les CITATIONS : une extraction lue et utilisée sans
  marqueur traverse la différence (borne inférieure, § 8).
- Les 292 synthèses HISTORIQUES ont `perimetre_d_extractions_fige` à
  False : leurs écartées sont un recalcul dynamique approximatif —
  l'écran devra le dire (addendum n°11).
- Le total de la couverture inclut les éléments non textuels (titres,
  tableaux) : pas un pourcentage de lecture comparable (addendum n°13).

