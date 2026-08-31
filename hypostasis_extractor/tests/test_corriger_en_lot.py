"""
Tests de `corriger_en_lot` — l'enregistrement d'une session d'edition.
/ Tests for the batch save of an editing session.

LOCALISATION : hypostasis_extractor/tests/test_corriger_en_lot.py

SPEC-edition-par-blocs-et-stenotypie.md § 7, § 8 et § 10.

CE QUE CET ENDPOINT DOIT GARANTIR, ET QUI SE TESTE ICI :

  - il compare le TEXTE BRUT, jamais l'empreinte normalisee : une
    correction de casse ou d'espace DOIT etre enregistree (§ 7.2) ;
  - un bloc vide est MASQUE, jamais supprime (§ 7.3) ;
  - un bloc disparu est refuse LUI SEUL, et le lot passe quand meme (§ 7.4) ;
  - une analyse qui tourne refuse le lot ENTIER (§ 8.1) ;
  - il rend CINQ NOMBRES et la LISTE des refus — un compte sans liste ne
    dit pas quoi retaper (§ 7.4) ;
  - il ecrit UN PageEdit par lot, pas un par bloc (§ 10).
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AppartenancePageDossier,
    Dossier,
    ElementDocument,
    Page,
    PageEdit,
    empreinte_du_texte,
)

Utilisateur = get_user_model()


class BaseDuLot(TestCase):
    """Socle : une note de cinq blocs, son proprietaire, un tiers."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprietaire-lot", password="motdepasse",
        )
        self.tiers = Utilisateur.objects.create_user(
            username="tiers-lot", password="motdepasse",
        )
        self.dossier = Dossier.objects.create(
            name="Carnet du lot", owner=self.proprietaire,
        )
        self.page = Page.objects.create(
            url="http://exemple.local/le-lot",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-du-lot",
            owner=self.proprietaire, dossier=self.dossier,
        )
        AppartenancePageDossier.objects.create(
            page=self.page, dossier=self.dossier,
        )
        self.blocs = [
            self._element("Le premier bloc de la note.", 0),
            self._element("le deuxieme bloc, en minuscules.", 1),
            self._element("Le troisieme  bloc, avec deux espaces.", 2),
            self._element("Le quatrieme bloc, qu'on videra.", 3),
            self._element("Le cinquieme bloc, intouche.", 4),
        ]
        self.client.force_login(self.proprietaire)

    def _element(self, texte, ordre, masque=False, label="text"):
        return ElementDocument.objects.create(
            page=self.page, ordre=ordre, label=label, texte=texte,
            empreinte_contenu=empreinte_du_texte(texte), masque=masque,
        )

    def _poster(self, blocs):
        return self.client.post(
            "/elements/corriger_en_lot/",
            data=json.dumps({"blocs": blocs}),
            content_type="application/json",
        )

    def _bloc(self, element, texte):
        return {
            "identifiant_stable": str(element.identifiant_stable),
            "texte": texte,
        }


class LeLotEnregistreCeQuiADImportant(BaseDuLot):
    """Le contrat du § 7.2 : on compare le texte BRUT."""

    def test_une_correction_ordinaire_est_enregistree(self):
        reponse = self._poster([
            self._bloc(self.blocs[0], "Le premier bloc, corrigé."),
        ])
        self.assertEqual(reponse.status_code, 200)
        self.blocs[0].refresh_from_db()
        self.assertEqual(self.blocs[0].texte, "Le premier bloc, corrigé.")

    def test_une_correction_de_CASSE_seule_est_enregistree(self):
        """
        L'empreinte normalisee met tout en minuscules : comparer dessus
        jetterait cette correction EN SILENCE. C'est le test qui aurait
        attrape l'erreur de la v1.0 de la spec.
        / A case-only fix must be saved: the normalized fingerprint hides it.
        """
        avant = self.blocs[1].texte
        apres = avant.capitalize()
        self.assertEqual(
            empreinte_du_texte(avant), empreinte_du_texte(apres),
            "le jeu d'essai doit avoir la MEME empreinte normalisee",
        )
        self._poster([self._bloc(self.blocs[1], apres)])
        self.blocs[1].refresh_from_db()
        self.assertEqual(self.blocs[1].texte, apres)

    def test_une_correction_d_ESPACES_seule_est_enregistree(self):
        """
        L'empreinte normalisee ecrase les suites d'espaces. Or une double
        espace corrigee DECALE tous les offsets qui suivent.
        / Whitespace-only fixes move every following offset.
        """
        avant = self.blocs[2].texte
        apres = avant.replace("troisieme  bloc", "troisieme bloc")
        self.assertEqual(
            empreinte_du_texte(avant), empreinte_du_texte(apres),
            "le jeu d'essai doit avoir la MEME empreinte normalisee",
        )
        self._poster([self._bloc(self.blocs[2], apres)])
        self.blocs[2].refresh_from_db()
        self.assertEqual(self.blocs[2].texte, apres)

    def test_un_bloc_inchange_n_est_pas_touche(self):
        """/ An unchanged block is not touched at all."""
        avant = self.blocs[4].updated_at
        self._poster([self._bloc(self.blocs[4], self.blocs[4].texte)])
        self.blocs[4].refresh_from_db()
        self.assertEqual(self.blocs[4].updated_at, avant)


class LeBlocVideEstMasque(BaseDuLot):
    """§ 7.3 et § 5.3 : masquer, jamais supprimer."""

    def test_un_bloc_vide_est_masque_et_non_supprime(self):
        self._poster([self._bloc(self.blocs[3], "")])
        self.blocs[3].refresh_from_db()
        self.assertTrue(self.blocs[3].masque)
        self.assertTrue(
            ElementDocument.objects.filter(pk=self.blocs[3].pk).exists(),
            "l'element doit SURVIVRE au masquage",
        )

    def test_un_bloc_fait_uniquement_d_espaces_est_masque(self):
        """/ A whitespace-only block counts as empty."""
        self._poster([self._bloc(self.blocs[3], "   \n  ")])
        self.blocs[3].refresh_from_db()
        self.assertTrue(self.blocs[3].masque)


class LeCompteRendu(BaseDuLot):
    """§ 7.4 : cinq nombres et une liste."""

    def test_le_compte_rendu_porte_les_cinq_nombres(self):
        reponse = self._poster([
            self._bloc(self.blocs[0], "Un texte neuf."),
            self._bloc(self.blocs[3], ""),
            self._bloc(self.blocs[4], self.blocs[4].texte),
        ])
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        for nom in ("blocs-modifies", "blocs-masques", "ancres-detachees",
                    "citations-detachees", "blocs-refuses"):
            self.assertIn(nom, corps, f"le compte rendu doit porter {nom}")

    def test_un_bloc_disparu_est_refuse_LUI_SEUL(self):
        """
        Un tiers a scinde ou fusionne : l'identifiant envoye n'existe
        plus. Ce bloc-la est refuse, les autres passent — et SURTOUT
        aucun rechargement n'est declenche (§ 7.4).
        / That block alone is refused; the others go through.
        """
        reponse = self._poster([
            self._bloc(self.blocs[0], "Celui-ci doit passer."),
            {"identifiant_stable": "3f7c1e2a-0000-4000-8000-000000000000",
             "texte": "Celui-ci a disparu."},
        ])
        self.assertEqual(reponse.status_code, 200)
        self.blocs[0].refresh_from_db()
        self.assertEqual(self.blocs[0].texte, "Celui-ci doit passer.")
        corps = reponse.content.decode()
        self.assertIn("3f7c1e2a-0000-4000-8000-000000000000", corps,
                      "le compte rendu doit NOMMER le bloc refuse")
        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertNotIn("lectureReload", declencheurs)

    def test_le_compte_rendu_dit_le_motif_de_chaque_refus(self):
        """Un compte sans motif ne dit pas quoi faire. / A count without a reason is useless."""
        reponse = self._poster([
            {"identifiant_stable": "3f7c1e2a-0000-4000-8000-000000000000",
             "texte": "disparu"},
        ])
        self.assertIn("disparu", reponse.content.decode().lower())


class LeResumeDuToast(BaseDuLot):
    """
    Le resume que porte `HX-Trigger` — c'est LE seul retour visible d'un
    enregistrement reussi, en haut a droite, quel que soit le
    defilement. Le compte rendu detaille, lui, s'affiche EN TETE de la
    note : en bas d'une note de 200 blocs, on ne le voit pas.
    / The header summary is the only visible feedback of a good save.

    IL NE DIT QUE CE QUI A EU LIEU. « 0 corrige, 0 masque, 0 refuse »
    fait lire trois nombres pour apprendre qu'il ne s'est rien passe.
    """

    def _resume(self, reponse):
        return json.loads(reponse["HX-Trigger"])["showToast"]["message"]

    def test_une_seule_correction_s_accorde_au_SINGULIER(self):
        reponse = self._poster([self._bloc(self.blocs[0], "Un texte neuf.")])
        self.assertEqual(self._resume(reponse), "1 passage corrigé.")

    def test_plusieurs_corrections_s_accordent_au_PLURIEL(self):
        reponse = self._poster([
            self._bloc(self.blocs[0], "Un texte neuf."),
            self._bloc(self.blocs[1], "Un autre texte neuf."),
        ])
        self.assertEqual(self._resume(reponse), "2 passages corrigés.")

    def test_le_resume_NE_DIT_PAS_les_comptes_a_zero(self):
        """Trois nombres pour apprendre qu'il ne s'est rien passe.
        / Three numbers to learn that nothing happened."""
        reponse = self._poster([self._bloc(self.blocs[3], "")])
        self.assertEqual(self._resume(reponse), "1 passage masqué.")

    def test_le_resume_CUMULE_ce_qui_a_eu_lieu(self):
        reponse = self._poster([
            self._bloc(self.blocs[0], "Un texte neuf."),
            self._bloc(self.blocs[3], ""),
        ])
        self.assertEqual(
            self._resume(reponse), "1 passage corrigé, 1 masqué.",
        )

    def test_un_refus_est_DIT_dans_le_resume(self):
        reponse = self._poster([
            self._bloc(self.blocs[0], "Un texte neuf."),
            {"identifiant_stable": "3f7c1e2a-0000-4000-8000-000000000000",
             "texte": "disparu"},
        ])
        self.assertEqual(
            self._resume(reponse), "1 passage corrigé, 1 refusé.",
        )

    def test_un_lot_SANS_EFFET_le_dit_clairement(self):
        """
        Renvoyer le meme texte n'est pas une erreur — le mode envoie
        TOUS les blocs. Mais le dire « 0 corrige » ferait croire a une
        panne. / Sending unchanged text is not an error, but "0" reads
        like a failure.
        """
        reponse = self._poster([
            self._bloc(self.blocs[0], self.blocs[0].texte),
        ])
        self.assertEqual(self._resume(reponse), "Aucun changement à enregistrer.")

    def test_l_icone_passe_en_AVERTISSEMENT_des_qu_un_bloc_est_refuse(self):
        reponse = self._poster([
            {"identifiant_stable": "3f7c1e2a-0000-4000-8000-000000000000",
             "texte": "disparu"},
        ])
        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertEqual(declencheurs["showToast"]["icon"], "warning")


class UnBlocMASQUE(BaseDuLot):
    """
    Addendum B : corriger un bloc deja masque est REFUSE.

    POURQUOI, ET CE QUE CELA COUTAIT

    `demasquer_un_element` ne rattache ses portions que si le texte n'a
    pas bouge depuis le masquage — il compare deux empreintes du texte
    brut. Un lot qui corrige un bloc masque passe entre les deux :
    mesure du 29 aout, sur un element portant 3 portions, masquer puis
    demasquer en rattache 3 ; masquer, CORRIGER, puis demasquer en
    rattache 0 et en laisse 3 detachees. **Definitivement, et sans que
    rien ne le dise.**
    / Correcting a hidden block breaks its un-hiding, forever, in silence.
    """

    def setUp(self):
        super().setUp()
        self.blocs[0].masque = True
        self.blocs[0].save(update_fields=["masque"])

    def test_du_texte_pour_un_bloc_masque_est_REFUSE(self):
        reponse = self._poster([
            self._bloc(self.blocs[0], "Un texte pour un bloc masqué."),
        ])
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        self.assertIn(str(self.blocs[0].identifiant_stable), corps,
                      "le compte rendu doit NOMMER le bloc refusé")
        self.assertIn("1", corps)

    def test_le_texte_du_bloc_masque_N_EST_PAS_touche(self):
        """
        Le refus doit etre effectif : si le texte changeait quand meme,
        le demasquage serait casse pour toujours.
        / The refusal must be effective, or un-hiding breaks forever.
        """
        avant = self.blocs[0].texte
        self._poster([self._bloc(self.blocs[0], "Un texte pour un bloc masqué.")])
        self.blocs[0].refresh_from_db()
        self.assertEqual(self.blocs[0].texte, avant)
        self.assertTrue(self.blocs[0].masque, "il doit rester masqué")

    def test_le_refus_dit_son_motif(self):
        """Un compte sans motif ne dit pas quoi faire (§ 7.4)."""
        reponse = self._poster([
            self._bloc(self.blocs[0], "Un texte pour un bloc masqué."),
        ])
        self.assertIn("masqué", reponse.content.decode().lower())

    def test_les_AUTRES_blocs_du_lot_passent_quand_meme(self):
        """
        Le refus porte sur CE bloc, et lui seul — comme pour un bloc
        disparu. / The refusal covers this block alone.
        """
        self._poster([
            self._bloc(self.blocs[0], "Refusé."),
            self._bloc(self.blocs[1], "Celui-ci doit passer."),
        ])
        self.blocs[1].refresh_from_db()
        self.assertEqual(self.blocs[1].texte, "Celui-ci doit passer.")

    def test_un_bloc_masque_qu_on_VIDE_reste_un_non_geste(self):
        """
        L'addendum B ne change PAS ce cas : vider un bloc deja masque
        n'ecrit rien, ne compte rien, ne journalise rien.
        / Emptying an already-hidden block stays a no-op.
        """
        from core.models import PageEdit
        journaux = PageEdit.objects.filter(page=self.page).count()
        reponse = self._poster([self._bloc(self.blocs[0], "")])
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        self.assertIn("0", corps)
        self.assertEqual(PageEdit.objects.filter(page=self.page).count(), journaux)
        self.assertNotIn(str(self.blocs[0].identifiant_stable), corps,
                         "un non-geste ne se refuse pas non plus")


class LesRefus(BaseDuLot):
    """§ 8 : les refus, et leur portee."""

    def test_un_tiers_qui_ne_peut_pas_LIRE_recoit_404(self):
        """
        Qui n'a pas acces a la note n'apprend rien : 404, jamais 403.

        Sans cette garde, poster un `identifiant_stable` vole permettait
        de distinguer « ce bloc existe mais tu n'y touches pas » (403)
        de « ce bloc n'existe pas » (le compte rendu « disparu ») — une
        difference qui est une information.
        / No read access: 404, never 403.
        """
        self.client.force_login(self.tiers)
        reponse = self._poster([self._bloc(self.blocs[0], "Pas le droit.")])
        self.assertEqual(reponse.status_code, 404)
        self.blocs[0].refresh_from_db()
        self.assertEqual(self.blocs[0].texte, "Le premier bloc de la note.")

    def test_un_tiers_qui_peut_LIRE_mais_pas_ecrire_recoit_403(self):
        """
        La personne VOIT deja la note : lui repondre 404 ne cacherait
        rien et l'egarerait. Le refus d'ecriture se dit donc.
        / They can already see the note: a 404 would hide nothing.
        """
        from core.models import VisibiliteDossier
        self.dossier.visibilite = VisibiliteDossier.PUBLIC
        self.dossier.save(update_fields=["visibilite"])
        self.client.force_login(self.tiers)
        reponse = self._poster([self._bloc(self.blocs[0], "Pas le droit.")])
        self.assertEqual(reponse.status_code, 403)
        self.blocs[0].refresh_from_db()
        self.assertEqual(self.blocs[0].texte, "Le premier bloc de la note.")

    def test_des_blocs_de_DEUX_pages_sont_refuses(self):
        """
        Un lot est l'enregistrement d'UNE session sur UNE note. Melanger
        deux pages rendrait la garde d'analyse — qui est au niveau PAGE —
        impossible a poser. / A batch is one session on one note.
        """
        autre_page = Page.objects.create(
            url="http://exemple.local/autre", html_original="<p>o</p>",
            html_readability="<p>l</p>", text_readability="t",
            content_hash="hash-autre", owner=self.proprietaire,
        )
        etranger = ElementDocument.objects.create(
            page=autre_page, ordre=0, label="text", texte="Ailleurs.",
            empreinte_contenu=empreinte_du_texte("Ailleurs."),
        )
        reponse = self._poster([
            self._bloc(self.blocs[0], "Ici."),
            self._bloc(etranger, "Ailleurs, corrigé."),
        ])
        self.assertEqual(reponse.status_code, 400)
        etranger.refresh_from_db()
        self.assertEqual(etranger.texte, "Ailleurs.")

    def test_un_lot_vide_est_refuse(self):
        self.assertEqual(self._poster([]).status_code, 400)


class UnTABLEAU(BaseDuLot):
    """
    § 12 : un tableau ne se relit pas — il est refuse, ce bloc seul.
    / A table cannot be read back: refused, that block alone.

    POURQUOI CETTE GARDE EXISTE COTE SERVEUR

    Le `texte` d'un element `table` est du markdown « pipe » ; ce qui
    s'affiche est un <table> construit APRES le marquage, et aucun
    chemin HTML -> markdown n'existe dans le depot. Ce qu'un client lit
    du tableau rendu differe donc TOUJOURS de la base :
    « CategorieArgument » au lieu de « | Categorie | Argument | ».

    Le mode d'edition ne les envoie plus. Cette garde-ci est pour le
    CLIENT PERIME — celui qui a charge la page avant que la regle
    n'existe. Sans elle, un enregistrement sur une note a tableaux les
    ecrasait tous, SANS QUE PERSONNE N'Y AIT TOUCHE.
    """

    def setUp(self):
        super().setUp()
        self.tableau = self._element(
            "| Catégorie | Argument |\n| --- | --- |\n| Coût | 6 500 euros |",
            5, label="table",
        )

    def test_un_tableau_MODIFIE_est_refuse(self):
        compte_rendu_html = self._poster([
            self._bloc(self.tableau, "CatégorieArgumentCoût6 500 euros"),
        ])
        self.assertEqual(compte_rendu_html.status_code, 200)
        self.assertIn(str(self.tableau.identifiant_stable),
                      compte_rendu_html.content.decode())

    def test_le_texte_du_tableau_N_EST_PAS_ecrase(self):
        """Le degat que cette garde interdit, mesure en base.
        / The exact damage the guard forbids."""
        avant = self.tableau.texte
        self._poster([
            self._bloc(self.tableau, "CatégorieArgumentCoût6 500 euros"),
        ])
        self.tableau.refresh_from_db()
        self.assertEqual(self.tableau.texte, avant)

    def test_le_refus_du_tableau_DIT_que_c_est_un_tableau(self):
        """Un refus sans motif est un bug d'interface.
        / A refusal without a reason is a UI bug."""
        reponse = self._poster([
            self._bloc(self.tableau, "CatégorieArgument"),
        ])
        self.assertIn("tableau", reponse.content.decode().lower())

    def test_VIDER_un_tableau_est_refuse_AUSSI(self):
        """
        Le vider n'est pas moins destructeur que le corriger : le refus
        est pose AVANT la branche du masquage.
        / Emptying is no less destructive: the guard comes first.
        """
        reponse = self._poster([self._bloc(self.tableau, "")])
        self.tableau.refresh_from_db()
        self.assertFalse(self.tableau.masque)
        # ET LE REFUS SE DIT. Sans cette assertion, ignorer le tableau
        # en silence — un `continue` sans `refuser` — passerait pour un
        # succes : la personne croirait avoir masque ce qui n'a pas
        # bouge.
        # / And the refusal is REPORTED: silence would read as success.
        corps = reponse.content.decode()
        self.assertIn(str(self.tableau.identifiant_stable), corps)
        self.assertIn("tableau", corps.lower())

    def test_les_AUTRES_blocs_du_lot_passent_quand_meme(self):
        """Ce bloc seul est refuse, jamais le lot.
        / That block alone, never the batch."""
        self._poster([
            self._bloc(self.tableau, "CatégorieArgument"),
            self._bloc(self.blocs[0], "Le premier bloc, corrigé."),
        ])
        self.blocs[0].refresh_from_db()
        self.assertEqual(self.blocs[0].texte, "Le premier bloc, corrigé.")

    def test_un_tableau_INCHANGE_ne_produit_AUCUN_refus(self):
        """
        Un client perime renvoie TOUS les blocs, tableaux compris. Ceux
        qu'il n'a pas touches ne doivent pas remplir le compte rendu de
        refus : le texte identique sort avant la garde.
        / An untouched table must not raise a refusal.
        """
        reponse = self._poster([self._bloc(self.tableau, self.tableau.texte)])
        corps = reponse.content.decode()
        self.assertNotIn(str(self.tableau.identifiant_stable), corps)


class UneAnalyseRefuseLeLotENTIER(BaseDuLot):
    """
    § 8.1 : le refus n'est pas partiel. Une analyse qui tourne travaille
    sur un texte qui n'existe plus ; laisser passer la moitie du lot
    donnerait des ancres fausses en silence, ou une analyse entiere
    perdue et facturee.
    / The refusal is total, never partial.
    """

    def _lancer_une_analyse(self):
        from hypostasis_extractor.models import ExtractionJob
        return ExtractionJob.objects.create(
            page=self.page, status="processing",
        )

    def test_une_analyse_qui_tourne_refuse_TOUT_le_lot(self):
        self._lancer_une_analyse()
        reponse = self._poster([
            self._bloc(self.blocs[0], "Un."),
            self._bloc(self.blocs[1], "Deux."),
        ])
        self.assertEqual(reponse.status_code, 409)

    def test_le_texte_n_est_PAS_perdu_quand_une_analyse_refuse(self):
        """
        Zero passe. Aucun bloc ne doit avoir bouge : un lot a moitie
        ecrit serait pire que pas de lot du tout.
        / Zero go through: a half-written batch is worse than none.
        """
        self._lancer_une_analyse()
        self._poster([
            self._bloc(self.blocs[0], "Un."),
            self._bloc(self.blocs[1], "Deux."),
            self._bloc(self.blocs[3], ""),
        ])
        for bloc in self.blocs:
            avant = bloc.texte
            bloc.refresh_from_db()
            self.assertEqual(bloc.texte, avant)
            self.assertFalse(bloc.masque)

    def test_une_analyse_qui_DEMARRE_PENDANT_le_lot_annule_TOUT(self):
        """
        LE REFUS SUBSISTE A L'ECRITURE, PAS SEULEMENT A L'ENTREE (§ 8.1).

        La garde d'entree ne voit que l'instant du POST. Entre elle et
        le commit, une analyse peut demarrer — et le lot ecrirait alors
        sous les pieds d'un job qui lit le texte : des ancres fausses,
        en silence, ou l'analyse entiere perdue et facturee.

        CE CHEMIN ETAIT OUVERT POUR LES VIDAGES SEULS. Le lot appelle
        `masquer_un_element(..., verifier_les_jobs=False)` : le service
        ne repose donc pas la garde, alors que
        `reconcilier_les_portions_de_l_element` le fait pour les
        corrections. Un lot fait uniquement de vidages n'etait protege
        que par la garde d'entree.
        / The write-time guard must hold for a batch of hides too.
        """
        from unittest import mock

        from hypostasis_extractor.services import masquage as service_masquage

        vrai_masquer = service_masquage.masquer_un_element

        def masquer_puis_lancer_une_analyse(*arguments, **nommes):
            """Une analyse surgit APRES le premier masquage du lot."""
            resultat = vrai_masquer(*arguments, **nommes)
            self._lancer_une_analyse()
            return resultat

        with mock.patch.object(
            service_masquage, "masquer_un_element",
            side_effect=masquer_puis_lancer_une_analyse,
        ):
            reponse = self._poster([
                self._bloc(self.blocs[3], ""),
                self._bloc(self.blocs[4], ""),
            ])

        self.assertEqual(reponse.status_code, 409)
        # ET RIEN N'EST ECRIT : le masquage deja fait est annule avec le
        # reste. Un lot a moitie ecrit serait pire que pas de lot.
        # / And nothing is written: the hide already done is rolled back.
        for bloc in (self.blocs[3], self.blocs[4]):
            bloc.refresh_from_db()
            self.assertFalse(
                bloc.masque,
                "le masquage doit être annulé avec le reste du lot",
            )
        self.assertEqual(PageEdit.objects.filter(page=self.page).count(), 0)

    def test_un_lot_SANS_ECRITURE_ne_declenche_pas_le_refus_tardif(self):
        """
        La garde de fin ne se pose que s'il y a quelque chose a
        proteger. Un lot ou rien n'a change n'ecrit rien : le refuser
        n'annulerait rien et dirait a la personne qu'elle a perdu un
        travail qu'elle n'a pas fait.
        / The late guard only fires when there is something to protect.
        """
        from unittest import mock

        from hypostasis_extractor.services import masquage as service_masquage

        vrai_masquer = service_masquage.masquer_un_element

        def masquer_puis_lancer_une_analyse(*arguments, **nommes):
            resultat = vrai_masquer(*arguments, **nommes)
            self._lancer_une_analyse()
            return resultat

        with mock.patch.object(
            service_masquage, "masquer_un_element",
            side_effect=masquer_puis_lancer_une_analyse,
        ):
            # Le meme texte : aucun bloc ne bouge, aucun service appele.
            # / The same text: nothing moves, no service is called.
            reponse = self._poster([
                self._bloc(self.blocs[0], self.blocs[0].texte),
            ])
        self.assertEqual(reponse.status_code, 200)

    def test_aucun_journal_n_est_ecrit_quand_le_lot_est_refuse(self):
        """/ No journal entry when the batch is refused."""
        self._lancer_une_analyse()
        avant = PageEdit.objects.filter(page=self.page).count()
        self._poster([self._bloc(self.blocs[0], "Un.")])
        self.assertEqual(PageEdit.objects.filter(page=self.page).count(), avant)


class LaBorneEtLesDoublons(BaseDuLot):
    """
    § 7.4 : ce qu'un lot ECARTE est compte et NOMME, jamais jete en
    silence. / What a batch drops is counted and named, never dropped
    silently.
    """

    def test_un_bloc_envoye_DEUX_FOIS_n_est_compte_qu_une_fois(self):
        """
        LE MEME BLOC DEUX FOIS CORROMPRAIT LE JOURNAL.

        A la seconde occurrence, l'element en memoire porte encore
        l'ancien texte : le service relit sous verrou, trouve « rien a
        faire », et rendrait un `ancien_texte` qui EST le nouveau. Le
        journal ecrirait alors un « avant » egal a l'« apres », et le
        compte annoncerait deux blocs modifies pour un seul.
        / The same block twice would write a journal whose "before"
        equals its "after".
        """
        reponse = self._poster([
            self._bloc(self.blocs[0], "Un texte neuf."),
            self._bloc(self.blocs[0], "Un texte neuf."),
        ])
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        self.assertIn("deux fois", corps,
                      "le doublon doit être nommé, pas jeté en silence")
        journal = PageEdit.objects.get(page=self.page)
        self.assertEqual(len(journal.donnees_avant["blocs"]), 1)
        self.assertEqual(
            journal.donnees_avant["blocs"][str(self.blocs[0].identifiant_stable)],
            "Le premier bloc de la note.",
            "le « avant » du journal doit être l'ancien texte, pas le neuf",
        )

    def test_les_blocs_AU_DELA_de_la_borne_sont_ecartes_ET_NOMMES(self):
        """
        Un lot fait un verrou et une reconciliation par bloc modifie. La
        borne protege la base ; ce qu'elle ecarte doit se dire, sinon la
        personne croit avoir enregistre ce qui n'est jamais parti.
        / The cap protects the DB; what it drops must be said.
        """
        from hypostasis_extractor.serializers import CorrectionEnLotSerializer

        borne = CorrectionEnLotSerializer.BORNE_DU_LOT
        # Le bloc reel est le PREMIER : il passe. Les suivants sont
        # inventes, et seuls ceux au-dela de la borne sont « ecartes ».
        # / The real block comes first; the rest are made up.
        lot = [self._bloc(self.blocs[0], "Un texte neuf.")]
        for numero in range(borne):
            lot.append({
                "identifiant_stable": f"3f7c1e2a-0000-4000-8000-{numero:012d}",
                "texte": "bloc de remplissage",
            })
        reponse = self._poster(lot)
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        self.assertIn("borne", corps, "l'écart doit dire POURQUOI")
        # LE NOMBRE, pas seulement le mot : 499 identifiants inventes
        # dans la borne (refuses « disparu ») + 1 au-dela (« ecarte »).
        # Sans ce compte, un decalage d'un cran sur `blocs_postes[borne:]`
        # passerait inapercu.
        # / The COUNT, not just the word: an off-by-one would slip by.
        import re
        trouve = re.search(
            r'data-testid="blocs-refuses">\s*<strong>(\d+)</strong>', corps,
        )
        self.assertIsNotNone(trouve)
        self.assertEqual(int(trouve.group(1)), borne)
        # Le dernier envoye est le seul au-dela de la borne.
        # / The last one sent is the only one past the cap.
        self.assertIn(f"3f7c1e2a-0000-4000-8000-{borne - 1:012d}", corps)
        self.blocs[0].refresh_from_db()
        self.assertEqual(self.blocs[0].texte, "Un texte neuf.")


class LeJournal(BaseDuLot):
    """§ 10 : UN PageEdit par lot, jamais un par bloc."""

    def test_un_seul_page_edit_par_lot(self):
        avant = PageEdit.objects.filter(page=self.page).count()
        self._poster([
            self._bloc(self.blocs[0], "Un."),
            self._bloc(self.blocs[1], "Deux."),
            self._bloc(self.blocs[2], "Trois."),
        ])
        apres = PageEdit.objects.filter(page=self.page).count()
        self.assertEqual(apres - avant, 1,
                         "trois blocs corriges, UNE entree de journal")

    def test_le_journal_porte_l_avant_et_l_apres_de_chaque_bloc(self):
        self._poster([
            self._bloc(self.blocs[0], "Le premier, refait."),
            self._bloc(self.blocs[1], "Le deuxieme, refait."),
        ])
        edit = PageEdit.objects.filter(page=self.page).latest("id")
        avant = json.dumps(edit.donnees_avant, ensure_ascii=False)
        apres = json.dumps(edit.donnees_apres, ensure_ascii=False)
        self.assertIn("Le premier bloc de la note.", avant)
        self.assertIn("Le premier, refait.", apres)
        self.assertIn(str(self.blocs[0].identifiant_stable), apres)
