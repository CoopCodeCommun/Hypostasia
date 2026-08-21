"""
Le controle verbatim tolere la FORME, jamais le FOND.
/ The verbatim check tolerates SHAPE, never SUBSTANCE.

LOCALISATION : core/tests/test_verbatim_tolerant_a_la_forme.py

CE QUE CE TEST PROTEGE. Le controle verbatim decide si une citation est
retrouvable dans sa source. S'il echoue, le lien part en INTROUVABLE et
la chaine de preuve est declaree cassee — c'est l'affirmation la plus
forte que ce produit sache faire sur une citation.

La mesure du 19 aout 2026 a montre que 34 des 60 INTROUVABLE ne
tenaient pas au fond : un point ajoute, une majuscule d'amorce, un
espace de ponctuation. Et que la cause dominante venait de NOTRE
ingestion, qui detache les points de leurs mots.

Elargir ce controle est donc un ARBITRAGE, et le danger est d'en
elargir trop : une regle de forme qui laisserait passer un changement de
SENS blanchirait une citation fausse. Les tests « ne doit JAMAIS » plus
bas sont la partie qui compte.

Detail : benchmarks/extraction_format/2026-08-19_le-mode-d-echec-du-verbatim.md
"""

from django.test import SimpleTestCase

from core.services.verification import _le_verbatim_est_present


class LeVerbatimToleredesRetouchesDeForme(SimpleTestCase):
    """Les trois regles adoptees. / The three adopted rules."""

    def test_un_point_final_ajoute_ne_casse_plus_la_chaine_de_preuve(self):
        """
        Le modele cite un item de liste et le termine par un point, pour
        en faire une phrase. Rien du sens n'a bouge.
        / The model turns a list item into a sentence. Meaning unchanged.
        """
        source = "Les usages : l'aide a la redaction, l'evaluation automatisee"

        self.assertTrue(_le_verbatim_est_present(
            "l'aide a la redaction, l'evaluation automatisee.", source,
        ))

    def test_une_majuscule_d_amorce_ne_casse_plus_la_chaine_de_preuve(self):
        """Le modele capitalise le premier mot de ce qu'il cite."""
        source = "on distingue trois categories d'usage de l'IA."

        self.assertTrue(_le_verbatim_est_present(
            "On distingue trois categories", source,
        ))

    def test_un_espace_de_ponctuation_de_la_source_ne_casse_plus_rien(self):
        """
        LA CAUSE LA PLUS FREQUENTE, et elle vient de NOUS. L'ingestion
        detache la ponctuation de son mot — « IMS Global , un » — et le
        modele la recolle. Lui refuser sa citation reviendrait a le punir
        pour la qualite de notre propre decoupage.
        / The most frequent cause, and it is ours: ingestion detaches
        punctuation and the model puts it back.
        """
        source = "developpe par IMS Global , un consortium international"

        self.assertTrue(_le_verbatim_est_present(
            "developpe par IMS Global, un consortium international", source,
        ))

    def test_une_majuscule_LEGITIME_de_la_source_ne_bloque_rien(self):
        """
        LA REGLE 1 EST UNE TOLERANCE, PAS UNE TRANSFORMATION. Forcer la
        premiere lettre en minuscule casse les citations qui commencent
        par un mot legitimement capitalise dans la source — un nom
        propre, un debut de phrase. La comparaison doit accepter LES
        DEUX casses, pas en imposer une.

        Mesure : sur le perimetre de 137 extractions, la version qui
        forcait la minuscule ne rattrapait qu'UNE extraction sur 21, la
        ou le banc en annoncait neuf.
        / Rule 1 accepts both cases; it must not impose one.
        """
        source = "developpe par IMS Global , un consortium international"

        self.assertTrue(_le_verbatim_est_present(
            "Global, un consortium international", source,
        ))

    def test_un_point_DETACHE_par_la_source_est_le_MEME_point(self):
        """
        LE CAS LE PLUS FREQUENT DU CORPUS, et le plus subtil. La source
        porte « interoperabilite . Qui sont les membres » — le point est
        bien la, simplement detache par l'ingestion. Le modele le
        recolle : « interoperabilite. »

        Ce n'est NI un point ajoute, NI un point substitue : c'est le
        MEME point. Une garde qui refuse des que la source porte une
        marque de fin rejette ce cas — et laisse passer a cote de la
        moitie des citations recuperables.
        / Neither added nor substituted: the very same period.
        """
        source = "une garantie de perennite . Qui sont les membres ?"

        self.assertTrue(_le_verbatim_est_present(
            "une garantie de perennite.", source,
        ))

    def test_le_verbatim_exact_passe_toujours(self):
        """La regle d'avant n'a pas bouge. / The old rule still holds."""
        self.assertTrue(_le_verbatim_est_present(
            "trois categories", "On distingue trois categories d'usage.",
        ))


class LeVerbatimNeToleredJAMAISUnChangementDeSens(SimpleTestCase):
    """
    LA PARTIE QUI COMPTE. Chacun de ces cas blanchirait une citation que
    la source n'etablit pas.
    / Each of these would launder a quote the source does not support.
    """

    def test_un_mot_change_reste_introuvable(self):
        """Le fond a bouge : aucune regle de forme ne le rattrape."""
        self.assertFalse(_le_verbatim_est_present(
            "On distingue quatre categories",
            "On distingue trois categories d'usage.",
        ))

    def test_une_enumeration_ne_blanchit_JAMAIS_un_nombre_decimal(self):
        """
        LE CONTRE-EXEMPLE QUI JUSTIFIE LA GARDE DES CHIFFRES. Ecraser
        l'espace autour d'une virgule transforme l'enumeration « les
        niveaux 3, 5 et 8 » en decimal « les niveaux 3,5 » — un chiffre
        que la source n'avance NULLE PART.

        Vaut pour les dates, les montants, les versions, les references
        d'article. La regle ne s'applique donc jamais entre deux
        chiffres.
        / An enumeration must never launder a decimal.
        """
        self.assertFalse(_le_verbatim_est_present(
            "Les niveaux 3,5", "Les niveaux 3, 5 et 8 sont concernes",
        ))

    def test_la_garde_des_chiffres_tient_entre_parentheses(self):
        """
        MEME PIEGE, AUTRE DISPOSITION. Si l'ecrasement CONSOMME le
        chiffre qui suit la parenthese, la virgule ne voit plus qu'un
        voisin et la garde tombe.
        / The bracket must not eat the digit the comma's guard needs.
        """
        self.assertFalse(_le_verbatim_est_present(
            "3,5", "les niveaux ( 3 , 5 ) sont concernes",
        ))

    def test_la_garde_des_chiffres_tient_sur_trois_nombres(self):
        """Deux virgules qui se suivent : la premiere ne consomme rien."""
        self.assertFalse(_le_verbatim_est_present(
            "2,3", "les niveaux 1 , 2 , 3 sont concernes",
        ))

    def test_une_question_devenue_affirmation_reste_introuvable(self):
        """
        Passer d'une question a une affirmation change ce que la source
        DIT. Ce n'est pas un point ajoute, c'est un point SUBSTITUE.
        / Turning a question into a statement changes the meaning.
        """
        self.assertFalse(_le_verbatim_est_present(
            "Comment evaluer un travail dont on ignore l'auteur.",
            "Comment evaluer un travail dont on ignore l'auteur ?",
        ))

    def test_un_propos_laisse_en_suspens_ne_se_ferme_pas(self):
        """
        La source suspend son propos ; la citation le clot. NFKC rend
        « … » en trois points, donc c'est le « . » qui doit garder.
        / The source suspends, the quote closes it.
        """
        self.assertFalse(_le_verbatim_est_present(
            "il viendra.", "il viendra … mais on ignore quand",
        ))

    def test_une_citation_ne_s_arrete_JAMAIS_au_milieu_d_un_mot(self):
        """
        LE TROU LE PLUS GRAVE, ET IL INVERSE LE SENS. Retirer le point
        final raccourcit ce qu'on cherche, donc permet a la recherche de
        tomber a l'INTERIEUR d'un mot : « Le vaccin est sur. » se
        retrouverait dans « le vaccin est surement inefficace », et la
        chaine de preuve validerait le CONTRAIRE de ce que la source dit.

        Le controle strict ne pouvait pas produire cela — le point du
        texte cite devait exister tel quel dans la source. C'est la
        tolerance qui ouvre ce trou, c'est donc a elle de le fermer.
        / Stripping the period lets the match land mid-word and can
        invert the meaning. Only the tolerance can open this; it closes it.
        """
        self.assertFalse(_le_verbatim_est_present(
            "Le vaccin est sur.",
            "des essais montrent que le vaccin est surement inefficace",
        ))
        self.assertFalse(_le_verbatim_est_present(
            "Le traitement est efficace.",
            "le traitement est efficacement bloque par la molecule",
        ))

    def test_un_point_DECIMAL_n_est_pas_une_marque_de_fin(self):
        """
        « La note 7. » ne doit pas se retrouver dans « la note 7.5 ».
        Le point qui precede un CHIFFRE n'est pas une fin de phrase :
        c'est une decimale ou un numero de version, et la citation
        chiffrerait alors autre chose que la source.
        / A period before a digit is a decimal, not a sentence end.
        """
        self.assertFalse(_le_verbatim_est_present(
            "Il a obtenu la note 7.", "il a obtenu la note 7.5 au concours",
        ))
        self.assertFalse(_le_verbatim_est_present(
            "La version 2.", "la version 2.1 est sortie en mars",
        ))
        # Meme piege, avec le point DETACHE que la garde des chiffres
        # laisse volontairement en place. / Same trap, detached period.
        self.assertFalse(_le_verbatim_est_present(
            "La note 7.", "la note 7 .5 est requise",
        ))

    def test_une_citation_vide_reste_introuvable(self):
        """
        Une chaine vide est sous-chaine de TOUT. La regle du point final
        la fabrique a partir d'un simple « . ».
        / The empty string is a substring of everything.
        """
        self.assertFalse(_le_verbatim_est_present("", "un texte source"))
        self.assertFalse(_le_verbatim_est_present(".", "un texte source"))
