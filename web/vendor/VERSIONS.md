# Vendored libraries

Everything the page needs is served from this folder so the app works offline.
Do not replace these with CDN links.

| File | Library | Version | Source |
| --- | --- | --- | --- |
| `codemirror/codemirror.min.js` | CodeMirror | 5.65.16 | https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js |
| `codemirror/codemirror.min.css` | CodeMirror | 5.65.16 | https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css |
| `codemirror/mode/octave/octave.min.js` | CodeMirror octave mode (MATLAB highlighting) | 5.65.16 | https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/octave/octave.min.js |
| `codemirror/addon/edit/matchbrackets.min.js` | CodeMirror addon | 5.65.16 | https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/matchbrackets.min.js |
| `codemirror/addon/lint/lint.min.js` | CodeMirror addon | 5.65.16 | https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/lint/lint.min.js |
| `codemirror/addon/lint/lint.min.css` | CodeMirror addon | 5.65.16 | https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/lint/lint.min.css |
| `marked/marked.min.js` | marked | 12.0.2 | https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js |
| `katex/katex.min.js` | KaTeX | 0.16.11 | https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/katex.min.js |
| `katex/katex.min.css` | KaTeX | 0.16.11 | https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/katex.min.css |
| `katex/contrib/auto-render.min.js` | KaTeX auto-render | 0.16.11 | https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/contrib/auto-render.min.js |
| `katex/fonts/*.woff2` (20 files) | KaTeX fonts | 0.16.11 | https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/fonts/&lt;name&gt;.woff2 |

Notes:
- Only the `.woff2` fonts are vendored. `katex.min.css` also lists `.woff` / `.ttf`
  fallbacks, but every supported browser picks the `.woff2` file first, so the others are never requested.
- `katex.min.css` loads fonts from the relative path `fonts/`, so keep `katex/fonts/` next to it.
