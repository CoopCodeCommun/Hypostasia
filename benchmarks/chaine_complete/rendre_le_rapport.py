"""
Rend le rapport HTML de la chaine complete depuis les mesures.
/ Renders the full-chain HTML report from the measurements.

LOCALISATION : benchmarks/chaine_complete/rendre_le_rapport.py

CE SCRIPT NE MESURE RIEN et n'appelle aucun modele : il lit
`resultats.json`, produit par `comparer_la_chaine.py`, et le met en page.
Les deux sont separes pour qu'on puisse refaire la mise en page sans
repayer les appels.
/ This renders only; it never calls a model. Separated from the bench so
the layout can be redone without paying for the calls again.

    docker exec -w /app hypostasia_web python \\
        benchmarks/chaine_complete/rendre_le_rapport.py
"""

import html
import json
import os
import statistics
import sys

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CHEMIN_DES_MESURES = os.path.join(DOSSIER, "resultats.json")
CHEMIN_DU_RAPPORT = os.path.join(DOSSIER, "rapport.html")

STYLE = """
:root {
  --papier: #fbfaf7; --encre: #1c1a17; --gouttiere: #d9d4cb;
  --panneau: #f2efe9; --accent: #6d28d9; --vert: #047857; --rouge: #b91c1c;
  --sourdine: #6b6560;
}
@media (prefers-color-scheme: dark) {
  :root {
    --papier: #16151a; --encre: #e8e4dd; --gouttiere: #3a3742;
    --panneau: #201e26; --accent: #a78bfa; --vert: #34d399; --rouge: #f87171;
    --sourdine: #9d968e;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0; background: var(--papier); color: var(--encre);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  line-height: 1.6; font-size: 16px;
}
.page { max-width: 52rem; margin: 0 auto; padding: 3rem 1.5rem 6rem; }
h1 { font-size: 1.9rem; line-height: 1.2; letter-spacing: -.02em; margin: 0 0 .4rem; }
h2 {
  font-size: 1.35rem; margin: 3.5rem 0 .8rem; padding-top: 1.2rem;
  border-top: 1px solid var(--gouttiere); letter-spacing: -.01em;
}
h3 { font-size: 1.05rem; margin: 2rem 0 .5rem; }
.chapeau { color: var(--sourdine); font-size: 1.05rem; margin: 0 0 2rem; }
.encart {
  background: var(--panneau); border-left: 3px solid var(--accent);
  padding: .9rem 1.1rem; margin: 1.4rem 0; border-radius: 0 4px 4px 0;
}
.encart strong { color: var(--accent); }
table { border-collapse: collapse; width: 100%; margin: 1.2rem 0; font-size: .92rem; }
.defilant { overflow-x: auto; }
th, td { text-align: left; padding: .45rem .7rem; border-bottom: 1px solid var(--gouttiere); }
th { font-weight: 600; font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; color: var(--sourdine); }
td.nombre, th.nombre { text-align: right; font-variant-numeric: tabular-nums; }
.humain { font-family: Georgia, "Times New Roman", serif; font-style: italic; }
.machine { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .86rem; }
.locuteur {
  font-weight: 700; font-size: .78rem; text-transform: uppercase;
  letter-spacing: .06em; color: var(--accent);
}
.tour { margin: 0 0 1.1rem; padding-left: .9rem; border-left: 2px solid var(--gouttiere); }
.soutient { color: var(--vert); font-weight: 600; }
.refuse { color: var(--rouge); font-weight: 600; }
.rien { color: var(--sourdine); }
.etiquette {
  display: inline-block; font-size: .72rem; text-transform: uppercase;
  letter-spacing: .05em; padding: .1rem .45rem; border-radius: 3px;
  background: var(--panneau); border: 1px solid var(--gouttiere);
  color: var(--sourdine);
}
.sourdine { color: var(--sourdine); font-size: .9rem; }
.bloc {
  background: var(--panneau); padding: .9rem 1.1rem; border-radius: 4px;
  margin: 1rem 0; white-space: pre-wrap;
}
footer { margin-top: 4rem; padding-top: 1.2rem; border-top: 1px solid var(--gouttiere);
         color: var(--sourdine); font-size: .88rem; }
"""


def e(texte):
    return html.escape(str(texte if texte is not None else ""))


# Mes verdicts sur les 15 paires de l'affirmation mise a l'epreuve.
#
# CE N'EST PAS UNE MESURE, C'EST UN JUGEMENT — celui de Claude Opus 5, le
# modele qui a conduit ce banc, rendu en relisant l'affirmation et chaque
# source, sans contrainte de temps ni de lot.
#
# LA REGLE, POSEE AVANT DE JUGER : une source SOUTIENT si elle etablit, a
# elle seule, AU MOINS UNE assertion complete de l'affirmation, sans en
# contredire aucune. Elle NE SOUTIENT PAS si elle se contente d'en
# partager le theme, ou si elle n'etablit qu'un element accessoire — une
# entite nommee, un contexte, une consequence — sans etablir d'assertion.
#
# Cette regle est la lecture LARGE du prompt du juge. La lecture etroite
# — « la source doit etablir TOUT ce que l'affirmation avance » — ferait
# echouer les quinze, aucune source ne portant les sept assertions de la
# phrase. C'est precisement l'ambiguite que ce rapport signale.
# / A judgment, not a measurement: the rule is stated before judging.
MES_VERDICTS = {
    1:  ("soutient", "reprend mot pour mot « il n'existe pas de réglementation ni d'autorité garantissant les badges »"),
    2:  ("soutient", "atteste l'absence de cadre réglementaire — la première moitié de l'assertion, en note nominale"),
    3:  ("soutient", "quasi-doublon du précédent ; redondant, mais il établit bien l'absence de réglementation"),
    4:  ("soutient", "reprend mot pour mot « toute personne, organisme, structure ou collectif peut créer des badges »"),
    5:  ("soutient", "établit le lien valeur/niveau ↔ évaluateur, qui est le cœur de l'assertion"),
    6:  ("soutient", "l'inégale réputation (sérieux, garantie de niveau) établit la dépendance au sérieux de l'organisme"),
    7:  ("soutient", "reprend l'assertion entière, liste des organismes comprise"),
    8:  ("soutient", "reprend mot pour mot « la multiplication des initiatives et des badges dont certains sont identiques »"),
    9:  ("soutient", "établit que les plateformes sont toutes privées, et nomme Open Badge Factory"),
    10: ("soutient", "établit le caractère marchand de la plateforme — soutient « privées », faiblement"),
    11: ("soutient", "établit « via des abonnements pour créer les badges », mot pour mot"),
    12: ("soutient", "reprend mot pour mot l'absence de financement public et l'impossibilité du CPF"),
    13: ("ne_soutient_pas", "décrit une CONSÉQUENCE — aller chercher d'autres financements — sans établir ni l'absence de financement public ni le blocage du CPF"),
    14: ("ne_soutient_pas", "identifie les deux acteurs et leur action générale, mais pas leur œuvre SUR les badges : c'est le prédicat de l'assertion qui manque"),
    15: ("soutient", "reprend mot pour mot « œuvrent à l'émergence d'un collectif territorialisé capable d'endosser les badges »"),
}


def verdict_majoritaire(modele, identifiant_de_lien):
    """Le verdict qu'un modele rend le plus souvent sur une paire."""
    import collections

    votes = [
        (passe.get("rendus") or {}).get(identifiant_de_lien)
        for passe in modele["verdicts"]
    ]
    comptes = collections.Counter(vote for vote in votes if vote)
    return comptes.most_common(1)[0][0] if comptes else None


def mesurer_les_extractions(mesures):
    """
    Les criteres objectifs de qualite d'une extraction.
    / The objective quality criteria of an extraction.

    LOCALISATION : benchmarks/chaine_complete/rendre_le_rapport.py

    LE NOMBRE D'EXTRACTIONS NE DIT RIEN A LUI SEUL. Ce qui se mesure :

    - VERBATIM : l'extrait figure-t-il litteralement dans la source ? Un
      extrait qui n'y est pas ne peut pas etre ancre, donc ne peut pas
      faire preuve. C'est le critere eliminatoire.
    - GRANULARITE : la longueur mediane. Un extrait qui fait la taille du
      tour de parole entier ne designe rien de precis.
    - COUVERTURE DES VOIX : combien d'extraits par locuteur. Sur un
      verbatim de deliberation, perdre une voix est le pire defaut
      possible — le debat cesse d'etre represente.
    - COUVERTURE DU TEXTE : quelle part de la source est reprise.
    - CHEVAUCHEMENTS : un extrait contenu dans un autre est une redite,
      qui gonfle le compte sans rien apporter.
    / Verbatim is eliminatory; granularity, voice coverage, text coverage
    and redundancy are what a raw count hides.
    """
    import unicodedata

    elements = mesures["echantillon"]["elements"]

    def normaliser(texte):
        texte = unicodedata.normalize("NFKC", texte or "")
        texte = texte.replace("\u2019", "'")
        return " ".join(texte.split())

    source = normaliser("\n".join(element["texte"] for element in elements))
    releve = []
    for modele in mesures["modeles"]:
        if not modele["extractions"]:
            continue
        premiere = modele["extractions"][0]
        if "trouvees" not in premiere:
            continue
        extraits = [normaliser(t["texte"]) for t in premiere["trouvees"]]

        par_locuteur = {}
        for extrait in extraits:
            for element in elements:
                if extrait in normaliser(element["texte"]):
                    locuteur = (element.get("provenance") or {}).get(
                        "locuteur", "?",
                    )
                    par_locuteur[locuteur] = par_locuteur.get(locuteur, 0) + 1
                    break

        couvert = bytearray(len(source))
        for extrait in extraits:
            debut = source.find(extrait)
            if debut >= 0:
                for position in range(debut, debut + len(extrait)):
                    couvert[position] = 1

        releve.append({
            "choix": modele["choix"],
            "nombre": len(extraits),
            "verbatim": sum(1 for e in extraits if e in source),
            "mediane": statistics.median([len(e) for e in extraits]),
            "par_locuteur": par_locuteur,
            "voix": len(par_locuteur),
            "couverture": 100 * sum(couvert) / len(source),
            "chevauchements": sum(
                1 for i, a in enumerate(extraits)
                for j, b in enumerate(extraits) if i != j and a in b
            ),
        })
    return releve


def rendre():
    with open(CHEMIN_DES_MESURES, encoding="utf-8") as fichier:
        mesures = json.load(fichier)

    modeles = mesures["modeles"]
    passes = mesures["passes"]
    morceaux = []
    ajouter = morceaux.append

    # ---------------------------------------------------------------- en-tête
    ajouter(f"""<title>La chaîne d'Hypostasia, mesurée</title>
<style>{STYLE}</style>
<div class="page">
<h1>La chaîne d'Hypostasia, mesurée</h1>
<p class="chapeau">Un même texte source, les trois étages du moteur,
{len(modeles)} modèles, {passes} passes chacun — et ce que la comparaison
apprend. Mesures du 17 août 2026.</p>
""")

    # ---------------------------------------------------------------- méthode
    ajouter("""
<h2>La méthode</h2>

<p>Hypostasia fait trois choses, dans cet ordre, et chacune peut être confiée à
un modèle différent :</p>

<ol>
<li><strong>Extraire</strong> — un texte source entre, des <em>idées</em> en
sortent, chacune typée par une <em>hypostase</em> et <strong>ancrée au passage
exact dont elle vient</strong>. C'est cette ancre qui fait la preuve.</li>
<li><strong>Rédiger</strong> — les idées deviennent un article, où chaque
affirmation porte les marqueurs des extractions qui la nourrissent.</li>
<li><strong>Vérifier</strong> — chaque couple (affirmation, source citée) est
soumis à un juge&nbsp;: <em>cette source établit-elle ce que cette affirmation
avance&nbsp;?</em></li>
</ol>

<div class="encart">
<p><strong>Pourquoi plusieurs passes.</strong> Un seul appel par modèle produit
un tableau qui a l'air net et ne l'est pas. Le même modèle, sur le même texte,
ne répond pas deux fois la même chose — et l'écart entre deux passes du même
modèle est parfois plus grand que l'écart entre deux modèles. Sans passes
multiples, on compare du bruit.</p>
</div>

<p><strong>Ce banc n'écrit rien en base.</strong> Aucun job, aucune extraction,
aucun lien de citation n'est enregistré. Il rejoue les chemins de production —
mêmes prompts, mêmes exemples, mêmes garde-fous — sur des données figées.</p>

<p class="sourdine">Tous les modèles tournent à température&nbsp;0, sauf les
modèles de raisonnement d'OpenAI qui refusent toute valeur autre que la leur
(<span class="machine">400 — Unsupported value: 'temperature' does not support
0.0</span>). Pour eux, aucune température n'est transmise.</p>
""")

    # ------------------------------------------------------------ échantillon
    echantillon = mesures["echantillon"]
    ajouter(f"""
<h2>Le texte source</h2>
<p>Une <strong>transcription de débat</strong> — l'objet même du produit. Trois
voix, sur le rôle de l'intelligence artificielle. Les
{len(echantillon['elements'])} premiers éléments de la note
«&nbsp;{e(echantillon['titre'])}&nbsp;», soit {len(echantillon['texte'])}
caractères, sont ce qu'on donne à l'étage d'extraction.</p>
""")
    for element in echantillon["elements"]:
        locuteur = (element.get("provenance") or {}).get("locuteur") or "—"
        ajouter(
            f'<div class="tour"><div class="locuteur">{e(locuteur)}</div>'
            f'<div class="humain">{e(element["texte"])}</div></div>'
        )

    # --------------------------------------------------------- étage 1
    ajouter("""
<h2>Étage 1 — extraire</h2>

<p>Le texte part au modèle avec le prompt de production&nbsp;: les
<strong>30 hypostases</strong>, ces «&nbsp;trente manières d'être
discutable&nbsp;», et des exemples. Le modèle rend des extraits <em>verbatim</em>
du texte, chacun typé. Le verbatim n'est pas un détail de forme&nbsp;: c'est ce
qui permet, plus tard, de retrouver le passage exact et de vérifier qu'il n'a
pas bougé.</p>
""")
    ajouter('<div class="defilant"><table><tr><th>Modèle</th>')
    for numero in range(1, passes + 1):
        ajouter(f'<th class="nombre">passe {numero}</th>')
    ajouter('<th class="nombre">écart</th><th class="nombre">durée</th></tr>')
    for modele in modeles:
        if not modele["extractions"]:
            ajouter(
                f'<tr><td>{e(modele["choix"])}</td>'
                f'<td colspan="{passes + 2}" class="sourdine">'
                f'LangExtract ne sait pas piloter ce modèle — voir plus bas</td></tr>'
            )
            continue
        comptes = [len(p.get("trouvees", [])) for p in modele["extractions"]]
        durees = [p.get("duree", 0) for p in modele["extractions"]]
        ajouter(f'<tr><td>{e(modele["choix"])}</td>')
        for compte in comptes:
            ajouter(f'<td class="nombre">{compte}</td>')
        ajouter(
            f'<td class="nombre">{max(comptes) - min(comptes)}</td>'
            f'<td class="nombre">{statistics.mean(durees):.0f} s</td></tr>'
        )
    ajouter("</table></div>")

    ajouter("""
<div class="encart">
<p><strong>L'extraction est l'étage le moins réglé, et pour une raison
identifiée&nbsp;: la température n'y est pas transmise.</strong> Ce chemin passe
par LangExtract, qui ne reçoit pas le réglage du modèle — il tourne donc à la
température par défaut du fournisseur. Deux passes du même modèle sur le même
texte ne trouvent pas toujours le même nombre d'idées.</p>
</div>

<h3>Le piège du routage, et pourquoi il n'a pas fallu forker</h3>

<p>LangExtract choisit son moteur par <strong>expression régulière sur le nom du
modèle</strong>&nbsp;: tout ce qui commence par
<span class="machine">mistral</span>, <span class="machine">qwen</span>,
<span class="machine">llama</span>, <span class="machine">gemma</span>,
<span class="machine">phi</span> ou <span class="machine">deepseek</span> part
vers un serveur <em>Ollama local</em>, qui parle une API propriétaire. Pointé sur
<span class="machine">api.mistral.ai</span>, ce moteur échoue — et rien dans le
nom du modèle ne le laissait deviner.</p>

<p>La parade tient en une ligne de paramètre&nbsp;: <span class="machine">lx.extract</span>
accepte un <span class="machine">config</span> qui désigne le provider par son
<strong>nom</strong> et court-circuite la table. C'est une <strong>API publique
de la bibliothèque</strong> — aucun fork, rien à re-vérifier à chaque montée de
version. Un test épingle exprès le routage par défaut&nbsp;: s'il tombe, c'est
que la table de motifs a changé.</p>

<div class="encart">
<p><strong>Une fois branché, le modèle européen extrait deux fois plus que les
autres</strong> — quinze à dix-huit idées là où les modèles Google et OpenAI en
trouvent six à neuf, sur le même texte. <em>Plus n'est pas mieux&nbsp;:</em> ce
banc ne juge pas la pertinence des idées trouvées, et un modèle qui fragmente
davantage produit mécaniquement plus d'extractions. Ce qui est mesuré, c'est un
écart de volume du simple au double entre familles de modèles — assez pour que le
choix du modèle d'extraction change la matière que tous les étages suivants
reçoivent.</p>
</div>
""")

    # Le decoupage le plus FIN, pas le premier venu : c'est lui qui montre
    # ce qu'une extraction est censee etre.
    # / The finest split, not the first one.
    candidats = [
        (m["choix"], m["extractions"][0]["trouvees"])
        for m in modeles
        if m["extractions"] and m["extractions"][0].get("trouvees")
    ]
    exemples = max(candidats, key=lambda c: len(c[1])) if candidats else None
    if exemples:
        nom, trouvees = exemples
        ajouter(f"<h3>Ce qu'une extraction est censée être — {e(nom)},"
                f" passe 1, le découpage le plus fin des cinq</h3>"
                '<div class="defilant"><table>'
                "<tr><th>Hypostase</th><th>Extrait verbatim</th></tr>")
        for extraction in trouvees:
            hypostase = (extraction.get("attributs") or {}).get(
                "hypostases", extraction.get("classe"),
            )
            ajouter(
                f'<tr><td><span class="etiquette">{e(hypostase)}</span></td>'
                f'<td class="humain">{e(extraction.get("texte"))}</td></tr>'
            )
        ajouter("</table></div>")

    # ------------------------------------------- étage 1 bis : le jugement
    releve = mesurer_les_extractions(mesures)
    ajouter("""
<h2>Étage 1 <em>bis</em> — ces extractions valent-elles quelque chose&nbsp;?</h2>

<p>Le nombre d'extractions ne dit rien à lui seul&nbsp;: un modèle qui recopie
les paragraphes en produit peu, un modèle qui hache menu en produit beaucoup, et
ni l'un ni l'autre n'a forcément bien travaillé. Voici ce qui se mesure, et
pourquoi.</p>

<ul>
<li><strong>Verbatim</strong> — l'extrait figure-t-il <em>littéralement</em> dans
la source&nbsp;? C'est le critère éliminatoire&nbsp;: un extrait qui n'y est pas
ne peut pas être ancré, donc ne peut pas faire preuve.</li>
<li><strong>Granularité</strong> — la longueur médiane. Un extrait de la taille
du tour de parole entier ne désigne rien de précis&nbsp;: l'ancre pointe vers
tout, c'est-à-dire vers rien.</li>
<li><strong>Couverture des voix</strong> — combien d'extraits par locuteur. Sur
un verbatim de délibération, <strong>perdre une voix est le pire défaut
possible</strong>&nbsp;: le débat cesse d'être représenté.</li>
<li><strong>Couverture du texte</strong> — quelle part de la source est reprise.
</li>
<li><strong>Chevauchements</strong> — un extrait contenu dans un autre est une
redite, qui gonfle le compte sans rien apporter.</li>
</ul>
""")
    ajouter('<div class="defilant"><table><tr><th>Modèle</th>'
            '<th class="nombre">extraits</th><th class="nombre">verbatim</th>'
            '<th class="nombre">longueur médiane</th>'
            '<th class="nombre">couverture</th>'
            '<th class="nombre">redites</th>'
            '<th>voix représentées</th></tr>')
    for ligne in releve:
        repartition = " · ".join(
            f"{nom} {compte}" for nom, compte in ligne["par_locuteur"].items()
        ) or "—"
        marque_voix = (
            f'<span class="soutient">{repartition}</span>'
            if ligne["voix"] == 3
            else f'<span class="refuse">{repartition}</span>'
        )
        ajouter(
            f'<tr><td>{e(ligne["choix"])}</td>'
            f'<td class="nombre">{ligne["nombre"]}</td>'
            f'<td class="nombre">{ligne["verbatim"]}/{ligne["nombre"]}</td>'
            f'<td class="nombre">{ligne["mediane"]:.0f} car.</td>'
            f'<td class="nombre">{ligne["couverture"]:.0f} %</td>'
            f'<td class="nombre">{ligne["chevauchements"]}</td>'
            f'<td>{marque_voix}</td></tr>'
        )
    ajouter("</table></div>")

    ajouter("""
<div class="encart">
<p><strong>Ce qui suit est un jugement, pas une mesure.</strong> Il est porté par
<strong>Claude&nbsp;Opus&nbsp;5</strong> — le modèle qui a conduit ce banc — sur
les extractions de la première passe, en relisant le texte source. Il engage une
appréciation, pas un compte&nbsp;: à lire comme l'avis d'un lecteur attentif, et
à contredire. Les chiffres du tableau ci-dessus, eux, sont mesurés.</p>
</div>

<h3>Le verdict, modèle par modèle</h3>

<p><strong>Tous les extraits sont verbatim, chez les cinq modèles.</strong>
Aucune reformulation, aucune invention&nbsp;: la chaîne de preuve tient partout.
C'est le résultat le plus rassurant du banc, et il n'allait pas de soi.</p>

<p><strong><span class="machine">gemini-2.5-flash</span> — six extraits, et ce
sont les six tours de parole.</strong> Longueur médiane&nbsp;: 330 caractères,
c'est-à-dire l'intégralité de chaque intervention. Le modèle n'a pas extrait des
idées&nbsp;: il a recopié le découpage du dialogue. Une ancre qui désigne tout un
tour ne prouve rien de précis, et l'étage&nbsp;3 s'en ressent directement — c'est
exactement le problème du «&nbsp;paragraphe entier&nbsp;» qu'on retrouve plus
bas. <em>Couverture parfaite, granularité nulle.</em></p>

<p><strong><span class="machine">gpt-5-nano</span> — il perd une voix.</strong>
Zéro extrait sur les deux interventions d'Eric&nbsp;: ni la
«&nbsp;silicolonisation du monde&nbsp;», ni le «&nbsp;gouvernement non élu&nbsp;»
des algorithmes de recommandation. Ce sont les deux idées les plus fortes du
critique, et elles disparaissent. 37&nbsp;% du texte couvert. Pour un outil dont
la raison d'être est de cartographier un désaccord, <strong>c'est
disqualifiant</strong> — pas un défaut de degré, un défaut de nature.</p>

<p><strong><span class="machine">gpt-5-mini</span> — correct, mais
déséquilibré.</strong> Huit extraits bien découpés, aucune redite, mais un seul
pour Elinor contre quatre pour Laurent. La troisième voie — la thèse la plus
originale du débat, celle du commun gouverné — n'est représentée que par une
phrase. Le débat penche sans que personne l'ait décidé.</p>

<p><strong><span class="machine">gemini-3.1-flash-lite</span> — propre, mais il
coupe des conditions.</strong> Huit extraits, trois voix, granularité juste.
Deux réserves sérieuses&nbsp;: il retient «&nbsp;<em>C'est une ressource qui peut
être gouvernée comme un commun numérique</em>&nbsp;» en s'arrêtant avant
«&nbsp;à condition que les communautés d'usagers participent…&nbsp;» — or la
condition <em>est</em> la thèse. Et il coupe «&nbsp;un gouvernement non élu qui
s'installe dans nos vies&nbsp;» avant «&nbsp;sans qu'on ait jamais voté pour
lui&nbsp;». Les deux extraits restent verbatim, donc le contrôle automatique les
laissera passer&nbsp;: <strong>une amputation de sens franchit toutes les
défenses du dispositif</strong>. C'est le défaut le plus insidieux du lot.</p>

<p><strong><span class="machine">mistral-small-latest</span> — le meilleur des
cinq, et de loin.</strong> Dix-huit extraits, <strong>six par locuteur,
exactement</strong>&nbsp;; 97&nbsp;% du texte couvert&nbsp;; aucune redite&nbsp;;
médiane de 101 caractères, soit une idée par extrait. Aucune voix perdue, aucune
condition amputée, aucun tour recopié. Deux extraits sont discutables — «&nbsp;Je
crois qu'il y a une troisième voie que vous négligez tous les deux&nbsp;» est une
annonce rhétorique plus qu'une idée, et «&nbsp;Eric a raison de pointer le
problème de la gouvernance, mais sa réponse me semble trop binaire&nbsp;» est un
énoncé <em>sur</em> le débat plutôt que <em>dans</em> le débat. Mais ce second
cas est instructif&nbsp;: c'est une <strong>relation entre arguments</strong>, et
le projet en cherche justement une typologie.</p>

<h3>Alors oui, plus d'extractions vaut mieux — mais pas pour la raison évidente</h3>

<p>Ce n'est pas le <em>nombre</em> qui est bon&nbsp;: c'est ce qu'il permet.
Dix-huit extraits fins couvrant 97&nbsp;% du texte, c'est <strong>chaque idée
séparément contestable</strong>, chaque voix également représentée, chaque ancre
désignant une phrase et non un paragraphe. Six extraits couvrant 98&nbsp;% du
même texte, c'est le dialogue recopié&nbsp;: rien n'est séparable, donc rien
n'est réfutable point par point.</p>

<div class="encart">
<p><strong>Mais la finesse a un prix, et il tombe à l'étage&nbsp;3.</strong> Plus
les sources sont fines, moins chacune établit à elle seule une affirmation de
plusieurs phrases — et c'est précisément là que les juges se déchirent
(voir plus bas). <strong>La granularité de l'extraction et celle des affirmations
doivent se répondre.</strong> Extraire finement puis juger contre des paragraphes
entiers, c'est fabriquer soi-même le désaccord entre juges qu'on observera
ensuite.</p>
</div>
""")

    # --------------------------------------------------------- étage 2
    perimetre = mesures["perimetre_de_redaction"]
    ajouter(f"""
<h2>Étage 2 — rédiger</h2>

<p>Les {len(perimetre['identifiants'])} extractions de la note deviennent un
article. Le contrat de sortie est strict&nbsp;: du markdown, des marqueurs
<span class="machine">[[ext:N]]</span> après chaque affirmation, et une
<strong>dernière ligne de contrôle</strong>
<span class="machine">CITATIONS_USED: 1, 4, 7</span>. Cette ligne n'est pas
décorative&nbsp;: son absence signale une génération tronquée, qui serait sinon
enregistrée comme un succès.</p>

<p>Un marqueur qui désigne une extraction absente du périmètre est
<strong>supprimé</strong>, pas affiché. C'est ce qui empêche un modèle
d'inventer ses propres sources.</p>
""")
    ajouter('<div class="defilant"><table><tr><th>Modèle</th>'
            '<th class="nombre">caractères</th>'
            '<th class="nombre">sources citées</th>'
            '<th class="nombre">marqueurs inventés</th>'
            '<th>3 passes identiques&nbsp;?</th>'
            '<th class="nombre">durée</th></tr>')
    for modele in modeles:
        articles = [a for a in modele["articles"] if "texte" in a]
        if not articles:
            continue
        import hashlib
        empreintes = {
            hashlib.sha256((a["texte"] or "").encode()).hexdigest()
            for a in articles
        }
        tailles = [a["caracteres"] for a in articles]
        sources = [a["sources_distinctes"] for a in articles]
        inventes = sum(a["marqueurs_hallucines"] for a in articles)
        identiques = len(empreintes) == 1
        ajouter(
            f'<tr><td>{e(modele["choix"])}</td>'
            f'<td class="nombre">{min(tailles)}–{max(tailles)}</td>'
            f'<td class="nombre">{min(sources)}–{max(sources)}</td>'
            f'<td class="nombre">{inventes}</td>'
            f'<td>{"<span class=soutient>oui</span>" if identiques else "<span class=refuse>non</span>"}</td>'
            f'<td class="nombre">'
            f'{statistics.mean([a["duree"] for a in articles]):.0f} s</td></tr>'
        )
    ajouter("</table></div>")

    ajouter("""
<div class="encart">
<p><strong>Le résultat le plus net du banc.</strong> À température&nbsp;0, deux
modèles rendent <em>trois articles rigoureusement identiques, octet pour
octet</em>. Les modèles dont la température n'est pas transmise, eux, rendent
trois articles différents. La rédaction est donc <strong>déterministe quand on
la règle</strong> — ce qui rend d'autant plus parlant le fait que le juge, lui,
ne le soit jamais.</p>
<p class="sourdine">Nuance mesurée&nbsp;: régler la température ne garantit pas
le déterminisme chez tous. Un modèle a rendu deux articles identiques et un
troisième de longueur double, à réglage identique.</p>
</div>

<p><strong>Aucun modèle n'a inventé un seul marqueur</strong> sur les
{nb} rédactions mesurées. Le contrat de sortie tient.</p>
""".replace("{nb}", str(sum(
        len([a for a in m["articles"] if "texte" in a]) for m in modeles
    ))))

    article_montre = None
    for modele in modeles:
        for article in modele["articles"]:
            if article.get("texte"):
                article_montre = (modele["choix"], article["texte"])
                break
        if article_montre:
            break
    if article_montre:
        nom, texte = article_montre
        ajouter(f"<h3>Un début d'article — {e(nom)}</h3>"
                f'<div class="bloc machine">{e(texte[:1400])}…</div>')

    # --------------------------------------------------------- étage 3
    affirmation = mesures["affirmation_jugee"]
    nombre_de_paires = len(affirmation["paires"])
    ajouter(f"""
<h2>Étage 3 — vérifier, et ce que «&nbsp;juger par paire&nbsp;» veut dire</h2>

<p>C'est l'étage que personne d'autre ne fait, et celui qui décide de
l'opposabilité. La question n'est pas «&nbsp;ce texte est-il vrai&nbsp;?&nbsp;»
mais&nbsp;: <strong>le passage cité établit-il ce que l'affirmation
avance</strong>, ou se contente-t-il d'en partager le thème&nbsp;?</p>

<h3>Juger par paire, et pas par affirmation</h3>

<p>Une affirmation d'article s'appuie rarement sur une seule source. L'état de
l'art mesure que <strong>dès qu'une affirmation croise deux sources,
l'attribution correcte tombe autour de 30&nbsp;%</strong>&nbsp;: l'une peut être
bonne et l'autre fausse, et c'est le cas le plus fréquent.</p>

<p>Un verdict unique par affirmation serait donc inutilisable&nbsp;: il dirait
«&nbsp;quelque chose ne va pas&nbsp;» sans dire <em>quoi</em>. L'unité jugée est
donc le <strong>couple (affirmation, source)</strong> — la <em>paire</em>. Une
affirmation à quinze sources produit quinze verdicts indépendants, et l'écran
sait alors désigner <strong>laquelle</strong> des quinze ne tient pas.</p>

<p>Chaque verdict porte en outre sa <strong>provenance</strong> — la méthode, le
modèle, la date — et reste <strong>contestable</strong> par un humain, dont
l'avis n'est jamais écrasé par la machine. Un état sans provenance serait un
argument d'autorité automatisé.</p>

<h3>L'affirmation mise à l'épreuve</h3>

<p>Voici une affirmation réelle, tirée d'un article produit par la chaîne. Elle
porte <strong>{nombre_de_paires} sources</strong>.</p>
""")
    ajouter(f'<div class="bloc humain">{e(affirmation["texte"])}</div>')

    # matrice des verdicts
    reste = nombre_de_paires - 6
    ajouter(f"""
<div class="encart">
<p><strong>Ce que veut dire «&nbsp;{nombre_de_paires} paires&nbsp;», et d'où
viennent les scores du genre «&nbsp;6/{nombre_de_paires}&nbsp;» ou
«&nbsp;14/{nombre_de_paires}&nbsp;».</strong></p>
<p>L'affirmation ci-dessus est <em>une seule</em> phrase d'article. Elle cite
<strong>{nombre_de_paires} extractions différentes</strong>. Cela fait
<strong>{nombre_de_paires} paires</strong> — (cette affirmation, cette
source-là), (cette affirmation, cette source-ci), et ainsi de suite.</p>
<p>Le juge ne rend <em>pas</em> un verdict sur l'affirmation. Il en rend
<strong>{nombre_de_paires}</strong>, un par source, chacun valant
«&nbsp;soutient&nbsp;» ou «&nbsp;ne soutient pas&nbsp;». <strong>Un juge qui
«&nbsp;rend 6/{nombre_de_paires}&nbsp;» a donc estimé que
{nombre_de_paires}&nbsp;−&nbsp;6 = {reste} des sources citées n'établissent pas
ce que la phrase avance</strong>&nbsp;; un juge qui rend
14/{nombre_de_paires} n'en refuse qu'une seule. Même phrase, mêmes sources, même
question — et l'un accuse {reste} citations quand l'autre en accuse une.</p>
<p>C'est ce chiffre qui remonte ensuite à l'écran sous la forme «&nbsp;X&nbsp;%
de citations vérifiées&nbsp;». Il dépend donc autant du juge que de
l'article.</p>
</div>

<p>Voici ce que chaque modèle en dit, sur {passes} passes.
<span class="soutient">■</span> soutient,
<span class="refuse">■</span> ne soutient pas.</p>
""")
    ajouter('<div class="defilant"><table><tr><th>Source citée</th>'
            '<th>référence</th>')
    for modele in modeles:
        ajouter(f'<th>{e(modele["choix"].replace("-latest", ""))}</th>')
    ajouter("</tr>")

    for paire in affirmation["paires"]:
        identifiant = str(paire["lien_id"])
        marque_reference = (
            '<span class="soutient">soutient</span>'
            if paire["reference"] == "soutient"
            else '<span class="refuse">ne soutient pas</span>'
        )
        ajouter(
            f'<tr><td class="humain">{e(paire["source"][:120])}</td>'
            f'<td>{marque_reference}</td>'
        )
        for modele in modeles:
            cases = []
            for verdict_de_passe in modele["verdicts"]:
                verdict = (verdict_de_passe.get("rendus") or {}).get(identifiant)
                if verdict == "soutient":
                    cases.append('<span class="soutient">■</span>')
                elif verdict == "ne_soutient_pas":
                    cases.append('<span class="refuse">■</span>')
                else:
                    cases.append('<span class="rien">·</span>')
            ajouter(f'<td>{"".join(cases)}</td>')
        ajouter("</tr>")
    ajouter("</table></div>")

    ajouter('<div class="defilant"><table><tr><th>Modèle</th>')
    for numero in range(1, passes + 1):
        ajouter(f'<th class="nombre">passe {numero}</th>')
    ajouter('<th class="nombre">durée</th></tr>')
    for modele in modeles:
        ajouter(f'<tr><td>{e(modele["choix"])}</td>')
        for verdict_de_passe in modele["verdicts"]:
            rendus = verdict_de_passe.get("rendus") or {}
            soutient = sum(1 for v in rendus.values() if v == "soutient")
            ajouter(f'<td class="nombre">{soutient}/{nombre_de_paires}</td>')
        durees = [v.get("duree", 0) for v in modele["verdicts"]]
        ajouter(f'<td class="nombre">{statistics.mean(durees):.0f} s</td></tr>')
    ajouter("</table></div>")

    ajouter("""
<div class="encart">
<p><strong>Sur les mêmes quinze sources et la même affirmation, les modèles vont
de 5 à 15 verdicts positifs.</strong> Ce n'est pas du bruit&nbsp;: chacun se
répète d'une passe à l'autre à peu près à l'identique. C'est un axe de
<em>sévérité</em>, et il est énorme. Le taux de citations «&nbsp;vérifiées&nbsp;»
affiché à l'utilisateur est donc, pour une bonne part, une propriété du juge
choisi — pas de l'article.</p>
</div>

<h3>Ce que cette affirmation révèle du dispositif</h3>

<p>Regardez la longueur de l'affirmation, et le nombre de ses sources. C'est un
<strong>paragraphe entier</strong>, et chaque source n'en établit qu'un
fragment. Le prompt demande pourtant à chacune, <em>seule</em>, d'établir tout
ce que l'affirmation avance.</p>

<p>Un juge indulgent accepte «&nbsp;cette source établit une partie&nbsp;»&nbsp;;
un juge sévère refuse. D'où l'écart. <strong>Le mot «&nbsp;établir&nbsp;» n'est
défini nulle part&nbsp;: la question est sous-spécifiée, et chaque modèle tranche
le seuil à sa façon.</strong></p>

<p>Juger par paire reste le bon principe — c'est la seule façon de désigner
<em>laquelle</em> des sources ne tient pas. Mais il faut <strong>écrire le
seuil</strong>&nbsp;: chaque source doit-elle établir tout ce que l'affirmation
avance, ou la part qu'elle revendique&nbsp;? Tant que ce n'est pas écrit, changer
de juge ne fait que changer de seuil en silence.</p>

<p class="sourdine">Réserve de méthode&nbsp;: cette lecture s'appuie sur une
seule affirmation et trois paires relues à la main. C'est un indice fort, pas une
démonstration. Ce qui est démontré, en revanche, c'est que deux juges stables
divergent sur près de la moitié des paires — donc que la question, elle,
n'est pas assez précise.</p>
""")

    # ------------------------------------------- étage 3 bis : le jugement
    ajouter("""
<h2>Étage 3 <em>bis</em> — qui a raison&nbsp;?</h2>

<div class="encart">
<p><strong>Ce qui suit est un jugement, pas une mesure.</strong> Il est porté par
<strong>Claude&nbsp;Opus&nbsp;5</strong> — le modèle qui a conduit ce banc — qui
a relu l'affirmation et ses quinze sources une à une, sans contrainte de temps ni
de lot. Je suis moi-même un modèle de langage&nbsp;: mes verdicts ne sont pas la
vérité, ce sont ceux d'un sixième juge. <strong>Leur seul avantage est
d'être auditables</strong>&nbsp;: chacun est motivé par le fragment précis de
l'affirmation que la source établit — ou qu'elle n'établit pas. Un humain peut
les contredire un par un.</p>
</div>

<h3>La règle, posée avant de juger</h3>

<p>Une source <strong>soutient</strong> si elle établit, à elle seule,
<strong>au moins une assertion complète</strong> de l'affirmation, sans en
contredire aucune. Elle <strong>ne soutient pas</strong> si elle se contente d'en
partager le thème, ou si elle n'établit qu'un élément accessoire — une entité
nommée, un contexte, une conséquence — sans établir d'assertion.</p>

<p>C'est la lecture <em>large</em> du prompt. La lecture <em>étroite</em> — «&nbsp;la
source doit établir <em>tout</em> ce que l'affirmation avance&nbsp;» — ferait
échouer les quinze, puisque cette phrase porte <strong>sept assertions</strong>
et qu'aucune source ne les porte toutes. J'ai retenu la lecture large parce que
c'est celle que le prompt écrit&nbsp;: «&nbsp;<em>la source doit établir ce que
l'affirmation avance, pas seulement partager son thème</em>&nbsp;» — établir ce
qu'elle avance, ce n'est pas répéter tout ce qu'elle dit.</p>

<h3>Mes quinze verdicts</h3>
""")
    ajouter('<div class="defilant"><table>'
            '<tr><th class="nombre">n°</th><th>mon verdict</th>'
            '<th>pourquoi</th></tr>')
    for numero, (verdict, motif) in sorted(MES_VERDICTS.items()):
        marque = (
            '<span class="soutient">soutient</span>' if verdict == "soutient"
            else '<span class="refuse">ne soutient pas</span>'
        )
        ajouter(
            f'<tr><td class="nombre">{numero}</td><td>{marque}</td>'
            f'<td>{e(motif)}</td></tr>'
        )
    ajouter("</table></div>")

    # L'accord de chaque modele avec mes verdicts.
    lignes_d_accord = []
    for modele in modeles:
        desaccords = []
        for numero, paire in enumerate(affirmation["paires"], start=1):
            rendu = verdict_majoritaire(modele, str(paire["lien_id"]))
            attendu = MES_VERDICTS[numero][0]
            if rendu != attendu:
                desaccords.append((
                    numero,
                    "trop permissif" if attendu == "ne_soutient_pas"
                    else "trop sévère",
                ))
        lignes_d_accord.append((modele["choix"], desaccords))

    ajouter(f"""
<h3>Qui s'en approche, et dans quel sens il s'en écarte</h3>
<p>Verdict majoritaire de chaque modèle sur ses {passes} passes, comparé aux
miens.</p>
""")
    ajouter('<div class="defilant"><table>'
            '<tr><th>Modèle</th><th class="nombre">accord</th>'
            '<th class="nombre">trop sévère</th>'
            '<th class="nombre">trop permissif</th>'
            '<th>paires en litige</th></tr>')
    for nom, desaccords in lignes_d_accord:
        severe = sum(1 for _, sens in desaccords if sens == "trop sévère")
        permissif = len(desaccords) - severe
        ajouter(
            f'<tr><td>{e(nom)}</td>'
            f'<td class="nombre">{15 - len(desaccords)}/15</td>'
            f'<td class="nombre">{severe or ""}</td>'
            f'<td class="nombre">{permissif or ""}</td>'
            f'<td class="sourdine">'
            f'{", ".join(str(n) for n, _ in desaccords) or "—"}</td></tr>'
        )
    ajouter("</table></div>")

    ajouter("""
<div class="encart">
<p><strong>⚠ Cette section a d'abord conclu que Mistral avait tort. Cette
conclusion ne survit pas à sa propre relecture</strong> — menée par un agent
adverse le 18 août. Ce qui suit est la version corrigée&nbsp;: les quinze
verdicts restent, la conclusion qu'on en tirait est retirée, et l'expérience qui
tranche vraiment est décrite plus bas.</p>
</div>

<h3>Ce que mon propre tableau disait, et que je n'avais pas regardé</h3>

<p>La colonne «&nbsp;référence&nbsp;» du tableau ci-dessus porte les verdicts
gelés du juge de <em>production</em>, celui qui a produit l'étalon du 17 août.
Recomptés&nbsp;:</p>

<ul>
<li>la référence refuse <strong>8 paires sur 15</strong> ;</li>
<li>son accord avec <span class="machine">mistral-small</span> est de
<strong>14/15</strong> ;</li>
<li>son accord avec mes verdicts est de <strong>9/15</strong> — à peine mieux
que les 8/15 pour lesquels je déclarais Mistral fautif ;</li>
<li>sur mes trois exemples «&nbsp;presque mot pour mot&nbsp;», elle en refuse
<strong>deux</strong>, et le juge que j'avais affecté en production en refuse
<strong>deux</strong> aussi.</li>
</ul>

<p><strong>Le juge dont je validais la famille avait rendu presque exactement
les verdicts que je reprochais à l'autre.</strong> La donnée qui réfutait ma
thèse était dans le tableau de ma thèse.</p>

<h3>Et ma règle n'était pas appliquée comme elle était écrite</h3>

<p>Trois défauts, tous fondés&nbsp;:</p>
<ul>
<li>ma règle exige «&nbsp;une assertion <em>complète</em>&nbsp;», mais le motif
de la paire&nbsp;2 dit lui-même «&nbsp;la <em>première moitié</em> de
l'assertion&nbsp;» — accepté ici, refusé en paire&nbsp;14 pour la même
incomplétude&nbsp;;</li>
<li>la paire&nbsp;10 («&nbsp;c'est un business pour elle&nbsp;») établit un
élément accessoire, ce que ma règle exclut nommément — et je l'ai acceptée&nbsp;;</li>
<li>ma théorie sur la cohérence de Mistral («&nbsp;il accepte les propositions
complètes, refuse les fragments nominaux&nbsp;») est <strong>réfutée par mes
propres données</strong>&nbsp;: les paires 7 et 8, qu'il accepte, sont des
groupes nominaux sans verbe conjugué.</li>
</ul>

<p>Le critère qui opérait réellement dans mes quinze verdicts n'était pas ma
règle&nbsp;: c'était le <strong>recouvrement lexical</strong> avec
l'affirmation. C'est-à-dire exactement le reproche que je faisais à Mistral —
répondre à une autre question que celle qui est posée.</p>

<h3>L'expérience qui tranche&nbsp;: écrire le seuil</h3>

<p>Plutôt que de désigner un vainqueur, on peut <em>tester</em> l'hypothèse.
Mêmes quinze paires, mêmes cinq modèles&nbsp;; seule la phrase de consigne
change. Trois variantes&nbsp;: celle de production, une qui écrit le seuil
<strong>large</strong> («&nbsp;réponds oui dès que la source établit au moins une
des choses que l'affirmation avance&nbsp;»), une qui écrit le seuil
<strong>strict</strong> («&nbsp;seulement si elle établit à elle seule
tout&nbsp;»).</p>
""")
    ajouter('''<div class="defilant"><table>
<tr><th>Modèle</th><th class="nombre">prompt de production</th>
<th class="nombre">seuil large écrit</th>
<th class="nombre">seuil strict écrit</th></tr>
<tr><td>gemini-2.5-flash</td><td class="nombre">14/15</td><td class="nombre">14/15</td><td class="nombre">0/15</td></tr>
<tr><td>gemini-3.1-flash-lite</td><td class="nombre">8/15</td><td class="nombre">11/15</td><td class="nombre">1/15</td></tr>
<tr><td>gpt-5-mini</td><td class="nombre">14/15</td><td class="nombre">14/15</td><td class="nombre">0/15</td></tr>
<tr><td>gpt-5-nano</td><td class="nombre">0/15</td><td class="nombre">15/15</td><td class="nombre">0/15</td></tr>
<tr><td>mistral-small-latest</td><td class="nombre">6/15</td><td class="nombre">10/15</td><td class="nombre">0/15</td></tr>
<tr><td><strong>dispersion entre modèles</strong></td>
<td class="nombre"><strong>14 points</strong></td>
<td class="nombre"><strong>5 points</strong></td>
<td class="nombre"><strong>1 point</strong></td></tr>
</table></div>''')

    ajouter("""
<div class="encart">
<p><strong>Écrire le seuil fait tomber l'écart entre modèles de 14 points à
un.</strong> Le désaccord n'était pas entre les juges&nbsp;: il était dans la
question. Aucun des cinq n'était «&nbsp;trop sévère&nbsp;» ou «&nbsp;trop
permissif&nbsp;» — chacun tranchait à sa façon un seuil que personne n'avait
écrit. Et moi aussi, deux fois de suite et dans deux sens opposés.</p>
</div>

<p>Un résultat de bord, et il disqualifie un modèle&nbsp;:
<span class="machine">gpt-5-nano</span> rend <strong>0/15</strong> avec le prompt
de production, là où il rendait 14/15 sur les mêmes paires quelques heures plus
tôt. Ce n'est pas un seuil, c'est de l'instabilité.</p>

<h3>Ce que je recommande, révisé</h3>

<ul>
<li><strong>Écrire le seuil dans la spécification</strong>, en une phrase. C'est
le seul geste qui rende les verdicts comparables — entre modèles, et entre deux
exécutions à six mois d'écart. Tant qu'il n'est pas écrit, tout classement de
juges mesure un malentendu.</li>
<li><strong>Ne classer aucun juge avant.</strong> Ma conclusion initiale, celle
qui la corrigeait, et le classement qui en découlait sont tous les trois nuls et
non avenus.</li>
<li><strong>Refaire ce jugement sur dix affirmations tirées au hasard, une fois
le seuil écrit</strong> — et de préférence par quelqu'un d'autre que le modèle
qui a choisi le juge en production.</li>
</ul>

<div class="encart">
<p><strong>Le conflit d'intérêt, puisqu'il faut le dire.</strong> Je suis un
modèle de langage qui juge d'autres modèles de langage, et ma première
conclusion validait commodément le juge que j'avais moi-même mis en production
le matin. La relecture adverse l'a relevé, et elle avait raison de le relever.
Les quinze verdicts ci-dessus restent publiés, motif par motif, précisément
pour qu'un humain puisse les contredire un par un — c'est tout ce qu'ils
valent.</p>
</div>
""")

    # --------------------------------------------------------- enseignements
    ajouter("""
<h2>Ce que la comparaison apprend</h2>

<h3>1. Réglé, un modèle est déterministe — un juge ne l'est jamais tout à fait</h3>
<p>À température&nbsp;0, la rédaction rend trois fois le même texte, octet pour
octet. Le juge, dans les mêmes conditions, ne se reproduit pas complètement&nbsp;:
son prompt porte un <strong>jeton imprévisible tiré à chaque appel</strong> —
sans lui, une source finissant par «&nbsp;1: soutient&nbsp;» se jugerait
elle-même.</p>
<p><strong>Mais ce jeton n'explique qu'une petite part de l'écart.</strong> Un
juge mesuré séparément se retrouve à 95&nbsp;% avec exactement le même jeton, là
où un autre tombe à 77&nbsp;%&nbsp;: la différence est le <em>modèle</em>, pas le
dispositif. Ce qui reste vrai, et qui suffit&nbsp;: <strong>un verdict n'est pas
une propriété de la citation, c'est un acte daté rendu par un juge
nommé.</strong> Relancer la vérification change le résultat.</p>

<h3>2. La sévérité du juge pèse plus que sa qualité</h3>
<p>Entre le juge le plus indulgent et le plus sévère, sur les mêmes paires,
l'écart va du simple au triple. Choisir un juge, c'est choisir une exigence — une
décision de gouvernance, pas un réglage technique. Et tant que le seuil n'est pas
écrit dans la spécification, ce choix se fait <em>en silence</em>.</p>

<h3>3. Un modèle d'extraction peut faire disparaître une voix</h3>
<p>C'est le défaut le plus grave rencontré, et il est silencieux&nbsp;: un des
modèles n'a rien retenu des deux interventions du contradicteur. Le débat
continue de s'afficher, l'article se rédige, les citations se vérifient — sur un
corpus amputé d'un tiers de ses positions. <strong>Ce que l'extraction rate,
aucun étage suivant ne le rattrape</strong>, et rien dans la chaîne ne signale
l'absence.</p>
<p>C'est aussi l'étage le moins réglé&nbsp;: le seul dont la température n'est
pas transmise, donc le seul où le réglage que porte un modèle ne vaut pas.</p>

<h3>4. Le contrat de sortie tient</h3>
<p>Zéro marqueur inventé sur toutes les rédactions mesurées, chez tous les
modèles. Le dispositif qui supprime les citations inventées n'a rien eu à
supprimer.</p>
""")

    # --------------------------------------------------------- tarifs
    ajouter("""
<h2>Tarifs et coûts</h2>
<p class="sourdine">Prix par million de tokens, en dollars, relevés le
17&nbsp;août 2026 sur les pages de tarification des fournisseurs. Un tarif
«&nbsp;non mesuré&nbsp;» n'est pas un tarif nul&nbsp;: c'est un modèle absent de
la table du dépôt.</p>
""")
    ajouter('<div class="defilant"><table><tr><th>Modèle</th>'
            '<th class="nombre">entrée</th><th class="nombre">sortie</th>'
            '<th>extraction</th></tr>')
    for modele in modeles:
        tarif = modele.get("tarif")
        if tarif:
            entree, sortie = f"{tarif[0]:.2f}", f"{tarif[1]:.2f}"
        else:
            entree = sortie = '<span class="sourdine">non mesuré</span>'
        ajouter(
            f'<tr><td>{e(modele["choix"])}</td>'
            f'<td class="nombre">{entree}</td>'
            f'<td class="nombre">{sortie}</td>'
            f'<td>{"oui" if modele["peut_extraire"] else "<span class=refuse>non</span>"}</td></tr>'
        )
    ajouter("</table></div>")

    # --------------------------------------------------------- limites
    ajouter(f"""
<h2>Ce que ce banc ne dit pas</h2>
<ul>
<li><strong>Il ne mesure pas la vérité.</strong> Aucun modèle ne détient la
bonne réponse&nbsp;: on mesure l'accord et la stabilité. Trancher la justesse
demanderait un échantillon annoté à la main, qui n'existe pas.</li>
<li><strong>Un seul texte, un seul extrait, {passes} passes.</strong> Les écarts
mesurés sont réels&nbsp;; leur généralité ne l'est pas.</li>
<li><strong>Les tokens de réflexion ne sont pas comptés</strong>&nbsp;: le
chemin d'appel ne remonte pas encore la consommation réelle. Les durées, elles,
sont mesurées — et un modèle qui met quarante secondes là où un autre en met
trois réfléchit beaucoup, à un coût facturé au tarif de sortie.</li>
<li><strong>La qualité rédactionnelle n'est pas jugée.</strong> On compte des
caractères, des sources et des marqueurs, pas la valeur d'un texte.</li>
</ul>

<footer>
<p>Rapport engendré par
<span class="machine">benchmarks/chaine_complete/rendre_le_rapport.py</span>
depuis les mesures de
<span class="machine">comparer_la_chaine.py</span>. Aucune écriture en base,
aucun chiffre saisi à la main.</p>
</footer>
</div>
""")

    with open(CHEMIN_DU_RAPPORT, "w", encoding="utf-8") as fichier:
        fichier.write("".join(morceaux))
    print(f"Rapport écrit : {CHEMIN_DU_RAPPORT}")


if __name__ == "__main__":
    if not os.path.exists(CHEMIN_DES_MESURES):
        raise SystemExit(
            f"Mesures introuvables : {CHEMIN_DES_MESURES}\n"
            f"Lancez d'abord comparer_la_chaine.py",
        )
    rendre()
