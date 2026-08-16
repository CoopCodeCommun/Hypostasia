# PHASE-26h — Credits prepays et paiement Stripe

**Complexite** : L | **Mode** : `/plan` d'abord | **Prerequis** : PHASE-25 (users), PHASE-26g (estimation cout), PHASE-26b (couts reels — au moins partiel)

---

## 1. Contexte

Le PLAN identifie un impense majeur : **qui paie les appels LLM ?** (PLAN.md, ligne 126).
Le modele retenu est le **credit prepaye** : l'utilisateur recharge son compte via Stripe,
chaque analyse debite son solde en fonction du cout reel. Si le solde est insuffisant,
l'analyse est bloquee et l'utilisateur est invite a recharger.

**Pourquoi les credits prepays** :
- Zero risque financier pour l'operateur (pas de facturation a posteriori, pas d'impayes)
- Compatible avec le modele multi-tenant et le modele auto-heberge (on peut desactiver Stripe en self-hosted)
- Transparent pour l'utilisateur : il voit son solde, le cout estime, et decide
- Simple a implementer vs un abonnement avec quotas

**Pourquoi a ce moment du developpement** :
- Les users existent (PHASE-25)
- L'estimation de cout est fiable (PHASE-26g)
- Le tracking des couts reels est en cours (PHASE-26b)
- C'est le dernier verrou avant la mise en prod

---

## 2. Objectifs precis

### Etape H.1 — Modele de donnees : solde et transactions

- [ ] Modele `CreditAccount` (1:1 avec User) :
  - `solde_euros` : DecimalField(max_digits=10, decimal_places=4, default=0)
  - `created_at`, `updated_at`
- [ ] Modele `CreditTransaction` (journal de toutes les operations) :
  - `user` : FK User
  - `type` : choices (RECHARGE, DEBIT_ANALYSE, AJUSTEMENT, REMBOURSEMENT)
  - `montant_euros` : DecimalField (positif pour recharge, negatif pour debit)
  - `solde_apres` : DecimalField (solde apres l'operation — audit trail)
  - `description` : TextField (ex: "Analyse Gemini 2.5 Flash — page 42")
  - `stripe_payment_intent_id` : CharField (nullable, pour les recharges)
  - `extraction_job` : FK ExtractionJob (nullable, pour les debits d'analyse)
  - `created_at`
- [ ] Signal ou methode `debiter(user, montant, description, job=None)` qui :
  - Verifie le solde suffisant (raise `SoldeInsuffisant` sinon)
  - Cree la transaction
  - Met a jour le solde en atomique (`select_for_update`)
- [ ] Methode `crediter(user, montant, description, stripe_pi=None)` (idem, en positif)
- [ ] Les superusers peuvent ajuster manuellement le solde (type AJUSTEMENT)

### Etape H.2 — Integration Stripe Checkout

- [ ] Installer `stripe` (pip) — pas de SDK Django specifique, le SDK Python suffit
- [ ] Settings : `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` (via env vars)
- [ ] `CreditViewSet` dans `front/views.py` (ou `front/views/credits.py`) :
  - `solde()` : affiche le solde actuel + historique recent (partial HTMX)
  - `recharger()` : affiche le formulaire de recharge (montants predefinis : 5, 10, 25, 50 EUR + montant libre)
  - `creer_checkout()` : cree une Stripe Checkout Session, redirige vers Stripe
  - `succes()` : page de retour apres paiement reussi (attend le webhook pour crediter)
  - `annule()` : page de retour si l'utilisateur annule
- [ ] Webhook Stripe (`/stripe/webhook/`) :
  - Ecoute `checkout.session.completed`
  - Verifie la signature du webhook (`stripe.Webhook.construct_event`)
  - Credite le compte utilisateur via `crediter()`
  - Idempotent : ignore les doublons (check `stripe_payment_intent_id` unique)
- [ ] Le webhook est **exempt CSRF** (c'est Stripe qui appelle, pas le navigateur)
- [ ] En dev/test : utiliser `stripe listen --forward-to localhost:8123/stripe/webhook/` pour tester

### Etape H.3 — Gate avant analyse : verification du solde

- [ ] Dans le flow d'analyse (drawer etat 2 — confirmation), **avant** le bouton "Lancer" :
  - Afficher le cout estime (deja fait via PHASE-26g)
  - Afficher le solde actuel de l'utilisateur
  - Si `solde >= cout_estime` : bouton "Lancer l'analyse" actif
  - Si `solde < cout_estime` : bouton "Lancer" desactive + message "Solde insuffisant" + lien "Recharger"
  - Le lien "Recharger" ouvre la modale/page de recharge Stripe
- [ ] Cote serveur : double verification au moment du lancement effectif (`previsualiser_analyse` → `lancer_analyse`) :
  - Si le solde a change entre-temps (race condition), bloquer et renvoyer un message
- [ ] Apres analyse terminee : debit du cout **reel** (pas l'estime) :
  - Le debit se fait dans la task Celery, apres reception de l'usage API
  - Si le cout reel > solde restant : l'analyse a deja tourne (on ne peut pas annuler), donc on debite quand meme (solde negatif tolere dans ce cas precis, avec un warning)
  - Alternative : bloquer le solde (reserve) au lancement, ajuster apres

### Etape H.4 — UX du solde dans l'interface

- [ ] **Indicateur de solde dans la navbar** : petit badge avec le solde en euros (visible sur toutes les pages)
- [ ] **Page "Mon compte > Credits"** :
  - Solde actuel
  - Historique des transactions (tableau pagine)
  - Bouton "Recharger"
  - Graphique simple : consommation des 30 derniers jours (optionnel, peut etre reporte)
- [ ] **Notification de solde bas** : quand le solde passe sous un seuil (ex: 1 EUR), afficher un bandeau d'avertissement

### Etape H.5 — Admin et superuser

- [ ] Vue admin pour voir les soldes de tous les utilisateurs
- [ ] Action admin : ajuster le solde d'un utilisateur (avec motif obligatoire)
- [ ] Les superusers peuvent lancer des analyses **sans verification de solde** (usage interne/dev)
- [ ] Dashboard admin : total des credits vendus, total consomme, solde global

### Etape H.6 — Mode self-hosted (desactivation Stripe)

- [ ] Setting `STRIPE_ENABLED = True/False` (default True)
- [ ] Si `STRIPE_ENABLED = False` :
  - Pas de verification de solde avant analyse
  - Pas d'affichage du solde dans la navbar
  - Pas de page de recharge
  - Les analyses sont illimitees (l'organisation gere ses propres cles API)
- [ ] Ce mode est celui utilise en dev local (`STRIPE_ENABLED=False` dans `.env`)

---

## 3. Fichiers a creer / modifier

### Nouveaux fichiers
- `core/models_credits.py` — modeles `CreditAccount`, `CreditTransaction`
- `front/views/credits.py` — `CreditViewSet` (recharge, solde, historique)
- `front/stripe_webhook.py` — vue webhook Stripe (exempt CSRF)
- `front/templates/front/includes/credits_solde.html` — partial solde navbar
- `front/templates/front/includes/credits_recharger.html` — formulaire recharge
- `front/templates/front/includes/credits_historique.html` — historique transactions
- `front/templates/front/includes/credits_solde_insuffisant.html` — message gate
- `front/serializers_credits.py` — serializers pour recharge (montant)

### Fichiers a modifier
- `core/models.py` — import des nouveaux modeles
- `front/views.py` ou `front/urls.py` — enregistrement du CreditViewSet + route webhook
- `front/templates/front/base.html` — badge solde dans la navbar
- `front/templates/front/includes/confirmation_analyse.html` — gate solde + cout estime
- `front/tasks.py` — debit du cout reel apres analyse terminee
- `hypostasia/settings.py` — settings Stripe (`STRIPE_*`, `STRIPE_ENABLED`)
- `hypostasia/urls.py` — route webhook Stripe
- `requirements.txt` / `pyproject.toml` — ajout `stripe`

---

## 4. Decisions d'architecture

### Pourquoi Stripe Checkout (pas Stripe Elements)
- Checkout est une page hebergee par Stripe → zero gestion de formulaire de carte cote serveur
- Conformite PCI-DSS automatique (on ne touche jamais aux numeros de carte)
- Support Apple Pay, Google Pay, SEPA, etc. sans code supplementaire
- Plus simple a implementer et a maintenir

### Pourquoi un journal de transactions (pas juste un solde)
- Audit trail complet : on peut reconstituer le solde a tout moment
- Debug facile : si un utilisateur conteste un debit, on voit exactement quoi/quand/combien
- RGPD : export possible du journal de transactions
- Comptabilite : le journal sert de base pour la facturation

### Pourquoi debiter le cout reel (pas l'estime)
- L'estimation est une approximation (overhead prompt, thinking tokens)
- Debiter l'estime puis ajuster = 2 transactions, plus complexe
- Debiter le reel = 1 seule transaction, plus simple
- Le risque de depassement est gere par la tolerance de solde negatif (rare, et le cout reel est generalement proche de l'estime)

### Alternative envisagee : reservation de solde
- Au lancement : `reserve = cout_estime * 1.2` (marge 20%), solde reduit
- Apres analyse : ajustement au cout reel, liberation de la reserve excedentaire
- Plus propre mais plus complexe — a implementer en V2 si les depassements sont frequents

---

## 5. Criteres de validation

- [ ] Un utilisateur peut recharger son compte via Stripe Checkout
- [ ] Le solde est mis a jour apres paiement (via webhook, pas via la page de retour)
- [ ] L'historique des transactions est visible et correct
- [ ] Une analyse est bloquee si le solde est insuffisant
- [ ] Le cout reel est debite apres chaque analyse terminee
- [ ] Le badge solde s'affiche dans la navbar
- [ ] En mode `STRIPE_ENABLED=False`, tout fonctionne sans verification de solde
- [ ] Le webhook est idempotent (re-jouer un event ne cree pas de doublon)
- [ ] `uv run python manage.py check` passe
- [ ] `uv run python manage.py migrate` passe

---

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8123/

1. **Verifier le badge solde dans la navbar**
   - **Attendu** : le solde s'affiche (0.00 EUR pour un nouveau user)
2. **Cliquer sur "Recharger"**
   - **Attendu** : formulaire avec montants predefinis (5, 10, 25, 50 EUR)
3. **Choisir un montant et payer (Stripe test mode)**
   - **Attendu** : redirection vers Stripe Checkout (carte test 4242...), retour sur la page succes
4. **Verifier que le solde est mis a jour**
   - **Attendu** : le solde reflete le montant recharge (apres webhook)
5. **Lancer une analyse sur une page**
   - **Attendu** : le cout estime ET le solde sont affiches dans la confirmation
6. **Avec un solde insuffisant, tenter une analyse**
   - **Attendu** : bouton "Lancer" desactive, message "Solde insuffisant", lien "Recharger"
7. **Verifier l'historique des transactions**
   - **Attendu** : recharges et debits visibles avec dates et montants

---

## 6. Securite

- **Webhook** : toujours verifier la signature Stripe (`stripe.Webhook.construct_event`) — ne jamais faire confiance au body sans verification
- **CSRF** : le webhook est exempt CSRF (decorateur `@csrf_exempt`), mais protege par la signature Stripe
- **Concurrence** : utiliser `select_for_update()` sur le `CreditAccount` pour eviter les debits concurrents
- **Pas de donnees de carte** : Stripe Checkout gere tout, on ne stocke que le `payment_intent_id`
- **Env vars** : les cles Stripe ne sont JAMAIS dans le code, toujours via `os.environ` / `.env`
