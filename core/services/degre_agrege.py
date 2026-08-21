"""
Le degre agrege : ce que les juges disent, en un seul nombre.
/ The aggregated degree: what the judges say, as one number.

LOCALISATION : core/services/degre_agrege.py

A QUOI IL SERT, ET A QUOI IL NE SERT PAS. Il colore la gouttiere d'une
affirmation, d'un rouge a un vert continus. Il ne s'affiche JAMAIS comme
un chiffre dans le corps de l'article (`PRESENTATION-V3.md` § 3.6) : la
rigueur est disponible au clic — la carte de preuve porte le detail par
juge — pas imposee a la lecture.

TROIS REGLES, chacune posee sur une mesure du 20 aout 2026 (836 avis
reels, 4 juges, 209 citations).
"""

# Un score exactement nul n'est pas un desaveu, c'est un juge qui n'a
# pas juge — troncature, chargement rate, sortie vide. Le compter ferait
# plonger le degre pour une panne. Aucun cas en base au 20 aout 2026 ;
# la garde protege l'avenir.
# / A zero is a failure, not a verdict.
SCORE_MINIMAL_POUR_COMPTER = 0.0

# L'exposant qui ETIRE les ecarts francs vers les bords.
#
# POURQUOI IL EST SOUS 1, ET POURQUOI C'EST NECESSAIRE. CamemBERTa v2 et
# mDeBERTa v3 sont dans leur bande de neutralite **85 % du temps** : une
# moyenne lineaire se tasserait autour de 50 et la gouttiere resterait
# d'une seule couleur sur tout l'article — un degre qui ne varie pas ne
# dit rien.
#
# La racine (exposant < 1) etire les ecarts moyens vers les bords SANS
# amplifier le bruit du centre : un ecart minuscule reste minuscule une
# fois eleve a la puissance, parce qu'il part de tres bas. C'est la
# multiplication par l'ACCORD qui protege du reste.
# / Below 1 on purpose: two judges are neutral 85 % of the time, and a
#   linear mean would flatten the gutter to a single colour.
EXPOSANT_D_ETIREMENT = 0.6


def _normalise_par_son_seuil(score, seuil):
    """
    Rend le score sur une echelle ou « au seuil » vaut 50, pour tous.
    / Rescales so that "at threshold" is 50 for every judge.

    POURQUOI CE N'EST PAS UN LUXE. Les quatre juges n'ont ni la meme
    echelle ni le meme seuil : `bge-m3` bascule a 70, `distilCamemBERT`
    a 63,7, les deux autres a ~50. Un `distilCamemBERT` a 59,9 est donc
    EN DESSOUS du sien — il dit NON — mais une moyenne brute le compte
    comme un « presque oui ».

    Mesure : sur les 209 citations notees, moyenne brute et moyenne
    normalisee **divergent de signe dans 17 % des cas**.
    / Raw and rescaled means disagree on the sign for 17 % of citations.
    """
    if seuil <= 0:
        return 50.0
    if score <= seuil:
        return 50.0 * score / seuil
    return 50.0 + 50.0 * (score - seuil) / (100.0 - seuil)


def degre_agrege(avis):
    """
    Le degre de 0 a 100 que les juges donnent a une citation.
    / The 0-100 degree the judges give a citation.

    LOCALISATION : core/services/degre_agrege.py

    FLUX :
    1. on ecarte les avis a zero — ce sont des pannes, pas des verdicts ;
    2. chaque score est ramene sur l'echelle ou son seuil vaut 50 ;
    3. on prend l'ecart moyen au centre — les neutres pesent zero, ils
       ne tirent nulle part ;
    4. on ETIRE cet ecart (racine) pour que les cas francs atteignent
       les bords malgre 85 % de neutres ;
    5. on le MULTIPLIE par l'accord — pencher n'est pas trancher.

    :param avis: des objets portant `score` et `seuil` (0 a 100).
    :return: un flottant de 0 a 100, ou **None** si personne n'a juge.
             `None` n'est PAS zero : 16 des 225 citations du carnet
             n'ont aucun avis, et les peindre « mauvaises » serait
             mentir. / None is not zero.
    """
    scores_utiles = [
        _normalise_par_son_seuil(un_avis.score, un_avis.seuil)
        for un_avis in avis
        if un_avis.score is not None
        and un_avis.score > SCORE_MINIMAL_POUR_COMPTER
    ]
    if not scores_utiles:
        return None

    # L'ecart signe au centre : positif = le juge confirme, negatif = il
    # dement, zero = il est pile a son seuil et ne pese sur rien.
    # / Signed distance from centre; a neutral judge weighs nothing.
    ecarts = [score - 50.0 for score in scores_utiles]
    ecart_moyen = sum(ecarts) / len(ecarts)

    # L'ACCORD : la part des juges qui vont dans le sens de la moyenne,
    # comptee en somme des signes. Quatre juges unanimes donnent 1 ;
    # deux contre deux donnent 0, et le degre revient au centre — on ne
    # SAIT pas, et c'est ce qu'il faut montrer.
    # / Agreement: unanimous gives 1, an even split gives 0.
    signes = [1 if ecart > 0 else -1 if ecart < 0 else 0 for ecart in ecarts]
    accord = abs(sum(signes)) / len(signes)

    amplitude = (abs(ecart_moyen) / 50.0) ** EXPOSANT_D_ETIREMENT
    sens = 1.0 if ecart_moyen >= 0 else -1.0
    degre = 50.0 + sens * 50.0 * amplitude * accord

    # Les arrondis flottants peuvent depasser d'un cheveu ; la gouttiere
    # n'a pas de couleur hors de [0, 100].
    # / Float rounding can overshoot; the gutter has no colour outside.
    return max(0.0, min(100.0, degre))


# L'ECART AU CENTRE au-dela duquel les juges locaux ne « penchent »
# plus : ils DEMENTENT.
#
# POURQUOI CE SEUIL, ET PAS ZERO. Sans lui, 44 citations sur 209
# seraient marquees — une sur cinq, donc du bruit qu'on cesse de voir.
# Avec lui, 16 le sont : 7,7 %, assez rare pour se remarquer, assez
# frequent pour se rencontrer. Pencher n'est pas dementir.
# / Without this guard the mark would fire on one citation in five.
ECART_MINIMAL_POUR_DEMENTIR = 15.0

# Le cran a partir duquel le juge de production CONFIRME. Son seuil vaut
# 45 et il ne rend que quatre valeurs — 0, 40, 70, 100 : la frontiere
# tombe donc entre 40 et 70, et aucune valeur ne s'y trouve.
# / The production judge returns only 0, 40, 70, 100; the boundary sits
#   between 40 and 70, where no value lands.
CRAN_DE_CONFIRMATION = 50.0


def tension_des_juges(avis, degre_de_production):
    """
    Les juges locaux DEMENTENT-ils franchement le juge de production ?
    / Do the local judges franky contradict the production judge?

    LOCALISATION : core/services/degre_agrege.py

    C'EST LE SEUL SIGNAL QUE LES LOCAUX APPORTENT VRAIMENT, et il a
    fallu une mesure pour s'en apercevoir. Sur 209 citations, la moitie
    sort de la bande neutre — mais **42 % de ce signal CONTREDIT** le
    cran de production. Un canal d'intensite, qui n'a pas de signe,
    aurait donc renforce un liseré ambre parce que les controleurs le
    rehabilitaient : il aurait affiche l'inverse de ce qui se passe.

    On ne rend donc que la contradiction, et seulement quand elle est
    FRANCHE.

    :param avis: les avis locaux (objets a `.score` et `.seuil`).
    :param degre_de_production: le degre du juge de production, ou None.
    :return: `"tension"`, `"accord"`, ou **None** quand il n'y a rien a
             dire — pas d'avis local, ou pas de reference a contredire.
             `None` n'est pas « accord » : affirmer l'accord quand
             personne n'a controle serait mentir.
    """
    if degre_de_production is None:
        return None
    degre_local = degre_agrege(avis)
    if degre_local is None:
        return None

    ecart = degre_local - 50.0
    if abs(ecart) < ECART_MINIMAL_POUR_DEMENTIR:
        return "accord"

    production_confirme = degre_de_production >= CRAN_DE_CONFIRMATION
    locaux_confirment = ecart > 0
    if production_confirme != locaux_confirment:
        return "tension"
    return "accord"
