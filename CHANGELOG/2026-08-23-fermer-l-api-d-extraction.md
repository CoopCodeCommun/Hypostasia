# Fermer l'API d'extraction / Closing the extraction API

**Date :** 2026-08-23
**Migration :** Non

## Résumé / Summary

**Quoi / What :** les trois ViewSets JSON de `hypostasis_extractor/views.py` —
`ExtractionJobViewSet`, `ExtractedEntityViewSet`, `ExtractionExampleViewSet` — portaient
`permission_classes = [permissions.AllowAny]` **sans aucun filtre de propriétaire**.
Chacune de leurs méthodes appelle désormais une garde explicite qui répond **404**.
/ The three JSON ViewSets were `AllowAny` with no owner filter; every method now calls
an explicit gate that answers 404.

**Pourquoi / Why :** sans le moindre cookie, `/api/extraction-jobs/` rendait les 37 jobs
de la base, `/api/extraction-jobs/4/` **17 487 octets** (le prompt entier et 25 extractions
verbatim) et `/api/extracted-entities/` **375 122 octets** — toutes les extractions de
l'instance, carnets privés compris. C'était routé dans les **deux** conf nginx, donc
indépendant de `DEBUG`.
/ Without any cookie, the API served every job, prompt and verbatim extraction of the
instance, in both nginx topologies.

### La règle appliquée / The rule applied

| Vue | Ce qu'elle exige maintenant |
|---|---|
| `ExtractionJobViewSet.list` / `.retrieve` | être connecté, et la note du job doit être dans `notes_visibles_par(user)` |
| `ExtractionJobViewSet.create` | le droit d'**écrire** sur la note visée (`_utilisateur_peut_ecrire_page`) |
| `ExtractedEntityViewSet.list` / `.retrieve` | être connecté, et la note du job porteur doit être dans le périmètre |
| `ExtractedEntityViewSet.validate` | le droit d'**écrire** sur la note du job |
| `ExtractionExampleViewSet.list` / `.retrieve` / `.create` | être **staff** — un exemple few-shot n'appartient à aucune note |

**Deux couches — et la première seulement est plus stricte que les écrans.** Un
**anonyme** obtient 404 partout, y compris sur une note rangée dans un carnet public :
ces endpoints rendent le prompt et le `raw_result`, pas l'écran de lecture. Un
**visiteur connecté**, lui, suit exactement le périmètre du projet
(`notes_visibles_par`, SPEC-corpus § 5.2) — donc **un carnet public ouvre bien cette
API à tout compte**, et une note orpheline sans propriétaire reste lisible par tout
authentifié (cas legacy). C'est ce que demandait la note d'origine (« lisibles par qui
a accès à la note qui les porte »), mais ce n'est pas la fermeture la plus stricte
possible : c'est une décision de gouvernance à confirmer, et deux tests la
**documentent** au lieu de la subir.
/ Only the anonymous layer is stricter than the screens: a signed-in visitor follows
the project's own scope, so a public notebook does open this API.

Aucun consommateur n'est cassé : `rg` ne trouve aucun appel XHR à ces trois endpoints
dans `front/static/front/js/`, `staticfiles/` ni `extension/` (qui n'appelle que
`/api/pages/*`), et aucun test existant ne les utilisait. Une seule occurrence dans un
gabarit : `includes/job_row.html:18` porte un `<a href="/api/extraction-jobs/{{ job.id }}/">`
— un lien, pas un appel, dans un partial que seule la branche `HX-Request` de `create`
rend, et qui n'a lui-même aucun appelant.

**La doctrine du 404, tenue par construction.** Le périmètre est posé **dans le
queryset**, jamais dans un `if` qui suivrait la lecture. Et **aucune de ces vues
n'appelle plus `get_object_or_404`** : il lève `Http404("No <Modèle> matches the given
query.")`, dont DRF fait un corps `{"detail": "No ExtractionJob matches…"}`, quand une
garde lève un `Http404` nu — corps `{"detail": "Not found."}`. **Deux corps différents
suffisent à distinguer un refus d'une absence.** Tout passe donc par un seul helper,
`_objet_du_perimetre_ou_404`, qui traite de la même façon les trois cas : objet absent,
objet hors périmètre, identifiant qui n'est même pas un nombre. Cinq tests comparent les
`content` octet à octet — y compris le cas le plus fin, un visiteur qui **peut lire**
l'extraction mais **pas l'écrire**.
/ No view calls get_object_or_404 anymore: its message differs from a bare Http404, and
that difference alone is an oracle. One helper covers missing, out-of-scope, and
non-numeric ids; five tests compare bodies byte for byte.

**Et `create` résout la note AVANT de valider.** Le champ `page` d'un `ModelSerializer`
voit toutes les notes : laisser le serializer trancher rendait **400** « Invalid pk »
pour une note inexistante et **404** pour une note interdite — la différence entre ces
deux réponses énumère les notes de l'instance, une par une.
/ create resolves the note before validation, or the two answers enumerate every note.

### La porte d'à côté : les exemples few-shot par le détail d'un job

Fermer `/api/extraction-examples/` ne suffisait pas. `ExtractionJobDetailSerializer`
rendait `example_text` **et** `example_extractions` de chaque exemple attaché au job,
sans aucun contrôle — et `ExtractionJobCreateSerializer` acceptait une liste
`example_ids` d'entiers arbitraires. En un seul POST sur **sa propre note**, un
utilisateur ordinaire attachait n'importe quel exemple de l'instance et en lisait le
contenu dans la réponse 201.

Deux corrections, dans le serializer :

- `get_examples` rend `[]` à qui n'est pas staff — le `request` arrive par le `context`
  que les deux vues passent désormais ;
- `validate_example_ids` refuse l'attachement à un non-staff, en **400** explicite.

**L'effet réel aujourd'hui était nul** : la table est vide sur cette base, et son seul
créateur (`seed_prompts.py`) n'est appelé ni par `bin/`, ni par le `Makefile`, ni par
`docker-compose.yml`. C'était néanmoins une garantie fausse — celle que le tableau
ci-dessus annonce.
/ Closing the examples endpoint was not enough: a job's detail served their full
content, and create accepted arbitrary example ids. Both are now staff-gated.

**`permission_classes` reste `AllowAny`, et c'est voulu :** une classe de permission DRF
répond 401 ou 403 — donc dit que l'objet existe. Un commentaire le dit au-dessus de
chacune des trois déclarations, pour que la ligne ne se lise pas comme un oubli.
/ The DRF gate stays open on purpose: a permission class would answer 401/403.

### La limite de la doctrine : le CSRF passe AVANT les gardes

**Sur les trois méthodes d'écriture** — `create` d'un job, `validate` d'une extraction,
`create` d'un exemple — un visiteur muni d'un cookie de session mais **sans jeton CSRF**
reçoit **403 « CSRF Failed »**, jamais 404. La garde n'est même pas atteinte.

Le `@method_decorator(csrf_exempt, name='dispatch')` posé sur ces ViewSets **n'y change
rien** : c'est `SessionAuthentication.enforce_csrf` qui fabrique son propre `CSRFCheck` et
l'appelle avec `callback=None`, si bien que le `csrf_exempt` du callback n'est jamais lu.
Et cela se produit dans `APIView.initial()`, **avant** le corps de la vue.

**Ce n'est pas un oracle** : la réponse ne dépend d'aucun identifiant, elle est la même
pour une note qui existe et pour une note qui n'existe pas. Mais la phrase « un refus rend
404, jamais 403 » ne vaut donc que pour les **lectures**, et c'est dit ici pour que
personne ne la croie universelle.

**Aucun des 42 tests ne peut le voir** : le client de test Django pose
`_dont_enforce_csrf_checks`. C'est un fait de production, établi par lecture du code de
DRF et de Django.
/ On the three write methods, a session cookie without a CSRF token yields 403 before any
gate. Not an oracle — the answer never depends on an identifier — but the 404 doctrine
covers reads only.

### `SidebarViewSet` (`core/views.py`) — vérifié, c'est voulu

Il reste `AllowAny`, à raison : l'extension navigateur l'interroge parfois sans session.
Il **ne fuit pas** — sa recherche est déjà bornée par `notes_visibles_par(request.user)`,
et sa réponse ne distingue jamais « rien ici » de « pas pour toi ». Un test de
non-régression le verrouille. Mesuré en anonyme : « Aucune analyse trouvee »
(sans accent — c'est la chaîne réelle du code).
/ Verified: deliberate, already scoped, and locked by a regression test.

> **La taille de sa réponse n'est pas un chiffre comparable** : le corps interpole
> l'URL reçue (`f"URL: {url_recue or 'Inconnue'}"`, dans `SidebarViewSet.list`), donc il
> varie avec la requête. `core/views.py` n'est pas dans ce diff : la ligne « après »
> du tableau dit *inchangé*, et non un nombre d'octets qui laisserait croire à une
> modification.

### Mesure avant / après — anonyme, `Host: beta.hypostasia.org`

Requêtes lancées depuis le conteneur `nginx` vers `web:8000`, sans aucun cookie.

| Endpoint | Avant (23 août) | Après |
|---|---|---|
| `/api/extraction-jobs/` | 200 — 11 107 o | **404** |
| `/api/extraction-jobs/4/` | 200 — 17 487 o | **404** |
| `/api/extracted-entities/` | 200 — 375 122 o | **404** |
| `/api/extraction-examples/` | 200 — `[]` | **404** |
| `/api/analyseurs/` | 403 | 403 *(inchangé — voir ci-dessous)* |
| `/api/pages/` | 401 | 401 |
| `/api/sidebar/?url=…` | 200 — 176 o | 200 — **inchangé** |

**Ce qui n'est PAS fait :** `/api/analyseurs/` répond toujours **403** là où la doctrine
demande un 404. C'est le second écart signalé par la note du 23 août, hors des quatre
points de sa section « Ce qui est voulu ». **Et il coûte plus cher qu'il n'en a l'air**,
parce que le 403 vient de deux endroits distincts : pour un **anonyme**, de
le `permission_classes = [permissions.IsAuthenticated]` d'`AnalyseurSyntaxiqueViewSet` — DRF lève
`NotAuthenticated` puis rétrograde en 403, faute d'`authenticate_header` sur
`SessionAuthentication` ; pour un **connecté non-staff**, de `_exiger_staff`, qui rend un
partial HTML destiné à HTMX. Corriger l'un sans l'autre ne changerait pas le 403 mesuré,
et toucher `_exiger_staff` touche l'écran d'édition des analyseurs.
/ Not done, and costlier than it looks: the 403 comes from two different places.

### Ce que la suite a révélé : `is_staff` n'est pas `is_superuser`

Un test écrit à l'aveugle supposait qu'un membre du staff lit le job d'une note privée
d'autrui. **Il rend 404, et c'est juste** : `notes_visibles_par` n'a de contournement
que pour le **superuser** (`core/services/corpus.py:250`). `is_staff` ouvre la
configuration du moteur — analyseurs, exemples few-shot — et **jamais le corpus des
autres**. Les deux droits se cumulent, ils ne se remplacent pas : le staff lit le
contenu des exemples de **ses propres** jobs. Deux tests écrivent la règle dans les
deux sens, pour qu'elle ne soit pas redécouverte de la même façon.
/ Being staff grants no read access to other people's notes: only the superuser has
that bypass. The two rights stack.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/views.py` | cinq gardes neuves (`_exiger_un_visiteur_connecte`, `_exiger_un_membre_du_staff`, `_exiger_le_droit_d_ecrire_sur_la_note`, `_objet_du_perimetre_ou_404`, `_note_visee_ou_404`) ; périmètre posé dans les querysets des quatre méthodes de lecture qui portent sur des notes ; droit d'écriture sur `create` et `validate` |
| `hypostasis_extractor/serializers.py` | `get_examples` ne rend le contenu des exemples qu'au staff ; `validate_example_ids` refuse l'attachement à un non-staff |
| `hypostasis_extractor/tests/test_l_api_d_extraction_est_fermee.py` | **neuf** — l'anonyme, le tiers connecté, le carnet public, le propriétaire, le staff, l'indiscernabilité refus/absence, la porte des exemples, l'identifiant non numérique, et la non-régression de la sidebar |
| `hypostasis_extractor/README.md` | tableau des endpoints : les droits, et retrait de `run`/`visualization`, supprimées le 17 août 2026 |
| `PLAN/TODO/2026-08-23-l-api-des-jobs-est-ouverte-a-tous.md` | supprimé — le code porte la note |

---

## Comment tester (à la main) / Manual test

### Test 1 — la fuite est fermée, en anonyme

Depuis l'hôte, sans aucun cookie, avec le `Host` de production :

```bash
for chemin in /api/extraction-jobs/ /api/extraction-jobs/4/ \
              /api/extracted-entities/ /api/extraction-examples/; do
  docker compose exec -T nginx sh -c \
    "wget -S -O /dev/null --header='Host: beta.hypostasia.org' 'http://web:8000$chemin' 2>&1" \
    | grep 'HTTP/1'
done
```

Attendu : **quatre 404**. Avant le correctif, quatre 200 dont un de 375 122 octets.

> **L'adresse du site est `https://beta.hypostasia.org/`**, pas `h.localhost` : le
> routeur Traefik ne connaît que `Host(${DOMAIN})`, et `DOMAIN=beta.hypostasia.org`
> dans le `.env` de cette machine. `https://h.localhost/` rend un **404 de Traefik**
> (19 octets, `content-type: text/plain`) — vérifié le 23 août 2026.

### Test 2 — le propriétaire lit toujours ses jobs

1. Se connecter sur https://beta.hypostasia.org/ (`jonas` / `admin1234`).
2. Dans le **même onglet**, ouvrir `https://beta.hypostasia.org/api/extraction-jobs/`.
3. Attendu : **200**, et la liste des jobs des notes de `jonas` — pas celles des autres.
4. Ouvrir `https://beta.hypostasia.org/api/extraction-jobs/<id d'un job listé>/` → **200**.

### Test 3 — un tiers ne voit rien de la note d'autrui

1. Créer un second compte (ou se connecter avec un compte qui ne possède pas la note).
2. Ouvrir `https://beta.hypostasia.org/api/extraction-jobs/` → **200**, liste **vide** ou réduite
   à ses propres notes.
3. Ouvrir le détail d'un job de `jonas` → **404**, et le corps est **identique** à celui
   de `https://beta.hypostasia.org/api/extraction-jobs/999999/`.

### Test 4 — les exemples few-shot sont au staff

1. Déconnecté → `https://beta.hypostasia.org/api/extraction-examples/` → **404**.
2. Connecté avec un compte **non staff** → **404**.
3. Connecté avec un compte **staff** → **200**.

### Test 5 — la sidebar de l'extension répond toujours

`https://beta.hypostasia.org/api/sidebar/?url=https://exemple.org/inconnu` en anonyme → **200**
avec « Aucune analyse trouvee ». C'est le seul endpoint de la table qui reste ouvert, et
c'est délibéré.

### Tests automatiques

```bash
make test-suite S=hypostasis_extractor.tests.test_l_api_d_extraction_est_fermee
```

42 tests, **92,7 s** (mesuré le 23 août 2026).

La suite complète est verte sur le même état : `make test-rapide` rend
**2 490 tests, OK (skipped=1)** en **30 min 47** — mesuré le 23 août 2026 sur cette
machine, une VM Haswell 8 vCPU. Le chiffre du § 7 de `PLAN/PASSATION.md` (« 1748
tests, ~7 min 30 », 15 août) est donc périmé sur les deux colonnes.
