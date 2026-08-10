import hashlib
import re
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.conf import settings
from django.utils import timezone
from solo.models import SingletonModel

# Create your models here.


class SourceType(models.TextChoices):
    """Type de source d'une Page (web, fichier importe ou audio transcrit).
    / Source type for a Page (web, imported file or transcribed audio).
    """
    WEB = "web", "Page web"
    FILE = "file", "Fichier importé"
    AUDIO = "audio", "Audio transcrit"


class PageStatus(models.TextChoices):
    """Statut de traitement d'une Page dans le pipeline d'analyse.

    - pending: page créée mais non analysée
    - processing: analyse en cours (appel LLM, parsing, etc.)
    - completed: analyse terminée avec succès
    - error: erreur survenue (voir `error_message`)
    """

    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En cours d'analyse"
    COMPLETED = "completed", "Terminé"
    ERROR = "error", "Erreur"


class VisibiliteDossier(models.TextChoices):
    """Niveau de visibilite d'un dossier (prive, partage, public).
    / Folder visibility level (private, shared, public).
    """
    PRIVE = "prive", "Privé"
    PARTAGE = "partage", "Partagé"
    PUBLIC = "public", "Public"


class RoleSpecialDossier(models.TextChoices):
    """
    Role technique d'un carnet « magique », independant de son nom.
    / Technical role of a "magic" notebook, independent of its name.

    Avant ce champ, « A ranger » et « Mes imports » etaient retrouves par
    get_or_create(name=...) : un utilisateur qui renommait son carnet
    cassait ces flux (SPEC-corpus § 6.3).
    / Before this field, these notebooks were found by name; renaming
    them broke the flows.
    """
    A_RANGER = "a_ranger", "À ranger"
    MES_IMPORTS = "mes_imports", "Mes imports"


class Dossier(models.Model):
    """Dossier de classement pour organiser les pages.

    A l'ecran, un Dossier s'appelle un « carnet » (SPEC-corpus § 3.0 :
    le renommage du modele est abandonne, seul le mot affiche change).
    / On screen, a Dossier is called a "carnet" (notebook); the model
    rename was abandoned, only the displayed word changes.
    """

    name = models.CharField(max_length=200, help_text="Nom du dossier")
    # Proprietaire du dossier (null = legacy/donnees existantes)
    # / Folder owner (null = legacy/existing data)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="dossiers_possedes",
        help_text="Proprietaire du dossier (null = legacy) / Folder owner",
    )
    # Visibilite du dossier : prive (defaut), partage, public
    # / Folder visibility: private (default), shared, public
    # Description courte du dossier (optionnel)
    # / Short folder description (optional)
    description = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Description courte du dossier (optionnel) / Short folder description (optional)",
    )
    visibilite = models.CharField(
        max_length=10,
        choices=VisibiliteDossier.choices,
        default=VisibiliteDossier.PRIVE,
        help_text="Niveau de visibilite du dossier / Folder visibility level",
    )
    # Guide de redaction affiche au contributeur AU MOMENT ou il
    # contribue, pas range dans une page d'aide (modele Praxis,
    # SPEC-corpus § 2 « Pris — un TextField sur le dossier »).
    # / Writing guide shown at contribution time (Praxis model).
    guide_de_redaction = models.TextField(
        blank=True,
        default="",
        help_text="Conseils de redaction propres a ce carnet, montres "
                  "aux contributeurs. Vide = pas de guide.",
    )
    # Role technique du carnet, vide pour un carnet ordinaire.
    # Les flux « A ranger » et « Mes imports » filtrent sur ce champ,
    # plus jamais sur le nom (SPEC-corpus § 6.3).
    # / Technical role, empty for an ordinary notebook. Flows filter on
    # this field, never on the name anymore.
    role_special = models.CharField(
        max_length=20,
        choices=RoleSpecialDossier.choices,
        blank=True,
        default="",
        help_text="Role technique ('a_ranger', 'mes_imports') ou vide. "
                  "Un seul carnet par role et par proprietaire.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        constraints = [
            # Un proprietaire n'a qu'UN carnet « A ranger » et UN
            # « Mes imports ». Les carnets ordinaires (role vide) ne sont
            # pas limites.
            # / One "A ranger" and one "Mes imports" per owner; ordinary
            # notebooks are unlimited.
            models.UniqueConstraint(
                fields=["owner", "role_special"],
                condition=~models.Q(role_special=""),
                # Sans nulls_distinct=False, Postgres considere chaque
                # owner NULL comme distinct : un nombre illimite de
                # fourre-tout sans proprietaire pourrait exister (retour
                # de relecture).
                # / Without nulls_distinct=False, Postgres treats each
                # NULL owner as distinct.
                nulls_distinct=False,
                name="unicite_role_special_par_proprietaire",
            ),
        ]


class MoteurDePage(models.TextChoices):
    """
    Le moteur d'ancrage d'une Page (SPEC-ancrage v2 § 9, branchement
    BR-A). Les DEUX coexistent : les pages existantes restent ANCIEN et
    fonctionnent a l'identique ; toute nouvelle page ingeree passe par
    ELEMENT. Un CHAMP explicite, pas `elements.exists()` : une
    ingestion ELEMENT echouee laisse zero element et serait prise pour
    une page ANCIEN (decision D1, cahier du branchement, 9 aout).
    / The page's anchoring engine; explicit field, never inferred.
    """
    ANCIEN = "ancien", "Ancien moteur (offsets)"
    ELEMENT = "element", "Moteur par élément"


class TypeDeNote(models.TextChoices):
    """
    Ce qu'une note EST. Ce n'est pas une etiquette d'affichage : le type
    decide si la note peut servir de SOURCE a une synthese
    (core/services/synthese.py, SPEC-synthese § 3.3).
    / Not a display label: the type decides source eligibility.
    """
    NOTE = "note", "Note"
    WIKI = "wiki", "Wiki"
    SYNTHESE = "synthese", "Synthèse dirigée"


class Page(models.Model):
    """Représente une page web capturée par l'extension.

    Règles (voir GUIDELINES):
    - `html_original` est immuable après création.
    - `content_hash` = SHA256 de `text_readability`.
    - Les `TextBlock` liés ancrent les passages dans le DOM.
    """

    parent_page = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="versions_enfants",
        help_text="Page parente — celle-ci est une version (synthese) de la parente / Parent page — this is a version (synthesis) of parent",
    )
    version_number = models.PositiveIntegerField(
        default=1,
        help_text="Numero de version (1 = original) / Version number (1 = original)",
    )
    version_label = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Label descriptif de cette version / Descriptive label for this version",
    )
    dossier = models.ForeignKey(
        "Dossier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pages",
        help_text="Dossier de classement (optionnel)",
    )
    # Le genre de la note. Un champ et non une propriete derivee : la
    # regle « une synthese n'est jamais source » doit etre exprimable en
    # une clause filter(), pas en boucle Python (SPEC-synthese § 2).
    # / The note's kind, as a field: the exclusion rule must be a filter
    # clause, never a Python loop.
    # Le moteur d'ancrage de cette page (SPEC-ancrage v2 § 9). Ecrit a
    # l'ingestion, jamais bascule en douce — la reconversion ANCIEN ->
    # ELEMENT est une commande explicite du proprietaire (§ 9.5).
    # / The anchoring engine, set at ingestion time, never silently
    # switched.
    moteur = models.CharField(
        max_length=10,
        choices=MoteurDePage.choices,
        default=MoteurDePage.ANCIEN,
        db_index=True,
        help_text="Moteur d'ancrage : 'ancien' (offsets plats) ou "
                  "'element' (ElementDocument + portions). Les deux "
                  "coexistent, aucune migration de force.",
    )
    type_de_note = models.CharField(
        max_length=10,
        choices=TypeDeNote.choices,
        default=TypeDeNote.NOTE,
        db_index=True,
        help_text="Ce que cette note est. Une synthese ou un wiki n'est "
                  "JAMAIS source d'une autre synthese — voir "
                  "core/services/synthese.py. / A synthesis is never a "
                  "source for another synthesis.",
    )
    # Proprietaire de la page (null = legacy/donnees existantes)
    # / Page owner (null = legacy/existing data)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="pages_possedees",
        help_text="Proprietaire de la page (null = legacy) / Page owner",
    )
    source_type = models.CharField(
        max_length=10,
        choices=SourceType.choices,
        default=SourceType.WEB,
        help_text="Type de source : page web ou fichier importé",
    )
    original_filename = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Nom du fichier original (uniquement pour source_type='file')",
    )
    url = models.URLField(
        blank=True,
        null=True,
        help_text="URL canonique de la page analysée (null pour les fichiers importés)",
    )
    title = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Titre optionnel détecté ou saisi",
    )
    html_original = models.TextField(
        help_text="HTML original complet (immuable après création)"
    )
    html_readability = models.TextField(
        help_text="HTML simplifié (Readability) pour l'analyse"
    )
    text_readability = models.TextField(
        help_text="Texte brut extrait de Readability (base de l'analyse)"
    )
    content_hash = models.CharField(
        max_length=64, blank=True, help_text="SHA256 hex du `text_readability`"
    )  # SHA256 hex digest

    # Fichier source original uploade (audio, document, JSON)
    # / Original uploaded source file (audio, document, JSON)
    source_file = models.FileField(
        upload_to="sources/",
        null=True,
        blank=True,
        help_text="Fichier source original (audio, document ou JSON uploade)",
    )

    # Donnees brutes de transcription audio (segments JSON du modele)
    # / Raw audio transcription data (model JSON segments)
    transcription_raw = models.JSONField(
        null=True,
        blank=True,
        help_text="Segments JSON bruts de la transcription audio (immuable apres creation)",
    )

    status = models.CharField(
        max_length=20,
        choices=PageStatus.choices,
        default=PageStatus.PENDING,
        help_text="Statut de la dernière analyse",
    )
    error_message = models.TextField(
        blank=True, null=True, help_text="Message d'erreur éventuel lors de l'analyse"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["url"],
                condition=models.Q(url__isnull=False),
                name="unique_url_si_presente",
            ),
        ]

    def __str__(self):
        return self.title if self.title else (self.url or self.original_filename or "Page sans titre")

    @property
    def domain(self):
        # Retourne le domaine de l'URL, ou "fichier" si pas d'URL
        # / Returns the URL domain, or "fichier" if no URL
        if not self.url:
            return "fichier"
        from urllib.parse import urlparse
        try:
            return urlparse(self.url).netloc
        except Exception:
            return ""

    @property
    def first_image_url(self):
        """Retourne la première URL d’image trouvée dans `html_readability` (si présente)."""
        import re

        if not self.html_readability:
            return None
        match = re.search(r'<img[^>]+src="([^">]+)"', self.html_readability)
        if match:
            return match.group(1)
        return None

    @property
    def page_racine(self):
        """Remonte jusqu'a la page sans parent (racine de la chaine de restitutions).
        / Walks up to the root page (no parent) of the restitution chain.
        """
        page_courante = self
        while page_courante.parent_page is not None:
            page_courante = page_courante.parent_page
        return page_courante

    @property
    def toutes_les_versions(self):
        """QuerySet de toutes les versions (racine + restitutions), triees par version_number.
        / QuerySet of all versions (root + restitutions), ordered by version_number.
        """
        racine = self.page_racine
        from django.db.models import Q
        return Page.objects.filter(
            Q(pk=racine.pk) | Q(parent_page=racine)
        ).order_by("version_number")


class HypostasisTag(models.Model):
    """Nouveau modèle pour les hypostases (tags)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class HypostasisChoices(models.TextChoices):
    """Taxonomie des hypostases (typologie conceptuelle) assignables à un bloc.
    Sert de guide pour le LLM et de base pour les premières instances de HypostasisTag.
    """

    CLASSIFICATION = "classification", "classification"
    APORIE = "aporie", "aporie"
    APPROXIMATION = "approximation", "approximation"
    PARADOXE = "paradoxe", "paradoxe"
    FORMALISME = "formalisme", "formalisme"
    EVENEMENT = "événement", "événement"
    VARIATION = "variation", "variation"
    DIMENSION = "dimension", "dimension"
    MODE = "mode", "mode"
    CROYANCE = "croyance", "croyance"
    INVARIANT = "invariant", "invariant"
    VALEUR = "valeur", "valeur"
    STRUCTURE = "structure", "structure"
    AXIOME = "axiome", "axiome"
    CONJECTURE = "conjecture", "conjecture"
    PARADIGME = "paradigme", "paradigme"
    OBJET = "objet", "objet"
    PRINCIPE = "principe", "principe"
    DOMAINE = "domaine", "domaine"
    LOI = "loi", "loi"
    PHENOMENE = "phénomène", "phénomène"
    VARIABLE = "variable", "variable"
    VARIANCE = "variance", "variance"
    INDICE = "indice", "indice"
    DONNEE = "donnée", "donnée"
    METHODE = "méthode", "méthode"
    DEFINITION = "définition", "définition"
    HYPOTHESE = "hypothèse", "hypothèse"
    PROBLEME = "problème", "problème"
    THEORIE = "théorie", "théorie"


class Modes(models.TextChoices):
    """Modes de débat associés au contenu du bloc (statut argumentatif)."""

    IN = "IN", "A initier"
    DC = "DC", "Discuté"
    DP = "DP", "Disputé"
    CT = "CT", "controversé"
    CS = "CS", "consensuel"


class Theme(models.Model):
    """Thème ou catégorie sémantique, réutilisable sur plusieurs blocs."""

    name = models.CharField(
        max_length=200, help_text="Nom du thème (ex: Énergie, Climat)"
    )
    description = models.TextField(
        blank=True, help_text="Description optionnelle du thème"
    )


class TextBlock(models.Model):
    """Bloc de texte ancré dans le DOM via un sélecteur CSS et des offsets.

    Sert d’ancrage pour les Arguments et porte les métadonnées de classification
    (hypostase, mode, thèmes). Les offsets sont relatifs au `textContent` du nœud.
    """

    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="blocks",
        help_text="Page à laquelle appartient ce bloc",
    )
    selector = models.CharField(
        max_length=500,
        help_text="Sélecteur CSS (querySelector) qui pointe vers le nœud",
    )
    start_offset = models.IntegerField(
        help_text="Offset de départ dans le `textContent` du nœud"
    )
    end_offset = models.IntegerField(
        help_text="Offset de fin dans le `textContent` du nœud"
    )
    text = models.TextField(help_text="Texte brut du bloc (extrait côté extension)")
    significant_extract = models.TextField(
        blank=True, null=True, help_text="Extrait représentatif et concis du bloc"
    )
    hypostases = models.ManyToManyField(
        HypostasisTag,
        related_name="text_blocks",
        blank=True,
        verbose_name="Hypostases",
        help_text="Typologies conceptuelles (ex: classification, axiome, théorie…)",
    )
    modes = models.CharField(
        max_length=20,
        choices=Modes.choices,
        default=Modes.IN,
        verbose_name="Mode de débat",
        help_text="Statut argumentatif du contenu (ex: discuté, consensuel)",
    )
    themes = models.ManyToManyField(
        Theme, related_name="text_blocks", help_text="Thèmes associés à ce bloc"
    )

    def __str__(self):
        return f"Bloc sur {self.page} ({self.selector})"


class Argument(models.Model):
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="arguments",
        help_text="Page source de l’argument",
    )
    text_block = models.ForeignKey(
        TextBlock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="arguments",
        help_text="Bloc d’origine si l’argument est ancré sur un passage précis",
    )
    selector = models.CharField(
        max_length=500,
        help_text="Sélecteur CSS du passage (doublon de sécurité si `text_block` est nul)",
    )
    start_offset = models.IntegerField(
        help_text="Offset de départ dans le nœud ciblé (sélecteur)"
    )
    end_offset = models.IntegerField(
        help_text="Offset de fin dans le nœud ciblé (sélecteur)"
    )

    text_original = models.TextField(
        help_text="Texte source sur lequel l’argument se base"
    )
    summary = models.TextField(
        help_text="Résumé de l’argument (généré par IA ou édité)"
    )
    # stance removed as per new architecture (focus on 'modes' in TextBlock)

    user_edited = models.BooleanField(
        default=False, help_text="Coché si un humain a modifié l’argument"
    )
    # invalidated = models.BooleanField(default=False)  # À introduire si l’invalidation automatique est activée (voir GUIDELINES §7)
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Horodatage de création"
    )

    def __str__(self):
        return f"{self.summary[:50]}..."


class ArgumentComment(models.Model):
    """Commentaire utilisateur attaché à un argument."""

    argument = models.ForeignKey(
        Argument,
        on_delete=models.CASCADE,
        related_name="comments",
        help_text="Argument commenté",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text="Auteur du commentaire",
    )
    comment = models.TextField(help_text="Contenu du commentaire")
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Horodatage de création"
    )

    def __str__(self):
        return f"Commentaire de {self.author} sur l’argument {self.argument.id}"


#### ANALYSE AI ####


class Provider(models.TextChoices):
    """
    Fournisseur du modele d'IA.
    Google et OpenAI sont supportes par LangExtract (extraction).
    Ollama et Anthropic sont supportes pour la reformulation/restitution.
    / AI model provider.
    Google and OpenAI are supported by LangExtract (extraction).
    Ollama and Anthropic are supported for reformulation/restitution.
    """

    MOCK = "mock", "Mock (Simulation)"
    GOOGLE = "google", "Google Gemini"
    OPENAI = "openai", "OpenAI GPT"
    OLLAMA = "ollama", "Ollama (Local)"
    ANTHROPIC = "anthropic", "Anthropic Claude"


class AIModelChoices(models.TextChoices):
    """
    Liste des modeles AI disponibles dans l'application.
    Google Gemini et OpenAI GPT sont supportes pour l'extraction (LangExtract).
    Ollama est supporte pour l'extraction et la reformulation.
    Anthropic Claude est supporte pour la reformulation et la restitution uniquement.
    / List of AI models available in the application.
    Google and OpenAI for extraction (LangExtract). Ollama for extraction + reformulation.
    Anthropic for reformulation/restitution only.
    """

    # Google / Gemini
    GOOGLE_GEMINI_2_5_PRO = "gemini-2.5-pro", "Gemini 2.5 Pro (Google)"
    GOOGLE_GEMINI_2_5_FLASH = "gemini-2.5-flash", "Gemini 2.5 Flash (Google)"
    GOOGLE_GEMINI_2_5_FLASH_LITE = (
        "gemini-2.5-flash-lite",
        "Gemini 2.5 Flash Lite (Google)",
    )
    GOOGLE_GEMINI_2_FLASH = "gemini-2.0-flash", "Gemini 2.0 Flash (Google)"
    GOOGLE_GEMINI_2_FLASH_LITE = (
        "gemini-2.0-flash-lite",
        "Gemini 2.0 Flash Lite (Google)",
    )
    GOOGLE_GEMINI_1_5_PRO = "gemini-1.5-pro", "Gemini 1.5 Pro (Google)"
    GOOGLE_GEMINI_1_5_FLASH = "gemini-1.5-flash", "Gemini 1.5 Flash (Google)"

    # OpenAI / GPT
    OPENAI_GPT_4O = "gpt-4o", "GPT-4o (OpenAI)"
    OPENAI_GPT_4O_MINI = "gpt-4o-mini", "GPT-4o Mini (OpenAI)"
    OPENAI_GPT_4_TURBO = "gpt-4-turbo", "GPT-4 Turbo (OpenAI)"
    OPENAI_GPT_4_1 = "gpt-4.1", "GPT-4.1 (OpenAI)"
    OPENAI_GPT_4_1_MINI = "gpt-4.1-mini", "GPT-4.1 Mini (OpenAI)"

    # Ollama (Local)
    OLLAMA_LLAMA3 = "llama3", "Llama 3 (Ollama)"
    OLLAMA_LLAMA3_1 = "llama3.1", "Llama 3.1 (Ollama)"
    OLLAMA_MISTRAL = "mistral", "Mistral (Ollama)"
    OLLAMA_GEMMA2 = "gemma2", "Gemma 2 (Ollama)"
    OLLAMA_QWEN2_5 = "qwen2.5", "Qwen 2.5 (Ollama)"
    OLLAMA_DEEPSEEK_R1 = "deepseek-r1", "DeepSeek R1 (Ollama)"
    OLLAMA_PHI3 = "phi3", "Phi 3 (Ollama)"

    # Anthropic / Claude
    ANTHROPIC_CLAUDE_SONNET_4 = "claude-sonnet-4-20250514", "Claude Sonnet 4 (Anthropic)"
    ANTHROPIC_CLAUDE_HAIKU_4 = "claude-haiku-4-20250414", "Claude Haiku 4 (Anthropic)"

    # Mock (Simulation)
    MOCK_DEFAULT = "mock", "Mock / Simulation"


class AIModel(models.Model):
    """
    Configuration d'un modèle AI pour l'analyse.
    / AI model configuration for analysis.

    ARCHITECTURE:
    - model_choice: Nouveau champ unifié (ChoiceField avec tous les modèles)
    - provider & model_name: Champs legacy pour rétrocompatibilité

    Le provider est déduit automatiquement du model_choice choisi.
    / Provider is automatically inferred from the selected model_choice.
    """

    name = models.CharField(
        max_length=100, help_text="Nom d'affichage personnalisé (optionnel)", blank=True
    )

    # NOUVEAU: Champ unifié pour choisir modèle + provider en un seul clic
    # / NEW: Unified field to choose model + provider in one click
    model_choice = models.CharField(
        max_length=100,
        choices=AIModelChoices.choices,
        default=AIModelChoices.MOCK_DEFAULT,
        help_text="Modèle AI à utiliser (sélection unique qui détermine automatiquement le provider)",
    )

    # CHAMPS LEGACY: Conservés pour rétrocompatibilité avec les données existantes
    # / LEGACY FIELDS: Kept for backward compatibility with existing data
    provider = models.CharField(
        max_length=50,
        choices=Provider.choices,
        default=Provider.MOCK,
        help_text="[LEGACY] Fournisseur - déduit automatiquement du modèle choisi",
    )
    model_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="[LEGACY] Nom technique - déduit automatiquement du modèle choisi",
    )

    base_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="URL de base du serveur (utilise par Ollama, ex: http://localhost:11434)",
    )
    temperature = models.FloatField(
        default=0.7, help_text="Température d'échantillonnage du LLM"
    )
    is_active = models.BooleanField(
        default=True, help_text="Modèle activé pour sélection"
    )

    def save(self, *args, **kwargs):
        """
        Synchronise automatiquement provider et model_name depuis model_choice.
        / Automatically synchronizes provider and model_name from model_choice.

        Cette méthode assure la rétrocompatibilité:
        - Quand on choisit un model_choice, les champs legacy sont mis à jour
        - Les anciennes données restent fonctionnelles
        """
        if self.model_choice:
            # Deduit le provider depuis la VALEUR du model_choice (ex: "gemini-2.5-flash")
            # / Infer provider from model_choice VALUE (e.g. "gemini-2.5-flash")
            choice_value = self.model_choice.lower()

            # Mapping des prefixes de valeur vers les providers
            # / Mapping of value prefixes to providers
            prefix_to_provider = [
                ("gemini-", Provider.GOOGLE),
                ("gpt-", Provider.OPENAI),
                ("llama", Provider.OLLAMA),
                ("mistral", Provider.OLLAMA),
                ("gemma", Provider.OLLAMA),
                ("qwen", Provider.OLLAMA),
                ("deepseek", Provider.OLLAMA),
                ("phi", Provider.OLLAMA),
                ("claude-", Provider.ANTHROPIC),
                ("mock", Provider.MOCK),
            ]

            for prefix, provider_value in prefix_to_provider:
                if choice_value.startswith(prefix):
                    self.provider = provider_value
                    break

            # Le model_name technique est directement la valeur du choice
            # / The technical model_name is directly the choice value
            self.model_name = self.model_choice

        super().save(*args, **kwargs)

    def get_display_name(self):
        """
        Retourne le nom d'affichage officiel du modèle.
        / Returns the official display name of the model.

        Priorité:
        1. name personnalisé si défini
        2. Libellé du model_choice
        """
        if self.name:
            return self.name
        return dict(AIModelChoices.choices).get(self.model_choice, self.model_choice)

    @property
    def technical_model_name(self):
        """
        Retourne le nom technique pour les appels API.
        / Returns the technical name for API calls.
        """
        return self.model_name or self.model_choice

    # Tarification par million de tokens (input, output) en USD
    # Sources : https://ai.google.dev/gemini-api/docs/pricing
    #           https://openai.com/api/pricing/
    # / Pricing per million tokens (input, output) in USD
    # Tarifs mis a jour le 2026-03-15 depuis :
    #   https://ai.google.dev/pricing
    #   https://openai.com/api/pricing/
    # / Pricing updated 2026-03-15 from official sources
    TARIFS_PAR_MILLION_TOKENS = {
        # Google Gemini — prix standard (paid tier) input/output par million de tokens
        # / Google Gemini — standard (paid tier) input/output price per million tokens
        "gemini-2.5-pro": (1.25, 10.00),
        "gemini-2.5-flash": (0.30, 2.50),
        "gemini-2.5-flash-lite": (0.075, 0.30),
        "gemini-2.0-flash": (0.10, 0.40),
        "gemini-2.0-flash-lite": (0.075, 0.30),
        "gemini-1.5-pro": (1.25, 5.00),
        "gemini-1.5-flash": (0.075, 0.30),
        # OpenAI GPT — prix input/output par million de tokens
        # / OpenAI GPT — input/output price per million tokens
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-4.1": (2.00, 8.00),
        "gpt-4.1-mini": (0.40, 1.60),
        # Ollama — gratuit (local) / Ollama — free (local)
        "llama3": (0.0, 0.0),
        "llama3.1": (0.0, 0.0),
        "mistral": (0.0, 0.0),
        "gemma2": (0.0, 0.0),
        "qwen2.5": (0.0, 0.0),
        "deepseek-r1": (0.0, 0.0),
        "phi3": (0.0, 0.0),
        # Anthropic Claude — prix input/output par million de tokens
        # / Anthropic Claude — input/output price per million tokens
        "claude-sonnet-4-20250514": (3.00, 15.00),
        "claude-haiku-4-20250414": (0.80, 4.00),
        # Mock — gratuit / Mock — free
        "mock": (0.0, 0.0),
    }

    # Multiplicateur de tokens output pour les modeles avec mode "thinking".
    # Le thinking genere des tokens de reflexion internes factures au tarif output.
    # Le ratio varie selon la complexite de la requete (3x a 8x observe).
    # On utilise 5x comme estimation conservatrice.
    # Les modeles absents de cette table n'ont pas de thinking (multiplicateur = 1).
    # / Output token multiplier for models with "thinking" mode.
    # / Thinking generates internal reasoning tokens billed at output rate.
    # / Ratio varies by request complexity (3x to 8x observed).
    # / We use 5x as a conservative estimate.
    # / Models not in this table have no thinking (multiplier = 1).
    MULTIPLICATEUR_THINKING = {
        "gemini-2.5-pro": 5,
        "gemini-2.5-flash": 5,
    }

    def multiplicateur_thinking(self):
        """
        Retourne le multiplicateur de tokens output lie au mode thinking.
        1 si le modele n'a pas de thinking, N si oui.
        / Returns the output token multiplier for thinking mode.
        1 if the model has no thinking, N if it does.
        """
        nom_technique = self.technical_model_name.lower()
        return self.MULTIPLICATEUR_THINKING.get(nom_technique, 1)

    def cout_par_million_tokens(self):
        """
        Retourne le tuple (cout_input, cout_output) en USD par million de tokens.
        Si le modele n'est pas dans la table, retourne (0.0, 0.0).
        / Returns the (input_cost, output_cost) tuple in USD per million tokens.
        If the model is not in the table, returns (0.0, 0.0).
        """
        nom_technique = self.technical_model_name.lower()
        return self.TARIFS_PAR_MILLION_TOKENS.get(nom_technique, (0.0, 0.0))

    def estimer_cout_euros(self, nombre_tokens_input, nombre_tokens_output_estime=0, taux_usd_eur=0.92):
        """
        Estime le cout en euros pour un nombre de tokens donne.
        Le nombre de tokens output est estime a 20% de l'input par defaut si non fourni.
        / Estimates cost in euros for a given number of tokens.
        Output token count defaults to 20% of input if not provided.
        """
        cout_input_usd, cout_output_usd = self.cout_par_million_tokens()

        if nombre_tokens_output_estime == 0:
            nombre_tokens_output_estime = int(nombre_tokens_input * 0.20)

        cout_total_usd = (
            (nombre_tokens_input / 1_000_000) * cout_input_usd
            + (nombre_tokens_output_estime / 1_000_000) * cout_output_usd
        )

        cout_total_euros = cout_total_usd * taux_usd_eur
        return cout_total_euros

    def __str__(self):
        return f"{self.get_display_name()} [{self.get_provider_display()}]"


class Prompt(models.Model):
    name = models.CharField(
        max_length=200, help_text="Nom lisible du prompt composable"
    )
    description = models.TextField(
        blank=True, help_text="Description / intention du prompt"
    )
    default_model = models.ForeignKey(
        AIModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prompts",
        help_text="Modèle par défaut utilisé pour ce prompt",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Horodatage de création"
    )

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    """Rôle d’un `TextInput` dans la composition d’un prompt."""

    CONTEXT = "context", "Contexte sémantique"
    INSTRUCTION = "instruction", "Instruction"
    FORMAT = "format", "Format de sortie"


class TextInput(models.Model):
    prompt = models.ForeignKey(
        Prompt,
        on_delete=models.CASCADE,
        related_name="inputs",
        help_text="Prompt auquel appartient cette brique",
    )
    name = models.CharField(max_length=200, help_text="Nom lisible de la brique")
    role = models.CharField(
        max_length=50,
        choices=Role.choices,
        help_text="Rôle de la brique dans le prompt",
    )
    content = models.TextField(help_text="Contenu texte de la brique (sera concaténé)")
    order = models.PositiveIntegerField(
        default=0, help_text="Ordre d’assemblage dans le prompt"
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} ({self.role})"


class Configuration(SingletonModel):
    """
    Configuration singleton globale de l'application.
    Global singleton configuration for the application.
    Controle l'activation de l'IA et le modele actif.
    / Controls AI activation and the active model.
    """
    ai_active = models.BooleanField(
        default=False,
        help_text="Active ou desactive l'IA globalement / Globally enable or disable AI",
    )
    ai_model = models.ForeignKey(
        AIModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Modele IA actuellement selectionne / Currently selected AI model",
    )

    class Meta:
        verbose_name = "Configuration"

    def __str__(self):
        return "Configuration"


#### TRANSCRIPTION AUDIO ####


class TranscriptionProvider(models.TextChoices):
    """Fournisseur de transcription audio.
    / Audio transcription provider.
    """
    VOXTRAL = "voxtral", "Voxtral (Mistral AI)"
    MOCK = "mock", "Mock (Simulation)"


class TranscriptionModelChoices(models.TextChoices):
    """
    Liste des modeles de transcription audio disponibles par provider.
    / List of available audio transcription models per provider.

    Format: PROVIDER_MODEL = "technical_name", "Display Name (Provider)"
    Le provider est deduit automatiquement du prefixe de la valeur.
    / Provider is automatically inferred from the value prefix.
    """

    # Voxtral / Mistral AI — endpoint dedie audio/transcriptions
    # / Voxtral / Mistral AI — dedicated audio/transcriptions endpoint
    VOXTRAL_MINI = "voxtral-mini-latest", "Voxtral Mini (Mistral AI)"

    # Mistral AI — modeles multimodaux (chat.complete avec audio_url)
    # / Mistral AI — multimodal models (chat.complete with audio_url)
    MISTRAL_SMALL = "mistral-small-latest", "Mistral Small (Mistral AI)"
    MISTRAL_LARGE = "mistral-large-latest", "Mistral Large (Mistral AI)"

    # Mock (Simulation)
    MOCK_DEFAULT = "mock", "Mock / Simulation"


class TranscriptionConfig(models.Model):
    """
    Configuration d'un outil de transcription audio (pattern identique a AIModel).
    / Audio transcription tool configuration (same pattern as AIModel).

    ARCHITECTURE:
    - model_choice: Champ unifie (ChoiceField avec tous les modeles de transcription)
    - provider & model_name: Champs legacy synchronises automatiquement
    / - model_choice: Unified field (ChoiceField with all transcription models)
    / - provider & model_name: Legacy fields automatically synced
    """
    name = models.CharField(
        max_length=100,
        help_text="Nom d'affichage de la configuration de transcription",
    )

    # Champ unifie pour choisir modele + provider en un seul clic
    # / Unified field to choose model + provider in one click
    model_choice = models.CharField(
        max_length=100,
        choices=TranscriptionModelChoices.choices,
        default=TranscriptionModelChoices.MOCK_DEFAULT,
        help_text="Modele de transcription (determine automatiquement le provider)",
    )

    # Champs legacy synchronises automatiquement via save()
    # / Legacy fields automatically synced via save()
    provider = models.CharField(
        max_length=50,
        choices=TranscriptionProvider.choices,
        default=TranscriptionProvider.MOCK,
        help_text="[LEGACY] Fournisseur - deduit automatiquement du modele choisi",
    )
    model_name = models.CharField(
        max_length=100,
        default="mock",
        help_text="[LEGACY] Nom technique - deduit automatiquement du modele choisi",
    )

    language = models.CharField(
        max_length=10,
        default="fr",
        help_text="Code langue pour la transcription (ex: fr, en)",
    )
    diarization_enabled = models.BooleanField(
        default=True,
        help_text="Activer la diarisation (identification des locuteurs)",
    )
    max_speakers = models.PositiveIntegerField(
        default=5,
        help_text="Nombre maximum de locuteurs a detecter",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Configuration active pour la transcription",
    )

    def save(self, *args, **kwargs):
        """
        Synchronise automatiquement provider et model_name depuis model_choice.
        / Automatically synchronizes provider and model_name from model_choice.
        """
        if self.model_choice:
            valeur_choix = self.model_choice.lower()

            # Mapping des prefixes vers les providers
            # Ordre important : les prefixes les plus specifiques d'abord
            # / Mapping of prefixes to providers
            # Order matters: most specific prefixes first
            prefixes_vers_provider = [
                ("voxtral-", TranscriptionProvider.VOXTRAL),
                ("mistral-", TranscriptionProvider.VOXTRAL),
                ("mock", TranscriptionProvider.MOCK),
            ]

            for prefixe, valeur_provider in prefixes_vers_provider:
                if valeur_choix.startswith(prefixe):
                    self.provider = valeur_provider
                    break

            # Le model_name technique est directement la valeur du choice
            # / The technical model_name is directly the choice value
            self.model_name = self.model_choice

        super().save(*args, **kwargs)

    def get_display_name(self):
        """
        Retourne le nom d'affichage officiel du modele de transcription.
        / Returns the official display name of the transcription model.
        """
        if self.name:
            return self.name
        return dict(TranscriptionModelChoices.choices).get(self.model_choice, self.model_choice)

    # Tarification par minute en USD
    # Sources : https://mistral.ai/news/voxtral-transcribe-2
    # / Pricing per minute in USD
    TARIFS_PAR_MINUTE_USD = {
        # Voxtral Mini — batch transcription
        "voxtral-mini-latest": 0.003,
        # Mistral Small — multimodal chat (tarif audio approximatif)
        # / Mistral Small — multimodal chat (approximate audio rate)
        "mistral-small-latest": 0.005,
        # Mistral Large — multimodal chat (tarif audio approximatif)
        # / Mistral Large — multimodal chat (approximate audio rate)
        "mistral-large-latest": 0.01,
        # Mock — gratuit / Mock — free
        "mock": 0.0,
    }

    def cout_par_minute_usd(self):
        """
        Retourne le cout en USD par minute de transcription.
        Si le modele n'est pas dans la table, retourne 0.0.
        / Returns the cost in USD per minute of transcription.
        If the model is not in the table, returns 0.0.
        """
        nom_technique = (self.model_name or self.model_choice).lower()
        return self.TARIFS_PAR_MINUTE_USD.get(nom_technique, 0.0)

    def estimer_cout_euros(self, duree_secondes, taux_usd_eur=0.92):
        """
        Estime le cout en euros pour une duree audio donnee en secondes.
        / Estimates cost in euros for a given audio duration in seconds.
        """
        duree_minutes = duree_secondes / 60.0
        cout_usd = duree_minutes * self.cout_par_minute_usd()
        return cout_usd * taux_usd_eur

    def __str__(self):
        return f"{self.get_display_name()} [{self.get_provider_display()}]"

    class Meta:
        verbose_name = "Configuration de transcription"
        verbose_name_plural = "Configurations de transcription"


class TranscriptionJobStatus(models.TextChoices):
    """Statut d'un job de transcription audio.
    / Status of an audio transcription job.
    """
    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En cours"
    COMPLETED = "completed", "Termine"
    ERROR = "error", "Erreur"


class TranscriptionJob(models.Model):
    """
    Job de transcription audio lie a une Page.
    Suit la progression de la tache Celery et stocke le resultat brut.
    / Audio transcription job linked to a Page.
    Tracks Celery task progress and stores raw result.
    """
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="transcription_jobs",
        help_text="Page associee a cette transcription",
    )
    transcription_config = models.ForeignKey(
        TranscriptionConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
        help_text="Configuration de transcription utilisee",
    )
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID de la tache Celery associee",
    )
    status = models.CharField(
        max_length=20,
        choices=TranscriptionJobStatus.choices,
        default=TranscriptionJobStatus.PENDING,
        help_text="Statut actuel du job de transcription",
    )
    raw_result = models.JSONField(
        null=True,
        blank=True,
        help_text="Resultat brut de la transcription (segments JSON)",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Message d'erreur en cas d'echec",
    )
    audio_filename = models.CharField(
        max_length=500,
        blank=True,
        help_text="Nom du fichier audio original",
    )
    processing_time_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Duree de traitement en secondes",
    )
    notification_lue = models.BooleanField(
        default=False,
        help_text="Notification de fin lue par le proprietaire / "
                  "End-of-task notification read by the owner",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"TranscriptionJob #{self.pk} — {self.get_status_display()} ({self.page})"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Job de transcription"
        verbose_name_plural = "Jobs de transcription"


# =============================================================================
# Questionnaire — Questions et reponses liees a une Page
# / Questionnaire — Questions and answers linked to a Page
# =============================================================================


class Question(models.Model):
    """
    Question posee sur une page (texte). L'auteur est identifie par son user FK.
    / Question asked about a page (text). The author is identified by user FK.
    """
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="questions",
        help_text="Page a laquelle cette question se rapporte / Page this question relates to",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="questions",
        help_text="Auteur de la question / Question author",
    )
    texte_question = models.TextField(
        help_text="Texte de la question / Question text",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Question"
        verbose_name_plural = "Questions"

    def __str__(self):
        return f"{self.user.username}: {self.texte_question[:60]}"


class ReponseQuestion(models.Model):
    """
    Reponse a une question — l'auteur est identifie par son user FK.
    / Answer to a question — the author is identified by user FK.
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="reponses",
        help_text="Question a laquelle cette reponse repond / Question this answer replies to",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="reponses_questions",
        help_text="Auteur de la reponse / Answer author",
    )
    texte_reponse = models.TextField(
        help_text="Texte de la reponse / Answer text",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Reponse"
        verbose_name_plural = "Reponses"

    def __str__(self):
        return f"{self.user.username}: {self.texte_reponse[:60]}"


class GroupeUtilisateurs(models.Model):
    """
    Groupe d'utilisateurs cree par un owner pour faciliter le partage de dossiers.
    / User group created by an owner to simplify folder sharing.
    """
    nom = models.CharField(max_length=200, help_text="Nom du groupe / Group name")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="groupes_possedes",
        help_text="Proprietaire du groupe / Group owner",
    )
    membres = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="groupes_membre",
        blank=True, help_text="Membres du groupe / Group members",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Groupe d'utilisateurs"
        verbose_name_plural = "Groupes d'utilisateurs"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class DossierPartage(models.Model):
    """
    Partage d'un dossier avec un utilisateur ou un groupe.
    Au moins un des deux (utilisateur, groupe) doit etre non-null.
    / Folder sharing with a user or a group.
    At least one of (utilisateur, groupe) must be non-null.
    """
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="partages")
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="dossiers_partages",
        help_text="Utilisateur cible du partage (null si partage par groupe)",
    )
    groupe = models.ForeignKey(
        GroupeUtilisateurs, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="partages_dossier",
        help_text="Groupe cible du partage (null si partage direct)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Partage de dossier"
        constraints = [
            # Unicite partage dossier+utilisateur (quand utilisateur non null)
            # / Unique share per folder+user (when user is not null)
            models.UniqueConstraint(
                fields=["dossier", "utilisateur"],
                condition=models.Q(utilisateur__isnull=False),
                name="unique_partage_dossier_utilisateur",
            ),
            # Unicite partage dossier+groupe (quand groupe non null)
            # / Unique share per folder+group (when group is not null)
            models.UniqueConstraint(
                fields=["dossier", "groupe"],
                condition=models.Q(groupe__isnull=False),
                name="unique_partage_dossier_groupe",
            ),
            # Au moins un des deux (utilisateur ou groupe) doit etre renseigne
            # / At least one of (user or group) must be set
            models.CheckConstraint(
                condition=~models.Q(utilisateur__isnull=True, groupe__isnull=True),
                name="partage_dossier_au_moins_un_cible",
            ),
        ]

    def __str__(self):
        if self.utilisateur:
            return f"{self.dossier.name} → {self.utilisateur.username}"
        return f"{self.dossier.name} → groupe:{self.groupe.nom}"


class Invitation(models.Model):
    """
    Invitation par email a rejoindre un dossier ou un groupe.
    Au moins un des deux (dossier, groupe) doit etre non-null.
    / Email invitation to join a folder or a group.
    At least one of (dossier, groupe) must be non-null.
    """
    dossier = models.ForeignKey(
        Dossier, on_delete=models.CASCADE,
        null=True, blank=True, related_name="invitations",
        help_text="Dossier cible de l'invitation (null si invitation groupe)",
    )
    groupe = models.ForeignKey(
        GroupeUtilisateurs, on_delete=models.CASCADE,
        null=True, blank=True, related_name="invitations",
        help_text="Groupe cible de l'invitation (null si invitation dossier)",
    )
    email = models.EmailField(
        help_text="Adresse email du destinataire / Recipient email address",
    )
    invite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="invitations_envoyees",
        help_text="Utilisateur qui a envoye l'invitation / User who sent the invitation",
    )
    token = models.CharField(
        max_length=64, unique=True,
        help_text="Token unique d'acceptation (secrets.token_hex(32)) / Unique acceptance token",
    )
    acceptee = models.BooleanField(
        default=False,
        help_text="True si l'invitation a ete acceptee / True if invitation was accepted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        help_text="Date d'expiration de l'invitation (now + 7 jours) / Invitation expiry date",
    )

    class Meta:
        verbose_name = "Invitation"
        verbose_name_plural = "Invitations"
        ordering = ["-created_at"]
        constraints = [
            # Au moins un des deux (dossier ou groupe) doit etre renseigne
            # / At least one of (dossier or groupe) must be set
            models.CheckConstraint(
                condition=~models.Q(dossier__isnull=True, groupe__isnull=True),
                name="invitation_au_moins_une_cible",
            ),
        ]

    def __str__(self):
        cible = self.dossier.name if self.dossier else f"groupe:{self.groupe.nom}"
        return f"Invitation {self.email} → {cible}"


# =============================================================================
# Tracabilite — historique des editions manuelles et liens de provenance
# / Traceability — manual edit history and provenance links
# =============================================================================


class TypeEdit(models.TextChoices):
    """Type d'edition manuelle sur une Page.
    / Manual edit type on a Page.
    """
    TITRE = "titre", "Titre modifié"
    CONTENU = "contenu", "Contenu modifié"
    BLOC_TRANSCRIPTION = "bloc_transcription", "Bloc de transcription modifié"
    LOCUTEUR = "locuteur", "Locuteur renommé"


class PageEdit(models.Model):
    """
    Historique des editions manuelles sur une Page.
    Chaque modification (titre, contenu, bloc transcription, locuteur)
    cree une entree avec l'etat avant et apres.
    / Manual edit history on a Page.
    Each modification (title, content, transcription block, speaker)
    creates an entry with the before and after state.
    """
    page = models.ForeignKey(
        Page, on_delete=models.CASCADE,
        related_name="edits",
        help_text="Page concernee par l'edition / Page affected by the edit",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="page_edits",
        help_text="Utilisateur ayant fait l'edition / User who made the edit",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    type_edit = models.CharField(
        max_length=30, choices=TypeEdit.choices,
        help_text="Type d'edition / Edit type",
    )
    description = models.CharField(
        max_length=500,
        help_text="Resume humain de l'edition / Human-readable edit summary",
    )
    donnees_avant = models.JSONField(
        default=dict,
        help_text="Etat avant l'edition / State before the edit",
    )
    donnees_apres = models.JSONField(
        default=dict,
        help_text="Etat apres l'edition / State after the edit",
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Edition de page"
        verbose_name_plural = "Editions de pages"

    def __str__(self):
        return f"PageEdit #{self.pk} — {self.get_type_edit_display()} — {self.page}"


class TypeLien(models.TextChoices):
    """Type de lien de provenance entre un passage cible et sa source.
    / Provenance link type between a target passage and its source.
    """
    IDENTIQUE = "identique", "Identique"
    MODIFIE = "modifie", "Modifié"
    NOUVEAU = "nouveau", "Nouveau"
    SUPPRIME = "supprime", "Supprimé"
    # Une synthese ou un wiki CITE une extraction (SPEC-synthese § 4.5).
    # / A synthesis or wiki CITES an extraction.
    CITE = "cite", "Cite"


class EtatDeLaSource(models.TextChoices):
    """
    Ce qu'est devenue la source d'une citation (SPEC-synthese § 4.2).
    / What became of a citation source.
    """
    PRESENTE = "presente", "Présente"
    SUPPRIMEE = "supprimee", "Source supprimée"
    DETACHEE = "detachee", "Ancre détachée"


class EtatDeVerification(models.TextChoices):
    """
    Le verdict du controle de fidelite, PAR PAIRE (affirmation, source) —
    jamais par affirmation : en multi-source, une source peut etre bonne
    et l'autre fausse (SPEC-synthese § 7).
    / Grounding verdict, PER (claim, source) PAIR.
    """
    NON_VERIFIE = "non_verifie", "Non vérifié"
    VERIFIE = "verifie", "Vérifié"
    FAIBLE = "faible", "Faible"
    NON_SOURCE = "non_source", "Non sourcé"
    # Pose par un HUMAIN qui refuse le verdict automatique — jamais
    # ecrase par une re-verification (§ 7.2 : l'etat est contestable).
    # / Set by a HUMAN contesting the automatic verdict; never overwritten.
    CONTESTE = "conteste", "Contesté"
    # L'affirmation reprend fidelement un COMMENTAIRE du debat, pas le
    # texte de l'extraction : provenance legitime, pas « faible »
    # (§ 7.4). / The claim faithfully echoes a debate comment.
    SOURCE_DEBAT = "source_debat", "Sourcé par le débat"


class SourceLink(models.Model):
    """
    Lien de provenance entre un passage dans une page cible et son origine.
    Permet de remonter le fil d'un paragraphe jusqu'au texte source original.
    / Provenance link between a passage in a target page and its origin.
    Allows tracing a paragraph back to the original source text.
    """
    page_cible = models.ForeignKey(
        Page, on_delete=models.CASCADE,
        related_name="source_links_cible",
        help_text="Page contenant le passage cible / Page containing the target passage",
    )
    start_char_cible = models.PositiveIntegerField(
        help_text="Position de debut dans le texte cible / Start position in target text",
    )
    end_char_cible = models.PositiveIntegerField(
        help_text="Position de fin dans le texte cible / End position in target text",
    )
    page_source = models.ForeignKey(
        Page, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="source_links_source",
        help_text="Page source du passage / Source page for the passage",
    )
    start_char_source = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Position de debut dans le texte source / Start position in source text",
    )
    end_char_source = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Position de fin dans le texte source / End position in source text",
    )
    extraction_source = models.ForeignKey(
        "hypostasis_extractor.ExtractedEntity", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="source_links",
        help_text="Extraction a l'origine du passage / Extraction that originated the passage",
    )
    commentaires_source = models.ManyToManyField(
        "hypostasis_extractor.CommentaireExtraction", blank=True,
        related_name="source_links",
        help_text="Commentaires a l'origine du passage / Comments that originated the passage",
    )
    # Ancrage par element (moteur ELEMENT) — SPEC v2 section 2.4.
    # extraction_source repond a "QUELLE extraction a alimente ce passage ?".
    # ancrage_source repond a "DANS QUEL ELEMENT, et a quel endroit exact ?".
    # Les deux cohabitent : le premier donne l'extraction entiere, le second
    # la portion precise dans un element.
    # Les anciens champs start_char_source / end_char_source restent en place
    # et ne sont pas touches (section 9 : les deux moteurs coexistent).
    # / ancrage_source points to the precise portion within one element.
    ancrage_source = models.ForeignKey(
        "hypostasis_extractor.AncrageExtraction",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="liens_de_provenance",
        help_text="La portion d'extraction precise qui a alimente ce passage "
                  "de synthese / The precise extraction portion that fed this passage",
    )

    # --- Champs de la couche synthese (SPEC-synthese § 4.3-4.5, phase B) ---
    # page_cible EST l'article citant (on ne cree pas de champ "article").
    # / page_cible IS the citing article.
    section = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Titre exact de la section citante. Sert aux operations "
                  "de mise a jour (§ 6) et a la navigation.",
    )
    ordre_dans_la_section = models.PositiveSmallIntegerField(
        default=0,
        help_text="Position de la citation dans sa section.",
    )
    etat_de_verification = models.CharField(
        max_length=12, choices=EtatDeVerification.choices,
        default=EtatDeVerification.NON_VERIFIE, db_index=True,
        help_text="Verdict du controle de fidelite, par paire "
                  "(affirmation, source).",
    )
    # § 7.2 : un etat sans provenance est un argument d'autorite
    # automatise — le verdict porte QUI l'a pose (methode + modele +
    # version, ou le nom de l'humain qui conteste) et QUAND.
    # / § 7.2: the verdict carries its judge and date.
    verifie_par = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Qui a pose le verdict : methode + modele + version "
                  "(ex. « verbatim+nli-lot v1 — gpt-x ») ou l'humain "
                  "qui conteste.",
    )
    verifie_le = models.DateTimeField(
        null=True, blank=True,
        help_text="Quand le verdict a ete pose. NULL = jamais verifie.",
    )
    etat_de_la_source = models.CharField(
        max_length=10, choices=EtatDeLaSource.choices,
        default=EtatDeLaSource.PRESENTE, db_index=True,
        help_text="Bascule par signal a la suppression de la source, ou "
                  "par la reconciliation quand l'ancre se detache.",
    )
    type_lien = models.CharField(
        max_length=20, choices=TypeLien.choices,
        help_text="Type de lien de provenance / Provenance link type",
    )
    justification = models.TextField(
        blank=True,
        help_text="Justification du lien / Justification for the link",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lien de provenance"
        verbose_name_plural = "Liens de provenance"

    def __str__(self):
        return f"SourceLink #{self.pk} — {self.get_type_lien_display()} — {self.page_cible}"


# =============================================================================
# ANCRAGE PAR ELEMENT — moteur ELEMENT (SPEC v2, phase A)
# / Element-based anchoring — ELEMENT engine (SPEC v2, phase A)
#
# LOCALISATION : core/models.py
#
# Ces modeles vivent A COTE de l'ancien moteur (ExtractedEntity.start_char /
# end_char), ils ne le remplacent pas. Les deux moteurs coexistent : aucune
# donnee existante n'est convertie, aucun ancien champ n'est retire (SPEC v2
# section 9).
# / These models live NEXT TO the old engine, they do not replace it.
# =============================================================================


def empreinte_du_texte(texte: str) -> str:
    """
    Calcule l'empreinte d'un texte, pour reconnaitre un element inchange.
    / Computes a text fingerprint, to recognize an unchanged element.

    LOCALISATION : core/models.py

    On veut qu'un texte qui n'a change QUE par des espaces ou par la casse
    donne la meme empreinte. Sinon, une re-ingestion croirait que l'element
    est nouveau alors qu'il dit la meme chose.

    ETAPES :
    1. On met tout en minuscules.
    2. On ecrase les suites d'espaces en un seul espace.
    3. On enleve les espaces au debut et a la fin.
    4. On calcule le SHA256 du resultat.

    Utilise par le moteur d'ajout par re-ingestion (SPEC v2 section 5.3),
    qui n'est pas encore ecrit. Le champ ElementDocument.empreinte_contenu
    est rempli des maintenant pour que ce moteur trouve la donnee prete.

    :param texte: Le texte de l'element / The element text
    :return: Une empreinte SHA256 en hexadecimal (64 caracteres)
    """
    # Etape 1 et 2 : minuscules, puis espaces ecrases en un seul
    # / Step 1 and 2: lowercase, then whitespace collapsed to a single space
    texte_en_minuscules = texte.lower()
    texte_aux_espaces_ecrases = re.sub(r"\s+", " ", texte_en_minuscules)

    # Etape 3 : on enleve les espaces au debut et a la fin
    # / Step 3: strip leading and trailing spaces
    texte_normalise = texte_aux_espaces_ecrases.strip()

    # Etape 4 : SHA256 du texte normalise
    # / Step 4: SHA256 of the normalized text
    return hashlib.sha256(texte_normalise.encode("utf-8")).hexdigest()


class EtatElement(models.TextChoices):
    """
    Le regime d'edition d'un element depend de ce qui s'y est attache.
    / Editing regime of an element depends on what is attached to it.

    LOCALISATION : core/models.py

    Cet etat n'est JAMAIS saisi a la main. Il est recalcule par le signal
    recalculer_etat_de_l_element (hypostasis_extractor/signals.py).

    Il n'y a PAS d'etat SCELLE : le scellement a ete abandonne (YAGNI).
    / There is no SCELLE state: sealing was dropped (YAGNI).
    """
    LIBRE = "libre", "Libre — aucune extraction"
    ANALYSE = "analyse", "Analysé — extractions sans commentaire"
    DEBATTU = "debattu", "Débattu — des commentaires sont attachés"


class ElementDocument(models.Model):
    """
    Un element adressable du document : un paragraphe, un titre, un item de
    liste, un tableau, ou un tour de parole dans une transcription.
    / An addressable element of the document.

    LOCALISATION : core/models.py

    C'est l'unite d'ancrage. Avec le moteur ELEMENT, une extraction ne pointe
    plus dans le texte global de la page. Elle pointe vers un ou plusieurs
    ElementDocument, via la table de liaison AncrageExtraction
    (hypostasis_extractor/models.py).

    Pourquoi identifiant_stable et pas le self_ref de Docling ("#/texts/4") ?
    Parce que le self_ref est un numero de position. Si on coupe un element
    en deux, toutes les positions suivantes glissent, et les ancres pointent
    au mauvais endroit. identifiant_stable, lui, ne bouge jamais.
    / identifiant_stable never moves, unlike Docling's positional self_ref.
    """

    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="elements",
        verbose_name="Page qui contient cet element",
        help_text="Page a laquelle cet element appartient / Page this element belongs to",
    )

    identifiant_stable = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Notre identifiant. Ne change jamais, meme apres scission "
                  "ou fusion — c'est ce a quoi toute ancre se refere.",
    )

    reference_docling = models.CharField(
        max_length=64,
        blank=True,
        help_text="Le self_ref d'origine, ex '#/texts/4'. Indicatif seulement, "
                  "jamais utilise comme cle.",
    )

    ordre = models.PositiveIntegerField(
        help_text="Position dans le document, 0, 1, 2, 3... Renumerote "
                  "librement a chaque scission/fusion/ajout : rien d'autre "
                  "ne depend de sa valeur numerique que le tri.",
    )

    label = models.CharField(
        max_length=32,
        help_text="Label Docling : text, section_header, title, list_item, "
                  "table, formula, code...",
    )

    texte = models.TextField(
        help_text="Le texte de cet element. C'est ici qu'on ancre.",
    )

    empreinte_contenu = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA256 du texte normalise (espaces ecrases, minuscules). "
                  "Utilise par le moteur d'ajout par re-ingestion pour "
                  "reconnaitre un element inchange.",
    )

    chemin_de_section = models.JSONField(
        default=list,
        help_text="Titres parents au moment de l'ingestion, ex "
                  "['Introduction', '1) Le calcul des IA']. Instantane, "
                  "pas re-derive automatiquement apres une scission de titre.",
    )

    provenance = models.JSONField(
        default=dict,
        help_text="Provenance physique, selon la source. "
                  "PDF -> {page_no, boites: [{l,t,r,b,coord_origin}, ...]} "
                  "(LISTE de boites : un paragraphe a cheval sur deux pages "
                  "ou deux colonnes produit plusieurs entrees). "
                  "audio -> {start_time, end_time, voice}. "
                  "md/html/txt -> {}",
    )

    etat = models.CharField(
        max_length=16,
        choices=EtatElement.choices,
        default=EtatElement.LIBRE,
        help_text="Recalcule par signal. Ne jamais assigner a la main.",
    )

    masque = models.BooleanField(
        default=False,
        help_text="Element retire du contenu utile sans etre supprime. "
                  "Cas reel : la transcription audio invente un segment "
                  "(bruit, musique, doublon). Reversible, trace dans "
                  "ElementOperation.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page", "ordre"]
        verbose_name = "Element de document"
        verbose_name_plural = "Elements de document"
        constraints = [
            # DEFERRABLE : la contrainte est verifiee a la FIN de la
            # transaction, pas a chaque ligne ecrite.
            #
            # Sans ca, le moteur de structure serait incodable. Scinder un
            # element, c'est creer deux morceaux qui prennent sa place :
            # le premier morceau reclame l'ordre de l'element d'origine,
            # qui existe encore a cet instant. Fusionner ou renumeroter
            # pose le meme probleme — decaler tous les ordres de +1 fait
            # forcement se telescoper deux lignes en cours de route.
            #
            # Differer la verification laisse la transaction passer par des
            # etats temporairement incoherents, mais garantit qu'a la fin,
            # deux elements d'une meme page n'ont jamais le meme ordre.
            # / Deferred: checked at COMMIT, so the structure engine can
            # pass through temporarily inconsistent states.
            models.UniqueConstraint(
                fields=["page", "ordre"],
                name="unicite_ordre_dans_la_page",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]

    def __str__(self):
        debut_du_texte = self.texte[:40]
        return f"ElementDocument #{self.pk} — {self.label} — {debut_du_texte}"


class TypeOperationElement(models.TextChoices):
    """
    Les operations de STRUCTURE possibles sur un element.
    / The possible STRUCTURE operations on an element.

    LOCALISATION : core/models.py

    A ne pas confondre avec TypeEdit, qui couvre les corrections de TEXTE
    (titre, contenu, bloc de transcription, locuteur). Les deux journaux
    sont separes et se lisent ensemble dans l'historique de la page.
    / Not to be confused with TypeEdit, which covers TEXT corrections.
    """
    SCISSION = "scission", "Élément scindé"
    FUSION = "fusion", "Éléments fusionnés"
    MASQUAGE = "masquage", "Élément masqué"
    DEMASQUAGE = "demasquage", "Élément démasqué"


class ElementOperation(models.Model):
    """
    Historique des operations de structure sur les elements.
    / History of structural operations on elements.

    LOCALISATION : core/models.py

    Pourquoi un modele separe de PageEdit ? Parce que TypeEdit ne connait
    que des corrections de texte (TITRE, CONTENU, BLOC_TRANSCRIPTION,
    LOCUTEUR). Il n'a ni SCISSION, ni FUSION, ni MASQUAGE. Detourner
    PageEdit obligerait a ajouter des types qui n'ont rien a y faire.
    / TypeEdit only knows text corrections, not structural operations.

    POURQUOI LE JOURNAL EST RATTACHE A LA PAGE, ET PAS SEULEMENT A L'ELEMENT

    Une scission et une fusion SUPPRIMENT toujours leurs elements sources.
    Si le journal ne tenait qu'a l'element, la premiere operation suivante
    effacerait en cascade l'histoire de la precedente : scinder puis
    refusionner ne laisserait aucune trace de la scission. Le journal
    serait decoratif — et l'invariant « rien ne disparait en silence »
    serait faux la ou il compte le plus.

    Le journal tient donc a la PAGE, qui, elle, ne disparait pas au fil
    des operations. La reference a l'element devient indicative : elle
    passe a NULL quand l'element est supprime, et identifiant_stable_element
    garde de quoi le reconnaitre.
    / The journal hangs off the Page, which survives; the element FK is
    indicative and nulls out.
    """
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="operations_sur_elements",
        help_text="Page ou l'operation a eu lieu / Page where the operation happened",
    )
    element = models.ForeignKey(
        ElementDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operations",
        help_text="Element concerne, s'il existe encore / Element affected, if it still exists",
    )
    identifiant_stable_element = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="L'identifiant de l'element au moment de l'operation. "
                  "Survit a sa suppression / The element's id at operation time",
    )
    donnees = models.JSONField(
        default=dict,
        blank=True,
        help_text="Contexte de l'operation : position de coupe, elements "
                  "sources, etc. Meme role que PageEdit.donnees_avant "
                  "/ Operation context: cut position, source elements...",
    )
    type_operation = models.CharField(
        max_length=16,
        choices=TypeOperationElement.choices,
        help_text="Type d'operation de structure / Structural operation type",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operations_sur_elements",
        help_text="Utilisateur ayant fait l'operation / User who performed the operation",
    )
    justification = models.TextField(
        blank=True,
        help_text="Pourquoi cette operation a ete faite / Why this operation was performed",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Operation sur un element"
        verbose_name_plural = "Operations sur les elements"

    def __str__(self):
        return (
            f"ElementOperation #{self.pk} — "
            f"{self.get_type_operation_display()} — page {self.page_id}"
        )


# ---------------------------------------------------------------------------
# COUCHE CORPUS — base de connaissances, carnet, note
# (SPEC-corpus-base-carnet-note.md v1.1, § 3)
# / CORPUS LAYER — knowledge base, notebook, note
#
# Le modele a trois niveaux de Praxis : une note (Page) vit dans plusieurs
# carnets (Dossier), un carnet vit dans plusieurs bases. Les deux relations
# N-N sont portees par des tables de liaison qui portent ELLES-MEMES les
# categories : le classement d'une note est propre a chaque carnet.
# / Praxis' three-level model: N-N relations carried by link tables which
# themselves carry the categories.
# ---------------------------------------------------------------------------


class BaseDeConnaissances(models.Model):
    """
    Un ensemble de carnets, porte par un collectif.
    / A set of notebooks, held by a collective.

    LOCALISATION : core/models.py

    Exemples reels attendus :
      - un reseau regional de tiers-lieux : ses carnets thematiques de veille
      - un lycee : ses carnets par classe, par projet, par instance

    Ce niveau est FACULTATIF. Un carnet peut exister sans base, directement
    au niveau plateforme — c'est le cas dans Praxis pour les carnets de
    veille collective ouverte. On ne force personne a creer une base pour
    ouvrir un carnet.
    / This level is OPTIONAL: a notebook can live without any base.
    """

    nom = models.CharField(
        max_length=200,
        help_text="Nom de la base de connaissances / Knowledge base name",
    )
    slug = models.SlugField(
        max_length=220,
        unique=True,
        help_text="Identifiant d'URL, ex 'reseau-tiers-lieux-occitanie'.",
    )
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="bases_possedees",
    )
    visibilite = models.CharField(
        max_length=10,
        choices=VisibiliteDossier.choices,   # PRIVE / PARTAGE / PUBLIC, existant
        default=VisibiliteDossier.PRIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Base de connaissances"
        verbose_name_plural = "Bases de connaissances"

    def __str__(self):
        return self.nom


class AppartenancePageDossier(models.Model):
    """
    Rattachement d'une note a un carnet, avec les categories propres A CE
    CARNET, l'epinglage et l'ordre manuel.
    / Membership of a note in a notebook, with categories specific TO THIS
    NOTEBOOK, pinning and manual ordering.

    LOCALISATION : core/models.py

    C'EST LA PIECE CENTRALE DE LA SPEC CORPUS.

    Une meme note rattachee a deux carnets a DEUX lignes ici, avec des
    categories differentes dans chacune. Exemple observe sur Praxis : la
    note "Appel a projets APCHQ 2026" appartient a deux carnets et porte
    des categories distinctes dans chacun.

    La categorie n'est donc PAS un attribut de la note. C'est un attribut
    de la RELATION note-carnet. Si on mettait les categories sur la Page,
    le premier collectif a classer imposerait son vocabulaire a tous les
    suivants — exactement ce qu'on veut eviter.
    / The category is an attribute of the note-notebook RELATION, never
    of the note itself.
    """

    page = models.ForeignKey(
        "Page",
        on_delete=models.CASCADE,
        related_name="appartenances_dossiers",
    )
    dossier = models.ForeignKey(
        "Dossier",
        on_delete=models.CASCADE,
        related_name="appartenances_pages",
    )
    categories = models.ManyToManyField(
        "CategorieDossier",
        blank=True,
        related_name="appartenances",
        help_text="Categories de CE carnet appliquees a CETTE note. "
                  "Validation applicative (phase B) : chaque categorie doit "
                  "venir du meme carnet que cette appartenance.",
    )
    integree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="integrations_de_notes",
    )

    # PAS auto_now_add : la migration de donnees (SPEC-corpus § 4.2) doit
    # pouvoir ecrire page.created_at ici. auto_now_add ecrase toute valeur
    # assignee, y compris via bulk_create et les modeles historiques.
    # / NOT auto_now_add: the data migration must be able to write
    # page.created_at here.
    integree_le = models.DateTimeField(default=timezone.now)

    epinglee = models.BooleanField(
        default=False,
        help_text="Remonte en tete du carnet, avant le tri normal",
    )
    ordre_manuel = models.PositiveIntegerField(
        default=0,
        help_text="Ordre de curation. 0 = pas d'ordre impose, on retombe "
                  "sur le tri chronologique. Sert a donner un ordre "
                  "NARRATIF : les temps d'une deliberation.",
    )

    class Meta:
        ordering = ["dossier", "-epinglee", "ordre_manuel", "-integree_le"]
        verbose_name = "Appartenance note-carnet"
        verbose_name_plural = "Appartenances note-carnet"
        constraints = [
            models.UniqueConstraint(
                fields=["page", "dossier"],
                name="unicite_page_dans_un_dossier",
            ),
        ]

    def __str__(self):
        return f"Page {self.page_id} dans dossier {self.dossier_id}"


class AppartenanceDossierBase(models.Model):
    """
    Rattachement d'un carnet a une base, avec les categories propres A
    CETTE BASE. Meme patron, un cran au-dessus.
    / Membership of a notebook in a knowledge base. Same pattern, one
    level up.

    LOCALISATION : core/models.py
    """

    dossier = models.ForeignKey(
        "Dossier", on_delete=models.CASCADE, related_name="appartenances_bases",
    )
    base = models.ForeignKey(
        "BaseDeConnaissances", on_delete=models.CASCADE,
        related_name="appartenances_dossiers",
    )
    categories = models.ManyToManyField(
        "CategorieBase", blank=True, related_name="appartenances",
    )
    integre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="integrations_de_carnets",
    )
    integre_le = models.DateTimeField(default=timezone.now)
    epingle = models.BooleanField(default=False)
    ordre_manuel = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["base", "-epingle", "ordre_manuel", "-integre_le"]
        verbose_name = "Appartenance carnet-base"
        verbose_name_plural = "Appartenances carnet-base"
        constraints = [
            models.UniqueConstraint(
                fields=["dossier", "base"],
                name="unicite_dossier_dans_une_base",
            ),
        ]

    def __str__(self):
        return f"Dossier {self.dossier_id} dans base {self.base_id}"


class ListeDeCategories(models.Model):
    """
    Un axe de classement dans un carnet ou une base.
    / A classification axis within a notebook or a knowledge base.

    LOCALISATION : core/models.py

    Exemple pour un carnet de veille financement :
      liste "Type"       -> Appel a projets, Subvention, Prix
      liste "Echeance"   -> Ce mois-ci, Ce trimestre, Passe
      liste "Territoire" -> Regional, National, Europeen

    DEPLACER UNE LISTE EST INTERDIT : son contenant (carnet ou base) est
    fixe a la creation. Changer le contenant rendrait incoherentes toutes
    les categorisations deja posees avec ses categories. clean() le refuse ;
    pour deplacer un axe, on en cree un nouveau dans le carnet cible.
    / Moving a list is forbidden: its container is fixed at creation.
    """

    nom = models.CharField(max_length=100)

    # Une liste appartient SOIT a un carnet, SOIT a une base. Jamais aux deux.
    # / A list belongs EITHER to a notebook OR to a base. Never both.
    dossier = models.ForeignKey(
        "Dossier", on_delete=models.CASCADE,
        null=True, blank=True, related_name="listes_de_categories",
    )
    base = models.ForeignKey(
        "BaseDeConnaissances", on_delete=models.CASCADE,
        null=True, blank=True, related_name="listes_de_categories",
    )

    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["dossier", "base", "ordre", "nom"]
        verbose_name = "Liste de categories"
        verbose_name_plural = "Listes de categories"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(dossier__isnull=False, base__isnull=True)
                    | models.Q(dossier__isnull=True, base__isnull=False)
                ),
                name="liste_appartient_a_un_seul_contenant",
            ),
        ]

    def __str__(self):
        return self.nom

    def clean(self):
        """
        Refuse le deplacement d'une liste vers un autre contenant.
        / Refuses moving a list to another container.

        On compare avec l'etat en base : si la liste existe deja et que son
        carnet ou sa base change, on refuse. L'interface n'offre pas cette
        operation ; ce clean() est le filet de securite.
        / Compared against the DB state; the UI does not offer the move.
        """
        if self.pk is None:
            return

        etat_en_base = ListeDeCategories.objects.get(pk=self.pk)
        contenant_change = (
            etat_en_base.dossier_id != self.dossier_id
            or etat_en_base.base_id != self.base_id
        )
        if contenant_change:
            raise ValidationError(
                "Le contenant d'une liste de catégories est fixé à sa "
                "création. Pour déplacer un axe, créez-en un nouveau dans "
                "le carnet cible. / A category list's container is fixed "
                "at creation."
            )


class CategorieDossier(models.Model):
    """
    Une categorie applicable aux notes d'un carnet.
    / A category applicable to the notes of one notebook.

    LOCALISATION : core/models.py

    PAS DE CHAMP dossier ICI (SPEC-corpus § 3.3, correction n°4) : le
    denormaliser pouvait diverger de liste.dossier apres un deplacement de
    liste. Le carnet se lit via self.liste.dossier. Une jointure de plus,
    a l'echelle d'un proto, contre une classe entiere de bugs en moins.
    / No denormalized dossier field: read the notebook via the list.
    """
    liste = models.ForeignKey(
        ListeDeCategories, on_delete=models.CASCADE,
        related_name="categories_de_dossier",
    )
    nom = models.CharField(max_length=100)
    couleur = models.CharField(
        max_length=7, blank=True, default="",
        # Hex strict : ce champ finit dans un style= inline — defense en
        # profondeur avant son ouverture a l'UI (relecture F).
        # / Strict hex: this lands in an inline style= attribute.
        validators=[RegexValidator(
            r"^#[0-9A-Fa-f]{6}$",
            message="Couleur au format #RRGGBB / #RRGGBB hex color",
        )],
        help_text="Hex optionnel, ex '#E69F00'. Vide = palette Wong par defaut.",
    )
    ordre = models.PositiveSmallIntegerField(default=0)

    # Palette de Wong : 8 couleurs distinguables par les daltoniens.
    # Utilisee quand une categorie n'a pas de couleur choisie.
    # / Wong palette: 8 colorblind-safe colors, used as fallback.
    PALETTE_WONG = (
        "#E69F00", "#56B4E9", "#009E73", "#F0E442",
        "#0072B2", "#D55E00", "#CC79A7", "#000000",
    )

    @property
    def couleur_effective(self):
        """
        La couleur choisie, ou une couleur de la palette Wong derivee de
        l'ordre — jamais de champ vide a l'affichage.
        / The chosen color, or a Wong palette color derived from ordre.
        """
        if self.couleur:
            return self.couleur
        return self.PALETTE_WONG[self.ordre % len(self.PALETTE_WONG)]

    @property
    def dossier_id(self):
        """Le carnet de cette categorie, via sa liste. / This category's notebook."""
        return self.liste.dossier_id

    class Meta:
        ordering = ["liste", "ordre", "nom"]
        verbose_name = "Categorie de carnet"
        verbose_name_plural = "Categories de carnet"
        constraints = [
            models.UniqueConstraint(
                fields=["liste", "nom"], name="unicite_nom_dans_la_liste",
            ),
        ]

    def __str__(self):
        return self.nom


class CategorieBase(models.Model):
    """
    Une categorie applicable aux carnets d'une base. Meme patron.
    / A category applicable to the notebooks of one base. Same pattern.

    LOCALISATION : core/models.py
    """
    liste = models.ForeignKey(
        ListeDeCategories, on_delete=models.CASCADE,
        related_name="categories_de_base",
    )
    nom = models.CharField(max_length=100)
    couleur = models.CharField(max_length=7, blank=True, default="")
    ordre = models.PositiveSmallIntegerField(default=0)

    @property
    def base_id(self):
        """La base de cette categorie, via sa liste. / This category's base."""
        return self.liste.base_id

    class Meta:
        ordering = ["liste", "ordre", "nom"]
        verbose_name = "Categorie de base"
        verbose_name_plural = "Categories de base"
        constraints = [
            models.UniqueConstraint(
                fields=["liste", "nom"], name="unicite_nom_dans_la_liste_de_base",
            ),
        ]

    def __str__(self):
        return self.nom


# =============================================================================
# LES DEUX GENRES DE SYNTHESE (SPEC-synthese § 3, phase C)
# Le wiki est VIVANT : son perimetre (des categories) se recalcule.
# La synthese dirigee est un ACTE DATE : son perimetre (des notes) est fige.
# / The two synthesis kinds: living wiki vs dated frozen synthesis.
# =============================================================================


class Wiki(models.Model):
    """
    Un article de synthese VIVANT, sur un sujet, dans un carnet.
    / A living synthesis article, on one subject, in one notebook.

    LOCALISATION : core/models.py

    Il n'a pas de version : il a un ETAT, et un compteur de tours de mise
    a jour. Chaque tour applique des operations de section (§ 6), jamais
    une reecriture. C'est ce qui permet de voir ce qui a change.
    Un wiki ne s'adopte pas, il se suit.
    / No versions: a state and an update-round counter.
    """

    page = models.OneToOneField(
        "Page", on_delete=models.CASCADE, related_name="wiki",
        help_text="La note qui porte l'article. type_de_note = WIKI.",
    )
    # CASCADE assume : un wiki sans carnet n'a pas de sens, son perimetre
    # EST le carnet. La note qui porte l'article, elle, survit (c'est une
    # Page ordinaire). / CASCADE: a wiki without its notebook is
    # meaningless; the article's Page itself survives.
    dossier = models.ForeignKey(
        "Dossier", on_delete=models.CASCADE, related_name="wikis",
        help_text="Le carnet dont il synthetise les notes.",
    )
    sujet = models.TextField(
        help_text="Ce sur quoi porte l'article, en une phrase. C'est une "
                  "CONSIGNE DE REDACTION, pas un filtre — le perimetre est "
                  "defini par categories_du_perimetre (§ 3.1.1).",
    )
    # Le PERIMETRE d'un wiki est defini par des CATEGORIES, exactement
    # comme celui d'une synthese dirigee. Sans ca, c'est le modele qui
    # choisirait ses sources en ecrivant (§ 3.1.1).
    # / Facets define the scope; the subject only guides the writing.
    categories_du_perimetre = models.ManyToManyField(
        "CategorieDossier", blank=True, related_name="wikis",
        help_text="Les categories qui definissent le perimetre. Vide = tout "
                  "le carnet. Les categories d'un meme axe se combinent en "
                  "OU, les axes entre eux en ET (spec corpus § 8.2).",
    )
    tours_de_mise_a_jour = models.PositiveIntegerField(default=1)
    derniere_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wiki"
        verbose_name_plural = "Wikis"

    def __str__(self):
        return f"Wiki « {self.sujet[:60]} » (carnet {self.dossier_id})"


class SyntheseDirigee(models.Model):
    """
    Une synthese FIGEE, produite a une date, sur un perimetre explicite.
    / A frozen synthesis, produced once, on an explicit scope.

    LOCALISATION : core/models.py

    Elle n'a pas de tours : elle a une date de production et un perimetre
    qu'on ne peut plus changer. Si le carnet evolue, on en produit une
    autre — on ne modifie pas celle-ci. C'est la condition pour qu'un
    collectif puisse s'y referer six mois plus tard.
    / No rounds: a production date and an immutable scope.
    """

    page = models.OneToOneField(
        "Page", on_delete=models.CASCADE, related_name="synthese_dirigee",
        help_text="La note qui porte la synthese. type_de_note = SYNTHESE.",
    )
    # SET_NULL et non CASCADE (ecart assume vs spec § 3.2, addendum n°5) :
    # l'acte date et son perimetre fige SURVIVENT a la suppression du
    # carnet — la preuve d'une adoption ne disparait pas avec le
    # rangement. Nullable aussi pour la synthese commandee depuis une
    # note hors carnet (le flux existant l'autorise).
    # / SET_NULL, not CASCADE: the dated act survives notebook deletion.
    dossier = models.ForeignKey(
        "Dossier", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="syntheses_dirigees",
        help_text="Le carnet sur lequel la synthese a ete produite. NULL "
                  "si le carnet a ete supprime depuis, ou si la demande "
                  "venait d'une note hors carnet.",
    )
    produite_le = models.DateTimeField(default=timezone.now)
    produite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="syntheses_produites",
    )
    # Le PERIMETRE est fige a la production : c'est ce qui permet de
    # recalculer « ce qui n'a pas ete repris » (§ 8) des mois apres.
    # / The scope is frozen; it is what makes § 8 reproducible.
    notes_du_perimetre = models.ManyToManyField(
        "Page", related_name="syntheses_qui_la_couvrent",
        help_text="Les notes effectivement dans le perimetre au moment de "
                  "la production. Fige, jamais recalcule.",
    )
    # Les EXTRACTIONS proposees au modele, figees aussi (relecture D,
    # B2) : sans elles, une re-analyse posterieure changerait « ce qui
    # n'a pas ete repris » — l'ensemble § 8 porterait sur des
    # extractions que l'acte date n'a jamais vues.
    # / The extractions offered to the model, frozen too: a later
    # re-analysis must never rewrite the § 8 set.
    extractions_du_perimetre = models.ManyToManyField(
        "hypostasis_extractor.ExtractedEntity", blank=True,
        related_name="syntheses_qui_les_ont_vues",
        help_text="Les extractions effectivement proposees au modele a "
                  "la production. Fige. Vide + flag a False = synthese "
                  "historique (perimetre inconnu, recalcul dynamique).",
    )
    perimetre_d_extractions_fige = models.BooleanField(
        default=False,
        help_text="True des que la production a fige la liste "
                  "d'extractions ci-dessus — meme vide (analyseur sans "
                  "extractions). False = historique d'avant la phase D.",
    )
    axe_de_direction = models.ForeignKey(
        "ListeDeCategories", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="syntheses_dirigees",
        help_text="L'axe qui a dirige la synthese, s'il y en a un.",
    )
    categorie_de_direction = models.ForeignKey(
        "CategorieDossier", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="syntheses_dirigees",
    )

    class Meta:
        verbose_name = "Synthese dirigee"
        verbose_name_plural = "Syntheses dirigees"

    def __str__(self):
        return f"Synthese dirigee du {self.produite_le:%d/%m/%Y} (page {self.page_id})"
