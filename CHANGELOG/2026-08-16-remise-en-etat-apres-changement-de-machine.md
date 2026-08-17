# Remise en état de l'environnement agent après changement de machine

**Date :** 2026-08-16
**Migration :** Non

Le dépôt a été recloné sur une nouvelle machine (`/home/jonas/Gits/Hypostasia`
→ `/home/ubuntu/Hypostasia`). Trois éléments de l'environnement agent ne
survivent pas à ce déplacement parce qu'ils sont **hors de git**, et **aucun ne
lève d'erreur en leur absence** : les sessions démarrent normalement, simplement
sans ce qu'ils apportent.

## 1. Le hook `SessionStart` avait disparu — reconstruit

`.claude/settings.json` n'est pas versionné (`.gitignore` ne le mentionne même
pas ; il n'a jamais été committé). Il portait le hook qui injecte le skill `djc`
dans le contexte de chaque session — les conventions de code du projet. Le
dossier `.claude/` était entièrement absent du clone.

Il a d'abord été **reconstruit à l'identique** à partir de la fiche de mémoire
persistante `trois-vehicules-pour-les-regles`, qui en décrivait la commande : un
`jq -n --rawfile` injectant le `SKILL.md` entier en `additionalContext`.

**Cette version ne marche plus, et son échec est invisible.** Au redémarrage de
session, le hook s'est exécuté sans erreur et a rendu **56 947 octets, octet
pour octet identiques** au `SKILL.md` — vérifié par `diff`. Mais le harnais juge
désormais un `additionalContext` de cette taille trop gros : il l'**écrit dans
un fichier** (`<session>/tool-results/hook-*-additionalContext.txt`) et n'injecte
qu'un **aperçu de 2 Ko**. Le hook réussit, sa sortie est correcte, et les
conventions ne sont pas dans le contexte. Rien ne le signale.

Le hook rend donc maintenant une **consigne de 494 octets** — largement sous le
seuil — qui ordonne d'invoquer `Skill(djc)`. Le skill est chargé par le
mécanisme prévu pour ça, au prix d'un appel d'outil par session :

```bash
test -r "$HOME/.claude/skills/djc/SKILL.md" \
  && echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"… invoque le skill djc : Skill(djc) …"}}' \
  || echo '{"systemMessage":"Le skill djc est introuvable dans ~/.claude/skills/ : les conventions de code ne seront PAS chargees."}'
```

Le `||` évite l'échec silencieux : si le skill manque, la session le dit au lieu
de tourner sans conventions. Vérifié sur les deux chemins.

**Chaîne validée de bout en bout au redémarrage** : la consigne arrive entière
dans le contexte, elle déclenche `Skill(djc)`, et le skill se charge réellement.

> **Ce que cette version perd.** L'ancienne injectait le skill **de force** ;
> celle-ci **demande** à l'agent de le charger. La garantie repose donc sur
> l'obéissance à la consigne, pas sur le harnais. En échange, l'échec devient
> **visible** — un skill non chargé se voit dans la conversation, là où la
> persistance silencieuse de 56 Ko ne se voyait nulle part. Le durcissement est
> dans `AGENTS.md` : *ne réponds à aucune question de convention de code sans
> l'avoir chargé*.

> Le hook ne prend effet qu'à la **session suivant** sa création : le surveillant
> de configuration ne suit que les dossiers qui portaient déjà un fichier de
> réglages au démarrage, et `.claude/` n'existait pas.

## 2. `AGENTS.md` pointait vers le dossier de mémoire de l'ancienne machine

La table « Où trouver le reste » codait en dur
`~/.claude/projects/-home-jonas-Gits-Hypostasia/memory/`. Ce nom est le chemin
du dépôt aplati : il **change à chaque machine**. Un agent qui suit la consigne
« à lire en premier » lisait donc un dossier vide, sans que rien ne le signale.

Remplacé par la forme générique, plus un encart qui explique la règle de nommage
et interdit d'y recoder un chemin en dur.

## 3. La fiche mémoire du kit borgwarehouse renvoyait à des dossiers absents

`kit-de-sauvegarde-borgwarehouse` citait `/home/jonas/Gits/borgwarehouse/scripts/`
et `/home/jonas/Gits/ghost/scripts/`. Ni l'un ni l'autre n'existe ici.

**Sans conséquence sur `make backup`** : les scripts réels sont dans `bin/`, et
aucun ne code de chemin externe en dur (vérifié par `grep` sur `bin/` et le
`Makefile`). Le kit n'est qu'une **référence**. La fiche le dit maintenant.

## Ce qui allait déjà

Vérifié sans correction nécessaire : le lien `CLAUDE.md` → `AGENTS.md` ; le lien
`~/.claude/skills/djc` → `/home/ubuntu/Lespass/TECH_DOC/SKILLS/djc` (cible
présente) ; les 16 fiches de mémoire + `MEMORY.md` ; `staticfiles/` et `media/`
en `ubuntu:ubuntu` (pas le piège `root:root`) ; `DEBUG=true` avec
`NGINX_CONF=dev.conf` ; le Traefik partagé `traefik-wildcard` sur 80/443 et le
réseau `frontend` ; les quatre conteneurs et les **deux** workers Celery.

## Fichiers touchés

| Fichier | Nature |
|---|---|
| `.claude/settings.json` | **créé** (hors git) |
| `AGENTS.md` | chemin de mémoire corrigé + encart |
| `CHANGELOG/2026-08-16-remise-en-etat-apres-changement-de-machine.md` | ce fichier |
| mémoire : `trois-vehicules-pour-les-regles`, `kit-de-sauvegarde-borgwarehouse`, `MEMORY.md` | hors dépôt |

---

## Comment tester (à la main) / Manual test

**1. Le hook se déclenche et le skill se charge.** Ouvrir une **nouvelle**
session Claude Code dans le dépôt : l'agent doit appeler `Skill(djc)` de
lui-même, avant toute autre chose. Lui demander ensuite une convention que seul
`djc` porte (par exemple : « quel type de ViewSet DRF pour une vue neuve ? »).

Si le hook ne semble pas tirer, ouvrir `/hooks` une fois (cela recharge la
configuration) ou redémarrer.

**2. La sortie du hook reste petite.** C'est le point qui a cassé une fois :
au-delà du seuil, le harnais persiste la sortie dans un fichier au lieu de
l'injecter, **sans erreur**. Depuis le dépôt :

```bash
eval "$(jq -r '.hooks.SessionStart[0].hooks[0].command' .claude/settings.json)" | wc -c
```

Doit afficher **quelques centaines d'octets** (494 au 16 août 2026). Plusieurs
dizaines de milliers = la régression est de retour, quoi qu'en dise le succès
apparent du hook.

**3. Le chemin de repli.** Simuler l'absence du skill :

```bash
HOME=/nonexistent bash -c \
  "$(jq -r '.hooks.SessionStart[0].hooks[0].command' .claude/settings.json)" \
  2>/dev/null | jq -r '.systemMessage'
```

Doit afficher le message d'échec, **pas** une sortie vide.

**4. Le dossier de mémoire.** `ls ~/.claude/projects/` doit rendre un dossier
dont le nom est le chemin du dépôt aplati, et il doit contenir `memory/MEMORY.md`.
