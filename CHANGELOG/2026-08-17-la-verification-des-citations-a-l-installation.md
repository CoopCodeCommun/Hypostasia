# La vérification des citations à l'installation / Citation verification at install time

**Date :** 2026-08-17
**Migration :** Non

## Résumé / Summary

**Quoi / What :** une installation neuve montrait des articles dont **tous** les renvois
étaient « non vérifié ». `bin/install.sh` déclenche désormais la vérification, par le même
chemin que le bouton de l'écran article.
*/ A fresh install showed articles whose every reference was "not verified"; the install now
triggers verification through the same path as the article screen's button.*

**Pourquoi / Why :** l'étage de vérification est **ce qui distingue ce produit** — aucun des
moteurs de synthèse comparables ne vérifie que le passage cité soutient l'affirmation. Le
laisser invisible à l'installation, c'était livrer une démonstration qui ne montre pas
l'essentiel.
*/ Verification is the differentiating stage; leaving it invisible shipped a demo that hid
the point.*

---

## ⚠️ LIRE CECI AVANT DE TOUCHER À LA VÉRIFICATION

Cette section est écrite pour le prochain relecteur — humain ou agent. Les quatre points
ci-dessous ont chacun coûté quelque chose.

### 1. La vérification n'est PAS automatique, et ce n'est pas un oubli

C'est la **question n°3 de `SPEC-synthese-carnet.md`, tranchée par le mainteneur le 9 août
2026** : le juge est le LLM configuré, appelé **en lot** et **à la demande**. Jamais à la
production d'un article.

Deux raisons, et la seconde compte plus que la première :

- **le coût** : juger 145 paires demande 8 appels de plus à chaque production ;
- **le sens** : un verdict porte sa date et son vérificateur. L'attacher automatiquement le
  ferait passer pour une propriété intrinsèque de l'article, alors que c'est un **acte
  séparé, daté, contestable**, qu'un humain déclenche et peut refaire.

Donc : **un article fraîchement produit a TOUS ses renvois en « non vérifié », et c'est
correct.** Ce n'est pas un état d'erreur, c'est un état d'attente — d'où le filet en
pointillé, qui n'affirme rien, et le libellé qui dit quoi faire.

### 2. La cascade est en DEUX temps, et le premier ne coûte rien

C'est le point le plus souvent mal compris, parce qu'on résume la vérification à « on
redemande au LLM ». Non :

| Temps | Ce qu'il demande | Qui répond | Coût |
|---|---|---|---|
| **1. Verbatim** | le texte cité est-il **littéralement** dans les éléments de la note ? | personne — une recherche de sous-chaîne, après normalisation | **nul** |
| **2. Implication (NLI)** | la source **établit-elle** ce que l'affirmation avance ? | le juge, en lots de 20 | facturé |

**L'ordre n'est pas cosmétique.** Le verbatim élimine à coût nul les cas où la citation
elle-même est cassée ; le juge, plus cher, ne traite que ce qui reste. Un passage introuvable
n'atteint **jamais** le juge.

Et le verbatim cherche dans les **`ElementDocument`**, pas dans `Page.text_readability`. Ce
champ est une projection dérivée depuis le 17 août ; y chercher le verbatim déclarait
**118 citations sur 136 introuvables** alors que leur passage était parfaitement présent
(voir `CHANGELOG/2026-08-17-deux-echecs-de-verification-confondus.md`).

### 3. Les deux échecs sont DEUX signaux, jamais un seul

| Verdict | Ce qu'il dit | Qui le pose | Nature | Réparation |
|---|---|---|---|---|
| **citation introuvable** | le passage cité n'est **plus** dans la source | le verbatim **seul** | **intégrité** — la chaîne de preuve est rompue | citation déformée, ou source éditée depuis l'extraction |
| **faible** | le passage **existe** mais n'établit pas l'affirmation | le **juge** | **attribution** — la mauvaise source est citée | l'affirmation ou son renvoi sont à revoir |

Ils étaient confondus sous un seul verdict `FAIBLE` jusqu'au 17 août, et cette confusion
masquait le bug ci-dessus. L'état de l'art mesure que **80,6 %** des affirmations
invérifiables sont des erreurs d'**attribution** et non des hallucinations : savoir dans
laquelle des deux populations on se trouve est ce qui rend le chiffre actionnable.

### 4. Ce que « vérifié » n'établit PAS

En contexte de gouvernance, « vérifié » sera lu comme « validé par quelqu'un ». **Il ne
l'est pas.** D'où trois exigences, inscrites dans `SPEC-synthese-carnet.md § 7.2` :

- **l'état porte son vérificateur** — méthode, modèle, date. Un état sans provenance est un
  argument d'autorité automatisé ;
- **l'état est contestable** — un humain peut poser « contesté », que la machine n'écrase
  jamais ;
- **l'état est par PAIRE** (affirmation, source). Une phrase à deux sources porte deux
  verdicts : en multi-sources, l'attribution correcte tombe autour de 30 %, et l'une des deux
  peut être bonne et l'autre fausse.

---

## Ce qui a été ajouté

| Fichier / File | Changement / Change |
|---|---|
| `front/management/commands/verifier_les_citations_etalons.py` | **Nouveau** — déclenche la vérification des articles du carnet étalon, par le **même** endpoint/job/tâche/juge que le bouton |
| `bin/install.sh` | appelle la commande, après la production des articles |
| `PLAN/Diagrams/03-la-verification-des-citations.md` | **+** la section « Qui déclenche, et par où » : les deux déclencheurs et le chemin unique |

**Idempotente sur le RÉSULTAT** : elle ne juge que les paires **sans verdict**, et saute un
article dont toutes les citations sont jugées. Un redémarrage ne refacture donc rien.

**Elle ne prend aucun raccourci** : même endpoint, même job, même marqueur
`est_verification`, même tâche, même juge que le bouton « Vérifier les citations » de
`article.html`. Un chemin de démonstration qui contournerait le vrai cesserait de l'éprouver.

**Le premier démarrage n'a rien à vérifier** — les articles partent dans la file Celery et
n'existent pas encore quand la commande passe. C'est le démarrage suivant qui les juge, sans
qu'on ait rien à ordonner. Même mécanique que la reprise du périmètre.

### Mesuré le 17 août 2026, Gemini 2.5 Flash, données étalons

| Article | Vérifiées | Faibles | Taux |
|---|---|---|---|
| Wiki « Les open badges… » | 56 | 2 | **97 %** |
| Synthèse « État des lieux… » | 62 | 25 | **71 %** |

**145 paires jugées, 118 vérifiées.** L'écart entre les deux articles est parlant et vaut
d'être gardé : le wiki est étroit et cite serré ; la synthèse générale ratisse large et étire
davantage ses sources. C'est exactement le signal que cet étage doit produire — et ces
145 paires jugées constituent désormais un **étalon** pour comparer d'autres juges.

---

## Comment tester (à la main) / Manual test

### Test 1 — le geste humain

1. Ouvrir un article du carnet 1, connecté avec le droit d'écriture sur le carnet.
2. Le bouton **« Vérifier les citations »** est présent (`article.html`). Sans droit
   d'écriture, il ne doit pas apparaître.
3. Cliquer : le message d'attente s'interroge lui-même et laisse place aux verdicts — il ne
   doit **pas** rester affiché indéfiniment.
4. Cliquer un renvoi **vert** : le panneau nomme le verdict, **son vérificateur et sa date**
   (`verbatim+nli-lot v2 — <modèle>`).
5. Cliquer un renvoi **faible** : le panneau dit *« la source existe mais ne suffit pas »* —
   un problème d'**attribution**.

### Test 2 — le geste de l'installation

```bash
docker exec -w /app hypostasia_web python manage.py verifier_les_citations_etalons
```

Puis **relancer la même commande** : elle doit afficher « toutes déjà jugées — sautée » et ne
créer **aucun** job. C'est ce qui garantit qu'un redémarrage ne refacture rien.

### Test 3 — les verdicts en base

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from collections import Counter
from core.models import SourceLink
print(dict(Counter(SourceLink.objects.values_list('etat_de_verification', flat=True))))"
```

Attendu après une installation complète : majoritairement `verifie`, un reste en `faible`,
et **aucun** `non_verifie`.

### Piège à connaître

**Le juge ne dégrade jamais rien quand il échoue.** Timeout, quota, réponse suspecte : les
verdicts précédents survivent, le lot entier reste « non vérifié », et l'échec est au bilan.
Si tu vois des verdicts disparaître, ce n'est pas le juge — cherche du côté des bornes
périmées (un article édité sans réindexation).
