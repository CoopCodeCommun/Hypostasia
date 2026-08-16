# Couche synthese, phase E : le blocage d'edition d'une source citee

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** SPEC-synthese § 5 : editer un ElementDocument dont une
portion appartient a une extraction citee par une synthese DIRIGEE est
refuse — la preuve d'un acte adopte ne bouge pas. Un wiki ne bloque
rien (il est vivant, le tour suivant corrige).
- `EditionBloqueeParUneSynthese` + `verifier_qu_aucune_synthese_ne_cite`
  (element) + `verifier_qu_aucune_synthese_ne_cite_la_page`
  (reingestion) dans garde_edition.py. Le refus NOMME la synthese et sa
  date (§ 5.3) ; seuls les liens CITE gelent (jamais les liens de
  versionnage historiques).
- Six sites gardes, juste apres verifier_qu_aucune_analyse_ne_tourne :
  reconciliation, masquage, demasquage, scission, fusion (les DEUX
  elements), reingestion (page entiere).
- ATTENTION AU M2M : citer une extraction gele TOUS les elements
  qu'elle traverse — une preuve coupee en deux n'est plus une preuve.
- La reconciliation reste intacte (§ 5.2) : elle repositionne les
  ancres des editions AUTORISEES ; le blocage protege les actes dates.

| Fichier | Changement |
|---|---|
| `hypostasis_extractor/services/garde_edition.py` | + exception + 2 gardes |
| `reconciliation.py`, `masquage.py`, `moteur_structure.py`, `reingestion.py` | + appels aux 6 sites |
| `core/tests/test_garde_synthese.py` | 7 tests (§ 12 + masquage, scission, lien non-CITE) |

115 tests extractor relances : aucune regression.

### Relecture / Review
Relecture adverse des lots D+E passee (9 aout soir), 3 bloquants et
4 importants corriges avec leurs tests :
- **B1** : la garde § 4.2 de run_langextract_job etait placee APRES
  l'appel LLM — on payait des minutes de modele pour un job voue au
  refus. Hissee AVANT l'appel (et gardee en profondeur avant la purge).
- **B2** : « nettoyer les extractions IA » sur une page citee par une
  dirigee faisait un 500 au milieu du delete. Garde § 4.2 en amont dans
  la vue analyser, refus 409 FALC, l'extraction citee survit.
- **B3** : le figement du perimetre (.set d'ids captures avant l'appel)
  pouvait exploser sur une extraction purgee PENDANT la generation et
  perdre la synthese entiere — re-requete des survivantes.
- **I1** : le blocage du DEMASQUAGE etait un sur-blocage qui enfermait
  (element masque par erreur puis cite -> plus jamais demasquable) :
  retire — le demasquage verifie le hash et rend la preuve PLUS fidele.
  La garde § 5 couvre donc CINQ sites, pas six.
- **I2** : les ecartees d'une dirigee HISTORIQUE (perimetre jamais
  fige) auraient annonce « 100 % ecarte » : refus explicite
  (PerimetreDExtractionsInconnu) plutot qu'un mensonge a charge.
- **I4** : fusion (le SECOND element bloque aussi) et reingestion page
  desormais testees. **I5** : verifier_les_citations=False depuis la
  reingestion (la garde page est un sur-ensemble). **M6/M8/M9** :
  filtre « citable » unique, fixtures sur statuts morts corrigees,
  no-op « deja masque » avant la garde.
- **I3 (decision a trancher, consignee § 14 de la spec)** : le seul
  chemin d'edition de texte REELLEMENT expose aujourd'hui (editer_bloc,
  ancien moteur) n'est pas garde — le § 5.2 l'exonere explicitement,
  mais sa justification (« reconciliation.py rend l'interdiction
  inutile ») ne tient pas sur l'ancien moteur. Le gel effectif attend
  le branchement du moteur element, ou une decision inverse.

### Migration
- **Migration necessaire / Migration required :** Non.

---

## Ce qui a été fait

SPEC-synthese § 5 : un élément dont une portion appartient à une
extraction citée par une synthèse DIRIGÉE ne s'édite plus — ni
correction (réconciliation), ni masquage/démasquage, ni scission, ni
fusion, ni réingestion de la page. Un wiki ne bloque rien.

- `EditionBloqueeParUneSynthese` : le message nomme la synthèse et sa
  date (« Ce passage est cité par « Synthèse du 12 mars »… retirez la
  citation ou produisez une nouvelle synthèse »).
- `verifier_qu_aucune_synthese_ne_cite(element)` +
  `verifier_qu_aucune_synthese_ne_cite_la_page(page)` dans
  garde_edition.py ; liens `type_lien=CITE` seulement.
- M2M : citer une extraction gèle TOUS les éléments qu'elle traverse.

## Tests a réaliser

### Suites automatiques
```bash
docker exec hypostasia_dev_web python manage.py test \
  core.tests.test_garde_synthese \
  hypostasis_extractor.tests.test_garde_edition \
  hypostasis_extractor.tests.test_masquage_et_reingestion \
  hypostasis_extractor.tests.test_moteur_structure \
  hypostasis_extractor.tests.test_reconciliation --noinput
```

### Test manuel (shell — le moteur élément n'a pas encore de vues)
```bash
docker exec hypostasia_dev_web python manage.py shell -c "
from core.models import SourceLink, TypeLien
lien = SourceLink.objects.filter(type_lien=TypeLien.CITE,
    page_cible__type_de_note='synthese',
    ancrage_source__isnull=False).first()
if lien:
    element = lien.ancrage_source.element
    from hypostasis_extractor.services.reconciliation import reconcilier_les_portions_de_l_element
    try:
        reconcilier_les_portions_de_l_element(element, element.texte + ' x')
        print('PROBLEME : édition passée')
    except Exception as e:
        print('Refus attendu :', e)
else:
    print('Aucune citation ancrée en base (produire une synthèse d’abord)')"
```

## Relecture adverse (9 août soir) — corrigé
- Garde § 4.2 hissée AVANT l'appel LLM dans run_langextract_job (B1) ;
  « nettoyer les extractions IA » répond un 409 FALC au lieu d'un 500
  (B2) ; le figement du périmètre survit à une purge concurrente (B3) ;
  le DÉMASQUAGE n'est plus bloqué (I1 — il rend la preuve plus fidèle,
  le bloquer enfermait) ; écartées d'une dirigée historique refusées
  explicitement (I2, PerimetreDExtractionsInconnu) ; fusion (2e
  élément) et réingestion page testées (I4) ; garde citation non
  répétée par élément dans la réingestion (I5).

## Compatibilité / limites
- Les vues du moteur élément n'existent pas encore (phases H-K de
  l'ancrage) : le message FALC § 5.3 vit dans l'exception, à afficher
  au branchement du moteur.
- **Décision du propriétaire (9 août)** : `editer_bloc` (ancien moteur)
  reste non gardé — au plus simple, le gel effectif du § 5 sera livré
  avec le branchement du moteur élément. Consigné question n°5 de la
  spec.
- TOCTOU : la garde précède le verrou (même fenêtre que la garde
  d'analyse existante, cohérent et assumé).

