"""
Fixtures de demonstration passees par de VRAIS appels LLM, pour
comparer le rendu reel a la maquette etalon (tmp/maquettes/).
/ Demo fixtures produced through REAL LLM calls, to compare the live
rendering with the reference mock.

LOCALISATION : front/management/commands/charger_fixtures_llm_reel.py

POURQUOI CETTE COMMANDE EXISTE
`charger_fixtures_demo` fabrique des extractions et des statuts A LA
MAIN : pratique, mais ce ne sont pas les sorties du vrai moteur.
L'etalon `tmp/maquettes/donnees.js` le dit lui-meme : « on comparera
ses sorties a celles du vrai moteur ». Cette commande-ci monte donc un
carnet dont les NOTES sont ingerees par le flux ELEMENT (Docling reel)
et ANALYSEES par le vrai LLM configure — les extractions, leurs tags
et leurs resumes viennent du modele, pas de nous. Seuls les
commentaires (deliberation humaine) sont poses a la main, exactement
comme l'etalon les pose.
/ The notes go through the real ELEMENT ingestion and the real LLM;
only the human comments are hand-written, as in the reference mock.

REJOUABLE (choix du proprietaire) : chaque execution refait de VRAIS
appels LLM. `--reset` supprime d'abord le carnet et ses notes.

COUT : chaque note = une conversion Docling (charge des modeles, lent)
+ un appel LLM facture. On reste sur un petit lot ; l'extension au PDF
(qui peuplera aussi les provenance.boites du visualiseur U6) et a
l'audio est notee en bas de fichier.

USAGE :
    docker exec hypostasia_dev_web python manage.py charger_fixtures_llm_reel --reset
"""

import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (
    CategorieDossier,
    Configuration,
    Dossier,
    ListeDeCategories,
    Page,
    VisibiliteDossier,
    empreinte_du_texte,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from hypostasis_extractor.models import (
    AnalyseurSyntaxique,
    AncrageExtraction,
    CommentaireExtraction,
    ExtractedEntity,
    ExtractionJob,
)

NOM_DU_CARNET = "Démonstration — moteur réel"

# Un axe de classement et ses categories : ce sont les « tags » que
# l'etalon pose sur ses idees (donnees.js). Le LLM les produit dans ses
# extractions ; l'axe les rend visibles a l'ecran corpus.
# / One classification axis whose categories are the étalon's idea tags.
AXE_NATURE = "Nature de l'idée"
CATEGORIES_NATURE = [
    ("Principe", "#2563eb"),
    ("Méthode", "#059669"),
    ("Problème", "#dc2626"),
    ("Phénomène", "#7c3aed"),
    ("Conjecture", "#d97706"),
    ("Axiome", "#0891b2"),
]

# Deux notes reelles, courtes (le cout LLM suit la longueur). La
# premiere passe par l'import fichier (.md -> Docling), la seconde par
# la capture web (HTML -> Docling). Les deux flux ELEMENT qu'on vient
# de livrer (BR-B et U4). / Two short real notes: one via file import,
# one via web capture — the two ELEMENT flows.
NOTE_MD = {
    "titre": "Ostrom — gouverner les communs",
    "fichier": "ostrom-communs.md",
    "markdown": (
        "# Gouverner les communs\n\n"
        "Elinor Ostrom montre qu'entre l'État et le marché existe une "
        "troisième voie : l'autogouvernement des ressources communes. "
        "Sa thèse s'oppose à la « tragédie des communs » de Hardin, "
        "pour qui une ressource partagée est fatalement surexploitée.\n\n"
        "## Les principes de conception\n\n"
        "La réussite d'une institution commune tient à des règles "
        "claires : des frontières définies, une cohérence entre les "
        "règles et la ressource, la participation des usagers aux "
        "décisions, et des sanctions graduées en cas de manquement.\n\n"
        "La confiance et la réciprocité sont les deux moteurs de "
        "l'émergence d'une gouvernance partagée durable."
    ),
    "commentaires": [
        ("Jonas", "C'est le cœur de notre démonstration : la troisième voie."),
        ("Amina", "Les sanctions graduées, c'est ce qui manque à beaucoup de collectifs."),
    ],
}
NOTE_WEB = {
    "titre": "L'IA comme commun numérique",
    "url": "https://exemple.test/ia-commun-numerique",
    "html": (
        "<html><body>"
        "<h1>L'IA comme commun numérique</h1>"
        "<p>Les principes d'Ostrom trouvent un écho dans le numérique. "
        "Les logiciels libres et les bases de connaissances "
        "collaboratives sont des ressources communes gérées par leurs "
        "usagers.</p>"
        "<h2>Une gouvernance à inventer</h2>"
        "<p>Gouverner l'intelligence artificielle comme un commun "
        "suppose des règles claires, une participation des usagers et "
        "des mécanismes de contrôle gradués — exactement la grammaire "
        "des institutions communes.</p>"
        "</body></html>"
    ),
    "commentaires": [
        ("Sonia", "Le parallèle avec le logiciel libre mérite d'être creusé."),
    ],
}


class Command(BaseCommand):
    help = (
        "Monte un carnet de démonstration dont les notes sont ingérées "
        "par le flux ELEMENT et analysées par le VRAI LLM configuré."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Supprime le carnet et ses notes avant de recommencer.",
        )
        parser.add_argument(
            "--si-absent", action="store_true", dest="si_absent",
            help=(
                "Ne fait rien si la démonstration porte déjà des "
                "extractions, ou si une analyse est déjà en file. "
                "Utilisé par install.sh, que le conteneur rejoue à "
                "chaque démarrage."
            ),
        )
        parser.add_argument(
            "--asynchrone", action="store_true", dest="asynchrone",
            help=(
                "Envoie les analyses dans la file Celery au lieu de les "
                "exécuter sur place. L'installation rend la main tout de "
                "suite et les analyses se suivent depuis le menu des "
                "tâches. Les commentaires humains ne sont alors PAS "
                "posés : ils s'ancrent sur des extractions que le modèle "
                "n'a pas encore produites."
            ),
        )

    def handle(self, *args, **options):
        # GARDE DE COUT (15 aout 2026). Cette commande est REJOUABLE par
        # conception : chaque execution refait de vrais appels factures.
        # C'est ce qu'on veut a la main. Mais elle est aussi appelee par
        # `install.sh`, que le conteneur rejoue a CHAQUE demarrage : sans
        # cette garde, un simple `docker compose restart` refacturerait
        # deux analyses. L'installation doit TESTER les cles API, pas les
        # consommer en boucle.
        # / Cost guard: the command is replayable by design, but
        # install.sh runs on every container start. The install must TEST
        # the API keys, not burn them.
        if options.get("si_absent") and self._la_demonstration_est_deja_analysee():
            self.stdout.write(
                "Démonstration déjà analysée par le modèle — rien à "
                "refaire (--si-absent). Pour tout rejouer : --reset.",
            )
            return

        configuration = Configuration.get_solo()
        if not configuration.ai_active or not configuration.ai_model:
            raise CommandError(
                "L'IA n'est pas active ou aucun modèle n'est configuré : "
                "impossible de produire des fixtures par vrai LLM.",
            )
        analyseur = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="analyser",
        ).order_by("-est_par_defaut", "name").first()
        if analyseur is None:
            raise CommandError("Aucun analyseur d'extraction actif.")

        proprietaire = self._proprietaire()

        if options["reset"]:
            self._reset(proprietaire)

        self.asynchrone = options.get("asynchrone", False)

        carnet = self._creer_le_carnet(proprietaire)
        categories = self._creer_l_axe_et_les_categories(carnet)

        # Note 1 : import fichier .md -> Docling -> ELEMENT -> LLM.
        page_md = self._creer_page_markdown(proprietaire)
        self._ingerer_un_fichier_markdown(page_md, NOTE_MD["markdown"])
        self._analyser_reellement(page_md, analyseur, configuration.ai_model)
        ranger_une_note_dans_un_carnet(page_md, carnet, proprietaire)

        # Note 2 : capture web -> Docling -> ELEMENT -> LLM.
        page_web = self._creer_page_web(proprietaire)
        self._ingerer_une_capture(page_web)
        self._analyser_reellement(page_web, analyseur, configuration.ai_model)
        ranger_une_note_dans_un_carnet(page_web, carnet, proprietaire)

        # Les commentaires s'ancrent sur les extractions que le modele
        # vient de produire : en asynchrone, elles n'existent pas encore.
        # / Comments anchor onto the extractions the model just produced;
        # asynchronously, those do not exist yet.
        if self.asynchrone:
            self.stdout.write(self.style.SUCCESS(
                f"\nCarnet « {NOM_DU_CARNET} » monté : 2 notes ingérées, "
                f"leurs analyses envoyées dans la file Celery et "
                f"analysées par {configuration.ai_model} en arrière-plan. "
                f"Suivez-les depuis le menu des tâches de "
                f"{proprietaire.username}. Les commentaires humains ne "
                f"sont pas posés en asynchrone.",
            ))
            return

        self._poser_des_commentaires(page_md, NOTE_MD["commentaires"], proprietaire)
        self._poser_des_commentaires(page_web, NOTE_WEB["commentaires"], proprietaire)

        self.stdout.write(self.style.SUCCESS(
            f"\nCarnet « {NOM_DU_CARNET} » prêt : 2 notes ingérées par le "
            f"moteur ELEMENT et analysées par {configuration.ai_model}. "
            f"Comparez /carnets/{carnet.pk}/ à l'étalon tmp/maquettes/corpus.html.",
        ))

    # ---- briques ----

    def _la_demonstration_est_deja_analysee(self):
        """
        Dit si le carnet de demonstration porte deja des extractions.
        / Says whether the demo notebook already carries extractions.

        LOCALISATION : front/management/commands/charger_fixtures_llm_reel.py

        On regarde les EXTRACTIONS, pas la seule existence du carnet :
        une premiere installation interrompue — cle absente, appel en
        erreur — laisse un carnet vide, et il faut alors retenter au
        demarrage suivant. Sans quoi la demonstration resterait nue pour
        toujours, et les cles ne seraient jamais testees.
        / We look at extractions, not at the notebook alone: an
        interrupted first install leaves an empty notebook, and that must
        be retried on the next start.

        ET AUSSI LES ANALYSES ENCORE EN FILE

        En asynchrone, les extractions n'existent pas encore tant que le
        worker n'a pas fini. Un conteneur redemarre entre-temps les
        renverrait toutes en file — et les refacturerait — puisque rien
        ne prouverait qu'une analyse est deja partie. Un job `pending` ou
        `processing` compte donc comme un travail deja lance.
        / A queued job counts too: otherwise a restart would re-queue and
        re-bill every analysis still in flight.

        :return: True si une note du carnet porte une extraction, ou si
            une analyse est deja en attente ou en cours
        """
        from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

        notes_du_carnet = {
            "job__page__appartenances_dossiers__dossier__name": NOM_DU_CARNET,
        }
        if ExtractedEntity.objects.filter(**notes_du_carnet).exists():
            return True

        return ExtractionJob.objects.filter(
            page__appartenances_dossiers__dossier__name=NOM_DU_CARNET,
            status__in=["pending", "processing"],
        ).exists()

    def _proprietaire(self):
        # Meme regle que charger_fixtures_sample : un compte
        # d'administration d'abord (superuser, puis staff), et seulement
        # a defaut le premier venu. Les analyses partent dans la file
        # Celery et se suivent depuis le menu des taches, qui ne montre a
        # chacun que SES notes : le proprietaire decide donc de qui voit
        # l'installation travailler.
        # / Same rule as charger_fixtures_sample: an admin account first,
        # since ownership decides who sees the install working.
        proprietaire = User.objects.filter(is_superuser=True).order_by("pk").first()
        if proprietaire is None:
            proprietaire = User.objects.filter(is_staff=True).order_by("pk").first()
        if proprietaire is None:
            proprietaire = User.objects.order_by("pk").first()
        if proprietaire is None:
            raise CommandError("Aucun utilisateur en base pour posséder le carnet.")
        return proprietaire

    def _reset(self, proprietaire):
        # Le carnet est cherche par son NOM SEUL, sans filtrer sur le
        # proprietaire courant : celui-ci peut avoir change entre deux
        # executions (la regle de choix prefere desormais un compte
        # d'administration). Filtrer dessus laissait l'ancien carnet en
        # place et en creait un second, homonyme — constate le 15 aout
        # 2026. / Searched by name alone: the owner may have changed
        # between runs, which used to leave a duplicate notebook behind.
        for ancien in Dossier.objects.filter(name=NOM_DU_CARNET):
            self._supprimer_le_carnet(ancien)

    def _supprimer_le_carnet(self, ancien):
        """
        Supprime un carnet de demonstration et les notes qui n'ont que lui.
        / Deletes a demo notebook and the notes it alone holds.

        LOCALISATION : front/management/commands/charger_fixtures_llm_reel.py
        """
        if ancien is None:
            return
        # Les pages rangees UNIQUEMENT dans ce carnet sont a nous : on les
        # emporte. On ne touche pas a une note partagee ailleurs.
        # / Only pages filed solely in this notebook are ours to remove.
        for page in Page.objects.filter(appartenances_dossiers__dossier=ancien).distinct():
            autres = page.appartenances_dossiers.exclude(dossier=ancien).exists()
            if not autres:
                # Defaire l'ancrage AVANT la note. Une analyse produit
                # des ancrages ; un ancrage protege son ElementDocument,
                # qui protege sa Page — `page.delete()` seul etait donc
                # refuse des la premiere execution reussie
                # (ProtectedError, constate le 15 aout 2026). On defait
                # dans l'ordre inverse de la construction : ancrages,
                # elements, puis la note.
                # / Undo the anchoring before the note: an anchor
                # protects its element, which protects its page.
                AncrageExtraction.objects.filter(
                    element__page=page,
                ).delete()
                page.elements.all().delete()
                page.delete()
        ancien.delete()
        self.stdout.write("Carnet précédent supprimé (--reset).")

    def _creer_le_carnet(self, proprietaire):
        carnet, cree = Dossier.objects.get_or_create(
            name=NOM_DU_CARNET, owner=proprietaire,
            defaults={"visibilite": VisibiliteDossier.PUBLIC},
        )
        self.stdout.write(("Carnet créé." if cree else "Carnet réutilisé.")
                          + f" pk={carnet.pk}")
        return carnet

    def _creer_l_axe_et_les_categories(self, carnet):
        axe, _ = ListeDeCategories.objects.get_or_create(
            nom=AXE_NATURE, dossier=carnet, defaults={"ordre": 0},
        )
        categories = {}
        for ordre, (nom, couleur) in enumerate(CATEGORIES_NATURE):
            categorie, _ = CategorieDossier.objects.get_or_create(
                liste=axe, nom=nom, defaults={"couleur": couleur, "ordre": ordre},
            )
            categories[nom] = categorie
        return categories

    def _creer_page_markdown(self, proprietaire):
        return Page.objects.create(
            title=NOTE_MD["titre"],
            original_filename=NOTE_MD["fichier"],
            source_type="file",
            html_original="", html_readability="", text_readability="",
            content_hash=empreinte_du_texte(NOTE_MD["markdown"]),
            owner=proprietaire, status="completed",
        )

    def _ingerer_un_fichier_markdown(self, page, markdown):
        # On ecrit le .md dans un fichier temporaire et on appelle le VRAI
        # service d'ingestion (Docling), en synchrone : la commande attend
        # le resultat. / Write the .md and call the real ingestion service.
        from hypostasis_extractor.services.ingestion_docling import ingerer_un_fichier

        self.stdout.write("  Ingestion Docling du .md (charge les modèles, patience)…")
        with tempfile.TemporaryDirectory() as repertoire:
            chemin = Path(repertoire) / NOTE_MD["fichier"]
            chemin.write_text(markdown, encoding="utf-8")
            elements = ingerer_un_fichier(page, str(chemin))
        page.refresh_from_db()

    def _creer_page_web(self, proprietaire):
        return Page.objects.create(
            title=NOTE_WEB["titre"], url=NOTE_WEB["url"], source_type="web",
            html_original=NOTE_WEB["html"],
            html_readability=NOTE_WEB["html"],
            text_readability="",
            content_hash=empreinte_du_texte(NOTE_WEB["html"]),
            owner=proprietaire, status="completed",
        )

    def _ingerer_une_capture(self, page):
        from hypostasis_extractor.services.ingestion_docling import ingerer_une_capture_web

        self.stdout.write("  Ingestion Docling du HTML capturé…")
        elements = ingerer_une_capture_web(page)
        page.refresh_from_db()

    def _analyser_reellement(self, page, analyseur, ai_model):
        # Meme construction que la vue d'analyse (front/views.py) : job
        # PENDING avec le snapshot du prompt, puis on execute la tache
        # ELEMENT EN SYNCHRONE (.apply) pour attendre le vrai appel LLM.
        # / Same as the analysis view, then run the ELEMENT task
        # synchronously to await the real LLM call.
        from hypostasis_extractor.models import PromptPiece
        from hypostasis_extractor.tasks_element import (
            analyser_une_page_avec_le_moteur_element,
        )

        # Une page sans element n'a rien a ancrer : l'analyse produirait
        # des extractions sans passage. On le dit et on passe.
        # (Le flag `Page.moteur` disait cela avant sa suppression ; la
        # question se pose maintenant aux elements eux-memes.)
        # / No element, nothing to anchor: say it and move on.
        if not page.elements.exists():
            self.stdout.write(self.style.WARNING(
                f"  Page {page.pk} sans élément (ingestion échouée) : "
                f"analyse sautée.",
            ))
            return

        pieces = PromptPiece.objects.filter(analyseur=analyseur).order_by("order")
        prompt_snapshot = "\n".join(piece.content for piece in pieces)
        job = ExtractionJob.objects.create(
            page=page, ai_model=ai_model,
            name=f"Analyseur: {analyseur.name}",
            prompt_description=prompt_snapshot,
            status="pending",
            raw_result={"analyseur_id": analyseur.pk},
        )
        # En asynchrone, la tache part dans la file Celery : le worker la
        # prendra, et l'utilisateur en suit l'avancement depuis le menu
        # des taches. L'installation n'attend donc pas le modele.
        # / Asynchronously the task goes to the Celery queue; the install
        # does not wait on the model.
        if getattr(self, "asynchrone", False):
            analyser_une_page_avec_le_moteur_element.delay(job.pk)
            self.stdout.write(
                f"  Analyse envoyée dans la file Celery (job {job.pk}, "
                f"{ai_model}).",
            )
            return

        self.stdout.write(f"  Appel LLM réel ({ai_model})…")
        analyser_une_page_avec_le_moteur_element.apply(args=[job.pk])
        job.refresh_from_db()
        nombre = ExtractedEntity.objects.filter(job__page=page).count()
        self.stdout.write(self.style.SUCCESS(
            f"  Analyse {job.status} : {nombre} extraction(s) réelle(s).",
        ))

    def _poser_des_commentaires(self, page, commentaires, proprietaire):
        # La deliberation humaine : posee a la main, comme l'etalon. On
        # commente les premieres extractions produites par le LLM.
        # / Human deliberation, hand-written like the étalon.
        extractions = list(
            ExtractedEntity.objects.filter(
                job__page=page, masquee=False,
            ).order_by("start_char")[:len(commentaires)]
        )
        for extraction, (qui, quoi) in zip(extractions, commentaires):
            auteur, _ = User.objects.get_or_create(
                username=qui.lower(),
                defaults={"first_name": qui},
            )
            CommentaireExtraction.objects.create(
                entity=extraction, user=auteur, commentaire=quoi,
            )
        if extractions:
            self.stdout.write(f"  {len(extractions)} commentaire(s) humain(s) posé(s).")


# EXTENSION (lot « complet » — a faire quand le budget le permet) :
#   - PDF : ajouter une note source_type='file' avec un vrai .pdf de
#     media/sources/ ; ingerer_un_fichier remplira les provenance.boites,
#     ce qui debloque le visualiseur PDF U6.
#   - Audio : ingerer une transcription diarisee (source_type='audio')
#     apres la bascule audio (decision D2, ordre 3, mesure D3 faite).
#   Chaque note suit le meme patron : creer -> ingerer -> analyser -> ranger.
