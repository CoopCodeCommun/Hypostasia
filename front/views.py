import difflib
import hashlib
import itertools
import json
import logging
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Case, Count, Prefetch, Value, When
from django.utils import timezone
from django.utils.html import escape, strip_tags
from django.db.models import Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.template.loader import render_to_string
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import AIModel, Configuration, Dossier, DossierPartage, GroupeUtilisateurs, Invitation, Page, PageEdit, Question, ReponseQuestion, TranscriptionConfig, VisibiliteDossier
from hypostasis_extractor.models import (
    AnalyseurSyntaxique, AnalyseurExample, CommentaireExtraction,
    ExampleExtraction, ExtractionAttribute,
    ExtractedEntity, ExtractionJob, PromptPiece,
)
from django.contrib.auth.models import User as AuthUser
from .serializers import (
    ChangerVisibiliteSerializer,
    CommentaireExtractionSerializer, DossierCreateSerializer,
    DossierPartageSerializer, DossierRenommerSerializer,
    EditerBlocSerializer,
    ExtractionManuelleSerializer, ExtractionSerializer,
    GroupeAjouterMembreSerializer, GroupeCreateSerializer,
    ImportFichierSerializer, InviterEmailSerializer,
    ModifierTitrePageSerializer,
    PageClasserSerializer, PromouvoirEntrainementSerializer,
    QuestionSerializer, RenommerLocuteurSerializer, ReponseQuestionSerializer,
    RunAnalyseSerializer,
    SelectModelSerializer,
    SupprimerBlocSerializer, SynthetiserSerializer,
    est_fichier_audio, est_fichier_json,
)
from .utils import annoter_html_avec_barres

logger = logging.getLogger(__name__)

# Seuil de consensus par defaut (pourcentage d'entites consensuelles)
# / Default consensus threshold (percentage of consensual entities)
SEUIL_CONSENSUS_DEFAUT = 80


def _exiger_authentification(request):
    """
    Verifie que l'utilisateur est authentifie pour les operations d'ecriture.
    Retourne None si OK, ou une HttpResponse 403/redirect si non authentifie.
    Pour les requetes HTMX : renvoie un HX-Trigger pour afficher un toast SweetAlert.
    / Checks user is authenticated for write ops. Returns None or 403/redirect.
    / For HTMX requests: returns an HX-Trigger to show a SweetAlert toast.

    LOCALISATION : front/views.py
    """
    if request.user.is_authenticated:
        return None
    if request.headers.get("HX-Request"):
        reponse = HttpResponse(status=403)
        reponse["HX-Trigger"] = json.dumps({
            "authRequise": {
                "titre": "Connexion requise",
                "message": "Connectez-vous pour effectuer cette action.",
                "url_login": "/auth/login/",
            }
        })
        return reponse
    return redirect("/auth/login/")


def _utilisateur_a_acces_dossier(utilisateur, dossier):
    """
    Verifie si un utilisateur a acces en lecture a un dossier.
    Public → tout le monde. Owner → oui. Legacy (owner=None) → tout authentifie.
    Partage direct ou via groupe → oui. Sinon → non.
    / Checks if a user has read access to a folder.
    Public → everyone. Owner → yes. Legacy (owner=None) → any authenticated.
    Direct or group share → yes. Otherwise → no.

    LOCALISATION : front/views.py

    FLUX :
    1. Dossier public → True pour tous (y compris anonymes)
    2. Owner → True
    3. Legacy (owner=None) → True pour tout authentifie
    4. Partage direct (DossierPartage.utilisateur) → True
    5. Partage via groupe (DossierPartage.groupe.membres) → True
    6. Sinon → False
    """
    if dossier is None:
        return False

    # Superuser → acces a tous les dossiers (PHASE-25d-v2)
    # / Superuser → access to all folders (PHASE-25d-v2)
    if utilisateur and utilisateur.is_authenticated and utilisateur.is_superuser:
        return True

    # Dossier public → accessible a tous (y compris anonymes)
    # / Public folder → accessible to all (including anonymous)
    if dossier.visibilite == VisibiliteDossier.PUBLIC:
        return True

    # Owner du dossier → toujours acces
    # / Folder owner → always access
    if utilisateur and utilisateur.is_authenticated and dossier.owner == utilisateur:
        return True

    # Legacy (owner=None) → tout utilisateur authentifie a acces
    # / Legacy (owner=None) → any authenticated user has access
    if dossier.owner is None and utilisateur and utilisateur.is_authenticated:
        return True

    # Partage direct (DossierPartage.utilisateur)
    # / Direct share (DossierPartage.utilisateur)
    if utilisateur and utilisateur.is_authenticated:
        partage_direct_existe = DossierPartage.objects.filter(
            dossier=dossier, utilisateur=utilisateur,
        ).exists()
        if partage_direct_existe:
            return True

        # Partage via groupe (DossierPartage.groupe.membres)
        # / Share via group (DossierPartage.groupe.membres)
        partage_groupe_existe = DossierPartage.objects.filter(
            dossier=dossier, groupe__membres=utilisateur,
        ).exists()
        if partage_groupe_existe:
            return True

    return False


def _utilisateur_peut_ecrire_dossier(utilisateur, dossier):
    """
    Verifie si un utilisateur peut ecrire dans un dossier.
    L'ecriture exige : authentification + etre owner, partage direct ou via groupe.
    Un dossier public est lisible par tous mais inscriptible seulement par
    le proprietaire et les invites (partage direct ou groupe).
    / Checks if a user can write to a folder.
    / Writing requires: authentication + being owner, direct share or group share.
    / A public folder is readable by all but writable only by owner and invitees.

    LOCALISATION : front/views.py
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return False
    if dossier is None:
        return False

    # Owner du dossier → toujours ecriture
    # / Folder owner → always write
    if dossier.owner == utilisateur:
        return True

    # Legacy (owner=None) → tout utilisateur authentifie peut ecrire
    # / Legacy (owner=None) → any authenticated user can write
    if dossier.owner is None:
        return True

    # Partage direct (DossierPartage.utilisateur)
    # / Direct share (DossierPartage.utilisateur)
    partage_direct_existe = DossierPartage.objects.filter(
        dossier=dossier, utilisateur=utilisateur,
    ).exists()
    if partage_direct_existe:
        return True

    # Partage via groupe (DossierPartage.groupe.membres)
    # / Share via group (DossierPartage.groupe.membres)
    partage_groupe_existe = DossierPartage.objects.filter(
        dossier=dossier, groupe__membres=utilisateur,
    ).exists()
    if partage_groupe_existe:
        return True

    return False


def _est_proprietaire_dossier(utilisateur, page):
    """
    Verifie si l'utilisateur est le proprietaire du dossier contenant la page.
    / Checks if the user is the owner of the folder containing the page.

    LOCALISATION : front/views.py
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return False
    if not page.dossier:
        return False
    return page.dossier.owner == utilisateur


def _peut_supprimer_extraction(utilisateur, entite):
    """
    Verifie si un utilisateur peut supprimer une extraction.
    Conditions : authentifie, statut nouveau (pas commente), aucun commentaire,
    et (owner du dossier OU contributeur qui a cree l'extraction).
    Logique consolidee suite au retrait de _peut_editer_extraction (A.8 Phase 4-bis).
    / Checks if a user can delete an extraction.
    / Conditions: authenticated, status nouveau (not commente), no comments,
    / and (folder owner OR contributor who created the extraction).
    / Logic consolidated after _peut_editer_extraction removal (A.8 Phase 4-bis).

    LOCALISATION : front/views.py
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return False
    if entite.statut_debat != "nouveau":
        return False
    if CommentaireExtraction.objects.filter(entity=entite).exists():
        return False
    # Owner du dossier → peut supprimer toute extraction
    # / Folder owner → can delete any extraction
    if _est_proprietaire_dossier(utilisateur, entite.job.page):
        return True
    # Contributeur → peut supprimer uniquement ses propres extractions manuelles
    # / Contributor → can only delete their own manual extractions
    if entite.cree_par == utilisateur and _utilisateur_peut_ecrire_dossier(utilisateur, entite.job.page.dossier):
        return True
    return False


def _reponse_acces_refuse(request):
    """
    Construit la reponse 403 — toast SweetAlert pour HTMX, template complet sinon.
    / Builds the 403 response — SweetAlert toast for HTMX, full template otherwise.

    LOCALISATION : front/views.py
    """
    # Requete HTMX → toast SweetAlert via HX-Trigger
    # / HTMX request → SweetAlert toast via HX-Trigger
    if request.headers.get("HX-Request"):
        reponse = HttpResponse(status=403)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {
                "message": "Acc\u00e8s r\u00e9serv\u00e9 au propri\u00e9taire du dossier.",
                "icon": "warning",
            }
        })
        return reponse
    # Acces direct (F5 ou URL) → template complet avec navigation
    # / Direct access (F5 or URL) → full template with navigation
    return render(request, "front/acces_refuse.html", status=403)


def _verifier_acces_page(request, page):
    """
    Verifie l'acces en lecture a une page via son dossier.
    Retourne None si OK, ou HttpResponse 403 si acces refuse.
    Page sans dossier : accessible uniquement par son owner.
    / Checks read access to a page via its folder.
    Returns None if OK, or HttpResponse 403 if access denied.
    Page without folder: accessible only by its owner.

    LOCALISATION : front/views.py

    DEPENDENCIES :
    - _utilisateur_a_acces_dossier() pour la verification du dossier
    - _reponse_acces_refuse() pour la reponse 403
    """
    if page.dossier:
        if _utilisateur_a_acces_dossier(request.user, page.dossier):
            return None
        return _reponse_acces_refuse(request)

    # Page sans dossier → accessible par son owner ou legacy (owner=None)
    # / Page without folder → accessible by owner or legacy (owner=None)
    if page.owner is None:
        if request.user.is_authenticated:
            return None
        return _reponse_acces_refuse(request)
    if request.user.is_authenticated and page.owner == request.user:
        return None
    return _reponse_acces_refuse(request)


def _obtenir_ou_creer_dossier_imports(utilisateur):
    """
    Retourne (ou cree) le dossier "Mes imports" pour l'utilisateur.
    Appel idempotent : si le dossier existe deja, on le retourne tel quel.
    / Returns (or creates) the "Mes imports" folder for the user.
    Idempotent: if the folder already exists, returns it as-is.

    LOCALISATION : front/views.py
    """
    dossier_imports, _cree = Dossier.objects.get_or_create(
        name="Mes imports", owner=utilisateur,
    )
    return dossier_imports


def _render_arbre(request):
    """
    Helper interne — renvoie le partial HTML de l'arbre de dossiers.
    3 sections : Mes dossiers, Partages avec moi, Dossiers publics.
    Anonyme : uniquement les dossiers publics.
    / Internal helper — returns the folder tree HTML partial.
    3 sections: My folders, Shared with me, Public folders.
    Anonymous: only public folders.
    """
    # Exclure les restitutions de l'arbre (ne montrer que les pages racines)
    # / Exclude restitutions from tree (only show root pages)
    pages_racines_seulement = Prefetch(
        "pages",
        queryset=Page.objects.filter(parent_page__isnull=True),
    )

    if request.user.is_authenticated:
        # Mes dossiers : owner=moi ou legacy (owner=null)
        # / My folders: owner=me or legacy (owner=null)
        mes_dossiers = Dossier.objects.prefetch_related(
            pages_racines_seulement,
        ).filter(
            Q(owner=request.user) | Q(owner__isnull=True)
        ).distinct()

        # Dossiers partages avec moi (direct ou via groupe), excluant mes propres dossiers
        # / Folders shared with me (direct or via group), excluding my own folders
        ids_dossiers_partages_directs = DossierPartage.objects.filter(
            utilisateur=request.user,
        ).values_list("dossier_id", flat=True)
        ids_dossiers_partages_groupe = DossierPartage.objects.filter(
            groupe__membres=request.user,
        ).values_list("dossier_id", flat=True)

        dossiers_partages = Dossier.objects.prefetch_related(
            pages_racines_seulement,
        ).select_related("owner").filter(
            Q(pk__in=ids_dossiers_partages_directs) | Q(pk__in=ids_dossiers_partages_groupe)
        ).exclude(
            Q(owner=request.user) | Q(owner__isnull=True)
        ).distinct()

        # Dossiers publics (tous, avec owner affiche) — exclut les partages
        # / Public folders (all, with owner displayed) — excludes shared
        dossiers_publics = Dossier.objects.prefetch_related(
            pages_racines_seulement,
        ).select_related("owner").filter(
            visibilite=VisibiliteDossier.PUBLIC,
        ).exclude(
            Q(owner=request.user) | Q(owner__isnull=True)
        ).exclude(
            pk__in=ids_dossiers_partages_directs,
        ).exclude(
            pk__in=ids_dossiers_partages_groupe,
        ).distinct()
    else:
        # Anonyme : uniquement les dossiers publics
        # / Anonymous: only public folders
        mes_dossiers = Dossier.objects.none()
        dossiers_partages = Dossier.objects.none()
        dossiers_publics = Dossier.objects.prefetch_related(
            pages_racines_seulement,
        ).select_related("owner").filter(
            visibilite=VisibiliteDossier.PUBLIC,
        )

    # Calculer le total de pages par section pour affichage dans les headers
    # / Calculate total pages per section for display in headers
    total_pages_mes_dossiers = 0
    for dossier_comptage in mes_dossiers:
        total_pages_mes_dossiers += dossier_comptage.pages.count()
    total_pages_partages = 0
    for dossier_comptage in dossiers_partages:
        total_pages_partages += dossier_comptage.pages.count()
    total_pages_publics = 0
    for dossier_comptage in dossiers_publics:
        total_pages_publics += dossier_comptage.pages.count()

    return render(request, "front/includes/arbre_dossiers.html", {
        "mes_dossiers": mes_dossiers,
        "dossiers_partages": dossiers_partages,
        "dossiers_publics": dossiers_publics,
        "total_pages_mes_dossiers": total_pages_mes_dossiers,
        "total_pages_partages": total_pages_partages,
        "total_pages_publics": total_pages_publics,
    })


def _annoter_entites_avec_commentaires(queryset_entites):
    """
    Annote un queryset d'entites avec le nombre de commentaires.
    Retourne (queryset_annote, set_ids_commentees).
    / Annotate entity queryset with comment count.
    Returns (annotated_queryset, set_of_commented_ids).
    """
    entites_annotees = queryset_entites.annotate(
        nombre_commentaires=Count("commentaires"),
    )
    ids_commentees = set(
        entites_annotees.filter(nombre_commentaires__gt=0).values_list("pk", flat=True)
    )
    return entites_annotees, ids_commentees


def _get_ia_active():
    """
    Helper — retourne True si l'IA est activee dans la configuration singleton.
    Helper — returns True if AI is enabled in singleton configuration.
    """
    return Configuration.get_solo().ai_active


def _diff_inline_mots(texte_ancien, texte_nouveau):
    """
    Compare deux textes mot par mot et retourne deux HTML :
    - html_ancien avec <del> sur les mots supprimes
    - html_nouveau avec <ins> sur les mots ajoutes
    Les textes sont echappes pour eviter les XSS.
    / Compare two texts word by word and return two HTMLs:
    - html_ancien with <del> on removed words
    - html_nouveau with <ins> on added words
    Texts are escaped to prevent XSS.
    """
    mots_anciens = texte_ancien.split()
    mots_nouveaux = texte_nouveau.split()
    matcher = difflib.SequenceMatcher(None, mots_anciens, mots_nouveaux)

    fragments_ancien = []
    fragments_nouveau = []

    # Parcourir les operations diff et construire les fragments HTML
    # / Iterate over diff operations and build HTML fragments
    for operation, i1, i2, j1, j2 in matcher.get_opcodes():
        if operation == "equal":
            texte_egal = escape(" ".join(mots_anciens[i1:i2]))
            fragments_ancien.append(texte_egal)
            fragments_nouveau.append(texte_egal)
        elif operation == "replace":
            fragments_ancien.append(
                '<del class="bg-red-200 text-red-800 no-underline rounded px-0.5">'
                + escape(" ".join(mots_anciens[i1:i2]))
                + "</del>"
            )
            fragments_nouveau.append(
                '<ins class="bg-green-200 text-green-800 no-underline rounded px-0.5">'
                + escape(" ".join(mots_nouveaux[j1:j2]))
                + "</ins>"
            )
        elif operation == "delete":
            fragments_ancien.append(
                '<del class="bg-red-200 text-red-800 no-underline rounded px-0.5">'
                + escape(" ".join(mots_anciens[i1:i2]))
                + "</del>"
            )
        elif operation == "insert":
            fragments_nouveau.append(
                '<ins class="bg-green-200 text-green-800 no-underline rounded px-0.5">'
                + escape(" ".join(mots_nouveaux[j1:j2]))
                + "</ins>"
            )

    return " ".join(fragments_ancien), " ".join(fragments_nouveau)


def _diff_paragraphes(texte_ancien, texte_nouveau):
    """
    Compare deux textes au niveau paragraphe, puis mot-a-mot dans les paragraphes modifies.
    Retourne une liste de dicts avec cles : operation, contenu_gauche, contenu_droite.
    / Compare two texts at paragraph level, then word-by-word within modified paragraphs.
    Returns a list of dicts with keys: operation, contenu_gauche, contenu_droite.
    """
    # Gerer les textes vides ou None
    # / Handle empty or None texts
    if not texte_ancien and not texte_nouveau:
        return []

    texte_ancien = texte_ancien or ""
    texte_nouveau = texte_nouveau or ""

    # Decouper en paragraphes (double saut de ligne), filtrer les vides
    # / Split into paragraphs (double newline), filter empty ones
    paragraphes_anciens = []
    for paragraphe_candidat in texte_ancien.split("\n\n"):
        if paragraphe_candidat.strip():
            paragraphes_anciens.append(paragraphe_candidat)

    paragraphes_nouveaux = []
    for paragraphe_candidat in texte_nouveau.split("\n\n"):
        if paragraphe_candidat.strip():
            paragraphes_nouveaux.append(paragraphe_candidat)

    # Si les deux listes sont vides apres filtrage
    # / If both lists are empty after filtering
    if not paragraphes_anciens and not paragraphes_nouveaux:
        return []

    matcher = difflib.SequenceMatcher(None, paragraphes_anciens, paragraphes_nouveaux)
    resultats = []

    # Parcourir les operations diff au niveau paragraphe
    # / Iterate over paragraph-level diff operations
    for operation, i1, i2, j1, j2 in matcher.get_opcodes():
        if operation == "equal":
            for paragraphe in paragraphes_anciens[i1:i2]:
                resultats.append({
                    "operation": "equal",
                    "contenu_gauche": escape(paragraphe),
                    "contenu_droite": escape(paragraphe),
                })
        elif operation == "replace":
            # Aligner les paires de paragraphes, remplir les manquants avec ""
            # / Align paragraph pairs, fill missing ones with ""
            paires = itertools.zip_longest(
                paragraphes_anciens[i1:i2],
                paragraphes_nouveaux[j1:j2],
                fillvalue="",
            )
            for para_ancien, para_nouveau in paires:
                if not para_ancien:
                    # Paragraphe insere (pas de correspondant a gauche)
                    # / Inserted paragraph (no left counterpart)
                    resultats.append({
                        "operation": "insert",
                        "contenu_gauche": "",
                        "contenu_droite": escape(para_nouveau),
                    })
                elif not para_nouveau:
                    # Paragraphe supprime (pas de correspondant a droite)
                    # / Deleted paragraph (no right counterpart)
                    resultats.append({
                        "operation": "delete",
                        "contenu_gauche": escape(para_ancien),
                        "contenu_droite": "",
                    })
                else:
                    # Les deux paragraphes existent → diff mot-a-mot
                    # / Both paragraphs exist → word-level diff
                    html_ancien, html_nouveau = _diff_inline_mots(para_ancien, para_nouveau)
                    resultats.append({
                        "operation": "replace",
                        "contenu_gauche": html_ancien,
                        "contenu_droite": html_nouveau,
                    })
        elif operation == "delete":
            for paragraphe in paragraphes_anciens[i1:i2]:
                resultats.append({
                    "operation": "delete",
                    "contenu_gauche": escape(paragraphe),
                    "contenu_droite": "",
                })
        elif operation == "insert":
            for paragraphe in paragraphes_nouveaux[j1:j2]:
                resultats.append({
                    "operation": "insert",
                    "contenu_gauche": "",
                    "contenu_droite": escape(paragraphe),
                })

    return resultats


# Delai maximum d'inactivite d'un job avant de le considerer comme bloque.
# Si updated_at n'a pas bouge depuis ce delai, le job est marque en erreur.
# / Maximum inactivity delay for a job before considering it stalled.
# / If updated_at hasn't changed for this delay, the job is marked as error.
DELAI_MAX_INACTIVITE_JOB = timedelta(minutes=5)


def _verifier_et_nettoyer_job_bloque(job_en_cours):
    """
    Verifie si un job en cours est bloque (pas de progression depuis DELAI_MAX_INACTIVITE_JOB).
    Si bloque → marque le job en erreur et retourne True.
    Si actif → retourne False.
    / Checks if an in-progress job is stalled (no progress for DELAI_MAX_INACTIVITE_JOB).
    / If stalled → marks the job as error and returns True.
    / If active → returns False.

    LOCALISATION : front/views.py
    """
    if not job_en_cours:
        return True

    inactivite_du_job = timezone.now() - job_en_cours.updated_at
    if inactivite_du_job > DELAI_MAX_INACTIVITE_JOB:
        logger.warning(
            "_verifier_et_nettoyer_job_bloque: job pk=%s inactif depuis %s — timeout",
            job_en_cours.pk, inactivite_du_job,
        )
        job_en_cours.status = "error"
        job_en_cours.error_message = (
            f"Timeout : l'analyse est bloquée depuis {DELAI_MAX_INACTIVITE_JOB.total_seconds() // 60:.0f} "
            "minutes sans progression. Vérifiez que le worker Celery tourne."
        )
        job_en_cours.save(update_fields=["status", "error_message"])
        return True

    return False


def _entites_deja_creees_pour_job(job):
    """
    Retourne les entites deja creees pour un job en cours.
    Sert a les afficher quand l'utilisateur rouvre le drawer pendant une analyse.
    / Returns entities already created for an in-progress job.
    / Used to display them when the user reopens the drawer during an analysis.
    """
    return ExtractedEntity.objects.filter(
        job=job,
    ).select_related("job").order_by("start_char")


def _calculer_consensus(page):
    """
    Calcule des stats binaires de debat pour une page :
    - total : nombre d'extractions visibles (non masquees)
    - commentees : nombre d'extractions avec au moins 1 commentaire
    - non_commentees : difference
    - pourcentage : ratio commentees/total en %

    / Computes binary debate stats for a page:
    - total : number of visible (non-hidden) extractions
    - commentees : number of extractions with at least 1 comment
    - non_commentees : difference
    - pourcentage : commentees/total ratio in %

    LOCALISATION : front/views.py
    """
    entites_visibles = ExtractedEntity.objects.filter(
        job__page=page, masquee=False,
    )
    total = entites_visibles.count()
    commentees = entites_visibles.filter(statut_debat="commente").count()
    return {
        "total": total,
        "commentees": commentees,
        "non_commentees": total - commentees,
        "pourcentage": int(100 * commentees / total) if total else 0,
    }


class ConfigurationIAViewSet(viewsets.ViewSet):
    """
    ViewSet pour la configuration IA (toggle on/off, selection du modele).
    ViewSet for AI configuration (toggle on/off, model selection).
    """

    @action(detail=False, methods=["GET"])
    def status(self, request):
        """
        Retourne le partial HTML du bouton IA + audio (pour HTMX).
        / Returns the AI + audio button HTML partial (for HTMX).
        """
        configuration = Configuration.get_solo()
        modeles_actifs = AIModel.objects.filter(is_active=True)
        config_transcription_active = TranscriptionConfig.objects.filter(is_active=True).first()
        return render(request, "front/includes/config_ia_toggle.html", {
            "configuration": configuration,
            "modeles_actifs": modeles_actifs,
            "config_transcription": config_transcription_active,
        })

    @action(detail=False, methods=["POST"])
    def toggle(self, request):
        """
        Active ou desactive l'IA. Si plusieurs modeles actifs et activation → renvoie un select.
        Toggle AI on/off. If multiple active models and enabling → return a select.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        configuration = Configuration.get_solo()
        modeles_actifs = AIModel.objects.filter(is_active=True)

        if configuration.ai_active:
            # Desactivation / Deactivate
            configuration.ai_active = False
            configuration.ai_model = None
            configuration.save()
        else:
            # Activation / Activate
            if modeles_actifs.count() == 1:
                # Un seul modele actif → activation directe
                # Single active model → direct activation
                configuration.ai_active = True
                configuration.ai_model = modeles_actifs.first()
                configuration.save()
            elif modeles_actifs.count() > 1:
                # Plusieurs modeles → on ne fait rien, le partial affiche le select
                # Multiple models → do nothing, partial shows the select
                pass
            else:
                # Aucun modele actif → on ne peut pas activer
                # No active model → cannot activate
                pass

        # Re-fetch apres modification / Re-fetch after modification
        configuration = Configuration.get_solo()
        return render(request, "front/includes/config_ia_toggle.html", {
            "configuration": configuration,
            "modeles_actifs": modeles_actifs,
        })

    @action(detail=False, methods=["POST"], url_path="select-model")
    def select_model(self, request):
        """
        Selectionne un modele IA et active l'IA.
        Select an AI model and enable AI.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        serializer = SelectModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        modele_choisi = get_object_or_404(
            AIModel, pk=serializer.validated_data["model_id"], is_active=True
        )
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = modele_choisi
        configuration.save()

        modeles_actifs = AIModel.objects.filter(is_active=True)
        return render(request, "front/includes/config_ia_toggle.html", {
            "configuration": configuration,
            "modeles_actifs": modeles_actifs,
        })


class BibliothequeViewSet(viewsets.ViewSet):
    """
    Page racine — shell 3 colonnes.
    Root page — 3-column shell.
    """

    def list(self, request):
        # Requete HTMX → retourne l'onboarding comme contenu par defaut
        # / HTMX request → return onboarding as default content
        if request.headers.get('HX-Request'):
            return render(request, "front/includes/onboarding_vide.html")

        # Acces direct → page complete
        # / Direct access → full page
        return render(request, "front/bibliotheque.html", {
            "ia_active": _get_ia_active(),
        })


class ArbreViewSet(viewsets.ViewSet):
    """
    Partial HTMX — arbre de dossiers + pages orphelines.
    HTMX partial — folder tree + orphan pages.
    """

    def list(self, request):
        return _render_arbre(request)


class LectureViewSet(viewsets.ViewSet):
    """
    Partial HTMX — zone de lecture d'une page + action analyse.
    HTMX partial — reading zone for a page + analyze action.
    """
    permission_classes = [permissions.AllowAny]

    def retrieve(self, request, pk=None):
        """
        Lecture d'une page.
        - Requete HTMX → partial lecture_principale + panneau analyse en OOB
        - Acces direct (F5) → page complete base.html avec lecture pre-chargee

        Quand c'est une requete HTMX, on renvoie deux morceaux de HTML :
        1. Le contenu de lecture (qui remplace #zone-lecture)
        2. Le panneau d'analyse en OOB swap (qui remplace #panneau-extractions)
        Ca permet de mettre a jour le panneau droit sans JS.
        """
        page = get_object_or_404(Page, pk=pk)

        # Verifier l'acces en lecture a la page via son dossier
        # / Check read access to the page via its folder
        refus_acces = _verifier_acces_page(request, page)
        if refus_acces:
            return refus_acces

        # Marquage 'notification lue' si parametres presents (refonte A.6)
        # Le lien dropdown passe ?marquer_lue=X&type=analyse|synthese|transcription
        # ("analyse" et "synthese" pointent tous deux sur ExtractionJob)
        # / Mark notification as read if query params present (A.6 refactor)
        # / Dropdown link passes ?marquer_lue=X&type=analyse|synthese|transcription
        # / ("analyse" and "synthese" both point to ExtractionJob)
        marquer_lue = request.query_params.get("marquer_lue")
        type_tache = request.query_params.get("type")
        if marquer_lue and type_tache in ("analyse", "synthese", "extraction", "transcription"):
            try:
                if type_tache == "transcription":
                    from core.models import TranscriptionJob
                    TranscriptionJob.objects.filter(
                        pk=marquer_lue, page__owner=request.user,
                    ).update(notification_lue=True)
                else:
                    ExtractionJob.objects.filter(
                        pk=marquer_lue, page__owner=request.user,
                    ).update(notification_lue=True)
            except (ValueError, TypeError):
                # marquer_lue n'est pas un entier valide, ignorer silencieusement
                # / marquer_lue is not a valid integer, ignore silently
                pass

        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")

        # Verifier si un job est en cours pour cette page
        # Si oui, renvoyer le panneau d'analyse en cours avec les entites deja trouvees
        # / Check if a job is currently running for this page
        # / If so, return the in-progress analysis panel with already found entities
        job_en_cours = ExtractionJob.objects.filter(
            page=page,
            status__in=["pending", "processing"],
        ).order_by("-created_at").first()

        if job_en_cours:
            job_est_bloque = _verifier_et_nettoyer_job_bloque(job_en_cours)
            if not job_est_bloque:
                # Job actif → utiliser le panneau en cours au lieu du panneau standard
                # / Active job → use the in-progress panel instead of the standard one
                return self._retrieve_avec_job_en_cours(request, page, job_en_cours, analyseurs_actifs)

        # Recupere le dernier job d'extraction termine pour cette page
        # pour afficher les resultats existants dans le panneau droit
        dernier_job_termine = ExtractionJob.objects.filter(
            page=page,
            status="completed",
        ).select_related("analyseur_version").order_by("-created_at").first()

        # Pour les pages audio avec transcription_raw, regenerer le HTML diarise
        # afin de garantir les data attributes PHASE-15 (fonds pales, data-speaker, etc.)
        # / For audio pages with transcription_raw, regenerate diarized HTML
        # to ensure PHASE-15 data attributes (pale backgrounds, data-speaker, etc.)
        if page.source_type == "audio" and page.transcription_raw:
            from .services.transcription_audio import construire_html_diarise
            html_diarise_regenere, texte_brut_regenere = construire_html_diarise(
                page.transcription_raw,
            )
            if html_diarise_regenere:
                page.html_readability = html_diarise_regenere
                page.text_readability = texte_brut_regenere
                page.save(update_fields=["html_readability", "text_readability"])

        # Si un job existe, on recupere les entites de TOUS les jobs termines
        # (pas seulement le dernier) pour etre coherent avec le drawer E.
        # / If a job exists, retrieve entities from ALL completed jobs
        # / (not just the last one) to be consistent with the E drawer.
        entites_existantes = None
        html_annote = None
        ids_entites_commentees = set()
        if dernier_job_termine:
            tous_les_jobs_de_la_page = ExtractionJob.objects.filter(
                page=page, status="completed",
            )
            toutes_entites_non_masquees = ExtractedEntity.objects.filter(
                job__in=tous_les_jobs_de_la_page, masquee=False,
            )
            entites_existantes, ids_entites_commentees = _annoter_entites_avec_commentaires(
                toutes_entites_non_masquees
            )
            # Annoter le HTML avec des ancres pour le scroll-to-extraction
            # / Annotate HTML with anchors for scroll-to-extraction
            html_annote = annoter_html_avec_barres(
                page.html_readability, page.text_readability,
                entites_existantes, ids_entites_commentees,
            )

        # Recupere toutes les versions de cette page (racine + restitutions)
        # / Retrieve all versions of this page (root + restitutions)
        toutes_les_versions = page.toutes_les_versions
        page_racine = page.page_racine

        # Widgets audio : filtre locuteurs + timeline (PHASE-15)
        # / Audio widgets: speaker filter + timeline (PHASE-15)
        html_filtre_locuteurs = ""
        html_timeline = ""
        if page.source_type == "audio" and page.transcription_raw:
            from .services.transcription_audio import construire_widgets_audio
            html_filtre_locuteurs, html_timeline = construire_widgets_audio(
                page.transcription_raw, entites_extraction=entites_existantes,
            )

        # Contexte commun pour les deux partials (HTMX et F5).
        # est_requete_htmx sert a conditionner les blocs OOB dans les templates.
        # est_proprietaire conditionne l'affichage des boutons reserves au proprio
        # (supprimer une version, masquer/restaurer extractions, etc.).
        # / Common context for both partials (HTMX and F5).
        # / est_proprietaire conditions display of owner-only buttons.
        ia_active = _get_ia_active()
        est_requete_htmx = bool(request.headers.get('HX-Request'))
        est_proprietaire = _est_proprietaire_dossier(request.user, page)
        contexte_partage = {
            "page": page,
            "html_annote": html_annote,
            "analyseurs_actifs": analyseurs_actifs,
            "job": dernier_job_termine,
            "entities": entites_existantes,
            "ia_active": ia_active,
            "versions": toutes_les_versions,
            "page_racine": page_racine,
            "html_filtre_locuteurs": html_filtre_locuteurs,
            "html_timeline": html_timeline,
            "est_requete_htmx": est_requete_htmx,
            "est_proprietaire": est_proprietaire,
        }

        if request.headers.get('HX-Request'):
            # 1. Partial principal : contenu de lecture
            html_lecture = render_to_string(
                "front/includes/lecture_principale.html",
                contexte_partage,
                request=request,
            )

            # 2. Partial OOB : panneau d'analyse injecte dans le sidebar droit
            # Le hx-swap-oob="innerHTML:#panneau-extractions" dit a HTMX :
            # "remplace le contenu de #panneau-extractions avec ce HTML"
            html_panneau_analyse = render_to_string(
                "front/includes/panneau_analyse.html",
                contexte_partage,
                request=request,
            )
            html_panneau_oob = (
                '<div id="panneau-extractions" hx-swap-oob="innerHTML:#panneau-extractions">'
                + html_panneau_analyse
                + '</div>'
            )

            # On concatene les deux morceaux : HTMX traite l'OOB automatiquement
            html_complet = html_lecture + html_panneau_oob
            return HttpResponse(html_complet)

        # Acces direct (F5) → page complete avec le panneau pre-charge
        # On passe aussi le job, les entites et le HTML annote
        # Determiner si l'utilisateur est proprietaire du dossier pour les controles UI
        # / Determine if user is the folder owner for UI controls
        est_proprietaire = _est_proprietaire_dossier(request.user, page)

        return render(request, "front/base.html", {
            "page_preloaded": page,
            "html_annote": html_annote,
            "analyseurs_actifs": analyseurs_actifs,
            "job": dernier_job_termine,
            "entities": entites_existantes,
            "ia_active": ia_active,
            "versions": toutes_les_versions,
            "page_racine": page_racine,
            "html_filtre_locuteurs": html_filtre_locuteurs,
            "html_timeline": html_timeline,
            "est_proprietaire": est_proprietaire,
        })

    def _retrieve_avec_job_en_cours(self, request, page, job_en_cours, analyseurs_actifs):
        """
        Rendu de la page quand un job d'extraction est en cours.
        Affiche le texte brut (sans annotations) + le panneau en cours avec
        les entites deja extraites par le callback Celery.
        / Page render when an extraction job is in progress.
        / Shows raw text (no annotations) + in-progress panel with
        / entities already extracted by the Celery callback.
        """
        # Recuperer les entites deja creees par le callback Celery
        # / Retrieve entities already created by the Celery callback
        entites_deja_creees = _entites_deja_creees_pour_job(job_en_cours)

        # Annoter le texte avec les entites deja trouvees (annotations partielles)
        # / Annotate text with already found entities (partial annotations)
        html_annote = None
        if entites_deja_creees.exists():
            html_annote = annoter_html_avec_barres(
                page.html_readability or '',
                page.text_readability or '',
                list(entites_deja_creees),
            )

        # Versions de la page / Page versions
        toutes_les_versions = page.toutes_les_versions
        page_racine = page.page_racine

        # Widgets audio (PHASE-15) / Audio widgets (PHASE-15)
        html_filtre_locuteurs = ""
        html_timeline = ""
        if page.source_type == "audio" and page.transcription_raw:
            from .services.transcription_audio import construire_widgets_audio
            html_filtre_locuteurs, html_timeline = construire_widgets_audio(
                page.transcription_raw,
            )

        ia_active = _get_ia_active()
        est_requete_htmx = bool(request.headers.get('HX-Request'))

        contexte_lecture = {
            "page": page,
            "html_annote": html_annote,
            "analyseurs_actifs": analyseurs_actifs,
            "job": None,
            "entities": None,
            "ia_active": ia_active,
            "versions": toutes_les_versions,
            "page_racine": page_racine,
            "html_filtre_locuteurs": html_filtre_locuteurs,
            "html_timeline": html_timeline,
            "est_requete_htmx": est_requete_htmx,
        }

        if est_requete_htmx:
            # Refonte A.6 : plus de drawer "analyse en cours" en OOB. On rend
            # uniquement le partial de lecture avec les annotations partielles
            # deja appliquees, et un toast HX-Trigger informe l'utilisateur.
            # Le bouton "taches" dans la toolbar le notifiera quand l'analyse
            # sera terminee.
            # / A.6 refactor: no more "in-progress" drawer via OOB. We only render
            # / the reading partial with partial annotations already applied,
            # / and an HX-Trigger toast informs the user. The "tasks" button
            # / in the toolbar will notify them when analysis completes.
            html_lecture = render_to_string(
                "front/includes/lecture_principale.html",
                contexte_lecture,
                request=request,
            )
            reponse = HttpResponse(html_lecture)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Analyse en cours pour cette page.",
                    "icon": "info",
                },
            })
            return reponse

        # Acces direct (F5) → page complete
        # / Direct access (F5) → full page
        est_proprietaire = _est_proprietaire_dossier(request.user, page)
        return render(request, "front/base.html", {
            "page_preloaded": page,
            "html_annote": html_annote,
            "analyseurs_actifs": analyseurs_actifs,
            "job": None,
            "entities": None,
            "ia_active": ia_active,
            "versions": toutes_les_versions,
            "page_racine": page_racine,
            "html_filtre_locuteurs": html_filtre_locuteurs,
            "html_timeline": html_timeline,
            "est_proprietaire": est_proprietaire,
            "job_en_cours": job_en_cours,
            "entites_deja_creees": entites_deja_creees,
        })

    @action(detail=True, methods=["POST"], url_path="modifier_titre")
    def modifier_titre(self, request, pk=None):
        """
        Modifie le titre d'une page (edition inline).
        Retourne le partial lecture_principale mis a jour.
        / Modifies a page's title (inline editing).
        Returns the updated lecture_principale partial.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        page = get_object_or_404(Page, pk=pk)

        # Validation via serializer DRF
        # / Validation via DRF serializer
        serializer_titre = ModifierTitrePageSerializer(data=request.data)
        serializer_titre.is_valid(raise_exception=True)
        nouveau_titre = serializer_titre.validated_data["nouveau_titre"]

        # Capturer le titre avant modification pour l'historique
        # / Capture old title before modification for history
        ancien_titre = page.title or ""

        # Mise a jour du titre de la page
        # / Update the page title
        page.title = nouveau_titre
        page.save(update_fields=["title"])
        logger.info("modifier_titre: page pk=%s titre='%s'", page.pk, nouveau_titre)

        # Enregistrer l'edition dans l'historique (PHASE-27a)
        # / Record the edit in history (PHASE-27a)
        description_edition_titre = f"Titre changé : '{ancien_titre}' → '{nouveau_titre}'"
        PageEdit.objects.create(
            page=page,
            user=request.user if request.user.is_authenticated else None,
            type_edit="titre",
            description=description_edition_titre[:500],
            donnees_avant={"titre": ancien_titre},
            donnees_apres={"titre": nouveau_titre},
        )

        # Rendu du partial de lecture (meme logique que retrieve)
        # / Render reading partial (same logic as retrieve)
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")
        dernier_job_termine = ExtractionJob.objects.filter(
            page=page, status="completed",
        ).select_related("analyseur_version").order_by("-created_at").first()

        entites_existantes = None
        html_annote = None
        ids_entites_commentees = set()
        if dernier_job_termine:
            # Entites de TOUS les jobs termines (coherent avec le drawer E)
            # / Entities from ALL completed jobs (consistent with the E drawer)
            tous_les_jobs_page = ExtractionJob.objects.filter(page=page, status="completed")
            toutes_entites = ExtractedEntity.objects.filter(job__in=tous_les_jobs_page, masquee=False)
            entites_existantes, ids_entites_commentees = _annoter_entites_avec_commentaires(
                toutes_entites
            )
            html_annote = annoter_html_avec_barres(
                page.html_readability, page.text_readability,
                entites_existantes, ids_entites_commentees,
            )

        toutes_les_versions = page.toutes_les_versions
        contexte_partage = {
            "page": page,
            "html_annote": html_annote,
            "analyseurs_actifs": analyseurs_actifs,
            "job": dernier_job_termine,
            "entities": entites_existantes,
            "ia_active": _get_ia_active(),
            "versions": toutes_les_versions,
            "page_racine": page.page_racine,
        }

        html_lecture = render_to_string(
            "front/includes/lecture_principale.html",
            contexte_partage,
            request=request,
        )

        # OOB swap : arbre mis a jour via _render_arbre
        # / OOB swap: updated tree via _render_arbre
        reponse_arbre = _render_arbre(request)
        html_arbre_oob = (
            '<div id="arbre" hx-swap-oob="innerHTML:#arbre">'
            + reponse_arbre.content.decode()
            + '</div>'
        )

        reponse = HttpResponse(html_lecture + html_arbre_oob)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Titre modifi\u00e9"},
        })
        return reponse

    @action(detail=True, methods=["GET"], url_path="historique")
    def historique(self, request, pk=None):
        """
        Affiche l'historique des editions manuelles d'une page (PHASE-27a).
        - Requete HTMX → partial historique_page.html
        - Acces direct (F5) → page complete base.html avec historique pre-charge
        / Displays the manual edit history of a page (PHASE-27a).
        - HTMX request → historique_page.html partial
        - Direct access (F5) → full base.html page with preloaded history
        """
        page = get_object_or_404(Page, pk=pk)

        # Verifier l'acces en lecture a la page via son dossier
        # / Check read access to the page via its folder
        refus_acces = _verifier_acces_page(request, page)
        if refus_acces:
            return refus_acces

        # Recuperer tous les edits de cette page, ordonnes par date decroissante
        # / Retrieve all edits for this page, ordered by most recent first
        # Le tri est gere par PageEdit.Meta.ordering (-created_at, -pk)
        # / Ordering is handled by PageEdit.Meta.ordering (-created_at, -pk)
        tous_les_edits = PageEdit.objects.filter(page=page).select_related("user")

        toutes_les_versions = page.toutes_les_versions

        contexte_historique = {
            "page": page,
            "edits": tous_les_edits,
            "versions": toutes_les_versions,
        }

        if request.headers.get("HX-Request"):
            # Requete HTMX → partial uniquement
            # / HTMX request → partial only
            return render(request, "front/includes/historique_page.html", contexte_historique)

        # Acces direct (F5) → page complete
        # / Direct access (F5) → full page
        est_proprietaire = _est_proprietaire_dossier(request.user, page)
        return render(request, "front/base.html", {
            "historique_preloaded": True,
            "page_preloaded": page,
            "edits": tous_les_edits,
            "versions": toutes_les_versions,
            "est_proprietaire": est_proprietaire,
        })

    def destroy(self, request, pk=None):
        """
        Supprime une version d'une page (parent_page non NULL). Refuse de supprimer
        la racine. Le proprietaire du dossier seul peut supprimer.
        Apres suppression, redirige le navigateur vers la racine via HX-Location
        (qui fait un GET HTMX et swap zone-lecture).
        / Deletes a page version (parent_page non-null). Refuses to delete the root.
        / Only the folder owner can delete. Redirects via HX-Location to root.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        version_a_supprimer = get_object_or_404(Page, pk=pk)

        # Refuser la suppression de la racine via cet endpoint
        # / Refuse deletion of the root via this endpoint
        if version_a_supprimer.parent_page is None:
            reponse_refus = HttpResponse(status=400)
            reponse_refus["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Impossible de supprimer la version racine. Supprimez plutôt le document depuis l'arbre.",
                    "icon": "warning",
                },
            })
            return reponse_refus

        # Verifier ownership du dossier / Check folder ownership
        if not _est_proprietaire_dossier(request.user, version_a_supprimer):
            return _reponse_acces_refuse(request)

        # Garde-fou : ne pas supprimer si des extractions de cette version ont
        # recu des commentaires. Le travail collaboratif (commentaires) merite
        # une protection. Les extractions sans commentaires sont OK a effacer.
        # / Safeguard: refuse deletion if any extraction has comments. Collaborative
        # / work (comments) deserves protection. Empty extractions are OK to wipe.
        nombre_commentaires_lies = CommentaireExtraction.objects.filter(
            entity__job__page=version_a_supprimer,
        ).count()
        if nombre_commentaires_lies > 0:
            reponse_refus_commentaires = HttpResponse(status=409)
            reponse_refus_commentaires["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": (
                        f"Impossible de supprimer cette version : {nombre_commentaires_lies} "
                        f"commentaire(s) y sont rattaché(s). "
                        f"Supprimez d'abord les commentaires, ou conservez la version pour préserver les échanges."
                    ),
                    "icon": "warning",
                },
            })
            return reponse_refus_commentaires

        page_racine = version_a_supprimer.page_racine
        nom_version = (
            version_a_supprimer.version_label or f"V{version_a_supprimer.version_number}"
        )
        logger.info(
            "destroy version: pk=%s racine=%s par user=%s",
            pk, page_racine.pk, request.user.username,
        )
        version_a_supprimer.delete()

        # Rediriger vers la racine via HX-Location (HTMX swap automatique)
        # / Redirect to root via HX-Location (automatic HTMX swap)
        reponse = HttpResponse(status=200)
        reponse["HX-Location"] = json.dumps({
            "path": f"/lire/{page_racine.pk}/",
            "target": "#zone-lecture",
            "swap": "innerHTML",
        })
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {
                "message": f"Version « {nom_version} » supprimée.",
                "icon": "success",
            },
        })
        return reponse

    @action(detail=True, methods=["GET"], url_path="comparer")
    def comparer(self, request, pk=None):
        """
        Affiche le diff side-by-side entre deux versions d'une page (PHASE-27b).
        - ?v2={pk2} pour specifier la version droite
        - Sans v2 → compare avec la version parent
        - Requete HTMX → partial diff_versions_pages.html
        - Acces direct (F5) → page complete base.html avec diff pre-charge
        / Displays the side-by-side diff between two page versions (PHASE-27b).
        - ?v2={pk2} to specify the right version
        - Without v2 → compare with the parent version
        - HTMX request → diff_versions_pages.html partial
        - Direct access (F5) → full base.html page with preloaded diff
        """
        page_gauche = get_object_or_404(Page, pk=pk)

        # Verifier l'acces en lecture a la page
        # / Check read access to the page
        refus_acces = _verifier_acces_page(request, page_gauche)
        if refus_acces:
            return refus_acces

        # Determiner la version droite : v2 explicite ou parent
        # / Determine the right version: explicit v2 or parent
        pk_version_droite = request.query_params.get("v2")
        if pk_version_droite:
            page_droite = get_object_or_404(Page, pk=pk_version_droite)

            # Verifier que les deux pages sont dans la meme chaine de versions
            # / Verify both pages are in the same version chain
            if page_gauche.page_racine.pk != page_droite.page_racine.pk:
                return HttpResponse(
                    '<div class="p-8 text-center text-slate-500">'
                    "Ces deux pages ne font pas partie de la même chaîne de versions."
                    "</div>",
                    status=400,
                )
        else:
            # Fallback : parent (si V2+) ou premiere restitution (si V1)
            # / Fallback: parent (if V2+) or first child restitution (if V1)
            page_droite = page_gauche.parent_page
            if page_droite is None:
                page_droite = page_gauche.versions_enfants.order_by("version_number").first()

        # Si pas de version a comparer (page unique sans parent ni enfant)
        # / If no version to compare (single page without parent or child)
        if page_droite is None:
            return HttpResponse(
                '<div class="p-8 text-center text-slate-500">'
                "Pas d'autre version à comparer."
                "</div>",
            )

        # Ordonner : version_number le plus petit a gauche
        # / Order: smallest version_number on the left
        if page_gauche.version_number > page_droite.version_number:
            page_gauche, page_droite = page_droite, page_gauche

        # Calculer le diff paragraphe par paragraphe
        # / Compute the paragraph-level diff
        resultats_diff = _diff_paragraphes(
            page_gauche.text_readability,
            page_droite.text_readability,
        )

        # Recuperer toutes les versions pour les selecteurs
        # / Retrieve all versions for the selectors
        toutes_les_versions = page_gauche.toutes_les_versions

        # La page d'origine est celle de l'URL (pk) — c'est la page que
        # l'utilisateur lisait avant d'appuyer Z. On la passe au template
        # pour que le bouton "Retour" ramene a la bonne page.
        # / The origin page is the URL one (pk) — the page the user
        # / was reading before pressing Z. We pass it to the template
        # / so the "Back" button returns to the right page.
        page_origine = get_object_or_404(Page, pk=pk)

        contexte_diff = {
            "page_gauche": page_gauche,
            "page_droite": page_droite,
            "page_origine": page_origine,
            "resultats_diff": resultats_diff,
            "versions": toutes_les_versions,
        }

        if request.headers.get("HX-Request"):
            # Requete HTMX → partial uniquement
            # / HTMX request → partial only
            return render(request, "front/includes/diff_versions_pages.html", contexte_diff)

        # Acces direct (F5) → page complete
        # / Direct access (F5) → full page
        est_proprietaire = _est_proprietaire_dossier(request.user, page_gauche)
        return render(request, "front/base.html", {
            "diff_preloaded": True,
            "page_gauche": page_gauche,
            "page_droite": page_droite,
            "resultats_diff": resultats_diff,
            "versions": toutes_les_versions,
            "est_proprietaire": est_proprietaire,
        })

    @action(detail=True, methods=["GET"], url_path="comparer_hypostases")
    def comparer_hypostases(self, request, pk=None):
        """
        Affiche l'alignement des hypostases entre deux versions (onglet dans le diff).
        GET /lire/{pk}/comparer_hypostases/?v2={pk2}
        Vue HTMX-only : si acces direct (F5/lien partage), redirige vers la vue
        comparer parente qui affiche l'onglet correctement.
        / Displays the hypostase alignment between two versions (tab in the diff).
        / HTMX-only: on direct access (F5/shared link), redirect to the parent
        / comparer view that displays the tab correctly.
        """
        # Acces direct (F5) → rediriger vers le diff comparer
        # / Direct access (F5) → redirect to the parent comparer view
        if not request.headers.get("HX-Request"):
            pk_v2 = request.query_params.get("v2")
            if pk_v2:
                return redirect(f"/lire/{pk}/comparer/?v2={pk_v2}")
            return redirect(f"/lire/{pk}/")

        from front.views_alignement import construire_alignement_versions

        page_gauche = get_object_or_404(Page, pk=pk)

        # Verifier l'acces en lecture a la page
        # / Check read access to the page
        refus_acces = _verifier_acces_page(request, page_gauche)
        if refus_acces:
            return refus_acces

        # Recuperer la version droite
        # / Retrieve the right version
        pk_version_droite = request.query_params.get("v2")
        if not pk_version_droite:
            return HttpResponse(
                '<div class="p-8 text-center text-slate-500">'
                "Paramètre v2 requis pour comparer les hypostases."
                "</div>",
                status=400,
            )

        page_droite = get_object_or_404(Page, pk=pk_version_droite)

        # Verifier que les deux pages sont dans la meme chaine de versions
        # / Verify both pages are in the same version chain
        if page_gauche.page_racine.pk != page_droite.page_racine.pk:
            return HttpResponse(
                '<div class="p-8 text-center text-slate-500">'
                "Ces deux pages ne font pas partie de la même chaîne de versions."
                "</div>",
                status=400,
            )

        # Ordonner : version_number le plus petit a gauche
        # / Order: smallest version_number on the left
        if page_gauche.version_number > page_droite.version_number:
            page_gauche, page_droite = page_droite, page_gauche

        # Construire l'alignement des hypostases entre les 2 versions
        # / Build the hypostase alignment between the 2 versions
        contexte_alignement = construire_alignement_versions(page_gauche, page_droite)

        return render(request, "front/includes/alignement_versions.html", contexte_alignement)

    @action(detail=True, methods=["GET"], url_path="telecharger_source")
    def telecharger_source(self, request, pk=None):
        """
        Telecharge la source originale de la page selon son type.
        - audio + source_file → FileResponse du fichier audio
        - audio sans source_file → transcription_raw en JSON
        - file + source_file → FileResponse du document
        - web → html_original en .html
        / Downloads the original source of the page based on its type.
        """
        page = get_object_or_404(Page, pk=pk)

        if page.source_type == "audio":
            if page.source_file:
                # Renvoyer le fichier audio original
                # / Return the original audio file
                nom_telechargement = page.original_filename or "audio.mp3"
                return FileResponse(
                    page.source_file.open("rb"),
                    as_attachment=True,
                    filename=nom_telechargement,
                )
            elif page.transcription_raw:
                # Pas de fichier source → renvoyer le JSON brut de la transcription
                # / No source file → return raw transcription JSON
                contenu_json = json.dumps(page.transcription_raw, ensure_ascii=False, indent=2)
                nom_fichier_json = f"{page.title or 'transcription'}.json"
                reponse = HttpResponse(contenu_json, content_type="application/json")
                reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier_json}"'
                return reponse
            else:
                return HttpResponse("Aucune source disponible.", status=404)

        elif page.source_type == "file":
            if page.source_file:
                # Renvoyer le document original
                # / Return the original document
                nom_telechargement = page.original_filename or "document"
                return FileResponse(
                    page.source_file.open("rb"),
                    as_attachment=True,
                    filename=nom_telechargement,
                )
            else:
                return HttpResponse("Aucune source disponible.", status=404)

        elif page.source_type == "web":
            # Renvoyer le HTML original de la page web
            # / Return the original HTML of the web page
            nom_fichier_html = f"{page.title or 'page'}.html"
            reponse = HttpResponse(page.html_original, content_type="text/html; charset=utf-8")
            reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier_html}"'
            return reponse

        return HttpResponse("Type de source inconnu.", status=400)

    @action(detail=True, methods=["GET"], url_path="exporter")
    def exporter(self, request, pk=None):
        """
        Exporte le contenu d'une page en JSON ou Markdown.
        Query param : ?type_export=json|markdown
        ('format' est reserve par DRF pour la negociation de contenu)
        / Exports a page's content as JSON or Markdown.
        """
        page = get_object_or_404(Page, pk=pk)
        format_export = request.query_params.get("type_export", "markdown")

        if page.source_type == "audio":
            if format_export == "json":
                # Renvoyer transcription_raw en JSON telechargeable (re-importable)
                # / Return transcription_raw as downloadable JSON (re-importable)
                donnees_export = page.transcription_raw or {"segments": []}
                contenu_json = json.dumps(donnees_export, ensure_ascii=False, indent=2)
                nom_fichier = f"{page.title or 'transcription'}.json"
                reponse = HttpResponse(contenu_json, content_type="application/json")
                reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
                return reponse
            else:
                # Markdown : construire [Locuteur HH:MM]\nTexte depuis les segments
                # / Markdown: build [Speaker HH:MM]\nText from segments
                donnees_transcription = page.transcription_raw or {}
                liste_segments = donnees_transcription.get("segments", [])
                lignes_markdown = [f"# {page.title or 'Transcription'}\n"]

                for segment in liste_segments:
                    locuteur = segment.get("speaker", "Inconnu")
                    debut_secondes = segment.get("start", 0)
                    # Convertir les secondes en HH:MM:SS
                    # / Convert seconds to HH:MM:SS
                    heures = int(debut_secondes // 3600)
                    minutes = int((debut_secondes % 3600) // 60)
                    secondes = int(debut_secondes % 60)
                    horodatage = f"{heures:02d}:{minutes:02d}:{secondes:02d}"
                    texte_segment = segment.get("text", "").strip()
                    lignes_markdown.append(f"**[{locuteur} {horodatage}]**")
                    lignes_markdown.append(f"{texte_segment}\n")

                contenu_markdown = "\n".join(lignes_markdown)
                nom_fichier = f"{page.title or 'transcription'}.md"
                reponse = HttpResponse(contenu_markdown, content_type="text/markdown; charset=utf-8")
                reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
                return reponse

        else:
            # Pages web ou documents : export Markdown du texte lisible
            # / Web pages or documents: Markdown export of readable text
            contenu_markdown = f"# {page.title or 'Document'}\n\n{page.text_readability}"
            nom_fichier = f"{page.title or 'document'}.md"
            reponse = HttpResponse(contenu_markdown, content_type="text/markdown; charset=utf-8")
            reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
            return reponse

    @action(detail=False, methods=["GET"])
    def aide(self, request):
        """
        Renvoie la modale d'aide adaptee au contexte (mobile ou desktop).
        Le contenu est un template Django modifiable en HTML.
        / Returns the help modal adapted to the context (mobile or desktop).
        Content is a Django template editable in HTML.
        """
        # Detecter le contexte mobile via le query param ou le User-Agent
        # / Detect mobile context via query param or User-Agent
        est_mobile = request.GET.get("mobile") == "1"

        if est_mobile:
            return render(request, "front/includes/aide_mobile.html")

        # Desktop : passer la liste des raccourcis clavier
        # / Desktop: pass the keyboard shortcuts list
        liste_raccourcis = [
            ("T", "Ouvrir/fermer la biblioth\u00e8que"),
            ("E", "Ouvrir/fermer le panneau extractions"),
            ("J", "Extraction suivante"),
            ("K", "Extraction pr\u00e9c\u00e9dente"),
            ("C", "Commenter l\u2019extraction s\u00e9lectionn\u00e9e"),
            ("S", "Marquer consensuelle"),
            ("X", "Masquer l\u2019extraction"),
            ("A", "Comparer / Aligner des pages"),
            ("Z", "Comparer les versions"),
            ("?", "Afficher cette aide"),
            ("Esc", "Fermer le panneau actif"),
        ]
        return render(request, "front/includes/aide_desktop.html", {
            "raccourcis": liste_raccourcis,
        })

    @action(detail=True, methods=["GET"], url_path="previsualiser_analyse")
    def previsualiser_analyse(self, request, pk=None):
        """
        Construit le prompt complet (pieces + exemples + texte source) et retourne
        un partial de confirmation avec : estimation tokens, cout, bouton voir prompt.
        Si un job est deja en cours → renvoie le template de polling directement.
        Si le dernier job est en erreur → affiche l'erreur avec possibilite de relancer.
        / Builds the full prompt and returns a confirmation partial.
        / If a job is already running → returns the polling template directly.
        / If the last job errored → shows the error with option to re-launch.
        """
        page = get_object_or_404(Page, pk=pk)

        # Acces direct (F5) → rediriger vers la page de lecture
        # Cette vue ne sert que comme partial HTMX, pas en acces direct
        # / Direct access (F5) → redirect to reading page
        # / This view only serves as an HTMX partial, not for direct access
        if not request.headers.get("HX-Request"):
            return redirect(f"/lire/{pk}/")

        # Verifier si un job est deja en cours ET actif pour cette page.
        # Si le job est bloque → le marquer en erreur et afficher la confirmation.
        # / Check if a job is already running AND active for this page.
        # / If stalled → mark as error and show the confirmation.
        job_en_cours = ExtractionJob.objects.filter(
            page=page,
            status__in=["pending", "processing"],
        ).order_by("-created_at").first()

        if job_en_cours:
            job_est_bloque = _verifier_et_nettoyer_job_bloque(job_en_cours)
            if not job_est_bloque:
                # Refonte A.6 : plus de drawer "analyse en cours". On renvoie un
                # toast informant l'utilisateur que l'analyse tourne deja, et
                # le bouton "taches" de la toolbar le notifiera a la fin.
                # / A.6 refactor: no more "in-progress" drawer. We send a toast
                # / telling the user analysis is already running; the toolbar
                # / "tasks" button will notify them when it completes.
                reponse = HttpResponse(status=200)
                reponse["HX-Trigger"] = json.dumps({
                    "showToast": {
                        "message": "Analyse deja en cours pour cette page.",
                        "icon": "info",
                    },
                })
                return reponse
            # Job bloque → continuer vers la confirmation pour relancer
            # / Stalled job → continue to confirmation to relaunch

        # Recupere l'analyseur depuis le query param, ou le premier actif par defaut
        # / Get analyzer from query param, or the first active one by default
        analyseur_id = request.GET.get("analyseur_id")
        if analyseur_id:
            analyseur = get_object_or_404(AnalyseurSyntaxique, pk=analyseur_id)
        else:
            analyseur = AnalyseurSyntaxique.objects.filter(
                is_active=True, type_analyseur="analyser",
            ).first()
            if not analyseur:
                reponse = HttpResponse(status=400)
                reponse["HX-Trigger"] = json.dumps({
                    "showToast": {"message": "Aucun analyseur actif. Configurez-en un dans /api/analyseurs/.", "icon": "error"},
                })
                return reponse

        # Tous les analyseurs actifs de type "analyser" pour le selecteur
        # / All active analyzers of type "analyser" for the selector
        tous_les_analyseurs_actifs = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="analyser",
        ).order_by("name")

        # Recupere le modele IA actif depuis la configuration singleton
        # / Get active AI model from singleton configuration
        configuration_ia = Configuration.get_solo()
        modele_ia_actif = configuration_ia.ai_model
        if not modele_ia_actif:
            reponse = HttpResponse(status=400)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Aucun mod\u00e8le IA configur\u00e9. Ajoutez une cl\u00e9 API dans .env (GOOGLE_API_KEY, OPENAI_API_KEY...) puis relancez install.sh.",
                    "icon": "error",
                },
            })
            return reponse

        # Construit le prompt complet en utilisant le meme pipeline que tasks.py.
        # On instancie le QAPromptGenerator de LangExtract pour obtenir l'overhead exact
        # (description + exemples formattés en JSON) envoye a chaque chunk.
        # / Builds the full prompt using the same pipeline as tasks.py.
        # / We instantiate LangExtract's QAPromptGenerator to get the exact overhead
        # / (description + JSON-formatted examples) sent with each chunk.
        import tiktoken
        import math
        import langextract.prompting as prompting_lx
        from langextract.core import data as data_lx, format_handler as fh_lx
        from hypostasis_extractor.services import _construire_exemples_langextract

        # Pieces de prompt concatenees (description envoyee au LLM)
        # / Prompt pieces concatenated (description sent to the LLM)
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        segments_contenu_prompt = []
        for piece in pieces_ordonnees:
            segments_contenu_prompt.append(piece.content)
        texte_prompt_pieces = "\n".join(segments_contenu_prompt)

        # Exemples few-shot au format LangExtract (identique a tasks.py)
        # / Few-shot examples in LangExtract format (same as tasks.py)
        tous_les_exemples = AnalyseurExample.objects.filter(
            analyseur=analyseur,
        ).order_by("order").prefetch_related("extractions__attributes")
        liste_exemples_langextract = _construire_exemples_langextract(analyseur)

        # Construire le PromptTemplate + QAPromptGenerator identique a tasks.py
        # / Build PromptTemplate + QAPromptGenerator identical to tasks.py
        modele_prompt = prompting_lx.PromptTemplateStructured(
            description=texte_prompt_pieces,
        )
        modele_prompt.examples.extend(liste_exemples_langextract)

        handler_format, _ = fh_lx.FormatHandler.from_resolver_params(
            resolver_params={},
            base_format_type=data_lx.FormatType.JSON,
            base_use_fences=False,
            base_attribute_suffix=data_lx.ATTRIBUTE_SUFFIX,
            base_use_wrapper=True,
            base_wrapper_key=data_lx.EXTRACTIONS_KEY,
        )
        generateur_prompt = prompting_lx.QAPromptGenerator(
            template=modele_prompt,
            format_handler=handler_format,
        )

        # Overhead = prompt complet SANS le texte a analyser (question vide).
        # C'est exactement ce que le LLM recoit en plus du texte de chaque chunk.
        # / Overhead = full prompt WITHOUT the text to analyze (empty question).
        # / This is exactly what the LLM receives on top of each chunk's text.
        prompt_overhead_reel = generateur_prompt.render(question="")

        # Texte source de la page (sera envoye au LLM, reparti en chunks)
        # / Source text from the page (will be sent to the LLM, split in chunks)
        texte_source_page = page.text_readability or ""

        # Prompt complet pour l'affichage (overhead + texte source)
        # / Full prompt for display (overhead + source text)
        prompt_complet = generateur_prompt.render(question=texte_source_page)

        # --- Estimation precise des tokens ---
        # Le LLM recoit pour chaque chunk : prompt_overhead + texte_du_chunk.
        # Donc : tokens_input_total = N_chunks × tokens(overhead) + tokens(texte_total).
        # On utilise tiktoken (cl100k_base) comme approximation — le tokenizer reel
        # varie selon le modele (Gemini, GPT, etc.) mais l'ecart est < 10%.
        # / --- Precise token estimation ---
        # / The LLM receives for each chunk: prompt_overhead + chunk_text.
        # / So: total_input_tokens = N_chunks × tokens(overhead) + tokens(total_text).
        # / We use tiktoken (cl100k_base) as approximation — the real tokenizer
        # / varies by model (Gemini, GPT, etc.) but the gap is < 10%.
        encodeur_tokens = tiktoken.get_encoding("cl100k_base")

        tokens_overhead_par_chunk = len(encodeur_tokens.encode(prompt_overhead_reel))
        tokens_texte_source = len(encodeur_tokens.encode(texte_source_page))

        # Nombre de chunks estimes (langextract coupe aux frontieres de phrases,
        # mais on approxime avec un decoupage brut par taille de buffer)
        # / Estimated chunk count (langextract cuts at sentence boundaries,
        # / but we approximate with raw buffer size division)
        taille_max_chunk = 1500
        nombre_chunks_estime = max(1, math.ceil(len(texte_source_page) / taille_max_chunk))

        # Total input = overhead repete N fois + texte source (reparti sur les chunks)
        # / Total input = overhead repeated N times + source text (spread across chunks)
        nombre_tokens_input = (nombre_chunks_estime * tokens_overhead_par_chunk) + tokens_texte_source

        # Estimation du nombre de tokens output visible (50% de l'input).
        # Mesure reelle sur 18 extractions : 52% — on arrondit a 50%.
        # / Estimate visible output token count (50% of input).
        # / Real measurement on 18 extractions: 52% — rounded to 50%.
        nombre_tokens_output_visible = int(nombre_tokens_input * 0.50)

        # Certains modeles (Gemini 2.5 Flash/Pro) ont un mode "thinking" qui genere
        # des tokens de reflexion internes. Ces tokens sont factures au tarif output
        # mais ne sont pas visibles dans la reponse.
        # / Some models (Gemini 2.5 Flash/Pro) have a "thinking" mode that generates
        # / internal reasoning tokens. These are billed at output rate but not visible.
        multiplicateur_thinking = modele_ia_actif.multiplicateur_thinking()
        nombre_tokens_thinking = nombre_tokens_output_visible * (multiplicateur_thinking - 1)
        nombre_tokens_output_total = nombre_tokens_output_visible + nombre_tokens_thinking

        # Estimation du cout en euros — on passe le total output (visible + thinking)
        # Marge x1.5 arrondi au centime superieur pour absorber les variations
        # (marge reduite car le thinking est deja une surestimation conservatrice)
        # / Cost estimate in euros — pass total output (visible + thinking)
        # / x1.5 margin rounded up to next cent to absorb variations
        # / (reduced margin since thinking is already a conservative overestimate)
        cout_brut_euros = modele_ia_actif.estimer_cout_euros(
            nombre_tokens_input, nombre_tokens_output_total
        )
        cout_estime_euros = max(0.01, math.ceil(cout_brut_euros * 1.5 * 100) / 100)

        # Compter les entites IA sans commentaires pour proposer le nettoyage
        # avant re-analyse (eviter les doublons)
        # / Count AI entities without comments to offer cleanup
        # / before re-analysis (avoid duplicates)
        entites_ia_sans_commentaires = ExtractedEntity.objects.filter(
            job__page=page,
            job__status="completed",
            cree_par__isnull=True,
            masquee=False,
        ).exclude(
            commentaires__isnull=False,
        ).count()

        return render(request, "front/includes/confirmation_analyse.html", {
            "page": page,
            "analyseur": analyseur,
            "analyseurs_actifs": tous_les_analyseurs_actifs,
            "modele_ia": modele_ia_actif,
            "nombre_tokens_input": nombre_tokens_input,
            "nombre_tokens_output_visible": nombre_tokens_output_visible,
            "nombre_tokens_thinking": nombre_tokens_thinking,
            "nombre_tokens_output_total": nombre_tokens_output_total,
            "multiplicateur_thinking": multiplicateur_thinking,
            "cout_estime_euros": cout_estime_euros,
            "prompt_complet": prompt_complet,
            "nombre_exemples": tous_les_exemples.count(),
            "nombre_pieces": pieces_ordonnees.count(),
            "nombre_chunks_estime": nombre_chunks_estime,
            "tokens_overhead_par_chunk": tokens_overhead_par_chunk,
            "nombre_entites_ia_sans_commentaires": entites_ia_sans_commentaires,
        })

    @action(detail=True, methods=["POST"])
    def analyser(self, request, pk=None):
        """
        Lance une extraction LangExtract asynchrone sur une page via Celery.
        - Si un job est deja en cours → renvoie le template de polling (pas de re-lancement)
        - Sinon → cree un ExtractionJob, lance la tache Celery, renvoie le polling
        / Launches an async LangExtract extraction on a page via Celery.
        - If a job is already running → returns polling template (no re-launch)
        - Otherwise → creates ExtractionJob, launches Celery task, returns polling
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        # Guard : verifie que l'IA est activee / Check AI is enabled
        if not _get_ia_active():
            reponse = HttpResponse(status=400)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "IA non activ\u00e9e. Configurez un mod\u00e8le dans /api/analyseurs/ ou ajoutez une cl\u00e9 API dans .env.",
                    "icon": "warning",
                },
            })
            return reponse

        page = get_object_or_404(Page, pk=pk)

        # Verifier les droits d'ecriture sur le dossier de la page
        # / Check write permissions on the page's folder
        if page.dossier and not _utilisateur_peut_ecrire_dossier(request.user, page.dossier):
            return _reponse_acces_refuse(request)

        # Guard anti-doublon : verifier s'il y a deja un job en cours pour cette page
        # / Anti-duplicate guard: check if a job is already running for this page
        job_en_cours = ExtractionJob.objects.filter(
            page=page,
            status__in=["pending", "processing"],
        ).order_by("-created_at").first()

        if job_en_cours:
            # Un job est deja en cours → toast d'info, pas de drawer (refonte A.6)
            # L'utilisateur sera notifie via le bouton "taches" dans la toolbar.
            # / A job is already running → info toast, no drawer (A.6 refactor)
            # / The user will be notified via the "tasks" button in the toolbar.
            logger.info("analyser: job deja en cours pk=%s pour page=%s", job_en_cours.pk, pk)
            reponse = HttpResponse(status=200)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Une analyse est deja en cours pour cette page.",
                    "icon": "info",
                },
                "fermerDrawer": {},
                "tachesChanged": {},
            })
            return reponse

        # Si analyseur_id n'est pas fourni, utiliser le premier analyseur actif de type "analyser"
        # / If analyseur_id is not provided, use the first active analyzer of type "analyser"
        donnees_requete = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if not donnees_requete.get("analyseur_id"):
            analyseur_par_defaut = AnalyseurSyntaxique.objects.filter(
                is_active=True, type_analyseur="analyser",
            ).first()
            if not analyseur_par_defaut:
                return render(request, "front/includes/extraction_results.html", {
                    "error_message": "Aucun analyseur actif trouvé. Configurez un analyseur via /api/analyseurs/.",
                })
            donnees_requete["analyseur_id"] = analyseur_par_defaut.pk

        # Validation via serializer DRF sur request.data (form-data envoye par HTMX)
        # / Validation via DRF serializer on request.data (form-data sent by HTMX)
        serializer = RunAnalyseSerializer(data=donnees_requete)
        if not serializer.is_valid():
            logger.warning("analyser: validation echouee — %s", serializer.errors)
            return render(request, "front/includes/extraction_results.html", {
                "error_message": str(serializer.errors),
            })

        analyseur = get_object_or_404(
            AnalyseurSyntaxique, pk=serializer.validated_data["analyseur_id"]
        )

        # Utiliser le modele selectionne dans la configuration singleton (sidebar)
        # / Use the model selected in the singleton configuration (sidebar)
        configuration_ia = Configuration.get_solo()
        ai_model_actif = configuration_ia.ai_model
        if not ai_model_actif:
            return render(request, "front/includes/extraction_results.html", {
                "error_message": "Aucun modele IA selectionne. Choisissez un modele dans la sidebar.",
            })

        # Nettoyage des entites IA sans commentaires si demande (checkbox)
        # Supprime les extractions IA non commentees pour eviter les doublons
        # Les extractions manuelles (cree_par != NULL) et commentees sont conservees
        # / Cleanup AI entities without comments if requested (checkbox)
        # / Deletes uncommented AI extractions to avoid duplicates
        # / Manual extractions (cree_par != NULL) and commented ones are kept
        nettoyer_ia = request.data.get("nettoyer_ia") == "1"
        if nettoyer_ia:
            entites_ia_a_supprimer = ExtractedEntity.objects.filter(
                job__page=page,
                job__status="completed",
                cree_par__isnull=True,
                masquee=False,
            ).exclude(
                commentaires__isnull=False,
            )
            nombre_supprimees = entites_ia_a_supprimer.count()
            entites_ia_a_supprimer.delete()
            if nombre_supprimees:
                logger.info(
                    "analyser: %d entite(s) IA sans commentaire supprimee(s) pour page=%s",
                    nombre_supprimees, pk,
                )

        # Construire le prompt snapshot depuis les pieces de l'analyseur
        # / Build prompt snapshot from the analyzer's prompt pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        prompt_snapshot = "\n".join(piece.content for piece in pieces_ordonnees)

        # Creer le job d'extraction en status PENDING (l'analyseur_id suffit,
        # la tache Celery reconstruira les exemples depuis la DB)
        # / Create extraction job in PENDING status (analyseur_id is enough,
        # the Celery task will rebuild examples from DB)
        job_extraction = ExtractionJob.objects.create(
            page=page,
            ai_model=ai_model_actif,
            name=f"Analyseur: {analyseur.name}",
            prompt_description=prompt_snapshot,
            status="pending",
            raw_result={
                "analyseur_id": analyseur.pk,
            },
        )

        # Lancer la tache Celery en arriere-plan
        # / Launch the Celery task in background
        from front.tasks import analyser_page_task
        analyser_page_task.delay(job_extraction.pk)

        logger.info(
            "analyser: job pk=%s cree pour page=%s analyseur=%s — tache Celery lancee",
            job_extraction.pk, pk, analyseur.name,
        )

        # Refonte A.6 : retour d'un simple toast HX-Trigger au lieu du drawer
        # "en cours". L'utilisateur garde la page intacte, le bouton "taches"
        # dans la toolbar le notifiera quand l'analyse est terminee.
        # / A.6 refactor: return a simple HX-Trigger toast instead of the
        # / "in-progress" drawer. The page stays intact, the "tasks" button
        # / in the toolbar will notify the user when analysis is complete.
        reponse = HttpResponse(status=200)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {
                "message": "Analyse lancee. Vous serez notifie a la fin.",
                "icon": "info",
            },
            "fermerDrawer": {},
            "tachesChanged": {},
        })
        return reponse

    @action(detail=True, methods=["GET"], url_path="previsualiser_synthese")
    def previsualiser_synthese(self, request, pk=None):
        """
        Construit le contexte de confirmation pour la synthese deliberative
        et renvoie le partial confirmation_synthese.html dans #drawer-contenu.
        Si un job de synthese est deja en cours \u2192 renvoie le partial polling.
        / Builds the confirmation context for deliberative synthesis
        / and returns confirmation_synthese.html in #drawer-contenu.
        / If a synthesis job is running \u2192 returns the polling partial.
        """
        page = get_object_or_404(Page, pk=pk)

        # Acces direct (F5) \u2192 rediriger vers la lecture / Direct access (F5) \u2192 redirect
        if not request.headers.get("HX-Request"):
            return redirect(f"/lire/{pk}/")

        # Verifier si un job de synthese est deja en cours
        # / Check if a synthesis job is already running
        job_synthese_en_cours = ExtractionJob.objects.filter(
            page=page,
            status__in=["pending", "processing"],
            raw_result__contains={"est_synthese": True},
        ).order_by("-created_at").first()
        if job_synthese_en_cours:
            # Refonte A.6 : plus de drawer "synthese en cours". On envoie un toast
            # informant que la synthese tourne deja, et le bouton "taches" de la
            # toolbar la signalera quand elle sera terminee.
            # / A.6 refactor: no more "in-progress" drawer. We send a toast telling
            # / the user synthesis is already running; the toolbar "tasks" button
            # / will notify them when it completes.
            reponse = HttpResponse(status=200)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Synthese deja en cours pour cette page.",
                    "icon": "info",
                },
            })
            return reponse

        # Recuperer l'analyseur synthese (default ou ?analyseur_id=)
        # / Get the synthesis analyzer (default or ?analyseur_id=)
        analyseur_id_choisi = request.GET.get("analyseur_id")
        analyseur_synthese = None
        if analyseur_id_choisi:
            analyseur_synthese = AnalyseurSyntaxique.objects.filter(
                pk=analyseur_id_choisi, is_active=True, type_analyseur="synthetiser",
            ).first()
        if not analyseur_synthese:
            analyseur_synthese = AnalyseurSyntaxique.objects.filter(
                is_active=True, type_analyseur="synthetiser",
            ).order_by("-est_par_defaut", "name").first()
        if not analyseur_synthese:
            reponse_erreur = HttpResponse(status=400)
            reponse_erreur["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Aucun analyseur de synth\u00e8se actif. Configurez-en un dans /api/analyseurs/.",
                    "icon": "error",
                },
            })
            return reponse_erreur

        # Tous les analyseurs synthese actifs (pour le selecteur)
        # / All active synthesis analyzers (for the selector)
        tous_les_analyseurs_synthese = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="synthetiser",
        ).order_by("-est_par_defaut", "name")

        # Modele IA actif / Active AI model
        configuration_ia = Configuration.get_solo()
        modele_ia_actif = configuration_ia.ai_model
        if not modele_ia_actif:
            reponse_erreur = HttpResponse(status=400)
            reponse_erreur["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Aucun mod\u00e8le IA configur\u00e9. Ajoutez une cl\u00e9 API dans .env.",
                    "icon": "error",
                },
            })
            return reponse_erreur

        # Dernier job d'analyse complete (pour les extractions disponibles)
        # / Latest completed analysis job (for available extractions)
        dernier_job_analyse = ExtractionJob.objects.filter(
            page=page, status="completed",
        ).exclude(
            raw_result__contains={"est_synthese": True},
        ).order_by("-created_at").first()

        # Compter les extractions et commentaires disponibles
        # / Count available extractions and comments
        nombre_extractions_disponibles = 0
        nombre_commentaires_disponibles = 0
        if dernier_job_analyse:
            nombre_extractions_disponibles = ExtractedEntity.objects.filter(
                job=dernier_job_analyse, masquee=False,
            ).exclude(statut_debat="non_pertinent").count()
            nombre_commentaires_disponibles = CommentaireExtraction.objects.filter(
                entity__job=dernier_job_analyse,
            ).count()

        # Construire le prompt complet pour l'estimation et l'affichage
        # / Build the full prompt for estimation and display
        from front.tasks import _construire_prompt_synthese
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur_synthese,
        ).order_by("order")
        prompt_systeme = "\n".join(piece.content for piece in pieces_ordonnees)
        prompt_utilisateur = _construire_prompt_synthese(
            page, dernier_job_analyse, analyseur_synthese,
        )
        prompt_complet = prompt_systeme + "\n\n" + prompt_utilisateur

        # Estimation tokens (pas de chunking pour la synthese, 1 seul appel)
        # / Token estimation (no chunking for synthesis, single call)
        import tiktoken
        import math
        encodeur_tokens = tiktoken.get_encoding("cl100k_base")
        nombre_tokens_input = len(encodeur_tokens.encode(prompt_complet))
        nombre_tokens_output_visible = int(nombre_tokens_input * 0.5)
        multiplicateur_thinking = modele_ia_actif.multiplicateur_thinking()
        nombre_tokens_thinking = nombre_tokens_output_visible * (multiplicateur_thinking - 1)
        nombre_tokens_output_total = nombre_tokens_output_visible + nombre_tokens_thinking
        cout_brut_euros = modele_ia_actif.estimer_cout_euros(
            nombre_tokens_input, nombre_tokens_output_total,
        )
        cout_estime_euros = max(0.01, math.ceil(cout_brut_euros * 1.5 * 100) / 100)

        # Etat du consensus / Consensus state
        donnees_consensus = _calculer_consensus(page)

        # Conditions de blocage du bouton "Lancer"
        # / Blocking conditions for the "Launch" button
        bouton_desactive = False
        raison_desactivation = ""
        if (not analyseur_synthese.inclure_extractions
                and not analyseur_synthese.inclure_texte_original):
            bouton_desactive = True
            raison_desactivation = (
                "Configurez l'analyseur pour inclure au moins le texte original "
                "ou les extractions."
            )
        elif (analyseur_synthese.inclure_extractions
                and nombre_extractions_disponibles == 0):
            bouton_desactive = True
            raison_desactivation = (
                "Lancez d'abord une analyse pour cet analyseur, "
                "ou d\u00e9cochez \u00ab Inclure les extractions \u00bb."
            )

        contexte = {
            "page": page,
            "analyseur": analyseur_synthese,
            "analyseurs_actifs": tous_les_analyseurs_synthese,
            "modele_ia": modele_ia_actif,
            "nombre_pieces": pieces_ordonnees.count(),
            "nombre_tokens_input": nombre_tokens_input,
            "nombre_tokens_output_visible": nombre_tokens_output_visible,
            "nombre_tokens_thinking": nombre_tokens_thinking,
            "nombre_tokens_output_total": nombre_tokens_output_total,
            "multiplicateur_thinking": multiplicateur_thinking,
            "cout_estime_euros": cout_estime_euros,
            "prompt_complet": prompt_complet,
            "nombre_extractions_disponibles": nombre_extractions_disponibles,
            "nombre_commentaires_disponibles": nombre_commentaires_disponibles,
            "bouton_desactive": bouton_desactive,
            "raison_desactivation": raison_desactivation,
            "consensus": donnees_consensus,
        }

        reponse = render(request, "front/includes/confirmation_synthese.html", contexte)
        reponse["HX-Trigger"] = "ouvrirDrawer"
        return reponse

    @action(detail=True, methods=["POST"])
    def synthetiser(self, request, pk=None):
        """
        Lance une synthese deliberative asynchrone sur une page via Celery.
        Collecte texte + hypostases + commentaires + statuts, appelle un LLM,
        et cree une Page enfant (nouvelle version).
        / Launches an async deliberative synthesis on a page via Celery.
        Collects text + hypostases + comments + statuses, calls an LLM,
        and creates a child Page (new version).
        """
        # Guard : authentification / Authentication guard
        refus = _exiger_authentification(request)
        if refus:
            return refus

        # Validation via serializer DRF (vide — le pk vient de l'URL detail=True)
        # / Validation via DRF serializer (empty — pk comes from URL detail=True)
        serializer_synthese = SynthetiserSerializer(data=request.data)
        serializer_synthese.is_valid(raise_exception=True)

        # Guard : verifie que l'IA est activee / Check AI is enabled
        if not _get_ia_active():
            reponse = HttpResponse(status=400)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "IA non activée. Configurez un modèle dans /api/analyseurs/ ou ajoutez une clé API dans .env.",
                    "icon": "warning",
                },
            })
            return reponse

        page = get_object_or_404(Page, pk=pk)

        # Verifier les droits d'ecriture sur le dossier de la page
        # / Check write permissions on the page's folder
        if page.dossier and not _utilisateur_peut_ecrire_dossier(request.user, page.dossier):
            return _reponse_acces_refuse(request)

        # Guard anti-doublon : verifier s'il y a deja une synthese en cours
        # / Anti-duplicate guard: check if a synthesis is already running
        job_synthese_en_cours = ExtractionJob.objects.filter(
            page=page,
            status__in=["pending", "processing"],
            raw_result__est_synthese=True,
        ).order_by("-created_at").first()

        if job_synthese_en_cours:
            # Une synthese est deja en cours → toast d'info, pas de drawer (refonte A.6)
            # L'utilisateur sera notifie via le bouton "taches" dans la toolbar.
            # / A synthesis is already running → info toast, no drawer (A.6 refactor)
            # / The user will be notified via the "tasks" button in the toolbar.
            logger.info("synthetiser: job deja en cours pk=%s pour page=%s", job_synthese_en_cours.pk, pk)
            reponse = HttpResponse(status=200)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Une synthese est deja en cours pour cette page.",
                    "icon": "info",
                },
                "fermerDrawer": {},
                "tachesChanged": {},
            })
            return reponse

        # Trouver l'analyseur de synthese : depuis le formulaire ou le default.
        # Le bouton Lancer envoie soit `analyseur_id` (via hx-include du select
        # `name="analyseur_id"`) si plusieurs analyseurs, soit `analyseur_id` via
        # hx-vals (default rendu serveur) si un seul.
        # / Find synthesis analyzer: from form (live select) or fallback default.
        analyseur_id_choisi = request.data.get("analyseur_id")
        if analyseur_id_choisi:
            analyseur_synthese = AnalyseurSyntaxique.objects.filter(
                pk=analyseur_id_choisi, is_active=True, type_analyseur="synthetiser",
            ).first()
        else:
            analyseur_synthese = None
        if not analyseur_synthese:
            analyseur_synthese = AnalyseurSyntaxique.objects.filter(
                is_active=True, type_analyseur="synthetiser",
            ).order_by("-est_par_defaut", "name").first()
        if not analyseur_synthese:
            reponse_erreur = HttpResponse(status=400)
            reponse_erreur["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Aucun analyseur de synthèse actif. Chargez la fixture demo_ia.json.",
                    "icon": "warning",
                },
            })
            return reponse_erreur

        # Garde-fou : au moins l'un des deux contextes doit etre coche pour
        # produire un prompt utile. Sinon le LLM n'aurait que la consigne.
        # / Guard: at least one of the two context flags must be enabled,
        # otherwise the LLM would only receive the instruction.
        bool_aucun_actif = (
            not analyseur_synthese.inclure_extractions
            and not analyseur_synthese.inclure_texte_original
        )
        if bool_aucun_actif:
            reponse_erreur = HttpResponse(status=400)
            reponse_erreur["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": (
                        "L'analyseur de synthèse doit inclure au moins le texte "
                        "original ou les extractions. Activez l'un des deux dans "
                        "la configuration de l'analyseur."
                    ),
                    "icon": "warning",
                },
            })
            return reponse_erreur

        # Utiliser le modele selectionne dans la configuration singleton
        # / Use the model selected in the singleton configuration
        configuration_ia = Configuration.get_solo()
        modele_ia_actif = configuration_ia.ai_model
        if not modele_ia_actif:
            reponse_erreur = HttpResponse(status=400)
            reponse_erreur["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Aucun modèle IA sélectionné. Choisissez un modèle dans la sidebar.",
                    "icon": "warning",
                },
            })
            return reponse_erreur

        # Construire le prompt snapshot depuis les pieces de l'analyseur
        # / Build prompt snapshot from the analyzer's prompt pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur_synthese,
        ).order_by("order")
        prompt_snapshot = "\n".join(piece.content for piece in pieces_ordonnees)

        # Creer le job d'extraction en status PENDING
        # / Create extraction job in PENDING status
        job_synthese = ExtractionJob.objects.create(
            page=page,
            ai_model=modele_ia_actif,
            name="Synthèse délibérative",
            prompt_description=prompt_snapshot,
            status="pending",
            raw_result={
                "analyseur_id": analyseur_synthese.pk,
                "est_synthese": True,
            },
        )

        # Lancer la tache Celery en arriere-plan
        # / Launch the Celery task in background
        from front.tasks import synthetiser_page_task
        synthetiser_page_task.delay(job_synthese.pk)

        logger.info(
            "synthetiser: job pk=%s cree pour page=%s — tache Celery lancee",
            job_synthese.pk, pk,
        )

        # Refonte A.6 : retour d'un simple toast HX-Trigger au lieu du drawer
        # "en cours". L'utilisateur garde la page intacte, le bouton "taches"
        # dans la toolbar le notifiera quand la synthese est terminee.
        # / A.6 refactor: return a simple HX-Trigger toast instead of the
        # / "in-progress" drawer. The page stays intact, the "tasks" button
        # / in the toolbar will notify the user when synthesis is complete.
        reponse = HttpResponse(status=200)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {
                "message": "Synthese lancee. Vous serez notifie a la fin.",
                "icon": "info",
            },
            "fermerDrawer": {},
            "tachesChanged": {},
        })
        return reponse

    @action(detail=True, methods=["GET"], url_path="formulaire_renommer_locuteur")
    def formulaire_renommer_locuteur(self, request, pk=None):
        """
        Retourne le partial modal pour renommer un locuteur.
        / Returns the modal partial for renaming a speaker.
        """
        page = get_object_or_404(Page, pk=pk)
        ancien_nom = request.query_params.get("speaker", "")
        index_bloc = request.query_params.get("block_index", "0")

        return render(request, "front/includes/modal_renommer_locuteur.html", {
            "page": page,
            "ancien_nom": ancien_nom,
            "index_bloc": index_bloc,
        })

    @action(detail=True, methods=["POST"], url_path="renommer_locuteur")
    def renommer_locuteur(self, request, pk=None):
        """
        Renomme un locuteur dans la transcription (transcription_raw + html/text_readability).
        / Renames a speaker in the transcription (transcription_raw + html/text_readability).
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        from .services.transcription_audio import construire_html_diarise

        page = get_object_or_404(Page, pk=pk)

        # Valider les donnees du formulaire / Validate form data
        serializer_renommage = RenommerLocuteurSerializer(data=request.data)
        serializer_renommage.is_valid(raise_exception=True)
        donnees_validees = serializer_renommage.validated_data

        ancien_nom_locuteur = donnees_validees["ancien_nom"]
        nouveau_nom_locuteur = donnees_validees["nouveau_nom"]
        portee_renommage = donnees_validees["portee"]
        index_bloc_cible = donnees_validees.get("index_bloc", 0)

        # Charger la transcription brute / Load raw transcription
        transcription_brute = page.transcription_raw or {}
        segments_existants = transcription_brute.get("segments", [])

        if not segments_existants:
            return HttpResponse("Aucune transcription trouvee.", status=400)

        # Appliquer le renommage selon la portee
        # / Apply renaming based on scope
        if portee_renommage == "tous":
            # Renommer toutes les occurrences de ce locuteur
            # / Rename all occurrences of this speaker
            for segment in segments_existants:
                if segment.get("speaker") == ancien_nom_locuteur:
                    segment["speaker"] = nouveau_nom_locuteur
        else:
            # Reconstruire les groupes pour identifier le bloc cible
            # / Rebuild groups to identify the target block
            index_groupe_courant = -1
            index_segment_debut_bloc = None
            index_segment_fin_bloc = None
            dernier_locuteur = None

            for index_segment, segment in enumerate(segments_existants):
                nom_segment = segment.get("speaker", "Inconnu")
                if nom_segment != dernier_locuteur:
                    index_groupe_courant += 1
                    dernier_locuteur = nom_segment

                    # Quand on trouve le debut du bloc suivant, on note la fin du bloc cible
                    # / When we find the start of the next block, note the end of the target block
                    if index_segment_debut_bloc is not None and index_segment_fin_bloc is None:
                        if index_groupe_courant > index_bloc_cible and nom_segment != ancien_nom_locuteur:
                            # On est dans un nouveau groupe different — le bloc cible est termine
                            # mais on ne coupe que pour "ce_bloc_seul"
                            pass

                    if index_groupe_courant == index_bloc_cible:
                        index_segment_debut_bloc = index_segment

            # Identifier les segments du bloc cible (groupe contigu)
            # / Identify segments of the target block (contiguous group)
            if index_segment_debut_bloc is not None:
                # Trouver la fin du groupe contigu pour le bloc cible
                # / Find the end of the contiguous group for the target block
                index_segment_fin_bloc = index_segment_debut_bloc
                for index_parcours in range(index_segment_debut_bloc + 1, len(segments_existants)):
                    if segments_existants[index_parcours].get("speaker") == ancien_nom_locuteur:
                        index_segment_fin_bloc = index_parcours
                    else:
                        break

                if portee_renommage == "ce_bloc_seul":
                    # Renommer uniquement les segments du bloc contigu cible
                    # / Rename only the segments of the target contiguous block
                    for index_segment in range(index_segment_debut_bloc, index_segment_fin_bloc + 1):
                        if segments_existants[index_segment].get("speaker") == ancien_nom_locuteur:
                            segments_existants[index_segment]["speaker"] = nouveau_nom_locuteur
                else:
                    # ce_bloc_et_suivants : renommer a partir du bloc cible
                    # / ce_bloc_et_suivants: rename from the target block onward
                    for index_segment in range(index_segment_debut_bloc, len(segments_existants)):
                        if segments_existants[index_segment].get("speaker") == ancien_nom_locuteur:
                            segments_existants[index_segment]["speaker"] = nouveau_nom_locuteur

        # Sauvegarder la transcription modifiee / Save modified transcription
        transcription_brute["segments"] = segments_existants
        page.transcription_raw = transcription_brute

        # Reconstruire le HTML et le texte brut / Rebuild HTML and plain text
        html_reconstruit, texte_reconstruit = construire_html_diarise(segments_existants)
        page.html_readability = html_reconstruit
        page.text_readability = texte_reconstruit
        page.save()

        # Enregistrer l'edition dans l'historique (PHASE-27a)
        # / Record the edit in history (PHASE-27a)
        description_edition_locuteur = f"Locuteur renommé : '{ancien_nom_locuteur}' → '{nouveau_nom_locuteur}' ({portee_renommage})"
        PageEdit.objects.create(
            page=page,
            user=request.user if request.user.is_authenticated else None,
            type_edit="locuteur",
            description=description_edition_locuteur[:500],
            donnees_avant={"locuteur": ancien_nom_locuteur, "portee": portee_renommage},
            donnees_apres={"locuteur": nouveau_nom_locuteur},
        )

        # Retourner le partial de lecture mis a jour + fermer la modale
        # / Return updated reading partial + close the modal
        toutes_les_versions = page.toutes_les_versions
        page_racine = page.page_racine

        reponse_renommage = render(request, "front/includes/lecture_principale.html", {
            "page": page,
            "versions": toutes_les_versions,
            "page_racine": page_racine,
        })
        # Fermer la modale de renommage via un event HTMX
        # / Close the rename modal via an HTMX event
        reponse_renommage["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Locuteur renommé : {nouveau_nom_locuteur}"},
            "fermerModaleRenommer": True,
        })
        return reponse_renommage

    @action(detail=True, methods=["GET"], url_path="formulaire_editer_bloc")
    def formulaire_editer_bloc(self, request, pk=None):
        """
        Retourne le partial inline qui remplace le bloc de transcription par un textarea.
        Conserve l'en-tete du bloc (nom, couleur, timestamps) pour une transition naturelle.
        / Returns the inline partial that replaces the transcription block with a textarea.
        Preserves the block header (name, color, timestamps) for a natural transition.
        """
        from .services.transcription_audio import COULEURS_LOCUTEURS, _formater_timestamp

        page = get_object_or_404(Page, pk=pk)
        index_bloc = int(request.query_params.get("block_index", "0"))

        # Extraire le texte et les metadonnees du bloc cible depuis transcription_raw
        # / Extract text and metadata of the target block from transcription_raw
        transcription_brute = page.transcription_raw or {}
        segments_existants = transcription_brute.get("segments", [])

        # Reconstruire les groupes pour trouver les phrases et metadonnees du bloc cible
        # / Rebuild groups to find the target block's sentences and metadata
        index_groupe_courant = -1
        dernier_locuteur = None
        phrases_bloc_cible = []
        nom_locuteur_bloc = "Inconnu"
        timestamp_debut_bloc = 0.0
        timestamp_fin_bloc = 0.0

        # Collecter les locuteurs uniques pour calculer la couleur
        # / Collect unique speakers to compute color
        locuteurs_uniques = []

        for segment in segments_existants:
            nom_segment = segment.get("speaker", "Inconnu")
            texte_segment = segment.get("text", "").strip()
            if not texte_segment:
                continue

            # Tracking des locuteurs uniques pour l'index de couleur
            # / Track unique speakers for color index
            if nom_segment not in locuteurs_uniques:
                locuteurs_uniques.append(nom_segment)

            if nom_segment != dernier_locuteur:
                index_groupe_courant += 1
                dernier_locuteur = nom_segment

            if index_groupe_courant == index_bloc:
                phrases_bloc_cible.append(texte_segment)
                nom_locuteur_bloc = nom_segment
                if len(phrases_bloc_cible) == 1:
                    timestamp_debut_bloc = segment.get("start", 0.0)
                timestamp_fin_bloc = segment.get("end", 0.0)

        texte_bloc = "\n".join(phrases_bloc_cible)

        # Calculer le nombre de lignes pour dimensionner le textarea
        # / Calculate line count to size the textarea
        nombre_lignes = max(3, len(phrases_bloc_cible) + 1)

        # Retrouver la couleur du locuteur / Find the speaker's color
        index_couleur_locuteur = locuteurs_uniques.index(nom_locuteur_bloc) if nom_locuteur_bloc in locuteurs_uniques else 0
        couleur_locuteur = COULEURS_LOCUTEURS[index_couleur_locuteur % len(COULEURS_LOCUTEURS)]

        return render(request, "front/includes/editer_bloc_inline.html", {
            "page": page,
            "index_bloc": index_bloc,
            "texte_bloc": texte_bloc,
            "nombre_lignes": nombre_lignes,
            "nom_locuteur": nom_locuteur_bloc,
            "couleur_locuteur": couleur_locuteur,
            "timestamp_debut": _formater_timestamp(timestamp_debut_bloc),
            "timestamp_fin": _formater_timestamp(timestamp_fin_bloc),
        })

    @action(detail=True, methods=["POST"], url_path="editer_bloc")
    def editer_bloc(self, request, pk=None):
        """
        Modifie le texte d'un bloc de transcription.
        / Edits the text of a transcription block.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        from .services.transcription_audio import construire_html_diarise

        page = get_object_or_404(Page, pk=pk)

        # Valider les donnees du formulaire / Validate form data
        serializer_edition = EditerBlocSerializer(data=request.data)
        serializer_edition.is_valid(raise_exception=True)
        donnees_validees = serializer_edition.validated_data

        index_bloc_cible = donnees_validees["index_bloc"]
        nouveau_texte_brut = donnees_validees["nouveau_texte"]

        # Charger la transcription brute / Load raw transcription
        transcription_brute = page.transcription_raw or {}
        segments_existants = transcription_brute.get("segments", [])

        if not segments_existants:
            return HttpResponse("Aucune transcription trouvee.", status=400)

        # Identifier les indices des segments du bloc cible
        # / Identify segment indices of the target block
        index_groupe_courant = -1
        dernier_locuteur = None
        indices_segments_bloc = []

        for index_segment, segment in enumerate(segments_existants):
            nom_segment = segment.get("speaker", "Inconnu")
            texte_segment = segment.get("text", "").strip()
            if not texte_segment:
                continue
            if nom_segment != dernier_locuteur:
                index_groupe_courant += 1
                dernier_locuteur = nom_segment
            if index_groupe_courant == index_bloc_cible:
                indices_segments_bloc.append(index_segment)

        if not indices_segments_bloc:
            return HttpResponse("Bloc introuvable.", status=400)

        # Capturer le texte original du bloc avant modification (PHASE-27a)
        # / Capture original block text before modification (PHASE-27a)
        texte_original_bloc = "\n".join(
            segments_existants[i].get("text", "").strip()
            for i in indices_segments_bloc
        )
        nom_locuteur_original = segments_existants[indices_segments_bloc[0]].get("speaker", "Inconnu")

        # Decouper le nouveau texte en lignes (une par segment)
        # / Split new text into lines (one per segment)
        nouvelles_lignes = [ligne.strip() for ligne in nouveau_texte_brut.split("\n") if ligne.strip()]

        if not nouvelles_lignes:
            return HttpResponse("Le texte ne peut pas etre vide.", status=400)

        # Remplacer les segments du bloc par les nouvelles lignes
        # On garde le speaker et les timestamps du premier et dernier segment
        # / Replace block segments with new lines
        # Keep speaker and timestamps from first and last segment
        premier_segment = segments_existants[indices_segments_bloc[0]]
        dernier_segment = segments_existants[indices_segments_bloc[-1]]
        nom_locuteur_bloc = premier_segment.get("speaker", "Inconnu")
        timestamp_debut_bloc = premier_segment.get("start", 0.0)
        timestamp_fin_bloc = dernier_segment.get("end", 0.0)

        # Construire les nouveaux segments / Build new segments
        nouveaux_segments_bloc = []
        nombre_nouvelles_lignes = len(nouvelles_lignes)
        duree_totale_bloc = timestamp_fin_bloc - timestamp_debut_bloc

        for index_ligne, ligne in enumerate(nouvelles_lignes):
            # Repartir les timestamps proportionnellement
            # / Distribute timestamps proportionally
            debut_ligne = timestamp_debut_bloc + (duree_totale_bloc * index_ligne / nombre_nouvelles_lignes)
            fin_ligne = timestamp_debut_bloc + (duree_totale_bloc * (index_ligne + 1) / nombre_nouvelles_lignes)
            nouveaux_segments_bloc.append({
                "speaker": nom_locuteur_bloc,
                "start": round(debut_ligne, 2),
                "end": round(fin_ligne, 2),
                "text": ligne,
            })

        # Remplacer dans la liste des segments / Replace in the segment list
        premier_indice = indices_segments_bloc[0]
        dernier_indice = indices_segments_bloc[-1]
        segments_existants[premier_indice:dernier_indice + 1] = nouveaux_segments_bloc

        # Sauvegarder et reconstruire / Save and rebuild
        transcription_brute["segments"] = segments_existants
        page.transcription_raw = transcription_brute

        html_reconstruit, texte_reconstruit = construire_html_diarise(segments_existants)
        page.html_readability = html_reconstruit
        page.text_readability = texte_reconstruit
        page.save()

        # Enregistrer l'edition dans l'historique (PHASE-27a)
        # / Record the edit in history (PHASE-27a)
        description_edition_bloc = f"Bloc {index_bloc_cible} modifié ({nom_locuteur_original})"
        PageEdit.objects.create(
            page=page,
            user=request.user if request.user.is_authenticated else None,
            type_edit="bloc_transcription",
            description=description_edition_bloc[:500],
            donnees_avant={"index": index_bloc_cible, "texte": texte_original_bloc, "locuteur": nom_locuteur_original},
            donnees_apres={"index": index_bloc_cible, "texte": nouveau_texte_brut},
        )

        # Re-annoter le HTML avec les barres d'extraction si un job existe
        # / Re-annotate HTML with extraction bars if a job exists
        html_annote = None
        dernier_job_termine = ExtractionJob.objects.filter(
            page=page, status="completed",
        ).select_related("analyseur_version").order_by("-created_at").first()
        if dernier_job_termine:
            # Entites de TOUS les jobs termines (coherent avec le drawer E)
            # / Entities from ALL completed jobs (consistent with the E drawer)
            tous_les_jobs_page = ExtractionJob.objects.filter(page=page, status="completed")
            entites_existantes, ids_entites_commentees = _annoter_entites_avec_commentaires(
                ExtractedEntity.objects.filter(job__in=tous_les_jobs_page, masquee=False)
            )
            html_annote = annoter_html_avec_barres(
                page.html_readability, page.text_readability,
                entites_existantes, ids_entites_commentees,
            )

        toutes_les_versions = page.toutes_les_versions
        page_racine = page.page_racine

        return render(request, "front/includes/lecture_principale.html", {
            "page": page,
            "html_annote": html_annote,
            "versions": toutes_les_versions,
            "page_racine": page_racine,
        })

    @action(detail=True, methods=["POST"], url_path="supprimer_bloc")
    def supprimer_bloc(self, request, pk=None):
        """
        Supprime un bloc entier de la transcription.
        / Deletes an entire block from the transcription.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        from .services.transcription_audio import construire_html_diarise

        page = get_object_or_404(Page, pk=pk)

        # Valider les donnees / Validate data
        serializer_suppression = SupprimerBlocSerializer(data=request.data)
        serializer_suppression.is_valid(raise_exception=True)
        index_bloc_cible = serializer_suppression.validated_data["index_bloc"]

        # Charger la transcription brute / Load raw transcription
        transcription_brute = page.transcription_raw or {}
        segments_existants = transcription_brute.get("segments", [])

        if not segments_existants:
            return HttpResponse("Aucune transcription trouvee.", status=400)

        # Identifier les indices des segments du bloc cible
        # / Identify segment indices of the target block
        index_groupe_courant = -1
        dernier_locuteur = None
        indices_segments_a_supprimer = []

        for index_segment, segment in enumerate(segments_existants):
            nom_segment = segment.get("speaker", "Inconnu")
            texte_segment = segment.get("text", "").strip()
            if not texte_segment:
                continue
            if nom_segment != dernier_locuteur:
                index_groupe_courant += 1
                dernier_locuteur = nom_segment
            if index_groupe_courant == index_bloc_cible:
                indices_segments_a_supprimer.append(index_segment)

        if not indices_segments_a_supprimer:
            return HttpResponse("Bloc introuvable.", status=400)

        # Supprimer les segments du bloc (en ordre inverse pour garder les indices)
        # / Delete block segments (in reverse order to preserve indices)
        for index_a_supprimer in reversed(indices_segments_a_supprimer):
            segments_existants.pop(index_a_supprimer)

        # Sauvegarder et reconstruire / Save and rebuild
        transcription_brute["segments"] = segments_existants
        page.transcription_raw = transcription_brute

        html_reconstruit, texte_reconstruit = construire_html_diarise(segments_existants)
        page.html_readability = html_reconstruit
        page.text_readability = texte_reconstruit
        page.save()

        # Re-annoter le HTML avec les barres d'extraction si un job existe
        # / Re-annotate HTML with extraction bars if a job exists
        html_annote = None
        dernier_job_termine = ExtractionJob.objects.filter(
            page=page, status="completed",
        ).select_related("analyseur_version").order_by("-created_at").first()
        if dernier_job_termine:
            # Entites de TOUS les jobs termines (coherent avec le drawer E)
            # / Entities from ALL completed jobs (consistent with the E drawer)
            tous_les_jobs_page = ExtractionJob.objects.filter(page=page, status="completed")
            entites_existantes, ids_entites_commentees = _annoter_entites_avec_commentaires(
                ExtractedEntity.objects.filter(job__in=tous_les_jobs_page, masquee=False)
            )
            html_annote = annoter_html_avec_barres(
                page.html_readability, page.text_readability,
                entites_existantes, ids_entites_commentees,
            )

        toutes_les_versions = page.toutes_les_versions
        page_racine = page.page_racine

        return render(request, "front/includes/lecture_principale.html", {
            "page": page,
            "html_annote": html_annote,
            "versions": toutes_les_versions,
            "page_racine": page_racine,
        })


class DossierViewSet(viewsets.ViewSet):
    """
    ViewSet explicite pour la gestion des dossiers.
    Explicit ViewSet for folder management.
    """

    def list(self, request):
        # Retourne la liste des dossiers de l'utilisateur en JSON (pour SweetAlert)
        # / Returns user's folder list as JSON (for SweetAlert)
        if request.user.is_authenticated:
            tous_les_dossiers = Dossier.objects.filter(
                Q(owner=request.user) | Q(owner__isnull=True)
            ).order_by("name")
        else:
            tous_les_dossiers = Dossier.objects.none()
        data = {str(d.pk): d.name for d in tous_les_dossiers}
        return JsonResponse(data)

    def create(self, request):
        """
        Cree un nouveau dossier. Le champ arrive sous le nom 'nom' depuis le JS.
        / Creates a new folder. The field arrives as 'nom' from the JS.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        # Le JS envoie 'nom', le serializer attend 'name' — on normalise
        # / JS sends 'nom', serializer expects 'name' — normalize
        donnees_normalisees = request.data.copy()
        if "nom" in donnees_normalisees and "name" not in donnees_normalisees:
            donnees_normalisees["name"] = donnees_normalisees["nom"]

        serializer = DossierCreateSerializer(data=donnees_normalisees)
        if not serializer.is_valid():
            logger.warning("create dossier: validation echouee — %s", serializer.errors)
            reponse = HttpResponse(status=400)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {"message": "Nom du dossier invalide", "icon": "error"},
            })
            return reponse

        nouveau_dossier = Dossier.objects.create(
            name=serializer.validated_data["name"],
            owner=request.user,
        )
        logger.info("create dossier: pk=%s name='%s' owner=%s", nouveau_dossier.pk, nouveau_dossier.name, request.user)

        reponse = _render_arbre(request)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Dossier \u00ab {nouveau_dossier.name} \u00bb cr\u00e9\u00e9"},
        })
        return reponse

    def destroy(self, request, pk=None):
        """
        Supprime un dossier. Seul le proprietaire peut supprimer.
        Si le dossier contient des pages, elles deviennent orphelines.
        / Deletes a folder. Only the owner can delete.
        / If the folder contains pages, they become orphans.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        dossier_a_supprimer = get_object_or_404(Dossier, pk=pk)

        # Verifier ownership / Check ownership
        if dossier_a_supprimer.owner and dossier_a_supprimer.owner != request.user:
            return _reponse_acces_refuse(request)

        nombre_pages_dans_dossier = Page.objects.filter(
            dossier=dossier_a_supprimer, parent_page__isnull=True,
        ).count()

        nom_dossier = dossier_a_supprimer.name
        dossier_a_supprimer.delete()

        # Message adapte selon que le dossier contenait des pages ou non
        # / Message adapted depending on whether folder contained pages or not
        if nombre_pages_dans_dossier > 0:
            message_toast = f"Dossier \u00ab {nom_dossier} \u00bb supprim\u00e9 — {nombre_pages_dans_dossier} page(s) reclassee(s) en orphelines"
        else:
            message_toast = f"Dossier \u00ab {nom_dossier} \u00bb supprim\u00e9"

        reponse = _render_arbre(request)
        reponse["HX-Trigger"] = json.dumps({"showToast": {"message": message_toast}})
        return reponse

    @action(detail=True, methods=["POST"])
    def renommer(self, request, pk=None):
        """
        Renomme un dossier et retourne l'arbre mis a jour.
        Seul le proprietaire du dossier peut le renommer.
        / Renames a folder and returns the updated tree.
        / Only the folder owner can rename it.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        dossier_a_renommer = get_object_or_404(Dossier, pk=pk)

        # Verifier ownership / Check ownership
        if dossier_a_renommer.owner and dossier_a_renommer.owner != request.user:
            return _reponse_acces_refuse(request)

        serializer = DossierRenommerSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("renommer dossier: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        nouveau_nom = serializer.validated_data["nouveau_nom"]
        dossier_a_renommer.name = nouveau_nom
        dossier_a_renommer.save(update_fields=["name"])

        reponse = _render_arbre(request)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Dossier renomm\u00e9 en \u00ab {nouveau_nom} \u00bb"},
        })
        return reponse

    @action(detail=True, methods=["GET", "POST"], url_path="partager")
    def partager(self, request, pk=None):
        """
        GET : affiche le formulaire de partage avec la liste des users partages.
        POST : ajoute ou retire un partage.
        / GET: display sharing form with list of shared users.
        / POST: add or remove a share.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        dossier_cible = get_object_or_404(Dossier, pk=pk)

        if request.method == "POST":
            # Detecter si c'est un retrait (retirer_user_id / retirer_groupe_id) ou un ajout
            # / Detect if it's a removal (retirer_user_id / retirer_groupe_id) or an addition
            retirer_user_id = request.data.get("retirer_user_id")
            retirer_groupe_id = request.data.get("retirer_groupe_id")
            groupe_id_a_ajouter = request.data.get("groupe_id")

            if retirer_user_id:
                DossierPartage.objects.filter(
                    dossier=dossier_cible, utilisateur_id=retirer_user_id,
                ).delete()
            elif retirer_groupe_id:
                DossierPartage.objects.filter(
                    dossier=dossier_cible, groupe_id=retirer_groupe_id,
                ).delete()
            elif groupe_id_a_ajouter:
                # Partage avec un groupe
                # / Share with a group
                groupe_cible = GroupeUtilisateurs.objects.filter(
                    pk=groupe_id_a_ajouter, owner=request.user,
                ).first()
                if groupe_cible:
                    DossierPartage.objects.get_or_create(
                        dossier=dossier_cible,
                        groupe=groupe_cible,
                        defaults={"utilisateur": None},
                    )
                    # Auto-upgrade : prive → partage
                    # / Auto-upgrade: private → shared
                    if dossier_cible.visibilite == VisibiliteDossier.PRIVE:
                        dossier_cible.visibilite = VisibiliteDossier.PARTAGE
                        dossier_cible.save(update_fields=["visibilite"])
            else:
                serializer = DossierPartageSerializer(data=request.data)
                if serializer.is_valid():
                    username_a_ajouter = serializer.validated_data["username"]
                    utilisateur_cible = AuthUser.objects.filter(username__iexact=username_a_ajouter).first()
                    if utilisateur_cible and utilisateur_cible != request.user:
                        DossierPartage.objects.get_or_create(
                            dossier=dossier_cible,
                            utilisateur=utilisateur_cible,
                            defaults={"groupe": None},
                        )
                        # Auto-upgrade : prive → partage
                        # / Auto-upgrade: private → shared
                        if dossier_cible.visibilite == VisibiliteDossier.PRIVE:
                            dossier_cible.visibilite = VisibiliteDossier.PARTAGE
                            dossier_cible.save(update_fields=["visibilite"])

        # Rendre le formulaire de partage / Render sharing form
        tous_les_partages_du_dossier = DossierPartage.objects.filter(
            dossier=dossier_cible,
        ).select_related("utilisateur", "groupe")

        # Recuperer les groupes de l'utilisateur (pour la section groupes)
        # / Get user's groups (for group section)
        groupes_de_utilisateur = GroupeUtilisateurs.objects.filter(
            owner=request.user,
        )
        ids_groupes_partages = DossierPartage.objects.filter(
            dossier=dossier_cible, groupe__isnull=False,
        ).values_list("groupe_id", flat=True)

        # Invitations en attente pour ce dossier (PHASE-25d)
        # / Pending invitations for this folder (PHASE-25d)
        invitations_en_attente_dossier = Invitation.objects.filter(
            dossier=dossier_cible, acceptee=False, expires_at__gte=timezone.now(),
        )

        return render(request, "front/includes/partage_dossier_form.html", {
            "dossier": dossier_cible,
            "partages": tous_les_partages_du_dossier,
            "groupes_disponibles": groupes_de_utilisateur,
            "ids_groupes_partages": set(ids_groupes_partages),
            "invitations_en_attente": invitations_en_attente_dossier,
        })

    @action(detail=True, methods=["POST"], url_path="visibilite")
    def changer_visibilite(self, request, pk=None):
        """
        Change la visibilite d'un dossier (prive, partage, public).
        Seul l'owner peut changer la visibilite.
        / Changes folder visibility (private, shared, public).
        Only the owner can change visibility.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        dossier_cible = get_object_or_404(Dossier, pk=pk)

        # Seul le proprietaire peut changer la visibilite
        # / Only the owner can change visibility
        if dossier_cible.owner != request.user:
            return HttpResponse("Non autorise.", status=403)

        serializer = ChangerVisibiliteSerializer(data=request.data)
        if not serializer.is_valid():
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        nouvelle_visibilite = serializer.validated_data["visibilite"]
        dossier_cible.visibilite = nouvelle_visibilite
        dossier_cible.save(update_fields=["visibilite"])

        reponse = _render_arbre(request)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Visibilite changee en « {nouvelle_visibilite} »"},
        })
        return reponse

    @action(detail=True, methods=["POST"], url_path="quitter")
    def quitter(self, request, pk=None):
        """
        Quitte un partage : supprime le DossierPartage pour l'utilisateur courant.
        / Leave a share: removes the DossierPartage for the current user.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        dossier_cible = get_object_or_404(Dossier, pk=pk)

        # Supprimer les partages directs de cet utilisateur
        # / Remove direct shares for this user
        DossierPartage.objects.filter(
            dossier=dossier_cible, utilisateur=request.user,
        ).delete()

        reponse = _render_arbre(request)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Partage quitte pour « {dossier_cible.name} »"},
        })
        return reponse

    @action(detail=True, methods=["POST"], url_path="inviter")
    def inviter(self, request, pk=None):
        """
        Invite un utilisateur par email a acceder a un dossier (PHASE-25d).
        Si l'email correspond a un utilisateur existant → DossierPartage direct.
        Sinon → creation d'une Invitation + envoi d'email.
        / Invite a user by email to access a folder (PHASE-25d).
        If email matches an existing user → direct DossierPartage.
        Otherwise → create Invitation + send email.

        LOCALISATION : front/views.py
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        dossier_cible = get_object_or_404(Dossier, pk=pk)

        # Verifier que c'est l'owner du dossier
        # / Check that user is folder owner
        if dossier_cible.owner != request.user:
            return HttpResponse("Non autorise.", status=403)

        serializer = InviterEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        email_invite = serializer.validated_data["email"]

        # Rejeter l'auto-invitation
        # / Reject self-invitation
        if request.user.email and email_invite.lower() == request.user.email.lower():
            return HttpResponse(
                '<p class="text-sm text-red-500">Vous ne pouvez pas vous inviter vous-meme.</p>',
                status=400,
            )

        # Verifier si un utilisateur avec cet email existe deja
        # / Check if a user with this email already exists
        utilisateur_existant = AuthUser.objects.filter(email__iexact=email_invite).first()

        if utilisateur_existant:
            # Partage direct (pas d'email envoye) / Direct share (no email sent)
            DossierPartage.objects.get_or_create(
                dossier=dossier_cible,
                utilisateur=utilisateur_existant,
                defaults={"groupe": None},
            )
            # Auto-upgrade : prive → partage
            # / Auto-upgrade: private → shared
            if dossier_cible.visibilite == VisibiliteDossier.PRIVE:
                dossier_cible.visibilite = VisibiliteDossier.PARTAGE
                dossier_cible.save(update_fields=["visibilite"])
        else:
            # Verifier si une invitation est deja en attente
            # / Check if an invitation is already pending
            invitation_existante = Invitation.objects.filter(
                dossier=dossier_cible, email__iexact=email_invite,
                acceptee=False, expires_at__gte=timezone.now(),
            ).exists()

            if invitation_existante:
                # Re-render le formulaire avec toast info
                # / Re-render form with info toast
                pass
            else:
                # Creer et envoyer l'invitation
                # / Create and send invitation
                from .views_invitation import creer_invitation
                creer_invitation(
                    dossier=dossier_cible,
                    groupe=None,
                    email=email_invite,
                    invite_par=request.user,
                )

        # Re-render le formulaire de partage avec les invitations en attente
        # / Re-render sharing form with pending invitations
        tous_les_partages_du_dossier = DossierPartage.objects.filter(
            dossier=dossier_cible,
        ).select_related("utilisateur", "groupe")

        groupes_de_utilisateur = GroupeUtilisateurs.objects.filter(
            owner=request.user,
        )
        ids_groupes_partages = DossierPartage.objects.filter(
            dossier=dossier_cible, groupe__isnull=False,
        ).values_list("groupe_id", flat=True)

        # Invitations en attente pour ce dossier
        # / Pending invitations for this folder
        invitations_en_attente_dossier = Invitation.objects.filter(
            dossier=dossier_cible, acceptee=False, expires_at__gte=timezone.now(),
        )

        # Toast de confirmation selon le type d'action
        # / Confirmation toast depending on action type
        if utilisateur_existant:
            message_toast = f"Dossier partage avec {utilisateur_existant.username}"
        else:
            message_toast = f"Invitation envoyee a {email_invite}"

        reponse = render(request, "front/includes/partage_dossier_form.html", {
            "dossier": dossier_cible,
            "partages": tous_les_partages_du_dossier,
            "groupes_disponibles": groupes_de_utilisateur,
            "ids_groupes_partages": set(ids_groupes_partages),
            "invitations_en_attente": invitations_en_attente_dossier,
        })
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": message_toast},
        })
        return reponse


class PageViewSet(viewsets.ViewSet):
    """
    ViewSet explicite pour les actions sur les pages.
    Explicit ViewSet for page actions.
    """

    @action(detail=True, methods=["POST"])
    def supprimer(self, request, pk=None):
        """
        Supprime une page et retourne l'arbre mis a jour.
        Seul le proprietaire du dossier contenant la page peut la supprimer.
        / Deletes a page and returns the updated tree.
        / Only the owner of the folder containing the page can delete it.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        page_a_supprimer = get_object_or_404(Page, pk=pk)

        # Verifier ownership du dossier / Check folder ownership
        if not _est_proprietaire_dossier(request.user, page_a_supprimer):
            return _reponse_acces_refuse(request)

        titre_page = page_a_supprimer.title or "Sans titre"
        page_a_supprimer.delete()

        reponse = _render_arbre(request)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Page \u00ab {titre_page} \u00bb supprim\u00e9e"},
        })
        return reponse

    @action(detail=True, methods=["POST"])
    def classer(self, request, pk=None):
        """
        Assigne une page a un dossier, retourne l'arbre mis a jour.
        Verifie que l'utilisateur est owner du dossier source ou destination.
        / Assign a page to a folder, return updated tree.
        / Checks user is owner of source or destination folder.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        page = get_object_or_404(Page, pk=pk)

        serializer = PageClasserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dossier_id = serializer.validated_data["dossier_id"]
        dossier_destination = get_object_or_404(Dossier, pk=dossier_id) if dossier_id else None

        # Verifier ownership : l'utilisateur doit etre owner du dossier source OU destination
        # / Check ownership: user must be owner of source OR destination folder
        est_owner_source = page.dossier and page.dossier.owner == request.user
        est_owner_destination = dossier_destination and dossier_destination.owner == request.user
        if not est_owner_source and not est_owner_destination:
            return _reponse_acces_refuse(request)

        page.dossier = dossier_destination
        page.save(update_fields=["dossier"])

        return _render_arbre(request)


def _calculer_teinte_contributeur(username):
    """
    Convertit un username en teinte HSL deterministe (0-360) via hash MD5.
    Chaque contributeur obtient une couleur unique et stable pour ses pilules.
    / Converts a username to a deterministic HSL hue (0-360) via MD5 hash.
    / Each contributor gets a unique, stable color for their pills.

    LOCALISATION : front/views.py (PHASE-26a UX)

    :param username: Nom d'utilisateur (str)
    :return: Teinte HSL entre 0 et 359 (int)
    """
    # Prendre les 8 premiers caracteres du hash MD5 et convertir en entier modulo 360
    # / Take the first 8 chars of the MD5 hash and convert to integer modulo 360
    digest = hashlib.md5(username.encode()).hexdigest()
    return int(digest[:8], 16) % 360


class ExtractionViewSet(viewsets.ViewSet):
    """
    ViewSet pour les extractions de texte (manuelle et IA).
    ViewSet for text extractions (manual and AI).
    """

    def _get_or_create_job_manuel(self, page):
        """
        Retourne (ou cree) le job d'extraction manuelle pour une page.
        Returns (or creates) the manual extraction job for a page.
        """
        job_manuel, _created = ExtractionJob.objects.get_or_create(
            page=page,
            name="Extractions manuelles",
            defaults={"status": "completed", "ai_model": None},
        )
        return job_manuel

    def _render_panneau_complet_avec_oob(self, request, page):
        """
        Re-rend le panneau d'analyse + OOB swap du readability-content annote.
        Re-renders analysis panel + OOB swap of annotated readability-content.
        """
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")

        # Toutes les entites de tous les jobs completed de la page
        # / All entities from all completed jobs for the page
        tous_les_jobs_termines = ExtractionJob.objects.filter(
            page=page, status="completed",
        )

        # Entites visibles (non masquees) pour l'annotation HTML
        # / Visible entities (not hidden) for HTML annotation
        entites_visibles, ids_entites_commentees = _annoter_entites_avec_commentaires(
            ExtractedEntity.objects.filter(
                job__in=tous_les_jobs_termines,
                masquee=False,
            ).order_by("start_char")
        )

        # Compteur d'entites masquees pour le drawer
        # / Hidden entities count for the drawer
        nombre_masquees = ExtractedEntity.objects.filter(
            job__in=tous_les_jobs_termines,
            masquee=True,
        ).count()

        # Annoter le HTML / Annotate HTML
        html_annote = annoter_html_avec_barres(
            page.html_readability, page.text_readability,
            entites_visibles, ids_entites_commentees,
        )

        # Dernier job pour le contexte du panneau / Latest job for panel context
        dernier_job = tous_les_jobs_termines.order_by("-created_at").first()

        html_panneau = render_to_string(
            "front/includes/panneau_analyse.html",
            {
                "page": page,
                "analyseurs_actifs": analyseurs_actifs,
                "job": dernier_job,
                "entities": entites_visibles,
                "nombre_masquees": nombre_masquees,
                "ia_active": _get_ia_active(),
            },
            request=request,
        )

        # OOB swap pour le contenu de lecture annote
        # / OOB swap for annotated reading content
        html_readability_oob = (
            '<article id="readability-content" hx-swap-oob="innerHTML:#readability-content">'
            + (html_annote or page.html_readability)
            + '</article>'
        )

        return html_panneau + html_readability_oob

    def _render_readability_avec_panneau_oob(self, request, page):
        """
        Inverse de _render_panneau_complet_avec_oob :
        retourne le readability-content annote en contenu principal
        et le panneau d'extractions en OOB.
        Utilise quand la cible principale est #readability-content (ex: masquer/restaurer
        appeles depuis le drawer JS via htmx.ajax).
        / Inverse of _render_panneau_complet_avec_oob:
        / returns annotated readability-content as main content
        / and extraction panel as OOB.
        / Used when main target is #readability-content (e.g. hide/restore
        / called from drawer JS via htmx.ajax).
        """
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")

        # Toutes les entites de tous les jobs completed de la page
        # / All entities from all completed jobs for the page
        tous_les_jobs_termines = ExtractionJob.objects.filter(
            page=page, status="completed",
        )

        # Entites visibles (non masquees) pour l'annotation HTML
        # / Visible entities (not hidden) for HTML annotation
        entites_visibles, ids_entites_commentees = _annoter_entites_avec_commentaires(
            ExtractedEntity.objects.filter(
                job__in=tous_les_jobs_termines,
                masquee=False,
            ).order_by("start_char")
        )

        # Compteur d'entites masquees pour le drawer
        # / Hidden entities count for the drawer
        nombre_masquees = ExtractedEntity.objects.filter(
            job__in=tous_les_jobs_termines,
            masquee=True,
        ).count()

        # Annoter le HTML / Annotate HTML
        html_annote = annoter_html_avec_barres(
            page.html_readability, page.text_readability,
            entites_visibles, ids_entites_commentees,
        )

        # Dernier job pour le contexte du panneau / Latest job for panel context
        dernier_job = tous_les_jobs_termines.order_by("-created_at").first()

        # Contenu principal : readability annote
        # / Main content: annotated readability
        html_readability_principal = html_annote or page.html_readability

        # OOB swap pour le panneau d'extractions
        # / OOB swap for extraction panel
        html_panneau = render_to_string(
            "front/includes/panneau_analyse.html",
            {
                "page": page,
                "analyseurs_actifs": analyseurs_actifs,
                "job": dernier_job,
                "entities": entites_visibles,
                "nombre_masquees": nombre_masquees,
                "ia_active": _get_ia_active(),
            },
            request=request,
        )
        html_panneau_oob = (
            '<div id="panneau-extractions" hx-swap-oob="innerHTML:#panneau-extractions">'
            + html_panneau
            + '</div>'
        )

        return html_readability_principal + html_panneau_oob

    @action(detail=False, methods=["POST"])
    def panneau(self, request):
        """
        Re-rend le panneau d'analyse complet pour une page (utilise par Annuler).
        Re-renders the full analysis panel for a page (used by Cancel).
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        page_id = request.data.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)
        page = get_object_or_404(Page, pk=page_id)
        html_complet = self._render_panneau_complet_avec_oob(request, page)
        return HttpResponse(html_complet)

    @action(detail=False, methods=["POST"])
    def manuelle(self, request):
        """
        Recoit le texte selectionne, calcule les positions, et renvoie le formulaire.
        Receives selected text, computes positions, returns the form partial.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        logger.info(
            "manuelle: content_type=%s data=%s",
            request.content_type, dict(request.data),
        )
        serializer = ExtractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_text = serializer.validated_data["text"]
        validated_page_id = serializer.validated_data.get("page_id")

        if not validated_page_id:
            return HttpResponse("Aucune page selectionnee.", status=400)

        page = get_object_or_404(Page, pk=validated_page_id)

        # Calculer start_char dans text_readability cote serveur
        # / Compute start_char in text_readability server-side
        start_char = page.text_readability.find(validated_text)
        if start_char == -1:
            # Fallback : recherche soft (nbsp → espace)
            start_char = page.text_readability.replace('\xa0', ' ').find(
                validated_text.replace('\xa0', ' ')
            )
        end_char = start_char + len(validated_text) if start_char != -1 else 0
        if start_char == -1:
            start_char = 0

        # Attributs par defaut pour le formulaire de creation : resume + hypostase
        # / Default attributes for the creation form: summary + hypostase
        liste_attributs_creation = [
            ("r\u00e9sum\u00e9", ""),
            ("hypostase", ""),
        ]

        html_formulaire = render_to_string(
            "front/includes/extraction_manuelle_form.html",
            {
                "text": validated_text,
                "page_id": page.pk,
                "start_char": start_char,
                "end_char": end_char,
                "liste_attributs": liste_attributs_creation,
            },
            request=request,
        )

        reponse = HttpResponse(html_formulaire)
        reponse["HX-Trigger"] = "ouvrirPanneauDroit"
        return reponse

    @action(detail=False, methods=["POST"], url_path="creer_manuelle")
    def creer_manuelle(self, request):
        """
        Cree une ExtractedEntity manuelle et re-rend le panneau complet.
        Creates a manual ExtractedEntity and re-renders the full panel.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        logger.info(
            "creer_manuelle: content_type=%s data=%s",
            request.content_type, {k: str(v)[:80] for k, v in request.data.items()},
        )
        serializer = ExtractionManuelleSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("creer_manuelle: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        donnees = serializer.validated_data
        page = get_object_or_404(Page, pk=donnees["page_id"])
        job_manuel = self._get_or_create_job_manuel(page)

        # Lire les paires cle/valeur dynamiques depuis le formulaire
        # (meme pattern que modifier)
        # / Read dynamic key/value pairs from form data (same pattern as modifier)
        attributs_entite = {}
        for index_attribut in range(10):
            cle = request.data.get(f"attr_key_{index_attribut}", "").strip()
            valeur = request.data.get(f"attr_val_{index_attribut}", "").strip()
            if cle and valeur:
                attributs_entite[cle] = valeur

        ExtractedEntity.objects.create(
            job=job_manuel,
            extraction_class="",
            extraction_text=donnees["text"],
            start_char=donnees["start_char"],
            end_char=donnees["end_char"],
            attributes=attributs_entite,
            cree_par=request.user,
        )

        html_complet = self._render_panneau_complet_avec_oob(request, page)
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "showToast": {"message": "Extraction cr\u00e9\u00e9e"},
        })
        return reponse

    @action(detail=False, methods=["GET"], url_path="carte_mobile")
    def carte_mobile(self, request):
        """
        Renvoie le partial HTML d'une carte pour le bottom sheet mobile (PHASE-21).
        / Returns the mobile bottom sheet extraction card HTML partial.

        LOCALISATION : front/views.py — ExtractionViewSet

        Appelee par bottom_sheet.js quand l'utilisateur tap une extraction sur mobile.
        Meme logique que carte_inline, mais rend bottom_sheet_extraction.html.
        / Called by bottom_sheet.js when user taps an extraction on mobile.
        """
        # Identifiant de l'entite a afficher / Entity ID to display
        identifiant_entite = request.query_params.get("entity_id")
        if not identifiant_entite:
            return HttpResponse("entity_id requis.", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=identifiant_entite)

        # Compter les commentaires pour cette entite
        # / Count comments for this entity
        nombre_commentaires = CommentaireExtraction.objects.filter(entity=entite).count()

        # Determiner si l'utilisateur est proprietaire du dossier
        # / Determine if user is the folder owner
        est_proprietaire = _est_proprietaire_dossier(request.user, entite.job.page)

        return render(request, "front/includes/bottom_sheet_extraction.html", {
            "entity": entite,
            "nombre_commentaires": nombre_commentaires,
            "est_proprietaire": est_proprietaire,
        })

    @action(detail=False, methods=["POST"], url_path="ajouter_commentaire")
    def ajouter_commentaire(self, request):
        """
        Cree un commentaire sur une extraction et renvoie _extraction_content.html.
        Le formulaire client cible "closest .extraction-content" avec swap "outerHTML",
        donc le wrapper rendu remplace la zone : commentaires nouveaux apparaissent
        immediatement, sans toast ni rechargement.
        / Creates a comment and returns _extraction_content.html.
        Client form targets "closest .extraction-content" with "outerHTML" swap.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        serializer = CommentaireExtractionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("ajouter_commentaire: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        donnees = serializer.validated_data
        entite = get_object_or_404(ExtractedEntity, pk=donnees["entity_id"])

        # Creer le commentaire (le signal Django met statut_debat a "commente")
        # / Create the comment (Django signal sets statut_debat to "commente")
        CommentaireExtraction.objects.create(
            entity=entite,
            user=request.user,
            commentaire=donnees["commentaire"],
        )

        # Refresh entite depuis la DB pour avoir le statut_debat synchronise par le signal
        # / Refresh entity from DB to get statut_debat synchronized by signal
        entite.refresh_from_db()

        est_proprietaire = _est_proprietaire_dossier(request.user, entite.job.page)

        return render(request, "hypostasis_extractor/includes/_extraction_content.html", {
            "entity": entite,
            "est_proprietaire": est_proprietaire,
        })


    @action(detail=False, methods=["POST"], url_path="supprimer_entite")
    def supprimer_entite(self, request):
        """
        Supprime une entite extraite (si pas de commentaires).
        Deletes an extracted entity (if no comments).
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        entity_id = request.data.get("entity_id")
        page_id = request.data.get("page_id")
        if not entity_id or not page_id:
            return HttpResponse("entity_id et page_id requis.", status=400)

        entite_a_supprimer = get_object_or_404(ExtractedEntity, pk=entity_id)

        # Verifier permissions / Check permissions
        if not _peut_supprimer_extraction(request.user, entite_a_supprimer):
            return _reponse_acces_refuse(request)

        page_id_pour_reload = entite_a_supprimer.job.page_id
        entite_a_supprimer.delete()

        # Meme pattern que masquer() : reponse minimale + triggers pour recharger
        # les zones concernees (drawer + lecture) sans detruire les cartes ouvertes.
        # / Same pattern as masquer(): minimal response + triggers to reload
        # / affected zones (drawer + lecture) without destroying open cards.
        reponse = HttpResponse("<span></span>")
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Extraction supprim\u00e9e"},
            "drawerContenuChange": True,
            "lectureReload": {"page_id": str(page_id_pour_reload)},
        })
        return reponse

    @action(detail=False, methods=["POST"], url_path="supprimer_ia")
    def supprimer_ia(self, request):
        """
        Supprime tous les jobs d'extraction IA (et leurs entites en cascade).
        Les extractions manuelles sont conservees.
        Deletes all AI extraction jobs (and their entities via cascade).
        Manual extractions are preserved.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        page_id = request.data.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=page_id)

        # Supprimer les entites IA sans commentaires (pas les jobs entiers pour garder celles avec commentaires)
        # / Delete AI entities without comments (not entire jobs, to keep commented ones)
        entites_ia_sans_commentaires = ExtractedEntity.objects.filter(
            job__page=page,
            job__ai_model__isnull=False,
        ).exclude(
            commentaires__isnull=False,
        )
        nombre_entites_supprimees = entites_ia_sans_commentaires.count()
        entites_ia_sans_commentaires.delete()

        # Supprimer les jobs IA qui n'ont plus d'entites
        # / Delete AI jobs that have no remaining entities
        jobs_ia_vides = ExtractionJob.objects.filter(
            page=page,
            ai_model__isnull=False,
        ).annotate(
            nombre_entites=Count("entities"),
        ).filter(nombre_entites=0)
        nombre_jobs_supprimes = jobs_ia_vides.count()
        jobs_ia_vides.delete()

        logger.info(
            "supprimer_ia: %d entites et %d jobs IA supprimes pour page pk=%s",
            nombre_entites_supprimees, nombre_jobs_supprimes, page_id,
        )

        html_complet = self._render_panneau_complet_avec_oob(request, page)
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "showToast": {"message": "Extractions IA supprim\u00e9es"},
        })
        return reponse

    @action(detail=False, methods=["GET"], url_path="formulaire_promouvoir")
    def formulaire_promouvoir(self, request):
        """
        Retourne le partial HTML du formulaire de promotion en entrainement.
        Charge la liste des analyseurs actifs cote serveur.
        / Returns the HTML partial for the training promotion form.
        Loads the active analyzers list server-side.
        """
        page_id = request.query_params.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=page_id)
        tous_les_analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True)

        return render(request, "front/includes/modale_promouvoir_entrainement.html", {
            "page": page,
            "analyseurs_actifs": tous_les_analyseurs_actifs,
        })

    @action(detail=False, methods=["POST"], url_path="promouvoir_entrainement")
    def promouvoir_entrainement(self, request):
        """
        Promeut les extractions IA d'une page en exemple d'entrainement few-shot.
        Le texte de la page devient le texte source de l'exemple.
        Chaque extraction devient une ExampleExtraction attendue avec ses attributs.
        / Promotes a page's AI extractions into a few-shot training example.
        The page text becomes the example source text.
        Each extraction becomes an expected ExampleExtraction with its attributes.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        # Validation des parametres via serializer DRF
        # / Validate parameters via DRF serializer
        serializer = PromouvoirEntrainementSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("promouvoir_entrainement: validation echouee — %s", serializer.errors)
            return HttpResponse("Parametres invalides.", status=400)

        page_id = serializer.validated_data["page_id"]
        analyseur_id = serializer.validated_data["analyseur_id"]

        page = get_object_or_404(Page, pk=page_id)
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=analyseur_id)

        # Recupere toutes les entites IA de la page (jobs completed avec ai_model)
        # / Retrieve all AI entities from the page (completed jobs with ai_model)
        toutes_les_entites_ia = ExtractedEntity.objects.filter(
            job__page=page,
            job__status="completed",
            job__ai_model__isnull=False,
        ).order_by("start_char")

        if not toutes_les_entites_ia.exists():
            return HttpResponse("Aucune extraction IA a promouvoir.", status=400)

        # Calcule l'order du nouvel exemple (max + 1)
        # / Compute order for the new example (max + 1)
        dernier_order_exemple = analyseur.examples.aggregate(
            max_order=Count("id"),
        )["max_order"] or 0

        # Cree le nouvel exemple d'entrainement avec le texte de la page
        # / Create the new training example with the page's text
        nouvel_exemple = AnalyseurExample.objects.create(
            analyseur=analyseur,
            name=page.title[:200] if page.title else f"Exemple depuis page {page.pk}",
            example_text=page.text_readability or "",
            order=dernier_order_exemple,
        )

        # Determine les cles d'attributs de reference :
        # 1. Depuis la premiere extraction du dernier exemple existant de cet analyseur
        # 2. Sinon, cles par defaut
        # / Determine reference attribute keys:
        # 1. From the first extraction of the last existing example of this analyzer
        # 2. Otherwise, default keys
        CLES_ATTRIBUTS_PAR_DEFAUT = ["Hypostase", "Résumé", "Status", "Mots clés"]
        cles_attributs_reference = CLES_ATTRIBUTS_PAR_DEFAUT

        dernier_exemple_existant = analyseur.examples.exclude(
            pk=nouvel_exemple.pk,
        ).prefetch_related("extractions__attributes").order_by("-order").first()

        if dernier_exemple_existant:
            premiere_extraction_reference = dernier_exemple_existant.extractions.first()
            if premiere_extraction_reference:
                cles_depuis_reference = list(
                    premiere_extraction_reference.attributes.order_by("order").values_list("key", flat=True)
                )
                if cles_depuis_reference:
                    cles_attributs_reference = cles_depuis_reference

        # Cree une ExampleExtraction attendue pour chaque entite IA
        # / Create an expected ExampleExtraction for each AI entity
        for numero_entite, entite in enumerate(toutes_les_entites_ia):
            nouvelle_extraction_attendue = ExampleExtraction.objects.create(
                example=nouvel_exemple,
                extraction_class=entite.extraction_class or "",
                extraction_text=entite.extraction_text or "",
                order=numero_entite,
            )

            # Mappe les valeurs du JSONField attributes sur les cles de reference
            # / Map JSONField attribute values onto reference keys
            dictionnaire_attributs_entite = entite.attributes or {}
            liste_valeurs_entite = list(dictionnaire_attributs_entite.values())

            for numero_attribut, cle_reference in enumerate(cles_attributs_reference):
                # Valeur de l'entite a cette position, ou vide si absente
                # / Entity value at this position, or empty if missing
                valeur_attribut = ""
                if numero_attribut < len(liste_valeurs_entite):
                    valeur_attribut = str(liste_valeurs_entite[numero_attribut])

                ExtractionAttribute.objects.create(
                    extraction=nouvelle_extraction_attendue,
                    key=cle_reference,
                    value=valeur_attribut,
                    order=numero_attribut,
                )

        logger.info(
            "promouvoir_entrainement: exemple pk=%d cree avec %d extractions pour analyseur pk=%d",
            nouvel_exemple.pk, toutes_les_entites_ia.count(), analyseur.pk,
        )

        # Retourne le panneau mis a jour + toast de succes
        # / Return updated panel + success toast
        html_complet = self._render_panneau_complet_avec_oob(request, page)
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "showToast": {"message": f"Ajouté comme entrainement dans {analyseur.name}"},
        })
        return reponse

    @action(detail=False, methods=["POST"])
    def ia(self, request):
        """
        Extrait des hypostases du texte selectionne via LangExtract (appel synchrone).
        Le LLM peut retourner une ou plusieurs extractions.
        Les positions sont recalculees par rapport a text_readability de la page.
        / Extracts hypostases from selected text via LangExtract (synchronous call).
        / The LLM can return one or more extractions.
        / Positions are recalculated relative to the page's text_readability.

        LOCALISATION : front/views.py — ExtractionViewSet
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        serializer = ExtractionSerializer(data=request.data)
        if not serializer.is_valid():
            reponse = HttpResponse(status=400)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {"message": "Texte invalide.", "icon": "error"},
            })
            return reponse

        texte_selectionne = serializer.validated_data["text"]
        identifiant_page = serializer.validated_data.get("page_id")
        if not identifiant_page:
            reponse = HttpResponse(status=400)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {"message": "Page introuvable.", "icon": "error"},
            })
            return reponse

        page = get_object_or_404(Page, pk=identifiant_page)

        # Verifier que l'IA est activee et qu'un modele est configure
        # / Check that AI is enabled and a model is configured
        configuration_ia = Configuration.get_solo()
        if not configuration_ia.ai_active or not configuration_ia.ai_model:
            reponse = HttpResponse(status=400)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "IA non activ\u00e9e. Configurez un mod\u00e8le dans /api/analyseurs/.",
                    "icon": "warning",
                },
            })
            return reponse

        # Recuperer le premier analyseur actif de type "analyser"
        # / Get the first active analyzer of type "analyser"
        analyseur = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="analyser",
        ).first()
        if not analyseur:
            reponse = HttpResponse(status=400)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {"message": "Aucun analyseur actif.", "icon": "error"},
            })
            return reponse

        # Construire le prompt et les exemples / Build prompt and examples
        from hypostasis_extractor.services import _construire_exemples_langextract, resolve_model_params
        import langextract as lx

        pieces_ordonnees = PromptPiece.objects.filter(analyseur=analyseur).order_by("order")
        prompt_complet = "\n".join(piece.content for piece in pieces_ordonnees)
        liste_exemples = _construire_exemples_langextract(analyseur)
        parametres_modele = resolve_model_params(configuration_ia.ai_model)

        logger.info(
            "ia (selection): page=%s model=%s text_len=%d",
            identifiant_page, parametres_modele.get("model_id", "?"), len(texte_selectionne),
        )

        # Appel synchrone LangExtract sur le texte selectionne
        # / Synchronous LangExtract call on selected text
        try:
            resultat = lx.extract(
                text_or_documents=texte_selectionne,
                prompt_description=prompt_complet,
                examples=liste_exemples,
                **parametres_modele,
            )
        except Exception as erreur_extraction:
            logger.error("ia (selection): erreur LangExtract — %s", erreur_extraction)
            reponse = HttpResponse(status=500)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": f"Erreur IA : {str(erreur_extraction)[:150]}",
                    "icon": "error",
                },
            })
            return reponse

        # Calculer l'offset du texte selectionne dans text_readability
        # pour que les positions des extractions soient relatives a la page entiere
        # / Calculate the offset of the selected text in text_readability
        # / so extraction positions are relative to the full page
        texte_page_complet = page.text_readability or ""
        offset_dans_page = texte_page_complet.find(texte_selectionne)
        if offset_dans_page == -1:
            # Fallback : essayer avec normalisation des espaces insecables
            # / Fallback: try with non-breaking space normalization
            texte_page_normalise = texte_page_complet.replace("\xa0", " ")
            texte_selectionne_normalise = texte_selectionne.replace("\xa0", " ")
            offset_dans_page = texte_page_normalise.find(texte_selectionne_normalise)
        if offset_dans_page == -1:
            offset_dans_page = 0

        # Creer un job d'extraction pour regrouper les entites
        # / Create an extraction job to group the entities
        job_ia_selection = ExtractionJob.objects.create(
            page=page,
            ai_model=configuration_ia.ai_model,
            name=f"Extraction IA (s\u00e9lection) — {analyseur.name}",
            prompt_description=prompt_complet[:500],
            status="completed",
        )

        # Creer les entites extraites / Create extracted entities
        nombre_entites_creees = 0
        for extraction in resultat.extractions or []:
            intervalle_caracteres = extraction.char_interval

            # Positions relatives au texte selectionne → ajouter l'offset page
            # / Positions relative to selected text → add page offset
            start_char_dans_selection = intervalle_caracteres.start_pos if intervalle_caracteres else 0
            end_char_dans_selection = intervalle_caracteres.end_pos if intervalle_caracteres else 0
            start_char_dans_page = start_char_dans_selection + offset_dans_page
            end_char_dans_page = end_char_dans_selection + offset_dans_page

            ExtractedEntity.objects.create(
                job=job_ia_selection,
                extraction_class=extraction.extraction_class or "",
                extraction_text=extraction.extraction_text or texte_selectionne,
                start_char=start_char_dans_page,
                end_char=end_char_dans_page,
                attributes=extraction.attributes or {},
            )
            nombre_entites_creees += 1

        logger.info(
            "ia (selection): %d extraction(s) creee(s) pour page=%s",
            nombre_entites_creees, identifiant_page,
        )

        # Re-rendre le panneau + OOB swap du texte annote
        # / Re-render panel + OOB swap of annotated text
        html_complet = self._render_panneau_complet_avec_oob(request, page)
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "showToast": {
                "message": f"{nombre_entites_creees} extraction(s) IA cr\u00e9\u00e9e(s)",
                "icon": "success",
            },
        })
        return reponse

    @action(detail=False, methods=["POST"])
    def masquer(self, request):
        """
        Masque une extraction (curation). Refuse si l'entite a des commentaires.
        / Hide an extraction (curation). Refuses if entity has comments.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        identifiant_entite = request.data.get("entity_id")
        identifiant_page = request.data.get("page_id")
        if not identifiant_entite or not identifiant_page:
            return HttpResponse("entity_id et page_id requis.", status=400)

        entite_a_masquer = get_object_or_404(ExtractedEntity, pk=identifiant_entite)

        # Verification ownership : seul le proprietaire du dossier peut masquer
        # / Ownership check: only the folder owner can hide
        page_de_lentite = entite_a_masquer.job.page
        if not _est_proprietaire_dossier(request.user, page_de_lentite):
            return HttpResponse("Non autorise.", status=403)

        # Garde : ne pas masquer une entite qui a des commentaires
        # / Guard: do not hide an entity that has comments
        nombre_commentaires_entite = CommentaireExtraction.objects.filter(
            entity=entite_a_masquer,
        ).count()
        if nombre_commentaires_entite > 0:
            return HttpResponse(
                '<p class="text-sm text-red-500">Impossible de masquer : '
                'cette extraction a des commentaires.</p>',
                status=400,
            )

        # Marquer comme masquee (le statut_debat est gere par signal)
        # / Mark as hidden (statut_debat handled by signal)
        entite_a_masquer.masquee = True
        entite_a_masquer.save(update_fields=["masquee"])

        # Reponse minimale : le panneau sera recharge via drawerContenuChange
        # et le texte sera recharge via lectureReload dans le JS
        # / Minimal response: panel will be reloaded via drawerContenuChange
        # / and text will be reloaded via lectureReload in JS
        reponse = HttpResponse('<span></span>')
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Extraction masqu\u00e9e"},
            "drawerContenuChange": True,
            "lectureReload": {"page_id": identifiant_page},
            "dashboardReload": True,
        })
        return reponse

    @action(detail=False, methods=["POST"])
    def restaurer(self, request):
        """
        Restaure une extraction masquee (la rend visible a nouveau).
        / Restore a hidden extraction (make it visible again).
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        identifiant_entite = request.data.get("entity_id")
        identifiant_page = request.data.get("page_id")
        if not identifiant_entite or not identifiant_page:
            return HttpResponse("entity_id et page_id requis.", status=400)

        entite_a_restaurer = get_object_or_404(ExtractedEntity, pk=identifiant_entite)

        # Verification ownership : seul le proprietaire du dossier peut restaurer
        # / Ownership check: only the folder owner can restore
        page_de_lentite = entite_a_restaurer.job.page
        if not _est_proprietaire_dossier(request.user, page_de_lentite):
            return HttpResponse("Non autorise.", status=403)

        # Demarquer comme masquee (le statut_debat est gere par signal)
        # / Unmark as hidden (statut_debat handled by signal)
        entite_a_restaurer.masquee = False
        entite_a_restaurer.save(update_fields=["masquee"])

        # Reponse minimale : le panneau et le texte seront recharges via events
        # / Minimal response: panel and text will be reloaded via events
        reponse = HttpResponse('<span></span>')
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Extraction restaur\u00e9e"},
            "drawerContenuChange": True,
            "lectureReload": {"page_id": identifiant_page},
            "dashboardReload": True,
        })
        return reponse

    @action(detail=False, methods=["GET"], url_path="dashboard")
    def dashboard(self, request):
        """
        Renvoie le dashboard de consensus pour une page donnee.
        Delegue le calcul au helper _calculer_consensus pour partage avec
        previsualiser_synthese (drawer de confirmation).
        / Returns the consensus dashboard for a given page.
        / Delegates calculation to _calculer_consensus helper for sharing with
        / previsualiser_synthese (confirmation drawer).
        """
        identifiant_page = request.query_params.get("page_id")
        if not identifiant_page:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=identifiant_page)

        # Calculer l'etat du consensus via le helper / Compute consensus state via helper
        donnees_consensus = _calculer_consensus(page)

        # Liste des analyseurs de synthese pour le bouton du dashboard
        # / Synthesis analyzers list for the dashboard button
        analyseurs_synthese = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="synthetiser",
        ).order_by("-est_par_defaut", "name")

        contexte = {
            "page": page,
            "analyseurs_synthese": analyseurs_synthese,
            "consensus": donnees_consensus,
        }
        return render(request, "front/includes/dashboard_consensus.html", contexte)

    @action(detail=False, methods=["GET"], url_path="drawer_contenu")
    def drawer_contenu(self, request):
        """
        Renvoie le contenu du drawer vue liste (toutes les extractions d'une page).
        Supporte un parametre de tri : position (defaut), activite, statut.
        Supporte un filtre par contributeur : ?contributeur=42 (PHASE-26a).
        / Returns drawer list view content (all extractions for a page).
        Supports sort parameter: position (default), activite, statut.
        Supports contributor filter: ?contributeur=42 (PHASE-26a).
        """
        identifiant_page = request.query_params.get("page_id")
        if not identifiant_page:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=identifiant_page)

        # Refonte A.6 : plus de drawer "analyse en cours" specifique. Si un job
        # tourne, on nettoie quand meme les jobs bloques (pour que les vues
        # ulterieures voient l'etat "error" plutot qu'un faux "processing"),
        # mais on tombe dans le rendu normal : l'utilisateur voit les entites
        # deja extraites comme cartes, et le bouton "taches" de la toolbar le
        # notifiera quand l'analyse sera terminee.
        # / A.6 refactor: no more dedicated "analysis-in-progress" drawer. If a
        # / job is running we still flush stalled jobs (so later views see "error"
        # / rather than a fake "processing" state), but we fall through to the
        # / normal render: the user sees entities already extracted as cards,
        # / and the toolbar "tasks" button will notify them when done.
        job_en_cours_pour_drawer = ExtractionJob.objects.filter(
            page=page,
            status__in=["pending", "processing"],
        ).order_by("-created_at").first()

        if job_en_cours_pour_drawer:
            _verifier_et_nettoyer_job_bloque(job_en_cours_pour_drawer)

        parametre_tri = request.query_params.get("tri", "position")

        # Parametre optionnel : filtre multi-contributeurs, virgule-separee (PHASE-26a-bis)
        # Retro-compatible : ?contributeur=42 (single) fonctionne toujours.
        # / Optional: multi-contributor filter, comma-separated (PHASE-26a-bis)
        # / Backward compat: ?contributeur=42 (single) still works.
        parametre_contributeur = request.query_params.get("contributeur", "")
        ensemble_contributeurs_actifs = set()
        for identifiant_brut in parametre_contributeur.split(","):
            identifiant_brut = identifiant_brut.strip()
            if identifiant_brut:
                try:
                    ensemble_contributeurs_actifs.add(int(identifiant_brut))
                except (ValueError, TypeError):
                    pass

        # Recuperer toutes les entites (masquees et non masquees)
        # / Retrieve all entities (hidden and not hidden)
        tous_les_jobs_termines = ExtractionJob.objects.filter(
            page=page, status="completed",
        )
        toutes_les_entites = ExtractedEntity.objects.filter(
            job__in=tous_les_jobs_termines,
        ).prefetch_related(
            Prefetch(
                "commentaires",
                queryset=CommentaireExtraction.objects.select_related("user"),
            ),
        ).annotate(
            nombre_commentaires=Count("commentaires"),
        )

        # Construire la liste des contributeurs ayant commente ce document (PHASE-26a)
        # / Build the list of contributors who commented on this document (PHASE-26a)
        commentaires_par_contributeur = CommentaireExtraction.objects.filter(
            entity__job__in=tous_les_jobs_termines,
        ).values("user__pk", "user__username", "user__first_name").annotate(
            nombre_commentaires=Count("pk"),
        ).order_by("-nombre_commentaires")

        # Compter le nombre d'entites distinctes par contributeur (PHASE-26a UX)
        # / Count distinct entities per contributor (PHASE-26a UX)
        entites_distinctes_par_contributeur = dict(
            CommentaireExtraction.objects.filter(
                entity__job__in=tous_les_jobs_termines,
            ).values("user__pk").annotate(
                nombre_entites=Count("entity_id", distinct=True),
            ).values_list("user__pk", "nombre_entites")
        )

        # Enrichir la liste des contributeurs avec nombre_entites + couleur HSL (PHASE-26a UX)
        # / Enrich contributor list with nombre_entites + HSL color (PHASE-26a UX)
        liste_contributeurs_enrichie = []
        for contributeur_entry in commentaires_par_contributeur:
            contributeur_enrichi = dict(contributeur_entry)
            contributeur_enrichi["nombre_entites"] = entites_distinctes_par_contributeur.get(
                contributeur_entry["user__pk"], 0,
            )
            contributeur_enrichi["couleur_hsl"] = _calculer_teinte_contributeur(
                contributeur_entry["user__username"],
            )
            liste_contributeurs_enrichie.append(contributeur_enrichi)

        # Compter le total AVANT filtre pour afficher "N sur M" (PHASE-26a UX)
        # / Count total BEFORE filter to display "N out of M" (PHASE-26a UX)
        nombre_total_sans_filtre = toutes_les_entites.count()

        # Mode filtre : inclure (defaut) ou exclure (PHASE-26a UX)
        # / Filter mode: inclure (default) or exclure (PHASE-26a UX)
        mode_filtre = request.query_params.get("mode_filtre", "inclure")

        # Si des contributeurs sont filtres, garder ou exclure les entites commentees
        # / If contributors are filtered, keep or exclude commented entities
        ids_entites_des_contributeurs = set()
        noms_contributeurs_actifs = []
        if ensemble_contributeurs_actifs:
            ids_entites_des_contributeurs = set(
                CommentaireExtraction.objects.filter(
                    entity__job__in=tous_les_jobs_termines,
                    user_id__in=ensemble_contributeurs_actifs,
                ).values_list("entity_id", flat=True).distinct()
            )
            if mode_filtre == "exclure":
                toutes_les_entites = toutes_les_entites.exclude(
                    pk__in=ids_entites_des_contributeurs,
                )
            else:
                toutes_les_entites = toutes_les_entites.filter(
                    pk__in=ids_entites_des_contributeurs,
                )
            # Recuperer les noms des contributeurs pour les pilules actives
            # / Get contributor names for active pills
            for contributeur_entry in commentaires_par_contributeur:
                if contributeur_entry["user__pk"] in ensemble_contributeurs_actifs:
                    # Majuscule sur le prenom / Capitalize the name
                    nom_affiche = contributeur_entry.get("user__first_name") or contributeur_entry["user__username"]
                    noms_contributeurs_actifs.append(nom_affiche.title())

        # Appliquer le tri / Apply sort order
        # Le tri "statut" a ete retire en A.8 Phase 4-bis : le statut binaire
        # nouveau/commente n'a plus de sens comme critere de tri (FALC).
        # / The "statut" sort was removed in A.8 Phase 4-bis: the binary
        # / new/commented status no longer makes sense as a sort criterion.
        if parametre_tri == "activite":
            toutes_les_entites = toutes_les_entites.order_by("-created_at")
        else:
            toutes_les_entites = toutes_les_entites.order_by("start_char")

        # Separer visibles et masquees (non_pertinent) pour le template
        # / Separate visible and hidden (non_pertinent) for the template
        entites_visibles = []
        entites_masquees = []
        for entite in toutes_les_entites:
            if entite.masquee:
                entites_masquees.append(entite)
            else:
                entites_visibles.append(entite)

        # Emettre HX-Trigger pour le filtrage des pastilles cote JS (PHASE-26a-bis)
        # / Emit HX-Trigger for pastille filtering on JS side (PHASE-26a-bis)
        donnees_trigger = json.dumps({
            "contributeurFiltreChange": {
                "contributeurs_ids": list(ensemble_contributeurs_actifs),
                "ids_entites": list(ids_entites_des_contributeurs) if ensemble_contributeurs_actifs else [],
                "mode_filtre": mode_filtre,
            }
        })

        # Determiner si l'utilisateur est proprietaire du dossier
        # / Determine if user is the folder owner
        est_proprietaire = _est_proprietaire_dossier(request.user, page)

        # Recuperer le dernier job termine pour le bandeau resume du drawer
        # / Get the last completed job for the drawer summary banner
        dernier_job_termine_pour_bandeau = tous_les_jobs_termines.order_by("-created_at").first()

        reponse = render(request, "front/includes/drawer_vue_liste.html", {
            "page": page,
            "entites_visibles": entites_visibles,
            "entites_masquees": entites_masquees,
            "nombre_masquees": len(entites_masquees),
            "nombre_total": len(entites_visibles) + len(entites_masquees),
            "nombre_total_sans_filtre": nombre_total_sans_filtre,
            "tri_actuel": parametre_tri,
            "liste_contributeurs": liste_contributeurs_enrichie,
            "contributeurs_actifs": ensemble_contributeurs_actifs,
            "noms_contributeurs_actifs": noms_contributeurs_actifs,
            "ids_entites_des_contributeurs": ids_entites_des_contributeurs,
            "mode_filtre": mode_filtre,
            "est_proprietaire": est_proprietaire,
            "dernier_job": dernier_job_termine_pour_bandeau,
        })

        reponse["HX-Trigger"] = donnees_trigger
        return reponse


class ImportViewSet(viewsets.ViewSet):
    """
    ViewSet pour l'import de fichiers (documents + audio).
    Convertit le fichier en HTML/texte et cree une Page.
    Les fichiers audio sont traites en async via Celery.
    / ViewSet for file import (documents + audio).
    Converts the file to HTML/text and creates a Page.
    Audio files are processed asynchronously via Celery.
    """

    @action(detail=False, methods=["POST"])
    def fichier(self, request):
        """
        Importe un fichier. Branche vers le pipeline audio si c'est un fichier audio,
        sinon pipeline synchrone pour les documents.
        / Imports a file. Branches to audio pipeline if audio file,
        otherwise synchronous pipeline for documents.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        # Validation via serializer DRF
        # / Validation via DRF serializer
        serializer = ImportFichierSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("import fichier: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        fichier_uploade = serializer.validated_data["fichier"]
        nom_fichier = fichier_uploade.name

        # Aiguillage : JSON → transcription pre-traitee, audio → async, document → synchrone
        # / Routing: JSON → pre-processed transcription, audio → async, document → synchronous
        if est_fichier_json(nom_fichier):
            return self._importer_fichier_json(request, serializer)
        elif est_fichier_audio(nom_fichier):
            return self._importer_fichier_audio(request, serializer)
        else:
            return self._importer_fichier_document(request, serializer)

    def _importer_fichier_json(self, request, serializer):
        """
        Pipeline d'import pour les fichiers JSON de transcription pre-traitee (ex: Voxtral).
        Le JSON doit contenir une cle 'segments' (list de dicts avec speaker/start/end/text).
        Stocke le JSON complet dans transcription_raw et genere le HTML diarise.
        / Import pipeline for pre-processed transcription JSON files (e.g. Voxtral).
        The JSON must contain a 'segments' key (list of dicts with speaker/start/end/text).
        Stores the full JSON in transcription_raw and generates diarized HTML.
        """
        import hashlib
        from front.services.transcription_audio import construire_html_diarise

        fichier_uploade = serializer.validated_data["fichier"]
        titre_personnalise = serializer.validated_data.get("titre", "")
        dossier_id = serializer.validated_data.get("dossier_id")
        nom_fichier = fichier_uploade.name

        # Lire et parser le contenu JSON
        # / Read and parse JSON content
        try:
            contenu_brut = fichier_uploade.read().decode("utf-8")
            donnees_json = json.loads(contenu_brut)
        except (UnicodeDecodeError, json.JSONDecodeError) as erreur_json:
            logger.warning("import JSON: parsing echoue — %s", erreur_json)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: fichier JSON invalide ({erreur_json})</p>',
                status=400,
            )

        # Valider la structure : doit contenir 'segments' (list)
        # / Validate structure: must contain 'segments' (list)
        if not isinstance(donnees_json, dict) or "segments" not in donnees_json:
            return HttpResponse(
                '<p class="text-sm text-red-500">Erreur: le JSON doit contenir une clé "segments"</p>',
                status=400,
            )

        liste_segments = donnees_json["segments"]
        if not isinstance(liste_segments, list) or len(liste_segments) == 0:
            return HttpResponse(
                '<p class="text-sm text-red-500">Erreur: "segments" doit être une liste non vide</p>',
                status=400,
            )

        # Construire le HTML colore par locuteur et le texte brut
        # / Build speaker-colored HTML and plain text
        html_diarise, texte_brut = construire_html_diarise(donnees_json)

        # Calculer le hash du contenu / Compute content hash
        hash_contenu = hashlib.sha256(texte_brut.encode("utf-8")).hexdigest()

        # Determiner le titre final et le dossier
        # / Determine final title and folder
        nom_sans_extension = os.path.splitext(nom_fichier)[0]
        titre_final = titre_personnalise.strip() if titre_personnalise.strip() else nom_sans_extension
        if dossier_id:
            dossier_assigne = Dossier.objects.filter(pk=dossier_id).first()
        else:
            # Auto-classement dans "Mes imports" si pas de dossier specifie
            # / Auto-classify in "Mes imports" if no folder specified
            dossier_assigne = _obtenir_ou_creer_dossier_imports(request.user)

        # Sauvegarder le fichier JSON original dans source_file
        # / Save the original JSON file in source_file
        from django.core.files.base import ContentFile
        contenu_fichier_source = ContentFile(contenu_brut.encode("utf-8"), name=nom_fichier)

        # Creer la Page avec source_type='audio' et le JSON complet en transcription_raw
        # / Create Page with source_type='audio' and full JSON in transcription_raw
        page_importee = Page.objects.create(
            source_type="audio",
            original_filename=nom_fichier,
            url=None,
            title=titre_final,
            html_original="",
            html_readability=html_diarise,
            text_readability=texte_brut,
            content_hash=hash_contenu,
            transcription_raw=donnees_json,
            status="completed",
            dossier=dossier_assigne,
            source_file=contenu_fichier_source,
            owner=request.user,
        )

        logger.info(
            "import JSON: page pk=%s creee depuis '%s' (%d segments)",
            page_importee.pk, nom_fichier, len(liste_segments),
        )

        # Rendu du partial de lecture + OOB arbre et panneau (meme pattern que document)
        # / Render reading partial + OOB tree and panel (same pattern as document)
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")
        ia_active = _get_ia_active()
        contexte_partage = {
            "page": page_importee,
            "html_annote": None,
            "analyseurs_actifs": analyseurs_actifs,
            "job": None,
            "entities": None,
            "ia_active": ia_active,
        }

        html_lecture = render_to_string(
            "front/includes/lecture_principale.html",
            contexte_partage,
            request=request,
        )

        # OOB swap : arbre de dossiers mis a jour
        # / OOB swap: updated folder tree
        # OOB swap : arbre via _render_arbre / OOB swap: tree via _render_arbre
        reponse_arbre = _render_arbre(request)
        html_arbre_oob = (
            '<div id="arbre" hx-swap-oob="innerHTML:#arbre">'
            + reponse_arbre.content.decode()
            + '</div>'
        )

        # OOB swap : panneau d'analyse reinitialise
        # / OOB swap: reset analysis panel
        html_panneau_oob = render_to_string(
            "front/includes/panneau_analyse.html",
            contexte_partage,
            request=request,
        )
        html_panneau_oob = (
            '<div id="panneau-extractions" hx-swap-oob="innerHTML:#panneau-extractions">'
            + html_panneau_oob
            + '</div>'
        )

        html_complet = html_lecture + html_arbre_oob + html_panneau_oob
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Transcription JSON importée"},
        })
        return reponse

    def _importer_fichier_audio(self, request, serializer):
        """
        Pipeline d'import audio : sauvegarde temp, cree Page en processing,
        lance la tache Celery, retourne le template de polling.
        / Audio import pipeline: save temp, create Page as processing,
        launch Celery task, return polling template.
        """
        import os
        import uuid
        from django.conf import settings
        from core.models import TranscriptionConfig, TranscriptionJob

        fichier_uploade = serializer.validated_data["fichier"]
        titre_personnalise = serializer.validated_data.get("titre", "")
        dossier_id = serializer.validated_data.get("dossier_id")
        nom_fichier = fichier_uploade.name
        extension_fichier = os.path.splitext(nom_fichier)[1].lower()

        # Sauvegarder le fichier audio dans AUDIO_TEMP_DIR avec un nom unique
        # / Save audio file to AUDIO_TEMP_DIR with a unique name
        nom_unique = f"{uuid.uuid4().hex}{extension_fichier}"
        chemin_fichier_audio = str(settings.AUDIO_TEMP_DIR / nom_unique)

        with open(chemin_fichier_audio, "wb") as destination:
            for morceau in fichier_uploade.chunks():
                destination.write(morceau)

        logger.info(
            "import audio: fichier sauvegarde %s (%s)",
            chemin_fichier_audio, nom_fichier,
        )

        # Determiner le titre et le dossier
        # / Determine title and folder
        nom_sans_extension = os.path.splitext(nom_fichier)[0]
        titre_final = titre_personnalise.strip() if titre_personnalise.strip() else nom_sans_extension
        if dossier_id:
            dossier_assigne = Dossier.objects.filter(pk=dossier_id).first()
        else:
            # Auto-classement dans "Mes imports" si pas de dossier specifie
            # / Auto-classify in "Mes imports" if no folder specified
            dossier_assigne = _obtenir_ou_creer_dossier_imports(request.user)

        # Sauvegarder le fichier audio dans source_file
        # / Save the audio file in source_file
        fichier_uploade.seek(0)

        # Creer la Page en status "processing" avec un placeholder HTML
        # / Create Page in "processing" status with a placeholder HTML
        page_audio = Page.objects.create(
            source_type="audio",
            original_filename=nom_fichier,
            url=None,
            title=titre_final,
            html_original="",
            html_readability='<p class="text-slate-400 italic">Transcription en cours...</p>',
            text_readability="",
            content_hash="",
            status="processing",
            dossier=dossier_assigne,
            source_file=fichier_uploade,
            owner=request.user,
        )

        # Recuperer la config de transcription active (ou None pour mock)
        # / Get active transcription config (or None for mock)
        config_transcription_active = TranscriptionConfig.objects.filter(
            is_active=True,
        ).first()

        # Creer le TranscriptionJob
        # / Create the TranscriptionJob
        job_transcription = TranscriptionJob.objects.create(
            page=page_audio,
            transcription_config=config_transcription_active,
            audio_filename=nom_fichier,
            status="pending",
        )

        # Lancer la tache Celery en arriere-plan
        # / Launch the Celery task in background
        from front.tasks import transcrire_audio_task
        # Nombre max de locuteurs et langue depuis la config
        # / Max speakers and language from config
        max_locuteurs_config = config_transcription_active.max_speakers if config_transcription_active else 5
        langue_config = config_transcription_active.language if config_transcription_active else "fr"
        resultat_tache = transcrire_audio_task.delay(
            job_transcription.pk, chemin_fichier_audio, max_locuteurs_config, langue_config,
        )

        # Stocker l'ID Celery dans le job
        # / Store Celery ID in the job
        job_transcription.celery_task_id = resultat_tache.id
        job_transcription.save(update_fields=["celery_task_id"])

        logger.info(
            "import audio: page pk=%s job pk=%s celery_id=%s",
            page_audio.pk, job_transcription.pk, resultat_tache.id,
        )

        # Refonte A.6 : plus de template "transcription en cours" avec polling.
        # On renvoie uniquement le swap OOB de l'arbre + un toast indiquant que
        # la transcription a demarre. Le bouton "taches" de la toolbar notifiera
        # l'utilisateur quand la transcription sera terminee.
        # / A.6 refactor: no more "transcription-in-progress" polling template.
        # / We only return the OOB tree swap + a toast indicating transcription
        # / has started. The toolbar "tasks" button will notify the user when
        # / transcription completes.
        reponse_arbre = _render_arbre(request)
        html_arbre_oob = (
            '<div id="arbre" hx-swap-oob="innerHTML:#arbre">'
            + reponse_arbre.content.decode()
            + '</div>'
        )

        reponse = HttpResponse(html_arbre_oob)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Transcription lanc\u00e9e..."},
        })
        return reponse

    def _importer_fichier_document(self, request, serializer):
        """
        Pipeline d'import synchrone pour les documents (PDF, DOCX, etc.).
        / Synchronous import pipeline for documents (PDF, DOCX, etc.).
        """
        import hashlib
        from front.services.conversion_fichiers import convertir_fichier_en_html

        fichier_uploade = serializer.validated_data["fichier"]
        titre_personnalise = serializer.validated_data.get("titre", "")
        dossier_id = serializer.validated_data.get("dossier_id")
        nom_fichier = fichier_uploade.name

        # Conversion du fichier en HTML + texte
        # / Convert file to HTML + text
        try:
            html_readability, text_readability, titre_extrait = convertir_fichier_en_html(
                fichier_uploade, nom_fichier,
            )
        except ValueError as erreur_conversion:
            logger.error("import fichier: erreur conversion — %s", erreur_conversion)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur de conversion: {erreur_conversion}</p>',
                status=400,
            )
        except Exception as erreur_inattendue:
            logger.error("import fichier: erreur inattendue — %s", erreur_inattendue, exc_info=True)
            return HttpResponse(
                '<p class="text-sm text-red-500">Erreur inattendue lors de la conversion du fichier.</p>',
                status=500,
            )

        # Determiner le titre final et le dossier
        # / Determine final title and folder
        titre_final = titre_personnalise.strip() if titre_personnalise.strip() else titre_extrait
        if dossier_id:
            dossier_assigne = Dossier.objects.filter(pk=dossier_id).first()
        else:
            # Auto-classement dans "Mes imports" si pas de dossier specifie
            # / Auto-classify in "Mes imports" if no folder specified
            dossier_assigne = _obtenir_ou_creer_dossier_imports(request.user)

        # Calculer le hash du contenu pour content_hash
        # / Compute content hash
        hash_contenu = hashlib.sha256(text_readability.encode("utf-8")).hexdigest()

        # Sauvegarder le fichier original dans source_file
        # / Save original file in source_file
        fichier_uploade.seek(0)

        # Creer la Page avec source_type='file'
        # / Create the Page with source_type='file'
        page_importee = Page.objects.create(
            source_type="file",
            original_filename=nom_fichier,
            url=None,
            title=titre_final,
            html_original=html_readability,
            html_readability=html_readability,
            text_readability=text_readability,
            content_hash=hash_contenu,
            dossier=dossier_assigne,
            source_file=fichier_uploade,
            owner=request.user,
        )

        logger.info(
            "import fichier: page pk=%s creee depuis '%s' (%d chars HTML)",
            page_importee.pk, nom_fichier, len(html_readability),
        )

        # Rendu du partial de lecture + OOB arbre et panneau
        # / Render reading partial + OOB tree and panel
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")
        ia_active = _get_ia_active()
        contexte_partage = {
            "page": page_importee,
            "html_annote": None,
            "analyseurs_actifs": analyseurs_actifs,
            "job": None,
            "entities": None,
            "ia_active": ia_active,
        }

        html_lecture = render_to_string(
            "front/includes/lecture_principale.html",
            contexte_partage,
            request=request,
        )

        # OOB swap : arbre de dossiers mis a jour
        # / OOB swap: updated folder tree
        # OOB swap : arbre via _render_arbre / OOB swap: tree via _render_arbre
        reponse_arbre = _render_arbre(request)
        html_arbre_oob = (
            '<div id="arbre" hx-swap-oob="innerHTML:#arbre">'
            + reponse_arbre.content.decode()
            + '</div>'
        )

        # OOB swap : panneau d'analyse reinitialise
        # / OOB swap: reset analysis panel
        html_panneau_oob = render_to_string(
            "front/includes/panneau_analyse.html",
            contexte_partage,
            request=request,
        )
        html_panneau_oob = (
            '<div id="panneau-extractions" hx-swap-oob="innerHTML:#panneau-extractions">'
            + html_panneau_oob
            + '</div>'
        )

        html_complet = html_lecture + html_arbre_oob + html_panneau_oob
        reponse = HttpResponse(html_complet)
        # Indique au front l'URL a pusher dans l'historique navigateur.
        # L'import est fait via XMLHttpRequest (pas HTMX direct), donc le JS
        # d'import lit ce header et appelle history.pushState manuellement.
        # / Tells the front the URL to push in browser history. Import goes
        # / via XMLHttpRequest, so the JS reads this header and pushState manually.
        reponse["X-Hypostasia-Page-Url"] = f"/lire/{page_importee.pk}/"
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Fichier import\u00e9"},
        })
        return reponse

    @action(detail=False, methods=["POST"], url_path="previsualiser_audio")
    def previsualiser_audio(self, request):
        """
        Recoit le fichier audio, le sauvegarde en temp, calcule la duree,
        et retourne un partial de confirmation avec estimation de cout.
        / Receives the audio file, saves it temporarily, computes duration,
        and returns a confirmation partial with cost estimate.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        import os
        import uuid
        from django.conf import settings
        from core.models import TranscriptionConfig

        # Validation via serializer DRF
        # / Validation via DRF serializer
        serializer = ImportFichierSerializer(data=request.data)
        if not serializer.is_valid():
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        fichier_uploade = serializer.validated_data["fichier"]
        nom_fichier = fichier_uploade.name
        extension_fichier = os.path.splitext(nom_fichier)[1].lower()

        # Sauvegarder le fichier audio dans AUDIO_TEMP_DIR avec un nom unique
        # / Save audio file to AUDIO_TEMP_DIR with a unique name
        nom_unique = f"{uuid.uuid4().hex}{extension_fichier}"
        chemin_fichier_audio = str(settings.AUDIO_TEMP_DIR / nom_unique)

        with open(chemin_fichier_audio, "wb") as destination:
            for morceau in fichier_uploade.chunks():
                destination.write(morceau)

        # Calculer la duree du fichier audio (mutagen + ffprobe fallback)
        # / Compute audio file duration (mutagen + ffprobe fallback)
        from front.services.transcription_audio import calculer_duree_audio
        duree_secondes = calculer_duree_audio(chemin_fichier_audio)

        # Recuperer la config de transcription active
        # / Get active transcription config
        config_transcription = TranscriptionConfig.objects.filter(is_active=True).first()
        if not config_transcription:
            reponse = HttpResponse(status=400)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Transcription non configur\u00e9e. Ajoutez MISTRAL_API_KEY dans .env puis relancez install.sh.",
                    "icon": "error",
                },
            })
            return reponse

        # Calcul du cout estime en euros — marge x2, minimum 0.01€
        # / Compute estimated cost in euros — x2 margin, minimum 0.01€
        import math
        cout_brut_euros = 0.0
        if config_transcription:
            cout_brut_euros = config_transcription.estimer_cout_euros(duree_secondes)
        cout_estime_euros = max(0.01, math.ceil(cout_brut_euros * 2 * 100) / 100)

        # Formater la duree en minutes:secondes pour affichage
        # / Format duration as minutes:seconds for display
        minutes_duree = int(duree_secondes // 60)
        secondes_restantes = int(duree_secondes % 60)
        duree_formatee = f"{minutes_duree}:{secondes_restantes:02d}"

        # Taille du fichier en Mo / File size in MB
        taille_fichier_mo = os.path.getsize(chemin_fichier_audio) / (1024 * 1024)

        # Langue par defaut depuis la config / Default language from config
        langue_defaut = config_transcription.language if config_transcription else ""

        return render(request, "front/includes/confirmation_audio.html", {
            "nom_fichier": nom_fichier,
            "chemin_fichier_temp": nom_unique,
            "duree_formatee": duree_formatee,
            "duree_secondes": round(duree_secondes, 1),
            "taille_fichier_mo": round(taille_fichier_mo, 2),
            "config_transcription": config_transcription,
            "cout_estime_euros": cout_estime_euros,
            "langue_defaut": langue_defaut,
        })

    @action(detail=False, methods=["POST"], url_path="confirmer_audio")
    def confirmer_audio(self, request):
        """
        Lance la transcription d'un fichier audio deja sauvegarde en temp.
        Recoit le nom du fichier temp (pas le fichier lui-meme).
        / Launches transcription of an already temp-saved audio file.
        Receives the temp file name (not the file itself).
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        import os
        from django.conf import settings
        from core.models import TranscriptionConfig, TranscriptionJob

        nom_fichier_temp = request.data.get("chemin_fichier_temp", "")
        nom_fichier_original = request.data.get("nom_fichier", "Fichier audio")
        titre_personnalise = request.data.get("titre", "")
        dossier_id = request.data.get("dossier_id")

        # Nombre max de locuteurs choisi par l'utilisateur (defaut: 5)
        # / Max speakers count chosen by the user (default: 5)
        try:
            max_locuteurs = int(request.data.get("max_speakers", 5))
            max_locuteurs = max(1, min(max_locuteurs, 10))
        except (ValueError, TypeError):
            max_locuteurs = 5

        # Langue de l'audio choisie par l'utilisateur (vide = detection auto)
        # / Audio language chosen by the user (empty = auto-detect)
        langue_audio = request.data.get("language", "").strip()

        if not nom_fichier_temp:
            return HttpResponse("Fichier temporaire introuvable.", status=400)

        chemin_fichier_audio = str(settings.AUDIO_TEMP_DIR / nom_fichier_temp)
        if not os.path.exists(chemin_fichier_audio):
            return HttpResponse("Le fichier temporaire a expire ou n'existe plus.", status=400)

        # Determiner le titre et le dossier
        # / Determine title and folder
        nom_sans_extension = os.path.splitext(nom_fichier_original)[0]
        titre_final = titre_personnalise.strip() if titre_personnalise.strip() else nom_sans_extension
        if dossier_id:
            dossier_assigne = Dossier.objects.filter(pk=dossier_id).first()
        else:
            # Auto-classement dans "Mes imports" si pas de dossier specifie
            # / Auto-classify in "Mes imports" if no folder specified
            dossier_assigne = _obtenir_ou_creer_dossier_imports(request.user)

        # Sauvegarder le fichier audio dans source_file depuis le fichier temp
        # / Save the audio file in source_file from the temp file
        from django.core.files.base import File as DjangoFile
        fichier_audio_pour_source = open(chemin_fichier_audio, "rb")
        fichier_django_source = DjangoFile(fichier_audio_pour_source, name=nom_fichier_original)

        # Creer la Page en status "processing"
        # / Create Page in "processing" status
        page_audio = Page.objects.create(
            source_type="audio",
            original_filename=nom_fichier_original,
            url=None,
            title=titre_final,
            html_original="",
            html_readability='<p class="text-slate-400 italic">Transcription en cours...</p>',
            text_readability="",
            content_hash="",
            status="processing",
            dossier=dossier_assigne,
            source_file=fichier_django_source,
            owner=request.user,
        )
        fichier_audio_pour_source.close()

        # Recuperer la config de transcription active (ou None pour mock)
        # / Get active transcription config (or None for mock)
        config_transcription_active = TranscriptionConfig.objects.filter(
            is_active=True,
        ).first()

        # Creer le TranscriptionJob
        # / Create the TranscriptionJob
        job_transcription = TranscriptionJob.objects.create(
            page=page_audio,
            transcription_config=config_transcription_active,
            audio_filename=nom_fichier_original,
            status="pending",
        )

        # Lancer la tache Celery en arriere-plan
        # / Launch the Celery task in background
        from front.tasks import transcrire_audio_task
        resultat_tache = transcrire_audio_task.delay(
            job_transcription.pk, chemin_fichier_audio, max_locuteurs, langue_audio,
        )

        # Stocker l'ID Celery dans le job
        # / Store Celery ID in the job
        job_transcription.celery_task_id = resultat_tache.id
        job_transcription.save(update_fields=["celery_task_id"])

        logger.info(
            "confirmer_audio: page pk=%s job pk=%s celery_id=%s",
            page_audio.pk, job_transcription.pk, resultat_tache.id,
        )

        # Refonte A.6 : plus de template "transcription en cours" avec polling.
        # On renvoie uniquement le swap OOB de l'arbre + un toast indiquant que
        # la transcription a demarre. Le bouton "taches" de la toolbar notifiera
        # l'utilisateur quand la transcription sera terminee.
        # / A.6 refactor: no more "transcription-in-progress" polling template.
        # / We only return the OOB tree swap + a toast indicating transcription
        # / has started. The toolbar "tasks" button will notify the user when
        # / transcription completes.
        reponse_arbre = _render_arbre(request)
        html_arbre_oob = (
            '<div id="arbre" hx-swap-oob="innerHTML:#arbre">'
            + reponse_arbre.content.decode()
            + '</div>'
        )

        reponse = HttpResponse(html_arbre_oob)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Transcription lancée..."},
        })
        return reponse


class QuestionnaireViewSet(viewsets.ViewSet):
    """
    ViewSet pour le questionnaire — questions et reponses liees a une page.
    / ViewSet for the questionnaire — questions and answers linked to a page.
    """

    def _render_questionnaire(self, request, page):
        """
        Helper — rend le partial du questionnaire pour une page.
        / Helper — renders the questionnaire partial for a page.
        """
        toutes_les_questions = Question.objects.filter(
            page=page,
        ).prefetch_related("reponses").order_by("-created_at")

        return render(request, "front/includes/vue_questionnaire.html", {
            "page": page,
            "toutes_les_questions": toutes_les_questions,
        })

    def list(self, request):
        """
        Affiche le questionnaire pour une page (GET avec ?page_id=...).
        / Displays the questionnaire for a page (GET with ?page_id=...).
        """
        page_id = request.query_params.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=page_id)
        return self._render_questionnaire(request, page)

    @action(detail=False, methods=["POST"], url_path="poser_question")
    def poser_question(self, request):
        """
        Cree une nouvelle question sur une page et re-rend le questionnaire.
        / Creates a new question on a page and re-renders the questionnaire.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        serializer = QuestionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("poser_question: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        donnees = serializer.validated_data
        page = get_object_or_404(Page, pk=donnees["page_id"])

        # Creer la question / Create the question
        Question.objects.create(
            page=page,
            user=request.user,
            texte_question=donnees["texte_question"],
        )

        reponse = self._render_questionnaire(request, page)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Question ajout\u00e9e"},
        })
        return reponse

    @action(detail=False, methods=["POST"])
    def repondre(self, request):
        """
        Cree une reponse a une question et re-rend le questionnaire.
        / Creates an answer to a question and re-renders the questionnaire.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus
        serializer = ReponseQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("repondre: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        donnees = serializer.validated_data
        question = get_object_or_404(Question, pk=donnees["question_id"])

        # Creer la reponse / Create the answer
        ReponseQuestion.objects.create(
            question=question,
            user=request.user,
            texte_reponse=donnees["texte_reponse"],
        )

        reponse_http = self._render_questionnaire(request, question.page)
        reponse_http["HX-Trigger"] = json.dumps({
            "showToast": {"message": "R\u00e9ponse ajout\u00e9e"},
        })
        return reponse_http
