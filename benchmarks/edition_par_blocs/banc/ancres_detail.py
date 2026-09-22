"""
QUELLES portions se detachent, et pourquoi ?
/ Which portions detach, and why?

Hypothese a eprouver : seules se detachent les portions qui ENJAMBENT le
point d'edition. Celles qui sont entierement avant ou entierement apres
devraient survivre.
"""
import json
from django.db import transaction
from core.models import ElementDocument
from hypostasis_extractor.models import AncrageExtraction
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
for genre in ("frappe_au_milieu", "correction_de_casse"):
    enjambantes_detachees = 0
    enjambantes_survivantes = 0
    hors_plage_detachees = 0
    hors_plage_survivantes = 0
    exemples = []
    for element in elements:
        frais = ElementDocument.objects.get(pk=element.pk)
        milieu = len(frais.texte) // 2
        if genre == "frappe_au_milieu":
            nouveau = frais.texte[:milieu] + "XX" + frais.texte[milieu:]
            point = milieu
        else:
            nouveau = frais.texte[0].swapcase() + frais.texte[1:]
            point = 0
        portions = {
            p.pk: (p.debut_dans_element, p.fin_dans_element)
            for p in AncrageExtraction.objects.filter(element=frais)
        }
        try:
            with transaction.atomic():
                rapport = reconcilier_les_portions_de_l_element(frais, nouveau)
                detachees = set(rapport["detachees"])
                for pk, (debut, fin) in portions.items():
                    enjambe = debut <= point < fin
                    if enjambe and pk in detachees:
                        enjambantes_detachees += 1
                    elif enjambe:
                        enjambantes_survivantes += 1
                    elif pk in detachees:
                        hors_plage_detachees += 1
                        if len(exemples) < 5:
                            exemples.append({
                                "ordre": frais.ordre, "debut": debut, "fin": fin,
                                "point": point, "longueur_du_texte": len(frais.texte),
                            })
                    else:
                        hors_plage_survivantes += 1
                raise AnnulationVolontaire()
        except AnnulationVolontaire:
            pass
        except EditionBloqueeParUneSynthese:
            pass
    resultats[genre] = {
        "portions_enjambant_le_point_DETACHEES": enjambantes_detachees,
        "portions_enjambant_le_point_SURVIVANTES": enjambantes_survivantes,
        "portions_hors_plage_DETACHEES": hors_plage_detachees,
        "portions_hors_plage_SURVIVANTES": hors_plage_survivantes,
        "exemples_de_detachement_hors_plage": exemples,
    }

print("@@@JSON@@@")
print(json.dumps(resultats, ensure_ascii=False))
