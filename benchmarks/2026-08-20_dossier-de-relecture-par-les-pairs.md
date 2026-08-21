# Dossier de relecture — deux sessions de mesure, 19-20 août 2026

> **À qui ce document s'adresse.** À un relecteur qui n'a assisté à aucune des
> deux sessions et doit pouvoir **rejouer** ce qui est affirmé ici, ou le
> réfuter. Chaque résultat porte la commande qui le produit et les réserves qui
> le bornent.
>
> Lisible en HTML à **`/benchmarks/`** (la route rend tout `.md` du dossier).
>
> **Ce document ne tient AUCUN état d'avancement** — c'est le rôle de
> `CHANGELOG/`, de `PLAN/PASSATION.md` et de la mémoire. Il consigne des
> **mesures** et la façon de les refaire.

---

## 0. Les cinq résultats, et ce qu'ils coûtent à croire

| # | résultat | établi par | solidité |
|---|---|---|---|
| 1 | Le mode d'échec du verbatim est **typographique**, pas sémantique — et sa cause dominante est **notre ingestion** | 400 extractions typées, lecture seule | **forte** — déterministe, rejouable |
| 2 | La consigne de sourçage laissait une **porte ouverte** : Large passe de 50 % à 19 % de prose non sourcée sans changer de modèle | 2 campagnes, même périmètre | **forte** — 30 points, un seul paramètre changé |
| 3 | Le **« % de citations vérifiées » ne discrimine pas** les rédacteurs | 9 passes répétées | **forte** — 11 points d'amplitude intra-modèle |
| 4 | Le **jeu adverse des juges fuit par la négation** | rejeu du jeu, sans modèle | **forte** — un compteur de « pas » bat tous les juges |
| 5 | **Deux des quatre juges locaux sont muets 85 % du temps** | 836 avis réels | **forte** — mesuré en production |

---

## 1. LE VERBATIM — pourquoi les citations étaient « introuvables »

### Ce qui était supposé

« Sur pièces, Mistral concatène : il colle une phrase d'amorce à la liste qui
suit. » Le correctif attendu était donc dans le **prompt d'extraction**.

### Ce que la mesure dit

```bash
docker compose exec -T web python \
    benchmarks/extraction_format/typer_les_non_verbatim.py
```

| modèle | verbatim | ponctuation | ellipse | **saut** | reformulation |
|---|---|---|---|---|---|
| `mistral-large` | 116 | 11 | 0 | **5** | 2 |
| `mistral-medium` | 107 | 17 | 0 | **4** | 1 |
| `mistral-small` | 116 | 16 | 0 | **3** | 2 |

**La concaténation fait 3 cas sur 21 chez Small.** Zéro ellipse : aucun modèle
n'annonce son élision.

### L'exemple qui a tout retourné

La page 1 du corpus porte **littéralement** :

```
source  : « … d'un territoire . Soutenu depuis 2011 … »
extrait : « … d'un territoire. »
```

Le point est **détaché de son mot par notre ingestion**. Le modèle le recolle,
comme le ferait un humain — et notre comparaison lui refusait sa citation.
**Les trois modèles font la même correction au même endroit** : les extractions
34, 167 et 301 sont un seul passage vu par trois modèles.

Même famille : `« par IMS Global , un consortium »`, `« des 1/3 Lieux(La
Bobine »`, `« Le créateur/ la créatrice »`.

### La répartition des 60 citations `INTROUVABLE`

| cause | liens | part |
|---|---|---|
| espace de ponctuation **de la source** | 20 | 33 % |
| point réellement ajouté par le modèle | 8 | 13 % |
| majuscule d'amorce | 6 | 10 % |
| autre retouche de forme | 13 | 22 % |
| **vrai saut de passage** | **11** | **18 %** |
| variante orthographique | 2 | 3 % |

> ⚠️ **Cette répartition a d'abord été publiée à l'envers** (21 points ajoutés,
> 7 espaces). L'outil ne refusait que les ponctuations *fortes* (`?`, `!`) après
> le passage, jamais un `.` que la source portait déjà : **13 cas changeaient de
> colonne**, et avec eux la conclusion — ce n'était pas le modèle qui met en
> phrase, c'était nous qui détachons les points. Verrouillé par
> `test_un_point_deja_dans_la_source_n_est_pas_un_point_AJOUTE`.

### Les deux correctifs, et leur garde-fou

1. **`core/services/verification.py`** tolère trois retouches de forme (point
   final, casse d'amorce, espace de ponctuation) — jamais un changement de fond.
2. **`hypostasis_extractor/services/ingestion_docling.py`** recolle la
   ponctuation détachée, à l'ingestion.

**Ce que la tolérance doit refuser, et qui est testé :**

| cas | pourquoi il doit échouer |
|---|---|
| `« Le vaccin est sûr. »` dans `« le vaccin est sûrement inefficace »` | **inverse le sens** — retirer le point laisse la recherche tomber au milieu d'un mot |
| `« La note 7. »` dans `« la note 7.5 »` | un point devant un chiffre est une **décimale**, pas une fin de phrase |
| `« les niveaux 3,5 »` dans `« les niveaux 3, 5 et 8 »` | une énumération ne doit pas **forger un décimal** |
| `« il viendra. »` dans `« il viendra … mais »` | **ferme** un propos que la source suspend |
| `« … l'auteur. »` dans `« … l'auteur ? »` | une question devenue affirmation |

Trois de ces cinq ont été trouvés par relecture adverse **après** une première
version que je croyais sûre.

---

## 2. LES RÉDACTEURS — ce que neuf passes autorisent à dire

### Le protocole, et les trois défauts qu'il ferme

```bash
docker compose exec -T -e NOMBRE_DE_PASSES=3 \
    -e MODELES_DU_BANC='{"small": 1, "medium": 5, "large": 4}' \
    web python benchmarks/redaction/lancer_les_passes.py
docker compose exec -T web python benchmarks/redaction/analyser_les_passes.py
```

| défaut d'une campagne antérieure | ce qui le ferme |
|---|---|
| un job échoué sur un 503, **invisible** — un job en `error` satisfait « plus rien en attente » | une garde exige que le dernier job de production de **chaque** article soit `completed` **et du modèle attendu** |
| trois extracteurs sur les mêmes notes ⇒ chaque fait en ~3 exemplaires | **un seul extracteur** : 275 extractions masquées, périmètre de 137 |
| `--forcer` re-fige un périmètre neuf | **aucune extraction entre les passes** — vérifié : 0 citation hors périmètre |
| envois parallèles ⇒ `429 Rate limit` ⇒ passe perdue | **envois sérialisés**, et une passe écartée est **réessayée une fois** |

### Le bruit, mesuré au lieu d'être supposé

| | passe 1 | passe 2 | passe 3 | **étendue** |
|---|---|---|---|---|
| **% vérifiées** — Small | 36,0 | 33,9 | 34,8 | 2,1 |
| **% vérifiées** — Medium | 37,4 | 41,4 | 38,9 | 4,1 |
| **% vérifiées** — Large | 29,4 | 40,6 | 31,1 | **11,2** |

**`mistral-large` rend 29,4 % puis 40,6 % sur deux passes identiques, à
température 0.** Onze points d'amplitude avec lui-même.

### Ce qui tranche, et ce qui ne tranche pas

| mesure | écart entre modèles | bruit | verdict |
|---|---|---|---|
| % vérifiées | 7,8 | **11,2** | **DANS LE BRUIT** |
| vérifiées (absolu) | 22 | **38** | **DANS LE BRUIT** |
| introuvables | 7 | **10** | **DANS LE BRUIT** |
| citations | 106 | 54 | tranche |
| caractères | 13 473 | 7 109 | tranche |
| % prose sans marqueur | 16,2 | 14,8 | tranche, **de justesse** |

**Tout classement fondé sur le « % vérifiées » — y compris ceux publiés le
18 et le 19 août — est du bruit.**

### L'effet du SUJET égale celui du modèle

% de prose sans marqueur, par article, médiane sur trois passes :

| article | Small | Medium | Large |
|---|---|---|---|
| Wiki — open badges | **4,5** | **0,0** | 20,9 |
| Wiki — explicabilité de l'IA | 13,3 | 10,0 | **39,2** |
| Wiki — gouvernance collective | **35,2** | 13,8 | 20,4 |
| Synthèse — état des lieux | 11,5 | 14,7 | 21,1 |

**Small passe de 4,5 % à 35,2 % selon le sujet.** « Gouvernance collective » est
celui que le corpus couvre le moins : le modèle comble le vide avec de la prose
non sourcée, précisément là où il devrait se taire. **Aucun choix de modèle ne
corrige cela.**

### La porte du prompt, ouverte puis fermée

La consigne disait :

> « Chaque affirmation **tirée d'une hypostase** se termine par le marqueur de
> sa source »

Elle conditionnait le marqueur à l'origine de la phrase. Une phrase de synthèse
générale n'est, du point de vue du modèle, tirée d'aucune extraction *en
particulier* : **elle échappait à la règle sans la violer.**

Réécrite en « TOUTE AFFIRMATION … si une phrase ne peut porter aucun marqueur,
supprime-la », avec deux exceptions nécessaires (titres, liaisons
structurelles) :

| | prose nue avant → après | % vérifiées avant → après |
|---|---|---|
| Small | 12 % → 9 % | 28 % → 36 % |
| Medium | 0 % → 2 % | 27 % → 41 % |
| **Large** | **50 % → 19 %** | 35 % → **30 %** |

**Large supprime les deux tiers de sa prose non sourcée sans changer de
modèle** — et son taux de vérifiées BAISSE. Ce n'est pas une régression : il
source désormais ce qu'il laissait nu, et le juge note ces sources-là faibles.
Son « 35 % » se lisait sur la moitié de son texte.

### Le tarif

Prompt d'entrée **identique** pour les trois (15 365 caractères mesurés).

| | in $/M | out $/M | caractères | coût campagne | **coût / 100 vérifiées** |
|---|---|---|---|---|---|
| Small | 0,15 | 0,60 | 15 326 | 0,0029 $ | **0,0065 $** |
| Large | 0,50 | 1,50 | **18 033** | 0,0087 $ | 0,0235 $ |
| Medium | 1,50 | 7,50 | 11 053 | 0,0265 $ | 0,0679 $ |

**Large est dominé** : Small le bat sur les deux axes, Medium sur la qualité.
C'est le milieu de gamme qui ne gagne rien, et il est le plus instable.

> Les coûts réels **ne sont pas enregistrés en base** (les trois champs prévus
> n'ont aucun écrivain). Calcul depuis les caractères mesurés, 4 caractères par
> token. **Le classement ne dépend pas de cette conversion**, les montants
> absolus si.

---

## 3. LES JUGES LOCAUX — ce que le jeu adverse ne prouve pas

### La fuite, et comment la rejouer

```bash
docker compose exec -T web python \
    benchmarks/juge_de_verification/comparer_un_encodeur.py --adverse \
    --depuis /app/benchmarks/juge_de_verification/encodeurs-adverse.json
```

Le tableau imprime désormais **deux** baselines :

| prédicteur trivial | AUC globale | AUC appariée |
|---|---|---|
| recouvrement de mots | 0,500 | 0,500 |
| **compteur de « ne / pas / aucun / jamais »** | **0,776** | **0,962** |
| *meilleur juge (`mdeberta`)* | 0,743 | 0,853 |

**97 % des affirmations fausses portent une négation, contre 42 % des vraies.**
Toutes les paires perturbées sont fausses, toutes les vraies non perturbées, et
la perturbation dominante est une négation.

**Ce qui tombe** : la preuve *positive* que ces juges vérifient. Une AUC de 0,74
est compatible avec le biais NLI « marqueur de négation ⇒ contradiction ».
**Ce qui tient** : la conclusion *négative* — écarter les deux LettuceDetect est
mieux fondé encore, ils échouent alors qu'un indice de surface était à portée.

### Le résultat neuf : deux juges sur quatre sont muets

836 avis réels, écrits sur les 209 citations jugeables du carnet :

```bash
docker compose exec -T web python manage.py noter_avec_les_juges_locaux
```

| juge | AUC appariée | **ne tranche pas** | confirme |
|---|---|---|---|
| CamemBERTa v2 | **0,853** | **85 %** | 13 % |
| mDeBERTa v3 | **0,840** | **85 %** | 12 % |
| bge-m3 | 0,801 | 4 % | 39 % |
| distilCamemBERT | 0,737 | 8 % | 29 % |

**Les deux MEILLEURS juges sont muets 85 % du temps.** Cause : la
`MARGE_DE_NEUTRALITE = 2,5` est appliquée uniformément à des échelles
différentes. Les juges à contradiction rendent `(P(ent) − P(contra) + 1)/2`,
très concentré autour de 50 — CamemBERTa v2 va de 43,1 à 78,4, médiane 50,1.
`bge-m3` rend `P(entailment)` brut, étalé de 0,3 à 99,2.

**Conséquence non dite jusqu'ici : l'accord affiché repose de fait sur
`bge-m3`** — précisément le juge **sans** classe contradiction, c'est-à-dire
sans le seul signal que le dossier défend.

**16 citations sur 225 ne sont notées par personne** : toutes `introuvable`.
C'est sain — une citation dont le passage n'existe plus n'a pas de paire.

---

## 3 bis. CE QUE LES MESURES ONT ÉCARTÉ À L'ÉCRAN

Trois designs successifs ont été proposés puis **tués par une mesure**, avant
qu'une ligne de production ne soit écrite. C'est le meilleur exemple de ce que
ce dossier sert à permettre.

| design proposé | mesure qui l'a écarté |
|---|---|
| la couleur pilotée par la **moyenne des juges locaux** | Pearson **0,187** avec le juge de production ; **53 %** des citations changeraient de camp |
| la couleur pilotée par le **seul juge de production** | il ne rend que **4 valeurs distinctes** (0, 40, 70, 100) : quatre couleurs, pas un dégradé |
| **teinte** production + **intensité** locale | une intensité n'a **pas de signe**, or **42 %** du signal qu'elle rendrait visible **contredit** la teinte qu'elle module |

**Ce qui a été retenu** : le renvoi `[N]` passe en ambre quand les locaux
démentent franchement le cran — **16 citations sur 209, soit 7,7 %**. Assez rare
pour se voir, assez fréquent pour se rencontrer.

```bash
docker compose exec -T web python manage.py shell -c "
from core.models import SourceLink
from core.services.degre_agrege import degre_agrege, tension_des_juges
from collections import Counter
c = Counter(
    tension_des_juges(list(l.avis_locaux.all()), l.score_de_verification)
    for l in SourceLink.objects.filter(avis_locaux__isnull=False).distinct()
                               .prefetch_related('avis_locaux'))
print(dict(c))"
```

**Un agrégat ne pourra piloter la couleur que le jour où il dépassera ~0,6
d'AUC** contre une référence. La moyenne des quatre fait **0,566** — et le
meilleur juge **seul** fait **0,642** : moyenner *détruit* de l'information.

## 4. LES PROCÉDURES, pour tout rejouer

| ce qu'on veut refaire | commande | coût |
|---|---|---|
| typer les non-verbatim | `benchmarks/extraction_format/typer_les_non_verbatim.py` | gratuit |
| le bruit des rédacteurs | `benchmarks/redaction/analyser_les_passes.py` | gratuit |
| relancer des passes | `benchmarks/redaction/lancer_les_passes.py` | **facturé** |
| la fuite du jeu adverse | `comparer_un_encodeur.py --adverse --depuis …` | gratuit |
| faire noter par les juges locaux | `manage.py noter_avec_les_juges_locaux` | gratuit, hors réseau |

**Trois pièges, chacun a coûté une mesure :**

1. **Une seule suite de tests à la fois.** L'échec ne ressemble pas à sa cause —
   des centaines d'erreurs en `real_ensure_connection`. Avant tout
   `make test-rapide` :
   ```bash
   docker exec hypostasia_web sh -c "ps -eo args | grep -c '[m]anage.py test'"
   ps -eo args | grep -c "[m]ake test"
   ```
   Zéro partout, ou on ne lance pas.
2. **Redémarrer les workers après toute modification de code** — sans quoi ils
   tournent avec l'ancien, et la mesure ne dit rien.
3. **Un banc qui déplace un rôle doit le reposer en partant** : un rôle posé à
   la main **survit** au redémarrage (`get_or_create`, pas `update_or_create`).

---

## 5. CE QUE CES DEUX SESSIONS NE DÉMONTRENT PAS

- **Aucun juge n'a démontré qu'il vérifie.** Le jeu adverse fuit ; l'étalon et
  les 15 paires relues sont lexicalement saturés (un recouvrement de mots y fait
  0,889 et 0,981). Il n'existe **aucune** référence propre à ce jour.
- **Trois répétitions, c'est peu.** L'étendue sur trois points sous-estime la
  dispersion : les verdicts « tranche » les plus serrés (prose nue Medium/Large,
  16,2 contre 14,8) sont des indices, pas des preuves.
- **Le juge de production a sa propre variation**, non isolée : une part du
  « bruit » attribué au rédacteur lui appartient peut-être.
- **Quatre articles, un corpus, un carnet de démonstration**, 6 notes dont 5
  analysées.
- **Le taux de verbatim de `gemini-2.5-flash` (100 %) reste invérifiable** : la
  base a été détruite, et il tournait à température 0,7.
- **Les 60 `INTROUVABLE` typés l'ont été sur les articles d'UN SEUL rédacteur**
  (`mistral-large`), et 60 liens ne sont que 43 citations distinctes.
- **La vérification au navigateur n'a pas été faite** pour le bloc de preuve
  pliable, en clair et en sombre, contrastes calculés. C'est une exigence
  d'`AGENTS.md` que rien ne remplace.
