"""
Compare le decoupage en chunks des deux moteurs, sans appel LLM.
/ Compares both engines' chunking, with no LLM call.

LOCALISATION : scripts/comparer_les_decoupages.py

POURQUOI UN SCRIPT SEPARE

Le decoupage est deterministe : il ne depend pas de ce que le modele
repond. On peut donc le mesurer sur des documents longs sans depenser un
centime, et repeter la mesure autant de fois qu'on veut.

C'est la moitie de la comparaison qui n'a pas besoin d'argent. L'autre
moitie — la justesse des ancres — est dans
scripts/comparer_les_deux_moteurs.py.

LANCER LE SCRIPT

    docker exec hypostasia_dev_web uv run python \\
        scripts/comparer_les_decoupages.py
"""

import os
import sys

import django

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
django.setup()

from core.models import ElementDocument, Page, empreinte_du_texte  # noqa: E402
from hypostasis_extractor.services.chunking import (  # noqa: E402
    BUDGET_MAXIMUM_PAR_CHUNK,
    construire_les_chunks,
)

SEPARATEUR = "\n\n"


def fabriquer_un_document_long(modele_d_elements, repetitions):
    """
    Repete un motif d'elements pour atteindre une taille reelle.
    / Repeats an element pattern to reach a realistic size.
    """
    elements = []
    for numero_de_tour in range(repetitions):
        for texte in modele_d_elements:
            elements.append(f"[{numero_de_tour + 1}] {texte}")
    return elements


DOCUMENTS = [
    {
        "nom": "Transcription longue (conseil de 2 h)",
        "elements": fabriquer_un_document_long([
            "Marie : Je pense qu'on va trop vite sur ce dossier, et je "
            "voudrais qu'on prenne le temps de l'expliquer aux equipes.",
            "Jonas : On a deja repousse deux fois, a un moment il faut "
            "trancher sinon on ne fera jamais rien.",
            "Amina : On decide pour des gens qui ne sont pas dans la piece.",
            "Pierre : On repousse d'une semaine et on les invite.",
        ], repetitions=8),
    },
    {
        "nom": "Compte-rendu de 12 points",
        "elements": fabriquer_un_document_long([
            "Point : la gouvernance des decisions engageantes",
            "Le conseil decide que les decisions engageant plus de dix mille "
            "euros seront prises en assemblee generale, et non plus en bureau "
            "restreint. Marie souligne que ce seuil doit etre reevalue chaque "
            "annee, faute de quoi il perdra son sens avec l'inflation.",
        ], repetitions=6),
    },
    {
        "nom": "Document dense (chapitre)",
        "elements": fabriquer_un_document_long([
            "La gouvernance des communs repose sur huit principes degages par "
            "Elinor Ostrom a partir de l'observation de centaines de cas "
            "reels. Le premier exige des limites claires : on doit savoir qui "
            "fait partie du groupe et ce qui appartient au commun. Sans cette "
            "frontiere, personne ne peut dire qui abuse ni de quoi.",
        ], repetitions=7),
    },
]


def decoupage_aveugle(elements, budget):
    """
    Simule le decoupage du moteur ANCIEN et compte les degats.
    / Simulates the OLD engine's cut and counts the damage.

    Le moteur ANCIEN colle tout le texte de la page, puis laisse
    LangExtract couper tous les `budget` caracteres, sans regarder ou
    commencent et finissent les paragraphes.
    / The OLD engine cuts every `budget` characters, blind to paragraphs.
    """
    texte_colle = SEPARATEUR.join(elements)
    positions_de_coupure = list(range(budget, len(texte_colle), budget))

    elements_coupes = []
    position_courante = 0
    for numero, texte in enumerate(elements):
        debut = position_courante
        fin = debut + len(texte)
        for coupure in positions_de_coupure:
            if debut < coupure < fin:
                elements_coupes.append({
                    "numero": numero,
                    "avant_la_coupe": texte_colle[debut:coupure][-45:],
                    "apres_la_coupe": texte_colle[coupure:fin][:45],
                })
                break
        position_courante = fin + len(SEPARATEUR)

    return len(positions_de_coupure) + 1, elements_coupes


def main():
    print("=" * 78)
    print("COMPARAISON DES DECOUPAGES — sans appel LLM")
    print(f"Budget par chunk : {BUDGET_MAXIMUM_PAR_CHUNK} caracteres")
    print("=" * 78)

    total_coupes = 0
    for document in DOCUMENTS:
        page = Page.objects.create(
            url=f"http://banc.local/decoupage-{document['nom'][:20]}",
            html_original="x", html_readability="x", text_readability="x",
            content_hash=f"decoupage_{document['nom'][:30]}",
        )
        elements_crees = [
            ElementDocument.objects.create(
                page=page, ordre=numero, label="text", texte=texte,
                empreinte_contenu=empreinte_du_texte(texte),
            )
            for numero, texte in enumerate(document["elements"])
        ]

        try:
            chunks_element = construire_les_chunks(elements_crees)
            chunks_ancien, elements_coupes = decoupage_aveugle(
                document["elements"], BUDGET_MAXIMUM_PAR_CHUNK,
            )
            total_coupes += len(elements_coupes)

            taille_totale = sum(len(t) for t in document["elements"])
            print(f"\n>>> {document['nom']}")
            print(
                f"    {len(document['elements'])} elements, "
                f"{taille_totale} caracteres"
            )
            print(
                f"    chunks : ELEMENT {len(chunks_element)} | "
                f"ANCIEN {chunks_ancien}   "
                f"(surcout : {len(chunks_element) - chunks_ancien} appel(s))"
            )
            print(
                f"    elements coupes en deux : "
                f"ELEMENT 0 | ANCIEN {len(elements_coupes)}"
            )

            # Verification de l'invariant du moteur ELEMENT.
            # / Check the ELEMENT engine's invariant.
            for chunk in chunks_element:
                for element in chunk["elements"]:
                    assert element.texte in chunk["texte"], (
                        "INVARIANT ROMPU : un element n'est pas entier "
                        "dans son chunk"
                    )
                assert len(chunk["texte"]) <= BUDGET_MAXIMUM_PAR_CHUNK or (
                    len(chunk["elements"]) == 1
                ), "INVARIANT ROMPU : chunk hors budget a plusieurs elements"

            if elements_coupes:
                exemple = elements_coupes[0]
                print(f"\n    Exemple de degat du moteur ANCIEN :")
                print(f"      element {exemple['numero']} coupe en plein milieu")
                print(f"      le LLM lit  : ...{exemple['avant_la_coupe']!r}")
                print(f"      puis, plus tard, dans un AUTRE appel, sans le "
                      f"contexte de ce qui precede :")
                print(f"                    {exemple['apres_la_coupe']!r}...")
        finally:
            page.elements.all().delete()
            page.delete()

    print("\n" + "=" * 78)
    print("BILAN")
    print("=" * 78)
    print(f"Elements coupes en deux — ANCIEN  : {total_coupes}")
    print(f"Elements coupes en deux — ELEMENT : 0")
    print()
    print("Un element coupe en deux, c'est un modele qui lit une demi-phrase")
    print("dans un appel, et la suite dans un autre, sans le contexte du")
    print("premier. Il complete alors de lui-meme ce qu'il n'a pas lu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
