### FICHIERS DE LA TACHE 1 (nouveaux, pas de diff : contenu integral)

=== front/management/commands/charger_fixtures_sample.py ===
     1	"""
     2	Charge les documents etalons de sample/ dans une base vide.
     3	/ Loads the reference documents from sample/ into an empty database.
     4	
     5	LOCALISATION : front/management/commands/charger_fixtures_sample.py
     6	
     7	POURQUOI CETTE COMMANDE
     8	
     9	Une base neuve n'a ni utilisateur, ni carnet, ni note : il n'y a rien a
    10	regarder, donc rien a developper. `sample/` porte les documents etalons
    11	choisis pour couvrir les quatre formes d'entree du produit — capture
    12	web, fichier ecrit, transcription deja faite, audio brut. Cette commande
    13	les transforme en base utilisable.
    14	
    15	CE QU'ELLE NE FAIT PAS
    16	
    17	Elle n'appelle JAMAIS Docling sur un PDF ni sur un docx. Une commande de
    18	fixtures qui convertit des PDF en masse a fait tomber le serveur le
    19	10 aout 2026. Le PDF a son propre chemin, mesure, une conversion a la
    20	fois.
    21	/ It never runs Docling on a PDF: mass conversion took the server down.
    22	
    23	LANCER LA COMMANDE
    24	
    25	    docker exec -w /app hypostasia_web uv run python manage.py \\
    26	        charger_fixtures_sample --a-blanc
    27	    docker exec -w /app hypostasia_web uv run python manage.py \\
    28	        charger_fixtures_sample
    29	"""
    30	
    31	import os
    32	
    33	from django.contrib.auth import get_user_model
    34	from django.core.management.base import BaseCommand
    35	
    36	from core.models import Dossier, TranscriptionConfig, VisibiliteDossier
    37	
    38	User = get_user_model()
    39	
    40	NOM_DU_CARNET = "Documents étalons"
    41	
    42	# Memes identifiants que charger_fixtures_demo : un seul mot de passe a
    43	# retenir, quel que soit l'ordre dans lequel les deux commandes tournent.
    44	# / Same credentials as charger_fixtures_demo: one password to remember.
    45	UTILISATEUR_PAR_DEFAUT = {
    46	    "username": "jonas",
    47	    "email": "jonas@demo.hypostasia.org",
    48	    "password": "admin1234",
    49	}
    50	
    51	
    52	class Command(BaseCommand):
    53	    help = (
    54	        "Charge les documents etalons de sample/ (capture web, markdown, "
    55	        "transcription JSON, audio) dans un carnet de demonstration. "
    56	        "N'appelle jamais Docling sur un PDF ou un docx."
    57	    )
    58	
    59	    def add_arguments(self, analyseur_d_arguments):
    60	        analyseur_d_arguments.add_argument(
    61	            "--a-blanc", action="store_true",
    62	            help="Affiche ce qui serait fait, sans rien ecrire.",
    63	        )
    64	
    65	    def handle(self, *args, **options):
    66	        self.a_blanc = options["a_blanc"]
    67	
    68	        if self.a_blanc:
    69	            self.stdout.write(self.style.WARNING(
    70	                "MODE A BLANC — rien ne sera ecrit.",
    71	            ))
    72	
    73	        proprietaire = self._proprietaire()
    74	        carnet_des_etalons = self._creer_le_carnet(proprietaire)
    75	        self._creer_la_config_de_transcription()
    76	
    77	        self._charger_les_documents(proprietaire, carnet_des_etalons)
    78	
    79	        if self.a_blanc:
    80	            self.stdout.write(self.style.WARNING(
    81	                "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
    82	            ))
    83	
    84	    def _proprietaire(self):
    85	        """
    86	        Rend le proprietaire des notes etalons, en le creant s'il le faut.
    87	        / Returns the reference notes' owner, creating one if needed.
    88	
    89	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
    90	
    91	        Une base neuve n'a AUCUN utilisateur. `charger_fixtures_llm_reel`
    92	        leve une CommandError dans ce cas — c'est precisement le cas que
    93	        cette commande doit savoir traiter.
    94	        / A fresh database has no user at all; this must not be fatal.
    95	        """
    96	        proprietaire_existant = User.objects.filter(
    97	            is_superuser=True,
    98	        ).order_by("pk").first()
    99	        if proprietaire_existant is None:
   100	            proprietaire_existant = User.objects.order_by("pk").first()
   101	
   102	        if proprietaire_existant is not None:
   103	            self.stdout.write(
   104	                f"Propriétaire        : {proprietaire_existant.username} (réutilisé)",
   105	            )
   106	            return proprietaire_existant
   107	
   108	        self.stdout.write(
   109	            f"Propriétaire        : {UTILISATEUR_PAR_DEFAUT['username']} (créé)",
   110	        )
   111	        if self.a_blanc:
   112	            return None
   113	
   114	        proprietaire_cree = User.objects.create_user(
   115	            username=UTILISATEUR_PAR_DEFAUT["username"],
   116	            email=UTILISATEUR_PAR_DEFAUT["email"],
   117	            is_staff=True,
   118	        )
   119	        proprietaire_cree.set_password(UTILISATEUR_PAR_DEFAUT["password"])
   120	        proprietaire_cree.save()
   121	        return proprietaire_cree
   122	
   123	    def _creer_le_carnet(self, proprietaire):
   124	        """
   125	        Rend le carnet des documents etalons, en le creant s'il le faut.
   126	        / Returns the reference notebook, creating it if needed.
   127	
   128	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   129	        """
   130	        if self.a_blanc:
   131	            self.stdout.write(f"Carnet              : {NOM_DU_CARNET} (serait créé)")
   132	            return None
   133	
   134	        carnet, a_ete_cree = Dossier.objects.get_or_create(
   135	            name=NOM_DU_CARNET, owner=proprietaire,
   136	            defaults={"visibilite": VisibiliteDossier.PUBLIC},
   137	        )
   138	        self.stdout.write(
   139	            f"Carnet              : {NOM_DU_CARNET} — pk={carnet.pk} "
   140	            f"({'créé' if a_ete_cree else 'réutilisé'})",
   141	        )
   142	        return carnet
   143	
   144	    def _creer_la_config_de_transcription(self):
   145	        """
   146	        Cree la configuration Voxtral, si la cle API est presente.
   147	        / Creates the Voxtral configuration, if the API key is present.
   148	
   149	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   150	
   151	        SANS CETTE CONFIG, LA TRANSCRIPTION EST MOCKEE EN SILENCE.
   152	
   153	        front/tasks.py:633 teste `config.provider == "voxtral"` et retombe
   154	        sinon sur `transcrire_audio_mock`. Sur une base neuve il n'existe
   155	        aucune config : le mp3 produirait un faux verbatim que rien ne
   156	        distinguerait d'une vraie transcription.
   157	        / Without this config the transcription is silently mocked.
   158	
   159	        Cle absente : on ne cree RIEN. Une config qui echouera au premier
   160	        appel est pire que pas de config — elle donne l'illusion que la
   161	        chaine est branchee. / An about-to-fail config is worse than none.
   162	        """
   163	        if not os.environ.get("MISTRAL_API_KEY"):
   164	            self.stdout.write(
   165	                "Transcription       : pas de MISTRAL_API_KEY — config non créée",
   166	            )
   167	            return None
   168	
   169	        if self.a_blanc:
   170	            self.stdout.write("Transcription       : Voxtral Mini (serait créée)")
   171	            return None
   172	
   173	        config, a_ete_creee = TranscriptionConfig.objects.get_or_create(
   174	            name="Voxtral Mini",
   175	            defaults={
   176	                "model_choice": "voxtral-mini-latest",
   177	                "is_active": True,
   178	                "diarization_enabled": True,
   179	                "language": "",
   180	            },
   181	        )
   182	        self.stdout.write(
   183	            f"Transcription       : {config.name} "
   184	            f"({'créée' if a_ete_creee else 'réutilisée'})",
   185	        )
   186	        return config
   187	
   188	    def _charger_les_documents(self, proprietaire, carnet_des_etalons):
   189	        """
   190	        Charge les quatre documents etalons. Rempli aux taches 2 et 3.
   191	        / Loads the four reference documents. Filled in by tasks 2 and 3.
   192	
   193	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   194	        """
   195	        return None

=== front/tests/test_charger_fixtures_sample.py ===
     1	"""
     2	Tests de la commande charger_fixtures_sample.
     3	/ Tests for the charger_fixtures_sample command.
     4	
     5	LOCALISATION : front/tests/test_charger_fixtures_sample.py
     6	"""
     7	
     8	from io import StringIO
     9	from unittest.mock import patch
    10	
    11	from django.contrib.auth import get_user_model
    12	from django.core.management import call_command
    13	from django.test import TestCase
    14	
    15	from core.models import Dossier, Page, TranscriptionConfig
    16	
    17	User = get_user_model()
    18	
    19	
    20	class ProprietaireEtCarnetTest(TestCase):
    21	    """Le socle : qui possède les notes étalons, et où elles sont rangées."""
    22	
    23	    def test_a_blanc_ne_cree_aucun_utilisateur(self):
    24	        # Une base neuve n'a personne, et le mode a blanc n'y change
    25	        # rien : il annonce ce qu'il ferait, sans l'ecrire.
    26	        # / A dry run announces without writing, users included.
    27	        self.assertEqual(User.objects.count(), 0)
    28	
    29	        call_command("charger_fixtures_sample", "--a-blanc", stdout=StringIO())
    30	
    31	        self.assertEqual(User.objects.count(), 0)
    32	
    33	    def test_le_superuser_existant_est_reutilise(self):
    34	        superuser_existant = User.objects.create_superuser(
    35	            username="deja_la", email="deja@example.org", password="x",
    36	        )
    37	
    38	        sortie = StringIO()
    39	        with patch.object(
    40	            __import__(
    41	                "front.management.commands.charger_fixtures_sample",
    42	                fromlist=["Command"],
    43	            ).Command,
    44	            "_charger_les_documents",
    45	            return_value=None,
    46	        ):
    47	            call_command("charger_fixtures_sample", stdout=sortie)
    48	
    49	        self.assertEqual(User.objects.count(), 1)
    50	        self.assertEqual(User.objects.first().pk, superuser_existant.pk)
    51	        self.assertIn("réutilisé", sortie.getvalue())
    52	
    53	    def test_sans_utilisateur_la_commande_cree_jonas(self):
    54	        sortie = StringIO()
    55	        with patch.object(
    56	            __import__(
    57	                "front.management.commands.charger_fixtures_sample",
    58	                fromlist=["Command"],
    59	            ).Command,
    60	            "_charger_les_documents",
    61	            return_value=None,
    62	        ):
    63	            call_command("charger_fixtures_sample", stdout=sortie)
    64	
    65	        utilisateur_cree = User.objects.get(username="jonas")
    66	        self.assertTrue(utilisateur_cree.is_staff)
    67	        self.assertTrue(utilisateur_cree.check_password("admin1234"))
    68	
    69	    def test_le_carnet_est_cree_une_seule_fois(self):
    70	        sortie = StringIO()
    71	        with patch.object(
    72	            __import__(
    73	                "front.management.commands.charger_fixtures_sample",
    74	                fromlist=["Command"],
    75	            ).Command,
    76	            "_charger_les_documents",
    77	            return_value=None,
    78	        ):
    79	            call_command("charger_fixtures_sample", stdout=sortie)
    80	            call_command("charger_fixtures_sample", stdout=sortie)
    81	
    82	        self.assertEqual(
    83	            Dossier.objects.filter(name="Documents étalons").count(), 1,
    84	        )
    85	
    86	    def test_la_config_voxtral_est_creee_si_la_cle_est_la(self):
    87	        with patch.dict("os.environ", {"MISTRAL_API_KEY": "une-cle-de-test"}):
    88	            with patch.object(
    89	                __import__(
    90	                    "front.management.commands.charger_fixtures_sample",
    91	                    fromlist=["Command"],
    92	                ).Command,
    93	                "_charger_les_documents",
    94	                return_value=None,
    95	            ):
    96	                call_command("charger_fixtures_sample", stdout=StringIO())
    97	
    98	        config = TranscriptionConfig.objects.get(name="Voxtral Mini")
    99	        self.assertTrue(config.is_active)
   100	        self.assertEqual(config.provider, "voxtral")
   101	
   102	    def test_sans_cle_mistral_aucune_config_n_est_creee(self):
   103	        # Creer une config qui echouera au premier appel serait pire que
   104	        # ne pas en creer : la transcription retomberait sur le mock, en
   105	        # silence. / A config that will fail is worse than no config.
   106	        with patch.dict("os.environ", {}, clear=False):
   107	            import os
   108	
   109	            os.environ.pop("MISTRAL_API_KEY", None)
   110	            with patch.object(
   111	                __import__(
   112	                    "front.management.commands.charger_fixtures_sample",
   113	                    fromlist=["Command"],
   114	                ).Command,
   115	                "_charger_les_documents",
   116	                return_value=None,
   117	            ):
   118	                call_command("charger_fixtures_sample", stdout=StringIO())
   119	
   120	        self.assertEqual(TranscriptionConfig.objects.count(), 0)
   121	
   122	    def test_a_blanc_n_ecrit_rien(self):
   123	        call_command("charger_fixtures_sample", "--a-blanc", stdout=StringIO())
   124	
   125	        self.assertEqual(Page.objects.count(), 0)
   126	        self.assertEqual(Dossier.objects.count(), 0)
   127	        self.assertEqual(User.objects.count(), 0)
   128	        self.assertEqual(TranscriptionConfig.objects.count(), 0)
