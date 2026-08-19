# LangExtract 1.1.1 → 1.6.0 / LangExtract upgrade

**Date :** 2026-08-18
**Migration :** Non — montée de dépendance.

⚠️ **Elle s'applique au prochain démarrage de conteneur**, pas tout de suite :
`bin/install.sh` fait `uv sync` en étape 1/6, et `.venv` vit dans le bind mount
du dépôt. **Aucune reconstruction d'image n'est nécessaire.** Tant que le venv
porte la 1.1.1, les quatre tests de `test_liste_json_nue.py` sont **rouges**, et
c'est attendu.

## Résumé / Summary

**Quoi / What :** `pyproject.toml` demande `langextract>=1.6.0` (il disait
`>=0.1.0`), `uv.lock` l'épingle. Deux corrections de code accompagnent la
montée.
*/ The pin moves from an unbounded `>=0.1.0` to `>=1.6.0`, with two code
changes the new version requires.*

**Pourquoi / Why :** une plateforme qui rend `[...]` au lieu de
`{"extractions": [...]}` faisait perdre **toutes** les extractions d'un chunk,
**en silence**. Le `FormatHandler` de 1.1.1 levait sur une liste au premier
niveau, et notre `suppress_parse_errors=True` transformait l'exception en liste
vide : job `completed`, zéro extraction, indiscernable d'une page sans idée.
*/ A bare top-level JSON list silently lost every extraction of a chunk.*

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `pyproject.toml`, `uv.lock` | 1.1.1 → **1.6.0** |
| `hypostasis_extractor/services/__init__.py` | retrait de `fence_output` (OpenAI) ; le commentaire sur le schéma corrigé |
| `tools/test_langextract.py` | même retrait |
| `hypostasis_extractor/tests/test_liste_json_nue.py` | **nouveau** — 4 tests |
| `CHANGELOG/DEFAUTS-DIFFERES.md` | ce qui reste ouvert derrière |

## Ce que la montée apporte

**Le cas de la liste nue se referme, sans une ligne de notre code.**
`core/format_handler.py` en 1.6.0 :

```python
elif isinstance(parsed, list):
    if require_wrapper and (strict or not self.allow_top_level_list):
        raise …
    # Some models return [...] instead of {"extractions": [...]}
```

`allow_top_level_list` valait déjà `True` par défaut dans les **deux** versions :
c'est le `raise` **inconditionnel** de 1.1.1 qui est assoupli. Mesuré dans le
conteneur avant la montée :

```
enveloppe -> [{'idee': 'x', …}]
liste nue -> LEVE FormatParseError
             « Content must be a mapping with an 'extractions' key. »
```

Bonus du même correctif : les balises `<think>` des modèles de raisonnement sont
retirées avant le parse.

**Ce n'est qu'UN cas.** `suppress_parse_errors=True` continue d'avaler les
autres `FormatError` — JSON invalide, items non-mapping, clôtures multiples. Un
job peut toujours finir `completed` à zéro extraction.

## Les deux corrections que la montée exige

### `fence_output` cesse d'être ignoré

`Provider.OPENAI` posait `params['fence_output'] = True`. En 1.1.1,
`OpenAILanguageModel.requires_fence_output` rendait `False` dès que le format
était JSON, **quoi que l'appelant demande** : la ligne était silencieusement
sans effet.

1.6.0 honore l'override (le test porte désormais sur
`_fence_output_override is None`). La laisser demanderait au modèle d'entourer
sa réponse de clôtures ```json alors que `response_format={'type':'json_object'}`
lui fait rendre du JSON nu — une consigne qui se contredit elle-même. Retirée
aux **deux** endroits qui la portaient.

### Le commentaire « aucun schéma structuré » devient faux

`services/__init__.py` affirmait que le provider compatible OpenAI n'expose
aucun schéma. Vrai en 1.1.1, **faux en 1.6.0** : `providers/schemas/openai.py`
existe. `use_schema_constraints` reste à `False` — l'activer fermerait le risque
du JSON nu **à la source**, mais l'éprouver demande des appels facturés.

## Ce qui NE bouge pas, vérifié sur les sources

- **`providers/patterns.py` est identique octet pour octet.** La table qui
  envoie `^mistral` vers Ollama n'a pas changé : le test
  `LeRoutageParDefautDeLangExtractTest` tiendra, et `config=ModelConfig` reste
  indispensable.
- **`ModelConfig(model_id, provider, provider_kwargs)`** inchangé.
- **`resolver_params={"format_handler": …}`** reste le point d'injection.

## Deux défauts corrigés en amont, qui rendent nos réglages redondants

`fetch_urls` passe de `True` à `False` par défaut, et `suppress_parse_errors` de
`False` à `True`. **On garde nos réglages explicites** : ils documentent le
piège, et ils protègent si un défaut rebascule.

## Le risque à surveiller, qui n'est pas couvert

**L'aligneur flou passe de `difflib` à LCS** — `_DEFAULT_FUZZY_ALGORITHM = "lcs"`,
barrière neuve `fuzzy_alignment_min_density = 1/3`, et
`fuzzy_alignment_threshold` **change de sens** à défaut identique (0,75). Le
moteur ELEMENT **jette** toute extraction non alignée : la montée peut changer
lesquelles obtiennent une ancre, **en silence**.

**Rayon d'action mesuré le 18 août, base de dev** : 112 extractions stockées,
**112 verbatims exacts, 112 ancrées** — l'aligneur flou n'avait produit
**aucune** ancre sur ce corpus. *Réserve : on ne voit que les survivantes ; une
extraction jamais alignée n'est pas stockée, donc invisible.*

---

## Comment tester (à la main) / Manual test

### Test 1 — la version est bien montée

```bash
docker exec -w /app hypostasia_web python -c "
from importlib.metadata import version; print(version('langextract'))"
```
**Attendu** : `1.6.0`. Si c'est `1.1.1`, le conteneur n'a pas redémarré depuis
la montée — `uv sync` ne s'est pas rejoué.

### Test 2 — les quatre tests passent au vert

```bash
make test-suite S=hypostasis_extractor.tests.test_liste_json_nue
```
**Attendu** : `OK`. **Avant redémarrage** : deux échecs, dont un qui dit
explicitement « LangExtract < 1.6 reperd la tolérance à la liste JSON nue ».

### Test 3 — une extraction réelle aboutit toujours (APPEL FACTURÉ)

1. Importer une note courte, lancer l'analyse.
2. **Attendu** : extractions non vides, toutes ancrées.
3. Le symptôme à surveiller — c'est celui que la montée referme à moitié :
   ```bash
   docker compose logs celery_worker | grep -i "Failed to parse"
   ```
   Un job `completed` à **zéro** extraction avec cette trace est le cas d'un
   JSON malformé, que `suppress_parse_errors` avale toujours.

### Test 4 — l'ancrage n'a pas bougé

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from hypostasis_extractor.models import ExtractedEntity
total = ExtractedEntity.objects.count()
ancrees = ExtractedEntity.objects.filter(ancrages__isnull=False).distinct().count()
print(f'{ancrees}/{total} extractions ancrées')
"
```
**Attendu** : le même ratio qu'avant la montée. Un écart signale que le passage
à LCS a changé quelles extractions obtiennent une ancre — le risque ci-dessus,
qui n'est couvert par aucun test.
