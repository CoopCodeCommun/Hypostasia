"""
Fait noter les citations du carnet etalon par les quatre juges locaux.
/ Has the four local judges score the reference notebook's citations.

LOCALISATION : front/management/commands/noter_avec_les_juges_locaux.py

POURQUOI CETTE COMMANDE EXISTE. Les avis des juges locaux ne partaient
que d'un BOUTON, article par article. Une installation neuve n'en avait
donc AUCUN : la fiche de preuve affichait « aucun avis » sur tout le
corpus etalon, et rien ne disait que c'etait normal. Le second avis
— toute une couche du produit — restait invisible sans qu'on sache si
elle marchait.

ELLE EST GRATUITE ET HORS RESEAU. Les quatre encodeurs tournent sur
processeur, dans le conteneur. C'est ce qui la distingue de
`analyser_les_notes_etalons` et de `produire_les_syntheses_etalons`, qui
appellent un modele FACTURE. On peut donc la lancer a chaque
installation sans rien payer.

ELLE NE NOTE RIEN ELLE-MEME : elle met un job par article en file, et
c'est `noter_avec_le_juge_local_task` qui travaille, sur la file
`verification_locale` — a concurrence 1, sous `nice -n 19`, pour ne pas
affamer Docling.

IDEMPOTENTE PAR DEFAUT : un article dont toutes les citations portent
deja l'avis des quatre juges est saute. `--forcer` est le seul flag, et
il fait l'inverse.
"""

from django.core.management.base import BaseCommand

from core.models import Dossier, Page, SourceLink, TypeDeNote, TypeLien
from hypostasis_extractor.models import ExtractionJob

# Le carnet monte par `charger_fixtures_sample`.
# / The notebook built by charger_fixtures_sample.
NOM_DU_CARNET_ETALON = "Documents étalons"


class Command(BaseCommand):
    help = (
        "Fait noter les citations du carnet étalon par les quatre juges "
        "locaux. GRATUIT et hors réseau. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--forcer", action="store_true",
            help=(
                "Remet en file même les articles déjà notés par les "
                "quatre juges."
            ),
        )

    def handle(self, *args, **options):
        from core.services.juges_locaux import JUGES, methode
        from front.tasks import noter_avec_le_juge_local_task

        carnet = Dossier.objects.filter(name=NOM_DU_CARNET_ETALON).first()
        if carnet is None:
            self.stdout.write(
                f"  Le carnet « {NOM_DU_CARNET_ETALON} » n'existe pas : "
                f"rien à noter.",
            )
            return

        methodes_attendues = {methode(nom) for nom in JUGES}
        articles = Page.objects.filter(
            appartenances_dossiers__dossier=carnet,
        ).exclude(type_de_note=TypeDeNote.NOTE).distinct()

        mis_en_file = 0
        for article in articles:
            liens = SourceLink.objects.filter(
                page_cible=article, type_lien=TypeLien.CITE,
            )
            # Un article sans citation ferait charger 5,13 Go de modeles
            # pour ne rien noter. / No citation, nothing to score.
            if not liens.exists():
                continue

            if not options["forcer"]:
                # DEJA NOTE = chaque citation porte les QUATRE avis. Un
                # seul juge manquant suffit a remettre l'article en
                # file : la tache, elle, est idempotente paire par paire
                # et ne refera pas ce qui existe.
                # / Fully scored means all four methods on every link.
                complet = True
                for lien in liens.prefetch_related("avis_locaux"):
                    rendues = {
                        avis.methode for avis in lien.avis_locaux.all()
                    }
                    if not methodes_attendues.issubset(rendues):
                        complet = False
                        break
                if complet:
                    self.stdout.write(
                        f"  « {article.title[:44]} » : déjà noté par les "
                        f"{len(JUGES)} juges — sauté.",
                    )
                    continue

            job = ExtractionJob.objects.create(
                page=article,
                # Pas d'`ai_model` : les juges locaux ne sont PAS au
                # referentiel, et ne doivent pas y entrer — ils seraient
                # alors proposes au clic comme modele d'extraction, que
                # LangExtract ne sait pas piloter.
                # / No AIModel row: it would be offered for extraction.
                ai_model=None,
                name=f"Second avis — {article.title}"[:200],
                prompt_description=(
                    f"Avis des {len(JUGES)} juges locaux de vérification"
                ),
                status="pending",
                raw_result={
                    # Marqueur DISTINCT de `est_verification` : le menu
                    # des taches liste ce dernier, et sans distinction
                    # chaque geste y ferait deux lignes.
                    # / A DISTINCT marker from est_verification.
                    "est_second_avis": True,
                    "demandeur_id": carnet.owner_id,
                },
            )
            noter_avec_le_juge_local_task.delay(job.pk)
            mis_en_file += 1
            self.stdout.write(
                f"  « {article.title[:44]} » : {liens.count()} citation(s) "
                f"envoyée(s) aux {len(JUGES)} juges locaux (job {job.pk}).",
            )

        if not mis_en_file:
            self.stdout.write(
                "  Rien à noter : tout le carnet porte déjà ses avis.",
            )
