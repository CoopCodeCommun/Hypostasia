"""
Endpoints de la couche corpus : le carnet et le rangement des notes.
/ Corpus layer endpoints: the notebook and note filing.

LOCALISATION : front/views_corpus.py

SPEC-corpus-base-carnet-note.md v1.1 § 9. Toutes les reponses sont du
HTML (HTMX). Aucune reponse JSON pour l'interface.

AllowAny, PAS IsAuthenticated : la v1.0 de la spec mettait
IsAuthenticated, ce qui tuait les carnets publics pour les anonymes.
Le controle se fait PAR OBJET, comme partout ailleurs dans front/views.py.
/ AllowAny with per-object control, as everywhere else.
"""

import logging
from collections import defaultdict

from django.db import models, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from core.models import (
    AppartenanceDossierBase,
    AppartenancePageDossier,
    BaseDeConnaissances,
    CategorieBase,
    CategorieDossier,
    Dossier,
    DossierPartage,
    ListeDeCategories,
    Page,
    TypeDeNote,
    VisibiliteDossier,
)
from core.serializers import CategoriserUneNoteSerializer
from core.services.corpus import (
    ranger_une_note_dans_un_carnet,
    retirer_une_note_d_un_carnet,
)
from front.serializers import (
    AjouterAUnCarnetSerializer,
    GererCategoriesSerializer,
    ReordonnerLeCarnetSerializer,
)
from front.views import (
    _est_proprietaire_page,
    _reponse_acces_refuse,
    _utilisateur_a_acces_dossier,
    _utilisateur_a_acces_page,
    _utilisateur_peut_ecrire_dossier,
)

logger = logging.getLogger(__name__)


def _filtre_des_carnets_visibles(utilisateur):
    """
    Le filtre Q des carnets qu'un utilisateur peut voir, pour les comptes
    annotes : publics, legacy sans owner, et les siens. Les partages ne
    sont pas inclus (sous-compte assume, jamais de fuite).
    / The Q filter of notebooks a user may see, for annotated counts.

    LOCALISATION : front/views_corpus.py
    """
    filtre = (
        Q(page__appartenances_dossiers__dossier__visibilite=VisibiliteDossier.PUBLIC)
        | Q(page__appartenances_dossiers__dossier__owner__isnull=True)
    )
    if utilisateur is not None and utilisateur.is_authenticated:
        filtre = filtre | Q(page__appartenances_dossiers__dossier__owner=utilisateur)
    return filtre


def _appartenances_filtrees_par_facettes(carnet, identifiants_de_categories,
                                         utilisateur=None):
    """
    Les appartenances d'un carnet, filtrees par facettes (§ 8.2) :
    les categories d'un MEME axe se combinent en OU, les axes entre eux
    en ET. C'est la convention des facettes de e-commerce.
    / A notebook's memberships filtered by facets: OR within one axis,
    AND across axes.

    LOCALISATION : front/views_corpus.py
    """
    # Les syntheses et wikis sont exclus par leur TYPE (etalon
    # estUneSource, dependance C.6) — plus seulement par le versionnage.
    # / Syntheses and wikis excluded by TYPE, not just versioning.
    appartenances = AppartenancePageDossier.objects.filter(
        dossier=carnet,
        page__parent_page__isnull=True,
        page__type_de_note=TypeDeNote.NOTE,
    )

    # Entree hostile : on ne garde que les identifiants numeriques —
    # ?categorie=abc est ignore, jamais un 500 (relecture E).
    # / Hostile input: keep numeric ids only, never a 500.
    identifiants_numeriques = [
        identifiant for identifiant in identifiants_de_categories
        if str(identifiant).isdigit()
    ]

    categories_choisies = CategorieDossier.objects.select_related("liste").filter(
        pk__in=identifiants_numeriques,
        liste__dossier=carnet,
    )
    categories_par_axe = defaultdict(list)
    for categorie in categories_choisies:
        categories_par_axe[categorie.liste_id].append(categorie.pk)

    # Chaque axe ajoute sa propre jointure : ET entre les axes, OU (in)
    # dans l'axe. / Each axis adds its own join: AND across, OR within.
    for identifiants_du_meme_axe in categories_par_axe.values():
        appartenances = appartenances.filter(
            categories__in=identifiants_du_meme_axe
        )

    # ordre_manuel=0 signifie « pas d'ordre impose » (help_text du champ) :
    # ces notes retombent APRES les notes ordonnees, en chronologique.
    # Sans cette annotation, 0 trierait avant 1 et les notes non classees
    # sauteraient en tete (relecture E).
    # / ordre_manuel=0 means "no imposed order": those notes fall AFTER
    # the ordered ones. Without this, 0 would sort before 1.
    ordre_effectif = models.Case(
        models.When(ordre_manuel=0, then=models.Value(1_000_000)),
        default="ordre_manuel",
        output_field=models.PositiveIntegerField(),
    )

    return (
        appartenances.distinct()
        .select_related("page")
        .prefetch_related("categories__liste")
        .annotate(
            ordre_effectif=ordre_effectif,
            # Compteurs de la ligne de note (etalon corpus.html:1164-1166),
            # en une requete — verrou N+1 § 5.3. distinct=True : les
            # jointures multiples ne doivent pas gonfler les comptes.
            # / Note-row counters in one query; distinct=True guards
            # against join inflation.
            nombre_d_extractions=models.Count(
                "page__extraction_jobs__entities", distinct=True,
            ),
            # « dans N carnets » ne compte que les carnets que le
            # DEMANDEUR peut voir : reveler l'existence d'un carnet prive
            # d'autrui serait une fuite (meme doctrine que le bloc de la
            # note, relecture F). Les partages ne sont pas comptes ici —
            # sous-compte assume, jamais de fuite.
            # / "in N notebooks" counts only notebooks the CALLER can
            # see; undercounting shares is accepted, leaking never.
            nombre_de_carnets=models.Count(
                "page__appartenances_dossiers",
                filter=_filtre_des_carnets_visibles(utilisateur),
                distinct=True,
            ),
        )
        .order_by("-epinglee", "ordre_effectif", "-integree_le")
    )


def _phrase_des_filtres(categories_choisies):
    """
    La phrase litterale des filtres actifs, avec OU et ET ECRITS :
    « Type : AAP OU Subvention  ET  Échéance : Ce mois-ci ».
    C'est ce qui rend la regle § 8.2 lisible sans documentation
    (etalon corpus.html:1129-1139).
    / The literal filter sentence, with OR and AND spelled out.

    LOCALISATION : front/views_corpus.py

    :param categories_choisies: CategorieDossier avec liste prechargee
    :return: la phrase, ou "" si aucun filtre / the sentence, or ""
    """
    noms_par_axe = defaultdict(list)
    for categorie in categories_choisies:
        noms_par_axe[categorie.liste.nom].append(categorie.nom)

    morceaux_par_axe = [
        f"{nom_de_l_axe} : {' OU '.join(noms)}"
        for nom_de_l_axe, noms in noms_par_axe.items()
    ]
    return "  ET  ".join(morceaux_par_axe)


def carnets_visibles_par(utilisateur):
    """
    Les carnets qu'un visiteur peut ouvrir : les siens, les orphelins,
    les publics, ceux qu'on lui a partages. Anonyme : les publics.
    / The notebooks a visitor may open.

    LOCALISATION : front/views_corpus.py

    Extrait de CarnetViewSet.list pour servir AUSSI au fil d'Ariane :
    la regle d'acces ne doit exister qu'une fois.
    / Extracted so the breadcrumb reuses the rule instead of copying it.
    """
    if utilisateur.is_authenticated:
        identifiants_partages = DossierPartage.objects.filter(
            Q(utilisateur=utilisateur) | Q(groupe__membres=utilisateur)
        ).values_list("dossier_id", flat=True)
        filtre = (
            Q(owner=utilisateur)
            | Q(owner__isnull=True)
            | Q(visibilite=VisibiliteDossier.PUBLIC)
            | Q(pk__in=identifiants_partages)
        )
    else:
        filtre = Q(visibilite=VisibiliteDossier.PUBLIC)
    return Dossier.objects.filter(filtre).distinct()


def contexte_du_fil_d_ariane(request, carnet=None, note=None, carnet_demande=None):
    """
    De quoi dessiner « Base › Carnet › Note » au-dessus d'un ecran.
    / What the "Base > Notebook > Note" breadcrumb needs.

    LOCALISATION : front/views_corpus.py

    POURQUOI UN FIL PLUTOT QU'UN ARBRE (etalon corpus.html:128-133) :
    le N-N a tue l'arbre. Une note rangee dans deux carnets n'a pas de
    parent unique, donc pas de place dans une arborescence. Le fil
    montre UN chemin parmi ceux qui existent, et son chevron permet de
    changer de chemin — c'est la bascule de carnet.

    Ce que la bascule propose depend de l'ecran :
    - sur un carnet : les autres carnets accessibles, pour changer de
      contexte de travail ;
    - sur une note : les carnets QUI CONTIENNENT CETTE NOTE, pour la
      relire sous un autre classement.
    Dans les deux cas, le carnet courant porte aria-current.

    La base affichee est la PREMIERE base visible du carnet : un carnet
    peut appartenir a plusieurs bases, le fil n'en montre qu'une (il
    donne un contexte, il ne remplace pas /bases/).
    / The breadcrumb shows one path among several; the chevron switches.
    """
    if carnet is None and note is None:
        return {}

    carnets_accessibles = carnets_visibles_par(request.user)

    if note is not None and carnet is None:
        # Un carnet EXPLICITEMENT demande (?carnet=N, pose par la
        # bascule) gagne — a condition qu'il contienne vraiment la note
        # et que le visiteur y ait acces. Sinon on l'ignore : un
        # parametre d'URL ne doit jamais servir d'oracle.
        # / An explicit ?carnet=N wins, but only if it really holds the
        # note and the visitor may open it; never trust it blindly.
        if carnet_demande:
            carnet = (
                carnets_accessibles.filter(
                    pk=carnet_demande, appartenances_pages__page=note,
                ).first()
            )

    if note is not None and carnet is None:
        # Le carnet de contexte d'une note : le premier auquel elle
        # appartient ET que le visiteur peut ouvrir. L'epingle passe
        # devant, comme partout ailleurs.
        # / A note's context notebook: the first it belongs to and the
        # visitor may open; pinned first.
        appartenance = (
            AppartenancePageDossier.objects
            .filter(page=note, dossier__in=carnets_accessibles)
            .select_related("dossier")
            .order_by("-epinglee", "dossier__name")
            .first()
        )
        carnet = appartenance.dossier if appartenance else None

    if carnet is None:
        return {"fil_note": note, "fil_carnet": None, "fil_base": None,
                "fil_carnets_bascule": []}

    if note is not None:
        # Basculer = relire la MEME note dans un AUTRE de SES carnets.
        # / Switching = the same note, seen from another of its notebooks.
        bascule = list(
            carnets_accessibles.filter(
                appartenances_pages__page=note,
            ).select_related("owner").distinct().order_by("name")[:25]
        )
    else:
        # select_related : le menu affiche le proprietaire pour separer
        # les homonymes (« Mes imports » existe quatre fois), et sans lui
        # ce serait une requete par ligne.
        # / The menu shows the owner to tell homonyms apart; without
        # select_related that is one query per row.
        bascule = list(
            carnets_accessibles.select_related("owner").order_by("name")[:25]
        )

    appartenance_de_base = (
        AppartenanceDossierBase.objects
        .filter(dossier=carnet)
        .select_related("base")
        .order_by("-epingle", "base__nom")
        .first()
    )
    base = appartenance_de_base.base if appartenance_de_base else None
    # Une base privee ne doit pas apparaitre dans le fil d'un visiteur
    # qui n'y a pas acces : le nom seul est deja une fuite.
    # / A private base must not leak through the breadcrumb.
    if base is not None and base.visibilite != VisibiliteDossier.PUBLIC:
        proprietaire = request.user.is_authenticated and base.owner_id == request.user.id
        if not proprietaire:
            base = None

    return {
        "fil_base": base,
        "fil_carnet": carnet,
        "fil_note": note,
        "fil_carnets_bascule": bascule,
    }


def _contexte_des_notes_du_carnet(request, carnet, identifiants_bruts):
    """
    Le contexte complet du partial notes_du_carnet.html : la liste
    filtree, le total sans filtre, la phrase des filtres, et les droits.
    / The full context for the notes partial: filtered list, unfiltered
    total, filter sentence, and rights.

    LOCALISATION : front/views_corpus.py
    """
    appartenances = _appartenances_filtrees_par_facettes(
        carnet, identifiants_bruts, utilisateur=request.user,
    )
    categories_choisies = list(
        CategorieDossier.objects.select_related("liste").filter(
            pk__in=[i for i in identifiants_bruts if str(i).isdigit()],
            liste__dossier=carnet,
        )
    )
    nombre_total = AppartenancePageDossier.objects.filter(
        dossier=carnet, page__parent_page__isnull=True,
        page__type_de_note=TypeDeNote.NOTE,
    ).count()

    return {
        "carnet": carnet,
        "appartenances": list(appartenances),
        "nombre_total": nombre_total,
        "phrase_des_filtres": _phrase_des_filtres(categories_choisies),
        "categories_choisies": [c.pk for c in categories_choisies],
        "peut_ecrire": _utilisateur_peut_ecrire_dossier(request.user, carnet),
    }


class CarnetViewSet(viewsets.ViewSet):
    """
    Le carnet : liste, detail, notes filtrees, categories, ordre manuel.
    / The notebook: list, detail, filtered notes, categories, ordering.

    LOCALISATION : front/views_corpus.py
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """
        GET /carnets/ — mes carnets + partages + publics.
        Anonyme : uniquement les publics.
        / My notebooks + shared + public; anonymous: public only.
        """
        # La regle d'acces vit dans carnets_visibles_par() : le fil
        # d'Ariane s'en sert aussi, elle ne doit exister qu'une fois.
        # / The access rule lives in one place; the breadcrumb reuses it.
        # Compteurs DERIVES en une requete (regle de l'etalon : rien de
        # tape). / DERIVED counters in one query.
        carnets_visibles = (
            carnets_visibles_par(request.user)
            .select_related("owner")
            .annotate(
                nombre_de_notes=models.Count(
                    "appartenances_pages",
                    filter=Q(appartenances_pages__page__parent_page__isnull=True),
                    distinct=True,
                ),
                nombre_d_axes=models.Count("listes_de_categories", distinct=True),
            )
            .distinct()
            .order_by("name")
        )

        contexte = {"carnets": carnets_visibles}
        if request.headers.get("HX-Request"):
            return render(request, "front/corpus/carnets_liste.html", contexte)
        contexte["carnets_liste_preloaded"] = True
        return render(request, "front/base.html", contexte)

    def retrieve(self, request, pk=None):
        """
        GET /carnets/{id}/ — le carnet, ses notes, ses facettes.
        / The notebook, its notes, its facets.
        """
        carnet = get_object_or_404(Dossier, pk=pk)
        if not _utilisateur_a_acces_dossier(request.user, carnet):
            return _reponse_acces_refuse(request)

        # L'etat des filtres vit dans l'URL (§ 8.2) : un F5 ou un lien
        # partage retrouve les memes cases cochees et la meme liste.
        # / Filter state lives in the URL: F5 or a shared link restores it.
        identifiants_bruts = request.GET.getlist("categorie")
        contexte = _contexte_des_notes_du_carnet(request, carnet, identifiants_bruts)

        axes = list(
            carnet.listes_de_categories.prefetch_related("categories_de_dossier")
        )
        # Compteurs des onglets synthese (phase H, etalon #cpt-wikis) :
        # on sait s'il y a du contenu SANS cliquer.
        # / Synthesis tab counters: content visible before clicking.
        from core.models import SyntheseDirigee, Wiki
        contexte.update({
            "axes": axes,
            "nombre_de_notes": contexte["nombre_total"],
            "nombre_de_categories": sum(
                len(axe.categories_de_dossier.all()) for axe in axes
            ),
            "nombre_de_wikis": Wiki.objects.filter(dossier=carnet).count(),
            "nombre_de_syntheses": SyntheseDirigee.objects.filter(
                dossier=carnet,
            ).count(),
        })

        contexte.update(contexte_du_fil_d_ariane(request, carnet=carnet))

        # Requete HTMX -> le contenu seul ; acces direct (F5) -> la page
        # complete via base.html, comme LectureViewSet.
        # / HTMX -> content only; direct hit -> full base.html page.
        if request.headers.get("HX-Request"):
            return render(request, "front/corpus/carnet_detail.html", contexte)
        contexte["carnet_preloaded"] = True
        return render(request, "front/base.html", contexte)

    @action(detail=True, methods=["GET"], url_path="notes")
    def notes_filtrees(self, request, pk=None):
        """
        GET /carnets/{id}/notes/?categorie=N&categorie=M — partial HTMX
        de la liste filtree par facettes (§ 8.2).
        / HTMX partial of the facet-filtered note list.
        """
        carnet = get_object_or_404(Dossier, pk=pk)
        if not _utilisateur_a_acces_dossier(request.user, carnet):
            return _reponse_acces_refuse(request)

        contexte = _contexte_des_notes_du_carnet(
            request, carnet, request.GET.getlist("categorie")
        )
        return render(
            request, "front/corpus/partials/notes_du_carnet.html", contexte
        )

    @action(detail=True, methods=["GET", "POST"], url_path="categories")
    def gerer_categories(self, request, pk=None):
        """
        GET/POST /carnets/{id}/categories/ — axes et categories du carnet.
        / The notebook's axes and categories.
        """
        carnet = get_object_or_404(Dossier, pk=pk)
        if not _utilisateur_a_acces_dossier(request.user, carnet):
            return _reponse_acces_refuse(request)

        if request.method == "POST":
            if not _utilisateur_peut_ecrire_dossier(request.user, carnet):
                return _reponse_acces_refuse(request)

            serializer = GererCategoriesSerializer(data=request.data)
            if not serializer.is_valid():
                return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                    "erreurs": serializer.errors,
                }, status=400)

            donnees = serializer.validated_data
            if donnees["action"] == "creer_liste":
                ListeDeCategories.objects.get_or_create(
                    dossier=carnet, nom=donnees["nom"],
                )
            else:
                liste_cible = get_object_or_404(
                    ListeDeCategories, pk=donnees["liste_id"], dossier=carnet,
                )
                CategorieDossier.objects.get_or_create(
                    liste=liste_cible, nom=donnees["nom"],
                )

        axes = carnet.listes_de_categories.prefetch_related(
            "categories_de_dossier"
        )
        return render(request, "front/corpus/partials/categories_du_carnet.html", {
            "carnet": carnet,
            "axes": axes,
        })

    @action(detail=True, methods=["POST"], url_path="reordonner")
    def reordonner(self, request, pk=None):
        """
        POST /carnets/{id}/reordonner/ — ecrit l'ordre manuel (l'ordre de
        la liste recue EST l'ordre voulu, 1, 2, 3...).
        / Writes the manual order; received list order IS the wanted one.
        """
        carnet = get_object_or_404(Dossier, pk=pk)
        if not _utilisateur_peut_ecrire_dossier(request.user, carnet):
            return _reponse_acces_refuse(request)

        # Les filtres actifs accompagnent le geste : la reponse re-rend la
        # MEME liste filtree, pas la liste complete (relecture E).
        # / Active filters travel with the gesture.
        filtres_bruts = []
        if request.data.get("categorie"):
            filtres_bruts = str(request.data.get("categorie")).split(",")

        message_d_ordre = ""
        note_a_deplacer = request.data.get("deplacer")
        if note_a_deplacer:
            if not str(note_a_deplacer).isdigit():
                return render(
                    request, "front/corpus/partials/erreurs_formulaire.html",
                    {"erreurs": {"deplacer": ["identifiant invalide"]}},
                    status=400,
                )
            reponse_erreur, message_d_ordre = self._deplacer_d_un_cran(
                carnet, int(note_a_deplacer),
                request.data.get("direction", ""), filtres_bruts,
            )
            if reponse_erreur:
                return render(
                    request, "front/corpus/partials/erreurs_formulaire.html",
                    {"erreurs": reponse_erreur}, status=400,
                )
        else:
            donnees_recues = {"page_ids": request.data.getlist("page_ids")} if hasattr(
                request.data, "getlist"
            ) else {"page_ids": request.data.get("page_ids", [])}
            serializer = ReordonnerLeCarnetSerializer(data=donnees_recues)
            if not serializer.is_valid():
                return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                    "erreurs": serializer.errors,
                }, status=400)

            # Une seule ecriture groupee, en transaction : pas d'ordre a
            # moitie ecrit si la requete est coupee (relecture E).
            # / One bulk write, in a transaction.
            position_par_page = {}
            for position, identifiant_de_page in enumerate(
                serializer.validated_data["page_ids"], start=1
            ):
                position_par_page[identifiant_de_page] = position

            with transaction.atomic():
                appartenances_a_ordonner = list(
                    AppartenancePageDossier.objects.select_for_update().filter(
                        dossier=carnet, page_id__in=position_par_page.keys(),
                    )
                )
                for appartenance in appartenances_a_ordonner:
                    appartenance.ordre_manuel = position_par_page[appartenance.page_id]
                AppartenancePageDossier.objects.bulk_update(
                    appartenances_a_ordonner, ["ordre_manuel"],
                )

        contexte = _contexte_des_notes_du_carnet(request, carnet, filtres_bruts)
        contexte["message_d_ordre"] = message_d_ordre
        return render(
            request, "front/corpus/partials/notes_du_carnet.html", contexte
        )

    def _deplacer_d_un_cran(self, carnet, identifiant_de_page, direction,
                            filtres_bruts):
        """
        Echange une note avec sa voisine VISIBLE (etalon corpus.html:
        1188-1194) : sous filtre, on permute avec la voisine affichee, pas
        avec la voisine reelle. Si l'une est epinglee et pas l'autre,
        l'epingle est transferee pour que l'echange soit visible.
        / Swaps a note with its VISIBLE neighbour; transfers the pin when
        they differ, so the swap is visible.

        LOCALISATION : front/views_corpus.py

        Si des notes n'ont pas encore d'ordre manuel (0), l'ordre courant
        est d'abord FIGE (1..n) — sinon echanger deux zeros ne ferait rien.
        / Unranked notes (0) get the current order materialized first.

        :return: None si OK, ou un dict d'erreurs / None, or an error dict
        """
        if direction not in ("monter", "descendre"):
            return (
                {"direction": ["direction doit etre 'monter' ou 'descendre'"]},
                "",
            )

        with transaction.atomic():
            # Figer l'ordre courant si besoin / Materialize current order
            toutes_les_appartenances = list(
                AppartenancePageDossier.objects.select_for_update()
                .filter(dossier=carnet, page__parent_page__isnull=True)
                .order_by("-epinglee", "ordre_manuel", "-integree_le")
            )
            au_moins_une_sans_ordre = any(
                appartenance.ordre_manuel == 0
                for appartenance in toutes_les_appartenances
            )
            if au_moins_une_sans_ordre:
                # Les ordonnees d'abord (0 en dernier), puis chronologique.
                # / Ranked first (0 last), then chronological.
                toutes_les_appartenances.sort(
                    key=lambda a: (
                        not a.epinglee,
                        a.ordre_manuel if a.ordre_manuel else 1_000_000,
                        -a.integree_le.timestamp(),
                    )
                )
                for position, appartenance in enumerate(
                    toutes_les_appartenances, start=1
                ):
                    appartenance.ordre_manuel = position
                AppartenancePageDossier.objects.bulk_update(
                    toutes_les_appartenances, ["ordre_manuel"],
                )

            # La liste VISIBLE, dans l'ordre affiche / The VISIBLE list
            visibles = list(
                _appartenances_filtrees_par_facettes(carnet, filtres_bruts)
            )
            positions = {
                appartenance.page_id: indice
                for indice, appartenance in enumerate(visibles)
            }
            if identifiant_de_page not in positions:
                return {"deplacer": ["note absente de la liste affichee"]}, ""

            indice_note = positions[identifiant_de_page]
            indice_voisine = (
                indice_note - 1 if direction == "monter" else indice_note + 1
            )
            aux_bornes = indice_voisine < 0 or indice_voisine >= len(visibles)
            if aux_bornes:
                # Deja a l'extremite : rien a faire, pas une erreur.
                # / Already at the edge: nothing to do, not an error.
                return None, "Déjà à l'extrémité de la liste."

            note = visibles[indice_note]
            voisine = visibles[indice_voisine]
            note.ordre_manuel, voisine.ordre_manuel = (
                voisine.ordre_manuel, note.ordre_manuel,
            )
            if note.epinglee != voisine.epinglee:
                note.epinglee, voisine.epinglee = (
                    voisine.epinglee, note.epinglee,
                )
            AppartenancePageDossier.objects.bulk_update(
                [note, voisine], ["ordre_manuel", "epinglee"],
            )
        return None, "Ordre modifié — l'ordre manuel donne le fil narratif du carnet."


class NoteCorpusViewSet(viewsets.ViewSet):
    """
    Le rangement d'une note dans ses carnets.
    / Filing a note into its notebooks.

    LOCALISATION : front/views_corpus.py

    Chaque action rend le bloc « Dans N carnets » de la note, que la
    phase G enrichira. / Each action renders the note's notebooks block.
    """

    permission_classes = [permissions.AllowAny]

    def _rendre_le_bloc_carnets(self, request, note, status=200):
        """
        Le partial des carnets de la note — LIMITE aux carnets que le
        demandeur peut lire : nommer le carnet prive d'un tiers serait
        une fuite (relecture E, bloquant 2). Chaque ligne porte ses
        droits d'edition ; le bloc propose « Ajouter a... » sur les
        carnets inscriptibles (phase G).
        / The note's notebooks partial — LIMITED to readable notebooks,
        with per-row edit rights and an "Add to..." form.
        """
        lignes = []
        for appartenance in note.appartenances_dossiers.select_related(
            "dossier", "dossier__owner"
        ).prefetch_related(
            "categories__liste",
            "dossier__listes_de_categories__categories_de_dossier",
        ):
            if not _utilisateur_a_acces_dossier(request.user, appartenance.dossier):
                continue
            lignes.append({
                "appartenance": appartenance,
                # Le crayon n'apparait que si on peut editer CETTE relation.
                # / The pencil shows only when THIS relation is editable.
                "peut_editer": _utilisateur_peut_ecrire_dossier(
                    request.user, appartenance.dossier
                ),
            })

        # « Ajouter a... » : mes carnets inscriptibles qui ne contiennent
        # pas deja la note. Un carnet public est marque — ranger une note
        # dans un carnet public LA REND PUBLIQUE (§ 5.2, § 7.3).
        # / "Add to...": writable notebooks not already containing the
        # note; public ones are flagged.
        carnets_disponibles = []
        if request.user.is_authenticated:
            identifiants_deja_la = [
                ligne["appartenance"].dossier_id for ligne in lignes
            ]
            # Les miens, les legacy, ET les partages avec moi (direct ou
            # groupe) : l'eleve doit pouvoir ranger dans le carnet de
            # classe (relecture G, meme regle que l'extension § 10).
            # / Mine, legacy, AND shared with me: same rule as the
            # extension.
            identifiants_partages = DossierPartage.objects.filter(
                Q(utilisateur=request.user) | Q(groupe__membres=request.user)
            ).values_list("dossier_id", flat=True)
            candidats = Dossier.objects.filter(
                Q(owner=request.user)
                | Q(owner__isnull=True)
                | Q(pk__in=identifiants_partages)
            ).exclude(pk__in=identifiants_deja_la).select_related(
                "owner"
            ).distinct().order_by("name")
            carnets_disponibles = [
                carnet for carnet in candidats
                if _utilisateur_peut_ecrire_dossier(request.user, carnet)
            ]

        return render(request, "front/corpus/partials/carnets_de_la_note.html", {
            "note": note,
            "lignes": lignes,
            "carnets_disponibles": carnets_disponibles,
        }, status=status)

    @action(detail=True, methods=["GET"], url_path="carnets/bloc")
    def bloc_carnets(self, request, pk=None):
        """
        GET /notes/{id}/carnets/bloc/ — le bloc « Dans N carnets »,
        charge en HTMX par l'ecran de lecture (phase G). Un seul endpoint
        au lieu de toucher les 8 contextes qui rendent
        lecture_principale.html.
        / The "In N notebooks" block, lazy-loaded by the reading screen.
        """
        # Racines seulement, comme l'ecran de lecture : une version suit
        # les appartenances de sa racine. / Root pages only.
        note = get_object_or_404(Page, pk=pk, parent_page__isnull=True)
        if not _utilisateur_a_acces_page(request.user, note):
            return _reponse_acces_refuse(request)
        return self._rendre_le_bloc_carnets(request, note)

    @action(detail=True, methods=["POST"], url_path="carnets")
    def ajouter_a_un_carnet(self, request, pk=None):
        """
        POST /notes/{id}/carnets/ — cree une appartenance.
        Exige : acces en LECTURE a la note (on ne range pas ce qu'on ne
        peut pas lire — sinon on pourrait l'exposer), et ECRITURE sur le
        carnet cible.
        / Requires READ access to the note and WRITE access to the target
        notebook.
        """
        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        # parent_page__isnull : une VERSION ne se range jamais separement
        # (spec § 11) — 404, comme si elle n'existait pas pour ce geste.
        # / A VERSION is never filed separately: 404.
        note = get_object_or_404(Page, pk=pk, parent_page__isnull=True)
        if not _utilisateur_a_acces_page(request.user, note):
            return _reponse_acces_refuse(request)

        serializer = AjouterAUnCarnetSerializer(data=request.data)
        if not serializer.is_valid():
            return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                "erreurs": serializer.errors,
            }, status=400)

        carnet_cible = get_object_or_404(
            Dossier, pk=serializer.validated_data["carnet_id"]
        )
        if not _utilisateur_peut_ecrire_dossier(request.user, carnet_cible):
            return _reponse_acces_refuse(request)

        ranger_une_note_dans_un_carnet(note, carnet_cible, request.user)
        logger.info(
            "NoteCorpusViewSet.ajouter: note %s rangee dans carnet %s (user=%s)",
            note.pk, carnet_cible.pk, request.user.username,
        )
        return self._rendre_le_bloc_carnets(request, note)

    @action(
        detail=True,
        methods=["DELETE", "POST"],
        url_path=r"carnets/(?P<carnet_id>\d+)",
    )
    def retirer_d_un_carnet(self, request, pk=None, carnet_id=None):
        """
        DELETE /notes/{id}/carnets/{carnet_id}/ — supprime l'appartenance.
        NE SUPPRIME JAMAIS LA NOTE (§ 9). POST est accepte pour les
        formulaires HTML sans DELETE (HTMX hx-delete envoie DELETE).
        / Removes the membership, NEVER deletes the note. POST accepted
        for plain HTML forms.
        """
        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        note = get_object_or_404(Page, pk=pk)
        carnet = get_object_or_404(Dossier, pk=carnet_id)

        # Qui peut retirer : celui qui ECRIT sur le carnet, OU le
        # PROPRIETAIRE de la note (decision du 8 aout, securite d'abord) :
        # un tiers peut ranger ma note dans son carnet public et la rendre
        # publique — je dois pouvoir l'en sortir.
        # / Who can remove: a notebook writer, OR the note's owner — a
        # third party can make my note public; I must be able to pull it
        # out.
        a_le_droit_de_retirer = (
            _utilisateur_peut_ecrire_dossier(request.user, carnet)
            or _est_proprietaire_page(request.user, note)
        )
        if not a_le_droit_de_retirer:
            return _reponse_acces_refuse(request)

        # L'appartenance doit EXISTER : sinon, retirer une note d'un
        # carnet ou elle n'est pas servirait d'oracle pour enumerer les
        # notes et lire leurs carnets (IDOR, relecture E bloquant 1).
        # / The membership must EXIST: otherwise this endpoint becomes an
        # enumeration oracle.
        get_object_or_404(AppartenancePageDossier, page=note, dossier=carnet)

        retirer_une_note_d_un_carnet(note, carnet)
        logger.info(
            "NoteCorpusViewSet.retirer: note %s retiree du carnet %s (user=%s)",
            note.pk, carnet.pk, request.user.username,
        )
        return self._rendre_le_bloc_carnets(request, note)

    @action(
        detail=True,
        methods=["POST"],
        url_path=r"carnets/(?P<carnet_id>\d+)/categories",
    )
    def categoriser(self, request, pk=None, carnet_id=None):
        """
        POST /notes/{id}/carnets/{carnet_id}/categories/ — les categories
        de CETTE relation note-carnet, et d'elle seule.
        / The categories of THIS note-notebook relation only.
        """
        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        note = get_object_or_404(Page, pk=pk)
        carnet = get_object_or_404(Dossier, pk=carnet_id)
        if not _utilisateur_peut_ecrire_dossier(request.user, carnet):
            return _reponse_acces_refuse(request)

        appartenance = get_object_or_404(
            AppartenancePageDossier, page=note, dossier=carnet,
        )

        identifiants_soumis = (
            request.data.getlist("categorie_ids")
            if hasattr(request.data, "getlist")
            else request.data.get("categorie_ids", [])
        )
        serializer = CategoriserUneNoteSerializer(
            data={"categorie_ids": identifiants_soumis},
            context={"appartenance": appartenance},
        )
        if not serializer.is_valid():
            return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                "erreurs": serializer.errors,
            }, status=400)

        appartenance.categories.set(
            serializer.validated_data["categories_a_appliquer"]
        )
        return self._rendre_selon_l_ecran(request, note, carnet)

    @action(
        detail=True,
        methods=["POST"],
        url_path=r"carnets/(?P<carnet_id>\d+)/epingler",
    )
    def epingler(self, request, pk=None, carnet_id=None):
        """
        POST /notes/{id}/carnets/{carnet_id}/epingler/ — bascule
        l'epinglage de la note dans CE carnet.
        / Toggles pinning in THIS notebook.
        """
        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        note = get_object_or_404(Page, pk=pk)
        carnet = get_object_or_404(Dossier, pk=carnet_id)
        if not _utilisateur_peut_ecrire_dossier(request.user, carnet):
            return _reponse_acces_refuse(request)

        appartenance = get_object_or_404(
            AppartenancePageDossier, page=note, dossier=carnet,
        )
        appartenance.epinglee = not appartenance.epinglee
        appartenance.save(update_fields=["epinglee"])

        return self._rendre_selon_l_ecran(request, note, carnet)

    def _rendre_selon_l_ecran(self, request, note, carnet):
        """
        Choisit le partial de reponse selon l'ecran d'origine :
        ecran=carnet -> la liste des notes du carnet (avec ses filtres) ;
        sinon -> le bloc « Dans N carnets » de la note.
        / Picks the response partial by originating screen.

        LOCALISATION : front/views_corpus.py
        """
        vient_de_l_ecran_carnet = request.data.get("ecran") == "carnet"
        if vient_de_l_ecran_carnet:
            filtres_bruts = []
            if request.data.get("categorie"):
                filtres_bruts = str(request.data.get("categorie")).split(",")
            contexte = _contexte_des_notes_du_carnet(request, carnet, filtres_bruts)
            return render(
                request, "front/corpus/partials/notes_du_carnet.html", contexte
            )
        return self._rendre_le_bloc_carnets(request, note)


# ---------------------------------------------------------------------------
# LA BASE DE CONNAISSANCES (SPEC-corpus § 9, phase H)
# Pas de partage fin sur les bases en v1 (§ 6.2) : public / owner / legacy.
# / THE KNOWLEDGE BASE: no fine-grained sharing in v1.
# ---------------------------------------------------------------------------


def _utilisateur_a_acces_base(utilisateur, base):
    """
    Lecture d'une base : publique → tous ; superuser → oui ; owner → oui.
    PAS de clause legacy (relecture H) : BaseDeConnaissances est un modele
    NEUF — le seul chemin vers owner=None est la suppression du compte du
    proprietaire, et une base privee orpheline doit se FERMER, pas
    s'ouvrir a tout authentifie.
    / No legacy clause: an orphaned private base closes, never opens.

    LOCALISATION : front/views_corpus.py
    """
    if base.visibilite == VisibiliteDossier.PUBLIC:
        return True
    if not utilisateur or not utilisateur.is_authenticated:
        return False
    if utilisateur.is_superuser:
        return True
    return base.owner_id == utilisateur.pk


def _utilisateur_peut_ecrire_base(utilisateur, base):
    """
    Ecriture d'une base : son owner, personne d'autre. Ni legacy (base
    orpheline = fermee, relecture H), ni bypass superuser (meme doctrine
    que les notes). / Only the owner writes; orphaned bases are closed.

    LOCALISATION : front/views_corpus.py
    """
    if not utilisateur or not utilisateur.is_authenticated:
        return False
    return base.owner_id is not None and base.owner_id == utilisateur.pk


def _filtre_des_carnets_d_une_base_visibles(utilisateur):
    """
    Le filtre Q des carnets d'une base visibles par un utilisateur, pour
    le compteur annote de la liste des bases. Publics + les siens ;
    partages non comptes (sous-compte assume, jamais de fuite).
    / Q filter for a base's notebooks visible to a user.

    LOCALISATION : front/views_corpus.py
    """
    filtre = Q(
        appartenances_dossiers__dossier__visibilite=VisibiliteDossier.PUBLIC
    ) | Q(appartenances_dossiers__dossier__owner__isnull=True)
    if utilisateur is not None and utilisateur.is_authenticated:
        filtre = filtre | Q(appartenances_dossiers__dossier__owner=utilisateur)
    return filtre


class BaseViewSet(viewsets.ViewSet):
    """
    La base de connaissances : liste, detail, rangement de carnets, axes.
    / The knowledge base: list, detail, notebook filing, axes.

    LOCALISATION : front/views_corpus.py

    Le pk d'URL est le SLUG (ex 'reseau-tiers-lieux-occitanie').
    / The URL pk is the SLUG.
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """GET /bases/ — les bases visibles. / Visible bases."""
        if request.user.is_authenticated:
            filtre = (
                Q(visibilite=VisibiliteDossier.PUBLIC)
                | Q(owner=request.user)
                | Q(owner__isnull=True)
            )
        else:
            filtre = Q(visibilite=VisibiliteDossier.PUBLIC)

        bases_visibles = (
            BaseDeConnaissances.objects.filter(filtre)
            .select_related("owner")
            .annotate(
                # Ne compte que les carnets que le DEMANDEUR peut voir —
                # meme doctrine que « dans N carnets » (jamais de fuite,
                # sous-compte des partages assume). Relecture H, B1.
                # / Counts only notebooks the CALLER can see.
                nombre_de_carnets=models.Count(
                    "appartenances_dossiers",
                    filter=_filtre_des_carnets_d_une_base_visibles(request.user),
                    distinct=True,
                ),
            )
            .distinct()
            .order_by("nom")
        )
        contexte = {"bases": bases_visibles}
        if request.headers.get("HX-Request"):
            return render(request, "front/corpus/bases_liste.html", contexte)
        contexte["bases_liste_preloaded"] = True
        return render(request, "front/base.html", contexte)

    def retrieve(self, request, pk=None):
        """
        GET /bases/{slug}/ — la base et ses carnets, avec les categories
        de CHAQUE relation carnet-base (meme patron que la note, un cran
        au-dessus). / The base and its notebooks, with per-relation
        categories.
        """
        base = get_object_or_404(BaseDeConnaissances, slug=pk)
        if not _utilisateur_a_acces_base(request.user, base):
            # 404, pas 403 : le slug EST le nom — un 403 confirmerait
            # l'existence d'une base privee a qui sonde des slugs
            # (relecture H, oracle). / 404, not 403: the slug is the name.
            from django.http import Http404
            raise Http404

        # On ne nomme JAMAIS un carnet que le demandeur ne peut pas lire
        # (meme doctrine que le bloc de la note).
        # / Never name a notebook the caller cannot read.
        lignes = [
            appartenance
            for appartenance in base.appartenances_dossiers.select_related(
                "dossier", "dossier__owner"
            ).prefetch_related("categories__liste")
            if _utilisateur_a_acces_dossier(request.user, appartenance.dossier)
        ]
        axes = base.listes_de_categories.prefetch_related("categories_de_base")

        peut_ecrire = _utilisateur_peut_ecrire_base(request.user, base)

        # « Ajouter un carnet » : mes carnets pas encore dans la base
        # (le POST re-verifie la lecture). / My notebooks not yet in.
        carnets_disponibles = []
        if peut_ecrire:
            identifiants_deja_la = [
                appartenance.dossier_id for appartenance in lignes
            ]
            carnets_disponibles = list(
                Dossier.objects.filter(owner=request.user)
                .exclude(pk__in=identifiants_deja_la)
                .order_by("name")
            )

        contexte = {
            "base": base,
            "lignes": lignes,
            "axes": list(axes),
            "peut_ecrire": peut_ecrire,
            "carnets_disponibles": carnets_disponibles,
        }
        if request.headers.get("HX-Request"):
            return render(request, "front/corpus/base_detail.html", contexte)
        contexte["base_preloaded"] = True
        return render(request, "front/base.html", contexte)

    def create(self, request):
        """
        POST /bases/ — cree une base de connaissances (relecture H, B3 :
        sans cet endpoint, aucune base ne peut exister — l'admin est
        desactive). Le slug est derive du nom.
        / Creates a knowledge base; the slug derives from the name.
        """
        from django.utils.text import slugify

        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        nom_soumis = str(request.data.get("nom", "")).strip()
        if not nom_soumis:
            return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                "erreurs": {"nom": ["Le nom est obligatoire / Name is required"]},
            }, status=400)

        # Slug unique : on suffixe si le nom est deja pris.
        # / Unique slug: suffix when the name is taken.
        slug_de_base = slugify(nom_soumis)[:200] or "base"
        slug_candidat = slug_de_base
        numero = 2
        while BaseDeConnaissances.objects.filter(slug=slug_candidat).exists():
            slug_candidat = f"{slug_de_base}-{numero}"
            numero += 1

        BaseDeConnaissances.objects.create(
            nom=nom_soumis, slug=slug_candidat, owner=request.user,
        )
        return self.list(request)

    @action(
        detail=True,
        methods=["DELETE", "POST"],
        url_path=r"carnets/(?P<carnet_id>\d+)/retirer",
    )
    def retirer_un_carnet(self, request, pk=None, carnet_id=None):
        """
        POST /bases/{slug}/carnets/{id}/retirer/ — retire un carnet de la
        base. Qui peut : l'owner de la BASE, OU l'owner du CARNET (meme
        doctrine que les notes, decision du 8 aout : on peut toujours
        sortir son contenu d'un contenant d'autrui). Ne supprime jamais
        le carnet. / Base owner OR notebook owner can remove; the
        notebook is never deleted.
        """
        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        base = get_object_or_404(BaseDeConnaissances, slug=pk)
        carnet = get_object_or_404(Dossier, pk=carnet_id)

        a_le_droit = (
            _utilisateur_peut_ecrire_base(request.user, base)
            or (carnet.owner_id is not None
                and carnet.owner_id == request.user.pk)
        )
        if not a_le_droit:
            return _reponse_acces_refuse(request)

        # L'appartenance doit exister (pas d'oracle). / Must exist.
        get_object_or_404(AppartenanceDossierBase, dossier=carnet, base=base)
        AppartenanceDossierBase.objects.filter(
            dossier=carnet, base=base
        ).delete()
        return self.retrieve(request, pk=pk)

    @action(detail=True, methods=["POST"], url_path="carnets")
    def ajouter_un_carnet(self, request, pk=None):
        """
        POST /bases/{slug}/carnets/ — cree une appartenance carnet-base.
        Exige : ecriture sur la base ET lecture du carnet (on ne range
        pas ce qu'on ne peut pas lire). Idempotent.
        / Adds a notebook to the base; requires base write + notebook read.
        """
        base = get_object_or_404(BaseDeConnaissances, slug=pk)
        if not _utilisateur_peut_ecrire_base(request.user, base):
            return _reponse_acces_refuse(request)

        serializer = AjouterAUnCarnetSerializer(data=request.data)
        if not serializer.is_valid():
            return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                "erreurs": serializer.errors,
            }, status=400)

        carnet = get_object_or_404(
            Dossier, pk=serializer.validated_data["carnet_id"]
        )
        if not _utilisateur_a_acces_dossier(request.user, carnet):
            return _reponse_acces_refuse(request)

        AppartenanceDossierBase.objects.get_or_create(
            dossier=carnet, base=base,
            defaults={"integre_par": request.user},
        )
        return self.retrieve(request, pk=pk)

    @action(
        detail=True,
        methods=["POST"],
        url_path=r"carnets/(?P<carnet_id>\d+)/categories",
    )
    def categoriser_un_carnet(self, request, pk=None, carnet_id=None):
        """
        POST /bases/{slug}/carnets/{id}/categories/ — les categories de
        CETTE relation carnet-base, et d'elle seule. Trou de spec § 9
        bouche (decision du 8 aout) : le patron « meme chose, un cran
        au-dessus » est enfin complet.
        / The categories of THIS notebook-base relation only.
        """
        from django.core.exceptions import ValidationError as ErreurDeValidation

        from core.services.corpus import (
            valider_les_categories_d_une_appartenance_de_base,
        )

        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        base = get_object_or_404(BaseDeConnaissances, slug=pk)
        if not _utilisateur_peut_ecrire_base(request.user, base):
            return _reponse_acces_refuse(request)

        carnet = get_object_or_404(Dossier, pk=carnet_id)
        appartenance = get_object_or_404(
            AppartenanceDossierBase, dossier=carnet, base=base,
        )

        identifiants_soumis = (
            request.data.getlist("categorie_ids")
            if hasattr(request.data, "getlist")
            else request.data.get("categorie_ids", [])
        )
        categories_trouvees = list(
            CategorieBase.objects.select_related("liste").filter(
                pk__in=[i for i in identifiants_soumis if str(i).isdigit()],
            )
        )
        try:
            valider_les_categories_d_une_appartenance_de_base(
                appartenance, categories_trouvees
            )
        except ErreurDeValidation as erreur:
            return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                "erreurs": {"categorie_ids": erreur.messages},
            }, status=400)

        appartenance.categories.set(categories_trouvees)
        return self.retrieve(request, pk=pk)

    @action(
        detail=True,
        methods=["POST"],
        url_path=r"carnets/(?P<carnet_id>\d+)/epingler",
    )
    def epingler_un_carnet(self, request, pk=None, carnet_id=None):
        """
        POST /bases/{slug}/carnets/{id}/epingler/ — bascule l'epinglage
        du carnet dans CETTE base. Trou de spec § 9 bouche.
        / Toggles pinning in THIS base.
        """
        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        base = get_object_or_404(BaseDeConnaissances, slug=pk)
        if not _utilisateur_peut_ecrire_base(request.user, base):
            return _reponse_acces_refuse(request)

        carnet = get_object_or_404(Dossier, pk=carnet_id)
        appartenance = get_object_or_404(
            AppartenanceDossierBase, dossier=carnet, base=base,
        )
        appartenance.epingle = not appartenance.epingle
        appartenance.save(update_fields=["epingle"])
        return self.retrieve(request, pk=pk)

    @action(detail=True, methods=["GET", "POST"], url_path="categories")
    def gerer_categories(self, request, pk=None):
        """
        GET/POST /bases/{slug}/categories/ — les axes de la base.
        / The base's classification axes.
        """
        base = get_object_or_404(BaseDeConnaissances, slug=pk)
        if not _utilisateur_a_acces_base(request.user, base):
            return _reponse_acces_refuse(request)

        if request.method == "POST":
            if not _utilisateur_peut_ecrire_base(request.user, base):
                return _reponse_acces_refuse(request)
            serializer = GererCategoriesSerializer(data=request.data)
            if not serializer.is_valid():
                return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                    "erreurs": serializer.errors,
                }, status=400)
            donnees = serializer.validated_data
            if donnees["action"] == "creer_liste":
                ListeDeCategories.objects.get_or_create(
                    base=base, nom=donnees["nom"],
                )
            else:
                liste_cible = get_object_or_404(
                    ListeDeCategories, pk=donnees["liste_id"], base=base,
                )
                CategorieBase.objects.get_or_create(
                    liste=liste_cible, nom=donnees["nom"],
                )

        axes = base.listes_de_categories.prefetch_related("categories_de_base")
        return render(request, "front/corpus/partials/categories_de_la_base.html", {
            "base": base,
            "axes": axes,
        })
