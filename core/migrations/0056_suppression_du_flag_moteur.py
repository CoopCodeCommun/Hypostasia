"""
Suppression du flag `Page.moteur` : il n'y a plus qu'un moteur.
/ Removing Page.moteur: one engine remains.

LOCALISATION : core/migrations/0056_suppression_du_flag_moteur.py

Le champ existait pour CHOISIR entre deux moteurs d'ancrage (BR-A,
decision D1). L'ancien est mort le 10 aout 2026 — pont texte<->HTML,
annotation par offsets, tache d'analyse, pastilles de marge : tout est
supprime. Un flag qui ne commande plus rien est une question sans objet.
"""

from django.db import migrations


def refuser_si_des_pages_sont_encore_sur_l_ancien(apps, schema_editor):
    """
    Refuse la suppression tant qu'une page attend sa reconversion.
    / Refuses removal while a page still awaits reconversion.

    POURQUOI CE CONTROLE

    Sur la base de dev, les 213 pages ont ete reconverties avant cette
    migration. Sur une AUTRE base — la production, une sauvegarde
    restauree, la machine d'un collegue — elles peuvent toutes etre
    encore ANCIEN. Supprimer le champ la-bas ne casserait rien
    bruyamment : les pages seraient simplement rendues sans leurs
    surlignages, puisqu'elles n'ont pas d'elements. Une perte muette,
    decouverte a la lecture, sans moyen de revenir en arriere.

    On s'arrete donc, en disant quoi faire :
        manage.py basculer_vers_le_moteur_element --a-blanc
        manage.py basculer_vers_le_moteur_element
    / On another database every page may still be ANCIEN; removing the
    field there would silently drop their highlights.
    """
    Page = apps.get_model("core", "Page")

    # ON NE S'ARRETE QUE S'IL Y A QUELQUE CHOSE A PERDRE.
    #
    # Une page ANCIEN qui ne porte AUCUNE extraction n'a aucun
    # surlignage : la basculer ne change rien a ce qu'on voit. C'est le
    # cas des pages nues qu'une base neuve ou un test de migration
    # fabriquent. Lever pour elles bloquerait la migration sans
    # protéger personne — et c'est ce qui s'est produit : la garde
    # d'origine faisait echouer les tests qui rejouent les migrations.
    #
    # Ce qu'on protege vraiment, c'est une page ANCIEN AVEC des
    # extractions : celle-la perdrait ses surlignages en silence.
    # / Only stop when there is something to lose: a bare ANCIEN page
    # has no highlights to drop.
    restantes = Page.objects.filter(
        moteur="ancien",
        extraction_jobs__entities__isnull=False,
    ).distinct().count()
    if not restantes:
        print(
            "[migration 0056] aucune page ANCIEN porteuse d'extractions — "
            "suppression du flag sans reserve."
        )
        return

    raise RuntimeError(
        f"ARRET : {restantes} page(s) sur l'ANCIEN moteur portent des "
        f"extractions. Supprimer le flag maintenant les afficherait SANS "
        f"leurs surlignages, en silence. Reconvertir d'abord :\n"
        f"    manage.py basculer_vers_le_moteur_element --a-blanc\n"
        f"    manage.py basculer_vers_le_moteur_element"
    )


def rien_a_refaire(apps, schema_editor):
    """Le retour arriere recree le champ vide, sans rien a verifier."""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_page_ingestion_maj_le'),
    ]

    operations = [
        migrations.RunPython(
            refuser_si_des_pages_sont_encore_sur_l_ancien,
            rien_a_refaire,
        ),
        migrations.RemoveField(
            model_name='page',
            name='moteur',
        ),
    ]
