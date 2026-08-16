# Recette connectee : les sept dernieres frictions (F4 a F10) — l'ecran en savait plus qu'il n'en disait

**Date :** 2026-08-10
**Migration :** Non

**Quoi / What :** les sept defauts d'experience restants de la recette
du carnet 1. Un fil les relie : **l'ecran detenait l'information et ne
la donnait pas**.

**F4 — lire un article ne changeait pas l'URL.** Pas de `hx-push-url`
sur les liens des listes : on lisait un wiki a l'adresse du carnet, F5
ramenait a la liste des notes, et le lien n'etait pas partageable
depuis l'endroit meme ou on lisait.

**F5 — le diff parlait en langage machine** au moment precis ou l'on
demande d'accepter ou de refuser : `append_to_section` s'affichait tel
quel, et `[[ext:35284]]` exposait une syntaxe interne masquee PARTOUT
ailleurs. Deux filtres de gabarit traduisent desormais a l'affichage,
sans toucher aux donnees. Un troisieme detecte une operation dont le
contenu n'est QUE des marqueurs et le DIT : le defaut B2 a ete corrige
cote back, mais un diff qu'on accepte les yeux fermes est un diff
inutile — l'ecran doit rester capable de le signaler.

**F6 — le verdict se lisait comme une separation.** Un filet bas
pleine largeur sous le paragraphe : en recette, il a d'abord ete pris
pour une bordure decorative. Dans ce design system un etat se porte a
GAUCHE — c'est deja le cas du guide de redaction, des operations de
diff, des messages d'etat. Le verdict rejoint cette grammaire, et
chaque paragraphe porte un `title` qui NOMME son etat : une couleur ne
se lit pas toute seule.

**F7 — la legende promettait des couleurs absentes.** Elle annoncait
les six etats, « non source » compris, avant meme la premiere
verification. Elle n'annonce plus que ceux que le texte porte
reellement, et s'ouvre en disant ce que la couleur qualifie — le
paragraphe, par son verdict le PLUS FAIBLE.

**F8 — trois actions, une seule ligne.** Produire un wiki, proposer une
mise a jour et verifier des citations donnaient trois entrees
identiques dans « Mes taches », parce que tout ce qui n'etait pas une
synthese tombait dans « analyse ». Un `libelle_de_tache` les distingue
— la logique (`type_tache`, marquage lu, cible du lien) n'a pas bouge.
Les accents manquants de ce panneau, seul endroit de l'interface dans
ce cas, sont retablis.

**F9 — le titre de l'onglet** disait « Bibliotheque » partout. C'est
pourtant souvent le SEUL nom qu'une page recoit : dans une barre de dix
onglets, dans un signet, dans un historique.

**F10 — le moteur n'etait pas nommable.** On ne le choisit pas a la
creation ; a defaut, l'ecran le NOMME et dit ou il se change.

Quatre ecarts de contraste trouves par la verification et corriges,
dont un de ce lot : le filet « pas encore verifie » tombait a
**2,94:1**, six centiemes sous le seuil, a cause d'un alpha de 70 %.
Les trois autres etaient preexistants — filet du guide de redaction
(2,12:1), compteur du bouton taches (3,30:1), taille de la pastille de
renvoi.

**Une regression introduite puis levee, qui merite d'etre ecrite.** En
remappant le fond du compteur de taches sur `--succes`, on a **re-commis
l'erreur que le lot T10 avait pourtant corrigee ailleurs** : un fond
semantique PLEIN ne peut pas porter un `white` fige. En theme sombre
ces tokens sont des pastels CLAIRS — ils y servent de texte sur fond
sombre — et le `color: white !important` de hypostasia.css:1920 y
tombait a **1,52:1**, pire qu'avant le correctif. Le token qui suit le
theme est `--papier`. Les quatre etats du badge (y compris l'etat
neutre, dernier `white` fige du composant) sont desormais entre 5,3 et
11,9:1 dans les deux themes. Regle a appliquer sans reflechir : **quand
on remappe un fond, on verifie ce que le TEXTE devient dans les deux
themes**, et on cherche un `color` en dur dans l'ancienne feuille.

14 tests neufs, 659 tests unitaires et 104 e2e verts.

| Fichier | Changement |
|---|---|
| `front/templatetags/lisibilite_diff.py` | **nouveau** : 3 filtres d'affichage pour le diff |
| `front/templates/front/corpus/partials/diff_operations.html` | operations nommees, marqueurs lisibles, alerte « sans redaction » |
| `front/templates/front/corpus/article.html` | legende conditionnee aux etats presents |
| `front/views_synthese.py` | `etats_de_verification_presents`, `title` des verdicts, moteur annonce |
| `front/views_taches.py` | `libelle_de_tache` : les actions se distinguent |
| `front/templates/front/includes/taches_dropdown.html` | libelles distincts, accents retablis |
| `front/templates/front/base.html` | `<title>` par ecran |
| `front/templates/front/corpus/liste_{wikis,syntheses}.html` | `hx-push-url`, moteur annonce |
| `front/templates/front/corpus/_style_maquette.html` | verdict a gauche, pastille de renvoi, filets ≥ 3:1 |
| `front/tests/test_frictions_recette_f4_f10.py` | **nouveau** : 14 tests |

### Migration
- **Migration necessaire / Migration required :** Non.

