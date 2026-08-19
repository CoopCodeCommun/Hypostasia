"""
Banc MANUEL : comparer des rédacteurs et des extracteurs sur le corpus.
/ MANUAL bench: compare writers and extractors on the demo corpus.

LOCALISATION : benchmarks/redaction/mesurer_les_redacteurs.py

CE QU'IL MESURE, ET CE QU'IL NE MESURE PAS. Il LIT la base et n'y écrit
rien : il rend l'état d'une comparaison déjà produite. Les productions
elles-mêmes se lancent par les commandes de gestion (voir le protocole
en bas), parce qu'elles passent par le VRAI chemin — le même prompt, le
même indexeur, le même juge que la production.

DEUX ÉTAGES, DEUX QUESTIONS DIFFÉRENTES :

- **l'extraction** se juge au VERBATIM. Une extraction qui n'est pas
  littéralement dans sa source casse la chaîne de preuve : la
  vérification la marquera `INTROUVABLE`, et aucun rédacteur ne peut
  rattraper ça ;
- **la rédaction** se juge au nombre de citations EXPLOITABLES et à leur
  force. Un modèle qui groupe ses marqueurs (`[[ext:1, ext:2]]`) au lieu
  de les enchaîner en perdait la totalité avant le repli du 19 août ; le
  compte de groupes réécrits reste donc un signal de qualité.

CE SCRIPT N'APPELLE AUCUN MODÈLE et n'écrit rien.
"""

import os
import re
import statistics
import sys
import unicodedata
from collections import defaultdict

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hypostasia.settings")
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."),
))
django.setup()

from core.models import (  # noqa: E402
    ElementDocument, Page, SourceLink, TypeDeNote, TypeLien,
)
from hypostasis_extractor.models import ExtractedEntity  # noqa: E402

MOTIF_GROUPE = re.compile(r"\[\[ext:\d+(?:\s*,\s*ext:\d+)+\]\]")
MOTIF_SIMPLE = re.compile(r"\[\[ext:(\d+)\]\]")


def _normalise(texte):
    """NFKC, apostrophes droites, espaces écrasés — comme la vérification."""
    texte = unicodedata.normalize("NFKC", texte or "").replace("’", "'")
    return " ".join(texte.split())


def mesurer_les_extracteurs():
    """
    Le verbatim, modèle par modèle. / Verbatim rate, per model.

    LE SEUL CRITÈRE QUI COMPTE ICI. Le nombre d'extraits ne dit rien :
    un modèle qui recopie des tours de parole entiers en produit peu et
    ancre mal ; un qui découpe fin en produit beaucoup. Ce qui décide,
    c'est qu'elles soient RETROUVABLES dans leur source.
    """
    textes_de_source = {}

    def source_de(identifiant_de_page):
        if identifiant_de_page not in textes_de_source:
            textes_de_source[identifiant_de_page] = _normalise("\n".join(
                ElementDocument.objects
                .filter(page_id=identifiant_de_page)
                .order_by("ordre").values_list("texte", flat=True)
            ))
        return textes_de_source[identifiant_de_page]

    par_modele = defaultdict(
        lambda: {"extraits": 0, "verbatim": 0, "longueurs": [], "notes": set()}
    )
    for extraction in ExtractedEntity.objects.select_related(
        "job", "job__ai_model",
    ).iterator():
        if not extraction.job.ai_model:
            continue
        texte_de_la_source = source_de(extraction.job.page_id)
        if not texte_de_la_source:
            continue
        mesure = par_modele[extraction.job.ai_model.model_choice]
        mesure["extraits"] += 1
        mesure["notes"].add(extraction.job.page_id)
        mesure["longueurs"].append(len(extraction.extraction_text or ""))
        if _normalise(extraction.extraction_text) in texte_de_la_source:
            mesure["verbatim"] += 1
    return par_modele


def mesurer_les_articles():
    """
    Ce que porte chaque article : format, citations, verdicts.
    / Per article: format, citations, verdicts.
    """
    articles = []
    for page in Page.objects.exclude(type_de_note=TypeDeNote.NOTE):
        texte = page.text_readability or ""
        liens = SourceLink.objects.filter(
            page_cible=page, type_lien=TypeLien.CITE,
        )
        etats = defaultdict(int)
        degres = defaultdict(int)
        for lien in liens:
            etats[lien.etat_de_verification] += 1
            if lien.score_de_verification is not None:
                degres[lien.score_de_verification] += 1
        articles.append({
            "genre": page.type_de_note,
            "titre": page.title,
            "caracteres": len(texte),
            "renvois": len(MOTIF_SIMPLE.findall(texte)),
            # Un groupe RESTANT signale que le repli n'a pas tourné —
            # worker au code périmé, ou chemin d'indexation oublié.
            # / A remaining group means the fallback did not run.
            "groupes_restants": len(MOTIF_GROUPE.findall(texte)),
            "liens": liens.count(),
            "etats": dict(etats),
            "degres": dict(sorted(degres.items())),
        })
    return articles


def main():
    print("\n=== EXTRACTION — le verbatim est le seul critère ===\n")
    print(f"{'modèle':26} {'notes':>5} {'extraits':>8} {'verbatim':>9} "
          f"{'médiane car.':>12}")
    for modele, mesure in sorted(mesurer_les_extracteurs().items()):
        taux = 100 * mesure["verbatim"] / max(mesure["extraits"], 1)
        print(f"{modele:26} {len(mesure['notes']):5} "
              f"{mesure['extraits']:8} {taux:8.0f}% "
              f"{statistics.median(mesure['longueurs']):12.0f}")

    print("\n=== ARTICLES — état courant de la base ===\n")
    for article in mesurer_les_articles():
        print(f"  {article['genre']:9} {article['caracteres']:6} car · "
              f"{article['renvois']:3} renvois · {article['liens']:3} liens "
              f"· {article['groupes_restants']} groupe(s) restant(s)")
        print(f"            états {article['etats']}")
        print(f"            degrés {article['degres']}")

    print("""
LE PROTOCOLE, pour rejouer une comparaison de rédacteurs :

  1. figer le périmètre : ne PLUS lancer d'extraction entre les passes,
     sinon les rédacteurs n'écrivent pas sur le même matériau ;
  2. pour chaque modèle :
       manage.py affecter_un_modele_a_un_role --role redacteur_d_article --modele <id>
       manage.py produire_les_syntheses_etalons --forcer
       (attendre la fin des tâches Celery)
       manage.py shell -c "…"  # sauvegarder le texte AVANT la passe suivante
       manage.py verifier_les_citations_etalons --forcer
       benchmarks/redaction/mesurer_les_redacteurs.py
  3. REDÉMARRER LES WORKERS après toute modification de code : ils
     tournent sinon avec l'ancien, et le 19 août c'est ce qui a fait
     rater le repli sur une des deux productions.
""")


if __name__ == "__main__":
    main()
