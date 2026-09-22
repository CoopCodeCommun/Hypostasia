"""
Le chemin REEL : une selection etendue au CLAVIER (Maj+Bas), puis Suppr,
sous la garde. C'est la que WebKit avale la gouttiere.
"""
import json
from playwright.sync_api import sync_playwright

BASE = ("https://beta.hypostasia.org/static/front/maquettes/"
        "prototype-champ-unique/index.html")
CURSEUR = """([i, o]) => {
    const champ = document.getElementById('champ');
    champ.focus();
    const c = champ.querySelectorAll('.bloc')[i].querySelector('.corps');
    const m = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
    let r = o, n = m.nextNode();
    while (n && r > n.textContent.length) { r -= n.textContent.length; n = m.nextNode(); }
    const p = document.createRange();
    p.setStart(n, Math.min(r, n.textContent.length)); p.collapse(true);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
}"""
ETAT = """() => ({
    gouttieres: document.querySelectorAll('#champ .gouttiere').length,
    textes: Array.from(document.querySelectorAll('#champ .gouttiere'))
        .slice(0, 30).map(g => g.textContent.trim()),
    blocs: document.querySelectorAll('#champ .bloc').length,
})"""

sortie = {}
with sync_playwright() as p:
    for nom in ("webkit", "firefox", "chromium"):
        n = getattr(p, nom).launch()
        c = n.new_context(viewport={"width": 1280, "height": 900},
                          ignore_https_errors=True)
        for garde in ("2", "0"):
            page = c.new_page()
            page.goto(f"{BASE}?ce=true&garde={garde}&page=19", wait_until="load")
            page.wait_for_function("window.PROTO && window.PROTO.pret === true",
                                   timeout=90000)
            avant = page.evaluate(ETAT)
            signature_avant = page.evaluate("window.signatureDesFrontieres()")
            page.evaluate(CURSEUR, [3, 10])
            for _ in range(12):
                page.keyboard.press("Shift+ArrowDown")
            selection = page.evaluate("window.getSelection().toString()")
            gouttiere_dedans = page.evaluate(
                """() => {
                    const t = window.getSelection().toString();
                    return ['#5', '#6', '#7'].filter(x => t.includes(x));
                }""")
            page.keyboard.press("Delete")
            page.wait_for_timeout(400)
            apres = page.evaluate(ETAT)
            sortie[f"{nom}_garde_{garde}"] = {
                "reperes_de_gouttiere_dans_la_selection": gouttiere_dedans,
                "gouttieres_avant_apres": [avant["gouttieres"], apres["gouttieres"]],
                "textes_de_gouttiere_INTACTS": avant["textes"] == apres["textes"],
                "blocs_avant_apres": [avant["blocs"], apres["blocs"]],
                "frontieres_identiques": (
                    signature_avant == page.evaluate("window.signatureDesFrontieres()")),
            }
            page.close()
        n.close()
print("@@@JSON@@@")
print(json.dumps(sortie, ensure_ascii=False, indent=1))
