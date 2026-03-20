"""
CreditViewSet — gestion des credits prepays et paiement Stripe.
/ CreditViewSet — prepaid credits management and Stripe payment.
"""

import logging

import stripe
from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from rest_framework import serializers, viewsets
from rest_framework.decorators import action

from core.models import CreditAccount, CreditTransaction
from front.services_stripe import traiter_paiement_stripe

logger = logging.getLogger("front")


class CreerCheckoutSerializer(serializers.Serializer):
    """Valide le montant choisi pour la recharge Stripe.
    / Validates the chosen amount for Stripe top-up.
    """
    montant_euros = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=1,
        help_text="Montant en euros a recharger / Amount in euros to top up",
    )


class CreditViewSet(viewsets.ViewSet):
    """
    Gestion des credits prepays : solde, historique, recharge Stripe.
    / Prepaid credits management: balance, history, Stripe top-up.

    LOCALISATION : front/views_credits.py
    """

    def list(self, request):
        """
        Page "Mes credits" : solde + historique + boutons de recharge.
        / "My credits" page: balance + history + top-up buttons.
        """
        if not request.user.is_authenticated:
            return HttpResponse("Non authentifie", status=401)

        compte_credits = CreditAccount.get_ou_creer(request.user)
        toutes_les_transactions = CreditTransaction.objects.filter(
            compte=compte_credits,
        ).order_by("-created_at")[:50]

        contexte = {
            "compte_credits": compte_credits,
            "transactions": toutes_les_transactions,
            "montants_recharge": settings.STRIPE_MONTANTS_RECHARGE,
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "stripe_enabled": settings.STRIPE_ENABLED,
        }

        # Si requete HTMX → partial, sinon → page complete via base.html
        # / If HTMX request → partial, otherwise → full page via base.html
        if request.headers.get("HX-Request"):
            return render(request, "front/includes/credits_page.html", contexte)
        return render(request, "front/base.html", {
            **contexte,
            "credits_page_preloaded": True,
        })

    @action(detail=False, methods=["GET"])
    def solde(self, request):
        """
        Partial badge solde pour refresh OOB dans la navbar.
        / Balance badge partial for OOB refresh in navbar.
        """
        if not request.user.is_authenticated:
            return HttpResponse("")

        compte_credits = CreditAccount.get_ou_creer(request.user)
        return render(request, "front/includes/credits_solde_badge.html", {
            "solde_credits_euros": compte_credits.solde_euros,
            "stripe_enabled": settings.STRIPE_ENABLED,
        })

    @action(detail=False, methods=["POST"])
    def creer_checkout(self, request):
        """
        Cree une Stripe Checkout Session et redirige le navigateur.
        / Creates a Stripe Checkout Session and redirects the browser.
        """
        if not request.user.is_authenticated:
            return HttpResponse("Non authentifie", status=401)

        if not settings.STRIPE_ENABLED:
            return HttpResponse("Stripe desactive", status=400)

        # Validation du montant via serializer DRF
        # / Amount validation via DRF serializer
        serializer = CreerCheckoutSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("creer_checkout: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f"Montant invalide : {serializer.errors}", status=400,
            )

        montant_euros = serializer.validated_data["montant_euros"]
        montant_centimes = int(montant_euros * 100)

        # Configurer la cle API Stripe
        # / Configure Stripe API key
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Construire l'URL de base depuis la requete
        # / Build base URL from request
        url_base = f"{request.scheme}://{request.get_host()}"

        # Creer la session Stripe Checkout
        # / Create Stripe Checkout session
        try:
            # Email pre-rempli pour eviter que Stripe le demande
            # Carte bancaire uniquement (pas de virement, pas de PayPal)
            # / Pre-fill email so Stripe doesn't ask for it
            # / Card only (no bank transfer, no PayPal)
            session_stripe = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                customer_email=request.user.email or None,
                client_reference_id=str(request.user.pk),
                line_items=[{
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": f"Recharge credits Hypostasia — {montant_euros} EUR",
                        },
                        "unit_amount": montant_centimes,
                    },
                    "quantity": 1,
                }],
                success_url=f"{url_base}/credits/succes/?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{url_base}/credits/annule/",
                metadata={"user_id": str(request.user.pk)},
            )
        except stripe.error.StripeError as erreur_stripe:
            logger.error("creer_checkout: erreur Stripe — %s", erreur_stripe)
            return HttpResponse(
                f"Erreur Stripe : {erreur_stripe}", status=500,
            )

        logger.info(
            "creer_checkout: session %s creee pour user=%s montant=%s EUR",
            session_stripe.id, request.user.username, montant_euros,
        )

        # Retourner un partial HTML qui redirige le navigateur via JS
        # / Return HTML partial that redirects browser via JS
        return HttpResponse(
            f'<script>window.location.href = "{session_stripe.url}";</script>',
            content_type="text/html",
        )

    @action(detail=False, methods=["GET"])
    def succes(self, request):
        """
        Page de retour apres paiement Stripe reussi.
        Appelle traiter_paiement_stripe() pour crediter le compte (idempotent).
        / Return page after successful Stripe payment.
        Calls traiter_paiement_stripe() to credit account (idempotent).
        """
        if not request.user.is_authenticated:
            return HttpResponse("Non authentifie", status=401)

        identifiant_session = request.GET.get("session_id", "")
        if not identifiant_session:
            return HttpResponse("session_id manquant", status=400)

        # Configurer la cle API Stripe
        # / Configure Stripe API key
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Tenter de traiter le paiement (idempotent)
        # / Try to process payment (idempotent)
        try:
            transaction_resultat = traiter_paiement_stripe(identifiant_session)
        except Exception as erreur:
            logger.error("succes: erreur traitement paiement — %s", erreur)
            transaction_resultat = None

        compte_credits = CreditAccount.get_ou_creer(request.user)

        contexte = {
            "transaction": transaction_resultat,
            "compte_credits": compte_credits,
            "paiement_confirme": transaction_resultat is not None,
            "session_id": identifiant_session,
        }

        if request.headers.get("HX-Request"):
            return render(request, "front/includes/credits_succes.html", contexte)
        return render(request, "front/base.html", {
            **contexte,
            "credits_succes_preloaded": True,
        })

    @action(detail=False, methods=["GET"])
    def annule(self, request):
        """
        Page affichee quand l'utilisateur annule le paiement Stripe.
        / Page displayed when user cancels Stripe payment.
        """
        if request.headers.get("HX-Request"):
            return render(request, "front/includes/credits_annule.html")
        return render(request, "front/base.html", {
            "credits_annule_preloaded": True,
        })
