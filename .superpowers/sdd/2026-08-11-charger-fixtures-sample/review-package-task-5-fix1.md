### DIFF DU FIX (round 1, tache 5)

--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task5-commande.py	2026-08-11 17:04:02.547989827 +0200
+++ front/management/commands/charger_fixtures_sample.py	2026-08-11 17:07:47.902087285 +0200
@@ -429,6 +429,30 @@
         HTML reel : section_header, list_item, text. Les pages « Wikipedia »
         de charger_fixtures_demo n'ont que des <p> et sortent toutes en
         `text`. / The only fixture exercising real HTML structure labels.
+
+        C'EST AUSSI LA SEULE DES QUATRE A VERIFIER UNE CONTRAINTE GLOBALE
+        AVANT DE CREER.
+
+        Elle est la seule des quatre fixtures a porter une `url` : le
+        markdown, la transcription JSON et le mp3 la creent a `None`. Or
+        `unique_url_si_presente` (core/models.py:321-325) est une
+        contrainte GLOBALE sur `url`, non scopee par carnet ni par
+        proprietaire — sa condition `url__isnull=False` exempte les trois
+        autres, qui n'ont donc pas besoin de ce garde. Ne pas « harmoniser »
+        les quatre methodes par symetrie : les trois autres n'ont rien a
+        verifier.
+        / Only this one carries a `url`; the other three create it as
+        None and are exempted by the constraint's `url__isnull=False`
+        condition. Do not "harmonize" the four loaders by apparent
+        symmetry — the other three have nothing to check.
+
+        Ce garde s'applique a CHAQUE execution, pas seulement apres un
+        --reset : c'est une consequence de la contrainte globale, pas une
+        specificite du reset. --reset est simplement le chemin qui le
+        rend visible en pratique (une page « rangee ailleurs » survit au
+        reset, puis le carnet recree tente de la re-creer).
+        / This guard runs on every execution, not only after --reset —
+        --reset is merely the path that makes the collision reachable.
         """
         # Garde : --fichier peut avoir exclu ce document.
         # / Guard: --fichier may have excluded this document.
@@ -451,7 +475,17 @@
         # unique. --reset may have kept this page elsewhere (also filed
         # in another notebook, so not ours to delete): file it here
         # instead of attempting a duplicate the DB constraint rejects.
-        page_deja_ailleurs = Page.objects.filter(url=URL_DE_LA_CAPTURE).first()
+        #
+        # SCOPE SUR proprietaire : sans ce filtre, la commande peut
+        # trouver la page d'un AUTRE utilisateur et la ranger dans notre
+        # carnet « Documents etalons » — une fuite de perimetre. On ne
+        # touche jamais a une note qui n'est pas a `proprietaire`.
+        # / Scoped to `proprietaire`: without it, a page belonging to a
+        # DIFFERENT user could get filed into our notebook — a scope
+        # leak. We never touch a note that is not the owner's.
+        page_deja_ailleurs = Page.objects.filter(
+            url=URL_DE_LA_CAPTURE, owner=proprietaire,
+        ).first()
         if page_deja_ailleurs is not None:
             ranger_une_note_dans_un_carnet(
                 page_deja_ailleurs, carnet_des_etalons, proprietaire,
@@ -461,6 +495,21 @@
             )
             return page_deja_ailleurs
 
+        # La page peut exister chez QUELQU'UN D'AUTRE : la contrainte
+        # d'unicite empecherait quand meme la creation. On le dit
+        # clairement et on passe, plutot que de laisser l'IntegrityError
+        # remonter en trace de pile. / The page may belong to someone
+        # else: the unique constraint would still block creation. Say so
+        # plainly and move on, instead of surfacing a raw IntegrityError.
+        if Page.objects.filter(url=URL_DE_LA_CAPTURE).exclude(
+            owner=proprietaire,
+        ).exists():
+            self.stdout.write(self.style.WARNING(
+                "Capture web         : une autre note porte déjà cette "
+                "url — capture web non chargée",
+            ))
+            return None
+
         html_capture = (REPERTOIRE_SAMPLE / FICHIER_DE_LA_CAPTURE).read_text(
             encoding="utf-8",
         )

--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task5-tests.py	2026-08-11 17:04:02.549747920 +0200
+++ front/tests/test_charger_fixtures_sample.py	2026-08-11 17:07:59.191995518 +0200
@@ -616,3 +616,22 @@
         # Elle vit ailleurs : on ne l'emporte pas.
         # / It lives elsewhere: not ours to delete.
         self.assertTrue(Page.objects.filter(pk=page_partagee.pk).exists())
+
+    def test_a_blanc_reset_ne_supprime_rien(self):
+        # La verification des ancres tourne AVANT le `if self.a_blanc:
+        # return None` de `_reinitialiser` : rien ne doit disparaitre,
+        # meme sans ancre a proteger. / The anchor check runs before the
+        # dry-run early return: nothing should vanish, anchors or not.
+        self._charger_une_fois()
+        nombre_de_pages_avant = Page.objects.count()
+        carnet_avant = Dossier.objects.get(name="Documents étalons")
+
+        call_command(
+            "charger_fixtures_sample", "--a-blanc", "--reset", "--sans-mp3",
+            stdout=StringIO(),
+        )
+
+        self.assertEqual(Page.objects.count(), nombre_de_pages_avant)
+        self.assertTrue(
+            Dossier.objects.filter(pk=carnet_avant.pk).exists(),
+        )
