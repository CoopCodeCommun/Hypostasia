## Tâche 4 : `--fichier`, et le refus du PDF et du docx

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`

**Interfaces :**
- Consomme : tout ce qui précède.
- Produit : l'option `--fichier`, répétable, et
  `EXTENSIONS_REFUSEES = {".pdf", ".docx"}`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
class RefusDesFormatsLourdsTest(TestCase):
    """Le PDF et le docx ne passent pas par cette porte."""

    def test_un_pdf_est_refuse_sans_conversion(self):
        from django.core.management.base import CommandError

        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_fichier) as fichier_mocke:
            with self.assertRaises(CommandError) as contexte:
                call_command(
                    "charger_fixtures_sample",
                    "--fichier", "sample/Etude_Epistemologique_IA.pdf",
                    stdout=StringIO(),
                )

        # Le message doit ORIENTER, pas seulement refuser.
        # / The message must point somewhere, not merely refuse.
        self.assertIn(".pdf", str(contexte.exception))
        fichier_mocke.assert_not_called()

    def test_un_docx_est_refuse_aussi(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "charger_fixtures_sample",
                "--fichier", "sample/quelque-chose.docx",
                stdout=StringIO(),
            )

    def test_fichier_restreint_le_chargement_a_ce_seul_document(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, patch(cible_fichier):
            call_command(
                "charger_fixtures_sample",
                "--fichier", "PRESENTATION-V3.md",
                stdout=StringIO(),
            )

        self.assertEqual(Page.objects.count(), 1)
        self.assertEqual(
            Page.objects.first().original_filename, "PRESENTATION-V3.md",
        )
        capture_mockee.assert_not_called()

    def test_un_fichier_inconnu_est_refuse_clairement(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as contexte:
            call_command(
                "charger_fixtures_sample",
                "--fichier", "n-existe-pas.md",
                stdout=StringIO(),
            )

        self.assertIn("n-existe-pas.md", str(contexte.exception))
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample.RefusDesFormatsLourdsTest \
    --noinput --settings=hypostasia.settings_test_opus
```

Attendu : erreur sur `--fichier` inconnu.

- [ ] **Étape 3 : écrire l'option et le refus**

```python
# En tete de fichier
EXTENSIONS_REFUSEES = {".pdf", ".docx"}

# Les quatre documents etalons, par nom de fichier, dans l'ordre de
# chargement. `--fichier` restreint a un sous-ensemble de cette table.
# / The four reference documents, in loading order.
DOCUMENTS_ETALONS = [
    FICHIER_DE_LA_CAPTURE,
    FICHIER_DU_MARKDOWN,
    FICHIER_DE_LA_TRANSCRIPTION,
    FICHIER_DU_MP3,
]
```

```python
    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--a-blanc", action="store_true",
            help="Affiche ce qui serait fait, sans rien ecrire.",
        )
        analyseur_d_arguments.add_argument(
            "--sans-mp3", action="store_true",
            help="Saute la transcription Voxtral du fichier audio.",
        )
        analyseur_d_arguments.add_argument(
            "--fichier", action="append", default=None, dest="fichiers",
            help=(
                "Ne charger que ce fichier de sample/, au lieu des quatre. "
                "Repetable."
            ),
        )
```

Dans `handle`, avant toute écriture :

```python
        self.fichiers_demandes = self._resoudre_les_fichiers_demandes(
            options["fichiers"],
        )
```

```python
    def _resoudre_les_fichiers_demandes(self, fichiers_de_l_option):
        """
        Rend la liste des fichiers a charger, en refusant les formats lourds.
        / Returns the files to load, refusing the heavy formats.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        POURQUOI REFUSER PLUTOT QU'IGNORER

        Le PDF et le docx n'ont pas ete eprouves par Docling sur cette
        machine. Une commande de fixtures qui convertit des PDF en masse a
        fait tomber le serveur le 10 aout 2026 : 2 031 Mio et 98 s pour
        trois pages. Les laisser passer en silence rejouerait l'incident ;
        les refuser en le disant oriente vers le chemin prevu pour eux.
        / Refusing loudly beats ignoring silently: mass PDF conversion
        took the server down.
        """
        from django.core.management.base import CommandError

        if not fichiers_de_l_option:
            return list(DOCUMENTS_ETALONS)

        fichiers_retenus = []
        for chemin_demande in fichiers_de_l_option:
            nom_du_fichier = os.path.basename(chemin_demande)
            extension = os.path.splitext(nom_du_fichier)[1].lower()

            if extension in EXTENSIONS_REFUSEES:
                raise CommandError(
                    f"« {nom_du_fichier} » est un {extension} : cette "
                    f"commande ne lance jamais Docling sur ce format. Une "
                    f"conversion de PDF coûte 2 031 Mio et 98 s (mesure du "
                    f"11 août 2026) ; une commande de fixtures qui en "
                    f"enchaîne a fait tomber le serveur le 10 août. Passer "
                    f"par `charger_fixtures_pdf`, qui rejoue des fixtures "
                    f"déjà converties, sans Docling.",
                )

            if nom_du_fichier not in DOCUMENTS_ETALONS:
                raise CommandError(
                    f"« {nom_du_fichier} » n'est pas un document étalon. "
                    f"Attendus : {', '.join(DOCUMENTS_ETALONS)}.",
                )

            fichiers_retenus.append(nom_du_fichier)

        return fichiers_retenus
```

Chaque `_charger_*` commence désormais par une garde :

```python
        if FICHIER_DE_LA_CAPTURE not in self.fichiers_demandes:
            return None
```

(et l'équivalent avec `FICHIER_DU_MARKDOWN`, `FICHIER_DE_LA_TRANSCRIPTION`,
`FICHIER_DU_MP3` dans les trois autres méthodes.)

- [ ] **Étape 4 : lancer les tests, vérifier qu'ils passent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK`, 20 tests.

- [ ] **Étape 5 : vérifier le refus en vrai**

```bash
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample --fichier sample/Etude_Epistemologique_IA.pdf
```

Attendu : le message de refus, et **aucune conversion** — la commande
rend la main immédiatement, pas au bout de 98 s.

- [ ] **Étape 6 : point d'arrêt**

---

## Tâche 5 : `--reset` et son garde-fou
## Contraintes globales

Elles valent pour **toutes** les tâches.

- **Aucune opération git.** Ni `add`, ni `commit`, ni `checkout --`, ni
  `stash`, ni `restore`. Le dépôt appartient au mainteneur. Chaque tâche
  se termine par un point d'arrêt, pas par un commit.
- **Aucun `ruff format` ni `ruff check --fix`** sur un fichier existant.
- **Une seule suite de tests à la fois.** Jamais `--parallel`. Deux runs
  simultanés se détruisent la base.
- **Commentaires bilingues** français puis anglais, sur chaque bloc de
  logique. C'est la convention du dépôt, sans exception.
- **Noms de variables verbeux** en français : `carnet_des_etalons`, pas
  `carnet`. `nombre_d_elements_crees`, pas `n`.
- **Chaque fichier créé porte un en-tête** avec une ligne
  `LOCALISATION : <chemin>`, comme tous les modules du dépôt.
- **Jamais Docling sur un `.pdf` ou un `.docx`** depuis cette commande.
- **Ne jamais inventer un chiffre.** Un compte annoncé est un compte mesuré.

### Commandes de référence

```bash
# Lancer un test
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus

# Lancer la commande
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample --a-blanc
```

`uv run` est obligatoire : `python manage.py` seul échoue dans ce
conteneur (`ImportError: Couldn't import Django`).

---

## Structure des fichiers
## Faits établis — ne pas les redécouvrir

Mesurés le 11 août 2026 sur cette machine. Ils dispensent de vérifier.

| Fait | Valeur |
|---|---|
| Champ d'état d'ingestion sur `Page` | **`ingestion_etat`** (pas `etat_ingestion`), plus `ingestion_detail` et `ingestion_maj_le` |
| Sans `TranscriptionConfig` active | la transcription est **mockée en silence** (`front/tasks.py:633`) |
| `sample/fake_debat_ia_transcription.json` | 12 segments, 3 locuteurs (Laurent, Elinor, Eric), clés racine `model` / `text` / `segments` |
| `sample/capture-web-badgeons-la-normandie.html` | 8 523 octets, déjà extrait |
| Conversion Docling d'un PDF de 3 pages | 2 031 Mio, 98 s dont ~89 s de chargement des modèles |
| L'import d'un JSON de transcription par la vue | **ne crée aucun élément** — la commande doit appeler l'ingestion elle-même |

### Signatures dont le code a besoin

```python
# core/services/corpus.py
ranger_une_note_dans_un_carnet(page, dossier, utilisateur=None)  # -> appartenance

# hypostasis_extractor/tasks_element.py
ingerer_un_fichier_avec_docling(identifiant_de_la_page, chemin_du_fichier=None)
ingerer_une_capture_web_avec_docling(identifiant_de_la_page)
ingerer_une_transcription_diarisee_en_elements(identifiant_de_la_page)
# -> {"elements": int} ou {"erreur": str}

# front/tasks.py
transcrire_audio_task(job_id, chemin_fichier_audio, max_locuteurs=5, langue="")

# front/services/transcription_audio.py
construire_html_diarise(donnees)  # -> (html_diarise, texte_brut)
```

Appel synchrone d'une tâche : `ingerer_un_fichier_avec_docling.apply(args=[page.pk])`.

---

## Tâche 1 : le squelette — propriétaire, carnet, config, `--a-blanc`
