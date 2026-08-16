# R4 : LE FRONT RESSEMBLE A LA MAQUETTE (gouttiere par media, audio branche, panneau integre, surlignage revele)

**Date :** 2026-08-11
**Migration :** Non

**Quoi / What :** l'ecran de lecture est mis en conformite avec l'etalon
`tmp/maquettes/maquette.html`, ecart par ecart, chacun mesure au
navigateur avant et apres. / The reading screen, brought in line with
the mock, gap by gap.

### LA GOUTTIERE, ET ELLE N'EST PAS LA MEME SELON LE MEDIA

L'etalon n'a pas UNE gouttiere mais trois (l. 73-78, 1567-1580), ce qui
avait echappe a une premiere lecture :

| Media | Largeur (lecture / structure) | Contenu |
|---|---|---|
| document ecrit | 46px / 124px | label reel, numero, empreinte |
| PDF | 46px / 124px | + numero de page, « voir la source » |
| AUDIO | **96px / 150px** | + locuteur colore, minutage, label « utterance » |

Le numero, le label et l'empreinte sont CACHES en lecture — un lecteur
n'a rien a faire de « SECTION_HEADER #6 ». Seul le COMPTEUR D'IDEES
s'adresse a lui : un clic allume toutes les ancres du passage et ouvre
le panneau sur la premiere carte.

### L'AUDIO REJOINT LE MOTEUR ELEMENT (decision D2, ordre 3)

Le dernier flux qui l'attendait. `services/ingestion_audio.py` decoupe
une transcription diarisee en tours de parole, selon la regle que la
mesure D3 avait deja tranchee : 1 element par tour, tours > 1 500 c
scindes ENTRE DEUX PHRASES, locuteur et minutage dans `provenance`.

**Sans Docling** — une transcription est deja structuree, il n'y a rien
a convertir : aucun modele charge, pas de file a concurrence 1. Verifie
de bout en bout sur un vrai appel Voxtral (14 s d'audio, 9 segments).

Pour les 34 pages audio DEJA en base, une re-ingestion aurait detruit
466 ancres et 479 extractions sur la seule page 40. `manage.py
enrichir_la_provenance_audio` les APPARIE plutot : 2 189 elements
enrichis, 0 orphelin, ancres et commentaires inchanges.

### CE QUE L'ETALON VOULAIT ET QUE L'APPLICATION NE FAISAIT PAS

- **Le surlignage se revele** (§ 9) : nu au repos, gris de revelation au
  survol du BLOC, teinte du statut au survol de l'ancre, lisere au clic.
  L'application surlignait tout, tout le temps — un texte entierement
  surligne n'est plus un texte, c'est une liste de citations.
- **Le panneau s'integre** (§ 13) : au-dela de 1400px il fait partie de
  la page, sans voile, et la zone de lecture lui cede 608px au lieu de
  le laisser recouvrir le passage dont l'idee vient. Ouvert par defaut.
  **Sous 1400px, rien ne change** : drawer glissant, feuille du bas sur
  telephone.
- **La citation se deplie au clic** (§ 14), au lieu de s'etaler sur
  toutes les cartes.
- **L'editeur en place** (§ 11) remplace le `<dialog>` pour la
  correction : on corrige DANS le document, pas dans un modal qui cache
  le contexte qui juge la correction. Le dialogue reste pour la
  SCISSION, ou l'on vise un point de coupe.
- **Typographie** : 17px / 1,7, marges portees par le BLOC selon son
  label (l'etalon met `margin: 0` sur le corps), colonne de 672px.
- Chaque puce de liste est un bloc a part entiere (`<ul>` d'un seul
  `<li>`, comme l. 1449) : elles n'avaient ni gouttiere ni compteur.

### CINQ ECARTS DELIBERES AVEC L'ETALON, ET POURQUOI

1. Compteur d'idees a **24px** (WCAG 2.5.8) ; l'etalon s'en tient a
   16,8px, trop petit pour un doigt.
2. Filet « debattu » au token `--filet-statut-commente` ; l'ambre brut
   de l'etalon fait 2,20:1 sur le papier clair.
3. Couleurs de locuteur en palette **WONG** (celle des categories) ;
   celle de l'etalon met un rouge et un vert cote a cote.
4. `:focus-within` et `@media (hover: none)` en plus : sans souris, la
   revelation n'arriverait jamais au clavier ni au doigt.
5. Le numero de page et le minutage sans `opacity` : a .75 ils tombent
   a 3,4:1, et ce sont des textes, pas un decor.

### DEFAUTS TROUVES PAR LA RELECTURE ADVERSE, CORRIGES

- `charger_fixtures_llm_reel` etait **morte a l'import** (elle lisait le
  flag supprime) : la commande plantait avant `--help`.
- La tache d'ingestion audio pouvait **figer l'etat sur EN_COURS pour
  toujours** — deux workers sur la meme page, exception non rattrapee.
  Ses trois soeurs avaient ce filet, pas elle.
- Le panneau **se rouvrait apres chaque correction** : `lectureReload`
  rappelait l'ouverture par defaut. Une fermeture explicite se retient.
- L'appariement audio pouvait **caler sur un segment** et orpheliner
  tout le reste en silence : il le dit maintenant.
- Deux contrastes sous les seuils et une bande de viewport (769-945px)
  ou la compensation de gouttiere rognait le texte hors ecran.

**Verifications** : 1 619 tests (seul un e2e d'authentification reste
instable SOUS CHARGE — vert en isole). Contrastes CALCULES au
navigateur dans les deux themes ; largeurs mesurees a 390, 800, 900,
1000, 1200, 1400 et 1600px ; piege a focus verifie (le panneau integre
n'enferme pas le clavier).

### Migration
- **Migration necessaire / Migration required :** Non.

