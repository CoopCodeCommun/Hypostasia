# Benchmarks — Format d'extraction LangExtract

Tests comparatifs des approches de format et des modèles LLM pour l'extraction d'hypostases.

## Lancer un test

```bash
docker exec hypostasia_web uv run python benchmarks/extraction_format/test_format_extraction.py
```

## Rapports

| Date | Fichier | Modèles | Approches | Résultat clé |
|---|---|---|---|---|
| 2026-03-22 | `2026-03-22_gemini-gpt_approche-a-b.md` | Gemini 2.5 Flash, GPT-4o Mini | A (classe unique) vs B (classe spécifique) | GPT+B = 14 classes, Gemini+B = 2 classes seulement |
