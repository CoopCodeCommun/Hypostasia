"""
L'API de l'extension navigateur : perimetre, carnets, capture ciblee.
/ The browser extension API: scope, notebooks, targeted capture.

LOCALISATION : core/tests/test_extension_api.py

Ce fichier est celui que SPEC-corpus-base-carnet-note.md § 9 annonce et
qui n'avait jamais ete ecrit. Il couvre les quatre endpoints que
l'extension appelle, et les trois regles qui les gouvernent :

1. LE PERIMETRE. `GET /api/pages/` rendait `Page.objects.all()` a
   n'importe qui, sans jeton, avec le HTML complet de chaque note.
   Il exige desormais un jeton et ne rend que les notes que le porteur
   peut lire.
2. LE DROIT D'ECRITURE. La liste des carnets proposes a la capture est
   celle des carnets ou l'utilisateur peut ECRIRE — partages par groupe
   compris, ce que `_ids_dossiers_accessibles` oubliait.
3. LE CARNET CHOISI. La capture part directement dans le carnet demande.
   Un carnet ou l'on ne peut pas ecrire est REFUSE, jamais remplace en
   silence par le fourre-tout : l'utilisateur a designe une destination,
   en changer sans le dire est un mensonge.

/ Covers the four endpoints the extension calls and the three rules that
govern them: read scope, write permission, and the chosen notebook.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.authtoken.models import Token

from core.models import (
    Dossier,
    DossierPartage,
    GroupeUtilisateurs,
    Page,
    VisibiliteDossier,
)
from core.services.corpus import (
    carnets_ou_ecrire,
    ranger_une_note_dans_un_carnet,
)

Utilisateur = get_user_model()

# La tache Docling part a chaque capture reussie. On la remplace partout
# ou un test cree vraiment une page : le broker n'a rien a faire ici.
# / The Docling task fires on every successful capture; stubbed out.
CHEMIN_DE_LA_TACHE = (
    "hypostasis_extractor.tasks_element"
    ".ingerer_une_capture_web_avec_docling.delay"
)


def creer_une_note(url_unique, owner=None, titre="Une note"):
    """Une note minimale, avec du HTML a ne pas laisser fuir.
    / A minimal note, carrying HTML that must not leak."""
    return Page.objects.create(
        url=url_unique,
        title=titre,
        html_original=f"<html><body><p>original de {url_unique}</p></body></html>",
        html_readability=f"<p>lisible de {url_unique}</p>",
        text_readability=f"texte de {url_unique}",
        content_hash=f"hash-{url_unique}",
        owner=owner,
    )


def jeton_de(utilisateur):
    """Le jeton d'API d'un utilisateur. / A user's API token."""
    return Token.objects.create(user=utilisateur).key


class ListeDesPagesFermeeTest(TestCase):
    """
    `GET /api/pages/` exige un jeton et reste dans le perimetre du
    porteur. / The page list needs a token and stays in scope.
    """

    def setUp(self):
        self.capteur = Utilisateur.objects.create_user(
            username="capteur_perimetre", password="motdepasse",
        )
        self.inconnu = Utilisateur.objects.create_user(
            username="inconnu_perimetre", password="motdepasse",
        )
        self.jeton = jeton_de(self.capteur)

        # Une note a moi, dans mon carnet prive.
        # / A note of mine, in my private notebook.
        self.mon_carnet = Dossier.objects.create(
            name="Mon carnet", owner=self.capteur,
        )
        self.ma_note = creer_une_note(
            "http://exemple.local/ma-note", owner=self.capteur,
        )
        ranger_une_note_dans_un_carnet(self.ma_note, self.mon_carnet, self.capteur)

        # Une note d'un inconnu, dans SON carnet prive.
        # / Someone else's note, in THEIR private notebook.
        self.carnet_de_l_inconnu = Dossier.objects.create(
            name="Carnet prive d'un inconnu", owner=self.inconnu,
        )
        self.note_de_l_inconnu = creer_une_note(
            "http://exemple.local/note-privee-d-un-autre", owner=self.inconnu,
        )
        ranger_une_note_dans_un_carnet(
            self.note_de_l_inconnu, self.carnet_de_l_inconnu, self.inconnu,
        )

    def test_sans_jeton_la_liste_est_refusee(self):
        """
        C'EST LA FUITE QUE CE TEST FERME. Mesure du 20 aout 2026 avant
        correction : 200, 13 pages, 291 840 octets, sans le moindre
        en-tete d'authentification et depuis n'importe quelle origine
        (CORS_ALLOW_ALL_ORIGINS).
        / This closes the measured leak.
        """
        reponse = self.client.get("/api/pages/")
        self.assertEqual(reponse.status_code, 401)

    def test_avec_jeton_je_ne_vois_que_mon_perimetre(self):
        reponse = self.client.get(
            "/api/pages/", HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        self.assertEqual(reponse.status_code, 200)

        identifiants_rendus = {note["id"] for note in reponse.json()}
        self.assertIn(self.ma_note.pk, identifiants_rendus)
        self.assertNotIn(self.note_de_l_inconnu.pk, identifiants_rendus)

    def test_la_liste_ne_livre_plus_le_contenu_des_notes(self):
        """
        Le pre-check de doublon n'a besoin que de l'identifiant et de
        l'URL. Livrer le texte et le HTML de chaque note pour repondre
        « existe / n'existe pas » est disproportionne.
        / The dedup pre-check only needs the id and the URL.
        """
        reponse = self.client.get(
            "/api/pages/", HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        premiere_note = reponse.json()[0]

        for champ_de_contenu in (
            "html_original", "html_readability", "text_readability",
        ):
            self.assertNotIn(champ_de_contenu, premiere_note)

        # Ce dont l'extension se sert reste la. / What the extension uses stays.
        for champ_attendu in ("id", "url", "title"):
            self.assertIn(champ_attendu, premiere_note)

    def test_le_filtre_par_url_reste_dans_le_perimetre(self):
        """
        Le pre-check ne doit pas repondre « deja enregistree » en
        montrant la note d'un inconnu, que le porteur ne peut pas ouvrir.
        / The pre-check must not answer with a stranger's note.
        """
        reponse = self.client.get(
            "/api/pages/",
            {"url": self.note_de_l_inconnu.url},
            HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json(), [])

    def test_une_note_orpheline_sans_proprietaire_reste_lisible(self):
        """
        CAS LEGACY, PRESERVE TEL QUEL. Une note sans aucun carnet et
        sans proprietaire reste lisible par tout authentifie
        (SPEC-corpus § 5.2, correction n°6 : la v1.0 de la spec les
        rendait invisibles pour tous).
        / Legacy: ownerless, notebook-less notes stay readable.
        """
        note_orpheline = creer_une_note(
            "http://exemple.local/orpheline-sans-owner", owner=None,
        )
        reponse = self.client.get(
            "/api/pages/", HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        identifiants_rendus = {note["id"] for note in reponse.json()}
        self.assertIn(note_orpheline.pk, identifiants_rendus)

    def test_une_note_orpheline_d_un_autre_reste_privee(self):
        """
        Sans carnet mais AVEC un proprietaire : elle suit son
        proprietaire, et lui seul.
        / No notebook but an owner: it follows its owner alone.
        """
        note_de_l_autre = creer_une_note(
            "http://exemple.local/orpheline-d-un-autre", owner=self.inconnu,
        )
        reponse = self.client.get(
            "/api/pages/", HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        identifiants_rendus = {note["id"] for note in reponse.json()}
        self.assertNotIn(note_de_l_autre.pk, identifiants_rendus)

    def test_une_note_d_un_carnet_public_reste_visible(self):
        """
        Ranger dans un carnet public rend public : le perimetre de
        lecture le dit aussi ici. / Filing in a public notebook publishes.
        """
        carnet_public = Dossier.objects.create(
            name="Carnet public", owner=self.inconnu,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        note_publique = creer_une_note(
            "http://exemple.local/note-publique", owner=self.inconnu,
        )
        ranger_une_note_dans_un_carnet(note_publique, carnet_public, self.inconnu)

        reponse = self.client.get(
            "/api/pages/", HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        identifiants_rendus = {note["id"] for note in reponse.json()}
        self.assertIn(note_publique.pk, identifiants_rendus)


class SidebarFermeeTest(TestCase):
    """
    `GET /api/sidebar/` ne renseigne plus un inconnu sur le contenu de
    l'instance. / The sidebar endpoint no longer informs a stranger.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio_sidebar", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet sidebar", owner=self.proprietaire,
        )
        self.note = creer_une_note(
            "http://exemple.local/note-sidebar", owner=self.proprietaire,
            titre="Titre confidentiel de la note",
        )
        ranger_une_note_dans_un_carnet(self.note, self.carnet, self.proprietaire)

    def test_un_anonyme_ne_distingue_pas_l_absente_de_l_interdite(self):
        """
        Doctrine du 404, jamais 403 : la meme reponse pour « rien ici »
        et pour « pas pour toi ». / Same answer for absent and forbidden.
        """
        reponse_sur_la_note = self.client.get(
            "/api/sidebar/", {"url": self.note.url},
        )
        reponse_sur_une_url_inconnue = self.client.get(
            "/api/sidebar/", {"url": "http://exemple.local/rien-du-tout"},
        )

        self.assertNotContains(
            reponse_sur_la_note, "Titre confidentiel de la note",
        )
        self.assertEqual(
            reponse_sur_la_note.status_code,
            reponse_sur_une_url_inconnue.status_code,
        )

    def test_le_proprietaire_voit_sa_note(self):
        jeton = jeton_de(self.proprietaire)
        reponse = self.client.get(
            "/api/sidebar/", {"url": self.note.url},
            HTTP_AUTHORIZATION=f"Token {jeton}",
        )
        self.assertEqual(reponse.status_code, 200)


class CarnetsOuEcrireTest(TestCase):
    """
    Le service qui dit ou l'on peut ecrire. C'est la version queryset de
    `_utilisateur_peut_ecrire_dossier`, et sa seule source.
    / The service that says where one may write.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="ecrivain_carnets", password="motdepasse",
        )
        self.autre = Utilisateur.objects.create_user(
            username="autre_carnets", password="motdepasse",
        )

    def test_mon_carnet_est_inscriptible(self):
        mon_carnet = Dossier.objects.create(
            name="Le mien", owner=self.utilisateur,
        )
        self.assertIn(mon_carnet, carnets_ou_ecrire(self.utilisateur))

    def test_le_partage_direct_est_inscriptible(self):
        carnet_partage = Dossier.objects.create(
            name="Partage avec moi", owner=self.autre,
        )
        DossierPartage.objects.create(
            dossier=carnet_partage, utilisateur=self.utilisateur,
        )
        self.assertIn(carnet_partage, carnets_ou_ecrire(self.utilisateur))

    def test_le_partage_par_groupe_est_inscriptible(self):
        """
        LE BUG QUE CE TEST FERME. `_ids_dossiers_accessibles`
        (core/views.py) ne filtrait que `DossierPartage.utilisateur` :
        un membre d'un groupe a qui l'on avait partage un carnet ne le
        voyait pas dans l'extension, alors que le front le lui montrait.
        / The group-share blind spot of the extension API.
        """
        groupe = GroupeUtilisateurs.objects.create(
            nom="Groupe de travail", owner=self.autre,
        )
        groupe.membres.add(self.utilisateur)
        carnet_du_groupe = Dossier.objects.create(
            name="Carnet du groupe", owner=self.autre,
        )
        DossierPartage.objects.create(dossier=carnet_du_groupe, groupe=groupe)

        self.assertIn(carnet_du_groupe, carnets_ou_ecrire(self.utilisateur))

    def test_un_carnet_public_d_un_autre_n_est_pas_inscriptible(self):
        """
        Public veut dire LISIBLE par tous, pas inscriptible par tous.
        / Public means readable by all, not writable by all.
        """
        carnet_public = Dossier.objects.create(
            name="Public mais pas a moi", owner=self.autre,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.assertNotIn(carnet_public, carnets_ou_ecrire(self.utilisateur))

    def test_un_carnet_prive_d_un_autre_n_est_pas_inscriptible(self):
        carnet_prive = Dossier.objects.create(
            name="Prive d'un autre", owner=self.autre,
        )
        self.assertNotIn(carnet_prive, carnets_ou_ecrire(self.utilisateur))

    def test_un_anonyme_n_ecrit_nulle_part(self):
        Dossier.objects.create(name="Un carnet", owner=self.autre)
        self.assertEqual(list(carnets_ou_ecrire(AnonymousUser())), [])


class MesCarnetsTest(TestCase):
    """
    `GET /api/pages/mes_carnets/` — ce que la popup met dans son menu.
    / What the popup puts in its dropdown.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="popup_carnets", password="motdepasse",
        )
        self.autre = Utilisateur.objects.create_user(
            username="popup_autre", password="motdepasse",
        )
        self.jeton = jeton_de(self.utilisateur)

    def test_sans_jeton_c_est_refuse(self):
        reponse = self.client.get("/api/pages/mes_carnets/")
        self.assertEqual(reponse.status_code, 401)

    def test_rend_le_nom_le_role_et_la_visibilite(self):
        Dossier.objects.create(name="Conseil", owner=self.utilisateur)
        reponse = self.client.get(
            "/api/pages/mes_carnets/",
            HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        self.assertEqual(reponse.status_code, 200)

        carnet_rendu = reponse.json()[0]
        self.assertEqual(carnet_rendu["nom"], "Conseil")
        self.assertEqual(carnet_rendu["role_special"], "")
        self.assertEqual(carnet_rendu["visibilite"], VisibiliteDossier.PRIVE)
        self.assertIs(carnet_rendu["est_public"], False)

    def test_le_carnet_public_est_signale_comme_tel(self):
        """
        La popup doit avertir AU MOMENT DU GESTE qu'un carnet publie la
        note (spec § 7.3). Elle a donc besoin du drapeau.
        / The popup warns at gesture time; it needs the flag.
        """
        Dossier.objects.create(
            name="Carnet ouvert", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        reponse = self.client.get(
            "/api/pages/mes_carnets/",
            HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        self.assertIs(reponse.json()[0]["est_public"], True)

    def test_le_carnet_partage_par_groupe_est_propose(self):
        groupe = GroupeUtilisateurs.objects.create(
            nom="Groupe popup", owner=self.autre,
        )
        groupe.membres.add(self.utilisateur)
        carnet_du_groupe = Dossier.objects.create(
            name="Carnet du groupe popup", owner=self.autre,
        )
        DossierPartage.objects.create(dossier=carnet_du_groupe, groupe=groupe)

        reponse = self.client.get(
            "/api/pages/mes_carnets/",
            HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        noms_proposes = [carnet["nom"] for carnet in reponse.json()]
        self.assertIn("Carnet du groupe popup", noms_proposes)

    def test_un_carnet_public_d_un_autre_n_est_pas_propose(self):
        Dossier.objects.create(
            name="Public d'un autre", owner=self.autre,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        reponse = self.client.get(
            "/api/pages/mes_carnets/",
            HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        self.assertEqual(reponse.json(), [])

    def test_aucun_carnet_n_est_jamais_cree_par_l_api(self):
        """
        AUCUNE LECTURE, AUCUNE CAPTURE NE CREE DE CARNET. Le carnet
        « A ranger » naissait tout seul a la premiere capture sans
        destination. Il a disparu le 21 aout 2026 : une note appartient
        toujours a un carnet, et ce carnet est cree par quelqu'un.
        / Nothing creates a notebook any more: the inbox that appeared
        on first destination-less capture is gone.
        """
        self.client.get(
            "/api/pages/mes_carnets/",
            HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        self.assertFalse(Dossier.objects.filter(owner=self.utilisateur).exists())


class CaptureVersUnCarnetChoisiTest(TestCase):
    """
    `POST /api/pages/` porte le carnet des la creation.
    / The capture carries its notebook from creation.
    """

    def setUp(self):
        self.capteur = Utilisateur.objects.create_user(
            username="capteur_choix", password="motdepasse",
        )
        self.autre = Utilisateur.objects.create_user(
            username="autre_choix", password="motdepasse",
        )
        self.jeton = jeton_de(self.capteur)
        self.mon_carnet = Dossier.objects.create(
            name="Veille financement", owner=self.capteur,
        )

    def _capturer(self, url="http://exemple.local/article-a-capturer", **extra):
        donnees = {
            "url": url,
            "title": "Un article",
            "html_original": "<html><body><p>Corps.</p></body></html>",
            "html_readability": "<p>Corps.</p>",
        }
        donnees.update(extra)
        return self.client.post(
            "/api/pages/", donnees, content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )

    @mock.patch(CHEMIN_DE_LA_TACHE)
    def test_la_capture_va_dans_le_carnet_demande(self, _tache):
        reponse = self._capturer(dossier_id=self.mon_carnet.pk)
        self.assertEqual(reponse.status_code, 201)

        note_creee = Page.objects.get(pk=reponse.json()["id"])
        carnets_de_la_note = [
            appartenance.dossier
            for appartenance in note_creee.appartenances_dossiers.all()
        ]
        self.assertEqual(carnets_de_la_note, [self.mon_carnet])

        # Elle n'a PAS transite par le fourre-tout, qui n'a donc pas
        # ete cree. / It never went through the inbox.
        # Le capteur possede UN carnet, celui du setUp. Aucun autre
        # n'a ete fabrique au passage.
        # / The capturer owns ONE notebook, from setUp; no other was made.
        self.assertEqual(Dossier.objects.filter(owner=self.capteur).count(), 1)

    @mock.patch(CHEMIN_DE_LA_TACHE)
    def test_sans_carnet_la_capture_est_refusee(self, _tache):
        """
        CE TEST DISAIT L'INVERSE JUSQU'AU 21 AOUT 2026. Il s'appelait
        « tombe dans le fourre-tout » et verrouillait la creation
        automatique du carnet « A ranger ».

        UNE NOTE APPARTIENT TOUJOURS A UN CARNET, et ce carnet est choisi
        par quelqu'un. Une destination inventee par le code n'en est pas
        une : elle rendait normal le fait de ne rien choisir, et le
        carnet ainsi cree ne se vidait jamais.
        / This test asserted the opposite: it locked the automatic
        creation of the inbox notebook.
        """
        reponse = self._capturer()

        self.assertEqual(reponse.status_code, 400)
        self.assertIn("dossier_id", reponse.json())
        self.assertFalse(
            Page.objects.filter(
                url="http://exemple.local/article-a-capturer",
            ).exists()
        )
        # Et surtout : aucun carnet n'a ete fabrique au passage — le
        # capteur en a toujours exactement un, celui du setUp.
        # / And above all: no notebook was manufactured on the way.
        self.assertEqual(Dossier.objects.filter(owner=self.capteur).count(), 1)

    @mock.patch(CHEMIN_DE_LA_TACHE)
    def test_un_carnet_non_inscriptible_est_refuse(self, _tache):
        """
        AVANT : le carnet refuse etait remplace en SILENCE par « A
        ranger », et l'extension annoncait un succes. L'utilisateur
        croyait avoir range dans le carnet de classe ; la note etait
        ailleurs. Un choix explicite se refuse, il ne se detourne pas.
        / Before: a refused notebook was silently swapped for the inbox.
        """
        carnet_interdit = Dossier.objects.create(
            name="Carnet d'un autre", owner=self.autre,
        )
        reponse = self._capturer(dossier_id=carnet_interdit.pk)

        self.assertEqual(reponse.status_code, 400)
        self.assertFalse(
            Page.objects.filter(
                url="http://exemple.local/article-a-capturer",
            ).exists()
        )

    @mock.patch(CHEMIN_DE_LA_TACHE)
    def test_un_carnet_inexistant_est_refuse(self, _tache):
        reponse = self._capturer(dossier_id=999999)
        self.assertEqual(reponse.status_code, 400)

    @mock.patch(CHEMIN_DE_LA_TACHE)
    def test_un_dossier_id_qui_n_est_pas_un_entier_rend_400(self, _tache):
        """
        Le `dossier_id` passe par le serializer, jamais par le payload
        brut. Lu du brut, il arrivait tel quel dans un `filter(pk=...)`
        qui leve une `ValueError` sur une chaine — c'est-a-dire un 500
        pour une faute de frappe du client.
        / Validated by the serializer: a raw string pk raises ValueError
        deep in the ORM, i.e. a 500 for a client typo.
        """
        reponse = self._capturer(dossier_id="pas-un-entier")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("dossier_id", reponse.json())


class UrlDejaPriseAilleursTest(TestCase):
    """
    `Page.url` est unique GLOBALEMENT (`unique_url_si_presente`) alors
    que la dedup est scopee par utilisateur. Quand un tiers a deja
    capture l'URL, la reponse doit etre lisible.
    / The URL is globally unique while dedup is per-user: say so plainly.
    """

    def setUp(self):
        self.capteur = Utilisateur.objects.create_user(
            username="capteur_url_prise", password="motdepasse",
        )
        self.tiers = Utilisateur.objects.create_user(
            username="tiers_url_prise", password="motdepasse",
        )
        self.jeton = jeton_de(self.capteur)

        carnet_du_tiers = Dossier.objects.create(
            name="Carnet du tiers", owner=self.tiers,
        )
        note_du_tiers = creer_une_note(
            "http://exemple.local/deja-prise", owner=self.tiers,
        )
        ranger_une_note_dans_un_carnet(
            note_du_tiers, carnet_du_tiers, self.tiers,
        )

    @mock.patch(CHEMIN_DE_LA_TACHE)
    def test_l_url_prise_par_un_tiers_rend_409_avec_un_code(self, _tache):
        """
        AVANT : 400 `{"url": ["Un objet page avec ce champ url existe
        deja."]}` que la popup affichait « Erreur creation (400) ». Le
        code machine permet un message honnete.
        / A machine-readable code, so the popup can say what happened.
        """
        reponse = self.client.post(
            "/api/pages/",
            {
                "url": "http://exemple.local/deja-prise",
                "title": "Ma capture a moi",
                "html_original": "<html><body><p>Autre corps.</p></body></html>",
                "html_readability": "<p>Autre corps.</p>",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(reponse.json()["code"], "url_prise_ailleurs")


class EmpreinteCalculeeParLeServeurTest(TestCase):
    """
    Le `content_hash` a une seule implementation, cote serveur.
    / The content hash has a single implementation, server-side.
    """

    def setUp(self):
        self.capteur = Utilisateur.objects.create_user(
            username="capteur_empreinte", password="motdepasse",
        )
        self.jeton = jeton_de(self.capteur)
        # Une capture exige un carnet depuis le 21 aout 2026 : il n'y a
        # plus de destination par defaut.
        # / A capture requires a notebook: there is no default any more.
        self.carnet = Dossier.objects.create(
            name="Carnet empreinte", owner=self.capteur,
        )

    @mock.patch(CHEMIN_DE_LA_TACHE)
    def test_une_empreinte_soumise_est_ignoree(self, _tache):
        """
        L'extension hachait `body.textContent` sans `.strip()`, le
        serveur hachait `extraire_texte_depuis_html()` AVEC. Deux
        implementations d'une meme empreinte : mesure du 20 aout 2026,
        2 pages sur 10 donnaient deux valeurs differentes, et le 409 par
        contenu ne se declenchait donc pas. On supprime la cause : le
        serveur seul calcule.
        / Two implementations of one hash; the cause is removed.
        """
        reponse = self.client.post(
            "/api/pages/",
            {
                "url": "http://exemple.local/empreinte",
                "title": "Empreinte",
                "html_original": "<html><body><p>Corps.</p></body></html>",
                "html_readability": "<p>Corps.</p>",
                "content_hash": "empreinte-fantaisiste-envoyee-par-le-client",
                "dossier_id": self.carnet.pk,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.jeton}",
        )
        self.assertEqual(reponse.status_code, 201)

        note_creee = Page.objects.get(pk=reponse.json()["id"])
        self.assertNotEqual(
            note_creee.content_hash,
            "empreinte-fantaisiste-envoyee-par-le-client",
        )
        self.assertEqual(len(note_creee.content_hash), 64)
