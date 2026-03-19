"""
ViewSet d'authentification — login, register, logout.
Pages standalone (pas des partials HTMX). Formulaires POST classiques avec redirect.
/ Authentication ViewSet — login, register, logout.
Standalone pages (not HTMX partials). Classic POST forms with redirect.

LOCALISATION : front/views_auth.py
"""

import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from rest_framework import viewsets
from rest_framework.decorators import action

from .serializers import LoginSerializer, RegisterSerializer

logger = logging.getLogger(__name__)


class AuthViewSet(viewsets.ViewSet):
    """
    Authentification : login, register, logout.
    Les pages login/register sont des pages completes (pas des partials HTMX).
    / Authentication: login, register, logout.
    Login/register pages are full pages (not HTMX partials).
    """

    @action(detail=False, methods=["GET", "POST"], url_path="login")
    def page_login(self, request):
        """
        Affiche le formulaire de connexion (GET) ou connecte l'utilisateur (POST).
        / Display login form (GET) or log in user (POST).

        LOCALISATION : front/views_auth.py

        FLUX :
        1. GET → render front/login.html (page standalone, pas de HTMX)
        2. POST → validation via LoginSerializer → authenticate() → login() → redirect /
        3. Si echec → re-render login.html avec erreurs inline
        """
        if request.method == "GET":
            # Si deja connecte, rediriger vers l'accueil
            # / If already logged in, redirect to home
            if request.user.is_authenticated:
                return redirect("/")
            return render(request, "front/login.html", {"erreurs": []})

        # Validation via serializer DRF
        # / Validation via DRF serializer
        serializer = LoginSerializer(data=request.POST)
        if not serializer.is_valid():
            return render(request, "front/login.html", {
                "erreurs": _extraire_erreurs_serializer(serializer),
                "donnees_login": {"username": request.POST.get("username", "")},
            })

        donnees = serializer.validated_data
        # Authentifier l'utilisateur via Django auth
        # / Authenticate user via Django auth
        utilisateur_authentifie = authenticate(
            request,
            username=donnees["username"],
            password=donnees["password"],
        )

        if utilisateur_authentifie is None:
            return render(request, "front/login.html", {
                "erreurs": ["Nom d'utilisateur ou mot de passe incorrect."],
                "donnees_login": {"username": donnees["username"]},
            })

        login(request, utilisateur_authentifie)
        logger.info("Login reussi pour %s", utilisateur_authentifie.username)

        # Rediriger vers la page demandee (next) ou l'accueil
        # / Redirect to requested page (next) or home
        url_suivante = request.GET.get("next", "/")
        return redirect(url_suivante)

    @action(detail=False, methods=["GET", "POST"], url_path="register")
    def page_register(self, request):
        """
        Affiche le formulaire d'inscription (GET) ou cree un compte (POST).
        / Display registration form (GET) or create account (POST).

        LOCALISATION : front/views_auth.py

        FLUX :
        1. GET → render front/register.html (page standalone)
        2. POST → validation via RegisterSerializer → create_user() → login() → redirect /
        3. Si echec → re-render register.html avec erreurs inline
        """
        if request.method == "GET":
            if request.user.is_authenticated:
                return redirect("/")
            # Passer le token d'invitation au template (PHASE-25d)
            # / Pass invitation token to template (PHASE-25d)
            token_invitation = request.GET.get("token", "")
            return render(request, "front/register.html", {
                "erreurs": [],
                "token_invitation": token_invitation,
            })

        # Validation via serializer DRF
        # / Validation via DRF serializer
        serializer = RegisterSerializer(data=request.POST)
        if not serializer.is_valid():
            return render(request, "front/register.html", {
                "erreurs": _extraire_erreurs_serializer(serializer),
                "donnees": request.POST,
            })

        donnees = serializer.validated_data

        # Creer le nouvel utilisateur / Create the new user
        nouvel_utilisateur = User.objects.create_user(
            username=donnees["username"],
            email=donnees.get("email", ""),
            password=donnees["password"],
        )
        logger.info("Inscription reussie pour %s", nouvel_utilisateur.username)

        # Offrir un solde de bienvenue si Stripe est active (PHASE-26h)
        # / Give welcome credits if Stripe is enabled (PHASE-26h)
        from django.conf import settings
        if settings.STRIPE_ENABLED:
            from core.models import CreditAccount
            compte_nouveau = CreditAccount.get_ou_creer(nouvel_utilisateur)
            compte_nouveau.crediter(
                montant=3,
                type_transaction="AJUSTEMENT",
                description="Bienvenue — 3 EUR offerts",
            )
            logger.info("Credits bienvenue 3 EUR credites pour %s", nouvel_utilisateur.username)

        # Connecter immediatement / Log in immediately
        login(request, nouvel_utilisateur)

        # Accepter automatiquement l'invitation si un token est present (PHASE-25d)
        # / Auto-accept invitation if a token is present (PHASE-25d)
        token_invitation = request.POST.get("token", "")
        if token_invitation:
            from django.utils import timezone
            from core.models import Invitation
            from .views_invitation import _accepter_invitation
            invitation_a_accepter = Invitation.objects.filter(
                token=token_invitation, acceptee=False,
            ).first()
            if invitation_a_accepter and invitation_a_accepter.expires_at >= timezone.now():
                _accepter_invitation(invitation_a_accepter, nouvel_utilisateur)
                logger.info("Invitation auto-acceptee apres inscription pour %s", nouvel_utilisateur.username)

        return redirect("/")

    @action(detail=False, methods=["GET", "POST"], url_path="token")
    def mon_token(self, request):
        """
        Affiche le token API de l'utilisateur (GET) ou en regenere un nouveau (POST).
        Page standalone, meme structure que login.html.
        / Display user's API token (GET) or regenerate a new one (POST).
        Standalone page, same structure as login.html.

        LOCALISATION : front/views_auth.py

        FLUX :
        1. Si non authentifie → redirect vers /auth/login/?next=/auth/token/
        2. POST → supprime l'ancien token, cree un nouveau, render avec regenere=True
        3. GET → get_or_create du token, render front/mon_token.html
        """
        # Exiger l'authentification / Require authentication
        if not request.user.is_authenticated:
            return redirect("/auth/login/?next=/auth/token/")

        from rest_framework.authtoken.models import Token

        if request.method == "POST":
            # Regenerer le token — supprimer l'ancien et en creer un nouveau
            # / Regenerate token — delete old one and create new
            Token.objects.filter(user=request.user).delete()
            nouveau_token = Token.objects.create(user=request.user)
            logger.info("Token regenere pour %s", request.user.username)
            return render(request, "front/mon_token.html", {
                "token": nouveau_token.key,
                "regenere": True,
            })

        # GET — afficher le token existant ou en creer un premier
        # / GET — show existing token or create first one
        token_existant, token_cree = Token.objects.get_or_create(user=request.user)
        if token_cree:
            logger.info("Premier token cree pour %s", request.user.username)
        return render(request, "front/mon_token.html", {
            "token": token_existant.key,
            "regenere": False,
        })

    @action(detail=False, methods=["GET", "POST"], url_path="logout")
    def deconnexion(self, request):
        """
        Deconnecte l'utilisateur et redirige vers la page de login.
        / Logs out the user and redirects to the login page.

        LOCALISATION : front/views_auth.py
        """
        logger.info("Deconnexion de %s", request.user.username if request.user.is_authenticated else "anonyme")
        logout(request)
        return redirect("/auth/login/")


def _extraire_erreurs_serializer(serializer):
    """
    Extrait les messages d'erreur d'un serializer DRF en liste plate de strings.
    / Extract error messages from a DRF serializer as a flat list of strings.

    LOCALISATION : front/views_auth.py
    """
    liste_erreurs = []
    for champ, messages in serializer.errors.items():
        for message in messages:
            if champ == "non_field_errors":
                liste_erreurs.append(str(message))
            else:
                liste_erreurs.append(f"{champ}: {message}")
    return liste_erreurs
