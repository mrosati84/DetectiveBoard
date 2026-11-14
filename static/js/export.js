// ---- Board export (PNG / PDF / SVG) ----
//
// Client-side only: the whole board is rendered from an off-screen clone of
// #canvas at zoom 1 with html-to-image; PDFs are assembled with jsPDF.
// Depends on globals from board.js (cards, notes, currentBoardId,
// currentBoardName, setFormError) and on the vendored libraries loaded by
// index.html (window.htmlToImage, window.jspdf).

const EXPORT_BG_KEY = 'db_export_include_bg';
const EXPORT_MARGIN = 48;            // px of empty board around the content
const EXPORT_PIXEL_RATIO = 2;        // preferred raster density
const EXPORT_MAX_SIDE = 8192;        // px, longest side of the output canvas
const EXPORT_MAX_AREA = 4096 * 4096; // px², safe canvas area across browsers (iOS Safari)
const EXPORT_JPEG_QUALITY = 0.92;
const EXPORT_PDF_MARGIN_MM = 10;
const EXPORT_CORK_URL = '/assets/cork_background.jpg';

let exportInProgress = false;

document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('export-modal-overlay');
    if (!overlay) return;

    document.getElementById('export-form').addEventListener('submit', onExportSubmit);
    document.getElementById('export-include-background').addEventListener('change', (e) => {
        saveExportBgPreference(e.target.checked);
    });
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeExportModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeExportModal();
    });

    updateExportButton();
});

// ---- Toolbar button / modal ----

function boardHasContent() {
    return Boolean(currentBoardId) && (cards.length > 0 || notes.length > 0);
}

function updateExportButton() {
    const btn = document.getElementById('export-btn');
    if (!btn) return;
    btn.disabled = !boardHasContent();
    if (!currentBoardId) {
        btn.title = 'Load a board to export it';
    } else if (btn.disabled) {
        btn.title = 'Add a card or a note to export this board';
    } else {
        btn.title = 'Export board';
    }
}

function openExportModal() {
    if (!boardHasContent()) return;
    setFormError('export-form-error', '');
    document.getElementById('export-include-background').checked = loadExportBgPreference();
    document.getElementById('export-modal-overlay').classList.add('open');
}

function closeExportModal() {
    const overlay = document.getElementById('export-modal-overlay');
    if (overlay) overlay.classList.remove('open');
}

function loadExportBgPreference() {
    try {
        return localStorage.getItem(EXPORT_BG_KEY) !== 'false';
    } catch {
        return true;
    }
}

function saveExportBgPreference(include) {
    try {
        localStorage.setItem(EXPORT_BG_KEY, include ? 'true' : 'false');
    } catch {
        // Storage unavailable (private mode, blocked site data): not remembered.
    }
}

function setExportBusy(busy) {
    exportInProgress = busy;
    const btn = document.getElementById('export-download-btn');
    btn.disabled = busy;
    btn.textContent = busy ? 'Exporting…' : 'Download';
}

async function onExportSubmit(e) {
    e.preventDefault();
    if (exportInProgress) return;
    setFormError('export-form-error', '');

    if (!window.htmlToImage || !window.jspdf) {
        setFormError('export-form-error', 'Export libraries failed to load. Reload the page and try again.');
        return;
    }
    if (!boardHasContent()) {
        setFormError('export-form-error', 'This board is empty: add a card or a note first.');
        return;
    }

    const format = document.querySelector('input[name="export_format"]:checked').value;
    const includeBg = document.getElementById('export-include-background').checked;
    saveExportBgPreference(includeBg);

    setExportBusy(true);
    let host = null;
    try {
        const bounds = computeExportBounds();
        const stage = buildExportStage(bounds, includeBg);
        host = mountOffscreen(stage);
        await prepareExportStage(stage);

        const filename = `${slugify(currentBoardName)}-${todayStamp()}.${format}`;
        if (format === 'png') await exportPng(stage, bounds, filename);
        else if (format === 'pdf') await exportPdf(stage, bounds, filename);
        else if (format === 'svg') await exportSvg(stage, bounds, filename);
        else throw new Error(`Unknown export format: ${format}`);

        closeExportModal();
    } catch (err) {
        console.error('Board export failed', err);
        setFormError('export-form-error', 'Export failed. Please try again.');
    } finally {
        if (host) host.remove();
        setExportBusy(false);
    }
}

// ---- Geometry ----

// Bounding box of every card, note and yarn in canvas coordinates (zoom 1),
// independent of the current pan/zoom.
function computeExportBounds() {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const extend = (x1, y1, x2, y2) => {
        minX = Math.min(minX, x1);
        minY = Math.min(minY, y1);
        maxX = Math.max(maxX, x2);
        maxY = Math.max(maxY, y2);
    };

    // offsetWidth/Height are layout sizes, unaffected by the canvas transform.
    // The pin sticks out ~12px above the top edge of a card.
    cards.forEach(c => extend(c.pos_x, c.pos_y - 12, c.pos_x + c.el.offsetWidth, c.pos_y + c.el.offsetHeight));
    notes.forEach(n => extend(n.pos_x, n.pos_y, n.pos_x + n.el.offsetWidth, n.pos_y + n.el.offsetHeight));

    // getBBox() returns the exact curve bounds in SVG user units (= canvas px).
    document.querySelectorAll('#connections-svg path').forEach(path => {
        try {
            const b = path.getBBox();
            const stroke = 4;
            extend(b.x - stroke, b.y - stroke, b.x + b.width + stroke, b.y + b.height + stroke);
        } catch {
            // Not rendered (e.g. detached): cards already cover the endpoints.
        }
    });

    const x = Math.floor(minX - EXPORT_MARGIN);
    const y = Math.floor(minY - EXPORT_MARGIN);
    return {
        x,
        y,
        width: Math.ceil(maxX + EXPORT_MARGIN) - x,
        height: Math.ceil(maxY + EXPORT_MARGIN) - y,
    };
}

// Largest density <= EXPORT_PIXEL_RATIO that keeps the canvas within limits.
function exportPixelRatio(width, height) {
    return Math.min(
        EXPORT_PIXEL_RATIO,
        EXPORT_MAX_SIDE / Math.max(width, height),
        Math.sqrt(EXPORT_MAX_AREA / (width * height)),
    );
}

// ---- Off-screen stage ----

// Keep the stage laid out (html-to-image reads computed styles) but invisible:
// a zero-size, clipping host. The stage itself must sit at offset 0, because
// html-to-image copies every computed property (including logical insets)
// onto the rendered copy, so an off-screen `left` would push the content out
// of frame.
function mountOffscreen(stage) {
    const host = document.createElement('div');
    host.setAttribute('aria-hidden', 'true');
    Object.assign(host.style, {
        position: 'fixed',
        left: '0',
        top: '0',
        width: '0',
        height: '0',
        overflow: 'hidden',
        pointerEvents: 'none',
        zIndex: '-1',
    });
    host.appendChild(stage);
    document.body.appendChild(host);
    return host;
}

// A clone of #canvas at zoom 1 inside a fixed-size box. The live board is
// never touched.
function buildExportStage(bounds, includeBg) {
    const stage = document.createElement('div');
    Object.assign(stage.style, {
        position: 'absolute',
        left: '0',
        top: '0',
        width: `${bounds.width}px`,
        height: `${bounds.height}px`,
        overflow: 'hidden',
        backgroundColor: 'transparent',
    });
    if (includeBg) {
        Object.assign(stage.style, {
            backgroundImage: `url('${EXPORT_CORK_URL}')`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
        });
    }

    const liveCanvas = document.getElementById('canvas');
    const canvas = liveCanvas.cloneNode(true);
    canvas.removeAttribute('id');
    Object.assign(canvas.style, {
        position: 'absolute',
        top: '0',
        left: '0',
        width: `${liveCanvas.offsetWidth}px`,
        height: `${liveCanvas.offsetHeight}px`,
        transformOrigin: '0 0',
        transform: `translate(${-bounds.x}px, ${-bounds.y}px)`,
    });

    // #connections-svg styles are id-based; inline them on the clone.
    const svg = canvas.querySelector('svg');
    if (svg) {
        svg.removeAttribute('id');
        Object.assign(svg.style, {
            position: 'absolute',
            top: '0',
            left: '0',
            width: '100%',
            height: '100%',
            overflow: 'visible',
            zIndex: '50',
            pointerEvents: 'none',
        });
    }

    stripUiState(canvas);
    stage.appendChild(canvas);
    return stage;
}

// Remove selection, hover/edit affordances and in-progress edits from a clone.
function stripUiState(root) {
    root.querySelectorAll('.selected').forEach(el => el.classList.remove('selected'));
    // Hide (not remove) the on-card color buttons so card heights match the board.
    root.querySelectorAll('.card-colors').forEach(el => { el.style.visibility = 'hidden'; });

    // A note being edited holds a textarea: show its saved content instead.
    root.querySelectorAll('.note-edit-area').forEach(area => {
        const noteEl = area.closest('.note');
        const note = noteEl && notes.find(n => String(n.id) === noteEl.dataset.id);
        const text = document.createElement('div');
        text.className = 'note-text';
        text.textContent = note ? note.content : area.value;
        area.replaceWith(text);
    });
    root.querySelectorAll('.note > :not(.note-text)').forEach(el => el.remove());
}

async function prepareExportStage(stage) {
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await Promise.all([...stage.querySelectorAll('img')].map(img =>
        img.decode ? img.decode().catch(() => {}) : null
    ));
}

function renderOptions(bounds, extra) {
    return {
        width: bounds.width,
        height: bounds.height,
        ...extra,
    };
}

// ---- Formats ----

async function exportPng(stage, bounds, filename) {
    const pixelRatio = exportPixelRatio(bounds.width, bounds.height);
    const blob = await htmlToImage.toBlob(stage, renderOptions(bounds, { pixelRatio }));
    if (!blob) throw new Error('PNG rendering returned no data');
    downloadBlob(blob, filename);
}

async function exportPdf(stage, bounds, filename) {
    const pixelRatio = exportPixelRatio(bounds.width, bounds.height);
    const dataUrl = await htmlToImage.toJpeg(stage, renderOptions(bounds, {
        pixelRatio,
        quality: EXPORT_JPEG_QUALITY,
        // JPEG has no alpha: without the cork the page is plain white.
        backgroundColor: '#ffffff',
    }));

    const pdf = new window.jspdf.jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const pageW = pdf.internal.pageSize.getWidth();
    const pageH = pdf.internal.pageSize.getHeight();
    const maxW = pageW - 2 * EXPORT_PDF_MARGIN_MM;
    const maxH = pageH - 2 * EXPORT_PDF_MARGIN_MM;
    const scale = Math.min(maxW / bounds.width, maxH / bounds.height);
    const imgW = bounds.width * scale;
    const imgH = bounds.height * scale;
    pdf.addImage(dataUrl, 'JPEG', (pageW - imgW) / 2, (pageH - imgH) / 2, imgW, imgH, undefined, 'FAST');
    pdf.save(filename);
}

async function exportSvg(stage, bounds, filename) {
    const dataUrl = await htmlToImage.toSvg(stage, renderOptions(bounds));
    const svgText = decodeURIComponent(dataUrl.slice(dataUrl.indexOf(',') + 1));
    downloadBlob(new Blob([svgText], { type: 'image/svg+xml' }), filename);
}

// ---- Helpers ----

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function slugify(name) {
    const slug = (name || '')
        .normalize('NFKD')
        .replace(/[̀-ͯ]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 60)
        .replace(/-+$/, '');
    return slug || 'board';
}

function todayStamp() {
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
