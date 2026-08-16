"""
Concordance de toutes les copies du referentiel des 30 hypostases.
/ Concordance of every copy of the 30-hypostases reference.

LOCALISATION : hypostasis_extractor/tests/test_referentiel_des_hypostases.py

CE QUE CES TESTS PROTEGENT

Les 30 hypostases de la geometrie des debats sont ecrites en de
nombreux endroits du depot, sous des formes differentes, sans qu'aucun
lien de code ne relie ces copies. Ce fichier en surveille cinq :

  1. `core.models.HypostasisChoices`      — la taxonomie du modele ;
  2. `PIECE_DE_DEFINITIONS_DE_L_EXTRACTION` — le referentiel enseigne au
     LLM dans le prompt (front/services/fixtures_analyseurs.py) ;
  3. `EXTRACTIONS_DE_L_EXEMPLE_FEW_SHOT`  — les 30 exemples livres, un
     par hypostase, qui montrent au modele ce qu'on attend de lui ;
  4. `front.normalisation.HYPOSTASES_CONNUES` — le FILTRE DE PRODUCTION ;
  5. `README.md` — la matrice et les 6 familles publiees aux humains.

UNE SIXIEME A DISPARU, ET C'EST UN GAIN. `front/fixtures/demo_*.json`
portait DOUZE copies de plus, reparties entre des `promptpiece.content`
et des `extractionjob.prompt_description`. Ces fixtures ont ete
supprimees le 15 aout 2026 : rien ne les chargeait, et trois d'entre
elles ne se chargeaient plus depuis cinq mois. Elles pouvaient prendre le
pas sur le prompt du code (voir le commentaire en bas de ce fichier).
/ A sixth source is gone, and that is a gain.

DEUX SOURCES TEXTUELLES RESTENT HORS DE CE FILET : `seed_prompts.py` et
`benchmarks/extraction_format/prompts.py`. Aucune des deux n'est chargee
par l'installation — la premiere est un script d'amorcage historique, la
seconde ne sert qu'au banc d'essai manuel. Elles ont ete corrigees le
14 aout 2026 mais rien ne les surveille : les verifier a la main si le
referentiel evolue.

La quatrieme est la dangereuse. `normaliser_valeur_hypostase()`
SUPPRIME toute hypostase absente de `HYPOSTASES_CONNUES`, en silence,
avant l'ecriture en base. Une valeur ajoutee a `HypostasisChoices` et
oubliee dans ce set serait donc enseignee au modele, rendue par lui, puis
jetee — sans une ligne de log, sans une erreur. L'extraction disparait
et personne ne sait pourquoi.

C'est exactement le genre de derive qu'aucun test ne surveillait :
`front/tests/test_phase29_normalize.py::test_les_30_hypostases_connues`
verrouille bien le COMPTE de la copie n°4, mais rien ne la confronte aux
trois autres. Compter 30 de chaque cote ne dit pas que ce sont les memes
30.
/ The 30 hypostases are written FOUR times with no code link between the
copies. Copy #4 is the production filter: it silently drops anything it
does not know. Nothing compared the four until this file.

CE QUE CES TESTS NE FONT PAS

Ils ne tranchent aucune question de fond. Ils constatent l'etat du
referentiel au 14 aout 2026 et se contentent d'exiger qu'il ne bouge pas
tout seul. Si quelqu'un DECIDE d'ajouter une 31e hypostase ou de
remanier la famille 4, ces tests tomberont — c'est leur role : rendre la
decision visible, pas l'interdire. Le message d'echec dit alors quoi
mettre a jour.
/ These tests decide nothing. They pin the current state and demand that
any change be deliberate.

Lancer avec :
    docker exec -w /app -e POSTGRES_DB=hypostasia_<nom> hypostasia_web \\
        uv run python manage.py test \\
        hypostasis_extractor.tests.test_referentiel_des_hypostases
"""

import json
import os
import re

from django.test import SimpleTestCase

from core.models import HypostasisChoices
from front.normalisation import (
    HYPOSTASES_CONNUES,
    SYNONYMES_HYPOSTASES,
    _normaliser_texte,
    normaliser_valeur_hypostase,
)
from front.services.fixtures_analyseurs import (
    EXTRACTIONS_DE_L_EXEMPLE_FEW_SHOT,
    PIECE_DE_DEFINITIONS_DE_L_EXTRACTION,
)

# Le nombre qui fonde toute la geometrie des debats : 2 dispositifs de
# preuve (formel, empirique) x 3 modes de raisonnement (induction,
# abduction, deduction) = 6 familles, de 5 hypostases chacune.
# / The founding number: 2 proof devices x 3 reasoning modes = 6
# families of 5 hypostases each.
NOMBRE_D_HYPOSTASES_ATTENDU = 30
NOMBRE_DE_FAMILLES_ATTENDU = 6
NOMBRE_D_HYPOSTASES_PAR_FAMILLE = 5


def _hypostases_du_modele():
    """
    Les valeurs de `HypostasisChoices`, forme normalisee.
    / The `HypostasisChoices` values, normalized form.

    On compare toujours sur la forme normalisee (minuscules, sans
    accents) : le modele ecrit « phénomène », le filtre de production
    ecrit « phenomene ». Comparer les formes brutes ferait echouer le
    test sur une difference d'accent qui n'en est pas une.
    / Comparison always happens on the normalized form: the model writes
    accented labels, the production filter writes unaccented keys.
    """
    return {_normaliser_texte(valeur) for valeur in HypostasisChoices.values}


def _hypostases_du_prompt():
    """
    Les hypostases mises en gras dans le referentiel enseigne au LLM.
    / The hypostases bolded in the reference taught to the LLM.
    """
    noms_en_gras = re.findall(
        r"\*\*([^*]+)\*\*", PIECE_DE_DEFINITIONS_DE_L_EXTRACTION,
    )
    return {_normaliser_texte(nom) for nom in noms_en_gras}


def _hypostases_de_l_exemple_few_shot():
    """
    Toutes les hypostases citees par les 30 extractions d'exemple.
    / Every hypostase cited by the 30 example extractions.

    Chaque exemple porte 1 a 2 hypostases separees par une virgule
    (« aporie, probleme »). On les collecte toutes, pas seulement la
    premiere : une hypostase qui n'apparaitrait qu'en seconde position
    est quand meme enseignee au modele.
    / Each example carries 1-2 comma-separated hypostases; all are
    collected, since a second-position one is taught just the same.
    """
    hypostases_citees = set()
    for _citation, _resume, hypostases, _mots_cles in EXTRACTIONS_DE_L_EXEMPLE_FEW_SHOT:
        for hypostase in hypostases.split(","):
            hypostases_citees.add(_normaliser_texte(hypostase))
    return hypostases_citees


def _familles_du_prompt():
    """
    Le referentiel du prompt relu comme {numero de famille: [(nom, mode)]}.
    / The prompt reference parsed as {family number: [(name, mode)]}.

    Le prompt a une structure reguliere qu'on peut relire :

        ## Famille 4 — Non réfuté par déduction formelle (...)
        - **paradigme** : modèle ou exemple. — *non prouvé par abduction empirique*

    On en tire, pour chaque famille, son mode de non-refutation et la
    liste de ses hypostases avec leur mode de non-preuve.
    / The prompt has a regular structure yielding, per family, its
    non-refutation mode and its hypostases with their non-proof mode.
    """
    familles = {}
    numero_de_la_famille_courante = None
    for ligne in PIECE_DE_DEFINITIONS_DE_L_EXTRACTION.split("\n"):
        entete_de_famille = re.search(
            r"## Famille (\d+) — Non réfuté par ([^(]+)", ligne,
        )
        if entete_de_famille:
            numero_de_la_famille_courante = int(entete_de_famille.group(1))
            familles[numero_de_la_famille_courante] = {
                "mode_de_non_refutation": entete_de_famille.group(2).strip(),
                "hypostases": [],
            }
            continue
        ligne_d_hypostase = re.match(
            r"- \*\*([^*]+)\*\* :.*— \*non prouvé par ([^*]+)\*", ligne,
        )
        if ligne_d_hypostase and numero_de_la_famille_courante is not None:
            familles[numero_de_la_famille_courante]["hypostases"].append(
                (
                    _normaliser_texte(ligne_d_hypostase.group(1)),
                    ligne_d_hypostase.group(2).strip(),
                ),
            )
    return familles


class ConcordanceDesQuatreSourcesTest(SimpleTestCase):
    """
    Les quatre copies du referentiel disent-elles la meme chose ?
    / Do the four copies of the reference say the same thing?
    """

    def test_les_quatre_sources_declarent_les_memes_trente_hypostases(self):
        # On compare les ENSEMBLES, pas les comptes. Deux listes de 30
        # peuvent parfaitement differer : c'est meme le scenario le plus
        # probable — une hypostase renommee en remplace une autre et le
        # compte ne bouge pas.
        # / Sets, not counts: a rename keeps the count and breaks the pairing.
        hypostases_du_modele = _hypostases_du_modele()
        hypostases_du_prompt = _hypostases_du_prompt()
        hypostases_de_l_exemple = _hypostases_de_l_exemple_few_shot()
        hypostases_du_filtre = set(HYPOSTASES_CONNUES)

        self.assertEqual(
            len(hypostases_du_modele), NOMBRE_D_HYPOSTASES_ATTENDU,
            "core.models.HypostasisChoices ne declare plus 30 hypostases.",
        )

        sources_a_comparer = [
            ("le prompt (PIECE_DE_DEFINITIONS_DE_L_EXTRACTION)", hypostases_du_prompt),
            ("l'exemple few-shot (EXTRACTIONS_DE_L_EXEMPLE_FEW_SHOT)", hypostases_de_l_exemple),
            ("le filtre de production (HYPOSTASES_CONNUES)", hypostases_du_filtre),
        ]
        for nom_de_la_source, hypostases_de_la_source in sources_a_comparer:
            absentes_de_la_source = hypostases_du_modele - hypostases_de_la_source
            en_trop_dans_la_source = hypostases_de_la_source - hypostases_du_modele
            self.assertEqual(
                (absentes_de_la_source, en_trop_dans_la_source), (set(), set()),
                f"Divergence entre core.models.HypostasisChoices et "
                f"{nom_de_la_source} :\n"
                f"  absentes de cette source : {sorted(absentes_de_la_source)}\n"
                f"  en trop dans cette source : {sorted(en_trop_dans_la_source)}\n"
                f"Les quatre copies du referentiel doivent etre mises a jour "
                f"ensemble — voir le docstring de ce fichier.",
            )

    def test_le_filtre_de_production_conserve_toute_hypostase_du_modele(self):
        """
        Le test qui protege du degat reel, et non de la seule divergence.

        La comparaison d'ensembles ci-dessus regarde le code ; celle-ci
        regarde le COMPORTEMENT. Elle fait passer chaque valeur declaree
        par le modele dans la moulinette que subissent les extractions du
        LLM, et exige qu'elle en ressorte intacte. Une hypostase que le
        filtre ne connait pas est rendue vide : c'est la perte
        silencieuse que ce fichier existe pour empecher.
        / The set comparison inspects the code; this one inspects the
        behaviour, running every declared value through the pipeline's
        actual filter and requiring it to survive.
        """
        for valeur_declaree in HypostasisChoices.values:
            valeur_apres_le_filtre = normaliser_valeur_hypostase(valeur_declaree)
            self.assertEqual(
                valeur_apres_le_filtre, _normaliser_texte(valeur_declaree),
                f"L'hypostase « {valeur_declaree} » est declaree dans "
                f"HypostasisChoices mais le filtre de production la rend "
                f"« {valeur_apres_le_filtre} ». Le LLM peut donc la produire, "
                f"et elle sera jetee sans un mot avant l'ecriture en base. "
                f"Ajouter « {_normaliser_texte(valeur_declaree)} » a "
                f"front.normalisation.HYPOSTASES_CONNUES.",
            )

    def test_l_exemple_few_shot_illustre_chacune_des_trente_hypostases(self):
        """
        Le few-shot livre doit montrer les 30, pas seulement quelques-unes.

        Le banc d'essai du 22 mars 2026
        (benchmarks/extraction_format/2026-03-22_test2_30fewshot.md) a
        mesure ce point : avec 2 extractions d'exemple, Gemini ne rendait
        que 2 classes distinctes ; avec 30, il en rend 20. Le nombre
        d'hypostases illustrees n'est donc pas cosmetique, c'est ce qui
        determine la variete de ce que le modele ose produire.
        / The benchmark measured it: 2 examples yield 2 classes, 30 yield
        20. The count of illustrated hypostases drives output variety.
        """
        self.assertEqual(
            len(EXTRACTIONS_DE_L_EXEMPLE_FEW_SHOT), NOMBRE_D_HYPOSTASES_ATTENDU,
            "L'exemple few-shot ne compte plus une extraction par hypostase.",
        )

        # Chaque exemple porte son hypostase en PREMIERE position : c'est
        # elle que l'exemple est cense illustrer. Les suivantes ne sont
        # que du contexte. / The first position is the illustrated one.
        hypostases_illustrees = [
            _normaliser_texte(hypostases.split(",")[0])
            for _citation, _resume, hypostases, _mots_cles
            in EXTRACTIONS_DE_L_EXEMPLE_FEW_SHOT
        ]
        hypostases_jamais_illustrees = _hypostases_du_modele() - set(
            hypostases_illustrees,
        )
        self.assertEqual(
            hypostases_jamais_illustrees, set(),
            f"Ces hypostases sont enseignees au modele mais aucun exemple "
            f"ne les illustre : {sorted(hypostases_jamais_illustrees)}. Le "
            f"modele les produira moins, voire jamais.",
        )
        self.assertEqual(
            len(set(hypostases_illustrees)), NOMBRE_D_HYPOSTASES_ATTENDU,
            "Deux exemples illustrent la meme hypostase : une autre n'est "
            "donc plus illustree du tout.",
        )


class StructureDeLaGeometrieDesDebatsTest(SimpleTestCase):
    """
    Le referentiel enseigne au LLM respecte-t-il sa propre construction ?
    / Does the reference taught to the LLM respect its own construction?
    """

    def test_le_prompt_classe_les_trente_en_six_familles_de_cinq(self):
        familles = _familles_du_prompt()

        self.assertEqual(
            len(familles), NOMBRE_DE_FAMILLES_ATTENDU,
            f"Le prompt n'annonce plus {NOMBRE_DE_FAMILLES_ATTENDU} familles.",
        )
        for numero_de_famille, contenu_de_la_famille in sorted(familles.items()):
            self.assertEqual(
                len(contenu_de_la_famille["hypostases"]),
                NOMBRE_D_HYPOSTASES_PAR_FAMILLE,
                f"La famille {numero_de_famille} ne compte plus "
                f"{NOMBRE_D_HYPOSTASES_PAR_FAMILLE} hypostases.",
            )

    def test_les_six_familles_couvrent_chacune_les_cinq_autres_modes(self):
        """
        Le motif de la geometrie des debats, exige sur les six familles.

        LE MOTIF. Une famille « non refute par X » range 5 hypostases,
        chacune « non prouvee par Y » avec Y parcourant les CINQ AUTRES
        modes. C'est ce qui fait tenir la construction : 6 familles x 5
        modes restants = 30 cases, une par hypostase, sans trou ni
        doublon. Lu comme une matrice 6x6, le referentiel occupe donc
        exactement toutes les cases hors diagonale.

        CE TEST A D'ABORD ETE ECRIT A L'ENVERS, ET POURQUOI.

        Le 14 aout 2026, la famille 4 (« non refute par deduction
        formelle ») violait seule ce motif :

          - « loi » et « principe » portaient tous deux *non prouve par
            induction empirique* — deux hypostases pour une seule case ;
          - « domaine » portait *non prouve par deduction formelle*,
            soit le mode de sa propre famille : une case diagonale, la
            seule interdite ;
          - *induction formelle* et *deduction empirique* n'etaient donc
            representes par aucune hypostase de cette famille.

        L'anomalie figurait a l'identique dans les SIX sources du
        referentiel (seed_prompts.py, le banc d'essai de mars 2026, le
        prompt de production et les trois fixtures) : elle ne venait pas
        d'une recopie fautive, elle etait dans la saisie d'origine.

        Ce test a donc d'abord constate l'etat de fait — il attendait
        [1, 2, 3, 5, 6] — plutot que d'exiger 6/6. Exiger la conformite
        aurait laisse la suite rouge en permanence sur une question que
        seul le mainteneur pouvait trancher : coquille, ou irregularite
        voulue ? Un test rouge en permanence n'alerte plus, il fait du
        bruit.

        LA DECISION, ET LA CORRECTION QUI EN DECOULE.

        Le mainteneur a tranche le 14 aout 2026 : c'etait une coquille.
        Deux places etaient libres, face a « invariant » et face a
        « evenement », et trois hypostases se disputaient trois cases.
        La correction retenue :

          - « loi » NE BOUGE PAS, face a « approximation ». « Non prouve
            par induction empirique » y decrit le probleme de Hume : une
            correlation ne se prouve pas en generalisant des observations.
          - « principe » passe a *induction formelle*, face a
            « invariant » — la cause a priori repond a ce qui se conserve.
          - « domaine » passe a *deduction empirique*, face a
            « evenement » — l'extension delimitee repond a l'occurrence.

        Les six familles suivent desormais le motif, et ce test l'exige.
        / The maintainer ruled on 14 Aug 2026 that family 4 was a typo.
        The test now requires all six families to follow the pattern.
        """
        familles = _familles_du_prompt()

        familles_conformes = []
        familles_non_conformes = {}
        for numero_de_famille, contenu_de_la_famille in sorted(familles.items()):
            mode_de_la_famille = contenu_de_la_famille["mode_de_non_refutation"]
            modes_des_hypostases = [
                mode for _nom, mode in contenu_de_la_famille["hypostases"]
            ]
            # Deux conditions : cinq modes tous distincts, et aucun d'eux
            # egal au mode de la famille elle-meme.
            # / Five distinct modes, none equal to the family's own.
            les_modes_sont_tous_distincts = (
                len(set(modes_des_hypostases)) == NOMBRE_D_HYPOSTASES_PAR_FAMILLE
            )
            aucun_mode_ne_repete_celui_de_la_famille = (
                mode_de_la_famille not in modes_des_hypostases
            )
            if les_modes_sont_tous_distincts and aucun_mode_ne_repete_celui_de_la_famille:
                familles_conformes.append(numero_de_famille)
            else:
                familles_non_conformes[numero_de_famille] = modes_des_hypostases

        self.assertEqual(
            familles_conformes, [1, 2, 3, 4, 5, 6],
            f"Une famille ne suit plus le motif de la geometrie des debats. "
            f"Chacune doit ranger 5 hypostases portant les 5 modes AUTRES que "
            f"le sien : ni doublon, ni case diagonale.\n"
            f"Familles non conformes : {familles_non_conformes}\n"
            f"Rappel : la famille 4 a ete reparee le 14 aout 2026 (« principe » "
            f"-> induction formelle, « domaine » -> deduction empirique). Si "
            f"elle reapparait ici, la correction a ete perdue dans l'une des "
            f"six sources du referentiel.",
        )


class ReferentielPublieDansLeReadmeTest(SimpleTestCase):
    """
    Le referentiel montre aux humains est-il celui que le code applique ?
    / Is the reference shown to humans the one the code enforces?

    Le README publie les 30 hypostases : la matrice complete, puis les 6
    familles avec leurs definitions. C'est la seule presentation lisible
    du concept fondateur du projet — celle qu'on donne a lire a quelqu'un
    qui decouvre Hypostasia.

    C'est donc une CINQUIEME copie du referentiel, et elle a le meme
    defaut que les quatre autres : rien ne l'oblige a rester d'accord
    avec le code. Pire, sa divergence serait la plus insidieuse — un
    lecteur n'a aucun moyen de savoir que la documentation ment, alors
    qu'un ecart entre deux fichiers de code finit par se voir.
    / The README is a fifth copy, and the most insidious to let drift: a
    reader has no way to tell that the documentation lies.
    """

    def _section_du_readme(self, titre_de_debut, titre_de_fin):
        """
        Decoupe une section du README entre deux titres.
        / Cuts a README section between two headings.
        """
        from django.conf import settings

        chemin_du_readme = os.path.join(settings.BASE_DIR, "README.md")
        contenu_du_readme = open(chemin_du_readme, encoding="utf-8").read()

        self.assertIn(
            titre_de_debut, contenu_du_readme,
            f"Le README n'a plus de section « {titre_de_debut} ». Si elle a "
            f"ete renommee, mettre a jour ce test ; si elle a ete supprimee, "
            f"le referentiel n'est plus documente nulle part pour les humains.",
        )
        return contenu_du_readme.split(titre_de_debut)[1].split(titre_de_fin)[0]

    def test_les_tableaux_par_famille_listent_les_trente_hypostases(self):
        section_des_familles = self._section_du_readme(
            "### Les 6 familles epistemiques", "### Ou vit ce referentiel",
        )
        # Les lignes de tableau ont la forme : | **nom** | definition | mode |
        # / Table rows read: | **name** | definition | mode |
        lignes_de_tableau = re.findall(
            r"^\| \*\*([^*]+)\*\* \| ([^|]+) \| ([^|]+) \|",
            section_des_familles, re.M,
        )
        hypostases_du_readme = {
            _normaliser_texte(nom) for nom, _definition, _mode in lignes_de_tableau
        }

        hypostases_du_modele = _hypostases_du_modele()
        self.assertEqual(
            hypostases_du_readme, hypostases_du_modele,
            f"Le README ne documente plus le meme referentiel que le code.\n"
            f"  absentes du README : "
            f"{sorted(hypostases_du_modele - hypostases_du_readme)}\n"
            f"  en trop dans le README : "
            f"{sorted(hypostases_du_readme - hypostases_du_modele)}",
        )

    def test_la_matrice_du_readme_place_chaque_hypostase_une_seule_fois(self):
        """
        La matrice publiee doit etre celle du prompt, case pour case.

        Elle est la piece la plus fragile du README : 36 cellules ecrites
        a la main, dont 6 vides. Une hypostase recopiee dans la mauvaise
        colonne y passerait inapercue a la lecture, tout en donnant une
        idee fausse de la construction — qui est precisement ce que cette
        section explique.
        / 36 hand-written cells: a misplaced hypostasis would read as
        correct while misrepresenting the very construction it explains.
        """
        section_de_la_matrice = self._section_du_readme(
            "### La matrice complete", "### Les 6 familles epistemiques",
        )

        hypostases_de_la_matrice = []
        for ligne in section_de_la_matrice.split("\n"):
            # Seules les lignes de donnees commencent par un intitule gras.
            # / Only data rows start with a bold row label.
            if not ligne.startswith("| **"):
                continue
            for cellule in [c.strip() for c in ligne.split("|")[2:-1]]:
                if cellule and cellule != "—":
                    hypostases_de_la_matrice.append(_normaliser_texte(cellule))

        self.assertEqual(
            len(hypostases_de_la_matrice), NOMBRE_D_HYPOSTASES_ATTENDU,
            f"La matrice du README contient {len(hypostases_de_la_matrice)} "
            f"hypostases au lieu de {NOMBRE_D_HYPOSTASES_ATTENDU}. Une case a "
            f"ete videe, dupliquee, ou la diagonale n'est plus vide.",
        )
        self.assertEqual(
            set(hypostases_de_la_matrice), _hypostases_du_modele(),
            "La matrice du README ne contient pas les memes hypostases que "
            "core.models.HypostasisChoices.",
        )
        self.assertEqual(
            len(set(hypostases_de_la_matrice)), NOMBRE_D_HYPOSTASES_ATTENDU,
            "Une hypostase apparait deux fois dans la matrice du README : "
            "une autre occupe donc une case qui n'est pas la sienne.",
        )


# LES FIXTURES JSON NE SONT PLUS UNE SOURCE DU REFERENTIEL (15 aout 2026)
#
# Une classe surveillait ici les copies du referentiel portees par
# `front/fixtures/*.json`. Ces quatre fixtures ont ete supprimees : rien
# ne les chargeait — ni l'installation, ni aucun test — et trois d'entre
# elles ne se chargeaient plus depuis le 21 mars 2026, deux migrations
# ayant change le schema sous elles.
#
# Leur disparition SUPPRIME le risque que cette classe surveillait. Elles
# ne portaient pas que des donnees : `demo_ia.json` contenait un
# analyseur « Hypostasia » complet, prompt inclus. Charge par `loaddata`,
# il prenait le pas sur le code — `creer_les_modeles_ia_et_les_analyseurs`
# fait un `get_or_create` sur le NOM et ne garnit le prompt que si
# l'analyseur n'a aucune piece. Une base ou la fixture etait chargee la
# premiere gardait donc le prompt de la FIXTURE pour toujours : un
# referentiel fantome, visible dans aucun fichier Python, et pourtant
# celui qu'un modele recevait.
#
# Le referentiel n'a plus qu'une source vivante, le code, et les classes
# ci-dessus la verrouillent : le modele, le prompt, l'exemple few-shot et
# le filtre de production.
# / A class here watched the reference carried by the JSON fixtures. Those
# fixtures are gone — nothing loaded them, and three had been unloadable
# for five months. Their removal REMOVES the risk this class watched: a
# loaded fixture used to outrank the code's prompt for good. The reference
# now has a single living source, locked by the classes above.


class SynonymesVersLeReferentielTest(SimpleTestCase):
    """
    Les rattrapages de synonymes visent-ils des hypostases reelles ?
    / Do the synonym fallbacks target real hypostases?
    """

    def test_tout_synonyme_pointe_une_hypostase_du_referentiel(self):
        """
        Un synonyme qui vise a cote annule le rattrapage qu'il est cense faire.

        `SYNONYMES_HYPOSTASES` rattrape ce que le LLM produit hors
        referentiel : il pense « proposition », on ecrit « hypothese ».
        Mais la cible du mapping est ensuite soumise au meme filtre que
        tout le reste. Une cible mal orthographiee — « hypothèse » avec
        son accent, « theorie_generale » — serait donc jetee juste apres
        avoir ete substituee. Le LLM aurait rendu quelque chose
        d'exploitable, et il n'en resterait rien.
        / A mistargeted synonym is dropped right after substitution: the
        salvage silently destroys what it was meant to save.
        """
        for synonyme, hypostase_cible in sorted(SYNONYMES_HYPOSTASES.items()):
            self.assertIn(
                hypostase_cible, HYPOSTASES_CONNUES,
                f"Le synonyme « {synonyme} » renvoie vers « {hypostase_cible} », "
                f"qui n'est pas une hypostase connue : la valeur sera "
                f"supprimee juste apres avoir ete substituee.",
            )

    def test_aucun_synonyme_ne_masque_une_hypostase_du_referentiel(self):
        """
        Une hypostase ne doit pas figurer parmi les CLES des synonymes.

        Les cles sont traduites avant d'etre validees. Inscrire une vraie
        hypostase comme cle la ferait donc remplacer par une autre a
        chaque extraction — « loi » deviendrait « regle » deviendrait
        autre chose. L'hypostase serait toujours declaree, toujours
        enseignee, et jamais enregistree.
        / Keys are translated before validation: a real hypostase used as
        a key would be substituted away on every extraction.
        """
        hypostases_utilisees_comme_cles = (
            set(SYNONYMES_HYPOSTASES) & set(HYPOSTASES_CONNUES)
        )
        self.assertEqual(
            hypostases_utilisees_comme_cles, set(),
            f"Ces hypostases du referentiel sont aussi des cles de "
            f"SYNONYMES_HYPOSTASES : {sorted(hypostases_utilisees_comme_cles)}. "
            f"Elles seraient remplacees a chaque extraction.",
        )
