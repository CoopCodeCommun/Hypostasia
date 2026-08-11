## Tâche 5 : `--reset` et son garde-fou

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`

**Interfaces :**
- Consomme : `NOM_DU_CARNET`, `_proprietaire()`.
- Produit : l'option `--reset` et `_reinitialiser(proprietaire)`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
class ReinitialisationTest(TestCase):
    """--reset rejoue tout, sauf s'il y a des preuves à perdre."""

    def _charger_une_fois(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        cible_audio = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply"
        )
        with patch(cible_capture), patch(cible_fichier), patch(cible_audio):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

    def test_reset_supprime_les_notes_et_les_recharge(self):
        self._charger_une_fois()
        pks_de_depart = set(Page.objects.values_list("pk", flat=True))
        self.assertEqual(len(pks_de_depart), 3)

        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--reset", "--sans-mp3",
                stdout=StringIO(),
            )
            # Le point du reset : on RECONVERTIT, la ou l'idempotence
            # aurait saute. / The point of --reset: convert again.
            self.assertEqual(capture_mockee.call_count, 1)

        self.assertEqual(Page.objects.count(), 3)
        self.assertFalse(
            set(Page.objects.values_list("pk", flat=True)) & pks_de_depart,
        )

    def test_reset_refuse_si_une_note_porte_une_ancre(self):
        from django.core.management.base import CommandError

        # Ces trois modeles vivent dans hypostasis_extractor, PAS dans
        # core.models. / These three live in hypostasis_extractor.
        from hypostasis_extractor.models import (
            AncrageExtraction, ExtractedEntity, ExtractionJob,
        )

        self._charger_une_fois()
        page_avec_ancre = Page.objects.filter(source_type="web").first()
        element = page_avec_ancre.elements.create(
            ordre=0, label="text", texte="un passage", empreinte_contenu="x",
        )
        job = ExtractionJob.objects.create(
            page=page_avec_ancre, name="job de test",
            prompt_description="peu importe", status="completed",
        )
        entite = ExtractedEntity.objects.create(
            job=job, extraction_class="PHENOMENE", extraction_text="une idée",
            start_char=0, end_char=10,
        )
        # Les champs sont debut_dans_element / fin_dans_element — des
        # positions DANS l'element, jamais dans le texte global de la
        # page. / Positions within the element, never page-global.
        AncrageExtraction.objects.create(
            extraction=entite, element=element,
            ordre_dans_extraction=0,
            debut_dans_element=0, fin_dans_element=10,
        )

        nombre_de_pages_avant = Page.objects.count()
        with self.assertRaises(CommandError) as contexte:
            call_command(
                "charger_fixtures_sample", "--reset", "--sans-mp3",
                stdout=StringIO(),
            )

        # RIEN ne doit avoir ete supprime — pas de suppression partielle
        # qui laisserait le carnet a moitie vide.
        # / Nothing deleted: no half-emptied notebook.
        self.assertEqual(Page.objects.count(), nombre_de_pages_avant)
        self.assertIn(page_avec_ancre.title, str(contexte.exception))

    def test_reset_ne_touche_pas_une_note_rangee_ailleurs(self):
        from core.models import Dossier as CarnetModele
        from core.services.corpus import ranger_une_note_dans_un_carnet

        self._charger_une_fois()
        page_partagee = Page.objects.filter(source_type="web").first()
        proprietaire = page_partagee.owner
        autre_carnet = CarnetModele.objects.create(
            name="Un autre carnet", owner=proprietaire,
        )
        ranger_une_note_dans_un_carnet(page_partagee, autre_carnet, proprietaire)

        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--reset", "--sans-mp3",
                stdout=StringIO(),
            )

        # Elle vit ailleurs : on ne l'emporte pas.
        # / It lives elsewhere: not ours to delete.
        self.assertTrue(Page.objects.filter(pk=page_partagee.pk).exists())
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample.ReinitialisationTest --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : erreur sur `--reset` inconnu.

**Note :** si `AncrageExtraction` ou `ExtractedEntity` n'ont pas ces
champs exacts, lire `core/models.py:1670` et suivants et **corriger le
test**, pas le modèle. Le test doit refléter le schéma réel.

- [ ] **Étape 3 : écrire la réinitialisation**

```python
    def add_arguments(self, analyseur_d_arguments):
        # ... les trois options precedentes ...
        analyseur_d_arguments.add_argument(
            "--reset", action="store_true",
            help=(
                "Supprime le carnet etalon et ses notes propres avant de "
                "recharger. Refuse si une note porte des ancres."
            ),
        )
```

Dans `handle`, juste après `proprietaire = self._proprietaire()` :

```python
        if options["reset"]:
            self._reinitialiser(proprietaire)
```

```python
    def _reinitialiser(self, proprietaire):
        """
        Supprime le carnet etalon et les notes qui n'appartiennent qu'a lui.
        / Deletes the reference notebook and the notes filed only in it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        POURQUOI CETTE OPTION EXISTE

        L'idempotence saute ce qui est deja la — y compris l'appel Voxtral,
        qu'on veut precisement pouvoir rejouer a chaque chargement. `--reset`
        est la seule facon de tout refaire.
        / Idempotency skips the Voxtral call we want to replay.

        LE GARDE-FOU N'EST PAS FACULTATIF

        `AncrageExtraction.element` est en PROTECT : supprimer une page qui
        porte des ancres leve ProtectedError. On ne se contente pas de
        laisser l'exception sortir — on VERIFIE D'ABORD, et on refuse tout
        en bloc. Une suppression partielle laisserait le carnet a moitie
        vide, dans un etat que personne n'a voulu.
        / Check first and refuse wholesale: a partial delete is worse.
        """
        from django.core.management.base import CommandError

        from hypostasis_extractor.models import AncrageExtraction

        carnet_existant = Dossier.objects.filter(
            name=NOM_DU_CARNET, owner=proprietaire,
        ).first()
        if carnet_existant is None:
            self.stdout.write("Réinitialisation    : aucun carnet à supprimer")
            return None

        # Les notes rangees UNIQUEMENT dans ce carnet sont a nous. Une note
        # rangee ailleurs aussi appartient a ce quelqu'un d'autre.
        # / Only notes filed solely here are ours to remove.
        notes_a_supprimer = []
        for page in Page.objects.filter(
            appartenances_dossiers__dossier=carnet_existant,
        ).distinct():
            rangee_ailleurs = page.appartenances_dossiers.exclude(
                dossier=carnet_existant,
            ).exists()
            if not rangee_ailleurs:
                notes_a_supprimer.append(page)

        # VERIFIER AVANT DE SUPPRIMER.
        notes_avec_ancres = []
        for page in notes_a_supprimer:
            nombre_d_ancres = AncrageExtraction.objects.filter(
                element__page=page,
            ).count()
            if nombre_d_ancres:
                notes_avec_ancres.append((page, nombre_d_ancres))

        if notes_avec_ancres:
            detail = " ; ".join(
                f"« {page.title} » ({nombre} ancre(s))"
                for page, nombre in notes_avec_ancres
            )
            raise CommandError(
                f"--reset refusé : {detail}. Ces notes portent des "
                f"extractions ancrées, et une ancre est une preuve. Rien "
                f"n'a été supprimé. Retirer les portions d'abord, ou "
                f"recharger dans une base neuve.",
            )

        if self.a_blanc:
            self.stdout.write(
                f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
                f"seraient supprimées",
            )
            return None

        for page in notes_a_supprimer:
            page.delete()
        carnet_existant.delete()

        self.stdout.write(
            f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
            f"supprimée(s), carnet supprimé",
        )
        return None
```

- [ ] **Étape 4 : lancer toute la suite, vérifier qu'elle passe**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK`, 24 tests.

- [ ] **Étape 5 : point d'arrêt**

---

## Tâche 6 : le contrôle réel — 28 éléments sur la capture web
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
