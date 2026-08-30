# L'endpoint de lot : enregistrer une session d'édition / The batch endpoint: saving an editing session

**Date :** 2026-08-24
**Migration :** Non

## Résumé / Summary

**Quoi / What :** `POST /elements/corriger_en_lot/` reçoit une liste de
`{identifiant_stable, texte}` et enregistre une session d'édition entière : il
corrige ce qui a changé, **masque** ce qui a été vidé, ne touche pas au reste, et
rend un **compte rendu à cinq nombres avec la liste des refus**.
/ A batch endpoint that saves a whole editing session and reports on it.

**Pourquoi / Why :** c'est le point 2 des trois choses que le § 11 de
`SPEC-edition-par-blocs-et-stenotypie.md` demandait d'écrire « sans attendre » —
celles qui servent **les trois voies** d'édition indifféremment. Les deux autres
sont faites : la fusion des provenances (23 août) et le swap ciblé (23-24 août).

### Les quatre décisions de la spec, et ce qui les rend vraies

**1. On compare le TEXTE BRUT, jamais l'empreinte normalisée (§ 7.2).**
`empreinte_du_texte()` met en minuscules et écrase les espaces. Comparer dessus
jetterait **en silence** toute correction de casse et toute correction d'espace —
les plus fréquentes en transcription — alors que ces deux-là **déplacent les
offsets** de tout ce qui suit. Deux tests l'épinglent, et chacun **vérifie d'abord
que son jeu d'essai a bien la même empreinte normalisée** : sans cette assertion,
le test passerait sans rien prouver.

**2. Un bloc vidé est MASQUÉ, jamais supprimé (§ 7.3).** `AncrageExtraction.element`
est en `PROTECT` : un `delete()` lèverait sur tout bloc portant une portion. Un
texte fait uniquement d'espaces compte comme vide.

**3. La portée des refus n'est pas la même pour tous (§ 8.1).**

| Refus | Portée |
|---|---|
| un bloc a **disparu** (un tiers a scindé, fusionné, réingéré) | **ce bloc seul** — les autres passent |
| un passage est cité par une **synthèse figée** | **ce bloc seul** |
| une **analyse** tourne | **le lot ENTIER**, 0 passé, tout annulé |
| l'envoi mélange **deux notes** | 400, rien n'est écrit |

**Et jamais de `lectureReload`, même quand tout est refusé.** Recharger la page de
qui vient d'enregistrer effacerait le texte qu'il n'a pas réussi à sauver —
exactement ce qu'il faut lui laisser pour retaper.

**4. Un `PageEdit` par LOT, pas un par bloc (§ 10).** C'est le geste que l'humain a
fait. Il porte l'avant et l'après de chaque bloc touché, par `identifiant_stable`.

### La borne, et ce qu'elle écarte

Un lot fait un verrou et une réconciliation **par bloc modifié**. La borne est à
**500**, soit 2,4× la plus grosse note de la base (210 blocs, mesuré le 23 août) :
aucune note réelle ne la rencontre. Et ce qu'elle écarterait est **compté et nommé**
dans le compte rendu — jamais jeté en silence, selon la règle du dépôt.

### Les citations détachées sont un nombre À PART

Masquer détache aussi des **citations** (`SourceLink` de type `CITE`), et pas
seulement des ancres : vider trente en-têtes peut détacher des dizaines de sources
d'articles **sans aucun refus**, parce qu'un wiki est vivant. C'est acceptable, mais
**jamais silencieux** — d'où le cinquième nombre.

Les services les détachent eux-mêmes (`detacher_les_citations_des_portions`) sans en
rendre le compte : l'endpoint les compte donc **avant et après**, sur les portions de
la page.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/serializers.py` | `UnBlocDuLotSerializer` et `CorrectionEnLotSerializer` (+ la borne) |
| `hypostasis_extractor/views_element.py` | l'action `corriger_en_lot` et `_reponse_du_compte_rendu()` |
| `front/templates/front/includes/_compte_rendu_du_lot.html` | **neuf** — cinq nombres, la liste des refus, `role="status"` + `aria-live` |
| `hypostasis_extractor/tests/test_corriger_en_lot.py` | **neuf** — 17 tests |

**Deux écarts assumés avec `CorrectionDElementSerializer`** : l'identifiant est
l'`identifiant_stable` (le pk désigne une ligne, l'identifiant stable désigne un
bloc), et le **texte vide est permis** — le refuser interdirait le geste central du
nettoyage post-Docling.

### Le coût, mesuré le 26 août 2026

Sur la plus grosse note de la base — **210 blocs, 58 770 caractères** —, machine au
repos (charge 0,32 à 0,65), chaque essai dans une transaction **annulée** (210
éléments relus après coup : **0 modifié**) :

| Ce qu'on envoie | durée | ce que le lot fait |
|---|---|---|
| les 210 blocs, **tous modifiés** | **9 161 ms** | 191 modifiés, 19 refusés (synthèse figée) |
| les 210 blocs, **21 touchés** — une session ordinaire | **1 164 ms** | 19 modifiés |
| les 210 blocs, **30 vidés** — le nettoyage post-Docling | **1 240 ms** | 30 masqués |
| les 210 blocs, **aucun changement** | **295 ms** | rien |

**Trois choses à retenir.**

1. **Le plancher est de 295 ms** : c'est ce que coûte de recevoir 210 blocs, hacher
   leur texte brut, compter les citations et rendre le compte rendu — même quand
   rien n'a bougé. Une session ordinaire tourne autour de **1,2 s**, ce qui est le
   bon ordre de grandeur pour un `Ctrl+S` explicite.
2. **Le pire cas tient 9,2 secondes**, soit ~48 ms par bloc réellement modifié — et
   il garde **191 verrous de ligne** pendant tout ce temps. C'est le prix de la
   réconciliation, qui relit et repositionne les portions bloc par bloc.
3. **La borne de 500 borne le NOMBRE, pas le TEMPS.** 500 blocs modifiés prendraient
   ~24 s. Elle n'est pas baissée pour autant : **refuser d'enregistrer le travail de
   quelqu'un est pire que d'être lent**, et aucune note réelle n'approche cette
   taille. La parade, le jour où ça gênera, est côté client — n'envoyer que les
   blocs changés — ou par découpage en plusieurs requêtes ; pas en rabotant la borne.

Le banc est dans `benchmarks/edition_par_blocs/banc/cout_d_un_gros_lot.py`.

> **Un piège de mesure, payé ici** : appeler la vue par `RequestFactory` rend un
> **403 CSRF** silencieux, et un banc bâti dessus « mesure » 2 ms au lieu de 9 s.
> Il faut `rest_framework.test.force_authenticate`. Et un **second** 403 attendait
> derrière : la page 19 appartient à `thales`, pas à `jonas` — le contrôle de droit
> faisait son travail, et le banc mesurait le refus.

### Addendum B — corriger un bloc MASQUÉ est refusé (29 août 2026)

Ni le § 5.3 ni le § 7.3 ne disaient ce que le lot devait faire d'un bloc **déjà
masqué** dont le client envoie du **texte non vide**. Le code le faisait, et mal.

**Ce que cela coûtait, mesuré** — `demasquer_un_element` ne rattache ses portions
que si le texte n'a pas bougé depuis le masquage (il compare deux empreintes du
texte **brut**). Un lot qui corrige un bloc masqué passe **entre les deux**. Sur un
élément de la page 19 portant **3 portions**, en transaction annulée :

| | rattachées au démasquage | laissées détachées |
|---|---|---|
| masquer → démasquer | **3** | **0** |
| masquer → **corriger** → démasquer | **0** | **3** |

**Les trois ancres étaient perdues définitivement**, et le compte rendu annonçait
« 1 bloc modifié » — pour un bloc que le champ n'affiche même pas.

**La décision** : ce bloc est **refusé**, lui seul, avec son motif. Le client ne
devrait jamais envoyer ce texte — en mode édition un élément masqué est rendu comme
un **placeholder**, pas comme un bloc modifiable. Le recevoir signifie que la vue du
client est **périmée**, exactement comme pour un bloc disparu.

**Vérifié par l'endpoint réel**, en transaction annulée : le bloc est nommé dans le
refus, **le texte ne bouge pas**, et le démasquage rattache de nouveau **3 portions
sur 3**.

**Ce que le refus n'est pas** : vider un bloc déjà masqué reste un **non-geste** —
rien d'écrit, rien de compté, aucun journal. Et vider puis re-remplir dans la même
session ne refuse rien : le bloc n'a jamais été masqué en base.

**Ce que cela laisse ouvert** : le mode ne sait toujours pas **démasquer** (§ 5.3,
cas 4). Corriger un bloc masqué demande d'en sortir, de le rétablir, d'y revenir —
un aller-retour de trop, et ce refus le rend visible.

Spec : **addendum B**. Bancs : `mesures17_bloc_masque.py`,
`mesures18_le_refus_protege.py`.

### Ce qui n'est PAS fait

**Aucun front ne l'appelle** — le mode d'édition n'existe pas.

> *À l'écriture de ces lignes, trois mesures conditionnaient encore la voie
> technique. **Elles ont été faites les 26 et 28 août, et les trois passent** :
> `CHANGELOG/2026-08-23-le-champ-unique-tranche-l-edition-par-blocs.md`.*

**Le compte rendu n'est pas encore annoncé** : la région porte `role="status"` et
`aria-live="polite"`, mais `annonces.js` n'annonce que les toasts — le § 9 de la
spec demande de trancher entre un résumé en toast et une région live dédiée. Le
toast porte le résumé ; le détail attend son écran.

---

## Comment tester (à la main) / Manual test

### Test 1 — une correction de casse est bien enregistrée
```bash
docker exec hypostasia_web python manage.py shell -c "
from core.models import ElementDocument
e = ElementDocument.objects.filter(page_id=3).order_by('ordre').first()
print(e.identifiant_stable, repr(e.texte[:60]))
"
```
Puis, connecté sur https://beta.hypostasia.org/ (`jonas` / `admin1234`), poster le
même texte avec **une seule lettre de casse changée** :
```bash
curl -X POST https://beta.hypostasia.org/elements/corriger_en_lot/ \
  -H "Content-Type: application/json" -b cookies.txt \
  -H "X-CSRFToken: <jeton>" \
  -d '{"blocs":[{"identifiant_stable":"<uuid>","texte":"<le texte, une casse changée>"}]}'
```
**Attendu** : `1 bloc modifié` dans le compte rendu — et le texte change en base.
Une comparaison sur l'empreinte normalisée aurait rendu `0 modifié`.

### Test 2 — un bloc vidé est masqué, pas supprimé
Poster `{"texte": ""}` sur un bloc. **Attendu** : `1 bloc masqué`, l'élément existe
toujours en base avec `masque=True`, et ses portions sont passées en `DÉTACHÉE`.

### Test 3 — un identifiant inventé est refusé, et nommé
Poster un `identifiant_stable` au hasard avec un bloc valide.
**Attendu** : le bloc valide passe, le faux est **refusé et nommé** dans la liste,
avec son motif — et **aucun `lectureReload`** dans le `HX-Trigger`.

### Tests automatiques
```bash
docker exec -w /app hypostasia_web python manage.py test \
  hypostasis_extractor.tests.test_corriger_en_lot --noinput
```
→ **23 tests, OK** (mesuré le 29 août 2026 : 17 d'origine, +2 sur la
distinction lire/écrire, +4 sur l'addendum B).

Toute l'app, pour la non-régression :
```bash
docker exec -w /app hypostasia_web python manage.py test hypostasis_extractor --noinput
```
→ **518 tests, OK (13 sautés), en 376 s** (mesuré le 24 août 2026).
