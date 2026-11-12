'use strict';

const TOKEN_KEY = 'db_token';

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

document.addEventListener('DOMContentLoaded', async () => {
    // Already authenticated → go straight to the board
    const token = getToken();
    if (token) {
        try {
            const res = await fetch('/api/auth/me', {
                headers: { 'Authorization': 'Bearer ' + token }
            });
            if (res.ok) {
                window.location.href = '/board';
                return;
            }
        } catch (_) {}
        clearToken();
    }

    initDemoBoard();

    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('register-form').addEventListener('submit', handleRegister);

    // ESC closes modals
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') { closeLoginModal(); closeRegisterModal(); }
    });

    // Click backdrop to close
    document.getElementById('login-modal-overlay').addEventListener('click', e => {
        if (e.target === e.currentTarget) closeLoginModal();
    });
    document.getElementById('register-modal-overlay').addEventListener('click', e => {
        if (e.target === e.currentTarget) closeRegisterModal();
    });
});

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    errorEl.textContent = '';

    const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (res.ok) {
        setToken(data.token);
        window.location.href = '/board';
    } else {
        errorEl.textContent = data.error || 'Login failed';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('register-username').value.trim();
    const password = document.getElementById('register-password').value;
    const errorEl = document.getElementById('register-error');
    errorEl.textContent = '';

    const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (res.ok) {
        setToken(data.token);
        trackEvent('signup-success', 'Signup success');
        window.location.href = '/board';
    } else {
        errorEl.textContent = data.error || 'Registration failed';
    }
}

function openLoginModal() {
    document.getElementById('login-modal-overlay').classList.add('open');
    document.getElementById('login-form').reset();
    document.getElementById('login-error').textContent = '';
    setTimeout(() => document.getElementById('login-username').focus(), 50);
}

function closeLoginModal() {
    document.getElementById('login-modal-overlay').classList.remove('open');
}

function openRegisterModal() {
    document.getElementById('register-modal-overlay').classList.add('open');
    document.getElementById('register-form').reset();
    document.getElementById('register-error').textContent = '';
    setTimeout(() => document.getElementById('register-username').focus(), 50);
}

function closeRegisterModal() {
    document.getElementById('register-modal-overlay').classList.remove('open');
}

/* ---- Analytics ---- */

// Sends a GoatCounter event (cookieless). GoatCounter uses sendBeacon, so the
// event survives the redirect that follows a successful signup.
function trackEvent(path, title) {
    try {
        if (window.goatcounter && typeof window.goatcounter.count === 'function') {
            window.goatcounter.count({ path, title, event: true });
        }
    } catch (_) {}
}

/* ---- Hero demo board ---- */

const SVG_NS = 'http://www.w3.org/2000/svg';
const DEMO_LINKS = [
    ['suspect', 'clue'],
    ['suspect', 'place'],
    ['note', 'place'],
];
const DEMO_YARN_START_MS = 1000;   // after the last card has landed
const DEMO_YARN_STAGGER_MS = 260;

function initDemoBoard() {
    const board = document.getElementById('demo-board');
    if (!board) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduceMotion) board.classList.add('will-animate');

    drawDemoYarn(board, !reduceMotion);

    if (!reduceMotion) {
        requestAnimationFrame(() => board.classList.add('is-playing'));
    }

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => drawDemoYarn(board, false), 100);
    });
}

function demoPinPoint(el) {
    // Anchor the yarn to the centre of the card's pin (offsets ignore CSS transforms).
    const pin = el.querySelector('.demo-pin');
    return {
        x: el.offsetLeft + pin.offsetLeft + pin.offsetWidth / 2,
        y: el.offsetTop + pin.offsetTop + pin.offsetHeight / 2,
    };
}

// Same sagging cubic Bézier used for real connections in board.js.
function yarnPath(a, b) {
    const dist = Math.hypot(b.x - a.x, b.y - a.y);
    const sag = Math.max(24, dist * 0.22);
    const cp1x = a.x + (b.x - a.x) * 0.25;
    const cp2x = a.x + (b.x - a.x) * 0.75;
    return `M ${a.x} ${a.y} C ${cp1x} ${a.y + sag} ${cp2x} ${b.y + sag} ${b.x} ${b.y}`;
}

function drawDemoYarn(board, animate) {
    const svg = document.getElementById('demo-yarn');
    svg.replaceChildren();

    DEMO_LINKS.forEach(([from, to], i) => {
        const a = board.querySelector(`[data-node="${from}"]`);
        const b = board.querySelector(`[data-node="${to}"]`);
        if (!a || !b) return;
        const d = yarnPath(demoPinPoint(a), demoPinPoint(b));

        const shadow = document.createElementNS(SVG_NS, 'path');
        shadow.setAttribute('d', d);
        shadow.setAttribute('fill', 'none');
        shadow.setAttribute('stroke', 'rgba(0,0,0,0.28)');
        shadow.setAttribute('stroke-width', '4');
        shadow.setAttribute('stroke-linecap', 'round');
        shadow.setAttribute('transform', 'translate(1.5 3)');

        const yarn = document.createElementNS(SVG_NS, 'path');
        yarn.setAttribute('d', d);
        yarn.setAttribute('fill', 'none');
        yarn.setAttribute('stroke', '#cc1a00');
        yarn.setAttribute('stroke-width', '2.5');
        yarn.setAttribute('stroke-linecap', 'round');

        svg.append(shadow, yarn);

        if (animate) {
            const delay = DEMO_YARN_START_MS + i * DEMO_YARN_STAGGER_MS;
            [shadow, yarn].forEach(p => {
                const len = p.getTotalLength();
                p.style.setProperty('--yarn-len', `${len}`);
                p.style.strokeDasharray = `${len}`;
                p.style.animationDelay = `${delay}ms`;
                p.classList.add('yarn-draw');
            });
        }
    });
}
