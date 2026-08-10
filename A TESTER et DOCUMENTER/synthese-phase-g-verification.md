# Synthèse phase G — la vérification des citations (§ 7)

## Ce qui a été fait

`core/services/verification.py` :
`verifier_les_citations_d_un_article(article, modele_ia=None)` — la
cascade § 7.1 par paire (affirmation, source) :

1. **Verbatim** (déterministe) sur le texte actuel de la note source ;
   en échec → verbatim sur les commentaires du débat → état
   `SOURCE_DEBAT` + `commentaires_source` rempli (§ 7.4) ; en échec
   partout → `FAIBLE` sans appel LLM.
2. **NLI en lot** : UN appel `appeler_llm` juge toutes les paires
   verbatim-OK (`N: soutient` / `N: ne_soutient_pas`) → `VERIFIE` /
   `FAIBLE` ; verdict absent → `NON_VERIFIE` signalé au bilan.

Garanties : provenance sur chaque verdict (`verifie_par`,
`verifie_le`) ; `CONTESTE` humain jamais écrasé ; à la demande
seulement (le déclencheur UI = phase H). Décision Q3 du propriétaire
consignée dans la spec (§ 14) : le juge est le LLM configuré, en lot.

Migration core.0052 (verifie_par/verifie_le + nouveaux états),
appliquée sur dev.

## Tests a réaliser

### Suite automatique
```bash
docker exec hypostasia_dev_web python manage.py test \
  core.tests.test_verification --noinput
```

### Test réel avec LLM (autorisé sur dev, coût ~centimes)
Produire une synthèse sur une note analysée (voir fiche phase C), puis :
```bash
docker exec hypostasia_dev_web python manage.py shell -c "
from core.models import Page
from core.services.verification import verifier_les_citations_d_un_article
p = Page.objects.filter(type_de_note='synthese',
    source_links_cible__type_lien='cite').distinct().latest('created_at')
print(verifier_les_citations_d_un_article(p))
from core.models import SourceLink
for l in SourceLink.objects.filter(page_cible=p, type_lien='cite'):
    print(l.pk, l.etat_de_verification, '|', l.verifie_par)"
```
Attendu : bilan avec verifiees/faibles, chaque lien portant
`verifie_par` (« verbatim+nli-lot v1 — <modèle> ») et `verifie_le`.

## Relecture adverse (9 août, nuit) — corrigé

2 bloquants + 7 importants, chacun testé (19 tests) : la ré-indexation
RÉCONCILIE les verdicts au lieu de les détruire (un CONTESTE dont la
paire disparaît est signalé dans `bilan["contestations_perdues"]`) ;
prompt du juge à délimiteurs nonce + rejet du lot entier sur indices
suspects (anti-injection) ; échec du juge sans dégradation ; source
supprimée déchue de son verdict ; bornes périmées jamais jugées (le
paragraphe doit contenir son marqueur) ; la fidélité au débat se juge
aussi ; paquets de 20 ; masquées/détachées non blanchies ;
commentaires_source suit le verdict.

## À porter au cahier des charges de la phase H
- L'étalon `tmp/maquettes/corpus.html` ne connaît que
  verifie/faible/non_source : il faut y ajouter les états
  `source_debat`, `conteste` et `non_verifie` (couleur, légende,
  compteurs) et étendre `scripts/verifier_les_maquettes.py`, sinon les
  37 contrôles resteront verts sur un écran incomplet.
- L'endpoint d'application des opérations doit, après ré-indexation,
  afficher `contestations_perdues` à l'utilisateur.

## Compatibilité / limites
- `NON_SOURCE` reste un état d'AFFICHAGE par paragraphe sans marqueur
  (calculé à l'écran, phase H) — pas posé par ce service.
- § 7.3 (le statut de débat remonte au renvoi [N]) : dérivable à
  l'affichage depuis `extraction_source.statut_debat`, rien à stocker.
- Le déclenchement est un geste explicite : aucun appel automatique.
