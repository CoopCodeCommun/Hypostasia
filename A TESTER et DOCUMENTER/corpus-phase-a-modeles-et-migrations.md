# Couche corpus, phase A — modèles, migrations, role_special

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
