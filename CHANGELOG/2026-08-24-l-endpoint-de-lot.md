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
| `hypostasis_extractor/tests/test_le_lot_et_les_ancrages.py` | **neuf, 30 août** — 15 tests, la première fixture qui porte de vrais ancrages |

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

### Les deux chemins que rien n'exerçait — 30 août 2026

Vingt-trois tests couvraient cet endpoint, et **aucun ne posait le moindre
ancrage** : ses blocs étaient du texte nu. Trois promesses du § 7.4 n'étaient donc
jamais éprouvées, et l'une d'elles est **le chemin le plus fréquent en usage
réel** — sur la note 3, **7 blocs sur 12 sont gelés par une synthèse figée**.

**1. Le refus par synthèse figée DANS un lot.** C'est le chemin le plus délicat de
la vue : `EditionBloqueeParUneSynthese` est attrapée **à l'intérieur** du
`transaction.atomic()`, et le lot doit continuer d'écrire après elle. Si
l'exception laissait la transaction en échec, tout serait annulé au commit — mais
le compte rendu, lui, annoncerait « 1 modifié ». **La personne verrait un succès et
n'aurait rien.** Vérifié : le bloc gelé est refusé, lui seul, et les autres blocs
du même lot sont bien **écrits en base**.

**2. Les deux compteurs.** `ancres_detachees` et `citations_detachees` n'étaient
affirmés que par la présence de leur `data-testid` — jamais par un nombre. La
fixture porte désormais de vraies extractions, de vraies portions posées sur des
**offsets calculés depuis le texte** (jamais écrits à la main), et des citations
créées **par le vrai service** `indexer_les_citations`, seul chemin qui pose
`ancrage_source`.

**Ce que ces tests épinglent, et que rien ne disait avant :**

| | |
|---|---|
| un bloc cité par une synthèse **figée** | refusé, **lui seul** — le reste du lot est écrit |
| **vider** un bloc gelé | refusé aussi : le masquage passe par un autre service, même garde |
| un bloc cité par un **wiki** | **passe** — sans quoi un carnet à cinq wikis gèlerait la moitié de ses passages |
| un lot **entièrement** gelé | 0 modifié, **aucun `PageEdit`** : un journal vide serait un geste inventé |
| le journal | porte l'avant/après des blocs **passés**, et la **liste des refus** |
| une correction qui efface le passage ancré | `ancres_detachees` = 1, portion `DETACHEE` en base |
| une correction **ailleurs** dans le bloc | `ancres_detachees` = **0**, portion toujours `ANCREE` |
| la citation qui pointait la portion | `citations_detachees` = 1, `SourceLink` en `DETACHEE` |

**Le mordant est mesuré, pas supposé.** Un test neuf qui passe du premier coup ne
prouve rien tant qu'on ne l'a pas vu tomber. En neutralisant
`verifier_qu_aucune_synthese_ne_cite` dans les **deux** services (réconciliation et
masquage), **7 des 15 tests tombent** — et le texte du bloc gelé se retrouve écrit
en base, ce qui est exactement le dégât qu'ils existent pour interdire. Les deux
services ont été restaurés depuis une copie hors dépôt, empreintes vérifiées.

### Le refus NOMME désormais la synthèse qui bloque — 30 août 2026

Le lot écrivait « ce passage est cité par une synthèse figée ». Sur une note où
**7 blocs sur 12 sont gelés**, ce motif ne dit ni quelle citation retirer, ni
quelle synthèse reproduire — et le § 5.3 de `SPEC-synthese-carnet.md` exige que
le refus **nomme** ce qui bloque. Les quatre gestes unitaires le faisaient déjà,
par `_message_falc_du_blocage_par_synthese` ; le lot jetait l'exception sans
même la lier.

Il la lie, et appelle **la même fonction** — pas une seconde version du message,
qui divergerait :

> ce passage est cité par « Synthèse du 12 mars ». Une synthèse adoptée ne doit
> pas voir ses preuves changer : retirez d'abord la citation, ou produisez une
> nouvelle synthèse.

**Et ce titre est saisi par un humain**, donc il fallait le suivre jusqu'au bout :
le gabarit l'échappe (un test l'épingle sur `<img src=x onerror=…>`), et côté
client la modale du mode ne construit plus son HTML par concaténation — chaque
`<li>` passe par `textContent`.
→ `CHANGELOG/2026-08-29-le-mode-edition-par-blocs.md`, troisième temps.

### Le refus des tableaux avait une garde, mais aucun test — 30 août 2026

`LABELS_QUI_NE_SE_RELISENT_PAS` protège contre un dégât grave et silencieux —
un `Ctrl+S` sur une note à tableaux les écrasait **tous, sans que personne n'y
ait touché**. Écrite le 29, elle n'était exercée par **rien** : les deux fixtures
ne créaient que des `label="text"`. Six tests la tiennent maintenant — un tableau
modifié est refusé, son texte n'est pas écrasé, le motif dit « tableau », le
vider est refusé aussi, les autres blocs du lot passent, et **un tableau
inchangé ne produit aucun refus** (le client périmé renvoie tout, il ne doit pas
remplir le compte rendu pour ce qu'il n'a pas touché).

### La garde d'analyse manquait aux VIDAGES — 30 août 2026

Relevé par la relecture adverse, **vérifié par un test qui échouait** : le § 8.1
promet que le refus subsiste **à l'écriture**, pas seulement à l'entrée. C'était
vrai pour les corrections — `reconcilier_les_portions_de_l_element` repose la
garde bloc par bloc — et **faux pour les vidages** : le lot appelle
`masquer_un_element(..., verifier_les_jobs=False)`. Un lot fait uniquement de
vidages n'était donc protégé que par la garde d'entrée, alors que le commentaire
de la vue affirmait « les services la reposent chacun ».

**Mesuré avant correction** : une analyse démarrée pendant le lot le laissait
passer — **200 au lieu de 409**, et les blocs restaient masqués.

**La garde est reposée UNE FOIS, en fin de lot**, dans le même `atomic` :

- **une fois, pas une par bloc** — la reposer dans la boucle coûterait deux
  requêtes par bloc masqué (400 pour un nettoyage de 200 en-têtes) sans rien
  gagner : ce qui compte est qu'**aucune écriture ne soit commitée** après le
  démarrage d'une analyse, et lever ici annule le lot **entier** ;
- **seulement s'il y a eu des écritures** — un lot où rien n'a changé n'a rien à
  protéger, et le refuser dirait à la personne qu'elle a perdu un travail qu'elle
  n'a pas fait. Un second test épingle ce cas.

L'exception remonte au `except EditionBloqueePendantAnalyse` qui existait déjà :
rollback complet, 409, et le texte reste à l'écran.

### Ce qui n'est PAS fait

**Le mode d'édition l'appelle depuis le 29 août 2026** — `Ctrl+S` enregistre par
cet endpoint : `CHANGELOG/2026-08-29-le-mode-edition-par-blocs.md`.

> *À l'écriture de ces lignes, trois mesures conditionnaient encore la voie
> technique. **Elles ont été faites les 26 et 28 août, et les trois passent** :
> `CHANGELOG/2026-08-23-le-champ-unique-tranche-l-edition-par-blocs.md`.*

**Le toast du compte rendu n'est affiché par personne** — relevé par la relecture
adverse du 30 août, vérifié : `_reponse_du_compte_rendu` pose bien
`HX-Trigger: showToast`, mais **le seul appelant est le `fetch()` du mode**, qui
lit le corps et ignore les en-têtes. Ce que la personne voit est le partial, en
tête de la note, plus la modale des refus. Trois documents affirmaient le
contraire ; ils sont corrigés. **Conséquence à connaître** : un `Ctrl+S`
entièrement réussi, en bas d'une note longue, n'a pas de retour visible près du
curseur — seulement l'annonce d'`annoncer()`, qui est `sr-only`. C'est le même
défaut de visibilité que celui qui a motivé la modale des refus, et il reste
ouvert.

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
→ **33 tests, OK** (mesuré le 30 août 2026 : 17 d'origine, +2 sur la distinction
lire/écrire, +4 sur l'addendum B, **+6 sur le refus des tableaux**, **+2 sur la
borne et les doublons**, **+2 sur la garde d'analyse des vidages**).

Et le fichier qui porte les ancrages réels — le refus par synthèse figée dans un
lot, le nom de la synthèse, et les deux compteurs du compte rendu :
```bash
docker exec -w /app hypostasia_web python manage.py test \
  hypostasis_extractor.tests.test_le_lot_et_les_ancrages --noinput
```
→ **22 tests**. Avec `test_corriger_en_lot` et `front.tests.test_mode_edition` :
**79 tests** ; et toute la suite du chantier, **737 tests OK en 481 s** (mesuré
le 30 août 2026, au soir).

Toute l'app, pour la non-régression :
```bash
docker exec -w /app hypostasia_web python manage.py test hypostasis_extractor --noinput
```
→ **518 tests, OK (13 sautés), en 376 s** (mesuré le 24 août 2026).
