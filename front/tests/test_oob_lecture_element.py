"""
Le re-rendu OOB de la zone de lecture respecte le moteur ELEMENT.
/ The OOB re-render of the reading area respects the ELEMENT engine.

LOCALISATION : front/tests/test_oob_lecture_element.py

CE QUE CES TESTS PROTEGENT

Cinq actions du panneau d'extractions (`panneau`, `creer_manuelle`,
`supprimer_ia`, `promouvoir_entrainement`, `ia`) renvoient un swap
« out of band » qui REMPLACE tout le contenu de `#readability-content`.
Ce remplacement etait construit par l'ANCIEN moteur — le HTML readability
annote par `annoter_html_avec_barres`.

Sur une page ELEMENT, la lecture est faite de BLOCS
(`_blocs_elements.html`). Le swap les ecrasait donc par un rendu de
l'ancien moteur : apres avoir simplement cree une extraction a la main,
le lecteur perdait ses blocs, ses boutons d'operations et ses ancres,
jusqu'au rechargement complet de la page.

Ces vues ne consultaient pas `Page.moteur` : elles ont ete ecrites avant
lui et personne ne les avait rouvertes depuis.
/ Five actions replaced the whole reading area with old-engine HTML,
wiping the ELEMENT blocks.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import ElementDocument, Page, empreinte_du_texte
from hypostasis_extractor.models import (
    AncrageExtraction,
    EtatAncrage,
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)

Utilisateur = get_user_model()

PREMIER = "Le conseil a vote le budget."
SECOND = "La minorite a demande un report."
TEXTE = f"{PREMIER}\n\n{SECOND}"


class LeSwapOobRendLesBlocsDUnePageElementTest(TestCase):
    """La zone de lecture reste faite de blocs apres une action."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio", password="motdepasse",
        )
        self.page = Page.objects.create(
            url="http://exemple.local/oob-element",
            html_original="<p>o</p>",
            html_readability=f"<p>{PREMIER}</p><p>{SECOND}</p>",
            text_readability=TEXTE,
            content_hash="empreinte-oob",
            title="Note ELEMENT",
            owner=self.proprietaire,
        )
        self.elements = [
            ElementDocument.objects.create(
                page=self.page, ordre=rang, label="text", texte=texte,
                empreinte_contenu=empreinte_du_texte(texte),
            )
            for rang, texte in enumerate([PREMIER, SECOND])
        ]
        self.job = ExtractionJob.objects.create(
            page=self.page, name="Job", prompt_description="p",
            status=ExtractionJobStatus.COMPLETED,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=self.job, extraction_class="idee",
            extraction_text="budget", start_char=TEXTE.index("budget"),
            end_char=TEXTE.index("budget") + len("budget"))
        AncrageExtraction.objects.create(
            extraction=self.extraction, element=self.elements[0],
            debut_dans_element=PREMIER.index("budget"),
            fin_dans_element=PREMIER.index("budget") + len("budget"),
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,
        )
        self.client.force_login(self.proprietaire)

    def test_le_swap_contient_les_blocs_et_non_le_html_de_l_ancien_moteur(self):
        reponse = self.client.post(
            "/extractions/panneau/", {"page_id": self.page.pk},

        )

        self.assertEqual(reponse.status_code, 200)
        corps = reponse.content.decode()
        self.assertIn('hx-swap-oob="innerHTML:#readability-content"', corps)
        self.assertIn('data-testid="blocs-elements"', corps,

    )

    def test_le_swap_conserve_les_ancres_de_l_extraction(self):
        # Sans blocs, le lecteur perd aussi ses surlignages : c'est la
        # preuve qui disparait. / Losing the blocks loses the evidence.
        reponse = self.client.post(
            "/extractions/panneau/", {"page_id": self.page.pk},

        )

        self.assertContains(reponse, "hl-extraction")
        self.assertContains(reponse, f'data-extraction-id="{self.extraction.pk}"',

    )

    def test_une_page_element_sans_bloc_retombe_sur_son_html(self):
        # Le repli honnete : une ingestion echouee n'a aucun bloc, on
        # rend le HTML readability. / Failed ingestion falls back.
        # (Les portions d'abord : `AncrageExtraction.element` est en
        # PROTECT. / Portions first: the FK is PROTECT.)
        AncrageExtraction.objects.filter(element__page=self.page).delete()
        self.page.elements.all().delete()

        reponse = self.client.post(
            "/extractions/panneau/", {"page_id": self.page.pk},

        )

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, PREMIER)
