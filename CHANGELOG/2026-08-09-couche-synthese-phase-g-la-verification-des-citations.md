# Couche synthese, phase G : la verification des citations

**Date :** 2026-08-09
**Migration :** Oui

**Quoi / What :** SPEC-synthese § 7 — deux controles en cascade, PAR
PAIRE (affirmation, source) :
1. **Verbatim** (deterministe, gratuit) : le texte cite existe-t-il
   litteralement dans la source ACTUELLE ? Tolerant aux espaces,
   sensible au reste. En echec sur l'extraction, on cherche dans les
   COMMENTAIRES : une affirmation qui reprend fidelement un commentaire
   est SOURCEE PAR LE DEBAT (§ 7.4, nouvel etat SOURCE_DEBAT +
   commentaires_source rempli) — pas « faible ». En echec partout :
   FAIBLE, sans payer d'appel au juge.
2. **Implication (NLI)** : jugee par LE LLM CONFIGURE, EN LOT (une
   requete pour N paires) et A LA DEMANDE — question ouverte n°3
   TRANCHEE par le proprietaire (9 aout) : pas de modele local sur un
   serveur 8 Go partage ; ~0,01-0,05 EUR par synthese en lot.

Les garanties § 7.2 :
- chaque verdict porte sa PROVENANCE (`verifie_par` = methode + modele,
  `verifie_le`) — « un etat sans provenance est un argument d'autorite
  automatise » ;
- l'etat CONTESTE pose par un humain n'est JAMAIS ecrase par une
  re-verification ;
- un verdict ABSENT de la reponse du juge (troncature, refus) laisse la
  paire NON_VERIFIE et le signale — jamais un faux « verifie ».

| Fichier | Changement |
|---|---|
| `core/models.py` | EtatDeVerification + CONTESTE + SOURCE_DEBAT ; SourceLink + verifie_par/verifie_le |
| `core/migrations/0052_provenance_du_verdict.py` | Schema (appliquee sur dev) |
| `core/services/verification.py` | Nouveau : la cascade + le juge en lot |
| `core/tests/test_verification.py` | 7 tests |

Le declenchement (endpoint « verifier cette synthese ») est la phase H —
le service est A LA DEMANDE par construction, jamais appele a la
production d'une synthese.

### Relecture / Review
Relecture adverse passee (9 aout, nuit — parsing et normalisation
prouves par execution), 2 bloquants et 7 importants corriges avec
leurs tests (19 au total) :
- **B1 (le plus grave)** : reconstruire l'index des citations
  (indexer_les_citations, phase B) DETRUISAIT tous les verdicts — y
  compris un CONTESTE humain. L'indexeur RECONCILIE desormais : un
  verdict est reporte quand la paire (extraction, paragraphe) est
  inchangee ; une contestation dont la paire a disparu est SIGNALEE
  (bilan["contestations_perdues"]), jamais perdue en silence.
- **B2 (injection)** : le prompt du juge encadre chaque donnee par des
  delimiteurs NONCE (l'affirmation et la source viennent de notes
  potentiellement hostiles), et une reponse aux indices dupliques,
  hors lot ou surnumeraires est REJETEE EN ENTIER — le lot reste
  NON_VERIFIE, jamais un faux « verifie » injectable.
- **I1** : une exception du juge (timeout, quota) ne degrade RIEN —
  les verdicts precedents survivent, l'echec est au bilan.
- **I2** : une source supprimee perd son verdict vert (provenance
  « source supprimee — verdict retire »).
- **I3** : des bornes cibles perimees (article edite sans
  re-indexation) ne sont JAMAIS jugees — le paragraphe doit contenir
  son marqueur.
- **I4** : la fidelite au DEBAT se juge aussi — reprendre un
  commentaire verbatim puis le deformer dans la conclusion donnait un
  SOURCE_DEBAT immerite ; le chemin debat passe au juge (soutient ->
  SOURCE_DEBAT, sinon FAIBLE).
- **I5** : le lot est decoupe par paquets de 20 (contextes et timeouts
  bornes), echec par paquet isole.
- **I6** : une extraction masquee ou une ancre detachee n'est pas
  blanchie par un verdict frais (non_jugeables au bilan).
- **I7** : commentaires_source suit toujours le verdict (plus de
  provenance « debat » orpheline sous un verdict faible).
- Mineurs : juge jamais anonyme (name ou model_choice), NFKC +
  apostrophes typographiques dans le verbatim, tolerance puces dans
  les lignes de verdict (indices controles strictement), marqueurs
  retires de l'affirmation envoyee au juge, texte source charge une
  fois par note, ordre deterministe des paires, NON_SOURCE documente
  comme etat d'affichage (jamais pose en base).
- Pour la phase H (fiche A TESTER) : l'etalon corpus.html ne connait
  pas encore source_debat/conteste/non_verifie — la maquette et
  verifier_les_maquettes.py devront etre etendus.

### Migration
- **Migration necessaire / Migration required :** Oui — core.0052
  (appliquee sur dev).

---

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

