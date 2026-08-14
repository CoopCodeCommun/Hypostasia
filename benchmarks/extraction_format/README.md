# Benchmarks — Format d'extraction LangExtract

Comparatifs **manuels** des approches de format et des modèles LLM pour l'extraction d'hypostases.

> **Ce dossier ne contient aucun test automatisé.** Le script était nommé
> `test_format_extraction.py` jusqu'au 14 août 2026 alors qu'il n'a jamais contenu de
> `TestCase` : il laissait croire à une couverture inexistante. Il s'appelle désormais
> `lancer_comparaison_formats.py`.
>
> La non-régression du format d'extraction est couverte, elle, par :
> - `hypostasis_extractor/tests/test_referentiel_des_hypostases.py` — les 4 copies du
>   référentiel des 30 hypostases concordent (suite par défaut) ;
> - `hypostasis_extractor/tests/test_justesse_semantique_llm.py` — le modèle classe dans
>   la bonne famille épistémique (tag `llm_reel`, hors suite par défaut).

## Lancer une comparaison

Appelle de vrais fournisseurs payants et lit une page de la base via un `PAGE_ID` codé en dur.

```bash
docker exec hypostasia_web uv run python benchmarks/extraction_format/lancer_comparaison_formats.py
```

## Rapports

| Date | Fichier | Few-shot | Résultat clé |
|---|---|---|---|
| 2026-03-22 | `2026-03-22_gemini-gpt_approche-a-b.md` | 2 extractions | GPT+B = 14 classes, Gemini+B = 2 classes (biais few-shot) |
| 2026-03-22 | `2026-03-22_test2_30fewshot.md` | **30 extractions** | Gemini+B = **20 classes**, GPT+B = 23 classes. Biais confirmé et corrigé. |
| 2026-03-22 | `comparatif_gemini_4_approches.md` | — | **Synthèse Gemini seul** : 4 configs comparées, A vs B, 2 vs 30 few-shot |

## Fichiers

| Fichier | Rôle |
|---|---|
| `prompts.py` | Définitions des 30 hypostases par familles + prompt amélioré |
| `fewshot_30_hypostases.py` | Texte synthétique + 30 extractions (une par hypostase) |
| `lancer_comparaison_formats.py` | Script manuel de comparaison (utilise les modules ci-dessus) |
