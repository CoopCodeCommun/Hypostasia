### DIFF — correction de coord_origin
diff --git a/hypostasis_extractor/services/ingestion_docling.py b/hypostasis_extractor/services/ingestion_docling.py
index e67c01a..9208e80 100644
--- a/hypostasis_extractor/services/ingestion_docling.py
+++ b/hypostasis_extractor/services/ingestion_docling.py
@@ -384,30 +384,56 @@ def _mettre_a_jour_la_pile_des_titres(pile_des_titres, texte_du_titre, label):
 
     Un titre de document (title) remet la pile a zero : c'est le sommet.
     Un sous-titre (section_header) remplace le dernier sous-titre au meme
     niveau. Docling ne donnant pas toujours un niveau fiable, on reste
     simple : un seul niveau de sous-titre a la fois.
     / Kept deliberately simple: one section level at a time.
     """
     if label == "title":
         return [texte_du_titre]
 
     if pile_des_titres:
         return pile_des_titres[:1] + [texte_du_titre]
     return [texte_du_titre]
 
 
+def _coord_origin_en_chaine(coord_origin):
+    """
+    Rend "BOTTOMLEFT", jamais "CoordOrigin.BOTTOMLEFT".
+    / Returns "BOTTOMLEFT", never "CoordOrigin.BOTTOMLEFT".
+
+    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py
+
+    `coord_origin` est un membre de l'enumeration CoordOrigin de
+    docling-core. str() d'un membre d'enum rend "NomDeClasse.MEMBRE" — le
+    prefixe de classe compris — ce qu'un visualiseur PDF ne sait pas
+    interpreter : c'est `.value` qu'il faut, pas `str()`. Le systeme de
+    coordonnees n'est pas cosmetique : BOTTOMLEFT dit que `t` se mesure
+    depuis le bas de la page, et se tromper dessine les surlignages a
+    l'envers.
+    / `.value` on purpose, never `str()`: str() leaks "ClassName.MEMBER",
+    and the origin decides which way highlights get drawn.
+
+    :param coord_origin: un membre d'enum, une chaine deja propre, ou
+        absent (None) selon la source Docling.
+    """
+    if coord_origin is None:
+        return ""
+    valeur = getattr(coord_origin, "value", coord_origin)
+    return str(valeur)
+
+
 def _provenance_de_l_element(element_docling):
     """
     Rend la provenance physique d'un element : page et boites.
     / Returns an element's physical provenance: page and boxes.
 
     LOCALISATION : hypostasis_extractor/services/ingestion_docling.py
 
     Pour un PDF, Docling donne une LISTE de provenances : un paragraphe a
     cheval sur deux colonnes ou deux pages en a plusieurs. On les garde
     toutes, chacune avec son numero de page — sinon le surlignage
     dessinerait les boites de la page 2 sur la page 1.
     / A paragraph spanning two columns has several boxes; each keeps its page.
 
     Pour un markdown ou un texte brut, il n'y a pas de provenance
     physique : on rend un dictionnaire vide, ce que la spec prevoit.
@@ -421,31 +447,33 @@ def _provenance_de_l_element(element_docling):
     numero_de_page_principal = None
     for provenance in provenances:
         numero_de_page = getattr(provenance, "page_no", None)
         if numero_de_page_principal is None:
             numero_de_page_principal = numero_de_page
 
         boite = getattr(provenance, "bbox", None)
         if boite is None:
             continue
 
         boites.append({
             "l": getattr(boite, "l", None),
             "t": getattr(boite, "t", None),
             "r": getattr(boite, "r", None),
             "b": getattr(boite, "b", None),
-            "coord_origin": str(getattr(boite, "coord_origin", "") or ""),
+            "coord_origin": _coord_origin_en_chaine(
+                getattr(boite, "coord_origin", None),
+            ),
             "page_no": numero_de_page,
         })
 
     if not boites:
         return {}
 
     return {"page_no": numero_de_page_principal, "boites": boites}
 
 
 def creer_les_elements_d_une_page(page, elements_bruts):
     """
     Cree les ElementDocument d'une page a partir d'elements bruts.
     / Creates a page's ElementDocument rows from raw elements.
 
     LOCALISATION : hypostasis_extractor/services/ingestion_docling.py
diff --git a/hypostasis_extractor/tests/test_ingestion_docling.py b/hypostasis_extractor/tests/test_ingestion_docling.py
index eac972b..f24f4e3 100644
--- a/hypostasis_extractor/tests/test_ingestion_docling.py
+++ b/hypostasis_extractor/tests/test_ingestion_docling.py
@@ -3,30 +3,31 @@ Tests de l'ingestion Docling — SPEC v2 section 4 (phase D).
 / Tests for Docling ingestion — SPEC v2 section 4.
 
 LOCALISATION : hypostasis_extractor/tests/test_ingestion_docling.py
 
 Lancer avec :
     docker exec hypostasia_dev_web uv run python manage.py test \\
         hypostasis_extractor.tests.test_ingestion_docling
 
 La conversion Docling elle-meme est lente (chargement de modeles). Les
 tests qui l'appellent portent le tag "docling" et sont ignores par defaut,
 comme les tests d'appel LLM. Le reste — le parcours du document, la
 construction des elements — est teste avec un document simule.
 / Docling conversion is slow; those tests are tagged and opt-in.
 """
 
+import enum
 import os
 
 from django.test import TestCase, tag
 
 from core.models import ElementDocument, Page, empreinte_du_texte
 from hypostasis_extractor.services.ingestion_docling import (
     LABELS_SANS_CONTENU_UTILE,
     creer_les_elements_d_une_page,
     extraire_les_elements_bruts,
 )
 
 
 class FauxElementDocling:
     """
     Imite un element rendu par Docling.
@@ -43,30 +44,44 @@ class FauxElementDocling:
 class FausseBoite:
     def __init__(self, gauche, haut, droite, bas):
         self.l = gauche
         self.t = haut
         self.r = droite
         self.b = bas
         self.coord_origin = "BOTTOMLEFT"
 
 
 class FausseProvenance:
     def __init__(self, page_no, boite):
         self.page_no = page_no
         self.bbox = boite
 
 
+class CoordOriginFeinte(enum.Enum):
+    """
+    Imite l'enumeration CoordOrigin de docling-core.
+    / Mimics docling-core's CoordOrigin enum.
+
+    str() d'un membre d'enumeration rend "CoordOriginFeinte.BOTTOMLEFT" —
+    le prefixe de classe compris. C'est exactement le defaut reproduit
+    ici : Docling rend un membre, pas une chaine.
+    / str() on a member includes the class prefix; that is the bug.
+    """
+
+    BOTTOMLEFT = "BOTTOMLEFT"
+
+
 class FauxDocumentDocling:
     """Imite un DoclingDocument. / Mimics a DoclingDocument."""
 
     def __init__(self, elements):
         self._elements = elements
 
     def iterate_items(self):
         for element in self._elements:
             yield element, 0
 
 
 class ParcoursDuDocumentTest(TestCase):
     """
     Le parcours d'un document Docling, sans appeler Docling.
     / Walking a Docling document, without calling Docling.
@@ -207,30 +222,54 @@ class ProvenancePhysiqueTest(TestCase):
                 "Un paragraphe a cheval", "text",
                 provenances=[
                     FausseProvenance(3, FausseBoite(10, 100, 300, 50)),
                     FausseProvenance(4, FausseBoite(10, 750, 300, 700)),
                 ],
             ),
         ])
 
         elements = extraire_les_elements_bruts(document)
 
         boites = elements[0]["provenance"]["boites"]
         self.assertEqual(len(boites), 2)
         self.assertEqual(boites[0]["page_no"], 3)
         self.assertEqual(boites[1]["page_no"], 4)
 
+    def test_le_coord_origin_est_reduit_a_sa_valeur(self):
+        """
+        Docling rend un MEMBRE d'enumeration pour coord_origin, pas une
+        chaine. str() dessus produit "CoordOriginFeinte.BOTTOMLEFT" — le
+        prefixe de classe compris — inexploitable par un visualiseur PDF.
+        C'est `.value` qu'il faut : "BOTTOMLEFT".
+        / str() on the enum member leaks the class prefix; take `.value`.
+        """
+        boite = FausseBoite(10, 700, 500, 650)
+        boite.coord_origin = CoordOriginFeinte.BOTTOMLEFT
+        document = FauxDocumentDocling([
+            FauxElementDocling(
+                "Un paragraphe", "text",
+                provenances=[FausseProvenance(1, boite)],
+            ),
+        ])
+
+        elements = extraire_les_elements_bruts(document)
+
+        self.assertEqual(
+            elements[0]["provenance"]["boites"][0]["coord_origin"],
+            "BOTTOMLEFT",
+        )
+
 
 class CreationDesElementsTest(TestCase):
     """
     La creation des ElementDocument en base.
     / Creating the ElementDocument rows.
     """
 
     def setUp(self):
         self.page_de_test = Page.objects.create(
             url="http://exemple.local/page-ingestion",
             html_original="x", html_readability="x", text_readability="x",
             content_hash="empreinte_ingestion",
         )
 
     def test_les_elements_sont_crees_dans_l_ordre(self):

## NOUVEAU : commande de reparation
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
    28	LANCER LA COMMANDE
    29	
    30	    docker exec -w /app hypostasia_web uv run python manage.py \\
    31	        reparer_la_provenance_des_boites --a-blanc
    32	    docker exec -w /app hypostasia_web uv run python manage.py \\
    33	        reparer_la_provenance_des_boites
    34	"""
    35	
    36	from django.core.management.base import BaseCommand
    37	from django.db import transaction
    38	
    39	from core.models import ElementDocument
    40	
    41	# Le prefixe que str() sur un membre d'enum ajoute toujours.
    42	# / The prefix str() always adds on an enum member.
    43	PREFIXE_D_ENUMERATION = "CoordOrigin."
    44	
    45	
    46	class Command(BaseCommand):
    47	    help = (
    48	        "Corrige coord_origin dans la provenance des ElementDocument : "
    49	        "'CoordOrigin.BOTTOMLEFT' -> 'BOTTOMLEFT'. Ne touche a rien d'autre."
    50	    )
    51	
    52	    def add_arguments(self, analyseur_d_arguments):
    53	        analyseur_d_arguments.add_argument(
    54	            "--a-blanc", action="store_true",
    55	            help="Affiche ce qui serait corrige, sans rien ecrire.",
    56	        )
    57	
    58	    def handle(self, *args, **options):
    59	        a_blanc = options["a_blanc"]
    60	
    61	        if a_blanc:
    62	            self.stdout.write(self.style.WARNING(
    63	                "MODE A BLANC — rien ne sera ecrit.",
    64	            ))
    65	
    66	        # On ne prend que les elements qui ont une provenance : la
    67	        # grande majorite (md/html/txt/audio) n'en a pas et n'a rien a
    68	        # gagner a etre chargee ici.
    69	        # / Only elements with a provenance; most have none to load.
    70	        elements_avec_provenance = list(
    71	            ElementDocument.objects.exclude(provenance={}).order_by("pk"),
    72	        )
    73	
    74	        total_boites_corrigees = 0
    75	        total_boites_deja_propres = 0
    76	        elements_a_ecrire = []
    77	
    78	        for element in elements_avec_provenance:
    79	            boites = (element.provenance or {}).get("boites")
    80	            if not boites:
    81	                continue
    82	
    83	            element_modifie = False
    84	            for boite in boites:
    85	                valeur = boite.get("coord_origin")
    86	                if isinstance(valeur, str) and valeur.startswith(PREFIXE_D_ENUMERATION):
    87	                    boite["coord_origin"] = valeur[len(PREFIXE_D_ENUMERATION):]
    88	                    total_boites_corrigees += 1
    89	                    element_modifie = True
    90	                else:
    91	                    total_boites_deja_propres += 1
    92	
    93	            if element_modifie:
    94	                elements_a_ecrire.append(element)
    95	                self.stdout.write(
    96	                    f"  element {element.pk} (page {element.page_id}) : "
    97	                    f"coord_origin corrige",
    98	                )
    99	
   100	        if not a_blanc:
   101	            with transaction.atomic():
   102	                for element in elements_a_ecrire:
   103	                    element.save(update_fields=["provenance"])
   104	
   105	        self.stdout.write("")
   106	        self.stdout.write(
   107	            f"Elements avec provenance examines : {len(elements_avec_provenance)}",
   108	        )
   109	        self.stdout.write(f"Elements corriges                 : {len(elements_a_ecrire)}")
   110	        self.stdout.write(f"Boites corrigees                   : {total_boites_corrigees}")
   111	        self.stdout.write(f"Boites deja propres                : {total_boites_deja_propres}")
   112	
   113	        if a_blanc:
   114	            self.stdout.write(self.style.WARNING(
   115	                "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
   116	            ))
   117	        elif total_boites_corrigees == 0:
   118	            self.stdout.write("\nRien a faire : toutes les boites etaient deja propres.")

## NOUVEAU : ses tests
     1	"""
     2	Tests de la reparation du prefixe d'enumeration dans coord_origin
     3	(commande reparer_la_provenance_des_boites).
     4	/ Tests for stripping the enum class prefix from coord_origin.
     5	
     6	LOCALISATION : core/tests/test_reparation_provenance_boites.py
     7	
     8	CE QUE CETTE COMMANDE CORRIGE
     9	
    10	`hypostasis_extractor/services/ingestion_docling.py` faisait `str()` sur
    11	le membre d'enumeration CoordOrigin de docling-core, ce qui ecrivait
    12	"CoordOrigin.BOTTOMLEFT" en base au lieu de "BOTTOMLEFT". Le service est
    13	corrige, mais les boites deja en base portent encore le defaut : cette
    14	commande le repare, sans toucher aux coordonnees ni au reste de la
    15	provenance.
    16	/ The service is fixed; this command repairs the data already written
    17	with the bug.
    18	"""
    19	
    20	from io import StringIO
    21	
    22	from django.core.management import call_command
    23	from django.test import TestCase
    24	
    25	from core.models import ElementDocument, Page
    26	
    27	
    28	def creer_une_page(suffixe):
    29	    return Page.objects.create(
    30	        url=f"http://exemple.local/reparation-{suffixe}",
    31	        html_original="<p>o</p>", html_readability="<p>l</p>",
    32	        text_readability="Un contenu.",
    33	        content_hash=f"hash-reparation-{suffixe}",
    34	    )
    35	
    36	
    37	def creer_un_element(page, ordre, provenance):
    38	    return ElementDocument.objects.create(
    39	        page=page, ordre=ordre, label="text", texte="Un paragraphe.",
    40	        empreinte_contenu=f"empreinte-{ordre}", provenance=provenance,
    41	    )
    42	
    43	
    44	def provenance_avec_prefixe(page_no=3):
    45	    return {
    46	        "page_no": page_no,
    47	        "boites": [{
    48	            "l": 46.0, "t": 739.2, "r": 472.8, "b": 661.0,
    49	            "coord_origin": "CoordOrigin.BOTTOMLEFT",
    50	            "page_no": page_no,
    51	        }],
    52	    }
    53	
    54	
    55	class LaReparationCorrigeLeDefautTest(TestCase):
    56	    def test_le_prefixe_de_classe_est_retire(self):
    57	        page = creer_une_page("prefixe")
    58	        element = creer_un_element(page, 0, provenance_avec_prefixe())
    59	
    60	        call_command("reparer_la_provenance_des_boites", stdout=StringIO())
    61	
    62	        element.refresh_from_db()
    63	        self.assertEqual(
    64	            element.provenance["boites"][0]["coord_origin"], "BOTTOMLEFT",
    65	        )
    66	
    67	    def test_les_coordonnees_ne_bougent_pas(self):
    68	        """
    69	        Seul coord_origin change : les boites, le numero de page, tout le
    70	        reste de la provenance doit rester identique.
    71	        / Only coord_origin changes; everything else stays put.
    72	        """
    73	        page = creer_une_page("coords")
    74	        provenance = provenance_avec_prefixe(page_no=7)
    75	        element = creer_un_element(page, 0, provenance)
    76	
    77	        call_command("reparer_la_provenance_des_boites", stdout=StringIO())
    78	
    79	        element.refresh_from_db()
    80	        boite = element.provenance["boites"][0]
    81	        self.assertEqual(element.provenance["page_no"], 7)
    82	        self.assertEqual(boite["l"], 46.0)
    83	        self.assertEqual(boite["t"], 739.2)
    84	        self.assertEqual(boite["r"], 472.8)
    85	        self.assertEqual(boite["b"], 661.0)
    86	        self.assertEqual(boite["page_no"], 7)
    87	
    88	    def test_une_valeur_deja_propre_est_laissee_intacte(self):
    89	        page = creer_une_page("propre")
    90	        provenance = {
    91	            "page_no": 1,
    92	            "boites": [{
    93	                "l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0,
    94	                "coord_origin": "BOTTOMLEFT", "page_no": 1,
    95	            }],
    96	        }
    97	        element = creer_un_element(page, 0, provenance)
    98	
    99	        call_command("reparer_la_provenance_des_boites", stdout=StringIO())
   100	
   101	        element.refresh_from_db()
   102	        self.assertEqual(
   103	            element.provenance["boites"][0]["coord_origin"], "BOTTOMLEFT",
   104	        )
   105	
   106	    def test_une_provenance_sans_boite_est_laissee_intacte(self):
   107	        page = creer_une_page("vide")
   108	        element = creer_un_element(page, 0, {})
   109	
   110	        call_command("reparer_la_provenance_des_boites", stdout=StringIO())
   111	
   112	        element.refresh_from_db()
   113	        self.assertEqual(element.provenance, {})
   114	
   115	    def test_la_reparation_est_idempotente(self):
   116	        page = creer_une_page("idempotence")
   117	        element = creer_un_element(page, 0, provenance_avec_prefixe())
   118	
   119	        call_command("reparer_la_provenance_des_boites", stdout=StringIO())
   120	
   121	        sortie_second_passage = StringIO()
   122	        call_command(
   123	            "reparer_la_provenance_des_boites", stdout=sortie_second_passage,
   124	        )
   125	
   126	        element.refresh_from_db()
   127	        self.assertEqual(
   128	            element.provenance["boites"][0]["coord_origin"], "BOTTOMLEFT",
   129	        )
   130	        self.assertIn("0", sortie_second_passage.getvalue())
   131	
   132	    def test_a_blanc_n_ecrit_rien(self):
   133	        page = creer_une_page("a-blanc")
   134	        element = creer_un_element(page, 0, provenance_avec_prefixe())
   135	
   136	        call_command(
   137	            "reparer_la_provenance_des_boites", "--a-blanc", stdout=StringIO(),
   138	        )
   139	
   140	        element.refresh_from_db()
   141	        self.assertEqual(
   142	            element.provenance["boites"][0]["coord_origin"],
   143	            "CoordOrigin.BOTTOMLEFT",
   144	        )
