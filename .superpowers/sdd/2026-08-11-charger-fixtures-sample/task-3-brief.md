## Tâche 3 : les deux entrées audio — transcription JSON et mp3

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`

**Interfaces :**
- Consomme : `_note_deja_presente()`, `_elements_du_resultat()` de la tâche 2.
- Produit : `_charger_la_transcription_json(proprietaire, carnet)`,
  `_charger_le_mp3(proprietaire, carnet)`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
class EntreesAudioTest(TestCase):
    """La transcription déjà faite, et la chaîne mp3 complète."""

    def _mocks_docling(self):
        """Les deux tâches Docling, neutralisées ensemble."""
        return (
            patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_capture_web_avec_docling.apply",
            ),
            patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_un_fichier_avec_docling.apply",
            ),
        )

    def test_le_json_devient_une_page_audio_avec_ses_elements(self):
        capture_mockee, fichier_mocke = self._mocks_docling()
        cible_ingestion = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply"
        )
        with capture_mockee, fichier_mocke, patch(cible_ingestion) as ingestion:
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_du_json = Page.objects.get(
            original_filename="fake_debat_ia_transcription.json",
        )
        self.assertEqual(page_du_json.source_type, "audio")
        # 12 segments, 3 locuteurs — mesure du fichier versionne.
        # / 12 segments, 3 speakers, measured from the versioned file.
        self.assertEqual(len(page_du_json.transcription_raw["segments"]), 12)
        # LE POINT : la vue d'import, elle, N'appelle PAS cette ingestion
        # (front/views.py:5326). Une note importee par cette porte reste
        # sans element. La commande, elle, doit l'appeler.
        # / The import view never calls this; the command must.
        ingestion.assert_called_once_with(args=[page_du_json.pk])

    def test_sans_mp3_la_transcription_voxtral_n_est_pas_lancee(self):
        capture_mockee, fichier_mocke = self._mocks_docling()
        cible_voxtral = "front.tasks.transcrire_audio_task.apply"
        with capture_mockee, fichier_mocke, patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply",
        ), patch(cible_voxtral) as voxtral_mocke:
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        voxtral_mocke.assert_not_called()
        self.assertFalse(
            Page.objects.filter(
                original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
            ).exists(),
        )

    def test_sans_cle_mistral_le_mp3_est_saute_et_le_reste_charge(self):
        import os

        capture_mockee, fichier_mocke = self._mocks_docling()
        sortie = StringIO()
        cle_sauvegardee = os.environ.pop("MISTRAL_API_KEY", None)
        try:
            with capture_mockee, fichier_mocke, patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_transcription_diarisee_en_elements.apply",
            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
                call_command("charger_fixtures_sample", stdout=sortie)
        finally:
            if cle_sauvegardee is not None:
                os.environ["MISTRAL_API_KEY"] = cle_sauvegardee

        voxtral.assert_not_called()
        self.assertIn("MISTRAL_API_KEY", sortie.getvalue())
        # Les trois autres notes sont chargees malgre tout.
        # / The other three notes are loaded regardless.
        self.assertEqual(Page.objects.count(), 3)

    def test_avec_la_cle_le_mp3_cree_une_page_et_un_job(self):
        import os

        capture_mockee, fichier_mocke = self._mocks_docling()
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
            with capture_mockee, fichier_mocke, patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_transcription_diarisee_en_elements.apply",
            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
                call_command("charger_fixtures_sample", stdout=StringIO())

        from core.models import TranscriptionJob

        page_du_mp3 = Page.objects.get(
            original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
        )
        job = TranscriptionJob.objects.get(page=page_du_mp3)
        self.assertEqual(job.transcription_config.provider, "voxtral")
        voxtral.assert_called_once()
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample.EntreesAudioTest --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `Page.DoesNotExist` sur le JSON.

- [ ] **Étape 3 : écrire le chargement des entrées audio**

```python
# Constantes, en tete de fichier
FICHIER_DE_LA_TRANSCRIPTION = "fake_debat_ia_transcription.json"
FICHIER_DU_MP3 = "audio-FR-2locuteur-palaiscesar-14s.mp3"
```

Étendre `_charger_les_documents` :

```python
    def _charger_les_documents(self, proprietaire, carnet_des_etalons):
        self._charger_la_capture_web(proprietaire, carnet_des_etalons)
        self._charger_le_markdown(proprietaire, carnet_des_etalons)
        self._charger_la_transcription_json(proprietaire, carnet_des_etalons)
        self._charger_le_mp3(proprietaire, carnet_des_etalons)
```

```python
    def _charger_la_transcription_json(self, proprietaire, carnet_des_etalons):
        """
        Cree la note issue de la transcription deja faite, et l'ingere.
        / Creates the note from the ready-made transcript, and ingests it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        DOCLING N'INTERVIENT PAS : une transcription diarisee est deja
        structuree. `ingerer_une_transcription_diarisee` la decoupe en
        tours de parole sans charger le moindre modele.
        / Docling plays no part: a diarised transcript is already structured.

        ATTENTION — la vue d'import, elle, N'appelle PAS cette ingestion
        (front/views.py:5326) : une note importee par cette porte reste
        sans element, donc sans gouttiere et sans ancrage possible. C'est
        un trou de l'application, releve le 11 aout 2026. La commande
        appelle l'ingestion explicitement.
        / The import view never triggers this ingestion; we do it here.
        """
        import json

        if self._note_deja_presente(
            carnet_des_etalons, FICHIER_DE_LA_TRANSCRIPTION,
        ):
            self.stdout.write("Transcription JSON  : déjà présente — sautée")
            return None

        if self.a_blanc:
            self.stdout.write("Transcription JSON  : serait chargée")
            return None

        from front.services.transcription_audio import construire_html_diarise

        chemin_du_json = REPERTOIRE_SAMPLE / FICHIER_DE_LA_TRANSCRIPTION
        contenu_brut = chemin_du_json.read_text(encoding="utf-8")
        donnees_de_la_transcription = json.loads(contenu_brut)

        html_diarise, texte_brut = construire_html_diarise(
            donnees_de_la_transcription,
        )

        page_du_json = Page.objects.create(
            source_type="audio",
            original_filename=FICHIER_DE_LA_TRANSCRIPTION,
            url=None,
            title="Débat IA — transcription",
            html_original="",
            html_readability=html_diarise,
            text_readability=texte_brut,
            content_hash=hashlib.sha256(
                texte_brut.encode("utf-8"),
            ).hexdigest(),
            transcription_raw=donnees_de_la_transcription,
            status="completed",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(
                contenu_brut.encode("utf-8"),
                name=FICHIER_DE_LA_TRANSCRIPTION,
            ),
        )
        ranger_une_note_dans_un_carnet(
            page_du_json, carnet_des_etalons, proprietaire,
        )

        from hypostasis_extractor.tasks_element import (
            ingerer_une_transcription_diarisee_en_elements,
        )

        resultat = ingerer_une_transcription_diarisee_en_elements.apply(
            args=[page_du_json.pk],
        )
        self.stdout.write(
            f"Transcription JSON  : {self._elements_du_resultat(resultat)} "
            f"tour(s) de parole",
        )
        return page_du_json

    def _charger_le_mp3(self, proprietaire, carnet_des_etalons):
        """
        Cree la note audio et lance la vraie transcription Voxtral.
        / Creates the audio note and runs the real Voxtral transcription.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        C'est la seule fixture qui eprouve la chaine COMPLETE : mp3 ->
        Voxtral -> tours de parole -> elements. Un appel reseau reel, donc
        aussi un test de bout en bout a chaque chargement.
        / The only fixture exercising the full chain, network call included.

        La tache enchaine elle-meme l'ingestion en elements, mais par
        `.delay()` : sans worker, elle partirait dans le broker et ne se
        ferait jamais. On la rejoue donc ici, en synchrone, si la page
        n'a pas d'element. / The task chains via .delay(); we redo it sync.
        """
        if self.sans_mp3:
            self.stdout.write("Audio mp3           : sauté (--sans-mp3)")
            return None

        if not os.environ.get("MISTRAL_API_KEY"):
            self.stdout.write(self.style.WARNING(
                "Audio mp3           : sauté — pas de MISTRAL_API_KEY. "
                "La transcription serait mockée, pas réelle.",
            ))
            return None

        if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MP3):
            self.stdout.write("Audio mp3           : déjà présent — sauté")
            return None

        if self.a_blanc:
            self.stdout.write("Audio mp3           : serait transcrit (Voxtral)")
            return None

        from core.models import TranscriptionConfig, TranscriptionJob

        chemin_du_mp3 = REPERTOIRE_SAMPLE / FICHIER_DU_MP3
        octets_du_mp3 = chemin_du_mp3.read_bytes()

        page_du_mp3 = Page.objects.create(
            source_type="audio",
            original_filename=FICHIER_DU_MP3,
            url=None,
            title="Palais César — deux locuteurs",
            html_original="",
            html_readability="",
            text_readability="",
            content_hash="",
            status="processing",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(octets_du_mp3, name=FICHIER_DU_MP3),
        )
        ranger_une_note_dans_un_carnet(
            page_du_mp3, carnet_des_etalons, proprietaire,
        )

        config_active = TranscriptionConfig.objects.filter(
            is_active=True,
        ).first()
        job_de_transcription = TranscriptionJob.objects.create(
            page=page_du_mp3,
            transcription_config=config_active,
            audio_filename=FICHIER_DU_MP3,
            status="pending",
        )

        from front.tasks import transcrire_audio_task

        transcrire_audio_task.apply(args=[
            job_de_transcription.pk,
            page_du_mp3.source_file.path,
            config_active.max_speakers if config_active else 5,
            config_active.language if config_active else "fr",
        ])

        page_du_mp3.refresh_from_db()

        # La tache enchaine l'ingestion par `.delay()`. Sans worker, elle
        # n'a pas eu lieu : on la rejoue ici, en synchrone.
        # / The task chained via .delay(); without a worker, redo it here.
        if not page_du_mp3.elements.exists() and page_du_mp3.transcription_raw:
            from hypostasis_extractor.tasks_element import (
                ingerer_une_transcription_diarisee_en_elements,
            )

            ingerer_une_transcription_diarisee_en_elements.apply(
                args=[page_du_mp3.pk],
            )

        self.stdout.write(
            f"Audio mp3 (Voxtral) : {page_du_mp3.elements.count()} "
            f"tour(s) de parole",
        )
        return page_du_mp3
```

- [ ] **Étape 4 : lancer les tests, vérifier qu'ils passent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK`, 16 tests.

- [ ] **Étape 5 : lancer la commande complète, appel Voxtral réel compris**

```bash
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample
```

Attendu : quatre lignes chiffrées, dont la capture web à 28 éléments.
Vérifier ensuite en base que la note du mp3 porte bien des locuteurs :

```bash
docker exec -w /app hypostasia_web uv run python manage.py shell -c "
from core.models import Page
for page in Page.objects.filter(source_type='audio'):
    locuteurs = {(e.provenance or {}).get('locuteur') for e in page.elements.all()}
    print(page.original_filename, '|', page.elements.count(), 'éléments |', locuteurs)
"
```

Attendu : des locuteurs nommés, pas `{None}`. `{None}` signifierait que la
provenance n'a pas été posée à l'ingestion.

- [ ] **Étape 6 : point d'arrêt**

Ne rien commiter. Rapporter les quatre comptes et les locuteurs trouvés.

---

## Tâche 4 : `--fichier`, et le refus du PDF et du docx
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
