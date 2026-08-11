### DIFF DU FIX — robustesse de la commande de reparation

## fichier complet (nouveau, non suivi par git)
     1	"""
     2	Retire le prefixe de classe que str() a laisse dans coord_origin.
     3	/ Strips the enum class prefix str() left behind in coord_origin.
     4	
     5	LOCALISATION : core/management/commands/reparer_la_provenance_des_boites.py
     6	
     7	POURQUOI CETTE COMMANDE EXISTE
     8	
     9	`hypostasis_extractor/services/ingestion_docling.py` faisait `str()` sur
    10	`boite.coord_origin`, un membre de l'enumeration CoordOrigin de
    11	docling-core. str() d'un membre d'enum rend "CoordOrigin.BOTTOMLEFT" — le
    12	prefixe de classe compris — au lieu de "BOTTOMLEFT". Le service est
    13	corrige (il prend `.value`), mais les boites deja en base portent encore
    14	le defaut.
    15	
    16	Re-ingerer reparerait la provenance, mais detruirait les ancres deja
    17	posees sur ces elements — meme principe que enrichir_la_provenance_audio :
    18	on repare la donnee en place plutot que de refaire l'ingestion.
    19	/ Re-ingesting would wipe existing anchors; repair the data in place.
    20	
    21	CE QU'ELLE FAIT
    22	
    23	Parcourt les ElementDocument dont la provenance porte des boites, et
    24	remplace tout coord_origin de la forme "CoordOrigin.XXX" par "XXX". Ne
    25	touche a rien d'autre : ni aux coordonnees (l, t, r, b), ni au numero de
    26	page, ni a une valeur deja propre.
    27	
    28	FACE A UNE DONNEE ABIMEE
    29	
    30	Une commande de reparation est exactement l'outil qu'on lance sur une
    31	base dont on soupconne les donnees d'etre abimees : elle ne doit pas
    32	s'arreter au premier cas inattendu. Une "boites" absente, valant None ou
    33	d'un type inattendu, une boite qui n'est pas un dictionnaire, une boite
    34	sans coord_origin : chaque cas est ignore SANS lever, et compte a part
    35	dans le bilan plutot qu'avale en silence ou range sous une etiquette
    36	fausse (voir _corriger_les_boites_d_un_element).
    37	/ A repair command must survive malformed data, not crash on it.
    38	
    39	LANCER LA COMMANDE
    40	
    41	    docker exec -w /app hypostasia_web uv run python manage.py \\
    42	        reparer_la_provenance_des_boites --a-blanc
    43	    docker exec -w /app hypostasia_web uv run python manage.py \\
    44	        reparer_la_provenance_des_boites
    45	"""
    46	
    47	from django.core.management.base import BaseCommand
    48	from django.db import transaction
    49	
    50	from core.models import ElementDocument
    51	
    52	# Le prefixe que str() sur un membre d'enum ajoute toujours.
    53	# / The prefix str() always adds on an enum member.
    54	PREFIXE_D_ENUMERATION = "CoordOrigin."
    55	
    56	
    57	class Command(BaseCommand):
    58	    help = (
    59	        "Corrige coord_origin dans la provenance des ElementDocument : "
    60	        "'CoordOrigin.BOTTOMLEFT' -> 'BOTTOMLEFT'. Ne touche a rien d'autre."
    61	    )
    62	
    63	    def add_arguments(self, analyseur_d_arguments):
    64	        analyseur_d_arguments.add_argument(
    65	            "--a-blanc", action="store_true",
    66	            help="Affiche ce qui serait corrige, sans rien ecrire.",
    67	        )
    68	
    69	    def handle(self, *args, **options):
    70	        a_blanc = options["a_blanc"]
    71	
    72	        if a_blanc:
    73	            self.stdout.write(self.style.WARNING(
    74	                "MODE A BLANC — rien ne sera ecrit.",
    75	            ))
    76	
    77	        # On ne prend que les elements qui ont une provenance : la
    78	        # grande majorite (md/html/txt/audio) n'en a pas et n'a rien a
    79	        # gagner a etre chargee ici.
    80	        # / Only elements with a provenance; most have none to load.
    81	        elements_avec_provenance = list(
    82	            ElementDocument.objects.exclude(provenance={}).order_by("pk"),
    83	        )
    84	
    85	        total_boites_corrigees = 0
    86	        total_boites_deja_propres = 0
    87	        total_boites_sans_coord_origin = 0
    88	        total_boites_ignorees = 0
    89	        total_elements_provenance_inattendue = 0
    90	        elements_a_ecrire = []
    91	
    92	        for element in elements_avec_provenance:
    93	            boites = (element.provenance or {}).get("boites")
    94	
    95	            # UNE PROVENANCE SANS BOITES EXPLOITABLES N'EST PAS UNE
    96	            # ERREUR QUI DOIT ARRETER LA COMMANDE.
    97	            #
    98	            # `boites` absente, valant None, ou d'un type inattendu
    99	            # (chaine, dict, nombre) : rien a reparer ici, mais on le
   100	            # compte plutot que de l'avaler en silence. Une provenance
   101	            # audio (locuteur, debut, fin) n'a jamais de "boites" : ce
   102	            # compte grimpe donc normalement sur une base mixte — ce
   103	            # n'est pas forcement un signal d'alarme, mais le mainteneur
   104	            # doit pouvoir le voir plutot que le deviner.
   105	            # / Missing/None/wrong-type `boites` is not fatal; count it
   106	            # instead of raising or hiding it — routine on a mixed base.
   107	            if not isinstance(boites, list):
   108	                total_elements_provenance_inattendue += 1
   109	                continue
   110	
   111	            element_modifie, corrigees, deja_propres, sans_origine, ignorees = (
   112	                self._corriger_les_boites_d_un_element(boites)
   113	            )
   114	            total_boites_corrigees += corrigees
   115	            total_boites_deja_propres += deja_propres
   116	            total_boites_sans_coord_origin += sans_origine
   117	            total_boites_ignorees += ignorees
   118	
   119	            if element_modifie:
   120	                elements_a_ecrire.append(element)
   121	                self.stdout.write(
   122	                    f"  element {element.pk} (page {element.page_id}) : "
   123	                    f"coord_origin corrige",
   124	                )
   125	
   126	        if not a_blanc:
   127	            with transaction.atomic():
   128	                for element in elements_a_ecrire:
   129	                    element.save(update_fields=["provenance"])
   130	
   131	        self.stdout.write("")
   132	        self.stdout.write(
   133	            f"Elements avec provenance examines : {len(elements_avec_provenance)}",
   134	        )
   135	        self.stdout.write(f"Elements corriges                 : {len(elements_a_ecrire)}")
   136	        self.stdout.write(f"Boites corrigees                   : {total_boites_corrigees}")
   137	        self.stdout.write(f"Boites deja propres                : {total_boites_deja_propres}")
   138	        self.stdout.write(
   139	            f"Boites sans coord_origin (muettes) : {total_boites_sans_coord_origin}",
   140	        )
   141	        self.stdout.write(
   142	            f"Boites ignorees (pas un dict)      : {total_boites_ignorees}",
   143	        )
   144	        self.stdout.write(
   145	            f"Elements a la provenance inattendue (boites absente/None/"
   146	            f"non-liste) : {total_elements_provenance_inattendue}",
   147	        )
   148	
   149	        if a_blanc:
   150	            self.stdout.write(self.style.WARNING(
   151	                "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
   152	            ))
   153	        elif total_boites_corrigees == 0:
   154	            self.stdout.write("\nRien a faire : toutes les boites etaient deja propres.")
   155	
   156	    def _corriger_les_boites_d_un_element(self, boites):
   157	        """
   158	        Corrige en place les boites d'un element, sans jamais lever.
   159	        / Repairs an element's boxes in place, without ever raising.
   160	
   161	        LOCALISATION : core/management/commands/reparer_la_provenance_des_boites.py
   162	
   163	        :param boites: la liste `provenance["boites"]` d'un element —
   164	            deja verifiee comme etant une liste par l'appelant, mais dont
   165	            le CONTENU n'est pas garanti : chaque entree peut ne pas etre
   166	            un dictionnaire, une donnee abimee que la reparation doit
   167	            traverser sans s'arreter.
   168	        :return: (element_modifie, corrigees, deja_propres, sans_origine,
   169	            ignorees)
   170	        """
   171	        element_modifie = False
   172	        corrigees = deja_propres = sans_origine = ignorees = 0
   173	
   174	        for boite in boites:
   175	            if not isinstance(boite, dict):
   176	                # UNE SEULE BOITE ABIMEE NE DOIT PAS FAIRE ECHOUER LA
   177	                # REPARATION DE TOUTES LES AUTRES.
   178	                # / One malformed box must not abort the whole repair.
   179	                ignorees += 1
   180	                continue
   181	
   182	            valeur = boite.get("coord_origin")
   183	
   184	            # ABSENTE N'EST PAS PROPRE, C'EST MUETTE — NUANCE QUI COMPTE.
   185	            #
   186	            # Une boite propre a deja subi la reparation ou n'a jamais
   187	            # eu le defaut ; une boite sans coord_origin exploitable
   188	            # (cle absente, None, ou un type qui n'est pas une chaine)
   189	            # n'a simplement rien a dire sur son systeme de coordonnees.
   190	            # Les confondre avec "deja propres" ferait mentir le bilan.
   191	            # / Missing/unusable is not clean, it is silent — a
   192	            # different case; conflating it with "already clean" lies.
   193	            if not isinstance(valeur, str) or not valeur:
   194	                sans_origine += 1
   195	                continue
   196	
   197	            if valeur.startswith(PREFIXE_D_ENUMERATION):
   198	                boite["coord_origin"] = valeur[len(PREFIXE_D_ENUMERATION):]
   199	                corrigees += 1
   200	                element_modifie = True
   201	            else:
   202	                deja_propres += 1
   203	
   204	        return element_modifie, corrigees, deja_propres, sans_origine, ignorees
