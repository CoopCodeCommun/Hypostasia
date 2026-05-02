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
    
    # Flag de reformulation : distingue les jobs de reformulation des jobs d'analyse
    # / Reformulation flag: distinguishes reformulation jobs from analysis jobs
    est_reformulation = models.BooleanField(
        default=False,
        help_text="True si ce job est une reformulation (pas une extraction classique)",
    )

    # Statistiques
    entities_count = models.PositiveIntegerField(default=0)
    processing_time_seconds = models.FloatField(blank=True, null=True)

    # Tokens reels et cout reel (renseignes apres completion par le LLM)
    # / Real tokens and real cost (filled after LLM completion)
    tokens_input_reels = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Nombre de tokens d'entree reels / Real input token count",
    )
    tokens_output_reels = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Nombre de tokens de sortie reels / Real output token count",
    )
    cout_reel_euros = models.FloatField(
        null=True, blank=True,
        help_text="Cout reel en euros / Real cost in euros",
    )

    # Lien vers la version de l'analyseur utilisee pour ce job
    # / Link to the analyzer version used for this job
    analyseur_version = models.ForeignKey(
        'AnalyseurVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extraction_jobs',
        help_text="Version de l'analyseur au moment de l'extraction / Analyzer version at extraction time",
    )

    notification_lue = models.BooleanField(
        default=False,
        help_text="Notification de fin lue par le proprietaire / "
                  "End-of-task notification read by the owner",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        url_page = (self.page.url or "")[:50] if self.page else "page supprimée"
        return f"{self.name} sur {url_page}..."


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
        blank=True,
        default="",
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
    
    # Reformulation : texte reformule par un analyseur de type "reformuler"
    # / Reformulation: text reformulated by a "reformuler" type analyzer
    texte_reformule = models.TextField(
        blank=True,
        default="",
        help_text="Texte reformule par un analyseur / Reformulated text by an analyzer",
    )
    reformule_par = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Nom de l'analyseur qui a reformule / Name of the reformulating analyzer",
    )
    reformulation_en_cours = models.BooleanField(
        default=False,
        help_text="True si une reformulation est en cours / True if reformulation is in progress",
    )
    reformulation_lancee_a = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp du lancement de la reformulation (pour timeout) / Reformulation start timestamp (for timeout)",
    )
    reformulation_erreur = models.TextField(
        blank=True,
        default="",
        help_text="Message d'erreur de la derniere reformulation / Last reformulation error message",
    )

    # Restitution : lie cette extraction a une version de page creee par restitution du debat
    # / Restitution: links this extraction to a page version created by debate restitution
    restitution_page = models.ForeignKey(
        "core.Page",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restitutions_source",
        help_text="Page version creee par restitution de ce debat / Page version created by restituting this debate",
    )
    restitution_texte = models.TextField(
        blank=True,
        default="",
        help_text="Texte de la restitution du debat / Debate restitution text",
    )
    restitution_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de la restitution / Restitution date",
    )

    # Restitution IA : generation automatique du texte de restitution via LLM
    # / AI Restitution: automatic generation of restitution text via LLM
    restitution_ia_en_cours = models.BooleanField(
        default=False,
        help_text="True si une restitution IA est en cours / True if AI restitution is in progress",
    )
    restitution_ia_lancee_a = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp du lancement de la restitution IA (pour timeout) / AI restitution start timestamp (for timeout)",
    )
    restitution_ia_erreur = models.TextField(
        blank=True,
        default="",
        help_text="Message d'erreur de la derniere restitution IA / Last AI restitution error message",
    )
    texte_restitution_ia = models.TextField(
        blank=True,
        default="",
        help_text="Texte de restitution genere par l'IA / AI-generated restitution text",
    )

    # Validation utilisateur
    user_validated = models.BooleanField(
        default=False,
        help_text="Validee par un utilisateur humain"
    )
    user_notes = models.TextField(blank=True, help_text="Notes de validation")

    # Auteur de l'extraction (null pour les extractions legacy/IA)
    # / Extraction author (null for legacy/AI extractions)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extractions_creees",
        help_text="Utilisateur ayant cree cette extraction manuellement / User who manually created this extraction",
    )

    # Statut du debat sur cette extraction
    # / Debate status for this extraction
    STATUT_DEBAT_CHOICES = [
        ("nouveau", "Nouveau"),
        ("consensuel", "Consensuel"),
        ("discutable", "Discutable"),
        ("discute", "Discuté"),
        ("controverse", "Controversé"),
        ("non_pertinent", "Non pertinent"),
    ]

    statut_debat = models.CharField(
        max_length=20,
        choices=STATUT_DEBAT_CHOICES,
        default="nouveau",
    )

    # Extraction masquee par curation
    # / Extraction hidden by curation
    masquee = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    # Date de derniere modification (changement de statut, etc.) — PHASE-20
    # / Last modification date (status change, etc.) — PHASE-20
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_char']

    def save(self, *args, **kwargs):
        # Synchronise masquee avec statut_debat : non_pertinent ↔ masquee=True
        # / Sync masquee with statut_debat: non_pertinent ↔ masquee=True
        self.masquee = (self.statut_debat == "non_pertinent")
        super().save(*args, **kwargs)

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
    Le champ 'type_analyseur' determine le role de l'analyseur dans l'interface.
    / Configurable syntactic analyzer for LangExtract extraction.
    Composed of ordered prompt pieces and few-shot examples.
    The 'type_analyseur' field determines the analyzer's role in the UI.
    """

    # Types d'analyseur disponibles
    # / Available analyzer types
    class TypeAnalyseur(models.TextChoices):
        ANALYSER = "analyser", "Analyser"
        REFORMULER = "reformuler", "Reformuler"
        RESTITUER = "restituer", "Restituer"
        SYNTHETISER = "synthetiser", "Synthétiser"

    name = models.CharField(max_length=200, help_text="Nom de l'analyseur")
    description = models.TextField(blank=True, help_text="Description de l'analyseur")
    is_active = models.BooleanField(default=True)

    # Type d'analyseur : determine les fonctionnalites disponibles dans l'interface
    # / Analyzer type: determines which features are available in the UI
    type_analyseur = models.CharField(
        max_length=20,
        choices=TypeAnalyseur.choices,
        default=TypeAnalyseur.ANALYSER,
        help_text="Type d'analyseur : analyser, reformuler ou restituer",
    )

    # Options d'injection de contexte dans le prompt avant envoi au LLM
    # / Context injection options in the prompt before sending to LLM
    inclure_extractions = models.BooleanField(
        default=False,
        help_text="Injecter les extractions dans le contexte du prompt / Inject extractions into prompt context",
    )
    inclure_texte_original = models.BooleanField(
        default=False,
        help_text="Injecter le texte original dans le contexte du prompt / Inject original text into prompt context",
    )

    # Marqueur "par defaut" : un seul analyseur par type peut l'etre.
    # Cocher ici decoche automatiquement les autres analyseurs du meme type au save.
    # / "Default" marker: only one analyzer per type can have it.
    # / Checking here automatically unchecks other analyzers of the same type at save.
    est_par_defaut = models.BooleanField(
        default=False,
        help_text=(
            "Marquer cet analyseur comme defaut pour son type. "
            "Cocher ici decoche automatiquement les autres analyseurs du meme type."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Si on coche est_par_defaut, decocher les autres analyseurs du meme type
        # / If we check est_par_defaut, uncheck other analyzers of the same type
        if self.est_par_defaut:
            AnalyseurSyntaxique.objects.filter(
                type_analyseur=self.type_analyseur,
                est_par_defaut=True,
            ).exclude(pk=self.pk).update(est_par_defaut=False)
        super().save(*args, **kwargs)


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


class CommentaireExtraction(models.Model):
    """
    Commentaire sur une extraction — mode debat avec authentification.
    L'auteur est identifie par son user FK.
    / Comment on an extraction — debate mode with authentication.
    The author is identified by user FK.
    """
    entity = models.ForeignKey(
        ExtractedEntity,
        on_delete=models.CASCADE,
        related_name='commentaires',
        help_text="Entite commentee / Commented entity",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="commentaires_extraction",
        help_text="Auteur du commentaire / Comment author",
    )
    commentaire = models.TextField(
        help_text="Texte du commentaire / Comment text",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username}: {self.commentaire[:50]}"


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


class TestRunExtractionAnnotation(models.TextChoices):
    """Annotation humaine sur une extraction obtenue / Human annotation on an obtained extraction."""
    VALIDATED = "validated", "Validee (ajoutee aux attendus)"
    REJECTED = "rejected", "Inappropriee"


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

    # Annotation humaine / Human annotation
    human_annotation = models.CharField(
        max_length=20,
        choices=TestRunExtractionAnnotation.choices,
        blank=True,
        null=True,
        help_text="Annotation humaine : validee ou inappropriee / Human annotation: validated or rejected"
    )
    annotation_note = models.TextField(
        blank=True,
        default="",
        help_text="Note humaine optionnelle / Optional human note"
    )
    promoted_to_extraction = models.ForeignKey(
        'ExampleExtraction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promoted_from',
        help_text="ExampleExtraction creee si validee / ExampleExtraction created if validated"
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"[{self.extraction_class}] {self.extraction_text[:50]}"


# =============================================================================
# Historique des versions d'analyseur
# / Analyzer version history
# =============================================================================

class AnalyseurVersion(models.Model):
    """
    Snapshot historique d'un analyseur (pieces + exemples + extractions + attributs).
    Cree automatiquement lors de mutations significatives (add/delete piece, example, etc.).
    / Historical snapshot of an analyzer (pieces + examples + extractions + attributes).
    Created automatically on significant mutations (add/delete piece, example, etc.).
    """
    analyseur = models.ForeignKey(
        AnalyseurSyntaxique,
        on_delete=models.CASCADE,
        related_name='versions',
    )
    version_number = models.PositiveIntegerField(
        help_text="Numero de version auto-incremente / Auto-incremented version number",
    )
    snapshot = models.JSONField(
        help_text="Snapshot JSON complet (pieces, exemples, extractions, attributs) / Full JSON snapshot",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analyseur_versions',
        help_text="Utilisateur ayant effectue la modification / User who made the modification",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    description_modification = models.CharField(
        max_length=500,
        blank=True,
        help_text="Description de la modification / Modification description",
    )

    class Meta:
        ordering = ['-version_number']
        unique_together = ['analyseur', 'version_number']

    def __str__(self):
        return f"{self.analyseur.name} v{self.version_number}"
