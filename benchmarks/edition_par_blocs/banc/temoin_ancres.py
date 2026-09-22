"""
LE TEMOIN — reconcilier avec un texte IDENTIQUE, puis avec une seule
lettre ajoutee EN FIN de texte.
/ The control: reconcile with identical text, then with one letter appended.

Si des portions se detachent deja sur un texte identique, alors le
detachement mesure l'etat de la base, PAS le geste d'edition.
"""
import json
from django.db import transaction
from core.models import ElementDocument
from hypostasis_extractor.services.garde_edition import EditionBloqueeParUneSynthese
from hypostasis_extractor.services.reconciliation import (
    reconcilier_les_portions_de_l_element,
)


class AnnulationVolontaire(Exception):
    pass


elements = list(
    ElementDocument.objects.filter(page_id=19)
    .exclude(portions_d_extractions=None).distinct().order_by("ordre")[:40]
)
resultats = {}
for genre in ("texte_identique", "une_lettre_a_la_fin", "une_lettre_au_debut"):
    compte = {"exactes": 0, "retrouvees": 0, "detachees": 0, "traites": 0, "refuses": 0}
    detail_detachees = []
    for element in elements:
        frais = ElementDocument.objects.get(pk=element.pk)
        if genre == "texte_identique":
            nouveau = frais.texte
        elif genre == "une_lettre_a_la_fin":
            nouveau = frais.texte + "Z"
        else:
            nouveau = "Z" + frais.texte
        try:
            with transaction.atomic():
                rapport = reconcilier_les_portions_de_l_element(frais, nouveau)
                compte["traites"] += 1
                compte["exactes"] += len(rapport["exactes"])
                compte["retrouvees"] += len(rapport["retrouvees"])
                compte["detachees"] += len(rapport["detachees"])
                if rapport["detachees"]:
                    detail_detachees.append(
                        {"ordre": frais.ordre, "n": len(rapport["detachees"])}
                    )
                raise AnnulationVolontaire()
        except AnnulationVolontaire:
            pass
        except EditionBloqueeParUneSynthese:
            compte["refuses"] += 1
    compte["detail_par_element"] = detail_detachees[:12]
    resultats[genre] = compte

print("@@@JSON@@@")
print(json.dumps(resultats, ensure_ascii=False))
