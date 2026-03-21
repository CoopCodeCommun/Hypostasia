# PHASE-11 — Charte visuelle : typographie + variables CSS

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-02

---

## 1. Contexte

Le front utilise actuellement Inter + Lora (polices generiques). La distinction typographique humain/machine/lecteur est le signal UX central du produit : un utilisateur doit pouvoir scanner une carte et savoir instantanement ce qui vient d'un LLM, ce qui vient d'un texte source, et ce qui vient d'un lecteur humain. Trois polices, trois provenances, zero ambiguite. Cette phase met en place le systeme typographique complet et les variables CSS pour toutes les couleurs semantiques (prerequis pour le dark mode futur).

## 2. Prerequis

- **PHASE-02** — Les assets statiques (fonts, CSS) doivent etre en place pour ajouter les nouvelles polices et les classes CSS.

## 3. Objectifs precis

### Typographie

- [ ] Charger B612, B612 Mono et Srisakdi dans `base.html` via fichiers locaux (installes en PHASE-02)
- [ ] Creer 5 classes CSS utilitaires :
  - `.typo-hypostase` : B612 700, 12px, uppercase, letter-spacing 0.05em (labels, tags d'hypostase)
  - `.typo-machine` : B612 Mono, 14px, couleur `#475569` (resume IA, synthese — signal "la machine a dit ca")
  - `.typo-citation` : Lora italique, 16px, couleur `#1e293b` (citations humaines entre `[...]` — serif chaleureuse)
  - `.typo-lecteur-nom` : Srisakdi, 20px, couleur `#0056D6` (nom/signature du lecteur)
  - `.typo-lecteur-corps` : Srisakdi, 16px, couleur `#0056D6` (corps du commentaire, taille reduite pour fils longs)
- [ ] Conserver Inter pour l'UI generale et Lora pour la zone de lecture

### Variables CSS couleurs semantiques

- [ ] Definir les variables de surface dans `:root` :
  - `--surface-primary: #ffffff`, `--surface-secondary: #f8fafc`, `--surface-tertiary: #f1f5f9`
- [ ] Definir les variables de texte :
  - `--text-primary: #0f172a`, `--text-secondary: #475569`, `--text-tertiary: #94a3b8`
- [ ] Definir les variables de bordure :
  - `--border-default: #e2e8f0`, `--border-strong: #cbd5e1`
- [ ] Definir les variables pour les 4 statuts de debat (texte + fond + accent) :
  - Consensuel : `--statut-consensuel-text: #15803d`, `--statut-consensuel-bg: #f0fdf4`, `--statut-consensuel-accent: #429900`
  - Discutable : `--statut-discutable-text: #B61601`, `--statut-discutable-bg: #fef2f2`, `--statut-discutable-accent: #B61601`
  - Discute : `--statut-discute-text: #b45309`, `--statut-discute-bg: #fffbeb`, `--statut-discute-accent: #D97706`
  - Controverse : `--statut-controverse-text: #C2410C`, `--statut-controverse-bg: #FFF4ED`, `--statut-controverse-accent: #FF4000`
- [ ] Definir les variables pour les 8 familles d'hypostases (fond + texte) :
  - `--hypostase-epistemique-bg: #e0e7ff`, `--hypostase-epistemique-text: #4338ca` (indigo)
  - `--hypostase-empirique-bg: #d1fae5`, `--hypostase-empirique-text: #047857` (emerald)
  - `--hypostase-speculatif-bg: #fef3c7`, `--hypostase-speculatif-text: #b45309` (amber)
  - `--hypostase-structurel-bg: #e2e8f0`, `--hypostase-structurel-text: #475569` (slate)
  - `--hypostase-normatif-bg: #ede9fe`, `--hypostase-normatif-text: #6d28d9` (violet)
  - `--hypostase-problematique-bg: #fee2e2`, `--hypostase-problematique-text: #b91c1c` (red)
  - `--hypostase-mode-bg: #cffafe`, `--hypostase-mode-text: #0e7490` (cyan)
  - `--hypostase-objet-bg: #f1f5f9`, `--hypostase-objet-text: #64748b` (gray)
- [ ] Definir les variables pour les 3 provenances typographiques :
  - `--typo-machine-color: #475569`, `--typo-citation-color: #1e293b`, `--typo-lecteur-color: #0056D6`
- [ ] Ne PAS implementer le theme dark — juste s'assurer que toutes les couleurs passent par des variables

## 4. Fichiers a modifier

- `front/templates/front/base.html` — ajout des `@font-face` pour B612, B612 Mono, Srisakdi via fichiers locaux (installes en PHASE-02)
- `front/static/front/css/hypostasia.css` — ajout des 5 classes typographiques, toutes les variables CSS dans `:root`

## 5. Criteres de validation

- [ ] Les 4 polices (Lora, B612, B612 Mono, Srisakdi) se chargent correctement (onglet Network)
- [ ] Les 5 classes `.typo-*` sont definies et applicables
- [ ] Toutes les couleurs semantiques sont en variables CSS dans `:root` (aucune couleur codee en dur pour les surfaces, textes, bordures, statuts, hypostases)
- [ ] Les variables sont utilisees dans le CSS existant (remplacement progressif des valeurs hex en dur)
- [ ] L'interface existante n'est pas visuellement cassee (les classes ne sont pas encore appliquees aux templates)
- [ ] Le futur dark mode ne necessiterait qu'un bloc `@media (prefers-color-scheme: dark)` pour surcharger les variables

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir un document** : verifier visuellement les 4 polices
   - **Attendu** : texte source/citations en Lora italique, labels d'hypostases en B612 gras, texte machine (resume IA) en B612 Mono, commentaires lecteur en Srisakdi
2. **Ouvrir DevTools > Elements** : inspecter l'element `<html>`
   - **Attendu** : les CSS custom properties sont presentes (`--color-consensuel`, `--color-controverse`, `--font-source`, `--font-machine`, etc.)
3. **Changer une variable dans DevTools** : modifier une variable CSS dans le panneau Styles
   - **Attendu** : la couleur/police change partout d'un coup (preuve que tout passe par les variables)

## 6. Extraits du PLAN.md

> **Actions typographie** :
> - [ ] Charger B612, B612 Mono et Srisakdi dans `base.html` via fichiers locaux (installes en PHASE-02)
> - [ ] Creer 5 classes CSS utilitaires :
>   ```css
>   .typo-hypostase { font-family: 'B612', sans-serif; font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
>   .typo-machine   { font-family: 'B612 Mono', monospace; font-size: 14px; color: #475569; }
>   .typo-citation  { font-family: 'Lora', Georgia, serif; font-style: italic; font-size: 16px; color: #1e293b; }
>   .typo-lecteur-nom  { font-family: 'Srisakdi', cursive; font-size: 20px; color: #0056D6; }
>   .typo-lecteur-corps { font-family: 'Srisakdi', cursive; font-size: 16px; color: #0056D6; }
>   ```
> - [ ] Conserver Inter pour l'UI generale et Lora pour la zone de lecture
>
> **Charte typographique consolidee** :
>
> | Element | Police | Style | Taille | Couleur | Justification |
> |---------|--------|-------|--------|---------|---------------|
> | Labels / statuts | B612 Mono | gras | 12pt | selon statut | Aviation font = lisible en petit |
> | Resume IA | B612 Mono | courant | 14pt | neutre `#475569` | Mono = signal "la machine a dit ca" |
> | Citations humaines | Lora | italique | 16-18pt | `#1e293b` | Serif chaleureuse = signal "un humain a ecrit ca" |
> | Interventions lecteur (nom) | Srisakdi | regular | 20pt | bleu `#0056D6` | Cursive = signal "quelqu'un reagit" |
> | Interventions lecteur (corps) | Srisakdi | regular | 16pt | bleu `#0056D6` | Taille reduite pour fils longs |
>
> **Actions compatibilite dark mode** :
> - [ ] Structurer TOUTES les couleurs en variables CSS dans `:root` :
>   ```css
>   --surface-primary: #ffffff;
>   --surface-secondary: #f8fafc;
>   --surface-tertiary: #f1f5f9;
>   --text-primary: #0f172a;
>   --text-secondary: #475569;
>   --text-tertiary: #94a3b8;
>   --border-default: #e2e8f0;
>   --border-strong: #cbd5e1;
>   ```
> - [ ] Les 8 familles d'hypostases utilisent des variables (ex: `--hypostase-epistemique-bg`)
> - [ ] Les 4 statuts de debat utilisent des variables
> - [ ] Les 3 provenances typographiques utilisent des variables couleur
> - [ ] Ne PAS implementer le theme dark maintenant — juste s'assurer que toutes les couleurs passent par des variables
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
