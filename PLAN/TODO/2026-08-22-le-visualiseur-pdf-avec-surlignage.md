# Le visualiseur PDF : ouvrir la source à la bonne page, boîte surlignée

**Chantier reporté par le mainteneur le 22 août 2026** — « rien d'urgent ».
Ce document rassemble ce qu'il faut savoir avant d'y toucher. **Rien n'est
codé.**

## Ce qui existe déjà, et qui est plus qu'on ne croit

**La donnée est là, mesurée le 22 août 2026 sur la base de dev :**

| document | éléments avec boîtes |
|---|---|
| springer paper version anglaise | **210** |
| Vers une IA au service des écoles | 87 |
| Présentation des Open Badges | 61 |
| Étude épistémologique de l'IA | 11 |
| **total** | **369** éléments, sur 4 PDF |

Elle vit dans `ElementDocument.provenance`, remplie à l'ingestion Docling :

```json
{"page_no": 1,
 "boites": [{"l": 46.0, "t": 739.232, "r": 472.768, "b": 661.032,
             "page_no": 1, "coord_origin": "BOTTOMLEFT"}]}
```

**Le bouton existe aussi** (`front/templates/front/includes/_blocs_elements.html:150`,
`bouton-voir-source`), avec son `data-page-source`. Il **dit honnêtement qu'il
ne sait pas encore le faire** au lieu de promettre — c'est ce qu'il faut garder
tant que le visualiseur n'est pas là.

Il manque donc : le visualiseur, et rien d'autre côté données.

## Les trois pièges, chacun avec sa conséquence visible

1. **`boites` est une LISTE.** Un paragraphe à cheval sur deux pages en a
   plusieurs, chacune avec **son propre `page_no`**. Prendre `boites[0]`
   perdrait la seconde moitié du surlignage, en silence.
2. **`coord_origin` vaut `BOTTOMLEFT`** : `t` se mesure depuis le **bas** de la
   page. PDF.js travaille en origine haut-gauche → `y_écran = hauteur_page − t`.
   Inverser dessine tous les surlignages **à l'envers**, ce qui se voit — mais
   seulement si on regarde.
3. **Les pages font 612 × 792 points** (format Letter, pas A4) pour le PDF
   étude. **Ne jamais coder cette taille en dur** : la lire du document. Un
   scan produit une page aux dimensions de son image (935 × 1210 pour un scan
   à 110 dpi).

## Pourquoi la spec existante ne suffit pas

`PLAN/specs/SPEC-ancrage-par-element-v2.md § 8.2` donne **trois corrections**
(`convertToViewportRectangle`, `devicePixelRatio`, `boites` en liste) mais
**aucun socle** : rien sur le composant PDF.js lui-même, la pagination, le
zoom, le calque de surlignage, ni le cycle de vie du visualiseur dans une page
HTMX.

**Écrire cette spec en addendum daté AVANT de coder** — c'est la règle du dépôt
pour un trou de spec, et celui-ci en est un.

## Ce qu'il reste à décider

- **PDF.js servi en local ou par CDN ?** Le local est cohérent avec le
  `collectstatic` du projet et avec le fait que le build Tailwind est figé ;
  le CDN est plus simple mais ajoute une dépendance réseau à une page de
  lecture.
- **SVG au-dessus du canvas, ou divs positionnés ?** Le SVG suit mieux le zoom ;
  les divs sont plus faciles à styler avec les tokens de `maquette.css`.
- **Le cas d'un PDF SANS couche texte** — un scan pur. Il n'y a alors **aucune
  coordonnée** à surligner : le bouton doit-il disparaître, ou ouvrir le
  document sans surlignage ? Rappel : Docling OCRise déjà (RapidOCR en
  dépendance transitive), donc un scan **a** des éléments et des boîtes — mais
  issues de l'OCR, avec sa marge d'erreur.
- **Où ouvrir le document ?** Dans le panneau de droite (comme les preuves), en
  plein écran, ou dans un onglet ? C'est une décision de lecture, pas de
  technique : le lecteur doit-il garder la note sous les yeux pendant qu'il
  regarde la source ?

## Ce qui casse si on ne le fait pas

Rien ne casse. La chaîne de preuve est complète sans lui : l'ancre existe, la
citation est vérifiée, le passage est montré dans son contexte
(`core/services/contexte_de_citation.py`). Le visualiseur ajoute **la dernière
marche** — voir la preuve dans le document original, à sa place, telle qu'elle
a été imprimée. C'est un gain de confiance, pas une réparation.
