# Revue finale de `charger_fixtures_sample` — correction des six défauts

> 11 août 2026. Une passe, méthode TDD : chaque défaut a d'abord eu son
> test, vu échouer, avant sa correction.
>
> Fichiers touchés : `front/management/commands/charger_fixtures_sample.py`
> et `front/tests/test_charger_fixtures_sample.py`. Aucune opération git.

**État final : 37 tests, tous verts** (26 existants + 11 ajoutés),
`manage.py check` sans issue. Les tests taggés `docling` n'ont pas été
relancés — ils sont lourds et rien de ce qui suit ne touche à la
conversion elle-même.

---

## Défaut 1 — la config de transcription était choisie au hasard (CRITIQUE)

`_charger_le_mp3` faisait `TranscriptionConfig.objects.filter(is_active=True).first()`.
Ce `.first()` prend n'importe quelle config active : `TranscriptionConfig`
n'a aucun `Meta.ordering`, l'ordre est arbitraire côté SGBD, et son
`provider` vaut `MOCK` par défaut (`core/models.py:993`) — toute config
créée depuis l'admin sans choisir de modèle est une config mock. Qu'une
seule traîne en base et `front/tasks.py:634` retombe sur
`transcrire_audio_mock`, pendant que le bilan annonce quand même
« Audio mp3 (Voxtral) : N tour(s) de parole ». C'est exactement le faux
verbatim que le § 3.2 de la spec existe pour interdire.

**Correction.** La valeur de retour de `_creer_la_config_de_transcription()`
n'est plus jetée : `handle()` la garde dans `self.config_de_transcription`.
Une nouvelle méthode `_config_voxtral_utilisable()` la rend si son
`provider` est bien `voxtral` ; sinon elle se rabat sur
`filter(is_active=True, provider=VOXTRAL).order_by("pk").first()` — jamais
sur autre chose. Si rien n'est utilisable, le mp3 est sauté avec un
message qui dit pourquoi, plutôt que d'être mocké en silence.

**Tests.** `ConfigDeTranscriptionDuMp3Test.test_le_mp3_recoit_la_config_voxtral_pas_une_config_mock_active`
(une config mock active créée d'abord ne doit pas être choisie) et
`…test_sans_config_voxtral_le_mp3_est_saute_plutot_que_mocke` (une config
mock *nommée* « Voxtral Mini » — cas réel, car `get_or_create` ne porte
que sur `name` et la rend telle quelle — fait sauter le mp3, sans appel).

---

## Défaut 2 — la commande détruisait le média de sa propre note (IMPORTANT)

Elle passait `page_du_mp3.source_file.path` à `transcrire_audio_task`. Or
cette tâche fait `os.unlink(chemin_fichier_audio)` dans un `finally`
(`front/tasks.py:742-747`), succès ou échec. Son contrat est de recevoir
un fichier **temporaire** : la vue d'import lui passe une copie dans
`AUDIO_TEMP_DIR` (`front/views.py:5422-5428`). Après la commande, la
`Page` référençait donc un `source_file` disparu du disque.

**Correction.** Nouvelle méthode `_copier_l_audio_en_temporaire()` : elle
écrit les octets du mp3 sous un nom UUID dans `settings.AUDIO_TEMP_DIR`
— même réglage et même usage que la vue d'import — et c'est **ce**
chemin qui part à la tâche. Le `source_file` de la page n'est plus jamais
exposé à l'`unlink`.

**Test.** `ConfigDeTranscriptionDuMp3Test.test_le_media_de_la_note_audio_survit_a_la_tache` :
le mock de la tâche fait réellement l'`unlink` du chemin reçu, comme la
vraie ; le test vérifie ensuite que ce chemin **diffère** de
`page.source_file.path` et que ce dernier **existe toujours**.

---

## Défaut 3 — une ingestion ratée était définitive (IMPORTANT)

`_note_deja_presente` ne testait que l'existence de la `Page`, jamais
celle de ses éléments. Une ingestion en échec laissait une coquille — ni
gouttière, ni ancrage possible — que toutes les relances sautaient :
sans `--reset`, l'état à moitié ingéré ne se réparait jamais. C'était la
vraie divergence entre les quatre chargeurs, le mp3 ayant seul un
rattrapage en fin de méthode.

**Correction.** Une note sans élément ne compte plus comme présente :
elle est **supprimée puis rechargée**. La suppression est obligatoire —
sinon la contrainte globale `unique_url_si_presente` refuse la capture
web, et les trois autres notes se dédoublent. Trois garde-fous encadrent
la suppression :

1. en `--a-blanc`, on constate sans supprimer (la note est rechargeable,
   c'est ce que le bilan doit annoncer) ;
2. si la note porte des ancres — censé impossible sans élément, mais
   **vérifié plutôt que supposé** — on n'y touche pas et on le dit ;
3. si elle est rangée **aussi** dans un autre carnet, elle appartient à
   quelqu'un d'autre : on ne l'emporte pas, même règle que `--reset`.

Le point 3 n'était pas demandé explicitement, mais sans lui la correction
supprimait la note d'un autre carnet — la même fuite de périmètre que
`_reinitialiser` prend déjà soin d'éviter.

**Tests.** `RattrapageDesNotesSansElementTest` :
`test_une_note_sans_element_est_rechargee`,
`test_une_note_avec_ses_elements_est_bien_sautee` (le cas nominal ne doit
pas régresser),
`test_une_note_sans_element_rangee_ailleurs_n_est_pas_supprimee`.

---

## Défaut 4 — `--a-blanc` mentait sur une base déjà chargée (IMPORTANT)

`_creer_le_carnet` rendait `None` en mode à blanc sans chercher le carnet
existant. `_note_deja_presente` n'avait donc aucun carnet où regarder et
rendait toujours `False` : le mode à blanc annonçait « serait chargée »
pour les quatre notes alors qu'une vraie exécution les sautait toutes.

**Correction.** En mode à blanc, le carnet est **cherché** (`filter(...).first()`,
scopé sur le propriétaire, et seulement s'il y en a un) mais **jamais
créé**. S'il existe, la ligne dit `pk=<N> (réutilisé)`.

Vérification sur la base de développement, où les quatre notes sont déjà
chargées :

```
Carnet              : Documents étalons — pk=1 (réutilisé)
Capture web         : déjà présente — sautée
Markdown            : déjà présent — sauté
Transcription JSON  : déjà présente — sautée
Audio mp3           : déjà présent — sauté
Notes sautées       : 4 (déjà présentes)
```

**Tests.** `ModeABlancTest.test_a_blanc_dit_vrai_sur_une_base_deja_chargee`
et `…test_a_blanc_ne_cree_toujours_aucun_carnet` (chercher ne doit pas
devenir créer).

---

## Défaut 5 — le bilan n'était pas conforme au § 4 de la spec (IMPORTANT)

Il manquait le détail par label de la capture web et la ligne finale des
notes sautées.

**Correction.** Nouvelle méthode `_detail_par_label(page)` : elle compte
les éléments par label dans l'ordre du document et rend
` — section_header 4 · list_item 5 · text 19`. Elle n'est appelée que
pour la capture web, comme la spec le précise — c'est elle qui porte le
contrôle de non-régression du § 5, qu'un simple total masquerait (54
éléments dont un `picture`, ou une cinquantaine de blocs tous en `text`,
passeraient inaperçus). Un compteur `self.nombre_de_notes_sautees`,
incrémenté aux quatre points de saut « déjà présente », donne la ligne
finale `Notes sautées       : <N> (déjà présentes)`. Il ne compte que les
notes déjà là — pas celles que `--sans-mp3` ou `--fichier` ont exclues,
qui n'ont jamais été candidates.

**Tests.** `BilanDeSortieTest.test_le_bilan_detaille_les_labels_de_la_capture_web`
(vérifie aussi que le markdown, lui, n'a **pas** de détail) et
`…test_le_bilan_compte_les_notes_sautees` (0 au premier chargement, 3 au
second).

---

## Défaut 6 — test manquant sur `--a-blanc` + `MISTRAL_API_KEY` (MINEUR)

Le mp3 est le seul chemin où une garde mal placée coûterait un appel
réseau payant, et aucun test ne couvrait la combinaison.

**Correction.** Test ajouté ;
`ModeABlancTest.test_a_blanc_n_appelle_pas_voxtral_meme_avec_la_cle`
vérifie qu'avec la clé présente, `--a-blanc` n'appelle ni
`transcrire_audio_task.apply` ni `transcrire_audio_via_voxtral`, ne crée
ni `Page`, ni `TranscriptionJob`, ni `TranscriptionConfig`, et écrit bien
« serait transcrit ». Ce test passait déjà à l'écriture : la garde était
au bon endroit. C'est donc un verrou de non-régression, pas la
révélation d'un bug — d'autant plus utile que la correction du défaut 1
a inséré une résolution de configuration juste après cette garde. Le
commentaire du code marque désormais explicitement que la garde à blanc
doit rester en premier.

---

## Test existant modifié — un seul

`DocumentsEcritsTest.test_relancer_ne_double_rien_et_ne_reconvertit_pas`.

Il mockait les deux tâches Docling par un `patch()` nu, qui ne crée
**aucun** élément. Ses pages restaient donc à moitié ingérées, et la
correction du défaut 3 les rechargeait — à juste titre : c'est
précisément ce qu'on lui demande désormais. `call_count` passait de 1 à 2.

Le mock était la fiction, pas l'assertion : une vraie ingestion produit
des éléments. Les deux `patch()` reçoivent maintenant le `side_effect`
`ingestion_simulee("text")`, un helper ajouté en tête du fichier de
tests, qui crée un `ElementDocument` sur la page ingérée et rend un
résultat `{"elements": N}`. L'intention du test — « une note bel et bien
ingérée ne se reconvertit pas » — est intacte, et ses deux assertions
sont inchangées. Aucun autre test existant n'a été touché.

---

## Réserves

- **Le mp3 réel n'a pas été transcrit.** Toutes les corrections sont
  éprouvées avec Voxtral mocké : aucun appel réseau payant n'a été
  déclenché. Le défaut 2 est vérifié par un mock qui reproduit fidèlement
  l'`unlink` de la vraie tâche, mais un chargement réel reste à faire
  avec une `MISTRAL_API_KEY` valide.
- **La ligne « Transcription » du bilan garde le même travers que le
  défaut 4**, à plus petite échelle : en `--a-blanc`, elle affiche
  « Voxtral Mini (serait créée) » sans chercher si la config existe déjà
  — sur la base de développement, elle existe. Ce n'est pas dans les six
  défauts listés et je ne l'ai pas corrigé de mon propre chef ; la
  correction serait le décalque de celle du carnet, six lignes.
- **Litière de test.** Les deux tests qui mockent `transcrire_audio_task`
  laissent la copie temporaire du mp3 dans `tmp/audio/` : le mock
  n'appelle pas le `finally` qui la supprimerait. Fichier de 14 s, sans
  conséquence, mais c'est une différence avec l'exécution réelle.
- **Tests `docling` non relancés**, conformément à la consigne. Le
  contrôle des 28 éléments porte sur la conversion, à laquelle rien de
  ceci ne touche ; seul son *affichage* a changé (ajout du détail par
  label), ce que couvre `test_le_bilan_detaille_les_labels_de_la_capture_web`.
