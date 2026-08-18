"""
Affecte un modele IA a un usage — rediger un article, ou juger une
citation. / Binds an AI model to a use.

LOCALISATION : front/management/commands/affecter_un_modele_a_un_role.py

POURQUOI UNE COMMANDE ET PAS UN ECRAN. L'admin Django est desactive
deliberement (`core/admin.py`), et l'ecran de configuration IA ne sait
poser qu'UN modele, celui de la `Configuration`. Cette commande est donc
le seul levier existant. L'ecran viendra quand le juge sera choisi — il
n'y a rien a dessiner tant qu'on ne sait pas encore quoi y montrer.

CE QU'ELLE CREE, ET POURQUOI EN `is_active=False`. Un modele servi par
une plateforme compatible OpenAI n'est PAS utilisable pour l'extraction :
LangExtract ne sait piloter que Google, OpenAI et Ollama, et
`resolve_model_params` leve pour tout le reste. Or l'ecran de
configuration IA propose au clic TOUT modele actif et le pose dans
`Configuration.ai_model`, qui EST le modele d'extraction. Un modele de
role laisse actif finirait donc, un jour, par eteindre l'extraction d'un
seul clic. `is_active=False` veut dire « pas proposable au choix » — et
`modele_du_role` ne filtre volontairement pas dessus.

LA CLE RESTE DANS L'ENVIRONNEMENT. La ligne creee ne porte QUE le nom de
la variable a lire.

Exemples :

    manage.py affecter_un_modele_a_un_role --lister

    manage.py affecter_un_modele_a_un_role \\
        --role juge_de_verification --modele 1

    manage.py affecter_un_modele_a_un_role \\
        --role juge_de_verification \\
        --plateforme https://openrouter.ai/api/v1 \\
        --modele-technique mistralai/mistral-small-3.2-24b-instruct \\
        --variable-de-cle OPENROUTER_API_KEY

    manage.py affecter_un_modele_a_un_role \\
        --role juge_de_verification --retirer
"""

import os

from django.core.management.base import BaseCommand, CommandError

from core.models import (
    AIModel, AIModelChoices, ModeleParRole, Provider, RoleDeModele,
    un_modele_refuse_toute_temperature,
)
from core.services.modeles_par_role import modele_du_role


class Command(BaseCommand):
    help = (
        "Affecte un modèle IA à un rôle (rédacteur d'article, juge de "
        "vérification). Sans affectation, un rôle retombe sur le modèle "
        "de la Configuration."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--lister", action="store_true",
            help="Affiche les affectations en cours et s'arrête.",
        )
        parser.add_argument(
            "--role", choices=RoleDeModele.values,
            help="L'usage à servir.",
        )
        parser.add_argument(
            "--modele", type=int,
            help="Identifiant d'un AIModel existant à affecter.",
        )
        parser.add_argument(
            "--choix",
            help=(
                "Valeur du référentiel AIModelChoices (ex: "
                "gemini-2.5-flash-lite). Crée la ligne si besoin ; le "
                "provider et le tarif en découlent."
            ),
        )
        parser.add_argument(
            "--plateforme",
            help=(
                "URL de base d'une API compatible OpenAI (ex: "
                "https://openrouter.ai/api/v1). Crée le modèle si besoin."
            ),
        )
        parser.add_argument(
            "--modele-technique",
            help=(
                "Identifiant du modèle chez la plateforme (ex: "
                "mistralai/mistral-small-3.2-24b-instruct)."
            ),
        )
        parser.add_argument(
            "--variable-de-cle",
            help=(
                "Nom de la variable d'environnement portant la clé "
                "(ex: OPENROUTER_API_KEY). La clé n'est jamais en base."
            ),
        )
        parser.add_argument(
            "--nom", default="",
            help="Nom d'affichage du modèle (défaut : son identifiant).",
        )
        parser.add_argument(
            "--temperature", type=float,
            help=(
                "Température du modèle. Un juge se règle bas : comparer "
                "deux juges à des températures différentes compare deux "
                "réglages, pas deux modèles. Sans l'option, la "
                "température du modèle est laissée telle quelle."
            ),
        )
        parser.add_argument(
            "--temperature-du-fournisseur", action="store_true",
            help=(
                "Ne transmet AUCUNE température : le fournisseur décide. "
                "Obligatoire pour les modèles de raisonnement d'OpenAI, "
                "qui refusent toute valeur autre que la leur."
            ),
        )
        parser.add_argument(
            "--retirer", action="store_true",
            help=(
                "Retire l'affectation : le rôle retombe sur le modèle de "
                "la Configuration."
            ),
        )

    def handle(self, *args, **options):
        if options["lister"]:
            self._lister()
            return

        role = options["role"]
        if not role:
            raise CommandError(
                "Précisez --role (ou --lister). Rôles : "
                + ", ".join(RoleDeModele.values),
            )

        if options["retirer"]:
            self._retirer(role)
            return

        if options["plateforme"]:
            modele = self._creer_le_modele_de_plateforme(options)
        elif options["choix"]:
            modele = self._creer_le_modele_du_referentiel(options)
        elif options["modele"]:
            modele = AIModel.objects.filter(pk=options["modele"]).first()
            if modele is None:
                raise CommandError(
                    f"Aucun modèle IA d'identifiant {options['modele']}.",
                )
        else:
            raise CommandError(
                "Précisez --modele <id>, --choix <valeur du référentiel>, "
                "ou --plateforme avec --modele-technique et "
                "--variable-de-cle.",
            )

        if options["temperature_du_fournisseur"]:
            # Vider n'est PAS mettre a zero : « aucune » veut dire « ne
            # transmets rien ». / Clearing is not setting zero.
            modele.temperature = None
            modele.save(update_fields=["temperature"])
            self.stdout.write(
                "  Aucune température ne sera transmise : le fournisseur "
                "décide.",
            )
        elif options["temperature"] is not None:
            modele.temperature = options["temperature"]
            modele.save(update_fields=["temperature"])
            self.stdout.write(
                f"  Température posée à {modele.temperature}.",
            )

        affectation, creee = ModeleParRole.objects.update_or_create(
            role=role, defaults={"modele": modele},
        )
        verbe = "affecté" if creee else "réaffecté"
        self.stdout.write(
            f"  {affectation.get_role_display()} : {verbe} à « {modele} » "
            f"(id {modele.pk}).",
        )

    def _creer_le_modele_du_referentiel(self, options):
        """
        Cree (ou retrouve) un modele du referentiel `AIModelChoices`.

        POURQUOI CE CHEMIN EXISTE. Les lignes d'`AIModel` ne sont creees
        qu'a l'installation, UNE PAR CLE D'API trouvee dans le `.env` —
        `gemini-2.5-flash` pour Google. Basculer le juge sur
        `gemini-2.5-flash-lite`, pourtant du meme referentiel et servi
        par la meme cle, exigeait sinon d'ouvrir un shell Django. En
        production, ce geste doit etre une commande comme les autres.
        / Model rows are only created at install, one per API key;
        switching to another listed model must not need a Django shell.

        Le provider et le tarif se deduisent du choix : ce chemin ne
        demande donc ni `base_url` ni variable de cle.
        / Provider and price follow from the choice.
        """
        valeur_du_choix = options["choix"]
        libelles_du_referentiel = dict(AIModelChoices.choices)
        if valeur_du_choix not in libelles_du_referentiel:
            raise CommandError(
                f"« {valeur_du_choix} » n'est pas dans le référentiel. "
                f"Un modèle hors référentiel n'a ni tarif ni provider "
                f"déductible : passez par --plateforme, qui exige une "
                f"base_url et une variable de clé.\n"
                f"Référentiel : "
                f"{', '.join(sorted(libelles_du_referentiel))}",
            )

        valeurs_par_defaut = {
            "name": options["nom"] or libelles_du_referentiel[
                valeur_du_choix
            ],
            # Comme pour une plateforme : un modele affecte a un role
            # n'a pas a etre proposable comme modele d'EXTRACTION.
            # / A role model is not an extraction model.
            "is_active": False,
        }
        # Un modele de raisonnement nait SANS temperature, sinon le
        # defaut du champ (0,7) en fait une ligne mort-nee : ces modeles
        # rendent un 400 des qu'on leur en impose une.
        # / A reasoning model is born without one, or the field's 0.7
        # default makes it dead on arrival.
        refuse_la_temperature = un_modele_refuse_toute_temperature(
            valeur_du_choix,
        )
        if refuse_la_temperature:
            valeurs_par_defaut["temperature"] = None

        modele, creee = AIModel.objects.get_or_create(
            model_choice=valeur_du_choix, defaults=valeurs_par_defaut,
        )
        if creee:
            self.stdout.write(
                f"  Modèle créé : « {modele} » (id {modele.pk}).",
            )
            if refuse_la_temperature:
                self.stdout.write(
                    "  Aucune température ne lui sera transmise : ce "
                    "modèle de raisonnement refuse toute valeur autre "
                    "que la sienne.",
                )
        return modele

    def _creer_le_modele_de_plateforme(self, options):
        """Cree (ou retrouve) le modele servi par une API compatible."""
        identifiant_technique = options["modele_technique"]
        variable_de_cle = options["variable_de_cle"]
        if not identifiant_technique or not variable_de_cle:
            raise CommandError(
                "--plateforme exige --modele-technique et "
                "--variable-de-cle.",
            )
        if not os.environ.get(variable_de_cle):
            # On ne bloque pas — un déploiement peut poser la clé plus
            # tard — mais on le dit, sinon l'échec n'arrivera qu'au
            # premier appel, dans un worker, loin d'ici.
            # / Not blocking, but said out loud: otherwise the failure
            # surfaces much later, inside a worker.
            self.stdout.write(
                f"  ⚠ La variable {variable_de_cle} est vide ou absente "
                f"de l'environnement : l'appel échouera tant qu'elle "
                f"n'est pas renseignée.",
            )

        modele, creee = AIModel.objects.get_or_create(
            model_choice=identifiant_technique,
            provider=Provider.COMPATIBLE_OPENAI,
            base_url=options["plateforme"],
            defaults={
                "name": options["nom"] or identifiant_technique,
                "variable_de_cle_api": variable_de_cle,
                # Voir l'en-tete : un modele de role ne doit pas être
                # proposable comme modele d'extraction.
                # / A role model must not be selectable for extraction.
                "is_active": False,
            },
        )
        if creee:
            self.stdout.write(
                f"  Modèle créé : « {modele} » (id {modele.pk}), "
                f"clé lue dans {variable_de_cle}.",
            )
        return modele

    def _retirer(self, role):
        """Retire l'affectation d'un role."""
        nombre_supprime, _ = ModeleParRole.objects.filter(role=role).delete()
        if not nombre_supprime:
            self.stdout.write(f"  {role} : aucune affectation à retirer.")
            return
        self.stdout.write(
            f"  {role} : affectation retirée — le rôle retombe sur "
            f"« {modele_du_role(role)} ».",
        )

    def _lister(self):
        """Affiche chaque role, son modele, et d'ou il vient."""
        affectations = {
            affectation.role: affectation.modele
            for affectation in ModeleParRole.objects.select_related("modele")
        }
        for role in RoleDeModele:
            modele_affecte = affectations.get(role.value)
            if modele_affecte is not None:
                origine = "affecté"
                modele = modele_affecte
            else:
                origine = "repli sur la Configuration"
                modele = modele_du_role(role.value)
            self.stdout.write(
                f"  {role.label} : {modele or 'aucun modèle'} ({origine})",
            )
