# Fix : taches en erreur bloquees en « En cours » (statut "error" vs "failed")

**Date :** 2026-06-19
**Migration :** Non

**Quoi / What :** correction d'une regression du widget « taches » : un job
d'analyse / synthese / transcription termine en erreur s'affichait indefiniment
« En cours… » (spinner) dans le dropdown et ne passait jamais le bouton en rouge.
Cause : le modele ecrit `status="error"` (`ExtractionJobStatus.ERROR`, coherent avec
`PageStatus` et `TranscriptionJobStatus`), mais `views_taches.py` et
`taches_dropdown.html` testaient `"failed"` — une valeur qui n'existe dans aucun enum.

**Pourquoi / Why :** introduit lors de la session A.8 (simplification des statuts).
Le vocabulaire du front a diverge de celui des modeles. `"failed"` n'etant jamais egal
a `"error"`, les jobs en erreur n'etaient ni comptes (badge non lu), ni detectes comme
erreur (etat rouge prioritaire), et tombaient dans le `else` du template → spinner
« En cours » permanent. Les erreurs ne remontaient donc jamais a l'utilisateur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views_taches.py` | Comparaisons de statut `"failed"` → `"error"` (compteurs non lues, etat erreur, marquer-toutes-lues) |
| `front/templates/front/includes/taches_dropdown.html` | `{% elif tache.status == "failed" %}` → `"error"` (icone + libelle Erreur) |
| `front/tasks.py` | Libelle WebSocket `notifier_tache_terminee(status="failed")` → `"error"` + docstring |
| `front/tests/test_phases.py` | `test_bouton_erreur_si_failed_non_lu` → `_si_error_non_lu`, `status="error"` |

### Migration
- **Migration necessaire / Migration required :** Non
- **Nettoyage des jobs deja bloques :** repasser en `"error"` les jobs orphelins restes
  `pending` / `processing` (worker interrompu) via `manage.py shell`
  (`ExtractionJob` + `TranscriptionJob`).

