# nanobaselib.github.io

Source and generated output of the [NanoBaseLib](https://nanobaselib.github.io) website,
the companion site of *NanoBaseLib: A Multi-Task Benchmark Dataset for Nanopore Sequencing*
(NeurIPS 2024, Datasets and Benchmarks Track).

The site is static HTML served by GitHub Pages. Pages are generated from the sources in
`src/` by `build.py`; both the sources and the generated HTML are committed so Pages needs
no build step.

## Layout

```
build.py              # generator (Python 3.9+, standard library only)
src/
  layout.html         # shared shell: head, header, footer
  pages/*.html        # one file per page; starts with a <!--meta {...} --> header
  data/datasets.json  # single source of truth for the 16 datasets / 44 samples
  data/benchmarks.json
  data/tools.json
  css/site.css        # design tokens, light/dark themes, components
  js/site.js          # theme toggle, sidebar, TOC, table sort/filter, copy buttons
assets/               # generated copies of site.css / site.js
data/                 # generated copies of the JSON files (public, machine-readable)
images/
*.html                # generated pages (do not edit by hand)
sitemap.xml, robots.txt, ploya.html (redirect)   # generated
```

## Editing

1. Change the page text in `src/pages/<page>.html`, or the numbers in `src/data/*.json`.
   Tables and charts (`{{dataset_overview_table}}`, `{{bc_chart_dna}}`, …) are rendered from
   the JSON by functions in `build.py`.
2. Run `python3 build.py --check` (the `--check` flag also verifies local links).
3. Preview with `python3 -m http.server` and open <http://localhost:8000>.
4. Commit `src/`, the generated HTML, `assets/` and `data/` together.

Page header fields: `title`, `description`, optional `lede`, `badges`, `heading`,
`layout` (`docs` default, or `home` for full-width pages) and `jsonld`.

## Design notes

- Fonts: Inter (text) and JetBrains Mono (identifiers, code), with system fallbacks.
- Colour tokens live in `:root` in `site.css`; dark mode follows the OS and can be toggled
  (stored in `localStorage` under `nbl-theme`).
- The four tasks use a fixed categorical palette (BC blue, PD orange, SA green, MD violet)
  validated for colour-vision deficiency in both themes.
- Legacy URLs are preserved (`dataset.html`, `raw.html`, `basecall.html`, …); `ploya.html`
  redirects to `polya.html`.

## Licenses

Website content: CC BY 4.0. Processed dataset: CC BY 4.0. Software: Apache 2.0.
