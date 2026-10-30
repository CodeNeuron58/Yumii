// The island — Yumii's top-of-screen bar. One state object, one `view()`
// derived from it, one render. Templates build structure; changing text
// (live words, her reply, the countdown) is patched into [data-text] slots
// so buttons are never rebuilt under the cursor.

import { IS_TAURI, backend, shell, esc, sleep, toolLabel, appName, actionName } from './backend.js';
import { icon } from './icons.js';
import { VoiceLink } from './voice.js';

const HOTKEY = 'Ctrl ⇧ Space';
const WINDOW_W = 560;        // the 480px island plus room for its shadow
const SHADOW_PAD = 44;
const SLIVER = { w: 136, h: 14 };
const MUTED = { w: 200, h: 34 };
const MIC_GATE = 0.02;       // local RMS that counts as "they're talking"
const RECENT_MAX = 30;

const S = {
    phase: 'boot',           // boot | idle | listening | thinking | speaking
    bootText: 'Waking her up…',
    progress: null,          // null | 0..1 | 'indeterminate'
    connected: false,
    ready: false,
    muted: false,
    hover: false,
    pinned: false,
    recentOpen: false,
    turnActive: false,       // between thinking_start and thinking_end
    question: '',            // what she's answering
    partial: '',             // live words while they talk
    reply: '',               // her words so far
    replyFromAudio: false,   // reply came from an utterance's audio_start, not reply_text
    tool: null,              // tool running right now
    approval: null,          // { id, tool, args, deadline, question }
    approvedTools: new Set(),
    result: null,            // { emails } from an inbox read
    done: null,              // { ok, label } for an approved action
    error: null,             // { kind, message }
    onboard: null,           // { provider, name, keyEnv, link, err, saving }
    lingering: false,        // answer finished, about to hide
    recent: [],              // { q, a, t }
    draft: '',               // the typed-input box
    prefs: { hideAfter: 4, showReply: true },
    pipeline: '',
};

let turn = null;             // { q, a, t } being built
let lingerTimer = null;
let hoverTimer = null;
let listenTimer = null;
let loudFrames = 0;
let countdownTimer = null;
let prefsLoadedAt = 0;
let reconnecting = false;

const root = document.getElementById('island');
const voice = new VoiceLink({
    onOpen, onClose, onEvent, onMicLevel, onMicError, onSpeechEnd,
});

// ── View ────────────────────────────────────────────────────────────────

function view() {
    if (S.onboard) return 'onboard';
    if (S.error) return 'error';
    if (S.approval) return 'approval';
    if (S.phase === 'boot') return 'boot';
    if (S.recentOpen) return 'recent';
    if (S.phase === 'listening') return 'listening';
    if (S.phase === 'thinking') return 'thinking';
    if (S.phase === 'speaking' || S.lingering) return 'answer';
    if (S.muted) return 'muted';
    if (S.hover) return 'peek';
    return 'sliver';
}

const ib = (action, title, name, cls = '') =>
    `<button class="ibtn ${cls}" data-action="${action}" title="${title}" aria-label="${title}">${icon(name)}</button>`;
const muteBtn = () => (S.muted
    ? ib('mute', 'Unmute microphone', 'micOff', 'danger')
    : ib('mute', 'Mute microphone', 'mic'));
const sep = '<span class="sep"></span>';

const WAVE_BARS = Array.from({ length: 9 }, (_, i) => {
    const h = 5 + Math.round(9 * Math.abs(Math.sin(i * 1.7 + 0.3)));
    return `<span style="height:${h}px;--d:${(0.6 + (i % 4) * 0.14).toFixed(2)}s;--delay:${(i * 0.08).toFixed(2)}s"></span>`;
}).join('');
const wave = (kind, still = false) => `<div class="wave ${kind}${still ? ' still' : ''}">${WAVE_BARS}</div>`;

const T = {
    sliver: () => ({ html: '<div class="sliver"></div>' }),

    muted: () => ({
        html: `<button class="muted-pill" data-action="mute" title="Unmute">${icon('micOff', 13)}<span>Muted</span></button>`,
    }),

    peek: () => ({
        html: `<div class="panel compact"><div class="strip">
            <span class="dot ${S.connected ? 'ok' : ''}"></span>
            <span class="status" data-text="status"></span>
            <span class="kbd">${HOTKEY}</span>
            <div class="btns lead">${muteBtn()}${ib('recent', 'Recent', 'chevronDown')}${sep}${ib('dashboard', 'Dashboard', 'sliders')}</div>
        </div></div>`,
        text: { status: S.connected ? 'Ready' : 'Connecting…' },
    }),

    listening: () => ({
        html: `<div class="panel wide"><div class="strip">
            ${wave('listen')}
            <p class="line live"><bdi data-text="live"></bdi></p>
            <div class="btns">${muteBtn()}${ib('recent', 'Recent', 'chevronDown')}</div>
        </div></div>`,
        text: { live: S.partial || 'Listening…' },
    }),

    thinking: () => ({
        html: `<div class="panel wide"><div class="strip">
            <span class="spinner"></span>
            <p class="line soft" data-text="line"></p>
            <button class="pill" data-action="stop">Stop</button>
        </div></div>`,
        text: { line: S.tool ? `${toolLabel(S.tool)}…` : (S.question || 'Thinking…') },
    }),

    answer: () => {
        const speaking = S.phase === 'speaking';
        const head = S.done
            ? `<span class="okmark ${S.done.ok ? '' : 'fail'}">${icon(S.done.ok ? 'check' : 'x', 11, { stroke: 2.25 })}</span>
               <span class="done-label ${S.done.ok ? '' : 'fail'}" data-text="done"></span>`
            : '<p class="line q" data-text="question"></p>';
        const showReply = S.prefs.showReply && S.reply;
        const emails = S.result?.emails?.length ? emailsBlock(S.result.emails) : '';
        let below = '';
        if (emails) {
            below = `<div class="reads">${emails}${showReply ? '<p class="reply inline" data-text="reply"></p>' : ''}</div>`;
        } else if (showReply) {
            below = '<p class="reply" data-text="reply"></p>';
        }
        const draining = S.lingering && !S.pinned && !S.hover && S.prefs.hideAfter !== 'never';
        const drain = draining
            ? `<div class="drain"><i style="--hide:${S.prefs.hideAfter}s"></i></div>`
            : '';
        const close = S.lingering && (S.pinned || S.prefs.hideAfter === 'never')
            ? ib('dismiss', 'Close', 'x') : '';
        return {
            html: `<div class="panel wide"><div class="strip">
                ${wave('speak', !speaking)}${head}
                <div class="btns">${muteBtn()}${ib('pin', S.pinned ? 'Unpin' : 'Pin open', 'pin', S.pinned ? 'on' : '')}${ib('recent', 'Recent', 'chevronDown')}${close}</div>
            </div>${below}${drain}</div>`,
            text: {
                question: S.question ? `"${S.question}"` : '',
                done: S.done?.label || '',
                reply: S.reply,
            },
        };
    },

    approval: () => {
        const a = S.approval;
        return {
            html: `<div class="panel wide"><div class="strip tight">
                <span class="dot warn"></span>
                <span class="warn-text">Needs your OK</span>
                <p class="line q" data-text="question"></p>
                <span class="count" data-text="countdown"></span>
            </div><div class="cardwrap">${approvalCard(a)}</div></div>`,
            text: {
                question: a.question ? `"${a.question}"` : '',
                countdown: countdownText(),
            },
        };
    },

    boot: () => {
        let bar = '';
        if (S.progress === 'indeterminate') bar = '<div class="progress indeterminate"><i></i></div>';
        else if (typeof S.progress === 'number') {
            bar = `<div class="progress"><i style="width:${Math.round(S.progress * 100)}%"></i></div>`;
        }
        return {
            html: `<div class="panel wide"><div class="strip">
                <span class="spinner"></span>
                <p class="line soft" data-text="boot"></p>
                <div class="btns">${ib('dashboard', 'Dashboard', 'sliders')}</div>
            </div>${bar}</div>`,
            text: { boot: S.bootText },
        };
    },

    onboard: () => {
        const o = S.onboard;
        return {
            html: `<div class="panel wide"><div class="strip tight">
                <span class="dot ok"></span>
                <span class="status strong">Hi — I'm Yumii</span>
            </div><div class="setup">
                <p>My ears and voice are ready. I just need a mind to think with — one key and we're talking.</p>
                ${o.link ? `<button class="getkey" data-action="getkey">Get your ${esc(o.name)} key ${icon('external', 12)}</button>` : ''}
                <input class="field" id="onboard-key" type="password" autocomplete="off" spellcheck="false"
                       placeholder="Paste your ${esc(o.name)} key">
                <p class="err" data-text="err"></p>
                <div class="actions">
                    <button class="link-btn" data-action="onboard-more">More options</button>
                    <span class="grow"></span>
                    <button class="pill primary lg" data-action="onboard-save" data-text="save"></button>
                </div>
            </div></div>`,
            text: { err: o.err || '', save: o.saving ? 'Waking her up…' : 'Wake her up' },
        };
    },

    error: () => {
        const e = S.error;
        const title = {
            auth: "I can't reach my mind",
            quota: 'Give me a moment',
            network: 'Connection trouble',
            startup: "Couldn't start",
            mic: "I can't hear you",
        }[e.kind] || 'Hmm';
        const fix = ['auth', 'quota'].includes(e.kind)
            ? '<button class="pill ghost lg" data-action="err-fix">Open dashboard</button>' : '';
        return {
            html: `<div class="panel wide"><div class="strip tight">
                <span class="dot danger"></span>
                <span class="status strong danger">${esc(title)}</span>
            </div><div class="setup">
                <p data-text="msg"></p>
                <div class="actions"><span class="grow"></span>${fix}
                    <button class="pill primary lg" data-action="err-ok">OK</button></div>
            </div></div>`,
            text: { msg: e.message || 'Something went wrong.' },
        };
    },

    recent: () => {
        const items = S.recent.length
            ? S.recent.map((h, i) => `<div class="item">
                <div class="item-main">
                    <div class="item-top"><span class="item-q">${esc(h.q || '—')}</span><span class="item-t">${esc(h.t)}</span></div>
                    <p class="item-a">${esc(h.a)}</p>
                </div>
                <div class="item-btns">
                    <button class="ibtn sm" data-action="replay" data-i="${i}" title="Replay" aria-label="Replay">${icon('play', 12)}</button>
                    <button class="ibtn sm" data-action="copy" data-i="${i}" title="Copy" aria-label="Copy">${icon('copy', 12)}</button>
                </div></div>`).join('')
            : '<div class="empty">Nothing yet — say something, or type below.</div>';
        return {
            html: `<div class="panel wide"><div class="strip ruled">
                <span class="dot ${S.connected ? 'ok' : ''}"></span>
                <span class="status grow">Recent</span>
                <div class="btns">${muteBtn()}${ib('recent', 'Collapse', 'chevronUp', 'on')}${sep}${ib('dashboard', 'Dashboard', 'sliders')}</div>
            </div>
            <div class="recent-list">${items}</div>
            <div class="type-row"><input id="type-input" type="text" autocomplete="off" spellcheck="false"
                placeholder="Type to Yumii — or say stop, mute, new chat"></div>
            <div class="foot"><span class="mono" data-text="pipeline"></span>
                ${S.recent.length ? '<button class="link-btn" data-action="clear">Clear</button>' : ''}</div></div>`,
            text: { pipeline: S.pipeline },
        };
    },
};

function emailsBlock(emails) {
    const rows = emails.map((m) => `<div class="mail">
        <b>${esc(m.from || 'Unknown')}</b><time>${esc(fmtTime(m.time))}</time>
        <span>${esc(m.subject)}</span></div>`).join('');
    return `<div class="reads-head">${icon('mail', 13)}<span>Gmail · read ${emails.length}</span></div>
        <div class="mails">${rows}</div>`;
}

function approvalCard(a) {
    const args = a.args || {};
    const tool = String(a.tool || '');
    const email = /^GMAIL_(SEND_EMAIL|REPLY_TO_THREAD|CREATE_EMAIL_DRAFT)$/.test(tool);
    if (email) {
        const draft = tool.endsWith('DRAFT');
        const to = args.recipient_email || args.to || (Array.isArray(args.extra_recipients) ? args.extra_recipients[0] : '') || 'the thread';
        const body = args.body || args.message_body || '';
        const thread = args.thread_id ? '<span class="chip">Reply in thread</span>' : '';
        return `<div class="card">
            <div class="mail-head">
                <span class="badge">${icon('mail', 13)}</span>
                <span class="summary"><span class="dim">${draft ? 'Draft to' : 'To'}</span> ${esc(to)}</span>${thread}
            </div>
            ${args.subject ? `<div class="mail-subject">${esc(args.subject)}</div>` : ''}
            ${body ? `<p class="mail-body">${esc(body)}</p>` : ''}
        </div>
        <div class="actions">
            <span class="hint">Say <b>"yes"</b> or <b>"no"</b></span>
            <button class="pill ghost lg" data-action="deny">Cancel</button>
            <button class="pill primary lg" data-action="approve">${draft ? 'Save draft' : 'Send'}${icon('send', 12, { stroke: 2 })}</button>
        </div>`;
    }
    let badge = 'bolt';
    let summary;
    if (tool === 'web_search') {
        badge = 'search';
        summary = `Search the web for <span class="dim">“</span>${esc(args.query || '')}<span class="dim">”</span>`;
    } else if (tool === 'GMAIL_FETCH_EMAILS') {
        badge = 'mail';
        summary = `Read your inbox${args.query ? ` <span class="dim">· ${esc(args.query)}</span>` : ''}`;
    } else {
        if (tool.startsWith('GOOGLECALENDAR_')) badge = 'calendar';
        else if (tool.startsWith('GMAIL_')) badge = 'mail';
        const app = appName(tool);
        const detail = Object.values(args)
            .filter((v) => typeof v === 'string' && v.trim())
            .slice(0, 2).join(' · ');
        summary = `${esc(app ? `${app} · ${actionName(tool)}` : actionName(tool) || tool)}`
            + (detail ? ` <span class="dim">· ${esc(detail.slice(0, 80))}</span>` : '');
    }
    return `<div class="card"><div class="card-row">
        <span class="badge">${icon(badge, 13)}</span>
        <span class="summary">${summary}</span>
        <button class="pill ghost" data-action="deny">Deny</button>
        <button class="pill primary" data-action="approve">Allow</button>
    </div></div>
    <div class="hint solo">Or just say <b>"yes"</b> or <b>"no"</b></div>`;
}

// ── Render ──────────────────────────────────────────────────────────────

let lastHTML = '';
let lastView = '';

function render() {
    const v = view();
    const { html, text = {} } = T[v]();
    if (html !== lastHTML) {
        const focused = document.activeElement?.id;
        root.innerHTML = html;
        lastHTML = html;
        const input = document.getElementById('type-input');
        if (input) {
            input.value = S.draft;
            if (focused === 'type-input') input.focus();
        }
        if (v === 'onboard' && lastView !== 'onboard') document.getElementById('onboard-key')?.focus();
    }
    for (const el of root.querySelectorAll('[data-text]')) {
        const value = text[el.dataset.text] ?? '';
        if (el.textContent !== value) el.textContent = value;
    }
    document.body.dataset.view = v;
    lastView = v;
    syncWindow();
}

// The window is only as big as what's showing: a 136×14 hover zone when
// tucked, otherwise the island plus its shadow. Only real changes reach the
// shell (one IPC per size, not per token).
let lastSize = '';
function syncWindow() {
    if (!IS_TAURI) return;
    const v = lastView;
    let w;
    let h;
    if (v === 'sliver') ({ w, h } = SLIVER);
    else if (v === 'muted') ({ w, h } = MUTED);
    else {
        w = WINDOW_W;
        h = Math.ceil(root.getBoundingClientRect().height) + SHADOW_PAD;
    }
    const key = `${w}x${h}`;
    if (key === lastSize) return;
    lastSize = key;
    shell.setIslandSize(w, h);
}
new ResizeObserver(syncWindow).observe(root);

// ── Linger / hover ──────────────────────────────────────────────────────

function startLinger() {
    clearTimeout(lingerTimer);
    S.lingering = true;
    const secs = S.prefs.hideAfter;
    if (secs !== 'never' && !S.pinned && !S.hover) {
        lingerTimer = setTimeout(endLinger, Number(secs) * 1000);
    }
    render();
}

function endLinger() {
    clearTimeout(lingerTimer);
    S.lingering = false;
    S.pinned = false;
    S.reply = '';
    S.question = '';
    S.result = null;
    S.done = null;
    render();
}

function setHover(on) {
    clearTimeout(hoverTimer);
    if (on) {
        if (S.hover) return;
        S.hover = true;
        clearTimeout(lingerTimer);   // reading it keeps it open
        render();
        return;
    }
    hoverTimer = setTimeout(() => {
        if (!S.hover) return;
        S.hover = false;
        if (S.lingering) startLinger();
        else render();
    }, 400);
}

document.body.addEventListener('mouseenter', () => {
    if (lastView === 'sliver' || lastView === 'muted') setHover(true);
});
root.addEventListener('mouseenter', () => setHover(true));
root.addEventListener('mouseleave', () => setHover(false));
document.documentElement.addEventListener('mouseleave', () => setHover(false));

// ── Turn bookkeeping ────────────────────────────────────────────────────

function finishTurn() {
    if (!turn) return;
    const answer = (S.reply || turn.a || '').trim();
    if (turn.q || answer) {
        S.recent.unshift({ q: turn.q, a: answer, t: turn.t });
        S.recent.length = Math.min(S.recent.length, RECENT_MAX);
    }
    turn = null;
}

function clock(date = new Date()) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

function fmtTime(value) {
    if (!value) return '';
    const s = String(value);
    let d;
    if (/^\d{10,13}$/.test(s)) d = new Date(s.length === 13 ? Number(s) : Number(s) * 1000);
    else d = new Date(s);
    if (Number.isNaN(d.getTime())) return s.slice(0, 10);
    const today = new Date().toDateString() === d.toDateString();
    return today ? clock(d) : d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function doneLabel(tool) {
    const t = String(tool || '');
    if (t.endsWith('SEND_EMAIL')) return 'Email sent';
    if (t.endsWith('REPLY_TO_THREAD')) return 'Reply sent';
    if (t.endsWith('CREATE_EMAIL_DRAFT')) return 'Draft saved';
    if (/^GOOGLECALENDAR_.*(CREATE|INSERT|QUICK_ADD)/.test(t)) return 'Event added';
    if (t.startsWith('GOOGLECALENDAR_')) return 'Calendar updated';
    const app = appName(t);
    return app ? `${app} updated` : 'Done';
}

// ── Approval countdown ──────────────────────────────────────────────────

function countdownText() {
    if (!S.approval) return '';
    const left = Math.max(0, Math.ceil((S.approval.deadline - Date.now()) / 1000));
    return `${left}s`;
}

function startCountdown() {
    clearInterval(countdownTimer);
    countdownTimer = setInterval(() => {
        const el = root.querySelector('[data-text="countdown"]');
        if (el) el.textContent = countdownText();
    }, 1000);
}

function closeApproval() {
    S.approval = null;
    clearInterval(countdownTimer);
}

// ── Backend events ──────────────────────────────────────────────────────

function onEvent(d) {
    switch (d.type) {
        case 'thinking_start':
            finishTurn();
            clearTimeout(lingerTimer);
            S.phase = 'thinking';
            S.turnActive = true;
            S.question = (d.text || S.partial || '').trim();
            S.partial = '';
            S.reply = '';
            S.tool = null;
            S.result = null;
            S.done = null;
            S.lingering = false;
            S.pinned = false;
            S.recentOpen = false;
            S.approvedTools = new Set();
            turn = { q: S.question, a: '', t: clock() };
            if (Date.now() - prefsLoadedAt > 15000) loadPrefs();
            break;
        case 'thinking_delta':
            if (S.phase === 'speaking' || S.phase === 'thinking') return;
            S.phase = 'thinking';
            break;
        case 'thinking_end':
            S.turnActive = false;
            // A turn that ends without any audio must not leave "Thinking…" up.
            setTimeout(() => {
                if (S.phase === 'thinking' && !S.turnActive && !voice.streaming) {
                    S.phase = 'idle';
                    if (S.reply) { finishTurn(); startLinger(); } else render();
                }
            }, 4000);
            return;
        case 'reply_text':
            S.replyFromAudio = false;
            if (S.phase === 'thinking' || S.phase === 'speaking') {
                S.reply = d.text || '';
                if (turn) turn.a = S.reply;
            } else if (d.text && !/^Mic (un)?muted\.?$/.test(d.text)) {
                // A command's one-liner ("New chat — I'm all ears.").
                S.question = '';
                S.reply = d.text;
                startLinger();
                return;
            } else return;
            break;
        case 'tool_status':
            S.tool = d.status === 'running' ? d.tool : null;
            break;
        case 'tool_result':
            if (d.emails?.length) S.result = { emails: d.emails };
            if (S.approvedTools.has(d.tool) && d.ok !== null && d.ok !== undefined) {
                S.done = d.ok ? { ok: true, label: doneLabel(d.tool) } : { ok: false, label: "Couldn't finish that" };
            }
            break;
        case 'confirmation_request':
            S.approval = {
                id: d.request_id,
                tool: d.tool,
                args: d.args || {},
                deadline: Date.now() + (d.timeout_seconds || 30) * 1000,
                question: S.question,
            };
            S.hover = false;
            startCountdown();
            break;
        case 'confirmation_resolved':
        case 'confirmation_timeout':
            if (S.approval && (!d.request_id || d.request_id === S.approval.id)) {
                if (d.type === 'confirmation_resolved' && d.approved) S.approvedTools.add(S.approval.tool);
                closeApproval();
            }
            break;
        case 'partial_transcript':
            if (S.phase !== 'idle' && S.phase !== 'listening') return;
            S.phase = 'listening';
            if (d.text && d.text.trim()) S.partial = d.text;
            clearTimeout(lingerTimer);
            S.lingering = false;
            armListenHangover();
            break;
        case 'audio_start':
            clearTimeout(lingerTimer);
            S.lingering = false;
            S.phase = 'speaking';
            S.partial = '';
            // An utterance's text shows until reply_text takes over. After a tool
            // runs, the answer is a new utterance: it must replace the "let me
            // check" line, not hide behind it.
            if (d.text && (!S.reply || S.replyFromAudio)) {
                S.reply = d.text;
                S.replyFromAudio = true;
                if (turn) turn.a = S.reply;
            }
            break;
        case 'interrupt':
            // Barge-in or "stop". A pending approval stays up until it's answered.
            finishTurn();
            S.phase = 'idle';
            S.tool = null;
            S.lingering = false;
            S.reply = '';
            S.question = '';
            break;
        case 'error':
            finishTurn();
            S.phase = 'idle';
            S.tool = null;
            S.lingering = false;
            S.reply = '';
            S.error = { kind: d.kind, message: d.message };
            break;
        case 'mic_state':
            S.muted = !!d.muted;
            voice.setMuted(S.muted, { tell: false });
            if (S.muted && S.phase === 'listening') S.phase = 'idle';
            break;
        default:
            return;
    }
    render();
}

function onSpeechEnd() {
    if (S.turnActive) {
        // Only her "let me check" line ended — the turn is still working.
        S.phase = 'thinking';
        render();
        return;
    }
    S.phase = 'idle';
    finishTurn();
    startLinger();
}

function armListenHangover() {
    clearTimeout(listenTimer);
    listenTimer = setTimeout(() => {
        if (S.phase === 'listening') {
            S.phase = 'idle';
            S.partial = '';
            render();
        }
    }, 900);
}

function onMicLevel(rms) {
    if (S.phase !== 'idle' && S.phase !== 'listening') return;
    if (rms <= MIC_GATE) { loudFrames = 0; return; }
    loudFrames += 1;
    if (S.phase === 'idle' && loudFrames < 2) return;   // a click isn't a voice
    if (S.phase !== 'listening') {
        S.phase = 'listening';
        S.partial = '';
        clearTimeout(lingerTimer);
        S.lingering = false;
        render();
    }
    armListenHangover();
}

function onMicError(err) {
    S.error = {
        kind: 'mic',
        message: `${err?.message || 'The microphone is unavailable.'} Check that a mic is connected and Yumii is allowed to use it, then reopen her.`,
    };
    render();
}

function onOpen() {
    S.connected = true;
    if (S.phase === 'boot') S.phase = 'idle';
    if (reconnecting) {
        reconnecting = false;
        afterReconnect();
    }
    render();
}

function onClose() {
    S.connected = false;
    reconnecting = true;
    closeApproval();
    S.phase = 'boot';
    S.bootText = 'Reconnecting…';
    S.progress = null;
    render();
}

// A backend that came back (crash, or a restart after a settings change)
// may be re-downloading models — show that instead of looking ready.
async function afterReconnect() {
    let st = await backend.status();
    while (st && !st.audio_ready) {
        showModelProgress(st);
        await sleep(700);
        st = await backend.status();
    }
    S.progress = null;
    if (S.phase === 'boot') S.phase = 'idle';
    loadPrefs();
    render();
}

// ── Actions ─────────────────────────────────────────────────────────────

const actions = {
    mute() {
        S.muted = !S.muted;
        voice.setMuted(S.muted);
        if (S.muted && S.phase === 'listening') S.phase = 'idle';
    },
    recent() {
        S.recentOpen = !S.recentOpen;
        if (S.recentOpen) {
            loadPrefs();
            clearTimeout(lingerTimer);
            S.lingering = false;
        }
    },
    dashboard() { shell.openDashboard(backend.base); },
    stop() {
        voice.command('stop');
        voice.stopAudio();
    },
    pin() {
        S.pinned = !S.pinned;
        if (!S.pinned && S.lingering) { startLinger(); return false; }
        clearTimeout(lingerTimer);
    },
    dismiss() { endLinger(); return false; },
    approve() { answerApproval(true); },
    deny() { answerApproval(false); },
    replay(el) {
        const item = S.recent[Number(el.dataset.i)];
        if (item?.a) voice.speak(item.a);
    },
    copy(el) {
        const item = S.recent[Number(el.dataset.i)];
        if (!item) return false;
        copyText(item.a).then(() => {
            el.innerHTML = icon('check', 12, { stroke: 2.25 });
            setTimeout(() => { el.innerHTML = icon('copy', 12); }, 1200);
        });
        return false;
    },
    clear() { S.recent = []; },
    'err-ok'() {
        const wasStartup = S.error?.kind === 'startup';
        S.error = null;
        if (wasStartup) boot();
    },
    'err-fix'() {
        S.error = null;
        shell.openDashboard(backend.base);
    },
    getkey() {
        if (S.onboard?.link) backend.openExternal(S.onboard.link);
        return false;
    },
    'onboard-more'() {
        shell.openDashboard(backend.base);
        return false;
    },
    'onboard-save'() { saveOnboarding(); return false; },
};

function answerApproval(approve) {
    if (!S.approval) return;
    voice.answer(S.approval.id, approve);
    if (approve) S.approvedTools.add(S.approval.tool);
    closeApproval();
}

root.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el || !root.contains(el)) return;
    e.stopPropagation();
    const fn = actions[el.dataset.action];
    if (!fn) return;
    if (fn(el, e) !== false) render();
});

root.addEventListener('input', (e) => {
    if (e.target.id === 'type-input') S.draft = e.target.value;
});

root.addEventListener('keydown', (e) => {
    if (e.target.id === 'type-input') {
        if (e.key === 'Enter') {
            const text = S.draft.trim();
            if (!text) return;
            if (!voice.command(text)) {
                S.error = { kind: 'network', message: "I'm not connected yet — give me a second and try again." };
            } else {
                S.draft = '';
                e.target.value = '';
            }
            render();
        } else if (e.key === 'Escape') {
            S.recentOpen = false;
            render();
        }
    } else if (e.target.id === 'onboard-key' && e.key === 'Enter') {
        saveOnboarding();
    }
});

async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
    }
}

// ── Preferences + the pipeline line ─────────────────────────────────────

async function loadPrefs() {
    prefsLoadedAt = Date.now();
    try {
        const s = await backend.get('/api/settings');
        const p = s.preferences || {};
        const hide = p.UI_HIDE_AFTER || '4';
        S.prefs = {
            hideAfter: hide === 'never' ? 'never' : Number(hide) || 4,
            showReply: p.UI_SHOW_REPLY !== 'off',
        };
        const labels = s.labels || {};
        const ears = (labels.STT_PROVIDER || {})[p.STT_PROVIDER] || p.STT_PROVIDER || '';
        const tts = p.TTS_PROVIDER || '';
        const voiceName = /kokoro/i.test(tts) ? (p.KOKORO_VOICE || 'Kokoro') : ((labels.TTS_PROVIDER || {})[tts] || tts);
        let mind = '';
        try {
            const cat = await backend.get('/api/llm/catalog');
            const model = cat?.current?.model || '';
            mind = model ? model.split('/').pop() : (cat?.current?.provider || '');
        } catch { /* catalog optional */ }
        S.pipeline = [shortLabel(ears), mind, voiceName].filter(Boolean).join(' · ');
        render();
    } catch { /* backend busy — keep the last prefs */ }
}

function shortLabel(label) {
    return String(label).replace(/\s*\(.*\)\s*$/, '');
}

// Seed Recent with the tail of the conversation she resumed.
async function seedRecent() {
    if (S.recent.length) return;
    try {
        const sessions = await backend.get('/api/sessions');
        const active = (sessions || []).find((s) => s.active);
        if (!active) return;
        const msgs = await backend.get(`/api/sessions/${encodeURIComponent(active.id)}/messages`);
        const pairs = [];
        let q = null;
        for (const m of msgs || []) {
            if (m.role === 'user') q = m.text;
            else if (m.role === 'assistant' && q !== null) {
                pairs.push({ q, a: m.text, t: '' });
                q = null;
            }
        }
        if (!S.recent.length) S.recent = pairs.slice(-6).reverse();
    } catch { /* nothing to seed */ }
}

// ── Boot: find her → models → one key → ready ───────────────────────────

function showModelProgress(st) {
    const m = st.models || {};
    S.phase = 'boot';
    if (m.stage === 'error') S.bootText = 'Trouble downloading — retrying…';
    else if (m.stage && m.stage !== 'starting' && m.stage !== 'ready') S.bootText = `${m.stage}…`;
    else S.bootText = 'Getting ready…';
    S.progress = m.indeterminate || typeof m.progress !== 'number' ? 'indeterminate' : m.progress;
    render();
}

async function boot() {
    S.phase = 'boot';
    S.bootText = 'Waking her up…';
    S.progress = null;
    render();
    const slow = () => {
        S.bootText = 'Still waking her up… a cold start can take a minute';
        render();
    };
    // The shell spawned the backend, so a cold first boot gets two full rounds.
    const up = (await backend.discover(150000, slow)) || (await backend.discover(150000, slow));
    if (!up) {
        S.phase = 'idle';
        S.error = {
            kind: 'startup',
            message: "My backend didn't start after a full cold-start wait. Another app may be using my port "
                + '(8000–8011), or the install didn\'t finish. Close that app, then reopen me.',
        };
        render();
        return;
    }
    await firstRun();
}

async function firstRun() {
    let st = await backend.status();
    while (st && !st.audio_ready) {
        showModelProgress(st);
        await sleep(700);
        st = await backend.status();
    }
    S.progress = null;
    if (st && !st.configured) {
        S.onboard = {
            provider: st.provider,
            name: String(st.provider_name || st.provider || 'your provider').replace(/\s*\(.*\)$/, ''),
            keyEnv: st.key_env,
            link: st.key_link,
            err: '',
            saving: false,
        };
        S.phase = 'idle';
        render();
        return;
    }
    S.ready = true;
    S.phase = voice.open ? 'idle' : 'boot';
    S.bootText = 'Connecting…';
    render();
    loadPrefs();
    seedRecent();
    voice.start();
}

async function saveOnboarding() {
    const o = S.onboard;
    if (!o || o.saving) return;
    const key = (document.getElementById('onboard-key')?.value || '').trim();
    if (!key) {
        o.err = 'Paste your key first.';
        render();
        return;
    }
    o.err = '';
    o.saving = true;
    render();
    try {
        await backend.put('/api/settings', {
            preferences: { LLM_PROVIDER: o.provider },
            credentials: { [o.keyEnv]: key },
        });
    } catch {
        o.err = "Couldn't save — try again.";
        o.saving = false;
        render();
        return;
    }
    // The backend reads keys once at import: restart it, then start over.
    S.onboard = null;
    S.phase = 'boot';
    S.bootText = 'Waking her up…';
    render();
    await shell.restartBackend();
    await sleep(1500);
    await backend.discover(150000);
    await firstRun();
}

// ── Preview (design review: index.html?preview=<view>) ──────────────────

function preview(name) {
    document.body.classList.add('preview');
    S.connected = true;
    S.phase = 'idle';
    S.pipeline = 'Groq Whisper · nemotron-3-super-120b-a12b · af_heart';
    const q = "What's on my calendar after lunch today?";
    const sample = {
        sliver() {},
        peek() { S.hover = true; },
        muted() { S.muted = true; },
        listening() { S.phase = 'listening'; S.partial = "What's on my calendar after lunch today"; },
        thinking() { S.phase = 'thinking'; S.question = q; },
        tool() { S.phase = 'thinking'; S.question = q; S.tool = 'web_search'; },
        answer() {
            S.phase = 'speaking'; S.question = q;
            S.reply = "Design review with Priya at 2:30, then you're free until the 5pm standup.";
        },
        linger() { sample.answer(); S.phase = 'idle'; S.lingering = true; },
        done() {
            S.phase = 'speaking'; S.done = { ok: true, label: 'Email sent' };
            S.reply = "Sent — I told Priya you'll have notes on the deck by Friday.";
        },
        emails() {
            S.phase = 'speaking'; S.question = 'Anything important in my email?';
            S.result = { emails: [
                { from: 'Priya Shah', subject: 'Q4 deck — feedback by Friday?', time: new Date().toISOString() },
                { from: 'Halden Legal', subject: 'Contract ready for signature', time: new Date().toISOString() },
                { from: 'Airline', subject: 'Check-in opens at 8:00 PM tonight', time: '2026-10-29T09:04:00Z' },
            ] };
            S.reply = 'Three need you: Priya wants feedback on the deck, the contract from Halden is ready to sign, and your flight check-in opens tonight.';
        },
        approval() {
            S.phase = 'thinking';
            S.approval = { id: 'x', tool: 'web_search', args: { query: 'weather in Tokyo today' }, deadline: Date.now() + 27000, question: "What's the weather in Tokyo?" };
        },
        email() {
            S.phase = 'thinking';
            S.approval = {
                id: 'x', tool: 'GMAIL_SEND_EMAIL', deadline: Date.now() + 27000,
                question: "Tell Priya I'll send feedback by Friday",
                args: { recipient_email: 'priya.shah@example.com', subject: 'Re: Q4 deck', body: "Hi Priya, thanks for sending this over. I'll have my notes on the deck to you by Friday.\n\nBest,\nSam" },
            };
        },
        calendar() {
            S.phase = 'thinking';
            S.approval = { id: 'x', tool: 'GOOGLECALENDAR_UPDATE_EVENT', args: { summary: 'Design review', start_datetime: '2026-10-30T16:00' }, deadline: Date.now() + 27000, question: 'Move my 2:30 with Priya to 4' };
        },
        recent() {
            S.recentOpen = true;
            S.recent = [
                { t: '14:02', q, a: 'Design review with Priya at 2:30, then free until the 5pm standup.' },
                { t: '13:47', q: 'Remind me to send the invoice at four.', a: "I can't set reminders yet — but I'll remember you mentioned it." },
                { t: '12:15', q: 'Translate "see you tomorrow" into Japanese.', a: 'Mata ashita.' },
            ];
        },
        boot() { S.phase = 'boot'; S.bootText = 'Downloading her voice…'; S.progress = 0.42; },
        onboard() { S.onboard = { provider: 'nebius', name: 'Nebius Token Factory', keyEnv: 'NEBIUS_API_KEY', link: 'nebius', err: '', saving: false }; },
        error() { S.error = { kind: 'auth', message: 'My key for Nebius Token Factory was rejected. Paste a fresh one in the dashboard and I\'ll be right back.' }; },
    };
    (sample[name] || sample.peek)();
    if (S.approval) startCountdown();
    render();
}

const previewName = new URLSearchParams(location.search).get('preview');
if (previewName) preview(previewName);
else boot();
