# CHANGELOG/ — un fichier par chantier

> Journal des modifications. Format bilingue FR/EN.
> Remplace l'ancien `CHANGELOG.md` unique, découpé le 16 août 2026.

Chaque chantier a **un fichier**, nommé `AAAA-MM-JJ-slug.md`. Il fusionne deux
besoins autrefois séparés : l'entrée de journal **et** la fiche « comment
tester à la main » (l'ancien dossier `A TESTER et DOCUMENTER/`). Une seule
écriture, deux lecteurs.

C'est le format du skill **`djc`**, section « CHANGELOG Workflow ».

## Le format

```markdown
# Titre du chantier

**Date :** 2026-08-15
**Migration :** Non        ← si Oui : le nom de la migration est dans le corps

<le résumé : quoi, pourquoi, fichiers modifiés>

---

## Comment tester (à la main) / Manual test

<les scénarios de vérification humaine, les requêtes de contrôle en base>
```

**Le `---` sépare deux publics.** Au-dessus, ce qui a changé et pourquoi — la
lecture chronologique du projet. En dessous, comment le vérifier soi-même à
l'écran. Un fichier sans `---` est un chantier pour lequel aucune fiche de
test manuel n'a été écrite ; les tests automatiques en tiennent lieu.

## Les règles

1. **Un fichier par chantier, créé en même temps que le code** — pas après.
2. **Un chantier qui s'étale sur plusieurs jours : on édite le même fichier.**
   On ne le renomme pas, on ne le recrée pas. Sa date reste celle du premier
   jour ; la ligne `**Date :**` porte alors un intervalle (`2026-08-09 →
   2026-08-10`).
3. **Le flag migration est toujours renseigné** (Oui/Non).
4. **Un refactoring interne sans effet visible mérite son fichier**, avec la
   mention « Refactoring interne / Internal refactoring ».
5. **Pas de gros fichier unique, pas de dossier `TEST_OK`.** La vue
   chronologique, c'est le préfixe date des noms de fichiers plus `git log`.

## Trouver quelque chose

```bash
# Les chantiers d'un mois
ls CHANGELOG/2026-08-*

# Où une chose a-t-elle changé ?
rg "ingestion_etat" CHANGELOG/

# Les chantiers qui ont porté une migration
rg -l "^\*\*Migration :\*\* Oui" CHANGELOG/
```

## Les chantiers regroupés

Trois fichiers portent plusieurs étapes d'un même chantier, parce qu'une
seule fiche de test les couvrait toutes :

| Fichier | Étapes réunies |
|---|---|
| `2026-08-05-ancrage-par-element-phases-b-c-e-f-g.md` | phases B, C, E, F, G du moteur d'ancrage |
| `2026-08-09-branchement-moteur-ancrage-br-a-f.md` | BR-A à BR-F du branchement |
| `2026-08-10-usage-moteur-element-u1-u4-securite-mesure-d3.md` | U1, U2, U3, U4, sécurité, mesure D3 |

Chaque étape y garde son propre titre daté, dans l'ordre où elle a été
réalisée — pas dans l'ordre antichronologique du journal.

## Ce qui n'est pas ici

- Les **défauts connus non traités** : `CHANGELOG/DEFAUTS-DIFFERES.md`
- La **carte du dépôt et ses invariants** : `AGENTS.md` à la racine
- L'**état cible d'un domaine** : `PLAN/specs/`
- Les **spécifications** : `PLAN/specs/`
