"""
Retire le prefixe de classe que str() a laisse dans coord_origin.
/ Strips the enum class prefix str() left behind in coord_origin.

LOCALISATION : core/management/commands/reparer_la_provenance_des_boites.py

POURQUOI CETTE COMMANDE EXISTE

`hypostasis_extractor/services/ingestion_docling.py` faisait `str()` sur
`boite.coord_origin`, un membre de l'enumeration CoordOrigin de
docling-core. str() d'un membre d'enum rend "CoordOrigin.BOTTOMLEFT" — le
prefixe de classe compris — au lieu de "BOTTOMLEFT". Le service est
corrige (il prend `.value`), mais les boites deja en base portent encore
le defaut.

Re-ingerer reparerait la provenance, mais detruirait les ancres deja
posees sur ces elements — meme principe que enrichir_la_provenance_audio :
on repare la donnee en place plutot que de refaire l'ingestion.
/ Re-ingesting would wipe existing anchors; repair the data in place.

CE QU'ELLE FAIT

Parcourt les ElementDocument dont la provenance porte des boites, et
remplace tout coord_origin de la forme "CoordOrigin.XXX" par "XXX". Ne
touche a rien d'autre : ni aux coordonnees (l, t, r, b), ni au numero de
page, ni a une valeur deja propre.

FACE A UNE DONNEE ABIMEE

Une commande de reparation est exactement l'outil qu'on lance sur une
base dont on soupconne les donnees d'etre abimees : elle ne doit pas
s'arreter au premier cas inattendu. Une "boites" absente, valant None ou
d'un type inattendu, une boite qui n'est pas un dictionnaire, une boite
sans coord_origin : chaque cas est ignore SANS lever, et compte a part
dans le bilan plutot qu'avale en silence ou range sous une etiquette
fausse (voir _corriger_les_boites_d_un_element).
/ A repair command must survive malformed data, not crash on it.

LANCER LA COMMANDE

    docker exec -w /app hypostasia_web uv run python manage.py \\
        reparer_la_provenance_des_boites --a-blanc
    docker exec -w /app hypostasia_web uv run python manage.py \\
        reparer_la_provenance_des_boites
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import ElementDocument

# Le prefixe que str() sur un membre d'enum ajoute toujours.
# / The prefix str() always adds on an enum member.
PREFIXE_D_ENUMERATION = "CoordOrigin."


class Command(BaseCommand):
    help = (
        "Corrige coord_origin dans la provenance des ElementDocument : "
        "'CoordOrigin.BOTTOMLEFT' -> 'BOTTOMLEFT'. Ne touche a rien d'autre."
    )

    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--a-blanc", action="store_true",
            help="Affiche ce qui serait corrige, sans rien ecrire.",
        )

    def handle(self, *args, **options):
        a_blanc = options["a_blanc"]

        if a_blanc:
            self.stdout.write(self.style.WARNING(
                "MODE A BLANC — rien ne sera ecrit.",
            ))

        # On ne prend que les elements qui ont une provenance : la
        # grande majorite (md/html/txt/audio) n'en a pas et n'a rien a
        # gagner a etre chargee ici.
        # / Only elements with a provenance; most have none to load.
        elements_avec_provenance = list(
            ElementDocument.objects.exclude(provenance={}).order_by("pk"),
        )

        total_boites_corrigees = 0
        total_boites_deja_propres = 0
        total_boites_sans_coord_origin = 0
        total_boites_ignorees = 0
        total_elements_provenance_inattendue = 0
        elements_a_ecrire = []

        for element in elements_avec_provenance:
            # `provenance` ELLE-MEME PEUT NE PAS ETRE UN DICT.
            #
            # `element.provenance or {}` ne protege que du cas falsy
            # (None, {}) : une provenance qui est une LISTE ou une
            # CHAINE non vide passe au travers, `or {}` ne s'applique
            # pas, et `.get("boites")` levait. Un JSONField accepte
            # n'importe quelle valeur JSON ; notre code n'y ecrit que des
            # dicts, mais une commande de reparation ne doit rien
            # supposer de ce qu'elle trouve. Meme categorie de bilan que
            # les boites elles-memes : provenance inattendue.
            # / `provenance` itself may not be a dict; `or {}` only
            # guards the falsy case. Same bucket as the box-level cases.
            provenance = element.provenance
            if not isinstance(provenance, dict):
                total_elements_provenance_inattendue += 1
                continue

            boites = provenance.get("boites")

            # UNE PROVENANCE SANS BOITES EXPLOITABLES N'EST PAS UNE
            # ERREUR QUI DOIT ARRETER LA COMMANDE.
            #
            # `boites` absente, valant None, ou d'un type inattendu
            # (chaine, dict, nombre) : rien a reparer ici, mais on le
            # compte plutot que de l'avaler en silence. Une provenance
            # audio (locuteur, debut, fin) n'a jamais de "boites" : ce
            # compte grimpe donc normalement sur une base mixte — ce
            # n'est pas forcement un signal d'alarme, mais le mainteneur
            # doit pouvoir le voir plutot que le deviner.
            # / Missing/None/wrong-type `boites` is not fatal; count it
            # instead of raising or hiding it — routine on a mixed base.
            if not isinstance(boites, list):
                total_elements_provenance_inattendue += 1
                continue

            element_modifie, corrigees, deja_propres, sans_origine, ignorees = (
                self._corriger_les_boites_d_un_element(boites)
            )
            total_boites_corrigees += corrigees
            total_boites_deja_propres += deja_propres
            total_boites_sans_coord_origin += sans_origine
            total_boites_ignorees += ignorees

            if element_modifie:
                elements_a_ecrire.append(element)
                self.stdout.write(
                    f"  element {element.pk} (page {element.page_id}) : "
                    f"coord_origin corrige",
                )

        if not a_blanc:
            with transaction.atomic():
                for element in elements_a_ecrire:
                    element.save(update_fields=["provenance"])

        self.stdout.write("")
        self.stdout.write(
            f"Elements avec provenance examines : {len(elements_avec_provenance)}",
        )
        self.stdout.write(f"Elements corriges                 : {len(elements_a_ecrire)}")
        self.stdout.write(f"Boites corrigees                   : {total_boites_corrigees}")
        self.stdout.write(f"Boites deja propres                : {total_boites_deja_propres}")
        self.stdout.write(
            f"Boites sans coord_origin (muettes) : {total_boites_sans_coord_origin}",
        )
        self.stdout.write(
            f"Boites ignorees (pas un dict)      : {total_boites_ignorees}",
        )
        self.stdout.write(
            f"Elements a la provenance inattendue (boites absente/None/"
            f"non-liste) : {total_elements_provenance_inattendue}",
        )

        if a_blanc:
            self.stdout.write(self.style.WARNING(
                "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
            ))
        elif total_boites_corrigees == 0:
            self.stdout.write("\nRien a faire : toutes les boites etaient deja propres.")

    def _corriger_les_boites_d_un_element(self, boites):
        """
        Corrige en place les boites d'un element, sans jamais lever.
        / Repairs an element's boxes in place, without ever raising.

        LOCALISATION : core/management/commands/reparer_la_provenance_des_boites.py

        :param boites: la liste `provenance["boites"]` d'un element —
            deja verifiee comme etant une liste par l'appelant, mais dont
            le CONTENU n'est pas garanti : chaque entree peut ne pas etre
            un dictionnaire, une donnee abimee que la reparation doit
            traverser sans s'arreter.
        :return: (element_modifie, corrigees, deja_propres, sans_origine,
            ignorees)
        """
        element_modifie = False
        corrigees = deja_propres = sans_origine = ignorees = 0

        for boite in boites:
            if not isinstance(boite, dict):
                # UNE SEULE BOITE ABIMEE NE DOIT PAS FAIRE ECHOUER LA
                # REPARATION DE TOUTES LES AUTRES.
                # / One malformed box must not abort the whole repair.
                ignorees += 1
                continue

            valeur = boite.get("coord_origin")

            # ABSENTE N'EST PAS PROPRE, C'EST MUETTE — NUANCE QUI COMPTE.
            #
            # Une boite propre a deja subi la reparation ou n'a jamais
            # eu le defaut ; une boite sans coord_origin exploitable
            # (cle absente, None, ou un type qui n'est pas une chaine)
            # n'a simplement rien a dire sur son systeme de coordonnees.
            # Les confondre avec "deja propres" ferait mentir le bilan.
            # / Missing/unusable is not clean, it is silent — a
            # different case; conflating it with "already clean" lies.
            if not isinstance(valeur, str) or not valeur:
                sans_origine += 1
                continue

            if valeur.startswith(PREFIXE_D_ENUMERATION):
                boite["coord_origin"] = valeur[len(PREFIXE_D_ENUMERATION):]
                corrigees += 1
                element_modifie = True
            else:
                deja_propres += 1

        return element_modifie, corrigees, deja_propres, sans_origine, ignorees
