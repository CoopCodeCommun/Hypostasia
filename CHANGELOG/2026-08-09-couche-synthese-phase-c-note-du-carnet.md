# Couche synthese, phase C : la synthese devient une note du carnet

**Date :** 2026-08-09
**Migration :** Oui

**Quoi / What :** le coeur de SPEC-synthese § 2-3 :
- Les deux genres au modele : `Wiki` (vivant — perimetre par CATEGORIES,
  recalcule a chaque appel par `notes_du_perimetre_d_un_wiki()`, OU dans
  un axe / ET entre axes) et `SyntheseDirigee` (acte date — perimetre de
  NOTES fige a la production, jamais recalcule). Migration core.0049.
- Migration core.0050 : les syntheses existantes (typees en phase A)
  recoivent leur enregistrement SyntheseDirigee — produite_le =
  created_at, perimetre fige = la racine dont elles etaient la version.
  Reversible, bilan chiffre.
- `synthetiser_page_task` REECRITE : la synthese est une note
  `type_de_note=SYNTHESE` du carnet — plus jamais une version de page
  (parent_page n'a plus AUCUN ecrivain, § 1). Le prompt expose
  « Identifiant : ext:N » et exige les marqueurs `[[ext:N]]` + la ligne
  finale `CITATIONS_USED:` ; sans elle, la generation est TRONQUEE :
  echec bruyant (`SyntheseTronqueeError`, message FALC), rien n'est
  enregistre. `indexer_les_citations()` est appelee avec le PERIMETRE
  des extractions envoyees au modele (une seule definition,
  `_extractions_pour_la_synthese`, pour le prompt ET le perimetre) — le
  parametre est desormais OBLIGATOIRE dans la signature. Les marqueurs
  hallucines sont retires ET signales (`raw_result["marqueurs_retires"]`).
  Le HTML derive rend des renvois `[N]` (jamais persistes, § 4.4).
  Tout-ou-rien : page + liens + appartenances + acte date naissent dans
  une transaction.
- La vue `synthetiser` accepte `dossier_id` (le carnet d'origine de la
  demande, § 2.1) : ECRITURE exigee sur ce carnet, sinon 400 FALC. Elle
  pose demandeur_id + dossier_id dans le job ; la tache range la
  synthese dans ce carnet (sinon repli : les carnets de la note source)
  via `ranger_une_note_dans_un_carnet`.

**4 decisions consignees en addendum de la spec (n°5-8)** : dossier de
la dirigee SET_NULL nullable (l'acte date survit au carnet), carnet
d'origine optionnel avec repli, format exact de CITATIONS_USED, rendu
[N] au HTML.

### Fichiers / Files
| Fichier | Changement |
|---|---|
| `core/models.py` | + `Wiki`, + `SyntheseDirigee` (fin de fichier) |
| `core/migrations/0049_wiki_et_synthese_dirigee.py` | Schema |
| `core/migrations/0050_estampiller_les_syntheses_dirigees_existantes.py` | Donnees, reversible |
| `core/services/synthese.py` | + `notes_du_perimetre_d_un_wiki` ; perimetre obligatoire dans `indexer_les_citations` |
| `front/tasks.py` | Tache reecrite + `_extractions_pour_la_synthese`, `_detacher_la_ligne_citations_used`, `_remplacer_les_marqueurs_par_des_renvois`, prompt SOURCAGE |
| `front/views.py`, `front/serializers.py` | `dossier_id` valide (ecriture requise) + demandeur_id dans le job |
| `core/tests/test_synthese_modele.py` | + 8 tests (genres, perimetres, migration 0050) |
| `front/tests/test_synthese_phase_c.py` | 12 tests (note typee, citations, troncature, carnet d'origine, vue) |
| `front/tests/test_phase28_light.py` | Adapte au nouveau contrat (CITATIONS_USED, plus de version) |

### Relecture / Review
Relecture adverse passee (9 aout) : 3 bloquants et 6 importants
corriges, chacun avec son test (dans test_synthese_phase_c,
test_synthese_citations, test_synthese_modele) :
- **B1** : la ligne CITATIONS_USED habillee par le modele (backticks,
  gras, bloc de code — le format que le prompt lui montre) n'est plus
  rejetee comme troncature. Le fond reste strict.
- **B2 (XSS stocke)** : la sortie markdown passe par bleach (allowlist
  balises + protocoles http/https/mailto). `html.escape` ne touche pas
  `[texte](url)` : un `javascript:` reconstruit APRES echappement etait
  rendu `|safe`.
- **B3** : on ne synthetise JAMAIS une synthese (§ 3.3) — refus 400
  FALC dans la vue ET garde en profondeur dans la tache.
- **I1** : le perimetre fige est la note ANALYSEE, pas sa racine (le
  § 8 en depend).
- **I2** : les notifications ciblent les carnets de LA SYNTHESE + le
  demandeur (la vue lui promettait une notification).
- **I3** : une source hors carnet -> la synthese est rangee dans le
  « A ranger » du demandeur, jamais orpheline invisible.
- **I5** : un titre de section > 200 caracteres est tronque au lieu de
  detruire la synthese entiere (bulk_create).
- **I6** : le perimetre est fige AVANT l'appel LLM — une extraction
  masquee pendant la generation reste une citation legitime.
- Mineurs : rollback 0050 filtre (ne supprime que ses lignes, compteur
  exact), carnet via les appartenances si FK vide, titre date
  (« Synthese du JJ/MM/AAAA — ... »), select_related sur l'indexeur.
- Arbitrage I4 consigne en addendum n°9 (synthese visible dans l'arbre,
  ecran carnet en phase H). Limites connues restantes documentees dans
  la fiche A TESTER (garde § 4.2 no-op sur la relance nominale — les
  anciennes extractions ne sont pas purgees ; TOCTOU dossier_id
  vue->tache ; analyseur "texte seul" exige quand meme une analyse).

### Migration
- **Migration necessaire / Migration required :** Oui — core.0049 et
  core.0050 (appliquees sur dev).

---

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

