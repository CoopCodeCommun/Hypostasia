"""
L'applieur d'operations de section (SPEC-synthese § 6, phase F).
/ The section-operations applier (phase F).

LOCALISATION : core/services/section_ops.py

Le modele ne reecrit JAMAIS l'article : il propose des operations
(no_change, append_to_section, replace_section, insert_section) qu'un
applieur fusionne, et qu'un humain accepte. C'est ce qui permet de voir
ce qui a change.

LES REGLES, ET D'OU ELLES VIENNENT :

- Un titre de section introuvable est une HALLUCINATION du modele, pas
  une approximation de placement : operation REJETEE VISIBLEMENT, son
  contenu CONSERVE et montre (§ 6.2 — corrige INSPIRATION_ATOMIC § 7,
  qui jetait le contenu en silence ou l'inserait en fin d'article).
- Le rejet est PAR OPERATION (addendum n°4) : le wiki n'a pas de point
  de reprise, rien n'est perdu par une application partielle, et c'est
  un humain qui accepte operation par operation. Une operation
  MALFORMEE (mauvais types JSON) est rejetee pareil, jamais une
  exception qui detruirait le lot (relecture F, I4).
- Seuls les titres de niveau 2 (##) font frontiere (addendum n°3), et
  SEULE insert_section cree une section : un contenu qui contient une
  ligne-titre fabriquerait une section que l'humain n'a pas approuvee
  (relecture F, B1) — rejet.
- Une operation de contenu sans source, ou citant hors du perimetre,
  est rejetee — controles DETERMINISTES, aucun appel au modele (§ 6.3).
  Les sources sont DERIVEES des marqueurs [[ext:N]] du contenu : le
  markdown est la verite (§ 4.4), pas un champ parallele.
- Les titres se comparent TRONQUES a 200 caracteres — la taille de
  SourceLink.section, la forme sous laquelle un prompt peut les avoir
  vus (relecture F, I3).
- UNE operation de contenu par section et par lot (relecture F, M5) :
  sinon le « avant » du diff § 6.4 ne serait pas l'avant de l'article.
- La proposition porte l'updated_at de l'article au moment de sa
  production ; s'il a bouge, l'application est refusee visiblement
  (« proposition perimee »), jamais ecrasee (addendum n°1, regle
  d'Atomic reprise telle quelle).

SCHEMA DES OPERATIONS (contractualise — addendum n°15) : des dicts
{"type", "section" | "titre"+"apres", "contenu"}, types en snake_case
francais. C'est la traduction assumee du schema d'INSPIRATION_ATOMIC
(op/heading/after_heading/content).
/ Visible per-operation rejection with preserved content, ## boundaries
only, marker-derived sources, 200-char title keys, optimistic
concurrency, French snake_case operation schema.
"""

import datetime

from core.services.synthese import MOTIF_DE_MARQUEUR, titre_de_section


class PropositionPerimee(Exception):
    """
    Levee quand l'article a change entre la previsualisation et
    l'application : la proposition ne decrit plus l'article reel.
    / Raised when the article moved between preview and apply.

    LOCALISATION : core/services/section_ops.py
    """

    def __init__(self, article):
        self.article = article
        super().__init__(
            "L'article a été modifié depuis que cette proposition a été "
            "produite : elle est périmée. Relancez la mise à jour pour "
            "obtenir une proposition sur la version actuelle. "
            "/ The article changed since this proposal was produced; "
            "re-run the update."
        )


def verifier_que_la_proposition_est_fraiche(article, updated_at_de_la_proposition):
    """
    Controle optimiste de concurrence (addendum n°1) : la proposition
    porte l'updated_at de l'article au moment de sa production.
    / Optimistic concurrency check.

    LOCALISATION : core/services/section_ops.py

    NOTE D'INTEGRATION (phase H) : refaire ce controle DANS la
    transaction d'ecriture, sur une instance relue sous
    select_for_update — sinon il reste une fenetre entre le controle et
    le save(). Et serialiser l'horodatage avec .isoformat(), jamais un
    filtre de gabarit localise. / Re-check inside the write transaction
    on a locked re-read; serialize with .isoformat().

    :param article: la Page de l'article (wiki)
    :param updated_at_de_la_proposition: datetime OU chaine ISO — la
        valeur transite par un formulaire HTMX et revient en texte.
        / datetime or ISO string (HTMX round-trip).
    :raises PropositionPerimee: si l'article a bouge / if it moved
    """
    horodatage = updated_at_de_la_proposition
    if isinstance(horodatage, str):
        try:
            horodatage = datetime.datetime.fromisoformat(horodatage)
        except ValueError:
            # Un horodatage illisible ne prouve pas la fraicheur : la
            # proposition est traitee comme perimee, jamais appliquee
            # a l'aveugle. / Unreadable timestamp = stale, never blind.
            raise PropositionPerimee(article)
    if article.updated_at != horodatage:
        raise PropositionPerimee(article)


def _cle_de_titre(titre):
    """
    La forme sous laquelle deux titres se comparent : nettoyee et
    tronquee a 200 — la taille de SourceLink.section, que le prompt a
    pu montrer au modele (relecture F, I3).
    / Titles compare stripped and truncated at 200 chars.
    """
    return (titre or "").strip()[:200]


def _decouper_en_sections(texte_markdown):
    """
    Decoupe l'article en (preambule, sections) sur les titres ## —
    reconnaissance PARTAGEE avec l'indexeur (titre_de_section).
    / Splits into (preamble, sections) with the shared boundary test.

    LOCALISATION : core/services/section_ops.py

    Chaque section garde ses lignes TELLES QUELLES : la reconstruction
    d'une section non touchee est l'identite — l'applieur ne reformate
    jamais ce qu'il ne modifie pas.
    / Untouched sections round-trip byte-for-byte.
    """
    lignes_de_preambule = []
    sections = []
    section_courante = None
    for ligne in texte_markdown.split("\n"):
        titre = titre_de_section(ligne)
        if titre is not None:
            section_courante = {
                "titre": titre,
                "ligne_de_titre": ligne,
                "lignes": [],
            }
            sections.append(section_courante)
        elif section_courante is None:
            lignes_de_preambule.append(ligne)
        else:
            section_courante["lignes"].append(ligne)
    return lignes_de_preambule, sections


def _reconstruire(lignes_de_preambule, sections):
    """Recolle preambule et sections. / Glue preamble and sections back."""
    morceaux = list(lignes_de_preambule)
    for section in sections:
        morceaux.append(section["ligne_de_titre"])
        morceaux.extend(section["lignes"])
    return "\n".join(morceaux)


def _corps_normalise(contenu):
    """
    Le corps d'une section a inserer : encadre de lignes vides pour que
    les paragraphes restent des paragraphes markdown.
    / Section body wrapped in blank lines to keep paragraphs intact.
    """
    return ["", contenu.strip(), ""]


def _trouver_la_section(sections, titre_cherche):
    """
    L'indice de la section visee, ou un motif de rejet.
    / The target section index, or a rejection reason.

    :return: (indice, None) ou (None, motif)
    """
    cle_cherchee = _cle_de_titre(titre_cherche)
    indices_correspondants = [
        indice for indice, section in enumerate(sections)
        if _cle_de_titre(section["titre"]) == cle_cherchee
    ]
    if not indices_correspondants:
        return None, (
            f"La section « {titre_cherche} » n'existe pas dans "
            f"l'article : l'opération est rejetée et son contenu est "
            f"conservé pour relecture. / Heading not found: rejected, "
            f"content preserved."
        )
    if len(indices_correspondants) > 1:
        return None, (
            f"Le titre « {titre_cherche} » apparaît "
            f"{len(indices_correspondants)} fois dans l'article : la "
            f"cible est ambiguë, l'opération est rejetée. "
            f"/ Ambiguous duplicate heading: rejected."
        )
    return indices_correspondants[0], None


CHAMPS_TEXTE_D_UNE_OPERATION = ("type", "section", "titre", "apres", "contenu")


def _motif_de_malformation(operation):
    """
    Garde de forme (relecture F, I4) : l'entree est du JSON produit par
    un LLM — une operation mal typee est rejetee AVEC MOTIF, jamais une
    exception qui emporterait les operations valides du lot.
    / Shape guard: malformed JSON is rejected per-operation, never a
    lot-destroying exception.

    :return: None si la forme est bonne, sinon le motif / reason
    """
    if not isinstance(operation, dict):
        return (
            "L'opération n'est pas un objet : elle est rejetée telle "
            "quelle. / Not an object: rejected."
        )
    for champ in CHAMPS_TEXTE_D_UNE_OPERATION:
        if champ in operation and not isinstance(operation[champ], str):
            return (
                f"Le champ « {champ} » n'est pas du texte : opération "
                f"malformée, rejetée. / Field is not text: rejected."
            )
    return None


def _controler_les_sources(operation, identifiants_du_perimetre):
    """
    Les deux controles § 6.3, deterministes. Sources = les marqueurs
    [[ext:N]] du contenu. / The two deterministic § 6.3 checks.

    :return: None si valide, sinon le motif de rejet / rejection reason
    """
    identifiants_cites = [
        int(correspondance.group(1))
        for correspondance in MOTIF_DE_MARQUEUR.finditer(
            operation.get("contenu", "")
        )
    ]
    if not identifiants_cites:
        return (
            "L'opération n'a aucune source : une affirmation sans "
            "preuve n'a rien à faire dans un article sourcé (§ 6.3). "
            "/ No source markers: rejected."
        )
    identifiants_hors_perimetre = sorted(
        set(identifiants_cites) - set(identifiants_du_perimetre)
    )
    if identifiants_hors_perimetre:
        return (
            f"L'opération cite hors du périmètre : "
            f"{identifiants_hors_perimetre} — le modèle a cité quelque "
            f"chose qu'on ne lui a pas donné (§ 6.3). "
            f"/ Out-of-scope sources: rejected."
        )
    # Le contenu, marqueurs retires, doit rester un texte : un marqueur
    # NU produirait un paragraphe orphelin fait d'un seul renvoi [4]
    # (recette connectee du 10 aout, defaut B2 — le modele a compris
    # « ajoute une source » au lieu de « ajoute un passage source »).
    # / Content stripped of markers must still be prose: a bare marker
    # would render as an orphan single-reference paragraph.
    contenu_sans_marqueurs = MOTIF_DE_MARQUEUR.sub(
        "", operation.get("contenu", ""),
    )
    if not contenu_sans_marqueurs.strip():
        return (
            "L'opération n'apporte que des marqueurs, sans texte "
            "rédigé : appliquée, elle produirait un paragraphe vide "
            "avec un simple renvoi. Le modèle doit proposer un passage "
            "rédigé ET sourcé. / Bare markers with no prose: rejected."
        )
    return None


def _contenu_fabrique_une_section(contenu):
    """
    Vrai si le contenu contient une ligne-titre ## : il fabriquerait
    une section que l'humain n'a pas approuvee — et un titre duplique
    rendrait la section ambigue POUR TOUJOURS (relecture F, B1).
    / True when the content smuggles a section boundary in.
    """
    return any(
        titre_de_section(ligne) is not None
        for ligne in contenu.split("\n")
    )


def appliquer_les_operations(texte_markdown, operations,
                             identifiants_du_perimetre):
    """
    Applique les operations acceptables, rejette les autres VISIBLEMENT.
    / Applies acceptable operations, rejects the rest visibly.

    LOCALISATION : core/services/section_ops.py

    FONCTION PURE : aucun acces base, aucun effet de bord. L'appelant
    (phase H) enregistre le texte final, reindexe les citations
    (indexer_les_citations) et incremente tours_de_mise_a_jour.
    / Pure function; the caller saves, re-indexes, bumps the counter.

    :param texte_markdown: l'article actuel / the current article
    :param operations: liste d'operations (voir le schema en tete de
        module) / operation dicts
    :param identifiants_du_perimetre: les ids d'extractions proposes au
        modele / the extraction ids the model was given
    :return: {"texte_final", "operations_appliquees": [{"indice",
        "operation", "ancien_contenu"?}], "operations_rejetees":
        [{"indice", "operation", "motif"}]}
    """
    # CRLF normalise, comme l'indexeur (relecture F, M2) : un texte a
    # fins de ligne mixtes casserait le decoupage.
    # / CRLF normalized like the indexer does.
    texte_markdown = texte_markdown.replace("\r\n", "\n").replace("\r", "\n")

    lignes_de_preambule, sections = _decouper_en_sections(texte_markdown)
    operations_appliquees = []
    operations_rejetees = []
    # Les cles de section deja modifiees par CE lot : une seule
    # operation de contenu par section (relecture F, M5).
    # / Section keys already modified by THIS batch.
    cles_deja_modifiees = set()

    def _rejeter(indice, operation, motif):
        operations_rejetees.append({
            "indice": indice, "operation": operation, "motif": motif,
        })

    def _accepter(indice, operation, **complement):
        operations_appliquees.append({
            "indice": indice, "operation": operation, **complement,
        })

    for indice, operation in enumerate(operations):
        motif_de_forme = _motif_de_malformation(operation)
        if motif_de_forme is not None:
            _rejeter(indice, operation, motif_de_forme)
            continue

        type_d_operation = operation.get("type")

        if type_d_operation == "no_change":
            # Un no_change vers une section fantome est le meme
            # symptome qu'un append fantome : signale (relecture F, M1).
            # / A no_change on a ghost section is the same symptom.
            titre_vise = operation.get("section", "")
            if titre_vise:
                _indice_de_section, motif = _trouver_la_section(
                    sections, titre_vise,
                )
                if motif is not None:
                    _rejeter(indice, operation, motif)
                    continue
            _accepter(indice, operation)
            continue

        if type_d_operation not in (
            "append_to_section", "replace_section", "insert_section",
        ):
            _rejeter(indice, operation, (
                f"Type d'opération inconnu : « {type_d_operation} ». "
                f"/ Unknown operation type."
            ))
            continue

        # Controles § 6.3 d'abord : une operation sans preuve est
        # rejetee meme si sa cible existe. / § 6.3 checks first.
        motif_de_sources = _controler_les_sources(
            operation, identifiants_du_perimetre,
        )
        if motif_de_sources is not None:
            _rejeter(indice, operation, motif_de_sources)
            continue

        # Seule insert_section cree une section (relecture F, B1).
        # / Only insert_section creates sections.
        if _contenu_fabrique_une_section(operation["contenu"]):
            _rejeter(indice, operation, (
                "Le contenu proposé contient un titre de section (##) : "
                "il fabriquerait une section que personne n'a demandée. "
                "Seule une opération d'insertion crée une section. "
                "/ Content smuggles a section boundary: rejected."
            ))
            continue

        if type_d_operation == "append_to_section":
            indice_de_section, motif = _trouver_la_section(
                sections, operation.get("section"),
            )
            if indice_de_section is None:
                _rejeter(indice, operation, motif)
                continue
            cle = _cle_de_titre(operation.get("section"))
            if cle in cles_deja_modifiees:
                _rejeter(indice, operation, (
                    "Cette section a déjà été modifiée par une opération "
                    "précédente du même lot : une seule opération de "
                    "contenu par section, sinon l'« avant » du diff "
                    "mentirait. / Section already modified in this batch."
                ))
                continue
            section = sections[indice_de_section]
            # On retire les lignes vides finales pour une couture
            # propre, puis on ajoute le contenu. / Clean seam then add.
            while section["lignes"] and not section["lignes"][-1].strip():
                section["lignes"].pop()
            section["lignes"].extend(_corps_normalise(operation["contenu"]))
            cles_deja_modifiees.add(cle)
            _accepter(indice, operation)

        elif type_d_operation == "replace_section":
            indice_de_section, motif = _trouver_la_section(
                sections, operation.get("section"),
            )
            if indice_de_section is None:
                _rejeter(indice, operation, motif)
                continue
            cle = _cle_de_titre(operation.get("section"))
            if cle in cles_deja_modifiees:
                _rejeter(indice, operation, (
                    "Cette section a déjà été modifiée par une opération "
                    "précédente du même lot : une seule opération de "
                    "contenu par section, sinon l'« avant » du diff "
                    "mentirait. / Section already modified in this batch."
                ))
                continue
            section = sections[indice_de_section]
            # § 6.4 : le diff montre l'avant — l'ancien corps est
            # retourne a l'appelant. / § 6.4: the before is returned.
            ancien_contenu = "\n".join(section["lignes"]).strip()
            section["lignes"] = _corps_normalise(operation["contenu"])
            cles_deja_modifiees.add(cle)
            _accepter(indice, operation, ancien_contenu=ancien_contenu)

        elif type_d_operation == "insert_section":
            ancre = (operation.get("apres") or "").strip()
            if not ancre:
                # Motif honnete : l'ancre n'est pas hallucinee, elle
                # n'est pas renseignee (relecture F, I5). Le prompt de
                # la phase G exigera une ancre.
                # / Honest reason: the anchor is missing, not wrong.
                _rejeter(indice, operation, (
                    "L'ancre d'insertion (« apres ») n'est pas "
                    "renseignée : l'applieur ne devine jamais "
                    "l'emplacement d'une section. / Insertion anchor "
                    "not provided."
                ))
                continue
            indice_d_ancrage, motif = _trouver_la_section(sections, ancre)
            if indice_d_ancrage is None:
                # JAMAIS de fallback en fin d'article (§ 6.2) : personne
                # ne verrait que quelque chose a mal tourne.
                # / NEVER an end-of-article fallback.
                _rejeter(indice, operation, motif)
                continue
            titre_propose = (operation.get("titre") or "").strip()
            if not titre_propose:
                _rejeter(indice, operation, (
                    "La nouvelle section n'a pas de titre. "
                    "/ Missing new-section title."
                ))
                continue
            if "\n" in titre_propose or titre_propose.startswith("#"):
                _rejeter(indice, operation, (
                    "Le titre proposé contient un retour à la ligne ou "
                    "des « # » : il casserait la structure de l'article. "
                    "/ Illegal characters in the proposed title."
                ))
                continue
            cle_du_titre = _cle_de_titre(titre_propose)
            titre_deja_pris = any(
                _cle_de_titre(section["titre"]) == cle_du_titre
                for section in sections
            )
            if titre_deja_pris:
                # Un doublon rendrait la section ambigue POUR TOUJOURS
                # (relecture F, I1). / A duplicate would be ambiguous
                # forever.
                _rejeter(indice, operation, (
                    f"La section « {titre_propose} » existe déjà dans "
                    f"l'article : pour la compléter, utilisez un ajout "
                    f"ou un remplacement. / This section title already "
                    f"exists."
                ))
                continue
            nouvelle_section = {
                "titre": titre_propose,
                "ligne_de_titre": f"## {titre_propose}",
                "lignes": _corps_normalise(operation["contenu"]),
            }
            sections.insert(indice_d_ancrage + 1, nouvelle_section)
            cles_deja_modifiees.add(cle_du_titre)
            _accepter(indice, operation)

    return {
        "texte_final": _reconstruire(lignes_de_preambule, sections),
        "operations_appliquees": operations_appliquees,
        "operations_rejetees": operations_rejetees,
    }
