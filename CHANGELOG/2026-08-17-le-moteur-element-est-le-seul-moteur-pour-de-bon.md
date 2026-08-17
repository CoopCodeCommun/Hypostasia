# Le moteur ELEMENT est le seul moteur — pour de bon / The ELEMENT engine, for real this time

**Date :** 2026-08-17
**Migration :** Oui — `core/0064_doc_du_texte_plat_et_de_son_empreinte`
(uniquement des `help_text` : aucun changement de schéma)

## Résumé / Summary

**Quoi / What :** la décision du 10 août 2026 — « le moteur ELEMENT est le SEUL moteur » —
n'était pas tenue. Neuf endroits lisaient encore `Page.text_readability` comme s'il portait
le contenu d'une note, deux vues créaient des extractions **sans aucune ancre**, trois
gestes d'édition ne touchaient **jamais** les éléments, et l'étage LangExtract historique
restait routé. Tout est retiré ou rebranché sur les éléments.
*/ The 10 August decision was not honoured: nine places still read the flat text as a
note's content, two views created unanchored extractions, three edit gestures never
touched the elements, and the legacy LangExtract layer was still routed.*

**Pourquoi / Why :** ces traces ne levaient aucune erreur. Elles rendaient des résultats
**faux en silence** — un verdict qui accuse une citation exacte, une ancre au caractère 0,
un bloc de prompt vide, un geste qui annonce un succès et ne change rien.
*/ None of them raised: they returned silently wrong results.*

### Ce que le champ plat est devenu

`Page.text_readability` **ne porte plus une vérité concurrente** : après une ingestion
réussie, il est **dérivé des éléments** (`_noter_l_etat_d_ingestion`, le seul point de
passage de toutes les tâches d'ingestion). Il garde ses deux rôles légitimes — l'empreinte
de déduplication, et le texte de secours d'une page sans élément — sans plus pouvoir
mentir.

Mesure du 17 août 2026 : la note « Présentation Hypostasia V3 » portait **58 524 signes de
texte plat ET 189 éléments**, écrits par deux convertisseurs différents. Trois autres notes
avaient ce champ **vide**. Deux façons de se tromper, un seul champ.

### Les neuf traces, et leur sort

| # | Où | Symptôme | Sort |
|---|---|---|---|
| 1 | `verification.py` | 118 citations sur 136 déclarées introuvables | corrigé le 16 août |
| 2 | `_construire_prompt_synthese` | bloc `=== TEXTE ORIGINAL ===` **vide** | lit les éléments |
| 3 | `run_langextract_job` (routé) | `ValueError` sur note Docling ; et **extractions sans ancre** quand il réussissait | **supprimé** |
| 4 | `generate_visualization_html` (routé) | 18 637 signes de HTML bâtis sur un texte vide | **supprimé** |
| 5 | `run_analyseur_on_page` | appelée nulle part | **supprimé** |
| 6 | `creer_manuelle` | `find()` = −1 → `start_char = 0`, **aucune ancre** | ancre dans les éléments, **refuse** si introuvable |
| 7 | `exporter` markdown | export vide ou divergent | lit les **éléments** |
| 8 | `promouvoir_entrainement` | exemple few-shot au texte source vide — il empoisonnait l'analyseur GLOBAL | lit les **éléments** |
| 9 | `comparer` deux versions | vestige du modèle « synthèse = version » | laissé — plus rien ne crée de version, dégradation propre |
| — | `views.py:2403` | **faux positif** : rejoue le vrai découpage | rien à faire |

### Les trois traces que l'audit a trouvées et que je n'avais pas vues

- **L'action `ia` sur une sélection** : même défaut que `creer_manuelle`, mais **après un
  appel LLM facturé**. Chaque entité est désormais ancrée ; celles qu'on ne sait pas ancrer
  sont écartées **et comptées dans le toast** — jamais en silence.
- **L'import de fichier écrivait deux textes concurrents** (voir ci-dessus).
- **Les trois éditions de transcription** — renommer un locuteur, modifier un bloc,
  supprimer un bloc — reconstruisaient `transcription_raw`, le HTML et le texte plat, et ne
  touchaient **jamais** les `ElementDocument`. Or le lecteur rend les éléments : **le geste
  était invisible**. Il annonçait un succès et ne changeait rien de ce qu'on voit.

**Un premier correctif visait l'élément par son `ordre`, et c'était faux.** La relecture
adverse l'a cassé, preuve à l'appui : un **bloc** groupe les segments consécutifs d'un même
locuteur, alors que l'ingestion audio crée **un élément par segment** et **saute les segments
vides**. « Bloc N = élément `ordre` N » ne tient donc que sur un corpus qui alterne les
locuteurs — la fixture de dev, précisément, ce qui rendait le bug invisible. Ailleurs, on
écrivait le texte d'un locuteur dans l'élément d'un **autre**, et la réconciliation replaçait
les ancres sur un texte étranger. S'y ajoutait le glissement des index après une suppression.

**Et ces trois gestes n'ont plus aucun déclencheur dans l'interface** : le JS écoute
`.speaker-name`, `.texte-bloc-cliquable` et `.btn-supprimer-bloc`, que le rendu par éléments
n'émet pas. Mesuré : le rendu de `/lire/3/` en contient **zéro**.

Autrement dit, mon correctif avait transformé un **no-op inoffensif** en **risque de
corruption**, sur des endpoints que l'interface ne peut plus appeler.

**Ils REFUSENT donc désormais**, en 409 et **avant toute écriture** — jamais de demi-état :

| Geste | Sur une note à éléments |
|---|---|
| renommer un locuteur | **refusé** |
| modifier un bloc | **refusé** |
| supprimer un bloc | **refusé** |

Une page **sans** élément — antérieure à la bascule, ou ingestion jamais aboutie — les garde.

> **Le vrai chantier reste à faire** : rebâtir ces trois gestes comme des **opérations
> d'élément**, ciblant l'élément par son **pk** (le lecteur le porte déjà en
> `data-element-id`), avec l'interface qui va avec. Les services existent —
> `masquer_un_element`, `reconcilier_les_portions_de_l_element`, `scinder_un_element`,
> `fusionner_deux_elements`. Ce n'est pas un correctif, c'est une fonctionnalité.

### Une garde de fond, et une garde de forme

**`synthetiser_page_task` court-circuitait le tronc commun d'écriture.** C'était le
**troisième** producteur d'articles vivant, et il échappait donc aux trois gardes :
normalisation des niveaux de titre, refus des titres en collision, refus d'un article sans
aucune citation. *Une garde qui ne couvre que deux producteurs sur trois n'est pas une
garde.* Il passe désormais par `_ecrire_le_corps_d_un_article`.

**Un garde-fou anti-réintroduction** remplace un `grep` devenu vide de sens : il balaye les
**trois apps** et échoue si l'un des cinq noms de l'étage historique réapparaît dans du
code exécuté. Le précédent ne cherchait `run_langextract_job` que dans `front/`, et passait
au vert le jour où la fonction a disparu de partout.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/services/__init__.py` | **736 → 349 lignes** : les cinq fonctions de l'étage historique retirées |
| `hypostasis_extractor/views.py` | actions `run` et `visualization` retirées, import supprimé |
| `hypostasis_extractor/templates/.../job_error.html`, `job_results.html` | **supprimés** — plus rien ne les rendait |
| `hypostasis_extractor/services/ancrage.py` | **+** `ancrer_un_texte_dans_une_page` : ancre un texte libre, réutilise la table des offsets et le découpage en portions |
| `hypostasis_extractor/tasks_element.py` | le texte plat devient une projection des éléments à la réussite |
| `hypostasis_extractor/services/analyse_par_element.py` | quatre commentaires reformulés — ils décrivaient l'ancien moteur au présent |
| `hypostasis_extractor/models.py` | `help_text` de `start_char`/`end_char` : ce ne sont plus des positions dans `text_readability` |
| `front/views.py` | **+** `_texte_de_la_note_depuis_ses_elements`, l'unique lecteur du texte d'une note ; `creer_manuelle` et `ia` ancrent et refusent ; les trois éditions de transcription **refusent** sur une note à éléments ; offsets sur le texte collé ; le GET de lecture ne réécrit plus le texte plat ; `exporter` et `promouvoir_entrainement` lisent les éléments |
| `front/tasks.py` | `synthetiser_page_task` passe par le tronc commun ; `_construire_prompt_synthese` lit les éléments |
| `front/templates/front/corpus/article.html`, `liste_wikis.html`, `liste_syntheses.html` | le verdict `introuvable` s'affiche enfin |
| `core/services/verification.py` | commentaire corrigé : l'audio a des éléments lui aussi |
| `front/tests/test_phases.py` | garde-fou anti-réintroduction |
| `core/tests/test_synthese_citations.py` | le test de la garde § 4.2 repointé vers le chemin vivant |
| `front/tests/test_phase28_light.py` | 4 mocks rendus conformes au contrat de citation |
| **5 fichiers de tests neufs** | 21 tests |

**191 tests verts** sur l'ensemble des modules touchés.

### Un affichage qui manquait

Le verdict `introuvable`, créé la veille, était **calculé et jamais affiché**. Pire : la
condition d'`article.html` l'excluait, donc un article dont tous les verdicts auraient été
« introuvable » n'aurait affiché **aucune ligne « Vérification »** — le signal invisible
dans le cas exact où il compte.

---

## Comment tester (à la main) / Manual test

### Test 1 — l'étage historique a disparu

```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_phases.EtageLangextractHistoriqueTest --noinput
```
Puis vérifier que `POST /api/extraction-jobs/<pk>/run/` et
`GET /api/extraction-jobs/<pk>/visualization/` répondent **404**.

### Test 2 — une extraction manuelle est ancrée, ou refusée

1. Ouvrir une note ingérée par Docling, sélectionner un passage, créer une extraction.
2. Cliquer la carte : elle doit surligner **le passage**, pas le début du document.
3. En base : `AncrageExtraction.objects.filter(extraction=...)` doit rendre au moins 1.
4. Coller un texte **retouché** (une lettre changée) : l'extraction est **refusée** avec un
   message clair, et rien n'est créé.

### Test 3 — les trois éditions de transcription refusent proprement

Ces gestes **n'ont plus de déclencheur dans l'interface** : le test passe donc par l'API.

```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_edition_transcription_touche_les_elements --noinput
```

À la main, sur la note « Débat IA — transcription » (qui porte 12 éléments) : un POST sur
`/lire/3/supprimer_bloc/` doit répondre **409**, et `transcription_raw` doit être
**inchangée** — c'est le point qui compte, un refus tardif l'aurait amputée.

### Test 4 — le texte plat suit les éléments

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
import unicodedata
from core.models import ElementDocument, Page
for p in Page.objects.filter(type_de_note='note'):
    elems = '\n\n'.join(ElementDocument.objects.filter(page=p).order_by('ordre').values_list('texte', flat=True))
    print(p.pk, p.title[:34], '| plat==elements :', (p.text_readability or '') == elems)"
```
Toute note dont l'ingestion a réussi **depuis ce chantier** affiche `True`. Les notes
ingérées **avant** restent divergentes — relancer leur ingestion les aligne, et **aucun
backfill n'est fourni**. Ce n'est plus dangereux : plus aucun lecteur ne prend ce champ pour
le contenu d'une note. `exporter` et `promouvoir_entrainement`, les deux derniers, lisent
maintenant les éléments par `_texte_de_la_note_depuis_ses_elements`.

### Test 5 — le verdict « introuvable » s'affiche

Vérifier une synthèse : la ligne « Vérification » de l'en-tête doit compter les
introuvables quand il y en a, et la légende doit porter son filet **tireté**.

### Piège à connaître

**`make restart S=celery_worker` après toute modification de `front/tasks.py` ou d'un
service qu'il importe.** Sans ça, les tâches tournent avec l'ancien code.
