// ---- Card colors ----
const CARD_COLORS = [
    { value: '',        bg: '#fffef0', dark: false, label: 'Bianco' },
    { value: '#f5e6c8', bg: '#f5e6c8', dark: false, label: 'Manila' },
    { value: '#f5d0c8', bg: '#f5d0c8', dark: false, label: 'Rosa'   },
    { value: '#d5e8d0', bg: '#d5e8d0', dark: false, label: 'Verde'  },
    { value: '#2a1e14', bg: '#2a1e14', dark: true,  label: 'Scuro'  },
];

function getColorEntry(color) {
    return CARD_COLORS.find(c => c.value === (color || '')) || CARD_COLORS[0];
}

// ---- Auth state ----
const TOKEN_KEY = 'db_token';
let currentUser = null; // { id, email }

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

function authHeaders(extra) {
    const h = Object.assign({}, extra);
    const token = getToken();
    if (token) h['Authorization'] = 'Bearer ' + token;
    return h;
}

async function checkAuth() {
    const token = getToken();
    if (!token) { onLoggedOut(); return; }
    const res = await fetch('/api/auth/me', { headers: authHeaders() });
    if (res.ok) {
        currentUser = await res.json();
        onLoggedIn();
    } else {
        clearToken();
        onLoggedOut();
    }
}

function onLoggedIn() {
    document.getElementById('auth-email').textContent = currentUser.email;
    document.getElementById('auth-logged-out').style.display = 'none';
    document.getElementById('auth-logged-in').style.display = 'flex';
    document.getElementById('menu-toggle').style.display = '';
    document.getElementById('no-board-text').textContent = 'Open the menu to load or create a board';
    document.getElementById('auth-logo').setAttribute('href', '/board');
    loadBoards();
}

function onLoggedOut() {
    currentUser = null;
    document.getElementById('auth-logged-out').style.display = 'flex';
    document.getElementById('auth-logged-in').style.display = 'none';
    document.getElementById('menu-toggle').style.display = 'none';
    closeMenu();
    currentBoardId = null;
    clearBoard();
    document.getElementById('no-board-msg').style.display = '';
    document.getElementById('toolbar').style.display = 'none';
    document.getElementById('no-board-text').textContent = 'Log in to use DetectiveBoard';
    document.getElementById('auth-logo').setAttribute('href', '/');
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
        currentUser = { email: data.email };
        closeLoginModal();
        onLoggedIn();
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
        currentUser = { email: data.email };
        closeRegisterModal();
        onLoggedIn();
    } else {
        errorEl.textContent = data.error || 'Registration failed';
    }
}

function logout() {
    clearToken();
    window.location.href = '/';
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

// Handle 401 globally: clear token and show login
function handleUnauthorized() {
    clearToken();
    currentUser = null;
    onLoggedOut();
    openLoginModal();
}

// ---- Board state ----
let currentBoardId = null;
let currentBoardShareToken = null; // null = not shared
let cards = [];        // [{id, title, description, image_path, pos_x, pos_y, el}]
let notes = [];        // [{id, content, pos_x, pos_y, el}]
let connections = [];  // [{id, card_id_1, card_id_2}]
let selectedCardIds = new Set();
let selectedNoteIds = new Set();
let editingCardId = null;
let pendingCreatePos = null;
let pendingNoteCreatePos = null;

// ---- Pan / Zoom state ----
let panX = 0;
let panY = 0;
let zoom = 1;
const MIN_ZOOM = 0.15;
const MAX_ZOOM = 4;

// ---- Init ----

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();

    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('register-form').addEventListener('submit', handleRegister);
    document.getElementById('new-board-form').addEventListener('submit', onCreateBoard);
    document.getElementById('card-form').addEventListener('submit', onCreateCard);
    document.getElementById('note-form').addEventListener('submit', onCreateNote);
    document.getElementById('edit-card-form').addEventListener('submit', onSaveEditCard);

    document.querySelectorAll('#modal-color-picker .color-dot').forEach(dot => {
        dot.addEventListener('click', () => {
            document.querySelectorAll('#modal-color-picker .color-dot').forEach(d => d.classList.remove('color-dot-selected'));
            dot.classList.add('color-dot-selected');
            document.getElementById('modal-card-color').value = dot.dataset.color;
        });
    });

    document.querySelectorAll('#edit-color-picker .color-dot').forEach(dot => {
        dot.addEventListener('click', () => {
            document.querySelectorAll('#edit-color-picker .color-dot').forEach(d => d.classList.remove('color-dot-selected'));
            dot.classList.add('color-dot-selected');
            document.getElementById('edit-card-color').value = dot.dataset.color;
        });
    });

    document.getElementById('modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('modal-overlay')) closeModal();
    });
    document.getElementById('note-modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('note-modal-overlay')) closeNoteModal();
    });
    document.getElementById('login-modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('login-modal-overlay')) closeLoginModal();
    });
    document.getElementById('register-modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('register-modal-overlay')) closeRegisterModal();
    });
    document.getElementById('help-modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('help-modal-overlay')) closeHelpModal();
    });
    document.getElementById('share-modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('share-modal-overlay')) closeShareModal();
    });

    document.getElementById('board').addEventListener('click', () => {
        closeMenu();
    });
    document.getElementById('board').addEventListener('click', (e) => {
        const board = document.getElementById('board');
        const canvas = document.getElementById('canvas');
        const svg = document.getElementById('connections-svg');
        if (e.target === board || e.target === canvas || e.target === svg) {
            deselectAll();
        }
    });

    document.getElementById('board').addEventListener('dblclick', (e) => {
        if (!currentBoardId) return;
        const board = document.getElementById('board');
        const canvas = document.getElementById('canvas');
        const svg = document.getElementById('connections-svg');
        if (e.target !== board && e.target !== canvas && e.target !== svg) return;
        const rect = board.getBoundingClientRect();
        pendingCreatePos = {
            x: (e.clientX - rect.left - panX) / zoom,
            y: (e.clientY - rect.top - panY) / zoom,
        };
        openModal();
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
            if (e.target.closest('.card') || e.target.closest('.note')) return;
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
            if (e.target.closest('.card') || e.target.closest('.note')) return;
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
                // Lifted one finger during pinch — restart as single-finger pan
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

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Delete' || e.key === 'Del') {
            if (selectedCardIds.size > 0 || selectedNoteIds.size > 0) {
                deleteSelected();
            }
        }
        if (e.key === 'Escape') {
            closeMenu();
            closeModal();
            closeNoteModal();
            closeEditPanel();
            closeLoginModal();
            closeRegisterModal();
            closeHelpModal();
            closeShareModal();
        }
    });
});

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

// ---- Menu ----

function toggleMenu() {
    document.getElementById('menu').classList.toggle('open');
}

function closeMenu() {
    document.getElementById('menu').classList.remove('open');
}

async function loadBoards() {
    const res = await fetch('/api/boards', { headers: authHeaders() });
    if (res.status === 401) { handleUnauthorized(); return; }
    const data = await res.json();
    renderBoardsList(data);
}

function renderBoardsList(boardsData) {
    const list = document.getElementById('boards-list');
    list.innerHTML = '';
    if (boardsData.length === 0) {
        list.innerHTML = '<p style="font-size:12px;opacity:0.5;padding:6px 0">No boards yet.</p>';
        return;
    }
    boardsData.forEach(b => {
        const item = document.createElement('div');
        item.className = 'board-item' + (b.id === currentBoardId ? ' active' : '');
        item.innerHTML = `
            <span class="board-item-name">${escHtml(b.name)}</span>
            <button class="board-rename-btn" title="Rename board">✎</button>
            <button class="board-delete-btn" title="Delete board">&times;</button>
        `;
        item.querySelector('.board-item-name').addEventListener('click', () => {
            document.getElementById('menu').classList.remove('open');
            loadBoard(b.id);
        });
        item.querySelector('.board-rename-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            startRenameBoard(item, b);
        });
        item.querySelector('.board-delete-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteBoard(b.id, b.name);
        });
        list.appendChild(item);
    });
}

async function onCreateBoard(e) {
    e.preventDefault();
    const input = document.getElementById('new-board-name');
    const name = input.value.trim();
    if (!name) return;
    const res = await fetch('/api/boards', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ name }),
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    if (res.ok) {
        const board = await res.json();
        input.value = '';
        await loadBoards();
        loadBoard(board.id);
    }
}

function startRenameBoard(item, b) {
    const nameSpan = item.querySelector('.board-item-name');
    const renameBtn = item.querySelector('.board-rename-btn');
    const deleteBtn = item.querySelector('.board-delete-btn');

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'board-rename-input';
    input.value = b.name;

    nameSpan.replaceWith(input);
    renameBtn.style.display = 'none';
    deleteBtn.style.display = 'none';
    input.focus();
    input.select();

    let done = false;

    const commit = async () => {
        if (done) return;
        done = true;
        const newName = input.value.trim();
        if (newName && newName !== b.name) {
            const res = await fetch(`/api/boards/${b.id}`, {
                method: 'PATCH',
                headers: authHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ name: newName }),
            });
            if (res.status === 401) { handleUnauthorized(); return; }
        }
        loadBoards();
    };

    const cancel = () => {
        if (done) return;
        done = true;
        loadBoards();
    };

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); commit(); }
        if (e.key === 'Escape') { e.preventDefault(); cancel(); }
    });
    input.addEventListener('blur', commit);
}

async function deleteBoard(boardId, boardName) {
    if (!confirm(`Delete board "${boardName}"?\nAll cards and connections will be lost.`)) return;
    const res = await fetch(`/api/boards/${boardId}`, {
        method: 'DELETE',
        headers: authHeaders(),
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    if (res.ok) {
        if (currentBoardId === boardId) {
            currentBoardId = null;
            clearBoard();
            document.getElementById('no-board-msg').style.display = '';
            document.getElementById('toolbar').style.display = 'none';
        }
        loadBoards();
    }
}

// ---- Board loading ----

async function loadBoard(boardId) {
    const res = await fetch(`/api/boards/${boardId}`, { headers: authHeaders() });
    if (res.status === 401) { handleUnauthorized(); return; }
    if (!res.ok) return;
    const data = await res.json();

    currentBoardId = boardId;
    clearBoard();
    currentBoardShareToken = data.board.share_token || null;

    connections = data.connections;
    data.cards.forEach(card => addCard(card));
    (data.notes || []).forEach(note => addNote(note));
    renderConnections();

    document.getElementById('no-board-msg').style.display = 'none';
    document.getElementById('toolbar').style.display = '';
    updateShareButton();

    loadBoards();
}

function clearBoard() {
    document.querySelectorAll('.card').forEach(el => el.remove());
    document.querySelectorAll('.note').forEach(el => el.remove());
    document.getElementById('connections-svg').innerHTML = '';
    selectedCardIds.clear();
    selectedNoteIds.clear();
    cards = [];
    notes = [];
    connections = [];
    currentBoardShareToken = null;
    updateToolbar();
    document.getElementById('share-btn').style.display = 'none';
    updateShareBanner();
}

// ---- Card creation ----

function addCard(cardData) {
    const card = { ...cardData };
    card.el = createCardElement(card);
    document.getElementById('canvas').appendChild(card.el);
    cards.push(card);
    return card;
}

function createCardElement(card) {
    const el = document.createElement('div');
    el.className = 'card';
    if (card.inactive) el.classList.add('card-inactive');
    el.style.left = card.pos_x + 'px';
    el.style.top = card.pos_y + 'px';
    el.dataset.id = card.id;

    const colorEntry = getColorEntry(card.color);
    el.style.background = colorEntry.bg;
    if (colorEntry.dark) el.classList.add('card-dark');

    const pinPos = card.pin_position || 'center';
    const colorDotsHtml = CARD_COLORS.map(c => {
        const isActive = (card.color || '') === c.value;
        const extraStyle = c.value === '' ? 'box-shadow:inset 0 0 0 1px #c0a888;' : '';
        return `<span class="card-color-dot${isActive ? ' active' : ''}" data-color="${c.value}" style="background:${c.bg};${extraStyle}" title="${c.label}"></span>`;
    }).join('');

    el.innerHTML = `
        <div class="card-pin pin-${pinPos}"></div>
        <div class="card-colors">${colorDotsHtml}</div>
        <div class="card-content">
            <div class="card-title">${escHtml(card.title)}</div>
            ${card.description ? `<div class="card-description">${escHtml(card.description)}</div>` : ''}
            ${card.image_path ? `<img src="${card.image_path}" class="card-image" alt="">` : ''}
        </div>
    `;

    el.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        openEditPanel(card);
    });

    el.querySelectorAll('.card-color-dot').forEach(dot => {
        dot.addEventListener('mousedown', e => e.stopPropagation());
        dot.addEventListener('click', async (e) => {
            e.stopPropagation();
            const newColor = dot.dataset.color;
            if ((card.color || '') === newColor) return;
            card.color = newColor || null;
            applyCardColor(card);
            await fetch(`/api/cards/${card.id}`, {
                method: 'PUT',
                headers: authHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ color: card.color }),
            });
        });
    });

    makeDraggable(el, card);
    return el;
}

function applyCardColor(card) {
    const colorEntry = getColorEntry(card.color);
    card.el.style.background = colorEntry.bg;
    card.el.classList.toggle('card-dark', colorEntry.dark);
    card.el.querySelectorAll('.card-color-dot').forEach(dot => {
        dot.classList.toggle('active', dot.dataset.color === (card.color || ''));
    });
}

async function onCreateCard(e) {
    e.preventDefault();
    if (!currentBoardId) return;

    const form = e.target;
    const fd = new FormData(form);

    let x, y;
    if (pendingCreatePos) {
        x = pendingCreatePos.x;
        y = pendingCreatePos.y;
    } else {
        const viewW = window.innerWidth / zoom;
        const viewH = window.innerHeight / zoom;
        const originX = -panX / zoom;
        const originY = -panY / zoom;
        x = originX + Math.max(20, viewW * 0.1) + Math.random() * Math.max(100, viewW * 0.7);
        y = originY + Math.max(20, viewH * 0.1) + Math.random() * Math.max(100, viewH * 0.6);
    }
    fd.append('pos_x', x.toFixed(0));
    fd.append('pos_y', y.toFixed(0));

    const res = await fetch(`/api/boards/${currentBoardId}/cards`, {
        method: 'POST',
        headers: authHeaders(),
        body: fd,
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    if (res.ok) {
        const cardData = await res.json();
        closeModal();
        form.reset();
        addCard(cardData);
    }
}

// ---- Drag & drop ----

function makeDraggable(el, card) {
    el.addEventListener('mousedown', (downEvent) => {
        if (downEvent.button !== 0) return;
        downEvent.preventDefault();
        downEvent.stopPropagation();

        const startX = downEvent.clientX;
        const startY = downEvent.clientY;
        const startPosX = card.pos_x;
        const startPosY = card.pos_y;
        let isDragging = false;

        function onMouseMove(e) {
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            if (!isDragging && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
                isDragging = true;
            }
            if (isDragging) {
                card.pos_x = startPosX + dx / zoom;
                card.pos_y = startPosY + dy / zoom;
                el.style.left = card.pos_x + 'px';
                el.style.top = card.pos_y + 'px';
                renderConnections();
            }
        }

        function onMouseUp(upEvent) {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);

            if (!isDragging) {
                toggleSelection(card.id, upEvent.shiftKey);
            } else {
                saveCardPosition(card);
            }
        }

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });

    el.addEventListener('touchstart', (downEvent) => {
        if (downEvent.touches.length !== 1) return;
        downEvent.stopPropagation();
        downEvent.preventDefault();

        const touch = downEvent.touches[0];
        const startX = touch.clientX;
        const startY = touch.clientY;
        const startPosX = card.pos_x;
        const startPosY = card.pos_y;
        let isDragging = false;

        function onTouchMove(e) {
            e.preventDefault();
            const t = e.touches[0];
            const dx = t.clientX - startX;
            const dy = t.clientY - startY;
            if (!isDragging && (Math.abs(dx) > 5 || Math.abs(dy) > 5)) {
                isDragging = true;
            }
            if (isDragging) {
                card.pos_x = startPosX + dx / zoom;
                card.pos_y = startPosY + dy / zoom;
                el.style.left = card.pos_x + 'px';
                el.style.top = card.pos_y + 'px';
                renderConnections();
            }
        }

        function onTouchEnd() {
            document.removeEventListener('touchmove', onTouchMove);
            document.removeEventListener('touchend', onTouchEnd);
            if (!isDragging) {
                toggleSelection(card.id, false);
            } else {
                saveCardPosition(card);
            }
        }

        document.addEventListener('touchmove', onTouchMove, { passive: false });
        document.addEventListener('touchend', onTouchEnd);
    }, { passive: false });
}

// ---- Selection ----

function toggleSelection(cardId, additive) {
    const card = cards.find(c => c.id === cardId);
    if (!card) return;

    if (!additive) {
        selectedCardIds.forEach(id => {
            const c = cards.find(x => x.id === id);
            if (c) c.el.classList.remove('selected');
        });
        selectedNoteIds.forEach(id => {
            const n = notes.find(x => x.id === id);
            if (n) n.el.classList.remove('selected');
        });
        selectedNoteIds.clear();
        const wasSelected = selectedCardIds.has(cardId);
        selectedCardIds.clear();
        if (!wasSelected) {
            selectedCardIds.add(cardId);
            card.el.classList.add('selected');
        }
    } else {
        if (selectedCardIds.has(cardId)) {
            selectedCardIds.delete(cardId);
            card.el.classList.remove('selected');
        } else {
            selectedCardIds.add(cardId);
            card.el.classList.add('selected');
        }
    }

    updateToolbar();
}

function toggleNoteSelection(noteId, additive) {
    const note = notes.find(n => n.id === noteId);
    if (!note) return;

    if (!additive) {
        selectedCardIds.forEach(id => {
            const c = cards.find(x => x.id === id);
            if (c) c.el.classList.remove('selected');
        });
        selectedCardIds.clear();
        selectedNoteIds.forEach(id => {
            const n = notes.find(x => x.id === id);
            if (n) n.el.classList.remove('selected');
        });
        const wasSelected = selectedNoteIds.has(noteId);
        selectedNoteIds.clear();
        if (!wasSelected) {
            selectedNoteIds.add(noteId);
            note.el.classList.add('selected');
        }
    } else {
        if (selectedNoteIds.has(noteId)) {
            selectedNoteIds.delete(noteId);
            note.el.classList.remove('selected');
        } else {
            selectedNoteIds.add(noteId);
            note.el.classList.add('selected');
        }
    }

    updateToolbar();
}

function deselectAll() {
    selectedCardIds.forEach(id => {
        const c = cards.find(x => x.id === id);
        if (c) c.el.classList.remove('selected');
    });
    selectedCardIds.clear();
    selectedNoteIds.forEach(id => {
        const n = notes.find(x => x.id === id);
        if (n) n.el.classList.remove('selected');
    });
    selectedNoteIds.clear();
    updateToolbar();
}

// ---- Toolbar ----

function updateToolbar() {
    const connectBtn = document.getElementById('connect-btn');
    const disconnectBtn = document.getElementById('disconnect-btn');
    const deleteBtn = document.getElementById('delete-selected-btn');
    const editBtn = document.getElementById('edit-selected-btn');

    const hasSelection = selectedCardIds.size > 0 || selectedNoteIds.size > 0;
    deleteBtn.style.display = hasSelection ? 'inline-block' : 'none';

    editBtn.style.display = (selectedCardIds.size === 1 && selectedNoteIds.size === 0) ? 'inline-block' : 'none';

    if (selectedCardIds.size === 2 && selectedNoteIds.size === 0) {
        const [id1, id2] = [...selectedCardIds];
        if (areConnected(id1, id2)) {
            connectBtn.style.display = 'none';
            disconnectBtn.style.display = 'inline-block';
        } else {
            connectBtn.style.display = 'inline-block';
            disconnectBtn.style.display = 'none';
        }
    } else {
        connectBtn.style.display = 'none';
        disconnectBtn.style.display = 'none';
    }
}

function editSelectedCard() {
    if (selectedCardIds.size !== 1 || selectedNoteIds.size !== 0) return;
    const [id] = [...selectedCardIds];
    const card = cards.find(c => c.id === id);
    if (card) openEditPanel(card);
}

// ---- Connections ----

function areConnected(id1, id2) {
    return connections.some(c =>
        (c.card_id_1 === id1 && c.card_id_2 === id2) ||
        (c.card_id_1 === id2 && c.card_id_2 === id1)
    );
}

async function connectCards() {
    const [id1, id2] = [...selectedCardIds];
    const res = await fetch('/api/connections', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ card_id_1: id1, card_id_2: id2 }),
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    if (res.ok) {
        const conn = await res.json();
        connections.push(conn);
        renderConnections();
        updateToolbar();
    }
}

async function disconnectCards() {
    const [id1, id2] = [...selectedCardIds];
    const res = await fetch('/api/connections', {
        method: 'DELETE',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ card_id_1: id1, card_id_2: id2 }),
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    if (res.ok) {
        connections = connections.filter(c =>
            !((c.card_id_1 === id1 && c.card_id_2 === id2) ||
              (c.card_id_1 === id2 && c.card_id_2 === id1))
        );
        renderConnections();
        updateToolbar();
    }
}

// ---- SVG yarn rendering ----

function renderConnections() {
    const svg = document.getElementById('connections-svg');
    svg.innerHTML = '';
    // Re-append SVG to canvas so it's always the last child (painted on top of all cards).
    document.getElementById('canvas').appendChild(svg);

    const CARD_WIDTH = 210;
    const PIN_Y_OFFSET = 4;

    function pinCenterX(card) {
        const pos = card.pin_position || 'center';
        if (pos === 'left') return card.pos_x + 32;
        if (pos === 'right') return card.pos_x + CARD_WIDTH - 32;
        return card.pos_x + CARD_WIDTH / 2;
    }

    connections.forEach(conn => {
        const card1 = cards.find(c => c.id === conn.card_id_1);
        const card2 = cards.find(c => c.id === conn.card_id_2);
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

// ---- Delete selected items ----

async function deleteSelected() {
    const cardCount = selectedCardIds.size;
    const noteCount = selectedNoteIds.size;
    const total = cardCount + noteCount;
    let msg;
    if (total === 1) {
        msg = cardCount === 1 ? 'Delete this card?' : 'Delete this note?';
    } else {
        msg = `Delete these ${total} items?`;
    }
    if (!confirm(msg)) return;

    const cardIdsToDelete = [...selectedCardIds];
    for (const id of cardIdsToDelete) {
        const res = await fetch(`/api/cards/${id}`, {
            method: 'DELETE',
            headers: authHeaders(),
        });
        if (res.status === 401) { handleUnauthorized(); return; }
        if (res.ok) {
            const card = cards.find(c => c.id === id);
            if (card) card.el.remove();
            cards = cards.filter(c => c.id !== id);
            connections = connections.filter(c => c.card_id_1 !== id && c.card_id_2 !== id);
            selectedCardIds.delete(id);
        }
    }

    const noteIdsToDelete = [...selectedNoteIds];
    for (const id of noteIdsToDelete) {
        const res = await fetch(`/api/notes/${id}`, {
            method: 'DELETE',
            headers: authHeaders(),
        });
        if (res.status === 401) { handleUnauthorized(); return; }
        if (res.ok) {
            const note = notes.find(n => n.id === id);
            if (note) note.el.remove();
            notes = notes.filter(n => n.id !== id);
            selectedNoteIds.delete(id);
        }
    }

    renderConnections();
    updateToolbar();
    closeEditPanel();
}

async function deleteEditingCard() {
    if (!editingCardId) return;
    selectedCardIds.clear();
    selectedCardIds.add(editingCardId);
    selectedNoteIds.clear();
    await deleteSelected();
}

// ---- Notes ----

function addNote(noteData) {
    const note = { ...noteData };
    note.el = createNoteElement(note);
    document.getElementById('canvas').appendChild(note.el);
    notes.push(note);
    return note;
}

function createNoteElement(note) {
    const el = document.createElement('div');
    el.className = 'note';
    el.style.left = note.pos_x + 'px';
    el.style.top = note.pos_y + 'px';
    el.dataset.id = note.id;

    const textEl = document.createElement('div');
    textEl.className = 'note-text';
    textEl.textContent = note.content;
    el.appendChild(textEl);

    el.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        startNoteEdit(note, el);
    });

    makeNoteDraggable(el, note);
    return el;
}

function startNoteEdit(note, el) {
    const textEl = el.querySelector('.note-text');
    if (!textEl) return;

    const originalContent = note.content;

    const textarea = document.createElement('textarea');
    textarea.className = 'note-edit-area';
    textarea.value = note.content;
    el.replaceChild(textarea, textEl);
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);

    let saved = false;

    function save() {
        if (saved) return;
        saved = true;
        const newContent = textarea.value;
        const newTextEl = document.createElement('div');
        newTextEl.className = 'note-text';
        newTextEl.textContent = newContent;
        if (textarea.parentNode === el) {
            el.replaceChild(newTextEl, textarea);
        }
        if (newContent !== originalContent) {
            note.content = newContent;
            saveNoteContent(note);
        }
    }

    function cancel() {
        if (saved) return;
        saved = true;
        const newTextEl = document.createElement('div');
        newTextEl.className = 'note-text';
        newTextEl.textContent = originalContent;
        if (textarea.parentNode === el) {
            el.replaceChild(newTextEl, textarea);
        }
    }

    textarea.addEventListener('blur', save);
    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            textarea.removeEventListener('blur', save);
            cancel();
        }
    });
}

async function saveNoteContent(note) {
    const res = await fetch(`/api/notes/${note.id}`, {
        method: 'PUT',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ content: note.content }),
    });
    if (res.status === 401) handleUnauthorized();
}

async function saveNotePosition(note) {
    const res = await fetch(`/api/notes/${note.id}`, {
        method: 'PUT',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ pos_x: note.pos_x, pos_y: note.pos_y }),
    });
    if (res.status === 401) handleUnauthorized();
}

function makeNoteDraggable(el, note) {
    el.addEventListener('mousedown', (downEvent) => {
        if (downEvent.button !== 0) return;
        if (downEvent.target.tagName === 'TEXTAREA') return;
        downEvent.preventDefault();
        downEvent.stopPropagation();

        const startX = downEvent.clientX;
        const startY = downEvent.clientY;
        const startPosX = note.pos_x;
        const startPosY = note.pos_y;
        let isDragging = false;

        function onMouseMove(e) {
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            if (!isDragging && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
                isDragging = true;
            }
            if (isDragging) {
                note.pos_x = startPosX + dx / zoom;
                note.pos_y = startPosY + dy / zoom;
                el.style.left = note.pos_x + 'px';
                el.style.top = note.pos_y + 'px';
            }
        }

        function onMouseUp(upEvent) {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            if (!isDragging) {
                toggleNoteSelection(note.id, upEvent.shiftKey);
            } else {
                saveNotePosition(note);
            }
        }

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });

    el.addEventListener('touchstart', (downEvent) => {
        if (downEvent.touches.length !== 1) return;
        if (downEvent.target.tagName === 'TEXTAREA') return;
        downEvent.stopPropagation();
        downEvent.preventDefault();

        const touch = downEvent.touches[0];
        const startX = touch.clientX;
        const startY = touch.clientY;
        const startPosX = note.pos_x;
        const startPosY = note.pos_y;
        let isDragging = false;

        function onTouchMove(e) {
            e.preventDefault();
            const t = e.touches[0];
            const dx = t.clientX - startX;
            const dy = t.clientY - startY;
            if (!isDragging && (Math.abs(dx) > 5 || Math.abs(dy) > 5)) {
                isDragging = true;
            }
            if (isDragging) {
                note.pos_x = startPosX + dx / zoom;
                note.pos_y = startPosY + dy / zoom;
                el.style.left = note.pos_x + 'px';
                el.style.top = note.pos_y + 'px';
            }
        }

        function onTouchEnd() {
            document.removeEventListener('touchmove', onTouchMove);
            document.removeEventListener('touchend', onTouchEnd);
            if (!isDragging) {
                toggleNoteSelection(note.id, false);
            } else {
                saveNotePosition(note);
            }
        }

        document.addEventListener('touchmove', onTouchMove, { passive: false });
        document.addEventListener('touchend', onTouchEnd);
    }, { passive: false });
}

// ---- Note Modal ----

function openNoteModal() {
    if (!currentBoardId) return;
    document.getElementById('note-modal-overlay').classList.add('open');
    setTimeout(() => document.getElementById('note-content').focus(), 50);
}

function closeNoteModal() {
    document.getElementById('note-modal-overlay').classList.remove('open');
    document.getElementById('note-form').reset();
    pendingNoteCreatePos = null;
}

async function onCreateNote(e) {
    e.preventDefault();
    if (!currentBoardId) return;

    const content = document.getElementById('note-content').value;

    let x, y;
    if (pendingNoteCreatePos) {
        x = pendingNoteCreatePos.x;
        y = pendingNoteCreatePos.y;
    } else {
        const viewW = window.innerWidth / zoom;
        const viewH = window.innerHeight / zoom;
        const originX = -panX / zoom;
        const originY = -panY / zoom;
        x = originX + Math.max(20, viewW * 0.1) + Math.random() * Math.max(100, viewW * 0.7);
        y = originY + Math.max(20, viewH * 0.1) + Math.random() * Math.max(100, viewH * 0.6);
    }

    const res = await fetch(`/api/boards/${currentBoardId}/notes`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ content, pos_x: Math.round(x), pos_y: Math.round(y) }),
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    if (res.ok) {
        const noteData = await res.json();
        closeNoteModal();
        addNote(noteData);
    }
}

// ---- Save card position ----

async function saveCardPosition(card) {
    const res = await fetch(`/api/cards/${card.id}`, {
        method: 'PUT',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ pos_x: card.pos_x, pos_y: card.pos_y }),
    });
    if (res.status === 401) handleUnauthorized();
}

// ---- Modal ----

function openModal() {
    if (!currentBoardId) return;
    document.getElementById('modal-overlay').classList.add('open');
    setTimeout(() => document.getElementById('card-title').focus(), 50);
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('open');
    document.getElementById('card-form').reset();
    document.querySelectorAll('#modal-color-picker .color-dot').forEach(d => d.classList.remove('color-dot-selected'));
    document.querySelector('#modal-color-picker .color-dot[data-color=""]').classList.add('color-dot-selected');
    document.getElementById('modal-card-color').value = '';
    pendingCreatePos = null;
}

// ---- Edit Panel ----

function openEditPanel(card) {
    editingCardId = card.id;
    document.getElementById('edit-card-title').value = card.title || '';
    document.getElementById('edit-card-description').value = card.description || '';
    document.getElementById('edit-card-image').value = '';

    const imgWrap = document.getElementById('edit-current-image-wrap');
    const img = document.getElementById('edit-current-image');
    if (card.image_path) {
        img.src = card.image_path;
        imgWrap.style.display = '';
    } else {
        imgWrap.style.display = 'none';
        img.src = '';
    }

    const pinPos = card.pin_position || 'center';
    document.querySelectorAll('input[name="pin_position"]').forEach(r => {
        r.checked = r.value === pinPos;
    });

    document.getElementById('edit-card-inactive').checked = !!card.inactive;

    const cardColor = card.color || '';
    document.querySelectorAll('#edit-color-picker .color-dot').forEach(dot => {
        dot.classList.toggle('color-dot-selected', dot.dataset.color === cardColor);
    });
    document.getElementById('edit-card-color').value = cardColor;

    document.getElementById('edit-panel').classList.add('open');
    setTimeout(() => document.getElementById('edit-card-title').focus(), 50);
}

function closeEditPanel() {
    document.getElementById('edit-panel').classList.remove('open');
    editingCardId = null;
    document.getElementById('edit-card-form').reset();
    document.getElementById('edit-current-image-wrap').style.display = 'none';
}

async function onSaveEditCard(e) {
    e.preventDefault();
    if (!editingCardId) return;

    const fd = new FormData(e.target);
    const res = await fetch(`/api/cards/${editingCardId}`, {
        method: 'PUT',
        headers: authHeaders(),
        body: fd,
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    if (res.ok) {
        const updated = await res.json();
        const card = cards.find(c => c.id === editingCardId);
        if (card) {
            card.title = updated.title;
            card.description = updated.description;
            card.image_path = updated.image_path;
            card.pin_position = updated.pin_position;
            card.inactive = updated.inactive;
            card.color = updated.color || null;
            updateCardElement(card);
            renderConnections();
        }
        closeEditPanel();
    }
}

function updateCardElement(card) {
    const pinEl = card.el.querySelector('.card-pin');
    pinEl.className = `card-pin pin-${card.pin_position || 'center'}`;

    card.el.classList.toggle('card-inactive', !!card.inactive);

    applyCardColor(card);

    const content = card.el.querySelector('.card-content');
    content.innerHTML = `
        <div class="card-title">${escHtml(card.title)}</div>
        ${card.description ? `<div class="card-description">${escHtml(card.description)}</div>` : ''}
        ${card.image_path ? `<img src="${card.image_path}" class="card-image" alt="">` : ''}
    `;
}

// ---- Share ----

function updateShareButton() {
    const btn = document.getElementById('share-btn');
    btn.style.display = currentBoardId ? 'inline-block' : 'none';
    if (currentBoardShareToken) {
        btn.textContent = '⛔ Stop sharing';
        btn.classList.add('share-btn-active');
    } else {
        btn.textContent = '🔗 Share';
        btn.classList.remove('share-btn-active');
    }
    updateShareBanner();
}

function updateShareBanner() {
    const banner = document.getElementById('share-url-banner');
    if (currentBoardShareToken) {
        const shareUrl = window.location.origin + '/share/' + currentBoardShareToken;
        document.getElementById('share-banner-input').value = shareUrl;
        document.getElementById('share-banner-copy-btn').textContent = 'Copy';
        banner.style.display = 'flex';
        document.body.classList.add('has-share-banner');
    } else {
        banner.style.display = 'none';
        document.body.classList.remove('has-share-banner');
    }
}

async function copyShareBannerUrl() {
    const input = document.getElementById('share-banner-input');
    try {
        await navigator.clipboard.writeText(input.value);
    } catch {
        input.select();
        document.execCommand('copy');
    }
    const btn = document.getElementById('share-banner-copy-btn');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
}

async function onShareToggle() {
    if (!currentBoardId) return;
    if (currentBoardShareToken) {
        if (!confirm('Stop sharing this board?\nThe share link will stop working.')) return;
        const res = await fetch(`/api/boards/${currentBoardId}/share`, {
            method: 'DELETE',
            headers: authHeaders(),
        });
        if (res.status === 401) { handleUnauthorized(); return; }
        if (res.ok) {
            currentBoardShareToken = null;
            updateShareButton();
        }
    } else {
        const res = await fetch(`/api/boards/${currentBoardId}/share`, {
            method: 'POST',
            headers: authHeaders(),
        });
        if (res.status === 401) { handleUnauthorized(); return; }
        if (res.ok) {
            const data = await res.json();
            currentBoardShareToken = data.share_token;
            updateShareButton();
            openShareModal(window.location.origin + data.share_url);
        }
    }
}

function openShareModal(shareUrl) {
    document.getElementById('share-url-input').value = shareUrl;
    document.getElementById('share-copy-btn').textContent = 'Copy';
    document.getElementById('share-modal-overlay').classList.add('open');
}

function closeShareModal() {
    document.getElementById('share-modal-overlay').classList.remove('open');
}

async function copyShareUrl() {
    const input = document.getElementById('share-url-input');
    try {
        await navigator.clipboard.writeText(input.value);
    } catch {
        input.select();
        document.execCommand('copy');
    }
    const btn = document.getElementById('share-copy-btn');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
}

// ---- Help Modal ----

function openHelpModal() {
    document.getElementById('help-modal-overlay').classList.add('open');
}

function closeHelpModal() {
    document.getElementById('help-modal-overlay').classList.remove('open');
}

// ---- Utilities ----

function escHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str || ''));
    return div.innerHTML;
}
