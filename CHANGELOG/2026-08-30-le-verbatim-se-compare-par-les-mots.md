# Le verbatim se compare par les mots / The verbatim check compares words

**Date :** 2026-08-30
**Migration :** Non

## Résumé / Summary

**Quoi / What :** le contrôle verbatim gagne une **troisième passe**. Quand le
test strict et les trois retouches de forme échouent, il compare la **suite des
mots** : ils doivent tous être là, dans l'ordre et sans trou. Ce qui n'est pas un
mot ne compte pas — **sauf les signes qui changent le sens** : parenthèses,
guillemets, deux-points, « ? », « ! », et la virgule entre deux chiffres.
/ A third pass compares the word sequence; non-word characters no longer count,
except the marks that change meaning.

**Pourquoi / Why :** mesuré le 30 août 2026, **45 des 119 citations
`INTROUVABLE` n'avaient aucun défaut de fond** — tous les mots y étaient, dans
l'ordre, d'un seul tenant. Seuls des signes différaient : un tiret cadratin pour
un tiret court (17 cas), un guillemet droit pour une apostrophe (11), un trait
d'union que **notre propre ingestion** avait détaché. Déclarer la chaîne de
preuve cassée sur ce motif fait porter au modèle un défaut qui est le nôtre.

### Ce que ça donne, mesuré

| | résultat |
|---|---|
| les 45 citations au fond intact | **42 récupérées** |
| les 37 sauts + 37 reformulations | **0 blanchi** |
| 225 falsifications fabriquées (négation, quantifieur, chiffre, ponctuation structurante) | **0 blanchie** |
| liens déjà `verifie` ou `faible` | **399 / 400** — inchangé |
| coût | 0,80 ms par citation (0,63 ms avant) |

### Le score de similarité a été mesuré, et écarté

C'était la piste la plus naturelle : un ratio de proximité, un seuil à 99 %. Le
banc la réfute, et le chiffre qui décide est le plus petit de tous.

| | ratio |
|---|---|
| la citation honnête la plus abîmée | **0,9577** |
| la citation **falsifiée** la mieux notée | **0,9977** |
| **changer 2011 en 2012** — un caractère sur cent cinquante | **0,9961** |

Les deux nuages se chevauchent : aucun seuil ne les sépare. À 0,99 on récupère
14 des 45 et on blanchit 72 citations fausses ; à 0,95 on récupère tout et on en
blanchit 182 sur 225. **Une similarité est unidimensionnelle** — elle additionne
« trois signes de ponctuation » et « une date falsifiée » dans le même nombre.

### Les trois décisions qui rendent la passe sûre

**1. Les signes structurants sont EXIGÉS, pas ignorés.** Une première version
ignorait toute la ponctuation. Mesurée, elle blanchissait **17 parenthèses
d'incise retirées sur 19** et **18 guillemets sur 64** — dont
« comme « l'école déscolarise » » rendu sans ses guillemets, où l'auteur
**affirme** ce qu'il rapportait. Ils sont donc comparés, **à la classe près
jamais à la forme près** : `"` et `'` sont le même signe.

**2. Seuls les signes INTÉRIEURS comptent.** Ceux des bords sont ignorés : une
citation honnête peut commencer après une parenthèse ouvrante que la source
porte. Sans cette distinction, 11 citations valides sur 400 étaient refusées.

**3. La coupe dans un mot n'est tolérée que devant une MAJUSCULE.** La base porte
**83 éléments avec des mots soudés** — « participation citoyenneAucun
parlementaire », deux blocs recollés sans séparateur — et une citation honnête
s'y arrête au milieu du mot soudé. Mais tolérer une coupe devant une minuscule
rouvrirait le trou le plus grave du contrôle : « Le vaccin est sur. » se
retrouverait dans « le vaccin est **sur**ement inefficace », et la chaîne de
preuve validerait le contraire de ce que la source dit.

### Ce qui a été gardé, et pourquoi

**La passe « à la forme près » n'est pas supprimée**, bien que la troisième
l'englobe. Elle est dix fois moins chère sur le cas fréquent, et elle est
verrouillée par quinze tests qui disent, un par un, ce que la chaîne de preuve
accepte. Les perdre pour une équivalence supposée, ce serait échanger une
garantie contre un raisonnement.

**La garde de la marque de fin est RÉUTILISÉE telle quelle**
(`_l_occurrence_ne_coupe_pas_une_marque_de_fin`) : elle sait déjà qu'un point
suivi d'un chiffre est une décimale et qu'un signe répété est une ellipse. La
réécrire en aurait fait une seconde copie, qui aurait divergé.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/services/verification.py` | `_signes_structurants`, `_le_bord_correspond`, `_le_verbatim_se_lit_par_les_mots` — **neuves** ; `_le_verbatim_est_present` passe à trois passes |
| `core/tests/test_verbatim_par_les_mots.py` | **neuf** — 19 tests, dont 13 « ne doit JAMAIS » |
| `benchmarks/extraction_format/mesurer_la_comparaison_par_les_mots.py` | **neuf** — le banc, qui **appelle la production** au lieu d'en garder une copie |

### Ce qui n'est PAS fait

- **Rien ne relit les liens déjà `INTROUVABLE`.** Les 42 récupérables le restent
  tant qu'une commande ne repasse pas dessus. Le contrôle n'appelle aucun modèle :
  ce rejugement est **gratuit**, il reste à écrire.
- **Les 3 des 45 non récupérés** portent une parenthèse que la source n'a pas :
  ils sont désormais refusés **à raison**.
- **Les deux défauts d'ingestion découverts** — le trait d'union détaché (8
  éléments) et les mots soudés (83 éléments, 13 notes) — ne sont réparés nulle
  part. La passe les absorbe ; la donnée reste fausse.
- **Une citation peut chevaucher deux éléments, et ce n'est PAS un défaut.**
  Relevé d'abord comme suspect — 60 citations fabriquées à cheval passent, avec
  l'ancienne règle comme avec la nouvelle — puis **démenti sur les données
  réelles** : 4 extractions sur 1 174 ne se lisent dans aucun élément isolé, et
  **les quatre sont correctement ancrées**, en 2 à 4 portions sur des éléments
  contigus. `AncrageExtraction.ordre_dans_extraction` existe pour cela : une
  extraction est une suite de portions. Recoller à la vérification est donc
  cohérent avec le moteur d'ancrage, pas une faille.
  Détail : `PLAN/TODO/2026-08-30-ce-qui-reste-du-verbatim-introuvable.md`, § 3.

---

## Comment tester (à la main) / Manual test

### Test 1 — le banc, qui dit tout d'un coup
```bash
docker exec -w /app hypostasia_web python \
    benchmarks/extraction_format/mesurer_la_comparaison_par_les_mots.py
```
**Attendu** : 42/45 des « ponctuation » passent, 0/37 des sauts et 0/37 des
reformulations, **0 blanchie** dans les huit familles de falsification, et
399/400 en non-régression. Aucun modèle n'est appelé, rien n'est écrit.

### Test 2 — les tests automatiques
```bash
docker exec -w /app hypostasia_web python manage.py test \
    core.tests.test_verbatim_par_les_mots \
    core.tests.test_verbatim_tolerant_a_la_forme --noinput
```
→ **34 tests, OK** (mesuré le 30 août 2026).

La non-régression large :
```bash
docker exec -w /app hypostasia_web python manage.py test \
    core.tests.test_verification core.tests.test_score_de_verification \
    core.tests.test_second_avis_de_verification \
    core.tests.test_avis_perdus_au_report \
    hypostasis_extractor.tests.test_typage_des_non_verbatim --noinput
```
→ **86 tests, OK** (mesuré le 30 août 2026).

### Test 3 — à l'écran, sur un article
1. Ouvrir un article de wiki qui porte des citations marquées « introuvable ».
2. Relancer sa vérification (bouton « vérifier »). **Attention : le juge de
   vérification est une API facturée.**
3. **Attendu** : les citations qui ne différaient que par un tiret, un guillemet
   ou un trait d'union détaché quittent l'état `INTROUVABLE`. Celles qui sautent
   un passage ou reformulent y restent.

### Vérif en base — l'effet, sans rien écrire
```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import ElementDocument, SourceLink
from core.services.verification import _le_verbatim_est_present
liens = [l for l in SourceLink.objects.filter(etat_de_verification='introuvable')
         .select_related('extraction_source__job__page') if l.extraction_source]
passent = 0
for lien in liens:
    page = lien.extraction_source.job.page_id
    textes = list(ElementDocument.objects.filter(page_id=page)
                  .order_by('ordre').values_list('texte', flat=True))
    source = '\n'.join(textes) or (lien.extraction_source.job.page.text_readability or '')
    passent += bool(_le_verbatim_est_present(lien.extraction_source.extraction_text, source))
print(f'{passent} des {len(liens)} liens INTROUVABLE redeviennent verifiables')
"
```
→ **42 des 119** (mesuré le 30 août 2026).
