"""
Le degre agrege : ce que les juges disent, en un seul nombre.
/ The aggregated degree: what the judges say, as one number.

LOCALISATION : core/tests/test_degre_agrege.py

CE QU'IL DOIT RENDRE, ET POURQUOI CHAQUE REGLE EXISTE.

Ce nombre ne s'affiche JAMAIS dans le corps d'un article
(`PRESENTATION-V3.md` § 3.6) : il colore la gouttiere, et c'est tout. Il
doit donc etre lisible D'UN COUP D'OEIL, ce qui interdit deux choses —
qu'il mente, et qu'il ne varie pas.

TROIS PROPRIETES, chacune mesuree sur les 836 avis reels du 20 aout :

1. **La normalisation par le SEUIL de chaque juge.** Les quatre n'ont ni
   la meme echelle ni le meme seuil : `distilCamemBERT` a 59,9 est EN
   DESSOUS du sien (63,7) — il dit NON — mais une moyenne brute le
   compte comme un « presque oui ». Mesure : moyenne brute et moyenne
   normalisee divergent de SIGNE sur **17 % des citations**.

2. **Une amplitude NON LINEAIRE.** CamemBERTa v2 et mDeBERTa v3 sont
   dans leur bande de neutralite **85 % du temps** : une moyenne lineaire
   se tasserait autour de 50 et la couleur ne montrerait rien. La racine
   ETIRE les ecarts francs vers les bords sans amplifier le bruit du
   centre, qui reste ecrase par sa propre petitesse.

3. **Un facteur d'ACCORD.** Trois juges mous dans le meme sens ne valent
   pas trois juges francs : le degre doit dire que les juges sont
   d'accord ET surs, pas seulement qu'ils penchent.
"""

from django.test import SimpleTestCase

from core.services.degre_agrege import degre_agrege


def _avis(score, seuil):
    """Un avis minimal, sans base. / A minimal opinion, DB-free."""
    return type("Avis", (), {"score": score, "seuil": seuil})()


class LeDegreAgregeDitCeQueLesJugesDisent(SimpleTestCase):
    """Les cas nominaux. / The nominal cases."""

    def test_sans_aucun_avis_il_n_y_a_PAS_de_degre(self):
        """
        Absence d'avis n'est pas un zero. 16 des 225 citations du carnet
        n'ont aucun avis : leur donner 0 les peindrait « mauvaises »
        alors que personne ne les a jugees.
        / No opinion is not a zero.
        """
        self.assertIsNone(degre_agrege([]))

    def test_tous_les_juges_au_seuil_donnent_cinquante(self):
        """
        « Au seuil » vaut 50 pour tout le monde — c'est le point de
        bascule de chaque juge, quelle que soit son echelle.
        / At-threshold is 50 for everyone.
        """
        avis = [_avis(49.7, 49.7), _avis(50.0, 50.0),
                _avis(70.0, 70.0), _avis(63.7, 63.7)]

        self.assertAlmostEqual(degre_agrege(avis), 50.0, places=1)

    def test_quatre_juges_francs_et_unanimes_vont_vers_le_bord(self):
        """
        LA PROPRIETE QUE LE MAINTENEUR A DEMANDEE : quand tous les juges
        sont surs ET d'accord, ca doit se voir. Une moyenne lineaire
        rendrait 95 ; l'amplitude non lineaire pousse plus haut encore.
        / When all judges are sure and agree, it must show.
        """
        avis = [_avis(95.0, 49.7), _avis(95.0, 50.0),
                _avis(95.0, 70.0), _avis(95.0, 63.7)]

        self.assertGreater(degre_agrege(avis), 90.0)

    def test_quatre_juges_francs_et_unanimement_CONTRE(self):
        """La symetrie : le desaveu unanime se voit autant."""
        avis = [_avis(5.0, 49.7), _avis(5.0, 50.0),
                _avis(5.0, 70.0), _avis(5.0, 63.7)]

        self.assertLess(degre_agrege(avis), 10.0)

    def test_un_desaccord_franc_ramene_au_centre(self):
        """
        Deux juges tres pour, deux tres contre : on ne SAIT pas. Le
        centre est la bonne reponse — pas une moyenne qui ferait croire
        a un demi-accord.
        / A split verdict means we do not know.
        """
        avis = [_avis(95.0, 49.7), _avis(95.0, 50.0),
                _avis(5.0, 70.0), _avis(5.0, 63.7)]

        self.assertAlmostEqual(degre_agrege(avis), 50.0, delta=5.0)

    def test_deux_neutres_et_un_franchement_positif_TENDENT_AU_POSITIF(self):
        """
        LE CAS POSE PAR LE MAINTENEUR, mot pour mot : « si il y a deux
        neutres et un positif bge-m3, ca tendra vers le positif ». Oui —
        les neutres ne tirent pas vers le bas, ils ne tirent nulle part.
        / The maintainer's own case: neutrals pull nowhere.
        """
        avis = [_avis(51.8, 49.7), _avis(50.0, 50.0),
                _avis(98.0, 70.0), _avis(63.7, 63.7)]

        degre = degre_agrege(avis)

        self.assertGreater(degre, 60.0)


class LeDegreAgregeNeSeLaissePasTromper(SimpleTestCase):
    """Les pieges mesures sur les donnees reelles. / Measured traps."""

    def test_un_juge_SOUS_son_seuil_tire_vers_le_bas_meme_au_dessus_de_50(self):
        """
        LE PIEGE QUI JUSTIFIE LA NORMALISATION. `distilCamemBERT` a 59,9
        est 4 points SOUS son seuil de 63,7 : il dit NON. Une moyenne
        brute le lirait « presque oui » — et se trompe de signe sur 17 %
        des citations reelles.
        / A judge below its own threshold says NO, whatever the raw
        number looks like.
        """
        sous_son_seuil = degre_agrege([_avis(59.9, 63.7)])
        au_dessus = degre_agrege([_avis(59.9, 50.0)])

        self.assertLess(sous_son_seuil, 50.0)
        self.assertGreater(au_dessus, 50.0)

    def test_un_score_nul_par_defaut_technique_est_ECARTE(self):
        """
        Un juge qui rend 0 n'a pas juge : il a echoue. Le compter
        ferait plonger le degre pour une panne, pas pour un desaveu.
        Aucun cas en base aujourd'hui — la garde protege l'avenir.
        / A zero is a failure, not a verdict.
        """
        avis = [_avis(0.0, 50.0), _avis(95.0, 50.0), _avis(95.0, 50.0)]

        degre = degre_agrege(avis)

        self.assertGreater(degre, 80.0)

    def test_si_TOUS_les_avis_sont_ecartes_il_n_y_a_pas_de_degre(self):
        """Aucun juge valide : pas de couleur, pas un zero."""
        self.assertIsNone(degre_agrege([_avis(0.0, 50.0)]))

    def test_le_degre_reste_dans_ses_bornes(self):
        """Il colore une gouttiere : hors de [0, 100] il n'a pas de sens."""
        for score in (0.1, 25.0, 50.0, 75.0, 99.9):
            with self.subTest(score=score):
                degre = degre_agrege([_avis(score, 63.7)])
                self.assertGreaterEqual(degre, 0.0)
                self.assertLessEqual(degre, 100.0)

    def test_trois_juges_MOUS_ne_valent_pas_trois_juges_FRANCS(self):
        """
        LE ROLE DU FACTEUR D'ACCORD. Pencher n'est pas trancher : trois
        avis a peine au-dessus du seuil ne doivent pas peindre la meme
        couleur que trois avis francs.
        / Leaning is not deciding.
        """
        mous = degre_agrege([_avis(52.0, 50.0), _avis(52.0, 50.0),
                             _avis(52.0, 50.0)])
        francs = degre_agrege([_avis(95.0, 50.0), _avis(95.0, 50.0),
                               _avis(95.0, 50.0)])

        self.assertLess(mous, francs)
        self.assertLess(mous, 70.0)


class LaTensionEntreLesJugesEtLaReference(SimpleTestCase):
    """
    Quand les juges locaux DEMENTENT le juge de production.
    / When the local judges CONTRADICT the production judge.

    LOCALISATION : core/tests/test_degre_agrege.py

    C'EST LE SEUL SIGNAL QUE LES LOCAUX APPORTENT VRAIMENT. Mesure du
    20 aout 2026 sur 209 citations : la moitie sort de la bande neutre,
    mais **42 % de ce signal CONTREDIT** le cran de production. Une
    intensite — canal sans signe — aurait donc « renforce » un liseré
    ambre parce que les controleurs le rehabilitaient : elle aurait dit
    l'inverse de ce qui se passe.

    On ne garde donc que la contradiction FRANCHE : 16 citations sur 209,
    soit 7,7 %. Assez rare pour se voir, assez frequent pour se
    rencontrer — et actionnable : ouvrir la preuve.
    """

    def setUp(self):
        from core.services.degre_agrege import tension_des_juges

        self.tension = tension_des_juges

    def test_sans_avis_local_il_n_y_a_rien_a_dire(self):
        """
        16 citations sur 225 n'ont aucun avis. Les peindre « en accord »
        affirmerait un controle qui n'a pas eu lieu.
        / No opinion is not agreement.
        """
        self.assertIsNone(self.tension([], 70.0))

    def test_sans_degre_de_production_il_n_y_a_rien_a_CONTREDIRE(self):
        """
        Le degre est NULL pour tout verdict pose sans juge — humain,
        introuvable, non verifie. Sans reference, pas de tension.
        / No reference, no tension.
        """
        self.assertIsNone(self.tension([_avis(95.0, 50.0)], None))

    def test_les_locaux_qui_confirment_un_bon_cran_sont_en_ACCORD(self):
        """Tout le monde dit oui : rien a signaler."""
        avis = [_avis(95.0, 50.0), _avis(95.0, 50.0), _avis(95.0, 50.0)]

        self.assertEqual(self.tension(avis, 70.0), "accord")

    def test_les_locaux_FRANCHEMENT_POUR_contre_un_cran_BAS_font_TENSION(self):
        """
        LE CAS QUI COMPTE. Le juge de production doute (cran 40), les
        quatre controleurs rehabilitent franchement. C'est exactement ce
        qu'une intensite non signee aurait affiche comme « encore plus
        douteux ».
        / The production judge doubts; the controllers rehabilitate.
        """
        avis = [_avis(95.0, 50.0), _avis(95.0, 50.0), _avis(95.0, 50.0)]

        self.assertEqual(self.tension(avis, 40.0), "tension")

    def test_les_locaux_FRANCHEMENT_CONTRE_un_cran_HAUT_font_TENSION(self):
        """La symetrie : le juge confirme, les controleurs dementent."""
        avis = [_avis(5.0, 50.0), _avis(5.0, 50.0), _avis(5.0, 50.0)]

        self.assertEqual(self.tension(avis, 70.0), "tension")

    def test_une_divergence_MOLLE_ne_fait_pas_tension(self):
        """
        LA GARDE QUI REND LE SIGNAL RARE. Sans elle, 44 citations sur
        209 seraient marquees — une sur cinq, donc du bruit. Avec elle,
        16 le sont. Pencher n'est pas dementir.
        / Without this guard the mark would fire on one citation in five.
        """
        avis = [_avis(56.0, 50.0), _avis(56.0, 50.0), _avis(56.0, 50.0)]

        self.assertEqual(self.tension(avis, 40.0), "accord")
