"""
Fait analyser les notes etalons par le VRAI modele configure.
/ Has the reference notes analysed by the REAL configured model.

LOCALISATION : front/management/commands/analyser_les_notes_etalons.py

POURQUOI CETTE COMMANDE EXISTE, ET CE QU'ELLE REMPLACE

Deux jeux de demonstration vivaient en parallele. Le mainteneur l'a vu a
l'ecran, le 15 aout 2026 : DEUX carnets, dont un nomme « Demonstration —
moteur reel » — ce qui disait, sans le vouloir, que l'autre ne l'etait
pas. Il avait raison de tiquer.

L'explication tient a un croisement de dates. `charger_fixtures_llm_reel`
date du 10 aout, `charger_fixtures_sample` du 11 : la premiere est
ANTERIEURE aux documents etalons du depot. Elle avait le bon principe —
ingerer puis analyser POUR DE VRAI — mais sur deux textes inventes,
ecrits en dur dans le fichier Python, et rangeait ses notes dans son
propre carnet. La seconde a apporte les vrais documents le lendemain,
sans les faire analyser. Les deux commandes se sont croisees sans se
rejoindre.

Mesure avant correction : sur 19 extractions, 7 venaient du modele (les
textes jouets) et 12 etaient ecrites a la main ; TROIS documents sur six
n'avaient aucune extraction.
/ Two datasets ran in parallel because one command predated the
repository's own documents by a day.

CE QU'ELLE FAIT, ET SURTOUT CE QU'ELLE NE FAIT PAS

Elle ne cree NI note NI carnet. Elle prend celles qui sont deja la —
chargees par `charger_fixtures_sample` — et les envoie a l'analyse. Il
n'y a donc plus qu'un seul carnet de demonstration.
/ It creates no note and no notebook: one demo notebook remains.

LES DEUX ORIGINES D'EXTRACTION COEXISTENT

`charger_extractions_demo` pose des extractions ECRITES A LA MAIN, pour
couvrir des cas qu'un modele ne produit pas de facon fiable : marques
imbriquees, ancre portee par un tableau, cartes a 0/1/2 commentaires.
C'est la matiere qui sert a styler l'interface, et elle reste.

Ses jobs se reconnaissent a leur `ai_model` VIDE. C'est ce qui permet de
distinguer « deja analysee par un modele » de « porte des extractions
posees a la main » — une garde qui regarderait les seules extractions
sauterait justement les notes a analyser.
/ Hand-written jobs carry no ai_model, which is how the guard tells the
two apart.
"""

from django.core.management.base import BaseCommand, CommandError

from core.models import Configuration, Page
from hypostasis_extractor.models import (
    AnalyseurSyntaxique,
    ExtractionJob,
    PromptPiece,
)

# Le carnet monte par `charger_fixtures_sample`.
# / The notebook built by charger_fixtures_sample.
NOM_DU_CARNET_ETALON = "Documents étalons"

# Au-dela de ce nombre d'elements, une note n'est PAS analysee a
# l'installation. La « Presentation Hypostasia V3 » en porte 549 a elle
# seule, soit 73 % du corpus etalon : l'analyser a chaque installation
# neuve couterait cher sans rien montrer de plus qu'un document plus
# court. Elle reste analysable a la main, ou avec --forcer.
# / Past this element count a note is not analysed at install time: one
# document alone holds 73 % of the corpus.
LIMITE_D_ELEMENTS_POUR_ANALYSE = 100


class Command(BaseCommand):
    help = (
        "Envoie a l'analyse par le vrai modele les notes etalons qui "
        "n'ont pas encore ete analysees. Ne cree ni note ni carnet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--forcer", action="store_true",
            help=(
                "Reanalyse meme les notes deja analysees par un modele. "
                "APPELS FACTURES."
            ),
        )

    def handle(self, *args, **options):
        configuration = Configuration.get_solo()
        if not configuration.ai_active or not configuration.ai_model:
            raise CommandError(
                "L'IA n'est pas active ou aucun modèle n'est configuré : "
                "impossible d'analyser les notes étalons.",
            )
        analyseur = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="analyser",
        ).order_by("-est_par_defaut", "name").first()
        if analyseur is None:
            raise CommandError("Aucun analyseur d'extraction actif.")

        notes_du_carnet = Page.objects.filter(
            appartenances_dossiers__dossier__name=NOM_DU_CARNET_ETALON,
        ).distinct().order_by("pk")

        nombre_envoye = 0
        for note in notes_du_carnet:
            nombre_d_elements = note.elements.count()

            # Une note sans element n'a rien a ancrer : l'analyse
            # produirait des extractions sans passage.
            # / No element, nothing to anchor.
            if nombre_d_elements == 0:
                self.stdout.write(
                    f"  {note.title[:44]} : aucun élément — sautée.",
                )
                continue

            if nombre_d_elements > LIMITE_D_ELEMENTS_POUR_ANALYSE:
                self.stdout.write(
                    f"  {note.title[:44]} : {nombre_d_elements} éléments, "
                    f"au-delà de {LIMITE_D_ELEMENTS_POUR_ANALYSE} — sautée "
                    f"(coût). Pour l'analyser quand même : --forcer.",
                )
                continue

            if not options["forcer"] and self._deja_analysee_par_un_modele(note):
                self.stdout.write(
                    f"  {note.title[:44]} : déjà analysée par un modèle — "
                    f"sautée.",
                )
                continue

            self._envoyer_a_l_analyse(note, analyseur, configuration.ai_model)
            nombre_envoye += 1

        if nombre_envoye == 0:
            self.stdout.write(
                "Aucune note à analyser : tout est déjà fait.",
            )
            return

        self.stdout.write(self.style.SUCCESS(
            f"\n{nombre_envoye} analyse(s) envoyée(s) dans la file Celery, "
            f"par {configuration.ai_model}. Suivez-les depuis le menu des "
            f"tâches.",
        ))

    def _deja_analysee_par_un_modele(self, note):
        """
        Dit si un MODELE a deja analyse cette note, ou est en train.
        / Says whether a MODEL has already analysed this note.

        LOCALISATION : front/management/commands/analyser_les_notes_etalons.py

        `ai_model__isnull=False` est la clef : les jobs de
        `charger_extractions_demo` n'en portent pas, puisque leurs
        extractions sont ecrites a la main. Regarder les extractions
        elles-memes sauterait donc les notes qu'on veut precisement faire
        analyser.

        Les jobs `pending` et `processing` comptent aussi : sans cela, un
        conteneur redemarre pendant le traitement renverrait toutes les
        analyses en file, et les refacturerait.
        / Queued jobs count too, or a restart would re-queue and re-bill.
        """
        return ExtractionJob.objects.filter(
            page=note,
            ai_model__isnull=False,
            status__in=["pending", "processing", "completed"],
        ).exists()

    def _envoyer_a_l_analyse(self, note, analyseur, ai_model):
        """
        Cree le job puis l'envoie dans la file Celery.
        / Creates the job then queues it.

        LOCALISATION : front/management/commands/analyser_les_notes_etalons.py

        Meme construction que la vue d'analyse (front/views.py) : un job
        `pending` portant le snapshot du prompt. `.delay()` et jamais
        `.apply()` — l'installation ne doit pas attendre le modele, et
        l'administrateur suit l'avancement depuis son menu des taches.
        / Same shape as the analysis view; queued, never run in place.
        """
        from hypostasis_extractor.tasks_element import (
            analyser_une_page_avec_le_moteur_element,
        )

        pieces = PromptPiece.objects.filter(analyseur=analyseur).order_by("order")
        prompt_snapshot = "\n".join(piece.content for piece in pieces)
        job = ExtractionJob.objects.create(
            page=note, ai_model=ai_model,
            name=f"Analyseur: {analyseur.name}",
            prompt_description=prompt_snapshot,
            status="pending",
            raw_result={"analyseur_id": analyseur.pk},
        )
        analyser_une_page_avec_le_moteur_element.delay(job.pk)
        self.stdout.write(
            f"  {note.title[:44]} : {note.elements.count()} éléments → "
            f"file Celery (job {job.pk}).",
        )
