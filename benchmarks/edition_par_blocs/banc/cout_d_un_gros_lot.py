"""
Combien coute un GROS lot ? / What does a BIG batch cost?

LOCALISATION : benchmarks/edition_par_blocs/banc/

La borne du lot est a 500 blocs, soit 2,4x la plus grosse note de la base.
Elle protege de l'absurde — mais pas de la lenteur. Un lot fait un verrou
et une reconciliation PAR BLOC MODIFIE : il faut savoir ce que coutent
210 d'un coup, sur la plus grosse note reelle.

AUCUNE ECRITURE N'EST CONSERVEE : chaque essai tourne dans une transaction
qu'on FAIT ECHOUER, et les textes sont relus apres coup.
"""
import json
import time

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.db import transaction
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import ElementDocument, Page
from hypostasis_extractor.views_element import ElementViewSet

Utilisateur = get_user_model()
jonas = Utilisateur.objects.get(username="thales")  # le proprietaire de la page 19
fabrique = APIRequestFactory()
vue = ElementViewSet.as_view({"post": "corriger_en_lot"})


class AnnulationVolontaire(Exception):
    pass


PAGE = 19
elements = list(
    ElementDocument.objects.filter(page_id=PAGE).order_by("ordre")
)
empreintes_avant = {e.pk: e.texte for e in elements}


def poster(blocs):
    requete = fabrique.post(
        "/elements/corriger_en_lot/", {"blocs": blocs}, format="json",
    )
    # `force_authenticate` court-circuite la SessionAuthentication, donc
    # sa verification CSRF : on mesure la vue, pas le jeton.
    # / Bypasses SessionAuthentication's CSRF check: we measure the view.
    force_authenticate(requete, user=jonas)
    requete.session = SessionStore()
    return vue(requete)


def essai(nom, blocs):
    depart = time.perf_counter()
    statut = None
    corps = ""
    try:
        with transaction.atomic():
            reponse = poster(blocs)
            statut = reponse.status_code
            if hasattr(reponse, "render"):
                reponse.render()
            corps = reponse.content.decode()[:400]
            raise AnnulationVolontaire()
    except AnnulationVolontaire:
        pass
    duree = (time.perf_counter() - depart) * 1000
    n = len(blocs)
    return {
        "blocs_envoyes": n,
        "statut": statut,
        "duree_ms": round(duree, 1),
        "ms_par_bloc": round(duree / max(1, n), 2),
        "extrait_du_compte_rendu": " ".join(corps.split())[:200],
    }


sortie = {"page": PAGE, "blocs_de_la_note": len(elements)}

# 1. Le pire cas : TOUS les blocs modifies.
sortie["tous_modifies"] = essai(
    "tous",
    [{"identifiant_stable": str(e.identifiant_stable),
      "texte": e.texte[:len(e.texte) // 2] + "XX" + e.texte[len(e.texte) // 2:]}
     for e in elements],
)

# 2. Le cas realiste d'une session de correction : 20 blocs touches,
#    190 renvoyes inchanges.
blocs_realistes = []
for i, e in enumerate(elements):
    if i % 10 == 0:
        texte = e.texte[:5] + "ZZ" + e.texte[5:]
    else:
        texte = e.texte
    blocs_realistes.append(
        {"identifiant_stable": str(e.identifiant_stable), "texte": texte})
sortie["session_realiste_21_touches_sur_210"] = essai("realiste", blocs_realistes)

# 3. Le nettoyage post-Docling : 30 blocs VIDES d'un coup.
blocs_vides = []
for i, e in enumerate(elements):
    texte = "" if 40 <= i < 70 else e.texte
    blocs_vides.append(
        {"identifiant_stable": str(e.identifiant_stable), "texte": texte})
sortie["nettoyage_30_blocs_vides"] = essai("vidage", blocs_vides)

# 4. Le cas ou RIEN n'a change : le lot doit etre quasi gratuit.
sortie["aucun_changement"] = essai(
    "rien",
    [{"identifiant_stable": str(e.identifiant_stable), "texte": e.texte}
     for e in elements],
)

# VERIFICATION : rien n'a bouge en base.
modifies = []
for e in ElementDocument.objects.filter(page_id=PAGE):
    if e.texte != empreintes_avant.get(e.pk) or e.masque:
        modifies.append(e.ordre)
sortie["verification_aucune_ecriture"] = {
    "elements_relus": len(empreintes_avant),
    "elements_modifies_ou_masques": modifies,
}

# La sortie est ECRITE, pas seulement imprimee : un chiffre
# annonce dans un document doit avoir sa source dans le depot.
# / Written, not just printed: every number needs its source.
with open("/tmp/resultats-cout-d-un-gros-lot.json", "w") as _f:
    import json as _json
    _json.dump(sortie, _f, ensure_ascii=False, indent=1)
print("@@@JSON@@@")
print(json.dumps(sortie, ensure_ascii=False, indent=1))
