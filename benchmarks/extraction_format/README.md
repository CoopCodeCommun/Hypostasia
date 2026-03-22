# Benchmarks — Format d'extraction LangExtract

Tests comparatifs des approches de format et des modèles LLM pour l'extraction d'hypostases.

## Lancer un test

```bash
docker exec hypostasia_web uv run python benchmarks/extraction_format/test_format_extraction.py
```

## Rapports

| Date | Fichier | Few-shot | Résultat clé |
|---|---|---|---|
| 2026-03-22 | `2026-03-22_gemini-gpt_approche-a-b.md` | 2 extractions | GPT+B = 14 classes, Gemini+B = 2 classes (biais few-shot) |
| 2026-03-22 | `2026-03-22_test2_30fewshot.md` | **30 extractions** | Gemini+B = **20 classes**, GPT+B = 23 classes. Biais confirmé et corrigé. |

## Fichiers

| Fichier | Rôle |
|---|---|
| `prompts.py` | Définitions des 30 hypostases par familles + prompt amélioré |
| `fewshot_30_hypostases.py` | Texte synthétique + 30 extractions (une par hypostase) |
| `test_format_extraction.py` | Script de test (utilise les modules ci-dessus) |
