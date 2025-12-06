from django.db import models
from django.conf import settings

# Create your models here.

class Page(models.Model):
    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("processing", "En cours d'analyse"),
        ("completed", "Terminé"),
        ("error", "Erreur"),
    ]

    url = models.URLField(unique=True)
    title = models.CharField(max_length=500, blank=True, null=True)
    html_original = models.TextField()
    html_readability = models.TextField()
    text_readability = models.TextField()
    content_hash = models.CharField(max_length=64, blank=True)  # SHA256 hex digest
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, null=True)
    
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
        """Extracts the first image src from html_readability."""
        import re
        if not self.html_readability:
            return None
        match = re.search(r'<img[^>]+src="([^">]+)"', self.html_readability)
        if match:
            return match.group(1)
        return None

class TextBlock(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='blocks')
    selector = models.CharField(max_length=500)
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()
    text = models.TextField()

    def __str__(self):
        return f"Block on {self.page} ({self.selector})"

class Argument(models.Model):
    STANCE_CHOICES = [
        ("pour", "Pour"),
        ("contre", "Contre"),
        ("neutre", "Neutre"),
    ]

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='arguments')
    text_block = models.ForeignKey(TextBlock, on_delete=models.SET_NULL, null=True, blank=True, related_name='arguments')
    selector = models.CharField(max_length=500)
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()

    text_original = models.TextField()
    summary = models.TextField()
    stance = models.CharField(max_length=10, choices=STANCE_CHOICES)

    user_edited = models.BooleanField(default=False)
    # invalidated = models.BooleanField(default=False) # To be implemented later based on specs if needed immediately, but sticking to basic models first from GUIDELINES 1.3
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.stance.capitalize()}: {self.summary[:50]}..."

class ArgumentComment(models.Model):
    argument = models.ForeignKey(Argument, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author} on Arg {self.argument.id}"

class AIModel(models.Model):
    PROVIDER_CHOICES = [
        ("mock", "Mock (Simulation)"),
        ("google", "Google Gemini"),
        ("openai", "OpenAI GPT"),
        ("mistral", "Mistral AI"),
        ("perplexity", "Perplexity"),
    ]

    name = models.CharField(max_length=100, help_text="Nom d'affichage (ex: Gemini Pro Dev)")
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default="mock")
    api_key = models.CharField(max_length=255, blank=True, help_text="Clé API (laisser vide pour Mock)")
    model_name = models.CharField(max_length=100, blank=True, help_text="Nom technique du modèle (ex: gemini-1.5-pro, gpt-4)")
    temperature = models.FloatField(default=0.7)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

class Prompt(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    default_model = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, blank=True, related_name="prompts", help_text="Modèle par défaut pour ce prompt")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class TextInput(models.Model):
    ROLE_CHOICES = [
        ("context", "Contexte sémantique"),
        ("instruction", "Instruction"),
        ("format", "Format de sortie")
    ]

    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name="inputs")
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.role})"
