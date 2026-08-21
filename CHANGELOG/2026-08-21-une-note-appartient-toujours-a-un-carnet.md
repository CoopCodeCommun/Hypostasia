# Une note appartient toujours à un carnet / A note always belongs to a notebook

**Date :** 2026-08-21
**Migration :** Non

## Resume / Summary

**Quoi / What :** les deux carnets fourre-tout — « A ranger » et « Mes imports » —
ne sont plus jamais crees. Toute capture et tout import exigent un carnet
CHOISI, et le droit d'y ecrire est verifie. Le bouton d'import quitte la barre
d'outils pour la ligne du titre de chaque carnet.
/ *The two catch-all notebooks are never created again. Every capture and import
requires a CHOSEN notebook, with write access checked.*

**Pourquoi / Why :** un carnet que le code fabrique tout seul n'est pas une
destination. Il rendait normal le fait de ne rien choisir, ne se vidait jamais,
et le bouton d'import global ne disait pas ou le fichier atterrissait — on
cliquait sans destination et on la decouvrait apres.
/ *A notebook the code makes up is not a destination.*

### Le trou de securite ferme au passage

Quand un `dossier_id` etait fourni, les quatre chemins d'import faisaient :

```python
dossier_assigne = Dossier.objects.filter(pk=dossier_id).first()
```

**Aucun controle du droit d'ecriture.** N'importe quel utilisateur authentifie
pouvait deposer un fichier dans le carnet de n'importe qui, en passant son
identifiant. **Quatre occurrences** dans `front/views.py` — audio, transcription
JSON, document, et l'aperçu audio. Personne ne l'exploitait parce que
l'interface n'envoyait jamais `dossier_id`. **Ce chantier la fait envoyer** : le
trou devait etre ferme avant, pas apres.

### La regle vit maintenant a un seul endroit

`core/services/corpus.carnet_ou_ranger(utilisateur, dossier_id)` — a cote de
`carnets_ou_ecrire`, dont elle se sert. Elle exige un carnet, verifie le droit
d'y ecrire, et **leve `CarnetRefuse`** plutot que de se rabattre. Un carnet
inconnu et un carnet interdit recoivent la MEME reponse (doctrine du 404) :
sinon un import devient un moyen de savoir quels carnets existent.

Elle remplace **six** ecritures de la meme regle : `_resoudre_dossier`
(core/views.py), `_obtenir_ou_creer_dossier_imports` (front/views.py), et les
quatre `filter(pk=dossier_id).first()`.

### La synthese sans carnet est refusee

Troisieme usager du fourre-tout, et le seul qui n'etait pas un import : une
synthese dont la source n'appartient a aucun carnet irait nulle part — invisible
de tous les ecrans. Elle etait rangee dans « A ranger », cree pour l'occasion.

**Arbitrage du mainteneur : on refuse.** Et le refus vit DANS LA VUE, avant
l'appel au modele — refuser dans la tache couterait une synthese **facturee**
pour la jeter. La tache garde un `logger.error` en filet, pour le cas ou la note
quitterait son carnet PENDANT la production.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/services/corpus.py` | `+CarnetRefuse`, `+carnet_ou_ranger` — la regle, une fois |
| `core/views.py` | `-CarnetRefuse` local, `-_resoudre_dossier` ; la capture delegue |
| `front/views.py` | 4 sites convertis ; `-_obtenir_ou_creer_dossier_imports` ; refus de la synthese sans carnet |
| `front/tasks.py` | le repli « A ranger » devient un journal d'erreur |
| `front/views_corpus.py` | (rien : `peut_ecrire` existait deja dans le contexte) |
| `front/templates/front/corpus/carnet_detail.html` | `+` le geste d'import sur la ligne du titre, `+{% load i18n %}` |
| `front/templates/front/corpus/_style_maquette.html` | `+.ligne-titre-carnet`, `+.bouton-importer-note` |
| `front/templates/front/base.html` | `-` le bouton d'import de la barre d'outils ; `?v=39` → `?v=40` |
| `front/templates/front/includes/onboarding_vide.html` | le bouton mene aux carnets au lieu d'ouvrir un selecteur de fichier |
| `front/static/front/js/hypostasia.js` | import par DELEGATION, `dossier_id` joint ; `-` le relais d'onboarding |
| `extension/popup.html`, `extension/popup.js` | `-` l'entree fourre-tout ; message « aucun carnet » ; « Recolter » eteint ; `dossier_id` toujours envoye |
| `core/tests/test_extension_api.py` | trois tests inverses (voir ci-dessous) |

### Trois tests changent de sens

- `test_sans_carnet_la_capture_tombe_dans_le_fourre_tout` verrouillait la
  creation automatique de « A ranger ». Devenu
  `test_sans_carnet_la_capture_est_refusee`.
- `test_lister_ne_cree_jamais_le_fourre_tout` et
  `test_le_fourre_tout_porte_son_role_et_non_son_nom` fusionnent en
  `test_aucun_carnet_n_est_jamais_cree_par_l_api` : plus rien ne cree de carnet,
  nulle part.

### Ou est passe le bouton, et pourquoi la

Sur la **ligne du titre du carnet, a sa droite**. La destination ne se devine
plus : le bouton est DANS le carnet qu'il remplit.

**A droite et non a gauche** : ce qui precede un titre se lit comme une commande
de navigation — retour, menu. Ce projet a deja paye cette ambiguite une fois,
avec le menu burger retire le 12 aout 2026.

Il n'apparait que si `peut_ecrire` — le drapeau que la vue calculait deja. Le
serveur reverifie de toute facon : l'affichage decide de ce qu'on MONTRE, jamais
de ce qu'on AUTORISE.

### Ce que les roles speciaux deviennent

`RoleSpecialDossier.A_RANGER` et `.MES_IMPORTS` restent dans le modele, avec
leur contrainte d'unicite : les carnets deja crees en portent la marque et
continuent de vivre comme des carnets ordinaires. **Plus aucun code ne les
cree** — verifie par `rg` : zero occurrence hors modele et migrations.

---

## Comment tester (a la main) / Manual test

### Test 1 — l'import depuis un carnet

1. Ouvrir un carnet. Le bouton **« Importer »** est a droite de son titre.
2. Importer un PDF.
3. Attendu : la note apparait **dans ce carnet**. Aucun carnet « Mes imports »
   n'est cree.

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import Dossier, RoleSpecialDossier
print('carnets a role special :', Dossier.objects.exclude(role_special='').count())
"
```

### Test 2 — le carnet d'un autre est refuse

Poster un import avec le `dossier_id` d'un carnet qui ne vous est pas partage.
Attendu : **400**, et le message « Ce carnet n'existe pas, ou vous n'avez pas le
droit d'y écrire. » — la meme reponse que pour un carnet inexistant.

### Test 3 — l'extension sans carnet

1. Avec un compte qui n'a aucun carnet inscriptible, ouvrir la popup.
2. Attendu : le menu disparait, un message dit « Vous n'avez aucun carnet où
   écrire. Créez-en un sur votre instance, puis rouvrez cette fenêtre. », et le
   bouton **Récolter est éteint**.

### Test 4 — l'accueil d'un compte neuf

Se connecter avec un compte sans aucune note. Attendu : le premier bouton dit
**« Créer mon premier carnet »** et mene a `/carnets/`. Il ouvrait un selecteur
de fichier, pour un import qui ne pouvait qu'echouer.

### Test 5 — la synthese d'une note sans carnet

Demander une synthese sur une note qui n'est dans aucun carnet. Attendu : un
toast « Cette note n'est dans aucun carnet : rangez-la d'abord, la synthèse ira
dans le même carnet. » et **aucun appel au modele**.

### Verifs automatiques

```bash
make test-suite S=core.tests.test_extension_api    # 28 tests, verts
make test-rapide
make test-e2e
```
