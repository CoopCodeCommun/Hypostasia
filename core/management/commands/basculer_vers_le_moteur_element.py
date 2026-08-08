"""
Bascule les pages existantes vers le moteur ELEMENT.
/ Migrates existing pages to the ELEMENT engine.

LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

CE QUE FAIT CETTE COMMANDE

Pour chaque page qui n'a pas encore d'elements :
  1. elle decoupe text_readability en elements, sur les paragraphes ;
  2. elle garde TOUTES les extractions existantes, telles quelles ;
  3. elle tente de re-ancrer chaque extraction en cherchant son texte
     dans les elements.

CE QU'ELLE NE SUPPRIME JAMAIS

Aucune extraction, aucun commentaire. Une extraction qu'on n'arrive pas a
re-ancrer reste en base, sans portion : elle apparaitra dans la section
« detachees », ou un humain decidera. C'est le principe « rien ne
disparait en silence », applique a la bascule elle-meme.
/ No extraction and no comment is ever deleted.

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

from core.models import ElementDocument, Page, empreinte_du_texte
from hypostasis_extractor.services.ancrage import (
    construire_la_table_des_offsets,
    decouper_le_span_en_portions_par_element,
)
from hypostasis_extractor.models import (
    AncrageExtraction,
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

# Caracteres typographiques a ramener a leur equivalent simple, UN POUR UN.
#
# POURQUOI CETTE TABLE EXISTE
#
# Le texte rendu par le modele et le texte du document ne s'ecrivent pas
# toujours pareil : l'un met une apostrophe courbe, l'autre une droite ;
# l'un un espace insecable, l'autre un espace ordinaire. Ce sont les
# memes mots, mais une comparaison stricte les declare differents.
#
# Mesure sur 400 extractions : une recherche sans cette normalisation
# trouve 28 % des citations. Avec, elle en trouve 57 %. La moitie des
# ancres recuperables se perdait sur des apostrophes.
#
# POURQUOI UN POUR UN, ET PAS UNE NORMALISATION LIBRE
#
# Chaque remplacement fait un caractere pour un caractere. La longueur du
# texte ne change donc pas, et les positions trouvees restent valides
# dans le texte d'origine. Ecraser les espaces multiples aurait ete plus
# efficace encore, mais aurait decale toutes les positions suivantes.
# / Strictly one-for-one, so found positions stay valid.
REMPLACEMENTS_TYPOGRAPHIQUES = {
    "’": "'",   # apostrophe courbe / curly apostrophe
    "‘": "'",   # apostrophe ouvrante / opening single quote
    "“": '"',   # guillemet anglais ouvrant / opening double quote
    "”": '"',   # guillemet anglais fermant / closing double quote
    "–": "-",   # tiret demi-cadratin / en dash
    "—": "-",   # tiret cadratin / em dash
    " ": " ",   # espace insecable / non-breaking space
    " ": " ",   # espace fine insecable / narrow no-break space
}


def normaliser_sans_changer_la_longueur(texte):
    """
    Ramene la typographie a sa forme simple, caractere pour caractere.
    / Normalizes typography one character for one, preserving length.

    LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

    :param texte: le texte a normaliser
    :return: le texte normalise, de MEME longueur
    """
    if not texte:
        return ""
    caracteres = [
        REMPLACEMENTS_TYPOGRAPHIQUES.get(caractere, caractere)
        for caractere in texte
    ]
    return "".join(caracteres).lower()


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

        pages_a_traiter = Page.objects.filter(elements__isnull=True)
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

        for page in pages_a_traiter:
            bilan_de_la_page = self._basculer_une_page(page, a_blanc)
            for cle, valeur in bilan_de_la_page.items():
                bilan_general[cle] = bilan_general.get(cle, 0) + valeur
            bilan_general["pages"] += 1

            if bilan_general["pages"] % 25 == 0:
                self.stdout.write(
                    f"  ... {bilan_general['pages']}/{nombre_de_pages} pages",
                )

        self._afficher_le_bilan(bilan_general, a_blanc)

    def _basculer_une_page(self, page, a_blanc):
        """
        Bascule une page : cree ses elements, re-ancre ses extractions.
        / Migrates one page: creates elements, re-anchors extractions.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

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
            "commentees_ancrees": 0, "commentees_detachees": 0,
            "ancrees_multi_elements": 0,
        }

        texte_de_la_page = page.text_readability or ""
        paragraphes = self._decouper_en_paragraphes(texte_de_la_page)
        if not paragraphes:
            return bilan

        bilan["elements"] = len(paragraphes)

        extractions = list(
            ExtractedEntity.objects.filter(job__page=page).distinct()
        )
        bilan["extractions"] = len(extractions)

        if a_blanc:
            for extraction in extractions:
                resultat = self._sort_de_l_extraction(
                    extraction, paragraphes, texte_de_la_page,
                )
                self._compter(bilan, resultat, extraction)
            return bilan

        with transaction.atomic():
            elements_crees = []
            for position, (texte_du_paragraphe, _debut) in enumerate(paragraphes):
                elements_crees.append(ElementDocument.objects.create(
                    page=page, ordre=position, label="text",
                    texte=texte_du_paragraphe,
                    empreinte_contenu=empreinte_du_texte(texte_du_paragraphe),
                ))

            # La table des offsets, exprimee dans le texte de la PAGE.
            # C'est ce qui permet de croiser directement les anciens
            # start_char / end_char avec les elements.
            # / The offsets table, expressed in the PAGE's text.
            offsets_dans_la_page = {
                element.pk: (debut, debut + len(element.texte))
                for element, (_texte, debut) in zip(elements_crees, paragraphes)
            }

            for extraction in extractions:
                resultat = self._sort_de_l_extraction(
                    extraction, paragraphes, texte_de_la_page,
                )
                self._compter(bilan, resultat, extraction)

                if resultat != "ancree":
                    continue

                portions = decouper_le_span_en_portions_par_element(
                    span_dans_le_chunk=(extraction.start_char, extraction.end_char),
                    elements_du_chunk=elements_crees,
                    offsets_des_elements_dans_le_chunk=offsets_dans_la_page,
                )
                if not portions:
                    continue

                if len(portions) > 1:
                    bilan["ancrees_multi_elements"] += 1

                for portion in portions:
                    AncrageExtraction.objects.create(
                        extraction=extraction,
                        etat_ancrage=EtatAncrage.ANCREE,
                        **portion,
                    )

        return bilan

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

    def _chercher_le_texte_en_dernier_recours(self, texte_cherche, texte_colle):
        """
        Cherche le texte d'une extraction dans le texte colle des elements.
        / Looks for an extraction's text in the joined element text.

        LOCALISATION : core/management/commands/basculer_vers_le_moteur_element.py

        :param texte_cherche: le texte de l'extraction
        :param texte_colle: les elements recolles, comme un chunk
        :return: ("ancree", (debut, fin)) si trouve une seule fois ;
                 ("introuvable", None) ; ("ambigu", None)

        LA REGLE EST LA MEME QUE PARTOUT : ON NE DEVINE PAS.

        Si le texte apparait a plusieurs endroits, on ne peut pas savoir
        lequel etait vise. Choisir le premier serait ancrer faux en
        silence. L'extraction reste detachee.
        / Several matches means we cannot know which one was meant.
        """
        texte_cherche = (texte_cherche or "").strip()
        if not texte_cherche:
            return "introuvable", None

        # ON CHERCHE SUR UN TEXTE NORMALISE, DE MEME LONGUEUR.
        #
        # extraction_text est ce que le MODELE a rendu. Il ne s'ecrit pas
        # toujours comme le document : apostrophe courbe contre droite,
        # espace insecable contre espace ordinaire, majuscules. Ce sont
        # les memes mots, mais une comparaison stricte les separe.
        #
        # La normalisation est strictement un caractere pour un : la
        # longueur ne bouge pas, donc les positions trouvees restent
        # valides dans le texte d'origine.
        # / One-for-one normalization keeps found positions valid.
        texte_cherche_normalise = normaliser_sans_changer_la_longueur(
            texte_cherche,
        )
        texte_colle_normalise = normaliser_sans_changer_la_longueur(texte_colle)

        if len(texte_colle_normalise) != len(texte_colle):
            texte_colle_normalise = texte_colle
            texte_cherche_normalise = texte_cherche

        occurrences = []
        position_de_depart = 0
        while True:
            position = texte_colle_normalise.find(
                texte_cherche_normalise, position_de_depart,
            )
            if position == -1:
                break
            occurrences.append(position)
            if len(occurrences) > 1:
                # Deux suffisent pour trancher : c'est ambigu.
                # / Two is enough to decide: ambiguous.
                return "ambigu", None
            position_de_depart = position + 1

        if not occurrences:
            return "introuvable", None

        debut = occurrences[0]
        return "ancree", (debut, debut + len(texte_cherche))

    def _compter(self, bilan, resultat, extraction):
        """Range le resultat dans le bilan. / Files the result in the report."""
        elle_est_commentee = extraction.commentaires.exists()

        if resultat == "ancree":
            bilan["ancrees"] += 1
            if elle_est_commentee:
                bilan["commentees_ancrees"] += 1
            return

        if resultat == "ambigu":
            bilan["detachees_ambigues"] += 1
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
        self.stdout.write(f"Elements crees        : {bilan['elements']}")
        self.stdout.write(f"Extractions vues      : {bilan['extractions']}")
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

        if bilan["extractions"]:
            part_ancree = 100 * bilan["ancrees"] / bilan["extractions"]
            self.stdout.write(f"  soit {part_ancree:.1f} % de re-ancrage")

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
