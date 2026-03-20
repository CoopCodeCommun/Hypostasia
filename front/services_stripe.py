"""
Service partage pour le traitement des paiements Stripe.
Fonction unique idempotente appelee par le webhook ET par la page de retour succes.
/ Shared service for Stripe payment processing.
Single idempotent function called by both webhook AND success return page.
"""

import logging
from decimal import Decimal

import stripe
from django.contrib.auth.models import User

from core.models import CreditAccount, CreditTransaction

logger = logging.getLogger("front")


def traiter_paiement_stripe(identifiant_session_stripe):
    """
    Verifie le paiement Stripe et credite le compte si le paiement est confirme.
    Idempotent : ne credite qu'une seule fois grace au payment_intent unique.
    Appelee par le webhook ET par la page de retour succes.
    / Verify Stripe payment and credit account if confirmed. Idempotent.
    Called by both webhook AND success return page.

    LOCALISATION : front/services_stripe.py

    Retourne :
    - La CreditTransaction si credit effectue ou deja fait
    - None si le paiement n'est pas encore confirme par Stripe
    / Returns:
    - The CreditTransaction if credit done or already done
    - None if payment not yet confirmed by Stripe
    """
    # Recuperer la session Stripe via l'API
    # / Retrieve the Stripe session via the API
    session_stripe = stripe.checkout.Session.retrieve(identifiant_session_stripe)
    if session_stripe.payment_status != "paid":
        logger.info(
            "traiter_paiement_stripe: session %s pas encore payee (status=%s)",
            identifiant_session_stripe, session_stripe.payment_status,
        )
        return None

    # Idempotence : verifier si ce payment_intent a deja ete traite
    # / Idempotency: check if this payment_intent was already processed
    identifiant_payment_intent = session_stripe.payment_intent
    transaction_existante = CreditTransaction.objects.filter(
        stripe_payment_intent_id=identifiant_payment_intent,
    ).first()
    if transaction_existante:
        logger.info(
            "traiter_paiement_stripe: payment_intent %s deja traite — transaction pk=%s",
            identifiant_payment_intent, transaction_existante.pk,
        )
        return transaction_existante

    # Crediter le compte de l'utilisateur
    # / Credit the user's account
    utilisateur = User.objects.get(pk=session_stripe.client_reference_id)
    montant_en_euros = Decimal(str(session_stripe.amount_total)) / Decimal("100")
    compte_credits = CreditAccount.get_ou_creer(utilisateur)

    logger.info(
        "traiter_paiement_stripe: credit %s EUR pour user=%s (pi=%s)",
        montant_en_euros, utilisateur.username, identifiant_payment_intent,
    )

    return compte_credits.crediter(
        montant=montant_en_euros,
        type_transaction="RECHARGE",
        stripe_payment_intent_id=identifiant_payment_intent,
        description=f"Recharge Stripe — {montant_en_euros} EUR",
    )
