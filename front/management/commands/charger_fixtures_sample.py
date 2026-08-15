"""
Charge les documents etalons de sample/ dans une base vide.
/ Loads the reference documents from sample/ into an empty database.

LOCALISATION : front/management/commands/charger_fixtures_sample.py

POURQUOI CETTE COMMANDE

Une base neuve n'a ni utilisateur, ni carnet, ni note : il n'y a rien a
regarder, donc rien a developper. `sample/` porte les documents etalons
choisis pour couvrir cinq formes d'entree du produit — capture web,
fichier ecrit, transcription deja faite, audio brut, PDF. Cette commande
les transforme en base utilisable, et range le carnet dans une base de
connaissances de demonstration.

CE QU'ELLE NE FAIT PAS

Elle n'appelle JAMAIS Docling sur un docx : le seul exemplaire du depot
est fait de diapositives exportees en images, et Docling n'en extrait
aucun element. Les DEUX PDF, eux, SONT convertis par cette commande
depuis le 11 aout 2026 — mesures : ~98 s et ~2 Gio pour l'etude (3
pages), ~81 s et ~3,4 Gio pour la presentation open badges (4 pages, 61
elements) — voir tmp/benchmark-docling-2026-08-11.md. Ils sont charges
en dernier, une conversion a la fois. / It never runs Docling on a docx.
The two PDF, on the other hand, ARE converted by this command since
11 August — measured at ~98s/~2GiB and ~81s/~3.4GiB.

LANCER LA COMMANDE

    docker exec -w /app hypostasia_web uv run python manage.py \\
        charger_fixtures_sample --a-blanc
    docker exec -w /app hypostasia_web uv run python manage.py \\
        charger_fixtures_sample
"""

import hashlib
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from core.models import (
    AppartenanceDossierBase,
    BaseDeConnaissances,
    Dossier,
    Page,
    TranscriptionConfig,
    TranscriptionProvider,
    VisibiliteDossier,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.services.fixtures_analyseurs import (
    NOM_DE_L_ANALYSEUR_D_EXTRACTION,
    NOM_DE_L_ANALYSEUR_DE_SYNTHESE,
    creer_les_modeles_ia_et_les_analyseurs,
)

User = get_user_model()

NOM_DU_CARNET = "Documents étalons"

# La base de connaissances qui range le carnet des étalons. Le slug est
# posé explicitement (SlugField unique) : le laisser se générer depuis
# le nom romprait sur un accent, et deux exécutions ne doivent jamais
# se heurter dessus. / The slug is set explicitly: never left to
# auto-generate from the accented name.
NOM_DE_LA_BASE_DE_DEMONSTRATION = "Démonstration"
SLUG_DE_LA_BASE_DE_DEMONSTRATION = "demonstration"


# =============================================================================
# LES TEXTES DE PRESENTATION
#
# Le carnet et la base etaient crees SANS description ni guide. Les ecrans
# qui les montrent — liste des carnets, detail d'un carnet, cartes des
# bases — avaient donc raison de paraitre vides : il n'y avait rien a
# montrer. On ne met pas au point une carte de presentation sur un objet
# sans texte de presentation.
#
# Ces textes disent ce que les objets SONT reellement, pas ce qu'on
# aimerait qu'ils soient : ce carnet porte six documents choisis pour
# eprouver le moteur, chacun sur un point precis. Une description de
# fixture qui ment sur son contenu est pire qu'une description absente.
# / These texts describe what the objects actually are.
# =============================================================================

# `Dossier.description` est un CharField(max_length=200) : ce texte doit
# tenir dans 200 signes, un test le verifie.
# / Capped at 200 characters; a test enforces it.
DESCRIPTION_DU_CARNET = (
    "Six documents choisis pour éprouver le moteur : un PDF à coordonnées, "
    "une capture web, un audio transcrit, un long markdown. Chacun met à "
    "l'épreuve un point précis de l'ancrage."
)

# Le guide s'adresse au contributeur AU MOMENT ou il contribue — l'etalon
# (corpus.html) l'affiche en tete du carnet, encadre, pas range dans une
# page d'aide. / Shown at contribution time, not filed in a help page.
GUIDE_DE_REDACTION_DU_CARNET = (
    "Ce carnet sert de banc d'essai : chaque note y est un cas limite, "
    "pas un contenu à lire pour lui-même.\n\n"
    "Avant d'ajouter un document, demandez-vous ce qu'il éprouve que les "
    "six autres n'éprouvent pas — un format, une structure, une façon de "
    "casser l'ancrage. Un septième document qui ressemble aux précédents "
    "allonge les tests sans rien couvrir de plus.\n\n"
    "Les extractions posées ici ne sont pas des opinions sur le texte : "
    "elles existent pour donner à voir les huit familles d'hypostases, "
    "les deux statuts de débat, les marques imbriquées et les ancres qui "
    "enjambent deux éléments."
)

# LES AXES DE CLASSEMENT DU CARNET.
#
# L'etalon (corpus.html) montre les axes en facettes cliquables au haut du
# carnet — « TYPE (4) · THEME (3) · ECHEANCE (2) ». Sans axe en base cette
# rangee reste vide, et l'ecran ne peut ni etre compare a l'etalon ni meme
# etre mis au point : on styleraient des facettes qui ne filtrent rien.
#
# Les deux axes retenus disent ce que ce carnet EST : un banc d'essai. Le
# premier range par format d'entree, le second par ce que le document met
# a l'epreuve. Deux axes croises sur six notes suffisent a montrer le
# mecanisme sans le noyer.
#
# Couleurs : palette de Wong (Nature Methods, 2011), sure pour les huit
# formes de daltonisme — celle que le projet emploie deja par ailleurs.
# / The mockup shows axes as clickable facets; without any, that row stays
# empty. Colours from Wong's colourblind-safe palette.
AXES_DE_CLASSEMENT_DU_CARNET = {
    "Format": {
        "PDF": "#0072B2",
        "Web": "#009E73",
        "Audio": "#D55E00",
        "Markdown": "#CC79A7",
    },
    "Éprouve": {
        "Coordonnées": "#0072B2",
        "Structure": "#009E73",
        "Locuteurs": "#D55E00",
        "Volume": "#E69F00",
    },
}

DESCRIPTION_DE_LA_BASE_DE_DEMONSTRATION = (
    "La base de démonstration d'Hypostasia. Elle rassemble les documents "
    "qui servent à vérifier, à chaque installation, que la chaîne complète "
    "tient debout : importer un document, en extraire des idées, les ancrer "
    "au passage exact dont elles viennent, puis en débattre.\n\n"
    "Rien ici n'est un contenu éditorial. Tout y est un étalon."
)

REPERTOIRE_SAMPLE = Path(settings.BASE_DIR) / "sample"

FICHIER_DE_LA_CAPTURE = "capture-web-badgeons-la-normandie.html"
FICHIER_DU_MARKDOWN = "PRESENTATION-V3.md"
FICHIER_DE_LA_TRANSCRIPTION = "fake_debat_ia_transcription.json"
FICHIER_DU_MP3 = "audio-FR-2locuteur-palaiscesar-14s.mp3"
FICHIER_DU_PDF_ETUDE = "Etude_Epistemologique_IA.pdf"
# Second PDF, ajoute le 11 aout 2026 : plus lourd que l'etude (4 pages,
# 61 elements, ~3 365 Mio au pic contre ~2 031 pour l'etude — voir
# tmp/benchmark-docling-2026-08-11.md § 2). Le nom du fichier porte un
# espace ET un accent : c'est un cas d'usage legitime, pas une raison de
# renommer le fichier verse au depot. / The second PDF's filename carries
# a space AND an accent — a legitimate case, not a reason to rename it.
FICHIER_DU_PDF_OPEN_BADGES = "présentation des open badges.pdf"

# Quelle note va sous quelles categories. La cle est le NOM DE FICHIER
# d'origine : les identifiants changent d'une base a l'autre, pas les
# documents. Une note absente de cette table n'est pas classee — et le
# test qui l'exige echouera, ce qui est le comportement voulu.
#
# Ce bloc vit APRES les noms de fichiers, dont il depend. Le placer plus
# haut levait un NameError au chargement du module.
# / Keyed by source filename: pks differ across databases, documents do
# not. Must sit after the filename constants it references.
CLASSEMENT_DES_NOTES_ETALONS = {
    FICHIER_DE_LA_CAPTURE: ("Web", "Structure"),
    FICHIER_DU_MARKDOWN: ("Markdown", "Volume"),
    FICHIER_DE_LA_TRANSCRIPTION: ("Audio", "Locuteurs"),
    FICHIER_DU_MP3: ("Audio", "Locuteurs"),
    FICHIER_DU_PDF_ETUDE: ("PDF", "Coordonnées"),
    FICHIER_DU_PDF_OPEN_BADGES: ("PDF", "Coordonnées"),
}

# Les deux PDF sont SORTIS de ce refus le 11 aout 2026 : la mesure qui
# manquait existe desormais (voir tmp/benchmark-docling-2026-08-11.md),
# et cette machine a largement assez de memoire libre. Ils sont charges
# en dernier par _charger_le_pdf et _charger_le_pdf_des_open_badges,
# comme les deux plus couteux des six documents — le second (open
# badges) apres le premier (etude), car c'est lui le plus lourd des
# deux. / Both PDF were REMOVED from this refusal on 11 August: the
# missing measurements now exist, and they load last as the costliest
# of the six documents — the heavier one (open badges) after the other.
#
# Le docx, lui, reste refuse : le seul exemplaire du depot est fait de
# diapositives exportees en images, et Docling n'en extrait aucun element.
# Une fixture qui ne produit rien n'eprouve rien. / The docx stays
# refused: the repo's only copy is slide images, and Docling extracts
# zero elements from it — a fixture that produces nothing proves nothing.
EXTENSIONS_REFUSEES = {".docx"}

# Les six documents etalons, par nom de fichier, dans l'ordre de
# chargement. `--fichier` restreint a un sous-ensemble de cette table.
# Les deux PDF sont VOLONTAIREMENT en dernier, le second (open badges)
# apres le premier (etude) : c'est le plus couteux des six (~81 s,
# ~3 365 Mio contre ~98 s, ~2 031 Mio pour l'etude), les quatre autres
# documents doivent etre en base avant eux tous. / The six reference
# documents, in loading order. Both PDF are DELIBERATELY last, the
# heavier one after the other: they are the costliest of the six.
DOCUMENTS_ETALONS = [
    FICHIER_DE_LA_CAPTURE,
    FICHIER_DU_MARKDOWN,
    FICHIER_DE_LA_TRANSCRIPTION,
    FICHIER_DU_MP3,
    FICHIER_DU_PDF_ETUDE,
    FICHIER_DU_PDF_OPEN_BADGES,
]

# L'article d'origine. Sans url, l'idempotence de la capture porterait
# sur un champ vide et deux captures se confondraient.
# / Without a url, the capture's idempotency key would be empty.
URL_DE_LA_CAPTURE = "https://badgeons-la-normandie.fr/"

# Memes identifiants que charger_fixtures_demo : un seul mot de passe a
# retenir, quel que soit l'ordre dans lequel les deux commandes tournent.
# / Same credentials as charger_fixtures_demo: one password to remember.
UTILISATEUR_PAR_DEFAUT = {
    "username": "jonas",
    "email": "jonas@demo.hypostasia.org",
    "password": "admin1234",
}


class Command(BaseCommand):
    help = (
        "Charge les documents etalons de sample/ (capture web, markdown, "
        "transcription JSON, audio, deux PDF) dans un carnet de "
        "demonstration range dans une base de connaissances. N'appelle "
        "jamais Docling sur un docx."
    )

    def add_arguments(self, analyseur_d_arguments):
        analyseur_d_arguments.add_argument(
            "--a-blanc", action="store_true",
            help="Affiche ce qui serait fait, sans rien ecrire.",
        )
        analyseur_d_arguments.add_argument(
            "--sans-mp3", action="store_true",
            help="Saute la transcription Voxtral du fichier audio.",
        )
        analyseur_d_arguments.add_argument(
            "--fichier", action="append", default=None, dest="fichiers",
            help=(
                "Ne charger que ce fichier de sample/, au lieu des six. "
                "Repetable."
            ),
        )
        analyseur_d_arguments.add_argument(
            "--reset", action="store_true",
            help=(
                "Supprime le carnet etalon et ses notes propres avant de "
                "recharger. Refuse si une note porte des ancres."
            ),
        )

    def handle(self, *args, **options):
        self.a_blanc = options["a_blanc"]
        self.sans_mp3 = options["sans_mp3"]
        # Resolu AVANT toute ecriture et toute conversion : un --fichier
        # pointant un PDF doit rendre la main immediatement, pas apres
        # avoir lance Docling. / Resolved before any write or conversion.
        self.fichiers_demandes = self._resoudre_les_fichiers_demandes(
            options["fichiers"],
        )

        if self.a_blanc:
            self.stdout.write(self.style.WARNING(
                "MODE A BLANC — rien ne sera ecrit.",
            ))

        # Le compteur du bilan final (§ 4 de la spec). Il ne compte que
        # les notes sautees PARCE QU'ELLES SONT DEJA LA — pas celles que
        # --sans-mp3 ou --fichier ont exclues, qui n'ont jamais ete
        # candidates. / Counts only notes skipped as already present.
        self.nombre_de_notes_sautees = 0

        proprietaire = self._proprietaire()

        if options["reset"]:
            self._reinitialiser(proprietaire)

        carnet_des_etalons = self._creer_le_carnet(proprietaire)
        # La valeur de retour n'est PAS jetable : c'est la seule config
        # dont on sait qu'elle est bien Voxtral. Voir
        # `_config_voxtral_utilisable`. / Not throwaway: it is the only
        # config known to be Voxtral.
        self.config_de_transcription = self._creer_la_config_de_transcription()
        # Sans analyseur en base, le bouton « Lancer une analyse » n'ouvre
        # aucun sélecteur : les notes chargées juste après seraient
        # illisibles par l'IA. Les analyseurs viennent donc AVANT les
        # documents. / Without an analyzer, the analysis button opens an
        # empty selector, so analyzers come before the documents.
        self._creer_les_analyseurs()

        self._charger_les_documents(proprietaire, carnet_des_etalons)
        # APRES le chargement des documents : on ne peut classer que des
        # notes qui existent. / After loading: only existing notes can be
        # filed.
        if not self.a_blanc:
            self._poser_les_axes_de_classement(carnet_des_etalons)

        self._creer_la_base_de_demonstration(proprietaire, carnet_des_etalons)

        if self.a_blanc:
            self.stdout.write(self.style.WARNING(
                "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
            ))

    def _resoudre_les_fichiers_demandes(self, fichiers_de_l_option):
        """
        Rend la liste des fichiers a charger, en refusant les formats lourds.
        / Returns the files to load, refusing the heavy formats.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        POURQUOI REFUSER PLUTOT QU'IGNORER

        Le PDF et le docx n'ont pas ete eprouves par Docling sur cette
        machine. Une commande de fixtures qui convertit des PDF en masse a
        fait tomber le serveur le 10 aout 2026 : 2 031 Mio et 98 s pour
        trois pages. Les laisser passer en silence rejouerait l'incident ;
        les refuser en le disant oriente vers le chemin prevu pour eux.
        / Refusing loudly beats ignoring silently: mass PDF conversion
        took the server down.
        """
        from django.core.management.base import CommandError

        if not fichiers_de_l_option:
            return list(DOCUMENTS_ETALONS)

        fichiers_retenus = []
        for chemin_demande in fichiers_de_l_option:
            nom_du_fichier = os.path.basename(chemin_demande)
            extension = os.path.splitext(nom_du_fichier)[1].lower()

            if extension in EXTENSIONS_REFUSEES:
                raise CommandError(
                    f"« {nom_du_fichier} » est un {extension} : cette "
                    f"commande ne lance jamais Docling sur ce format. Le "
                    f"seul .docx du dépôt (« présentation des open "
                    f"badges.docx ») est fait de diapositives exportées "
                    f"en images — Docling en extrait zéro élément, une "
                    f"fixture qui ne produit rien n'éprouve rien. Les "
                    f"PDF, eux, sont désormais chargés par défaut par "
                    f"cette commande (voir FICHIER_DU_PDF_ETUDE et "
                    f"FICHIER_DU_PDF_OPEN_BADGES) ; s'il est refusé ici, "
                    f"c'est qu'il ne figure pas dans DOCUMENTS_ETALONS.",
                )

            if nom_du_fichier not in DOCUMENTS_ETALONS:
                raise CommandError(
                    f"« {nom_du_fichier} » n'est pas un document étalon. "
                    f"Attendus : {', '.join(DOCUMENTS_ETALONS)}.",
                )

            fichiers_retenus.append(nom_du_fichier)

        return fichiers_retenus

    def _proprietaire(self):
        """
        Rend le proprietaire des notes etalons, en le creant s'il le faut.
        / Returns the reference notes' owner, creating one if needed.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        Une base neuve n'a AUCUN utilisateur. `charger_fixtures_llm_reel`
        leve une CommandError dans ce cas — c'est precisement le cas que
        cette commande doit savoir traiter.
        / A fresh database has no user at all; this must not be fatal.

        UN COMPTE D'ADMINISTRATION D'ABORD, ET POURQUOI

        Les analyses de la demonstration partent dans la file Celery et
        se suivent depuis le menu des taches — un menu qui ne montre a
        chacun que SES notes. Le proprietaire decide donc de qui voit
        l'installation travailler.

        La regle etait « le premier superuser, sinon le premier
        utilisateur par cle primaire ». Or aucun compte n'est superuser
        dans ce projet, et le premier par pk est un compte de
        demonstration : le 15 aout 2026, sur une base reelle, `marie`
        portait douze notifications et l'administrateur `jonas` n'en
        voyait aucune. On cherche donc aussi le `is_staff` avant de
        retomber sur le premier venu.
        / Ownership decides who sees the install working; a demo account
        used to own everything while the administrator saw nothing.
        """
        proprietaire_existant = User.objects.filter(
            is_superuser=True,
        ).order_by("pk").first()
        if proprietaire_existant is None:
            proprietaire_existant = User.objects.filter(
                is_staff=True,
            ).order_by("pk").first()
        if proprietaire_existant is None:
            proprietaire_existant = User.objects.order_by("pk").first()

        if proprietaire_existant is not None:
            self.stdout.write(
                f"Propriétaire        : {proprietaire_existant.username} (réutilisé)",
            )
            return proprietaire_existant

        self.stdout.write(
            f"Propriétaire        : {UTILISATEUR_PAR_DEFAUT['username']} (créé)",
        )
        if self.a_blanc:
            return None

        proprietaire_cree = User.objects.create_user(
            username=UTILISATEUR_PAR_DEFAUT["username"],
            email=UTILISATEUR_PAR_DEFAUT["email"],
            is_staff=True,
        )
        proprietaire_cree.set_password(UTILISATEUR_PAR_DEFAUT["password"])
        proprietaire_cree.save()
        return proprietaire_cree

    def _creer_le_carnet(self, proprietaire):
        """
        Rend le carnet des documents etalons, en le creant s'il le faut.
        / Returns the reference notebook, creating it if needed.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        LE MODE A BLANC CHERCHE, MAIS NE CREE PAS.

        Rendre `None` sans chercher ferait mentir tout le reste du bilan :
        `_note_deja_presente` rendrait toujours False faute de carnet ou
        regarder, et --a-blanc annoncerait « serait chargee » pour les
        quatre notes alors qu'une vraie execution les sauterait toutes.
        L'option existe pour montrer ce qui se passerait — elle doit dire
        vrai. / A dry run looks the notebook up but never creates it:
        returning None blindly made every downstream line lie.
        """
        if self.a_blanc:
            carnet_existant = None
            if proprietaire is not None:
                carnet_existant = Dossier.objects.filter(
                    name=NOM_DU_CARNET, owner=proprietaire,
                ).first()

            if carnet_existant is not None:
                self.stdout.write(
                    f"Carnet              : {NOM_DU_CARNET} — "
                    f"pk={carnet_existant.pk} (réutilisé)",
                )
            else:
                self.stdout.write(
                    f"Carnet              : {NOM_DU_CARNET} (serait créé)",
                )
            return carnet_existant

        carnet, a_ete_cree = Dossier.objects.get_or_create(
            name=NOM_DU_CARNET, owner=proprietaire,
            defaults={
                "visibilite": VisibiliteDossier.PUBLIC,
                "description": DESCRIPTION_DU_CARNET,
                "guide_de_redaction": GUIDE_DE_REDACTION_DU_CARNET,
            },
        )

        # ON REMPLIT LE VIDE, ON N'ECRASE JAMAIS.
        #
        # Les `defaults` de `get_or_create` ne touchent que les objets
        # qu'il CREE. Le carnet des etalons existe depuis des semaines sur
        # les bases de developpement : sans ce rattrapage il resterait
        # sans description pour toujours, et les ecrans qui l'affichent
        # continueraient d'avoir raison de paraitre vides.
        #
        # Mais la commande se relance a CHAQUE installation. Si elle
        # reimposait ses textes, elle effacerait a chaque fois ce que le
        # mainteneur aurait ecrit lui-meme. D'ou la condition : seul le
        # champ vide est rempli.
        # / defaults only apply to rows it creates, so pre-existing
        # notebooks would stay blank forever. But the command re-runs on
        # every install: fill blanks, never overwrite.
        champs_completes = []
        if not carnet.description.strip():
            carnet.description = DESCRIPTION_DU_CARNET
            champs_completes.append("description")
        if not carnet.guide_de_redaction.strip():
            carnet.guide_de_redaction = GUIDE_DE_REDACTION_DU_CARNET
            champs_completes.append("guide_de_redaction")
        if champs_completes:
            carnet.save(update_fields=champs_completes)

        etat_du_carnet = "créé" if a_ete_cree else "réutilisé"
        if champs_completes and not a_ete_cree:
            etat_du_carnet += f", {' et '.join(champs_completes)} complétée(s)"
        self.stdout.write(
            f"Carnet              : {NOM_DU_CARNET} — pk={carnet.pk} "
            f"({etat_du_carnet})",
        )
        return carnet

    def _poser_les_axes_de_classement(self, carnet):
        """
        Pose les axes du carnet et classe ses notes dessous.
        / Create the notebook's axes and file its notes under them.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        POURQUOI CETTE METHODE EXISTE

        L'etalon montre les axes en facettes cliquables au haut du carnet.
        Sans axe en base, cette rangee reste vide : on ne peut ni comparer
        l'ecran a l'etalon, ni le mettre au point — on stylerait des
        facettes qui ne filtrent rien.

        DES AXES SANS NOTES CLASSEES NE VALENT GUERE MIEUX. Une facette
        qui rend « 0 sur 6 » a chaque clic ne montre pas le mecanisme,
        elle montre un bug. Les deux vont donc ensemble, ici.

        On ne touche a une note que si elle n'a AUCUNE categorie : un
        classement pose a la main ne doit pas etre refait a chaque
        installation. / Axes and filing go together; a hand-made filing is
        never redone.
        """
        from core.models import CategorieDossier, ListeDeCategories

        if carnet is None:
            return

        categories_par_nom = {}
        axes_crees = 0
        for nom_de_l_axe, categories_de_l_axe in AXES_DE_CLASSEMENT_DU_CARNET.items():
            axe, axe_a_ete_cree = ListeDeCategories.objects.get_or_create(
                nom=nom_de_l_axe, dossier=carnet,
            )
            axes_crees += 1 if axe_a_ete_cree else 0
            for rang, (nom_de_la_categorie, couleur) in enumerate(
                categories_de_l_axe.items()
            ):
                categorie, _ = CategorieDossier.objects.get_or_create(
                    liste=axe, nom=nom_de_la_categorie,
                    defaults={"couleur": couleur, "ordre": rang},
                )
                categories_par_nom[nom_de_la_categorie] = categorie

        notes_classees = 0
        for appartenance in carnet.appartenances_pages.select_related("page"):
            if appartenance.categories.exists():
                continue

            # La table de classement est indexee par nom de fichier
            # d'origine. Une note qui n'y figure pas reste non classee :
            # c'est visible, et c'est mieux qu'un rangement au hasard.
            # / A note absent from the table stays unfiled: visible, and
            # better than filing it at random.
            noms_des_categories = CLASSEMENT_DES_NOTES_ETALONS.get(
                appartenance.page.original_filename or "",
            )
            if not noms_des_categories:
                continue

            categories_a_poser = [
                categories_par_nom[nom]
                for nom in noms_des_categories
                if nom in categories_par_nom
            ]
            if categories_a_poser:
                appartenance.categories.set(categories_a_poser)
                notes_classees += 1

        self.stdout.write(
            f"Axes de classement  : {len(AXES_DE_CLASSEMENT_DU_CARNET)} axe(s), "
            f"{notes_classees} note(s) classée(s)",
        )

    def _creer_la_config_de_transcription(self):
        """
        Cree la configuration Voxtral, si la cle API est presente.
        / Creates the Voxtral configuration, if the API key is present.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        SANS CETTE CONFIG, LA TRANSCRIPTION EST MOCKEE EN SILENCE.

        front/tasks.py:633 teste `config.provider == "voxtral"` et retombe
        sinon sur `transcrire_audio_mock`. Sur une base neuve il n'existe
        aucune config : le mp3 produirait un faux verbatim que rien ne
        distinguerait d'une vraie transcription.
        / Without this config the transcription is silently mocked.

        Cle absente : on ne cree RIEN. Une config qui echouera au premier
        appel est pire que pas de config — elle donne l'illusion que la
        chaine est branchee. / An about-to-fail config is worse than none.
        """
        if not os.environ.get("MISTRAL_API_KEY"):
            self.stdout.write(
                "Transcription       : pas de MISTRAL_API_KEY — config non créée",
            )
            return None

        if self.a_blanc:
            self.stdout.write("Transcription       : Voxtral Mini (serait créée)")
            return None

        config, a_ete_creee = TranscriptionConfig.objects.get_or_create(
            name="Voxtral Mini",
            defaults={
                "model_choice": "voxtral-mini-latest",
                "is_active": True,
                "diarization_enabled": True,
                "language": "",
            },
        )
        self.stdout.write(
            f"Transcription       : {config.name} "
            f"({'créée' if a_ete_creee else 'réutilisée'})",
        )
        return config

    def _creer_les_analyseurs(self):
        """
        Cree les modeles IA et les deux analyseurs, via le service partage.
        / Creates the AI models and both analyzers, via the shared service.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        SANS ANALYSEUR, L'APPLICATION NE FAIT PLUS RIEN.

        Cette commande a longtemps charge six documents dans une base qui
        n'avait aucun analyseur : le bouton « Lancer une analyse » n'ouvrait
        aucun sélecteur, faute d'avoir quoi que ce soit à proposer. Un
        corpus qu'on ne peut pas analyser n'éprouve pas le produit.
        / This command used to load six documents into a database with no
        analyzer at all, leaving the analysis button with nothing to offer.

        LA DEFINITION N'EST PAS ICI, ET C'EST VOULU.

        Elle vit dans `front/services/fixtures_analyseurs.py`, partagée avec
        `charger_fixtures_demo`. Recopier ici les quatre pièces de prompt et
        les trente extractions d'exemple aurait donné une seconde version à
        tenir à jour — l'oubli d'origine vient exactement de là.
        / The definition lives in the shared service: a local copy would be
        a second version to maintain, which is how the omission happened.

        Le mode a blanc annonce sans écrire, comme partout ailleurs.
        / Dry run announces without writing, as everywhere else.
        """
        if self.a_blanc:
            self.stdout.write(
                f"Analyseurs IA       : {NOM_DE_L_ANALYSEUR_D_EXTRACTION} + "
                f"{NOM_DE_L_ANALYSEUR_DE_SYNTHESE} (seraient créés)",
            )
            return None

        rapport_des_fixtures_ia = creer_les_modeles_ia_et_les_analyseurs()

        # Les modèles IA dépendent des clés du .env : sans clé, pas de
        # modèle du tout — on le dit, sinon l'IA resterait éteinte sans
        # que personne sache pourquoi. / No key means no model at all, and
        # silence here would leave the AI off for no visible reason.
        if rapport_des_fixtures_ia["aucune_cle_api_detectee"]:
            self.stdout.write(
                "Modèles IA          : aucune clé API dans .env — IA non activée",
            )
        else:
            noms_des_modeles_crees = [
                nom for nom, _cle_env in rapport_des_fixtures_ia["modeles_ia_crees"]
            ]
            if noms_des_modeles_crees:
                self.stdout.write(
                    f"Modèles IA          : {', '.join(noms_des_modeles_crees)} (créés)",
                )
            else:
                self.stdout.write("Modèles IA          : réutilisés")

        # Le détail « 4 pièces, 1 exemple » n'est pas décoratif : c'est
        # l'exemple few-shot qui rend l'analyseur utilisable, et son absence
        # est invisible autrement. / The few-shot example is what makes the
        # analyzer usable, and its absence is invisible otherwise.
        etat_de_l_extraction = (
            f"créé, {rapport_des_fixtures_ia['pieces_de_prompt_creees']} pièces, "
            f"{rapport_des_fixtures_ia['extractions_d_exemple_creees']} extractions d'exemple"
            if rapport_des_fixtures_ia["analyseur_extraction_cree"]
            else "réutilisé"
        )
        etat_de_la_synthese = (
            "créé" if rapport_des_fixtures_ia["analyseur_synthese_cree"] else "réutilisé"
        )
        self.stdout.write(
            f"Analyseurs IA       : "
            f"{rapport_des_fixtures_ia['analyseur_extraction'].name} "
            f"({etat_de_l_extraction}), "
            f"{rapport_des_fixtures_ia['analyseur_synthese'].name} "
            f"({etat_de_la_synthese})",
        )
        return None

    def _reinitialiser(self, proprietaire):
        """
        Supprime le carnet etalon et les notes qui n'appartiennent qu'a lui.
        / Deletes the reference notebook and the notes filed only in it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        POURQUOI CETTE OPTION EXISTE

        L'idempotence saute ce qui est deja la — y compris l'appel Voxtral,
        qu'on veut precisement pouvoir rejouer a chaque chargement. `--reset`
        est la seule facon de tout refaire.
        / Idempotency skips the Voxtral call we want to replay.

        LE GARDE-FOU N'EST PAS FACULTATIF

        `AncrageExtraction.element` est en PROTECT : supprimer une page qui
        porte des ancres leve ProtectedError. On ne se contente pas de
        laisser l'exception sortir — on VERIFIE D'ABORD, et on refuse tout
        en bloc. Une suppression partielle laisserait le carnet a moitie
        vide, dans un etat que personne n'a voulu.
        / Check first and refuse wholesale: a partial delete is worse.
        """
        from django.core.management.base import CommandError

        from hypostasis_extractor.models import AncrageExtraction

        carnet_existant = Dossier.objects.filter(
            name=NOM_DU_CARNET, owner=proprietaire,
        ).first()
        if carnet_existant is None:
            self.stdout.write("Réinitialisation    : aucun carnet à supprimer")
            return None

        # Les notes rangees UNIQUEMENT dans ce carnet sont a nous. Une note
        # rangee ailleurs aussi appartient a ce quelqu'un d'autre.
        # / Only notes filed solely here are ours to remove.
        notes_a_supprimer = []
        for page in Page.objects.filter(
            appartenances_dossiers__dossier=carnet_existant,
        ).distinct():
            rangee_ailleurs = page.appartenances_dossiers.exclude(
                dossier=carnet_existant,
            ).exists()
            if not rangee_ailleurs:
                notes_a_supprimer.append(page)

        # VERIFIER AVANT DE SUPPRIMER.
        notes_avec_ancres = []
        for page in notes_a_supprimer:
            nombre_d_ancres = AncrageExtraction.objects.filter(
                element__page=page,
            ).count()
            if nombre_d_ancres:
                notes_avec_ancres.append((page, nombre_d_ancres))

        if notes_avec_ancres:
            detail = " ; ".join(
                f"« {page.title} » ({nombre} ancre(s))"
                for page, nombre in notes_avec_ancres
            )
            raise CommandError(
                f"--reset refusé : {detail}. Ces notes portent des "
                f"extractions ancrées, et une ancre est une preuve. Rien "
                f"n'a été supprimé. Retirer les portions d'abord, ou "
                f"recharger dans une base neuve.",
            )

        if self.a_blanc:
            self.stdout.write(
                f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
                f"seraient supprimées",
            )
            return None

        for page in notes_a_supprimer:
            page.delete()
        carnet_existant.delete()

        self.stdout.write(
            f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
            f"supprimée(s), carnet supprimé",
        )
        return None

    def _note_deja_presente(self, carnet_des_etalons, nom_du_fichier):
        """
        Dit si une note issue de ce fichier est deja dans le carnet.
        / Says whether a note from this file is already in the notebook.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        On regarde AVANT de convertir. Le service porte bien un garde-fou
        — `creer_les_elements_d_une_page` leve si la page a deja des
        elements — mais il arrive APRES la conversion Docling. S'y fier
        ferait payer 98 s pour un PDF de 3 pages, et rien produire.
        / The service's guard comes after conversion; this one comes before.

        UNE NOTE SANS ELEMENT N'EST PAS UNE NOTE PRESENTE.

        Si l'ingestion echoue, la Page reste en base sans le moindre
        element : elle n'a ni gouttiere, ni ancrage possible, elle ne sert
        a rien. Tester la seule existence de la Page faisait sauter cette
        coquille a chaque relance, et l'etat a moitie ingere ne se reparait
        jamais sans --reset. On la supprime donc pour la recharger — la
        supprimer est obligatoire, sinon la contrainte globale
        `unique_url_si_presente` refuse la capture web, et les trois
        autres notes se dedoublent.
        / A note with no element is a shell: delete it so it can reload.
        Deleting first is mandatory — the global url constraint would
        otherwise reject the web capture, and the others would duplicate.
        """
        from hypostasis_extractor.models import AncrageExtraction

        if carnet_des_etalons is None:
            return False

        note_existante = Page.objects.filter(
            appartenances_dossiers__dossier=carnet_des_etalons,
            original_filename=nom_du_fichier,
        ).first()
        if note_existante is None:
            return False

        if note_existante.elements.exists():
            return True

        # A blanc, on constate sans supprimer : la note EST rechargeable,
        # c'est ce que le bilan doit annoncer.
        # / Dry run states the fact without deleting anything.
        if self.a_blanc:
            return False

        # Une ancre est une preuve. Elle est censee etre impossible sans
        # element (AncrageExtraction.element pointe un ElementDocument),
        # mais on verifie plutot que de supposer : une suppression qui
        # emporte une preuve ne se rattrape pas.
        # / An anchor is evidence: verify rather than assume.
        nombre_d_ancres = AncrageExtraction.objects.filter(
            element__page=note_existante,
        ).count()
        if nombre_d_ancres:
            self.stdout.write(self.style.WARNING(
                f"    « {note_existante.title} » est sans élément mais "
                f"porte {nombre_d_ancres} ancre(s) — non supprimée, non "
                f"rechargée.",
            ))
            return True

        # Rangee AUSSI ailleurs, elle appartient a ce quelqu'un d'autre.
        # Meme regle que --reset : on ne l'emporte pas.
        # / Also filed elsewhere: not ours to delete, same rule as --reset.
        rangee_ailleurs = note_existante.appartenances_dossiers.exclude(
            dossier=carnet_des_etalons,
        ).exists()
        if rangee_ailleurs:
            self.stdout.write(self.style.WARNING(
                f"    « {note_existante.title} » est sans élément mais "
                f"rangée aussi dans un autre carnet — non supprimée, non "
                f"rechargée.",
            ))
            return True

        note_existante.delete()
        return False

    def _charger_les_documents(self, proprietaire, carnet_des_etalons):
        """
        Charge les documents etalons, un par forme d'entree.
        / Loads the reference documents, one per input form.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py
        """
        self._charger_la_capture_web(proprietaire, carnet_des_etalons)
        self._charger_le_markdown(proprietaire, carnet_des_etalons)
        self._charger_la_transcription_json(proprietaire, carnet_des_etalons)
        self._charger_le_mp3(proprietaire, carnet_des_etalons)
        # Les deux PDF ferment la marche : ce sont les plus couteux des
        # six documents, les quatre autres doivent etre en base avant
        # eux. Le second (open badges, ~3 365 Mio) est encore plus lourd
        # que le premier (etude, ~2 031 Mio) — il vient donc en tout
        # dernier. / Both PDF close the march: the costliest of the six
        # documents. The second (open badges) is heavier than the first
        # (etude) — it therefore loads last of all.
        self._charger_le_pdf(proprietaire, carnet_des_etalons)
        self._charger_le_pdf_des_open_badges(proprietaire, carnet_des_etalons)

        self.stdout.write(
            f"Notes sautées       : {self.nombre_de_notes_sautees} "
            f"(déjà présentes)",
        )

    def _detail_par_label(self, page_ingeree):
        """
        Rend le decompte par label des elements d'une page, en une ligne.
        / Returns the per-label element breakdown of a page, on one line.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        CE DETAIL EST LE TEMOIN DE NON-REGRESSION (§ 5 de la spec).

        La capture web doit rendre `section_header 4 · list_item 5 ·
        text 19`. Un total seul ne dirait rien : 54 elements dont un
        `picture` signalerait un retour d'avant les correctifs du 11 aout
        (legende d'image, recollage des groupes `inline`), et une
        cinquantaine de blocs TOUS en `text` signalerait le retour du
        decoupage maison par paragraphes. Les deux passeraient inapercus
        derriere un simple compte.
        / A bare total would hide both known regressions; the per-label
        breakdown is what catches them.

        Le detail n'est imprime QUE pour la capture web : les autres
        fixtures ne portent pas ce controle.
        / Printed for the web capture only.
        """
        nombre_par_label = {}
        for element in page_ingeree.elements.order_by("ordre"):
            nombre_par_label[element.label] = (
                nombre_par_label.get(element.label, 0) + 1
            )

        if not nombre_par_label:
            return ""

        morceaux_du_detail = []
        for label, nombre in nombre_par_label.items():
            morceaux_du_detail.append(f"{label} {nombre}")
        return " — " + " · ".join(morceaux_du_detail)

    def _charger_la_capture_web(self, proprietaire, carnet_des_etalons):
        """
        Cree la note issue de la capture web, et l'ingere.
        / Creates the note from the web capture, and ingests it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        C'est la SEULE fixture qui eprouve les labels de structure d'un
        HTML reel : section_header, list_item, text. Les pages « Wikipedia »
        de charger_fixtures_demo n'ont que des <p> et sortent toutes en
        `text`. / The only fixture exercising real HTML structure labels.

        C'EST AUSSI LA SEULE DES QUATRE A VERIFIER UNE CONTRAINTE GLOBALE
        AVANT DE CREER.

        Elle est la seule des quatre fixtures a porter une `url` : le
        markdown, la transcription JSON et le mp3 la creent a `None`. Or
        `unique_url_si_presente` (core/models.py:321-325) est une
        contrainte GLOBALE sur `url`, non scopee par carnet ni par
        proprietaire — sa condition `url__isnull=False` exempte les trois
        autres, qui n'ont donc pas besoin de ce garde. Ne pas « harmoniser »
        les quatre methodes par symetrie : les trois autres n'ont rien a
        verifier.
        / Only this one carries a `url`; the other three create it as
        None and are exempted by the constraint's `url__isnull=False`
        condition. Do not "harmonize" the four loaders by apparent
        symmetry — the other three have nothing to check.

        Ce garde s'applique a CHAQUE execution, pas seulement apres un
        --reset : c'est une consequence de la contrainte globale, pas une
        specificite du reset. --reset est simplement le chemin qui le
        rend visible en pratique (une page « rangee ailleurs » survit au
        reset, puis le carnet recree tente de la re-creer).
        / This guard runs on every execution, not only after --reset —
        --reset is merely the path that makes the collision reachable.
        """
        # Garde : --fichier peut avoir exclu ce document.
        # / Guard: --fichier may have excluded this document.
        if FICHIER_DE_LA_CAPTURE not in self.fichiers_demandes:
            return None

        if self._note_deja_presente(carnet_des_etalons, FICHIER_DE_LA_CAPTURE):
            self.stdout.write("Capture web         : déjà présente — sautée")
            self.nombre_de_notes_sautees += 1
            return None

        if self.a_blanc:
            self.stdout.write("Capture web         : serait chargée")
            return None

        # `url` est unique en base (contrainte unique_url_si_presente,
        # non scopee par carnet). --reset peut avoir garde cette page
        # ailleurs (rangee aussi dans un autre carnet, donc pas a nous
        # de la supprimer) : on la range ici plutot que d'en tenter un
        # doublon que la contrainte refuserait. / `url` is globally
        # unique. --reset may have kept this page elsewhere (also filed
        # in another notebook, so not ours to delete): file it here
        # instead of attempting a duplicate the DB constraint rejects.
        #
        # SCOPE SUR proprietaire : sans ce filtre, la commande peut
        # trouver la page d'un AUTRE utilisateur et la ranger dans notre
        # carnet « Documents etalons » — une fuite de perimetre. On ne
        # touche jamais a une note qui n'est pas a `proprietaire`.
        # / Scoped to `proprietaire`: without it, a page belonging to a
        # DIFFERENT user could get filed into our notebook — a scope
        # leak. We never touch a note that is not the owner's.
        page_deja_ailleurs = Page.objects.filter(
            url=URL_DE_LA_CAPTURE, owner=proprietaire,
        ).first()
        if page_deja_ailleurs is not None:
            ranger_une_note_dans_un_carnet(
                page_deja_ailleurs, carnet_des_etalons, proprietaire,
            )
            self.stdout.write(
                "Capture web         : déjà présente ailleurs — rangée ici",
            )
            return page_deja_ailleurs

        # La page peut exister chez QUELQU'UN D'AUTRE : la contrainte
        # d'unicite empecherait quand meme la creation. On le dit
        # clairement et on passe, plutot que de laisser l'IntegrityError
        # remonter en trace de pile. / The page may belong to someone
        # else: the unique constraint would still block creation. Say so
        # plainly and move on, instead of surfacing a raw IntegrityError.
        if Page.objects.filter(url=URL_DE_LA_CAPTURE).exclude(
            owner=proprietaire,
        ).exists():
            self.stdout.write(self.style.WARNING(
                "Capture web         : une autre note porte déjà cette "
                "url — capture web non chargée",
            ))
            return None

        html_capture = (REPERTOIRE_SAMPLE / FICHIER_DE_LA_CAPTURE).read_text(
            encoding="utf-8",
        )

        page_de_la_capture = Page.objects.create(
            source_type="web",
            original_filename=FICHIER_DE_LA_CAPTURE,
            url=URL_DE_LA_CAPTURE,
            title="Badgeons la Normandie",
            html_original=html_capture,
            html_readability=html_capture,
            text_readability="",
            content_hash=hashlib.sha256(
                html_capture.encode("utf-8"),
            ).hexdigest(),
            status="completed",
            owner=proprietaire,
            dossier=carnet_des_etalons,
        )
        ranger_une_note_dans_un_carnet(
            page_de_la_capture, carnet_des_etalons, proprietaire,
        )

        nombre_d_elements = self._ingerer_la_capture(page_de_la_capture)
        self.stdout.write(
            f"Capture web         : {nombre_d_elements} élément(s)"
            f"{self._detail_par_label(page_de_la_capture)}",
        )
        return page_de_la_capture

    def _ingerer_la_capture(self, page_de_la_capture):
        """
        Lance l'ingestion de la capture, en synchrone.
        / Runs the capture's ingestion, synchronously.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        ON PASSE PAR LA TACHE, PAS PAR LE SERVICE.

        Le service nu cree les elements et s'arrete la. C'est la tache qui
        ecrit `Page.ingestion_etat` (en_cours -> reussie/echouee) et qui
        attrape l'echec avec un message lisible. L'ecran de lecture affiche
        cet etat : une page ingeree par le service nu ment sur son statut.
        `.apply()` l'execute ici meme, sans worker.
        / The task writes ingestion_etat; the bare service does not.
        """
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        resultat = ingerer_une_capture_web_avec_docling.apply(
            args=[page_de_la_capture.pk],
        )
        return self._elements_du_resultat(resultat)

    def _elements_du_resultat(self, resultat_de_la_tache):
        """
        Lit le nombre d'elements d'un resultat de tache, sans mentir.
        / Reads a task result's element count, without lying.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        Les taches rendent {"elements": N} ou {"erreur": "..."} — jamais
        une exception pour un cas normal. Un mock de test rend un Mock :
        on ne compte alors rien plutot que d'inventer un chiffre.
        / Never invent a count: a mocked task has none to give.
        """
        valeur = getattr(resultat_de_la_tache, "result", None)
        if not isinstance(valeur, dict):
            return "?"
        if "erreur" in valeur:
            self.stdout.write(self.style.WARNING(
                f"    ingestion en échec : {valeur['erreur']}",
            ))
            return 0
        return valeur.get("elements", 0)

    def _charger_le_markdown(self, proprietaire, carnet_des_etalons):
        """
        Cree la note issue du markdown, et l'ingere.
        / Creates the note from the markdown file, and ingests it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        Le markdown passe bien par Docling, mais sans OCR ni modele de
        layout : ceux-la ne se chargent que pour les PDF et les images.
        C'est pourquoi cette fixture-ci est sure, la ou le PDF ne l'est pas.
        / Markdown goes through Docling without OCR or layout models.
        """
        # Garde : --fichier peut avoir exclu ce document.
        # / Guard: --fichier may have excluded this document.
        if FICHIER_DU_MARKDOWN not in self.fichiers_demandes:
            return None

        if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MARKDOWN):
            self.stdout.write("Markdown            : déjà présent — sauté")
            self.nombre_de_notes_sautees += 1
            return None

        if self.a_blanc:
            self.stdout.write("Markdown            : serait chargé")
            return None

        chemin_du_markdown = REPERTOIRE_SAMPLE / FICHIER_DU_MARKDOWN
        contenu_du_markdown = chemin_du_markdown.read_text(encoding="utf-8")

        page_du_markdown = Page.objects.create(
            source_type="file",
            original_filename=FICHIER_DU_MARKDOWN,
            url=None,
            title="Présentation Hypostasia V3",
            html_original="",
            html_readability="",
            text_readability=contenu_du_markdown,
            content_hash=hashlib.sha256(
                contenu_du_markdown.encode("utf-8"),
            ).hexdigest(),
            status="completed",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(
                contenu_du_markdown.encode("utf-8"),
                name=FICHIER_DU_MARKDOWN,
            ),
        )
        ranger_une_note_dans_un_carnet(
            page_du_markdown, carnet_des_etalons, proprietaire,
        )

        from hypostasis_extractor.tasks_element import (
            ingerer_un_fichier_avec_docling,
        )

        # On ne passe QUE la cle primaire : la tache resout le chemin
        # depuis page.source_file, comme le fait la vue d'import.
        # / Only the pk: the task resolves the path from source_file.
        resultat = ingerer_un_fichier_avec_docling.apply(
            args=[page_du_markdown.pk],
        )
        self.stdout.write(
            f"Markdown            : {self._elements_du_resultat(resultat)} élément(s)",
        )
        return page_du_markdown

    def _charger_la_transcription_json(self, proprietaire, carnet_des_etalons):
        """
        Cree la note issue de la transcription deja faite, et l'ingere.
        / Creates the note from the ready-made transcript, and ingests it.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        DOCLING N'INTERVIENT PAS : une transcription diarisee est deja
        structuree. `ingerer_une_transcription_diarisee` la decoupe en
        tours de parole sans charger le moindre modele.
        / Docling plays no part: a diarised transcript is already structured.

        ATTENTION — la vue d'import, elle, N'APPELLE PAS cette ingestion
        (front/views.py:5326) : une note importee par cette porte reste
        sans element, donc sans gouttiere et sans ancrage possible. C'est
        un trou de l'application, releve le 11 aout 2026. La commande
        appelle l'ingestion explicitement.
        / The import view never triggers this ingestion; we do it here.
        """
        import json

        # Garde : --fichier peut avoir exclu ce document.
        # / Guard: --fichier may have excluded this document.
        if FICHIER_DE_LA_TRANSCRIPTION not in self.fichiers_demandes:
            return None

        if self._note_deja_presente(
            carnet_des_etalons, FICHIER_DE_LA_TRANSCRIPTION,
        ):
            self.stdout.write("Transcription JSON  : déjà présente — sautée")
            self.nombre_de_notes_sautees += 1
            return None

        if self.a_blanc:
            self.stdout.write("Transcription JSON  : serait chargée")
            return None

        from front.services.transcription_audio import construire_html_diarise

        chemin_du_json = REPERTOIRE_SAMPLE / FICHIER_DE_LA_TRANSCRIPTION
        contenu_brut = chemin_du_json.read_text(encoding="utf-8")
        donnees_de_la_transcription = json.loads(contenu_brut)

        html_diarise, texte_brut = construire_html_diarise(
            donnees_de_la_transcription,
        )

        page_du_json = Page.objects.create(
            source_type="audio",
            original_filename=FICHIER_DE_LA_TRANSCRIPTION,
            url=None,
            title="Débat IA — transcription",
            html_original="",
            html_readability=html_diarise,
            text_readability=texte_brut,
            content_hash=hashlib.sha256(
                texte_brut.encode("utf-8"),
            ).hexdigest(),
            transcription_raw=donnees_de_la_transcription,
            status="completed",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(
                contenu_brut.encode("utf-8"),
                name=FICHIER_DE_LA_TRANSCRIPTION,
            ),
        )
        ranger_une_note_dans_un_carnet(
            page_du_json, carnet_des_etalons, proprietaire,
        )

        from hypostasis_extractor.tasks_element import (
            ingerer_une_transcription_diarisee_en_elements,
        )

        resultat = ingerer_une_transcription_diarisee_en_elements.apply(
            args=[page_du_json.pk],
        )
        self.stdout.write(
            f"Transcription JSON  : {self._elements_du_resultat(resultat)} "
            f"tour(s) de parole",
        )
        return page_du_json

    def _config_voxtral_utilisable(self):
        """
        Rend la configuration Voxtral a passer au job, ou None.
        / Returns the Voxtral configuration for the job, or None.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        POURQUOI PAS `filter(is_active=True).first()`.

        Ce `.first()` prenait N'IMPORTE QUELLE config active.
        `TranscriptionConfig` n'a aucun `Meta.ordering` : l'ordre est
        arbitraire cote SGBD. Et son `provider` vaut MOCK par defaut
        (core/models.py:993) — toute config creee depuis l'admin sans
        choisir de modele est une config mock. Qu'une seule traine en base
        et front/tasks.py:634 retombe sur `transcrire_audio_mock`, pendant
        que le bilan annonce « Audio mp3 (Voxtral) : N tour(s) de parole ».
        C'est le faux verbatim que le § 3.2 de la spec existe pour
        interdire. / That `.first()` could pick a MOCK config: the task
        would silently mock while the report still claimed Voxtral.

        On prend donc la config que `_creer_la_config_de_transcription` a
        rendue — la seule dont on sait qu'elle est bien Voxtral. Le repli
        n'accepte qu'un `provider` voxtral, jamais autre chose : mieux
        vaut sauter le mp3 en le disant que produire un faux verbatim.
        / Fall back only to a genuinely voxtral provider — skipping loudly
        beats faking a transcript.
        """
        if (
            self.config_de_transcription is not None
            and self.config_de_transcription.provider
            == TranscriptionProvider.VOXTRAL
        ):
            return self.config_de_transcription

        return TranscriptionConfig.objects.filter(
            is_active=True, provider=TranscriptionProvider.VOXTRAL,
        ).order_by("pk").first()

    def _copier_l_audio_en_temporaire(self, octets_de_l_audio):
        """
        Copie l'audio dans AUDIO_TEMP_DIR et rend le chemin de la copie.
        / Copies the audio into AUDIO_TEMP_DIR and returns the copy's path.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        LA TACHE DETRUIT LE FICHIER QU'ON LUI PASSE.

        `transcrire_audio_task` fait `os.unlink(chemin_fichier_audio)` dans
        un `finally` (front/tasks.py:742-747) : succes ou echec, le fichier
        recu disparait. Son contrat est de recevoir un fichier TEMPORAIRE
        — la vue d'import lui passe une copie dans `AUDIO_TEMP_DIR`
        (front/views.py:5422-5428), jamais le media de la page. Lui passer
        `page.source_file.path` laissait la note avec un `source_file` qui
        ne pointait plus sur rien.
        / The task unlinks whatever path it receives; give it a copy, never
        the page's own media.
        """
        nom_temporaire = f"{uuid.uuid4().hex}.mp3"
        chemin_temporaire = str(settings.AUDIO_TEMP_DIR / nom_temporaire)
        with open(chemin_temporaire, "wb") as destination:
            destination.write(octets_de_l_audio)
        return chemin_temporaire

    def _charger_le_mp3(self, proprietaire, carnet_des_etalons):
        """
        Cree la note audio et lance la vraie transcription Voxtral.
        / Creates the audio note and runs the real Voxtral transcription.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        C'est la seule fixture qui eprouve la chaine COMPLETE : mp3 ->
        Voxtral -> tours de parole -> elements. Un appel reseau reel, donc
        aussi un test de bout en bout a chaque chargement.
        / The only fixture exercising the full chain, network call included.

        La tache enchaine elle-meme l'ingestion en elements, mais par
        `.delay()` : sans worker, elle partirait dans le broker et ne se
        ferait jamais. On la rejoue donc ici, en synchrone, si la page
        n'a pas d'element. / The task chains via .delay(); we redo it sync.
        """
        # Garde : --fichier peut avoir exclu ce document.
        # / Guard: --fichier may have excluded this document.
        if FICHIER_DU_MP3 not in self.fichiers_demandes:
            return None

        if self.sans_mp3:
            self.stdout.write("Audio mp3           : sauté (--sans-mp3)")
            return None

        if not os.environ.get("MISTRAL_API_KEY"):
            self.stdout.write(self.style.WARNING(
                "Audio mp3           : sauté — pas de MISTRAL_API_KEY. "
                "La transcription serait mockée, pas réelle.",
            ))
            return None

        if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MP3):
            self.stdout.write("Audio mp3           : déjà présent — sauté")
            self.nombre_de_notes_sautees += 1
            return None

        # LA GARDE A BLANC EST ICI, AVANT TOUT LE RESTE : le mp3 est le
        # seul document dont le traitement appelle un service facture.
        # / The dry-run guard comes first: this is the only paid path.
        if self.a_blanc:
            self.stdout.write("Audio mp3           : serait transcrit (Voxtral)")
            return None

        from core.models import (
            PageStatus,
            TranscriptionJob,
            TranscriptionJobStatus,
        )

        config_voxtral = self._config_voxtral_utilisable()
        if config_voxtral is None:
            self.stdout.write(self.style.WARNING(
                "Audio mp3           : sauté — aucune configuration "
                "Voxtral active. La transcription serait mockée en "
                "silence, et le bilan annoncerait quand même des tours "
                "de parole Voxtral.",
            ))
            return None

        chemin_du_mp3 = REPERTOIRE_SAMPLE / FICHIER_DU_MP3
        octets_du_mp3 = chemin_du_mp3.read_bytes()

        page_du_mp3 = Page.objects.create(
            source_type="audio",
            original_filename=FICHIER_DU_MP3,
            url=None,
            title="Palais César — deux locuteurs",
            html_original="",
            html_readability="",
            text_readability="",
            content_hash="",
            status="processing",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(octets_du_mp3, name=FICHIER_DU_MP3),
        )
        ranger_une_note_dans_un_carnet(
            page_du_mp3, carnet_des_etalons, proprietaire,
        )

        job_de_transcription = TranscriptionJob.objects.create(
            page=page_du_mp3,
            transcription_config=config_voxtral,
            audio_filename=FICHIER_DU_MP3,
            status="pending",
        )

        from front.tasks import transcrire_audio_task

        chemin_temporaire_de_l_audio = self._copier_l_audio_en_temporaire(
            octets_du_mp3,
        )
        transcrire_audio_task.apply(args=[
            job_de_transcription.pk,
            chemin_temporaire_de_l_audio,
            config_voxtral.max_speakers,
            config_voxtral.language,
        ])

        page_du_mp3.refresh_from_db()
        job_de_transcription.refresh_from_db()

        # `transcrire_audio_task` attrape ses propres exceptions et pose
        # page.status/job.status = ERROR en silence (front/tasks.py
        # ~711-726), sans jamais relever d'exception ici. Sans ce
        # controle, le bilan afficherait "0 tour(s) de parole" —
        # indiscernable d'une transcription reussie qui n'aurait rien
        # trouve a dire. / The task silently marks page/job as ERROR on
        # failure; without this check the report would lie by omission.
        transcription_en_echec = (
            page_du_mp3.status == PageStatus.ERROR
            or job_de_transcription.status == TranscriptionJobStatus.ERROR
        )
        if transcription_en_echec:
            message_d_erreur = (
                job_de_transcription.error_message
                or page_du_mp3.error_message
                or "raison inconnue"
            )
            self.stdout.write(self.style.WARNING(
                f"Audio mp3 (Voxtral) : ÉCHEC de la transcription — "
                f"{message_d_erreur}",
            ))
            return page_du_mp3

        # La tache enchaine l'ingestion par `.delay()`. Sans worker, elle
        # n'a pas eu lieu : on la rejoue ici, en synchrone.
        # / The task chained via .delay(); without a worker, redo it here.
        if not page_du_mp3.elements.exists() and page_du_mp3.transcription_raw:
            from hypostasis_extractor.tasks_element import (
                ingerer_une_transcription_diarisee_en_elements,
            )

            ingerer_une_transcription_diarisee_en_elements.apply(
                args=[page_du_mp3.pk],
            )

        self.stdout.write(
            f"Audio mp3 (Voxtral) : {page_du_mp3.elements.count()} "
            f"tour(s) de parole",
        )
        return page_du_mp3

    def _charger_le_pdf(self, proprietaire, carnet_des_etalons):
        """
        Cree la note issue du PDF, et lance sa conversion Docling complete.
        / Creates the note from the PDF, and runs its full Docling conversion.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        LE SEUL DOCUMENT AVEC OCR ET MODELE DE LAYOUT.

        A la difference du markdown, un PDF charge Docling au complet —
        OCR et detection de mise en page. Mesure du 11 aout 2026 (voir
        tmp/benchmark-docling-2026-08-11.md) : ~98 s et ~2 031 Mio pour
        ces trois pages. C'est pourquoi il est charge en dernier
        (DOCUMENTS_ETALONS) et pourquoi son bilan annonce le cout AVANT
        de commencer — sans cette ligne, la commande bloquerait une
        minute et demie sans rien dire. / The only document loading OCR
        and a layout model; the report line warns of the cost before
        starting, since the command would otherwise block silently.

        UN PDF EST BINAIRE.

        `read_bytes()`, jamais `read_text()` : un decodage UTF-8
        planterait sur le premier octet non textuel. Et
        `text_readability` reste vide — ce sont les ElementDocument, pas
        la Page, qui porteront le texte une fois l'ingestion faite.
        / A PDF is binary: read_bytes(), never read_text().
        text_readability stays empty; the elements carry the text.
        """
        # Garde : --fichier peut avoir exclu ce document.
        # / Guard: --fichier may have excluded this document.
        if FICHIER_DU_PDF_ETUDE not in self.fichiers_demandes:
            return None

        if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_PDF_ETUDE):
            self.stdout.write("PDF étude           : déjà présent — sauté")
            self.nombre_de_notes_sautees += 1
            return None

        if self.a_blanc:
            self.stdout.write("PDF étude           : serait chargé")
            return None

        # Annoncee AVANT de lancer Docling : sans elle, la commande
        # bloquerait ~98 s sans rien dire. / Announced before Docling
        # runs: otherwise the command blocks silently for ~98s.
        self.stdout.write(
            "PDF étude           : conversion Docling en cours "
            "(~98 s, ~2 Gio)…",
        )

        chemin_du_pdf = REPERTOIRE_SAMPLE / FICHIER_DU_PDF_ETUDE
        octets_du_pdf = chemin_du_pdf.read_bytes()

        page_du_pdf = Page.objects.create(
            source_type="file",
            original_filename=FICHIER_DU_PDF_ETUDE,
            url=None,
            title="Étude épistémologique de l'IA",
            html_original="",
            html_readability="",
            text_readability="",
            content_hash=hashlib.sha256(octets_du_pdf).hexdigest(),
            status="completed",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(octets_du_pdf, name=FICHIER_DU_PDF_ETUDE),
        )
        ranger_une_note_dans_un_carnet(
            page_du_pdf, carnet_des_etalons, proprietaire,
        )

        from hypostasis_extractor.tasks_element import (
            ingerer_un_fichier_avec_docling,
        )

        # On ne passe QUE la cle primaire : la tache resout le chemin
        # depuis page.source_file, comme le fait la vue d'import.
        # / Only the pk: the task resolves the path from source_file.
        resultat = ingerer_un_fichier_avec_docling.apply(
            args=[page_du_pdf.pk],
        )
        self.stdout.write(
            f"PDF étude           : {self._elements_du_resultat(resultat)} élément(s)",
        )
        return page_du_pdf

    def _charger_le_pdf_des_open_badges(self, proprietaire, carnet_des_etalons):
        """
        Cree la note issue du second PDF, et lance sa conversion Docling.
        / Creates the note from the second PDF, and runs its conversion.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        LE PLUS COUTEUX DES SIX DOCUMENTS.

        Meme patron que `_charger_le_pdf` (OCR + modele de layout charges
        au complet), mais plus lourd : mesure du 11 aout 2026 (voir
        tmp/benchmark-docling-2026-08-11.md § 2) : ~81 s et ~3 365 Mio au
        pic pour 4 pages et 61 elements — contre ~98 s et ~2 031 Mio pour
        l'etude. C'est pourquoi il charge en tout dernier
        (DOCUMENTS_ETALONS), apres le premier PDF. / Same pattern as
        `_charger_le_pdf`, but heavier: it is why it loads last of all.

        LE NOM DE FICHIER PORTE UN ESPACE ET UN ACCENT.

        « présentation des open badges.pdf » n'est pas renomme : un nom
        avec espace et accent est un cas d'usage legitime, qu'un
        utilisateur produira. `read_bytes()` + `ContentFile(..., name=...)`
        le portent tel quel jusque dans media/, et la tache resout le
        chemin depuis `page.source_file`, comme pour l'etude. / The
        filename is not renamed: a space-and-accent name is legitimate
        and travels unscathed through read_bytes(), ContentFile, and the
        task's path resolution.
        """
        # Garde : --fichier peut avoir exclu ce document.
        # / Guard: --fichier may have excluded this document.
        if FICHIER_DU_PDF_OPEN_BADGES not in self.fichiers_demandes:
            return None

        if self._note_deja_presente(
            carnet_des_etalons, FICHIER_DU_PDF_OPEN_BADGES,
        ):
            self.stdout.write(
                "PDF open badges     : déjà présent — sauté",
            )
            self.nombre_de_notes_sautees += 1
            return None

        if self.a_blanc:
            self.stdout.write("PDF open badges     : serait chargé")
            return None

        # Annoncee AVANT de lancer Docling : sans elle, la commande
        # bloquerait ~81 s sans rien dire. / Announced before Docling
        # runs: otherwise the command blocks silently for ~81s.
        self.stdout.write(
            "PDF open badges     : conversion Docling en cours "
            "(~81 s, ~3,4 Gio)…",
        )

        chemin_du_pdf = REPERTOIRE_SAMPLE / FICHIER_DU_PDF_OPEN_BADGES
        octets_du_pdf = chemin_du_pdf.read_bytes()

        page_du_pdf = Page.objects.create(
            source_type="file",
            original_filename=FICHIER_DU_PDF_OPEN_BADGES,
            url=None,
            title="Présentation des Open Badges",
            html_original="",
            html_readability="",
            text_readability="",
            content_hash=hashlib.sha256(octets_du_pdf).hexdigest(),
            status="completed",
            owner=proprietaire,
            dossier=carnet_des_etalons,
            source_file=ContentFile(
                octets_du_pdf, name=FICHIER_DU_PDF_OPEN_BADGES,
            ),
        )
        ranger_une_note_dans_un_carnet(
            page_du_pdf, carnet_des_etalons, proprietaire,
        )

        from hypostasis_extractor.tasks_element import (
            ingerer_un_fichier_avec_docling,
        )

        # On ne passe QUE la cle primaire : la tache resout le chemin
        # depuis page.source_file, comme le fait la vue d'import.
        # / Only the pk: the task resolves the path from source_file.
        resultat = ingerer_un_fichier_avec_docling.apply(
            args=[page_du_pdf.pk],
        )
        self.stdout.write(
            f"PDF open badges     : "
            f"{self._elements_du_resultat(resultat)} élément(s)",
        )
        return page_du_pdf

    def _creer_la_base_de_demonstration(self, proprietaire, carnet_des_etalons):
        """
        Range le carnet des étalons dans une base de connaissances.
        / Files the reference notebook into a knowledge base.

        LOCALISATION : front/management/commands/charger_fixtures_sample.py

        Une base de connaissances est le niveau au-dessus du carnet : elle
        rassemble des carnets pour une communauté. Sans elle, l'écran des
        bases reste vide et rien ne s'y travaille.
        / A knowledge base groups notebooks; without one, its screen is empty.

        LE SLUG EST POSE EXPLICITEMENT.

        `BaseDeConnaissances.slug` est un `SlugField` unique. Le laisser
        se generer depuis `nom` romprait sur l'accent de « Démonstration »,
        et deux executions ne doivent jamais se heurter dessus — d'ou
        `get_or_create` sur `nom`, avec `slug` fixe dans les `defaults`.
        / The slug is set explicitly rather than auto-derived: two runs
        must never collide on it.
        """
        if self.a_blanc:
            base_existante = BaseDeConnaissances.objects.filter(
                nom=NOM_DE_LA_BASE_DE_DEMONSTRATION,
            ).first()
            if base_existante is not None:
                self.stdout.write(
                    f"Base                : {NOM_DE_LA_BASE_DE_DEMONSTRATION} "
                    f"— pk={base_existante.pk} (réutilisée)",
                )
            else:
                self.stdout.write(
                    f"Base                : {NOM_DE_LA_BASE_DE_DEMONSTRATION} "
                    f"(serait créée)",
                )
            return None

        base, base_a_ete_creee = BaseDeConnaissances.objects.get_or_create(
            nom=NOM_DE_LA_BASE_DE_DEMONSTRATION,
            defaults={
                "slug": SLUG_DE_LA_BASE_DE_DEMONSTRATION,
                "owner": proprietaire,
                "visibilite": VisibiliteDossier.PUBLIC,
                "description": DESCRIPTION_DE_LA_BASE_DE_DEMONSTRATION,
            },
        )

        # Meme regle que pour le carnet : on remplit le vide d'une base
        # deja presente, on n'ecrase jamais un texte ecrit a la main.
        # / Same rule as the notebook: fill blanks, never overwrite.
        description_a_ete_completee = False
        if not base.description.strip():
            base.description = DESCRIPTION_DE_LA_BASE_DE_DEMONSTRATION
            base.save(update_fields=["description"])
            description_a_ete_completee = True

        etat_de_la_base = "créée" if base_a_ete_creee else "réutilisée"
        if description_a_ete_completee and not base_a_ete_creee:
            etat_de_la_base += ", description complétée"
        self.stdout.write(
            f"Base                : {NOM_DE_LA_BASE_DE_DEMONSTRATION} — "
            f"pk={base.pk} ({etat_de_la_base})",
        )

        AppartenanceDossierBase.objects.get_or_create(
            dossier=carnet_des_etalons, base=base,
            defaults={"integre_par": proprietaire},
        )
        return base
