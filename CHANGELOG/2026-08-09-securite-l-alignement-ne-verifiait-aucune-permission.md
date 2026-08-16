# SECURITE : l'alignement ne verifiait aucune permission

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** `/alignement/tableau/` et
`/alignement/export_markdown/` ne controlaient RIEN.
`?dossier_id=N` alignait n'importe quel carnet, `?page_ids=1,2`
n'importe quelles notes — par leur simple identifiant, sans etre
connecte. Le tableau produit affiche le TEXTE des extractions et leurs
resumes, et l'export en fait un fichier telechargeable : c'etait une
fuite directe et complete du contenu prive d'autrui. Repere en portant
l'onglet Alignement du carnet, corrige ici.

**Le correctif** applique la regle deja en vigueur partout ailleurs
(`_utilisateur_a_acces_dossier`, `_utilisateur_a_acces_page` : on
accede a une note si on accede a AU MOINS UN carnet qui la contient),
aux DEUX vecteurs — le mode `page_ids` etait le plus grave, deux
identifiants suffisaient.

**Le filtrage est SILENCIEUX**, et c'est un choix : une page interdite
est retiree exactement comme une page inexistante, un carnet interdit
repond comme un carnet absent, **au meme octet**. Repondre « acces
refuse » aurait confirme l'existence de la note — c'est la doctrine du
404 plutot que du 403 deja retenue pour les bases privees (phase H
corpus). Deux tests le verifient en comparant les reponses.

**Le superuser garde son acces en lecture** : la regle du produit lui
en accorde un, et un alignement plus strict que le reste serait
incoherent.

**Trois classes de tests existantes passaient GRACE au trou**
(`Phase18EndpointTableauTest`, `Phase18EndpointExportMarkdownTest`,
`Phase18bDossierAlignementEndpointTest`) : elles creent des pages et un
dossier sans owner et appelaient l'endpoint en ANONYME. Ces objets
« legacy » sont lisibles par tout utilisateur AUTHENTIFIE — c'est deja
ce que fait `/lire/` pour eux. Les tests se connectent desormais et
redeviennent ce qu'ils sont : des tests du RENDU du tableau.

**Preuve que les tests mordent** : les gardes ont ete temporairement
neutralisees, 7 des 11 tests de securite echouent ; restaurees, les 11
passent. Verifie aussi en conditions reelles sur le dev — anonyme, un
carnet prive repond 404, ses notes par `page_ids` 400, l'export 404,
aucune occurrence de leur contenu ; le carnet public repond 200.

616 tests unitaires et 104 e2e verts.

| Fichier | Changement |
|---|---|
| `front/views_alignement.py` | controle d'acces sur les deux vecteurs, filtrage silencieux |
| `front/tests/test_alignement_permissions.py` | **nouveau** : 11 tests (fuite, oracle, export, superuser, non-regression) |
| `front/tests/test_phases.py` | 3 classes Phase18 connectees — elles passaient grace au trou |

### Migration
- **Migration necessaire / Migration required :** Non.

