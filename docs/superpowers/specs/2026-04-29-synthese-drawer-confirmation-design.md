# Synthèse délibérative — confirmation dans le drawer

> Spec écrite le 2026-04-29 lors d'une session de brainstorming.
> Statut : design validé section par section avec le mainteneur, en attente de spec self-review et de plan d'implémentation.

## Contexte

Aujourd'hui, lancer une synthèse délibérative ouvre une **modale construite en JavaScript** depuis le dashboard de consensus (`front/static/front/js/dashboard_consensus.js:208-286`). La modale propose un sélecteur d'analyseur et un bouton « Confirmer », mais elle n'affiche **ni l'estimation des tokens, ni le coût, ni le prompt complet**, contrairement au flow d'extraction qui affiche tout cela dans le drawer (panneau de droite).

Cette spec décrit le remplacement de cette modale par un partial Django qui s'affiche dans le **drawer existant** (`#drawer-contenu`), en miroir de `confirmation_analyse.html`. Elle introduit aussi un bool `est_par_defaut` sur les analyseurs pour fixer un analyseur de défaut par type.

## Objectifs

- Remplacer le modal JS par un partial Django dans le drawer.
- Afficher l'estimation tokens + coût + prompt avant confirmation, comme le flow d'extraction.
- Conserver l'info consensus (% atteint / seuil / extractions bloquantes) en permanence dans la confirmation.
- Faire vivre le polling et la fin de synthèse dans le drawer (auto-fermeture quand terminé).
- Ajouter un bool `est_par_defaut` sur les analyseurs (un par type), avec auto-décochage des autres au save.
- Bloquer la synthèse en amont si l'analyseur a `inclure_extractions=True` mais qu'aucune analyse complète n'existe sur la page.

## Non-objectifs

- Pas de refactoring du flow extraction.
- Pas d'unification générique extraction + synthèse (YAGNI, anti-pattern djc).
- Pas de tests E2E (le projet est en alpha).
- Pas de bouton « Annuler » dans la confirmation (croix du drawer ou Escape suffisent).

## Architecture

Trois endpoints (sur `PageViewSet` dans `front/views.py`), tous renvoient des partials HTMX dans `#drawer-contenu` :

| Endpoint | Méthode | Rôle |
|---|---|---|
| `/lire/{pk}/previsualiser_synthese/` | GET | Confirmation : analyseur, estimation, consensus, compteurs |
| `/lire/{pk}/synthetiser/` | POST | Lance le job Celery, renvoie le partial polling dans le drawer |
| `/lire/{pk}/synthese_status/` | GET | Polling 3s, et à la fin : OOB de la zone-lecture vers la V2 + HX-Trigger `fermerDrawer` |

Le `PATCH /api/analyseurs/{id}/` existant gère déjà l'auto-save des bool — il faut juste ajouter la logique de toast quand `est_par_defaut` décoche un autre analyseur.

## Composants par fichier

### Modèle et migration

**`hypostasis_extractor/models.py:336+`** — ajout d'un champ booléen :
```python
est_par_defaut = models.BooleanField(
    default=False,
    help_text=(
        "Marquer cet analyseur comme défaut pour son type. "
        "Cocher ici décoche automatiquement les autres analyseurs du même type."
    ),
)
```

Surcharge du `save()` :
```python
def save(self, *args, **kwargs):
    if self.est_par_defaut:
        AnalyseurSyntaxique.objects.filter(
            type_analyseur=self.type_analyseur,
            est_par_defaut=True,
        ).exclude(pk=self.pk).update(est_par_defaut=False)
    super().save(*args, **kwargs)
```

**Migration** : `0026_analyseursyntaxique_est_par_defaut.py` auto-générée par `makemigrations`.

### Serializer

**`hypostasis_extractor/serializers.py:237+`** — ajout dans `AnalyseurSyntaxiqueUpdateSerializer` :
```python
est_par_defaut = serializers.BooleanField(required=False)
```

### ViewSet de l'analyseur (modification du `partial_update`)

**`hypostasis_extractor/views.py`** — `AnalyseurSyntaxiqueViewSet.partial_update` capture l'autre default avant le save et ajoute un `HX-Trigger` toast info si quelqu'un a été décoché. Code complet dans la section 5.3 de la conversation (à transposer dans le plan d'implémentation).

### Helper consensus

**`front/views.py`** — extraire la logique du dashboard de consensus en helper `_calculer_consensus(page)` qui renvoie un dict avec compteurs, pourcentage, seuil, extractions bloquantes. Réutilisé par : la vue dashboard existante et le nouveau `previsualiser_synthese`.

### Endpoint `previsualiser_synthese`

**`front/views.py`** — nouvel `@action(detail=True, methods=["GET"], url_path="previsualiser_synthese")` sur `PageViewSet`. Construit le contexte :

| Donnée | Calcul |
|---|---|
| `analyseur` | `?analyseur_id=` ou premier `is_active=True, type_analyseur="synthetiser"` ordré par `-est_par_defaut, name` |
| `tous_les_analyseurs_synthese` | tous les actifs de type synthetiser (pour le selecteur) |
| `modele_ia_actif` | `Configuration.get_solo().ai_model` (toast si None) |
| `dernier_job_analyse` | dernier `ExtractionJob` `status="completed"` exclu `est_synthese=True` |
| `nombre_extractions_disponibles` | entités du job non masquées et `statut_debat != "non_pertinent"` |
| `nombre_commentaires_disponibles` | `CommentaireExtraction.objects.filter(entity__job=dernier_job_analyse).count()` |
| `prompt_complet` | `prompt_systeme` (depuis pieces) + `_construire_prompt_synthese(...)` |
| `nombre_tokens_input` | `tiktoken.encode(prompt_complet)` (pas de chunking) |
| `nombre_tokens_output_visible` | `nombre_tokens_input * 0.5` (cohérent avec extraction, YAGNI sur ratio spécifique synthèse) |
| `nombre_tokens_thinking` | `output_visible * (multiplicateur_thinking - 1)` |
| `cout_estime_euros` | `modele_ia.estimer_cout_euros(...) * 1.5` arrondi au cent |
| `consensus` (dict) | `_calculer_consensus(page)` — compteurs par statut, %, seuil, bloquantes |
| `bouton_desactive` | `(analyseur.inclure_extractions and nombre_extractions_disponibles == 0) OR (not analyseur.inclure_extractions and not analyseur.inclure_texte_original)` |
| `raison_desactivation` | Texte explicite selon le cas |
| `contexte_credits` | Identique extraction (gate Stripe) |

Si un job de synthèse est déjà en cours sur la page → renvoyer directement le partial polling (comme `previsualiser_analyse` le fait pour les jobs actifs).

### Template `confirmation_synthese.html`

**`front/templates/front/includes/confirmation_synthese.html`** — nouveau partial, structure :

```
#confirmation-synthese
├── En-tête (icône violette + titre + nom de page)
├── Selecteur analyseur (si count > 1) — recharge l'estimation au changement
├── Encart consensus complet (compteurs 3x2 par statut + barre + bloquantes)
├── Infos résumé (analyseur, modèle IA, pieces, état des 2 bool)
├── Compteurs disponibilité (extractions, commentaires)
├── Estimation tokens et coût
├── Bouton "Voir le prompt complet" (toggle JS, zone scrollable)
├── Gate solde Stripe (si activé)
├── Alerte de blocage (si bouton_desactive=True)
└── Bouton "Lancer la synthèse" (désactivé si bouton_desactive)
```

OOB swap pour `#drawer-titre` avec un bouton retour vers le dashboard de consensus.

### Adaptation du flow synthèse existant

**`front/views.py`** :
- `synthetiser` (POST) → renvoie un nouveau partial `synthese_en_cours_drawer.html` dans `#drawer-contenu` + `HX-Trigger: ouvrirDrawer`.
- `synthese_status` (GET) → branches `processing` / `completed` / `error` cibles `#drawer-contenu`. Branche `completed` renvoie un OOB qui recharge `#zone-lecture` (via `hx-trigger="load"`) avec la V2 + maj du pill du switcher de versions + `HX-Trigger: fermerDrawer`. Branche `error` reste dans le drawer avec bouton « Refaire la confirmation ».

**`front/templates/front/includes/synthese_en_cours_drawer.html`** — nouveau partial polling, 2 états (en cours avec spinner, error avec retry). Le state `completed` n'utilise PAS ce template — il est géré directement par la vue qui renvoie un body composé du partial OOB + HX-Trigger.

**`front/templates/front/includes/synthese_terminee_oob.html`** — nouveau partial OOB, recharge `#zone-lecture` et met à jour le pill V2. Renvoyé en réponse complète par `synthese_status` quand le state est `completed`.

### Bouton dashboard

**`front/templates/front/includes/dashboard_consensus.html:97-107`** — remplacement du `onclick="ouvrirModaleSynthese(...)"` par `hx-get="/lire/{pk}/previsualiser_synthese/" hx-target="#drawer-contenu"`. Le `data-analyseurs` JSON disparaît. Conservation du dégradé de couleur orange/vert selon `seuil_atteint`.

### Suppression de code mort

- `front/static/front/js/dashboard_consensus.js:208-286` — fonctions `ouvrirModaleSynthese` et `fermerModaleSynthese`.
- `front/templates/front/includes/synthese_en_cours.html` — vérifier au moment de l'implémentation s'il est encore référencé. Si non → supprimer.

### JS — listener `fermerDrawer`

**`front/static/front/js/hypostasia.js`** — ajouter (à côté du listener `ouvrirDrawer` existant) :
```javascript
document.body.addEventListener('fermerDrawer', function() {
    if (window.drawerVueListe && window.drawerVueListe.fermer) {
        window.drawerVueListe.fermer();
    }
});
```

### Affichage du badge « Par défaut »

Ajouter le badge dans :
- `front/templates/front/includes/carte_analyseur.html`
- `front/templates/front/includes/detail_analyseur_readonly.html`
- `hypostasis_extractor/templates/hypostasis_extractor/includes/analyseur_item.html`

Style : `bg-blue-50 text-blue-700 border border-blue-200`, texte « Par défaut », `data-testid="badge-defaut"`.

### Fixtures

**`front/management/commands/charger_fixtures_demo.py`** — ajouter `est_par_defaut=True` dans les `defaults` des trois analyseurs créés (Hypostasia, FALC, Synthèse délibérative). Pour la base existante : update manuel via shell Django après application de la migration.

## Data flow

### Lancement d'une synthèse

```
1. Dashboard : clic sur "Lancer la synthèse"
   → hx-get /lire/{pk}/previsualiser_synthese/
   → réponse : confirmation_synthese.html dans #drawer-contenu
   → HX-Trigger: ouvrirDrawer (drawer s'ouvre)

2. Drawer : utilisateur change l'analyseur (optionnel)
   → hx-get /lire/{pk}/previsualiser_synthese/?analyseur_id=N
   → réponse : confirmation_synthese.html avec nouveau contexte

3. Drawer : clic "Lancer la synthèse"
   → hx-post /lire/{pk}/synthetiser/
   → backend : crée ExtractionJob, lance Celery, valide les bool
   → réponse : synthese_en_cours_drawer.html dans #drawer-contenu

4. Drawer : polling toutes les 3s
   → hx-get /lire/{pk}/synthese_status/
   → tant que processing : re-render du polling
   → au completed :
       → réponse vide + OOB de #zone-lecture (hx-trigger="load") + pill V2
       → HX-Trigger: fermerDrawer
       → résultat : drawer se ferme, zone-lecture charge la V2
   → en cas d'erreur : message + bouton "Refaire la confirmation"
```

### Cocher `est_par_defaut`

```
1. Editor : utilisateur coche "Analyseur par défaut pour son type"
   → JS auto-save : PATCH /api/analyseurs/{id}/ {est_par_defaut: true}

2. Backend partial_update :
   → Capture l'autre default actuel du même type (si existe)
   → save() : décoche les autres du même type, applique le nouveau

3. Réponse : OK + HX-Trigger toast info si un autre a été décoché
   → "Analyseur « X » n'est plus marqué par défaut pour le type « Y »"
```

## Gestion des erreurs

| Cas | Comportement |
|---|---|
| Aucun analyseur synthetiser actif | `previsualiser_synthese` → HTTP 400 + toast erreur, drawer ne s'ouvre pas |
| Aucun modèle IA actif | idem |
| Job de synthèse déjà en cours | `previsualiser_synthese` → renvoie le partial polling (drawer s'ouvre sur l'état en cours) |
| `inclure_extractions=True` + 0 extractions | Confirmation s'affiche, bouton désactivé, alerte « Lancez d'abord une analyse » |
| Les 2 bool à False | Confirmation s'affiche, bouton désactivé, alerte « Configurez l'analyseur » |
| Solde Stripe insuffisant | Confirmation s'affiche, bouton désactivé, lien vers `/credits/` |
| Échec Celery (LLM ou autre) | `synthese_status` branche `error` → message dans le drawer + bouton retry |

## Tests

### Unitaires

- `est_par_defaut` au save : décoche les autres du même type, ne touche pas les autres types.
- `_calculer_consensus(page)` retourne les compteurs corrects.

### Intégration

- `previsualiser_synthese` : retours dans tous les cas (succès, sans analyseur, sans modèle, avec job en cours, avec/sans extractions, avec les 2 bool à False, solde insuffisant).
- `synthetiser` (POST) : retourne le partial drawer + HX-Trigger ouvrirDrawer.
- `synthese_status` : 3 branches (processing, completed avec OOB + fermerDrawer, error).
- `partial_update` analyseur : toast info si décoche un autre default.

### Tests existants à vérifier

- `front/tests/test_phase28_light.py` — peut tester le retour vers `#zone-btn-synthese` → adapter.
- `front/tests/e2e/test_18_bibliotheque_analyseurs.py` — vérifier les sélecteurs si badge default ajouté (mais E2E pas dans le scope, juste vérification rapide).

### Pas de E2E

Le projet est en alpha, on teste manuellement via le navigateur.

## Ordre d'implémentation suggéré

1. Migration + champ `est_par_defaut` + save() + serializer.
2. Toast info dans `partial_update`.
3. Toggle dans editor + tests unitaires sur le save.
4. Helper `_calculer_consensus`.
5. Endpoint `previsualiser_synthese` + template `confirmation_synthese.html`.
6. Adaptation `synthetiser` (POST) + nouveau partial polling.
7. Adaptation `synthese_status` + nouveau partial OOB.
8. Listener JS `fermerDrawer`.
9. Suppression du modal JS + adaptation bouton dashboard.
10. Badges « Par défaut » dans bibliothèque + sidebar config.
11. Mise à jour fixtures + base existante.
12. Tests d'intégration.
13. Test manuel du flow complet via navigateur.

## Dette laissée volontairement

- Le flow « Restituer une extraction » (modal sur le fil de discussion) reste en place avec son type `restituer` legacy. Le mainteneur a explicitement demandé de ne pas y toucher dans cette session.
- Les endroits du code qui filtrent par `type_analyseur="restituer"` (~5 occurrences dans `front/views.py`) restent inchangés — ils n'interagissent pas avec la synthèse.

## Décisions de design

| Décision | Justification |
|---|---|
| Drawer plutôt que modal | Cohérence avec le flow extraction, anti-pattern djc d'avoir du HTML construit en JS |
| Approche 1 (réutilisation par miroir) | YAGNI, djc privilégie le verbeux et le lisible top-to-bottom |
| Ratio output 50% (comme extraction) | YAGNI sur un ratio spécifique synthèse, à ajuster après mesure réelle |
| Bool `est_par_defaut` par type | Plus utile qu'un default unique global ; chaque type a son contexte |
| Toast info au décochage automatique | UX explicite, l'utilisateur comprend ce qui s'est passé |
| Encart consensus en permanence dans la confirmation | Donne le contexte à chaque synthèse, l'utilisateur peut le consulter même si seuil atteint |
| Auto-fermeture du drawer en fin de synthèse | Plus rapide pour l'utilisateur, le drawer est un panneau temporaire |
| Pas d'unification extraction + synthèse | Logiques métier différentes, anti-pattern djc |
| Pas de bouton Annuler explicite | La croix du drawer et Escape suffisent (réponse Q1 = c) |
