"""
Combien coute un swap cible, compare au rechargement qu'il remplace ?
/ What does a targeted swap cost, against the reload it replaces?

LOCALISATION : benchmarks/edition_par_blocs/banc/ LECTURE SEULE, aucune ecriture.

Le swap rend UN bloc, mais il construit les blocs de TOUTE la page pour
cela (c'est voulu : un second chemin de rendu finirait par diverger). Il
faut donc savoir ce que ca coute — et le comparer a ce qu'il remplace,
c'est-a-dire le rendu de la page entiere que `lectureReload` allait
chercher en une SECONDE requete HTTP.
"""
import json
import time

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from core.models import ElementDocument, Page
from front.services.rendu_elements import construire_les_blocs_de_lecture
from hypostasis_extractor.views_element import _html_du_bloc

Utilisateur = get_user_model()
jonas = Utilisateur.objects.get(username="jonas")
fabrique = RequestFactory()


def chronometrer(fonction, tours=5):
    """Rend la mediane, en millisecondes. / Returns the median, in ms."""
    mesures = []
    for _ in range(tours):
        depart = time.perf_counter()
        resultat = fonction()
        mesures.append((time.perf_counter() - depart) * 1000)
        dernier = resultat
    mesures.sort()
    return round(mesures[len(mesures) // 2], 1), round(mesures[0], 1), dernier


sortie = {}
for page_id in (19, 3):
    page = Page.objects.get(pk=page_id)
    element = ElementDocument.objects.filter(page_id=page_id).order_by("ordre").first()
    requete = fabrique.get(f"/elements/{element.pk}/bloc/")
    requete.user = jonas
    # Un context processor lit la session : sans elle, le rendu leve.
    # / A context processor reads the session.
    requete.session = SessionStore()

    # 1. Le swap cible : construire les blocs, puis rendre le seul vise.
    med_bloc, min_bloc, html_bloc = chronometrer(
        lambda: _html_du_bloc(requete, element, pour_swap_oob=True)
    )

    # 2. Le service seul, sans le rendu du gabarit.
    med_service, min_service, blocs = chronometrer(
        lambda: construire_les_blocs_de_lecture(page)
    )

    # 3. Ce que le swap REMPLACE : le rendu de toute la zone de lecture,
    #    que `lectureReload` allait chercher en une seconde requete HTTP.
    from django.template.loader import render_to_string
    med_page, min_page, html_page = chronometrer(
        lambda: render_to_string(
            "front/includes/_blocs_elements.html",
            {"blocs_de_lecture": construire_les_blocs_de_lecture(page),
             "la_note_est_modifiable": True},
            request=requete,
        )
    )

    sortie[f"page_{page_id}"] = {
        "blocs": len(blocs),
        "caracteres_de_la_note": sum(len(b["element"].texte) for b in blocs),
        "swap_d_un_bloc_median_ms": med_bloc,
        "swap_d_un_bloc_min_ms": min_bloc,
        "octets_du_bloc": len(html_bloc or ""),
        "dont_service_median_ms": med_service,
        "rendu_de_TOUTE_la_zone_median_ms": med_page,
        "octets_de_toute_la_zone": len(html_page),
        "rapport_octets": round(len(html_page) / max(1, len(html_bloc or "")), 1),
    }

# La sortie est ECRITE, pas seulement imprimee : un chiffre
# annonce dans un document doit avoir sa source dans le depot.
# / Written, not just printed: every number needs its source.
with open("/tmp/resultats-cout-du-rendu-d-un-bloc.json", "w") as _f:
    import json as _json
    _json.dump(sortie, _f, ensure_ascii=False, indent=1)
print("@@@JSON@@@")
print(json.dumps(sortie, ensure_ascii=False, indent=1))
