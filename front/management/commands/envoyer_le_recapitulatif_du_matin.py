"""
Le recapitulatif du matin : un mail par personne, une fois par jour.
/ The morning recap: one mail per person, once a day.

LOCALISATION :
front/management/commands/envoyer_le_recapitulatif_du_matin.py

LE MAIL PART TOUJOURS APRES LE RUN DE LA NUIT. Deux lignes de cron a
quatre heures d'ecart sont une ESPERANCE d'ordre, pas une garantie :
une nuit chargee suffirait a faire partir le mail avant la fin du
travail qu'il annonce. Cette commande interroge donc la `PasseDeNuit`,
et ATTEND qu'elle soit terminee. Si l'attente expire, elle N'ENVOIE
RIEN et sort en erreur — un mail qui annonce a moitie serait pire
qu'un mail en retard, et un cron en erreur se voit.
/ The mail always follows the night run: it waits, and refuses rather
than half-announcing.

CE QU'ELLE RACONTE : les wikis modifies depuis le dernier mail de
CETTE personne, et ceux dont le perimetre a recu du neuf non repris.
Rien des deux ⇒ aucun mail. C'est le modele Discourse : on n'ecrit
que quand il y a quelque chose a dire.

FLUX :
1. attend la fin de la passe de nuit (sauf --sans-attendre-la-nuit) ;
2. rassemble la matiere, par destinataire (core/services) ;
3. envoie, et enregistre l'envoi — c'est l'enregistrement qui borne le
   prochain, donc qui tient la promesse « un par jour ».
"""

import logging
import time

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string

from core.models import EnvoiDuRecapitulatif
from core.services.passe_de_nuit import passe_en_cours
from core.services.recapitulatif_du_matin import matiere_par_destinataire

logger = logging.getLogger(__name__)

# Entre deux regards sur la passe de nuit. Assez court pour ne pas
# retarder le mail, assez long pour ne pas marteler la base.
# / Between two looks at the night pass.
SECONDES_ENTRE_DEUX_REGARDS = 30


class Command(BaseCommand):
    help = (
        "Envoie le recapitulatif du matin. Attend la fin de la passe "
        "de nuit avant de partir."
    )

    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--attendre-minutes", type=int, default=60,
            dest="attendre_minutes",
            help="Combien de temps attendre la fin de la passe de nuit "
                 "avant d'abandonner (defaut : 60).",
        )
        analyseur_d_arguments.add_argument(
            "--sans-attendre-la-nuit", action="store_true",
            dest="sans_attendre_la_nuit",
            help="Part meme si une passe de nuit tourne. Pour un envoi "
                 "a la main, en connaissance de cause.",
        )
        analyseur_d_arguments.add_argument(
            "--a-blanc", action="store_true", dest="a_blanc",
            help="N'envoie rien : dit qui recevrait quoi.",
        )
        analyseur_d_arguments.add_argument(
            "--destinataire", type=str, default="",
            help="Ne traite qu'un seul destinataire, par son username.",
        )
        analyseur_d_arguments.add_argument(
            "--adresse-de-test", type=str, default="",
            dest="adresse_de_test",
            help="Envoie le recapitulatif a CETTE adresse au lieu des "
                 "vrais destinataires, et n'enregistre AUCUN envoi. "
                 "Pour eprouver la configuration SMTP et le rendu sans "
                 "toucher a la promesse « un mail par jour ».",
        )

    def handle(self, *arguments, **options):
        if not options.get("sans_attendre_la_nuit"):
            self._attendre_la_fin_de_la_nuit(
                options.get("attendre_minutes", 60),
            )

        matiere = matiere_par_destinataire()

        nom_demande = (options.get("destinataire") or "").strip()
        if nom_demande:
            matiere = [
                entree for entree in matiere
                if entree["utilisateur"].username == nom_demande
            ]

        if not matiere:
            self.stdout.write("Rien à raconter ce matin : aucun mail.")
            return

        if options.get("a_blanc"):
            for entree in matiere:
                self.stdout.write(
                    f"  {entree['utilisateur'].username} "
                    f"<{entree['utilisateur'].email}> : "
                    f"{len(entree['wikis_modifies'])} modifié(s), "
                    f"{len(entree['wikis_avec_du_neuf'])} avec du neuf."
                )
            return

        adresse_de_test = (options.get("adresse_de_test") or "").strip()
        if adresse_de_test:
            # UN ESSAI N'EST PAS UN ENVOI : on ne cree aucune trace, donc
            # on ne borne pas le prochain recapitulatif des vraies
            # personnes. Sans cette precaution, tester la configuration
            # SMTP priverait quelqu'un de son mail du lendemain.
            # / A trial writes no record: it must not consume anyone's
            # daily mail.
            entree_d_essai = matiere[0]
            self._envoyer_a(entree_d_essai, adresse=adresse_de_test,
                            enregistrer=False)
            self.stdout.write(
                f"Essai envoyé à {adresse_de_test} — contenu de "
                f"{entree_d_essai['utilisateur'].username} "
                f"({len(entree_d_essai['wikis_modifies'])} modifié(s), "
                f"{len(entree_d_essai['wikis_avec_du_neuf'])} avec du neuf). "
                f"Aucun envoi enregistré."
            )
            return

        envoyes = 0
        en_erreur = 0
        for entree in matiere:
            try:
                self._envoyer_a(entree)
            except Exception as erreur:
                # UN ECHEC N'ARRETE PAS LES AUTRES : un serveur SMTP
                # qui refuse une adresse priverait tout le monde de son
                # recapitulatif. / One refusal must not silence everyone.
                en_erreur += 1
                logger.exception(
                    "recapitulatif du matin : envoi a %s impossible",
                    entree["utilisateur"].username,
                )
                self.stderr.write(
                    f"  {entree['utilisateur'].username} : {erreur}"
                )
                continue
            envoyes += 1

        self.stdout.write(
            f"Récapitulatif du matin : {envoyes} envoyé(s), "
            f"{en_erreur} en erreur."
        )

    def _attendre_la_fin_de_la_nuit(self, attendre_minutes):
        """
        Retient le mail tant que la passe de nuit tourne.
        / Holds the mail while the night pass is running.
        """
        secondes_restantes = max(0, attendre_minutes) * 60
        while True:
            # `passe_en_cours` ferme d'abord les passes ABANDONNEES :
            # sans ce nettoyage, un conteneur tue en pleine nuit
            # bloquerait le recapitulatif POUR TOUJOURS, et personne
            # ne recevrait plus rien — sans un message.
            # / Dead passes are closed first: one kill would otherwise
            # block the mail forever.
            passe = passe_en_cours()
            if passe is None:
                return
            if secondes_restantes <= 0:
                raise CommandError(
                    f"La passe de nuit lancée le "
                    f"{passe.lancee_le:%d/%m/%Y à %H:%M} tourne "
                    f"encore : le récapitulatif n'est pas parti. Il "
                    f"annoncerait un travail à moitié fait. Relancez-le "
                    f"quand elle aura fini. / The night pass is still "
                    f"running; the recap was not sent."
                )
            attente = min(SECONDES_ENTRE_DEUX_REGARDS, secondes_restantes)
            time.sleep(attente)
            secondes_restantes -= attente

    def _envoyer_a(self, entree, adresse=None, enregistrer=True):
        """
        Un mail, puis sa trace — c'est la trace qui borne le suivant.
        / One mail, then its record: the record bounds the next one.

        :param adresse: a qui envoyer, si ce n'est pas au destinataire
            lui-meme (essai de configuration).
        :param enregistrer: False pour un essai — aucun `EnvoiDuRecapitulatif`,
            donc aucune journee consommee pour personne.
        """
        contexte = {
            "destinataire": entree["utilisateur"],
            "depuis": entree["depuis"],
            "wikis_modifies": entree["wikis_modifies"],
            "wikis_avec_du_neuf": entree["wikis_avec_du_neuf"],
            "base_url": settings.SITE_URL.rstrip("/"),
        }
        nombre_de_wikis = (
            len(entree["wikis_modifies"]) + len(entree["wikis_avec_du_neuf"])
        )
        sujet = (
            f"Hypostasia — {nombre_de_wikis} wiki"
            f"{'s' if nombre_de_wikis > 1 else ''} à relire ce matin"
        )
        texte_brut = render_to_string(
            "front/emails/recapitulatif_du_matin.txt", contexte,
        )
        html = render_to_string(
            "front/emails/recapitulatif_du_matin.html", contexte,
        )

        message = EmailMultiAlternatives(
            subject=sujet,
            body=texte_brut,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[adresse or entree["utilisateur"].email],
        )
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)

        if not enregistrer:
            return

        EnvoiDuRecapitulatif.objects.create(
            destinataire=entree["utilisateur"],
            couvre_depuis=entree["depuis"],
            wikis_modifies=len(entree["wikis_modifies"]),
            wikis_avec_du_neuf=len(entree["wikis_avec_du_neuf"]),
        )
