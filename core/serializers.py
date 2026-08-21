from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import CategorieDossier, Page, TextBlock
from .services.corpus import valider_les_categories_d_une_appartenance


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

    LOCALISATION : core/serializers.py

    IL NE PORTE PLUS LE CONTENU DES NOTES. Repondre « cette URL est deja
    la » demande un identifiant et une URL ; livrer en plus
    `text_readability`, `html_readability` et `html_original` de chaque
    note du perimetre est hors de proportion avec la question posee.
    Mesure du 20 aout 2026 sur le depot : la reponse pesait 291 840
    octets pour 13 notes, dont 150 384 caracteres de texte lisible.
    / It no longer carries note content: answering "is this URL already
    here?" needs an id and a URL, not the full text of every note.
    """
    class Meta:
        model = Page
        fields = [
            "id", "url", "title", "domain", "status",
            "error_message", "created_at",
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
    # LECTURE SEULE, ET C'EST LE POINT. L'empreinte a longtemps eu DEUX
    # implementations : l'extension hachait `body.textContent` (sans
    # `.strip()`), le serveur hachait `extraire_texte_depuis_html()`
    # (avec). Mesure du 20 aout 2026 : sur les 10 notes du depot ayant un
    # `html_readability`, 2 donnaient deux empreintes differentes — donc
    # le doublon par contenu ne se declenchait pas. Une seule
    # implementation supprime la classe de bug au lieu de la corriger.
    # / Read-only on purpose: the hash had two implementations that
    # disagreed on 2 of 10 measured notes, so content dedup never fired.
    content_hash = serializers.CharField(read_only=True)
    # Le carnet demande par l'extension. Il ne va pas sur le modele — il
    # est retire dans create() et rendu a la vue, qui verifie le droit
    # d'ecriture. Il passe ICI et non par le payload brut pour qu'un
    # `dossier_id` non entier rende un 400 lisible : lu du brut, il
    # arrivait tel quel dans un `filter(pk=...)` et levait une
    # `ValueError` — donc un 500 pour une faute de frappe.
    # / The notebook the extension asks for: validated here so a
    # non-integer value yields a readable 400 instead of a 500.
    dossier_id = serializers.IntegerField(
        required=False, allow_null=True, write_only=True,
        error_messages={
            "invalid": "dossier_id doit être un entier / must be an integer",
        },
    )

    class Meta:
        model = Page
        fields = [
            "id", "url", "title",
            "html_original", "html_readability", "text_readability",
            "content_hash", "blocks", "dossier_id",
        ]

    def create(self, validated_data):
        import logging

        from front.services.texte_depuis_html import (
            empreinte_d_une_capture,
            extraire_texte_depuis_html,
        )

        logger = logging.getLogger("core")

        blocks_data = validated_data.pop("blocks", [])
        # La destination n'est pas un champ du modele : la vue s'en est
        # deja servie pour resoudre le carnet, et le rangement passe par
        # `ranger_une_note_dans_un_carnet`.
        # / Not a model field: the view already resolved the notebook.
        validated_data.pop("dossier_id", None)

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

        # L'empreinte de deduplication, par la fonction que la vue appelle
        # elle aussi : une seule implementation, deux appelants.
        # / The dedup fingerprint, through the function the view calls too.
        texte_pour_hash = validated_data.get("text_readability", "")
        validated_data["content_hash"] = empreinte_d_une_capture(
            html_readability, texte_pour_hash,
        )

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

class ClasserDepuisExtensionSerializer(serializers.Serializer):
    """
    Validation pour le classement d'une page dans un dossier depuis l'extension.
    / Validation for classifying a page into a folder from the extension.

    LOCALISATION : core/serializers.py
    """
    dossier_id = serializers.IntegerField(
        error_messages={
            "required": "dossier_id est obligatoire / dossier_id is required",
        },
    )


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


# --- COUCHE CORPUS / CORPUS LAYER ---

class CategoriserUneNoteSerializer(serializers.Serializer):
    """
    Valide les categories a appliquer a UNE appartenance note-carnet.
    / Validates the categories to apply to ONE note-notebook membership.

    LOCALISATION : core/serializers.py

    Contexte requis : {"appartenance": AppartenancePageDossier}.
    La regle de fond (chaque categorie vient du carnet de l'appartenance)
    vit dans core/services/corpus.py — le serializer la traduit en erreur
    de formulaire, le signal m2m_changed (core/signals.py) la garantit en
    dernier filet.
    / Context requires the membership. The core rule lives in
    core/services/corpus.py; the m2m signal is the last safety net.
    """

    categorie_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
        max_length=100,
        help_text="Les categories de CE carnet a appliquer a CETTE note. "
                  "Liste vide = tout decocher. Les doublons sont absorbes.",
    )

    def validate_categorie_ids(self, identifiants_soumis):
        appartenance = self.context.get("appartenance")
        if appartenance is None:
            raise AssertionError(
                "CategoriserUneNoteSerializer exige le contexte "
                "{'appartenance': AppartenancePageDossier} / requires the "
                "'appartenance' context key"
            )

        # Reinitialise a chaque validation : jamais d'etat perime si
        # l'instance etait revalidee. / Reset on every validation run.
        self._categories_validees = []

        categories_trouvees = list(
            CategorieDossier.objects.select_related("liste").filter(
                pk__in=identifiants_soumis
            )
        )
        identifiants_introuvables = set(identifiants_soumis) - {
            categorie.pk for categorie in categories_trouvees
        }
        if identifiants_introuvables:
            raise serializers.ValidationError(
                f"Catégories introuvables : {sorted(identifiants_introuvables)}"
                f" / Categories not found: {sorted(identifiants_introuvables)}"
            )

        try:
            valider_les_categories_d_une_appartenance(
                appartenance, categories_trouvees
            )
        except DjangoValidationError as erreur:
            raise serializers.ValidationError(erreur.messages)

        # On expose les objets valides pour que la vue n'ait pas a les
        # recharger. / Expose the validated objects so the view does not
        # reload them.
        self._categories_validees = categories_trouvees
        return identifiants_soumis

    def validate(self, donnees_validees):
        donnees_validees["categories_a_appliquer"] = getattr(
            self, "_categories_validees", []
        )
        return donnees_validees
