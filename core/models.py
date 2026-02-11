from django.db import models
from django.conf import settings

# Create your models here.


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


class Dossier(models.Model):
    """Dossier de classement pour organiser les pages."""

    name = models.CharField(max_length=200, help_text="Nom du dossier")
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

    dossier = models.ForeignKey(
        "Dossier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pages",
        help_text="Dossier de classement (optionnel)",
    )
    url = models.URLField(unique=True, help_text="URL canonique de la page analysée")
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

    def __str__(self):
        return self.title if self.title else self.url

    @property
    def domain(self):
        from urllib.parse import urlparse

        try:
            return urlparse(self.url).netloc
        except:
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
    """Fournisseur du modèle d'IA."""

    MOCK = "mock", "Mock (Simulation)"
    GOOGLE = "google", "Google Gemini"
    OPENAI = "openai", "OpenAI GPT"
    MISTRAL = "mistral", "Mistral AI"
    PERPLEXITY = "perplexity", "Perplexity"
    ANTHROPIC = "anthropic", "Anthropic Claude"
    MOONSHOT = "moonshot", "Moonshot AI (Kimi)"


class AIModelChoices(models.TextChoices):
    """
    Liste unifiée des modèles AI principaux avec leur provider intégré.
    / Unified list of main AI models with integrated provider.

    Format: PROVIDER_MODEL_NAME = "technical_name", "Display Name (Provider)"
    Permet de choisir un seul champ qui détermine automatiquement le provider.
    / Allows selecting a single field that automatically determines the provider.
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
    GOOGLE_GEMINI_1_0_PRO = "gemini-1.0-pro", "Gemini 1.0 Pro (Google)"

    # OpenAI / GPT (Nouvelle génération GPT-5.x + GPT-4.1)
    OPENAI_GPT_5_2 = "gpt-5.2", "GPT-5.2 (OpenAI)"
    OPENAI_GPT_5_MINI = "gpt-5-mini", "GPT-5 Mini (OpenAI)"
    OPENAI_GPT_5_NANO = "gpt-5-nano", "GPT-5 Nano (OpenAI)"
    OPENAI_GPT_4_1 = "gpt-4.1", "GPT-4.1 (OpenAI)"
    OPENAI_GPT_4_1_MINI = "gpt-4.1-mini", "GPT-4.1 Mini (OpenAI)"
    OPENAI_GPT_4_1_NANO = "gpt-4.1-nano", "GPT-4.1 Nano (OpenAI)"
    OPENAI_GPT_4O = "gpt-4o", "GPT-4o (OpenAI)"
    OPENAI_GPT_4O_MINI = "gpt-4o-mini", "GPT-4o Mini (OpenAI)"
    OPENAI_GPT_4_TURBO = "gpt-4-turbo", "GPT-4 Turbo (OpenAI)"
    OPENAI_GPT_4 = "gpt-4", "GPT-4 (OpenAI)"
    OPENAI_GPT_3_5_TURBO = "gpt-3.5-turbo", "GPT-3.5 Turbo (OpenAI)"

    # Mistral AI
    MISTRAL_LARGE = "mistral-large-latest", "Mistral Large (Mistral)"
    MISTRAL_MEDIUM = "mistral-medium-latest", "Mistral Medium (Mistral)"
    MISTRAL_SMALL = "mistral-small-latest", "Mistral Small (Mistral)"
    MISTRAL_7B = "open-mistral-7b", "Mistral 7B (Mistral)"
    MISTRAL_8X7B = "open-mixtral-8x7b", "Mixtral 8x7B (Mistral)"
    MISTRAL_8X22B = "open-mixtral-8x22b", "Mixtral 8x22B (Mistral)"

    # Perplexity
    PERPLEXITY_SONAR = "sonar", "Sonar (Perplexity)"
    PERPLEXITY_SONAR_PRO = "sonar-pro", "Sonar Pro (Perplexity)"
    PERPLEXITY_LLAMA_3_1 = (
        "llama-3.1-sonar-large-128k-online",
        "Llama 3.1 Sonar Large (Perplexity)",
    )

    # Anthropic / Claude (Nouvelle génération 4.x + Legacy 3.x)
    ANTHROPIC_CLAUDE_OPUS_4_6 = "claude-opus-4-6", "Claude Opus 4.6 (Anthropic)"
    ANTHROPIC_CLAUDE_SONNET_4_5 = "claude-sonnet-4-5", "Claude Sonnet 4.5 (Anthropic)"
    ANTHROPIC_CLAUDE_HAIKU_4_5 = "claude-haiku-4-5", "Claude Haiku 4.5 (Anthropic)"
    # Legacy models (conservés pour compatibilité)
    ANTHROPIC_CLAUDE_3_5_SONNET = (
        "claude-3-5-sonnet-20241022",
        "Claude 3.5 Sonnet Legacy (Anthropic)",
    )
    ANTHROPIC_CLAUDE_3_OPUS = (
        "claude-3-opus-20240229",
        "Claude 3 Opus Legacy (Anthropic)",
    )
    ANTHROPIC_CLAUDE_3_SONNET = (
        "claude-3-sonnet-20240229",
        "Claude 3 Sonnet Legacy (Anthropic)",
    )
    ANTHROPIC_CLAUDE_3_HAIKU = (
        "claude-3-haiku-20240307",
        "Claude 3 Haiku Legacy (Anthropic)",
    )

    # Moonshot AI / Kimi
    MOONSHOT_KIMI_K2_5 = "kimi-k2.5", "Kimi K2.5 (Moonshot AI)"
    MOONSHOT_KIMI_K1_5 = "kimi-k1.5", "Kimi K1.5 (Moonshot AI)"
    MOONSHOT_KIMI_K2 = "kimi-k2", "Kimi K2 (Moonshot AI)"

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

    api_key = models.CharField(
        max_length=255, blank=True, help_text="Clé API (laisser vide pour Mock)"
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
            # Les prefixes des valeurs identifient le provider :
            #   gemini-* → Google, gpt-* → OpenAI, mistral-*/open-mistral-*/open-mixtral-* → Mistral,
            #   sonar*/llama-* → Perplexity, claude-* → Anthropic, kimi-* → Moonshot, mock → Mock
            # / Infer provider from model_choice VALUE (e.g. "gemini-2.5-flash")
            choice_value = self.model_choice.lower()

            # Mapping des prefixes de valeur vers les providers
            # Ordre important : les prefixes les plus specifiques d'abord
            # / Mapping of value prefixes to providers
            # Order matters: most specific prefixes first
            prefix_to_provider = [
                ("gemini-", Provider.GOOGLE),
                ("gpt-", Provider.OPENAI),
                ("open-mistral-", Provider.MISTRAL),
                ("open-mixtral-", Provider.MISTRAL),
                ("mistral-", Provider.MISTRAL),
                ("sonar", Provider.PERPLEXITY),
                ("llama-", Provider.PERPLEXITY),
                ("claude-", Provider.ANTHROPIC),
                ("kimi-", Provider.MOONSHOT),
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
