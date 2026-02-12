from rest_framework import serializers

from .models import Page, TextBlock


# --- BLOCS DE TEXTE / TEXT BLOCKS ---

class TextBlockSerializer(serializers.ModelSerializer):
    """
    Serialiseur pour les blocs de texte envoyes par l'extension navigateur.
    Utilise dans PageCreateSerializer pour creer les blocs en meme temps que la page.
    / Serializer for text blocks sent by the browser extension.
    / Used in PageCreateSerializer to create blocks alongside the page.
    """
    class Meta:
        model = TextBlock
        fields = [
            "id", "selector", "start_offset", "end_offset",
            "text", "significant_extract", "hypostases", "modes",
        ]


# --- PAGES ---

class PageListSerializer(serializers.ModelSerializer):
    """
    Serialiseur leger pour la liste des pages (GET /api/pages/).
    L'extension l'utilise pour verifier si une page existe deja via ?url=...
    / Lightweight serializer for the page list (GET /api/pages/).
    / The extension uses it to check if a page already exists via ?url=...
    """
    class Meta:
        model = Page
        fields = [
            "id", "url", "title", "domain", "status",
            "error_message", "created_at",
            "text_readability", "html_readability", "html_original",
        ]


class PageCreateSerializer(serializers.ModelSerializer):
    """
    Serialiseur pour la creation d'une page (POST /api/pages/).
    Accepte une liste optionnelle de 'blocks' pour creer les TextBlocks en meme temps.
    Derive text_readability depuis html_readability pour garantir la coherence
    entre les positions texte et le mapping HTML (annotation cote serveur).
    / Serializer for page creation (POST /api/pages/).
    / Accepts an optional 'blocks' list to create TextBlocks alongside.
    / Derives text_readability from html_readability for consistency
    / between text positions and HTML mapping (server-side annotation).
    """
    text_readability = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    blocks = TextBlockSerializer(many=True, required=False)
    content_hash = serializers.CharField(read_only=True)

    class Meta:
        model = Page
        fields = [
            "id", "url", "title",
            "html_original", "html_readability", "text_readability",
            "content_hash", "blocks",
        ]

    def create(self, validated_data):
        import hashlib
        import logging

        from front.utils import extraire_texte_depuis_html

        logger = logging.getLogger("core")

        blocks_data = validated_data.pop("blocks", [])

        url_page = validated_data.get("url", "(pas d'url)")
        logger.debug(
            "PageCreateSerializer.create: url=%s html_readability=%d chars html_original=%d chars",
            url_page,
            len(validated_data.get("html_readability", "")),
            len(validated_data.get("html_original", "")),
        )

        # Deriver text_readability depuis html_readability (single source of truth)
        # Garantit la coherence entre les positions texte et le mapping HTML
        # pour l'annotation cote serveur (scroll-to-extraction).
        # / Derive text_readability from html_readability (single source of truth)
        html_readability = validated_data.get("html_readability", "")
        if html_readability:
            validated_data["text_readability"] = extraire_texte_depuis_html(
                html_readability
            )
            logger.debug(
                "PageCreateSerializer.create: text_readability derive — %d chars",
                len(validated_data["text_readability"]),
            )

        # Calculer le hash du contenu pour detecter les modifications futures
        # / Compute content hash to detect future modifications
        texte_pour_hash = validated_data.get("text_readability", "")
        validated_data["content_hash"] = hashlib.sha256(
            texte_pour_hash.encode("utf-8")
        ).hexdigest()

        logger.debug(
            "PageCreateSerializer.create: content_hash=%s — creation Page en base",
            validated_data["content_hash"][:16],
        )

        page_creee = Page.objects.create(**validated_data)

        logger.info(
            "PageCreateSerializer.create: Page %d creee — url=%s text=%d chars blocks=%d",
            page_creee.pk,
            page_creee.url,
            len(texte_pour_hash),
            len(blocks_data),
        )

        # Creation des blocs de texte associes a la page
        # / Create text blocks associated with the page
        for donnees_bloc in blocks_data:
            TextBlock.objects.create(page=page_creee, **donnees_bloc)

        # Pas d'analyse LLM ici — l'analyse se lance depuis le front Hypostasia
        # / No LLM analysis here — analysis is launched from the Hypostasia front
        return page_creee


# --- VALIDATION PIPELINE IA / AI PIPELINE VALIDATION ---

class AnalysisItemSerializer(serializers.Serializer):
    """
    Valide un element individuel de la reponse JSON du LLM.
    Utilise dans le pipeline d'analyse pour garantir la conformite au schema.
    / Validates a single item from the LLM JSON response.
    / Used in the analysis pipeline to ensure schema compliance.
    """
    text_quote = serializers.CharField(required=True, allow_blank=False)
    significant_extract = serializers.CharField(required=True, allow_blank=False)
    summary = serializers.CharField(required=True, allow_blank=False)
    hypostasis = serializers.CharField(required=True)
    mode = serializers.CharField(required=True)
    theme = serializers.CharField(required=True, allow_blank=False)

    def validate_hypostasis(self, value):
        from .models import HypostasisChoices

        # L'IA renvoie la valeur (ex: "probleme"), qui correspond aux values du Choice
        # / The AI returns the value (e.g. "probleme"), matching Choice values
        if value not in HypostasisChoices.values:
            valeur_minuscule = value.lower()
            if valeur_minuscule in HypostasisChoices.values:
                return valeur_minuscule
            # Si absent de HypostasisChoices, on accepte quand meme (nouveau tag possible)
            # / If not in HypostasisChoices, still accept (may be a new tag)
            return value
        return value

    def validate_mode(self, value):
        modes_autorises = [
            "A initier", "Discuté", "Disputé", "Controversé", "Consensuel",
        ]
        if value not in modes_autorises:
            raise serializers.ValidationError(
                f"Mode invalide: '{value}'. Doit etre parmi {modes_autorises}"
            )
        return value
