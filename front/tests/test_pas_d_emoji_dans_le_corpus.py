"""
Test : les ecrans du corpus ne portent pas d'emoji comme icone.
/ Test: corpus screens use no emoji as icons.

LOCALISATION : front/tests/test_pas_d_emoji_dans_le_corpus.py

POURQUOI CE TEST EXISTE

Le 12 aout, la carte d'une base a ete dessinee sans emoji : la visibilite
s'y lit en toutes lettres, « PUBLIC », en petites capitales monospace.
Les quatre autres ecrans du corpus, eux, gardaient 🌐 👥 🔒 — et les
notes 🎧 🌐 📄 pour leur source. Deux vocabulaires visuels pour la meme
information, sur des ecrans qu'on parcourt a la suite.

L'etalon `corpus.html` n'utilise aucun emoji : sa sous-ligne de note dit
« conseil-2026-03-12.m4a · 3 min 12 · 5 locuteurs · 10 extractions »,
en texte. Un emoji depend de la police du systeme, ne se teinte pas avec
le theme, ignore le mode sombre et rend differemment sur chaque
plateforme — il ne peut pas appartenir a une charte typographique qui
fait tenir trois polices pour dire trois provenances.

Ce test verrouille l'harmonisation : il echouera si un emoji revient
dans un gabarit du corpus.
/ Emoji ignore the theme, depend on system fonts and render differently
per platform: they cannot belong to a typographic charter.
"""

import pathlib
import re

from django.test import SimpleTestCase

# Le dossier des gabarits du corpus. / The corpus templates directory.
GABARITS_DU_CORPUS = (
    pathlib.Path(__file__).resolve().parent.parent
    / "templates" / "front" / "corpus"
)

# UN EMOJI N'EST PAS UN GLYPHE TYPOGRAPHIQUE, ET LA DIFFERENCE COMPTE.
#
# On vise les PICTOGRAMMES EN COULEUR — 🌐 👥 🔒 📌 🎧 📄 — que la
# police systeme dessine a sa guise, qui ignorent `color` et donc le
# mode sombre, et qui changent d'aspect d'une plateforme a l'autre.
#
# On NE vise PAS les signes typographiques monochromes : « ✕ » (U+2715),
# « ✎ » (U+270E), « ↓ », « ↑ », « ↻ », « › ». Ceux-la se teintent avec
# `color`, suivent le theme, et l'etalon les emploie lui-meme dans sa
# rangee d'actions (« ↓ Source », « ↑ Exporter », « ↻ Historique »).
# Une premiere version de ce motif couvrait tout le plan des dingbats et
# les condamnait avec les autres.
# / Colour pictographs only: they ignore `color`, hence dark mode, and
# vary per platform. Monochrome typographic marks are legitimate — the
# mockup uses them in its own action row.
MOTIF_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"   # pictogrammes, symboles et objets, en couleur
    "\U0001F1E6-\U0001F1FF"   # drapeaux
    "\U0000FE0F"              # selecteur de variante EMOJI (force la couleur)
    "]"
)


class PasDEmojiDansLeCorpusTest(SimpleTestCase):
    """
    LOCALISATION : front/tests/test_pas_d_emoji_dans_le_corpus.py
    """

    def test_aucun_gabarit_du_corpus_ne_porte_d_emoji(self):
        """
        Un emoji dans un gabarit du corpus est une regression de charte.
        / An emoji in a corpus template is a charter regression.
        """
        self.assertTrue(
            GABARITS_DU_CORPUS.is_dir(),
            f"Dossier introuvable : {GABARITS_DU_CORPUS}",
        )

        emojis_trouves = []
        for gabarit in sorted(GABARITS_DU_CORPUS.rglob("*.html")):
            for numero_de_ligne, ligne in enumerate(
                gabarit.read_text(encoding="utf-8").splitlines(), start=1
            ):
                for emoji in MOTIF_EMOJI.findall(ligne):
                    chemin_relatif = gabarit.relative_to(GABARITS_DU_CORPUS)
                    emojis_trouves.append(
                        f"{chemin_relatif}:{numero_de_ligne} — « {emoji} »"
                    )

        self.assertEqual(
            emojis_trouves,
            [],
            "Emoji trouvé(s) dans les gabarits du corpus :\n  "
            + "\n  ".join(emojis_trouves)
            + "\n\nLa visibilité et la source se disent en toutes lettres, "
            "comme sur la carte d'une base.",
        )
