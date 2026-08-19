"""
Les mesures du dossier `benchmarks/`, servies en HTML.
/ The `benchmarks/` measurement notes, served as HTML.

LOCALISATION : front/views_benchmarks.py

POURQUOI UNE ROUTE PLUTOT QU'UN HTML ENGENDRE. Les comptes rendus de
mesure sont ecrits en markdown et mis a jour souvent. Un HTML engendre
serait une SECONDE copie, a regenerer a la main — et le jour ou on
oublie, la page ment sans que rien ne le dise. Cette vue rend le
markdown a la lecture : il n'y a jamais qu'une source.
/ Rendered on read, never generated: a second copy would go stale.

CE QU'ELLE NE FAIT PAS. Elle ne sert QUE des `.md` situes sous
`benchmarks/`, et le chemin est resolu puis VERIFIE comme etant a
l'interieur — sans quoi un `../../.env` serait servi.
"""

from pathlib import Path

import bleach
import markdown
from django.conf import settings
from django.shortcuts import render
from rest_framework import permissions, viewsets

DOSSIER_DES_MESURES = Path(settings.BASE_DIR) / "benchmarks"

# Les balises que le markdown d'un compte rendu peut produire. Les
# tableaux en font partie : c'est la forme meme de ces mesures.
# / The tags a measurement note can produce; tables are essential here.
BALISES_AUTORISEES = [
    "h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "strong", "em", "code",
    "pre", "blockquote", "hr", "br", "a", "table", "thead", "tbody", "tr",
    "th", "td", "del",
]
ATTRIBUTS_AUTORISES = {"a": ["href", "title"]}


def _mesures_disponibles():
    """
    Les comptes rendus, du plus recent au plus ancien.
    / The measurement notes, newest first.

    Le tri est sur le NOM, parce que ces fichiers sont dates en tete de
    nom (`2026-08-19-…`) : c'est la convention du dossier, et elle est
    plus fiable qu'une date de fichier qu'un `git clone` remet a zero.
    / Sorted by name: these files are date-prefixed, and a clone resets
    filesystem dates.
    """
    if not DOSSIER_DES_MESURES.is_dir():
        return []
    fichiers = sorted(
        DOSSIER_DES_MESURES.rglob("*.md"),
        key=lambda chemin: chemin.name, reverse=True,
    )
    return [
        {
            "chemin": str(fichier.relative_to(DOSSIER_DES_MESURES)),
            "nom": fichier.stem,
            "dossier": str(fichier.parent.relative_to(DOSSIER_DES_MESURES)),
        }
        for fichier in fichiers
    ]


def _fichier_de_mesure(chemin_demande):
    """
    Le fichier demande, ou None s'il sort du dossier des mesures.
    / The requested file, or None if it escapes the benchmarks folder.

    LA VERIFICATION D'APPARTENANCE EST OBLIGATOIRE, et elle se fait
    APRES resolution : sans elle, `../../.env` serait servi. `resolve()`
    seul ne protege pas — c'est la comparaison qui protege.
    / The containment check must happen AFTER resolution.
    """
    candidat = (DOSSIER_DES_MESURES / chemin_demande).resolve()
    racine = DOSSIER_DES_MESURES.resolve()
    if not candidat.is_relative_to(racine):
        return None
    if candidat.suffix != ".md" or not candidat.is_file():
        return None
    return candidat


class BenchmarksViewSet(viewsets.ViewSet):
    """
    Les mesures, en lecture. / The measurements, read-only.

    AUTHENTIFICATION EXIGEE, et 404 plutot que 403 (doctrine du projet) :
    ces comptes rendus nomment des modeles, des tarifs et des defauts du
    produit. Rien de secret, rien qui doive etre public non plus.
    """

    permission_classes = [permissions.AllowAny]

    def _refus(self, request):
        from front.views import _exiger_authentification
        return _exiger_authentification(request)

    def list(self, request):
        """GET /benchmarks/ — l'index des mesures."""
        refus = self._refus(request)
        if refus:
            return refus
        return render(request, "front/benchmarks/index.html", {
            "mesures": _mesures_disponibles(),
        })

    def voir(self, request, chemin=None):
        """
        GET /benchmarks/voir/<chemin.md> — une mesure, rendue.

        ROUTEE PAR UN `re_path` EXPLICITE, et c'est une exception
        assumee a la regle du routeur DRF : le chemin d'une mesure porte
        des barres obliques (`redaction/2026-08-19_….md`), qu'un
        `DefaultRouter` ne sait pas exprimer. Meme motif que les trois
        `path()` deja presents dans `front/urls.py`.
        / Explicitly routed: a DefaultRouter cannot express a path
        containing slashes.
        """
        refus = self._refus(request)
        if refus:
            return refus
        fichier = _fichier_de_mesure(chemin or "")
        if fichier is None:
            return render(request, "front/benchmarks/index.html", {
                "mesures": _mesures_disponibles(),
                "introuvable": chemin,
            }, status=404)
        html = markdown.markdown(
            fichier.read_text(encoding="utf-8"),
            extensions=["extra", "toc", "sane_lists"],
        )
        return render(request, "front/benchmarks/mesure.html", {
            "titre": fichier.stem,
            "corps": bleach.clean(
                html, tags=BALISES_AUTORISEES,
                attributes=ATTRIBUTS_AUTORISES, strip=True,
            ),
            "mesures": _mesures_disponibles(),
        })
