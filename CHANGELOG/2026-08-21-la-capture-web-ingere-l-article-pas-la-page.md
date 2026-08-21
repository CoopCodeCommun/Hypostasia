# La capture web ingère l'article, plus la page / Web capture ingests the article, not the page

**Date :** 2026-08-21
**Migration :** Non

## Resume / Summary

**Quoi / What :** le moteur ELEMENT decoupe desormais l'ARTICLE rendu par
Readability, et non la page brute. L'extension y joint le titre, la signature,
le chapeau et la provenance, que Readability rend dans des champs separes et que
l'extension jetait. Les widgets d'interface (cases a cocher, formulaires) sont
ecartes. Une commande redecoupe les captures deja en base.
/ *The ELEMENT engine now cuts the Readability ARTICLE, not the raw page. The
extension adds the title, byline, standfirst and provenance that Readability
returns in separate fields and that the extension threw away.*

**Pourquoi / Why :** l'ingestion repartait de `page.html_original`, c'est-a-dire
`document.documentElement.outerHTML` — la page ENTIERE. Readability tournait,
son resultat etait stocke dans `html_readability`... et le moteur ne le lisait
jamais. Sur la page Wikipedia « Convivialite », **l'article commencait a
l'element 84 sur 245** : un tiers du document etait du sommaire et de la barre
laterale avant le premier mot du sujet.
/ *Ingestion restarted from the whole raw page; Readability's output was stored
and never read.*

### Ce qui a ete mesure / What was measured

Meme pipeline, deux entrees, 21 aout 2026 :

| Page | `html_original` | `html_readability` | elements avant | apres | conversion |
|---|---|---|---|---|---|
| Wikipedia — Convivialite | 367 161 car | 58 123 car | **245** | **111** | 6,8 s → 0,2 s |
| Monde diplomatique — Illich | 107 248 car | 19 522 car | **150** | **39** | 0,4 s → 0,1 s |

Le debut du document, avant et apres :

```
AVANT (page 14)                        APRES
  0 Traductions de cet article           0 [title] La resistance selon Ivan Illich
  1 English - The nonconformist          1 Thierry Paquot
  2 Espanol - La resistencia...          2 Celebre theoricien de « La Convivialite »...
  3 Deutsch - Vagabundierendes...        3 Le Monde diplomatique - 01/01/2003
  4 Esperanto - Rezistado...             4 Le lundi 2 decembre, Ivan Illich...
  ...                                    5 Assez grand, sec, un regard engageant...
  8 [title] La resistance selon...       6 [section_header] Cuernavaca, un detour oblige
```

### Les quatre points, et ce que chacun corrige

**A — ingerer l'article propre.** `source_html_d_une_capture()` choisit
`html_readability` quand il est credible, `html_original` sinon.

**B — recuperer ce que Readability range ailleurs.** `parse()` rend DIX champs ;
l'extension en gardait deux. Le titre, la signature (`byline`) et le chapeau
(`excerpt`) vivent dans des champs SEPARES, absents de `content` — le mode
lecture de Firefox les reaffiche, l'extension les jetait. Mesure sur l'article
du Monde diplomatique : `byline` vaut `'Thierry Paquot'`, `excerpt` vaut le
chapeau entier, et **aucun des deux n'etait dans la note**. S'y ajoutent
`siteName` et `publishedTime` : de la **provenance**, dans un outil dont c'est
le sujet.

Le chapeau n'est ajoute que s'il n'ouvre pas deja le corps : `excerpt` vaut
tantot le chapeau, tantot le premier paragraphe, et l'ajouter aveuglement le
ferait lire deux fois.

**C — ecarter le chrome d'interface.** `LABELS_SANS_CONTENU_UTILE` ne contenait
que `page_header`, `page_footer` et `footnote` : trois notions **de PDF**,
inertes sur une capture web. La page Wikipedia produisait **13
`checkbox_unselected`** — les cases de repli de son sommaire, treize elements a
commenter et a compter dans la couverture. Les labels de formulaire et de widget
les rejoignent ; les labels de CONTENU (`caption`, `reference`, `table`, `code`,
`formula`…) sont explicitement preserves, et un test le verrouille.

**D — le plancher qui evite de remplacer du bruit par du vide.** Readability est
fait pour les ARTICLES : sur une page d'accueil ou un forum, il rend trois
lignes de menu. En dessous de `MINIMUM_DE_TEXTE_LISIBLE` (200 caracteres de
texte), on repart de la page brute.

**E — `html_original` n'est pas touche.** C'est l'archive immuable de ce qui a
ete capture, et c'est elle qui a rendu possible la re-ingestion ci-dessous.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasis_extractor/services/ingestion_docling.py` | `+source_html_d_une_capture`, `+MINIMUM_DE_TEXTE_LISIBLE`, `LABELS_SANS_CONTENU_UTILE` etendu au chrome web, `ingerer_une_capture_web` choisit sa source et la journalise |
| `extension/popup.js` | la fonction injectee assemble titre + signature + chapeau + provenance devant `article.content` |
| `hypostasis_extractor/management/commands/reingerer_les_captures_web.py` | **Nouveau** — redecoupe les captures deja en base, saute celles qui portent des ancres |
| `hypostasis_extractor/tests/test_recette_de_capture_web.py` | **Nouveau** — 7 tests |

### Ce qui reste, et qui est connu

**Les bandeaux de maintenance de Wikipedia survivent** a Readability : deux
elements « Si ce bandeau n'est plus pertinent, retirez-le » ouvrent encore la
note. Ils arrivent en label `picture` avec leur legende ; filtrer `picture`
ferait perdre les legendes d'images, qui sont du texte d'auteur. Deux elements
de bruit au lieu de 84 : on s'arrete la.

**La capture herite de ce que les AUTRES extensions ont fait a la page.**
Constate sur l'article du Monde diplomatique : le premier mot arrive coupe,
« L e lundi ». Le HTML capture porte
`<span><span data-darkreader-inline-color="">L</span>e</span> lundi` — **Dark
Reader** avait enveloppe la lettrine pour la recolorer, avant la capture.
Readability conserve ce balisage, Docling le lit comme deux fragments. Nettoyer
les attributs injectes par les extensions tierces, avant de passer a
Readability, est un chantier a part.

---

## Comment tester (a la main) / Manual test

### Test 1 — une capture neuve

1. Capturer un article de presse avec l'extension.
2. L'ouvrir dans Hypostasia.
   - Attendu : le document **commence par le titre**, puis l'auteur, puis le
     chapeau s'il y en a un, puis la source et la date. Aucun menu, aucun
     sommaire, aucun pied de page.

### Test 2 — les captures deja en base

```bash
# Voir ce qui serait fait, sans rien ecrire
docker exec -w /app hypostasia_web python manage.py reingerer_les_captures_web --a-blanc

# Redecouper
docker exec -w /app hypostasia_web python manage.py reingerer_les_captures_web

# Une seule note
docker exec -w /app hypostasia_web python manage.py reingerer_les_captures_web --page 14
```

Attendu : les notes portant des **ancres d'extraction** sont SAUTEES avec leur
compte d'ancres — redecouper effacerait des preuves. Les autres affichent
`245 -> 111 element(s), depuis html_readability`.

### Test 3 — une page qui n'est pas un article

Capturer une page d'accueil ou une page de resultats de recherche.

- Attendu : la note n'est pas vide. Le journal du worker porte
  `article propre trop court (N caracteres de texte, minimum 200) — on repart
  de la page brute`.

### Verifs DB

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import Page
p = Page.objects.get(pk=14)
for e in p.elements.order_by('ordre')[:6]:
    print(e.ordre, '|', e.label, '|', ' '.join((e.texte or '').split())[:60])
print('projection :', len(p.text_readability or ''), 'car pour',
      sum(len(t or '') for t in p.elements.values_list('texte', flat=True)), 'car d elements')
"
```

Attendu : le titre en premier, et une projection coherente avec la somme des
elements — la commande passe par `_noter_l_etat_d_ingestion`, qui reecrit
`text_readability` comme le fait la tache Celery.

### Verifs automatiques

```bash
make test-suite S=hypostasis_extractor.tests.test_recette_de_capture_web   # 7 tests
make test-suite S=front.tests.test_capture_web_docling
make test-suite S=hypostasis_extractor.tests.test_ingestion_docling
make test-suite S=hypostasis_extractor.tests.test_tasks_element
```
