// Saves options to chrome.storage
const saveOptions = () => {
    let serverUrl = document.getElementById('serverUrl').value.trim();
    const apiKey = document.getElementById('apiKey').value.trim();

    // Basic validation / formatting
    if (!serverUrl) {
        serverUrl = "http://127.0.0.1:8000/";
    }
    // Ensure trailing slash
    if (!serverUrl.endsWith('/')) {
        serverUrl += '/';
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
        { serverUrl: 'http://127.0.0.1:8000/', apiKey: '' },
        (items) => {
            document.getElementById('serverUrl').value = items.serverUrl;
            document.getElementById('apiKey').value = items.apiKey;
        }
    );
};

document.addEventListener('DOMContentLoaded', restoreOptions);
document.getElementById('save').addEventListener('click', saveOptions);
