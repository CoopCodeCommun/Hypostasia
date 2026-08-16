# Ingestion Docling, simplifications, bascule des pages existantes

**Date :** 2026-08-05
**Migration :** Oui

**Quoi / What :** Docling installe et branche, deux simplifications du modele, et
une commande de bascule des pages du moteur ANCIEN vers le moteur ELEMENT.

### Ingestion Docling / Docling ingestion
`services/ingestion_docling.py` convertit un fichier en ElementDocument. Verifie
sur un markdown avec titres, liste et tableau : 9 elements, labels corrects
(`title`, `section_header`, `text`, `list_item`, `table`), chemins de section
hierarchiques.

Deux points traites que Docling ne fait pas seul :
- **Les tableaux sont serialises en markdown.** Un tableau Docling n'a pas
  d'attribut texte : son contenu est dans sa structure. Sans serialisation, il
  arriverait vide et tout son contenu serait perdu pour l'analyse.
- **Chaque boite PDF garde SON numero de page.** `page_no` est unique au niveau
  de la provenance, alors que les boites sont une liste : un paragraphe a cheval
  sur deux pages aurait vu ses boites de la page 2 dessinees sur la page 1.

Chaine complete verifiee avec un appel LLM reel : Docling -> 9 elements ->
1 chunk -> 4 extractions -> 14 portions, dont 2 couvrant plusieurs elements.

### Deux simplifications / Two simplifications
| Quoi / What | Pourquoi / Why |
|---|---|
| `ElementDocument.element_parent` supprime | Scission et fusion suppriment toujours leurs sources, et le `SET_NULL` vidait donc la reference a chaque fois. Un champ qui ne peut jamais rien indiquer invite a s'y fier a tort. La filiation vit dans `ElementOperation.donnees` |
| `EtatAncrage` passe de trois etats a deux | `EXACTE` et `RETROUVEE` se comportaient exactement pareil : ni le regime d'edition, ni l'affichage, ni le calcul d'etat ne les distinguaient. Fusionnes en `ANCREE` |

### Bascule des pages existantes / Migrating existing pages
`manage.py basculer_vers_le_moteur_element` decoupe `text_readability` en
elements et tente de re-ancrer les extractions en cherchant leur texte, avec la
regle habituelle : plusieurs occurrences, on ne devine pas.

Resultat sur le dev (538 pages, 29 921 extractions) : **13 174 elements crees,
8 585 ancres recuperees (28,7 %)**. Aucune extraction ni commentaire supprime :
celles qu'on ne retrouve pas restent en base, detachees.

### On traduit les anciens offsets, on ne cherche pas le texte
Les anciennes extractions portent `start_char` et `end_char` : des positions
dans `text_readability`, ecrites par l'alignement de LangExtract au moment de
l'analyse. **Ces positions sont fiables** — verifie sur echantillon : aucune
hors bornes, 5 % seulement a 0-0 (jamais alignees).

Comme les elements sont decoupes dans CE MEME texte, il suffit de noter ou
commence chaque paragraphe pour traduire un ancien offset en portions. C'est un
calcul d'intersection, exactement celui que `services/ancrage.py` fait deja pour
le nouveau moteur.

Trois versions successives de la commande, et ce que chacune a appris :

| Methode | Re-ancrage | Extractions commentees |
|---|---|---|
| Chercher `extraction_text`, element par element | 39,7 % | 51/115 |
| + insensible a la casse et a la typographie, sur le texte colle | 48,6 % | 66/115 |
| **Traduire `start_char`/`end_char`** | **99,7 %** | **113/115** |

Chercher le texte etait a la fois inutile et moins bon :
- ca rejetait des ancres correctes au motif que le texte apparaissait ailleurs
  dans la page (« ambigu »), alors que l'offset, lui, savait laquelle etait la
  bonne ;
- ca echouait sur les alignements partiels de LangExtract, ou `extraction_text`
  est plus long que ce qui a reellement ete trouve dans le document ;
- ca echouait sur les differences d'ecriture entre le texte rendu et le
  document (un `\n` devenu espace, une apostrophe courbe).

**Note** : une analyse intermediaire avait conclu que 73 % des extractions
etaient des reformulations et non des citations. C'etait faux, et c'etait un
artefact de la methode de mesure — une recherche de texte trop litterale, pas
un fait sur les donnees. `extraction_text` porte bien la citation.

### Migration
- **Migration necessaire / Migration required :** Oui — `core.0039` et
  `hypostasis_extractor.0033` (suppression du champ, fusion des etats, avec
  conversion des donnees existantes).
- La commande de bascule, elle, se lance a la demande, et accepte `--a-blanc`
  pour voir ce qui se passerait sans rien ecrire.

