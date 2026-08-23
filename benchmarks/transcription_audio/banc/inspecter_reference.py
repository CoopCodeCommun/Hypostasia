#!/usr/bin/env python3
"""
Affiche l'ordre des tours de parole pour reperer les frontieres des segments.
/ Prints turns in order, to locate segment boundaries.
"""
import json

tours = json.load(open("reference.json", encoding="utf-8"))
print(f"{len(tours)} tours au total\n")
print("idx | locuteur               | mots | debut du texte")
print("-" * 100)
for indice, tour in enumerate(tours):
    locuteur = tour["locuteur"][:22]
    nombre_mots = len(tour["texte"].split())
    debut = tour["texte"][:60].replace("\n", " ")
    print(f"{indice:3d} | {locuteur:22s} | {nombre_mots:4d} | {debut}")
