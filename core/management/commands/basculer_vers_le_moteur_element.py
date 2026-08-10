"""
Bascule les pages existantes vers le moteur ELEMENT.
/ Migrates existing pages to the ELEMENT engine.

LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

CE QUE FAIT CETTE COMMANDE

Pour chaque page encore sur l'ANCIEN moteur, selon ce qu'elle porte deja :

  · elle N'A PAS d'elements — le cas minoritaire (5 pages en dev) :
      1. elle decoupe text_readability en elements, sur les paragraphes ;
      2. elle traduit les anciens offsets de chaque extraction en portions.

  · elle EN A DEJA — le cas majoritaire (537 pages en dev, elements
    dormants issus des phases de test du moteur) :
      1. elle ne recree RIEN — recreer dupliquerait les blocs ;
      2. elle retrouve la position de chaque element dans le texte de la
         page, puis re-ancre les SEULES extractions encore sans portion.

  · dans les deux cas, si la page a des blocs a lire a la fin, elle passe
    sur le moteur ELEMENT (`Page.moteur`).

POURQUOI LE FLAG EST POSE ICI, ET NULLE PART AILLEURS

Cette commande est anterieure au champ `Page.moteur` (branchement BR-A) :
elle creait des elements sans jamais dire que la page avait change de
moteur. D'ou l'etat trouve le 10 aout — 537 pages pourvues d'elements ET
d'ancrages, mais toutes affichees par l'ANCIEN moteur. La reconversion
§ 9.5 est precisement le geste qui manquait.
/ This command predates the Page.moteur field; it built elements without
ever flipping the engine. That is the gap it now closes.

CE QU'ELLE NE SUPPRIME JAMAIS

Aucune extraction, aucun commentaire. Une extraction qu'on n'arrive pas a
re-ancrer reste en base, sans portion : elle apparaitra dans la section
« detachees », ou un humain decidera. C'est le principe « rien ne
disparait en silence », applique a la bascule elle-meme.
/ No extraction and no comment is ever deleted.

C'est ce qui rend la reconversion sans risque pour la donnee la plus
precieuse de la base : les 983 commentaires humains. Ils pendent aux
extractions (`CommentaireExtraction.entity`, en CASCADE) — tant qu'aucune
extraction ne part, aucun commentaire ne part, meme si son extraction
finit detachee.
/ Comments hang off extractions; no extraction is ever removed.

POURQUOI ON TENTE UN RE-ANCRAGE PLUTOT QUE DE TOUT JETER

Les anciens offsets (start_char/end_char) ne sont pas fiables : ils
comptent dans un texte plat qui a pu bouger. Mais le TEXTE de
l'extraction, lui, est fiable. Le chercher dans les elements permet de
recuperer gratuitement une grande partie des ancres.

On applique la meme regle que partout ailleurs : si le texte apparait
plusieurs fois, on ne devine pas — l'extraction reste detachee.
/ The old offsets are unreliable, but the extracted TEXT is not.

LANCER LA COMMANDE

    # Voir ce qui se passerait, sans rien ecrire :
    docker exec hypostasia_web uv run python manage.py \\
        basculer_vers_le_moteur_element --a-blanc

    # Faire la bascule pour de vrai :
    docker exec hypostasia_web uv run python manage.py \\
        basculer_vers_le_moteur_element

    # Une seule page, pour essayer :
    docker exec hypostasia_web uv run python manage.py \\
        basculer_vers_le_moteur_element --page 42
"""

import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists, OuterRef

from core.models import (
    ElementDocument,
    MoteurDePage,
    Page,
    empreinte_du_texte,
)
from hypostasis_extractor.services.ancrage import (
    construire_la_table_des_offsets,
    decouper_le_span_en_portions_par_element,
)
from hypostasis_extractor.models import (
    AncrageExtraction,
    CommentaireExtraction,
    EtatAncrage,
    ExtractedEntity,
)

# Un paragraphe se termine par au moins un saut de ligne double.
# / A paragraph ends with at least a double line break.
SEPARATEUR_DE_PARAGRAPHE = re.compile(r"\n\s*\n+")

# En dessous de cette longueur, un « paragraphe » n'est pas du contenu :
# c'est une ligne vide residuelle, une puce isolee, un artefact.
# / Below this length, a "paragraph" is an artifact, not content.
LONGUEUR_MINIMALE_D_UN_ELEMENT = 2

# POURQUOI IL N'Y A PAS DE REPLI PAR RECHERCHE DE TEXTE
#
# Une version precedente cherchait le texte de l'extraction dans le
# document quand ses offsets ne disaient rien (le couple 0-0 que l'ancien
# moteur ecrivait lorsque LangExtract ne retrouvait pas le passage).
# L'ancien rendu faisait de meme (front/utils.py, repli de recherche).
#
# Mesure du 10 aout 2026 sur les 1 707 extractions a 0-0 de la base de
# dev : la recherche en retrouve 12 sans ambiguite — 0,7 %. Elle en
# trouve 75 a plusieurs endroits, qu'il faudrait de toute facon refuser
# faute de savoir lequel etait vise, et n'en retrouve AUCUNE des 92 qui
# portent un commentaire humain. Le gain ne paie ni la complexite ni le
# risque d'ancrer faux en silence.
# / Measured: text search recovers 0.7 % and none of the commented ones.

# Part de la citation qu'une ancre NEUVE doit couvrir pour etre posee.
#
# Un span peut tomber dans les bornes du texte sans tomber au bon
# endroit : « dans les bornes » n'est pas « a la bonne place ». Mesure du
# 10 aout sur les 518 extractions re-ancrables — 452 tranches egalent la
# citation, 11 la couvrent a 95 % ou plus (une ponctuation finale de
# moins), 47 designent autre chose (dont une citation de 500 caracteres
# dont le span ne couvrait que « l' »), et 8 portent un span vide ou
# inverse, refuse plus haut. Le seuil separe les deux populations sans
# rien couper au milieu : entre 50 % et 95 %, la base ne contient QUE
# deux cas.
# / In-bounds is not in-place; the threshold separates two clean groups.
COUVERTURE_MINIMALE_D_UNE_ANCRE_NEUVE = 0.95

ESPACES_MULTIPLES = re.compile(r"\s+")

# Differences d'ecriture qui ne changent pas le passage designe.
# / Spelling differences that do not change which passage is meant.
EQUIVALENCES_TYPOGRAPHIQUES = {
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "‑": "-", "­": "-",
    " ": " ", " ": " ",
}


def normaliser_pour_comparer(texte):
    """
    Ramene un texte a la forme sous laquelle on le compare a un autre.
    / Reduces a text to the form in which we compare it to another.

    LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

    Cette normalisation-la CHANGE la longueur (elle ecrase les espaces
    multiples) : elle sert uniquement a comparer deux textes, jamais a
    calculer une position.
    / This one changes lengths: for comparison only, never for positions.
    """
    texte = texte or ""
    for caractere, equivalent in EQUIVALENCES_TYPOGRAPHIQUES.items():
        texte = texte.replace(caractere, equivalent)
    return ESPACES_MULTIPLES.sub(" ", texte).strip().lower()


def recomposer_le_texte_ancre(morceaux):
    """
    Recolle les portions d'une ancre en un seul texte comparable.
    / Joins an anchor's portions into one comparable text.

    LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

    :param morceaux: les tranches de texte, une par element traverse
    :return: le texte que l'ancre surligne

    POURQUOI UN ESPACE ENTRE LES MORCEAUX

    Une citation a cheval sur deux blocs est ancree en deux portions. Les
    blocs sont, dans le document, separes par un blanc — que les portions
    ne portent pas, puisqu'il tombe dans le trou entre deux elements. Les
    recoller bout a bout souderait le dernier mot de l'un au premier de
    l'autre (« l'unanimite.La minorite »), et une ancre parfaitement
    juste passerait pour fausse.

    Mesure du 10 aout : le collage sans separateur condamnait 309 ancres
    correctes sur la base de dev.
    / Measured: joining without a separator condemned 309 valid anchors.
    """
    return " ".join(morceaux)


def l_ancre_couvre_la_citation(texte_ancre, citation):
    """
    Dit si une ancre NEUVE designe bien le passage qu'elle pretend citer.
    / Says whether a NEW anchor really points at the quoted passage.

    LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

    :param texte_ancre: le texte que l'ancre surlignerait, recompose
        depuis les elements
    :param citation: `extraction_text`, ce que l'extraction pretend citer
    :return: True si l'ancre peut etre posee

    Exigeante par construction : on ne FABRIQUE une ancre que si elle dit
    vrai. Comparer a `l_ancre_designe_un_autre_passage`, qui est bien plus
    tolerante — parce que detruire une ancre existante et en creer une
    fausse ne se valent pas.
    / Strict on creation; see the tolerant predicate used on existing ones.
    """
    for ancre, attendu in _formes_comparables(texte_ancre, citation):
        if not ancre or not attendu:
            return False
        if ancre == attendu:
            return True
        if ancre not in attendu and attendu not in ancre:
            continue
        # LA COUVERTURE SE MESURE DANS LES DEUX SENS.
        #
        # Rapporter la longueur de l'ancre a celle de la citation ne borne
        # qu'un cote : une ancre SEPT FOIS trop longue donne un rapport de
        # 7, qui passe tout seuil. Or surligner le paragraphe entier pour
        # une citation d'un mot est le meme mensonge que l'inverse — le
        # lecteur croit lire la preuve.
        # / Coverage must be bounded on both sides, not just one.
        couverture = min(len(ancre), len(attendu)) / max(
            len(ancre), len(attendu),
        )
        if couverture >= COUVERTURE_MINIMALE_D_UNE_ANCRE_NEUVE:
            return True
    return False


def _formes_comparables(texte_ancre, citation):
    """
    Rend les couples (ancre, citation) sous lesquels les comparer.
    / Yields the (anchor, quote) pairs under which to compare them.

    LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

    LA SECONDE FORME : SANS AUCUN ESPACE

    Recoller deux blocs avec un espace suppose qu'un blanc les separait.
    C'est vrai la plupart du temps, faux quand un mot a ete coupe par un
    tiret a la frontiere : la citation dit « Jesus-Christ », l'ancre
    recomposee dit « Jesus- Christ ». Meme passage, comparaison perdue.

    Comparer une seconde fois en retirant TOUS les espaces des deux cotes
    tranche ces cas sans rien relacher : deux textes qui ne different que
    par des blancs designent le meme passage. Mesure du 10 aout : 4 ancres
    dormantes justes et 5 ancres neuves justes se jouaient la-dessus.
    / Two texts differing only in whitespace point at the same passage.
    """
    ancre = normaliser_pour_comparer(texte_ancre)
    attendu = normaliser_pour_comparer(citation)
    yield ancre, attendu
    sans_blancs_ancre = ancre.replace(" ", "")
    sans_blancs_attendu = attendu.replace(" ", "")
    if (sans_blancs_ancre, sans_blancs_attendu) != (ancre, attendu):
        yield sans_blancs_ancre, sans_blancs_attendu


def l_ancre_designe_un_autre_passage(texte_ancre, citation):
    """
    Dit si une ancre EXISTANTE surligne un passage sans rapport.
    / Says whether an EXISTING anchor highlights an unrelated passage.

    LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

    POURQUOI CE SEUIL-CI EST PLUS TOLERANT QUE L'AUTRE

    Les 28 096 ancres deja en base viennent d'anciennes phases de test.
    La reconversion les rend officielles, donc elle les regarde — mais
    elle n'a pas a les refaire. Mesure du 10 aout : la majorite egale sa
    citation ou la couvre presque entierement, une partie n'en surligne
    qu'un MORCEAU, et **1 402 designent un passage sans rapport** (5,0 %,
    dont 36 portant un commentaire humain).

    Decision du proprietaire du 10 aout : detacher celles qui mentent,
    garder les tronquees. Surligner une partie du bon passage est
    degrade ; surligner un autre passage est faux, et l'ancre est la
    preuve — c'est le seul mensonge que le produit ne peut pas se
    permettre.
    / Owner's call: detach the lying ones, keep the merely truncated.
    """
    attendu = normaliser_pour_comparer(citation)
    if not attendu:
        return False

    # Une ancre qui ne surligne RIEN n'est pas une ancre tronquee : elle
    # n'affiche aucun passage tout en se presentant comme une preuve.
    # / An anchor highlighting nothing is not a truncated anchor.
    if not normaliser_pour_comparer(texte_ancre):
        return True

    for ancre, attendu_compare in _formes_comparables(texte_ancre, citation):
        if ancre in attendu_compare or attendu_compare in ancre:
            return False
    return True


class Command(BaseCommand):
    help = (
        "Bascule les pages vers le moteur ELEMENT : cree les elements et "
        "tente de re-ancrer les extractions existantes."
    )

    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--a-blanc",
            action="store_true",
            help="Affiche ce qui serait fait, sans rien ecrire en base.",
        )
        analyseur_d_arguments.add_argument(
            "--page",
            type=int,
            default=None,
            help="Ne traiter qu'une seule page, par son identifiant.",
        )
        analyseur_d_arguments.add_argument(
            "--limite",
            type=int,
            default=None,
            help="Ne traiter que les N premieres pages.",
        )

    def handle(self, *args, **options):
        a_blanc = options["a_blanc"]
        identifiant_de_page = options["page"]
        limite = options["limite"]

        # ON SELECTIONNE PAR LE FLAG, PAS PAR L'ABSENCE D'ELEMENTS.
        #
        # L'ancien filtre `elements__isnull=True` rendait 537 des 542 pages
        # a reconvertir INVISIBLES a la commande — y compris quand on la
        # lancait sur une page nommee par --page, qui repondait alors
        # « 0 page a traiter » sans dire pourquoi.
        # / Selecting by flag, not by absence of elements.
        pages_a_traiter = Page.objects.filter(moteur=MoteurDePage.ANCIEN)
        if identifiant_de_page is not None:
            pages_a_traiter = pages_a_traiter.filter(pk=identifiant_de_page)
        pages_a_traiter = pages_a_traiter.order_by("pk")
        if limite is not None:
            pages_a_traiter = pages_a_traiter[:limite]

        nombre_de_pages = pages_a_traiter.count()
        if a_blanc:
            self.stdout.write(self.style.WARNING(
                "MODE A BLANC — rien ne sera ecrit en base.",
            ))
        self.stdout.write(f"{nombre_de_pages} page(s) a traiter.\n")

        if nombre_de_pages == 0 and identifiant_de_page is not None:
            self._expliquer_la_page_absente(identifiant_de_page)
            return

        bilan_general = {
            "pages": 0,
            "elements": 0,
            "extractions": 0,
            "ancrees": 0,
            "detachees_introuvables": 0,
            "detachees_ambigues": 0,
            "commentees_ancrees": 0,
            "commentees_detachees": 0,
        }

        pages_en_erreur = []

        for page in pages_a_traiter:
            # UNE PAGE EMPOISONNEE NE COUTE PAS LEUR BASCULE AUX AUTRES.
            #
            # 542 pages a traiter : sans ce filet, la premiere levee
            # arrete tout, et la relance replante au meme endroit. La
            # page fautive est laissee ANCIEN — son atomic a fait le
            # rollback — et son numero est rapporte a la fin.
            # / One poisoned page must not cost the others their migration.
            try:
                bilan_de_la_page = self._basculer_une_page(page, a_blanc)
            except Exception as erreur:  # noqa: BLE001 — on veut TOUT retenir
                pages_en_erreur.append((page.pk, erreur))
                bilan_general["pages"] += 1
                continue

            for cle, valeur in bilan_de_la_page.items():
                bilan_general[cle] = bilan_general.get(cle, 0) + valeur
            bilan_general["pages"] += 1

            if bilan_general["pages"] % 25 == 0:
                self.stdout.write(
                    f"  ... {bilan_general['pages']}/{nombre_de_pages} pages",
                )

        self._afficher_le_bilan(bilan_general, a_blanc)
        self._afficher_les_erreurs(pages_en_erreur)

    def _expliquer_la_page_absente(self, identifiant_de_page):
        """
        Dit POURQUOI une page nommee n'a pas ete traitee.
        / Says WHY an explicitly named page was not processed.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

        Repondre « 0 page a traiter » a quelqu'un qui a nomme sa page se
        lit comme une faute de frappe. Les deux raisons possibles se
        distinguent en une requete.
        / "0 pages" on an explicit --page reads like a typo.
        """
        page = Page.objects.filter(pk=identifiant_de_page).first()
        if page is None:
            self.stdout.write(self.style.WARNING(
                f"La page {identifiant_de_page} n'existe pas.",
            ))
            return
        if page.moteur != MoteurDePage.ELEMENT:
            # Elle est bien ANCIEN : c'est autre chose qui l'a exclue de
            # la selection (--limite). Ne pas lui inventer une raison.
            # / It IS on ANCIEN; something else excluded it. Say nothing.
            return
        self.stdout.write(self.style.WARNING(
            f"La page {identifiant_de_page} est deja sur le moteur ELEMENT : "
            f"il n'y a rien a reconvertir.",
        ))

    def _afficher_les_erreurs(self, pages_en_erreur):
        """Rapporte les pages qui ont leve. / Reports pages that raised."""
        if not pages_en_erreur:
            return
        self.stdout.write("")
        self.stdout.write(self.style.ERROR(
            f"{len(pages_en_erreur)} page(s) en erreur, laissees en ANCIEN :",
        ))
        for identifiant, erreur in pages_en_erreur:
            self.stdout.write(self.style.ERROR(
                f"  page {identifiant} : {type(erreur).__name__} — {erreur}",
            ))

    def _basculer_une_page(self, page, a_blanc):
        """
        Bascule une page : lui donne des blocs, re-ancre, pose le flag.
        / Migrates one page: gives it blocks, re-anchors, stamps the flag.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

        DEUX CHEMINS, UN SEUL PRINCIPE

        Que les elements existent deja ou qu'il faille les creer, la suite
        est la meme : on a besoin de savoir OU chaque element se trouve
        dans `text_readability`, parce que c'est dans ce texte-la que les
        anciennes extractions comptent leurs offsets. Cette table de
        positions obtenue, la traduction offsets -> portions est le meme
        calcul d'intersection dans les deux cas.
        / Both paths need the same thing: where each element sits in the
        page text. After that, the translation is identical.

        ON TRADUIT LES ANCIENS OFFSETS, ON NE CHERCHE PAS LE TEXTE.

        Les anciennes extractions portent start_char et end_char : des
        positions dans text_readability, ecrites par l'alignement de
        LangExtract au moment de l'analyse. Ces positions sont FIABLES —
        verifie sur echantillon : aucune hors bornes.

        Comme les elements sont decoupes dans CE MEME texte, et qu'on note
        ou chacun commence, traduire un ancien offset en portions est un
        simple calcul d'intersection. Exactement celui que
        services/ancrage.py fait deja pour le nouveau moteur.

        Chercher le texte, comme le faisait une premiere version, etait a
        la fois inutile et moins bon : ca rejetait des ancres correctes au
        motif que le texte apparaissait ailleurs, et ca echouait sur les
        alignements partiels.
        / Translating offsets beats searching text: it is exact, and it
        does not reject correct anchors as "ambiguous".
        """
        bilan = {
            "elements": 0, "extractions": 0, "ancrees": 0,
            "detachees_introuvables": 0, "detachees_ambigues": 0,
            "detachees_discordantes": 0,
            "commentees_ancrees": 0, "commentees_detachees": 0,
            "ancrees_multi_elements": 0, "basculees": 0,
            "sans_bloc_a_lire": 0, "sans_table_de_positions": 0,
            "deja_pourvues_d_elements": 0,
            "dormantes_verifiees": 0, "dormantes_detachees": 0,
            "dormantes_detachees_commentees": 0,
        }

        # TOUT SE LIT ET S'ECRIT DANS LA MEME TRANSACTION.
        #
        # La commande tourne pendant que l'application est en service. Une
        # extraction ancree entre la lecture et l'ecriture donnerait un
        # doublon d'ancre (la contrainte est DEFERRED : l'erreur ne
        # tomberait qu'au commit, trop tard pour la page). On verrouille
        # donc la page avant de lire quoi que ce soit d'elle.
        # / Read and write in one transaction; the app is live meanwhile.
        with transaction.atomic():
            if not a_blanc:
                page = Page.objects.select_for_update().get(pk=page.pk)

            texte_de_la_page = page.text_readability or ""

            # LES ELEMENTS A TEXTE VIDE SONT ECARTES UNE FOIS POUR TOUTES.
            #
            # Ils n'occupent aucune place dans le texte, donc la table de
            # positions les saute. Les garder dans la liste passee au
            # decoupeur romprait son contrat (« liste complete => table
            # complete ») et levait un KeyError qui arretait la commande
            # au milieu des 542 pages. Une seule liste, cohérente partout.
            # / One list, consistent everywhere: no empty elements.
            tous_les_elements = list(page.elements.order_by("ordre"))
            # Un element fait d'un seul blanc n'affiche rien, exactement
            # comme un element vide — et le decoupage, lui, exige deux
            # caracteres non blancs pour en fabriquer un. Meme regle des
            # deux cotes. / Same emptiness rule as the paragraph splitter.
            elements_existants = [
                element for element in tous_les_elements
                if (element.texte or "").strip()
            ]

            # Une page qui a des elements mais AUCUN qui porte du texte ne
            # peut pas etre re-decoupee : ses numeros d'ordre sont deja
            # pris. Et basculee, elle n'aurait rien a afficher. On la
            # laisse. / Elements exist but none has text: nothing to show,
            # and the ordre numbers are taken. Leave it.
            if tous_les_elements and not elements_existants:
                bilan["sans_bloc_a_lire"] = 1
                return bilan

            positions = None
            pks_ambigus = set()
            paragraphes = None

            if elements_existants:
                bilan["deja_pourvues_d_elements"] = 1
                positions, pks_ambigus = (
                    self._retrouver_les_positions_des_elements(
                        elements_existants, texte_de_la_page,
                    )
                )
            else:
                paragraphes = self._decouper_en_paragraphes(texte_de_la_page)
                if not paragraphes:
                    # Ni bloc a lire, ni texte a decouper : basculer cette
                    # page la rendrait vide a l'ecran. On la laisse.
                    # / Nothing to read: leave it on ANCIEN.
                    bilan["sans_bloc_a_lire"] = 1
                    return bilan
                bilan["elements"] = len(paragraphes)

            # Les ancres deja posees deviennent OFFICIELLES par cette
            # bascule : on les regarde avant de la faire.
            # / Dormant anchors become official here, so check them first.
            if elements_existants:
                self._verifier_les_ancres_dormantes(page, a_blanc, bilan)

            # Les extractions dont l'ancre reste a poser. Celles qui en ont
            # deja une ne sont pas retouchees : c'est ce qui rend la
            # commande rejouable sans creer de doublon.
            #
            # Les deux questions qu'on se pose sur chaque extraction —
            # « a-t-elle une ancre ? », « est-elle commentee ? » — sont
            # posees DANS la requete. Une par extraction ferait 60 000
            # allers-retours sur la base de dev.
            # / Both questions are answered inside the query.
            extractions = list(
                ExtractedEntity.objects.filter(job__page=page)
                .annotate(
                    a_deja_une_ancre=Exists(
                        AncrageExtraction.objects.filter(
                            extraction=OuterRef("pk"),
                        ),
                    ),
                    porte_un_commentaire=Exists(
                        CommentaireExtraction.objects.filter(
                            entity=OuterRef("pk"),
                        ),
                    ),
                )
                .filter(a_deja_une_ancre=False)
                .distinct()
            )
            bilan["extractions"] = len(extractions)

            # Sans table de positions, on ne sait traduire aucun offset :
            # on ne re-ancre rien plutot que d'ancrer au jugé. Les
            # extractions restent detachees, visibles comme telles.
            # / No position table means no anchoring, rather than guesswork.
            if elements_existants and positions is None:
                bilan["sans_table_de_positions"] = 1
                for extraction in extractions:
                    self._compter(bilan, "introuvable", extraction)
                if not a_blanc:
                    self._poser_le_flag(page)
                bilan["basculees"] = 1
                return bilan

            if elements_existants:
                elements = elements_existants
                offsets_dans_la_page = positions
            elif a_blanc:
                # A blanc, les elements ne sont pas crees : on raisonne
                # sur des elements de travail, non sauvegardes, qui
                # portent le meme texte et les memes positions. C'est ce
                # qui permet au bilan a blanc de compter EXACTEMENT ce que
                # le run reel fera — y compris les ancres refusees.
                # / Unsaved stand-ins, so the dry run counts exactly right.
                elements = [
                    ElementDocument(
                        page=page, ordre=position, label="text",
                        texte=texte_du_paragraphe,
                        empreinte_contenu=empreinte_du_texte(
                            texte_du_paragraphe,
                        ),
                        pk=-(position + 1),
                    )
                    for position, (texte_du_paragraphe, _debut)
                    in enumerate(paragraphes)
                ]
                offsets_dans_la_page = {
                    element.pk: (debut, debut + len(element.texte))
                    for element, (_texte, debut)
                    in zip(elements, paragraphes)
                }
            else:
                elements = [
                    ElementDocument.objects.create(
                        page=page, ordre=position, label="text",
                        texte=texte_du_paragraphe,
                        empreinte_contenu=empreinte_du_texte(
                            texte_du_paragraphe,
                        ),
                    )
                    for position, (texte_du_paragraphe, _debut)
                    in enumerate(paragraphes)
                ]
                # La table des offsets, exprimee dans le texte de la PAGE.
                # C'est ce qui permet de croiser directement les anciens
                # start_char / end_char avec les elements.
                # / The offsets table, expressed in the PAGE's text.
                offsets_dans_la_page = {
                    element.pk: (debut, debut + len(element.texte))
                    for element, (_texte, debut)
                    in zip(elements, paragraphes)
                }

            reference = [
                (element.texte, offsets_dans_la_page[element.pk][0])
                for element in elements
            ]

            for extraction in extractions:
                resultat, portions = self._evaluer_l_extraction(
                    extraction, reference, texte_de_la_page,
                    elements, offsets_dans_la_page, pks_ambigus,
                )
                self._compter(bilan, resultat, extraction)

                if resultat != "ancree":
                    continue

                if len(portions) > 1:
                    bilan["ancrees_multi_elements"] += 1

                if a_blanc:
                    continue

                for portion in portions:
                    AncrageExtraction.objects.create(
                        extraction=extraction,
                        etat_ancrage=EtatAncrage.ANCREE,
                        **portion,
                    )

            if not a_blanc:
                self._poser_le_flag(page)
            bilan["basculees"] = 1

        return bilan

    def _evaluer_l_extraction(self, extraction, reference, texte_de_la_page,
                              elements, offsets_dans_la_page, pks_ambigus):
        """
        Decide du sort d'une extraction, et rend ses portions si elle est
        ancrable. / Decides an extraction's fate and yields its portions.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

        :return: (resultat, portions) — resultat parmi "ancree",
            "introuvable", "ambigu", "discordant"

        LES TROIS FACONS DE REFUSER UNE ANCRE

        1. « introuvable » — les offsets ne designent rien d'exploitable
           (0-0, span inverse, hors bornes, tombe dans un blanc).
        2. « ambigu » — le span vise un element dont le texte se repete
           dans la page : on ne sait pas laquelle des copies etait visee.
        3. « discordant » — le span est exploitable, mais le texte qu'il
           surlignerait n'est pas celui que l'extraction cite. C'est le
           cas le plus dangereux, parce qu'il produit une ancre d'allure
           parfaitement normale qui montre le mauvais passage.
        / Three ways to refuse: nothing to translate, ambiguous, or the
        highlighted text simply is not the quoted one.

        Cette fonction ne DECIDE que : elle n'ecrit rien. C'est ce qui
        permet au mode a blanc d'annoncer exactement ce que le run reel
        fera. / Pure decision, so the dry run cannot lie.
        """
        resultat = self._sort_de_l_extraction(
            extraction, reference, texte_de_la_page,
        )
        if resultat != "ancree":
            return resultat, []

        portions = decouper_le_span_en_portions_par_element(
            span_dans_le_chunk=(extraction.start_char, extraction.end_char),
            elements_du_chunk=elements,
            offsets_des_elements_dans_le_chunk=offsets_dans_la_page,
        )
        if not portions:
            return "introuvable", []

        if any(portion["element"].pk in pks_ambigus for portion in portions):
            return "ambigu", []

        texte_ancre = recomposer_le_texte_ancre(
            portion["element"].texte[
                portion["debut_dans_element"]:portion["fin_dans_element"]
            ]
            for portion in portions
        )
        if not l_ancre_couvre_la_citation(
            texte_ancre, extraction.extraction_text,
        ):
            return "discordant", []

        return "ancree", portions

    def _verifier_les_ancres_dormantes(self, page, a_blanc, bilan):
        """
        Detache les ancres deja posees qui designent un autre passage.
        / Detaches existing anchors that point at another passage.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

        POURQUOI CETTE PASSE EXISTE

        Les 28 096 ancres deja en base ont ete posees par d'anciennes
        phases de test et n'ont jamais ete auditees. Tant que la page
        restait ANCIEN, elles dormaient — le rendu passait par les
        offsets. La bascule les reveille et en fait la SEULE verite
        affichee. Les officialiser sans les regarder reviendrait a
        publier 1 746 surlignages faux d'un coup, dont 59 sur des
        extractions que des humains ont commentees.

        DETACHER N'EST PAS EFFACER

        L'ancre reste, l'extraction reste, le commentaire reste. Seul
        `etat_ancrage` change : l'extraction rejoint la liste des
        detachees, ou un humain tranchera. C'est reversible.
        / Detaching keeps everything; only the state changes.
        """
        extractions_ancrees = (
            ExtractedEntity.objects.filter(
                job__page=page,
                ancrages__etat_ancrage=EtatAncrage.ANCREE,
            )
            .annotate(
                porte_un_commentaire=Exists(
                    CommentaireExtraction.objects.filter(
                        entity=OuterRef("pk"),
                    ),
                ),
            )
            .prefetch_related("ancrages__element")
            .distinct()
        )

        for extraction in extractions_ancrees:
            portions = sorted(
                (
                    ancrage for ancrage in extraction.ancrages.all()
                    if ancrage.etat_ancrage == EtatAncrage.ANCREE
                ),
                key=lambda ancrage: ancrage.ordre_dans_extraction,
            )
            if not portions:
                continue

            bilan["dormantes_verifiees"] += 1
            texte_ancre = recomposer_le_texte_ancre(
                ancrage.element.texte[
                    ancrage.debut_dans_element:ancrage.fin_dans_element
                ]
                for ancrage in portions
            )
            if not l_ancre_designe_un_autre_passage(
                texte_ancre, extraction.extraction_text,
            ):
                continue

            bilan["dormantes_detachees"] += 1
            if extraction.porte_un_commentaire:
                bilan["dormantes_detachees_commentees"] += 1

            # ON NOMME CE QU'ON DETACHE.
            #
            # Un compte global ne se retrie pas. La comparaison textuelle
            # se trompe dans les deux sens a la marge, et sans les
            # numeros, les quelques ancres justes detachees a tort sont
            # indiscernables des menteuses dans le tas a trier.
            # / A bare count cannot be re-sorted; print the pks.
            self.stdout.write(
                f"    detachee : extraction {extraction.pk} "
                f"(page {page.pk})"
                + (" — COMMENTEE" if extraction.porte_un_commentaire else ""),
            )

            if a_blanc:
                continue

            AncrageExtraction.objects.filter(
                pk__in=[ancrage.pk for ancrage in portions],
            ).update(etat_ancrage=EtatAncrage.DETACHEE)

    def _poser_le_flag(self, page):
        """
        Fait passer la page sur le moteur ELEMENT.
        / Flips the page onto the ELEMENT engine.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

        On n'ecrit que ce champ : une page reconvertie garde par ailleurs
        exactement ce qu'elle avait.
        / Only this field is written.
        """
        page.moteur = MoteurDePage.ELEMENT
        page.save(update_fields=["moteur"])

    def _retrouver_les_positions_des_elements(self, elements, texte_de_la_page):
        """
        Retrouve ou chaque element se trouve dans le texte de la page.
        / Finds where each element sits in the page text.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

        :param elements: les ElementDocument, DANS L'ORDRE du document,
            AUCUN a texte vide
        :param texte_de_la_page: son text_readability
        :return: ({element.pk: (debut, fin)}, {pk des elements ambigus}).
            La table vaut None si un seul element n'a pas ete retrouve.

        LES ELEMENTS AMBIGUS SONT SIGNALES, PAS DEVINES

        Quand le texte d'un element reapparait plus loin dans la page, la
        recherche en avant retient la premiere copie — qui n'est pas
        forcement celle que l'extraction visait. Rien ne le trahit : les
        positions restent croissantes. 39 pages de la base sont dans ce
        cas. On rend donc la liste de ces elements, pour que l'appelant
        refuse d'y ancrer plutot que de choisir a pile ou face.
        / Repeated element text: flag it, never pick a copy at random.

        POURQUOI ON CHERCHE EN AVANCANT, ET JAMAIS EN ARRIERE

        Les elements se suivent dans le document. Chercher chacun a partir
        de la fin du precedent interdit deux erreurs : qu'un element court
        (« Oui. ») s'apparie a une occurrence anterieure, et qu'un element
        repete plus loin remonte au premier exemplaire venu. L'ordre du
        document sert d'arbitre, on n'a rien a deviner.
        / Searching forward from the previous match uses document order as
        the tie-breaker, so repeated short texts cannot mis-match.

        POURQUOI TOUT OU RIEN

        Un seul element introuvable, et la table est fausse pour tous ceux
        qui suivent — leurs positions auraient glisse. On rend None :
        l'appelant re-ancrera zero extraction sur cette page plutot que de
        toutes les ancrer de travers.
        / One miss invalidates every following position, so we return None.
        """
        if not texte_de_la_page:
            return None, set()

        positions = {}
        curseur = 0
        for element in elements:
            debut = texte_de_la_page.find(element.texte, curseur)
            if debut == -1:
                return None, set()
            positions[element.pk] = (debut, debut + len(element.texte))
            curseur = debut + len(element.texte)

        if not positions:
            return None, set()

        return positions, self._reperer_les_elements_ambigus(
            elements, positions, texte_de_la_page,
        )

    def _reperer_les_elements_ambigus(self, elements, positions,
                                      texte_de_la_page):
        """
        Dit quels elements auraient pu etre places ailleurs.
        / Says which elements could have been placed elsewhere.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

        :return: l'ensemble des pk dont la position n'est pas certaine

        CE QUI EST AMBIGU, ET CE QUI NE L'EST PAS

        Un texte qui se repete dans la page ne suffit PAS a rendre sa
        position incertaine. Si le refrain apparait deux fois et que DEUX
        elements le portent, l'ordre du document attribue une copie a
        chacun : rien a deviner.

        COMMENT ON LE SAIT : ON PLACE LES ELEMENTS DEUX FOIS

        Une premiere fois en partant du debut, chaque element prenant la
        premiere place libre ; une seconde en partant de la fin, chacun
        prenant la derniere. Un element que les deux lectures posent au
        MEME endroit n'avait pas le choix : sa position est certaine. Un
        element que les deux lectures separent en avait plusieurs, et
        aucune raison de preferer l'une — on refuse d'y ancrer.

        Mesurer l'ecart entre les deux lectures est la seule facon
        honnete de poser la question. Regarder la « zone libre » autour de
        la position gloutonne, comme le faisait une premiere version,
        revient a supposer les voisins bien places pour prouver que
        celui-ci l'est : sur « A B A B » avec les elements [A, B], les
        placements A1-B1 et A2-B2 se valent, et pourtant la zone de A,
        bornee par B pris gloutonnement, ne contenait qu'un seul A.
        / Place them greedily from the front, then from the back: any
        element the two passes disagree on had a choice.
        """
        positions_en_arriere = {}
        curseur = len(texte_de_la_page)
        for element in reversed(elements):
            debut = texte_de_la_page.rfind(element.texte, 0, curseur)
            if debut == -1:
                # Les deux lectures doivent aboutir pour etre comparees.
                # Sans quoi on ne sait rien, et on ne sait pas non plus
                # qu'on ne sait rien : tout est declare ambigu.
                # / Without both passes, everything is ambiguous.
                return {element.pk for element in elements}
            positions_en_arriere[element.pk] = debut
            curseur = debut

        return {
            element.pk
            for element in elements
            if positions[element.pk][0] != positions_en_arriere[element.pk]
        }

    def _sort_de_l_extraction(self, extraction, paragraphes, texte_de_la_page):
        """
        Dit si une extraction peut etre re-ancree par ses offsets.
        / Says whether an extraction can be re-anchored by its offsets.

        :return: "ancree", "introuvable" ou "ambigu"

        Une extraction a 0-0 n'a jamais ete alignee : l'ancien moteur
        ecrivait ces valeurs quand LangExtract ne retrouvait pas le
        passage. Il n'y a rien a traduire.
        / A 0-0 extraction was never aligned; there is nothing to translate.
        """
        debut, fin = extraction.start_char, extraction.end_char

        if (debut, fin) == (0, 0):
            return "introuvable"
        if fin <= debut:
            return "introuvable"
        if fin > len(texte_de_la_page):
            return "introuvable"

        # Le span doit recouper au moins un paragraphe retenu. Un span qui
        # tombe entierement entre deux paragraphes — dans un blanc — n'a
        # rien a ancrer. / A span falling entirely between paragraphs.
        for _texte, debut_du_paragraphe in paragraphes:
            fin_du_paragraphe = debut_du_paragraphe + len(_texte)
            if min(fin, fin_du_paragraphe) > max(debut, debut_du_paragraphe):
                return "ancree"
        return "introuvable"

    def _decouper_en_paragraphes(self, texte):
        """
        Decoupe un texte plat en paragraphes, EN NOTANT leurs positions.
        / Splits flat text into paragraphs, RECORDING their positions.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

        :param texte: le text_readability de la page
        :return: liste de (texte_du_paragraphe, debut_dans_la_page)

        POURQUOI ON NOTE LES POSITIONS

        C'est toute la difference entre une bascule approximative et une
        bascule exacte. Les anciennes extractions portent des offsets dans
        CE texte : en sachant ou commence chaque paragraphe, on peut
        traduire ces offsets en portions, sans rien chercher ni deviner.
        / Knowing where each paragraph starts turns old offsets into
        portions, with no searching and no guessing.
        """
        paragraphes = []
        position_courante = 0
        for morceau in SEPARATEUR_DE_PARAGRAPHE.split(texte):
            # On retrouve la position exacte du morceau dans le texte
            # d'origine, en tenant compte de ce que le split a mange.
            # / Find the morsel's exact position in the original text.
            debut = texte.find(morceau, position_courante)
            if debut == -1:
                debut = position_courante
            position_courante = debut + len(morceau)

            morceau_nettoye = morceau.strip()
            if len(morceau_nettoye) < LONGUEUR_MINIMALE_D_UN_ELEMENT:
                continue

            # Le strip() a pu retirer des espaces en tete : on decale la
            # position d'autant. / strip() may have removed leading spaces.
            decalage_du_strip = len(morceau) - len(morceau.lstrip())
            paragraphes.append((morceau_nettoye, debut + decalage_du_strip))

        return paragraphes

    def _compter(self, bilan, resultat, extraction):
        """Range le resultat dans le bilan. / Files the result in the report."""
        # L'annotation vient de la requete de selection ; le repli sert
        # aux appels hors de ce flux. / Annotation first, query as fallback.
        elle_est_commentee = getattr(
            extraction, "porte_un_commentaire", None,
        )
        if elle_est_commentee is None:
            elle_est_commentee = extraction.commentaires.exists()

        if resultat == "ancree":
            bilan["ancrees"] += 1
            if elle_est_commentee:
                bilan["commentees_ancrees"] += 1
            return

        if resultat == "ambigu":
            bilan["detachees_ambigues"] += 1
        elif resultat == "discordant":
            bilan["detachees_discordantes"] += 1
        else:
            bilan["detachees_introuvables"] += 1
        if elle_est_commentee:
            bilan["commentees_detachees"] += 1

    def _afficher_le_bilan(self, bilan, a_blanc):
        """Affiche le bilan de la bascule. / Prints the migration report."""
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            "BILAN DE LA BASCULE" + (" (A BLANC)" if a_blanc else ""),
        )
        self.stdout.write("=" * 70)
        self.stdout.write(f"Pages traitees        : {bilan['pages']}")
        self.stdout.write(
            f"  basculees en ELEMENT: {bilan.get('basculees', 0)}",
        )
        self.stdout.write(
            f"  dont deja pourvues  : "
            f"{bilan.get('deja_pourvues_d_elements', 0)}",
        )
        self.stdout.write(
            f"  laissees en ANCIEN  : {bilan.get('sans_bloc_a_lire', 0)} "
            f"(aucun bloc a lire)",
        )
        self.stdout.write(
            f"  sans re-ancrage     : "
            f"{bilan.get('sans_table_de_positions', 0)} "
            f"(positions des elements introuvables)",
        )
        self.stdout.write(f"Elements crees        : {bilan['elements']}")
        self.stdout.write(
            f"Extractions a ancrer  : {bilan['extractions']}",
        )
        self.stdout.write("")
        self.stdout.write(f"  re-ancrees          : {bilan['ancrees']}")
        self.stdout.write(
            f"    dont multi-elements : "
            f"{bilan.get('ancrees_multi_elements', 0)}",
        )
        self.stdout.write(
            f"  detachees (absent)  : {bilan['detachees_introuvables']}",
        )
        self.stdout.write(
            f"  detachees (ambigu)  : {bilan['detachees_ambigues']}",
        )
        self.stdout.write(
            f"  detachees (discord.): "
            f"{bilan.get('detachees_discordantes', 0)} "
            f"(le span ne montre pas la citation)",
        )

        if bilan["extractions"]:
            part_ancree = 100 * bilan["ancrees"] / bilan["extractions"]
            self.stdout.write(f"  soit {part_ancree:.1f} % de re-ancrage")

        self.stdout.write("")
        self.stdout.write(
            "ANCRES DEJA EN BASE — devenues officielles par la bascule :",
        )
        self.stdout.write(
            f"  verifiees           : {bilan.get('dormantes_verifiees', 0)}",
        )
        self.stdout.write(
            f"  DETACHEES (fausses) : "
            f"{bilan.get('dormantes_detachees', 0)} "
            f"(dont commentees : "
            f"{bilan.get('dormantes_detachees_commentees', 0)})",
        )
        self.stdout.write(
            "  Detachees, pas effacees : l'extraction et son commentaire "
            "restent.",
        )

        self.stdout.write("")
        self.stdout.write("EXTRACTIONS COMMENTEES — les plus precieuses :")
        self.stdout.write(
            f"  re-ancrees          : {bilan['commentees_ancrees']}",
        )
        self.stdout.write(
            f"  detachees           : {bilan['commentees_detachees']}",
        )
        self.stdout.write("")
        self.stdout.write(
            "Aucune extraction ni aucun commentaire n'a ete supprime.",
        )
        if a_blanc:
            self.stdout.write(self.style.WARNING(
                "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
            ))
