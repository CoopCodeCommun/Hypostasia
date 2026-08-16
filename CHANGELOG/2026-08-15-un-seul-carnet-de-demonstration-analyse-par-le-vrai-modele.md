# UN SEUL CARNET DE DEMONSTRATION, ANALYSE PAR LE VRAI MODELE

**Date :** 2026-08-15
**Migration :** Non

**Quoi / What :** le carnet « Demonstration — moteur reel » et ses deux
textes en dur disparaissent ; ce sont les vrais documents du depot qui
sont analyses. / The toy notebook is gone; the repository's own
documents are the ones being analysed.

### CE QUE LE MAINTENEUR A VU, ET POURQUOI IL AVAIT RAISON

Deux carnets de demonstration, dont un nomme « moteur reel » — ce qui
disait, sans le vouloir, que l'autre ne l'etait pas.

C'etait exact. Sur 19 extractions, 7 venaient du modele (deux textes
INVENTES, ecrits en dur dans un fichier Python, avec une URL
`exemple.test`) et 12 etaient ecrites a la main. Et TROIS documents sur
six n'avaient aucune extraction : la demonstration montrait des
documents vides.

### L'EXPLICATION TIENT A UN CROISEMENT DE DATES

`charger_fixtures_llm_reel` date du 10 aout 2026, `charger_fixtures_sample`
du 11. La premiere est donc ANTERIEURE aux documents etalons du depot :
elle avait le bon principe — ingerer puis analyser POUR DE VRAI — mais
sur deux textes jouets, dans son propre carnet, faute de mieux a se
mettre sous la dent. Son auteur le savait et l'ecrivait en bas de
fichier : « EXTENSION (lot complet — a faire quand le budget le
permet) : PDF… Audio… ».

Le lendemain, `charger_fixtures_sample` a livre exactement cela — les six
documents, PDF et audio compris — mais sans les faire analyser. Les deux
commandes se sont croisees sans se rejoindre. Le branchement de la
premiere dans l'installation, la veille, a fige le malentendu.

### CE QUI REMPLACE

`analyser_les_notes_etalons` ne cree NI note NI carnet : elle prend
celles qui sont deja la et les envoie a l'analyse. Il n'y a donc plus
qu'un seul carnet de demonstration.

    Badgeons la Normandie          28 elements  → file Celery
    Presentation Hypostasia V3    549 elements  → SAUTEE (cout)
    Debat IA — transcription       12 elements  → file Celery
    Palais Cesar — deux locuteurs   9 elements  → file Celery
    Etude epistemologique          11 elements  → file Celery
    Presentation des Open Badges   61 elements  → file Celery

La Presentation V3 porte 549 elements a elle seule, soit 73 % du corpus
etalon : l'analyser a chaque installation neuve couterait cher sans rien
montrer de plus qu'un document plus court. Le seuil est explicite
(`LIMITE_D_ELEMENTS_POUR_ANALYSE`) et la note sautee est annoncee, avec
le moyen de passer outre.

### LES DEUX ORIGINES D'EXTRACTION COEXISTENT, ET C'EST VOULU

`charger_extractions_demo` reste : ses extractions ECRITES A LA MAIN
couvrent des cas qu'un modele ne produit pas de facon fiable — marques
imbriquees, ancre portee par un tableau, cartes a 0/1/2 commentaires.
C'est la matiere qui sert a styler l'interface.

La garde distingue les deux par un detail qui existait deja : les jobs
poses a la main n'ont pas d'`ai_model`. Regarder les seules extractions
aurait saute exactement les notes qu'il fallait analyser.

### L'IDEMPOTENCE N'EST PLUS UNE OPTION

L'ancienne commande rejouait de vrais appels payants a chaque
execution ; il fallait lui passer `--si-absent` pour la rendre
supportable dans un script rejoue a chaque demarrage du conteneur. La
nouvelle n'analyse par construction que ce qui ne l'est pas encore — les
jobs `pending` et `processing` comptent aussi, sans quoi un redemarrage
en plein traitement aurait tout renvoye en file. `--forcer` reste pour
rejouer volontairement.

Supprimes : `charger_fixtures_llm_reel.py` et son test d'idempotence.

