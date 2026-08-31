// ==========================================================================
// keyboard.js — Dispatcher centralise des raccourcis clavier (PHASE-17)
// / Centralized keyboard shortcut dispatcher (PHASE-17)
//
// LOCALISATION : front/static/front/js/keyboard.js
//
// Ce fichier est le SEUL listener keydown de l'application.
// Il appelle les APIs publiques des autres modules :
//   - window.drawerVueListe  (drawer_vue_liste.js)
//   - window.marginalia      (marginalia.js)
//
// LA TOUCHE T A DISPARU LE 12 AOUT 2026 avec l'arbre lateral qu'elle
// ouvrait (window.arbreOverlay n'existe plus). La navigation entre
// carnets et bases se fait par les liens nommes de la barre.
// / T is gone with the side tree it opened; navigation is by the
// toolbar's named links.
//
// RACCOURCIS :
//   E       → Toggle drawer vue liste
//   L       → Toggle mode focus lecture
//   J       → Extraction suivante
//   K       → Extraction precedente
//   C       → Commenter extraction selectionnee
//   X       → Masquer extraction selectionnee
//   H       → Toggle heat map du debat
//   A       → Toggle mode selection alignement / ouvrir modale
//   /       → Recherche (placeholder)
//   ?       → Modale aide raccourcis
//   Escape  → Cascade fermeture (modale alignement > modale aide > focus > drawer > carte > selection)
//
// Expose : window.raccourcisClavier = { fermerAide }
// ==========================================================================
(function() {
    'use strict';

    // --- Etat interne ---
    // / --- Internal state ---
    var modaleAideOuverte = false;
    var indexExtractionSelectionnee = -1;
    var listeExtractionsVisibles = [];


    // --- Utilitaires ---
    // / --- Utilities ---

    // Verifie si le focus est dans un champ de saisie (input, textarea, select, contentEditable)
    // / Check if focus is on an input field (input, textarea, select, contentEditable)
    function estDansChampSaisie() {
        var elementActif = document.activeElement;
        if (!elementActif) return false;
        return (
            elementActif.tagName === 'INPUT' ||
            elementActif.tagName === 'TEXTAREA' ||
            elementActif.tagName === 'SELECT' ||
            elementActif.isContentEditable
        );
    }

    // Extrait le token CSRF depuis le header hx-headers du body
    // / Extract CSRF token from body's hx-headers attribute
    function extraireTokenCsrf() {
        var headersBrut = document.querySelector('body').getAttribute('hx-headers');
        if (!headersBrut) return '';
        try {
            return JSON.parse(headersBrut)['X-CSRFToken'];
        } catch (erreur) {
            return '';
        }
    }

    // Recupere le page_id depuis la zone de lecture
    // / Get page_id from reading zone
    function getPageId() {
        var elementPage = document.querySelector('#zone-lecture [data-page-id]');
        if (!elementPage) return null;
        return elementPage.dataset.pageId;
    }


    // === Navigation J/K entre extractions ===
    // / === J/K navigation between extractions ===

    // Reconstruit la liste des extractions visibles dans le texte
    // Deduplique par extraction-id (un meme id peut avoir plusieurs spans)
    // / Rebuild list of visible extractions in text
    // / Deduplicate by extraction-id (same id may have multiple spans)
    function reconstruireListeExtractions() {
        var tousLesSpans = document.querySelectorAll('#readability-content .hl-extraction[data-extraction-id]');
        var idsVus = {};
        listeExtractionsVisibles = [];

        tousLesSpans.forEach(function(span) {
            var extractionId = span.dataset.extractionId;
            if (!extractionId || idsVus[extractionId]) return;
            idsVus[extractionId] = true;
            listeExtractionsVisibles.push({
                extractionId: extractionId,
                premierSpan: span,
            });
        });
    }

    // Selectionne une extraction par index : surligne, scroll, ouvre le drawer
    // Refonte A.8 drawer-only : plus de carte inline sous le paragraphe.
    // / Select extraction by index: highlight, scroll, open drawer
    // / A.8 drawer-only: no more inline card below the paragraph.
    function selectionnerExtraction(index) {
        if (index < 0 || index >= listeExtractionsVisibles.length) return;

        // Deselectionner la precedente / Deselect previous
        deselectionnerExtraction();

        indexExtractionSelectionnee = index;
        var extraction = listeExtractionsVisibles[index];
        var span = extraction.premierSpan;

        // Ajouter la classe de selection visuelle / Add visual selection class
        span.classList.add('extraction-selectionnee');

        // Scroll vers le span / Scroll to span
        span.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Activer le surlignage / Activate highlighting
        document.querySelectorAll('.hl-extraction.ancre-active').forEach(function(el) {
            el.classList.remove('ancre-active');
        });
        span.classList.add('ancre-active');

        // Ouvrir le drawer + scroller vers la carte concernee (drawer-only A.8)
        // / Open drawer + scroll to card (A.8 drawer-only)
        if (window.marginalia && window.marginalia.ouvrirDrawerEtScrollerVersCarte) {
            window.marginalia.ouvrirDrawerEtScrollerVersCarte(extraction.extractionId);
        }
    }

    // Retire la selection visuelle de l'extraction courante
    // / Remove visual selection from current extraction
    function deselectionnerExtraction() {
        document.querySelectorAll('.extraction-selectionnee').forEach(function(el) {
            el.classList.remove('extraction-selectionnee');
        });
        indexExtractionSelectionnee = -1;
    }

    // Passe a l'extraction suivante (J)
    // / Move to next extraction (J)
    function extractionSuivante() {
        if (listeExtractionsVisibles.length === 0) return;
        var nouvelIndex = indexExtractionSelectionnee + 1;
        if (nouvelIndex >= listeExtractionsVisibles.length) {
            nouvelIndex = 0; // Boucle / Loop
        }
        selectionnerExtraction(nouvelIndex);
    }

    // Passe a l'extraction precedente (K)
    // / Move to previous extraction (K)
    function extractionPrecedente() {
        if (listeExtractionsVisibles.length === 0) return;
        var nouvelIndex = indexExtractionSelectionnee - 1;
        if (nouvelIndex < 0) {
            nouvelIndex = listeExtractionsVisibles.length - 1; // Boucle / Loop
        }
        selectionnerExtraction(nouvelIndex);
    }


    // === Modale aide raccourcis (?) ===
    // La modale est chargee via HTMX depuis /lire/aide/ (template serveur).
    // fermerAideRaccourcis() est appele par la touche Escape.
    // / === Keyboard shortcuts help modal (?) ===
    // / The modal is loaded via HTMX from /lire/aide/ (server template).
    // / fermerAideRaccourcis() is called by the Escape key.

    // Ferme la modale d'aide
    // / Close help modal
    function fermerAideRaccourcis() {
        if (!modaleAideOuverte) return;
        modaleAideOuverte = false;

        var modale = document.getElementById('modale-raccourcis');
        if (modale) {
            modale.remove();
        }
    }


    // === Actions sur extraction selectionnee ===
    // / === Actions on selected extraction ===

    // Clique le bouton commenter de la carte concernee dans le drawer (C)
    // Refonte A.8 drawer-only : la carte se trouve maintenant dans le drawer,
    // plus sous le paragraphe.
    // / Click the comment button on the matching card in the drawer (C)
    // / A.8 drawer-only: card is in the drawer, not under the paragraph.
    function commenterExtractionSelectionnee() {
        if (indexExtractionSelectionnee < 0) return;
        var extraction = listeExtractionsVisibles[indexExtractionSelectionnee];
        if (!extraction) return;

        // S'assurer que le drawer est ouvert et la carte chargee
        // / Ensure drawer is open and card loaded
        if (window.marginalia && window.marginalia.ouvrirDrawerEtScrollerVersCarte) {
            window.marginalia.ouvrirDrawerEtScrollerVersCarte(extraction.extractionId);
        }
        var carte = document.querySelector(
            '#drawer-contenu .drawer-carte-compacte[data-extraction-id="' + extraction.extractionId + '"]'
        );
        if (!carte) return;

        var boutonCommenter = carte.querySelector('.btn-commenter-extraction');
        if (boutonCommenter) {
            boutonCommenter.click();
        }
    }

    // Masque l'extraction selectionnee (X)
    // / Hide selected extraction (X)
    function masquerExtractionSelectionnee() {
        if (indexExtractionSelectionnee < 0) return;
        var extraction = listeExtractionsVisibles[indexExtractionSelectionnee];
        if (!extraction) return;

        var pageId = getPageId();
        if (!pageId) return;

        fetch('/extractions/masquer/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': extraireTokenCsrf(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'entity_id=' + extraction.extractionId + '&page_id=' + pageId,
        }).then(function(reponse) {
            if (reponse.ok) {
                Swal.fire({
                    toast: true, position: 'top-end', icon: 'success',
                    title: 'Extraction masqu\u00e9e',
                    showConfirmButton: false, timer: 2000, timerProgressBar: true,
                });
                // Deselectionner et reconstruire / Deselect and rebuild
                deselectionnerExtraction();
                reconstruireListeExtractions();
            }
        });
    }

    // Placeholder recherche (/)
    // / Search placeholder (/)
    // Z → Ouvrir la comparaison de versions pour la page courante
    // / Z → Open version comparison for the current page
    function comparerVersionsPageCourante() {
        // Verifier si on est deja sur la vue de comparaison
        // / Check if we're already on the comparison view
        var diffExistant = document.querySelector('[data-testid="diff-versions-pages"]');
        if (diffExistant) {
            // Deja sur la comparaison → retour a la page d'origine (data-page-id sur le conteneur diff)
            // / Already on comparison → back to origin page (data-page-id on the diff container)
            var pageOrigineId = diffExistant.dataset.pageId;
            if (pageOrigineId) {
                htmx.ajax('GET', '/lire/' + pageOrigineId + '/', {target: '#zone-lecture', swap: 'innerHTML', pushUrl: true});
            }
            return;
        }

        // Mode lecture normal → ouvrir la comparaison
        // / Normal reading mode → open comparison
        var elementPage = document.querySelector('#zone-lecture [data-page-id]');
        if (!elementPage) return;
        var pageId = elementPage.dataset.pageId;

        htmx.ajax('GET', '/lire/' + pageId + '/comparer/', {target: '#zone-lecture', swap: 'innerHTML', pushUrl: true});
    }

    function placeholderRecherche() {
        Swal.fire({
            toast: true,
            position: 'top-end',
            icon: 'info',
            title: 'Recherche \u2014 bient\u00f4t disponible',
            showConfirmButton: false,
            timer: 2000,
            timerProgressBar: true,
        });
    }


    // === Cascade Escape ===
    // Ferme le panneau le plus "proche" de l'utilisateur en premier
    // / Close the panel closest to the user first
    function gererEscape() {
        // 0.0 bis Le DIALOGUE de scission est en top layer : il est
        //     au-dessus de tout, il se ferme donc en premier. Sans ce
        //     rang, le rang 4.5 fermait l'editeur CACHE DERRIERE lui
        //     — un brouillon perdu sans que rien ne se voie — et le
        //     preventDefault de ce fichier empechait en plus la
        //     fermeture native du <dialog>.
        // / A <dialog> sits in the top layer: it closes first.
        var dialogueElement = document.getElementById('dialogue-element-ouvert');
        if (dialogueElement && dialogueElement.open) {
            dialogueElement.close();
            return true;
        }

        // 0.0 ter Menu utilisateur ouvert → fermer. Il s'ouvre par-dessus
        //     l'ecran, donc avant tout le reste. Ce rang REMPLACE un
        //     ecouteur que `user_menu.js` portait hors cascade : menu +
        //     editeur ouverts, un seul Echap fermait les deux et jetait
        //     la correction en cours de frappe.
        // / Replaces an out-of-cascade listener in user_menu.js.
        if (window.userMenu && window.userMenu.fermerSiOuvert) {
            if (window.userMenu.fermerSiOuvert()) {
                return true;
            }
        }

        // 0.0 Bottom sheet mobile ouvert → fermer (PHASE-21)
        // / 0.0 Mobile bottom sheet open → close (PHASE-21)
        if (window.bottomSheet && window.bottomSheet.estOuvert()) {
            window.bottomSheet.fermer();
            return true;
        }

        // 0. Modale alignement ouverte → fermer
        // / 0. Alignment modal open → close
        if (window.alignement && window.alignement.estOuvert()) {
            window.alignement.fermer();
            return true;
        }

        // 1. Modale aide ouverte → fermer
        // / 1. Help modal open → close
        if (modaleAideOuverte) {
            fermerAideRaccourcis();
            return true;
        }

        // 1.5 Bandeau notification ouvert → fermer et marquer vu
        // / 1.5 Notification banner open → close and mark as viewed
        var bandeauNotification = document.getElementById('bandeau-notifications');
        if (bandeauNotification && bandeauNotification.querySelector('.bandeau-notification')) {
            bandeauNotification.innerHTML = '';
            if (window.notificationsProgression) {
                window.notificationsProgression.marquerVu();
            }
            return true;
        }

        // 2. Dashboard ouvert → fermer
        // / 2. Dashboard open → close

        // 3. Drawer ouvert → fermer
        // / 3. Drawer open → close
        if (window.drawerVueListe && window.drawerVueListe.estOuvert()) {
            window.drawerVueListe.fermer();
            return true;
        }

        // 4. L'arbre lateral occupait ce rang de la cascade jusqu'au
        //    12 aout 2026. Retire avec l'arbre.
        // / 4. The side tree held this rung until it was removed.

        // 4.5 Editeur de correction en place ouvert -> fermer.
        //
        // CE RANG EST APRES LE DRAWER, ET C'EST VOULU : le drawer est un
        // panneau qui s'ouvre PAR-DESSUS le texte, donc plus pres de
        // l'utilisateur. Un Echap ferme le drawer, un second ferme
        // l'editeur — une chose a la fois, ce que cette cascade existe
        // pour garantir.
        //
        // Ce rang REMPLACE un second ecouteur `keydown` que marginalia.js
        // portait hors cascade : les deux repondaient a la meme touche, et
        // un seul appui fermait le drawer ET jetait la correction en cours
        // de frappe (mesure du 29 aout 2026).
        // / This rung replaces a second, out-of-cascade Escape listener:
        // one keypress used to close two things and discard the edit.
        if (window.marginalia && window.marginalia.fermerEditeurEnPlace) {
            if (window.marginalia.fermerEditeurEnPlace()) {
                return true;
            }
        }

        // 4.6 Mode d'edition ouvert → en sortir.
        //
        // CE RANG EST LE DERNIER AVANT LA DESELECTION, ET C'EST VOULU :
        // le mode est un ETAT, pas un panneau. Tout ce qui s'ouvre
        // par-dessus lui — dialogue, menu, drawer, editeur en place — se
        // ferme d'abord ; on ne sort du mode que lorsqu'il ne reste plus
        // que lui. En sortir par megarde coute cher.
        // / The mode is a state, not a panel: everything else closes first.
        if (window.modeEdition && window.modeEdition.estOuvert
            && window.modeEdition.estOuvert()) {
            window.modeEdition.fermer();
            return true;
        }

        // 5. Extraction selectionnee → deselectionner
        // (la branche 'carte inline ouverte' a ete retiree avec la refonte
        //  drawer-only A.8 : il n'y a plus de carte inline sous le paragraphe)
        // / 5. Extraction selected → deselect (no more inline card to close)
        if (indexExtractionSelectionnee >= 0) {
            deselectionnerExtraction();
            return true;
        }

        return false;
    }


    // === Listener unique keydown ===
    // / === Single keydown listener ===
    document.addEventListener('keydown', function(evenement) {
        var touche = evenement.key;

        // Escape fonctionne toujours (meme dans un champ de saisie)
        // / Escape always works (even in an input field)
        if (touche === 'Escape') {
            var gere = gererEscape();
            if (gere) {
                evenement.preventDefault();
            }
            return;
        }

        // Ignorer les raccourcis si dans un champ de saisie
        // / Ignore shortcuts if in an input field
        if (estDansChampSaisie()) return;

        // LE MODE D'EDITION PREND LE CLAVIER, MEME QUAND LE FOCUS EST
        // SORTI DU CHAMP.
        //
        // La garde ci-dessus ne voit que le champ lui-meme. Or pendant
        // une session d'edition, le focus passe legitimement sur le rail
        // du lecteur (`tabindex="0"`), sur le menu du recul a la
        // reprise, sur un bouton du panneau des masques — et la, les
        // touches simples redevenaient vivantes : « e » ouvrait un
        // tiroir que le mode cache, « m » rebasculait le mode, et
        // surtout « z » REMPLACE `#zone-lecture` par la comparaison de
        // versions, ce qui detruit la session de frappe sans une
        // question.
        //
        // `Echap` est traite PLUS HAUT, avant cette garde : le mode s'en
        // sort au rang 4.6, comme il le doit.
        // / During an editing session the focus legitimately leaves the
        // field; bare letters must stay silent, or "z" replaces the
        // whole reading zone and the session dies unasked.
        if (window.modeEdition && window.modeEdition.estOuvert()) return;

        // Ignorer si Ctrl, Meta ou Alt est enfonce (raccourcis navigateur)
        // / Ignore if Ctrl, Meta or Alt is pressed (browser shortcuts)
        if (evenement.ctrlKey || evenement.metaKey || evenement.altKey) return;

        switch (touche) {
            // La touche T ouvrait l'arbre lateral. Elle n'est plus liee :
            // laisser un raccourci sans effet est pire que pas de
            // raccourci du tout — il consomme la frappe sans rien faire.
            // / T opened the side tree; unbound rather than left as a
            // no-op that would swallow the keystroke.

            // E → Toggle drawer vue liste
            // / E → Toggle list view drawer
            // 'm' — ENTRER EN MODE EDITION.
            //
            // Le mode se ferme par Echap (rang 4.6 de la cascade), et
            // cette touche-ci ne peut pas l'y aider : une fois le mode
            // ouvert, le focus est DANS le champ, et `estDansChampSaisie`
            // — qui compte `isContentEditable` — arrete toutes les
            // touches simples avant d'arriver ici. C'est heureux : sans
            // cela, taper « m » dans le texte sortirait du mode.
            // / 'm' enters; Escape leaves. Once inside, single keys are
            // stopped by the input-field guard, which is what we want.
            case 'm':
                if (window.modeEdition && window.modeEdition.basculer) {
                    var boutonDuMode = document.getElementById('bouton-mode-edition');
                    if (boutonDuMode && !boutonDuMode.disabled) {
                        evenement.preventDefault();
                        window.modeEdition.basculer(boutonDuMode);
                    }
                }
                break;

            case 'e':
                if (window.drawerVueListe) {
                    window.drawerVueListe.basculer();
                }
                evenement.preventDefault();
                break;

            // J → Extraction suivante
            // / J → Next extraction
            case 'j':
                extractionSuivante();
                evenement.preventDefault();
                break;

            // K → Extraction precedente
            // / K → Previous extraction
            case 'k':
                extractionPrecedente();
                evenement.preventDefault();
                break;

            // C → Commenter extraction selectionnee
            // / C → Comment selected extraction
            case 'c':
                commenterExtractionSelectionnee();
                evenement.preventDefault();
                break;

            // X → Masquer extraction selectionnee
            // / X → Hide selected extraction
            case 'x':
                masquerExtractionSelectionnee();
                evenement.preventDefault();
                break;

            // A → Toggle alignement du dossier courant
            // / A → Toggle alignment for current folder
            case 'a':
                if (window.alignement) {
                    window.alignement.basculerAlignement();
                }
                evenement.preventDefault();
                break;

            // Z → Comparer les versions (diff + hypostases)
            // / Z → Compare versions (diff + hypostases)
            case 'z':
                comparerVersionsPageCourante();
                evenement.preventDefault();
                break;

            // / → Recherche (placeholder)
            // / / → Search (placeholder)
            case '/':
                placeholderRecherche();
                evenement.preventDefault();
                break;

            // ? → Modale aide (chargee via HTMX depuis le serveur)
            // / ? → Help modal (loaded via HTMX from the server)
            case '?':
                // Eviter d'ouvrir un doublon si deja ouverte
                // / Avoid opening a duplicate if already open
                if (!document.getElementById('modale-raccourcis')) {
                    htmx.ajax('GET', '/lire/aide/', {
                        target: 'body',
                        swap: 'beforeend',
                    });
                }
                evenement.preventDefault();
                break;
        }
    });


    // === Initialisation au chargement ===
    // / === Initialization on load ===
    document.addEventListener('DOMContentLoaded', function() {
        reconstruireListeExtractions();

        // Le bouton aide est desormais gere par HTMX (hx-get dans le template)
        // / Help button is now handled by HTMX (hx-get in the template)

        // Empecher d'ouvrir 2 modales d'aide (via HTMX beforeend)
        // / Prevent opening 2 help modals (via HTMX beforeend)
        document.body.addEventListener('click', function(evenement) {
            var boutonAide = evenement.target.closest('#btn-toolbar-aide, #btn-toolbar-aide-mobile');
            if (!boutonAide) return;
            // Si la modale est deja ouverte, la fermer au lieu d'en creer une deuxieme
            // / If modal is already open, close it instead of creating a second one
            var modaleExistante = document.getElementById('modale-raccourcis');
            if (modaleExistante) {
                evenement.preventDefault();
                evenement.stopPropagation();
                modaleExistante.remove();
            }
        });

        // Toggle mode mobile : cycle entre 2 modes d'affichage (refonte A.2 — heatmap retiree)
        // Le bouton oeil dans la toolbar change le mode a chaque tap :
        //   surlignage → lecture pure → retour au surlignage
        // - surlignage : le texte extrait a un fond colore (par statut de debat)
        // - lecture pure : pas de surlignage, texte brut pour lire sans distraction
        // / Mobile mode toggle: cycles between 2 display modes (A.2 refactor — heatmap removed)
        // The eye button in the toolbar changes mode on each tap:
        //   highlight → reading → back to highlight
        var modeActuel = 'surlignage'; // surlignage | lecture
        var boutonModeMobile = document.getElementById('btn-toolbar-mode-mobile');
        if (boutonModeMobile) {
            boutonModeMobile.addEventListener('click', function() {
                // Passer au mode suivant — toggle simple
                // / Switch to next mode — simple toggle
                if (modeActuel === 'surlignage') {
                    // Surlignage → Lecture : masquer le surlignage
                    // / Highlight → Reading: hide highlighting
                    modeActuel = 'lecture';
                    document.body.classList.add('mode-lecture-mobile');
                } else {
                    // Lecture → Surlignage : remettre le surlignage
                    // / Reading → Highlight: restore highlighting
                    modeActuel = 'surlignage';
                    document.body.classList.remove('mode-lecture-mobile');
                }

                // Mettre a jour le title du bouton pour indiquer le mode actif
                // / Update button title to indicate active mode
                var titresParMode = {
                    'surlignage': 'Mode : Surlignage (tap pour changer)',
                    'lecture': 'Mode : Lecture pure (tap pour changer)',
                };
                boutonModeMobile.title = titresParMode[modeActuel];
            });
        }
    });

    document.body.addEventListener('htmx:afterSwap', function(evenement) {
        var cible = evenement.detail.target;
        if (cible && (cible.id === 'zone-lecture' || cible.closest('#zone-lecture'))) {
            // Reinitialiser la selection et reconstruire la liste
            // / Reset selection and rebuild list
            deselectionnerExtraction();
            reconstruireListeExtractions();
        }
    });


    // Expose l'API publique
    // / Expose public API
    window.raccourcisClavier = {
        fermerAide: fermerAideRaccourcis,
    };

})();
