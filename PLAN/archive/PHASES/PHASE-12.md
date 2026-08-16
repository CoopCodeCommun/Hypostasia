# PHASE-12 — Charte visuelle : cartes extraction + statuts

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-11, PHASE-09

---

## 1. Contexte

Les cartes d'extraction n'ont pas de distinction visuelle entre texte machine (IA) et texte humain (citation). Les hypostases sont affichees en pastilles indigo uniformes sans couleur par famille. Cette phase applique le systeme typographique et les couleurs definis en PHASE-11 aux cartes d'extraction et aux statuts de debat. Apres cette phase, un utilisateur peut scanner une carte et savoir instantanement ce qui vient d'un LLM, ce qui vient d'un texte source, et ce qui vient d'un lecteur humain.

## 2. Prerequis

- **PHASE-11** — Les classes typographiques (`.typo-*`) et les variables CSS doivent etre en place.
- **PHASE-09** — Les pastilles de marge et cartes inline doivent exister pour y appliquer la charte.

## 3. Objectifs precis

### Application aux cartes d'extraction

- [ ] `attr_0` (hypostase) : appliquer `.typo-hypostase` + couleur par famille (B612 gras uppercase, coloree selon le tableau des 8 familles)
- [ ] `attr_1` (resume IA) : appliquer `.typo-machine` (B612 Mono 14px, texte neutre) — le mono signale visuellement "c'est la machine qui parle"
- [ ] `text` (citation source) : appliquer `.typo-citation` (Lora italique 16px) + prefixer `[` et suffixer `]` — la serif chaleureuse signale "c'est un humain qui a ecrit ca"
- [ ] `attr_2` (statut de debat) : appliquer couleurs charte avec distinction DISCUTE `#D97706` / DISCUTABLE `#B61601` + icones Unicode (⚫ ▶ ▷ !)
- [ ] `attr_3` (hashtags) : ajouter `data-hashtag` pour rendu cliquable futur

### Mapping hypostase → couleur

- [ ] Implementer le mapping hypostase → couleur via un template tag dans `hypostasis_extractor/templatetags/extractor_tags.py`
- [ ] Chaque pastille d'hypostase dans le header de carte utilise le fond et texte de sa famille (variables CSS)

### Application aux interventions lecteur

- [ ] Nom de l'auteur du commentaire : `.typo-lecteur-nom` (Srisakdi 20pt bleu)
- [ ] Corps du commentaire : `.typo-lecteur-corps` (Srisakdi 16pt bleu)
- [ ] Appliquer dans `vue_commentaires.html` et `vue_questionnaire.html`

### Structure cible d'une carte

1. **Header** : hypostase(s) typee(s) en B612 gras uppercase, coloree par famille
2. **Corps** : resume IA en B612 Mono 14pt + citation source en Lora italique 16pt entre `[...]`
3. **Footer** : badge statut colore (avec distinction DISCUTE/DISCUTABLE) + hashtags

## 4. Fichiers a modifier

- `hypostasis_extractor/includes/_card_body.html` — application des classes typographiques aux differentes zones de la carte
- `hypostasis_extractor/templatetags/extractor_tags.py` — template tag pour le mapping hypostase → couleur de famille
- `front/templates/front/includes/vue_commentaires.html` — application `.typo-lecteur-nom` et `.typo-lecteur-corps`
- `front/templates/front/includes/vue_questionnaire.html` — idem
- `front/static/front/css/hypostasia.css` — ajustements CSS pour les cartes si necessaire

## 5. Criteres de validation

- [ ] Le header de carte affiche l'hypostase en B612 gras uppercase avec la couleur de sa famille
- [ ] Le resume IA est en B612 Mono 14px gris neutre
- [ ] La citation source est en Lora italique 16px entre crochets `[...]`
- [ ] Le statut DISCUTE est en ambre fonce (`#b45309`) avec icone ▷, visuellement distinct de DISCUTABLE en rouge (`#B61601`) avec icone ▶
- [ ] Les commentaires de lecteurs sont en Srisakdi bleu (nom 20pt, corps 16pt)
- [ ] Le template tag `extractor_tags.py` mappe correctement chaque hypostase a sa famille de couleur
- [ ] Les 3 provenances typographiques sont immediatement distinguables visuellement (mono = machine, serif = humain, cursive = lecteur)

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir un document avec extractions et deplier une carte inline** : cliquer sur une pastille de marge
   - **Attendu** : le label d'hypostase est en B612 gras avec la couleur de sa famille
   - **Attendu** : le resume IA est en B612 Mono (texte "machine")
   - **Attendu** : la citation est en Lora italique entre guillemets francais
   - **Attendu** : les commentaires sont en Srisakdi
2. **Verifier les badges de statut** : inspecter les statuts sur les cartes
   - **Attendu** : chaque statut a sa couleur distincte (vert, rouge, ambre, orange)
3. **Verifier les couleurs des 8 familles d'hypostases** : comparer les labels d'hypostases
   - **Attendu** : chaque type a une teinte distincte (indigo epistemique, emerald empirique, amber speculatif, etc.)

## 6. Extraits du PLAN.md

> **Actions cartes d'extraction** (`_card_body.html`) :
> - [ ] `attr_0` (hypostase) : appliquer `.typo-hypostase` + couleur par famille
> - [ ] `attr_1` (resume IA) : appliquer `.typo-machine` (B612 Mono 14px, texte neutre)
> - [ ] `text` (citation source) : appliquer `.typo-citation` (Lora italique 16px) + prefixer `[` et suffixer `]`
> - [ ] `attr_2` (statut de debat) : appliquer couleurs charte ajustee + icones Unicode, avec distinction DISCUTE / DISCUTABLE
> - [ ] `attr_3` (hashtags) : ajouter `data-hashtag` pour rendu cliquable futur
>
> **Couleurs par famille d'hypostase** :
>
> | Famille | Hypostases | Hex fond | Hex texte |
> |---------|-----------|----------|-----------|
> | Epistemique | classification, axiome, theorie, definition, formalisme | `#e0e7ff` | `#4338ca` |
> | Empirique | phenomene, evenement, donnee, variable, indice | `#d1fae5` | `#047857` |
> | Speculatif | hypothese, conjecture, approximation | `#fef3c7` | `#b45309` |
> | Structurel | structure, invariant, dimension, domaine | `#e2e8f0` | `#475569` |
> | Normatif | loi, principe, valeur, croyance | `#ede9fe` | `#6d28d9` |
> | Problematique | aporie, paradoxe, probleme | `#fee2e2` | `#b91c1c` |
> | Mode/Variation | mode, variation, variance, paradigme | `#cffafe` | `#0e7490` |
> | Objet/Methode | objet, methode | `#f1f5f9` | `#64748b` |
>
> - [ ] Implementer le mapping hypostase → couleur via un template tag dans `extractor_tags.py`
> - [ ] Chaque pastille d'hypostase dans le header de carte utilise le fond et texte de sa famille
>
> **Actions interventions lecteur** :
> - [ ] Nom de l'auteur : `.typo-lecteur-nom` (Srisakdi 20pt bleu)
> - [ ] Corps du commentaire : `.typo-lecteur-corps` (Srisakdi 16pt bleu)
> - [ ] Distinction visuelle a 3 niveaux :
>   - Mono neutre (B612 Mono) = la machine a synthetise
>   - Serif chaleureuse (Lora italique) = un humain a ecrit le texte source
>   - Cursive bleue (Srisakdi) = un lecteur reagit maintenant
>
> **Structure cible d'une carte** (mockup Yves, ajuste) :
> 1. Header : hypostase(s) en B612 gras uppercase, coloree par famille
> 2. Corps : resume IA en B612 Mono 14pt + citation source en Lora italique 16pt entre `[...]`
> 3. Footer : badge statut colore (distinction DISCUTE/DISCUTABLE) + hashtags
