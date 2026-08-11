"""
Middlewares de l'app core.
/ Core app middlewares.

LOCALISATION : core/middleware.py
"""


class EmpecherLeCacheDuHtml:
    """
    Pose Cache-Control: no-cache sur les reponses HTML.
    / Sets Cache-Control: no-cache on HTML responses.

    LOCALISATION : core/middleware.py

    POURQUOI (audit UX D14) : sans directive de cache, le navigateur
    applique son cache heuristique et peut servir un document HTML
    PERIME apres un deploiement — constate en direct : la barre de
    navigation absente du document affiche alors que le serveur la
    renvoyait. no-cache force la revalidation a chaque affichage, sans
    interdire le stockage (les statiques, eux, gardent leur cache).
    / Without a cache directive, browsers heuristically cache HTML and
    serve stale UI after deploys. no-cache forces revalidation.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reponse = self.get_response(request)

        type_de_contenu = reponse.get("Content-Type", "")
        est_du_html = "text/html" in type_de_contenu
        cache_deja_regle = reponse.has_header("Cache-Control")

        if est_du_html and not cache_deja_regle:
            reponse["Cache-Control"] = "no-cache"
        return reponse
