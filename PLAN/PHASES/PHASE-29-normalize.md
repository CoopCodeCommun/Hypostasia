# PHASE-29-normalize — Normalisation deterministe des attributs d'extraction

**Complexite** : S | **Mode** : Normal | **Prerequis** : aucun (independant, ameliore tout le cycle)

---

## 1. Contexte

### Le probleme

Le LLM retourne des attributs d'extraction dans un JSONField (`ExtractedEntity.attributes`)
dont les **cles** et **valeurs** varient selon le modele, la session et la temperature.

Le PLAN.md (section 1.8) decrit les cartes comme affichant 4 attributs generiques
(`attr_0` a `attr_3`). La couche de template (`entity_json_attrs()`) normalise a
l'affichage — mais les couches en aval (alignement cross-documents, synthese
deliberative, prompt de synthese) lisent le dict **brut** et cassent quand les cles
ne correspondent pas.

### Etat actuel en DB (audit 2026-03-21)

**Cles d'attributs** — 2 conventions coexistent :

| Cle canonique (cible) | Variantes en DB | Occurrences |
|---|---|---|
| `hypostases` | `hypostase` (451x), `Hypostases` (4x) | 455 |
| `resume` | `résumé` (461x), `Résumé` (4x) | 465 |
| `mots_cles` | `mots_clés` (426x), `Mots-clés` (4x) | 430 |
| `statut` | `statut_debat` (1x), `Statut` (4x) | 5 |

**Valeurs d'hypostases** — 99.1% conformes aux 30 hypostases de la geometrie des debats :

- 1085 valeurs correspondent aux 30 hypostases connues (classees par frequence :
  methode 136x, probleme 118x, principe 104x, theorie 96x, definition 93x...)
- 10 valeurs sont hallucinees (`metaphore` 2x, `biais`, `calcul`, `relation`,
  `logique`, `geometrie`, `creativite`, `information`, `capacite`, `consequence`)

### Origine du probleme

Le prompt de l'analyseur Hypostasia contenait 2 conventions contradictoires :
- PromptPiece #5 (methode) : `Résumé`, `Hypostases`, `Mots-clés`, `Statut` (avec majuscules et accents)
- PromptPiece #7 (format) : `"mots_cles": "politique, économie"` (snake_case)
- Exemples few-shot (ExtractionAttribute) : `"Hypostases"`, `"Résumé"` (majuscules)

**Correction deja appliquee** : les fixtures (`demo_ia.json`) ont ete harmonisees
en snake_case le 2026-03-21. Les nouvelles analyses produiront des cles plus
homogenes. Mais les entites existantes en DB conservent les anciennes cles, et la
normalisation cote code n'est pas encore faite.

### 3 couches lisent les attributs avec des logiques differentes

| Couche | Fichier | Ce qu'elle cherche | Comportement si absent |
|---|---|---|---|
| Cartes (affichage) | `extractor_tags.py:entity_json_attrs()` | Normalise par nom (accents, casse) → 4 slots | Fallback slot vide (robuste) |
| Alignement (tableau) | `views_alignement.py:_extraire_hypostases_de_entite()` | 4 variantes + substring `hypostas` | Entite invisible dans le tableau |
| Synthese (prompt) | `tasks.py:_construire_prompt_synthese()` | `get("resume")` ou `get("Résumé")` | Pas de resume dans le prompt |

L'objectif : normaliser UNE FOIS au stockage, simplifier TOUTES les lectures.

---

## 2. Solution : normalisation en 2 couches deterministes

### Couche 1 — Normalisation des cles (100% succes, 0 cout)

**Fonction `normaliser_attributs_entite(attributes_dict) -> dict`**

Appelee dans `analyser_page_task()` juste AVANT le `ExtractedEntity.objects.create()`.
Transforme les cles du dict retourne par le LLM en snake_case sans accent :

```
"Résumé"     → "resume"
"Hypostases" → "hypostases"
"Mots-clés"  → "mots_cles"
"Statut"     → "statut"
"hypostase"  → "hypostases"  (singulier → pluriel normalise)
"résumé"     → "resume"      (accents retires)
```

**Algorithme** :

1. Pour chaque cle du dict, normaliser (minuscule + strip accents + remplacer `-` par `_`)
2. Mapper vers les 4 cles canoniques via un dictionnaire de synonymes :
   ```python
   SYNONYMES_CLES = {
       "resume": "resume", "résumé": "resume", "summary": "resume",
       "hypostase": "hypostases", "hypostases": "hypostases",
       "mots_cles": "mots_cles", "mots-cles": "mots_cles",
       "mots_clés": "mots_cles", "keywords": "mots_cles", "hashtags": "mots_cles",
       "statut": "statut", "statut_debat": "statut", "status": "statut",
   }
   ```
3. Cle inconnue → conserver telle quelle + log warning pour audit
4. Retourner le dict avec les cles normalisees

### Couche 2 — Normalisation des valeurs d'hypostases (99%+ succes, 0 cout)

**Fonction `normaliser_valeur_hypostase(valeur_brute) -> str`**

Appelee sur la valeur de `attributes["hypostases"]` apres la couche 1.

**Algorithme** :

1. Split par virgule → liste de fragments
2. Pour chaque fragment :
   a. Normaliser (minuscule, strip accents) → ex: `"Théorie"` → `"theorie"`
   b. Lookup exact dans les 30 hypostases connues → si trouve, garder
   c. Si pas trouve : **fuzzy match** via `difflib.get_close_matches(seuil=0.8)`
      - `"theeorie"` → `"theorie"` (typo corrigee)
      - `"metaphore"` → pas de match → supprimer + `logger.warning`
   d. Rejoindre par `, `

**La liste des 30 hypostases** est definie dans le PLAN.md (section "Geometrie du debat")
et dans le modele `HypostasisChoices` (`core/models.py`). La meme liste est deja
referencee dans `views_alignement.py:HYPOSTASE_VERS_FAMILLE`. La source de verite
pour cette phase sera `HYPOSTASE_VERS_FAMILLE` (deja existant, 30 entrees).

### Pourquoi pas de retry LLM

| Critere | Normalisation deterministe | Retry LLM |
|---------|---------------------------|-----------|
| Cout | 0 (CPU pur) | 2x tokens + 5-15s |
| Taux de succes cles | 100% | ~95% (meme prompt, meme tendance) |
| Taux de succes valeurs | 99%+ (fuzzy) | ~97% (peut re-halluciner) |
| Reproductibilite | 100% | Non deterministe |
| Complexite | ~50 lignes | ~100 lignes + timeout + retry logic |
| Latence | <1ms | 5-15s |

### Pourquoi difflib et pas embeddings cosine

| Critere | difflib (Levenshtein) | Cosine (embeddings) |
|---------|----------------------|---------------------|
| Dependance | stdlib Python | Modele d'embeddings |
| Latence | <1ms | 50-200ms |
| Pertinence | Excellente pour typos sur mots courts | Overkill (5-15 caracteres) |
| Faux positifs | `"metaphore"` → pas de match (correct) | Mapperait vers un faux positif |

Les hallucinations semantiques (`metaphore`, `biais`) ne doivent PAS etre mappees
vers une hypostase proche — ce serait une fausse correction. Elles doivent etre
supprimees et loguees. `difflib` ne les matche pas (distance trop grande), ce qui
est le comportement souhaite.

---

## 3. Fichiers a modifier

| Fichier | Changement |
|---------|-----------|
| `front/normalisation.py` (nouveau) | Fonctions `normaliser_attributs_entite()` + `normaliser_valeur_hypostase()` + constantes (`SYNONYMES_CLES`, `HYPOSTASES_CONNUES`) |
| `front/tasks.py` (analyser_page_task) | Appeler `normaliser_attributs_entite()` avant chaque `ExtractedEntity.objects.create()` |
| `front/views_alignement.py` | Simplifier `_extraire_hypostases_de_entite()` → juste `attributes.get("hypostases")` |
| `front/tasks.py` (_construire_prompt_synthese) | Simplifier → juste `attributes.get("resume")` |
| `hypostasis_extractor/templatetags/extractor_tags.py` | Simplifier `entity_json_attrs()` → lecture directe des cles canoniques, garder fallback pour les entites non migrees |
| `front/fixtures/demo_ia.json` | **FAIT (2026-03-21)** — PromptPieces #5/#6/#7 + ExtractionAttributes harmonises en snake_case |
| Migration `RunPython` | Normaliser les attributs des entites existantes en DB (idempotent) |
| `front/tests/test_phase29_normalize.py` | Tests unitaires |

---

## 4. Tests prevus

| Classe | Test | Quoi |
|--------|------|------|
| `NormalisationClesTest` | `test_cle_resume_accent_majuscule` | `{"Résumé": "x"}` → `{"resume": "x"}` |
| `NormalisationClesTest` | `test_cle_hypostases_singulier` | `{"hypostase": "x"}` → `{"hypostases": "x"}` |
| `NormalisationClesTest` | `test_cle_mots_cles_tirets_accent` | `{"Mots-clés": "x"}` → `{"mots_cles": "x"}` |
| `NormalisationClesTest` | `test_cle_inconnue_conservee` | `{"foo_bar": "x"}` reste `{"foo_bar": "x"}` |
| `NormalisationClesTest` | `test_dict_complet_4_cles` | Les 4 cles canoniques en sortie |
| `NormalisationClesTest` | `test_dict_vide` | `{}` → `{}` |
| `NormalisationClesTest` | `test_collision_cles_derniere_gagne` | `{"hypostase": "a", "Hypostases": "b"}` → comportement defini |
| `NormalisationValeurTest` | `test_hypostase_avec_accent` | `"Théorie"` → `"theorie"` |
| `NormalisationValeurTest` | `test_hypostases_multiples` | `"théorie, problème"` → `"theorie, probleme"` |
| `NormalisationValeurTest` | `test_hypostase_hallucinee_supprimee` | `"metaphore"` → supprimee (chaine vide ou absente) |
| `NormalisationValeurTest` | `test_hypostase_typo_corrigee` | `"theeorie"` → `"theorie"` |
| `NormalisationValeurTest` | `test_hypostase_valide_inchangee` | `"donnee"` → `"donnee"` |
| `NormalisationValeurTest` | `test_chaine_vide` | `""` → `""` |
| `NormalisationValeurTest` | `test_les_30_hypostases_connues` | Chacune des 30 passe sans modification |
| `IntegrationNormalisationTest` | `test_entite_creee_avec_cles_normalisees` | Mock LLM → `ExtractedEntity.attributes` a des cles canoniques |
| `MigrationDonneesTest` | `test_entites_existantes_normalisees` | `RunPython` → les vieilles entites ont des cles canoniques |
| `SimplificationAvalTest` | `test_alignement_lecture_directe` | `_extraire_hypostases_de_entite()` n'a plus besoin de variantes |
| `SimplificationAvalTest` | `test_prompt_synthese_lecture_directe` | `_construire_prompt_synthese()` lit `attributes["resume"]` directement |

---

## 5. Criteres de validation

- [ ] `manage.py check` → 0 erreur
- [ ] Toutes les nouvelles entites ont des cles normalisees (`resume`, `hypostases`, `mots_cles`, `statut`)
- [ ] Les entites existantes en DB sont migrees (migration `RunPython`)
- [ ] Le tableau d'alignement fonctionne avec les entites normalisees (plus de variantes de casse)
- [ ] Les cartes d'extraction s'affichent correctement (regression zero)
- [ ] Le prompt de synthese lit `attributes["resume"]` sans fallback
- [ ] Les hypostases hallucinees sont loguees en `logger.warning` (pas d'erreur silencieuse)
- [ ] Les PromptPieces du prompt Hypostasia sont en snake_case (FAIT)
- [ ] Les exemples few-shot (ExtractionAttribute) sont en snake_case (FAIT)
- [ ] Test navigateur : analyser un texte → verifier les cles en DB via shell

---

## 6. Verification navigateur

1. Charger les fixtures : `loaddata front/fixtures/demo_ia.json`
2. Analyser un texte avec Gemini (`/lire/17/` → Analyser)
3. En shell : `ExtractedEntity.objects.filter(job__page_id=17).last().attributes.keys()`
   → doit retourner `dict_keys(['resume', 'hypostases', 'mots_cles', 'statut'])`
4. Ouvrir le tableau d'alignement entre V1 et V2 → les hypostases s'affichent (pas les statuts)
5. Lancer une synthese → le prompt contient les resumes (verifier dans les logs Celery)

---

## 7. Liens avec le PLAN.md et les phases existantes

### Sections du PLAN concernees

| Section PLAN | Impact |
|---|---|
| 1.5 — Framework d'extraction configurable | La normalisation s'insere dans le pipeline existant (`analyser_page_task`) sans changer l'architecture LangExtract |
| 1.8 — Charte visuelle (`attr_0` a `attr_3`) | Les `entity_json_attrs()` du template tag sont simplifies — lecture directe au lieu de normalisation a la volee |
| Etape 5.6 — Synthese assistee | Le prompt de synthese (`_construire_prompt_synthese`) beneficie directement des cles canoniques |
| Etape 6.2 — Alignement cross-documents | Le tableau d'alignement (`views_alignement.py`) n'a plus besoin de chercher 4 variantes de casse |
| Geometrie du debat (principes) | La facette "structurelle" (alignement par hypostases) est fiabilisee par la normalisation des valeurs |

### Position dans le graphe de dependances

La PHASE-29-normalize est **independante** — elle n'a pas de prerequis strict.
Elle ameliore toutes les couches existantes (cartes, alignement, synthese) sans
en dependre. Elle beneficie a toutes les phases suivantes.

```
Independant ──► PHASE-29-normalize (normalisation attributs)
                    ├── ameliore PHASE-18 (alignement)
                    ├── ameliore PHASE-28-light (synthese)
                    ├── facilite PHASE-27c (SourceLinks)
                    └── facilite PHASE-27d (fil reflexion)
```

### Probleme identifie dans le PLAN (section 1.5)

> "La synthese IA ne source pas ses affirmations : le LLM recoit extraction +
> commentaires mais sa reponse n'est pas liee paragraphe par paragraphe aux
> sources qui l'ont alimentee"

La PHASE-29-normalize ne resout pas ce probleme (c'est le role de 27c/27d), mais elle
le rend plus facile a traiter : avec des cles canoniques, les futures couches de
provenance pourront lire `attributes["hypostases"]` sans incertitude.
