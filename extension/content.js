// Hypostasia Content Script

(function () {
    function extract() {
        console.log("Hypostasia: Starting extraction...");

        // We need Readability. Since it's not a module here, we assume it's injected or available.
        // If we inject it via popup.js using executeScript, it might not be in the global scope cleanly.
        // Best practice in V3: use scripting.executeScript with files: ['lib/Readability.js', 'content.js']

        // Create a clone of the document to avoid modifying the specific page
        var documentClone = document.cloneNode(true);

        // Use Readability
        if (typeof Readability === 'undefined') {
            console.error("Hypostasia: Readability is not defined. Make sure it is injected.");
            return { error: "Readability missing" };
        }

        var article = new Readability(documentClone).parse();

        if (!article) {
            console.error("Hypostasia: Extraction failed (null article).");
            return { error: "Extraction failed" };
        }

        console.log("Hypostasia: Extraction success.", article.title);

        return {
            url: window.location.href,
            html_original: document.documentElement.outerHTML, // We capture the full original HTML as requested
            html_readability: article.content,
            text_readability: article.textContent,
            title: article.title
        };
    }

    // --- UI INJECTION LOGIC ---

    let sidebarVisible = false;

    function createStyles() {
        const style = document.createElement('style');
        style.textContent = `
            #hypostasia-float-btn {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 50px;
                height: 50px;
                background-color: #0d6efd;
                color: white;
                border: none;
                border-radius: 50%;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                cursor: pointer;
                z-index: 2147483647;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                transition: transform 0.2s;
            }
            #hypostasia-float-btn:hover { transform: scale(1.1); }
            
            #hypostasia-sidebar {
                position: fixed;
                top: 0;
                right: -350px; /* Hidden via transform roughly matches width */
                width: 350px;
                height: 100vh;
                background: white;
                box-shadow: -2px 0 5px rgba(0,0,0,0.1);
                z-index: 2147483646;
                transition: right 0.3s ease;
                display: flex;
                flex-direction: column;
                font-family: sans-serif;
            }
            #hypostasia-sidebar.visible { right: 0; }
            
            .ag-header { padding: 15px; background: #f8f9fa; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; }
            .ag-title { font-weight: bold; margin: 0; font-size: 16px; color: #333; }
            .ag-close { background: none; border: none; font-size: 20px; cursor: pointer; color: #666; }
            
            .ag-list { flex: 1; overflow-y: auto; padding: 0; margin: 0; list-style: none; }
            .ag-item { padding: 15px; border-bottom: 1px solid #eee; cursor: pointer; border-left: 4px solid transparent; }
            .ag-item:hover { background: #f9f9f9; }
            .ag-item.pour { border-left-color: #198754; }
            .ag-item.contre { border-left-color: #dc3545; }
            .ag-item.neutre { border-left-color: #6c757d; }
            
            .ag-badge { display: inline-block; padding: 2px 6px; border-radius: 4px; color: white; font-size: 10px; font-weight: bold; text-transform: uppercase; margin-bottom: 5px; }
            .ag-badge.pour { background-color: #198754; }
            .ag-badge.contre { background-color: #dc3545; }
            .ag-badge.neutre { background-color: #6c757d; }
            
            .ag-summary { margin: 0; font-size: 13px; color: #333; line-height: 1.4; }
            
            .ag-highlight { background-color: rgba(255, 235, 59, 0.4); border-bottom: 2px solid #fbc02d; transition: background 0.5s; }
            .ag-item.active { background-color: #e9ecef; }
        `;
        document.head.appendChild(style);
    }

    function injectUI(argumentsList) {
        if (document.getElementById('hypostasia-float-btn')) {
            // Update args if already exists
            updateSidebar(argumentsList);
            openSidebar();
            return;
        }

        createStyles();

        // Floating Button
        const btn = document.createElement('button');
        btn.id = 'hypostasia-float-btn';
        btn.innerHTML = '⚖️';
        btn.title = 'Hypostasia Arguments';
        btn.onclick = toggleSidebar;
        document.body.appendChild(btn);

        // Sidebar
        const sidebar = document.createElement('div');
        sidebar.id = 'hypostasia-sidebar';
        sidebar.innerHTML = `
            <div class="ag-header">
                <h2 class="ag-title">Arguments (${argumentsList.length})</h2>
                <button class="ag-close">&times;</button>
            </div>
            <ul class="ag-list"></ul>
        `;
        document.body.appendChild(sidebar);

        sidebar.querySelector('.ag-close').onclick = closeSidebar;

        renderArguments(argumentsList);

        // Auto open
        setTimeout(() => openSidebar(), 100);
    }

    function toggleSidebar() {
        sidebarVisible = !sidebarVisible;
        const sb = document.getElementById('hypostasia-sidebar');
        if (sidebarVisible) sb.classList.add('visible');
        else sb.classList.remove('visible');
    }

    function openSidebar() {
        sidebarVisible = true;
        document.getElementById('hypostasia-sidebar').classList.add('visible');
    }

    function closeSidebar() {
        sidebarVisible = false;
        document.getElementById('hypostasia-sidebar').classList.remove('visible');
    }

    function renderArguments(list) {
        const ul = document.querySelector('#hypostasia-sidebar .ag-list');
        ul.innerHTML = '';

        list.forEach(arg => {
            const li = document.createElement('li');
            li.className = `ag-item ${arg.stance}`;
            li.innerHTML = `
                <span class="ag-badge ${arg.stance}">${arg.stance}</span>
                <p class="ag-summary">${arg.summary}</p>
            `;
            li.onclick = () => {
                // Remove active class from others
                ul.querySelectorAll('.ag-item').forEach(el => el.classList.remove('active'));
                li.classList.add('active');
                scrollToText(arg.text_original);
            };
            ul.appendChild(li);
        });
    }

    function updateSidebar(list) {
        document.querySelector('#hypostasia-sidebar .ag-title').textContent = `Arguments (${list.length})`;
        renderArguments(list);
    }

    // --- SCROLL LOGIC (Robust Cross-Node Implementation) ---

    function scrollToText(textSnippet) {
        console.log("Hypostasia: Scrolling to snippet...", textSnippet.substring(0, 30));

        // 1. Cleanup previous highlights
        document.querySelectorAll('.ag-highlight').forEach(el => {
            const parent = el.parentNode;
            if (parent) {
                parent.replaceChild(document.createTextNode(el.textContent), el);
                parent.normalize();
            }
        });
        document.querySelectorAll('.ag-highlight-fallback').forEach(el => {
            el.classList.remove('ag-highlight-fallback');
        });

        const cleanSnippet = textSnippet.trim();
        if (!cleanSnippet) return;

        // 2. Try window.find (Native browser search)
        // This is the most accurate way to find text as rendered (handling bold/italic/etc matches)
        // However, it selects the text. We then capture the selection.

        // Reset selection first
        window.getSelection().removeAllRanges();

        // window.find(string, caseSensitive, backwards, wrapAround, wholeWord, searchInFrames, showDialog)
        const found = window.find(cleanSnippet, false, false, true, false, false, false);

        if (found) {
            const selection = window.getSelection();
            if (selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);

                // Verify if the found text is inside our sidebar (false positive)
                const sidebar = document.getElementById('hypostasia-sidebar');
                if (sidebar && sidebar.contains(range.commonAncestorContainer)) {
                    // It found the text in the sidebar! We need to find the NEXT one.
                    // Loop finder until we are out of sidebar
                    let attempts = 0;
                    let valid = false;
                    while (attempts < 10 && !valid) {
                        const foundNext = window.find(cleanSnippet, false, false, true, false, false, false);
                        if (!foundNext) break;
                        const rng = window.getSelection().getRangeAt(0);
                        if (!sidebar.contains(rng.commonAncestorContainer)) {
                            valid = true;
                        }
                        attempts++;
                    }
                }

                // Now we have a valid range?
                // Re-check selection
                const finalRange = window.getSelection().getRangeAt(0);
                const ancestor = finalRange.commonAncestorContainer;

                if (sidebar && !sidebar.contains(ancestor)) {
                    // Create highlight
                    // Note: surroundContents fails if range crosses non-text boundaries partially.
                    // Safer way: use a span or simplified scrolling.

                    // We try to surround. If it fails (complex DOM), we fallback to scrolling to the start node.
                    try {
                        const span = document.createElement('span');
                        span.className = 'ag-highlight';
                        finalRange.surroundContents(span);
                        span.scrollIntoView({ behavior: 'smooth', block: 'center' });

                        // Deselect for clean look (optional, but finding requires selection)
                        window.getSelection().removeAllRanges();
                    } catch (e) {
                        console.warn("Hypostasia: surroundContents failed (complex range), scrolling only.", e);
                        const element = ancestor.nodeType === 3 ? ancestor.parentElement : ancestor;
                        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        // Add class to parent as fallback highlight
                        element.classList.add('ag-highlight-fallback');
                        setTimeout(() => element.classList.remove('ag-highlight-fallback'), 2000);
                    }
                    return;
                }
            }
        }

        console.warn("Hypostasia: Text not found via window.find, trying fuzzy strategies (Block Level)...");

        // --- BLOCK LEVEL SEARCH STRATEGY ---
        // Scans P, DIV, LI, etc. looking for combined text content.
        // This solves issues where text is split by <b>, <i>, <a> tags.

        function findBlock(matcher) {
            // We select common block elements containing text
            const blocks = document.body.querySelectorAll('p, li, h1, h2, h3, h4, h5, h6, blockquote, article section, div');

            for (let block of blocks) {
                // Optimization: Skip huge container divs or tiny irrelevant tags
                if (block.tagName === 'DIV' && block.childElementCount > 5) continue;
                if (block.offsetParent === null) continue; // Hidden

                const blockText = block.textContent.replace(/\s+/g, ' ');
                if (matcher(blockText)) {
                    return block;
                }
            }
            return null;
        }

        // Strategy A: Exact Match (Normalized)
        let foundElement = findBlock(text => text.includes(cleanSnippet));

        // Strategy B: First 60 chars
        if (!foundElement && cleanSnippet.length > 60) {
            const startChunk = cleanSnippet.substring(0, 60);
            foundElement = findBlock(text => text.includes(startChunk));
        }

        // Strategy C: First 5-8 words
        if (!foundElement) {
            const words = cleanSnippet.split(' ');
            if (words.length >= 5) {
                const firstFive = words.slice(0, 5).join(' ');
                foundElement = findBlock(text => text.includes(firstFive));
            }
        }

        if (foundElement) {
            console.log("Hypostasia: Found via block search!");
            foundElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            foundElement.classList.add('ag-highlight-fallback');
            setTimeout(() => foundElement.classList.remove('ag-highlight-fallback'), 2000);
        } else {
            console.error("Hypostasia: Content not found in page (even with block search).");
        }
    }

    // Check if duplicate injection to avoid conflict?
    if (window.hypostasiaInjected) return;
    window.hypostasiaInjected = true;

    // Expose extractor and injector
    window.hypostasiaExtract = extract;
    window.hypostasiaInjectUI = injectUI;
})();
