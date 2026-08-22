# L'histoire d'un wiki, la passe de nuit et le récapitulatif du matin / A wiki's history, the nightly pass and the morning recap

**Date :** 2026-08-21
**Migration :** **Oui** — `core.0074_tourdewiki_operationdewiki`,
`core.0075_passedenuit_envoidurecapitulatif`,
`core.0076_compteur_de_la_passe_de_nuit`,
`core.0077_borne_haute_du_recapitulatif`,
`core.0078_une_seule_passe_ouverte` et `core.0079_un_echec_est_un_tour`
(`docker compose exec web python manage.py migrate core`)
**Redémarrage exigé :** **Oui** — trois tâches Celery neuves.
`make restart S=celery_worker`, sinon le worker tourne avec l'ancien code et
ne sait pas les exécuter (constaté le jour même).

## Resume / Summary

**Quoi / What :** un wiki garde desormais son **histoire**. Chaque ecriture de
son corps ecrit un `TourDeWiki` — **quand**, **par qui** (un humain nomme, ou
`NULL` = le moteur), **pourquoi** (combien d'extractions et de commentaires
neufs depuis le tour precedent, et quelles notes les ont apportes), le texte
**avant** et **apres** — et une `OperationDeWiki` par operation du lot : sa
section, ce qu'elle a **ajoute**, ce qu'elle a **remplace**, les extractions
qu'elle cite, et **son motif de rejet** quand elle a ete refusee.
/ Every wiki body write now records a round: when, by whom, why, before/after,
and one line per operation — additions, replacements, and refusals with reasons.

**Deux mecanismes neufs par-dessus :** une **passe de nuit** qui met les wikis a
jour toute seule (elle propose ET applique), et un **recapitulatif du matin**,
un mail par personne et par jour au maximum, qui annonce les wikis modifies —
humains comme automatiques — et ceux dont le perimetre a recu du neuf non
repris. **Le mail part toujours APRES le run de la nuit** : il interroge la
`PasseDeNuit`, attend qu'elle finisse, et **refuse d'envoyer** plutot que
d'annoncer un travail a moitie fait.
/ A nightly pass that proposes AND applies, plus a once-a-day recap mail that
always waits for the night run to finish.

**LA PLANIFICATION VIT DANS L'APPLICATION.** `hypostasia/celery.py`
(`beat_schedule`) declare les deux rendez-vous, un programme `celery_beat` les
declenche, et les heures se reglent par `HEURE_PASSE_DE_NUIT` et
`HEURE_RECAPITULATIF` (UTC, defaut 2 h et 6 h). Pas de `django-celery-beat` :
sa valeur ajoutee est de piloter l'horaire depuis l'**admin Django**, qui est
desactive dans ce projet — il couterait une dependance, une migration et deux
tables pour un ecran qui n'existe pas. Pas de cron d'hote non plus : il vit
hors du depot, ne se relit pas en revue, et un clone frais ne l'a pas.
**`celery_beat` n'est pas un quatrieme worker** : il ne consomme aucune file et
ne prend aucun slot — la topologie des trois workers reste vraie.
/ The schedule lives in the app's code, not in a host crontab.

**LE RECAPITULATIF SURVEILLE SIX CHOSES**, pas seulement les wikis : les wikis
**modifies** (en disant quelle note les a appeles), les **commentaires** neufs —
avec leur **texte**, leur **auteur** et un bouton **« Reagir »** qui ouvre la
note commentee —, les **articles neufs** (wikis et syntheses), les **notes
neuves**, les **carnets publics** qui viennent d'apparaitre, et les wikis dont
le perimetre porte du **neuf non repris**. Le titre du mail est « Ce qui a bouge
sur Hypostasia.org ».

**ON NE S'ANNONCE JAMAIS A SOI-MEME CE QU'ON VIENT DE FAIRE.** Sa propre note,
son propre commentaire, son propre tour accepte, son propre carnet public : le
lendemain matin, leur auteur le sait deja. Les lui raconter ferait du
recapitulatif un accuse de reception — et c'est l'utilisateur le PLUS ACTIF qui
recevrait le plus de bruit, donc celui qui cesserait de le lire le premier.
**Une exception, et une seule : ce que LE MOTEUR a fait.** Un tour de la passe
de nuit sur mon wiki est une nouvelle pour moi, puisque je ne l'ai pas decide —
c'est meme la seule facon de l'apprendre sans ouvrir l'article. Mesure sur la
base de dev : le destinataire le plus actif passe de 20 lignes annoncees a 7.
/ One is never told what one did oneself — except what the engine did.

**Le perimetre n'est pas le meme partout, et c'est deliberé.** Le CONTENU
(notes, commentaires, articles) ne porte que sur les carnets qu'on **suit** —
les siens et ceux qu'on lui a partages. Les carnets **publics** de tiers ont
leur propre rubrique, qui annonce le **carnet** et jamais son contenu : cent
notes importees dans un carnet public arroseraient sinon tout le monde.
/ Followed notebooks for content; public ones only announce themselves.

**LA PASSE EST UN FAN-OUT, plus une boucle sequentielle.** Une tache Celery par
wiki, sur la file par defaut : les appels au redacteur avancent a la
concurrence du worker, et chacun tient largement sous le plafond de 30 minutes
(`CELERY_TASK_TIME_LIMIT`) — la ou une passe sequentielle de vingt wikis le
crevait. Aucune tache ne sait si elle est la derniere : chacune incremente
`PasseDeNuit.wikis_termines` de facon **atomique** en rendant la main, et celle
qui rejoint le total ferme la passe. C'est cette fermeture que le matin attend.
/ One task per wiki; an atomic counter closes the pass.

**Pourquoi / Why :** le moteur produisait toute la matiere de sa propre
tracabilite — les operations appliquees **avec l'ancien contenu**, les rejets
**avec leur motif**, le compte des nouveautes — puis la jetait. Il ne restait
qu'un compteur, `Wiki.tours_de_mise_a_jour`, et une date **ecrasee** a chaque
tour. Sur un wiki suivi depuis six semaines, personne ne pouvait dire quand un
paragraphe etait entre, pourquoi, ni ce qu'il avait remplace — et rien ne
distinguait ce qu'un collegue avait ecrit de ce que la machine avait complete.
/ The engine produced its own traceability, then threw it away.

**Ce que ca contredit, et qui est assume :** `SPEC-synthese-carnet.md § 6.1`
reservait l'application a un humain, et le § 11.3 classait le journal des
acceptations « YAGNI pour le POC ». Les deux changent, par decision du
mainteneur du 21 aout 2026 — **encart date en tete de la spec**. Ce qui ne
change pas : **tous** les controles mecaniques du § 6.2/6.3, et l'interdit qui
les tient tous — **un wiki ne se regenere jamais**.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `PLAN/specs/SPEC-synthese-carnet.md` | **Encart date du 21 aout** : le journal n'est plus YAGNI, la nuit applique, et ce qui la borne |
| `core/models.py` | **Neufs :** `MotifDeTourDeWiki`, `TypeOperationDeSection`, `TourDeWiki`, `OperationDeWiki`, `PasseDeNuit`, `EnvoiDuRecapitulatif` |
| `core/services/historique_de_wiki.py` | **Neuf.** Ecrit un tour et ses operations depuis le bilan de l'applieur ; les sources viennent des marqueurs `[[ext:N]]` |
| `core/services/destinataires_de_wiki.py` | **Neuf.** Proprietaire de l'article + proprietaires des carnets + **partages** (utilisateurs et membres de groupes), sans adresse vide |
| `core/services/recapitulatif_du_matin.py` | **Neuf.** Six rubriques : wikis modifies, commentaires (texte + auteur), articles neufs, notes neuves, carnets publics, wikis en retard sur leur perimetre. `carnets_suivis_par()` porte le perimetre du contenu. Ce qu'il y a a dire, par personne : modifies, et « du neuf non repris » — « du neuf » exige quelque chose d'APPARU depuis le dernier mail, sinon c'est un rappel quotidien. Un tour qui n'a rien change, et une **reparation de titres**, ne font pas un mail |
| `core/services/passe_de_nuit.py` | **Neuf.** Deux pannes silencieuses : deux passes en meme temps (facture doublee), et une passe **morte** dont `terminee_le` reste NULL — elle bloquerait le mail pour toujours. Au-dela de **12 h**, une passe est declaree abandonnee |
| `front/tasks.py` | `_ecrire_le_corps_d_un_article` **refuse** un wiki sans motif de tour ; `appliquer_un_tour_de_wiki` (vue **et** nuit) ; `construire_la_proposition_d_operations` extrait de la tache ; `mettre_a_jour_un_wiki_la_nuit` ; `_demandeur_du_job` |
| `front/views_synthese.py` | `appliquer` passe par le chemin commun ; nouvelle action `GET /wikis/{id}/historique/` |
| `front/management/commands/mettre_a_jour_les_wikis.py` | **Neuf.** La passe de nuit : `--maximum`, `--a-blanc`, une erreur n'arrete pas les autres |
| `front/management/commands/envoyer_le_recapitulatif_du_matin.py` | **Neuf.** Attend la nuit, un mail par jour, `--a-blanc`, `--destinataire`, `--sans-attendre-la-nuit` |
| `front/templates/front/emails/recapitulatif_du_matin.{txt,html}` | **Neufs.** Six rubriques ; bouton **« Reagir »** sur chaque commentaire. **L'autoescape est coupe dans le `.txt` seulement** : Django y transformait « C'est » en « C&#x27;est ». Le HTML le GARDE — un commentaire est du contenu d'utilisateur |
| `front/templates/front/corpus/partials/historique_de_wiki.html` | **Neuf.** Le depliant d'historique — classes existantes, aucun CSS neuf (build Tailwind fige) |
| `front/templates/front/corpus/article.html` | Ligne depliante « Historique » dans l'en-tete, a cote d'« Ecartees » |
| `hypostasia/celery.py` | **`beat_schedule`** : les deux rendez-vous, en UTC, reglables par variables d'environnement |
| `supervisord.conf`, `supervisord-dev.conf` | Programme **`celery_beat`** — il ne consomme aucune file, donc la topologie des trois workers reste vraie. **`autostart=true` des deux cotes** : meme topologie en dev qu'en prod |
| `bin/nuit.sh`, `Makefile` | **Neuf.** `make nuit` et `make recapitulatif` — la porte **manuelle**. **Ne pas poser ce script dans un cron** : la passe partirait deux fois |

### Tests

| Fichier | Ce qu'il verrouille |
|---|---|
| `core/tests/test_historique_de_wiki.py` (12) | le tour, ses operations, l'ancien contenu d'un remplacement, le motif d'un rejet, les sources derivees des marqueurs, la raison figee |
| `core/tests/test_aucun_corps_de_wiki_sans_tour.py` (3) | la garde : ecrire un wiki sans motif est **refuse**, et le refus n'ecrit rien |
| `core/tests/test_destinataires_de_wiki.py` (5) | proprietaires, partages directs, membres de groupe, adresse vide ecartee, aucun doublon |
| `core/tests/test_l_etat_de_la_passe_de_nuit.py` (5) | une passe trop vieille est fermee, une passe recente reste en cours |
| `core/tests/test_le_planificateur.py` (8) | chaque tache planifiee **existe**, le beat est declare dans les DEUX topologies, il n'y en a **qu'un**, il ne consomme aucune file |
| `front/tests/test_la_passe_de_nuit_des_wikis.py` (28) | signe par le moteur, un lot rejete laisse l'article **identique**, `--maximum` compte ce qu'il ecarte, `--a-blanc` n'ecrit rien, une erreur n'arrete pas les autres, **deux passes ne tournent jamais ensemble** |
| `front/tests/test_le_recapitulatif_du_matin.py` (42) — dont l'auto-notification | le mail **suit** la nuit, un seul par jour, rien a dire = rien envoye, une reparation de titres ne fait pas un mail, les partages recoivent, un echec SMTP n'arrete pas les suivants |
| `front/tests/test_l_ecran_de_l_historique.py` (9) | le moteur annonce comme tel, la raison chiffree, l'avant d'un remplacement, le rejet avec son motif, **les marqueurs `[[ext:N]]` ne sont pas montres** |

---

## Comment tester (a la main) / Manual test

### Test 1 — l'histoire d'un tour demande a la main

1. `make dev`, ouvrir un carnet qui porte un wiki (`/carnets/`).
2. Sur l'ecran de l'article, deplier **« Historique »** dans l'en-tete : sur un
   wiki d'avant aujourd'hui, il dit qu'aucune histoire n'a ete gardee — c'est
   normal, le moteur ne l'ecrivait nulle part.
3. Cliquer **« Mettre a jour »**, attendre la proposition, **n'accepter qu'une
   operation sur deux**, appliquer.
4. Redéplier « Historique » : le tour doit nommer **l'auteur** (vous), la
   **raison chiffree** (« N nouvelles extractions, N nouveaux commentaires,
   depuis le … »), **l'ajout** section par section, et — si l'applieur en a
   refuse — le **motif du refus** avec le contenu conserve.
5. Verifier qu'un **remplacement** affiche « À la place de : … ».

### Test 2 — la passe de nuit

```bash
# Ce qui partirait, sans rien appeler ni ecrire :
docker compose exec web python manage.py mettre_a_jour_les_wikis --a-blanc

# Pour de vrai — ATTENTION, un appel au redacteur par wiki, c'est facture.
# `--attendre` est INDISPENSABLE si l'on veut lire le resultat juste apres :
# sans lui la commande rend la main des la mise en file, et rien n'est
# encore ecrit.
docker compose exec web python manage.py mettre_a_jour_les_wikis \
    --maximum 1 --attendre
```

Puis, en base :

```bash
docker compose exec web python manage.py shell -c "
from core.models import TourDeWiki, PasseDeNuit
tour = TourDeWiki.objects.first()
print(tour, '| par le moteur :', tour.est_fait_par_le_moteur)
print('a change l article :', tour.a_change_l_article)
for operation in tour.operations.all():
    print('  ', operation, '|', operation.section, '|', operation.motif_de_rejet[:60])
print(PasseDeNuit.objects.first())
"
```

À verifier : `fait_par` est **NULL**, `motif` vaut `maj_nocturne`, et le
`text_readability` de l'article **contient encore ce qu'il disait avant** — la
nuit ajoute, elle ne regenere pas.

### Test 3 — le recapitulatif du matin

```bash
# Qui recevrait quoi, rubrique par rubrique, sans envoyer :
docker compose exec web python manage.py envoyer_le_recapitulatif_du_matin --a-blanc

# CE QUE DONNERAIT UN MOIS CHARGE, envoye a une seule adresse et
# sans consommer la journee de personne :
docker compose exec web python manage.py envoyer_le_recapitulatif_du_matin \
    --adresse-de-test moi@exemple.fr --depuis-jours 30

# L'envoi (backend console en dev : le mail s'imprime dans les journaux) :
docker compose exec web python manage.py envoyer_le_recapitulatif_du_matin

# LE RELANCER : il ne doit RIEN envoyer la seconde fois.
docker compose exec web python manage.py envoyer_le_recapitulatif_du_matin
```

Pour verifier qu'il **attend la nuit**, ouvrir une passe a la main puis relancer :

```bash
docker compose exec web python manage.py shell -c "
from core.models import PasseDeNuit; PasseDeNuit.objects.create()"
docker compose exec web python manage.py envoyer_le_recapitulatif_du_matin \
    --attendre-minutes 0
# -> CommandError : « la passe de nuit tourne encore », et AUCUN mail.
```

Ne pas oublier de refermer la passe ouverte a la main :

```bash
docker compose exec web python manage.py shell -c "
from core.models import PasseDeNuit
from django.utils import timezone
PasseDeNuit.objects.filter(terminee_le__isnull=True).update(terminee_le=timezone.now())"
```

### Ce que la relecture adverse a corrige (21 aout, apres coup)

- **Le critere de reprise porte sur le dernier ESSAI, pas sur la derniere
  reussite.** `derniere_mise_a_jour` n'avance que si une operation est
  appliquee : un lot entierement rejete la laissait en arriere, et la meme
  nouveaute rappelait le redacteur **chaque nuit**, pour le meme rejet.
  `borne_du_dernier_essai` lit `TourDeWiki.fait_le`, ecrit meme pour un lot
  rejete.
- **Un lot de `no_change` ne prend plus le chemin d'ecriture.** L'applieur
  l'ACCEPTE (c'est une operation legitime), mais accepter n'est pas changer.
- **La borne haute d'un envoi est l'instant du CALCUL**, pas l'heure d'envoi :
  ce qui naissait pendant que les mails partaient n'etait raconte ni ce
  matin-la ni le lendemain.
- **« Un mail par jour » est devenu mecanique** : la garde regarde les envois
  des 20 dernieres heures. Avant, une relance a la main apres l'arrivee d'un
  commentaire renvoyait un second mail le meme jour.
- **`bin/nuit.sh tout` attend la fin de la passe** (`--attendre`) : la commande
  ne faisant plus que mettre en file, le recapitulatif partait avant que la
  passe n'existe — la promesse centrale, cassee par sa propre porte manuelle.
- **Le compte de tours du depliant vient des tours ecrits**, pas du compteur du
  wiki : les deux divergent des le premier lot rejete.
- **L'auto-notification est retiree** (decision du mainteneur, apres la
  relecture) : on ne recoit plus l'annonce de ses propres gestes, sauf ceux du
  moteur.
- **UN ECHEC EST UN TOUR** (motif `ECHEC`, champ `message_d_echec`). Sans lui,
  une tache qui echoue ne laissait RIEN : pas de tour, donc pas d'avancee de la
  borne, donc le meme wiki rappelait le redacteur chaque nuit — sans backoff,
  sans plafond, et invisiblement. Atomic resout le meme probleme par un ledger a
  backoff exponentiel (`max_attempts = 3`) ; nous le resolvons en ecrivant
  l'echec dans l'histoire de l'article, ou le lecteur le voit.

### Test 4 — la planification

Rien a poser : elle est dans le code. Ce qu'il faut verifier une fois :

```bash
make status                      # celery_beat — RUNNING en prod
docker compose logs web | grep "beat: Starting"
```

**Ce que la nuit coute, mesure le 21 aout 2026.** Elle ne reprend un wiki que si
quelque chose est **apparu** dans son perimetre depuis son dernier **essai** —
une nuit sans nouveaute ne coute donc RIEN. Une nuit chargee coute, par wiki
repris : un appel au **redacteur** (Mistral Medium, 5 800 a 17 500 tokens
d'entree, soit **0,022 a 0,038 EUR** aux tarifs de
`AIModel.cout_par_million_tokens`) **plus** un appel au **juge de verification**
sur les citations neuves, qui est une API et donc facture lui aussi. Les quatre
juges locaux, eux, sont gratuits (ils tournent sur la machine).

Pour changer les heures, dans le `.env` (UTC), puis
`make restart S=celery_beat` :

```
HEURE_PASSE_DE_NUIT=2
HEURE_RECAPITULATIF=6
```

`make nuit` et `make recapitulatif` restent la porte **manuelle**.
**Ne jamais poser `bin/nuit.sh` dans un cron** : la passe partirait deux fois
par nuit, et la facture du redacteur avec elle.

### Ce qu'il faut savoir avant de brancher le cron

- **La passe est facturee** : un appel au redacteur par wiki ayant du neuf.
  `--maximum N` borne la nuit, et ce qu'elle ecarte est **compte** dans
  `PasseDeNuit.wikis_ecartes_par_le_maximum`.
- **Chaque tour enchaine les juges** (`verification_locale`, concurrence 1,
  `nice -n 19`) : vingt wikis mis a jour font vingt verifications a la file. Le
  mail du matin peut donc partir **avant** que tous les verdicts soient rendus —
  il annonce la modification, pas le jugement.
- **Deux passes ne tournent jamais ensemble** : la contrainte PostgreSQL
  `une_seule_passe_de_nuit_ouverte` l'interdit — un controle en Python laissait
  passer deux lancements simultanes.
- **Une tache tuee net ne rend PAS la main** (SIGKILL, OOM, plafond de
  30 minutes : le `finally` ne s'execute pas). Le compteur n'atteint alors jamais
  son total, et le recapitulatif — qui attend la fin de la passe — refuserait
  d'envoyer : **un seul wiki tue couterait le mail de tout le monde**. C'est
  pourquoi une passe ouverte depuis plus de **3 h** est declaree abandonnee : le
  delai est calcule pour qu'elle soit fauchee AVANT le mail du matin.
- **L'envoi reel exige `EMAIL_HOST*` dans le `.env`.** Sans eux, le backend par
  defaut est la **console** : les mails s'impriment dans les journaux du
  conteneur et personne ne recoit rien, **sans la moindre erreur**.
