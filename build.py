#!/usr/bin/env python3
"""Static site builder for nanobaselib.github.io.

    python3 build.py          # build everything into the repository root
    python3 build.py --check  # build and report broken local links

Sources live in src/ (layout, pages, data, css, js). The generated HTML at the
repository root is what GitHub Pages serves, so both are committed.
No third-party dependencies: Python 3.9+ standard library only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
SITE_URL = "https://nanobaselib.github.io"

DATA = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (SRC / "data").glob("*.json")}
DS = DATA["datasets"]
BM = DATA["benchmarks"]
TOOLS = DATA["tools"]

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
NAV = [
    ("Datasets", [("dataset.html", "Overview & statistics"), ("raw.html", "Raw data download")]),
    ("Pipeline", [("pipeline.html", "Preprocessing pipeline"), ("signal.html", "Signal processing")]),
    ("Benchmarks", [("benchmarks.html", "Overview"), ("basecall.html", "Base calling"), ("polya.html", "PolyA detection"),
                    ("segment.html", "Segmentation & event alignment"), ("mod.html", "Modification detection")]),
    ("Software", [("software.html", "Package & tutorials")]),
    ("Resources", [("links.html", "Nanopore links")]),
    ("About", [("about.html", "Paper & changelog")]),
]
FLAT = [(f, t, sec) for sec, pages in NAV for f, t in pages]
TASK_CLASS = {"BC": "task-bc", "PD": "task-pd", "SA": "task-sa", "MD": "task-md"}
TASK_NAME = DS["tasks"]

def esc(s) -> str:
    return html.escape(str(s), quote=True)

def slugify(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"

def fmt_int(n) -> str:
    return f"{int(n):,}"

# ---------------------------------------------------------------------------
# Data-driven components
# ---------------------------------------------------------------------------
def all_samples():
    for d in DS["datasets"]:
        for s in d["samples"]:
            yield d, s

def site_stats() -> dict:
    reads = sum(s.get("n_reads", 0) for _, s in all_samples())
    size_gb = sum(int(re.sub(r"\D", "", d["raw_size"])) for d in DS["datasets"])
    species = {d["species"] for d in DS["datasets"]}
    mods = {s["tasks"]["MD"] for _, s in all_samples() if isinstance(s["tasks"]["MD"], str)}
    return {"datasets": len(DS["datasets"]), "samples": sum(1 for _ in all_samples()), "reads": reads,
            "size_tb": size_gb / 1000, "species": len(species), "mods": sorted(mods)}

def c_stats_tiles() -> str:
    st = site_stats()
    tiles = [
        (f"{st['datasets']}", "public datasets, re-processed with one pipeline"),
        (f"{st['reads']/1e6:.1f}M", "reads with raw signal and base calls"),
        ("4", "benchmark tasks with baselines"),
        (f"{st['species']}", "species, DNA and RNA"),
        (f"{st['size_tb']:.1f} TB", "raw fast5 data indexed"),
        (f"{len(st['mods'])}", "RNA modification types (m6A, m5C, hm5C, inosine, Ψ)"),
    ]
    return '<div class="stats">' + "".join(
        f'<div class="stat"><div class="value">{esc(v)}</div><div class="label">{esc(l)}</div></div>' for v, l in tiles) + "</div>"

def task_badge(code: str, value) -> str:
    if value is True:
        return '<span class="check" aria-label="yes">✓</span>'
    if value is False or value in (None, ""):
        return '<span class="cross" aria-label="no">–</span>'
    return f'<span class="badge badge-task {TASK_CLASS[code]}"><span class="dot"></span>{esc(value)}</span>'

def dataset_link(d) -> str:
    extra = "".join(f' · <a href="{esc(e["href"])}">{esc(e["label"])}</a>' for e in d.get("accession_extra", []))
    return f'<a href="{esc(d["accession_url"])}" class="mono">{esc(d["accession"])}</a>{extra}'

def c_dataset_filters(table_id: str, with_tasks: bool = True) -> str:
    species = sorted({d["species"] for d in DS["datasets"]})
    types = sorted({d["type"] for d in DS["datasets"]})
    opts = lambda vals: "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in vals)
    chips = "".join(
        f'<button type="button" class="chip {TASK_CLASS[c]}" data-task="{c}" aria-pressed="false" title="{esc(TASK_NAME[c])}"><span class="dot"></span>{c}</button>'
        for c in ("BC", "PD", "SA", "MD")) if with_tasks else ""
    return f'''<div class="table-toolbar" data-filter-table="{table_id}" role="search">
  <input class="input" type="search" placeholder="Search dataset, sample, accession…" aria-label="Search samples">
  <select class="input" name="species" aria-label="Filter by species"><option value="">All species</option>{opts(species)}</select>
  <select class="input" name="type" aria-label="Filter by molecule type"><option value="">All types</option>{opts(types)}</select>
  {chips}
  <button type="button" class="chip reset">Reset</button>
  <span class="count"></span>
</div>'''

def c_dataset_overview_table() -> str:
    rows = []
    for d in DS["datasets"]:
        for i, s in enumerate(d["samples"]):
            tasks = " ".join(k for k, v in s["tasks"].items() if v)
            cls = "group-start" if i == 0 else ""
            name_cell = f'<td class="group-cell">{esc(d["id"])}</td>' if i == 0 else f'<td class="sub">{esc(d["id"])}</td>'
            rows.append(
                f'<tr class="{cls}" data-species="{esc(d["species"])}" data-type="{esc(d["type"])}" data-tasks="{tasks}">'
                f'{name_cell}<td class="nowrap">{esc(d["published"])}</td><td>{dataset_link(d)}</td>'
                f'<td><i>{esc(d["species"])}</i></td><td>{esc(d["type"])}</td><td class="mono">{esc(s["name"])}</td>'
                f'<td class="mono sub">{esc(s["flowcell"])}</td><td class="mono sub">{esc(s["kit"])}</td>'
                + "".join(f'<td style="text-align:center">{task_badge(c, s["tasks"][c])}</td>' for c in ("BC", "PD", "SA", "MD"))
                + "</tr>")
    head = ("<tr><th>Dataset</th><th>Published</th><th>Accession</th><th>Species</th><th>Type</th><th>Sample</th>"
            "<th>Flow cell</th><th>Kit</th>"
            + "".join(f'<th style="text-align:center" title="{esc(TASK_NAME[c])}" data-nosort>{c}</th>' for c in ("BC", "PD", "SA", "MD")) + "</tr>")
    return (c_dataset_filters("tbl-overview") +
            f'<div class="table-wrap"><table id="tbl-overview" data-sortable><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>')

def c_dataset_stats_table() -> str:
    rows = []
    for d in DS["datasets"]:
        for i, s in enumerate(d["samples"]):
            cls = "group-start" if i == 0 else ""
            name_cell = f'<td class="group-cell">{esc(d["id"])}</td>' if i == 0 else f'<td class="sub">{esc(d["id"])}</td>'
            size = f'<td class="num">{esc(d["raw_size"])}</td>' if i == 0 else '<td class="num sub"></td>'
            rows.append(
                f'<tr class="{cls}" data-species="{esc(d["species"])}" data-type="{esc(d["type"])}">'
                f'{name_cell}<td>{esc(d["type"])}</td>{size}<td class="mono">{esc(s["name"])}</td>'
                f'<td class="num">{fmt_int(s["n_fast5"])}</td><td class="num">{fmt_int(s["n_reads"])}</td>'
                f'<td class="num">{s["avg_signal_len"]:,.1f}</td><td class="num">{s["avg_base_len"]:,.1f}</td></tr>')
    head = ("<tr><th>Dataset</th><th>Type</th><th class=\"num\">Raw size</th><th>Sample</th><th class=\"num\"># multi-fast5</th>"
            "<th class=\"num\"># reads</th><th class=\"num\">Avg. signal length</th><th class=\"num\">Avg. base length*</th></tr>")
    return (c_dataset_filters("tbl-stats", with_tasks=False) +
            f'<div class="table-wrap"><table id="tbl-stats" data-sortable><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>')

DL_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>'

def c_raw_table() -> str:
    rows = []
    for d in DS["datasets"]:
        for i, s in enumerate(d["samples"]):
            cls = "group-start" if i == 0 else ""
            name_cell = f'<td class="group-cell">{esc(d["id"])}</td>' if i == 0 else f'<td class="sub">{esc(d["id"])}</td>'
            links = "<br>".join(f'<a class="dl-link" href="{esc(l["href"])}">{DL_ICON}{esc(l["label"])}</a>' for l in s.get("raw_links", []))
            rows.append(
                f'<tr class="{cls}" data-species="{esc(d["species"])}" data-type="{esc(d["type"])}">'
                f'{name_cell}<td class="nowrap">{esc(d["published"])}</td><td>{dataset_link(d)}</td><td><i>{esc(d["species"])}</i></td>'
                f'<td>{esc(d["type"])}</td><td class="mono">{esc(s["name"])}</td><td>{links}</td></tr>')
    head = "<tr><th>Dataset</th><th>Published</th><th>Accession</th><th>Species</th><th>Type</th><th>Sample</th><th data-nosort>Raw data (fast5)</th></tr>"
    return (c_dataset_filters("tbl-raw", with_tasks=False) +
            f'<div class="table-wrap"><table id="tbl-raw" data-sortable><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>')

def c_tools_table() -> str:
    step_names = {0: "Utility", 1: "1 · Standardization", 2: "2 · Base calling", 3: "3 · Mapping", 4: "4 · PolyA detection",
                  5: "5 · Segmentation & alignment", 6: "6 · Modification detection"}
    rows = "".join(
        f'<tr><td><a href="{esc(t["url"])}">{esc(t["name"])}</a></td><td class="mono">{esc(t["version"])}</td>'
        f'<td>{esc(step_names[t["step"]])}</td><td>{esc(t["function"])}</td><td class="sub">{esc(t["limitation"] or "–")}</td></tr>'
        for t in sorted(TOOLS, key=lambda t: (t["step"] or 99, t["name"].lower())))
    return ('<div class="table-wrap"><table data-sortable><thead><tr><th>Software</th><th>Version</th><th>Pipeline step</th>'
            f'<th>Function</th><th>Limitation</th></tr></thead><tbody>{rows}</tbody></table></div>')

def _bc_rows(kind: str):
    return BM["base_calling"][kind]["rows"]

def c_bc_table(kind: str) -> str:
    rows = _bc_rows(kind)
    metrics = BM["base_calling"]["metrics"]
    best_idx = {}
    for j, m in enumerate(metrics):
        vals = [r["values"][j] for r in rows]
        best_idx[j] = vals.index(max(vals) if m.startswith("M") else min(vals))
    head = ("<tr><th rowspan=\"2\">Model</th><th rowspan=\"2\">Version</th>"
            "<th colspan=\"4\" style=\"text-align:center\">Normalized by alignment length (%)</th>"
            "<th colspan=\"4\" style=\"text-align:center\">Normalized by reference length (%)</th></tr>"
            "<tr>" + "".join(f'<th class="num">{m} {"↑" if m == "M" else "↓"}</th>' for m in ("M", "I", "X", "D")) * 2 + "</tr>")
    body = ""
    for i, r in enumerate(rows):
        cells = "".join(
            f'<td class="num{" best" if best_idx[j] == i else ""}">{v:.2f}</td>' for j, v in enumerate(r["values"]))
        body += f'<tr><td><b>{esc(r["model"])}</b></td><td class="mono sub">{esc(r["version"] or "–")}</td>{cells}</tr>'
    return f'<div class="table-wrap"><table><thead>{head}</thead><tbody>{body}</tbody></table></div>'

def c_bc_chart(kind: str) -> str:
    """Dot plot of match rate (alignment-normalized). Axis 80–100 is explicit and labelled; dots, not bars, so no truncated-baseline issue."""
    rows = _bc_rows(kind)
    vals = [r["values"][0] for r in rows]
    best = vals.index(max(vals))
    w, left, right, row_h, top = 640, 170, 60, 30, 14
    h = top + row_h * len(rows) + 36
    x0, x1 = 80, 100
    xs = lambda v: left + (v - x0) / (x1 - x0) * (w - left - right)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="bc-{kind}-t"><title id="bc-{kind}-t">Match rate by base caller, {kind.upper()} test set {esc(BM["base_calling"][kind]["test_dataset"])}</title>']
    out.append('<g class="grid">' + "".join(f'<line x1="{xs(t):.1f}" x2="{xs(t):.1f}" y1="{top}" y2="{top + row_h*len(rows)}"/>' for t in range(80, 101, 5)) + "</g>")
    out.append('<g class="axis">' + f'<line x1="{left}" x2="{w-right}" y1="{top + row_h*len(rows)}" y2="{top + row_h*len(rows)}"/>' + "</g>")
    out.append("".join(f'<text class="tick" x="{xs(t):.1f}" y="{top + row_h*len(rows) + 16}" text-anchor="middle">{t}%</text>' for t in range(80, 101, 5)))
    out.append(f'<text class="tick" x="{w-right}" y="{h-2}" text-anchor="end">Match rate (M, normalized by alignment length)</text>')
    for i, r in enumerate(rows):
        cy = top + row_h * i + row_h / 2
        label = f'{r["model"]} {r["version"]}'.strip()
        cls = "mark best" if i == best else "mark"
        out.append(f'<text x="{left-10}" y="{cy+4}" text-anchor="end">{esc(label)}</text>')
        out.append(f'<line x1="{left}" x2="{xs(vals[i]):.1f}" y1="{cy}" y2="{cy}" stroke="var(--chart-grid)" stroke-width="2"/>')
        out.append(f'<circle class="{cls}" cx="{xs(vals[i]):.1f}" cy="{cy}" r="6" stroke="var(--bg-elev)" stroke-width="2"><title>{esc(label)}: {vals[i]:.2f}%</title></circle>')
        out.append(f'<text class="val" x="{xs(vals[i]) + 11:.1f}" y="{cy+4}">{vals[i]:.2f}</text>')
    out.append("</svg>")
    title = "DNA base calling" if kind == "dna" else "RNA base calling"
    return (f'<div class="chart"><div class="chart-title">{title}: match rate on {esc(BM["base_calling"][kind]["test_dataset"])}</div>'
            f'<div class="chart-sub">{fmt_int(BM["base_calling"][kind]["n_pairs"])} signal-chunk / reference pairs. Highlighted dot = best model.</div>'
            + "".join(out) + "</div>")

def bar_cell(v: float, vmax: float, best: bool, fmt: str = "{:.3f}") -> str:
    pct = max(0.0, min(100.0, v / vmax * 100 if vmax else 0))
    return (f'<td class="bar-cell"><div class="bar{" is-best" if best else ""}"><div class="track"><div class="fill" style="width:{pct:.1f}%"></div></div>'
            f'<span class="val{" best" if best else ""}">{fmt.format(v)}</span></div></td>')

def c_sa_table() -> str:
    sa = BM["segment_align"]
    models = sa["models"]
    head = ("<tr><th rowspan=\"2\">Test dataset</th><th colspan=\"3\" style=\"text-align:center\">Average std σ̂ (lower is better)</th>"
            "<th colspan=\"3\" style=\"text-align:center\">Average log-likelihood L̂ (higher is better)</th></tr><tr>"
            + "".join(f'<th>{esc(m)}</th>' for m in models) * 2 + "</tr>")
    body = ""
    for r in sa["rows"]:
        bstd = r["avg_std"].index(min(r["avg_std"])); blp = r["avg_logp"].index(max(r["avg_logp"]))
        vmax = max(r["avg_std"])
        cells = "".join(bar_cell(v, vmax, i == bstd) for i, v in enumerate(r["avg_std"]))
        cells += "".join(f'<td class="num{" best" if i == blp else ""}">{v:.3f}</td>' for i, v in enumerate(r["avg_logp"]))
        body += f'<tr><td class="mono">{esc(r["dataset"])}</td>{cells}</tr>'
    versions = " · ".join(f'{m}: {esc(v)}' for m, v in sa["model_versions"].items())
    return (f'<div class="table-wrap"><table><thead>{head}</thead><tbody>{body}</tbody></table></div>'
            f'<p class="sub">Baselines: {versions}. Std bars are scaled within each row; ★ marks the best value in each metric.</p>')

def c_md_m6a_table() -> str:
    m = BM["modification"]["m6a"]
    gts = m["ground_truths"]
    head = ("<tr><th rowspan=\"2\">Model</th><th colspan=\"3\" style=\"text-align:center\">ROC AUC ↑</th>"
            "<th colspan=\"3\" style=\"text-align:center\">PR AUC ↑</th></tr><tr>" + "".join(f'<th>{esc(g)}</th>' for g in gts) * 2 + "</tr>")
    best_roc = [max(r["roc"][j] for r in m["rows"]) for j in range(3)]
    best_pr = [max(r["pr"][j] for r in m["rows"]) for j in range(3)]
    body = ""
    for r in sorted(m["rows"], key=lambda r: -sum(r["roc"])):
        cells = "".join(bar_cell(v, 1.0, v == best_roc[j]) for j, v in enumerate(r["roc"]))
        cells += "".join(bar_cell(v, 1.0, v == best_pr[j]) for j, v in enumerate(r["pr"]))
        body += f'<tr><td><b>{esc(r["model"])}</b></td>{cells}</tr>'
    return f'<div class="table-wrap"><table><thead>{head}</thead><tbody>{body}</tbody></table></div>'

def c_md_m5c_table() -> str:
    m = BM["modification"]["m5c"]
    broc = max(r["roc"] for r in m["rows"]); bpr = max(r["pr"] for r in m["rows"])
    body = "".join(f'<tr><td><b>{esc(r["model"])}</b></td>{bar_cell(r["roc"], 1.0, r["roc"] == broc)}{bar_cell(r["pr"], 1.0, r["pr"] == bpr)}</tr>'
                   for r in sorted(m["rows"], key=lambda r: -r["roc"]))
    return ('<div class="table-wrap"><table><thead><tr><th>Model</th><th>ROC AUC ↑</th><th>PR AUC ↑</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')

def c_md_models_table() -> str:
    rows = "".join(
        f'<tr><td><b>{esc(r["model"])}</b>{(" · <a href=\"" + esc(r["paper"]) + "\">paper</a>") if r["paper"] else ""}</td>'
        f'<td class="mono sub">{esc(r["version"])}</td><td><a href="{esc(r["url"])}" class="dl-link">{esc(r["url"].replace("https://", ""))}</a></td>'
        f'<td>{esc(r["method"])}</td><td class="sub">{esc(r["scope"])}</td></tr>' for r in BM["modification"]["models"])
    return ('<div class="table-wrap"><table><thead><tr><th>Model</th><th>Version</th><th>Code</th><th>Method</th><th>Scope</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')

def c_polya_models_table() -> str:
    rows = "".join(
        f'<tr><td><b>{esc(r["model"])}</b></td><td class="mono sub">{esc(r["version"])}</td><td>{esc(r["approach"])}</td>'
        f'<td>{"Deep learning" if r["dl"] else "Statistical / HMM"}</td></tr>' for r in BM["polya"]["models"])
    return ('<div class="table-wrap"><table><thead><tr><th>Model</th><th>Version</th><th>Approach</th><th>Category</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')

def c_bc_downloads() -> str:
    return '<ul class="dl-list">' + "".join(
        f'<li><span>{esc(d["label"])}</span><span class="size">{esc(d["size"])}</span><a class="btn" href="{esc(d["href"])}">{DL_ICON} Download</a></li>'
        for d in BM["base_calling"]["downloads"]) + "</ul>"

def c_dataset_jsonld() -> str:
    st = site_stats()
    obj = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "NanoBaseLib: A Multi-Task Benchmark Dataset for Nanopore Sequencing",
        "description": f"{st['datasets']} public Nanopore sequencing datasets ({st['reads']:,} reads) re-processed with a unified pipeline for four benchmark tasks: base calling, polyA detection, segmentation and event alignment, and RNA modification detection.",
        "url": f"{SITE_URL}/dataset.html", "sameAs": DS["zenodo"], "identifier": f"https://doi.org/{DS['zenodo_doi']}",
        "license": "https://creativecommons.org/licenses/by/4.0/", "version": DS["version"], "isAccessibleForFree": True,
        "keywords": ["nanopore sequencing", "benchmark", "base calling", "polyA", "RNA modification", "m6A", "event alignment", "fast5"],
        "creator": [{"@type": "Person", "name": "Guangzhao Cheng", "affiliation": "Aalto University"},
                    {"@type": "Person", "name": "Chengbo Fu", "affiliation": "Aalto University"},
                    {"@type": "Person", "name": "Lu Cheng", "affiliation": "Aalto University"}],
        "citation": "Cheng, G., Fu, C., & Cheng, L. (2024). NanoBaseLib: A Multi-Task Benchmark Dataset for Nanopore Sequencing. NeurIPS 37, 76319-76331.",
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/gzip", "contentUrl": DS["zenodo"]}],
        "hasPart": [{"@type": "Dataset", "name": d["id"], "identifier": d["accession"], "url": d["accession_url"]} for d in DS["datasets"]],
    }
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>"

def c_dataset_count_sentence() -> str:
    st = site_stats()
    return f"{st['datasets']} datasets · {st['samples']} samples · {st['reads']:,} reads · {st['size_tb']:.1f} TB raw fast5"

def c_links_sections() -> str:
    out = []
    for g in DATA["links"]:
        cards = []
        for it in g["items"]:
            ext = it["url"].startswith("http")
            host = re.sub(r"^https?://(www\.)?", "", it["url"]).split("/")[0] if ext else "nanobaselib.github.io"
            cards.append(
                f'<article class="card link-card"><div class="link-head"><h3 data-toc="skip"><a class="stretched" href="{esc(it["url"])}">{esc(it["name"])}</a></h3>'
                f'<span class="badge">{esc(it["tag"])}</span></div><p>{esc(it["desc"])}</p><span class="link-host mono">{esc(host)}</span></article>')
        out.append(f'<h2>{esc(g["group"])}</h2><p class="muted">{esc(g["blurb"])}</p><div class="cards cards-links">{"".join(cards)}</div>')
    return "".join(out)

COMPONENTS = {
    "stats_tiles": c_stats_tiles,
    "dataset_overview_table": c_dataset_overview_table,
    "dataset_stats_table": c_dataset_stats_table,
    "raw_table": c_raw_table,
    "tools_table": c_tools_table,
    "bc_table_dna": lambda: c_bc_table("dna"), "bc_table_rna": lambda: c_bc_table("rna"),
    "bc_chart_dna": lambda: c_bc_chart("dna"), "bc_chart_rna": lambda: c_bc_chart("rna"),
    "bc_downloads": c_bc_downloads,
    "sa_table": c_sa_table,
    "md_m6a_table": c_md_m6a_table, "md_m5c_table": c_md_m5c_table, "md_models_table": c_md_models_table,
    "polya_models_table": c_polya_models_table,
    "dataset_count_sentence": c_dataset_count_sentence,
    "links_sections": c_links_sections,
    "links_count": lambda: str(sum(len(g["items"]) for g in DATA["links"])),
}

# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------
META_RE = re.compile(r"^\s*<!--meta\s*(\{.*?\})\s*-->", re.S)
HEADING_RE = re.compile(r"<h([23])([^>]*)>(.*?)</h\1>", re.S)

def render_components(content: str) -> str:
    def sub(m):
        name = m.group(1)
        if name not in COMPONENTS:
            raise SystemExit(f"unknown component {{{{{name}}}}}")
        return COMPONENTS[name]()
    return re.sub(r"\{\{(\w+)\}\}", sub, content)

def add_ids_and_toc(content: str):
    toc, seen = [], set()
    def sub(m):
        level, attrs, inner = m.group(1), m.group(2), m.group(3)
        if 'data-toc="skip"' in attrs:
            return m.group(0)
        idm = re.search(r'id="([^"]+)"', attrs)
        if idm:
            hid = idm.group(1)
        else:
            base = slugify(inner); hid = base; n = 2
            while hid in seen: hid = f"{base}-{n}"; n += 1
            attrs += f' id="{hid}"'
        seen.add(hid)
        toc.append((int(level), hid, html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()))
        return f"<h{level}{attrs}>{inner}</h{level}>"
    content = HEADING_RE.sub(sub, content)
    return content, toc

def top_nav(active_file: str) -> str:
    out = ['<a href="index.html"%s>Home</a>' % (' aria-current="true"' if active_file == "index.html" else "")]
    for sec, pages in NAV:
        cur = any(f == active_file for f, _ in pages)
        out.append(f'<a href="{pages[0][0]}"{" aria-current=\"true\"" if cur else ""}>{esc(sec)}</a>')
    return "\n      ".join(out)

def sidebar(active_file: str) -> str:
    groups = []
    for sec, pages in NAV:
        items = "".join(
            f'<li><a href="{f}"{" aria-current=\"page\"" if f == active_file else ""}>{esc(t)}</a></li>' for f, t in pages)
        groups.append(f'<div class="group"><div class="group-title">{esc(sec)}</div><ul>{items}</ul></div>')
    return f'<aside class="sidebar" id="sidebar" aria-label="Section navigation"><nav>{"".join(groups)}</nav></aside>'

def toc_html(toc) -> str:
    if len(toc) < 2:
        return '<aside class="toc" aria-hidden="true"></aside>'
    items = "".join(f'<li class="depth-{lvl}"><a href="#{hid}">{esc(txt)}</a></li>' for lvl, hid, txt in toc)
    return f'<aside class="toc" aria-label="On this page"><div class="toc-title">On this page</div><ul>{items}</ul></aside>'

def pager(active_file: str) -> str:
    idx = next((i for i, (f, _, _) in enumerate(FLAT) if f == active_file), None)
    if idx is None:
        return ""
    prev_ = FLAT[idx - 1] if idx > 0 else ("index.html", "Home", "")
    next_ = FLAT[idx + 1] if idx + 1 < len(FLAT) else None
    out = ['<nav class="pager" aria-label="Previous and next page">']
    out.append(f'<a class="prev" href="{prev_[0]}"><span class="dir">← Previous</span>{esc(prev_[1])}</a>')
    if next_:
        out.append(f'<a class="next" href="{next_[0]}"><span class="dir">Next →</span>{esc(next_[1])}</a>')
    out.append("</nav>")
    return "".join(out)

def build_page(path: Path, layout: str, build_hash: str, out_dir: Path):
    raw = path.read_text(encoding="utf-8")
    m = META_RE.match(raw)
    if not m:
        raise SystemExit(f"{path.name}: missing <!--meta {{...}} --> header")
    meta = json.loads(m.group(1))
    content = raw[m.end():]
    content = render_components(content)
    content, toc = add_ids_and_toc(content)
    fname = path.name
    section = next((sec for f, _, sec in FLAT if f == fname), "")
    kind = meta.get("layout", "docs")

    if kind == "docs":
        meta_badges = "".join(f'<span class="badge">{esc(render_components(b))}</span>' for b in meta.get("badges", []))
        eyebrow = f'<div class="eyebrow">{esc(section)}</div>' if section else ""
        lede = f'<p class="lede">{meta["lede"]}</p>' if meta.get("lede") else ""
        badges = f'<div class="meta">{meta_badges}</div>' if meta_badges else ""
        header = f'<div class="page-header">{eyebrow}<h1>{meta.get("heading", esc(meta["title"]))}</h1>{lede}{badges}</div>'
        body = (f'<div class="page docs">{sidebar(fname)}<main id="main">{header}{content}{pager(fname)}</main>{toc_html(toc)}</div>'
                '<div class="sidebar-backdrop"></div>')
    else:
        body = content

    page_title = meta["title"] if fname == "index.html" else f'{meta["title"]} · NanoBaseLib'
    html_out = (layout.replace("{{title}}", esc(page_title))
                .replace("{{description}}", esc(meta.get("description", "")))
                .replace("{{canonical}}", "" if fname == "index.html" else fname)
                .replace("{{site_url}}", SITE_URL)
                .replace("{{top_nav}}", top_nav(fname))
                .replace("{{body}}", body)
                .replace("{{body_class}}", f"layout-{kind}")
                .replace("{{head_extra}}", c_dataset_jsonld() if meta.get("jsonld") == "dataset" else "")
                .replace("{{build_hash}}", build_hash)
                .replace("{{year}}", str(dt.date.today().year))
                .replace("{{build_date}}", dt.date.today().isoformat()))
    (out_dir / fname).write_text(html_out, encoding="utf-8")
    return fname

REDIRECTS = {"ploya.html": "polya.html"}  # legacy URL kept alive

def write_redirects(out_dir: Path):
    for old, new in REDIRECTS.items():
        (out_dir / old).write_text(
            f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Redirecting…</title>'
            f'<meta http-equiv="refresh" content="0; url={new}"><link rel="canonical" href="{SITE_URL}/{new}">'
            f'<script>location.replace("{new}" + location.hash)</script></head>'
            f'<body><p>This page moved to <a href="{new}">{new}</a>.</p></body></html>\n', encoding="utf-8")

def write_sitemap(out_dir: Path, files):
    today = dt.date.today().isoformat()
    urls = "".join(f"<url><loc>{SITE_URL}/{'' if f == 'index.html' else f}</loc><lastmod>{today}</lastmod></url>" for f in files if f != "404.html")
    (out_dir / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    (out_dir / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")

def check_links(out_dir: Path, files):
    bad = []
    for f in files:
        txt = (out_dir / f).read_text(encoding="utf-8")
        for href in re.findall(r'(?:href|src)="([^"#?]+)', txt):
            if href.startswith(("http", "mailto:", "data:", "//")):
                continue
            if not (out_dir / href).exists():
                bad.append((f, href))
    return bad

def main():
    out_dir = ROOT
    assets = out_dir / "assets"; assets.mkdir(exist_ok=True)
    css = (SRC / "css" / "site.css").read_text(encoding="utf-8"); js = (SRC / "js" / "site.js").read_text(encoding="utf-8")
    build_hash = hashlib.sha1((css + js).encode()).hexdigest()[:8]
    (assets / "site.css").write_text(css, encoding="utf-8"); (assets / "site.js").write_text(js, encoding="utf-8")
    # expose data for programmatic consumers
    data_dir = out_dir / "data"; data_dir.mkdir(exist_ok=True)
    for name, obj in DATA.items():
        (data_dir / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    layout = (SRC / "layout.html").read_text(encoding="utf-8")
    files = [build_page(p, layout, build_hash, out_dir) for p in sorted((SRC / "pages").glob("*.html"))]
    write_redirects(out_dir); write_sitemap(out_dir, files)
    print(f"built {len(files)} pages + {len(REDIRECTS)} redirects (assets v{build_hash})")
    if "--check" in sys.argv:
        bad = check_links(out_dir, files)
        for f, h in bad:
            print(f"  broken: {f} -> {h}")
        print("links ok" if not bad else f"{len(bad)} broken links")
        sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
