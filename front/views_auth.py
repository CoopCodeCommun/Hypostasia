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
            return render(request, "front/register.html", {"erreurs": []})

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

        # Connecter immediatement / Log in immediately
        login(request, nouvel_utilisateur)
        return redirect("/")

    @action(detail=False, methods=["POST"], url_path="logout")
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
