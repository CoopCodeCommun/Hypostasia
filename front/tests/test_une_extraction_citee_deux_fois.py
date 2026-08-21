"""
Une MÊME extraction citée dans DEUX paragraphes : deux renvois distincts.
/ One extraction cited in TWO paragraphs: two distinct references.

LOCALISATION : front/tests/test_une_extraction_citee_deux_fois.py

LE DÉFAUT QUE CE FICHIER VERROUILLE, ET IL ÉTAIT SILENCIEUX.

`_html_avec_renvois` remplaçait chaque marqueur par un jeton
`RENVOIJETON{numero}X{identifiant}FIN` — construit sur **l'extraction
seule**, jamais sur le paragraphe. Quand une extraction était citée deux
fois :

1. les deux marqueurs produisaient le **même** jeton ;
2. `jetons[jeton] = …` n'en gardait que **le dernier lien** ;
3. `str.replace(jeton, …)` remplaçait **les deux** occurrences par ce
   dernier lien.

**Le lecteur cliquait le renvoi du premier paragraphe et obtenait la
preuve du second** — autres bornes, autre statut de vérification. Et le
`SourceLink` du premier paragraphe n'était atteignable par AUCUN chemin.

Mesuré le 19 août 2026 sur la base de démonstration : sur le wiki des
open badges, **4 citations sur 61 n'étaient jamais rendues**, et 4 autres
l'étaient deux fois. Les huit portaient les mêmes quatre extractions.

Dans un outil dont l'objet est la traçabilité, montrer une preuve pour
une autre est le pire défaut possible : rien ne le signale.
/ The token keyed on the extraction alone, so a twice-cited extraction
rendered one link twice and left the other unreachable.

CE QUI RESTE INCHANGÉ, ET C'EST VOULU : le NUMÉRO affiché `[N]` suit
l'extraction, pas le paragraphe. Une même source citée deux fois porte
donc le même numéro aux deux endroits — c'est une numérotation de
bibliographie. Seule la CIBLE du renvoi doit différer.
/ The displayed number still follows the extraction; only the target differs.
"""

import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Dossier, Page, SourceLink, TypeDeNote, TypeLien, VisibiliteDossier, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from core.services.synthese import indexer_les_citations
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()

TEXTE_DE_LA_SOURCE = (
    "Le compte rendu note que le seuil de dix mille euros déclenche le "
    "passage en assemblée, et que le quorum reste inchangé."
)


class UneExtractionCiteeDeuxFoisTest(TestCase):
    """Deux paragraphes, une seule source : deux renvois, deux cibles."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            "proprio_deux_fois", "pdf@exemple.test", "motdepasse123",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet des renvois", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        note_source = Page.objects.create(
            url="http://exemple.local/deux-fois-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-deux-fois-source", title="Compte rendu",
        )
        job = ExtractionJob.objects.create(
            page=note_source, name="Analyse deux fois", status="completed",
            ai_model=None,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=job, extraction_class="donnee",
            extraction_text=(
                "le seuil de dix mille euros déclenche le passage en assemblée"
            ),
            start_char=0, end_char=60,
        )
        self.article = Page.objects.create(
            title="Wiki — une source, deux paragraphes",
            type_de_note=TypeDeNote.WIKI, owner=self.proprietaire,
            content_hash="hash-deux-fois-article",
            html_readability="<p>provisoire</p>",
            text_readability="provisoire", html_original="",
        )
        ranger_une_note_dans_un_carnet(
            self.article, self.carnet, utilisateur=self.proprietaire,
        )
        Wiki.objects.create(
            page=self.article, dossier=self.carnet, sujet="renvois",
        )

        # DEUX paragraphes qui citent LA MÊME extraction — le cas exact
        # qui perdait une citation. / Two paragraphs, one extraction.
        marqueur = f"[[ext:{self.extraction.pk}]]"
        markdown = (
            f"Le seuil de convocation est fixé.{marqueur}\n\n"
            f"Ce même seuil vaut pour les délibérations.{marqueur}\n"
        )
        bilan = indexer_les_citations(self.article, markdown, None)
        self.article.text_readability = bilan["texte_nettoye"]
        self.article.save(update_fields=["text_readability"])

    def _renvois(self):
        """
        Les identifiants de lien portés par les renvois rendus.

        Chaque renvoi est une ancre vers SA fiche dans la colonne des
        preuves : `href="#preuve-<pk>"`, avec le même `pk` en
        `data-lien-id`. C'est ce `pk` qu'on relève ici — l'identité de
        la citation, pas celle de l'extraction.
        / Each reference anchors to its own card by SourceLink pk.
        """
        from front.views_synthese import _html_avec_renvois

        html = _html_avec_renvois(self.article)
        return re.findall(r'data-lien-id="(\d+)"', html)

    def test_deux_paragraphes_donnent_DEUX_liens_distincts(self):
        """
        LE CŒUR DU DÉFAUT. Deux citations en base, deux renvois à
        l'écran, et surtout : DEUX CIBLES DIFFÉRENTES.
        / Two citations, two references, two distinct targets.
        """
        liens = list(
            SourceLink.objects.filter(
                page_cible=self.article, type_lien=TypeLien.CITE,
            ).order_by("start_char_cible")
        )
        self.assertEqual(len(liens), 2, "l'indexation doit poser 2 liens")

        cibles = self._renvois()

        self.assertEqual(len(cibles), 2, "deux renvois doivent être rendus")
        self.assertEqual(
            len(set(cibles)), 2,
            "les deux renvois doivent viser DEUX liens différents ; un seul "
            "id signifie qu'une citation est devenue inatteignable",
        )

    def test_aucune_citation_n_est_laissee_sans_renvoi(self):
        """
        Chaque `SourceLink` doit être atteignable. Une citation sans
        renvoi est une preuve que le lecteur ne peut pas ouvrir — donc
        une source qui n'existe pas pour lui.
        / Every SourceLink must be reachable.
        """
        attendus = set(
            str(pk) for pk in SourceLink.objects.filter(
                page_cible=self.article, type_lien=TypeLien.CITE,
            ).values_list("pk", flat=True)
        )

        self.assertEqual(set(self._renvois()), attendus)

    def test_le_NUMERO_reste_celui_de_l_extraction(self):
        """
        CE QUI NE DOIT PAS CHANGER. Le numéro affiché suit l'extraction,
        pas le paragraphe : une même source citée deux fois porte le
        même `[1]` aux deux endroits, comme une bibliographie.
        / The displayed number still follows the extraction.
        """
        from front.views_synthese import _html_avec_renvois

        html = _html_avec_renvois(self.article)

        self.assertEqual(html.count('aria-label="Source 1"'), 2)
        self.assertNotIn('aria-label="Source 2"', html)
