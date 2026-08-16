# Couche synthese, phase F : l'applieur d'operations de section

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** SPEC-synthese § 6 : le modele ne reecrit jamais un
wiki — il propose des operations (no_change, append_to_section,
replace_section, insert_section) qu'un applieur fusionne et qu'un
humain accepte.
- `core/services/section_ops.py` : `appliquer_les_operations()`,
  fonction PURE (l'appelant phase H sauvera, reindexera les citations
  et incrementera tours_de_mise_a_jour).
- Un titre introuvable est une HALLUCINATION : operation rejetee
  VISIBLEMENT avec son motif, contenu CONSERVE — jamais de fallback en
  fin d'article, jamais de perte silencieuse (§ 6.2, corrige
  INSPIRATION_ATOMIC § 7). Titre duplique = cible ambigue = rejet.
- Rejet PAR OPERATION (addendum n°4) : une hallucination ne jette pas
  les faits des autres operations.
- Controles § 6.3 deterministes : sources DERIVEES des marqueurs
  [[ext:N]] du contenu (le markdown est la verite) — operation sans
  marqueur ou citant hors perimetre : rejetee.
- Seuls les ## font frontiere (addendum n°3) ; replace retourne
  l'ancien corps pour le diff (§ 6.4).
- `verifier_que_la_proposition_est_fraiche()` : concurrence optimiste
  par updated_at (addendum n°1) — proposition perimee refusee
  visiblement, horodatage illisible traite comme perime.

| Fichier | Changement |
|---|---|
| `core/services/section_ops.py` | Nouveau : l'applieur + la garde de fraicheur |
| `core/tests/test_section_ops.py` | 13 tests (§ 12 + par-operation, ambiguite, ## seulement, ISO) |

**Egalement** : question ouverte n°5 TRANCHEE par le proprietaire (au
plus simple : editer_bloc reste non garde, le gel § 5 effectif sera
livre avec le branchement du moteur element).

### Relecture / Review
Relecture adverse passee (9 aout soir, constats PROUVES par execution),
1 bloquant et 6 importants corriges avec leurs tests (+11) :
- **B1** : le contenu d'une operation pouvait CONTENIR un titre ## et
  fabriquer une section que l'humain n'a pas approuvee — avec un titre
  duplique rendant la section ambigue pour toujours. Rejet : seule
  insert_section cree une section.
- **I1** : insert d'un titre deja present -> rejet (meme corruption).
- **I2** : reconnaissance de frontiere PARTAGEE applieur/indexeur
  (`titre_de_section()`, permissive sur l'indentation) — un titre
  indente ne range plus un ajout dans la mauvaise section.
- **I3** : les titres se comparent tronques a 200 (la taille de
  SourceLink.section, la forme que le prompt peut montrer au modele).
- **I4** : une operation JSON malformee (mauvais types) est rejetee
  PAR OPERATION avec motif, plus jamais une exception qui detruisait
  le lot entier (addendum n°4 respecte jusqu'au bout).
- **I5** : ancre d'insertion absente -> motif honnete (« non
  renseignee », pas « hallucinee »).
- **I6/addendum n°15** : le schema des operations (type/section/titre/
  apres/contenu, snake_case FR) est contractualise dans la spec.
- Mineurs : no_change fantome signale (M1), CRLF normalise (M2), titre
  d'insertion multi-lignes ou en # rejete (M3), recherche par indice
  (M4), UNE operation de contenu par section et par lot (M5 — sinon
  l'« avant » du diff § 6.4 mentirait), indice d'origine dans les
  resultats (M6), motifs FALC (M7), assertion discriminante (M8).
- Caveats d'integration phase H consignes dans la docstring de
  verifier_que_la_proposition_est_fraiche (re-controle sous verrou,
  .isoformat() jamais un filtre localise).

### Migration
- **Migration necessaire / Migration required :** Non.

---

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

