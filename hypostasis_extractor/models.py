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
                  "End-of-task notification read by the owner. MORT "
                  "pour la decision depuis la correction 1 (11 aout "
                  "2026) : voir core.models.NotificationTacheLue, qui "
                  "porte le drapeau PAR DESTINATAIRE. Champ laisse en "
                  "base mais plus ecrit ni lu.",
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
    
    # Offsets HERITES de l'ancien moteur d'ancrage. Ils ne designent PLUS
    # une position dans `Page.text_readability` : ce champ est vide sur
    # toute note ingeree par Docling, et le moteur ELEMENT est le seul
    # moteur depuis le 10 aout 2026. Ce sont des offsets relatifs au
    # CHUNK analyse, sans referentiel utilisable seul.
    # L'ancrage qui fait la preuve, c'est `AncrageExtraction` : une ou
    # plusieurs portions bornees a l'interieur d'un ElementDocument.
    # / Legacy offsets: chunk-relative, NOT positions in text_readability.
    # The real anchor is AncrageExtraction.
    start_char = models.PositiveIntegerField(
        help_text=(
            "Offset de debut relatif au chunk analyse (herite de l'ancien "
            "moteur). L'ancrage reel est AncrageExtraction."
        )
    )
    end_char = models.PositiveIntegerField(
        help_text=(
            "Offset de fin relatif au chunk analyse (herite de l'ancien "
            "moteur). L'ancrage reel est AncrageExtraction."
        )
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

    # Statut du debat sur cette extraction (binaire : nouveau / commente)
    # / Debate status for this extraction (binary: nouveau / commente)
    class StatutDebat(models.TextChoices):
        NOUVEAU = "nouveau", "Nouveau"
        COMMENTE = "commente", "Commenté"

    statut_debat = models.CharField(
        max_length=20,
        choices=StatutDebat.choices,
        default=StatutDebat.NOUVEAU,
        help_text=(
            "Statut auto-derive de l'existence de commentaires. "
            "Mis a jour par signal Django, jamais set manuellement. "
            "/ Status auto-derived from comment existence. "
            "Updated by Django signal, never set manually."
        ),
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
        # TROIS TYPES, ET PAS DAVANTAGE TANT QU'UNE MESURE NE LE RECLAME.
        #
        # La mise a jour d'un wiki n'a PAS son type : c'est le meme metier
        # sur le meme article, et ce qui change est la consigne, qui reste
        # en dur dans le code. Un type de plus ferait diverger deux
        # preambules qui doivent dire la meme chose — et
        # `mettre_a_jour_un_wiki` aurait fait 21 caracteres, donc n'aurait
        # pas tenu dans `max_length=20`.
        # / Three types: a wiki update is the same trade on the same
        # article, and a fourth name would not even fit the column.
        ANALYSER = "analyser", "Analyser"
        SYNTHETISER = "synthetiser", "Synthétiser"
        REDIGER_UN_ARTICLE = "rediger_un_article", "Rédiger un article"

    name = models.CharField(max_length=200, help_text="Nom de l'analyseur")
    description = models.TextField(blank=True, help_text="Description de l'analyseur")
    is_active = models.BooleanField(default=True)

    # Type d'analyseur : determine les fonctionnalites disponibles dans l'interface
    # / Analyzer type: determines which features are available in the UI
    type_analyseur = models.CharField(
        max_length=20,
        choices=TypeAnalyseur.choices,
        default=TypeAnalyseur.ANALYSER,
        help_text="Type d'analyseur : analyser, synthetiser ou rediger_un_article "
                  "/ Analyzer type: analyser, synthetiser or rediger_un_article",
    )

    # Pose par l'installation, jamais par un geste d'utilisateur.
    # / Set by the installation, never by a user gesture.
    est_d_origine = models.BooleanField(
        default=False,
        help_text=(
            "Analyseur posé par l'installation. Seul un superutilisateur "
            "peut le modifier : c'est le prompt sur lequel tout le site "
            "retombe, et une modification malheureuse s'y propage à "
            "toutes les productions."
        ),
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

    def texte_du_prompt(self):
        """
        Le preambule assemble : chaque piece sous le titre de son role.
        / The assembled preamble: each piece under its role heading.

        LOCALISATION : hypostasis_extractor/models.py

        LE SEUL POINT D'ASSEMBLAGE. Neuf endroits du depot recollaient
        les pieces a la main, chacun a sa facon. Une seule facon, ici :
        un titre `=== ROLE ===` par piece, dans l'ordre de `order`.
        / The single assembly site: nine places used to glue pieces by
        hand, each its own way.

        POURQUOI LE ROLE PART AU MODELE. Il classait les pieces a l'ecran
        sans jamais rien dire au modele. Titrer chaque bloc le rend
        LISIBLE par le modele, et cohérent avec le reste du prompt, qui
        est deja decoupe ainsi (`=== SUJET DE L'ARTICLE ===`,
        `=== EXTRACTIONS DU PERIMETRE ===`, `=== CONSIGNE ===`).
        / The role now travels: it titles each block, like the rest of
        the prompt already does.

        UNE PIECE VIDE NE PRODUIT PAS DE TITRE ORPHELIN : un bloc sans
        contenu n'apprend rien au modele, et son titre seul lui ferait
        croire a une section qu'on aurait oublie de remplir.
        / An empty piece yields no orphan heading.

        :return: le preambule, ou une chaine vide s'il n'y a rien
        """
        blocs = []
        for piece in self.pieces.order_by("order", "pk"):
            contenu = (piece.content or "").strip()
            if not contenu:
                continue
            titre = piece.get_role_display().upper()
            blocs.append(f"=== {titre} ===\n{contenu}")
        return "\n\n".join(blocs)

    def save(self, *args, **kwargs):
        # Si on coche est_par_defaut, decocher les autres analyseurs du meme type
        # / If we check est_par_defaut, uncheck other analyzers of the same type
        if self.est_par_defaut:
            AnalyseurSyntaxique.objects.filter(
                type_analyseur=self.type_analyseur,
                est_par_defaut=True,
            ).exclude(pk=self.pk).update(est_par_defaut=False)
        super().save(*args, **kwargs)


class PreferenceD_analyseur(models.Model):
    """
    L'analyseur qu'UN utilisateur prefere, pour UN type de geste.
    / The analyzer ONE user prefers, for ONE gesture type.

    LOCALISATION : hypostasis_extractor/models.py

    POURQUOI UNE PREFERENCE PLUTOT QU'UN DEFAUT DE PLUS.
    `AnalyseurSyntaxique.est_par_defaut` designe l'analyseur sur lequel
    TOUT LE SITE retombe : le cocher engage les productions de tout le
    monde. Une preference n'engage que celui qui la pose — elle
    preremplit SON selecteur, et rien d'autre.
    / A site default binds everyone; a preference binds only its owner.

    ELLE NE FAIT QUE PREREMPLIR. Le choix reel se fige sur le job au
    moment du geste (`raw_result["analyseur_id"]`) : changer sa
    preference ne rejoue aucune production passee, et n'atteint aucune
    production deja en file.
    / It only preselects: the real choice freezes on the job.

    UNE SEULE PAR (UTILISATEUR, TYPE) — sans quoi « ma preference » ne
    designerait rien de precis. / One per (user, type).
    """

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences_d_analyseur",
    )
    type_analyseur = models.CharField(
        max_length=20,
        choices=AnalyseurSyntaxique.TypeAnalyseur.choices,
        help_text="Le geste auquel cette préférence s'applique "
                  "/ The gesture this preference applies to",
    )
    # CASCADE : une preference qui designe un analyseur supprime ne veut
    # plus rien dire — la resolution retomberait de toute facon sur le
    # defaut du type. / CASCADE: a preference naming a deleted analyzer
    # means nothing; resolution falls back to the type default anyway.
    analyseur = models.ForeignKey(
        AnalyseurSyntaxique,
        on_delete=models.CASCADE,
        related_name="preferee_par",
    )
    posee_le = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["utilisateur", "type_analyseur"],
                name="une_preference_par_utilisateur_et_par_type",
            ),
        ]
        verbose_name = "Préférence d'analyseur"
        verbose_name_plural = "Préférences d'analyseur"

    def __str__(self):
        return f"{self.utilisateur} préfère {self.analyseur} pour {self.type_analyseur}"


class PromptPiece(models.Model):
    """
    Morceau de prompt ordonne, lie a un AnalyseurSyntaxique.
    / Ordered prompt piece, linked to an AnalyseurSyntaxique.

    LOCALISATION : hypostasis_extractor/models.py

    CE QUI PART AU MODELE : le `content`, TITRE par le role, dans
    l'ordre de `order` — c'est `AnalyseurSyntaxique.texte_du_prompt()`
    qui assemble, et lui seul.
    / What is sent: the content, TITLED by its role, in `order` order.

    UNE PIECE N'A PAS DE NOM, et n'en a jamais eu besoin : le nom ne
    partait nulle part. L'ecran en offrait un a remplir, que le modele
    ne voyait pas — les trois pieces de l'installation l'avaient laisse
    vide.
    / A piece has no name: it never travelled anywhere.
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
        return f"[{self.role}] {(self.content or '')[:60]}"


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


class CheminDeProduction(models.TextChoices):
    """
    Par quel geste un prompt est parti au modele.
    / Which gesture sent a prompt to the model.

    LOCALISATION : hypostasis_extractor/models.py

    UN CHEMIN N'EST PAS UN TYPE D'ANALYSEUR. Le type dit quel PROMPT-
    SOURCE a servi ; le chemin dit quel GESTE l'a employe. Deux gestes
    peuvent partager un type — rediger un wiki et le mettre a jour sont
    le meme metier sur le meme article — et il faut pourtant pouvoir les
    comparer separement.
    / A path is not an analyzer type: the type says which prompt source
    served, the path says which gesture used it.
    """
    ANALYSE = "analyse", "Analyse d'une note"
    SYNTHESE_NOTE = "synthese_note", "Synthèse d'une note"
    WIKI = "wiki", "Article de wiki"
    SYNTHESE_DIRIGEE = "synthese_dirigee", "Synthèse dirigée de carnet"
    MAJ_WIKI = "maj_wiki", "Mise à jour d'un wiki"


class ProvenanceDeProduction(models.Model):
    """
    Quel prompt a produit ce texte, et n'a-t-il pas change depuis ?
    / Which prompt produced this text, and has it changed since?

    LOCALISATION : hypostasis_extractor/models.py

    UNE TABLE DEDIEE, JAMAIS `ExtractionJob`. Trois raisons, toutes
    verifiees :

    1. `/api/extraction-jobs/` rend `prompt_description` ET `raw_result`
       (`ExtractionJobDetailSerializer`). L'API est fermee aux inconnus
       depuis le 23 aout 2026, mais elle reste ouverte a qui accede a la
       note — donc a tout compte connecte si le carnet est public. Y
       ecrire l'assemblage y deverserait 25 000 a 80 000 caracteres de
       corpus par job ;
    2. le menu des taches charge trente `ExtractionJob` COMPLETS, sans
       `.only()` ni `.defer()` ;
    3. un tour de wiki est l'objet d'histoire du projet. Le champ
       `tour_de_wiki` existe pour qu'il pointe sa provenance, mais
       AUCUN chemin actuel ne l'ecrit : un tour rejoint sa provenance
       par le job de la proposition (`TourDeWiki.job`).
    / A dedicated table: the API exposes job rows, the task menu loads
    thirty whole ones. A round reaches its provenance through the job;
    `tour_de_wiki` has no writer today.

    CE QU'ELLE NE GARDE PAS : le texte du prompt. Une EMPREINTE et une
    longueur suffisent aux deux seules questions qui comptent — « quel
    prompt a ecrit ce paragraphe ? » et « le prompt a-t-il change entre
    deux tours ? ». Garder le texte integral est un chantier a part
    (`PLAN/TODO/2026-08-23-garder-le-texte-integral-d-un-prompt.md`),
    parce qu'il pose des questions de volume et de fuite que
    l'empreinte ne pose pas.
    / It keeps a fingerprint and a length, never the text.

    DEUX ANCRES NULLABLES, ET ELLES PEUVENT DISPARAITRE TOUTES LES DEUX.
    `SET_NULL` des deux cotes : un job supprime ou un tour supprime
    laisse une provenance orpheline, qui garde son empreinte, son
    chemin, son modele et sa date. C'est voulu — une empreinte sans
    ancre reste comparable a une autre, et c'est exactement ce qu'un banc
    lui demande.
    / Both anchors are nullable and may vanish: the fingerprint stays
    comparable, which is what a benchmark asks of it.
    """

    # L'ancre du chemin humain : le job porte deja le demandeur, le
    # modele et l'issue. / The human path's anchor.
    job = models.ForeignKey(
        ExtractionJob,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="provenances",
        help_text="Le job de la demande, s'il y en a un / The job, if any",
    )
    # L'ancre de l'histoire d'un article. / The article history anchor.
    tour_de_wiki = models.ForeignKey(
        "core.TourDeWiki",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="provenances",
        help_text="Le tour de wiki que cette production a écrit "
                  "/ The wiki round this production wrote",
    )
    chemin = models.CharField(
        max_length=30,
        choices=CheminDeProduction.choices,
        help_text="Le geste qui a envoyé ce prompt / The sending gesture",
    )
    analyseur = models.ForeignKey(
        AnalyseurSyntaxique,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="provenances",
        help_text="L'analyseur dont le préambule a servi / The analyzer used",
    )
    analyseur_version = models.ForeignKey(
        "AnalyseurVersion",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="provenances",
        help_text="La version de cet analyseur au moment de l'envoi "
                  "/ That analyzer's version at send time",
    )
    modele = models.ForeignKey(
        AIModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="provenances",
        help_text="Le modèle qui a reçu ce prompt / The model that got it",
    )
    # SHA-256 hexadecimal du prompt assemble, tel qu'envoye.
    # / Hex SHA-256 of the assembled prompt, as sent.
    empreinte = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 du prompt assemblé / SHA-256 of the prompt",
    )
    longueur = models.PositiveIntegerField(
        help_text="Longueur du prompt assemblé, en caractères "
                  "/ Assembled prompt length, in characters",
    )
    # TRIEE, toujours. Les perimetres se calculent en `set`, qui s'itere
    # dans un ordre que rien ne garantit : versee telle quelle, la liste
    # changerait d'une production a l'autre sans qu'aucune extraction
    # n'ait bouge. / Always sorted: scopes are computed as sets.
    extractions_montrees = models.JSONField(
        default=list, blank=True,
        help_text="Les identifiants d'extractions montrés au modèle, "
                  "triés / The extraction ids shown to the model, sorted",
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le", "-pk"]
        verbose_name = "Provenance de production"
        verbose_name_plural = "Provenances de production"

    def __str__(self):
        return f"{self.chemin} · {self.empreinte[:12]} · {self.longueur} car."


# =============================================================================
# ANCRAGE PAR ELEMENT — la table de liaison M2M (SPEC v2, phase A)
# / Element-based anchoring — the M2M link table (SPEC v2, phase A)
#
# LOCALISATION : hypostasis_extractor/models.py
#
# Les anciens champs ExtractedEntity.start_char / end_char restent en place
# et continuent de fonctionner. Rien n'est migre de force (SPEC v2 section 9).
# / The old start_char / end_char fields stay in place and keep working.
# =============================================================================


class EtatAncrage(models.TextChoices):
    """
    Est-ce qu'on retrouve encore, ELEMENT PAR ELEMENT, le passage source
    d'une portion d'extraction ?
    / Can we still locate, per element, the source passage of a portion?

    LOCALISATION : hypostasis_extractor/models.py

    DEUX ETATS, PAS TROIS

    Une premiere version distinguait EXACTE (position calculee au premier
    ancrage) et RETROUVEE (repositionnee apres une edition). Cette
    distinction ne changeait RIEN : ni le regime d'edition (SPEC section
    3), ni l'affichage, ni le calcul de l'etat de l'element. Seule
    comptait la difference avec DETACHEE.

    Deux etats qui se comportent pareil, c'est une occasion de se tromper
    sans contrepartie. On les a fusionnes en ANCREE. L'histoire fine —
    quelle portion a bouge, quand, a cause de quelle edition — vit dans
    ElementOperation et PageEdit, qui sont faits pour ca.
    / Two states that behave identically are a trap with no upside.

    L'etat DETACHEE s'appelait ORPHELINE dans une premiere version. On l'a
    renomme parce que le mot "orpheline" designe deja une PAGE sans dossier
    ailleurs dans le code. Deux sens pour un meme mot, c'est un piege.
    / Renamed from ORPHELINE: that word already means "page without folder".
    """
    ANCREE = "ancree", "Ancrée — le passage source est localisé"
    DETACHEE = "detachee", "Détachée — le passage source a changé"


class AncrageExtraction(models.Model):
    """
    Une PORTION d'une extraction, dans UN element.
    / One PORTION of an extraction, within ONE element.

    LOCALISATION : hypostasis_extractor/models.py

    Pourquoi une table de liaison, et pas une simple ForeignKey ?
    Parce qu'une extraction deborde souvent d'un seul element. Exemple
    mesure : une extraction d'une seule phrase enjambe deja deux elements
    dans 7,5 % des cas ; une extraction de deux phrases, dans 76 % des cas.
    Une ForeignKey unique ne saurait pas dire ou est le reste.
    / A single ForeignKey could not express an extraction spanning elements.

    COMMENT LIRE UNE ANCRE :
    - Une extraction qui tient dans un seul element a UNE ligne ici.
    - Une extraction qui traverse trois elements a TROIS lignes,
      ordre_dans_extraction 0, 1, 2.
    - Mises bout a bout, ces portions redonnent le texte extrait, SAUF les
      separateurs de jonction (les sauts de ligne entre deux elements), qui
      n'appartiennent a aucune portion.

    C'est pour cette raison que le surlignage produit N balises <mark> et
    non une seule qui traverserait deux paragraphes : le modele de donnees
    suit exactement ce que le rendu HTML doit de toute facon faire.
    / The data model mirrors what the HTML rendering must do anyway.
    """
    extraction = models.ForeignKey(
        ExtractedEntity,
        on_delete=models.CASCADE,
        related_name="ancrages",
        help_text="Extraction dont ceci est une portion / Extraction this is a portion of",
    )
    element = models.ForeignKey(
        "core.ElementDocument",
        # PROTECT : on ne supprime jamais un element qui porte une portion.
        # Le moteur de structure doit d'abord redistribuer les portions,
        # ensuite seulement l'element d'origine peut disparaitre.
        # / PROTECT: an element carrying a portion is never deleted directly.
        on_delete=models.PROTECT,
        related_name="portions_d_extractions",
        help_text="Element qui porte cette portion / Element carrying this portion",
    )
    ordre_dans_extraction = models.PositiveSmallIntegerField(
        help_text="0 pour la premiere portion (la plus a gauche dans le "
                  "document), 1 pour la suivante, etc.",
    )
    debut_dans_element = models.PositiveIntegerField(
        help_text="Position de debut DANS LE TEXTE DE L'ELEMENT, jamais dans "
                  "le texte global de la page / Start position within the ELEMENT text",
    )
    fin_dans_element = models.PositiveIntegerField(
        help_text="Position de fin DANS LE TEXTE DE L'ELEMENT / End position within the ELEMENT text",
    )
    etat_ancrage = models.CharField(
        max_length=16,
        choices=EtatAncrage.choices,
        default=EtatAncrage.ANCREE,
        help_text="Resultat du dernier calcul de position / Result of the last positioning pass",
    )

    class Meta:
        ordering = ["extraction", "ordre_dans_extraction"]
        verbose_name = "Ancrage d'extraction"
        verbose_name_plural = "Ancrages d'extraction"
        constraints = [
            # DEFERRABLE, pour la meme raison que sur ElementDocument :
            # quand une scission coupe une portion en deux, il faut
            # decaler de +1 le numero de toutes les portions suivantes de
            # la meme extraction. Un decalage ligne a ligne fait
            # forcement se telescoper deux numeros en chemin.
            # / Deferred for the same reason: shifting portion numbers by
            # +1 necessarily collides mid-way.
            models.UniqueConstraint(
                fields=["extraction", "ordre_dans_extraction"],
                name="unicite_ordre_dans_l_extraction",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]

    def __str__(self):
        return (
            f"AncrageExtraction #{self.pk} — extraction {self.extraction_id} "
            f"portion {self.ordre_dans_extraction} — element {self.element_id}"
        )

    def texte_de_la_portion(self) -> str:
        """
        Relit le texte de cette portion depuis l'element, a la demande.
        / Reads this portion's text from the element, on demand.

        LOCALISATION : hypostasis_extractor/models.py

        On ne stocke PAS le texte de la portion. On le relit a chaque fois
        depuis l'element. Ainsi, si l'element est corrige, on ne garde pas
        une vieille copie du texte qui dirait le contraire de l'original.
        / The portion text is never stored, always re-read from the element.

        :return: Le texte de la portion / The portion text
        """
        return self.element.texte[self.debut_dans_element:self.fin_dans_element]
