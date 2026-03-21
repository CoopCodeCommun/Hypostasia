# PHASE-27e — Verrous d'édition optimistes

**Complexite** : S | **Mode** : Normal | **Prerequis** : PHASE-27a

---

## 1. Contexte

Avec le multi-utilisateur (PHASE-25), plusieurs personnes peuvent éditer la même
page simultanément. Sans protection, le dernier à sauvegarder écrase le travail
des autres sans prévenir.

Un verrou **optimiste** est le bon compromis MVP :
- Pas de verrouillage en base (pessimiste = trop complexe, deadlocks, timeouts)
- Le client envoie le timestamp de dernière lecture
- Le serveur vérifie si la page a été modifiée entre-temps
- Si oui → alerte l'utilisateur avec le choix de forcer ou abandonner

## 2. Objectifs précis

### 2.1 — Timestamp côté client

Les 3 actions d'édition (`modifier_titre`, `renommer_locuteur`, `editer_bloc`)
envoient un champ `derniere_lecture` (timestamp ISO) dans le formulaire.

Ce timestamp est injecté dans les templates d'édition via un `data-attribute`
sur la zone de lecture, mis à jour à chaque chargement de page :
```html
<div data-page-updated-at="{{ page.updated_at|date:'c' }}">
```

Le JS lit ce `data-attribute` et l'inclut dans les requêtes HTMX d'édition.

### 2.2 — Vérification côté serveur

Dans chaque action d'édition, **avant** le save :
```python
derniere_lecture_client = serializer.validated_data.get("derniere_lecture")
if derniere_lecture_client and page.updated_at > derniere_lecture_client:
    # Conflit détecté — la page a été modifiée depuis la dernière lecture
    return render(request, "front/includes/conflit_edition.html", {
        "page": page,
        "derniere_modification_par": dernier_edit.user if dernier_edit else None,
        "derniere_modification_date": page.updated_at,
    })
```

La réponse de conflit est un partial HTMX (pas une erreur 409 brute) :
- Message : "Cette page a été modifiée par {user} le {date}."
- Bouton "Recharger la page" (abandon)
- Bouton "Forcer la sauvegarde" (re-soumet avec `force=true`)

### 2.3 — Template `conflit_edition.html`

Bannière d'alerte (style warning) qui remplace la zone d'édition :
- Fond orange pâle, bordure orange
- Icône ⚠️ + message descriptif
- 2 boutons d'action

### 2.4 — Mise à jour des serializers

Ajouter un champ optionnel `derniere_lecture` (DateTimeField, required=False)
aux 3 serializers :
- `ModifierTitrePageSerializer`
- `RenommerLocuteurSerializer`
- `EditerBlocSerializer`

Et un champ `force` (BooleanField, default=False) pour forcer malgré le conflit.

### 2.5 — Helper `_verifier_conflit_edition()`

Fonction utilitaire réutilisable dans les 3 actions :
```python
def _verifier_conflit_edition(page, derniere_lecture, force=False):
    """
    Retourne None si pas de conflit, ou un dict de contexte pour le template conflit.
    / Returns None if no conflict, or a context dict for the conflict template.
    """
```

## 3. Fichiers à modifier

| Fichier | Changement |
|---------|-----------|
| `front/views.py` | +`_verifier_conflit_edition()`, hooks dans 3 actions |
| `front/serializers.py` | +champ `derniere_lecture` + `force` sur 3 serializers |
| `front/templates/front/includes/conflit_edition.html` | Nouveau — bannière de conflit |
| `front/templates/front/includes/lecture_principale.html` | +data-page-updated-at |
| `front/static/front/js/hypostasia.js` | +envoi `derniere_lecture` dans les requêtes d'édition |
| `front/tests/test_phase27e.py` | Tests unitaires (détection conflit, force, pas de conflit) |

## 4. Critères de validation

- [ ] `uv run python manage.py check` → 0 erreur
- [ ] Édition sans conflit → sauvegarde normalement
- [ ] Édition avec conflit → bannière d'alerte avec message et boutons
- [ ] "Forcer la sauvegarde" avec `force=true` → sauvegarde quand même
- [ ] "Recharger" → recharge la page avec les données à jour
- [ ] Le timestamp `derniere_lecture` est absent → édition fonctionne normalement
  (rétrocompatibilité avec l'extension navigateur et les anciens formulaires)
- [ ] Le `data-page-updated-at` est présent sur la zone de lecture

## 5. Vérification navigateur

1. Ouvrir une page dans 2 onglets (même utilisateur ou 2 utilisateurs différents)
2. Dans l'onglet 1 : modifier le titre et sauvegarder
3. Dans l'onglet 2 : modifier le titre et sauvegarder
4. **Attendu** : onglet 2 affiche la bannière "modifié par {user} le {date}"
5. Cliquer "Forcer" → le titre est sauvegardé
6. Cliquer "Recharger" → la page se recharge avec le titre de l'onglet 1

## 6. Tests prevus

**Module :** `front.tests.test_phase27e` | **Statut : A ECRIRE**

| Classe | Test | Quoi |
|--------|------|------|
| `ConflitEditionTest` | `test_edition_sans_conflit_sauvegarde` | Pas de conflit si page non modifiee |
| `ConflitEditionTest` | `test_edition_avec_conflit_retourne_banniere` | Banniere si page modifiee entre-temps |
| `ConflitEditionTest` | `test_force_true_sauvegarde_malgre_conflit` | Force bypass le conflit |
| `ConflitEditionTest` | `test_sans_derniere_lecture_fonctionne` | Retrocompatibilite si champ absent |
| `ConflitEditionTest` | `test_conflit_modifier_titre` | Conflit detecte sur modifier_titre |
| `ConflitEditionTest` | `test_conflit_editer_bloc` | Conflit detecte sur editer_bloc |
| `ConflitEditionTest` | `test_conflit_renommer_locuteur` | Conflit detecte sur renommer_locuteur |
| `HelperConflitTest` | `test_verifier_conflit_retourne_none_si_ok` | Helper retourne None sans conflit |
| `HelperConflitTest` | `test_verifier_conflit_retourne_contexte_si_conflit` | Helper retourne dict si conflit |

**E2E :** `front.tests.e2e` — tests prevus :
- `test_conflit_affiche_banniere_orange`
- `test_forcer_sauvegarde_fonctionne`
- `test_recharger_page_apres_conflit`

## 7. Notes pour les phases suivantes

- Un vrai verrou pessimiste (lock en base) pourra être ajouté si nécessaire
  pour l'édition collaborative temps réel (PHASE-35 WebSocket)
- Le conflit ne bloque pas — il prévient. L'utilisateur a toujours le dernier mot
