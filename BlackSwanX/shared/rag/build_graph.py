#!/usr/bin/env python3
"""
Proper knowledge-graph harvest from a PDF.

1. Windowed entity + relation extraction via Qwen (Ollama)
2. SQLite graph with per-page provenance
3. vis-network interactive HTML export (hover = type + description + pages)
4. OKF wiki (Markdown per document)

Usage:
  python3 build_graph.py /path/to/doc.pdf [output_dir]
"""
from __future__ import annotations
import json
import re
import sqlite3
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import pypdfium2 as pdfium
from openai import OpenAI

PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else "/Users/mango/Downloads/2025_Broschuere_BIM-Leitfaden_2.0_barrierefrei.pdf"
OUT_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/Users/mango/BlackSwanX/shared/rag/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
MODEL = "qwen2.5-coder:7b"
WINDOW = 3   # pages per harvest window
OVERLAP = 1  # overlap pages

# --------------------------------------------------------------------------- #
# SQLite graph
# --------------------------------------------------------------------------- #
DB_PATH = str(OUT_DIR / "knowledge_graph.db")

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            id      INTEGER PRIMARY KEY,
            name    TEXT NOT NULL,
            name_key TEXT NOT NULL UNIQUE,
            type    TEXT DEFAULT '',
            description TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS relations (
            id          INTEGER PRIMARY KEY,
            source_key  TEXT NOT NULL,
            target_key  TEXT NOT NULL,
            type        TEXT DEFAULT '',
            description TEXT DEFAULT '',
            UNIQUE(source_key, target_key, type)
        );
        CREATE TABLE IF NOT EXISTS mentions (
            name_key TEXT NOT NULL,
            page     INTEGER NOT NULL,
            PRIMARY KEY(name_key, page)
        );
        CREATE TABLE IF NOT EXISTS doc_summary (
            id      INTEGER PRIMARY KEY,
            title   TEXT,
            summary TEXT,
            pages   INTEGER
        );
    """)
    conn.commit()
    return conn


def upsert_entity(conn: sqlite3.Connection, name: str, etype: str, desc: str):
    key = name.strip().lower()
    if not key:
        return
    try:
        conn.execute(
            "INSERT INTO entities (name, name_key, type, description) VALUES (?,?,?,?)",
            (name.strip(), key, etype.strip(), desc.strip()),
        )
    except sqlite3.IntegrityError:
        # Update if better description
        conn.execute(
            "UPDATE entities SET type=COALESCE(NULLIF(?,''),type), "
            "description=CASE WHEN length(?)>length(description) THEN ? ELSE description END "
            "WHERE name_key=?",
            (etype.strip(), desc.strip(), desc.strip(), key),
        )


def upsert_relation(conn: sqlite3.Connection, src: str, tgt: str, rtype: str, desc: str):
    sk, tk = src.strip().lower(), tgt.strip().lower()
    if not sk or not tk or sk == tk:
        return
    try:
        conn.execute(
            "INSERT INTO relations (source_key,target_key,type,description) VALUES (?,?,?,?)",
            (sk, tk, rtype.strip(), desc.strip()),
        )
    except sqlite3.IntegrityError:
        pass


def add_mention(conn: sqlite3.Connection, name: str, page: int):
    key = name.strip().lower()
    if not key:
        return
    try:
        conn.execute("INSERT INTO mentions(name_key,page) VALUES (?,?)", (key, page))
    except sqlite3.IntegrityError:
        pass


# --------------------------------------------------------------------------- #
# PDF extraction
# --------------------------------------------------------------------------- #
def extract_pages(pdf_path: str) -> list[tuple[int, str]]:
    pdf = pdfium.PdfDocument(pdf_path)
    pages: list[tuple[int, str]] = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                text = page.get_textpage().get_text_range() or ""
            except Exception:
                text = ""
            if text.strip():
                pages.append((i + 1, text))  # 1-indexed pages
    finally:
        pdf.close()
    print(f"[PDF] extracted {len(pages)} pages with text", flush=True)
    return pages


# --------------------------------------------------------------------------- #
# Windowed harvest
# --------------------------------------------------------------------------- #
HARVEST_PROMPT = """You are a knowledge-graph harvester for a German BIM document.

Extract from the text:

ENTITIES — named real-world things relevant to BIM:
  - method: BIM-Methode, Qualitätssicherung, Kollisionsprüfung, etc.
  - standard: ISO 19650, VDI 2552, IFC, buildingSMART Certification, etc.
  - organization: Ministerium für Verkehr BW, DEGES, Autobahn GmbH, etc.
  - system: Landes-CDE, BIM-Portal, CDE, IFC-Format, Revit, etc.
  - role: BIM-Gesamtkoordinator, BIM-Fachkoordinator, BIM-Manager, Auftraggeber, etc.
  - concept: Level of Information Need, LOI, Digitaler Zwilling, Openness, etc.
  - document: AIA, BAP, BIM-Leitfaden 2.0, Masterplan BIM, etc.
  - process: Übergabeworkflow, Qualitätsprüfung, Bestandsdokumentation, etc.

DO NOT extract: page numbers, section headings (like "2.1 Schulungen"), table of contents entries.
Prefer entities that appear multiple times or are central to BIM.

RELATIONS — factual connections between two named entities:
  Types: implements, describes, requires, published_by, part_of, defines,
         uses, managed_by, supersedes, certifies, supports, references

Return ONLY this exact JSON (no preamble):
{
  "entities": [
    {"name": "BIM-Methode", "type": "method", "description": "Digitale Arbeitsmethode für Infrastrukturprojekte"}
  ],
  "relations": [
    {"source": "BIM-Leitfaden 2.0", "target": "BIM-Methode", "type": "describes", "description": "Leitfaden beschreibt die BIM-Methode für Baden-Württemberg"}
  ],
  "summary": "2-3 sentence summary of this section"
}

--- TEXT (pages {pages}) ---
{text}"""


def harvest_window(pages: list[tuple[int, str]], page_nums: list[int]) -> dict:
    text = "\n\n".join(f"[Seite {p}]\n{t}" for p, t in pages if t.strip())
    pages_str = ", ".join(str(p) for p in page_nums)
    prompt = HARVEST_PROMPT.replace("{pages}", pages_str).replace("{text}", text[:8000])
    try:
        msg = OLLAMA.chat.completions.create(
            model=MODEL,
            max_tokens=2000,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.choices[0].message.content or ""
        # Extract JSON block
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return {"entities": [], "relations": [], "summary": ""}
        data = json.loads(match.group())
        return {
            "entities": data.get("entities") or [],
            "relations": data.get("relations") or [],
            "summary": data.get("summary") or "",
        }
    except Exception as e:
        print(f"  [harvest error: {str(e)[:80]}]", flush=True)
        return {"entities": [], "relations": [], "summary": ""}


def windows(pages: list[tuple[int, str]], size: int, overlap: int) -> list[list[tuple[int, str]]]:
    step = max(1, size - overlap)
    out = []
    i, n = 0, len(pages)
    while i < n:
        chunk = pages[i : i + size]
        out.append(chunk)
        if i + size >= n:
            break
        i += step
    return out


def condense_summaries(summaries: list[str]) -> str:
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]
    joined = " ".join(summaries)[:6000]
    try:
        msg = OLLAMA.chat.completions.create(
            model=MODEL,
            max_tokens=400,
            temperature=0.1,
            messages=[{
                "role": "user",
                "content": (
                    "Fasse diese Abschnitts-Notizen zu einer 3-4 Sätze langen Zusammenfassung "
                    "des gesamten Dokuments zusammen. Auf Deutsch, sachlich:\n\n" + joined
                )
            }],
        )
        return (msg.choices[0].message.content or "").strip()
    except Exception:
        return joined[:800]


# --------------------------------------------------------------------------- #
# vis-network HTML export
# --------------------------------------------------------------------------- #
VIS_VERSION = "9.1.9"
VIS_URL = f"https://unpkg.com/vis-network@{VIS_VERSION}/standalone/umd/vis-network.min.js"

TYPE_COLORS = {
    "standard":     {"background": "#e91e8c", "border": "#c0186e"},
    "organization": {"background": "#2196f3", "border": "#1565c0"},
    "method":       {"background": "#ff9800", "border": "#e65100"},
    "system":       {"background": "#4caf50", "border": "#2e7d32"},
    "role":         {"background": "#9c27b0", "border": "#6a1b9a"},
    "concept":      {"background": "#00bcd4", "border": "#00838f"},
    "document":     {"background": "#607d8b", "border": "#37474f"},
    "process":      {"background": "#ff5722", "border": "#bf360c"},
}
DEFAULT_COLOR = {"background": "#78909c", "border": "#455a64"}


def _ensure_vis(out_dir: Path) -> str:
    local = out_dir / "vis-network.min.js"
    if not local.exists():
        print(f"[VIS] downloading vis-network {VIS_VERSION}…", flush=True)
        try:
            urllib.request.urlretrieve(VIS_URL, local)
        except Exception:
            return VIS_URL
    return local.name


def export_vis_network(conn: sqlite3.Connection, out_dir: Path, title: str = "LEGATUM Knowledge Graph") -> Path:
    # Load entities + mentions
    ents = conn.execute("SELECT name_key, name, type, description FROM entities").fetchall()
    rels = conn.execute("SELECT source_key, target_key, type, description FROM relations").fetchall()
    mentions_raw = conn.execute("SELECT name_key, page FROM mentions ORDER BY page").fetchall()

    # Build mention map: name_key → sorted list of pages
    mentions: dict[str, list[int]] = defaultdict(list)
    for mk, pg in mentions_raw:
        mentions[mk].append(pg)

    # Degree
    degree: Counter = Counter()
    for src, tgt, _, _ in rels:
        degree[src] += 1
        degree[tgt] += 1

    # Nodes
    known_keys = {e["name_key"] for e in ents}
    nodes = []
    for e in ents:
        key = e["name_key"]
        etype = (e["type"] or "").lower()
        color = TYPE_COLORS.get(etype, DEFAULT_COLOR)
        pages = mentions.get(key, [])
        page_str = f"Seiten: {', '.join(str(p) for p in sorted(set(pages)))}" if pages else ""
        tooltip = f"<b>{e['name']}</b><br><i>{etype}</i><br>{e['description'] or ''}<br>{page_str}"
        nodes.append({
            "id": key,
            "label": (e["name"] or key)[:35],
            "group": etype or "concept",
            "value": degree.get(key, 0) + 1,
            "title": tooltip,
            "color": color,
            "font": {"color": "#ffffff", "size": 13},
        })

    # Stub nodes for relation endpoints not in entities
    stub_keys = {e for src, tgt, _, _ in rels for e in (src, tgt)} - known_keys
    for k in stub_keys:
        nodes.append({
            "id": k,
            "label": k[:35],
            "group": "concept",
            "value": degree.get(k, 1),
            "color": DEFAULT_COLOR,
            "font": {"color": "#ffffff", "size": 11},
            "title": f"<b>{k}</b>",
        })

    # Edges
    edges = [
        {
            "from": src,
            "to": tgt,
            "label": rtype[:20],
            "title": desc or "",
            "arrows": "to",
        }
        for src, tgt, rtype, desc in rels
    ]

    vis_src = _ensure_vis(out_dir)

    # Legend HTML
    legend_items = "".join(
        f'<span style="display:inline-flex;align-items:center;margin:4px 8px">'
        f'<span style="width:12px;height:12px;border-radius:50%;background:{c["background"]};margin-right:5px"></span>'
        f'{t}</span>'
        for t, c in TYPE_COLORS.items()
    )

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<script src="{vis_src}"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{height:100%;background:#0b0e1a;color:#ddd;font-family:system-ui,-apple-system,sans-serif}}
  #net{{height:100vh;width:100%}}
  #hud{{position:fixed;top:12px;left:12px;z-index:9;background:rgba(10,14,32,0.88);
        padding:12px 16px;border-radius:10px;font-size:13px;max-width:340px;
        border:1px solid rgba(255,255,255,0.08)}}
  #hud h2{{font-size:15px;margin-bottom:6px;color:#fff}}
  #stats{{color:#aaa;font-size:12px;margin-bottom:8px}}
  #q{{width:220px;background:#1a1f3a;border:1px solid #333;color:#eee;
      border-radius:6px;padding:6px 10px;font-size:12px}}
  #legend{{margin-top:10px;font-size:11px;color:#aaa;line-height:1.8}}
  .vis-tooltip{{background:#0e1225 !important;border:1px solid #333 !important;
                color:#ddd !important;font-size:12px !important;border-radius:6px !important;
                padding:8px 10px !important;max-width:280px !important}}
</style></head><body>
<div id="hud">
  <h2>🧠 {title}</h2>
  <div id="stats">{len(nodes)} Entitäten · {len(edges)} Beziehungen</div>
  <input id="q" placeholder="Entity suchen…" oninput="focusNode(this.value)">
  <div id="legend">{legend_items}</div>
</div>
<div id="net"></div>
<script>
const nodes = new vis.DataSet({json.dumps(nodes, ensure_ascii=False)});
const edges = new vis.DataSet({json.dumps(edges, ensure_ascii=False)});

const options = {{
  nodes: {{
    shape: "dot",
    scaling: {{min: 8, max: 50, label: {{min:10,max:20}}}},
    borderWidth: 2,
    shadow: {{enabled:true, size:8, color:"rgba(0,0,0,0.5)"}},
  }},
  edges: {{
    arrows: {{to: {{scaleFactor: 0.5}}}},
    color: {{color:"#3a4060", highlight:"#7080c0", hover:"#5060a0"}},
    font: {{size: 9, color:"#8090b0", strokeWidth:0, align:"middle"}},
    smooth: {{type:"continuous"}},
    width: 1.5,
    selectionWidth: 3,
  }},
  physics: {{
    solver: "forceAtlas2Based",
    stabilization: {{iterations: 300, updateInterval: 25}},
    forceAtlas2Based: {{
      gravitationalConstant: -55,
      springLength: 130,
      springConstant: 0.08,
      damping: 0.9,
      centralGravity: 0.005,
    }},
  }},
  interaction: {{
    hover: true,
    tooltipDelay: 60,
    navigationButtons: true,
    keyboard: {{enabled:true, bindToWindow:false}},
    multiselect: true,
  }},
}};

const net = new vis.Network(document.getElementById("net"), {{nodes, edges}}, options);

net.on("stabilizationIterationsDone", () => {{
  net.setOptions({{physics:{{enabled:false}}}});
}});

// Highlight connected nodes on click
net.on("click", params => {{
  if (!params.nodes.length) return;
  const nid = params.nodes[0];
  const connected = net.getConnectedNodes(nid);
  nodes.update([nid, ...connected].map(id => ({{id, opacity:1}})));
}});

function focusNode(q) {{
  q = (q||"").toLowerCase().trim();
  if (!q) return;
  const hit = nodes.get().find(n => (n.label||"").toLowerCase().includes(q) || (n.id||"").includes(q));
  if (hit) {{
    net.selectNodes([hit.id]);
    net.focus(hit.id, {{scale:1.6, animation:{{duration:600, easingFunction:"easeInOutQuad"}}}});
  }}
}}

document.getElementById("q").addEventListener("keydown", e => {{
  if (e.key === "Enter") focusNode(e.target.value);
}});
</script></body></html>"""

    out = out_dir / "knowledge_graph.html"
    out.write_text(html, encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
# OKF wiki export
# --------------------------------------------------------------------------- #
def export_okf(conn: sqlite3.Connection, doc_title: str, summary: str, okf_dir: Path):
    okf_dir.mkdir(parents=True, exist_ok=True)
    ents = conn.execute("SELECT name, type, description FROM entities ORDER BY type, name").fetchall()
    rels = conn.execute("SELECT source_key, target_key, type, description FROM relations").fetchall()

    slug = re.sub(r"[^a-z0-9]+", "-", doc_title.lower()).strip("-")
    doc_file = okf_dir / "docs" / f"{slug}.md"
    doc_file.parent.mkdir(parents=True, exist_ok=True)

    by_type: dict[str, list] = defaultdict(list)
    for e in ents:
        by_type[(e["type"] or "concept")].append(e)

    lines = [
        "---",
        f"title: {doc_title}",
        "type: Document",
        "---",
        "",
        f"# {doc_title}",
        "",
        "## Summary",
        summary or "_(no summary)_",
        "",
        f"**Entities:** {len(ents)} · **Relations:** {len(rels)}",
        "",
    ]
    for etype, elist in sorted(by_type.items()):
        lines.append(f"## {etype.capitalize()}s")
        for e in elist:
            desc = f" — {e['description']}" if e["description"] else ""
            lines.append(f"- **{e['name']}**{desc}")
        lines.append("")

    doc_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OKF] wrote {doc_file}", flush=True)

    # Index
    idx = okf_dir / "index.md"
    idx.write_text(
        f"# OKF Knowledge Bundle\n\n"
        f"- [{doc_title}](docs/{slug}.md) — {summary[:120] if summary else ''}\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    pdf_path = PDF_PATH
    print(f"\n=== LEGATUM Graph Harvest ===", flush=True)
    print(f"PDF:   {pdf_path}", flush=True)
    print(f"Model: {MODEL}", flush=True)
    print(f"Out:   {OUT_DIR}\n", flush=True)

    # Extract text
    pages = extract_pages(pdf_path)
    doc_title = Path(pdf_path).stem

    # Init graph DB
    conn = init_db(DB_PATH)
    print(f"[DB] {DB_PATH}", flush=True)

    # Windowed harvest
    wins = windows(pages, WINDOW, OVERLAP)
    print(f"[harvest] {len(wins)} windows (window={WINDOW}, overlap={OVERLAP})", flush=True)

    all_summaries: list[str] = []
    total_ents = 0
    total_rels = 0

    for i, win in enumerate(wins, 1):
        page_nums = [p for p, _ in win]
        print(f"  window {i}/{len(wins)} pages={page_nums} … ", end="", flush=True)

        result = harvest_window(win, page_nums)
        n_ents = len(result["entities"])
        n_rels = len(result["relations"])
        print(f"{n_ents} entities, {n_rels} relations", flush=True)

        for e in result["entities"]:
            name = (e.get("name") or "").strip()
            if not name:
                continue
            upsert_entity(conn, name, e.get("type", ""), e.get("description", ""))
            for pg in page_nums:
                add_mention(conn, name, pg)

        for r in result["relations"]:
            src = (r.get("source") or "").strip()
            tgt = (r.get("target") or "").strip()
            if src and tgt:
                upsert_relation(conn, src, tgt, r.get("type", ""), r.get("description", ""))
                # Ensure both endpoints exist as entities
                upsert_entity(conn, src, "", "")
                upsert_entity(conn, tgt, "", "")

        if result.get("summary"):
            all_summaries.append(result["summary"])

        total_ents += n_ents
        total_rels += n_rels

    conn.commit()

    # Stats
    stats = dict(conn.execute("SELECT 'entities', count(*) FROM entities UNION ALL SELECT 'relations', count(*) FROM relations").fetchall())
    ent_count = conn.execute("SELECT count(*) FROM entities").fetchone()[0]
    rel_count = conn.execute("SELECT count(*) FROM relations").fetchone()[0]
    print(f"\n[graph] {ent_count} entities, {rel_count} relations", flush=True)

    # Condense summaries
    print("[summary] condensing…", flush=True)
    doc_summary = condense_summaries(all_summaries)
    conn.execute("INSERT OR REPLACE INTO doc_summary(id,title,summary,pages) VALUES(1,?,?,?)",
                 (doc_title, doc_summary, len(pages)))
    conn.commit()

    # vis-network export
    print("[vis] exporting knowledge_graph.html…", flush=True)
    graph_html = export_vis_network(conn, OUT_DIR, title="BIM-Leitfaden 2.0 — Knowledge Graph")
    print(f"[vis] → {graph_html}", flush=True)

    # OKF wiki
    okf_dir = Path("/Users/mango/BlackSwanX/shared/rag/okf")
    print("[okf] writing wiki…", flush=True)
    export_okf(conn, doc_title, doc_summary, okf_dir)

    conn.close()

    print(f"\n=== DONE ===")
    print(f"Graph:   {graph_html}")
    print(f"OKF:     {okf_dir}/docs/")
    print(f"DB:      {DB_PATH}")
    print(f"\nOpen:  open {graph_html}")


if __name__ == "__main__":
    main()
