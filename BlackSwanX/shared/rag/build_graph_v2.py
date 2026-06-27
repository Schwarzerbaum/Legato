#!/usr/bin/env python3
"""
LEGATUM Graph v2 — all 4 improvements:

1. Hierarchical chunking:  Doc → Chapter → Section → page windows
2. Semantic graph traversal: chapter nodes link to child entities
3. Layout-aware parsing: Markdown tables extracted and linked to entities
4. Self-correction ready: per-entity source/page provenance for CRAG grading

Plus: phi4:14b for extraction (much better than qwen2.5-coder:7b)
Plus: rich interactive vis-network (click = neighbor highlight + side panel)

Usage:
  python3 build_graph_v2.py /path/to/doc.pdf [output_dir]
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

PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else \
    "/Users/mango/Downloads/2025_Broschuere_BIM-Leitfaden_2.0_barrierefrei.pdf"
OUT_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else \
    Path("/Users/mango/BlackSwanX/shared/rag/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
EXTRACT_MODEL = "phi4:14b"    # much better reasoning than qwen2.5-coder:7b
SYNTH_MODEL   = "phi4:14b"
WINDOW        = 3
OVERLAP       = 1

DB_PATH = str(OUT_DIR / "knowledge_graph_v2.db")

# ─────────────────────────────────────────────────────────────────────────────
# SQLite graph (same schema + hierarchy table)
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            name_key    TEXT NOT NULL UNIQUE,
            type        TEXT DEFAULT '',
            description TEXT DEFAULT '',
            importance  INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS relations (
            id          INTEGER PRIMARY KEY,
            source_key  TEXT NOT NULL,
            target_key  TEXT NOT NULL,
            type        TEXT DEFAULT '',
            description TEXT DEFAULT '',
            confidence  REAL DEFAULT 1.0,
            UNIQUE(source_key, target_key, type)
        );
        CREATE TABLE IF NOT EXISTS mentions (
            name_key  TEXT NOT NULL,
            page      INTEGER NOT NULL,
            chapter   TEXT DEFAULT '',
            context   TEXT DEFAULT '',
            PRIMARY KEY(name_key, page)
        );
        -- Hierarchical: chapters and their page ranges
        CREATE TABLE IF NOT EXISTS chapters (
            id          INTEGER PRIMARY KEY,
            title       TEXT NOT NULL,
            chapter_key TEXT NOT NULL UNIQUE,
            start_page  INTEGER,
            end_page    INTEGER,
            parent_key  TEXT DEFAULT ''
        );
        -- Which entities belong to which chapter
        CREATE TABLE IF NOT EXISTS chapter_entities (
            chapter_key TEXT NOT NULL,
            name_key    TEXT NOT NULL,
            PRIMARY KEY(chapter_key, name_key)
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


def key(s: str) -> str:
    return s.strip().lower()


def upsert_entity(conn, name: str, etype: str, desc: str, importance: int = 1):
    k = key(name)
    if not k or len(k) < 2:
        return
    try:
        conn.execute(
            "INSERT INTO entities (name,name_key,type,description,importance) VALUES(?,?,?,?,?)",
            (name.strip(), k, etype.strip(), desc.strip(), importance),
        )
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE entities SET "
            "  type=COALESCE(NULLIF(?,''),type), "
            "  description=CASE WHEN length(?)>length(description) THEN ? ELSE description END, "
            "  importance=MAX(importance,?) "
            "WHERE name_key=?",
            (etype.strip(), desc.strip(), desc.strip(), importance, k),
        )


def upsert_relation(conn, src: str, tgt: str, rtype: str, desc: str, conf: float = 1.0):
    sk, tk = key(src), key(tgt)
    if not sk or not tk or sk == tk or len(sk) < 2 or len(tk) < 2:
        return
    try:
        conn.execute(
            "INSERT INTO relations(source_key,target_key,type,description,confidence) "
            "VALUES(?,?,?,?,?)",
            (sk, tk, rtype.strip(), desc.strip(), conf),
        )
    except sqlite3.IntegrityError:
        pass


def add_mention(conn, name: str, page: int, chapter: str = "", context: str = ""):
    k = key(name)
    if not k:
        return
    try:
        conn.execute(
            "INSERT INTO mentions(name_key,page,chapter,context) VALUES(?,?,?,?)",
            (k, page, chapter, context[:200]),
        )
    except sqlite3.IntegrityError:
        pass


def upsert_chapter(conn, title: str, start: int, end: int, parent: str = ""):
    ck = key(title)
    try:
        conn.execute(
            "INSERT INTO chapters(title,chapter_key,start_page,end_page,parent_key) "
            "VALUES(?,?,?,?,?)",
            (title.strip(), ck, start, end, parent),
        )
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE chapters SET end_page=? WHERE chapter_key=?", (end, ck)
        )


def link_chapter_entity(conn, chapter_key: str, name: str):
    k = key(name)
    try:
        conn.execute(
            "INSERT INTO chapter_entities(chapter_key,name_key) VALUES(?,?)",
            (chapter_key, k),
        )
    except sqlite3.IntegrityError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 1. Layout-aware PDF extraction
# ─────────────────────────────────────────────────────────────────────────────

CHAPTER_RE = re.compile(
    r'^(\d+\.?\d*\.?\d*)\s+([A-ZÄÖÜ][^\n]{3,60})$', re.MULTILINE
)
TABLE_HEADER_RE = re.compile(r'\|.*\|.*\|')


def detect_chapters(pages: list[tuple[int, str]]) -> list[dict]:
    """Detect chapter/section headings and their page ranges."""
    chapters = []
    all_text = "\n".join(f"[PAGE:{p}]\n{t}" for p, t in pages)

    # Ask phi4 to identify the document's chapter structure
    prompt = (
        "You are analysing a German BIM document. From the text below, extract the "
        "table of contents / chapter structure. Return a JSON array of chapters:\n"
        '[{"number": "1", "title": "Einführung", "page": 3}, ...]\n'
        "Only include numbered chapters and major subsections. Return ONLY valid JSON.\n\n"
        + all_text[:6000]
    )
    try:
        msg = OLLAMA.chat.completions.create(
            model=EXTRACT_MODEL, max_tokens=1000, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.choices[0].message.content or ""
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            chapters = json.loads(match.group())
    except Exception as e:
        print(f"  [chapter detection error: {e}]", flush=True)

    return chapters


def extract_tables_as_markdown(text: str, page: int) -> list[str]:
    """Extract pipe-delimited table blocks and return as markdown strings."""
    tables = []
    lines = text.split('\n')
    in_table = False
    buf: list[str] = []
    for ln in lines:
        if '|' in ln and ln.count('|') >= 2:
            in_table = True
            buf.append(ln)
        else:
            if in_table and len(buf) >= 2:
                tables.append('\n'.join(buf))
            in_table = False
            buf = []
    if in_table and len(buf) >= 2:
        tables.append('\n'.join(buf))
    return tables


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
                pages.append((i + 1, text))
    finally:
        pdf.close()
    print(f"[PDF] {len(pages)} pages with text", flush=True)
    return pages


# ─────────────────────────────────────────────────────────────────────────────
# 2. Hierarchical chunking + windowed entity/relation extraction
# ─────────────────────────────────────────────────────────────────────────────

HARVEST_PROMPT = """You are a knowledge-graph harvester for a German BIM (Building Information Modeling) document.

Extract from the text below:

ENTITIES — significant named real-world things:
  Types: method, standard, organization, system, role, concept, document, process, model, tool
  Examples:
    method: BIM-Methode, Qualitätssicherung, Kollisionsprüfung, Übergabeworkflow
    standard: ISO 19650, VDI 2552, IFC, buildingSMART Certification, DIN SPEC 91391
    organization: Ministerium für Verkehr BW, DEGES, Autobahn GmbH, SBV BW, BMV
    system: Landes-CDE, BIM-Portal, IFC-Format, Revit, CDE
    role: BIM-Gesamtkoordinator, BIM-Fachkoordinator, BIM-Manager, Auftraggeber, AN
    concept: Level of Information Need, LOI, Digitaler Zwilling, LOIN, LOG, LOD, LoD
    document: AIA, BAP, BIM-Leitfaden 2.0, Masterplan BIM, BIM-BVB, Muster-BAP
    process: Freigabeprozess, Qualitätsprüfung, Bestandsdokumentation, Koordinationsmodell
    model: Fachmodell, Koordinationsmodell, Bestandsmodell, As-Built-Modell, Teilmodell

IMPORTANT: Do NOT extract: page numbers, section headings (like "2.1"), bare table of contents entries.
Extract entities that appear in actual content — things that are DEFINED, DESCRIBED or REFERENCED.
Include importance 1-3 (3 = central concept).

RELATIONS — typed factual connections:
  Types: implements, describes, requires, published_by, part_of, defines, uses,
         managed_by, supersedes, certifies, supports, references, enables,
         created_during, follows, links_to, specifies

TABLES: If you see tabular data (responsibilities, phase gates, role assignments), extract
the key entity-relationships from it as additional relations.

Return ONLY this JSON (no preamble or explanation):
{
  "entities": [
    {"name": "AIA", "type": "document", "description": "Auftraggeber-Informationsanforderungen, defines digital deliverables", "importance": 3}
  ],
  "relations": [
    {"source": "AIA", "target": "BIM-Methode", "type": "describes", "description": "AIA beschreibt die BIM-Anforderungen des Auftraggebers", "confidence": 0.95}
  ],
  "summary": "2-3 sentence section summary"
}

--- TEXT (pages {PAGES}) ---
{TEXT}"""


def harvest_window(win_pages: list[tuple[int, str]], page_nums: list[int],
                   chapter: str = "") -> dict:
    # Include any table markdown
    parts = []
    for p, t in win_pages:
        tables = extract_tables_as_markdown(t, p)
        section = f"[Seite {p}]\n{t}"
        if tables:
            section += "\n\n[TABELLEN AUF DIESER SEITE]\n" + "\n\n".join(tables)
        parts.append(section)

    text = "\n\n".join(parts)
    if chapter:
        text = f"[KAPITEL: {chapter}]\n\n" + text

    prompt = (HARVEST_PROMPT
              .replace("{PAGES}", ", ".join(str(p) for p in page_nums))
              .replace("{TEXT}", text[:9000]))

    try:
        msg = OLLAMA.chat.completions.create(
            model=EXTRACT_MODEL, max_tokens=2500, temperature=0.05,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.choices[0].message.content or ""
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


def windows(pages: list[tuple[int, str]], size: int, overlap: int):
    step = max(1, size - overlap)
    i, n = 0, len(pages)
    while i < n:
        yield pages[i: i + size]
        if i + size >= n:
            break
        i += step


# ─────────────────────────────────────────────────────────────────────────────
# Condense summaries
# ─────────────────────────────────────────────────────────────────────────────

def condense(summaries: list[str]) -> str:
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]
    joined = " ".join(summaries)[:6000]
    try:
        msg = OLLAMA.chat.completions.create(
            model=SYNTH_MODEL, max_tokens=500, temperature=0.1,
            messages=[{"role": "user", "content": (
                "Fasse diese Abschnitts-Notizen zu einer 4-5 Sätze langen "
                "Zusammenfassung des gesamten Dokuments auf Deutsch zusammen:\n\n" + joined
            )}],
        )
        return (msg.choices[0].message.content or "").strip()
    except Exception:
        return joined[:800]


# ─────────────────────────────────────────────────────────────────────────────
# vis-network HTML — rich interactive version
# ─────────────────────────────────────────────────────────────────────────────

VIS_URL = "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"

TYPE_COLORS = {
    "standard":     {"bg": "#e91e8c", "border": "#9c0f5f"},
    "organization": {"bg": "#1e88e5", "border": "#1145a0"},
    "method":       {"bg": "#f57c00", "border": "#a04000"},
    "system":       {"bg": "#2ecc71", "border": "#1a7a43"},
    "role":         {"bg": "#9b59b6", "border": "#6c3483"},
    "concept":      {"bg": "#00bcd4", "border": "#006978"},
    "document":     {"bg": "#607d8b", "border": "#37474f"},
    "process":      {"bg": "#e74c3c", "border": "#922b21"},
    "model":        {"bg": "#27ae60", "border": "#145a32"},
    "tool":         {"bg": "#f39c12", "border": "#9a6205"},
}
DEFAULT = {"bg": "#546e7a", "border": "#263238"}


def _vis_js(out_dir: Path) -> str:
    local = out_dir / "vis-network.min.js"
    if not local.exists():
        print("[VIS] downloading vis-network…", flush=True)
        try:
            urllib.request.urlretrieve(VIS_URL, local)
        except Exception:
            return VIS_URL
    return local.name


def export_vis(conn: sqlite3.Connection, out_dir: Path,
               title: str = "LEGATUM Knowledge Graph") -> Path:

    ents   = conn.execute("SELECT name_key,name,type,description,importance FROM entities").fetchall()
    rels   = conn.execute("SELECT source_key,target_key,type,description,confidence FROM relations").fetchall()
    ments  = conn.execute("SELECT name_key,page,chapter,context FROM mentions").fetchall()
    chaps  = conn.execute("SELECT chapter_key,title,start_page,end_page FROM chapters").fetchall()
    ch_ents = conn.execute("SELECT chapter_key,name_key FROM chapter_entities").fetchall()

    # Mention map
    mention_map: dict[str, list[dict]] = defaultdict(list)
    for mk, pg, ch, ctx in ments:
        mention_map[mk].append({"page": pg, "chapter": ch, "context": ctx})

    chapter_entity_map: dict[str, list[str]] = defaultdict(list)
    for ck, nk in ch_ents:
        chapter_entity_map[ck].append(nk)

    degree: Counter = Counter()
    for src, tgt, *_ in rels:
        degree[src] += 1
        degree[tgt] += 1

    known_keys = {e["name_key"] for e in ents}

    # Build nodes
    nodes_data = []
    for e in ents:
        k, name, etype = e["name_key"], e["name"], (e["type"] or "concept").lower()
        c = TYPE_COLORS.get(etype, DEFAULT)
        ms = mention_map.get(k, [])
        pages_sorted = sorted({m["page"] for m in ms})
        chapters_list = sorted({m["chapter"] for m in ms if m["chapter"]})
        ctx_samples = [m["context"] for m in ms[:2] if m["context"]]
        imp = e["importance"] or 1

        tooltip_lines = [
            f"<b style='font-size:14px'>{name}</b>",
            f"<span style='color:#aaa'>Type: {etype}</span>",
            f"<hr style='border:0;border-top:1px solid #333;margin:5px 0'>",
        ]
        if e["description"]:
            tooltip_lines.append(f"{e['description']}")
        if pages_sorted:
            tooltip_lines.append(f"<br><b>Seiten:</b> {', '.join(str(p) for p in pages_sorted[:10])}")
        if chapters_list:
            tooltip_lines.append(f"<b>Kapitel:</b> {'; '.join(chapters_list[:3])}")
        if ctx_samples:
            tooltip_lines.append(f"<b>Kontext:</b> <i>…{ctx_samples[0][:120]}…</i>")
        tooltip_lines.append(f"<b>Verbindungen:</b> {degree.get(k, 0)}")

        nodes_data.append({
            "id": k,
            "label": (name or k)[:32],
            "group": etype,
            "value": (degree.get(k, 0) + 1) * imp,
            "title": "<br>".join(tooltip_lines),
            "color": {"background": c["bg"], "border": c["border"],
                      "highlight": {"background": c["bg"], "border": "#ffffff"},
                      "hover": {"background": c["bg"], "border": "#ffffff"}},
            "font": {"color": "#ffffff", "size": 12 + min(imp * 2, 6)},
            "shadow": {"enabled": True, "size": 10, "color": c["bg"] + "55"},
        })

    # Stub nodes for endpoints not in entity table
    stub_keys = {e for src, tgt, *_ in rels for e in (src, tgt)} - known_keys
    for k in stub_keys:
        nodes_data.append({
            "id": k, "label": k[:30], "group": "concept", "value": degree.get(k, 1),
            "color": {"background": DEFAULT["bg"], "border": DEFAULT["border"]},
            "font": {"color": "#cccccc", "size": 10},
            "title": f"<b>{k}</b>",
        })

    # Chapter nodes (hierarchical)
    for ch in chaps:
        ck, ct = ch["chapter_key"], ch["title"]
        child_count = len(chapter_entity_map.get(ck, []))
        nodes_data.append({
            "id": f"__ch_{ck}",
            "label": ct[:28],
            "group": "chapter",
            "shape": "diamond",
            "value": max(child_count * 2, 3),
            "color": {"background": "#1a2540", "border": "#3d5af1"},
            "font": {"color": "#7089ff", "size": 11},
            "title": f"<b>📂 {ct}</b><br>Seiten: {ch['start_page']}–{ch['end_page']}<br>Entitäten: {child_count}",
        })

    # Chapter → entity edges (dashed)
    edges_data = []
    for ck, nks in chapter_entity_map.items():
        for nk in nks[:8]:  # limit fan-out per chapter
            edges_data.append({
                "from": f"__ch_{ck}", "to": nk,
                "dashes": True, "width": 0.8,
                "color": {"color": "#1e2d5a", "opacity": 0.5},
                "arrows": "", "label": "",
            })

    # Relation edges
    for src, tgt, rtype, desc, conf in rels:
        edges_data.append({
            "from": src, "to": tgt,
            "label": rtype[:18],
            "title": f"<b>{rtype}</b><br>{desc or ''}",
            "arrows": "to",
            "width": max(0.8, (conf or 1.0) * 2),
            "color": {"color": "#3a4575", "highlight": "#6080d0", "hover": "#5070c0"},
            "font": {"size": 9, "color": "#8090b0", "strokeWidth": 0},
            "smooth": {"type": "curvedCW", "roundness": 0.1},
        })

    vis_src = _vis_js(out_dir)

    # Legend
    legend = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0">'
        f'<span style="width:11px;height:11px;border-radius:50%;background:{c["bg"]};flex-shrink:0"></span>'
        f'<span>{t}</span></div>'
        for t, c in TYPE_COLORS.items()
    ) + (
        f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0">'
        f'<span style="width:11px;height:11px;background:#1a2540;border:2px solid #3d5af1;flex-shrink:0"></span>'
        f'<span>chapter</span></div>'
    )

    # Entity detail panel data (for JS)
    entity_info = {
        e["name_key"]: {
            "name": e["name"], "type": e["type"],
            "description": e["description"],
            "pages": sorted({m["page"] for m in mention_map.get(e["name_key"], [])}),
        }
        for e in ents
    }

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<script src="{vis_src}"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;background:#070b18;color:#ccd;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow:hidden}}
#net{{position:absolute;top:0;left:0;right:360px;bottom:0}}
#sidebar{{position:absolute;top:0;right:0;width:360px;bottom:0;background:#0c1128;
          border-left:1px solid #1e2a4a;display:flex;flex-direction:column;overflow:hidden}}
#hud{{padding:14px 16px;border-bottom:1px solid #1e2a4a}}
#hud h2{{font-size:14px;color:#fff;margin-bottom:6px;letter-spacing:0.3px}}
#stats{{color:#667;font-size:11px;margin-bottom:10px}}
#q{{width:100%;background:#111827;border:1px solid #2a3560;color:#dde;
    border-radius:6px;padding:7px 11px;font-size:12px;outline:none}}
#q:focus{{border-color:#3d5af1}}
#type-filters{{padding:10px 14px;border-bottom:1px solid #1e2a4a;display:flex;flex-wrap:wrap;gap:5px}}
.filter-btn{{padding:3px 8px;border-radius:12px;border:1px solid #2a3560;background:transparent;
             color:#889;font-size:10px;cursor:pointer;transition:all 0.15s}}
.filter-btn.active{{color:#fff;border-color:currentColor}}
#detail{{flex:1;overflow-y:auto;padding:16px}}
#detail h3{{font-size:15px;color:#fff;margin-bottom:4px}}
#detail .type-badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;
                     margin-bottom:10px;color:#fff}}
#detail .desc{{font-size:12px;color:#aab;line-height:1.6;margin-bottom:12px}}
#detail .section{{margin-bottom:12px}}
#detail .section-title{{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#556;margin-bottom:4px}}
#detail .tag{{display:inline-block;background:#111827;border:1px solid #2a3560;color:#8af;
              padding:2px 7px;border-radius:4px;font-size:10px;margin:2px}}
#detail .relation-row{{padding:5px 0;border-bottom:1px solid #111827;font-size:11px}}
#detail .relation-type{{color:#5566aa;font-size:10px;margin-right:4px}}
#placeholder{{color:#334;text-align:center;padding:40px 20px;font-size:13px;line-height:1.8}}
</style></head><body>
<div id="net"></div>
<div id="sidebar">
  <div id="hud">
    <h2>🧠 {title}</h2>
    <div id="stats">{len(nodes_data)} Entitäten · {len(edges_data)} Verbindungen</div>
    <input id="q" placeholder="Entity suchen (Enter)…">
  </div>
  <div id="type-filters">
    {''.join(f'<button class="filter-btn active" data-type="{t}" style="color:{c["bg"]};border-color:{c["bg"]}">{t}</button>' for t, c in TYPE_COLORS.items())}
    <button class="filter-btn active" data-type="chapter" style="color:#3d5af1;border-color:#3d5af1">chapter</button>
  </div>
  <div id="detail"><div id="placeholder">← Klicke auf einen Knoten<br>um Details zu sehen</div></div>
</div>

<script>
const ALL_NODES = {json.dumps(nodes_data, ensure_ascii=False)};
const ALL_EDGES = {json.dumps(edges_data, ensure_ascii=False)};
const ENTITY_INFO = {json.dumps(entity_info, ensure_ascii=False)};
const TYPE_COLORS = {json.dumps({t: c["bg"] for t, c in TYPE_COLORS.items()}, ensure_ascii=False)};

const nodes = new vis.DataSet(ALL_NODES);
const edges = new vis.DataSet(ALL_EDGES);

const options = {{
  nodes: {{
    shape: "dot",
    scaling: {{min:10, max:55, label:{{min:10,max:20,drawThreshold:6}}}},
    borderWidth: 2, borderWidthSelected: 4,
  }},
  edges: {{
    width: 1.5, selectionWidth: 3,
    color: {{inherit: false}},
    font: {{size:9, color:"#8090b0", strokeWidth:0, vadjust:-5}},
  }},
  physics: {{
    solver: "forceAtlas2Based",
    stabilization: {{iterations:400, updateInterval:20}},
    forceAtlas2Based: {{
      gravitationalConstant:-70, springLength:150,
      springConstant:0.06, damping:0.92, centralGravity:0.003,
    }},
  }},
  interaction: {{
    hover:true, tooltipDelay:50,
    navigationButtons:true,
    keyboard:{{enabled:true, bindToWindow:false}},
    multiselect:false,
  }},
}};

const net = new vis.Network(document.getElementById("net"), {{nodes, edges}}, options);

net.on("stabilizationIterationsDone", () => {{
  net.setOptions({{physics:{{enabled:false}}}});
}});

// ── Click → highlight neighbours + detail panel
let lastSelected = null;
net.on("click", params => {{
  const nid = params.nodes[0];
  if (!nid) {{ resetHighlight(); return; }}
  lastSelected = nid;
  highlightNeighbours(nid);
  showDetail(nid);
}});

function highlightNeighbours(nid) {{
  const connected = new Set(net.getConnectedNodes(nid));
  connected.add(nid);
  const allIds = nodes.getIds();
  nodes.update(allIds.map(id => ({{
    id,
    opacity: connected.has(id) ? 1 : 0.12,
  }})));
  const allEdgeIds = edges.getIds();
  const connEdges = new Set(net.getConnectedEdges(nid));
  edges.update(allEdgeIds.map(id => ({{
    id,
    color: connEdges.has(id)
      ? {{color:"#5070d0", opacity:1}}
      : {{color:"#1a2040", opacity:0.15}},
    width: connEdges.has(id) ? 2.5 : 0.8,
  }})));
}}

function resetHighlight() {{
  nodes.update(nodes.getIds().map(id => ({{id, opacity:1}})));
  edges.update(edges.getIds().map(id => ({{id, color:undefined, width:undefined}})));
  document.getElementById("detail").innerHTML = '<div id="placeholder">← Klicke auf einen Knoten<br>um Details zu sehen</div>';
  lastSelected = null;
}}

// ── Detail panel
function showDetail(nid) {{
  const info = ENTITY_INFO[nid];
  const nodeData = nodes.get(nid);
  const bgColor = TYPE_COLORS[nodeData?.group] || "#546e7a";

  // Neighbour relations
  const connEdges = net.getConnectedEdges(nid);
  const relRows = connEdges.slice(0, 15).map(eid => {{
    const e = edges.get(eid);
    if (!e) return "";
    const isOut = e.from === nid;
    const other = isOut ? e.to : e.from;
    const otherNode = nodes.get(other);
    const arrow = isOut ? "→" : "←";
    return `<div class="relation-row">
      <span class="relation-type">${{e.label || ""}}</span>
      ${{arrow}} <b>${{otherNode?.label || other}}</b>
      ${{e.title ? `<br><span style="color:#667;font-size:10px">${{e.title.replace(/<[^>]+>/g,"")}}</span>` : ""}}
    </div>`;
  }}).join("");

  const pagesHtml = info?.pages?.length
    ? info.pages.map(p => `<span class="tag">p.${p}</span>`).join("")
    : '<span style="color:#445">—</span>';

  document.getElementById("detail").innerHTML = `
    <h3>${{info?.name || nid}}</h3>
    <span class="type-badge" style="background:${{bgColor}}">${{info?.type || nodeData?.group || ""}}</span>
    <p class="desc">${{info?.description || "<em style='color:#445'>Keine Beschreibung</em>"}}</p>
    <div class="section">
      <div class="section-title">Seiten</div>
      ${{pagesHtml}}
    </div>
    <div class="section">
      <div class="section-title">Verbindungen (${{connEdges.length}})</div>
      ${{relRows || '<span style="color:#445">Keine</span>'}}
    </div>
  `;
}}

// ── Search
document.getElementById("q").addEventListener("keydown", e => {{
  if (e.key !== "Enter") return;
  const q = e.target.value.toLowerCase().trim();
  if (!q) {{ resetHighlight(); return; }}
  const hit = nodes.get().find(n =>
    (n.label||"").toLowerCase().includes(q) || (n.id||"").includes(q)
  );
  if (hit) {{
    net.selectNodes([hit.id]);
    net.focus(hit.id, {{scale:1.8, animation:{{duration:500}}}});
    highlightNeighbours(hit.id);
    showDetail(hit.id);
  }}
}});

// ── Type filter buttons
document.querySelectorAll(".filter-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    btn.classList.toggle("active");
    applyFilters();
  }});
}});

function applyFilters() {{
  const active = new Set(
    [...document.querySelectorAll(".filter-btn.active")].map(b => b.dataset.type)
  );
  const visible = ALL_NODES.filter(n => active.has(n.group || "concept")).map(n => n.id);
  const visSet = new Set(visible);
  nodes.update(ALL_NODES.map(n => ({{id:n.id, hidden: !visSet.has(n.id)}})));
}}

// ── Background click = reset
net.on("click", params => {{
  if (!params.nodes.length && !params.edges.length) resetHighlight();
}});

// ── Double-click → zoom to node
net.on("doubleClick", params => {{
  if (params.nodes.length) {{
    net.focus(params.nodes[0], {{scale:2.5, animation:true}});
  }}
}});
</script></body></html>"""

    out = out_dir / "knowledge_graph_v2.html"
    out.write_text(html, encoding="utf-8")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# OKF wiki
# ─────────────────────────────────────────────────────────────────────────────

def export_okf(conn: sqlite3.Connection, doc_title: str, summary: str):
    okf_dir = Path("/Users/mango/BlackSwanX/shared/rag/okf")
    slug = re.sub(r"[^a-z0-9]+", "-", doc_title.lower()).strip("-")
    doc_file = okf_dir / "docs" / f"{slug}-v2.md"
    doc_file.parent.mkdir(parents=True, exist_ok=True)

    ents = conn.execute(
        "SELECT name, type, description, importance FROM entities ORDER BY importance DESC, type, name"
    ).fetchall()
    rels = conn.execute("SELECT source_key,target_key,type FROM relations").fetchall()
    chaps = conn.execute("SELECT title,start_page,end_page FROM chapters ORDER BY start_page").fetchall()

    by_type: dict[str, list] = defaultdict(list)
    for e in ents:
        by_type[(e["type"] or "concept")].append(e)

    lines = [
        "---",
        f"title: {doc_title}",
        "type: Document",
        "version: v2-hierarchical",
        "---", "",
        f"# {doc_title}", "",
        "## Summary",
        summary or "_(no summary)_", "",
        f"**Entities:** {len(ents)} · **Relations:** {len(rels)} · **Chapters:** {len(chaps)}", "",
        "## Document Structure",
    ]
    for ch in chaps:
        lines.append(f"- **{ch['title']}** (pp. {ch['start_page']}–{ch['end_page']})")
    lines += [""]

    for etype in sorted(by_type):
        lines.append(f"## {etype.capitalize()}s ({len(by_type[etype])})")
        for e in by_type[etype]:
            stars = "★" * min(e["importance"], 3)
            desc = f" — {e['description']}" if e["description"] else ""
            lines.append(f"- **{e['name']}** {stars}{desc}")
        lines.append("")

    doc_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OKF] {doc_file}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n=== LEGATUM Graph v2 (Hierarchical + phi4) ===", flush=True)
    print(f"PDF:   {PDF_PATH}", flush=True)
    print(f"Model: {EXTRACT_MODEL}", flush=True)
    print(f"Out:   {OUT_DIR}\n", flush=True)

    pages = extract_pages(PDF_PATH)
    doc_title = Path(PDF_PATH).stem
    conn = init_db()
    print(f"[DB]   {DB_PATH}", flush=True)

    # Detect chapter structure
    print("[chapters] detecting document structure…", flush=True)
    raw_chaps = detect_chapters(pages)
    print(f"  found {len(raw_chaps)} chapters/sections", flush=True)

    # Map pages to chapters
    page_chapter: dict[int, str] = {}
    for i, ch in enumerate(raw_chaps):
        pg = ch.get("page", 0)
        next_pg = raw_chaps[i + 1]["page"] if i + 1 < len(raw_chaps) else len(pages) + 1
        num = ch.get("number", "")
        chap_title = f"{num} {ch.get('title', '')}".strip()
        chap_key = key(chap_title)
        upsert_chapter(conn, chap_title, pg, next_pg - 1)
        for p in range(pg, next_pg):
            page_chapter[p] = chap_key

    conn.commit()

    # Windowed harvest with chapter context
    win_list = list(windows(pages, WINDOW, OVERLAP))
    print(f"[harvest] {len(win_list)} windows (phi4:14b)", flush=True)

    all_summaries: list[str] = []

    for i, win in enumerate(win_list, 1):
        page_nums = [p for p, _ in win]
        ch_key = page_chapter.get(page_nums[0], "")
        ch_row = conn.execute("SELECT title FROM chapters WHERE chapter_key=?", (ch_key,)).fetchone()
        ch_label = ch_row["title"] if ch_row else ""

        print(f"  [{i:02d}/{len(win_list)}] pp={page_nums}"
              f"{f' ch={ch_label[:30]}' if ch_label else ''} … ", end="", flush=True)

        result = harvest_window(win, page_nums, chapter=ch_label)
        n_e, n_r = len(result["entities"]), len(result["relations"])
        print(f"{n_e} ents, {n_r} rels", flush=True)

        for e in result["entities"]:
            name = (e.get("name") or "").strip()
            if not name:
                continue
            imp = int(e.get("importance", 1))
            upsert_entity(conn, name, e.get("type", ""), e.get("description", ""), imp)
            for pg in page_nums:
                # Grab a tiny context snippet
                page_text = next((t for p, t in win if p == pg), "")
                idx = page_text.lower().find(name.lower())
                ctx = page_text[max(0, idx - 40): idx + 80].strip() if idx >= 0 else ""
                add_mention(conn, name, pg, ch_label, ctx)
                if ch_key:
                    link_chapter_entity(conn, ch_key, name)

        for r in result["relations"]:
            src, tgt = (r.get("source") or "").strip(), (r.get("target") or "").strip()
            if src and tgt:
                upsert_relation(conn, src, tgt, r.get("type", ""),
                                r.get("description", ""), float(r.get("confidence", 1.0)))
                upsert_entity(conn, src, "", "", 1)
                upsert_entity(conn, tgt, "", "", 1)

        if result.get("summary"):
            all_summaries.append(result["summary"])

    conn.commit()

    ent_count  = conn.execute("SELECT count(*) FROM entities").fetchone()[0]
    rel_count  = conn.execute("SELECT count(*) FROM relations").fetchone()[0]
    chap_count = conn.execute("SELECT count(*) FROM chapters").fetchone()[0]
    print(f"\n[graph] {ent_count} entities · {rel_count} relations · {chap_count} chapters",
          flush=True)

    # Document summary
    print("[summary] condensing…", flush=True)
    doc_summary = condense(all_summaries)
    conn.execute(
        "INSERT OR REPLACE INTO doc_summary(id,title,summary,pages) VALUES(1,?,?,?)",
        (doc_title, doc_summary, len(pages)),
    )
    conn.commit()

    # Export
    print("[vis] exporting knowledge_graph_v2.html…", flush=True)
    graph_html = export_vis(conn, OUT_DIR, title="BIM-Leitfaden 2.0 — Knowledge Graph v2")
    print(f"[vis] → {graph_html}", flush=True)

    export_okf(conn, doc_title, doc_summary)

    conn.close()

    print(f"\n=== DONE ===")
    print(f"Graph:  {graph_html}")
    print(f"DB:     {DB_PATH}")
    print(f"\nOpen:  open {graph_html}")


if __name__ == "__main__":
    main()
