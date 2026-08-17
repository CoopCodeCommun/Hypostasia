"""
Tests de l'applieur d'operations de section (SPEC-synthese § 6,
phase F).
/ Section-operations applier tests (phase F).

LOCALISATION : core/tests/test_section_ops.py

Le modele ne reecrit pas l'article : il propose des operations qu'un
applieur fusionne et qu'un humain accepte. Un titre introuvable est une
HALLUCINATION : operation rejetee VISIBLEMENT, contenu CONSERVE — jamais
de fallback silencieux, jamais de perte de donnees (§ 6.2). Le rejet est
PAR OPERATION (addendum n°4). Seuls les titres ## font frontiere
(addendum n°3). La proposition porte l'updated_at de l'article
(addendum n°1).
/ Visible per-operation rejection, content preserved, ## only,
optimistic concurrency.
"""

import datetime

from django.test import TestCase

from core.services.section_ops import (
    PropositionPerimee,
    appliquer_les_operations,
    verifier_que_la_proposition_est_fraiche,
)

ARTICLE = (
    "# Le seuil de passage en assemblée\n"
    "\n"
    "Préambule de l'article.\n"
    "\n"
    "## Le seuil\n"
    "\n"
    "Le seuil déclenche le passage en assemblée.[[ext:11]]\n"
    "\n"
    "## Les coûts\n"
    "\n"
    "L'ajournement répété est un coût.[[ext:12]]\n"
)

PERIMETRE = {11, 12, 13}


class RejetsVisiblesTest(TestCase):
    """§ 6.2-6.3 : les quatre motifs de rejet. / The four rejections."""

    def test_heading_introuvable_rejette_visiblement(self):
        operations = [{
            "type": "append_to_section",
            "section": "Section fantôme",
            "contenu": "Un fait nouveau.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        # Rien n'est applique, rien n'est perdu : le texte est intact et
        # le contenu rejete est CONSERVE avec son motif.
        # / Nothing applied, nothing lost.
        self.assertEqual(bilan["texte_final"], ARTICLE)
        self.assertEqual(bilan["operations_appliquees"], [])
        self.assertEqual(len(bilan["operations_rejetees"]), 1)
        rejet = bilan["operations_rejetees"][0]
        self.assertIn("Section fantôme", rejet["motif"])
        self.assertEqual(
            rejet["operation"]["contenu"], "Un fait nouveau.[[ext:13]]",
        )

    def test_after_heading_introuvable_ne_fait_pas_de_fallback(self):
        operations = [{
            "type": "insert_section",
            "titre": "Nouvelle section",
            "apres": "Section fantôme",
            "contenu": "Contenu neuf.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        # PAS d'ajout en fin d'article : le fallback silencieux insere a
        # un endroit que le modele n'a pas choisi (§ 6.2).
        # / No end-of-article fallback.
        self.assertEqual(bilan["texte_final"], ARTICLE)
        self.assertNotIn("Nouvelle section", bilan["texte_final"])
        self.assertEqual(len(bilan["operations_rejetees"]), 1)

    def test_sources_vides_rejetees(self):
        # Une affirmation sans preuve n'a rien a faire dans un article
        # source (§ 6.3). / No unsourced claim in a sourced article.
        operations = [{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": "Une affirmation sans aucun marqueur.",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(bilan["texte_final"], ARTICLE)
        # « aucune source » discrimine ce rejet de celui du hors
        # perimetre (relecture F, M8). / Discriminating assertion.
        self.assertIn("aucune source", bilan["operations_rejetees"][0]["motif"])

    def test_sources_hors_perimetre_rejetees(self):
        # Le modele a cite quelque chose qu'on ne lui a pas donne
        # (§ 6.3). / The model cited something it was never given.
        operations = [{
            "type": "replace_section",
            "section": "Le seuil",
            "contenu": "Réécriture.[[ext:999]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(bilan["texte_final"], ARTICLE)
        self.assertIn("999", bilan["operations_rejetees"][0]["motif"])


class ApplicationNominaleTest(TestCase):
    """§ 6.1 : les operations acceptees fusionnent. / Accepted ops merge."""

    def test_append_replace_insert_s_appliquent(self):
        operations = [
            {
                "type": "append_to_section",
                "section": "Le seuil",
                "contenu": "Le vote est confirmé.[[ext:13]]",
            },
            {
                "type": "replace_section",
                "section": "Les coûts",
                "contenu": "Les coûts sont requalifiés.[[ext:12]]",
            },
            {
                "type": "insert_section",
                "titre": "La décision",
                "apres": "Les coûts",
                "contenu": "La décision est actée.[[ext:11]]",
            },
        ]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        texte = bilan["texte_final"]
        self.assertEqual(len(bilan["operations_appliquees"]), 3)
        self.assertEqual(bilan["operations_rejetees"], [])
        # L'append garde l'existant et ajoute a la fin de la section.
        # / Append keeps the section body and adds at its end.
        self.assertIn("Le seuil déclenche le passage", texte)
        self.assertIn("Le vote est confirmé.[[ext:13]]", texte)
        self.assertLess(
            texte.index("Le seuil déclenche"), texte.index("Le vote est confirmé"),
        )
        # Le replace remplace le corps, pas le titre. / Replace swaps body.
        self.assertIn("## Les coûts", texte)
        self.assertNotIn("L'ajournement répété", texte)
        self.assertIn("Les coûts sont requalifiés.[[ext:12]]", texte)
        # L'insert cree la section apres « Les coûts ».
        self.assertIn("## La décision", texte)
        self.assertLess(
            texte.index("## Les coûts"), texte.index("## La décision"),
        )

    def test_replace_retourne_l_ancien_corps(self):
        # § 6.4 : le diff montre l'avant — l'applieur le fournit.
        # / § 6.4: the diff shows the before; the applier provides it.
        operations = [{
            "type": "replace_section",
            "section": "Les coûts",
            "contenu": "Nouveau corps.[[ext:12]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        appliquee = bilan["operations_appliquees"][0]
        self.assertIn(
            "L'ajournement répété est un coût.[[ext:12]]",
            appliquee["ancien_contenu"],
        )

    def test_no_change_ne_change_rien(self):
        operations = [{"type": "no_change", "section": "Le seuil"}]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(bilan["texte_final"], ARTICLE)
        self.assertEqual(len(bilan["operations_appliquees"]), 1)
        self.assertEqual(bilan["operations_rejetees"], [])

    def test_le_rejet_est_par_operation(self):
        # Addendum n°4 : une hallucination ne jette pas les faits des
        # autres operations — pas de point de reprise chez nous.
        # / One hallucination never drops the other operations' facts.
        operations = [
            {
                "type": "append_to_section",
                "section": "Le seuil",
                "contenu": "Fait valide.[[ext:13]]",
            },
            {
                "type": "append_to_section",
                "section": "Section fantôme",
                "contenu": "Fait orphelin.[[ext:13]]",
            },
        ]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(len(bilan["operations_appliquees"]), 1)
        self.assertEqual(len(bilan["operations_rejetees"]), 1)
        self.assertIn("Fait valide.[[ext:13]]", bilan["texte_final"])
        self.assertNotIn("Fait orphelin", bilan["texte_final"])


class TitresDeNiveauDeuxSeulementTest(TestCase):
    """Addendum n°3 : seuls les ## font frontiere. / ## only."""

    def test_un_sous_titre_n_est_pas_une_section(self):
        article_avec_sous_titre = (
            "## La seule section\n"
            "\n"
            "Corps.[[ext:11]]\n"
            "\n"
            "### Un sous-titre\n"
            "\n"
            "Suite du corps.[[ext:12]]\n"
        )
        operations = [{
            "type": "append_to_section",
            "section": "Un sous-titre",
            "contenu": "Ajout.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(
            article_avec_sous_titre, operations, PERIMETRE,
        )

        # Le ### n'est pas resolvable : rejet. / ### never resolves.
        self.assertEqual(len(bilan["operations_rejetees"]), 1)
        self.assertEqual(bilan["texte_final"], article_avec_sous_titre)

    def test_un_titre_duplique_rejette_pour_ambiguite(self):
        article_ambigu = (
            "## Budget\n\nCorps un.[[ext:11]]\n\n"
            "## Budget\n\nCorps deux.[[ext:12]]\n"
        )
        operations = [{
            "type": "replace_section",
            "section": "Budget",
            "contenu": "Lequel ?[[ext:13]]",
        }]

        bilan = appliquer_les_operations(article_ambigu, operations, PERIMETRE)

        self.assertEqual(bilan["texte_final"], article_ambigu)
        self.assertIn("ambigu", bilan["operations_rejetees"][0]["motif"].lower())


class PropositionPerimeeTest(TestCase):
    """Addendum n°1 : la concurrence optimiste. / Optimistic concurrency."""

    def _creer_un_article(self):
        from core.models import Page, TypeDeNote

        return Page.objects.create(
            url="http://exemple.local/sf-article",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=ARTICLE, content_hash="hash-sf-1",
            title="Wiki du seuil", type_de_note=TypeDeNote.WIKI,
        )

    def test_une_proposition_perimee_est_refusee(self):
        article = self._creer_un_article()
        updated_at_au_moment_de_la_proposition = article.updated_at

        # L'article bouge entre la previsualisation et l'application.
        # / The article moves between preview and apply.
        article.text_readability = ARTICLE + "\nPost-scriptum.\n"
        article.save(update_fields=["text_readability", "updated_at"])
        article.refresh_from_db()

        with self.assertRaises(PropositionPerimee):
            verifier_que_la_proposition_est_fraiche(
                article, updated_at_au_moment_de_la_proposition,
            )

    def test_une_proposition_fraiche_passe(self):
        article = self._creer_un_article()
        article.refresh_from_db()

        # Ne doit pas lever. / Must not raise.
        verifier_que_la_proposition_est_fraiche(article, article.updated_at)

    def test_un_horodatage_texte_est_accepte(self):
        # La proposition transite par un formulaire HTMX : l'horodatage
        # revient en chaine ISO. / The timestamp round-trips as ISO text.
        article = self._creer_un_article()
        article.refresh_from_db()

        verifier_que_la_proposition_est_fraiche(
            article, article.updated_at.isoformat(),
        )

        with self.assertRaises(PropositionPerimee):
            verifier_que_la_proposition_est_fraiche(
                article,
                (article.updated_at - datetime.timedelta(minutes=3)).isoformat(),
            )


class CorrectifsRelectureFTest(TestCase):
    """
    Correctifs de la relecture adverse de la phase F (9 aout soir).
    / Fixes from the phase F adversarial review.
    """

    # ----- B1 : le contenu ne peut pas fabriquer de sections -----

    def test_un_contenu_avec_titre_de_section_est_rejete(self):
        # Un ## dans le contenu fabriquerait une section que l'humain
        # n'a pas approuvee — et un titre duplique irreversible. Seule
        # insert_section cree une section.
        # / Content must never smuggle section boundaries in.
        operations = [{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": "Ajout.[[ext:13]]\n\n## Les coûts\n\nDoublon !",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(bilan["texte_final"], ARTICLE)
        self.assertEqual(len(bilan["operations_rejetees"]), 1)
        self.assertIn("titre de section", bilan["operations_rejetees"][0]["motif"])

    # ----- I1 : insert ne duplique jamais un titre existant -----

    def test_insert_d_un_titre_deja_present_est_rejete(self):
        operations = [{
            "type": "insert_section",
            "titre": "Les coûts",
            "apres": "Le seuil",
            "contenu": "Encore des coûts.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(bilan["texte_final"], ARTICLE)
        self.assertIn("existe déjà", bilan["operations_rejetees"][0]["motif"])

    # ----- I2 : un titre indente est une section (comme l'indexeur) -----

    def test_un_titre_indente_est_reconnu_comme_frontiere(self):
        article_indente = (
            "## A\n\nCorps A.[[ext:11]]\n\n"
            "  ## Indenté\n\nCorps indenté.[[ext:12]]\n"
        )
        operations = [{
            "type": "append_to_section",
            "section": "A",
            "contenu": "Ajout à A.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(article_indente, operations, PERIMETRE)

        texte = bilan["texte_final"]
        # L'ajout atterrit DANS A, avant la frontiere indentee — jamais
        # dans la section suivante. / The add lands INSIDE A.
        self.assertLess(
            texte.index("Ajout à A."), texte.index("## Indenté"),
        )
        # Et la section indentee est adressable. / And it is addressable.
        bilan_2 = appliquer_les_operations(
            article_indente,
            [{"type": "append_to_section", "section": "Indenté",
              "contenu": "Ajout indenté.[[ext:13]]"}],
            PERIMETRE,
        )
        self.assertEqual(bilan_2["operations_rejetees"], [])

    # ----- I3 : le titre se compare tronque a 200 (SourceLink.section) -----

    def test_un_titre_long_se_retrouve_par_sa_forme_tronquee(self):
        titre_verbeux = "Très long titre de section " * 10  # 270 chars
        article_verbeux = (
            f"## {titre_verbeux}\n\nCorps.[[ext:11]]\n"
        )
        operations = [{
            "type": "append_to_section",
            # Le prompt peut n'avoir vu que la forme SourceLink.section,
            # tronquee a 200. / The prompt may only know the 200-char form.
            "section": titre_verbeux[:200],
            "contenu": "Ajout.[[ext:12]]",
        }]

        bilan = appliquer_les_operations(article_verbeux, operations, PERIMETRE)

        self.assertEqual(bilan["operations_rejetees"], [])
        self.assertIn("Ajout.[[ext:12]]", bilan["texte_final"])

    # ----- I4 : une operation malformee ne detruit pas le lot -----

    def test_une_operation_malformee_est_rejetee_sans_detruire_le_lot(self):
        operations = [
            {
                "type": "append_to_section",
                "section": "Le seuil",
                "contenu": "Fait valide.[[ext:13]]",
            },
            {"type": "append_to_section", "section": "Le seuil",
             "contenu": ["une", "liste"]},
            "pas un dictionnaire",
        ]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        # L'operation valide est appliquee, les deux malformees sont
        # rejetees avec motif (addendum n°4). / Valid op applied.
        self.assertIn("Fait valide.[[ext:13]]", bilan["texte_final"])
        self.assertEqual(len(bilan["operations_appliquees"]), 1)
        self.assertEqual(len(bilan["operations_rejetees"]), 2)

    # ----- I5 : ancre d'insertion absente, motif honnete -----

    def test_apres_vide_donne_un_motif_honnete(self):
        operations = [{
            "type": "insert_section", "titre": "Neuve", "apres": "",
            "contenu": "Contenu.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        motif = bilan["operations_rejetees"][0]["motif"]
        self.assertIn("renseign", motif)
        self.assertNotIn("None", motif)

    # ----- M1 : no_change fantome signale -----

    def test_no_change_sur_une_section_inexistante_est_rejete(self):
        operations = [{"type": "no_change", "section": "Fantôme"}]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(len(bilan["operations_rejetees"]), 1)

    # ----- M3 : titre d'insertion multi-lignes ou en # rejete -----

    def test_un_titre_d_insertion_illegal_est_rejete(self):
        for titre_illegal in ["Ligne1\nLigne2", "# Grand titre"]:
            with self.subTest(titre=titre_illegal):
                bilan = appliquer_les_operations(ARTICLE, [{
                    "type": "insert_section", "titre": titre_illegal,
                    "apres": "Le seuil", "contenu": "C.[[ext:13]]",
                }], PERIMETRE)
                self.assertEqual(bilan["texte_final"], ARTICLE)
                self.assertEqual(len(bilan["operations_rejetees"]), 1)

    # ----- M5 : une seule operation de contenu par section et par lot -----

    def test_deux_operations_de_contenu_sur_la_meme_section_rejettent_la_seconde(self):
        operations = [
            {"type": "append_to_section", "section": "Le seuil",
             "contenu": "Premier ajout.[[ext:13]]"},
            {"type": "replace_section", "section": "Le seuil",
             "contenu": "Écrasement.[[ext:11]]"},
        ]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        # Sinon le « avant » du diff § 6.4 ne serait pas l'avant de
        # l'article. / Otherwise the § 6.4 "before" would lie.
        self.assertEqual(len(bilan["operations_appliquees"]), 1)
        self.assertEqual(len(bilan["operations_rejetees"]), 1)
        self.assertIn("Premier ajout.[[ext:13]]", bilan["texte_final"])
        self.assertNotIn("Écrasement", bilan["texte_final"])

    # ----- M2 : les fins de ligne CRLF sont normalisees -----

    def test_le_crlf_est_normalise(self):
        article_crlf = ARTICLE.replace("\n", "\r\n")
        operations = [{
            "type": "append_to_section", "section": "Le seuil",
            "contenu": "Ajout.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(article_crlf, operations, PERIMETRE)

        self.assertNotIn("\r", bilan["texte_final"])
        self.assertIn("Ajout.[[ext:13]]", bilan["texte_final"])

    # ----- M6 : chaque resultat porte l'indice d'origine -----

    def test_les_resultats_portent_l_indice_d_origine(self):
        operations = [
            {"type": "no_change", "section": "Le seuil"},
            {"type": "append_to_section", "section": "Fantôme",
             "contenu": "X.[[ext:13]]"},
        ]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(bilan["operations_appliquees"][0]["indice"], 0)
        self.assertEqual(bilan["operations_rejetees"][0]["indice"], 1)


class ContenuSansRedactionTest(TestCase):
    """
    Une operation dont le contenu se reduit a des marqueurs nus est
    rejetee (recette connectee du 10 aout, defaut B2) : appliquee, elle
    produisait des paragraphes orphelins faits d'un seul renvoi [4].
    / An operation whose content is only bare markers is rejected: it
    used to produce orphan single-reference paragraphs.
    """

    def test_un_marqueur_nu_est_rejete(self):
        operations = [{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": "[[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(bilan["texte_final"], ARTICLE)
        self.assertEqual(bilan["operations_appliquees"], [])
        self.assertEqual(len(bilan["operations_rejetees"]), 1)
        motif = bilan["operations_rejetees"][0]["motif"]
        # Le motif explique le POURQUOI, en francais lisible.
        # / The reason explains why, in plain French.
        self.assertIn("marqueur", motif.lower())

    def test_plusieurs_marqueurs_nus_sont_rejetes_pareil(self):
        operations = [{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": "[[ext:11]] [[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(len(bilan["operations_rejetees"]), 1)

    def test_un_contenu_redige_avec_marqueur_passe_toujours(self):
        operations = [{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": "Un passage sourcé et rédigé.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(len(bilan["operations_appliquees"]), 1)
        self.assertIn("Un passage sourcé et rédigé.", bilan["texte_final"])


class TitreRecopieAvecSesDiesesTest(TestCase):
    """
    Un modele qui recopie la LIGNE DE TITRE entiere doit etre compris.
    / A model copying the whole heading line must still match.

    LOCALISATION : core/tests/test_section_ops.py

    Le prompt demande au modele de reprendre « les titres de l'article ».
    Recopier « ## Le seuil » plutot que « Le seuil » est une lecture
    honnete de cette consigne : les dieses sont une NOTATION de niveau,
    pas une partie du nom de la section. Les laisser faire echouer la
    correspondance transforme une obeissance en hallucination.
    / The hashes are level notation, not part of the section name.
    """

    def test_un_titre_recopie_avec_ses_dieses_est_reconnu(self):
        operations = [{
            "type": "append_to_section",
            "section": "## Le seuil",
            "contenu": "Un ajout sourcé.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(len(bilan["operations_rejetees"]), 0)
        self.assertEqual(len(bilan["operations_appliquees"]), 1)
        self.assertIn("Un ajout sourcé.", bilan["texte_final"])

    def test_l_ancre_d_insertion_accepte_aussi_les_dieses(self):
        operations = [{
            "type": "insert_section",
            "titre": "Les délais",
            "apres": "## Le seuil",
            "contenu": "Une section neuve et sourcée.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(len(bilan["operations_rejetees"]), 0)
        self.assertIn("## Les délais", bilan["texte_final"])

    def test_un_titre_vraiment_absent_reste_rejete(self):
        # La tolerance aux dieses ne doit pas devenir une correspondance
        # approximative : une section inexistante reste une
        # hallucination. / Hash tolerance is not fuzzy matching.
        operations = [{
            "type": "append_to_section",
            "section": "## Une section qui n'existe pas",
            "contenu": "Un ajout sourcé.[[ext:13]]",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(len(bilan["operations_rejetees"]), 1)
        self.assertEqual(len(bilan["operations_appliquees"]), 0)


class ContenuDeContrebandeTest(TestCase):
    """
    La garde B1 doit couvrir TOUS les niveaux de titre.
    / The B1 guard must cover every heading level.

    LOCALISATION : core/tests/test_section_ops.py

    Elle ne detectait que les `##`. Depuis que l'ecriture promeut les
    `###` en `##`, un contenu qui glisse un `###` fabrique une section
    APRES l'acceptation humaine — la porte que B1 existe pour fermer.
    / It only caught `##`; since writing promotes `###`, a smuggled
    `###` creates a section after human approval.
    """

    def test_un_sous_titre_de_contrebande_est_rejete(self):
        operations = [{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": (
                "Un texte sourcé.[[ext:13]]\n"
                "\n"
                "### Une section clandestine\n"
                "\n"
                "Autre texte.[[ext:13]]"
            ),
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(len(bilan["operations_appliquees"]), 0)
        self.assertEqual(len(bilan["operations_rejetees"]), 1)
        self.assertIn(
            "titre", bilan["operations_rejetees"][0]["motif"].lower(),
        )

    def test_un_titre_de_niveau_quatre_est_rejete_aussi(self):
        operations = [{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": "Un texte.[[ext:13]]\n\n#### Encore plus bas\n",
        }]

        bilan = appliquer_les_operations(ARTICLE, operations, PERIMETRE)

        self.assertEqual(len(bilan["operations_rejetees"]), 1)
