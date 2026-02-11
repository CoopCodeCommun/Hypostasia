from rest_framework import serializers
from .models import Page, TextBlock, Argument, ArgumentComment, Prompt, TextInput, HypostasisTag, HypostasisChoices

# --- HYPOSTASES ---

class HypostasisTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = HypostasisTag
        fields = ['id', 'name', 'description']

# --- TEXT BLOCKS ---

class TextBlockSerializer(serializers.ModelSerializer):
    """
    Sérialiseur pour les blocs de texte.
    Utilisé pour l'affichage et la création nichée dans une Page.
    """
    hypostases = HypostasisTagSerializer(many=True, read_only=True)

    class Meta:
        model = TextBlock
        fields = ['id', 'selector', 'start_offset', 'end_offset', 'text', 'significant_extract', 'hypostases', 'modes']


# --- ARGUMENTS ---

class ArgumentSerializer(serializers.ModelSerializer):
    """
    Sérialiseur pour lire les arguments.
    Affiche toutes les infos utiles pour l'extension (résumé, position, etc.).
    """
    class Meta:
        model = Argument
        fields = [
            'id', 'page', 'text_block', 
            'selector', 'start_offset', 'end_offset', 
            'text_original', 'summary', 
            'user_edited', 'created_at'
        ]
        read_only_fields = ['user_edited', 'created_at']

class ArgumentUpdateSerializer(serializers.ModelSerializer):
    """
    Sérialiseur spécifique pour la modification par l'utilisateur.
    Seul le résumé est modifiable.
    """
    class Meta:
        model = Argument
        fields = ['summary']

    def update(self, instance, validated_data):
        # Si l'utilisateur modifie quelque chose, on passe le flag à True
        instance.user_edited = True
        return super().update(instance, validated_data)


# --- PAGES ---

class PageListSerializer(serializers.ModelSerializer):
    """
    Sérialiseur léger pour la liste des pages.
    """
    class Meta:
        model = Page
        fields = ['id', 'url', 'title', 'domain', 'status', 'error_message', 'created_at', 'text_readability', 'html_readability', 'html_original']

class PageCreateSerializer(serializers.ModelSerializer):
    """
    Serialiseur pour la creation d'une page (stockage uniquement, pas d'analyse).
    Accepte une liste de 'blocks' pour creer les TextBlocks en meme temps.
    Derive text_readability depuis html_readability pour garantir la coherence.
    / Serializer for page creation (storage only, no analysis).
    """
    # text_readability est derive cote serveur depuis html_readability
    # / text_readability is derived server-side from html_readability
    text_readability = serializers.CharField(required=False, allow_blank=True, default='')
    blocks = TextBlockSerializer(many=True, required=False)
    content_hash = serializers.CharField(read_only=True)

    class Meta:
        model = Page
        fields = ['id', 'url', 'title', 'html_original', 'html_readability', 'text_readability', 'content_hash', 'blocks']

    def create(self, validated_data):
        import hashlib
        import logging
        from front.utils import extraire_texte_depuis_html

        logger = logging.getLogger('core')

        blocks_data = validated_data.pop('blocks', [])

        url_page = validated_data.get('url', '(pas d\'url)')
        logger.debug(
            "PageCreateSerializer.create: url=%s html_readability=%d chars html_original=%d chars",
            url_page,
            len(validated_data.get('html_readability', '')),
            len(validated_data.get('html_original', '')),
        )

        # Deriver text_readability depuis html_readability (single source of truth)
        # Garantit la coherence entre les positions texte et le mapping HTML
        # pour l'annotation cote serveur (scroll-to-extraction).
        # / Derive text_readability from html_readability (single source of truth)
        html_readability = validated_data.get('html_readability', '')
        if html_readability:
            validated_data['text_readability'] = extraire_texte_depuis_html(html_readability)
            logger.debug(
                "PageCreateSerializer.create: text_readability derive — %d chars",
                len(validated_data['text_readability']),
            )

        # Compute content_hash from text_readability
        text = validated_data.get('text_readability', '')
        validated_data['content_hash'] = hashlib.sha256(text.encode('utf-8')).hexdigest()

        logger.debug(
            "PageCreateSerializer.create: content_hash=%s — creation Page en base",
            validated_data['content_hash'][:16],
        )

        page = Page.objects.create(**validated_data)

        logger.info(
            "PageCreateSerializer.create: Page %d creee — url=%s text=%d chars blocks=%d",
            page.pk, page.url, len(text), len(blocks_data),
        )

        for block_data in blocks_data:
            TextBlock.objects.create(page=page, **block_data)

        # Pas d'analyse LLM ici — l'analyse se lance depuis le front Hypostasia
        # / No LLM analysis here — analysis is launched from the Hypostasia front
        return page

class PageDetailSerializer(serializers.ModelSerializer):
    """
    Sérialiseur complet pour voir une page et ses blocs.
    """
    blocks = TextBlockSerializer(many=True, read_only=True)
    # On pourrait ajouter les arguments ici si besoin, mais souvent on les charge à part.
    
    class Meta:
        model = Page
        fields = [
            'id', 'url', 'created_at', 'updated_at', 
            'html_original', 'html_readability', 'text_readability', 
            'blocks'
        ]


# --- PROMPTS ---

class TextInputSerializer(serializers.ModelSerializer):
    """
    Sérialiseur pour les briques de prompt (TextInput).
    """
    class Meta:
        model = TextInput
        fields = ['id', 'name', 'role', 'content', 'order']

class PromptSerializer(serializers.ModelSerializer):
    """
    Sérialiseur pour les Prompts, incluant leurs inputs.
    """
    inputs = TextInputSerializer(many=True, read_only=True)

    class Meta:
        model = Prompt
        fields = ['id', 'name', 'description', 'created_at', 'inputs']


# --- VALIDATION ---

class AnalysisItemSerializer(serializers.Serializer):
    """
    Serializer to validate a single item from the AI JSON response.
    Used in the analysis pipeline to ensure strict adherence to the schema.
    """
    text_quote = serializers.CharField(required=True, allow_blank=False)
    significant_extract = serializers.CharField(required=True, allow_blank=False)
    summary = serializers.CharField(required=True, allow_blank=False)
    hypostasis = serializers.CharField(required=True)
    mode = serializers.CharField(required=True)
    theme = serializers.CharField(required=True, allow_blank=False)

    def validate_hypostasis(self, value):
        from .models import HypostasisChoices
        # The AI returns the value (e.g. "problème"), which matches the values in the Choice class
        if value not in HypostasisChoices.values:
            # Try lowercase just in case
            if value.lower() in HypostasisChoices.values:
                return value.lower()
            # If not in HypostasisChoices, we still allow it as it can be a new tag
            return value
        return value

    def validate_mode(self, value):
        allowed_modes = ["A initier", "Discuté", "Disputé", "Controversé", "Consensuel"]
        if value not in allowed_modes:
             raise serializers.ValidationError(f"Invalid mode: '{value}'. Must be one of {allowed_modes}")
        return value
