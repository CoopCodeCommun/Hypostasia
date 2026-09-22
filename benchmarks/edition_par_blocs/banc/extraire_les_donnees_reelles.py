"""
Extraction en lecture seule des blocs reels de la base de dev.
/ Read-only extraction of real blocks from the dev database.

LOCALISATION : scratchpad de session — HORS DEPOT, jetable.
Ce script ne fait aucune ecriture. Il sert le prototype de l'option C.
"""
import json

from core.models import ElementDocument

# Page 19 = la plus grosse note (210 blocs) ; page 3 = la transcription.
# / Page 19 = the biggest note; page 3 = the transcription.
sortie = {}
for page_id in (19, 3):
    blocs = []
    for element in ElementDocument.objects.filter(page_id=page_id).order_by("ordre"):
        blocs.append({
            "identifiant_stable": str(element.identifiant_stable),
            "ordre": element.ordre,
            "label": element.label,
            "texte": element.texte,
            "masque": element.masque,
            "provenance": element.provenance,
        })
    sortie[str(page_id)] = blocs

with open("/tmp/donnees-reelles.json", "w") as fichier:
    json.dump(sortie, fichier, ensure_ascii=False)
print("ecrit /tmp/donnees-reelles.json dans le conteneur")
