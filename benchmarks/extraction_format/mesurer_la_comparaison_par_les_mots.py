#!/usr/bin/env python
"""
Banc MANUEL : le controle verbatim, et ce qu'il refuse de blanchir.
/ MANUAL bench: the verbatim check, and what it refuses to launder.

LOCALISATION : benchmarks/extraction_format/mesurer_la_comparaison_par_les_mots.py

CE QU'IL REPOND. La question a ete posee le 30 aout 2026 : plutot que
d'ajouter une regle de forme a la fois, pourquoi ne pas comparer les
deux textes avec un algorithme de proximite, et accepter au-dela de
99 % ? Ce banc mesure les deux voies sur les memes donnees :

1. un SCORE DE SIMILARITE (`difflib`, bibliotheque standard) — la voie
   ECARTEE, mesuree ici pour qu'on sache pourquoi ;
2. le CONTROLE DE PRODUCTION, qui compare la suite des MOTS.

IL N'A PAS SA PROPRE COPIE DE LA REGLE. Il appelle
`core.services.verification._le_verbatim_est_present` — celui que la
chaine de preuve utilise. Une seconde implementation dans un banc
finirait par diverger de celle qu'elle est censee mesurer, et le banc
annoncerait alors des chiffres qui ne decrivent plus le produit.
/ No second implementation: the bench calls production.

CE QU'IL NE FAIT PAS. Il n'appelle aucun modele et n'ecrit rien en
base. Il relit ce que la base porte deja, et fabrique ses perturbations.

LE JEU ADVERSE EST FABRIQUE ICI, ET C'EST LE COEUR DU BANC. Mesurer ce
qu'une regle RECUPERE ne dit rien : toute regle assez lache recupere
tout. Ce qui decide est ce qu'elle BLANCHIT. On part donc de citations
aujourd'hui verbatim et on les falsifie mecaniquement. La verite est
connue sans juge, et c'est gratuit — c'est le jeu que
`benchmarks/juge_de_verification/README.md` appelle de ses voeux.

DEUX FAMILLES DE FALSIFICATION, et la seconde a change le code :

- le FOND — une negation inseree, un quantifieur inverse, un chiffre
  change ;
- la PONCTUATION STRUCTURANTE — une parenthese d'incise retiree, un
  deux-points retire, des guillemets retires. Aucun mot ne bouge, et
  pourtant la source dit autre chose : « comme « l'ecole descolarise » »
  sans ses guillemets fait AFFIRMER a l'auteur ce qu'il rapportait.
  C'est cette famille qui a impose de garder les signes structurants.

RESULTAT DU 30 AOUT 2026, sur la base de dev :

- **aucun seuil de similarite ne separe** la citation honnete abimee
  (la pire vaut 0,9577) de la citation falsifiee (la meilleure vaut
  0,9970). Un chiffre change — 2011 en 2012, un caractere sur cent
  cinquante — obtient 0,9961 ;
- **le controle par les mots separe** : 42 recuperations sur 45, zero
  blanchiment sur 74 cas reels et sur toutes les perturbations.

Detail et arbitrage :
`PLAN/TODO/2026-08-30-ce-qui-reste-du-verbatim-introuvable.md`.

Usage :
    docker exec -w /app hypostasia_web python \
        benchmarks/extraction_format/mesurer_la_comparaison_par_les_mots.py
"""

import difflib
import os
import re
import statistics
import sys
import time

# Django doit etre amorce AVANT tout import de modele, comme dans les
# autres bancs de ce dossier. `setdefault` et `django.setup()` sont
# idempotents.
# / Django must be set up before any model import.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")

import django  # noqa: E402

django.setup()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import ElementDocument, SourceLink  # noqa: E402
from core.services.verification import (  # noqa: E402
    _le_verbatim_est_present,
)
from hypostasis_extractor.models import ExtractedEntity  # noqa: E402
from typer_les_non_verbatim import (  # noqa: E402
    MOTIF_DES_MOTS, decomposer_en_blocs, normaliser, typer_l_ecart,
)

# Combien de citations verbatim on falsifie pour fabriquer le jeu adverse.
# / How many verbatim quotes we falsify to build the adversarial set.
TAILLE_DU_JEU_ADVERSE = 150

# Combien de liens deja valides servent a la non-regression.
# / How many already-valid links serve the regression check.
TAILLE_DE_LA_NON_REGRESSION = 400

_textes_des_sources = {}


def texte_de_la_source(extraction):
    """
    Le texte de la note source : ses elements d'abord, comme en
    production. / The source note's text: its elements first.
    """
    identifiant_de_page = extraction.job.page_id
    if identifiant_de_page not in _textes_des_sources:
        textes_des_elements = list(
            ElementDocument.objects.filter(page_id=identifiant_de_page)
            .order_by("ordre").values_list("texte", flat=True)
        )
        _textes_des_sources[identifiant_de_page] = (
            "\n".join(textes_des_elements) if textes_des_elements
            else (extraction.job.page.text_readability or "")
        )
    return _textes_des_sources[identifiant_de_page]


def ratio_sur_la_meilleure_fenetre(texte_source, texte_extrait):
    """
    Le ratio de similarite entre l'extrait et SA fenetre dans la source.
    / The similarity ratio against the located source window.

    LA FENETRE EST LE POINT DELICAT, et elle est localisee comme le fait
    `compter_les_retouches` : chercher le premier mot dans toute la
    source tomberait sur une autre occurrence et rendrait un ratio qui
    ne veut rien dire.
    / Locating the window matters: a naive search hits another occurrence.
    """
    source = normaliser(texte_source)
    extrait = normaliser(texte_extrait)
    decomposition = decomposer_en_blocs(source, extrait)
    if not decomposition["blocs"]:
        return 0.0
    positions_des_mots = [m.span() for m in MOTIF_DES_MOTS.finditer(source)]
    premier_bloc = decomposition["blocs"][0]
    dernier_bloc = decomposition["blocs"][-1]
    debut = positions_des_mots[premier_bloc[0]][0]
    fin = positions_des_mots[dernier_bloc[0] + dernier_bloc[1] - 1][1]
    fenetre = source[debut:fin]
    return difflib.SequenceMatcher(
        None, fenetre, extrait, autojunk=False,
    ).ratio()


# --- Le jeu adverse : des citations vraies, falsifiees mecaniquement -----

NEGATIONS = [
    (r"\best\b", "n'est pas"), (r"\bsont\b", "ne sont pas"),
    (r"\bpeut\b", "ne peut pas"), (r"\bpeuvent\b", "ne peuvent pas"),
    (r"\bpermet\b", "ne permet pas"),
    (r"\bpermettent\b", "ne permettent pas"),
    (r"\ba\b", "n'a pas"), (r"\bexiste\b", "n'existe pas"),
]

QUANTIFIEURS = [
    (r"\btous\b", "aucun"), (r"\btoutes\b", "aucune"),
    (r"\btoujours\b", "jamais"), (r"\bplusieurs\b", "aucun"),
    (r"\bchaque\b", "aucun"), (r"\bdoit\b", "ne doit pas"),
]


def perturber_par(texte, regles):
    """Applique la PREMIERE regle qui mord, une seule fois."""
    for motif, remplacement in regles:
        texte_perturbe, combien = re.subn(motif, remplacement, texte, count=1)
        if combien:
            return texte_perturbe
    return None


def changer_un_chiffre(texte):
    """
    Un nombre change : la falsification la plus PETITE possible.
    / One digit changed: the smallest possible falsification.

    C'est elle qui decide du sort de la voie « score de similarite » :
    un caractere sur cent cinquante, et le sens bascule.
    """
    trouve = re.search(r"\b(\d{1,4})\b", texte)
    if not trouve:
        return None
    valeur = int(trouve.group(1))
    return texte[:trouve.start()] + str(valeur + 1) + texte[trouve.end():]


def retirer_une_parenthese_d_incise(texte):
    """« reconnu (sauf X) » -> « reconnu sauf X » : la reserve se fond."""
    if "(" not in texte or ")" not in texte:
        return None
    return texte.replace("(", "", 1).replace(")", "", 1)


def retirer_un_deux_points(texte):
    """« il refuse : les badges » -> « il refuse les badges »."""
    return texte.replace(" :", "", 1) if " :" in texte else None


def retirer_des_guillemets(texte):
    """
    LA FALSIFICATION LA PLUS GRAVE DE SA FAMILLE. La source met un
    propos a DISTANCE ; sans les guillemets, l'auteur semble l'affirmer.
    / The source quotes at a distance; without marks it reads as assertion.
    """
    for ouvrant, fermant in (("«", "»"), ('"', '"')):
        if ouvrant in texte and fermant in texte[texte.index(ouvrant) + 1:]:
            return texte.replace(ouvrant, "", 1).replace(fermant, "", 1)
    return None


def remplacer_la_marque_de_fin(texte):
    """« ? » rendu « . » : aucun mot ne change, la source dit autre chose."""
    return texte.replace("?", ".", 1) if "?" in texte else None


def remplacer_une_marque_au_milieu(texte):
    """Un « ? » AU MILIEU : la garde de fin ne le voit pas, les signes si."""
    trouve = re.search(r"\?(?=.{10,})", texte)
    if not trouve:
        return None
    return texte[:trouve.start()] + "." + texte[trouve.end():]


PERTURBATIONS_DU_FOND = {
    "negation inseree": lambda texte: perturber_par(texte, NEGATIONS),
    "quantifieur inverse": lambda texte: perturber_par(texte, QUANTIFIEURS),
    "UN CHIFFRE change (2011 -> 2012)": changer_un_chiffre,
}

PERTURBATIONS_DE_LA_PONCTUATION = {
    "parenthese d'incise retiree": retirer_une_parenthese_d_incise,
    "deux-points retire": retirer_un_deux_points,
    "guillemets retires (la distance disparait)": retirer_des_guillemets,
    "« ? » AU MILIEU rendu « . »": remplacer_une_marque_au_milieu,
    "« ? » FINAL rendu « . »": remplacer_la_marque_de_fin,
}


def citations_aujourd_hui_verbatim():
    """Des citations que la chaine de preuve accepte AUJOURD'HUI."""
    retenues = []
    for extraction in ExtractedEntity.objects.select_related(
        "job__page",
    ).filter(masquee=False)[:600]:
        if not extraction.extraction_text:
            continue
        if len(extraction.extraction_text) < 40:
            continue
        source = texte_de_la_source(extraction)
        if _le_verbatim_est_present(extraction.extraction_text, source):
            retenues.append((extraction, source))
        if len(retenues) >= TAILLE_DU_JEU_ADVERSE:
            break
    return retenues


def _mesurer_une_famille(jeu, familles, titre):
    """Une famille de falsifications, et ce que le controle en fait."""
    print(f"\n=== {titre} ===\n")
    print(f"{'perturbation':44s} {'n':>4s} {'ratio max':>10s} "
          f"{'BLANCHIES':>12s}")
    ratios_de_la_famille = []
    for nom, fabriquer in familles.items():
        ratios = []
        blanchies = 0
        for extraction, source in jeu:
            falsifiee = fabriquer(extraction.extraction_text)
            if not falsifiee or falsifiee == extraction.extraction_text:
                continue
            ratios.append(ratio_sur_la_meilleure_fenetre(source, falsifiee))
            if _le_verbatim_est_present(falsifiee, source):
                blanchies += 1
        if not ratios:
            continue
        ratios_de_la_famille.extend(ratios)
        print(f"{nom:44s} {len(ratios):4d} {max(ratios):10.4f} "
              f"{blanchies:6d} / {len(ratios)}")
    return ratios_de_la_famille


def main():
    liens_introuvables = [
        lien for lien in SourceLink.objects.filter(
            etat_de_verification="introuvable",
        ).select_related("extraction_source__job__page")
        if lien.extraction_source
    ]

    # 1. Les liens INTROUVABLE : leur ecart, leur ratio, leur sort.
    ratios_par_categorie = {}
    passent_par_categorie = {}
    total_par_categorie = {}
    for lien in liens_introuvables:
        extraction = lien.extraction_source
        source = texte_de_la_source(extraction)
        categorie = typer_l_ecart(
            source, extraction.extraction_text,
        )["categorie"]
        total_par_categorie[categorie] = total_par_categorie.get(categorie, 0) + 1
        ratios_par_categorie.setdefault(categorie, []).append(
            ratio_sur_la_meilleure_fenetre(source, extraction.extraction_text)
        )
        if _le_verbatim_est_present(extraction.extraction_text, source):
            passent_par_categorie[categorie] = (
                passent_par_categorie.get(categorie, 0) + 1
            )

    print(f"=== Les {len(liens_introuvables)} liens INTROUVABLE ===\n")
    print(f"{'categorie':16s} {'n':>4s} {'ratio min':>10s} {'median':>8s} "
          f"{'max':>8s} {'passent':>10s}")
    for categorie in sorted(total_par_categorie):
        ratios = ratios_par_categorie[categorie]
        print(f"{categorie:16s} {len(ratios):4d} {min(ratios):10.4f} "
              f"{statistics.median(ratios):8.4f} {max(ratios):8.4f} "
              f"{passent_par_categorie.get(categorie, 0):6d} / "
              f"{total_par_categorie[categorie]}")

    # 2. Le jeu adverse, en deux familles.
    jeu = citations_aujourd_hui_verbatim()
    print(f"\nJeu adverse : {len(jeu)} citations verbatim, falsifiees.")
    ratios_du_fond = _mesurer_une_famille(
        jeu, PERTURBATIONS_DU_FOND, "Falsifier le FOND",
    )
    ratios_de_la_ponctuation = _mesurer_une_famille(
        jeu, PERTURBATIONS_DE_LA_PONCTUATION,
        "Falsifier la PONCTUATION STRUCTURANTE (aucun mot ne bouge)",
    )

    # 3. Un seuil de similarite separe-t-il ?
    a_recuperer = ratios_par_categorie.get("ponctuation", [])
    a_rejeter = (ratios_par_categorie.get("saut", [])
                 + ratios_par_categorie.get("reformulation", [])
                 + ratios_du_fond + ratios_de_la_ponctuation)
    print("\n=== Un seuil de similarite separe-t-il ? ===\n")
    print(f"  a RECUPERER (fond intact) : n={len(a_recuperer)}, "
          f"le plus BAS vaut {min(a_recuperer):.4f}")
    print(f"  a REJETER  (fond change)  : n={len(a_rejeter)}, "
          f"le plus HAUT vaut {max(a_rejeter):.4f}")
    if min(a_recuperer) > max(a_rejeter):
        print("  -> un seuil existe.")
    else:
        print("  -> AUCUN SEUIL NE SEPARE : les deux nuages se chevauchent.\n")
        for seuil in (0.99, 0.98, 0.95, 0.90):
            pris = sum(1 for ratio in a_recuperer if ratio >= seuil)
            faux = sum(1 for ratio in a_rejeter if ratio >= seuil)
            print(f"     seuil {seuil:.2f} : recupere {pris:3d}/{len(a_recuperer)}"
                  f" · BLANCHIT {faux:3d}/{len(a_rejeter)} citations fausses")

    # 4. La non-regression : ce qui passait doit passer.
    liens_valides = [
        lien for lien in SourceLink.objects.filter(
            etat_de_verification__in=["verifie", "faible"],
        ).select_related("extraction_source__job__page")[
            :TAILLE_DE_LA_NON_REGRESSION
        ]
        if lien.extraction_source
    ]
    for lien in liens_valides:
        texte_de_la_source(lien.extraction_source)

    depart = time.monotonic()
    tiennent = sum(
        1 for lien in liens_valides
        if _le_verbatim_est_present(
            lien.extraction_source.extraction_text,
            texte_de_la_source(lien.extraction_source),
        )
    )
    duree = time.monotonic() - depart
    nombre = len(liens_valides)
    print(f"\n=== Non-regression, sur {nombre} liens deja verifies ou faibles "
          f"===\n")
    print(f"  passent toujours : {tiennent} / {nombre}"
          f"   ({1000 * duree / nombre:.2f} ms par citation)")


if __name__ == "__main__":
    main()
