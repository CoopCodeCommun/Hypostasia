"""
Les niveaux de titre, entre la production d'un article et sa mise a jour.
/ Heading levels, between article production and its update.

LOCALISATION : front/tests/test_maj_wiki_niveaux_de_titre.py

L'applieur (SPEC-synthese § 6, addendum n°3) ne resout QUE les titres
de niveau 2. Deux consequences que ces tests verrouillent :

1. Un article stocke ne doit contenir QUE des `##`. Le prompt le
   demande deja, mais un modele reel desobeit : la garde doit donc etre
   MECANIQUE, pas seulement redigee. Un `###` stocke serait une zone de
   l'article que la mise a jour ne peut plus jamais atteindre — un
   piege silencieux, puisque rien ne le signale.
2. Le prompt de mise a jour ne doit exposer QUE ces titres-la. Lui
   donner l'article brut, c'est lui montrer des titres que l'applieur
   rejettera.
/ The applier resolves level-2 headings only: stored articles must hold
only `##`, and the update prompt must expose only those.
"""

from unittest.mock import patch

from django.test import TestCase

from core.models import Page, TypeDeNote, Wiki
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c
from hypostasis_extractor.models import ExtractionJob


class NiveauxDeTitreALEcritureTest(TestCase):
    """
    Ce qui est ECRIT ne porte que des `##`.
    / What gets written carries only level-2 headings.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page = Page.objects.create(
            title="Wiki — Le seuil", text_readability="",
            html_readability="", html_original="", content_hash="h",
            type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )

    def test_un_sous_titre_produit_devient_une_section_adressable(self):
        # Le cas REEL du 16 aout 2026 : Gemini 2.5 Flash a rendu un
        # wiki a 1 seul `##` et 5 `###`, malgre une consigne qui les
        # interdit. Cinq sections sur six etaient alors hors de portee
        # de la mise a jour. / The real case: 1 `##` and 5 `###`.
        from front.tasks import _ecrire_le_corps_d_un_article

        pk_seuil = self.fixtures["extraction_seuil"].pk
        texte_du_modele = (
            "## Le grand titre\n"
            "\n"
            "### Qu'est-ce que le seuil ?\n"
            "\n"
            f"Le seuil déclenche l'assemblée.[[ext:{pk_seuil}]]\n"
        )

        _ecrire_le_corps_d_un_article(
            self.page, texte_du_modele, {pk_seuil},
        )
        self.page.refresh_from_db()

        from core.services.synthese import titre_de_section

        titres = [
            titre_de_section(ligne)
            for ligne in self.page.text_readability.split("\n")
        ]
        titres_reconnus = [titre for titre in titres if titre is not None]

        self.assertNotIn("###", self.page.text_readability)
        self.assertIn("Qu'est-ce que le seuil ?", titres_reconnus)
        self.assertIn("Le grand titre", titres_reconnus)

    def test_le_contenu_des_sections_est_intact(self):
        # On normalise la NOTATION du titre, jamais le texte.
        # / We normalise the heading notation, never the prose.
        from front.tasks import _ecrire_le_corps_d_un_article

        pk_seuil = self.fixtures["extraction_seuil"].pk
        texte_du_modele = (
            "### Un sous-titre\n"
            "\n"
            f"Une phrase qui ne doit pas bouger.[[ext:{pk_seuil}]]\n"
        )

        _ecrire_le_corps_d_un_article(
            self.page, texte_du_modele, {pk_seuil},
        )
        self.page.refresh_from_db()

        self.assertIn(
            "Une phrase qui ne doit pas bouger.",
            self.page.text_readability,
        )

    def test_un_diese_dans_une_phrase_n_est_pas_touche(self):
        # `#` en milieu de ligne n'est pas une notation de titre.
        # / A mid-line hash is not heading notation.
        from front.tasks import _ecrire_le_corps_d_un_article

        pk_seuil = self.fixtures["extraction_seuil"].pk
        texte_du_modele = (
            "## Le seuil\n"
            "\n"
            f"Le mot-clé #gouvernance revient souvent.[[ext:{pk_seuil}]]\n"
        )

        _ecrire_le_corps_d_un_article(
            self.page, texte_du_modele, {pk_seuil},
        )
        self.page.refresh_from_db()

        self.assertIn("#gouvernance", self.page.text_readability)


class PromptDeMiseAJourTest(TestCase):
    """
    Le prompt de mise a jour n'expose que les titres resolvables.
    / The update prompt exposes only resolvable headings.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        pk_seuil = self.fixtures["extraction_seuil"].pk
        self.page = Page.objects.create(
            title="Wiki — Le seuil",
            text_readability=(
                "## Le seuil\n"
                "\n"
                f"Une affirmation.[[ext:{pk_seuil}]]\n"
                "\n"
                "### Un sous-titre invisible pour l'applieur\n"
                "\n"
                "Du texte.\n"
            ),
            html_readability="", html_original="", content_hash="h",
            type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            self.page, self.fixtures["carnet"], self.fixtures["demandeur"],
        )
        self.wiki = Wiki.objects.create(
            page=self.page, dossier=self.fixtures["carnet"],
            sujet="Le seuil",
        )

    def _prompt_envoye(self):
        """Lance la tache et rend le prompt reellement transmis au modele."""
        job = ExtractionJob.objects.create(
            page=self.page, ai_model=self.fixtures["modele_ia"],
            name="MAJ", prompt_description="t", status="pending",
            raw_result={
                "est_maj_wiki": True, "wiki_id": self.wiki.pk,
                "demandeur_id": self.fixtures["demandeur"].pk,
            },
        )
        messages_captures = []

        def _capturer(modele_ia, message_complet):
            messages_captures.append(message_complet)
            return "[]"

        with patch("core.llm_providers.appeler_llm", side_effect=_capturer):
            from front.tasks import proposer_une_maj_de_wiki_task
            proposer_une_maj_de_wiki_task(job.pk)

        self.assertTrue(messages_captures, "aucun appel au modèle")
        # LE PROMPT DE MISE A JOUR, reconnu a sa signature — jamais « le
        # premier » ni « le dernier ».
        #
        # Cette tache ecrit d'abord le corps normalise (elle passe par le
        # chemin d'ecriture normal pour ne pas perimer les bornes des
        # citations), et l'ecriture ENCHAINE la verification : le juge
        # est donc appele, lui aussi, dans le meme bloc. Un test qui
        # prend un appel par son RANG lit alors le prompt d'un autre
        # metier, et son assertion parle de ce qu'elle n'examine pas.
        # / This task writes the normalised body first, and writing
        # chains the verification: the judge is called in the same block.
        # Picking a call by rank reads another job's prompt.
        prompts_de_mise_a_jour = [
            message for message in messages_captures
            if "=== ARTICLE ACTUEL ===" in message
        ]
        self.assertTrue(
            prompts_de_mise_a_jour,
            "aucun prompt de mise à jour parmi les appels au modèle",
        )
        return prompts_de_mise_a_jour[0]

    def test_le_prompt_liste_les_titres_resolvables(self):
        prompt = self._prompt_envoye()

        self.assertIn("Le seuil", prompt)

    def test_le_prompt_ne_montre_aucun_niveau_non_resolvable(self):
        # Montrer un `###` au modele, c'est l'inviter a proposer une
        # operation que l'applieur rejettera (addendum n°3).
        # / Showing a `###` invites a doomed operation.
        prompt = self._prompt_envoye()

        self.assertNotIn("###", prompt)

    def test_tout_titre_montre_est_dans_la_liste_adressable(self):
        # L'invariant qui compte : le modele ne doit voir AUCUN titre
        # qu'il n'aurait pas le droit de viser.
        # / The invariant: no heading is shown that cannot be targeted.
        import re as re_module

        prompt = self._prompt_envoye()
        article_montre = prompt.split("=== ARTICLE ACTUEL ===")[1].split(
            "=== TITRES DE SECTION ADRESSABLES ==="
        )[0]
        liste_montree = prompt.split(
            "=== TITRES DE SECTION ADRESSABLES ==="
        )[1].split("=== EXTRACTIONS NON REPRISES ===")[0]

        titres_de_l_article = re_module.findall(
            r"^#+ +(.+)$", article_montre, re_module.MULTILINE,
        )
        self.assertTrue(titres_de_l_article, "l'article montré n'a aucun titre")
        for titre in titres_de_l_article:
            self.assertIn(titre, liste_montree)

    def test_la_ligne_vide_apres_un_titre_survit(self):
        # Le markdown a besoin de cette ligne vide : sans elle, le titre
        # et son paragraphe se recollent.
        # / Markdown needs that blank line after a heading.
        self._prompt_envoye()
        self.page.refresh_from_db()

        self.assertIn(
            "## Un sous-titre invisible pour l'applieur\n\nDu texte.",
            self.page.text_readability,
        )

    def test_le_prompt_dit_qu_une_operation_porte_sur_une_section(self):
        # Mesure du 16 aout 2026 : un prompt en forme « par extraction »
        # obtient une reponse en forme « par extraction » — 46 entrees,
        # 46 `no_change`, rien d'integre. La consigne doit dire la
        # maille. / An extraction-shaped prompt gets an
        # extraction-shaped answer: state the granularity.
        prompt = self._prompt_envoye()

        self.assertIn("UNE OPÉRATION PORTE SUR UNE SECTION", prompt)
        self.assertIn("JAMAIS SUR UNE EXTRACTION", prompt)


class ReparationDUnArticleHeriteTest(TestCase):
    """
    Reparer un article herite ne doit RIEN perdre.
    / Repairing a legacy article must lose nothing.

    LOCALISATION : front/tests/test_maj_wiki_niveaux_de_titre.py

    Chaque `###` ramene a `##` retire UN caractere : toutes les bornes
    des SourceLink en aval se decalent. Sauver le texte sans reindexer
    perime donc les bornes, fait perdre les verdicts de verification a
    la reindexation suivante (la paire ne correspond plus), et laisse
    le HTML et l'empreinte en desaccord avec le texte.
    / Each demoted heading shifts downstream bounds by one character.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        pk_seuil = self.fixtures["extraction_seuil"].pk
        self.page = Page.objects.create(
            title="Wiki hérité",
            text_readability=(
                "## Contexte\n"
                "\n"
                "Un premier paragraphe.\n"
                "\n"
                "### Le seuil\n"
                "\n"
                f"Un second paragraphe.[[ext:{pk_seuil}]]\n"
            ),
            html_readability="<p>vieux html</p>", html_original="",
            content_hash="vieux-hash", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            self.page, self.fixtures["carnet"], self.fixtures["demandeur"],
        )
        self.wiki = Wiki.objects.create(
            page=self.page, dossier=self.fixtures["carnet"], sujet="Le seuil",
        )
        # On indexe une premiere fois, puis on pose un verdict : c'est
        # ce capital que la reparation ne doit pas detruire.
        # / Index once, then set a verdict: the repair must preserve it.
        from core.services.synthese import indexer_les_citations
        indexer_les_citations(
            self.page, self.page.text_readability, {pk_seuil},
        )

    def _lancer_la_reparation(self):
        job = ExtractionJob.objects.create(
            page=self.page, ai_model=self.fixtures["modele_ia"],
            name="MAJ", prompt_description="t", status="pending",
            raw_result={
                "est_maj_wiki": True, "wiki_id": self.wiki.pk,
                "demandeur_id": self.fixtures["demandeur"].pk,
            },
        )
        with patch("core.llm_providers.appeler_llm", return_value="[]"):
            from front.tasks import proposer_une_maj_de_wiki_task
            proposer_une_maj_de_wiki_task(job.pk)
        self.page.refresh_from_db()

    def test_les_bornes_des_citations_restent_justes(self):
        from core.models import SourceLink

        self._lancer_la_reparation()

        for lien in SourceLink.objects.filter(page_cible=self.page):
            tranche = self.page.text_readability[
                lien.start_char_cible:lien.end_char_cible
            ]
            # Le decalage d'UN caractere laisse encore le marqueur dans
            # la tranche : verifier sa presence ne prouve rien. On exige
            # le DEBUT exact du paragraphe.
            # / A one-char shift still leaves the marker inside: assert
            # the exact paragraph start instead.
            self.assertTrue(
                tranche.startswith("Un second paragraphe."),
                f"bornes décalées : la tranche commence par {tranche[:30]!r}",
            )

    def test_le_verdict_de_verification_survit(self):
        from core.models import EtatDeVerification, SourceLink

        lien = SourceLink.objects.filter(page_cible=self.page).first()
        lien.etat_de_verification = EtatDeVerification.VERIFIE
        lien.verifie_par = "juge de test"
        lien.save(update_fields=["etat_de_verification", "verifie_par"])

        self._lancer_la_reparation()

        # La perte ne se produit pas a la reparation : elle se produit a
        # la REINDEXATION SUIVANTE, quand la reconciliation cherche la
        # paire (extraction, paragraphe) aux anciennes bornes et ne la
        # retrouve plus. C'est donc ce second temps qu'il faut jouer.
        # / The loss happens on the NEXT reindex, not on the repair.
        # Le motif de tour est OBLIGATOIRE des que la page porte un wiki
        # (addendum du 21 aout 2026) : ecrire un article sans lui ne
        # laisserait aucune histoire.
        # / A round motive is mandatory once the page carries a wiki.
        from core.models import MotifDeTourDeWiki
        from front.tasks import _ecrire_le_corps_d_un_article
        _ecrire_le_corps_d_un_article(
            self.page, self.page.text_readability,
            {self.fixtures["extraction_seuil"].pk},
            motif_du_tour=MotifDeTourDeWiki.REPARATION_DE_TITRES,
        )

        etats = list(
            SourceLink.objects.filter(page_cible=self.page)
            .values_list("etat_de_verification", flat=True)
        )
        self.assertIn(EtatDeVerification.VERIFIE, etats)

    def test_le_html_et_l_empreinte_suivent_le_texte(self):
        self._lancer_la_reparation()

        self.assertNotEqual(self.page.html_readability, "<p>vieux html</p>")
        self.assertNotEqual(self.page.content_hash, "vieux-hash")


class TitresDupliquesParLAplatissementTest(TestCase):
    """
    L'aplatissement ne doit jamais rendre deux sections ambigues.
    / Flattening must never make two sections ambiguous.

    « ## Conclusion » + « ### Conclusion » donneraient deux sections de
    meme titre : les DEUX deviennent alors inatteignables pour toujours
    (« le titre apparait 2 fois »). C'est exactement l'etat que la
    relecture F interdisait a l'insertion de creer.
    / Two same-titled sections make both permanently unreachable.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page = Page.objects.create(
            title="Wiki — collision", text_readability="",
            html_readability="", html_original="", content_hash="h",
            type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )

    def test_une_collision_de_titres_est_refusee_bruyamment(self):
        from front.tasks import _ecrire_le_corps_d_un_article

        pk_seuil = self.fixtures["extraction_seuil"].pk
        texte_du_modele = (
            "## Conclusion\n"
            "\n"
            f"Un paragraphe.[[ext:{pk_seuil}]]\n"
            "\n"
            "### Conclusion\n"
            "\n"
            f"Un autre paragraphe.[[ext:{pk_seuil}]]\n"
        )

        with self.assertRaises(ValueError) as levee:
            _ecrire_le_corps_d_un_article(
                self.page, texte_du_modele, {pk_seuil},
            )

        self.assertIn("Conclusion", str(levee.exception))
