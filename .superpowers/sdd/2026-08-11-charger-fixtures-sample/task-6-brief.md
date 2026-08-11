## Tâche 6 : le contrôle réel — 28 éléments sur la capture web

**Fichiers :**
- Modifier : `hypostasis_extractor/tests/test_fixtures_representatives.py`

Ce fichier porte déjà le patron : `DOCLING_DEMANDE = os.environ.get("TESTS_DOCLING") == "1"`,
`@tag("docling")`, et son en-tête explique pourquoi ces tests ne tournent
jamais dans une suite ordinaire.

**Interfaces :**
- Consomme : la commande complète des tâches 1 à 5.

- [ ] **Étape 1 : écrire le test qui échoue**

```python
@tag("docling")
@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
class CaptureWebEtalonTest(TestCase):
    """
    Le contrôle de non-régression de l'extraction HTML.
    / The HTML extraction's non-regression control.

    LOCALISATION : hypostasis_extractor/tests/test_fixtures_representatives.py

    Ce compte VERROUILLE les deux correctifs du 11 août 2026 :

    - une image n'est pas un tableau : sans légende elle ne produit
      aucun bloc, au lieu du message « Image not available… » destiné au
      développeur ;
    - un gras ne coupe pas une phrase : les fragments d'un même groupe
      inline se recollent, au lieu de produire deux blocs là où l'auteur
      a écrit une phrase.

    54 éléments dont un `picture` = retour à la version d'avant les
    correctifs. Une cinquantaine de blocs tous en `text` = retour du
    découpage maison par paragraphes.
    / This count locks in the two 11 August fixes.
    """

    def test_la_capture_web_rend_vingt_huit_elements(self):
        from io import StringIO

        from django.core.management import call_command

        from core.models import ElementDocument, Page

        call_command(
            "charger_fixtures_sample",
            "--fichier", "capture-web-badgeons-la-normandie.html",
            stdout=StringIO(),
        )

        page_de_la_capture = Page.objects.get(source_type="web")
        elements = ElementDocument.objects.filter(page=page_de_la_capture)

        self.assertEqual(elements.count(), 28)

        comptes_par_label = {}
        for element in elements:
            comptes_par_label[element.label] = (
                comptes_par_label.get(element.label, 0) + 1
            )

        self.assertEqual(
            comptes_par_label,
            {"section_header": 4, "list_item": 5, "text": 19},
        )

    def test_la_page_ingeree_porte_l_etat_reussie(self):
        """
        L'état d'ingestion ne peut se tester qu'ici.
        / The ingestion state can only be tested here.

        Avec Docling mocké, la tâche ne tourne pas, donc n'écrit pas
        `ingestion_etat` : un test rapide qui l'affirmerait ne
        vérifierait que son propre mock. C'est justement l'écart que
        `charger_fixtures_llm_reel` a laissé passer — ses pages
        gardent un état vide alors que l'écran de lecture l'affiche.
        / A mocked task writes no state; asserting it would test the mock.
        """
        from io import StringIO

        from django.core.management import call_command

        from core.models import EtatIngestion, Page

        call_command(
            "charger_fixtures_sample",
            "--fichier", "capture-web-badgeons-la-normandie.html",
            stdout=StringIO(),
        )

        page_de_la_capture = Page.objects.get(source_type="web")
        self.assertEqual(
            page_de_la_capture.ingestion_etat, EtatIngestion.REUSSIE,
        )
```

- [ ] **Étape 2 : lancer le test SANS le drapeau, vérifier qu'il est sauté**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_fixtures_representatives --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `OK (skipped=…)`. Aucun modèle Docling ne doit être chargé —
la commande doit rendre la main en quelques secondes, pas en 98 s.

- [ ] **Étape 3 : lancer le test AVEC le drapeau**

```bash
free -h | head -2
docker exec -w /app -e TESTS_DOCLING=1 hypostasia_web uv run python \
    manage.py test hypostasis_extractor.tests.test_fixtures_representatives \
    --noinput --settings=hypostasia.settings_test_opus --tag=docling
```

Attendu : `OK`. Une vraie conversion Docling, quelques dizaines de
secondes.

**Si le compte diffère de 28 :** ne pas ajuster le test au résultat.
S'arrêter, relever le compte obtenu et sa ventilation complète par label,
et le signaler. Un écart signifie que `extraire_les_elements_bruts` a
changé de comportement — c'est exactement ce que ce test existe pour
détecter, et le corriger en silence détruirait sa seule raison d'être.

- [ ] **Étape 4 : point d'arrêt**

Rapporter le compte obtenu et la ventilation par label.

---

## Vérification finale
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
