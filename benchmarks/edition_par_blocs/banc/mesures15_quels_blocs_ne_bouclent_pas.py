"""
MESURE 15 — quels blocs ne survivent PAS a l'aller-retour DOM, et de quel LABEL.
/ Measure 15: which blocks fail the DOM round trip, and of which label.

LOCALISATION : benchmarks/edition_par_blocs/banc/

La mesure 10 comptait les echecs sans dire lesquels : « 8 sur 210 »
n'etablit pas « les 8 table ». Ce banc-ci rend le LABEL de chaque echec,
ce qui tranche la question ouverte du § 12 de la spec — les elements non
textuels sont-ils editables, ou en lecture seule ?

PREALABLE : deux fichiers, ecrits par une requete EN LECTURE SEULE :
    docker exec hypostasia_web python manage.py shell -c "
    import json
    from core.models import ElementDocument
    q = ElementDocument.objects.filter(page_id=19)
    open('/tmp/textes-19.json','w').write(json.dumps(
        {str(e.identifiant_stable): e.texte for e in q}, ensure_ascii=False))
    open('/tmp/labels-19.json','w').write(json.dumps(
        {str(e.identifiant_stable): e.label for e in q}, ensure_ascii=False))
    "
La page 19 est dans un carnet PUBLIC : le banc tourne en anonyme, sans
connexion — donc sans les boutons d'action, qui ne changent rien a cette
mesure-ci (la serialisation les retire de toute facon).
"""
import json
from playwright.sync_api import sync_playwright

ATTENDUS = json.load(open("/tmp/textes-19.json"))
LABELS = json.load(open("/tmp/labels-19.json"))

with sync_playwright() as p:
    n = p.chromium.launch()
    c = n.new_context(viewport={"width": 1400, "height": 1000}, ignore_https_errors=True)
    page = c.new_page()
    page.goto("https://beta.hypostasia.org/lire/19/", wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.evaluate("""() => { const d = document.getElementById('message-d-accueil'); if (d) d.remove(); }""")
    obtenus = page.evaluate(
        """() => {
            const sortie = {};
            document.querySelectorAll('[data-testid=blocs-elements] .bloc[data-element]')
              .forEach((b) => {
                const corps = b.querySelector('.corps');
                const interne = corps ? corps.querySelector('[data-element-id]') : null;
                if (!interne) { sortie[b.dataset.element] = null; return; }
                const copie = interne.cloneNode(true);
                copie.querySelectorAll('.actions-element').forEach((x) => x.remove());
                sortie[b.dataset.element] = copie.textContent;
              });
            return sortie;
        }"""
    )
    page.close(); n.close()

differents = []
for identifiant, attendu in ATTENDUS.items():
    obtenu = obtenus.get(identifiant)
    if obtenu != attendu:
        differents.append({
            "label": LABELS[identifiant],
            "attendu": attendu[:70],
            "obtenu": (obtenu or "")[:70],
        })
from collections import Counter
resultat = {
    "blocs_compares": len(ATTENDUS),
    "exacts": len(ATTENDUS) - len(differents),
    "differents": len(differents),
    "par_label": dict(Counter(d["label"] for d in differents)),
    "exemples": differents[:3],
}
with open("/tmp/resultats-quels-blocs-ne-bouclent-pas.json", "w") as f:
    json.dump(resultat, f, ensure_ascii=False, indent=1)
print("@@@JSON@@@")
print(json.dumps(resultat, ensure_ascii=False, indent=1))
