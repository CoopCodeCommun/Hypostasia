"""
Services de la couche synthese.
/ Synthesis layer services.

LOCALISATION : core/services/synthese.py

SPEC-synthese-carnet.md. Phase A : le perimetre source d'un carnet.
"""

from core.models import Page, TypeDeNote


def notes_sources_du_carnet(dossier):
    """
    Les notes d'un carnet qui peuvent servir de SOURCE a une synthese.
    / The notes of a notebook that can serve as sources.

    LOCALISATION : core/services/synthese.py

    SANS CETTE EXCLUSION, LE SYSTEME S'EFFONDRE SUR LUI-MEME. Une synthese
    est une note du carnet (§ 2). Si elle entrait dans le perimetre de la
    suivante, celle-ci citerait celle-la ; au troisieme tour, le wiki se
    citerait lui-meme et la deliberation d'origine disparaitrait sous ses
    propres resumes.

    L'exclusion est MECANIQUE — une clause de filtre, pas une convention
    d'interface. Une synthese qui se glisserait dans un perimetre ne se
    verrait pas. C'est aussi la discipline d'Atomic (leur wiki ne cite
    jamais son propre journal : filtre kind='captured' a la resolution du
    scope, pas seulement au comptage).
    / Mechanical exclusion: a filter clause, not a UI convention — same
    discipline as Atomic's kind='captured' scope filter.
    """
    return Page.objects.filter(
        appartenances_dossiers__dossier=dossier,
        type_de_note=TypeDeNote.NOTE,
        parent_page__isnull=True,
    ).distinct()


def notes_du_perimetre_d_un_wiki(wiki):
    """
    Les notes qu'un wiki retient, RECALCULEES a chaque appel.
    / The notes a wiki's scope retains, recomputed on every call.

    LOCALISATION : core/services/synthese.py

    SPEC-synthese § 3.1.1 : le perimetre d'un wiki est defini par ses
    categories, jamais par son sujet (le sujet n'oriente que la
    redaction). Sans categorie, le wiki prend TOUT le carnet — moins les
    syntheses et wikis, garde-fou § 3.3 via notes_sources_du_carnet().

    Les categories se lisent sur l'appartenance de la note A CE
    CARNET-LA : les categories d'un MEME axe se combinent en OU, les
    axes entre eux en ET (spec corpus § 8.2) — meme regle que le filtre
    de l'ecran carnet.
    / Categories are read on the note's membership in THIS notebook;
    OR within an axis, AND across axes, like the notebook screen filter.

    C'est LA difference avec la synthese dirigee : elle fige une liste
    de notes (notes_du_perimetre), lui recalcule — une note ajoutee au
    carnet et classee dans ces categories y entre au tour suivant.
    / THE difference with the frozen synthesis: recomputed, never stored.
    """
    from collections import defaultdict

    notes_retenues = notes_sources_du_carnet(wiki.dossier)

    # Regroupe les categories du perimetre par axe : OU dans un axe se
    # traduit en categories__in, ET entre axes en filtres successifs.
    # / Group scope categories by axis: OR -> __in, AND -> chained filters.
    categories_par_axe = defaultdict(list)
    for categorie in wiki.categories_du_perimetre.select_related("liste"):
        categories_par_axe[categorie.liste_id].append(categorie.pk)

    for identifiants_du_meme_axe in categories_par_axe.values():
        notes_retenues = notes_retenues.filter(
            appartenances_dossiers__dossier=wiki.dossier,
            appartenances_dossiers__categories__in=identifiants_du_meme_axe,
        )

    return notes_retenues.distinct()


# ---------------------------------------------------------------------------
# LE PERIMETRE D'EXTRACTIONS ET LES CALCULS PURS (SPEC-synthese § 8-9,
# phase D). Une seule definition de « citable » pour le prompt, le
# perimetre d'indexation ET les ecartees — deux definitions divergeraient.
# / The extraction scope and pure computations; ONE definition of
# "citable" shared by the prompt, the indexing scope and the left-outs.
# ---------------------------------------------------------------------------


def dernier_job_d_analyse_de_la_note(page):
    """
    Le dernier job d'ANALYSE termine d'une note — jamais un job de
    synthese. / The note's latest completed ANALYSIS job, never a
    synthesis job.

    LOCALISATION : core/services/synthese.py

    NOTE : __contains et non __est_synthese, car .exclude() sur un
    lookup JSONField standard exclut aussi les lignes ou la cle est
    absente (le lookup renvoie NULL, et NOT NULL = NULL est falsy).
    / __contains, because .exclude() on a plain JSONField lookup also
    drops rows lacking the key.
    """
    from hypostasis_extractor.models import ExtractionJob

    return ExtractionJob.objects.filter(
        page=page, status="completed",
    ).exclude(
        raw_result__contains={"est_synthese": True},
    ).order_by("-created_at", "-pk").first()


class PerimetreDExtractionsInconnu(Exception):
    """
    Levee quand on demande les ecartees d'une synthese HISTORIQUE
    (produite avant le figeage du perimetre, migration 0050) : aucun
    SourceLink n'existe pour elle, la difference d'ensembles dirait
    « 100 % ecarte » — un faux positif a charge contre l'acte. On
    refuse de repondre plutot que de mentir (relecture E, I2).
    / Raised for pre-phase-D syntheses: the set difference would claim
    "100% left out"; refuse to answer rather than lie.
    """


def _filtrer_les_citables(queryset_d_extractions):
    """
    LE filtre « citable », unique (relecture E, M6) : jobs termines,
    jamais un job de synthese, extraction non masquee.
    / THE single "citable" filter: completed non-synthesis jobs,
    unhidden extractions.

    LOCALISATION : core/services/synthese.py
    """
    return queryset_d_extractions.filter(
        job__status="completed", masquee=False,
    ).exclude(job__raw_result__contains={"est_synthese": True})


def extractions_citables_de_la_note(page):
    """
    TOUTES les extractions qu'une synthese a le droit de citer sur une
    note : celles de TOUS ses jobs termines (analyse, manuelles,
    selection), non masquees.
    / ALL the extractions a synthesis may cite on a note: every
    completed job's visible entities.

    LOCALISATION : core/services/synthese.py

    POURQUOI TOUS LES JOBS ET PAS « LE DERNIER » (relecture D, B1) :
    trois chemins creent des jobs completed sur une meme note (analyse,
    extractions manuelles, extraction sur selection). Prendre « le
    dernier » ferait qu'une seule extraction ajoutee a la main EVINCE
    les quarante de l'analyse — et l'ecran § 8 dirait « rien d'ecarte »
    sur un perimetre vide. C'est aussi la definition de l'ecran
    d'analyse (front/views.py, tous les jobs completed) : une seule
    notion de « les extractions d'une note ».
    / "Latest job" would let one manual extraction evict the whole
    analysis; the UI already aggregates every completed job.

    Le filtre d'antan sur statut_debat="non_pertinent" a disparu : la
    migration extractor 0029 a fusionne cette valeur dans masquee=True.
    / The old non_pertinent filter died with extractor migration 0029.
    """
    from hypostasis_extractor.models import ExtractedEntity

    return _filtrer_les_citables(
        ExtractedEntity.objects.filter(job__page=page)
    )


def extractions_du_perimetre(article):
    """
    Les extractions du perimetre d'un article — wiki ou synthese dirigee.
    / The extraction scope of an article (wiki or frozen synthesis).

    LOCALISATION : core/services/synthese.py

    § 8 : pour une DIRIGEE produite depuis la phase D, l'ensemble est
    FIGE deux fois — les notes (notes_du_perimetre) ET les extractions
    effectivement proposees au modele (extractions_du_perimetre,
    relecture D B2) : une re-analyse posterieure ne reecrit jamais
    « ce qui n'a pas ete repris ». Pour une dirigee HISTORIQUE (flag a
    False) et pour un WIKI, recalcul dynamique : les extractions
    citables des notes du perimetre — filtre § 3.3 mecanique inclus, le
    perimetre fige d'une dirigee peut contenir n'importe quelle Page
    (relecture D, I4).
    / Twice-frozen for post-phase-D syntheses; dynamic recomputation
    (with the mechanical § 3.3 filter) for wikis and historical ones.

    :raises ValueError: si la page n'est ni un wiki ni une dirigee
    """
    from hypostasis_extractor.models import ExtractedEntity

    from core.models import SyntheseDirigee, TypeDeNote, Wiki

    enregistrement_de_wiki = Wiki.objects.filter(page=article).first()
    if enregistrement_de_wiki is not None:
        notes_du_perimetre = notes_du_perimetre_d_un_wiki(
            enregistrement_de_wiki,
        )
    else:
        enregistrement_de_dirigee = SyntheseDirigee.objects.filter(
            page=article,
        ).first()
        if enregistrement_de_dirigee is None:
            raise ValueError(
                f"La page {article.pk} n'est ni un wiki ni une synthese "
                f"dirigee : elle n'a pas de perimetre d'extractions. "
                f"/ Neither a wiki nor a frozen synthesis: no scope."
            )
        if enregistrement_de_dirigee.perimetre_d_extractions_fige:
            # L'instantane de la production fait foi — meme vide
            # (analyseur sans extractions : rien propose, rien ecarte).
            # / The production snapshot rules — even when empty.
            return enregistrement_de_dirigee.extractions_du_perimetre.all()
        notes_du_perimetre = (
            enregistrement_de_dirigee.notes_du_perimetre.filter(
                type_de_note=TypeDeNote.NOTE,
            )
        )

    identifiants_des_notes = list(
        notes_du_perimetre.values_list("pk", flat=True)
    )
    return _filtrer_les_citables(
        ExtractedEntity.objects.filter(
            job__page_id__in=identifiants_des_notes,
        )
    )


def extractions_ecartees(article):
    """
    Ce qu'une synthese N'A PAS repris : difference d'ensembles.
    / What the synthesis left out: a set difference.

    LOCALISATION : core/services/synthese.py

    Une synthese dit ce qu'elle retient ; elle ne dit jamais ce qu'elle
    a laisse de cote. C'est pourtant calculable sans aucun appel au
    modele, et c'est ce qui rend une synthese CONTESTABLE — donc
    utilisable dans une gouvernance.

    JAMAIS UNE LISTE STOCKEE. Une liste ecrite a la main ne peut pas
    etre juste : dans la maquette, elle etait fausse sur trois articles
    sur quatre avant qu'on la calcule.
    / Never a stored list; always computed.

    LIMITE A DIRE A L'ECRAN (§ 8) : ceci n'audite que les CITATIONS.
    Une extraction lue par le modele et utilisee sans etre citee
    traverse la difference. Borne inferieure de controle, pas garantie.
    / Audits citations only — a lower bound, not a guarantee.

    :raises PerimetreDExtractionsInconnu: pour une dirigee HISTORIQUE
        (perimetre jamais fige) — sa difference serait un mensonge.
        / For historical syntheses the difference would be a lie.
    """
    from core.models import SourceLink, SyntheseDirigee, TypeLien

    dirigee = SyntheseDirigee.objects.filter(page=article).first()
    if dirigee is not None and not dirigee.perimetre_d_extractions_fige:
        raise PerimetreDExtractionsInconnu(
            f"La synthese {article.pk} date d'avant le figeage du "
            f"perimetre : ce qu'elle a vu n'est pas connu, la difference "
            f"d'ensembles dirait a tort « tout ecarte ». "
            f"/ Pre-freeze synthesis: scope unknown, refusing to answer."
        )

    perimetre = extractions_du_perimetre(article)
    identifiants_cites = SourceLink.objects.filter(
        page_cible=article, type_lien=TypeLien.CITE,
        extraction_source__isnull=False,
    ).values_list("extraction_source_id", flat=True)
    return perimetre.exclude(pk__in=identifiants_cites)


def couverture_de_la_note(page):
    """
    Quels elements portent au moins une extraction, et lesquels non.
    / Which elements carry at least one extraction.

    LOCALISATION : core/services/synthese.py

    § 9 : c'est une JOINTURE, pas une estimation — aucun appel au
    modele. « Non source » confond « le modele a invente » et « le
    passage n'a jamais ete extrait » ; la couverture separe les deux.
    / A join, not an estimate: separates "invented" from "never
    extracted".

    NE COMPTENT PAS comme couverture (relecture D, I6) : une extraction
    masquee, une ancre DETACHEE (elle ne pointe plus le passage), un
    job inacheve. Le chiffre annonce « l'analyse a lu ce passage » —
    il ne doit pas le survendre. Limite restante, a dire a l'ecran
    (phase H) : le total inclut les elements non textuels (titres,
    tableaux), qui ne porteront jamais d'extraction.
    / Hidden extractions, detached anchors and unfinished jobs do not
    count; the denominator still includes non-textual elements.
    """
    from hypostasis_extractor.models import EtatAncrage

    elements = page.elements.all()
    couverts = elements.filter(
        portions_d_extractions__extraction__masquee=False,
        portions_d_extractions__extraction__job__status="completed",
        portions_d_extractions__etat_ancrage=EtatAncrage.ANCREE,
    ).distinct()
    return {"total": elements.count(), "couverts": couverts.count()}


# ---------------------------------------------------------------------------
# LE LIEN DE CITATION (SPEC-synthese § 4, phase B)
# Le markdown est la verite ; les SourceLink en sont l'index, reconstruits
# a chaque enregistrement — deux verites divergent toujours.
# / THE CITATION LINK: markdown is the truth, links are its index.
# ---------------------------------------------------------------------------

import re

from django.db import transaction

MOTIF_DE_MARQUEUR = re.compile(r"\[\[ext:(\d+)\]\]")

# LE FORMAT GROUPE, QU'UN MODELE PRODUIT ALORS QU'ON NE LE DEMANDE PAS.
#
# Le prompt de redaction exige des marqueurs CONSECUTIFS et le dit avec
# un exemple : « Plusieurs sources = plusieurs marqueurs consecutifs
# (`[[ext:12]][[ext:15]]`) ». `mistral-small-latest` desobeit et ecrit
# `[[ext:14, ext:15, ext:16]]`.
#
# CE QUE CA COUTAIT, mesure le 18 aout 2026 sur deux articles reels :
# 107 citations perdues sur 142 produites — et le balisage BRUT restait
# a l'ecran, huit `[[ext:14, ext:15, …]]` en clair dans le HTML du wiki.
# Rien ne le signalait : l'indexeur denonce bruyamment un marqueur
# HALLUCINE, mais il etait AVEUGLE a celui-la.
# / A model disobeys the documented format; 107 of 142 citations were
#   silently lost, and raw markup reached the screen.
MOTIF_DE_MARQUEUR_GROUPE = re.compile(
    r"\[\[ext:\d+(?:\s*,\s*ext:\d+)+\]\]"
)


def normaliser_les_marqueurs_groupes(texte_markdown):
    """
    Recrit `[[ext:1, ext:2]]` en `[[ext:1]][[ext:2]]`.
    / Rewrites grouped markers into consecutive ones.

    LOCALISATION : core/services/synthese.py

    C'EST UN REPLI, PAS UNE BENEDICTION. Un modele qui desobeit au
    format reste un defaut de ce modele, et le nombre de groupes
    reecrits est RENDU pour que le bilan le compte : reparer en silence
    excuserait la desobeissance, et on ne saurait plus quel modele la
    commet. Mais perdre les trois quarts des preuves d'un article parce
    qu'une virgule remplace deux crochets n'est pas une sanction
    proportionnee.

    Le repli est place ICI, en amont de tout : l'indexation, le texte
    enregistre, la verification et l'affichage voient donc tous la meme
    forme canonique, et aucun d'eux n'a besoin de connaitre l'existence
    du format groupe. Une seconde tolerance ailleurs finirait par
    diverger de celle-ci.
    / A fallback, not a blessing: the count is returned so the model's
    disobedience stays visible. Placed upstream of everything, so every
    consumer sees one canonical form.

    :return: (texte normalise, nombre de groupes reecrits)
    """
    groupes_reecrits = 0

    def _eclater(correspondance):
        nonlocal groupes_reecrits
        groupes_reecrits += 1
        identifiants = re.findall(r"ext:(\d+)", correspondance.group(0))
        return "".join(f"[[ext:{identifiant}]]" for identifiant in identifiants)

    return MOTIF_DE_MARQUEUR_GROUPE.sub(_eclater, texte_markdown), groupes_reecrits

# Seuls les titres de niveau 2 delimitent les sections : c'est aussi le
# seul niveau que l'applieur (§ 6) sait resoudre, et le seul expose au
# modele (addendum n°3, regle d'Atomic). / Level-2 headings only.
MOTIF_DE_TITRE_DE_SECTION = re.compile(r"^## +(.+?)\s*$")


def titre_de_section(ligne):
    """
    LA reconnaissance d'une frontiere de section, partagee par
    l'indexeur ET l'applieur (§ 6) — deux definitions divergentes
    rangeraient un contenu dans la mauvaise section (relecture F, I2).
    Permissif sur l'indentation, comme le markdown.
    / THE single section-boundary test, shared by the indexer and the
    applier; indentation-tolerant like markdown.

    LOCALISATION : core/services/synthese.py

    :return: le titre, ou None si la ligne n'est pas une frontiere
    """
    correspondance = MOTIF_DE_TITRE_DE_SECTION.match(ligne.strip())
    return correspondance.group(1) if correspondance else None


class SuppressionRefuseeSourceCitee(Exception):
    """
    Levee quand on tente de supprimer une extraction citee par une
    synthese DIRIGEE : c'est un acte date, sa preuve ne peut pas
    s'evaporer (SPEC-synthese § 4.2).
    / Raised when deleting an extraction cited by a frozen synthesis.
    """

    def __init__(self, extraction, citations):
        self.extraction = extraction
        self.citations = citations
        super().__init__(
            f"L'extraction {extraction.pk} est citee par une synthese "
            f"dirigee : suppression refusee. Retirez d'abord la citation "
            f"ou produisez une nouvelle synthese. / Cited by a frozen "
            f"synthesis: deletion refused."
        )


def indexer_les_citations(article, texte_markdown,
                          identifiants_du_perimetre):
    """
    Cree un SourceLink par couple (paragraphe, extraction citee), en
    reconstruisant l'index complet de l'article.
    / One SourceLink per (paragraph, cited extraction) pair, rebuilding
    the article's whole index.

    LOCALISATION : core/services/synthese.py

    Un marqueur pointant une extraction INEXISTANTE ou HORS DU PERIMETRE
    est une hallucination : le lien n'est pas cree, le marqueur est
    retire du texte, et le fait est signale a l'appelant (jamais en
    silence). / Unknown or out-of-scope markers are stripped and loudly
    reported, never silently kept.

    :param article: la Page (wiki ou synthese) qui cite / the citing Page
    :param texte_markdown: le corps markdown de l'article / the body
    :param identifiants_du_perimetre: ensemble d'ids d'extractions
        admissibles — OBLIGATOIRE : tout appelant de production DOIT
        passer le perimetre reel (phase C), sinon un marqueur vers
        n'importe quelle extraction de la base passerait. None (explicite)
        n'exige que l'existence — reserve aux outils et aux tests.
        / admissible extraction ids — MANDATORY; production callers must
        pass the real scope. Explicit None (tools/tests only) checks
        existence only.
    :return: {"texte_nettoye", "liens_crees", "marqueurs_retires"}
    """
    from hypostasis_extractor.models import ExtractedEntity

    from core.models import EtatDeLaSource, SourceLink, TypeLien

    # Normalisation des fins de ligne : un textarea navigateur envoie du
    # \r\n, qui casserait le decoupage en paragraphes et toutes les
    # bornes (relecture B, N1). / CRLF would break paragraph splitting.
    texte_markdown = texte_markdown.replace("\r\n", "\n").replace("\r", "\n")

    # LE REPLI SUR LE FORMAT GROUPE, en amont de tout le reste : ce qui
    # suit — indexation, texte enregistre, verification, affichage — ne
    # voit qu'une seule forme de marqueur.
    # / The grouped-marker fallback, upstream of everything else.
    texte_markdown, marqueurs_groupes_normalises = (
        normaliser_les_marqueurs_groupes(texte_markdown)
    )

    identifiants_cites = [
        int(correspondance.group(1))
        for correspondance in MOTIF_DE_MARQUEUR.finditer(texte_markdown)
    ]
    identifiants_existants = set(
        ExtractedEntity.objects.filter(pk__in=identifiants_cites)
        .values_list("pk", flat=True)
    )
    if identifiants_du_perimetre is None:
        identifiants_admissibles = identifiants_existants
    else:
        identifiants_admissibles = identifiants_existants & set(
            identifiants_du_perimetre
        )

    # Retire les marqueurs inadmissibles du texte, en gardant la trace.
    # / Strip inadmissible markers, keeping track.
    marqueurs_retires = []

    def _garder_ou_retirer(correspondance):
        identifiant = int(correspondance.group(1))
        if identifiant in identifiants_admissibles:
            return correspondance.group(0)
        if identifiant not in marqueurs_retires:
            marqueurs_retires.append(identifiant)
        return ""

    texte_nettoye = MOTIF_DE_MARQUEUR.sub(_garder_ou_retirer, texte_markdown)

    # Un marqueur DANS un titre de section est une hallucination de
    # placement : un titre n'affirme rien. Retire ET signale — et le nom
    # de section reste propre pour l'applieur (relecture B, N4).
    # / A marker inside a heading is stripped AND reported.
    lignes = texte_nettoye.split("\n")
    for indice, ligne in enumerate(lignes):
        if titre_de_section(ligne) is not None and MOTIF_DE_MARQUEUR.search(ligne):
            for correspondance in MOTIF_DE_MARQUEUR.finditer(ligne):
                identifiant = int(correspondance.group(1))
                if identifiant not in marqueurs_retires:
                    marqueurs_retires.append(identifiant)
            lignes[indice] = MOTIF_DE_MARQUEUR.sub("", ligne)
    texte_nettoye = "\n".join(lignes)

    # Les doublons d'un meme marqueur dans un meme paragraphe sortent
    # DU TEXTE aussi (recette connectee du 10 aout, defaut B1) :
    # l'index les absorbait deja (un lien par couple paragraphe x
    # extraction, § 4.4) mais le texte gardait toutes les occurrences —
    # l'en-tete annoncait 23 renvois quand le corps en montrait 25.
    # Retirer le doublon ici fait coincider TOUS les compteurs.
    # / Same-paragraph duplicate markers leave the text too, so every
    # counter on screen agrees with the index.
    doublons_absorbes = 0
    morceaux_sans_doublons = []
    for morceau in texte_nettoye.split("\n\n"):
        identifiants_deja_vus = set()
        morceau_nettoye = []
        derniere_fin = 0
        for correspondance in MOTIF_DE_MARQUEUR.finditer(morceau):
            identifiant = int(correspondance.group(1))
            morceau_nettoye.append(morceau[derniere_fin:correspondance.start()])
            if identifiant in identifiants_deja_vus:
                doublons_absorbes += 1
            else:
                identifiants_deja_vus.add(identifiant)
                morceau_nettoye.append(correspondance.group(0))
            derniere_fin = correspondance.end()
        morceau_nettoye.append(morceau[derniere_fin:])
        morceaux_sans_doublons.append("".join(morceau_nettoye))
    texte_nettoye = "\n\n".join(morceaux_sans_doublons)

    # Precharge la premiere portion de chaque extraction admissible :
    # ancrage_source pointe le passage exact (§ 4.5).
    # / Preload each extraction's first portion for ancrage_source.
    extractions_par_id = {
        extraction.pk: extraction
        for extraction in ExtractedEntity.objects.filter(
            pk__in=identifiants_admissibles
        ).select_related("job__page").prefetch_related("ancrages")
    }

    liens_a_creer = []
    section_courante = ""
    ordre_dans_la_section = 0
    position = 0

    from hypostasis_extractor.models import EtatAncrage

    # Parcours des paragraphes AVEC leurs bornes dans le texte nettoye —
    # c'est ce texte qui sera stocke, donc les bornes s'y rapportent.
    # Un titre COLLE a son paragraphe (« ## Titre\nPhrase », courant chez
    # les LLM — relecture B, N2) est reconnu : la premiere ligne fait
    # frontiere de section, le reste est le paragraphe.
    # / Iterate paragraphs WITH their bounds; a heading glued to its
    # paragraph is recognized.
    for morceau in texte_nettoye.split("\n\n"):
        debut_du_paragraphe = position
        fin_du_paragraphe = position + len(morceau)
        position = fin_du_paragraphe + 2  # le separateur \n\n

        premiere_ligne, _saut, reste_du_morceau = morceau.partition("\n")
        titre_reconnu = titre_de_section(premiere_ligne)
        contenu_du_paragraphe = morceau
        if titre_reconnu is not None:
            # Tronque a la taille du champ SourceLink.section : un titre
            # verbeux ne doit pas faire echouer le bulk_create — et
            # perdre la synthese entiere (relecture C, I5). L'applieur
            # § 6 devra tronquer pareil pour retrouver la section.
            # / Truncated to the field size; a verbose heading must not
            # destroy the whole synthesis.
            section_courante = titre_reconnu[:200]
            ordre_dans_la_section = 0
            if not reste_du_morceau.strip():
                continue
            contenu_du_paragraphe = reste_du_morceau
            debut_du_paragraphe += len(premiere_ligne) + 1

        # Un lien par couple (paragraphe, extraction) : les doublons de
        # marqueur dans un meme paragraphe sont absorbes (§ 4.4,
        # relecture B N3). / One link per (paragraph, extraction) pair.
        identifiants_vus_dans_le_paragraphe = set()
        for correspondance in MOTIF_DE_MARQUEUR.finditer(contenu_du_paragraphe):
            identifiant = int(correspondance.group(1))
            if identifiant in identifiants_vus_dans_le_paragraphe:
                continue
            identifiants_vus_dans_le_paragraphe.add(identifiant)

            extraction = extractions_par_id[identifiant]
            premiere_portion = min(
                extraction.ancrages.all(),
                key=lambda portion: portion.ordre_dans_extraction,
                default=None,
            )
            # La reindexation ne blanchit pas une derive existante : une
            # ancre deja detachee donne un lien DETACHEE (relecture B, N5).
            # / Reindexing must not launder an existing drift.
            ancre_deja_detachee = (
                premiere_portion is not None
                and premiere_portion.etat_ancrage == EtatAncrage.DETACHEE
            )
            liens_a_creer.append(SourceLink(
                page_cible=article,
                start_char_cible=debut_du_paragraphe,
                end_char_cible=fin_du_paragraphe,
                extraction_source=extraction,
                ancrage_source=premiere_portion,
                page_source=extraction.job.page,
                type_lien=TypeLien.CITE,
                section=section_courante,
                ordre_dans_la_section=ordre_dans_la_section,
                etat_de_la_source=(
                    EtatDeLaSource.DETACHEE if ancre_deja_detachee
                    else EtatDeLaSource.PRESENTE
                ),
            ))
            ordre_dans_la_section += 1

    # LA RECONCILIATION DES VERDICTS (relecture G, B1) : reconstruire
    # l'index ne doit pas detruire les verdicts § 7 — surtout pas un
    # CONTESTE humain. Un verdict est reporte quand la PAIRE est
    # inchangee : meme extraction, meme paragraphe citant (au mot pres).
    # Une contestation dont la paire a disparu est SIGNALEE, jamais
    # perdue en silence.
    # / Verdict reconciliation: rebuilding the index must not destroy
    # § 7 verdicts — least of all a human CONTESTE. Reported when the
    # pair vanished.
    from core.models import EtatDeVerification

    texte_precedent = article.text_readability or ""

    def _cle_de_paire(identifiant_d_extraction, paragraphe):
        return (identifiant_d_extraction, " ".join(paragraphe.split()))

    anciens_verdicts = {}
    contestations_perdues = []
    anciens_liens = SourceLink.objects.filter(
        page_cible=article, type_lien=TypeLien.CITE,
    ).exclude(etat_de_verification=EtatDeVerification.NON_VERIFIE)
    for ancien_lien in anciens_liens.prefetch_related("commentaires_source"):
        cle = _cle_de_paire(
            ancien_lien.extraction_source_id,
            texte_precedent[
                ancien_lien.start_char_cible:ancien_lien.end_char_cible
            ],
        )
        anciens_verdicts[cle] = {
            "etat": ancien_lien.etat_de_verification,
            "verifie_par": ancien_lien.verifie_par,
            "verifie_le": ancien_lien.verifie_le,
            # LE DEGRE ET SA PROVENANCE VOYAGENT AVEC LE VERDICT, et les
            # oublier ici serait une perte silencieuse : le nouveau lien
            # garderait « verifie » avec un score NULL, donc sortirait
            # DEFINITIVEMENT du recalcul au changement de seuil. Un
            # article vivant — un wiki, mis a jour a chaque tour — y
            # perdrait sa sensibilite au seuil des la premiere mise a
            # jour, sans que rien ne le signale.
            # / The degree travels with the verdict: dropping it here
            # would silently freeze the link out of every future
            # threshold change.
            "score": ancien_lien.score_de_verification,
            "provenance_du_verbatim": ancien_lien.provenance_du_verbatim,
            # LE SECOND AVIS VOYAGE AVEC, et c'est la raison pour
            # laquelle il vit dans des COLONNES et non dans une table
            # liee : une cle etrangere en CASCADE aurait perdu tous les
            # avis a chaque tour de wiki, c'est-a-dire exactement les
            # donnees que la campagne de comparaison accumule.
            # / The second opinion rides along: that is why it lives in
            # columns and not in a linked table.
            "score_du_second_avis": ancien_lien.score_du_second_avis,
            "methode_du_second_avis": ancien_lien.methode_du_second_avis,
            "seuil_du_second_avis": ancien_lien.seuil_du_second_avis,
            "second_avis_rendu_le": ancien_lien.second_avis_rendu_le,
            "commentaires": list(ancien_lien.commentaires_source.all()),
        }

    with transaction.atomic():
        SourceLink.objects.filter(
            page_cible=article, type_lien=TypeLien.CITE,
        ).delete()
        nouveaux_liens = SourceLink.objects.bulk_create(liens_a_creer)

        verdicts_reportes = 0
        for nouveau_lien in nouveaux_liens:
            cle = _cle_de_paire(
                nouveau_lien.extraction_source_id,
                texte_nettoye[
                    nouveau_lien.start_char_cible:nouveau_lien.end_char_cible
                ],
            )
            ancien_verdict = anciens_verdicts.pop(cle, None)
            if ancien_verdict is None:
                continue
            nouveau_lien.etat_de_verification = ancien_verdict["etat"]
            nouveau_lien.verifie_par = ancien_verdict["verifie_par"]
            nouveau_lien.verifie_le = ancien_verdict["verifie_le"]
            nouveau_lien.score_de_verification = ancien_verdict["score"]
            nouveau_lien.provenance_du_verbatim = ancien_verdict[
                "provenance_du_verbatim"
            ]
            nouveau_lien.score_du_second_avis = ancien_verdict[
                "score_du_second_avis"
            ]
            nouveau_lien.methode_du_second_avis = ancien_verdict[
                "methode_du_second_avis"
            ]
            nouveau_lien.seuil_du_second_avis = ancien_verdict[
                "seuil_du_second_avis"
            ]
            nouveau_lien.second_avis_rendu_le = ancien_verdict[
                "second_avis_rendu_le"
            ]
            nouveau_lien.save(update_fields=[
                "etat_de_verification", "verifie_par", "verifie_le",
                "score_de_verification", "provenance_du_verbatim",
                "score_du_second_avis", "methode_du_second_avis",
                "seuil_du_second_avis", "second_avis_rendu_le",
            ])
            if ancien_verdict["commentaires"]:
                nouveau_lien.commentaires_source.set(
                    ancien_verdict["commentaires"],
                )
            verdicts_reportes += 1

        # Les contestations humaines restantes n'ont pas retrouve leur
        # paire : la paire a change ou disparu. SIGNALE a l'appelant.
        # / Leftover human contestations are loudly reported.
        for (identifiant, _paragraphe), verdict in anciens_verdicts.items():
            if verdict["etat"] == EtatDeVerification.CONTESTE:
                contestations_perdues.append(identifiant)

    return {
        "texte_nettoye": texte_nettoye,
        "liens_crees": len(liens_a_creer),
        "marqueurs_retires": marqueurs_retires,
        # Combien de marqueurs GROUPES ont du etre reecrits. Compte, et
        # non tu : un modele qui desobeit au format doit rester visible,
        # sinon le repli devient une excuse et on ne sait plus lequel le
        # fait. / Counted, not swallowed: the disobedience stays visible.
        "marqueurs_groupes_normalises": marqueurs_groupes_normalises,
        "doublons_absorbes": doublons_absorbes,
        "verdicts_reportes": verdicts_reportes,
        "contestations_perdues": contestations_perdues,
    }


def detacher_les_citations_des_portions(identifiants_de_portions):
    """
    Bascule en DETACHEE les citations dont l'ancre vient d'etre detachee.
    Appele par la reconciliation, le masquage et la reingestion — TOUS
    les chemins de detachement, pas seulement le premier (relecture B, N6).
    / Detaches citations whose anchor was just detached; called from ALL
    detachment paths.

    LOCALISATION : core/services/synthese.py
    """
    if not identifiants_de_portions:
        return 0
    from core.models import EtatDeLaSource, SourceLink, TypeLien

    return SourceLink.objects.filter(
        ancrage_source_id__in=list(identifiants_de_portions),
        type_lien=TypeLien.CITE,
    ).update(etat_de_la_source=EtatDeLaSource.DETACHEE)


def verifier_qu_aucune_dirigee_ne_cite_les_extractions(queryset_d_extractions):
    """
    La garde a appeler AVANT toute purge d'extractions (§ 4.2) : si une
    synthese DIRIGEE cite l'une d'elles, on refuse AVANT de commencer —
    un refus propre en amont vaut mieux qu'un signal qui explose au
    milieu d'une purge (relecture B, B2/N7).
    / The guard to call BEFORE any extraction purge: a clean upfront
    refusal beats a signal blowing up mid-purge.

    LOCALISATION : core/services/synthese.py

    :raises SuppressionRefuseeSourceCitee: si une dirigee cite
    """
    from core.models import SourceLink, TypeDeNote, TypeLien

    citations_de_dirigees = SourceLink.objects.filter(
        extraction_source__in=queryset_d_extractions,
        type_lien=TypeLien.CITE,
        page_cible__type_de_note=TypeDeNote.SYNTHESE,
    ).select_related("page_cible")
    premiere = citations_de_dirigees.first()
    if premiere is not None:
        raise SuppressionRefuseeSourceCitee(
            premiere.extraction_source, list(citations_de_dirigees[:5])
        )
