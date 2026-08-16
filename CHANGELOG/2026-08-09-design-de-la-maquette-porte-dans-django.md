# Le design de la maquette porte dans Django (ecrans corpus/synthese)

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** decision du proprietaire (« l'ancien CSS est a
jeter, le design de la maquette est tres bon ») : le design system de
l'etalon tmp/maquettes/corpus.html est PORTE dans Django, avec les P0
de la confrontation maquette integres.
- `front/templates/front/corpus/_style_maquette.html` : les tokens et
  composants de l'etalon (Georgia, papier/encre/filet, onglets a
  soulignement ambre, puces-facettes, lignes de notes en grille,
  article-synthese, renvois exposants, panneau de preuve LATERAL fixe
  + voile, operations a liseret par type, surfaces de creation),
  SCOPES sous .zone-corpus pour cohabiter avec l'ancien CSS du reste
  du site jusqu'a la bascule complete. prefers-reduced-motion
  respecte. Etats etendus vs etalon : source_debat, conteste,
  non_verifie (pointille).
- **Les P0 de la confrontation** :
  1. LES VERDICTS AU FIL DU TEXTE : chaque paragraphe est une
     .affirmation[data-verification] coloree (pire verdict de ses
     citations ; AUCUNE citation = non_source ROUGE, § 4.4) +
     legende des etats + comptes de verdicts dans l'en-tete.
  2. Panneau de preuve LATERAL (.est-ouvert, voile, ✕, Escape,
     renvoi marque actif, focus rendu a la fermeture).
  3. /lire/ REDIRIGE les articles de synthese vers leur ecran
     (un wiki ouvert par l'arbre ne perd plus ses citations) ;
     les syntheses historiques versionnees gardent l'ecran lecture.
  4. Navigation : bouton retour-liste, hx-push-url sur l'onglet
     Notes, etat actif des onglets tenu par 3 lignes de JS
     (aria-selected ne ment plus), compteurs Wikis (n) /
     Syntheses (n).
  5. Le compteur d'ecartees DANS le summary (« 46 extractions du
     perimetre n'ont pas ete reprises »), charge a l'ouverture du
     pli ; « Sources citees : N extractions (M renvois) » — deux
     comptes, deux mots. Les lignes de liste sont QUALIFIEES
     (sources · ecartees · verifiees · faibles).
- La garde zero-citation (voir phases H-I) est nee d'un constat reel
  pendant cette livraison.

Verifie en navigation reelle (Playwright, hyp.nasjo.fr/carnets/1/) :
onglet actif honnete, 8 affirmations colorees (6 faibles oranges,
2 verifiees vertes), legende, panneau lateral + Escape, summary
chiffre, qualification des listes, zero erreur JS.

| Fichier | Changement |
|---|---|
| `front/templates/front/corpus/_style_maquette.html` | Nouveau : le design system de l'etalon, scope |
| `carnet_detail.html`, `partials/notes_du_carnet.html` | Refonte aux classes maquette (testids conserves) |
| `article.html`, `liste_wikis.html`, `liste_syntheses.html` | Refonte + P0 |
| `partials/preuve.html`, `partials/diff_operations.html` | Classes maquette (etat-verification, operation[data-op]) |
| `front/views_synthese.py` | Affirmations colorees, comptes distincts, qualification des lignes, compteur d'ecartees |
| `front/views_corpus.py` | Compteurs d'onglets wikis/syntheses |
| `front/views.py` | Redirection /lire/ des articles de synthese |

### Migration
- **Migration necessaire / Migration required :** Non.

