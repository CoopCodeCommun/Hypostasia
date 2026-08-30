"""
LE DIFF COTE PYTHON — ce que ferait `corriger_en_lot`.
/ The Python-side diff: what `corriger_en_lot` would do.

LOCALISATION : scratchpad de session, HORS DEPOT.

Il rejoue le § 7.3 de SPEC-edition-par-blocs-et-stenotypie.md :
  1. texte identique au caractere pres  -> rien
  2. texte vide                         -> masquer
  3. sinon                              -> corriger (reconciliation)

Et il compare DEUX regles de detection :
  - le texte BRUT (hash_du_texte_brut, masquage.py:52) — ce que la spec exige ;
  - l'empreinte NORMALISEE (empreinte_du_texte, core/models.py:2116) —
    minuscules, espaces ecrases, strip — ce que la v1.0 de la spec proposait.
"""
import hashlib
import json
import re
import sys


def hash_du_texte_brut(texte):
    """Copie exacte de hypostasis_extractor/services/masquage.py:52."""
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def empreinte_du_texte(texte):
    """Copie exacte de core/models.py:2116 — minuscules, espaces ecrases, strip."""
    normalise = re.sub(r"\s+", " ", texte.lower()).strip()
    return hashlib.sha256(normalise.encode("utf-8")).hexdigest()


def diff(initiaux, poste, empreinte):
    """Rend les operations, par identifiant_stable."""
    par_identifiant = {b["identifiant_stable"]: b for b in initiaux}
    operations = {"rien": [], "corriger": [], "masquer": [], "refuse": []}
    vus = set()
    doublons = []
    for entree in poste:
        identifiant = entree["identifiant_stable"]
        if identifiant in vus:
            doublons.append(identifiant)
            continue
        vus.add(identifiant)
        origine = par_identifiant.get(identifiant)
        if origine is None:
            operations["refuse"].append(identifiant)
            continue
        texte = entree["texte"]
        if texte is None:
            operations["refuse"].append(identifiant)
        elif empreinte(texte) == empreinte(origine["texte"]):
            operations["rien"].append(identifiant)
        elif texte.strip() == "":
            operations["masquer"].append(identifiant)
        else:
            operations["corriger"].append(identifiant)
    perdus = [i for i in par_identifiant if i not in vus]
    return operations, perdus, doublons


def principal(chemin):
    resultat = json.load(open(chemin))["mesure_2_vingt_gestes"]
    initiaux = resultat["initiaux"]
    poste = resultat["post"]
    ordre = {b["identifiant_stable"]: i for i, b in enumerate(initiaux)}

    print("=== LE POST ===")
    print(f"blocs envoyes            : {len(poste)}")
    print(f"blocs en base au depart  : {len(initiaux)}")
    identifiants = [b["identifiant_stable"] for b in poste]
    print(f"identifiants uniques     : {len(set(identifiants))}")
    print(f"ordre preserve           : "
          f"{identifiants == [b['identifiant_stable'] for b in initiaux]}")
    corps_detruits = [b for b in poste if b.get("corps_detruit")]
    print(f"corps detruits           : {len(corps_detruits)}")

    for nom, fonction in (("TEXTE BRUT (spec v1.1)", hash_du_texte_brut),
                          ("EMPREINTE NORMALISEE (v1.0)", empreinte_du_texte)):
        operations, perdus, doublons = diff(initiaux, poste, fonction)
        print(f"\n=== DIFF PAR {nom} ===")
        print(f"rien     : {len(operations['rien'])}")
        print(f"corriger : {len(operations['corriger'])}  -> "
              f"blocs {sorted(ordre[i] for i in operations['corriger'])}")
        print(f"masquer  : {len(operations['masquer'])}  -> "
              f"blocs {sorted(ordre[i] for i in operations['masquer'])}")
        print(f"refuse   : {len(operations['refuse'])}")
        print(f"identifiants perdus   : {len(perdus)}")
        print(f"identifiants dupliques: {len(doublons)}")

    # Ce que la normalisation JETTE en silence.
    operations_brut, _, _ = diff(initiaux, poste, hash_du_texte_brut)
    operations_norm, _, _ = diff(initiaux, poste, empreinte_du_texte)
    perdues = set(operations_brut["corriger"]) - set(operations_norm["corriger"])
    perdues -= set(operations_norm["masquer"])
    print("\n=== CE QUE L'EMPREINTE NORMALISEE JETTERAIT EN SILENCE ===")
    print(f"corrections vues par le brut et PAS par la normalisee : {len(perdues)}")
    par_identifiant = {b["identifiant_stable"]: b for b in initiaux}
    poste_par_identifiant = {b["identifiant_stable"]: b for b in poste}
    for identifiant in sorted(perdues, key=lambda i: ordre[i]):
        avant = par_identifiant[identifiant]["texte"]
        apres = poste_par_identifiant[identifiant]["texte"]
        print(f"  bloc {ordre[identifiant]:3d} : {avant[:38]!r}")
        print(f"              -> {apres[:38]!r}")

    # L'attribution par geste.
    print("\n=== LES VINGT GESTES ET LES BLOCS QU'ILS ONT TOUCHES ===")
    touches_par_gestes = set()
    for entree in resultat["journal_des_gestes"]:
        touches_par_gestes.update(entree.get("blocs_touches") or [])
        print(f"  {entree['n']:2d}. {entree['geste'][:52]:<52} "
              f"-> {entree.get('blocs_touches')}")

    operations_par_index = set(ordre[i] for i in operations_brut["corriger"])
    operations_par_index |= set(ordre[i] for i in operations_brut["masquer"])
    print("\n=== CONFRONTATION ===")
    print(f"blocs touches par au moins un geste (mesure DOM) : "
          f"{len(touches_par_gestes)} -> {sorted(touches_par_gestes)}")
    print(f"blocs vus par le diff serveur                    : "
          f"{len(operations_par_index)} -> {sorted(operations_par_index)}")
    faux_positifs = operations_par_index - touches_par_gestes
    faux_negatifs = touches_par_gestes - operations_par_index
    print(f"FAUX POSITIFS (le diff voit ce que nul n'a touche) : "
          f"{sorted(faux_positifs)}")
    print(f"FAUX NEGATIFS (touche, mais le diff ne le voit pas): "
          f"{sorted(faux_negatifs)}")

    # Les blocs JAMAIS touches doivent revenir a l'octet pres.
    intacts = [b for b in initiaux if ordre[b["identifiant_stable"]] not in touches_par_gestes]
    differents = [
        b for b in intacts
        if poste_par_identifiant[b["identifiant_stable"]]["texte"] != b["texte"]
    ]
    print(f"\nblocs jamais touches                : {len(intacts)}")
    print(f"  dont le texte revient DIFFERENT   : {len(differents)}")
    for b in differents[:5]:
        i = ordre[b["identifiant_stable"]]
        print(f"    bloc {i} : {b['texte'][:50]!r}")
        print(f"          -> {poste_par_identifiant[b['identifiant_stable']]['texte'][:50]!r}")


if __name__ == "__main__":
    principal(sys.argv[1])
