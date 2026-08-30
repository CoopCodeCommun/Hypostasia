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

    def _element(self, texte, ordre, masque=False):
        return ElementDocument.objects.create(
            page=self.page, ordre=ordre, label="text", texte=texte,
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

    def test_aucun_journal_n_est_ecrit_quand_le_lot_est_refuse(self):
        """/ No journal entry when the batch is refused."""
        self._lancer_une_analyse()
        avant = PageEdit.objects.filter(page=self.page).count()
        self._poster([self._bloc(self.blocs[0], "Un.")])
        self.assertEqual(PageEdit.objects.filter(page=self.page).count(), avant)


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
