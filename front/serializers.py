import os

from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

# Extensions de fichiers autorisees pour l'import
# / Allowed file extensions for import
EXTENSIONS_AUTORISEES = [".pdf", ".docx", ".md", ".txt", ".pptx", ".xlsx", ".json"]

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


def est_fichier_json(nom_fichier):
    """
    Verifie si un fichier est un fichier JSON d'apres son extension.
    / Checks if a file is a JSON file based on its extension.
    """
    extension = os.path.splitext(nom_fichier)[1].lower()
    return extension == ".json"


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
    Le user est implicite (request.user), plus besoin de prenom.
    / Validation for creating a comment on an extraction.
    User is implicit (request.user), no more prenom needed.
    """
    entity_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'entite est obligatoire / Entity ID is required",
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
    Le user est implicite (request.user).
    / Validation for creating a question on a page.
    User is implicit (request.user).
    """
    page_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de la page est obligatoire / Page ID is required",
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
    Le user est implicite (request.user).
    / Validation for creating an answer to a question.
    User is implicit (request.user).
    """
    question_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de la question est obligatoire / Question ID is required",
        },
    )
    texte_reponse = serializers.CharField(
        error_messages={
            "required": "La reponse est obligatoire / Answer is required",
            "blank": "La reponse ne peut pas etre vide / Answer cannot be blank",
        },
    )


class RenommerLocuteurSerializer(serializers.Serializer):
    """
    Validation pour le renommage d'un locuteur dans une transcription audio.
    Validation for renaming a speaker in an audio transcription.
    """
    ancien_nom = serializers.CharField(
        error_messages={
            "required": "L'ancien nom du locuteur est obligatoire / Old speaker name is required",
            "blank": "L'ancien nom ne peut pas etre vide / Old name cannot be blank",
        },
    )
    nouveau_nom = serializers.CharField(
        max_length=100,
        error_messages={
            "required": "Le nouveau nom est obligatoire / New name is required",
            "blank": "Le nouveau nom ne peut pas etre vide / New name cannot be blank",
        },
    )
    portee = serializers.ChoiceField(
        choices=["ce_bloc_et_suivants", "ce_bloc_seul", "tous"],
        default="ce_bloc_et_suivants",
        error_messages={
            "required": "La portee est obligatoire / Scope is required",
        },
    )
    index_bloc = serializers.IntegerField(required=False, default=0)

    def validate_nouveau_nom(self, valeur):
        """
        Nettoie le nouveau nom — supprime les espaces et balises HTML.
        / Clean new name — strip whitespace and HTML tags.
        """
        import bleach
        nom_nettoye = bleach.clean(valeur, tags=[], strip=True).strip()
        if not nom_nettoye:
            raise serializers.ValidationError(
                "Le nom ne peut pas etre vide apres nettoyage / Name cannot be empty after sanitization"
            )
        return nom_nettoye


class EditerBlocSerializer(serializers.Serializer):
    """
    Validation pour l'edition du texte d'un bloc de transcription.
    Validation for editing the text of a transcription block.
    """
    index_bloc = serializers.IntegerField(
        error_messages={
            "required": "L'index du bloc est obligatoire / Block index is required",
        },
    )
    nouveau_texte = serializers.CharField(
        error_messages={
            "required": "Le texte est obligatoire / Text is required",
            "blank": "Le texte ne peut pas etre vide / Text cannot be blank",
        },
    )

    def validate_nouveau_texte(self, valeur):
        """
        Sanitize le texte — supprime toute balise HTML.
        / Sanitize text — strip all HTML tags.
        """
        import bleach
        texte_nettoye = bleach.clean(valeur, tags=[], strip=True).strip()
        if not texte_nettoye:
            raise serializers.ValidationError(
                "Le texte ne peut pas etre vide apres nettoyage / Text cannot be empty after sanitization"
            )
        return texte_nettoye


class SupprimerBlocSerializer(serializers.Serializer):
    """
    Validation pour la suppression d'un bloc de transcription.
    Validation for deleting a transcription block.
    """
    index_bloc = serializers.IntegerField(
        error_messages={
            "required": "L'index du bloc est obligatoire / Block index is required",
        },
    )


class ModifierTitrePageSerializer(serializers.Serializer):
    """
    Validation pour la modification inline du titre d'une page.
    Validation for inline modification of a page title.
    """
    nouveau_titre = serializers.CharField(
        max_length=500,
        error_messages={
            "required": "Le titre est obligatoire / Title is required",
            "blank": "Le titre ne peut pas etre vide / Title cannot be blank",
        },
    )

    def validate_nouveau_titre(self, valeur):
        """
        Sanitize le titre — supprime toute balise HTML.
        / Sanitize title — strip all HTML tags.
        """
        import bleach
        titre_nettoye = bleach.clean(valeur, tags=[], strip=True).strip()
        if not titre_nettoye:
            raise serializers.ValidationError(
                "Le titre ne peut pas etre vide apres nettoyage / Title cannot be empty after sanitization"
            )
        return titre_nettoye


class DossierRenommerSerializer(serializers.Serializer):
    """
    Validation pour le renommage d'un dossier.
    Validation for renaming a folder.
    """
    nouveau_nom = serializers.CharField(
        max_length=200,
        error_messages={
            "required": "Le nouveau nom est obligatoire / New name is required",
            "blank": "Le nom ne peut pas etre vide / Name cannot be blank",
        },
    )

    def validate_nouveau_nom(self, valeur):
        # Nettoyage du nom — on enleve les espaces et les balises HTML
        # / Clean name — strip whitespace and HTML tags
        import bleach
        nom_nettoye = bleach.clean(valeur, tags=[], strip=True).strip()
        if not nom_nettoye:
            raise serializers.ValidationError(
                "Le nom ne peut pas etre vide apres nettoyage / Name cannot be empty after sanitization"
            )
        return nom_nettoye


class ModifierCommentaireSerializer(serializers.Serializer):
    """
    Validation pour la modification d'un commentaire sur une extraction.
    Validation for editing a comment on an extraction.
    """
    commentaire_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID du commentaire est obligatoire / Comment ID is required",
        },
    )
    commentaire = serializers.CharField(
        error_messages={
            "required": "Le commentaire est obligatoire / Comment is required",
            "blank": "Le commentaire ne peut pas etre vide / Comment cannot be blank",
        },
    )

    def validate_commentaire(self, valeur):
        # Sanitize le commentaire — supprime toute balise HTML
        # / Sanitize comment — strip all HTML tags
        import bleach
        texte_nettoye = bleach.clean(valeur, tags=[], strip=True).strip()
        if not texte_nettoye:
            raise serializers.ValidationError(
                "Le commentaire ne peut pas etre vide apres nettoyage / Comment cannot be empty after sanitization"
            )
        return texte_nettoye


class SupprimerCommentaireSerializer(serializers.Serializer):
    """
    Validation pour la suppression d'un commentaire sur une extraction.
    Validation for deleting a comment on an extraction.
    """
    commentaire_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID du commentaire est obligatoire / Comment ID is required",
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


class ChangerStatutSerializer(serializers.Serializer):
    """
    Validation pour le changement de statut de debat d'une extraction.
    / Validation for changing the debate status of an extraction.
    """
    entity_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de l'entite est obligatoire / Entity ID is required",
        },
    )
    page_id = serializers.IntegerField(
        error_messages={
            "required": "L'ID de la page est obligatoire / Page ID is required",
        },
    )
    nouveau_statut = serializers.ChoiceField(
        choices=["consensuel", "discutable", "discute", "controverse"],
        error_messages={
            "required": "Le nouveau statut est obligatoire / New status is required",
        },
    )


# =============================================================================
# PHASE-25 — Serializers d'authentification et partage
# / PHASE-25 — Authentication and sharing serializers
# =============================================================================


class LoginSerializer(serializers.Serializer):
    """
    Validation du formulaire de connexion.
    / Login form validation.

    LOCALISATION : front/serializers.py
    """
    username = serializers.CharField(max_length=150)
    password = serializers.CharField()


class RegisterSerializer(serializers.Serializer):
    """
    Validation du formulaire d'inscription.
    / Registration form validation.

    LOCALISATION : front/serializers.py
    """
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(
        error_messages={
            "required": "L'email est obligatoire / Email is required",
            "invalid": "Format d'email invalide / Invalid email format",
        },
    )
    password = serializers.CharField(min_length=8)
    password_confirm = serializers.CharField()

    def validate_username(self, value):
        # Verifie que le nom d'utilisateur n'est pas deja pris
        # / Check that username is not already taken
        if User.objects.filter(username__iexact=value).exists():
            raise ValidationError("Ce nom d'utilisateur existe deja.")
        return value

    def validate(self, data):
        # Verifie que les mots de passe correspondent
        # / Check that passwords match
        if data["password"] != data["password_confirm"]:
            raise ValidationError({
                "password_confirm": "Les mots de passe ne correspondent pas.",
            })
        return data


class DossierPartageSerializer(serializers.Serializer):
    """
    Validation pour le partage d'un dossier avec un utilisateur.
    / Validation for sharing a folder with a user.

    LOCALISATION : front/serializers.py
    """
    username = serializers.CharField(
        max_length=150,
        help_text="Nom d'utilisateur a ajouter / Username to add",
    )
