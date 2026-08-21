"""
Le worker du SECOND AVIS : sa file, sa concurrence, et son `nice`.
/ The second-opinion worker: its queue, its concurrency, its nice level.

LOCALISATION : hypostasis_extractor/tests/test_worker_du_juge_local.py

CE QUE CES TESTS PROTEGENT, ET POURQUOI AUCUN N'EST DECORATIF.

Le juge local charge 5,13 Go (les quatre encodeurs residents, mesure du 19 aout) et coute moins d'une demi-seconde de
processeur PAR PAIRE. Trois reglages le rendent supportable, et aucun
des trois ne leve d'erreur s'il disparait :

- **sa file dediee** : laisse sur la file par defaut, qui est a
  concurrence 2, DEUX inferences pourraient tourner ensemble — seize
  threads sur huit coeurs — et Docling mourrait de faim ;
- **la concurrence 1** : la meme raison, du cote du worker ;
- **`nice -n 19`** : c'est ce qui remplace une porte « attendre que le
  CPU baisse ». Sans lui, le worker redevient un voisin ordinaire, et
  personne ne s'en apercoit avant que Docling ne traine.

Ces trois-la vivent dans des fichiers de conf que rien d'autre ne
verifie : une reecriture de `supervisord.conf` les emporterait en
silence.
/ Three settings, none of which raises an error when it disappears.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

RACINE = Path(__file__).resolve().parents[2]
FICHIERS_SUPERVISORD = {
    "dev": RACINE / "supervisord-dev.conf",
    "prod": RACINE / "supervisord.conf",
}
NOM_DU_PROGRAMME = "celery_worker_juge_local"
FILE_DU_JUGE_LOCAL = "verification_locale"


def _commande_du_programme(chemin, nom_du_programme):
    """La ligne `command=` d'un programme supervisord. / Its command line."""
    contenu = chemin.read_text(encoding="utf-8")
    bloc = re.split(r"^\[program:", contenu, flags=re.MULTILINE)
    for morceau in bloc:
        if not morceau.startswith(f"{nom_du_programme}]"):
            continue
        for ligne in morceau.splitlines():
            if ligne.startswith("command="):
                return ligne[len("command="):].strip()
    return None


class LeWorkerDuJugeLocalTest(SimpleTestCase):
    """Les trois réglages, dans les DEUX environnements."""

    def test_le_programme_existe_dans_les_deux_environnements(self):
        for environnement, chemin in FICHIERS_SUPERVISORD.items():
            with self.subTest(environnement=environnement):
                self.assertIsNotNone(
                    _commande_du_programme(chemin, NOM_DU_PROGRAMME),
                    f"{chemin.name} n'a pas de programme "
                    f"« {NOM_DU_PROGRAMME} ».",
                )

    def test_il_sert_sa_file_dediee_et_elle_seule(self):
        for environnement, chemin in FICHIERS_SUPERVISORD.items():
            with self.subTest(environnement=environnement):
                commande = _commande_du_programme(chemin, NOM_DU_PROGRAMME)
                self.assertIn(f"-Q {FILE_DU_JUGE_LOCAL}", commande)
                # Jamais melangee avec Docling : une inference de sept
                # gigaoctets ne doit pas retarder une conversion.
                # / Never mixed with Docling.
                self.assertNotIn("ingestion_docling", commande)

    def test_il_reste_a_concurrence_1(self):
        # Deux inférences en même temps feraient douze threads sur huit
        # cœurs, sans rien accélérer. / Two at once would not help.
        for environnement, chemin in FICHIERS_SUPERVISORD.items():
            with self.subTest(environnement=environnement):
                commande = _commande_du_programme(chemin, NOM_DU_PROGRAMME)
                self.assertIn("--concurrency=1", commande)

    def test_il_est_lance_sous_nice(self):
        # LE RÉGLAGE LE PLUS FRAGILE : il tient en trois mots au début
        # d'une ligne de conf, et rien ne le redemande. Sans lui, le
        # juge local cesse d'être prioritaire-bas et Docling traîne —
        # sans qu'aucune erreur ne le dise.
        # / The most fragile setting: three words, no error if lost.
        for environnement, chemin in FICHIERS_SUPERVISORD.items():
            with self.subTest(environnement=environnement):
                commande = _commande_du_programme(chemin, NOM_DU_PROGRAMME)
                self.assertTrue(
                    commande.startswith("nice -n 19 celery "),
                    f"{chemin.name} : la commande doit commencer par "
                    f"« nice -n 19 celery », elle vaut « {commande} ».",
                )

    def test_aucun_autre_worker_ne_consomme_la_file_du_juge_local(self):
        # Sinon la concurrence 1 ne veut plus rien dire.
        # / Otherwise concurrency 1 means nothing.
        for environnement, chemin in FICHIERS_SUPERVISORD.items():
            with self.subTest(environnement=environnement):
                contenu = chemin.read_text(encoding="utf-8")
                lignes_de_commande = [
                    ligne for ligne in contenu.splitlines()
                    if ligne.startswith("command=")
                    and FILE_DU_JUGE_LOCAL in ligne
                ]
                self.assertEqual(len(lignes_de_commande), 1)

    def test_l_arret_laisse_finir_un_paquet(self):
        # Les tâches ne sont pas en `acks_late` : un paquet tué à l'arrêt
        # est perdu. Dix paires durent ~5 à 10 s (quatre encodeurs, mesure du 19 août).
        # / Tasks are not acks_late: a packet killed on stop is lost.
        for environnement, chemin in FICHIERS_SUPERVISORD.items():
            with self.subTest(environnement=environnement):
                contenu = chemin.read_text(encoding="utf-8")
                bloc = contenu.split(f"[program:{NOM_DU_PROGRAMME}]")[1]
                attentes = re.findall(r"^stopwaitsecs=(\d+)", bloc,
                                      flags=re.MULTILINE)
                self.assertTrue(attentes, "stopwaitsecs manquant.")
                self.assertGreaterEqual(int(attentes[0]), 300)


class LeRoutageDeLaTacheDuJugeLocalTest(SimpleTestCase):
    """La tâche part sur sa file, et pas sur une autre."""

    def test_la_tache_est_routee_vers_la_file_dediee(self):
        from hypostasia.celery import celery_app

        routes = celery_app.conf.task_routes
        self.assertEqual(
            routes.get("front.tasks.noter_avec_le_juge_local_task", {})
            .get("queue"),
            FILE_DU_JUGE_LOCAL,
        )

    def test_la_verification_de_production_reste_sur_la_file_par_defaut(self):
        # Le juge d'API coûte des secondes : il n'a rien à faire dans une
        # file à concurrence 1 derrière une heure d'inférence locale.
        # / The API judge costs seconds; it must not queue behind an hour.
        from hypostasia.celery import celery_app

        self.assertNotIn(
            "front.tasks.verifier_les_citations_task",
            celery_app.conf.task_routes,
        )
