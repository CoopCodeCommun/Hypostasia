# Réécriture direct → indirect en français — dossier de conception

> **Document EXTERNE**, fourni par le mainteneur le 23 août 2026. Recherche menée
> hors de ce dépôt ; dépôts Hugging Face vérifiés par API à cette date.
>
> **Il n'est pas une spec d'Hypostasia.** Ce qu'il devient une fois confronté à notre
> code — ce qui est déjà là, ce que nos invariants imposent, et le risque
> supplémentaire qu'il ne pouvait pas connaître (une distorsion de certitude CHANGE
> L'HYPOSTASE) — est écrit dans
> `PLAN/TODO/2026-08-23-ressusciter-l-analyseur-reformuler.md`.
>
> Conservé ici parce que la spec le cite abondamment et qu'un dossier de recherche
> qui ne vit que dans une conversation est perdu à la session suivante.

---

## 1. Le résultat qui doit piloter toute la conception

La contrainte « ne pas halluciner » n'est pas le bon risque à surveiller.

### Le vrai mode de défaillance : la distorsion de certitude

*« From "May" to "Is": Certainty Distortion in Language Model Rewriting »*
(arXiv 2606.07951) : le contenu propositionnel est préservé, **le degré de confiance
ne l'est pas.**

| Mesure | Valeur |
|---|---|
| Distorsion en réécriture au niveau phrase | **30 – 49,5 %** |
| En réécriture journalistique | jusqu'à **75 %** |
| Biais vers l'**inflation** de certitude | **1,5 à 2×** plus fréquent que la déflation |
| Accumulation en boucle | +20 % après 1 itération, **+40 % après 5** |
| Effet du prompt « preserve certainty » | 50,6 % → 40,1 % — insuffisant |
| **Effet de la température** | **quasi nul** |

« je pense qu'il faudrait peut-être réformer ça » devient « il faut réformer cela ».
Le contenu est là, **l'engagement du locuteur a disparu**. Aucune métrique de
similarité ne le détecte : BERTScore rend 0,95.

### Le second résultat, et il est français

GDN-CC (arXiv 2601.14944, ACL 2026, ISIR/Sorbonne) a fait la même tâche : réécrire des
contributions du Grand Débat National en énoncés auto-suffisants. Classement de 100
corrections humaines :

| Type d'erreur des LLM zero-shot | Part |
|---|---|
| **Sur-analyse** — ajout d'une analyse ou conclusion absente du texte | **72 %** |
| Mauvaise formulation | 13 % |
| Omission d'information importante | 12 % |
| Sur-spécificité | 3 % |

> *« all four models consistently struggle with over-analysis (72 % of all errors),
> even when specifically prompted not to suppress any information not expressed in
> the text »*

> *« a significant part of the human annotation effort was to remove information added
> by the LLMs »*

> **« Finetuned models reduced LLM over-analysis errors from 72 % to 2 %. »**

**Facteur 36, par un simple SFT.** Le prompt ne suffit pas — mesuré, en français.

---

## 2. Les trois réglages gratuits

### 2.1 Greedy ou beam search, jamais de sampling

*Faithfulness-Aware Decoding Strategies* (EACL 2023) :

| Jeu | Métrique | Beam k=10 | Nucleus p=0,9 |
|---|---|---|---|
| CNN/DM | FactCC | **84,23** | **54,05** |
| CNN/DM | QuestEval | 60,03 | 56,43 |
| XSum | taux d'erreur DAE | 63,49 | 76,20 |

Confirmé sur 37 modèles (125M–70B) par *The Mirage of Hallucination Detection*.
Bénéfice secondaire décisif : **le greedy est reproductible.**

### 2.2 Trois contrôles symboliques, zéro modèle

| Contrôle | Ce qu'il attrape |
|---|---|
| **Inventaire** : entités nommées, nombres, dates présents en source doivent l'être en sortie | 4 des 11 catégories d'hallucination de la taxonomie GEM |
| **Modalité** : lexique fermé de marqueurs épistémiques (*peut-être, je crois, il me semble, sans doute, probablement, devrait, faudrait, pourrait*). Présent en source, absent en sortie → **rejet** | **toute la distorsion de certitude** |
| **Polarité** : négations et antonymes | Negation, Antonym |

Déterministes, sans latence, **explicables à un contradicteur**.

### 2.3 Le prompt de LequeuISIR, réutilisable tel quel

> *« Je vais te donner un segment de texte d'opinions en français, ainsi que le texte
> initial dont il est tiré. […] Tu dois aussi ajouter le contexte présent dans le texte
> initial si il est important pour la compréhension du segment. […] **Si le segment est
> déjà clair et bien écrit, tu dois simplement le recopier.** Tu dois ressortir
> UNIQUEMENT la clarification du segment et rien d'autre. »*

La clause « si c'est déjà bon, recopie » est le garde-fou anti-embellissement le plus
efficace à coût nul.

---

## 3. L'architecture proposée : le modèle décide, les règles exécutent

### Ce qui relève d'une table, pas d'un modèle

| Transformation | Règle |
|---|---|
| **Pronoms** | je → il/elle · tu → il/elle · nous → ils · mon → son · notre → leur |
| **Concordance des temps** *(si le verbe introducteur est au passé)* | présent → imparfait · passé composé → plus-que-parfait · futur → conditionnel présent. Imparfait, plus-que-parfait, conditionnel **invariants** |
| **Déictiques** | ici → là · aujourd'hui → ce jour-là · hier → la veille · demain → le lendemain · maintenant → alors · ce…-ci → ce…-là · ça → cela |
| **Subordination** | déclaration → *que* · question totale → *si* · question partielle → mot interrogatif · impératif → *de* + infinitif |

💡 Si le verbe introducteur est au **présent** (« il pense que… »), **aucune
concordance ne s'applique**. Probablement le cas à imposer par défaut sur du verbatim.

### Ce qui justifie un modèle

Résoudre le référent des pronoms · segmenter l'oral spontané · **choisir le verbe
introducteur** (c'est là que se loge la distorsion de certitude → **liste fermée**) ·
traiter les sources qui ne sont pas des phrases bien formées.

### Le montage

```
bloc oral
   │
   ├─ [LLM sous grammaire GBNF] ──► sortie STRUCTURÉE, jamais du texte libre :
   │                                  { locuteur, acte_de_parole,
   │                                    verbe_introducteur ∈ liste_fermée,
   │                                    empan_rapporté, mapping_pronoms }
   │
   ├─ [Grew + spaCy fr + mlconjug3] ─► concordance, déictiques, morphologie
   │
   └─ [contrôles symboliques + NLI] ─► vérification, puis accepte ou rejette
```

**Le modèle ne produit jamais de texte libre.** L'invention devient structurellement
impossible, pas seulement improbable.

Outils : Grew (réécriture de graphes UD, INRIA/LORIA), spaCy français, mlconjug3 ou
verbecc.

### Variante plus légère : le format d'éditions

```json
[{"remplacer": "Je pense", "par": "Selon lui,"},
 {"remplacer": "ça",       "par": "cela"}]
```

**Tout ce qui n'est pas explicitement édité est copié par construction**, pas par bonne
volonté du modèle. Et la liste s'affiche à un contradicteur.

### ⚠️ Ce qu'il ne faut PAS faire : contraindre le vocabulaire à la source

Le style indirect exige du vocabulaire absent de la source (*selon, lui, que, cela*, et
les formes fléchies). Et le masquage déforme la distribution : *Grammar-Aligned
Decoding* (NeurIPS 2024) montre que le décodage contraint standard ne produit pas la
distribution du modèle conditionnée sur la grammaire. **La contrainte utile est
structurelle, pas lexicale.**

---

## 4. Le choix du modèle

⚠️ **Aucun classement français à jour n'existe.** `le-leadboard/OpenLLMFrenchLeaderboard`
est en `BUILD_ERROR`, résultats figés au 01/08/2025 ; celui du gouvernement tourne mais
son code date du 16/06/2025. Avertissement des auteurs de Gaperon (ALMAnaCH/Inria) :
*« filtering for linguistic quality enhances text fluency and coherence but yields
subpar benchmark results »* — **la qualité de génération et les scores de benchmark
divergent.**

| Modèle | Params | Licence | Q4 réel | MMMLU | Contexte |
|---|---|---|---|---|---|
| **`google/gemma-4-12B-it`** | 11,95 B | **Apache 2.0** | **7,12 Go** | **83,4** | 262k |
| `mistralai/Ministral-3-14B-Instruct-2512` | 14 B | Apache 2.0 | 8,24 Go | — | 262k |
| `Qwen/Qwen3.5-9B` | 9 B | Apache 2.0 | 5,68 Go | 81,2 | 262k |
| `google/gemma-4-31B-it` | 31 B | Apache 2.0 | 17,29 Go | 88,4 | 262k |

**Choix du dossier : Gemma 4 12B-it** — Apache 2.0 et non gated, 7,12 Go en Q4 (6,98
avec les GGUF QAT officiels), MMMLU 83,4, écosystème mature.

**Ministral-3-14B** est le pari français : seul éditeur qui liste explicitement le
français dans les métadonnées de tout son catalogue, et meilleur en génération libre
(Arena Hard 0,551 contre 0,436 pour Gemma3-12B) — ce qui compte plus que MMLU ici.

**À écarter** : gpt-oss-20b (MMMLU 69,7, 11,6 Go incompressibles) · Muse Glimmer 30B
(non évalué sur toutes ses langues) · Luciole 23B (post-training « almost entirely on
English data », zéro benchmark chiffré) · BARThez / mT5-fr (2021-2024) · Claire-7B
(CC-BY-NC-SA, 2048 tokens — mais son **corpus** est une bonne référence).

### Le modèle qui fait déjà presque ça

**`LequeuISIR/AU-clarification_gemma-2-9b-it`** : fine-tuné sur GDN-CC, BERTScore 0,86
/ ROUGE-L 0,60 contre 0,81 / 0,45 pour GPT-4.1 zero-shot, préféré 66 % contre 26 %.

⚠️ **Aucune licence déclarée**, et il dérive de `gemma-2-9b-it` sous Gemma Terms of Use.

**La bonne manœuvre : refaire leur fine-tuning sur un modèle Apache 2.0.** Dataset
(`LequeuISIR/GDN-CC`, 2 285 unités annotées à la main ; `GDN-CC-large`, 300 748
automatiques) et plateforme d'annotation publics. Budget de référence : ~100 GPU-heures
H100 pour l'ensemble de leurs expériences — quelques heures pour un run, LoRA sur une
L4 ou ~50 € de location.

---

## 5. Le vérificateur

### N'utilise pas BERTScore

*Mind the Style Gap* : les métriques de similarité corrèlent avec l'humain **uniquement
parce que les jeux de test contiennent trop peu d'erreurs de préservation de contenu**.
Sur un jeu difficile, corrélations « faibles à négatives ». Dans GDN-CC, l'écart
zero-shot → fine-tuné vaut **0,45 → 0,60 en ROUGE-L** mais seulement **0,81 → 0,86 en
BERTScore**.

### ⚠️ Le piège spécifique

La taxonomie GEM compte 11 catégories d'hallucination, dont **Pronoun** et **Tense** —
**exactement les deux axes que la transformation doit modifier délibérément**. Un
vérificateur générique signalerait les transformations correctes comme des
hallucinations.

### Ce qu'il faut construire

Aucun équivalent français d'AlignScore ou MiniCheck. Briques disponibles :
`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`,
`cmarkea/distilcamembert-base-nli`.

**Implication bidirectionnelle** : source → réécriture détecte l'**ajout**, réécriture →
source détecte la **perte**. Un seul sens ne détecte que la moitié des problèmes.

Pour l'entraîner : injecter mécaniquement les 11 types GEM plus une catégorie
« certitude » dans des paires correctes (méthode TrueBrief.DataGen) — on obtient à la
fois le vérificateur et les données DPO.

Sur la paraphrase, les baselines NLI atteignent **F1 0,90–0,92**, au-dessus de
Llama3-70B et Mixtral 8×22B. **Un petit NLI dédié bat un gros LLM juge.**

---

## 6. 🔴 Ne pas boucler

*Verify, Repair, Repeat, or Stop?* (arXiv 2607.17641) :

- **il existe un régime où réparer est nuisible** — la validité monte, atteint un pic,
  puis **décline durablement** ;
- frontière de décision **b\* = α/(α+β)** ; dans leur système réel **β ≈ 0,94** — la
  réparation abîme des sorties valides presque à chaque occasion ;
- **le taux de vérification peut monter pendant que la qualité réelle baisse.**

Combiné à l'accumulation du § 1 (+40 % après 5 tours) :

> **Au plus un retry, puis escalade ou abandon.**

Si la deuxième tentative échoue, **renvoyer le texte en style direct inchangé** avec un
marqueur « non transformé ». Un bloc laissé en citation directe est un échec
acceptable ; un bloc réécrit trois fois jusqu'à passer le vérificateur est un risque
juridique.

---

## 7. Le plan proposé par le dossier

**Semaine 1 — le gratuit** : greedy ou beam k=4-10 ; les trois contrôles symboliques
(~100 lignes de Python) ; le prompt LequeuISIR + clause de préservation de la
certitude ; Gemma 4 12B-it en Q4.

**Semaines 2-3 — mesurer** : annoter 100 à 200 blocs, mesurer sur-analyse et distorsion
de certitude sur la baseline. *Le papier du § 1 ne teste que l'anglais — l'existence du
phénomène en français est une extrapolation raisonnable, non mesurée. C'est
probablement la mesure la plus rentable à faire.*

**Mois 2 — le vrai gain** : 500 à 2 000 paires, SFT ou LoRA. C'est le passage 72 % → 2 %.
Métriques : **ROUGE-L** (pas BERTScore) + juge LLM sur un axe unique « contenu ajouté
oui/non ».

**Plus tard** : la sortie structurée GBNF + règles Grew (§ 3) ·
`PrefixNLI` / `MiniTruePrefixes` (+7,5 points de fidélité sur un 1B, ×2,9 de latence ;
+2,9 seulement sur un 8B — les petits modèles ont plus à gagner d'un garde-fou externe).

---

## 8. Ce qui n'a PAS été vérifié

1. **Aucun travail de TAL sur la transformation automatique direct → indirect**,
   français ou anglais. Le TAL français **détecte** le discours rapporté (CamemBERT,
   96 % F1) mais ne le **transforme** jamais.
2. **La distorsion de certitude n'a été mesurée qu'en anglais.**
3. **Aucun taux de rejet publié** pour une boucle réécriture → vérification NLI.
4. **Aucune évaluation indépendante de Gemma 4, Qwen3.5/3.6 ou Ministral 3
   spécifiquement sur le français** en août 2026.
5. **Les benchmarks de Luciole ne sont publiés qu'en images PNG.**
6. **Les articles francophones sur ces modèles sont du contenu SEO avec des erreurs
   vérifiables.** Ne s'appuyer sur aucun.
7. **Le décodage contraint sur le français est moins étudié**, et les problèmes de
   tokenisation risquent d'être pires sur les élisions (*l'*, *qu'*, *d'*), partout dans
   le style indirect.

---

## 9. Sources

**Le risque réel** — [Certainty Distortion](https://arxiv.org/abs/2606.07951) ·
[GDN-CC (ACL 2026)](https://arxiv.org/abs/2601.14944) ·
[Intrinsic Hallucinations in Paraphrasing (GEM 2025)](https://aclanthology.org/2025.gem-1.13.pdf) ·
[Short-form Text Rewriting with Phi Silica](https://arxiv.org/abs/2606.00462)

**Décodage** — [Faithfulness-Aware Decoding (EACL 2023)](https://aclanthology.org/2023.eacl-main.210.pdf) ·
[Mirage of Hallucination Detection (EMNLP 2025)](https://aclanthology.org/2025.findings-emnlp.1035.pdf) ·
[Grammar-Aligned Decoding (NeurIPS 2024)](https://arxiv.org/abs/2405.21047) ·
[The Parser Already Knows](https://arxiv.org/html/2608.10137) ·
[PrefixNLI](https://arxiv.org/html/2511.01359) ·
[llama.cpp GBNF](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)

**Métriques** — [Mind the Style Gap](https://arxiv.org/html/2502.15022v3) ·
[Do Automatic Factuality Metrics Measure Factuality?](https://arxiv.org/html/2411.16638v4) ·
[MiniCheck (EMNLP 2024)](https://arxiv.org/abs/2404.10774) ·
[mDeBERTa-v3-xnli](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7) ·
[distilcamembert-base-nli](https://huggingface.co/cmarkea/distilcamembert-base-nli)

**Boucle** — [Verify, Repair, Repeat, or Stop?](https://arxiv.org/html/2607.17641v1) ·
[TrueBrief](https://arxiv.org/html/2601.04212) ·
[Optimising Factual Consistency via Preference Learning](https://aclanthology.org/2025.findings-emnlp.940.pdf)

**Modèles** — [gemma-4-12B-it](https://huggingface.co/google/gemma-4-12B-it) ·
[GGUF QAT](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf) ·
[Ministral-3-14B](https://huggingface.co/mistralai/Ministral-3-14B-Instruct-2512) ·
[Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) ·
[AU-clarification_gemma-2-9b-it](https://huggingface.co/LequeuISIR/AU-clarification_gemma-2-9b-it) ·
[dataset GDN-CC](https://huggingface.co/datasets/LequeuISIR/GDN-CC) ·
[GDNCorpusClarification](https://github.com/LequeuISIR/GDNCorpusClarification) ·
[Luciole-23B](https://huggingface.co/OpenLLM-France/Luciole-23B-Instruct-1.1)

**Français : outils et corpus** — [Grew](https://grew.fr/) ·
[spaCy fr](https://spacy.io/models/fr) ·
[mlconjug3](https://github.com/Ars-Linguistica/mlconjug3) ·
[verbecc](https://github.com/bretttolbert/verbecc) ·
[Direct Speech in French Narratives](https://arxiv.org/html/2306.15634v1) ·
[FRACAS (LREC 2024)](https://arxiv.org/abs/2309.10604) ·
[french_bench](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/french_bench/README.md)
