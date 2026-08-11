# Déduplication à l'import de fichier, par empreinte du fichier source

> Spécification, 11 août 2026.
> Chantier voisin de `2026-08-11-fixtures-sample-design.md`, indépendant
> de lui : ni l'un ni l'autre n'attend l'autre pour être écrit.

---

## 1. Le problème

L'application a deux portes d'entrée, et une seule sait reconnaître un
document qu'elle a déjà.

**L'extension navigateur dédoublonne.** `PageViewSet.create`
(`core/views.py:130`) vérifie d'abord l'URL normalisée, puis le
`content_hash`, dans le périmètre « carnets de l'utilisateur + carnets
partagés avec lui ». Un doublon reçoit un **409** avec
`existing_page_id`.

**L'import de fichier ne dédoublonne pas.** `ImportViewSet.fichier`
(`front/views.py:5225`) calcule pourtant `hashlib.sha256(text_readability)`
à la ligne 5576 — et ne le consulte jamais. Réimporter deux fois le même
PDF crée deux notes, et fait payer deux fois la conversion Docling.

Le second point est celui qui coûte. Un `content_hash` n'est connu
qu'**après** conversion : même utilisé, il n'éviterait que la note en
double, pas le travail.

---

## 2. La décision

Un nouveau champ **`Page.empreinte_source`** : le SHA256 du **fichier
binaire**, calculé **avant** toute conversion.

C'est ce que `content_hash` ne peut pas être. `content_hash` est le
SHA256 de `text_readability`, donc du résultat ; `empreinte_source` est
celui de l'entrée. Les deux cohabitent sans se remplacer : le premier
reconnaît deux textes identiques venus de sources différentes, le second
reconnaît le même fichier avant de le lire.

### Le point d'insertion est unique

`ImportViewSet.fichier` aiguille vers trois pipelines — JSON, audio,
document (`front/views.py:5250`) — et cet aiguillage vient **après** la
validation du sérialiseur. La vérification se pose là, avant les trois
branches : une seule insertion couvre les trois formats, y compris le
mp3 et la transcription JSON.

```python
fichier_uploade = serializer.validated_data["fichier"]
nom_fichier = fichier_uploade.name

# ── ici : empreinte + recherche du doublon ──

if est_fichier_json(nom_fichier):
    ...
```

### Le calcul se fait par morceaux

Django sert les gros fichiers en morceaux ; lire un PDF de 100 Mio d'un
bloc pour le hacher chargerait 100 Mio en mémoire pour rien.

```python
empreinte = hashlib.sha256()
for morceau in fichier_uploade.chunks():
    empreinte.update(morceau)
empreinte_du_fichier = empreinte.hexdigest()
fichier_uploade.seek(0)
```

Le `seek(0)` n'est pas facultatif : sans lui, le pipeline en aval lit un
fichier déjà consommé et produit une note vide.

### Le périmètre est celui de l'utilisateur

Le même que pour l'extension : carnets possédés + carnets partagés. On
ne dit jamais à quelqu'un qu'un document existe déjà s'il n'y a pas
accès — ce serait une fuite d'information sur le corpus d'autrui.

`_ids_dossiers_accessibles` vit aujourd'hui dans `core/views.py:77`.
L'importer depuis `front/views.py` violerait la séparation posée par les
guidelines (« les deux apps partagent les modèles de `core`, jamais les
vues »). Il **descend donc dans `core/services/corpus.py`**, qui porte
déjà `ranger_une_note_dans_un_carnet`, et les deux vues l'importent de
là. On ne le duplique pas : c'est une règle de périmètre d'accès, et
deux copies finiraient par diverger.

### Le doublon ouvre la note existante

L'extension parle à un programme : un 409 lui suffit. L'import parle à
un humain, qui vient de choisir un fichier et attend de voir quelque
chose.

La réponse rend donc la **lecture de la note déjà présente** — même
partial `lecture_principale.html` et mêmes OOB (arbre, panneau) qu'un
import réussi — accompagnée d'un toast, sur le patron `HX-Trigger` déjà
en place (`front/views.py:126`) :

```python
reponse["HX-Trigger"] = json.dumps({
    "toast": {"items": [{
        "level_tag": "info",
        "text": "Cette note existe déjà : la voici.",
    }]},
})
```

Statut **200**, pas 409 : de son point de vue, l'utilisateur obtient
exactement ce qu'il demandait — sa note à l'écran.

---

## 3. Ce qui ne change pas

- **L'extension garde son 409.** Son appelant est un programme qui sait
  lire `existing_page_id` ; changer ce contrat casserait l'extension pour
  rien.
- **`content_hash` reste ce qu'il est**, calculé et écrit comme avant.
- **Les pages antérieures ont une `empreinte_source` vide**, et une
  empreinte vide n'est jamais un doublon — sans quoi tous les anciens
  documents se reconnaîtraient entre eux. Le rétro-remplissage depuis
  `Page.source_file` est possible, mais hors de ce périmètre : il
  demande de relire chaque fichier sur disque, et la question de ce
  qu'on fait des doublons ainsi révélés est une question produit, pas
  technique.
- **Un fichier modifié n'est pas un doublon.** Même nom, contenu
  différent → empreinte différente → import normal. C'est le
  comportement voulu.

---

## 4. Tests (TDD)

Dans `front/tests/test_dedup_import.py` :

1. Importer deux fois le même fichier → une seule `Page`, la seconde
   réponse rend la première note.
2. La seconde réponse porte le `HX-Trigger` de toast et un statut 200.
3. La seconde réponse ne lance **aucune** conversion (assertion sur le
   mock de `ingerer_un_fichier_avec_docling`) — c'est le gain réel.
4. Deux fichiers de contenus différents mais de même nom → deux pages.
5. Le même fichier importé par un **autre** utilisateur sans accès
   partagé → une seconde page est bien créée, et la réponse ne révèle
   rien de la première.
6. Le même fichier importé par un utilisateur qui a le carnet **en
   partage** → doublon détecté, note existante rendue.
7. Une page à `empreinte_source` vide n'est jamais reconnue comme
   doublon, même si le fichier importé hache en `""`… ce qui n'arrive
   pas : un SHA256 fait toujours 64 caractères. Le test verrouille la
   garde explicite `if empreinte_du_fichier and ...`.
8. Les trois branches sont couvertes : un `.md`, un `.json` de
   transcription et un `.mp3` réimportés sont tous trois reconnus.
9. Après import, `empreinte_source` est bien peuplée sur la page créée,
   et le fichier reste lisible en aval (garde du `seek(0)` : la note
   n'est pas vide).

---

## 5. Migration

Une seule, additive :

```python
empreinte_source = models.CharField(
    max_length=64, blank=True, db_index=True,
    help_text="SHA256 hex du FICHIER source, calculé avant conversion",
)
```

`db_index=True` parce que chaque import fait une recherche dessus.
Champ nullable-vide, aucune donnée existante à réécrire, aucun risque
de rejeu.

---

## 6. Hors périmètre

- **Le cache de conversion partagé entre utilisateurs** — une table
  `(empreinte_source, version_docling) → éléments`, qui éviterait de
  reconvertir un document déjà converti par quelqu'un d'autre. C'est le
  gain le plus gros, et le plus lourd : invalidation à chaque montée de
  version de Docling, et une vraie question de cloisonnement entre
  périmètres. **À reprendre quand la mesure Docling aura dit ce que
  coûte réellement une conversion** — décider avant serait décider sans
  savoir.
- Le rétro-remplissage des pages existantes (§ 3).
- La dédup de l'extension, inchangée.
