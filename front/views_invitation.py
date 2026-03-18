"""
ViewSet pour la gestion des invitations par email (PHASE-25d).
/ ViewSet for email invitation management (PHASE-25d).

LOCALISATION : front/views_invitation.py
"""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import viewsets

from core.models import (
    DossierPartage, Invitation, VisibiliteDossier,
)

logger = logging.getLogger(__name__)


class InvitationViewSet(viewsets.ViewSet):
    """
    Gestion des invitations par email.
    Le retrieve utilise le token hex (64 caracteres) comme pk.
    / Email invitation management.
    Retrieve uses the hex token (64 chars) as pk.

    LOCALISATION : front/views_invitation.py
    """
    lookup_value_regex = r'[a-f0-9]{64}'

    def retrieve(self, request, pk=None):
        """
        Accepte une invitation via son token.
        - Si expiree ou deja acceptee → page erreur.
        - Si anonyme → redirect vers /auth/register/?token=...
        - Si connecte → _accepter_invitation() → redirect /
        / Accept an invitation via its token.
        - If expired or already accepted → error page.
        - If anonymous → redirect to /auth/register/?token=...
        - If authenticated → _accepter_invitation() → redirect /

        LOCALISATION : front/views_invitation.py
        """
        token_invitation = pk

        # Chercher l'invitation par token
        # / Find invitation by token
        invitation_trouvee = Invitation.objects.filter(
            token=token_invitation,
        ).select_related("dossier", "groupe", "invite_par").first()

        if not invitation_trouvee:
            return render(request, "front/invitation_erreur.html", {
                "message_erreur": "Cette invitation est invalide ou n'existe pas.",
            })

        if invitation_trouvee.acceptee:
            return render(request, "front/invitation_erreur.html", {
                "message_erreur": "Cette invitation a deja ete acceptee.",
            })

        if invitation_trouvee.expires_at < timezone.now():
            return render(request, "front/invitation_erreur.html", {
                "message_erreur": "Cette invitation a expire.",
            })

        # Si anonyme → redirect vers inscription avec le token
        # / If anonymous → redirect to registration with token
        if not request.user.is_authenticated:
            return redirect(f"/auth/register/?token={token_invitation}")

        # Si connecte → accepter l'invitation
        # / If authenticated → accept invitation
        _accepter_invitation(invitation_trouvee, request.user)
        return redirect("/")


def _accepter_invitation(invitation, utilisateur):
    """
    Marque l'invitation comme acceptee et cree le partage/adhesion correspondant.
    - Invitation dossier → DossierPartage + auto-upgrade visibilite
    - Invitation groupe → ajout comme membre du groupe
    / Marks invitation as accepted and creates the corresponding share/membership.
    - Folder invitation → DossierPartage + auto-upgrade visibility
    - Group invitation → add as group member

    LOCALISATION : front/views_invitation.py
    """
    invitation.acceptee = True
    invitation.save(update_fields=["acceptee"])

    if invitation.dossier:
        # Creer le partage de dossier / Create folder share
        DossierPartage.objects.get_or_create(
            dossier=invitation.dossier,
            utilisateur=utilisateur,
            defaults={"groupe": None},
        )
        # Auto-upgrade visibilite : prive → partage
        # / Auto-upgrade visibility: private → shared
        if invitation.dossier.visibilite == VisibiliteDossier.PRIVE:
            invitation.dossier.visibilite = VisibiliteDossier.PARTAGE
            invitation.dossier.save(update_fields=["visibilite"])
        logger.info(
            "Invitation acceptee: %s rejoint dossier '%s' (invite par %s)",
            utilisateur.username, invitation.dossier.name, invitation.invite_par.username,
        )

    if invitation.groupe:
        # Ajouter au groupe / Add to group
        invitation.groupe.membres.add(utilisateur)
        logger.info(
            "Invitation acceptee: %s rejoint groupe '%s' (invite par %s)",
            utilisateur.username, invitation.groupe.nom, invitation.invite_par.username,
        )


def envoyer_email_invitation(invitation):
    """
    Envoie l'email d'invitation avec le lien d'acceptation.
    Utilise les templates txt/html pour dossier ou groupe.
    / Sends the invitation email with acceptance link.
    Uses txt/html templates for folder or group.

    LOCALISATION : front/views_invitation.py
    """
    lien_invitation = f"{settings.SITE_URL}/invitation/{invitation.token}/"

    if invitation.dossier:
        contexte_email = {
            "invite_par_username": invitation.invite_par.username,
            "dossier_nom": invitation.dossier.name,
            "lien_invitation": lien_invitation,
            "date_expiration": invitation.expires_at,
        }
        sujet = f"{invitation.invite_par.username} vous invite a consulter un dossier sur Hypostasia"
        texte_brut = render_to_string("front/emails/invitation_dossier.txt", contexte_email)
        html_email = render_to_string("front/emails/invitation_dossier.html", contexte_email)
    else:
        contexte_email = {
            "invite_par_username": invitation.invite_par.username,
            "groupe_nom": invitation.groupe.nom,
            "lien_invitation": lien_invitation,
            "date_expiration": invitation.expires_at,
        }
        sujet = f"{invitation.invite_par.username} vous invite a rejoindre un groupe sur Hypostasia"
        texte_brut = render_to_string("front/emails/invitation_groupe.txt", contexte_email)
        html_email = render_to_string("front/emails/invitation_groupe.html", contexte_email)

    send_mail(
        subject=sujet,
        message=texte_brut,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        html_message=html_email,
        fail_silently=False,
    )
    logger.info("Email d'invitation envoye a %s (token: %s...)", invitation.email, invitation.token[:8])


def creer_invitation(dossier, groupe, email, invite_par):
    """
    Cree une invitation avec token unique et date d'expiration, puis envoie l'email.
    / Creates an invitation with unique token and expiry date, then sends the email.

    LOCALISATION : front/views_invitation.py
    """
    token_unique = secrets.token_hex(32)
    date_expiration = timezone.now() + timedelta(days=7)

    nouvelle_invitation = Invitation.objects.create(
        dossier=dossier,
        groupe=groupe,
        email=email,
        invite_par=invite_par,
        token=token_unique,
        expires_at=date_expiration,
    )

    envoyer_email_invitation(nouvelle_invitation)
    return nouvelle_invitation
