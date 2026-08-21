"""
La fiche de preuve se lit comme une carte d'extraction.
/ The proof card reads like an extraction card.

LOCALISATION : front/tests/test_la_preuve_en_contexte.py

CE QUE CE CHANTIER CORRIGE, ET COMMENT ON L'A SU.

La fiche de preuve n'avait AUCUNE des marques qui font reconnaitre une
extraction ailleurs dans le produit : ni badge d'hypostase, ni resume
machine, ni indicateur de statut. Elle empilait en revanche, a la
meme taille et dans la meme couleur que la citation, une douzaine de
lignes sur la verification.

TROIS MESURES ONT DECIDE DE LA FORME.

1. **`.explication` etait INERTE dans le panneau.** La regle est
   `.zone-corpus .ecarte .explication`, or le panneau est HORS de
   `.zone-corpus`. Mesure au navigateur : la prose explicative rendait a
   **13,6px en `--encre`** — exactement la taille et la couleur de la
   citation. La preuve n'avait aucun avantage typographique sur son
   propre commentaire.

2. **La citation n'etait pas en Lora.** `.panneau-preuve` impose
   `font-family: Georgia`. La carte de lecture, elle, rend le resume en
   **B612 Mono 14px** et la citation en **Lora 16px** — mesure au
   navigateur. `maquette.css` tranche ce point : « la TYPOGRAPHIE suit
   la charte du projet et non le `ui-monospace` de l'etalon, qui n'est
   qu'un substitut pour rester autonome ».

3. **225 citations sur 225** portent des hypostases et un resume, avec
   **exactement 2 badges** chacune : aucune carte ne sera depareillee.

DEUX ARBITRAGES DU MAINTENEUR, qui ne sont ni des retards ni des oublis :

- **PAS DE MOTS-CLES.** L'etalon de cet ecran (`corpus.html`,
  `htmlDUneCartePreuve`) a deja arbitre ce qu'une carte de preuve
  contient — statut, badges, provenance, resume, citation, debat — et
  n'y met aucun hashtag. Precedent du 15 aout : quand l'etalon et le
  produit divergent, c'est l'etalon qui gagne.
- **TOUTE LA VERIFICATION EST DANS UN PLI**, dont le resume est l'etat
  lui-meme (« Faible ▸ »). La fiche montrait trop : le degre, son seuil,
  deux paragraphes didactiques et cinq juges s'affichaient avant meme
  qu'on les demande.
"""

import re

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AvisDeVerification, Configuration, ElementDocument, EtatDeVerification,
    Page, SourceLink, TypeDeNote, TypeLien,
)

TEXTE_DE_L_ELEMENT = (
    "Une phrase qui precede et qui sert de contexte. "
    "Le passage exactement cite. "
    "Une phrase qui suit et qui sert aussi de contexte."
)
CITATION = "Le passage exactement cite."


class BaseDeLaFicheDePreuve(TestCase):
    """Une citation ancree dans une note, avec ses quatre juges locaux."""

    def setUp(self):
        from hypostasis_extractor.models import (
            AncrageExtraction, ExtractedEntity, ExtractionJob,
        )

        self.utilisateur = get_user_model().objects.create_user(
            username="lecteur", password="motdepasse",
        )
        self.client.force_login(self.utilisateur)
        self.note = Page.objects.create(
            title="Badgeons la Normandie", owner=self.utilisateur,
            type_de_note=TypeDeNote.NOTE,
        )
        self.element = ElementDocument.objects.create(
            page=self.note, ordre=0, label="text",
            texte=TEXTE_DE_L_ELEMENT, empreinte_contenu="empreinte",
        )
        job = ExtractionJob.objects.create(page=self.note, status="completed")
        self.extraction = ExtractedEntity.objects.create(
            job=job, extraction_text=CITATION, extraction_class="hypostase",
            start_char=0, end_char=len(CITATION),
            attributes={
                "hypostases": "evenement, methode",
                "resume": "Création des Open Badges en 2011.",
                "statut": "",
                "mots_cles": "Open Badges, Mozilla",
            },
        )
        debut = TEXTE_DE_L_ELEMENT.index(CITATION)
        AncrageExtraction.objects.create(
            extraction=self.extraction, element=self.element,
            ordre_dans_extraction=0,
            debut_dans_element=debut, fin_dans_element=debut + len(CITATION),
        )
        texte = f"Une affirmation sourcée [[ext:{self.extraction.pk}]]."
        self.article = Page.objects.create(
            title="Article", owner=self.utilisateur, type_de_note=TypeDeNote.WIKI,
            text_readability=texte,
        )
        self.lien = SourceLink.objects.create(
            page_cible=self.article, extraction_source=self.extraction,
            type_lien=TypeLien.CITE,
            start_char_cible=0, end_char_cible=len(texte),
            score_de_verification=40.0,
            etat_de_verification=EtatDeVerification.FAIBLE,
            verifie_par="verbatim+nli-score v3 — Mistral Small",
        )
        Configuration.get_solo()

    def _poser_les_quatre_juges(self, version="xnli-directe v1"):
        for libelle, score in [
            ("bge-m3", 90.0), ("distilCamemBERT", 64.4),
            ("mDeBERTa v3", 50.0), ("CamemBERTa v2", 49.9),
        ]:
            AvisDeVerification.objects.create(
                lien=self.lien, methode=f"{version} — {libelle}",
                score=score, seuil=50.0,
            )

    def _fiche(self):
        return self.client.get(
            f"/citations/{self.lien.pk}/preuve/",
        ).content.decode()


class LaFicheEstUneCarteDExtraction(BaseDeLaFicheDePreuve):
    """La signature visuelle d'une extraction, dans le panneau."""

    def test_la_fiche_est_une_carte_de_preuve(self):
        """
        L'etalon veut une CARTE (filet, rayon, fond `--papier` sur un
        panneau `--papier-panneau`). La regle existait dans
        `_style_maquette.html` et aucun gabarit ne l'employait.
        / The rule existed; no template used it.
        """
        self.assertIn('class="carte-preuve"', self._fiche())

    def test_elle_porte_les_badges_d_hypostase_de_l_extraction(self):
        """
        C'est la marque qui fait reconnaitre une extraction d'un coup
        d'oeil dans le panneau des analyses. Elle manquait entierement.
        / The mark that makes an extraction recognisable at a glance.
        """
        contenu = self._fiche()

        self.assertEqual(
            contenu.count('data-testid="synthese-badge-hypostase"'), 2,
        )
        self.assertIn("evenement", contenu)
        self.assertIn("methode", contenu)

    def test_elle_porte_le_resume_machine(self):
        contenu = self._fiche()

        self.assertIn('data-testid="synthese-resume-machine"', contenu)
        self.assertIn("Création des Open Badges en 2011.", contenu)

    def test_elle_porte_l_indicateur_de_statut_de_debat(self):
        """
        Le cercle creux gris et le triangle orange sont daltonien-safe
        par la FORME. Ils restent dans leurs deux etats, comme dans
        l'etalon et dans la carte de lecture.
        / Both states are kept: the shape carries the meaning.
        """
        self.assertIn('class="indicateur-statut"', self._fiche())

    def test_elle_NE_porte_PAS_les_mots_cles(self):
        """
        ARBITRAGE DU MAINTENEUR, pas un oubli. `htmlDUneCartePreuve`
        (`corpus.html`) enumere ce qu'une carte de preuve contient, et
        n'y met aucun hashtag. Dans un panneau de 416px ils seraient du
        texte de plus sans geste attache.
        / A maintainer's call, not an omission.
        """
        contenu = self._fiche()

        self.assertNotIn('class="mot-cle"', contenu)
        self.assertNotIn("#Open Badges", contenu)

    def test_elle_ne_redit_PAS_le_mot_Preuve_en_titre(self):
        """
        L'entete du panneau (`article.html`) affiche deja « PREUVE » en
        capitales deux lignes plus haut. Le meme mot deux fois de suite
        n'apprend rien et coute une ligne.
        / The panel header already says PREUVE, two lines above.
        """
        self.assertNotIn("<h3", self._fiche())


class LaCitationEstMontreeDansSonContexte(BaseDeLaFicheDePreuve):
    """
    Une citation sortie de son paragraphe se lit mal, et parfois faux.
    / A quote pulled out of its paragraph reads badly, sometimes falsely.
    """

    def test_le_texte_d_avant_et_d_apres_encadrent_la_citation(self):
        contenu = self._fiche()

        self.assertIn('data-testid="synthese-contexte-avant"', contenu)
        self.assertIn('data-testid="synthese-contexte-apres"', contenu)
        self.assertIn("Une phrase qui precede", contenu)
        self.assertIn("Une phrase qui suit", contenu)

    def test_la_citation_reste_DISTINGUEE_de_son_contexte(self):
        """
        Sans marque propre, le lecteur ne sait plus ou finit la preuve
        et ou commence le decor. / Otherwise the reader cannot tell
        where the evidence stops and the setting starts.
        """
        contenu = self._fiche()

        self.assertIn('data-testid="synthese-citation-exacte"', contenu)
        self.assertIn(CITATION, contenu)

    def test_le_passage_vit_DANS_le_depliant_et_nulle_part_ailleurs(self):
        """
        C'est ce qui permet au CSS de ne montrer que la citation au
        repos. Un contexte pose HORS du `<details>` s'afficherait
        toujours, et la regle qui le cache ne l'atteindrait pas — sans
        qu'aucune erreur ne le signale.
        / This is what lets the CSS show the quote alone at rest: context
        placed outside the details would always show, silently.
        """
        contenu = self._fiche()

        depliant = contenu[
            contenu.index('class="passage-source"'):contenu.index("</details>")
        ]
        self.assertIn('data-testid="synthese-contexte-avant"', depliant)
        self.assertIn('data-testid="synthese-contexte-apres"', depliant)
        self.assertIn('data-testid="synthese-citation-exacte"', depliant)

    def test_une_ancre_DETACHEE_n_affiche_aucun_contexte(self):
        """
        Ses positions sont perimees : decouper le texte dessus
        fabriquerait un decor faux, presente comme une preuve.
        / Stale offsets would fabricate context and pass it off as proof.
        """
        self.extraction.ancrages.update(etat_ancrage="detachee")

        contenu = self._fiche()

        self.assertNotIn('data-testid="synthese-contexte-avant"', contenu)
        self.assertIn(CITATION, contenu)

    def test_la_source_est_annoncee_SOUS_le_texte_cite(self):
        """
        Le lien vivait au tout dernier rang, apres douze lignes de
        verification : le lecteur ne savait pas d'ou venait ce qu'il
        lisait au moment ou il le lisait.
        / The link sat last, after twelve lines of verification.
        """
        contenu = self._fiche()

        self.assertIn('data-testid="synthese-lien-source"', contenu)
        self.assertIn("Badgeons la Normandie", contenu)
        self.assertLess(
            contenu.index('data-testid="synthese-lien-source"'),
            contenu.index('data-testid="synthese-verification"'),
        )


class TouteLaVerificationTientDansUnPli(BaseDeLaFicheDePreuve):
    """
    Le degre, son seuil, les deux paragraphes didactiques et les cinq
    juges s'affichaient avant meme qu'on les demande.
    / All of it used to show before anyone asked.
    """

    def test_le_degre_et_les_juges_sont_DANS_le_depliant(self):
        self._poser_les_quatre_juges()

        contenu = self._fiche()

        self.assertIn('data-testid="synthese-verification"', contenu)
        debut_du_pli = contenu.index('data-testid="synthese-verification"')
        self.assertLess(debut_du_pli, contenu.index('data-testid="synthese-degre"'))
        self.assertLess(
            debut_du_pli, contenu.index('data-testid="synthese-avis-locaux"'),
        )

    def test_le_resume_du_pli_est_l_ETAT_lui_meme(self):
        """
        « Faible » n'est pas un libelle de plus : c'est le verdict. Le
        poser en resume du depliant garde le signal visible et range le
        detail. / The state IS the summary: signal visible, detail filed.
        """
        contenu = self._fiche()

        self.assertIn('data-testid="synthese-etat-verification"', contenu)
        # Le resume DU PLI DE VERIFICATION, pas le premier `<summary>` de
        # la fiche : celui du passage vient avant lui.
        # / The verification fold's summary, not the card's first one.
        depliant = contenu[contenu.index('class="verification"'):]
        resume = depliant[
            depliant.index("<summary"):depliant.index("</summary>")
        ]
        self.assertIn('data-testid="synthese-etat-verification"', resume)

    def test_sans_degre_NI_avis_l_etat_n_est_pas_replie(self):
        """
        Replier une seule ligne — « pas encore verifie : utilisez
        Verifier les citations » — cacherait une consigne derriere un
        chevron, sans rien ranger.
        / Folding one actionable line hides an instruction for nothing.
        """
        self.lien.score_de_verification = None
        self.lien.etat_de_verification = EtatDeVerification.NON_VERIFIE
        self.lien.verifie_par = ""
        self.lien.save()

        contenu = self._fiche()

        self.assertIn('data-testid="synthese-etat-verification"', contenu)
        self.assertNotIn('data-testid="synthese-verification"', contenu)
        self.assertIn("Pas encore vérifié", contenu)

    def test_une_citation_INTROUVABLE_n_est_pas_dite_non_verifiee(self):
        """
        DEUX CAS TOMBENT DANS LA MEME BRANCHE, et un seul est « pas
        encore vérifié ». Une citation introuvable A ETE JUGEE — le
        degré est absent pour tout verdict posé SANS juge. Lui proposer
        « utilisez Vérifier les citations » ferait relancer un juge qui
        a déjà répondu, et effacerait le verdict.
        / Both land here; only one of them is unverified.
        """
        self.lien.score_de_verification = None
        self.lien.etat_de_verification = EtatDeVerification.INTROUVABLE
        self.lien.verifie_par = "verbatim+nli-score v3 — Mistral Small"
        self.lien.save()

        contenu = self._fiche()

        self.assertNotIn("Pas encore vérifié", contenu)
        self.assertIn("Rendu par", contenu)
        self.assertIn("verbatim+nli-score v3 — Mistral Small", contenu)


class ChaqueBarreDitQuiParleAVANTDeDireCombien(BaseDeLaFicheDePreuve):
    """
    Les avis sont tries PAR SCORE DECROISSANT (`views_synthese.py`) :
    l'ordre des barres change d'une citation a l'autre, donc l'identite
    positionnelle n'existe pas. Le nom du juge est obligatoire, et il
    doit venir en tete — sinon il faut lire cinq phrases jusqu'au bout
    pour savoir qui dit quoi.
    / Opinions are sorted by score, so bar position means nothing.
    """

    def test_chaque_barre_nomme_son_juge_dans_un_element_dedie(self):
        self._poser_les_quatre_juges()

        contenu = self._fiche()

        # Quatre juges locaux, plus le juge de reference.
        # / Four local judges, plus the reference judge.
        self.assertEqual(
            contenu.count('data-testid="synthese-nom-du-juge"'), 5,
        )
        self.assertIn("bge-m3", contenu)
        self.assertIn("CamemBERTa v2", contenu)

    def test_la_version_COMMUNE_aux_juges_n_est_ecrite_QU_UNE_FOIS(self):
        """
        « xnli-directe v1 — » etait recopie sur les quatre lignes : il
        n'identifie personne, il remplit. Il sort de la LIGNE VISIBLE
        pour aller une fois en pied.
        / Identical on all four: it fills, it does not identify.

        CE QUI RESTE, ET DELIBEREMENT : `data-methode` et l'`aria-label`
        portent l'identite COMPLETE du juge sur chaque barre. § 7.2 —
        l'etat porte son verificateur. Un lecteur d'ecran navigue barre
        par barre, sans coup d'oeil au pied : chaque barre doit se
        decrire seule. / The full identity stays in the data attribute
        and the aria-label: a screen reader has no footer at a glance.
        """
        self._poser_les_quatre_juges()

        contenu = self._fiche()

        self.assertEqual(
            contenu.count('data-testid="synthese-version-commune"'), 1,
        )
        self.assertNotIn('class="version-du-juge"', contenu)

    def test_des_versions_DIFFERENTES_restent_sur_chaque_ligne(self):
        """
        § 7.2 : l'etat porte son verificateur — modele, VERSION, date,
        seuil. Factoriser une version qui n'est pas commune mentirait
        sur trois des quatre juges.
        / Factoring out a version that is not shared would lie.
        """
        AvisDeVerification.objects.create(
            lien=self.lien, methode="xnli-directe v1 — bge-m3",
            score=90.0, seuil=50.0,
        )
        AvisDeVerification.objects.create(
            lien=self.lien, methode="xnli-par-phrase v2 — CamemBERTa v2",
            score=49.9, seuil=50.0,
        )

        contenu = self._fiche()

        self.assertNotIn('data-testid="synthese-version-commune"', contenu)
        self.assertIn("xnli-directe v1", contenu)
        self.assertIn("xnli-par-phrase v2", contenu)

    def test_le_juge_de_reference_est_SEPARE_des_quatre_locaux(self):
        """
        Cinq barres identiques feraient croire a cinq juges egaux, alors
        qu'un avis local se lit A COTE du juge de production, jamais a
        sa place (`core/models.py`).
        / Five identical bars would suggest five equal judges.
        """
        self._poser_les_quatre_juges()

        contenu = self._fiche()

        self.assertIn('data-testid="synthese-barre-juge-de-production"', contenu)
        self.assertIn('class="separateur-des-locaux"', contenu)


class LesPreuvesSontToutesDansLaPage(BaseDeLaFicheDePreuve):
    """
    LE TIROIR EST MORT. Les fiches se chargeaient UNE PAR UNE dans un
    panneau `position: fixed` pose sur un voile qui grisait l'article :
    ouvrir une preuve rendait illisible la phrase qu'on verifiait, et on
    perdait la fiche precedente. Or verifier, c'est comparer
    l'affirmation et sa source — donc les avoir sous les yeux ensemble.
    / The drawer is dead: verifying means having claim and source in
    view at the same time.
    """

    def _article(self):
        return self.client.get(f"/syntheses/{self.article.pk}/").content.decode()

    def setUp(self):
        super().setUp()
        # L'article doit etre une SYNTHESE pour que /syntheses/<pk>/ le serve.
        # / The article must be a SYNTHESE for that route to serve it.
        self.article.type_de_note = TypeDeNote.SYNTHESE
        self.article.save(update_fields=["type_de_note"])

    def test_la_fiche_est_rendue_DANS_la_page_de_l_article(self):
        contenu = self._article()

        self.assertIn('data-testid="synthese-panneau-preuve"', contenu)
        self.assertIn('data-testid="synthese-preuve"', contenu)
        self.assertIn(CITATION, contenu)

    def test_il_n_y_a_PLUS_de_voile_qui_grise_l_article(self):
        """Le voile est ce qui empechait de lire les deux a la fois."""
        contenu = self._article()

        self.assertNotIn("voile-preuve", contenu)

    def test_le_renvoi_est_une_ANCRE_vers_sa_fiche(self):
        """
        Sans JavaScript, le navigateur saute a la fiche. Le script
        n'ajoute que le defilement doux et le surlignage.
        / Without JS the browser still reaches the card.
        """
        contenu = self._article()

        self.assertIn(f'href="#preuve-{self.lien.pk}"', contenu)
        self.assertIn(f'id="preuve-{self.lien.pk}"', contenu)

    def test_le_renvoi_ne_charge_plus_la_preuve_en_HTMX(self):
        contenu = self._article()

        self.assertNotIn(f'hx-get="/citations/{self.lien.pk}/preuve/"', contenu)

    def test_la_fiche_porte_le_NUMERO_du_renvoi(self):
        """
        Une colonne de soixante fiches ne se raccroche a rien sans lui.
        / Sixty cards with no number tie back to nothing.
        """
        contenu = self._article()

        self.assertIn('data-testid="synthese-numero-de-renvoi"', contenu)
        self.assertIn("[1]", contenu)

    def test_une_extraction_citee_DEUX_FOIS_donne_DEUX_fiches(self):
        """
        Meme numero aux deux endroits — comme une bibliographie — mais
        DEUX SourceLink, donc deux verdicts et deux fiches. Un `id` bati
        sur le numero en rendrait une inatteignable.
        / One number, two links, two verdicts, two cards.
        """
        from core.services.synthese import indexer_les_citations

        marqueur = f"[[ext:{self.extraction.pk}]]"
        bilan = indexer_les_citations(
            self.article,
            f"Une affirmation.{marqueur}\n\nUne autre.{marqueur}\n",
            None,
        )
        self.article.text_readability = bilan["texte_nettoye"]
        self.article.save(update_fields=["text_readability"])

        contenu = self._article()

        self.assertEqual(contenu.count('data-testid="synthese-preuve"'), 2)
        # Le meme numero aux deux endroits, deux ancres distinctes.
        # / Same number, two distinct anchors.
        identifiants = set(re.findall(r'id="preuve-(\d+)"', contenu))
        self.assertEqual(len(identifiants), 2)

    def test_un_article_sans_aucune_citation_le_dit(self):
        """Une colonne vide sans un mot serait une panne muette."""
        self.lien.delete()
        self.article.text_readability = "Une affirmation sans source."
        self.article.save(update_fields=["text_readability"])

        contenu = self._article()

        self.assertIn('data-testid="synthese-aucune-preuve"', contenu)


class LaColonneNeFaitPasUneRequETEParFICHE(BaseDeLaFicheDePreuve):
    """
    RENDRE SOIXANTE FICHES NE DOIT PAS COUTER SOIXANTE FOIS UNE FICHE.

    Mesure du 20 aout sur l'article de demonstration — 63 citations,
    6 notes sources : la premiere version de la colonne faisait
    **213 requetes en 0,91 s**. Trois N+1 s'y cachaient, et aucun ne se
    voyait a la lecture du code :

    · `.order_by()` sur un manager lie CONSTRUIT UN NOUVEAU QUERYSET et
      ignore le cache du `prefetch_related` — 64 requetes d'ancrages ;
    · l'element voisin etait cherche en base pour chaque fiche —
      65 requetes pour 6 notes ;
    · `accord_des_juges_locaux` relisait la `Configuration` a chaque
      appel — 59 requetes pour une valeur qui ne change pas.

    Apres correction : **32 requetes en 0,40 s**. Ce test existe pour
    que la prochaine session ne les reintroduise pas sans le voir.
    / Sixty cards must not cost sixty times one card.
    """

    def test_le_nombre_de_requetes_ne_croit_pas_avec_les_citations(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from core.services.synthese import indexer_les_citations

        self.article.type_de_note = TypeDeNote.SYNTHESE
        self.article.save(update_fields=["type_de_note"])
        marqueur = f"[[ext:{self.extraction.pk}]]"

        def _compter(nombre_de_citations):
            bilan = indexer_les_citations(
                self.article,
                "".join(
                    f"Affirmation {rang}.{marqueur}\n\n"
                    for rang in range(nombre_de_citations)
                ),
                None,
            )
            self.article.text_readability = bilan["texte_nettoye"]
            self.article.save(update_fields=["text_readability"])
            # Un premier appel pour ecarter les requetes de session et de
            # migration. / A warm-up call to shed session queries.
            self.client.get(f"/syntheses/{self.article.pk}/")
            with CaptureQueriesContext(connection) as requetes:
                self.client.get(f"/syntheses/{self.article.pk}/")
            return len(requetes)

        avec_deux = _compter(2)
        avec_douze = _compter(12)

        # Dix citations de plus ne doivent pas coûter dix requêtes de
        # plus. La marge tolère les comptes d'en-tête, pas un N+1.
        # / Ten more citations must not cost ten more queries.
        self.assertLess(
            avec_douze, avec_deux + 5,
            f"{avec_deux} requêtes pour 2 citations, {avec_douze} pour 12 : "
            "le coût croît avec le nombre de fiches, un N+1 est revenu",
        )


class LeLienVersLaSource(BaseDeLaFicheDePreuve):

    def test_il_s_ouvre_A_COTE_et_non_a_la_place(self):
        """
        Le lecteur verifie une synthese : quitter la page lui ferait
        perdre l'endroit ou il en etait, et la colonne avec.
        `rel="noopener"` va toujours avec `target="_blank"` — sans lui,
        la page ouverte peut rediriger celle-ci.
        / Leaving the page would lose the reader's place.
        """
        contenu = self._fiche()

        self.assertIn('target="_blank"', contenu)
        self.assertIn('rel="noopener"', contenu)

    def test_il_annonce_le_nombre_de_commentaires(self):
        from hypostasis_extractor.models import CommentaireExtraction

        CommentaireExtraction.objects.create(
            entity=self.extraction, user=self.utilisateur,
            commentaire="Un commentaire.",
        )

        contenu = self._fiche()

        self.assertIn("Voir la source", contenu)
        self.assertIn("1 commentaire", contenu)

    def test_sans_commentaire_il_n_annonce_pas_un_zero(self):
        """« Voir la source, 0 commentaire » serait du bruit."""
        contenu = self._fiche()

        self.assertIn("Voir la source", contenu)
        self.assertNotIn("0 commentaire", contenu)


class LeCompteurDeCommentairesCompteLaSource(BaseDeLaFicheDePreuve):
    """
    Le compteur et l'indicateur de statut parlent des commentaires de
    l'EXTRACTION SOURCE — les memes que le bloc « debat » plus bas, et
    les memes que la carte de la vue de lecture. `statut_debat` en est
    derive par un signal, jamais pose a la main.
    / Counter and status indicator both speak of the source extraction's
    comments, the very ones the debate block lists.
    """

    def test_sans_commentaire_aucun_compteur(self):
        self.assertNotIn(
            'data-testid="synthese-compteur-commentaires"', self._fiche(),
        )

    def test_avec_commentaires_le_compteur_les_compte(self):
        from hypostasis_extractor.models import CommentaireExtraction

        for propos in ("Un premier avis.", "Un second avis."):
            CommentaireExtraction.objects.create(
                entity=self.extraction, user=self.utilisateur,
                commentaire=propos,
            )

        contenu = self._fiche()

        self.assertIn('data-testid="synthese-compteur-commentaires"', contenu)
        self.assertIn("2 commentaires sur l'extraction source", contenu)

    def test_l_indicateur_de_statut_suit_les_memes_commentaires(self):
        from hypostasis_extractor.models import CommentaireExtraction

        CommentaireExtraction.objects.create(
            entity=self.extraction, user=self.utilisateur,
            commentaire="Un avis.",
        )

        self.assertIn('data-statut="commente"', self._fiche())


class LEtatEstDANSLaCarte(BaseDeLaFicheDePreuve):
    """
    Le pli de verification etait un frere de la carte, pose dessous : il
    flottait entre deux fiches sans dire a laquelle il appartenait.
    / The fold used to float between cards, belonging to neither.
    """

    def test_le_pli_de_verification_est_a_l_interieur_de_la_carte(self):
        self._poser_les_quatre_juges()

        contenu = self._fiche()

        debut_de_la_carte = contenu.index('class="carte-preuve"')
        fin_de_la_carte = contenu.index("</article>")
        pli = contenu.index('data-testid="synthese-verification"')
        self.assertLess(debut_de_la_carte, pli)
        self.assertLess(pli, fin_de_la_carte)


class LeDebatSuitLaGrammaireDeLEtalon(BaseDeLaFicheDePreuve):
    """
    Le debat sortait en `<ul class="list-disc ml-4">` — des utilitaires
    Tailwind, hors du systeme. La grammaire `.debat .qui` existe et est
    DEJA stylee dans `_style_maquette.html`.
    / The rule already existed; the template used Tailwind instead.
    """

    def _commenter(self, qui, quoi):
        from hypostasis_extractor.models import CommentaireExtraction

        return CommentaireExtraction.objects.create(
            entity=self.extraction,
            user=get_user_model().objects.create_user(
                username=qui, password="motdepasse",
            ),
            commentaire=quoi,
        )

    def test_chaque_commentaire_nomme_son_auteur_dans_un_span_qui(self):
        self._commenter("amina", "Un avenant écrit a été chiffré.")

        contenu = self._fiche()

        self.assertIn('data-testid="synthese-debat"', contenu)
        self.assertIn('class="qui"', contenu)
        self.assertIn("amina", contenu)
        self.assertIn("Un avenant écrit a été chiffré.", contenu)

    def test_le_debat_n_emploie_plus_d_utilitaires_Tailwind(self):
        self._commenter("sonia", "Je conteste ce passage.")

        self.assertNotIn('class="list-disc ml-4"', self._fiche())
