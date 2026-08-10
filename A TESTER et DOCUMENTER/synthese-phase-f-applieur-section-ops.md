# Synthèse phase F — l'applieur d'opérations de section

## Ce qui a été fait

SPEC-synthese § 6 : `core/services/section_ops.py`, fonction pure
`appliquer_les_operations(texte, operations, perimetre)` :

- 4 types d'opérations : no_change, append_to_section, replace_section,
  insert_section.
- Rejet VISIBLE et PAR OPÉRATION (addendum n°4) : motif + contenu
  conservé dans `operations_rejetees` — titre introuvable (jamais de
  fallback fin d'article), titre dupliqué (ambigu), sources vides,
  sources hors périmètre (dérivées des marqueurs [[ext:N]]).
- Seuls les `##` font frontière (addendum n°3).
- `replace` retourne `ancien_contenu` (le diff § 6.4 montrera l'avant).
- `verifier_que_la_proposition_est_fraiche(article, updated_at)` :
  concurrence optimiste (addendum n°1), accepte datetime ou chaîne ISO.

L'applieur n'écrit RIEN en base : l'enchaînement complet (sauver le
texte final, réindexer via indexer_les_citations, incrémenter
tours_de_mise_a_jour) est le travail des endpoints de la phase H.

## Tests a réaliser

```bash
docker exec hypostasia_dev_web python manage.py test \
  core.tests.test_section_ops --noinput
```

Test manuel en shell (fonction pure, sans risque) :
```bash
docker exec hypostasia_dev_web python manage.py shell -c "
from core.services.section_ops import appliquer_les_operations
article = '## A\n\nCorps.[[ext:1]]\n'
bilan = appliquer_les_operations(article, [
    {'type': 'append_to_section', 'section': 'A', 'contenu': 'Ajout.[[ext:1]]'},
    {'type': 'append_to_section', 'section': 'Fantome', 'contenu': 'Perdu ?[[ext:1]]'},
], {1})
print(bilan['texte_final'])
print('rejets:', [r['motif'][:60] for r in bilan['operations_rejetees']])"
```
Attendu : l'ajout dans A est appliqué, l'opération « Fantome » est
rejetée avec son motif et son contenu conservé.

## Relecture adverse (9 août soir, constats prouvés par exécution) — corrigé
1 bloquant + 6 importants, chacun avec son test (24 tests au total) :
un contenu contenant un `##` fabriquait une section non approuvée avec
titre dupliqué irréversible (B1 → rejet) ; insert d'un titre existant
(I1 → rejet) ; titre indenté reconnu par l'indexeur mais pas l'applieur
— l'ajout atterrissait dans la mauvaise section (I2 → reconnaissance
partagée `titre_de_section()`) ; titres comparés tronqués à 200 (I3) ;
opération JSON malformée qui détruisait le lot (I4 → rejet par
opération) ; ancre vide au motif mensonger (I5) ; schéma contractualisé
en addendum n°15 (I6) ; + M1-M8 (no_change fantôme, CRLF, titre
illégal, une op de contenu par section/lot, indices, motifs FALC).

## Compatibilité
- Aucun appelant de production encore (phase H : endpoints
  previsualiser_maj / appliquer_maj du WikiViewSet). Caveats
  d'intégration dans la docstring de la garde de fraîcheur : re-contrôle
  sous select_for_update dans la transaction d'écriture, horodatage
  sérialisé par .isoformat() (jamais un filtre de gabarit localisé),
  et toute écriture sur la Page périme les propositions en cours
  (auto_now, assumé).
- La définition d'une section (##, indentation tolérée) est PARTAGÉE
  avec indexer_les_citations : `core/services/synthese.py:titre_de_section`
  — une seule vérité.
