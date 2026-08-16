# PHASE-25d : Invitation par email + Explorer + DossierSuivi

**Date :** 2026-03-15
**Migration :** Oui

**Quoi / What:** Invitation par email pour dossiers et groupes (email connu = partage direct,
email inconnu = invitation avec token + email). Page Explorer pour decouvrir les dossiers publics
(recherche, filtre auteur, pagination). Suivi de dossiers publics (4e section "Suivis" dans l'arbre).
Inscription avec token d'invitation → auto-acceptation.

**Pourquoi / Why:** PHASE-25c imposait de connaitre le username exact pour partager. Pas de
decouverte de contenu public. Pas moyen d'inviter un non-inscrit.

### Fichiers crees / Created files
| Fichier / File | Description |
|---|---|
| `front/views_invitation.py` | InvitationViewSet + helpers (creer, accepter, envoyer email) |
| `front/views_explorer.py` | ExplorerViewSet (list, suivre, ne_plus_suivre) |
| `front/templates/front/includes/explorer_page.html` | Page Explorer complete |
| `front/templates/front/includes/explorer_resultats.html` | Resultats pagines |
| `front/templates/front/includes/explorer_card.html` | Card dossier individuelle |
| `front/templates/front/invitation_erreur.html` | Page erreur invitation |
| `front/templates/front/emails/invitation_dossier.txt` | Email invitation dossier (texte) |
| `front/templates/front/emails/invitation_dossier.html` | Email invitation dossier (HTML) |
| `front/templates/front/emails/invitation_groupe.txt` | Email invitation groupe (texte) |
| `front/templates/front/emails/invitation_groupe.html` | Email invitation groupe (HTML) |
| `front/tests/e2e/test_16_invitation_explorer.py` | 8 tests E2E |
| `core/migrations/0023_dossiersuivi_invitation.py` | Migration auto |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +Invitation, +DossierSuivi |
| `hypostasia/settings.py` | +config email (EMAIL_BACKEND, SITE_URL, etc.) |
| `front/serializers.py` | +InviterEmailSerializer, +ExplorerFiltresSerializer |
| `front/views.py` | +action inviter sur DossierViewSet, _render_arbre 4 sections (+ Suivis) |
| `front/views_auth.py` | Handle ?token= dans register |
| `front/views_groupes.py` | +action inviter sur GroupeViewSet |
| `front/urls.py` | +ExplorerViewSet, +InvitationViewSet |
| `front/templates/front/includes/arbre_dossiers.html` | +section Suivis |
| `front/templates/front/includes/_dossier_node.html` | +bouton Ne plus suivre |
| `front/templates/front/includes/partage_dossier_form.html` | +section email + invitations en attente |
| `front/templates/front/register.html` | +hidden field token |
| `front/templates/front/base.html` | +lien Explorer dans footer arbre |
| `front/tests/test_phases.py` | +18 tests unitaires PHASE-25d |

### Migration
- **Migration necessaire / Migration required:** Oui
- `core/migrations/0023_dossiersuivi_invitation.py`
- Commande : `uv run python manage.py migrate`

