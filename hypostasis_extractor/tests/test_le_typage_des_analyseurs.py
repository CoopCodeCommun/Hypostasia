"""
Trois types d'analyseur, et trois métiers qui ne se confondent plus.
/ Three analyzer types, three trades that no longer blur.

LOCALISATION : hypostasis_extractor/tests/test_le_typage_des_analyseurs.py

CE QUE CE CHANTIER SÉPARE. Avant lui, `_prompt_systeme_de_synthese()`
prenait le premier analyseur actif de type `synthetiser` — et servait la
création d'un wiki, la synthèse dirigée ET la mise à jour d'un wiki. La
synthèse d'UNE NOTE, elle, résolvait le MEME type par un autre chemin.
Quatre gestes, un seul préambule : on ne pouvait pas régler l'un sans
régler les autres.
/ Four gestures shared one preamble: none could be tuned alone.

POURQUOI COPIER PLUTOT QUE BASCULER. « Synthèse délibérative » sert les
DEUX métiers aujourd'hui. La basculer vers `rediger_un_article`
laisserait les trois vues de la synthèse d'une note sans aucun analyseur
— HTTP 400, « Aucun analyseur de synthèse actif » — et le remède que ce
toast affiche (`make install`) ne repareraIT RIEN : les fixtures
retrouvent l'analyseur basculé PAR SON NOM et ne recréent jamais de
`synthetiser`. La casse serait permanente.
/ Copy, never move: moving it would permanently break note synthesis,
and the on-screen remedy would not repair it.

LE NOM EST UN VERROU. La copie porte EXACTEMENT le nom que les fixtures
emploient. Sinon le démarrage suivant crée un SECOND `rediger_un_article`
garni du texte par défaut qui, naissant `est_par_defaut=True`, décoche
celui du mainteneur — son prompt cesse de servir, sans une erreur.
/ The name is a lock: a mismatch would let the next boot create a second
analyzer that steals the default.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from hypostasis_extractor.models import (
    AnalyseurSyntaxique, PromptPiece,
)


class LeTypeRedigerUnArticleTest(TestCase):
    """Le troisième type existe, et il est sélectionnable."""

    def test_le_type_existe(self):
        self.assertEqual(
            AnalyseurSyntaxique.TypeAnalyseur.REDIGER_UN_ARTICLE,
            "rediger_un_article",
        )

    def test_il_tient_dans_la_colonne(self):
        # `max_length=20` : `rediger_un_article` fait 18 caractères.
        # Un `mettre_a_jour_un_wiki` en aurait fait 21 et exigé une
        # `AlterField` — c'est une raison de plus de s'en tenir à trois.
        # / It fits in max_length=20; a longer name would not have.
        longueur = AnalyseurSyntaxique._meta.get_field(
            "type_analyseur",
        ).max_length
        self.assertLessEqual(len("rediger_un_article"), longueur)

    def test_le_selecteur_de_type_propose_les_trois(self):
        # Le `<select>` du gabarit se construit sur les choices du
        # modèle. Écrit en dur, il rendrait un type neuf
        # INSÉLECTIONNABLE — et pire : sans option `selected`, le
        # navigateur affiche la première (« Analyser »), donc l'écran
        # ment, et le premier `change` écrase le vrai type.
        # / A hard-coded select would misreport the type, then overwrite it.
        staff = get_user_model().objects.create_user(
            username="staff_typage", password="test1234", is_staff=True,
        )
        self.client.force_login(staff)
        analyseur = AnalyseurSyntaxique.objects.create(
            name="Rédacteur d'essai",
            type_analyseur="rediger_un_article",
        )

        reponse = self.client.get(f"/api/analyseurs/{analyseur.pk}/")

        contenu = reponse.content.decode()
        self.assertIn('value="analyser"', contenu)
        self.assertIn('value="synthetiser"', contenu)
        self.assertIn('value="rediger_un_article"', contenu)
        # Le type réel est celui qui est sélectionné, pas le premier.
        # / The real type is the selected one, not the first.
        self.assertIn('value="rediger_un_article" selected', contenu)


class LesDeuxMetiersNeSeConfondentPlusTest(TestCase):
    """Le préambule d'article et celui d'une note sont distincts."""

    def setUp(self):
        self.redacteur = AnalyseurSyntaxique.objects.create(
            name="Rédacteur", type_analyseur="rediger_un_article",
            is_active=True, est_par_defaut=True,
        )
        PromptPiece.objects.create(
            analyseur=self.redacteur, role="instruction",
            content="TU RÉDIGES UN ARTICLE.", order=0,
        )
        self.synthetiseur = AnalyseurSyntaxique.objects.create(
            name="Synthétiseur", type_analyseur="synthetiser",
            is_active=True, est_par_defaut=True,
        )
        PromptPiece.objects.create(
            analyseur=self.synthetiseur, role="instruction",
            content="TU SYNTHÉTISES UNE NOTE.", order=0,
        )

    def test_le_preambule_d_article_vient_du_redacteur(self):
        from front.tasks import _prompt_systeme_de_synthese

        self.assertEqual(
            _prompt_systeme_de_synthese(),
            "=== INSTRUCTION ===\nTU RÉDIGES UN ARTICLE.",
        )

    def test_la_provenance_nomme_le_meme_analyseur_que_le_prompt(self):
        # DEUX RÈGLES DE RÉSOLUTION DIVERGENTES feraient écrire dans la
        # trace un analyseur qui n'a pas servi.
        # / Two divergent rules would name an analyzer that never served.
        from hypostasis_extractor.services.provenance import (
            analyseur_de_redaction,
        )

        analyseur, _version = analyseur_de_redaction()
        self.assertEqual(analyseur, self.redacteur)

    def test_le_selecteur_de_synthese_d_une_note_ignore_le_redacteur(self):
        # Les trois vues de la synthèse d'une note gardent leur type :
        # les basculer aurait cassé le geste.
        # / Note synthesis keeps its own type.
        analyseurs_de_synthese = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="synthetiser",
        )

        self.assertIn(self.synthetiseur, analyseurs_de_synthese)
        self.assertNotIn(self.redacteur, analyseurs_de_synthese)


class L_utilisabiliteD_unRedacteurTest(TestCase):
    """
    La garde d'utilisabilité couvre le rédacteur.
    / The usability guard covers the writer.

    Avant, elle rendait `True, []` pour tout ce qui n'était pas
    `analyser` : un rédacteur SANS AUCUNE PIÈCE passait pour prêt.
    / It used to whitelist everything that was not an analyzer.
    """

    def test_un_redacteur_sans_piece_n_est_pas_utilisable(self):
        from hypostasis_extractor.services import (
            verifier_utilisabilite_analyseur,
        )

        redacteur_vide = AnalyseurSyntaxique.objects.create(
            name="Rédacteur vide", type_analyseur="rediger_un_article",
        )

        utilisable, raisons = verifier_utilisabilite_analyseur(redacteur_vide)
        self.assertFalse(utilisable)
        self.assertTrue(raisons)

    def test_un_redacteur_avec_une_piece_est_utilisable(self):
        from hypostasis_extractor.services import (
            verifier_utilisabilite_analyseur,
        )

        redacteur = AnalyseurSyntaxique.objects.create(
            name="Rédacteur garni", type_analyseur="rediger_un_article",
        )
        PromptPiece.objects.create(
            analyseur=redacteur, role="instruction",
            content="Rédige.", order=0,
        )

        utilisable, raisons = verifier_utilisabilite_analyseur(redacteur)
        self.assertTrue(utilisable, raisons)


class LesFixturesPosentLeRedacteurTest(TestCase):
    """L'installation crée le rédacteur, une seule fois."""

    def test_les_fixtures_creent_un_redacteur_d_article(self):
        from front.services.fixtures_analyseurs import (
            creer_les_modeles_ia_et_les_analyseurs,
        )

        creer_les_modeles_ia_et_les_analyseurs()

        redacteurs = AnalyseurSyntaxique.objects.filter(
            type_analyseur="rediger_un_article",
        )
        self.assertEqual(redacteurs.count(), 1)
        self.assertTrue(redacteurs.get().pieces.exists())

    def test_un_second_passage_ne_cree_pas_de_second_redacteur(self):
        # Cette fonction tourne à CHAQUE démarrage de conteneur.
        # / It runs at every container start.
        from front.services.fixtures_analyseurs import (
            creer_les_modeles_ia_et_les_analyseurs,
        )

        creer_les_modeles_ia_et_les_analyseurs()
        creer_les_modeles_ia_et_les_analyseurs()

        self.assertEqual(
            AnalyseurSyntaxique.objects.filter(
                type_analyseur="rediger_un_article",
            ).count(),
            1,
        )

    def test_la_migration_et_les_fixtures_nomment_le_MEME_analyseur(self):
        # LE VERROU. La migration de données copie « Synthèse
        # délibérative » sous un nom écrit en dur ; les fixtures
        # cherchent ce nom par `get_or_create`. S'ils divergent, le
        # démarrage suivant crée un SECOND rédacteur garni du texte par
        # défaut qui, naissant `est_par_defaut=True`, décoche celui du
        # mainteneur — son prompt cesse de servir, sans une erreur.
        # / If the two names diverge, the next boot steals the default.
        import importlib

        from front.services.fixtures_analyseurs import (
            NOM_DE_L_ANALYSEUR_DE_REDACTION,
        )

        # `importlib` et pas un `import` ordinaire : un module dont le nom
        # commence par un chiffre n'est pas un identifiant Python.
        # / importlib: a module name starting with a digit is no identifier.
        migration = importlib.import_module(
            "hypostasis_extractor.migrations."
            "0038_le_type_rediger_un_article",
        )

        self.assertEqual(
            migration.NOM_DE_L_ANALYSEUR_DE_REDACTION,
            NOM_DE_L_ANALYSEUR_DE_REDACTION,
        )


class UnMorceauDePromptN_aPasDeNomTest(TestCase):
    """
    Un morceau part par son CONTENU, titré par son RÔLE — jamais par un nom.
    / A piece travels by its content, titled by its role — never a name.

    LOCALISATION : hypostasis_extractor/tests/test_le_typage_des_analyseurs.py

    Le nom ne partait nulle part : c'était un champ que l'écran donnait
    à remplir et que le modèle ne voyait pas — trois morceaux sur trois
    l'avaient laissé vide.
    / The name never travelled: a field the screen offered and the model
    never saw.
    """

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff_morceau", password="test1234", is_staff=True,
        )
        self.client.force_login(self.staff)
        self.analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur d'essai", type_analyseur="rediger_un_article",
        )

    def test_le_modele_ne_porte_plus_de_nom(self):
        champs = {champ.name for champ in PromptPiece._meta.get_fields()}
        self.assertNotIn("name", champs)

    def test_on_ajoute_un_morceau_sans_lui_donner_de_nom(self):
        reponse = self.client.post(
            f"/api/analyseurs/{self.analyseur.pk}/add_piece/",
            {"role": "instruction", "content": "Rédige.", "order": 0},
        )

        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(self.analyseur.pieces.get().content, "Rédige.")

    def test_chaque_bloc_part_sous_le_titre_de_son_role(self):
        # LE ROLE PART AU MODELE. Il classait les pieces a l'ecran sans
        # jamais rien dire au modele ; il titre maintenant chaque bloc,
        # comme le reste du prompt (`=== SUJET DE L'ARTICLE ===`,
        # `=== CONSIGNE ===`).
        # / The role now travels: it titles each block.
        from front.tasks import _prompt_systeme_de_synthese

        self.analyseur.is_active = True
        self.analyseur.est_par_defaut = True
        self.analyseur.save()
        PromptPiece.objects.create(
            analyseur=self.analyseur, role="instruction",
            content="DEUXIÈME.", order=1,
        )
        PromptPiece.objects.create(
            analyseur=self.analyseur, role="context",
            content="PREMIÈRE.", order=0,
        )

        self.assertEqual(
            _prompt_systeme_de_synthese(),
            "=== CONTEXTE ===\nPREMIÈRE.\n\n=== INSTRUCTION ===\nDEUXIÈME.",
        )

    def test_une_piece_vide_ne_laisse_pas_de_titre_orphelin(self):
        # Un titre seul ferait croire au modele a une section qu'on
        # aurait oublie de remplir.
        # / A lone heading would suggest a section left blank.
        PromptPiece.objects.create(
            analyseur=self.analyseur, role="format", content="   ", order=0,
        )
        PromptPiece.objects.create(
            analyseur=self.analyseur, role="instruction",
            content="Rédige.", order=1,
        )

        self.assertEqual(
            self.analyseur.texte_du_prompt(),
            "=== INSTRUCTION ===\nRédige.",
        )
