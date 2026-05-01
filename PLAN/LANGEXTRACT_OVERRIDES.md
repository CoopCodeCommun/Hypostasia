# Surcharges LangExtract — Registre de maintenance

> ⚠️ **DOCUMENT DÉPRÉCIÉ** (depuis 2026-04-26)
>
> LangExtract sera **supprimé en PHASE-38** (refonte du pipeline d'extraction
> Atomic-style : 1 chunk markdown-aware = 1 extraction, validation Pydantic via
> instructor, pas de dépendance externe pour l'extraction).
>
> Voir `PLAN/INSPIRATION_ATOMIC.md` section 2 (refactoring) et Annexe A (PHASE-38)
> pour le plan de suppression.
>
> Ce document reste utile **tant que LangExtract est en place**. Une fois la
> PHASE-38 livrée, ce fichier peut être supprimé du repo.

---

> Ce document recense toutes les surcharges appliquees a la lib `langextract` dans
> Hypostasia. A consulter **a chaque mise a jour** de la dependance.

Version actuelle couplee : **langextract v1.1.1**

---

## 1. AnnotateurAvecProgression (front/tasks.py)

### Ce qu'on surcharge

La classe `AnnotateurAvecProgression` herite de `langextract.annotation.Annotator` et
surcharge la methode interne `_annotate_documents_single_pass()`.

**Fichier source dans langextract** : `annotation.py`, lignes ~278-426 (v1.1.1)

### Pourquoi

LangExtract ne fournit pas de callback par chunk. L'`Annotator` standard traite tous
les chunks puis retourne le resultat final d'un bloc. Pour le streaming temps reel via
WebSocket (afficher les extractions au fur et a mesure dans le navigateur), on a besoin
d'un callback appele apres chaque cycle `resolve()` + `align()`.

### Ce qu'il faut verifier a chaque mise a jour

1. **Comparer** `annotation.py:_annotate_documents_single_pass()` de la nouvelle version
   avec notre copie dans `front/tasks.py` (classe `AnnotateurAvecProgression`).
2. Si la signature ou la logique interne a change, **re-synchroniser** notre copie.
3. Verifier que les imports internes utilises (`chunking.make_batches_of_textchunk`,
   `progress.get_model_info`, `progress.create_extraction_progress_bar`,
   `annotation._document_chunk_iterator`) existent toujours.

### Comment tester

```bash
# Lancer une extraction sur une page avec du texte long (>1 chunk)
# et verifier dans les logs Celery que les chunks arrivent un par un
# avec le message "[chunk N] resolve → X extraction(s)"
```

---

## 2. Auto-wrap des tableaux JSON nus (front/tasks.py)

### Le probleme

Le `FormatHandler.parse_output()` de langextract exige que la reponse du LLM soit wrappee
dans `{"extractions": [...]}`. Mais certains LLM (observe avec Gemini 2.5 Flash sur des
textes longs) renvoient parfois un tableau JSON brut `[{...}, {...}]` sans le wrapper.

Quand ca arrive, `Resolver.resolve()` leve une `FormatParseError`. Avec
`suppress_parse_errors=True`, l'erreur est loggee mais le resolver retourne `[]` — les
extractions de ce chunk sont **silencieusement perdues**.

### Le fix

Dans `AnnotateurAvecProgression._annotate_documents_single_pass()`, avant d'appeler
`resolver.resolve()`, on :

1. Recupere la sortie brute du LLM
2. Retire les fences `` ```json ``` `` si presentes
3. Detecte si la sortie commence par `[` (tableau nu)
4. Si oui, tente de parser le JSON et le wrappe dans `{"extractions": [...]}`
5. Si le JSON est tronque/invalide, laisse le resolver gerer avec `suppress_parse_errors`

Un message de log `[chunk N] reponse LLM wrappee dans {'extractions': [...]}` est emis
quand le wrapping est applique.

### Ce qu'il faut verifier a chaque mise a jour

1. **Verifier le changelog de langextract** : est-ce que `FormatHandler.parse_output()`
   accepte desormais les tableaux nus nativement ? Chercher des mots-cles comme
   "bare array", "unwrapped", "auto-wrap" dans les release notes.
2. **Verifier le code** : dans `langextract/core/format_handler.py`, methode `parse_output()`,
   est-ce qu'il y a un fallback pour les tableaux JSON sans wrapper ?
3. **Si le fix est integre upstream** : supprimer notre workaround dans `front/tasks.py`
   (le bloc qui commence par `texte_sortie_llm = scored_outputs[0].output`).
4. **Si le fix n'est pas integre** : garder notre workaround, il reste compatible tant
   que `resolver.resolve()` accepte un `str` en premier argument.

### Issue upstream a ouvrir (optionnel)

Titre suggere : _"FormatHandler.parse_output should accept bare JSON arrays when use_wrapper=True"_

Argument : quand `use_wrapper=True` et `wrapper_key="extractions"`, si le contenu parse
est une liste, la lib devrait automatiquement le wrapper dans `{wrapper_key: content}`
plutot que de lever `FormatParseError`. Le LLM ne respecte pas toujours les consignes
de formatage, surtout sur des chunks longs.

---

## 3. Checklist rapide pour une montee de version

```
[ ] Lire le changelog de la nouvelle version
[ ] Diff annotation.py:_annotate_documents_single_pass() (ancien vs nouveau)
[ ] Diff core/format_handler.py:parse_output() (auto-wrap tableau nu ?)
[ ] Diff resolver.py:resolve() (signature, gestion suppress_parse_errors)
[ ] Verifier que ALIGNMENT_PARAM_KEYS contient toujours suppress_parse_errors
[ ] Lancer une extraction sur un texte long (>3 chunks) et verifier les logs
[ ] Verifier qu'aucun chunk ne retourne 0 extractions de maniere suspecte
[ ] Mettre a jour la version dans ce document
```
