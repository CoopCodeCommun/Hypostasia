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


class Page(models.Model):
    """Représente une page web capturée par l'extension.

    Règles (voir GUIDELINES):
    - `html_original` est immuable après création.
    - `content_hash` = SHA256 de `text_readability`.
    - Les `TextBlock` liés ancrent les passages dans le DOM.
    """

    url = models.URLField(unique=True, help_text="URL canonique de la page analysée")
    title = models.CharField(max_length=500, blank=True, null=True, help_text="Titre optionnel détecté ou saisi")
    html_original = models.TextField(help_text="HTML original complet (immuable après création)")
    html_readability = models.TextField(help_text="HTML simplifié (Readability) pour l'analyse")
    text_readability = models.TextField(help_text="Texte brut extrait de Readability (base de l'analyse)")
    content_hash = models.CharField(max_length=64, blank=True, help_text="SHA256 hex du `text_readability`")  # SHA256 hex digest
    
    status = models.CharField(max_length=20, choices=PageStatus.choices, default=PageStatus.PENDING, help_text="Statut de la dernière analyse")
    error_message = models.TextField(blank=True, null=True, help_text="Message d'erreur éventuel lors de l'analyse")
    
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

    name = models.CharField(max_length=200, help_text="Nom du thème (ex: Énergie, Climat)")
    description = models.TextField(blank=True, help_text="Description optionnelle du thème")

class TextBlock(models.Model):
    """Bloc de texte ancré dans le DOM via un sélecteur CSS et des offsets.

    Sert d’ancrage pour les Arguments et porte les métadonnées de classification
    (hypostase, mode, thèmes). Les offsets sont relatifs au `textContent` du nœud.
    """

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='blocks', help_text="Page à laquelle appartient ce bloc")
    selector = models.CharField(max_length=500, help_text="Sélecteur CSS (querySelector) qui pointe vers le nœud")
    start_offset = models.IntegerField(help_text="Offset de départ dans le `textContent` du nœud")
    end_offset = models.IntegerField(help_text="Offset de fin dans le `textContent` du nœud")
    text = models.TextField(help_text="Texte brut du bloc (extrait côté extension)")
    significant_extract = models.TextField(blank=True, null=True, help_text="Extrait représentatif et concis du bloc")
    hypostases = models.ManyToManyField(HypostasisTag, related_name="text_blocks", blank=True, verbose_name="Hypostases", help_text="Typologies conceptuelles (ex: classification, axiome, théorie…)")
    modes = models.CharField(max_length=20, choices=Modes.choices, default=Modes.IN, verbose_name="Mode de débat", help_text="Statut argumentatif du contenu (ex: discuté, consensuel)")
    themes = models.ManyToManyField(Theme, related_name="text_blocks", help_text="Thèmes associés à ce bloc")

    def __str__(self):
        return f"Bloc sur {self.page} ({self.selector})"


class Reformulation(models.Model):
    origin = models.ForeignKey(TextBlock, on_delete=models.CASCADE, related_name='reformulations')
    text = models.TextField()
    style = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)




class Argument(models.Model):

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='arguments', help_text="Page source de l’argument")
    text_block = models.ForeignKey(
        TextBlock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='arguments',
        help_text="Bloc d’origine si l’argument est ancré sur un passage précis"
    )
    selector = models.CharField(max_length=500, help_text="Sélecteur CSS du passage (doublon de sécurité si `text_block` est nul)")
    start_offset = models.IntegerField(help_text="Offset de départ dans le nœud ciblé (sélecteur)")
    end_offset = models.IntegerField(help_text="Offset de fin dans le nœud ciblé (sélecteur)")

    text_original = models.TextField(help_text="Texte source sur lequel l’argument se base")
    summary = models.TextField(help_text="Résumé de l’argument (généré par IA ou édité)")
    # stance removed as per new architecture (focus on 'modes' in TextBlock)

    user_edited = models.BooleanField(default=False, help_text="Coché si un humain a modifié l’argument")
    # invalidated = models.BooleanField(default=False)  # À introduire si l’invalidation automatique est activée (voir GUIDELINES §7)
    created_at = models.DateTimeField(auto_now_add=True, help_text="Horodatage de création")

    def __str__(self):
        return f"{self.summary[:50]}..."

class ArgumentComment(models.Model):
    """Commentaire utilisateur attaché à un argument."""

    argument = models.ForeignKey(Argument, on_delete=models.CASCADE, related_name='comments', help_text="Argument commenté")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, help_text="Auteur du commentaire")
    comment = models.TextField(help_text="Contenu du commentaire")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Horodatage de création")

    def __str__(self):
        return f"Commentaire de {self.author} sur l’argument {self.argument.id}"


#### ANALYSE AI ####

class Provider(models.TextChoices):
    """Fournisseur du modèle d’IA."""

    MOCK = "mock", "Mock (Simulation)"
    GOOGLE = "google", "Google Gemini"
    OPENAI = "openai", "OpenAI GPT"
    MISTRAL = "mistral", "Mistral AI"
    PERPLEXITY = "perplexity", "Perplexity"


class AIModel(models.Model):

    name = models.CharField(max_length=100, help_text="Nom d'affichage (ex: Gemini Pro Dev)")
    provider = models.CharField(max_length=50, choices=Provider.choices, default=Provider.MOCK, help_text="Fournisseur du modèle")
    api_key = models.CharField(max_length=255, blank=True, help_text="Clé API (laisser vide pour Mock)")
    model_name = models.CharField(max_length=100, blank=True, help_text="Nom technique du modèle (ex: gemini-1.5-pro, gpt-4)")
    temperature = models.FloatField(default=0.7, help_text="Température d'échantillonnage du LLM")
    is_active = models.BooleanField(default=True, help_text="Modèle activé pour sélection")

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

class Prompt(models.Model):
    name = models.CharField(max_length=200, help_text="Nom lisible du prompt composable")
    description = models.TextField(blank=True, help_text="Description / intention du prompt")
    default_model = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, blank=True, related_name="prompts", help_text="Modèle par défaut utilisé pour ce prompt")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Horodatage de création")

    def __str__(self):
        return self.name

class Role(models.TextChoices):
    """Rôle d’un `TextInput` dans la composition d’un prompt."""

    CONTEXT = "context", "Contexte sémantique"
    INSTRUCTION = "instruction", "Instruction"
    FORMAT = "format", "Format de sortie"


class TextInput(models.Model):

    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name="inputs", help_text="Prompt auquel appartient cette brique")
    name = models.CharField(max_length=200, help_text="Nom lisible de la brique")
    role = models.CharField(max_length=50, choices=Role.choices, help_text="Rôle de la brique dans le prompt")
    content = models.TextField(help_text="Contenu texte de la brique (sera concaténé)")
    order = models.PositiveIntegerField(default=0, help_text="Ordre d’assemblage dans le prompt")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.role})"
