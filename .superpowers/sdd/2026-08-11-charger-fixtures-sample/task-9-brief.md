## Tâche 9 : charger le PDF et créer la base de démonstration

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`
- Modifier : `hypostasis_extractor/tests/test_fixtures_representatives.py`
- Modifier : `docs/superpowers/specs/2026-08-11-fixtures-sample-design.md`
  (le § 3.5 ne dit plus la vérité — l'amender en addendum daté, ne pas le
  réécrire en silence)

**Interfaces :**
- Consomme : `AppartenanceDossierBase`, `BaseDeConnaissances`,
  `_note_deja_presente`, `_elements_du_resultat`.
- Produit : `FICHIER_DU_PDF`, `_charger_le_pdf(proprietaire, carnet)`,
  `_creer_la_base_de_demonstration(proprietaire, carnet)`.

### Le rattachement à la base de connaissances

Le patron exact est dans `front/views_corpus.py:1176` :

```python
AppartenanceDossierBase.objects.get_or_create(
    dossier=carnet, base=base, defaults={"integre_par": utilisateur},
)
```

`BaseDeConnaissances` porte `nom`, `slug`, `description`, `owner`,
`visibilite`. Le `slug` est un `SlugField` **unique** : le poser
explicitement (`demonstration`) plutôt que de le laisser se générer.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
class PdfEtBaseDeDemonstrationTest(TestCase):
    """Le PDF entre dans les étalons, et le carnet dans une base."""

    def _mocks_sans_docling(self):
        """Les quatre tâches d'ingestion, neutralisées ensemble."""
        return [
            patch("hypostasis_extractor.tasks_element."
                  "ingerer_une_capture_web_avec_docling.apply"),
            patch("hypostasis_extractor.tasks_element."
                  "ingerer_un_fichier_avec_docling.apply"),
            patch("hypostasis_extractor.tasks_element."
                  "ingerer_une_transcription_diarisee_en_elements.apply"),
        ]

    def test_le_pdf_est_charge_par_defaut(self):
        from contextlib import ExitStack

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        page_du_pdf = Page.objects.get(
            original_filename="Etude_Epistemologique_IA.pdf",
        )
        self.assertEqual(page_du_pdf.source_type, "file")
        # La tâche résout le chemin depuis source_file : sans lui, elle
        # rendrait {"erreur": "page sans fichier source"}.
        # / The task resolves the path from source_file.
        self.assertTrue(page_du_pdf.source_file)

    def test_le_docx_reste_refuse(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as contexte:
            call_command("charger_fixtures_sample",
                         "--fichier", "quelque-chose.docx", stdout=StringIO())

        self.assertIn(".docx", str(contexte.exception))

    def test_le_carnet_est_range_dans_la_base_demonstration(self):
        from contextlib import ExitStack

        from core.models import AppartenanceDossierBase, BaseDeConnaissances

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        base = BaseDeConnaissances.objects.get(nom="Démonstration")
        carnet = Dossier.objects.get(name="Documents étalons")
        self.assertTrue(
            AppartenanceDossierBase.objects.filter(
                dossier=carnet, base=base,
            ).exists(),
        )

    def test_relancer_ne_cree_pas_deux_bases(self):
        from contextlib import ExitStack

        from core.models import BaseDeConnaissances

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        self.assertEqual(
            BaseDeConnaissances.objects.filter(nom="Démonstration").count(), 1,
        )

    def test_a_blanc_ne_cree_pas_la_base(self):
        call_command("charger_fixtures_sample", "--a-blanc", stdout=StringIO())

        from core.models import BaseDeConnaissances

        self.assertEqual(BaseDeConnaissances.objects.count(), 0)
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_charger_fixtures_sample.PdfEtBaseDeDemonstrationTest \
    --noinput --settings=hypostasia.settings_test_opus
```

- [ ] **Étape 3 : retirer le PDF des extensions refusées**

`EXTENSIONS_REFUSEES` ne garde que `{".docx"}`. Le commentaire qui la
surplombe doit dire **pourquoi le PDF en est sorti** — mesure du 11 août,
référence à `tmp/benchmark-docling-2026-08-11.md` — et pourquoi le docx y
reste : le seul du dépôt ne produit aucun élément.

Le message de `CommandError` parle encore du PDF : le réécrire pour le seul
docx.

- [ ] **Étape 4 : écrire `_charger_le_pdf`**

Sur le patron **exact** de `_charger_le_markdown` : lecture des octets,
`Page` en `source_type="file"` avec `source_file=ContentFile(...)`,
`ranger_une_note_dans_un_carnet`, puis
`ingerer_un_fichier_avec_docling.apply(args=[page.pk])`.

Une différence à respecter : un PDF est **binaire**. `read_bytes()`, pas
`read_text()`. Et `text_readability` ne peut pas recevoir son contenu — le
laisser vide, les éléments porteront le texte.

Ajouter `FICHIER_DU_PDF` à `DOCUMENTS_ETALONS`, **en dernier** : c'est le
document le plus coûteux, les trois autres doivent être chargés avant lui.

Sa ligne de bilan doit annoncer le coût **avant** de commencer, puisqu'elle
va bloquer une minute et demie :

```
PDF                 : conversion Docling en cours (~98 s, ~2 Gio)…
```

- [ ] **Étape 5 : écrire `_creer_la_base_de_demonstration`**

```python
    def _creer_la_base_de_demonstration(self, proprietaire, carnet_des_etalons):
        """
        Range le carnet des étalons dans une base de connaissances.
        / Files the reference notebook into a knowledge base.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        Une base de connaissances est le niveau au-dessus du carnet : elle
        rassemble des carnets pour une communauté. Sans elle, l'écran des
        bases reste vide et rien ne s'y travaille.
        / A knowledge base groups notebooks; without one, its screen is empty.
        """
```

`get_or_create` sur le `nom`, avec `slug="demonstration"` explicite dans les
`defaults` — le `SlugField` est unique, deux exécutions ne doivent pas se
heurter. Puis le `get_or_create` d'`AppartenanceDossierBase`.

Rien ne doit être créé en `--a-blanc`.

- [ ] **Étape 6 : reprendre les tests devenus faux**

Le test `test_un_pdf_est_refuse_sans_conversion` de `RefusDesFormatsLourdsTest`
affirme l'inverse de la nouvelle règle. **Le reprendre, ne pas le supprimer** :
il devient le test du docx. Vérifier aussi les comptes de pages attendus dans
les autres classes — ils passent de 3 à 4 avec `--sans-mp3`.

Ce genre de test qui bascule est le signe d'un vrai changement de
comportement : le dire dans le rapport, ne pas l'ajuster en silence.

- [ ] **Étape 7 : l'étalon PDF, taggé `docling`**

Dans `hypostasis_extractor/tests/test_fixtures_representatives.py`, à côté de
`CaptureWebEtalonTest`, une classe pour le PDF — mêmes décorateurs
`@tag("docling")` et `@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)`.

Elle verrouille ce qu'aucun test ne couvre aujourd'hui :

- **11 éléments**, dont **2 de label `table`** ;
- **11 éléments sur 11** portent `provenance["page_no"]` **et**
  `provenance["boites"]` non vide ;
- les pages vont de 1 à 3.

C'est le premier test du dépôt qui prouve que l'ancrage par coordonnées
fonctionne de bout en bout. **Si un compte diffère, ne pas l'ajuster** :
relever le compte obtenu et le signaler.

- [ ] **Étape 8 : lancer la commande pour de vrai**

```bash
free -h | head -2
docker exec -w /app hypostasia_web uv run python manage.py \
    charger_fixtures_sample --reset
```

Attendu : cinq documents, dont le PDF à 11 éléments. Vérifier ensuite que la
base porte enfin des coordonnées :

```bash
docker exec -w /app hypostasia_web uv run python manage.py shell -c "
from core.models import ElementDocument
avec_page = ElementDocument.objects.exclude(provenance__page_no=None)
print('elements avec page_no :', avec_page.count())
for e in avec_page[:3]:
    print(' ', e.label, '| page', e.provenance.get('page_no'), '|', len(e.provenance.get('boites') or []), 'boite(s)')
"
```

Attendu : un compte **non nul**. La passation notait « 0 élément avec
`page_no` » — c'est ce chiffre qu'on vient corriger.

- [ ] **Étape 9 : amender la spec**

`docs/superpowers/specs/2026-08-11-fixtures-sample-design.md` § 3.5 dit que
le PDF est refusé. Ce n'est plus vrai. Ajouter un **addendum daté** en fin de
document qui explique le renversement et son motif — la mesure. Ne pas
réécrire le § 3.5 en place : la trace de la décision initiale et de son
renversement a plus de valeur qu'un texte lisse.

- [ ] **Étape 10 : point d'arrêt**
# Addendum n°2 du 11 août 2026 — le PDF entre dans les étalons

> Demande du propriétaire du dépôt, en cours de session. **Renverse une
> décision de la spec** (§ 3.5) : le PDF n'est plus refusé, il est chargé
> par défaut.

## Ce qui change, et pourquoi c'est légitime maintenant

Le § 3.5 faisait refuser les `.pdf` parce que Docling n'avait **pas été
éprouvé** sur cette machine, et qu'une commande de fixtures convertissant des
PDF en masse avait fait tomber le serveur le 10 août. Ce motif est levé : la
mesure existe.

| PDF | Pages | Éléments | `provenance.boites` | Durée | RSS pic |
|---|---|---|---|---|---|
| `Etude_Epistemologique_IA.pdf` | 3 | 11, dont **2 `table`** | **11/11** | 98 s | 2 031 Mio |

**Le gain dépasse la fixture.** La passation notait que la base portait
« 0 élément avec `page_no` » — aucun PDF n'avait jamais été ingéré par le
moteur ELEMENT, ce qui rendait le visualiseur PDF impossible à développer
faute de la moindre boîte de coordonnées. Charger ce PDF **remplit enfin ce
trou** : 11 éléments avec `page_no` et boîtes, et le bouton « voir la source »
de la gouttière, déjà codé, a de quoi s'afficher.

**Le docx reste refusé.** Le seul du dépôt (`présentation des open badges.docx`)
est fait de huit diapositives exportées en images : Docling en extrait
**zéro élément**. Une fixture qui ne produit rien n'éprouve rien.

**Le second PDF n'est pas versionné.** `présentation des open badges.pdf`
n'apparaît pas dans `git ls-files sample/` : une fixture non versionnée
n'existe pas pour les autres machines. À versionner d'abord si on le veut.

## Tâche 9 : charger le PDF et créer la base de démonstration
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
