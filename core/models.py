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
    Fournisseur du modèle d'IA pour LangExtract.
    Seuls Google Gemini et OpenAI GPT sont supportés par LangExtract.
    / AI model provider for LangExtract.
    Only Google Gemini and OpenAI GPT are supported by LangExtract.
    """

    MOCK = "mock", "Mock (Simulation)"
    GOOGLE = "google", "Google Gemini"
    OPENAI = "openai", "OpenAI GPT"


class AIModelChoices(models.TextChoices):
    """
    Liste des modèles AI supportés par LangExtract.
    Seuls Google Gemini et OpenAI GPT sont supportés.
    / List of AI models supported by LangExtract.
    Only Google Gemini and OpenAI GPT are supported.
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
            # / Infer provider from model_choice VALUE (e.g. "gemini-2.5-flash")
            choice_value = self.model_choice.lower()

            # Mapping des prefixes de valeur vers les providers
            # / Mapping of value prefixes to providers
            prefix_to_provider = [
                ("gemini-", Provider.GOOGLE),
                ("gpt-", Provider.OPENAI),
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
    TARIFS_PAR_MILLION_TOKENS = {
        # Google Gemini — prix input/output par million de tokens
        # / Google Gemini — input/output price per million tokens
        "gemini-2.5-pro": (1.25, 10.00),
        "gemini-2.5-flash": (0.15, 0.60),
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
        # Mock — gratuit / Mock — free
        "mock": (0.0, 0.0),
    }

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

    api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Cle API Mistral (laisser vide pour Mock)",
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
    Question posee sur une page (texte). Pas d'authentification requise,
    l'auteur est identifie par son prenom (meme pattern que CommentaireExtraction).
    / Question asked about a page (text). No authentication required,
    the author is identified by first name (same pattern as CommentaireExtraction).
    """
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="questions",
        help_text="Page a laquelle cette question se rapporte / Page this question relates to",
    )
    prenom = models.CharField(
        max_length=100,
        help_text="Prenom de l'auteur de la question / Author first name",
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
        return f"{self.prenom}: {self.texte_question[:60]}"


class ReponseQuestion(models.Model):
    """
    Reponse a une question — meme pattern sans authentification (prenom).
    / Answer to a question — same pattern without authentication (first name).
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="reponses",
        help_text="Question a laquelle cette reponse repond / Question this answer replies to",
    )
    prenom = models.CharField(
        max_length=100,
        help_text="Prenom de l'auteur de la reponse / Author first name",
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
        return f"{self.prenom}: {self.texte_reponse[:60]}"
