"""
Tests de la reconversion ANCIEN -> ELEMENT (SPEC-ancrage v2 § 9.5).
/ Tests for the ANCIEN -> ELEMENT reconversion.

LOCALISATION : core/tests/test_reconversion_moteur.py

CE QUE CES TESTS PROTEGENT

La decision de gouvernance du 10 aout 2026 : le moteur ELEMENT devient le
SEUL moteur. La reconversion doit faire mourir l'ANCIEN sans rien perdre.
Mesure sur la base de dev qui motive ce chantier : 537 des 542 pages
ANCIEN portent DEJA leurs elements et 94 % de leurs extractions sont deja
ancrees — mais AUCUNE ne porte le flag `moteur`, parce que la commande
`basculer_vers_le_moteur_element` est anterieure a BR-A et ne traitait que
les pages DEPOURVUES d'elements.
/ Most pages already have elements and anchors but keep the old flag.

LES DEUX INVARIANTS

1. Rien ne disparait : aucune extraction, aucun commentaire supprime. Une
   extraction qu'on ne sait pas re-ancrer reste en base, sans portion —
   elle se montrera comme detachee, et un humain tranchera.
2. On ne devine pas : quand la position d'un element dans le texte de la
   page n'est pas retrouvable, on ne re-ancre pas au jugé. Et une ancre
   qui designe un AUTRE passage que la citation est pire que pas d'ancre
   du tout — c'est le seul mensonge que le produit ne peut pas se
   permettre, puisque l'ancre est la preuve.
/ Nothing vanishes; we never guess an anchor. A wrong anchor is worse
than none, because the anchor IS the evidence.
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    ElementDocument,
    MoteurDePage,
    Page,
    empreinte_du_texte,
)
from hypostasis_extractor.models import (
    AncrageExtraction,
    CommentaireExtraction,
    EtatAncrage,
    ExtractedEntity,
    ExtractionJob,
)

Utilisateur = get_user_model()

PREMIER_PARAGRAPHE = "Le conseil a vote le budget a l'unanimite."
SECOND_PARAGRAPHE = "La minorite a demande un report du vote."
TEXTE_DE_LA_PAGE = f"{PREMIER_PARAGRAPHE}\n\n{SECOND_PARAGRAPHE}"


def creer_une_page(suffixe_unique, texte=TEXTE_DE_LA_PAGE, **champs):
    """Cree une page ANCIEN minimale. / Minimal ANCIEN page."""
    return Page.objects.create(
        url=f"http://exemple.local/reconv-{suffixe_unique}",
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability=texte,
        content_hash=f"hash-reconv-{suffixe_unique}",
        title=f"Note {suffixe_unique}",
        **champs,
    )


def creer_les_elements_a_la_main(page, textes):
    """
    Cree les elements d'une page SANS Docling.
    / Creates a page's elements WITHOUT Docling.

    Docling charge des modeles de plusieurs Go : interdit en test comme en
    fixture sur cet hote de 8 Go partages avec la production.
    """
    return [
        ElementDocument.objects.create(
            page=page,
            ordre=position,
            label="text",
            texte=texte,
            empreinte_contenu=empreinte_du_texte(texte),
        )
        for position, texte in enumerate(textes)
    ]


def creer_une_extraction(page, texte, debut, fin):
    """Cree une extraction de l'ANCIEN moteur (offsets). / Old-engine extraction."""
    job = ExtractionJob.objects.create(
        page=page,
        name="Job de test",
        prompt_description="Extraire les decisions",
    )
    return ExtractedEntity.objects.create(
        job=job,
        extraction_class="decision",
        extraction_text=texte,
        start_char=debut,
        end_char=fin,
    )


class ReconversionDUnePageDejaPourvueDElementsTest(TestCase):
    """
    LE CAS MAJORITAIRE en base : la page a ses elements, il ne manque que
    le flag. / The majority case: elements exist, only the flag is missing.
    """

    def test_une_page_avec_elements_bascule_sur_le_moteur_element(self):
        page = creer_une_page("deja-pourvue")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        page.refresh_from_db()
        self.assertEqual(page.moteur, MoteurDePage.ELEMENT)

    def test_elle_ne_recree_aucun_element(self):
        # Recreer les elements d'une page qui en a deja dupliquerait ses
        # blocs et detacherait les ancres existantes.
        # / Re-creating elements would duplicate blocks.
        page = creer_une_page("pas-de-doublon")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertEqual(page.elements.count(), 2)

    def test_elle_reancre_les_extractions_qui_n_ont_pas_d_ancrage(self):
        # 2 225 extractions de la base sont dans ce cas, toutes sur des
        # pages qui ont deja leurs elements.
        # / 2,225 extractions in this exact situation.
        page = creer_une_page("reancrage")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        debut = TEXTE_DE_LA_PAGE.index("budget")
        extraction = creer_une_extraction(
            page, "budget", debut, debut + len("budget"),
        )
        self.assertFalse(extraction.ancrages.exists())

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        ancrages = list(extraction.ancrages.all())
        self.assertEqual(len(ancrages), 1)
        self.assertEqual(ancrages[0].element_id, elements[0].pk)
        self.assertEqual(ancrages[0].etat_ancrage, EtatAncrage.ANCREE)

    def test_elle_ne_touche_pas_aux_ancrages_deja_poses(self):
        # L'ancre doit etre JUSTE, sinon la passe de verification la
        # detacherait — a raison — et ce test prouverait le contraire de
        # ce que son nom annonce.
        # / The anchor must be a truthful one, or the check detaches it.
        page = creer_une_page("ancrage-intact")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        debut = PREMIER_PARAGRAPHE.index("budget")
        extraction = creer_une_extraction(page, "budget", 0, 10)
        ancrage_existant = AncrageExtraction.objects.create(
            extraction=extraction,
            element=elements[0],
            debut_dans_element=debut,
            fin_dans_element=debut + len("budget"),
            ordre_dans_extraction=0,
            etat_ancrage=EtatAncrage.ANCREE,
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertEqual(extraction.ancrages.count(), 1)
        ancrage_existant.refresh_from_db()
        self.assertEqual(ancrage_existant.fin_dans_element, debut + 6)
        self.assertEqual(ancrage_existant.etat_ancrage, EtatAncrage.ANCREE)

    def test_une_extraction_deja_ancree_ne_recoit_pas_une_seconde_ancre(self):
        # Le filtre anti-doublon n'etait prouve par aucun test : on
        # pouvait le retirer sans qu'un seul tombe. Sur la base reelle il
        # produirait un doublon d'ordre_dans_extraction, donc une
        # IntegrityError au commit — la contrainte etant DEFERRED, elle ne
        # tombe qu'a la fin, quand la page entiere est perdue.
        # / Nothing proved the anti-duplicate filter; on the real base it
        # would raise a DEFERRED IntegrityError at commit time.
        page = creer_une_page("deja-ancree")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        debut_dans_la_page = TEXTE_DE_LA_PAGE.index("budget")
        debut_dans_le_bloc = PREMIER_PARAGRAPHE.index("budget")
        extraction = creer_une_extraction(
            page, "budget",
            debut_dans_la_page, debut_dans_la_page + len("budget"),
        )
        AncrageExtraction.objects.create(
            extraction=extraction, element=elements[0],
            debut_dans_element=debut_dans_le_bloc,
            fin_dans_element=debut_dans_le_bloc + len("budget"),
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertEqual(extraction.ancrages.count(), 1)


class ReconversionDUnePageSansElementTest(TestCase):
    """
    Le cas minoritaire (5 pages en base) : il faut d'abord decouper le
    texte. / The minority case: the text must be split first.
    """

    def test_elle_cree_les_elements_puis_bascule(self):
        page = creer_une_page("sans-element")

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        page.refresh_from_db()
        self.assertEqual(page.elements.count(), 2)
        self.assertEqual(page.moteur, MoteurDePage.ELEMENT)

    def test_une_page_sans_texte_exploitable_reste_sur_l_ancien(self):
        # Basculer une page qui n'a aucun bloc a lire la rendrait vide :
        # le moteur ELEMENT n'aurait rien a afficher.
        # / Flipping a page with no readable block would empty it.
        page = creer_une_page("texte-vide", texte="")

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        page.refresh_from_db()
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)
        self.assertEqual(page.elements.count(), 0)


class RienNeDisparaitTest(TestCase):
    """
    L'invariant n°1, celui qui protege les 983 commentaires humains.
    / Invariant #1, protecting the 983 human comments.
    """

    def test_une_extraction_non_reancrable_survit_avec_ses_commentaires(self):
        # 0-0 : l'ancien moteur ecrivait ces offsets quand LangExtract ne
        # retrouvait pas le passage. Il n'y a rien a traduire — mais
        # l'extraction et son commentaire restent.
        # / Nothing to translate, yet extraction and comment remain.
        auteur = Utilisateur.objects.create_user(
            username="commentateur", password="motdepasse",
        )
        page = creer_une_page("commentee")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, "introuvable", 0, 0)
        CommentaireExtraction.objects.create(
            entity=extraction, user=auteur, commentaire="Je conteste.",
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        extraction.refresh_from_db()
        self.assertEqual(extraction.commentaires.count(), 1)
        self.assertEqual(
            extraction.commentaires.first().commentaire, "Je conteste.",
        )
        self.assertFalse(extraction.ancrages.exists())

    def test_le_bilan_compte_les_extractions_commentees_detachees(self):
        auteur = Utilisateur.objects.create_user(
            username="commentateur2", password="motdepasse",
        )
        page = creer_une_page("bilan-commentee")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, "introuvable", 0, 0)
        CommentaireExtraction.objects.create(
            entity=extraction, user=auteur, commentaire="Je conteste.",
        )

        sortie = StringIO()
        call_command("basculer_vers_le_moteur_element", stdout=sortie)

        # On asserte le CHIFFRE, pas le titre : le titre est imprime
        # inconditionnellement, donc l'asserter laissait passer un
        # comptage entierement casse.
        # / Assert the count, not the heading printed unconditionally.
        self.assertRegex(
            sortie.getvalue(), r"detachees\s+:\s+1\b",
        )


class OnNeDevinePasTest(TestCase):
    """
    L'invariant n°2 : sans position sure, pas d'ancre.
    / Invariant #2: no sure position, no anchor.
    """

    def test_des_elements_absents_du_texte_ne_produisent_aucune_ancre(self):
        # Une page dont les elements viennent d'ailleurs (conversion
        # Docling) : leurs textes ne se retrouvent pas dans
        # text_readability, donc les anciens offsets ne sont traduisibles
        # en rien. On bascule quand meme — les blocs existent, la page se
        # lit — mais sans inventer d'ancre.
        # / Elements from another source: flip the page, invent no anchor.
        page = creer_une_page("elements-etrangers")
        creer_les_elements_a_la_main(
            page, ["Un contenu qui ne figure pas dans le texte de la page."],
        )
        extraction = creer_une_extraction(page, "budget", 0, 10)

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        page.refresh_from_db()
        self.assertEqual(page.moteur, MoteurDePage.ELEMENT)
        self.assertFalse(extraction.ancrages.exists())


class UneAncreQuiDesigneAutreChoseNEstPasPoseeTest(TestCase):
    """
    Les anciens offsets sont DANS LES BORNES du texte, ce qui ne veut pas
    dire qu'ils sont AU BON ENDROIT. Mesure du 10 aout sur les 518
    extractions re-ancrables de la base : 452 tranches correspondent a la
    citation, 11 la couvrent a 95 % ou plus (ponctuation), et 47 designent
    un passage sans rapport — dont une citation de 500 caracteres dont les
    offsets ne couvrent que « l' ».
    / In-bounds offsets are not in-place offsets.
    """

    def test_des_offsets_qui_pointent_un_autre_passage_ne_produisent_rien(self):
        page = creer_une_page("offsets-menteurs")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        # La citation parle du report du vote ; les offsets designent le
        # tout debut de la page, qui parle d'autre chose.
        # / The citation and the offsets disagree.
        extraction = creer_une_extraction(page, "un report du vote", 0, 10)

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertFalse(extraction.ancrages.exists())

    def test_des_offsets_qui_ne_couvrent_que_deux_caracteres_ne_valent_rien(self):
        # Le cas trouve en base : une longue citation dont le span ne
        # couvre qu'un fragment minuscule. La tranche est bien une
        # sous-chaine de la citation, et pourtant l'ancre serait fausse.
        # / A tiny slice of a long citation is not an anchor.
        page = creer_une_page("offsets-riquiqui")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        debut = TEXTE_DE_LA_PAGE.index("Le conseil")
        extraction = creer_une_extraction(
            page, PREMIER_PARAGRAPHE, debut, debut + 2,
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertFalse(extraction.ancrages.exists())

    def test_un_span_qui_surligne_bien_plus_que_la_citation_est_refuse(self):
        # Le miroir du cas precedent, et le meme mensonge : la citation
        # tient en un mot, le span couvre le paragraphe entier. Le lecteur
        # verrait sept fois trop de texte surligne comme etant « la
        # preuve ». Comparer la longueur de la citation a celle de l'ancre
        # ne suffit donc pas : il faut comparer la PLUS COURTE a la plus
        # longue, dans les deux sens.
        # / The mirror case: the anchor highlights far more than the quote.
        page = creer_une_page("span-trop-large")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(
            page, "budget", 0, len(PREMIER_PARAGRAPHE),
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertFalse(extraction.ancrages.exists())

    def test_un_mot_coupe_entre_deux_blocs_reste_ancrable(self):
        # « deux blocs sont separes par un blanc » est faux quand un mot a
        # ete coupe par un tiret a la frontiere. Recoller avec un espace
        # donne « jesus- christ » la ou la citation dit « jesus-christ »,
        # et une ancre juste passerait pour fausse. Mesure du 10 aout :
        # 4 ancres dormantes justes et 5 ancres neuves justes en base.
        # / A hyphen-split word across two blocks is still a valid anchor.
        premier = "Il a confesse sa foi en Jesus-"
        second = "Christ, Verbe incarne."
        texte = f"{premier}\n\n{second}"
        page = creer_une_page("mot-coupe", texte=texte)
        elements = creer_les_elements_a_la_main(page, [premier, second])
        extraction = creer_une_extraction(
            page, "Jesus-Christ, Verbe incarne.", 0, 0,
        )
        for rang, element in enumerate(elements):
            debut = element.texte.index("Jesus-") if rang == 0 else 0
            AncrageExtraction.objects.create(
                extraction=extraction, element=element,
                debut_dans_element=debut,
                fin_dans_element=len(element.texte),
                ordre_dans_extraction=rang,
                etat_ancrage=EtatAncrage.ANCREE,
            )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        for ancrage in extraction.ancrages.all():
            self.assertEqual(ancrage.etat_ancrage, EtatAncrage.ANCREE)

    def test_une_troncature_de_ponctuation_reste_acceptee(self):
        # A l'inverse, un span qui couvre la citation a la ponctuation
        # finale pres designe bien le bon passage : on l'ancre.
        # / A span short by its final punctuation still points right.
        page = creer_une_page("offsets-ponctuation")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        debut = TEXTE_DE_LA_PAGE.index("Le conseil")
        extraction = creer_une_extraction(
            page,
            PREMIER_PARAGRAPHE,
            debut,
            debut + len(PREMIER_PARAGRAPHE) - 1,
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertTrue(extraction.ancrages.exists())


class LesAncresDormantesSontVerifieesTest(TestCase):
    """
    Les 28 096 ancres deja en base viennent d'anciennes phases de test et
    n'ont jamais ete auditees. La reconversion les rend OFFICIELLES : elle
    doit donc les regarder. Mesure du 10 aout : 6,2 % designent un passage
    sans rapport avec leur citation, dont 59 portant un commentaire humain.
    Decision du proprietaire : detacher ces mensongeres, garder les
    tronquees (une partie du bon passage reste honnete).
    / Dormant anchors become official, so they get checked first.
    """

    def test_une_ancre_dormante_qui_designe_autre_chose_est_detachee(self):
        page = creer_une_page("dormante-fausse")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, "un report du vote", 0, 0)
        ancrage = AncrageExtraction.objects.create(
            extraction=extraction,
            element=elements[0],
            debut_dans_element=0,
            fin_dans_element=len("Le conseil"),
            ordre_dans_extraction=0,
            etat_ancrage=EtatAncrage.ANCREE,
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        ancrage.refresh_from_db()
        self.assertEqual(ancrage.etat_ancrage, EtatAncrage.DETACHEE)

    def test_elle_n_est_pas_supprimee_pour_autant(self):
        # Detacher n'est pas effacer : l'ancre reste, l'extraction reste,
        # le commentaire reste. Un humain pourra trancher.
        # / Detaching is not deleting.
        auteur = Utilisateur.objects.create_user(
            username="temoin", password="motdepasse",
        )
        page = creer_une_page("dormante-conservee")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, "un report du vote", 0, 0)
        CommentaireExtraction.objects.create(
            entity=extraction, user=auteur, commentaire="Important.",
        )
        AncrageExtraction.objects.create(
            extraction=extraction, element=elements[0],
            debut_dans_element=0, fin_dans_element=len("Le conseil"),
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertEqual(extraction.ancrages.count(), 1)
        self.assertEqual(extraction.commentaires.count(), 1)

    def test_une_ancre_dormante_juste_est_laissee_intacte(self):
        page = creer_une_page("dormante-juste")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, PREMIER_PARAGRAPHE, 0, 0)
        ancrage = AncrageExtraction.objects.create(
            extraction=extraction, element=elements[0],
            debut_dans_element=0, fin_dans_element=len(PREMIER_PARAGRAPHE),
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        ancrage.refresh_from_db()
        self.assertEqual(ancrage.etat_ancrage, EtatAncrage.ANCREE)

    def test_une_ancre_dormante_a_cheval_sur_deux_blocs_est_conservee(self):
        # Une citation qui traverse deux elements est ancree en DEUX
        # portions. Les recoller bout a bout sans rien entre elles
        # souderait le dernier mot du premier bloc au premier mot du
        # second (« l'unanimite.La minorite »), et l'ancre paraitrait
        # fausse alors qu'elle est juste. Dans le document, deux blocs
        # consecutifs sont toujours separes par un blanc.
        # / Two blocks are always separated by whitespace in the document.
        page = creer_une_page("dormante-a-cheval")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, TEXTE_DE_LA_PAGE, 0, 0)
        for rang, element in enumerate(elements):
            AncrageExtraction.objects.create(
                extraction=extraction, element=element,
                debut_dans_element=0, fin_dans_element=len(element.texte),
                ordre_dans_extraction=rang,
                etat_ancrage=EtatAncrage.ANCREE,
            )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        for ancrage in extraction.ancrages.all():
            self.assertEqual(ancrage.etat_ancrage, EtatAncrage.ANCREE)

    def test_une_ancre_dormante_tronquee_est_conservee(self):
        # Decision du proprietaire : surligner une PARTIE du bon passage
        # est degrade, pas mensonger. On garde.
        # / Truncated is degraded, not lying: keep it.
        page = creer_une_page("dormante-tronquee")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, PREMIER_PARAGRAPHE, 0, 0)
        ancrage = AncrageExtraction.objects.create(
            extraction=extraction, element=elements[0],
            debut_dans_element=0, fin_dans_element=len("Le conseil a vote"),
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        ancrage.refresh_from_db()
        self.assertEqual(ancrage.etat_ancrage, EtatAncrage.ANCREE)

    def test_une_ancre_qui_ne_surligne_rien_est_detachee(self):
        # Une portion vide (bornes egales, ou sorties du texte apres une
        # edition) ne montre AUCUN passage. La laisser ANCREE, c'est
        # annoncer une preuve qui n'affiche rien.
        # / An anchor highlighting nothing must not stay official.
        page = creer_une_page("ancre-vide")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, "budget", 0, 0)
        ancrage = AncrageExtraction.objects.create(
            extraction=extraction, element=elements[0],
            debut_dans_element=3, fin_dans_element=3,
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        ancrage.refresh_from_db()
        self.assertEqual(ancrage.etat_ancrage, EtatAncrage.DETACHEE)

    def test_les_pk_detaches_sont_nommes_dans_la_sortie(self):
        # Sans les numeros, les quelques ancres justes detachees a tort
        # sont indiscernables des menteuses dans le tas a trier.
        # / Without pks, wrongly detached anchors vanish into the pile.
        page = creer_une_page("pk-nommes")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, "un report du vote", 0, 0)
        AncrageExtraction.objects.create(
            extraction=extraction, element=elements[0],
            debut_dans_element=0, fin_dans_element=len("Le conseil"),
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
        )

        sortie = StringIO()
        call_command("basculer_vers_le_moteur_element", stdout=sortie)

        self.assertIn(str(extraction.pk), sortie.getvalue())

    def test_le_mode_a_blanc_ne_detache_aucune_ancre(self):
        page = creer_une_page("dormante-a-blanc")
        elements = creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        extraction = creer_une_extraction(page, "un report du vote", 0, 0)
        ancrage = AncrageExtraction.objects.create(
            extraction=extraction, element=elements[0],
            debut_dans_element=0, fin_dans_element=len("Le conseil"),
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
        )

        call_command(
            "basculer_vers_le_moteur_element", "--a-blanc", stdout=StringIO(),
        )

        ancrage.refresh_from_db()
        self.assertEqual(ancrage.etat_ancrage, EtatAncrage.ANCREE)


class UnElementVideNArretePasLaCommandeTest(TestCase):
    """
    Le croisement qui plantait : la table de positions saute les elements
    a texte vide, mais la liste des elements passee au decoupeur les
    gardait — d'ou un KeyError qui arretait la commande au milieu des 542
    pages, mode a blanc compris.
    / Skipped in the table but kept in the list: a KeyError mid-run.
    """

    def test_un_element_vide_au_milieu_n_empeche_pas_le_reancrage(self):
        page = creer_une_page("element-vide")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, "", SECOND_PARAGRAPHE],
        )
        debut = TEXTE_DE_LA_PAGE.index(SECOND_PARAGRAPHE)
        extraction = creer_une_extraction(
            page, SECOND_PARAGRAPHE, debut, debut + len(SECOND_PARAGRAPHE),
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        page.refresh_from_db()
        self.assertEqual(page.moteur, MoteurDePage.ELEMENT)
        self.assertTrue(extraction.ancrages.exists())

    def test_un_element_fait_d_un_seul_blanc_compte_comme_vide(self):
        # Le decoupage exige 2 caracteres non blancs pour faire un
        # element ; le filtre, lui, se contentait d'une chaine non vide.
        # Un element fait d'un espace passait donc, sans jamais rien
        # afficher. Meme regle des deux cotes.
        # / Same emptiness rule on both sides.
        page = creer_une_page("element-blanc")
        creer_les_elements_a_la_main(page, [" ", "\n "])

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        page.refresh_from_db()
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)

    def test_une_page_dont_tous_les_elements_sont_vides_reste_ancienne(self):
        # Sinon elle deviendrait une page ELEMENT sans un bloc a lire.
        # / Otherwise it becomes an ELEMENT page with nothing to read.
        page = creer_une_page("elements-tous-vides")
        creer_les_elements_a_la_main(page, ["", ""])

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        page.refresh_from_db()
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)


REFRAIN = "Le vote est reporte."
OUVERTURE = "Ouverture de la seance."
CONCLUSION = "Conclusion de la seance."

# Le refrain apparait DEUX fois entre l'ouverture et la conclusion, et un
# seul element le revendique. Les deux copies tiennent dans la meme zone
# permise : l'ordre du document ne tranche pas, rien ne dit laquelle cet
# element occupe. (Le paragraphe « Un interlude. » n'a pas d'element : la
# zone entre deux elements n'est pas forcement vide.)
# / Two copies in one gap, one element claiming them: undecidable.
TEXTE_AMBIGU = (
    f"{OUVERTURE}\n\n{REFRAIN}\n\nUn interlude.\n\n{REFRAIN}\n\n{CONCLUSION}"
)
ELEMENTS_AMBIGUS = [OUVERTURE, REFRAIN, CONCLUSION]


class UnTexteDElementRepeteEstAmbiguTest(TestCase):
    """
    La recherche en avant retient la premiere occurrence du texte d'un
    element — qui n'est pas toujours la bonne. Les positions restent
    croissantes, donc rien ne trahit l'erreur.

    ATTENTION a ce qui n'est PAS ambigu : si le refrain apparait deux fois
    et que DEUX elements le portent, l'ordre du document attribue une
    copie a chacun. C'est le cas courant, et il doit s'ancrer normalement.
    / Repetition alone is not ambiguity; see the second test.
    """

    def test_une_extraction_visant_un_element_ambigu_n_est_pas_ancree(self):
        # L'extraction vise la copie que l'element est CENSE occuper. Le
        # span le recoupe donc, et l'ancre serait posee sans hesiter — sauf
        # que rien ne garantit que l'element soit sur cette copie-la plutot
        # que sur l'autre. C'est la que l'incertitude mord : viser l'autre
        # copie tomberait simplement dans un trou entre deux elements, et
        # serait refuse comme « introuvable » pour une tout autre raison.
        # / Aim at the copy the element supposedly occupies.
        page = creer_une_page("refrain", texte=TEXTE_AMBIGU)
        creer_les_elements_a_la_main(page, ELEMENTS_AMBIGUS)
        debut = TEXTE_AMBIGU.index(REFRAIN)
        extraction = creer_une_extraction(
            page, REFRAIN, debut, debut + len(REFRAIN),
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertFalse(extraction.ancrages.exists())

    def test_deux_elements_portant_le_meme_texte_ne_sont_pas_ambigus(self):
        # L'ordre du document tranche : le premier element est la
        # premiere copie, le second est la seconde.
        # / Document order assigns one copy to each element.
        texte = f"{REFRAIN}\n\n{PREMIER_PARAGRAPHE}\n\n{REFRAIN}"
        page = creer_une_page("refrain-deux-elements", texte=texte)
        creer_les_elements_a_la_main(
            page, [REFRAIN, PREMIER_PARAGRAPHE, REFRAIN],
        )
        debut = texte.rindex(REFRAIN)
        extraction = creer_une_extraction(
            page, REFRAIN, debut, debut + len(REFRAIN),
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertTrue(extraction.ancrages.exists())

    def test_les_autres_extractions_de_la_page_sont_ancrees_quand_meme(self):
        # On refuse l'element ambigu, pas la page entiere.
        # / We refuse the ambiguous element, not the whole page.
        page = creer_une_page("refrain-partiel", texte=TEXTE_AMBIGU)
        creer_les_elements_a_la_main(page, ELEMENTS_AMBIGUS)
        debut = TEXTE_AMBIGU.index(CONCLUSION)
        extraction = creer_une_extraction(
            page, CONCLUSION, debut, debut + len(CONCLUSION),
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertTrue(extraction.ancrages.exists())

    def test_un_element_place_autrement_par_la_fin_est_ambigu(self):
        # Le piege : borner la zone d'un element par la position GLOUTONNE
        # de ses voisins, c'est supposer resolu ce qu'on cherche a
        # verifier. Texte « A B A B », elements [A, B] : la lecture en
        # avant donne A1-B1, la lecture en arriere donne A2-B2. Les deux
        # tiennent. A est donc incertain — mais sa zone, bornee par B pris
        # gloutonnement, ne contient qu'un seul A et le declare sûr.
        # / Forward-greedy bounds hide the ambiguity they should reveal.
        bloc_a = "Premiere affirmation."
        bloc_b = "Seconde affirmation."
        texte = f"{bloc_a}\n\n{bloc_b}\n\n{bloc_a}\n\n{bloc_b}"
        page = creer_une_page("aller-retour", texte=texte)
        creer_les_elements_a_la_main(page, [bloc_a, bloc_b])
        extraction = creer_une_extraction(page, bloc_a, 0, len(bloc_a))

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertFalse(extraction.ancrages.exists())

    def test_le_bilan_compte_les_ambigus(self):
        page = creer_une_page("refrain-bilan", texte=TEXTE_AMBIGU)
        creer_les_elements_a_la_main(page, ELEMENTS_AMBIGUS)
        debut = TEXTE_AMBIGU.index(REFRAIN)
        creer_une_extraction(page, REFRAIN, debut, debut + len(REFRAIN))

        sortie = StringIO()
        call_command("basculer_vers_le_moteur_element", stdout=sortie)

        self.assertIn("detachees (ambigu)  : 1", sortie.getvalue())


class UnePageEnErreurNArretePasLeRunTest(TestCase):
    """
    542 pages a traiter : une seule page empoisonnee ne doit pas priver
    les 541 autres de leur bascule, ni obliger a tout recommencer.
    / One poisoned page must not cost the other 541 their migration.
    """

    def test_les_pages_suivantes_sont_traitees_malgre_une_erreur(self):
        page_qui_casse = creer_une_page("erreur-1")
        creer_les_elements_a_la_main(page_qui_casse, [PREMIER_PARAGRAPHE])
        page_saine = creer_une_page("erreur-2")
        creer_les_elements_a_la_main(page_saine, [PREMIER_PARAGRAPHE])

        vraie_methode = (
            "core.management.commands.basculer_vers_le_moteur_element"
            ".Command._basculer_une_page"
        )
        original = None

        def casser_sur_la_premiere(self, page, a_blanc):
            if page.pk == page_qui_casse.pk:
                raise ValueError("panne simulee")
            return original(self, page, a_blanc)

        import core.management.commands.basculer_vers_le_moteur_element as module
        original = module.Command._basculer_une_page

        with mock.patch(vraie_methode, casser_sur_la_premiere):
            sortie = StringIO()
            call_command("basculer_vers_le_moteur_element", stdout=sortie)

        page_qui_casse.refresh_from_db()
        page_saine.refresh_from_db()
        self.assertEqual(page_qui_casse.moteur, MoteurDePage.ANCIEN)
        self.assertEqual(page_saine.moteur, MoteurDePage.ELEMENT)
        self.assertIn("en erreur", sortie.getvalue())


class IdempotenceEtModeABlancTest(TestCase):
    """Relancer ne double rien ; a blanc n'ecrit rien."""

    def test_relancer_la_commande_ne_cree_aucun_doublon(self):
        page = creer_une_page("idempotence")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        debut = TEXTE_DE_LA_PAGE.index("budget")
        extraction = creer_une_extraction(
            page, "budget", debut, debut + len("budget"),
        )

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())
        elements_apres_un_passage = page.elements.count()
        ancrages_apres_un_passage = extraction.ancrages.count()

        call_command("basculer_vers_le_moteur_element", stdout=StringIO())

        self.assertEqual(page.elements.count(), elements_apres_un_passage)
        self.assertEqual(
            extraction.ancrages.count(), ancrages_apres_un_passage,
        )

    def test_le_mode_a_blanc_n_ecrit_rien(self):
        page = creer_une_page("a-blanc")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        debut = TEXTE_DE_LA_PAGE.index("budget")
        extraction = creer_une_extraction(
            page, "budget", debut, debut + len("budget"),
        )

        call_command(
            "basculer_vers_le_moteur_element", "--a-blanc", stdout=StringIO(),
        )

        page.refresh_from_db()
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)
        self.assertEqual(page.elements.count(), 2)
        self.assertFalse(extraction.ancrages.exists())


class SelectionDesPagesATraiterTest(TestCase):
    """
    Le filtre de selection. La version d'origine ne voyait QUE les pages
    sans elements — donc 537 pages sur 542 lui etaient invisibles, y
    compris quand on la lancait sur une page nommee.
    / The original filter hid 537 of 542 pages, even by explicit --page.
    """

    def test_l_option_page_atteint_une_page_qui_a_deja_des_elements(self):
        page = creer_une_page("option-page")
        creer_les_elements_a_la_main(
            page, [PREMIER_PARAGRAPHE, SECOND_PARAGRAPHE],
        )
        page_voisine = creer_une_page("option-page-voisine")
        creer_les_elements_a_la_main(page_voisine, [PREMIER_PARAGRAPHE])

        call_command(
            "basculer_vers_le_moteur_element",
            "--page", str(page.pk),
            stdout=StringIO(),
        )

        page.refresh_from_db()
        page_voisine.refresh_from_db()
        self.assertEqual(page.moteur, MoteurDePage.ELEMENT)
        self.assertEqual(page_voisine.moteur, MoteurDePage.ANCIEN)

    def test_une_page_deja_element_n_est_pas_retraitee(self):
        page = creer_une_page("deja-element", moteur=MoteurDePage.ELEMENT)

        sortie = StringIO()
        call_command("basculer_vers_le_moteur_element", stdout=sortie)

        self.assertEqual(page.elements.count(), 0)
        self.assertIn("0 page(s) a traiter", sortie.getvalue())

    def test_viser_une_page_deja_element_le_dit_au_lieu_de_se_taire(self):
        # « 0 page a traiter » sur une page nommee laisse croire a une
        # erreur de frappe. La commande doit dire ce qu'elle a trouve.
        # / Silence on an explicit --page reads like a typo.
        page = creer_une_page("deja-element-nommee", moteur=MoteurDePage.ELEMENT)

        sortie = StringIO()
        call_command(
            "basculer_vers_le_moteur_element",
            "--page", str(page.pk),
            stdout=sortie,
        )

        self.assertIn("deja sur le moteur ELEMENT", sortie.getvalue())

    def test_une_limite_a_zero_ne_fait_pas_mentir_le_message(self):
        # --page sur une page ANCIEN, mais --limite 0 la fait sortir de la
        # selection : dire « deja sur le moteur ELEMENT » serait faux.
        # / The page is ANCIEN; only the limit excluded it.
        page = creer_une_page("limite-zero")
        creer_les_elements_a_la_main(page, [PREMIER_PARAGRAPHE])

        sortie = StringIO()
        call_command(
            "basculer_vers_le_moteur_element",
            "--page", str(page.pk), "--limite", "0",
            stdout=sortie,
        )

        self.assertNotIn("deja sur le moteur ELEMENT", sortie.getvalue())
