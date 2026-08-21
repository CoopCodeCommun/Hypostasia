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


# Une phrase se termine par un point, un point d'interrogation ou
# d'exclamation — SUIVI DE SES MARQUEURS, qui se collent apres lui :
# « … informels.[[ext:13]] Un Open Badge… ». Chercher une ponctuation
# suivie d'une espace ne couperait NULLE PART dans un article source, et
# rendrait l'article entier comme une phrase unique — qui porte un
# marqueur, donc « 0 % de prose nue ».
# / The marker sits AFTER the period: the split must step over it.
MOTIF_DE_FIN_DE_PHRASE = re.compile(r"[.!?](?:\[\[ext:\d+\]\])*\s+")

# Un titre markdown ne cite jamais, et c'est normal.
# / A markdown heading never cites, and that is fine.
MOTIF_DE_TITRE = re.compile(r"^\s*#{1,6}\s")


def part_de_prose_sans_marqueur(texte_de_l_article):
    """
    Quelle part de l'article n'appuie sur RIEN. / Unsourced prose share.

    LOCALISATION : benchmarks/redaction/mesurer_les_redacteurs.py

    LA DEFINITION VOYAGE AVEC LE CHIFFRE. Une campagne anterieure a
    publie « Small 7-9 %, Large 4-5 %, Medium 0 % » sans dire ce qui
    etait compte, et aucune definition essayee depuis ne reproduit ces
    valeurs. Un pourcentage dont on ignore l'unite n'est pas une mesure.

    DEUX UNITES, parce qu'elles repondent a deux questions :

    - la PHRASE dit si l'auteur cite au fil du texte ou par blocs ;
    - le PARAGRAPHE dit s'il existe des pans entiers qui n'appuient sur
      rien. Un paragraphe qui porte UN marqueur n'est pas « sans
      source », meme si ses autres phrases n'en portent pas.

    LES TITRES SONT EXCLUS. Un titre de section ne cite jamais : le
    compter gonflerait la prose nue de tout article bien structure, et
    punirait le modele qui decoupe le mieux.
    """
    texte = texte_de_l_article or ""

    paragraphes = [
        bloc for bloc in texte.split("\n\n")
        if bloc.strip() and not MOTIF_DE_TITRE.match(bloc)
    ]
    paragraphes_sans_marqueur = sum(
        1 for bloc in paragraphes if not MOTIF_SIMPLE.search(bloc)
    )

    phrases = []
    for bloc in paragraphes:
        # On coupe APRES les marqueurs, jamais avant : ils appartiennent
        # a la phrase qui les precede, et c'est eux qui la rendent
        # sourcee. / We cut after the markers: they belong to the
        # sentence before them.
        debut = 0
        for coupure in MOTIF_DE_FIN_DE_PHRASE.finditer(bloc):
            phrases.append(bloc[debut:coupure.end()])
            debut = coupure.end()
        phrases.append(bloc[debut:])
        phrases = [phrase for phrase in phrases if phrase.strip()]
    phrases_sans_marqueur = sum(
        1 for phrase in phrases if not MOTIF_SIMPLE.search(phrase)
    )

    return {
        "phrases": len(phrases),
        "phrases_sans_marqueur": phrases_sans_marqueur,
        "part_des_phrases": (
            phrases_sans_marqueur / len(phrases) if phrases else 0.0
        ),
        "paragraphes": len(paragraphes),
        "paragraphes_sans_marqueur": paragraphes_sans_marqueur,
        "part_des_paragraphes": (
            paragraphes_sans_marqueur / len(paragraphes)
            if paragraphes else 0.0
        ),
    }


def mesurer_les_articles():
    """
    Ce que porte chaque article : format, citations, verdicts.
    / Per article: format, citations, verdicts.
    """
    articles = []
    for page in articles_du_carnet_etalon():
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


# Le carnet que ce banc mesure. / The notebook this bench measures.
NOM_DU_CARNET_ETALON = "Documents étalons"


def articles_du_carnet_etalon():
    """
    Les articles du carnet etalon, et EUX SEULS. / Reference articles only.

    LOCALISATION : benchmarks/redaction/mesurer_les_redacteurs.py

    POURQUOI CE FILTRE EXISTE. Le serveur de developpement est permanent
    et quelqu'un s'en sert : un wiki produit dans un autre carnet, sur un
    autre corpus, entrait dans les comptes de ce banc et faussait la
    garde des jobs comme la couverture. Constate le 19 aout 2026, pendant
    la campagne — une note et un wiki sur un tout autre sujet sont
    apparus entre deux passes.
    / The dev server is shared: articles from other notebooks would
    silently enter the counts.
    """
    return Page.objects.filter(
        appartenances_dossiers__dossier__name=NOM_DU_CARNET_ETALON,
    ).exclude(type_de_note=TypeDeNote.NOTE).distinct()


def controler_les_jobs_de_production(modele_attendu=None):
    """
    Refuse de mesurer si une production a echoue. / Refuses on failure.

    LOCALISATION : benchmarks/redaction/mesurer_les_redacteurs.py

    LE CONTROLE QUI MANQUAIT, ET CE QU'IL A COUTE. La campagne du
    19 aout 2026 attendait que « pending/processing » tombe a zero pour
    mesurer. **Un job en `error` satisfait cette condition.** Un article
    est donc reste celui d'une passe anterieure, ecrit sur 283
    extractions quand les cinq autres l'etaient sur 412 — et le rapport
    a titre « a perimetre fige ».

    LA GARDE NE PEUT PAS ETRE « AUCUN JOB EN ERREUR ». Trois jobs
    `error` vivent en base a demeure (deux seconds avis du juge local,
    un 503 historique) : une garde globale refuserait de mesurer a
    jamais. Elle porte donc sur LE DERNIER JOB DE PRODUCTION DE CHAQUE
    ARTICLE — celui dont le texte courant est le resultat.

    :param modele_attendu: le `model_choice` de la passe en cours. Un
        article produit par un autre modele signale une passe qui n'a
        pas tourne, ce qu'un simple `completed` ne dit pas.
    :return: la liste des problemes. Vide = on peut mesurer.
    """
    from hypostasis_extractor.models import ExtractionJob

    problemes = []
    for page in articles_du_carnet_etalon():
        dernier_job = (
            ExtractionJob.objects.filter(page=page)
            .exclude(raw_result__contains={"est_verification": True})
            .order_by("-pk").select_related("ai_model").first()
        )
        if dernier_job is None:
            problemes.append(f"« {page.title[:40]} » : aucun job de production")
            continue
        if dernier_job.status != "completed":
            problemes.append(
                f"« {page.title[:40]} » : job {dernier_job.pk} en "
                f"{dernier_job.status} — {dernier_job.error_message or 'sans message'}"
            )
            continue
        modele_du_job = (
            dernier_job.ai_model.model_choice if dernier_job.ai_model else None
        )
        if modele_attendu and modele_du_job != modele_attendu:
            problemes.append(
                f"« {page.title[:40]} » : produit par {modele_du_job}, "
                f"attendu {modele_attendu} — la passe n'a pas tourne"
            )
    return problemes


def mesurer_la_couverture_du_perimetre():
    """
    Combien d'extractions DISTINCTES chaque article cite, sur combien.
    / How many DISTINCT extractions each article cites, out of how many.

    LOCALISATION : benchmarks/redaction/mesurer_les_redacteurs.py

    LE COMPTE DE CITATIONS SEUL TROMPE. Un modele qui cite trois fois la
    meme extraction affiche trois citations et n'apporte qu'une preuve.
    La campagne du 19 aout mesurait 240 / 280 / 265 citations pour
    192 / 205 / 210 extractions distinctes : l'ecart de 40 fondait a 18,
    et le classement « le plus abondant » ne survivait pas.
    """
    from core.services.synthese import extractions_du_perimetre

    couverture = []
    for page in articles_du_carnet_etalon():
        # `extractions_du_perimetre` prend la PAGE de l'article, pas
        # l'enregistrement Wiki ou SyntheseDirigee : c'est elle qui
        # porte le lien vers l'un ou l'autre.
        # / It takes the article's Page, not the Wiki/Synthese row.
        taille_du_perimetre = extractions_du_perimetre(page).count()
        liens = SourceLink.objects.filter(
            page_cible=page, type_lien=TypeLien.CITE,
        )
        citees = set(liens.values_list("extraction_source_id", flat=True))

        # LA COUVERTURE SE COMPTE DANS LE PERIMETRE, PAS A COTE. Un
        # article ecrit sur un perimetre plus large cite des extractions
        # qui n'en font plus partie : les compter au numerateur d'un
        # denominateur qui les exclut peut donner « 100 % » a un article
        # qui n'a pas touche la moitie du perimetre.
        # / Cited-but-outside extractions would inflate the ratio.
        du_perimetre = set(
            extractions_du_perimetre(page).values_list("id", flat=True)
        )
        citees_du_perimetre = citees & du_perimetre

        couverture.append({
            "titre": page.title,
            "citations": liens.count(),
            "distinctes": len(citees),
            "hors_perimetre": len(citees - du_perimetre),
            "perimetre": taille_du_perimetre,
            "couverture": (
                len(citees_du_perimetre) / taille_du_perimetre
                if taille_du_perimetre else 0.0
            ),
        })
    return couverture


def main():
    print("\n=== EXTRACTION — le verbatim est le seul critère ===\n")
    print(f"{'modèle':26} {'notes':>5} {'extraits':>8} {'verbatim':>9} "
          f"{'médiane car.':>12}")
    for modele, mesure in sorted(mesurer_les_extracteurs().items()):
        taux = 100 * mesure["verbatim"] / max(mesure["extraits"], 1)
        print(f"{modele:26} {len(mesure['notes']):5} "
              f"{mesure['extraits']:8} {taux:8.0f}% "
              f"{statistics.median(mesure['longueurs']):12.0f}")

    print("\n=== CONTRÔLE DES JOBS — avant toute mesure ===\n")
    modele_attendu = os.environ.get("MODELE_ATTENDU") or None
    problemes = controler_les_jobs_de_production(modele_attendu)
    if problemes:
        print("  ⚠️  NE PAS MESURER — la production n'est pas saine :")
        for probleme in problemes:
            print(f"     · {probleme}")
    else:
        attendu = f" (modèle attendu : {modele_attendu})" if modele_attendu else ""
        print(f"  Tous les articles ont un job de production completed{attendu}.")

    print("\n=== COUVERTURE DU PÉRIMÈTRE ===\n")
    for mesure in mesurer_la_couverture_du_perimetre():
        print(f"  « {mesure['titre'][:38]} » : {mesure['citations']:3} citations "
              f"· {mesure['distinctes']:3} distinctes "
              f"(dont {mesure['hors_perimetre']:3} hors périmètre) "
              f"· périmètre {mesure['perimetre']:3} "
              f"· couverture {mesure['couverture']:.0%}")

    print("\n=== PROSE SANS AUCUN MARQUEUR ===\n")
    for page in articles_du_carnet_etalon():
        mesure = part_de_prose_sans_marqueur(page.text_readability or "")
        print(f"  « {page.title[:38]} » : "
              f"{mesure['part_des_phrases']:.0%} des phrases "
              f"({mesure['phrases_sans_marqueur']}/{mesure['phrases']}) · "
              f"{mesure['part_des_paragraphes']:.0%} des paragraphes "
              f"({mesure['paragraphes_sans_marqueur']}/{mesure['paragraphes']})")

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
