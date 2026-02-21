// ---- State ----
let currentBoardId = null;
let cards = [];        // [{id, title, description, image_path, pos_x, pos_y, el}]
let connections = [];  // [{id, card_id_1, card_id_2}]
let selectedCardIds = new Set();
let editingCardId = null;
let pendingCreatePos = null; // position from dblclick on empty board area

// ---- Pan / Zoom state ----
let panX = 0;
let panY = 0;
let zoom = 1;
const MIN_ZOOM = 0.15;
const MAX_ZOOM = 4;

// ---- Init ----

document.addEventListener('DOMContentLoaded', () => {
    loadBoards();

    document.getElementById('new-board-form').addEventListener('submit', onCreateBoard);
    document.getElementById('card-form').addEventListener('submit', onCreateCard);
    document.getElementById('edit-card-form').addEventListener('submit', onSaveEditCard);
    document.getElementById('modal-overlay').addEventListener('click', (e) => {
        if (e.target === document.getElementById('modal-overlay')) closeModal();
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
        // Convert screen coordinates to canvas coordinates
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

    // Scroll wheel zoom (centered on cursor)
    document.getElementById('board').addEventListener('wheel', (e) => {
        e.preventDefault();
        const board = document.getElementById('board');
        const rect = board.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const factor = e.deltaY < 0 ? 1.1 : 0.9;
        const newZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom * factor));

        // Adjust pan so the canvas point under the cursor stays fixed
        panX = mouseX - (mouseX - panX) * (newZoom / zoom);
        panY = mouseY - (mouseY - panY) * (newZoom / zoom);
        zoom = newZoom;
        updateTransform();
    }, { passive: false });

    document.addEventListener('keydown', (e) => {
        if ((e.key === 'Delete' || e.key === 'Del') && selectedCardIds.size > 0) {
            deleteSelectedCards();
        }
        if (e.key === 'Escape') {
            closeModal();
            closeEditPanel();
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

async function loadBoards() {
    const res = await fetch('/api/boards');
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
            <button class="board-delete-btn" title="Delete board">&times;</button>
        `;
        item.querySelector('.board-item-name').addEventListener('click', () => {
            document.getElementById('menu').classList.remove('open');
            loadBoard(b.id);
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
    });
    if (res.ok) {
        const board = await res.json();
        input.value = '';
        await loadBoards();
        loadBoard(board.id);
    }
}

async function deleteBoard(boardId, boardName) {
    if (!confirm(`Delete board "${boardName}"?\nAll cards and connections will be lost.`)) return;
    const res = await fetch(`/api/boards/${boardId}`, { method: 'DELETE' });
    if (res.ok) {
        if (currentBoardId === boardId) {
            currentBoardId = null;
            clearBoard();
            document.getElementById('no-board-msg').style.display = '';
        }
        loadBoards();
    }
}

// ---- Board loading ----

async function loadBoard(boardId) {
    const res = await fetch(`/api/boards/${boardId}`);
    if (!res.ok) return;
    const data = await res.json();

    currentBoardId = boardId;
    clearBoard();

    connections = data.connections;
    data.cards.forEach(card => addCard(card));
    renderConnections();

    document.getElementById('no-board-msg').style.display = 'none';

    // Refresh list to show active state
    loadBoards();
}

function clearBoard() {
    document.querySelectorAll('.card').forEach(el => el.remove());
    document.getElementById('connections-svg').innerHTML = '';
    selectedCardIds.clear();
    cards = [];
    connections = [];
    updateToolbar();
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
    el.style.left = card.pos_x + 'px';
    el.style.top = card.pos_y + 'px';
    el.dataset.id = card.id;

    const pinPos = card.pin_position || 'center';
    el.innerHTML = `
        <div class="card-pin pin-${pinPos}"></div>
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

    makeDraggable(el, card);
    return el;
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
        // Place randomly within the currently visible canvas area
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
        body: fd,
    });
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

function deselectAll() {
    selectedCardIds.forEach(id => {
        const c = cards.find(x => x.id === id);
        if (c) c.el.classList.remove('selected');
    });
    selectedCardIds.clear();
    updateToolbar();
}

// ---- Toolbar ----

function updateToolbar() {
    const connectBtn = document.getElementById('connect-btn');
    const disconnectBtn = document.getElementById('disconnect-btn');

    if (selectedCardIds.size === 2) {
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card_id_1: id1, card_id_2: id2 }),
    });
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card_id_1: id1, card_id_2: id2 }),
    });
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

    const CARD_WIDTH = 210;
    const PIN_Y_OFFSET = 4; // near the pin at top of card

    function pinCenterX(card) {
        const pos = card.pin_position || 'center';
        if (pos === 'left') return card.pos_x + 32;   // 22px left + 10px half-pin
        if (pos === 'right') return card.pos_x + CARD_WIDTH - 32; // right: 22px, center
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

        // Cubic Bézier — control points pulled downward to simulate gravity
        const cp1x = x1 + (x2 - x1) * 0.25;
        const cp1y = y1 + sag;
        const cp2x = x1 + (x2 - x1) * 0.75;
        const cp2y = y2 + sag;

        // Subtle texture: slightly thicker white shadow path beneath
        const shadow = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        shadow.setAttribute('d', `M ${x1} ${y1} C ${cp1x} ${cp1y} ${cp2x} ${cp2y} ${x2} ${y2}`);
        shadow.setAttribute('stroke', 'rgba(0,0,0,0.25)');
        shadow.setAttribute('stroke-width', '4');
        shadow.setAttribute('fill', 'none');
        shadow.setAttribute('stroke-linecap', 'round');
        svg.appendChild(shadow);

        // Main red yarn path
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

// ---- Delete selected cards ----

async function deleteSelectedCards() {
    const count = selectedCardIds.size;
    const msg = count === 1 ? 'Delete this card?' : `Delete these ${count} cards?`;
    if (!confirm(msg)) return;

    const idsToDelete = [...selectedCardIds];
    for (const id of idsToDelete) {
        const res = await fetch(`/api/cards/${id}`, { method: 'DELETE' });
        if (res.ok) {
            const card = cards.find(c => c.id === id);
            if (card) card.el.remove();
            cards = cards.filter(c => c.id !== id);
            connections = connections.filter(c => c.card_id_1 !== id && c.card_id_2 !== id);
            selectedCardIds.delete(id);
        }
    }

    renderConnections();
    updateToolbar();
}

// ---- Save card position ----

async function saveCardPosition(card) {
    await fetch(`/api/cards/${card.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pos_x: card.pos_x, pos_y: card.pos_y }),
    });
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
        body: fd,
    });

    if (res.ok) {
        const updated = await res.json();
        const card = cards.find(c => c.id === editingCardId);
        if (card) {
            card.title = updated.title;
            card.description = updated.description;
            card.image_path = updated.image_path;
            card.pin_position = updated.pin_position;
            updateCardElement(card);
            renderConnections();
        }
        closeEditPanel();
    }
}

function updateCardElement(card) {
    const pinEl = card.el.querySelector('.card-pin');
    pinEl.className = `card-pin pin-${card.pin_position || 'center'}`;

    const content = card.el.querySelector('.card-content');
    content.innerHTML = `
        <div class="card-title">${escHtml(card.title)}</div>
        ${card.description ? `<div class="card-description">${escHtml(card.description)}</div>` : ''}
        ${card.image_path ? `<img src="${card.image_path}" class="card-image" alt="">` : ''}
    `;
}

// ---- Utilities ----

function escHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str || ''));
    return div.innerHTML;
}
