"""
Serializers pour l'application Hypostasis Extractor.
Validation DRF pour les jobs d'extraction et les entites.
"""

import html
import bleach
from rest_framework import serializers
from .models import (
    ExtractionJob, ExtractedEntity, ExtractionExample, JobExampleMapping,
    AnalyseurSyntaxique, PromptPiece, AnalyseurExample, ExampleExtraction, ExtractionAttribute
)


def sanitize_text(value):
    """
    Nettoie le HTML d'un champ texte sans double-encoder les entites.
    bleach.clean() encode & en &amp;, puis Django auto-escape re-encode.
    On unescape apres bleach pour eviter le double encodage.
    / Sanitize HTML from a text field without double-encoding entities.
    """
    if value is None:
        return value
    cleaned = bleach.clean(str(value), tags=[], strip=True)
    return html.unescape(cleaned)


class ExtractedEntitySerializer(serializers.ModelSerializer):
    """
    Serializer pour les entites extraites.
    Inclut les infos de source grounding (start_char, end_char).
    """
    hypostasis_name = serializers.CharField(
        source='hypostasis_tag.name',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = ExtractedEntity
        fields = [
            'id',
            'extraction_class',
            'extraction_text',
            'start_char',
            'end_char',
            'attributes',
            'hypostasis_tag',
            'hypostasis_name',
            'user_validated',
            'user_notes'
        ]


class ExtractionExampleSerializer(serializers.ModelSerializer):
    """
    Serializer pour les exemples few-shot.
    """
    class Meta:
        model = ExtractionExample
        fields = ['id', 'name', 'description', 'example_text', 'example_extractions']


class ExtractionExampleBriefSerializer(serializers.ModelSerializer):
    """
    Version legere pour les listes.
    """
    class Meta:
        model = ExtractionExample
        fields = ['id', 'name']


class ExtractionJobListSerializer(serializers.ModelSerializer):
    """
    Serializer pour la liste des jobs.
    Vue resume sans les resultats complets.
    """
    page_url = serializers.CharField(source='page.url', read_only=True)
    page_title = serializers.CharField(source='page.title', read_only=True)
    model_name = serializers.CharField(source='ai_model.name', read_only=True, allow_null=True)
    
    class Meta:
        model = ExtractionJob
        fields = [
            'id',
            'name',
            'page_url',
            'page_title',
            'model_name',
            'status',
            'entities_count',
            'created_at'
        ]


class ExtractionJobCreateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la creation d'un job.
    Accepte les IDs des exemples a associer.
    """
    example_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="Liste des IDs d'exemples a associer au job"
    )
    
    class Meta:
        model = ExtractionJob
        fields = [
            'id',
            'page',
            'ai_model',
            'name',
            'prompt_description',
            'example_ids'
        ]
    
    def create(self, validated_data):
        # Recupere les IDs des exemples avant de creer le job
        example_ids = validated_data.pop('example_ids', [])
        
        # Cree le job
        job = ExtractionJob.objects.create(**validated_data)
        
        # Associe les exemples
        for index, example_id in enumerate(example_ids):
            try:
                example = ExtractionExample.objects.get(pk=example_id)
                JobExampleMapping.objects.create(
                    job=job,
                    example=example,
                    order=index
                )
            except ExtractionExample.DoesNotExist:
                # On ignore silencieusement les IDs invalides
                pass
        
        return job


class ExtractionJobDetailSerializer(serializers.ModelSerializer):
    """
    Serializer complet pour le detail d'un job.
    Inclut les entites et les exemples associes.
    """
    page_url = serializers.CharField(source='page.url', read_only=True)
    page_title = serializers.CharField(source='page.title', read_only=True)
    model_name = serializers.CharField(source='ai_model.name', read_only=True, allow_null=True)
    entities = ExtractedEntitySerializer(many=True, read_only=True)
    examples = serializers.SerializerMethodField()
    
    class Meta:
        model = ExtractionJob
        fields = [
            'id',
            'name',
            'prompt_description',
            'page',
            'page_url',
            'page_title',
            'ai_model',
            'model_name',
            'status',
            'error_message',
            'raw_result',
            'entities',
            'entities_count',
            'processing_time_seconds',
            'examples',
            'created_at',
            'updated_at'
        ]
    
    def get_examples(self, job):
        """Retourne les exemples associes au job."""
        mappings = JobExampleMapping.objects.filter(job=job).select_related('example')
        return [
            {
                'id': mapping.example.id,
                'name': mapping.example.name,
                'example_text': mapping.example.example_text,
                'example_extractions': mapping.example.example_extractions,
                'order': mapping.order
            }
            for mapping in mappings
        ]


class ExtractionValidationSerializer(serializers.Serializer):
    """
    Serializer pour valider une entite extraite par l'utilisateur.
    """
    user_validated = serializers.BooleanField()
    user_notes = serializers.CharField(required=False, allow_blank=True)
    hypostasis_tag_id = serializers.IntegerField(required=False, allow_null=True)


class RunExtractionSerializer(serializers.Serializer):
    """
    Serializer pour le lancement d'une extraction.
    Valide les parametres avant d'executer LangExtract.
    """
    use_chunking = serializers.BooleanField(
        default=False,
        help_text="Activer le decoupage pour les longs documents"
    )
    max_workers = serializers.IntegerField(
        default=1,
        min_value=1,
        max_value=20,
        help_text="Nombre de workers paralleles (si chunking active)"
    )


# =============================================================================
# Serializers pour les Analyseurs Syntaxiques
# / Serializers for Syntactic Analyzers
# =============================================================================

class AnalyseurSyntaxiqueCreateSerializer(serializers.Serializer):
    """Creation d'un analyseur / Create an analyzer."""
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)


class AnalyseurSyntaxiqueUpdateSerializer(serializers.Serializer):
    """Mise a jour partielle d'un analyseur (auto-save) / Partial update."""
    name = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)


class PromptPieceCreateSerializer(serializers.Serializer):
    """Creation d'une piece de prompt / Create a prompt piece."""
    name = serializers.CharField(max_length=200)
    role = serializers.ChoiceField(choices=PromptPiece.RoleChoices.choices, default="instruction")
    content = serializers.CharField(allow_blank=True, default="")
    order = serializers.IntegerField(default=0)

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_content(self, value):
        return sanitize_text(value)


class PromptPieceUpdateSerializer(serializers.Serializer):
    """Mise a jour partielle d'une piece (auto-save) / Partial update."""
    piece_id = serializers.IntegerField()
    name = serializers.CharField(max_length=200, required=False)
    role = serializers.ChoiceField(choices=PromptPiece.RoleChoices.choices, required=False)
    content = serializers.CharField(required=False, allow_blank=True)
    order = serializers.IntegerField(required=False)

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_content(self, value):
        return sanitize_text(value)


class AnalyseurExampleCreateSerializer(serializers.Serializer):
    """Creation d'un exemple / Create an example."""
    name = serializers.CharField(max_length=200)
    example_text = serializers.CharField(allow_blank=True, default="")
    order = serializers.IntegerField(default=0)

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_example_text(self, value):
        return sanitize_text(value)


class AnalyseurExampleUpdateSerializer(serializers.Serializer):
    """Mise a jour partielle d'un exemple (auto-save) / Partial update."""
    example_id = serializers.IntegerField()
    name = serializers.CharField(max_length=200, required=False)
    example_text = serializers.CharField(required=False, allow_blank=True)
    order = serializers.IntegerField(required=False)

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_example_text(self, value):
        return sanitize_text(value)


class ExampleExtractionCreateSerializer(serializers.Serializer):
    """Creation d'une extraction dans un exemple / Create an extraction."""
    example_id = serializers.IntegerField()
    extraction_class = serializers.CharField(max_length=100, allow_blank=True, default="")
    extraction_text = serializers.CharField(allow_blank=True, default="")
    order = serializers.IntegerField(default=0)

    def validate_extraction_class(self, value):
        return sanitize_text(value)

    def validate_extraction_text(self, value):
        return sanitize_text(value)


class ExampleExtractionUpdateSerializer(serializers.Serializer):
    """Mise a jour partielle d'une extraction (auto-save) / Partial update."""
    extraction_id = serializers.IntegerField()
    extraction_class = serializers.CharField(max_length=100, required=False)
    extraction_text = serializers.CharField(required=False, allow_blank=True)
    order = serializers.IntegerField(required=False)

    def validate_extraction_class(self, value):
        return sanitize_text(value)

    def validate_extraction_text(self, value):
        return sanitize_text(value)


class ExtractionAttributeSerializer(serializers.Serializer):
    """CRUD d'un attribut d'extraction / CRUD for extraction attribute."""
    key = serializers.CharField(max_length=100, allow_blank=True, default="")
    value = serializers.CharField(allow_blank=True, default="")
    order = serializers.IntegerField(default=0)

    def validate_key(self, value):
        return sanitize_text(value)

    def validate_value(self, value):
        return sanitize_text(value)


class ExtractionAttributeUpdateSerializer(serializers.Serializer):
    """Mise a jour d'un attribut / Update an attribute."""
    attribute_id = serializers.IntegerField()
    key = serializers.CharField(max_length=100, required=False)
    value = serializers.CharField(required=False, allow_blank=True)
    order = serializers.IntegerField(required=False)

    def validate_key(self, value):
        return sanitize_text(value)

    def validate_value(self, value):
        return sanitize_text(value)


# =============================================================================
# Serializer pour les tests d'analyseur
# / Serializer for analyzer tests
# =============================================================================

class RunAnalyseurTestSerializer(serializers.Serializer):
    """Valide les parametres pour lancer un test LLM sur un exemple."""
    example_id = serializers.IntegerField()
    ai_model_id = serializers.IntegerField()
