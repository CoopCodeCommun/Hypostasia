"""
ViewSet pour le bouton 'taches en cours' dans la toolbar (refonte A.6).
- bouton() : renvoie l'etat actuel du bouton (compteurs + couleur)
- dropdown() : renvoie la liste des 10 dernieres taches + OOB swap du bouton
- marquer_lue() : cree une ligne NotificationTacheLue pour ce destinataire (correction 1, 11 aout)
/ ViewSet for the 'tasks in progress' button in the toolbar (A.6 refactor).

LOCALISATION : front/views_taches.py
"""
from datetime import timedelta

from django.db.models import F
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from core.models import EtatIngestion, NotificationTacheLue, Page, TranscriptionJob, TypeDeTache
from hypostasis_extractor.models import ExtractionJob

from .views import (
    DELAI_INGESTION_FANTOME_MIN,
    _est_proprietaire_page,
    _filtre_proprietaire_page,
    _marquer_tache_lue_pour,
    _type_tache_stocke,
)


def _ids_taches_lues_par(utilisateur, type_tache_stocke):
    """
    QuerySet des tache_id que `utilisateur` a deja marques lus pour ce
    type — utilise en anti-jointure (exclude(pk__in=...)) : reste UNE
    seule requete SQL (sous-requete), jamais une requete separee.
    / Anti-join source: stays a single SQL query (subquery), never a
    separate round trip.

    LOCALISATION : front/views_taches.py
    """
    return NotificationTacheLue.objects.filter(
        utilisateur=utilisateur, type_tache=type_tache_stocke,
    ).values_list("tache_id", flat=True)


def _rangs_dans_la_file_d_ingestion():
    """
    Rend {pk_de_page: rang} pour toute la file d'ingestion Docling.
    / Returns {page_pk: rank} for the whole Docling ingestion queue.

    LOCALISATION : front/views_taches.py

    POURQUOI CETTE FONCTION NE FILTRE PAS PAR PROPRIETAIRE

    C'est la seule du fichier dans ce cas, et c'est deliberé (decision du
    mainteneur, 14 aout 2026). La file d'ingestion est GLOBALE : un seul
    worker la sert, a concurrence 1, sans distinction d'utilisateur. Un
    rang calcule sur mes seules pages afficherait « 1ᵉʳ » pendant que
    quatre notes d'autrui passent devant — un chiffre faux vaut moins
    que pas de chiffre.

    Ce qui sort d'ici est un ENTIER DE CHARGE, et rien d'autre : ni
    titre, ni proprietaire, ni contenu. C'est l'information que donnerait
    un temps d'attente estime.
    / The only unfiltered query in this file, on purpose: the queue is
    global. What leaks is one integer of load, nothing else.

    POURQUOI TOUTE LA FILE D'UN COUP

    Le menu peut afficher plusieurs notes en attente. Calculer le rang
    note par note ferait une requete par ligne — et le menu deviendrait
    couteux exactement le jour ou la file s'allonge, c'est-a-dire le
    jour ou il sert. Une requete rend la file entiere, ordonnee.
    / One query for the whole queue: per-row ranking would get expensive
    precisely when the queue gets long.

    :return: dict {pk de page: rang, a partir de 1}, limite aux pages
        reellement en attente (les fantomes sont exclus)
    """
    # Meme regle de peremption que _calculer_etat_bouton : une page que
    # personne ne traite plus (worker mort) ne doit pas decaler le rang
    # de tout le monde, definitivement.
    # / Same ghost rule as the badge counter: an abandoned page must not
    # shift everyone's rank forever.
    seuil_fantome = timezone.now() - timedelta(minutes=DELAI_INGESTION_FANTOME_MIN)
    pks_des_pages_en_attente = Page.objects.filter(
        ingestion_etat=EtatIngestion.EN_ATTENTE,
        ingestion_maj_le__gte=seuil_fantome,
    ).order_by(
        # `pk` en second critere : deux imports dans la meme microseconde
        # doivent recevoir deux rangs distincts et stables d'un
        # rafraichissement a l'autre.
        # / pk breaks ties: same-microsecond imports need distinct,
        # stable ranks across refreshes.
        "ingestion_maj_le", "pk",
    ).values_list("pk", flat=True)

    return {
        pk_de_page: rang
        for rang, pk_de_page in enumerate(pks_des_pages_en_attente, start=1)
    }


def _ordinal_francais(rang):
    """
    Rend "1ᵉʳ", "2ᵉ", "3ᵉ"… / Returns French ordinals.

    LOCALISATION : front/views_taches.py

    Le premier rang s'ecrit differemment des autres. C'est du francais
    lu par un humain, pas une numerotation technique — le calcul est
    fait ici plutot que dans le gabarit, qui n'a pas a porter de regle
    de langue. / French writes the first ordinal differently; the rule
    belongs here, not in the template.
    """
    if rang == 1:
        return "1ᵉʳ"
    return f"{rang}ᵉ"


def _calculer_etat_bouton(user):
    """
    Calcule l'etat du bouton + les compteurs pour un utilisateur.
    Priorite : erreur > succes > en_cours > neutre.
    / Compute button state + counters for a user.
    Priority: erreur > succes > en_cours > neutre.

    LOCALISATION : front/views_taches.py

    Perimetre ELARGI (defaut 1, revue de cloture du 11 aout) :
    _filtre_proprietaire_page (front/views.py) reproduit
    _est_proprietaire_page — proprietaire de la note OU proprietaire
    d'un carnet qui la contient — pour matcher exactement qui
    _destinataires_de_notification (front/tasks.py) previent. Ecrit en
    filtre de requete (pas en boucle par objet) pour eviter le N+1.
    / Widened scope to match notification recipients; expressed as a
    query filter, not a per-object loop, to avoid N+1.
    """
    # Comptage taches en cours / Count tasks in progress
    nombre_extractions_en_cours = ExtractionJob.objects.filter(
        _filtre_proprietaire_page("page__", user),
        status__in=["pending", "processing"],
    ).distinct().count()
    nombre_transcriptions_en_cours = TranscriptionJob.objects.filter(
        _filtre_proprietaire_page("page__", user),
        status__in=["pending", "processing"],
    ).distinct().count()
    # Les ingestions n'ont pas de job : leur etat vit sur la Page.
    # `ingestion_etat` vide = aucune ingestion demandee (un .txt, une page
    # nee avant le moteur ELEMENT) : ce n'est pas une tache.
    # / Ingestions have no job; an empty state means no task at all.
    # Defaut 2 (revue de cloture du 11 aout) : un etat actif sans mise
    # a jour depuis DELAI_INGESTION_FANTOME_MIN est un FANTOME (worker
    # mort) — meme regle que relancer_ingestion (front/views.py), sinon
    # le badge reste allume pour toujours.
    # Correction 2 (revue de cloture du 11 aout, meme jour) : filter(__gte=seuil)
    # au lieu de exclude(__lt=seuil) — une comparaison NULL est TOUJOURS
    # inconnue en SQL, donc exclue d'un filter(). Un etat actif SANS
    # ingestion_maj_le (le bug corrige de core/views.py, plus jamais
    # produit desormais) est ainsi traite comme un fantome : sans date,
    # rien ne prouve qu'il est recent.
    # / filter(__gte=) instead of exclude(__lt=): a NULL comparison is
    # always unknown in SQL, so filter() drops it — an active state
    # with no timestamp is now treated as a ghost.
    seuil_fantome = timezone.now() - timedelta(minutes=DELAI_INGESTION_FANTOME_MIN)
    nombre_ingestions_en_cours = Page.objects.filter(
        _filtre_proprietaire_page("", user),
        ingestion_etat__in=[EtatIngestion.EN_ATTENTE, EtatIngestion.EN_COURS],
        ingestion_maj_le__gte=seuil_fantome,
    ).distinct().count()
    nombre_en_cours = (
        nombre_extractions_en_cours
        + nombre_transcriptions_en_cours
        + nombre_ingestions_en_cours
    )

    # Comptage taches terminees non lues / Count finished unread tasks
    # Correction 1 (revue de cloture du 11 aout) : "non lue" est
    # desormais "aucune ligne NotificationTacheLue pour CET
    # utilisateur" — anti-jointure en sous-requete (exclude(pk__in=...)),
    # pas une requete separee ni une boucle : le cout en requetes ne
    # bouge pas (voir le rapport de tache).
    # / "Unread" is now "no NotificationTacheLue row for THIS user" —
    # an anti-join subquery, not an extra round trip.
    nombre_extractions_non_lues = ExtractionJob.objects.filter(
        _filtre_proprietaire_page("page__", user),
        status__in=["completed", "error"],
    ).exclude(
        pk__in=_ids_taches_lues_par(user, TypeDeTache.EXTRACTION),
    ).distinct().count()
    nombre_transcriptions_non_lues = TranscriptionJob.objects.filter(
        _filtre_proprietaire_page("page__", user),
        status__in=["completed", "error"],
    ).exclude(
        pk__in=_ids_taches_lues_par(user, TypeDeTache.TRANSCRIPTION),
    ).distinct().count()
    nombre_ingestions_non_lues = Page.objects.filter(
        _filtre_proprietaire_page("", user),
        ingestion_etat__in=[EtatIngestion.REUSSIE, EtatIngestion.ECHOUEE],
    ).exclude(
        pk__in=_ids_taches_lues_par(user, TypeDeTache.INGESTION),
    ).distinct().count()
    nombre_non_lues = (
        nombre_extractions_non_lues
        + nombre_transcriptions_non_lues
        + nombre_ingestions_non_lues
    )

    # Etat dominant : priorite erreur > en_cours > succes > neutre
    # On veut voir 'en_cours' pendant qu'une tache tourne, meme s'il y a
    # des anciennes notifications non lues (ne pas les masquer mais les
    # reporter a la fin de la tache courante).
    # / Dominant state: priority erreur > en_cours > succes > neutre
    # / We want to see 'en_cours' while a task is running, even if there
    # / are unread old notifications (don't mask them but defer to end of
    # / current task).
    a_des_erreurs_non_lues = ExtractionJob.objects.filter(
        _filtre_proprietaire_page("page__", user),
        status="error",
    ).exclude(
        pk__in=_ids_taches_lues_par(user, TypeDeTache.EXTRACTION),
    ).exists() or TranscriptionJob.objects.filter(
        _filtre_proprietaire_page("page__", user),
        status="error",
    ).exclude(
        pk__in=_ids_taches_lues_par(user, TypeDeTache.TRANSCRIPTION),
    ).exists() or Page.objects.filter(
        _filtre_proprietaire_page("", user),
        ingestion_etat=EtatIngestion.ECHOUEE,
    ).exclude(
        pk__in=_ids_taches_lues_par(user, TypeDeTache.INGESTION),
    ).exists()

    if a_des_erreurs_non_lues:
        etat = "erreur"
    elif nombre_en_cours > 0:
        etat = "en_cours"
    elif nombre_non_lues > 0:
        etat = "succes"
    else:
        etat = "neutre"

    return {
        "nombre_en_cours": nombre_en_cours,
        "nombre_non_lues": nombre_non_lues,
        "etat": etat,
    }


class TachesViewSet(viewsets.ViewSet):
    """
    Bouton 'taches en cours' dans la toolbar + dropdown au clic + marquer lue.
    / 'Tasks in progress' button in toolbar + dropdown on click + mark as read.

    LOCALISATION : front/views_taches.py
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["GET"])
    def bouton(self, request):
        """
        Renvoie le HTML du bouton avec son etat actuel (compteur, couleur).
        Appele en reaction a un message WS (via JS dans hypostasia.js).
        / Returns button HTML with current state.
        """
        contexte = _calculer_etat_bouton(request.user)
        return render(request, "front/includes/taches_bouton.html", contexte)

    @action(detail=False, methods=["GET"])
    def dropdown(self, request):
        """
        Renvoie la liste des 30 dernieres taches dans un dropdown
        + OOB swap du bouton pour realignement.
        / Returns 30 most recent tasks in a dropdown + OOB swap button.
        """
        # Taches recentes : 30 dernieres extractions + 30 dernieres transcriptions
        # melangees par created_at desc, max 30 au total. Perimetre
        # ELARGI (defaut 1, revue de cloture du 11 aout) : voir
        # _filtre_proprietaire_page. .distinct() est necessaire — le
        # join sur appartenances_dossiers duplique une ligne par carnet.
        # / Recent tasks: 30 latest extractions + 30 latest transcriptions
        # / merged by created_at desc, max 30 total. Widened scope; the
        # / join can duplicate rows, hence distinct().
        extractions_recentes = list(ExtractionJob.objects.filter(
            _filtre_proprietaire_page("page__", request.user),
        ).select_related("page").order_by("-created_at").distinct()[:30])

        transcriptions_recentes = list(TranscriptionJob.objects.filter(
            _filtre_proprietaire_page("page__", request.user),
        ).select_related("page").order_by("-created_at").distinct()[:30])

        # Annoter le type pour le template / Annotate type for template
        # Une ExtractionJob peut etre soit une analyse, soit une synthese
        # (raw_result.est_synthese=True). On les distingue ici pour l'affichage.
        # / An ExtractionJob can be either an analysis or a synthesis
        # / (raw_result.est_synthese=True). We distinguish here for display.
        # `type_tache` porte la LOGIQUE (marquage lu, cible du lien) et
        # ne bouge pas ; `libelle_de_tache` porte l'AFFICHAGE. Sans lui,
        # produire un wiki, proposer une mise a jour et verifier des
        # citations donnaient trois lignes IDENTIQUES — « Analyse de
        # "Wiki — …" » — parce que tout ce qui n'est pas une synthese
        # tombait dans « analyse » (recette du 10 aout, F8).
        # / type_tache drives logic and stays; libelle_de_tache is new
        # and only drives display: three different actions used to read
        # exactly the same.
        for extraction in extractions_recentes:
            raw = extraction.raw_result or {}
            if raw.get("est_synthese"):
                extraction.type_tache = "synthese"
                # Le lien "Voir le resultat" pointe vers la page V2/V3 creee
                # / "View result" link points to the V2/V3 page created
                extraction.page_resultat_id = raw.get("page_synthese_id") or extraction.page.pk
                extraction.libelle_de_tache = "Synthèse"
            else:
                extraction.type_tache = "analyse"
                extraction.page_resultat_id = extraction.page.pk
                if raw.get("est_verification"):
                    extraction.libelle_de_tache = "Vérification"
                elif raw.get("est_second_avis"):
                    # SANS CETTE BRANCHE, une tache qui peut durer une
                    # heure s'afficherait « Analyse » — le defaut exact
                    # que la recette F8 a corrige plus haut. Le libelle
                    # dit aussi POURQUOI c'est long : le juge tourne
                    # ici, pas chez un fournisseur.
                    # / Without this, an hour-long task would read
                    # "Analyse" — the very defect F8 fixed above.
                    extraction.libelle_de_tache = "Second avis (juge local)"
                elif raw.get("est_maj_wiki"):
                    extraction.libelle_de_tache = "Mise à jour"
                elif raw.get("est_wiki"):
                    extraction.libelle_de_tache = "Wiki"
                elif raw.get("est_synthese_carnet"):
                    extraction.libelle_de_tache = "Synthèse dirigée"
                else:
                    extraction.libelle_de_tache = "Analyse"
        for transcription in transcriptions_recentes:
            transcription.type_tache = "transcription"
            transcription.page_resultat_id = transcription.page.pk
            transcription.libelle_de_tache = "Transcription"

        # Les ingestions recentes de l'utilisateur. On annote les memes
        # attributs que les jobs pour que le template ne connaisse qu'une
        # seule forme. `status` est traduit depuis ingestion_etat : le
        # `status` propre de la Page parle d'autre chose. `page = soi-meme`
        # reproduit la FK `.page` qu'ont ExtractionJob et TranscriptionJob :
        # le gabarit lit `tache.page.title` et (branche erreur)
        # `tache.page.pk` sans savoir que la tache EST la page (complement
        # du brief, piege 1).
        # / Same annotations as jobs, so the template knows one shape only.
        # `page = self` mirrors the `.page` FK of the other two models,
        # since the template reads `tache.page.title`/`tache.page.pk`
        # without knowing an ingestion tache IS the page.
        # Correction 2, second endroit (revue de cloture du 11 aout) :
        # sous PostgreSQL, "-ingestion_maj_le" place les NULL EN TETE
        # (NULLS FIRST par defaut en DESC) — un etat actif fantome sans
        # date (bug corrige de core/views.py) squattait donc le haut du
        # menu devant des ingestions reellement recentes.
        # nulls_last=True les traite comme les plus anciennes possibles,
        # coherent avec le comptage (meme fantome, memes deux endroits
        # a corriger).
        # / Under PostgreSQL, DESC ordering puts NULLs first by default;
        # nulls_last treats a dateless ghost as the oldest possible row.
        ingestions_recentes = list(Page.objects.filter(
            _filtre_proprietaire_page("", request.user),
        ).exclude(ingestion_etat="").order_by(
            F("ingestion_maj_le").desc(nulls_last=True),
        ).distinct()[:30])

        # Le rang de chaque note dans la file d'ingestion, calcule pour
        # toute la file en UNE requete (voir _rangs_dans_la_file_d_ingestion).
        # / Each note's queue rank, computed in ONE query for the lot.
        rangs_dans_la_file = _rangs_dans_la_file_d_ingestion()

        for page_ingeree in ingestions_recentes:
            page_ingeree.type_tache = "ingestion"
            page_ingeree.page_resultat_id = page_ingeree.pk
            page_ingeree.libelle_de_tache = "Découpage"
            page_ingeree.page = page_ingeree
            # Seule une note EN ATTENTE a une position : une note EN
            # COURS a deja quitte la file, elle est sur le worker.
            # `.get()` rend None pour tout le reste — et un fantome, qui
            # n'est dans aucun rang, retombe donc sur « En cours… ».
            # / Only a waiting note has a position; an in-progress one
            # has already left the queue.
            rang_de_la_note = rangs_dans_la_file.get(page_ingeree.pk)
            page_ingeree.position_dans_la_file = (
                _ordinal_francais(rang_de_la_note) if rang_de_la_note else ""
            )
            if page_ingeree.ingestion_etat == EtatIngestion.ECHOUEE:
                page_ingeree.status = "error"
            elif page_ingeree.ingestion_etat == EtatIngestion.REUSSIE:
                page_ingeree.status = "completed"
            else:
                page_ingeree.status = "processing"

        # Fusionner et trier par date desc, garder 30. Cle de tri commune
        # explicite (`date_tri`) plutot que `created_at` brut : pour un
        # job, created_at EST la date de la tache, mais pour une
        # ingestion, created_at est la date de creation de la NOTE — qui
        # peut preceder de loin le decoupage. Utiliser ingestion_maj_le
        # pour les ingestions evite de trier deux sens du temps
        # differents dans le meme sorted().
        # / Common sort key rather than raw created_at: a job's
        # created_at IS its date, but a page's created_at is when the
        # NOTE was made, not when it was ingested.
        for extraction in extractions_recentes:
            extraction.date_tri = extraction.created_at
        for transcription in transcriptions_recentes:
            transcription.date_tri = transcription.created_at
        for page_ingeree in ingestions_recentes:
            page_ingeree.date_tri = page_ingeree.ingestion_maj_le or page_ingeree.created_at

        toutes_taches = sorted(
            extractions_recentes + transcriptions_recentes + ingestions_recentes,
            key=lambda t: t.date_tri,
            reverse=True,
        )[:30]

        contexte_bouton = _calculer_etat_bouton(request.user)

        return render(request, "front/includes/taches_dropdown.html", {
            "taches": toutes_taches,
            **contexte_bouton,
        })

    @action(detail=True, methods=["POST"], url_path="marquer-lue")
    def marquer_lue(self, request, pk=None):
        """
        Marque une notification comme lue. Pk = id du job (ou, pour une
        ingestion qui n'a pas de job, id de la Page elle-meme).
        Le query param ?type=extraction|transcription|ingestion distingue
        les modeles concernes.
        / Marks a notification as read. Pk = job id, or (ingestion has no
        job) the Page id itself.

        LOCALISATION : front/views_taches.py

        Perimetre ELARGI (defaut 1, revue de cloture du 11 aout) : on
        recupere l'objet par pk SEUL, puis on verifie l'acces avec
        _est_proprietaire_page — la MEME fonction que le reste du
        depot, appelee ici sur un objet unique (pas de N+1 : c'est une
        action detail=True, un seul objet). Acces refuse -> Http404,
        JAMAIS 403 (doctrine du projet) : un tiers ne doit pas
        distinguer une tache d'autrui d'une tache inexistante.
        / Widened scope: fetch by pk alone, then check access with the
        same _est_proprietaire_page used everywhere else. No access ->
        Http404, never 403.
        """
        type_tache = request.query_params.get("type")
        # "analyse" et "synthese" pointent tous deux sur ExtractionJob (distinction via raw_result.est_synthese)
        # / "analyse" and "synthese" both point to ExtractionJob (distinguished via raw_result.est_synthese)
        # Correction 1 (revue de cloture du 11 aout) : la lecture ne
        # touche plus le booleen partage du job/de la page — elle cree
        # UNE ligne NotificationTacheLue pour CE destinataire.
        # / The read no longer writes the shared boolean — it creates a
        # row for THIS recipient only.
        if type_tache in ("analyse", "synthese", "extraction"):
            job = get_object_or_404(ExtractionJob, pk=pk)
            if not _est_proprietaire_page(request.user, job.page):
                raise Http404("No ExtractionJob matches the given query.")
            _marquer_tache_lue_pour(request.user, TypeDeTache.EXTRACTION, job.pk)
        elif type_tache == "transcription":
            job = get_object_or_404(TranscriptionJob, pk=pk)
            if not _est_proprietaire_page(request.user, job.page):
                raise Http404("No TranscriptionJob matches the given query.")
            _marquer_tache_lue_pour(request.user, TypeDeTache.TRANSCRIPTION, job.pk)
        elif type_tache == "ingestion":
            # Pas de job : pk est directement l'id de la Page.
            # / No job: pk IS the page id.
            page = get_object_or_404(Page, pk=pk)
            if not _est_proprietaire_page(request.user, page):
                raise Http404("No Page matches the given query.")
            _marquer_tache_lue_pour(request.user, TypeDeTache.INGESTION, page.pk)
        else:
            return HttpResponse(
                "Parametre type=analyse|synthese|transcription|ingestion requis",
                status=400,
            )

        return HttpResponse(status=204)

    @action(detail=False, methods=["POST"], url_path="marquer-toutes-lues")
    def marquer_toutes_lues(self, request):
        """
        Marque TOUTES les notifications terminees du user comme lues.
        Refetch ensuite le dropdown frais + OOB swap du bouton (etat neutre).
        / Mark ALL user's finished notifications as read.
        Then refetch fresh dropdown + OOB swap of button (neutre state).

        LOCALISATION : front/views_taches.py

        Perimetre ELARGI (defaut 1, revue de cloture du 11 aout) : voir
        _filtre_proprietaire_page.

        Correction 1 (meme revue) : plus un .update() sur un booleen
        partage — pour chaque type, on liste les taches non lues PAR CE
        DESTINATAIRE (anti-jointure), puis on cree leurs lignes
        NotificationTacheLue en un seul bulk_create(). Deux requetes
        par type (1 SELECT + 1 INSERT), aucune boucle Python cote DB,
        et ignore_conflicts=True encaisse une notification deja lue
        entre-temps sans lever.
        / No longer a shared-boolean .update(): for each type, select
        this recipient's unread task ids then bulk_create their rows —
        two queries per type, no per-row loop.
        """
        NotificationTacheLue.objects.bulk_create(
            [
                NotificationTacheLue(
                    utilisateur=request.user, type_tache=TypeDeTache.EXTRACTION,
                    tache_id=identifiant,
                )
                for identifiant in ExtractionJob.objects.filter(
                    _filtre_proprietaire_page("page__", request.user),
                    status__in=["completed", "error"],
                ).exclude(
                    pk__in=_ids_taches_lues_par(request.user, TypeDeTache.EXTRACTION),
                ).distinct().values_list("pk", flat=True)
            ],
            ignore_conflicts=True,
        )

        NotificationTacheLue.objects.bulk_create(
            [
                NotificationTacheLue(
                    utilisateur=request.user, type_tache=TypeDeTache.TRANSCRIPTION,
                    tache_id=identifiant,
                )
                for identifiant in TranscriptionJob.objects.filter(
                    _filtre_proprietaire_page("page__", request.user),
                    status__in=["completed", "error"],
                ).exclude(
                    pk__in=_ids_taches_lues_par(request.user, TypeDeTache.TRANSCRIPTION),
                ).distinct().values_list("pk", flat=True)
            ],
            ignore_conflicts=True,
        )

        NotificationTacheLue.objects.bulk_create(
            [
                NotificationTacheLue(
                    utilisateur=request.user, type_tache=TypeDeTache.INGESTION,
                    tache_id=identifiant,
                )
                for identifiant in Page.objects.filter(
                    _filtre_proprietaire_page("", request.user),
                    ingestion_etat__in=[EtatIngestion.REUSSIE, EtatIngestion.ECHOUEE],
                ).exclude(
                    pk__in=_ids_taches_lues_par(request.user, TypeDeTache.INGESTION),
                ).distinct().values_list("pk", flat=True)
            ],
            ignore_conflicts=True,
        )

        # Renvoie le dropdown rafraichi (avec OOB swap du bouton inclus)
        # / Returns refreshed dropdown (with OOB button swap included)
        # Reutilise la logique de dropdown() / Reuses dropdown() logic
        return self.dropdown(request)
