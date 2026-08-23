# La fusion de deux tours garde le mauvais locuteur

**Défaut de production constaté le 23 août 2026, en relecture adverse. Rien n'est corrigé.**
**Il ne dépend d'aucun chantier en cours : il se corrige seul, et il devrait l'être en premier.**

## Le défaut

`_fusionner_les_provenances` (`hypostasis_extractor/services/moteur_structure.py:475-488`)
lit **trois clés que rien n'écrit** :

```python
debut_du_premier = provenance_du_premier.get("start_time")   # toujours None
fin_du_second    = provenance_du_second.get("end_time")      # toujours None
...
locuteur_du_premier = provenance_du_premier.get("voice")     # toujours None
locuteur_du_second  = provenance_du_second.get("voice")      # toujours None
if locuteur_du_premier != locuteur_du_second:                # None != None -> FAUX
    provenance_fusionnee.pop("voice", None)                  # jamais exécuté
```

**Les clés réellement écrites sont `locuteur`, `debut`, `fin`** — par
`ingestion_audio.py:144-146` et `:172-174`, seul chemin d'ingestion audio vivant
(appelé par `tasks_element.py:741`). C'est aussi ce que le rendu lit
(`front/services/rendu_elements.py`).

`moteur_structure.py:475-488` est **le seul endroit du code de production** à employer
`start_time` / `end_time` / `voice`. Vérifié par recensement le 23 août.

## Ce que ça produit

`provenance_fusionnee` part de `dict(provenance_du_premier)` : elle contient donc déjà
le `locuteur`, le `debut` et la `fin` du **premier** tour. Comme aucune des quatre
lectures ci-dessus ne rend quoi que ce soit :

- **le locuteur du premier est conservé, quel que soit celui du second.** Recoller le
  tour de Paul dans celui d'Ian produit **un tour attribué à Ian contenant les mots de
  Paul** ;
- **la `fin` reste celle du premier tour** : l'intervalle du tour fusionné est trop
  court. Le lecteur audio désynchronise son surlignage, et un « écouter depuis ici »
  s'arrête avant la fin du texte affiché.

Et c'est **silencieux** — c'est exactement ce que le commentaire d'à côté prétend
empêcher :

> Le locuteur n'est conservé que si c'est le même des deux côtés.
> Recoller deux locuteurs différents effacerait qui a dit quoi.

L'intention est bonne ; le code ne l'exécute pas.

## Pourquoi les tests ne l'ont pas vu

`hypostasis_extractor/tests/test_moteur_structure.py:784-811` **fabrique lui-même**
une provenance `{"start_time", "end_time", "voice"}` — un dictionnaire que la
production ne produit jamais. Le test est **vert sur un contrat mort**.

C'est, avec la fonction testée, le seul endroit du dépôt où ce vocabulaire existe —
plus le `help_text` du modèle (`core/models.py:2413`), qui annonce
`audio -> {start_time, end_time, voice}` et **désigne le mauvais contrat**. C'est de
là que l'erreur se propage : une session qui lit le modèle croit ces clés vraies.

## Ce qu'il faut faire

1. **`moteur_structure.py:475-488`** : lire `locuteur`, `debut`, `fin`.
2. **`core/models.py:2413`** : corriger le `help_text` — il est la source de la
   confusion, pas sa victime.
3. **`test_moteur_structure.py:784-811`** : le test doit partir d'une provenance
   **produite par `ingestion_audio`**, jamais d'un littéral écrit à la main. Un test
   qui fabrique son propre contrat ne teste rien.
4. **Un test de non-régression** : fusionner deux tours de locuteurs **différents**
   doit retirer le locuteur ; fusionner deux tours du **même** doit le garder, et
   l'intervalle doit couvrir les deux.

## Ce qui n'est PAS le problème

**Le renommage de locuteur existe déjà, et il est complet.**
`PageViewSet.renommer_locuteur` (`front/views.py:3263`, plus son formulaire l. 3241)
renomme dans `transcription_raw`, reconstruit le HTML et le texte, met à jour
`provenance["locuteur"]` sur les éléments par `bulk_update`, et écrit un `PageEdit` de
type `locuteur` (`TypeEdit.LOCUTEUR` existe depuis PHASE-27a). Il a **trois portées** :
`tous`, `ce_bloc_seul`, `ce_bloc_et_suivants`.

> **Correction à deux documents de cette série.**
> `2026-08-23-les-deux-gestes-manquants-de-l-edition-par-blocs.md` et
> `SPEC-edition-par-blocs-et-stenotypie.md` § 6.2 affirment qu'« aucun geste ne corrige
> le locuteur ». **C'est faux** : `ce_bloc_seul` fait exactement la réattribution d'un
> tour. Ce qui manque n'est pas le geste — c'est **son accès au clavier depuis le mode
> édition**, et le fait qu'il passe par une modale plutôt que par une frappe.

## Ce qui casse si on ne fait rien

Rien ne se met à casser : c'est **déjà** cassé, et ça ne se voit pas. Toute fusion de
deux tours de parole depuis la mise en service du moteur ELEMENT a produit une
attribution potentiellement fausse — et une transcription dont les tours sont attribués
à la mauvaise personne alimente des extractions qui citent quelqu'un qui n'a rien dit.
Dans un outil de délibération sourcée, c'est le défaut le plus coûteux de la série.

**Aucune fusion de tour n'a pu être constatée en base** : `provenance__has_key='voice'`
et `provenance__has_key='locuteur'` rendent **0 élément** sur la base de dev — aucune
transcription n'y est ingérée. Le défaut est donc établi **par lecture du code**, et sa
portée réelle reste à mesurer sur une vraie transcription.

## Coût de mise en œuvre

Six lignes de code, un `help_text`, deux tests. Une heure.
