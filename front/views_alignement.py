"""
ViewSet d'alignement cross-documents par hypostases (PHASE-18).
/ Cross-document alignment ViewSet by hypostases (PHASE-18).

LOCALISATION : front/views_alignement.py

Compare 2 a 6 documents : tableau croise hypostases (lignes) x documents (colonnes).
Revele les gaps argumentatifs entre les textes.
"""
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import viewsets
from rest_framework.decorators import action

from core.models import Dossier, Page
from front.normalisation import _normaliser_texte
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


def _extraire_hypostases_de_entite(entite):
    """
    Extrait les hypostases d'une entite a partir de attr_0 (premier attribut).
    Retourne une liste de tuples (hypostase_normalisee, famille).
    / Extract hypostases from an entity via attr_0 (first attribute).
    / Returns a list of (normalized_hypostase, family) tuples.
    """
    resultats = []

    attributs = entite.attributes or {}
    if not attributs:
        return resultats

    # Lecture directe de la cle canonique (normalisee au stockage par front.normalisation)
    # / Direct read of canonical key (normalized at storage by front.normalisation)
    premiere_valeur = attributs.get('hypostases', '')

    # Fallback de compatibilite pour les entites non migrees
    # / Compatibility fallback for non-migrated entities
    if not premiere_valeur:
        for cle_attribut, valeur_attribut in attributs.items():
            if 'hypostas' in cle_attribut.lower():
                premiere_valeur = valeur_attribut
                break

    if not premiere_valeur:
        return resultats

    # Split par virgule si l'attribut contient plusieurs hypostases
    # / Split by comma if attribute contains multiple hypostases
    fragments = str(premiere_valeur).split(',')

    for fragment in fragments:
        hypostase_normalisee = _normaliser_texte(fragment)
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
                    # Concatene les resumes IA de toutes les entites (point median)
                    # / Concatenate AI summaries from all entities (bullet separator)
                    resumes_ia = [
                        str(entite.attributes.get('resume', ''))
                        for entite in entites_page
                        if entite.attributes and entite.attributes.get('resume')
                    ]
                    resume_concat = ' \u2022 '.join(resumes_ia)
                    resume_tronque = (resume_concat[:80] + '...') if len(resume_concat) > 80 else resume_concat

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
                        'resume_complet': resume_concat,
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


def construire_alignement_versions(page_gauche, page_droite):
    """
    Construit le contexte d'alignement des hypostases entre 2 versions d'un meme texte.
    Reutilise les helpers existants et enrichit chaque ligne avec un delta (ajoute/supprime/conserve).
    / Build the hypostase alignment context between 2 versions of the same text.
    / Reuses existing helpers and enriches each row with a delta (added/removed/kept).
    """
    pages_selectionnees = [page_gauche, page_droite]

    # Construit les donnees d'alignement via les helpers existants
    # / Build alignment data via existing helpers
    donnees_par_famille, toutes_hypostases = _construire_donnees_alignement(pages_selectionnees)
    sections_tableau = _preparer_lignes_tableau(donnees_par_famille, pages_selectionnees)

    # Enrichit chaque ligne avec un delta : ajoute, supprime, conserve
    # / Enrich each row with a delta: added, removed, kept
    for section in sections_tableau:
        for ligne in section['lignes']:
            cellule_v1 = ligne['cellules'][0]
            cellule_v2 = ligne['cellules'][1]

            if cellule_v1['remplie'] and not cellule_v2['remplie']:
                ligne['delta_type'] = 'supprime'
                ligne['delta_statut'] = None
            elif not cellule_v1['remplie'] and cellule_v2['remplie']:
                ligne['delta_type'] = 'ajoute'
                ligne['delta_statut'] = None
            else:
                ligne['delta_type'] = 'conserve'

                # Compare le statut_debat dominant entre V1 et V2
                # / Compare the dominant statut_debat between V1 and V2
                statut_v1 = _statut_dominant(cellule_v1.get('entites', []))
                statut_v2 = _statut_dominant(cellule_v2.get('entites', []))
                if statut_v1 != statut_v2 and statut_v1 and statut_v2:
                    ligne['delta_statut'] = {'de': statut_v1, 'vers': statut_v2}
                else:
                    ligne['delta_statut'] = None

    return {
        'pages_selectionnees': pages_selectionnees,
        'page_gauche': page_gauche,
        'page_droite': page_droite,
        'sections_tableau': sections_tableau,
        'nombre_hypostases': len(toutes_hypostases),
    }


def _statut_dominant(entites):
    """
    Retourne le statut_debat le plus frequent parmi une liste d'entites.
    / Returns the most frequent statut_debat among a list of entities.
    """
    if not entites:
        return None
    compteur_statuts = {}
    for entite in entites:
        statut = getattr(entite, 'statut_debat', 'nouveau')
        compteur_statuts[statut] = compteur_statuts.get(statut, 0) + 1
    # Retourne le statut avec le plus de votes
    # / Return the status with the most votes
    return max(compteur_statuts, key=compteur_statuts.get)


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
