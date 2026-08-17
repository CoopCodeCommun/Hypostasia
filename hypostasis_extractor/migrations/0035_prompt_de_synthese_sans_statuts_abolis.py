"""
Remplace le prompt de synthese qui enseignait un produit disparu.
/ Replaces the synthesis prompt that taught an abolished product.

LOCALISATION : hypostasis_extractor/migrations/0035_...py

POURQUOI UNE MIGRATION ET PAS SEULEMENT LA FIXTURE : le garnissage
(`_garnir_le_prompt_de_synthese`) ne pose ses pieces que si l'analyseur
n'en a AUCUNE — le contenu d'un prompt est un travail d'auteur, on ne
l'ecrase pas a chaque demarrage. Toute installation existante garderait
donc l'ancien texte, production du 16 aout 2026 comprise.

CE QUI ETAIT FAUX, sur deux axes independants :
- les SIX statuts de debat (CONSENSUEL, DISCUTABLE, DISCUTE,
  CONTROVERSE, NON PERTINENT) ont ete fusionnes en DEUX le 2 mai 2026 ;
- la synthese a cesse d'etre une VERSION d'un texte le 9 aout 2026 pour
  devenir une NOTE DU CARNET, qui n'a pas de « texte original ».

Sur un appel reel du 16 aout, le modele justifiait ses operations par
« avec le statut CONSENSUEL ».

PRUDENCE : on ne remplace une piece que si elle porte encore la marque
de l'ancien texte. Un prompt reecrit a la main par le mainteneur n'est
jamais ecrase — c'est la meme regle que le garnissage.
/ Only pieces still carrying the abolished vocabulary are replaced;
hand-authored prompts are never clobbered.
"""

from django.db import migrations

# Ce qui trahit l'ancien texte, et rien d'autre.
# / What betrays the old text, and nothing else.
MARQUEURS_DE_L_ANCIEN_PROMPT = (
    "CONSENSUEL",
    "nouvelle version",
    "texte original",
)


def remplacer_le_prompt_de_synthese(apps, schema_editor):
    """Repose les trois pieces, si elles sont restees les anciennes."""
    from front.services.fixtures_analyseurs import (
        PIECE_DE_CONSIGNE_DE_LA_SYNTHESE,
        PIECE_DE_CONTEXTE_DE_LA_SYNTHESE,
        PIECE_DE_PONDERATION_DE_LA_SYNTHESE,
    )

    AnalyseurSyntaxique = apps.get_model(
        "hypostasis_extractor", "AnalyseurSyntaxique",
    )
    PromptPiece = apps.get_model("hypostasis_extractor", "PromptPiece")

    contenus_par_ordre = {
        0: PIECE_DE_CONTEXTE_DE_LA_SYNTHESE,
        1: PIECE_DE_PONDERATION_DE_LA_SYNTHESE,
        2: PIECE_DE_CONSIGNE_DE_LA_SYNTHESE,
    }

    nombre_de_pieces_remplacees = 0
    nombre_d_analyseurs_laisses = 0
    for analyseur in AnalyseurSyntaxique.objects.filter(
        type_analyseur="synthetiser",
    ):
        pieces = list(
            PromptPiece.objects.filter(analyseur=analyseur).order_by("order")
        )
        texte_entier = "\n".join(piece.content or "" for piece in pieces)
        porte_l_ancien_texte = any(
            marqueur in texte_entier
            for marqueur in MARQUEURS_DE_L_ANCIEN_PROMPT
        )
        if not porte_l_ancien_texte:
            # Prompt deja a jour, ou reecrit a la main : on n'y touche pas.
            # / Already current, or hand-authored: left alone.
            nombre_d_analyseurs_laisses += 1
            continue

        for piece in pieces:
            contenu_neuf = contenus_par_ordre.get(piece.order)
            if contenu_neuf is None:
                continue
            piece.content = contenu_neuf
            piece.save(update_fields=["content"])
            nombre_de_pieces_remplacees += 1

    print(
        f"\n[migration 0035] prompt de synthese : "
        f"{nombre_de_pieces_remplacees} piece(s) remplacee(s), "
        f"{nombre_d_analyseurs_laisses} analyseur(s) laisse(s) intact(s)"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("hypostasis_extractor", "0034_documenter_les_champs_de_notification_lue_morts"),
    ]

    operations = [
        migrations.RunPython(
            remplacer_le_prompt_de_synthese,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
