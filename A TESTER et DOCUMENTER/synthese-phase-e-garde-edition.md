# Synthèse phase E — le blocage d'édition d'une source citée

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
