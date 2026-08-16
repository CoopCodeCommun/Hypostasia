# R6 : LE LECTEUR AUDIO EXISTE (ecart n°2 de l'etalon, le dernier ouvert)

**Date :** 2026-08-13
**Migration :** Non

**Quoi / What :** une barre de lecture en bas de l'ecran, avec un rail
d'un segment par tour de parole. / A playback bar with one rail segment
per speech turn.

### CE QUI EXISTAIT, ET N'ETAIT PAS UN LECTEUR

Mesure du 12 aout sur la note 8 : **0 balise `<audio>`, aucune tete de
lecture, aucun rail**. Le produit portait depuis PHASE-15 une « barre de
progression de lecture » dont le nom trompait : elle suit le
DEFILEMENT du texte, pas le son. On pouvait la voir avancer sans
qu'aucun son ne sorte.

### CE QUI A ETE BATI

- `front/templates/front/includes/_lecteur_audio.html` — la barre, 62px,
  `fixed` en bas. Rendue si la note est un audio **et** qu'un media est
  attache : une transcription sans son (la note 7, dont le
  `source_file` est un `.json`) garderait sinon un bouton qui ne joue
  rien.
- `front/static/front/js/lecteur_audio.js` — mise a l'echelle du rail
  sur `loadedmetadata`, tete de lecture, minutage, tour courant marque
  dans la marge. Le texte suit l'oreille **pendant la lecture
  seulement**, et au changement de tour seulement.
- `rendu_elements.py` expose `debut`/`fin` BRUTS a cote du minutage
  formate : le rail calcule avec, la gouttiere affiche l'autre. Reparser
  « 00:00 » aurait perdu les decimales — les tours de la note 8 durent
  0,4 seconde.
- Le minutage de la gouttiere devient un `<button>` qui ecoute a partir
  de la. Il DISAIT deja l'instant ; il ne manquait qu'a l'atteindre.

### UN LOCUTEUR AVAIT DEUX COULEURS SUR LE MEME ECRAN

Le rail a rendu visible un desaccord qui existait deja : les pilules de
filtre et la timeline prenaient la palette TAILWIND
(`transcription_audio.py:23`) quand la gouttiere prend celle de WONG
(`rendu_elements.py:585`). `speaker_1` etait donc **bleu en haut et
orange en bas**, a 700 pixels d'ecart. Suivre un debat, c'est suivre qui
parle : deux codes couleur contradictoires coutent plus cher qu'aucun
code. Les widgets prennent desormais Wong.

### DEUX ECARTS ASSUMES AVEC L'ETALON

1. **Segments en absolu, non empiles en `flex`.** L'empilement suppose
   que les tours se touchent. Ils ne se touchent pas : le premier finit
   a 0,5s, le second commence a 0,7s. En flex, chaque segment derive de
   la somme des silences qui le precedent, et la tete de lecture ne
   tombe plus sur le tour qu'on entend.
2. **Filet `--filet`, non `2px solid var(--cible)`.** Le violet marque
   dans l'etalon ce qui n'existe PAS ENCORE.

### LA BARRE VIT HORS DE `#zone-lecture`

`lectureReload` remplace tout l'`innerHTML` de cette zone apres chaque
operation d'element : un lecteur qui vivrait dedans serait detruit et
recree a chaque extraction, et l'audio repartirait a zero au milieu de
l'ecoute. Elle suit donc le chemin OOB du fil d'Ariane, redeposee par
TOUS les ecrans — un ecran sans audio rend un conteneur vide, sans quoi
la barre survivrait a la note qu'elle joue.

### A SAVOIR : LE DEPLACEMENT EXIGE NGINX

`/media/` est servi par `django.views.static` en dev
(`hypostasia/urls.py:32`), qui **ne gere pas les requetes `Range`** : sur
un enregistrement long, se deplacer ne marchera pas en dev. En prod,
nginx le sert (`nginx/default.conf:25`) et gere `Range` nativement.

### RESTE OUVERT — DECISION DU MAINTENEUR

**Deux rails a l'ecran** : celui du lecteur, et la timeline
click-to-scroll de PHASE-15 que l'etalon decrivait comme « l'existant »
a remplacer. Le rail fait plus ; la timeline garde le defilement au
clic, sans equivalent. Non tranche.

### DEUXIEME PASSE — LE SURLIGNAGE ET LE BOUTON DE GOUTTIERE

Deux remarques du mainteneur, le meme jour, sur deux points ou la
premiere version s'ecartait de l'etalon sans raison.

**1. Le tour ecoute se surligne EN ENTIER** (etalon l. 559) :
`background: color-mix(in srgb, var(--statut-commente) 7%, transparent)`
sur tout le bloc. La premiere version posait un lisere dans la
gouttiere, par crainte qu'un fond n'abaisse le contraste du texte.
Mesure au navigateur, note 8 : **clair 16,79:1 -> 14,37:1** (perte de
2,42 points), **sombre 15,10:1 -> 15,30:1** (gain de 0,20). La perte est
reelle en clair, et plus grande que ce que le commentaire annoncait
d'abord — mais 14,37:1 reste trois fois le seuil AA. La crainte etait
fondee sur le principe, sans consequence sur ce texte-la.

**2. Un BOUTON D'ECOUTE dans la gouttiere** (etalon l. 1725-1727), a
cote du minutage et non a sa place. La premiere version faisait du
minutage LUI-MEME un bouton : le minutage est un REPERE qu'on lit pour
situer et pour citer, et un repere qui se souligne au survol invite a
un clic qu'on ne cherchait pas ; l'action, elle, n'etait ecrite nulle
part. Deux objets distincts, donc. Le bouton s'efface (`opacity: 0`) et
parait au survol du bloc ou pendant sa lecture.

  · ECART ASSUME : couleur `--encre-douce`, non le violet `--cible` de
    l'etalon, qui marque ce qui n'existe pas encore.
  · AJOUT : `:focus-visible` revele le bouton. L'etalon ne le montre
    qu'au SURVOL — un geste que le clavier ne fait pas. Sans cette
    regle, on tabule sur un bouton invisible : le focus est quelque
    part, et rien a l'ecran ne le dit.

### TROISIEME PASSE — LE DEPLACEMENT NE MARCHAIT PAS (14 aout)

**Le mainteneur :** « si je clique sur un play dans le texte, l'audio se
lance depuis le debut ».

**LA CAUSE ETAIT SERVEUR.** En dev, `/media/` tombait dans le
`location /` de `nginx/dev.conf`, donc sur `django.views.static.serve`,
qui NE GERE PAS les requetes `Range` — verifie sur Django 6.0.2 :
`FileResponse` n'en contient aucune trace. Elle repond `200 OK` avec le
fichier ENTIER la ou le navigateur demande un morceau. Or un navigateur
IGNORE SILENCIEUSEMENT un `currentTime` qu'il ne peut pas atteindre : ni
erreur, ni exception, la valeur retombe. Le clic demandait 1,9s,
n'obtenait rien, et la lecture partait de zero.

**CE QU'IL NE FALLAIT PAS FAIRE, ET QUI A ETE FAIT D'ABORD.** Contourner
cote client : rejouer le positionnement a chaque `canplay`, forcer
`preload="auto"` + `load()`. Le mainteneur a entendu « un gresillement
dans l'oreille a la place de l'audio » — `load()` vide le tampon sous
une lecture en cours, et le repositionnement rejoue faisait sauter le
decodeur plusieurs fois par seconde. **Un bricolage cote client ne
repare pas un serveur qui ne sait pas envoyer un morceau de fichier : il
ajoute un defaut au premier.**

**LA CORRECTION** tient en un `location /media/` dans `nginx/dev.conf` :
nginx repond `206 Partial Content` nativement, comme il le fait deja en
prod. Mesure sur le vrai serveur : clic sur le 4e tour -> lecture a
4,33s apres 1,2s depuis 3,2s, **sans une ligne de JavaScript**. Dev et
prod servent desormais les medias de la meme facon — un defaut de ce
genre ne peut plus se voir d'un seul cote.

### UN BOUTON « ECOUTER » SUR LES CARTES D'EXTRACTION

Demande du mainteneur, a droite de « Commenter ». Une carte affirme
quelque chose et cite un passage ; sur un audio, cette citation est une
TRANSCRIPTION, donc deja une interpretation. Le bouton permet de
verifier la source plutot que de croire la carte sur parole.

L'INSTANT N'EST PAS RECOPIE dans la carte : le bouton ne porte que
l'identifiant de l'idee, et le JS retrouve sa marque dans le texte pour
lire le minutage du bloc qui la contient. Une donnee ecrite a un seul
endroit ne peut pas diverger de sa copie — et une idee peut avoir
PLUSIEURS ancres, dont le serveur ne saurait pas laquelle choisir.

Pas de bouton sur une ancre detachee : elle a perdu son passage, et le
panneau le dit deja. C'est le SERVEUR qui tranche (`entity.est_detachee`)
— une premiere version laissait le JS retirer ces boutons, ce qui les
faisait disparaitre sous le doigt au gre des swaps HTMX.

### UN SURLIGNAGE ORPHELIN, REVELE PAR CE BOUTON

Cliquer « Écouter » sur une carte declenche un swap HTMX, et
`brancherLeLecteur` oubliait le tour courant SANS effacer sa marque : le
surlignage restait colle au bloc precedent pendant que la lecture etait
ailleurs, et le tour suivant en recevait un second. Mesure : lecture a
4,63s, bloc surligne a 0,0s. Deux tours surlignes a la fois ne designent
plus rien.

**Tests :** 37 nouveaux — `test_lecteur_audio` (5),
`test_barre_du_lecteur_audio` (7), `test_couleurs_des_locuteurs` (4),
`test_gouttiere_audio` (5), `test_service_des_medias` (2),
`test_32_lecteur_audio` e2e (9), plus les gardes ajoutees aux tests
existants. Suite complete : **1894 tests, verts**.

NOTE SUR `test_service_des_medias` : il lit la CONFIGURATION nginx,
faute de pouvoir lire le comportement. Aucun test e2e ne le peut :
`StaticLiveServerTestCase` est un serveur Django, nginx n'est pas dans
sa boucle. C'est aussi pourquoi les e2e gardent
`attendre_que_le_deplacement_soit_possible()` — un helper qui compense
l'ecart entre le serveur de test et le serveur reel, et qui ne prouve
rien du lecteur.

