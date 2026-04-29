# Synthèse délibérative drawer — Plan d'implémentation

> **Spec source :** `docs/superpowers/specs/2026-04-29-synthese-drawer-confirmation-design.md`
>
> **Note importante** : ce projet ne commit pas via l'agent. Chaque tâche se termine par une **vérification** (tests + check Django) au lieu d'un commit. Le mainteneur committera lui-même.

**Goal :** Remplacer le modal JS de synthèse par un partial Django dans le drawer, avec confirmation complète (estimation, prompt, consensus). Ajouter un bool `est_par_defaut` sur les analyseurs (un par type, auto-décochage des autres).

**Architecture :** Approche miroir du flow extraction. Nouveaux endpoints `previsualiser_synthese` + adaptation de `synthetiser` et `synthese_status` pour cibler `#drawer-contenu`. Auto-fermeture du drawer en fin de synthèse via `HX-Trigger: fermerDrawer` + OOB swap de la zone-lecture vers la V2.

**Tech Stack :** Django 6.0, DRF (`viewsets.ViewSet` + `@action`), HTMX (avec OOB swap), Celery (async), tiktoken (estimation tokens), Tailwind CSS.

**Commandes utiles :**
```bash
# Lancer tests rapides
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer -v2 --keepdb

# Check Django
docker exec hypostasia_web uv run python manage.py check

# Shell Django
docker exec hypostasia_web uv run python manage.py shell -c "..."
```

---

## Tâche 1 : Modèle `est_par_defaut` + migration

**Files:**
- Modify: `hypostasis_extractor/models.py:336+` (ajout du champ + save())
- Create: `hypostasis_extractor/migrations/0026_analyseursyntaxique_est_par_defaut.py` (auto)
- Create: `front/tests/test_phase29_synthese_drawer.py`

- [ ] **Étape 1.1 : Écrire le test unitaire qui échoue (champ + save logic)**

Créer le fichier `front/tests/test_phase29_synthese_drawer.py` :

```python
"""
Tests pour la PHASE-29 : synthese deliberative dans le drawer
+ bool est_par_defaut sur les analyseurs.
/ Tests for PHASE-29: deliberative synthesis in drawer
+ est_par_defaut bool on analyzers.
"""
from django.test import TestCase

from hypostasis_extractor.models import AnalyseurSyntaxique


class EstParDefautModeleTests(TestCase):
    """Tests sur le bool est_par_defaut et sa logique de save()."""

    def setUp(self):
        # Trois analyseurs du meme type / Three analyzers of the same type
        self.analyseur_a = AnalyseurSyntaxique.objects.create(
            name="Synthese A", type_analyseur="synthetiser",
            inclure_texte_original=True,
        )
        self.analyseur_b = AnalyseurSyntaxique.objects.create(
            name="Synthese B", type_analyseur="synthetiser",
            inclure_texte_original=True,
        )
        # Un analyseur d'un autre type / One analyzer of another type
        self.analyseur_autre_type = AnalyseurSyntaxique.objects.create(
            name="Hypostasia",
            type_analyseur="analyser",
            est_par_defaut=True,
        )

    def test_cocher_un_analyseur_comme_default(self):
        # Cocher A comme default → A doit avoir est_par_defaut=True
        # / Mark A as default → A must have est_par_defaut=True
        self.analyseur_a.est_par_defaut = True
        self.analyseur_a.save()
        self.analyseur_a.refresh_from_db()
        self.assertTrue(self.analyseur_a.est_par_defaut)

    def test_cocher_un_default_decoche_les_autres_du_meme_type(self):
        # B etait deja default → cocher A doit decocher B
        # / B was already default → marking A must uncheck B
        self.analyseur_b.est_par_defaut = True
        self.analyseur_b.save()
        self.analyseur_b.refresh_from_db()
        self.assertTrue(self.analyseur_b.est_par_defaut)

        self.analyseur_a.est_par_defaut = True
        self.analyseur_a.save()
        self.analyseur_b.refresh_from_db()
        self.assertFalse(self.analyseur_b.est_par_defaut)
        self.analyseur_a.refresh_from_db()
        self.assertTrue(self.analyseur_a.est_par_defaut)

    def test_cocher_un_default_ne_touche_pas_les_autres_types(self):
        # Cocher un analyseur synthetiser ne doit pas toucher l'analyseur "analyser"
        # / Marking a synthetiser analyzer must not affect the "analyser" type
        self.analyseur_a.est_par_defaut = True
        self.analyseur_a.save()
        self.analyseur_autre_type.refresh_from_db()
        self.assertTrue(self.analyseur_autre_type.est_par_defaut)
```

- [ ] **Étape 1.2 : Lancer le test pour confirmer qu'il échoue**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer -v2 --keepdb
```
Attendu : ERROR / FAIL (champ `est_par_defaut` n'existe pas).

- [ ] **Étape 1.3 : Ajouter le champ + save() dans le modèle**

Dans `hypostasis_extractor/models.py`, après le bloc `inclure_texte_original` (ligne ~376), avant `created_at` :

```python
    # Marqueur "par defaut" : un seul analyseur par type peut l'etre.
    # Cocher ici decoche automatiquement les autres analyseurs du meme type au save.
    # / "Default" marker: only one analyzer per type can have it.
    # / Checking here automatically unchecks other analyzers of the same type at save.
    est_par_defaut = models.BooleanField(
        default=False,
        help_text=(
            "Marquer cet analyseur comme defaut pour son type. "
            "Cocher ici decoche automatiquement les autres analyseurs du meme type."
        ),
    )
```

Et ajouter une surcharge de `save()` après le `def __str__()` (ligne ~385) :

```python
    def save(self, *args, **kwargs):
        # Si on coche est_par_defaut, decocher les autres analyseurs du meme type
        # / If we check est_par_defaut, uncheck other analyzers of the same type
        if self.est_par_defaut:
            AnalyseurSyntaxique.objects.filter(
                type_analyseur=self.type_analyseur,
                est_par_defaut=True,
            ).exclude(pk=self.pk).update(est_par_defaut=False)
        super().save(*args, **kwargs)
```

- [ ] **Étape 1.4 : Générer la migration**

```bash
docker exec hypostasia_web uv run python manage.py makemigrations hypostasis_extractor
```
Attendu : création de `0026_analyseursyntaxique_est_par_defaut.py`.

- [ ] **Étape 1.5 : Appliquer la migration**

```bash
docker exec hypostasia_web uv run python manage.py migrate
```
Attendu : `Applying hypostasis_extractor.0026_analyseursyntaxique_est_par_defaut... OK`.

- [ ] **Étape 1.6 : Relancer les tests**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer -v2 --keepdb
```
Attendu : 3 tests PASS.

- [ ] **Étape 1.7 : Vérifier**

```bash
docker exec hypostasia_web uv run python manage.py check
```
Attendu : `System check identified no issues`.

---

## Tâche 2 : Serializer + toast dans `partial_update`

**Files:**
- Modify: `hypostasis_extractor/serializers.py:237+` (ajouter le champ)
- Modify: `hypostasis_extractor/views.py` (`AnalyseurSyntaxiqueViewSet.partial_update`)
- Test: `front/tests/test_phase29_synthese_drawer.py` (ajouts)

- [ ] **Étape 2.1 : Ajouter le test pour le toast**

Dans `front/tests/test_phase29_synthese_drawer.py`, ajouter cette classe à la suite :

```python
import json
from django.contrib.auth.models import User


class PartialUpdateEstParDefautToastTests(TestCase):
    """Tests sur le toast info quand on coche est_par_defaut sur un analyseur."""

    def setUp(self):
        self.user_admin = User.objects.create_superuser(
            "admin_test", "admin@test.local", "test1234",
        )
        self.client.force_login(self.user_admin)
        self.analyseur_a = AnalyseurSyntaxique.objects.create(
            name="Synthese A", type_analyseur="synthetiser",
            inclure_texte_original=True,
        )
        self.analyseur_b = AnalyseurSyntaxique.objects.create(
            name="Synthese B", type_analyseur="synthetiser",
            inclure_texte_original=True,
            est_par_defaut=True,
        )

    def test_patch_est_par_defaut_true_renvoie_toast_si_un_autre_etait_default(self):
        # PATCH A.est_par_defaut=True → B doit etre decoche + toast info renvoye
        # / PATCH A.est_par_defaut=True → B must be unchecked + info toast returned
        reponse = self.client.patch(
            f"/api/analyseurs/{self.analyseur_a.pk}/",
            data=json.dumps({"est_par_defaut": True}),
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 200)
        # Verifier que le HX-Trigger contient le toast info
        # / Check that HX-Trigger contains the info toast
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertTrue(trigger, "HX-Trigger absent")
        donnees_trigger = json.loads(trigger)
        self.assertIn("showToast", donnees_trigger)
        self.assertEqual(donnees_trigger["showToast"]["icon"], "info")
        self.assertIn("Synthese B", donnees_trigger["showToast"]["message"])

    def test_patch_est_par_defaut_true_sans_autre_default_ne_declenche_pas_toast(self):
        # B est deja default, A devient default → toast renvoye (B est decoche)
        # On teste maintenant le cas ou personne n'etait default
        # / B was default, A becomes default → toast (B unchecked)
        # / Now test the case where nobody was default
        # On retire le default de B
        # / Remove default from B
        AnalyseurSyntaxique.objects.filter(pk=self.analyseur_b.pk).update(est_par_defaut=False)

        reponse = self.client.patch(
            f"/api/analyseurs/{self.analyseur_a.pk}/",
            data=json.dumps({"est_par_defaut": True}),
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 200)
        trigger = reponse.headers.get("HX-Trigger", "")
        # Pas de toast attendu / No toast expected
        self.assertFalse(trigger, f"HX-Trigger inattendu : {trigger}")

    def test_patch_autre_champ_ne_declenche_pas_toast(self):
        # PATCH name uniquement → pas de toast
        # / PATCH name only → no toast
        reponse = self.client.patch(
            f"/api/analyseurs/{self.analyseur_a.pk}/",
            data=json.dumps({"name": "Nouveau nom"}),
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 200)
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertFalse(trigger, f"HX-Trigger inattendu : {trigger}")
```

- [ ] **Étape 2.2 : Lancer pour confirmer l'échec**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.PartialUpdateEstParDefautToastTests -v2 --keepdb
```
Attendu : 3 FAIL (le serializer rejette le champ inconnu, ou le toast n'est pas généré).

- [ ] **Étape 2.3 : Ajouter `est_par_defaut` au serializer**

Dans `hypostasis_extractor/serializers.py`, dans `AnalyseurSyntaxiqueUpdateSerializer` (ligne ~237), à la suite des autres `BooleanField` :

```python
    est_par_defaut = serializers.BooleanField(required=False)
```

- [ ] **Étape 2.4 : Modifier `partial_update` pour le toast**

Dans `hypostasis_extractor/views.py`, remplacer la méthode `partial_update` du `AnalyseurSyntaxiqueViewSet` (ligne ~498) par :

```python
    def partial_update(self, request, pk=None):
        """Mise a jour partielle (auto-save). Staff uniquement.
        Si on coche est_par_defaut, renvoie un toast info si un autre etait default.
        / Partial update (auto-save). Staff only.
        / If checking est_par_defaut, returns an info toast if another was default.
        """
        reponse_refus = _exiger_staff(request)
        if reponse_refus:
            return reponse_refus
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = AnalyseurSyntaxiqueUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Capturer l'autre default du meme type AVANT le save (pour le toast)
        # / Capture other default of same type BEFORE save (for the toast)
        autre_default_decoche = None
        coche_default = serializer.validated_data.get("est_par_defaut") is True
        if coche_default and not analyseur.est_par_defaut:
            autre_default_decoche = AnalyseurSyntaxique.objects.filter(
                type_analyseur=analyseur.type_analyseur,
                est_par_defaut=True,
            ).exclude(pk=analyseur.pk).first()

        for field_name, field_value in serializer.validated_data.items():
            setattr(analyseur, field_name, field_value)
        analyseur.save()

        # Reponse standard + HX-Trigger toast si un autre default a ete decoche
        # / Standard response + HX-Trigger toast if another default was unchecked
        reponse = _saved_response()
        if autre_default_decoche:
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": (
                        f"Analyseur « {autre_default_decoche.name} » n'est plus "
                        f"marqué par défaut pour le type "
                        f"« {analyseur.get_type_analyseur_display()} »."
                    ),
                    "icon": "info",
                },
            })
        return reponse
```

- [ ] **Étape 2.5 : Relancer les tests**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer -v2 --keepdb
```
Attendu : 6 tests PASS (3 du Tâche 1 + 3 du Tâche 2).

- [ ] **Étape 2.6 : Vérifier**

```bash
docker exec hypostasia_web uv run python manage.py check
```
Attendu : 0 issues.

---

## Tâche 3 : Toggle dans editor + badges

**Files:**
- Modify: `hypostasis_extractor/templates/hypostasis_extractor/analyseur_editor.html` (ajout toggle)
- Modify: `front/templates/front/includes/carte_analyseur.html` (badge default)
- Modify: `front/templates/front/includes/detail_analyseur_readonly.html` (badge)
- Modify: `hypostasis_extractor/templates/hypostasis_extractor/includes/analyseur_item.html` (badge)

- [ ] **Étape 3.1 : Ajouter le toggle dans editor**

Dans `analyseur_editor.html`, dans le bloc `<div class="flex flex-col gap-3 mb-4">` (lignes ~68-91), à la suite du toggle « Inclure le texte original », ajouter :

```html
            <label class="flex items-center gap-3 cursor-pointer">
                <div class="relative">
                    <input type="checkbox" id="toggle-est-par-defaut-{{ analyseur.id }}"
                           {% if analyseur.est_par_defaut %}checked{% endif %}
                           class="toggle-contexte sr-only peer"
                           data-champ="est_par_defaut">
                    <div class="w-9 h-5 bg-slate-300 rounded-full peer-checked:bg-blue-500 transition-colors"></div>
                    <div class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow peer-checked:translate-x-4 transition-transform"></div>
                </div>
                <span class="text-sm text-slate-700">Analyseur par défaut pour son type</span>
            </label>
```

Le JS auto-save existant (boucle `.toggle-contexte`) gère déjà ce nouveau toggle sans modification.

- [ ] **Étape 3.2 : Ajouter le badge dans `carte_analyseur.html`**

Lire d'abord le fichier pour voir où placer le badge. Le badge va à côté du nom de l'analyseur, après le badge de type. Format :

```html
{% if analyseur.est_par_defaut %}
    <span class="px-2 py-0.5 text-[10px] font-medium rounded-full bg-blue-50 text-blue-700 border border-blue-200" data-testid="badge-defaut">
        Par défaut
    </span>
{% endif %}
```

(Localisation exacte à confirmer en lisant le fichier — chercher la ligne qui affiche le `badge-type`.)

- [ ] **Étape 3.3 : Ajouter le badge dans `detail_analyseur_readonly.html`**

Idem : à côté du nom, après le badge de type. Même format que 3.2.

- [ ] **Étape 3.4 : Ajouter le badge dans `analyseur_item.html` (sidebar config LLM)**

Dans `hypostasis_extractor/templates/hypostasis_extractor/includes/analyseur_item.html`, ajouter dans la zone de droite :

```html
{% if analyseur.est_par_defaut %}
    <span class="px-1.5 py-0.5 text-[9px] font-medium rounded-full bg-blue-50 text-blue-700 border border-blue-200 ml-1" data-testid="badge-defaut" title="Par defaut pour son type">
        ★
    </span>
{% endif %}
```

(Étoile pour ne pas alourdir la sidebar.)

- [ ] **Étape 3.5 : Vérifier**

```bash
docker exec hypostasia_web uv run python manage.py check
```
Attendu : 0 issues. Pas de tests automatisés pour cette étape (templates), test visuel manuel dans le navigateur.

---

## Tâche 4 : Helper `_calculer_consensus`

**Files:**
- Modify: `front/views.py` (extraction du calcul de consensus en helper)
- Test: `front/tests/test_phase29_synthese_drawer.py`

- [ ] **Étape 4.1 : Identifier la vue dashboard et son code consensus**

```bash
grep -n "dashboard_consensus\|seuil_consensus\|extractions_bloquantes" front/views.py | head -10
```

- [ ] **Étape 4.2 : Lire la vue qui calcule le consensus**

Lire la portion de code identifiée (probablement dans une `@action` du `PageViewSet` qui s'appelle `dashboard_consensus`). Comprendre la structure du dict retourné.

- [ ] **Étape 4.3 : Écrire le test du helper**

Dans `front/tests/test_phase29_synthese_drawer.py`, ajouter :

```python
from core.models import Page, Dossier
from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
from front.views import _calculer_consensus


class CalculerConsensusHelperTests(TestCase):
    """Tests sur le helper _calculer_consensus."""

    def setUp(self):
        self.user = User.objects.create_user("user_test", password="test1234")
        self.dossier = Dossier.objects.create(name="Test", owner=self.user)
        self.page = Page.objects.create(
            title="Test", dossier=self.dossier, owner=self.user,
            html_readability="<p>Test</p>", text_readability="Test text",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page, status="completed", name="Test",
        )
        # 3 entites consensuelles, 1 discutee, 1 controverse, 1 non_pertinent
        # / 3 consensual, 1 discussed, 1 controversial, 1 non-relevant
        for _ in range(3):
            ExtractedEntity.objects.create(
                job=self.job, extraction_class="theorie",
                extraction_text="texte", statut_debat="consensuel",
            )
        ExtractedEntity.objects.create(
            job=self.job, extraction_class="theorie",
            extraction_text="texte", statut_debat="discute",
        )
        ExtractedEntity.objects.create(
            job=self.job, extraction_class="theorie",
            extraction_text="texte", statut_debat="controverse",
        )
        ExtractedEntity.objects.create(
            job=self.job, extraction_class="theorie",
            extraction_text="texte", statut_debat="non_pertinent",
        )

    def test_calculer_consensus_compteurs_corrects(self):
        consensus = _calculer_consensus(self.page)
        self.assertEqual(consensus["compteur_consensuel"], 3)
        self.assertEqual(consensus["compteur_discute"], 1)
        self.assertEqual(consensus["compteur_controverse"], 1)
        self.assertEqual(consensus["compteur_non_pertinent"], 1)

    def test_calculer_consensus_pourcentage(self):
        # 3 consensuel sur 6 entites visibles (5 si on exclut non_pertinent — verifier)
        # / Verify the formula matches existing dashboard logic
        consensus = _calculer_consensus(self.page)
        self.assertIn("pourcentage_consensus", consensus)
        self.assertIn("seuil_consensus", consensus)
        self.assertIn("seuil_atteint", consensus)
        self.assertIn("extractions_bloquantes", consensus)
```

- [ ] **Étape 4.4 : Lancer pour confirmer l'échec**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.CalculerConsensusHelperTests -v2 --keepdb
```
Attendu : ImportError (`_calculer_consensus` n'existe pas).

- [ ] **Étape 4.5 : Extraire le helper**

Dans `front/views.py`, juste avant la classe `PageViewSet` (chercher `class PageViewSet`) ou à proximité d'autres helpers comme `_rendre_drawer_analyse_en_cours`, ajouter une nouvelle fonction `_calculer_consensus(page)` qui contient la logique extraite de la vue `dashboard_consensus` actuelle.

**Pour ne pas casser ce qui existe** : la fonction renvoie un dict avec les mêmes clés que celles utilisées par `dashboard_consensus.html`. Puis modifier la vue `dashboard_consensus` pour appeler ce helper au lieu de calculer directement.

(Le code exact dépend de l'implémentation actuelle — voir Étape 4.2.)

- [ ] **Étape 4.6 : Relancer les tests**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.CalculerConsensusHelperTests -v2 --keepdb
```
Attendu : 2 tests PASS.

- [ ] **Étape 4.7 : Vérifier que le dashboard fonctionne toujours**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phases -v2 --keepdb -k "consensus"
```
Attendu : tous les tests existants sur le consensus passent.

---

## Tâche 5 : Endpoint `previsualiser_synthese`

**Files:**
- Modify: `front/views.py` (`PageViewSet`, ajout de l'action)
- Test: `front/tests/test_phase29_synthese_drawer.py`

- [ ] **Étape 5.1 : Écrire les tests d'intégration**

Dans `front/tests/test_phase29_synthese_drawer.py`, ajouter :

```python
from core.models import Configuration, AIModel


class PrevisualiserSyntheseTests(TestCase):
    """Tests sur l'endpoint /lire/{pk}/previsualiser_synthese/."""

    def setUp(self):
        self.user = User.objects.create_user("user_test", password="test1234")
        self.client.force_login(self.user)
        self.dossier = Dossier.objects.create(name="Test", owner=self.user)
        self.page = Page.objects.create(
            title="Test", dossier=self.dossier, owner=self.user,
            html_readability="<p>Test</p>", text_readability="Test text",
        )
        # Modele IA actif / Active AI model
        self.modele_ia = AIModel.objects.create(
            provider="ollama", model_name="test-model", is_active=True,
            cout_input_par_million=0.5, cout_output_par_million=1.0,
        )
        config = Configuration.get_solo()
        config.ai_active = True
        config.ai_model = self.modele_ia
        config.save()
        # Analyseur synthese par defaut / Default synthesis analyzer
        self.analyseur_synthese = AnalyseurSyntaxique.objects.create(
            name="Synthese delib", type_analyseur="synthetiser",
            inclure_extractions=True, inclure_texte_original=True,
            est_par_defaut=True,
        )

    def test_previsualiser_synthese_renvoie_partial(self):
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("confirmation-synthese", contenu)
        self.assertIn("Synthese delib", contenu)

    def test_previsualiser_sans_analyseur_synthese_renvoie_400(self):
        AnalyseurSyntaxique.objects.filter(type_analyseur="synthetiser").delete()
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 400)
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertIn("showToast", trigger)
        self.assertIn("error", trigger)

    def test_previsualiser_sans_modele_ia_renvoie_400(self):
        config = Configuration.get_solo()
        config.ai_model = None
        config.save()
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 400)

    def test_previsualiser_avec_inclure_extractions_mais_zero_extractions(self):
        # inclure_extractions=True mais pas de job d'analyse → bouton desactive
        # / inclure_extractions=True but no analysis job → button disabled
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        # Le contenu doit indiquer que le bouton est desactive
        # / Content must indicate the button is disabled
        self.assertIn("Lancez d'abord une analyse", contenu)

    def test_previsualiser_avec_les_deux_bool_a_false(self):
        # Les deux bool a False → bouton desactive avec message "configurez"
        # / Both bools False → button disabled with "configure" message
        self.analyseur_synthese.inclure_extractions = False
        self.analyseur_synthese.inclure_texte_original = False
        AnalyseurSyntaxique.objects.filter(pk=self.analyseur_synthese.pk).update(
            inclure_extractions=False,
            inclure_texte_original=False,
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Configurez l'analyseur", contenu)

    def test_previsualiser_select_analyseur_param(self):
        # Si plusieurs analyseurs synthetiser, ?analyseur_id=N permet de basculer
        # / If multiple synthetiser analyzers, ?analyseur_id=N switches
        autre_analyseur = AnalyseurSyntaxique.objects.create(
            name="Autre Synthese", type_analyseur="synthetiser",
            inclure_texte_original=True,
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/?analyseur_id={autre_analyseur.pk}",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Autre Synthese", contenu)
```

- [ ] **Étape 5.2 : Lancer pour confirmer l'échec**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.PrevisualiserSyntheseTests -v2 --keepdb
```
Attendu : tous FAIL (404 car endpoint n'existe pas).

- [ ] **Étape 5.3 : Implémenter l'endpoint dans `PageViewSet`**

Dans `front/views.py`, après l'action `synthetiser` (chercher `def synthetiser`), ajouter une nouvelle action :

```python
    @action(detail=True, methods=["GET"], url_path="previsualiser_synthese")
    def previsualiser_synthese(self, request, pk=None):
        """
        Construit le contexte de confirmation pour la synthese deliberative
        et renvoie le partial confirmation_synthese.html dans #drawer-contenu.
        Si un job de synthese est deja en cours → renvoie le partial polling.
        / Builds the confirmation context for deliberative synthesis
        / and returns confirmation_synthese.html in #drawer-contenu.
        / If a synthesis job is running → returns the polling partial.
        """
        page = get_object_or_404(Page, pk=pk)

        # Acces direct (F5) → rediriger vers la lecture
        # / Direct access (F5) → redirect to reading page
        if not request.headers.get("HX-Request"):
            return redirect(f"/lire/{pk}/")

        # Verifier s'il y a deja un job de synthese en cours
        # / Check if there is a synthesis job already running
        job_synthese_en_cours = ExtractionJob.objects.filter(
            page=page,
            status__in=["pending", "processing"],
            raw_result__contains={"est_synthese": True},
        ).order_by("-created_at").first()
        if job_synthese_en_cours:
            return render(request, "front/includes/synthese_en_cours_drawer.html", {
                "page": page,
            })

        # Recuperer l'analyseur synthese (default ou ?analyseur_id=)
        # / Get the synthesis analyzer (default or ?analyseur_id=)
        analyseur_id_choisi = request.GET.get("analyseur_id")
        if analyseur_id_choisi:
            analyseur_synthese = AnalyseurSyntaxique.objects.filter(
                pk=analyseur_id_choisi, is_active=True, type_analyseur="synthetiser",
            ).first()
        else:
            analyseur_synthese = None
        if not analyseur_synthese:
            analyseur_synthese = AnalyseurSyntaxique.objects.filter(
                is_active=True, type_analyseur="synthetiser",
            ).order_by("-est_par_defaut", "name").first()
        if not analyseur_synthese:
            reponse_erreur = HttpResponse(status=400)
            reponse_erreur["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Aucun analyseur de synthèse actif. Configurez-en un dans /api/analyseurs/.",
                    "icon": "error",
                },
            })
            return reponse_erreur

        # Tous les analyseurs synthese actifs (pour le selecteur)
        # / All active synthesis analyzers (for the selector)
        tous_les_analyseurs_synthese = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="synthetiser",
        ).order_by("-est_par_defaut", "name")

        # Modele IA actif / Active AI model
        configuration_ia = Configuration.get_solo()
        modele_ia_actif = configuration_ia.ai_model
        if not modele_ia_actif:
            reponse_erreur = HttpResponse(status=400)
            reponse_erreur["HX-Trigger"] = json.dumps({
                "showToast": {
                    "message": "Aucun modèle IA configuré. Ajoutez une clé API dans .env.",
                    "icon": "error",
                },
            })
            return reponse_erreur

        # Dernier job d'analyse complete (pour les extractions disponibles)
        # / Latest completed analysis job (for available extractions)
        dernier_job_analyse = ExtractionJob.objects.filter(
            page=page, status="completed",
        ).exclude(
            raw_result__contains={"est_synthese": True},
        ).order_by("-created_at").first()

        # Compter les extractions et commentaires disponibles
        # / Count available extractions and comments
        nombre_extractions_disponibles = 0
        nombre_commentaires_disponibles = 0
        if dernier_job_analyse:
            nombre_extractions_disponibles = ExtractedEntity.objects.filter(
                job=dernier_job_analyse, masquee=False,
            ).exclude(statut_debat="non_pertinent").count()
            nombre_commentaires_disponibles = CommentaireExtraction.objects.filter(
                entity__job=dernier_job_analyse,
            ).count()

        # Construire le prompt complet pour l'estimation et l'affichage
        # / Build the full prompt for estimation and display
        from front.tasks import _construire_prompt_synthese
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur_synthese,
        ).order_by("order")
        prompt_systeme = "\n".join(piece.content for piece in pieces_ordonnees)

        # Le prompt utilisateur ne peut etre construit que si on a un job d'analyse
        # ou si on inclut le texte original. Sinon → texte vide pour l'estimation.
        # / User prompt can only be built with analysis job or text original. Otherwise empty.
        prompt_utilisateur = ""
        if dernier_job_analyse or analyseur_synthese.inclure_texte_original:
            # Si pas de job d'analyse mais inclure_texte_original=True, on construit
            # quand meme avec un job factice → on doit gerer le cas dans _construire_prompt_synthese.
            # Mais celle-ci skipe deja le bloc HYPOSTASES si inclure_extractions=False.
            # Donc on lui passe None pour dernier_job_analyse si pas de job.
            prompt_utilisateur = _construire_prompt_synthese(
                page, dernier_job_analyse, analyseur_synthese,
            )
        prompt_complet = prompt_systeme + "\n\n" + prompt_utilisateur

        # Estimation tokens (pas de chunking pour la synthese, 1 seul appel)
        # / Token estimation (no chunking for synthesis, single call)
        import tiktoken
        import math
        encodeur_tokens = tiktoken.get_encoding("cl100k_base")
        nombre_tokens_input = len(encodeur_tokens.encode(prompt_complet))
        nombre_tokens_output_visible = int(nombre_tokens_input * 0.5)
        multiplicateur_thinking = modele_ia_actif.multiplicateur_thinking()
        nombre_tokens_thinking = nombre_tokens_output_visible * (multiplicateur_thinking - 1)
        nombre_tokens_output_total = nombre_tokens_output_visible + nombre_tokens_thinking
        cout_brut_euros = modele_ia_actif.estimer_cout_euros(
            nombre_tokens_input, nombre_tokens_output_total,
        )
        cout_estime_euros = max(0.01, math.ceil(cout_brut_euros * 1.5 * 100) / 100)

        # Consensus / Consensus
        consensus = _calculer_consensus(page)

        # Conditions de blocage / Blocking conditions
        bouton_desactive = False
        raison_desactivation = ""
        if (not analyseur_synthese.inclure_extractions
                and not analyseur_synthese.inclure_texte_original):
            bouton_desactive = True
            raison_desactivation = (
                "Configurez l'analyseur pour inclure au moins le texte original "
                "ou les extractions."
            )
        elif (analyseur_synthese.inclure_extractions
                and nombre_extractions_disponibles == 0):
            bouton_desactive = True
            raison_desactivation = (
                "Lancez d'abord une analyse pour cet analyseur, "
                "ou décochez « Inclure les extractions »."
            )

        # Gate solde credits Stripe
        # / Stripe credit balance gate
        contexte_credits = {}
        if (settings.STRIPE_ENABLED
                and request.user.is_authenticated
                and not request.user.is_superuser):
            from core.models import CreditAccount
            compte_existant = CreditAccount.objects.filter(user=request.user).first()
            if compte_existant:
                solde_utilisateur_euros = compte_existant.solde_euros
                solde_suffisant = solde_utilisateur_euros >= cout_estime_euros
                contexte_credits = {
                    "stripe_enabled": True,
                    "solde_suffisant": solde_suffisant,
                    "solde_utilisateur_euros": solde_utilisateur_euros,
                }
                if not solde_suffisant:
                    bouton_desactive = True

        return render(request, "front/includes/confirmation_synthese.html", {
            "page": page,
            "analyseur": analyseur_synthese,
            "analyseurs_actifs": tous_les_analyseurs_synthese,
            "modele_ia": modele_ia_actif,
            "nombre_pieces": pieces_ordonnees.count(),
            "nombre_tokens_input": nombre_tokens_input,
            "nombre_tokens_output_visible": nombre_tokens_output_visible,
            "nombre_tokens_thinking": nombre_tokens_thinking,
            "nombre_tokens_output_total": nombre_tokens_output_total,
            "multiplicateur_thinking": multiplicateur_thinking,
            "cout_estime_euros": cout_estime_euros,
            "prompt_complet": prompt_complet,
            "nombre_extractions_disponibles": nombre_extractions_disponibles,
            "nombre_commentaires_disponibles": nombre_commentaires_disponibles,
            "bouton_desactive": bouton_desactive,
            "raison_desactivation": raison_desactivation,
            **consensus,
            **contexte_credits,
        })
```

- [ ] **Étape 5.4 : Vérifier qu'il faut adapter `_construire_prompt_synthese`**

Vérifier si `_construire_prompt_synthese` lève une erreur quand `dernier_job_analyse` est `None` mais `inclure_extractions=False`. Si oui, adapter pour qu'elle accepte `None`. Sinon, c'est bon.

```bash
grep -A 5 "def _construire_prompt_synthese" front/tasks.py
```

Adapter si nécessaire pour rendre l'argument tolérant à `None` quand `inclure_extractions=False`.

- [ ] **Étape 5.5 : Relancer les tests**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.PrevisualiserSyntheseTests -v2 --keepdb
```
Attendu : 6 tests PASS (les templates seront créés à la Tâche 6 — pour passer ces tests dès maintenant, créer le template minimal vide).

- [ ] **Étape 5.6 : Vérifier**

```bash
docker exec hypostasia_web uv run python manage.py check
```

---

## Tâche 6 : Template `confirmation_synthese.html`

**Files:**
- Create: `front/templates/front/includes/confirmation_synthese.html`

- [ ] **Étape 6.1 : Créer le template**

Créer `front/templates/front/includes/confirmation_synthese.html` en miroir de `confirmation_analyse.html`. Structure complète :

```html
{# Partial : confirmation avant lancement d'une synthese deliberative #}
{# S'affiche dans #drawer-contenu (panneau drawer) #}
{# / Partial: confirmation before launching a deliberative synthesis #}
{# / Displayed in #drawer-contenu (drawer panel) #}

<div id="confirmation-synthese" class="py-4 px-1" data-page-id="{{ page.pk }}" data-testid="confirmation-synthese">

    {# En-tete avec titre / Header with title #}
    <div class="flex items-center gap-3 mb-5">
        <div class="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center shrink-0">
            <svg class="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
            </svg>
        </div>
        <div class="min-w-0">
            <h2 class="text-lg font-bold text-slate-900">Synthèse délibérative</h2>
            <p class="text-sm text-slate-500 truncate">{{ page.title|default:"Sans titre" }}</p>
        </div>
    </div>

    {# Selecteur d'analyseur si plusieurs / Analyzer selector if multiple #}
    {% if analyseurs_actifs.count > 1 %}
    <div class="mb-4">
        <label for="select-analyseur-synthese" class="block text-xs font-medium text-slate-600 mb-1">Analyseur de synthèse</label>
        <select id="select-analyseur-synthese" name="analyseur_id"
                data-testid="select-analyseur-synthese"
                hx-get="/lire/{{ page.pk }}/previsualiser_synthese/"
                hx-target="#drawer-contenu"
                hx-swap="innerHTML"
                hx-include="this"
                class="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-violet-400 focus:border-violet-400">
            {% for a in analyseurs_actifs %}
                <option value="{{ a.id }}" {% if a.id == analyseur.id %}selected{% endif %}>{{ a.name }}{% if a.est_par_defaut %} ★{% endif %}</option>
            {% endfor %}
        </select>
    </div>
    {% endif %}

    {# Encart consensus permanent (toujours present, reponse Q2 = c) #}
    {# / Permanent consensus block #}
    <div class="bg-slate-50 rounded-lg p-4 mb-4" data-testid="encart-consensus-synthese">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Consensus du débat</h3>

        {# Compteurs 3x2 par statut / 3x2 status counters #}
        {% if total_entites_toutes > 0 %}
        <div class="grid grid-cols-3 gap-2 mb-3 text-xs">
            <div class="dashboard-compteur"><span class="font-semibold">{{ compteur_nouveau }}</span> Nouveau</div>
            <div class="dashboard-compteur"><span class="font-semibold">{{ compteur_consensuel }}</span> Consensuel</div>
            <div class="dashboard-compteur"><span class="font-semibold">{{ compteur_discutable }}</span> Discutable</div>
            <div class="dashboard-compteur"><span class="font-semibold">{{ compteur_discute }}</span> Discuté</div>
            <div class="dashboard-compteur"><span class="font-semibold">{{ compteur_controverse }}</span> Controversé</div>
            <div class="dashboard-compteur"><span class="font-semibold">{{ compteur_non_pertinent }}</span> Non pertinent</div>
        </div>

        {# Barre de progression / Progress bar #}
        <div class="mb-2">
            <div class="flex items-center justify-between mb-1">
                <span class="text-xs text-slate-600">Pourcentage de consensus</span>
                <span class="text-xs font-bold {% if seuil_atteint %}text-emerald-600{% else %}text-amber-600{% endif %}">
                    {{ pourcentage_consensus }}% / {{ seuil_consensus }}%
                </span>
            </div>
            <div class="h-2 bg-slate-200 rounded-full overflow-hidden">
                <div class="h-full transition-all"
                     style="width: {{ pourcentage_consensus }}%; background-color: {% if seuil_atteint %}#10b981{% else %}#f59e0b{% endif %};">
                </div>
            </div>
        </div>

        {# Bloquantes / Blocking #}
        {% if extractions_bloquantes %}
        <p class="text-[10px] text-amber-600 mt-2">
            {{ extractions_bloquantes|length }} extraction{{ extractions_bloquantes|length|pluralize }} encore débattue{{ extractions_bloquantes|length|pluralize }}.
        </p>
        {% endif %}
        {% else %}
        <p class="text-xs text-slate-500 italic">Aucune extraction sur cette page.</p>
        {% endif %}
    </div>

    {# Infos resume / Summary info #}
    <div class="bg-slate-50 rounded-lg p-4 space-y-2 text-sm text-slate-600 mb-4">
        <div class="flex justify-between items-center">
            <span>Analyseur</span>
            <span class="font-semibold text-slate-800">
                {{ analyseur.name }}{% if analyseur.est_par_defaut %} <span class="text-blue-600">★</span>{% endif %}
            </span>
        </div>
        <div class="flex justify-between items-center">
            <span>Modèle IA</span>
            <span class="font-semibold text-slate-800">{{ modele_ia.get_display_name }}</span>
        </div>
        <div class="flex justify-between items-center">
            <span>Pièces de prompt</span>
            <span class="font-semibold text-slate-800">{{ nombre_pieces }}</span>
        </div>
        <div class="flex justify-between items-center">
            <span>Inclure texte original</span>
            <span class="font-semibold {% if analyseur.inclure_texte_original %}text-emerald-700{% else %}text-slate-400{% endif %}">
                {% if analyseur.inclure_texte_original %}✓ Oui{% else %}✗ Non{% endif %}
            </span>
        </div>
        <div class="flex justify-between items-center">
            <span>Inclure extractions et commentaires</span>
            <span class="font-semibold {% if analyseur.inclure_extractions %}text-emerald-700{% else %}text-slate-400{% endif %}">
                {% if analyseur.inclure_extractions %}✓ Oui{% else %}✗ Non{% endif %}
            </span>
        </div>
    </div>

    {# Compteurs disponibilite / Availability counters #}
    <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-xs text-slate-700">
        <div class="flex justify-between mb-1">
            <span>Extractions disponibles</span>
            <span class="font-bold">{{ nombre_extractions_disponibles }}</span>
        </div>
        <div class="flex justify-between">
            <span>Commentaires disponibles</span>
            <span class="font-bold">{{ nombre_commentaires_disponibles }}</span>
        </div>
    </div>

    {# Estimation tokens et cout / Token and cost estimate #}
    <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2 text-sm mb-4" data-testid="estimation-synthese">
        <div class="flex justify-between items-center text-amber-800">
            <span>Tokens input</span>
            <span class="font-bold text-base">~{{ nombre_tokens_input|floatformat:0 }}</span>
        </div>
        <div class="flex justify-between items-center text-amber-700">
            <span>Tokens output (~50%)</span>
            <span class="font-medium text-base">~{{ nombre_tokens_output_visible|floatformat:0 }}</span>
        </div>
        {% if nombre_tokens_thinking > 0 %}
        <div class="flex justify-between items-center text-amber-600 text-xs">
            <span>Tokens thinking (×{{ multiplicateur_thinking }})</span>
            <span class="font-medium">~{{ nombre_tokens_thinking|floatformat:0 }}</span>
        </div>
        {% endif %}
        <div class="flex justify-between items-center text-amber-900 border-t border-amber-300 pt-2 mt-2">
            <span class="font-bold">Coût estimé</span>
            <span class="font-bold text-lg">≤ {{ cout_estime_euros|floatformat:2 }} €</span>
        </div>
    </div>

    {# Bouton voir le prompt complet / View full prompt button #}
    <button type="button"
            class="btn-voir-prompt-complet w-full text-sm font-medium text-slate-600 hover:text-violet-600 hover:bg-violet-50 border border-slate-200 rounded-lg px-3 py-2.5 transition-colors mb-4"
            data-testid="btn-voir-prompt-synthese"
            data-prompt-visible="false">
        Voir le prompt complet
    </button>
    <div id="zone-prompt-complet" class="hidden mb-4">
        <div class="bg-slate-900 text-slate-100 rounded-lg p-4 max-h-[20rem] overflow-y-auto text-xs font-mono whitespace-pre-wrap leading-relaxed">{{ prompt_complet }}</div>
    </div>

    {# Gate solde credits / Credit balance gate #}
    {% if stripe_enabled and not solde_suffisant and not request.user.is_superuser %}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4" data-testid="alerte-solde-insuffisant" aria-live="polite" role="alert">
        <p class="text-sm font-bold text-red-800 mb-1">Solde insuffisant</p>
        <p class="text-sm text-red-600 mb-2">
            Votre solde ({{ solde_utilisateur_euros|floatformat:2 }} €) est insuffisant pour cette synthèse (≤ {{ cout_estime_euros|floatformat:2 }} €).
        </p>
        <a href="/credits/" hx-get="/credits/" hx-target="#zone-lecture" hx-swap="innerHTML" hx-push-url="/credits/"
           class="inline-block text-sm font-medium text-red-700 underline hover:text-red-900">Recharger mes crédits</a>
    </div>
    {% elif stripe_enabled and solde_suffisant %}
    <div class="flex justify-between items-center text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2 mb-4" data-testid="info-solde-suffisant">
        <span>Votre solde</span>
        <span class="font-bold">{{ solde_utilisateur_euros|floatformat:2 }} €</span>
    </div>
    {% endif %}

    {# Alerte de blocage si bouton_desactive / Blocking alert #}
    {% if bouton_desactive and raison_desactivation %}
    <div class="bg-amber-50 border border-amber-300 rounded-lg p-3 mb-4" data-testid="alerte-blocage-synthese" role="alert">
        <p class="text-sm text-amber-800">{{ raison_desactivation }}</p>
    </div>
    {% endif %}

    {# Bouton Lancer / Launch button #}
    <button type="button"
            data-testid="btn-lancer-synthese"
            hx-post="/lire/{{ page.pk }}/synthetiser/"
            hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'
            hx-vals='{"select-analyseur-synthese": "{{ analyseur.id }}"}'
            hx-target="#drawer-contenu"
            hx-swap="innerHTML"
            {% if bouton_desactive %}disabled aria-disabled="true"{% endif %}
            class="w-full px-5 py-4 text-base font-bold {% if bouton_desactive %}text-slate-400 bg-slate-100 border-slate-200 cursor-not-allowed{% else %}text-violet-700 bg-violet-100 hover:bg-violet-200 border border-violet-200{% endif %} rounded-xl transition-colors flex items-center justify-center gap-2">
        Lancer la synthèse
    </button>
</div>

{# OOB : titre du drawer avec bouton retour #}
{# / OOB: drawer title with back button #}
<span id="drawer-titre" hx-swap-oob="innerHTML:#drawer-titre">Synthèse délibérative</span>

<script>
(function() {
    var boutonVoirPrompt = document.querySelector('.btn-voir-prompt-complet');
    var zonePrompt = document.getElementById('zone-prompt-complet');
    if (boutonVoirPrompt && zonePrompt) {
        boutonVoirPrompt.addEventListener('click', function() {
            var estCache = zonePrompt.classList.toggle('hidden');
            boutonVoirPrompt.textContent = estCache ? 'Voir le prompt complet' : 'Masquer le prompt';
        });
    }
})();
</script>
```

- [ ] **Étape 6.2 : Relancer les tests**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.PrevisualiserSyntheseTests -v2 --keepdb
```
Attendu : tous PASS.

---

## Tâche 7 : Adaptation `synthetiser` (POST)

**Files:**
- Modify: `front/views.py` (`PageViewSet.synthetiser`)
- Test: `front/tests/test_phase29_synthese_drawer.py`

- [ ] **Étape 7.1 : Test pour le nouveau retour drawer**

Ajouter dans la classe `PrevisualiserSyntheseTests` (ou nouvelle classe) :

```python
class SynthetiserPostTests(TestCase):
    """Tests sur l'action POST synthetiser (nouveau retour drawer)."""

    def setUp(self):
        # Meme setUp que PrevisualiserSyntheseTests, factoriser si pertinent
        # / Same setUp, refactor if relevant
        self.user = User.objects.create_user("user_test", password="test1234")
        self.client.force_login(self.user)
        self.dossier = Dossier.objects.create(name="Test", owner=self.user)
        self.page = Page.objects.create(
            title="Test", dossier=self.dossier, owner=self.user,
            html_readability="<p>Test</p>", text_readability="Test text",
        )
        self.modele_ia = AIModel.objects.create(
            provider="ollama", model_name="test-model", is_active=True,
            cout_input_par_million=0.5, cout_output_par_million=1.0,
        )
        config = Configuration.get_solo()
        config.ai_active = True
        config.ai_model = self.modele_ia
        config.save()
        self.analyseur_synthese = AnalyseurSyntaxique.objects.create(
            name="Synthese delib", type_analyseur="synthetiser",
            inclure_extractions=False, inclure_texte_original=True,
            est_par_defaut=True,
        )

    def test_synthetiser_renvoie_partial_drawer_et_ouvre_drawer(self):
        # Mock la tache Celery pour ne pas reellement appeler le LLM
        # / Mock Celery task to not actually call LLM
        from unittest.mock import patch
        with patch("front.tasks.synthetiser_page_task.delay"):
            reponse = self.client.post(
                f"/lire/{self.page.pk}/synthetiser/",
                HTTP_HX_REQUEST="true",
            )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        # Le contenu doit etre le partial polling drawer
        # / Content must be the polling drawer partial
        self.assertIn("synthese_status", contenu)
        # HX-Trigger doit ouvrir le drawer
        # / HX-Trigger must open the drawer
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertIn("ouvrirDrawer", trigger)
```

- [ ] **Étape 7.2 : Lancer le test (échec attendu)**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.SynthetiserPostTests -v2 --keepdb
```

- [ ] **Étape 7.3 : Modifier le retour de `synthetiser`**

Dans `front/views.py`, dans `PageViewSet.synthetiser` (chercher le bloc `# Retourner le spinner de polling dans la zone du bouton`), remplacer :

```python
        reponse = render(request, "front/includes/synthese_en_cours.html", {
            "page": page,
        })
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {
                "message": "Synthèse lancée...",
                "icon": "info",
            },
        })
        return reponse
```

par :

```python
        # Retourner le partial polling dans le drawer + ouvrir le drawer
        # / Return polling partial in drawer + open drawer
        reponse = render(request, "front/includes/synthese_en_cours_drawer.html", {
            "page": page,
        })
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirDrawer": True,
            "showToast": {
                "message": "Synthèse lancée...",
                "icon": "info",
            },
        })
        return reponse
```

- [ ] **Étape 7.4 : Vérifier (le template n'existe pas encore — Tâche 8)**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.SynthetiserPostTests -v2 --keepdb
```
Attendu : ce test va échouer avec TemplateDoesNotExist tant qu'on n'a pas créé `synthese_en_cours_drawer.html` (Tâche 8).

---

## Tâche 8 : Partial polling drawer

**Files:**
- Create: `front/templates/front/includes/synthese_en_cours_drawer.html`

- [ ] **Étape 8.1 : Créer le template**

```html
{# Partial : polling de la synthese deliberative dans le drawer (PHASE-29) #}
{# 2 etats : en cours (avec polling 3s) ou erreur (avec retry) #}
{# Le state completed est gere directement par la vue (OOB + HX-Trigger fermerDrawer) #}
{# / Partial: deliberative synthesis polling in the drawer (PHASE-29) #}
{# / 2 states: in progress (with 3s polling) or error (with retry) #}
{# / The completed state is handled directly by the view (OOB + HX-Trigger fermerDrawer) #}

{% if erreur_synthese %}
    {# Erreur : message + bouton refaire la confirmation #}
    {# / Error: message + redo confirmation button #}
    <div class="py-8 px-4">
        <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center shrink-0">
                <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
                </svg>
            </div>
            <h2 class="text-lg font-bold text-slate-900">Erreur de synthèse</h2>
        </div>
        <p class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3 mb-4">{{ erreur_synthese }}</p>
        <button type="button"
                hx-get="/lire/{{ page.pk }}/previsualiser_synthese/"
                hx-target="#drawer-contenu"
                hx-swap="innerHTML"
                data-testid="btn-retry-synthese"
                class="w-full px-5 py-3 text-sm font-medium text-violet-700 bg-violet-100 hover:bg-violet-200 border border-violet-200 rounded-lg transition-colors">
            Refaire la confirmation
        </button>
    </div>

    {# OOB : retirer le pill spinner du switcher de versions #}
    {# / OOB: remove the version switcher spinner pill #}
    <span id="indicateur-synthese" hx-swap-oob="innerHTML:#indicateur-synthese"></span>
    <span id="drawer-titre" hx-swap-oob="innerHTML:#drawer-titre">Erreur de synthèse</span>

{% else %}
    {# En cours : spinner large + polling toutes les 3s #}
    {# / In progress: large spinner + polling every 3s #}
    <div id="drawer-contenu-inner"
         class="py-8 px-4"
         hx-get="/lire/{{ page.pk }}/synthese_status/"
         hx-trigger="every 3s"
         hx-target="#drawer-contenu"
         hx-swap="innerHTML"
         aria-live="polite">
        <div class="flex flex-col items-center text-center py-8">
            <div class="w-16 h-16 rounded-full bg-violet-100 flex items-center justify-center mb-4">
                <svg class="animate-spin w-8 h-8 text-violet-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </div>
            <h2 class="text-lg font-bold text-slate-900 mb-1">Synthèse en cours…</h2>
            <p class="text-sm text-slate-500 max-w-xs">Le LLM rédige une nouvelle version du texte intégrant le débat structuré.</p>
            <p class="text-xs text-slate-400 mt-3">Vous pouvez fermer ce panneau, la synthèse continue en arrière-plan.</p>
        </div>
    </div>

    {# OOB : pill spinner dans le switcher de versions #}
    {# / OOB: spinner pill in the version switcher #}
    <span id="indicateur-synthese" hx-swap-oob="innerHTML:#indicateur-synthese">
        <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium" style="background: #fef3c7; color: #b45309;">
            <svg class="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Synthèse…
        </span>
    </span>
    <span id="drawer-titre" hx-swap-oob="innerHTML:#drawer-titre">Synthèse en cours</span>
{% endif %}
```

- [ ] **Étape 8.2 : Relancer les tests Tâche 7**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.SynthetiserPostTests -v2 --keepdb
```
Attendu : PASS.

---

## Tâche 9 : Adaptation `synthese_status`

**Files:**
- Modify: `front/views.py` (`PageViewSet.synthese_status`)
- Create: `front/templates/front/includes/synthese_terminee_oob.html`

- [ ] **Étape 9.1 : Créer le partial OOB de fin**

`front/templates/front/includes/synthese_terminee_oob.html` :

```html
{# Partial OOB : recharge zone-lecture vers la V2 + maj du pill switcher de versions #}
{# Renvoye en reponse complete par synthese_status quand status=completed #}
{# / OOB partial: reloads zone-lecture to V2 + updates version switcher pill #}

<div id="zone-lecture" hx-swap-oob="innerHTML:#zone-lecture"
     hx-get="/lire/{{ page_synthese_id }}/"
     hx-trigger="load"
     hx-target="#zone-lecture"
     hx-swap="innerHTML"
     hx-push-url="/lire/{{ page_synthese_id }}/">
    <div class="flex items-center justify-center py-8">
        <svg class="animate-spin h-6 w-6 text-violet-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
    </div>
</div>

<span id="indicateur-synthese" hx-swap-oob="innerHTML:#indicateur-synthese">
    <a href="/lire/{{ page_synthese_id }}/"
       hx-get="/lire/{{ page_synthese_id }}/"
       hx-target="#zone-lecture"
       hx-swap="innerHTML"
       hx-push-url="true"
       class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium"
       style="background: #d1fae5; color: #047857;"
       data-testid="pill-synthese-terminee">
        <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        V{{ version_number }}
    </a>
</span>
```

- [ ] **Étape 9.2 : Test des 3 branches de `synthese_status`**

Ajouter à la classe `SynthetiserPostTests` (ou nouvelle classe `SyntheseStatusTests`) :

```python
class SyntheseStatusTests(TestCase):
    """Tests sur l'endpoint /lire/{pk}/synthese_status/."""

    def setUp(self):
        # Meme setUp que SynthetiserPostTests
        self.user = User.objects.create_user("user_test", password="test1234")
        self.client.force_login(self.user)
        self.dossier = Dossier.objects.create(name="Test", owner=self.user)
        self.page = Page.objects.create(
            title="Test", dossier=self.dossier, owner=self.user,
            html_readability="<p>Test</p>", text_readability="Test text",
        )
        self.modele_ia = AIModel.objects.create(
            provider="ollama", model_name="test-model", is_active=True,
            cout_input_par_million=0.5, cout_output_par_million=1.0,
        )

    def test_synthese_status_processing_renvoie_polling(self):
        ExtractionJob.objects.create(
            page=self.page, ai_model=self.modele_ia,
            status="processing", raw_result={"est_synthese": True},
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("synthese_status", contenu)  # polling presence
        self.assertIn("Synthèse en cours", contenu)

    def test_synthese_status_completed_renvoie_oob_et_fermer_drawer(self):
        page_v2 = Page.objects.create(
            title="V2", dossier=self.dossier, owner=self.user,
            parent_page=self.page, version_number=2,
            html_readability="<p>V2</p>", text_readability="V2 text",
        )
        ExtractionJob.objects.create(
            page=self.page, ai_model=self.modele_ia,
            status="completed",
            raw_result={
                "est_synthese": True,
                "page_synthese_id": page_v2.pk,
                "version_number": 2,
            },
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        # OOB swap de zone-lecture / OOB swap of zone-lecture
        self.assertIn("zone-lecture", contenu)
        self.assertIn("indicateur-synthese", contenu)
        # HX-Trigger fermerDrawer
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertIn("fermerDrawer", trigger)

    def test_synthese_status_error_reste_dans_drawer(self):
        ExtractionJob.objects.create(
            page=self.page, ai_model=self.modele_ia,
            status="error",
            error_message="Erreur LLM",
            raw_result={"est_synthese": True},
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Erreur LLM", contenu)
        self.assertIn("btn-retry-synthese", contenu)
```

- [ ] **Étape 9.3 : Lancer (échec attendu)**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.SyntheseStatusTests -v2 --keepdb
```

- [ ] **Étape 9.4 : Adapter `synthese_status`**

Dans `front/views.py`, remplacer la méthode `synthese_status` (chercher `def synthese_status`) entièrement par :

```python
    @action(detail=True, methods=["GET"], url_path="synthese_status")
    def synthese_status(self, request, pk=None):
        """
        Endpoint de polling HTMX pour suivre la progression d'une synthese.
        - pending/processing → re-render le partial polling drawer
        - completed → renvoie l'OOB de la V2 dans zone-lecture + HX-Trigger fermerDrawer
        - error → renvoie le partial erreur dans le drawer (avec bouton retry)
        / HTMX polling endpoint to track synthesis progress.
        """
        page = get_object_or_404(Page, pk=pk)

        # Chercher le dernier job de synthese / Find the latest synthesis job
        dernier_job_synthese = ExtractionJob.objects.filter(
            page=page,
            raw_result__contains={"est_synthese": True},
        ).order_by("-created_at").first()

        if not dernier_job_synthese:
            return render(request, "front/includes/synthese_en_cours_drawer.html", {
                "page": page,
                "erreur_synthese": "Aucun job de synthèse trouvé.",
            })

        if dernier_job_synthese.status in ("pending", "processing"):
            return render(request, "front/includes/synthese_en_cours_drawer.html", {
                "page": page,
            })

        if dernier_job_synthese.status == "completed":
            page_synthese_id = dernier_job_synthese.raw_result.get("page_synthese_id")
            version_number = dernier_job_synthese.raw_result.get("version_number", 2)
            html_oob = render_to_string(
                "front/includes/synthese_terminee_oob.html",
                {
                    "page_synthese_id": page_synthese_id,
                    "version_number": version_number,
                },
                request=request,
            )
            reponse = HttpResponse(html_oob)
            reponse["HX-Trigger"] = json.dumps({
                "fermerDrawer": True,
                "showToast": {
                    "message": "Synthèse délibérative terminée",
                    "icon": "success",
                },
            })
            return reponse

        # Status error / Error status
        return render(request, "front/includes/synthese_en_cours_drawer.html", {
            "page": page,
            "erreur_synthese": dernier_job_synthese.error_message or "Erreur inconnue",
        })
```

- [ ] **Étape 9.5 : Relancer les tests**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer.SyntheseStatusTests -v2 --keepdb
```
Attendu : 3 PASS.

---

## Tâche 10 : Listener JS `fermerDrawer`

**Files:**
- Modify: `front/static/front/js/hypostasia.js`

- [ ] **Étape 10.1 : Ajouter le listener**

Dans `front/static/front/js/hypostasia.js`, à proximité du listener `ouvrirDrawer` (chercher `addEventListener('ouvrirDrawer'`), ajouter en dessous :

```javascript
// Ecoute l'evenement HTMX custom "fermerDrawer"
// Utilise par : la fin de synthese deliberative (PHASE-29) + autres flows futurs
// / Listens for HTMX custom event "fermerDrawer"
// Used by: end of deliberative synthesis (PHASE-29) + other future flows
document.body.addEventListener('fermerDrawer', function() {
    if (window.drawerVueListe && window.drawerVueListe.fermer) {
        window.drawerVueListe.fermer();
    }
});
```

- [ ] **Étape 10.2 : Vérifier**

```bash
docker exec hypostasia_web uv run python manage.py check
```
Test visuel manuel à effectuer avec le navigateur après la Tâche 13.

---

## Tâche 11 : Adaptation bouton dashboard

**Files:**
- Modify: `front/templates/front/includes/dashboard_consensus.html` (lignes ~95-113)

- [ ] **Étape 11.1 : Remplacer le `onclick` par `hx-get`**

Dans `dashboard_consensus.html`, remplacer le bloc `{# Bouton synthese... #}` (lignes ~92-113) par :

```html
        {# Bouton synthese — ouvre la confirmation dans le drawer (PHASE-29) #}
        {# / Synthesis button — opens confirmation in the drawer (PHASE-29) #}
        <div class="mt-4" id="zone-btn-synthese">
            <button class="btn-synthese {% if not seuil_atteint %}btn-synthese-avertissement{% endif %}"
                    data-testid="btn-lancer-synthese"
                    hx-get="/lire/{{ page.pk }}/previsualiser_synthese/"
                    hx-target="#drawer-contenu"
                    hx-swap="innerHTML"
                    hx-on::after-request="if(window.dashboardConsensus){window.dashboardConsensus.fermer();}">
                Lancer la synthèse
            </button>
            {% if not seuil_atteint %}
            <p class="text-[10px] text-amber-600 mt-1 text-center">
                Seuil non atteint ({{ pourcentage_consensus }}% / {{ seuil_consensus }}%).
                Continuez la curation ou lancez quand même depuis le drawer.
            </p>
            {% endif %}
        </div>
```

L'événement `ouvrirDrawer` est déclenché par la réponse de `previsualiser_synthese` ? **Non** — il faut l'ajouter. Dans `previsualiser_synthese`, ajouter au retour final :

```python
        reponse = render(request, "front/includes/confirmation_synthese.html", {...})
        reponse["HX-Trigger"] = "ouvrirDrawer"
        return reponse
```

- [ ] **Étape 11.2 : Adapter `previsualiser_synthese` pour déclencher `ouvrirDrawer`**

Dans `front/views.py`, dans `previsualiser_synthese` (Tâche 5.3), modifier le `return render(...)` final pour ajouter le `HX-Trigger` :

```python
        reponse = render(request, "front/includes/confirmation_synthese.html", {...})
        reponse["HX-Trigger"] = "ouvrirDrawer"
        return reponse
```

(Garder les retours d'erreur 400 tels quels, sans `ouvrirDrawer`.)

- [ ] **Étape 11.3 : Vérifier que la fonction JS `dashboardConsensus.fermer()` existe**

```bash
grep -n "dashboardConsensus" front/static/front/js/dashboard_consensus.js | head -5
```
Vérifier que `window.dashboardConsensus.fermer` existe ou ajuster l'attribut `hx-on::after-request`.

- [ ] **Étape 11.4 : Vérifier**

```bash
docker exec hypostasia_web uv run python manage.py check
```

---

## Tâche 12 : Suppression du modal JS

**Files:**
- Modify: `front/static/front/js/dashboard_consensus.js` (suppression de `ouvrirModaleSynthese` et `fermerModaleSynthese`)

- [ ] **Étape 12.1 : Vérifier qu'aucune autre référence n'existe**

```bash
grep -rn "ouvrirModaleSynthese\|fermerModaleSynthese" --include="*.js" --include="*.html" --include="*.py"
```
Si des références existent ailleurs que dans `dashboard_consensus.js` et `dashboard_consensus.html` (déjà modifié à la Tâche 11), les corriger d'abord.

- [ ] **Étape 12.2 : Supprimer les fonctions du JS**

Dans `front/static/front/js/dashboard_consensus.js`, supprimer les blocs des lignes ~200-286 (les deux fonctions et le commentaire JSDoc associé). S'assurer de ne pas casser le reste du fichier (le `})()` final doit rester si présent).

- [ ] **Étape 12.3 : Vérifier**

```bash
docker exec hypostasia_web uv run python manage.py check
```

- [ ] **Étape 12.4 : Vérifier qu'il ne reste pas de référence à `synthese_en_cours.html`**

```bash
grep -rn "synthese_en_cours\.html\|synthese_en_cours\b" --include="*.py" --include="*.html"
```

Si le template `synthese_en_cours.html` n'est plus référencé nulle part → le supprimer :
```bash
rm front/templates/front/includes/synthese_en_cours.html
```
(S'il est encore référencé, le laisser et noter la dette technique.)

---

## Tâche 13 : Mise à jour fixtures + DB

**Files:**
- Modify: `front/management/commands/charger_fixtures_demo.py`

- [ ] **Étape 13.1 : Mettre à jour les fixtures**

Dans `charger_fixtures_demo.py`, ajouter `est_par_defaut=True` aux trois analyseurs créés :

Pour Hypostasia (chercher `name="Hypostasia"`) :
```python
defaults={
    "type_analyseur": "analyser",
    "is_active": True,
    "inclure_extractions": False,
    "inclure_texte_original": False,
    "est_par_defaut": True,  # AJOUT
},
```

Pour FALC :
```python
defaults={
    "type_analyseur": "reformuler",
    "is_active": True,
    "est_par_defaut": True,  # AJOUT
},
```

Pour Synthèse délibérative :
```python
defaults={
    "type_analyseur": "synthetiser",
    "is_active": True,
    "inclure_extractions": True,
    "inclure_texte_original": True,
    "est_par_defaut": True,  # AJOUT
    "description": (...),
},
```

- [ ] **Étape 13.2 : Mettre à jour la base existante**

```bash
docker exec hypostasia_web uv run python manage.py shell -c "
from hypostasis_extractor.models import AnalyseurSyntaxique
# Marquer le premier de chaque type comme defaut
# / Mark first of each type as default
for type_ana in ['analyser', 'reformuler', 'synthetiser']:
    premier = AnalyseurSyntaxique.objects.filter(type_analyseur=type_ana).order_by('pk').first()
    if premier:
        premier.est_par_defaut = True
        premier.save()
        print(f'{type_ana}: {premier.name} marque par defaut')
"
```

---

## Tâche 14 : Test final + check global

- [ ] **Étape 14.1 : Lancer toute la suite de tests Phase 29**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase29_synthese_drawer -v2 --keepdb
```
Attendu : tous PASS (au moins 15 tests).

- [ ] **Étape 14.2 : Lancer les tests phase 28 (synthese existante) pour vérifier qu'on n'a pas cassé**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase28_light front.tests.test_phases.PhasesSyntheseTests -v2 --keepdb 2>&1 | tail -30
```
Attendu : tous PASS, ou alors clarifier les échecs (peut-être adaptations attendues sur l'ancien retour `synthese_en_cours.html`).

- [ ] **Étape 14.3 : Check Django global**

```bash
docker exec hypostasia_web uv run python manage.py check
```
Attendu : 0 issues.

- [ ] **Étape 14.4 : Test manuel via le navigateur**

Demander au mainteneur de tester manuellement :
1. Cliquer « Lancer la synthèse » dans le dashboard → drawer s'ouvre avec confirmation.
2. Cliquer « Voir le prompt complet » → zone scrollable s'affiche.
3. Cliquer « Lancer la synthèse » dans le drawer → spinner dans le drawer.
4. Attendre fin → drawer se ferme, zone-lecture montre la V2.
5. Cocher `est_par_defaut` sur un analyseur → toast info si un autre était default.
6. Sur un analyseur synthese avec les 2 bool à False, cliquer « Lancer la synthèse » → bouton désactivé + message « Configurez l'analyseur ».
7. Sur un analyseur synthese avec `inclure_extractions=True` mais page sans analyse → bouton désactivé + message « Lancez d'abord une analyse ».

---

## Self-review du plan

**1. Spec coverage** : toutes les sections de la spec ont une tâche correspondante.
- Modèle `est_par_defaut` → Tâche 1
- Migration → Tâche 1.4
- Serializer + toast → Tâche 2
- Toggle editor + badges → Tâche 3
- Helper `_calculer_consensus` → Tâche 4
- Endpoint `previsualiser_synthese` → Tâche 5
- Template `confirmation_synthese.html` → Tâche 6
- Adaptation `synthetiser` → Tâche 7
- Partial polling drawer → Tâche 8
- Adaptation `synthese_status` + partial OOB → Tâche 9
- Listener JS `fermerDrawer` → Tâche 10
- Bouton dashboard → Tâche 11
- Suppression modal JS → Tâche 12
- Fixtures + DB → Tâche 13

**2. Placeholder scan** : pas de TBD/TODO. Tous les blocs de code sont complets.

**3. Type consistency** : noms cohérents entre tâches (`analyseur_synthese`, `dernier_job_analyse`, `consensus`, etc.).

**4. Pas de E2E** : conforme à la décision « pas de E2E ».
