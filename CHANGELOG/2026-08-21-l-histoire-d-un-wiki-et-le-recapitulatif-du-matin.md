# L'histoire d'un wiki, la passe de nuit et le récapitulatif du matin / A wiki's history, the nightly pass and the morning recap

**Date :** 2026-08-21
**Migration :** **Oui** — `core.0074_tourdewiki_operationdewiki` et
`core.0075_passedenuit_envoidurecapitulatif`
(`docker compose exec web python manage.py migrate core`)

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
repris. **Le mail part toujours APRES le run de la nuit** : la commande
interroge la `PasseDeNuit`, attend qu'elle finisse, et **refuse d'envoyer**
plutot que d'annoncer un travail a moitie fait.
/ A nightly pass that proposes AND applies, plus a once-a-day recap mail that
always waits for the night run to finish.

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
| `core/services/recapitulatif_du_matin.py` | **Neuf.** Ce qu'il y a a dire, par personne : modifies, et « du neuf non repris » — « du neuf » exige quelque chose d'APPARU depuis le dernier mail, sinon c'est un rappel quotidien. Un tour qui n'a rien change, et une **reparation de titres**, ne font pas un mail |
| `core/services/passe_de_nuit.py` | **Neuf.** Deux pannes silencieuses : deux passes en meme temps (facture doublee), et une passe **morte** dont `terminee_le` reste NULL — elle bloquerait le mail pour toujours. Au-dela de **12 h**, une passe est declaree abandonnee |
| `front/tasks.py` | `_ecrire_le_corps_d_un_article` **refuse** un wiki sans motif de tour ; `appliquer_un_tour_de_wiki` (vue **et** nuit) ; `construire_la_proposition_d_operations` extrait de la tache ; `mettre_a_jour_un_wiki_la_nuit` ; `_demandeur_du_job` |
| `front/views_synthese.py` | `appliquer` passe par le chemin commun ; nouvelle action `GET /wikis/{id}/historique/` |
| `front/management/commands/mettre_a_jour_les_wikis.py` | **Neuf.** La passe de nuit : `--maximum`, `--a-blanc`, une erreur n'arrete pas les autres |
| `front/management/commands/envoyer_le_recapitulatif_du_matin.py` | **Neuf.** Attend la nuit, un mail par jour, `--a-blanc`, `--destinataire`, `--sans-attendre-la-nuit` |
| `front/templates/front/emails/recapitulatif_du_matin.{txt,html}` | **Neufs.** Deux sections : « ce qui a change », « ce qui attend » |
| `front/templates/front/corpus/partials/historique_de_wiki.html` | **Neuf.** Le depliant d'historique — classes existantes, aucun CSS neuf (build Tailwind fige) |
| `front/templates/front/corpus/article.html` | Ligne depliante « Historique » dans l'en-tete, a cote d'« Ecartees » |
| `bin/nuit.sh`, `Makefile` | **Neuf.** `make nuit` et `make recapitulatif` ; les deux lignes de cron sont dans l'en-tete du script |

### Tests

| Fichier | Ce qu'il verrouille |
|---|---|
| `core/tests/test_historique_de_wiki.py` (12) | le tour, ses operations, l'ancien contenu d'un remplacement, le motif d'un rejet, les sources derivees des marqueurs, la raison figee |
| `core/tests/test_aucun_corps_de_wiki_sans_tour.py` (3) | la garde : ecrire un wiki sans motif est **refuse**, et le refus n'ecrit rien |
| `core/tests/test_destinataires_de_wiki.py` (5) | proprietaires, partages directs, membres de groupe, adresse vide ecartee, aucun doublon |
| `core/tests/test_l_etat_de_la_passe_de_nuit.py` (5) | une passe trop vieille est fermee, une passe recente reste en cours |
| `front/tests/test_la_passe_de_nuit_des_wikis.py` (16) | signe par le moteur, un lot rejete laisse l'article **identique**, `--maximum` compte ce qu'il ecarte, `--a-blanc` n'ecrit rien, une erreur n'arrete pas les autres, **deux passes ne tournent jamais ensemble** |
| `front/tests/test_le_recapitulatif_du_matin.py` (15) | le mail **suit** la nuit, un seul par jour, rien a dire = rien envoye, une reparation de titres ne fait pas un mail, les partages recoivent, un echec SMTP n'arrete pas les suivants |
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

# Pour de vrai — ATTENTION, un appel au redacteur par wiki, c'est facture :
docker compose exec web python manage.py mettre_a_jour_les_wikis --maximum 1
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
# Qui recevrait quoi, sans envoyer :
docker compose exec web python manage.py envoyer_le_recapitulatif_du_matin --a-blanc

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

### Les deux lignes de cron (a poser sur l'hote)

L'heure est celle de **l'hote** — les settings Django sont en `UTC`.

```cron
0 3 * * * bash /home/ubuntu/Hypostasia/bin/nuit.sh passe         >> /var/log/hypostasia-nuit.log 2>&1
0 7 * * * bash /home/ubuntu/Hypostasia/bin/nuit.sh recapitulatif >> /var/log/hypostasia-nuit.log 2>&1
```

Depuis le depot : `make nuit` et `make recapitulatif` font la meme chose.

### Ce qu'il faut savoir avant de brancher le cron

- **La passe est facturee** : un appel au redacteur par wiki ayant du neuf.
  `--maximum N` borne la nuit, et ce qu'elle ecarte est **compte** dans
  `PasseDeNuit.wikis_ecartes_par_le_maximum`.
- **Chaque tour enchaine les juges** (`verification_locale`, concurrence 1,
  `nice -n 19`) : vingt wikis mis a jour font vingt verifications a la file. Le
  mail du matin peut donc partir **avant** que tous les verdicts soient rendus —
  il annonce la modification, pas le jugement.
- **Deux passes ne tournent jamais ensemble** : la seconde refuse de demarrer.
  Et une passe dont le conteneur a ete tue est declaree **abandonnee** au bout de
  12 h — sans quoi le recapitulatif attendrait sa fin pour toujours, et plus
  personne ne recevrait rien.
- **L'envoi reel exige `EMAIL_HOST*` dans le `.env`.** Sans eux, le backend par
  defaut est la **console** : les mails s'impriment dans les journaux du
  conteneur et personne ne recoit rien, **sans la moindre erreur**.
