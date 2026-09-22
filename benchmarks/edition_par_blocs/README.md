# Le banc de l'édition par blocs — l'option C, le champ unique

**23, 26 et 28 août 2026.** Ce banc a servi à **trancher une voie technique**, pas
à mesurer une performance. Ce qu'on en garde est
`CHANGELOG/2026-08-23-le-champ-unique-tranche-l-edition-par-blocs.md`.

> **Le prototype lui-même s'ouvre au navigateur** :
> `front/static/front/maquettes/prototype-champ-unique/`. Ce dossier-ci ne porte
> que les **bancs** et les **chiffres**.

## Ce qu'il a établi, en une ligne chacun

- le champ tient à 210 blocs / 58 770 caractères : montage ~50 ms, **6 ms par frappe** ;
- le diff par `identifiant_stable` est exact : **0 identifiant perdu, 0 dupliqué**, et les 191 blocs jamais touchés reviennent **à l'octet près** ;
- **`contenteditable="plaintext-only"` n'empêche pas la fusion multi-blocs** (210 → 205) ;
- **une garde par `keydown` ne suffit pas** : `Ctrl+A` puis une frappe réduit la note à **un seul bloc** ; la même garde sur `beforeinput` tient ;
- **`getTargetRanges()` rend une liste VIDE sous `plaintext-only`** — une garde qui s'y fie seule y est aveugle ;
- **`insertCompositionText` n'est pas annulable** : une composition IME multi-blocs détruit 5 blocs que rien n'arrête ;
- la réconciliation ne détache **que** les portions qui enjambent le point d'édition (22/22), **aucune** des 37 autres — et c'est **identique pour les trois voies**.

**Les trois mesures qui conditionnaient la décision, faites les 26 août 2026 :**

- **le DOM réel** : la garde injectée dans la vraie page (189 blocs, 189 boutons d'action) tient les trois gestes ; lire `.corps.textContent` rend **0 bloc exact sur 189**, lire l'élément interne **189 sur 189** ; et sur la page 19, **202 sur 210 bouclent — les 8 échecs sont exactement les 8 `table`** ;
- **Firefox 146 et WebKit 26** : la promesse fondatrice tient sur les trois moteurs, et la garde aussi (**210 blocs et 210 gouttières intacts**, contre 206/209 sans elle). Le piège de `getTargetRanges()` vide est **propre à Chromium** ; sur WebKit le repère de gouttière entre dans la sélection étendue au clavier (défaut de **copie**) ;
- **la composition IME** : **210 → 205 sans parade, 210 → 210 avec**. La parade normalise la sélection dès `compositionstart`.

## Comment le rejouer

Playwright vit **dans le conteneur** `hypostasia_web`, et **les trois moteurs y
tournent** depuis le 26 août 2026 : Chromium 145, Firefox 146, WebKit 26.

> Les binaires étaient déjà téléchargés ; seules les **dépendances système**
> manquaient. Le message d'erreur ne le disait pas, ce qui a fait croire trois jours
> durant qu'ils étaient ininstallables. Le remède :
> ```bash
> docker exec -u root hypostasia_web apt-get update -qq
> docker exec -u root hypostasia_web python -m playwright install-deps firefox webkit
> ```
> Et **`HOME=/app`** dans ce conteneur : le cache est `/app/.cache/ms-playwright/`,
> pas `/home/hypostasia/`.

```bash
# 1. Le prototype et le banc, dans le conteneur.
docker cp front/static/front/maquettes/prototype-champ-unique hypostasia_web:/tmp/proto
docker cp benchmarks/edition_par_blocs/banc/. hypostasia_web:/tmp/proto/
docker exec -d -w /tmp/proto hypostasia_web python -m http.server 8899 --bind 127.0.0.1

# 2. Les bancs. Chacun écrit son JSON dans /tmp/proto/.
docker exec -w /tmp/proto hypostasia_web python mesures.py      # les 6 mesures d'origine
docker exec -w /tmp/proto hypostasia_web python mesures6.py     # les trous de la garde keydown
docker exec -w /tmp/proto hypostasia_web python mesures8.py     # le collage sous beforeinput
docker exec -w /tmp/proto hypostasia_web python mesures9.py     # getTargetRanges vide

# 3. Récupérer les résultats.
docker cp hypostasia_web:/tmp/proto/resultats-volet9.json benchmarks/edition_par_blocs/resultats/
```

`mesures.py` accepte les numéros de mesure en argument (`python mesures.py 1 2`).

**Les volets 10 à 15** (le vrai DOM, les trois moteurs, l'IME, l'annulation, les
labels qui ne bouclent pas) se lancent directement :
`python /tmp/mesures11_trois_moteurs.py`, etc. **Deux d'entre eux ont un
préalable** : `mesures10_le_vrai_dom.py` exige `/tmp/textes-attendus.json` **et une
connexion réussie** (il s'arrête sans cookie de session — un premier passage avait
mesuré la page en anonyme sans le dire) ; `mesures15_quels_blocs_ne_bouclent_pas.py`
exige `/tmp/textes-19.json` et `/tmp/labels-19.json`. Les deux requêtes qui les
produisent sont en commentaire d'en-tête de chaque banc, et elles sont en **lecture
seule**.

### Les mesures qui exigent la VRAIE base

Trois d'entre elles ne se rejouent pas sur les données synthétiques :

```bash
# Extraire les blocs réels (LECTURE SEULE, écrit /tmp/donnees-reelles.json)
docker cp banc/extraire_les_donnees_reelles.py hypostasia_web:/tmp/
docker exec hypostasia_web python manage.py shell -c "exec(open('/tmp/extraire.py').read())"

# La mesure des ancres — en transaction ANNULÉE, aucune écriture conservée
docker cp banc/mesure_des_ancres.py hypostasia_web:/tmp/
docker exec hypostasia_web python manage.py shell -c "exec(open('/tmp/mesure_des_ancres.py').read())"
docker cp banc/temoin_ancres.py hypostasia_web:/tmp/     # le témoin : texte identique
docker cp banc/ancres_detail.py hypostasia_web:/tmp/     # quelles portions se détachent

# Le diff par identifiant_stable, sur le POST des vingt gestes
python3 banc/diff.py resultats/resultats-2.json
```

> ⚠️ `diff.py` a besoin des champs `post` et `initiaux` de `resultats-2.json`, et
> **ils ont été retirés du dépôt** : ils portaient les 58 770 caractères d'un
> article qui appartient à un tiers. Rejouer `mesures.py 2` sur les données réelles
> les reproduit.

## Les données livrées sont SYNTHÉTIQUES

`fabriquer_des_donnees_synthetiques.py` rend un jeu de **même forme** que le corpus
réel — 210 blocs, `{text: 116, section_header: 43, list_item: 41, table: 8,
caption: 2}`, les 8 tableaux à saut de ligne, 12 tours et 5 locuteurs — avec du
texte fabriqué, à **−3,2 %** du volume réel. Graine fixe : le jeu est reproductible.

```bash
python3 banc/fabriquer_des_donnees_synthetiques.py \
  > ../../front/static/front/maquettes/prototype-champ-unique/donnees.json
```

## Les quatre pièges de méthode, payés dans cette journée

1. **Un `ClipboardEvent` ou un `DragEvent` construits en JavaScript ne déclenchent
   AUCUNE action par défaut.** Le premier banc « mesurait » un collage sans garde
   qui ne collait rien. Il faut le vrai presse-papier
   (`context.grant_permissions(["clipboard-read", "clipboard-write"])` +
   `navigator.clipboard.write` + un vrai `Ctrl+V`) et la vraie souris.
2. **Compter les blocs ne suffit pas.** Sur l'`Entrée` sans garde, leur nombre ne
   bouge pas : c'est le `<p>` *dans* le bloc qui se scinde, et les deux moitiés
   portent **le même identifiant**.
3. **N'éprouver que les touches auxquelles on a pensé donne une garde qui ne protège
   que celles-là.** Le geste le plus courant d'un correcteur — taper sur une
   sélection — n'était pas dans les vingt premiers gestes, et il détruisait cinq
   blocs.
4. **Un instrument qui se vérifie lui-même ne prouve rien.** L'attribution par geste
   et le POST venaient du même sérialiseur ; un collage tombé dans le mauvais bloc
   n'a déclenché aucune alarme.

**Trois relectures adverses** ont produit ces quatre lignes. C'est la méthode à
reconduire, pas le code à reprendre.
