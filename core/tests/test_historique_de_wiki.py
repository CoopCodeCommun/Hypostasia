"""
Tests de l'historique des tours de wiki.
/ Wiki update-round history tests.

LOCALISATION : core/tests/test_historique_de_wiki.py

SPEC-synthese, addendum du 21 aout 2026 : un tour de mise a jour
produisait toute la matiere de sa tracabilite, puis la jetait. Il ne
restait qu'un compteur et une date ecrasee. Ces tests EXERCENT la regle
neuve : chaque tour s'ecrit, avec sa raison MESUREE, son ajout, son
avant, et ses rejets — un rejet est un fait d'histoire, pas un
non-evenement.
/ Every round is written down: measured reason, addition, before, and
rejections.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Dossier, MotifDeTourDeWiki, OperationDeWiki, Page, TourDeWiki,
    TypeDeNote, Wiki,
)
from core.services.historique_de_wiki import enregistrer_un_tour
from core.services.section_ops import appliquer_les_operations
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()


def creer_une_page(url_unique, **champs):
    """Cree une page minimale. / Minimal page."""
    return Page.objects.create(
        url=url_unique,
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="texte",
        content_hash=f"hash-{url_unique}",
        title=f"Note {url_unique[-10:]}",
        **champs,
    )


def creer_une_extraction(page, texte="le seuil de dix mille euros"):
    """Cree une extraction sur une page. / An extraction on a page."""
    job = ExtractionJob.objects.create(
        page=page, name="Job test historique", status="completed",
        ai_model=None,
    )
    return ExtractedEntity.objects.create(
        job=job, extraction_class="argument", extraction_text=texte,
        start_char=0, end_char=len(texte),
    )


class HistoriqueDUnTourTest(TestCase):
    """
    enregistrer_un_tour : le tour et ses operations.
    / enregistrer_un_tour: the round and its operations.
    """

    def setUp(self):
        self.redacteur = Utilisateur.objects.create_user(
            username="redactrice_historique", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet historique", owner=self.redacteur,
        )
        self.note_source = creer_une_page("http://exemple.local/hw-source")
        self.extraction = creer_une_extraction(self.note_source)
        self.article = creer_une_page(
            "http://exemple.local/hw-article",
            type_de_note=TypeDeNote.WIKI, owner=self.redacteur,
        )
        self.wiki = Wiki.objects.create(
            page=self.article, dossier=self.carnet, sujet="Le seuil",
        )

    def _bilan_d_un_lot(self, texte_de_depart, operations):
        """Le bilan REEL de l'applieur. / The applier's real report."""
        return appliquer_les_operations(
            texte_de_depart, operations, {self.extraction.pk},
        )

    def test_un_tour_porte_sa_date_son_auteur_et_son_motif(self):
        bilan = self._bilan_d_un_lot("## Le seuil\n\nUn premier état.\n", [])

        tour = enregistrer_un_tour(
            wiki=self.wiki,
            motif=MotifDeTourDeWiki.MAJ_MANUELLE,
            fait_par=self.redacteur,
            bilan=bilan,
            texte_avant="## Le seuil\n\nUn premier état.\n",
        )

        self.assertEqual(tour.wiki, self.wiki)
        self.assertEqual(tour.motif, MotifDeTourDeWiki.MAJ_MANUELLE)
        self.assertEqual(tour.fait_par, self.redacteur)
        self.assertEqual(tour.numero_de_tour, self.wiki.tours_de_mise_a_jour)
        self.assertIsNotNone(tour.fait_le)

    def test_un_tour_de_la_nuit_n_a_pas_d_auteur(self):
        # fait_par NULL est le seul signe qu'un humain n'a rien decide.
        # / NULL author is the only sign no human decided.
        bilan = self._bilan_d_un_lot("## Le seuil\n\nUn état.\n", [])

        tour = enregistrer_un_tour(
            wiki=self.wiki,
            motif=MotifDeTourDeWiki.MAJ_NOCTURNE,
            fait_par=None,
            bilan=bilan,
            texte_avant="## Le seuil\n\nUn état.\n",
        )

        self.assertIsNone(tour.fait_par)
        self.assertTrue(tour.est_fait_par_le_moteur)

    def test_l_ajout_est_conserve_avec_sa_section(self):
        texte_de_depart = "## Le seuil\n\nUn premier état.\n"
        contenu_ajoute = f"Un fait de plus [[ext:{self.extraction.pk}]]."
        bilan = self._bilan_d_un_lot(texte_de_depart, [
            {
                "type": "append_to_section",
                "section": "Le seuil",
                "contenu": contenu_ajoute,
            },
        ])

        tour = enregistrer_un_tour(
            wiki=self.wiki,
            motif=MotifDeTourDeWiki.MAJ_MANUELLE,
            fait_par=self.redacteur,
            bilan=bilan,
            texte_avant=texte_de_depart,
        )

        operation = tour.operations.get()
        self.assertTrue(operation.appliquee)
        self.assertEqual(operation.type_d_operation, "append_to_section")
        self.assertEqual(operation.section, "Le seuil")
        self.assertEqual(operation.contenu, contenu_ajoute)
        self.assertEqual(operation.motif_de_rejet, "")

    def test_un_remplacement_conserve_l_ancien_contenu(self):
        # § 6.4 : le diff montre l'avant. Sans lui, l'historique
        # approuverait une reecriture sans montrer ce qui disparait.
        # / § 6.4: without the before, the history hides what vanished.
        texte_de_depart = "## Le seuil\n\nCe que l'article disait avant.\n"
        bilan = self._bilan_d_un_lot(texte_de_depart, [
            {
                "type": "replace_section",
                "section": "Le seuil",
                "contenu": f"Ce qu'il dit maintenant [[ext:{self.extraction.pk}]].",
            },
        ])

        tour = enregistrer_un_tour(
            wiki=self.wiki,
            motif=MotifDeTourDeWiki.MAJ_MANUELLE,
            fait_par=self.redacteur,
            bilan=bilan,
            texte_avant=texte_de_depart,
        )

        operation = tour.operations.get()
        self.assertTrue(operation.appliquee)
        self.assertEqual(
            operation.ancien_contenu, "Ce que l'article disait avant.",
        )

    def test_un_rejet_est_ecrit_avec_son_motif(self):
        # Une section fantome est une hallucination du modele : elle
        # doit rester lisible dans l'historique.
        # / A ghost section is a hallucination; it stays readable.
        texte_de_depart = "## Le seuil\n\nUn état.\n"
        bilan = self._bilan_d_un_lot(texte_de_depart, [
            {
                "type": "append_to_section",
                "section": "Une section qui n'existe pas",
                "contenu": f"Du contenu [[ext:{self.extraction.pk}]].",
            },
        ])

        tour = enregistrer_un_tour(
            wiki=self.wiki,
            motif=MotifDeTourDeWiki.MAJ_MANUELLE,
            fait_par=self.redacteur,
            bilan=bilan,
            texte_avant=texte_de_depart,
        )

        operation = tour.operations.get()
        self.assertFalse(operation.appliquee)
        self.assertNotEqual(operation.motif_de_rejet, "")
        # Le contenu du rejet est CONSERVE (§ 6.2) : jeter serait une
        # perte de donnees. / Rejected content is kept (§ 6.2).
        self.assertIn("Du contenu", operation.contenu)

    def test_les_extractions_citees_viennent_des_marqueurs(self):
        # Le markdown est la verite (§ 4.4) : jamais un champ parallele.
        # / Markdown is the truth: never a parallel field.
        autre_extraction = creer_une_extraction(
            self.note_source, "un autre passage",
        )
        texte_de_depart = "## Le seuil\n\nUn état.\n"
        bilan = self._bilan_d_un_lot(texte_de_depart, [
            {
                "type": "append_to_section",
                "section": "Le seuil",
                "contenu": (
                    f"Deux preuves [[ext:{self.extraction.pk}]] "
                    f"[[ext:{autre_extraction.pk}]]."
                ),
            },
        ])

        tour = enregistrer_un_tour(
            wiki=self.wiki,
            motif=MotifDeTourDeWiki.MAJ_MANUELLE,
            fait_par=self.redacteur,
            bilan=bilan,
            texte_avant=texte_de_depart,
            identifiants_du_perimetre={
                self.extraction.pk, autre_extraction.pk,
            },
        )

        operation = tour.operations.get()
        self.assertEqual(
            set(operation.extractions_citees.values_list("pk", flat=True)),
            {self.extraction.pk, autre_extraction.pk},
        )

    def test_le_texte_avant_et_le_texte_apres_sont_conserves(self):
        # Les DEUX : une edition manuelle entre deux tours briserait un
        # chainage, et personne ne le verrait.
        # / Both: a manual edit between rounds would break a chain.
        texte_de_depart = "## Le seuil\n\nUn premier état.\n"
        bilan = self._bilan_d_un_lot(texte_de_depart, [
            {
                "type": "append_to_section",
                "section": "Le seuil",
                "contenu": f"Un fait de plus [[ext:{self.extraction.pk}]].",
            },
        ])

        tour = enregistrer_un_tour(
            wiki=self.wiki,
            motif=MotifDeTourDeWiki.MAJ_MANUELLE,
            fait_par=self.redacteur,
            bilan=bilan,
            texte_avant=texte_de_depart,
        )

        self.assertEqual(tour.texte_avant, texte_de_depart)
        self.assertEqual(tour.texte_apres, bilan["texte_final"])
        self.assertNotEqual(tour.texte_avant, tour.texte_apres)


class RaisonMesureeDuTourTest(TestCase):
    """
    La raison est COMPTEE, puis FIGEE : elle n'est plus recalculable
    une fois le tour suivant passe.
    / The reason is measured then frozen: later rounds make it
    unreproducible.
    """

    def setUp(self):
        self.redacteur = Utilisateur.objects.create_user(
            username="redacteur_raison", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet raison", owner=self.redacteur,
        )
        self.article = creer_une_page(
            "http://exemple.local/hw-raison",
            type_de_note=TypeDeNote.WIKI, owner=self.redacteur,
        )
        self.wiki = Wiki.objects.create(
            page=self.article, dossier=self.carnet, sujet="La raison",
        )

    def test_les_comptes_de_nouveautes_sont_figes_sur_le_tour(self):
        from core.services.corpus import ranger_une_note_dans_un_carnet

        borne_basse = timezone.now()
        note_neuve = creer_une_page("http://exemple.local/hw-neuve")
        ranger_une_note_dans_un_carnet(
            note_neuve, self.carnet, self.redacteur,
        )
        creer_une_extraction(note_neuve, "un fait tout neuf")

        bilan = appliquer_les_operations("## Vide\n\nRien.\n", [], set())
        tour = enregistrer_un_tour(
            wiki=self.wiki,
            motif=MotifDeTourDeWiki.MAJ_NOCTURNE,
            fait_par=None,
            bilan=bilan,
            texte_avant="## Vide\n\nRien.\n",
            depuis=borne_basse,
        )

        self.assertEqual(tour.depuis, borne_basse)
        self.assertEqual(tour.extractions_nouvelles, 1)
        self.assertEqual(tour.commentaires_nouveaux, 0)
        self.assertIn(
            note_neuve.pk,
            tour.notes_declenchantes.values_list("pk", flat=True),
        )

    def test_sans_borne_basse_aucune_nouveaute_n_est_inventee(self):
        # nouveautes_du_perimetre rend 0 quand `depuis` est None :
        # inventer un compte serait pire que n'en donner aucun.
        # / No reference date, no invented count.
        bilan = appliquer_les_operations("## Vide\n\nRien.\n", [], set())

        tour = enregistrer_un_tour(
            wiki=self.wiki,
            motif=MotifDeTourDeWiki.CREATION,
            fait_par=self.redacteur,
            bilan=bilan,
            texte_avant="",
            depuis=None,
        )

        self.assertIsNone(tour.depuis)
        self.assertEqual(tour.extractions_nouvelles, 0)
        self.assertEqual(tour.commentaires_nouveaux, 0)


class LiaisonAuJobTest(TestCase):
    """Le tour garde le job qui a produit la proposition.
    / The round keeps the job that produced the proposal."""

    def test_le_tour_pointe_la_proposition_d_origine(self):
        redacteur = Utilisateur.objects.create_user(
            username="redacteur_job", password="motdepasse",
        )
        carnet = Dossier.objects.create(name="Carnet job", owner=redacteur)
        article = creer_une_page(
            "http://exemple.local/hw-job",
            type_de_note=TypeDeNote.WIKI, owner=redacteur,
        )
        wiki = Wiki.objects.create(
            page=article, dossier=carnet, sujet="Le job",
        )
        job = ExtractionJob.objects.create(
            page=article, name="Proposition test", status="completed",
            ai_model=None,
        )

        bilan = appliquer_les_operations("## S\n\nRien.\n", [], set())
        tour = enregistrer_un_tour(
            wiki=wiki,
            motif=MotifDeTourDeWiki.MAJ_MANUELLE,
            fait_par=redacteur,
            bilan=bilan,
            texte_avant="## S\n\nRien.\n",
            job=job,
        )

        self.assertEqual(tour.job, job)
        # Le job disparait un jour ; le tour, non.
        # / Jobs get deleted; the round survives.
        job.delete()
        tour.refresh_from_db()
        self.assertIsNone(tour.job)
        self.assertTrue(TourDeWiki.objects.filter(pk=tour.pk).exists())


class OrdreDeLectureTest(TestCase):
    """Le plus recent d'abord. / Most recent first."""

    def test_les_tours_se_lisent_du_plus_recent_au_plus_ancien(self):
        redacteur = Utilisateur.objects.create_user(
            username="redacteur_ordre", password="motdepasse",
        )
        carnet = Dossier.objects.create(name="Carnet ordre", owner=redacteur)
        article = creer_une_page(
            "http://exemple.local/hw-ordre",
            type_de_note=TypeDeNote.WIKI, owner=redacteur,
        )
        wiki = Wiki.objects.create(
            page=article, dossier=carnet, sujet="L'ordre",
        )

        for numero in (1, 2, 3):
            TourDeWiki.objects.create(
                wiki=wiki, numero_de_tour=numero,
                motif=MotifDeTourDeWiki.MAJ_MANUELLE,
            )

        numeros_lus = list(
            wiki.tours.values_list("numero_de_tour", flat=True)
        )
        self.assertEqual(numeros_lus, [3, 2, 1])

    def test_les_operations_se_lisent_dans_l_ordre_du_lot(self):
        redacteur = Utilisateur.objects.create_user(
            username="redacteur_lot", password="motdepasse",
        )
        carnet = Dossier.objects.create(name="Carnet lot", owner=redacteur)
        article = creer_une_page(
            "http://exemple.local/hw-lot",
            type_de_note=TypeDeNote.WIKI, owner=redacteur,
        )
        wiki = Wiki.objects.create(page=article, dossier=carnet, sujet="Lot")
        tour = TourDeWiki.objects.create(
            wiki=wiki, numero_de_tour=1,
            motif=MotifDeTourDeWiki.MAJ_MANUELLE,
        )
        for indice in (2, 0, 1):
            OperationDeWiki.objects.create(
                tour=tour, indice=indice,
                type_d_operation="no_change", appliquee=True,
            )

        indices_lus = list(tour.operations.values_list("indice", flat=True))
        self.assertEqual(indices_lus, [0, 1, 2])
