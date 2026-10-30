// Finding and talking to the local backend, and asking the desktop shell
// for things a web page can't do. Shared by the island and the dashboard.

const tauri = window.__TAURI__;
export const IS_TAURI = !!(tauri || window.__TAURI_INTERNALS__);

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Escape text for an HTML template — every dynamic value goes through this. */
export function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[c]);
}

// ── Desktop shell (Tauri IPC) ───────────────────────────────────────────

export const shell = {
    invoke(cmd, args) {
        if (!tauri?.core?.invoke) return Promise.resolve(null);
        return tauri.core.invoke(cmd, args).catch(() => null);
    },
    /** Size the island window; the shell keeps it top-centre of its monitor. */
    setIslandSize(width, height) {
        return this.invoke('set_island_size', { width, height });
    },
    restartBackend() {
        return this.invoke('restart_backend');
    },
    openDashboard(base) {
        if (IS_TAURI && tauri?.core?.invoke) return this.invoke('open_dashboard');
        window.open(`${base}/dashboard.html`, '_blank');
        return Promise.resolve(null);
    },
};

// ── Backend (FastAPI on 127.0.0.1, port 8000–8011) ──────────────────────

const PORT_BASE = 8000;
const PORT_TRIES = 12;

export const backend = {
    // The island lives on the shell's own origin and must find the port;
    // the dashboard is served by the backend itself (same origin).
    base: IS_TAURI ? `http://127.0.0.1:${PORT_BASE}` : '',
    get wsUrl() {
        if (this.base) return this.base.replace(/^http/, 'ws') + '/ws';
        return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
    },

    /**
     * Probe the port range until the backend answers /health. It walks up
     * from 8000 when a port is taken, so the first healthy port wins.
     * `onSlow` fires every few seconds during a long cold start.
     */
    async discover(deadlineMs = 150000, onSlow = null) {
        if (!IS_TAURI) {
            try { return (await fetch('/health', { cache: 'no-store' })).ok; } catch { return false; }
        }
        const until = Date.now() + deadlineMs;
        let sweep = 0;
        while (Date.now() < until) {
            for (let port = PORT_BASE; port < PORT_BASE + PORT_TRIES; port++) {
                try {
                    const r = await fetch(`http://127.0.0.1:${port}/health`, { cache: 'no-store' });
                    if (r.ok) {
                        this.base = `http://127.0.0.1:${port}`;
                        return true;
                    }
                } catch { /* next port */ }
            }
            sweep += 1;
            if (onSlow && sweep % 6 === 0) onSlow();
            await sleep(500);
        }
        return false;
    },

    /** Wait for /health on the known port (after a restart). */
    async waitHealthy(deadlineMs = 150000) {
        const until = Date.now() + deadlineMs;
        while (Date.now() < until) {
            try {
                if ((await fetch(`${this.base}/health`, { cache: 'no-store' })).ok) return true;
            } catch { /* not up yet */ }
            await sleep(500);
        }
        return false;
    },

    async request(method, path, body) {
        const init = { method, cache: 'no-store', headers: {} };
        if (body !== undefined) {
            init.headers['Content-Type'] = 'application/json';
            init.body = JSON.stringify(body);
        }
        const r = await fetch(`${this.base}${path}`, init);
        const text = await r.text();
        let data = null;
        try { data = text ? JSON.parse(text) : null; } catch { data = text; }
        if (!r.ok) {
            const detail = (data && data.detail) || text || `HTTP ${r.status}`;
            throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
        }
        return data;
    },
    get(path) { return this.request('GET', path); },
    put(path, body) { return this.request('PUT', path, body); },
    post(path, body) { return this.request('POST', path, body); },
    del(path) { return this.request('DELETE', path); },

    /** First-run status, or null when the backend isn't answering. */
    async status() {
        try { return await this.get('/api/status'); } catch { return null; }
    },

    /** Open an allowlisted sign-up page in the system browser. */
    openExternal(target) {
        return this.post('/api/open-external', { target }).catch(() => null);
    },
};

/** Human names for tools, used in the island's status line. */
export function toolLabel(name) {
    const n = String(name || '');
    const known = {
        web_search: 'Searching the web',
        get_current_time: 'Checking the time',
        manage_memory: 'Remembering',
        search_past_conversations: 'Looking back through your chats',
        GMAIL_FETCH_EMAILS: 'Checking your inbox',
        GMAIL_SEND_EMAIL: 'Sending the email',
        GMAIL_REPLY_TO_THREAD: 'Sending the reply',
        GMAIL_CREATE_EMAIL_DRAFT: 'Saving a draft',
    };
    if (known[n]) return known[n];
    const app = appName(n);
    return app ? `Using ${app}` : 'Working on it';
}

/** "GOOGLECALENDAR_CREATE_EVENT" → "Google Calendar"; null for built-ins. */
export function appName(tool) {
    const m = /^([A-Z0-9]+)_/.exec(String(tool || ''));
    if (!m) return null;
    const names = {
        GMAIL: 'Gmail', GOOGLECALENDAR: 'Google Calendar', NOTION: 'Notion',
        SLACK: 'Slack', GITHUB: 'GitHub', GOOGLEDRIVE: 'Google Drive',
        GOOGLEDOCS: 'Google Docs', GOOGLESHEETS: 'Google Sheets', SPOTIFY: 'Spotify',
    };
    return names[m[1]] || m[1].charAt(0) + m[1].slice(1).toLowerCase();
}

/** "GOOGLECALENDAR_CREATE_EVENT" → "create event". */
export function actionName(tool) {
    return String(tool || '').replace(/^[A-Z0-9]+_/, '').replace(/_/g, ' ').toLowerCase();
}
