# Bascule CSS, lots T6 a T9 : pages nues, theme sombre, overlays, purge — et les restes d'accessibilite

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** la fin du chantier de bascule. Toujours du front pur :
aucun modele, aucune migration, aucun endpoint touche. Chaque lot a ete
verifie au navigateur par un agent Playwright avec contrastes calcules,
et chaque ecart trouve a ete corrige puis contre-verifie.

**T6 — les cinq pages nues** (connexion, inscription, token, 403,
invitation) : elles n'avaient AUCUN equivalent dans la maquette
(cahier des charges § 2.4, trou n°1). Gabarit neuf `.page-nue` — une
`.zone-corpus` etroite de 26rem — qui REUTILISE les composants
existants (`.champ-*`, `.bouton-plat`, `.surface-formulaire`,
`.message-etat`, `.pied-page`) plutot que d'inventer un systeme
parallele. Elles chargent maintenant la couche maquette : ce sont les
premieres pages hors `base.html` a le faire.

**T7 — le theme sombre, qui n'existait pas.** Mecanisme a trois etats
de l'etalon (`:root` / `@media prefers-color-scheme` /
`[data-theme="dark"]`) plus la PERSISTANCE `localStorage` que l'etalon
n'a pas, appliquee dans le `<head>` avant le premier rendu pour ne pas
clignoter. Les 8 tokens de surface sont ceux de l'etalon au bit pres
(verifie contre le fichier). **Ses accents, eux, ne survivent pas au
fond sombre** — `--info` y tombe a 2,26:1 — donc ils basculent aussi,
ainsi que les 8 familles d'hypostases, les deux tokens de statut et le
filet de controle. Trouve et repare a la verification : l'onboarding
entier reste en couleurs Tailwind (titre a 1,02:1), un ilot `#fafbfc`
oublie, les ombres portees noires devenues invisibles, les soulignements
de statut ecrits en `rgba()` fixe (1,37:1) et **l'ambre pur lui-meme,
qui ne fait que 2,20:1 sur le papier clair** — d'ou un token
`--filet-statut-commente` qui le fonce en clair et le laisse pur en
sombre.

**T8 — les overlays.** Modale d'alignement (les fonds blancs sticky
etaient vises par les classes de la MAQUETTE, absentes de
l'application : corrige sur les vraies classes), badges d'hypostase du
drawer re-derives de la teinte de leur famille, bottom sheet, voiles.
**Decouverte du lot** : les 150 lignes de `.ws-toast*`
(hypostasia.css:1668-1810) sont du CSS MORT — zero occurrence dans un
`.js`, un `.html` ou un `.py`. Les « deux systemes de toasts » du
cahier des charges n'en font plus qu'un : c'est SweetAlert qu'on
habille.

**T9 — la purge.** Deux `.woff2` de Lora orphelins supprimes (aucun
`@font-face` ne les nommait). Et les **deux tests-mensonges** reecrits
sur le contrat REEL : « le body est en B612 » devient « la couche
maquette, chargee en dernier, met le body en Georgia », avec un test
qui verifie l'ORDRE DE CHARGEMENT — c'est lui le contrat, l'inverser
rendrait le corps a B612 sans qu'aucun autre test ne bronche.

**Accessibilite — les restes du plan, tous traites :** lien
d'evitement (la barre compte quinze controles avant le contenu),
`aria-expanded`/`aria-haspopup`/`aria-controls` et fermeture a Echap
avec retour du focus sur le menu utilisateur, onglets du carnet devenus
un vrai tablist (`aria-controls`, `role=tabpanel`, `aria-labelledby`
qui SUIT l'onglet courant, fleches en activation manuelle, un seul
onglet dans l'ordre de tabulation), `aria-live` resserre du panneau
entier vers la seule liste rechargee, repli `@supports` pour `:has()`,
et le manifeste — page entiere jamais basculee, 1,02:1 en sombre —
passe integralement en tokens.

**Le troisieme reservoir de couleurs**, trouve a la toute fin : le
plugin Tailwind Typography porte les siennes dans des variables
`--tw-prose-*` en `oklch`, hors de portee du remappage des echelles
comme des regles par classe. Le texte d'une citation en bloc tombait a
**1,07:1** en sombre — un bloc vide avec une barre bleue. Les 16
variables sont remappees a la source. Regle du chantier, confirmee
trois fois : quand une couleur resiste, chercher la VARIABLE qui la
porte plutot qu'ajouter un selecteur.

**Deux tests-mensonges de plus, decouverts par la suite e2e** :
« la police B612 est chargee » et « la police Lora est chargee »
echouaient — non parce qu'une police avait disparu, mais parce que le
navigateur ne charge une police que si un element l'emploie, et que
depuis la decision D1 ni B612 ni Lora n'habillent plus le corps. Elles
ne servent plus qu'aux ilots de provenance, absents d'une page sans
extraction. Les deux tests verifient desormais la DECLARATION (comme
celui de Srisakdi, deja ecrit ainsi), et un test neuf assied le
nouveau contrat : le corps de lecture est en Georgia.

**Une regression trouvee par la suite mobile et corrigee** : le bouton
de bascule du theme mangeait la largeur du titre du document dans la
barre, jusqu'a le faire disparaitre sous 640px. Il y est masque — le
titre est plus utile la, et la bascule reste accessible depuis la page
de reglages et les pages nues.

669 tests verts (test_phases, test_rendu_elements, corpus D a H,
phase28) et **les 104 tests e2e** de la suite complete.

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | theme sombre 3 etats, tokens d'accents sombres, `--filet-statut-*`, overlays, SweetAlert, onboarding, lien d'evitement, repli `:has()` |
| `front/static/front/js/theme.js` | **nouveau** : le theme 3 etats et sa persistance |
| `front/static/front/js/user_menu.js` | aria-expanded, Echap, retour du focus |
| `front/templates/front/{login,register,mon_token,acces_refuse,invitation_erreur}.html` | gabarit `.page-nue` + bascule de theme |
| `front/templates/front/base.html` | lien d'evitement, bouton de theme, aria du menu |
| `front/templates/front/corpus/_style_maquette.html` | `.page-nue`, `.vide`, `.bouton-icone`, `.groupe-actions`, contours de controles, onglet actif |
| `front/templates/front/corpus/carnet_detail.html` | tablist complet, aria-live resserre |
| `front/templates/front/includes/manifeste.html` | 14 couleurs en dur -> tokens |
| `front/templates/front/includes/lecture_principale.html` | les 6 utilitaires `prose-*` COLORES retires (ils battaient les variables) |
| `front/tests/test_phases.py` | 2 tests-mensonges reecrits + 3 tests neufs |
| `front/tests/e2e/test_22_corpus.py` | clique la puce et non la case masquee |
| `front/tests/e2e/test_06_charte_visuelle.py` | 2 tests de police reecrits + 1 test neuf (corps en Georgia) |
| `front/static/front/fonts/lora-{medium,semibold}.woff2` | supprimes (orphelins) |

### Migration
- **Migration necessaire / Migration required :** Non.

