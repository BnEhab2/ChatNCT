// ══════════════════════════════════════════════════════════════
// chat.js - Chat Page Logic
//
// This file handles the real-time chat interface where students
// interact with the AI assistant. Key features:
//
//   1. SENDING MESSAGES: User types a message, it gets sent to the
//      backend API which routes it to the appropriate AI agent.
//
//   2. MARKDOWN RENDERING: Bot responses can contain formatted text
//      (headers, lists, code blocks, etc.) using Markdown syntax.
//      We use the "marked" library to convert Markdown to HTML.
//
//   3. CODE SYNTAX HIGHLIGHTING: Code blocks in bot responses are
//      colored using highlight.js, with a "Copy" button on each block.
//
//   4. CHAT SESSIONS: Conversations are saved to the database (Supabase).
//      Users can see their chat history, resume old conversations,
//      rename them, or delete them.
//
//   5. RTL/LTR SUPPORT: Arabic text is automatically right-aligned,
//      English text is left-aligned.
// ══════════════════════════════════════════════════════════════

// API endpoint for the chat service
const API_URL = `${API_BASE}/api/chat`;

// State variables
let isWaiting = false;                 // True while waiting for bot response (prevents double-send)
let currentChatSessionId = null;       // ID of the active chat session in the database


// ── Markdown Renderer Configuration ────────────────────────
// Customize how marked.js renders code blocks:
// - Add syntax highlighting using highlight.js
// - Add a "Copy" button to each code block
// - Show the programming language name in a header bar
const renderer = new marked.Renderer();
renderer.code = function(code, language) {
    // Extract the code text (marked v5+ passes an object instead of string)
    const escapedCode = typeof code === 'string' ? code : (code?.text || '');
    const lang = language || code?.lang || '';

    // Apply syntax highlighting (colorize the code)
    let highlighted;
    try {
        if (lang && hljs.getLanguage(lang)) {
            // Known language: use specific highlighting rules
            highlighted = hljs.highlight(escapedCode, { language: lang }).value;
        } else {
            // Unknown language: let highlight.js guess
            highlighted = hljs.highlightAuto(escapedCode).value;
        }
    } catch (e) {
        // Fallback: just escape HTML characters (no colors)
        highlighted = escapedCode.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // Return HTML with a header bar (language label + copy button) and the highlighted code
    return `<div class="code-block-wrapper">
        <div class="code-block-header">
            <span>${lang || 'code'}</span>
            <button class="copy-code-btn" onclick="copyCodeBlock(this)">
                <i class="fas fa-copy"></i> Copy
            </button>
        </div>
        <pre><code class="hljs language-${lang}">${highlighted}</code></pre>
    </div>`;
};
// Enable line breaks in markdown (single newline = <br>)
marked.setOptions({ renderer, breaks: true });


// ── DOM Element References ─────────────────────────────────
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const chatMessages = document.getElementById('chatMessages');


// ── Start Chat with Pre-filled Message ─────────────────────
// Used when navigating from dashboard with a specific prompt
function startChat(initialMessage = '') {
    if (initialMessage) {
        if (messageInput) {
            messageInput.value = initialMessage;
            setTimeout(() => sendMessage(), 300);
        }
    }
}


// ── Study Tools Popup Menu ─────────────────────────────────
// Toggle the study tools dropdown menu (summarize, quiz, etc.)
const studyBtn = document.getElementById('studyBtn');
const studyPopup = document.getElementById('studyPopup');

if (studyBtn && studyPopup) {
    studyBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        studyPopup.classList.toggle('active');
    });
    // Close popup when clicking anywhere else on the page
    document.addEventListener('click', (e) => {
        if (studyPopup && !studyPopup.contains(e.target) && e.target !== studyBtn) {
            studyPopup.classList.remove('active');
        }
    });
}


// ══════════════════════════════════════════════════════════════
// MESSAGE DISPLAY
//
// Creates the visual message bubble in the chat area.
// User messages get a user avatar (right side).
// Bot messages get the character avatar (left side) + markdown rendering.
// ══════════════════════════════════════════════════════════════

function addMessage(text, sender, isLoading = false) {
    if (!chatMessages) return null;

    // Create the message container
    const wrapper = document.createElement('div');
    wrapper.className = `message-wrapper ${sender}`;
    if (isLoading) wrapper.id = `loading-${Date.now()}`;

    // Choose avatar image based on sender
    const avatarSrc = sender === 'bot' ? 'img/Head of Charcter.png' : 'img/Group 26.png';

    // Format the message text:
    // - Loading messages: show as-is (HTML with typing animation)
    // - Bot messages: convert Markdown to HTML (headers, lists, code, etc.)
    // - User messages: escape HTML to prevent XSS, convert newlines to <br>
    let displayText;
    if (isLoading) {
        displayText = text;
    } else if (sender === 'bot') {
        displayText = marked.parse(text);
    } else {
        displayText = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
    }

    // Detect text direction (Arabic = right-to-left, English = left-to-right)
    const dir = detectDirection(text);

    // Build the message HTML with avatar and bubble
    wrapper.innerHTML = `
        <div class="message-avatar">
            <img src="${avatarSrc}" alt="${sender}" onerror="this.style.display='none'">
        </div>
        <div class="message-bubble ${sender}" dir="${dir}">${displayText}</div>
    `;
    chatMessages.appendChild(wrapper);

    // Auto-scroll to the bottom of the chat
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrapper.id;
}


// ── Copy Code Block ────────────────────────────────────────
// Called when user clicks the "Copy" button on a code block.
// Copies the code text to clipboard and shows "Copied!" feedback.
function copyCodeBlock(btn) {
    const wrapper = btn.closest('.code-block-wrapper');
    const codeEl = wrapper.querySelector('code');
    const text = codeEl.textContent;
    navigator.clipboard.writeText(text).then(() => {
        btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.innerHTML = '<i class="fas fa-copy"></i> Copy';
            btn.classList.remove('copied');
        }, 2000);
    });
}


// ══════════════════════════════════════════════════════════════
// SENDING MESSAGES TO THE AI
//
// Flow:
//   1. User types a message and presses Enter (or clicks Send)
//   2. Message appears in chat as a user bubble
//   3. A "typing..." animation appears while waiting
//   4. Message is sent to /api/chat via POST request
//   5. Server forwards it to the AI agent and returns the response
//   6. Typing animation is replaced with the bot's response
// ══════════════════════════════════════════════════════════════

async function sendToBackend(message) {
    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                message: message,
                user_id: getUserId(),
                session_id: currentChatSessionId,  // Link message to current session
            })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        // Server returns the session ID (needed for new conversations)
        if (data.session_id) currentChatSessionId = data.session_id;
        return data.status === 'success' ? data.response : (data.message || 'Error occurred');
    } catch (e) {
        console.error('Backend:', e);
        return "Connection error - make sure the backend is running";
    }
}

async function sendMessage() {
    const message = messageInput ? messageInput.value.trim() : '';
    if (!message || isWaiting) return;  // Don't send empty messages or while waiting

    // Small delay to ensure UI is ready
    await new Promise(resolve => setTimeout(resolve, 100));

    // Show user's message in the chat
    addMessage(message, 'user');
    if (messageInput) { messageInput.value = ''; autoResizeTextarea(); }
    if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;

    // Lock input while waiting for response
    isWaiting = true;
    if (sendButton) sendButton.disabled = true;
    if (messageInput) messageInput.disabled = true;

    // Show typing animation
    const loadingId = addMessage(
        '<span class="typing-dot">Typing</span><span class="typing-dot">.</span><span class="typing-dot">.</span><span class="typing-dot">.</span>',
        'bot', true
    );

    try {
        // Send message to AI and get response
        const botReply = await sendToBackend(message);
        document.getElementById(loadingId)?.remove();  // Remove typing animation
        addMessage(botReply, 'bot');                    // Show bot's response
    } catch (error) {
        console.error('Error:', error);
        document.getElementById(loadingId)?.remove();
        addMessage("Connection error occurred", 'bot');
    }

    // Unlock input
    isWaiting = false;
    if (sendButton) sendButton.disabled = false;
    if (messageInput) { messageInput.disabled = false; messageInput.focus(); }
}


// ── Auto-Resize Text Input ─────────────────────────────────
// Automatically grows the text input as the user types more lines,
// up to a maximum height of 200px. After that, it scrolls internally.
function autoResizeTextarea() {
    if (!messageInput) return;
    messageInput.style.height = 'auto';
    const newHeight = Math.min(messageInput.scrollHeight, 200);
    messageInput.style.height = newHeight + 'px';
    messageInput.style.overflowY = messageInput.scrollHeight > 200 ? 'auto' : 'hidden';
}


// ── Input Event Listeners ──────────────────────────────────
if (sendButton) sendButton.addEventListener('click', sendMessage);
if (messageInput) {
    // Enter = send message, Shift+Enter = new line
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    // Auto-detect text direction as user types
    messageInput.addEventListener('input', () => {
        autoResizeTextarea();
        const val = messageInput.value.trim();
        if (val) {
            messageInput.dir = detectDirection(val);
            messageInput.style.textAlign = detectDirection(val) === 'rtl' ? 'right' : 'left';
        } else {
            messageInput.dir = 'auto';
            messageInput.style.textAlign = '';
        }
    });
}


// ── Typing Animation CSS ──────────────────────────────────
// Inject the blinking dots animation for the "typing..." indicator
const style = document.createElement('style');
style.textContent = `
    .typing-dot { display:inline-block; animation:blink 1.4s infinite both; }
    .typing-dot:nth-child(2){animation-delay:.2s}
    .typing-dot:nth-child(3){animation-delay:.4s}
    .typing-dot:nth-child(4){animation-delay:.6s}
    @keyframes blink{0%,100%{opacity:.2}20%{opacity:1}}
`;
if (document.head) document.head.appendChild(style);


// ══════════════════════════════════════════════════════════════
// CHAT SESSION MANAGEMENT (Saved in Supabase Database)
//
// Each conversation is saved as a "session" with a title.
// Users can:
//   - See a list of their past conversations (sidebar)
//   - Click on one to resume it (loads old messages)
//   - Rename sessions for easy identification
//   - Delete sessions they no longer need
// ══════════════════════════════════════════════════════════════

async function loadChatSessions() {
    // Fetch all chat sessions for the current user
    try {
        const res = await fetch(`${API_BASE}/api/chat/sessions?user_id=${encodeURIComponent(getUserId())}`, {
            headers: getAuthHeaders(),
        });
        const data = await res.json();
        if (data.status === 'success') {
            renderSessionList(data.sessions);
        }
    } catch (e) {
        console.error('Load sessions error:', e);
    }
}

function renderSessionList(sessions) {
    // Build the sidebar list of chat sessions
    const container = document.getElementById('chatHistoryList');
    if (!container) return;
    container.innerHTML = '';
    sessions.forEach(s => {
        const item = document.createElement('div');
        item.className = 'chat-history-item';
        item.dataset.sessionId = s.id;
        item.innerHTML = `
            <span class="chat-history-title" onclick="resumeSession('${s.id}')">${s.title}</span>
            <div class="chat-history-actions">
                <button class="chat-history-btn" onclick="renameSession('${s.id}')" title="Rename">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="chat-history-btn delete" onclick="deleteSession('${s.id}')" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        container.appendChild(item);
    });
}

async function resumeSession(sessionId) {
    // Load messages from a previous conversation
    currentChatSessionId = sessionId;
    if (chatMessages) chatMessages.innerHTML = '';
    try {
        const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages`);
        const data = await res.json();
        if (data.status === 'success') {
            data.messages.forEach(m => addMessage(m.content, m.role === 'user' ? 'user' : 'bot'));
        }
    } catch (e) {
        console.error('Resume session error:', e);
    }
}

async function deleteSession(sessionId) {
    if (!confirm('Delete this chat session?')) return;
    try {
        await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, { method: 'DELETE' });
        // If we deleted the currently active session, clear the chat area
        if (currentChatSessionId === sessionId) {
            currentChatSessionId = null;
            if (chatMessages) chatMessages.innerHTML = '';
        }
        loadChatSessions();  // Refresh the sidebar list
        showNotification('Session deleted', 'success');
    } catch (e) {
        console.error('Delete error:', e);
    }
}

async function renameSession(sessionId) {
    const newTitle = prompt('Enter new title:');
    if (!newTitle || !newTitle.trim()) return;
    try {
        await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/rename`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle.trim() }),
        });
        loadChatSessions();  // Refresh the sidebar list
        showNotification('Session renamed', 'success');
    } catch (e) {
        console.error('Rename error:', e);
    }
}

function newChat() {
    // Start a fresh conversation (no session ID = server creates a new one)
    currentChatSessionId = null;
    if (chatMessages) chatMessages.innerHTML = '';
}


// ── Page Initialization ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);

    // Check if there's an initial message to send (from dashboard "Start Chat" links)
    const initialRaw = params.get('initial');
    if (initialRaw) {
        setTimeout(() => startChat(initialRaw), 300);
    }

    // Check if there's a pending prompt from the Prompt Generator page
    if (params.get('prompt') === 'true') {
        const pendingPrompt = localStorage.getItem('chatnct_pending_prompt');
        if (pendingPrompt) {
            localStorage.removeItem('chatnct_pending_prompt');
            setTimeout(() => startChat(pendingPrompt), 500);
        }
    }

    // Load the user's chat history from the database
    loadChatSessions();
});
