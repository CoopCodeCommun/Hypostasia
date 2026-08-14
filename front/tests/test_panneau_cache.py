"""
Test : le panneau cache ne rend plus les cartes une seconde fois.
/ Test: the hidden panel no longer renders the cards a second time.

LOCALISATION : front/tests/test_panneau_cache.py

CE QUE LA MESURE A MONTRE — 14 aout 2026

`base.html` porte un `<aside id="sidebar-right" class="hidden">` qui
contient `#panneau-extractions`. Au chargement d'une note, il INCLUAIT
`panneau_analyse.html`, c'est-a-dire les memes cartes que le panneau
visible. Mesure sur la note 8 : **3 cartes dans le drawer, 3 cartes
dans le cache** — soit six `data-testid` identiques dans le DOM pour
trois idees.

CE QUE CE DOUBLE RENDU COUTAIT

  · un rendu serveur complet paye deux fois a chaque ouverture de note,
    cartes, commentaires et attributs compris ;
  · des `data-testid` en double, donc un selecteur nu qui tombe sur
    l'invisible une fois sur deux — un test peut attendre 30 secondes un
    element « visible » qui ne le sera jamais. C'est arrive le 14 aout.

CE QUE CE TEST NE CORRIGE PAS, ET QUI EST PIRE

`#panneau-extractions` reste la CIBLE de trois gestes — l'onglet
« extractions », le bouton d'extraction manuelle et le bouton
d'extraction IA (hypostasia.js:38, 686, 720) — qui ecrivent donc dans un
conteneur invisible. Mesure du 14 aout : selectionner du texte, cliquer
« extraction manuelle », et le formulaire « Extraction manuelle » se
rend bien... dans le cache. ZERO textarea visible a l'ecran.

Ce test retire le double rendu INITIAL. Il ne rebranche pas ces trois
gestes : c'est une decision d'architecture du panneau, laissee au
mainteneur.
/ The hidden aside re-rendered the same cards, paying a full server
render twice and duplicating every data-testid. This test removes that;
it does not rewire the three gestures that still target the hidden
container.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import AIModel, Page
from hypostasis_extractor.models import (
    AnalyseurSyntaxique,
    AncrageExtraction, ExtractedEntity, ExtractionJob,
)


class PanneauCacheTest(TestCase):
    """
    LOCALISATION : front/tests/test_panneau_cache.py
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="panneau_cache_test", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

        self.note = Page.objects.create(
            title="Note à cartes",
            html_original="", html_readability="", text_readability="",
            owner=self.proprietaire,
        )
        element = self.note.elements.create(
            ordre=0, label="text", texte="Un passage qui porte une idée.",
            empreinte_contenu="empreinte-panneau-cache",
        )
        # UN ANALYSEUR ACTIF EST INDISPENSABLE A CE TEST. `base.html` ne
        # precharge le panneau cache que `{% if page_preloaded and
        # analyseurs_actifs %}` : sans analyseur, il n'y a pas de double
        # rendu du tout, et ces tests passeraient AVANT la correction —
        # c'est-a-dire sans rien eprouver. Ils l'ont fait une premiere
        # fois, le 14 aout.
        # / Without an active analyser there is no double render at all,
        # and these tests would pass before the fix — proving nothing.
        # Un analyseur d'extraction n'est « utilisable » qu'avec au moins
        # UN EXEMPLE COMPLET — un texte source, et une extraction qui a
        # sa classe et son texte (services/__init__.py:171). Sans lui,
        # `_analyseurs_extraction_utilisables()` rend une liste vide, le
        # `{% if %}` de base.html est faux, et rien n'est preloade : ces
        # tests passeraient sans rien eprouver.
        # / An analyser is "usable" only with one complete example;
        # without it nothing is preloaded and these tests prove nothing.
        analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur du test", type_analyseur="analyser",
            is_active=True, est_par_defaut=True,
        )
        exemple = analyseur.examples.create(
            name="Exemple du test",
            example_text="Un texte d'exemple pour le cadre few-shot.",
        )
        exemple.extractions.create(
            extraction_class="phenomene",
            extraction_text="Un texte d'exemple",
        )
        modele = AIModel.objects.create(
            name="Mock cache", model_choice="mock_default", is_active=True,
        )
        job = ExtractionJob.objects.create(
            page=self.note, ai_model=modele, name="Extraction",
            prompt_description="Support", status="completed", entities_count=1,
        )
        idee = ExtractedEntity.objects.create(
            job=job, extraction_class="phenomene",
            extraction_text="Un passage qui porte une idée",
            start_char=0, end_char=29,
            attributes={"hypostases": "PHENOMENE", "resume": "Une idée."},
        )
        AncrageExtraction.objects.create(
            extraction=idee, element=element, ordre_dans_extraction=0,
            debut_dans_element=0, fin_dans_element=29,
        )

    def lire(self):
        reponse = self.client.get(f"/lire/{self.note.pk}/")
        self.assertEqual(reponse.status_code, 200)
        return reponse.content.decode("utf-8")

    # -------------------------------------------------------------------

    def test_la_page_ne_precharge_plus_les_cartes_dans_le_cache(self):
        """
        LE DOUBLE RENDU, PRIS A SA SOURCE.

        Le panneau VISIBLE se remplit par HTMX (`/extractions/
        drawer_contenu/`, drawer_vue_liste.js:158) : au chargement
        direct il ne porte qu'un squelette. Les cartes du HTML initial
        sont donc CELLES DU CACHE, et elles seront doublees des que le
        drawer se chargera — mesure du 14 aout : 3 dans l'un, 3 dans
        l'autre.

        Zero carte dans le HTML initial est donc le bon compte : le
        panneau visible les demandera lui-meme.
        / The visible panel fills itself via HTMX; cards in the initial
        HTML are the hidden copy, and get doubled the moment it loads.
        """
        html = self.lire()

        self.assertEqual(
            html.count('data-testid="btn-commenter-extraction"'),
            0,
            "Le panneau caché précharge encore les cartes : elles seront "
            "en double dès que le panneau visible se chargera.",
        )

    def test_le_conteneur_oob_survit_au_retrait_de_son_contenu(self):
        """
        `#panneau-extractions` reste la cible de quatre OOB swaps
        (views.py) et de trois appels HTMX. Le retirer ferait tomber ces
        swaps dans le vide, en silence — HTMX n'avertit pas quand une
        cible OOB manque.
        / The container stays: four OOB swaps and three HTMX calls target
        it, and HTMX says nothing when an OOB target is missing.
        """
        html = self.lire()

        self.assertIn('id="panneau-extractions"', html)
        self.assertIn('id="sidebar-right"', html)

    def test_le_panneau_visible_porte_toujours_la_carte(self):
        """
        LE PENDANT INDISPENSABLE : on a retire la COPIE, pas l'original.
        Sans cette verification, vider les DEUX panneaux passerait pour
        une reussite — et le lecteur n'aurait plus aucune idee a lire.
        / We removed the copy, not the original: without this, emptying
        both would look like success.
        """
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.note.pk}",
        )
        self.assertEqual(reponse.status_code, 200)

        self.assertIn(
            'data-testid="btn-commenter-extraction"',
            reponse.content.decode("utf-8"),
            "Le panneau visible ne porte plus la carte.",
        )
