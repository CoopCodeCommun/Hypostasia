"""
Migration de donnees : pose role_special sur les carnets « A ranger » et
« Mes imports » existants (SPEC-corpus § 6.3).
/ Data migration: stamp role_special on existing "A ranger" and
"Mes imports" notebooks.

LOCALISATION : core/migrations/0042_estampiller_les_dossiers_speciaux.py

Sans cet estampillage, les resolveurs convertis (core/views._resoudre_dossier,
front/views._obtenir_ou_creer_dossier_imports) creeraient un DOUBLON du
fourre-tout pour chaque utilisateur existant : ils cherchent par role, et
les carnets historiques n'en ont pas.

Regles :
- seuls les carnets AVEC proprietaire sont estampilles (un « A ranger »
  sans owner n'appartient a personne, on ne devine pas) ;
- en cas d'homonymes chez un meme proprietaire, seul le PLUS ANCIEN recoit
  le role — la contrainte unicite_role_special_par_proprietaire interdit
  d'en marquer deux.
/ Only owned notebooks are stamped; oldest wins among duplicates.
"""

from django.db import migrations

CORRESPONDANCE_NOM_VERS_ROLE = {
    "A ranger": "a_ranger",
    "Mes imports": "mes_imports",
}


def estampiller_les_dossiers_speciaux(apps, schema_editor):
    """
    Pose le role technique sur les carnets historiques reconnus par leur
    nom par defaut.
    / Stamps the technical role on historical notebooks recognized by
    their default name.
    """
    Dossier = apps.get_model("core", "Dossier")

    for nom_par_defaut, role in CORRESPONDANCE_NOM_VERS_ROLE.items():
        # Seuls les carnets SANS role sont candidats, et un proprietaire
        # qui possede deja un carnet portant ce role n'est pas re-servi :
        # sans ces deux gardes, relancer la migration sur une base
        # partiellement estampillee (arret apres 0041, resolveurs deja en
        # service) violerait la contrainte d'unicite (retour de relecture).
        # / Idempotence guards: skip already-stamped notebooks and owners
        # already holding the role.
        candidats = (
            Dossier.objects.filter(
                name=nom_par_defaut, owner__isnull=False, role_special="",
            )
            .order_by("owner_id", "created_at", "pk")
        )

        nombre_estampille = 0
        proprietaires_deja_servis = set(
            Dossier.objects.filter(role_special=role, owner__isnull=False)
            .values_list("owner_id", flat=True)
        )
        for dossier in candidats:
            proprietaire_deja_servi = dossier.owner_id in proprietaires_deja_servis
            if proprietaire_deja_servi:
                # Homonyme : on laisse role_special vide, le carnet reste
                # un carnet ordinaire. / Duplicate: left as ordinary.
                continue
            dossier.role_special = role
            dossier.save(update_fields=["role_special"])
            proprietaires_deja_servis.add(dossier.owner_id)
            nombre_estampille += 1

        print(
            f"\n[migration 0042] '{nom_par_defaut}' -> role '{role}' : "
            f"{nombre_estampille} carnet(s) estampille(s)"
        )


def retirer_les_estampilles(apps, schema_editor):
    """
    Rollback : remet role_special a vide partout.
    / Rollback: clears role_special everywhere.
    """
    Dossier = apps.get_model("core", "Dossier")
    nombre = Dossier.objects.exclude(role_special="").update(role_special="")
    print(f"\n[migration 0042 rollback] {nombre} estampille(s) retiree(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_creer_les_appartenances_depuis_la_fk"),
    ]

    operations = [
        migrations.RunPython(
            estampiller_les_dossiers_speciaux,
            reverse_code=retirer_les_estampilles,
        ),
    ]
