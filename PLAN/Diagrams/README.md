# Le moteur, en diagrammes

> Trois planches Mermaid qui décrivent le **mécanisme** d'Hypostasia : comment un
> fichier devient une preuve citable, comment un article se source, et comment ses
> citations se vérifient.

| Planche | Ce qu'elle établit |
|---|---|
| [1. De l'ingestion au périmètre](01-de-l-ingestion-au-perimetre.md) | **Rien n'entre dans un périmètre sans être ancré**, et c'est un humain qui décide du périmètre |
| [2. Du prompt à l'article sourcé](02-du-prompt-a-l-article-source.md) | Le numéro `[N]` **n'est jamais enregistré**, et **aucun texte n'est jamais retiré** de l'article |
| [3. La vérification des citations](03-la-verification-des-citations.md) | L'unité jugée est une **paire**, jamais une phrase — et le défaut est toujours **restrictif** |

## Pourquoi du Mermaid, et pas une image

Parce que la source est du **texte** : elle se relit dans un diff, elle se corrige sans
outil, et elle vit dans le dépôt à côté du code qu'elle décrit. Un PNG exporté d'un éditeur
en ligne devient faux sans que personne ne le voie.

**GitHub rend ces blocs nativement.** Les diagrammes s'affichent dans l'interface du dépôt,
ici comme dans n'importe quel `README.md`. Aucune dépendance, aucun build.

## Ce que ces planches ne font PAS

**Elles ne tiennent aucun état d'avancement.** Trois documents seulement en tiennent un —
`CHANGELOG/`, `PLAN/PASSATION.md` et la mémoire — et `AGENTS.md` interdit d'en écrire un
quatrième, parce qu'il périmerait sans que personne ne le sache.

Ces planches décrivent un **mécanisme**, qui ne périme pas au même rythme. Quand elles
citent une mesure, elles la datent.

## Les conventions de lecture

| Forme | Sens |
|---|---|
| Cadre **vert** | une vérité durable : les éléments, les portions, un verdict établi |
| Cadre **rouge** | un **refus** — et le projet en est fier : ils sont tous *bruyants* ou *visibles*, jamais silencieux |
| Cadre **violet** | un geste **humain** : rien ne s'applique tout seul |
| Cadre **orange** | un appel au modèle, donc **facturé** |
| Flèche pointillée | une note, une justification, une branche d'échec |

Le fil conducteur des trois planches est une même règle : **on ne devine jamais.** Un texte
qu'on ne sait pas ancrer n'est pas ancré au hasard, une proposition périmée n'écrase rien, un
lot de verdicts suspect est annulé en entier. À chaque fois, le défaut est de ne pas
conclure — parce qu'une preuve fausse se donne pour une preuve, et qu'une absence de preuve
ne trompe personne.

## Si tu corriges une planche

Le code fait foi, pas le diagramme. Vérifie dans le code avant de changer une flèche, et
date toute mesure que tu ajoutes.
