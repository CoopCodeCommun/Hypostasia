# Le webclipper choisit son carnet / The web clipper picks its notebook

**Date :** 2026-08-20
**Migration :** Non

## Resume / Summary

**Quoi / What :** l'extension navigateur fait choisir le carnet **avant** la
capture, dans un menu qui liste les carnets ou l'utilisateur peut ecrire —
partages par groupe compris — et retient le dernier choisi par serveur et par
compte. Au passage, `GET /api/pages/` cesse de rendre le corpus entier a qui le
demande sans jeton.
/ *The browser extension now picks the notebook **before** capturing, from a menu
of notebooks the user may write to — group shares included — remembering the last
choice per server and per account. Along the way, `GET /api/pages/` stops handing
the whole corpus to anyone without a token.*

**Pourquoi / Why :** la capture atterrissait dans le fourre-tout « A ranger »,
puis des boutons de rangement apparaissaient *apres coup* : deux gestes, deux
aller-retours, et une note mal rangee si la popup se fermait entre les deux. Et
la liste de carnets proposee ignorait les partages par groupe, donc un eleve ne
voyait pas le carnet de sa classe.
/ *Captures landed in the inbox and offered filing buttons afterwards: two
gestures, and a misfiled note if the popup closed in between. The offered list
also ignored group shares.*

### Ce qui a ete mesure / What was measured

| Mesure | Valeur | Date |
|---|---|---|
| `GET /api/pages/` sans jeton, `Origin` tiers, via nginx | **200**, **291 840 octets**, **13 notes**, `Access-Control-Allow-Origin: *` | 20 aout 2026 |
| dont texte lisible | **150 384 caracteres** | 20 aout 2026 |
| dont HTML d'origine | **54 538 caracteres** | 20 aout 2026 |
| carnets en base de dev | **2**, pour **6 comptes** | 20 aout 2026 |
| captures web reelles en base | **1** (page 1), **28 elements**, ingestion `reussie` | 20 aout 2026 |

**Deux precisions d'honnetete.** D'abord, sur les 13 notes exposees, **12
portaient `url: null`** : ce qui fuyait n'etait pas la liste des URL du corpus
(ce que la spec corpus § 13.5 annonce) mais **le texte integral des notes**, y
compris les wikis internes. Ensuite, la divergence des deux empreintes de
contenu est **etablie par lecture du code** (l'extension hachait
`body.textContent` sans `.strip()`, le serveur hachait son extracteur avec) mais
l'ecart client/serveur **n'a pas ete mesure** — il aurait fallu un moteur JS. Ce
qui est mesure, c'est que **9 des 10** notes du depot ayant un `html_readability`
portent un `content_hash` qui ne correspond pas a un recalcul serveur depuis leur
propre HTML : le champ n'a aujourd'hui aucun invariant.

### Ce que la fermeture de l'API ferme, et ce qu'elle ne ferme pas

Elle ferme **l'enumeration du corpus entier en un appel non authentifie**, notes
privees comprises. Elle **ne ferme pas** la lecture d'une note rangee dans un
carnet **public** : `GET /lire/1/` en anonyme rend toujours son texte, et c'est
le modele de visibilite qui le veut — public veut dire public. Onze des treize
notes du depot de dev sont dans un carnet public.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/services/corpus.py` | **+4 fonctions** : `carnets_visibles_par` (venue de `front/views_corpus.py`), `carnets_ou_ecrire`, `peut_ecrire_dans_le_carnet`, `notes_visibles_par` — les perimetres d'acces vivent la, et nulle part ailleurs |
| `core/views.py` | `list()` exige un jeton et se borne au perimetre ; `+mes_carnets` ; `mes_dossiers` corrige des partages par groupe ; conflits traites **avant** `is_valid()` ; `_resoudre_dossier` refuse au lieu de se rabattre ; sidebar bornee au perimetre ; `-_ids_dossiers_accessibles` |
| `core/serializers.py` | `PageListSerializer` perd les trois champs de contenu ; `content_hash` passe en lecture seule ; `+dossier_id` valide en entier |
| `front/services/texte_depuis_html.py` | `+empreinte_d_une_capture` — l'empreinte a desormais **une** implementation, appelee par la vue et par le serializer |
| `front/views.py` | `_utilisateur_peut_ecrire_dossier` delegue au service |
| `front/views_corpus.py` | `carnets_visibles_par` importee du service ; la **troisieme copie** de la regle d'ecriture (bloc « Ajouter a... ») remplacee par `carnets_ou_ecrire` |
| `extension/popup.html` | menu des carnets **avant** le bouton, avertissement « carnet public », tokens de couleur clair **et** sombre, `data-testid` |
| `extension/popup.js` | choix du carnet envoye dans le POST ; souvenir du dernier carnet ; indicateur de serveur bascule sur `/api/pages/me/` ; les trois 409 distingues par leur `code` ; plus d'empreinte calculee cote client ; rangement post-recolte retire |
| `extension/manifest.json` | retrait de `init_htmx_sidebar.js`, declaree et absente du paquet |
| `core/tests/test_extension_api.py` | **Nouveau** — 26 tests, le fichier que `SPEC-corpus` § 9 annonce depuis le 5 aout et qui n'avait jamais ete ecrit |
| `front/tests/test_phases.py` | `Phase25bPageListSansTokenTest` **inverse** : il exigeait un 200 sans jeton, donc il verrouillait la fuite |
| `front/tests/test_corpus_phase_d.py` | le test de dedup par contenu posait l'empreinte a la main ; il pose maintenant celle que le serveur calcule |
| `PLAN/specs/SPEC-corpus-base-carnet-note.md` | addendum date du 20 aout : ce que ce chantier fait de la phase I |

### Ce qui n'a PAS ete fait, et pourquoi

- **Le multi-carnets de la phase I** (cases a cocher, `carnet_ids`) : arbitrage
  du mainteneur, un seul carnet a la fois. `classer_depuis_extension` reste en
  place, **sans appelant** desormais.
- **L'unicite globale de `Page.url`** : non touchee, arbitrage du mainteneur.
  Consequence assumee : deux collectifs d'une meme instance ne peuvent pas
  capturer la meme page ; le second recoit un message qui le dit.
- **Le code mort de la sidebar** (`background.js`, `content.js`, `sidebar.*`) :
  non supprime. `SidebarViewSet` a **quand meme** ete borne au perimetre — un
  endpoint reste appelable a la main meme quand son client est injoignable.

---

## Comment tester (a la main) / Manual test

### Test 1 — la fuite est fermee

```bash
# Avant : 200 et ~292 Ko. Maintenant : 401.
docker exec hypostasia_web curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Host: beta.hypostasia.org" -H "Origin: https://un-site-tiers.example" \
  "http://nginx/api/pages/"
```

Attendu : **401**.

Puis, avec un jeton (page `/auth/token/`) :

```bash
docker exec hypostasia_web curl -s -H "Host: beta.hypostasia.org" \
  -H "Authorization: Token <ton-jeton>" "http://nginx/api/pages/" | head -c 400
```

Attendu : **200**, et **aucun** des champs `html_original`, `html_readability`,
`text_readability` dans la reponse.

### Test 2 — le menu des carnets

1. Charger l'extension (`chrome://extensions/` → mode developpeur → charger
   `extension/`).
2. Ouvrir la popup **sans** avoir colle de jeton.
   - Attendu : point **vert** « Serveur connecte » et ligne orange « Non
     connecte : collez votre token ». **Pas** de « Serveur erreur (401) ».
3. Coller le jeton dans les options, rouvrir la popup.
   - Attendu : « Connecte : jonas », et le menu « Ranger dans » liste
     « A ranger (le fourre-tout) » puis les carnets inscriptibles.
4. Choisir « Documents etalons ».
   - Attendu : la ligne orange « Ce carnet est public : la note y sera visible
     par tous. » apparait sous le menu.

### Test 3 — la capture va dans le carnet choisi

1. Aller sur un article quelconque, ouvrir la popup, choisir un carnet, cliquer
   **Recolter**.
2. Attendu : « Enregistree dans « *nom du carnet* » ».
3. Ouvrir `/carnets/` sur le site : la note est **dans ce carnet**, et **pas**
   dans « A ranger ».

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import Page
note = Page.objects.latest('created_at')
print(note.title)
print([a.dossier.name for a in note.appartenances_dossiers.all()])
print('elements :', note.elements.count(), '| ingestion :', note.ingestion_etat)
"
```

Attendu : un seul carnet, celui qu'on a choisi. Et apres une minute,
`elements` > 0 avec `ingestion : reussie` — la capture nourrit bien le moteur
ELEMENT.

### Test 4 — le souvenir du dernier carnet

1. Capturer dans « Veille financement ».
2. Fermer la popup, aller sur une autre page, rouvrir la popup.
   - Attendu : « Veille financement » est **deja selectionne**.
3. Supprimer ce carnet depuis le site, rouvrir la popup.
   - Attendu : le menu retombe sur « A ranger », **sans erreur**.

### Test 5 — l'URL deja prise par un tiers

1. Se connecter avec un second compte, capturer une URL deja capturee par le
   premier dans un carnet **prive**.
   - Attendu : message orange « Cette page est deja capturee sur ce serveur,
     dans un carnet auquel vous n'avez pas acces. »
   - **Pas** de « Erreur creation (400) », et **pas** de message vert.

### Test 6 — le partage par groupe

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from django.contrib.auth import get_user_model
from core.models import Dossier, DossierPartage, GroupeUtilisateurs
from core.services.corpus import carnets_ou_ecrire
U = get_user_model()
membre = U.objects.get(username='jonas')
print([c.name for c in carnets_ou_ecrire(membre)])
"
```

Ajouter `jonas` a un groupe a qui un carnet est partage, relancer : le carnet
doit apparaitre. Avant ce chantier, l'extension ne le voyait pas.

### Verifs automatiques

```bash
make test-suite S=core.tests.test_extension_api      # 26 tests
make test-suite S=front.tests.test_corpus_phase_d
make test-suite S=front.tests.test_phases
make test-rapide
```

### Contraste et theme sombre

La popup a son propre CSS (elle ne peut charger ni Tailwind ni `maquette.css`
depuis une page `chrome-extension://`). Basculer le systeme en theme sombre et
rouvrir la popup : fond `#0f172a`, texte `#e2e8f0`.

Contrastes **calcules** le 20 aout 2026, popup rendue dans le Chromium de
Playwright, couleurs lues sur les elements (`getComputedStyle`) :

| Paire | Clair | Sombre |
|---|---|---|
| texte sur fond | 9,92:1 **AAA** | 14,48:1 **AAA** |
| avertissement « carnet public » | 4,81:1 **AA** | 10,69:1 **AAA** |
| libelles secondaires | 4,56:1 **AA** | 6,96:1 **AA** |
| message de succes | 4,81:1 **AA** | 10,25:1 **AAA** |
| message d'erreur | 4,63:1 **AA** | 6,45:1 **AA** |
| bouton « Recolter » | 5,17:1 **AA** | 7,02:1 **AA** |

**Le bouton en theme sombre a ete corrige apres mesure.** Le couple d'origine
— blanc sur `#3b82f6` — ne donnait que **3,68:1**, ce qui ne passe AA que pour
du « grand texte » ; or le libelle fait 13 px gras, en dessous du seuil WCAG
(18,66 px gras). Le theme sombre inverse donc le bouton : bleu clair `#60a5fa`,
texte `#0f172a`. Meme correction sur le bouton « OK » de l'adresse, ou le blanc
sur gris tombait a 2,6:1.
