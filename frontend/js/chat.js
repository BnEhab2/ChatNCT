const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? '' : 'https://chatnct.onrender.com';

// ══════════════════════════════════════════════════════════════
// ChatNCT — Chat Page Logic (Feature 1: Supabase Persistence)
// ══════════════════════════════════════════════════════════════

const API_URL = '/api/chat';
let isWaiting = false;
let currentChatSessionId = null;  // Supabase chat_sessions.id

// ── Chat Logic ─────────────────────────────────────────────
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const chatMessages = document.getElementById('chatMessages');

function startChat(initialMessage = '') {
    if (initialMessage) {
        if (messageInput) {
            messageInput.value = initialMessage;
            setTimeout(() => sendMessage(), 300);
        }
    }
}
const studyBtn = document.getElementById('studyBtn');
const studyPopup = document.getElementById('studyPopup');

if (studyBtn && studyPopup) {
    studyBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        studyPopup.classList.toggle('active');
    });
    document.addEventListener('click', (e) => {
        if (studyPopup && !studyPopup.contains(e.target) && e.target !== studyBtn) {
            studyPopup.classList.remove('active');
        }
    });
}

function addMessage(text, sender, isLoading = false) {
    if (!chatMessages) return null;
    const wrapper = document.createElement('div');
    wrapper.className = `message-wrapper ${sender}`;
    if (isLoading) wrapper.id = `loading-${Date.now()}`;
    const avatarSrc = sender === 'bot' ? 'img/Head of Charcter.png' : 'img/Group 26.png';

    let displayText;
    if (isLoading) {
        displayText = text;
    } else if (sender === 'bot') {
        displayText = marked.parse(text);
    } else {
        displayText = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
    }

    const dir = detectDirection(text);

    wrapper.innerHTML = `
        <div class="message-avatar">
            <img src="${avatarSrc}" alt="${sender}" onerror="this.style.display='none'">
        </div>
        <div class="message-bubble ${sender}" dir="${dir}">${displayText}</div>
    `;
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrapper.id;
}

async function sendToBackend(message) {
    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                message: message,
                user_id: getUserId(),
                session_id: currentChatSessionId,  // Feature 1: persist
            })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        // Track session ID returned from server
        if (data.session_id) currentChatSessionId = data.session_id;
        return data.status === 'success' ? data.response : (data.message || 'حدث خطأ');
    } catch (e) {
        console.error('Backend:', e);
        return "عذراً، تأكد إن الـ Backend شغال";
    }
}

async function sendMessage() {
    const message = messageInput ? messageInput.value.trim() : '';
    if (!message || isWaiting) return;

    await new Promise(resolve => setTimeout(resolve, 100));

    addMessage(message, 'user');
    if (messageInput) { messageInput.value = ''; autoResizeTextarea(); }
    if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;

    isWaiting = true;
    if (sendButton) sendButton.disabled = true;
    if (messageInput) messageInput.disabled = true;

    const loadingId = addMessage(
        '<span class="typing-dot">جاري الرد</span><span class="typing-dot">.</span><span class="typing-dot">.</span><span class="typing-dot">.</span>',
        'bot', true
    );

    try {
        const botReply = await sendToBackend(message);
        document.getElementById(loadingId)?.remove();
        addMessage(botReply, 'bot');
    } catch (error) {
        console.error('Error:', error);
        document.getElementById(loadingId)?.remove();
        addMessage("عذراً، حدث خطأ في الاتصال", 'bot');
    }

    isWaiting = false;
    if (sendButton) sendButton.disabled = false;
    if (messageInput) { messageInput.disabled = false; messageInput.focus(); }
}

function autoResizeTextarea() {
    if (!messageInput) return;
    messageInput.style.height = 'auto';
    const newHeight = Math.min(messageInput.scrollHeight, 200);
    messageInput.style.height = newHeight + 'px';
    messageInput.style.overflowY = messageInput.scrollHeight > 200 ? 'auto' : 'hidden';
}

if (sendButton) sendButton.addEventListener('click', sendMessage);
if (messageInput) {
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
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

// ── Typing Animation Styles ───────────────────────────────
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
// Feature 1: Chat Session Management (Supabase)
// ══════════════════════════════════════════════════════════════

async function loadChatSessions() {
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
        if (currentChatSessionId === sessionId) {
            currentChatSessionId = null;
            if (chatMessages) chatMessages.innerHTML = '';
        }
        loadChatSessions();
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
        loadChatSessions();
        showNotification('Session renamed', 'success');
    } catch (e) {
        console.error('Rename error:', e);
    }
}

function newChat() {
    currentChatSessionId = null;
    if (chatMessages) chatMessages.innerHTML = '';
}

// ── Init: Check URL params ─────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);

    // Initial message if passed from Start Chat links
    const initialRaw = params.get('initial');
    if (initialRaw) {
        setTimeout(() => startChat(initialRaw), 300);
    }

    // Handle pending prompt from Prompt Generator page
    if (params.get('prompt') === 'true') {
        const pendingPrompt = localStorage.getItem('chatnct_pending_prompt');
        if (pendingPrompt) {
            localStorage.removeItem('chatnct_pending_prompt');
            setTimeout(() => startChat(pendingPrompt), 500);
        }
    }

    // Feature 1: Load chat history from Supabase
    loadChatSessions();
});

