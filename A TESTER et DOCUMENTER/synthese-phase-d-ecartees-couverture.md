# Synthèse phase D — écartées (§ 8) et couverture (§ 9)

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
