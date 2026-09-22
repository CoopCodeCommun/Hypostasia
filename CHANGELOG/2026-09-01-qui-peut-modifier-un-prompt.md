# Qui peut modifier un prompt / Who may edit a prompt

**Date :** 2026-09-01
**Migration :** **Oui** —
`hypostasis_extractor/0041_la_preference_d_analyseur_et_les_prompts_d_origine`
(schéma **et** données : elle a estampillé **3** analyseurs sur la base de dev).
`docker exec -w /app hypostasia_web python manage.py migrate`

## Résumé / Summary

**Quoi / What :** le panneau des analyseurs s'ouvre à tout utilisateur connecté.
Chacun crée et modifie **ses** analyseurs. Les **prompts d'origine** et les
**trois champs à portée globale** restent au superutilisateur. Et pour choisir
son analyseur sans l'imposer à personne, il y a désormais une **préférence par
utilisateur**.
/ The panel opens to every signed-in user; original prompts and the three
global-reach fields stay superuser-only; a per-user preference replaces
"check the default".

**Pourquoi / Why :** la configuration était entièrement fermée au staff — un
prompt qu'on ne peut pas lire ne se discute pas. Mais l'ouvrir sans distinction
aurait donné à n'importe qui le moyen de détourner la production de **tout le
monde**.

## Trois portes vers le détournement, pas une / Three doors, not one

Chacun de ces champs suffit, à lui seul, à faire passer **tous** les gestes —
**y compris la passe de nuit, qui est facturée** — par l'analyseur de n'importe
qui. Ils restent donc au superutilisateur, même sur un analyseur ordinaire :

| Champ | Ce qu'il suffirait de faire |
|---|---|
| `est_par_defaut` | cocher son propre analyseur : tous les gestes le prennent |
| `type_analyseur` | le déplacer laisse le type de **départ** sans aucun défaut ; la résolution retombe alors sur l'**ordre alphabétique**, qu'il suffit de gagner en se nommant « AAA » |
| `is_active` | retirer un analyseur de tous les sélecteurs |

## La préférence remplace « cocher le défaut » / A preference instead

`PreferenceD_analyseur(utilisateur, type_analyseur, analyseur)` — une seule par
personne et par type. `POST /api/analyseurs/{id}/preferer/`.

**Elle n'engage que son auteur** : elle préremplit **son** sélecteur, et rien
d'autre. L'ordre de résolution devient :

```
le geste (?analyseur_id=)  →  MA préférence  →  le défaut du site  →  repli journalisé
```

**Elle ne rejoue rien.** Le choix réel se fige sur le job au moment du geste :
changer sa préférence n'atteint aucune production passée, ni aucune déjà en file.
Une préférence qui désigne un analyseur devenu inactif vaut comme absente.

## Les prompts d'origine / Original prompts

`AnalyseurSyntaxique.est_d_origine` — **un champ, pas une comparaison de noms** :
un renommage ne déverrouille rien. La migration estampille les trois analyseurs
posés par l'installation ; les fixtures estampillent ce qu'elles créent.

Ce sont ceux sur lesquels **tout le site retombe**. Une modification malheureuse
s'y propagerait à toutes les productions, sans qu'aucun écran ne l'annonce.

## Ne pas offrir un geste impossible / Never offer an impossible gesture

Le refus fonctionnait (`403`), mais **HTMX ne swappe pas sur 4xx** : un compte
sans droit cliquait « Sauver » et **rien ne se passait, sans le moindre
message**. Constaté au navigateur, pas en test.

L'écran n'offre donc plus que ce qui est permis. Pour un compte ordinaire devant
un prompt d'origine, **mesuré à l'écran** : 4 zones de texte sur 4 en lecture
seule, 0 bouton « Sauver », sélecteur de type désactivé, bascules globales
absentes, et une phrase qui dit pourquoi et quoi faire à la place.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/models.py` | `est_d_origine` ; `PreferenceD_analyseur` |
| `hypostasis_extractor/migrations/0041_…` | le champ, le modèle, et l'estampillage des trois analyseurs |
| `hypostasis_extractor/views.py` | `_exiger_de_pouvoir_creer()`, `_exiger_de_pouvoir_modifier()`, `_refus_de_modifier()` ; **21** gardes converties ; les trois champs globaux ; l'action `preferer` ; `peut_modifier` et `est_superutilisateur` au gabarit |
| `hypostasis_extractor/services/__init__.py` | la garde d'utilisabilité couvre les **deux** types qui rédigent |
| `hypostasis_extractor/templates/…/analyseur_editor.html` | lecture seule, bascules globales masquées, message explicatif |
| `hypostasis_extractor/templates/…/includes/piece_row.html` | boutons et édition sous condition |
| `hypostasis_extractor/templates/…/configuration_llm.html` | l'en-tête gardait deux colonnes dont les cellules avaient disparu ; le texte d'aide décrivait des réglages supprimés |
| `front/views_synthese.py` | `_redacteur_prefere_de()` dans la résolution |
| `front/services/fixtures_analyseurs.py` | estampille ce qu'elle pose |
| `hypostasis_extractor/tests/test_qui_peut_modifier_un_prompt.py` | **neuf** — 16 tests |
| `front/tests/test_utilisabilite_analyseur.py` | le test « toujours utilisable » épinglait un contrat qui a changé |

---

## Comment tester (à la main) / Manual test

### Test 1 — un compte ordinaire lit tout, ne casse rien

1. Se connecter avec un compte **ni staff ni superuser**.
2. Ouvrir `/api/analyseurs/`.
3. **Attendu** : la liste s'affiche, les trois analyseurs sont lisibles.
4. Ouvrir « Rédacteur d'article ».
5. **Attendu** : tous les champs en lecture seule, **aucun** bouton « Sauver »,
   le sélecteur de type grisé, aucune bascule « par défaut », et le message
   « Ce prompt vient de l'installation… Dupliquez-le pour écrire le vôtre. »

### Test 2 — il crée le sien et le modifie

1. Bouton **+ Nouveau**, créer « Mon rédacteur », type « Rédiger un article ».
2. **Attendu** : création acceptée, et l'éditeur permet d'ajouter des morceaux
   de prompt et de les sauver.
3. Tenter de le marquer « par défaut » : **refusé**, avec le message qui renvoie
   vers la préférence.

### Test 3 — la préférence n'engage que soi

```bash
docker exec -w /app hypostasia_web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','hypostasia.settings')
django.setup()
from hypostasis_extractor.models import PreferenceD_analyseur, AnalyseurSyntaxique
for p in PreferenceD_analyseur.objects.select_related('utilisateur','analyseur'):
    print(p.utilisateur, '|', p.type_analyseur, '->', p.analyseur.name)
print('--- défauts du site (inchangés) ---')
for a in AnalyseurSyntaxique.objects.filter(est_par_defaut=True):
    print(' ', a.type_analyseur, '->', a.name, '| origine:', a.est_d_origine)
"
```

**Attendu** : la préférence apparaît pour son auteur seul ; les défauts du site
n'ont pas bougé.
