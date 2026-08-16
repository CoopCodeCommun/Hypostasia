# Couche corpus, phase A : modeles, migrations, role_special

**Date :** 2026-08-08
**Migration :** Oui

**Quoi / What :** le socle de donnees de la couche corpus
(SPEC-corpus-base-carnet-note.md v1.1 § 3, § 4.2, § 6.3) : les modeles
`BaseDeConnaissances`, `AppartenancePageDossier`, `AppartenanceDossierBase`,
`ListeDeCategories`, `CategorieDossier`, `CategorieBase`, le champ
`Dossier.role_special`, et les migrations de schema + donnees.

**Pourquoi / Why :** une note doit pouvoir vivre dans plusieurs carnets sans
duplication, avec un classement propre a chaque carnet — la categorie est un
attribut de la RELATION note-carnet, pas de la note. Et les carnets
« magiques » (« A ranger », « Mes imports ») etaient retrouves par leur nom :
les renommer cassait la capture et l'import.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | + 6 modeles corpus, + `RoleSpecialDossier`, + `Dossier.role_special` avec contrainte `unicite_role_special_par_proprietaire` |
| `core/migrations/0040_...py` | Schema : les 6 modeles + role_special + contraintes |
| `core/migrations/0041_creer_les_appartenances_depuis_la_fk.py` | Donnees, REVERSIBLE : une appartenance par page ayant un dossier, `integree_le=page.created_at`, bilan chiffre + controle d'integrite qui leve si les comptes different |
| `core/migrations/0042_estampiller_les_dossiers_speciaux.py` | Donnees, REVERSIBLE : pose `role_special` sur les carnets historiques (plus ancien seulement en cas d'homonymes, jamais sans owner) |
| `core/views.py` | `_resoudre_dossier` : fallback retrouve par `role_special`, plus par nom |
| `front/views.py` | `_obtenir_ou_creer_dossier_imports` : idem |
| `core/migrations/0043_...py` | Contrainte role_special reprise avec `nulls_distinct=False` (les fourre-tout sans owner sont limites aussi — retour de relecture) |
| `core/tests/` | `tests.py` (vide) converti en paquet : `test_corpus_modele.py` (18 tests), `test_corpus_migration.py` (4 tests MigrationExecutor), `test_role_special.py` (8 tests) |

### Decisions / Decisions
- `Page.dossier` reste en place, intouchee : la FK porte le « premier carnet »
  pendant la coexistence. Son retrait est la migration 3 de la spec, apres
  recette. / The FK stays during coexistence.
- La question ouverte n°1 de la spec (pages sans dossier -> « A ranger » ?)
  est tranchee de facon conservatrice : on ne les touche pas. Le comportement
  d'acces legacy (tout authentifie si owner=None) sera preserve par la
  phase C (§ 5.2). Sur la base de dev : 1 seule page concernee.
- L'extension continue de filtrer par nom (`popup.js`), sans casser : les noms
  par defaut ne changent pas (spec § 6.3). Reserve : un carnet special
  renomme AVANT la migration n'est pas estampille — un doublon apparaitra
  a la capture suivante (aucun cas sur la base de dev, verifie).
- Relecture adverse passee (8 aout) : 3 correctifs appliques — idempotence
  de 0042 sur base partiellement estampillee, controle d'integrite de 0041
  compte les lignes creees (pas la table), `nulls_distinct=False` sur la
  contrainte role_special. Chaque correctif a son test.

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0040`, `0041`,
  `0042`, `0043`. Appliquees sur la base de dev : 537 pages avec dossier ->
  537 appartenances (COHERENT), 14 « Mes imports » estampilles.

---

## Ce qui a été fait

Le socle de données de `SPEC-corpus-base-carnet-note.md` v1.1 : les deux
relations N-N (note↔carnet, carnet↔base) portées par des tables de liaison
qui portent elles-mêmes les catégories, les axes de classement, et le champ
`Dossier.role_special` qui remplace la recherche par nom des carnets
« A ranger » et « Mes imports ».

### Modifications
| Fichier | Changement |
|---|---|
| `core/models.py` | `BaseDeConnaissances`, `AppartenancePageDossier`, `AppartenanceDossierBase`, `ListeDeCategories`, `CategorieDossier`, `CategorieBase`, `RoleSpecialDossier`, `Dossier.role_special` |
| `core/migrations/0040` | Schéma (généré par makemigrations) |
| `core/migrations/0041` | Données : FK → appartenances, réversible, bilan + contrôle d'intégrité |
| `core/migrations/0042` | Données : estampillage `role_special`, réversible |
| `core/views.py` | `_resoudre_dossier` cherche par `role_special` |
| `front/views.py` | `_obtenir_ou_creer_dossier_imports` cherche par `role_special` |

## Tests à réaliser

### Test 1 : la migration sur une base réelle
```bash
docker exec hypostasia_dev_web python manage.py migrate core
docker exec hypostasia_dev_web python manage.py shell -c "
from core.models import Page, AppartenancePageDossier
print(Page.objects.filter(dossier__isnull=False).count())
print(AppartenancePageDossier.objects.count())"
```
Les deux nombres doivent être égaux (fait sur dev le 8 août : 537 = 537).

### Test 2 : rollback (avec ses limites, à connaître)
```bash
docker exec hypostasia_dev_web python manage.py migrate core 0040
# → la table d'appartenances est vide, Page.dossier intacte
docker exec hypostasia_dev_web python manage.py migrate core
# → tout est recréé à l'identique (integree_le = created_at de la page)
```
**Limites du rollback** (retour de relecture) :
- le reverse de 0041 vide TOUTE la table d'appartenances. C'est sans perte
  tant que la seule écriture est la migration elle-même — c'est-à-dire
  jusqu'à la phase D. Après la phase D, ne plus utiliser ce rollback.
- le reverse de 0042 efface TOUS les role_special, y compris ceux posés
  après coup par les résolveurs. À la ré-application, un fourre-tout
  renommé entre-temps n'est pas ré-estampillé (reconnaissance par nom) :
  la capture suivante créerait un doublon.

### Test 3 : le carnet renommé reste retrouvé
1. Renommer son carnet « Mes imports » en « Fichiers déposés » dans l'UI.
2. Importer un fichier.
3. Vérification attendue : le fichier arrive dans « Fichiers déposés »,
   aucun nouveau carnet « Mes imports » n'est créé.

### Test 4 : suites automatiques
```bash
docker exec hypostasia_dev_web python manage.py test core.tests
```
30 tests (18 modèles + 4 migration + 8 role_special).

**Note** : les tests de migration (MigrationExecutor + TransactionTestCase)
laissent la base de test dans un état non-feuille s'ils sont interrompus.
Symptôme : `setUpClass` en échec sur les classes suivantes, ou un
`DROP DATABASE` refusé. Remède : relancer avec `--noinput` (la base de test
est recréée).

## Compatibilité

- `Page.dossier` reste la source de vérité de lecture pour toutes les vues
  existantes (la conversion des lecteurs est la phase D, en un seul lot).
- L'extension continue de filtrer par nom : les noms par défaut ne changent
  pas, rien ne casse (`extension/popup.js` inchangé). Détail cosmétique :
  après renommage du fourre-tout, il n'est plus masqué par le filtre de la
  popup et apparaît comme cible de classement (clic sans effet néfaste).
  À reprendre en phase I avec la mise à jour de l'extension.
- **Limite connue** : un utilisateur qui avait renommé « A ranger » ou
  « Mes imports » AVANT cette migration n'est pas estampillé (on ne peut
  pas le reconnaître). Sa prochaine capture/import créera un nouveau
  carnet spécial ; l'ancien devient un carnet ordinaire plein. Sur la base
  de dev : aucun cas (0 « A ranger », 14/14 « Mes imports » au nom par
  défaut).
- Question ouverte n°1 de la spec (pages sans dossier) tranchée en
  conservateur : non rangées, comportement d'accès actuel préservé.
  1 page concernée sur la base de dev. À re-trancher explicitement si le
  propriétaire préfère les ranger dans « A ranger ».

