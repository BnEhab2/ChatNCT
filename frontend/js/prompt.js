const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? '' : 'https://minadiaa-chatnct.hf.space';

// ══════════════════════════════════════════════════════════════
// ChatNCT — Prompt Generator Logic
// ══════════════════════════════════════════════════════════════

const ideaInput = document.querySelector('.idea-input');
const promptOutput = document.querySelector('.prompt-output');
const generateBtn = document.querySelector('.generate-btn');
const executeBtn = document.querySelector('.execute-btn');

// ── Generate Prompt via API ────────────────────────────────
let isGenerating = false;

generateBtn.addEventListener('click', async () => {
    const ideaText = ideaInput.value.trim();
    if (!ideaText) {
        promptOutput.value = 'Please enter your idea first!';
        return;
    }
    if (isGenerating) return;

    isGenerating = true;
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
    generateBtn.disabled = true;
    promptOutput.value = 'جاري توليد الـ Prompt...';

    try {
        const response = await fetch(`${API_BASE}/api/prompt/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ idea: ideaText, user_id: getUsername() })
        });
        const data = await response.json();

        if (data.status === 'success') {
            promptOutput.value = data.prompt;
            showNotification('Prompt generated successfully! ', 'success');
        } else {
            promptOutput.value = 'Error: ' + (data.message || 'Unknown error');
            showNotification('Failed to generate prompt', 'error');
        }
    } catch (err) {
        console.error('Generate error:', err);
        promptOutput.value = 'Connection error. Make sure the server is running.';
        showNotification('Connection error', 'error');
    } finally {
        isGenerating = false;
        generateBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles"></i> Generate Prompt';
        generateBtn.disabled = false;
    }
});

// ── Execute Prompt → Chat ──────────────────────────────────
executeBtn.addEventListener('click', () => {
    const promptText = promptOutput.value;
    if (promptText && promptText !== 'Please enter your idea first!' && !promptText.startsWith('Error:') && !promptText.startsWith('Connection error')) {
        // Store prompt and redirect to chat
        localStorage.setItem('chatnct_pending_prompt', promptText);
        window.location.href = 'chat.html?view=chat&prompt=true';
    } else {
        showNotification('Please generate a prompt first!', 'error');
    }
});

// ── Drag & Drop ────────────────────────────────────────────
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    ideaInput.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); }, false);
});
['dragenter', 'dragover'].forEach(eventName => {
    ideaInput.addEventListener(eventName, () => {
        ideaInput.style.borderColor = '#7c66e3';
        ideaInput.style.background = 'rgba(62, 58, 131, 1)';
    }, false);
});
['dragleave', 'drop'].forEach(eventName => {
    ideaInput.addEventListener(eventName, () => {
        ideaInput.style.borderColor = 'rgba(124, 102, 227, 0.4)';
        ideaInput.style.background = 'rgba(62, 58, 131, 0.8)';
    }, false);
});
ideaInput.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    handleFiles(files);
}, false);

// ── Paste Button ───────────────────────────────────────────
document.getElementById('pasteBtn').addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        ideaInput.value += text;
    } catch (err) {
        console.error('Failed to read clipboard:', err);
        showNotification('Unable to paste from clipboard', 'error');
    }
});

// ── Upload Button ──────────────────────────────────────────
const fileInput = document.getElementById('fileInput');
document.getElementById('uploadBtn').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', function () {
    if (this.files.length > 0) handleFiles(this.files);
});

function handleFiles(files) {
    let fileInfo = '\n[Uploaded files: ';
    for (let i = 0; i < files.length; i++) {
        fileInfo += files[i].name + (i < files.length - 1 ? ', ' : '');
    }
    fileInfo += ']\n';
    ideaInput.value += fileInfo;
}
