# Mistral partout, sauf l'embedding / Mistral everywhere but embeddings

**Date :** 2026-08-18
**Migration :** Non — changements de **données**, pas de schéma.

## Résumé / Summary

**Quoi / What :** les quatre étages de la chaîne tournent désormais chez
Mistral. L'extraction (`Configuration.ai_model`), la rédaction d'article et le
juge de vérification passent sur `mistral-small-latest` ; la transcription était
déjà sur `voxtral-mini-latest`. La ligne morte `gemini-2.5-flash-lite`, qui
répond 404, est retirée du référentiel.
*/ Extraction, article writing and the verification judge move to
`mistral-small-latest`; transcription was already on `voxtral-mini-latest`. The
dead `gemini-2.5-flash-lite` row is removed.*

**Pourquoi / Why :** souveraineté. Mesuré le 18 août sur un même extrait de
débat à trois voix, `mistral-small-latest` rend **le découpage le plus fin des
cinq modèles** (18 extractions, 6·6·6 sur les trois voix, 97 % de couverture),
**zéro marqueur de citation inventé** en rédaction, et **95 % de stabilité** en
jugement. Rien ne justifiait de rester ailleurs.
*/ Sovereignty; and the measurements did not argue for staying elsewhere.*

### Ce qui a changé, en base

| Rôle / usage | Avant | Après |
|---|---|---|
| Extraction (`Configuration.ai_model`) | Gemini 2.5 Flash | **mistral-small-latest** |
| Rédacteur d'article | *(repli sur la Configuration)* | **mistral-small-latest** |
| Juge de vérification | gemini-3.1-flash-lite | **mistral-small-latest** |
| Transcription | voxtral-mini-latest | **inchangé** |

```bash
docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role --role redacteur_d_article --modele 7
docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role --role juge_de_verification --modele 7
```

`mistral-small-latest` est passé `is_active=True` : sans cela, l'écran de
configuration IA ne le proposerait pas au clic.

## Le piège de la bascule, et pourquoi il ne s'est pas refermé

Poser un modèle de plateforme dans `Configuration.ai_model` était nommé comme un
piège au CHANGELOG du 17 août : LangExtract choisit son moteur par **expression
régulière sur le nom du modèle**, et `mistral-small-latest` matche `^mistral`,
donc partirait vers `OllamaLanguageModel` — qui parle l'API propriétaire
d'Ollama. Pointé sur `api.mistral.ai`, ce moteur échoue.

`resolve_model_params` court-circuite la table par un `config=ModelConfig` qui
désigne le provider par son **nom**. Vérifié sur la configuration réelle, après
bascule, **sans aucun appel réseau** :

```
clés rendues     : ['config', 'model_id', 'use_schema_constraints']
provider désigné : OpenAILanguageModel
model_id         : mistral-small-latest
base_url         : https://api.mistral.ai/v1
clé au 1er niveau ? False
moteur construit : OpenAILanguageModel
```

**Ce que cela prouve, et ce que cela ne prouve pas.** Le bon moteur est
construit, pointé sur la bonne plateforme, et la clé ne fuit pas dans les
paramètres de premier niveau. Cela **ne prouve pas** qu'une extraction complète
aboutit : seule une extraction réelle le dirait, et c'est un appel **facturé**.
À faire par `make test-llm` ou par un import de note.

## `gemini-2.5-flash-lite` : la ligne retirée

Le modèle répond « 404 — no longer available to new users ». Il était en base
(id 2, `is_active=False`).

**Vérifié avant suppression**, FK par FK — le collecteur Django ne recense
**pas** les `SET_NULL`, donc une preuve par `Collector` n'aurait rien prouvé :

```
Prompt.default_model     (SET_NULL) -> 0
Configuration.ai_model   (SET_NULL) -> 0
ModeleParRole.modele     (PROTECT)  -> 0
ExtractionJob.ai_model   (SET_NULL) -> 0
AnalyseurTestRun.ai_model(SET_NULL) -> 0
```

⚠️ **Ce comptage vaut pour la base de DEV.** En production, un `ExtractionJob`
historique pointant cette ligne perdrait sa **provenance en silence**
(`SET_NULL`). **Rejouer ce comptage sur la base de prod avant d'y supprimer
quoi que ce soit.**

La valeur d'énumération `AIModelChoices.GOOGLE_GEMINI_2_5_FLASH_LITE` et son
tarif (`core/models.py:990`) sont **conservés** : les retirer coûterait une
migration d'altération de `choices` et casserait la lecture d'une donnée
historique qui les nommerait. Ce qui compte est retiré : la ligne qu'on
proposait au clic.

## L'embedding reste hors périmètre

`mistral-embed` date de décembre 2023 et ne revendique aucun multilinguisme —
c'est le maillon faible de la chaîne Mistral. Mais **le RAG n'existe pas dans le
code** : il n'y a rien à câbler, et rien à mesurer aujourd'hui. `bge-m3` chez
OVHcloud (0,01 €/M, MIT, 8 192 tokens) reste l'alternative à mesurer le jour
venu.

---

## Comment tester (à la main) / Manual test

### Test 1 — l'écran dit bien qui travaille

1. Ouvrir la bibliothèque, regarder le panneau de configuration IA.
2. **Attendu** : « IA active — mistral-small-latest ».
3. Ouvrir l'onglet Wikis d'un carnet.
4. **Attendu** : le moteur de rédaction annoncé est `mistral-small-latest`.

### Test 2 — une extraction réelle aboutit (APPEL FACTURÉ)

1. Importer une note courte (un ou deux paragraphes) et lancer l'analyse.
2. **Attendu** : le job finit `completed` avec des extractions **non vides**,
   toutes ancrées.
3. **Le piège à surveiller** : un job `completed` avec **zéro** extraction est
   le symptôme du « JSON nu » — la plateforme rend `[...]` au lieu de
   `{"extractions": [...]}`, et `suppress_parse_errors=True` avale l'échec.
   Seule trace : un `logging.exception` dans les journaux du worker.
   ```bash
   docker compose logs celery_worker | grep -i "Failed to parse"
   ```

### Vérifs DB

```bash
docker exec -w /app hypostasia_web python manage.py affecter_un_modele_a_un_role --lister
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import AIModel, Configuration
print('extraction :', Configuration.get_solo().ai_model)
print('gemini-2.5-flash-lite encore en base ?',
      AIModel.objects.filter(model_choice='gemini-2.5-flash-lite').exists())
"
```

**Attendu** : les trois rôles sur `mistral-small-latest`, et `False` pour la
ligne morte.
