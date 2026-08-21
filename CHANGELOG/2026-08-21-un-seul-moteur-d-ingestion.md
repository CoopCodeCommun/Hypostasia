# Un seul moteur d'ingestion / One ingestion engine

**Date :** 2026-08-21
**Migration :** Non

## Resume / Summary

**Quoi / What :** la vue d'import ne convertit plus rien. `MarkItDown`,
`mammoth` et `mistune` sont retires, `front/services/conversion_fichiers.py`
(158 lignes) est supprime, et le `.txt` rejoint le moteur ELEMENT. Tout fichier
importe suit desormais un seul chemin : le fichier est enregistre, la note est
creee, le decoupage part sur la file `ingestion_docling`.
/ *The import view converts nothing any more. MarkItDown, mammoth and mistune
are gone, conversion_fichiers.py is deleted, and .txt joins the ELEMENT engine.*

**Pourquoi / Why :** l'import faisait DEUX rendus du meme fichier. Un synchrone,
dans la requete HTTP, pour remplir l'ecran tout de suite ; un asynchrone, par
Docling, qui le remplacait quelques secondes plus tard. Le lecteur ouvrait la
note, lisait une version, et la page changeait sous ses yeux pour une autre.
/ *Two renderings of the same file, one replaced by the other under the reader.*

### Ce qui a ete mesure / What was measured

Meme fichier, les deux moteurs, 21 aout 2026 :

| Fichier | MarkItDown | Docling |
|---|---|---|
| `Etude_Epistemologique_IA.pdf` | 6 426 car, 1,5 s | **8 770 car**, 11 elements |
| `présentation des open badges.pdf` | 6 896 car, 0,8 s | 6 941 car, **61 elements** |

Les deux rendus ne disaient pas la meme chose : **+36 % de texte** cote Docling
sur le premier (les tableaux, que MarkItDown aplatit). Et sur le second,
MarkItDown ouvrait par `1 A LA DECOUVERTE…` — ce `1` est le **numero de page**,
que Docling ecarte par son filtre `page_header`.

**Le rendu synchrone etait de la lecture morte.** Il ne produisait aucun
`ElementDocument` : rien d'ancrable, rien d'analysable — `analyse_par_element`
sort aussitot sur « aucun element a analyser » — rien de citable. Dans un outil
dont la these est « l'ancre fait la preuve », une note qu'on peut lire mais pas
travailler est un piege, pas un filet.

### Le `.txt` avait ZERO element, pour une raison fausse

`EXTENSIONS_COUVERTES_PAR_DOCLING` excluait `.txt`, avec ce motif en
commentaire : « il n'a pas de structure a decouper, il reste sur l'ancien
pipeline ». **C'est faux.** Mesure : Docling avale un `.txt` et rend exactement
les memes elements que le `.md` equivalent — les lignes vides separent les
paragraphes, les tirets font des puces. Une note `.txt` etait donc lisible et
morte. L'unification ferme ce trou au lieu d'en ouvrir un.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/services/conversion_fichiers.py` | **SUPPRIME** — 158 lignes, cinq fonctions de conversion |
| `pyproject.toml` | `-markitdown[all]`, `-mammoth`, `-mistune` |
| `front/views.py` | `_importer_fichier_document` ne convertit plus ; empreinte sur les OCTETS du fichier ; `html_original`/`html_readability`/`text_readability` vides |
| `hypostasis_extractor/services/ingestion_docling.py` | `.txt` couvert ; `+adopter_le_titre_du_document` |
| `hypostasis_extractor/management/commands/reingerer_les_notes.py` | **Nouveau** — remplace `reingerer_les_captures_web`, couvre captures **et** fichiers |
| `front/tests/test_import_docling.py` | trois tests inverses ou reecrits (voir ci-dessous) |

### Ce qu'on gagne en dependances, mesure

Retirer `markitdown` retire aussi ce qu'il tirait seul :

| Paquet | Taille | Tire par |
|---|---|---|
| `magika` | **32,2 Mo** | `markitdown` (detecteur de type de fichier par apprentissage) |
| `youtube-transcript-api` | 8,7 Mo | `markitdown` |
| `azure-ai-documentintelligence` | 0,8 Mo | `markitdown` |
| `markitdown` + `mammoth` + `mistune` | 0,5 Mo | nous |

**≈ 42 Mo.** `pdfminer` **reste** : `pdfplumber`, cote Docling, le tire aussi.

### Trois tests changent de sens, et il faut le dire

- `test_les_types_non_couverts_par_docling` affirmait que `.txt` n'etait pas
  couvert. Il ne l'affirme plus.
- `test_un_type_non_couvert_reste_sur_l_ancien_moteur` verrouillait le fait
  qu'un `.txt` n'ait AUCUN element. Renomme
  `test_un_texte_brut_part_aussi_au_decoupage`, il verrouille l'inverse.
- `test_une_conversion_en_echec_ne_lance_pas_docling` mockait
  `convertir_fichier_en_html`, qui n'existe plus. L'intention — un fichier
  rejete n'atteint jamais Docling — est conservee sous
  `test_un_fichier_refuse_ne_lance_pas_docling`, avec le mecanisme qui la porte
  desormais : le serializer d'import.

### Ce qu'on perd, assume

**Si Docling echoue, la note est vide** au lieu d'etre lisible en version
degradee. C'etait une resilience en trompe-l'oeil : la note de secours ne
pouvait ni etre analysee, ni ancree, ni citee. L'etat `echouee` et le bouton de
relance disent la verite ; le repli la maquillait.

**L'attente devient visible.** Elle ne change pas de duree — 11 s a chaud sur un
PDF, davantage a froid le temps que les modeles se chargent — mais elle n'est
plus masquee par un rendu provisoire.
`front/templates/front/includes/_etat_ingestion.html` affiche « en attente / en
cours / echouee ».

### Une precision, parce que la question s'est posee

**Docling etait deja sur Celery**, et pas seulement : il a sa **file dediee**
`ingestion_docling`, servie par un worker a **concurrence 1**, pour que deux
conversions ne chargent jamais leurs modeles en meme temps sur l'hote partage
(`hypostasia/celery.py`). Les deux taches — fichier et capture web — y sont
routees. Ce qui etait synchrone, c'etait MarkItDown/mammoth, dans la requete
HTTP. Ce chantier ne « deplace » donc pas Docling vers la file : il fait de la
file le **seul** chemin.

---

## Comment tester (a la main) / Manual test

### Test 1 — un import de fichier

1. Importer un PDF.
2. Attendu : la reponse est **immediate** (plus de conversion dans la requete),
   et l'ecran de lecture affiche « decoupage en cours ».
3. Attendre la fin (le bouton des taches notifie).
4. Attendu : la note affiche ses elements, et son **titre vient du document**,
   pas du nom du fichier.

### Test 2 — un `.txt`

1. Importer un `.txt` de deux ou trois paragraphes.
2. Attendu : le toast dit « decoupage en elements lance » — avant ce chantier il
   ne le disait pas, et la note n'avait aucun element.

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import Page
p = Page.objects.filter(original_filename__endswith='.txt').latest('created_at')
print(p.title, '|', p.elements.count(), 'element(s)')
"
```

Attendu : au moins un element. Une note `.txt` peut desormais etre analysee,
ancree et citee.

### Test 3 — redecouper l'existant

```bash
docker exec -w /app hypostasia_web python manage.py reingerer_les_notes --a-blanc
docker exec -w /app hypostasia_web python manage.py reingerer_les_notes
docker exec -w /app hypostasia_web python manage.py reingerer_les_notes --page 14
```

Attendu : les notes portant des **ancres d'extraction** sont SAUTEES avec leur
compte d'ancres. Les `.txt` deja importes passent de 0 element a plusieurs.

### Test 4 — les dependances ont bien disparu

```bash
docker exec -w /app hypostasia_web python -c "import markitdown"   # doit echouer
docker exec -w /app hypostasia_web python -c "import mammoth"      # doit echouer
```

> **`uv sync` est necessaire** pour que la desinstallation prenne effet dans
> l'image : tant qu'il n'a pas tourne, les paquets restent presents et les
> imports reussissent. C'est `bin/install.sh` qui le lance au demarrage du
> conteneur.

### Verifs automatiques

```bash
make test-suite S=front.tests.test_import_docling
make test-suite S=hypostasis_extractor.tests.test_recette_de_capture_web
make test-suite S=hypostasis_extractor.tests.test_ingestion_docling
make test-suite S=hypostasis_extractor.tests.test_texte_plat_derive_des_elements
make test-e2e S=test_03_import
```

**Ces suites n'ont PAS ete lancees** : le mainteneur a demande de ne pas lancer
de tests pendant ce chantier. Les fichiers compilent et `manage.py check` passe,
c'est tout ce qui est verifie. Le point a regarder en premier est
`test_03_import` : ses deux tests d'import verifiaient que le contenu est
visible immediatement apres l'import. En e2e, `CELERY_TASK_ALWAYS_EAGER=True`
(`front/tests/e2e/base.py`) fait tourner la tache EN LIGNE — les elements
devraient donc exister avant le rendu de la reponse, et ces tests devraient
passer sur du vrai contenu Docling. **Raisonne, pas mesure.**
