# Cahier des charges de la phase F (UI carnet) — écarts phase E ↔ étalon

**Source** : rapport de l'agent de comparaison structurelle (Opus, 8 août
2026) entre la phase E livrée et l'étalon `tmp/maquettes/corpus.html`.
Chaque point porte la référence maquette. Les divergences spec/étalon
(section C) sont à arbitrer par le propriétaire avant de coder.

## A. Déjà conforme en phase E (à ne pas casser)

- Sémantique ET/OU des facettes (`views_corpus.py`, identique à
  `passeLesFiltres()` corpus.html:1032-1039) — groupement par PK d'axe,
  meilleur que l'étalon qui clé sur le nom.
- Catégories portées par la relation, partout.
- Épinglage et tri par le Meta des appartenances (= `notesFiltrees()`).
- AllowAny + contrôle par objet ; HTML seulement ; retirer ≠ supprimer.
- `aria-live="polite"` sur la zone de notes (ajout correct absent de l'étalon).

## B. À combler en phase F

### B.0 — BLOQUANT : intégration au gabarit du site
Les écrans E sont autonomes, sans htmx ni CSS → les `hx-*` sont inertes
dans un navigateur. `front/templates/front/base.html` charge tout (htmx:10,
tailwind:8) mais n'a AUCUN `{% block %}` : cascade d'`{% include %}`
(:281-301). À trancher d'abord : blocks dans base.html, ou branche dans la
cascade.

### B.1 — En-tête du carnet
- Meta « N notes · N axes de classement · N catégories » (corpus.html:1856-1858),
  tout dérivé, jamais tapé.
- Visibilité : icône + mot, span dédié (corpus.html:1859-1861).
- Bloc guide de rédaction (corpus.html:1862-1866) → champ à créer, cf. C.1.
- Compteur (N) dans l'onglet Notes (corpus.html:1868).

### B.2 — Chips de facettes
1. Forme : étalon = puces `aria-pressed` toujours visibles dans une boîte
   `.axe` (corpus.html:1101-1127) ; spec § 8.2 = « menu déroulant » ;
   réel = details/summary. **Arbitrage C.2 requis.**
2. Compteur par axe « Thème (3) » (corpus.html:1109-1110, justifié :728-731).
3. Couleur des catégories : `--teinte` (corpus.html:1114, :211), champ
   `CategorieDossier.couleur`, repli palette Wong, nom toujours écrit.
4. État vide « Ce carnet n'a pas encore d'axe » (corpus.html:1104-1106).
5. **Restauration depuis l'URL** : `retrieve()` doit lire
   `request.GET.getlist("categorie")` et pré-cocher — sinon hx-push-url
   ne sert à rien (défaut réel actuel, views_corpus.py:143).

### B.3 — Résumé des filtres (absent du réel)
« X sur Y notes » + phrase littérale `Type : A OU B ET Thème : C`
(texteDesFiltres, corpus.html:1129-1150) + bouton « Tout afficher ».
À rendre côté serveur DANS le partial notes_du_carnet.html.

### B.4 — Ligne de note
Rang (numéro d'ordre quand pas épinglée, corpus.html:1161-1162), source
(fichier · pages · poids, :1164), « N extractions » (:1165), « dans N
carnets » si N>1 (:1166), étiquettes teintées, titre non tronqué en liste.
Comptes par `annotate()` en une requête (verrou N+1 § 5.3).

### B.5 — Ordre narratif (monter/descendre)
- Boutons ▲▼ absents ; § 8.3 exige l'alternative clavier.
- Contrat : `reordonner` prend la liste complète — HTMX doit émettre les
  `page_ids` de tout le DOM (`hx-include`), l'ordre du DOM = ordre voulu.
- `reordonner` doit re-rendre AVEC les filtres actifs (défaut actuel :
  re-rend tout, views_corpus.py:244).
- L'étalon permute les notes VISIBLES adjacentes et transfère l'épingle
  au besoin (corpus.html:1188-1194) ; toasts « Ordre modifié » / « Déjà à
  l'extrémité » (:1191, :1196), au minimum role="status".

### B.6 — Cible HTMX d'epingler/categoriser depuis l'écran carnet
Les deux rendent le bloc de l'écran note (carnets_de_la_note.html) —
hors sujet dans #corpus-notes. Solution : paramètre de contexte ou
hx-swap-oob.

### B.7 — Onglets (tablist accessible)
Structure role=tablist + flèches clavier + compteurs. Panneaux Wikis /
Synthèses : dépendent de SPEC-synthese phase H — poser la structure,
panneaux vides. Sélection des preuves : SPEC-selection § 2 dépend de
CETTE phase F. Alignement : scoper sur les notes filtrées.

### B.8 — Fil d'Ariane à bascule
corpus.html:530-541 + 1056-1083 : chevron → menu des carnets contenant
la note, aria-haspopup/expanded/current, compte de notes par carnet.
Piège : pas d'overflow:hidden sur le parent (corpus.html:131-133).
(Décrit dans PRESENTATION-V3 § 5.5 ; absent de SPEC-corpus § 8 — cf. C.3.)

### B.9 — Liste des carnets
« N notes · N axes » par annotate ; wikis/synthèses viendront avec
SPEC-synthese.

### B.10 — Accessibilité
- Corriger : aria-label sur span non interactif (notes_du_carnet.html,
  épingle) → sr-only ou role="img". [FAIT en phase E, correctif immédiat]
- data-testid en trois segments pour les nouveaux éléments
  (corpus-note-monter, corpus-filtre-vider, corpus-resume-filtres…).
- Conserver de l'étalon : prefers-reduced-motion, thème sombre 3 états.

## C. Divergences spec/étalon — arbitrages

| # | Divergence | Proposition (à valider par le propriétaire) |
|---|---|---|
| C.1 | Guide de rédaction : dans l'étalon, absent du modèle | La spec § 2 le dit « Pris — un TextField sur le dossier » ; § 3 a oublié le champ. → Ajouter `Dossier.guide_de_redaction` (TextField) en F, migration triviale |
| C.2 | Facettes : « menu déroulant » (spec § 8.2) vs puces toujours visibles (étalon) | **À trancher par le propriétaire.** L'étalon est l'autorité déclarée ; recommandation : suivre l'étalon (puces aria-pressed) |
| C.3 | Fil d'Ariane absent de SPEC-corpus § 8 | Décrit dans PRESENTATION-V3 § 5.5 : manque de la spec § 8, suivre l'étalon |
| C.4 | Avertissement carnet public § 8.3 sans définition ni étalon | Le « cochage » vise la popup d'extension (§ 7.3, phase I) et l'ajout à un carnet public (phase G). À spécifier au moment de G/I |
| C.5 | Avertissement « dernière appartenance » (§ 9) ni codé ni maquetté | Phase G (bloc « Dans N carnets ») ; test § 10 à écrire à ce moment |
| C.6 | Exclusion des synthèses : `estUneSource()` (étalon, par type) vs `parent_page` (réel, provisoire) | Dépendance dure : dès SPEC-synthese phase A (`type_de_note`), basculer le filtre de `_appartenances_filtrees_par_facettes` |
| C.7 | Trois définitions du compteur de notes | Unifier en F : le compte de l'en-tête = celui de l'onglet = notes sources (hors synthèses), dérivé |
