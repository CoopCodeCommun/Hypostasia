# Drapeau de lecture par destinataire — rapport

## Addendum — revue adverse : deux defauts Important corriges

**Defaut A — premisse fausse de la migration 0060.** Mon rapport initial
affirmait que les booleens `notification_lue=True` venaient forcement d'un
clic du proprietaire de la note, "seul marqueur possible avant
l'elargissement". Faux, et verifiable : `core/migrations/0032` fait
`ExtractionJob.objects.update(notification_lue=True)` sur TOUS les jobs, et
`core/migrations/0058` fait de meme sur toutes les ingestions terminees —
des ESTAMPILLAGES EN MASSE sans destinataire, poses pour eviter qu'un
compteur enorme s'allume au deploiement. Attribuer uniquement a l'auteur
de la note aurait fait apparaitre, au premier chargement, tout l'historique
d'un carnet comme "non lu" pour son proprietaire — le meme compteur enorme
que 0032/0058 existaient pour eviter.

**Corrige** : `0060` calcule desormais le MEME ensemble de destinataires
que `_destinataires_de_notification` (`front/tasks.py:50`) — proprietaire
de la note PLUS proprietaires des carnets qui la contiennent — via
`_calculer_les_triples_a_migrer(apps)`, 6 requetes SELECT bornees (2 par
type : une via `page__owner`, une via
`page__appartenances_dossiers__dossier__owner`) plus 3 requetes de
comptage "sans destinataire", puis UN `bulk_create()`. Aucune requete par
tache. Le rollback reutilise la MEME fonction pour recalculer exactement
le meme ensemble de triples et ne supprime QUE ceux-la (regroupes par
type, un DELETE par type via un grand OR de paires tache/utilisateur) —
plus le `.all().delete()` qui aurait aussi efface des lectures reelles
posterieures. Teste par `core/tests/test_migration_notification_par_destinataire.py`
(nouveau, patron `MigrationEstampillageTest` de `test_role_special.py`) :
3 tests — double attribution (note + carnet), page sans aucun destinataire
(ni owner ni carnet possede, pas d'erreur), et rollback qui epargne une
ligne reelle posterieure sans rapport. Les 3 passent.

**Defaut B — deux regles opposees sur la meme donnee.** Le comptage du
badge traite `ingestion_maj_le=NULL` comme un fantome (correction 2
initiale), mais `relancer_ingestion` (`front/views.py`) faisait encore
`derniere_maj is not None and ...` — NULL y restait "pas fantome", donc
relance REFUSEE. Une page active sans date devenait invisible au badge
ET impossible a relancer : une impasse, pire que le defaut d'origine (au
moins le badge la signalait avant).

**Corrige** : `fantome = derniere_maj is None or (...)` dans
`relancer_ingestion` — meme convention que le badge. Test
`test_pas_de_relance_pendant_une_ingestion_active` corrige pour poser une
date recente explicite (il testait par accident le cas NULL, pas le cas
"vraiment actif") ; nouveau test
`test_une_ingestion_active_sans_date_se_relance` verifie que NULL autorise
desormais la relance (200, `delay` appele). `front/tests/test_ingestion_ui.py`
: 21/21 verts.

**Defaut mineur C — test non discriminant.** `IngestionFantomeSansDateDansLeMenuTest`
passait avec ou sans le correctif : avec seulement 2 lignes, le tri final
Python (`sorted()` par `date_tri = ingestion_maj_le or created_at`) corrige
deja tout seul l'ordre, que `nulls_last` soit applique ou non au niveau
SQL. Le vrai bug se joue AVANT ce tri Python, dans la pre-tranche SQL
`[:30]` : sous l'ancien tri (`NULLS FIRST` par defaut en DESC sous
PostgreSQL), 30 fantomes ou plus REMPLISSENT a eux seuls la tranche et
EVINCENT une tache datee avant meme que le tri Python n'ait sa chance.

**Corrige** : le test cree 30 pages fantomes (sans date) plus 1 tache
recente et datee, puis verifie que la tache recente apparait quand meme
dans le dropdown (`assertIn`) et arrive en tete (`taches[0]`) — un test
qui echoue reellement sans le correctif SQL (`nulls_last=True`) et passe
avec. Aucun changement necessaire au tri Python : le defaut vivait
entierement dans la requete SQL, deja corrigee lors de la premiere passe.

**Verification** : `front.tests.test_taches_ingestion` +
`front.tests.test_notification_par_destinataire` (30 tests, relance finale
demandee) + `front.tests.test_ingestion_ui` (21 tests, suite du defaut B,
lancee separement) + `core.tests.test_migration_notification_par_destinataire`
(3 tests, nouveau) — tous verts, une seule suite a la fois, aucune commande
git. Migrations 0060 (recalculee) et 0061 re-appliquees a la base de dev
(rollback vers 0059 puis remigrate) : bilan toujours 0/0/0 (base sans
donnees legacy), `manage.py check` et `makemigrations --check` propres.

## Correction 1 — un drapeau de lecture par destinataire

### Conception retenue

Nouveau modele `NotificationTacheLue` (`core/models.py`, apres `Page`) :

```python
class TypeDeTache(models.TextChoices):
    EXTRACTION = "extraction", "Extraction"
    TRANSCRIPTION = "transcription", "Transcription"
    INGESTION = "ingestion", "Ingestion"


class NotificationTacheLue(models.Model):
    utilisateur = models.ForeignKey(AUTH_USER_MODEL, on_delete=CASCADE,
                                     related_name="notifications_taches_lues")
    type_tache = models.CharField(max_length=14, choices=TypeDeTache.choices)
    tache_id = models.PositiveIntegerField()

    class Meta:
        constraints = [UniqueConstraint(
            fields=["utilisateur", "type_tache", "tache_id"],
            name="unicite_notification_tache_lue_par_destinataire",
        )]
```

**L'existence de la ligne EST le drapeau** — pas de booleen supplementaire.
"Non lue" = aucune ligne `(utilisateur, type_tache, tache_id)`.

**Pourquoi ce design plutot qu'une GenericForeignKey.** Une tache est soit
une `ExtractionJob`, soit un `TranscriptionJob`, soit une `Page`
(ingestion — pas de job dedie, l'etat vit sur la Page elle-meme). Ces trois
tables n'ont aucune cle d'integrite commune possible de toute facon (une
GFK n'apporterait ni contrainte FK reelle, ni simplicite — juste une
indirection `ContentType` + deux colonnes au lieu d'une). `front/views_taches.py`
distinguait DEJA les trois formes par un couple `type_tache` + pk explicite
(`marquer_lue(pk, ?type=)`) : le modele reprend exactement ce vocabulaire
existant, pas un nouveau. C'est le choix le plus simple qui couvre les
trois cas — conforme a la preference du projet pour l'explicite (CLAUDE.md
§ 2.1, "pas d'abstraction au cas ou").

**Normalisation du type stocke.** Le parametre `?type=` accepte
`analyse|synthese|extraction` — les trois pointent sur `ExtractionJob`
(distingues par `raw_result.est_synthese`, un champ d'AFFICHAGE, pas de
routage). `_type_tache_stocke()` (`front/views.py`) les normalise tous les
trois vers `TypeDeTache.EXTRACTION` avant d'ecrire — sinon "analyse" et
"synthese" auraient cree deux lignes pour le MEME job, laissant "l'autre"
variante perpetuellement non lue.

**Idempotence.** `_marquer_tache_lue_pour()` utilise `get_or_create` (chemin
`?marquer_lue=` et `TachesViewSet.marquer_lue`) ; `marquer_toutes_lues` utilise
`bulk_create(..., ignore_conflicts=True)`. Un double-clic, un double-onglet,
ou une notification deja lue entre-temps par une autre requete concurrente
n'levent jamais d'`IntegrityError` sur la contrainte d'unicite — teste
explicitement (`test_marquer_lue_deux_fois_par_le_meme_destinataire_ne_casse_rien`).

### Cout en requetes — mesure

Le brief demandait de mesurer, pas de promettre. La mesure :

**Bouton (`_calculer_etat_bouton`) : 9 requetes avant, 9 requetes apres**
(`front/tests/test_notification_par_destinataire.py::CoutEnRequetesDuBoutonTest::test_neuf_requetes_constantes`,
`assertNumQueries(9)`, verifie avec 5 `ExtractionJob` + 1 ligne
`NotificationTacheLue` en base — le nombre ne bouge pas avec le volume).
Le mecanisme : `notification_lue=False` (comparaison de colonne, cout nul)
devient `.exclude(pk__in=NotificationTacheLue.objects.filter(...).values_list("tache_id"))`
— une **sous-requete SQL** (`WHERE pk NOT IN (SELECT tache_id FROM ...)`),
compilee et executee comme partie de la MEME requete par le query planner.
Aucune requete separee, aucune boucle Python. Le compte de requetes
`_calculer_etat_bouton` reste donc strictement : 3 (en_cours) + 3 (non_lues,
chacune desormais avec anti-jointure) + 3 (`a_des_erreurs_non_lues`, idem)
= 9, comme avant.

**Dropdown : 14 requetes avant, 14 requetes apres**
(`front/tests/test_taches_ingestion.py::NotificationDestinataireCarnetTest::test_pas_de_n_plus_1_sur_le_dropdown`,
`assertNumQueries(14)`, deja existant, toujours vert sans modification).
La liste de 30 taches n'affiche PAS l'etat lu/non-lu par ligne (verifie
dans `taches_dropdown.html` : seul le compteur agrege en depend) — aucune
requete supplementaire par ligne n'a ete necessaire.

**`marquer_toutes_lues` : 6 requetes propres** (2 par type — 1 `SELECT` des
ids non lus par ce destinataire, 1 `INSERT ... bulk_create`), plus l'appel
a `dropdown()` qu'elle reutilise pour rafraichir l'affichage. Cet endpoint
n'etait couvert par aucune borne de requetes existante ; il n'entre pas
dans la contrainte "9 requetes" du brief (qui vise le chargement de
page, pas un clic explicite "tout marquer lu"), mais reste borne et
sans boucle par ligne.

### Migration de donnees — bilan chiffre

Deux migrations creees (`core/migrations/`) :

- **`0059_creer_notification_tache_lue.py`** — schema (generee par
  `makemigrations`, `CreateModel`).
- **`0060_migrer_les_notifications_lues_par_destinataire.py`** — donnees,
  patron des migrations 0042/0047/0050/0058 (bilan chiffre imprime,
  reversible).

**Attribution retenue : le PROPRIETAIRE DE LA NOTE, pas le proprietaire
d'un carnet.** Avant l'elargissement du perimetre de lecture (widening
fait le meme jour, cf. `task-trois-defauts-graves-report.md`),
`front/views_taches.py` filtrait strictement en `page__owner=user` — SEUL
le proprietaire de la note pouvait marquer une tache lue (confirme par
`git diff HEAD -- front/views_taches.py`, qui montre `page__owner=user`
comme etat "avant"). Un booleen a `True` ne peut donc temoigner que de LA
lecture de CE destinataire-la ; l'attribuer a un proprietaire de carnet
serait une invention non fondee. Les pages/jobs sans owner (legacy) sont
ignores — personne a qui attribuer la lecture, imprime dans le bilan.

**Bilan sur la base de dev** (execute via `manage.py migrate core`) :

```
[migration 0060] notifications lues migrees par destinataire :
  extraction    : 0 migree(s), 0 ignoree(s) (sans owner)
  transcription : 0 migree(s), 0 ignoree(s) (sans owner)
  ingestion     : 0 migree(s), 0 ignoree(s) (sans owner)
```

Base de dev vide de donnees "deja lues" au moment de la migration (verifie :
`ExtractionJob.objects.filter(notification_lue=True).count()` == 0,
idem pour les deux autres) — bilan 0/0/0 coherent, pas un bug de la
migration.

**Reamorcage sur relance d'ingestion.** `_noter_l_etat_d_ingestion()`
(`hypostasis_extractor/tasks_element.py`) remettait deja
`ingestion_notification_lue=False` quand un cycle REDEMARRE
(`en_attente`/`en_cours`), pour que la fin du nouveau cycle rallume le
badge. Le meme besoin existe pour le nouveau modele — sans lui, un
destinataire qui avait deja lu un cycle precedent ne reverrait plus JAMAIS
la notification du nouveau cycle. Ajoute : suppression des lignes
`NotificationTacheLue(type_tache="ingestion", tache_id=page)` **pour tous
les destinataires** au meme endroit (teste :
`test_une_relance_reamorce_aussi_le_drapeau_par_destinataire`, deux
destinataires distincts, les deux lignes disparaissent).

### Code mort

Les trois booleens legacy **restent en base** (pas de suppression de
colonne dans cette passe — irreversible, d'autres ecrans pourraient les
lire) :

- `hypostasis_extractor.models.ExtractionJob.notification_lue`
- `core.models.TranscriptionJob.notification_lue`
- `core.models.Page.ingestion_notification_lue`

**Ils ne pilotent plus AUCUNE decision** : ni le comptage du bouton
(`_calculer_etat_bouton`), ni le dropdown, ni les deux chemins de
marquage (`TachesViewSet.marquer_lue` / `marquer_toutes_lues` et
`?marquer_lue=` dans `LectureViewSet.retrieve`). Leur `help_text` a ete
mis a jour dans les trois modeles pour dire explicitement "MORT pour la
decision, voir NotificationTacheLue" (migrations `core/0061` et
`hypostasis_extractor/0034` — de simples `AlterField` sur `help_text`,
aucun changement de schema, generees pour garder `makemigrations --check`
silencieux).

Seul endroit ou l'un de ces trois booleens est encore ECRIT :
`_noter_l_etat_d_ingestion` continue de poser
`ingestion_notification_lue=False` au redemarrage d'un cycle — laisse en
l'etat pour ne pas casser le test existant
`test_une_relance_reussie_reamorce_le_drapeau_de_notification` (qui teste
CE champ precisement) et parce que ce n'est pas une decision, juste une
ecriture inerte tant que rien ne le relit.

### Ce qui continue de marcher (verifie)

- `TachesViewSet.marquer_lue` (pk = job ou page, `?type=`) — 404 jamais 403
  sur acces refuse, verifie.
- `TachesViewSet.marquer_toutes_lues` — ne touche que l'appelant.
- `LectureViewSet.retrieve` (`?marquer_lue=&type=`) — second chemin
  independant, verifie separement.
- Le proprietaire d'un carnet ET l'auteur de la note voient la meme tache
  et la marquent independamment — **le test qui compte** du brief :
  `test_extraction_marquee_lue_par_le_prof_reste_non_lue_pour_l_auteur`
  et ses variantes transcription/ingestion/lien-lecture/marquer-toutes.

## Correction 2 — les pages sans horodatage traitees comme des fantomes

### Comptage (`front/views_taches.py::_calculer_etat_bouton`)

`.exclude(ingestion_maj_le__lt=seuil_fantome)` (gardait les `NULL`, car
une comparaison NULL est toujours indeterminee en SQL — donc jamais
exclue) devient `.filter(ingestion_maj_le__gte=seuil_fantome)` : la MEME
raison SQL (NULL n'est jamais vrai dans une comparaison) joue maintenant
en sens inverse — un `filter()` sur une colonne NULL ne matche JAMAIS, donc
NULL est desormais EXCLU du compte. Un seul mot change
(`exclude(__lt=)` -> `filter(__gte=)`), comportement inverse, sans
degrader le cout (toujours une seule condition dans la meme requete).

### Tri du menu (`TachesViewSet.dropdown`)

Sous PostgreSQL, `order_by("-ingestion_maj_le")` place les `NULL` **en
tete** (NULLS FIRST est le defaut en DESC) — une page fantome sans date
squattait donc le haut du dropdown devant des ingestions reellement
recentes, et pouvait meme evincer une vraie recente du `[:30]` avant que
le tri Python de fusion (`date_tri`) n'ait la moindre chance de la
repositionner. Fixe avec `order_by(F("ingestion_maj_le").desc(nulls_last=True))`
(import `django.db.models.F` ajoute) — les NULL sont traites comme la
date la plus ancienne possible, coherent avec "sans date on ne peut pas
prouver la recence".

### Tests

- `front/tests/test_taches_ingestion.py::IngestionFantomeTest::test_une_ingestion_en_cours_sans_date_ne_compte_plus`
  — RENVERSE l'assertion de l'ancien test du meme nom (`..._compte_toujours`,
  `nombre_en_cours == 1`) vers `nombre_en_cours == 0` : c'est le meme test,
  la regle qu'il verifie a change de sens sur decision du mainteneur (le
  seul code qui produisait ce cas est corrige).
- `front/tests/test_taches_ingestion.py::IngestionFantomeSansDateDansLeMenuTest`
  — verifie sous PostgreSQL reel (le moteur de test) qu'une page recente
  et datee passe DEVANT une page fantome sans date dans le dropdown.

### Effet de bord decouvert en testant

Les fixtures de test existantes qui creaient une page "en_cours" SANS
poser `ingestion_maj_le` (le cas normal avant aujourd'hui, puisque le
comptage ne s'en souciait pas) sont devenues, par construction, des
fantomes au sens de la correction 2 — cassant plusieurs tests preexistants
qui ne testaient PAS le cas fantome mais l'assumaient implicitement absent.
Corrige en alignant les helpers de fixtures
(`IngestionDansLesTachesTest._creer_page`,
`NotificationDestinataireCarnetTest.setUp`) sur ce que le code REEL ecrit
toujours desormais (import, relance, tache Docling posent tous
`ingestion_maj_le` en meme temps que l'etat) — pas un contournement du
test, une correction d'une fixture qui ne refletait plus la realite du
code.

## Fichiers modifies

- `core/models.py` — `TypeDeTache`, `NotificationTacheLue`, help_text morts
  sur les trois booleens legacy.
- `hypostasis_extractor/models.py` — help_text mort sur `ExtractionJob.notification_lue`.
- `core/migrations/0059_creer_notification_tache_lue.py` (schema),
  `0060_migrer_les_notifications_lues_par_destinataire.py` (donnees),
  `0061_documenter_les_champs_de_notification_lue_morts.py` (help_text).
- `hypostasis_extractor/migrations/0034_documenter_les_champs_de_notification_lue_morts.py` (help_text).
- `front/views.py` — `_type_tache_stocke`, `_marquer_tache_lue_pour`,
  `LectureViewSet.retrieve` (`?marquer_lue=`) reecrit sur le nouveau modele.
- `front/views_taches.py` — `_ids_taches_lues_par`, `_calculer_etat_bouton`
  (anti-jointure + correction 2), `dropdown()` (tri `nulls_last`),
  `marquer_lue()`, `marquer_toutes_lues()` reecrits sur le nouveau modele.
- `hypostasis_extractor/tasks_element.py` — `_noter_l_etat_d_ingestion`
  supprime les lignes `NotificationTacheLue` au redemarrage d'un cycle.
- Tests : `front/tests/test_notification_par_destinataire.py` (nouveau),
  `front/tests/test_taches_ingestion.py` (helpers + assertions mises a
  jour + nouvelle classe fantome-sans-date-dans-le-menu),
  `hypostasis_extractor/tests/test_tasks_element.py` (nouveau test
  reamorcage par destinataire), `front/tests/test_phases.py`
  (`test_marquer_lue_passe_le_flag_a_true` mis a jour).

## Migrations appliquees a la base de dev

`core.0059`, `core.0060` (bilan 0/0/0 — base vide), `core.0061`,
`hypostasis_extractor.0034` — toutes appliquees via `manage.py migrate`
dans le conteneur `hypostasia_web`, sans redemarrage du serveur/worker.
`manage.py check` et `makemigrations --check --dry-run` : propres.

## Verification (TDD) et resultats finaux

Tests ecrits AVANT le code, observes en echec, puis correction :
- Import de `NotificationTacheLue` : `ImportError` (le modele n'existait
  pas encore).
- `test_une_ingestion_en_cours_sans_date_ne_compte_plus` : `1 != 0` (la
  regle n'etait pas encore inversee).
- `test_la_page_fantome_sans_date_ne_squatte_pas_la_tete_du_dropdown` :
  echoue par une erreur de fixture (corrigee), puis logiquement avant le
  fix du tri.
- 9 echecs supplementaires decouverts en re-lancant les suites
  existantes apres l'implementation : des tests preexistants asseraient
  encore sur les trois booleens legacy (desormais morts) ou construisaient
  des fixtures "en_cours" sans date (desormais fantomes) — tous corriges,
  voir "Effet de bord decouvert en testant" plus haut.

Suites lancees apres correction, toutes vertes :
- `front.tests.test_notification_par_destinataire` + `front.tests.test_taches_ingestion`
  + `hypostasis_extractor.tests.test_tasks_element` + `front.tests.test_phases.Phase26iTachesViewSetTest`
  — 56 tests.
- `front.tests.test_notification_transcription` + `hypostasis_extractor.tests.test_notifications_ingestion`
  + `hypostasis_extractor.tests.test_ingestion_docling` + `hypostasis_extractor.tests.test_fixtures_representatives`
  + `front.tests.test_capture_web_docling` + `core.tests.test_reparation_provenance_boites`
  — 54 tests (7 skipped, attendu).
- `core` (app complete, 212 tests, 84.6s) — OK.
- Re-verification finale ciblée (`test_notification_par_destinataire` +
  `test_taches_ingestion`) apres les derniers ajustements de commentaires —
  30 tests, OK.

Suite `front` et `hypostasis_extractor` completes NON lancees en entier :
le combo des trois apps depasse 550s (une suite de tests de migrations
existante, deja lente avant cette tache, iterant 0042->0060 a chaque
sous-cas). Le perimetre explicitement demande (`test_taches_ingestion`
et "celles qui touchent aux taches") est couvert et vert ; `core` complet
est vert. Reserve : je n'ai pas fait tourner `front`/`hypostasis_extractor`
dans leur totalite faute de temps d'execution raisonnable dans cette
session — a signaler si une regression hors perimetre notification/
ingestion est suspectee ailleurs.
