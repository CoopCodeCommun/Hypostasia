#!/usr/bin/env python3
"""
Extrait la transcription humaine de reference depuis librealire.org.
/ Extracts the human reference transcript from librealire.org.

Les tours de parole y sont marques par un nom en gras suivi de deux-points.
/ Speaker turns are marked there by a bold name followed by a colon.
"""
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser

URL = sys.argv[1] if len(sys.argv) > 1 else (
    "https://www.librealire.org/"
    "emission-libre-a-vous-diffusee-mardi-7-juillet-2026-sur-radio-cause-commune"
)
SORTIE = sys.argv[2] if len(sys.argv) > 2 else "reference"

IGNORER = {"script", "style", "head", "nav", "footer"}


class ExtracteurDeTours(HTMLParser):
    """
    Reconstruit le flux texte en marquant ce qui etait en gras.
    / Rebuilds the text stream, flagging what was bold.
    """

    def __init__(self):
        super().__init__()
        self.morceaux = []          # liste de (en_gras, texte)
        self.profondeur_gras = 0
        self.balise_ignoree = 0

    def handle_starttag(self, tag, attrs):
        if tag in IGNORER:
            self.balise_ignoree += 1
        elif tag in ("strong", "b"):
            self.profondeur_gras += 1
        elif tag in ("p", "div", "br", "li"):
            self.morceaux.append((False, "\n"))

    def handle_endtag(self, tag):
        if tag in IGNORER:
            self.balise_ignoree = max(0, self.balise_ignoree - 1)
        elif tag in ("strong", "b"):
            self.profondeur_gras = max(0, self.profondeur_gras - 1)

    def handle_data(self, data):
        if self.balise_ignoree:
            return
        self.morceaux.append((self.profondeur_gras > 0, data))


def recuperer(url):
    """
    Telecharge la page et la decode. / Downloads the page and decodes it.
    """
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bench-asr)"})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        brut = reponse.read()
    try:
        return brut.decode("utf-8")
    except UnicodeDecodeError:
        # Repli si la page n'est pas en UTF-8 / fallback if the page is not UTF-8
        return brut.decode("latin-1")


def construire_les_tours(morceaux):
    """
    Un tour commence a chaque nom en gras termine par ':'.
    / A turn starts at each bold name ending with ':'.
    """
    tours = []
    locuteur_courant = None
    tampon = []

    for en_gras, texte in morceaux:
        propre = texte.replace("\xa0", " ")
        # Un nom de locuteur : en gras, court, et suivi de deux-points
        # / A speaker name: bold, short, and followed by a colon
        candidat = propre.strip()
        if en_gras and candidat.endswith(":") and 0 < len(candidat) <= 40:
            if locuteur_courant is not None:
                tours.append((locuteur_courant, " ".join(tampon)))
            locuteur_courant = candidat.rstrip(":").strip()
            tampon = []
        elif locuteur_courant is not None:
            tampon.append(propre)

    if locuteur_courant is not None:
        tours.append((locuteur_courant, " ".join(tampon)))

    nettoyes = []
    for locuteur, corps in tours:
        corps = re.sub(r"\s+", " ", corps).strip()
        if corps:
            nettoyes.append({"locuteur": locuteur, "texte": corps})
    return nettoyes


def main():
    print(f"recuperation : {URL}")
    html = recuperer(URL)
    print(f"  page recue : {len(html)} caracteres")

    extracteur = ExtracteurDeTours()
    extracteur.feed(html)
    tours = construire_les_tours(extracteur.morceaux)

    if not tours:
        print("  AUCUN TOUR DETECTE — le balisage de la page a probablement change.")
        print("  Verifier que les noms sont bien dans un <strong> avec le ':' a l'interieur.")
        sys.exit(1)

    print(f"  tours de parole detectes : {len(tours)}  (attendu : 131)")
    compteur = {}
    for tour in tours:
        compteur[tour["locuteur"]] = compteur.get(tour["locuteur"], 0) + 1
    print("  locuteurs :")
    for nom, nombre in sorted(compteur.items(), key=lambda x: -x[1]):
        mots = sum(len(t["texte"].split()) for t in tours if t["locuteur"] == nom)
        print(f"    {nom!r} : {nombre} tours, {mots} mots")

    with open(f"{SORTIE}.json", "w", encoding="utf-8") as fichier:
        json.dump(tours, fichier, ensure_ascii=False, indent=1)
    with open(f"{SORTIE}.txt", "w", encoding="utf-8") as fichier:
        for tour in tours:
            fichier.write(f"{tour['locuteur']} : {tour['texte']}\n\n")

    print(f"  ecrit : {SORTIE}.json et {SORTIE}.txt")


if __name__ == "__main__":
    main()
