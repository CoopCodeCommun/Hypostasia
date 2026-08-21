# Connecter l'extension en un clic / One-click extension connection

**Date :** 2026-08-21
**Migration :** Non

## Resume / Summary

**Quoi / What :** un bouton « Connecter cette extension » dans la popup va
chercher le jeton d'API du compte connecte au site et le range. Le
copier-coller de quarante caracteres hexadecimaux disparait. Nouvel endpoint
`GET /api/pages/mon_jeton/`.
/ *A "Connect this extension" button fetches the API token of the account
logged into the site and stores it. The forty-hex-character copy-paste is gone.*

**Pourquoi / Why :** pour utiliser l'extension il fallait ouvrir `/auth/token/`,
selectionner le jeton, le copier, ouvrir les options de l'extension, le coller.
Cinq gestes et un presse-papier, pour une valeur qu'aucun humain ne peut relire
ni verifier.
/ *Five gestures and a clipboard, for a value no human can read back.*

### La question posee, et pourquoi la reponse n'est pas « la session »

La question du mainteneur etait : **pourquoi une cle d'API, et pas simplement
les cookies de session ?** Mesure du 21 aout 2026 — session valide, cookie CSRF
present, en-tete `X-CSRFToken` correct ; seule l'**origine** de l'appelant
change :

| Origine de la requete d'ecriture | Django repond |
|---|---|
| aucune (appel serveur a serveur) | **201** |
| `moz-extension://a3f9c2e1-…` (Firefox) | **403** — *Origin checking failed* |
| `chrome-extension://lmflifaokphpaknpdnmdmhdiaeiieomd` | **201** |
| `chrome-extension://<un autre id>` | **403** |

La troisieme ligne ne passe que parce que cet identifiant est **code en dur**
dans `CSRF_TRUSTED_ORIGINS` (`hypostasia/settings.py`) — vestige d'une extension
chargee en mode developpeur, et qui changera a la publication.

**Le blocage est Firefox, et il est definitif** : Firefox attribue a chaque
INSTALLATION d'une extension un UUID aleatoire (`moz-extension://<uuid>`),
different par profil et par machine, delibere pour empecher le pistage. Aucune
liste blanche serveur ne peut le contenir. **Une requete d'ECRITURE authentifiee
par session ne peut donc jamais aboutir depuis une extension Firefox.**

Mais une **lecture** le peut : un GET n'est pas soumis au controle CSRF. D'ou la
solution retenue — la session sert **une fois**, a recuperer le jeton ; tout le
reste passe par le jeton, dans les deux navigateurs, a l'identique.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/views.py` | `+PageViewSet.mon_jeton` — `GET /api/pages/mon_jeton/`, authentifie par session ou par jeton, `get_or_create` et **jamais** de regeneration |
| `extension/popup.html` | `+#connecterBtn` (masque tant qu'un jeton fonctionne) et son style, clair et sombre |
| `extension/popup.js` | `+recupererLeJetonDepuisLaSession()` ; `AVEC_LES_COOKIES` sur ce seul appel ; le bouton se montre selon la reponse de `me/` |
| `extension/README.md` | le mode d'emploi : un clic au lieu du copier-coller |
| `core/tests/test_jeton_pour_l_extension.py` | **Nouveau** — 6 tests |

### Les deux garde-fous qui comptent

**Le jeton n'est JAMAIS regenere.** Regenerer a chaque appel invaliderait celui
des autres installations : connecter l'extension du portable deconnecterait
celle du poste fixe, en silence. Ce geste connecte une machine de plus, il n'en
deconnecte aucune. La regeneration reste un geste explicite, sur `/auth/token/`.
Verrouille par `test_appeler_deux_fois_rend_le_MEME_jeton`.

**Ce n'est pas une nouvelle exposition.** `/auth/token/` **affiche** deja ce
jeton en clair a quiconque porte la session. Un site tiers ne peut lire ni l'un
ni l'autre : `Access-Control-Allow-Origin: *` interdit au navigateur d'y joindre
des cookies. Seule une extension disposant de la permission d'hote y accede — ce
qui est le propre des extensions, pas un defaut de cette API.

---

## Comment tester (a la main) / Manual test

### Test 1 — le chemin nominal

1. Se connecter a son instance dans le navigateur (`/auth/login/`).
2. Ouvrir la popup de l'extension **sans avoir jamais colle de jeton**.
   - Attendu : point **vert** « Serveur connecte », ligne orange « Non connecte
     a cette instance », et le bouton **« Connecter cette extension »**.
3. Cliquer.
   - Attendu : « Connectee en tant que *votre nom* », la ligne passe au vert,
     **le bouton disparait**, et le menu « Ranger dans » se remplit de vos
     carnets.

### Test 2 — pas connecte au site

1. Se deconnecter du site (ou ouvrir une fenetre privee).
2. Cliquer sur « Connecter cette extension ».
   - Attendu : « Connectez-vous d'abord a *adresse* dans ce navigateur, puis
     reessayez. » Aucun jeton n'est range.

### Test 3 — connecter une seconde machine ne deconnecte pas la premiere

1. Noter le jeton courant (`/auth/token/`).
2. Cliquer sur « Connecter cette extension » depuis un autre navigateur.
3. Recharger `/auth/token/`.
   - Attendu : **le meme jeton**. La premiere installation continue de marcher.

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from rest_framework.authtoken.models import Token
print(Token.objects.count(), 'jeton(s) —', [t.user.username for t in Token.objects.all()])
"
```

Attendu : **un seul** jeton par utilisateur, quel que soit le nombre de clics.

### Test 4 — un jeton devenu invalide

1. Regenerer le jeton sur `/auth/token/`.
2. Rouvrir la popup.
   - Attendu : « Token invalide — reconnectez l'extension » et le bouton
     reapparait. Un clic suffit a repartir.

### Verifs automatiques

```bash
make test-suite S=core.tests.test_jeton_pour_l_extension   # 6 tests
make test-suite S=core.tests.test_extension_api            # 29 tests
```

### Contraste

Mesure du 21 aout 2026, bouton rendu dans Chromium, couleurs lues sur
l'element : **4,95:1** en clair (`#2563eb` sur `#fafafa`) et **7,02:1** en
sombre (`#60a5fa` sur `#0f172a`). La premiere version utilisait `--accent`
(`#3b82f6`) et ne donnait que **3,52:1** en clair — sous le seuil AA pour du
texte de 11 px.
