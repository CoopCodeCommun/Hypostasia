# Synthèse phase C — la synthèse devient une note du carnet

## Ce qui a été fait

SPEC-synthese-carnet.md § 2-3, phase C (§ 13) :

1. **Modèles `Wiki` et `SyntheseDirigee`** (core/models.py, fin de
   fichier ; migration core.0049). Le wiki a un périmètre par CATÉGORIES
   (recalculé : `notes_du_perimetre_d_un_wiki()`, OU dans un axe / ET
   entre axes) ; la dirigée a un périmètre de NOTES figé
   (`notes_du_perimetre`, jamais recalculé).
2. **Migration core.0050** : chaque page déjà typée SYNTHESE (292 sur
   dev) reçoit son enregistrement SyntheseDirigee — produite_le =
   created_at, dossier = FK, périmètre = [racine versionnée]. Réversible.
3. **`synthetiser_page_task` réécrite** (front/tasks.py) : note typée
   SYNTHESE sans parent_page ; prompt avec identifiants + ligne
   CITATIONS_USED obligatoire (échec bruyant sinon) ; citations indexées
   avec le périmètre réel ; marqueurs hallucinés retirés et signalés ;
   rendu HTML en renvois [N] ; rangement dans le carnet d'origine de la
   demande (sinon les carnets de la source) ; SyntheseDirigee créée.
4. **Vue `synthetiser`** : paramètre optionnel `dossier_id` (écriture
   requise, sinon 400 FALC) ; demandeur_id posé dans le job.

Décisions consignées : addendum n°5-8 de la spec (daté 9 août).

### Modifications
| Fichier | Changement |
|---|---|
| `core/models.py` | + Wiki, + SyntheseDirigee |
| `core/migrations/0049_*.py`, `0050_*.py` | Schéma + données |
| `core/services/synthese.py` | + notes_du_perimetre_d_un_wiki ; périmètre obligatoire |
| `front/tasks.py` | Tâche réécrite + 3 helpers + prompt SOURÇAGE |
| `front/views.py`, `front/serializers.py` | dossier_id validé, demandeur_id |

## Tests a réaliser

### Test 1 : Scénario nominal (avec vrai LLM, autorisé sur dev)
1. Ouvrir une note analysée (avec extractions) sur hyp.nasjo.fr
2. Lancer une synthèse délibérative depuis le dashboard
3. Vérifications attendues :
   - la synthèse apparaît comme une NOTE dans le(s) même(s) carnet(s)
     que la source (titre « Synthèse — … »), pas comme une version V2
   - son texte contient des marqueurs `[[ext:N]]` (vue brute) et le
     HTML affiche des renvois `[1]`, `[2]`…
   - en base : `Page.type_de_note='synthese'`, `parent_page IS NULL`,
     `SyntheseDirigee` créée avec `notes_du_perimetre` = [note source],
     des `SourceLink` `type_lien='cite'` avec section renseignée

```bash
docker exec hypostasia_dev_web python manage.py shell -c "
from core.models import Page, SourceLink, SyntheseDirigee
p = Page.objects.filter(type_de_note='synthese').latest('created_at')
print(p.pk, p.title, p.parent_page_id, p.version_number)
print(SyntheseDirigee.objects.get(page=p).notes_du_perimetre.all())
print(SourceLink.objects.filter(page_cible=p, type_lien='cite').count())"
```

### Test 2 : Génération tronquée
Difficile à provoquer en réel ; couvert par le test automatique
`test_sans_ligne_citations_used_echec_bruyant`. Si un modèle réel coupe
sa réponse : le job passe en erreur avec un message FALC (« la ligne de
contrôle CITATIONS_USED manque… »), AUCUNE page n'est créée.

### Test 3 : Marqueur halluciné
Couvert par `test_un_marqueur_hors_perimetre_est_retire_et_signale` :
le marqueur est retiré du texte, signalé dans
`job.raw_result['marqueurs_retires']`, aucun SourceLink créé.

### Test 4 : Migration 0050 sur dev
```bash
docker exec hypostasia_dev_web python manage.py migrate core
# attendu : "[migration 0050] syntheses dirigees estampillees : ~292 (...)"
docker exec hypostasia_dev_web python manage.py shell -c "
from core.models import SyntheseDirigee; print(SyntheseDirigee.objects.count())"
```

### Suites automatiques
```bash
docker exec hypostasia_dev_web python manage.py test \
  front.tests.test_synthese_phase_c core.tests.test_synthese_modele \
  core.tests.test_synthese_citations front.tests.test_phase28_light --noinput
```

## Relecture adverse (9 août) — corrigé

3 bloquants + 6 importants corrigés avec leurs tests : ligne
CITATIONS_USED habillée acceptée (B1), bleach sur le HTML rendu — un
lien `javascript:` est neutralisé (B2), refus de synthétiser une
synthèse dans la vue ET la tâche (B3), périmètre figé = note analysée
(I1), notifications = carnets de la synthèse + demandeur (I2), repli
« À ranger » pour une source hors carnet (I3), titre de section tronqué
à 200 (I5), périmètre figé avant l'appel LLM (I6), rollback 0050 filtré
et chiffré juste (M1/M2), carnet par les appartenances si FK vide (M3),
titre daté (M9), select_related indexeur (M10). Arbitrage I4 : addendum
n°9.

## Limites connues (assumées, à reprendre plus tard)

- **Garde § 4.2 no-op sur le chemin nominal de relance** (constat M6) :
  une relance d'analyse crée un NOUVEAU job et ne purge pas les
  extractions de l'ancien — la garde
  `verifier_qu_aucune_dirigee_ne_cite_les_extractions` ne se déclenche
  donc pas là ; aucune donnée n'est orpheline (le signal pre_delete
  couvre les vraies suppressions), mais la promesse « une note citée ne
  se ré-analyse pas » attend la phase E (garde_edition) pour être tenue.
- **TOCTOU sur dossier_id** (M11) : la vue vérifie l'écriture, la tâche
  ne revérifie pas ; un partage révoqué entre les deux fait atterrir la
  synthèse dans le carnet quand même. Fenêtre de quelques secondes,
  assumée.
- **Analyseur « texte original seul »** (M5) : la tâche exige un job
  d'analyse même si inclure_extractions=False (préexistant) — la vue
  accepte puis la tâche échoue. À trancher si un tel analyseur apparaît.
- **SyntheseDirigee.dossier ne retient qu'un carnet** (M8) quand la
  source en a plusieurs (le champ est mono-FK par spec § 3.2) ; les
  appartenances de la note, elles, couvrent tous les carnets.
- **citations_annoncees** (M12) : stocké à titre de diagnostic, jamais
  confronté aux marqueurs — candidat pour la vérification phase G.

## Compatibilité
- Le polling front lit toujours `raw_result["page_synthese_id"]` —
  inchangé. `raw_result["version_number"]` n'est plus écrit (aucun
  lecteur, vérifié).
- Les pilules V1·V2 des versions HISTORIQUES restent affichables (les
  données ne bougent pas) ; leur retrait de l'en-tête est la phase H.
- `parent_page` n'a plus aucun écrivain en production (spec § 1) — il
  reste en base pour l'historique.
- L'UI n'envoie pas encore `dossier_id` : le repli (carnets de la note
  source) reproduit le comportement d'avant. Le carnet du geste arrive
  avec l'écran carnet (phase H).
