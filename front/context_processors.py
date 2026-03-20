"""
Context processor pour injecter le solde de credits dans tous les templates.
/ Context processor to inject credit balance into all templates.
"""

from django.conf import settings


def solde_credits(request):
    """
    Injecte `stripe_enabled` et `solde_credits_euros` dans le contexte template.
    Ne fait la requete DB que si l'utilisateur est authentifie et STRIPE_ENABLED=True.
    / Injects `stripe_enabled` and `solde_credits_euros` into template context.
    Only queries DB if user is authenticated and STRIPE_ENABLED=True.

    LOCALISATION : front/context_processors.py
    """
    stripe_est_active = getattr(settings, "STRIPE_ENABLED", False)

    if not stripe_est_active:
        return {
            "stripe_enabled": False,
            "solde_credits_euros": None,
        }

    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {
            "stripe_enabled": True,
            "solde_credits_euros": None,
        }

    # Import ici pour eviter les imports circulaires
    # / Import here to avoid circular imports
    from core.models import CreditAccount

    compte_credits = CreditAccount.get_ou_creer(request.user)
    return {
        "stripe_enabled": True,
        "solde_credits_euros": compte_credits.solde_euros,
    }
