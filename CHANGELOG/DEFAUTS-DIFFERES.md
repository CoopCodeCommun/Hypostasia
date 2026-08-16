# Défauts connus, différés

> Ce que les revues ont trouvé, que personne n'a corrigé, et qui n'est bloquant
> pour rien. Chaque ligne porte sa date de constat et l'endroit exact où elle
> vit dans le code.
>
> Extrait le 16 août 2026 de
> `.superpowers/sdd/2026-08-11-charger-fixtures-sample/progress.md`, sorti du
> dépôt le même jour. Deux passations renvoyaient à ce fichier d'artefacts
> d'agent pour la seule information durable qu'il portait ; elle est ici.

---

## Arbitrages produit en attente

### Une transcription Voxtral échouée refait un appel **facturé** à chaque relance

*Constaté le 11 août 2026 — le plus coûteux des trois.*

Une transcription qui échoue laisse une page **sans aucun élément**. Chaque
relance de `charger_fixtures_sample` la voit incomplète, la supprime, et
**relance l'appel Voxtral — qui est facturé**. Une boucle de rechargement paie
donc plusieurs fois la même transcription ratée.

C'est cohérent avec le comportement voulu pour `--reset` (« la seule façon de
rejouer l'appel Voxtral »), mais ça le contredit en pratique : le rejeu se
produit sans qu'on l'ait demandé.

**Arbitrage attendu du mainteneur** : marquer la page en échec pour ne plus la
reprendre, ou assumer le rejeu.

Chantier voisin déjà spécifié, non exécuté :
`docs/superpowers/plans/2026-08-11-suppression-et-echec-voxtral.md`, qui prévoit
de faire passer `TranscriptionJob.page` de `CASCADE` à `SET_NULL`.
⚠️ **Ce chantier rendra `job.page` nullable**, et
`_destinataires_de_notification` (`front/tasks.py:50`) fait `page.owner_id` sans
garde : il lèvera. C'est une mine posée, pas un bug actuel.

### `Page.delete()` laisse le média sur le disque

*Constaté le 11 août 2026.*

Supprimer une note ne supprime pas son `source_file`. Chaque rechargement des
fixtures dépose donc un média orphelin de plus dans `media/`. Rien ne casse ;
le disque se remplit.

**Mesuré le 16 août 2026, en mettant la sauvegarde en place :** `media/` pèse
**473 Mo** pour **7245 fichiers** — qui ne portent que **18 contenus
distincts**. Tout le reste est un empilement de copies des mêmes documents
étalons, une par rechargement. C'est borg qui l'a révélé : il archive 483 Mo
en **2,18 Mo dédupliqués**, avec 31 chunks uniques pour 7258 chunks au total.

La sauvegarde n'en souffre pas (la déduplication absorbe tout), mais une
restauration recopie bien les 7245 fichiers, et le disque de la prod les porte
tous.

Le correctif est spécifié dans le même plan non exécuté (signal `post_delete`).

---

## Affichage

### `--a-blanc` annonce « serait créée » sous une ligne qui dit « réutilisée »

*Constaté le 11 août 2026.*

`_creer_la_config_de_transcription` rend `None` en mode `--a-blanc`, ce qui fait
afficher « Voxtral Mini (serait créée) » juste sous une ligne annonçant
« réutilisée ». Contradiction d'affichage seule — aucun effet sur ce que la
commande écrit réellement.

---

## Robustesse, sans conséquence observée

*Tous constatés le 11 août 2026, sur `charger_fixtures_sample`.*

| Défaut | Où |
|---|---|
| Rattrapage d'ingestion non atomique (pas de `select_for_update`) — course théorique avec un worker Celery vivant | la commande |
| `create_user` puis `set_password` + `save` = un INSERT suivi d'un UPDATE | `charger_fixtures_sample.py:117-121` |
| `_charger_le_markdown` lit le fichier en texte puis le ré-encode en bytes pour `ContentFile` | `charger_fixtures_sample.py:335-355` |
| `TranscriptionJob` créé avec `status='pending'` en dur au lieu de `TranscriptionJobStatus.PENDING` | la commande |
| « Gio » employé au sens décimal de Go dans les commentaires (préexistant) | commentaires |

## Trous de couverture de test

*Constatés le 11 août 2026.*

- Aucun test ne combine `--a-blanc` avec `MISTRAL_API_KEY` présente sur le
  chemin mp3.
- Pas de test dédié pour la branche « url détenue par un autre owner ».
- Le retour `'?'` de `_elements_du_resultat` n'est vérifié que par lecture, pas
  par un test.

---

## Une leçon, gardée parce qu'elle a coûté un serveur

*11 août 2026.* Une migration avait été interdite à un agent alors que son code
lisait déjà la colonne. Le serveur de dev est tombé en `ProgrammingError` sous
les yeux du mainteneur.

**Une migration doit être appliquée à la base de dev dès que le code la
référence** — le serveur de dev est permanent, il ne redémarre pas sur un état
cohérent tout seul.
