/**
 * Cloudflare Pages Function — API Proxy
 * 
 * Proxies all /api/* requests to the Koyeb backend.
 * This lets the frontend use relative paths (e.g. /api/chat)
 * without any code changes.
 */

const BACKEND_URL = 'https://REPLACE_WITH_KOYEB_URL';

export async function onRequest(context) {
    const url = new URL(context.request.url);
    const backendPath = url.pathname + url.search;
    const backendUrl = BACKEND_URL + backendPath;

    // Clone headers, remove host
    const headers = new Headers(context.request.headers);
    headers.delete('host');
    headers.set('X-Forwarded-Host', url.hostname);

    const init = {
        method: context.request.method,
        headers: headers,
    };

    // Forward body for non-GET methods
    if (context.request.method !== 'GET' && context.request.method !== 'HEAD') {
        init.body = context.request.body;
    }

    try {
        const response = await fetch(backendUrl, init);

        // Clone response and add CORS headers
        const newHeaders = new Headers(response.headers);
        newHeaders.set('Access-Control-Allow-Origin', '*');
        newHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
        newHeaders.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');

        // Handle CORS preflight
        if (context.request.method === 'OPTIONS') {
            return new Response(null, { status: 204, headers: newHeaders });
        }

        return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: newHeaders,
        });
    } catch (err) {
        return new Response(JSON.stringify({ 
            status: 'error', 
            message: 'Backend connection failed: ' + err.message 
        }), {
            status: 502,
            headers: { 'Content-Type': 'application/json' },
        });
    }
}
