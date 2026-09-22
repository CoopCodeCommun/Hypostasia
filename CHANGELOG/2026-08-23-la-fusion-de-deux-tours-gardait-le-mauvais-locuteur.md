# La fusion de deux tours gardait le mauvais locuteur / Merging two turns kept the wrong speaker

**Date :** 2026-08-23
**Migration :** Oui — `core/migrations/0080_les_cles_de_provenance_audio.py`
(`AlterField` sur un `help_text` seulement, aucun changement de schéma)
`docker compose exec web python manage.py migrate core`

## Résumé / Summary

**Quoi / What :** `_fusionner_les_provenances` lisait `start_time`, `end_time` et
`voice` — trois clés que l'ingestion audio n'écrit **nulle part**. Elle écrit
`locuteur`, `debut`, `fin`, et c'est ce que le rendu lit. Les quatre lectures rendaient
donc `None`, les deux gardes ne s'exécutaient jamais, et la provenance du **premier**
tour était conservée telle quelle.
/ The merge read three keys the audio ingestion never writes, so both guards were
inert and the FIRST turn's provenance was kept as-is.

**Pourquoi / Why :** recoller le tour de Paul dans celui d'Ian produisait **un tour
attribué à Ian contenant les mots de Paul**, et un intervalle qui s'arrêtait à la fin
du premier tour. En silence. Dans un outil de délibération sourcée, une extraction
peut ainsi citer quelqu'un qui n'a rien dit.
/ Merging Paul's turn into Ian's produced a turn attributed to Ian holding Paul's
words, silently.

### Ce que la correction change / What the fix changes

| Avant | Après |
|---|---|
| locuteur du premier, toujours | locuteur retiré si les deux diffèrent |
| `fin` du premier tour | `fin` du **second** tour |
| `debut` déjà juste (venait du `dict()` initial) | inchangé |

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/services/moteur_structure.py` | `_fusionner_les_provenances` lit `locuteur`/`debut`/`fin` ; commentaire qui dit **pourquoi** une autre orthographe désactive les gardes en silence |
| `core/models.py` | `help_text` de `ElementDocument.provenance` : il annonçait le mauvais contrat, et c'est par lui que l'erreur s'est propagée |
| `hypostasis_extractor/tests/test_moteur_structure.py` | les tests **dérivent** leur provenance de `_decouper_un_tour_trop_long` au lieu de l'écrire à la main ; 2 tests neufs |
| `core/migrations/0080_les_cles_de_provenance_audio.py` | `AlterField` du `help_text` |

### Pourquoi les tests ne l'avaient pas vu / Why the tests missed it

Les deux tests existants **fabriquaient eux-mêmes** une provenance
`{"start_time", "end_time", "voice"}` — un dictionnaire que la production ne produit
jamais. Ils étaient **verts sur un contrat mort**.

Le nouveau helper `_provenance_d_un_tour` appelle le vrai code d'ingestion, et un test
(`test_la_provenance_du_tour_porte_les_cles_de_l_ingestion`) épingle le contrat
lui-même : s'il tombe, les trois autres cessent de prouver quoi que ce soit.

**44 tests dans `test_moteur_structure`, verts.** Suites voisines vérifiées, toutes
vertes : `test_ancrage_m2m` (54), `test_rendu_elements` (54),
`test_masquage_et_reingestion` (26), `test_reconciliation` (23),
`test_barre_du_lecteur_audio` (7), `test_gouttiere_audio` (5),
`test_edition_transcription_touche_les_elements` (5), `test_couleurs_des_locuteurs` (3).

### Ce que ce correctif ne fait PAS / What it does not do

**Il ne répare aucune donnée existante.** Toute fusion de tours faite avant aujourd'hui
a produit une attribution potentiellement fausse, et rien ne permet de la retrouver :
la provenance d'origine n'est pas conservée.

**Correction de mesure, le 23 août 2026 :** cette section affirmait d'abord qu'« aucune
transcription n'est ingérée sur la base de dev ». C'était faux — la requête avait porté
sur `voice`, la clé morte. Remesuré avec la bonne clé :
`provenance__has_key='locuteur'` rend **21 éléments sur 1 129**, sur **deux** notes
(page 3 « Débat IA — transcription », 12 ; page 4 « Palais César — deux locuteurs », 9),
**5 locuteurs distincts**. `provenance__has_key='voice'` rend bien **0**. La portée
réelle en production reste à établir, mais le cas audio est éprouvable ici.

---

## Comment tester (à la main) / Manual test

### Test 1 — deux locuteurs différents perdent le locuteur

```bash
docker compose exec web python manage.py shell -c "
from hypostasis_extractor.services.moteur_structure import _fusionner_les_provenances
a = {'locuteur': 'Paul', 'debut': 10.0, 'fin': 15.0}
b = {'locuteur': 'Ian',  'debut': 15.0, 'fin': 22.5}
print(_fusionner_les_provenances(a, b))
"
```

Attendu : `{'debut': 10.0, 'fin': 22.5}` — **pas de `locuteur`**, et la fin est celle
du second tour.
Avant le correctif : `{'locuteur': 'Paul', 'debut': 10.0, 'fin': 15.0}`.

### Test 2 — le même locuteur des deux côtés est conservé

Même commande avec `'locuteur': 'Paul'` des deux côtés.
Attendu : `{'locuteur': 'Paul', 'debut': 10.0, 'fin': 22.5}`.

### Test 3 — au navigateur, sur une vraie transcription

1. importer un fichier audio et attendre la transcription ;
2. ouvrir la note, activer « Modifier la structure » ;
3. repérer deux tours **de locuteurs différents** qui se suivent ;
4. « recoller avec le suivant » sur le premier ;
5. **vérifier** que le tour fusionné n'affiche plus d'étiquette de locuteur, et que
   l'écoute depuis ce tour couvre bien les deux interventions jusqu'au bout.

### Test 4 — la suite

```bash
make test-suite S=hypostasis_extractor.tests.test_moteur_structure
```

### Vérif DB

```bash
docker compose exec web python manage.py shell -c "
from core.models import ElementDocument
print('avec locuteur :', ElementDocument.objects.filter(provenance__has_key='locuteur').count())
print('avec voice (ne doit plus jamais augmenter) :',
      ElementDocument.objects.filter(provenance__has_key='voice').count())
"
```
