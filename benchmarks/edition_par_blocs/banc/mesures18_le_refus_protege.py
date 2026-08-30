"""Le refus protege-t-il REELLEMENT le demasquage ? En transaction annulee."""
import json
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import ElementDocument
from hypostasis_extractor.models import AncrageExtraction, EtatAncrage
from hypostasis_extractor.services.masquage import (
    demasquer_un_element, masquer_un_element,
)
from hypostasis_extractor.services.garde_edition import (
    EditionBloqueeParUneSynthese, verifier_qu_aucune_synthese_ne_cite,
)
from hypostasis_extractor.views_element import ElementViewSet


class Annulation(Exception):
    pass


candidat = None
for e in (ElementDocument.objects.filter(page_id=19)
          .exclude(portions_d_extractions=None).distinct().order_by("ordre")):
    try:
        verifier_qu_aucune_synthese_ne_cite(e)
        candidat = e
        break
    except EditionBloqueeParUneSynthese:
        continue

U = get_user_model()
vue = ElementViewSet.as_view({"post": "corriger_en_lot"})
fabrique = APIRequestFactory()
sortie = {"element": candidat.ordre}

try:
    with transaction.atomic():
        element = ElementDocument.objects.get(pk=candidat.pk)
        masquer_un_element(element, justification="essai", verifier_les_jobs=False)
        # LE LOT tente de corriger le bloc masque.
        requete = fabrique.post("/elements/corriger_en_lot/", {"blocs": [
            {"identifiant_stable": str(element.identifiant_stable),
             "texte": element.texte + " MOT AJOUTE"}]}, format="json")
        force_authenticate(requete, user=U.objects.get(username="thales"))
        requete.session = SessionStore()
        reponse = vue(requete)
        if hasattr(reponse, "render"):
            reponse.render()
        corps = reponse.content.decode()
        element.refresh_from_db()
        resultat = demasquer_un_element(element, verifier_les_jobs=False)
        raise Annulation({
            "statut": reponse.status_code,
            "le_bloc_est_nomme_dans_le_refus": str(element.identifiant_stable) in corps,
            "le_texte_a_bouge": element.texte != candidat.texte,
            "rattachees_au_demasquage": resultat["portions_rattachees"],
            "laissees_detachees": resultat["portions_laissees_detachees"],
        })
except Annulation as a:
    sortie["avec_le_refus"] = a.args[0]

frais = ElementDocument.objects.get(pk=candidat.pk)
sortie["verification"] = {
    "masque": frais.masque, "texte_intact": frais.texte == candidat.texte,
    "portions_ancrees": AncrageExtraction.objects.filter(
        element=frais, etat_ancrage=EtatAncrage.ANCREE).count(),
}
print("@@@JSON@@@")
print(json.dumps(sortie, ensure_ascii=False, indent=1))
