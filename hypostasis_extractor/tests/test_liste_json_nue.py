"""
Le « JSON nu » : une liste sans son enveloppe ne doit plus tout perdre.
/ The bare JSON list must no longer lose everything.

LOCALISATION : hypostasis_extractor/tests/test_liste_json_nue.py

LE RISQUE QUE CE TEST EPINGLE. Une plateforme qui rend `[...]` au lieu
de `{"extractions": [...]}` faisait perdre TOUTES les extractions d'un
chunk — EN SILENCE. Le `FormatHandler` de LangExtract 1.1.1 levait une
`FormatParseError` inconditionnelle sur une liste au premier niveau ;
notre `resolver_params={"suppress_parse_errors": True}`
(`hypostasis_extractor/services/analyse_par_element.py`) transformait
alors l'exception en liste vide. Le job finissait `completed` avec zero
extraction — indiscernable d'une page sans idee. Seule trace : un
`logging.exception` dans les journaux du worker.

Mesure du 18 aout 2026, sur la 1.1.1 alors installee :

    enveloppe -> [{'idee': 'x', …}]
    liste nue -> LEVE FormatParseError
                 « Content must be a mapping with an 'extractions' key. »

LangExtract 1.6.0 accepte la liste nue hors mode strict
(`core/format_handler.py` : `if require_wrapper and (strict or not
self.allow_top_level_list)`), avec le commentaire amont « *Some models
return [...] instead of {"extractions": [...]}* ».

POURQUOI CE TEST EXISTE PLUTOT QU'UNE LIGNE DE CHANGELOG. La correction
est chez le fournisseur, pas chez nous : rien dans notre code ne la
protege. Une montee de version future qui la reperdrait ne casserait
AUCUN de nos tests — et le symptome serait, a nouveau, zero extraction
sans erreur.
/ The fix lives upstream; nothing in our code protects it. A future
version losing it would break no test of ours, and the symptom would
again be a silent empty result.

LE ROUTAGE PAR DEFAUT, LUI, EST DEJA EPINGLE AILLEURS :
`test_extraction_par_api_compatible.py`, classe
`LeRoutageParDefautDeLangExtractTest` — verifie que la table de motifs
envoie toujours `mistral-*` vers Ollama, ce qui est la raison d'etre de
`config=`. Ne pas le recopier ici : deux copies du meme verrou finissent
par ne plus verifier la meme chose.
/ The default routing is already pinned elsewhere; do not copy it here.
"""

import json

from django.test import SimpleTestCase


def _handler_comme_en_production():
    """
    Un `FormatHandler` configure comme `lx.extract` le construit.
    / A FormatHandler configured the way lx.extract builds one.

    `use_wrapper=True` et `wrapper_key="extractions"` sont les defauts
    que `extract()` passe (`base_use_wrapper`, `base_wrapper_key`), et
    `use_fences=False` correspond a nos providers en mode JSON.
    """
    from langextract.core import data
    from langextract.core import format_handler as fh

    return fh.FormatHandler(
        format_type=data.FormatType.JSON,
        use_fences=False,
        use_wrapper=True,
        wrapper_key="extractions",
    )


class LaListeJsonNueEstAcceptaleTest(SimpleTestCase):
    """Le contrat que la montee en 1.6.0 nous apporte."""

    def test_l_enveloppe_normale_est_lue(self):
        handler = _handler_comme_en_production()
        reponse = json.dumps(
            {"extractions": [{"idee": "x", "idee_attributes": {}}]},
        )

        extraits = handler.parse_output(reponse, strict=False)

        self.assertEqual(len(extraits), 1)

    def test_une_liste_NUE_est_lue_elle_aussi(self):
        # LE TEST QUI COMPTE. En 1.1.1 cette ligne levait, et notre
        # `suppress_parse_errors=True` rendait alors une liste vide :
        # toutes les extractions du chunk perdues, sans une erreur.
        # / The one that matters: this raised in 1.1.1, and our
        # suppress_parse_errors turned it into a silent empty result.
        handler = _handler_comme_en_production()
        reponse = json.dumps([{"idee": "x", "idee_attributes": {}}])

        extraits = handler.parse_output(reponse, strict=False)

        self.assertEqual(len(extraits), 1)

    def test_le_mode_STRICT_refuse_toujours_la_liste_nue(self):
        # La tolerance est deliberement bornee : en mode strict, le
        # contrat d'enveloppe reste exige. / Deliberately bounded.
        from langextract.core import exceptions

        handler = _handler_comme_en_production()
        reponse = json.dumps([{"idee": "x", "idee_attributes": {}}])

        with self.assertRaises(exceptions.FormatParseError):
            handler.parse_output(reponse, strict=True)


class LaVersionInstalleeEstBienCelleAttendueTest(SimpleTestCase):
    """
    La correction vit chez le fournisseur : la version compte.
    / The fix lives upstream, so the version matters.
    """

    def test_langextract_est_au_moins_en_1_6(self):
        from importlib.metadata import version

        installee = tuple(
            int(morceau) for morceau in version("langextract").split(".")[:2]
        )

        self.assertGreaterEqual(
            installee, (1, 6),
            "LangExtract < 1.6 reperd la tolérance à la liste JSON nue, "
            "et notre suppress_parse_errors la transforme en zéro "
            "extraction silencieuse.",
        )
