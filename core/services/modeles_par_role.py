"""
La resolution d'un modele IA par son usage.
/ Resolving an AI model from its use.

LOCALISATION : core/services/modeles_par_role.py

UN SEUL POINT D'ENTREE : `modele_du_role(role)`.

Le redacteur d'article et le juge de verification sont deux metiers
opposes. Cette fonction est ce qui les separe : chaque endroit qui cree
un `ExtractionJob` demande le modele de SON role, et jamais
`Configuration.ai_model` directement.

LE REPLI EST LA REGLE, PAS L'EXCEPTION. Un role sans ligne rend le
modele de la `Configuration`. La table peut donc rester vide : rien ne
change tant que personne n'a affecte quoi que ce soit.

COMMUNICATION :
Appelants : front/views_synthese.py (production d'articles et
verification), front/views.py (synthese par note),
core/services/verification.py (le juge par defaut),
front/management/commands/ (les commandes etalons).
/ Single entry point; callers ask for their role's model, never for
Configuration.ai_model directly. An unassigned role falls back.
"""

import logging

logger = logging.getLogger(__name__)


def modele_du_role(role):
    """
    Retourne l'AIModel affecte a un usage, ou le modele de la
    Configuration si aucun ne l'est.
    / Returns the AIModel bound to a use, or the Configuration's one.

    LOCALISATION : core/services/modeles_par_role.py

    FLUX :
    1. Verifie que le role existe — un nom inconnu LEVE
    2. Cherche la ligne de `ModeleParRole` pour ce role
    3. A defaut, rend `Configuration.ai_model` (qui peut valoir None)
    / 1. Unknown role raises  2. Role row  3. Configuration fallback

    UN ROLE INCONNU LEVE, IL NE RETOMBE PAS. Une faute de frappe dans un
    nom de role retomberait sinon sur le modele generique : le juge
    specialise ne serait jamais appele, et rien ne le dirait.
    / An unknown role raises: a typo must never silently degrade.

    None EST UNE REPONSE VALIDE, et c'est le comportement d'avant la
    table : aucun modele configure, la vue stampe un job sans modele, et
    c'est la tache qui echoue avec son propre message. Lever ici
    transformerait ce cas en erreur 500 sur l'endpoint.
    / None is a valid answer, exactly as before this table existed.

    :param role: une valeur de `RoleDeModele`
    :return: une instance d'AIModel, ou None
    """
    from core.models import Configuration, ModeleParRole, RoleDeModele

    if role not in RoleDeModele.values:
        raise ValueError(
            f"Rôle de modèle inconnu : « {role} ». "
            f"Rôles connus : {', '.join(RoleDeModele.values)}."
        )

    affectation = ModeleParRole.objects.filter(
        role=role,
    ).select_related("modele").first()
    if affectation is not None:
        return affectation.modele

    modele_de_la_configuration = Configuration.get_solo().ai_model
    logger.debug(
        "modele_du_role: aucun modèle affecté au rôle « %s » — repli sur "
        "la Configuration (%s).", role, modele_de_la_configuration,
    )
    return modele_de_la_configuration
