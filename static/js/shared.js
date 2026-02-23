// ---- Shared board (read-only) ----

const TOKEN_KEY = 'db_token';
const MIN_ZOOM = 0.15;
const MAX_ZOOM = 4;

let panX = 0;
let panY = 0;
let zoom = 1;

let cards = [];

// ---- Auth header (passive, no board editing) ----

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }

async function checkAuth() {
    const token = getToken();
    if (!token) return;
    const res = await fetch('/api/auth/me', {
        headers: { 'Authorization': 'Bearer ' + token }
    });
    if (res.ok) {
        const user = await res.json();
        document.getElementById('auth-email').textContent = user.email;
        document.getElementById('auth-logged-out').style.display = 'none';
        document.getElementById('auth-logged-in').style.display = 'flex';
    }
}

function openLoginModal() {
    document.getElementById('login-modal-overlay').classList.add('open');
    document.getElementById('login-form').reset();
    document.getElementById('login-error').textContent = '';
    setTimeout(() => document.getElementById('login-email').focus(), 50);
}

function closeLoginModal() {
    document.getElementById('login-modal-overlay').classList.remove('open');
}

function openRegisterModal() {
    document.getElementById('register-modal-overlay').classList.add('open');
    document.getElementById('register-form').reset();
    document.getElementById('register-error').textContent = '';
    setTimeout(() => document.getElementById('register-email').focus(), 50);
}

function closeRegisterModal() {
    document.getElementById('register-modal-overlay').classList.remove('open');
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    errorEl.textContent = '';
    const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (res.ok) {
        setToken(data.token);
        closeLoginModal();
        document.getElementById('auth-email').textContent = data.email;
        document.getElementById('auth-logged-out').style.display = 'none';
        document.getElementById('auth-logged-in').style.display = 'flex';
    } else {
        errorEl.textContent = data.error || 'Login failed';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;
    const errorEl = document.getElementById('register-error');
    errorEl.textContent = '';
    const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (res.ok) {
        setToken(data.token);
        closeRegisterModal();
        document.getElementById('auth-email').textContent = data.email;
        document.getElementById('auth-logged-out').style.display = 'none';
        document.getElementById('auth-logged-in').style.display = 'flex';
    } else {
        errorEl.textContent = data.error || 'Registration failed';
    }
}

// ---- Board loading ----

async function initBoard() {
    const token = window.SHARE_TOKEN;
    const res = await fetch(`/api/share/${token}`);
    if (!res.ok) {
        window.location.href = '/';
        return;
    }
    const data = await res.json();
    cards = data.cards;
    renderCards(data.cards);
    renderNotes(data.notes || []);
    renderConnections(data.connections, data.cards);
}

// ---- Rendering ----

function escHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str || ''));
    return div.innerHTML;
}

function renderCards(cardsData) {
    const canvas = document.getElementById('canvas');
    cardsData.forEach(card => {
        const el = document.createElement('div');
        el.className = 'card card-readonly';
        if (card.inactive) el.classList.add('card-inactive');
        el.style.left = card.pos_x + 'px';
        el.style.top = card.pos_y + 'px';
        const pinPos = card.pin_position || 'center';
        el.innerHTML = `
            <div class="card-pin pin-${pinPos}"></div>
            <div class="card-content">
                <div class="card-title">${escHtml(card.title)}</div>
                ${card.description ? `<div class="card-description">${escHtml(card.description)}</div>` : ''}
                ${card.image_path ? `<img src="${card.image_path}" class="card-image" alt="">` : ''}
            </div>
        `;
        card.el = el;
        canvas.appendChild(el);
    });
}

function renderNotes(notesData) {
    const canvas = document.getElementById('canvas');
    notesData.forEach(note => {
        const el = document.createElement('div');
        el.className = 'note note-readonly';
        el.style.left = note.pos_x + 'px';
        el.style.top = note.pos_y + 'px';
        const textEl = document.createElement('div');
        textEl.className = 'note-text';
        textEl.textContent = note.content;
        el.appendChild(textEl);
        canvas.appendChild(el);
    });
}

function renderConnections(connections, cardsData) {
    const svg = document.getElementById('connections-svg');
    svg.innerHTML = '';

    const CARD_WIDTH = 210;
    const PIN_Y_OFFSET = 4;

    function pinCenterX(card) {
        const pos = card.pin_position || 'center';
        if (pos === 'left') return card.pos_x + 32;
        if (pos === 'right') return card.pos_x + CARD_WIDTH - 32;
        return card.pos_x + CARD_WIDTH / 2;
    }

    connections.forEach(conn => {
        const card1 = cardsData.find(c => c.id === conn.card_id_1);
        const card2 = cardsData.find(c => c.id === conn.card_id_2);
        if (!card1 || !card2) return;

        const x1 = pinCenterX(card1);
        const y1 = card1.pos_y + PIN_Y_OFFSET;
        const x2 = pinCenterX(card2);
        const y2 = card2.pos_y + PIN_Y_OFFSET;

        const dist = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
        const sag = Math.max(40, dist * 0.22);

        const cp1x = x1 + (x2 - x1) * 0.25;
        const cp1y = y1 + sag;
        const cp2x = x1 + (x2 - x1) * 0.75;
        const cp2y = y2 + sag;

        const shadow = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        shadow.setAttribute('d', `M ${x1} ${y1} C ${cp1x} ${cp1y} ${cp2x} ${cp2y} ${x2} ${y2}`);
        shadow.setAttribute('stroke', 'rgba(0,0,0,0.25)');
        shadow.setAttribute('stroke-width', '4');
        shadow.setAttribute('fill', 'none');
        shadow.setAttribute('stroke-linecap', 'round');
        svg.appendChild(shadow);

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', `M ${x1} ${y1} C ${cp1x} ${cp1y} ${cp2x} ${cp2y} ${x2} ${y2}`);
        path.setAttribute('stroke', '#cc1a00');
        path.setAttribute('stroke-width', '2.5');
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('opacity', '0.88');
        svg.appendChild(path);
    });
}

// ---- Pan / Zoom ----

function updateTransform() {
    document.getElementById('canvas').style.transform =
        `translate(${panX}px, ${panY}px) scale(${zoom})`;
    document.getElementById('reset-pan-btn').style.display =
        (panX !== 0 || panY !== 0) ? 'inline-block' : 'none';
}

function resetPan() {
    panX = 0;
    panY = 0;
    updateTransform();
}

// ---- Init ----

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    initBoard();

    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('register-form').addEventListener('submit', handleRegister);

    document.getElementById('login-modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('login-modal-overlay')) closeLoginModal();
    });
    document.getElementById('register-modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('register-modal-overlay')) closeRegisterModal();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeLoginModal();
            closeRegisterModal();
        }
    });

    // Middle mouse button pan
    document.getElementById('board').addEventListener('mousedown', (e) => {
        if (e.button !== 1) return;
        e.preventDefault();
        const startX = e.clientX;
        const startY = e.clientY;
        const startPanX = panX;
        const startPanY = panY;
        document.getElementById('board').classList.add('panning');

        function onMouseMove(e) {
            panX = startPanX + (e.clientX - startX);
            panY = startPanY + (e.clientY - startY);
            updateTransform();
        }
        function onMouseUp() {
            document.getElementById('board').classList.remove('panning');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        }
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });

    // Scroll wheel: pan (two-finger swipe) or zoom (ctrl+scroll / pinch)
    document.getElementById('board').addEventListener('wheel', (e) => {
        e.preventDefault();
        if (e.ctrlKey) {
            const board = document.getElementById('board');
            const rect = board.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            const factor = e.deltaY < 0 ? 1.1 : 0.9;
            const newZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom * factor));

            panX = mouseX - (mouseX - panX) * (newZoom / zoom);
            panY = mouseY - (mouseY - panY) * (newZoom / zoom);
            zoom = newZoom;
        } else {
            panX -= e.deltaX;
            panY -= e.deltaY;
        }
        updateTransform();
    }, { passive: false });

    // Touch pan / pinch-zoom on the board background
    (function () {
        const board = document.getElementById('board');
        let touchState = null;

        board.addEventListener('touchstart', (e) => {
            e.preventDefault();
            if (e.touches.length === 1) {
                touchState = {
                    type: 'pan',
                    startX: e.touches[0].clientX,
                    startY: e.touches[0].clientY,
                    startPanX: panX,
                    startPanY: panY,
                };
            } else if (e.touches.length === 2) {
                const t1 = e.touches[0], t2 = e.touches[1];
                touchState = {
                    type: 'pinch',
                    startDist: Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY),
                    startMidX: (t1.clientX + t2.clientX) / 2,
                    startMidY: (t1.clientY + t2.clientY) / 2,
                    startPanX: panX,
                    startPanY: panY,
                    startZoom: zoom,
                };
            }
        }, { passive: false });

        board.addEventListener('touchmove', (e) => {
            if (!touchState) return;
            e.preventDefault();
            if (e.touches.length === 1 && touchState.type === 'pan') {
                panX = touchState.startPanX + (e.touches[0].clientX - touchState.startX);
                panY = touchState.startPanY + (e.touches[0].clientY - touchState.startY);
                updateTransform();
            } else if (e.touches.length === 2 && touchState.type === 'pinch') {
                const t1 = e.touches[0], t2 = e.touches[1];
                const newDist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
                const newMidX = (t1.clientX + t2.clientX) / 2;
                const newMidY = (t1.clientY + t2.clientY) / 2;
                const rect = board.getBoundingClientRect();
                const newZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, touchState.startZoom * (newDist / touchState.startDist)));
                const boardMidX = touchState.startMidX - rect.left;
                const boardMidY = touchState.startMidY - rect.top;
                panX = touchState.startPanX + boardMidX * (1 - newZoom / touchState.startZoom) + (newMidX - touchState.startMidX);
                panY = touchState.startPanY + boardMidY * (1 - newZoom / touchState.startZoom) + (newMidY - touchState.startMidY);
                zoom = newZoom;
                updateTransform();
            }
        }, { passive: false });

        board.addEventListener('touchend', (e) => {
            if (!touchState) return;
            e.preventDefault();
            if (e.touches.length === 0) {
                touchState = null;
            } else if (e.touches.length === 1) {
                touchState = {
                    type: 'pan',
                    startX: e.touches[0].clientX,
                    startY: e.touches[0].clientY,
                    startPanX: panX,
                    startPanY: panY,
                };
            }
        }, { passive: false });
    })();
});
