# LES QUATRE FIXTURES JSON SONT SUPPRIMEES

**Date :** 2026-08-15
**Migration :** Non

**Quoi / What :** `front/fixtures/` disparait. Les donnees de
demonstration ne viennent plus que de commandes.
/ The JSON fixtures are gone; demo data now comes only from commands.

### POURQUOI

Aucune n'etait chargee par quoi que ce soit : ni l'installation, ni un
test, ni une des cinq commandes de fixtures. Et trois des quatre ne se
chargeaient PLUS depuis le 21 mars 2026 — cinq mois — deux migrations
ayant change le schema sous elles (`updated_at` sur ExtractedEntity,
puis le remplacement de `prenom` par une cle etrangere sur
CommentaireExtraction). Verifie en les chargeant une par une sur une
base vierge :

| fixture | loaddata |
|---|---|
| `demo_ia.json` | passait |
| `demo_completes.json` | IntegrityError — `updated_at` |
| `exemple_deliberation.json` | IntegrityError — `updated_at` |
| `demo_alignement_versions.json` | deux erreurs de cle etrangere |

### CE QUE LEUR DEPART SUPPRIME

Elles ne portaient pas que des donnees. `demo_ia.json` contenait un
analyseur « Hypostasia » COMPLET, prompt inclus, et il prenait le pas
sur le code : `creer_les_modeles_ia_et_les_analyseurs` fait un
`get_or_create` sur le NOM et ne garnit le prompt que si l'analyseur n'a
aucune piece. Une base ou la fixture avait ete chargee la premiere
gardait donc le prompt de la FIXTURE pour toujours — un referentiel des
30 hypostases fantome, visible dans aucun fichier Python, et pourtant
celui qu'un modele recevait.

Le referentiel n'a donc plus qu'une source vivante, le code, et les
quatre classes de `test_referentiel_des_hypostases.py` la verrouillent :
le modele, le prompt, l'exemple few-shot et le filtre de production. La
classe qui surveillait les DOUZE copies portees par les fixtures a ete
retiree, avec la raison inscrite a sa place.

### CORRIGE AU PASSAGE

Un message d'erreur de `front/views.py` conseillait « Chargez la fixture
demo_ia.json » : il envoyait l'utilisateur vers un fichier qui n'existe
plus. Il dit desormais « Lancez `make fixtures` ».

Les fixtures restent dans l'historique git (commit `58d18df`).

