# L'usage du moteur ELEMENT — U1 (boutons), U2 (ingestion), U4 (capture web), sécurité, U3 (panneau), D3 (audio)

**Date :** 2026-08-10
**Migration :** Oui

## 2026-08-10 — U1 : les operations d'element ont leurs BOUTONS (mode structure de la lecture)

**Quoi / What :** les endpoints BR-E (corriger, scinder, fusionner,
masquer, demasquer) etaient prets et testes mais SANS un seul bouton.
La lecture d'une page ELEMENT gagne un MODE STRUCTURE :
- un bouton a bascule « Modifier la structure » (aria-pressed), rendu
  pour qui PEUT ECRIRE la note (filtre `est_modifiable_par`, meme
  regle que les endpoints — le bouton et le droit ne divergent pas) ;
- chaque bloc porte un groupe de boutons monospace (corriger, couper
  en deux, recoller avec le suivant, masquer), rendu par le serveur,
  INVISIBLE hors mode structure (la classe vit sur #zone-lecture et
  SURVIT au rechargement lectureReload) ;
- les elements MASQUES deviennent des placeholders demasquables
  (etiquette « Passage masqué », extrait, bouton) — visibles en mode
  structure, ABSENTS du DOM d'un simple lecteur ;
- corriger et couper ouvrent des formulaires rendus par le serveur
  dans un <dialog> natif (focus piege, Echap) ; couper se fait EN
  PLACANT LE CURSEUR dans le texte (lecture seule) puis « Couper ici ».
/ The element operations get their buttons: a structure mode on the
reading zone, server-rendered per-block button groups, un-hideable
placeholders for masked elements, native-dialog forms.

**Relecture adverse appliquee (3 HAUTE, 9 MOYENNE, 5 BASSE) — les
correctifs qui meritent d'etre retenus :**
1. HAUTE — `selectionStart` compte des unites UTF-16, le serveur coupe
   en points de code : un emoji avant le curseur decalait la coupe
   d'un cran, EN SILENCE. Conversion `Array.from(...)` a l'envoi.
2. HAUTE — le parseur HTML avale le premier retour a la ligne apres
   `<textarea>` : un texte commencant par \n perdait un caractere
   (offsets faux, correction « identique » qui reconcilie). Les deux
   formulaires prefixent un \n VOLONTAIRE.
3. HAUTE — la position de coupe n'a de sens que sur le texte AFFICHE :
   l'empreinte du texte voyage avec le formulaire et le serveur
   compare SOUS LE VERROU — texte change entre-temps = 409 FALC, pas
   une coupe posee sur un autre texte.
4. HAUTE — l'include des boutons injectait ~24 retours a la ligne
   VISIBLES dans les blocs `<pre>` (white-space:pre) : gabarit reecrit
   sans un blanc hors du span + `white-space:normal`.
5. Un pk mort (l'element vient d'etre scinde/fusionne par un autre)
   repond un toast FALC + rechargement — plus jamais la page 404
   brute dans un SweetAlert. `hx-disabled-elt` contre le double-clic.
6. Le toast d'erreur passait SOUS le voile du dialogue modal (top
   layer) : une zone role="alert" DANS le dialogue reprend le message.
7. Un script inline injecte par innerHTML ne s'execute JAMAIS : la
   resynchronisation aria-pressed + focus vit dans le gestionnaire
   lectureReload (hypostasia.js). Session expiree (403 nu DRF) =
   invite de connexion au lieu d'un echec silencieux.
8. Les boutons ne sortent plus DANS les h2/h3 (nom accessible du titre
   pollue) ; « recoller » n'est pas propose quand le suivant est
   masque ; messages de scission/fusion FALC dedies (jamais
   str(erreur) brut) ; droit evalue UNE fois par rendu (M7).
Consignes sans code : oracle 403/404 des endpoints element (coherent
avec BR-F, a trancher globalement), textarea readonly peu fiable sur
iOS, aria-live large de #zone-lecture, \r\n theorique (0 en base).

37 tests neufs/renforces (test_boutons_elements 16, test_views_element
+13, test_lecture_elements adapte). 93 verts sur le perimetre.

**Verification au navigateur reel (agent Opus, clair + sombre,
contrastes CALCULES)** : fonctionnel entierement conforme (bascule,
9 groupes de boutons, dialogues modaux avec focus piege et Echap,
erreur de scission DANS le dialogue, cycle masquer/demasquer reversible
prouve — etat de la base identique avant/apres, aria-pressed conserve a
travers lectureReload, anonyme sans un seul bouton, zero erreur JS).
Tous les contrastes au-dessus des seuils (boutons 5,4-6,2:1, contours
3,3-4,4:1, dialogue 14,5-16,8:1, focus 5,9-6,6:1). Cinq defauts, TROIS
CORRIGES dans la foulee : le <dialog> se collait en haut a gauche (le
preflight Tailwind `*{margin:0}` ecrase le centrage natif — `margin:
auto` retabli) ; en sombre le modal ne se detachait pas du voile
(1,08:1 — bordure passee a --filet-controle + ombre) ; la zone d'erreur
n'avait aucun style (filet gauche danger, grammaire des etats). Cibles
tactiles montees a 24 px (WCAG 2.5.8). CONSIGNES : le toast d'erreur
s'affiche brievement EN PLUS de la zone du dialogue (duplication de
4,5 s assumee) ; les boutons d'un titre s'affichent sous lui, entre
titre et paragraphe (l'aria-label leve l'ambiguite, cosmetique a
revoir).

| Fichier | Changement |
|---|---|
| `front/templates/front/includes/_actions_element.html` | **nouveau** : le groupe de boutons d'un bloc |
| `front/templates/front/includes/_blocs_elements.html` | placeholders masques, boutons, listes toutes-masquees |
| `front/templates/front/includes/_formulaire_element_correction.html` | **nouveau** : dialogue de correction |
| `front/templates/front/includes/_formulaire_element_scission.html` | **nouveau** : dialogue de scission (curseur) |
| `front/templates/front/includes/lecture_principale.html` | bascule mode structure, conteneur du dialogue |
| `hypostasis_extractor/views_element.py` | 2 actions GET formulaires, empreinte, messages FALC, pk morts |
| `hypostasis_extractor/serializers.py` | `empreinte_du_texte` sur la scission |
| `front/services/rendu_elements.py` | `fusion_possible`, `toutes_masquees` |
| `front/templatetags/corpus_permissions.py` | filtre `est_modifiable_par` |
| `front/static/front/js/hypostasia.js` | `basculerModeStructure`, resync lectureReload, 403 nu, anti double-Swal |
| `front/static/front/css/maquette.css` | section U1 (actions, placeholders, dialogue) |

### Migration
- **Migration necessaire / Migration required :** Non.

## 2026-08-10 — U2 : l'ingestion Docling n'echoue plus en silence

**Quoi / What :** la dette n°1 du § 5 du cahier de branchement. Quand
la conversion Docling echouait, la page restait ANCIEN et lisible mais
RIEN ne le disait, et aucune relance n'existait — le journal Celery
faisait foi. Desormais :
- l'ETAT du decoupage vit sur la Page (`ingestion_etat` : en_attente /
  en_cours / reussie / echouee + `ingestion_detail` FALC), ecrit par la
  vue d'import (en_attente), par la tache (en_cours puis
  reussie/echouee, messages simples — le detail technique reste au
  journal), et par la relance ;
- la lecture montre une PUCE d'etat a qui peut ecrire : attente/cours
  avec sonde auto-rafraichie 5 s (patron F1/F2 : plafond d'essais ~5
  min, puis « Verifier a nouveau » — un worker mort devient un message,
  pas un poll infini) ; echec avec le detail et « Relancer le
  decoupage ». La reussite est SILENCIEUSE a l'ecran : la sonde repond
  vide + lectureReload, la lecture passe aux blocs toute seule ;
- la RELANCE manuelle est gardee : droit d'ecriture, pas pendant une
  ingestion active (409), pas sur une page qui a deja ses elements
  (409 — la re-ingestion qui preserve les ancres est un autre flux),
  type couvert par Docling seulement, broker en panne = 503 honnete.
/ Docling ingestion failures now show a status chip with a guarded
manual relaunch; success silently reloads the reading.

17 tests (front/tests/test_ingestion_ui.py). Migration core.0054
appliquee sur dev : 4 pages ELEMENT estampillees reussie ; les 537
pages ANCIEN aux elements dormants restent vierges (§ 9.2).

| Fichier | Changement |
|---|---|
| `core/models.py` | `EtatIngestion`, `Page.ingestion_etat/_detail` |
| `core/migrations/0054_page_ingestion_etat.py` | **nouvelle** : schema + estampillage ELEMENT |
| `hypostasis_extractor/tasks_element.py` | la tache ecrit les etats, messages FALC |
| `front/views.py` | etat en_attente a l'import ; actions `etat_ingestion` (sonde) et `relancer_ingestion` |
| `front/templates/front/includes/_etat_ingestion.html` | **nouveau** : la puce d'etat |
| `front/templates/front/includes/lecture_principale.html` | inclusion de la puce |
| `front/static/front/css/maquette.css` | styles de la puce (filet gauche danger en echec) |

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0054`
  (appliquee sur dev le 10 aout).

## 2026-08-10 — U3 : les cartes du panneau suivent le DOCUMENT, l'estimation compte les chunks REELS

**Quoi / What :** les deux restes cosmetiques § 5 du cahier de
branchement (consignes BR-C/BR-D) :
1. Le drawer des extractions d'une page ELEMENT etait trie par
   `start_char` — un offset DE CHUNK pour ce moteur : les cartes de
   chunks differents s'entrelacaient. Le tri « position » suit
   desormais l'ANCRE (ordre de l'element, debut dans l'element, via la
   premiere portion non detachee) ; les extractions sans portion
   ferment la marche au lieu de s'intercaler au hasard. L'ANCIEN
   moteur garde start_char (offset de page, fiable).
2. L'estimation du drawer d'analyse chunkait `text_readability` a
   l'arithmetique ; pour une page ELEMENT elle rejoue desormais le
   VRAI decoupage (`construire_les_chunks` sur les elements visibles) :
   nombre de chunks exact, overhead de prompt compte juste.
/ Anchor-ordered extraction cards and real chunk counts for ELEMENT
pages; OLD pages unchanged.

5 tests (front/tests/test_restes_moteur_element.py).
Fichiers : front/views.py (`_trier_les_entites_par_ancre`,
`drawer_contenu`, `previsualiser_analyse`).

### Migration
- **Migration necessaire / Migration required :** Non.

## 2026-08-10 — U4 : la capture web nourrit le moteur ELEMENT

**Quoi / What :** apres l'import fichier (BR-B), c'est au tour de la
capture web (extension navigateur, `POST /api/pages/`) de basculer sur
le moteur ELEMENT (decision D2, ordre 2). Meme patron :
- la source est `page.html_original` (le HTML capture), pas un fichier
  sur disque : Docling convertit un `DocumentStream` nomme `.html`
  (`convertir_du_html_avec_docling`, service `ingerer_une_capture_web`) ;
- la tache `ingerer_une_capture_web_avec_docling` partage la MEME file
  dediee `ingestion_docling` (concurrence 1) — une conversion a la
  fois sur l'hote 8 Go, fichier ou HTML confondus ;
- double ecriture de transition : le pipeline synchrone a rempli
  `html_readability`, l'affichage reste ANCIEN jusqu'a ce que les
  elements existent ; la page devient ELEMENT quand la tache aboutit ;
- repli honnete + etat U2 : un echec laisse une page ANCIEN lisible,
  la puce d'etat le dit et permet la relance ; broker en panne = la
  capture reste un succes, sans fausse promesse.
/ Web capture now feeds the ELEMENT engine, same pattern as file
import: background Docling conversion of the captured HTML on the
shared dedicated queue, honest fallback, U2 state surfaced.

7 tests (front/tests/test_capture_web_docling.py).

| Fichier | Changement |
|---|---|
| `hypostasis_extractor/services/ingestion_docling.py` | `convertir_du_html_avec_docling`, `ingerer_une_capture_web` |
| `hypostasis_extractor/tasks_element.py` | tache `ingerer_une_capture_web_avec_docling` (etats U2, repli) |
| `hypostasia/celery.py` | la tache web partage la file `ingestion_docling` |
| `core/views.py` | `PageViewSet.create` lance l'ingestion web + etat en_attente |

### Migration
- **Migration necessaire / Migration required :** Non.

## 2026-08-10 — SECURITE : quatre lectures d'extractions ne verifiaient aucune permission

**Quoi / What :** decouvert en preparant U3 — quatre actions GET
d'`ExtractionViewSet` (front/views.py) ne controlaient RIEN :
- `/extractions/drawer_contenu/?page_id=N` donnait le TEXTE de toutes
  les extractions de n'importe quelle page, plus les noms des
  contributeurs, SANS ETRE CONNECTE — la meme famille que la faille de
  l'alignement corrigee le 9 aout ;
- `/extractions/carte_mobile/?entity_id=N` : une extraction et son
  activite ; `/extractions/dashboard/` : les stats de debat ;
  `/extractions/formulaire_promouvoir/` : le titre (et un oracle
  d'existence).
/ Four unauthenticated extraction READ endpoints leaked private
content — same family as the alignment hole fixed on Aug 9.

**Correctif** : la regle du produit (`_utilisateur_a_acces_page`,
SPEC-corpus § 5.2) + doctrine du 404 — l'interdit repond au MEME OCTET
que l'absent (`Http404` au message identique a get_object_or_404, DRF
le transmet). Une note d'un carnet public reste lisible : c'est la
regle, pas un mur de connexion.

**Preuve que les tests mordent** : garde du drawer neutralisee
temporairement -> 3 tests tombent (200 != 404) -> garde restauree.
9 tests (front/tests/test_extractions_permissions.py), dont l'octet
identique interdit/absent et la non-regression note publique.

**La FAMILLE n'etait pas eteinte (relecture adverse) — le reste
corrige dans la foulee.** Constat de fond : le projet n'a AUCUN
`DEFAULT_PERMISSION_CLASSES` — chaque ViewSet est `AllowAny` sauf garde
manuelle. Restaient :
- des LECTEURS ANONYMES rendant le texte integral d'une note privee :
  `/lire/<pk>/exporter/` et `previsualiser_analyse` (le prompt complet
  contient tout le texte — aussi grave que le drawer),
  `previsualiser_synthese`, `telecharger_source`, les formulaires
  audio, `panneau`, `manuelle` -> garde de lecture ;
  `/questionnaire/?page_id=` -> doctrine du 404 ;
- des IDOR authentifies : `modifier_titre`, `renommer_locuteur`,
  `editer_bloc`, `supprimer_bloc`, `creer_manuelle`, `ia` (analyse LLM
  payante) -> droit d'ecriture ; `supprimer_ia` (destructif) et
  `promouvoir_entrainement` (copie le texte dans un exemple GLOBAL) ->
  proprietaire ; `ajouter_commentaire`, `poser_question`, `repondre`
  -> acces en lecture (le debat est ouvert a qui peut LIRE) ;
  `DossierViewSet.partager` (le GET fuyait les emails des invitations,
  le POST modifiait les partages du dossier d'AUTRUI) -> owner du
  dossier. 19 tests (front/tests/test_permissions_famille.py), preuve
  de morsure faite (garde de l'export neutralisee -> le test tombe).

### Migration
- **Migration necessaire / Migration required :** Non.

## 2026-08-10 — Mesure D3 : la frontiere audio est TRANCHEE par les chiffres

**Quoi / What :** la question ouverte n°1 de SPEC-ancrage (frontiere
preferentielle du chunking audio) est fermee par une MESURE sur les 24
transcriptions diarisees reelles de la base dev (2 153 tours de
parole), pas par une opinion. Protocole rejouable :
`tmp/mesure_d3_audio.py` ; chiffres complets :
`PLAN/mesure-D3-frontiere-audio-2026-08-10.md` ; addendum date dans la
spec. / Open question #1 settled by measurement on 24 real diarised
transcriptions.

**Les trois decisions que les chiffres imposent :**
1. PAS de frontiere preferee au changement de locuteur : +12,6 %
   d'appels LLM pour 2 points de gain (chunks multi-locuteurs 59,3 %
   → 57,3 %) — un tour median fait 125 caracteres, l'attribution est
   portee par l'ancre M2M, pas par la frontiere.
2. L'element audio est le TOUR DE PAROLE, pas le segment ASR :
   elements=segments donnerait 605 coupes en plein tour (85 % des
   frontieres internes), elements=tours zero.
3. Un tour au-dela du budget (6,5 % des tours, max observe 34 715
   caracteres — un podcast) est scinde A L'INGESTION a la frontiere de
   segment la plus proche du budget, sinon la regle « jamais couper un
   element » enverrait des chunks de 35 000 caracteres au LLM.

Aucun code de production touche : c'est le prealable exige avant la
bascule audio (decision D2, ordre 3).

### Migration
- **Migration necessaire / Migration required :** Non.

---

> Écrit le 10 août 2026. Réfère : SPEC-ancrage-par-element-v2.md (addendums
> du 10 août), PLAN/branchement-moteur-ancrage-cahier-des-charges.md § 5,
> PLAN/mesure-D3-frontiere-audio-2026-08-10.md, CHANGELOG du 10 août.

## Ce qui a été livré

### U1 — le mode structure de la lecture
- Bouton à bascule « Modifier la structure » sur toute page ELEMENT dont
  on peut écrire (même règle que les endpoints : `est_modifiable_par` →
  `_utilisateur_peut_ecrire_page`). La classe `mode-structure` vit sur
  `#zone-lecture` et survit aux rechargements.
- En mode structure, chaque bloc porte : **corriger** (dialogue avec
  textarea), **couper en deux** (dialogue : placer le curseur puis
  « Couper ici »), **recoller avec le suivant** (confirmation ; absent sur
  le dernier bloc et quand le suivant est masqué), **masquer**
  (confirmation).
- Les éléments masqués deviennent des placeholders « Passage masqué »
  (extrait + bouton **démasquer**), visibles en mode structure seulement,
  absents du DOM des simples lecteurs.
- Sécurité d'offsets de la scission : conversion UTF-16 → points de code,
  retour à la ligne volontaire après `<textarea>`, empreinte du texte
  affiché vérifiée sous le verrou (409 « modifié entre-temps »).

### U2 — l'ingestion ne se tait plus
- État du découpage sur la Page (`ingestion_etat` + `ingestion_detail`),
  migration core.0054 appliquée sur dev (4 pages ELEMENT estampillées).
- Puce d'état dans la lecture (écrivains seulement) : attente/cours
  auto-rafraîchie (plafond ~5 min puis « Vérifier à nouveau »), échec
  avec détail FALC + « Relancer le découpage ». Réussite silencieuse :
  la lecture se recharge en blocs.
- Relance gardée : écriture requise, refus 409 si ingestion active ou
  éléments déjà présents, type couvert seulement, broker mort = 503.

### U4 — la capture web nourrit le moteur ELEMENT
- `POST /api/pages/` (extension) lance
  `ingerer_une_capture_web_avec_docling` en plus de la création
  synchrone. Source = `html_original`. Même file dédiée, double
  écriture, repli honnête, état U2.
- Une capture aboutie devient `moteur=element` et se lit en blocs ; un
  échec reste ANCIEN lisible avec la puce d'échec + relance.

### Sécurité — extractions ET la famille entière des endpoints
`drawer_contenu`, `carte_mobile`, `dashboard`, `formulaire_promouvoir`
ne vérifiaient aucune permission (fuite anonyme du texte des
extractions). Garde `_utilisateur_a_acces_page` + 404 au même octet que
l'absent. Preuve de morsure faite (garde neutralisée → 3 tests tombent).

La relecture adverse a montré que la famille N'ÉTAIT PAS éteinte : le
projet n'a **aucun `DEFAULT_PERMISSION_CLASSES`** (tout est `AllowAny`
par défaut). Bouché à son tour :
- **lecteurs anonymes** rendant le texte intégral d'une note privée :
  `/lire/<pk>/exporter/`, `previsualiser_analyse` (le prompt complet
  contient tout le texte), `previsualiser_synthese`,
  `telecharger_source`, les deux formulaires audio, `panneau`,
  `manuelle` → garde de lecture ; `/questionnaire/?page_id=` → 404 ;
- **IDOR authentifiés** : `modifier_titre`, `renommer_locuteur`,
  `editer_bloc`, `supprimer_bloc`, `creer_manuelle`, `ia` (analyse
  payante) → droit d'écriture ; `supprimer_ia`,
  `promouvoir_entrainement` (copie le texte dans un exemple global) →
  propriétaire ; `ajouter_commentaire`, `poser_question`, `repondre`
  → accès en lecture (le débat est ouvert à qui peut lire) ;
  `DossierViewSet.partager` (fuyait les emails d'invitation, POST
  modifiait les partages d'autrui) → owner du dossier.
28 tests dédiés (`test_extractions_permissions` 9 +
`test_permissions_famille` 19).

### U3 — les restes § 5
- Drawer d'une page ELEMENT trié par ancre (ordre d'élément, début dans
  l'élément) ; sans portion → en queue. ANCIEN inchangé.
- Estimation d'analyse d'une page ELEMENT : `construire_les_chunks`
  réel sur les éléments visibles (nombre de chunks exact).

### D3 — mesure audio (aucun code de production)
Voir PLAN/mesure-D3-frontiere-audio-2026-08-10.md : pas de frontière
préférentielle au changement de locuteur ; élément audio = tour de
parole ; tours > 1 500 c scindés à l'ingestion. Addendum daté posé dans
la spec.

## Tests à réaliser à la main

1. **Mode structure** (connecté, propriétaire d'une note ELEMENT — ex.
   page 674) : le bouton « Modifier la structure » apparaît sous la
   ligne Historique. Cliquer : les boutons apparaissent sur chaque bloc,
   `aria-pressed` passe à true. Recliquer : tout disparaît.
2. **Corriger** : ouvrir, modifier un mot, enregistrer → toast, la
   lecture se recharge, le mode structure est TOUJOURS actif et le
   bouton bascule annonce toujours « enfoncé ».
3. **Couper en deux** : placer le curseur au milieu d'une phrase,
   « Couper ici » → deux blocs. « Recoller avec le suivant » sur le
   premier → un seul bloc, texte intact.
4. **Couper sans placer le curseur** : le message d'erreur apparaît DANS
   le dialogue (« Placez d'abord le curseur… »), le dialogue reste
   ouvert.
5. **Masquer/démasquer** : masquer un bloc → il devient « Passage
   masqué » (extrait + démasquer). Quitter le mode structure : le
   placeholder disparaît de la lecture. Démasquer → le bloc revient.
6. **Simple lecteur** : ouvrir la même note avec un compte qui peut la
   lire sans pouvoir l'écrire (ou en navigation privée si publique) :
   AUCUN bouton, AUCUN placeholder dans le DOM (inspecter).
7. **Sécurité** : déconnecté,
   `curl -s https://hyp.nasjo.fr/extractions/drawer_contenu/?page_id=1`
   → 404, aucun texte d'extraction.
8. **Panneau (U3)** : sur une note ELEMENT analysée (page 676), ouvrir
   le drawer des extractions : les cartes suivent l'ordre du texte, pas
   d'entrelacement.
9. **Estimation (U3)** : bouton analyser sur une note ELEMENT → le
   nombre de chunks affiché correspond aux éléments réels.
10. **Deux onglets** (concurrence) : ouvrir « couper en deux » dans
    l'onglet A, corriger le même passage dans l'onglet B, envoyer la
    coupe dans A → 409 « modifié entre-temps », rien n'est coupé.
11. **Ingestion (U2), chemin nominal** : importer un `.md` → la note
    s'ouvre avec la puce « Découpage en éléments en attente… » qui
    passe à « en cours », puis disparaît quand la lecture se recharge
    en blocs (toast « Découpage en éléments terminé »).
12. **Ingestion (U2), échec + relance** : simuler un échec
    (`docker exec hypostasia_dev_web python manage.py shell -c
    "from core.models import Page, EtatIngestion;
    Page.objects.filter(pk=<pk>).update(ingestion_etat='echouee',
    ingestion_detail='La conversion du fichier a échoué.')"`) →
    recharger la note : puce d'échec avec le détail et « Relancer le
    découpage ». Cliquer : la puce repasse en attente, la vraie tâche
    tourne, la note finit en blocs. Un lecteur sans droit d'écriture ne
    voit jamais la puce.

## Vérifications en base utiles

```bash
docker exec hypostasia_dev_web python manage.py shell -c "
from core.models import ElementDocument
e = ElementDocument.objects.filter(page_id=674).order_by('ordre')
print([(x.ordre, x.masque, x.texte[:30]) for x in e])"
```

## Limites consignées (pas corrigées)
- Oracle 403/404 des endpoints élément (un tiers authentifié distingue
  « existe » de « n'existe pas ») — cohérent avec le reste du dépôt,
  consigné depuis BR-F, à trancher globalement.
- Textarea readonly : poser le curseur est peu fiable sur iOS Safari —
  le message d'erreur FALC rattrape (« Placez d'abord le curseur »).
- `aria-live` sur `#zone-lecture` (préexistant) : chaque opération
  fait relire la zone aux lecteurs d'écran.
- Éléments à `\r\n` : offsets théoriquement décalés (0 cas en base dev ;
  Docling n'en produit pas).
- Échap/Annuler jette la saisie de correction sans confirmation.

