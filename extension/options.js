// Saves options to chrome.storage
const saveOptions = async () => {
    let serverUrl = document.getElementById('serverUrl').value.trim();
    const apiKey = document.getElementById('apiKey').value.trim();

    // Basic validation / formatting
    if (!serverUrl) {
        serverUrl = "https://beta.hypostasia.org/";
    }
    // Ensure trailing slash
    if (!serverUrl.endsWith('/')) {
        serverUrl += '/';
    }

    // L'autorisation de joindre ce serveur vient AVANT l'enregistrement.
    // Le manifest n'accorde d'office que les deux instances officielles ;
    // une adresse auto-hebergee vit dans `optional_host_permissions` et
    // doit etre autorisee ici.
    //
    // L'APPEL NE DOIT AVOIR AUCUN `await` AVANT LUI : le navigateur
    // refuse une demande de permission qui ne descend pas du clic, et le
    // premier `await` perd ce geste.
    // / Permission before saving; no await may precede this call.
    const autorisation_accordee = await chrome.permissions.request({
        origins: [serverUrl + '*'],
    });
    if (!autorisation_accordee) {
        const status = document.getElementById('status');
        status.textContent = "Sans autorisation, l'extension ne peut pas joindre ce serveur.";
        status.className = 'error visible';
        return;
    }

    chrome.storage.sync.set(
        { serverUrl: serverUrl, apiKey: apiKey },
        () => {
            // Update status to let user know options were saved.
            const status = document.getElementById('status');
            status.textContent = 'Options enregistrées !';
            status.className = 'success visible';

            // Update input to reflect formatted value
            document.getElementById('serverUrl').value = serverUrl;

            setTimeout(() => {
                status.classList.remove('visible');
            }, 2000);
        }
    );
};

// Restores select box and checkbox state using the preferences
// stored in chrome.storage.
const restoreOptions = () => {
    chrome.storage.sync.get(
        { serverUrl: 'https://beta.hypostasia.org/', apiKey: '' },
        (items) => {
            document.getElementById('serverUrl').value = items.serverUrl;
            document.getElementById('apiKey').value = items.apiKey;
        }
    );
};

document.addEventListener('DOMContentLoaded', restoreOptions);
document.getElementById('save').addEventListener('click', saveOptions);
