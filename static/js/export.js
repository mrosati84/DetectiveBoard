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
        if (!['png', 'pdf', 'svg'].includes(format)) throw new Error(`Unknown export format: ${format}`);
        const bounds = computeExportBounds();
        const plan = planRender(bounds, format !== 'svg');
        const stage = buildExportStage(bounds, includeBg, plan.domScale);
        host = mountOffscreen(stage);
        await prepareExportStage(stage);

        const filename = `${slugify(currentBoardName)}-${todayStamp()}.${format}`;
        if (format === 'png') await exportPng(stage, plan, filename);
        else if (format === 'pdf') await exportPdf(stage, plan, filename);
        else await exportSvg(stage, plan, filename);

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

// WebKit (Safari, and every iOS browser) mis-renders box-shadow inside an
// SVG <foreignObject> when the image is drawn scaled onto a canvas: offset
// and blur are not scaled with the image, so shadows come out as hard,
// shifted rectangles. A CSS `transform: scale()` triggers the same bug.
// Blink and Gecko are unaffected.
function isWebKitEngine() {
    const ua = navigator.userAgent;
    return /AppleWebKit\//.test(ua) && !/Chrome\/|Chromium\//.test(ua);
}

// How to reach the target raster density for this browser:
// - default: render the stage at zoom 1 and let html-to-image upscale the
//   canvas (`pixelRatio`);
// - WebKit raster: scale the DOM itself with CSS `zoom` (which re-lays out
//   shadows at the larger size) and draw it 1:1 onto the canvas.
// `width`/`height` are the stage's CSS size as rendered.
function planRender(bounds, raster) {
    const ratio = raster ? exportPixelRatio(bounds.width, bounds.height) : 1;
    const domScale = raster && ratio !== 1 && isWebKitEngine() ? ratio : 1;
    return {
        domScale,
        pixelRatio: ratio / domScale,
        width: Math.round(bounds.width * domScale),
        height: Math.round(bounds.height * domScale),
    };
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

// A clone of #canvas inside a fixed-size box, at zoom 1 (or `domScale`, see
// planRender). The live board is never touched.
function buildExportStage(bounds, includeBg, domScale = 1) {
    const stage = document.createElement('div');
    Object.assign(stage.style, {
        position: 'absolute',
        left: '0',
        top: '0',
        width: `${Math.round(bounds.width * domScale)}px`,
        height: `${Math.round(bounds.height * domScale)}px`,
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
        // Under `zoom`, the translate lengths are scaled along with everything else.
        transform: `translate(${-bounds.x}px, ${-bounds.y}px)`,
    });
    if (domScale !== 1) canvas.style.zoom = String(domScale);

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

function renderOptions(plan, extra) {
    return {
        width: plan.width,
        height: plan.height,
        // Always explicit: html-to-image otherwise defaults to devicePixelRatio.
        pixelRatio: plan.pixelRatio,
        ...extra,
    };
}

// ---- Formats ----

// WebKit draws the SVG image before the data-URI images inside its
// <foreignObject> are decoded, so the first raster misses the cork and card
// photos. A throw-away warm-up render primes the decode cache.
async function rasterize(render, stage, options) {
    if (isWebKitEngine()) await render(stage, options);
    return render(stage, options);
}

async function exportPng(stage, plan, filename) {
    const blob = await rasterize(htmlToImage.toBlob, stage, renderOptions(plan));
    if (!blob) throw new Error('PNG rendering returned no data');
    downloadBlob(blob, filename);
}

async function exportPdf(stage, plan, filename) {
    const dataUrl = await rasterize(htmlToImage.toJpeg, stage, renderOptions(plan, {
        quality: EXPORT_JPEG_QUALITY,
        // JPEG has no alpha: without the cork the page is plain white.
        backgroundColor: '#ffffff',
    }));

    const pdf = new window.jspdf.jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const pageW = pdf.internal.pageSize.getWidth();
    const pageH = pdf.internal.pageSize.getHeight();
    const maxW = pageW - 2 * EXPORT_PDF_MARGIN_MM;
    const maxH = pageH - 2 * EXPORT_PDF_MARGIN_MM;
    const scale = Math.min(maxW / plan.width, maxH / plan.height);
    const imgW = plan.width * scale;
    const imgH = plan.height * scale;
    pdf.addImage(dataUrl, 'JPEG', (pageW - imgW) / 2, (pageH - imgH) / 2, imgW, imgH, undefined, 'FAST');
    pdf.save(filename);
}

async function exportSvg(stage, plan, filename) {
    const dataUrl = await htmlToImage.toSvg(stage, renderOptions(plan));
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
