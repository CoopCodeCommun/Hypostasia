# Le locuteur, l'aide qui lit la table, et la doc qui mentait

> **⚠️ Encart du 22 septembre 2026 — la passe de nuit n'existe plus.**
> Elle a été retirée le 21 septembre 2026 (`CHANGELOG/2026-09-21-la-mise-a-jour-des-wikis-redevient-un-geste.md`) :
> aucune tâche planifiée n'appelle plus de modèle, et mettre un wiki à jour est
> un geste humain — le bouton « Mettre à jour » de son article. **Tout ce que ce
> fichier dit de la nuit est donc de l'histoire**, y compris la commande
> `mettre_a_jour_les_wikis`, supprimée, et le module de tests
> `front/tests/test_la_passe_de_nuit_des_wikis.py`, supprimé lui aussi. Ce qui
> reste vrai : la provenance s'écrit toujours, sur le chemin du geste.
/ The speaker, the help that reads the table, and the lying docs

**Date :** 2026-09-01
**Migration :** Non

## Résumé / Summary

**Quoi / What :** quatre chantiers d'un coup — un geste **natif ELEMENT** pour
corriger qui parle, l'**aide** qui rend la table des raccourcis au lieu de la
recopier, l'**accessibilité** du mode mesurée de bout en bout, et **six documents
qui affirmaient le contraire du code**.
/ A native speaker-fix gesture, a help screen that renders the shortcut table, a
measured accessibility pass, and six documents corrected.

**Pourquoi / Why :** ce sont les restes nommés par la session du 30 août et par la
note « la doc ment sur la nuit et la vérification » du 23 août, supprimée
aujourd'hui puisque son intention est faite.

---

## 1. Corriger qui parle — un geste natif, parce que l'ancien refusait

**Le geste existait, et il ne servait à rien.** `PageViewSet.renommer_locuteur`
porte les trois portées depuis PHASE-27a, mais il **refuse en 409 toute note qui
porte des éléments** — c'est-à-dire toute note réelle depuis que le moteur ELEMENT
est le seul (10 août 2026). La spec § 6.2 affirmait pourtant « le renommage
EXISTE, ce qui manque est son accès » : c'était faux, et lui donner un raccourci
n'aurait fait que répondre 409 plus vite.

**Son refus dit lui-même pourquoi il ne pouvait pas être recyclé** : un BLOC groupe
les segments consécutifs d'un même locuteur, alors que l'ingestion crée **un
élément par segment** et saute les vides. « bloc N = élément ordre N » n'est vrai
que sur un corpus qui alterne les locuteurs — la fixture de dev, précisément.

`POST /elements/<pk>/renommer_le_locuteur/` vise donc l'élément **par son pk**.

| Portée | Ce qu'elle touche |
|---|---|
| `ce_bloc_seul` | ce tour, et lui seul — **la réattribution d'un tour**, le geste que la diarisation rend nécessaire |
| `ce_bloc_et_suivants` | ce tour et les suivants **qui portent le même locuteur**. Jamais tous les suivants : ce serait écraser la voix de l'autre, donc détruire la diarisation au lieu de la corriger |
| `tous` | tous les tours de cette voix, **y compris ceux qui précèdent** — sans quoi ce ne serait qu'un « et suivants » déguisé |

**Ce que le geste ne touche pas, et c'est tout l'intérêt** : ni le texte, ni
l'empreinte, ni l'ordre, ni les ancres. Il écrit **une clé** de `provenance`, en
laissant `debut` et `fin` — sans lesquels « écouter à partir de ce passage »
cesserait de fonctionner. Il ne passe donc ni par la réconciliation, ni par la
garde des synthèses figées : **une citation porte un passage, et ce passage ne
bouge pas.** La garde d'**analyse**, elle, s'applique : une transcription en cours
va remplacer tous les éléments de la note.

**Un tour sans voix ne se renomme que seul.** La fusion de deux tours divergents
**retire** la clé : un bloc peut n'avoir aucun locuteur, et ce geste est aussi ce
qui répare ce cas. Mais « tous les blocs sans locuteur » n'est pas un groupe — ils
n'ont rien en commun qu'une **absence**, et les renommer ensemble inventerait une
voix là où l'information manque.

**Au clavier, depuis le mode** : `Ctrl+Maj+L` sur le passage du curseur ouvre un
dialogue — le nom, et la portée. Pas une touche F : celles qui restaient libres
sont prises par le navigateur, et `Ctrl+L` **est** la barre d'adresse. L'envoi
passe par **htmx**, non par `fetch` : le serveur répond en `hx-swap-oob`, que
`fetch` laisserait tomber en silence — l'écran garderait l'ancien nom.

**17 tests**, dont le journal (`PageEdit` de type `locuteur`, avec l'avant, l'après
et le compte), le non-geste qui n'écrit rien, et les quatre refus.

## 2. L'aide rend la table, elle ne la recopie plus

Le § 4.4 le demandait depuis le 23 août : « la modale d'aide la rend **telle
qu'elle est**, jamais une liste recopiée qui divergerait ». Il y avait **trois**
listes — la table `RACCOURCIS`, `liste_raccourcis` dans `front/views.py`, et la
prose du gabarit d'aide.

- les trois lignes dupliquées **sortent** de `views.py` ;
- la prose ne contient plus une seule touche : des `<kbd data-raccourci="…">`
  **vides**, que le JavaScript remplit depuis la table ;
- une section « Le mode édition, au clavier » se remplit depuis la table, **et ne
  paraît que si elle a quelque chose à dire**.

**Les gestes de son n'y figurent que sur une note qui a du son** : promettre `F2`
sur un article web serait promettre un geste qui ne fait rien.

**Deux entrées de la table ne sont pas exécutées par le mode** — `Échap` et `M`,
liées dans la cascade de `keyboard.js`. Elles y figurent quand même, parce que
c'est la table que l'aide rend, et **qu'une aide qui tairait la touche pour sortir
serait pire qu'une aide absente**. Un marqueur `traiteAilleurs` dit au listener de
les laisser passer — sans lui, le double `Échap` du 29 août reviendrait.

**Trois tests** épinglent la non-recopie, dont un qui échoue si une touche du mode
réapparaît en dur dans le gabarit.

**Mesuré au navigateur** : l'aide liste les **12** raccourcis, et les quatre
marqueurs de la prose sont remplis.

## 3. L'accessibilité du mode, mesurée — et ce qui reste à éprouver

La chaîne du § 9, dans l'ordre : entrer → atteindre le champ → naviguer → gestes →
sortir.

| | |
|---|---|
| le bouton du mode | nommé « Éditer le texte », atteignable au clavier, `aria-pressed` **false → true → false** |
| l'entrée, la sortie | **annoncées** — « Mode édition ouvert… », « Mode édition fermé. » |
| le champ, dans l'arbre **de Chromium** | `textbox`, nommé « Texte de la note, modifiable passage par passage », `aria-multiline` |
| « savoir où l'on est sans regarder » (§ 9) | **9 blocs sur 9** portent leur numéro **et** leur locuteur |
| les gestes de son | annoncés : « Lecture. », « Vitesse 1,25 fois. », « Recul de 5 secondes. », « Pause. » |
| erreurs JavaScript | **0** |

→ `benchmarks/edition_par_blocs/banc/mesures24_l_accessibilite_du_mode.py`

**Ce banc n'est pas un lecteur d'écran, et il ne prétend pas l'être.** Il mesure
l'arbre d'accessibilité — ce que Chromium remet aux technologies d'assistance, par
CDP. NVDA, VoiceOver et Orca ont chacun leur façon de restituer un
`contenteditable` multi-blocs et une région live. **Le § 9 dit « à éprouver avec un
vrai lecteur d'écran, jamais en le supposant » : cette exigence reste entière.** Ce
banc réduit ce qu'il reste à éprouver à la main ; il ne le remplace pas.

## 4. Six documents affirmaient le contraire du code

Tous constatés le 23 août, corrigés aujourd'hui — par des **encarts datés**, jamais
en réécrivant les sections.

| Document | Ce qu'il affirmait | Ce qui est vrai |
|---|---|---|
| planche **03** | « la vérification n'est JAMAIS automatique à la production », deux déclencheurs | **trois** déclencheurs : `_ecrire_le_corps_d_un_article` enchaîne la vérification à **toute** écriture de corps, et c'est **facturé** (fan-out des quatre juges locaux) |
| planche **02** | « l'humain coche, opération par opération » | la **nuit applique sans humain**, par le même applieur (`fait_par=None`) |
| **README** des Diagrams | le violet : « rien ne s'applique tout seul » | le violet dit un geste humain, et **ne promet plus** que rien ne s'applique seul |
| **SPEC-synthese**, addendum du 18 août | « la vérification ne se déclenche jamais à la production » | corrigé, avec sa conséquence : le coût d'une nuit inclut cet enchaînement et son juge d'API |
| docstring `verifier_les_citations_task` | « un geste explicite, jamais automatique (Q3) » | trois déclencheurs ; ce qui reste de Q3, c'est que la vérification **complète et rejouée** reste explicite |
| le **prompt** de mise à jour | « un humain les acceptera une par une » | **la nuit n'a pas d'humain** — et c'était ce qui autorisait le modèle à proposer largement, en comptant sur un filtre inexistant |

**Le prompt change, donc les productions futures peuvent changer.** Il dit
maintenant que les opérations « peuvent être appliquées **telles quelles**, sans
relecture humaine ». Le texte est vrai dans les deux cas — jour et nuit — et n'est
volontairement **pas** conditionné à l'appelant : une phrase qui changerait selon
l'heure serait une seconde version du prompt, donc une seconde production à
comparer.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/views_element.py` | l'action `renommer_le_locuteur` et sa portée |
| `hypostasis_extractor/serializers.py` | `RenommageDuLocuteurSerializer` |
| `hypostasis_extractor/tests/test_le_locuteur_d_un_element.py` | **neuf** — 17 tests |
| `front/static/front/js/mode_edition.js` | `Ctrl+Maj+L`, `traiteAilleurs`, le remplissage de l'aide — **?v=17** |
| `front/templates/front/includes/aide_desktop.html` | les `<kbd data-raccourci>` et la section du mode |
| `front/views.py` | `liste_raccourcis` ne double plus la table |
| `front/tests/test_ce_que_dit_l_aide.py` | **+3 tests** sur la non-recopie |
| `front/tasks.py` | la docstring Q3 et le prompt de mise à jour |
| `PLAN/Diagrams/02`, `03`, `README.md` · `PLAN/specs/SPEC-synthese-carnet.md` | encarts datés |
| `benchmarks/edition_par_blocs/banc/mesures24_*.py` | **neuf** — l'arbre d'accessibilité par CDP |

## Ce qui n'est PAS fait

- **La planche 04 « La nuit des wikis »** reste à écrire — elle ne corrige rien,
  elle écrit ce qui manque : **aucune des trois planches ne couvre ce mécanisme**,
  et c'est celui qui applique sans humain.
  → `PLAN/TODO/2026-09-01-la-planche-04-de-la-nuit-des-wikis.md`
- **Le lecteur d'écran réel** (§ 9) : l'arbre est mesuré, le rendu ne l'est pas.
- **`lecteur_audio.js` garde ses touches en dur** (flèches, Début, Fin du rail) :
  c'est le dernier listener que la table ne gouverne pas.

---

## Comment tester (à la main) / Manual test

### Test 1 — corriger qui parle
1. Ouvrir `/lire/4/` (neuf tours, deux locuteurs), cliquer **« Éditer le texte »**.
2. Placer le curseur dans un tour mal attribué, faire **`Ctrl+Maj+L`**.
3. Taper un nom, choisir **« ce passage seulement »**, valider. **Attendu** : le
   nom change **dans la gouttière de ce tour**, les autres ne bougent pas, et le
   mode reste ouvert.
4. Recommencer avec **« tous les passages de cette voix »**. **Attendu** : tous les
   tours de cette voix changent, y compris **avant** celui du curseur.

### Test 2 — l'aide dit la vérité
1. Appuyer sur **`?`**. **Attendu** : une section « Le mode édition, au clavier »
   liste les raccourcis — dont `F2`, `F4`, `F7`…, mais **seulement sur une note qui
   a du son**.
2. Ouvrir l'aide depuis un article web. **Attendu** : les touches de son ont
   disparu de la liste.

### Tests automatiques
```bash
docker exec -w /app hypostasia_web python manage.py test \
  hypostasis_extractor.tests.test_le_locuteur_d_un_element \
  front.tests.test_ce_que_dit_l_aide front.tests.test_mode_edition --noinput
```

Et la non-régression du chantier, qui porte désormais le locuteur :
```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_mode_edition front.tests.test_ce_que_dit_l_aide \
  front.tests.test_phases front.tests.test_lecture_elements \
  front.tests.test_boutons_elements front.tests.test_rendu_elements \
  front.tests.test_barre_du_lecteur_audio front.tests.test_lecteur_audio \
  front.tests.test_gouttiere_audio front.tests.test_aucun_geste_orphelin \
  hypostasis_extractor.tests.test_corriger_en_lot \
  hypostasis_extractor.tests.test_le_lot_et_les_ancrages \
  hypostasis_extractor.tests.test_le_locuteur_d_un_element \
  hypostasis_extractor.tests.test_le_rendu_d_un_seul_bloc \
  hypostasis_extractor.tests.test_views_element --noinput
```
→ **788 tests, OK en 526 s** (mesuré le 1er septembre 2026 ; 768 la veille au soir).

Et les 102 tests de la nuit et de la vérification, que le prompt corrigé touche :
```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_la_passe_de_nuit_des_wikis \
  front.tests.test_le_recapitulatif_du_matin core.tests.test_verification --noinput
```
→ **102 tests, OK en 99 s.**
