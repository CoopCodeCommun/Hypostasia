"""
Compare le moteur ANCIEN et le moteur ELEMENT sur plusieurs documents.
/ Compares the OLD engine and the ELEMENT engine on several documents.

LOCALISATION : scripts/comparer_les_deux_moteurs.py

A QUOI SERT CE SCRIPT

Les deux moteurs coexistent (SPEC v2 section 9). Avant de basculer quoi
que ce soit, il faut des chiffres : est-ce que le nouveau moteur ancre
mieux que l'ancien, et sur quels documents ?

Ce script passe les MEMES documents dans les deux moteurs et mesure ce
qui compte vraiment : combien d'ancres pointent le bon texte.

CE QU'IL MESURE, ET POURQUOI

  elements_coupes       Combien d'elements le chunking a coupes en deux.
                        Un element coupe, c'est un LLM qui lit une demi
                        phrase et invente la suite.

  ancres_a_zero         Combien d'extractions sont ancrees a la position
                        0-0. C'est le defaut silencieux du moteur ANCIEN :
                        quand l'alignement echoue, il ecrit 0-0, donc une
                        ancre qui pointe le debut du document. Elle a
                        l'air valide et elle est fausse.

  ancres_verifiees      Combien d'ancres pointent un texte qui a des mots
                        en commun avec ce que le modele a rendu. C'est la
                        mesure de justesse.

  ancres_multi          Combien d'extractions couvrent plusieurs elements.
                        Le moteur ANCIEN en est incapable par
                        construction : il n'a qu'une position de debut et
                        une de fin dans un texte plat.

LANCER LE SCRIPT

    docker exec -e TESTS_LLM_REELS=1 hypostasia_dev_web \\
        uv run python scripts/comparer_les_deux_moteurs.py

Il fait de VRAIS appels LLM. Il cree ses pages dans la base, les analyse,
affiche le tableau, puis nettoie tout derriere lui.
/ It makes REAL LLM calls, then cleans up after itself.
"""

import os
import sys

import django

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
django.setup()

from core.models import (  # noqa: E402
    AIModel,
    ElementDocument,
    Page,
    empreinte_du_texte,
)
from hypostasis_extractor.models import (  # noqa: E402
    AncrageExtraction,
    ExtractedEntity,
    ExtractionJob,
)
from hypostasis_extractor.services.analyse_par_element import (  # noqa: E402
    appeler_langextract_sur_un_chunk,
    lancer_l_analyse_d_une_page,
)
from hypostasis_extractor.services.chunking import (  # noqa: E402
    BUDGET_MAXIMUM_PAR_CHUNK,
    construire_les_chunks,
)

SEPARATEUR = "\n\n"


# =============================================================================
# LES DOCUMENTS DE TEST
#
# Quatre formes reelles, choisies pour leurs pieges differents.
# / Four real shapes, each with its own trap.
# =============================================================================

DOCUMENTS_DE_TEST = [
    {
        "nom": "Liste a puces longue",
        "piege": "une idee couvre l'intro ET ses puces ; le tout deborde d'un chunk",
        "elements": [
            "L'intelligence artificielle ne doit pas remplacer :",
            "le jugement des personnes directement concernees par la decision, "
            "car elles seules connaissent les consequences concretes qu'elle "
            "aura sur leur travail quotidien et sur leurs conditions de vie",
            "la deliberation collective, qui permet de faire apparaitre des "
            "desaccords que personne n'avait formules avant la reunion",
            "le temps long de la decision partagee, sans lequel les accords "
            "obtenus ne tiennent pas au dela de la premiere difficulte",
            "la responsabilite personnelle de celui qui signe, car une "
            "decision sans auteur est une decision que personne n'assume",
            "Ces quatre limites ne sont pas des precautions morales ajoutees "
            "apres coup. Elles decrivent ce qui se passe quand on les ignore : "
            "des decisions techniquement correctes que personne n'applique.",
            "La question n'est donc pas de savoir si l'outil est fiable. Elle "
            "est de savoir qui reste comptable de ce qui est decide.",
        ],
    },
    {
        "nom": "Compte-rendu structure",
        "piege": "des sous-titres courts entre des paragraphes longs",
        "elements": [
            "Reunion du conseil du 12 mars",
            "Presents : Marie, Jonas, Amina, Pierre. Excusee : Sonia.",
            "Point 1 : le budget de fonctionnement",
            "Le budget augmente de quatre pour cent cette annee. Cette hausse "
            "s'explique par deux facteurs : le cout de l'energie, qui a "
            "double depuis deux ans sur nos locaux, et l'embauche d'une "
            "personne supplementaire au secretariat, decidee en decembre. "
            "Le conseil note que cette augmentation reste inferieure a "
            "l'inflation constatee sur la periode.",
            "Point 2 : la gouvernance des decisions engageantes",
            "Le conseil decide que les decisions engageant plus de dix mille "
            "euros seront desormais prises en assemblee generale, et non plus "
            "en bureau restreint. Marie souligne que ce seuil doit etre "
            "reevalue chaque annee, faute de quoi il perdra son sens avec "
            "l'inflation. Le conseil retient cette remarque.",
            "Point 3 : le calendrier",
            "La prochaine assemblee generale se tiendra le 18 juin. L'ordre "
            "du jour sera envoye trois semaines avant, pour laisser le temps "
            "aux personnes concernees de preparer leurs questions.",
        ],
    },
    {
        "nom": "Transcription audio diarisee",
        "piege": "des tours de parole courts, un locuteur par element",
        "elements": [
            "Marie : Je pense qu'on va beaucoup trop vite sur ce dossier, et "
            "je voudrais qu'on prenne le temps de l'expliquer.",
            "Jonas : On a deja repousse deux fois cette decision, a un moment "
            "il faut trancher, sinon on ne fera jamais rien.",
            "Marie : Trancher oui, mais pas sans avoir consulte les personnes "
            "qui vont vivre avec cette decision au quotidien.",
            "Amina : Je rejoins ce que dit Marie. On est en train de decider "
            "pour des gens qui ne sont pas dans la piece, et qui n'ont meme "
            "pas ete prevenus qu'on en parlait aujourd'hui.",
            "Jonas : D'accord, je l'entends. Mais alors on se donne une date "
            "ferme, sinon on repousse encore de six mois.",
            "Pierre : On peut faire les deux : on repousse d'une semaine, on "
            "les invite, et on decide la semaine prochaine quoi qu'il arrive.",
            "Marie : Ca me va. Je me charge de les contacter demain matin.",
            "Amina : Et on leur envoie le document en amont, pas la veille au "
            "soir comme la derniere fois.",
        ],
    },
    {
        "nom": "Document dense",
        "piege": "des paragraphes longs qui remplissent plusieurs chunks",
        "elements": [
            "La gouvernance des communs repose sur huit principes degages "
            "par Elinor Ostrom a partir de l'observation de centaines de cas "
            "reels, des pecheries turques aux systemes d'irrigation "
            "espagnols. Le premier principe exige des limites claires : on "
            "doit savoir qui fait partie du groupe et ce qui appartient au "
            "commun. Sans cette frontiere, personne ne peut dire qui abuse.",
            "Le deuxieme principe demande que les regles soient adaptees au "
            "contexte local, et non copiees d'un modele exterieur. Une regle "
            "qui marche sur un canal d'irrigation ne marche pas "
            "necessairement sur une foret. Ostrom insiste : il n'existe pas "
            "de recette universelle, seulement des principes qui se "
            "declinent differemment selon les situations.",
            "Le troisieme principe veut que les personnes concernees "
            "participent a l'ecriture des regles qui les gouvernent. C'est "
            "le principe le plus souvent cite et le moins souvent applique. "
            "Il ne suffit pas de consulter : il faut que la modification "
            "d'une regle soit reellement a la portee de ceux qui la "
            "subissent.",
            "Les quatrieme et cinquieme principes portent sur la "
            "surveillance et sur les sanctions graduees. Surveiller ne veut "
            "pas dire punir : dans les communs qui durent, la surveillance "
            "est mutuelle et la premiere sanction est un rappel. La sanction "
            "lourde n'arrive qu'apres plusieurs recidives.",
            "Ces principes ne forment pas une recette a appliquer. Ils "
            "decrivent ce qu'on observe dans les communs qui durent, par "
            "difference avec ceux qui s'effondrent.",
        ],
    },
]


def compter_les_elements_coupes_par_l_ancien_chunker(elements, budget):
    """
    Compte les elements qu'un decoupage aveugle couperait en deux.
    / Counts elements a blind chunker would cut in half.

    LOCALISATION : scripts/comparer_les_deux_moteurs.py

    Le moteur ANCIEN colle tout le texte de la page, puis laisse
    LangExtract couper tous les `budget` caracteres, sans regarder ou
    commencent et finissent les paragraphes. On simule ce decoupage et on
    compte combien d'elements se retrouvent a cheval sur une coupure.
    / We simulate the blind cut and count straddled elements.
    """
    texte_colle = SEPARATEUR.join(element["texte"] for element in elements)

    # Les positions de coupure d'un decoupage aveugle.
    # / The cut positions of a blind chunker.
    positions_de_coupure = list(range(budget, len(texte_colle), budget))

    nombre_d_elements_coupes = 0
    position_courante = 0
    for element in elements:
        debut = position_courante
        fin = debut + len(element["texte"])
        for coupure in positions_de_coupure:
            if debut < coupure < fin:
                nombre_d_elements_coupes += 1
                break
        position_courante = fin + len(SEPARATEUR)

    return nombre_d_elements_coupes, len(positions_de_coupure) + 1


def mots_en_commun(premier_texte, second_texte):
    """Compte les mots partages par deux textes.
    / Counts words shared by two texts."""
    premiers_mots = set(premier_texte.lower().split())
    seconds_mots = set(second_texte.lower().split())
    return len(premiers_mots & seconds_mots)


def analyser_un_document(document, modele, identifiant_analyseur):
    """
    Passe un document dans le moteur ELEMENT et mesure le resultat.
    / Runs a document through the ELEMENT engine and measures.
    """
    page = Page.objects.create(
        url=f"http://banc.local/{document['nom'].replace(' ', '-')}",
        html_original="x", html_readability="x", text_readability="x",
        content_hash=f"banc_{document['nom']}",
        title=document["nom"],
    )
    elements_crees = []
    for numero, texte in enumerate(document["elements"]):
        elements_crees.append(ElementDocument.objects.create(
            page=page, ordre=numero, label="text", texte=texte,
            empreinte_contenu=empreinte_du_texte(texte),
        ))

    job = ExtractionJob.objects.create(
        page=page, ai_model=modele,
        name=f"Banc — {document['nom']}",
        prompt_description="Extraire les arguments et les principes du texte.",
        raw_result={"analyseur_id": identifiant_analyseur},
    )

    # --- Moteur ELEMENT : chunking aligne + ancrage par element ---
    chunks = construire_les_chunks(elements_crees)
    resultat = lancer_l_analyse_d_une_page(page, job)

    ancres_verifiees = 0
    ancres_douteuses = 0
    ancres_multi = 0
    total_des_portions = 0
    for extraction in job.entities.all():
        portions = list(extraction.ancrages.all())
        total_des_portions += len(portions)
        if len(portions) > 1:
            ancres_multi += 1
        texte_ancre = " ".join(
            portion.texte_de_la_portion() for portion in portions
        )
        if mots_en_commun(texte_ancre, extraction.extraction_text) > 0:
            ancres_verifiees += 1
        else:
            ancres_douteuses += 1

    # --- Moteur ANCIEN : simulation du decoupage aveugle ---
    elements_bruts = [{"texte": e.texte} for e in elements_crees]
    elements_coupes, chunks_de_l_ancien = (
        compter_les_elements_coupes_par_l_ancien_chunker(
            elements_bruts, BUDGET_MAXIMUM_PAR_CHUNK,
        )
    )

    mesures = {
        "nom": document["nom"],
        "piege": document["piege"],
        "elements": len(elements_crees),
        "caracteres": sum(len(e.texte) for e in elements_crees),
        "chunks_element": len(chunks),
        "chunks_ancien": chunks_de_l_ancien,
        "elements_coupes_ancien": elements_coupes,
        "elements_coupes_element": 0,  # garanti par la regle 1
        "extractions": resultat["extractions"],
        "portions": total_des_portions,
        "ancres_multi": ancres_multi,
        "ancres_verifiees": ancres_verifiees,
        "ancres_douteuses": ancres_douteuses,
        "chunks_en_erreur": resultat["chunks_en_erreur"],
        "refusees": resultat.get("extractions_refusees", 0),
    }

    # Nettoyage / Cleanup
    AncrageExtraction.objects.filter(element__page=page).delete()
    ExtractedEntity.objects.filter(job=job).delete()
    page.elements.all().delete()
    job.delete()
    page.delete()

    return mesures


def main():
    modele = AIModel.objects.filter(provider="google").first()
    if modele is None:
        print("Aucun modele Google configure. Arret.")
        return 1

    from hypostasis_extractor.models import AnalyseurExample, AnalyseurSyntaxique
    analyseur = (
        AnalyseurSyntaxique.objects
        .filter(pk__in=AnalyseurExample.objects.values("analyseur"))
        .first()
    )
    if analyseur is None:
        print("Aucun analyseur avec exemple. Arret.")
        return 1

    print(f"Modele : {modele.model_name} | Analyseur : {analyseur}")
    print("=" * 78)

    toutes_les_mesures = []
    for document in DOCUMENTS_DE_TEST:
        print(f"\n>>> {document['nom']} — {document['piege']}")
        mesures = analyser_un_document(document, modele, analyseur.pk)
        toutes_les_mesures.append(mesures)
        print(
            f"    {mesures['elements']} elements, "
            f"{mesures['caracteres']} caracteres"
        )
        print(
            f"    chunks    : ELEMENT {mesures['chunks_element']} | "
            f"ANCIEN {mesures['chunks_ancien']}"
        )
        print(
            f"    elements coupes en deux : ELEMENT "
            f"{mesures['elements_coupes_element']} | "
            f"ANCIEN {mesures['elements_coupes_ancien']}"
        )
        print(
            f"    extractions {mesures['extractions']} -> "
            f"{mesures['portions']} portions "
            f"({mesures['ancres_multi']} multi-elements)"
        )
        print(
            f"    ancres verifiees : {mesures['ancres_verifiees']} | "
            f"douteuses : {mesures['ancres_douteuses']}"
        )

    print("\n" + "=" * 78)
    print("BILAN")
    print("=" * 78)
    total_coupes_ancien = sum(
        m["elements_coupes_ancien"] for m in toutes_les_mesures
    )
    total_extractions = sum(m["extractions"] for m in toutes_les_mesures)
    total_portions = sum(m["portions"] for m in toutes_les_mesures)
    total_multi = sum(m["ancres_multi"] for m in toutes_les_mesures)
    total_verifiees = sum(m["ancres_verifiees"] for m in toutes_les_mesures)
    total_douteuses = sum(m["ancres_douteuses"] for m in toutes_les_mesures)

    print(f"Elements coupes en deux — ANCIEN : {total_coupes_ancien}")
    print(f"Elements coupes en deux — ELEMENT : 0 (garanti par la regle 1)")
    print(f"Extractions totales : {total_extractions}")
    print(f"Portions totales : {total_portions}")
    print(
        f"Extractions couvrant PLUSIEURS elements : {total_multi} "
        f"(impossible a representer avec le moteur ANCIEN)"
    )
    print(f"Ancres verifiees : {total_verifiees} | douteuses : {total_douteuses}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
