"""
Que coute une correction sur un bloc DEJA MASQUE ?
/ What does correcting an already-hidden block cost?

LOCALISATION : scratchpad de session. AUCUNE ECRITURE CONSERVEE :
chaque essai tourne dans une transaction que l'on fait echouer.

L'hypothese a eprouver : `demasquer` ne rattache ses portions QUE si le
texte n'a pas bouge depuis le masquage (il compare deux empreintes du
texte brut). Une correction entre les deux romprait donc le rattachement
— definitivement, et sans le dire.
"""
import json

from django.db import transaction

from core.models import ElementDocument
from hypostasis_extractor.models import AncrageExtraction, EtatAncrage
from hypostasis_extractor.services.masquage import (
    demasquer_un_element,
    masquer_un_element,
)
from hypostasis_extractor.services.reconciliation import (
    reconcilier_les_portions_de_l_element,
)
from hypostasis_extractor.services.garde_edition import EditionBloqueeParUneSynthese


class AnnulationVolontaire(Exception):
    pass


# Un element qui porte des portions, et que rien ne gele.
candidat = None
for e in (ElementDocument.objects.filter(page_id=19)
          .exclude(portions_d_extractions=None).distinct().order_by("ordre")):
    try:
        from hypostasis_extractor.services.garde_edition import (
            verifier_qu_aucune_synthese_ne_cite,
        )
        verifier_qu_aucune_synthese_ne_cite(e)
        candidat = e
        break
    except EditionBloqueeParUneSynthese:
        continue

sortie = {"element": candidat.ordre if candidat else None}


def essai(avec_correction):
    try:
        with transaction.atomic():
            element = ElementDocument.objects.get(pk=candidat.pk)
            avant = AncrageExtraction.objects.filter(
                element=element, etat_ancrage=EtatAncrage.ANCREE).count()
            masquer_un_element(element, justification="essai",
                               verifier_les_jobs=False)
            if avec_correction:
                # Ce que ferait le lot sur un bloc masque dont le client
                # envoie du texte. / What the batch would do.
                element.refresh_from_db()
                reconcilier_les_portions_de_l_element(
                    element, element.texte + " MOT AJOUTE")
            element.refresh_from_db()
            resultat = demasquer_un_element(element, verifier_les_jobs=False)
            raise AnnulationVolontaire({
                "portions_ancrees_au_depart": avant,
                "rattachees_au_demasquage": resultat["portions_rattachees"],
                "laissees_detachees": resultat["portions_laissees_detachees"],
            })
    except AnnulationVolontaire as annulation:
        return annulation.args[0]


sortie["sans_correction"] = essai(False)
sortie["AVEC_correction_du_bloc_masque"] = essai(True)

# Rien n'a bouge.
frais = ElementDocument.objects.get(pk=candidat.pk)
sortie["verification"] = {
    "masque": frais.masque,
    "texte_intact": frais.texte == candidat.texte,
    "portions_ancrees": AncrageExtraction.objects.filter(
        element=frais, etat_ancrage=EtatAncrage.ANCREE).count(),
}
print("@@@JSON@@@")
print(json.dumps(sortie, ensure_ascii=False, indent=1))
