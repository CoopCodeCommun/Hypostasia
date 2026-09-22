# Typer les analyseurs par action / Typing analyzers by action

**Date :** 2026-09-01
**Migration :** **Oui** — `hypostasis_extractor/0038_le_type_rediger_un_article`
(schéma **et** données ; appliquée à la base de dev, elle y a copié 3 pièces) :
`docker exec -w /app hypostasia_web python manage.py migrate hypostasis_extractor`

## Résumé / Summary

**Quoi / What :** un troisième type d'analyseur, `rediger_un_article`, sépare le
préambule des **articles** (création d'un wiki, synthèse dirigée, mise à jour)
de celui de la **synthèse d'une note**. Les deux partent du même texte ; ils
peuvent désormais diverger.
/ A third analyzer type separates the article preamble from the note-synthesis
one. Both start identical and can now diverge.

**Pourquoi / Why :** `_prompt_systeme_de_synthese()` prenait le premier
analyseur actif de type `synthetiser` et servait **quatre gestes** à la lettre
près. On ne pouvait régler l'un sans régler les autres — et le jour où l'on veut
qu'un wiki soit rédigé autrement qu'une synthèse dirigée, il fallait modifier le
code, ce que l'éditeur de prompts existe précisément pour éviter.

## La migration COPIE — elle ne bascule pas / It copies, it does not move

**C'est une correction délibérée de la note qui a commandé ce chantier**, écrite
en addendum daté dans `PLAN/TODO/2026-08-23-typer-les-analyseurs-par-action.md`.

La note demandait de **basculer** « Synthèse délibérative » vers le type neuf.
Or cet analyseur sert **deux métiers** : la rédaction d'article
(`_prompt_systeme_de_synthese`) **et** la synthèse d'une note, que trois vues
résolvent par `type_analyseur="synthetiser"` — `previsualiser_synthese`,
`synthetiser` et `drawer_contenu`.

Le basculer les aurait laissées sans aucun analyseur : **HTTP 400** et le toast
« Aucun analyseur de synthèse actif ». **Et le remède que ce toast affiche
n'aurait rien réparé** : `creer_les_modeles_ia_et_les_analyseurs()` fait
`get_or_create(name="Synthèse délibérative")`, aurait retrouvé l'analyseur
basculé **par son nom**, et n'aurait jamais recréé de `synthetiser`. La casse
aurait été permanente, et le message affiché mensonger.

La copie préserve l'intention de la note — le prompt personnalisé ne devient pas
orphelin, il part dans les deux — sans casser un geste existant.

### Il fallait la migration **et** les fixtures, pas l'une ou l'autre

`bin/install.sh` **migre avant de poser les fixtures**. Sur un clone neuf,
« Synthèse délibérative » n'existe pas encore quand la migration passe : elle n'a
rien à copier. Sans le troisième `get_or_create` ajouté aux fixtures, une
installation neuve n'aurait **jamais** eu de rédacteur, et tous ses articles
seraient partis avec la consigne générique de trois lignes du repli — à vie, sans
un mot.

### Le nom est un verrou / The name is a lock

La migration et les fixtures nomment le rédacteur **« Rédacteur d'article »**, au
caractère près. S'ils divergeaient, le démarrage suivant créerait un **second**
rédacteur garni du texte par défaut qui, naissant `est_par_defaut=True`,
**décocherait celui du mainteneur** — son prompt cesserait de servir sans qu'une
erreur ne le dise. Verrouillé par
`test_la_migration_et_les_fixtures_nomment_le_MEME_analyseur`.

## Ce qui change ailleurs / What else changes

- **Deux résolveurs, une seule règle.** `_prompt_systeme_de_synthese()` et
  `analyseur_de_redaction()` (celui de la provenance) résolvent le même type, et
  le premier **appelle** le second : deux règles séparées auraient un jour fait
  écrire dans la trace un analyseur qui n'a pas servi. Le préambule accepte
  désormais l'analyseur **déjà résolu** — les producteurs le résolvent une fois
  et le donnent au prompt **et** à la trace.
- **Le repli est journalisé.** Sans analyseur utilisable, l'article partait avec
  trois lignes de consigne générique et **rien ne le disait**. Un `logger.warning`
  le dit maintenant.
- **La garde d'utilisabilité couvre le rédacteur** : un `rediger_un_article` sans
  aucune pièce de prompt n'est plus blanchi. ⚠️ Elle alimente un **badge** et un
  sélecteur — elle ne ferme aucun chemin de production.
- **Les deux `<select>` en dur** : celui du gabarit est construit sur les
  `choices` du modèle (un type neuf y apparaît tout seul) ; celui du JS de
  création reçoit la troisième option. `?v=41` → `?v=42`.
- **Le banc `comparer_la_chaine.py` ne réassemble plus le prompt à la main** : il
  appelle `assembler_un_article_sur_des_notes()`. Il annonçait « le prompt de
  production » tout en en gardant sa propre copie, qui n'aurait suivi ni ce
  typage ni les consignes de forme.

### Ce qu'une relecture adverse a corrigé / What an adversarial review fixed

- **La migration copie l'analyseur RÉSOLU, pas celui qui porte le bon nom.**
  Avant ce chantier, le préambule d'un article se résolvait **par type** (actif,
  `synthetiser`, trié `-est_par_defaut, name`). Copier par nom aurait laissé sans
  rien un mainteneur ayant renommé son analyseur, ou en tenant un autre par
  défaut : les fixtures lui auraient posé un rédacteur garni du **texte par
  défaut**, et ses articles auraient cessé d'utiliser son prompt — sans erreur,
  sans repli, sans un mot.
- **Les fixtures se gardent par TYPE, comme la migration.** Un rédacteur créé à
  la main sous un autre nom faisait sauter la migration, mais pas le bloc des
  fixtures : « Rédacteur d'article » serait né quand même, `est_par_defaut=True`,
  et son `save()` aurait **décoché le rédacteur du mainteneur**. Le nom reste un
  verrou partagé ; il ne suffisait pas à lui seul.

## Ce qui N'A PAS été fait, et pourquoi / What was NOT done

- **Le niveau « carnet » du régime de repli.** La note demande l'ordre « geste,
  puis carnet, puis défaut ». **Ni « geste » ni « carnet » n'ont d'écrivain** :
  aucune clé étrangère `Dossier → AnalyseurSyntaxique` n'existe, et aucun des
  trois chemins d'article ne prend d'`analyseur_id`. Les coder aurait fait du
  code mort. Le régime posé est **défaut du type, puis repli journalisé**.
  ⇒ **Décision demandée au mainteneur**, posée en addendum daté.
- **Les bancs LLM réels par type** (`make test-llm`) : **facturés**, non lancés.
  La note demande une mesure avant/après la séparation, et le § 6 de la
  PASSATION rappelle 11 points d'amplitude intra-modèle : rien ne doit être
  conclu sous cette amplitude.
- **Les fixtures étalons par type**, gelées hors base : non écrites.
- **`AnalyseurSyntaxique.save()` filtre toujours sur la valeur NOUVELLE** :
  changer le type d'un analyseur par défaut décoche le défaut du type d'arrivée
  et laisse celui de départ sans aucun défaut. Le comportement voulu est une
  décision, pas une évidence — non touché.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | `TypeAnalyseur.REDIGER_UN_ARTICLE` |
| `hypostasis_extractor/migrations/0038_…` | `AlterField` + `RunPython` qui **copie**, idempotente, avec son inverse |
| `hypostasis_extractor/services/provenance.py` | `analyseur_de_redaction()` résout le type neuf — le résolveur unique |
| `hypostasis_extractor/services/__init__.py` | la garde d'utilisabilité couvre le rédacteur |
| `hypostasis_extractor/views.py` | l'éditeur reçoit `types_d_analyseur` |
| `hypostasis_extractor/templates/…/analyseur_editor.html` | le `<select>` boucle sur les choices |
| `front/static/front/js/hypostasia.js` | troisième option à la création |
| `front/templates/front/base.html` | `?v=42` |
| `front/services/fixtures_analyseurs.py` | `NOM_DE_L_ANALYSEUR_DE_REDACTION`, le 3ᵉ analyseur, sa v1 |
| `front/tasks.py` | `_prompt_systeme_de_synthese(analyseur=None)` + repli journalisé ; `assembler_un_article_sur_des_notes()` |
| `benchmarks/chaine_complete/comparer_la_chaine.py` | appelle la production |
| `front/tests/test_synthese_phase_c.py` | la fixture partagée pose un rédacteur — **une retouche répare douze suites** |
| `hypostasis_extractor/tests/test_le_typage_des_analyseurs.py` | **neuf** — 11 tests |

---

## Comment tester (à la main) / Manual test

### Test 1 — les deux préambules sont séparés, et le vôtre a été copié

```bash
docker exec -w /app hypostasia_web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','hypostasia.settings')
django.setup()
from hypostasis_extractor.models import AnalyseurSyntaxique
for a in AnalyseurSyntaxique.objects.order_by('type_analyseur','name'):
    print(f'[{a.type_analyseur}] {a.name!r} actif={a.is_active} '
          f'defaut={a.est_par_defaut} pieces={a.pieces.count()} '
          f'versions={a.versions.count()}')
"
```

**Attendu** : trois analyseurs, dont `[rediger_un_article] « Rédacteur d'article »`
avec **le même nombre de pièces** que « Synthèse délibérative ». Si vous aviez
édité celle-ci, le rédacteur porte **votre** texte.

### Test 2 — l'écran ne ment plus sur le type

1. `/api/analyseurs/`, ouvrir « Rédacteur d'article ».
2. **Attendu** : le sélecteur « Type » affiche **Rédiger un article** — pas
   « Analyser ». Avant, un type absent de la liste en dur faisait afficher la
   première option, et le premier changement écrasait le vrai type.
3. Créer un analyseur (bouton **+**) : la liste propose bien **trois** types.
   ⚠️ Videz le cache si le JS ne suit pas (`?v=42`).

### Test 3 — le rédacteur vide se signale

1. Créer un analyseur de type « Rédiger un article », sans aucune pièce.
2. **Attendu** : le badge le dit non utilisable. Un article produit dans cet état
   part avec la consigne générique, et le journal du worker le dit —
   `make logs | grep "AUCUN analyseur de rédaction"`.

### Test 4 — la synthèse d'une note n'a pas bougé

1. Ouvrir une note analysée, lancer une synthèse depuis le panneau.
2. **Attendu** : le sélecteur d'analyseur de synthèse propose « Synthèse
   délibérative » — **jamais** le rédacteur — et la synthèse se produit. C'est
   exactement ce qu'une bascule aurait cassé.
