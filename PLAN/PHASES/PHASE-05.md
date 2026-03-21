# PHASE-05 — Extension navigateur : robustesse

**Complexite** : S | **Mode** : Normal | **Prerequis** : aucun

---

## 1. Contexte

L'extension navigateur actuelle manque de robustesse : pas de deduplication par contenu (seulement par URL), pas de normalisation d'URL, pas d'indicateur de statut serveur, et un endpoint sidebar de test au lieu d'un vrai endpoint de production.

## 2. Prerequis

Aucun. Cette phase est independante.

## 3. Objectifs precis

- [ ] Deduplication par `content_hash` en plus de l'URL (envoyer un hash cote extension, comparer cote serveur)
- [ ] Normaliser l'URL avant comparaison (retirer UTM params, fragment, trailing slash)
- [ ] Afficher un indicateur de statut serveur (online/offline) dans la popup
- [ ] Remplacer `test_sidebar_view` par un vrai endpoint de production

## 4. Fichiers a modifier

- `extension/popup.js` — ajouter le calcul du content hash, la normalisation d'URL, l'indicateur de statut
- `core/views.py` — adapter `PageViewSet.create()` pour verifier le content hash, remplacer `test_sidebar_view`
- `core/serializers.py` — ajouter le champ `content_hash` au serializer

## 5. Criteres de validation

- [ ] Envoyer deux fois la meme page avec des URLs differentes (params UTM) → une seule Page creee
- [ ] Envoyer deux pages avec la meme URL mais du contenu different → deux Pages creees
- [ ] La popup affiche un indicateur vert/rouge selon que le serveur repond ou non
- [ ] L'endpoint `test_sidebar_view` est remplace par un endpoint propre
- [ ] `uv run python manage.py check` passe sans erreur

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir le popup de l'extension avec le serveur eteint** : cliquer sur l'icone de l'extension dans la barre du navigateur
   - **Attendu** : un indicateur "serveur hors ligne" s'affiche
2. **Rallumer le serveur** : relancer `uv run python manage.py runserver`
   - **Attendu** : l'indicateur passe a "connecte"
3. **Recolter une page deja recoltee (meme URL)** : cliquer sur le bouton de recolte pour une page deja importee
   - **Attendu** : message "page deja importee" au lieu d'un doublon
4. **Recolter une page avec des parametres UTM differents mais meme contenu** : modifier l'URL avec des params UTM puis recolter
   - **Attendu** : detection du doublon par content_hash

## 6. Extraits du PLAN.md

> ### Etape 1.3 — Extension navigateur : robustesse
>
> **Actions** :
> - [ ] Deduplication par content_hash en plus de l'URL (envoyer un hash cote extension, comparer cote serveur)
> - [ ] Normaliser l'URL avant comparaison (retirer UTM params, fragment, trailing slash)
> - [ ] Afficher un indicateur de statut serveur (online/offline) dans la popup
> - [ ] Remplacer `test_sidebar_view` par un vrai endpoint de production
>
> **Fichiers concernes** : `extension/popup.js`, `core/views.py`, `core/serializers.py`
