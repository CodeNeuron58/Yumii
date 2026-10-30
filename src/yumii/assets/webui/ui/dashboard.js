// The dashboard: her pipeline (Hear → Think → Speak), behaviour, tools,
// chats, memory, keys and a plain account of what leaves the machine.
// Every control saves on its own — no "save all" that could rewrite
// settings you never touched.

import { backend, esc, appName } from './backend.js';
import { icon } from './icons.js';

backend.base = '';   // served by the backend itself — same origin

const TABS = [
    ['models', 'Models'], ['behaviour', 'Behaviour'], ['tools', 'Tools'],
    ['chats', 'Chats'], ['memory', 'Memory'], ['keys', 'Keys'], ['privacy', 'Privacy'],
];

const D = {
    tab: 'models',
    settings: null,
    catalog: null,
    models: {},             // provider id → { models, source }
    thinkProvider: null,
    freeOnly: false,
    openDd: null,
    keyDraft: '',
    keyDrafts: {},
    notes: {},              // section → { text, kind }
    restart: false,
    sessions: null,
    transcripts: {},
    openChats: new Set(),
    facts: null,
    composio: null,
    slugDraft: '',
    editing: null,          // { kind, id, value }
    confirming: null,       // { kind, id }
};

const KEY_GROUPS = [
    ['Mind', ['NEBIUS_API_KEY', 'GROQ_API_KEY', 'GEMINI_API_KEY', 'OPENROUTER_API_KEY', 'DEEPSEEK_API_KEY',
        'XAI_API_KEY', 'TOGETHER_API_KEY', 'MISTRAL_API_KEY', 'OPENCODE_API_KEY', 'OLLAMA_API_KEY',
        'OPENAI_API_KEY', 'ANTHROPIC_API_KEY']],
    ['Voice', ['ELEVENLABS_API_KEY', 'ELEVENLABS_VOICE_ID', 'CAMB_API_KEY', 'CAMB_VOICE_ID']],
    ['Tools', ['TAVILY_API_KEY', 'COMPOSIO_API_KEY']],
];
const KEY_LABELS = {
    NEBIUS_API_KEY: 'Nebius Token Factory', GROQ_API_KEY: 'Groq', GEMINI_API_KEY: 'Google Gemini',
    OPENROUTER_API_KEY: 'OpenRouter', DEEPSEEK_API_KEY: 'DeepSeek', XAI_API_KEY: 'xAI (Grok)',
    TOGETHER_API_KEY: 'Together AI', MISTRAL_API_KEY: 'Mistral', OPENCODE_API_KEY: 'OpenCode Zen',
    OLLAMA_API_KEY: 'Ollama Cloud', OPENAI_API_KEY: 'OpenAI', ANTHROPIC_API_KEY: 'Anthropic',
    ELEVENLABS_API_KEY: 'ElevenLabs', ELEVENLABS_VOICE_ID: 'ElevenLabs voice ID',
    CAMB_API_KEY: 'CAMB.ai', CAMB_VOICE_ID: 'CAMB.ai voice ID',
    TAVILY_API_KEY: 'Tavily (web search)', COMPOSIO_API_KEY: 'Composio (apps)',
};
const VOICES = {
    af_heart: 'Warm and expressive — her default',
    af_bella: 'Bright and youthful',
    af_sky: 'Soft and airy',
    af_nicole: 'Calm, close to the mic',
    bf_emma: 'British, gentle',
    am_michael: 'Male, steady',
    bm_george: 'British male, deep',
};
const HITL = {
    external: ['Outside actions', 'She asks before anything that reaches the outside world — web searches, email, apps.'],
    always: ['Everything', 'She asks before every tool, even the time and her memory.'],
    never: ['Never', "She acts without asking. Only if you're sure."],
};

// ── Small helpers ───────────────────────────────────────────────────────

/** "Groq Whisper (cloud, fast)" → ["Groq Whisper", "cloud, fast"]. */
function splitLabel(label) {
    const m = /^(.*?)\s*\((.*)\)\s*$/.exec(String(label || ''));
    return m ? [m[1], m[2]] : [String(label || ''), ''];
}
const isCloud = (label) => /cloud/i.test(label || '');

function note(section) {
    const n = D.notes[section];
    return `<div class="note-line ${n ? n.kind : ''}">${n ? esc(n.text) : ''}</div>`;
}
function setNote(section, text, kind = '') {
    D.notes[section] = text ? { text, kind } : null;
}

function dropdown(id, current, options, empty = 'Nothing to pick yet') {
    const sel = options.find((o) => o.value === current);
    const label = sel ? sel.name : (current || 'Choose…');
    const items = options.length
        ? options.map((o) => `<button class="dd-opt ${o.value === current ? 'sel' : ''}" data-act="dd-pick" data-dd="${id}" data-value="${esc(o.value)}">
            <span class="txt"><span class="name">${esc(o.name)}</span>${o.note ? `<span class="note">${esc(o.note)}</span>` : ''}</span>
            ${o.tag ? `<span class="tag">${esc(o.tag)}</span>` : ''}</button>`).join('')
        : `<div class="dd-empty">${esc(empty)}</div>`;
    return `<div class="dd ${D.openDd === id ? 'open' : ''}">
        <button class="dd-btn" data-act="dd-toggle" data-dd="${id}"><span>${esc(label)}</span>${icon('chevronDown')}</button>
        <div class="dd-menu">${items}</div></div>`;
}

function seg(act, current, options) {
    return `<div class="seg">${options.map(([value, label]) =>
        `<button class="${value === current ? 'sel' : ''}" data-act="${act}" data-value="${esc(value)}">${esc(label)}</button>`).join('')}</div>`;
}

const isFree = (m) => String(m.id).includes(':free') || (m.cost_in === 0 && m.cost_out === 0);
function modelNote(m) {
    const bits = [];
    if (isFree(m)) bits.push('free');
    if (m.reasoning) bits.push('reasoning');
    if (m.context) bits.push(`${Math.round(m.context / 1000)}k context`);
    if (m.cost_in != null && !isFree(m)) bits.push(`$${m.cost_in} / $${m.cost_out} per M tokens`);
    return bits.join(' · ');
}

function currentProvider() {
    return (D.catalog?.providers || []).find((p) => p.id === D.thinkProvider) || null;
}

function mindName() {
    const cur = D.catalog?.current || {};
    const list = D.models[cur.provider]?.models || [];
    const m = list.find((x) => x.id === cur.model);
    if (m) return m.name;
    return cur.model ? cur.model.split('/').pop() : (cur.provider || '');
}

// ── Data ────────────────────────────────────────────────────────────────

async function loadSettings() {
    for (;;) {
        try {
            D.settings = await backend.get('/api/settings');
            return;
        } catch {
            document.getElementById('live-text').textContent = 'Waking Yumii up…';
            await new Promise((r) => setTimeout(r, 1500));
        }
    }
}

async function loadCatalog() {
    try {
        D.catalog = await backend.get('/api/llm/catalog');
        if (!D.thinkProvider) D.thinkProvider = D.catalog.current?.provider || null;
        if (D.catalog.current?.provider) await loadModels(D.catalog.current.provider);
        if (D.thinkProvider && D.thinkProvider !== D.catalog.current?.provider) await loadModels(D.thinkProvider);
    } catch (e) {
        setNote('think', `Couldn't load the model catalog: ${e.message}`, 'err');
    }
}

async function loadModels(provider, force = false) {
    if (!provider || (D.models[provider] && !force)) return;
    try {
        D.models[provider] = await backend.get(`/api/llm/models/${encodeURIComponent(provider)}`);
    } catch (e) {
        D.models[provider] = { models: [], source: 'error', error: e.message };
    }
}

async function savePref(key, value, section) {
    try {
        const res = await backend.put('/api/settings', { preferences: { [key]: value } });
        D.settings.preferences[key] = value;
        if (res?.restart_required) {
            D.restart = true;
            setNote(section, 'Saved. Restart Yumii to apply.', 'warn');
        } else {
            setNote(section, 'Saved — applies from her next reply.', 'ok');
        }
    } catch (e) {
        setNote(section, `Couldn't save: ${e.message}`, 'err');
    }
    render();
}

// ── Views ───────────────────────────────────────────────────────────────

function viewModels() {
    const s = D.settings;
    const p = s.preferences;
    const sttLabels = s.labels?.STT_PROVIDER || {};
    const ttsLabels = s.labels?.TTS_PROVIDER || {};

    const ears = (s.choices.STT_PROVIDER || []).map((v) => {
        const [name, detail] = splitLabel(sttLabels[v] || v);
        return { value: v, name, note: detail };
    });
    const earsCloud = isCloud(sttLabels[p.STT_PROVIDER]);
    const whisper = p.STT_PROVIDER === 'local'
        ? `<div class="row-inline"><span class="mono-note">Size</span>${seg('whisper', p.WHISPER_MODEL_SIZE, [['tiny', 'Tiny'], ['base', 'Base'], ['small', 'Small']])}</div>`
        : '';

    const voices = (s.choices.TTS_PROVIDER || []).map((v) => {
        const [name, detail] = splitLabel(ttsLabels[v] || v);
        return { value: v, name, note: detail };
    });
    const voiceCloud = isCloud(ttsLabels[p.TTS_PROVIDER]);

    const providers = (D.catalog?.providers || []).map((pr) => {
        const [name, detail] = splitLabel(pr.name);
        const key = pr.connected ? (pr.key_optional ? 'no key needed' : 'key saved') : 'needs a key';
        return {
            value: pr.id,
            name,
            note: [detail, key].filter(Boolean).join(' · '),
            tag: pr.model_count != null ? String(pr.model_count) : '',
        };
    });
    const prov = currentProvider();
    const data = D.models[D.thinkProvider] || { models: [] };
    const live = data.source === 'live';
    let models = data.models || [];
    if (D.freeOnly && !live) models = models.filter(isFree);
    const modelOpts = models.map((m) => ({ value: m.id, name: m.name, note: modelNote(m) }));
    const cur = D.catalog?.current || {};
    const curModel = D.thinkProvider === cur.provider ? cur.model : null;
    const needsKey = prov && !prov.connected && !prov.key_optional;
    const thinkCloud = D.thinkProvider !== 'ollama';

    const personalities = (s.choices.PERSONALITY || []).map((v) => {
        const desc = s.descriptions?.PERSONALITY?.[v] || '';
        return `<button class="choice ${v === p.PERSONALITY ? 'sel' : ''}" data-act="persona" data-value="${esc(v)}">
            <span class="ava">${esc(v.slice(0, 2).toUpperCase())}</span>
            <span class="name">${esc(v.charAt(0).toUpperCase() + v.slice(1))}</span>
            <span class="desc">${esc(desc)}</span><span class="radio"></span></button>`;
    }).join('');

    const kokoro = /kokoro/i.test(p.TTS_PROVIDER || '');
    const voiceRows = (s.choices.KOKORO_VOICE || []).map((v) => {
        const [accent, name] = v.split('_');
        const who = { af: 'US', am: 'US', bf: 'UK', bm: 'UK' }[accent] || '';
        return `<button class="choice ${v === p.KOKORO_VOICE ? 'sel' : ''}" data-act="voice" data-value="${esc(v)}" ${kokoro ? '' : 'disabled'}>
            <span class="ava">${esc(who)}</span>
            <span class="name">${esc(name.charAt(0).toUpperCase() + name.slice(1))}</span>
            <span class="desc">${esc(VOICES[v] || '')}</span><span class="radio"></span></button>`;
    }).join('');

    return `
    <div class="pipeline">
        <div class="stage ${D.openDd === 'stt' ? 'focus' : ''}">
            <div class="stage-head"><span class="step">${icon('ear', 13)} 01 Hear</span>
                <span class="where ${earsCloud ? 'cloud' : ''}">${earsCloud ? 'cloud' : 'on device'}</span></div>
            ${dropdown('stt', p.STT_PROVIDER, ears)}
            <div class="chips"><span class="chip">Silero VAD · always local</span><span class="chip">Smart Turn</span></div>
            ${whisper}
            ${note('hear')}
        </div>
        <div class="arrow">${icon('arrowRight', 16)}</div>
        <div class="stage ${['provider', 'model'].includes(D.openDd) ? 'focus' : ''}">
            <div class="stage-head"><span class="step">${icon('brain', 13)} 02 Think</span>
                <span class="where ${thinkCloud ? 'cloud' : ''}">${thinkCloud ? 'cloud' : 'local or cloud'}</span></div>
            ${dropdown('provider', D.thinkProvider, providers)}
            ${dropdown('model', curModel, modelOpts, data.error || (D.freeOnly ? 'No free models here — turn off "Free only".' : 'No models yet — try Refresh.'))}
            ${needsKey ? `<input class="field" type="password" data-field="think-key" placeholder="Paste your ${esc(prov.name)} key, then pick a model" autocomplete="off" spellcheck="false">` : ''}
            <div class="chips">
                <button class="chip ${D.freeOnly ? 'ok' : ''}" data-act="free-only" style="border:none;cursor:pointer">Free only</button>
                <button class="chip" data-act="refresh" style="border:none;cursor:pointer">${icon('refresh', 11)} Refresh</button>
                ${D.thinkProvider === 'nebius' ? '<span class="chip ok">Reasoning off · warm start</span>' : ''}
            </div>
            ${note('think')}
        </div>
        <div class="arrow">${icon('arrowRight', 16)}</div>
        <div class="stage ${D.openDd === 'tts' ? 'focus' : ''}">
            <div class="stage-head"><span class="step">${icon('speaker', 13)} 03 Speak</span>
                <span class="where ${voiceCloud ? 'cloud' : ''}">${voiceCloud ? 'cloud' : 'on device'}</span></div>
            ${dropdown('tts', p.TTS_PROVIDER, voices)}
            <div class="chips"><span class="chip">Streaming</span><span class="chip">Sentence by sentence</span></div>
            ${note('speak')}
        </div>
    </div>
    <div class="cols">
        <section class="panel">
            <div class="panel-head"><span class="panel-title">Voice</span>
                <span class="mono-note">${kokoro ? 'Kokoro · on device' : 'Kokoro voices'}</span></div>
            ${kokoro ? '' : '<p class="panel-note">These apply to the Kokoro voice. Switch Speak to Kokoro to use them.</p>'}
            <div class="choices">${voiceRows}</div>
            ${note('voice')}
        </section>
        <section class="panel">
            <div class="panel-head"><span class="panel-title">Personality</span>
                <span class="mono-note">applies live</span></div>
            <div class="choices">${personalities}</div>
            <p class="panel-note">You can also just ask her — "switch to tsundere".</p>
            ${note('persona')}
        </section>
    </div>`;
}

function viewBehaviour() {
    const p = D.settings.preferences;
    const show = p.UI_SHOW_REPLY !== 'off';
    const hitl = HITL[p.HITL_MODE] || HITL.external;
    return `
    <div class="cols">
        <section class="panel">
            <span class="panel-title">The island</span>
            <div class="grid-rows">
                <span class="label">Hide answers after</span>
                ${seg('hide-after', p.UI_HIDE_AFTER || '4', [['2', '2 s'], ['4', '4 s'], ['6', '6 s'], ['8', '8 s'], ['never', 'Never']])}
            </div>
            <div class="toggle-row">
                <span>Show her reply under the bar<small>Off: the strip only, her voice carries the answer.</small></span>
                <button class="switch ${show ? 'on' : ''}" data-act="show-reply" aria-label="Show her reply"></button>
            </div>
            <p class="panel-note">Hovering an answer keeps it open; the pin keeps it open until you close it.</p>
            ${note('island')}
        </section>
        <section class="panel">
            <span class="panel-title">Asking first</span>
            ${seg('hitl', p.HITL_MODE, Object.entries(HITL).map(([k, v]) => [k, v[0]]))}
            <p class="panel-note">${esc(hitl[1])} Answer with a click, or just say <b>"yes"</b> or <b>"no"</b>.</p>
            ${note('hitl')}
        </section>
    </div>
    <div class="cols">
        <section class="panel">
            <span class="panel-title">Listening</span>
            <p class="panel-note"><b>Always listening — no wake word.</b> Talk any time, and interrupt her mid-sentence;
            she stops and listens. Mute with the mic button on the island, or say "mute".</p>
        </section>
        <section class="panel">
            <span class="panel-title">Shortcuts</span>
            <div class="grid-rows">
                <span class="label"><kbd>Ctrl ⇧ Space</kbd></span><span>Show or hide her</span>
                <span class="label">"stop"</span><span>Stop talking</span>
                <span class="label">"repeat"</span><span>Say that again</span>
                <span class="label">"new chat"</span><span>Start a fresh conversation</span>
                <span class="label">"mute" / "unmute"</span><span>Mic off / on</span>
            </div>
        </section>
    </div>`;
}

function viewTools() {
    const creds = D.settings.credentials || {};
    const tavily = creds.TAVILY_API_KEY?.set;
    const c = D.composio;
    let apps;
    if (!c) apps = '<div class="empty">Loading…</div>';
    else if (!c.toolkits.length) apps = '<div class="empty">No apps connected yet.</div>';
    else {
        apps = `<div class="list">${c.toolkits.map((t) => {
            const confirming = D.confirming?.kind === 'app' && D.confirming.id === t;
            return `<div class="li"><div class="main"><span class="title">${esc(appName(`${t}_X`) || t)}</span>
                <span class="meta">${esc(t)}</span></div><div class="acts">${confirming
                ? `<span class="mono-note">She loses these tools now.</span>
                   <button class="btn sm danger" data-act="app-off" data-id="${esc(t)}">Disable</button>
                   <button class="btn sm ghost" data-act="cancel">Keep</button>`
                : `<button class="btn sm ghost" data-act="confirm-app" data-id="${esc(t)}">Disable</button>`}</div></div>`;
        }).join('')}</div>`;
    }
    const quick = [['GMAIL', 'Gmail'], ['GOOGLECALENDAR', 'Google Calendar'], ['NOTION', 'Notion'], ['GITHUB', 'GitHub'], ['SLACK', 'Slack']];
    return `
    <div class="cols">
        <section class="panel">
            <div class="panel-head"><span class="panel-title">Web search</span>
                <span class="chip ${tavily ? 'ok' : ''}">${tavily ? 'Tavily' : 'DuckDuckGo'}</span></div>
            <p class="panel-note">${tavily
                ? 'Searches go to <b>Tavily</b>, which also returns a short answer she can speak. DuckDuckGo stays as the fallback.'
                : 'Searches use <b>DuckDuckGo</b> (free, no key). A Tavily key gives better results and a short spoken-ready answer.'}</p>
            ${tavily ? '' : `<div class="row-inline"><button class="btn sm ghost" data-act="tavily">Get a Tavily key ${icon('external', 12)}</button>
                <button class="btn sm ghost" data-act="go-keys">Add it in Keys</button></div>`}
        </section>
        <section class="panel">
            <div class="panel-head"><span class="panel-title">Apps</span>
                <span class="mono-note">via Composio</span></div>
            <p class="panel-note">${c?.key_set
                ? 'Connect an app and she can use it — always asking first.'
                : 'Add a <b>Composio</b> key in Keys first (free at app.composio.dev), then connect apps here.'}</p>
            ${apps}
            <div class="row-inline">${quick.map(([slug, name]) => `<button class="btn sm ghost" data-act="connect" data-id="${slug}">${esc(name)}</button>`).join('')}</div>
            <div class="row-inline">
                <input class="field" style="flex:1;min-width:160px" data-field="slug" placeholder="Any toolkit slug, e.g. SPOTIFY" autocomplete="off" spellcheck="false">
                <button class="btn sm" data-act="connect-custom">Connect</button>
            </div>
            ${note('apps')}
        </section>
    </div>`;
}

function viewChats() {
    const rows = D.sessions;
    if (!rows) return '<section class="panel"><div class="empty">Loading…</div></section>';
    if (!rows.length) return '<section class="panel"><div class="empty">No conversations yet — go talk to her.</div></section>';
    const items = rows.map((s) => {
        const date = (s.last_active_at || s.created_at || '').slice(0, 16).replace('T', ' ');
        const editing = D.editing?.kind === 'chat' && D.editing.id === s.id;
        const confirming = D.confirming?.kind === 'chat' && D.confirming.id === s.id;
        const open = D.openChats.has(s.id);
        const title = editing
            ? `<input class="field" data-field="edit" value="${esc(D.editing.value)}" autocomplete="off">`
            : `<span class="title">${esc(s.name)}${s.active ? '<span class="badge-now">Now</span>' : ''}</span>`;
        let acts;
        if (editing) {
            acts = '<button class="btn sm primary" data-act="save-edit">Save</button><button class="btn sm ghost" data-act="cancel">Cancel</button>';
        } else if (confirming) {
            acts = `<span class="mono-note">Delete for good?</span><button class="btn sm danger" data-act="chat-del" data-id="${esc(s.id)}">Delete</button><button class="btn sm ghost" data-act="cancel">Keep</button>`;
        } else {
            acts = `<button class="btn sm ghost" data-act="chat-view" data-id="${esc(s.id)}">${open ? 'Hide' : 'View'}</button>
                ${s.active ? '' : `<button class="btn sm ghost" data-act="chat-resume" data-id="${esc(s.id)}">Resume</button>`}
                <button class="btn sm ghost" data-act="chat-rename" data-id="${esc(s.id)}" title="Rename">${icon('pencil', 12)}</button>
                <button class="btn sm ghost" data-act="confirm-chat" data-id="${esc(s.id)}" title="Delete">${icon('trash', 12)}</button>`;
        }
        let transcript = '';
        if (open) {
            const msgs = D.transcripts[s.id];
            transcript = `<div class="transcript">${!msgs ? '<div class="empty">Loading…</div>'
                : !msgs.length ? '<div class="empty">No messages in this one.</div>'
                : msgs.map((m) => (m.role === 'event'
                    ? `<p class="msg event">${esc(m.text)}</p>`
                    : `<p class="msg"><span class="who">${m.role === 'user' ? 'You' : 'Yumii'}</span>${esc(m.text)}</p>`)).join('')}</div>`;
        }
        return `<div class="li"><div class="main">${title}<span class="meta">${esc(date)} · ${s.message_count} messages</span></div>
            <div class="acts">${acts}</div></div>${transcript}`;
    }).join('');
    return `<section class="panel"><div class="panel-head"><span class="panel-title">Conversations</span>
        <span class="mono-note">${rows.length} saved on this computer</span></div>
        <div class="list">${items}</div>${note('chats')}</section>`;
}

function viewMemory() {
    const facts = D.facts;
    let body;
    if (!facts) body = '<div class="empty">Loading…</div>';
    else if (!facts.length) body = '<div class="empty">Nothing remembered yet. Tell her something about you — "remember, my sister\'s name is Riya."</div>';
    else {
        body = `<div class="list">${facts.map((f) => {
            const editing = D.editing?.kind === 'fact' && D.editing.id === f.id;
            const confirming = D.confirming?.kind === 'fact' && D.confirming.id === f.id;
            const main = editing
                ? `<input class="field" data-field="edit" value="${esc(D.editing.value)}" autocomplete="off">`
                : `<span class="title">${esc(f.fact)}</span>`;
            let acts;
            if (editing) acts = '<button class="btn sm primary" data-act="save-edit">Save</button><button class="btn sm ghost" data-act="cancel">Cancel</button>';
            else if (confirming) acts = `<span class="mono-note">She'll forget this.</span><button class="btn sm danger" data-act="fact-del" data-id="${esc(f.id)}">Forget</button><button class="btn sm ghost" data-act="cancel">Keep</button>`;
            else acts = `<button class="btn sm ghost" data-act="fact-edit" data-id="${esc(f.id)}" title="Edit">${icon('pencil', 12)}</button>
                <button class="btn sm ghost" data-act="confirm-fact" data-id="${esc(f.id)}" title="Forget">${icon('trash', 12)}</button>`;
            return `<div class="li"><span class="cat">${esc(f.category)}</span><div class="main">${main}</div><div class="acts">${acts}</div></div>`;
        }).join('')}</div>`;
    }
    return `<section class="panel"><div class="panel-head"><span class="panel-title">What she knows about you</span>
        <span class="mono-note">stored on this computer</span></div>${body}${note('memory')}</section>`;
}

function viewKeys() {
    const creds = D.settings.credentials || {};
    const known = new Set(KEY_GROUPS.flatMap(([, keys]) => keys));
    const extra = Object.keys(creds).filter((k) => !known.has(k));
    const groups = [...KEY_GROUPS, ...(extra.length ? [['Other', extra]] : [])];
    const rows = groups.map(([group, keys]) => {
        const items = keys.filter((k) => k in creds).map((k) => {
            const c = creds[k];
            const draft = D.keyDrafts[k] || '';
            return `<div class="li"><div class="main"><span class="title">${esc(KEY_LABELS[k] || k)}</span>
                <span class="meta">${esc(k)}</span></div>
                <span class="key-status ${c.set ? 'set' : ''}">${c.set ? esc(c.masked) : 'not set'}</span>
                <input class="field" style="width:220px" type="password" data-field="key:${esc(k)}" value="${esc(draft)}"
                    placeholder="${c.set ? 'New key to replace' : 'Paste key'}" autocomplete="off" spellcheck="false">
                <button class="btn sm ${draft ? 'primary' : 'ghost'}" data-act="key-save" data-id="${esc(k)}" ${draft ? '' : 'disabled'}>Save</button></div>`;
        }).join('');
        return items ? `<div class="group-label">${esc(group)}</div><div class="list">${items}</div>` : '';
    }).join('');
    return `<section class="panel"><div class="panel-head"><span class="panel-title">Keys</span>${icon('key', 15)}</div>
        <p class="panel-note">Write-only here. Keys live in <b>~/.yumii/auth.json</b>, readable only by your user — never in a repo, never sent anywhere but their own provider.</p>
        ${rows}${note('keys')}</section>`;
}

function viewPrivacy() {
    const s = D.settings;
    const p = s.preferences;
    const sttLabel = s.labels?.STT_PROVIDER?.[p.STT_PROVIDER] || p.STT_PROVIDER;
    const ttsLabel = s.labels?.TTS_PROVIDER?.[p.TTS_PROVIDER] || p.TTS_PROVIDER;
    const prov = (D.catalog?.providers || []).find((x) => x.id === D.catalog?.current?.provider);
    const localMind = D.catalog?.current?.provider === 'ollama';
    const tavily = s.credentials?.TAVILY_API_KEY?.set;
    const row = (out, ic, title, sub) => `<div class="flow-row"><span class="ic ${out ? 'out' : ''}">${icon(ic, 14)}</span>
        <span>${title}<small>${sub}</small></span></div>`;
    return `<div class="cols">
        <section class="panel"><span class="panel-title">Stays on this computer</span><div class="flow">
            ${row(false, 'brain', 'Her memory and every conversation', 'SQLite files in ~/.yumii/memory — the dashboard shows all of it, and you can delete any of it.')}
            ${row(false, 'key', 'Your keys', '~/.yumii/auth.json, owner-only.')}
            ${row(false, 'ear', 'Listening for your voice', 'Speech detection always runs locally, on every audio frame.')}
            ${isCloud(sttLabel) ? '' : row(false, 'mic', 'Turning speech into text', `${esc(splitLabel(sttLabel)[0])} runs on this computer.`)}
            ${isCloud(ttsLabel) ? '' : row(false, 'speaker', 'Her voice', `${esc(splitLabel(ttsLabel)[0])} speaks on this computer.`)}
        </div></section>
        <section class="panel"><span class="panel-title">Leaves this computer</span><div class="flow">
            ${localMind ? row(false, 'brain', 'Her thinking', 'Ollama — local if you pointed it at your own server.')
                : row(true, 'brain', `What you say, as text → ${esc(prov ? splitLabel(prov.name)[0] : 'your model provider')}`, 'So she can think. Only the conversation and what she remembers about you.')}
            ${isCloud(sttLabel) ? row(true, 'mic', `Your audio → ${esc(splitLabel(sttLabel)[0])}`, 'Each finished sentence is sent to be transcribed.') : ''}
            ${isCloud(ttsLabel) ? row(true, 'speaker', `Her replies → ${esc(splitLabel(ttsLabel)[0])}`, 'To be spoken.') : ''}
            ${row(true, 'search', `Web searches → ${tavily ? 'Tavily' : 'DuckDuckGo'}`, 'Only when she searches — and she asks first.')}
            ${row(true, 'mail', 'Connected apps → Composio', 'Only when she uses one — and she asks first.')}
        </div></section>
    </div>`;
}

const VIEWS = {
    models: viewModels, behaviour: viewBehaviour, tools: viewTools, chats: viewChats,
    memory: viewMemory, keys: viewKeys, privacy: viewPrivacy,
};

// ── Render ──────────────────────────────────────────────────────────────

const mainEl = document.getElementById('main');

function render() {
    document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === D.tab));
    document.getElementById('banner').classList.toggle('show', D.restart);
    const name = mindName();
    document.getElementById('live-dot').className = `dot ${name ? 'ok' : ''}`;
    document.getElementById('live-text').textContent = name ? `thinking with ${name}` : 'connecting…';
    if (!D.settings) return;

    const active = document.activeElement;
    const field = active?.dataset?.field;
    const caret = field ? active.selectionStart : null;

    mainEl.innerHTML = `<div class="view active">${VIEWS[D.tab]()}</div>`;

    // Re-fill drafts, restore focus to the field being typed in.
    mainEl.querySelectorAll('[data-field]').forEach((el) => {
        const f = el.dataset.field;
        if (f === 'think-key') el.value = D.keyDraft;
        if (f === 'slug') el.value = D.slugDraft;
    });
    if (field) {
        const el = mainEl.querySelector(`[data-field="${CSS.escape(field)}"]`);
        if (el) {
            el.focus();
            try { el.setSelectionRange(caret, caret); } catch { /* not a text field */ }
        }
    }
}

async function showTab(tab) {
    D.tab = tab;
    history.replaceState(null, '', `#${tab}`);
    D.openDd = null;
    D.editing = null;
    D.confirming = null;
    render();
    if (tab === 'chats') { D.sessions = await backend.get('/api/sessions').catch(() => []); render(); }
    if (tab === 'memory') { D.facts = await backend.get('/api/facts').catch(() => []); render(); }
    if (tab === 'tools') { D.composio = await backend.get('/api/composio/status').catch(() => ({ key_set: false, toolkits: [] })); render(); }
    if (tab === 'keys' || tab === 'privacy' || tab === 'tools') { D.settings = await backend.get('/api/settings').catch(() => D.settings); render(); }
}

// ── Actions ─────────────────────────────────────────────────────────────

async function pickDropdown(dd, value) {
    D.openDd = null;
    if (dd === 'stt') return savePref('STT_PROVIDER', value, 'hear');
    if (dd === 'tts') return savePref('TTS_PROVIDER', value, 'speak');
    if (dd === 'provider') {
        D.thinkProvider = value;
        D.keyDraft = '';
        setNote('think', 'Loading models…');
        render();
        await loadModels(value);
        setNote('think', value === D.catalog?.current?.provider ? '' : 'Pick a model to switch.');
        return render();
    }
    if (dd === 'model') return selectModel(value);
    return render();
}

async function selectModel(model) {
    const prov = currentProvider();
    const body = { provider: D.thinkProvider, model };
    if (D.keyDraft.trim()) body.api_key = D.keyDraft.trim();
    if (prov && !prov.connected && !prov.key_optional && !body.api_key) {
        setNote('think', `Paste your ${prov.name} key first.`, 'warn');
        return render();
    }
    setNote('think', 'Saving…');
    render();
    try {
        await backend.post('/api/llm/select', body);
        D.keyDraft = '';
        await loadCatalog();
        setNote('think', `She thinks with ${mindName()} from her next reply.`, 'ok');
    } catch (e) {
        setNote('think', `Couldn't switch: ${e.message}`, 'err');
    }
    render();
}

const ACTS = {
    'dd-toggle': (el) => { D.openDd = D.openDd === el.dataset.dd ? null : el.dataset.dd; render(); },
    'dd-pick': (el) => pickDropdown(el.dataset.dd, el.dataset.value),
    whisper: (el) => savePref('WHISPER_MODEL_SIZE', el.dataset.value, 'hear'),
    voice: (el) => savePref('KOKORO_VOICE', el.dataset.value, 'voice'),
    persona: (el) => savePref('PERSONALITY', el.dataset.value, 'persona'),
    'hide-after': (el) => savePref('UI_HIDE_AFTER', el.dataset.value, 'island'),
    'show-reply': () => savePref('UI_SHOW_REPLY', D.settings.preferences.UI_SHOW_REPLY === 'off' ? 'on' : 'off', 'island'),
    hitl: (el) => savePref('HITL_MODE', el.dataset.value, 'hitl'),
    'free-only': () => { D.freeOnly = !D.freeOnly; render(); },
    refresh: async () => {
        setNote('think', 'Refreshing the catalog…');
        render();
        try {
            const res = await backend.post('/api/llm/refresh');
            D.models = {};
            await loadCatalog();
            setNote('think', `Catalog updated — ${res?.models ?? 'all'} models.`, 'ok');
        } catch (e) {
            setNote('think', `Refresh failed: ${e.message}`, 'err');
        }
        render();
    },
    tavily: () => backend.openExternal('tavily'),
    'go-keys': () => showTab('keys'),
    connect: (el) => connectApp(el.dataset.id),
    'connect-custom': () => connectApp(D.slugDraft.trim().toUpperCase()),
    'confirm-app': (el) => { D.confirming = { kind: 'app', id: el.dataset.id }; render(); },
    'app-off': async (el) => {
        D.confirming = null;
        try { await backend.del(`/api/composio/toolkits/${encodeURIComponent(el.dataset.id)}`); } catch (e) { setNote('apps', e.message, 'err'); }
        D.composio = await backend.get('/api/composio/status').catch(() => D.composio);
        render();
    },
    'chat-view': async (el) => {
        const id = el.dataset.id;
        if (D.openChats.has(id)) { D.openChats.delete(id); return render(); }
        D.openChats.add(id);
        render();
        D.transcripts[id] = await backend.get(`/api/sessions/${encodeURIComponent(id)}/messages`).catch(() => []);
        render();
    },
    'chat-resume': async (el) => {
        try {
            await backend.post(`/api/sessions/${encodeURIComponent(el.dataset.id)}/resume`);
            setNote('chats', 'Resumed — she picks up that conversation.', 'ok');
        } catch (e) { setNote('chats', e.message, 'err'); }
        D.sessions = await backend.get('/api/sessions').catch(() => D.sessions);
        render();
    },
    'chat-rename': (el) => {
        const s = D.sessions.find((x) => x.id === el.dataset.id);
        D.editing = { kind: 'chat', id: el.dataset.id, value: s?.name || '' };
        render();
        mainEl.querySelector('[data-field="edit"]')?.focus();
    },
    'confirm-chat': (el) => { D.confirming = { kind: 'chat', id: el.dataset.id }; render(); },
    'chat-del': async (el) => {
        D.confirming = null;
        try { await backend.del(`/api/sessions/${encodeURIComponent(el.dataset.id)}`); } catch (e) { setNote('chats', e.message, 'err'); }
        D.sessions = await backend.get('/api/sessions').catch(() => D.sessions);
        render();
    },
    'fact-edit': (el) => {
        const f = D.facts.find((x) => String(x.id) === el.dataset.id);
        D.editing = { kind: 'fact', id: f?.id, value: f?.fact || '' };
        render();
        mainEl.querySelector('[data-field="edit"]')?.focus();
    },
    'confirm-fact': (el) => {
        const f = D.facts.find((x) => String(x.id) === el.dataset.id);
        D.confirming = { kind: 'fact', id: f?.id };
        render();
    },
    'fact-del': async () => {
        const id = D.confirming?.id;
        D.confirming = null;
        try { await backend.del(`/api/facts/${encodeURIComponent(id)}`); } catch (e) { setNote('memory', e.message, 'err'); }
        D.facts = await backend.get('/api/facts').catch(() => D.facts);
        render();
    },
    'save-edit': () => saveEdit(),
    cancel: () => { D.editing = null; D.confirming = null; render(); },
    'key-save': async (el) => {
        const key = el.dataset.id;
        const value = (D.keyDrafts[key] || '').trim();
        if (!value) return;
        try {
            await backend.put('/api/settings', { credentials: { [key]: value } });
            D.keyDrafts[key] = '';
            D.restart = true;
            setNote('keys', `${KEY_LABELS[key] || key} saved. Restart Yumii to apply.`, 'warn');
            D.settings = await backend.get('/api/settings').catch(() => D.settings);
        } catch (e) {
            setNote('keys', `Couldn't save: ${e.message}`, 'err');
        }
        render();
    },
};

async function saveEdit() {
    const e = D.editing;
    if (!e) return;
    const value = (e.value || '').trim();
    if (!value) return;
    try {
        if (e.kind === 'chat') {
            await backend.put(`/api/sessions/${encodeURIComponent(e.id)}`, { name: value });
            D.sessions = await backend.get('/api/sessions').catch(() => D.sessions);
        } else {
            await backend.put(`/api/facts/${encodeURIComponent(e.id)}`, { fact: value });
            D.facts = await backend.get('/api/facts').catch(() => D.facts);
        }
    } catch (err) {
        setNote(e.kind === 'chat' ? 'chats' : 'memory', err.message, 'err');
    }
    D.editing = null;
    render();
}

async function connectApp(slug) {
    if (!slug) return;
    setNote('apps', `Getting a ${slug} sign-in link…`);
    render();
    try {
        const res = await backend.post('/api/composio/connect', { toolkit: slug });
        setNote('apps', `A ${res.toolkit} sign-in page opened in your browser. Finish there, then just talk — the tools are already loaded.`, 'ok');
        D.slugDraft = '';
        D.composio = await backend.get('/api/composio/status').catch(() => D.composio);
    } catch (e) {
        setNote('apps', `Couldn't connect: ${e.message}`, 'err');
    }
    render();
}

mainEl.addEventListener('click', (e) => {
    const el = e.target.closest('[data-act]');
    if (!el || el.disabled) return;
    e.stopPropagation();
    ACTS[el.dataset.act]?.(el, e);
});

mainEl.addEventListener('input', (e) => {
    const f = e.target.dataset?.field;
    if (!f) return;
    if (f === 'think-key') D.keyDraft = e.target.value;
    else if (f === 'slug') D.slugDraft = e.target.value;
    else if (f === 'edit' && D.editing) D.editing.value = e.target.value;
    else if (f.startsWith('key:')) {
        const key = f.slice(4);
        const had = !!(D.keyDrafts[key] || '').trim();
        D.keyDrafts[key] = e.target.value;
        if (had !== !!e.target.value.trim()) render();   // enable / disable Save
    }
});

mainEl.addEventListener('keydown', (e) => {
    const f = e.target.dataset?.field;
    if (!f) return;
    if (e.key === 'Escape') { D.editing = null; D.openDd = null; render(); return; }
    if (e.key !== 'Enter') return;
    if (f === 'edit') saveEdit();
    else if (f === 'slug') connectApp(D.slugDraft.trim().toUpperCase());
    else if (f.startsWith('key:')) ACTS['key-save']({ dataset: { id: f.slice(4) } });
});

// A click anywhere else closes an open dropdown.
document.addEventListener('click', (e) => {
    if (D.openDd && !e.target.closest('.dd')) {
        D.openDd = null;
        render();
    }
});

document.getElementById('tabs').addEventListener('click', (e) => {
    const t = e.target.closest('.tab');
    if (t) showTab(t.dataset.tab);
});

document.getElementById('tabs').innerHTML = TABS
    .map(([id, label]) => `<button class="tab" data-tab="${id}">${label}</button>`).join('');

(async () => {
    const linked = location.hash.slice(1);
    if (TABS.some(([id]) => id === linked)) D.tab = linked;
    render();
    await loadSettings();
    if (D.tab === 'models') render();
    else await showTab(D.tab);
    await loadCatalog();   // the live model list can take a few seconds
    render();
})();
