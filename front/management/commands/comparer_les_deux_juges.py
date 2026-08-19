"""
Lire la campagne : ou en sont les deux juges, et sur quoi divergent-ils ?
/ Read the campaign: where do the two judges stand, and where do they differ?

LOCALISATION : front/management/commands/comparer_les_deux_juges.py

CE QU'ELLE MESURE, ET CE QU'ELLE NE MESURE PAS. L'ACCORD, pas la verite.
Ni le juge de production ni le juge local ne detiennent la bonne
reponse : ce que cette commande produit, c'est une LISTE DE DESACCORDS
a relire a la main. C'est cette relecture, et elle seule, qui donnera la
reference humaine a grande echelle qui manque aujourd'hui — les deux
mesures publiees portent sur quinze paires d'une seule affirmation, et
sur 145 paires jugees par un modele dont la reproductibilite est de
77 %.

ELLE LIT LA BASE VIVANTE. Decision du mainteneur, 18 aout 2026 : pas de
gel pour l'instant. Consequence a connaitre — un chiffre lu deux jours
de suite peut differer parce que des articles ont ete revus entre-temps,
et ce n'est pas un defaut.

AUCUN APPEL DE MODELE, AUCUNE ECRITURE.
"""

from django.core.management.base import BaseCommand

from core.models import EtatDeVerification, SourceLink, TypeLien
from core.services.verification import seuil_de_verification


def _aire_sous_la_courbe(scores, verites):
    """
    L'AUC, par comptage de paires concordantes (Mann-Whitney).
    / AUC by concordant-pair counting.

    POURQUOI L'AUC PLUTOT QU'UN TAUX D'ACCORD. Un taux d'accord depend
    du seuil qu'on a choisi, et les deux juges n'ont pas le meme. L'AUC
    n'en depend d'aucun : c'est la probabilite qu'une paire jugee
    positive par la production recoive un degre local plus haut qu'une
    paire jugee negative. 0,5 = le hasard.
    / Threshold-free, which matters when the two judges do not share one.
    """
    positifs = [s for s, v in zip(scores, verites) if v]
    negatifs = [s for s, v in zip(scores, verites) if not v]
    if not positifs or not negatifs:
        return None
    concordantes = 0.0
    for score_positif in positifs:
        for score_negatif in negatifs:
            if score_positif > score_negatif:
                concordantes += 1.0
            elif score_positif == score_negatif:
                concordantes += 0.5
    return concordantes / (len(positifs) * len(negatifs))


class Command(BaseCommand):
    help = (
        "Compare le juge de production et le juge local sur les citations "
        "que les deux ont notées. Lecture seule : aucun appel de modèle, "
        "aucune écriture en base."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--desaccords", type=int, default=20,
            help="Combien de désaccords détailler (défaut : 20).",
        )

    def handle(self, *args, **options):
        seuil_de_production = seuil_de_verification()

        liens = SourceLink.objects.filter(
            type_lien=TypeLien.CITE,
        ).select_related("page_cible")

        total = liens.count()
        avec_degre = liens.filter(score_de_verification__isnull=False).count()
        avec_second_avis = liens.filter(
            score_du_second_avis__isnull=False,
        ).count()
        comparables = list(
            liens.filter(
                score_de_verification__isnull=False,
                score_du_second_avis__isnull=False,
                seuil_du_second_avis__isnull=False,
            ).order_by("page_cible_id", "start_char_cible")
        )

        self.stdout.write("")
        self.stdout.write(f"  citations                    : {total}")
        self.stdout.write(f"  avec un degré de production  : {avec_degre}")
        self.stdout.write(f"  avec un second avis          : {avec_second_avis}")
        self.stdout.write(
            f"  COMPARABLES (les deux)       : {len(comparables)}",
        )

        if not comparables:
            # LE CAS ORDINAIRE AU DEMARRAGE DE LA CAMPAGNE, et il faut le
            # dire au lieu d'afficher un tableau vide : au 18 aout 2026 la
            # base porte 145 citations et zero degre de production, tous
            # les verdicts etant anterieurs a l'addendum.
            # / The ordinary case at campaign start; say it.
            self.stdout.write("")
            self.stdout.write(
                "  Aucune citation n'a encore les DEUX avis.\n"
                "  Un article n'est comparable qu'après avoir été vérifié "
                "depuis le passage au degré :\n"
                "  le bouton « Vérifier les citations » lance les deux "
                "juges.",
            )
            return

        methodes = {
            lien.methode_du_second_avis for lien in comparables
        }
        self.stdout.write("")
        self.stdout.write(f"  juge de production, seuil    : {seuil_de_production:g}/100")
        for methode in sorted(methodes):
            seuils = {
                lien.seuil_du_second_avis for lien in comparables
                if lien.methode_du_second_avis == methode
            }
            seuils_lisibles = ", ".join(f"{s:g}" for s in sorted(seuils))
            self.stdout.write(
                f"  second juge                  : {methode} "
                f"(seuil {seuils_lisibles}/100)",
            )

        accords = 0
        desaccords = []
        for lien in comparables:
            production_positive = (
                lien.score_de_verification >= seuil_de_production
            )
            second_positif = (
                lien.score_du_second_avis >= lien.seuil_du_second_avis
            )
            if production_positive == second_positif:
                accords += 1
            else:
                desaccords.append((lien, production_positive, second_positif))

        taux = 100 * accords / len(comparables)
        self.stdout.write("")
        self.stdout.write(
            f"  accord                       : {accords}/{len(comparables)} "
            f"({taux:.0f} %)",
        )

        auc = _aire_sous_la_courbe(
            [lien.score_du_second_avis for lien in comparables],
            [
                lien.score_de_verification >= seuil_de_production
                for lien in comparables
            ],
        )
        if auc is None:
            self.stdout.write(
                "  AUC                          : incalculable — le juge "
                "de production n'a qu'un seul verdict sur cet échantillon",
            )
        else:
            self.stdout.write(f"  AUC du second juge           : {auc:.3f}")

        if not desaccords:
            self.stdout.write("")
            self.stdout.write("  Aucun désaccord.")
            return

        # LES DESACCORDS SONT LE LIVRABLE. Le taux d'accord ne dit rien
        # de la verite ; la liste, elle, se relit a la main — et c'est
        # cette relecture qui produira la reference qui manque.
        # / The disagreements are the deliverable.
        self.stdout.write("")
        self.stdout.write(
            f"  {len(desaccords)} désaccord(s) — à relire à la main, "
            f"c'est le livrable de cette campagne :",
        )
        for lien, production_positive, second_positif in \
                desaccords[:options["desaccords"]]:
            self.stdout.write(
                f"   lien {lien.pk:>5} · production "
                f"{lien.score_de_verification:>5.1f} "
                f"({'oui' if production_positive else 'non'}) "
                f"· local {lien.score_du_second_avis:>5.1f} "
                f"({'oui' if second_positif else 'non'}) "
                f"· « {lien.page_cible.title[:44]} »",
            )
        if len(desaccords) > options["desaccords"]:
            self.stdout.write(
                f"   … et {len(desaccords) - options['desaccords']} autres "
                f"(--desaccords N pour en voir plus).",
            )

        contestees = SourceLink.objects.filter(
            type_lien=TypeLien.CITE,
            etat_de_verification=EtatDeVerification.CONTESTE,
            score_du_second_avis__isnull=False,
        ).count()
        if contestees:
            self.stdout.write("")
            self.stdout.write(
                f"  ({contestees} citation(s) contestée(s) par un humain "
                f"portent aussi un second avis : il ne les remplace pas.)",
            )
