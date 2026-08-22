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

## LangExtract 1.6.0 : monté — ce qui reste ouvert derrière

*Constaté puis fait le 18 août 2026.*

**La montée EST faite** : `pyproject.toml` demande `langextract>=1.6.0` et
`uv.lock` l'épingle. Elle s'installe au prochain `uv sync`, c'est-à-dire au
prochain démarrage de conteneur (`bin/install.sh`, étape 1/6) — **aucune
reconstruction d'image n'est nécessaire**, le venv vit dans le bind mount du
dépôt. Détail dans `CHANGELOG/2026-08-18-langextract-1-6.md`.

**Ce qui reste ouvert derrière**, et qui demande des appels facturés :

| Point | Ce qu'il faudrait |
|---|---|
| `use_schema_constraints` reste à `False` pour `COMPATIBLE_OPENAI`, alors que 1.6.0 apporte `providers/schemas/openai.py` et sait poser un `response_format: json_schema` | L'activer fermerait le risque du « JSON nu » **à la source** au lieu de compter sur la tolérance du parseur. Éprouver d'abord que Mistral honore ce format |
| **L'aligneur flou est passé de `difflib` à LCS** — `_DEFAULT_FUZZY_ALGORITHM = "lcs"`, barrière neuve `fuzzy_alignment_min_density = 1/3`, et `fuzzy_alignment_threshold` **change de sens** à défaut identique. Le moteur ELEMENT **jette** toute extraction non alignée | Mesurer avant/après sur un corpus. **Rayon d'action mesuré le 18 août** : 112 extractions stockées, 112 verbatims exacts, 112 ancrées — l'aligneur flou n'avait produit **aucune** ancre. *Réserve : on ne voit que les survivantes* |
| `suppress_parse_errors=True` continue d'avaler toutes les autres `FormatError` — JSON invalide, items non-mapping, clôtures multiples | Un job peut toujours finir `completed` à zéro extraction. Seul le cas de la **liste nue** est refermé |
| `providers/gemini.py` gagne 3 tentatives avec backoff jusqu'à 16 s sur 408/429/5xx | En tenir compte dans les mesures de durée |

## Le seuil de vérification n'a pas de journal durable

*Constaté le 18 août 2026, au chantier du score.*

Déplacer `Configuration.seuil_de_verification` laisse une trace dans les
journaux du serveur (`logger.info` dans `ConfigurationIAViewSet.seuil`) et un
compte rendu à l'écran, mais **rien en base**. Pour un outil de délibération,
déplacer le seuil du collectif est un acte de gouvernance : qui l'a fait, quand,
et de combien à combien devrait survivre à une rotation de journaux.

**Arbitrage attendu du mainteneur** : un modèle d'audit, ou l'acceptation du
journal seul.

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

---

## L'extension navigateur n'est pas soumissible sur les stores

*Constaté le 20 août 2026, audit dédié du paquet `extension/` contre les
politiques Chrome Web Store et Firefox AMO.*

Deux défauts ont été corrigés le jour même avec le chantier
`2026-08-20-le-webclipper-choisit-son-carnet.md` : la ressource
`init_htmx_sidebar.js`, **déclarée dans `web_accessible_resources` et absente du
paquet**, et la déclaration `data_collection_permissions: {"required":
["none"]}` — factuellement fausse, l'extension transmettant le HTML complet de
la page — passée à `["websiteContent"]` (valeur vérifiée sur la documentation
Mozilla ; la clé est obligatoire pour toute nouvelle soumission depuis le
3 novembre 2025).

> ### ⚠️ Quatre des cinq points ci-dessous ont été RÉGLÉS le 21 août 2026
> par le chantier de publication Firefox (commits `b9d8071`, `3e65de2`), et
> **cette section les décrivait encore comme ouverts** — vérifié dans le paquet
> le 22 août. Ce qu'il reste est le point 5, plus le travail humain de
> soumission.
>
> - `<all_urls>` a disparu : `host_permissions` ne porte plus que
>   `https://hypostasia.org/*` et `https://beta.hypostasia.org/*`, le reste
>   passe par `optional_host_permissions`. `permissions` se limite à
>   `activeTab`, `scripting`, `storage`.
> - `lib/` ne contient plus que `Readability.js` : les 109 Ko de SweetAlert
>   sont partis.
> - La sidebar morte est supprimée — `background.js`, `content.js`,
>   `sidebar.html`, `sidebar.js` ne sont plus dans le paquet. Le point 4
>   (défaut sur `beta.hypostasia.org`) disparaît avec elle.
> - La **politique de confidentialité est écrite** et hébergée
>   (`front/templates/front/includes/confidentialite.html`).

**Ce qui reste ouvert :**

1. **`hypostasia/settings.py` code en dur
   `chrome-extension://lmflifaokphpaknpdnmdmhdiaeiieomd`** dans
   `CSRF_TRUSTED_ORIGINS`. C'est l'identifiant d'une extension chargée en mode
   développeur ; il **changera** à la publication (aucune clé `key` n'est
   épinglée dans le manifest). L'extension s'authentifiant par
   `Authorization: Token`, elle ne dépend probablement pas de cette entrée — à
   vérifier avant de la retirer ou de la passer en variable d'environnement.
   **Toujours présent le 22 août 2026** (`settings.py:192`).

**À faire avant toute soumission**, et c'est du travail humain, pas du code :
formulaire « Data usage / Privacy practices » du dashboard, justification écrite
de chaque permission, notes au relecteur AMO expliquant que le serveur
destinataire est **choisi et hébergé par l'utilisateur**. Les captures d'écran,
elles, sont **déjà dans le dépôt** (`extension/screen/`, quatre vues), et la
politique de confidentialité est écrite.

Le store le plus proche est **Firefox AMO** : `browser_specific_settings`, l'id
gecko et la structure `data_collection_permissions` sont déjà en place. Chrome
demande davantage de travail neuf.

---

## `SessionAuthentication` sur l'API de l'extension : lecture oui, ecriture 403

*Constaté le 21 août 2026, à l'installation de l'extension dans Firefox.*

`PageViewSet` et `SidebarViewSet` (`core/views.py`) déclarent
`authentication_classes = [TokenAuthentication, SessionAuthentication]`. Or ces
deux ViewSets ne servent **que** l'extension navigateur, qui s'authentifie par
jeton. La session n'y est réellement utilisée que par des tests
(`front/tests/test_capture_web_docling.py` fait `force_login` puis `POST`).

Le piège, mesuré :

```
GET  /api/pages/me/          -> 200 {'authenticated': True, 'username': 'jonas'}
GET  /api/pages/mes_carnets/ -> 200 [...la liste...]
POST /api/pages/             -> 403 {"detail":"CSRF Failed: CSRF cookie not set."}
```

Un client porteur d'un cookie de session **lit** l'API mais ne peut pas y
**écrire** : `SessionAuthentication.enforce_csrf()` exige un jeton CSRF sur les
méthodes d'écriture. **Le `@method_decorator(csrf_exempt, name="dispatch")`
posé sur les deux ViewSets ne protège pas de ça** — le contrôle vit dans la
classe d'authentification, pas dans le décorateur. C'est un classique de DRF, et
il ne se voit pas à la lecture de la vue.

Ce n'est plus un problème pour l'extension : depuis le 21 août ses appels
portent `credentials: 'omit'`. Le piège reste posé pour tout autre client qui
arriverait avec une session.

> ⚠️ **NE PAS « corriger » en retirant `SessionAuthentication`.** C'était la
> correction envisagée le matin du 21 août ; elle est devenue **destructrice**
> le soir même. `PageViewSet.mon_jeton` — la connexion en un clic de l'extension
> — s'authentifie **par la session**, et c'est tout son mécanisme : la session
> ne peut pas *écrire* depuis une extension Firefox (origine aléatoire par
> installation, jamais whitelistable), mais elle peut *lire*, et un GET n'est
> pas soumis au contrôle CSRF. La retirer supprimerait la seule façon de
> connecter l'extension sans copier-coller.
> Voir `CHANGELOG/2026-08-21-connecter-l-extension-en-un-clic.md`.

Ce qui reste vrai, et qu'il faut lire comme une **contrainte** et non comme un
défaut à réparer : sur ces deux ViewSets, une session **lit** mais n'**écrit**
pas. Tout client qui arriverait avec une session et tenterait un `POST` recevra
un 403 CSRF, sans que la vue ne le laisse deviner.

**Note de sécurité, pour éviter une inquiétude mal placée** : ce chemin n'est pas
exploitable depuis un site web ordinaire. `CORS_ALLOW_ALL_ORIGINS = True` rend
`Access-Control-Allow-Origin: *`, et le navigateur **refuse** une requête avec
cookies (`credentials: 'include'`) quand la réponse répond `*`. Seule une
extension disposant de la permission d'hôte contourne le CORS — ce qui est le
propre des extensions, pas un défaut de cette API.
