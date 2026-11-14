# Vendored JavaScript libraries

Third-party libraries committed as-is (no build step). Loaded only by
`templates/index.html` for board export.

| File | Library | Version | Source | License |
|---|---|---|---|---|
| `html-to-image-1.11.11.js` | [html-to-image](https://github.com/bubkoo/html-to-image) | 1.11.11 | `https://unpkg.com/html-to-image@1.11.11/dist/html-to-image.js` | MIT (`html-to-image.LICENSE`) |
| `jspdf-2.5.2.umd.min.js` | [jsPDF](https://github.com/parallax/jsPDF) | 2.5.2 | `https://unpkg.com/jspdf@2.5.2/dist/jspdf.umd.min.js` | MIT (`jspdf.LICENSE`) |

To upgrade, download the new release, rename it with the new version, update
the `<script>` tags in `templates/index.html`, the tests in
`tests/test_export.py`, and this table.
