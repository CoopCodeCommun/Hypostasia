# R1 — La reconversion : l'ancien moteur n'affiche plus rien

> Livré le 10 août 2026 (session Opus). Applique à la BASE la décision de
> gouvernance du même jour : le moteur ELEMENT devient le seul moteur.

## Ce qui a été livré

Deux commandes `manage.py`, aucune migration.

1. **`basculer_vers_le_moteur_element`** — existait déjà, mais ne voyait
   que les pages sans éléments et ne posait jamais `Page.moteur`. Elle
   reconvertit désormais toute page ANCIEN, vérifie les ancres qu'elle
   crée *et* celles qu'elle rend officielles, et nomme ce qu'elle détache.
2. **`purger_les_notes_inutiles`** — nouvelle : retire les pages en
   double d'essai, sous trois gardes, en **itérant jusqu'au point fixe**
   (un protecteur peut lui-même partir dans le passage).

Plus deux correctifs d'affichage exposés par la bascule : l'avis « trop
d'idées pour les surligner » et l'étiquette « ancre détachée ».

## Résultat sur la base de dev

| | Avant | Après |
|---|---|---|
| Pages | 546 (542 ancien / 4 element) | 213 (2 ancien / 211 element) |
| **Commentaires humains** | **983** | **983** |
| Pages commentées | 37 | 37 |
| Extractions | 30 325 | 24 253 |
| Ancrages | 28 617, toutes `ancree` | 22 148 `ancree` / 1 311 `detachee` |
| Types de note | — | 204 notes / 7 synthèses / 2 wikis |

Les **2 pages restées ANCIEN** le sont à dessein : elles n'ont ni élément
ni texte exploitable, les basculer les afficherait vides. Ce sont les
pages **97** (« présentation des open badges ») et **680** (« Ostrom —
gouverner les communs »). Elles réapparaîtront à chaque `--a-blanc` :
c'est honnête, elles restent à traiter.

## Comment tester

### La reconversion (rejouable sans risque)

```bash
# Elle est idempotente : ce lancement ne doit annoncer que les 2 pages
# sans bloc à lire, et ne rien écrire.
docker exec hypostasia_dev_web python manage.py \
    basculer_vers_le_moteur_element --a-blanc
```

Le bilan à blanc annonce **exactement** ce que le run réel ferait — c'est
un invariant : le mode à blanc calcule les mêmes portions, sur des
éléments de travail non sauvegardés. Si les deux divergent, c'est un
défaut.

### La purge

```bash
docker exec hypostasia_dev_web python manage.py \
    purger_les_notes_inutiles --a-blanc
```

Doit annoncer « **0** page à supprimer » — la purge a convergé. Si elle
en propose, c'est que de nouvelles pages ont été créées depuis.

Elle annonce toujours « commentaires emportés : 0 (aucun) » : la commande
**refuse de s'exécuter** si ce nombre n'est pas nul, et le recompte une
seconde fois *dans* la transaction (l'application tourne pendant).

### Les tests

```bash
docker exec hypostasia_dev_web python manage.py test \
    core.tests.test_reconversion_moteur core.tests.test_purge_notes \
    front.tests.test_ancres_detachees_drawer front.tests.test_rendu_elements \
    --noinput --settings=hypostasia.settings_test_opus
```

### À l'écran

⚠️ Les comptes ci-dessous ont été relevés AVANT le second passage de
purge ; les pages 419 et 235 sont conservées (commentées) mais leurs
voisines ont bougé. L'invariant à vérifier est la cohérence
carte-étiquetée ⇔ extraction sans ancre vivante, pas le nombre exact.

- `/lire/419/` : un bloc unique portant 623 ancres. Le surlignage est
  abandonné (plafond de 400 marques) et **le bloc le dit** — paragraphe
  `data-testid="avis-surlignage-abandonne-0"`.
- Panneau des extractions de `/lire/419/` : **65 cartes** portent
  l'étiquette « ancre détachée » (46 détachées + 19 sans aucun ancrage).
  Sur `/lire/235/` : **156**.
- Une carte bien ancrée ne porte jamais l'étiquette.

## Vérifications en base

```python
# L'invariant, le seul qui compte vraiment.
CommentaireExtraction.objects.count()          # 983
Page.objects.filter(
    extraction_jobs__entities__commentaires__isnull=False,
).distinct().count()                            # 37

# Aucune page ne doit plus attendre la bascule, sauf les deux connues.
Page.objects.filter(moteur='ancien').values_list('pk', flat=True)  # [97, 680]
```

## Les décisions prises, et pourquoi

**Reconvertir plutôt que vider.** La mesure a renversé le coût supposé :
537 des 542 pages portaient déjà leurs éléments, 94 % des extractions
étaient déjà ancrées. Docling n'a jamais été appelé — donc aucun risque
d'OOM. Vider aurait détruit 983 commentaires pour un gain de temps nul.

**Détacher les ancres mensongères, garder les tronquées.** Sur les
28 096 ancres dormantes rendues officielles par la bascule, **1 402
désignaient un passage sans rapport** (5,0 %), dont **36 commentées** ;
elles sont passées à `DETACHEE`. Surligner une partie du bon passage est
dégradé ; surligner un autre passage est faux — et l'ancre *est* la
preuve.

⚠️ Une première mesure annonçait 1 746 dont 59 commentées. Elle recollait
les portions d'une citation à cheval sur deux blocs **sans séparateur**
(« l'unanimite.La minorite ») et condamnait ainsi 343 ancres justes. Si
vous croisez les chiffres 1 746 / 59 / « 6,2 % » ailleurs, ils sont
périmés.

**Deux seuils différents, assumés.** Créer une ancre exige l'égalité ou
95 % de couverture ; conserver une ancre existante se contente d'une
relation de sous-chaîne. Fabriquer du faux et détruire de l'existant ne
se valent pas.

**Pas de repli par recherche de texte.** Mesuré, avant la purge, sur les
1 707 extractions à offsets 0-0 : 12 retrouvées sans ambiguïté (0,7 %),
75 ambiguës, et **aucune** des 92 commentées. Le code correspondant a été
supprimé.

## Limites connues, à assumer ou à traiter plus tard

- **1 243 extractions restent sans aucune ancre** (offsets 0-0 : jamais
  alignées par l'ancien moteur, dont 92 commentées) ; 1 199 de plus
  n'ont qu'une ancre détachée, soit **2 442 idées montrées nulle part**,
  dont 128 commentées. (Le bilan de la reconversion annonçait 1 715
  « détachées (absent) » : c'était l'état AVANT la purge, qui a depuis
  emporté des pages entières.) Elles sont
  visibles dans le panneau, étiquetées, avec leurs commentaires. Aucun
  moyen automatique de les replacer n'a été trouvé qui ne soit pas du
  devinage. **Décision du propriétaire : on n'y consacre pas plus de
  temps.**
- **Le bouton « Replacer dans le texte »** de l'étalon (maquette
  l. 1671-1682) n'existe pas : l'étiquette annonce l'état, elle n'offre
  pas encore le geste.
- Une extraction dont l'ancre vient d'être détachée n'est pas
  re-tentée par les offsets dans le même passage — choix conservateur.
- La structure de gouttière de la maquette (`.gouttiere`, `.filet-etat`,
  `.barre-progression`, panneau permanent) n'est toujours pas portée :
  c'est le chantier A restant, indépendant de cette livraison.

## Sauvegardes

`tmp/sauvegardes/avant-reconversion-2026-08-10.dump` et
`apres-reconversion-avant-purge-2026-08-10.dump` (format `pg_dump -Fc`,
25 Mo chacun). Restauration :

```bash
docker exec -i hypostasia_dev_postgres pg_restore -U hypostasia \
    -d hypostasia --clean < tmp/sauvegardes/<le dump>
```

## Piège d'environnement découvert

Les 15 tests e2e Playwright échouent en `setUpClass` si
`PLAYWRIGHT_BROWSERS_PATH` n'est pas passé : le défaut pointe
`/app/.cache/ms-playwright`, les navigateurs sont dans
`/home/hypostasia/.cache/ms-playwright`.

```bash
docker exec -e PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright \
    hypostasia_dev_web python manage.py test front.tests.e2e ...
```
