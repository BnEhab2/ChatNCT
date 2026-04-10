// ══════════════════════════════════════════════════════════════
// ChatNCT — API Configuration
// Change API_BASE to your Render backend URL when deployed
// ══════════════════════════════════════════════════════════════

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? ''  // Local dev: same origin (proxy)
    : 'https://minadiaa-chatnct.hf.space';  // Production: Hugging Face backend URL
