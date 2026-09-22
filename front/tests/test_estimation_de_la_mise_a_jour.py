"""
Le cout d'une mise a jour de wiki, annonce AVANT le clic.
/ The cost of a wiki update, shown BEFORE the click.

LOCALISATION : front/tests/test_estimation_de_la_mise_a_jour.py

Le geste « Mettre a jour » appelle le redacteur, et c'est facture. La
modale qui le confirme annonce donc un cout estime, calcule par le
serveur a l'ouverture (GET /wikis/{id}/estimation/).

Trois garanties s'exercent ici :

- l'estimation compte EXACTEMENT le prompt que la tache enverra — un
  seul constructeur de prompt, jamais une copie qui divergerait ;
- elle n'ecrit RIEN : la reparation des titres `###`, qui ecrit en
  base, reste dans la tache ;
- un tarif inconnu s'affiche « non mesure », jamais « 0 € ».
/ Same prompt as the task, no write, unknown price never shown as 0.
"""

import math
import re
from unittest.mock import patch

import tiktoken
from django.contrib.auth.models import User
from django.test import TestCase

from core.models import (
    AIModel,
    ModeleParRole,
    Page,
    Provider,
    RoleDeModele,
    TourDeWiki,
    TypeDeNote,
    VisibiliteDossier,
    Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c


class BaseDeLEstimation(TestCase):
    """Un wiki qui cite une extraction sur deux. / A partial wiki."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.client.login(username="demandeur_synthese", password="test1234")

    def _creer_un_wiki(self, texte):
        page = Page.objects.create(
            title="Wiki du seuil", text_readability=texte,
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-estimation", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            page, self.fixtures["carnet"], self.fixtures["demandeur"],
        )
        return Wiki.objects.create(
            page=page, dossier=self.fixtures["carnet"], sujet="Le seuil",
        )

    def _un_wiki_partiel(self, niveau_de_titre="##"):
        return self._creer_un_wiki(
            f"{niveau_de_titre} Le seuil\n\nLe seuil est acté."
            f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n"
        )

    def _donner_au_redacteur_un_modele(self, nom="Mistral Medium"):
        # C'est `model_choice` qui porte l'identifiant : `save()` recopie
        # sa valeur dans `model_name`. Le provider explicite survit a la
        # table de prefixes (test_chemin_compatible_openai.py).
        # / model_choice carries the id; save() copies it to model_name.
        modele_tarife = AIModel.objects.create(
            name=nom, model_choice="mistral-medium-latest",
            provider=Provider.COMPATIBLE_OPENAI, is_active=False,
        )
        ModeleParRole.objects.create(
            role=RoleDeModele.REDACTEUR_D_ARTICLE, modele=modele_tarife,
        )
        return modele_tarife

    def _lire_l_estimation(self, wiki):
        reponse = self.client.get(
            f"/wikis/{wiki.pk}/estimation/", HTTP_HX_REQUEST="true",
        )
        return reponse, reponse.content.decode()

    def _tokens_annonces(self, contenu):
        trouve = re.search(r'data-tokens="(\d+)"', contenu)
        self.assertIsNotNone(trouve, "le partial doit porter data-tokens")
        return int(trouve.group(1))


class LeCoutEstAnnonceTest(BaseDeLEstimation):
    """Ce que la modale lit. / What the dialog reads."""

    def test_un_modele_au_tarif_connu_annonce_le_montant_calcule(self):
        # Un tarif ENORME, pour que le montant sorte du plancher de
        # 0,01 € : sinon n'importe quelle formule afficherait 0,01 et le
        # test ne prouverait rien. / A huge price, above the 0.01 floor.
        self._donner_au_redacteur_un_modele()
        wiki = self._un_wiki_partiel()

        with patch.dict(
            AIModel.TARIFS_PAR_MILLION_TOKENS,
            {"mistral-medium-latest": (1000.0, 1000.0)},
        ):
            reponse, contenu = self._lire_l_estimation(wiki)

        # Le calcul attendu, pas a pas, avec les conventions de la
        # confirmation de synthese : sortie a 50 % de l'entree, taux
        # 0,92, marge x1,5 arrondie au centime superieur.
        # / Expected amount, step by step, same conventions.
        tokens_entree = self._tokens_annonces(contenu)
        tokens_sortie = int(tokens_entree * 0.5)
        cout_brut_euros = (
            tokens_entree / 1_000_000 * 1000.0
            + tokens_sortie / 1_000_000 * 1000.0
        ) * 0.92
        montant_attendu = max(0.01, math.ceil(cout_brut_euros * 1.5 * 100) / 100)
        self.assertGreater(montant_attendu, 0.01)

        self.assertEqual(reponse.status_code, 200)
        self.assertIn('data-testid="wiki-estimation-cout"', contenu)
        self.assertIn(
            f"environ {montant_attendu:.2f} €".replace(".", ","), contenu,
        )
        self.assertIn("Mistral Medium", contenu)

    def test_un_modele_sans_nom_est_designe_par_son_libelle(self):
        # `AIModel.name` est facultatif : la phrase ne doit jamais dire
        # « envoyés à , pour ». / A blank name must not leave a hole.
        self._donner_au_redacteur_un_modele(nom="")
        wiki = self._un_wiki_partiel()

        _reponse, contenu = self._lire_l_estimation(wiki)

        self.assertNotRegex(contenu, r"envoyés à\s*,")

    def test_un_jeton_special_dans_une_extraction_ne_fait_pas_tomber_l_estimation(self):
        # tiktoken refuse par defaut le texte de ses jetons speciaux. Une
        # note qui parle de tokenizers en contient : l'estimation doit
        # compter ce texte comme du texte, pas repondre 500 (ce qui
        # remplacerait la modale par une boite d'erreur).
        # / Special-token text must be counted as text, not crash.
        from hypostasis_extractor.models import ExtractedEntity

        wiki = self._un_wiki_partiel()
        ExtractedEntity.objects.create(
            job=self.fixtures["extraction_seuil"].job,
            extraction_class="donnee",
            extraction_text="Le modèle s'arrête à <|endoftext|>.",
            start_char=0, end_char=10,
        )

        reponse, contenu = self._lire_l_estimation(wiki)

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("data-tokens", contenu)

    def test_un_tarif_inconnu_s_affiche_non_mesure(self):
        # Le modele des fixtures n'est dans aucune table de tarifs.
        # Annoncer « 0 € » avant un appel facture serait un chiffre
        # invente. / An unknown price is never shown as zero.
        wiki = self._un_wiki_partiel()

        _reponse, contenu = self._lire_l_estimation(wiki)

        self.assertIn('data-testid="wiki-estimation-non-mesuree"', contenu)
        self.assertIn("non mesuré", contenu)
        self.assertNotIn("€", contenu)

    def test_rien_a_reprendre_rien_a_annoncer(self):
        wiki = self._creer_un_wiki(
            f"## Le seuil\n\nActé."
            f"[[ext:{self.fixtures['extraction_seuil'].pk}]] Et coûteux."
            f"[[ext:{self.fixtures['extraction_cout'].pk}]]\n"
        )
        # Les SourceLink disent ce qui est repris : on passe par le
        # chemin d'ecriture normal. / Indexed links say what is taken up.
        from core.models import MotifDeTourDeWiki
        from core.services.synthese import extractions_du_perimetre
        from front.tasks import _ecrire_le_corps_d_un_article

        with patch("front.tasks.enchainer_la_verification"):
            _ecrire_le_corps_d_un_article(
                wiki.page, wiki.page.text_readability,
                set(
                    extractions_du_perimetre(wiki.page)
                    .values_list("pk", flat=True)
                ),
                motif_du_tour=MotifDeTourDeWiki.MAJ_MANUELLE,
                wiki_du_tour=wiki,
            )

        _reponse, contenu = self._lire_l_estimation(wiki)

        self.assertIn('data-testid="wiki-estimation-rien"', contenu)
        self.assertNotIn("data-tokens", contenu)

    def test_un_lecteur_qui_ne_peut_pas_ecrire_n_obtient_pas_l_estimation(self):
        # Meme porte que le geste « Mettre a jour » (_ecriture_ou_refus) :
        # qui ne peut pas relancer n'a pas a connaitre le cout. Le carnet
        # est PUBLIC — le tiers peut LIRE l'article — pour que le test
        # distingue la porte d'ecriture de la porte de lecture.
        # / A public notebook: the reader may read, but not estimate.
        wiki = self._un_wiki_partiel()
        carnet = self.fixtures["carnet"]
        carnet.visibilite = VisibiliteDossier.PUBLIC
        carnet.save(update_fields=["visibilite"])
        User.objects.create_user(username="tiers_estimation", password="x1234567")
        self.client.logout()
        self.client.login(username="tiers_estimation", password="x1234567")

        lecture = self.client.get(f"/wikis/{wiki.pk}/", HTTP_HX_REQUEST="true")
        reponse, contenu = self._lire_l_estimation(wiki)

        self.assertEqual(lecture.status_code, 200)
        self.assertIn(reponse.status_code, (403, 404))
        self.assertNotIn("data-tokens", contenu)


class LaMemeChoseQueLaTacheTest(BaseDeLEstimation):
    """
    L'estimation compte ce qui partira vraiment, et n'ecrit rien.
    / The estimate counts what will really be sent, and writes nothing.
    """

    def _prompt_envoye_par_la_tache(self, wiki):
        from front.tasks import construire_la_proposition_d_operations

        with patch(
            "core.llm_providers.appeler_llm", return_value="[]",
        ) as appel, patch("front.tasks.enchainer_la_verification"):
            construire_la_proposition_d_operations(
                wiki, self.fixtures["modele_ia"],
            )
        return appel.call_args.args[1]

    def test_l_estimation_compte_exactement_le_prompt_envoye(self):
        wiki = self._un_wiki_partiel()

        _reponse, contenu = self._lire_l_estimation(wiki)
        prompt_envoye = self._prompt_envoye_par_la_tache(wiki)

        encodeur = tiktoken.get_encoding("cl100k_base")
        self.assertEqual(
            self._tokens_annonces(contenu), len(encodeur.encode(prompt_envoye)),
        )

    def test_sur_un_article_a_reparer_l_estimation_n_ecrit_rien(self):
        # Un `###` herite : la tache le repare en base avant d'appeler le
        # modele. L'estimation, elle, ne doit toucher a rien.
        # / A legacy `###`: the task repairs it; the estimate must not.
        wiki = self._un_wiki_partiel(niveau_de_titre="###")
        texte_avant = wiki.page.text_readability

        self._lire_l_estimation(wiki)

        wiki.page.refresh_from_db()
        self.assertEqual(wiki.page.text_readability, texte_avant)
        self.assertFalse(TourDeWiki.objects.filter(wiki=wiki).exists())

    def test_sur_un_article_a_reparer_le_compte_est_celui_d_apres_reparation(self):
        wiki = self._un_wiki_partiel(niveau_de_titre="###")

        _reponse, contenu = self._lire_l_estimation(wiki)
        prompt_envoye = self._prompt_envoye_par_la_tache(wiki)

        encodeur = tiktoken.get_encoding("cl100k_base")
        self.assertEqual(
            self._tokens_annonces(contenu), len(encodeur.encode(prompt_envoye)),
        )


class LeVraiCheminDuGesteTest(BaseDeLEstimation):
    """
    Du clic a la tache, avec un redacteur qui N'EST PAS celui par defaut.
    / From the click to the task, with a non-default writer.

    Les tests ci-dessus appellent la proposition SANS job : elle resout
    alors l'analyseur avec la meme expression que l'estimation, et ils
    lui donneraient raison meme si les deux chemins divergeaient. Le vrai
    geste passe par un job : `mise_a_jour` y pose `analyseur_id`, que la
    tache relit (`_analyseur_fige_sur_le_job`). C'est ce chemin-la qu'on
    suit ici, avec une piece de prompt reconnaissable.
    / The real gesture goes through a job; this test follows it.
    """

    PIECE_RECONNAISSABLE = "PRÉAMBULE-DU-RÉDACTEUR-CHOISI-7Q2"

    def _un_wiki_avec_son_propre_redacteur(self):
        from hypostasis_extractor.models import (
            AnalyseurSyntaxique,
            PromptPiece,
        )

        redacteur_choisi = AnalyseurSyntaxique.objects.create(
            name="Rédacteur choisi", type_analyseur="rediger_un_article",
            is_active=True, est_par_defaut=False,
        )
        PromptPiece.objects.create(
            analyseur=redacteur_choisi,
            role=PromptPiece.RoleChoices.INSTRUCTION,
            content=self.PIECE_RECONNAISSABLE, order=0,
        )
        wiki = self._un_wiki_partiel()
        wiki.analyseur_de_redaction = redacteur_choisi
        wiki.save(update_fields=["analyseur_de_redaction"])
        return wiki

    def test_le_cout_annonce_est_celui_du_prompt_que_la_tache_envoie(self):
        from front.tasks import proposer_une_maj_de_wiki_task
        from hypostasis_extractor.models import ExtractionJob

        wiki = self._un_wiki_avec_son_propre_redacteur()

        _reponse, contenu = self._lire_l_estimation(wiki)

        with patch("front.tasks.proposer_une_maj_de_wiki_task.delay"):
            reponse_du_geste = self.client.post(
                f"/wikis/{wiki.pk}/mise_a_jour/", HTTP_HX_REQUEST="true",
            )
        self.assertEqual(reponse_du_geste.status_code, 200)
        job = ExtractionJob.objects.get(
            page=wiki.page, raw_result__est_maj_wiki=True,
        )

        with patch(
            "core.llm_providers.appeler_llm", return_value="[]",
        ) as appel, patch("front.tasks.enchainer_la_verification"):
            proposer_une_maj_de_wiki_task(job.pk)
        prompt_envoye = appel.call_args.args[1]

        # Le redacteur choisi a bien ecrit le preambule envoye…
        # / The chosen writer's preamble is the one sent…
        self.assertIn(self.PIECE_RECONNAISSABLE, prompt_envoye)
        # … et c'est lui que l'estimation a compte.
        # / … and it is the one the estimate counted.
        encodeur = tiktoken.get_encoding("cl100k_base")
        self.assertEqual(
            self._tokens_annonces(contenu), len(encodeur.encode(prompt_envoye)),
        )


class LaModaleSaitOuChercherTest(BaseDeLEstimation):
    """Le bouton porte l'adresse de l'estimation. / The button knows."""

    def test_le_geste_mettre_a_jour_porte_l_adresse_de_l_estimation(self):
        wiki = self._un_wiki_partiel()

        contenu = self.client.get(
            f"/wikis/{wiki.pk}/", HTTP_HX_REQUEST="true",
        ).content.decode()

        self.assertIn(
            f'data-url-estimation="/wikis/{wiki.pk}/estimation/"', contenu,
        )
