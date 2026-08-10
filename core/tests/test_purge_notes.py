"""
Tests de l'allegement de la base (commande purger_les_notes_inutiles).
/ Tests for the database slimming command.

LOCALISATION : core/tests/test_purge_notes.py

CE QUE CES TESTS PROTEGENT

Decision du proprietaire du 10 aout 2026 : la base de dev porte 546
pages dont beaucoup de doublons d'essai, et on veut la degraisser pour
travailler la stack, l'UX et le back. Mais une suppression de masse se
juge sur ce qu'elle NE detruit PAS.

TROIS CHOSES NE PARTENT JAMAIS

1. Une note commentee — les 983 commentaires humains sont la donnee la
   plus precieuse de la base.
2. Une note CITEE par une synthese conservee, ou PARENT d'une autre.
   Piege verifie le 10 aout : les sources d'une synthese appartiennent
   aux NOTES, pas a l'article. La supprimer viderait la preuve en
   laissant l'article debout.
3. Le dernier exemplaire d'un titre — degraisser n'est pas faire
   disparaitre un sujet de la base.
/ Three things never go: commented notes, cited sources and parents,
and the last copy of a title.

CE QUI N'EST PAS UNE GARDE, CONTRAIREMENT A CE QU'ON POURRAIT CROIRE

Etre un WIKI ou une SYNTHESE ne protege pas. Ce qu'on conserve, c'est le
TYPE de note — de quoi faire vivre les ecrans carnet/wiki/synthese —, pas
ses copies : les plus gros groupes de doublons de la base SONT des
syntheses produites en rafale pendant les essais, jusqu'a 33 du meme
titre. C'est la garde n°3 qui garantit qu'il en reste.
/ Being a wiki or a synthesis is NOT a guard.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models import Page, SourceLink, TypeDeNote
from hypostasis_extractor.models import (
    CommentaireExtraction,
    ExtractedEntity,
    ExtractionJob,
)

Utilisateur = get_user_model()


def creer_une_page(suffixe, titre="Note ordinaire", **champs):
    return Page.objects.create(
        url=f"http://exemple.local/purge-{suffixe}",
        html_original="<p>o</p>", html_readability="<p>l</p>",
        text_readability="Un contenu.",
        content_hash=f"hash-purge-{suffixe}",
        title=titre,
        **champs,
    )


def creer_une_extraction(page):
    job = ExtractionJob.objects.create(
        page=page, name="Job", prompt_description="p",
    )
    return ExtractedEntity.objects.create(
        job=job, extraction_class="idee", extraction_text="une idee",
        start_char=0, end_char=8,
    )


class LaPurgeEpargneCeQuiCompteTest(TestCase):
    """Les quatre gardes. / The four guards."""

    def setUp(self):
        self.auteur = Utilisateur.objects.create_user(
            username="auteur", password="motdepasse",
        )

    def test_une_note_commentee_survit(self):
        page = creer_une_page("commentee", titre="Note commentée")
        extraction = creer_une_extraction(page)
        CommentaireExtraction.objects.create(
            entity=extraction, user=self.auteur, commentaire="Important.",
        )

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertTrue(Page.objects.filter(pk=page.pk).exists())

    def test_un_wiki_survit(self):
        page = creer_une_page(
            "wiki", titre="Wiki vivant", type_de_note=TypeDeNote.WIKI,
        )

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertTrue(Page.objects.filter(pk=page.pk).exists())

    def test_une_synthese_survit(self):
        page = creer_une_page(
            "synthese", titre="Synthèse", type_de_note=TypeDeNote.SYNTHESE,
        )

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertTrue(Page.objects.filter(pk=page.pk).exists())

    def test_trente_syntheses_du_meme_titre_sont_ramenees_a_une(self):
        # Ce qu'on conserve, c'est le TYPE de note, pas ses 33 copies
        # d'essai. Les plus gros groupes de doublons de la base sont
        # justement des syntheses produites en rafale pendant les tests :
        # les proteger une a une ne garderait rien d'utile, ca
        # encombrerait l'ecran de carnet qu'on veut travailler.
        # / We keep the KIND of note, not its 33 trial copies.
        for numero in range(30):
            creer_une_page(
                f"rafale-{numero}", titre="Synthèse en rafale",
                type_de_note=TypeDeNote.SYNTHESE,
            )

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertEqual(
            Page.objects.filter(title="Synthèse en rafale").count(), 1,
        )

    def test_une_note_citee_par_une_synthese_survit(self):
        # Le piege du 10 aout : les sources d'une synthese sont des
        # NOTES. Supprimer la note laisse l'article debout mais vide sa
        # preuve. / Deleting the source empties the article's evidence.
        note_source = creer_une_page("source", titre="Note source")
        extraction = creer_une_extraction(note_source)
        article = creer_une_page(
            "article", titre="Synthèse citante",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        SourceLink.objects.create(
            page_cible=article, start_char_cible=0, end_char_cible=10,
            page_source=note_source, extraction_source=extraction,
        )

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertTrue(Page.objects.filter(pk=note_source.pk).exists())

    def test_le_dernier_exemplaire_d_un_titre_survit(self):
        # Degraisser n'est pas faire disparaitre un sujet.
        # / Slimming is not making a subject vanish.
        creer_une_page("solo", titre="Sujet unique")

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertEqual(Page.objects.filter(title="Sujet unique").count(), 1)


class LaPurgeEnleveLesDoublonsTest(TestCase):
    """Ce qu'elle enleve vraiment. / What it actually removes."""

    def test_un_groupe_de_doublons_est_ramene_a_un_seul(self):
        for numero in range(5):
            creer_une_page(f"doublon-{numero}", titre="Sujet en double")

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertEqual(
            Page.objects.filter(title="Sujet en double").count(), 1,
        )

    def test_l_exemplaire_garde_est_celui_qui_porte_des_commentaires(self):
        auteur = Utilisateur.objects.create_user(
            username="auteur2", password="motdepasse",
        )
        for numero in range(3):
            creer_une_page(f"nu-{numero}", titre="Sujet arbitré")
        la_precieuse = creer_une_page("precieuse", titre="Sujet arbitré")
        extraction = creer_une_extraction(la_precieuse)
        CommentaireExtraction.objects.create(
            entity=extraction, user=auteur, commentaire="A garder.",
        )

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        restantes = Page.objects.filter(title="Sujet arbitré")
        self.assertEqual(restantes.count(), 1)
        self.assertEqual(restantes.first().pk, la_precieuse.pk)

    def test_une_page_dont_les_extractions_sont_ancrees_part_quand_meme(self):
        # `AncrageExtraction.element` est en PROTECT : le moteur de
        # structure interdit de supprimer un element qui porte une
        # portion, pour qu'on redistribue les portions d'abord. Cette
        # garde vise l'element SEUL — pas la page entiere, dont les
        # extractions s'en vont avec. Sans traiter le cas, la purge
        # levait ProtectedError et ne supprimait rien du tout.
        # / The PROTECT guard targets a lone element, not a whole page.
        from core.models import ElementDocument, empreinte_du_texte
        from hypostasis_extractor.models import AncrageExtraction, EtatAncrage

        for numero in range(2):
            page = creer_une_page(f"ancree-{numero}", titre="Sujet ancré")
            element = ElementDocument.objects.create(
                page=page, ordre=0, label="text", texte="Un contenu.",
                empreinte_contenu=empreinte_du_texte("Un contenu."),
            )
            AncrageExtraction.objects.create(
                extraction=creer_une_extraction(page), element=element,
                debut_dans_element=0, fin_dans_element=3,
                ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
            )

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertEqual(Page.objects.filter(title="Sujet ancré").count(), 1)

    def test_le_mode_a_blanc_ne_supprime_rien(self):
        for numero in range(4):
            creer_une_page(f"blanc-{numero}", titre="Sujet a blanc")

        call_command(
            "purger_les_notes_inutiles", "--a-blanc", stdout=StringIO(),
        )

        self.assertEqual(Page.objects.filter(title="Sujet a blanc").count(), 4)

    def test_le_bilan_annonce_ce_qui_part(self):
        for numero in range(3):
            creer_une_page(f"bilan-{numero}", titre="Sujet du bilan")

        sortie = StringIO()
        call_command(
            "purger_les_notes_inutiles", "--a-blanc", stdout=sortie,
        )

        # On asserte la LIGNE, pas un « 2 » isole : un chiffre nu se
        # trouve dans presque toute sortie chiffree, et l'assertion
        # restait verte quoi qu'il arrive.
        # / Assert the line, not a bare digit found in any output.
        self.assertRegex(sortie.getvalue(), r"Pages a supprimer\s+:\s+2\b")

    def test_relancer_la_purge_ne_propose_plus_rien(self):
        # LE POINT FIXE. Les gardes se calculent sur l'etat AVANT
        # suppression : une page peut n'etre protegee que par une autre
        # page qui, elle, part dans le meme passage — l'article qui la
        # citait, le parent dont elle etait l'enfant. Le protecteur
        # disparu, la protegee devient supprimable, et un second
        # lancement enleve encore des pages que le bilan du premier
        # n'avait pas annoncees.
        # / Guards computed on the pre-deletion state are not a fixed
        # point: a protector may itself be deleted in the same pass.
        # Deux articles en double, citant chacun une source differente.
        # Les DEUX sources sont protegees au premier passage, donc
        # aucune ne part — mais l'un des deux articles part comme
        # doublon, et sa source se retrouve nue. Au second passage elle
        # devient supprimable : le premier bilan avait donc menti.
        # / Both sources are protected at first; one loses its protector.
        sources = []
        for suffixe in ("a", "b"):
            article = creer_une_page(
                f"citant-{suffixe}", titre="Article citant",
                type_de_note=TypeDeNote.SYNTHESE,
            )
            source = creer_une_page(
                f"source-{suffixe}", titre="Source fragile",
            )
            SourceLink.objects.create(
                page_cible=article, start_char_cible=0, end_char_cible=5,
                page_source=source,
            )
            sources.append(source)

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        sortie = StringIO()
        call_command(
            "purger_les_notes_inutiles", "--a-blanc", stdout=sortie,
        )
        self.assertRegex(sortie.getvalue(), r"Pages a supprimer\s+:\s+0\b")

    def test_un_commentaire_pose_juste_avant_la_suppression_arrete_tout(self):
        # Le garde-fou « zero commentaire emporte » etait verifie AVANT
        # d'ouvrir la transaction, sans verrou : un commentaire pose
        # entre-temps partait en CASCADE, en silence. Il doit etre
        # recompte DANS la transaction.
        # / The guard was checked before the transaction, with no lock.
        from unittest import mock

        auteur = Utilisateur.objects.create_user(
            username="retardataire", password="motdepasse",
        )
        # L'exemplaire garde est le plus riche en extractions : on en
        # donne DEUX a celui qui reste, une seule au doublon — sinon
        # c'est le doublon qu'on garderait, et le commentaire tardif
        # tomberait sur une page conservee sans rien prouver.
        # / The richest copy is kept; make sure the comment lands on the
        # doomed one.
        gardee = creer_une_page("course-1", titre="Sujet en course")
        creer_une_extraction(gardee)
        creer_une_extraction(gardee)
        doublon = creer_une_page("course-2", titre="Sujet en course")
        extraction = creer_une_extraction(doublon)

        vraie_selection = (
            "core.management.commands.purger_les_notes_inutiles"
            ".Command._afficher_ce_qui_part"
        )
        original = None

        def commenter_juste_apres_le_controle(self, a_supprimer, a_blanc):
            resultat = original(self, a_supprimer, a_blanc)
            CommentaireExtraction.objects.get_or_create(
                entity=extraction, user=auteur,
                defaults={"commentaire": "Arrive trop tard."},
            )
            return resultat

        import core.management.commands.purger_les_notes_inutiles as module
        original = module.Command._afficher_ce_qui_part

        with mock.patch(vraie_selection, commenter_juste_apres_le_controle):
            with self.assertRaises(SystemExit):
                call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertEqual(CommentaireExtraction.objects.count(), 1)
        self.assertTrue(Page.objects.filter(pk=doublon.pk).exists())
        self.assertTrue(Page.objects.filter(pk=gardee.pk).exists())

    def test_aucun_commentaire_n_est_emporte(self):
        # L'invariant du produit, verifie sur le resultat et pas sur
        # l'intention. / The invariant, checked on the outcome.
        auteur = Utilisateur.objects.create_user(
            username="auteur3", password="motdepasse",
        )
        gardee = creer_une_page("gardee", titre="Sujet mixte")
        extraction = creer_une_extraction(gardee)
        CommentaireExtraction.objects.create(
            entity=extraction, user=auteur, commentaire="Le seul.",
        )
        for numero in range(3):
            creer_une_page(f"mixte-{numero}", titre="Sujet mixte")

        call_command("purger_les_notes_inutiles", stdout=StringIO())

        self.assertEqual(CommentaireExtraction.objects.count(), 1)
