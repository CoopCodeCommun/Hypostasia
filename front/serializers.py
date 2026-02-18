import os

from rest_framework import serializers

# Extensions de fichiers autorisees pour l'import
# / Allowed file extensions for import
EXTENSIONS_AUTORISEES = [".pdf", ".docx", ".md", ".txt", ".pptx", ".xlsx"]

# Extensions audio autorisees (tous les formats ffmpeg courants)
# / Allowed audio extensions (all common ffmpeg formats)
EXTENSIONS_AUDIO_AUTORISEES = [
    ".mp3", ".wav", ".m4a", ".ogg", ".flac",
    ".webm", ".aac", ".wma", ".opus", ".aiff",
]

# Toutes les extensions acceptees (documents + audio)
# / All accepted extensions (documents + audio)
TOUTES_LES_EXTENSIONS = EXTENSIONS_AUTORISEES + EXTENSIONS_AUDIO_AUTORISEES

TAILLE_MAX_FICHIER = 50 * 1024 * 1024  # 50 MB


def est_fichier_audio(nom_fichier):
    """
    Verifie si un fichier est un fichier audio d'apres son extension.
    / Checks if a file is an audio file based on its extension.
    """
    extension = os.path.splitext(nom_fichier)[1].lower()
    return extension in EXTENSIONS_AUDIO_AUTORISEES


class ImportFichierSerializer(serializers.Serializer):
    """
    Validation pour l'import d'un fichier a convertir en Page.
    / Validation for importing a file to convert into a Page.
    """
    fichier = serializers.FileField(
        error_messages={
            "required": "Le fichier est obligatoire / File is required",
        },
    )
    titre = serializers.CharField(required=False, allow_blank=True, default="")
    dossier_id = serializers.IntegerField(required=False, allow_null=True, default=None)

    def validate_fichier(self, fichier_uploade):
        # Valider l'extension du fichier
        # / Validate file extension
        nom_fichier = fichier_uploade.name or ""
        extension = os.path.splitext(nom_fichier)[1].lower()
        if extension not in TOUTES_LES_EXTENSIONS:
            raise serializers.ValidationError(
                f"Extension '{extension}' non supportee. Extensions acceptees : {', '.join(TOUTES_LES_EXTENSIONS)}"
            )

        # Valider la taille du fichier
        # / Validate file size
        if fichier_uploade.size > TAILLE_MAX_FICHIER:
            taille_mo = fichier_uploade.size / (1024 * 1024)
            raise serializers.ValidationError(
                f"Fichier trop volumineux ({taille_mo:.1f} Mo). Maximum : 50 Mo."
            )

        return fichier_uploade


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


class CommentaireExtractionSerializer(serializers.Serializer):
    """
    Validation pour la creation d'un commentaire sur une extraction.
    Validation for creating a comment on an extraction.
    """
    entity_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'entite est obligatoire / Entity ID is required",
        },
    )
    prenom = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Le prenom est obligatoire / First name is required",
            "blank": "Le prenom ne peut pas etre vide / First name cannot be blank",
        },
    )
    commentaire = serializers.CharField(
        error_messages={
            "required": "Le commentaire est obligatoire / Comment is required",
            "blank": "Le commentaire ne peut pas etre vide / Comment cannot be blank",
        },
    )


class QuestionSerializer(serializers.Serializer):
    """
    Validation pour la creation d'une question sur une page.
    Validation for creating a question on a page.
    """
    page_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de la page est obligatoire / Page ID is required",
        },
    )
    prenom = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Le prenom est obligatoire / First name is required",
            "blank": "Le prenom ne peut pas etre vide / First name cannot be blank",
        },
    )
    texte_question = serializers.CharField(
        error_messages={
            "required": "La question est obligatoire / Question is required",
            "blank": "La question ne peut pas etre vide / Question cannot be blank",
        },
    )


class PromouvoirEntrainementSerializer(serializers.Serializer):
    """
    Validation pour promouvoir les extractions d'une page en exemple d'entrainement.
    Validation for promoting a page's extractions into a training example.
    """
    page_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de la page est obligatoire / Page ID is required",
        },
    )
    analyseur_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'analyseur est obligatoire / Analyzer ID is required",
        },
    )


class RunReformulationSerializer(serializers.Serializer):
    """
    Validation pour lancer une reformulation sur une extraction specifique.
    Validation for launching a reformulation on a specific extraction.
    """
    entity_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'entite est obligatoire / Entity ID is required",
        },
    )
    analyseur_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'analyseur est obligatoire / Analyzer ID is required",
        },
    )


class RunRestitutionSerializer(serializers.Serializer):
    """
    Validation pour lancer une restitution IA sur une extraction specifique.
    Validation for launching an AI restitution on a specific extraction.
    """
    entity_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'entite est obligatoire / Entity ID is required",
        },
    )
    analyseur_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'analyseur est obligatoire / Analyzer ID is required",
        },
    )


class ReponseQuestionSerializer(serializers.Serializer):
    """
    Validation pour la creation d'une reponse a une question.
    Validation for creating an answer to a question.
    """
    question_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de la question est obligatoire / Question ID is required",
        },
    )
    prenom = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Le prenom est obligatoire / First name is required",
            "blank": "Le prenom ne peut pas etre vide / First name cannot be blank",
        },
    )
    texte_reponse = serializers.CharField(
        error_messages={
            "required": "La reponse est obligatoire / Answer is required",
            "blank": "La reponse ne peut pas etre vide / Answer cannot be blank",
        },
    )


class RechercheSemantiqueSerializer(serializers.Serializer):
    """
    Validation pour la recherche semantique dans un dossier.
    Validation for semantic search within a folder.
    """
    dossier_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID du dossier est obligatoire / Folder ID is required",
        },
    )
    q = serializers.CharField(
        min_length=2,
        error_messages={
            "required": "Le texte de recherche est obligatoire / Search text is required",
            "blank": "Le texte de recherche ne peut pas etre vide / Search text cannot be blank",
            "min_length": "Minimum 2 caracteres / Minimum 2 characters",
        },
    )


class RestitutionDebatSerializer(serializers.Serializer):
    """
    Validation pour la creation d'une restitution depuis un debat d'extraction.
    Le texte est sanitize via bleach : aucune balise HTML n'est autorisee.
    / Validation for creating a restitution from an extraction debate.
    Text is sanitized via bleach: no HTML tags allowed.
    """
    entity_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'entite est obligatoire / Entity ID is required",
        },
    )
    version_label = serializers.CharField(
        max_length=200, required=False, default="", allow_blank=True,
    )
    texte_restitution = serializers.CharField(
        error_messages={
            "required": "Le texte de restitution est obligatoire / Restitution text is required",
            "blank": "Le texte ne peut pas etre vide / Text cannot be blank",
        },
    )

    def validate_texte_restitution(self, valeur):
        """
        Sanitize le texte de restitution — supprime toute balise HTML.
        / Sanitize restitution text — strip all HTML tags.
        """
        import bleach
        texte_nettoye = bleach.clean(valeur, tags=[], strip=True).strip()
        if not texte_nettoye:
            raise serializers.ValidationError(
                "Le texte ne peut pas etre vide apres nettoyage / Text cannot be empty after sanitization"
            )
        return texte_nettoye

    def validate_version_label(self, valeur):
        """
        Sanitize le label de version — supprime toute balise HTML.
        / Sanitize version label — strip all HTML tags.
        """
        import bleach
        return bleach.clean(valeur, tags=[], strip=True).strip()
