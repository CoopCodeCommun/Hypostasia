# Plan A.4 — Retrait Stripe / crédits prépayés (PHASE-26h)

> **Pour les workers agentiques :** ce plan suit la skill `superpowers:writing-plans`. Les étapes utilisent la syntaxe checkbox `- [ ]` pour le suivi. Voir [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md) pour le contexte.

**Goal :** retirer entièrement la couche commerciale Stripe / crédits prépayés (PHASE-26h) — 3 fichiers Python entiers, 5 templates, 4 modèles Django, 1 migration de suppression, 12 classes de tests Django + 1 fichier E2E entier, 4 variables d'env, 2 routes URL, gates avant analyse, débits dans Celery, badge solde dans la toolbar, crédits bienvenue à l'inscription.

**Architecture :**
- Suppression complète des modèles `CreditAccount`, `CreditTransaction`, `TypeTransaction` (TextChoices), `SoldeInsuffisantError` (Exception) dans `core/models.py`
- Migration auto-générée `core/migrations/0030_remove_credit_models.py` (`DeleteModel` + cleanup constraints)
- Suppression de 3 fichiers Python : `front/services_stripe.py`, `front/views_credits.py`, `front/views_stripe_webhook.py`
- Suppression de 5 templates `front/templates/front/includes/credits_*.html`
- Suppression du fichier `front/context_processors.py` entier (ne contient que `solde_credits()`) + retrait de l'entrée dans `settings.TEMPLATES.OPTIONS.context_processors`
- Retrait des 2 routes : `path('webhooks/stripe/', stripe_webhook, ...)` dans `hypostasia/urls.py` et `router.register(r"credits", CreditViewSet, ...)` dans `front/urls.py`
- Retrait des refs UI dans `base.html` (badge solde + lien Mes credits + 3 includes conditionnels), `confirmation_analyse.html` (gate solde + bouton recharger), `confirmation_synthese.html` (gate solde + bouton recharger)
- Retrait du code Python conditionnel à `STRIPE_ENABLED` dans : `views.py` (2 gates), `views_auth.py` (crédits bienvenue 3 EUR), `tasks.py` (débits audio + synthèse)
- Retrait des 5 variables `STRIPE_*` dans `hypostasia/settings.py` et 4 dans `.env.example`
- Retrait des 12 classes `Phase26h*` dans `test_phases.py` + section `DebitCreditsSyntheseTest` dans `test_phase28_light.py`
- Suppression entière de `front/tests/e2e/test_19_credits.py`

**Tech stack :** Django 6 + DRF + HTMX + Tailwind subset + PostgreSQL. Stack-ccc / skill djc.

**Hors périmètre :**
- Bibliothèque analyseurs → A.5
- Calcul de coût LLM sur les analyseurs (champ `cout_estime_centimes` ou similaire sur `Analyseur`/`ExtractionJob`) : à conserver, sert à informer l'utilisateur indépendamment de la facturation
- Le `.env` local de Jonas (non versionné) — il nettoiera lui-même si nécessaire

**Préférences user :**
- Aucune commande git automatique (commits gérés par Jonas)
- Pas de `Co-Authored-By` dans les messages de commit
- Tests Django dans Docker via `docker exec hypostasia_web uv run python manage.py test --noinput`
- Migrations Django à appliquer dans Docker

---

## Décisions actées (pas de question à valider)

1. **Suppression complète vs flag `STRIPE_ENABLED=False`** : suppression complète conformément à la spec YAGNI Q2. Pas de code dormant.
2. **Tabula rasa pour les comptes en DB** : la migration `DeleteModel` détruit les tables `core_creditaccount` et `core_credittransaction`. Aucune migration de données. Les 3 EUR offerts à des comptes existants sont perdus (acceptable car SaaS en alpha).
3. **Crédits bienvenue à l'inscription (`views_auth.py:129-137`)** : retiré entièrement.
4. **Calcul de coût LLM** : conservé indépendamment (sert à informer l'utilisateur, pas à facturer).
5. **Migration 0030** : auto-générée par `makemigrations` après suppression des modèles. Renommée pour lisibilité après inspection.

---

## Cartographie des changements

### Fichiers supprimés (9)

| Fichier | Rôle |
|---|---|
| `front/services_stripe.py` | 1 fonction `traiter_paiement_stripe(identifiant_session_stripe)` |
| `front/views_credits.py` | 1 ViewSet `CreditViewSet` (4 actions) + 1 serializer `CreerCheckoutSerializer` |
| `front/views_stripe_webhook.py` | 1 fonction `stripe_webhook(request)` (POST raw, hors DRF) |
| `front/context_processors.py` | 1 fonction `solde_credits(request)` — fichier ne contient que ça |
| `front/templates/front/includes/credits_annule.html` | Page annulation paiement Stripe |
| `front/templates/front/includes/credits_page.html` | Page principale "Mes crédits" |
| `front/templates/front/includes/credits_recharger.html` | Formulaire recharge |
| `front/templates/front/includes/credits_solde_badge.html` | Badge solde (utilisé via include) |
| `front/templates/front/includes/credits_succes.html` | Page succès paiement Stripe |
| `front/tests/e2e/test_19_credits.py` | 196 lignes de tests E2E credits/Stripe |

### Fichiers créés (1)

| Fichier | Rôle |
|---|---|
| `core/migrations/0030_remove_credit_models.py` | Migration auto-générée par `makemigrations`, `DeleteModel` sur `CreditTransaction` et `CreditAccount` |

### Fichiers modifiés (10)

| Fichier | Changement |
|---|---|
| `core/models.py` | Retrait `SoldeInsuffisantError` (l. 1254-1259), `TypeTransaction` (l. 1261-1268), `CreditAccount` (l. 1271-1364), `CreditTransaction` (l. 1367-1418) — bloc complet ~165 lignes |
| `hypostasia/settings.py` | Retrait des 5 vars `STRIPE_*` (l. ~205-212) + retrait ligne 95 `'front.context_processors.solde_credits'` |
| `hypostasia/urls.py` | Retrait import `from front.views_stripe_webhook import stripe_webhook` (l. 22) + route `path('webhooks/stripe/', ...)` (l. 30) |
| `front/urls.py` | Retrait import `from .views_credits import CreditViewSet` (l. 9) + `router.register(r"credits", ...)` (l. 30) |
| `front/views.py` | Retrait 2 blocs gate avant analyse (l. ~1962-2011 et l. ~2045-2053) |
| `front/views_auth.py` | Retrait bloc crédits bienvenue 3 EUR (l. 126-138) |
| `front/tasks.py` | Retrait 2 blocs débit (audio l. 644-672, synthèse l. 1259-1288) |
| `front/templates/front/base.html` | Retrait badge solde toolbar (l. 145-160), lien Mes credits dans menu (l. 178-185), 3 includes conditionnels `credits_*_preloaded` (l. 312-317) |
| `front/templates/front/includes/confirmation_analyse.html` | Retrait gate solde + bouton recharger + classes disabled conditionnelles (l. 114-172) |
| `front/templates/front/includes/confirmation_synthese.html` | Retrait gate solde + bouton recharger (l. 170-180) |
| `front/tests/test_phases.py` | Retrait 12 classes `Phase26h*` (l. 8347-8611 environ) + commentaire de section |
| `front/tests/test_phase28_light.py` | Retrait sections `DebitCreditsSyntheseTest` et `DebitCreditsTranscriptionAudioTest` (l. ~675-800+) |
| `.env.example` | Retrait des 4 vars `STRIPE_*` |

### Cas particuliers

**`STRIPE_MONTANTS_RECHARGE = [5, 10, 20, 50]`** dans settings : utilisé uniquement par `views_credits.py:55`. À supprimer en même temps.

**Migration 0026** : a une dépendance déclarée `('core', '0025_credit_account_and_credit_transaction')`. C'est une dépendance d'historique — elle reste valide (la migration 0025 existe toujours, on n'y touche pas). La nouvelle migration 0030 dépendra de la dernière migration courante (0029_remove_dossiersuivi).

**Renumérotation Escape dans `keyboard.js`** : déjà fait en A.3 step 3.4. Pas concerné par A.4.

**`onboarding_vide.html`** : aucune ref `credit`/`stripe` (vérifié par scan). Pas concerné.

---

## Tâches

### Task 1 : Retrait routes & 3 fichiers Python entiers

**Files:**
- Modify: `hypostasia/urls.py` (l. 22 + l. 30)
- Modify: `front/urls.py` (l. 9 + l. 30)
- Delete: `front/services_stripe.py`
- Delete: `front/views_credits.py`
- Delete: `front/views_stripe_webhook.py`

- [ ] **Step 1.1 — Modifier `hypostasia/urls.py`**

```bash
Read /home/jonas/Gits/Hypostasia/hypostasia/urls.py limit=40
```

Retirer ligne 22 :
```python
from front.views_stripe_webhook import stripe_webhook
```

Retirer ligne 30 (avec son commentaire l. 28-29) :
```python
    # / Stripe webhook — BEFORE front.urls (raw POST, not DRF)
    path('webhooks/stripe/', stripe_webhook, name='stripe-webhook'),
```

- [ ] **Step 1.2 — Modifier `front/urls.py`**

Retirer ligne 9 :
```python
from .views_credits import CreditViewSet
```

Retirer ligne 30 :
```python
router.register(r"credits", CreditViewSet, basename="credit")
```

- [ ] **Step 1.3 — Supprimer les 3 fichiers Python**

```bash
rm /home/jonas/Gits/Hypostasia/front/services_stripe.py \
   /home/jonas/Gits/Hypostasia/front/views_credits.py \
   /home/jonas/Gits/Hypostasia/front/views_stripe_webhook.py
```

- [ ] **Step 1.4 — Vérifier que Django démarre**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -5
```

Attendu : `System check identified no issues (0 silenced).`

Si erreur : un autre fichier importe peut-être `services_stripe`, `views_credits`, ou `views_stripe_webhook`. Vérifier :
```bash
rg "from front\.services_stripe|from front\.views_credits|from front\.views_stripe_webhook|from \.services_stripe|from \.views_credits|from \.views_stripe_webhook" /home/jonas/Gits/Hypostasia/
```
Attendu : 0 résultat.

- [ ] **Step 1.5 — Commit suggéré**

```
A.4 (1/10) — Retrait routes Stripe + 3 fichiers Python entiers

Supprime services_stripe.py, views_credits.py et
views_stripe_webhook.py. Retire les routes /webhooks/stripe/
(hypostasia/urls.py) et /credits/ (front/urls.py). Premier commit
du retrait Stripe (session A.4 de la revue YAGNI 2026-05-01).
```

---

### Task 2 : Retrait des 5 templates `credits_*.html` + refs `base.html`

**Files:**
- Delete: 5 templates `front/templates/front/includes/credits_*.html`
- Modify: `front/templates/front/base.html` (3 zones : badge toolbar, menu sidebar, includes conditionnels)

- [ ] **Step 2.1 — Supprimer les 5 templates**

```bash
rm /home/jonas/Gits/Hypostasia/front/templates/front/includes/credits_annule.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/credits_page.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/credits_recharger.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/credits_solde_badge.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/credits_succes.html
```

- [ ] **Step 2.2 — `base.html` : retirer le badge solde toolbar (l. 145-160)**

```bash
Read /home/jonas/Gits/Hypostasia/front/templates/front/base.html offset=140 limit=25
```

Identifier le bloc complet (commence par `{# Badge solde credits (PHASE-26h) ... #}` et se termine par `</a>` ou `{% endif %}`). Le retirer entièrement.

- [ ] **Step 2.3 — `base.html` : retirer le lien "Mes credits" dans le menu (l. 178-185)**

Identifier le bloc :
```html
                    {% if stripe_enabled %}
                    <a href="/credits/"
                       hx-get="/credits/"
                       ...
                       data-testid="btn-mes-credits">Mes credits</a>
                    {% endif %}
```
Le retirer entièrement.

- [ ] **Step 2.4 — `base.html` : retirer les 3 includes conditionnels `credits_*_preloaded` (l. 312-317)**

```bash
Read /home/jonas/Gits/Hypostasia/front/templates/front/base.html offset=308 limit=15
```

Identifier le bloc :
```html
            {% elif credits_page_preloaded %}
                {% include "front/includes/credits_page.html" %}
            {% elif credits_succes_preloaded %}
                {% include "front/includes/credits_succes.html" %}
            {% elif credits_annule_preloaded %}
                {% include "front/includes/credits_annule.html" %}
```
Le retirer entièrement (6 lignes).

- [ ] **Step 2.5 — Vérifier l'absence de ref résiduelle**

```bash
rg "credits_|/credits/|stripe_enabled|solde_credits" /home/jonas/Gits/Hypostasia/front/templates/front/base.html
```
Attendu : 0 résultat.

- [ ] **Step 2.6 — Django check + test serveur**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```
Attendu : OK.

- [ ] **Step 2.7 — Commit suggéré**

```
A.4 (2/10) — Retrait templates credits_*.html + refs base.html

Supprime les 5 templates credits_annule, credits_page,
credits_recharger, credits_solde_badge, credits_succes. Retire
le badge solde toolbar, le lien "Mes credits" du menu sidebar
et les 3 includes conditionnels credits_*_preloaded de base.html.
```

---

### Task 3 : Retrait gates solde dans `confirmation_analyse.html` + `confirmation_synthese.html`

**Files:**
- Modify: `front/templates/front/includes/confirmation_analyse.html` (l. 114-172)
- Modify: `front/templates/front/includes/confirmation_synthese.html` (l. 170-180)

- [ ] **Step 3.1 — Lire `confirmation_analyse.html` zones concernées**

```bash
Read /home/jonas/Gits/Hypostasia/front/templates/front/includes/confirmation_analyse.html offset=110 limit=70
```

Identifier 2 zones :
1. **Bloc gate solde** (l. 114-136 environ) :
   ```html
   {# Gate solde credits (PHASE-26h) — alerte si solde insuffisant #}
   {% if stripe_enabled and not solde_suffisant and not request.user.is_superuser %}
       ... alerte + bouton recharger ...
   {% elif stripe_enabled and solde_suffisant %}
       ... message solde OK ...
   {% endif %}
   ```
2. **Classes disabled conditionnelles sur le bouton submit** (l. 171-172 environ) :
   ```html
   {% if stripe_enabled and not solde_suffisant and not request.user.is_superuser %}disabled aria-disabled="true"{% endif %}
   class="... {% if stripe_enabled and not solde_suffisant and not request.user.is_superuser %}text-slate-400 bg-slate-100 ...{% else %}text-indigo-700 bg-indigo-100 ...{% endif %} ..."
   ```

- [ ] **Step 3.2 — Retirer le bloc gate complet (l. 114-136)**

Utiliser `Edit` avec `old_string` = le bloc complet et `new_string` = "" (ou ajustement).

- [ ] **Step 3.3 — Simplifier les classes du bouton submit (l. 171-172)**

Avant :
```html
                {% if stripe_enabled and not solde_suffisant and not request.user.is_superuser %}disabled aria-disabled="true"{% endif %}
                class="flex-1 px-5 py-4 text-base font-bold {% if stripe_enabled and not solde_suffisant and not request.user.is_superuser %}text-slate-400 bg-slate-100 border-slate-200 cursor-not-allowed{% else %}text-indigo-700 bg-indigo-100 hover:bg-indigo-200 border border-indigo-200{% endif %} rounded-xl transition-colors flex items-center justify-center gap-2">
```
Après :
```html
                class="flex-1 px-5 py-4 text-base font-bold text-indigo-700 bg-indigo-100 hover:bg-indigo-200 border border-indigo-200 rounded-xl transition-colors flex items-center justify-center gap-2">
```

- [ ] **Step 3.4 — Lire `confirmation_synthese.html` zone concernée**

```bash
Read /home/jonas/Gits/Hypostasia/front/templates/front/includes/confirmation_synthese.html offset=165 limit=25
```

Identifier le bloc :
```html
{# Gate solde credits / Credit balance gate #}
{% if stripe_enabled and not solde_suffisant and not request.user.is_superuser %}
    ... alerte + bouton recharger ...
{% elif stripe_enabled and solde_suffisant %}
    ... message solde OK ...
{% endif %}
```

- [ ] **Step 3.5 — Retirer le bloc gate dans `confirmation_synthese.html`**

Edit : supprimer le bloc complet.

- [ ] **Step 3.6 — Vérifier l'absence de ref résiduelle**

```bash
rg "stripe_enabled|solde_credits|solde_suffisant|/credits/" /home/jonas/Gits/Hypostasia/front/templates/front/includes/confirmation_analyse.html /home/jonas/Gits/Hypostasia/front/templates/front/includes/confirmation_synthese.html
```
Attendu : 0 résultat.

- [ ] **Step 3.7 — Commit suggéré**

```
A.4 (3/10) — Retrait gates solde dans confirmation analyse + synthese

Retire les blocs gate solde et boutons "Recharger mes credits"
des templates confirmation_analyse.html et confirmation_synthese.html.
Le bouton submit retrouve son style normal (plus de classes disabled
conditionnelles).
```

---

### Task 4 : Retrait `front/context_processors.py` + entrée settings

**Files:**
- Delete: `front/context_processors.py`
- Modify: `hypostasia/settings.py` (l. 95)

- [ ] **Step 4.1 — Vérifier que `solde_credits` est la seule fonction du fichier**

```bash
rg -n "^def |^class " /home/jonas/Gits/Hypostasia/front/context_processors.py
```
Attendu : `def solde_credits` seulement.

- [ ] **Step 4.2 — Supprimer le fichier**

```bash
rm /home/jonas/Gits/Hypostasia/front/context_processors.py
```

- [ ] **Step 4.3 — Modifier `settings.py` : retirer l'entrée context_processor**

```bash
Read /home/jonas/Gits/Hypostasia/hypostasia/settings.py offset=85 limit=15
```

Identifier la liste `context_processors` (l. 91-96 environ). Retirer la ligne :
```python
                'front.context_processors.solde_credits',
```

- [ ] **Step 4.4 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```
Attendu : OK.

- [ ] **Step 4.5 — Commit suggéré**

```
A.4 (4/10) — Retrait context_processor solde_credits

Supprime front/context_processors.py (ne contenait que la fonction
solde_credits) et retire l'entree
'front.context_processors.solde_credits' de la liste
TEMPLATES.OPTIONS.context_processors dans settings.py.
```

---

### Task 5 : Retrait crédits bienvenue dans `views_auth.py`

**Files:**
- Modify: `front/views_auth.py` (l. 126-138 environ)

- [ ] **Step 5.1 — Lire le contexte**

```bash
Read /home/jonas/Gits/Hypostasia/front/views_auth.py offset=120 limit=25
```

- [ ] **Step 5.2 — Retirer le bloc crédits bienvenue**

Identifier le bloc (à confirmer en lecture, structure attendue) :
```python
        # Offrir un solde de bienvenue si Stripe est active (PHASE-26h)
        # / Give welcome credits if Stripe is enabled (PHASE-26h)
        from django.conf import settings
        if settings.STRIPE_ENABLED:
            from core.models import CreditAccount
            compte_nouveau = CreditAccount.get_ou_creer(nouvel_utilisateur)
            compte_nouveau.crediter(
                ...
            )
            logger.info("Credits bienvenue 3 EUR credites pour %s", nouvel_utilisateur.username)
```
Le retirer entièrement.

À l'exécution : adapter le pattern exact en lisant le code.

- [ ] **Step 5.3 — Vérifier qu'aucune ref CreditAccount/STRIPE ne subsiste**

```bash
rg "STRIPE|CreditAccount|credit" /home/jonas/Gits/Hypostasia/front/views_auth.py
```
Attendu : 0 résultat.

- [ ] **Step 5.4 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 5.5 — Commit suggéré**

```
A.4 (5/10) — Retrait credits bienvenue a l'inscription

Supprime le bloc qui creditait 3 EUR a chaque nouvel utilisateur
(views_auth.py l. 126-138). Plus de "Credits bienvenue" dans les
logs d'inscription.
```

---

### Task 6 : Retrait débits dans `tasks.py` (transcription audio + synthèse)

**Files:**
- Modify: `front/tasks.py` (l. 644-672 audio, l. 1259-1288 synthèse)

- [ ] **Step 6.1 — Lire le bloc audio (l. 644-672)**

```bash
Read /home/jonas/Gits/Hypostasia/front/tasks.py offset=640 limit=40
```

Identifier le bloc complet `if django_settings.STRIPE_ENABLED and config_transcription:` jusqu'à la fin du `except Exception as erreur_credits:` correspondant.

- [ ] **Step 6.2 — Retirer le bloc débit audio**

Utiliser `Edit` avec `old_string` = le bloc complet et `new_string` = "" (ou ajustement minimal pour conserver l'indentation).

- [ ] **Step 6.3 — Lire le bloc synthèse (l. 1259-1288)**

```bash
Read /home/jonas/Gits/Hypostasia/front/tasks.py offset=1255 limit=40
```

Identifier le bloc `if django_settings.STRIPE_ENABLED:` ... `except Exception as erreur_credits:`.

- [ ] **Step 6.4 — Retirer le bloc débit synthèse**

Edit : supprimer le bloc complet.

- [ ] **Step 6.5 — Vérifier l'absence de ref résiduelle**

```bash
rg "STRIPE|CreditAccount|SoldeInsuffisantError|crediter|debiter" /home/jonas/Gits/Hypostasia/front/tasks.py
```
Attendu : 0 résultat.

- [ ] **Step 6.6 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 6.7 — Commit suggéré**

```
A.4 (6/10) — Retrait debits credits dans Celery tasks

Supprime les blocs de debit du compte credits dans
transcrire_audio_task (l. 644-672) et synthetiser_page_task
(l. 1259-1288). Les analyses LLM ne consomment plus de credits.
```

---

### Task 7 : Retrait gates avant analyse dans `views.py`

**Files:**
- Modify: `front/views.py` (l. 1962-2011 et l. 2045-2053)

- [ ] **Step 7.1 — Lire le bloc gate previsualisation (l. 1962-2011)**

```bash
Read /home/jonas/Gits/Hypostasia/front/views.py offset=1958 limit=60
```

Identifier la zone qui calcule `contexte_credits` (probablement avec `if settings.STRIPE_ENABLED and utilisateur_authentifie and not request.user.is_superuser:`) et l'expansion `**contexte_credits` dans le render.

- [ ] **Step 7.2 — Retirer le calcul de `contexte_credits`**

Supprimer le bloc :
```python
        # Gate solde credits (PHASE-26h) — verifier si le solde est suffisant
        # Si l'utilisateur n'a pas de compte credits, on n'affiche pas la gate
        # / Credit balance gate (PHASE-26h) — check if balance is sufficient
        # / If user has no credit account, don't show the gate.
        contexte_credits = {}

        if settings.STRIPE_ENABLED and utilisateur_authentifie and not request.user.is_superuser:
            from core.models import CreditAccount
            compte_existant = CreditAccount.objects.filter(user=request.user).first()
            ...
                contexte_credits = {
                    ...
                }
```

Et retirer l'expansion `**contexte_credits,` du render.

À l'exécution : utiliser le pattern exact lu en step 7.1.

- [ ] **Step 7.3 — Lire le bloc gate avant lancement (l. 2045-2053)**

```bash
Read /home/jonas/Gits/Hypostasia/front/views.py offset=2040 limit=30
```

- [ ] **Step 7.4 — Retirer le bloc gate avant lancement**

Identifier le bloc `if settings.STRIPE_ENABLED and not request.user.is_superuser:` qui vérifie le solde avant de lancer la tâche Celery. Le retirer entièrement.

- [ ] **Step 7.5 — Vérifier l'absence de ref résiduelle**

```bash
rg "STRIPE|CreditAccount|SoldeInsuffisantError|contexte_credits|solde_suffisant" /home/jonas/Gits/Hypostasia/front/views.py
```
Attendu : 0 résultat.

- [ ] **Step 7.6 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 7.7 — Commit suggéré**

```
A.4 (7/10) — Retrait gates solde avant analyse dans views.py

Supprime les 2 blocs de gate solde dans views.py :
- Calcul de contexte_credits avant render previsualisation (l. 1962-2011)
- Gate avant lancement Celery task analyser_page_task (l. 2045-2053)
Les utilisateurs non-superuser peuvent lancer une analyse sans
verification de solde.
```

---

### Task 8 : Retrait variables `STRIPE_*` dans `settings.py` + `.env.example`

**Files:**
- Modify: `hypostasia/settings.py` (l. ~205-212)
- Modify: `.env.example`

- [ ] **Step 8.1 — Lire les variables STRIPE dans settings.py**

```bash
rg -n "STRIPE" /home/jonas/Gits/Hypostasia/hypostasia/settings.py
```

- [ ] **Step 8.2 — Retirer les 5 variables STRIPE_* dans settings.py**

Supprimer les lignes :
```python
STRIPE_ENABLED = os.environ.get("STRIPE_ENABLED", "false").lower() in ("true", "1", "yes")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_MONTANTS_RECHARGE = [5, 10, 20, 50]
```

Si elles sont précédées par un commentaire de section "# === Stripe ===", retirer le commentaire aussi.

- [ ] **Step 8.3 — Retirer les 4 variables STRIPE_* dans `.env.example`**

```bash
Read /home/jonas/Gits/Hypostasia/.env.example
```

Identifier et supprimer les lignes :
```
STRIPE_ENABLED=false
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

Et le commentaire de section associé s'il existe.

- [ ] **Step 8.4 — Vérifier l'absence de ref résiduelle**

```bash
rg "STRIPE" /home/jonas/Gits/Hypostasia/hypostasia/settings.py /home/jonas/Gits/Hypostasia/.env.example
```
Attendu : 0 résultat.

- [ ] **Step 8.5 — Vérifier que la dépendance `stripe` peut être retirée du `pyproject.toml`**

```bash
rg "^stripe" /home/jonas/Gits/Hypostasia/pyproject.toml
```

Si la lib `stripe` y figure, vérifier qu'elle n'est plus importée nulle part :
```bash
rg "^import stripe|^from stripe" /home/jonas/Gits/Hypostasia/ --type py -g '!PLAN/**'
```
Attendu : 0 résultat (les 3 fichiers qui importaient `stripe` ont été supprimés en Task 1).

Si la lib peut être retirée, ajouter une note dans le commit suggéré pour que Jonas la retire de `pyproject.toml` + `uv sync` plus tard.

- [ ] **Step 8.6 — Commit suggéré**

```
A.4 (8/10) — Retrait variables d'env STRIPE_* (settings + .env.example)

Supprime les 5 variables STRIPE_* dans settings.py
(STRIPE_ENABLED, STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY,
STRIPE_WEBHOOK_SECRET, STRIPE_MONTANTS_RECHARGE) et les 4
correspondantes dans .env.example.

NOTE : la dependance `stripe` dans pyproject.toml peut etre
retiree (plus aucun import dans le code) — geste a faire avec
`uv remove stripe && uv sync` quand Jonas le decide.
```

---

### Task 9 : Retrait modèles + migration

**Files:**
- Modify: `core/models.py` (retrait `SoldeInsuffisantError`, `TypeTransaction`, `CreditAccount`, `CreditTransaction`)
- Create: `core/migrations/0030_remove_credit_models.py` (auto-généré)

- [ ] **Step 9.1 — Lire le bloc complet à supprimer dans models.py (l. 1250-1418)**

```bash
Read /home/jonas/Gits/Hypostasia/core/models.py offset=1248 limit=175
```

- [ ] **Step 9.2 — Lire le commentaire de section qui précède (s'il existe)**

```bash
Read /home/jonas/Gits/Hypostasia/core/models.py offset=1240 limit=10
```

S'il y a un commentaire de section "# Crédits prépayés..." juste avant `class SoldeInsuffisantError`, le supprimer aussi.

- [ ] **Step 9.3 — Supprimer le bloc complet via Edit**

Utiliser `Edit` avec `old_string` = du début du commentaire de section (ou de `class SoldeInsuffisantError(Exception):`) jusqu'à la fin de `class CreditTransaction(...)`. `new_string` = "" (ou minimal pour préserver la structure).

À l'exécution : si le bloc est trop gros pour un seul Edit, le faire en 2-3 passes (Exception, TextChoices, CreditAccount, CreditTransaction).

- [ ] **Step 9.4 — Auto-générer la migration**

```bash
docker exec hypostasia_web uv run python manage.py makemigrations core 2>&1 | tail -10
```

Attendu : `Migrations for 'core': core/migrations/0030_*.py - Delete model CreditTransaction - Delete model CreditAccount`.

- [ ] **Step 9.5 — Inspecter la migration générée**

```bash
ls /home/jonas/Gits/Hypostasia/core/migrations/0030_*.py
cat /home/jonas/Gits/Hypostasia/core/migrations/0030_*.py
```

Vérifier :
- 2 opérations `DeleteModel` (CreditTransaction puis CreditAccount, dans cet ordre car `CreditTransaction` a une FK vers `CreditAccount`)
- 1 opération `RemoveField` éventuellement sur `ExtractionJob.transactions_credits` (related_name reverse, à voir)
- Pas de modification accidentelle d'autres modèles

Si tout est propre, renommer pour lisibilité :
```bash
mv /home/jonas/Gits/Hypostasia/core/migrations/0030_*.py /home/jonas/Gits/Hypostasia/core/migrations/0030_remove_credit_models.py
```

- [ ] **Step 9.6 — Appliquer la migration dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py migrate core 2>&1 | tail -5
```

Attendu : `Applying core.0030_remove_credit_models... OK`

- [ ] **Step 9.7 — Vérifier qu'aucune ref résiduelle Python ne subsiste hors tests + migration historique**

```bash
rg "CreditAccount|CreditTransaction|SoldeInsuffisantError|TypeTransaction|crediter|debiter" /home/jonas/Gits/Hypostasia/ \
   --type py \
   -g '!core/migrations/0025_*' \
   -g '!core/migrations/0030_*' \
   -g '!PLAN/**' 2>&1 | head -10
```
Attendu : seulement dans les tests Django (test_phases.py et test_phase28_light.py — Tasks 10 et 11) et dans test_19_credits.py (Task 11).

- [ ] **Step 9.8 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 9.9 — Commit suggéré**

```
A.4 (9/10) — Retrait modeles credits + migration 0030

Supprime les classes SoldeInsuffisantError, TypeTransaction,
CreditAccount, CreditTransaction dans core/models.py et applique
la migration 0030_remove_credit_models (DeleteModel x2). La
migration 0025 (creation) est conservee intacte car deja appliquee
en prod ; 0030 efface uniquement les tables.
```

---

### Task 10 : Retrait tests Django Phase26h + section dans test_phase28_light

**Files:**
- Modify: `front/tests/test_phases.py` (l. 8347-8611 environ — 12 classes)
- Modify: `front/tests/test_phase28_light.py` (sections DebitCredits*)

- [ ] **Step 10.1 — Identifier les bornes des classes Phase26h**

```bash
rg -n "^class Phase26h|^class Phase26[a-g]|^class Phase27" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py | head -20
```

Confirmer la dernière classe Phase26h et la première classe à conserver après (Phase27 ou autre).

- [ ] **Step 10.2 — Lire le commentaire de section et la fin de la dernière classe**

```bash
Read /home/jonas/Gits/Hypostasia/front/tests/test_phases.py offset=8340 limit=12
Read /home/jonas/Gits/Hypostasia/front/tests/test_phases.py offset=<fin_phase26h> limit=15
```

Identifier les lignes exactes du commentaire `# PHASE-26h ...` et de la première ligne après le bloc Phase26h.

- [ ] **Step 10.3 — Supprimer le bloc Phase26h via sed**

```bash
sed -i '<début>,<fin>d' /home/jonas/Gits/Hypostasia/front/tests/test_phases.py
```

À l'exécution : utiliser les valeurs exactes lues en step 10.2.

- [ ] **Step 10.4 — Vérifier l'absence de ref résiduelle**

```bash
rg "Phase26h|CreditAccount|CreditTransaction|SoldeInsuffisantError|crediter|debiter|STRIPE|stripe_enabled" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py | head -10
```
Attendu : 0 résultat.

- [ ] **Step 10.5 — Identifier les sections à retirer dans `test_phase28_light.py`**

```bash
rg -n "^class |^@override_settings.*STRIPE" /home/jonas/Gits/Hypostasia/front/tests/test_phase28_light.py | head -20
```

Identifier les classes `DebitCreditsSyntheseTest`, `DebitCreditsTranscriptionAudioTest` (et toute autre classe avec `@override_settings(STRIPE_ENABLED=True)`).

- [ ] **Step 10.6 — Supprimer ces classes dans `test_phase28_light.py`**

Utiliser `Edit` ou `sed` selon la complexité. Vérifier qu'aucune classe non liée au crédit ne soit affectée.

- [ ] **Step 10.7 — Vérifier l'absence de ref résiduelle**

```bash
rg "STRIPE|CreditAccount|CreditTransaction|crediter|debiter|stripe" /home/jonas/Gits/Hypostasia/front/tests/test_phase28_light.py
```
Attendu : 0 résultat.

- [ ] **Step 10.8 — Lancer les tests Django dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phases front.tests.test_phase28_light --noinput -v 0 2>&1 | tail -5
```
Attendu : tous les tests restants passent. Aucune erreur d'import.

- [ ] **Step 10.9 — Commit suggéré**

```
A.4 (10a/10) — Retrait tests Django Phase26h + sections test_phase28_light

Supprime les 12 classes Phase26h* dans test_phases.py et les
sections DebitCreditsSyntheseTest / DebitCreditsTranscriptionAudioTest
dans test_phase28_light.py.
```

---

### Task 11 : Retrait test E2E `test_19_credits.py`

**Files:**
- Delete: `front/tests/e2e/test_19_credits.py`
- Modify: `front/tests/e2e/__init__.py` (retrait de l'import)

- [ ] **Step 11.1 — Vérifier que test_19_credits est importé dans __init__.py**

```bash
rg "test_19_credits" /home/jonas/Gits/Hypostasia/front/tests/e2e/__init__.py
```

- [ ] **Step 11.2 — Supprimer le fichier**

```bash
rm /home/jonas/Gits/Hypostasia/front/tests/e2e/test_19_credits.py
```

- [ ] **Step 11.3 — Retirer la ligne d'import dans __init__.py**

```bash
Read /home/jonas/Gits/Hypostasia/front/tests/e2e/__init__.py
```

Retirer la ligne :
```python
from front.tests.e2e.test_19_credits import *  # noqa: F401,F403
```

- [ ] **Step 11.4 — Vérifier qu'aucune autre ref ne subsiste**

```bash
rg "test_19_credits" /home/jonas/Gits/Hypostasia/
```
Attendu : 0 résultat (sauf dans PLAN/ et CHANGELOG.md).

- [ ] **Step 11.5 — Commit suggéré**

```
A.4 (10b/10) — Retrait test E2E test_19_credits.py

Supprime le fichier de tests E2E credits/Stripe (196 lignes) et
retire l'import correspondant dans front/tests/e2e/__init__.py.
```

---

### Task 12 : Vérification finale

**Files:** aucun (verification uniquement)

- [ ] **Step 12.1 — Grep complet**

```bash
rg "STRIPE|stripe_enabled|stripe_est_active|CreditAccount|CreditTransaction|SoldeInsuffisantError|TypeTransaction|crediter|debiter|services_stripe|views_credits|views_stripe_webhook|credits_solde_badge|credits_page|credits_succes|credits_annule|credits_recharger|/credits/|webhooks/stripe|Phase26h|stripe_payment_intent|montants_recharge" /home/jonas/Gits/Hypostasia/ \
   --type-add 'web:*.{py,html,js,css,env,example,toml,yml,yaml,sh}' -t web \
   -g '!PLAN/**' \
   -g '!CHANGELOG.md' \
   -g '!core/migrations/0025_*' \
   -g '!core/migrations/0030_*' \
   -g '!*.lock' 2>&1
```
Attendu : 0 résultat (sauf éventuellement le mot "stripe" dans des contextes non liés — ex. CSS `linear-gradient stripes`, mais non détecté par les patterns ci-dessus car en minuscule sans contexte).

Note : `import stripe` dans `pyproject.toml` peut subsister si la lib n'a pas été retirée — c'est OK pour ce plan, à scoper séparément.

- [ ] **Step 12.2 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 12.3 — Lancer la suite de tests Django dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phases front.tests.test_phase28_light front.tests.test_phase29_normalize front.tests.test_phase29_synthese_drawer front.tests.test_phase27a front.tests.test_phase27b front.tests.test_analyse_drawer_unifie front.tests.test_langextract_overrides --noinput -v 0 2>&1 | tail -5
```
Attendu : tous les tests passent (baisse vs A.3 d'environ ~25-30 tests Phase26h et debit retirés).

- [ ] **Step 12.4 — Test manuel UI complet (Firefox)**

1. `docker exec hypostasia_web uv run python manage.py runserver 0.0.0.0:8123` (ou via Traefik)
2. **Connexion** : se connecter avec un compte existant
3. **Inscription** : créer un nouvel utilisateur — vérifier dans les logs serveur qu'il n'y a PLUS la ligne `Credits bienvenue 3 EUR credites pour ...`
4. **Toolbar desktop** :
   - Plus de badge solde (ex: "0,00 €")
   - Pas de bouton "Mes credits" dans le menu sidebar
5. **Page de lecture → analyser** :
   - Cliquer sur "Lancer l'analyse" → vérifier qu'il n'y a plus le bandeau gate "Solde insuffisant"
   - L'analyse se lance directement (passe par la clé OpenRouter de l'utilisateur)
6. **Page de synthèse** :
   - Idem : pas de gate solde
7. **URLs explicitement testées** :
   - `http://localhost:8123/credits/` doit renvoyer 404 (route retirée)
   - `http://localhost:8123/webhooks/stripe/` doit renvoyer 404
8. **Console JS** : aucune erreur `is not a function`

- [ ] **Step 12.5 — Vérifier qu'aucune table credit_account / credit_transaction ne subsiste en DB**

```bash
docker exec hypostasia_web uv run python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"SELECT to_regclass('core_creditaccount'), to_regclass('core_credittransaction')\"); print(cur.fetchone())"
```
Attendu : `(None, None)` après migration 0030 appliquée.

- [ ] **Step 12.6 — Pas de commit final si la vérification est OK**

Si tout est propre, pas de commit additionnel. Le commit cleanup éventuel concerne seulement des oublis trouvés en step 12.1.

---

## Sortie attendue à la fin de la session A.4

- 9 fichiers supprimés (3 Python entiers + 5 templates + 1 fichier E2E)
- 1 fichier créé (migration 0030)
- 12 fichiers modifiés
- 12 classes Django supprimées (Phase26h*) + 2 classes (DebitCredits*) dans test_phase28_light
- ~10 commits proposés à Jonas
- Plus aucun code Stripe / crédits en production
- Inscription : plus de crédits offerts
- Lancer une analyse : plus de gate de solde
- Migration 0030 appliquée : tables `core_creditaccount` et `core_credittransaction` supprimées de la DB

## Risques identifiés et mitigation

| Risque | Mitigation |
|---|---|
| Comptes credits avec solde > 0 perdus | Acceptable (SaaS en alpha, décision spec) |
| Migration 0030 génère des opérations imprévues | Step 9.5 inspecte avant d'appliquer |
| Tests d'autres phases utilisent indirectement CreditAccount | Step 12.1 fait un grep exhaustif ; si un test casse, retirer dans la task concernée |
| Lib `stripe` reste dans `pyproject.toml` | Step 8.5 vérifie + note pour Jonas, hors périmètre stricto sensu |
| Refs `solde_credits_euros` ou `stripe_enabled` dans des templates oubliés | Step 12.1 grep large + step 12.4 test manuel UI |
| Migration 0030 ne s'applique pas (DB pas accessible localement) | Step 9.6 utilise Docker (DB postgres dispo) |
| `extraction_job` FK reverse `transactions_credits` sur ExtractionJob | Disparaît automatiquement avec DeleteModel(CreditTransaction). À confirmer en step 9.5 |

## Auto-revue

- ✅ Toutes les sections de la spec YAGNI 2026-05-01 §Q2 (Stripe) sont couvertes
- ✅ Tous les fichiers du scan ripgrep ont une task associée
- ✅ Aucun placeholder, aucun "TODO"
- ✅ Chemins exacts pour chaque modification
- ✅ Ordre des tasks respecte la dépendance (Tasks 1-7 retirent les usages, Task 9 retire les modèles en dernier — sinon Django plante à l'import)
- ✅ Tous les commits suggérés respectent la préférence "pas de Co-Authored-By"
- ✅ Aucune commande git automatique
- ✅ Migration générée dans Docker (DB accessible)
- ✅ Onboarding `H` et `L` déjà retirés (A.1/A.2/A.3) — pas de double traitement

## Références

- Spec validée : [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md) §Q2
- Plans précédents : [PLAN/A.1-retrait-explorer.md](A.1-retrait-explorer.md), [PLAN/A.2-retrait-heatmap.md](A.2-retrait-heatmap.md), [PLAN/A.3-retrait-mode-focus.md](A.3-retrait-mode-focus.md)
- Skill obligatoire pour exécution : `superpowers:executing-plans`
