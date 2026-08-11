### PAQUET DE REVUE FINALE — plan charger_fixtures_sample, taches 1 a 6

Deux fichiers NEUFS (contenu integral) et un fichier MODIFIE (diff).

## NEUF : front/management/commands/charger_fixtures_sample.py
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
    31	import hashlib
    32	import os
    33	from pathlib import Path
    34	
    35	from django.conf import settings
    36	from django.contrib.auth import get_user_model
    37	from django.core.files.base import ContentFile
    38	from django.core.management.base import BaseCommand
    39	
    40	from core.models import Dossier, Page, TranscriptionConfig, VisibiliteDossier
    41	from core.services.corpus import ranger_une_note_dans_un_carnet
    42	
    43	User = get_user_model()
    44	
    45	NOM_DU_CARNET = "Documents étalons"
    46	
    47	REPERTOIRE_SAMPLE = Path(settings.BASE_DIR) / "sample"
    48	
    49	FICHIER_DE_LA_CAPTURE = "capture-web-badgeons-la-normandie.html"
    50	FICHIER_DU_MARKDOWN = "PRESENTATION-V3.md"
    51	FICHIER_DE_LA_TRANSCRIPTION = "fake_debat_ia_transcription.json"
    52	FICHIER_DU_MP3 = "audio-FR-2locuteur-palaiscesar-14s.mp3"
    53	
    54	# Les formats que cette commande ne convertit jamais elle-meme : Docling
    55	# les mesure a 2 a 3,4 Gio et 80 a 164 s selon la taille (mesure du
    56	# 11 aout 2026, voir tmp/benchmark-docling-2026-08-11.md). Ils ont leur
    57	# propre chemin, une conversion a la fois. / Formats this command never
    58	# converts itself: measured at 2-3.4 GiB and 80-164s, see the benchmark
    59	# file above. They have their own path, one conversion at a time.
    60	EXTENSIONS_REFUSEES = {".pdf", ".docx"}
    61	
    62	# Les quatre documents etalons, par nom de fichier, dans l'ordre de
    63	# chargement. `--fichier` restreint a un sous-ensemble de cette table.
    64	# / The four reference documents, in loading order.
    65	DOCUMENTS_ETALONS = [
    66	    FICHIER_DE_LA_CAPTURE,
    67	    FICHIER_DU_MARKDOWN,
    68	    FICHIER_DE_LA_TRANSCRIPTION,
    69	    FICHIER_DU_MP3,
    70	]
    71	
    72	# L'article d'origine. Sans url, l'idempotence de la capture porterait
    73	# sur un champ vide et deux captures se confondraient.
    74	# / Without a url, the capture's idempotency key would be empty.
    75	URL_DE_LA_CAPTURE = "https://badgeons-la-normandie.fr/"
    76	
    77	# Memes identifiants que charger_fixtures_demo : un seul mot de passe a
    78	# retenir, quel que soit l'ordre dans lequel les deux commandes tournent.
    79	# / Same credentials as charger_fixtures_demo: one password to remember.
    80	UTILISATEUR_PAR_DEFAUT = {
    81	    "username": "jonas",
    82	    "email": "jonas@demo.hypostasia.org",
    83	    "password": "admin1234",
    84	}
    85	
    86	
    87	class Command(BaseCommand):
    88	    help = (
    89	        "Charge les documents etalons de sample/ (capture web, markdown, "
    90	        "transcription JSON, audio) dans un carnet de demonstration. "
    91	        "N'appelle jamais Docling sur un PDF ou un docx."
    92	    )
    93	
    94	    def add_arguments(self, analyseur_d_arguments):
    95	        analyseur_d_arguments.add_argument(
    96	            "--a-blanc", action="store_true",
    97	            help="Affiche ce qui serait fait, sans rien ecrire.",
    98	        )
    99	        analyseur_d_arguments.add_argument(
   100	            "--sans-mp3", action="store_true",
   101	            help="Saute la transcription Voxtral du fichier audio.",
   102	        )
   103	        analyseur_d_arguments.add_argument(
   104	            "--fichier", action="append", default=None, dest="fichiers",
   105	            help=(
   106	                "Ne charger que ce fichier de sample/, au lieu des quatre. "
   107	                "Repetable."
   108	            ),
   109	        )
   110	        analyseur_d_arguments.add_argument(
   111	            "--reset", action="store_true",
   112	            help=(
   113	                "Supprime le carnet etalon et ses notes propres avant de "
   114	                "recharger. Refuse si une note porte des ancres."
   115	            ),
   116	        )
   117	
   118	    def handle(self, *args, **options):
   119	        self.a_blanc = options["a_blanc"]
   120	        self.sans_mp3 = options["sans_mp3"]
   121	        # Resolu AVANT toute ecriture et toute conversion : un --fichier
   122	        # pointant un PDF doit rendre la main immediatement, pas apres
   123	        # avoir lance Docling. / Resolved before any write or conversion.
   124	        self.fichiers_demandes = self._resoudre_les_fichiers_demandes(
   125	            options["fichiers"],
   126	        )
   127	
   128	        if self.a_blanc:
   129	            self.stdout.write(self.style.WARNING(
   130	                "MODE A BLANC — rien ne sera ecrit.",
   131	            ))
   132	
   133	        proprietaire = self._proprietaire()
   134	
   135	        if options["reset"]:
   136	            self._reinitialiser(proprietaire)
   137	
   138	        carnet_des_etalons = self._creer_le_carnet(proprietaire)
   139	        self._creer_la_config_de_transcription()
   140	
   141	        self._charger_les_documents(proprietaire, carnet_des_etalons)
   142	
   143	        if self.a_blanc:
   144	            self.stdout.write(self.style.WARNING(
   145	                "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
   146	            ))
   147	
   148	    def _resoudre_les_fichiers_demandes(self, fichiers_de_l_option):
   149	        """
   150	        Rend la liste des fichiers a charger, en refusant les formats lourds.
   151	        / Returns the files to load, refusing the heavy formats.
   152	
   153	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   154	
   155	        POURQUOI REFUSER PLUTOT QU'IGNORER
   156	
   157	        Le PDF et le docx n'ont pas ete eprouves par Docling sur cette
   158	        machine. Une commande de fixtures qui convertit des PDF en masse a
   159	        fait tomber le serveur le 10 aout 2026 : 2 031 Mio et 98 s pour
   160	        trois pages. Les laisser passer en silence rejouerait l'incident ;
   161	        les refuser en le disant oriente vers le chemin prevu pour eux.
   162	        / Refusing loudly beats ignoring silently: mass PDF conversion
   163	        took the server down.
   164	        """
   165	        from django.core.management.base import CommandError
   166	
   167	        if not fichiers_de_l_option:
   168	            return list(DOCUMENTS_ETALONS)
   169	
   170	        fichiers_retenus = []
   171	        for chemin_demande in fichiers_de_l_option:
   172	            nom_du_fichier = os.path.basename(chemin_demande)
   173	            extension = os.path.splitext(nom_du_fichier)[1].lower()
   174	
   175	            if extension in EXTENSIONS_REFUSEES:
   176	                raise CommandError(
   177	                    f"« {nom_du_fichier} » est un {extension} : cette "
   178	                    f"commande ne lance jamais Docling sur ce format. Une "
   179	                    f"conversion de PDF coûte de 2 à 3,4 Gio et de 80 à "
   180	                    f"164 s selon la taille (mesure du 11 août 2026, voir "
   181	                    f"tmp/benchmark-docling-2026-08-11.md) ; une commande "
   182	                    f"de fixtures qui en enchaîne a fait tomber le serveur "
   183	                    f"le 10 août. Le PDF et le docx ont un chemin "
   184	                    f"d'ingestion dédié, mesuré, une conversion à la "
   185	                    f"fois — la commande qui rejouera ces fixtures déjà "
   186	                    f"converties sans Docling est prévue mais n'existe "
   187	                    f"pas encore dans ce dépôt.",
   188	                )
   189	
   190	            if nom_du_fichier not in DOCUMENTS_ETALONS:
   191	                raise CommandError(
   192	                    f"« {nom_du_fichier} » n'est pas un document étalon. "
   193	                    f"Attendus : {', '.join(DOCUMENTS_ETALONS)}.",
   194	                )
   195	
   196	            fichiers_retenus.append(nom_du_fichier)
   197	
   198	        return fichiers_retenus
   199	
   200	    def _proprietaire(self):
   201	        """
   202	        Rend le proprietaire des notes etalons, en le creant s'il le faut.
   203	        / Returns the reference notes' owner, creating one if needed.
   204	
   205	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   206	
   207	        Une base neuve n'a AUCUN utilisateur. `charger_fixtures_llm_reel`
   208	        leve une CommandError dans ce cas — c'est precisement le cas que
   209	        cette commande doit savoir traiter.
   210	        / A fresh database has no user at all; this must not be fatal.
   211	        """
   212	        proprietaire_existant = User.objects.filter(
   213	            is_superuser=True,
   214	        ).order_by("pk").first()
   215	        if proprietaire_existant is None:
   216	            proprietaire_existant = User.objects.order_by("pk").first()
   217	
   218	        if proprietaire_existant is not None:
   219	            self.stdout.write(
   220	                f"Propriétaire        : {proprietaire_existant.username} (réutilisé)",
   221	            )
   222	            return proprietaire_existant
   223	
   224	        self.stdout.write(
   225	            f"Propriétaire        : {UTILISATEUR_PAR_DEFAUT['username']} (créé)",
   226	        )
   227	        if self.a_blanc:
   228	            return None
   229	
   230	        proprietaire_cree = User.objects.create_user(
   231	            username=UTILISATEUR_PAR_DEFAUT["username"],
   232	            email=UTILISATEUR_PAR_DEFAUT["email"],
   233	            is_staff=True,
   234	        )
   235	        proprietaire_cree.set_password(UTILISATEUR_PAR_DEFAUT["password"])
   236	        proprietaire_cree.save()
   237	        return proprietaire_cree
   238	
   239	    def _creer_le_carnet(self, proprietaire):
   240	        """
   241	        Rend le carnet des documents etalons, en le creant s'il le faut.
   242	        / Returns the reference notebook, creating it if needed.
   243	
   244	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   245	        """
   246	        if self.a_blanc:
   247	            self.stdout.write(f"Carnet              : {NOM_DU_CARNET} (serait créé)")
   248	            return None
   249	
   250	        carnet, a_ete_cree = Dossier.objects.get_or_create(
   251	            name=NOM_DU_CARNET, owner=proprietaire,
   252	            defaults={"visibilite": VisibiliteDossier.PUBLIC},
   253	        )
   254	        self.stdout.write(
   255	            f"Carnet              : {NOM_DU_CARNET} — pk={carnet.pk} "
   256	            f"({'créé' if a_ete_cree else 'réutilisé'})",
   257	        )
   258	        return carnet
   259	
   260	    def _creer_la_config_de_transcription(self):
   261	        """
   262	        Cree la configuration Voxtral, si la cle API est presente.
   263	        / Creates the Voxtral configuration, if the API key is present.
   264	
   265	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   266	
   267	        SANS CETTE CONFIG, LA TRANSCRIPTION EST MOCKEE EN SILENCE.
   268	
   269	        front/tasks.py:633 teste `config.provider == "voxtral"` et retombe
   270	        sinon sur `transcrire_audio_mock`. Sur une base neuve il n'existe
   271	        aucune config : le mp3 produirait un faux verbatim que rien ne
   272	        distinguerait d'une vraie transcription.
   273	        / Without this config the transcription is silently mocked.
   274	
   275	        Cle absente : on ne cree RIEN. Une config qui echouera au premier
   276	        appel est pire que pas de config — elle donne l'illusion que la
   277	        chaine est branchee. / An about-to-fail config is worse than none.
   278	        """
   279	        if not os.environ.get("MISTRAL_API_KEY"):
   280	            self.stdout.write(
   281	                "Transcription       : pas de MISTRAL_API_KEY — config non créée",
   282	            )
   283	            return None
   284	
   285	        if self.a_blanc:
   286	            self.stdout.write("Transcription       : Voxtral Mini (serait créée)")
   287	            return None
   288	
   289	        config, a_ete_creee = TranscriptionConfig.objects.get_or_create(
   290	            name="Voxtral Mini",
   291	            defaults={
   292	                "model_choice": "voxtral-mini-latest",
   293	                "is_active": True,
   294	                "diarization_enabled": True,
   295	                "language": "",
   296	            },
   297	        )
   298	        self.stdout.write(
   299	            f"Transcription       : {config.name} "
   300	            f"({'créée' if a_ete_creee else 'réutilisée'})",
   301	        )
   302	        return config
   303	
   304	    def _reinitialiser(self, proprietaire):
   305	        """
   306	        Supprime le carnet etalon et les notes qui n'appartiennent qu'a lui.
   307	        / Deletes the reference notebook and the notes filed only in it.
   308	
   309	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   310	
   311	        POURQUOI CETTE OPTION EXISTE
   312	
   313	        L'idempotence saute ce qui est deja la — y compris l'appel Voxtral,
   314	        qu'on veut precisement pouvoir rejouer a chaque chargement. `--reset`
   315	        est la seule facon de tout refaire.
   316	        / Idempotency skips the Voxtral call we want to replay.
   317	
   318	        LE GARDE-FOU N'EST PAS FACULTATIF
   319	
   320	        `AncrageExtraction.element` est en PROTECT : supprimer une page qui
   321	        porte des ancres leve ProtectedError. On ne se contente pas de
   322	        laisser l'exception sortir — on VERIFIE D'ABORD, et on refuse tout
   323	        en bloc. Une suppression partielle laisserait le carnet a moitie
   324	        vide, dans un etat que personne n'a voulu.
   325	        / Check first and refuse wholesale: a partial delete is worse.
   326	        """
   327	        from django.core.management.base import CommandError
   328	
   329	        from hypostasis_extractor.models import AncrageExtraction
   330	
   331	        carnet_existant = Dossier.objects.filter(
   332	            name=NOM_DU_CARNET, owner=proprietaire,
   333	        ).first()
   334	        if carnet_existant is None:
   335	            self.stdout.write("Réinitialisation    : aucun carnet à supprimer")
   336	            return None
   337	
   338	        # Les notes rangees UNIQUEMENT dans ce carnet sont a nous. Une note
   339	        # rangee ailleurs aussi appartient a ce quelqu'un d'autre.
   340	        # / Only notes filed solely here are ours to remove.
   341	        notes_a_supprimer = []
   342	        for page in Page.objects.filter(
   343	            appartenances_dossiers__dossier=carnet_existant,
   344	        ).distinct():
   345	            rangee_ailleurs = page.appartenances_dossiers.exclude(
   346	                dossier=carnet_existant,
   347	            ).exists()
   348	            if not rangee_ailleurs:
   349	                notes_a_supprimer.append(page)
   350	
   351	        # VERIFIER AVANT DE SUPPRIMER.
   352	        notes_avec_ancres = []
   353	        for page in notes_a_supprimer:
   354	            nombre_d_ancres = AncrageExtraction.objects.filter(
   355	                element__page=page,
   356	            ).count()
   357	            if nombre_d_ancres:
   358	                notes_avec_ancres.append((page, nombre_d_ancres))
   359	
   360	        if notes_avec_ancres:
   361	            detail = " ; ".join(
   362	                f"« {page.title} » ({nombre} ancre(s))"
   363	                for page, nombre in notes_avec_ancres
   364	            )
   365	            raise CommandError(
   366	                f"--reset refusé : {detail}. Ces notes portent des "
   367	                f"extractions ancrées, et une ancre est une preuve. Rien "
   368	                f"n'a été supprimé. Retirer les portions d'abord, ou "
   369	                f"recharger dans une base neuve.",
   370	            )
   371	
   372	        if self.a_blanc:
   373	            self.stdout.write(
   374	                f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
   375	                f"seraient supprimées",
   376	            )
   377	            return None
   378	
   379	        for page in notes_a_supprimer:
   380	            page.delete()
   381	        carnet_existant.delete()
   382	
   383	        self.stdout.write(
   384	            f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
   385	            f"supprimée(s), carnet supprimé",
   386	        )
   387	        return None
   388	
   389	    def _note_deja_presente(self, carnet_des_etalons, nom_du_fichier):
   390	        """
   391	        Dit si une note issue de ce fichier est deja dans le carnet.
   392	        / Says whether a note from this file is already in the notebook.
   393	
   394	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   395	
   396	        On regarde AVANT de convertir. Le service porte bien un garde-fou
   397	        — `creer_les_elements_d_une_page` leve si la page a deja des
   398	        elements — mais il arrive APRES la conversion Docling. S'y fier
   399	        ferait payer 98 s pour un PDF de 3 pages, et rien produire.
   400	        / The service's guard comes after conversion; this one comes before.
   401	        """
   402	        if carnet_des_etalons is None:
   403	            return False
   404	        return Page.objects.filter(
   405	            appartenances_dossiers__dossier=carnet_des_etalons,
   406	            original_filename=nom_du_fichier,
   407	        ).exists()
   408	
   409	    def _charger_les_documents(self, proprietaire, carnet_des_etalons):
   410	        """
   411	        Charge les documents etalons, un par forme d'entree.
   412	        / Loads the reference documents, one per input form.
   413	
   414	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   415	        """
   416	        self._charger_la_capture_web(proprietaire, carnet_des_etalons)
   417	        self._charger_le_markdown(proprietaire, carnet_des_etalons)
   418	        self._charger_la_transcription_json(proprietaire, carnet_des_etalons)
   419	        self._charger_le_mp3(proprietaire, carnet_des_etalons)
   420	
   421	    def _charger_la_capture_web(self, proprietaire, carnet_des_etalons):
   422	        """
   423	        Cree la note issue de la capture web, et l'ingere.
   424	        / Creates the note from the web capture, and ingests it.
   425	
   426	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   427	
   428	        C'est la SEULE fixture qui eprouve les labels de structure d'un
   429	        HTML reel : section_header, list_item, text. Les pages « Wikipedia »
   430	        de charger_fixtures_demo n'ont que des <p> et sortent toutes en
   431	        `text`. / The only fixture exercising real HTML structure labels.
   432	
   433	        C'EST AUSSI LA SEULE DES QUATRE A VERIFIER UNE CONTRAINTE GLOBALE
   434	        AVANT DE CREER.
   435	
   436	        Elle est la seule des quatre fixtures a porter une `url` : le
   437	        markdown, la transcription JSON et le mp3 la creent a `None`. Or
   438	        `unique_url_si_presente` (core/models.py:321-325) est une
   439	        contrainte GLOBALE sur `url`, non scopee par carnet ni par
   440	        proprietaire — sa condition `url__isnull=False` exempte les trois
   441	        autres, qui n'ont donc pas besoin de ce garde. Ne pas « harmoniser »
   442	        les quatre methodes par symetrie : les trois autres n'ont rien a
   443	        verifier.
   444	        / Only this one carries a `url`; the other three create it as
   445	        None and are exempted by the constraint's `url__isnull=False`
   446	        condition. Do not "harmonize" the four loaders by apparent
   447	        symmetry — the other three have nothing to check.
   448	
   449	        Ce garde s'applique a CHAQUE execution, pas seulement apres un
   450	        --reset : c'est une consequence de la contrainte globale, pas une
   451	        specificite du reset. --reset est simplement le chemin qui le
   452	        rend visible en pratique (une page « rangee ailleurs » survit au
   453	        reset, puis le carnet recree tente de la re-creer).
   454	        / This guard runs on every execution, not only after --reset —
   455	        --reset is merely the path that makes the collision reachable.
   456	        """
   457	        # Garde : --fichier peut avoir exclu ce document.
   458	        # / Guard: --fichier may have excluded this document.
   459	        if FICHIER_DE_LA_CAPTURE not in self.fichiers_demandes:
   460	            return None
   461	
   462	        if self._note_deja_presente(carnet_des_etalons, FICHIER_DE_LA_CAPTURE):
   463	            self.stdout.write("Capture web         : déjà présente — sautée")
   464	            return None
   465	
   466	        if self.a_blanc:
   467	            self.stdout.write("Capture web         : serait chargée")
   468	            return None
   469	
   470	        # `url` est unique en base (contrainte unique_url_si_presente,
   471	        # non scopee par carnet). --reset peut avoir garde cette page
   472	        # ailleurs (rangee aussi dans un autre carnet, donc pas a nous
   473	        # de la supprimer) : on la range ici plutot que d'en tenter un
   474	        # doublon que la contrainte refuserait. / `url` is globally
   475	        # unique. --reset may have kept this page elsewhere (also filed
   476	        # in another notebook, so not ours to delete): file it here
   477	        # instead of attempting a duplicate the DB constraint rejects.
   478	        #
   479	        # SCOPE SUR proprietaire : sans ce filtre, la commande peut
   480	        # trouver la page d'un AUTRE utilisateur et la ranger dans notre
   481	        # carnet « Documents etalons » — une fuite de perimetre. On ne
   482	        # touche jamais a une note qui n'est pas a `proprietaire`.
   483	        # / Scoped to `proprietaire`: without it, a page belonging to a
   484	        # DIFFERENT user could get filed into our notebook — a scope
   485	        # leak. We never touch a note that is not the owner's.
   486	        page_deja_ailleurs = Page.objects.filter(
   487	            url=URL_DE_LA_CAPTURE, owner=proprietaire,
   488	        ).first()
   489	        if page_deja_ailleurs is not None:
   490	            ranger_une_note_dans_un_carnet(
   491	                page_deja_ailleurs, carnet_des_etalons, proprietaire,
   492	            )
   493	            self.stdout.write(
   494	                "Capture web         : déjà présente ailleurs — rangée ici",
   495	            )
   496	            return page_deja_ailleurs
   497	
   498	        # La page peut exister chez QUELQU'UN D'AUTRE : la contrainte
   499	        # d'unicite empecherait quand meme la creation. On le dit
   500	        # clairement et on passe, plutot que de laisser l'IntegrityError
   501	        # remonter en trace de pile. / The page may belong to someone
   502	        # else: the unique constraint would still block creation. Say so
   503	        # plainly and move on, instead of surfacing a raw IntegrityError.
   504	        if Page.objects.filter(url=URL_DE_LA_CAPTURE).exclude(
   505	            owner=proprietaire,
   506	        ).exists():
   507	            self.stdout.write(self.style.WARNING(
   508	                "Capture web         : une autre note porte déjà cette "
   509	                "url — capture web non chargée",
   510	            ))
   511	            return None
   512	
   513	        html_capture = (REPERTOIRE_SAMPLE / FICHIER_DE_LA_CAPTURE).read_text(
   514	            encoding="utf-8",
   515	        )
   516	
   517	        page_de_la_capture = Page.objects.create(
   518	            source_type="web",
   519	            original_filename=FICHIER_DE_LA_CAPTURE,
   520	            url=URL_DE_LA_CAPTURE,
   521	            title="Badgeons la Normandie",
   522	            html_original=html_capture,
   523	            html_readability=html_capture,
   524	            text_readability="",
   525	            content_hash=hashlib.sha256(
   526	                html_capture.encode("utf-8"),
   527	            ).hexdigest(),
   528	            status="completed",
   529	            owner=proprietaire,
   530	            dossier=carnet_des_etalons,
   531	        )
   532	        ranger_une_note_dans_un_carnet(
   533	            page_de_la_capture, carnet_des_etalons, proprietaire,
   534	        )
   535	
   536	        nombre_d_elements = self._ingerer_la_capture(page_de_la_capture)
   537	        self.stdout.write(
   538	            f"Capture web         : {nombre_d_elements} élément(s)",
   539	        )
   540	        return page_de_la_capture
   541	
   542	    def _ingerer_la_capture(self, page_de_la_capture):
   543	        """
   544	        Lance l'ingestion de la capture, en synchrone.
   545	        / Runs the capture's ingestion, synchronously.
   546	
   547	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   548	
   549	        ON PASSE PAR LA TACHE, PAS PAR LE SERVICE.
   550	
   551	        Le service nu cree les elements et s'arrete la. C'est la tache qui
   552	        ecrit `Page.ingestion_etat` (en_cours -> reussie/echouee) et qui
   553	        attrape l'echec avec un message lisible. L'ecran de lecture affiche
   554	        cet etat : une page ingeree par le service nu ment sur son statut.
   555	        `.apply()` l'execute ici meme, sans worker.
   556	        / The task writes ingestion_etat; the bare service does not.
   557	        """
   558	        from hypostasis_extractor.tasks_element import (
   559	            ingerer_une_capture_web_avec_docling,
   560	        )
   561	
   562	        resultat = ingerer_une_capture_web_avec_docling.apply(
   563	            args=[page_de_la_capture.pk],
   564	        )
   565	        return self._elements_du_resultat(resultat)
   566	
   567	    def _elements_du_resultat(self, resultat_de_la_tache):
   568	        """
   569	        Lit le nombre d'elements d'un resultat de tache, sans mentir.
   570	        / Reads a task result's element count, without lying.
   571	
   572	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   573	
   574	        Les taches rendent {"elements": N} ou {"erreur": "..."} — jamais
   575	        une exception pour un cas normal. Un mock de test rend un Mock :
   576	        on ne compte alors rien plutot que d'inventer un chiffre.
   577	        / Never invent a count: a mocked task has none to give.
   578	        """
   579	        valeur = getattr(resultat_de_la_tache, "result", None)
   580	        if not isinstance(valeur, dict):
   581	            return "?"
   582	        if "erreur" in valeur:
   583	            self.stdout.write(self.style.WARNING(
   584	                f"    ingestion en échec : {valeur['erreur']}",
   585	            ))
   586	            return 0
   587	        return valeur.get("elements", 0)
   588	
   589	    def _charger_le_markdown(self, proprietaire, carnet_des_etalons):
   590	        """
   591	        Cree la note issue du markdown, et l'ingere.
   592	        / Creates the note from the markdown file, and ingests it.
   593	
   594	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   595	
   596	        Le markdown passe bien par Docling, mais sans OCR ni modele de
   597	        layout : ceux-la ne se chargent que pour les PDF et les images.
   598	        C'est pourquoi cette fixture-ci est sure, la ou le PDF ne l'est pas.
   599	        / Markdown goes through Docling without OCR or layout models.
   600	        """
   601	        # Garde : --fichier peut avoir exclu ce document.
   602	        # / Guard: --fichier may have excluded this document.
   603	        if FICHIER_DU_MARKDOWN not in self.fichiers_demandes:
   604	            return None
   605	
   606	        if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MARKDOWN):
   607	            self.stdout.write("Markdown            : déjà présent — sauté")
   608	            return None
   609	
   610	        if self.a_blanc:
   611	            self.stdout.write("Markdown            : serait chargé")
   612	            return None
   613	
   614	        chemin_du_markdown = REPERTOIRE_SAMPLE / FICHIER_DU_MARKDOWN
   615	        contenu_du_markdown = chemin_du_markdown.read_text(encoding="utf-8")
   616	
   617	        page_du_markdown = Page.objects.create(
   618	            source_type="file",
   619	            original_filename=FICHIER_DU_MARKDOWN,
   620	            url=None,
   621	            title="Présentation Hypostasia V3",
   622	            html_original="",
   623	            html_readability="",
   624	            text_readability=contenu_du_markdown,
   625	            content_hash=hashlib.sha256(
   626	                contenu_du_markdown.encode("utf-8"),
   627	            ).hexdigest(),
   628	            status="completed",
   629	            owner=proprietaire,
   630	            dossier=carnet_des_etalons,
   631	            source_file=ContentFile(
   632	                contenu_du_markdown.encode("utf-8"),
   633	                name=FICHIER_DU_MARKDOWN,
   634	            ),
   635	        )
   636	        ranger_une_note_dans_un_carnet(
   637	            page_du_markdown, carnet_des_etalons, proprietaire,
   638	        )
   639	
   640	        from hypostasis_extractor.tasks_element import (
   641	            ingerer_un_fichier_avec_docling,
   642	        )
   643	
   644	        # On ne passe QUE la cle primaire : la tache resout le chemin
   645	        # depuis page.source_file, comme le fait la vue d'import.
   646	        # / Only the pk: the task resolves the path from source_file.
   647	        resultat = ingerer_un_fichier_avec_docling.apply(
   648	            args=[page_du_markdown.pk],
   649	        )
   650	        self.stdout.write(
   651	            f"Markdown            : {self._elements_du_resultat(resultat)} élément(s)",
   652	        )
   653	        return page_du_markdown
   654	
   655	    def _charger_la_transcription_json(self, proprietaire, carnet_des_etalons):
   656	        """
   657	        Cree la note issue de la transcription deja faite, et l'ingere.
   658	        / Creates the note from the ready-made transcript, and ingests it.
   659	
   660	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   661	
   662	        DOCLING N'INTERVIENT PAS : une transcription diarisee est deja
   663	        structuree. `ingerer_une_transcription_diarisee` la decoupe en
   664	        tours de parole sans charger le moindre modele.
   665	        / Docling plays no part: a diarised transcript is already structured.
   666	
   667	        ATTENTION — la vue d'import, elle, N'APPELLE PAS cette ingestion
   668	        (front/views.py:5326) : une note importee par cette porte reste
   669	        sans element, donc sans gouttiere et sans ancrage possible. C'est
   670	        un trou de l'application, releve le 11 aout 2026. La commande
   671	        appelle l'ingestion explicitement.
   672	        / The import view never triggers this ingestion; we do it here.
   673	        """
   674	        import json
   675	
   676	        # Garde : --fichier peut avoir exclu ce document.
   677	        # / Guard: --fichier may have excluded this document.
   678	        if FICHIER_DE_LA_TRANSCRIPTION not in self.fichiers_demandes:
   679	            return None
   680	
   681	        if self._note_deja_presente(
   682	            carnet_des_etalons, FICHIER_DE_LA_TRANSCRIPTION,
   683	        ):
   684	            self.stdout.write("Transcription JSON  : déjà présente — sautée")
   685	            return None
   686	
   687	        if self.a_blanc:
   688	            self.stdout.write("Transcription JSON  : serait chargée")
   689	            return None
   690	
   691	        from front.services.transcription_audio import construire_html_diarise
   692	
   693	        chemin_du_json = REPERTOIRE_SAMPLE / FICHIER_DE_LA_TRANSCRIPTION
   694	        contenu_brut = chemin_du_json.read_text(encoding="utf-8")
   695	        donnees_de_la_transcription = json.loads(contenu_brut)
   696	
   697	        html_diarise, texte_brut = construire_html_diarise(
   698	            donnees_de_la_transcription,
   699	        )
   700	
   701	        page_du_json = Page.objects.create(
   702	            source_type="audio",
   703	            original_filename=FICHIER_DE_LA_TRANSCRIPTION,
   704	            url=None,
   705	            title="Débat IA — transcription",
   706	            html_original="",
   707	            html_readability=html_diarise,
   708	            text_readability=texte_brut,
   709	            content_hash=hashlib.sha256(
   710	                texte_brut.encode("utf-8"),
   711	            ).hexdigest(),
   712	            transcription_raw=donnees_de_la_transcription,
   713	            status="completed",
   714	            owner=proprietaire,
   715	            dossier=carnet_des_etalons,
   716	            source_file=ContentFile(
   717	                contenu_brut.encode("utf-8"),
   718	                name=FICHIER_DE_LA_TRANSCRIPTION,
   719	            ),
   720	        )
   721	        ranger_une_note_dans_un_carnet(
   722	            page_du_json, carnet_des_etalons, proprietaire,
   723	        )
   724	
   725	        from hypostasis_extractor.tasks_element import (
   726	            ingerer_une_transcription_diarisee_en_elements,
   727	        )
   728	
   729	        resultat = ingerer_une_transcription_diarisee_en_elements.apply(
   730	            args=[page_du_json.pk],
   731	        )
   732	        self.stdout.write(
   733	            f"Transcription JSON  : {self._elements_du_resultat(resultat)} "
   734	            f"tour(s) de parole",
   735	        )
   736	        return page_du_json
   737	
   738	    def _charger_le_mp3(self, proprietaire, carnet_des_etalons):
   739	        """
   740	        Cree la note audio et lance la vraie transcription Voxtral.
   741	        / Creates the audio note and runs the real Voxtral transcription.
   742	
   743	        LOCALISATION : front/management/commands/charger_fixtures_sample.py
   744	
   745	        C'est la seule fixture qui eprouve la chaine COMPLETE : mp3 ->
   746	        Voxtral -> tours de parole -> elements. Un appel reseau reel, donc
   747	        aussi un test de bout en bout a chaque chargement.
   748	        / The only fixture exercising the full chain, network call included.
   749	
   750	        La tache enchaine elle-meme l'ingestion en elements, mais par
   751	        `.delay()` : sans worker, elle partirait dans le broker et ne se
   752	        ferait jamais. On la rejoue donc ici, en synchrone, si la page
   753	        n'a pas d'element. / The task chains via .delay(); we redo it sync.
   754	        """
   755	        # Garde : --fichier peut avoir exclu ce document.
   756	        # / Guard: --fichier may have excluded this document.
   757	        if FICHIER_DU_MP3 not in self.fichiers_demandes:
   758	            return None
   759	
   760	        if self.sans_mp3:
   761	            self.stdout.write("Audio mp3           : sauté (--sans-mp3)")
   762	            return None
   763	
   764	        if not os.environ.get("MISTRAL_API_KEY"):
   765	            self.stdout.write(self.style.WARNING(
   766	                "Audio mp3           : sauté — pas de MISTRAL_API_KEY. "
   767	                "La transcription serait mockée, pas réelle.",
   768	            ))
   769	            return None
   770	
   771	        if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MP3):
   772	            self.stdout.write("Audio mp3           : déjà présent — sauté")
   773	            return None
   774	
   775	        if self.a_blanc:
   776	            self.stdout.write("Audio mp3           : serait transcrit (Voxtral)")
   777	            return None
   778	
   779	        from core.models import (
   780	            PageStatus,
   781	            TranscriptionConfig,
   782	            TranscriptionJob,
   783	            TranscriptionJobStatus,
   784	        )
   785	
   786	        chemin_du_mp3 = REPERTOIRE_SAMPLE / FICHIER_DU_MP3
   787	        octets_du_mp3 = chemin_du_mp3.read_bytes()
   788	
   789	        page_du_mp3 = Page.objects.create(
   790	            source_type="audio",
   791	            original_filename=FICHIER_DU_MP3,
   792	            url=None,
   793	            title="Palais César — deux locuteurs",
   794	            html_original="",
   795	            html_readability="",
   796	            text_readability="",
   797	            content_hash="",
   798	            status="processing",
   799	            owner=proprietaire,
   800	            dossier=carnet_des_etalons,
   801	            source_file=ContentFile(octets_du_mp3, name=FICHIER_DU_MP3),
   802	        )
   803	        ranger_une_note_dans_un_carnet(
   804	            page_du_mp3, carnet_des_etalons, proprietaire,
   805	        )
   806	
   807	        config_active = TranscriptionConfig.objects.filter(
   808	            is_active=True,
   809	        ).first()
   810	        job_de_transcription = TranscriptionJob.objects.create(
   811	            page=page_du_mp3,
   812	            transcription_config=config_active,
   813	            audio_filename=FICHIER_DU_MP3,
   814	            status="pending",
   815	        )
   816	
   817	        from front.tasks import transcrire_audio_task
   818	
   819	        transcrire_audio_task.apply(args=[
   820	            job_de_transcription.pk,
   821	            page_du_mp3.source_file.path,
   822	            config_active.max_speakers if config_active else 5,
   823	            config_active.language if config_active else "fr",
   824	        ])
   825	
   826	        page_du_mp3.refresh_from_db()
   827	        job_de_transcription.refresh_from_db()
   828	
   829	        # `transcrire_audio_task` attrape ses propres exceptions et pose
   830	        # page.status/job.status = ERROR en silence (front/tasks.py
   831	        # ~711-726), sans jamais relever d'exception ici. Sans ce
   832	        # controle, le bilan afficherait "0 tour(s) de parole" —
   833	        # indiscernable d'une transcription reussie qui n'aurait rien
   834	        # trouve a dire. / The task silently marks page/job as ERROR on
   835	        # failure; without this check the report would lie by omission.
   836	        transcription_en_echec = (
   837	            page_du_mp3.status == PageStatus.ERROR
   838	            or job_de_transcription.status == TranscriptionJobStatus.ERROR
   839	        )
   840	        if transcription_en_echec:
   841	            message_d_erreur = (
   842	                job_de_transcription.error_message
   843	                or page_du_mp3.error_message
   844	                or "raison inconnue"
   845	            )
   846	            self.stdout.write(self.style.WARNING(
   847	                f"Audio mp3 (Voxtral) : ÉCHEC de la transcription — "
   848	                f"{message_d_erreur}",
   849	            ))
   850	            return page_du_mp3
   851	
   852	        # La tache enchaine l'ingestion par `.delay()`. Sans worker, elle
   853	        # n'a pas eu lieu : on la rejoue ici, en synchrone.
   854	        # / The task chained via .delay(); without a worker, redo it here.
   855	        if not page_du_mp3.elements.exists() and page_du_mp3.transcription_raw:
   856	            from hypostasis_extractor.tasks_element import (
   857	                ingerer_une_transcription_diarisee_en_elements,
   858	            )
   859	
   860	            ingerer_une_transcription_diarisee_en_elements.apply(
   861	                args=[page_du_mp3.pk],
   862	            )
   863	
   864	        self.stdout.write(
   865	            f"Audio mp3 (Voxtral) : {page_du_mp3.elements.count()} "
   866	            f"tour(s) de parole",
   867	        )
   868	        return page_du_mp3

## NEUF : front/tests/test_charger_fixtures_sample.py
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
   129	
   130	
   131	class DocumentsEcritsTest(TestCase):
   132	    """La capture web et le markdown, avec Docling mocké."""
   133	
   134	    def setUp(self):
   135	        self.chemin_du_module = (
   136	            "front.management.commands.charger_fixtures_sample"
   137	        )
   138	
   139	    def test_la_capture_web_devient_une_page(self):
   140	        with patch(
   141	            "hypostasis_extractor.tasks_element."
   142	            "ingerer_une_capture_web_avec_docling.apply",
   143	        ), patch(
   144	            "hypostasis_extractor.tasks_element."
   145	            "ingerer_un_fichier_avec_docling.apply",
   146	        ):
   147	            call_command(
   148	                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
   149	            )
   150	
   151	        page_de_la_capture = Page.objects.get(source_type="web")
   152	        self.assertTrue(page_de_la_capture.html_original)
   153	        self.assertEqual(
   154	            page_de_la_capture.original_filename,
   155	            "capture-web-badgeons-la-normandie.html",
   156	        )
   157	
   158	    def test_le_markdown_devient_une_page_avec_son_fichier(self):
   159	        with patch(
   160	            "hypostasis_extractor.tasks_element."
   161	            "ingerer_une_capture_web_avec_docling.apply",
   162	        ), patch(
   163	            "hypostasis_extractor.tasks_element."
   164	            "ingerer_un_fichier_avec_docling.apply",
   165	        ):
   166	            call_command(
   167	                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
   168	            )
   169	
   170	        page_du_markdown = Page.objects.get(
   171	            original_filename="PRESENTATION-V3.md",
   172	        )
   173	        self.assertEqual(page_du_markdown.source_type, "file")
   174	        # La tache resout le chemin depuis source_file : sans lui, elle
   175	        # rendrait {"erreur": "page sans fichier source"}.
   176	        # / The task resolves the path from source_file.
   177	        self.assertTrue(page_du_markdown.source_file)
   178	
   179	    def test_les_deux_notes_sont_rangees_dans_le_carnet(self):
   180	        with patch(
   181	            "hypostasis_extractor.tasks_element."
   182	            "ingerer_une_capture_web_avec_docling.apply",
   183	        ), patch(
   184	            "hypostasis_extractor.tasks_element."
   185	            "ingerer_un_fichier_avec_docling.apply",
   186	        ):
   187	            call_command(
   188	                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
   189	            )
   190	
   191	        carnet = Dossier.objects.get(name="Documents étalons")
   192	        # 3, pas 2 : --sans-mp3 ne saute que le mp3. La transcription JSON
   193	        # (tache 3) se charge toujours, meme ici ou son ingestion n'est
   194	        # pas mockee. / --sans-mp3 only skips the mp3; the JSON transcript
   195	        # (task 3) still loads, even with its ingestion unmocked here.
   196	        self.assertEqual(
   197	            Page.objects.filter(
   198	                appartenances_dossiers__dossier=carnet,
   199	            ).distinct().count(),
   200	            3,
   201	        )
   202	
   203	    def test_relancer_ne_double_rien_et_ne_reconvertit_pas(self):
   204	        cible_capture = (
   205	            "hypostasis_extractor.tasks_element."
   206	            "ingerer_une_capture_web_avec_docling.apply"
   207	        )
   208	        cible_fichier = (
   209	            "hypostasis_extractor.tasks_element."
   210	            "ingerer_un_fichier_avec_docling.apply"
   211	        )
   212	        with patch(cible_capture) as capture_mockee, \
   213	                patch(cible_fichier) as fichier_mocke:
   214	            call_command(
   215	                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
   216	            )
   217	            call_command(
   218	                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
   219	            )
   220	
   221	            # LE POINT DE CE TEST : la seconde execution ne doit PAS
   222	            # reconvertir. Le garde-fou du service arrive apres la
   223	            # conversion — s'y fier ferait payer Docling pour rien.
   224	            # / The second run must not re-convert.
   225	            self.assertEqual(capture_mockee.call_count, 1)
   226	            self.assertEqual(fichier_mocke.call_count, 1)
   227	
   228	        # 3, pas 2 : la transcription JSON (tache 3) se charge aussi, et
   229	        # son idempotence propre (_note_deja_presente) evite qu'elle soit
   230	        # doublee au second appel. / The JSON transcript (task 3) also
   231	        # loads, and its own idempotency check prevents duplication.
   232	        self.assertEqual(Page.objects.count(), 3)
   233	
   234	    def test_les_taches_sont_appelees_en_synchrone_avec_la_cle_primaire(self):
   235	        cible_capture = (
   236	            "hypostasis_extractor.tasks_element."
   237	            "ingerer_une_capture_web_avec_docling.apply"
   238	        )
   239	        with patch(cible_capture) as capture_mockee, patch(
   240	            "hypostasis_extractor.tasks_element."
   241	            "ingerer_un_fichier_avec_docling.apply",
   242	        ):
   243	            call_command(
   244	                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
   245	            )
   246	
   247	        page_de_la_capture = Page.objects.get(source_type="web")
   248	        capture_mockee.assert_called_once_with(
   249	            args=[page_de_la_capture.pk],
   250	        )
   251	
   252	
   253	class EntreesAudioTest(TestCase):
   254	    """La transcription déjà faite, et la chaîne mp3 complète."""
   255	
   256	    def _mocks_docling(self):
   257	        """Les deux tâches Docling, neutralisées ensemble."""
   258	        return (
   259	            patch(
   260	                "hypostasis_extractor.tasks_element."
   261	                "ingerer_une_capture_web_avec_docling.apply",
   262	            ),
   263	            patch(
   264	                "hypostasis_extractor.tasks_element."
   265	                "ingerer_un_fichier_avec_docling.apply",
   266	            ),
   267	        )
   268	
   269	    def test_le_json_devient_une_page_audio_avec_ses_elements(self):
   270	        capture_mockee, fichier_mocke = self._mocks_docling()
   271	        cible_ingestion = (
   272	            "hypostasis_extractor.tasks_element."
   273	            "ingerer_une_transcription_diarisee_en_elements.apply"
   274	        )
   275	        with capture_mockee, fichier_mocke, patch(cible_ingestion) as ingestion:
   276	            call_command(
   277	                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
   278	            )
   279	
   280	        page_du_json = Page.objects.get(
   281	            original_filename="fake_debat_ia_transcription.json",
   282	        )
   283	        self.assertEqual(page_du_json.source_type, "audio")
   284	        # 12 segments, 3 locuteurs — mesure du fichier versionne.
   285	        # / 12 segments, 3 speakers, measured from the versioned file.
   286	        self.assertEqual(len(page_du_json.transcription_raw["segments"]), 12)
   287	        # LE POINT : la vue d'import, elle, N'appelle PAS cette ingestion
   288	        # (front/views.py:5326). Une note importee par cette porte reste
   289	        # sans element. La commande, elle, doit l'appeler.
   290	        # / The import view never calls this; the command must.
   291	        ingestion.assert_called_once_with(args=[page_du_json.pk])
   292	
   293	    def test_sans_mp3_la_transcription_voxtral_n_est_pas_lancee(self):
   294	        capture_mockee, fichier_mocke = self._mocks_docling()
   295	        cible_voxtral = "front.tasks.transcrire_audio_task.apply"
   296	        with capture_mockee, fichier_mocke, patch(
   297	            "hypostasis_extractor.tasks_element."
   298	            "ingerer_une_transcription_diarisee_en_elements.apply",
   299	        ), patch(cible_voxtral) as voxtral_mocke:
   300	            call_command(
   301	                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
   302	            )
   303	
   304	        voxtral_mocke.assert_not_called()
   305	        self.assertFalse(
   306	            Page.objects.filter(
   307	                original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
   308	            ).exists(),
   309	        )
   310	
   311	    def test_sans_cle_mistral_le_mp3_est_saute_et_le_reste_charge(self):
   312	        import os
   313	
   314	        capture_mockee, fichier_mocke = self._mocks_docling()
   315	        sortie = StringIO()
   316	        cle_sauvegardee = os.environ.pop("MISTRAL_API_KEY", None)
   317	        try:
   318	            with capture_mockee, fichier_mocke, patch(
   319	                "hypostasis_extractor.tasks_element."
   320	                "ingerer_une_transcription_diarisee_en_elements.apply",
   321	            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
   322	                call_command("charger_fixtures_sample", stdout=sortie)
   323	        finally:
   324	            if cle_sauvegardee is not None:
   325	                os.environ["MISTRAL_API_KEY"] = cle_sauvegardee
   326	
   327	        voxtral.assert_not_called()
   328	        self.assertIn("MISTRAL_API_KEY", sortie.getvalue())
   329	        # Les trois autres notes sont chargees malgre tout.
   330	        # / The other three notes are loaded regardless.
   331	        self.assertEqual(Page.objects.count(), 3)
   332	
   333	    def test_avec_la_cle_le_mp3_cree_une_page_et_un_job(self):
   334	        import os
   335	
   336	        capture_mockee, fichier_mocke = self._mocks_docling()
   337	        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
   338	            with capture_mockee, fichier_mocke, patch(
   339	                "hypostasis_extractor.tasks_element."
   340	                "ingerer_une_transcription_diarisee_en_elements.apply",
   341	            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
   342	                call_command("charger_fixtures_sample", stdout=StringIO())
   343	
   344	        from core.models import TranscriptionJob
   345	
   346	        page_du_mp3 = Page.objects.get(
   347	            original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
   348	        )
   349	        job = TranscriptionJob.objects.get(page=page_du_mp3)
   350	        self.assertEqual(job.transcription_config.provider, "voxtral")
   351	        voxtral.assert_called_once()
   352	
   353	    def test_echec_voxtral_est_signale_dans_le_bilan(self):
   354	        # LE POINT : `transcrire_audio_task` attrape ses propres
   355	        # exceptions et pose page.status/job.status = ERROR en silence
   356	        # (front/tasks.py ~711-726). Sans controle explicite, le bilan
   357	        # affiche "0 tour(s) de parole" — indiscernable d'un succes sans
   358	        # contenu. On simule cet echec en posant les statuts d'erreur
   359	        # nous-memes, comme le ferait la tache reelle en cas de panne
   360	        # reseau. / The task swallows its own exceptions and silently
   361	        # marks page/job as ERROR; the report must say so explicitly.
   362	        import os
   363	
   364	        from core.models import PageStatus, TranscriptionJob, TranscriptionJobStatus
   365	
   366	        capture_mockee, fichier_mocke = self._mocks_docling()
   367	
   368	        def simuler_echec_reseau_voxtral(args=None, **kwargs):
   369	            job_de_test = TranscriptionJob.objects.get(pk=args[0])
   370	            job_de_test.status = TranscriptionJobStatus.ERROR
   371	            job_de_test.error_message = "Erreur réseau Voxtral (simulée)"
   372	            job_de_test.save(update_fields=["status", "error_message"])
   373	
   374	            page_de_test = job_de_test.page
   375	            page_de_test.status = PageStatus.ERROR
   376	            page_de_test.error_message = "Erreur réseau Voxtral (simulée)"
   377	            page_de_test.save(update_fields=["status", "error_message"])
   378	
   379	        sortie = StringIO()
   380	        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
   381	            with capture_mockee, fichier_mocke, patch(
   382	                "hypostasis_extractor.tasks_element."
   383	                "ingerer_une_transcription_diarisee_en_elements.apply",
   384	            ), patch(
   385	                "front.tasks.transcrire_audio_task.apply",
   386	                side_effect=simuler_echec_reseau_voxtral,
   387	            ):
   388	                call_command("charger_fixtures_sample", stdout=sortie)
   389	
   390	        self.assertIn("ÉCHEC", sortie.getvalue())
   391	        self.assertIn("Erreur réseau Voxtral (simulée)", sortie.getvalue())
   392	
   393	
   394	class RefusDesFormatsLourdsTest(TestCase):
   395	    """Le PDF et le docx ne passent pas par cette porte."""
   396	
   397	    def test_un_pdf_est_refuse_sans_conversion(self):
   398	        from django.core.management.base import CommandError
   399	
   400	        cible_fichier = (
   401	            "hypostasis_extractor.tasks_element."
   402	            "ingerer_un_fichier_avec_docling.apply"
   403	        )
   404	        with patch(cible_fichier) as fichier_mocke:
   405	            with self.assertRaises(CommandError) as contexte:
   406	                call_command(
   407	                    "charger_fixtures_sample",
   408	                    "--fichier", "sample/Etude_Epistemologique_IA.pdf",
   409	                    stdout=StringIO(),
   410	                )
   411	
   412	        # Le message doit ORIENTER, pas seulement refuser.
   413	        # / The message must point somewhere, not merely refuse.
   414	        self.assertIn(".pdf", str(contexte.exception))
   415	        fichier_mocke.assert_not_called()
   416	
   417	    def test_un_docx_est_refuse_aussi(self):
   418	        from django.core.management.base import CommandError
   419	
   420	        with self.assertRaises(CommandError):
   421	            call_command(
   422	                "charger_fixtures_sample",
   423	                "--fichier", "sample/quelque-chose.docx",
   424	                stdout=StringIO(),
   425	            )
   426	
   427	    def test_fichier_restreint_le_chargement_a_ce_seul_document(self):
   428	        cible_capture = (
   429	            "hypostasis_extractor.tasks_element."
   430	            "ingerer_une_capture_web_avec_docling.apply"
   431	        )
   432	        cible_fichier = (
   433	            "hypostasis_extractor.tasks_element."
   434	            "ingerer_un_fichier_avec_docling.apply"
   435	        )
   436	        with patch(cible_capture) as capture_mockee, patch(cible_fichier):
   437	            call_command(
   438	                "charger_fixtures_sample",
   439	                "--fichier", "PRESENTATION-V3.md",
   440	                stdout=StringIO(),
   441	            )
   442	
   443	        self.assertEqual(Page.objects.count(), 1)
   444	        self.assertEqual(
   445	            Page.objects.first().original_filename, "PRESENTATION-V3.md",
   446	        )
   447	        capture_mockee.assert_not_called()
   448	
   449	    def test_un_fichier_inconnu_est_refuse_clairement(self):
   450	        from django.core.management.base import CommandError
   451	
   452	        with self.assertRaises(CommandError) as contexte:
   453	            call_command(
   454	                "charger_fixtures_sample",
   455	                "--fichier", "n-existe-pas.md",
   456	                stdout=StringIO(),
   457	            )
   458	
   459	        self.assertIn("n-existe-pas.md", str(contexte.exception))
   460	
   461	    def test_fichier_est_repetable_et_charge_les_deux(self):
   462	        # LE POINT : `--fichier` repete deux fois doit charger les DEUX
   463	        # documents demandes, et rien d'autre — pas seulement le dernier
   464	        # de la liste. / --fichier repeated twice must load BOTH requested
   465	        # documents, and nothing else — not just the last one.
   466	        cible_capture = (
   467	            "hypostasis_extractor.tasks_element."
   468	            "ingerer_une_capture_web_avec_docling.apply"
   469	        )
   470	        cible_fichier = (
   471	            "hypostasis_extractor.tasks_element."
   472	            "ingerer_un_fichier_avec_docling.apply"
   473	        )
   474	        with patch(cible_capture), patch(cible_fichier):
   475	            call_command(
   476	                "charger_fixtures_sample",
   477	                "--fichier", "capture-web-badgeons-la-normandie.html",
   478	                "--fichier", "PRESENTATION-V3.md",
   479	                stdout=StringIO(),
   480	            )
   481	
   482	        noms_de_fichiers_charges = set(
   483	            Page.objects.values_list("original_filename", flat=True),
   484	        )
   485	        self.assertEqual(
   486	            noms_de_fichiers_charges,
   487	            {
   488	                "capture-web-badgeons-la-normandie.html",
   489	                "PRESENTATION-V3.md",
   490	            },
   491	        )
   492	        self.assertEqual(Page.objects.count(), 2)
   493	
   494	
   495	class ReinitialisationTest(TestCase):
   496	    """--reset rejoue tout, sauf s'il y a des preuves à perdre."""
   497	
   498	    def _charger_une_fois(self):
   499	        cible_capture = (
   500	            "hypostasis_extractor.tasks_element."
   501	            "ingerer_une_capture_web_avec_docling.apply"
   502	        )
   503	        cible_fichier = (
   504	            "hypostasis_extractor.tasks_element."
   505	            "ingerer_un_fichier_avec_docling.apply"
   506	        )
   507	        cible_audio = (
   508	            "hypostasis_extractor.tasks_element."
   509	            "ingerer_une_transcription_diarisee_en_elements.apply"
   510	        )
   511	        with patch(cible_capture), patch(cible_fichier), patch(cible_audio):
   512	            call_command(
   513	                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
   514	            )
   515	
   516	    def test_reset_supprime_les_notes_et_les_recharge(self):
   517	        self._charger_une_fois()
   518	        pks_de_depart = set(Page.objects.values_list("pk", flat=True))
   519	        self.assertEqual(len(pks_de_depart), 3)
   520	
   521	        cible_capture = (
   522	            "hypostasis_extractor.tasks_element."
   523	            "ingerer_une_capture_web_avec_docling.apply"
   524	        )
   525	        with patch(cible_capture) as capture_mockee, patch(
   526	            "hypostasis_extractor.tasks_element."
   527	            "ingerer_un_fichier_avec_docling.apply",
   528	        ), patch(
   529	            "hypostasis_extractor.tasks_element."
   530	            "ingerer_une_transcription_diarisee_en_elements.apply",
   531	        ):
   532	            call_command(
   533	                "charger_fixtures_sample", "--reset", "--sans-mp3",
   534	                stdout=StringIO(),
   535	            )
   536	            # Le point du reset : on RECONVERTIT, la ou l'idempotence
   537	            # aurait saute. / The point of --reset: convert again.
   538	            self.assertEqual(capture_mockee.call_count, 1)
   539	
   540	        self.assertEqual(Page.objects.count(), 3)
   541	        self.assertFalse(
   542	            set(Page.objects.values_list("pk", flat=True)) & pks_de_depart,
   543	        )
   544	
   545	    def test_reset_refuse_si_une_note_porte_une_ancre(self):
   546	        from django.core.management.base import CommandError
   547	
   548	        # Ces trois modeles vivent dans hypostasis_extractor, PAS dans
   549	        # core.models. / These three live in hypostasis_extractor.
   550	        from hypostasis_extractor.models import (
   551	            AncrageExtraction, ExtractedEntity, ExtractionJob,
   552	        )
   553	
   554	        self._charger_une_fois()
   555	        page_avec_ancre = Page.objects.filter(source_type="web").first()
   556	        element = page_avec_ancre.elements.create(
   557	            ordre=0, label="text", texte="un passage", empreinte_contenu="x",
   558	        )
   559	        job = ExtractionJob.objects.create(
   560	            page=page_avec_ancre, name="job de test",
   561	            prompt_description="peu importe", status="completed",
   562	        )
   563	        entite = ExtractedEntity.objects.create(
   564	            job=job, extraction_class="PHENOMENE", extraction_text="une idée",
   565	            start_char=0, end_char=10,
   566	        )
   567	        # Les champs sont debut_dans_element / fin_dans_element — des
   568	        # positions DANS l'element, jamais dans le texte global de la
   569	        # page. / Positions within the element, never page-global.
   570	        AncrageExtraction.objects.create(
   571	            extraction=entite, element=element,
   572	            ordre_dans_extraction=0,
   573	            debut_dans_element=0, fin_dans_element=10,
   574	        )
   575	
   576	        nombre_de_pages_avant = Page.objects.count()
   577	        with self.assertRaises(CommandError) as contexte:
   578	            call_command(
   579	                "charger_fixtures_sample", "--reset", "--sans-mp3",
   580	                stdout=StringIO(),
   581	            )
   582	
   583	        # RIEN ne doit avoir ete supprime — pas de suppression partielle
   584	        # qui laisserait le carnet a moitie vide.
   585	        # / Nothing deleted: no half-emptied notebook.
   586	        self.assertEqual(Page.objects.count(), nombre_de_pages_avant)
   587	        self.assertIn(page_avec_ancre.title, str(contexte.exception))
   588	
   589	    def test_reset_ne_touche_pas_une_note_rangee_ailleurs(self):
   590	        from core.models import Dossier as CarnetModele
   591	        from core.services.corpus import ranger_une_note_dans_un_carnet
   592	
   593	        self._charger_une_fois()
   594	        page_partagee = Page.objects.filter(source_type="web").first()
   595	        proprietaire = page_partagee.owner
   596	        autre_carnet = CarnetModele.objects.create(
   597	            name="Un autre carnet", owner=proprietaire,
   598	        )
   599	        ranger_une_note_dans_un_carnet(page_partagee, autre_carnet, proprietaire)
   600	
   601	        with patch(
   602	            "hypostasis_extractor.tasks_element."
   603	            "ingerer_une_capture_web_avec_docling.apply",
   604	        ), patch(
   605	            "hypostasis_extractor.tasks_element."
   606	            "ingerer_un_fichier_avec_docling.apply",
   607	        ), patch(
   608	            "hypostasis_extractor.tasks_element."
   609	            "ingerer_une_transcription_diarisee_en_elements.apply",
   610	        ):
   611	            call_command(
   612	                "charger_fixtures_sample", "--reset", "--sans-mp3",
   613	                stdout=StringIO(),
   614	            )
   615	
   616	        # Elle vit ailleurs : on ne l'emporte pas.
   617	        # / It lives elsewhere: not ours to delete.
   618	        self.assertTrue(Page.objects.filter(pk=page_partagee.pk).exists())
   619	
   620	    def test_a_blanc_reset_ne_supprime_rien(self):
   621	        # La verification des ancres tourne AVANT le `if self.a_blanc:
   622	        # return None` de `_reinitialiser` : rien ne doit disparaitre,
   623	        # meme sans ancre a proteger. / The anchor check runs before the
   624	        # dry-run early return: nothing should vanish, anchors or not.
   625	        self._charger_une_fois()
   626	        nombre_de_pages_avant = Page.objects.count()
   627	        carnet_avant = Dossier.objects.get(name="Documents étalons")
   628	
   629	        call_command(
   630	            "charger_fixtures_sample", "--a-blanc", "--reset", "--sans-mp3",
   631	            stdout=StringIO(),
   632	        )
   633	
   634	        self.assertEqual(Page.objects.count(), nombre_de_pages_avant)
   635	        self.assertTrue(
   636	            Dossier.objects.filter(pk=carnet_avant.pk).exists(),
   637	        )

## MODIFIE : hypostasis_extractor/tests/test_fixtures_representatives.py
diff --git a/hypostasis_extractor/tests/test_fixtures_representatives.py b/hypostasis_extractor/tests/test_fixtures_representatives.py
index 6b09984..1c97b93 100644
--- a/hypostasis_extractor/tests/test_fixtures_representatives.py
+++ b/hypostasis_extractor/tests/test_fixtures_representatives.py
@@ -193,10 +193,99 @@ class ConversionReelleDUnDocxAvecTableauTest(BaseFixturesTestCase):
         )
 
         element_tableau = next(
             e for e in elements if e.label == "table"
         )
         # Le contenu des cellules est dans le texte de l'element : les
         # extractions pourront s'y ancrer. / Cell content is anchorable.
         self.assertIn("6 500 euros", element_tableau.texte,
         )
         self.assertIn("Formations", element_tableau.texte)
+
+
+@tag("docling")
+@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
+class CaptureWebEtalonTest(TestCase):
+    """
+    Le contrôle de non-régression de l'extraction HTML.
+    / The HTML extraction's non-regression control.
+
+    LOCALISATION : hypostasis_extractor/tests/test_fixtures_representatives.py
+
+    Ce compte VERROUILLE les deux correctifs du 11 août 2026 :
+
+    - une image n'est pas un tableau : sans légende elle ne produit
+      aucun bloc, au lieu du message « Image not available… » destiné au
+      développeur ;
+    - un gras ne coupe pas une phrase : les fragments d'un même groupe
+      inline se recollent, au lieu de produire deux blocs là où l'auteur
+      a écrit une phrase.
+
+    54 éléments dont un `picture` = retour à la version d'avant les
+    correctifs. Une cinquantaine de blocs tous en `text` = retour du
+    découpage maison par paragraphes.
+    / This count locks in the two 11 August fixes.
+    """
+
+    def test_la_capture_web_rend_vingt_huit_elements(self):
+        from io import StringIO
+
+        from django.core.management import call_command
+
+        from core.models import ElementDocument, Page
+
+        # Ne charge QUE la capture web : les trois autres documents
+        # etalons (markdown, transcription, mp3) ne nous concernent pas
+        # ici et gonfleraient le temps du test. / Only the web capture.
+        call_command(
+            "charger_fixtures_sample",
+            "--fichier", "capture-web-badgeons-la-normandie.html",
+            stdout=StringIO(),
+        )
+
+        page_de_la_capture = Page.objects.get(source_type="web")
+        elements = ElementDocument.objects.filter(page=page_de_la_capture)
+
+        self.assertEqual(elements.count(), 28)
+
+        # Ventilation par label : le compte total seul ne suffirait pas
+        # a distinguer un retour du bug d'une coincidence numerique.
+        # / Per-label breakdown: the total alone could hide a regression.
+        comptes_par_label = {}
+        for element in elements:
+            comptes_par_label[element.label] = (
+                comptes_par_label.get(element.label, 0) + 1
+            )
+
+        self.assertEqual(
+            comptes_par_label,
+            {"section_header": 4, "list_item": 5, "text": 19},
+        )
+
+    def test_la_page_ingeree_porte_l_etat_reussie(self):
+        """
+        L'état d'ingestion ne peut se tester qu'ici.
+        / The ingestion state can only be tested here.
+
+        Avec Docling mocké, la tâche ne tourne pas, donc n'écrit pas
+        `ingestion_etat` : un test rapide qui l'affirmerait ne
+        vérifierait que son propre mock. C'est justement l'écart que
+        `charger_fixtures_llm_reel` a laissé passer — ses pages
+        gardent un état vide alors que l'écran de lecture l'affiche.
+        / A mocked task writes no state; asserting it would test the mock.
+        """
+        from io import StringIO
+
+        from django.core.management import call_command
+
+        from core.models import EtatIngestion, Page
+
+        call_command(
+            "charger_fixtures_sample",
+            "--fichier", "capture-web-badgeons-la-normandie.html",
+            stdout=StringIO(),
+        )
+
+        page_de_la_capture = Page.objects.get(source_type="web")
+        self.assertEqual(
+            page_de_la_capture.ingestion_etat, EtatIngestion.REUSSIE,
+        )
