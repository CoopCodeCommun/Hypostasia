# Bascule CSS, lots T4 et T5 : la lecture, puis les trois derniers ecrans corpus

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** deux lots livres et verifies au navigateur (agent
Playwright, contrastes calcules), sans toucher un modele, une migration
ni un endpoint.

**T4 — l'ecran de lecture.** Les derniers bleus du produit y vivaient.
Plutot qu'un selecteur par utilitaire, on REMAPPE A LA SOURCE les
echelles Tailwind `--color-blue-*` et `--color-indigo-*` vers
`var(--info)` : d'un coup, `hover:`, `prose-a:`, `prose-blockquote:` et
`border-l-` suivent, la ou une liste de classes ne les atteignait pas.
Puis : liens du corps en `--info` souligne (7,71:1), citation en bloc au
filet `--info`, legendes et en-tetes de tableau en monospace, chrome de
la page (Source / Exporter / Historique / pilules de version) en
monospace dense. Les PASTILLES de marge perdent leur halo bleu au profit
de l'ambre, et leur ecart passe a 8px : 16px + 8px = 24px de centre a
centre, soit l'EXCEPTION D'ESPACEMENT de WCAG 2.5.8 (la geometrie ne
peut pas grandir, le clip-path du triangle l'interdit).
Trois defauts trouves par la verification et corrigees dans la foulee :
le flash au clic (`@keyframes hl-pulse`, `bloc-flash-pulse`, ecrits en
bleu Tailwind en dur — les keyframes de meme nom sont REDEFINIES dans
maquette.css, hypostasia.css n'est pas touchee) ; le nom d'utilisateur
de la barre, NOIR SUR NOIR (1:1 -> 10,56:1) parce qu'un `<span>` a
quatre niveaux echappait aux selecteurs « enfant direct » ; l'avatar et
le lien Connexion sur la barre sombre (2,18:1 -> 10,18:1).

**T5 — carnets_liste, bases_liste, base_detail** portes sur
`.zone-corpus` / `.ligne-note` comme carnet_detail : ils forment
desormais un systeme avec lui (memes polices, memes tailles, meme
largeur de 64rem, verifie au pixel). Tous les `data-testid` sont
conserves a l'identique. La visibilite passe en icone ET mot, les etats
vides EXPLIQUENT la regle au lieu de la constater, et le design system
gagne cinq composants (`.lien-navigation`, `.vide`, `.rangee-champ`,
`.bouton-icone`, `.marque-visibilite`, `.groupe-actions`).
**Ecart assume vs l'etalon** : un token `--filet-controle` (3,27:1)
remplace `--filet` (1,28:1) sur le contour des champs et des boutons —
WCAG 1.4.11 demande 3:1 quand le contour est le seul indice visuel du
controle. L'etalon est fautif sur ce point ; la doctrine du chantier est
de faire mieux que lui en accessibilite, pas de le copier.

571 tests (test_phases + test_rendu_elements) et 122 tests corpus verts.

| Fichier | Changement |
|---|---|
| `front/static/front/css/maquette.css` | remappage des echelles Tailwind, section T4, keyframes ambre, barre (utilisateur/avatar/connexion), `--filet-controle` |
| `front/templates/front/corpus/_style_maquette.html` | 6 composants ajoutes, contours de controles renforces |
| `front/templates/front/corpus/carnets_liste.html` | porte sur .zone-corpus / .ligne-note |
| `front/templates/front/corpus/bases_liste.html` | idem |
| `front/templates/front/corpus/base_detail.html` | idem + edition des categories dans la ligne |
| `front/templates/front/corpus/partials/categories_de_la_base.html` | axes et categories en .axe / .etiquette-categorie |
| `front/templates/front/corpus/partials/erreurs_formulaire.html` | rouge Tailwind -> tokens |
| `front/templates/front/base.html` | cache-busting maquette.css v4 |

### Migration
- **Migration necessaire / Migration required :** Non.

