# Inspiration Atomic — Spec de refonte Hypostasia

> Spec de refonte d'Hypostasia inspirée d'[Atomic](https://github.com/kenforthewin/atomic),
> KB personnelle écrite en Rust open source. Objectif : combler les manques structurels
> d'Hypostasia (RAG/embeddings absent, sourçage des synthèses inexistant, pipeline
> d'extraction trop verbeux) en adoptant les patterns éprouvés d'Atomic, tout en
> préservant et renforçant la dimension collective d'Hypostasia (commentaires, partage,
> débat) qu'Atomic n'a pas.
>
> **Sens de l'inspiration : Atomic → Hypostasia uniquement.**
>
> Date de rédaction : 2026-04-26. Version Atomic référencée : v1.28.1.
> Stratégie validée : **refactoring profond, pas from scratch.**

---

## 0. Comment lire ce document

### Pour un humain qui découvre

1. Lire la **section 1** (résumé exécutif des décisions tranchées) pour la vue d'ensemble
2. Lire la **section 2** (stratégie d'implémentation) pour comprendre ce qui change
3. Lire la **section 3** (nouveau modèle conceptuel) pour saisir le changement de paradigme
4. Parcourir les axes (sections 4 à 9) selon centres d'intérêt

### Pour un agent IA qui implémente

1. Lire le doc en entier une fois pour le contexte
2. Identifier la phase à implémenter via **Annexe A** (squelettes de phases prêts à dérouler)
3. Pour chaque phase, lire la section correspondante du doc + le squelette
4. Référencer **Annexe B** (mapping fichiers Atomic ↔ Hypostasia) pour les détails techniques
5. Référencer **Annexe D** (continuation de session) si on démarre froid

### Conventions de ce document

- Chemins absolus : `/mnt/tank/Gits/Hypostasia/` (Hypostasia) et `/mnt/tank/Gits/atomic/` (Atomic, lecture seule)
- Snippets en Python/Django pour Hypostasia, Rust pour Atomic à titre conceptuel
- Conventions de code Hypostasia (skill `stack-ccc`) : ViewSet explicite, DRF Serializers,
  HTMX, noms verbeux, commentaires bilingues FR/EN

---

## 1. Décisions tranchées — résumé exécutif

| # | Décision | Justification | Impact |
|---|---|---|---|
| 1 | **Adopter "1 chunk markdown-aware = 1 extraction"** (option A stricte) | LangExtract sur-extrait (~30/page), UX surchargé, classification meilleure sur paragraphe que phrase | Refonte pipeline extraction |
| 2 | **Supprimer LangExtract** complètement | Plus de raison d'être avec option A. Élimine workarounds, dette `LANGEXTRACT_OVERRIDES.md`, verrou Gemini/OpenAI | -1 dépendance critique |
| 3 | **Sélection manuelle conservée** pour la précision fine | Permet à l'humain de promouvoir une phrase précise en extraction libre quand chunk trop dense (philo) | Code existant, zéro nouveau |
| 4 | **Sourçage automatique `[N]` des synthèses** (pattern Atomic) | Résout 27c/27d sans travail manuel, pas d'hallucination d'identifiant, byte-exact en mode incrémental | PHASE-30 |
| 5 | **Chunking markdown-aware** avec paramètres Hypostasia (300-500 tokens cibles, 0 overlap) | Préserver les unités sémantiques tant que la taille permet ; pas d'overlap car 1 chunk = 1 unité de débat | PHASE-31 |
| 6 | **OpenRouter + instructor** pour tout LLM | Une clé, 200+ modèles, structured output via Pydantic, retry auto | PHASE-32 |
| 7 | **RAG via pgvector** (PostgreSQL déjà en place) | Recherche sémantique, alignement, doublons, chat agentique | PHASES 33-35 |
| 8 | **Section_ops pour update incrémental** des synthèses | Préserve `[N]` byte-exact, économise tokens, audit trail | PHASE-36 |
| 9 | **6 idées sociales × RAG** en backlog priorisable | Différenciation produit, capitalise sur dimension collective | PHASE-37+ |
| 10 | **Refactoring profond, pas from scratch** | ~75% du code reste utile, dette concentrée sur pipeline extraction | 4-5 phases sur 2-3 mois |

### Plan B documenté

Si après l'alpha, l'option A se révèle insuffisante (utilisateurs trouvent les chunks
trop gros, sélection manuelle trop pénible), pivot vers **double passe** : extraction
verbeuse style LangExtract + consolidation LLM (pattern type `TAG_CONSOLIDATION_PROMPT`
d'Atomic). Détails section 10.

---

## 2. Stratégie d'implémentation : refactoring profond

### Pourquoi pas from scratch

- **Dette technique concentrée**, pas systémique. Hypostasia est bien structurée (skill
  stack-ccc respecté, modèles propres, ~865 tests). La dette se trouve sur le pipeline
  d'extraction et la normalisation tardive — ce sont des îlots refactorables.
- **Capital conservé** : 75% du code reste utile (voir tableau ci-dessous).
- **Second-system effect** : tendance à sur-ingéniérer la v2 quand on a la liberté de la
  page blanche. Pour un solo en alpha, le coût d'opportunité d'un from scratch
  (6-12 mois) est massif comparé au refactoring (2-3 mois).
- **Le from scratch ne serait justifié que si on changeait de stack** (ex: Django →
  FastAPI/Litestar) ou d'architecture (ex: passage en multi-tenant via django-tenants
  dès le socle). Ce n'est pas le cas.

### Ce qui dégage

| Élément | Volume estimé |
|---|---|
| Dépendance LangExtract et tous ses workarounds | -1 dépendance, -200 lignes |
| `AnnotateurAvecProgression` (front/tasks.py) | -200 lignes |
| Auto-wrap JSON arrays | -50 lignes |
| `PLAN/LANGEXTRACT_OVERRIDES.md` | Document entier dépréqué |
| **PHASE-29-normalize** complète | -245 lignes de phase + tout le code de normalisation post-hoc |
| `entity_json_attrs()` avec ses fallbacks | -60% de complexité |
| `_extraire_hypostases_de_entite()` avec ses 4 variantes | -80% de complexité |
| **PHASE-27c (SourceLinks manuels)** | Phase entière → automatisée par `[N]` |
| Champs `start_char`/`end_char` sur ExtractedEntity | Schéma simplifié (positions dérivées du chunk) |

### Ce qui reste

| Domaine | Conservation |
|---|---|
| Identité produit (hypostases, statuts, cycle délibératif) | 100% |
| Design system (3 polices, palette Wong, formes daltonien-safe, responsive) | 100% |
| Couche sociale (auth, partage, visibilité 3 niveaux, invitations, crédits Stripe) | ~95% |
| Infrastructure Docker + Celery + Channels + Redis + PostgreSQL | 100% |
| Modèles métier (User, Dossier, Page, Commentaire, AIModel, Analyseur, ExtractionJob) | ~85% |
| Vues HTMX + templates (lecture, drawer, dashboard, alignement, comparaison V1/V2) | ~80% |
| Tests (~865) | ~70% réutilisables avec adaptations |
| Conventions stack-ccc | 100% |
| PHASE-26b (bibliothèque d'analyseurs admin-only) | 100% |
| PHASE-26g (drawer hub d'analyse, WS, estimation coût) | 90% |

### Ce qui change profondément sans disparaître

| Composant | Refactor |
|---|---|
| Pipeline d'extraction (`front/tasks.py:analyser_page_task`) | Réécrit sans LangExtract, ~150 lignes |
| Modèle ExtractedEntity | + `chunk_index` FK vers PageChunk, validation Pydantic stricte sur `attributes` |
| PHASE-09 pastilles | Position vient du chunk (PageChunk.start_char), refactor template |
| PHASE-28-light synthèse | + sourçage `[N]` automatique |
| PHASE-18 alignement | Garder structurel + ajouter mode sémantique (Axe 6) |
| PHASE-27a/b traçabilité | Modèles `PageEdit` restent ; SourceLink étendu avec `citation_index` |

### Calendrier indicatif

Ordre suggéré, à valider phase par phase :

1. **PHASE-31** (chunker markdown-aware) — 1-2 semaines. Prérequis pour 38.
2. **PHASE-32** (OpenRouter + instructor) — 3-5 jours.
3. **PHASE-38** (refonte pipeline extraction Atomic-style) — 2-3 semaines. Migration data.
4. **PHASE-30** (sourçage `[N]` synthèses) — 1 semaine.
5. **PHASE-33** (RAG socle pgvector + embedding pipeline) — 1-2 semaines.
6. **PHASE-34** (RAG features : recherche, doublons, alignement sémantique) — 2-3 semaines.
7. **PHASE-36** (update incrémental section_ops) — 1 semaine.
8. **PHASE-35** (chat agentique) — 2-3 semaines.
9. **PHASE-37** (sociales × RAG) — selon priorité, 1-2 semaines par sous-phase.

Total estimé : **2-3 mois pour la refonte complète** + 1-2 mois pour les sociales.

---

## 3. Le nouveau modèle conceptuel

### Architecture en 3 couches

```
┌──────────────────────────────────────────────────────────────────┐
│  Page                                                            │
│  ──────                                                          │
│  Le document complet (titre, contenu, métadonnées, parent_page)  │
└─────────────────────────┬────────────────────────────────────────┘
                          │ 1-N (chunking markdown-aware)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  PageChunk                                                       │
│  ──────────                                                      │
│  Une unité sémantique du document : section, paragraphe,         │
│  bloc de transcription. Position connue (start_char/end_char).   │
│  Embedding stocké pour le RAG (vector(1536)).                    │
└─────────────────────────┬────────────────────────────────────────┘
                          │ 1-1 (extraction Atomic-style)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  ExtractedEntity                                                 │
│  ──────────────                                                  │
│  Une classification du chunk : hypostases, résumé, mots-clés,    │
│  statut de débat. UNE par chunk pour les extractions auto.       │
│  Plus 0-N extractions manuelles (sans chunk_index, positions     │
│  libres) pour les cas où l'humain veut affiner.                  │
└──────────────────────────────────────────────────────────────────┘
```

### Différence vs modèle actuel

| Aspect | Modèle actuel (LangExtract) | Modèle cible (Atomic-style) |
|---|---|---|
| Granularité | ~30 extractions par page | 5-10 extractions auto + 0-5 manuelles |
| Position | start_char/end_char sur chaque extraction | Sur PageChunk uniquement, dérivée pour extractions auto |
| Cohérence inter-extractions | Faible (chacune isolée) | Forte (chunks partitionnent le doc) |
| Validation | LangExtract + workarounds | Pydantic + JSON Schema natif via instructor |
| Coût LLM | ~30 appels par page (multi-pass) | 5-10 appels par page (1 par chunk) |

### Conséquences UX

- **Pastilles dans la marge** : 5-10 au lieu de 30. Scan visuel évident.
- **Cartes inline** : moins denses, plus lisibles, naturellement organisées par section thématique.
- **Drawer vue liste** : 5-10 cartes scrollables au lieu de 30+, débats focalisés.
- **Dashboard de consensus** : ratios sur 5-10 unités plus intelligibles que sur 30.
- **Sélection manuelle** reste accessible (touche `S` ou via popup contextuelle) pour
  promouvoir une phrase précise en extraction supplémentaire.

---

## 4. Pipeline détaillé

### 4.1 Chunking markdown-aware

Inspiré de `crates/atomic-core/src/chunking.rs` (méthode rasoir : préserver l'unité
sémantique tant que la taille permet).

#### Méthode rasoir

```
1. Parse markdown en blocs (Header, Paragraph, List, CodeBlock) via markdown-it-py
2. Code blocks JAMAIS coupés (intégrité syntaxique)
3. Headers créent des coupures naturelles
4. Merge des petits blocs adjacents tant qu'on reste sous max
5. Si un bloc dépasse max → split par phrases ('. ', '! ', '? ', '…')
6. Si une phrase dépasse max → hard split par caractères (UTF-8 safe)
7. Cas spécial : 1 bloc <bloc-transcription> = 1 chunk (ne jamais merger)
```

#### Paramètres Hypostasia

```python
# core/chunking.py

CHUNK_TARGET_TOKENS = 400         # Cible : un paragraphe substantiel
CHUNK_MIN_TOKENS = 80             # Sinon merge avec le voisin
CHUNK_MAX_TOKENS = 800            # Au-delà, débat perd en focus
CHUNK_OVERLAP_TOKENS = 0          # Pas d'overlap : 1 chunk = 1 unité de débat
TOKENIZER = "cl100k_base"         # Compatible OpenAI/text-embedding-3-small
```

**Différences vs Atomic** : Hypostasia vise des unités plus petites (400 vs 800 tokens
cible) parce qu'on veut des unités de débat, pas des chunks d'embedding. Pas d'overlap
car un commentaire doit être attaché à UN chunk précis.

#### Implémentation

```python
# core/chunking.py

from dataclasses import dataclass
import tiktoken
from markdown_it import MarkdownIt

@dataclass
class Chunk:
    """Un chunk markdown-aware avec position dans le source.
    / A markdown-aware chunk with position in the source."""
    content: str
    start_char: int
    end_char: int
    chunk_index: int
    metadata: dict   # ex: {"locuteur": "X", "timestamp": "00:12:34"}

def chunker_markdown(
    texte: str,
    target_tokens: int = CHUNK_TARGET_TOKENS,
    min_tokens: int = CHUNK_MIN_TOKENS,
    max_tokens: int = CHUNK_MAX_TOKENS,
) -> list[Chunk]:
    """
    Decoupe un texte markdown en chunks respectant headers, paragraphes, code blocks.
    / Split markdown text into chunks respecting headers, paragraphs, code blocks.
    """
    encoder = tiktoken.get_encoding("cl100k_base")

    # 1. Parse markdown en blocs avec leurs positions char
    # / Parse markdown into blocks with char positions
    blocks = _parser_blocks_markdown(texte)

    # 2. Detecter les blocs <bloc-transcription> qui sont atomiques
    # / Detect <bloc-transcription> blocks which are atomic
    blocks = _isoler_blocs_transcription(blocks)

    # 3. Merge des petits blocs, split des gros
    # / Merge small blocks, split big ones
    chunks = _merger_et_splitter(blocks, target_tokens, min_tokens, max_tokens, encoder)

    return chunks

def chunker_transcription(blocs_transcription: list) -> list[Chunk]:
    """
    Cas special : 1 bloc de transcription = 1 chunk (= 1 tour de parole).
    / Special case: 1 transcription block = 1 chunk (= 1 speaker turn).
    """
    chunks = []
    cursor = 0
    for i, bloc in enumerate(blocs_transcription):
        chunks.append(Chunk(
            content=bloc.texte,
            start_char=cursor,
            end_char=cursor + len(bloc.texte),
            chunk_index=i,
            metadata={
                "locuteur": bloc.locuteur,
                "timestamp": bloc.timestamp,
            },
        ))
        cursor += len(bloc.texte) + 2  # +2 pour le \n\n separateur
    return chunks
```

#### Modèle Django

```python
# core/models.py

class PageChunk(models.Model):
    """Un chunk markdown-aware d'une Page, avec position dans le source.
    / A markdown-aware chunk of a Page, with position in the source."""
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.IntegerField()
    content = models.TextField()
    start_char = models.IntegerField()
    end_char = models.IntegerField()
    metadata = models.JSONField(default=dict)
    embedding = VectorField(dimensions=1536, null=True, blank=True)   # Axe 6 (RAG)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["page", "chunk_index"]
        unique_together = [("page", "chunk_index")]
```

### 4.2 Extraction (1 par chunk) via Pydantic + instructor

#### Schema Pydantic

```python
# hypostasis_extractor/schemas.py

from pydantic import BaseModel, Field
from typing import Literal

# Les 30 hypostases de la geometrie des debats (cf. core/models.py:HypostasisChoices)
# / The 30 hypostases of the debate geometry
HYPOSTASES_VALIDES = Literal[
    "paradigme", "objet", "principe", "domaine", "loi", "phenomene",
    "variable", "variance", "indice", "donnee", "methode", "definition",
    "hypothese", "probleme", "theorie", "approximation", "classification",
    "aporie", "paradoxe", "formalisme", "evenement", "variation", "dimension",
    "mode", "croyance", "invariant", "valeur", "structure", "axiome", "conjecture",
]

STATUTS_DEBAT = Literal[
    "nouveau", "consensuel", "discutable", "discute",
    "controverse", "non_pertinent",
]

class HypostaseExtraction(BaseModel):
    """Schema d'une extraction par chunk. 1 chunk = 1 instance de cette classe.
    / Schema for one chunk's extraction. 1 chunk = 1 instance of this class."""
    resume: str = Field(
        ..., min_length=10, max_length=500,
        description="Resume neutre du contenu du chunk en 1-3 phrases. "
                    "Doit pouvoir etre lu hors-contexte."
    )
    hypostases: list[HYPOSTASES_VALIDES] = Field(
        ..., min_length=1, max_length=3,
        description="1 a 3 hypostases qui caracterisent le chunk. "
                    "Si plusieurs natures coexistent, listees par ordre d'importance."
    )
    mots_cles: list[str] = Field(
        ..., min_length=2, max_length=5,
        description="2 a 5 mots-cles thematiques pour faciliter la recherche."
    )
    pertinent: bool = Field(
        default=True,
        description="False si le chunk est purement structurel "
                    "(table des matieres, salutations, signature) et non argumentatif."
    )
```

#### Prompt système

```python
# hypostasis_extractor/prompts.py

SYSTEM_PROMPT_EXTRACTION = """Tu es un analyste de la lecture deliberative.

Pour chaque passage qui t'est soumis, tu dois identifier sa nature argumentative en
lui attribuant une ou plusieurs HYPOSTASES (types d'unites argumentatives).

LISTE DES 30 HYPOSTASES :

[Topics structurants]
- paradigme : un modele ou un exemple
- objet : ce sur quoi porte le discours, la pensee, la connaissance
- principe : les causes a priori d'une connaissance
- domaine : un champ discerne par des limites, bornes, frontieres
- loi : exprime des correlations
- phenomene : se manifeste a la connaissance via les sens

[Mesures et donnees]
- variable : ce qui prend differentes valeurs et determine l'etat d'un systeme
- variance : caracterise une dispersion d'une distribution ou d'un echantillon
- indice : indicateur numerique ou litteral qui sert a distinguer ou classer
- donnee : ce qui est admis, donne, qui sert a decouvrir ou a raisonner

[Methodes et processus]
- methode : procedure qui indique ce que l'on doit faire ou comment le faire
- definition : determination, caracterisation du contenu d'un concept
- hypothese : explication ou possibilite d'un evenement
- probleme : difficulte a resoudre

[Constructions intellectuelles]
- theorie : construction intellectuelle explicative, hypothetique et synthetique
- approximation : calcul approche d'une grandeur reelle
- classification : distribuer en classes, en categories
- aporie : difficulte d'ordre rationnel apparemment sans issue
- paradoxe : proposition a la fois vraie et fausse
- formalisme : consideration de la forme d'un raisonnement

[Phenomenes temporels]
- evenement : ce qui arrive
- variation : changement d'un etat dans un autre
- dimension : grandeur mesurable qui determine des positions
- mode : maniere d'etre d'un systeme

[Convictions et bases]
- croyance : certitude ou conviction qui fait croire une chose vraie
- invariant : grandeur, relation ou propriete conservee lors d'une transformation
- valeur : mesure d'une grandeur variable
- structure : organisation des parties d'un systeme
- axiome : proposition admise au depart d'une theorie
- conjecture : opinion ou proposition non verifiee

REGLES STRICTES :
- Tu choisis 1 a 3 hypostases par passage, par ordre d'importance
- Tu n'inventes PAS de nouvelle hypostase (utilise UNIQUEMENT celles de la liste)
- Tu produis un resume neutre du passage en 1-3 phrases
- Tu extraits 2-5 mots-cles thematiques
- Si le passage n'est pas argumentatif (table des matieres, salutations, signature),
  tu mets pertinent=False
"""
```

#### Appel LLM via instructor

```python
# core/llm_providers.py

import instructor
from openai import OpenAI

class OpenRouterBackend:
    """Backend unifie pour 200+ modeles via OpenRouter (API OpenAI-compatible).
    / Unified backend for 200+ models via OpenRouter (OpenAI-compatible API)."""

    def __init__(self, api_key: str):
        # instructor.from_openai wrap le client OpenAI pour ajouter
        # validation Pydantic + retry automatique en cas d'echec de validation
        # / instructor.from_openai wraps the OpenAI client to add
        # Pydantic validation + automatic retry on validation failure
        self.client = instructor.from_openai(
            OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://hypostasia.app",
                    "X-Title": "Hypostasia",
                },
            )
        )

    def extraire_hypostase(
        self,
        chunk_content: str,
        modele: str,
        max_retries: int = 2,
    ) -> HypostaseExtraction:
        """Extrait une HypostaseExtraction depuis un chunk.
        / Extract one HypostaseExtraction from a chunk."""
        return self.client.chat.completions.create(
            model=modele,
            response_model=HypostaseExtraction,
            max_retries=max_retries,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION},
                {"role": "user", "content": f"Passage a analyser :\n\n{chunk_content}"},
            ],
        )

    def embed_batch(
        self,
        textes: list[str],
        modele: str = "openai/text-embedding-3-small",
    ) -> list[list[float]]:
        """Embedding batch pour le RAG (Axe 6).
        / Batch embedding for RAG (Axis 6)."""
        # On utilise le client OpenAI brut (pas instructor) pour les embeddings
        # / Use raw OpenAI client (not instructor) for embeddings
        from openai import OpenAI
        raw_client = OpenAI(
            api_key=self.client.client.api_key,
            base_url=self.client.client.base_url,
        )
        response = raw_client.embeddings.create(model=modele, input=textes)
        return [item.embedding for item in response.data]
```

### 4.3 Pipeline d'extraction complet (refonte)

```python
# front/tasks.py

@shared_task(bind=True)
def analyser_page_task(self, page_id: int, analyseur_id: int):
    """
    Pipeline d'extraction Atomic-style : 1 chunk = 1 extraction.
    Remplace l'ancien pipeline LangExtract.
    / Atomic-style extraction pipeline: 1 chunk = 1 extraction.
    Replaces the old LangExtract pipeline.
    """
    from core.models import Page, PageChunk
    from hypostasis_extractor.models import ExtractedEntity, ExtractionJob, Analyseur
    from core.llm_providers import OpenRouterBackend
    from core.chunking import chunker_markdown, chunker_transcription

    page = Page.objects.get(id=page_id)
    analyseur = Analyseur.objects.get(id=analyseur_id)
    backend = OpenRouterBackend(api_key=analyseur.modele_ia.openrouter_api_key)

    # 1. Creer le job
    # / Create the job
    job = ExtractionJob.objects.create(
        page=page,
        analyseur=analyseur,
        status="processing",
    )

    try:
        # 2. Chunking markdown-aware (cas transcription audio detecte automatiquement)
        # / Markdown-aware chunking (audio transcription case auto-detected)
        if page.est_transcription_audio:
            chunks_donnees = chunker_transcription(page.blocs_transcription())
        else:
            chunks_donnees = chunker_markdown(page.text_readability)

        # 3. Persister les PageChunks (sera reutilise pour l'embedding RAG)
        # / Persist PageChunks (will be reused for RAG embedding)
        page.chunks.all().delete()  # idempotent : on regenere si re-analyse
        chunks_persistes = []
        for cd in chunks_donnees:
            chunk = PageChunk.objects.create(
                page=page,
                chunk_index=cd.chunk_index,
                content=cd.content,
                start_char=cd.start_char,
                end_char=cd.end_char,
                metadata=cd.metadata,
            )
            chunks_persistes.append(chunk)

        # 4. Pour chaque chunk : extraction LLM via instructor
        # / For each chunk: LLM extraction via instructor
        for i, chunk in enumerate(chunks_persistes):
            # Notification de progression via WebSocket
            # / Progress notification via WebSocket
            _notifier_progression(job.id, i + 1, len(chunks_persistes))

            try:
                extraction_pydantic = backend.extraire_hypostase(
                    chunk_content=chunk.content,
                    modele=analyseur.modele_ia.identifiant,
                )
            except Exception as e:
                # Si l'extraction d'un chunk echoue (apres retry), on logue et continue
                # / If chunk extraction fails (after retry), log and continue
                logger.warning(f"Extraction chunk {chunk.id} echouee : {e}")
                continue

            # Si le chunk n'est pas pertinent, on le skip
            # / If chunk is not pertinent, skip it
            if not extraction_pydantic.pertinent:
                continue

            # Persister l'extraction (1-1 avec chunk)
            # / Persist the extraction (1-1 with chunk)
            ExtractedEntity.objects.create(
                page=page,
                chunk=chunk,
                extraction_text=chunk.content,   # le contenu complet du chunk
                attributes={
                    "resume": extraction_pydantic.resume,
                    "hypostases": extraction_pydantic.hypostases,
                    "mots_cles": extraction_pydantic.mots_cles,
                },
                statut_debat="nouveau",
                job=job,
            )

            # Streaming en temps reel : envoyer la carte au frontend via WS
            # / Real-time streaming: send card to frontend via WS
            _streamer_carte_extraction(job.id, chunk, extraction_pydantic)

        job.status = "completed"
        job.save()

        # 5. Trigger embedding job (Axe 6 - RAG)
        # / Trigger embedding job (Axis 6 - RAG)
        embed_page_chunks_task.delay(page.id)

    except Exception as e:
        job.status = "error"
        job.error_message = str(e)
        job.save()
        raise
```

### 4.4 Sélection manuelle pour précision fine

Le mécanisme existant (PHASE-09) reste actif et même valorisé : pour les chunks denses
(essai philosophique, texte juridique), l'utilisateur peut promouvoir une phrase
précise en extraction supplémentaire.

```python
# Differences entre extractions auto et manuelles :
# / Differences between auto and manual extractions:

# Auto (issue du pipeline) :
ExtractedEntity(
    page=page,
    chunk=page_chunk,                    # FK obligatoire
    extraction_text=chunk.content,       # = chunk content
    attributes={...},                    # rempli par LLM
    statut_debat="nouveau",
    # start_char/end_char dérivés via .chunk.start_char/.chunk.end_char
)

# Manuelle (creee par l'humain via selection) :
ExtractedEntity(
    page=page,
    chunk=None,                          # PAS de chunk
    extraction_text="phrase precise selectionnee par l'humain",
    start_char=1234,                     # position exacte de la selection
    end_char=1290,
    attributes={
        "hypostases": ["conjecture"],    # rempli par humain ou LLM ulterieur
        "resume": "...",
        "mots_cles": [...],
    },
    statut_debat="nouveau",
)
```

Le UX (pastilles, drawer, dashboard) traite les deux types de manière transparente.

---

## 5. Sourçage `[N]` des synthèses délibératives

### Pattern Atomic réutilisé tel quel

Quand on génère une synthèse délibérative (PHASE-28-light), on numérote les sources
dans le user prompt et on demande au LLM de citer `[N]`. Côté code, on parse les `[N]`
et on crée des SourceLinks par index.

#### Construction du prompt avec sources numérotées

```python
# front/tasks.py

def _construire_prompt_synthese_avec_citations(
    page,
    extractions_triees: list[ExtractedEntity],
    commentaires_par_extraction: dict,
) -> tuple[str, list[dict]]:
    """
    Construit le prompt utilisateur avec sources numerotees [N].
    Retourne (prompt_str, sources_list) ou sources_list est utilise pour le mapping.
    / Build the user prompt with numbered [N] sources.
    Returns (prompt_str, sources_list) where sources_list is used for mapping.
    """
    sources = []  # liste ordonnee pour le mapping [N] -> ref source

    # Chaque extraction devient une source numerotee
    # / Each extraction becomes a numbered source
    for extraction in extractions_triees:
        hypos = ", ".join(extraction.attributes.get("hypostases", []))
        sources.append({
            "type": "extraction",
            "ref": extraction,
            "content": (
                f"[{hypos.upper()}] "
                f"{extraction.attributes.get('resume', '')}\n"
                f"Citation : « {extraction.extraction_text[:200]}... »\n"
                f"Statut : {extraction.statut_debat}"
            ),
        })

        # Et chaque commentaire de cette extraction
        # / And each comment on this extraction
        for commentaire in commentaires_par_extraction.get(extraction.id, []):
            sources.append({
                "type": "commentaire",
                "ref": commentaire,
                "content": (
                    f"Commentaire de {commentaire.user.username} : "
                    f"« {commentaire.commentaire} »"
                ),
            })

    # Assembler le prompt
    # / Assemble the prompt
    bloc_sources = "\n\n".join(
        f"[{i+1}] {s['content']}" for i, s in enumerate(sources)
    )
    prompt = (
        f"SOURCES (cite-les avec [N] dans ta synthese) :\n\n"
        f"{bloc_sources}\n\n"
        f"=== CONSIGNE ===\n"
        f"Redige la synthese deliberative. Chaque affirmation factuelle DOIT etre "
        f"suivie d'une citation [N] qui pointe vers la source utilisee. "
        f"N'invente jamais de numero — utilise UNIQUEMENT les [N] presents dans les "
        f"SOURCES ci-dessus."
    )
    return prompt, sources
```

#### Schema Pydantic de la sortie

```python
class SyntheseDelibérative(BaseModel):
    """Sortie attendue du LLM pour une synthese deliberative.
    / Expected LLM output for a deliberative synthesis."""
    synthese_html: str = Field(
        ...,
        description="Synthese complete en markdown, avec citations [N] inline."
    )
    citations_used: list[int] = Field(
        ...,
        description="Liste des numeros [N] effectivement utilises."
    )
```

#### Extraction des citations côté code

```python
# front/tasks.py

import re

def extraire_citations_synthese(
    synthese_html: str,
    sources: list[dict],
    page_v2,
) -> list[SourceLink]:
    """
    Parse les [N] dans la synthese et cree les SourceLinks correspondants.
    Inspire de atomic-core/src/wiki/mod.rs:662 (extract_citations).
    / Parse [N] markers in the synthesis and create matching SourceLinks.
    """
    pattern = re.compile(r"\[(\d+)\]")
    indices_vus = set()
    source_links_crees = []

    for match in pattern.finditer(synthese_html):
        index = int(match.group(1))
        if index in indices_vus:
            continue                    # dedup : meme [N] cite plusieurs fois -> 1 SourceLink
        indices_vus.add(index)

        if 0 < index <= len(sources):
            source = sources[index - 1]    # [1] -> sources[0]
            source_link = _creer_source_link_depuis_source(source, index, page_v2)
            source_links_crees.append(source_link)
        # Si index hors limites (hallucination LLM), on ignore silencieusement
        # avec un log warning pour audit
        # / If index out of bounds (LLM hallucination), silently skip with warning log
        else:
            logger.warning(
                f"Citation [{index}] hallucinee dans synthese page {page_v2.id} : "
                f"seulement {len(sources)} sources disponibles"
            )

    return source_links_crees


def _creer_source_link_depuis_source(source: dict, citation_index: int, page_v2):
    """Cree un SourceLink avec le bon type_lien selon la nature de la source.
    / Create a SourceLink with the right type_lien based on source nature."""
    type_lien_par_source = {
        "extraction": "cite",
        "commentaire": "modifie",  # commentaire qui a influence la redaction
    }
    return SourceLink.objects.create(
        page_cible=page_v2,
        page_source=source["ref"].page if hasattr(source["ref"], "page") else None,
        extraction_source=source["ref"] if source["type"] == "extraction" else None,
        commentaire_source=source["ref"] if source["type"] == "commentaire" else None,
        type_lien=type_lien_par_source[source["type"]],
        citation_index=citation_index,           # nouveau champ
    )
```

#### Migration : étendre SourceLink

```python
# core/migrations/00XX_source_link_citation.py

from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="sourcelink",
            name="citation_index",
            field=models.IntegerField(
                null=True, blank=True,
                help_text="Index [N] dans la synthese qui a cree ce lien (auto)"
            ),
        ),
        migrations.AddField(
            model_name="sourcelink",
            name="commentaire_source",
            field=models.ForeignKey(
                "core.CommentaireExtraction",
                null=True, blank=True,
                on_delete=models.SET_NULL,
                related_name="source_links_crees",
            ),
        ),
    ]
```

#### Affichage des citations cliquables côté front

Dans le template de lecture de la V2, les `[N]` sont rendus comme des liens HTMX qui
ouvrent la carte de l'extraction source dans le drawer existant :

```python
# hypostasis_extractor/templatetags/citations.py

from django import template
import re

register = template.Library()

@register.filter
def render_citations(synthese_html: str, source_links_dict: dict) -> str:
    """
    Remplace les [N] dans le markdown rendu par des liens cliquables.
    source_links_dict: {citation_index: SourceLink}
    / Replace [N] markers in rendered markdown with clickable links.
    """
    def _remplacer_citation(match):
        index = int(match.group(1))
        link = source_links_dict.get(index)
        if not link:
            return match.group(0)  # pas de SourceLink -> laisser tel quel

        if link.extraction_source:
            return (
                f'<a href="#extraction-{link.extraction_source.id}" '
                f'class="citation-inline" '
                f'hx-get="/extractions/{link.extraction_source.id}/carte/" '
                f'hx-target="#zone-source-active" '
                f'hx-swap="innerHTML">[{index}]</a>'
            )
        elif link.commentaire_source:
            return (
                f'<a href="#commentaire-{link.commentaire_source.id}" '
                f'class="citation-inline citation-commentaire" '
                f'hx-get="/commentaires/{link.commentaire_source.id}/contexte/" '
                f'hx-target="#zone-source-active" '
                f'hx-swap="innerHTML">[{index}]</a>'
            )
        return match.group(0)

    return re.sub(r"\[(\d+)\]", _remplacer_citation, synthese_html)
```

### Bénéfices

- **PHASE-27c (SourceLinks manuels) devient triviale** : 80% du sourçage est automatique.
  La popup manuelle reste utile pour les rares cas où l'humain veut affiner, mais ce
  n'est plus le chemin principal.
- **Zero hallucination d'identifiant** : le LLM manipule des entiers, pas des UUIDs.
- **Compatible avec mode incrémental** (section 7) : les `[N]` existants restent intacts
  byte-exact dans les sections non touchées par un update.

---

## 6. RAG complet via pgvector

### Stack technique

| Composant | Choix | Pourquoi |
|---|---|---|
| Vector store | **pgvector** (extension PostgreSQL) | Hypostasia a déjà PostgreSQL ; pas de service à ajouter |
| Modèle d'embedding défaut | **text-embedding-3-small** via OpenRouter (1536 dims) | Standard, bon multilingue, peu cher |
| Alternative locale | **nomic-embed-text** via Ollama (768 dims) | Self-hosted, bon en multilingue |
| Driver | `pgvector` Python + `django-pgvector` | Intégration Django propre, `VectorField` natif |
| Tâche async | **Celery** (déjà en place) | Cohérent avec PHASE-15 et autres tâches longues |

### Pipeline d'embedding

#### Migration : activer pgvector + ajouter les champs embedding

```python
# core/migrations/00XX_pgvector.py

from django.db import migrations
from pgvector.django import VectorField

class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS vector;"),
        # Embedding sur PageChunk
        migrations.AddField(
            model_name="pagechunk",
            name="embedding",
            field=VectorField(dimensions=1536, null=True, blank=True),
        ),
        # Embedding sur ExtractedEntity (pour recherche d'extractions similaires)
        migrations.AddField(
            model_name="extractedentity",
            name="embedding",
            field=VectorField(dimensions=1536, null=True, blank=True),
        ),
        # Index HNSW pour recherche rapide
        migrations.RunSQL(
            "CREATE INDEX idx_pagechunk_embedding ON core_pagechunk "
            "USING hnsw (embedding vector_l2_ops);"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_extractedentity_embedding "
            "ON hypostasis_extractor_extractedentity "
            "USING hnsw (embedding vector_l2_ops);"
        ),
    ]
```

#### Tâches Celery

```python
# front/tasks.py

@shared_task(bind=True)
def embed_page_chunks_task(self, page_id: int):
    """
    Embed tous les chunks d'une page (apres chunking markdown-aware).
    Lance apres chaque creation/modification de Page (et apres analyser_page_task).
    / Embed all chunks of a page (after markdown-aware chunking).
    """
    from core.models import Page, PageChunk
    from core.llm_providers import OpenRouterBackend, get_active_ai_model

    page = Page.objects.get(id=page_id)
    chunks_a_embed = list(page.chunks.filter(embedding__isnull=True))
    if not chunks_a_embed:
        return

    backend = OpenRouterBackend(api_key=...)
    modele_ia = get_active_ai_model()

    # Batch les textes par groupes de 64 pour reduire le nombre d'appels API
    # / Batch texts in groups of 64 to reduce API calls
    BATCH_SIZE = 64
    for i in range(0, len(chunks_a_embed), BATCH_SIZE):
        batch = chunks_a_embed[i:i+BATCH_SIZE]
        textes = [c.content for c in batch]
        embeddings = backend.embed_batch(textes, modele=modele_ia.embedding_model)
        for chunk, emb in zip(batch, embeddings):
            chunk.embedding = emb
            chunk.save(update_fields=["embedding"])


@shared_task(bind=True)
def embed_extractions_task(self, page_id: int):
    """
    Embed les ExtractedEntity (sur le resume IA + extraction_text).
    Permet la recherche semantique d'extractions similaires.
    / Embed ExtractedEntity (on summary + extraction text).
    """
    from hypostasis_extractor.models import ExtractedEntity
    from core.llm_providers import OpenRouterBackend, get_active_ai_model

    extractions = list(ExtractedEntity.objects.filter(
        page_id=page_id, embedding__isnull=True,
    ))
    if not extractions:
        return

    backend = OpenRouterBackend(api_key=...)
    modele = get_active_ai_model()

    # Pour chaque extraction, on embed resume + texte (concatenes)
    # / For each extraction, embed summary + text concatenated
    BATCH_SIZE = 64
    for i in range(0, len(extractions), BATCH_SIZE):
        batch = extractions[i:i+BATCH_SIZE]
        textes = [
            f"{e.attributes.get('resume', '')}\n\n{e.extraction_text}"
            for e in batch
        ]
        embeddings = backend.embed_batch(textes, modele=modele.embedding_model)
        for extraction, emb in zip(batch, embeddings):
            extraction.embedding = emb
            extraction.save(update_fields=["embedding"])
```

### Recherche sémantique cross-documents

```python
# front/views_recherche.py

from pgvector.django import L2Distance
from rest_framework.decorators import action
from rest_framework import viewsets

class RechercheSemantiqueViewSet(viewsets.ViewSet):
    """Recherche semantique cross-documents et extractions.
    / Cross-document and extraction semantic search."""

    def list(self, request):
        """Page de recherche pleine page."""
        # Pattern : partial HTMX + page complete pour F5
        if request.headers.get("HX-Request"):
            return render(request, "front/includes/recherche_contenu.html", {})
        return render(request, "front/recherche_semantique.html", {})

    @action(detail=False, methods=["post"])
    def chercher(self, request):
        """
        Recherche semantique sur extractions ou chunks.
        / Semantic search on extractions or chunks.
        """
        serializer = RechercheSemantiqueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requete = serializer.validated_data["requete"]
        type_cible = serializer.validated_data.get("type_cible", "extractions")
        filtres = serializer.validated_data.get("filtres", {})

        # Embed la requete
        # / Embed the query
        backend = OpenRouterBackend(api_key=...)
        modele = get_active_ai_model()
        [vecteur_requete] = backend.embed_batch(
            [requete], modele=modele.embedding_model,
        )

        # Lookup pgvector avec scope sur les dossiers visibles de l'user
        # / pgvector lookup scoped to user's visible folders
        dossiers_visibles_ids = request.user.dossiers_visibles().values_list("id", flat=True)

        if type_cible == "extractions":
            extractions_proches = ExtractedEntity.objects.alias(
                distance=L2Distance("embedding", vecteur_requete)
            ).filter(
                page__dossier_id__in=dossiers_visibles_ids,
                embedding__isnull=False,
                **filtres,
            ).order_by("distance")[:20]

            return render(request, "front/includes/recherche_resultats.html", {
                "extractions": extractions_proches,
                "type_cible": "extractions",
            })

        elif type_cible == "chunks":
            chunks_proches = PageChunk.objects.alias(
                distance=L2Distance("embedding", vecteur_requete)
            ).filter(
                page__dossier_id__in=dossiers_visibles_ids,
                embedding__isnull=False,
            ).order_by("distance")[:20]

            return render(request, "front/includes/recherche_resultats.html", {
                "chunks": chunks_proches,
                "type_cible": "chunks",
            })
```

### Cas d'usage débloqués par le RAG

#### 6.1 Détection de doublons à la création d'extraction

À la création d'une extraction (auto ou manuelle), embed son contenu et chercher dans
les extractions existantes du dossier. Si similarité > 0.85, signaler à l'utilisateur :

```python
def detecter_doublons_potentiels(extraction_nouvelle, dossier, seuil=0.85):
    """
    Trouve les extractions existantes semantiquement proches.
    / Find existing extractions that are semantically close.
    """
    return ExtractedEntity.objects.alias(
        distance=L2Distance("embedding", extraction_nouvelle.embedding)
    ).filter(
        page__dossier=dossier,
        embedding__isnull=False,
    ).exclude(
        id=extraction_nouvelle.id,
    ).annotate(
        similarity=1 - (F("distance") ** 2 / 2),
    ).filter(
        similarity__gte=seuil,
    ).order_by("distance")[:5]
```

UI : bandeau dans le drawer "Cette extraction ressemble à 3 autres dans ce dossier.
[Voir les similaires]". Anti-fragmentation de la KB.

#### 6.2 Auto-suggestion d'hypostase

Pour chaque extraction manuelle créée par l'utilisateur, comparer sémantiquement le
passage aux **embeddings moyens des 30 hypostases** (calculés depuis les exemples
few-shot de la bibliothèque d'analyseurs PHASE-26b). Pré-cocher la classe la plus
probable :

```python
# Une fois calcules a l'init du systeme et stockes en cache Redis
# / Computed once at system init and cached in Redis
HYPOSTASES_EMBEDDINGS = {
    "paradigme": [...],    # moyenne des embeddings des exemples "paradigme"
    "objet": [...],
    # ... 30 hypostases
}

def suggerer_hypostase(extraction_text: str) -> list[tuple[str, float]]:
    """
    Retourne les 3 hypostases les plus probables avec leur score de similarite.
    / Return the 3 most likely hypostases with similarity scores.
    """
    backend = OpenRouterBackend(api_key=...)
    [vecteur] = backend.embed_batch([extraction_text])

    similarites = []
    for hypostase, vec_hypo in HYPOSTASES_EMBEDDINGS.items():
        sim = cosine_similarity(vecteur, vec_hypo)
        similarites.append((hypostase, sim))

    return sorted(similarites, key=lambda x: -x[1])[:3]
```

#### 6.3 Alignement sémantique (extension PHASE-18)

PHASE-18 actuellement aligne par hypostase exacte (PRINCIPE de doc A vs PRINCIPE de
doc B). Ajouter un mode "alignement sémantique" :

```python
def aligner_semantiquement(extractions_doc_a, extractions_doc_b, seuil=0.7):
    """
    Pour chaque extraction de A, trouve la plus proche dans B (peu importe l'hypostase).
    / For each extraction in A, find the closest one in B (regardless of hypostase).
    """
    alignements = []
    for ea in extractions_doc_a:
        if not ea.embedding:
            continue
        eb_proche = ExtractedEntity.objects.alias(
            distance=L2Distance("embedding", ea.embedding)
        ).filter(
            id__in=[e.id for e in extractions_doc_b],
            embedding__isnull=False,
        ).order_by("distance").first()

        if eb_proche:
            similarity = 1 - (eb_proche.distance ** 2 / 2)
            if similarity >= seuil:
                alignements.append({
                    "extraction_a": ea,
                    "extraction_b": eb_proche,
                    "similarite": similarity,
                    "hypostase_a": ea.attributes.get("hypostases"),
                    "hypostase_b": eb_proche.attributes.get("hypostases"),
                    "convergence": ea.attributes.get("hypostases") == eb_proche.attributes.get("hypostases"),
                })

    return alignements
```

Bénéfice : on découvre des correspondances que l'alignement structurel rate (ex:
"la PRINCIPE de A est sémantiquement proche de la THÉORIE de B").

#### 6.4 Chat agentique avec la base (équivalent du chat Atomic)

Voir squelette PHASE-35 dans l'Annexe A.

---

## 7. Update incrémental des synthèses (section_ops)

### Pattern Atomic

Source : `crates/atomic-core/src/wiki/section_ops.rs` et le prompt
`WIKI_UPDATE_SECTION_OPS_PROMPT` dans `wiki/mod.rs:551`.

Au lieu de regénérer toute la synthèse à chaque update, le LLM retourne un **diff
structuré** sous forme de JSON list d'opérations qu'un applier merge dans la synthèse
existante.

### Schema Pydantic des opérations

```python
# hypostasis_extractor/schemas.py

from typing import Literal

class SectionOp(BaseModel):
    """Une operation de mise a jour de section."""
    op: Literal["NoChange", "AppendToSection", "ReplaceSection", "InsertSection"]
    heading: str = Field(
        default="",
        description="Titre exact de la section concernee (sans le ##). Vide pour NoChange."
    )
    after_heading: str = Field(
        default="",
        description="Pour InsertSection : titre de la section apres laquelle inserer. "
                    "Vide pour ajouter en fin."
    )
    content: str = Field(
        default="",
        description="Nouveau contenu (markdown avec [N] citations)."
    )

class SyntheseUpdate(BaseModel):
    """Sortie attendue du LLM pour un update incremental de synthese."""
    operations: list[SectionOp] = Field(
        ..., min_length=1,
        description="Liste d'operations a appliquer. Si rien a changer : [NoChange]."
    )
    citations_used: list[int] = Field(
        ...,
        description="Liste des nouveaux numeros [N] effectivement utilises."
    )
```

### Prompt système

```python
PROMPT_UPDATE_SECTION_OPS = """Tu mets a jour une synthese deliberative existante avec
de nouvelles informations issues de nouvelles sources (extractions, commentaires).

Retourne une liste d'operations structurees au format JSON.

OPERATIONS POSSIBLES :

- NoChange : aucune modification necessaire (rien de neuf ne justifie un update).
  Utilise UNIQUEMENT cette operation comme seul element de la liste.

- AppendToSection : ajouter du contenu a la fin d'une section existante.
  - heading : titre EXACT de la section a etendre (sans le ##)
  - content : nouveau markdown a ajouter

- ReplaceSection : reecrire une section (a utiliser avec parcimonie, seulement si
  contradiction directe avec les nouvelles sources).
  - heading : titre EXACT de la section
  - content : nouveau corps de section

- InsertSection : creer une nouvelle section.
  - heading : titre de la nouvelle section
  - after_heading : titre EXACT de la section apres laquelle inserer (vide = en fin)
  - content : corps de la nouvelle section

REGLES :
- Les valeurs `heading` et `after_heading` doivent EXACTEMENT correspondre aux titres
  existants (pas de paraphrase, pas de changement de casse, pas de prefixe ##)
- Prefere AppendToSection a ReplaceSection
- Continue la numerotation des citations [N] depuis la derniere utilisee dans la
  synthese existante
- Si rien de nouveau ne justifie un update, retourne UNIQUEMENT NoChange
"""
```

### Applier en Python

```python
# front/section_ops.py

from dataclasses import dataclass

@dataclass
class Section:
    heading: str
    body: str

def parser_sections(markdown: str) -> list[Section]:
    """Parse un markdown en sections (## heading + body).
    / Parse markdown into sections."""
    sections = []
    lignes = markdown.split("\n")
    current = None
    for ligne in lignes:
        if ligne.startswith("## "):
            if current:
                sections.append(current)
            current = Section(heading=ligne[3:].strip(), body="")
        elif current:
            current.body += ligne + "\n"
        else:
            # Texte avant la premiere section : section "preambule" sans heading
            if not sections:
                sections.append(Section(heading="", body=ligne + "\n"))
            else:
                sections[-1].body += ligne + "\n"
    if current:
        sections.append(current)
    return sections


def appliquer_ops(markdown_existant: str, ops: list[SectionOp]) -> str:
    """
    Applique les operations sur le markdown existant.
    Inspire de atomic-core/src/wiki/section_ops.rs.
    / Apply section operations on existing markdown.
    """
    sections = parser_sections(markdown_existant)

    for op in ops:
        if op.op == "NoChange":
            continue

        elif op.op == "AppendToSection":
            section = _trouver_section(sections, op.heading)
            if section:
                section.body = section.body.rstrip() + "\n\n" + op.content
            else:
                logger.warning(f"AppendToSection : section '{op.heading}' introuvable")

        elif op.op == "ReplaceSection":
            section = _trouver_section(sections, op.heading)
            if section:
                section.body = op.content
            else:
                logger.warning(f"ReplaceSection : section '{op.heading}' introuvable")

        elif op.op == "InsertSection":
            nouvelle = Section(heading=op.heading, body=op.content)
            if op.after_heading:
                idx = _index_section(sections, op.after_heading)
                if idx is not None:
                    sections.insert(idx + 1, nouvelle)
                else:
                    sections.append(nouvelle)  # fallback en fin
            else:
                sections.append(nouvelle)

    # Reconstruire le markdown
    # / Rebuild the markdown
    return "\n\n".join(
        f"## {s.heading}\n\n{s.body.strip()}" if s.heading else s.body.strip()
        for s in sections
    )


def _trouver_section(sections, heading_recherche):
    return next((s for s in sections if s.heading == heading_recherche), None)

def _index_section(sections, heading_recherche):
    return next((i for i, s in enumerate(sections) if s.heading == heading_recherche), None)
```

### Audit trail : table SyntheseUpdate

```python
# core/models.py

class SyntheseUpdate(models.Model):
    """Historique des mises a jour incrementales d'une synthese.
    / History of incremental updates to a synthesis."""
    page_synthese = models.ForeignKey(
        Page, on_delete=models.CASCADE, related_name="updates"
    )
    operations_json = models.JSONField()  # liste de SectionOp
    citations_used = models.JSONField()
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Bénéfices

- **Citations préservées byte-exact** dans les sections non touchées
- **Coût LLM réduit** : on génère que les diffs, pas tout l'article
- **Audit trail** : chaque update est inspectable, reversible
- **Compatible avec le sourçage `[N]`** (section 5) : numérotation continue, sources
  existantes préservées

---

## 8. Couche sociale × RAG (les 6 idées bonus)

Là où la portabilité s'inverse : Atomic n'a pas la dimension collective. Ces idées
capitalisent sur ce qu'Hypostasia a en propre, en y ajoutant l'intelligence sémantique
débloquée par le RAG (Axe 6).

À implémenter en sous-phases indépendantes (PHASE-37a, 37b, 37c...) selon priorité.

### 8.1 Notifications "ce qui te concerne"

**Trigger** : nouveau commentaire ajouté à une extraction X dans un dossier.
**Action** : pour chaque user du dossier qui n'a pas commenté X, calculer la similarité
entre l'embedding de X et la moyenne des embeddings des extractions que l'user a déjà
commentées dans le dossier. Si > 0.7 → notification "Ce débat pourrait t'intéresser".

```python
@shared_task
def notifier_users_pertinents_task(extraction_id: int, commentateur_id: int):
    """
    Apres un commentaire, notifier les users non-commentateurs interesses.
    / After a comment, notify non-commenting users who might be interested.
    """
    from core.models import ExtractedEntity, User

    extraction = ExtractedEntity.objects.select_related("page__dossier").get(id=extraction_id)
    dossier = extraction.page.dossier
    if not extraction.embedding:
        return

    # Users du dossier sauf le commentateur, qui n'ont pas deja commente cette extraction
    # / Folder users except the commenter, who haven't commented this extraction yet
    users_potentiels = User.objects.filter(
        dossiers_visibles=dossier,
    ).exclude(
        id=commentateur_id,
    ).exclude(
        commentaires_extractions__extraction=extraction,
    )

    for user in users_potentiels:
        # Profil semantique de l'user dans ce dossier
        # / User's semantic profile in this folder
        extractions_commentees = ExtractedEntity.objects.filter(
            commentaires__user=user,
            page__dossier=dossier,
            embedding__isnull=False,
        )
        if not extractions_commentees.exists():
            continue

        embeddings_commentes = [e.embedding for e in extractions_commentees]
        profil_user = np.mean(embeddings_commentes, axis=0)

        # Distance entre le profil user et l'extraction nouvelle
        # / Distance between user profile and new extraction
        distance = np.linalg.norm(profil_user - np.array(extraction.embedding))
        similarity = 1 - (distance ** 2 / 2)

        if similarity >= 0.7:
            Notification.objects.create(
                user=user,
                type="extraction_pertinente",
                contexte={"extraction_id": extraction_id, "score": similarity},
                message=f"Un debat sur '{extraction.attributes.get('resume', '')[:60]}...' "
                        f"pourrait vous interesser.",
            )
```

### 8.2 Cartographie des contributeurs par sujet

Pour chaque user, calculer son "profil sémantique" = centroïde des embeddings des
extractions qu'il a commentées. Page admin "Profils contributeurs" : montre quel user
est expert sur quel cluster sémantique (via clustering K-means ou DBSCAN sur les
profils).

**Cas d'usage** : à la création d'un nouveau dossier sur le sujet X, le système
suggère "Bob et Alice ont commenté beaucoup d'extractions proches sémantiquement de X
— les inviter ?".

### 8.3 Détection de contradiction cross-document

Quand l'user édite la V2 ou rédige un commentaire long, embed le passage et chercher
dans les autres documents du dossier les extractions consensuelles avec une distance
faible **mais statut opposé** (ex: l'user écrit ce qui contredit un consensus établi
ailleurs).

Bandeau de warning : "Tu écris X. Sur tel autre document, un consensus a été atteint
sur le contraire — [voir le débat]".

⚠️ Feature délicate (faux positifs si la similarité confond "même sujet" et "même
position"). À itérer sur le seuil et le wording.

### 8.4 Heat map sémantique du débat — ⚠️ DEPRECATED 2026-05-01

> Cette sous-phase est sans objet : PHASE-19 (heat map de base) a été retirée du
> périmètre (YAGNI, personne ne s'en sert). Il n'y a plus de couche thermique sur
> laquelle empiler une dimension sémantique. Voir `discussions/YAGNI 2026-05-01.md`.
>
> Si la piste « divergence sémantique des commentaires » devient pertinente plus tard,
> elle peut renaître comme indicateur dans le **dashboard de consensus** (PHASE-14)
> plutôt que comme couche colorée sur le texte — par exemple un compteur « N
> extractions à forte divergence » ou un tri du drawer par dispersion sémantique.

### 8.5 Géométrie du débat enrichie (concept Jean/Dominique)

Le concept de "géométrie du débat" mentionné dans `discussions/notes design suite.md`
liste 6 facettes (spatiale, statistique, thermique, structurelle, sociale, temporelle).

**Ajouter une 7e facette : sémantique.**

- **Couverture conceptuelle** : clustering des embeddings des extractions du dossier →
  détection de gaps thématiques ("personne n'a abordé l'angle écologique")
- **Densité sémantique** : nombre d'extractions par cluster
- **Cohésion** : moyenne des distances inter-extractions (un dossier cohérent a une
  faible cohésion ; un dossier dispersé en a une forte)

Affichage : nouvelle zone dans le dashboard (PHASE-14) — "Couverture sémantique du
débat".

### 8.6 Suggestion d'analyseur à l'import

Quand un user importe un nouveau document, embed le texte et comparer aux embeddings
moyens des analyseurs de la bibliothèque (PHASE-26b). Pré-suggérer l'analyseur le plus
pertinent.

Bonus : si aucun analyseur n'est sémantiquement proche, signaler "Aucun analyseur de
ta bibliothèque n'est conçu pour ce type de texte. Veux-tu en créer un ? (admin only)".

---

## 9. Provider LLM unifié — OpenRouter + instructor

### Pourquoi OpenRouter

- **Une clé, 200+ modèles** (GPT, Claude, Gemini, Llama, DeepSeek, Mistral, Qwen, etc.)
- **API OpenAI-compatible** → `instructor` fonctionne nativement
- **Tarifs comparés** : OpenRouter affiche le prix par token, on peut router selon
  coût/performance
- **Dégradation gracieuse** : si un provider tombe, OpenRouter route automatiquement
- **Embeddings disponibles** : `openai/text-embedding-3-small`, `voyage/voyage-3`,
  `nomic-ai/nomic-embed-text-v1.5`, etc.

### Pourquoi instructor

- Combine OpenAI SDK + Pydantic + retry automatique en cas d'échec de validation
- Plus FALC que la gestion manuelle de `response_format` + parsing + retry
- Largement adopté dans la communauté Python LLM
- Compatible avec OpenRouter (juste base_url différente)

### Configuration

```python
# core/llm_providers.py

import instructor
from openai import OpenAI
from pydantic import BaseModel
from typing import Type

class OpenRouterBackend:
    """Backend LLM unifie via OpenRouter avec validation Pydantic via instructor.
    / Unified LLM backend via OpenRouter with Pydantic validation via instructor."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = instructor.from_openai(
            OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://hypostasia.app",
                    "X-Title": "Hypostasia",
                },
            )
        )

    def appeler_llm_structured(
        self,
        modele: str,
        messages: list[dict],
        response_model: Type[BaseModel],
        max_retries: int = 2,
        temperature: float = 0.0,
    ) -> BaseModel:
        """
        Appel LLM avec response_model Pydantic. Retry auto en cas d'echec de validation.
        / LLM call with Pydantic response_model. Auto-retry on validation failure.
        """
        return self.client.chat.completions.create(
            model=modele,
            response_model=response_model,
            max_retries=max_retries,
            temperature=temperature,
            messages=messages,
        )

    def appeler_llm_texte(
        self,
        modele: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Appel LLM standard sans validation (pour reformulation texte libre).
        / Standard LLM call without validation (for free-form reformulation)."""
        # Pour les sorties texte libre, on bypasse instructor
        # / For free-form output, bypass instructor
        from openai import OpenAI
        raw = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")
        completion = raw.chat.completions.create(
            model=modele,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return completion.choices[0].message.content

    def embed_batch(
        self,
        textes: list[str],
        modele: str = "openai/text-embedding-3-small",
    ) -> list[list[float]]:
        """Embedding batch pour le RAG.
        / Batch embedding for RAG."""
        from openai import OpenAI
        raw = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")
        response = raw.embeddings.create(model=modele, input=textes)
        return [item.embedding for item in response.data]
```

### Settings

```python
# core/models.py

class AIModel(models.Model):
    # ... existant
    PROVIDER_CHOICES = [
        # ... existants
        ("openrouter", "OpenRouter (200+ modeles)"),
    ]
    openrouter_api_key = models.CharField(max_length=200, blank=True)
    embedding_model = models.CharField(
        max_length=100,
        default="openai/text-embedding-3-small",
        help_text="Modele d'embedding pour le RAG (text-embedding-3-small, "
                  "voyage-3, nomic-embed-text-v1.5...)"
    )
```

### Fallback Ollama

Pour le mode self-hosted (pas de clé API), Ollama reste accessible via le même
backend (Ollama expose une API OpenAI-compatible) :

```python
class OllamaBackend(OpenRouterBackend):
    """Backend Ollama : utilise la meme infrastructure que OpenRouter
    (Ollama expose une API OpenAI-compatible).
    / Ollama backend: uses same infrastructure as OpenRouter
    (Ollama exposes OpenAI-compatible API)."""

    def __init__(self, base_url: str = "http://localhost:11434/v1"):
        self.client = instructor.from_openai(
            OpenAI(
                api_key="ollama",   # placeholder, pas requis par Ollama
                base_url=base_url,
            )
        )
```

---

## 10. Évolutions possibles si insuffisant (Plan B documenté)

### Si l'option A (1 chunk = 1 extraction) se révèle insuffisante

**Symptômes** :
- Utilisateurs en alpha trouvent les chunks "trop gros" et la sélection manuelle
  "trop pénible"
- Sur > 30% des pages, l'utilisateur fait > 5 promotions manuelles → effort excessif
- Feedback récurrent : "j'aimerais voir les sous-arguments dans le chunk"

**Pivot vers double passe** : extraction Atomic-style pour la classification
principale + 2e passe LLM pour identifier des sous-extractions intéressantes dans les
chunks denses :

```python
def double_passe_extraction(chunk: PageChunk) -> tuple[ExtractedEntity, list[ExtractedEntity]]:
    """
    Premiere passe : extraction principale du chunk (Atomic-style).
    Deuxieme passe : si le chunk est dense, sous-extractions optionnelles.
    / First pass: main chunk extraction. Second pass: optional sub-extractions if dense.
    """
    # Passe 1 : 1 extraction principale (existant)
    extraction_principale = backend.extraire_hypostase(chunk.content, modele=modele)

    # Decision : le chunk merite-t-il une 2e passe ?
    # Critere : > 250 tokens ET (multiple hypostases dans la passe 1 OU densite argumentative elevee)
    # / Decision: does the chunk deserve a 2nd pass?
    chunk_dense = (
        len(chunk.content) > 1000
        and (
            len(extraction_principale.hypostases) >= 2
            or _detecter_densite_argumentative(chunk.content)
        )
    )
    if not chunk_dense:
        return extraction_principale, []

    # Passe 2 : sous-extractions
    # / Pass 2: sub-extractions
    class SousExtractions(BaseModel):
        sous_extractions: list[HypostaseExtraction] = Field(
            ..., max_length=5,
            description="0 a 5 sous-extractions interessantes dans ce chunk."
        )

    sous_ext = backend.appeler_llm_structured(
        modele=modele,
        response_model=SousExtractions,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_SOUS_EXTRACTIONS},
            {"role": "user", "content": (
                f"Chunk principal classifie comme {extraction_principale.hypostases}.\n\n"
                f"{chunk.content}\n\n"
                f"Identifie 0 a 5 sous-arguments distincts qui meriteraient une carte separee."
            )},
        ],
    )

    return extraction_principale, sous_ext.sous_extractions
```

**Critères d'activation** : à valider après l'alpha, avec métriques quantitatives
(% de chunks où l'utilisateur fait > N promotions manuelles).

**Coût** : double appel LLM sur les chunks denses (~10-30% des chunks). Acceptable
si la valeur ajoutée est mesurée.

### Si OpenRouter pose problème

Fallback : repartir sur appels directs aux providers (Anthropic SDK, OpenAI SDK,
Mistral SDK). instructor supporte tous ces SDK. La couche `OpenRouterBackend`
est isolée → swap d'implémentation sans toucher au reste.

### Si pgvector ne scale plus

Pour > 1M de chunks/extractions embeddés, pgvector commence à ralentir. Options :
- Index HNSW plus agressif
- Migration vers Qdrant ou Weaviate (plus complexe ops)

À reconsidérer quand le volume justifie. Au volume Hypostasia attendu
(quelques milliers de documents par instance), pgvector est largement suffisant.

---

## Annexe A — Squelettes de phases prêts à dérouler

Phases numérotées de 30 à 38, ordre suggéré dans la section 2 (calendrier).

### PHASE-30 — Sourçage `[N]` automatique des synthèses

**Complexité** : M | **Mode** : Normal | **Prérequis** : PHASE-28-light, PHASE-32

**Objectifs** :
- [ ] Modifier `_construire_prompt_synthese` pour numéroter les sources `[N]`
- [ ] Adapter le prompt système (règles de citation obligatoires)
- [ ] Schema Pydantic `SyntheseDelibérative` (synthese_html + citations_used)
- [ ] Appel LLM via `instructor` avec `response_model=SyntheseDelibérative`
- [ ] Implémenter `extraire_citations_synthese` qui parse `[N]` et crée SourceLinks
- [ ] Migration : ajouter `citation_index` (IntegerField) à SourceLink
- [ ] Migration : ajouter `commentaire_source` (FK) à SourceLink
- [ ] Templater `[N]` cliquables dans la V2 (template tag `render_citations`)
- [ ] Tests unitaires : mock LLM produit `[N]`, assert SourceLinks créés
- [ ] Tests E2E : générer synthèse, cliquer `[N]`, vérifier ouverture carte source
- [ ] Mettre à jour fixtures `demo_ia.json` (analyseur "Synthèse délibérative")

**Fichiers concernés** :
- `front/tasks.py` — `synthetiser_page_task`, `_construire_prompt_synthese`
- `core/models.py` — SourceLink (migration)
- `core/llm_providers.py` — exposer `appeler_llm_structured`
- `front/templates/front/includes/lecture_principale.html` — render `[N]` cliquables
- `hypostasis_extractor/templatetags/citations.py` — nouveau filter
- `front/fixtures/demo_ia.json` — analyseur Synthèse mis à jour

---

### PHASE-31 — Chunking markdown-aware

**Complexité** : M | **Mode** : Normal | **Prérequis** : aucun (indépendant)

**Objectifs** :
- [ ] Créer `core/chunking.py` avec `chunker_markdown` et `chunker_transcription`
- [ ] Méthode rasoir : Header > paragraphe > code block (jamais coupé)
- [ ] Paramètres Hypostasia : 400 tokens cible, 80 min, 800 max, 0 overlap
- [ ] Cas spécial : 1 bloc `<bloc-transcription>` = 1 chunk (atomique)
- [ ] Créer modèle `PageChunk` (page FK, chunk_index, content, start_char, end_char,
      metadata JSON, embedding VectorField nullable préparé pour PHASE-33)
- [ ] Migration data : générer les chunks pour toutes les Pages existantes (idempotent)
- [ ] Hook : recréer les chunks à chaque save de Page
- [ ] Tests unitaires : split markdown avec headers, code blocks, paragraphes, UTF-8
- [ ] Tests : split transcription par tour de parole, métadata locuteur préservée

**Fichiers à créer** :
- `core/chunking.py`
- `core/migrations/00XX_pagechunk.py`

**Fichiers à modifier** :
- `core/models.py` — ajouter PageChunk
- `pyproject.toml` — `tiktoken`, `markdown-it-py`

---

### PHASE-32 — OpenRouter + instructor

**Complexité** : S | **Mode** : Normal | **Prérequis** : PHASE-24

**Objectifs** :
- [ ] Ajouter `OpenRouterBackend` à `core/llm_providers.py` via `instructor.from_openai`
- [ ] Méthode `appeler_llm_structured(modele, messages, response_model, max_retries)`
- [ ] Méthode `appeler_llm_texte` (sans validation, pour texte libre)
- [ ] Méthode `embed_batch(textes, modele)` (préparation PHASE-33)
- [ ] Ajouter `openrouter` dans `AIModel.PROVIDER_CHOICES`
- [ ] Ajouter champs `openrouter_api_key`, `embedding_model` à `AIModel`
- [ ] Migration
- [ ] UI admin : champ pour la clé OpenRouter, sélecteur de modèle d'embedding
- [ ] `OllamaBackend` qui hérite de `OpenRouterBackend` (même infra, base_url différente)
- [ ] Tests : mock OpenRouter, structured output, embedding batch
- [ ] Documentation : `LANGEXTRACT_OVERRIDES.md` est obsolète (le mentionner dans le doc)

**Fichiers concernés** :
- `core/llm_providers.py`
- `core/models.py` — `AIModel`
- `pyproject.toml` — `instructor`, `openai`

---

### PHASE-33 — RAG socle : pgvector + pipeline d'embedding

**Complexité** : L | **Mode** : `/plan` d'abord | **Prérequis** : PHASE-31, PHASE-32

**Objectifs** :
- [ ] Migration : `CREATE EXTENSION vector`
- [ ] Migration : ajouter `embedding vector(1536)` à `PageChunk` et `ExtractedEntity`
- [ ] Migration : créer index HNSW sur les colonnes embedding
- [ ] Tâche Celery `embed_page_chunks_task` (batch 64 chunks par appel API)
- [ ] Tâche Celery `embed_extractions_task` (sur résumé + extraction_text)
- [ ] Hook : trigger `embed_page_chunks_task` après chaque création/modif de Page
- [ ] Hook : trigger `embed_extractions_task` après création d'ExtractedEntity
- [ ] Migration data : embedder toutes les pages et extractions existantes (batch
      Celery scheduled, idempotent via `embedding__isnull=True`)
- [ ] Page admin : voir l'avancement de l'embedding global (% chunks embeddés)
- [ ] Stocker `embedding_model_version` à côté du vecteur (pour gérer le re-embedding
      lors d'un changement de modèle)
- [ ] Tests : mock embedding, vecteurs stockés, queries pgvector OK

**Fichiers concernés** :
- `core/migrations/00XX_pgvector.py`
- `front/tasks.py` — nouvelles tâches Celery
- `core/models.py` — PageChunk + ExtractedEntity (champ embedding)
- `front/views.py` — page admin de monitoring
- `pyproject.toml` — `pgvector` + `django-pgvector`

---

### PHASE-34 — RAG features : recherche sémantique + cas d'usage

**Complexité** : L | **Mode** : Normal | **Prérequis** : PHASE-33

**Objectifs** :
- [ ] `RechercheSemantiqueViewSet` avec page dédiée (mockup `discussions/notes design suite.md` section 6)
- [ ] Action `chercher` : embed la requête, query pgvector, filtre par dossier visible
- [ ] Filtres : type cible (extractions / chunks), dossier, hypostase, statut, contributeur
- [ ] Détection de doublons à la création d'extraction (similarité > 0.85)
- [ ] Auto-suggestion d'hypostase basée sur similarité aux exemples few-shot
- [ ] Mode alignement sémantique (extension PHASE-18)
- [ ] Tests : queries semantic search, filtres, détection doublons, auto-suggestion

**Fichiers concernés** :
- `front/views_recherche.py` — `RechercheSemantiqueViewSet`
- `front/views_alignement.py` — mode sémantique
- `front/templates/front/recherche_semantique.html`
- `front/templates/front/includes/recherche_resultats.html`
- `hypostasis_extractor/views.py` — `ExtractionViewSet.creer_manuelle` (auto-suggestion)
- `front/services/embeddings.py` — utilitaires (cosine, KMeans, etc.)

---

### PHASE-35 — Chat agentique avec la base

**Complexité** : L | **Mode** : `/plan` d'abord | **Prérequis** : PHASE-34

**Objectifs** :
- [ ] Modèle `Conversation` (user + dossier scope + créé le)
- [ ] Modèle `ChatMessage` (conversation FK + role + content + tool_calls JSON)
- [ ] `ChatViewSet` avec interface HTMX (drawer ou page dédiée)
- [ ] Boucle agentique : LLM avec tools `chercher_extractions(query)`, `lire_page(id)`,
      `lire_commentaires(extraction_id)`
- [ ] Sourçage `[N]` dans les réponses (cohérent PHASE-30)
- [ ] Streaming HTMX (réponses au fur et à mesure via WebSocket)
- [ ] Tests : mock agent, vérifier appels tools, citations parsées

**Fichiers concernés** :
- `core/models.py` — Conversation, ChatMessage
- `front/views_chat.py` — ChatViewSet
- `front/templates/front/chat/` — templates dédiés
- `front/consumers.py` — WebSocket pour streaming

---

### PHASE-36 — Update incrémental section_ops

**Complexité** : L | **Mode** : `/plan` d'abord | **Prérequis** : PHASE-30

**Objectifs** :
- [ ] Schema Pydantic `SectionOp` + `SyntheseUpdate` (operations + citations_used)
- [ ] Prompt système `PROMPT_UPDATE_SECTION_OPS`
- [ ] Module `front/section_ops.py` avec `parser_sections` + `appliquer_ops`
- [ ] Adapter `synthetiser_page_task` : si page a déjà une V2, mode update
- [ ] Préserver les `[N]` existants byte-exact dans les sections non touchées
- [ ] Continuer la numérotation des `[N]` pour les nouveaux SourceLinks
- [ ] Modèle `SyntheseUpdate` (audit trail des opérations)
- [ ] Tests : append, replace, insert avec after_heading, NoChange
- [ ] Tests : SourceLinks existants préservés byte-exact

**Fichiers concernés** :
- `front/tasks.py` — `synthetiser_page_task` (mode update)
- `front/section_ops.py` — applier
- `core/models.py` — `SyntheseUpdate`
- `hypostasis_extractor/schemas.py` — SectionOp + SyntheseUpdate

---

### PHASE-37+ — Sociales × RAG (sous-phases indépendantes)

Sous-phases indépendantes, à dérouler selon priorité utilisateur. Chacune est petite
(S à M), peut être traitée indépendamment.

- **37a** — Notifications "ce qui te concerne" (S, post-PHASE-34)
- **37b** — Cartographie contributeurs (M, post-PHASE-34)
- **37c** — Détection contradiction cross-document (M, post-PHASE-34, délicate)
- ~~**37d** — Heat map sémantique (S, extension PHASE-19)~~ **DEPRECATED 2026-05-01 (PHASE-19 retirée, voir `discussions/YAGNI 2026-05-01.md`)**
- **37e** — Géométrie du débat enrichie 7e facette (M, concept Jean/Dominique)
- **37f** — Suggestion d'analyseur à l'import (S, extension PHASE-26b)

---

### PHASE-38 — Refonte pipeline extraction (Atomic-style, sans LangExtract)

**Complexité** : L | **Mode** : `/plan` d'abord | **Prérequis** : PHASE-31, PHASE-32

> **C'est la phase pivot du refactoring.** Elle remplace tout le pipeline d'extraction
> actuel par le modèle Atomic-style (1 chunk = 1 extraction) + supprime LangExtract.

**Objectifs** :
- [ ] Schemas Pydantic : `HypostaseExtraction` avec validation `Literal[HYPOSTASES_VALIDES]`
- [ ] Prompt système `SYSTEM_PROMPT_EXTRACTION` avec définitions des 30 hypostases
- [ ] Réécrire `analyser_page_task` :
  - Chunking via PHASE-31
  - Persistance des PageChunks
  - Pour chaque chunk : appel LLM via instructor → 1 ExtractedEntity (si pertinent)
  - Trigger embedding (PHASE-33)
- [ ] Migration ExtractedEntity :
  - Ajouter `chunk` FK vers PageChunk (nullable pour les manuelles)
  - Garder `start_char`/`end_char` (utilisés pour les manuelles uniquement)
  - Validation Pydantic stricte sur `attributes`
- [ ] Migration data : pour chaque page, regrouper les anciennes extractions par chunk
      et les fusionner (1 nouvelle ExtractedEntity par chunk avec hypostase la plus
      consensuelle, résumé fusionné, statut max, commentaires reportés)
- [ ] Soft delete des anciennes extractions (lien vers la nouvelle pour rollback)
- [ ] Adapter PHASE-09 templates : pastille position depuis `extraction.chunk.start_char`
- [ ] Adapter PHASE-26g hub d'analyse : streaming par chunk au lieu de par extraction
- [ ] Suppression : `AnnotateurAvecProgression`, auto-wrap JSON, dépendance LangExtract
- [ ] Suppression : `front/normalisation.py` (PHASE-29 devient inutile)
- [ ] Suppression : entrée `langextract` dans `pyproject.toml`
- [ ] Marquer `PLAN/LANGEXTRACT_OVERRIDES.md` comme déprécié
- [ ] Tests : pipeline complet, validation Pydantic, migration data, sélection manuelle
- [ ] Tests E2E : analyser une page, vérifier 5-10 extractions au lieu de 30+

**Fichiers concernés** :
- `front/tasks.py` — réécriture analyser_page_task
- `hypostasis_extractor/schemas.py` — schemas Pydantic
- `hypostasis_extractor/prompts.py` — SYSTEM_PROMPT_EXTRACTION
- `hypostasis_extractor/models.py` — ExtractedEntity (migration)
- `core/migrations/` — migration data
- `front/templates/front/includes/lecture_principale.html` — pastilles depuis chunks
- `front/templates/front/includes/drawer_vue_liste.html` — affichage cartes
- `pyproject.toml` — supprimer langextract, ajouter rapidfuzz si besoin
- `PLAN/LANGEXTRACT_OVERRIDES.md` — marquer déprécié
- Tests : `front/tests/test_phase38.py` (nouveaux)

---

## Annexe B — Mapping fichiers Atomic ↔ Hypostasia

| Concept | Atomic (référence) | Hypostasia (cible) |
|---|---|---|
| Provider LLM abstraction | `crates/atomic-core/src/providers/mod.rs` | `core/llm_providers.py` |
| Embedding pipeline | `crates/atomic-core/src/embedding.rs` | `front/tasks.py` (à créer : `embed_*_task`) |
| Chunking markdown | `crates/atomic-core/src/chunking.rs` | `core/chunking.py` (à créer) |
| Citation `[N]` mapping | `crates/atomic-core/src/wiki/mod.rs:662` (`extract_citations`) | `front/tasks.py` (à créer : `extraire_citations_synthese`) |
| Section ops applier | `crates/atomic-core/src/wiki/section_ops.rs` | `front/section_ops.py` (à créer) |
| Wiki generation prompt | `crates/atomic-core/src/wiki/mod.rs:524` (`WIKI_GENERATION_SYSTEM_PROMPT`) | `front/fixtures/demo_ia.json` (analyseur Synthèse) |
| Wiki update section ops prompt | `crates/atomic-core/src/wiki/mod.rs:551` (`WIKI_UPDATE_SECTION_OPS_PROMPT`) | À créer : `PROMPT_UPDATE_SECTION_OPS` |
| Auto-tagging system prompt | `crates/atomic-core/src/extraction.rs:120` (`SYSTEM_PROMPT`) | `hypostasis_extractor/prompts.py` (`SYSTEM_PROMPT_EXTRACTION`) |
| Vector storage | `crates/atomic-core/src/storage/sqlite/embeddings.rs` (sqlite-vec) | pgvector dans PostgreSQL |
| Semantic search | `crates/atomic-core/src/search.rs` | `front/views_recherche.py` (à créer : `RechercheSemantiqueViewSet`) |
| Chat agentique | `crates/atomic-core/src/chat.rs` | `front/views_chat.py` (à créer) |

---

## Annexe C — Lectures recommandées dans le code Atomic

Si tu veux comprendre Atomic en profondeur avant d'implémenter une phase :

1. **Architecture globale** : `/mnt/tank/Gits/atomic/CLAUDE.md` — overview du projet
2. **Provider abstraction** : `/mnt/tank/Gits/atomic/crates/atomic-core/src/providers/mod.rs`
   (~150 lignes, traits + factory)
3. **Pipeline embedding** : `/mnt/tank/Gits/atomic/crates/atomic-core/src/embedding.rs`
   (le pipeline async + auto-tagging + edges sémantiques)
4. **Chunking** : `/mnt/tank/Gits/atomic/crates/atomic-core/src/chunking.rs`
   (méthode rasoir, ~700 lignes avec tests)
5. **Wiki générator** : `/mnt/tank/Gits/atomic/crates/atomic-core/src/wiki/mod.rs`
   et `wiki/centroid.rs` (stratégie centroïde) et `wiki/agentic.rs` (stratégie agent)
6. **Section ops applier** : `/mnt/tank/Gits/atomic/crates/atomic-core/src/wiki/section_ops.rs`
   (le applier markdown qui préserve les sections inchangées byte-exact)
7. **Prompts wiki** : `/mnt/tank/Gits/atomic/crates/atomic-core/src/wiki/mod.rs:524-569`
   (3 prompts wiki) et `extraction.rs:96-145` (auto-tagging et consolidation)

---

## Annexe D — Continuation de session (pour Claude Code futur)

> Section auto-suffisante : si une session future démarre froid avec **ce seul document**
> en contexte, elle aura tout pour avancer.

### Contexte projet Hypostasia

- Plateforme de **lecture délibérative collective** : un groupe lit un texte, l'IA en
  extrait des passages clés (hypostases — 30 catégories en 8 familles), commentaires
  et débats par passage avec statuts évolutifs (consensuel/discutable/discuté/
  controversé/non pertinent/nouveau), seuil 80% consensus → V2 chaînée à V1
- Stack : Django 6 + DRF + HTMX + Tailwind + PostgreSQL 17 + Redis + Celery
- Conventions strictes (skill `stack-ccc`) : ViewSet explicite (jamais ModelViewSet),
  Serializers DRF (jamais Forms), HTMX (jamais SPA), noms verbeux, commentaires
  bilingues FR/EN
- 28+ phases planifiées dans `PLAN/PHASES/`, ~25 livrées
- Multi-user avec auth, partage, visibilité 3 niveaux, invitations email, crédits Stripe
- En **alpha**, sans utilisateurs réels — peut tout casser librement

### Préférences utilisateur (importantes)

- **Pas de `Co-Authored-By`** dans les commits — l'utilisateur veut l'attribution
  entièrement à son nom (cf. `~/.claude/projects/-mnt-tank-Gits-atomic/memory/`)
- **Pas de commandes git automatiques** (cf. CLAUDE.md section 8 d'Hypostasia) — l'user
  gère tout son git manuellement
- **Stack opinionée à respecter** (cf. GUIDELINES.md sections 1-5)
- **FALC autant UX que code** : pas sur-ingéniérer, code lisible, conventions strictes
- **Refactoring profond préféré au from scratch** (décision validée le 2026-04-26)

### Contexte Atomic

- KB personnelle Rust open source, déployée par l'utilisateur sur son VPS sous
  `https://atomic.nasjo.fr` via Docker + Traefik
- Repo Git cloné en lecture seule à `/mnt/tank/Gits/atomic/`
- Repo Hypostasia à `/mnt/tank/Gits/Hypostasia/`
- L'utilisateur a forké Atomic à `https://github.com/Nasjoe/atomic` pour des
  contributions ponctuelles (port Firefox du clipper)

### État du sourçage actuel (à comprendre)

- Atomic source ses synthèses (wikis) via `[N]` mapping — mécanisme bien rodé
  (`crates/atomic-core/src/wiki/mod.rs:662`)
- Hypostasia ne source PAS ses synthèses (PHASE-28-light génère du texte libre sans
  citations) — c'est l'objet de PHASE-30
- Modèles `SourceLink` et `PageEdit` existent dans Hypostasia mais SourceLink n'est
  peuplé qu'en PHASE-27c (manuelle, jamais implémentée). PHASE-30 l'automatisera.

### Décisions tranchées (résumées)

1. Adopter **1 chunk = 1 extraction** (option A, Atomic-style)
2. **Supprimer LangExtract** complètement
3. Garder la **sélection manuelle** pour la précision fine (philo, juridique)
4. **Sourçage `[N]`** automatique des synthèses
5. **Chunking markdown-aware** (paramètres : 400 tokens cible, 80 min, 800 max, 0 overlap)
6. **OpenRouter + instructor** pour tout LLM
7. **RAG via pgvector**
8. **Section_ops** pour update incrémental
9. **6 idées sociales × RAG** en backlog
10. **Refactoring profond, pas from scratch** (~75% du code reste)

### Ordre d'implémentation suggéré

1. **PHASE-31** (chunker markdown-aware) — base de tout
2. **PHASE-32** (OpenRouter + instructor)
3. **PHASE-38** (refonte pipeline extraction Atomic-style + suppression LangExtract)
4. **PHASE-30** (sourçage `[N]`)
5. **PHASE-33** (RAG socle pgvector)
6. **PHASE-34** (RAG features)
7. **PHASE-36** (update incrémental section_ops)
8. **PHASE-35** (chat agentique)
9. **PHASE-37** (sociales × RAG, sous-phases indépendantes)

### Comment démarrer une nouvelle session sur une phase

1. Lire ce document (INSPIRATION_ATOMIC.md) en entier
2. Identifier la phase à implémenter dans **Annexe A**
3. Lire la section correspondante du doc (ex: section 5 pour PHASE-30)
4. Lire le squelette de phase
5. Lire le PLAN/PHASES/INDEX.md pour les dépendances et l'historique
6. Optionnel : lire les fichiers Atomic référencés pour comprendre le pattern source
7. Brainstormer avec l'utilisateur si des points méritent clarification
8. Écrire la phase concrète dans `PLAN/PHASES/PHASE-XX.md` (template existant)
9. Implémenter

---

## Notes finales

Ce document est volontairement **opinioné**. Toutes les propositions sont discutables
et révisables. Le choix de pgvector vs autre vector store, le choix d'OpenRouter vs
provider direct, le seuil de similarité 0.5 vs 0.7 — autant de décisions à valider
avec l'utilisateur au moment de chaque phase concernée.

L'objectif n'est PAS de transformer Hypostasia en clone d'Atomic. C'est de capitaliser
sur les patterns que Atomic a éprouvés (sourçage, chunking, RAG, section ops) pour les
**adapter** à la dimension collective d'Hypostasia. La synthèse délibérative sourçée
vers les commentaires des contributeurs n'existe nulle part ailleurs — c'est le
différenciateur que ces axes vont rendre tangible.

Le refactoring n'est pas une fin en soi : chaque phase doit débloquer une valeur
mesurable pour l'utilisateur. Si une phase semble n'apporter que de la complexité
technique, la repenser ou la repousser.
