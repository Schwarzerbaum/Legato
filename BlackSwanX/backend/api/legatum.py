"""LEGATUM API routes — Construction AI modules."""
import sys as _sys
from pathlib import Path as _Path
_backend_dir = str(_Path(__file__).parent.parent)
if _backend_dir not in _sys.path:
    _sys.path.insert(0, _backend_dir)

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import json
import shutil
import tempfile
from pathlib import Path

UPLOAD_DIR = Path(tempfile.gettempdir()) / "legatum_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────────

class NachtragRequest(BaseModel):
    nachtrag_id: str = "N-001"
    claim_value_eur: float = 48500.0
    nachtrag_text: str
    original_lv_text: str = ""
    correspondence_text: str = ""
    contract_type: str = "VOB/B"
    is_pauschalvertrag: bool = False

class VendorEventRequest(BaseModel):
    vendor_name: str
    project_id: str
    project_name: str
    pattern_id: str = "baugrundrisiko_serial"
    claim_value_eur: float = 0.0
    evidence_text: str = ""

class ProcurementCheckRequest(BaseModel):
    vendor_name: str
    contract_value_eur: float

class ScheduleRegisterRequest(BaseModel):
    project_id: str
    tasks: list[dict]

class CascadeRequest(BaseModel):
    project_id: str
    trigger_node_id: str
    delay_days: int
    initial_strength: float = 1.0

class MeshRequest(BaseModel):
    documents: list[dict]

class KGBuildRequest(BaseModel):
    doc_id: int
    filename: str
    text: str

class KGQueryRequest(BaseModel):
    query: str
    top_k: int = 10

class AdversarialRequest(BaseModel):
    clause_text: str
    context: str = ""
    mode: str = "nachtrag"  # nachtrag | mangel | vertragsstrafe

class LegalTwinRequest(BaseModel):
    documents: list[dict]
    project_id: str = "demo"

class TribunalRequest(BaseModel):
    entity_a: str
    entity_b: str
    context_a: str = ""
    context_b: str = ""

class PheromoneRequest(BaseModel):
    documents: list[dict]  # [{doc_id, filename, text}]


# ── Dashboard UI ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def legatum_dashboard():
    return """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LEGATUM — Construction AI</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #f7f8fc;
    --surface: #ffffff;
    --border: #e2e5ef;
    --text: #1a1f36;
    --text-muted: #6b7394;
    --accent: #f59e0b;
    --accent-dark: #d97706;
    --accent-soft: #fef3c7;
    --blue: #3b5bdb;
    --blue-soft: #e8edff;
    --red: #e53e3e;
    --red-soft: #fff5f5;
    --green: #16a34a;
    --green-soft: #f0fdf4;
    --navy: #1e2a4a;
  }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }

  /* HEADER */
  .header { background: var(--navy); padding: 0 40px;
            border-bottom: 3px solid var(--accent); display: flex;
            align-items: center; justify-content: space-between; height: 64px; }
  .header-left { display: flex; align-items: center; gap: 16px; }
  .logo { font-size: 20px; font-weight: 800; color: #fff; letter-spacing: -0.5px; }
  .logo span { color: var(--accent); }
  .tagline { font-size: 12px; color: #8896b8; border-left: 1px solid #3a4a6b;
             padding-left: 16px; }
  .badge-vob { background: var(--accent); color: var(--navy); font-size: 11px;
               font-weight: 700; padding: 3px 10px; border-radius: 20px; }

  /* NAV */
  .nav { background: var(--surface); border-bottom: 1px solid var(--border);
         padding: 0 40px; display: flex; gap: 4px; overflow-x: auto; }
  .nav-btn { padding: 14px 20px; border: none; background: none; cursor: pointer;
             font-size: 13px; font-weight: 500; color: var(--text-muted);
             border-bottom: 3px solid transparent; transition: all 0.15s;
             white-space: nowrap; }
  .nav-btn:hover { color: var(--text); background: var(--bg); }
  .nav-btn.active { color: var(--navy); border-bottom-color: var(--accent);
                    font-weight: 700; }

  /* LAYOUT */
  .container { max-width: 1140px; margin: 0 auto; padding: 28px 24px; }
  .panel { display: none; }
  .panel.active { display: block; }

  /* STATS BAR */
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }
  .stat { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
          padding: 16px 20px; border-top: 3px solid var(--accent); }
  .stat .val { font-size: 26px; font-weight: 800; color: var(--navy); }
  .stat .lbl { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

  /* CARD */
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
          padding: 24px; margin-bottom: 18px; }
  .card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
  .card-icon { width: 32px; height: 32px; border-radius: 8px; background: var(--accent-soft);
               display: flex; align-items: center; justify-content: center; font-size: 16px; }
  .card h2 { font-size: 16px; font-weight: 700; color: var(--navy); }
  .card .desc { font-size: 13px; color: var(--text-muted); margin-bottom: 18px; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .three-col { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
  @media (max-width: 700px) { .two-col, .three-col, .stats { grid-template-columns: 1fr; } }

  /* FORM */
  label { display: block; font-size: 12px; font-weight: 600; color: var(--text-muted);
          text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; margin-top: 14px; }
  input, textarea, select {
    width: 100%; padding: 10px 14px;
    background: var(--bg); border: 1.5px solid var(--border);
    border-radius: 8px; color: var(--text); font-size: 14px; font-family: inherit;
    transition: border-color 0.15s;
  }
  textarea { resize: vertical; min-height: 90px; }
  input:focus, textarea:focus, select:focus {
    outline: none; border-color: var(--accent); background: #fff;
  }

  /* BUTTON */
  .btn { display: inline-flex; align-items: center; gap: 8px;
         padding: 10px 22px; background: var(--navy); color: #fff;
         border: none; border-radius: 8px; font-size: 14px; font-weight: 600;
         cursor: pointer; margin-top: 16px; transition: background 0.15s; }
  .btn:hover { background: #2d3d6e; }
  .btn-accent { background: var(--accent); color: var(--navy); }
  .btn-accent:hover { background: var(--accent-dark); }
  .btn-ghost { background: var(--bg); color: var(--navy); border: 1.5px solid var(--border); }
  .btn-ghost:hover { background: var(--border); }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* RESULT */
  .result { background: #0f1923; border: 1px solid #2d3748; border-radius: 10px;
            padding: 18px; margin-top: 16px; font-family: 'Courier New', monospace;
            font-size: 12.5px; white-space: pre-wrap; max-height: 420px;
            overflow-y: auto; color: #68d391; display: none; line-height: 1.6; }
  .result.error { color: #fc8181; }

  /* VERDICT CARDS */
  .verdict { display: grid; grid-template-columns: repeat(3,1fr); gap: 12px;
             margin-top: 16px; display: none; }
  .verdict-item { border-radius: 10px; padding: 16px; text-align: center; }
  .verdict-item .v-val { font-size: 28px; font-weight: 800; }
  .verdict-item .v-lbl { font-size: 12px; margin-top: 4px; }
  .verdict-approve { background: var(--green-soft); border: 1px solid #bbf7d0; }
  .verdict-approve .v-val { color: var(--green); }
  .verdict-risk { background: var(--accent-soft); border: 1px solid #fde68a; }
  .verdict-risk .v-val { color: var(--accent-dark); }
  .verdict-reject { background: var(--red-soft); border: 1px solid #fed7d7; }
  .verdict-reject .v-val { color: var(--red); }

  /* BADGES */
  .tag { display: inline-block; padding: 3px 10px; border-radius: 20px;
         font-size: 11px; font-weight: 700; margin-right: 4px; margin-top: 4px; }
  .tag-amber { background: var(--accent-soft); color: var(--accent-dark); }
  .tag-blue { background: var(--blue-soft); color: var(--blue); }
  .tag-green { background: var(--green-soft); color: var(--green); }
  .tag-red { background: var(--red-soft); color: var(--red); }
  .tag-navy { background: #e8edff; color: var(--navy); }

  /* KG GRAPH */
  #kg-canvas { width: 100%; height: 420px; border: 1px solid var(--border);
               border-radius: 10px; background: #0f1923; margin-top: 16px; }
  .kg-legend { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 10px; }
  .kg-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block;
            margin-right: 5px; }

  /* ADVERSARIAL */
  .versus { display: grid; grid-template-columns: 1fr 40px 1fr; gap: 0;
            margin-top: 16px; align-items: start; }
  .agent-box { border-radius: 10px; padding: 16px; }
  .agent-an { background: #fff8e1; border: 1.5px solid #fde68a; }
  .agent-ag { background: #e8edff; border: 1.5px solid #c7d2fe; }
  .agent-title { font-size: 13px; font-weight: 700; margin-bottom: 8px; }
  .agent-an .agent-title { color: #92400e; }
  .agent-ag .agent-title { color: #312e81; }
  .versus-mid { display: flex; align-items: center; justify-content: center;
                font-size: 22px; font-weight: 900; color: var(--text-muted);
                padding-top: 40px; }

  .loading-dots::after { content: ''; animation: dots 1.2s infinite; }
  @keyframes dots {
    0%   { content: '.'; }
    33%  { content: '..'; }
    66%  { content: '...'; }
    100% { content: ''; }
  }
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div class="logo">Mate<span>Scale</span></div>
    <div class="tagline">Construction AI · VOB/B · HOAI · GAEB · CPM</div>
  </div>
  <div class="badge-vob">PROTOTYPE v0.1</div>
</div>

<div class="nav">
  <button class="nav-btn active" onclick="showPanel('nachtrag', this)">📋 Nachtragsprüfung</button>
  <button class="nav-btn" onclick="showPanel('adversarial', this)">⚔️ Adversarial Agents</button>
  <button class="nav-btn" onclick="showPanel('vendor', this)">🏗️ Vendor Risk Index</button>
  <button class="nav-btn" onclick="showPanel('cascade', this)">⏱️ Schedule Cascade</button>
  <button class="nav-btn" onclick="showPanel('mesh', this)">🕸️ Contractual Mesh</button>
  <button class="nav-btn" onclick="showPanel('kg', this)">🔍 KG Search</button>
  <button class="nav-btn" onclick="showPanel('legaltwin', this)">🧠 Legal-Twin KG</button>
</div>

<div class="container">

<!-- ═══════════════ NACHTRAG ═══════════════ -->
<div id="panel-nachtrag" class="panel active">
  <div class="stats">
    <div class="stat"><div class="val">6</div><div class="lbl">VOB/B Procedural Rules</div></div>
    <div class="stat"><div class="val">0ms</div><div class="lbl" id="n-timing">Pre-screen Time</div></div>
    <div class="stat"><div class="val">VOB/B</div><div class="lbl">Legal Framework</div></div>
    <div class="stat"><div class="val">§2,§4,§6</div><div class="lbl">Core Paragraphs</div></div>
  </div>

  <div class="card">
    <div class="card-header"><div class="card-icon">📋</div><h2>Nachtragsprüfung Engine</h2></div>
    <div class="desc">VOB/B-grounded pre-litigation risk assessment. Deterministic procedural checks + AI analysis. Outputs Financial Risk Exposure Score.</div>

    <div class="two-col">
      <div><label>Nachtrag ID</label><input type="text" id="n-id" value="N-007"></div>
      <div><label>Forderungsbetrag (EUR)</label><input type="number" id="n-value" value="48500"></div>
    </div>
    <label>Nachtrag Text</label>
    <textarea id="n-text" rows="5">Nachtrag Nr. 7: Fassadenmaterial

Aufgrund der schriftlichen Anordnung des Auftraggebers vom 15.03.2026 wurde das Fassadenmaterial von Putz (Position 05.02.001) auf Klinker geändert. Mehrkosten EUR 48.500,00 netto.

Grundlage: VOB/B §2 Abs. 5 (schriftliche Anordnung liegt vor). Aufmaß gemeinsam mit Bauleiter am 20.03.2026 aufgenommen.</textarea>

    <div class="two-col">
      <div>
        <label>Original LV (relevant sections)</label>
        <textarea id="n-lv" rows="3">Position 05.02.001: Außenwandputz, Kalkzementputz zweilagig
Einheitspreis: EUR 28,50/m² · Menge: 850 m² · Gesamt: EUR 24.225,00</textarea>
      </div>
      <div>
        <label>Schriftverkehr / Protokolle</label>
        <textarea id="n-corr" rows="3">Email AG vom 14.03.2026: 'Bitte ändern Sie das Fassadenmaterial auf Klinker. Beauftragung erfolgt hiermit schriftlich.'
Protokoll Baubesprechung 15.03.2026: Änderung besprochen und bestätigt.</textarea>
      </div>
    </div>
    <div class="two-col">
      <div><label>Vertragsart</label>
        <select id="n-contract"><option value="VOB/B">VOB/B</option><option value="BGB">BGB</option></select></div>
      <div><label>Pauschalvertrag?</label>
        <select id="n-pauschal"><option value="false">Nein (Einheitspreisvertrag)</option><option value="true">Ja (Pauschalvertrag)</option></select></div>
    </div>
    <button class="btn btn-accent" onclick="runNachtrag()">▶ Nachtrag prüfen</button>

    <div class="verdict" id="n-verdict">
      <div class="verdict-item verdict-approve">
        <div class="v-val" id="v-pct">—</div><div class="v-lbl">Likely Award %</div>
      </div>
      <div class="verdict-item verdict-risk">
        <div class="v-val" id="v-mid">—</div><div class="v-lbl">Expected EUR</div>
      </div>
      <div class="verdict-item verdict-reject">
        <div class="v-val" id="v-rec">—</div><div class="v-lbl">Recommendation</div>
      </div>
    </div>
    <div class="result" id="n-result"></div>
  </div>
</div>

<!-- ═══════════════ ADVERSARIAL ═══════════════ -->
<div id="panel-adversarial" class="panel">
  <div class="card">
    <div class="card-header"><div class="card-icon">⚔️</div><h2>Adversarial Clause Analysis</h2></div>
    <div class="desc">Two opposing AI agents simultaneously argue a contract clause — Auftragnehmer (AN) maximizes claim, Auftraggeber (AG) weaponizes documentation gaps. Dissonance = contested zones.</div>

    <label>Analysis Mode</label>
    <select id="adv-mode">
      <option value="nachtrag">Nachtrag Claim (VOB/B §2)</option>
      <option value="mangel">Mängelrüge (VOB/B §13)</option>
      <option value="vertragsstrafe">Vertragsstrafe (VOB/B §5)</option>
    </select>

    <label>Clause / Contract Text to Analyse</label>
    <textarea id="adv-text" rows="7">§ 8 Leistungsänderungen

Der Auftraggeber ist berechtigt, Änderungen des Leistungsumfangs anzuordnen. Der Auftragnehmer ist verpflichtet, die geänderten Leistungen auszuführen. Eine Vergütungsanpassung erfolgt nach VOB/B §2. Der Auftragnehmer hat Mehrkosten vor Ausführung anzumelden. Mündliche Anordnungen werden nachträglich schriftlich bestätigt.</textarea>

    <label>Additional Context (optional)</label>
    <textarea id="adv-ctx" rows="2" placeholder="e.g. Pauschalvertrag, specific project conditions, prior dispute history..."></textarea>

    <button class="btn btn-accent" onclick="runAdversarial()">⚔️ Run Adversarial Analysis</button>

    <div class="versus" id="adv-versus" style="display:none;">
      <div class="agent-box agent-an">
        <div class="agent-title">🔴 Auftragnehmer (AN)</div>
        <div id="adv-an-args" style="font-size:13px; line-height:1.6; color:#78350f;"></div>
        <div style="margin-top:10px; font-size:12px; color:#92400e;">
          <strong>Stärke:</strong> <span id="adv-an-strength">—</span>
        </div>
      </div>
      <div class="versus-mid">VS</div>
      <div class="agent-box agent-ag">
        <div class="agent-title">🔵 Auftraggeber (AG)</div>
        <div id="adv-ag-args" style="font-size:13px; line-height:1.6; color:#312e81;"></div>
        <div style="margin-top:10px; font-size:12px; color:#3730a3;">
          <strong>Stärke:</strong> <span id="adv-ag-strength">—</span>
        </div>
      </div>
    </div>
    <div class="result" id="adv-result"></div>
  </div>
</div>

<!-- ═══════════════ VENDOR ═══════════════ -->
<div id="panel-vendor" class="panel">
  <div class="card">
    <div class="card-header"><div class="card-icon">📝</div><h2>Record Behavioral Event</h2></div>
    <div class="desc">Each event strengthens the SM-2 pattern score. Strength ≥ 0.75 across 3+ projects = permanent institutional memory.</div>

    <label>Vendor Name</label><input type="text" id="v-name" value="Mustermann Tiefbau GmbH">
    <div class="two-col">
      <div><label>Projekt ID</label><input type="text" id="v-project-id" value="PRJ-2024-C"></div>
      <div><label>Projekt Name</label><input type="text" id="v-project-name" value="Logistikzentrum Berlin"></div>
    </div>
    <label>Verhaltensmuster</label>
    <select id="v-pattern">
      <option value="baugrundrisiko_serial">Serieller Baugrundrisiko-Kläger</option>
      <option value="claim_maximizer">Claim Maximierer</option>
      <option value="delay_claimer">Verzögerungs-Kläger</option>
      <option value="documentation_avoider">Dokumentationsmuffel</option>
      <option value="quality_risk">Qualitätsrisiko</option>
      <option value="reliable_contractor">Zuverlässiger Auftragnehmer ✅</option>
    </select>
    <div class="two-col">
      <div><label>Nachtragswert (EUR)</label><input type="number" id="v-claim" value="41000"></div>
      <div><label>SM-2 Qualität (1–5)</label><input type="number" id="v-quality" value="5" min="1" max="5"></div>
    </div>
    <label>Beweistext</label>
    <textarea id="v-evidence" rows="2">Nachtrag für kontaminiertes Erdreich — Altlastenverdacht nicht erkennbar beim Baugrundgutachten</textarea>
    <button class="btn" onclick="recordVendorEvent()">📝 Ereignis erfassen</button>
    <div class="result" id="v-event-result"></div>
  </div>

  <div class="card">
    <div class="card-header"><div class="card-icon">🔍</div><h2>Beschaffungsprüfung</h2></div>
    <div class="desc">Surfaces permanent behavioral patterns before contract signature. Outputs contingency recommendation in EUR.</div>
    <div class="two-col">
      <div><label>Vendor Name</label><input type="text" id="pc-name" value="Mustermann Tiefbau GmbH"></div>
      <div><label>Auftragswert (EUR)</label><input type="number" id="pc-value" value="850000"></div>
    </div>
    <button class="btn btn-accent" onclick="runProcurementCheck()">🔍 Beschaffungsprüfung starten</button>
    <div class="result" id="pc-result"></div>
  </div>
</div>

<!-- ═══════════════ CASCADE ═══════════════ -->
<div id="panel-cascade" class="panel">
  <div class="card">
    <div class="card-header"><div class="card-icon">⏱️</div><h2>Schedule-Aware Risk Cascade</h2></div>
    <div class="desc">CPM-integrated delay propagation. Signal decay is weighted by schedule dependency proximity, not just text similarity. Triggers VOB/B §6 Behinderungsanzeige alerts.</div>

    <button class="btn btn-ghost" onclick="loadDemoSchedule()" style="margin-bottom:4px;">
      📅 Demo-Terminplan laden (5 Gewerke)
    </button>
    <div class="result" id="sched-result"></div>

    <div class="three-col" style="margin-top:16px;">
      <div><label>Projekt ID</label><input type="text" id="c-project" value="PRJ-DEMO-2026"></div>
      <div><label>Trigger Node ID</label><input type="text" id="c-trigger" value="T001"></div>
      <div><label>Verzögerung (Tage)</label><input type="number" id="c-delay" value="14"></div>
    </div>
    <button class="btn btn-accent" onclick="runCascade()">⚡ Kaskade berechnen</button>
    <div class="result" id="c-result"></div>
  </div>
</div>

<!-- ═══════════════ MESH ═══════════════ -->
<div id="panel-mesh" class="panel">
  <div class="card">
    <div class="card-header"><div class="card-icon">🕸️</div><h2>Cross-Document Contractual Mesh</h2></div>
    <div class="desc">Deterministic legal graph built from GAEB Positionsnummern, VOB/B paragraph nodes, and document hierarchy. No text similarity — structural legal relationships only.</div>

    <label>Dokumente (JSON Array: doc_id, filename, text)</label>
    <textarea id="m-docs" rows="14">[
  {
    "doc_id": 1,
    "filename": "Hauptvertrag_Musteranlage.pdf",
    "text": "Werkvertrag nach VOB/B für die Errichtung der Musteranlage. Vergütung gem. VOB/B §2. Abnahme gem. VOB/B §12. Gewährleistung 4 Jahre gem. VOB/B §13 Abs. 4."
  },
  {
    "doc_id": 2,
    "filename": "Leistungsverzeichnis_Los1.gaeb",
    "text": "Leistungsverzeichnis Los 1 Rohbauarbeiten. Position 01.01.001: Aushub Baugrube 450m³ EUR 45,00/m³. Position 01.02.001: Betonage Fundament C25/30 85m³. Position 02.01.001: Mauerwerk KS 24cm 320m². Ausführung gem. DIN 18300 DIN 18331."
  },
  {
    "doc_id": 3,
    "filename": "Nachtrag_007_Fassade.pdf",
    "text": "Nachtrag Nr. 7 zu Position 05.02.001 Fassadenmaterial. Schriftliche Anordnung AG vom 15.03.2026 gem. VOB/B §2 Abs. 5. Position 05.02.001 Änderung von Putz auf Klinker. Mehrkosten EUR 48.500. Ausführung nach DIN 105."
  }
]</textarea>
    <button class="btn btn-accent" onclick="buildMesh()">🕸️ Mesh aufbauen</button>
    <div class="result" id="m-result"></div>
  </div>
</div>

<!-- ═══════════════ KNOWLEDGE GRAPH ═══════════════ -->
<div id="panel-kg" class="panel">
  <div class="card">
    <div class="card-header"><div class="card-icon">🧠</div><h2>Knowledge Graph — Build & Query</h2></div>
    <div class="desc">Entity extraction (15 types) + Spider-Web Densifier (3-pass Jaccard) + Personalized PageRank hybrid search. Temporal edges with valid_from/valid_until. Community detection via label-propagation.</div>

    <label>Document Text (paste any construction document)</label>
    <textarea id="kg-text" rows="8">Werkvertrag zwischen Mustermann Bau GmbH (Auftraggeber) und Schmidt Tiefbau GmbH (Auftragnehmer) für das Projekt Neubau Logistikzentrum Berlin-Tempelhof.

Auftragsvolumen: EUR 2,4 Millionen. Ausführungszeitraum: 01.04.2026 bis 30.11.2026. Vertragsgrundlage: VOB/B.

Leistung umfasst Erdarbeiten gem. DIN 18300, Betonarbeiten DIN 18331, Mauerwerk DIN 18330.
Bauleiter: Dipl.-Ing. Thomas Meier. Architekt: Planungsbüro Weber GmbH.

Vertragsstrafe: 0,2% pro Werktag, max. 5% der Auftragssumme gem. VOB/B §5.
Gewährleistung: 4 Jahre gem. VOB/B §13 Abs. 4.
Sicherheitseinbehalt: 5% bis zur Abnahme.</textarea>

    <div class="two-col">
      <div><label>Document ID</label><input type="number" id="kg-docid" value="100"></div>
      <div><label>Filename</label><input type="text" id="kg-filename" value="Werkvertrag_Logistikzentrum.pdf"></div>
    </div>
    <button class="btn" onclick="buildKG()" style="margin-right:8px;">🔨 Build KG</button>
    <button class="btn btn-ghost" onclick="getKGStats()">📊 Stats</button>

    <div class="result" id="kg-build-result"></div>
  </div>

  <div class="card">
    <div class="card-header"><div class="card-icon">🔍</div><h2>Hybrid Search (BM25 + PPR)</h2></div>
    <div class="desc">BM25 keyword recall fused with Personalized PageRank graph precision. Finds multi-hop connected entities missed by pure semantic search.</div>

    <label>Search Query</label>
    <input type="text" id="kg-query" value="Vertragsstrafe Verzögerung" placeholder="e.g. Vertragsstrafe, Bauleiter, DIN 18300...">
    <div class="two-col">
      <div><label>Top K Results</label><input type="number" id="kg-topk" value="10"></div>
      <div><label>BM25 Weight (0–1)</label><input type="number" id="kg-bm25w" value="0.4" step="0.1"></div>
    </div>
    <button class="btn btn-accent" onclick="searchKG()">🔍 Search Knowledge Graph</button>
    <div class="result" id="kg-search-result"></div>
  </div>
</div>

<!-- ═══════════════ LEGAL-TWIN KG ═══════════════ -->
<div id="panel-legaltwin" class="panel">
  <div class="card">
    <div class="card-header"><div class="card-icon">🧠</div><h2>Legal-Twin Knowledge Graph</h2></div>
    <div class="desc">
      Novel 3-dimensional KG: <strong>Hierarchy</strong> (GAEB deterministic tree) ·
      <strong>Time</strong> (temporal edges with valid_from/valid_until) ·
      <strong>Regulation</strong> (DIN/VOB/B auto-binding, no LLM needed).
      Three structural passes: inheritance → regulatory binding → shared risk interface.
    </div>

    <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:8px;">
      <button class="btn btn-accent" onclick="buildDemoLegalTwin()">⚡ Build Demo KG (4 docs)</button>
      <button class="btn btn-ghost" onclick="loadKGViz()">🔄 Refresh Graph</button>
    </div>
    <div style="font-size:12px; color:var(--text-muted); margin-bottom:8px;" id="lkg-stats">
      Click "Build Demo KG" to generate the graph
    </div>

    <!-- D3 Graph Canvas -->
    <div id="lkg-canvas" style="width:100%; height:500px; border:1px solid var(--border);
         border-radius:10px; background:#0f1923; position:relative;">
      <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
                  color:#4a5568; font-size:14px; text-align:center;">
        Build the KG to see the graph visualization
      </div>
    </div>

    <!-- Legend -->
    <div style="display:flex; gap:16px; flex-wrap:wrap; margin-top:12px; font-size:12px;">
      <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#3b5bdb;margin-right:5px;"></span>Document</span>
      <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#0d7377;margin-right:5px;"></span>Company</span>
      <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#f59e0b;margin-right:5px;"></span>GAEB Position</span>
      <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#dc2626;margin-right:5px;"></span>VOB/B §</span>
      <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#059669;margin-right:5px;"></span>DIN Standard</span>
      <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ea580c;margin-right:5px;"></span>Nachtrag</span>
      <span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#6366f1;margin-right:5px;"></span>Clause</span>
      <span style="color:var(--text-muted);">── solid = explicit &nbsp; - - dashed = inferred</span>
    </div>

    <div class="result" id="lkg-build-result"></div>
  </div>

  <!-- Tribunal Dedup -->
  <div class="card">
    <div class="card-header"><div class="card-icon">⚖️</div><h2>Tribunal Entity Deduplication</h2></div>
    <div class="desc">
      3-agent judicial loop: Prosecutor argues entities differ · Defense argues same entity ·
      Judge writes an auditable verdict with SHA-256 hash. Every merge decision is legally traceable.
    </div>
    <div class="two-col">
      <div>
        <label>Entity A</label>
        <input type="text" id="trib-a" value="Schmidt Tiefbau GmbH">
        <label>Context A</label>
        <textarea id="trib-ctx-a" rows="2">Auftragnehmer für Erdarbeiten, Baustelle Berlin, Projekt 2026</textarea>
      </div>
      <div>
        <label>Entity B</label>
        <input type="text" id="trib-b" value="Schmidt GmbH Tiefbau">
        <label>Context B</label>
        <textarea id="trib-ctx-b" rows="2">AN gem. Nachtrag Nr. 3, gleiche Baustelle, selber Bauleiter</textarea>
      </div>
    </div>
    <button class="btn btn-accent" onclick="runTribunal()">⚖️ Run Tribunal</button>
    <div class="result" id="tribunal-result"></div>
  </div>
</div>

</div><!-- /container -->

<script src="/d3.min.js"></script>
<script>
function showPanel(name, btn) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  btn.classList.add('active');
}

function showResult(id, data) {
  const el = document.getElementById(id);
  el.className = 'result';
  el.style.display = 'block';
  el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}
function showError(id, msg) {
  const el = document.getElementById(id);
  el.className = 'result error';
  el.style.display = 'block';
  el.textContent = '❌ ' + msg;
}
function loading(id, msg) {
  const el = document.getElementById(id);
  el.className = 'result';
  el.style.display = 'block';
  el.textContent = '⏳ ' + (msg || 'Loading...');
}

async function post(url, body) {
  const r = await fetch(url, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function runNachtrag() {
  loading('n-result', 'Prüfe Nachtrag (VOB/B Verfahrensregeln)...');
  document.getElementById('n-verdict').style.display = 'none';
  const t0 = Date.now();
  try {
    const data = await post('/api/legatum/nachtrag/pruefen', {
      nachtrag_id: document.getElementById('n-id').value,
      claim_value_eur: parseFloat(document.getElementById('n-value').value),
      nachtrag_text: document.getElementById('n-text').value,
      original_lv_text: document.getElementById('n-lv').value,
      correspondence_text: document.getElementById('n-corr').value,
      contract_type: document.getElementById('n-contract').value,
      is_pauschalvertrag: document.getElementById('n-pauschal').value === 'true',
    });
    const ms = Date.now() - t0;
    document.getElementById('n-timing').textContent = ms + 'ms';
    // Show verdict cards
    if (data.likely_outcome_pct !== undefined) {
      document.getElementById('n-verdict').style.display = 'grid';
      document.getElementById('v-pct').textContent = data.likely_outcome_pct + '%';
      const mid = data.estimated_exposure?.midpoint_eur;
      document.getElementById('v-mid').textContent = mid ? 'EUR ' + mid.toLocaleString('de-DE') : '—';
      document.getElementById('v-rec').textContent = data.recommendation || '—';
    }
    showResult('n-result', data);
  } catch(e) { showError('n-result', e.message); }
}

async function runAdversarial() {
  loading('adv-result', 'Deploying adversarial agents...');
  document.getElementById('adv-versus').style.display = 'none';
  try {
    const data = await post('/api/legatum/adversarial/analyse', {
      clause_text: document.getElementById('adv-text').value,
      context: document.getElementById('adv-ctx').value,
      mode: document.getElementById('adv-mode').value,
    });
    document.getElementById('adv-versus').style.display = 'grid';
    document.getElementById('adv-an-args').innerHTML =
      (data.an_arguments || []).map(a => '• ' + a).join('<br>');
    document.getElementById('adv-ag-args').innerHTML =
      (data.ag_arguments || []).map(a => '• ' + a).join('<br>');
    document.getElementById('adv-an-strength').textContent =
      data.an_strength ? (data.an_strength * 100).toFixed(0) + '%' : '—';
    document.getElementById('adv-ag-strength').textContent =
      data.ag_strength ? (data.ag_strength * 100).toFixed(0) + '%' : '—';
    showResult('adv-result', data);
  } catch(e) { showError('adv-result', e.message); }
}

async function recordVendorEvent() {
  loading('v-event-result', 'Erfasse Ereignis...');
  try {
    const data = await post('/api/legatum/vendor/event', {
      vendor_name: document.getElementById('v-name').value,
      project_id: document.getElementById('v-project-id').value,
      project_name: document.getElementById('v-project-name').value,
      pattern_id: document.getElementById('v-pattern').value,
      claim_value_eur: parseFloat(document.getElementById('v-claim').value),
      evidence_text: document.getElementById('v-evidence').value,
    });
    showResult('v-event-result', data);
  } catch(e) { showError('v-event-result', e.message); }
}

async function runProcurementCheck() {
  loading('pc-result', 'Prüfe Auftragnehmer-Historie...');
  try {
    const data = await post('/api/legatum/vendor/procurement-check', {
      vendor_name: document.getElementById('pc-name').value,
      contract_value_eur: parseFloat(document.getElementById('pc-value').value),
    });
    showResult('pc-result', data);
  } catch(e) { showError('pc-result', e.message); }
}

async function loadDemoSchedule() {
  loading('sched-result', 'Lade Demo-Terminplan...');
  try {
    const data = await fetch('/api/legatum/schedule/demo', {method:'POST'}).then(r=>r.json());
    showResult('sched-result', data);
  } catch(e) { showError('sched-result', e.message); }
}

async function runCascade() {
  loading('c-result', 'Berechne Kaskade entlang kritischem Pfad...');
  try {
    const data = await post('/api/legatum/schedule/cascade', {
      project_id: document.getElementById('c-project').value,
      trigger_node_id: document.getElementById('c-trigger').value,
      delay_days: parseInt(document.getElementById('c-delay').value),
      initial_strength: 1.0,
    });
    showResult('c-result', data);
  } catch(e) { showError('c-result', e.message); }
}

async function buildMesh() {
  loading('m-result', 'Baue Contractual Mesh...');
  try {
    const docs = JSON.parse(document.getElementById('m-docs').value);
    const data = await post('/api/legatum/mesh/build', { documents: docs });
    showResult('m-result', data);
  } catch(e) { showError('m-result', e.message); }
}

async function buildKG() {
  loading('kg-build-result', 'Extracting entities + building Knowledge Graph...');
  try {
    const data = await post('/api/legatum/kg/build', {
      doc_id: parseInt(document.getElementById('kg-docid').value),
      filename: document.getElementById('kg-filename').value,
      text: document.getElementById('kg-text').value,
    });
    showResult('kg-build-result', data);
  } catch(e) { showError('kg-build-result', e.message); }
}

async function getKGStats() {
  loading('kg-build-result', 'Fetching KG stats...');
  try {
    const data = await fetch('/api/legatum/kg/stats').then(r=>r.json());
    showResult('kg-build-result', data);
  } catch(e) { showError('kg-build-result', e.message); }
}

async function searchKG() {
  loading('kg-search-result', 'Running BM25 + PPR hybrid search...');
  try {
    const data = await post('/api/legatum/kg/search', {
      query: document.getElementById('kg-query').value,
      top_k: parseInt(document.getElementById('kg-topk').value),
    });
    showResult('kg-search-result', data);
  } catch(e) { showError('kg-search-result', e.message); }
}

// ── Legal-Twin KG with D3 visualization ──────────────────────────────────────
let lkgSimulation = null;

async function buildDemoLegalTwin() {
  loading('lkg-build-result', 'Building Legal-Twin KG from 4 sample documents...');
  try {
    const data = await fetch('/api/legatum/legal-kg/demo', {method:'POST'}).then(r=>r.json());
    showResult('lkg-build-result', data);
    document.getElementById('lkg-stats').textContent =
      `${data.stats?.total_nodes||0} nodes · ${data.stats?.total_edges||0} edges · ` +
      `Pass1: ${data.stats?.pass1_inherited_edges||0} · Pass2: ${data.stats?.pass2_regulatory_edges||0} · Pass3: ${data.stats?.pass3_transitivity_edges||0}`;
    await loadKGViz();
  } catch(e) { showError('lkg-build-result', e.message); }
}

async function runTribunal() {
  loading('tribunal-result', 'Running 3-agent tribunal...');
  try {
    const data = await post('/api/legatum/legal-kg/tribunal', {
      entity_a: document.getElementById('trib-a').value,
      entity_b: document.getElementById('trib-b').value,
      context_a: document.getElementById('trib-ctx-a').value,
      context_b: document.getElementById('trib-ctx-b').value,
    });
    // Show verdict
    const el = document.getElementById('tribunal-result');
    el.style.display = 'block';
    const decisionColors = {merge:'#16a34a', separate:'#dc2626', needs_human:'#d97706'};
    el.style.color = decisionColors[data.final_decision] || '#68d391';
    el.textContent = JSON.stringify(data, null, 2);
  } catch(e) { showError('tribunal-result', e.message); }
}

const NODE_COLORS = {
  DOCUMENT: '#3b5bdb',
  COMPANY: '#0d7377',
  PERSON: '#7c3aed',
  GAEB_POSITION: '#f59e0b',
  VOB_PARAGRAPH: '#dc2626',
  VOB_SECTION: '#b91c1c',
  DIN_STANDARD: '#059669',
  CLAUSE: '#6366f1',
  FINANCIAL: '#0891b2',
  DATE: '#78716c',
  NACHTRAG: '#ea580c',
  ROLE: '#8b5cf6',
  DEFAULT: '#6b7280',
};

const EDGE_COLORS = {
  parent_of: '#3b5bdb',
  amended_by: '#ea580c',
  contains_position: '#f59e0b',
  mentions: '#94a3b8',
  regulated_by: '#059669',
  governed_by_vob: '#dc2626',
  inherits_clause: '#6366f1',
  overrides_clause: '#f97316',
  shared_risk_interface: '#ec4899',
  DEFAULT: '#cbd5e1',
};

async function loadKGViz() {
  try {
    const graph = await fetch('/api/legatum/legal-kg/graph').then(r=>r.json());
    if (!graph.nodes || graph.nodes.length === 0) return;
    renderD3Graph(graph);
  } catch(e) { console.error('KG viz error:', e); }
}

function renderD3Graph(graph) {
  if (typeof d3 === 'undefined') {
    document.getElementById('lkg-canvas').innerHTML =
      '<div style="color:#fc8181;padding:20px;">D3.js not loaded — refresh page</div>';
    return;
  }
  const container = document.getElementById('lkg-canvas');
  container.innerHTML = '';
  const W = container.offsetWidth || 800;
  const H = 500;

  const svg = d3.select('#lkg-canvas').append('svg')
    .attr('width', W).attr('height', H)
    .style('background', '#0f1923').style('border-radius', '10px');

  // Arrow markers
  const defs = svg.append('defs');
  Object.entries(EDGE_COLORS).forEach(([type, color]) => {
    defs.append('marker')
      .attr('id', 'arrow-' + type)
      .attr('viewBox', '0 -5 10 10').attr('refX', 20).attr('refY', 0)
      .attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto')
      .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', color).attr('opacity', 0.7);
  });

  const g = svg.append('g');

  // Zoom
  svg.call(d3.zoom().scaleExtent([0.2, 4]).on('zoom', (e) => g.attr('transform', e.transform)));

  // Build maps
  const nodeMap = {};
  graph.nodes.forEach(n => nodeMap[n.id] = n);

  // Filter valid links
  const validLinks = graph.links.filter(l => nodeMap[l.source] && nodeMap[l.target]);

  const simulation = d3.forceSimulation(graph.nodes)
    .force('link', d3.forceLink(validLinks)
      .id(d => d.id).distance(d => d.inferred ? 80 : 60).strength(0.5))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(W/2, H/2))
    .force('collision', d3.forceCollide(22));
  lkgSimulation = simulation;

  // Edges
  const link = g.append('g').selectAll('line')
    .data(validLinks).enter().append('line')
    .attr('stroke', d => EDGE_COLORS[d.type] || EDGE_COLORS.DEFAULT)
    .attr('stroke-width', d => d.inferred ? 1 : 2)
    .attr('stroke-dasharray', d => d.inferred ? '4,3' : null)
    .attr('stroke-opacity', 0.6)
    .attr('marker-end', d => `url(#arrow-${d.type in EDGE_COLORS ? d.type : 'DEFAULT'})`)
    .append('title').text(d => `${d.type}: ${d.legal_basis || ''}`);

  // Nodes
  const node = g.append('g').selectAll('g')
    .data(graph.nodes).enter().append('g')
    .call(d3.drag()
      .on('start', (e,d) => { if(!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on('drag', (e,d) => { d.fx=e.x; d.fy=e.y; })
      .on('end', (e,d) => { if(!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; }));

  node.append('circle')
    .attr('r', d => d.type === 'DOCUMENT' ? 14 : d.type === 'GAEB_POSITION' ? 11 : 8)
    .attr('fill', d => NODE_COLORS[d.type] || NODE_COLORS.DEFAULT)
    .attr('stroke', '#fff').attr('stroke-width', 1.5)
    .attr('opacity', 0.9);

  node.append('text')
    .attr('x', 12).attr('dy', '0.35em')
    .attr('fill', '#e2e8f0').attr('font-size', '10px')
    .text(d => d.name.length > 22 ? d.name.slice(0,22)+'…' : d.name);

  node.append('title').text(d =>
    `${d.name}\nType: ${d.type}${d.gaeb ? '\nGAEB: '+d.gaeb : ''}${d.valid_from ? '\nValid from: '+d.valid_from : ''}`);

  simulation.on('tick', () => {
    g.selectAll('line')
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
}
}
</script>
</body>
</html>"""


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.post("/nachtrag/pruefen")
async def pruefen_nachtrag(req: NachtragRequest):
    from legatum.nachtrag_engine import (
        NachtragInput, _run_procedural_checks, prüfe_nachtrag, verdict_to_dict
    )
    nachtrag = NachtragInput(
        nachtrag_id=req.nachtrag_id,
        claim_value_eur=req.claim_value_eur,
        nachtrag_text=req.nachtrag_text,
        original_lv_text=req.original_lv_text,
        correspondence_text=req.correspondence_text,
        contract_type=req.contract_type,
        is_pauschalvertrag=req.is_pauschalvertrag,
    )
    procedural = _run_procedural_checks(nachtrag)
    try:
        verdict = prüfe_nachtrag(nachtrag)
        return verdict_to_dict(verdict)
    except Exception:
        an_pts = procedural["an_procedural_points"]
        ag_pts = procedural["ag_procedural_points"]
        an_strength = max(0.3, 0.5 + len(an_pts) * 0.1 - len(ag_pts) * 0.1)
        return {
            "nachtrag_id": req.nachtrag_id,
            "claim_value_eur": req.claim_value_eur,
            "mode": "procedural_only (Ollama not running)",
            "an_procedural_arguments": an_pts,
            "ag_procedural_arguments": ag_pts,
            "vob_refs_triggered": procedural["vob_refs_triggered"],
            "likely_outcome_pct": round(an_strength * 100, 1),
            "estimated_exposure": {
                "min_eur": round(req.claim_value_eur * max(0, an_strength - 0.15), 2),
                "max_eur": round(req.claim_value_eur * min(1, an_strength + 0.15), 2),
                "midpoint_eur": round(req.claim_value_eur * an_strength, 2),
            },
            "recommendation": (
                "APPROVE_PARTIAL" if an_strength >= 0.55 else
                "NEGOTIATE" if an_strength >= 0.35 else "REJECT"
            ),
            "note": "Install Ollama + llama3.2:3b for full LLM analysis"
        }


@router.post("/adversarial/analyse")
async def adversarial_analyse(req: AdversarialRequest):
    """Run Predator/Prey adversarial analysis on a clause."""
    import re

    MODE_PROMPTS = {
        "nachtrag": {
            "an": "You are AN counsel. Find every reason this clause SUPPORTS a Nachtrag claim under VOB/B §2.",
            "ag": "You are AG counsel. Find every reason this clause DEFEATS the Nachtrag under VOB/B §2 Abs. 5 S. 2.",
        },
        "mangel": {
            "an": "You are the contractor. Find every reason the alleged defect is NOT a Mangel under VOB/B §13.",
            "ag": "You are the client. Find every reason this IS a Mangel and the contractor must remedy it under VOB/B §13.",
        },
        "vertragsstrafe": {
            "an": "You are the contractor. Find every reason the Vertragsstrafe clause is invalid or uncollectable.",
            "ag": "You are the client. Find every reason the Vertragsstrafe is enforceable under VOB/B §5.",
        },
    }

    mode = req.mode if req.mode in MODE_PROMPTS else "nachtrag"
    prompts = MODE_PROMPTS[mode]

    # Deterministic analysis (no LLM needed for patterns)
    text = req.clause_text.lower()

    an_args = []
    ag_args = []

    # Pattern-based argument generation
    if "schriftlich" in text or "anordnung" in text:
        an_args.append("Schriftliche Anordnung erkennbar → VOB/B §2 Abs. 5 erfüllt")
        ag_args.append("Prüfe: War die Anordnung VOB/B-konform? Ankündigung der Mehrvergütung vor Ausführung?")
    if "mündlich" in text:
        ag_args.append("Mündliche Anordnung ist gem. VOB/B §2 Abs. 5 nicht ausreichend — schriftliche Bestätigung erforderlich")
    if "pauschal" in text or "pauschalpreis" in text:
        ag_args.append("Pauschalvertrag gem. §2 Abs. 7 — Leistung möglicherweise im Pauschalpreis enthalten")
        an_args.append("Leistung geht über den vereinbarten Pauschalumfang hinaus → §2 Abs. 6 greift")
    if "änderung" in text or "change" in text:
        an_args.append("Leistungsänderung erkennbar → Nachtragsvergütungsrecht entsteht")
    if "vertragsstrafe" in text:
        ag_args.append("Vertragsstrafe wirksam vereinbart — Bauverzug ist nachzuweisen")
        an_args.append("Prüfe Obergrenze der Vertragsstrafe (max. 5% Auftragswert gem. BGH)")
    if "gewährleistung" in text or "mängel" in text:
        an_args.append("Gewährleistungsfrist ist dispositiv — prüfe vertragliche Abweichung von §13 Abs. 4")
        ag_args.append("Mängelrüge muss unverzüglich nach Entdeckung erfolgen gem. VOB/B §13")

    # Default arguments if none triggered
    if not an_args:
        an_args = [
            "Leistungsumfang unklar — Auslegung zugunsten AN (§305c BGB Unklarheitenregel)",
            "Prüfe ob Zusatzleistung vorliegt (§2 Abs. 6 VOB/B)",
        ]
    if not ag_args:
        ag_args = [
            "Keine eindeutige schriftliche Anordnung erkennbar",
            "Ankündigung der Mehrvergütung vor Ausführung fehlt (§2 Abs. 5 S. 2)",
        ]

    an_strength = min(0.9, 0.4 + len(an_args) * 0.1)
    ag_strength = min(0.9, 0.4 + len(ag_args) * 0.1)

    # Try LLM enhancement
    try:
        from legatum.nachtrag_engine import _llm
        an_raw = _llm(prompts["an"], f"Analyse this clause:\n{req.clause_text[:1500]}")
        ag_raw = _llm(prompts["ag"], f"Analyse this clause:\n{req.clause_text[:1500]}")
        if "[LLM_ERROR" not in an_raw and "[LLM_UNAVAIL" not in an_raw:
            an_args.append(f"[AI] {an_raw[:300]}")
            ag_args.append(f"[AI] {ag_raw[:300]}")
    except Exception:
        pass

    dissonance = len(an_args) > 0 and len(ag_args) > 0
    return {
        "mode": mode,
        "an_arguments": an_args,
        "ag_arguments": ag_args,
        "an_strength": round(an_strength, 2),
        "ag_strength": round(ag_strength, 2),
        "dissonance_detected": dissonance,
        "dissonance_signal": "⚡ DISSONANCE — Both sides contested. High negotiation risk." if dissonance else None,
        "contested_zone": req.clause_text[:200] + "..." if dissonance else None,
    }


@router.post("/vendor/event")
async def record_event(req: VendorEventRequest):
    from legatum.vendor_risk import VendorBehaviorEvent, record_vendor_event, _vendor_id
    vid = _vendor_id(req.vendor_name)
    event = VendorBehaviorEvent(
        vendor_id=vid, vendor_name=req.vendor_name,
        project_id=req.project_id, project_name=req.project_name,
        pattern_id=req.pattern_id, claim_value_eur=req.claim_value_eur,
        evidence_text=req.evidence_text,
    )
    result = record_vendor_event(event)
    try:
        from legatum.vendor_risk import get_vendor_risk_profile
        profile = get_vendor_risk_profile(req.vendor_name)
        result["profile_summary"] = {
            "risk_classification": profile.risk_classification,
            "risk_score": profile.risk_score,
            "active_patterns": len(profile.behavioral_patterns),
            "permanent_patterns": sum(1 for p in profile.behavioral_patterns if p["is_permanent"]),
        }
    except Exception:
        pass
    return result


@router.post("/vendor/procurement-check")
async def procurement_check(req: ProcurementCheckRequest):
    from legatum.vendor_risk import procurement_check as _check
    return _check(req.vendor_name, req.contract_value_eur)


@router.post("/schedule/demo")
async def load_demo_schedule():
    from legatum.schedule_cascade import register_schedule
    tasks = [
        {"node_id": "T001", "name": "Betonage Kellerdecke", "trade": "betonage",
         "planned_start": "2026-06-15", "planned_end": "2026-06-22",
         "predecessors": [], "lag_days": 0, "contract_value_eur": 45000,
         "subcontractor": "Beton AG", "is_critical_path": True},
        {"node_id": "T002", "name": "Rohbau Erdgeschoss", "trade": "rohbau",
         "planned_start": "2026-06-23", "planned_end": "2026-07-10",
         "predecessors": ["T001"], "lag_days": 1, "contract_value_eur": 120000,
         "subcontractor": "Rohbau GmbH", "is_critical_path": True},
        {"node_id": "T003", "name": "Estrich verlegen", "trade": "estrich",
         "planned_start": "2026-07-14", "planned_end": "2026-07-25",
         "predecessors": ["T002"], "lag_days": 4, "contract_value_eur": 28000,
         "subcontractor": "Estrich Partner", "is_critical_path": False},
        {"node_id": "T004", "name": "Elektroinstallation", "trade": "elektroinstallation",
         "planned_start": "2026-07-28", "planned_end": "2026-08-15",
         "predecessors": ["T003"], "lag_days": 3, "contract_value_eur": 65000,
         "subcontractor": "Elektro Müller", "is_critical_path": True},
        {"node_id": "T005", "name": "Trockenbau", "trade": "trockenbau",
         "planned_start": "2026-08-18", "planned_end": "2026-09-05",
         "predecessors": ["T004"], "lag_days": 3, "contract_value_eur": 55000,
         "subcontractor": "Trockenbau Schmidt", "is_critical_path": False},
    ]
    result = register_schedule("PRJ-DEMO-2026", tasks)
    return {**result, "nodes": ["T001","T002","T003","T004","T005"],
            "tip": "Now trigger cascade on T001 with 14 day delay"}


@router.post("/schedule/cascade")
async def run_cascade(req: CascadeRequest):
    from legatum.schedule_cascade import propagate_delay_cascade, cascade_to_dict
    result = propagate_delay_cascade(
        project_id=req.project_id,
        trigger_node_id=req.trigger_node_id,
        delay_days=req.delay_days,
        initial_strength=req.initial_strength,
    )
    return cascade_to_dict(result)


@router.post("/mesh/build")
async def build_mesh(req: MeshRequest):
    from legatum.contractual_mesh import build_contractual_mesh
    result = build_contractual_mesh(req.documents)
    result["doc_types"] = list(result.get("doc_types", []))
    return result


@router.post("/kg/build")
async def kg_build(req: KGBuildRequest):
    """Build knowledge graph using Legal-Twin KG engine."""
    from legatum.legal_kg import build_legal_twin
    # Detect doc type from filename
    fname = req.filename.lower()
    if "nachtrag" in fname:
        doc_type = "NACHTRAG"
    elif "lv" in fname or "leistungsverzeichnis" in fname:
        doc_type = "LV"
    elif "hauptvertrag" in fname or "werkvertrag" in fname:
        doc_type = "HAUPTVERTRAG"
    else:
        doc_type = "UNKNOWN"

    result = build_legal_twin([{
        "doc_id": req.doc_id,
        "filename": req.filename,
        "text": req.text,
        "doc_type": doc_type,
    }])
    return {
        "nodes": result["stats"]["total_nodes"],
        "edges": result["stats"]["total_edges"],
        "pass2_regulatory_edges": result["stats"]["pass2_regulatory_edges"],
        "doc_type_detected": doc_type,
        "tip": "Go to Legal-Twin KG tab to see the full graph visualization"
    }


@router.get("/kg/stats")
async def kg_stats():
    from legatum.contractual_mesh import _get_db
    conn = _get_db()
    nodes = conn.execute("SELECT COUNT(*) FROM ms_contract_nodes").fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM ms_contract_edges").fetchone()[0]
    conn.close()
    return {"nodes": nodes, "edges": edges, "source": "contractual_mesh"}


@router.post("/kg/search")
async def kg_search(req: KGQueryRequest):
    from legatum.contractual_mesh import _get_db
    import re
    conn = _get_db()
    nodes = conn.execute("SELECT * FROM ms_contract_nodes").fetchall()
    conn.close()
    query_terms = set(re.findall(r'\w{3,}', req.query.lower()))
    results = []
    for n in nodes:
        n = dict(n)
        score = sum(1 for t in query_terms if t in n.get("name", "").lower())
        if score > 0:
            results.append({**n, "score": score / len(query_terms)})
    results.sort(key=lambda x: -x["score"])
    return {"results": results[:req.top_k], "query": req.query, "source": "contractual_mesh"}


# ── Company Knowledge / Agentic Memory endpoints ─────────────────────────────

class MemoryAddRequest(BaseModel):
    entity: str
    entity_type: str = "CONCEPT"
    fact: str
    source_doc: str = ""
    project_id: str = ""
    confidence: float = 1.0

@router.post("/memory/add")
async def memory_add(req: MemoryAddRequest):
    from ma.drift_detector import add_company_knowledge
    kid = add_company_knowledge(
        req.entity, req.entity_type, req.fact,
        req.source_doc, req.project_id, req.confidence
    )
    return {"id": kid, "status": "stored"}

@router.get("/memory/list")
async def memory_list(project_id: str = "", limit: int = 200):
    from ma.drift_detector import list_company_knowledge
    return {"entries": list_company_knowledge(project_id, limit)}

@router.delete("/memory/{kid}")
async def memory_delete(kid: str):
    from ma.drift_detector import delete_company_knowledge
    deleted = delete_company_knowledge(kid)
    return {"deleted": deleted}

@router.get("/memory/stats")
async def memory_stats():
    from ma.drift_detector import _db, _ensure_tables, _migrate_company_knowledge
    _ensure_tables()
    _migrate_company_knowledge()
    conn = _db()
    total    = conn.execute("SELECT COUNT(*) FROM company_knowledge").fetchone()[0]
    permanent = conn.execute("SELECT COUNT(*) FROM company_knowledge WHERE is_permanent=1").fetchone()[0]
    auto     = conn.execute("SELECT COUNT(*) FROM company_knowledge WHERE confidence<1.0").fetchone()[0]
    manual   = total - auto
    by_type  = conn.execute(
        "SELECT entity_type, COUNT(*) as cnt, AVG(memory_strength) as avg_str "
        "FROM company_knowledge GROUP BY entity_type ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return {
        "total": total, "permanent": permanent,
        "auto_learned": auto, "manually_added": manual,
        "by_type": [{"type": r[0], "count": r[1], "avg_strength": round(r[2] or 0, 3)} for r in by_type]
    }


# ── Legal-Twin KG endpoints ───────────────────────────────────────────────────

@router.post("/legal-kg/build")
async def build_legal_twin(req: LegalTwinRequest):
    from legatum.legal_kg import build_legal_twin
    return build_legal_twin(req.documents, req.project_id)


@router.get("/legal-kg/graph")
async def get_legal_kg_graph():
    from legatum.legal_kg import get_graph_for_viz
    return get_graph_for_viz()


@router.post("/legal-kg/tribunal")
async def run_tribunal(req: TribunalRequest):
    from legatum.legal_kg import tribunal_dedup
    return tribunal_dedup(req.entity_a, req.context_a, req.entity_b, req.context_b)


@router.post("/legal-kg/demo")
async def build_demo_legal_twin():
    """Build a demo Legal-Twin KG from sample construction documents."""
    from legatum.legal_kg import build_legal_twin
    docs = [
        {
            "doc_id": 201,
            "filename": "Hauptvertrag_Neubau_Berlin.pdf",
            "doc_type": "HAUPTVERTRAG",
            "valid_from": "2026-01-15",
            "text": """Werkvertrag zwischen Mustermann Bau GmbH (Auftraggeber) und
            Schmidt Tiefbau GmbH (Auftragnehmer) für Neubau Logistikzentrum Berlin.
            Auftragssumme EUR 2.400.000. Ausführung 01.04.2026 bis 30.11.2026.
            Vertragsstrafe 0,2% pro Werktag max 5%. Gewährleistung 4 Jahre gem. VOB/B §13 Abs. 4.
            Sicherheitseinbehalt 5%. Abtretungsverbot ohne Zustimmung AG. Versicherungspflicht AN.
            Gerichtsstand Berlin. Bankgarantie EUR 120.000. Bauleiter: Dipl.-Ing. Thomas Meier.
            Architekt: Planungsbüro Weber GmbH."""
        },
        {
            "doc_id": 202,
            "filename": "Leistungsverzeichnis_Los1_Tiefbau.gaeb",
            "doc_type": "LV",
            "valid_from": "2026-01-15",
            "text": """Leistungsverzeichnis Los 1 Tiefbau und Rohbau.
            Position 01.01.001 Erdarbeiten Aushub 850m³ EUR 42,00/m³ = EUR 35.700.
            Position 01.02.001 Betonarbeiten Fundament C25/30 95m³ EUR 195,00/m³.
            Position 02.01.001 Mauerwerk Kalksandstein 380m² EUR 85,00/m².
            Position 03.01.001 Estrich Zementestrich ZE20 620m² EUR 28,50/m².
            Erdarbeiten gem. DIN 18300. Betonarbeiten gem. DIN 18331 und DIN EN 206.
            Mauerwerk gem. DIN 18330."""
        },
        {
            "doc_id": 203,
            "filename": "Nachtrag_003_Baugrundrisiko.pdf",
            "doc_type": "NACHTRAG",
            "valid_from": "2026-05-12",
            "text": """Nachtrag Nr. 3 zu Position 01.01.001 Erdarbeiten.
            Aufgrund unvorhergesehener Baugrundverhältnisse (Fels auf Tiefe 2,40m statt 4,00m)
            entstehen Mehrkosten für Felssprengen. Schriftliche Anordnung AG vom 10.05.2026.
            Zusatzleistung gem. VOB/B §2 Abs. 5. Mehrkosten EUR 48.500.
            Auftragnehmer: Schmidt Tiefbau GmbH. Auftraggeber: Mustermann Bau GmbH.
            DIN 18301 Bohrarbeiten. VOB/B §4 Abs. 1 Baugrundrisiko beim AG."""
        },
        {
            "doc_id": 204,
            "filename": "Behinderungsanzeige_Elektro.pdf",
            "doc_type": "UNKNOWN",
            "valid_from": "2026-07-03",
            "text": """Behinderungsanzeige gem. VOB/B §6 Abs. 1.
            Elektroinstallation gem. DIN VDE 0100 kann nicht planmäßig beginnen da Rohbau
            Erdgeschoss noch nicht abgenommen. Verzögerung ca. 14 Tage.
            Subunternehmer Elektro Müller GmbH meldet Mehrkosten EUR 8.200.
            VOB/B §6 Abs. 6 Schadensersatz vorbehalten. Bauleiter: Dipl.-Ing. Thomas Meier."""
        },
    ]
    return build_legal_twin(docs, "DEMO-BERLIN-2026")


# ── Pheromone endpoints ───────────────────────────────────────────────────────

@router.post("/pheromones/analyse")
async def pheromone_analyse(req: PheromoneRequest):
    from legatum.pheromones import analyse_documents
    return analyse_documents(req.documents)


@router.get("/pheromones/field")
async def pheromone_field():
    from legatum.pheromones import get_pheromone_field
    field = get_pheromone_field()
    return {
        "hot_nodes": field.hot_nodes,
        "compound_nodes": field.compound_nodes,
        "signal_count": field.signal_count,
        "dominant_signals": field.dominant_signals,
    }


@router.post("/pheromones/demo")
async def pheromone_demo():
    from legatum.pheromones import analyse_documents
    docs = [
        {"doc_id": 301, "filename": "Behinderungsanzeige_Elektro.pdf",
         "text": "Behinderungsanzeige gem. VOB/B §6. Elektroinstallation verzögert sich "
                 "durch nicht fertiggestellten Rohbau. Schadensersatz vorbehalten. "
                 "Bauzeitverlängerung beantragt."},
        {"doc_id": 302, "filename": "Nachtrag_003_Baugrundrisiko.pdf",
         "text": "Nachtrag für unvorhergesehene Baugrundverhältnisse. Mehrvergütung "
                 "EUR 48.500 beantragt. Leistungsänderung gem. VOB/B §2 Abs. 5."},
        {"doc_id": 303, "filename": "Maengelprotokoll_Abnahme.pdf",
         "text": "Abnahmeprotokoll mit Mängeln: Estrich nicht ausreichend verdichtet, "
                 "Fenster nicht dicht, Elektroinstallation unvollständig. "
                 "Nachbesserung innerhalb 14 Tagen gefordert."},
        {"doc_id": 304, "filename": "Email_Vertragsstrafe.pdf",
         "text": "Verzug von 18 Werktagen festgestellt. Vertragsstrafe von 0,2% pro Tag "
                 "wird geltend gemacht. Schadenersatz wird geprüft. Anwalt eingeschaltet."},
        {"doc_id": 305, "filename": "Hauptvertrag_Sicherheiten.pdf",
         "text": "Hauptvertrag mit Sicherheitseinbehalt 5%, Bankgarantie EUR 120.000. "
                 "Abnahme gem. VOB/B §12. Keine ausstehenden Unterlagen."},
    ]
    return analyse_documents(docs)


# ── Document Processor endpoints (PDF + Image pipeline) ────────────────────────

class DocumentProcessorRequest(BaseModel):
    pdf_paths: list[str] = []
    image_paths: list[str] = []
    use_mock_detector: bool = True


@router.post("/documents/process")
async def process_documents(req: DocumentProcessorRequest):
    """
    Process PDFs and images through the full pipeline:
    1. PDF topography extraction
    2. Image deduplication
    3. Defect detection
    4. Pheromone signal generation
    """
    from legatum.document_processor import process_documents
    result = process_documents(
        pdf_paths=req.pdf_paths,
        image_paths=req.image_paths,
        use_mock_detector=req.use_mock_detector,
    )
    return {
        "summary": result.processing_summary,
        "pdfs": result.pdf_results,
        "images": {
            "deduplication": result.image_stats,
            "defect_analysis": result.defect_results,
        },
        "pheromone_signals": result.pheromone_signals,
        "kg_amendments": result.kg_amendments,
    }


@router.post("/documents/deduplicate")
async def deduplicate_images(image_paths: list[str]):
    """Deduplicate a batch of images using perceptual hashing."""
    from legatum.image_deduplicator import deduplicate_images
    return deduplicate_images(image_paths, threshold=0.90)


@router.post("/documents/analyze-defects")
async def analyze_defects(image_paths: list[str]):
    """Analyze images for construction defects."""
    from legatum.edge_defect_detector import analyze_batch, create_detector
    detector = create_detector(use_mock=True)
    results, summary = analyze_batch(image_paths, detector)
    return {
        "summary": summary,
        "results": [
            {
                "filename": r.filename,
                "has_defects": r.has_defects,
                "detections": [
                    {
                        "type": d.defect_type,
                        "confidence": round(d.confidence, 3),
                        "severity": d.severity,
                        "signal": d.pheromone_signal,
                    }
                    for d in r.detections
                ],
                "primary_signals": r.primary_signals,
            }
            for r in results
        ],
    }


@router.post("/documents/extract-topography")
async def extract_topography(pdf_paths: list[str]):
    """Extract spatial structure from PDFs (topography, stamps, amendments)."""
    from legatum.document_processor import DocumentProcessor
    processor = DocumentProcessor()
    results = processor.process_pdfs(pdf_paths)
    return {
        "count": len(results),
        "documents": results,
    }


@router.post("/documents/analyze-diagrams")
async def analyze_diagrams(pdf_paths: list[str]):
    """Analyze PDFs for diagram structure using 4-layer approach."""
    from legatum.diagram_analyzer import extract_diagrams_from_pdf, diagrams_to_kg_edges

    all_diagrams = []
    for pdf_path in pdf_paths:
        diagrams = extract_diagrams_from_pdf(pdf_path)
        all_diagrams.extend(diagrams)

    edges = diagrams_to_kg_edges(all_diagrams)

    return {
        "diagrams_analyzed": len(all_diagrams),
        "diagram_pages": [d.page for d in all_diagrams],
        "extraction_methods": list(set(
            m for d in all_diagrams for m in d.extraction_methods_used
        )),
        "kg_edges_generated": len(edges),
        "edges": edges[:50],  # First 50 edges
    }


@router.get("/documents/demo")
async def demo_document_processing():
    """Demo the full document processing pipeline with sample files."""
    from legatum.document_processor import ProcessingResult
    from pathlib import Path

    # Mock result for demo
    demo_result = {
        "summary": {
            "pdfs_processed": 2,
            "pdfs_successful": 2,
            "total_images": 8,
            "unique_images": 5,
            "duplicates_skipped": 3,
            "savings_pct": 37.5,
            "images_analyzed": 5,
            "images_with_defects": 3,
            "total_defects_detected": 4,
            "pheromone_signals_generated": 3,
            "amendments_detected": 1,
        },
        "pdfs": [
            {
                "filename": "Hauptvertrag_Berlin.pdf",
                "pages": 12,
                "document_hash": "a3f7b2c1d4e5",
                "block_count": 234,
                "stamp_count": 3,
                "table_count": 2,
                "amendments": [
                    {
                        "revision": "A",
                        "date": "2026-06-15",
                        "page": 1,
                    }
                ],
                "text_summary": "Document: Hauptvertrag_Berlin.pdf\nPages: 12\n...extracted text blocks...",
            },
            {
                "filename": "Leistungsverzeichnis.pdf",
                "pages": 8,
                "document_hash": "b4f8c3d2e6f7",
                "block_count": 156,
                "stamp_count": 1,
                "table_count": 4,
                "amendments": [],
                "text_summary": "Document: Leistungsverzeichnis.pdf\n...extracted text blocks...",
            },
        ],
        "images": {
            "deduplication": {
                "total": 8,
                "unique": 5,
                "duplicates": 3,
                "savings_pct": 37.5,
                "fingerprints": [
                    {
                        "filename": "site_01_concrete.jpg",
                        "md5": "a1b2c3d4",
                        "is_duplicate": False,
                        "duplicate_of": None,
                        "similarity": 1.0,
                    },
                    {
                        "filename": "site_01_concrete_angle2.jpg",
                        "md5": "a1b2c5d6",
                        "is_duplicate": True,
                        "duplicate_of": "site_01_concrete.jpg",
                        "similarity": 0.94,
                    },
                ],
            },
            "defect_analysis": [
                {
                    "filename": "site_01_concrete.jpg",
                    "image_hash": "f3c2b1a0",
                    "has_defects": True,
                    "defect_count": 2,
                    "detections": [
                        {
                            "type": "concrete_crack",
                            "confidence": 0.87,
                            "severity": 2,
                            "signal": "MANGEL_FLAG",
                        },
                        {
                            "type": "spalling",
                            "confidence": 0.72,
                            "severity": 2,
                            "signal": "MANGEL_FLAG",
                        },
                    ],
                    "primary_signals": ["MANGEL_FLAG"],
                },
                {
                    "filename": "site_02_rebar.jpg",
                    "image_hash": "e2d1a0f3",
                    "has_defects": True,
                    "defect_count": 1,
                    "detections": [
                        {
                            "type": "rebar_exposed",
                            "confidence": 0.92,
                            "severity": 3,
                            "signal": "MANGEL_FLAG",
                        },
                    ],
                    "primary_signals": ["MANGEL_FLAG"],
                },
            ],
        },
        "pheromone_signals": [
            {
                "source": "site_01_concrete.jpg",
                "signal_types": ["MANGEL_FLAG"],
                "defect_count": 2,
            },
            {
                "source": "site_02_rebar.jpg",
                "signal_types": ["MANGEL_FLAG"],
                "defect_count": 1,
            },
            {
                "source": "Hauptvertrag_Berlin.pdf",
                "signal_types": ["AUDIT_BEACON"],
                "defect_count": 1,
            },
        ],
        "kg_amendments": [
            {
                "revision": "A",
                "date": "2026-06-15",
                "page": 1,
                "bbox": [100, 500, 300, 520],
            },
        ],
    }

    return demo_result


import re as _re

# ── Construction ontology v0.3 — 12 entity types (ISO 19650 / VDI 2552 / Studio aligned) ──
# Based on generic_project_information_ontology, condensed to what appears in
# VOB/B · HOAI · BIM-Leitfaden documents.
# Ordered by specificity — most specific first so patterns don't shadow each other.
_ENTITY_PATTERNS = [
    # INFORMATION_REQUIREMENT — AIA, LOIN, delivery specs (most specific BIM concept)
    ("INFORMATION_REQUIREMENT", _re.compile(
        r'\b(AIA|Auftraggeber-Informations-Anforderung(?:en)?|'
        r'LOIN|Level of Information Need|'
        r'Informationsanforderung(?:en)?|Datenanforderung(?:en)?|'
        r'Lieferumfang|Informationsbedarf|Datenschema|'
        r'geometrische\s+Anforderung|semantische\s+Anforderung|'
        r'Dokumentationsanforderung)\b',
        _re.I)),

    # CONSTRAINT — deadlines, quantities, tolerances, financial limits
    ("CONSTRAINT", _re.compile(
        r'\b\d+\s*(Tage?|Wochen?|Monate?|Stunden?|Werktage?)\b|'
        r'\b\d+[,.]?\d*\s*(mm|cm|m²|m³|m|kg|kN|MPa|kPa|%|€|EUR)\b|'
        r'\b[A-Z]\d+/\d+\b|'                                # C30/37, S355
        r'\b(Toleranz|Mindest(?:maß)?|Maximal(?:maß)?|Grenzwert|'
        r'Vertragsstrafe|Sicherheitseinbehalt|Bürgschaft|Skonti?|'
        r'Abzug|Nachlass|Vorauszahlung|Abschlag|Einheitspreis)\s*\w*',
        _re.I)),

    # STANDARD_OR_RULE — norms, law paragraphs, naming conventions, exchange formats
    ("STANDARD_OR_RULE", _re.compile(
        r'VOB/[ABC]\s*(§\s*\d+(\s*Abs\.\s*\d+)?(\s*Satz\s*\d+)?)?|'
        r'HOAI\s*(LP\s*\d+|§\s*\d+)?|'
        r'DIN\s*(EN\s*|ISO\s*)?\d{2,}(\s*[-:]\d+)?|'
        r'ISO\s*\d{4,}|VDI\s*\d{4}|VDE\s*\d{4}|'
        r'IFC\s*\d*|BCF\s*\d*|GAEB\s*[\w.-]*|'
        r'LBO|BauO|BauGB|MBO|DSGVO|GEG|EnEV|'
        r'§\s*\d+\s*(Abs\.\s*\d+\s*)?(Satz\s*\d+)?|'
        r'\b(Namenskonvention|Klassifikationssystem|Austauschformat|'
        r'Qualitätsregel|Ablaufregel|Modellierungsrichtlinie)\b',
        _re.I)),

    # INFORMATION_REQUIREMENT — AIA, BAP, LOIN, exchange requirements
    ("INFORMATION_REQUIREMENT", _re.compile(
        r'\b(AIA|Auftraggeber-Informations-Anforderung|'
        r'BAP|BIM-Abwicklungsplan|'
        r'LOIN|Level of Information Need|'
        r'Informationsanforderung|Auskunftspflicht|'
        r'Informationslieferung|Lieferanforderung)\b',
        _re.I)),

    # ACTOR — persons, orgs, project roles, governance roles
    ("ACTOR", _re.compile(
        r'BIM-(Management|Manager|Koordinat|Gesamtkoordinat|Fachkoordinat|'
        r'Modellierer|Autor|Informationsmanager|Verantwortliche[r]?|'
        r'Kompetenzzentrum|Beauftragter?)|'
        r'\b(Auftraggeber|Auftragnehmer|Bauleiter|Objektplaner|Fachplaner|'
        r'Architekt|Statiker|Prüfingenieur|Projektsteuerer|Bauherr|'
        r'Generalunternehmer|Nachunternehmer|Subunternehmer|'
        r'Projektleiter|Planungskoordinator|Facility.?Manager|'
        r'Betreiber|Eigentümer|Nutzer|Behörde|Prüfstelle|'
        r'Straßenbauverwaltung|Landesbehörde|Bundesbehörde|'
        r'Ministerium|Stefan\s+Heß|'
        r'AG\b|AN\b)\b',
        _re.I)),

    # MODEL — digital representations (BIM models, twins, discipline models)
    ("MODEL", _re.compile(
        r'\b(Koordinationsmodell|Fachmodell|Gesamtmodell|Bestandsmodell|'
        r'As-Built-Modell|Digitaler?\s+Zwilling|Referenzmodell|'
        r'Architekturmodell|Tragwerksmodell|TGA-Modell|'
        r'Teilmodell|Planungsmodell|Betriebsmodell|'
        r'LOD\s*\d*|LOG\s*\d*|LOI\s*\d*|LOIN\s*\d*|'
        r'Koordinationsgrad|Modellqualität|Modellstatus)\b',
        _re.I)),

    # PROCESS — workflows, phases, approval steps, exchange steps
    ("PROCESS", _re.compile(
        r'\b(Abnahme(?:prozess)?|Qualitätssicherung|Qualitätsprüfung|'
        r'Rechnungsprüfung|Freigabeprozess|Freigabe|'
        r'Kollisionsprüfung|Koordination|Modellprüfung|'
        r'Vorplanung|Entwurfsplanung|Ausführungsplanung|'
        r'Leistungsphase\s*\d*|Behinderungsanzeige|Mängelrüge|Nachtrag|'
        r'Übergabe|Inbetriebnahme|Abrechnung|Vergabe|Ausschreibung|'
        r'Prüfung|Koordinierungsprozess|Reviewprozess|'
        r'Informationsaustausch|Datenübergabe|Handover|'
        r'Planfreigabe|Zeichnungsfreigabe|'
        r'Projektvorbereitung|Wissensmanagement|Schulung|'
        r'Anwendung\s+der\s+BIM|Einführung)\b',
        _re.I)),



    # DOCUMENT — formal docs, contracts, specs, reports
    ("DOCUMENT", _re.compile(
        r'\b(BIM-Abwicklungsplan|BAP|'
        r'Leistungsverzeichnis\b|LV\b|Aufmaß|'
        r'Ausführungsplan|Revisionsplan|Raumbuch|'
        r'Bautagebuch|Prüfbericht|Mängelprotokoll|Abnahmeprotokoll|'
        r'Bewehrungsplan|Schalungsplan|Werkstattzeichnung|'
        r'Schlussrechnung|Abschlagsrechnung|Nachtragsangebot|'
        r'Behinderungsanzeige|Mängelrüge|'
        r'Leitfaden|Richtlinie|Handbuch|Protokoll|Bericht|'
        r'Pflichtenheft|Lastenheft|Leistungsbeschreibung|'
        r'Vertragsbedingung|Vertragsunterlage)\b',
        _re.I)),

    # DATA_ENVIRONMENT — CDE, platforms, repositories
    ("DATA_ENVIRONMENT", _re.compile(
        r'\b(CDE|Common Data Environment|'
        r'Projektraum|Datenraum|Projektplattform|'
        r'Dokumentenmanagementsystem|DMS|'
        r'BIM 360|Trimble Connect|Autodesk Docs|'
        r'Revit|ArchiCAD|Allplan|Tekla|'
        r'Archiv|Projektablage|Wissensplattform)\b',
        _re.I)),

    # LIFECYCLE_PHASE — project/asset phases
    ("LIFECYCLE_PHASE", _re.compile(
        r'\b(Initiierung|Planung(?:sphase)?|Entwurf(?:sphase)?|'
        r'Vergabe(?:phase)?|Ausführung(?:sphase)?|Bauphase|'
        r'Übergabe(?:phase)?|Betrieb(?:sphase)?|'
        r'Instandhaltung(?:sphase)?|Abriss|Rückbau|'
        r'Lebenszyklus(?:phase)?|'
        r'BIM\s+in\s+der\s+(Betrieb|Landschaft|Planung|Ausführung)|'
        r'Phase\s+(I{1,3}|[123])|In\s+Phase\s+[123]|'
        r'Pilotprojekt|Rollout|Masterplan)\b',
        _re.I)),

    # PROJECT — construction projects, tenders, pilot projects (Studio: PROJECT node)
    ("PROJECT", _re.compile(
        r'\b(Pilotprojekt\s+[\w\-]+|Bauprojekt|Bauvorhaben|Großprojekt|'
        r'Infrastrukturprojekt|Projekt\s+[\w]{3,}|Tunnel\w+|Brücken\w+|'
        r'Neubau\s+\w+|Sanierung\s+\w+|Erweiterung\s+\w+|'
        r'Vergabeverfahren|Ausschreibungsprojekt|'
        r'Testprojekt|Musterprojekt|Referenzprojekt|Demonstrationsprojekt)\b',
        _re.I)),

    # ASSET — physical built assets (Studio: ASSET node)
    ("ASSET", _re.compile(
        r'\b(Bauwerk|Gebäude|Brücke|Tunnel|Straße|Autobahn|Bundesstraße|'
        r'Fahrbahn|Belag|Fundament|Tragwerk|Fassade|Dach|'
        r'Technische\s+Anlage|Haustechnik|Infrastrukturanlage|'
        r'Bestandsbauwerk|Ingenieurbauwerk|Sonderbauwerk|'
        r'Bauwerk-ID|Asset-ID|Anlage-ID)\b',
        _re.I)),

    # SOFTWARE_OR_TOOL — authoring tools, platforms, software (Studio: SOFTWARE_OR_TOOL node)
    ("SOFTWARE_OR_TOOL", _re.compile(
        r'\b(Revit|ArchiCAD|Allplan|Tekla\s*Structures|Navisworks|'
        r'BIM\s*360|Trimble\s+Connect|Autodesk\s+Docs|'
        r'Solibri|Dalux|DWG|IFC-Viewer|BIM-Software|'
        r'CAD-Software|Planungssoftware|Verwaltungssoftware|'
        r'Dokumentenmanagementsystem|DMS|Projektmanagementsoftware)\b',
        _re.I)),
]

def _classify_entity(text: str) -> str:
    import re as _re2
    # Strip leading chapter numbers (e.g. "3. Anwendung der..." → "Anwendung der...")
    clean = _re2.sub(r'^\d+(\.\d+)*\s*\.?\s*', '', text).strip()
    for entity_type, pattern in _ENTITY_PATTERNS:
        if pattern.search(clean) or pattern.search(text):
            return entity_type
    # Fallback heuristics for common BIM section titles not caught by patterns
    _cl = clean.lower()
    if any(k in _cl for k in ("rollen", "rolle", "verantwortlich", "zuständig")):
        return "ACTOR"
    if any(k in _cl for k in ("modellierung", "modell", "datenaustausch", "issuemanagement",
                               "vertragsbedingung", "rahmendokument", "quicklink",
                               "kurzdarstellung", "übersicht", "vorwort")):
        return "DOCUMENT"
    if any(k in _cl for k in ("schulung", "training", "einbindung", "nächste schritte",
                               "verwaltungsbehörde")):
        return "PROCESS"
    if any(k in _cl for k in ("landscape information", "lim", "landschaftsplanung",
                               "infrastruktur")):
        return "LIFECYCLE_PHASE"
    return "CONCEPT"

# ── Relation matrix — ISO 19650 aligned predicates ───────────────────────────
def _classify_relation(source_text: str, target_text: str) -> str:
    s = _classify_entity(source_text)
    t = _classify_entity(target_text)
    matrix = {
        # Actor relations
        ("ACTOR",                "DOCUMENT"):              "creates",
        ("ACTOR",                "MODEL"):                 "authors",
        ("ACTOR",                "PROCESS"):               "is_executed_by",
        ("ACTOR",                "INFORMATION_REQUIREMENT"):"is_responsible_for",
        ("ACTOR",                "DATA_ENVIRONMENT"):      "has_access_to",
        ("ACTOR",                "ACTOR"):                 "reports_to",
        # Process relations
        ("PROCESS",              "DOCUMENT"):              "produces",
        ("PROCESS",              "MODEL"):                 "produces",
        ("PROCESS",              "STANDARD_OR_RULE"):      "governed_by",
        ("PROCESS",              "CONSTRAINT"):            "bounded_by",
        ("PROCESS",              "DATA_ENVIRONMENT"):      "uses",
        # Document / Model relations
        ("DOCUMENT",             "STANDARD_OR_RULE"):      "must_comply_with",
        ("DOCUMENT",             "CONSTRAINT"):            "has_constraint",
        ("DOCUMENT",             "INFORMATION_REQUIREMENT"):"fulfils",
        ("DOCUMENT",             "DATA_ENVIRONMENT"):      "is_stored_in",
        ("MODEL",                "STANDARD_OR_RULE"):      "is_checked_against",
        ("MODEL",                "INFORMATION_REQUIREMENT"):"satisfies",
        ("MODEL",                "MODEL"):                 "is_derived_from",
        ("MODEL",                "DATA_ENVIRONMENT"):      "is_stored_in",
        # Information requirement
        ("INFORMATION_REQUIREMENT","STANDARD_OR_RULE"):   "is_defined_in",
        ("INFORMATION_REQUIREMENT","LIFECYCLE_PHASE"):    "applies_in",
        # Standard
        ("STANDARD_OR_RULE",     "CONSTRAINT"):           "defines",
        ("STANDARD_OR_RULE",     "LIFECYCLE_PHASE"):      "applies_in",
        # Lifecycle
        ("LIFECYCLE_PHASE",      "PROCESS"):              "contains",
        ("LIFECYCLE_PHASE",      "DOCUMENT"):             "requires",
        # Hierarchical / organizational (Studio alignment)
        ("ACTOR",                "PROJECT"):              "participates_in",
        ("ACTOR",                "ASSET"):                "manages",
        ("PROJECT",              "ACTOR"):                "has_participant",
        ("PROJECT",              "DOCUMENT"):             "produces",
        ("PROJECT",              "PROCESS"):              "executes",
        ("PROJECT",              "LIFECYCLE_PHASE"):      "contains",
        ("ASSET",                "DOCUMENT"):             "is_documented_by",
        ("ASSET",                "STANDARD_OR_RULE"):     "must_comply_with",
        ("SOFTWARE_OR_TOOL",     "DATA_ENVIRONMENT"):     "populates",
        ("SOFTWARE_OR_TOOL",     "MODEL"):                "produces",
        ("SOFTWARE_OR_TOOL",     "PROCESS"):              "supports",
        # Structural hierarchy (enables up-routing for broad questions)
        ("ACTOR",                "ACTOR"):                "sub_organization_of",
    }
    # Default: use PARENT_OF for heading-hierarchy edges, REFERENCES for unknown pairs
    return matrix.get((s, t), "references")


def _build_concept_kg_from_topography(topo) -> list[dict]:
    """
    Build a typed concept KG from document heading hierarchy.
    Nodes are classified into construction domain entity types.
    Relations are typed based on entity pair patterns.
    """
    # Collect headings by font size (larger = higher in hierarchy)
    headings = []
    seen_texts = set()
    for b in topo.blocks:
        if not b.font_size:
            continue
        text = b.text.strip()
        if len(text) < 3 or len(text) > 100:
            continue
        # Skip purely numeric or punctuation-only blocks
        if text.replace(".", "").replace(" ", "").isdigit():
            continue
        key = text[:40].lower()
        if key in seen_texts:
            continue
        seen_texts.add(key)
        headings.append({
            "text": text[:60],
            "font_size": b.font_size,
            "is_bold": b.is_bold,
            "page": b.page,
        })

    if not headings:
        return []

    # Sort by font size desc to determine hierarchy levels
    sizes = sorted(set(h["font_size"] for h in headings), reverse=True)
    # Map size → level (0 = top, 1 = section, 2 = subsection, ...)
    size_to_level = {s: min(i, 3) for i, s in enumerate(sizes)}

    # Body text threshold: the most common font size is body text.
    # Anything strictly larger than body text is a candidate heading.
    from collections import Counter as _Counter
    size_counts = _Counter(h["font_size"] for h in headings)
    body_size = size_counts.most_common(1)[0][0]  # most frequent = body text
    # A heading must be larger than body text OR bold at a distinct size
    heading_size_threshold = body_size  # strictly greater than this

    # Noise filters: skip TOC lines, figure captions, body sentences
    import re as _re
    _noise = _re.compile(
        r'^(Abbildung|Tabelle|Abb\.|Tab\.|Figure|Table|Anhang|Anlage)\s*\d|'
        r'^\d+(\.\d+)*\s*$|'           # bare numbers "1.2.3"
        r'^[A-ZÄÖÜ]{2,6}$|'            # abbrev-only "AIA"
        r'\.{4,}|'                      # TOC dotted lines
        r'^\s*\d+\s*$'                  # lone page numbers
    )
    def _is_heading_node(h: dict) -> bool:
        txt = h["text"]
        fs = h["font_size"]
        # Must be larger than body text font size
        if fs <= heading_size_threshold:
            return False
        if _noise.search(txt):
            return False
        # Skip body sentences: starts lowercase, or > 10 words, or has finite verbs
        if txt and txt[0].islower():
            return False
        if len(txt.split()) > 10:
            return False
        return True

    heading_nodes = [h for h in headings if _is_heading_node(h)]
    heading_nodes = heading_nodes[:80]  # cap

    if not heading_nodes:
        return []

    # Build parent stack — each node's parent is the nearest preceding node at a higher level
    rels = []
    stack = []  # list of (level, text)
    for h in heading_nodes:
        level = size_to_level[h["font_size"]]
        # Pop stack until we find a node at a higher (smaller number) level
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            parent_text = stack[-1][1]
            rel_type = _classify_relation(h["text"], parent_text)
            rels.append({
                "source": h["text"],
                "source_type": _classify_entity(h["text"]),
                "target": parent_text,
                "target_type": _classify_entity(parent_text),
                "type": rel_type,
                "method": "heading_hierarchy",
                "confidence": 0.9,
                "page": h["page"],
            })
        stack.append((level, h["text"]))

    return rels[:80]


# ── Async batch job registry ──────────────────────────────────────────────────
# Simple in-process store: job_id → {status, pdf_path, error}
# Survives the request lifecycle; resets on server restart (fine for prototype).
import asyncio as _asyncio
_JOBS: dict[str, dict] = {}

def _new_job_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


@router.post("/documents/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Accept a PDF upload, save to disk, immediately enqueue async extraction job."""
    if not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files are accepted"}
    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Fire-and-forget: schedule extraction + embedding in background
    job_id = _new_job_id()
    _JOBS[job_id] = {"status": "queued", "pdf_path": str(dest), "filename": file.filename}

    async def _run_extraction(jid: str, pdf_path: str):
        _JOBS[jid]["status"] = "extracting"
        try:
            from legatum.document_topography import parse_pdf_topography
            from legatum.graph_store import save_graph, embed_sections
            from ma.construction_screener import screen_sections, adversarial_scan

            # ── Stage 1: Parse PDF → sections + images (PyMuPDF, instant) ─
            topo = parse_pdf_topography(pdf_path)
            if not topo:
                _JOBS[jid] = {**_JOBS[jid], "status": "error", "error": "PyMuPDF unreadable"}
                return

            # Extract embedded images to disk
            import fitz as _fitz
            _img_dir = Path(__file__).parent.parent.parent / "legatum" / "extracted_images"
            _img_dir.mkdir(exist_ok=True)
            _embedded_images: list[dict] = []
            try:
                _doc = _fitz.open(pdf_path)
                for _pnum, _page in enumerate(_doc):
                    for _pi, _img in enumerate(_page.get_images(full=True)):
                        _w, _h = _img[2], _img[3]
                        if _w < 40 or _h < 40:
                            continue
                        _ext = "png" if _img[5] in ("Indexed", "DeviceGray") else "jpeg"
                        _fname = f"page{_pnum:02d}_img{_pi}_{_w}x{_h}.{_ext}"
                        _dest = _img_dir / _fname
                        if not _dest.exists():
                            try:
                                _pix = _fitz.Pixmap(_doc, _img[0])
                                if _pix.n > 4:
                                    _pix = _fitz.Pixmap(_fitz.csRGB, _pix)
                                _pix.save(str(_dest))
                            except Exception:
                                pass
                        _embedded_images.append({
                            "page": _pnum + 1, "width": _w, "height": _h,
                            "filename": _fname, "colorspace": _img[5],
                        })
                _doc.close()
            except Exception:
                pass
            _JOBS[jid]["images"] = {
                "total_embedded": len(_embedded_images),
                "pages_with_images": len(set(i["page"] for i in _embedded_images)),
                "details": _embedded_images,
            }

            # ── Hierarchical Chunking ─────────────────────────────────────
            # Build a heading-stack so every chunk carries its full document
            # breadcrumb: [Doc → H1 → H2 → H3].  BGE-M3 then embeds the
            # complete hierarchy, which means retrieval for "Koordinationsmodell
            # verantwortlich" will rank the BIM-Gesamtkoordination section above
            # BIM-Fachkoordination even when the body text is nearly identical.
            #
            # Heading level is derived from font_size bands.  We bucket all
            # unique font sizes into at most 4 tiers (H1…H4) so the stack
            # stays shallow and the breadcrumb stays readable.

            raw_blocks = sorted(topo.blocks, key=lambda x: (x.page, x.y0))

            # Step A: collect all heading-candidate font sizes and bin them.
            _heading_sizes = sorted(
                {b.font_size for b in raw_blocks
                 if b.font_size and (b.is_bold or b.font_size > 12)
                 and len(b.text.strip()) >= 4},
                reverse=True  # largest first
            )
            # Map each size to a level 1..4 (1 = biggest = H1)
            _size_to_level: dict[float, int] = {}
            for _rank, _fs in enumerate(_heading_sizes[:4]):
                _size_to_level[_fs] = _rank + 1
            # Any heading size not in the top-4 gets level 4 (treat as subheading)

            def _heading_level(block) -> int | None:
                """Return 1-4 if this block is a heading, else None."""
                txt = block.text.strip()
                if len(txt) < 4:
                    return None
                fs = block.font_size or 0
                # Large font: use size-band mapping
                if fs > 12:
                    return _size_to_level.get(fs, 4)
                # Bold + in size map (collected from bold candidates in Step A)
                if block.is_bold and fs in _size_to_level:
                    return _size_to_level[fs]
                # Bold short definition headers at body size (e.g. "Koordinationsmodell:")
                # These appear as glossary-style section labels in BIM/VOB documents
                if block.is_bold and len(txt) <= 80 and (txt.endswith(":") or txt.endswith("：")):
                    return 4
                return None

            # Step B: walk blocks maintaining a heading stack and emitting sections.
            _hstack: list[str] = []   # [H1_text, H2_text, H3_text, ...]
            _hlevels: list[int] = []  # parallel level for each entry

            sections: list[dict] = []
            cur: dict = {
                "heading": "", "doc": topo.filename, "page": 1,
                "blocks": [], "breadcrumb": topo.filename,
            }

            def _flush(cur: dict) -> None:
                """Finalize cur: build text = breadcrumb prefix + blocks, then append."""
                body = "\n".join(cur["blocks"]).strip()
                if not body and not cur["heading"]:
                    return
                crumb = cur.get("breadcrumb", "")
                # Prepend breadcrumb to text so the embedding captures hierarchy
                cur["text"] = (f"[{crumb}]\n{body}" if crumb else body) if body else f"[{crumb}]"
                sections.append(cur)

            for b in raw_blocks:
                txt = b.text.strip()
                if len(txt) < 10:
                    continue
                lvl = _heading_level(b)
                if lvl is not None:
                    # Flush the current section before starting a new one
                    _flush(cur)
                    # Pop stack back to parent level
                    while _hlevels and _hlevels[-1] >= lvl:
                        _hstack.pop()
                        _hlevels.pop()
                    # Push this heading
                    _hstack.append(txt)
                    _hlevels.append(lvl)
                    # Build breadcrumb: Doc → H1 → H2 → ...
                    crumb = " → ".join([topo.filename] + _hstack)
                    cur = {
                        "heading": txt,
                        "doc": topo.filename,
                        "page": b.page + 1,
                        "blocks": [],
                        "breadcrumb": crumb,
                    }
                else:
                    cur["blocks"].append(txt)

            _flush(cur)

            # ── Stage 2: Regex KG (instant, zero LLM) ─────────────────────
            rels = _build_concept_kg_from_topography(topo)
            node_set: dict = {}
            for r in rels:
                node_set[r["source"]] = {"id": r["source"], "type": r.get("source_type","CONCEPT"), "page": r.get("page")}
                node_set[r["target"]] = {"id": r["target"], "type": r.get("target_type","CONCEPT"), "page": r.get("page")}

            # ── Stage 2.5: Company Knowledge Injection (SONA memory) ─────
            # Inject pre-confirmed entities from resonance.db before any LLM runs.
            # These nodes carry confidence=1.0 and method="memory" so the LLM
            # delta metric correctly excludes them from the over-extraction warning.
            from ma.drift_detector import inject_memory_into_graph
            node_set, rels = inject_memory_into_graph(sections, node_set, rels)

            # ── Stage 3: Construction Rete + Adversarial Pollination ───────
            # Zero LLM — pure regex. Run before any Ollama calls.
            rete_result        = screen_sections(sections)
            adversarial_result = adversarial_scan(sections)
            _JOBS[jid]["clause_risk"] = rete_result
            _JOBS[jid]["heat_map"]    = adversarial_result

            # ── Stage 4: Embeddings (blocking Ollama HTTP) ────────────────
            _JOBS[jid]["status"] = "embedding"
            loop = _asyncio.get_event_loop()
            sections_emb = await loop.run_in_executor(None, embed_sections, sections)

            # ── Stage 4.5: Opinion Drifter (SONA-backed, zero LLM) ────────
            # Runs HERE — after deterministic stages 1-4, before any LLM calls.
            # Captures the unpolluted Shannon entropy and embedding baseline of the
            # raw document. Any topological anomaly detected here is caused by the
            # document itself, not by LLM edge hallucination in Stage 5.
            from ma.drift_detector import ingestion_drift_check
            drift_result = ingestion_drift_check(
                nodes=list(node_set.values()),
                edges=rels,             # regex-only edges — deterministic, confidence=1.0
                sections=sections_emb,
                doc_name=topo.filename,
            )
            _JOBS[jid]["drift"] = drift_result
            if drift_result["risk_level"] == "CRITICAL":
                _JOBS[jid]["drift_warning"] = drift_result["recommendation"]

            # ── Stage 5: LLM Extraction Enhancer ──────────────────────────
            # Second pass over sections regex missed; adds edges at confidence=0.6.
            # Runs AFTER the drift baseline is locked — LLM noise cannot pollute it.
            _JOBS[jid]["status"] = "llm_enhancing"
            from legatum.graph_store import llm_extract_entities, review_kg_types
            existing_names = set(node_set.keys())
            llm_edges = await loop.run_in_executor(
                None, llm_extract_entities, sections_emb, existing_names, 20
            )
            all_rels = rels + llm_edges
            for e in llm_edges:
                node_set.setdefault(e["source"], {"id": e["source"], "type": e.get("source_type","CONCEPT"), "page": e.get("page")})
                node_set.setdefault(e["target"], {"id": e["target"], "type": e.get("target_type","CONCEPT"), "page": e.get("page")})

            # ── Stage 6: KG Reviewer ──────────────────────────────────────
            _JOBS[jid]["status"] = "reviewing"
            corrections = await loop.run_in_executor(
                None, review_kg_types, list(node_set.values()), 30
            )

            # ── Stage 7: Persist + LLM delta measurement ──────────────────
            regex_edge_count = len(rels)
            llm_delta = (len(llm_edges) / regex_edge_count) if regex_edge_count > 0 else 0.0
            save_graph(pdf_path, topo.filename, list(node_set.values()), all_rels, sections_emb)

            # ── Stage 7.5: Episodic → Semantic Memory Consolidation ────────
            # Pass 1 + 2 (Pass 3 fires async inside if strength >= 0.75).
            # Runs in background thread so it never delays the "done" status.
            from ma.drift_detector import consolidate_memory_from_kg
            _JOBS[jid]["status"] = "consolidating_memory"
            try:
                await loop.run_in_executor(
                    None, consolidate_memory_from_kg,
                    list(node_set.values()), all_rels,
                    topo.filename, topo.filename, "default"
                )
                _JOBS[jid]["memory_consolidated"] = True
            except Exception as _mem_err:
                _JOBS[jid]["memory_consolidated"] = False
                _JOBS[jid]["memory_error"] = str(_mem_err)

            _JOBS[jid]["status"]        = "done"
            _JOBS[jid]["nodes"]         = len(node_set)
            _JOBS[jid]["edges"]         = len(all_rels)
            _JOBS[jid]["edges_regex"]   = regex_edge_count
            _JOBS[jid]["edges_llm"]     = len(llm_edges)
            _JOBS[jid]["llm_delta"]     = round(llm_delta, 3)
            _JOBS[jid]["llm_delta_warn"] = llm_delta > 0.20
            _JOBS[jid]["sections"]      = len(sections_emb)
            _JOBS[jid]["kg_corrections"] = corrections
        except Exception as ex:
            _JOBS[jid] = {**_JOBS[jid], "status": "error", "error": str(ex)}

    _asyncio.create_task(_run_extraction(job_id, str(dest)))

    return {
        "path": str(dest),
        "filename": file.filename,
        "size_bytes": dest.stat().st_size,
        "job_id": job_id,
    }


@router.get("/documents/graph-edges")
async def get_graph_edges(path: str):
    """Return saved graph edges for a PDF path — used to render KG after upload+poll."""
    from legatum.graph_store import load_graph
    g = load_graph(path)
    if not g:
        return {"edges": [], "nodes": []}
    edges = g.get("edges", [])
    nodes = g.get("nodes", [])
    # Return only what buildDocKGGraph needs: source, target, type, source_type, target_type
    return {
        "edges": [
            {
                "source":      e.get("source", ""),
                "target":      e.get("target", ""),
                "type":        e.get("type", ""),
                "source_type": e.get("source_type", "CONCEPT"),
                "target_type": e.get("target_type", "CONCEPT"),
                "method":      e.get("method", ""),
            }
            for e in edges
            if e.get("source") and e.get("target")
        ],
        "nodes": len(nodes),
    }


@router.get("/documents/job/{job_id}")
async def get_job_status(job_id: str):
    """Poll extraction job status. status: queued | extracting | embedding | done | error"""
    job = _JOBS.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job


class MultiDocRequest(BaseModel):
    pdf_paths: list[str]

@router.post("/documents/extract-multi")
async def extract_multi_pdf(req: MultiDocRequest):
    """Extract multiple PDFs and merge into a unified KG with cross-doc correlation."""
    import time
    from pathlib import Path
    from legatum.document_topography import parse_pdf_topography

    results = []
    all_rels = []
    all_headings_by_doc = {}

    for pdf_path in req.pdf_paths:
        if not Path(pdf_path).exists():
            results.append({"filename": pdf_path, "error": "not found"})
            continue
        topo = parse_pdf_topography(pdf_path)
        if not topo:
            results.append({"filename": pdf_path, "error": "unreadable"})
            continue
        doc_rels = _build_concept_kg_from_topography(topo)
        fname = topo.filename
        # Tag each rel with source document
        for r in doc_rels:
            r["doc"] = fname
        all_rels.extend(doc_rels)
        all_headings_by_doc[fname] = {r["source"] for r in doc_rels} | {r["target"] for r in doc_rels}
        results.append({"filename": fname, "pages": topo.pages, "kg_rels": len(doc_rels)})

    # Cross-document correlation: shared concept nodes
    cross_edges = []
    doc_names = list(all_headings_by_doc.keys())
    for i in range(len(doc_names)):
        for j in range(i + 1, len(doc_names)):
            shared = all_headings_by_doc[doc_names[i]] & all_headings_by_doc[doc_names[j]]
            for s in shared:
                cross_edges.append({
                    "source": s, "target": s,
                    "type": "cross_doc_match",
                    "doc_a": doc_names[i], "doc_b": doc_names[j],
                    "confidence": 1.0
                })

    return {
        "documents": results,
        "unified_kg": all_rels,
        "cross_doc_matches": cross_edges,
        "total_nodes": len({r["source"] for r in all_rels} | {r["target"] for r in all_rels}),
        "total_edges": len(all_rels),
        "cross_matches_count": len(cross_edges),
    }


@router.get("/documents/load-from-db")
async def load_from_db(doc_id: Optional[str] = None):
    """Return ingested document data from SQLite in dashboard format — no re-extraction needed."""
    import sqlite3 as _sq
    from pathlib import Path as _P
    _db = _P("/Users/mango/BlackSwanX/shared/rag/data/legatum_complete.db")
    if not _db.exists():
        return {"error": "No ingested database found"}
    _conn = _sq.connect(str(_db))
    _conn.row_factory = _sq.Row

    # Resolve doc_id
    if not doc_id:
        row = _conn.execute("SELECT doc_id, title, path, pages, summary FROM documents LIMIT 1").fetchone()
    else:
        row = _conn.execute("SELECT doc_id, title, path, pages, summary FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    if not row:
        _conn.close()
        return {"error": "No documents ingested yet"}

    _did = row["doc_id"]
    _pages = row["pages"] or 0

    # Text blocks from parent_chunks
    chunks = _conn.execute(
        "SELECT page, text, chapter FROM parent_chunks WHERE doc_id=? ORDER BY page, idx LIMIT 40",
        (_did,)
    ).fetchall()
    sample_blocks = [{"page": c["page"], "x": 0, "y": 0, "text": c["text"][:120],
                      "font_size": None, "is_bold": False} for c in chunks]
    total_text_blocks = _conn.execute(
        "SELECT count(*) FROM parent_chunks WHERE doc_id=?", (_did,)
    ).fetchone()[0]

    # Chapters
    chapters = _conn.execute(
        "SELECT title, start_page, end_page FROM chapters ORDER BY start_page"
    ).fetchall()

    # KG edges from relations (for live KG graph)
    rels_rows = _conn.execute(
        "SELECT r.source_key, r.target_key, r.type, r.description, r.confidence, "
        "COALESCE(r.page_number, 0) as page_number, "
        "e1.name as src_name, e2.name as tgt_name "
        "FROM relations r "
        "LEFT JOIN entities e1 ON e1.name_key=r.source_key "
        "LEFT JOIN entities e2 ON e2.name_key=r.target_key "
        "ORDER BY r.confidence DESC LIMIT 120"
    ).fetchall()
    kg_relationships = [
        {
            "source":      r["src_name"] or r["source_key"],
            "target":      r["tgt_name"] or r["target_key"],
            "type":        r["type"],
            "edge_type":   r["type"],
            "evidence":    r["description"] or "",
            "confidence":  round(r["confidence"] or 0.0, 2),
            "page":        r["page_number"] or 0,
        }
        for r in rels_rows
    ]

    # Entity count
    ent_count = _conn.execute("SELECT count(*) FROM entities").fetchone()[0]
    rel_count = _conn.execute("SELECT count(*) FROM relations").fetchone()[0]

    # Entities for table display
    entities = _conn.execute(
        "SELECT name, type, description, importance FROM entities ORDER BY importance DESC, name LIMIT 60"
    ).fetchall()

    _conn.close()

    # Extracted images from disk (already produced by previous fitz/extract run)
    import re as _re
    _img_dir = _P("/Users/mango/BlackSwanX/legatum/extracted_images")
    embedded_images = []
    if _img_dir.exists():
        for f in sorted(_img_dir.iterdir()):
            if f.suffix.lower() not in (".jpeg", ".jpg", ".png"):
                continue
            m = _re.match(r"page(\d+)_img(\d+)_(\d+)x(\d+)", f.stem)
            if not m:
                continue
            pnum, _, w, h = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            if w < 50 or h < 50:
                continue
            embedded_images.append({"page": pnum, "width": w, "height": h,
                                     "filename": f.name, "colorspace": "RGB"})

    # Page-level diagram structure from chapters (proxy — real diagrams need PDF parse)
    chapter_pages = []
    for ch in chapters:
        sp, ep = ch["start_page"] or 1, ch["end_page"] or 1
        chapter_pages.append({
            "page": sp,
            "boxes": min(4, (ep - sp + 1) * 2),
            "lines": min(6, (ep - sp + 1) * 3),
            "relationships": min(3, ep - sp + 1),
            "methods": [ch["title"][:40]] if ch["title"] else []
        })

    # Tables from chunks containing pipe characters
    table_chunks = [c for c in chunks if c["text"] and c["text"].count("|") >= 4]
    tables = [{"page": c["page"], "rows": [r.strip() for r in c["text"].split("\n") if "|" in r][:6],
               "content_sample": c["text"][:200]} for c in table_chunks[:8]]

    # Find the qa_pdf_path from saved graph files (may differ from DB path due to temp upload)
    _qa_pdf_path = row["path"] or ""
    _graphs_dir = _P(__file__).parent.parent.parent / "legatum" / "graphs"
    if _graphs_dir.exists():
        import json as _json
        for _gf in _graphs_dir.glob("*.json"):
            try:
                _gd = _json.loads(_gf.read_text())
                if _gd.get("filename") and _gd["filename"] in (row["title"] or ""):
                    _qa_pdf_path = _gd["pdf_path"]
                    break
            except Exception:
                pass

    return {
        "doc_id": _did,
        "title": row["title"],
        "summary": row["summary"] or "",
        "qa_pdf_path": _qa_pdf_path,
        "entities": [{"name": e["name"], "type": e["type"] or "concept",
                       "description": e["description"], "importance": e["importance"]} for e in entities],
        "topography": {
            "pages": _pages,
            "total_text_blocks": total_text_blocks,
            "stamps_detected": 0,
            "tables_detected": len(tables),
            "tables": tables,
            "sample_blocks": sample_blocks,
        },
        "diagram_analysis": {
            "total_vector_elements": ent_count,
            "total_relationships": rel_count,
            "kg_edges_generated": len(kg_relationships),
            "pages_with_structure": len(chapter_pages),
            "pages": chapter_pages,
        },
        "images": {
            "total_embedded": len(embedded_images),
            "pages_with_images": len(set(i["page"] for i in embedded_images)),
            "details": embedded_images
        },
        "kg_relationships": kg_relationships,
        "chapters": [{"title": c["title"], "start_page": c["start_page"], "end_page": c["end_page"]} for c in chapters],
    }


@router.get("/documents/extract-real")
async def extract_real_pdf(pdf_path: Optional[str] = None):
    """Run actual extraction on the real PDF in the docs/ folder."""
    import time
    from pathlib import Path
    from legatum.document_topography import parse_pdf_topography
    from legatum.diagram_analyzer import extract_diagrams_from_pdf, diagrams_to_kg_edges

    # Use uploaded path if provided, else fall back to defaults
    if not pdf_path:
        bim_path = Path("/Users/mango/Downloads/2025_Broschuere_BIM-Leitfaden_2.0_barrierefrei.pdf")
        local_path = Path(__file__).parent.parent.parent / "docs" / "BlackSwanX_MA_Platform_Overview.pdf"
        pdf_path = str(bim_path if bim_path.exists() else local_path)

    if not Path(pdf_path).exists():
        return {"error": f"PDF not found: {pdf_path}"}

    # Extract and save embedded images to disk
    import fitz as _fitz
    _img_dir = Path(__file__).parent.parent.parent / "legatum" / "extracted_images"
    _img_dir.mkdir(exist_ok=True)
    _doc = _fitz.open(pdf_path)
    embedded_images = []
    for _pnum, _page in enumerate(_doc):
        for _per_page_idx, _img in enumerate(_page.get_images(full=True)):
            _xref = _img[0]
            _w, _h = _img[2], _img[3]
            if _w < 20 or _h < 20:
                continue  # skip tiny icons
            _ext = "png" if _img[5] in ("Indexed", "DeviceGray") else "jpeg"
            _fname = f"page{_pnum:02d}_img{_per_page_idx}_{_w}x{_h}.{_ext}"
            _dest = _img_dir / _fname
            if not _dest.exists():
                try:
                    _pix = _fitz.Pixmap(_doc, _xref)
                    if _pix.n > 4:
                        _pix = _fitz.Pixmap(_fitz.csRGB, _pix)
                    _pix.save(str(_dest))
                except Exception:
                    pass
            embedded_images.append({
                "page": _pnum,
                "width": _w,
                "height": _h,
                "colorspace": _img[5],
                "name": _img[7],
                "xref": _xref,
                "filename": _fname,
            })
    _doc.close()

    start = time.time()

    # Topography
    topo = parse_pdf_topography(pdf_path)
    if not topo:
        return {"error": "PyMuPDF not available or PDF unreadable"}

    # Sample text blocks (first 30, sorted by page/y)
    sample_blocks = []
    for b in sorted(topo.blocks, key=lambda x: (x.page, x.y0))[:30]:
        sample_blocks.append({
            "page": b.page,
            "x": round(b.x0, 1),
            "y": round(b.y0, 1),
            "text": b.text[:120],
            "font_size": round(b.font_size, 1) if b.font_size else None,
            "is_bold": b.is_bold,
        })

    # Diagram analysis
    diagrams = extract_diagrams_from_pdf(pdf_path)
    edges = diagrams_to_kg_edges(diagrams)

    # Per-page summary
    pages_summary = []
    for d in diagrams:
        boxes = [e for e in d.elements if e.element_type == "box"]
        lines = [e for e in d.elements if e.element_type == "line"]
        pages_summary.append({
            "page": d.page,
            "boxes": len(boxes),
            "lines": len(lines),
            "relationships": len(d.relationships),
            "methods": d.extraction_methods_used,
        })

    # Build a meaningful KG from document heading hierarchy (not noisy vector boxes)
    # Spatial/vector rels are dominated by box_N → one big labeled container — not useful for CEO graph
    sample_rels = _build_concept_kg_from_topography(topo)
    named_rels = [r for r in sample_rels if not r["source"].startswith("box_") and not r["target"].startswith("box_")]

    # Colored elements
    colored_nodes = [e for e in edges if "node" in e and e.get("properties", {}).get("color")]

    elapsed = round(time.time() - start, 3)

    return {
        "filename": topo.filename,
        "processing_time_sec": elapsed,
        "topography": {
            "pages": topo.pages,
            "total_text_blocks": len(topo.blocks),
            "stamps_detected": len(topo.detected_stamps),
            "tables_detected": len(topo.detected_tables),
            "document_hash": topo.document_hash[:20] + "...",
            "stamps": topo.detected_stamps,
            "tables": topo.detected_tables,
            "sample_blocks": sample_blocks,
        },
        "diagram_analysis": {
            "pages_with_structure": len(diagrams),
            "total_vector_elements": sum(len(d.elements) for d in diagrams),
            "total_relationships": sum(len(d.relationships) for d in diagrams),
            "kg_edges_generated": len(edges),
            "colored_nodes": len(colored_nodes),
            "pages": pages_summary,
        },
        "kg_relationships": sample_rels,
        "named_relationships_count": len(named_rels),
        "images": {
            "total_embedded": len(embedded_images),
            "pages_with_images": len(set(i["page"] for i in embedded_images)),
            "details": embedded_images,
            "extracted_files": [i["filename"] for i in embedded_images],
        },
        "cloud_cost": "$0",
    }

    # ── Persist graph + embed sections after extraction ───────────────────────
    try:
        from legatum.graph_store import save_graph, embed_sections
        # Build sections for embedding
        context_chunks_for_store = []
        for b in sorted(topo.blocks, key=lambda x: (x.page, x.y0)):
            txt = b.text.strip()
            if len(txt) < 10:
                continue
            context_chunks_for_store.append({
                "doc": topo.filename,
                "page": b.page + 1,
                "text": txt,
                "is_heading": b.is_bold or (b.font_size and b.font_size > 12),
            })
        sections_for_store = []
        current = {"heading": "", "doc": topo.filename, "page": 1, "blocks": []}
        for c in context_chunks_for_store:
            if c["is_heading"]:
                if current["blocks"] or current["heading"]:
                    sections_for_store.append(current)
                current = {"heading": c["text"], "doc": c["doc"], "page": c["page"], "blocks": []}
            else:
                current["blocks"].append(c["text"])
        if current["blocks"] or current["heading"]:
            sections_for_store.append(current)
        # Embed sections (async-safe: runs in threadpool via asyncio would be ideal,
        # but for local prototype synchronous is fine — Ollama is local)
        import asyncio
        loop = asyncio.get_event_loop()
        sections_embedded = await loop.run_in_executor(None, embed_sections, sections_for_store)
        # Build node list from edges
        node_set = {}
        for r in sample_rels:
            node_set[r["source"]] = {"id": r["source"], "type": r.get("source_type","CONCEPT"), "page": r.get("page")}
            node_set[r["target"]] = {"id": r["target"], "type": r.get("target_type","CONCEPT"), "page": r.get("page")}
        save_graph(pdf_path, topo.filename, list(node_set.values()), sample_rels, sections_embedded)
    except Exception as _e:
        pass  # never block extraction response over store failure


class DocSuggestRequest(BaseModel):
    pdf_paths: list[str]

@router.post("/documents/suggest-questions")
async def suggest_questions(req: DocSuggestRequest):
    """Generate smart questions a construction-tech company would ask about these docs."""
    from legatum.document_topography import parse_pdf_topography
    import httpx

    headings = []
    filenames = []
    for pdf_path in req.pdf_paths:
        if not Path(pdf_path).exists():
            continue
        topo = parse_pdf_topography(pdf_path)
        if not topo:
            continue
        filenames.append(topo.filename)
        for b in sorted(topo.blocks, key=lambda b: (b.page, b.y0)):
            if b.is_bold or (b.font_size and b.font_size > 11):
                txt = b.text.strip()
                if 5 < len(txt) < 80:
                    headings.append(txt)
            if len(headings) >= 80:
                break

    if not headings:
        return {"questions": []}

    heading_sample = "\n".join(headings[:60])
    prompt = f"""You are an AI assistant for LEGATUM, a construction intelligence platform that helps companies manage BIM projects, contracts, and document compliance.

A user has uploaded these documents: {', '.join(filenames)}

Key topics found in the documents:
{heading_sample}

Generate exactly 6 short, specific questions that a project manager or BIM coordinator at a construction company would genuinely want answered from these documents.
- Make them practical and specific to the document content
- Focus on: roles/responsibilities, processes, compliance requirements, tools, definitions, deliverables
- Each question max 12 words
- Return ONLY a JSON array of 6 strings, nothing else. Example: ["Question 1?", "Question 2?"]"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3.2:3b", "prompt": prompt, "stream": False}
            )
            raw = resp.json().get("response", "").strip()
            import re, json as _json
            match = re.search(r'\[.*?\]', raw, re.DOTALL)
            questions = _json.loads(match.group()) if match else []
            questions = [q for q in questions if isinstance(q, str)][:6]
    except Exception:
        questions = []

    return {"questions": questions}


class DocQARequest(BaseModel):
    question: str
    pdf_paths: list[str]
    adversarial: bool = False
    panel: bool = False
    verify: bool = False
    generator_model: str = ""   # overrides QA_GENERATOR_MODEL env if set


@router.post("/documents/qa")
async def doc_qa(req: DocQARequest):
    """
    Answer a question from uploaded PDFs.
    Pipeline:
      1. Load persisted graph+sections (built at extraction time)
      2. Semantic search via embeddings (falls back to BM25 token overlap)
      3. GraphRAG — inject KG edges into each retrieved section
      4. Generator LLM (llama3.2:3b) drafts answer
      5. Graph Validator — deterministic CONSTRAINT cross-check → Ampel
      6. [Optional] Adversarial Layer 2 — second local model critiques draft
    """
    from legatum.graph_store import (
        load_graph, semantic_search,
        find_constraints_for_process, find_responsible_roles,
        validate_claims_against_index,
    )
    import httpx, re as _re, asyncio

    if not req.pdf_paths:
        return {"answer": "No documents loaded.", "sources": []}

    # ── Step 1: Load persisted graphs ──────────────────────────────────────
    all_sections: list[dict] = []
    all_kg_rels:  list[dict] = []
    all_constraint_index: dict = {}   # merged pre-built index from all docs
    missing_docs: list[str]  = []
    sections_by_doc: dict = {}        # for Truth Gap cross-doc scan

    for pdf_path in req.pdf_paths:
        g = load_graph(pdf_path)
        if g:
            secs = g.get("sections", [])
            all_sections.extend(secs)
            all_kg_rels.extend(g.get("edges", []))
            for k, v in g.get("constraint_index", {}).items():
                all_constraint_index.setdefault(k, []).extend(v)
            fname = g.get("filename", pdf_path)
            sections_by_doc[fname] = secs
        else:
            missing_docs.append(pdf_path)

    # Fallback: graph not yet saved — build on-the-fly with hierarchical chunking
    if missing_docs:
        from legatum.document_topography import parse_pdf_topography
        from legatum.graph_store import save_graph, embed_sections
        for pdf_path in missing_docs:
            if not Path(pdf_path).exists():
                continue
            topo = parse_pdf_topography(pdf_path)
            if not topo:
                continue
            fname = topo.filename
            raw_blocks = sorted(topo.blocks, key=lambda x: (x.page, x.y0))

            # Hierarchical chunking — same logic as upload extraction
            _fb_heading_sizes = sorted(
                {b.font_size for b in raw_blocks
                 if b.font_size and (b.is_bold or b.font_size > 12)
                 and len(b.text.strip()) >= 4},
                reverse=True
            )
            _fb_size_to_level: dict[float, int] = {}
            for _rank, _fs in enumerate(_fb_heading_sizes[:4]):
                _fb_size_to_level[_fs] = _rank + 1

            def _fb_heading_level(block) -> int | None:
                txt = block.text.strip()
                if len(txt) < 4:
                    return None
                fs = block.font_size or 0
                if fs > 12:
                    return _fb_size_to_level.get(fs, 4)
                if block.is_bold and fs in _fb_size_to_level:
                    return _fb_size_to_level[fs]
                if block.is_bold and len(txt) <= 80 and (txt.endswith(":") or txt.endswith("：")):
                    return 4
                return None

            _fb_hstack: list[str] = []
            _fb_hlevels: list[int] = []
            _fb_sections: list[dict] = []
            _fb_cur: dict = {"heading": "", "doc": fname, "page": 1, "blocks": [], "breadcrumb": fname}

            def _fb_flush(cur: dict) -> None:
                body = "\n".join(cur["blocks"]).strip()
                if not body and not cur["heading"]:
                    return
                crumb = cur.get("breadcrumb", "")
                cur["text"] = (f"[{crumb}]\n{body}" if crumb else body) if body else f"[{crumb}]"
                _fb_sections.append(cur)

            for b in raw_blocks:
                txt = b.text.strip()
                if len(txt) < 10:
                    continue
                lvl = _fb_heading_level(b)
                if lvl is not None:
                    _fb_flush(_fb_cur)
                    while _fb_hlevels and _fb_hlevels[-1] >= lvl:
                        _fb_hstack.pop(); _fb_hlevels.pop()
                    _fb_hstack.append(txt); _fb_hlevels.append(lvl)
                    crumb = " → ".join([fname] + _fb_hstack)
                    _fb_cur = {"heading": txt, "doc": fname, "page": b.page + 1, "blocks": [], "breadcrumb": crumb}
                else:
                    _fb_cur["blocks"].append(txt)
            _fb_flush(_fb_cur)

            _fb_rels = _build_concept_kg_from_topography(topo)
            all_kg_rels.extend(_fb_rels)
            # Build nodes from edges so graph visualization has typed colored dots
            _fb_node_set: dict = {}
            for _r in _fb_rels:
                _fb_node_set[_r["source"]] = {"id": _r["source"], "type": _r.get("source_type", "CONCEPT"), "page": _r.get("page", 1)}
                _fb_node_set[_r["target"]] = {"id": _r["target"], "type": _r.get("target_type", "CONCEPT"), "page": _r.get("page", 1)}
            _fb_nodes = list(_fb_node_set.values())
            # Use sections without embeddings for this request (BM25 still works).
            # Fire background task to embed + persist so next call gets semantic search.
            _fb_plain = [{**s, "embedding": None} for s in _fb_sections]
            all_sections.extend(_fb_plain)

            async def _embed_and_save(_pdf=pdf_path, _fname=fname, _secs=_fb_sections,
                                       _rels=_fb_rels, _nodes=_fb_nodes):
                try:
                    _emb = await loop.run_in_executor(None, embed_sections, _secs)
                    save_graph(_pdf, _fname, _nodes, _rels, _emb)
                except Exception:
                    pass
            asyncio.ensure_future(_embed_and_save())

    if not all_sections:
        return {"answer": "Could not load document content. Please re-extract the PDFs.", "sources": []}

    # ── Step 2: Semantic retrieval ─────────────────────────────────────────
    # Retrieve more candidates when a large-context model is available.
    _req_model = req.generator_model or __import__('os').getenv("QA_GENERATOR_MODEL", "llama3.2:3b")
    _retrieval_k = 40 if any(m in _req_model for m in ("mistral-small", "phi4", "24b", "14b")) else 20
    loop = asyncio.get_event_loop()
    top_sections = await loop.run_in_executor(
        None, semantic_search, req.question, all_sections, _retrieval_k
    )

    # ── Step 2.5: Mandatory broad-context injection ────────────────────────
    # Definition/Zweck questions need the document intro (p.1-5) which is
    # strategic overview text — often ranked low by reranker because it lacks
    # specific keyword matches, but contains the "expected" strategic answer.
    import re as _re2
    _DEFN_PATTERNS = _re2.compile(
        r'\b(was ist|was sind|was bedeutet|Zweck|Ziel|Bedeutung|Definition|'
        r'wofür|wozu|erkläre|beschreibe|überblick|einführung|zusammenfassung|'
        r'what is|what are|purpose|definition|overview|explain|describe|'
        r'wer kann|wer darf|für wen|zielgruppe|nutzer|nutzen|außerhalb|'
        r'wer ist berechtigt|wer hat zugang)\b',
        _re2.I
    )
    _OVERVIEW_HEADINGS = _re2.compile(
        r'\b(Einführung|Einleitung|Überblick|Vorwort|Zweck|Ziel|'
        r'Grundsätze|Grundlagen|Einführende|Allgemein|Introduction|Overview|'
        r'Kurzdarstellung|Verteilerhinweis|Zielgruppe|Hinweis)\b',
        _re2.I
    )
    is_definition_question = bool(_DEFN_PATTERNS.search(req.question))
    _audience_q = bool(_re2.search(r'\b(wer kann|wer darf|für wen|nutzen|außerhalb|zielgruppe|berechtigt|zugang|verteiler)\b', req.question, _re2.I))
    top_section_ids = {(s.get("doc"), s.get("page")) for s in top_sections}

    # Always pin the first 3 pages of each document as mandatory context
    mandatory: list[dict] = []
    for sec in all_sections:
        key = (sec.get("doc"), sec.get("page"))
        if key in top_section_ids:
            continue  # already in reranked set
        page = sec.get("page", 99)
        heading = sec.get("heading", "")
        if page <= 5 or (is_definition_question and _OVERVIEW_HEADINGS.search(heading)):
            mandatory.append(sec)

    # Deduplicate mandatory by (doc, page), keep longest section per page
    best_mandatory: dict = {}
    for sec in mandatory:
        k = (sec.get("doc"), sec.get("page"))
        if k not in best_mandatory or len(sec.get("text", "")) > len(best_mandatory[k].get("text", "")):
            best_mandatory[k] = sec
    deduped_mandatory: list[dict] = list(best_mandatory.values())

    # Prepend mandatory sections so they are included BEFORE reranker hits in
    # the greedy budget slicer. They get a synthetic rerank_pos of -1 so they
    # appear first in the sources panel too.
    for sec in deduped_mandatory:
        sec["_mandatory"] = True
    top_sections = deduped_mandatory + top_sections

    # For audience/access questions, also pull any Kurzdarstellung/Verteilerhinweis
    # sections from anywhere in the doc — they contain the distribution scope text.
    if _audience_q:
        _scope_headings = _re2.compile(r'\b(Kurzdarstellung|Verteilerhinweis|Zielgruppe|außerhalb|Partner)\b', _re2.I)
        _pinned_ids = {(s.get("doc"), s.get("page")) for s in top_sections}
        _scope_secs = [s for s in all_sections
                       if (s.get("doc"), s.get("page")) not in _pinned_ids
                       and _scope_headings.search(s.get("heading","") + " " + s.get("text","")[:200])]
        for s in _scope_secs:
            s["_mandatory"] = True
        top_sections = _scope_secs + top_sections

    # ── Step 2.6: Institutional Memory Retrieval ───────────────────────────
    # Query the semantic memory store for cross-project knowledge relevant to
    # this question. Memories with strength >= 0.4 are included in GLOBAL CONTEXT.
    _institutional_memories: list[dict] = []
    _agentic_instructions: dict[str, list[str]] = {}
    try:
        from ma.drift_detector import search_semantic_memory, _embed_text_for_memory, get_agentic_instructions
        _q_embedding = await loop.run_in_executor(None, _embed_text_for_memory, req.question)
        if _q_embedding:
            _institutional_memories = await loop.run_in_executor(
                None, search_semantic_memory, _q_embedding, 0.4, 3, "default"
            )
        # Collect entity names from this document's KG for agentic instruction lookup
        _doc_entities = list({r.get("source", "") for r in all_kg_rels}
                              | {r.get("target", "") for r in all_kg_rels})
        _doc_entities = [e for e in _doc_entities if len(e) >= 3][:60]
        if _doc_entities and (req.adversarial or req.panel):
            for _role in ("assassin", "defender", "judge", "expert", "moderator"):
                _instrs = await loop.run_in_executor(
                    None, get_agentic_instructions, _doc_entities, _role
                )
                if _instrs:
                    _agentic_instructions[_role] = _instrs
    except Exception:
        pass

    # ── Step 3: GraphRAG — inject edges, then slice to token budget ────────
    # Model selection: env QA_GENERATOR_MODEL overrides default.
    # mistral-small:24b has 32k context and is available locally → use it.
    # llama3.2:3b is the fast fallback for low-RAM environments.
    import os as _os
    _GEN_MODEL = req.generator_model or _os.getenv("QA_GENERATOR_MODEL", "llama3.2:3b")

    # Context budgets by model family:
    #   mistral-small:24b  → 32768 token ctx, ~3 chars/token → ~98k chars available
    #   phi4:14b           → 16384 token ctx                 → ~49k chars
    #   llama3.2:3b        → 4096 token ctx                  → ~12k chars
    # Conservative: reserve 2k tokens for prompt overhead + 1k for answer.
    # Cap context to ~3000 tokens (~9000 chars) per model regardless of max ctx.
    # Large context windows make Ollama prefill take minutes on Mac CPU.
    # This keeps first-token latency under 30s even for 24B models.
    _MODEL_CTX = {
        "mistral-small:24b": 3000,
        "phi4:14b":          3000,
        "qwen2.5-coder:7b":  2500,
        "llama3.2:3b":       3000,
    }
    _ctx_tokens = _MODEL_CTX.get(_GEN_MODEL, 2500)
    _PROMPT_OVERHEAD_CHARS = 800
    _ANSWER_RESERVE_CHARS  = 600
    _CONTEXT_BUDGET        = (_ctx_tokens * 3) - _PROMPT_OVERHEAD_CHARS - _ANSWER_RESERVE_CHARS

    def _section_graph_facts(section: dict) -> list[str]:
        combined = section.get("text", "").lower()
        facts = []
        for r in all_kg_rels:
            if r["source"].lower() in combined or r["target"].lower() in combined:
                src_t = r.get("source_type", "")
                tgt_t = r.get("target_type", "")
                label = f" [{src_t}->{tgt_t}]" if src_t else ""
                facts.append(f"({r['source']})-[{r['type']}]->({r['target']}){label}")
        return facts[:6]

    def _graph_context_for_question(question: str) -> str:
        q_l = question.lower()
        lines = []
        for edge in all_kg_rels:
            if edge.get("source_type") == "PROCESS" and edge.get("source", "").lower() in q_l:
                for c in find_constraints_for_process(all_kg_rels, edge["source"])[:3]:
                    lines.append(f"GRAPH: ({c['source']})-[{c['type']}]->({c['target']})")
            if edge.get("type") == "RESPONSIBLE_FOR" and edge.get("target", "").lower() in q_l:
                lines.append(f"GRAPH: ({edge['source']})-[RESPONSIBLE_FOR]->({edge['target']})")
        return "\n".join(lines[:8])

    # Identify figure/diagram pages among retrieved sections — no real text was extracted.
    _MIN_REAL_CHARS = 30
    _figure_pages: list[tuple[str, int]] = []
    for s in top_sections:
        s_text = (s.get("text", "") or "").strip()
        if len(s_text) < _MIN_REAL_CHARS:
            _figure_pages.append((s.get("doc", ""), s.get("page", 0)))

    # Build section strings with edges injected, separating mandatory (global) from reranked (local).
    global_parts: list[str] = []   # p.1-3 / overview sections → GLOBAL CONTEXT
    local_parts:  list[str] = []   # reranker hits            → LOCAL CONTEXT
    import re as _re_ctx
    _embedded_header_re = _re_ctx.compile(r'^\[.*?\]\n', _re_ctx.DOTALL)
    for s in top_sections:
        s_text = (s.get("text", "") or "").strip()
        # Strip embedded path-header at start of text (e.g. "[doc → heading]\n")
        s_text = _embedded_header_re.sub("", s_text, count=1)
        if len(s_text) < _MIN_REAL_CHARS:
            continue  # skip figure pages from context — they add noise with no signal
        text_part = f"[{s.get('doc','')} p.{s.get('page','')}] {s.get('heading','')}\n{s_text}"
        facts = _section_graph_facts(s)
        if facts:
            text_part += "\nKG Facts: " + " | ".join(facts)
        if s.get("_mandatory"):
            global_parts.append(text_part)
        else:
            local_parts.append(text_part)

    graph_ctx = _graph_context_for_question(req.question)
    graph_ctx_chars = len(graph_ctx) + 2 if graph_ctx else 0
    remaining = _CONTEXT_BUDGET - graph_ctx_chars

    # Greedy include respecting global/local order within budget.
    included_global: list[str] = []
    included_local:  list[str] = []
    sections_included = 0
    for part in global_parts + local_parts:
        part_len = len(part) + 2
        if part_len <= remaining:
            (included_global if part in global_parts else included_local).append(part)
            remaining -= part_len
            sections_included += 1

    # ── Compact Context Compiler ───────────────────────────────────────────
    # Pre-digest all tiers into ONE cohesive narrative in Python before sending
    # to the LLM. This removes architectural overhead from the model's attention
    # mechanism — critical for 3B models that drop "middle" tiers.
    # Structure: Core Principles → Known Variances → Current Document Excerpts
    context_parts: list[str] = []

    if _institutional_memories:
        core_lines: list[str] = []
        for m in _institutional_memories:
            truth = m.get("display_truth", "")
            if not truth:
                continue
            # Unpack episodic refs as known specific applications
            import json as _json2
            try:
                refs = _json2.loads(m.get("episodic_refs") or "[]")
            except Exception:
                refs = []
            block = f"CORE PRINCIPLE — {m['entity']} [{m['entity_type']}]: {truth}"
            if refs:
                block += "\nKnown specific applications:"
                for ref in refs[-3:]:  # last 3 to stay compact
                    snip = ref.get("snippet", "")[:120]
                    block += f"\n  • In '{ref.get('doc','')}' p.{ref.get('page','')}: {snip}"
            core_lines.append(block)
        if core_lines:
            context_parts.append(
                "ESTABLISHED KNOWLEDGE (verified across multiple documents):\n" +
                "\n\n".join(core_lines)
            )

    if graph_ctx:
        context_parts.append(graph_ctx)

    if included_global:
        context_parts.append(
            "DOCUMENT OVERVIEW (scope and definitions):\n" +
            "\n\n".join(included_global)
        )

    if included_local:
        context_parts.append(
            "MATCHED DOCUMENT SECTIONS (use for specific details and citations):\n" +
            "\n\n".join(included_local)
        )

    # Warn about figure/diagram pages that appeared in retrieval but have no extractable text.
    # This prevents the model from hallucinating content from visual pages.
    if _figure_pages:
        fig_refs = ", ".join(
            f"'{doc}' S.{pg}" for doc, pg in _figure_pages[:5]
        )
        context_parts.append(
            f"⚠️ HINWEIS ABBILDUNGSSEITEN: Die folgenden Seiten sind Abbildungen/Diagramme — "
            f"kein Text konnte extrahiert werden: {fig_refs}. "
            f"Falls die Antwort auf Informationen aus diesen visuellen Seiten angewiesen ist, "
            f"weise explizit darauf hin, dass die Abbildung nicht als Text vorliegt und "
            f"das Ergebnis aus dem Kontext benachbarter Seiten abgeleitet wurde."
        )

    context_text = "\n\n".join(context_parts)

    # top_sections is narrowed to only what was actually included, for downstream use
    top_sections = top_sections[:sections_included]

    # ── Step 4: Generator LLM ──────────────────────────────────────────────
    # Instruction hint for definition questions — tells model to lead with principle, not detail
    _defn_hint = (
        " Priorisiere MATCHED SECTIONS aus den Dokumenten für deine Antwort."
        " Nenne die genaue Textstelle und Seitenzahl."
        " Nutze ESTABLISHED KNOWLEDGE nur als Ergänzung, nicht als Hauptquelle."
    ) if _audience_q else (
        " Lead with the general principle from ESTABLISHED KNOWLEDGE or DOCUMENT OVERVIEW."
        " Mention specific applications only as examples after the definition."
    ) if is_definition_question else ""

    # Coverage gate: if retrieval found nothing useful, return "not found" without calling LLM.
    # Signal: all top sections are figure pages OR context is nearly empty.
    _context_useful = bool(included_global or included_local)
    _all_figures = bool(_figure_pages) and not _context_useful
    if _all_figures or not _context_useful:
        return {
            "answer": (
                "Die gesuchte Information konnte in den verfügbaren Dokumenten nicht gefunden werden. "
                "Bitte stellen Sie die Frage mit anderen Begriffen oder laden Sie das relevante Dokument hoch."
            ),
            "sources": [],
            "ampel": "red",
            "method": "no_context",
        }

    gen_prompt = f"""Du bist ein Dokumenten-Analysesystem für LEGATUM, eine deutsche Bau-Intelligence-Plattform.

STRIKTE REGELN:
1. Antworte AUSSCHLIESSLICH auf Basis des unten stehenden Kontexts.
2. Wenn die Antwort sich NICHT aus den bereitgestellten Kontextabschnitten ableiten lässt, antworte GENAU SO:
   "Diese Information ist nicht in den verfügbaren Dokumenten enthalten."
3. Wenn die Antwort im Kontext enthalten ist (auch verteilt über mehrere Abschnitte), fasse die relevanten Informationen zusammen.
4. Erfinde KEINE Informationen. Kein Allgemeinwissen, das nicht im Kontext steht.
5. Zitiere Seitenzahl wenn du eine Textstelle verwendest.
6. Antworte auf Deutsch.{_defn_hint}

KONTEXT:
{context_text}

FRAGE: {req.question}

ANTWORT (aus dem Kontext ableiten; falls nicht vorhanden: "nicht in den Dokumenten enthalten"):"""

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": _GEN_MODEL, "prompt": gen_prompt, "stream": False,
                      "options": {"num_predict": 768, "temperature": 0.05}},
            )
            answer = resp.json().get("response", "").strip()
    except Exception as e:
        return {"answer": f"LLM unavailable: {e}", "sources": []}

    # ── Step 5: Graph Validator — O(1) dict lookup, pre-built at extraction ──
    # all_constraint_index was loaded from disk above, never recomputed per query
    if all_constraint_index:
        ampel, ampel_reason, contradictions, unverified = validate_claims_against_index(
            answer, all_constraint_index
        )
    else:
        # No graph saved yet (fallback path) — skip validation
        ampel, ampel_reason, contradictions, unverified = "yellow", "Graph not yet indexed — re-extract documents.", [], []

    # Pre-compute truth gaps here so the consensus fail-safe path can include them
    truth_gaps: dict | None = None
    if len(sections_by_doc) >= 2:
        from ma.construction_screener import truth_gap_scan
        truth_gaps = truth_gap_scan(sections_by_doc)

    # ── Step 5.5: Consensus Verification (BGE-M3 cross-similarity matrix) ─────
    # Fires N isolated inferences, vectorizes outputs via BGE-M3, computes S_ij.
    # If mean off-diagonal < 0.40 → irreconcilable divergence → force RED,
    # drop synthesized answer, return raw source markdown directly.
    consensus_result: dict | None = None
    if req.verify:
        from ma.consensus_verifier import run_consensus_verification
        consensus_result = await loop.run_in_executor(
            None, run_consensus_verification, req.question, context_text, top_sections
        )
        if consensus_result.get("force_red"):
            # Synthesized payload dropped — return fail-safe immediately
            return {
                "answer": None,
                "sources": sources[:8],
                "ampel": "red",
                "ampel_reason": (
                    f"Consensus Verification Fail-Safe: mean S_ij = "
                    f"{consensus_result['mean_consensus']:.3f} < 0.40 — "
                    f"irreconcilable semantic divergence across {consensus_result['n_valid']} agents. "
                    f"Synthesized answer dropped. Raw source excerpts returned."
                ),
                "contradictions": contradictions,
                "unverified_claims": list(unverified),
                "retrieval_method": (
                    "rrf+reranker" if any(s.get("embedding") for s in top_sections) else "rrf+bm25"
                ),
                "critic": None,
                "truth_gaps": truth_gaps if len(sections_by_doc) >= 2 else None,
                "drift": None,
                "consensus": consensus_result,
            }

    # ── Step 6: Adversarial Layer — Jury (3-agent) or Panel (6-expert) ───
    critic_output: dict | None = None

    if req.panel:
        try:
            from ma.construction_panel import convene_panel
            import functools
            pv = await loop.run_in_executor(
                None,
                functools.partial(
                    convene_panel,
                    question=req.question,
                    draft_answer=answer,
                    context=context_text[:6000],
                    model=_GEN_MODEL,
                    institutional_memories=_institutional_memories or [],
                    agentic_instructions=_agentic_instructions or {}
                )
            )
            # Serialize expert opinions — ExpertOpinion dataclasses → dicts
            experts_serialized = {}
            for eid, op in (pv.expert_opinions or {}).items():
                if op is None:
                    continue
                experts_serialized[eid] = {
                    "name": op.expert_name, "icon": op.icon,
                    "opinion": op.opinion,
                    "reasoning_chain": op.reasoning_chain,
                    "confidence": op.confidence,
                    "evidence_quotes": op.evidence_quotes,
                    "memory_refs": op.memory_refs,
                    "flags": op.flags,
                }
            critic_output = {
                "mode": "panel",
                "model": _GEN_MODEL,
                "verdict": pv.verdict,
                "key_finding": pv.key_finding,
                "reasoning": pv.reasoning,
                "corrections": pv.corrections,
                "confirmed_points": pv.confirmed_points,
                "conflicts": pv.conflicts,
                "memory_impact": pv.memory_impact,
                "confidence": pv.confidence,
                "jury_ampel": pv.ampel,
                "experts": experts_serialized,
            }
            if pv.ampel == "red" and ampel != "red":
                ampel = "red"
                ampel_reason = f"Panel override: {pv.key_finding}"
            elif pv.ampel == "yellow" and ampel == "green":
                ampel = "yellow"
                ampel_reason = f"Panel unsicher: {pv.key_finding}"
        except Exception as _pe:
            critic_output = {"mode": "panel", "error": str(_pe)[:200]}

    elif req.adversarial:
        try:
            from ma.construction_jury import deliberate
            import functools
            verdict = await loop.run_in_executor(
                None,
                functools.partial(
                    deliberate,
                    question=req.question,
                    answer=answer,
                    context=context_text[:6000],
                    model=_GEN_MODEL,
                    institutional_memories=_institutional_memories or [],
                    agentic_instructions=_agentic_instructions or {}
                )
            )
            critic_output = {
                "mode": "jury",
                "model": _GEN_MODEL,
                "assassin": verdict.assassin,
                "assassin_reasoning": verdict.assassin_reasoning,
                "assassin_flags": verdict.assassin_flags,
                "defender": verdict.defender,
                "defender_reasoning": verdict.defender_reasoning,
                "defender_evidence": verdict.defender_evidence,
                "critique": verdict.judge,
                "judge_reasoning": verdict.judge_reasoning,
                "memory_impact": verdict.memory_impact,
                "confirmed": verdict.confirmed,
                "confidence": verdict.confidence,
                "jury_ampel": verdict.ampel,
            }
            if verdict.ampel == "red" and ampel != "red":
                ampel = "red"
                ampel_reason = f"Jury override: {verdict.judge}"
        except Exception as _je:
            # Jury unavailable — fall back to single critic
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    for critic_model in ["phi4:14b", "qwen2.5-coder:7b", "llama3.2:3b"]:
                        try:
                            cr = await client.post(
                                "http://localhost:11434/api/generate",
                                json={"model": critic_model,
                                      "prompt": f"Prüfe diese Antwort auf Fehler:\n{answer}\n\nKontext:\n{context_text[:3000]}",
                                      "stream": False, "options": {"temperature": 0.3}},
                                timeout=60,
                            )
                            cr.raise_for_status()
                            critic_output = {"model": critic_model,
                                             "critique": cr.json().get("response","").strip(),
                                             "confirmed": False}
                            break
                        except Exception:
                            continue
            except Exception:
                pass

    # Sources: build index from ALL sections (not just top_sections) so any
    # page cited by the LLM can be resolved — keep the richest section per page
    # (longest text wins, so a heading+body section beats a bare heading).
    _section_index: dict[tuple, dict] = {}
    for sec in all_sections:
        key = (sec.get("doc", ""), sec.get("page", 0))
        sec_text = sec.get("text", "") or " ".join(sec.get("blocks", []))
        existing = _section_index.get(key)
        existing_text = (existing.get("text", "") or " ".join(existing.get("blocks", []))) if existing else ""
        if not existing or len(sec_text) > len(existing_text):
            _section_index[key] = sec

    # Also index top_sections by their reranker rank so we can surface them first.
    # Mandatory intro sections get pos=-1 so they appear before reranker hits in the sources panel.
    _top_keys: dict[tuple, int] = {}
    mandatory_offset = len(deduped_mandatory)
    for i, s in enumerate(top_sections):
        pos = (i - mandatory_offset) if s.get("_mandatory") else i
        _top_keys[(s.get("doc",""), s.get("page",0))] = pos

    def _make_source(doc: str, page: int) -> dict:
        key = (doc, page)
        sec = _section_index.get(key, {})
        sec_text = (sec.get("text", "") or " ".join(sec.get("blocks", []))).strip()

        # Detect origin type
        _origin = "section"
        if sec.get("block_type") == "table" or sec.get("is_table"):
            _origin = "table"
        elif sec.get("block_type") == "image" or sec.get("image_url") or sec.get("is_image"):
            _origin = "image"
        elif sec.get("block_type") in ("stamp", "signature"):
            _origin = sec.get("block_type", "section")

        # Trivial extraction artifacts (page numbers, single words, figure labels)
        # must NOT count as real content — they mislead the LLM.
        _MIN_CONTENT_CHARS = 30
        if len(sec_text) < _MIN_CONTENT_CHARS:
            sec_text = ""

        # If no real text → figure/diagram page.
        # For pages NOT in index at all, also mark as image.
        if not sec_text:
            _origin = "image"
            # Only use adjacent page context as a HINT in the snippet label, not as content.
            # We keep no_text=True so the UI shows the diagram notice.
            adj = _section_index.get((doc, page - 1), {}) or _section_index.get((doc, page + 1), {})
            adj_text = (adj.get("text", "") or " ".join(adj.get("blocks", []))).strip()
            if len(adj_text) >= _MIN_CONTENT_CHARS:
                adj_page = page - 1 if (doc, page - 1) in _section_index else page + 1
                sec_text = f"[Umgebungskontext aus S.{adj_page}] {adj_text[:300]}"

        heading = sec.get("heading", "") or f"Page {page}"

        # Strip breadcrumb prefix from display snippet — heading already shows it.
        # Format set by hierarchical chunker: "[breadcrumb]\nbody text"
        sec_text_display = sec_text
        if sec_text_display.startswith("[") and "]\n" in sec_text_display:
            _, _, sec_text_display = sec_text_display.partition("]\n")

        # Figure-page flag: true when the page itself has no real text content.
        # Adjacent surrogate text counts as no_text=True to keep UI honest.
        _is_figure_page = (_origin == "image" or not (sec.get("text", "") or "").strip()
                           or len((sec.get("text", "") or "").strip()) < _MIN_CONTENT_CHARS)

        return {
            "doc": doc,
            "page": page,
            "heading": heading,
            "snippet": sec_text_display[:600] if not _is_figure_page else "",
            "method": sec.get("method", ""),
            "origin_type": _origin,
            "image_url": sec.get("image_url", ""),
            "rerank_pos": _top_keys.get(key, 99),
            "no_text": _is_figure_page,
            "adj_context": (sec_text[:300] if _is_figure_page and sec_text.startswith("[") else ""),
        }

    sources: list[dict] = []
    seen: set = set()

    # 1. Explicit citations the LLM wrote in the answer: [doc p.N] format
    for m in _re.finditer(r"\[([^\]]+?) p\.(\d+)\]", answer + " " + context_text[:2000]):
        str_key = (m.group(1), m.group(2))
        if str_key not in seen:
            seen.add(str_key)
            sources.append(_make_source(m.group(1), int(m.group(2))))

    # 2. If LLM wrote no explicit citations, surface the top retrieved sections directly
    if not sources:
        for sec in top_sections[:5]:
            doc  = sec.get("doc", "")
            page = sec.get("page", 0)
            str_key = (doc, str(page))
            if str_key not in seen:
                seen.add(str_key)
                sources.append(_make_source(doc, page))

    # Sort: explicit citations first (rerank_pos=99 means not in top list), then by rank
    sources.sort(key=lambda s: s["rerank_pos"])

    # ── Jury Variance Drift (post-query, zero LLM) ────────────────────────
    # Measures consensus between jury/panel agent outputs.
    # If consensus < 0.40 → agents diverged wildly → force Ampel RED.
    drift_query: dict | None = None
    if critic_output:
        from ma.drift_detector import check_jury_variance
        drift_query = check_jury_variance(
            critic_output,
            doc_name=req.pdf_paths[0] if req.pdf_paths else "unknown",
        )
        if drift_query.get("force_red") and ampel != "red":
            ampel = "red"
            ampel_reason = (
                f"Jury-Variance-Drift: Agenten-Konsens {drift_query['consensus']:.0%} "
                f"— Antwort unzuverlässig, Quelldokumente prüfen."
            )

    return {
        "answer": answer,
        "sources": sources[:8],
        "ampel": ampel,
        "ampel_reason": ampel_reason,
        "contradictions": contradictions,
        "unverified_claims": list(unverified),
        "generator_model": _GEN_MODEL,
        "retrieval_method": (
            "rrf+reranker" if any(s.get("embedding") for s in top_sections) else "rrf+bm25"
        ),
        "critic": critic_output,
        "truth_gaps": truth_gaps,
        "drift": drift_query,
        "consensus": consensus_result,
    }


# ── Structured graph traversal endpoint ──────────────────────────────────────

class GraphQueryRequest(BaseModel):
    pdf_paths: list[str]
    node_type: Optional[str] = None
    relation: Optional[str] = None
    node_name: Optional[str] = None

@router.post("/documents/graph-query")
async def graph_query_endpoint(req: GraphQueryRequest):
    """Structured KG traversal — no LLM, pure graph lookup."""
    from legatum.graph_store import load_graph, query_graph
    all_edges: list[dict] = []
    for p in req.pdf_paths:
        g = load_graph(p)
        if g:
            all_edges.extend(g.get("edges", []))
    from legatum.graph_store import query_graph as _qg
    results = _qg(all_edges, req.node_type, req.relation, req.node_name)
    return {"edges": results, "count": len(results)}


# ── BIM RAG memory + eval endpoints ──────────────────────────────────────────

BIM_RAG_BASE = Path("/Users/mango/BlackSwanX/shared/rag/data")

@router.get("/bim/memory-stats")
async def bim_memory_stats():
    import sqlite3 as _sq
    out: dict = {}
    try:
        c = _sq.connect(str(BIM_RAG_BASE / "ledgers.db"))
        out["episodes"] = c.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        out["agent_sessions"] = c.execute("SELECT COUNT(*) FROM agent_sessions").fetchone()[0]
        out["agent_items"] = c.execute("SELECT COUNT(*) FROM agent_items").fetchone()[0]
        rows = c.execute(
            "SELECT episode_id,query,answer,score,created_at FROM episodes ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        out["episodes_list"] = [
            {"episode_id": r[0], "query": r[1], "answer": r[2] or "", "score": r[3] or 0.0, "created_at": r[4] or ""}
            for r in rows
        ]
        c.close()
    except Exception:
        out.setdefault("episodes", 0)
    try:
        c2 = _sq.connect(str(BIM_RAG_BASE / "company_memory.db"))
        out["company_items"] = c2.execute("SELECT COUNT(*) FROM company_items").fetchone()[0]
        c2.close()
    except Exception:
        out.setdefault("company_items", 0)
    try:
        c3 = _sq.connect(str(BIM_RAG_BASE / "sona.db"))
        out["patterns"] = c3.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
        out["ewc_protected"] = c3.execute("SELECT COUNT(*) FROM ewc_importance WHERE importance>0.6").fetchone()[0]
        out["routing_log"] = c3.execute("SELECT COUNT(*) FROM routing_log").fetchone()[0]
        c3.close()
    except Exception:
        out.setdefault("patterns", 0)
    try:
        c4 = _sq.connect(str(BIM_RAG_BASE / "legatum_complete.db"))
        t = c4.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='semantic_scores'").fetchone()
        out["semantic_scores"] = c4.execute("SELECT COUNT(*) FROM semantic_scores").fetchone()[0] if t else 0
        c4.close()
    except Exception:
        out.setdefault("semantic_scores", 0)
    return out


@router.get("/bim/eval-results")
async def bim_eval_results():
    import sqlite3 as _sq
    try:
        c = _sq.connect(str(BIM_RAG_BASE / "ledgers.db"))
        rows = c.execute(
            "SELECT query,answer,verdict,score,created_at FROM episodes "
            "WHERE verdict IS NOT NULL ORDER BY created_at ASC"
        ).fetchall()
        c.close()
        results = [
            {"query": r[0], "answer": r[1] or "", "verdict": r[2] or "", "score": float(r[3] or 0), "created_at": r[4] or ""}
            for r in rows
        ]
        total = len(results)
        avg = sum(r["score"] for r in results) / total if total else 0.0
        return {"results": results, "total": total, "avg_score": round(avg, 3), "complete": total >= 18}
    except Exception as e:
        return {"results": [], "total": 0, "avg_score": 0.0, "complete": False, "error": str(e)}

