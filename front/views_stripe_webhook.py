"""
Webhook Stripe — reception des evenements de paiement.
Vue Django classique @csrf_exempt (pas un ViewSet — Stripe envoie du POST brut).
/ Stripe webhook — payment event reception.
Classic Django view @csrf_exempt (not a ViewSet — Stripe sends raw POST).
"""

import logging

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from front.services_stripe import traiter_paiement_stripe

logger = logging.getLogger("front")


@csrf_exempt
def stripe_webhook(request):
    """
    Recoit les evenements Stripe (checkout.session.completed).
    Verifie la signature puis appelle traiter_paiement_stripe() (idempotent).
    / Receives Stripe events (checkout.session.completed).
    Verifies signature then calls traiter_paiement_stripe() (idempotent).

    LOCALISATION : front/views_stripe_webhook.py
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    # Configurer la cle API Stripe
    # / Configure Stripe API key
    stripe.api_key = settings.STRIPE_SECRET_KEY

    corps_requete = request.body
    signature_stripe = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    # Verifier la signature Stripe
    # / Verify Stripe signature
    try:
        evenement = stripe.Webhook.construct_event(
            corps_requete, signature_stripe, settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        logger.warning("stripe_webhook: corps de requete invalide")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning("stripe_webhook: signature invalide")
        return HttpResponse(status=400)

    # Ecouter uniquement checkout.session.completed
    # / Listen only to checkout.session.completed
    type_evenement = evenement.get("type", "")
    if type_evenement == "checkout.session.completed":
        session_donnees = evenement["data"]["object"]
        identifiant_session = session_donnees.get("id", "")
        logger.info(
            "stripe_webhook: checkout.session.completed — session=%s",
            identifiant_session,
        )
        try:
            traiter_paiement_stripe(identifiant_session)
        except Exception as erreur:
            logger.error(
                "stripe_webhook: erreur traitement session=%s — %s",
                identifiant_session, erreur,
            )
    else:
        logger.debug("stripe_webhook: evenement ignore — type=%s", type_evenement)

    return HttpResponse(status=200)
