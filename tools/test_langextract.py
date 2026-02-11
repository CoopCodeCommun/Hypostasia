#!/usr/bin/env python3
"""
Test du moteur LangExtract.

Ce script montre comment fonctionne LangExtract, etape par etape.
LangExtract est une librairie Google qui extrait des informations
structurees depuis un texte brut, en utilisant un LLM (modele de langage).

Le principe est simple :
    1. On donne un TEXTE a analyser
    2. On donne des EXEMPLES pour montrer ce qu'on veut extraire
    3. On donne un PROMPT qui decrit la tache
    4. LangExtract appelle le LLM et retourne des ENTITES extraites
    5. Chaque entite a une POSITION exacte dans le texte (grounding)

Pour lancer :
    uv run python tools/test_langextract.py --django
    uv run python tools/test_langextract.py --django --text "Mon texte a analyser"
    uv run python tools/test_langextract.py --django --analyseur 1
    uv run python tools/test_langextract.py --django --analyseur 1 --benchmark
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import langextract as lx


# ==========================================================================
# TEXTE PAR DEFAUT
#
# Ce texte court sert de test rapide.
# Il contient une these, une objection et une metaphore.
# ==========================================================================

TEXTE_PAR_DEFAUT = (
    "Le chiffrement est un droit fondamental, pas un outil criminel. "
    "Pourtant, les gouvernements veulent imposer des portes derobees "
    "dans nos communications, ce qui reviendrait a affaiblir la securite "
    "de tous les citoyens pour surveiller une poignee de suspects."
)


# ==========================================================================
# EXEMPLES FEW-SHOT PAR DEFAUT
#
# Les "exemples few-shot" sont des demonstrations qu'on donne au LLM.
# On lui montre : "voici un texte, et voici ce que j'attends comme resultat".
# Le LLM comprend le schema et l'applique au nouveau texte.
#
# Chaque exemple contient :
#   - text : le texte d'exemple
#   - extractions : la liste des entites qu'on veut extraire de ce texte
#
# Chaque extraction contient :
#   - extraction_class : le TYPE d'entite (these, objection, metaphore...)
#   - extraction_text  : le TEXTE EXACT cite depuis le texte source
#   - attributes       : des ATTRIBUTS supplementaires (stance, emotion...)
# ==========================================================================

EXEMPLES_PAR_DEFAUT = [
    lx.data.ExampleData(
        text=(
            "L'energie nucleaire est fiable et pilotable. "
            "Mais le risque d'accident reste inacceptable."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="these",
                extraction_text="L'energie nucleaire est fiable et pilotable",
                attributes={"stance": "pour"},
            ),
            lx.data.Extraction(
                extraction_class="objection",
                extraction_text="le risque d'accident reste inacceptable",
                attributes={"stance": "contre"},
            ),
        ],
    ),
]


# ==========================================================================
# PROMPT PAR DEFAUT
#
# Le prompt decrit au LLM CE QU'ON VEUT EXTRAIRE.
# C'est une consigne en langage naturel.
# ==========================================================================

PROMPT_PAR_DEFAUT = (
    "Extraire les theses, objections, presupposes et metaphores. "
    "Texte exact uniquement, ne pas reformuler. "
    "Attributs : stance (pour/contre), emotion si pertinent."
)


def recuperer_cle_api_depuis_django():
    """
    Recupere la cle API stockee dans la base de donnees Django.

    Dans Hypostasia, les cles API sont stockees dans le modele AIModel.
    Cette fonction initialise Django et va chercher la premiere cle active.

    Retourne un tuple : (cle_api, nom_du_provider, nom_du_modele)
    Exemple : ("sk-abc123...", "openai", "gpt-5.1")
    """

    # On ajoute le dossier du projet au path Python
    # Le script est dans tools/, donc le projet est un niveau au-dessus
    # / Script is in tools/, so project root is one level up
    chemin_du_projet = str(Path(__file__).resolve().parent.parent)
    sys.path.insert(0, chemin_du_projet)

    # On indique a Django quel fichier de settings utiliser
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")

    # On initialise Django (necessaire pour acceder a la base de donnees)
    import django
    django.setup()

    # On importe le modele AIModel depuis l'app "core"
    from core.models import AIModel

    # On cherche le premier modele actif
    modele_ia = AIModel.objects.filter(is_active=True).first()

    if modele_ia and modele_ia.api_key:
        return modele_ia.api_key, modele_ia.provider, modele_ia.model_name

    # Aucune cle trouvee
    return None, None, None


# ==========================================================================
# CONSTRUCTION PROMPT + EXEMPLES DEPUIS UN AnalyseurSyntaxique DJANGO
#
# Ces fonctions vont chercher dans la base Django les morceaux de prompt
# (PromptPiece) et les exemples few-shot (AnalyseurExample) lies a un
# analyseur, puis les convertissent en objets LangExtract.
# ==========================================================================


def lister_analyseurs_disponibles():
    """
    Affiche la liste des AnalyseurSyntaxique actifs dans la base Django.
    / Lists active AnalyseurSyntaxique from Django DB.
    """
    from hypostasis_extractor.models import AnalyseurSyntaxique

    analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True)

    if not analyseurs_actifs.exists():
        print("  Aucun analyseur actif en base.")
        return

    print("\n[ANALYSEURS DISPONIBLES]")
    for analyseur in analyseurs_actifs:
        nombre_de_pieces = analyseur.pieces.count()
        nombre_d_exemples = analyseur.examples.count()
        print(
            f"  id={analyseur.id}  "
            f"\"{analyseur.name}\"  "
            f"({nombre_de_pieces} pieces, {nombre_d_exemples} exemples)"
        )
    print()


def construire_prompt_depuis_analyseur(identifiant_analyseur):
    """
    Construit le prompt LangExtract en concatenant les PromptPiece ordonnees.
    Retourne un string (le prompt complet).
    / Builds LangExtract prompt by concatenating ordered PromptPieces.
    Returns a string (the full prompt).
    """
    from hypostasis_extractor.models import AnalyseurSyntaxique

    analyseur = AnalyseurSyntaxique.objects.get(id=identifiant_analyseur)

    # On recupere toutes les pieces de prompt, triees par ordre
    # / Get all prompt pieces, sorted by order
    pieces_ordonnees = analyseur.pieces.all().order_by('order')

    if not pieces_ordonnees.exists():
        print(f"  [ATTENTION] Aucune piece de prompt pour l'analyseur \"{analyseur.name}\"")
        return PROMPT_PAR_DEFAUT

    # Concatenation de chaque morceau avec un retour a la ligne
    # / Concatenate each piece with a newline separator
    morceaux_de_prompt = []
    for piece in pieces_ordonnees:
        morceaux_de_prompt.append(piece.content)

    prompt_complet = "\n".join(morceaux_de_prompt)

    print(f"  [Analyseur] Prompt construit depuis \"{analyseur.name}\" ({len(pieces_ordonnees)} pieces)")
    return prompt_complet


def construire_exemples_depuis_analyseur(identifiant_analyseur):
    """
    Construit les exemples few-shot LangExtract depuis les AnalyseurExample.
    Chaque AnalyseurExample contient des ExampleExtraction, chacune avec
    des ExtractionAttribute (cle-valeur).
    Retourne une liste de lx.data.ExampleData.
    / Builds LangExtract few-shot examples from AnalyseurExample models.
    Returns a list of lx.data.ExampleData.
    """
    from hypostasis_extractor.models import AnalyseurSyntaxique

    analyseur = AnalyseurSyntaxique.objects.get(id=identifiant_analyseur)

    # On recupere les exemples lies a cet analyseur, tries par ordre
    # / Get examples linked to this analyzer, sorted by order
    exemples_du_modele = analyseur.examples.all().order_by('order')

    if not exemples_du_modele.exists():
        print(f"  [ATTENTION] Aucun exemple few-shot pour l'analyseur \"{analyseur.name}\"")
        return EXEMPLES_PAR_DEFAUT

    liste_exemples_langextract = []

    for exemple_django in exemples_du_modele:
        # Pour chaque exemple, on recupere les extractions attendues
        # / For each example, get the expected extractions
        extractions_du_modele = exemple_django.extractions.all().order_by('order')

        liste_extractions_langextract = []

        for extraction_django in extractions_du_modele:
            # On recupere les attributs cle-valeur de cette extraction
            # / Get key-value attributes of this extraction
            attributs_du_modele = extraction_django.attributes.all()

            dictionnaire_attributs = {}
            for attribut in attributs_du_modele:
                dictionnaire_attributs[attribut.key] = attribut.value

            extraction_langextract = lx.data.Extraction(
                extraction_class=extraction_django.extraction_class,
                extraction_text=extraction_django.extraction_text,
                attributes=dictionnaire_attributs,
            )
            liste_extractions_langextract.append(extraction_langextract)

        exemple_langextract = lx.data.ExampleData(
            text=exemple_django.example_text,
            extractions=liste_extractions_langextract,
        )
        liste_exemples_langextract.append(exemple_langextract)

    nombre_exemples = len(liste_exemples_langextract)
    print(f"  [Analyseur] {nombre_exemples} exemples few-shot charges depuis \"{analyseur.name}\"")

    return liste_exemples_langextract


def choisir_texte_benchmark_depuis_analyseur(identifiant_analyseur):
    """
    Recupere le texte d'un exemple few-shot de l'analyseur pour servir de benchmark.
    S'il y a plusieurs exemples, demande a l'utilisateur de choisir via input().
    Retourne le texte choisi (string).
    / Gets an example text from the analyzer to use as benchmark input.
    If multiple examples, asks the user to choose via input().
    Returns the chosen text (string).
    """
    from hypostasis_extractor.models import AnalyseurSyntaxique

    analyseur = AnalyseurSyntaxique.objects.get(id=identifiant_analyseur)
    exemples_du_modele = list(analyseur.examples.all().order_by('order'))

    nombre_d_exemples = len(exemples_du_modele)

    if nombre_d_exemples == 0:
        print("  [BENCHMARK] Aucun exemple dans cet analyseur, utilisation du texte par defaut.")
        return TEXTE_PAR_DEFAUT

    if nombre_d_exemples == 1:
        # Un seul exemple : on le prend directement
        # / Single example: use it directly
        exemple_choisi = exemples_du_modele[0]
        print(f"  [BENCHMARK] Texte de l'exemple \"{exemple_choisi.name}\" utilise comme input.")
        return exemple_choisi.example_text

    # Plusieurs exemples : on demande a l'utilisateur de choisir
    # / Multiple examples: ask the user to choose
    print("\n[BENCHMARK] Plusieurs exemples disponibles :")
    for index, exemple in enumerate(exemples_du_modele):
        apercu_du_texte = exemple.example_text[:80].replace("\n", " ")
        print(f"  {index + 1}. \"{exemple.name}\" — {apercu_du_texte}...")

    choix_utilisateur = input(f"\nChoisissez un exemple (1-{nombre_d_exemples}) : ").strip()

    try:
        index_choisi = int(choix_utilisateur) - 1
        if 0 <= index_choisi < nombre_d_exemples:
            exemple_choisi = exemples_du_modele[index_choisi]
            print(f"  [BENCHMARK] Texte de l'exemple \"{exemple_choisi.name}\" utilise comme input.")
            return exemple_choisi.example_text
    except ValueError:
        pass

    # Choix invalide : on prend le premier par defaut
    # / Invalid choice: fallback to first
    print("  [BENCHMARK] Choix invalide, utilisation du premier exemple.")
    return exemples_du_modele[0].example_text


def lancer_test(
    texte,
    exemples=None,
    prompt=None,
    identifiant_modele="gemini-2.5-flash",
    cle_api=None,
    activer_chunking=False,
    nombre_de_workers=1,
    sauvegarder_jsonl=True,
    generer_html=True,
    mode_verbeux=True,
):
    """
    Fonction principale de test.

    Elle deroule tout le pipeline LangExtract :

        ETAPE 1 : Afficher la configuration
                  (quel modele, quel texte, quels exemples)

        ETAPE 2 : Lancer l'extraction via le LLM
                  (appel a lx.extract)

        ETAPE 3 : Inspecter les resultats
                  (quelles entites, quelles positions, quels attributs)

        ETAPE 4 : Verifier le grounding
                  (est-ce que le texte extrait correspond bien a sa position ?)

        ETAPE 5 : Sauvegarder en JSONL
                  (format standard pour LangExtract)

        ETAPE 6 : Generer la visualisation HTML interactive
                  (surlignage des entites dans le texte)

    Arguments :
        texte               : le texte a analyser (string)
        exemples            : liste d'ExampleData (few-shot). None = exemples par defaut
        prompt              : description de ce qu'on veut extraire. None = prompt par defaut
        identifiant_modele  : quel LLM utiliser ("gemini-2.5-flash", "gpt-4o", etc.)
        cle_api             : cle API du provider. None = cherche dans les variables d'env
        activer_chunking    : True pour decouper les longs textes en morceaux
        nombre_de_workers   : combien de workers paralleles (utile avec chunking)
        sauvegarder_jsonl   : True pour sauvegarder les resultats en fichier JSONL
        generer_html        : True pour generer une page HTML de visualisation
        mode_verbeux        : True pour afficher les details etape par etape

    Retourne :
        Le resultat LangExtract (AnnotatedDocument avec les extractions)
    """

    # --- Valeurs par defaut ---

    if exemples is None:
        exemples = EXEMPLES_PAR_DEFAUT

    if prompt is None:
        prompt = PROMPT_PAR_DEFAUT

    # On cherche la cle API dans cet ordre :
    # 1. Argument de la fonction
    # 2. Variable d'environnement LANGEXTRACT_API_KEY
    # 3. Variable d'environnement GOOGLE_API_KEY
    cle_api_resolue = (
        cle_api
        or os.environ.get("LANGEXTRACT_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )

    # ==================================================================
    # ETAPE 1 : Afficher la configuration
    # ==================================================================

    if mode_verbeux:
        print("=" * 60)
        print("  LANGEXTRACT - Test du pipeline complet")
        print("=" * 60)

        # On montre avec quel modele on va travailler
        print(f"\n  Modele    : {identifiant_modele}")

        # On masque la cle API sauf les 4 derniers caracteres
        if cle_api_resolue:
            cle_masquee = "***" + cle_api_resolue[-4:]
        else:
            cle_masquee = "MANQUANTE"
        print(f"  Cle API   : {cle_masquee}")

        # Infos sur le texte et les exemples
        nombre_de_caracteres = len(texte)
        nombre_d_exemples = len(exemples)
        print(f"  Texte     : {nombre_de_caracteres} caracteres")
        print(f"  Exemples  : {nombre_d_exemples}")
        print(f"  Chunking  : {activer_chunking}")

        # Afficher le prompt
        print(f"\n[PROMPT]")
        print(f"  {prompt}")

        # Afficher chaque exemple few-shot
        print(f"\n[EXEMPLES FEW-SHOT]")
        for numero, exemple in enumerate(exemples):
            nombre_extractions_dans_exemple = len(exemple.extractions)
            print(f"\n  Exemple #{numero + 1} ({nombre_extractions_dans_exemple} extractions) :")

            for extraction in exemple.extractions:
                # On formate les attributs en "cle=valeur, cle=valeur"
                liste_attributs = []
                for cle, valeur in (extraction.attributes or {}).items():
                    liste_attributs.append(f"{cle}={valeur}")
                attributs_formetes = ", ".join(liste_attributs)

                print(f"    [{extraction.extraction_class}] \"{extraction.extraction_text}\"")
                if attributs_formetes:
                    print(f"      attributs: {attributs_formetes}")

        # Afficher le texte a analyser
        print(f"\n[TEXTE A ANALYSER]")
        print(f"  {texte}")

    # ==================================================================
    # ETAPE 2 : Lancer l'extraction via le LLM
    # ==================================================================

    if mode_verbeux:
        print(f"\n{'─' * 60}")
        print(f"  Appel au LLM en cours...")

    # On prepare les parametres pour lx.extract()
    parametres_extraction = {
        "text_or_documents": texte,          # le texte a analyser
        "prompt_description": prompt,        # ce qu'on veut extraire
        "examples": exemples,               # les exemples few-shot
        "model_id": identifiant_modele,      # quel modele utiliser
    }

    # On ajoute la cle API si on en a une
    if cle_api_resolue:
        parametres_extraction["api_key"] = cle_api_resolue

    # Si le modele est OpenAI (GPT), on ajoute des parametres specifiques
    # car LangExtract ne supporte pas encore le schema OpenAI natif
    modele_est_openai = "gpt" in identifiant_modele or "openai" in identifiant_modele
    if modele_est_openai:
        parametres_extraction["fence_output"] = True
        parametres_extraction["use_schema_constraints"] = False

    # Si on active le chunking pour les longs textes (plus de 4000 caracteres)
    # Le chunking decoupe le texte en morceaux, les traite en parallele,
    # et fusionne les resultats. Utile pour les articles longs.
    texte_est_long = len(texte) > 4000
    if activer_chunking and texte_est_long:
        parametres_extraction["extraction_passes"] = 3       # 3 passes pour ne rien rater
        parametres_extraction["max_workers"] = nombre_de_workers  # workers en parallele
        parametres_extraction["max_char_buffer"] = 1000      # chevauchement entre les morceaux

    # On mesure le temps d'execution
    moment_debut = time.time()

    # APPEL PRINCIPAL : c'est ici que LangExtract envoie le texte au LLM
    # et recupere les entites extraites
    resultat = lx.extract(**parametres_extraction)

    duree_en_secondes = time.time() - moment_debut

    # ==================================================================
    # ETAPE 3 : Inspecter les resultats
    # ==================================================================

    # Le resultat contient une liste d'extractions
    liste_des_entites = resultat.extractions or []
    nombre_total_entites = len(liste_des_entites)

    # --- Statistiques par classe ---
    # On compte combien d'entites de chaque type on a trouve
    compteur_par_classe = {}
    for entite in liste_des_entites:
        nom_de_classe = entite.extraction_class
        if nom_de_classe in compteur_par_classe:
            compteur_par_classe[nom_de_classe] += 1
        else:
            compteur_par_classe[nom_de_classe] = 1

    if mode_verbeux:
        print(f"  Termine : {nombre_total_entites} entites en {duree_en_secondes:.1f}s")

        # On trie par nombre decroissant
        classes_triees = sorted(
            compteur_par_classe.items(),
            key=lambda paire: paire[1],
            reverse=True,
        )

        print(f"\n[REPARTITION PAR CLASSE]")
        for nom_classe, nombre in classes_triees:
            barre_visuelle = "█" * nombre
            print(f"  {nom_classe:<25s} {barre_visuelle} ({nombre})")

        # --- Detail de chaque entite ---
        print(f"\n[DETAIL DES EXTRACTIONS]")
        for numero, entite in enumerate(liste_des_entites):

            # Position dans le texte (char_interval)
            # C'est le "grounding" : a quel endroit exact du texte correspond cette entite
            intervalle = entite.char_interval
            if intervalle:
                position_texte = f"[{intervalle.start_pos}:{intervalle.end_pos}]"
            else:
                position_texte = "[position inconnue]"

            print(f"\n  {numero + 1}. [{entite.extraction_class}] {position_texte}")
            print(f"     \"{entite.extraction_text}\"")

            # Afficher les attributs (stance, emotion, etc.)
            if entite.attributes:
                liste_attrs = []
                for cle_attr, valeur_attr in entite.attributes.items():
                    liste_attrs.append(f"{cle_attr}={valeur_attr}")
                print(f"     Attributs: {' | '.join(liste_attrs)}")

            # ==================================================================
            # ETAPE 4 : Verifier le grounding
            #
            # Le "grounding" verifie que le texte extrait correspond exactement
            # au texte qui se trouve a la position indiquee.
            #
            # Si ca ne correspond pas, c'est que le LLM a reformule ou invente
            # au lieu de citer exactement. C'est un indicateur de qualite.
            # ==================================================================

            position_est_connue = (
                intervalle
                and intervalle.start_pos is not None
                and intervalle.end_pos is not None
            )

            if position_est_connue:
                # On decoupe le texte original a la position indiquee
                texte_a_cette_position = texte[intervalle.start_pos:intervalle.end_pos]

                # On compare avec ce que le LLM a extrait
                texte_extrait_par_le_llm = entite.extraction_text
                les_textes_correspondent = (texte_a_cette_position == texte_extrait_par_le_llm)

                if les_textes_correspondent:
                    print(f"     Grounding: OK (citation exacte)")
                else:
                    print(f"     Grounding: ECART DETECTE")
                    print(f"       Le LLM dit  : \"{texte_extrait_par_le_llm[:60]}\"")
                    print(f"       Le texte dit : \"{texte_a_cette_position[:60]}\"")

    # ==================================================================
    # ETAPE 5 : Sauvegarder en JSONL
    #
    # Le format JSONL est le format standard de LangExtract.
    # C'est un fichier ou chaque ligne est un objet JSON.
    # Il contient le texte, les extractions, et les positions.
    # ==================================================================

    # Le dossier de sortie est a la racine du projet (un niveau au-dessus de tools/)
    # / Output dir is at project root (one level above tools/)
    racine_du_projet = Path(__file__).resolve().parent.parent
    dossier_de_sortie = racine_du_projet / "test_output"
    dossier_de_sortie.mkdir(exist_ok=True)

    chemin_fichier_jsonl = None

    if sauvegarder_jsonl:
        nom_du_fichier_jsonl = "test_extraction.jsonl"

        # LangExtract fournit une fonction pour sauvegarder les resultats
        lx.io.save_annotated_documents(
            [resultat],
            output_name=nom_du_fichier_jsonl,
            output_dir=str(dossier_de_sortie),
        )

        chemin_fichier_jsonl = dossier_de_sortie / nom_du_fichier_jsonl
        taille_du_fichier = chemin_fichier_jsonl.stat().st_size

        if mode_verbeux:
            print(f"\n[JSONL] {chemin_fichier_jsonl} ({taille_du_fichier:,} octets)")

    # ==================================================================
    # ETAPE 6 : Generer la visualisation HTML interactive
    #
    # lx.visualize() prend un fichier JSONL et genere du HTML
    # avec le texte surligne : chaque entite est coloree et cliquable.
    # On peut naviguer entre les entites avec les boutons Play/Next.
    # ==================================================================

    chemin_fichier_html = None

    fichier_jsonl_existe = chemin_fichier_jsonl is not None
    if generer_html and fichier_jsonl_existe:
        # Generation du HTML par LangExtract
        contenu_html = lx.visualize(str(chemin_fichier_jsonl))

        # En mode Jupyter, le resultat a un attribut .data
        if hasattr(contenu_html, "data"):
            contenu_html = contenu_html.data

        chemin_fichier_html = dossier_de_sortie / "test_visualization.html"
        with open(chemin_fichier_html, "w", encoding="utf-8") as fichier:
            fichier.write(contenu_html)

        taille_html = chemin_fichier_html.stat().st_size

        if mode_verbeux:
            print(f"[HTML]  {chemin_fichier_html} ({taille_html:,} octets)")
            print(f"        Pour ouvrir : xdg-open {chemin_fichier_html}")

    # --- Resume final ---

    # On calcule le nombre de classes (defini dans l'etape 3, ou 0 si pas d'entites)
    nombre_de_classes = len(compteur_par_classe) if liste_des_entites else 0

    if mode_verbeux:
        print(f"\n{'=' * 60}")
        print(f"  {nombre_total_entites} entites | {nombre_de_classes} classes | {duree_en_secondes:.1f}s | {identifiant_modele}")
        print(f"{'=' * 60}\n")

    return resultat


# ==========================================================================
# INTERFACE EN LIGNE DE COMMANDE (CLI)
#
# Permet de lancer le script depuis le terminal avec des options.
# ==========================================================================

def main():
    analyseur_arguments = argparse.ArgumentParser(
        description="Test du moteur LangExtract",
    )

    # --- Source du texte ---
    # On ne peut choisir qu'une seule source a la fois
    groupe_texte = analyseur_arguments.add_mutually_exclusive_group()
    groupe_texte.add_argument(
        "--text", type=str,
        help="Texte a analyser (entre guillemets)",
    )
    groupe_texte.add_argument(
        "--text-file", type=str,
        help="Chemin vers un fichier texte a analyser",
    )
    groupe_texte.add_argument(
        "--url", type=str,
        help="URL d'un document (LangExtract le telecharge)",
    )

    # --- Configuration du modele ---
    analyseur_arguments.add_argument(
        "--model", type=str, default="gemini-2.5-flash",
        help="Modele LLM a utiliser (defaut: gemini-2.5-flash)",
    )
    analyseur_arguments.add_argument(
        "--api-key", type=str,
        help="Cle API directe (sinon utilise LANGEXTRACT_API_KEY)",
    )
    analyseur_arguments.add_argument(
        "--django", action="store_true",
        help="Recuperer la cle API depuis la base Django",
    )
    analyseur_arguments.add_argument(
        "--prompt", type=str,
        help="Prompt d'extraction personnalise",
    )

    # --- Options d'extraction ---
    analyseur_arguments.add_argument(
        "--chunking", action="store_true",
        help="Decouper les longs textes en morceaux",
    )
    analyseur_arguments.add_argument(
        "--workers", type=int, default=1,
        help="Nombre de workers paralleles (avec --chunking)",
    )

    # --- Options de sortie ---
    analyseur_arguments.add_argument(
        "--no-jsonl", action="store_true",
        help="Ne pas sauvegarder le fichier JSONL",
    )
    analyseur_arguments.add_argument(
        "--no-html", action="store_true",
        help="Ne pas generer la visualisation HTML",
    )
    analyseur_arguments.add_argument(
        "--quiet", action="store_true",
        help="Mode silencieux (pas d'affichage)",
    )

    # --- Exemples few-shot personnalises ---
    analyseur_arguments.add_argument(
        "--examples-file", type=str,
        help="Fichier JSON contenant des exemples few-shot personnalises",
    )

    # --- Analyseur Syntaxique Django ---
    analyseur_arguments.add_argument(
        "--analyseur", type=int,
        help="ID de l'AnalyseurSyntaxique Django (prompt + exemples depuis la base)",
    )
    analyseur_arguments.add_argument(
        "--list-analyseurs", action="store_true",
        help="Lister les analyseurs disponibles en base et quitter",
    )
    analyseur_arguments.add_argument(
        "--benchmark", action="store_true",
        help="Mode benchmark : utilise le texte d'un exemple few-shot de l'analyseur comme input",
    )

    arguments = analyseur_arguments.parse_args()

    # --- Si --list-analyseurs, on initialise Django et on affiche la liste ---

    besoin_de_django = arguments.list_analyseurs or arguments.analyseur or arguments.benchmark
    if besoin_de_django:
        # On a besoin de Django pour acceder aux modeles AnalyseurSyntaxique
        # / We need Django to access AnalyseurSyntaxique models
        chemin_du_projet = str(Path(__file__).resolve().parent.parent)
        sys.path.insert(0, chemin_du_projet)
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
        import django
        django.setup()

    if arguments.list_analyseurs:
        lister_analyseurs_disponibles()
        sys.exit(0)

    # --- Determiner le texte a analyser ---

    if arguments.benchmark and arguments.analyseur:
        # Mode benchmark : on utilise le texte d'un exemple few-shot comme input
        # / Benchmark mode: use a few-shot example text as input
        texte_a_analyser = choisir_texte_benchmark_depuis_analyseur(arguments.analyseur)
    elif arguments.benchmark and not arguments.analyseur:
        print("  [ERREUR] --benchmark necessite --analyseur <ID>")
        sys.exit(1)
    elif arguments.text:
        texte_a_analyser = arguments.text
    elif arguments.text_file:
        texte_a_analyser = Path(arguments.text_file).read_text(encoding="utf-8")
    elif arguments.url:
        # LangExtract accepte directement une URL comme source
        texte_a_analyser = arguments.url
    else:
        texte_a_analyser = TEXTE_PAR_DEFAUT

    # --- Determiner la cle API et le modele ---

    cle_api = arguments.api_key
    identifiant_modele = arguments.model

    # Si --django est passe, on recupere la cle depuis la base de donnees
    if arguments.django and not cle_api:
        cle_trouvee, provider_trouve, modele_trouve = recuperer_cle_api_depuis_django()

        if cle_trouvee:
            cle_api = cle_trouvee

            # Si l'utilisateur n'a pas force de modele ET que la cle est OpenAI,
            # on bascule automatiquement sur le bon modele
            utilisateur_na_pas_force_le_modele = (arguments.model == "gemini-2.5-flash")
            cle_est_openai = (provider_trouve == "openai")

            if utilisateur_na_pas_force_le_modele and cle_est_openai:
                identifiant_modele = modele_trouve or "gpt-4o"

            print(f"  [Django] Cle recuperee (provider={provider_trouve}, modele={identifiant_modele})")

    # --- Charger prompt + exemples depuis un AnalyseurSyntaxique Django ---
    # / Load prompt + examples from a Django AnalyseurSyntaxique

    prompt_depuis_analyseur = None
    exemples_depuis_analyseur = None

    if arguments.analyseur:
        prompt_depuis_analyseur = construire_prompt_depuis_analyseur(arguments.analyseur)
        exemples_depuis_analyseur = construire_exemples_depuis_analyseur(arguments.analyseur)

    # --- Charger des exemples personnalises si fournis ---

    exemples_personnalises = None

    if arguments.examples_file:
        contenu_json = Path(arguments.examples_file).read_text(encoding="utf-8")
        donnees_exemples = json.loads(contenu_json)

        exemples_personnalises = []

        for donnee_exemple in donnees_exemples:
            # On convertit chaque extraction JSON en objet LangExtract
            liste_extractions = []
            for extraction_brute in donnee_exemple["extractions"]:
                extraction_objet = lx.data.Extraction(
                    extraction_class=extraction_brute["extraction_class"],
                    extraction_text=extraction_brute["extraction_text"],
                    attributes=extraction_brute.get("attributes", {}),
                )
                liste_extractions.append(extraction_objet)

            exemple_objet = lx.data.ExampleData(
                text=donnee_exemple["text"],
                extractions=liste_extractions,
            )
            exemples_personnalises.append(exemple_objet)

    # --- Determiner le prompt et les exemples finaux ---
    # Priorite : --analyseur > --examples-file / --prompt > defauts
    # / Priority: --analyseur > --examples-file / --prompt > defaults

    prompt_final = arguments.prompt or prompt_depuis_analyseur
    exemples_finaux = exemples_personnalises or exemples_depuis_analyseur

    # --- Lancer le test ---

    resultat = lancer_test(
        texte=texte_a_analyser,
        exemples=exemples_finaux,
        prompt=prompt_final,
        identifiant_modele=identifiant_modele,
        cle_api=cle_api,
        activer_chunking=arguments.chunking,
        nombre_de_workers=arguments.workers,
        sauvegarder_jsonl=not arguments.no_jsonl,
        generer_html=not arguments.no_html,
        mode_verbeux=not arguments.quiet,
    )

    # ==================================================================
    # AFFICHAGE JSON LISIBLE DANS LE TERMINAL
    #
    # On convertit le resultat LangExtract en dictionnaire JSON
    # structure et lisible, avec indentation et couleurs Unicode.
    # / Convert LangExtract result to a readable JSON dict for terminal.
    # ==================================================================

    liste_des_entites = resultat.extractions or []

    resultat_json_lisible = []
    for entite in liste_des_entites:
        entite_dict = {
            "extraction_class": entite.extraction_class,
            "extraction_text": entite.extraction_text,
            "attributes": entite.attributes or {},
        }

        # Position dans le texte (grounding)
        # / Position in text (grounding)
        intervalle = entite.char_interval
        if intervalle and intervalle.start_pos is not None:
            entite_dict["start_pos"] = intervalle.start_pos
            entite_dict["end_pos"] = intervalle.end_pos

        resultat_json_lisible.append(entite_dict)

    print("\n[RESULTAT JSON]")
    print(json.dumps(resultat_json_lisible, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
