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


class SelectModelSerializer(serializers.Serializer):
    """
    Validation pour la selection du modele IA actif.
    Validation for selecting the active AI model.
    """
    model_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID du modele est obligatoire / Model ID is required",
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


class ExtractionManuelleSerializer(serializers.Serializer):
    """
    Validation pour la creation d'une extraction manuelle.
    Validation for creating a manual extraction.
    """
    text = serializers.CharField(
        error_messages={
            "required": "Le texte est obligatoire / Text is required",
            "blank": "Le texte ne peut pas etre vide / Text cannot be blank",
        },
    )
    page_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de la page est obligatoire / Page ID is required",
        },
    )
    start_char = serializers.IntegerField()
    end_char = serializers.IntegerField()
    # Les attributs (attr_key_N / attr_val_N) sont lus dynamiquement dans la view
    # / Attributes (attr_key_N / attr_val_N) are read dynamically in the view
