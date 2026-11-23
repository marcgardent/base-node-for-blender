#!/usr/bin/env python3
"""Write site/state-of-the-art-autumn-2026.html, site/sitemap.xml and site/robots.txt.

    python3 tools/compare_page.py           # write them (make compare)
    python3 tools/compare_page.py --check   # fail if one is not up to date (make compare-check)

The page is a comparison of the tools that write node graphs as text, from site/compare/tools.toml
(a table per tool, with its sources). The site's address is in site/site.toml, its one place: the
canonical link, the Open Graph tags, the JSON-LD, the sitemap and robots.txt take it from there, and the
sitemap lists that file's `pages`.
"""

from __future__ import annotations

import html
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SITE_TOML = SITE / "site.toml"
TOOLS = SITE / "compare" / "tools.toml"
PAGE_NAME = "state-of-the-art-autumn-2026.html"
PAGE = SITE / PAGE_NAME
SITEMAP = SITE / "sitemap.xml"
ROBOTS = SITE / "robots.txt"

ARROW = re.compile(r"^Node (⇔|⇒|⇐) [A-Z][A-Za-z]*( \(.+\))?$")
LEVELS = {"yes", "no", "partial"}
LICENCES = {"open source", "free", "commercial"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def site() -> dict:
    data = tomllib.loads(SITE_TOML.read_text(encoding="utf-8"))
    if not data["url"].startswith("https://") or not data["url"].endswith("/"):
        raise SystemExit(f"{SITE_TOML.relative_to(ROOT)}: url must be https://…/")
    return data


def tools() -> dict:
    data = tomllib.loads(TOOLS.read_text(encoding="utf-8"))
    families = data["families"]
    for key in ("published", "modified"):
        if not DATE.match(data["page"][key]):
            raise SystemExit(f"{TOOLS.relative_to(ROOT)}: page.{key} is not YYYY-MM-DD")
    for name, t in data["tools"].items():
        where = f"{TOOLS.relative_to(ROOT)}: [tools.{name}]"
        if t["family"] not in families:
            raise SystemExit(f"{where}: no family {t['family']!r}")
        for arrow in t["arrows"]:
            if not ARROW.match(arrow):
                raise SystemExit(f"{where}: arrow {arrow!r} is not `Node ⇔|⇒|⇐ Format`")
        for key in ("diff", "build"):
            if t[key] not in LEVELS:
                raise SystemExit(f"{where}: {key} must be one of {sorted(LEVELS)}")
        if t["licence"] not in LICENCES:
            raise SystemExit(f"{where}: licence must be one of {sorted(LICENCES)}")
        if not t["sources"] or not all(s.startswith("https://") for s in t["sources"]):
            raise SystemExit(f"{where}: sources must be https:// URLs, one at least")
    return data


def e(s: str) -> str:
    return html.escape(s, quote=False)


def a(s: str) -> str:
    return html.escape(s, quote=True)


def inline(s: str) -> str:
    """Escaped text with `code` spans."""
    parts = e(s).split("`")
    if len(parts) % 2 == 0:
        raise SystemExit(f"unbalanced backticks in {s!r}")
    return "".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(parts))


def cell(level: str, note: str | None) -> str:
    tail = f' <span class="note">{inline(note)}</span>' if note else ""
    return f'<span class="lv lv-{level.replace(" ", "-")}">{level}</span>{tail}'


def arrow(s: str) -> str:
    head, _, rest = s.partition(" (")
    out = f'<span class="arrow">{e(head)}</span>'
    if rest:
        out += f' <span class="note">({e(rest)}</span>'
    return out


def rows(data: dict) -> str:
    out = []
    for key, t in data["tools"].items():
        arrows = "<br>".join(arrow(x) for x in t["arrows"])
        licence = cell(t["licence"], t.get("licence_note"))
        cells = [
            ("Host software", inline(t["host"]), ""),
            ("Format", inline(t["format"]), ""),
            ("Arrow", arrows, ' class="arrows"'),
            ("Readable git diff", cell(t["diff"], t.get("diff_note")), ""),
            ("Built from the file", cell(t["build"], t.get("build_note")), ""),
            ("Licence", licence, ""),
            ("Note", inline(t["note"]), ""),
        ]
        tds = "".join(f'            <td data-label="{label}"{cls}><span>{body}</span></td>\n' for label, body, cls in cells)
        out.append(
            f'          <tr id="{a(key)}">\n'
            f'            <th scope="row">{e(t["name"])}</th>\n'
            f'{tds}'
            f'          </tr>'
        )
    return "\n".join(out)


def families(data: dict) -> str:
    out = []
    for key, f in data["families"].items():
        names = ", ".join(e(t["name"]) for t in data["tools"].values() if t["family"] == key)
        out.append(
            f'    <h3 id="family-{a(key)}">{e(f["title"])}</h3>\n'
            f'    <p class="who">{names}</p>\n'
            f'    <p>{inline(f["text"].strip())}</p>'
        )
    return "\n".join(out)


def sources(data: dict) -> str:
    out = []
    for key, t in data["tools"].items():
        links = "<br>".join(f'<a href="{a(u)}">{e(u)}</a>' for u in t["sources"])
        out.append(f'      <li><a href="#{a(key)}">{e(t["name"])}</a><br>{links}</li>')
    return "\n".join(out)


STYLE = """\
    :root {
      color-scheme: dark light;
      --bg: #0f1115;
      --panel: #161920;
      --border: #262b36;
      --text: #e6e9ef;
      --muted: #939ab0;
      --accent: #4f9cf9;
      --ok: #3fb950;
      --warn: #d29922;
      --bad: #f85149;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    @media (prefers-color-scheme: light) {
      :root {
        --bg: #ffffff;
        --panel: #f6f8fa;
        --border: #d0d7de;
        --text: #1f2328;
        --muted: #59636e;
        --accent: #0969da;
        --ok: #1a7f37;
        --warn: #9a6700;
        --bad: #cf222e;
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
      font-size: 15px;
      line-height: 1.55;
    }
    .wrap {
      max-width: 1240px;
      margin: 0 auto;
      padding: 2.5rem 1rem 4rem;
    }
    header {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      justify-content: space-between;
      gap: 1rem;
      padding-bottom: 1.25rem;
      border-bottom: 1px solid var(--border);
    }
    header .brand {
      margin: 0;
      font-family: var(--mono);
      font-size: 1.4rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    header .brand span { color: var(--muted); font-weight: 400; }
    nav {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      font-family: var(--mono);
      font-size: 0.85rem;
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    h1 {
      margin: 2rem 0 0.5rem;
      font-size: 1.6rem;
      line-height: 1.25;
    }
    .date { color: var(--muted); font-family: var(--mono); font-size: 0.82rem; margin: 0; }
    .lead { margin: 1.25rem 0; font-size: 1.05rem; }
    h2 {
      margin: 2.5rem 0 0.75rem;
      font-size: 1.1rem;
      font-family: var(--mono);
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.35rem;
    }
    h3 { margin: 1.5rem 0 0.25rem; font-size: 1rem; }
    p { margin: 0.6rem 0; }
    code {
      font-family: var(--mono);
      font-size: 0.86em;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.05rem 0.3rem;
    }
    .legend {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 0.75rem;
      margin: 1rem 0;
      padding: 0;
      list-style: none;
    }
    .legend li {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.75rem 0.9rem;
    }
    .legend .arrow { display: block; font-size: 1.05rem; margin-bottom: 0.25rem; }
    .arrow { font-family: var(--mono); font-weight: 600; white-space: nowrap; }
    .table-scroll {
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 6px;
      margin: 1rem 0;
    }
    table {
      border-collapse: collapse;
      min-width: 1060px;
      width: 100%;
      font-size: 0.88rem;
    }
    th, td {
      text-align: left;
      padding: 0.5rem 0.65rem;
      border-bottom: 1px solid var(--border);
      border-right: 1px solid var(--border);
      vertical-align: top;
    }
    thead th {
      background: var(--panel);
      font-family: var(--mono);
      font-weight: 600;
      font-size: 0.8rem;
      white-space: nowrap;
    }
    tbody th { white-space: nowrap; }
    td[data-label="Note"] { min-width: 16rem; }
    td[data-label="Licence"] { min-width: 9rem; }
    tbody tr:last-child th, tbody tr:last-child td { border-bottom: 0; }
    th:last-child, td:last-child { border-right: 0; }
    @media (max-width: 760px) {
      .table-scroll { overflow: visible; border: 0; }
      table, thead, tbody, tr, th, td { display: block; min-width: 0; }
      table { min-width: 0; }
      thead { display: none; }
      tbody tr {
        border: 1px solid var(--border);
        border-radius: 6px;
        margin: 0 0 0.9rem;
        overflow: hidden;
      }
      tbody th {
        background: var(--panel);
        border-right: 0;
        font-size: 1rem;
      }
      td { border-right: 0; display: grid; grid-template-columns: 7.5rem 1fr; gap: 0.5rem; }
      td::before {
        content: attr(data-label);
        color: var(--muted);
        font-family: var(--mono);
        font-size: 0.75rem;
      }
      tbody tr:last-child th { border-bottom: 1px solid var(--border); }
    }
    .lv { font-family: var(--mono); font-size: 0.8rem; font-weight: 600; }
    .lv-yes { color: var(--ok); }
    .lv-partial { color: var(--warn); }
    .lv-no { color: var(--bad); }
    .note { color: var(--muted); font-size: 0.82rem; }
    .who { color: var(--muted); font-family: var(--mono); font-size: 0.8rem; margin: 0; }
    .sources { padding-left: 1.25rem; font-size: 0.85rem; overflow-wrap: anywhere; }
    .sources li { margin: 0.5rem 0; }
    footer {
      margin-top: 3rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border);
      color: var(--muted);
      font-size: 0.82rem;
      font-family: var(--mono);
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
"""


def page(data: dict, url: str, repo: str) -> str:
    p = data["page"]
    canonical = url + PAGE_NAME
    image = url + p["image"]
    ld = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": p["title"],
        "description": p["description"],
        "datePublished": p["published"],
        "dateModified": p["modified"],
        "inLanguage": "en",
        "url": canonical,
        "mainEntityOfPage": canonical,
        "image": image,
        "author": {"@type": "Organization", "name": "Base Node", "url": url},
        "about": [t["name"] for t in data["tools"].values()],
    }
    ld_text = json.dumps(ld, ensure_ascii=False, indent=2).replace("</", "<\\/")
    n = len(data["tools"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(p["title"])}</title>
  <meta name="description" content="{a(p["description"])}">
  <link rel="canonical" href="{a(canonical)}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{a(p["title"])}">
  <meta property="og:description" content="{a(p["description"])}">
  <meta property="og:url" content="{a(canonical)}">
  <meta property="og:image" content="{a(image)}">
  <meta property="og:site_name" content="Base Node">
  <meta property="article:published_time" content="{a(p["published"])}">
  <meta property="article:modified_time" content="{a(p["modified"])}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{a(p["title"])}">
  <meta name="twitter:description" content="{a(p["description"])}">
  <meta name="twitter:image" content="{a(image)}">
  <script type="application/ld+json">
{ld_text}
  </script>
  <style>
{STYLE}  </style>
</head>
<body>
  <!-- Generated from site/compare/tools.toml and site/site.toml: edit those, not this. -->
  <div class="wrap">
    <header>
      <p class="brand"><a href="index.html" style="color:inherit">base-node</a> <span>(.bn)</span></p>
      <nav>
        <a href="index.html">Home</a>
        <a href="tutorials/index.html">Tutorials</a>
        <a href="reference/index.html">Reference</a>
        <a href="developers.html">Developers</a>
        <a href="{a(repo)}">GitHub</a>
      </nav>
    </header>

    <h1>{e(p["title"])}</h1>
    <p class="date">Published <time datetime="{a(p["published"])}">{e(p["published"])}</time> · updated <time datetime="{a(p["modified"])}">{e(p["modified"])}</time></p>

    <p class="lead">Most node editors save their graphs in a file only the editor can read. Some write the graph as text and read the same text back: then a change shows as a diff in git, a reviewer can read it, a script or an AI model can write a graph, and a graph can be rebuilt from the file without clicking. This page compares {n} tools on that one question: which way does the graph go between the nodes and the text, and in which format.</p>

    <h2 id="legend">Legend</h2>
    <ul class="legend">
      <li><span class="arrow">Node ⇔ Text</span>Both ways. The file is the graph: it is saved and loaded back without loss.</li>
      <li><span class="arrow">Node ⇒ JSON</span>The graph is written out. The file is not read back into the same graph.</li>
      <li><span class="arrow">Node ⇐ Python</span>Code builds the graph. The graph is not read back as that code.</li>
    </ul>
    <p>The word after the arrow is the format: Text, JSON, XML or Python. A note in brackets says what limits it.</p>

    <h2 id="table">Comparison</h2>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th scope="col">Tool</th>
            <th scope="col">Host software</th>
            <th scope="col">Format</th>
            <th scope="col">Arrow</th>
            <th scope="col">Readable git diff</th>
            <th scope="col">Built from the file</th>
            <th scope="col">Licence</th>
            <th scope="col">Note</th>
          </tr>
        </thead>
        <tbody>
{rows(data)}
        </tbody>
      </table>
    </div>

    <h2 id="how-to-read">How to read it</h2>
    <p>The arrow says what you can do with the file. With <span class="arrow">⇔</span>, you can edit the text, load it, edit the nodes, save, and get text again. With <span class="arrow">⇒</span>, the text is a snapshot: edits to it do not come back. With <span class="arrow">⇐</span>, the code is the source and the nodes are its output.</p>
    <p><em>Readable git diff</em> says whether a change to the graph shows as a few changed lines. <em>Partial</em> means the file is text but carries generated ids, positions or long XML, or needs a tool to unpack it first. <em>Built from the file</em> says whether the graph can be made from the file by a script or a command, not by hand.</p>
    <p>Licence: <em>open source</em> is an OSI licence; <em>commercial</em> may have a free tier, named in the cell. Each row has its sources at the bottom of the page. A cell the sources do not settle says <em>partial</em>.</p>

    <h2 id="families">By family</h2>
{families(data)}

    <h2 id="sources">Sources</h2>
    <p>Checked on {e(p["modified"])}. The data of this page is <a href="compare/tools.toml">compare/tools.toml</a>.</p>
    <ol class="sources">
{sources(data)}
    </ol>

    <footer>
      <span>Base Node — MIT OR Apache-2.0 (Blender host binding: GPL-3.0-or-later)</span>
      <span><a href="index.html">Home</a> · <a href="developers.html">Developers</a> · <a href="{a(repo)}">Source</a></span>
    </footer>
  </div>
</body>
</html>
"""


def sitemap(data: dict, s: dict) -> str:
    url = s["url"]
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<!-- Generated from site/site.toml. -->',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in s["pages"]:
        loc = url if path == "index.html" else url + path
        lastmod = f"<lastmod>{data['page']['modified']}</lastmod>" if path == PAGE_NAME else ""
        out.append(f"  <url><loc>{html.escape(loc)}</loc>{lastmod}</url>")
    out.append("</urlset>")
    return "\n".join(out) + "\n"


def robots(s: dict) -> str:
    return f"# Generated from site/site.toml.\nUser-agent: *\nAllow: /\n\nSitemap: {s['url']}sitemap.xml\n"


def outputs() -> dict[Path, str]:
    s, data = site(), tools()
    if PAGE_NAME not in s["pages"]:
        raise SystemExit(f"{SITE_TOML.relative_to(ROOT)}: pages must list {PAGE_NAME}")
    return {PAGE: page(data, s["url"], s["repo"]), SITEMAP: sitemap(data, s), ROBOTS: robots(s)}


def main() -> None:
    check = "--check" in sys.argv[1:]
    stale = []
    for path, text in outputs().items():
        rel = path.relative_to(ROOT)
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(str(rel))
            continue
        path.write_text(text, encoding="utf-8")
        print(f"wrote {rel}")
    if stale:
        raise SystemExit(f"not up to date (make compare): {', '.join(stale)}")
    if check:
        print("the comparison page, sitemap.xml and robots.txt are up to date")


if __name__ == "__main__":
    main()
