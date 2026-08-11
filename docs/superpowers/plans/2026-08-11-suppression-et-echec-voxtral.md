# Suppression d'une note, média orphelin, échec Voxtral — plan

> **Pour les agents :** SOUS-SKILL REQUIS — `superpowers:subagent-driven-development`,
> tâche par tâche. Les étapes utilisent des cases à cocher (`- [ ]`).

**But :** rendre la suppression d'une note conforme à la règle décidée le
11 août 2026, faire disparaître le média avec elle, et traiter proprement
l'échec d'une transcription Voxtral.

**Architecture :** trois tâches indépendantes — un signal de modèle, une
règle de vue, un changement de cardinalité — plus une passe d'interface qui
conditionne la confirmation.

**Pile :** Django 5 · DRF · HTMX · SweetAlert · Celery · PostgreSQL · `uv`.

---

## Contraintes globales

Elles valent pour **toutes** les tâches.

- **Aucune opération git.** Ni `add`, ni `commit`, ni `checkout --`, ni
  `stash`, ni `restore`, ni `clean`, ni `reset`. Chaque tâche se termine
  par un point d'arrêt.
- **Aucun `ruff format` ni `ruff check --fix`** sur un fichier existant.
- **Une seule suite de tests à la fois.** Jamais `--parallel`. Et **cibler**
  la suite : `manage.py test` sans argument fait tourner tout le projet et
  dépasse les dix minutes.
- **Commentaires bilingues** français puis anglais sur chaque bloc de logique.
- **Noms de variables verbeux** en français.
- **Doctrine du projet : 404, jamais 403.**
- **Ne jamais inventer un chiffre.** Un compte annoncé est un compte mesuré.
- Un serveur Django et un worker Celery tournent dans des panes byobu sur la
  base de développement. **Toute migration doit être appliquée** à cette base
  après création — sinon le serveur tombe en `ProgrammingError` (c'est arrivé
  le 11 août : le code référençait une colonne non migrée).

### Commandes de référence

```bash
docker exec -w /app hypostasia_web uv run python manage.py test <cible> \
    --noinput --settings=hypostasia.settings_test_opus

docker exec -w /app hypostasia_web uv run python manage.py migrate core --noinput
```

`uv run` est obligatoire : `python manage.py` seul échoue dans ce conteneur.

---

## La règle de suppression décidée

| Qui | Note dans plusieurs carnets | Note dans un seul carnet |
|---|---|---|
| **Propriétaire de la note** | supprimer, avec confirmation | supprimer, avec confirmation si destructif |
| **Propriétaire d'un carnet seulement** | **retirer du carnet** | **retirer du carnet** — la note devient orpheline |
| Ni l'un ni l'autre | refus | refus |

Le principe : **qui ne possède pas la note ne la détruit jamais.** Une note
orpheline n'est pas perdue — elle reste en base, sans carnet, visible de son
auteur. Le projet a déjà cette notion : `appartenances_dossiers` vide plus un
`owner`.

**La confirmation** n'apparaît que lorsque le geste est destructif *et* non
évident : une note présente dans plusieurs carnets, ou portant des
commentaires ou des ancres. Un simple retrait de carnet est réversible et ne
demande rien.

---

## Faits établis — ne pas les redécouvrir

| Fait | Où |
|---|---|
| `_est_proprietaire_page` = propriétaire de la note **OU** d'un carnet la contenant | `front/views.py:365` — décision de gouvernance documentée (spec § 5.2, correction n°5) : sans elle, le prof perd la modération sur les captures de ses élèves |
| `retirer_une_note_d_un_carnet(page, dossier)` existe et **ne supprime jamais la note** | `core/services/corpus.py:128` — réaffecte la FK ou la met à NULL |
| `PageViewSet.supprimer` ne reçoit **que** le pk de la note, aucun carnet | `front/views.py:3911` |
| Le geste vient d'un menu contextuel **en JavaScript statique** | `front/static/front/js/arbre_context_menu.js:313` |
| La confirmation SweetAlert existe déjà, mais **systématique** | même fichier, lignes 314-322 |
| `TranscriptionJob.page` est en **CASCADE** | `core/models.py:1126` |
| Le gabarit du menu des tâches lit `tache.page.title` et `tache.page.pk` | `front/templates/front/includes/taches_dropdown.html:60`, `:75` |
| `transcrire_audio_task` attrape toute exception, pose `PageStatus.ERROR` et `job.error_message` | `front/tasks.py:712-732` |
| Un signal `pre_delete` existe déjà sur `Dossier`, avec sa doctrine écrite | `core/signals.py:119` — « l'admin Django, une cascade ou un `delete()` en shell contournent la vue » |

---

## Tâche 1 : le média disparaît avec sa note

**Fichiers :**
- Modifier : `core/signals.py`
- Test : `core/tests/test_suppression_du_media.py` (créer)

**Interfaces :**
- Produit : un récepteur `post_delete` sur `Page` nommé
  `supprimer_le_media_apres_la_note`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""
Le fichier source suit-il sa note dans la tombe ?
/ Does the source file follow its note into the grave?

LOCALISATION : core/tests/test_suppression_du_media.py
"""

import os

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase

from core.models import Page

User = get_user_model()


class SuppressionDuMediaTest(TestCase):

    def setUp(self):
        self.proprietaire = User.objects.create_user(username="proprio")

    def _page_avec_media(self, nom="doc.txt", contenu=b"du contenu"):
        return Page.objects.create(
            title="Une note", source_type="file", original_filename=nom,
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=self.proprietaire,
            source_file=ContentFile(contenu, name=nom),
        )

    def test_supprimer_la_note_supprime_le_fichier(self):
        page = self._page_avec_media()
        chemin_du_media = page.source_file.path
        self.assertTrue(os.path.exists(chemin_du_media))

        page.delete()

        self.assertFalse(os.path.exists(chemin_du_media))

    def test_une_note_sans_media_se_supprime_sans_erreur(self):
        page = Page.objects.create(
            title="Sans fichier", source_type="web",
            html_original="<p>x</p>", html_readability="<p>x</p>",
            text_readability="x", content_hash="", owner=self.proprietaire,
        )

        page.delete()

        self.assertFalse(Page.objects.filter(pk=page.pk).exists())

    def test_un_fichier_deja_absent_ne_fait_pas_echouer_la_suppression(self):
        # Le disque et la base peuvent diverger : un media efface a la
        # main ne doit pas empecher de supprimer la note.
        # / Disk and database can diverge; a missing file must not block.
        page = self._page_avec_media()
        os.remove(page.source_file.path)

        page.delete()

        self.assertFalse(Page.objects.filter(pk=page.pk).exists())

    def test_deux_notes_partageant_un_meme_fichier(self):
        # Django renomme les doublons (doc.txt, doc_XXXX.txt), donc deux
        # notes n'ont normalement PAS le meme chemin. On verrouille le
        # cas ou, malgre tout, un chemin serait partage : supprimer la
        # premiere ne doit pas priver la seconde de son fichier.
        # / Locks the shared-path case: the survivor keeps its file.
        premiere = self._page_avec_media()
        seconde = Page.objects.create(
            title="Une autre", source_type="file",
            original_filename="doc.txt",
            html_original="", html_readability="", text_readability="",
            content_hash="", owner=self.proprietaire,
        )
        seconde.source_file.name = premiere.source_file.name
        seconde.save(update_fields=["source_file"])
        chemin_partage = premiere.source_file.path

        premiere.delete()

        self.assertTrue(os.path.exists(chemin_partage))
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    core.tests.test_suppression_du_media --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : le premier test échoue (`assertFalse` sur un fichier toujours là),
le dernier passe déjà. Un échec du premier **et** du dernier signalerait un
signal déjà présent quelque part — s'arrêter et chercher.

- [ ] **Étape 3 : écrire le signal**

Dans `core/signals.py`, sur le modèle du récepteur `pre_delete` existant :

```python
@receiver(
    post_delete,
    sender=Page,
    dispatch_uid="corpus_supprimer_le_media_apres_la_note",
)
def supprimer_le_media_apres_la_note(sender, instance, **kwargs):
    """
    Efface du disque le fichier source d'une note supprimee.
    / Deletes a removed note's source file from disk.

    LOCALISATION : core/signals.py

    POURQUOI UN SIGNAL ET PAS LA VUE

    Meme raison que reaffecter_les_fk_avant_suppression_du_carnet :
    l'admin Django, une cascade et un delete() en shell contournent la
    vue. Un media qui ne part qu'en passant par l'ecran laisserait des
    fichiers orphelins par tous les autres chemins.
    / Admin, cascades and shell deletes bypass the view.

    QUI A LE DROIT DE SUPPRIMER N'EST PAS DECIDE ICI

    Un signal de modele ne connait pas l'utilisateur courant. Le controle
    d'acces vit dans la vue (front/views.py, _est_proprietaire_page) et
    ce signal en herite : si seul un ayant droit peut supprimer la note,
    seul un ayant droit declenche la suppression du fichier.
    / Access control lives in the view; this signal inherits it.

    POST_DELETE, PAS PRE_DELETE

    On efface le fichier une fois la ligne partie. Sur un pre_delete, une
    transaction annulee apres coup laisserait une note sans son fichier —
    l'inverse exact du probleme qu'on corrige.
    / After the row is gone: a rollback would strand a fileless note.
    """
    if not instance.source_file:
        return

    # Un autre enregistrement peut pointer le meme chemin. Django renomme
    # normalement les doublons, mais une copie de fixture ou une reprise
    # de donnees peut les faire coincider : on ne prend pas ce risque.
    # / Another row may point at the same path; do not risk it.
    if Page.objects.filter(source_file=instance.source_file.name).exists():
        return

    try:
        instance.source_file.storage.delete(instance.source_file.name)
    except Exception as erreur_de_suppression:
        # Le disque et la base peuvent diverger. Un fichier deja efface,
        # un stockage distant en panne : la note est supprimee, c'est
        # l'essentiel. On le note et on continue.
        # / Disk and DB can diverge; the row is gone, that is what counts.
        logger.warning(
            "Note %s supprimee, mais son fichier %s n'a pas pu l'etre (%s).",
            instance.pk, instance.source_file.name, erreur_de_suppression,
        )
```

Ajouter `post_delete` à l'import de `django.db.models.signals`, en tête de
fichier, et vérifier qu'un `logger` y est défini — sinon l'ajouter.

- [ ] **Étape 4 : lancer les tests, vérifier qu'ils passent**

- [ ] **Étape 5 : point d'arrêt**

---

## Tâche 2 : retirer du carnet plutôt que détruire

**Fichiers :**
- Modifier : `front/views.py` (`PageViewSet.supprimer`, vers la ligne 3911)
- Modifier : `front/static/front/js/arbre_context_menu.js`
- Modifier : `front/templates/front/includes/arbre_dossiers.html` (transmettre
  le carnet de contexte)
- Test : `front/tests/test_suppression_de_note.py` (créer)

**Interfaces :**
- Consomme : `_est_proprietaire_page`, `retirer_une_note_d_un_carnet`.
- Produit : `PageViewSet.supprimer` accepte un paramètre `dossier_id`
  facultatif, validé par un `serializers.Serializer` DRF — **jamais** un
  Django Form, c'est la convention du dépôt.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""
Supprimer une note, ou seulement la retirer d'un carnet ?
/ Delete a note, or merely remove it from a notebook?

LOCALISATION : front/tests/test_suppression_de_note.py
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page
from core.services.corpus import ranger_une_note_dans_un_carnet

User = get_user_model()


class SuppressionDeNoteTest(TestCase):

    def setUp(self):
        self.auteur = User.objects.create_user(
            username="auteur", password="motdepasse",
        )
        self.gardien = User.objects.create_user(
            username="gardien", password="motdepasse",
        )
        self.carnet_du_gardien = Dossier.objects.create(
            name="Carnet de classe", owner=self.gardien,
        )

    def _note_de_l_auteur(self, titre="Une note"):
        return Page.objects.create(
            title=titre, source_type="web", html_original="<p>x</p>",
            html_readability="<p>x</p>", text_readability="x",
            content_hash="", owner=self.auteur,
        )

    def test_l_auteur_supprime_vraiment_sa_note(self):
        note = self._note_de_l_auteur()
        ranger_une_note_dans_un_carnet(note, self.carnet_du_gardien, self.auteur)
        self.client.force_login(self.auteur)

        self.client.post(
            f"/pages/{note.pk}/supprimer/",
            {"dossier_id": self.carnet_du_gardien.pk},
        )

        self.assertFalse(Page.objects.filter(pk=note.pk).exists())

    def test_le_gardien_retire_du_carnet_sans_detruire(self):
        # LE COEUR DE LA REGLE : qui ne possede pas la note ne la
        # detruit jamais. / Whoever does not own the note never destroys it.
        note = self._note_de_l_auteur()
        ranger_une_note_dans_un_carnet(note, self.carnet_du_gardien, self.auteur)
        self.client.force_login(self.gardien)

        self.client.post(
            f"/pages/{note.pk}/supprimer/",
            {"dossier_id": self.carnet_du_gardien.pk},
        )

        self.assertTrue(Page.objects.filter(pk=note.pk).exists())
        self.assertFalse(
            note.appartenances_dossiers.filter(
                dossier=self.carnet_du_gardien,
            ).exists(),
        )

    def test_le_gardien_retire_meme_le_dernier_carnet_la_note_devient_orpheline(self):
        note = self._note_de_l_auteur()
        ranger_une_note_dans_un_carnet(note, self.carnet_du_gardien, self.auteur)
        self.client.force_login(self.gardien)

        self.client.post(
            f"/pages/{note.pk}/supprimer/",
            {"dossier_id": self.carnet_du_gardien.pk},
        )

        note.refresh_from_db()
        self.assertTrue(Page.objects.filter(pk=note.pk).exists())
        self.assertEqual(note.appartenances_dossiers.count(), 0)
        # Elle reste visible de son auteur. / Still visible to its author.
        self.assertEqual(note.owner, self.auteur)

    def test_un_tiers_ne_peut_ni_supprimer_ni_retirer(self):
        tiers = User.objects.create_user(username="tiers", password="x")
        note = self._note_de_l_auteur()
        ranger_une_note_dans_un_carnet(note, self.carnet_du_gardien, self.auteur)
        self.client.force_login(tiers)

        self.client.post(
            f"/pages/{note.pk}/supprimer/",
            {"dossier_id": self.carnet_du_gardien.pk},
        )

        self.assertTrue(Page.objects.filter(pk=note.pk).exists())
        self.assertTrue(
            note.appartenances_dossiers.filter(
                dossier=self.carnet_du_gardien,
            ).exists(),
        )

    def test_sans_dossier_id_l_auteur_supprime_quand_meme(self):
        # Compatibilite : un appel sans carnet de contexte (ancien JS en
        # cache, appel direct) reste traite. Pour l'auteur, c'est une
        # suppression. / Backward compatible: the author still deletes.
        note = self._note_de_l_auteur()
        self.client.force_login(self.auteur)

        self.client.post(f"/pages/{note.pk}/supprimer/")

        self.assertFalse(Page.objects.filter(pk=note.pk).exists())

    def test_sans_dossier_id_le_gardien_est_refuse_proprement(self):
        # On ne peut pas retirer d'un carnet qu'on ne connait pas, et on
        # ne detruira pas la note d'autrui par defaut. On refuse en le
        # disant. / Cannot remove from an unknown notebook; refuse plainly.
        note = self._note_de_l_auteur()
        ranger_une_note_dans_un_carnet(note, self.carnet_du_gardien, self.auteur)
        self.client.force_login(self.gardien)

        reponse = self.client.post(f"/pages/{note.pk}/supprimer/")

        self.assertTrue(Page.objects.filter(pk=note.pk).exists())
        self.assertIn(reponse.status_code, (400, 409))

    def test_un_dossier_id_qui_ne_contient_pas_la_note_est_refuse(self):
        autre_carnet = Dossier.objects.create(
            name="Ailleurs", owner=self.gardien,
        )
        note = self._note_de_l_auteur()
        ranger_une_note_dans_un_carnet(note, self.carnet_du_gardien, self.auteur)
        self.client.force_login(self.gardien)

        reponse = self.client.post(
            f"/pages/{note.pk}/supprimer/", {"dossier_id": autre_carnet.pk},
        )

        self.assertTrue(
            note.appartenances_dossiers.filter(
                dossier=self.carnet_du_gardien,
            ).exists(),
        )
        self.assertIn(reponse.status_code, (400, 404, 409))
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_suppression_de_note --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `test_le_gardien_retire_du_carnet_sans_detruire` échoue — la note
est détruite, c'est le comportement actuel.

- [ ] **Étape 3 : écrire le sérialiseur et la règle**

Créer le sérialiseur d'entrée dans `front/serializers.py`, à côté des autres :

```python
class PageSupprimerSerializer(serializers.Serializer):
    """
    Valide le carnet de contexte d'une suppression de note.
    / Validates a note deletion's context notebook.

    LOCALISATION : front/serializers.py

    `dossier_id` dit DEPUIS QUEL CARNET le geste est fait. Sans lui, on
    ne peut pas « retirer du carnet » — seulement supprimer ou refuser.
    / Says which notebook the gesture came from.
    """
    dossier_id = serializers.IntegerField(required=False, allow_null=True)
```

Puis remplacer le corps de `PageViewSet.supprimer` : après
`_exiger_authentification` et `get_object_or_404`, valider l'entrée, vérifier
`_est_proprietaire_page` (inchangé), puis **aiguiller** :

- si l'utilisateur est `page.owner` → suppression réelle, code actuel inchangé
  (avec son `try/except SuppressionRefuseeSourceCitee`) ;
- sinon → il est propriétaire d'un carnet. S'il n'a pas donné de `dossier_id`,
  refuser en le disant. S'il en a donné un, vérifier **qu'il en est bien
  propriétaire** et **que la note y est rangée**, puis appeler
  `retirer_une_note_d_un_carnet(page, carnet)`.

Le message de retour doit dire ce qui s'est passé : « retirée du carnet » n'est
pas « supprimée ». Réutiliser le patron `HX-Trigger` / `showToast` déjà en
place dans cette action.

- [ ] **Étape 4 : lancer les tests, vérifier qu'ils passent**

- [ ] **Étape 5 : transmettre le carnet depuis l'arbre**

Le menu contextuel ne connaît aujourd'hui que le pk de la note
(`arbre_context_menu.js:313`). Il faut qu'il connaisse aussi le carnet sous
lequel la note est affichée.

Lire `front/templates/front/includes/arbre_dossiers.html` pour voir comment
les nœuds sont rendus, et poser un attribut de données sur le nœud de la note
— par exemple `data-dossier-id`. Puis le lire dans le JS et l'ajouter au
corps du `htmx.ajax('POST', ...)`.

**Ne pas deviner la structure du gabarit : la lire.**

- [ ] **Étape 6 : conditionner la confirmation**

La confirmation est aujourd'hui systématique et annonce « Cette action est
irréversible » — ce qui est **faux** pour un simple retrait de carnet.

Le JS ne peut pas décider seul : il ignore si la note est dans plusieurs
carnets et si elle porte des commentaires. C'est au serveur de le lui dire,
via des attributs de données posés sur le nœud au rendu de l'arbre.

Poser sur le nœud de la note ce que la vue de l'arbre sait déjà, ou peut
savoir sans requête supplémentaire par note (attention aux N+1 : l'arbre
rend potentiellement des centaines de nœuds — utiliser une annotation de
requête, pas une boucle) :

- le geste sera-t-il une suppression ou un retrait, pour cet utilisateur ;
- la note porte-t-elle des commentaires ou des ancres.

Puis dans le JS :

- **retrait** → pas de confirmation, action directe, message « retirée du
  carnet » ;
- **suppression d'une note sans commentaire ni ancre, dans un seul carnet** →
  pas de confirmation ;
- **suppression destructive** (plusieurs carnets, ou commentaires, ou ancres)
  → confirmation, dont le texte **dit ce qui va être perdu**, pas seulement
  « irréversible ».

- [ ] **Étape 7 : `collectstatic` et bump du `?v=`**

`arbre_context_menu.js` est un fichier statique. Sans ces deux gestes, les
navigateurs continuent de servir l'ancien code :

```bash
docker exec -w /app hypostasia_web uv run python manage.py collectstatic --noinput
```

Puis **incrémenter le `?v=`** de la balise qui charge ce fichier, dans le
gabarit qui l'inclut (chercher `arbre_context_menu.js` dans
`front/templates/`).

- [ ] **Étape 8 : vérifier au navigateur**

Sur https://h.localhost/, connecté en `jonas` / `admin1234` :

1. supprimer une note dont on est l'auteur, sans commentaire → pas de
   confirmation, la note disparaît, son fichier aussi ;
2. la même dans deux carnets → confirmation, et le texte dit ce qui est perdu ;
3. avec un second compte propriétaire d'un carnet contenant une note d'autrui
   → le geste retire du carnet, la note existe toujours.

**Vérifier dans la console du navigateur** qu'aucune erreur JS n'apparaît, et
que le fichier chargé est bien le nouveau (l'onglet réseau montre le `?v=`).

- [ ] **Étape 9 : point d'arrêt**

---

## Tâche 3 : l'échec Voxtral ne laisse pas de coquille

**Fichiers :**
- Modifier : `core/models.py` (`TranscriptionJob.page`)
- Créer : une migration de schéma
- Modifier : `front/tasks.py` (`transcrire_audio_task`)
- Modifier : `front/views_taches.py` et
  `front/templates/front/includes/taches_dropdown.html` (un job peut désormais
  n'avoir plus de page)
- Test : `front/tests/test_echec_transcription.py` (créer)

**Interfaces :**
- Consomme : `notifier_tache_terminee`, `_destinataires_de_notification`.
- Produit : `TranscriptionJob.page` devient `null=True`, `on_delete=SET_NULL`.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""
Que reste-t-il quand une transcription echoue ?
/ What remains when a transcription fails?

LOCALISATION : front/tests/test_echec_transcription.py
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Page, TranscriptionJob, TranscriptionJobStatus

User = get_user_model()


class EchecDeTranscriptionTest(TestCase):

    def setUp(self):
        self.proprietaire = User.objects.create_user(username="proprio")
        self.page = Page.objects.create(
            title="Un audio", source_type="audio", original_filename="a.mp3",
            html_original="", html_readability="", text_readability="",
            content_hash="", status="processing", owner=self.proprietaire,
        )
        self.job = TranscriptionJob.objects.create(
            page=self.page, audio_filename="a.mp3", status="pending",
        )

    def _faire_echouer_la_transcription(self):
        from front.tasks import transcrire_audio_task

        with patch(
            "front.tasks.transcrire_audio_mock",
            side_effect=RuntimeError("Voxtral injoignable"),
        ), patch(
            "front.tasks.transcrire_audio_via_voxtral",
            side_effect=RuntimeError("Voxtral injoignable"),
        ):
            return transcrire_audio_task.apply(
                args=[self.job.pk, "/tmp/inexistant.mp3", 5, "fr"],
            )

    def test_la_page_vide_est_supprimee(self):
        self._faire_echouer_la_transcription()

        self.assertFalse(Page.objects.filter(pk=self.page.pk).exists())

    def test_le_job_survit_avec_sa_raison(self):
        # C'EST LE POINT DE CETTE TACHE : la coquille part, la raison
        # reste. / The shell goes, the reason stays.
        self._faire_echouer_la_transcription()

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, TranscriptionJobStatus.ERROR)
        self.assertIn("Voxtral injoignable", self.job.error_message)
        self.assertIsNone(self.job.page)

    def test_l_utilisateur_est_prevenu(self):
        with patch("front.tasks.notifier_tache_terminee") as notification:
            self._faire_echouer_la_transcription()

        self.assertTrue(notification.called)
        self.assertEqual(
            notification.call_args.kwargs["status"], "error",
        )

    def test_une_page_qui_a_des_elements_n_est_PAS_supprimee(self):
        # Une page qui porte deja des elements n'est pas une coquille :
        # une seconde tentative echouee ne doit pas emporter le travail
        # d'une premiere qui avait reussi.
        # / A page with elements is not an empty shell: never delete it.
        self.page.elements.create(
            ordre=0, label="text", texte="deja la", empreinte_contenu="x",
        )

        self._faire_echouer_la_transcription()

        self.assertTrue(Page.objects.filter(pk=self.page.pk).exists())
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_echec_transcription --noinput \
    --settings=hypostasia.settings_test_opus
```

- [ ] **Étape 3 : rendre la page facultative sur le job**

Dans `core/models.py`, `TranscriptionJob.page` :

```python
    page = models.ForeignKey(
        Page,
        # SET_NULL et non CASCADE : quand une transcription echoue, on
        # supprime la page vide qu'elle laisserait derriere elle, mais on
        # GARDE le job — c'est lui qui porte error_message, donc la seule
        # trace de POURQUOI ca a echoue. En CASCADE, supprimer la coquille
        # effacait aussi le diagnostic (decision du 11 aout 2026).
        # / SET_NULL: the job carries error_message, the only trace of why.
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="transcription_jobs",
        help_text="Page associee. NULL si la page a ete supprimee apres un echec.",
    )
```

Créer la migration, **et l'appliquer à la base de développement** :

```bash
docker exec -w /app hypostasia_web uv run python manage.py makemigrations core
docker exec -w /app hypostasia_web uv run python manage.py migrate core --noinput
```

- [ ] **Étape 4 : traiter les lecteurs de `job.page`**

Un job peut désormais n'avoir plus de page. Deux endroits le supposent :

- `front/views_taches.py:180` — `transcription.page_resultat_id = transcription.page.pk`
  lèverait `AttributeError`. Traiter le cas.
- `front/templates/front/includes/taches_dropdown.html:60` et `:75` —
  `tache.page.title` et `tache.page.pk`. Un gabarit Django rend une chaîne
  vide sur un `None` sans lever, mais le lien deviendrait `/lire//`. Traiter
  explicitement : afficher le nom du fichier audio (`audio_filename`) et
  n'afficher **aucun lien** quand la page n'existe plus.

Chercher tout autre lecteur avant de conclure :

```bash
grep -rn "\.page\b" --include=*.py front/ core/ | grep -i "transcription"
```

- [ ] **Étape 5 : supprimer la coquille dans la tâche**

Dans le `except` de `transcrire_audio_task`, après avoir posé les statuts
d'erreur et **avant** de notifier :

- ne supprimer la page **que si** elle n'a aucun élément — une page qui en
  porte n'est pas une coquille ;
- délier le job avant la suppression, ou compter sur le `SET_NULL` (le tester,
  ne pas le supposer) ;
- notifier **après**, avec `status="error"`.

Attention à l'ordre : la notification porte `tache_id`. Si la page est
supprimée, c'est le pk du **job** qu'il faut transmettre, pas celui de la
page — la transcription a toujours utilisé le pk du job, donc rien à changer,
mais le vérifier.

- [ ] **Étape 6 : lancer les tests, vérifier qu'ils passent**

Puis, **séparément**, les suites touchées :

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_taches_ingestion front.tests.test_notification_transcription \
    --noinput --settings=hypostasia.settings_test_opus
```

- [ ] **Étape 7 : redémarrer le worker Celery**

Une tâche modifiée n'est pas rechargée à chaud : le worker tourne avec
l'ancien code tant qu'il n'a pas redémarré. Il est dans un pane byobu —
le signaler au mainteneur plutôt que de le tuer soi-même.

- [ ] **Étape 8 : point d'arrêt**

---

## Tâche 4 : la ligne `--a-blanc` qui ment

**Fichiers :**
- Modifier : `front/management/commands/charger_fixtures_sample.py`
- Modifier : `front/tests/test_charger_fixtures_sample.py`

Détail relevé à la revue finale du 11 août. En mode `--a-blanc`, la commande
annonce ce qu'elle ferait. Toutes ses lignes disent vrai sauf une :

```
Carnet              : Documents étalons — pk=1 (réutilisé)
Transcription       : Voxtral Mini (serait créée)   ← ment : elle existe
```

`_creer_la_config_de_transcription` rend `None` en mode à blanc **sans
chercher** la configuration existante, exactement le travers déjà corrigé sur
`_creer_le_carnet`.

- [ ] **Étape 1 : écrire le test qui échoue**

```python
    def test_a_blanc_dit_que_la_config_existe_deja(self):
        import os

        from core.models import TranscriptionConfig

        TranscriptionConfig.objects.create(
            name="Voxtral Mini", model_choice="voxtral-mini-latest",
            is_active=True,
        )
        sortie = StringIO()

        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
            call_command("charger_fixtures_sample", "--a-blanc", stdout=sortie)

        self.assertIn("réutilisée", sortie.getvalue())
        self.assertNotIn("serait créée", sortie.getvalue())
```

- [ ] **Étape 2 : le faire échouer**, puis corriger sur le patron exact de
  `_creer_le_carnet` : chercher sans créer, dire « réutilisée » si trouvée.

- [ ] **Étape 3 : relancer `front.tests.test_charger_fixtures_sample`.**

- [ ] **Étape 4 : point d'arrêt**

---

## Vérification finale

- [ ] Les quatre suites passent, avec leur nombre de tests.
- [ ] Les migrations sont appliquées à la base de développement, et le
      serveur répond toujours sur https://h.localhost/.
- [ ] Supprimer une note efface son fichier ; le répertoire `media/sources/`
      ne gagne pas d'orphelin.
- [ ] Un propriétaire de carnet qui « supprime » la note d'autrui la retire,
      et elle existe toujours.
- [ ] Une transcription échouée ne laisse aucune page vide, mais un
      `TranscriptionJob` en erreur qui dit pourquoi.
- [ ] Le menu des tâches affiche ce job sans lien mort.
- [ ] `collectstatic` fait, `?v=` incrémenté, vérifié dans l'onglet réseau.
- [ ] `CHANGELOG.md` et une fiche `A TESTER et DOCUMENTER/` rédigés.
- [ ] Aucune opération git.
