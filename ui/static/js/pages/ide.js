document.addEventListener('DOMContentLoaded', () => {

    // --- Panel Resizing Logic ---
    const resizer1 = document.getElementById('resizer-1');
    const resizer2 = document.getElementById('resizer-2');
    const explorer = document.getElementById('ide-explorer');
    const terminal = document.getElementById('ide-terminal');
    const preview = document.getElementById('ide-preview');

    let isResizing = false;
    let currentResizer = null;

    resizer1.addEventListener('mousedown', (e) => { isResizing = true; currentResizer = 1; document.body.style.cursor = 'col-resize'; e.preventDefault();});
    resizer2.addEventListener('mousedown', (e) => { isResizing = true; currentResizer = 2; document.body.style.cursor = 'col-resize'; e.preventDefault();});
    document.addEventListener('mouseup', () => { isResizing = false; currentResizer = null; document.body.style.cursor = 'default'; });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        if (currentResizer === 1) {
            const newWidth = e.clientX;
            if (newWidth > 150 && newWidth < 500) explorer.style.width = newWidth + 'px';
        } else if (currentResizer === 2) {
            const containerWidth = document.querySelector('.file-panel-layout').clientWidth;
            const newWidth = containerWidth - e.clientX;
            if (newWidth > 200 && newWidth < 800) preview.style.width = newWidth + 'px';
        }
    });

    // --- File Explorer Logic ---
    async function loadExplorer(path = "", parentElement = document.getElementById('file-tree')) {
        const files = await window.apiFetch('/api/files?path=' + encodeURIComponent(path));
        if(!files) return;

        const ul = document.createElement('ul');
        ul.className = "tree-ul";

        files.forEach(f => {
            const li = document.createElement('li');
            li.className = `tree-item ${f.is_dir ? 'dir' : 'file'}`;
            li.textContent = f.name;
            li.setAttribute("data-path", f.path);

            li.addEventListener('click', (e) => {
                e.stopPropagation();
                if(f.is_dir) {
                    if (li.children.length === 0) {
                        loadExplorer(f.path, li); // expand
                    } else {
                        li.querySelector('ul').remove(); // collapse
                    }
                } else {
                    openFilePreview(f.path);
                }
            });
            ul.appendChild(li);
        });
        parentElement.appendChild(ul);
    }

    async function openFilePreview(path) {
        document.getElementById('preview-filename').textContent = path.split('/').pop();
        const data = await window.apiFetch('/api/files/content?path=' + encodeURIComponent(path));
        const codeBlock = document.getElementById('preview-code');

        if (data && !data.binary) {
            codeBlock.textContent = data.content;
            // determine language roughly
            let lang = 'python';
            if(path.endsWith('.js')) lang = 'javascript';
            else if(path.endsWith('.css')) lang = 'css';
            else if(path.endsWith('.html')) lang = 'markup';

            codeBlock.className = `language-${lang}`;
            Prism.highlightElement(codeBlock);
        } else {
            codeBlock.textContent = data?.content || "Could not load file.";
            codeBlock.className = "";
        }
    }

    // --- WebSocket Terminal Logic ---
    let ws = null;
    let renderMarkdown = true;
    const termOut = document.getElementById('terminal-output');
    const termIn = document.getElementById('terminal-input');

    function connectWS() {
        if(ws) return;
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        ws = new WebSocket(`${protocol}://${window.location.host}/ws/claude`);

        ws.onopen = () => {
            console.log("Terminal connected.");
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if(msg.type === "history") {
                termOut.innerHTML = '';
                msg.messages.forEach(m => appendMessage(m.role, m.content));
            } else if (msg.type === "claude_stream") {
                appendMessage("assistant_stream", msg.content);
            } else if (msg.type === "user") {
                appendMessage("user", msg.content);
            } else if (msg.type === "claude_done") {
                termOut.querySelector('.streaming-msg')?.classList.remove('streaming-msg');
            } else if (msg.type === "claude_working") {
                setWorking(msg.content === "true");
            } else if (msg.type === "claude_error") {
                appendMessage("error", msg.content);
            } else if (msg.type === "cleared") {
                termOut.innerHTML = '';
            }
        };

        ws.onclose = () => {
            ws = null;
            setTimeout(connectWS, 3000);
        };
    }

    function setWorking(active) {
        const dot = document.getElementById('term-dot');
        const status = document.getElementById('term-status');
        const stopBtn = document.getElementById('term-stop');
        if (active) {
            dot.classList.add('working');
            status.classList.add('working');
            status.textContent = 'WORKING...';
            stopBtn.style.display = '';
            termIn.disabled = true;
            termIn.placeholder = 'Claude is working...';
        } else {
            dot.classList.remove('working');
            status.classList.remove('working');
            status.textContent = 'READY';
            stopBtn.style.display = 'none';
            termIn.disabled = false;
            termIn.placeholder = 'Enter command for Claude... (Ctrl+V to paste screenshot)';
            termIn.focus();
        }
    }

    function appendMessage(role, text) {
        if (role === "assistant_stream") {
            let el = termOut.querySelector('.streaming-msg');
            if(!el) {
                el = document.createElement('div');
                el.className = "claude-msg streaming-msg";
                termOut.appendChild(el);
            }
            if(renderMarkdown) {
                const raw = (el.getAttribute("data-raw") || "") + text;
                el.setAttribute("data-raw", raw);
                el.innerHTML = DOMPurify.sanitize(marked.parse(raw));
            } else {
                el.textContent += text;
            }
        } else {
            const el = document.createElement('div');
            el.className = role === "user" ? "user-msg text-amber" : role === "error" ? "user-msg text-red" : "claude-msg";
            if(role === "user") {
                el.innerHTML = `<b>> ${DOMPurify.sanitize(text)}</b>`;
            } else {
                if(renderMarkdown) {
                    el.setAttribute("data-raw", text);
                    el.innerHTML = DOMPurify.sanitize(marked.parse(text));
                } else {
                    el.textContent = text;
                }
            }
            termOut.appendChild(el);
        }
        termOut.scrollTop = termOut.scrollHeight;
    }

    // --- Image paste support ---
    let pendingImage = null;

    document.addEventListener('paste', (e) => {
        // Only handle paste when IDE page is active
        if (!document.getElementById('page-ide').classList.contains('active')) return;

        const items = e.clipboardData?.items;
        if (!items) return;
        for (const item of items) {
            if (item.type.startsWith('image/')) {
                const blob = item.getAsFile();
                const reader = new FileReader();
                reader.onload = (ev) => {
                    pendingImage = ev.target.result;
                    const previewBar = document.getElementById('image-preview');
                    document.getElementById('preview-thumb').src = pendingImage;
                    previewBar.style.display = 'flex';
                    termIn.focus();
                };
                reader.readAsDataURL(blob);
                e.preventDefault();
                return;
            }
        }
    });

    function clearImage() {
        pendingImage = null;
        document.getElementById('image-preview').style.display = 'none';
    }

    document.getElementById('btn-remove-img').addEventListener('click', clearImage);

    // Fullscreen preview on thumbnail click
    document.getElementById('preview-thumb').addEventListener('click', () => {
        if (pendingImage) {
            document.getElementById('overlay-img').src = pendingImage;
            document.getElementById('img-overlay').style.display = 'flex';
        }
    });

    // Fullscreen on inline image click
    termOut.addEventListener('click', (e) => {
        if (e.target.classList.contains('inline-img')) {
            document.getElementById('overlay-img').src = e.target.src;
            document.getElementById('img-overlay').style.display = 'flex';
        }
    });

    // --- Input handling ---
    termIn.addEventListener('keydown', (e) => {
        if(e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            const val = termIn.value.trim();
            if(!val && !pendingImage) return;
            if(ws && ws.readyState === WebSocket.OPEN) {
                const payload = { type: "prompt", content: val || "Describe this screenshot." };

                if (pendingImage) {
                    payload.image = pendingImage;
                    // Show inline image in terminal
                    const msgEl = document.createElement('div');
                    msgEl.className = "user-msg text-amber";
                    msgEl.innerHTML = `<b>> ${DOMPurify.sanitize(val || 'Screenshot')}</b>`;
                    const img = document.createElement('img');
                    img.className = 'inline-img';
                    img.src = pendingImage;
                    msgEl.appendChild(img);
                    termOut.appendChild(msgEl);
                    termOut.scrollTop = termOut.scrollHeight;
                    clearImage();
                }

                ws.send(JSON.stringify(payload));
                termIn.value = "";
            }
        }
    });

    document.getElementById('term-clear').addEventListener('click', () => {
        if(ws) ws.send(JSON.stringify({type: "command", name: "clear"}));
    });

    document.getElementById('term-stop').addEventListener('click', () => {
        if(ws) ws.send(JSON.stringify({type: "stop"}));
    });

    document.getElementById('term-toggle').addEventListener('click', () => {
        renderMarkdown = !renderMarkdown;
        window.showToast("Markdown rendering: " + (renderMarkdown ? "ON" : "OFF"));
    });

    // Init when IDE page opened
    let initialized = false;
    window.addEventListener('page-expanded', (e) => {
        if (e.detail.pageId === 'page-ide' && !initialized) {
            loadExplorer();
            connectWS();
            initialized = true;
        }
    });
});
