/* =========================================================================
   HYPOSTASIA — LE CORPUS DE REFERENCE, SOURCE UNIQUE
   LOCALISATION : front/static/front/maquettes/donnees.js

   POURQUOI CE FICHIER EXISTE
   Les trois ecrans (carnet, selection des preuves, note) affichaient
   chacun leur propre copie des extractions. Trois copies, trois verites :
   des identifiants divergents, des comptes tapes a la main qui ne
   correspondaient pas aux donnees, et des offsets d'ancrage errones dans
   19 cas sur 20. Une maquette qui doit servir d'ETALON ne peut pas se
   permettre ca : on comparera ses sorties a celles du vrai moteur, et
   toute divergence interne rendrait la comparaison illisible.

   LA REGLE, SANS EXCEPTION
   On ecrit ici ce qu'un humain ou un LLM produit vraiment : un texte, une
   citation, un commentaire. Tout le reste — offsets, comptes, ecartees,
   couverture, similarites — est DERIVE par les fonctions du bas de ce
   fichier. Si un chiffre est tape quelque part, c'est un defaut.
   / Everything derivable is derived. A typed number is a bug.

   CE QUI RESTE MOCKE, ET C'EST ASSUME
   · les textes des documents et les citations : ils tiennent lieu de
     sortie de Docling et de LangExtract ;
   · les commentaires : ils tiennent lieu de deliberation humaine ;
   · les positions 2D de selection-preuves.js : elles tiennent lieu de
     projection d'un espace d'embedding ;
   · la liste des oppositions : elle tient lieu de seconde passe LLM.
   Aucune de ces quatre choses ne peut se deduire du reste ; tout le reste
   se deduit d'elles.
   ========================================================================= */

var DOCUMENTS = {

pdf: {
  titre:"Rapport annuel 2024 — Coopérative des Trois Vallées",
  dossier:"Conseil d'administration", visibilite:"👥",
  source:"rapport-annuel-2024.pdf · 18 pages · 1,4 Mo",
  meta:"PDF · 214 éléments · ingéré le 3 mars 2026",
  note:{titre:"Ce qu'un PDF apporte de plus",
    corps:"Docling rend la <strong>position physique</strong> de chaque élément : sa page et ses boîtes. " +
      "Un paragraphe à cheval sur deux pages en porte deux — d'où <code>p. 4–5</code> sur le bloc du bail, " +
      "visible en mode inspection. C'est ce qui permet le lien « voir la source ». Les <code>page_header</code>, " +
      "<code>page_footer</code> et <code>footnote</code> sont écartés à l'ingestion : 36 éléments sur 250."},
  elements:[
    {label:"title", page:1, texte:"Rapport annuel 2024"},
    {label:"section_header", page:3, section:["Rapport annuel 2024"], texte:"3. Situation financière"},
    {label:"text", page:3, section:["Rapport annuel 2024","3. Situation financière"],
     texte:"L'exercice se clôt sur un excédent de 12 400 euros, contre un déficit de 3 100 euros l'année précédente. Ce redressement tient pour l'essentiel à la renégociation du bail commercial, obtenue en avril.",
     idees:[{id:301, cite:"un excédent de 12 400 euros, contre un déficit de 3 100 euros l'année précédente",
       statut:'nouveau', tags:['phenomene'], motscles:['résultat','exercice'],
       resume:"Le résultat passe d'un déficit à un excédent d'une année sur l'autre."}]},
    {label:"table", page:4, section:["Rapport annuel 2024","3. Situation financière"],
     entetes:["Poste","2023","2024"],
     lignes:[["Cotisations","42 100 €","44 800 €"],["Subventions","18 000 €","18 000 €"],
             ["Loyer","−31 200 €","−22 400 €"],["Salaires","−29 900 €","−31 100 €"]],
     total:["Résultat","−3 100 €","12 400 €"]},
    {label:"text", page:4, section:["Rapport annuel 2024","3. Situation financière"],
     texte:"Le poste des salaires progresse de 4 %, ce qui correspond à l'embauche au secrétariat décidée en assemblée. Aucun autre poste n'a été augmenté.",
     idees:[{id:302, cite:"Le poste des salaires progresse de 4 %", statut:'commente',
       tags:['phenomene'], motscles:['salaires','masse salariale'],
       resume:"La masse salariale croît de quatre pour cent.",
       commentaires:[{qui:"Sonia", quoi:"Sur douze mois pleins, ce sera plutôt 6 %."}]}]},
    /* Deux idees qui SE CHEVAUCHENT : le service emet des marques imbriquees. */
    {label:"text", page:4, pageFin:5, etat:"debattu",
     section:["Rapport annuel 2024","3. Situation financière"],
     texte:"La renégociation du bail, si elle allège durablement les charges, repose sur un accord verbal avec le propriétaire actuel. Rien ne garantit sa reconduction en cas de vente du local, hypothèse qui n'est pas à écarter compte tenu de l'âge du bailleur.",
     idees:[{id:303, cite:"repose sur un accord verbal avec le propriétaire actuel", statut:'commente',
       tags:['probleme','conjecture'], motscles:['bail','risque'],
       resume:"L'allègement des charges n'est garanti par aucun écrit.",
       commentaires:[{qui:"Jonas", quoi:"C'est le vrai risque du budget. À mettre en tête du rapport."},
                     {qui:"Amina", quoi:"Un avenant écrit coûte 300 € de notaire. On le fait ?"}]},
      {id:304, cite:"un accord verbal avec le propriétaire actuel. Rien ne garantit sa reconduction en cas de vente du local",
       statut:'nouveau', tags:['conjecture'], motscles:['reconduction','vente'],
       resume:"La reconduction du bail dépend du maintien du propriétaire actuel."}]},
    {label:"formula", page:5, section:["Rapport annuel 2024","3. Situation financière"],
     texte:"seuil = charges_fixes / (1 − charges_variables / recettes)"},
    {label:"section_header", page:6, section:["Rapport annuel 2024"], texte:"4. Fréquentation"},
    {label:"picture", page:6, section:["Rapport annuel 2024","4. Fréquentation"], texte:"",
     legende:"Figure 2 — Fréquentation mensuelle, 2022–2024. Source : registre d'entrée."},
    {label:"text", page:6, section:["Rapport annuel 2024","4. Fréquentation"],
     texte:"La fréquentation progresse sur les trois indicateurs suivis. La hausse des passages hebdomadaires est la plus nette au dernier trimestre, après l'ouverture des créneaux du samedi matin."},
    {label:"list_item", page:6, section:["Rapport annuel 2024","4. Fréquentation"],
     texte:"Adhérents actifs : 312, en hausse de 8 %"},
    {label:"list_item", page:6, section:["Rapport annuel 2024","4. Fréquentation"],
     texte:"Passages hebdomadaires : 940 en moyenne"},
    {label:"list_item", page:6, section:["Rapport annuel 2024","4. Fréquentation"],
     texte:"Ateliers ouverts : 14, contre 11 en 2023"},
    /* Element masque : le modele le permet, aucune interface ne le fait. */
    {label:"text", page:7, masque:true, section:["Rapport annuel 2024","4. Fréquentation"],
     texte:"Ce paragraphe doublonnait la section 2 ; il a été retiré du contenu utile sans être supprimé."}
  ]},

md: {
  titre:"ADR 007 — Ancrage par élément",
  dossier:"Veille documentaire", visibilite:"🔒",
  source:"adr-007-ancrage-par-element.md · 4 200 signes",
  meta:"Markdown · 31 éléments · ingéré le 12 mars 2026",
  note:{titre:"Ce qui change avec un Markdown",
    corps:"Même moteur, même richesse de structure. Mais <code>_provenance_de_l_element()</code> rend " +
      "<code>{}</code> : un Markdown n'a pas de page physique, et il n'y a rien à pointer dans un " +
      "document d'origine. En revanche les blocs de code prennent leur forme propre."},
  elements:[
    {label:"title", texte:"ADR 007 — Ancrage par élément"},
    {label:"text", section:["ADR 007 — Ancrage par élément"],
     texte:"Statut : accepté. Date : 12 mars 2026. Remplace l'ADR 003."},
    {label:"section_header", section:["ADR 007 — Ancrage par élément"], texte:"Contexte"},
    {label:"text", section:["ADR 007 — Ancrage par élément","Contexte"],
     texte:"L'ancrage par décalage de caractères dans le texte entier casse dès qu'un paragraphe est corrigé en amont : toutes les positions suivantes glissent, et les extractions se retrouvent sur le mauvais passage.",
     idees:[{id:401, cite:"toutes les positions suivantes glissent", statut:'commente',
       tags:['probleme'], motscles:['décalage','régression'],
       resume:"Une correction en amont invalide toutes les ancres qui suivent.",
       commentaires:[{qui:"Jonas", quoi:"C'est exactement ce qu'on a constaté sur la page du 4 février."}]}]},
    {label:"blockquote", section:["ADR 007 — Ancrage par élément","Contexte"],
     texte:"Un décalage n'est pas une adresse : c'est une distance depuis un point qui bouge."},
    {label:"section_header", section:["ADR 007 — Ancrage par élément"], texte:"Décision"},
    {label:"text", etat:"debattu", section:["ADR 007 — Ancrage par élément","Décision"],
     texte:"On ancre désormais dans l'élément, pas dans la page. Une extraction porte une ou plusieurs portions, chacune bornée à l'intérieur d'un élément identifié de façon stable.",
     idees:[{id:402, cite:"On ancre désormais dans l'élément, pas dans la page", statut:'commente',
       tags:['principe','methode'], motscles:['ancrage','élément'],
       resume:"L'unité d'ancrage devient l'élément de document.",
       commentaires:[{qui:"Amina", quoi:"Et pour un passage qui traverse deux paragraphes ?"},
                     {qui:"Jonas", quoi:"Deux portions, une extraction. C'est le point suivant."}]},
      {id:403, cite:"chacune bornée à l'intérieur d'un élément identifié de façon stable",
       statut:'nouveau', tags:['methode'], motscles:['portion','identifiant'],
       resume:"Chaque portion est bornée par un identifiant qui survit aux scissions."}]},
    {label:"code", section:["ADR 007 — Ancrage par élément","Décision"],
     texte:"class AncrageExtraction(models.Model):\n    extraction = models.ForeignKey(ExtractedEntity, related_name=\"ancrages\")\n    element    = models.ForeignKey(ElementDocument, on_delete=PROTECT)\n    ordre_dans_extraction = models.PositiveSmallIntegerField()\n    debut_dans_element    = models.PositiveIntegerField()\n    fin_dans_element      = models.PositiveIntegerField()"},
    {label:"section_header", section:["ADR 007 — Ancrage par élément"], texte:"Conséquences"},
    {label:"list_item", section:["ADR 007 — Ancrage par élément","Conséquences"],
     texte:"Corriger un paragraphe ne touche plus que ses propres ancres."},
    {label:"list_item", section:["ADR 007 — Ancrage par élément","Conséquences"],
     texte:"Une extraction peut traverser plusieurs éléments — d'où la relation M2M."},
    {label:"list_item", section:["ADR 007 — Ancrage par élément","Conséquences"],
     texte:"Une portion qu'on ne retrouve plus est détachée, jamais supprimée.",
     idees:[{id:404, cite:"détachée, jamais supprimée", statut:'nouveau',
       tags:['principe'], motscles:['détachement','conservation'],
       resume:"La perte de position ne détruit pas l'extraction."}]}
  ],
  /* Portion detachee : le service ne la dessine pas dans le texte, elle
     n'apparait qu'au panneau. rendu_elements.py:306-312 */
  detachees:[{id:405, statut:'commente', tags:['probleme'],
    resume:"Le passage d'origine a été réécrit ; l'ancre ne retrouve plus son texte.",
    citation:"les positions absolues rendent la réconciliation impossible",
    motscles:['détachée'],
    commentaires:[{qui:"Sonia", quoi:"C'était le paragraphe qu'on a réécrit mardi."}]}]},

web: {
  titre:"Ce que les communs nous apprennent de la gouvernance",
  dossier:"Communs et gouvernance", visibilite:"🌐",
  source:"https://lemondeducommun.fr/communs-gouvernance-ostrom",
  meta:"Capture web · 24 éléments · capturée le 8 mars 2026",
  note:{titre:"Ce qu'une capture web apporte, et ce qui lui manque",
    corps:"L'extension envoie <code>html_readability</code>, déjà débarrassé de la navigation par " +
      "Readability.js dans le navigateur. Docling structure ce HTML nettoyé : la hiérarchie suit celle " +
      "du site, donc <strong>bonne quand le site est bien écrit, pauvre sinon</strong>. Pas de page " +
      "physique, mais une <strong>URL</strong> — chaque élément peut porter une ancre de fragment."},
  elements:[
    {label:"title", texte:"Ce que les communs nous apprennent de la gouvernance"},
    {label:"text", section:["Ce que les communs nous apprennent de la gouvernance"],
     texte:"Publié le 8 mars 2026 par Claire Vasseur · 11 min de lecture"},
    {label:"text", section:["Ce que les communs nous apprennent de la gouvernance"],
     texte:"Depuis les travaux d'Elinor Ostrom, on sait qu'une ressource partagée peut être gérée durablement sans être ni privatisée ni nationalisée. Ce que l'on sait moins, c'est à quelles conditions.",
     idees:[{id:501, cite:"une ressource partagée peut être gérée durablement sans être ni privatisée ni nationalisée",
       statut:'nouveau', tags:['axiome','principe'], motscles:['communs','gestion'],
       resume:"Une troisième voie de gestion existe entre marché et État."}]},
    {label:"section_header", section:["Ce que les communs nous apprennent de la gouvernance"],
     texte:"Les huit principes"},
    {label:"text", section:["Ce que les communs nous apprennent de la gouvernance","Les huit principes"],
     texte:"Ostrom en dégage huit, tirés de l'observation de centaines de cas concrets : irrigation, pêcheries, forêts communales. Le troisième nous intéresse particulièrement ici.",
     idees:[{id:502, cite:"tirés de l'observation de centaines de cas concrets", statut:'nouveau',
       tags:['methode'], motscles:['induction','terrain'],
       resume:"Les principes sont inductifs, issus de cas observés."}]},
    {label:"blockquote", etat:"debattu",
     section:["Ce que les communs nous apprennent de la gouvernance","Les huit principes"],
     texte:"La plupart des personnes concernées par les règles peuvent participer à les modifier.",
     idees:[{id:503, cite:"peuvent participer à les modifier", statut:'commente',
       tags:['principe'], motscles:['légitimité','participation'],
       resume:"La légitimité d'une règle tient à qui peut la changer.",
       commentaires:[{qui:"Pierre", quoi:"C'est le principe 3, mot pour mot. Utile à citer en AG."},
                     {qui:"Marie", quoi:"« Peuvent participer », pas « participent ». La nuance compte."}]}]},
    {label:"text", section:["Ce que les communs nous apprennent de la gouvernance","Les huit principes"],
     texte:"La formule est prudente. Elle ne dit pas que tout le monde décide de tout, mais que personne n'est structurellement empêché de peser sur les règles qui le concernent.",
     idees:[{id:504, cite:"personne n'est structurellement empêché de peser sur les règles qui le concernent",
       statut:'commente', tags:['principe','mode'], motscles:['empêchement','participation'],
       resume:"Le critère porte sur l'absence d'empêchement, pas sur la participation effective.",
       commentaires:[{qui:"Amina", quoi:"C'est la différence entre une porte ouverte et une invitation."}]}]},
    {label:"picture", section:["Ce que les communs nous apprennent de la gouvernance","Les huit principes"],
     texte:"", legende:"Système d'irrigation communal, huerta de Valence. Photo : CC-BY Ferran Cornellà."},
    {label:"list_item", section:["Ce que les communs nous apprennent de la gouvernance","Les huit principes"],
     texte:"Des limites clairement définies"},
    {label:"list_item", section:["Ce que les communs nous apprennent de la gouvernance","Les huit principes"],
     texte:"Des règles adaptées aux conditions locales"},
    {label:"list_item", section:["Ce que les communs nous apprennent de la gouvernance","Les huit principes"],
     texte:"Des dispositifs de choix collectif ouverts aux concernés"}
  ]},

audio: {
  titre:"Conseil du 12 mars — enregistrement",
  dossier:"Conseil d'administration", visibilite:"👥",
  source:"conseil-2026-03-12.m4a · 3 min 12 · 5 locuteurs",
  meta:"Audio · transcription diarisée · 13 tours",
  note:{titre:"L'audio ne passe pas par Docling, et c'est normal",
    corps:"Un enregistrement n'a ni page ni mise en page : son unité naturelle est le " +
      "<strong>tour de parole</strong>. L'élément porte un locuteur et un intervalle en secondes, là où " +
      "un PDF porte une page et des boîtes. C'est le seul cas où la glissière reste utile en lecture : " +
      "<strong>qui parle et quand, c'est du contenu</strong>. Attention — il n'existe aujourd'hui " +
      "<strong>aucune ingestion audio vers ElementDocument</strong> : la transcription vit dans " +
      "<code>transcription_raw</code> et un HTML diarisé."},
  elements:[
    {label:"utterance", qui:"Marie", debut:0, duree:14,
     texte:"Je pense qu'on va beaucoup trop vite sur ce dossier, et je voudrais qu'on prenne le temps de l'expliquer aux équipes avant de trancher.",
     idees:[{id:601, cite:"je voudrais qu'on prenne le temps de l'expliquer aux équipes", statut:'nouveau',
       tags:['methode','principe'], motscles:['pédagogie','préalable'],
       resume:"L'explication aux équipes est posée en préalable à la décision."}]},
    {label:"utterance", qui:"Jonas", debut:14, duree:13,
     texte:"On a déjà repoussé deux fois cette décision, à un moment il faut trancher, sinon on ne fera jamais rien.",
     idees:[{id:602, cite:"On a déjà repoussé deux fois cette décision, à un moment il faut trancher",
       statut:'commente', tags:['probleme'], motscles:['temporalité','décision'],
       resume:"L'ajournement répété est présenté comme un coût en soi.",
       commentaires:[{qui:"Amina", quoi:"Deux reports, c'est factuel. Mais ça n'oblige pas à décider mal."},
                     {qui:"Marie", quoi:"Je note qu'on n'a jamais dit pourquoi on avait reporté."}]}]},
    {label:"utterance", qui:"Marie", debut:27, duree:16,
     texte:"Trancher oui, mais pas sans avoir consulté les personnes qui vont vivre avec cette décision au quotidien.",
     idees:[{id:603, cite:"pas sans avoir consulté les personnes qui vont vivre avec cette décision",
       statut:'commente', tags:['principe','methode'], motscles:['consultation','légitimité'],
       resume:"La consultation des personnes concernées est érigée en condition de légitimité.",
       commentaires:[{qui:"Pierre", quoi:"C'est le principe 3 d'Ostrom, mot pour mot."}]}]},
    {label:"utterance", qui:"Amina", debut:43, duree:19, etat:"debattu",
     texte:"Je rejoins ce que dit Marie. On est en train de décider pour des gens qui ne sont pas dans la pièce, et qui n'ont même pas été prévenus qu'on en parlait aujourd'hui.",
     idees:[{id:604, cite:"On est en train de décider pour des gens qui ne sont pas dans la pièce",
       statut:'commente', tags:['probleme','phenomene'], motscles:['absence','procédure'],
       resume:"L'absence des personnes concernées est décrite comme un vice de procédure.",
       commentaires:[{qui:"Jonas", quoi:"D'accord sur le constat, pas sur la conclusion."},
                     {qui:"Sonia", quoi:"On pourrait les inviter en visio, ça lève l'objection."},
                     {qui:"Marie", quoi:"La visio ne remplace pas le fait de les prévenir à l'avance."}]}]},
    {label:"utterance", qui:"Jonas", debut:62, duree:11,
     texte:"D'accord, je l'entends. Mais alors on se donne une date ferme, sinon on repousse encore de six mois."},
    {label:"utterance", qui:"Pierre", debut:73, duree:6,
     texte:"Est-ce qu'on a une idée du budget que ça représente ?"},
    {label:"utterance", qui:"Sonia", debut:79, duree:17,
     texte:"Sur le budget, on est à quatre pour cent d'augmentation, essentiellement le coût de l'énergie et l'embauche au secrétariat.",
     idees:[{id:605, cite:"quatre pour cent d'augmentation, essentiellement le coût de l'énergie et l'embauche au secrétariat",
       statut:'nouveau', tags:['phenomene'], motscles:['budget','énergie'],
       resume:"La hausse budgétaire est rapportée à deux causes identifiées."}]},
    {label:"utterance", qui:"Pierre", debut:96, duree:12,
     texte:"Quatre pour cent, c'est en dessous de l'inflation. On ne peut pas dire qu'on dérape."},
    {label:"utterance", qui:"Marie", debut:108, duree:19,
     texte:"Le sujet n'est pas le montant, c'est la manière dont on décide. Dix mille euros engagés sans que personne ne l'ait vu passer, c'est ça qui pose problème.",
     idees:[{id:606, cite:"Le sujet n'est pas le montant, c'est la manière dont on décide", statut:'nouveau',
       tags:['axiome','principe'], motscles:['gouvernance','recadrage'],
       resume:"Le débat est déplacé du montant vers la procédure de décision."},
      {id:607, cite:"Dix mille euros engagés sans que personne ne l'ait vu passer", statut:'commente',
       tags:['phenomene'], motscles:['montant','opacité'],
       resume:"Un engagement de dix mille euros a été pris hors du regard collectif.",
       commentaires:[{qui:"Pierre", quoi:"Le montant est exact, je l'ai vérifié au compte 606."}]}]},
    {label:"utterance", qui:"Jonas", debut:127, duree:14,
     texte:"Alors on fixe un seuil. Au-delà de dix mille euros, ça passe en assemblée générale, point.",
     idees:[{id:608, cite:"Au-delà de dix mille euros, ça passe en assemblée générale", statut:'nouveau',
       tags:['methode'], motscles:['seuil','assemblée'],
       resume:"Un seuil chiffré est proposé comme règle de passage en assemblée."}]},
    {label:"utterance", qui:"Sonia", debut:141, duree:20,
     texte:"Attention, si on fixe un seuil en euros sans le réévaluer, dans cinq ans l'inflation l'aura vidé de son sens.",
     idees:[{id:609, cite:"si on fixe un seuil en euros sans le réévaluer, dans cinq ans l'inflation l'aura vidé de son sens",
       statut:'commente', tags:['conjecture','probleme'], motscles:['inflation','indexation'],
       resume:"Un seuil nominal non indexé perd son sens avec le temps.",
       commentaires:[{qui:"Jonas", quoi:"On l'indexe sur le budget total, alors. Cinq pour cent."}]}]},
    {label:"utterance", qui:"Marie", debut:161, duree:18,
     texte:"Je propose qu'on repousse d'une semaine, qu'on invite les personnes concernées, et qu'on décide la semaine prochaine avec elles.",
     idees:[{id:610, cite:"qu'on repousse d'une semaine, qu'on invite les personnes concernées",
       statut:'nouveau', tags:['methode','mode'], motscles:['report','invitation'],
       resume:"Une décision différée d'une semaine, en présence des concernés, est proposée."}]},
    {label:"utterance", qui:"Jonas", debut:179, duree:13,
     texte:"Une semaine, pas plus. Et on met l'ordre du jour par écrit cette fois."}
  ]}
,
fevrier: {
  titre:"Conseil du 9 février — enregistrement",
  source:"conseil-2026-02-09.m4a · 2 min 41 · 4 locuteurs",
  meta:"Audio · transcription diarisée · 8 tours",
  note:{titre:"Séance précédente", corps:"Le conseil du 9 février, où la règle de séquence a été posée."},
  elements:[
    {label:"utterance", qui:"Marie", debut:0, duree:11,
     texte:"On reprend le point qu'on n'a pas fini la dernière fois, celui des engagements."},
    {label:"utterance", qui:"Pierre", debut:11, duree:13,
     texte:"On avait dit qu'on validerait le budget avant de signer quoi que ce soit.",
     idees:[{id:701, cite:"On avait dit qu'on validerait le budget avant de signer quoi que ce soit",
       statut:'commente', tags:['principe','methode'], motscles:['séquence','budget'],
       resume:"Une règle de séquence budget-avant-signature avait déjà été posée.",
       commentaires:[{qui:"Marie", quoi:"Et personne ne l'a appliquée depuis. C'est le sujet."}]}]},
    {label:"utterance", qui:"Jonas", debut:24, duree:14,
     texte:"D'accord sur le principe. Reste à savoir à partir de quel montant on considère que c'est un engagement."},
    {label:"utterance", qui:"Sonia", debut:38, duree:24,
     texte:"Ça dépend de ce qu'on appelle engagement. Un abonnement annuel, c'est un engagement ? Une commande ponctuelle ?"},
    {label:"utterance", qui:"Amina", debut:62, duree:17,
     texte:"Pour moi, trois mille euros, c'est déjà beaucoup pour une décision de bureau.",
     idees:[{id:702, cite:"trois mille euros, c'est déjà beaucoup pour une décision de bureau",
       statut:'nouveau', tags:['conjecture'], motscles:['seuil','bureau'],
       resume:"Un premier seuil implicite, plus bas, avait été évoqué en février."}]},
    {label:"utterance", qui:"Pierre", debut:79, duree:19,
     texte:"On n'a pas tranché ce jour-là. On s'est dit qu'on regarderait les comptes d'abord."},
    {label:"utterance", qui:"Marie", debut:98, duree:31,
     texte:"Et les comptes sont arrivés en mars. Donc on aurait pu trancher depuis un mois."},
    {label:"utterance", qui:"Jonas", debut:129, duree:32,
     texte:"Je propose qu'on remette ce point à l'ordre du jour de la prochaine séance, avec une proposition écrite."}
  ]},

statuts: {
  titre:"Statuts de la coopérative — version 2023",
  source:"statuts-2023.pdf · 11 pages",
  meta:"PDF · 28 éléments · ingéré le 14 janvier 2026",
  note:{titre:"Le cadre", corps:"Les statuts en vigueur, adoptés en assemblée générale de 2023."},
  elements:[
    {label:"title", page:1, texte:"Statuts de la Coopérative des Trois Vallées"},
    {label:"section_header", page:1, texte:"Titre I — Forme et objet"},
    {label:"text", page:1,
     texte:"La coopérative est constituée sous forme de société coopérative d'intérêt collectif à capital variable."},
    {label:"section_header", page:2, texte:"Titre III — Assemblée générale"},
    {label:"text", page:2,
     texte:"L'assemblée générale est seule compétente pour les engagements pluriannuels et pour toute modification des présents statuts.",
     idees:[{id:801, cite:"L'assemblée générale est seule compétente pour les engagements pluriannuels",
       statut:'nouveau', tags:['loi','structure'], motscles:['assemblée','compétence'],
       resume:"Les statuts réservent les engagements pluriannuels à l'assemblée générale."}]},
    {label:"section_header", page:3, texte:"Titre IV — Conseil d'administration"},
    {label:"text", page:3,
     texte:"Le conseil rend compte de ses décisions à la plus prochaine assemblée générale ordinaire.",
     idees:[{id:802, cite:"Le conseil rend compte de ses décisions à la plus prochaine assemblée",
       statut:'commente', tags:['loi','methode'], motscles:['compte rendu','conseil'],
       resume:"Une obligation de compte rendu a posteriori pèse sur le conseil.",
       commentaires:[{qui:"Sonia", quoi:"Donc décider vite n'est pas illégal. C'est juste discutable."}]}]},
    {label:"text", page:4,
     texte:"Le conseil se réunit au moins quatre fois par an, sur convocation de son président ou à la demande du tiers de ses membres."},
    {label:"section_header", page:5, texte:"Titre V — Règlement intérieur"},
    {label:"text", page:5,
     texte:"Tout seuil financier fixé par le conseil doit figurer au règlement intérieur, porté à la connaissance de l'assemblée.",
     idees:[{id:803, cite:"Tout seuil financier fixé par le conseil doit figurer au règlement intérieur",
       statut:'nouveau', tags:['loi','methode'], motscles:['seuil','règlement'],
       resume:"Un seuil décidé par le conseil n'a de portée qu'inscrit au règlement."}]},
    {label:"text", page:6,
     texte:"Le règlement intérieur est adopté par le conseil et communiqué aux sociétaires dans le mois qui suit son adoption."}
  ]}
};

/* =========================================================================
   LES DERIVATIONS
   Aucune de ces valeurs n'est ecrite : elles sont toutes recalculees.
   ========================================================================= */

/* Toutes les idees d'un document, dans l'ordre des elements. */
function toutesLesIdeesDuDocument(cle) {
  var liste = [];
  (DOCUMENTS[cle].elements || []).forEach(function (element, index) {
    (element.idees || []).forEach(function (idee) {
      liste.push({idee: idee, element: element, indexElement: index});
    });
  });
  return liste;
}

/* L'ancrage d'une idee : l'element qui la porte et ses bornes REELLES.
   Les offsets ne sont jamais tapes — ils sont retrouves dans le texte.
   / Offsets are found in the text, never typed. */
function ancrageDeLIdee(identifiant) {
  var trouve = null;
  Object.keys(DOCUMENTS).forEach(function (cle) {
    toutesLesIdeesDuDocument(cle).forEach(function (entree) {
      if (String(entree.idee.id) !== String(identifiant)) return;
      var texte = entree.element.texte || '';
      var debut = texte.indexOf(entree.idee.cite);
      trouve = {
        source: cle,
        idee: entree.idee,
        element: entree.element,
        indexElement: entree.indexElement,
        debut: debut,
        fin: debut === -1 ? -1 : debut + entree.idee.cite.length,
        introuvable: debut === -1
      };
    });
  });
  return trouve;
}

/* Le catalogue plat de toutes les extractions du corpus, ancrages compris.
   C'est LA liste que les trois ecrans partagent. */
function catalogueDesExtractions() {
  var catalogue = [];
  Object.keys(DOCUMENTS).forEach(function (cle) {
    toutesLesIdeesDuDocument(cle).forEach(function (entree) {
      var texte = entree.element.texte || '';
      var debut = texte.indexOf(entree.idee.cite);
      catalogue.push({
        id: entree.idee.id,
        source: cle,
        note: DOCUMENTS[cle].titre,
        citation: entree.idee.cite,
        resume: entree.idee.resume,
        tags: entree.idee.tags,
        statut: entree.idee.statut,
        motscles: entree.idee.motscles || [],
        commentaires: entree.idee.commentaires || [],
        indexElement: entree.indexElement,
        debut: debut,
        fin: debut === -1 ? -1 : debut + entree.idee.cite.length,
        qui: entree.element.qui || null,
        debutAudio: entree.element.debut,
        dureeAudio: entree.element.duree,
        page: entree.element.page || null,
        pageFin: entree.element.pageFin || null
      });
    });
  });
  return catalogue;
}

/* Combien d'extractions porte une note. Jamais annonce, toujours compte. */
function nombreDExtractions(cleDeSource) {
  return toutesLesIdeesDuDocument(cleDeSource).length;
}

/* La COUVERTURE : combien d'elements portent au moins une extraction.
   C'est la jointure que l'ecran pretend etre — donc on la fait vraiment.
   / The join the screen claims to be. */
function couvertureDuDocument(cle) {
  var elements = DOCUMENTS[cle].elements || [];
  var couverts = elements.filter(function (e) { return (e.idees || []).length > 0; });
  return {
    note: DOCUMENTS[cle].titre,
    source: cle,
    elements: elements.length,
    couverts: couverts.length,
    /* Les elements sans extraction : ce que l'analyse n'a jamais touche. */
    nonCouverts: elements
      .filter(function (e) { return !(e.idees || []).length && (e.texte || '').length > 40; })
      .map(function (e) { return (e.texte || '').slice(0, 70) + '…'; })
  };
}

/* Ce qu'une synthese N'A PAS repris : difference d'ensembles, calculee.
   / Set difference, computed — never a hand-written list. */
function extractionsEcartees(identifiantsDuPerimetre, identifiantsCites) {
  var cites = {};
  identifiantsCites.forEach(function (id) { cites[String(id)] = true; });
  return identifiantsDuPerimetre.filter(function (id) { return !cites[String(id)]; });
}

/* Les identifiants cites par un article, dans l'ordre d'apparition. */
function identifiantsCitesParLArticle(article) {
  var ordre = [], vus = {};
  article.sections.forEach(function (section) {
    section.paragraphes.forEach(function (p) {
      (p.sources || []).forEach(function (id) {
        if (!(String(id) in vus)) { vus[String(id)] = true; ordre.push(id); }
      });
    });
  });
  return ordre;
}

/* Un minutage « 01:48 » en secondes, pour les Media Fragments URI.
   Retirer les deux-points donnait « 148 » au lieu de 108 : le selecteur
   etait faux des qu'on depassait la minute. / Colons are not decoration. */
function secondesDepuisMinutage(minutage) {
  var morceaux = String(minutage).split(':').map(Number);
  return morceaux.length === 2 ? morceaux[0] * 60 + morceaux[1] : morceaux[0];
}
function fragmentTemporel(debutSecondes, finSecondes) {
  return '#t=npt:' + debutSecondes + ',' + finSecondes;
}
