"""
Justesse semantique de l'extraction, mesuree par famille epistemique.
/ Semantic accuracy of extraction, measured by epistemic family.

LOCALISATION : hypostasis_extractor/tests/test_justesse_semantique_llm.py

CE TEST NE TOURNE PAS PAR DEFAUT — voir test_analyse_llm_reel.py, meme
double verrou : le tag « llm_reel » ET la variable TESTS_LLM_REELS.

    docker exec -w /app -e POSTGRES_DB=hypostasia_<nom> \\
        -e TESTS_LLM_REELS=1 hypostasia_web \\
        uv run python manage.py test \\
        hypostasis_extractor.tests.test_justesse_semantique_llm --tag=llm_reel

CE QU'IL MESURE, QUE LES AUTRES NE MESURENT PAS

`test_analyse_llm_reel.py` eprouve la MECANIQUE de la jonction avec
LangExtract : les spans rendus pointent le bon texte, une extraction
longue produit plusieurs portions. Il est vert meme si le modele classe
« croyance » un releve de temperature — il ne regarde pas ce que
l'etiquette veut dire.

Ce test-ci regarde justement cela : le modele met-il les passages dans la
bonne case ? C'est la seule chose qui puisse attraper une REGRESSION DE
PROMPT. Si quelqu'un remanie
`PIECE_DE_DEFINITIONS_DE_L_EXTRACTION`, casse une famille, ou reduit
l'exemple few-shot, toute la mecanique reste verte et les extractions
deviennent silencieusement fausses.

POURQUOI PAR FAMILLE, ET NON PAR HYPOSTASE

Exiger l'hypostase exacte ferait de ce test une loterie. Separer
« donnee » de « variance », ou « conjecture » de « hypothese », est
difficile pour un humain informe : ce sont des voisines de la meme
region epistemique, et le desaccord entre deux annotateurs y est la
regle. Un test qui l'exigerait tomberait au hasard des jours et on
finirait par le desactiver.

La FAMILLE, elle, est un jugement grossier et robuste. Confondre la
famille 5 (« ce qu'on constate sans pouvoir l'expliquer » : donnee,
phenomene, indice) avec la famille 6 (« ce qu'on propose sans pouvoir le
confirmer » : hypothese, methode, definition) n'est pas une nuance
d'annotateur : c'est ne pas avoir compris le texte. Un modele qui garde
la bonne famille reste utilisable meme quand il hesite a l'interieur ;
un modele qui perd la famille rend un resultat inexploitable.

/ Requiring the exact hypostase would make this a lottery: neighbours
within one family are genuinely hard to separate. The family is a coarse,
robust judgement — losing it means the text was not understood.

LE SEUIL, ET POURQUOI IL EST BAS

60 % des passages classes dans la bonne famille. C'est volontairement
loin de 100 % : le but n'est pas de noter le modele, c'est d'attraper un
effondrement. Un prompt casse fait chuter ce score bien en dessous de la
moitie ; un bon jour et un mauvais jour se tiennent tous deux largement
au-dessus. Entre les deux, la marge est assez large pour que le test ne
clignote pas.
/ The threshold is deliberately far from 100%: it catches a collapse, it
does not grade the model.
"""

import os

from django.test import TestCase, tag

from core.models import ElementDocument, Page, empreinte_du_texte
from front.services.fixtures_analyseurs import (
    NOM_DE_L_ANALYSEUR_D_EXTRACTION,
    creer_les_modeles_ia_et_les_analyseurs,
)
from hypostasis_extractor.models import (
    AnalyseurSyntaxique,
    ExtractionJob,
    ExtractionJobStatus,
)
from hypostasis_extractor.services.analyse_par_element import (
    lancer_l_analyse_d_une_page,
)
from hypostasis_extractor.tests.test_referentiel_des_hypostases import (
    _familles_du_prompt,
)

# Part minimale de passages devant tomber dans la bonne famille.
# / Minimum share of passages that must land in the right family.
SEUIL_DE_CONCORDANCE = 0.60

# Part minimale de passages devant recevoir au moins une extraction.
# Sans ce garde-fou, un modele qui ne rend qu'UN passage bien classe
# afficherait 100 % de concordance : le score serait excellent et le
# pipeline pourtant inutilisable.
# / Without this guard, a model returning a single well-classified
# passage would score 100% while being useless.
SEUIL_DE_COUVERTURE = 0.50

# Les passages d'epreuve : courts, autonomes, et choisis pour que leur
# famille ne se discute pas. Chacun devient un ElementDocument distinct,
# ce qui permet de savoir, a la lecture des ancres, quelle extraction
# parle de quel passage.
#
# On evite deliberement les passages « limites ». Le test ne cherche pas
# a savoir si le modele arbitre finement, mais s'il a compris de quel
# ordre de discours releve la phrase.
# / Deliberately unambiguous passages, one ElementDocument each so
# anchors tell us which extraction speaks about which passage.
PASSAGES_D_EPREUVE = [
    # --- Famille 2 : ce qui se produit, sans cadre formel ---
    # (evenement, variation, dimension, mode, croyance)
    (
        "Le 12 mars 2025, un incendie a entierement detruit l'entrepot "
        "principal de la cooperative agricole de la vallee.",
        2,
        "un fait date et singulier : un evenement",
    ),
    # Ce passage a remplace une formulation chiffree (« la frequentation a
    # baisse de moitie entre 2020 et 2025 »). Elle visait « variation »,
    # mais un passage qui porte un chiffre appelle legitimement
    # « donnee » — famille 5. Le modele la classait donc famille 5, et il
    # avait autant raison que le test. Un passage d'epreuve doit avoir UNE
    # lecture defendable : le defaut etait dans le passage, pas dans le
    # modele. « sont convaincus que » ne se lit, lui, que comme croyance.
    # / A figure-bearing passage legitimately invites "donnee"; the flaw
    # was in the probe, not in the model.
    (
        "De nombreux agriculteurs sont convaincus que les semences "
        "anciennes resistent mieux a la secheresse, sans qu'aucune etude "
        "ne l'ait jamais montre.",
        2,
        "une conviction qui fait tenir une chose pour vraie : une croyance",
    ),
    # --- Famille 3 : ce qu'on formalise sans pouvoir le verifier ---
    # (invariant, valeur, structure, axiome, conjecture)
    (
        "Toute personne accusee est presumee innocente tant que sa "
        "culpabilite n'a pas ete legalement etablie.",
        3,
        "une proposition admise au depart : un axiome",
    ),
    (
        "La cooperative s'organise en trois echelons : les sections "
        "locales, le conseil de gestion et l'assemblee generale.",
        3,
        "l'organisation des parties d'un systeme : une structure",
    ),
    # --- Famille 5 : ce qu'on constate sans pouvoir l'expliquer ---
    # (phenomene, variable, variance, indice, donnee)
    (
        "Les releves de la station meteorologique indiquent une "
        "temperature moyenne de 14,2 degres sur l'annee 2025.",
        5,
        "un releve chiffre qui sert a raisonner : une donnee",
    ),
    (
        "On observe depuis trois ans une disparition progressive des "
        "abeilles dans les vergers, sans que personne sache l'expliquer.",
        5,
        "ce qui se manifeste aux sens sans explication : un phenomene",
    ),
    # --- Famille 6 : ce qu'on propose sans pouvoir le confirmer ---
    # (methode, definition, hypothese, probleme, theorie)
    (
        "On entend par circuit court toute vente comportant au plus un "
        "intermediaire entre le producteur et le consommateur.",
        6,
        "la caracterisation du contenu d'un concept : une definition",
    ),
    (
        "La procedure consiste a prelever trois echantillons, a les "
        "filtrer, puis a les analyser en laboratoire sous quarante-huit heures.",
        6,
        "une procedure qui indique comment faire : une methode",
    ),
    (
        "Si les aides europeennes etaient versees des le printemps, la "
        "tresorerie des exploitations pourrait cesser de se degrader.",
        6,
        "une explication possible, non verifiee : une hypothese",
    ),
    (
        "Le probleme central reste l'absence de financement perenne pour "
        "l'entretien du reseau d'irrigation.",
        6,
        "une difficulte a resoudre : un probleme",
    ),
]


@tag("llm_reel")
class JustesseSemantiqueParFamilleTest(TestCase):
    """
    Le modele range-t-il les passages dans la bonne famille epistemique ?
    / Does the model file passages under the right epistemic family?
    """

    def setUp(self):
        # Meme double verrou que test_analyse_llm_reel.py : le tag seul ne
        # protege pas, Django n'exclut aucun tag par defaut.
        # / Same double lock: a tag alone protects nothing.
        if not os.environ.get("TESTS_LLM_REELS"):
            self.skipTest(
                "TESTS_LLM_REELS non definie : test d'appel LLM reel ignore.",
            )
        if not os.environ.get("GOOGLE_API_KEY"):
            self.skipTest(
                "GOOGLE_API_KEY absente : ce test a besoin d'un vrai "
                "fournisseur LLM.",
            )

        # L'ANALYSEUR DE PRODUCTION, PAS UN ANALYSEUR DE TEST.
        #
        # C'est tout l'interet : ce test doit eprouver le prompt qu'on
        # livre — ses 30 definitions classees par famille et ses 30
        # exemples few-shot. Un analyseur bricole pour l'occasion ne
        # dirait rien d'une regression du prompt reel.
        # / The shipped analyzer, not a test one: a hand-made analyzer
        # would say nothing about a regression of the real prompt.
        rapport_des_fixtures = creer_les_modeles_ia_et_les_analyseurs()
        self.assertFalse(
            rapport_des_fixtures["aucune_cle_api_detectee"],
            "Aucun modele IA n'a pu etre cree malgre GOOGLE_API_KEY.",
        )
        self.analyseur_de_production = AnalyseurSyntaxique.objects.get(
            name=NOM_DE_L_ANALYSEUR_D_EXTRACTION,
        )

        self.page_d_epreuve = Page.objects.create(
            url="http://exemple.local/justesse-semantique",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="empreinte_justesse",
        )

        # Un element par passage : c'est ce qui rend le score calculable.
        # / One element per passage: this is what makes the score computable.
        self.famille_attendue_par_element = {}
        for numero_du_passage, (texte, famille_attendue, _pourquoi) in enumerate(
            PASSAGES_D_EPREUVE,
        ):
            element = ElementDocument.objects.create(
                page=self.page_d_epreuve, ordre=numero_du_passage, label="text",
                texte=texte, empreinte_contenu=empreinte_du_texte(texte),
            )
            self.famille_attendue_par_element[element.pk] = famille_attendue

        # ATTENTION : c'est model_choice qui decide du provider reel.
        # `creer_les_modeles_ia_et_les_analyseurs` a deja pose le bon
        # AIModel a partir de la cle presente dans l'environnement ; on le
        # reprend tel quel plutot que d'en fabriquer un, sous peine de
        # partir sur le provider MOCK sans appeler personne.
        # / The service already created the right AIModel from the env key;
        # building another one risks silently landing on the MOCK provider.
        self.modele_ia = rapport_des_fixtures["modele_ia_de_la_configuration"]
        self.assertIsNotNone(
            self.modele_ia, "Aucun modele IA disponible pour l'appel reel.",
        )

        self.job = ExtractionJob.objects.create(
            page=self.page_d_epreuve,
            ai_model=self.modele_ia,
            name="Mesure de justesse semantique",
            prompt_description="Extraire l'ossature argumentative du texte.",
            raw_result={"analyseur_id": self.analyseur_de_production.pk},
        )

    def _famille_de_chaque_hypostase(self):
        """
        {nom d'hypostase normalise: numero de famille}, lu dans le prompt.
        / {normalized hypostase name: family number}, read from the prompt.

        La table est derivee du prompt lui-meme plutot que recopiee ici :
        une seconde copie du referentiel serait exactement le probleme que
        test_referentiel_des_hypostases.py surveille.
        / Derived from the prompt rather than copied: a second copy would
        be the very problem the reference test guards against.
        """
        famille_par_hypostase = {}
        for numero_de_famille, contenu in _familles_du_prompt().items():
            for nom_d_hypostase, _mode in contenu["hypostases"]:
                famille_par_hypostase[nom_d_hypostase] = numero_de_famille
        return famille_par_hypostase

    def test_les_passages_sont_classes_dans_la_bonne_famille_epistemique(self):
        resultat = lancer_l_analyse_d_une_page(self.page_d_epreuve, self.job)

        self.job.refresh_from_db()
        self.assertEqual(
            self.job.status, ExtractionJobStatus.COMPLETED,
            f"L'analyse a echoue : {self.job.error_message}",
        )
        self.assertGreater(
            resultat["extractions"], 0,
            "Le modele n'a rien extrait : la justesse n'est pas mesurable.",
        )

        famille_par_hypostase = self._famille_de_chaque_hypostase()

        # Pour chaque passage, on retient les familles de toutes les
        # hypostases que le modele lui a attribuees. Le prompt en autorise
        # 1 a 3 ; le passage est compte juste si la bonne s'y trouve.
        # / A passage counts as correct if the expected family appears
        # among the families of the 1-3 hypostases it received.
        familles_rendues_par_element = {}
        for extraction in self.job.entities.all():
            premiere_portion = extraction.ancrages.order_by(
                "ordre_dans_extraction",
            ).first()
            if premiere_portion is None:
                continue
            hypostases_rendues = (extraction.attributes or {}).get("hypostases", "")
            for nom_d_hypostase in str(hypostases_rendues).split(","):
                famille_rendue = famille_par_hypostase.get(nom_d_hypostase.strip())
                if famille_rendue is not None:
                    familles_rendues_par_element.setdefault(
                        premiere_portion.element_id, set(),
                    ).add(famille_rendue)

        nombre_de_passages = len(PASSAGES_D_EPREUVE)
        nombre_de_passages_couverts = len(familles_rendues_par_element)
        nombre_de_passages_bien_classes = 0
        passages_mal_classes = []
        for element_id, familles_rendues in familles_rendues_par_element.items():
            famille_attendue = self.famille_attendue_par_element[element_id]
            if famille_attendue in familles_rendues:
                nombre_de_passages_bien_classes += 1
            else:
                passages_mal_classes.append(
                    f"element {element_id} : attendu famille "
                    f"{famille_attendue}, rendu {sorted(familles_rendues)}",
                )

        # 1. La couverture, d'abord : un score calcule sur deux passages
        # ne veut rien dire. / Coverage first: a score over two passages
        # is meaningless.
        couverture = nombre_de_passages_couverts / nombre_de_passages
        self.assertGreaterEqual(
            couverture, SEUIL_DE_COUVERTURE,
            f"Seuls {nombre_de_passages_couverts}/{nombre_de_passages} passages "
            f"ont recu une hypostase reconnue ({couverture:.0%}). Le score de "
            f"justesse ne serait pas significatif. Cause probable : le modele "
            f"rend des hypostases hors referentiel, que le filtre de "
            f"production supprime.",
        )

        # 2. La justesse ensuite, sur les passages effectivement couverts.
        # / Then accuracy, over the passages actually covered.
        concordance = nombre_de_passages_bien_classes / nombre_de_passages_couverts
        self.assertGreaterEqual(
            concordance, SEUIL_DE_CONCORDANCE,
            f"Concordance par famille epistemique : "
            f"{nombre_de_passages_bien_classes}/{nombre_de_passages_couverts} "
            f"= {concordance:.0%}, sous le seuil de "
            f"{SEUIL_DE_CONCORDANCE:.0%}.\n"
            f"Passages mal classes :\n  "
            + "\n  ".join(passages_mal_classes)
            + "\nUne chute de ce score signale d'abord une regression du "
            "prompt d'extraction (definitions par famille, exemples "
            "few-shot), pas un mauvais jour du modele.",
        )

    def test_les_hypostases_rendues_appartiennent_au_referentiel(self):
        """
        Le modele invente-t-il des etiquettes ?

        Le filtre de production supprime les hypostases hors referentiel.
        Une extraction dont TOUTES les hypostases ont ete supprimees
        arrive en base avec un champ vide : elle existe, elle est ancree,
        et elle n'est classee nulle part. Elle n'apparaitra dans aucune
        vue par hypostase.

        Ce test mesure combien d'extractions survivent a ce filtre. Il ne
        vise pas la perfection : il attrape le cas ou le prompt ne
        transmet plus le referentiel et ou le modele etiquette a sa
        guise.
        / Extractions whose hypostases were all filtered out arrive with
        an empty field: anchored, but classified nowhere.
        """
        lancer_l_analyse_d_une_page(self.page_d_epreuve, self.job)

        extractions = list(self.job.entities.all())
        self.assertGreater(len(extractions), 0)

        extractions_sans_hypostase = [
            extraction for extraction in extractions
            if not str((extraction.attributes or {}).get("hypostases", "")).strip()
        ]
        part_sans_hypostase = len(extractions_sans_hypostase) / len(extractions)
        self.assertLessEqual(
            part_sans_hypostase, 0.40,
            f"{len(extractions_sans_hypostase)}/{len(extractions)} extractions "
            f"({part_sans_hypostase:.0%}) n'ont aucune hypostase du referentiel : "
            f"elles sont ancrees dans le texte mais classees nulle part. Le "
            f"modele etiquette hors referentiel et le filtre de production "
            f"(front.normalisation) supprime tout.",
        )
