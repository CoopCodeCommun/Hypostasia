/**
 * Fermeture du dropdown menu utilisateur au clic exterieur.
 * / Close user menu dropdown on outside click.
 *
 * Quand on clique en dehors du conteneur du menu, le dropdown se ferme.
 * / When clicking outside the menu container, the dropdown closes.
 */
(function() {
    document.addEventListener('click', function(evenement) {
        var conteneurMenu = document.getElementById('user-menu-container');
        var dropdown = document.getElementById('user-menu-dropdown');
        if (!conteneurMenu || !dropdown) return;
        // Si le clic est en dehors du conteneur du menu, fermer le dropdown
        // / If click is outside the menu container, close dropdown
        var clicEstDansLeMenu = conteneurMenu.contains(evenement.target);
        if (!clicEstDansLeMenu) {
            dropdown.classList.add('hidden');
        }
    });
})();
