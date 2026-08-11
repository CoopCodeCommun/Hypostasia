from playwright.sync_api import sync_playwright

verdicts = []
def verifier(nom, condition, detail=""):
    verdicts.append((nom, bool(condition), detail))

with sync_playwright() as p:
    nav = p.chromium.launch()
    page = nav.new_page(viewport={'width':1500,'height':1000})
    erreurs = []
    page.on('pageerror', lambda e: erreurs.append(str(e)))
    page.on('console', lambda m: erreurs.append(m.text) if m.type == 'error' else None)

    page.goto('file:///app/tmp/maquettes/corpus.html', wait_until='networkidle')
    verifier("carnet chargé", page.locator('#liste-notes .ligne-note').count() == 5)
    verifier("guide de rédaction affiché", page.locator('#guide-redaction:visible').count() == 1)

    page.click('#fil-carnet'); page.wait_for_timeout(250)
    verifier("fil : menu de bascule", page.locator('#menu-bascule button').count() == 4)
    page.locator('#menu-bascule button[data-carnet="c-communs"]').click(); page.wait_for_timeout(350)
    verifier("fil : bascule de carnet", page.locator('#titre-carnet').inner_text() == "Communs et gouvernance")
    page.click('#fil-carnet'); page.locator('#menu-bascule button[data-carnet="c-ca"]').click(); page.wait_for_timeout(350)

    F = '#facettes-carnet .puce-categorie[data-categorie="%s"]'
    page.locator(F % 'th-gouv').click(); page.wait_for_timeout(200)
    n1 = page.locator('#liste-notes .ligne-note').count()
    page.locator(F % 'e-tri').click(); page.wait_for_timeout(200)
    n2 = page.locator('#liste-notes .ligne-note').count()
    page.locator(F % 'e-passe').click(); page.wait_for_timeout(200)
    n3 = page.locator('#liste-notes .ligne-note').count()
    verifier("facettes : ET entre axes", n2 < n1, "%d->%d" % (n1, n2))
    verifier("facettes : OU dans un axe", n3 > n2, "%d->%d" % (n2, n3))
    page.click('#vider-filtres'); page.wait_for_timeout(200)
    titres_avant = page.locator('#liste-notes .titre-note').all_inner_texts()
    page.locator('#liste-notes .ligne-note').nth(2).locator('.monter').click(); page.wait_for_timeout(250)
    titres_apres = page.locator('#liste-notes .titre-note').all_inner_texts()
    verifier("ordre manuel : la note remonte d'un rang",
             titres_apres[1] == titres_avant[2] and titres_apres[2] == titres_avant[1],
             str(titres_avant[:3]) + ' -> ' + str(titres_apres[:3]))

    page.click('button[data-onglet="wikis"]'); page.wait_for_timeout(250)
    page.locator('#liste-wikis .ligne-note').first.click(); page.wait_for_timeout(350)
    verifier("wiki : sections", page.locator('#article-wiki h2').count() == 4)
    etats = page.locator('.affirmation').evaluate_all('ns=>ns.map(n=>n.dataset.verification)')
    verifier("wiki : trois états de vérification",
             set(etats) == {'verifie','faible','non_source'}, str(sorted(set(etats))))
    verifier("wiki : renvois numérotés", page.locator('#article-wiki .renvoi').count() >= 12)

    page.locator('#article-wiki .renvoi').first.click(); page.wait_for_timeout(300)
    verifier("sourcing : panneau de preuve", page.locator('#panneau-preuve.est-ouvert').count() == 1)
    verifier("sourcing : citation exacte", page.locator('#corps-preuve .citation-exacte').count() >= 1)
    verifier("sourcing : le débat est joint", page.locator('#corps-preuve .debat').count() >= 1)
    # Une note non maquettée le DIT au lieu d'offrir un lien mort.
    verifier("sourcing : note non maquettée signalée",
             'non maquettée' in page.locator('#corps-preuve').inner_text())
    # Et une note maquettée offre bien son lien.
    trouve = False
    for i in range(page.locator('#article-wiki .renvoi').count()):
        page.locator('#article-wiki .renvoi').nth(i).click(); page.wait_for_timeout(120)
        if page.locator('#corps-preuve a[href*="extraction="]').count():
            trouve = True
            break
    verifier("sourcing : lien vers la note maquettée", trouve)

    page.locator('.affirmation[data-sources*=","]').first.click(); page.wait_for_timeout(300)
    verifier("multi-sources : deux preuves", page.locator('#corps-preuve .carte-preuve').count() == 2)
    page.locator('.affirmation[data-verification="non_source"]').first.click(); page.wait_for_timeout(300)
    verifier("non sourcé : état affiché", page.locator('#corps-preuve .etat-verification').count() == 1)

    page.locator('.ecarte:visible summary').click(); page.wait_for_timeout(250)
    # « écartées » est une DIFFERENCE D'ENSEMBLES : on ne verifie pas un
    # nombre fige, on verifie l'invariant — perimetre moins citees.
    # / Verify the invariant, not a frozen count.
    annonce = int(page.locator('.ecarte:visible summary').inner_text().split()[0])
    cartes = page.locator('.ecarte:visible .carte-preuve').count()
    perimetre = page.evaluate('extractionsDuPerimetreDeLArticle(articleOuvert).length')
    cites = page.evaluate('identifiantsCitesParLArticle(articleOuvert).length')
    verifier("écartées = périmètre − citées",
             cartes == annonce == perimetre - cites,
             "annonce=%d cartes=%d perimetre=%d cites=%d" % (annonce, cartes, perimetre, cites))

    page.locator(".js-maj-wiki:visible").click(); page.wait_for_timeout(350)
    verifier("section_ops : 4 opérations", page.locator('#diff-operations .operation').count() == 4)
    verifier("section_ops : rejet mécanique", page.locator('.operation.rejetee').count() == 1)
    page.click('#diff-accepter'); page.wait_for_timeout(500)
    verifier("section_ops : tour incrémenté",
             '5' in page.locator('#article-wiki .entete-article .ligne').nth(2).inner_text())

    page.click('button[data-onglet="syntheses"]'); page.wait_for_timeout(250)
    page.locator('#liste-syntheses .ligne-note').first.click(); page.wait_for_timeout(300)
    verifier("synthèse figée : bouton MAJ désactivé",
             page.locator('#article-synthese .rangee-boutons button').nth(1).is_disabled())
    page.locator(".js-retour-liste:visible").click(); page.wait_for_timeout(250)
    page.click('#btn-nouvelle-synthese'); page.wait_for_timeout(300)
    verifier("synthèse : directions par axe", page.locator('#synth-axe option').count() == 11)
    # Le garde-fou doit etre EXERCE, pas seulement annonce : le carnet
    # contient 4 syntheses, elles ne doivent pas entrer dans la portee.
    portee = page.locator('#synth-portee').inner_text()
    nombre_de_notes = int(portee.split('Portée : ')[1].split(' notes')[0])
    verifier("garde-fou : les synthèses sont hors du corpus source",
             nombre_de_notes == 5, "portée = %d notes, attendu 5" % nombre_de_notes)
    verifier("garde-fou : la règle est dite à l'utilisateur",
             'exclus du corpus source' in page.locator('#synth-recap').inner_text())
    page.click('#synth-lancer'); page.wait_for_timeout(400)

    page.click('button[data-onglet="alignement"]'); page.wait_for_timeout(400)
    avant = page.locator('#tableau-alignement thead th').count()
    page.locator('#facettes-alignement .puce-categorie[data-categorie="th-budget"]').click(); page.wait_for_timeout(350)
    apres = page.locator('#tableau-alignement thead th').count()
    verifier("alignement suit les facettes", apres < avant, "%d->%d" % (avant, apres))
    verifier("alignement groupé par famille", page.locator('.bandeau-famille').count() >= 1)

    page.goto('file:///app/tmp/maquettes/maquette.html', wait_until='networkidle'); page.wait_for_timeout(300)
    verifier("bloc « Dans N carnets »", page.locator('#bloc-carnets li').count() == 2)
    etiquettes = [li.inner_text() for li in page.locator('#bloc-carnets li').all()]
    verifier("étiquettes différentes selon le carnet",
             'Budget' in etiquettes[0] and 'Subvention' in etiquettes[1])
    page.click('#fil-carnet'); page.wait_for_timeout(200)
    page.locator('#menu-bascule button[data-carnet="c-veille"]').click(); page.wait_for_timeout(300)
    verifier("note : bascule de carnet", page.locator('#fil-carnet-nom').inner_text() == "Veille financement")

    page.goto('file:///app/tmp/maquettes/maquette.html?extraction=604', wait_until='networkidle')
    page.wait_for_timeout(1500)
    verifier("deep-link : bonne source", page.locator('#choix-source').input_value() == 'audio')
    verifier("deep-link : passage allumé", page.locator('mark.est-active').count() >= 1)
    verifier("deep-link : carte active", page.locator('.carte.est-active').count() >= 1)
    # Aucun lien de preuve ne doit pointer vers une note absente
    page.goto('file:///app/tmp/maquettes/corpus.html', wait_until='networkidle')
    page.click('button[data-onglet="wikis"]'); page.wait_for_timeout(250)
    page.locator('#liste-wikis .ligne-note').first.click(); page.wait_for_timeout(350)
    liens_morts = []
    nombre = page.locator('#article-wiki .renvoi').count()
    for i in range(nombre):
        page.locator('#article-wiki .renvoi').nth(i).click(); page.wait_for_timeout(120)
        for a in page.locator('#corps-preuve a[href*="extraction="]').all():
            liens_morts.append(a.get_attribute('href'))
    page2 = nav.new_page()
    casses = []
    for href in set(liens_morts):
        page2.goto('file:///app/tmp/maquettes/' + href, wait_until='networkidle')
        page2.wait_for_timeout(900)
        if page2.locator('mark.est-active').count() == 0:
            casses.append(href)
    page2.close()
    verifier("tous les liens de preuve aboutissent", not casses, str(casses[:3]))

    # Etalon : chaque citation doit se retrouver dans le texte de son
    # element, sinon l'ancrage affiche serait faux.
    page.goto('file:///app/tmp/maquettes/corpus.html', wait_until='networkidle')
    page.wait_for_timeout(300)
    introuvables = page.evaluate(
        'catalogueDesExtractions().filter(function(e){return e.debut === -1;})'
        '.map(function(e){return e.id;})')
    verifier("tous les ancrages sont retrouvés dans le texte",
             not introuvables, str(introuvables))
    # Et la couverture doit etre la jointure qu'elle pretend etre.
    page.goto('file:///app/tmp/maquettes/selection-preuves.html', wait_until='networkidle')
    page.wait_for_timeout(300)
    ecarts = page.evaluate('''Object.keys(DOCUMENTS).filter(function (cle) {
        var c = couvertureDuDocument(cle);
        var reels = (DOCUMENTS[cle].elements || [])
          .filter(function (e) { return (e.idees || []).length; }).length;
        return c.couverts !== reels;
      })''')
    verifier("la couverture est une vraie jointure", not ecarts, str(ecarts))

    verifier("aucune erreur console", not erreurs, str(erreurs[:1]))
    nav.close()

reussis = sum(1 for _, ok, _ in verdicts if ok)
for nom, ok, detail in verdicts:
    print(('  OK   ' if ok else ' ECHEC ') + nom + (('   ' + detail) if detail and not ok else ''))
print()
print("=== %d/%d verifications passees ===" % (reussis, len(verdicts)))
