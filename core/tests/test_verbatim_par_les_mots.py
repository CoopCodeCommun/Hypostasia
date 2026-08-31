"""
Le controle verbatim compare LES MOTS, pas les caracteres.
/ The verbatim check compares WORDS, not characters.

LOCALISATION : core/tests/test_verbatim_par_les_mots.py

CE QUE CE TEST PROTEGE. Le controle verbatim decide si une citation est
retrouvable dans sa source. S'il echoue, le lien part en INTROUVABLE et
la chaine de preuve est declaree cassee — l'affirmation la plus forte
que ce produit sache faire sur une citation.

Mesure du 30 aout 2026 : sur 119 liens INTROUVABLE, **45 n'avaient
AUCUN defaut de fond** — tous les mots y etaient, dans l'ordre, d'un
seul tenant. Seuls des signes differaient : un tiret cadratin pour un
tiret court, un guillemet droit pour une apostrophe, un trait d'union
que notre ingestion avait detache.

LA REGLE, ET POURQUOI ELLE EST PLUS SURE QUE L'ANCIENNE. Les mots de la
citation doivent se lire tels quels dans la source, dans l'ordre et sans
trou. Ce qui n'est pas un mot ne compte pas — SAUF les signes qui
changent ce que la source DIT : parentheses, guillemets, deux-points,
« ? » et « ! ». C'est donc plus STRICT sur ce qui porte le sens, et
indifferent au reste.

CE QU'UN SCORE DE SIMILARITE AURAIT FAIT, ET POURQUOI IL A ETE ECARTE.
Mesure du meme jour : la citation honnete la plus abimee obtient 0,9577,
et la citation FALSIFIEE la mieux notee obtient 0,9970. Aucun seuil ne
les separe. Un chiffre change — 2011 en 2012, un caractere sur cent
cinquante — obtient 0,9961. Une similarite est unidimensionnelle : elle
additionne « trois signes de ponctuation » et « une date falsifiee »
dans le meme nombre.

Banc : benchmarks/extraction_format/mesurer_la_comparaison_par_les_mots.py
Dossier : PLAN/TODO/2026-08-30-ce-qui-reste-du-verbatim-introuvable.md
"""

from django.test import SimpleTestCase

from core.services.verification import _le_verbatim_est_present


class LeVerbatimSeLitParLesMots(SimpleTestCase):
    """Les 45 citations au fond intact. / The 45 sound quotes."""

    def test_un_tiret_cadratin_vaut_un_tiret_court(self):
        """
        LE PREMIER ECART DU CORPUS — 17 occurrences. La source porte un
        tiret court, le modele rend un cadratin. Aucun mot ne bouge.
        / The most frequent gap: a dash rendered as an em dash.
        """
        source = "les badges - et leurs limites - sont un objet technique"

        self.assertTrue(_le_verbatim_est_present(
            "les badges — et leurs limites — sont un objet technique", source,
        ))

    def test_un_guillemet_droit_vaut_une_apostrophe_droite(self):
        """
        DEUXIEME ECART — 11 occurrences, toutes des citations imbriquees.
        La source ecrit "illusion de transparence", le modele rend
        'illusion de transparence'. Le signe reste un guillemet.
        / A straight quote rendered as a straight apostrophe.
        """
        source = 'au risque d\'une "illusion de transparence" induite'

        self.assertTrue(_le_verbatim_est_present(
            "au risque d'une 'illusion de transparence' induite", source,
        ))

    def test_un_trait_d_union_DETACHE_par_la_source_est_le_MEME_trait(self):
        """
        LE DEFAUT EST LE NOTRE, PAS CELUI DU MODELE. L'ingestion detache
        le trait d'union — « savoir -faire » — et le modele le recolle,
        comme n'importe quel lecteur. Huit elements en base le portent.

        C'est la meme famille que l'espace avant le point, corrigee dans
        le moteur le 22 aout : le tiret, lui, ne l'a pas ete.
        / Ingestion detaches the hyphen; the model puts it back.
        """
        source = "des connaissances, un savoir -faire ou un savoir -etre"

        self.assertTrue(_le_verbatim_est_present(
            "un savoir-faire ou un savoir-etre", source,
        ))

    def test_une_citation_peut_s_arreter_dans_un_mot_SOUDE_par_la_source(self):
        """
        83 ELEMENTS EN BASE PORTENT DES MOTS SOUDES. Deux blocs recolles
        sans separateur : « participation citoyenneAucun parlementaire ».
        Une citation honnete s'y arrete au milieu du mot soude.

        La coupe n'est toleree QUE devant une majuscule ou un chiffre —
        c'est la signature d'une soudure. Devant une minuscule, c'est un
        mot coupe, et le test « JAMAIS au milieu d'un mot » l'interdit.
        / Welded words: the cut is tolerated only before a capital.
        """
        source = "comites constituants et participation citoyenneAucun"

        self.assertTrue(_le_verbatim_est_present(
            "et participation citoyenne", source,
        ))

    def test_une_citation_peut_COMMENCER_dans_un_mot_soude(self):
        """La soudure vaut aux deux bouts. / Welding cuts both ways."""
        source = "comites constituants et participation citoyenneAucun"

        self.assertTrue(_le_verbatim_est_present("Aucun", source))

    def test_le_verbatim_exact_passe_toujours(self):
        """La regle stricte reste la definition de reference."""
        self.assertTrue(_le_verbatim_est_present(
            "trois categories", "On distingue trois categories d'usage.",
        ))


class LeVerbatimNeToleredJAMAISUnSIGNEQuiPorteLeSens(SimpleTestCase):
    """
    LA PARTIE QUI COMPTE, et elle est neuve. Ignorer TOUTE la ponctuation
    aurait blanchi ces cas : mesure du 30 aout, 17 parentheses sur 19 et
    18 guillemets sur 64 passaient. Chacun change ce que la source DIT
    sans changer un seul mot.
    / Ignoring ALL punctuation would launder these: each changes meaning
    without changing a single word.
    """

    def test_une_parenthese_d_incise_RETIREE_reste_introuvable(self):
        """
        La source met une reserve entre parentheses ; la citation la
        fond dans la phrase. Les mots sont les memes, la portee non.
        / The source brackets a caveat; the quote melts it into the text.
        """
        self.assertFalse(_le_verbatim_est_present(
            "les badges sont reconnus sauf par les employeurs",
            "les badges sont reconnus (sauf par les employeurs)",
        ))

    def test_un_deux_points_RETIRE_reste_introuvable(self):
        """
        « il refuse : les badges » annonce une liste. Sans le
        deux-points, la phrase affirme autre chose.
        / A colon announces; without it the sentence asserts.
        """
        self.assertFalse(_le_verbatim_est_present(
            "il refuse les badges numeriques",
            "il refuse : les badges numeriques",
        ))

    def test_des_guillemets_RETIRES_restent_introuvables(self):
        """
        LE CAS LE PLUS GRAVE DE CETTE CLASSE. La source met un propos a
        DISTANCE — « comme « l'ecole descolarise » » — et la citation le
        rend en son nom propre. Le sens s'inverse : ce que l'auteur
        rapportait, il semble l'affirmer.
        / The source quotes at a distance; without the marks the author
        seems to assert it.
        """
        self.assertFalse(_le_verbatim_est_present(
            "des constats simplifies comme l'ecole descolarise",
            "des constats simplifies comme « l'ecole descolarise »",
        ))

    def test_une_question_AU_MILIEU_devenue_affirmation_reste_introuvable(self):
        """
        La garde de fin ne regarde que le dernier signe. Un « ? » AU
        MILIEU de la citation lui echappe : ce sont les signes internes
        qui le tiennent.
        / The end guard only sees the last mark; internal marks need
        their own check.
        """
        self.assertFalse(_le_verbatim_est_present(
            "Faut-il evaluer. Nous le pensons",
            "Faut-il evaluer ? Nous le pensons",
        ))

    def test_une_question_FINALE_devenue_affirmation_reste_introuvable(self):
        """La garde de fin, qui existait deja, doit survivre au changement."""
        self.assertFalse(_le_verbatim_est_present(
            "Comment evaluer un travail dont on ignore l'auteur.",
            "Comment evaluer un travail dont on ignore l'auteur ?",
        ))

    def test_une_negation_inseree_reste_introuvable(self):
        """Deux mots de plus, et la source dit l'inverse."""
        self.assertFalse(_le_verbatim_est_present(
            "les badges ne sont pas reconnus par les employeurs",
            "les badges sont reconnus par les employeurs",
        ))

    def test_UN_CHIFFRE_change_reste_introuvable(self):
        """
        LE CAS QUI A TUE LE SCORE DE SIMILARITE. Un caractere sur cent
        cinquante — et il obtient 0,9961 de ratio, mieux que la moitie
        des citations honnetes. Un mot different reste un mot different.
        / One character in a hundred and fifty; a similarity ratio
        cannot see it, a word comparison can.
        """
        self.assertFalse(_le_verbatim_est_present(
            "le College de Rosemont decerne des badges depuis 2015",
            "le College de Rosemont decerne des badges depuis 2014",
        ))

    def test_une_citation_ne_s_arrete_JAMAIS_au_milieu_d_un_mot(self):
        """
        LE TROU QUE LA TOLERANCE DES SOUDURES POURRAIT ROUVRIR, ET IL
        INVERSE LE SENS. « Le vaccin est sur. » se retrouverait dans
        « le vaccin est surement inefficace ».

        La tolerance ne vaut que devant une MAJUSCULE — la signature
        d'une soudure de blocs. Devant une minuscule, c'est un mot coupe.
        / Welding tolerance must never let a quote end mid-word.
        """
        self.assertFalse(_le_verbatim_est_present(
            "Le vaccin est sur.",
            "des essais montrent que le vaccin est surement inefficace",
        ))

    def test_un_saut_de_passage_reste_introuvable(self):
        """
        Deux passages litteraux colles SANS marque : chaque mot existe,
        la phrase non. Les mots doivent etre CONTIGUS.
        / Two literal passages welded: every word exists, the sentence
        does not.
        """
        self.assertFalse(_le_verbatim_est_present(
            "les badges sont reconnus les employeurs les ignorent",
            "les badges sont reconnus. Beaucoup de choses se disent. "
            "Pourtant les employeurs les ignorent",
        ))

    def test_une_enumeration_ne_blanchit_JAMAIS_un_nombre_decimal(self):
        """
        LA GARDE DES CHIFFRES, qui doit survivre au changement d'unite.
        Comparer par mots decoupe « 3,5 » en deux mots « 3 » et « 5 » —
        exactement ceux de l'enumeration « 3, 5 et 8 ». Sans garde, la
        chaine de preuve validerait un chiffre que la source n'avance
        NULLE PART.
        / Word comparison splits a decimal into the enumeration's digits.
        """
        self.assertFalse(_le_verbatim_est_present(
            "Les niveaux 3,5", "Les niveaux 3, 5 et 8 sont concernes",
        ))

    def test_un_point_DECIMAL_n_est_pas_une_marque_de_fin(self):
        """
        « La note 7. » ne se retrouve pas dans « la note 7.5 ».

        LA MAJUSCULE INITIALE N'EST PAS UN DETAIL DE REDACTION : sans
        elle, la citation serait une sous-chaine EXACTE de la source et
        le test strict l'accepterait — on eprouverait le controle
        d'origine au lieu des passes tolerantes.
        / The capital matters: without it the strict pass would match,
        and this test would prove nothing about the tolerant passes.
        """
        self.assertFalse(_le_verbatim_est_present(
            "La note 7.", "la note 7.5 sur dix",
        ))

    def test_un_propos_laisse_en_suspens_ne_se_ferme_pas(self):
        """La source suspend, la citation clot."""
        self.assertFalse(_le_verbatim_est_present(
            "il viendra.", "il viendra … mais on ignore quand",
        ))

    def test_un_mot_change_reste_introuvable(self):
        """Le fond a bouge : aucune regle de forme ne le rattrape."""
        self.assertFalse(_le_verbatim_est_present(
            "On distingue quatre categories",
            "On distingue trois categories d'usage.",
        ))
