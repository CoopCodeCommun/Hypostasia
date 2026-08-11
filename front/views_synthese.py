"""
Les endpoints de la couche synthese (SPEC-synthese § 10, phases H-I).
/ Synthesis layer endpoints (§ 10, phases H-I).

LOCALISATION : front/views_synthese.py

Toutes les reponses sont du HTML (HTMX). AllowAny avec controle PAR
OBJET, comme partout dans front/ : un carnet public est lisible par un
anonyme, l'ECRITURE sur le carnet est exigee pour creer, mettre a jour,
appliquer ou verifier.
/ HTML-only responses; per-object access control; notebook write access
required for every mutating gesture.

FLUX :
- Onglets Wikis / Syntheses de l'ecran carnet -> listes + formulaires
- Article (wiki ou synthese) -> renvois [N] cliquables -> panneau de
  preuve (GET /citations/{id}/preuve/)
- Wiki : proposer une mise a jour (tache), previsualiser les operations
  (diff avec l'AVANT, § 6.4), appliquer les retenues (applieur § 6 +
  fraicheur addendum n°1 + reindexation + tour incremente)
- Synthese dirigee : JAMAIS de mise a jour (§ 10) — le bouton est
  desactive avec son motif ; ecartees § 8 et couverture § 9 en partials
- Verifier (§ 7) : geste explicite -> tache asynchrone
"""

import logging

from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from core.models import (
    CategorieDossier, Dossier, Page, SourceLink, SyntheseDirigee,
    TypeDeNote, TypeLien, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from core.services.synthese import (
    MOTIF_DE_MARQUEUR, PerimetreDExtractionsInconnu, extractions_ecartees,
    couverture_de_la_note, notes_du_perimetre_d_un_wiki,
    notes_sources_du_carnet,
)

logger = logging.getLogger(__name__)


def _acces_ou_refus(request, carnet):
    """Acces lecture au carnet, sinon la reponse de refus. / Read gate."""
    from front.views import _reponse_acces_refuse, _utilisateur_a_acces_dossier

    if not _utilisateur_a_acces_dossier(request.user, carnet):
        return _reponse_acces_refuse(request)
    return None


def _ecriture_ou_refus(request, carnet):
    """Ecriture sur le carnet, sinon le refus. / Write gate."""
    from front.views import (
        _reponse_acces_refuse, _utilisateur_peut_ecrire_dossier,
    )

    if not request.user.is_authenticated:
        return _reponse_acces_refuse(request)
    if not _utilisateur_peut_ecrire_dossier(request.user, carnet):
        return _reponse_acces_refuse(request)
    return None


def _acces_article_ou_refus(request, page_d_article):
    """Acces a un article par ses carnets. / Article access by notebooks."""
    from front.views import _reponse_acces_refuse, _utilisateur_a_acces_page

    if not _utilisateur_a_acces_page(request.user, page_d_article):
        return _reponse_acces_refuse(request)
    return None


def _html_avec_renvois(page_d_article):
    """
    Le HTML de l'article avec des renvois [N] CLIQUABLES : chaque
    marqueur [[ext:N]] devient une ancre HTMX vers le panneau de preuve
    de SON SourceLink. Le numero suit l'ordre de premiere apparition —
    jamais persiste (§ 4.4).
    / The article HTML with clickable [N] references bound to their
    SourceLink; numbering by first appearance, never stored.

    LOCALISATION : front/views_synthese.py
    """
    import html as html_module

    import markdown

    from front.tasks import _nettoyer_le_html_de_synthese

    texte = page_d_article.text_readability or ""
    liens = list(
        SourceLink.objects.filter(
            page_cible=page_d_article, type_lien=TypeLien.CITE,
        ).order_by("start_char_cible", "pk")
    )

    numero_par_extraction = {}
    jetons = {}

    def _en_jeton(correspondance):
        identifiant = int(correspondance.group(1))
        position = correspondance.start()
        if identifiant not in numero_par_extraction:
            numero_par_extraction[identifiant] = (
                len(numero_par_extraction) + 1
            )
        numero = numero_par_extraction[identifiant]
        # Le lien du couple (paragraphe, extraction) : celui dont les
        # bornes cibles contiennent la position du marqueur.
        # / The link whose target bounds contain the marker position.
        lien_du_marqueur = next(
            (lien for lien in liens
             if lien.extraction_source_id == identifiant
             and lien.start_char_cible <= position <= lien.end_char_cible),
            None,
        )
        jeton = f"RENVOIJETON{numero}X{identifiant}FIN"
        jetons[jeton] = (numero, lien_du_marqueur)
        return jeton

    texte_a_rendre = MOTIF_DE_MARQUEUR.sub(_en_jeton, texte)
    html_rendu = _nettoyer_le_html_de_synthese(
        markdown.markdown(
            html_module.escape(texte_a_rendre),
            extensions=["extra", "nl2br"],
        )
    )
    for jeton, (numero, lien_du_marqueur) in jetons.items():
        if lien_du_marqueur is None:
            html_rendu = html_rendu.replace(jeton, f"[{numero}]")
            continue
        # Bouton exposant comme l'etalon (cible cliquable dediee) —
        # injecte APRES bleach, donc hors de son allowlist.
        # / Superscript button like the etalon, injected post-bleach.
        html_rendu = html_rendu.replace(
            jeton,
            f'<button type="button" class="renvoi" '
            f'data-testid="synthese-renvoi" '
            f'data-etat="{lien_du_marqueur.etat_de_verification}" '
            f'hx-get="/citations/{lien_du_marqueur.pk}/preuve/" '
            f'hx-target="#corps-preuve" hx-swap="innerHTML" '
            f'aria-label="Source {numero}">[{numero}]</button>',
        )

    # LES VERDICTS AU FIL DU TEXTE (confrontation, manque n°1) : chaque
    # paragraphe devient une .affirmation[data-verification] — verte,
    # bleue debat, orange, pointillee non verifiee, ou ROUGE s'il n'a
    # AUCUNE source (§ 4.4 : un paragraphe sans marqueur est une
    # affirmation non sourcee). L'etat d'un paragraphe multi-citations
    # est le PIRE de ses verdicts : une phrase n'est pas plus fiable
    # que sa plus mauvaise preuve.
    # / Per-paragraph verification states; worst verdict wins; no
    # marker = "non_source" in red.
    import re as re_module

    gravite = {
        "faible": 5, "conteste": 4, "non_verifie": 3,
        "source_debat": 2, "verifie": 1,
    }

    def _classer_le_paragraphe(correspondance):
        interieur = correspondance.group(1)
        etats_presents = re_module.findall(r'data-etat="([a-z_]+)"', interieur)
        if not etats_presents:
            etat_du_paragraphe = "non_source"
        else:
            etat_du_paragraphe = max(
                etats_presents, key=lambda e: gravite.get(e, 0),
            )
        # Le title NOMME l'etat : une couleur ne se lit pas toute
        # seule, et le lecteur ne connait pas la legende par coeur
        # (recette du 10 aout, F6). / Colour alone names nothing.
        return (
            f'<p class="affirmation" '
            f'data-verification="{etat_du_paragraphe}" '
            f'title="{_LIBELLES_DE_VERDICT.get(etat_du_paragraphe, etat_du_paragraphe)}"'
            f'>{interieur}</p>'
        )

    html_rendu = re_module.sub(
        r"<p>(.*?)</p>", _classer_le_paragraphe, html_rendu,
        flags=re_module.DOTALL,
    )
    return html_rendu


_LIBELLES_DE_VERDICT = {
    "verifie": "Vérifié : la source dit ceci mot pour mot, et l'implique.",
    "source_debat": "Source en débat : elle est contestée par des lecteurs.",
    "faible": "Faible : la source ne suffit pas à tout ce qui est affirmé.",
    "conteste": "Contesté par un lecteur.",
    "non_verifie": "Pas encore vérifié.",
    "non_source": "Non sourcé : ce paragraphe ne cite aucune preuve.",
}


def _qualifier_une_ligne_d_article(page_d_article):
    """
    La qualification d'une ligne de liste (confrontation, manque n°7) :
    N sources · N faibles · N ecartees — la fiabilite se voit AVANT
    d'ouvrir. / List-line quality counts, visible before opening.
    """
    liens = SourceLink.objects.filter(
        page_cible=page_d_article, type_lien=TypeLien.CITE,
    )
    try:
        nombre_d_ecartees = extractions_ecartees(page_d_article).count()
    except (PerimetreDExtractionsInconnu, ValueError):
        nombre_d_ecartees = None
    return {
        "sources": liens.exclude(extraction_source__isnull=True)
        .values("extraction_source_id").distinct().count(),
        "faibles": liens.filter(etat_de_verification="faible").count(),
        "verifiees": liens.filter(etat_de_verification="verifie").count(),
        "ecartees": nombre_d_ecartees,
    }


def _contexte_d_article(request, page_d_article):
    """Le contexte commun de l'ecran article. / Shared article context."""
    enregistrement_de_wiki = Wiki.objects.filter(
        page=page_d_article,
    ).select_related("dossier").first()
    enregistrement_de_dirigee = SyntheseDirigee.objects.filter(
        page=page_d_article,
    ).select_related("dossier", "produite_par").first()
    carnet = (
        enregistrement_de_wiki.dossier if enregistrement_de_wiki
        else (enregistrement_de_dirigee.dossier
              if enregistrement_de_dirigee else None)
    )
    from front.views import _utilisateur_peut_ecrire_dossier

    liens = SourceLink.objects.filter(
        page_cible=page_d_article, type_lien=TypeLien.CITE,
    )
    # « Citations 8 » quand la numerotation s'arrete a [6] etait deux
    # chiffres sous le meme mot (confrontation, divergence 9) : on
    # compte les SOURCES DISTINCTES, et les renvois a part.
    # / Distinct sources vs reference marks: two separate counts.
    nombre_de_renvois = liens.count()
    nombre_de_sources = (
        liens.exclude(extraction_source__isnull=True)
        .values("extraction_source_id").distinct().count()
    )
    comptes_de_verdicts = {
        "verifie": liens.filter(etat_de_verification="verifie").count(),
        "faible": liens.filter(etat_de_verification="faible").count(),
        "conteste": liens.filter(etat_de_verification="conteste").count(),
    }
    # Le compteur d'ecartees vit DANS le pli (confrontation, manque 4) :
    # le chiffre est le message. None = perimetre inconnu (historique).
    # / The left-out count lives in the summary; None = unknown scope.
    try:
        nombre_d_ecartees = extractions_ecartees(page_d_article).count()
    except (PerimetreDExtractionsInconnu, ValueError):
        nombre_d_ecartees = None
    # Le fil d'Ariane « Base > Carnet > Article » : un article n'a
    # qu'UN carnet (il en est le produit), donc pas de bascule ici — le
    # menu ne s'affiche qu'a partir de deux entrees.
    # / An article belongs to exactly one notebook: no switcher here.
    from front.views_corpus import contexte_du_fil_d_ariane
    fil = contexte_du_fil_d_ariane(request, carnet=carnet) if carnet else {}
    html_de_l_article = _html_avec_renvois(page_d_article)
    # Quels etats de verification l'article porte-t-il REELLEMENT ? La
    # legende les annoncait tous, « non source » compris, avant meme
    # qu'une verification ait eu lieu : elle promettait des couleurs que
    # le texte n'avait pas (recette du 10 aout, F7).
    # / Which verdicts does the article actually carry? The legend
    # announced all of them before any verification had run.
    import re as _re
    etats_presents = set(
        _re.findall(r'data-verification="([a-z_]+)"', html_de_l_article)
    )
    return {
        **fil,
        "fil_note": page_d_article,
        "etats_de_verification_presents": etats_presents,
        "article": page_d_article,
        "wiki": enregistrement_de_wiki,
        "dirigee": enregistrement_de_dirigee,
        "carnet": carnet,
        "html_de_l_article": html_de_l_article,
        "nombre_de_renvois": nombre_de_renvois,
        "nombre_de_citations": nombre_de_sources,
        "comptes_de_verdicts": comptes_de_verdicts,
        "nombre_d_ecartees": nombre_d_ecartees,
        "peut_ecrire": (
            request.user.is_authenticated and carnet is not None
            and _utilisateur_peut_ecrire_dossier(request.user, carnet)
        ),
    }


def _etat_de_la_tache(request, page_d_article, carnet, apres):
    """
    L'etat d'une production asynchrone, interrogeable en boucle.
    / The state of an async production, pollable.

    LOCALISATION : front/views_synthese.py

    POURQUOI. Une production (wiki, synthese) se lancait en RENVOYANT LA
    LISTE : le nouvel objet y apparaissait comme s'il etait fini —
    « tour 1 · 0 sources » — alors que la tache venait a peine de
    partir. Rien ne disait d'attendre, rien ne se rafraichissait, et
    l'utilisateur recliquait (recette du 10 aout, friction F1). La
    verification, elle, affichait un message qui ne partait JAMAIS,
    faute d'interrogation (F2). Ce point d'entree unique repond aux
    deux : tant que le job tourne il se renvoie lui-meme, et quand il
    finit il rend le resultat.

    `apres` dit quoi rendre a la fin : la LISTE apres une production
    (l'utilisateur est dans l'onglet, il voit sa ligne complete avec
    ses vrais compteurs) ou l'ARTICLE apres une verification (il y est
    deja, ce sont les verdicts qu'il attend).

    Le compteur d'essais evite la boucle sans fin : si un worker est
    mort, l'ecran finit par le DIRE au lieu d'interroger indefiniment.
    / A pollable single entry point; the attempt counter turns a dead
    worker into a message instead of an endless poll.
    """
    from hypostasis_extractor.models import ExtractionJob, ExtractionJobStatus

    identifiant_de_job = request.GET.get("job_id", "")
    if not str(identifiant_de_job).isdigit():
        return render(request, "front/corpus/partials/erreur.html", {
            "message": "Tâche introuvable : impossible de suivre cette "
                       "production.",
        }, status=400)

    job = ExtractionJob.objects.filter(
        pk=int(identifiant_de_job), page=page_d_article,
    ).first()
    if job is None:
        return render(request, "front/corpus/partials/erreur.html", {
            "message": "Tâche introuvable : impossible de suivre cette "
                       "production.",
        }, status=404)

    if job.status == ExtractionJobStatus.ERROR:
        return render(request, "front/corpus/partials/erreur.html", {
            "message": "La production a échoué. Rien n'a été modifié. "
                       "Vous pouvez relancer le geste ; si l'échec se "
                       "répète, l'erreur est dans les journaux du "
                       "serveur.",
        })

    if job.status != ExtractionJobStatus.COMPLETED:
        essais = request.GET.get("essais", "0")
        essais = int(essais) + 1 if str(essais).isdigit() else 1
        # ~5 minutes a 3 secondes d'intervalle. Au-dela, on cesse
        # d'interroger et on le dit. / Stop polling and say so.
        if essais > 100:
            return render(request, "front/corpus/partials/tache_lancee.html", {
                "message": "Cette production prend plus de temps que "
                           "prévu. Elle continue peut-être en arrière-"
                           "plan : rechargez la page dans un moment "
                           "pour voir où elle en est.",
            })
        suffixe = "&apres=article" if apres == "article" else ""
        return render(request, "front/corpus/partials/tache_lancee.html", {
            "message": _MESSAGES_D_ATTENTE.get(apres, _MESSAGES_D_ATTENTE["liste"]),
            "hx_get": (
                f"{request.path}?job_id={job.pk}&essais={essais}{suffixe}"
            ),
        })

    # Termine : on rend ce que l'utilisateur attend.
    if apres == "article":
        contexte = _contexte_d_article(request, page_d_article)
        return render(request, "front/corpus/article.html", contexte)
    return None  # au caller de rendre la liste : il connait son ViewSet


_MESSAGES_D_ATTENTE = {
    "liste": "Rédaction en cours… L'article s'affichera ici dès qu'il "
             "sera prêt. Vous pouvez quitter cette page : la production "
             "continue, et « Mes tâches » vous préviendra.",
    "article": "Vérification en cours : verbatim d'abord, puis le juge "
               "d'implication, paire par paire. Les verdicts "
               "s'afficheront ici, avec leur provenance.",
}


class WikiViewSet(viewsets.ViewSet):
    """Les wikis d'un carnet (§ 3.1, § 10). / Notebook wikis."""

    permission_classes = [permissions.AllowAny]

    def lister_pour_le_carnet(self, request, pk=None):
        """GET /carnets/{id}/wikis/ — l'onglet Wikis. / The Wikis tab."""
        carnet = get_object_or_404(Dossier, pk=pk)
        refus = _acces_ou_refus(request, carnet)
        if refus:
            return refus
        # Acces direct -> l'ecran carnet complet (le partial serait nu).
        # / Direct hit -> the full notebook screen.
        if request.method == "GET" and not request.headers.get("HX-Request"):
            from django.shortcuts import redirect
            return redirect(f"/carnets/{carnet.pk}/")
        from front.views import _utilisateur_peut_ecrire_dossier

        wikis = list(
            Wiki.objects.filter(dossier=carnet)
            .select_related("page").order_by("-derniere_mise_a_jour")
        )
        for wiki in wikis:
            wiki.qualite = _qualifier_une_ligne_d_article(wiki.page)
        from core.models import Configuration
        return render(request, "front/corpus/liste_wikis.html", {
            "carnet": carnet,
            "wikis": wikis,
            # Le moteur ne se CHOISIT pas a la creation (recette, F10) :
            # a defaut de le choisir, l'ecran doit au moins le DIRE, et
            # dire ou il se change. / The engine is not chosen here; the
            # screen must at least name it.
            "modele_de_redaction": Configuration.get_solo().ai_model,
            "nombre_de_notes_sources":
                notes_sources_du_carnet(carnet).count(),
            "peut_ecrire": (
                request.user.is_authenticated
                and _utilisateur_peut_ecrire_dossier(request.user, carnet)
            ),
        })

    def creer_pour_le_carnet(self, request, pk=None):
        """
        POST /carnets/{id}/wikis/ — cree le wiki et lance la production.
        / Creates the wiki and launches production.
        """
        carnet = get_object_or_404(Dossier, pk=pk)
        refus = _ecriture_ou_refus(request, carnet)
        if refus:
            return refus

        sujet = (request.data.get("sujet") or "").strip()
        if not sujet:
            return render(request, "front/corpus/partials/erreur.html", {
                "message": "Le sujet du wiki est obligatoire : c'est la "
                           "consigne de rédaction de l'article.",
            }, status=400)

        page_d_article = Page.objects.create(
            title=f"Wiki — {sujet}"[:500],
            text_readability="", html_readability="", html_original="",
            content_hash="", type_de_note=TypeDeNote.WIKI,
            owner=request.user,
        )
        ranger_une_note_dans_un_carnet(page_d_article, carnet, request.user)
        wiki = Wiki.objects.create(
            page=page_d_article, dossier=carnet, sujet=sujet,
        )
        identifiants_de_categories = [
            int(v) for v in request.data.getlist("categorie")
            if str(v).isdigit()
        ]
        if identifiants_de_categories:
            wiki.categories_du_perimetre.set(
                CategorieDossier.objects.filter(
                    pk__in=identifiants_de_categories,
                    liste__dossier=carnet,
                )
            )

        from core.models import Configuration
        from hypostasis_extractor.models import ExtractionJob

        job = ExtractionJob.objects.create(
            page=page_d_article,
            ai_model=Configuration.get_solo().ai_model,
            name=f"Wiki — {sujet}"[:200],
            prompt_description="Production d'article de wiki (phase H)",
            status="pending",
            raw_result={
                "est_wiki": True, "wiki_id": wiki.pk,
                "demandeur_id": request.user.pk,
            },
        )
        from front.tasks import produire_un_wiki_task
        produire_un_wiki_task.delay(job.pk)

        # On NE renvoie PAS la liste : elle montrerait le wiki comme
        # s'il etait fini (« tour 1 · 0 sources ») alors que la tache
        # vient de partir (recette du 10 aout, F1). On renvoie un etat
        # qui s'interroge lui-meme et laissera place a la liste.
        # / Returning the list would show the wiki as finished.
        return render(request, "front/corpus/partials/tache_lancee.html", {
            "message": _MESSAGES_D_ATTENTE["liste"],
            "hx_get": f"/wikis/{wiki.pk}/etat/?job_id={job.pk}",
        })

    @action(detail=True, methods=["GET"], url_path="etat")
    def etat(self, request, pk=None):
        """GET /wikis/{id}/etat/?job_id=N — l'avancement d'une tache.

        Rend la LISTE quand une production s'acheve, l'ARTICLE quand
        c'est une verification (?apres=article).
        / Polling endpoint: list after a production, article after a
        verification.
        """
        wiki = get_object_or_404(
            Wiki.objects.select_related("page", "dossier"), pk=pk,
        )
        refus = _acces_article_ou_refus(request, wiki.page)
        if refus:
            return refus
        apres = "article" if request.GET.get("apres") == "article" else "liste"
        reponse = _etat_de_la_tache(request, wiki.page, wiki.dossier, apres)
        if reponse is not None:
            return reponse
        return self.lister_pour_le_carnet(request, pk=wiki.dossier_id)

    def retrieve(self, request, pk=None):
        """GET /wikis/{id}/ — l'article. / The article."""
        wiki = get_object_or_404(
            Wiki.objects.select_related("page", "dossier"), pk=pk,
        )
        refus = _acces_article_ou_refus(request, wiki.page)
        if refus:
            return refus
        contexte = _contexte_d_article(request, wiki.page)
        contexte["perimetre_de_notes"] = (
            notes_du_perimetre_d_un_wiki(wiki).count()
        )
        # Acces direct (F5, lien partage) -> la page complete dans le
        # chrome ; HTMX -> le contenu seul (audit visuel n°11).
        # / Direct hit -> full page; HTMX -> content only.
        if request.headers.get("HX-Request"):
            return render(request, "front/corpus/article.html", contexte)
        contexte["article_preloaded"] = True
        return render(request, "front/base.html", contexte)

    @action(detail=True, methods=["POST"], url_path="mise_a_jour")
    def mise_a_jour(self, request, pk=None):
        """
        POST /wikis/{id}/mise_a_jour/ — lance la PROPOSITION (jamais
        l'application). / Launches the proposal, never the application.
        """
        wiki = get_object_or_404(Wiki, pk=pk)
        refus = _ecriture_ou_refus(request, wiki.dossier)
        if refus:
            return refus
        from core.models import Configuration
        from hypostasis_extractor.models import ExtractionJob

        job = ExtractionJob.objects.create(
            page=wiki.page, ai_model=Configuration.get_solo().ai_model,
            name=f"Mise à jour — {wiki.sujet}"[:200],
            prompt_description="Proposition d'opérations (phase H)",
            status="pending",
            raw_result={
                "est_maj_wiki": True, "wiki_id": wiki.pk,
                "demandeur_id": request.user.pk,
            },
        )
        from front.tasks import proposer_une_maj_de_wiki_task
        proposer_une_maj_de_wiki_task.delay(job.pk)
        return render(request, "front/corpus/partials/tache_lancee.html", {
            "message": "La proposition de mise à jour est en cours de "
                       "rédaction. Elle vous attendra ici : rien ne "
                       "sera appliqué sans votre accord.",
            "hx_get": f"/wikis/{wiki.pk}/proposition/?job_id={job.pk}",
        })

    @action(detail=True, methods=["GET"], url_path="proposition")
    def proposition(self, request, pk=None):
        """
        GET /wikis/{id}/proposition/?job_id=N — le diff des operations,
        avec l'AVANT (§ 6.4, phase I). Poll tant que la tache tourne.
        / The operations diff with the before; polls while running.
        """
        wiki = get_object_or_404(Wiki, pk=pk)
        refus = _ecriture_ou_refus(request, wiki.dossier)
        if refus:
            return refus
        from hypostasis_extractor.models import ExtractionJob

        identifiant_de_job = request.GET.get("job_id", "")
        job = get_object_or_404(
            ExtractionJob,
            pk=int(identifiant_de_job) if identifiant_de_job.isdigit() else 0,
            page=wiki.page, raw_result__est_maj_wiki=True,
        )
        if job.status in ("pending", "processing"):
            return render(
                request, "front/corpus/partials/tache_lancee.html", {
                    "message": "Proposition en cours de rédaction…",
                    "hx_get":
                        f"/wikis/{wiki.pk}/proposition/?job_id={job.pk}",
                    "recharger": True,
                },
            )
        if job.status != "completed":
            return render(request, "front/corpus/partials/erreur.html", {
                "message": job.error_message
                or "La proposition a échoué. Relancez la mise à jour.",
            }, status=200)

        # Previsualisation par UN PASSAGE A BLANC de l'applieur (§ 6.4) :
        # les rejets mecaniques et l'« avant » de chaque replace viennent
        # du meme code que l'application reelle — jamais deux verites.
        # / Preview via a dry run of the very applier used for real.
        from core.services.section_ops import appliquer_les_operations
        from core.services.synthese import extractions_du_perimetre

        identifiants_du_perimetre = set(
            extractions_du_perimetre(wiki.page).values_list("pk", flat=True)
        )
        bilan_a_blanc = appliquer_les_operations(
            wiki.page.text_readability or "",
            job.raw_result.get("operations", []),
            identifiants_du_perimetre,
        )
        return render(request, "front/corpus/partials/diff_operations.html", {
            "wiki": wiki,
            "job": job,
            "bilan": bilan_a_blanc,
            "updated_at_de_l_article":
                job.raw_result.get("updated_at_de_l_article", ""),
        })

    @action(detail=True, methods=["POST"], url_path="appliquer")
    def appliquer(self, request, pk=None):
        """
        POST /wikis/{id}/appliquer/ — applique les operations RETENUES
        par l'humain. Fraicheur d'abord (addendum n°1), reindexation,
        tour incremente, contestations perdues montrees.
        / Applies the human-retained operations; freshness first.
        """
        wiki = get_object_or_404(Wiki.objects.select_related("page"), pk=pk)
        refus = _ecriture_ou_refus(request, wiki.dossier)
        if refus:
            return refus
        from hypostasis_extractor.models import ExtractionJob

        identifiant_de_job = str(request.data.get("job_id", ""))
        job = get_object_or_404(
            ExtractionJob,
            pk=int(identifiant_de_job) if identifiant_de_job.isdigit() else 0,
            page=wiki.page, raw_result__est_maj_wiki=True,
        )

        from core.services.section_ops import (
            PropositionPerimee, appliquer_les_operations,
            verifier_que_la_proposition_est_fraiche,
        )

        try:
            verifier_que_la_proposition_est_fraiche(
                wiki.page,
                job.raw_result.get("updated_at_de_l_article", ""),
            )
        except PropositionPerimee as peremption:
            return render(request, "front/corpus/partials/erreur.html", {
                "message": str(peremption).split("/")[0].strip(),
            }, status=409)

        indices_retenus = {
            int(v) for v in str(request.data.get("indices", "")).split(",")
            if v.strip().isdigit()
        }
        operations = job.raw_result.get("operations", [])
        operations_retenues = [
            operation for indice, operation in enumerate(operations)
            if indice in indices_retenus
        ]

        from core.services.synthese import extractions_du_perimetre

        identifiants_du_perimetre = set(
            extractions_du_perimetre(wiki.page).values_list("pk", flat=True)
        )
        bilan = appliquer_les_operations(
            wiki.page.text_readability or "",
            operations_retenues, identifiants_du_perimetre,
        )

        from front.tasks import _ecrire_le_corps_d_un_article

        bilan_d_indexation = _ecrire_le_corps_d_un_article(
            wiki.page, bilan["texte_final"], identifiants_du_perimetre,
        )
        wiki.tours_de_mise_a_jour += 1
        wiki.save(update_fields=[
            "tours_de_mise_a_jour", "derniere_mise_a_jour",
        ])

        contexte = _contexte_d_article(request, wiki.page)
        contexte.update({
            "perimetre_de_notes": notes_du_perimetre_d_un_wiki(wiki).count(),
            "operations_appliquees": bilan["operations_appliquees"],
            "operations_rejetees": bilan["operations_rejetees"],
            # JAMAIS en silence : une contestation humaine dont la paire
            # a disparu est montree (relecture G, B1).
            # / Lost human contestations are shown, never swallowed.
            "contestations_perdues":
                bilan_d_indexation.get("contestations_perdues", []),
        })
        return render(request, "front/corpus/article.html", contexte)

    @action(detail=True, methods=["POST"], url_path="verifier")
    def verifier(self, request, pk=None):
        """POST /wikis/{id}/verifier/ — la verification § 7, a la
        demande. / On-demand § 7 verification."""
        wiki = get_object_or_404(Wiki, pk=pk)
        refus = _ecriture_ou_refus(request, wiki.dossier)
        if refus:
            return refus
        return _lancer_une_verification(request, wiki.page)


def _lancer_une_verification(request, page_d_article):
    """Cree le job de verification et lance la tache. / Launches § 7."""
    from core.models import Configuration
    from hypostasis_extractor.models import ExtractionJob

    job = ExtractionJob.objects.create(
        page=page_d_article,
        ai_model=Configuration.get_solo().ai_model,
        name=f"Vérification — {page_d_article.title}"[:200],
        prompt_description="Vérification des citations (§ 7)",
        status="pending",
        raw_result={
            "est_verification": True,
            "demandeur_id": request.user.pk,
        },
    )
    from front.tasks import verifier_les_citations_task
    verifier_les_citations_task.delay(job.pk)
    # Sans hx_get, ce message restait affiche POUR TOUJOURS : les
    # verdicts n'apparaissaient qu'apres un rechargement manuel que
    # rien ne suggerait (recette du 10 aout, F2).
    # / Without hx_get this message never went away.
    from core.models import Wiki as ModeleWiki
    enregistrement_de_wiki = ModeleWiki.objects.filter(
        page=page_d_article,
    ).only("pk").first()
    racine = (
        f"/wikis/{enregistrement_de_wiki.pk}" if enregistrement_de_wiki
        else f"/syntheses/{page_d_article.pk}"
    )
    return render(request, "front/corpus/partials/tache_lancee.html", {
        "message": _MESSAGES_D_ATTENTE["article"],
        "hx_get": f"{racine}/etat/?job_id={job.pk}&apres=article",
    })


class SyntheseViewSet(viewsets.ViewSet):
    """Les syntheses dirigees (§ 3.2, § 10). / Frozen syntheses."""

    permission_classes = [permissions.AllowAny]

    def lister_pour_le_carnet(self, request, pk=None):
        """GET /carnets/{id}/syntheses/ — l'onglet. / The tab."""
        carnet = get_object_or_404(Dossier, pk=pk)
        refus = _acces_ou_refus(request, carnet)
        if refus:
            return refus
        # Acces direct -> l'ecran carnet complet (le partial serait nu).
        # / Direct hit -> the full notebook screen.
        if request.method == "GET" and not request.headers.get("HX-Request"):
            from django.shortcuts import redirect
            return redirect(f"/carnets/{carnet.pk}/")
        from front.views import _utilisateur_peut_ecrire_dossier

        syntheses = list(
            SyntheseDirigee.objects.filter(dossier=carnet)
            .select_related("page", "produite_par")
            .order_by("-produite_le")
        )
        for synthese in syntheses:
            synthese.qualite = _qualifier_une_ligne_d_article(synthese.page)
        axes = list(
            carnet.listes_de_categories.prefetch_related(
                "categories_de_dossier",
            )
        )
        from core.models import Configuration
        return render(request, "front/corpus/liste_syntheses.html", {
            "carnet": carnet,
            "syntheses": syntheses,
            "axes": axes,
            # Meme raison que pour le wiki (recette, F10).
            "modele_de_redaction": Configuration.get_solo().ai_model,
            "nombre_de_notes_sources":
                notes_sources_du_carnet(carnet).count(),
            "peut_ecrire": (
                request.user.is_authenticated
                and _utilisateur_peut_ecrire_dossier(request.user, carnet)
            ),
        })

    def creer_pour_le_carnet(self, request, pk=None):
        """
        POST /carnets/{id}/syntheses/ — fige le perimetre AU MOMENT DU
        GESTE (§ 3.2) et lance la production. Le garde-fou § 3.3 est
        mecanique : notes_sources_du_carnet exclut les syntheses.
        / Freezes the scope at request time and launches production.
        """
        carnet = get_object_or_404(Dossier, pk=pk)
        refus = _ecriture_ou_refus(request, carnet)
        if refus:
            return refus

        titre = (request.data.get("titre") or "").strip()
        if not titre:
            return render(request, "front/corpus/partials/erreur.html", {
                "message": "Le titre de la synthèse est obligatoire : "
                           "c'est ce que le collectif adoptera.",
            }, status=400)

        notes_retenues = notes_sources_du_carnet(carnet)
        categorie_de_direction = None
        identifiant_de_categorie = str(request.data.get("categorie_id", ""))
        if identifiant_de_categorie.isdigit():
            categorie_de_direction = CategorieDossier.objects.filter(
                pk=int(identifiant_de_categorie), liste__dossier=carnet,
            ).first()
            if categorie_de_direction is not None:
                notes_retenues = notes_retenues.filter(
                    appartenances_dossiers__dossier=carnet,
                    appartenances_dossiers__categories=categorie_de_direction,
                )
        notes_figees = list(notes_retenues.values_list("pk", flat=True))

        page_de_synthese = Page.objects.create(
            title=titre[:500],
            text_readability="", html_readability="", html_original="",
            content_hash="", type_de_note=TypeDeNote.SYNTHESE,
            owner=request.user,
        )
        ranger_une_note_dans_un_carnet(page_de_synthese, carnet, request.user)
        synthese_dirigee = SyntheseDirigee.objects.create(
            page=page_de_synthese, dossier=carnet,
            produite_par=request.user, produite_le=timezone.now(),
            categorie_de_direction=categorie_de_direction,
            axe_de_direction=(
                categorie_de_direction.liste
                if categorie_de_direction else None
            ),
            perimetre_d_extractions_fige=True,
        )
        synthese_dirigee.notes_du_perimetre.set(notes_figees)

        from core.models import Configuration
        from hypostasis_extractor.models import ExtractionJob

        job = ExtractionJob.objects.create(
            page=page_de_synthese,
            ai_model=Configuration.get_solo().ai_model,
            name=titre[:200],
            prompt_description="Synthèse dirigée de carnet (phase H)",
            status="pending",
            raw_result={
                "est_synthese_carnet": True,
                "demandeur_id": request.user.pk,
                "notes_du_perimetre": notes_figees,
            },
        )
        from front.tasks import produire_une_synthese_de_carnet_task
        produire_une_synthese_de_carnet_task.delay(job.pk)

        # Meme raison que pour le wiki (recette du 10 aout, F1) : la
        # liste montrerait la synthese comme si elle etait redigee.
        # / Same as the wiki: the list would look finished.
        return render(request, "front/corpus/partials/tache_lancee.html", {
            "message": _MESSAGES_D_ATTENTE["liste"],
            "hx_get": f"/syntheses/{page_de_synthese.pk}/etat/?job_id={job.pk}",
        })

    @action(detail=True, methods=["GET"], url_path="etat")
    def etat(self, request, pk=None):
        """GET /syntheses/{page_id}/etat/?job_id=N — l'avancement.

        L'identifiant est celui de la PAGE, comme partout dans ce
        ViewSet. / The id is the PAGE id, as everywhere here.
        """
        page_de_synthese = get_object_or_404(
            Page, pk=pk, type_de_note=TypeDeNote.SYNTHESE,
        )
        refus = _acces_article_ou_refus(request, page_de_synthese)
        if refus:
            return refus
        enregistrement = SyntheseDirigee.objects.filter(
            page=page_de_synthese,
        ).select_related("dossier").first()
        carnet_de_la_synthese = enregistrement.dossier if enregistrement else None
        apres = "article" if request.GET.get("apres") == "article" else "liste"
        reponse = _etat_de_la_tache(
            request, page_de_synthese, carnet_de_la_synthese, apres,
        )
        if reponse is not None:
            return reponse
        if carnet_de_la_synthese is None:
            # Une synthese sans carnet (dossier SET_NULL, ecart assume
            # de l'addendum n°5) n'a pas de liste ou retourner : on rend
            # l'article. / A notebook-less synthesis has no list.
            contexte = _contexte_d_article(request, page_de_synthese)
            return render(request, "front/corpus/article.html", contexte)
        return self.lister_pour_le_carnet(request, pk=carnet_de_la_synthese.pk)

    def retrieve(self, request, pk=None):
        """GET /syntheses/{page_id}/ — l'article fige. / The frozen
        article. L'identifiant est celui de la PAGE de l'article."""
        page_de_synthese = get_object_or_404(
            Page, pk=pk, type_de_note=TypeDeNote.SYNTHESE,
        )
        refus = _acces_article_ou_refus(request, page_de_synthese)
        if refus:
            return refus
        contexte = _contexte_d_article(request, page_de_synthese)
        if request.headers.get("HX-Request"):
            return render(request, "front/corpus/article.html", contexte)
        contexte["article_preloaded"] = True
        return render(request, "front/base.html", contexte)

    @action(detail=True, methods=["GET"], url_path="ecartees")
    def ecartees(self, request, pk=None):
        """GET /syntheses/{page_id}/ecartees/ — § 8, jamais une liste
        stockee. / § 8 partial, always computed."""
        page_de_synthese = get_object_or_404(Page, pk=pk)
        refus = _acces_article_ou_refus(request, page_de_synthese)
        if refus:
            return refus
        try:
            toutes_les_ecartees = extractions_ecartees(page_de_synthese)
            # La fenetre de 200 est ANNONCEE (recette du 10 aout, B3) :
            # le resume disait « 458 » quand le volet en montrait 200,
            # sans un mot. Le total est passe au template.
            # / The 200-row window is announced; the total is passed.
            nombre_total_d_ecartees = toutes_les_ecartees.count()
            ecartees = list(
                toutes_les_ecartees.select_related("job__page")[:200]
            )
            perimetre_inconnu = False
        except PerimetreDExtractionsInconnu:
            # Une dirigee historique : dire « inconnu » plutot que
            # mentir « 100 % ecarte » (relecture E, I2).
            # / Historical synthesis: say "unknown", never lie.
            ecartees = []
            nombre_total_d_ecartees = 0
            perimetre_inconnu = True
        return render(request, "front/corpus/partials/ecartees.html", {
            "article": page_de_synthese,
            "ecartees": ecartees,
            "nombre_total_d_ecartees": nombre_total_d_ecartees,
            "perimetre_inconnu": perimetre_inconnu,
        })

    @action(detail=True, methods=["GET"], url_path="couverture")
    def couverture(self, request, pk=None):
        """GET /syntheses/{page_id}/couverture/ — § 9, la jointure par
        note du perimetre. / § 9 partial, per scoped note."""
        page_de_synthese = get_object_or_404(Page, pk=pk)
        refus = _acces_article_ou_refus(request, page_de_synthese)
        if refus:
            return refus
        dirigee = SyntheseDirigee.objects.filter(
            page=page_de_synthese,
        ).first()
        notes = (
            list(dirigee.notes_du_perimetre.all()) if dirigee else []
        )
        couvertures = [
            {"note": note, **couverture_de_la_note(note)}
            for note in notes
        ]
        return render(request, "front/corpus/partials/couverture.html", {
            "article": page_de_synthese,
            "couvertures": couvertures,
        })

    @action(detail=True, methods=["POST"], url_path="verifier")
    def verifier(self, request, pk=None):
        """POST /syntheses/{page_id}/verifier/ — § 7 a la demande."""
        page_de_synthese = get_object_or_404(Page, pk=pk)
        dirigee = SyntheseDirigee.objects.filter(
            page=page_de_synthese,
        ).select_related("dossier").first()
        carnet = dirigee.dossier if dirigee else None
        if carnet is None:
            from front.views import _reponse_acces_refuse
            return _reponse_acces_refuse(request)
        refus = _ecriture_ou_refus(request, carnet)
        if refus:
            return refus
        return _lancer_une_verification(request, page_de_synthese)


class CitationViewSet(viewsets.ViewSet):
    """Le panneau de preuve d'une citation. / The evidence panel."""

    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=["GET"], url_path="preuve")
    def preuve(self, request, pk=None):
        """
        GET /citations/{id}/preuve/ — la citation exacte, son etat de
        verification AVEC provenance, le debat joint, le retour a la
        source. / Exact quote, provenanced verdict, debate, deep link.
        """
        lien = get_object_or_404(
            SourceLink.objects.select_related(
                "page_cible", "extraction_source__job__page",
                "ancrage_source",
            ).prefetch_related("extraction_source__commentaires__user",
                               "commentaires_source"),
            pk=pk, type_lien=TypeLien.CITE,
        )
        refus = _acces_article_ou_refus(request, lien.page_cible)
        if refus:
            return refus
        extraction = lien.extraction_source
        return render(request, "front/corpus/partials/preuve.html", {
            "lien": lien,
            "extraction": extraction,
            "note_source": extraction.job.page if extraction else None,
        })
