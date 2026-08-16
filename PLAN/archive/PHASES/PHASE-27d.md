# PHASE-27d — Fil de réflexion (source → extraction → commentaires → synthèse)

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-27c

---

## 1. Contexte

Les SourceLinks existent et sont peuplés (manuellement en 27c, automatiquement
en 28). On peut maintenant répondre à la question fondamentale du produit :
**d'où vient ce paragraphe ?**

Le fil de réflexion est la vue qui matérialise la traçabilité totale. Pour
n'importe quel passage de n'importe quelle version, on peut naviguer toute la
chaîne depuis l'origine : texte source → extraction → commentaires du débat →
synthèse → texte final.

C'est la vue qui distingue Hypostasia d'un Google Docs + ChatGPT.

## 2. Objectifs précis

### 2.1 — Action "Voir le fil" sur un passage annoté

- Bouton contextuel sur les passages qui ont des SourceLinks
- URL : `/lire/{pk}/fil/?start={start_char}&end={end_char}`
- Le serveur remonte la chaîne de SourceLinks pour le passage sélectionné
- Retourne un partial HTMX qui remplace #zone-lecture (mode pleine page)
- Push-url + F5 support

### 2.2 — Algorithme de remontée de chaîne

```
Entrée : page_cible, start_char, end_char
1. Trouver les SourceLinks pour cette plage de caractères
2. Pour chaque SourceLink trouvé :
   a. Si page_source existe :
      - Extraire le passage source (start_char_source → end_char_source)
      - Chercher récursivement les SourceLinks de page_source (si v3→v2→v1)
   b. Si extraction_source existe :
      - Récupérer l'extraction (titre, classe, texte, statut_debat)
   c. Si commentaires_source existent :
      - Récupérer les commentaires avec auteur et date
3. Construire la timeline ordonnée chronologiquement
```

Gestion du cas multi-niveaux : si v3 pointe vers v2 qui pointe vers v1,
le fil affiche les 3 niveaux. Limite : 10 niveaux max pour éviter les boucles.

### 2.3 — Template `fil_reflexion.html`

Timeline verticale avec la charte typographique (3 polices = 3 provenances) :

| Élément | Classe CSS | Police | Signification |
|---------|-----------|--------|---------------|
| Texte source (citation) | `.typo-citation` | Lora italique | Un humain a écrit ça |
| Commentaires lecteur | `.typo-lecteur-nom` + `.typo-lecteur-corps` | Srisakdi bleu | Quelqu'un réagit |
| Synthèse/extraction IA | `.typo-machine` | B612 Mono | La machine a produit ça |
| Labels système | `.typo-label` | B612 gras | Metadata (statuts, dates) |

Structure de la timeline :
```
┌─ V1 — Texte original ──────────────────────┐
│  "La loi d'Amara stipule que..."           │  ← .typo-citation
│  📄 source : passage p.42-60               │
└─────────────────────────────────────────────┘
         │
┌─ Extraction #42 ───────────────────────────┐
│  LOI — "La loi d'Amara..."                 │  ← .typo-machine
│  Statut : CONSENSUEL ⚫                     │
│  [Voir dans le texte →]                    │
└─────────────────────────────────────────────┘
         │
┌─ Commentaires ──────────────────────────────┐
│  Jonas (3 mars) :                           │  ← .typo-lecteur
│  "D'accord, mais nuancer avec la           │
│  question de la régulation."               │
│                                             │
│  Marie (5 mars) :                           │
│  "D'accord. Ajouter 'sous réserve'."       │
│  [Voir le commentaire →]                   │
└─────────────────────────────────────────────┘
         │
┌─ V2 — Post-débat ──────────────────────────┐
│  "L'IA est un outil essentiel pour         │  ← .typo-citation
│  l'éducation, sous réserve de régulation." │
│  📎 type: modifié                           │
│  justification: "Nuancé suite au débat"    │
└─────────────────────────────────────────────┘
```

### 2.4 — Chaque élément cliquable

- Clic sur un passage source → navigue vers `/lire/{pk_source}/` avec scroll
  vers la position du passage
- Clic sur une extraction → ouvre la carte inline dans le drawer
- Clic sur un commentaire → ouvre le drawer avec le commentaire scrollé

### 2.5 — Export Markdown du fil

- Bouton "Exporter en Markdown" en haut du fil
- Génère un fichier `.md` avec la chaîne complète
- Format :
  ```markdown
  # Fil de réflexion — "passage ciblé"

  ## V1 — Texte original
  > La loi d'Amara stipule que…

  ## Extraction #42 — LOI
  Statut : CONSENSUEL
  > La loi d'Amara…

  ## Commentaires
  **Jonas** (3 mars) : D'accord, mais nuancer…
  **Marie** (5 mars) : D'accord. Ajouter…

  ## V2 — Post-débat
  > L'IA est un outil essentiel… sous réserve de régulation.
  Type de lien : modifié
  ```

## 3. Fichiers à modifier

| Fichier | Changement |
|---------|-----------|
| `front/views.py` | +action `fil_reflexion()` sur LectureViewSet, +`_remonter_chaine_source()` |
| `front/templates/front/includes/fil_reflexion.html` | Nouveau — timeline verticale |
| `front/templates/front/includes/diff_versions_pages.html` | +bouton "Voir le fil" sur les zones avec SourceLinks |
| `front/templates/front/base.html` | +elif `fil_reflexion_preloaded` |
| `front/tests/test_phase27d.py` | Tests unitaires (remontée chaîne, export Markdown) |
| `front/tests/e2e/test_20_tracabilite.py` | +tests E2E fil de réflexion |

## 4. Critères de validation

- [ ] `uv run python manage.py check` → 0 erreur
- [ ] `_remonter_chaine_source()` remonte correctement une chaîne v3→v2→v1
- [ ] `_remonter_chaine_source()` gère le cas sans SourceLink (retourne timeline vide)
- [ ] `_remonter_chaine_source()` s'arrête après 10 niveaux max (anti-boucle)
- [ ] Le fil affiche les 4 types d'éléments (source, extraction, commentaires, synthèse)
- [ ] Chaque élément est cliquable et navigue vers la bonne cible
- [ ] L'export Markdown génère un fichier correct
- [ ] F5 sur `/lire/{pk}/fil/?start=0&end=100` retourne la page complète
- [ ] La charte typographique est respectée (3 polices = 3 provenances)

## 5. Vérification navigateur

1. Avoir un document avec V1 (original) + extractions + commentaires + V2 (restitution)
2. Ouvrir le diff V1↔V2 (PHASE-27b)
3. Cliquer "Voir le fil" sur une zone modifiée ayant un SourceLink (PHASE-27c)
4. **Attendu** : timeline verticale complète :
   - Passage original (V1) en Lora italique
   - Extraction en B612 Mono
   - Commentaires en Srisakdi bleu
   - Passage final (V2) en Lora italique
5. Cliquer sur l'extraction → ouvre la carte dans le drawer
6. Cliquer "Exporter en Markdown" → fichier téléchargé
7. F5 → page complète avec le fil

## 6. Tests prevus

**Module :** `front.tests.test_phase27d` | **Statut : A ECRIRE**

| Classe | Test | Quoi |
|--------|------|------|
| `RemonterChaineTest` | `test_remontee_v2_vers_v1` | Remonte v2→v1 correctement |
| `RemonterChaineTest` | `test_remontee_v3_vers_v2_vers_v1` | Remonte v3→v2→v1 multi-niveaux |
| `RemonterChaineTest` | `test_sans_source_link_retourne_vide` | Timeline vide si pas de SourceLink |
| `RemonterChaineTest` | `test_limite_10_niveaux` | S'arrete apres 10 niveaux (anti-boucle) |
| `RemonterChaineTest` | `test_inclut_extractions` | Les extractions sont presentes dans le fil |
| `RemonterChaineTest` | `test_inclut_commentaires` | Les commentaires sont presents dans le fil |
| `FilReflexionActionTest` | `test_fil_retourne_200_htmx` | L'action retourne le partial HTMX |
| `FilReflexionActionTest` | `test_fil_f5_page_complete` | F5 retourne la page complete |
| `FilReflexionActionTest` | `test_fil_sans_start_end_refuse` | Parametres start/end obligatoires |
| `ExportFilMarkdownTest` | `test_export_genere_markdown` | Le fichier Markdown est correct |
| `ExportFilMarkdownTest` | `test_export_contient_citations_et_commentaires` | Les 4 types d'elements presents |

**E2E :** `front.tests.e2e.test_20_tracabilite` — tests prevus :
- `test_bouton_voir_fil_visible_sur_zone_avec_source`
- `test_fil_affiche_timeline_complete`
- `test_clic_extraction_ouvre_drawer`
- `test_export_markdown_telecharge_fichier`
- `test_f5_fil_affiche_page_complete`

## 7. Notes pour les phases suivantes

- PHASE-28 étendra le fil pour montrer le wizard de synthèse (étape par étape)
- PHASE-28 ajoutera les indicateurs ✎ / 🤖 / 🤖⚠️ dans le fil
- Le fil sera aussi accessible depuis la vue comparaison côté-à-côté (PHASE-28, Étape 5.8)
