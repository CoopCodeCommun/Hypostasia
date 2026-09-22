# Ce qui part vraiment dans un prompt / What a prompt actually sends

**Date :** 2026-09-01
**Migration :** **Oui** — trois, toutes appliquées à la base de dev :
`hypostasis_extractor/0039_le_morceau_de_prompt_n_a_pas_de_nom`,
`0040_les_deux_bascules_d_injection_disparaissent`,
`core/0081_le_wiki_porte_son_redacteur`.
`docker exec -w /app hypostasia_web python manage.py migrate`

## Résumé / Summary

**Quoi / What :** l'éditeur de prompts ne propose plus que ce qui **part
réellement** au modèle. Le nom d'un morceau disparaît (il ne partait nulle
part), son **rôle** part désormais en titre de bloc, et les deux bascules
d'injection sont supprimées. Chacun des trois gestes de production choisit son
analyseur, et un wiki garde le sien.
/ The prompt editor now offers only what actually travels: piece names are
gone, roles now title each block, the two injection toggles are removed, and
every production gesture picks its analyzer.

**Pourquoi / Why :** l'écran offrait trois réglages sans effet. Le **nom** d'un
morceau n'entrait dans aucun prompt — les trois morceaux de l'installation
l'avaient d'ailleurs laissé vide. Les **deux bascules** ne décidaient de rien
pour un article, et pour une synthèse de note elles pouvaient produire un prompt
sans matière — ce que deux gardes existaient uniquement pour empêcher. Un
réglage qui ne règle rien est pire qu'une absence de réglage : il laisse croire
qu'on a agi.

## Le rôle part maintenant au modèle / The role now travels

Chaque morceau est envoyé sous le titre de son rôle :

```
=== CONTEXTE ===
Tu es un moteur de synthèse délibérative.

=== INSTRUCTION ===
Une extraction porte un statut de débat…
```

C'est cohérent avec le reste du prompt, qui est déjà découpé ainsi
(`=== SUJET DE L'ARTICLE ===`, `=== EXTRACTIONS DU PÉRIMÈTRE ===`,
`=== CONSIGNE ===`). Une pièce vide ne produit **pas** de titre orphelin : un
titre seul ferait croire au modèle à une section qu'on aurait oublié de remplir.

**Un seul point d'assemblage** : `AnalyseurSyntaxique.texte_du_prompt()`. **Dix**
endroits recollaient les pièces à la main, chacun à sa façon — dont un par une
boucle, que la recherche sur `join(piece.content` ne voyait pas : il aurait
affiché à l'écran un prompt **sans** les titres pendant que le vrai en aurait eu.

⚠️ **Toutes les empreintes de provenance changent.** Le prompt change réellement,
donc les productions d'avant ne sont plus comparables à celles d'après. C'est
voulu, mais il faut le savoir avant d'ouvrir un banc.

⚠️ **Deux sections homonymes.** Les fixtures posent deux pièces de rôle
`instruction` : le préambule porte donc deux `=== INSTRUCTION ===`. À éprouver au
banc LLM avant d'en tirer une conclusion.

## Les deux bascules sont supprimées / The two toggles are gone

`inclure_extractions` et `inclure_texte_original` n'existent plus. Une synthèse
de note envoie **toujours** le texte de la note, ses extractions et leurs
commentaires. Les deux gardes qui refusaient « aucun des deux coché » (HTTP 400
et bouton désactivé) disparaissent avec leur cause.

L'écran de confirmation **énonce** ce qui part au lieu d'offrir un choix :

```
Ce qui est envoyé    Texte, extractions et commentaires
```

## Chaque geste choisit son analyseur / Every gesture picks its analyzer

La création d'un wiki et la synthèse dirigée n'avaient **aucun** paramètre : elles
prenaient le défaut du type sans qu'on puisse en désigner un autre. Elles ont
maintenant leur sélecteur, le **préféré en tête** — et c'est exactement celui qui
aurait servi sans choix, la liste employant le tri du résolveur
(`-est_par_defaut, name`).

**Le choix se fige sur le job**, jamais relu à l'exécution : entre la demande et
son tour dans la file, le défaut peut changer, et relire le défaut au moment de
produire ferait mentir la provenance de l'article.

**Un wiki garde son rédacteur** (`Wiki.analyseur_de_redaction`). Sans ce champ, la
mise à jour — humaine comme nocturne — retombait sur l'analyseur par défaut du
moment : le préambule changeait au milieu de l'histoire d'un article, chaque
nuit, sans qu'aucun écran ne l'annonce.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | `texte_du_prompt()` ; `PromptPiece` sans `name` ; `AnalyseurSyntaxique` sans les deux booléens |
| `hypostasis_extractor/migrations/0039_…`, `0040_…` | les deux retraits |
| `core/models.py`, `core/migrations/0081_…` | `Wiki.analyseur_de_redaction` |
| `hypostasis_extractor/services/__init__.py` | la garde d'utilisabilité couvre les **deux** types qui rédigent ; le snapshot ne garde plus les champs retirés |
| `hypostasis_extractor/views.py`, `serializers.py` | pièces sans nom, versionnage ajusté |
| `front/tasks.py` | les assemblages passent par `texte_du_prompt()` ; `_construire_prompt_synthese` sans condition ; `_analyseur_fige_sur_le_job()` ; la mise à jour suit le rédacteur du wiki |
| `front/views.py` | cinq assemblages, deux gardes retirées, compteurs de pièces |
| `front/views_synthese.py` | `_redacteurs_proposables()`, `_redacteur_choisi()`, l'analyseur figé sur les trois jobs |
| `front/services/fixtures_analyseurs.py` | sans les deux booléens |
| Gabarits | `analyseur_editor.html`, `piece_row.html`, `analyseur_item.html`, `versions_diff.html`, `confirmation_synthese.html`, `modale_prompt_readonly.html`, `liste_wikis.html`, `liste_syntheses.html` |
| `benchmarks/chaine_complete/comparer_la_chaine.py` | appelle `texte_du_prompt()` |
| Tests | `test_le_choix_de_l_analyseur_par_geste.py` (**neuf**, 8 tests) ; ajouts dans `test_le_typage_des_analyseurs.py` et `test_la_provenance_d_une_production.py` |

## ⚠️ INCIDENT DU 2 SEPTEMBRE — 3 h d'analyses en échec / A 3-hour outage

**Ce qui s'est passé.** Les migrations `0039`/`0040` ont été appliquées à la fin
de la session. **`beta.hypostasia.org` est servi par ce conteneur** : elles sont
donc parties en ligne. Le `runserver` recharge à chaud et a suivi ; les
**workers Celery, non** — ils tournaient depuis 9 jours avec l'ancien code, qui
demandait `AnalyseurSyntaxique.inclure_extractions`, colonne que `0040` venait de
retirer. Django `SELECT`e **toutes** les colonnes d'un modèle : n'importe quelle
requête sur un analyseur levait alors `column ... does not exist`.

**Ce que ça a coûté.** De 04:19 à 07:30, **toutes** les analyses ont échoué —
tous chunks en erreur, 0 extraction. **Jobs 155 à 164**, sur les pages 27, 28,
63, 65 et 66. L'échec était instantané (0,15 s), donc **aucun appel facturé** :
l'exception tombait avant le modèle. Mais rien ne le disait à l'écran.

**Ce qui l'a réparé.** `make restart S=celery_worker`, puis les deux autres
workers. Les trois répondent à `inspect ping`, l'invariant « trois workers,
jamais moins » est tenu.

**À retenir.** Après toute migration qui **retire ou renomme** une colonne :
redémarrer les **trois** workers, après avoir vérifié qu'aucun travail n'est en
vol (`inspect active`) et que la mémoire suffit (`free -h` — le juge local
recharge 6 Go au pic, et `nice` ne protège pas de l'OOM killer). L'ajout d'une
colonne ne casse rien tout de suite ; c'est le retrait qui tue.

**Les jobs 155 à 164 sont à relancer** — cette fois, ce sera facturé.

---

## Comment tester (à la main) / Manual test

### Test 1 — l'éditeur n'offre plus que ce qui compte

1. `/api/analyseurs/`, ouvrir « Rédacteur d'article ».
2. **Attendu** : aucun champ « Nom du morceau » ; aucune bascule « Inclure… » ;
   un sélecteur de **rôle** par morceau ; le type affiche « Rédiger un article ».

### Test 2 — le rôle part vraiment

```bash
docker exec -w /app hypostasia_web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','hypostasia.settings')
django.setup()
from hypostasis_extractor.models import AnalyseurSyntaxique
a = AnalyseurSyntaxique.objects.get(name=\"Rédacteur d'article\")
print(a.texte_du_prompt()[:400])
"
```

**Attendu** : chaque bloc précédé de `=== CONTEXTE ===`, `=== INSTRUCTION ===`…

### Test 3 — chaque geste propose son analyseur

1. Ouvrir un carnet, onglet **Wikis** : le sélecteur « Analyseur de rédaction »
   propose les rédacteurs actifs, le préféré marqué ★ et présélectionné.
2. Même chose sur l'onglet **Synthèses dirigées**.
3. Créer un wiki en choisissant un autre rédacteur, puis vérifier que la mise à
   jour le suit :

```bash
docker exec -w /app hypostasia_web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','hypostasia.settings')
django.setup()
from core.models import Wiki
for w in Wiki.objects.select_related('analyseur_de_redaction')[:10]:
    r = w.analyseur_de_redaction
    print(w.pk, '|', w.sujet[:40], '| rédacteur:', r.name if r else '(défaut)')
"
```

### Test 4 — une synthèse de note envoie toujours les trois choses

1. Ouvrir une note analysée, panneau des extractions, « Lancer la synthèse ».
2. **Attendu** : la ligne « Ce qui est envoyé — Texte, extractions et
   commentaires », et **aucune** bascule à lire.
