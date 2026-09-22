# La mise à jour des wikis redevient un geste / Wiki updates are a human gesture again

**Date :** 2026-09-21
**Migration :** Oui — `core.0081_retrait_de_la_passe_de_nuit` (supprime `PasseDeNuit`, et
met à jour le `help_text` de `TourDeWiki.fait_par`, sans effet SQL).
`docker exec -w /app hypostasia_web python manage.py migrate`

## Résumé / Summary

**Quoi / What :** la passe de nuit des wikis est retirée. Aucune tâche planifiée
n'appelle plus de modèle : un wiki ne se met à jour que par le bouton « Mettre à jour »
de son article (proposer, diff, accepter). En remplacement, chaque ligne de la liste
des wikis d'un carnet dit « ● N nouveautés depuis le JJ/MM/AAAA » ou « rien de neuf ».
Le récapitulatif du matin reste planifié, sans plus attendre de passe.
*/ The nightly wiki pass is removed; no scheduled task calls a model any more. Each
line of a notebook's wiki list now says how many new items arrived since the last
round. The morning recap stays scheduled and no longer waits.*

**Pourquoi / Why :** la passe retenait un wiki dès qu'il portait **une** extraction
écartée — et non une extraction *apparue depuis le dernier tour*. Un wiki qui écarte à
raison des extractions hors sujet était rappelé et facturé chaque nuit, avec un prompt
qui grossissait. Estimé (non mesuré) : environ les trois quarts de la facture LLM pour
une centaine de wikis. Décision du mainteneur ; addendum du 21 septembre 2026 dans
`PLAN/specs/SPEC-synthese-carnet.md`.
*/ The pass billed every wiki carrying any left-out extraction, every night, whether or
not anything new had arrived.*

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasia/celery.py` | le beat ne planifie plus que le récapitulatif ; `HEURE_PASSE_DE_NUIT` disparaît |
| `front/tasks.py` | **retirés** : `lancer_la_passe_de_nuit_task`, `mettre_a_jour_un_wiki_la_nuit_task`, `mettre_a_jour_un_wiki_la_nuit`, `_fermer_la_passe`, `_rendre_la_main_a_la_passe`. `envoyer_le_recapitulatif_du_matin_task` n'attend plus rien |
| `front/management/commands/envoyer_le_recapitulatif_du_matin.py` | **retirés** : `--attendre-minutes`, `--sans-attendre-la-nuit` et la boucle d'attente |
| `front/management/commands/mettre_a_jour_les_wikis.py` | **supprimé** |
| `core/services/passe_de_nuit.py` | **supprimé** |
| `core/models.py`, `core/migrations/0081_…` | `PasseDeNuit` supprimé. `MotifDeTourDeWiki.MAJ_NOCTURNE` **gardé** : les tours déjà écrits le portent. `TourDeWiki.fait_par` : NULL ne désigne plus que l'ancienne nuit ou un compte supprimé |
| `front/views_synthese.py` | `lister_pour_le_carnet` annote chaque wiki de ses `nouveautes` (même calcul que l'en-tête d'article) |
| `front/templates/front/corpus/liste_wikis.html` | la ligne « ● N nouveautés depuis le … » / « rien de neuf » |
| `front/templates/front/corpus/_style_maquette.html` | le style `.valeur-du-geste[data-neuf]` de l'en-tête s'applique aussi à la liste |
| `bin/nuit.sh` → `bin/recapitulatif.sh` | ne garde que l'envoi du mail, à la main |
| `Makefile` | `make nuit` **retiré** ; `make recapitulatif` appelle `bin/recapitulatif.sh` ; `make prod-update` relance aussi `celery_beat` |
| `supervisord.conf`, `supervisord-dev.conf` | commentaires du beat à jour (il n'appelle plus de modèle) |
| `front/tests/test_la_liste_des_wikis_signale_le_neuf.py` | **neuf** — 4 tests |
| `front/tests/test_appliquer_un_tour_de_wiki.py` | **neuf** — les 9 tests de l'applieur que portait la passe, rebranchés sur le geste humain |
| `front/tests/test_la_passe_de_nuit_des_wikis.py`, `core/tests/test_l_etat_de_la_passe_de_nuit.py` | **supprimés** (orchestration de la passe) |
| `front/tests/test_le_recapitulatif_du_matin.py` | tests d'attente retirés ; « le beat ne planifie que le récapitulatif » et « la tâche part sans attendre » ajoutés |
| `PLAN/specs/SPEC-synthese-carnet.md` | addendum du 21 septembre ; renvoi en tête de celui du 21 août |

### ⚠️ En production

Si le crontab de l'hôte porte des lignes `bin/nuit.sh` (le CHANGELOG du 21 août en
proposait **deux** : `passe` à 3 h et `recapitulatif` à 7 h), **les retirer toutes les
deux** : le script n'existe plus, et le beat envoie déjà le récapitulatif. `crontab -l`
pour vérifier.

**Relancer le beat au déploiement.** Un beat qui tourne garde l'ancien horaire en
mémoire : il enverrait chaque nuit une tâche qui n'existe plus (erreur « unregistered
task » dans les journaux, rien de facturé). `make prod-update` le relance désormais ;
après un déploiement fait autrement :
`docker exec hypostasia_web supervisorctl -c /app/supervisord.conf restart celery_beat`.

### Au merge avec `origin/dev` (22 septembre)

La branche distante avait fait évoluer la passe pendant ce temps (critère « du neuf depuis
le dernier essai », fan-out, verrou en base, tours d'échec, borne haute du récapitulatif).
Résolution : la passe reste retirée, tout le reste est gardé.

- **Migration renumérotée** : elle s'appelait `0077_retrait_…` et suit désormais les quatre
  migrations distantes — `0081_retrait_de_la_passe_de_nuit`, après `0080`. Elle supprime
  aussi la contrainte `une_seule_passe_de_nuit_ouverte` (avec la table).
- **Gardé du distant** : la borne haute du récapitulatif (`couvre_jusqu_a`), ses six
  rubriques, `--forcer` et `--depuis-jours` ; le motif `ECHEC` et `message_d_echec`
  (historique seulement : aucun chemin actuel n'en écrit) ; `borne_du_dernier_essai`, que
  l'applieur utilise pour compter ce qui a appelé un tour ; le traitement de `no_change`
  par l'applieur (test rebranché sur le geste humain).
- **Retiré du distant** : le critère de reprise nocturne, le verrou de passe, les tâches de
  fan-out, et leurs tests. `core/tests/test_le_planificateur.py` verrouille désormais
  « seul le récapitulatif est planifié ».

---

## Comment tester (à la main) / Manual test

### Test 1 — le planificateur n'appelle plus de modèle

```bash
docker exec -w /app hypostasia_web python -c "
import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','hypostasia.settings'); django.setup()
from hypostasia.celery import celery_app
print([e['task'] for e in celery_app.conf.beat_schedule.values()])"
```

Attendu : `['front.tasks.envoyer_le_recapitulatif_du_matin_task']`, rien d'autre.

### Test 2 — la liste des wikis signale le neuf

1. Ouvrir un carnet qui a au moins un wiki, onglet **Wikis**.
2. Chaque ligne porte une ligne de plus : « rien de neuf » en gris, ou
   « ● N nouveautés depuis le JJ/MM/AAAA » en bleu gras.
3. Analyser une note du carnet (ou en ajouter une et l'analyser), revenir à l'onglet
   Wikis : le wiki concerné passe à « ● N nouveautés ».
4. Ouvrir ce wiki : la ligne « Mettre à jour » de l'en-tête annonce **le même nombre**.
5. Cliquer « Mettre à jour », accepter au moins une opération que l'applieur retient :
   revenu à la liste, la ligne repasse à « rien de neuf ». Un lot entièrement rejeté
   ne compte pas comme un tour : la ligne garde ses nouveautés, comme l'en-tête.
6. Refaire l'étape 2 en thème sombre : contraste lisible.

### Test 3 — le récapitulatif part sans attendre

```bash
make recapitulatif ARGS=--a-blanc
```

Attendu : la liste de qui recevrait quoi, ou « Rien à raconter ce matin », sans aucune
attente et sans erreur « la passe de nuit tourne encore ».

### Vérifs DB

```bash
docker exec -w /app hypostasia_web python manage.py showmigrations core | tail -2
# -> [X] 0081_retrait_de_la_passe_de_nuit
```
