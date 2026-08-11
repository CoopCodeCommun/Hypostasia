# L'usage du moteur ELEMENT — U1 (boutons), U2 (ingestion), U4 (capture web), sécurité, U3 (panneau), D3 (audio)

> Écrit le 10 août 2026. Réfère : SPEC-ancrage-par-element-v2.md (addendums
> du 10 août), PLAN/branchement-moteur-ancrage-cahier-des-charges.md § 5,
> PLAN/mesure-D3-frontiere-audio-2026-08-10.md, CHANGELOG du 10 août.

## Ce qui a été livré

### U1 — le mode structure de la lecture
- Bouton à bascule « Modifier la structure » sur toute page ELEMENT dont
  on peut écrire (même règle que les endpoints : `est_modifiable_par` →
  `_utilisateur_peut_ecrire_page`). La classe `mode-structure` vit sur
  `#zone-lecture` et survit aux rechargements.
- En mode structure, chaque bloc porte : **corriger** (dialogue avec
  textarea), **couper en deux** (dialogue : placer le curseur puis
  « Couper ici »), **recoller avec le suivant** (confirmation ; absent sur
  le dernier bloc et quand le suivant est masqué), **masquer**
  (confirmation).
- Les éléments masqués deviennent des placeholders « Passage masqué »
  (extrait + bouton **démasquer**), visibles en mode structure seulement,
  absents du DOM des simples lecteurs.
- Sécurité d'offsets de la scission : conversion UTF-16 → points de code,
  retour à la ligne volontaire après `<textarea>`, empreinte du texte
  affiché vérifiée sous le verrou (409 « modifié entre-temps »).

### U2 — l'ingestion ne se tait plus
- État du découpage sur la Page (`ingestion_etat` + `ingestion_detail`),
  migration core.0054 appliquée sur dev (4 pages ELEMENT estampillées).
- Puce d'état dans la lecture (écrivains seulement) : attente/cours
  auto-rafraîchie (plafond ~5 min puis « Vérifier à nouveau »), échec
  avec détail FALC + « Relancer le découpage ». Réussite silencieuse :
  la lecture se recharge en blocs.
- Relance gardée : écriture requise, refus 409 si ingestion active ou
  éléments déjà présents, type couvert seulement, broker mort = 503.

### U4 — la capture web nourrit le moteur ELEMENT
- `POST /api/pages/` (extension) lance
  `ingerer_une_capture_web_avec_docling` en plus de la création
  synchrone. Source = `html_original`. Même file dédiée, double
  écriture, repli honnête, état U2.
- Une capture aboutie devient `moteur=element` et se lit en blocs ; un
  échec reste ANCIEN lisible avec la puce d'échec + relance.

### Sécurité — extractions ET la famille entière des endpoints
`drawer_contenu`, `carte_mobile`, `dashboard`, `formulaire_promouvoir`
ne vérifiaient aucune permission (fuite anonyme du texte des
extractions). Garde `_utilisateur_a_acces_page` + 404 au même octet que
l'absent. Preuve de morsure faite (garde neutralisée → 3 tests tombent).

La relecture adverse a montré que la famille N'ÉTAIT PAS éteinte : le
projet n'a **aucun `DEFAULT_PERMISSION_CLASSES`** (tout est `AllowAny`
par défaut). Bouché à son tour :
- **lecteurs anonymes** rendant le texte intégral d'une note privée :
  `/lire/<pk>/exporter/`, `previsualiser_analyse` (le prompt complet
  contient tout le texte), `previsualiser_synthese`,
  `telecharger_source`, les deux formulaires audio, `panneau`,
  `manuelle` → garde de lecture ; `/questionnaire/?page_id=` → 404 ;
- **IDOR authentifiés** : `modifier_titre`, `renommer_locuteur`,
  `editer_bloc`, `supprimer_bloc`, `creer_manuelle`, `ia` (analyse
  payante) → droit d'écriture ; `supprimer_ia`,
  `promouvoir_entrainement` (copie le texte dans un exemple global) →
  propriétaire ; `ajouter_commentaire`, `poser_question`, `repondre`
  → accès en lecture (le débat est ouvert à qui peut lire) ;
  `DossierViewSet.partager` (fuyait les emails d'invitation, POST
  modifiait les partages d'autrui) → owner du dossier.
28 tests dédiés (`test_extractions_permissions` 9 +
`test_permissions_famille` 19).

### U3 — les restes § 5
- Drawer d'une page ELEMENT trié par ancre (ordre d'élément, début dans
  l'élément) ; sans portion → en queue. ANCIEN inchangé.
- Estimation d'analyse d'une page ELEMENT : `construire_les_chunks`
  réel sur les éléments visibles (nombre de chunks exact).

### D3 — mesure audio (aucun code de production)
Voir PLAN/mesure-D3-frontiere-audio-2026-08-10.md : pas de frontière
préférentielle au changement de locuteur ; élément audio = tour de
parole ; tours > 1 500 c scindés à l'ingestion. Addendum daté posé dans
la spec.

## Tests à réaliser à la main

1. **Mode structure** (connecté, propriétaire d'une note ELEMENT — ex.
   page 674) : le bouton « Modifier la structure » apparaît sous la
   ligne Historique. Cliquer : les boutons apparaissent sur chaque bloc,
   `aria-pressed` passe à true. Recliquer : tout disparaît.
2. **Corriger** : ouvrir, modifier un mot, enregistrer → toast, la
   lecture se recharge, le mode structure est TOUJOURS actif et le
   bouton bascule annonce toujours « enfoncé ».
3. **Couper en deux** : placer le curseur au milieu d'une phrase,
   « Couper ici » → deux blocs. « Recoller avec le suivant » sur le
   premier → un seul bloc, texte intact.
4. **Couper sans placer le curseur** : le message d'erreur apparaît DANS
   le dialogue (« Placez d'abord le curseur… »), le dialogue reste
   ouvert.
5. **Masquer/démasquer** : masquer un bloc → il devient « Passage
   masqué » (extrait + démasquer). Quitter le mode structure : le
   placeholder disparaît de la lecture. Démasquer → le bloc revient.
6. **Simple lecteur** : ouvrir la même note avec un compte qui peut la
   lire sans pouvoir l'écrire (ou en navigation privée si publique) :
   AUCUN bouton, AUCUN placeholder dans le DOM (inspecter).
7. **Sécurité** : déconnecté,
   `curl -s https://hyp.nasjo.fr/extractions/drawer_contenu/?page_id=1`
   → 404, aucun texte d'extraction.
8. **Panneau (U3)** : sur une note ELEMENT analysée (page 676), ouvrir
   le drawer des extractions : les cartes suivent l'ordre du texte, pas
   d'entrelacement.
9. **Estimation (U3)** : bouton analyser sur une note ELEMENT → le
   nombre de chunks affiché correspond aux éléments réels.
10. **Deux onglets** (concurrence) : ouvrir « couper en deux » dans
    l'onglet A, corriger le même passage dans l'onglet B, envoyer la
    coupe dans A → 409 « modifié entre-temps », rien n'est coupé.
11. **Ingestion (U2), chemin nominal** : importer un `.md` → la note
    s'ouvre avec la puce « Découpage en éléments en attente… » qui
    passe à « en cours », puis disparaît quand la lecture se recharge
    en blocs (toast « Découpage en éléments terminé »).
12. **Ingestion (U2), échec + relance** : simuler un échec
    (`docker exec hypostasia_dev_web python manage.py shell -c
    "from core.models import Page, EtatIngestion;
    Page.objects.filter(pk=<pk>).update(ingestion_etat='echouee',
    ingestion_detail='La conversion du fichier a échoué.')"`) →
    recharger la note : puce d'échec avec le détail et « Relancer le
    découpage ». Cliquer : la puce repasse en attente, la vraie tâche
    tourne, la note finit en blocs. Un lecteur sans droit d'écriture ne
    voit jamais la puce.

## Vérifications en base utiles

```bash
docker exec hypostasia_dev_web python manage.py shell -c "
from core.models import ElementDocument
e = ElementDocument.objects.filter(page_id=674).order_by('ordre')
print([(x.ordre, x.masque, x.texte[:30]) for x in e])"
```

## Limites consignées (pas corrigées)
- Oracle 403/404 des endpoints élément (un tiers authentifié distingue
  « existe » de « n'existe pas ») — cohérent avec le reste du dépôt,
  consigné depuis BR-F, à trancher globalement.
- Textarea readonly : poser le curseur est peu fiable sur iOS Safari —
  le message d'erreur FALC rattrape (« Placez d'abord le curseur »).
- `aria-live` sur `#zone-lecture` (préexistant) : chaque opération
  fait relire la zone aux lecteurs d'écran.
- Éléments à `\r\n` : offsets théoriquement décalés (0 cas en base dev ;
  Docling n'en produit pas).
- Échap/Annuler jette la saisie de correction sans confirmation.
