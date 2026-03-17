"""
ViewSet d'alignement cross-documents par hypostases (PHASE-18).
/ Cross-document alignment ViewSet by hypostases (PHASE-18).

LOCALISATION : front/views_alignement.py

Compare 2 a 6 documents : tableau croise hypostases (lignes) x documents (colonnes).
Revele les gaps argumentatifs entre les textes.
"""
import unicodedata

from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import viewsets
from rest_framework.decorators import action

from core.models import Dossier, Page
from hypostasis_extractor.models import ExtractedEntity


# --- Mapping hypostase → famille (copie locale pour eviter les imports circulaires) ---
# / --- Hypostase → family mapping (local copy to avoid circular imports) ---
HYPOSTASE_VERS_FAMILLE = {
    'classification': 'epistemique', 'axiome': 'epistemique', 'theorie': 'epistemique',
    'definition': 'epistemique', 'formalisme': 'epistemique',
    'phenomene': 'empirique', 'evenement': 'empirique', 'donnee': 'empirique',
    'variable': 'empirique', 'indice': 'empirique',
    'hypothese': 'speculatif', 'conjecture': 'speculatif', 'approximation': 'speculatif',
    'structure': 'structurel', 'invariant': 'structurel', 'dimension': 'structurel',
    'domaine': 'structurel',
    'loi': 'normatif', 'principe': 'normatif', 'valeur': 'normatif', 'croyance': 'normatif',
    'aporie': 'problematique', 'paradoxe': 'problematique', 'probleme': 'problematique',
    'mode': 'mode', 'variation': 'mode', 'variance': 'mode', 'paradigme': 'mode',
    'objet': 'objet', 'methode': 'objet',
}

# Ordre d'affichage des familles dans le tableau
# / Display order of families in the table
FAMILLES_ORDONNEES = [
    'epistemique', 'empirique', 'speculatif', 'structurel',
    'normatif', 'problematique', 'mode', 'objet',
]

# Noms lisibles des familles
# / Human-readable family names
NOMS_FAMILLES = {
    'epistemique': 'Epistémique',
    'empirique': 'Empirique',
    'speculatif': 'Spéculatif',
    'structurel': 'Structurel',
    'normatif': 'Normatif',
    'problematique': 'Problématique',
    'mode': 'Mode / Variation',
    'objet': 'Objet / Méthode',
}


def _normaliser_hypostase(valeur):
    """
    Normalise un nom d'hypostase : minuscule, sans accents.
    / Normalize a hypostase name: lowercase, no accents.
    """
    texte = str(valeur).strip().lower()
    texte_nfkd = unicodedata.normalize('NFKD', texte)
    return ''.join(c for c in texte_nfkd if not unicodedata.combining(c))


def _extraire_hypostases_de_entite(entite):
    """
    Extrait les hypostases d'une entite a partir de attr_0 (premier attribut).
    Retourne une liste de tuples (hypostase_normalisee, famille).
    / Extract hypostases from an entity via attr_0 (first attribute).
    / Returns a list of (normalized_hypostase, family) tuples.
    """
    resultats = []

    # Cherche la cle 'hypostase' dans attributes, fallback sur la premiere valeur
    # / Look for 'hypostase' key in attributes, fallback to first value
    attributs = entite.attributes or {}
    if not attributs:
        return resultats

    premiere_valeur = attributs.get('hypostase') or next(iter(attributs.values()), '')
    if not premiere_valeur:
        return resultats

    # Split par virgule si l'attribut contient plusieurs hypostases
    # / Split by comma if attribute contains multiple hypostases
    fragments = str(premiere_valeur).split(',')

    for fragment in fragments:
        hypostase_normalisee = _normaliser_hypostase(fragment)
        if not hypostase_normalisee:
            continue
        famille = HYPOSTASE_VERS_FAMILLE.get(hypostase_normalisee, 'objet')
        resultats.append((hypostase_normalisee, famille))

    return resultats


def _construire_donnees_alignement(pages_selectionnees):
    """
    Construit la structure de donnees pour le tableau d'alignement.
    / Build the data structure for the alignment table.

    Retourne :
        donnees_par_famille = { famille: { hypostase: { page_id: [entites] } } }
        toutes_hypostases   = set de toutes les hypostases trouvees
    / Returns:
        donnees_par_famille = { family: { hypostase: { page_id: [entities] } } }
        toutes_hypostases   = set of all found hypostases
    """
    # Recupere toutes les entites non masquees des pages selectionnees
    # / Retrieve all non-hidden entities from selected pages
    identifiants_pages = [page.id for page in pages_selectionnees]
    toutes_les_entites = ExtractedEntity.objects.filter(
        job__page__id__in=identifiants_pages,
        job__status="completed",
        masquee=False,
    ).select_related("job", "job__page")

    # Groupement par famille → hypostase → page_id → [entites]
    # / Grouping by family → hypostase → page_id → [entities]
    donnees_par_famille = {}
    toutes_hypostases = set()

    for entite in toutes_les_entites:
        liste_hypostases = _extraire_hypostases_de_entite(entite)
        identifiant_page = entite.job.page_id

        for hypostase_normalisee, famille in liste_hypostases:
            toutes_hypostases.add(hypostase_normalisee)

            if famille not in donnees_par_famille:
                donnees_par_famille[famille] = {}
            if hypostase_normalisee not in donnees_par_famille[famille]:
                donnees_par_famille[famille][hypostase_normalisee] = {}
            if identifiant_page not in donnees_par_famille[famille][hypostase_normalisee]:
                donnees_par_famille[famille][hypostase_normalisee][identifiant_page] = []

            donnees_par_famille[famille][hypostase_normalisee][identifiant_page].append(entite)

    return donnees_par_famille, toutes_hypostases


def _preparer_lignes_tableau(donnees_par_famille, pages_selectionnees):
    """
    Prepare les lignes du tableau pour le template.
    Retourne une liste de sections (famille + lignes hypostases).
    / Prepare table rows for the template.
    / Returns a list of sections (family + hypostase rows).
    """
    identifiants_pages = [page.id for page in pages_selectionnees]
    sections = []

    for famille in FAMILLES_ORDONNEES:
        hypostases_de_famille = donnees_par_famille.get(famille, {})
        if not hypostases_de_famille:
            continue

        lignes = []
        for hypostase in sorted(hypostases_de_famille.keys()):
            cellules_par_page = []
            for identifiant_page in identifiants_pages:
                entites_page = hypostases_de_famille[hypostase].get(identifiant_page, [])
                if entites_page:
                    # Prend le resume depuis la cle 'resume' ou 'résumé' de la premiere entite
                    # / Take summary from 'resume' or 'résumé' key of first entity
                    premiere_entite = entites_page[0]
                    attributs = premiere_entite.attributes or {}
                    resume = attributs.get('resume', '') or attributs.get('r\u00e9sum\u00e9', '')
                    resume_tronque = (str(resume)[:60] + '...') if len(str(resume)) > 60 else str(resume)

                    # Concatene les extraction_text de toutes les entites (texte source)
                    # / Concatenate extraction_text from all entities (source text)
                    textes_origine = [
                        entite.extraction_text
                        for entite in entites_page
                        if entite.extraction_text
                    ]
                    texte_origine_concat = ' \u2022 '.join(textes_origine)

                    cellules_par_page.append({
                        'remplie': True,
                        'count': len(entites_page),
                        'resume': resume_tronque,
                        'resume_complet': str(resume),
                        'texte_origine': texte_origine_concat,
                        'page_id': identifiant_page,
                        'entites': entites_page,
                    })
                else:
                    cellules_par_page.append({
                        'remplie': False,
                        'page_id': identifiant_page,
                    })

            lignes.append({
                'hypostase': hypostase,
                'cellules': cellules_par_page,
            })

        sections.append({
            'famille': famille,
            'nom_famille': NOMS_FAMILLES.get(famille, famille.capitalize()),
            'lignes': lignes,
        })

    return sections


class AlignementViewSet(viewsets.ViewSet):
    """
    Alignement cross-documents par hypostases (PHASE-18).
    / Cross-document alignment by hypostases (PHASE-18).
    """

    def _recuperer_pages_depuis_parametres(self, request):
        """
        Recupere les pages a comparer depuis page_ids ou dossier_id.
        Retourne (pages_selectionnees, avertissement, erreur_http).
        / Retrieve pages to compare from page_ids or dossier_id.
        / Returns (selected_pages, warning, http_error).
        """
        parametre_dossier = request.query_params.get("dossier_id", "")
        parametre_ids = request.query_params.get("page_ids", "")
        avertissement = None

        if parametre_dossier:
            # Mode dossier : recupere toutes les pages du dossier
            # / Folder mode: retrieve all pages from the folder
            try:
                identifiant_dossier = int(parametre_dossier.strip())
            except ValueError:
                return None, None, HttpResponse(
                    '<p class="text-red-600 text-sm p-4">Identifiant de dossier invalide.</p>',
                    status=400,
                )

            try:
                dossier = Dossier.objects.get(pk=identifiant_dossier)
            except Dossier.DoesNotExist:
                return None, None, HttpResponse(
                    '<p class="text-red-600 text-sm p-4">Dossier introuvable.</p>',
                    status=404,
                )

            toutes_les_pages_du_dossier = list(
                Page.objects.filter(dossier=dossier).order_by("id")
            )

            if len(toutes_les_pages_du_dossier) < 2:
                return None, None, HttpResponse(
                    '<p class="text-red-600 text-sm p-4">Ce dossier contient moins de 2 pages.</p>',
                    status=400,
                )

            # Limite a 6 pages max, avertit si tronque
            # / Limit to 6 pages max, warn if truncated
            if len(toutes_les_pages_du_dossier) > 6:
                avertissement = (
                    f"Le dossier contient {len(toutes_les_pages_du_dossier)} pages, "
                    "seules les 6 premières sont affichées."
                )
                toutes_les_pages_du_dossier = toutes_les_pages_du_dossier[:6]

            return toutes_les_pages_du_dossier, avertissement, None

        elif parametre_ids:
            # Mode page_ids classique
            # / Classic page_ids mode
            try:
                liste_ids = [
                    int(identifiant.strip())
                    for identifiant in parametre_ids.split(",")
                    if identifiant.strip()
                ]
            except ValueError:
                return None, None, HttpResponse(
                    '<p class="text-red-600 text-sm p-4">Identifiants de pages invalides.</p>',
                    status=400,
                )

            if len(liste_ids) < 2:
                return None, None, HttpResponse(
                    '<p class="text-red-600 text-sm p-4">Sélectionnez au moins 2 pages.</p>',
                    status=400,
                )
            if len(liste_ids) > 6:
                return None, None, HttpResponse(
                    '<p class="text-red-600 text-sm p-4">Maximum 6 pages pour la comparaison.</p>',
                    status=400,
                )

            pages_par_id = {
                page.id: page
                for page in Page.objects.filter(id__in=liste_ids)
            }
            pages_selectionnees = [
                pages_par_id[identifiant]
                for identifiant in liste_ids
                if identifiant in pages_par_id
            ]

            if len(pages_selectionnees) < 2:
                return None, None, HttpResponse(
                    '<p class="text-red-600 text-sm p-4">Certaines pages n\'existent pas ou plus.</p>',
                    status=400,
                )

            return pages_selectionnees, None, None

        else:
            return None, None, HttpResponse(
                '<p class="text-red-600 text-sm p-4">Aucune page sélectionnée.</p>',
                status=400,
            )

    @action(detail=False, methods=["get"], url_path="tableau")
    def tableau(self, request):
        """
        GET /alignement/tableau/?page_ids=1,2,3
        GET /alignement/tableau/?dossier_id=X
        Retourne le tableau HTML d'alignement croise.
        / Returns the cross-alignment HTML table.
        """
        # Recupere les pages depuis page_ids ou dossier_id
        # / Retrieve pages from page_ids or dossier_id
        pages_selectionnees, avertissement, erreur = self._recuperer_pages_depuis_parametres(request)
        if erreur:
            return erreur

        # Construit les donnees d'alignement
        # / Build alignment data
        donnees_par_famille, toutes_hypostases = _construire_donnees_alignement(pages_selectionnees)

        # Prepare les sections pour le template
        # / Prepare sections for the template
        sections_tableau = _preparer_lignes_tableau(donnees_par_famille, pages_selectionnees)

        contexte = {
            'pages_selectionnees': pages_selectionnees,
            'sections_tableau': sections_tableau,
            'nombre_hypostases': len(toutes_hypostases),
            'nombre_pages': len(pages_selectionnees),
            'avertissement': avertissement,
        }

        html_rendu = render_to_string(
            "front/includes/alignement_tableau.html",
            contexte,
            request=request,
        )
        return HttpResponse(html_rendu)

    @action(detail=False, methods=["get"], url_path="export_markdown")
    def export_markdown(self, request):
        """
        GET /alignement/export_markdown/?page_ids=1,2,3
        GET /alignement/export_markdown/?dossier_id=X
        Exporte le tableau d'alignement en Markdown telecharge.
        / Export the alignment table as downloadable Markdown.
        """
        # Recupere les pages depuis page_ids ou dossier_id
        # / Retrieve pages from page_ids or dossier_id
        pages_selectionnees, _avertissement, erreur = self._recuperer_pages_depuis_parametres(request)
        if erreur:
            return erreur

        donnees_par_famille, toutes_hypostases = _construire_donnees_alignement(pages_selectionnees)
        sections_tableau = _preparer_lignes_tableau(donnees_par_famille, pages_selectionnees)

        # Genere le Markdown
        # / Generate Markdown
        lignes_markdown = []
        lignes_markdown.append("# Alignement par hypostases")
        lignes_markdown.append("")

        # En-tete du tableau
        # / Table header
        titres_pages = [page.title or f"Page {page.id}" for page in pages_selectionnees]
        en_tete = "| Hypostase | " + " | ".join(titres_pages) + " |"
        separateur = "| --- | " + " | ".join(["---"] * len(pages_selectionnees)) + " |"
        lignes_markdown.append(en_tete)
        lignes_markdown.append(separateur)

        # Lignes du tableau par famille
        # / Table rows by family
        for section in sections_tableau:
            nom_famille = section['nom_famille']
            lignes_markdown.append(f"| **{nom_famille}** | " + " | ".join([""] * len(pages_selectionnees)) + " |")

            for ligne in section['lignes']:
                cellules_texte = []
                for cellule in ligne['cellules']:
                    if cellule['remplie']:
                        cellules_texte.append(f"{cellule['count']}x — {cellule['resume']}")
                    else:
                        cellules_texte.append("—")
                ligne_md = f"| {ligne['hypostase']} | " + " | ".join(cellules_texte) + " |"
                lignes_markdown.append(ligne_md)

        contenu_markdown = "\n".join(lignes_markdown)

        # Retourne en telechargement
        # / Return as download
        reponse = HttpResponse(contenu_markdown, content_type="text/markdown; charset=utf-8")
        reponse["Content-Disposition"] = 'attachment; filename="alignement-hypostases.md"'
        return reponse
