"""
Produit le wiki et la synthese dirigee du carnet etalon.
/ Produces the reference notebook's wiki and directed synthesis.

LOCALISATION : front/management/commands/produire_les_syntheses_etalons.py

POURQUOI CETTE COMMANDE EXISTE : jusqu'au 16 aout 2026, une
installation neuve n'avait AUCUN wiki et AUCUNE synthese — les deux
onglets du carnet etaient vides, et toute la couche synthese
(sourcage [N], panneau de preuve, ecartees, couverture, verification,
mise a jour par operations de section) restait invisible sans qu'on
sache si elle marchait.

ELLE APPELLE UN VRAI MODELE, DONC ELLE EST FACTUREE — comme
`analyser_les_notes_etalons`, et pour la meme raison : c'est ce qui
fait de l'installation un test de bout en bout de la chaine de
synthese, cles API comprises.

IDEMPOTENTE PAR DEFAUT : elle ne produit que ce qui manque. Relancer
l'installation ne refacture rien. `--forcer` est le seul flag, et il
fait l'inverse.
/ Billed, idempotent by default; --forcer re-produces.

FLUX :
1. Verifie que l'IA est active et qu'un modele est configure
2. Trouve le carnet etalon et ses notes sources
3. Cree le wiki s'il manque, puis lance produire_un_wiki_task
4. Cree la synthese dirigee si elle manque (perimetre FIGE au moment
   du geste, comme la vue), puis lance la tache correspondante

DEPENDENCIES :
- `charger_fixtures_sample` (le carnet), `charger_extractions_demo` et
  `analyser_les_notes_etalons` (les extractions a citer)
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import (
    Configuration, Dossier, Page, SyntheseDirigee, TypeDeNote, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from core.services.synthese import notes_sources_du_carnet
from hypostasis_extractor.models import ExtractionJob

# Le carnet monte par `charger_fixtures_sample`.
# / The notebook built by charger_fixtures_sample.
NOM_DU_CARNET_ETALON = "Documents étalons"

# Le sujet du wiki etalon. Il est VOLONTAIREMENT etroit : un sujet
# large citerait tout, et l'ecran « ce qui n'a pas ete repris »
# n'aurait rien a montrer. Mesure du 16 aout 2026 : sur ce sujet, le
# wiki cite 55 extractions sur 99 et en ecarte 46 — les ecartees sont
# celles qui parlent d'IA et d'epistemologie, donc hors sujet. C'est
# exactement ce que le panneau des ecartees doit donner a voir.
# / Deliberately narrow: a broad subject would cite everything and the
# "what was left out" panel would have nothing to show.
SUJET_DU_WIKI_ETALON = "Les open badges et la reconnaissance des compétences"

TITRE_DE_LA_SYNTHESE_ETALON = "État des lieux du carnet de démonstration"


class Command(BaseCommand):
    help = (
        "Produit le wiki et la synthese dirigee du carnet etalon par le "
        "VRAI modele. Idempotente : ne produit que ce qui manque. "
        "APPELS FACTURES."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--forcer", action="store_true",
            help=(
                "Reproduit meme si le wiki et la synthese existent deja. "
                "APPELS FACTURES."
            ),
        )

    def handle(self, *args, **options):
        configuration = Configuration.get_solo()
        if not configuration.ai_active or not configuration.ai_model:
            raise CommandError(
                "L'IA n'est pas active ou aucun modèle n'est configuré : "
                "impossible de produire les synthèses étalons.",
            )

        carnet = Dossier.objects.filter(name=NOM_DU_CARNET_ETALON).first()
        if carnet is None:
            raise CommandError(
                f"Le carnet « {NOM_DU_CARNET_ETALON} » n'existe pas : "
                f"lancez d'abord charger_fixtures_sample.",
            )

        # Sans extraction, un article ne pourrait citer personne — et la
        # garde « zero citation = refus » ferait echouer la tache.
        # / No extraction, no citation, and the zero-citation guard fires.
        notes_sources = list(notes_sources_du_carnet(carnet))
        nombre_d_extractions = self._compter_les_extractions(notes_sources)
        if nombre_d_extractions == 0:
            self.stdout.write(
                "  Aucune extraction dans le carnet étalon : rien à citer, "
                "production sautée. Lancez d'abord "
                "charger_extractions_demo.",
            )
            return

        self.stdout.write(
            f"  Carnet « {carnet.name} » : {len(notes_sources)} note(s) "
            f"source(s), {nombre_d_extractions} extraction(s).",
        )

        self._produire_le_wiki(
            carnet, configuration, options["forcer"], nombre_d_extractions,
        )
        self._produire_la_synthese(
            carnet, notes_sources, configuration, options["forcer"],
            nombre_d_extractions,
        )

    def _faut_il_reproduire(self, page_d_article, nombre_d_extractions):
        """
        Reproduit-on cet article ? / Should this article be reproduced?

        DEUX raisons de reproduire, et une seule de sauter.

        1. L'article est VIDE : la tache a echoue, ou n'a jamais tourne.
           Sauter sur la seule existence de la ligne gelerait un article
           vide POUR TOUJOURS, en annonçant « deja produit ».
        2. Le PERIMETRE A GROSSI depuis la production. `bin/install.sh`
           lance cette commande apres l'analyse, mais les analyses partent
           dans la file Celery et ne sont pas finies : au premier
           demarrage, l'article ne cite qu'une partie du corpus (mesure du
           17 aout 2026 : 65 extractions sur 101). C'est ce qui rend vraie
           la promesse d'`install.sh` — « le demarrage suivant complete ce
           qui manque ».

        Sinon on saute, et rien n'est refacture.
        / Reproduce when the article is empty, or when the scope has grown
        since it was produced. Otherwise skip — nothing is re-billed.
        """
        if page_d_article is None:
            return True
        if not (page_d_article.text_readability or "").strip():
            return True

        dernier_job = ExtractionJob.objects.filter(
            page=page_d_article,
        ).order_by("-pk").first()
        taille_a_la_production = (
            (dernier_job.raw_result or {}).get("taille_du_perimetre")
            if dernier_job else None
        )
        if taille_a_la_production is None:
            # Article produit avant que la taille ne soit consignee : on
            # ne sait pas, donc on ne refacture pas. / Unknown: don't bill.
            return False
        return nombre_d_extractions > taille_a_la_production

    def _compter_les_extractions(self, notes_sources):
        """Le nombre d'extractions citables du carnet. / Citable count."""
        from core.services.synthese import extractions_citables_de_la_note

        total = 0
        for note in notes_sources:
            total += extractions_citables_de_la_note(note).count()
        return total

    def _produire_le_wiki(self, carnet, configuration, forcer,
                          nombre_d_extractions):
        """Cree le wiki s'il manque, et lance sa production."""
        wiki_existant = Wiki.objects.filter(
            dossier=carnet, sujet=SUJET_DU_WIKI_ETALON,
        ).first()
        # Le saut porte sur le RESULTAT (un article rempli), jamais sur
        # l'intention. La ligne Wiki est creee AVANT l'envoi de la
        # tache : si celle-ci echoue — cle tombee, garde zero-citation —
        # sauter sur son existence gelerait un article VIDE pour
        # toujours, et chaque redemarrage annoncerait « deja produit ».
        # / Skip on the result, never on the intent: a failed task must
        # not freeze an empty article forever.
        page_du_wiki = wiki_existant.page if wiki_existant else None
        deja_produit = not self._faut_il_reproduire(
            page_du_wiki, nombre_d_extractions,
        )
        if deja_produit and not forcer:
            self.stdout.write(
                f"  Wiki « {SUJET_DU_WIKI_ETALON[:40]} » : déjà produit — "
                f"sauté.",
            )
            return

        if wiki_existant is not None:
            wiki = wiki_existant
        else:
            page_d_article = Page.objects.create(
                title=f"Wiki — {SUJET_DU_WIKI_ETALON}"[:500],
                text_readability="", html_readability="", html_original="",
                content_hash="", type_de_note=TypeDeNote.WIKI,
                owner=carnet.owner,
            )
            ranger_une_note_dans_un_carnet(
                page_d_article, carnet, carnet.owner,
            )
            wiki = Wiki.objects.create(
                page=page_d_article, dossier=carnet,
                sujet=SUJET_DU_WIKI_ETALON,
            )

        job = ExtractionJob.objects.create(
            page=wiki.page, ai_model=configuration.ai_model,
            name=f"Wiki — {SUJET_DU_WIKI_ETALON}"[:200],
            prompt_description="Wiki étalon (fixtures)",
            status="pending",
            raw_result={
                "est_wiki": True, "wiki_id": wiki.pk,
                "demandeur_id": carnet.owner_id,
                # La taille du perimetre AU MOMENT DE LA PRODUCTION :
                # c'est elle que le prochain passage comparera.
                # / The scope size at production time.
                "taille_du_perimetre": nombre_d_extractions,
            },
        )
        from front.tasks import produire_un_wiki_task

        produire_un_wiki_task.delay(job.pk)
        self.stdout.write(
            f"  Wiki « {SUJET_DU_WIKI_ETALON[:40]} » : envoyé au modèle "
            f"(job {job.pk}).",
        )

    def _produire_la_synthese(self, carnet, notes_sources, configuration,
                              forcer, nombre_d_extractions):
        """Cree l'acte date si besoin, perimetre FIGE, et lance la tache."""
        synthese_existante = SyntheseDirigee.objects.filter(
            dossier=carnet, page__title=TITRE_DE_LA_SYNTHESE_ETALON,
        ).first()
        # Meme regle que pour le wiki : on saute sur le RESULTAT.
        # / Same rule as the wiki: skip on the result.
        page_de_la_dirigee = (
            synthese_existante.page if synthese_existante else None
        )
        deja_produite = not self._faut_il_reproduire(
            page_de_la_dirigee, nombre_d_extractions,
        )
        if deja_produite and not forcer:
            self.stdout.write(
                f"  Synthèse « {TITRE_DE_LA_SYNTHESE_ETALON[:40]} » : déjà "
                f"produite — sautée.",
            )
            return

        if synthese_existante is not None:
            page_de_synthese = synthese_existante.page
        else:
            page_de_synthese = Page.objects.create(
                title=TITRE_DE_LA_SYNTHESE_ETALON[:500],
                text_readability="", html_readability="", html_original="",
                content_hash="", type_de_note=TypeDeNote.SYNTHESE,
                owner=carnet.owner,
            )
            ranger_une_note_dans_un_carnet(
                page_de_synthese, carnet, carnet.owner,
            )
            # Le perimetre est FIGE au moment du geste (SPEC-synthese
            # § 3.2) : un acte date ne recalcule jamais sa portee.
            # / Frozen at request time: a dated act never recomputes.
            synthese = SyntheseDirigee.objects.create(
                page=page_de_synthese, dossier=carnet,
                produite_par=carnet.owner, produite_le=timezone.now(),
                perimetre_d_extractions_fige=True,
            )
            synthese.notes_du_perimetre.set(
                [note.pk for note in notes_sources]
            )

        job = ExtractionJob.objects.create(
            page=page_de_synthese, ai_model=configuration.ai_model,
            name=TITRE_DE_LA_SYNTHESE_ETALON[:200],
            prompt_description="Synthèse dirigée étalon (fixtures)",
            status="pending",
            raw_result={
                "est_synthese_carnet": True,
                "demandeur_id": carnet.owner_id,
                "notes_du_perimetre": [note.pk for note in notes_sources],
                "taille_du_perimetre": nombre_d_extractions,
            },
        )
        from front.tasks import produire_une_synthese_de_carnet_task

        produire_une_synthese_de_carnet_task.delay(job.pk)
        self.stdout.write(
            f"  Synthèse « {TITRE_DE_LA_SYNTHESE_ETALON[:40]} » : envoyée "
            f"au modèle (job {job.pk}).",
        )
