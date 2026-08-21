#!/usr/bin/env python
"""
Banc MANUEL : TYPER les extractions qui ne sont pas verbatim.
/ MANUAL bench: TYPE the extractions that are not verbatim.

LOCALISATION : benchmarks/extraction_format/typer_les_non_verbatim.py

CE QU'IL REPOND. Le banc de rédaction annonce un taux de verbatim par
modèle — 85 % pour `mistral-small`, 87 % pour `mistral-large`, 100 %
pour `gemini-2.5-flash`. Ce taux ne dit pas COMMENT le modèle échoue, et
c'est pourtant la seule chose qui permette de corriger le prompt : on ne
réécrit pas une consigne de la même façon selon que le modèle SAUTE un
passage, l'ANNONCE par des points de suspension, ou REFORMULE.

CE QU'IL NE FAIT PAS. Il n'appelle aucun modèle et n'écrit rien en base.
Il relit ce que la base porte déjà.

LES SIX TYPES, et pourquoi la frontière est là :

- `verbatim`      — le texte est dans la source, une fois normalisé ;
- `ponctuation`   — tous les mots sont là, dans l'ordre et d'un seul
                    tenant : seuls des caractères non-mots diffèrent ;
- `ellipse`       — le modèle a POSÉ une marque (« ... ») à l'endroit
                    du saut. Désobéissance avouée, réparable par le
                    prompt ;
- `saut`          — deux passages littéraux collés SANS marque.
                    Désobéissance invisible : c'est le mode d'échec
                    soupçonné chez Mistral ;
- `reformulation` — des mots que la source ne porte pas ;
- `hors_source`   — moins de la moitié des mots retrouvés.

La normalisation suit celle de la vérification (NFKC, apostrophes
droites, espaces écrasés) : typer autrement compterait comme un écart ce
que la chaîne de preuve accepte. Elle n'est PAS identique — la
vérification traite en plus les guillemets courbes `‘ “ ”`. Sans effet
mesuré sur ce corpus (aucun guillemet courbe en base), mais un texte
qui en porterait se typerait ici en `ponctuation` là où la chaîne de
preuve le tiendrait pour verbatim.

Verrouillé par `hypostasis_extractor/tests/test_typage_des_non_verbatim.py`.
"""

import difflib
import itertools
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

# Django est mis en route ICI, avant l'import du service de production
# plus bas. `setdefault` et `django.setup()` sont idempotents : sous
# `manage.py test`, tout est deja en place et cette section ne fait rien.
# / Django is set up here, before importing the production service.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."),
))

import django  # noqa: E402

django.setup()

# LES REGLES DE FORME VIENNENT DE LA PRODUCTION, jamais d'une copie.
# Ce banc mesure ce que la chaine de preuve FAIT ; une seconde
# definition des memes regles finirait par diverger de la premiere, et
# le banc mesurerait alors autre chose que le produit.
# / The shape rules come from production, never from a copy.
from core.services.verification import (  # noqa: E402
    MARQUES_DE_FIN_DE_PHRASE,
    _ecraser_l_espace_de_ponctuation,
    _l_occurrence_ne_coupe_pas_une_marque_de_fin,
    _le_verbatim_est_present,
    _texte_normalise,
)

# La part des mots retrouvés en dessous de laquelle on cesse de parler
# d'un écart : le modèle n'a pas cité, il a écrit.
# / Below this word coverage, the model did not quote at all.
COUVERTURE_MINIMALE_POUR_PARLER_D_UN_ECART = 0.5

MOTIF_DES_MOTS = re.compile(r"\w+", re.UNICODE)
MARQUES_D_ELLIPSE = ("...", "…")


def normaliser(texte):
    """
    LA normalisation de la verification, importee — jamais recopiee.
    / The verification's own normalisation, imported, never copied.

    Une seconde definition finirait par diverger : celle du banc ignorait
    les guillemets courbes que la production remplace, et typait donc en
    « ponctuation » ce que la chaine de preuve tient pour verbatim.
    """
    return _texte_normalise(texte)


def _decouper_en_mots(texte):
    """Les mots seuls, en minuscules. / Words only, lowercased."""
    return [mot.casefold() for mot in MOTIF_DES_MOTS.findall(texte)]


def _positions_par_mot(mots_de_la_source):
    """
    Où chaque mot apparaît dans la source. / Where each word occurs.

    Sert à retrouver vite le point de départ d'un bloc littéral, sans
    balayer la source entière à chaque essai.
    """
    positions = defaultdict(list)
    for indice, mot in enumerate(mots_de_la_source):
        positions[mot].append(indice)
    return positions


def _plus_long_bloc_commun(mots_source, positions, mots_extrait, depart_extrait,
                           depart_minimal_dans_la_source):
    """
    Le plus long morceau de l'extrait, à partir de `depart_extrait`, qui
    se lit tel quel dans la source.
    / The longest run of the extract that reads verbatim in the source.

    À longueur égale, on préfère la position la PLUS PROCHE en avant du
    bloc précédent : c'est la lecture naturelle d'un modèle qui parcourt
    sa source de haut en bas, et c'est elle qui rend les « sauts »
    comptables.

    :return: (position_dans_la_source, longueur_en_mots) — longueur 0 si
             le mot de départ est absent de la source.
    """
    meilleure_position = -1
    meilleure_longueur = 0

    for position in positions.get(mots_extrait[depart_extrait], []):
        longueur = 0
        while (position + longueur < len(mots_source)
               and depart_extrait + longueur < len(mots_extrait)
               and mots_source[position + longueur]
               == mots_extrait[depart_extrait + longueur]):
            longueur += 1

        # On garde le bloc le plus long ; à égalité, celui qui avance le
        # moins loin dans la source, et de préférence vers l'avant.
        # / Longest block wins; ties go to the nearest forward position.
        position_est_en_avant = position >= depart_minimal_dans_la_source
        meilleure_est_en_avant = meilleure_position >= depart_minimal_dans_la_source
        if longueur > meilleure_longueur:
            meilleure_position, meilleure_longueur = position, longueur
        elif longueur == meilleure_longueur and longueur > 0:
            if position_est_en_avant and not meilleure_est_en_avant:
                meilleure_position = position
            elif position_est_en_avant and meilleure_est_en_avant:
                meilleure_position = min(meilleure_position, position)

    return meilleure_position, meilleure_longueur


def decomposer_en_blocs(texte_source, texte_extrait):
    """
    Décompose l'extrait en morceaux qui se lisent tels quels dans la
    source, et relève ce qui n'en est pas.
    / Splits the extract into runs found verbatim in the source.

    FLUX :
    1. on part du premier mot de l'extrait ;
    2. on prend le plus long morceau lisible tel quel dans la source ;
    3. si le mot n'y est pas du tout, on le range en « hors source » ;
    4. on recommence jusqu'au bout de l'extrait.

    :return: dict avec `blocs` (position source, longueur),
             `mots_hors_source` et `mots_de_l_extrait`.
    """
    mots_source = _decouper_en_mots(texte_source)
    mots_extrait = _decouper_en_mots(texte_extrait)
    positions = _positions_par_mot(mots_source)

    blocs = []
    mots_hors_source = []
    indice_dans_l_extrait = 0
    position_minimale_dans_la_source = 0

    while indice_dans_l_extrait < len(mots_extrait):
        position, longueur = _plus_long_bloc_commun(
            mots_source, positions, mots_extrait, indice_dans_l_extrait,
            position_minimale_dans_la_source,
        )
        if longueur == 0:
            # Ce mot n'existe nulle part dans la source.
            # / This word appears nowhere in the source.
            mots_hors_source.append(mots_extrait[indice_dans_l_extrait])
            indice_dans_l_extrait += 1
            continue

        blocs.append((position, longueur))
        indice_dans_l_extrait += longueur
        position_minimale_dans_la_source = position + longueur

    return {
        "blocs": blocs,
        "mots_hors_source": mots_hors_source,
        "mots_de_l_extrait": len(mots_extrait),
    }


def _compter_les_sauts(blocs):
    """
    Combien de fois la lecture quitte le fil de la source.
    / How many times the reading leaves the source's thread.

    Deux blocs qui se suivent EXACTEMENT ne font pas un saut. Tout le
    reste en fait un : trou en avant comme retour en arrière.
    """
    nombre_de_sauts = 0
    for precedent, suivant in zip(blocs, blocs[1:]):
        fin_du_precedent = precedent[0] + precedent[1]
        if suivant[0] != fin_du_precedent:
            nombre_de_sauts += 1
    return nombre_de_sauts


def typer_l_ecart(texte_source, texte_extrait):
    """
    Dit de quelle NATURE est l'écart entre une extraction et sa source.
    / Says what KIND of gap separates an extraction from its source.

    LOCALISATION : benchmarks/extraction_format/typer_les_non_verbatim.py

    L'ordre des tests porte le sens de la mesure :
    1. un texte étranger à la source n'est pas un écart, c'est autre
       chose — on le sort tout de suite ;
    2. une ellipse est une désobéissance AVOUÉE : on la reconnaît à sa
       marque, avant de regarder la géométrie ;
    3. une reformulation se voit aux mots que la source ne porte pas ;
    4. reste la géométrie : un saut, ou rien.

    :return: dict avec `categorie`, `sauts`, `mots_hors_source`,
             `couverture`, `blocs`.
    """
    source_normalisee = normaliser(texte_source)
    extrait_normalise = normaliser(texte_extrait)

    decomposition = decomposer_en_blocs(source_normalisee, extrait_normalise)
    nombre_de_sauts = _compter_les_sauts(decomposition["blocs"])
    mots_retrouves = sum(longueur for _, longueur in decomposition["blocs"])
    couverture = mots_retrouves / max(decomposition["mots_de_l_extrait"], 1)

    mesure = {
        "sauts": nombre_de_sauts,
        "mots_hors_source": decomposition["mots_hors_source"],
        "couverture": couverture,
        "blocs": decomposition["blocs"],
    }

    if extrait_normalise and extrait_normalise in source_normalisee:
        mesure["categorie"] = "verbatim"
        return mesure

    if couverture < COUVERTURE_MINIMALE_POUR_PARLER_D_UN_ECART:
        mesure["categorie"] = "hors_source"
        return mesure

    # La marque d'ellipse ne compte que si le modèle l'a AJOUTÉE : une
    # source qui porte déjà « ... » ne rend pas son extrait fautif.
    # / The ellipsis marker only counts when the model added it.
    ellipse_ajoutee = any(
        marque in extrait_normalise and marque not in source_normalisee
        for marque in MARQUES_D_ELLIPSE
    )
    if ellipse_ajoutee:
        mesure["categorie"] = "ellipse"
        return mesure

    if decomposition["mots_hors_source"]:
        mesure["categorie"] = "reformulation"
        return mesure

    if nombre_de_sauts:
        mesure["categorie"] = "saut"
        return mesure

    # Tous les mots, dans l'ordre, d'un seul tenant : ce qui diffère
    # n'est pas un mot. / Only non-word characters differ.
    mesure["categorie"] = "ponctuation"
    return mesure


# Le carnet que ce banc mesure. / The notebook this bench measures.
NOM_DU_CARNET_ETALON = "Documents étalons"


def extractions_du_carnet_etalon():
    """
    Les extractions du carnet etalon, et ELLES SEULES. / Reference only.

    LOCALISATION : benchmarks/extraction_format/typer_les_non_verbatim.py

    POURQUOI CE FILTRE EXISTE. Le serveur de developpement est permanent
    et quelqu'un s'en sert : sans perimetre, ce banc balayait TOUTE la
    base et ses tableaux cessaient d'etre reproductibles des qu'une note
    etrangere etait analysee. Constate le 19 aout 2026 — le typage de
    `mistral-small` etait passe de 137 extractions a 306 entre la mesure
    et sa relecture, sans qu'une ligne de code ait bouge.

    LES EXTRACTIONS MASQUEES SONT GARDEES, elles : le masquage a servi a
    figer le perimetre d'un AUTRE banc, celui des redacteurs. Ici on
    veut voir les trois extracteurs.
    / Hidden extractions are kept: masking served another bench.
    """
    from hypostasis_extractor.models import ExtractedEntity

    return ExtractedEntity.objects.filter(
        job__page__appartenances_dossiers__dossier__name=NOM_DU_CARNET_ETALON,
    ).distinct()


def main():
    """
    Type toutes les extractions de la base, modèle par modèle.
    / Types every extraction in the database, model by model.
    """
    from core.models import ElementDocument
    from hypostasis_extractor.models import ExtractedEntity

    textes_de_source = {}

    def source_de(identifiant_de_page):
        if identifiant_de_page not in textes_de_source:
            textes_de_source[identifiant_de_page] = "\n".join(
                ElementDocument.objects
                .filter(page_id=identifiant_de_page)
                .order_by("ordre").values_list("texte", flat=True)
            )
        return textes_de_source[identifiant_de_page]

    par_modele = defaultdict(Counter)
    ecarts_a_montrer = defaultdict(list)

    for extraction in extractions_du_carnet_etalon().select_related(
        "job", "job__ai_model", "job__page",
    ).iterator():
        if not extraction.job.ai_model:
            continue
        texte_de_la_source = source_de(extraction.job.page_id)
        if not texte_de_la_source:
            continue

        mesure = typer_l_ecart(texte_de_la_source, extraction.extraction_text)
        modele = extraction.job.ai_model.model_choice
        par_modele[modele][mesure["categorie"]] += 1
        if mesure["categorie"] != "verbatim":
            ecarts_a_montrer[modele].append((extraction, mesure))

    print("\n=== LE MODE D'ÉCHEC, modèle par modèle ===\n")
    categories = ["verbatim", "ponctuation", "ellipse", "saut",
                  "reformulation", "hors_source"]
    entete = f"{'modèle':26}" + "".join(f"{c:>14}" for c in categories)
    print(entete)
    for modele in sorted(par_modele):
        compte = par_modele[modele]
        total = sum(compte.values())
        ligne = f"{modele:26}"
        for categorie in categories:
            ligne += f"{compte[categorie]:>14}"
        print(ligne + f"   (total {total})")

    print("\n=== LES RETOUCHES, caractère par caractère ===\n")
    print("  (DESCRIPTIF : ce que l'extrait porte et pas la fenêtre source.")
    print("   Il ne dit PAS qui l'a mis là — c'est le tableau suivant.)\n")
    for (operation, cote_source, cote_extrait), compte in (
        mesurer_les_retouches_de_la_base().most_common(12)
    ):
        print(f"  {compte:4}  {operation:8} "
              f"source={cote_source!r:10} extrait={cote_extrait!r}")

    par_cause, par_article, redacteurs = mesurer_les_introuvables()
    print("\n=== LES INTROUVABLE — forme ou fond ? ===\n")
    print(f"  articles produits par : {sorted(set(redacteurs.values()))}")
    total_introuvable = sum(par_cause.values())
    for cause, compte in par_cause.most_common():
        part = 100 * compte / max(total_introuvable, 1)
        print(f"  {compte:4} ({part:4.0f}%)  {cause}")
    print(f"  {total_introuvable:4}          TOTAL")
    print()
    for titre, causes in sorted(par_article.items()):
        print(f"  « {titre} » : {dict(causes)}")

    print("\n=== LE DÉTAIL DES ÉCARTS ===\n")
    for modele in sorted(ecarts_a_montrer):
        print(f"\n--- {modele} — {len(ecarts_a_montrer[modele])} écart(s)\n")
        for extraction, mesure in ecarts_a_montrer[modele]:
            print(f"  [{mesure['categorie']}] extraction {extraction.id} "
                  f"· note « {extraction.job.page.title[:40]} » "
                  f"· {mesure['sauts']} saut(s) "
                  f"· couverture {mesure['couverture']:.0%}")
            if mesure["mots_hors_source"]:
                print(f"      mots absents de la source : "
                      f"{mesure['mots_hors_source']}")
            print(f"      « {normaliser(extraction.extraction_text)[:160]} »")



# --- LES TROIS RÈGLES D'ASSOUPLISSEMENT DU VERBATIM -------------------
# Elles sont importées de `core/services/verification.py` : ce banc
# mesure ce que la chaîne de preuve fait, pas ce qu'il en réimplémente.
# Ce qui suit n'existe QUE pour le banc : dire LAQUELLE des trois règles
# suffit à retrouver une citation — la production, elle, n'a pas besoin
# de le savoir.
# / Imported from production; what follows only names WHICH rule sufficed.


def _sans_point_final(texte):
    """Retire un point terminal. / Strips one trailing period."""
    return texte[:-1] if texte.endswith(".") else texte


def _essayer(source, extrait, regles):
    """Le verbatim passe-t-il sous ces règles ? / Does it pass?"""
    # On retient si l'extrait D'ORIGINE portait une marque de fin : la
    # règle « point final » va la lui retirer, et la garde doit
    # s'appliquer quand même. / Remember before rule 1 strips it.
    # La production attend LA MARQUE (une chaine), pas un booleen : lui
    # passer `True` rendait la branche « meme signe » morte au banc.
    # / Production expects the MARK itself, not a boolean.
    derniere_marque = extrait[-1:]
    marque_de_l_extrait = (
        derniere_marque if derniere_marque in MARQUES_DE_FIN_DE_PHRASE else ""
    )

    texte_de_l_extrait = extrait
    texte_de_la_source = source

    if "majuscule initiale" in regles and texte_de_l_extrait:
        texte_de_l_extrait = (
            texte_de_l_extrait[:1].lower() + texte_de_l_extrait[1:]
        )
    if "espace de ponctuation" in regles:
        texte_de_l_extrait = _ecraser_l_espace_de_ponctuation(
            texte_de_l_extrait)
        texte_de_la_source = _ecraser_l_espace_de_ponctuation(
            texte_de_la_source)
    if "point final" in regles:
        texte_de_l_extrait = _sans_point_final(texte_de_l_extrait)
        if not texte_de_l_extrait:
            return False

    return _l_occurrence_ne_coupe_pas_une_marque_de_fin(
        texte_de_la_source, texte_de_l_extrait, marque_de_l_extrait,
    )


def reparation_qui_suffit(texte_source, texte_extrait):
    """
    La PLUS PETITE retouche de forme qui retrouverait cette citation.
    / The SMALLEST shape fix that would find this quote again.

    LOCALISATION : benchmarks/extraction_format/typer_les_non_verbatim.py

    :return: `None` si la citation est déjà verbatim ; le nom des règles
             qui suffisent, joints par « + » ; `"IRRECUPERABLE"` si
             aucune combinaison n'y parvient — c'est alors le FOND qui a
             bougé, et aucune règle de forme ne doit le rattraper.
    """
    source = normaliser(texte_source)
    extrait = normaliser(texte_extrait)

    # Une chaîne vide est sous-chaîne de TOUT : sans cette garde, un
    # extrait vide — ou réduit à un point, que la règle 1 viderait — se
    # déclarerait retrouvé partout.
    # / The empty string is a substring of everything.
    if not extrait or not extrait.strip("."):
        return "IRRECUPERABLE"

    if extrait in source:
        return None

    # L'ORACLE EST LA PRODUCTION, jamais la reimplementation qui suit.
    # Les combinaisons ci-dessous ne servent qu'a NOMMER la regle qui a
    # suffi ; elles n'ont pas le droit de decider. Sans cette ligne, le
    # banc annonçait « IRRECUPERABLE » — donc « le FOND a bouge » — sur
    # des cas que la chaine de preuve accepte, parce qu'il essayait la
    # casse dans un seul sens quand la production l'essaie dans les deux.
    # / The oracle is production; the combinations below only NAME the
    #   rule that sufficed. They never decide.
    if not _le_verbatim_est_present(extrait, source):
        return "IRRECUPERABLE"

    # L'ORDRE PORTE DU SENS, il n'est pas arbitraire. Deux regles
    # peuvent expliquer le meme ecart — « territoire . Soutenu » cite
    # « territoire. » se repare AUSSI BIEN en retirant le point qu'en
    # recollant l'espace. La cause retenue doit alors etre celle de la
    # SOURCE, pas celle du modele : c'est notre ingestion qui a detache
    # le point, et l'attribuer au modele ferait croire a un defaut de
    # PROMPT la ou il y a un defaut d'INGESTION. Les deux se corrigent a
    # des endroits opposes.
    # / When two rules explain the same gap, the SOURCE's rule wins:
    #   blaming the model would send the fix to the wrong place.
    regles = ["espace de ponctuation", "point final", "majuscule initiale"]
    for nombre_de_regles in (1, 2, 3):
        for combinaison in itertools.combinations(regles, nombre_de_regles):
            if _essayer(source, extrait, combinaison):
                return " + ".join(combinaison)
    # La production accepte, mais aucune combinaison nommee ne l'explique.
    # / Production accepts it, but no named rule explains it.
    return "retouche non nommée"


def compter_les_retouches(texte_source, texte_extrait):
    """
    QUELS caractères le modèle a retouchés, un par un.
    / WHICH characters the model touched, one by one.

    LOCALISATION : benchmarks/extraction_format/typer_les_non_verbatim.py

    `typer_l_ecart` dit de quelle NATURE est l'écart ; celle-ci dit ce
    qu'il contient. Elle aligne l'extrait sur la fenêtre exacte de la
    source — celle que la décomposition en blocs a localisée — puis
    compare caractère par caractère.

    LA FENÊTRE EST LE POINT DÉLICAT. Chercher le premier mot de
    l'extrait dans toute la source tombe sur une autre occurrence et
    rend un diff illisible, plein de faux remplacements. On part donc
    des blocs déjà localisés.

    :return: liste de (opération, texte de la source, texte de l'extrait)
    """
    source = normaliser(texte_source)
    extrait = normaliser(texte_extrait)
    decomposition = decomposer_en_blocs(source, extrait)
    if not decomposition["blocs"]:
        return []

    positions_des_mots = [m.span() for m in MOTIF_DES_MOTS.finditer(source)]
    premier_bloc = decomposition["blocs"][0]
    dernier_bloc = decomposition["blocs"][-1]
    debut = positions_des_mots[premier_bloc[0]][0]
    fin = positions_des_mots[dernier_bloc[0] + dernier_bloc[1] - 1][1]
    fenetre = source[debut:fin]

    retouches = []
    comparateur = difflib.SequenceMatcher(None, fenetre, extrait,
                                          autojunk=False)
    for operation, debut_source, fin_source, debut_extrait, fin_extrait in (
        comparateur.get_opcodes()
    ):
        if operation == "equal":
            continue
        retouches.append((
            operation,
            fenetre[debut_source:fin_source],
            extrait[debut_extrait:fin_extrait],
        ))
    return retouches


def mesurer_les_retouches_de_la_base():
    """
    Le compte des retouches, tous modèles confondus. / Touch-up counts.

    Ce que ce compte NE dit PAS : quelle règle les répare. Une même
    retouche peut venir du modèle ou de la source — c'est
    `reparation_qui_suffit` qui tranche, pas celle-ci.
    """
    from core.models import ElementDocument
    from hypostasis_extractor.models import ExtractedEntity

    textes_de_source = {}

    def source_de(identifiant_de_page):
        if identifiant_de_page not in textes_de_source:
            textes_de_source[identifiant_de_page] = "\n".join(
                ElementDocument.objects
                .filter(page_id=identifiant_de_page)
                .order_by("ordre").values_list("texte", flat=True)
            )
        return textes_de_source[identifiant_de_page]

    compte = Counter()
    for extraction in extractions_du_carnet_etalon().select_related(
        "job", "job__ai_model",
    ).iterator():
        if not extraction.job.ai_model:
            continue
        texte_de_la_source = source_de(extraction.job.page_id)
        if not texte_de_la_source:
            continue
        # SEULEMENT les non-verbatim. Sur un extrait déjà verbatim, la
        # fenêtre s'arrête au dernier MOT : un extrait qui finit par un
        # point produirait un « insert '.' » qui n'est pas une retouche
        # du modèle, mais une frontière de fenêtre.
        # / Verbatim extracts would yield a window-boundary artefact.
        if normaliser(extraction.extraction_text) in normaliser(
            texte_de_la_source
        ):
            continue
        for operation, cote_source, cote_extrait in compter_les_retouches(
            texte_de_la_source, extraction.extraction_text,
        ):
            # On ne retient que les retouches COURTES : au-delà, ce
            # n'est plus une retouche, c'est un saut de passage — et il
            # est déjà compté par le typage.
            # / Long edits are passage jumps, already counted elsewhere.
            if len(cote_source) > 3 or len(cote_extrait) > 3:
                continue
            compte[(operation, cote_source, cote_extrait)] += 1
    return compte


def mesurer_les_introuvables():
    """
    Pourquoi chaque citation `INTROUVABLE` l'est, et ce qui la sauverait.
    / Why each INTROUVABLE citation is one, and what would save it.

    LOCALISATION : benchmarks/extraction_format/typer_les_non_verbatim.py

    LE COMPTE QUI DÉCIDE. Le taux d'`INTROUVABLE` est présenté comme un
    défaut de l'EXTRACTEUR. Cette fonction sépare ce qui l'est vraiment
    — le fond a bougé — de ce qui n'est qu'une retouche de FORME que
    notre comparaison refuse.

    Elle lit la base et n'appelle aucun modèle : le contrôle verbatim
    est déterministe et gratuit, seul le juge est facturé.
    """
    from core.models import ElementDocument, SourceLink
    from hypostasis_extractor.models import ExtractionJob

    textes_de_source = {}

    def source_de(identifiant_de_page):
        if identifiant_de_page not in textes_de_source:
            textes_de_source[identifiant_de_page] = "\n".join(
                ElementDocument.objects
                .filter(page_id=identifiant_de_page)
                .order_by("ordre").values_list("texte", flat=True)
            )
        return textes_de_source[identifiant_de_page]

    par_cause = Counter()
    par_article = defaultdict(Counter)
    for lien in SourceLink.objects.filter(
        etat_de_verification="introuvable",
    ).select_related("extraction_source__job", "page_cible"):
        extraction = lien.extraction_source
        if extraction is None:
            par_cause["extraction supprimée"] += 1
            continue
        cause = reparation_qui_suffit(
            source_de(extraction.job.page_id), extraction.extraction_text,
        )
        # `None` = déjà verbatim : la source a changé depuis le verdict.
        # / None means the source changed since the verdict.
        cause = cause or "verbatim aujourd'hui"
        par_cause[cause] += 1
        par_article[lien.page_cible.title[:38]][cause] += 1

    # QUI a écrit ces articles : sans cette ligne, le rapport dirait
    # « les articles mesurés » pour un seul rédacteur.
    # / Which writer produced these articles.
    redacteurs = {}
    for titre_de_page in SourceLink.objects.filter(
        etat_de_verification="introuvable",
    ).values_list("page_cible_id", flat=True).distinct():
        job = ExtractionJob.objects.filter(
            page_id=titre_de_page,
        ).exclude(raw_result__contains={"est_verification": True}
                  ).order_by("-pk").select_related("ai_model").first()
        if job:
            redacteurs[titre_de_page] = (
                job.ai_model.model_choice if job.ai_model else "?"
            )
    return par_cause, par_article, redacteurs

if __name__ == "__main__":
    main()
