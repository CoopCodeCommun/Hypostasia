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
    carnets_ou_ecrire,
    carnets_visibles_par,
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
            # LE DEBAT SE COMPTE SUR LA LIGNE, comme les extractions.
            # Une note tres commentee ne se distinguait en rien d'une
            # note que personne n'a lue : le compteur existait sur la
            # CARTE de chaque extraction, jamais sur la note qui les
            # porte. / A heavily debated note looked exactly like an
            # unread one: the counter lived on each extraction card only.
            nombre_de_commentaires=models.Count(
                "page__extraction_jobs__entities__commentaires",
                distinct=True,
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


# `carnets_visibles_par` vit desormais dans core/services/corpus.py et
# est importee en tete de ce fichier. Elle a demenage le 20 aout 2026
# parce que l'API de l'extension (core/views.py) en a besoin elle aussi :
# `core` ne peut pas importer `front`, et une seconde copie de la regle
# d'acces aurait diverge de celle-ci — c'est exactement ce qui etait
# arrive aux partages par groupe.
# / It moved to core/services/corpus.py: the extension API needs it too,
# core cannot import front, and a second copy would diverge.


def _filtre_des_bases_visibles(utilisateur):
    """
    Le filtre Q, pose sur une AppartenanceDossierBase, des appartenances
    dont la base est ouvrable par ce visiteur.
    / The Q filter, on AppartenanceDossierBase, of memberships whose base
    the visitor may open.

    LOCALISATION : front/views_corpus.py

    Meme doctrine que le fil d'Ariane (voir contexte_du_fil_d_ariane) :
    le nom d'une base privee est deja une fuite, et le nom d'une de ses
    categories l'est tout autant. On ne montre donc les etiquettes d'un
    carnet que pour les bases publiques ou possedees par le visiteur.
    / Same doctrine as the breadcrumb: a private base's name — and its
    categories' names — must not leak.
    """
    filtre = (
        Q(base__visibilite=VisibiliteDossier.PUBLIC)
        | Q(base__owner__isnull=True)
    )
    if utilisateur is not None and utilisateur.is_authenticated:
        filtre = filtre | Q(base__owner=utilisateur)
    return filtre


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


def _contexte_de_la_liste_des_carnets(request):
    """
    Le contexte de /carnets/ : les carnets visibles et les deux totaux
    de l'en-tete.
    / The context of /carnets/: visible notebooks and the header totals.

    LOCALISATION : front/views_corpus.py

    EXTRAIT DE CarnetViewSet.list LE 12 AOUT. Pourquoi : le retrait de
    l'arbre lateral fait de `/carnets/` le domicile des gestes que le
    tiroir portait seul (creer, supprimer, quitter un partage). Les vues
    qui executent ces gestes vivent dans `front/views.py` et doivent
    pouvoir RENDRE cette liste sans reimplementer ses requetes.
    / Extracted so the gesture endpoints in front/views.py can render
    this list without duplicating its queries.
    """
    # La regle d'acces vit dans carnets_visibles_par() : le fil
    # d'Ariane s'en sert aussi, elle ne doit exister qu'une fois.
    # / The access rule lives in one place; the breadcrumb reuses it.
    # Compteurs DERIVES en une requete (regle de l'etalon : rien de
    # tape). / DERIVED counters in one query.
    #
    # Le filtre type_de_note=NOTE est INDISPENSABLE : la page qui
    # porte un wiki ou une synthese est RANGEE dans le carnet
    # (views_synthese.py:454 et :837), donc sans ce filtre la liste
    # annoncait « 6 notes » la ou le detail — qui, lui, filtre —
    # annoncait « 3 notes ». Deux nombres pour un meme carnet.
    # / Wiki and synthesis pages are filed in the notebook, so
    # without this filter the list and the detail disagreed.
    carnets_visibles = (
        carnets_visibles_par(request.user)
        .select_related("owner")
        .prefetch_related(
            # Les etiquettes d'un carnet vivent sur la relation
            # carnet<->base, et on ne montre QUE celles des bases que
            # le visiteur peut ouvrir : le nom d'une categorie d'une
            # base privee est deja une fuite, exactement comme le nom
            # de la base dans le fil d'Ariane.
            # / A notebook's tags live on the notebook<->base
            # relation; only visible bases' tags are shown.
            models.Prefetch(
                "appartenances_bases",
                queryset=(
                    AppartenanceDossierBase.objects
                    .filter(_filtre_des_bases_visibles(request.user))
                    .select_related("base")
                    .prefetch_related("categories")
                ),
                to_attr="appartenances_de_bases_visibles",
            ),
        )
        .annotate(
            nombre_de_notes=models.Count(
                "appartenances_pages",
                filter=Q(
                    appartenances_pages__page__parent_page__isnull=True,
                    appartenances_pages__page__type_de_note=TypeDeNote.NOTE,
                ),
                distinct=True,
            ),
            nombre_d_axes=models.Count("listes_de_categories", distinct=True),
            # Les deux genres de synthese, comptes SEPAREMENT : un
            # wiki est vivant, une synthese dirigee est un acte date.
            # L'etalon les distingue dans sa sous-ligne
            # (« 2 wikis · 2 synthèses »), on ne les additionne pas.
            # / The two synthesis kinds, counted separately.
            nombre_de_wikis=models.Count("wikis", distinct=True),
            nombre_de_syntheses=models.Count(
                "syntheses_dirigees", distinct=True,
            ),
        )
        .distinct()
        .order_by("name")
    )

    # LES TOTAUX DE L'EN-TETE. L'etalon annonce « 4 carnets ·
    # 10 notes · 4 synthèses » : des totaux DISTINCTS, pas la somme
    # des compteurs de lignes — une note rangee dans deux carnets ne
    # doit compter qu'une fois.
    # / Header totals are DISTINCT counts, not a sum of row counters:
    # a note filed in two notebooks must count once.
    identifiants_des_carnets_visibles = list(
        carnets_visibles_par(request.user).values_list("pk", flat=True)
    )
    nombre_total_de_notes = Page.objects.filter(
        appartenances_dossiers__dossier_id__in=identifiants_des_carnets_visibles,
        parent_page__isnull=True,
        type_de_note=TypeDeNote.NOTE,
    ).distinct().count()
    # « Synthèses » au sens de l'etalon : les deux genres reunis, car
    # l'en-tete dit ce que la base PRODUIT, pas comment elle le range.
    # / "Syntheses" here means both kinds: the header says what the
    # collection produced, not how it is filed.
    from core.models import SyntheseDirigee, Wiki
    nombre_total_de_syntheses = (
        Wiki.objects.filter(
            dossier_id__in=identifiants_des_carnets_visibles,
        ).count()
        + SyntheseDirigee.objects.filter(
            dossier_id__in=identifiants_des_carnets_visibles,
        ).count()
    )

    return {
        "carnets": carnets_visibles,
        "nombre_total_de_notes": nombre_total_de_notes,
        "nombre_total_de_syntheses": nombre_total_de_syntheses,
    }


def rendre_la_liste_des_carnets(request):
    """
    La liste des carnets rendue en PARTIAL HTMX, quel que soit l'appelant.
    / The notebook list rendered as an HTMX partial, whoever calls.

    LOCALISATION : front/views_corpus.py

    C'est la reponse des gestes qui font disparaitre le carnet courant —
    le supprimer, quitter son partage : apres eux il n'y a plus de page
    de carnet a montrer, seulement la collection. Les vues appelantes
    vivent dans `front/views.py`, qui ne peut pas importer ce module en
    tete (import circulaire) : elles l'importent dans le corps de la
    methode.
    / The response of gestures that destroy the current notebook page.
    Callers live in front/views.py and import this lazily (circular).
    """
    return render(
        request,
        "front/corpus/carnets_liste.html",
        _contexte_de_la_liste_des_carnets(request),
    )


def rendre_les_notes_du_carnet(request, carnet):
    """
    La liste des notes d'un carnet, en PARTIAL HTMX (cible #corpus-notes).
    / A notebook's note list, as an HTMX partial (targets #corpus-notes).

    LOCALISATION : front/views_corpus.py

    C'est la reponse de la suppression d'une note (`PageViewSet.supprimer`,
    dans front/views.py) : le geste part de cette liste, il y revient.
    Les filtres de facettes ne sont pas rejoues — un POST n'a pas de
    `?categorie=` — donc la liste revient complete, ce qui est honnete :
    la note supprimee ne peut plus etre cachee par un filtre.
    / The response of deleting a note; the gesture starts from this list
    and returns to it, unfiltered.
    """
    return render(
        request,
        "front/corpus/partials/notes_du_carnet.html",
        _contexte_des_notes_du_carnet(request, carnet, []),
    )


def _contexte_du_detail_du_carnet(request, carnet):
    """
    Le contexte de /carnets/{id}/ : notes filtrees, axes, compteurs des
    onglets, fil d'Ariane, et les DROITS de gouvernance du visiteur.
    / The context of /carnets/{id}/, including governance rights.

    LOCALISATION : front/views_corpus.py
    """
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

    # LES DROITS DE GOUVERNANCE, poses ici parce que le gabarit doit
    # decider quoi MONTRER, pas seulement quoi autoriser. Ils ne
    # remplacent aucune garde serveur : chaque endpoint refait sa
    # verification (DossierViewSet.renommer, .destroy, .partager…).
    # / Governance rights, for what to SHOW. They replace no server-side
    # guard: every endpoint re-checks.
    #
    # `est_proprietaire` suit la meme regle que DossierViewSet : les
    # carnets legataires (owner NULL, anterieurs aux comptes) n'ont pas
    # de proprietaire, donc personne ne les gouverne depuis l'interface.
    # / Legacy notebooks (owner NULL) have no owner and no governance.
    est_proprietaire = bool(
        request.user.is_authenticated and carnet.owner_id == request.user.pk
    )
    # « Quitter » n'a de sens que pour un partage RECU EN DIRECT : un
    # acces obtenu par un groupe ne se quitte pas note par note, il se
    # quitte en sortant du groupe. / "Leave" only for a DIRECT share.
    partage_direct_recu = bool(
        request.user.is_authenticated
        and DossierPartage.objects.filter(
            dossier=carnet, utilisateur=request.user,
        ).exists()
    )
    contexte.update({
        "est_proprietaire": est_proprietaire,
        "partage_direct_recu": partage_direct_recu,
        # Les trois niveaux, ecrits une fois : le gabarit boucle dessus
        # plutot que de repeter trois blocs presque identiques.
        # / The three levels, written once.
        "niveaux_de_visibilite": [
            (VisibiliteDossier.PRIVE, "privé"),
            (VisibiliteDossier.PARTAGE, "partagé"),
            (VisibiliteDossier.PUBLIC, "public"),
        ],
    })

    contexte.update(contexte_du_fil_d_ariane(request, carnet=carnet))
    return contexte


def rendre_le_detail_du_carnet(request, carnet):
    """
    Le detail d'un carnet rendu en PARTIAL HTMX, quel que soit l'appelant.
    / A notebook's detail rendered as an HTMX partial, whoever calls.

    LOCALISATION : front/views_corpus.py

    C'est la reponse des gestes qui MODIFIENT le carnet sans le faire
    disparaitre — le renommer, changer sa visibilite. Rendre la page
    entiere plutot qu'un fragment evite la divergence classique : le
    titre change dans l'en-tete mais pas dans le fil d'Ariane.
    / Response of gestures that change the notebook without destroying
    it. Re-rendering the whole page avoids a stale breadcrumb.
    """
    return render(
        request,
        "front/corpus/carnet_detail.html",
        _contexte_du_detail_du_carnet(request, carnet),
    )


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
        contexte = _contexte_de_la_liste_des_carnets(request)
        if request.headers.get("HX-Request"):
            return render(request, "front/corpus/carnets_liste.html", contexte)
        contexte["carnets_liste_preloaded"] = True
        return render(request, "front/base.html", contexte)

    def create(self, request):
        """
        POST /carnets/ — cree un carnet, comme POST /bases/ cree une base.
        / Creates a notebook, exactly as POST /bases/ creates a base.

        LOCALISATION : front/views_corpus.py

        POURQUOI CET ENDPOINT EXISTE (12 aout). Creer un carnet n'etait
        possible QUE depuis le pied du tiroir lateral
        (`#btn-creer-dossier-overlay`), qui postait sur `/dossiers/` et
        recevait un arbre en retour. Le tiroir part ; sans cet endpoint,
        plus personne ne peut creer de carnet — l'admin Django etant
        ferme, le produit serait ampute d'un de ses trois objets.
        / Creating a notebook was only possible from the side drawer's
        footer. The drawer goes away; without this, nobody can create a
        notebook at all.

        Un carnet EST un `Dossier` : le modele n'a jamais ete renomme,
        seul le vocabulaire de l'interface l'a ete (SPEC-corpus § 2).
        / A notebook IS a Dossier; only the UI vocabulary was renamed.
        """
        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        nom_soumis = str(request.data.get("nom", "")).strip()
        if not nom_soumis:
            return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                "erreurs": {"nom": ["Le nom est obligatoire / Name is required"]},
            }, status=400)

        Dossier.objects.create(name=nom_soumis[:200], owner=request.user)
        logger.info(
            "creer carnet: nom='%s' owner=%s", nom_soumis, request.user,
        )
        return self.list(request)

    def retrieve(self, request, pk=None):
        """
        GET /carnets/{id}/ — le carnet, ses notes, ses facettes.
        / The notebook, its notes, its facets.
        """
        carnet = get_object_or_404(Dossier, pk=pk)
        if not _utilisateur_a_acces_dossier(request.user, carnet):
            return _reponse_acces_refuse(request)

        # Requete HTMX -> le contenu seul ; acces direct (F5) -> la page
        # complete via base.html, comme LectureViewSet.
        # / HTMX -> content only; direct hit -> full base.html page.
        if request.headers.get("HX-Request"):
            return rendre_le_detail_du_carnet(request, carnet)
        contexte = _contexte_du_detail_du_carnet(request, carnet)
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
            # La regle vient du service ; ce bloc la recopiait mot pour
            # mot, puis refiltrait le resultat par le predicat — un
            # troisieme exemplaire de la meme condition.
            # / The rule comes from the service; this block used to copy
            # it verbatim and then re-filter the result by the predicate.
            carnets_disponibles = list(
                carnets_ou_ecrire(request.user)
                .exclude(pk__in=identifiants_deja_la)
                .select_related("owner")
                .order_by("name")
            )

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


def _filtre_des_carnets_d_une_base_visibles(
    utilisateur, prefixe="appartenances_dossiers__dossier",
):
    """
    Le filtre Q des carnets d'une base visibles par un utilisateur.
    Publics + les siens ; partages non comptes (sous-compte assume,
    jamais de fuite).
    / Q filter for a base's notebooks visible to a user.

    LOCALISATION : front/views_corpus.py

    Le prefixe existe parce que la MEME regle sert depuis deux points
    d'entree : depuis la base (« combien de carnets ? », prefixe par
    defaut) et depuis l'appartenance elle-meme (« lesquels nommer dans
    le sommaire d'une carte ? », prefixe « dossier »). Une regle de
    NON-FUITE ne doit exister qu'a un seul endroit : recopiee, elle
    derive, et c'est le sommaire qui se met alors a nommer un carnet
    prive d'autrui.
    / The prefix exists so the same no-leak rule serves both entry
    points; copied, such a rule drifts, and the drift is a leak.

    :param prefixe: le chemin ORM qui mene au Dossier depuis le modele
        interroge / the ORM path leading to the Dossier
    """
    filtre = Q(**{f"{prefixe}__visibilite": VisibiliteDossier.PUBLIC}) | Q(
        **{f"{prefixe}__owner__isnull": True}
    )
    if utilisateur is not None and utilisateur.is_authenticated:
        filtre = filtre | Q(**{f"{prefixe}__owner": utilisateur})
    return filtre


# Le nombre de teintes de cote disponibles (tokens --cote-1 a --cote-8
# de front/static/front/css/maquette.css). Huit, comme les huit familles
# d'hypostases : c'est le nombre de teintes que ce design system sait
# tenir a 3:1 sur le papier clair ET sur le papier sombre.
# / The number of available call-number tints.
NOMBRE_DE_TEINTES_DE_COTE = 8


def numero_de_cote_du_slug(slug):
    """
    Le numero de teinte (1 a 8) d'une base, derive de son slug.
    / A base's tint number (1..8), derived from its slug.

    LOCALISATION : front/views_corpus.py

    POURQUOI PAS `hash()` : en Python, `hash()` d'une chaine est SALE
    par processus (PYTHONHASHSEED). Deux workers gunicorn donneraient
    deux couleurs a la meme base, et la couleur changerait a chaque
    redemarrage. La somme des points de code, elle, est stable partout
    et pour toujours.
    / Python's hash() of a string is per-process salted: two gunicorn
    workers would give the same base two different colours.

    Une collision entre deux slugs est POSSIBLE et acceptee : la cote
    aide a distinguer les cartes d'un coup d'oeil, elle n'identifie
    pas — le nom identifie, et il est ecrit juste a cote.
    / A collision is possible and accepted: the tint helps tell cards
    apart, the name is what identifies.
    """
    somme_des_points_de_code = sum(ord(caractere) for caractere in slug)
    return somme_des_points_de_code % NOMBRE_DE_TEINTES_DE_COTE + 1


def bases_visibles_avec_leurs_comptes(utilisateur):
    """
    Rend les bases ouvrables par ce visiteur, comptees et cotees, plus le
    nombre de carnets distincts qu'elles totalisent.
    / Return the bases this visitor may open, counted and tinted, plus the
    number of distinct notebooks they hold.

    LOCALISATION : front/views_corpus.py

    POURQUOI CETTE FONCTION EXISTE

    Deux ecrans montrent ces bases : `/bases/` et, depuis le 12 aout,
    l'onglet « Bases de connaissances » de l'accueil. Recopier le calcul
    aurait recopie aussi la regle de non-fuite, les deux compteurs et
    leurs `distinct=True` — et la moindre correction n'aurait porte que
    sur une moitie. Le defaut existe deja au dossier : une meme base
    annoncait deux nombres de notes selon l'ecran, faute d'un filtre de
    type recopie d'un cote seulement.
    / Two screens show these bases; duplicating the query would duplicate
    the non-leak rule and both counters — and fixes would land on one
    half only. That exact defect already happened once.

    :return: (liste de BaseDeConnaissances, nombre de carnets distincts)
    """
    if utilisateur.is_authenticated:
        filtre = (
            Q(visibilite=VisibiliteDossier.PUBLIC)
            | Q(owner=utilisateur)
            | Q(owner__isnull=True)
        )
    else:
        filtre = Q(visibilite=VisibiliteDossier.PUBLIC)

    # LE SOMMAIRE D'UNE CARTE. La description d'une base est souvent
    # vide (elle l'est sur la base de developpement) : sans
    # substitut, la carte serait un cartouche creux. Le substitut
    # est de la DONNEE REELLE — les carnets reellement dedans — et
    # jamais un texte d'attente. On ne prefetch que les carnets
    # OUVRABLES : le sommaire les NOMME, la regle de non-fuite du
    # corpus s'applique donc mot pour mot.
    # / A card's summary. Descriptions are often empty, so the
    # substitute is real data: the notebooks actually inside, and
    # only those the caller may open — the summary names them.
    appartenances_ouvrables = (
        AppartenanceDossierBase.objects.filter(
            _filtre_des_carnets_d_une_base_visibles(
                utilisateur, prefixe="dossier",
            )
        )
        .select_related("dossier")
        .order_by("-epingle", "dossier__name")
        .distinct()
    )

    bases_visibles = (
        BaseDeConnaissances.objects.filter(filtre)
        .select_related("owner")
        .prefetch_related(
            models.Prefetch(
                "appartenances_dossiers",
                queryset=appartenances_ouvrables,
                to_attr="appartenances_ouvrables",
            ),
        )
        .annotate(
            # Ne compte que les carnets que le DEMANDEUR peut voir —
            # meme doctrine que « dans N carnets » (jamais de fuite,
            # sous-compte des partages assume). Relecture H, B1.
            # / Counts only notebooks the CALLER can see.
            nombre_de_carnets=models.Count(
                "appartenances_dossiers",
                filter=_filtre_des_carnets_d_une_base_visibles(utilisateur),
                distinct=True,
            ),
            # Le poids REEL d'une base : ses notes. Comptees a
            # travers ses carnets visibles, en excluant wikis et
            # syntheses par leur TYPE et les versions par leur
            # parent — exactement le compteur de /carnets/, dont le
            # defaut symetrique a ete corrige le 12 aout (une meme
            # base annoncerait sinon deux nombres selon l'ecran).
            # `distinct=True` : une note rangee dans deux carnets de
            # la MEME base ne pese qu'une fois, et sans lui la
            # double jointure gonflerait aussi le compte des
            # carnets ci-dessus.
            # / A base's real weight: its notes, counted through its
            # visible notebooks, wikis and syntheses excluded by
            # TYPE. distinct=True, or the double join inflates both
            # counters.
            nombre_de_notes=models.Count(
                "appartenances_dossiers__dossier__appartenances_pages__page",
                filter=(
                    _filtre_des_carnets_d_une_base_visibles(utilisateur)
                    & Q(
                        appartenances_dossiers__dossier__appartenances_pages__page__parent_page__isnull=True,
                        appartenances_dossiers__dossier__appartenances_pages__page__type_de_note=TypeDeNote.NOTE,
                    )
                ),
                distinct=True,
            ),
        )
        .distinct()
        .order_by("nom")
    )

    # La liste est evaluee ICI, une fois : la boucle qui suit lit le
    # prefetch, elle ne redeclenche aucune requete.
    # / The queryset is evaluated once here; the loop below only
    # reads the prefetch and issues no further query.
    bases_a_afficher = list(bases_visibles)

    identifiants_de_carnets_distincts = set()
    for base in bases_a_afficher:
        # La cote : l'identite visuelle d'une base qui n'a pas
        # d'image de couverture — c'est-a-dire, pour l'instant,
        # toutes. / The tint of a base with no cover image.
        base.numero_de_cote = numero_de_cote_du_slug(base.slug)
        for appartenance in base.appartenances_ouvrables:
            identifiants_de_carnets_distincts.add(appartenance.dossier_id)

    return bases_a_afficher, len(identifiants_de_carnets_distincts)


def _les_deux_zones_de_bases(bases_visibles, utilisateur):
    """
    Partage les bases visibles en deux : les miennes, celles des autres.
    / Split the visible bases in two: mine, and other people's.

    LOCALISATION : front/views_corpus.py

    POURQUOI DEUX ZONES ET NON UNE LISTE TRIEE

    Demande du mainteneur, 12 aout. Les deux moities ne se lisent pas de
    la meme facon : ce que j'ai cree, j'y REVIENS — c'est un espace de
    travail ; ce que d'autres publient, je l'EXPLORE — c'est un
    catalogue. Une seule liste triee par nom melangerait les deux
    intentions et obligerait a lire chaque ligne pour savoir dans
    laquelle on se trouve.

    UNE BASE NE FIGURE JAMAIS DES DEUX COTES. Une base a moi ET publique
    reste dans « les miennes » : la montrer deux fois ferait douter du
    sens des zones. L'appartenance l'emporte sur la publication.

    LA VISIBILITE N'EST PAS REJOUEE ICI. On decoupe une liste deja
    filtree par `bases_visibles_avec_leurs_comptes` : une base privee
    d'autrui n'y est jamais entree, et ce n'est pas a cette fonction de
    le reverifier — deux regles de visibilite finiraient par diverger.

    :param bases_visibles: les bases deja filtrees, annotees et rangees
    :param utilisateur: le demandeur (anonyme accepte)
    :return: le couple (mes_bases, bases_des_autres)
    / Ownership wins over publication; the visibility rule stays where it
    already is, never re-implemented here.
    """
    mes_bases = []
    bases_des_autres = []

    for base in bases_visibles:
        elle_est_a_moi = (
            utilisateur.is_authenticated and base.owner_id == utilisateur.pk
        )
        if elle_est_a_moi:
            mes_bases.append(base)
        else:
            bases_des_autres.append(base)

    return mes_bases, bases_des_autres


class BaseViewSet(viewsets.ViewSet):
    """
    La base de connaissances : liste, detail, rangement de carnets, axes.
    / The knowledge base: list, detail, notebook filing, axes.

    LOCALISATION : front/views_corpus.py

    Le pk d'URL est le SLUG (ex 'reseau-tiers-lieux-occitanie').
    / The URL pk is the SLUG.
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request, slug_de_la_base_creee=None):
        """
        GET /bases/ — les bases visibles. / Visible bases.

        :param slug_de_la_base_creee: pose par `create()` juste apres une
            creation, pour que le gabarit sache LAQUELLE des cartes vient
            d'apparaitre. Vaut None sur une simple consultation.
            / Set by create() so the template knows which card is new.
        """
        bases_a_afficher, nombre_total_de_carnets = (
            bases_visibles_avec_leurs_comptes(request.user)
        )

        mes_bases, bases_des_autres = _les_deux_zones_de_bases(
            bases_a_afficher, request.user
        )

        contexte = {
            "bases": bases_a_afficher,
            # LES DEUX ZONES, arrivees ici le 21 aout avec la disparition
            # de l'onglet « Bases de connaissances » de l'accueil, qui
            # les portait depuis le 12. Elles decoupent `bases` sans le
            # remplacer : le compteur de l'en-tete, lui, parle bien du
            # tout. / The two zones split `bases` without replacing it.
            "mes_bases": mes_bases,
            "bases_des_autres": bases_des_autres,
            "slug_de_la_base_creee": slug_de_la_base_creee,
            "nombre_de_bases": len(bases_a_afficher),
            # DISTINCT : un carnet range dans deux bases ne compte
            # qu'une fois. Additionner les compteurs par base le
            # compterait deux fois — meme regle que les totaux de
            # l'en-tete de /carnets/. Aucun cout : l'ensemble est
            # construit a partir du prefetch deja charge.
            # / DISTINCT: a notebook filed in two bases counts once.
            "nombre_total_de_carnets": nombre_total_de_carnets,
        }
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
            # Les trois niveaux, ecrits une fois : le gabarit boucle
            # dessus plutot que de repeter trois blocs presque
            # identiques. Meme cle et meme forme que le contexte du
            # carnet (`_contexte_du_detail_du_carnet`), pour que le
            # partial de formulaire n'ait pas a savoir qui l'appelle.
            # / The three levels, written once — same key and shape as
            # the notebook's context, so the shared form partial does
            # not need to know its caller.
            "niveaux_de_visibilite": [
                (VisibiliteDossier.PRIVE, "privé"),
                (VisibiliteDossier.PARTAGE, "partagé"),
                (VisibiliteDossier.PUBLIC, "public"),
            ],
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

        from front.serializers import CreationDeBaseSerializer

        if not request.user.is_authenticated:
            return _reponse_acces_refuse(request)

        # La validation passe par un serializer, comme partout ailleurs
        # dans le depot : il nettoie les balises HTML du nom, que la
        # carte, le fil d'Ariane et le titre de page affichent ensuite.
        # / Validation goes through a serializer, which strips HTML from
        # the name displayed by the card, breadcrumb and page title.
        serializer = CreationDeBaseSerializer(data=request.data)
        if not serializer.is_valid():
            return render(request, "front/corpus/partials/erreurs_formulaire.html", {
                "erreurs": serializer.errors,
            }, status=400)

        nom_soumis = serializer.validated_data["nom"]

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

        # ON DIT LAQUELLE VIENT D'ETRE CREEE. La reponse est la grille
        # ENTIERE, et les bases y sont rangees par nom : la nouvelle
        # atterrit a sa place alphabetique, pas la ou l'oeil revient
        # apres avoir clique « Creer ». Sur une dizaine de bases, il faut
        # la chercher. Le gabarit la marque, et le CSS l'eclaire un
        # instant.
        # / The response is the whole grid, sorted by name: the new base
        # lands at its alphabetical place, not where the eye returns.
        return self.list(request, slug_de_la_base_creee=slug_candidat)

    @action(detail=True, methods=["POST"], url_path="editer")
    def editer(self, request, pk=None):
        """
        POST /bases/{slug}/editer/ — nom, description, couverture,
        visibilite. / Name, description, cover image, visibility.

        LOCALISATION : front/views_corpus.py

        POURQUOI CET ENDPOINT EXISTE

        AUCUN de ces quatre champs n'etait atteignable. Ils existaient en
        base et la carte en affiche trois, mais rien ne permettait de les
        renseigner : l'admin Django est desactive, et la creation d'une
        base ne prend que le nom — une faute de frappe y devenait donc
        definitive, et une base restait `prive` a jamais. Un champ
        qu'aucun ecran ne remplit est un champ mort.

        UNE SOUMISSION PARTIELLE N'EFFACE RIEN : seules les cles
        REELLEMENT presentes sont ecrites (`update_fields`). Sans cette
        regle, un formulaire qui ne montre pas tous les champs viderait
        ceux qu'il tait.

        LE 404 PLUTOT QUE LE 403, comme partout dans le corpus : le slug
        EST le nom, et un 403 confirmerait l'existence d'une base privee
        a qui sonde des slugs.
        / None of the four fields was reachable anywhere. A partial
        submission writes only the keys actually present, so a form that
        hides a field cannot blank it. 404, never 403: the slug is the name.
        """
        from front.serializers import EditionDeBaseSerializer

        base = get_object_or_404(BaseDeConnaissances, slug=pk)
        if not _utilisateur_a_acces_base(request.user, base):
            from django.http import Http404
            raise Http404

        # L'ACCES EN LECTURE NE SUFFIT PAS. Une base publique se lit ;
        # elle ne s'ecrit que par son proprietaire.
        # / Public means readable, not writable.
        if not request.user.is_authenticated or base.owner_id != request.user.pk:
            return _reponse_acces_refuse(request)

        serializer = EditionDeBaseSerializer(data=request.data)
        if not serializer.is_valid():
            return render(
                request,
                "front/corpus/partials/erreurs_formulaire.html",
                {"erreurs": serializer.errors},
                status=400,
            )

        donnees = serializer.validated_data
        champs_modifies = []
        # LE SLUG NE SUIT PAS LE NOM, et c'est un choix : il est l'adresse
        # publique de la base. Le regenerer casserait toute URL deja
        # partagee, sans redirection pour la rattraper — et un lien mort
        # coute plus cher qu'un slug qui vieillit mal. C'est aussi ce que
        # fait le carnet, qui s'adresse par son `pk`, insensible au nom.
        # / The slug stays put: it is the base's public address, and
        # regenerating it would break every shared link with no redirect.
        if "nom" in donnees:
            base.nom = donnees["nom"]
            champs_modifies.append("nom")
        if "description" in donnees:
            base.description = donnees["description"]
            champs_modifies.append("description")
        # Une couverture absente du formulaire laisse en place celle qui
        # existe : on ne l'efface que sur demande explicite.
        # / An absent cover leaves the existing one alone.
        if donnees.get("image_de_couverture"):
            base.image_de_couverture = donnees["image_de_couverture"]
            champs_modifies.append("image_de_couverture")
        if "visibilite" in donnees:
            base.visibilite = donnees["visibilite"]
            champs_modifies.append("visibilite")
        if champs_modifies:
            base.save(update_fields=champs_modifies)

        # UN RETOUR EXPLICITE, sinon l'enregistrement est muet. La reponse
        # re-rend la page et le panneau se replie : a l'oeil, rien ne
        # distingue « c'est enregistre » de « le clic n'a pas pris ». Le
        # carnet annonce deja ses renommages et ses changements de
        # visibilite de cette facon.
        # / Without this the save is silent: the panel folds back and
        # nothing tells success from a click that never landed.
        import json

        reponse = self.retrieve(request, pk=pk)
        if champs_modifies:
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {"message": f"Base « {base.nom} » enregistrée"},
            })
        return reponse

    def destroy(self, request, pk=None):
        """
        DELETE /bases/{slug}/ — supprime la base, PAS ses carnets.
        / Deletes the base, not its notebooks.

        LOCALISATION : front/views_corpus.py

        CE QUI SURVIT, ET CE QUI PART

        Les CARNETS survivent : le niveau « base » est facultatif dans le
        modele (core/models.py, BaseDeConnaissances), un carnet vit tres
        bien sans base. Seule leur APPARTENANCE a celle-ci disparait —
        ils ressortent au niveau plateforme, la ou `/carnets/` les
        montre. C'est la meme doctrine que le carnet, qui ne detruit pas
        ses notes.

        Les AXES DE CLASSEMENT de la base partent avec elle, et leurs
        categories avec eux : ils ne decrivent que cette base, ils
        n'auraient nulle part ou aller. Le libelle de confirmation dit
        les deux, sinon la personne decouvre la perte apres coup.

        SEUL LE PROPRIETAIRE supprime. Une base publique se lit, elle ne
        se detruit pas pour autant — et le 404 plutot que le 403 vaut ici
        comme partout dans le corpus.
        / Notebooks survive: the base level is optional in the model, so
        only the membership goes. The base's own classification axes go
        with it — the confirmation text says both.
        """
        import json

        base = get_object_or_404(BaseDeConnaissances, slug=pk)
        if not _utilisateur_a_acces_base(request.user, base):
            from django.http import Http404
            raise Http404

        if not request.user.is_authenticated or base.owner_id != request.user.pk:
            return _reponse_acces_refuse(request)

        # Le nom est lu AVANT la suppression : apres, l'objet ne l'a plus
        # a offrir au message. / Read before deleting: afterwards the
        # object has no name left to give the message.
        nom_de_la_base_supprimee = base.nom
        base.delete()

        # La base n'existe plus : on ne peut plus montrer SA page, on
        # montre la collection d'ou elle vient.
        # / The base is gone: show the collection it came from.
        reponse = self.list(request)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {
                "message": f"Base « {nom_de_la_base_supprimee} » supprimée",
            },
        })
        return reponse

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
