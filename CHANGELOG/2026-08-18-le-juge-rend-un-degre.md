# Le juge rend un degré, le seuil passe à l'affichage / The judge returns a degree

**Date :** 2026-08-18
**Migration :** Oui — `core.0070_score_de_verification`
```bash
docker exec -w /app hypostasia_web python manage.py migrate core
```

## Résumé / Summary

**Quoi / What :** le juge de vérification ne répond plus « soutient /
ne_soutient_pas » mais un **degré de 0 à 100**. Le seuil qui sépare « vérifié »
de « faible » devient un **réglage d'affichage**, posé sur `Configuration` et
modifiable depuis l'écran de configuration IA — le déplacer **ne rejuge rien**.
`INTROUVABLE`, `CONTESTÉ` et `NON VÉRIFIÉ` sont inchangés.
*/ The verification judge now returns a 0-100 degree instead of a binary
verdict. The threshold becomes a display setting on Configuration, movable from
the AI configuration screen; moving it re-labels without re-judging.*

**Pourquoi / Why :** le prompt demandait à la source d'« établir » ce que
l'affirmation avance, sans dire si cela voulait dire **tout** établir ou
seulement **la part que cette source revendique**. Mesuré le 18 août sur quinze
paires d'une même affirmation, cinq modèles : de **0 à 14** verdicts positifs.
Le désaccord ne venait pas des juges, **il venait de la question**. Un seuil
écrit dans un prompt est en outre **figé au moment du jugement** : en changer
signifierait tout rejuger, donc repayer, et perdre la mesure précédente — or
c'est précisément un arbitrage que le collectif doit pouvoir refaire.
*/ "Establish" was never defined, and five models spread from 0 to 14 positive
verdicts on the same fifteen pairs. A threshold written into a prompt is frozen
at judging time; as a setting, it can be revisited for free.*

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | `SourceLink.score_de_verification` (flottant, NULL possible), `SourceLink.provenance_du_verbatim`, `ProvenanceDuVerbatim`, `Configuration.seuil_de_verification` |
| `core/migrations/0070_score_de_verification.py` | les trois champs |
| `core/services/verification.py` | prompt à degré, `MOTIF_DE_SCORE`, `_scores_de_la_reponse`, `_etat_pour_le_degre`, `seuil_de_verification`, `appliquer_le_seuil`, `provenance_du_juge_courant` ; `VERSION_DE_LA_METHODE` → `verbatim+nli-score v3` |
| `core/services/synthese.py` | le report de verdict emporte **aussi** le degré et sa provenance |
| `front/views.py` | `ConfigurationIAViewSet.seuil` — le geste qui déplace le seuil |
| `front/serializers.py` | `SeuilDeVerificationSerializer` (bornes 0–100) |
| `front/views_synthese.py` | le panneau de preuve reçoit le seuil courant |
| `front/templates/front/corpus/partials/preuve.html` | le curseur 0–100, le seuil marqué dessus, le nom du juge |
| `front/templates/front/corpus/_style_maquette.html` | le style du curseur, aux tokens |
| `front/templates/front/includes/config_ia_toggle.html` | le réglage du seuil et son compte rendu |
| `front/management/commands/geler_l_etalon_du_juge.py` | gèle aussi le degré et la provenance du verbatim |
| `core/tests/test_score_de_verification.py` | **nouveau** — 18 tests |
| `front/tests/test_degre_a_l_ecran.py` | **nouveau** — 9 tests |
| `core/tests/test_verification.py` | les charges utiles des mocks passent en degrés |
| `benchmarks/juge_de_verification/comparer_un_juge.py` | convertit le degré par le seuil, et **dit** que la comparaison est croisée |
| `benchmarks/juge_de_verification/comparer_les_seuils.py` | motif v2 **gelé localement** : ce banc mesure la question d'avant |
| `benchmarks/chaine_complete/comparer_la_chaine.py` | convertit le degré par le seuil |

## Les quatre décisions de conception, et ce qu'elles évitent

### 1. Pas de nouvel état : `VÉRIFIÉ` / `FAIBLE` deviennent **dérivés**

Un état `JUGE` neuf avait été proposé, puis abandonné. Il aurait fait tomber à
zéro les compteurs de l'écran d'article — et **un compteur qui tombe à zéro
n'est pas visible, c'est une dégradation silencieuse**, celle que
`front/views_synthese.py` documente déjà comme « pire qu'une erreur ». Il aurait
aussi cassé `geler_l_etalon_du_juge` et `verifier_les_citations_etalons`, qui
continuent aujourd'hui de fonctionner **sans une ligne de modification**.

Les trois libellés restent donc stockés, écrits par **un écrivain unique**,
`appliquer_le_seuil`, appelé au jugement et au changement de seuil. Une seule
source (le degré), un seul écrivain : ce n'est pas la duplication qu'on voulait
éviter, c'est une matérialisation.

### 2. Un champ de provenance, parce que le témoin évident est destructible

Le recalcul doit savoir, longtemps après le jugement, si le verbatim a été
trouvé dans la source ou dans un commentaire du débat — c'est ce qui départage
`VÉRIFIÉ` de `SOURCÉ PAR LE DÉBAT` au-dessus du seuil.

`commentaires_source` ne peut pas servir de témoin : `CommentaireExtraction.entity`
**et** `.user` sont tous deux en `CASCADE`. Supprimer une extraction ou un compte
efface le témoin, et le recalcul poserait alors `VÉRIFIÉ` sur un verbatim qui
n'a **jamais** été dans la source — un blanchiment par un réglage d'affichage.

D'où `provenance_du_verbatim`, posé par le parcours déterministe : il enregistre
un **fait**, pas un verdict. Bénéfice second : l'invariant I7 reste **intact**,
donc aucun addendum de spec n'a été nécessaire.

### 3. Colonne flottante, parseur entier

Deux décisions distinctes, et les confondre créait un silence neuf.

La **colonne** est flottante parce qu'un juge local à logits rend une
probabilité continue (mesure du 18 août : AUC 0,923, seuil utile 0,378).

Le **parseur** du protocole texte n'accepte que des entiers 0–100. Un juge qui
répondrait « 1: 0.92 » au lieu de « 1: 92 » rendrait des valeurs **dans** les
bornes : tout le lot basculerait en « faible » **sans une erreur**. Avec
l'entier seul, la ligne ne correspond pas, la paire n'a pas de verdict, et rien
n'est dégradé.

Le rejet du lot **entier** sur anomalie de **structure** (indice dupliqué, hors
lot) est inchangé — c'est la signature d'une injection. Une anomalie de
**valeur** ne coûte que sa paire.

### 4. Le curseur ne vit que dans le panneau de preuve

`PRESENTATION-V3.md § 3.6` a arbitré, sur une corrélation mesurée de
**r = −0,96** entre la précision des citations et l'utilité perçue : « trois
états visuellement discrets, **pas un score par phrase** — la rigueur est
disponible **au clic**, pas imposée à la lecture ». Le corps de l'article garde
donc ses trois filets de couleur, sans un chiffre. Un test le verrouille
(`LeCorpsDeLArticleNePorteAucunChiffreTest`).

## Deux limites, nommées

**Le seuil appartient au couple (juge, collectif), pas au collectif seul.**
45/100 chez un juge d'API sollicité par le protocole texte et ~38/100 chez un
juge local à logits ne sont pas le même réglage. `appliquer_le_seuil` **refuse
donc de toucher les degrés d'un autre juge**, et l'écran compte ceux qu'il a
laissés de côté.

**L'échelle des juges d'API n'a que quatre crans.** Mesuré : `{0, 40, 70, 100}`,
aucune valeur intermédiaire chez aucun des cinq modèles. Tout seuil de 41 à 70
sépare donc à l'identique ; 45 est le milieu de ce palier. **N'affichez jamais
de décimale** sur un chiffre qui n'en porte pas.

---

## Comment tester (à la main) / Manual test

### Test 1 — le degré s'affiche avec son seuil et son juge

1. Ouvrir un article (wiki ou synthèse) d'un carnet.
2. Cliquer « Vérifier les citations », attendre la fin.
3. Cliquer un renvoi `[N]` dans le texte → le panneau de preuve s'ouvre.
4. **Attendu** : sous l'état, une barre 0–100, un trait vertical au seuil, et la
   phrase « Soutenu à N sur 100 — seuil 45. Degré rendu par `<méthode> —
   <modèle>` ».
5. **Attendu** : le corps de l'article ne porte **aucun** chiffre — seulement
   les filets de couleur.

### Test 2 — déplacer le seuil ne rejuge rien

1. Noter l'état d'un renvoi dont le degré est 70 (vérifié au seuil 45).
2. Dans le panneau de configuration IA, mettre le seuil à **80**, « Appliquer ».
3. **Attendu** : « Seuil 45 → 80 : N renvois ont changé d'état. »
4. Rouvrir le panneau de preuve du même renvoi.
5. **Attendu** : l'état est passé à « faible », **le degré est toujours 70**, et
   le trait du seuil a bougé. Aucun appel de modèle n'a eu lieu — vérifiable
   dans les journaux : `docker compose logs web | grep "seuil de verification"`.
6. Remettre 45 : l'état revient à « vérifié ».

### Test 3 — un verdict sans juge n'a pas de barre

1. Trouver (ou provoquer) une citation `INTROUVABLE` — éditer le texte d'une
   extraction citée pour qu'il ne soit plus dans sa source, puis revérifier.
2. **Attendu** : le panneau montre « Citation introuvable » et **aucune barre**.
   Une barre à zéro mentirait : aucun juge ne s'est prononcé.

### Test 4 — un seuil hors bornes est refusé

1. Saisir `140` dans le champ du seuil, « Appliquer ».
2. **Attendu** : refus (400), le seuil en base est inchangé, aucun état ne bouge.

### Vérifs DB

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import Configuration, SourceLink, TypeLien
print('seuil :', Configuration.get_solo().seuil_de_verification)
liens = SourceLink.objects.filter(type_lien=TypeLien.CITE)
print('avec degré  :', liens.filter(score_de_verification__isnull=False).count())
print('sans degré  :', liens.filter(score_de_verification__isnull=True).count())
for l in liens.filter(score_de_verification__isnull=False)[:5]:
    print(f'  {l.pk}: {l.score_de_verification} -> {l.etat_de_verification} ({l.provenance_du_verbatim}) par {l.verifie_par}')
"
```

**Attendu** : tout lien à degré non nul porte `verifie` ou `source_debat`
au-dessus du seuil, `faible` en dessous — et **aucun** lien `introuvable`,
`conteste` ou `non_verifie` ne porte de degré.

### Les contrastes du curseur — calculés, pas devinés

WCAG 1.4.11 (composant non textuel) exige **3:1**. Calculés sur les tokens
réels, fond `--papier-panneau`, piste = `--encre-douce` à 22 % :

| | clair | sombre |
|---|---|---|
| contour de la piste vs fond | **5,24:1** | **5,94:1** |
| remplissage « vérifié » vs piste | 3,86:1 | 8,09:1 |
| remplissage « faible » vs piste | **3,54:1** | 7,39:1 |
| marque du seuil vs piste | 12,12:1 | 10,25:1 |

**Pourquoi un contour plutôt qu'une piste plus sombre.** Le fond de la piste à
22 % n'est qu'à **1,34:1** du papier : la borne de la barre serait invisible, et
une longueur de remplissage sans sa borne ne veut rien dire. Mais l'assombrir
assez pour atteindre 3:1 ferait tomber le remplissage **sous** 3:1 contre la
piste — mesuré : à 25 % d'encre, « faible » tombe à 2,79:1. **Les deux exigences
se contredisent sur ces tokens.** Un contour à pleine force les concilie : il
porte la borne à 5,24:1 sans toucher au contraste intérieur.

### Vérification navigateur — reste à faire

Les contrastes sont établis ; le **rendu** ne l'est pas. La stack ne prend aucun
port de l'hôte (le Traefik partagé détient 80/443), et je n'avais pas le domaine :
le curseur n'a donc **pas été vu** dans un navigateur, ni en clair ni en sombre.
Restent à contrôler à l'œil : l'alignement du trait de seuil sur un
`border-box` de 8 px, le rendu du `border-radius` quand le remplissage vaut 100,
et le cas `score = 0` (remplissage de largeur nulle).
