# Synthèse phases H-I — les écrans wikis et synthèses dirigées

## Ce qui a été fait

Voir l'entrée CHANGELOG du 9 août (phases H-I). En bref : onglets réels
sur l'écran carnet, 4 tâches carnet-niveau, 3 ViewSets
(front/views_synthese.py), écran article avec renvois [N] cliquables →
panneau de preuve, écartées/couverture en `<details>` paresseux, diff
des opérations par passage à blanc de l'applieur (l'humain coche), et
la garde « zéro citation = refus ».

## Tests a réaliser

### Suites automatiques
```bash
docker exec hypostasia_dev_web python manage.py test \
  front.tests.test_synthese_phase_h --noinput
```

### Parcours réel (données de démonstration EN PLACE sur dev)
1. https://hyp.nasjo.fr/carnets/1/ (anonyme suffit — carnet public)
2. Onglet « Synthèses dirigées » → « Synthèse de démonstration du
   9 août » : 8 renvois [N] cliquables → panneau de preuve avec
   citation exacte, verdict + provenance (2 vérifiées / 6 faibles par
   GPT-4o-mini), débat, lien retour à la source.
3. Dérouler « Ce qui n'a pas été repris » et « Couverture de
   l'analyse ».
4. Onglet « Wikis » → « La gouvernance partagée » (9 citations).
5. Connecté avec l'écriture : « Proposer une mise à jour » sur le wiki
   → attendre la proposition → diff opération par opération (l'avant
   des replace affiché) → appliquer les cochées → tour incrémenté.
6. « Vérifier les citations » sur un article → verdicts avec provenance
   dans le panneau de preuve.

### Garde à connaître
- Un article généré SANS aucune citation (périmètre non vide) est
  refusé avec un message FALC — constaté en réel avec GPT-4o-mini
  avant le renforcement de la consigne.

## Limites connues (pour la bascule CSS / itérations)
- Le panneau de preuve est en bas d'article (aside), pas en panneau
  latéral overlay comme la maquette.
- Les états de vérification ne colorent pas les affirmations AU FIL DU
  TEXTE (data-verification de la maquette) — seulement le renvoi
  (data-etat) et le panneau.
- Les onglets n'affichent pas les compteurs wikis/synthèses, et l'état
  visuel actif ne migre pas après bascule HTMX.
- L'étalon corpus.html ne connaît pas encore les états source_debat /
  conteste / non_verifie (fiche phase G).
- Rapport de confrontation complet : voir l'agent maquette du 9 août
  (synthèse dans la conversation de session) + les améliorations UX/UI
  proposées.
