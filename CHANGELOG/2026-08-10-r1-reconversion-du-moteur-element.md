# R1 : LA RECONVERSION — l'ancien moteur n'affiche plus rien (540 pages basculees, 983 commentaires intacts) + allegement de la base

**Date :** 2026-08-10
**Migration :** Non

**Quoi / What :** decision de gouvernance du 10 aout (le moteur ELEMENT
devient le SEUL moteur) appliquee A LA BASE. 540 des 542 pages ANCIEN
sont passees sur ELEMENT ; il reste 2 pages sans un bloc a lire, laissees
en ANCIEN a dessein. / The 540 remaining ANCIEN pages now run on ELEMENT.

**Ce que la mesure a change dans le plan.** La reconversion s'annoncait
couteuse (§ 9.5 : « reconvertir_avec_docling », et Docling = OOM sur cet
hote). Mesure prealable : **537 des 542 pages portaient DEJA leurs
elements** (dormants, issus des phases de test) et **94 % des extractions
etaient deja ancrees**. Il ne manquait que le flag. Aucun appel Docling
n'a ete necessaire, et la bascule a pris 13 secondes.
/ Measured first: the expensive part was already done.

**Le trou trouve dans la commande existante.**
`basculer_vers_le_moteur_element` (a) ne traitait que les pages SANS
elements — 537 sur 542 lui etaient invisibles, y compris par `--page` —
et (b) ne posait JAMAIS `Page.moteur`, etant anterieure a BR-A. D'ou
l'etat constate : des pages pourvues d'elements ET d'ancrages, toutes
affichees par l'ANCIEN moteur.

**Ce que la reconversion a refuse de faire.** Deux relectures adverses
ont montre que « dans les bornes du texte » n'est pas « au bon
endroit » :
- **47 ancres neuves refusees** : le span etait exploitable mais ne
  montrait pas la citation (dont une de 500 caracteres dont les offsets
  ne couvraient que « l' »). Une ancre n'est posee que si le texte
  surligne EGALE la citation, ou la couvre a 95 % ou plus, la couverture
  etant bornee **dans les deux sens** — surligner sept fois trop est le
  meme mensonge que surligner deux caracteres.
- **1 402 ancres DORMANTES detachees** (5,0 % des 28 096) : ces ancres
  n'avaient jamais ete auditees et devenaient officielles par la
  bascule ; celles-la designaient un passage sans rapport avec leur
  citation — **36 portaient un commentaire humain**. Decision du
  proprietaire : detacher les mensongeres, garder les tronquees (une
  partie du bon passage reste honnete). Detacher n'efface rien —
  extraction et commentaires restent, et chaque pk detache est NOMME sur
  la sortie pour le triage.
  *(Une premiere mesure annoncait 1 746 dont 59 commentees : elle collait
  les portions d'une citation a cheval sur deux blocs SANS separateur et
  condamnait 343 ancres justes. Chiffres corriges apres correctif.)*
- **L'ambiguite est reperee en placant les elements deux fois**, une fois
  depuis le debut et une fois depuis la fin : tout element que les deux
  lectures separent avait le choix, on n'y ancre pas. Regarder la « zone
  libre » autour de la position gloutonne revenait a supposer resolu ce
  qu'on cherchait a verifier.

**Le repli par recherche de texte a ete SUPPRIME** (~100 l. de code
mort) : mesure sur les 1 707 extractions a offsets 0-0 — il en retrouve
12 sans ambiguite (0,7 %), en trouve 75 a plusieurs endroits, et AUCUNE
des 92 commentees. Le gain ne payait ni la complexite ni le risque.

**Deux defauts d'affichage exposes par la bascule, corriges :**
1. Un bloc portant plus de 400 marques rend le texte nu — la page 419
   affichait 623 ancres et pas un surlignage, SANS un mot. Le code
   promettait de « le dire dans le bloc » et n'emettait qu'un
   `logger.warning`. Le bloc l'annonce desormais (5,01:1 clair /
   5,69:1 sombre, mesure au navigateur).
2. Les extractions detachees etaient atteignables mais INDISCERNABLES
   dans le panneau. Etiquette « ancre detachee — aucun passage, a
   replacer » (etalon maquette l. 1671-1682), sur les seules cartes
   concernees : 65/65 sur la page 419, 156/156 sur la 235.

**ALLEGEMENT DE LA BASE (decision du proprietaire, meme jour)** : la base
d'essai portait 98 titres en plusieurs exemplaires, un sujet jusqu'a 33
fois. `purger_les_notes_inutiles` retire les doublons en gardant un
exemplaire par titre. Trois gardes : jamais une note commentee, jamais
une source citee (les sources d'une synthese sont des NOTES — la
supprimer viderait la preuve en laissant l'article debout) ni une page
parent, jamais le dernier exemplaire d'un titre (ce qui garantit qu'il
reste des wikis et des syntheses). Un garde-fou refuse d'agir si la
selection emporte le moindre commentaire, et il se **reverifie dans la
transaction** — le controle du bilan a lieu avant, l'application est en
service. `AncrageExtraction.element` etant en PROTECT, les portions
partent d'abord, sinon la suppression echoue en bloc.

**La purge CONVERGE, et c'est un correctif de relecture** : les gardes se
calculent sur l'etat AVANT suppression, or un protecteur peut lui-meme
partir dans le passage (l'article citant emporte ses SourceLink, le
parent perd ses enfants). Un premier passage donne pour complet laissait
encore 15 pages et 1 179 extractions au lancement suivant — un bilan
incomplet, donc un bilan faux. La commande simule desormais les tours
successifs jusqu'au point fixe. Relancee apres coup : « 0 page a
supprimer ».

| Etat | Avant | Apres |
|---|---|---|
| Pages | 546 (542 ancien / 4 element) | 213 (2 ancien / 211 element) |
| **Commentaires humains** | **983** | **983** |
| Pages commentees | 37 | 37 |
| Extractions | 30 325 | 24 253 |
| Ancrages | 28 617 toutes « ancree » | 22 148 ancree / 1 311 detachee |
| Types de note | — | 204 notes / 7 syntheses / 2 wikis |

**Verifications** : 38 tests de reconversion, 14 de purge, 6 d'etiquette
detachee et d'avis de plafond, 2 du service de rendu. Suite complete :
1 621 tests. TROIS relectures adverses, la derniere portant sur le code
ET sur les chiffres de cette entree — elle a trouve la non-convergence
de la purge et trois chiffres faux, corriges ici. Deux passages au
navigateur reel avec contrastes CALCULES dans les deux themes.
Sauvegardes `tmp/sauvegardes/` (avant-reconversion,
apres-reconversion-avant-purge).

**Deux tests-mensonges PREEXISTANTS corriges au passage** (tous deux
rouges sur la branche avant cette session, sans rapport avec elle) :
`test_drawer_z_index_superieur_backdrop` cherchait les classes
`z-40`/`z-50`, disparues le 10 aout quand les z-index sont passes en
style INLINE (build Tailwind fige) ; `test_type_lien_choices` attendait
QUATRE types de lien alors qu'un cinquieme, `cite`, est arrive avec la
phase B de la synthese (migration core.0048, 9 aout).

**Consigne d'environnement** : les 15 e2e Playwright echouent en
`setUpClass` sans `PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/
ms-playwright` — le defaut pointe `/app/.cache`. Avec la variable, ils
passent.

| Fichier | Changement |
|---|---|
| `core/management/commands/basculer_vers_le_moteur_element.py` | selection par flag, deux chemins, pose du flag, verification des ancres neuves ET dormantes, ambiguite aller-retour, resilience par page, verrou, repli mort supprime |
| `core/management/commands/purger_les_notes_inutiles.py` | **nouveau** : allegement garde |
| `core/tests/test_reconversion_moteur.py` | **nouveau** : 38 tests |
| `core/tests/test_purge_notes.py` | **nouveau** : 12 tests |
| `front/services/rendu_elements.py` | `le_surlignage_depasse_le_plafond`, `idees_non_surlignees` par bloc |
| `front/templates/front/includes/_blocs_elements.html` | l'avis « trop d'idees pour les surligner » |
| `front/templates/front/includes/drawer_vue_liste.html` | l'etiquette « ancre detachee » |
| `front/views.py` | `est_detachee` par entite (drawer), seulement sur page ELEMENT |
| `front/tests/test_ancres_detachees_drawer.py` | **nouveau** : 4 tests |
| `front/static/front/css/maquette.css` | avis + etiquette (grammaire des etats : filet gauche) |
| `front/templates/front/base.html` | bump `maquette.css?v=23` |

### Migration
- **Migration necessaire / Migration required :** Non. Les deux commandes
  sont des operations de DONNEES, a lancer a la demande, `--a-blanc`
  d'abord.

---

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

