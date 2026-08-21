# La consigne de sourçage ferme sa porte / The sourcing rule closes its loophole

**Date :** 2026-08-19
**Migration :** Non

## Resume / Summary

**Quoi / What :** la consigne de sourçage du prompt de synthèse exige désormais
un marqueur sur **TOUTE affirmation**, et interdit d'écrire une phrase qui ne
puisse en porter. Elle vit dans une constante nommée, `CONSIGNE_DE_SOURCAGE`
(`front/tasks.py`), qu'un test peut lire sans monter de job.
/ The sourcing rule now requires a marker on EVERY claim.

**Pourquoi / Why :** elle disait « chaque affirmation **tirée d'une hypostase**
se termine par le marqueur de sa source ». Elle conditionnait le marqueur à
l'origine de la phrase — et une phrase de synthèse générale n'est, du point de
vue du modèle, tirée d'aucune extraction *en particulier*. Elle échappait donc à
la règle **sans la violer**.
/ The old wording let a general claim escape the rule without breaking it.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/tasks.py` | `CONSIGNE_DE_SOURCAGE`, constante nommée et réécrite |
| `front/tests/test_consigne_de_sourcage.py` | **Neuf**, 5 tests sur la formulation |
| `benchmarks/redaction/2026-08-19_trois-redacteurs-a-un-seul-extracteur.md` | § 7 : la remesure des trois Mistral |

### Ce que la remesure a trouvé / What the re-run found

Même périmètre (137 extractions d'un seul extracteur), même juge, seule la
consigne change :

| | prose nue AVANT → APRÈS | % vérifiées AVANT → APRÈS |
|---|---|---|
| **Small** | 12 % → **9 %** | 28 % → **36 %** |
| **Medium** | 0 % → **2 %** | 27 % → **41 %** |
| **Large** | **50 % → 19 %** | 35 % → **30 %** |

- **La consigne était bien la cause.** Large supprime les deux tiers de ses
  phrases non sourcées sans qu'on ait changé de modèle.
- **Et son taux de vérifiées BAISSE** — ce n'est pas une régression, c'est une
  révélation : il source désormais ce qu'il laissait nu, et le juge note ces
  sources-là faibles. Son « 35 % » se lisait sur la moitié de son texte.
- **Medium prend la tête sur les deux critères** : 41 % de vérifiées, 2 % de
  prose nue.

⚠️ **Une seule passe par condition.** L'écart de Small (28 → 36 %) n'est pas
distinguable du bruit ; le 50 % → 19 % de Large l'est.

---

## Comment tester (a la main) / Manual test

### Test 1 — la formulation
```bash
docker compose exec -T web python manage.py test front.tests.test_consigne_de_sourcage
```
Attendu : **5 tests OK**. Ils vérifient que la porte reste fermée (« TOUTE
AFFIRMATION », « supprime-la ») **et** que la contrepartie tient : les titres et
les phrases de liaison n'ont pas à porter de marqueur — sans elle, on
produirait des titres balisés et un texte sans charpente.

### Test 2 — à l'œil, sur une production réelle
```bash
docker compose exec -T web python manage.py affecter_un_modele_a_un_role \
    --role redacteur_d_article --modele <id>
docker compose exec -T web python manage.py produire_les_syntheses_etalons --forcer
docker compose exec -T web python benchmarks/redaction/mesurer_les_redacteurs.py
```
⚠️ **Redémarrer le worker avant** (`make restart S=celery_worker`) : sans quoi
il rédige avec l'ancienne consigne, et la mesure ne dit rien.

Lire le bloc « PROSE SANS AUCUN MARQUEUR ». Puis ouvrir l'article et vérifier
que les phrases d'ouverture et de conclusion portent bien leur marqueur — c'est
là que la porte était ouverte.
