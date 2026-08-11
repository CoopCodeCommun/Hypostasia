# SDD ledger — plan: docs/superpowers/plans/2026-08-11-charger-fixtures-sample.md

Adaptation aux regles du depot : AUCUNE operation git (pas de worktree,
pas de commit). Les diffs de revue sont produits par snapshots de fichiers
dans $W/snapshots/, compares avec diff -u.

Task 1: complete (fichiers charger_fixtures_sample.py + test_charger_fixtures_sample.py, 7 tests OK, revue propre)
Task 1: minor (deferred): create_user puis set_password+save = un INSERT puis un UPDATE (commande:117-121). Herite du brief.
Task 1: minor (deferred): commentaires bilingues sur les docstrings mais pas sur chaque bloc interne. Herite du brief.
Task 2: complete (capture web 28 elements CONFORME, markdown 549 elements, 12 tests OK, revue propre)
Task 2: minor (deferred): _charger_le_markdown lit le fichier en texte puis re-encode en bytes pour ContentFile (commande:335-355).
Task 2: minor (deferred): le retour '?' de _elements_du_resultat n'est verifie que par lecture, pas par test.
Task 3: revue — conformite OK, 1 Important (bilan mp3 muet sur echec Voxtral), 2 mineurs differes
Task 3: minor (deferred): rattrapage d'ingestion non atomique (pas de select_for_update) — course theorique avec un worker Celery vivant.
Task 3: minor (deferred): aucun test ne combine --a-blanc avec MISTRAL_API_KEY presente sur le chemin mp3.
Task 3: fix round 1/5 en cours — bilan d'echec Voxtral + test de couverture
Task 3: fix round 1/5 (1 adresse, 0 ouvert — bilan d'echec Voxtral + test dedie, 17 tests OK)
Task 3: complete (JSON 12 tours {Laurent,Elinor,Eric}, mp3 Voxtral reel 9 tours {speaker_1,speaker_2}, 17 tests OK)
Task 3: minor (deferred): TranscriptionJob cree avec status='pending' en dur au lieu de TranscriptionJobStatus.PENDING.
Task 4: fix round 1/5 (3 adresses, 0 ouvert — chiffres sources, message honnete, test de repetabilite; 22 tests OK)
Task 4: complete (refus PDF/docx immediat en 2,16 s sans conversion, --fichier repetable, 22 tests OK)
Task 4: minor (deferred): 'Gio' employe au sens decimal de Go dans les commentaires (preexistant).
DECISION 11 aout : brancher les 3 taches d'ingestion au moteur de notification, SANS nouveau modele
  (via Page.ingestion_etat + un marqueur 'lu'), ET corriger les destinataires de l'analyse et de la
  transcription pour qu'ils utilisent _destinataires_de_notification. => tache 7, apres la tache 6.
Task 5: fix round 1/5 (3 adresses, 0 ouvert — scope owner, docstring, test a-blanc+reset; 26 tests OK)
Task 5: complete (--reset avec garde-fou PROTECT verifie AVANT suppression, 26 tests OK)
Task 5: minor (deferred): pas de test dedie pour la branche 'url detenue par un autre owner'.
Task 6: complete (28 elements confirmes en test reel, tests bien sautes sans TESTS_DOCLING=1, revue propre)

REVUE FINALE (opus) : 1 Critique + 4 Important + mineurs -> UNE vague de correction -> re-revue : 6/6 ADRESSES.
Verification finale reelle : 4 notes, 598 elements, toutes en ingestion_etat='reussie'.
  capture web 28 | markdown 549 | transcription JSON 12 | mp3 Voxtral 9. Relance : 4 sautees, 0 doublon.
  Suite complete : Ran 43 tests, OK (skipped=4 docling).

PARKED (residuels de la re-revue, non bloquants — arbitrage Jonas) :
  parked 1: _creer_la_config_de_transcription rend None en --a-blanc -> 'Voxtral Mini (serait creee)'
    alors que la ligne du dessus dit 'reutilisee'. Affichage seul. Meme travers que le defaut 4 corrige.
  parked 2: une transcription Voxtral ECHOUEE laisse une page sans element ; chaque relance la supprime
    et RELANCE un appel Voxtral facture. Coherent avec le defaut 3, mais contredit le docstring de --reset
    ('la seule facon de rejouer l'appel Voxtral'). ARBITRAGE PRODUIT.
  parked 3: Page.delete() ne supprime pas source_file du disque -> un media orphelin par rechargement.

Task 7-8 (notifications) : planifiees dans l'addendum du plan, non commencees.

Task 7: complete (9 points d'appel + destinataires corriges ; fix round 1/5 : try/except + filtre None ; 679 tests OK)
Task 8: en cours — migrations 0057 (champ) + 0058 (estampillage, 4 pages) CREEES ET APPLIQUEES a la base de dev.
  INCIDENT 11 aout : j'avais interdit la migration a l'agent alors que son code lisait deja la colonne.
  -> le serveur de dev est tombe en ProgrammingError sous les yeux du mainteneur. Migration appliquee, repare.
  LECON : une migration doit etre appliquee a la base de dev des que le code la reference (serveur permanent).

DECISIONS Jonas (11 aout, seconde moitie de session) :
  - suppression d'une note : retrait du carnet si on n'est pas owner ; suppression reelle reservee a l'owner ;
    confirmation seulement quand c'est destructif et non evident. Note orpheline acceptee.
  - Page.delete() doit supprimer le media -> signal post_delete.
  - echec Voxtral : supprimer la page vide, GARDER le TranscriptionJob (CASCADE -> SET_NULL) pour la raison.
  - confirmation conditionnelle : tout en une passe, JS + collectstatic + bump ?v=.
  - PDF charge PAR DEFAUT (renverse le § 3.5 de la spec) ; docx toujours refuse (0 element).
  - carnet 'Documents etalons' range dans une BaseDeConnaissances 'Demonstration'.

PLANS ECRITS : docs/superpowers/plans/2026-08-11-suppression-et-echec-voxtral.md (4 taches)
               + addendum n2 au plan des fixtures (tache 9 : PDF + base de demonstration)
Task 8: fix round 1/5 (2 volets adresses — reamorcage du drapeau + migration 0058 restreinte ; 8 tests OK)
Task 8: complete (ingestions dans le bouton et le dropdown, 2 chemins de marquage lu, tri sur ingestion_maj_le)
Task 8: corrige par le controleur : artefact d'encodage cyrillique 'reармer' -> 'rearme' (tasks_element.py:244).
  Scan global : aucun autre caractere cyrillique/grec dans le code de la session.
CONSTAT : PLAYWRIGHT_BROWSERS_PATH n'est pas definie dans le conteneur -> les 21 tests e2e n'ont
  JAMAIS tourne de la session (21 ERROR setUpClass, prealables et sans lien avec le travail fait).
Task 9: complete (PDF charge par defaut, 11 elements dont 2 tables, 11/11 boites ; base 'Demonstration' creee)
  VERIFIE EN BASE : 11 elements avec page_no (etait 0 — le trou central de la passation est comble).
  49 tests OK. Spec amendee par addendum date, § 3.5 non reecrit.
Task 9: minor (deferred): l'addendum se numerote n2 sans qu'un n1 existe dans ce fichier.
Task 9: minor (deferred): le commentaire du compteur 'Notes sautees' ne mentionne pas le PDF.

PRIORITE MONTANTE : coord_origin est desormais FIGE EN BASE ('CoordOrigin.BOTTOMLEFT' au lieu de
  'BOTTOMLEFT'). Tant qu'il n'etait que dans le code, c'etait un detail ; maintenant il est dans la
  donnee, et toute fixture etalon JSON produite le transporterait.
coord_origin: complete (service corrige + commande de reparation robuste, 10 tests OK)
  fix round 1 : boite non-dict, boites non-liste, boite muette -> comptees a part
  fix round 2 : provenance elle-meme non-dict (le meme defaut un niveau au-dessus)
  BASE REPAREE : 11 boites, coord_origin = 'BOTTOMLEFT' (etait 'CoordOrigin.BOTTOMLEFT')

VERIFICATION FINALE DE SESSION : 97 tests, OK (skipped=7 docling), une seule invocation.

=== CLOTURE DE SESSION — 11 aout 2026 ===
Revue de cloture (opus, apres echec de Fable pour limite de credits) : 3 defauts GRAVES d'interaction,
  tous corriges + revue : reception des notifications elargie, borne de temps sur le badge, horodatage.
Puis : drapeau de lecture PAR DESTINATAIRE (modele NotificationTacheLue + 4 migrations), 2 Important corriges.
Puis : second PDF (open badges) ajoute aux etalons — 61 elements, 61/61 boites.
ENFIN — defaut trouve par verification manuelle de la base, PAS par les tests :
  une page portait 9 elements ET l'etat 'echouee'. Cause : la course 'theorique' signalee comme mineure
  a la tache 3 s'est PRODUITE (logs worker, 77 ms d'ecart). Le vrai defaut n'etait pas la course mais le
  fait qu'une seconde execution constatant 'page deja ingeree' posait ECHOUEE — alors que la garde
  d'entree de la MEME fonction posait REUSSIE. Les TROIS taches d'ingestion avaient ce defaut.
  Corrige par un filet partage. 1 page reparee. 0 page incoherente restante.

ETAT FINAL : 6 notes, 670 elements, 72 avec coordonnees, 0 incoherence. 1597 tests (21 e2e Playwright
  en echec, prealables et d'infrastructure). Site debout. RIEN COMMITE.
