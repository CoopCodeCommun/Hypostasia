# La planche 04 : « La nuit des wikis » — le seul mécanisme qu'aucun diagramme ne montre

**Constaté le 23 août 2026, isolé le 1er septembre 2026 quand le reste de la note
d'origine a été codé. Rien n'est écrit.**

Cette note est le **reste** de
`2026-08-23-la-doc-ment-sur-la-nuit-et-la-verification.md`, supprimée le
1er septembre : ses six corrections sont faites
(`CHANGELOG/2026-09-01-le-locuteur-l-aide-et-la-doc.md`). Celle-ci ne l'était pas,
parce qu'elle ne corrige rien — elle **écrit ce qui manque**.

## Ce qui existe, et ce qui n'existe pas

| Planche | Ce qu'elle montre |
|---|---|
| `01` | l'ingestion |
| `02` | du prompt à l'article sourcé — *la nuit y apparaît depuis le 1er septembre, mais seulement comme un nœud* |
| `03` | la vérification des citations — *trois déclencheurs depuis le 1er septembre* |

**Aucune ne montre la nuit elle-même.** Or c'est le seul mécanisme du projet qui
**applique sans humain** (`fait_par=None`), et le seul qui **facture** sans que
personne n'ait rien demandé.

## Ce que la planche doit porter

1. **le planificateur** — `celery_beat` et le `beat_schedule` de
   `hypostasia/celery.py` : la passe de nuit, puis le récapitulatif du matin. **Un
   seul beat**, jamais deux : deux enverraient chaque tâche en double, donc
   doubleraient la facture du rédacteur ;
2. **les deux conditions de reprise** d'un wiki ;
3. le **fan-out** et le **compteur de fermeture** — comment la passe sait qu'elle a
   fini ;
4. le **tour** lui-même : proposition d'opérations, application par le même
   applieur que l'humain ;
5. **l'enchaînement facturé** : toute écriture de corps déclenche la vérification,
   qui part avec les quatre juges locaux et un juge d'API ;
6. le **récapitulatif du matin**.

## Ce qui casse si on ne l'écrit pas

Le mécanisme le plus coûteux et le moins visible du projet reste **connu de son
seul code**. Trois documents ont déjà menti sur lui — les planches 02 et 03, et le
README des Diagrams — précisément parce qu'aucune planche ne l'obligeait à se
montrer en entier.

## Avant d'écrire

**Lire le code, pas les planches voisines.** C'est la leçon des six corrections du
1er septembre : les planches se recopiaient entre elles. Les sources sont
`hypostasia/celery.py`, `front/tasks.py` (`mettre_a_jour_un_wiki_la_nuit`,
`_ecrire_le_corps_d_un_article`, `enchainer_la_verification`) et
`core/services/section_ops.py`.
