# Branchement du moteur d'ancrage — phases BR-A à BR-F

> **Mise à jour du 10 août (nuit) : le branchement BR-A→F est COMPLET.**
> Les sections BR-C à BR-F sont documentées à la fin de cette fiche.

> Écrit le 9 août 2026 (nuit). Réfère : SPEC-ancrage-par-element-v2.md § 9,
> PLAN/branchement-moteur-ancrage-cahier-des-charges.md, CHANGELOG du 9 août.

## Ce qui a été livré

### BR-A — le flag moteur (`Page.moteur`)

- Champ explicite `moteur` sur Page : `ancien` (défaut) ou `element`,
  migration `core/0053_page_moteur.py` **appliquée sur dev**.
- Décision § 9.2 confirmée après découverte : **537 des 541 pages du dev
  portent des éléments DORMANTS** (ingérés par les phases de test du
  moteur, jamais lus par le flux réel). Elles restent TOUTES `ancien` —
  la migration n'estampille rien, c'est un choix documenté dans son
  docstring. La bascule de l'existant sera une reconversion explicite
  (§ 9.5, décision D4, hors périmètre).
- Le flag `element` est posé au point de passage unique :
  `creer_les_elements_d_une_page` (ingestion_docling.py).

### BR-B — l'import de fichier nourrit le moteur ELEMENT

- Types couverts par Docling : `.pdf`, `.docx`, `.md`, `.pptx`, `.xlsx`
  (`fichier_couvert_par_docling`, ingestion_docling.py).
- Pour un type couvert, `_importer_fichier_document` (front/views.py)
  lance `ingerer_un_fichier_avec_docling` en arrière-plan **en plus** du
  pipeline synchrone : `html_readability` continue d'être rempli,
  l'affichage reste celui de l'ancien moteur jusqu'à BR-D (double
  écriture de transition). Toast honnête : « Fichier importé —
  découpage en éléments lancé ».
- `.txt` (pas de structure) et `.json` (pipeline transcription) :
  repli intégral sur l'ancien comportement, toast inchangé.

## À tester à la main

1. **Import d'un `.md` ou `.docx`** (connecté) : la note s'affiche
   immédiatement (pipeline synchrone), le toast mentionne le découpage.
   Quelques secondes plus tard (≈45 s au premier import après un
   redémarrage : chargement de Docling dans le worker), en admin ou en
   shell : `page.moteur == "element"` et `page.elements.count() > 0`.
2. **Import d'un `.txt`** : toast simple « Fichier importé », la page
   reste `moteur=ancien`, zéro élément.
3. **Vérifier l'affichage** : la note importée se lit normalement —
   rien ne doit changer visuellement avant BR-D.
4. **Analyse d'une page fraîchement importée** : elle passe encore par
   l'ancien moteur (le routage de l'analyse est BR-C) — vérifier que
   les extractions fonctionnent comme avant.

## Preuves déjà faites

- 10 tests unitaires verts : `core.tests.test_moteur_flag` (5) et
  `front.tests.test_import_docling` (5), TDD RED→GREEN.
- Recette réelle sur dev : import `.md` par la vraie vue, ingestion par
  le vrai worker — **page 674**, 4 éléments (title, text, 2 list_item),
  `moteur=element`. Première page ELEMENT née du flux réel.

## Correctifs de la relecture adverse (appliqués, testés)

- **Gardes-fous de ressources** : conversion bornée
  (`max_num_pages=200`, `max_file_size=50 Mo` passés à Docling) et
  **file Celery dédiée `ingestion_docling` à concurrence 1** (nouveau
  programme `celery_worker_docling` dans supervisord.conf — nécessite
  un redémarrage du conteneur) : jamais deux conversions en même temps
  sur l'hôte 8 Go partagé avec la prod.
- **Broker en panne** : `.delay` encadré — l'import reste un succès
  (page ANCIEN lisible), toast sans promesse de découpage, erreur au
  journal.
- **Découplage stockage** : la vue ne passe que `page.pk`, la tâche
  résout le chemin depuis `source_file` (et refuse proprement une page
  sans fichier ou un stockage sans chemin local).
- **Toast FALC** : le message double « Fichier importé — découpage en
  éléments lancé » s'affiche 4,5 s (timer paramétrable dans
  `showToast`).
- Tests ajoutés : `.docx` réel (binaire), broker en panne, conversion
  synchrone en échec (verrouille que Docling n'est jamais lancé sur un
  fichier rejeté), résolution du chemin, limites, route de queue.

## Points de vigilance

- L'ingestion qui ÉCHOUE laisse la page en `ancien`, lisible (le
  pipeline synchrone a rempli le HTML) — dégradation SILENCIEUSE :
  aucun objet de suivi, le bouton « tâches » ne liste que les jobs,
  et **aucune relance manuelle n'existe encore**. Surface UI et relance
  à livrer avec BR-D/BR-E ; en attendant, le journal Celery fait foi.
- **Fenêtre BR-B→BR-D** : analyser une page fraîchement importée passe
  encore par l'ancien moteur — extractions en offsets, sans portions,
  qui ne survivront pas à la bascule d'affichage BR-D (risque consigné
  au § 5 du cahier, à trancher à BR-C).
- La reconversion des 537 pages dormantes reste une décision explicite
  du propriétaire (§ 9.5) — carnet par carnet, quasi gratuite.
- Suite : BR-C (routage de l'analyse), BR-D (affichage rendu_elements).

---

# Phases BR-C à BR-F (nuit du 9 au 10 août)

## Ce qui a été livré

- **BR-C — analyse routée** : le bouton « analyser » lance le moteur
  ELEMENT pour une page ELEMENT (même job, même toast). La tâche
  ancienne REVALIDE le moteur à l'exécution (course avec l'ingestion).
  Battement de cœur par chunk ; un job PENDING en file n'est plus tué
  à 5 min (tolérance 90 min).
- **BR-D — lecture par blocs** : une page ELEMENT s'affiche depuis ses
  éléments (h2/h3/p/listes), chaque portion marquée
  `mark.portion.hl-extraction` sur son passage exact. Repli
  readability si zéro élément. Vérifiée AU NAVIGATEUR (clair + sombre,
  contrastes ≥ 13:1 après correctif `mark`).
- **BR-E — endpoints élément** : `/elements/<pk>/corriger|scinder|
  fusionner_avec_le_suivant|masquer|demasquer`. Verrou de PAGE pour
  les opérations de structure, verrou de ligne sinon ; gardes en 409
  FALC nommant la synthèse bloquante ; journal PageEdit avec
  identifiant stable. PAS ENCORE DE BOUTONS dans l'interface (BR-G).
- **BR-F — fixtures et e2e** : conversions réelles opt-in
  (`docker exec -e TESTS_DOCLING=1 … --tag=docling`) et parcours
  navigateur complet (`front.tests.e2e.test_23_moteur_element`).

## À tester à la main

1. Importer un `.md` structuré (titres, puces) : après quelques
   secondes, la note se lit en BLOCS (inspecter :
   `data-testid="blocs-elements"`). La relire, l'analyser : les
   surlignages tombent sur les passages exacts, y compris dans les
   titres et les puces.
2. Vérifier le MODE SOMBRE d'une note ELEMENT analysée : texte des
   surlignages lisible, pas de jaune fluo.
3. Tester les endpoints élément au curl/HTMX (pas encore de boutons) :
   corriger un texte → toast + la lecture se recharge ; scinder ;
   masquer/démasquer. Vérifier le 409 FALC pendant une analyse.
4. Vérifier qu'une note ANCIENNE (tout le corpus existant) se lit et
   s'analyse exactement comme avant.

## Dettes et limites consignées (§ 5 du cahier pour le détail)

- Échec d'ingestion silencieux (pas de surface UI ni relance — BR-G).
- Cartes du panneau triées par offsets de chunk pour ELEMENT
  (entrelacement cosmétique) ; estimation du drawer à l'ancienne.
- Docling md : paragraphes à retours durs fragmentés, puce sur deux
  lignes perd son label (documenté dans les fixtures).
- Boutons d'interface des opérations d'élément : à livrer avec BR-G,
  sur le design maquette.
