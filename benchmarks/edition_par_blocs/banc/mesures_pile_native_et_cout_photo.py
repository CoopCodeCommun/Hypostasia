"""
Deux questions qui decident du dessin de l'annulation.
/ Two questions that decide the undo design.

1. `preventDefault` sur Ctrl+Z suffit-il a EMPECHER l'annulation native ?
   Si le navigateur annule quand meme, la pile applicative et la pile
   native se battent, et l'ordre des annulations devient imprevisible.
2. Que coute une PHOTO de l'etat du champ, et combien pese une pile ?
"""
import json
from playwright.sync_api import sync_playwright

URL = ("https://beta.hypostasia.org/static/front/maquettes/prototype-champ-unique/"
       "index.html?garde=2&ce=plaintext-only&compo=1&page=19")

CURSEUR = """([i, o]) => {
    const champ = document.getElementById('champ'); champ.focus();
    const c = champ.querySelectorAll('.bloc')[i].querySelector('.corps');
    const m = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
    let r = o, n = m.nextNode();
    while (n && r > n.textContent.length) { r -= n.textContent.length; n = m.nextNode(); }
    const p = document.createRange();
    p.setStart(n, Math.min(r, n.textContent.length)); p.collapse(true);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(p);
}"""

sortie = {}
with sync_playwright() as p:
    for nom in ("chromium", "firefox", "webkit"):
        n = getattr(p, nom).launch()
        c = n.new_context(viewport={"width": 1280, "height": 900},
                          ignore_https_errors=True)
        page = c.new_page()
        page.goto(URL, wait_until="load")
        page.wait_for_function("window.PROTO && window.PROTO.pret === true", timeout=90000)
        r = {}

        # --- 1. Ctrl+Z SANS interception : l'annulation native marche-t-elle ? ---
        page.evaluate(CURSEUR, [30, 10])
        page.keyboard.type("AAA")
        page.wait_for_timeout(200)
        avec = page.evaluate("window.serialiser()[30].texte")
        page.keyboard.press("Control+z")
        page.wait_for_timeout(300)
        sans = page.evaluate("window.serialiser()[30].texte")
        r["annulation_native_sans_interception"] = ("AAA" in avec and "AAA" not in sans)

        # --- 2. Ctrl+Z AVEC preventDefault : est-elle bien empechee ? ---
        page.evaluate(
            """() => {
                window.CTRLZ_VUS = 0;
                document.getElementById('champ').addEventListener('keydown', (e) => {
                    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
                        window.CTRLZ_VUS += 1;
                        e.preventDefault();
                    }
                }, true);
            }""")
        page.evaluate(CURSEUR, [31, 10])
        page.keyboard.type("BBB")
        page.wait_for_timeout(200)
        avec2 = page.evaluate("window.serialiser()[31].texte")
        page.keyboard.press("Control+z")
        page.wait_for_timeout(300)
        sans2 = page.evaluate("window.serialiser()[31].texte")
        r["ctrl_z_recu_par_la_page"] = page.evaluate("window.CTRLZ_VUS")
        r["preventDefault_EMPECHE_l_annulation_native"] = (avec2 == sans2 and "BBB" in sans2)

        # --- 3. Ce que coute une PHOTO, et ce qu'elle pese ---
        cout = page.evaluate(
            """() => {
                const photo = () => window.serialiser().map(b => b.texte);
                // Une premiere passe pour chauffer.
                photo();
                const mesures = [];
                for (let i = 0; i < 7; i += 1) {
                    const t = performance.now();
                    const p = photo();
                    mesures.push(performance.now() - t);
                }
                mesures.sort((a, b) => a - b);
                const une = photo();
                return {
                    median_ms: Math.round(mesures[3] * 100) / 100,
                    max_ms: Math.round(mesures[6] * 100) / 100,
                    octets_d_une_photo: new Blob([JSON.stringify(une)]).size,
                    blocs: une.length,
                };
            }""")
        r["cout_d_une_photo"] = cout
        r["poids_de_100_photos_Mo"] = round(cout["octets_d_une_photo"] * 100 / 1048576, 2)
        sortie[nom] = r
        page.close(); n.close()

# La sortie est ECRITE, pas seulement imprimee : un chiffre
# annonce dans un document doit avoir sa source dans le depot.
# / Written, not just printed: every number needs its source.
with open("/tmp/resultats-pile-native-et-cout-photo.json", "w") as _f:
    import json as _json
    _json.dump(sortie, _f, ensure_ascii=False, indent=1)
print("@@@JSON@@@")
print(json.dumps(sortie, ensure_ascii=False, indent=1))
