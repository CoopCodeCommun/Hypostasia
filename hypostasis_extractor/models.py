"""
Models pour l'application Hypostasis Extractor.
Integre LangExtract avec les Pages existantes d'Hypostasia.
"""

from django.db import models
from django.conf import settings

# Import des modeles existants depuis core
from core.models import Page, AIModel, HypostasisTag


class ExtractionJobStatus(models.TextChoices):
    """Statut d'un job d'extraction LangExtract."""
    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En cours"
    COMPLETED = "completed", "Termine"
    ERROR = "error", "Erreur"


class ExtractionJob(models.Model):
    """
    Represente une tache d'extraction LangExtract sur une Page.
    Une Page peut avoir plusieurs jobs avec differentes configurations.
    """
    
    # Lien vers la Page existante (on utilise html_readability de Page)
    page = models.ForeignKey(
        Page, 
        on_delete=models.CASCADE, 
        related_name='extraction_jobs',
        help_text="Page source pour l'extraction (utilise html_readability)"
    )
    
    # Configuration du modele LLM
    ai_model = models.ForeignKey(
        AIModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Modele LLM utilise pour l'extraction"
    )
    
    # Description de la tache d'extraction (prompt LangExtract)
    name = models.CharField(max_length=200, help_text="Nom descriptif du job")
    prompt_description = models.TextField(
        help_text="Description de ce qu'on veut extraire (ex: 'Extraire les entites medicales')"
    )
    
    # Statut et suivi
    status = models.CharField(
        max_length=20,
        choices=ExtractionJobStatus.choices,
        default=ExtractionJobStatus.PENDING
    )
    error_message = models.TextField(blank=True, null=True)
    
    # Resultats stockes en JSON (format LangExtract natif)
    raw_result = models.JSONField(
        blank=True, 
        null=True,
        help_text="Resultat brut de LangExtract (JSON)"
    )
    
    # Statistiques
    entities_count = models.PositiveIntegerField(default=0)
    processing_time_seconds = models.FloatField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} sur {self.page.url[:50]}..."


class ExtractedEntity(models.Model):
    """
    Entite extraite par LangExtract, liee a un ExtractionJob.
    Correspond a un objet lx.data.Extraction serialise.
    """
    
    job = models.ForeignKey(
        ExtractionJob,
        on_delete=models.CASCADE,
        related_name='entities'
    )
    
    # Classification de l'entite (ex: "character", "probleme", "axiome")
    extraction_class = models.CharField(
        max_length=100,
        help_text="Classe/categorie de l'entite extraite"
    )
    
    # Texte exact extrait (source grounding)
    extraction_text = models.TextField(
        help_text="Texte exact extrait du document source"
    )
    
    # Position dans le texte (pour le linking/source grounding)
    start_char = models.PositiveIntegerField(
        help_text="Position de debut dans text_readability"
    )
    end_char = models.PositiveIntegerField(
        help_text="Position de fin dans text_readability"
    )
    
    # Attributs additionnels (JSON flexible)
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Attributs additionnels extraits (ex: {emotion: 'wonder'})"
    )
    
    # Optionnel: lien vers une HypostasisTag si mapping possible
    hypostasis_tag = models.ForeignKey(
        HypostasisTag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Tag hypostasia associe (si mapping automatique reussi)"
    )
    
    # Validation utilisateur
    user_validated = models.BooleanField(
        default=False,
        help_text="Validee par un utilisateur humain"
    )
    user_notes = models.TextField(blank=True, help_text="Notes de validation")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['start_char']
    
    def __str__(self):
        return f"[{self.extraction_class}] {self.extraction_text[:50]}..."


class ExtractionExample(models.Model):
    """
    Exemple few-shot pour guider LangExtract.
    Stocke les exemples reutilisables pour differents jobs.
    """
    
    name = models.CharField(max_length=200, help_text="Nom de l'exemple")
    description = models.TextField(blank=True)
    
    # Texte d'exemple
    example_text = models.TextField(
        help_text="Texte source de l'exemple"
    )
    
    # Extraction attendue (JSON au format LangExtract)
    example_extractions = models.JSONField(
        help_text="Liste des extractions attendues [{extraction_class, extraction_text, attributes}]"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class JobExampleMapping(models.Model):
    """
    Table de liaison entre ExtractionJob et ExtractionExample.
    Permet d'associer plusieurs exemples a un job.
    """
    job = models.ForeignKey(ExtractionJob, on_delete=models.CASCADE)
    example = models.ForeignKey(ExtractionExample, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ['job', 'example']


# =============================================================================
# Analyseur Syntaxique — Prompts configurables + Exemples few-shot
# / Syntactic Analyzer — Configurable prompts + Few-shot examples
# =============================================================================

class AnalyseurSyntaxique(models.Model):
    """
    Analyseur syntaxique configurable pour l'extraction LangExtract.
    Compose de morceaux de prompt ordonnes et d'exemples few-shot.
    / Configurable syntactic analyzer for LangExtract extraction.
    Composed of ordered prompt pieces and few-shot examples.
    """
    name = models.CharField(max_length=200, help_text="Nom de l'analyseur")
    description = models.TextField(blank=True, help_text="Description de l'analyseur")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class PromptPiece(models.Model):
    """
    Morceau de prompt ordonne, lie a un AnalyseurSyntaxique.
    Roles possibles : definition, instruction, format, context.
    / Ordered prompt piece, linked to an AnalyseurSyntaxique.
    Possible roles: definition, instruction, format, context.
    """
    class RoleChoices(models.TextChoices):
        DEFINITION = "definition", "Définition"
        INSTRUCTION = "instruction", "Instruction"
        FORMAT = "format", "Format"
        CONTEXT = "context", "Contexte"

    analyseur = models.ForeignKey(
        AnalyseurSyntaxique,
        on_delete=models.CASCADE,
        related_name='pieces'
    )
    name = models.CharField(max_length=200, help_text="Nom du morceau de prompt")
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.INSTRUCTION
    )
    content = models.TextField(help_text="Contenu du morceau de prompt")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"[{self.role}] {self.name}"


class AnalyseurExample(models.Model):
    """
    Exemple few-shot lie a un AnalyseurSyntaxique.
    Contient un texte source et des extractions typees.
    / Few-shot example linked to an AnalyseurSyntaxique.
    Contains a source text and typed extractions.
    """
    analyseur = models.ForeignKey(
        AnalyseurSyntaxique,
        on_delete=models.CASCADE,
        related_name='examples'
    )
    name = models.CharField(max_length=200, help_text="Nom de l'exemple")
    example_text = models.TextField(help_text="Texte source de l'exemple")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class ExampleExtraction(models.Model):
    """
    Extraction attendue dans un exemple few-shot.
    Chaque extraction a une classe et un texte, plus des attributs.
    / Expected extraction in a few-shot example.
    Each extraction has a class and text, plus attributes.
    """
    example = models.ForeignKey(
        AnalyseurExample,
        on_delete=models.CASCADE,
        related_name='extractions'
    )
    extraction_class = models.CharField(
        max_length=100,
        help_text="Classe/categorie de l'extraction attendue"
    )
    extraction_text = models.TextField(
        help_text="Texte exact attendu pour cette extraction"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"[{self.extraction_class}] {self.extraction_text[:50]}"


class ExtractionAttribute(models.Model):
    """
    Attribut cle-valeur d'une ExampleExtraction.
    Pas de JSONField — tout est modele propre avec FK.
    / Key-value attribute of an ExampleExtraction.
    No JSONField — everything is a proper model with FK.
    """
    extraction = models.ForeignKey(
        ExampleExtraction,
        on_delete=models.CASCADE,
        related_name='attributes'
    )
    key = models.CharField(max_length=100, help_text="Nom de l'attribut")
    value = models.TextField(help_text="Valeur de l'attribut")
    order = models.PositiveIntegerField(default=0, help_text="Ordre d'affichage / Display order")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.key}: {self.value[:50]}"


# =============================================================================
# Test & Benchmark LLM — Resultats de test sur les exemples
# / LLM Test & Benchmark — Test results on examples
# =============================================================================

class AnalyseurTestRun(models.Model):
    """
    Resultat d'un test LangExtract lance sur un exemple d'analyseur.
    Stocke le snapshot du prompt, le modele utilise, et les extractions obtenues.
    / Result of a LangExtract test run on an analyzer example.
    Stores prompt snapshot, model used, and obtained extractions.
    """
    analyseur = models.ForeignKey(
        AnalyseurSyntaxique,
        on_delete=models.CASCADE,
        related_name='test_runs'
    )
    example = models.ForeignKey(
        AnalyseurExample,
        on_delete=models.CASCADE,
        related_name='test_runs'
    )
    ai_model = models.ForeignKey(
        AIModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Modele LLM utilise pour ce test"
    )
    ai_model_display_name = models.CharField(
        max_length=200,
        help_text="Nom du modele fige au moment du test / Model name frozen at test time"
    )
    prompt_snapshot = models.TextField(
        help_text="Prompt complet concatene au moment du test / Full prompt at test time"
    )
    status = models.CharField(
        max_length=20,
        choices=ExtractionJobStatus.choices,
        default=ExtractionJobStatus.PENDING
    )
    error_message = models.TextField(blank=True, null=True)
    raw_result = models.JSONField(blank=True, null=True)
    processing_time_seconds = models.FloatField(blank=True, null=True)
    extractions_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Test {self.ai_model_display_name} sur {self.example.name}"


class TestRunExtraction(models.Model):
    """
    Extraction obtenue lors d'un test run.
    Meme structure qu'ExampleExtraction mais avec attributs en JSONField.
    / Extraction obtained during a test run.
    Same structure as ExampleExtraction but with attributes as JSONField.
    """
    test_run = models.ForeignKey(
        AnalyseurTestRun,
        on_delete=models.CASCADE,
        related_name='extractions'
    )
    extraction_class = models.CharField(max_length=200)
    extraction_text = models.TextField()
    start_pos = models.IntegerField(default=0)
    end_pos = models.IntegerField(default=0)
    attributes = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"[{self.extraction_class}] {self.extraction_text[:50]}"
