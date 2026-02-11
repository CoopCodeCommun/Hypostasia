from rest_framework import serializers


class DossierCreateSerializer(serializers.Serializer):
    """
    Validation pour la creation d'un dossier.
    Validation for creating a folder.
    """
    name = serializers.CharField(
        max_length=200,
        error_messages={
            "required": "Le nom du dossier est obligatoire / Folder name is required",
            "blank": "Le nom du dossier ne peut pas etre vide / Folder name cannot be blank",
        },
    )

    def validate_name(self, value):
        # Nettoyage du nom — on enleve les espaces en debut/fin
        # Clean name — strip leading/trailing whitespace
        name_cleaned = value.strip()
        if not name_cleaned:
            raise serializers.ValidationError(
                "Le nom du dossier ne peut pas etre vide / Folder name cannot be blank"
            )
        return name_cleaned


class PageClasserSerializer(serializers.Serializer):
    """
    Validation pour classer une page dans un dossier.
    Validation for filing a page into a folder.
    """
    dossier_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
    )


class RunAnalyseSerializer(serializers.Serializer):
    """
    Validation pour lancer une analyse via un analyseur syntaxique.
    Validation for launching an analysis via a syntactic analyzer.
    """
    analyseur_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'analyseur est obligatoire / Analyzer ID is required",
        },
    )


class ExtractionSerializer(serializers.Serializer):
    """
    Validation du texte selectionne pour une extraction (manuelle ou IA).
    Validation of selected text for an extraction (manual or AI).
    """
    text = serializers.CharField(
        error_messages={
            "required": "Le texte selectionne est obligatoire / Selected text is required",
            "blank": "Le texte selectionne ne peut pas etre vide / Selected text cannot be blank",
        },
    )
    page_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
    )
