## Tâche 8 : afficher les ingestions dans le bouton et le dropdown

**Fichiers :**
- Modifier : `core/models.py` (un champ sur `Page`)
- Créer : une migration de schéma **et** une migration de données
- Modifier : `front/views_taches.py`
- Modifier : `front/templates/front/includes/taches_dropdown.html`
- Test : `front/tests/test_taches_ingestion.py` (créer)

**Interfaces :**
- Consomme : `Page.ingestion_etat`, `Page.ingestion_detail`,
  `Page.ingestion_maj_le`, et le `tache_type="ingestion"` de la tâche 7.
- Produit : `Page.ingestion_notification_lue`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""
Les ingestions apparaissent-elles dans le bouton et le dropdown ?
/ Do ingestions show up in the tasks button and dropdown?

LOCALISATION : front/tests/test_taches_ingestion.py
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import EtatIngestion, Page

User = get_user_model()


class IngestionDansLesTachesTest(TestCase):

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="proprio", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def _creer_page(self, etat, lue=False):
        return Page.objects.create(
            title="Un document", source_type="file",
            original_filename="doc.pdf",
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=self.proprietaire,
            ingestion_etat=etat, ingestion_notification_lue=lue,
        )

    def test_une_ingestion_en_cours_compte_dans_le_bouton(self):
        self._creer_page(EtatIngestion.EN_COURS)

        reponse = self.client.get("/taches/bouton/")

        self.assertContains(reponse, "1")
        self.assertEqual(reponse.context["nombre_en_cours"], 1)

    def test_une_ingestion_reussie_non_lue_compte_comme_non_lue(self):
        self._creer_page(EtatIngestion.REUSSIE, lue=False)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_non_lues"], 1)

    def test_une_ingestion_deja_lue_ne_compte_plus(self):
        self._creer_page(EtatIngestion.REUSSIE, lue=True)

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_non_lues"], 0)

    def test_une_page_sans_ingestion_ne_compte_jamais(self):
        # Une page nee avant le moteur ELEMENT, ou un .txt : son
        # ingestion_etat est vide, elle n'est pas une tache.
        # / A page that never requested an ingestion is not a task.
        self._creer_page("")

        reponse = self.client.get("/taches/bouton/")

        self.assertEqual(reponse.context["nombre_non_lues"], 0)
        self.assertEqual(reponse.context["nombre_en_cours"], 0)

    def test_l_ingestion_apparait_dans_le_dropdown(self):
        page = self._creer_page(EtatIngestion.REUSSIE)

        reponse = self.client.get("/taches/dropdown/")

        libelles = [t.libelle_de_tache for t in reponse.context["taches"]]
        self.assertIn("Découpage", libelles)
        self.assertEqual(reponse.context["taches"][0].page_resultat_id, page.pk)

    def test_marquer_lue_une_ingestion(self):
        page = self._creer_page(EtatIngestion.REUSSIE, lue=False)

        self.client.post(
            f"/taches/{page.pk}/marquer-lue/", {"type": "ingestion"},
        )

        page.refresh_from_db()
        self.assertTrue(page.ingestion_notification_lue)

    def test_on_ne_marque_pas_lue_la_page_d_un_autre(self):
        # Doctrine du projet : 404, jamais 403.
        # / Project doctrine: 404, never 403.
        autre = User.objects.create_user(username="autre")
        page_d_autrui = Page.objects.create(
            title="Pas la mienne", source_type="file",
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=autre,
            ingestion_etat=EtatIngestion.REUSSIE,
        )

        reponse = self.client.post(
            f"/taches/{page_d_autrui.pk}/marquer-lue/", {"type": "ingestion"},
        )

        self.assertEqual(reponse.status_code, 404)
        page_d_autrui.refresh_from_db()
        self.assertFalse(page_d_autrui.ingestion_notification_lue)
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

Attendu : `TypeError` sur `ingestion_notification_lue`, champ inexistant.

- [ ] **Étape 3 : ajouter le champ et ses deux migrations**

Dans `core/models.py`, sur `Page`, à côté de `ingestion_maj_le` :

```python
    ingestion_notification_lue = models.BooleanField(
        default=False,
        help_text="La fin du decoupage en elements a-t-elle ete vue ? "
                  "Symetrique du notification_lue des jobs d'analyse et "
                  "de transcription (addendum du 11 aout 2026).",
    )
```

Puis :

```bash
docker exec -w /app hypostasia_web uv run python manage.py makemigrations core
```

**Et une migration de données, obligatoire.** Le champ vaut `False` par
défaut : sans elle, **toutes** les pages déjà ingérées apparaîtraient d'un
coup comme des notifications non lues. Le dépôt a déjà ce patron — voir
`core/migrations/0042`, `0047` et `0050`, qui estampillent l'existant et
impriment leur bilan. Écrire une migration qui pose
`ingestion_notification_lue=True` sur toutes les pages existantes dont
`ingestion_etat` n'est pas vide, et qui écrit combien de pages elle a
touchées.

- [ ] **Étape 4 : compter les ingestions dans le bouton**

Dans `_calculer_etat_bouton` (`front/views_taches.py:19`), ajouter aux
trois comptages existants — en cours, non lues, erreurs non lues — leur
équivalent sur `Page` :

```python
    # Les ingestions n'ont pas de job : leur etat vit sur la Page.
    # `ingestion_etat` vide = aucune ingestion demandee (un .txt, une page
    # nee avant le moteur ELEMENT) : ce n'est pas une tache.
    # / Ingestions have no job; an empty state means no task at all.
    nombre_ingestions_en_cours = Page.objects.filter(
        owner=user,
        ingestion_etat__in=[EtatIngestion.EN_ATTENTE, EtatIngestion.EN_COURS],
    ).count()
    nombre_ingestions_non_lues = Page.objects.filter(
        owner=user,
        ingestion_etat__in=[EtatIngestion.REUSSIE, EtatIngestion.ECHOUEE],
        ingestion_notification_lue=False,
    ).count()
```

et les ajouter aux totaux. Pour les erreurs non lues, ajouter au `or`
existant un `Page.objects.filter(owner=user,
ingestion_etat=EtatIngestion.ECHOUEE,
ingestion_notification_lue=False).exists()`.

- [ ] **Étape 5 : lister les ingestions dans le dropdown**

Dans `dropdown()`, les objets passés au template portent quatre attributs
annotés : `type_tache`, `page_resultat_id`, `libelle_de_tache`, plus
`created_at` et `status` lus directement. Une `Page` a bien `created_at`,
mais son `status` est celui de la page, pas de l'ingestion — il faut donc
annoter explicitement :

```python
    # Les ingestions recentes de l'utilisateur. On annote les memes
    # attributs que les jobs pour que le template ne connaisse qu'une
    # seule forme. `status` est traduit depuis ingestion_etat : le
    # `status` propre de la Page parle d'autre chose.
    # / Same annotations as jobs, so the template knows one shape only.
    ingestions_recentes = list(Page.objects.filter(
        owner=request.user,
    ).exclude(ingestion_etat="").order_by("-ingestion_maj_le")[:30])

    for page_ingeree in ingestions_recentes:
        page_ingeree.type_tache = "ingestion"
        page_ingeree.page_resultat_id = page_ingeree.pk
        page_ingeree.libelle_de_tache = "Découpage"
        page_ingeree.notification_lue = page_ingeree.ingestion_notification_lue
        if page_ingeree.ingestion_etat == EtatIngestion.ECHOUEE:
            page_ingeree.status = "error"
        elif page_ingeree.ingestion_etat == EtatIngestion.REUSSIE:
            page_ingeree.status = "completed"
        else:
            page_ingeree.status = "processing"
```

**Attention au tri.** La fusion existante trie sur `created_at`. Pour une
ingestion, c'est la date de création de la **note**, qui peut être bien
antérieure au découpage. Trier les ingestions sur `ingestion_maj_le`, et
donner à chaque objet fusionné une clé de tri commune plutôt que de mélanger
deux sens du temps dans le même `sorted()`. Écrire ce choix en commentaire :
c'est le genre de détail qu'on « corrige » à tort six mois plus tard.

- [ ] **Étape 6 : traiter le cas « ingestion » dans `marquer_lue`**

`marquer_lue` (`front/views_taches.py:174`) aiguille aujourd'hui sur deux
cas. Ajouter le troisième : `tache_type == "ingestion"` →
`get_object_or_404(Page, pk=pk, owner=request.user)` puis
`ingestion_notification_lue = True`. Le `get_object_or_404` filtré sur
`owner` donne bien un **404** pour la page d'autrui, conformément à la
doctrine du projet — jamais un 403.

Faire de même dans `marquer_toutes_lues` (`:197`).

- [ ] **Étape 7 : le template**

Dans `front/templates/front/includes/taches_dropdown.html`, vérifier ce que
le gabarit fait de `type_tache` : s'il choisit une icône ou une couleur par
type, ajouter le cas `ingestion`. **Lire le template avant d'écrire** — s'il
n'utilise que `libelle_de_tache` et `status`, il n'y a rien à changer, et
c'est le résultat le plus probable.

Aucun fichier JS ni CSS n'est touché : **ni `collectstatic`, ni bump `?v=`**.
Un template modifié demande en revanche, si `DEBUG=False` :
`docker exec hypostasia_web supervisorctl restart daphne gunicorn`.

- [ ] **Étape 8 : lancer les tests**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_taches_ingestion --noinput \
    --settings=hypostasia.settings_test_opus
```

Puis, séparément, la suite des tâches existantes pour vérifier qu'aucun
compteur n'a changé de sens.

- [ ] **Étape 9 : vérifier au navigateur**

Importer un document réel, et regarder le bouton passer en « en cours »
puis en « terminé » **sans rafraîchir la page**. C'est la seule preuve qui
compte : les tests vérifient les comptages, pas le fait que le message
traverse vraiment le WebSocket.

- [ ] **Étape 10 : point d'arrêt**
# Addendum du 11 août 2026 — brancher l'ingestion aux notifications

> Demande du propriétaire du dépôt, en cours de session. Ne fait pas partie
> de la spec `2026-08-11-fixtures-sample-design.md` : ces deux tâches
> touchent l'application, pas les fixtures.

## Le constat

Le moteur de notification existe et fonctionne :

```
tâche Celery → notifier_tache_terminee(user_pk, tache_id, tache_type, status)
             → group_send "user_<pk>" → NotificationConsumer.tache_terminee
             → JS : refetch /taches/bouton/
```

**Trois tâches n'y sont pas branchées**, toutes dans
`hypostasis_extractor/tasks_element.py` :

| Tâche | Ligne | Notifie ? |
|---|---|---|
| `ingerer_un_fichier_avec_docling` | 256 | non |
| `ingerer_une_capture_web_avec_docling` | 361 | non |
| `ingerer_une_transcription_diarisee_en_elements` | 427 | non |

Conséquence : importer un PDF déclenche 80 à 164 s de travail (mesure du
11 août) sans que rien ne prévienne l'utilisateur à la fin.

**Second défaut, découvert au même endroit.**
`_destinataires_de_notification(page)` (`front/tasks.py:50`) rend « l'owner
plus les propriétaires des carnets contenant la note ». Son commentaire dit
qu'elle existe parce qu'« avant la phase D, le second carnet d'une note
n'apprenait jamais qu'une synthèse avait tourné ». Or seules la **synthèse**
(`front/tasks.py:1383`, `1414`) et l'**article** (`1615`) l'utilisent :
l'**analyse** (`tasks_element.py:213`) et la **transcription**
(`front/tasks.py:704`, `735`) notifient encore `page.owner` seul. La
correction de la phase D n'a été appliquée qu'à moitié.

## Décision

Pas de nouveau modèle. `Page.ingestion_etat` porte déjà l'état
(`en_attente` / `en_cours` / `reussie` / `echouee`) et fait foi ; un modèle
`JobIngestion` parallèle dupliquerait la vérité et finirait par en diverger.
Il manque seulement un marqueur « lu », symétrique du `notification_lue`
que portent `ExtractionJob` et `TranscriptionJob`.

Le JS n'inspecte pas `tache_type` — il refetch le bouton à chaque message.
Aucun fichier statique à toucher : **ni `collectstatic`, ni bump de `?v=`**.

---

## Tâche 7 : notifier depuis les trois tâches d'ingestion

---

# COMPLÉMENT AU BRIEF — deux pièges relevés dans le code (11 août, après rédaction du plan)

## Piège 1 : le template utilise `tache.page.pk`

`front/templates/front/includes/taches_dropdown.html` ligne 75, dans la
branche **erreur**, écrit `{{ tache.page.pk }}` — alors que la branche
succès utilise `{{ tache.page_resultat_id }}`.

Pour un `ExtractionJob` ou un `TranscriptionJob`, `.page` est la clé
étrangère vers la note. **Pour une `Page`, `page.page` n'existe pas** :
le gabarit rendrait une chaîne vide et produirait un lien `/lire//`.

Il faut donc, soit annoter `page_ingeree.page = page_ingeree` dans la vue
(laid mais local), soit rendre le gabarit homogène en utilisant
`page_resultat_id` dans les deux branches. **Regarde le gabarit en entier
avant de choisir**, et dis dans ton rapport lequel tu as retenu et
pourquoi. Une ingestion en échec est précisément le cas où l'utilisateur
a le plus besoin que le lien marche.

## Piège 2 : il y a DEUX chemins de marquage « lu », pas un

Le plan ne mentionne que `TachesViewSet.marquer_lue`
(`front/views_taches.py:174`). Mais le gabarit du dropdown n'utilise pas
cette route : ses liens pointent vers
`/lire/<page_resultat_id>/?marquer_lue=<pk>&type=<type_tache>`, et c'est
`front/views.py:1120-1132` qui traite ce paramètre.

Ce code teste `if marquer_lue and type_tache in ("analyse", "synthese",
"extraction", "transcription")` — une ingestion n'y figure pas, donc
cliquer sur la notification ne la marquerait jamais comme lue, et le
badge resterait allumé pour toujours.

**Les deux chemins doivent traiter le cas `"ingestion"`** :
- `front/views.py:1122` — ajouter `"ingestion"` à la liste et la branche
  correspondante, qui pose `ingestion_notification_lue=True` sur la Page,
  filtrée sur `owner=request.user` ;
- `front/views_taches.py:174` (`marquer_lue`) et `:197`
  (`marquer_toutes_lues`) — comme le plan le décrit.

Écris un test pour **chacun** des deux chemins : ils sont indépendants et
il serait facile d'en corriger un seul.
