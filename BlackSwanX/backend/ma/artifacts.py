"""M&A Artifacts — HTML report / presentation builder."""
from datetime import datetime


REPORT_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: 'Inter', sans-serif; background: #f8f9fc; color: #1a1d2e; padding: 40px; }
  .cover { text-align:center; padding: 60px 0 40px; border-bottom: 2px solid #e8eaf0; margin-bottom: 40px; }
  .cover h1 { font-size: 32px; font-weight: 700; background: linear-gradient(135deg,#6366f1,#8b5cf6);
              -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom: 12px; }
  .cover .subtitle { font-size: 15px; color: #6b7280; }
  .cover .meta { margin-top: 16px; font-size: 12px; color: #9ca3af; }
  .section { background: white; border: 1px solid #e8eaf0; border-radius: 16px;
             padding: 28px 32px; margin-bottom: 24px; }
  .section h2 { font-size: 18px; font-weight: 600; color: #1a1d2e; margin-bottom: 16px;
                padding-bottom: 10px; border-bottom: 1px solid #f0f0f5; }
  .fact-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .fact-table th { background: #f8f9fc; padding: 10px 12px; text-align: left; font-weight: 600;
                   font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: #6b7280;
                   border-bottom: 1px solid #e8eaf0; }
  .fact-table td { padding: 10px 12px; border-bottom: 1px solid #f5f5f8; vertical-align: top; }
  .fact-table tr:last-child td { border-bottom: none; }
  .badge { display:inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .badge-valuation { background:#eef2ff; color:#6366f1; }
  .badge-risk { background:#fff1f2; color:#ef4444; }
  .badge-revenue { background:#e6faf0; color:#10b981; }
  .badge-legal { background:#fff7ed; color:#f59e0b; }
  .badge-general { background:#f5f5f8; color:#6b7280; }
  .chunk-box { background:#f8f9fc; border-left: 3px solid #6366f1; padding: 10px 14px;
               border-radius: 0 8px 8px 0; margin-bottom: 8px; font-size: 13px; line-height: 1.6; }
  .chunk-meta { font-size: 11px; color:#9ca3af; margin-top: 4px; }
  .annotation-item { padding: 10px 14px; background: #fefce8; border: 1px solid #fef08a;
                     border-radius: 8px; margin-bottom: 8px; }
  .annotation-tag { display:inline-block; padding: 1px 6px; background:#fef9c3; color:#a16207;
                    border-radius: 4px; font-size: 10px; font-weight: 600; margin-bottom: 4px; }
  .conf-bar { display:inline-block; height:6px; background:#6366f1; border-radius:3px; vertical-align:middle; }
  @media print { body { padding:20px; } .section { break-inside: avoid; } }
</style>
"""


def build_report_html(
    title: str,
    documents: list[dict],
    facts: list[dict],
    annotations: list[dict],
    top_chunks: list[dict],
    metadata: dict | None = None,
) -> str:
    now = datetime.now().strftime("%B %d, %Y")
    meta = metadata or {}

    # Cover
    html = f"""<!DOCTYPE html><html lang="en"><head>
    <meta charset="UTF-8"><title>{title}</title>{REPORT_CSS}</head><body>
    <div class="cover">
      <h1>{title}</h1>
      <div class="subtitle">{meta.get('subtitle', 'M&A Intelligence Report')}</div>
      <div class="meta">Generated {now} &nbsp;|&nbsp; {len(documents)} document(s) &nbsp;|&nbsp;
                        {len(facts)} extracted facts &nbsp;|&nbsp; {len(annotations)} annotations</div>
    </div>"""

    # Document inventory
    if documents:
        html += """<div class="section"><h2>📁 Document Inventory</h2>
        <table class="fact-table"><thead><tr>
          <th>#</th><th>Filename</th><th>Type</th><th>Pages</th><th>Chunks</th><th>Uploaded</th>
        </tr></thead><tbody>"""
        for i, d in enumerate(documents, 1):
            html += f"""<tr>
              <td>{i}</td>
              <td style="font-weight:500">{d.get('filename','')}</td>
              <td>{d.get('file_type','').upper()}</td>
              <td>{d.get('page_count',1)}</td>
              <td>{d.get('chunk_count',0)}</td>
              <td style="color:#9ca3af">{(d.get('upload_date') or '')[:16]}</td>
            </tr>"""
        html += "</tbody></table></div>"

    # Extracted facts
    if facts:
        html += """<div class="section"><h2>🔍 Extracted Facts</h2>
        <table class="fact-table"><thead><tr>
          <th>Type</th><th>Subject</th><th>Value</th><th>Source</th><th>Confidence</th>
        </tr></thead><tbody>"""
        for f in facts[:60]:
            badge_type = f.get("fact_type", "general").lower()
            badge_class = f"badge-{badge_type}" if badge_type in ("valuation","risk","revenue","legal") else "badge-general"
            conf = float(f.get("confidence", 0.8))
            bar_w = int(conf * 60)
            html += f"""<tr>
              <td><span class="badge {badge_class}">{f.get('fact_type','')}</span></td>
              <td style="font-weight:500">{f.get('subject','') or '—'}</td>
              <td>{f.get('value','')}</td>
              <td style="color:#9ca3af;font-size:11px">{f.get('filename','')}</td>
              <td><span class="conf-bar" style="width:{bar_w}px"></span>
                  <span style="margin-left:6px;font-size:11px">{conf*100:.0f}%</span></td>
            </tr>"""
        html += "</tbody></table></div>"

    # Annotations
    if annotations:
        html += """<div class="section"><h2>📌 Analyst Annotations</h2>"""
        for a in annotations[:20]:
            html += f"""<div class="annotation-item">
              <div class="annotation-tag">{a.get('tag','general').upper()}</div>
              <div style="font-size:13px;margin-top:2px">{a.get('note','')}</div>
              <div class="chunk-meta">{a.get('filename','')} — {(a.get('created_at') or '')[:16]}</div>
            </div>"""
        html += "</div>"

    # Key passages
    if top_chunks:
        html += """<div class="section"><h2>📄 Key Passages</h2>"""
        for c in top_chunks[:10]:
            html += f"""<div class="chunk-box">
              {c.get('text','')[:400]}{'…' if len(c.get('text','')) > 400 else ''}
              <div class="chunk-meta">{c.get('filename','')} · Page {c.get('page',1)} · Score {c.get('score',0):.2f}</div>
            </div>"""
        html += "</div>"

    html += "</body></html>"
    return html


def build_deck_html(title: str, slides: list[dict]) -> str:
    """Build a simple slide-deck HTML (one slide per fact_type group)."""
    now = datetime.now().strftime("%B %d, %Y")
    slide_css = """
    <style>
      body { font-family: 'Inter', sans-serif; margin:0; background:#0f172a; color:white; }
      .slide { min-height: 100vh; display:flex; flex-direction:column; justify-content:center;
               padding: 60px 80px; border-bottom: 1px solid #1e293b; page-break-after: always; }
      .slide-num { font-size:11px; color:#475569; margin-bottom:20px; }
      .slide h2 { font-size:36px; font-weight:700; margin-bottom:24px;
                  background: linear-gradient(135deg,#6366f1,#8b5cf6);
                  -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
      .slide ul { list-style:none; }
      .slide ul li { font-size:18px; color:#e2e8f0; padding:10px 0; border-bottom:1px solid #1e293b; }
      .slide ul li::before { content:"→ "; color:#6366f1; font-weight:700; }
      .slide .date { font-size:12px; color:#475569; margin-top:24px; }
      @media print { .slide { page-break-after: always; } }
    </style>"""

    html = f"""<!DOCTYPE html><html lang="en"><head>
    <meta charset="UTF-8"><title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    {slide_css}</head><body>"""

    # Title slide
    html += f"""<div class="slide">
      <div class="slide-num">01 / {len(slides)+1}</div>
      <h2>{title}</h2>
      <p style="color:#94a3b8;font-size:18px">M&A Intelligence Platform — BlackSwanX</p>
      <div class="date">{now}</div>
    </div>"""

    for i, slide in enumerate(slides, 2):
        items = slide.get("items", [])
        html += f"""<div class="slide">
          <div class="slide-num">{i:02d} / {len(slides)+1}</div>
          <h2>{slide.get('title', '')}</h2>
          <ul>{''.join(f"<li>{item}</li>" for item in items[:8])}</ul>
        </div>"""

    html += "</body></html>"
    return html
