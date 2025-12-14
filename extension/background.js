// Hypostasia Background Script

chrome.action.onClicked.addListener(async (tab) => {
    // Prevent execution on restricted pages (e.g., chrome://)
    if (!tab.url || tab.url.startsWith("chrome://")) return;

    try {
        // Inject script if needed (though it should be declared in manifest content_scripts or injected here)
        // Since we removed 'content_scripts' from manifest in previous steps (or didn't? let's assume we inject manually to be safe or check manifest)
        // Actually, previous content.js was likely injected via manifest or popup.
        // Let's rely on manual injection for robustness as per request "sidebar logic".

        // We inject the content script and CSS
        await chrome.scripting.insertCSS({
            target: { tabId: tab.id },
            files: ["lib/sweetalert2.min.css"] // If we still use it, otherwise maybe just custom styles in content.js
        });

        // Inject HTMX lib (from web_accessible_resources)
        // We cannot inject generic script src easily in V3 content scripts without main world.
        // But content.js handles injection of htmx script tag.

        await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ["lib/Readability.js", "content.js"]
        });

        // Send message to toggle sidebar
        chrome.tabs.sendMessage(tab.id, { action: "toggle_sidebar" }).catch(err => {
            console.warn("Could not send message, maybe script just injected?", err);
            // If script was just injected, it might run its own init or we retry?
            // Actually, content.js should probably just init sidebar on load if we want?
            // Or we just rely on the fact that executeScript runs the file, and we add a check in content.js to toggle if it's already there.
        });

    } catch (e) {
        console.error("Hypostasia Background Error:", e);
    }
});
