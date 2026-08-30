# Commenter une base, un carnet, une note

**Intention du mainteneur, instruite le 23 août 2026. Rien n'est codé.**

Le fragment d'origine, tel qu'il a été écrit, tenait en une phrase :

> pouvoir ajouter des notes et des commentaires sur les trois objets base / carnet /
> note, au nom d'un user, qui pourra être pris en compte dans une synthèse et/ou un
> wiki.

## Ce que le code fait aujourd'hui

**Un seul objet est commentable, et ce n'est aucun des trois : l'EXTRACTION.**

`CommentaireExtraction` (`hypostasis_extractor/models.py:457`) porte `entity`, `user`,
`commentaire`, `created_at` — une FK vers `ExtractedEntity`, et rien d'autre. Vérifié le
23 août : `rg "^class .*Commentaire" core/models.py hypostasis_extractor/models.py` ne
rend que celui-là. Ni `BaseDeConnaissances`, ni `Dossier`, ni `Page` n'a de commentaire.

Le geste existe et il est complet :

| Brique | Où |
|---|---|
| poser un commentaire | `PageViewSet.ajouter_commentaire` (`front/views.py:4925`) — POST, `_exiger_authentification` puis `_verifier_acces_page` : **le débat est ouvert à qui peut LIRE la note** |
| l'effet sur le statut | un signal Django passe l'extraction en `statut_debat="commente"` — jamais écrit à la main |
| la notification | `_commentaires_neufs` (`core/services/recapitulatif_du_matin.py:195`) met les commentaires neufs dans le récapitulatif du matin |
| la vérification | `SourceLink.commentaires_source` les reporte d'un tour de wiki au suivant (`core/services/synthese.py:683, 776`) |

**Et la prise en compte par le rédacteur existe DÉJÀ pour ce commentaire-là.**
`front/tasks.py:463-477` compose le bloc envoyé au modèle :

```python
for commentaire in entite.commentaires.all():
    nom_auteur = commentaire.user.username if commentaire.user else "Anonyme"
    lignes_commentaires.append(f'  - {nom_auteur} : "{commentaire.commentaire}"')
```

Le prompt de synthèse le promet explicitement
(`front/services/fixtures_analyseurs.py:346-362`) : « Les commentaires te sont fournis
avec l'extraction : quand ils divergent, expose la divergence au lieu de la trancher. »

**Donc la seconde moitié de l'intention — « pris en compte dans une synthèse et/ou un
wiki » — est déjà vraie, mais seulement pour un commentaire ancré à une extraction.**
Ce qui manque est la première moitié : les trois objets du corpus.

## Ce qui est voulu

Un commentaire signé, posé sur une **base de connaissances**, un **carnet** ou une
**note**, et versé à la matière du rédacteur au même titre qu'un commentaire
d'extraction.

## Ce qui n'est pas tranché — à décider avant d'écrire une ligne

Ces quatre points changent le modèle de données, pas seulement l'écran :

1. **« des notes ET des commentaires » — un objet ou deux ?** La phrase d'origine
   distingue les deux mots. S'agit-il d'un seul modèle (comme `CommentaireExtraction`),
   ou d'une note personnelle privée distincte d'un commentaire visible de tous ? Le
   projet a déjà un texte porté par le carnet et montré aux contributeurs :
   `Dossier.guide_de_redaction` (`core/models.py`). Ce n'est pas la même chose, mais
   c'est le voisin le plus proche.
2. **Qui peut poser, qui peut lire.** Le commentaire d'extraction suit la règle
   « ouvert à qui peut LIRE la note ». Un commentaire de carnet suit-il
   `_utilisateur_a_acces_dossier`, ou exige-t-il le droit d'**écrire** ? Un carnet
   public rendrait le premier choix commentable par le monde entier.
3. **Ce que le rédacteur en fait.** Un commentaire d'extraction est **ancré** : le
   modèle sait à quel passage il se rapporte, et l'article peut le citer. Un
   commentaire de carnet ne l'est pas. Or l'invariant du projet est que **chaque
   affirmation cite sa source**. Injecter dans le prompt un texte sans ancre, c'est
   offrir au modèle de la matière qu'il ne pourra **pas** sourcer — et le prompt de
   synthèse lui interdit précisément d'écrire ce qu'aucune extraction ne porte. Deux
   voies s'excluent : *consigne de cadrage* (le commentaire oriente la rédaction, mais
   n'est jamais cité) ou *source de plein droit* (il faut alors lui donner un
   `SourceLink`, donc une ancre — ce qui revient à en faire une extraction).
4. **Le périmètre.** Un article a un périmètre figé de notes et d'extractions
   (`core/services/synthese.py:175`). Le commentaire d'un carnet entre-t-il dans le
   périmètre de tout article de ce carnet, y compris ceux figés avant qu'il n'existe ?

**Le point 3 est le vrai.** Les trois autres sont des choix ; celui-là décide si la
fonctionnalité respecte la promesse du produit ou l'entame.

## Ce qui casse si on ne fait rien

Rien ne casse — c'est une fonctionnalité absente, pas un défaut. Ce qui manque est un
endroit où déposer ce qui ne se rattache à **aucun** passage : une consigne de lecture
sur un carnet, une réserve sur une base entière, un mot de contexte sur une note dont
aucune phrase précise n'est en cause. Aujourd'hui, il faut accrocher ce propos à une
extraction quelconque, ce qui le fait entrer dans le débat d'une idée qu'il ne visait
pas — et bascule cette extraction en `COMMENTÉ`, donc en « au moins une intervention
humaine », alors que personne n'a réagi à elle.

## Coût de mise en œuvre

Indéterminé tant que le point 3 n'est pas tranché. La partie mécanique — un modèle,
une migration, un endpoint sur le modèle de `ajouter_commentaire`, un include par
écran — est d'une journée. La partie qui compte est la décision de conception.
