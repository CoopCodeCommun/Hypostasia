"""
Verifie les citations du wiki et de la synthese etalons.
/ Verifies the reference wiki's and synthesis's citations.

LOCALISATION : front/management/commands/verifier_les_citations_etalons.py

POURQUOI CETTE COMMANDE EXISTE : la verification est un GESTE EXPLICITE,
jamais automatique a la production (SPEC-synthese § 7, question n°3
tranchee le 9 aout 2026). Consequence : une installation neuve montrait
des articles dont TOUS les renvois etaient « non verifie » — l'etage qui
fait toute la valeur du produit restait invisible, et le chiffre qui rend
la demonstration convaincante (~88 % de citations verifiees sur les
donnees etalons, mesure du 17 aout 2026) n'apparaissait nulle part.

CE QU'ELLE NE CHANGE PAS : la doctrine. La verification reste un acte
separe et contestable, declenche ici par l'installation comme il l'est
ailleurs par le bouton « Verifier les citations » de l'ecran article.
C'est le meme endpoint, la meme tache, le meme juge.

ELLE APPELLE UN VRAI MODELE, DONC ELLE EST FACTUREE — un lot de 20
paires par appel.

IDEMPOTENTE AU GRAIN DE L'ARTICLE, ET C'EST UNE NUANCE QUI COUTE. Elle
saute un article dont plus AUCUNE citation n'attend de verdict, donc un
redemarrage ordinaire ne refacture rien. Mais des qu'UNE SEULE paire est
« non verifie », le job couvre l'article ENTIER et le juge rejuge toutes
ses paires — leurs verdicts sont REECRITS, celui d'une mesure comprise.
C'est pour cela que l'etalon des juges est GELE hors de la base :
`manage.py geler_l_etalon_du_juge`, lu par
`benchmarks/juge_de_verification/`.
/ Skipping is per ARTICLE, not per pair: one unverified pair re-judges —
and rewrites — every verdict of that article. Hence the frozen file.

`--forcer` est le seul flag, et il rejuge tout sans condition.
/ Verification is an explicit act, never automatic at production; a fresh
install showed only "not verified". Billed, idempotent on the result.

DEPENDENCIES :
- `produire_les_syntheses_etalons` (les articles et leurs SourceLink)
"""

from django.core.management.base import BaseCommand, CommandError

from core.models import (
    Configuration, Dossier, EtatDeVerification, RoleDeModele, SourceLink,
    SyntheseDirigee, TypeLien, Wiki,
)
from core.services.modeles_par_role import modele_du_role
from hypostasis_extractor.models import ExtractionJob

from .produire_les_syntheses_etalons import NOM_DU_CARNET_ETALON


class Command(BaseCommand):
    help = (
        "Verifie les citations du wiki et de la synthese etalons par le "
        "VRAI modele. Ne juge que les paires sans verdict. APPELS FACTURES."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--forcer", action="store_true",
            help=(
                "Rejuge TOUTES les paires, meme celles qui portent deja un "
                "verdict. APPELS FACTURES."
            ),
        )

    def handle(self, *args, **options):
        configuration = Configuration.get_solo()
        # Le JUGE, pas le redacteur. A defaut d'affectation, le role
        # retombe sur le modele de la Configuration — c'est ce repli qui
        # garantit que cette commande se comporte comme avant tant que
        # personne n'a affecte de juge.
        # / The JUDGE; falls back to the Configuration's model.
        modele_du_juge = modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION)
        if not configuration.ai_active or not modele_du_juge:
            raise CommandError(
                "L'IA n'est pas active ou aucun modèle n'est configuré : "
                "le juge de vérification a besoin d'un modèle.",
            )

        carnet = Dossier.objects.filter(name=NOM_DU_CARNET_ETALON).first()
        if carnet is None:
            raise CommandError(
                f"Le carnet « {NOM_DU_CARNET_ETALON} » n'existe pas : "
                f"lancez d'abord charger_fixtures_sample.",
            )

        articles = [wiki.page for wiki in Wiki.objects.filter(dossier=carnet)]
        articles += [
            dirigee.page
            for dirigee in SyntheseDirigee.objects.filter(dossier=carnet)
        ]
        if not articles:
            self.stdout.write(
                "  Aucun article dans le carnet étalon : rien à vérifier. "
                "Lancez d'abord produire_les_syntheses_etalons.",
            )
            return

        for page_d_article in articles:
            self._verifier_un_article(
                page_d_article, modele_du_juge, options["forcer"],
            )

    def _verifier_un_article(self, page_d_article, modele_du_juge, forcer):
        """Lance la verification si des paires attendent un verdict."""
        liens = SourceLink.objects.filter(
            page_cible=page_d_article, type_lien=TypeLien.CITE,
        )
        if not liens.exists():
            self.stdout.write(
                f"  « {page_d_article.title[:40]} » : aucune citation — "
                f"l'article n'est peut-être pas encore produit.",
            )
            return

        # Le saut porte sur le RESULTAT : plus aucune paire sans verdict.
        # Un article produit apres cette commande — les taches d'article
        # partent dans la file Celery — sera donc verifie au demarrage
        # suivant, sans qu'on ait rien a ordonner.
        # / Skip on the result: no pair left without a verdict.
        nombre_sans_verdict = liens.filter(
            etat_de_verification=EtatDeVerification.NON_VERIFIE,
        ).count()
        if nombre_sans_verdict == 0 and not forcer:
            self.stdout.write(
                f"  « {page_d_article.title[:40]} » : "
                f"{liens.count()} citation(s), toutes déjà jugées — sautée.",
            )
            return

        job = ExtractionJob.objects.create(
            page=page_d_article,
            ai_model=modele_du_juge,
            name=f"Vérification — {page_d_article.title}"[:200],
            prompt_description="Vérification des citations (§ 7, fixtures)",
            status="pending",
            # LE MEME MARQUEUR que l'endpoint du bouton : c'est lui que la
            # tache verifie avant de toucher au job (garde du 17 aout).
            # / The same marker the button's endpoint sets.
            raw_result={
                "est_verification": True,
                "demandeur_id": page_d_article.owner_id,
            },
        )
        from front.tasks import verifier_les_citations_task

        verifier_les_citations_task.delay(job.pk)
        self.stdout.write(
            f"  « {page_d_article.title[:40]} » : {nombre_sans_verdict} "
            f"citation(s) sans verdict envoyée(s) au juge (job {job.pk}).",
        )
