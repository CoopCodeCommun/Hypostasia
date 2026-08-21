"""
La commande qui fait noter tout le carnet par les juges locaux.
/ The command that has the local judges score the whole notebook.

LOCALISATION : front/tests/test_notation_par_les_juges_locaux.py

POURQUOI CETTE COMMANDE EXISTE. Les avis des juges locaux ne partaient
que d'un BOUTON, article par article. Une installation neuve n'en avait
donc AUCUN : la fiche de preuve affichait « aucun avis » sur tout le
corpus etalon, et rien ne disait que c'etait normal.

Elle est GRATUITE et HORS RESEAU — les quatre encodeurs tournent sur
processeur — ce qui la distingue de `verifier_les_citations_etalons`,
qui appelle un modele facture.
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models import (
    Dossier, Page, SourceLink, TypeDeNote, TypeLien, Wiki,
)


class LaCommandeDeNotationParLesJugesLocaux(TestCase):
    """Elle met en file, elle ne note pas elle-meme. / It queues."""

    def setUp(self):
        self.utilisateur = get_user_model().objects.create_user(
            username="mainteneur", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Documents étalons", owner=self.utilisateur,
        )

    def _un_article_cite(self):
        """Un wiki du carnet, portant une citation. / A cited wiki."""
        page = Page.objects.create(
            title="Wiki — sujet", owner=self.utilisateur,
            type_de_note=TypeDeNote.WIKI, text_readability="Un texte.",
        )
        page.appartenances_dossiers.create(dossier=self.carnet)
        Wiki.objects.create(page=page, dossier=self.carnet, sujet="sujet")
        SourceLink.objects.create(
            page_cible=page, type_lien=TypeLien.CITE,
            start_char_cible=0, end_char_cible=9,
        )
        return page

    def test_elle_met_un_job_en_file_par_article_cite(self):
        """Un article sans citation n'a rien a faire noter."""
        self._un_article_cite()

        with patch("front.tasks.noter_avec_le_juge_local_task.delay") as tache:
            call_command("noter_avec_les_juges_locaux", stdout=StringIO())

        self.assertEqual(tache.call_count, 1)

    def test_un_article_sans_citation_est_saute(self):
        """
        Mettre un job en file pour un article vide ferait charger 5,13 Go
        de modeles pour ne rien noter.
        / Queueing an empty article would load 5.13 GB for nothing.
        """
        page = Page.objects.create(
            title="Wiki — vide", owner=self.utilisateur,
            type_de_note=TypeDeNote.WIKI, text_readability="",
        )
        page.appartenances_dossiers.create(dossier=self.carnet)
        Wiki.objects.create(page=page, dossier=self.carnet, sujet="vide")

        with patch("front.tasks.noter_avec_le_juge_local_task.delay") as tache:
            call_command("noter_avec_les_juges_locaux", stdout=StringIO())

        self.assertEqual(tache.call_count, 0)

    def test_elle_est_idempotente_par_defaut(self):
        """
        DEUX EXECUTIONS NE DOIVENT PAS DOUBLER LE TRAVAIL. La commande
        tourne a chaque demarrage de conteneur : sans cette garde, un
        redemarrage remettrait tout le corpus en file, et le worker —
        a concurrence 1 — le rejouerait entierement.
        / It runs at every container start; without this guard a restart
        would re-queue the whole corpus.
        """
        page = self._un_article_cite()
        from core.models import AvisDeVerification
        from core.services.juges_locaux import JUGES, methode

        lien = SourceLink.objects.get(page_cible=page)
        for nom_du_juge in JUGES:
            AvisDeVerification.objects.create(
                lien=lien, methode=methode(nom_du_juge),
                score=80.0, seuil=50.0,
            )

        with patch("front.tasks.noter_avec_le_juge_local_task.delay") as tache:
            call_command("noter_avec_les_juges_locaux", stdout=StringIO())

        self.assertEqual(tache.call_count, 0)

    def test_forcer_remet_en_file_ce_qui_est_deja_note(self):
        """`--forcer` est le seul flag, et il fait l'inverse."""
        page = self._un_article_cite()
        from core.models import AvisDeVerification
        from core.services.juges_locaux import JUGES, methode

        lien = SourceLink.objects.get(page_cible=page)
        for nom_du_juge in JUGES:
            AvisDeVerification.objects.create(
                lien=lien, methode=methode(nom_du_juge),
                score=80.0, seuil=50.0,
            )

        with patch("front.tasks.noter_avec_le_juge_local_task.delay") as tache:
            call_command("noter_avec_les_juges_locaux", forcer=True,
                         stdout=StringIO())

        self.assertEqual(tache.call_count, 1)
