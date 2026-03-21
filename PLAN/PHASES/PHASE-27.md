# PHASE-27 — Traçabilité : SourceLink + historique + diff

**Complexite** : L | **Mode** : Plan then normal | **Prerequis** : PHASE-25

---

## 1. Contexte

Le cycle Lecture → Extraction → Commentaire → Synthèse → Nouvelle version existe
en parties isolées mais il manque le lien structurel entre elles. On ne peut pas
remonter le fil d'un paragraphe de la version finale jusqu'au texte original.

Cette phase couvre les Étapes 5.1 à 5.5 du PLAN.md (Phase 5 — Édition collaborative
et fil de traçabilité). Elle est découpée en **5 sous-phases** livrables indépendamment.

Les SourceLinks IA (parsing automatique des références LLM) et le wizard de synthèse
sont reportés à PHASE-28.

## 2. Découpage en sous-phases

```
PHASE-27a (FAIT) — Modèles + PageEdit hooks + historique
    ├── PHASE-27b — Diff side-by-side entre versions
    │       └── (réutilise _diff_inline_mots existant)
    ├── PHASE-27c — SourceLinks manuels
    │       └── PHASE-27d — Fil de réflexion
    │               └── (nécessite des SourceLinks peuplés)
    └── PHASE-27e — Verrous d'édition optimistes
            └── (indépendant de 27c/27d)
```

| Sous-phase | Titre | Taille | Dépend de | Étape PLAN |
|------------|-------|--------|-----------|------------|
| [27a](PHASE-27a.md) | Modèles + PageEdit logging + vue historique | M | PHASE-25 | 5.1 + 5.2 |
| [27b](PHASE-27b.md) | Diff side-by-side entre versions de pages | M | 27a | 5.3 (partiel) |
| [27c](PHASE-27c.md) | SourceLinks manuels + association source-cible | M | 27a + 27b | 5.1 (usage) |
| [27d](PHASE-27d.md) | Fil de réflexion (timeline de provenance) | M | 27c | 5.4 |
| [27e](PHASE-27e.md) | Verrous d'édition optimistes | S | 27a | 5.5 |

### Ce qui reste en PHASE-28

| Étape PLAN | Contenu | Pourquoi pas ici |
|------------|---------|-----------------|
| 5.1 (IA) | SourceLinks IA : parsing `[src:extraction-42]` dans les réponses LLM | Nécessite le wizard (5.6) |
| 5.3 (provenance) | Superposition SourceLinks sur le diff + indicateurs ✎/🤖/🤖⚠️ | Nécessite 27c peuplé + indicateurs de provenance rédaction |
| 5.6 | Wizard synthèse en 5 étapes | Phase majeure à part entière |
| 5.7 | Export PDF/HTML | Après le wizard |
| 5.8 | Comparaison côté-à-côté avec provenance explicite + compteur sourçage | Extension de 27b + 27c + wizard |

## 3. Mapping Étapes PLAN → Sous-phases

| Étape PLAN.md | Couvert par | Notes |
|---------------|-------------|-------|
| **5.1** Modèle SourceLink | **27a** (schéma) + **27c** (peuplement manuel) | Le peuplement IA = PHASE-28 |
| **5.2** Historique modifications | **27a** (complet) | PageEdit + hooks + vue timeline |
| **5.3** Diff versions | **27b** (diff technique) | La superposition SourceLinks = PHASE-28 |
| **5.4** Fil de réflexion | **27d** (complet) | Timeline source→extraction→commentaires→synthèse |
| **5.5** Verrous d'édition | **27e** (complet) | Verrou optimiste MVP |

## 4. Critères de validation globaux

Quand les 5 sous-phases sont terminées :
- [ ] Le modèle SourceLink stocke les liens entre passages, extractions et commentaires
- [ ] L'historique des modifications affiche une timeline par page
- [ ] Le diff side-by-side entre deux versions fonctionne avec coloration ajouts/suppressions
- [ ] Les SourceLinks manuels permettent de lier une zone modifiée à sa source
- [ ] Le fil de réflexion affiche la chaîne : source → extraction → commentaires → synthèse
- [ ] Chaque élément du fil est cliquable et navigue vers l'élément concerné
- [ ] Le verrou optimiste alerte si une modification concurrente est détectée
- [ ] `uv run python manage.py check` passe

## 5. Vérification navigateur (scénario complet)

1. **Avoir au moins 2 versions d'un document** (original + restitution)
2. **Modifier le titre** → "Historique" affiche l'entrée avec diff rouge/vert
3. **Ouvrir le diff** entre V1 et V2 → vue 2 colonnes avec coloration
4. **Lier un passage** modifié à une extraction source → badge 📎 apparaît
5. **Voir le fil de réflexion** d'un passage lié → timeline complète navigable
6. **Exporter le fil en Markdown** → fichier téléchargé correct
7. **Tester le verrou** : éditer dans 2 onglets → alerte de conflit
