"""
Gele les paires deja jugees dans un fichier, pour pouvoir comparer des
juges. / Freezes already-judged pairs to a file, to compare judges.

LOCALISATION : front/management/commands/geler_l_etalon_du_juge.py

POURQUOI CETTE COMMANDE EXISTE. Les verdicts vivent dans une colonne
QU'ON REECRIT : le bouton « Vérifier les citations » rejuge tout l'article
(sauf les CONTESTE), `verifier_les_citations_etalons` en fait autant des
qu'une seule paire a perdu son verdict, et `--forcer` rejuge sans
condition. Une mesure qui ne vit que dans une colonne reecrivable n'est
pas une mesure : c'est un etat.

Le fichier produit est donc l'ETALON — la question exacte posee au juge,
et la reponse qu'il a donnee — et c'est lui que le banc de comparaison
rejoue. Il n'est PAS une fixture : rien ne le charge en base, et le banc
le lit a chaque execution. Un fichier que personne ne lit devient faux
sans que personne ne le sache.

LA QUESTION GELEE EST LA VRAIE. Les affirmations sont redecoupees par
`preparer_les_paires_a_juger`, le meme parcours que celui qui a servi au
juge de reference — pas une seconde copie qui finirait par diverger.

LA DERIVE EST SIGNALEE, JAMAIS AVALEE. Un lien qui porte un verdict mais
qui n'atteindrait plus le juge aujourd'hui (bornes perimees, source
supprimee, verbatim devenu introuvable) a change de question depuis son
verdict : le geler produirait une comparaison fausse. Il est donc EXCLU
des paires et compte dans « derives ».

DEPENDENCIES :
- `core.services.verification.preparer_les_paires_a_juger` (lecture seule)
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import EtatDeVerification, Page, SourceLink, TypeLien
from core.services.verification import (
    VERSION_DE_LA_METHODE, preparer_les_paires_a_juger,
)

CHEMIN_PAR_DEFAUT = "benchmarks/juge_de_verification/etalon-du-juge.json"

# Ce que le juge de reference a REPONDU, deduit de l'etat qu'il a pose.
# C'est l'unite comparable : « soutient » ou « ne_soutient_pas », le seul
# vocabulaire que le juge parle.
# / What the reference judge ANSWERED, derived from the state it stored.
REPONSE_DE_REFERENCE_PAR_ETAT = {
    EtatDeVerification.VERIFIE: "soutient",
    EtatDeVerification.SOURCE_DEBAT: "soutient",
    EtatDeVerification.FAIBLE: "ne_soutient_pas",
}


class Command(BaseCommand):
    help = (
        "Gèle dans un fichier JSON les paires (affirmation, source) déjà "
        "jugées, avec la réponse du juge de référence. Lecture seule : "
        "aucun appel de modèle, aucune écriture en base."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sortie", default=CHEMIN_PAR_DEFAUT,
            help=f"Chemin du fichier à écrire (défaut : {CHEMIN_PAR_DEFAUT})",
        )

    def handle(self, *args, **options):
        # Les articles qui portent au moins une citation jugee.
        # / The articles carrying at least one judged citation.
        identifiants_d_articles = SourceLink.objects.filter(
            type_lien=TypeLien.CITE,
        ).exclude(
            etat_de_verification=EtatDeVerification.NON_VERIFIE,
        ).values_list("page_cible_id", flat=True).distinct()
        articles = list(
            Page.objects.filter(pk__in=list(identifiants_d_articles))
            .order_by("pk")
        )
        if not articles:
            raise CommandError(
                "Aucune citation jugée en base : il n'y a rien à geler. "
                "Lancez d'abord `verifier_les_citations_etalons`.",
            )

        paires_gelees = []
        derives = []
        jamais_jugees = 0

        for article in articles:
            file_du_juge, ecartees = preparer_les_paires_a_juger(article)

            for paire in file_du_juge:
                reponse = REPONSE_DE_REFERENCE_PAR_ETAT.get(
                    paire.lien.etat_de_verification,
                )
                if reponse is None:
                    # La paire atteindrait le juge, mais aucun verdict
                    # n'a jamais ete pose : rien a comparer.
                    # / Judgeable, but never judged: nothing to compare.
                    jamais_jugees += 1
                    continue
                paires_gelees.append({
                    "lien_id": paire.lien.pk,
                    "article_id": article.pk,
                    "article_titre": article.title,
                    "extraction_id": paire.lien.extraction_source_id,
                    "affirmation": paire.affirmation,
                    "texte_source": paire.texte_source,
                    "etat_si_soutient": paire.etat_si_soutient,
                    "verdict_de_reference": paire.lien.etat_de_verification,
                    "reponse_de_reference": reponse,
                    "verifie_par": paire.lien.verifie_par,
                    "verifie_le": (
                        paire.lien.verifie_le.isoformat()
                        if paire.lien.verifie_le else None
                    ),
                })

            for lien, raison in ecartees:
                if lien.etat_de_verification in REPONSE_DE_REFERENCE_PAR_ETAT:
                    # Un verdict existe, mais la question a change depuis.
                    # / A verdict exists, but the question has drifted.
                    derives.append({
                        "lien_id": lien.pk,
                        "article_id": article.pk,
                        "raison": raison,
                        "verdict_en_base": lien.etat_de_verification,
                    })

        contenu = {
            "gele_le": timezone.now().isoformat(),
            "methode_de_reference": VERSION_DE_LA_METHODE,
            "nombre_de_paires": len(paires_gelees),
            "articles": [
                {"page_id": article.pk, "titre": article.title}
                for article in articles
            ],
            "paires": paires_gelees,
            "derives": derives,
        }

        chemin_de_sortie = Path(options["sortie"])
        chemin_de_sortie.parent.mkdir(parents=True, exist_ok=True)
        chemin_de_sortie.write_text(
            json.dumps(contenu, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.stdout.write(
            f"  {len(paires_gelees)} paire(s) gelée(s) dans "
            f"{chemin_de_sortie}",
        )
        repartition = {}
        for paire in paires_gelees:
            verdict = paire["verdict_de_reference"]
            repartition[verdict] = repartition.get(verdict, 0) + 1
        for verdict, nombre in sorted(repartition.items()):
            self.stdout.write(f"    {verdict} : {nombre}")
        if jamais_jugees:
            self.stdout.write(
                f"  {jamais_jugees} paire(s) jugeable(s) mais jamais "
                f"jugée(s) — exclue(s), rien à comparer.",
            )
        if derives:
            # Ce n'est pas une erreur, c'est un fait a connaitre : ces
            # paires portent un verdict rendu sur une question qui n'est
            # plus la leur. / Not an error, a fact worth knowing.
            self.stdout.write(
                f"  ⚠ {len(derives)} paire(s) portent un verdict mais "
                f"n'atteindraient plus le juge (question dérivée depuis "
                f"le verdict) — exclue(s) de l'étalon.",
            )
