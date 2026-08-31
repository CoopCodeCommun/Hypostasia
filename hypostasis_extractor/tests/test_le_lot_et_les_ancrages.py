"""
Tests du lot d'edition FACE A DE VRAIS ANCRAGES.
/ Tests of the batch save against REAL anchors.

LOCALISATION : hypostasis_extractor/tests/test_le_lot_et_les_ancrages.py

SPEC-edition-par-blocs-et-stenotypie.md § 7.3, § 7.4, § 8.2.
(§ 8.1 est l'ANALYSE, et rien ici ne la teste : le refus par
synthese figee est le § 8.2.)
SPEC-synthese-carnet.md § 4.2 et § 5.

POURQUOI CE FICHIER EXISTE A COTE DE `test_corriger_en_lot.py`

La fixture de l'autre fichier ne porte AUCUN ancrage : ses blocs sont du
texte nu. Trois promesses du § 7.4 n'y sont donc jamais eprouvees, et
deux d'entre elles sont les plus frequentes en usage reel :

  - un bloc cite par une synthese FIGEE est refuse, LUI SEUL, et le
    reste du lot passe quand meme. C'est le chemin le plus delicat de
    l'endpoint : l'exception est attrapee A L'INTERIEUR du
    `transaction.atomic()` du lot, et le lot doit continuer d'ecrire
    apres elle ;
  - `ancres_detachees` compte les portions que le geste a decrochees ;
  - `citations_detachees` compte les citations que ces portions
    alimentaient — un nombre A PART, parce qu'il dit ce que le geste
    coute a la couche synthese.

Ici, chaque bloc porte donc une vraie extraction, une vraie portion, et
pour deux d'entre eux une vraie citation.
/ The other fixture has no anchors at all: three § 7.4 promises were
never exercised. Here every block carries a real portion.

CE QUI NE BLOQUE PAS, ET C'EST VOULU : un WIKI cite sans geler. Seule
une synthese dirigee est un acte adopte (SPEC-synthese § 5).
"""

import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AppartenancePageDossier,
    Dossier,
    ElementDocument,
    EtatDeLaSource,
    Page,
    PageEdit,
    SourceLink,
    SyntheseDirigee,
    TypeDeNote,
    TypeLien,
    Wiki,
    empreinte_du_texte,
)
from core.services.synthese import indexer_les_citations
from hypostasis_extractor.models import (
    AncrageExtraction,
    EtatAncrage,
    ExtractedEntity,
    ExtractionJob,
)

Utilisateur = get_user_model()


class BaseDuLotAvecAncrages(TestCase):
    """
    Une note de quatre blocs, dont trois portent une portion d'extraction.
    / A four-block note, three of them carrying an extraction portion.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprietaire-ancres", password="motdepasse",
        )
        self.dossier = Dossier.objects.create(
            name="Carnet des ancres", owner=self.proprietaire,
        )
        self.page = Page.objects.create(
            url="http://exemple.local/le-lot-ancre",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-du-lot-ancre",
            owner=self.proprietaire, dossier=self.dossier,
            title="La note qui porte des ancres",
        )
        AppartenancePageDossier.objects.create(
            page=self.page, dossier=self.dossier,
        )
        self.job = ExtractionJob.objects.create(
            page=self.page, name="Analyse des ancres",
            status="completed", ai_model=None,
        )

        # Le bloc GELE : une synthese adoptee cite son passage.
        # / The FROZEN block: an adopted synthesis cites its passage.
        self.bloc_gele = self._element(
            "Le passage adopte par le collectif en mars.", 0,
        )
        self.portion_gelee = self._ancrer(self.bloc_gele, "adopte par le collectif")

        # Le bloc ANCRE, cite par un WIKI : le wiki ne gele rien.
        # / The ANCHORED block, cited by a WIKI: a wiki freezes nothing.
        self.bloc_ancre = self._element(
            "Le passage vivant, celui qu'un wiki cite.", 1,
        )
        self.portion_vivante = self._ancrer(self.bloc_ancre, "Le passage vivant")

        # Le bloc LIBRE : une portion, aucune citation.
        # / The FREE block: a portion, no citation.
        self.bloc_libre = self._element(
            "Le passage libre, que personne ne cite.", 2,
        )
        self.portion_libre = self._ancrer(self.bloc_libre, "que personne ne cite")

        # Le bloc NU : ni portion, ni citation — le temoin.
        # / The BARE block: no portion, no citation — the witness.
        self.bloc_nu = self._element("Le passage nu, sans ancre.", 3)

        # Le bloc DOUBLE : DEUX portions sur un seul bloc. Sans lui, le
        # compteur d'ancres ne prouve pas qu'il compte les PORTIONS : un
        # `+= 1` par bloc touche donnerait les memes nombres partout
        # ailleurs. Or c'est le cas multi-portions que le § 8.2 brandit
        # — « masquer trente en-tetes coute des dizaines de sources ».
        # / TWO portions on one block: otherwise the counter could count
        # blocks instead of portions and no test would notice.
        self.bloc_double = self._element(
            "Le premier fragment, puis le second fragment, ensemble.", 4,
        )
        self.portion_a = self._ancrer(self.bloc_double, "Le premier fragment")
        self.portion_b = self._ancrer(self.bloc_double, "le second fragment")

        self.client.force_login(self.proprietaire)

    # ------------------------------------------------------------------
    # Les briques de la fixture / The fixture's building blocks
    # ------------------------------------------------------------------

    def _element(self, texte, ordre, masque=False):
        """Un bloc de la note. / One block of the note."""
        return ElementDocument.objects.create(
            page=self.page, ordre=ordre, label="text", texte=texte,
            empreinte_contenu=empreinte_du_texte(texte), masque=masque,
        )

    def _ancrer(self, element, passage):
        """
        Pose une extraction et sa portion sur un passage EXACT du bloc.
        / Anchors an extraction portion on an EXACT passage of the block.

        Les offsets sont calcules depuis le texte reel : une portion posee
        sur des offsets a la main mentirait des que le texte de la fixture
        changerait d'une lettre.
        / Offsets come from the real text, never hand-written.
        """
        debut = element.texte.index(passage)
        extraction = ExtractedEntity.objects.create(
            job=self.job, extraction_class="argument",
            extraction_text=passage,
            start_char=debut, end_char=debut + len(passage),
        )
        return AncrageExtraction.objects.create(
            extraction=extraction, element=element,
            ordre_dans_extraction=0,
            debut_dans_element=debut,
            fin_dans_element=debut + len(passage),
        )

    def _faire_citer(self, portion, type_de_note, titre):
        """
        Fait citer la portion par un article, PAR LE VRAI SERVICE.
        / Makes an article cite the portion, THROUGH THE REAL SERVICE.

        `indexer_les_citations` est le seul chemin de production : il pose
        `ancrage_source` sur la premiere portion de l'extraction, et c'est
        ce champ que le detachement relit. Fabriquer le SourceLink a la
        main testerait un lien que la production ne cree jamais.
        / The real service is the only path that sets `ancrage_source`.
        """
        article = Page.objects.create(
            url=f"http://exemple.local/citant-{titre}",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash=f"hash-{titre}",
            owner=self.proprietaire, type_de_note=type_de_note, title=titre,
        )
        if type_de_note == TypeDeNote.SYNTHESE:
            SyntheseDirigee.objects.create(
                page=article, dossier=self.dossier,
                produite_par=self.proprietaire,
            )
        else:
            Wiki.objects.create(page=article, dossier=self.dossier, sujet=titre)
        indexer_les_citations(
            article,
            f"Une affirmation.[[ext:{portion.extraction.pk}]]\n",
            None,
        )
        return article

    # ------------------------------------------------------------------
    # Les gestes / The gestures
    # ------------------------------------------------------------------

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

    def _compte_rendu(self, reponse):
        """
        Relit les cinq nombres DANS LE HTML RENDU, jamais dans un JSON.
        / Reads the five numbers from the RENDERED HTML, never from JSON.

        L'endpoint rend un partial HTMX — c'est ce que la personne voit,
        donc c'est ce qu'il faut eprouver. Un test qui lirait un JSON
        epinglerait un contrat que la vue n'a jamais offert, et resterait
        vert le jour ou le partial cesserait d'afficher un nombre.
        """
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        nombres = {}
        for nom in ("blocs-modifies", "blocs-masques", "ancres-detachees",
                    "citations-detachees", "blocs-refuses"):
            trouve = re.search(
                'data-testid="' + nom + r'">\s*<strong>(\d+)</strong>', corps,
            )
            self.assertIsNotNone(
                trouve, f"le compte rendu doit porter {nom}",
            )
            nombres[nom.replace("-", "_")] = int(trouve.group(1))
        nombres["corps"] = corps
        nombres["refus"] = re.findall(r'data-testid="refus-([^"]+)"', corps)
        return nombres


class UnBlocGeleParUneSyntheseDansUnLot(BaseDuLotAvecAncrages):
    """
    § 8.2 : un passage cite par une synthese FIGEE est refuse, LUI SEUL.
    / A passage cited by a FROZEN synthesis is refused, IT ALONE.
    """

    def setUp(self):
        super().setUp()
        self.synthese = self._faire_citer(
            self.portion_gelee, TypeDeNote.SYNTHESE, "Synthese du 12 mars",
        )

    def test_le_bloc_gele_est_refuse_LUI_SEUL(self):
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_gele, "Le passage refait par un editeur."),
            self._bloc(self.bloc_libre, "Le passage libre, corrige."),
        ]))
        self.assertEqual(compte_rendu["blocs_refuses"], 1)
        self.assertEqual(compte_rendu["blocs_modifies"], 1)

    def test_le_texte_du_bloc_gele_N_EST_PAS_touche(self):
        # LE STATUT SE VERIFIE, MEME SUR UN TEST NEGATIF. Sans lui, un
        # 500 sur ce chemin laisserait le test vert : la transaction
        # annulee rend le meme texte intact qu'un refus propre.
        # / A 500 would leave a purely negative test green.
        reponse = self._poster([
            self._bloc(self.bloc_gele, "Le passage refait par un editeur."),
        ])
        self.assertEqual(reponse.status_code, 200)
        self.bloc_gele.refresh_from_db()
        self.assertEqual(
            self.bloc_gele.texte, "Le passage adopte par le collectif en mars.",
        )

    def test_LES_AUTRES_blocs_du_lot_sont_bien_ECRITS_EN_BASE(self):
        """
        Le coeur du chemin : le `try/except` de ce refus vit DANS le
        `transaction.atomic()` du lot, et il doit y rester.

        Deplace au-dehors — comme l'est celui de
        `EditionBloqueePendantAnalyse`, qui refuse le lot ENTIER —, il
        annulerait tout au commit pendant que le compte rendu, lui,
        annoncerait « 1 modifie ». La personne verrait un succes et
        n'aurait rien. C'est ce test qui interdit ce deplacement.

        (La garde leve AVANT tout SQL : la transaction n'est jamais en
        etat d'echec PostgreSQL. Le risque n'est pas la, il est dans la
        PORTEE du refus.)
        / The try/except must stay INSIDE the atomic block: moved out, it
        would roll everything back while reporting a success.
        """
        self._poster([
            self._bloc(self.bloc_gele, "Le passage refait par un editeur."),
            self._bloc(self.bloc_libre, "Le passage libre, corrige."),
            self._bloc(self.bloc_nu, "Le passage nu, corrige."),
        ])
        self.bloc_libre.refresh_from_db()
        self.bloc_nu.refresh_from_db()
        self.assertEqual(self.bloc_libre.texte, "Le passage libre, corrige.")
        self.assertEqual(self.bloc_nu.texte, "Le passage nu, corrige.")

    def test_le_refus_porte_l_identifiant_du_bloc_gele_et_son_motif(self):
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_gele, "Le passage refait par un editeur."),
        ]))
        self.assertEqual(
            compte_rendu["refus"], [str(self.bloc_gele.identifiant_stable)],
        )
        self.assertIn("synthèse", compte_rendu["corps"])

    def test_le_refus_NOMME_la_synthese_qui_bloque(self):
        """
        § 5.3 de SPEC-synthese : le refus NOMME ce qui bloque.

        Sur une note ou 7 blocs sur 12 sont geles, « cite par une
        synthese figee » ne dit pas laquelle : on ne sait pas quelle
        citation retirer, ni quelle synthese reproduire. Le geste
        unitaire nomme deja (`_message_falc_du_blocage_par_synthese`) ;
        le lot doit en faire autant.
        / The refusal must name the blocking synthesis, as the single
        gesture already does.
        """
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_gele, "Le passage refait par un editeur."),
        ]))
        self.assertIn("Synthese du 12 mars", compte_rendu["corps"])

    def test_le_titre_de_la_synthese_est_ECHAPPE(self):
        """
        Le titre vient d'une note, donc d'un humain. Rendu tel quel, il
        ferait entrer du balisage dans le compte rendu — et le mode le
        reprend dans une modale.
        / The title is human input: it must arrive escaped.
        """
        self.synthese.title = "<img src=x onerror=alert(1)>"
        self.synthese.save(update_fields=["title"])
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_gele, "Le passage refait par un editeur."),
        ]))
        self.assertNotIn("<img src=x", compte_rendu["corps"])
        self.assertIn("&lt;img src=x", compte_rendu["corps"])

    def test_VIDER_un_bloc_gele_est_AUSSI_refuse(self):
        """
        Le masquage passe par un autre service que la correction, et il
        pose la meme garde : vider un passage cite le ferait disparaitre
        de la synthese adoptee.
        / Hiding goes through another service, with the same guard.
        """
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_gele, "   "),
        ]))
        self.assertEqual(compte_rendu["blocs_refuses"], 1)
        self.assertEqual(compte_rendu["blocs_masques"], 0)
        self.bloc_gele.refresh_from_db()
        self.assertFalse(self.bloc_gele.masque)

    def test_la_portion_gelee_reste_ANCREE(self):
        """Un refus ne detache rien. / A refusal detaches nothing."""
        # Le statut, ici encore : un 500 rendrait la portion intacte.
        # / The status, again: a 500 would leave the portion intact too.
        reponse = self._poster([
            self._bloc(self.bloc_gele, "Le passage refait par un editeur."),
        ])
        self.assertEqual(reponse.status_code, 200)
        self.portion_gelee.refresh_from_db()
        self.assertEqual(self.portion_gelee.etat_ancrage, EtatAncrage.ANCREE)

    def test_le_journal_porte_les_blocs_PASSES_et_la_liste_des_refus(self):
        self._poster([
            self._bloc(self.bloc_gele, "Le passage refait par un editeur."),
            self._bloc(self.bloc_libre, "Le passage libre, corrige."),
        ])
        journal = PageEdit.objects.get(page=self.page)
        identifiant_gele = str(self.bloc_gele.identifiant_stable)
        identifiant_libre = str(self.bloc_libre.identifiant_stable)
        # Le bloc refuse n'a PAS d'avant/apres : il n'a pas bouge.
        # / The refused block has no before/after: it did not move.
        self.assertNotIn(identifiant_gele, journal.donnees_avant["blocs"])
        self.assertIn(identifiant_libre, journal.donnees_avant["blocs"])
        # Mais le refus, lui, est trace : c'est ce qui dit quoi retaper.
        # / But the refusal IS recorded: it says what to retype.
        identifiants_refuses = [
            refus["identifiant_stable"] for refus in journal.donnees_apres["refus"]
        ]
        self.assertEqual(identifiants_refuses, [identifiant_gele])

    def test_un_lot_ENTIEREMENT_gele_n_ecrit_AUCUN_journal(self):
        """
        Rien n'a change : un PageEdit vide serait un geste invente.
        / Nothing changed: an empty journal entry would be a made-up act.
        """
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_gele, "Le passage refait par un editeur."),
        ]))
        self.assertEqual(compte_rendu["blocs_modifies"], 0)
        self.assertEqual(compte_rendu["blocs_refuses"], 1)
        self.assertEqual(PageEdit.objects.filter(page=self.page).count(), 0)

    def test_le_SECOND_element_d_une_extraction_citee_est_GELE_AUSSI(self):
        """
        § 8.2 : citer une extraction gele TOUS les elements qu'elle
        traverse, pas seulement celui qui porte le passage cite.

        C'est inevitable — une preuve coupee en deux n'est plus une
        preuve — et c'est ce qui explique le chiffre du § 8.2 : 114
        elements geles sur 386. Le service le garantit ; ce test
        verifie que le LOT le repercute, avec son motif.
        / Citing one extraction freezes every element it spans.
        """
        # La meme extraction porte une SECONDE portion, sur un bloc que
        # rien ne cite directement.
        # / The same extraction gets a second portion, on another block.
        AncrageExtraction.objects.create(
            extraction=self.portion_gelee.extraction,
            element=self.bloc_libre,
            ordre_dans_extraction=1,
            debut_dans_element=0,
            fin_dans_element=11,
        )
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_libre, "Ce bloc n'est pas cite, lui."),
        ]))
        self.assertEqual(compte_rendu["blocs_refuses"], 1)
        self.assertEqual(compte_rendu["blocs_modifies"], 0)
        self.assertIn("Synthese du 12 mars", compte_rendu["corps"])
        self.bloc_libre.refresh_from_db()
        self.assertEqual(
            self.bloc_libre.texte, "Le passage libre, que personne ne cite.",
        )

    def test_un_WIKI_qui_cite_ne_gele_RIEN(self):
        """
        Le pendant du refus : sans lui, un carnet a cinq wikis gelerait
        la moitie de ses passages des la premiere semaine.
        / Without this, a five-wiki notebook would freeze half its blocks.
        """
        self._faire_citer(
            self.portion_vivante, TypeDeNote.WIKI, "Wiki du sujet",
        )
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_ancre, "Le passage vivant, corrige."),
        ]))
        self.assertEqual(compte_rendu["blocs_refuses"], 0)
        self.assertEqual(compte_rendu["blocs_modifies"], 1)


class LesDeuxComptesDuCompteRendu(BaseDuLotAvecAncrages):
    """
    § 7.4 : `ancres_detachees` et `citations_detachees` sont DEUX nombres.
    / § 7.4: detached anchors and detached citations are TWO numbers.
    """

    def test_une_correction_qui_efface_le_passage_DETACHE_sa_portion(self):
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_libre, "Un texte entierement different."),
        ]))
        self.assertEqual(compte_rendu["ancres_detachees"], 1)
        self.portion_libre.refresh_from_db()
        self.assertEqual(self.portion_libre.etat_ancrage, EtatAncrage.DETACHEE)

    def test_une_correction_AILLEURS_dans_le_bloc_ne_detache_RIEN(self):
        """
        Le passage ancre survit mot pour mot : la portion le retrouve.
        / The anchored passage survives verbatim: the portion finds it.
        """
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_libre, "Voici que personne ne cite, enfin."),
        ]))
        self.assertEqual(compte_rendu["blocs_modifies"], 1)
        self.assertEqual(compte_rendu["ancres_detachees"], 0)
        self.portion_libre.refresh_from_db()
        self.assertEqual(self.portion_libre.etat_ancrage, EtatAncrage.ANCREE)

    def test_la_citation_QUI_POINTAIT_la_portion_est_comptee_A_PART(self):
        """
        Une ancre detachee detache la citation qui la pointait
        (SPEC-synthese § 4.2). Le § 7.4 veut ce nombre SEPAREMENT :
        masquer trente en-tetes peut couter des dizaines de sources
        d'articles, et ce doit etre dit.
        / A detached anchor detaches its citation; § 7.4 wants that
        number apart.
        """
        self._faire_citer(
            self.portion_vivante, TypeDeNote.WIKI, "Wiki du sujet",
        )
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_ancre, "Un texte entierement different."),
        ]))
        self.assertEqual(compte_rendu["ancres_detachees"], 1)
        self.assertEqual(compte_rendu["citations_detachees"], 1)
        lien = SourceLink.objects.get(
            ancrage_source=self.portion_vivante, type_lien=TypeLien.CITE,
        )
        self.assertEqual(lien.etat_de_la_source, EtatDeLaSource.DETACHEE)

    def test_VIDER_un_bloc_detache_ses_portions_ET_ses_citations(self):
        """
        Le masquage detache tout ce que le bloc portait — c'est le geste
        qui coute le plus cher, et le compte rendu doit le dire.
        / Hiding detaches everything the block carried.
        """
        self._faire_citer(
            self.portion_vivante, TypeDeNote.WIKI, "Wiki du sujet",
        )
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_ancre, ""),
        ]))
        self.assertEqual(compte_rendu["blocs_masques"], 1)
        self.assertEqual(compte_rendu["ancres_detachees"], 1)
        self.assertEqual(compte_rendu["citations_detachees"], 1)

    def test_les_deux_comptes_S_ADDITIONNENT_sur_tout_le_lot(self):
        """
        Un seul compte rendu pour le lot entier, pas un par bloc.
        / One report for the whole batch, not one per block.
        """
        self._faire_citer(
            self.portion_vivante, TypeDeNote.WIKI, "Wiki du sujet",
        )
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_ancre, "Un texte entierement different."),
            self._bloc(self.bloc_libre, "Un autre texte, tout aussi neuf."),
            self._bloc(self.bloc_nu, "Le passage nu, corrige."),
        ]))
        self.assertEqual(compte_rendu["blocs_modifies"], 3)
        self.assertEqual(compte_rendu["ancres_detachees"], 2)
        self.assertEqual(compte_rendu["citations_detachees"], 1)

    def test_UN_bloc_a_DEUX_portions_compte_DEUX_ancres(self):
        """
        Un seul bloc, deux portions effacees : le compte vaut DEUX.
        Un compteur qui compterait les blocs touches dirait « 1 ».
        / One block, two portions: the count is TWO, not one.
        """
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_double, "Un texte entierement different."),
        ]))
        self.assertEqual(compte_rendu["blocs_modifies"], 1)
        self.assertEqual(compte_rendu["ancres_detachees"], 2)

    def test_VIDER_un_bloc_a_DEUX_portions_compte_DEUX_ancres(self):
        """
        Le masquage rend un NOMBRE de portions detachees, et la vue doit
        l'additionner, pas le reduire a « ce bloc a coute quelque chose ».
        / Hiding returns a COUNT: the view must add it, not flatten it.
        """
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_double, ""),
        ]))
        self.assertEqual(compte_rendu["blocs_masques"], 1)
        self.assertEqual(compte_rendu["ancres_detachees"], 2)

    def test_DEUX_citations_sur_la_MEME_portion_comptent_DEUX(self):
        """
        Deux articles peuvent citer la meme portion. Le § 7.4 compte les
        CITATIONS, pas les portions qui en portaient : une seule ancre
        detachee peut en couter deux.
        / Two articles can cite one portion: the count follows the
        citations, not the anchors.
        """
        self._faire_citer(self.portion_vivante, TypeDeNote.WIKI, "Premier wiki")
        self._faire_citer(self.portion_vivante, TypeDeNote.WIKI, "Second wiki")
        compte_rendu = self._compte_rendu(self._poster([
            self._bloc(self.bloc_ancre, "Un texte entierement different."),
        ]))
        self.assertEqual(compte_rendu["ancres_detachees"], 1)
        self.assertEqual(compte_rendu["citations_detachees"], 2)

    def test_une_citation_DEJA_detachee_n_est_PAS_recomptee(self):
        """
        Le compte se fait par DIFFERENCE (avant/apres), et c'est vital :
        sans la soustraction, chaque enregistrement re-annoncerait
        toutes les citations detachees des sessions precedentes. On
        finirait par lire « 40 citations detachees » pour un lot qui n'en
        a detache aucune.
        / The count is a difference: without it, every save would
        re-announce every citation detached in past sessions.
        """
        self._faire_citer(self.portion_vivante, TypeDeNote.WIKI, "Wiki du sujet")
        premier = self._compte_rendu(self._poster([
            self._bloc(self.bloc_ancre, "Un texte entierement different."),
        ]))
        self.assertEqual(premier["citations_detachees"], 1)

        # Un second lot, sur un AUTRE bloc, qui ne detache aucune
        # citation : le compte doit valoir zero, pas un.
        # / A second batch on another block detaches nothing: zero.
        second = self._compte_rendu(self._poster([
            self._bloc(self.bloc_libre, "Un autre texte, tout aussi neuf."),
        ]))
        self.assertEqual(second["ancres_detachees"], 1)
        self.assertEqual(second["citations_detachees"], 0)

    def test_le_journal_porte_les_deux_comptes(self):
        """
        § 10 : les ancres et les citations detachees ne se relisent nulle
        part ailleurs — ce sont elles qui disent ce que le geste a coute.
        / § 10: these two numbers exist nowhere else.
        """
        self._faire_citer(
            self.portion_vivante, TypeDeNote.WIKI, "Wiki du sujet",
        )
        self._poster([
            self._bloc(self.bloc_ancre, "Un texte entierement different."),
        ])
        journal = PageEdit.objects.get(page=self.page)
        compte_rendu_journalise = journal.donnees_apres["compte_rendu"]
        self.assertEqual(compte_rendu_journalise["ancres_detachees"], 1)
        self.assertEqual(compte_rendu_journalise["citations_detachees"], 1)
