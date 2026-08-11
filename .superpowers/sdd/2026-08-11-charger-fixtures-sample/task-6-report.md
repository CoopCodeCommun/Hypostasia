# Rapport — Tâche 6 : le contrôle réel — 28 éléments sur la capture web

## Ce qui a été fait

Ajout, en fin de `hypostasis_extractor/tests/test_fixtures_representatives.py`,
d'une classe `CaptureWebEtalonTest` (tag `docling`, sautée sans
`TESTS_DOCLING=1`), reprise verbatim du brief — je n'ai pas touché aux
classes existantes du fichier :

- `test_la_capture_web_rend_vingt_huit_elements` : charge uniquement la
  capture web (`--fichier capture-web-badgeons-la-normandie.html`) via
  `charger_fixtures_sample`, compte les `ElementDocument` de la page
  `source_type="web"`, vérifie le total (28) et la ventilation exacte par
  label.
- `test_la_page_ingeree_porte_l_etat_reussie` : même chargement, vérifie
  `page.ingestion_etat == EtatIngestion.REUSSIE`.

Seul écart avec le texte du brief : un commentaire bilingue ajouté au-dessus
de l'appel `call_command` du premier test, expliquant pourquoi on charge
seulement la capture (pas les quatre documents étalons) — convention du
dépôt, aucune conséquence sur le test lui-même.

## Fichier modifié

- `hypostasis_extractor/tests/test_fixtures_representatives.py` : nouvelle
  classe `CaptureWebEtalonTest` (2 tests) ajoutée en fin de fichier.

## Étape 2 — sans le drapeau

```
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_fixtures_representatives --noinput \
    --settings=hypostasia.settings_test_opus
```

Sortie :

```
Creating test database for alias 'default'...
ssss..
----------------------------------------------------------------------
Ran 6 tests in 0.546s

OK (skipped=4)
Destroying test database for alias 'default'...
```

6 tests trouvés (2 non-Docling + 4 tagués `docling`, dont les 2 nouveaux),
les 4 tagués `docling` sautés (`skipped=4`), suite exécutée en 0,546 s.
Temps total de la commande (avec création/destruction de la base de test et
les logs de migrations de données) : **≈ 13 s** — aucun modèle Docling
chargé, loin des ~98 s d'une conversion réelle. Conforme à l'attendu.

## Étape 3 — avec le drapeau

Vérification mémoire avant lancement :

```
free -h | head -2
               total       utilisé      libre     partagé tamp/cache   disponible
Mem:            30Gi        14Gi       1,0Gi       4,4Gi        19Gi        16Gi
```

16 Gio disponibles, largement au-dessus du seuil de 4 Gio.

```
docker exec -w /app -e TESTS_DOCLING=1 hypostasia_web uv run python \
    manage.py test hypostasis_extractor.tests.test_fixtures_representatives \
    --noinput --settings=hypostasia.settings_test_opus --tag=docling
```

Sortie :

```
Creating test database for alias 'default'...
[15:13:25] INFO hypostasis_extractor.services.ingestion_docling — Docling : 28 element(s) retenu(s) sur le document.
[15:13:25] INFO hypostasis_extractor.services.ingestion_docling — Page 1 : 28 element(s) cree(s) depuis Docling.
[15:13:25] INFO hypostasis_extractor.tasks_element — Page 1 : 28 element(s) ingere(s) depuis le HTML capture.
.[15:13:25] INFO hypostasis_extractor.services.ingestion_docling — Docling : 28 element(s) retenu(s) sur le document.
[15:13:25] INFO hypostasis_extractor.services.ingestion_docling — Page 2 : 28 element(s) cree(s) depuis Docling.
[15:13:25] INFO hypostasis_extractor.tasks_element — Page 2 : 28 element(s) ingere(s) depuis le HTML capture.
.[15:13:26] INFO hypostasis_extractor.services.ingestion_docling — Docling : 3 element(s) retenu(s) sur le document.
[15:13:26] INFO hypostasis_extractor.services.ingestion_docling — Page 3 : 3 element(s) cree(s) depuis Docling.
.[15:13:26] INFO hypostasis_extractor.services.ingestion_docling — Docling : 13 element(s) retenu(s) sur le document.
[15:13:26] INFO hypostasis_extractor.services.ingestion_docling — Page 4 : 13 element(s) cree(s) depuis Docling.
.
----------------------------------------------------------------------
Ran 4 tests in 6.415s

OK
Destroying test database for alias 'default'...
```

`real 0m20,642s` (temps total de la commande, DB de test comprise).

Les 4 tests tagués `docling` passent : les 2 nouveaux (capture web, deux
appels indépendants de la commande, chacun produisant sa propre `Page` —
logs « Page 1 : 28 element(s) » et « Page 2 : 28 element(s) ») et les 2
préexistants (docx avec tableau → « Page 3 : 3 element(s) », pad markdown
→ « Page 4 : 13 element(s) »).

**Le temps de conversion réel observé (≈ 6 s pour les 4 conversions
combinées) est bien plus court que les 80–164 s mesurées le 11 août** —
vraisemblablement parce que les modèles Docling sont déjà en cache disque
sur cette machine (pas de téléchargement), et que la capture web est un
document HTML léger. Le test n'en est pas moins un vrai run Docling : les
logs `hypostasis_extractor.services.ingestion_docling` proviennent du
service réel, jamais émis par le mock.

## Compte obtenu — confirmé, aucun écart

**28 éléments**, ventilation :

| label | compte |
|---|---|
| `section_header` | 4 |
| `list_item` | 5 |
| `text` | 19 |
| **total** | **28** |

Identique au compte attendu du brief. Les deux tests sont passés du premier
coup, sans aucun ajustement du test ni du code de production.

## Confirmation

- Sans `TESTS_DOCLING=1` : les 4 tests `docling` (dont les 2 nouveaux) sont
  sautés, la suite rend la main en quelques secondes.
- Avec `TESTS_DOCLING=1 --tag=docling` : les 4 tests passent, `OK`.
- Aucune opération git effectuée.
