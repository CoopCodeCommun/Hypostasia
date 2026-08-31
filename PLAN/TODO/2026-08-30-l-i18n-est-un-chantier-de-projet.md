# L'i18n est un chantier de projet, pas un reste du mode d'édition

**Décidé le** : 30 août 2026 (mainteneur)
**État** : décidé, **non codé** — et délibérément remis
**Origine** : la liste des restes du mode d'édition portait « i18n : tous les
messages du mode et du compte rendu sont en français dur ». La mesure a montré
que ce n'était pas un reste du mode.

## Ce qui a été mesuré, le 30 août 2026

| | |
|---|---|
| `{% translate %}` / `{% blocktrans %}` dans les **85** gabarits de `front/` | **2** |
| `gettext` dans `front/*.py` | **0** |
| dossier `locale/` | **aucun** |
| `LOCALE_PATHS` dans `settings.py` | **absent** (`USE_I18N = True`, `LANGUAGE_CODE = fr-fr`) |
| mécanisme pour les chaînes **JavaScript** | **aucun** (pas de `JavaScriptCatalog`) |

## La décision

**Ne rien envelopper tant que le chantier n'est pas ouvert en entier.**

Envelopper les seules chaînes du mode d'édition ne produirait **aucune**
traduction : il n'existe pas de catalogue pour les recevoir. Cela donnerait un
écran à moitié instrumenté au milieu d'un projet monolingue — et la moitié
instrumentée ferait croire, au prochain lecteur, que le reste a été oublié
plutôt que jamais commencé.

## Ce que le chantier suppose, le jour où il s'ouvrira

1. `LOCALE_PATHS` + `locale/`, et `LANGUAGES` (quelles langues, décision produit) ;
2. l'enveloppement de `front/` — 85 gabarits —, **msgid en français** (règle du
   skill `djc` : le français est la langue source, l'anglais s'en déduit) ;
3. un mécanisme pour les chaînes **JavaScript** : `JavaScriptCatalog`, ou des
   `data-*` posés par le gabarit — à trancher, les deux existent dans la nature ;
4. **`makemessages` et `compilemessages` sont lancés par le mainteneur, jamais
   par un agent** : ils réécrivent les deux `.po` en entier et fabriquent des
   « fuzzy » faux.

## Ce qui ne doit PAS arriver entre-temps

Que quelqu'un « commence par un écran » en croyant bien faire. C'est ce que
cette note existe pour empêcher.
