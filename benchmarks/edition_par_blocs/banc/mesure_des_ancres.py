"""
LA MESURE DES ANCRES — celle que la note avait pre-enregistree comme
eliminatoire, et que le premier passage n'avait pas prise.
/ The anchor measurement, pre-registered as eliminatory.

LOCALISATION : scratchpad de session, HORS DEPOT.

QUESTION : apres une session d'edition, combien de portions se DETACHENT ?
`reconcilier_les_portions_de_l_element` rend le compte lui-meme :
{"exactes": [...], "retrouvees": [...], "detachees": [...]}.

AUCUNE ECRITURE N'EST CONSERVEE. Chaque reconciliation tourne dans une
transaction que l'on FAIT ECHOUER volontairement. La garantie ne repose
pas sur ma vigilance mais sur une exception levee a la fin du bloc
`atomic`, plus une verification des empreintes avant et apres.
"""
import json

from django.db import transaction

from core.models import ElementDocument
from hypostasis_extractor.services.garde_edition import (
    EditionBloqueeParUneSynthese,
    EditionBloqueePendantAnalyse,
)
from hypostasis_extractor.services.reconciliation import (
    reconcilier_les_portions_de_l_element,
)


class AnnulationVolontaire(Exception):
    """Levee pour forcer le rollback. / Raised to force the rollback."""


def editer(texte, genre):
    """Fabrique le texte d'apres, selon le genre de correction."""
    milieu = len(texte) // 2
    if genre == "frappe_au_milieu":
        return texte[:milieu] + "XX" + texte[milieu:]
    if genre == "nbsp_comme_le_navigateur":
        # Ce que Chromium insere REELLEMENT quand on tape deux espaces.
        # / What Chromium actually inserts when you type two spaces.
        return texte[:milieu] + "   " + texte[milieu:]
    if genre == "saut_de_ligne":
        return texte[:milieu] + "\n" + texte[milieu:]
    if genre == "troncature_de_tete":
        # Le bloc 20 de la suppression multi-blocs : il ne garde que sa tete.
        # / The multi-block delete: the block keeps only its head.
        return texte[:15]
    if genre == "correction_de_casse":
        return texte[0].swapcase() + texte[1:]
    raise ValueError(genre)


GENRES = [
    "frappe_au_milieu",
    "nbsp_comme_le_navigateur",
    "saut_de_ligne",
    "correction_de_casse",
    "troncature_de_tete",
]

elements = list(
    ElementDocument.objects.filter(page_id=19)
    .exclude(portions_d_extractions=None)
    .distinct()
    .order_by("ordre")[:40]
)
empreintes_avant = {e.pk: (e.texte, e.empreinte_contenu) for e in elements}

resultats = {"page": 19, "elements_eprouves": len(elements), "par_genre": {}}

for genre in GENRES:
    compte = {
        "portions_totales": 0,
        "exactes": 0,
        "retrouvees": 0,
        "detachees": 0,
        "elements_traites": 0,
        "refus_synthese_figee": 0,
        "refus_analyse_en_cours": 0,
    }
    for element in elements:
        frais = ElementDocument.objects.get(pk=element.pk)
        nouveau = editer(frais.texte, genre)
        try:
            with transaction.atomic():
                rapport = reconcilier_les_portions_de_l_element(frais, nouveau)
                compte["elements_traites"] += 1
                compte["exactes"] += len(rapport["exactes"])
                compte["retrouvees"] += len(rapport["retrouvees"])
                compte["detachees"] += len(rapport["detachees"])
                compte["portions_totales"] += (
                    len(rapport["exactes"]) + len(rapport["retrouvees"])
                    + len(rapport["detachees"])
                )
                # ON ANNULE TOUT. / Roll everything back.
                raise AnnulationVolontaire()
        except AnnulationVolontaire:
            pass
        except EditionBloqueeParUneSynthese:
            compte["refus_synthese_figee"] += 1
        except EditionBloqueePendantAnalyse:
            compte["refus_analyse_en_cours"] += 1
    total = compte["portions_totales"] or 1
    compte["taux_de_detachement_pct"] = round(100 * compte["detachees"] / total, 1)
    resultats["par_genre"][genre] = compte

# VERIFICATION : rien n'a bouge en base.
# / VERIFICATION: nothing moved in the database.
inchanges = 0
modifies = []
for element in elements:
    frais = ElementDocument.objects.get(pk=element.pk)
    texte_avant, empreinte_avant = empreintes_avant[element.pk]
    if frais.texte == texte_avant and frais.empreinte_contenu == empreinte_avant:
        inchanges += 1
    else:
        modifies.append(frais.ordre)
resultats["verification_aucune_ecriture"] = {
    "elements_inchanges": inchanges,
    "elements_modifies": modifies,
}

print("@@@JSON@@@")
print(json.dumps(resultats, ensure_ascii=False))
