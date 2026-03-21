from django.db import models
from django.conf import settings
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


class Dossier(models.Model):
    """Dossier de classement pour organiser les pages."""

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
    # Description courte du dossier (optionnel, visible dans l'Explorer)
    # / Short folder description (optional, shown in Explorer)
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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


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
        related_name="restitutions",
        help_text="Page originale dont celle-ci est une restitution / Original page this is a restitution of",
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


class Reformulation(models.Model):
    origin = models.ForeignKey(
        TextBlock, on_delete=models.CASCADE, related_name="reformulations"
    )
    text = models.TextField()
    style = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)


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


class DossierSuivi(models.Model):
    """
    Suivi d'un dossier public par un utilisateur.
    Permet d'ajouter un dossier public dans la section "Suivis" de l'arbre.
    / Follow of a public folder by a user.
    Allows adding a public folder in the "Followed" section of the tree.
    """
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="dossiers_suivis",
        help_text="Utilisateur qui suit le dossier / User following the folder",
    )
    dossier = models.ForeignKey(
        Dossier, on_delete=models.CASCADE,
        related_name="suivis",
        help_text="Dossier suivi / Followed folder",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Suivi de dossier"
        verbose_name_plural = "Suivis de dossiers"
        constraints = [
            # Unicite : un utilisateur ne peut suivre un dossier qu'une fois
            # / Uniqueness: a user can follow a folder only once
            models.UniqueConstraint(
                fields=["utilisateur", "dossier"],
                name="unique_suivi_utilisateur_dossier",
            ),
        ]

    def __str__(self):
        return f"{self.utilisateur.username} suit {self.dossier.name}"


# =============================================================================
# Credits prepays — comptes et transactions pour les analyses LLM
# / Prepaid credits — accounts and transactions for LLM analyses
# =============================================================================


class SoldeInsuffisantError(Exception):
    """Erreur levee quand le solde est insuffisant pour un debit.
    / Error raised when balance is insufficient for a debit.
    """
    pass


class TypeTransaction(models.TextChoices):
    """Type de transaction sur un compte de credits.
    / Transaction type on a credit account.
    """
    RECHARGE = "RECHARGE", "Recharge"
    DEBIT_ANALYSE = "DEBIT_ANALYSE", "Debit analyse"
    AJUSTEMENT = "AJUSTEMENT", "Ajustement"
    REMBOURSEMENT = "REMBOURSEMENT", "Remboursement"


class CreditAccount(models.Model):
    """
    Compte de credits prepays (1:1 avec User).
    Le solde represente le montant en euros disponible pour les analyses LLM.
    / Prepaid credit account (1:1 with User).
    Balance represents the amount in euros available for LLM analyses.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="compte_credits",
        help_text="Utilisateur proprietaire du compte / Account owner",
    )
    solde_euros = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Solde actuel en euros / Current balance in euros",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_ou_creer(cls, user):
        """Recupere ou cree le compte de credits pour un utilisateur.
        / Get or create the credit account for a user.
        """
        compte, _cree = cls.objects.get_or_create(user=user)
        return compte

    def debiter(self, montant, extraction_job=None, description=""):
        """
        Debite le compte d'un montant. Leve SoldeInsuffisantError si solde < montant.
        Atomique avec select_for_update pour eviter les debits concurrents.
        / Debit the account. Raises SoldeInsuffisantError if balance < amount.
        Atomic with select_for_update to prevent concurrent debits.
        """
        from django.db import transaction
        from decimal import Decimal

        montant = Decimal(str(montant))
        with transaction.atomic():
            compte_verrouille = CreditAccount.objects.select_for_update().get(pk=self.pk)
            if compte_verrouille.solde_euros < montant:
                raise SoldeInsuffisantError(
                    f"Solde insuffisant : {compte_verrouille.solde_euros} EUR < {montant} EUR"
                )
            compte_verrouille.solde_euros -= montant
            compte_verrouille.save(update_fields=["solde_euros", "updated_at"])

            # Mettre a jour l'instance courante / Update current instance
            self.solde_euros = compte_verrouille.solde_euros

            transaction_credit = CreditTransaction.objects.create(
                compte=compte_verrouille,
                type_transaction=TypeTransaction.DEBIT_ANALYSE,
                montant_euros=-montant,
                solde_apres_euros=compte_verrouille.solde_euros,
                extraction_job=extraction_job,
                description=description,
            )
            return transaction_credit

    def crediter(self, montant, type_transaction="RECHARGE",
                 stripe_payment_intent_id=None, description=""):
        """
        Credite le compte d'un montant. Atomique avec select_for_update.
        / Credit the account. Atomic with select_for_update.
        """
        from django.db import transaction
        from decimal import Decimal

        montant = Decimal(str(montant))
        with transaction.atomic():
            compte_verrouille = CreditAccount.objects.select_for_update().get(pk=self.pk)
            compte_verrouille.solde_euros += montant
            compte_verrouille.save(update_fields=["solde_euros", "updated_at"])

            # Mettre a jour l'instance courante / Update current instance
            self.solde_euros = compte_verrouille.solde_euros

            transaction_credit = CreditTransaction.objects.create(
                compte=compte_verrouille,
                type_transaction=type_transaction,
                montant_euros=montant,
                solde_apres_euros=compte_verrouille.solde_euros,
                stripe_payment_intent_id=stripe_payment_intent_id,
                description=description,
            )
            return transaction_credit

    def __str__(self):
        return f"CreditAccount {self.user.username} — {self.solde_euros} EUR"

    class Meta:
        verbose_name = "Compte de credits"
        verbose_name_plural = "Comptes de credits"


class CreditTransaction(models.Model):
    """
    Transaction sur un compte de credits (recharge, debit, ajustement, remboursement).
    Chaque transaction enregistre le solde apres operation pour tracabilite.
    / Transaction on a credit account (recharge, debit, adjustment, refund).
    Each transaction records the balance after operation for traceability.
    """
    compte = models.ForeignKey(
        CreditAccount, on_delete=models.CASCADE,
        related_name="transactions",
        help_text="Compte de credits associe / Associated credit account",
    )
    type_transaction = models.CharField(
        max_length=20, choices=TypeTransaction.choices,
        help_text="Type de transaction / Transaction type",
    )
    montant_euros = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Montant en euros (positif=credit, negatif=debit) / Amount in euros",
    )
    solde_apres_euros = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Solde apres la transaction / Balance after transaction",
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255, null=True, blank=True, unique=True,
        help_text="ID du PaymentIntent Stripe (idempotence) / Stripe PaymentIntent ID",
    )
    extraction_job = models.ForeignKey(
        "hypostasis_extractor.ExtractionJob", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="transactions_credits",
        help_text="Job d'extraction associe au debit / Associated extraction job",
    )
    description = models.TextField(
        blank=True,
        help_text="Description de la transaction / Transaction description",
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="transactions_credits",
        help_text="Utilisateur a l'origine de la transaction / User who initiated",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_transaction_display()} {self.montant_euros} EUR — {self.compte.user.username}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Transaction de credits"
        verbose_name_plural = "Transactions de credits"


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
