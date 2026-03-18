"""
ViewSet pour la gestion des groupes d'utilisateurs (PHASE-25c).
/ ViewSet for user group management (PHASE-25c).

LOCALISATION : front/views_groupes.py
"""
import json

from django.contrib.auth.models import User as AuthUser
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from rest_framework import viewsets
from rest_framework.decorators import action

from core.models import GroupeUtilisateurs, Invitation
from .serializers import GroupeAjouterMembreSerializer, GroupeCreateSerializer, InviterEmailSerializer


def _exiger_authentification(request):
    """
    Verifie que l'utilisateur est authentifie.
    / Checks user is authenticated.
    """
    if request.user.is_authenticated:
        return None
    if request.headers.get("HX-Request"):
        return HttpResponse(
            '<p class="text-sm text-red-600 p-3">'
            'Connexion requise. <a href="/auth/login/" class="underline text-blue-600">Se connecter</a>'
            '</p>', status=403,
        )
    from django.shortcuts import redirect
    return redirect("/auth/login/")


class GroupeViewSet(viewsets.ViewSet):
    """
    CRUD pour les groupes d'utilisateurs.
    Chaque utilisateur peut creer ses propres groupes et y ajouter des membres.
    Les groupes servent ensuite au partage de dossiers (DossierPartage avec FK groupe).
    / CRUD for user groups.
    Each user can create their own groups and add members.
    Groups are then used for folder sharing (DossierPartage with group FK).

    LOCALISATION : front/views_groupes.py

    DEPENDENCIES :
    - core.models.GroupeUtilisateurs
    - front/serializers.py (GroupeCreateSerializer, GroupeAjouterMembreSerializer)
    - front/templates/front/includes/groupe_detail.html
    """

    def list(self, request):
        """
        Liste les groupes de l'utilisateur en JSON (pour les selects).
        / Lists user's groups as JSON (for selects).
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        tous_les_groupes_de_utilisateur = GroupeUtilisateurs.objects.filter(
            owner=request.user,
        )
        liste_groupes_json = []
        for groupe in tous_les_groupes_de_utilisateur:
            liste_groupes_json.append({
                "id": groupe.pk,
                "nom": groupe.nom,
                "membres_count": groupe.membres.count(),
            })
        return JsonResponse(liste_groupes_json, safe=False)

    def create(self, request):
        """
        Cree un nouveau groupe d'utilisateurs.
        / Creates a new user group.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        serializer = GroupeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        nom_groupe = serializer.validated_data["nom"]
        nouveau_groupe = GroupeUtilisateurs.objects.create(
            nom=nom_groupe, owner=request.user,
        )

        # Retourne le partial du detail du groupe cree
        # / Return the detail partial of the created group
        return self._render_detail_groupe(request, nouveau_groupe)

    def destroy(self, request, pk=None):
        """
        Supprime un groupe (seul l'owner peut supprimer).
        / Deletes a group (only owner can delete).
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        groupe_a_supprimer = get_object_or_404(
            GroupeUtilisateurs, pk=pk, owner=request.user,
        )
        nom_groupe = groupe_a_supprimer.nom
        groupe_a_supprimer.delete()

        reponse = HttpResponse(
            f'<p class="text-sm text-green-600 p-2">Groupe « {nom_groupe} » supprime.</p>'
        )
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Groupe « {nom_groupe} » supprime"},
        })
        return reponse

    @action(detail=True, methods=["POST"], url_path="ajouter_membre")
    def ajouter_membre(self, request, pk=None):
        """
        Ajoute un membre au groupe par username.
        / Adds a member to the group by username.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        groupe_cible = get_object_or_404(
            GroupeUtilisateurs, pk=pk, owner=request.user,
        )

        serializer = GroupeAjouterMembreSerializer(data=request.data)
        if not serializer.is_valid():
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        username_a_ajouter = serializer.validated_data["username"]
        utilisateur_a_ajouter = AuthUser.objects.filter(
            username__iexact=username_a_ajouter,
        ).first()

        if not utilisateur_a_ajouter:
            return HttpResponse(
                '<p class="text-sm text-red-500">Utilisateur introuvable.</p>',
                status=400,
            )

        groupe_cible.membres.add(utilisateur_a_ajouter)

        return self._render_detail_groupe(request, groupe_cible)

    @action(detail=True, methods=["POST"], url_path="retirer_membre")
    def retirer_membre(self, request, pk=None):
        """
        Retire un membre du groupe par user_id.
        / Removes a member from the group by user_id.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        groupe_cible = get_object_or_404(
            GroupeUtilisateurs, pk=pk, owner=request.user,
        )

        user_id_a_retirer = request.data.get("user_id")
        if user_id_a_retirer:
            groupe_cible.membres.remove(user_id_a_retirer)

        return self._render_detail_groupe(request, groupe_cible)

    @action(detail=True, methods=["GET"], url_path="detail")
    def detail_groupe(self, request, pk=None):
        """
        Retourne le partial HTML des membres du groupe.
        / Returns the HTML partial of group members.
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        groupe_cible = get_object_or_404(
            GroupeUtilisateurs, pk=pk, owner=request.user,
        )

        return self._render_detail_groupe(request, groupe_cible)

    @action(detail=True, methods=["POST"], url_path="inviter")
    def inviter(self, request, pk=None):
        """
        Invite un utilisateur par email a rejoindre un groupe (PHASE-25d).
        Si l'email correspond a un utilisateur existant → ajout direct.
        Sinon → creation d'une Invitation + envoi d'email.
        / Invites a user by email to join a group (PHASE-25d).
        If email matches an existing user → direct addition.
        Otherwise → create Invitation + send email.

        LOCALISATION : front/views_groupes.py
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        groupe_cible = get_object_or_404(
            GroupeUtilisateurs, pk=pk, owner=request.user,
        )

        serializer = InviterEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        email_invite = serializer.validated_data["email"]

        # Rejeter l'auto-invitation
        # / Reject self-invitation
        if request.user.email and email_invite.lower() == request.user.email.lower():
            return HttpResponse(
                '<p class="text-sm text-red-500">Vous ne pouvez pas vous inviter vous-meme.</p>',
                status=400,
            )

        # Verifier si un utilisateur avec cet email existe deja
        # / Check if a user with this email already exists
        utilisateur_existant = AuthUser.objects.filter(email__iexact=email_invite).first()

        if utilisateur_existant:
            # Ajout direct au groupe / Direct addition to group
            groupe_cible.membres.add(utilisateur_existant)
            return self._render_detail_groupe(request, groupe_cible)

        # Verifier si une invitation est deja en attente
        # / Check if an invitation is already pending
        from django.utils import timezone
        invitation_existante = Invitation.objects.filter(
            groupe=groupe_cible, email__iexact=email_invite,
            acceptee=False, expires_at__gte=timezone.now(),
        ).exists()

        if invitation_existante:
            return HttpResponse(
                '<p class="text-sm text-amber-600">Invitation deja envoyee a cette adresse.</p>',
                status=200,
            )

        # Creer et envoyer l'invitation
        # / Create and send invitation
        from .views_invitation import creer_invitation
        creer_invitation(
            dossier=None,
            groupe=groupe_cible,
            email=email_invite,
            invite_par=request.user,
        )

        return self._render_detail_groupe(request, groupe_cible)

    def _render_detail_groupe(self, request, groupe):
        """
        Helper : rend le partial inline des membres d'un groupe via template.
        / Helper: renders the inline partial of group members via template.

        LOCALISATION : front/views_groupes.py
        """
        tous_les_membres_du_groupe = groupe.membres.all()
        return render(request, "front/includes/groupe_detail.html", {
            "groupe": groupe,
            "tous_les_membres": tous_les_membres_du_groupe,
        })
