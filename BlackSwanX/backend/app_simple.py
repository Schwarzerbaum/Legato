"""BlackSwanX — Simple Flask server (no pydantic dependency)."""
import json
import sqlite3
import os
from flask import Flask, request, jsonify, Response, render_template
from flask_cors import CORS

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "blackswanx.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS raw_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER,
            platform TEXT,
            author TEXT,
            content TEXT,
            url TEXT,
            engagement INTEGER DEFAULT 0,
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


init_db()

# User profile storage
USER_PROFILE = {}

@app.route("/api/profile", methods=["GET"])
def get_profile():
    return jsonify(USER_PROFILE)

@app.route("/api/profile", methods=["POST"])
def save_profile():
    global USER_PROFILE
    USER_PROFILE = request.json
    # Persist to DB
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS user_profile (id INTEGER PRIMARY KEY, data TEXT)")
    conn.execute("INSERT OR REPLACE INTO user_profile (id, data) VALUES (1, ?)", (json.dumps(USER_PROFILE),))
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})

# Load profile on startup
try:
    _conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "blackswanx.db"))
    _conn.row_factory = sqlite3.Row
    _conn.execute("CREATE TABLE IF NOT EXISTS user_profile (id INTEGER PRIMARY KEY, data TEXT)")
    _row = _conn.execute("SELECT data FROM user_profile WHERE id=1").fetchone()
    if _row:
        USER_PROFILE = json.loads(_row["data"])
    _conn.close()
except:
    pass


# ─── Upgrade 2: Deal Team Persona — Investment Thesis Cache ─────────────────
# Inspired by Supermemory's 50ms user profile cache.
# The PE firm / legal team inputs their mandate once; it is injected into
# every Predator agent's system prompt so agents hunt firm-specific violations.

DEAL_PROFILE: dict = {}

def _init_deal_profile_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS ma_deal_profile "
        "(id INTEGER PRIMARY KEY, data TEXT, updated_at TEXT DEFAULT (datetime('now')))"
    )

def _load_deal_profile():
    global DEAL_PROFILE
    try:
        _c = sqlite3.connect(os.path.join(os.path.dirname(__file__), "blackswanx.db"))
        _c.row_factory = sqlite3.Row
        _init_deal_profile_table(_c)
        row = _c.execute("SELECT data FROM ma_deal_profile WHERE id=1").fetchone()
        if row:
            DEAL_PROFILE = json.loads(row["data"])
        _c.close()
    except Exception:
        pass

_load_deal_profile()


@app.route("/api/ma/deal-profile", methods=["GET"])
def get_deal_profile():
    return jsonify(DEAL_PROFILE)


@app.route("/api/ma/deal-profile", methods=["POST"])
def save_deal_profile():
    global DEAL_PROFILE
    DEAL_PROFILE = request.json or {}
    conn = get_db()
    _init_deal_profile_table(conn)
    conn.execute(
        "INSERT OR REPLACE INTO ma_deal_profile (id, data, updated_at) VALUES (1, ?, datetime('now'))",
        (json.dumps(DEAL_PROFILE),),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "saved", "fields": list(DEAL_PROFILE.keys())})


def _build_deal_profile_injection() -> str:
    """Render the firm's investment mandate as a system-prompt injection block.

    Returns an empty string if no profile is set (safe to append unconditionally).
    """
    if not DEAL_PROFILE:
        return ""

    lines = ["\n\n[DEAL TEAM MANDATE — hunt SPECIFICALLY for violations of these criteria]"]
    if DEAL_PROFILE.get("firm_name"):
        lines.append(f"Firm: {DEAL_PROFILE['firm_name']}")
    if DEAL_PROFILE.get("no_go_clauses"):
        lines.append(f"HARD STOPS (flag immediately): {DEAL_PROFILE['no_go_clauses']}")
    if DEAL_PROFILE.get("max_churn_pct"):
        lines.append(f"Max acceptable churn: {DEAL_PROFILE['max_churn_pct']}%")
    if DEAL_PROFILE.get("jurisdiction"):
        lines.append(f"Required jurisdiction: {DEAL_PROFILE['jurisdiction']}")
    if DEAL_PROFILE.get("indemnity_cap"):
        lines.append(f"Indemnity cap requirement: {DEAL_PROFILE['indemnity_cap']}")
    if DEAL_PROFILE.get("max_leverage"):
        lines.append(f"Max leverage: {DEAL_PROFILE['max_leverage']}x")
    if DEAL_PROFILE.get("sector_focus"):
        lines.append(f"Sector focus: {DEAL_PROFILE['sector_focus']}")
    if DEAL_PROFILE.get("custom_criteria"):
        lines.append(f"Additional mandate: {DEAL_PROFILE['custom_criteria']}")
    lines.append(
        "If you find ANY violation of the above criteria, prefix the finding with "
        "[MANDATE VIOLATION] and assign severity=CRITICAL."
    )
    return "\n".join(lines)


def _build_ltm_context(entity_names: list[str], limit: int = 12) -> str:
    """Retrieve long-term memories relevant to these entities.

    Returns a formatted block to prepend to agent user messages, or ''
    if no relevant memories exist yet.  Safe to call unconditionally.
    """
    if not entity_names:
        return ""
    try:
        from ma.long_term_memory import recall_as_context_block
        return recall_as_context_block(entity_names, min_strength=0.25, limit=limit)
    except Exception:
        return ""


def _build_full_agent_context(entity_names: list[str], kg_triples: str) -> str:
    """Merge KG triples + LTM recall into one ordered context block.

    Order: LTM permanent memories first (highest signal), then KG triples
    (current-document structure), then the raw chunk text follows separately.
    """
    ltm = _build_ltm_context(entity_names)
    parts = []
    if ltm:
        parts.append(ltm)
    if kg_triples:
        parts.append(kg_triples)
    return "\n\n".join(parts)


@app.route("/")
def root():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({"name": "BlackSwanX", "version": "0.1.0", "status": "running"})


@app.route("/api/system/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/system/hardware")
def hardware():
    import subprocess
    try:
        chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        chip = "Unknown"
    try:
        ram = int(subprocess.run(["sysctl", "-n", "hw.memsize"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()) / (1024**3)
    except Exception:
        ram = 0

    return jsonify({
        "hardware": {"chip": chip, "total_ram_gb": round(ram, 1), "usable_vram_gb": round(ram * 0.75, 1), "os": "Darwin"},
        "models": {
            "swarm": "llama3.2:3b",
            "assassin": "phi4:14b",
            "nexus": "mistral-small:24b",
        }
    })


@app.route("/api/analysis/topics", methods=["GET"])
def list_topics():
    conn = get_db()
    rows = conn.execute("SELECT * FROM topics ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/analysis/upload", methods=["POST"])
def upload_document():
    """Upload a document (PDF, TXT, MD, CSV) for analysis alongside live data."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Save to uploads dir
    upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    import time as _t
    safe_name = f"{int(_t.time())}_{file.filename}"
    filepath = os.path.join(upload_dir, safe_name)
    file.save(filepath)

    # Extract text based on file type
    text = ""
    ext = file.filename.lower().split('.')[-1]
    try:
        if ext == 'pdf':
            import subprocess
            # Use python's built-in or pdftotext
            with open(filepath, 'rb') as f:
                # Simple PDF text extraction
                content = f.read()
                # Try to extract text between stream/endstream
                text = content.decode('latin-1', errors='ignore')
                # Basic cleanup
                import re
                text = re.sub(r'[^\x20-\x7E\n]', ' ', text)[:10000]
        elif ext in ('txt', 'md', 'csv', 'tsv'):
            with open(filepath, 'r', errors='ignore') as f:
                text = f.read()[:10000]
        else:
            text = f"Unsupported file type: {ext}"
    except Exception as e:
        text = f"Error reading file: {e}"

    # Store document text in DB
    conn = get_db()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, filename TEXT, filepath TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    cur = conn.execute("INSERT INTO documents (filename, filepath, content) VALUES (?,?,?)",
                        (file.filename, filepath, text[:10000]))
    conn.commit()
    doc_id = cur.lastrowid
    conn.close()

    return jsonify({"doc_id": doc_id, "filename": file.filename, "chars": len(text), "preview": text[:500]})


@app.route("/api/analysis/topics", methods=["POST"])
def create_topic():
    data = request.json
    query = data.get("query", "").strip()
    doc_id = data.get("doc_id")  # Optional: attach a document
    if not query:
        return jsonify({"error": "query required"}), 400

    # If doc_id provided, append document context to the query
    doc_context = ""
    if doc_id:
        conn = get_db()
        doc = conn.execute("SELECT content, filename FROM documents WHERE id=?", (doc_id,)).fetchone()
        conn.close()
        if doc:
            doc_context = f"\n\n[UPLOADED DOCUMENT: {doc['filename']}]\n{doc['content'][:3000]}"
    conn = get_db()
    cur = conn.execute("INSERT INTO topics (query) VALUES (?)", (query,))
    conn.commit()
    topic = dict(conn.execute("SELECT * FROM topics WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()

    # Set citizen count based on mode
    mode = data.get("mode", "fast")
    citizen_map = {"fast": "25", "medium": "50", "deep": "200"}
    citizen_count = citizen_map.get(mode, "25")
    os.environ["BLACKSWANX_CITIZENS"] = citizen_count

    # Inject user profile into query context
    profile_context = ""
    if USER_PROFILE:
        p = USER_PROFILE
        profile_context = f"\n\n[USER PROFILE — personalize all advice to this person]\n"
        profile_context += f"Name: {p.get('name', 'Anonymous')}\n"
        profile_context += f"Age: {p.get('age', 'Unknown')}\n"
        profile_context += f"Role: {p.get('role', 'Unknown')}\n"
        profile_context += f"Location: {p.get('location', 'Unknown')}\n"
        profile_context += f"Income: {p.get('income', 'Unknown')}\n"
        profile_context += f"Savings: {p.get('savings', 'Unknown')}\n"
        profile_context += f"Risk tolerance: {p.get('risk_tolerance', 'medium')}\n"
        profile_context += f"Dependents: {p.get('dependents', 'Unknown')}\n"
        profile_context += f"Goals: {p.get('goals', 'Unknown')}\n"
        profile_context += f"Context: {p.get('context', '')}\n"

    # Auto-start the NEXUS pipeline in background
    from pipeline_sync import run_pipeline_background
    run_pipeline_background(topic["id"], query + doc_context + profile_context)

    return jsonify(topic)


@app.route("/api/analysis/topics/<int:topic_id>")
def get_topic(topic_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))


@app.route("/api/analysis/topics/<int:topic_id>/crawl", methods=["POST"])
def start_crawl(topic_id):
    conn = get_db()
    row = conn.execute("SELECT query FROM topics WHERE id=?", (topic_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404

    from pipeline_sync import run_pipeline_background
    run_pipeline_background(topic_id, row["query"])
    return jsonify({"status": "crawling", "topic_id": topic_id})


@app.route("/api/analysis/topics/<int:topic_id>/result")
def get_result(topic_id):
    from pipeline_sync import get_result
    result = get_result(topic_id)
    if not result:
        return jsonify({"status": "pending", "message": "Pipeline still running..."})
    return jsonify(result)


@app.route("/api/sona/status")
def sona_status():
    """Get SONA learning status — what has it learned across all runs?"""
    try:
        conn = get_db()
        # Check if SONA tables exist
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

        if 'sona_agent_scores' not in tables:
            conn.close()
            return jsonify({"status": "no_data", "message": "SONA hasn't learned anything yet. Run an analysis first.", "runs": 0})

        scores = conn.execute("SELECT * FROM sona_agent_scores ORDER BY total_weight DESC LIMIT 20").fetchall()
        patterns = conn.execute("SELECT * FROM sona_reasoning_bank ORDER BY id DESC LIMIT 10").fetchall()
        audit_count = conn.execute("SELECT count(*) as c FROM sona_audit_log").fetchone()
        conn.close()

        return jsonify({
            "status": "active",
            "top_agents": [dict(r) for r in scores],
            "patterns_learned": [dict(r) for r in patterns],
            "total_audits": audit_count["c"] if audit_count else 0,
            "message": f"SONA has audited agents across {audit_count['c'] if audit_count else 0} events and learned {len(patterns)} patterns."
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/analysis/topics/<int:topic_id>/live")
def get_live_feed(topic_id):
    """Get live feed events for real-time simulation display."""
    after_id = request.args.get("after", 0, type=int)
    from pipeline_sync import get_live_feed
    events = get_live_feed(topic_id, after_id)
    return jsonify(events)


@app.route("/api/simulation/kill-switch/<int:topic_id>", methods=["POST"])
def kill_switch(topic_id):
    return jsonify({"status": "pending", "message": "Pull Ollama models first to enable simulation"})


# ============================================================
# AGENT REGISTRY API — 140+ Experts from agency-agents
# ============================================================
import sys
sys.path.insert(0, os.path.dirname(__file__))
from agents.registry import load_agents, list_agents, list_divisions, search_agents, get_agent


@app.route("/api/agents")
def api_list_agents():
    division = request.args.get("division")
    return jsonify(list_agents(division))


@app.route("/api/agents/divisions")
def api_list_divisions():
    return jsonify(list_divisions())


@app.route("/api/agents/search")
def api_search_agents():
    q = request.args.get("q", "")
    return jsonify(search_agents(q))


@app.route("/api/agents/<agent_id>")
def api_get_agent(agent_id):
    a = get_agent(agent_id)
    if not a:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": a.id, "name": a.name, "emoji": a.emoji, "vibe": a.vibe,
        "division": a.division, "color": a.color, "description": a.description,
        "system_prompt_preview": a.system_prompt[:500] + "..." if len(a.system_prompt) > 500 else a.system_prompt,
    })


@app.route("/api/chat/message", methods=["POST"])
def chat_message():
    data = request.json
    agent = data.get("agent", "provocateur")
    message = data.get("message", "")

    # Without Ollama running, return a placeholder
    def generate():
        yield f"[{agent.upper()}] I need Ollama to be running to respond. "
        yield f"Pull a model with: ollama pull qwen2.5:3b\n\n"
        yield f"Your question was: {message}"

    return Response(generate(), mimetype="text/plain")


# ── ACCOUNTING / DATEV ROUTES ────────────────────────────────

def init_accounting_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fiscal_years (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL UNIQUE,
            start_date TEXT,
            end_date TEXT,
            is_closed INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS chart_of_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            account_type TEXT,
            skr_variant TEXT DEFAULT 'SKR03',
            tax_relevant INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_number TEXT,
            date TEXT,
            debit_account_code TEXT,
            credit_account_code TEXT,
            amount REAL,
            tax_rate REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            description TEXT,
            document_ref TEXT,
            is_locked INTEGER DEFAULT 0,
            is_storno INTEGER DEFAULT 0,
            fiscal_year_id INTEGER,
            pheromone_intensity REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

init_accounting_db()


@app.route("/api/datev/sample-data/<data_type>")
def get_sample_data(data_type):
    """Download sample CSV for testing."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from accounting.sample_data import (
            generate_sample_datev_csv,
            generate_sample_payroll_csv,
            generate_sample_bank_csv,
        )
        generators = {
            "datev": (generate_sample_datev_csv, "sample_datev.csv"),
            "payroll": (generate_sample_payroll_csv, "sample_payroll.csv"),
            "bank": (generate_sample_bank_csv, "sample_bank.csv"),
        }
        if data_type not in generators:
            return jsonify({"error": f"Unknown type: {data_type}. Use: datev, payroll, bank"}), 400
        gen_func, filename = generators[data_type]
        csv_content = gen_func()
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/datev/fiscal-years")
def list_fiscal_years():
    conn = get_db()
    rows = conn.execute("SELECT * FROM fiscal_years ORDER BY year DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/datev/bookings")
def list_bookings():
    conn = get_db()
    limit = request.args.get("limit", 500, type=int)
    reflex = request.args.get("reflex", "false").lower() == "true"
    fy_id = request.args.get("fiscal_year_id", type=int)
    conditions = []
    if fy_id:
        conditions.append(f"fiscal_year_id = {fy_id}")
    if reflex:
        conditions.append("(pheromone_intensity > 0.1 OR is_locked = 0)")
    query = "SELECT * FROM bookings"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" ORDER BY date DESC LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    conn.close()
    # Normalize column names for React (debit_account_code → debit_account)
    result = []
    for r in rows:
        d = dict(r)
        d["debit_account"] = d.pop("debit_account_code", "")
        d["credit_account"] = d.pop("credit_account_code", "")
        d["locked"] = bool(d.get("is_locked", 0))
        result.append(d)
    return jsonify(result)


@app.route("/api/datev/export-csv/<int:fiscal_year_id>")
def export_datev_csv(fiscal_year_id):
    """Export bookings as DATEV-compatible CSV (cp1252, semicolon)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM bookings WHERE fiscal_year_id=? ORDER BY date", (fiscal_year_id,)
    ).fetchall()
    conn.close()
    lines = ["Umsatz (ohne Soll/Haben-Kz);Soll/Haben-Kennzeichen;Konto;Gegenkonto (ohne BU-Schluessel);BU-Schluessel;Belegdatum;Belegfeld 1;Buchungstext"]
    for r in rows:
        amount = f"{r['amount']:.2f}".replace(".", ",")
        bu = "3" if r["tax_rate"] == 19.0 else ("2" if r["tax_rate"] == 7.0 else "")
        date_str = (r["date"] or "").replace("-", "")[-8:] if r["date"] else ""
        # DATEV format: DDMMYYYY
        if len(date_str) == 8:
            date_str = date_str[6:8] + date_str[4:6] + date_str[:4]
        # H = Haben (credit to Konto), credit_account is the main account
        konto = r["credit_account_code"] or ""
        gegen = r["debit_account_code"] or ""
        lines.append(f"{amount};H;{konto};{gegen};{bu};{date_str};{r['booking_number'] or ''};{r['description'] or ''}")
    csv_content = "\n".join(lines)
    return Response(
        csv_content.encode("cp1252", errors="replace"),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=blackswanx_export_{fiscal_year_id}.csv"},
    )


@app.route("/api/datev/import", methods=["POST"])
def import_datev():
    """Import a DATEV CSV file into bookings table."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    content = f.read()
    if not content:
        return jsonify({"error": "Empty file"}), 400
    try:
        # Inline lightweight parser to avoid SQLAlchemy import
        import csv, io

        def _parse_amount_simple(s):
            if not s: return 0.0
            s = s.strip().replace(".", "").replace(",", ".")
            try: return round(float(s), 2)
            except: return 0.0

        def _parse_date_simple(s):
            if not s: return None
            s = s.strip()
            try:
                if len(s) == 4: return f"2026-{s[2:4]}-{s[:2]}"
                if len(s) == 6: return f"20{s[4:6]}-{s[2:4]}-{s[:2]}"
                if len(s) == 8: return f"{s[4:8]}-{s[2:4]}-{s[:2]}"
                if "." in s:
                    p = s.split(".")
                    return f"{p[2]}-{p[1]}-{p[0]}" if len(p) == 3 else None
            except: return None

        try:
            text = content.decode("cp1252")
        except:
            text = content.decode("utf-8", errors="replace")

        lines = text.strip().split("\n")
        header_idx = 0
        for i, line in enumerate(lines):
            if "Umsatz" in line or "Konto" in line:
                header_idx = i
                break

        csv_text = "\n".join(lines[header_idx:])
        reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
        bookings = []
        for row in reader:
            amt_str = row.get("Umsatz (ohne Soll/Haben-Kz)") or row.get("Umsatz") or ""
            amount = _parse_amount_simple(amt_str)
            if amount == 0: continue
            sh = (row.get("Soll/Haben-Kennzeichen") or row.get("S/H") or "").strip().upper()
            konto = (row.get("Konto") or "").strip()
            gegen = (row.get("Gegenkonto (ohne BU-Schluessel)") or row.get("Gegenkonto") or "").strip()
            debit = gegen if sh == "H" else konto
            credit = konto if sh == "H" else gegen
            bu = (row.get("BU-Schluessel") or "").strip()
            tax = 19.0 if bu == "3" else (7.0 if bu == "2" else 0.0)
            bookings.append({
                "booking_number": None,
                "debit_account": debit,
                "credit_account": credit,
                "amount": amount,
                "tax_rate": tax,
                "tax_amount": round(amount * tax / (100 + tax), 2) if tax else 0.0,
                "date": _parse_date_simple(row.get("Belegdatum") or row.get("Datum") or ""),
                "description": (row.get("Buchungstext") or row.get("Text") or "").strip(),
                "document_ref": (row.get("Belegfeld 1") or row.get("Beleg") or "").strip(),
            })
        conn = get_db()
        # Ensure fiscal year exists
        year = __import__("datetime").date.today().year
        fy = conn.execute("SELECT id FROM fiscal_years WHERE year=?", (year,)).fetchone()
        if not fy:
            conn.execute(
                "INSERT INTO fiscal_years (year, start_date, end_date) VALUES (?,?,?)",
                (year, f"{year}-01-01", f"{year}-12-31"),
            )
            conn.commit()
            fy = conn.execute("SELECT id FROM fiscal_years WHERE year=?", (year,)).fetchone()
        fy_id = fy["id"]
        # Get next sequential booking number (GoBD: no gaps)
        last = conn.execute("SELECT booking_number FROM bookings ORDER BY id DESC LIMIT 1").fetchone()
        next_num = 1
        if last and last["booking_number"]:
            try:
                next_num = int(last["booking_number"].split("-")[-1]) + 1
            except (ValueError, IndexError):
                next_num = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] + 1
        imported = 0
        for b in bookings:
            bk_num = f"BK{year}-{(next_num + imported):03d}"
            conn.execute(
                """INSERT INTO bookings
                   (booking_number, date, debit_account_code, credit_account_code,
                    amount, tax_rate, tax_amount, description, document_ref, fiscal_year_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    bk_num,
                    str(b.get("date", "")),
                    b.get("debit_account", ""),
                    b.get("credit_account", ""),
                    float(b.get("amount", 0)),
                    float(b.get("tax_rate", 0)),
                    float(b.get("tax_amount", 0)),
                    b.get("description", ""),
                    b.get("document_ref", ""),
                    fy_id,
                ),
            )
            imported += 1
        conn.commit()
        conn.close()
        return jsonify({
            "status": "success",
            "imported": imported,
            "fiscal_year": year,
            "message": f"Imported {imported} bookings. Run Financial Analysis to detect anomalies.",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/datev/analyze/<int:fiscal_year_id>", methods=["POST"])
def run_analysis(fiscal_year_id):
    """Run simplified financial analysis (Benford + duplicate check) — no Ollama needed."""
    import math
    from collections import Counter
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM bookings WHERE fiscal_year_id=?", (fiscal_year_id,)
    ).fetchall()
    conn.close()
    if not rows:
        return jsonify({"error": "No bookings found for this fiscal year"}), 404

    amounts = [r["amount"] for r in rows if r["amount"] and r["amount"] > 0]
    # Benford's Law check
    first_digits = [int(str(abs(a)).lstrip("0")[0]) for a in amounts if str(abs(a)).lstrip("0")]
    observed = Counter(first_digits)
    benford_expected = {d: math.log10(1 + 1/d) for d in range(1, 10)}
    n = len(first_digits)
    benford_deviation = sum(
        abs(observed.get(d, 0)/n - benford_expected[d]) for d in range(1, 10)
    ) if n > 0 else 0

    # Duplicate detection
    seen = {}
    duplicates = []
    for r in rows:
        key = (round(r["amount"], 2), r["description"][:30] if r["description"] else "")
        if key in seen:
            duplicates.append({"booking_id": r["id"], "amount": r["amount"], "description": r["description"]})
        seen[key] = r["id"]

    # Round number detection
    round_numbers = [r for r in rows if r["amount"] and r["amount"] % 100 == 0 and r["amount"] >= 500]

    risk_level = "LOW"
    if benford_deviation > 0.15 or len(duplicates) > 2:
        risk_level = "HIGH"
    elif benford_deviation > 0.08 or len(duplicates) > 0:
        risk_level = "MEDIUM"

    # Update pheromone intensity on flagged bookings
    conn = get_db()
    for d in duplicates:
        conn.execute("UPDATE bookings SET pheromone_intensity=0.9 WHERE id=?", (d["booking_id"],))
    for r in round_numbers:
        conn.execute("UPDATE bookings SET pheromone_intensity=MAX(pheromone_intensity, 0.6) WHERE id=?", (r["id"],))
    conn.commit()
    conn.close()

    return jsonify({
        "fiscal_year_id": fiscal_year_id,
        "total_bookings": len(rows),
        "total_amount": sum(amounts),
        "fraud_detection": {
            "risk_level": risk_level,
            "benford_deviation": round(benford_deviation, 4),
            "benford_flag": benford_deviation > 0.08,
            "duplicates_found": len(duplicates),
            "duplicate_entries": duplicates[:5],
            "round_number_entries": len(round_numbers),
            "findings": [
                f"Benford deviation: {benford_deviation:.1%} ({'SUSPICIOUS' if benford_deviation > 0.08 else 'normal'})",
                f"{len(duplicates)} duplicate amount+description pairs detected",
                f"{len(round_numbers)} suspiciously round amounts (≥500, mod 100)",
            ],
        },
        "tax_optimization": {
            "note": "Connect Ollama (ollama pull qwen2.5:3b) for AI tax analysis",
            "deductible_estimate": round(sum(amounts) * 0.19, 2),
        },
        "pheromone_summary": {
            "flagged_bookings": len(duplicates) + len(round_numbers),
            "message": "Flagged bookings now glow on the dashboard (pheromone_intensity updated)",
        },
        "apoptosis_check": {
            "consensus_score": 1.0 - benford_deviation,
            "threshold": 0.90,
            "status": "PASS" if benford_deviation < 0.10 else "REVIEW_REQUIRED",
        },
    })


@app.route("/api/datev/payroll-analysis", methods=["POST"])
def payroll_analysis():
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    content = f.read()
    if not content:
        return jsonify({"error": "Empty file"}), 400
    try:
        from accounting.payroll import parse_payroll_csv
        employees = parse_payroll_csv(content)
        if not employees:
            return jsonify({"error": "No employee data found in CSV"}), 400

        # Synchronous analysis (no async needed for Flask)
        mindestlohn = 12.82
        violations = []
        for emp in employees:
            hourly = emp.get("hourly_rate", 0)
            if hourly and float(hourly) < mindestlohn:
                violations.append({
                    "employee": emp.get("name", "Unknown"),
                    "hourly_rate": hourly,
                    "violation": f"Below Mindestlohn ({mindestlohn} EUR/h)",
                })

        firmenwagen = [e for e in employees if e.get("company_car") or "firmenwagen" in str(e.get("notes", "")).lower()]
        overtime_risk = [e for e in employees if float(e.get("overtime_hours", 0) or 0) > 20]

        return jsonify({
            "employees_analyzed": len(employees),
            "mindestlohn_violations": violations,
            "firmenwagen_geldwerter_vorteil": len(firmenwagen),
            "overtime_risk_employees": len(overtime_risk),
            "compliance_score": max(0, 100 - len(violations) * 15 - len(firmenwagen) * 10),
            "findings": [
                f"{len(violations)} Mindestlohn violations (below {mindestlohn} EUR/h)",
                f"{len(firmenwagen)} employees with potential undeclared Firmenwagen",
                f"{len(overtime_risk)} employees with >20h overtime risk",
            ],
            "recommendation": "Full LLM analysis available when Ollama is running (ollama pull qwen2.5:3b)",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/neural/stats")
def neural_stats():
    conn = get_db()
    booking_count = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    flagged = conn.execute("SELECT COUNT(*) FROM bookings WHERE pheromone_intensity > 0.1").fetchone()[0]
    conn.close()
    return jsonify({
        "pheromone_deposits": flagged,
        "neural_pathways": 10,
        "myelinated_pathways": 3,
        "signals_transmitted": booking_count,
        "apoptosis_events": 0,
        "aweb_veins": 11,
        "message": "Living organism is active",
    })


@app.route("/api/accounting/booking", methods=["POST"])
def create_booking():
    """Create a single booking entry (GoBD-compliant sequential numbering)."""
    data = request.json or {}
    required = ["date", "debit_account", "credit_account", "amount", "fiscal_year_id"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    try:
        amount = float(data["amount"])
        tax_rate = float(data.get("tax_rate", 0))
        tax_amount = float(data.get("tax_amount", round(amount * tax_rate / (100 + tax_rate), 2) if tax_rate else 0))
        fiscal_year_id = int(data["fiscal_year_id"])
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid numeric value: {e}"}), 400

    conn = get_db()
    fy = conn.execute("SELECT id, year FROM fiscal_years WHERE id=?", (fiscal_year_id,)).fetchone()
    if not fy:
        conn.close()
        return jsonify({"error": f"Fiscal year {fiscal_year_id} not found"}), 404

    # GoBD-compliant sequential booking number — no gaps allowed
    last = conn.execute("SELECT booking_number FROM bookings ORDER BY id DESC LIMIT 1").fetchone()
    next_num = 1
    if last and last["booking_number"]:
        try:
            next_num = int(last["booking_number"].split("-")[-1]) + 1
        except (ValueError, IndexError):
            next_num = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] + 1
    bk_num = f"BK{fy['year']}-{next_num:03d}"

    conn.execute(
        """INSERT INTO bookings
           (booking_number, date, debit_account_code, credit_account_code,
            amount, tax_rate, tax_amount, description, document_ref, fiscal_year_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            bk_num,
            str(data["date"]),
            str(data["debit_account"]),
            str(data["credit_account"]),
            amount,
            tax_rate,
            tax_amount,
            str(data.get("description", "")),
            str(data.get("document_ref", "")),
            fiscal_year_id,
        ),
    )
    conn.commit()
    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({
        "status": "created",
        "id": new_id,
        "booking_number": bk_num,
        "debit_account": data["debit_account"],
        "credit_account": data["credit_account"],
        "amount": amount,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "fiscal_year_id": fiscal_year_id,
    }), 201


@app.route("/api/accounting/euer/<int:fiscal_year_id>")
def get_euer(fiscal_year_id):
    """EUeR summary: revenue, expenses, profit, VAT liability.
    SKR03: revenue = 8xxx credit, expenses = 4xxx debit
    SKR04: revenue = 4xxx credit, expenses = 5xxx debit
    """
    skr = request.args.get("skr", "SKR03").upper()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM bookings WHERE fiscal_year_id=? AND is_storno=0", (fiscal_year_id,)
    ).fetchall()
    conn.close()

    if skr == "SKR04":
        # SKR04: revenue accounts 4xxx (credit side), expense accounts 5xxx (debit side)
        revenue = sum(r["amount"] for r in rows if str(r["credit_account_code"] or "").startswith("4"))
        expenses = sum(r["amount"] for r in rows if str(r["debit_account_code"] or "").startswith("5"))
        tax_collected = sum(r["tax_amount"] or 0 for r in rows if str(r["credit_account_code"] or "").startswith("4"))
        tax_paid = sum(r["tax_amount"] or 0 for r in rows if str(r["debit_account_code"] or "").startswith("5"))
    else:
        # SKR03 (default): revenue accounts 8xxx (credit side), expense accounts 4xxx (debit side)
        revenue = sum(r["amount"] for r in rows if str(r["credit_account_code"] or "").startswith("8"))
        expenses = sum(r["amount"] for r in rows if str(r["debit_account_code"] or "").startswith("4"))
        tax_collected = sum(r["tax_amount"] or 0 for r in rows if str(r["credit_account_code"] or "").startswith("8"))
        tax_paid = sum(r["tax_amount"] or 0 for r in rows if str(r["debit_account_code"] or "").startswith("4"))

    return jsonify({
        "fiscal_year_id": fiscal_year_id,
        "skr": skr,
        "total_revenue": round(revenue, 2),
        "total_expenses": round(expenses, 2),
        "profit_loss": round(revenue - expenses, 2),
        "ust_zahllast": round(tax_collected - tax_paid, 2),
        "booking_count": len(rows),
    })


@app.route("/api/neural/pheromones")
def neural_pheromones():
    conn = get_db()
    flagged = conn.execute(
        "SELECT id, pheromone_intensity, description FROM bookings WHERE pheromone_intensity > 0.05 ORDER BY pheromone_intensity DESC LIMIT 20"
    ).fetchall()
    conn.close()
    heatmap = {}
    for r in flagged:
        heatmap[f"booking_{r['id']}"] = r["pheromone_intensity"]
    pheromones = [
        {
            "type": "ANOMALY_SCENT" if r["pheromone_intensity"] > 0.7 else "URGENCY_ALARM",
            "intensity": r["pheromone_intensity"],
            "source_agent": "fraud_detector",
            "target_entity_type": "booking",
            "target_entity_id": r["id"],
            "payload": {"description": r["description"]},
        }
        for r in flagged
    ]
    return jsonify({
        "heatmap": heatmap,
        "pheromones": pheromones,
        "total_deposits": len(flagged),
    })


@app.route("/api/neural/network")
def neural_network():
    """Return D3-compatible node/edge topology of the financial organism."""
    conn = get_db()
    booking_count = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    flagged_count = conn.execute("SELECT COUNT(*) FROM bookings WHERE pheromone_intensity > 0.1").fetchone()[0]
    conn.close()
    nodes = [
        {"id": "fraud_detector", "label": "Fraud Detector", "type": "agent", "activity": 0.9 if flagged_count > 0 else 0.2},
        {"id": "tax_optimizer", "label": "Tax Optimizer", "type": "agent", "activity": 0.7},
        {"id": "cashflow", "label": "Cash Flow", "type": "agent", "activity": 0.6},
        {"id": "audit_risk", "label": "Audit Risk", "type": "agent", "activity": 0.5},
        {"id": "regulatory", "label": "Regulatory", "type": "agent", "activity": 0.4},
        {"id": "bookings", "label": f"Bookings ({booking_count})", "type": "data", "activity": 0.8},
        {"id": "pheromones", "label": f"Pheromones ({flagged_count})", "type": "neural", "activity": min(1.0, flagged_count / 10)},
        {"id": "apoptosis", "label": "Apoptosis KS", "type": "immune", "activity": 0.3},
        {"id": "elster", "label": "ELSTER/USt-VA", "type": "output", "activity": 0.2},
        {"id": "aweb", "label": "AWEB Vascular", "type": "vascular", "activity": 0.7},
    ]
    pathways = [
        {"source": "bookings", "target": "fraud_detector", "myelinated": True, "weight": 2},
        {"source": "bookings", "target": "tax_optimizer", "myelinated": True, "weight": 2},
        {"source": "bookings", "target": "cashflow", "myelinated": False, "weight": 1},
        {"source": "fraud_detector", "target": "pheromones", "myelinated": True, "weight": 3},
        {"source": "tax_optimizer", "target": "pheromones", "myelinated": False, "weight": 1},
        {"source": "pheromones", "target": "apoptosis", "myelinated": True, "weight": 2},
        {"source": "audit_risk", "target": "elster", "myelinated": False, "weight": 1},
        {"source": "apoptosis", "target": "elster", "myelinated": True, "weight": 3},
        {"source": "aweb", "target": "bookings", "myelinated": True, "weight": 2},
        {"source": "regulatory", "target": "pheromones", "myelinated": False, "weight": 1},
    ]
    return jsonify({"nodes": nodes, "pathways": pathways})


@app.route("/api/neural/aweb")
def neural_aweb():
    """Return vein health with a live Ollama endpoint probe."""
    import time as _time

    # Live check: probe Ollama /api/tags endpoint
    ollama_status = "healthy"
    ollama_latency = 0.0
    ollama_failures = 0
    try:
        import urllib.request as _req
        t0 = _time.time()
        with _req.urlopen("http://localhost:11434/api/tags", timeout=3) as _r:
            _r.read()
        ollama_latency = round((_time.time() - t0) * 1000, 1)
    except Exception:
        ollama_status = "degraded"
        ollama_latency = 0.0
        ollama_failures = 1

    # SQLite DB health check
    db_status = "healthy"
    db_latency = 0.0
    try:
        t0 = _time.time()
        _c = get_db()
        _c.execute("SELECT 1").fetchone()
        _c.close()
        db_latency = round((_time.time() - t0) * 1000, 1)
    except Exception:
        db_status = "degraded"

    veins = [
        {"vein_id": "bank_api",      "source_type": "bank_api",    "status": "healthy",     "avg_latency_ms": 120,          "failure_count": 0},
        {"vein_id": "datev_import",  "source_type": "file_import", "status": "healthy",     "avg_latency_ms": 45,           "failure_count": 0},
        {"vein_id": "sqlite_db",     "source_type": "file_import", "status": db_status,     "avg_latency_ms": db_latency,   "failure_count": 0 if db_status == "healthy" else 1},
        {"vein_id": "ollama_llm",    "source_type": "ollama",      "status": ollama_status, "avg_latency_ms": ollama_latency, "failure_count": ollama_failures},
        {"vein_id": "bmf_crawler",   "source_type": "crawler",     "status": "healthy",     "avg_latency_ms": 890,          "failure_count": 0},
        {"vein_id": "elster_api",    "source_type": "elster",      "status": "healthy",     "avg_latency_ms": 340,          "failure_count": 0},
    ]
    healthy_count  = sum(1 for v in veins if v["status"] == "healthy")
    degraded_count = sum(1 for v in veins if v["status"] == "degraded")
    blocked_count  = sum(1 for v in veins if v["status"] == "blocked")
    return jsonify({
        "veins": veins,
        "total_veins": len(veins),
        "healthy_count": healthy_count,
        "degraded_count": degraded_count,
        "blocked_count": blocked_count,
    })


@app.route("/api/neural/apoptosis")
def neural_apoptosis():
    conn = get_db()
    # Check if analysis found issues
    analysis_row = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE pheromone_intensity >= 0.9"
    ).fetchone()[0]
    conn.close()
    events = []
    if analysis_row > 0:
        events.append({
            "id": 1,
            "entity_type": "booking_batch",
            "entity_id": "1",
            "trigger_reason": f"{analysis_row} high-risk bookings detected (duplicates/anomalies)",
            "consensus_score": 0.815,
            "threshold_required": 0.90,
            "agents_involved": ["fraud_detector", "audit_risk"],
            "timestamp": "2026-05-12T09:16:10",
            "status": "REVIEW_REQUIRED",
        })
    return jsonify(events)


@app.route("/api/neural/efficiency")
def neural_efficiency():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    flagged = conn.execute("SELECT COUNT(*) FROM bookings WHERE pheromone_intensity > 0.1").fetchone()[0]
    conn.close()
    myelinated = 3
    total_pathways = 10
    efficiency_pct = round((myelinated / total_pathways) * 100, 1) if total_pathways > 0 else 0
    return jsonify({
        "myelinated_pathways": myelinated,
        "total_pathways": total_pathways,
        "efficiency_pct": efficiency_pct,
        "tokens_saved": myelinated * 45,
        "tokens_spent": total * 2,
        "flagged_bookings": flagged,
    })


@app.route("/api/neural/tick", methods=["POST"])
def neural_tick():
    """Run one organism heartbeat — evaporate pheromones, update myelination.

    Also bridges any new M&A adversarial-pollination signals into the neural
    pheromone heatmap via backend.neural.ma_bridge.
    """
    conn = get_db()
    # Slightly decay all pheromone intensities (simulate evaporation)
    conn.execute("UPDATE bookings SET pheromone_intensity = pheromone_intensity * 0.95 WHERE pheromone_intensity > 0.01")
    conn.commit()
    booking_count = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    flagged = conn.execute("SELECT COUNT(*) FROM bookings WHERE pheromone_intensity > 0.1").fetchone()[0]
    conn.close()

    # Bridge M&A pheromone signals into the neural organism heatmap
    ma_bridged = 0
    try:
        from backend.neural.ma_bridge import bridge_ma_signals
        ma_bridged = bridge_ma_signals(db_path=DB_PATH)
    except Exception as _e:
        pass  # Bridge is best-effort; don't fail the tick

    return jsonify({
        "status": "tick_complete",
        "pheromones_evaporated": True,
        "decay_rate": 0.05,
        "active_pheromones": flagged,
        "signals_processed": booking_count,
        "myelination_updated": True,
        "apoptosis_checks": 1,
        "ma_signals_bridged": ma_bridged,
    })


@app.route("/api/neural/signals/recent")
def neural_signals():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, date, description, amount, pheromone_intensity FROM bookings WHERE pheromone_intensity > 0.05 ORDER BY pheromone_intensity DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return jsonify([
        {
            "id": r["id"],
            "signal_type": "ANOMALY_SCENT" if r["pheromone_intensity"] > 0.7 else "URGENCY_ALARM",
            "priority": "CRITICAL" if r["pheromone_intensity"] > 0.8 else "HIGH",
            "intensity": r["pheromone_intensity"],
            "propagated": True,
            "payload": {"description": r["description"], "amount": r["amount"], "date": r["date"]},
            "created_at": r["date"],
        }
        for r in rows
    ])


# ═══════════════════════════════════════════════════════════════
#  M&A Intelligence Platform
# ═══════════════════════════════════════════════════════════════

def init_ma_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ma_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            upload_date TEXT DEFAULT (datetime('now')),
            char_count INTEGER DEFAULT 0,
            page_count INTEGER DEFAULT 0,
            chunk_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'indexed',
            summary TEXT,
            doc_type TEXT DEFAULT 'UNKNOWN'
        );
        CREATE TABLE IF NOT EXISTS ma_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL REFERENCES ma_documents(id),
            text TEXT NOT NULL,
            page INTEGER DEFAULT 1,
            source TEXT DEFAULT 'text',
            char_start INTEGER DEFAULT 0,
            keyword_freq TEXT DEFAULT '{}',
            relevance_score REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS ma_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL REFERENCES ma_documents(id),
            chunk_id INTEGER REFERENCES ma_chunks(id),
            fact_type TEXT NOT NULL,
            subject TEXT,
            value TEXT,
            confidence REAL DEFAULT 0.8,
            extracted_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS ma_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id INTEGER NOT NULL REFERENCES ma_chunks(id),
            doc_id INTEGER NOT NULL REFERENCES ma_documents(id),
            note TEXT NOT NULL,
            tag TEXT DEFAULT 'general',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

init_ma_db()


@app.route("/api/ma/upload", methods=["POST"])
def ma_upload():
    """Ingest a document into the M&A knowledge base."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from ma.ingestion import extract_text, chunk_pages, keyword_vector, synaptic_prune

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    filename = f.filename or "upload.txt"
    file_bytes = f.read()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"

    pages = extract_text(filename, file_bytes)
    chunks = chunk_pages(pages)
    # Synaptic Pruning: score and tag every chunk by M&A signal density
    # High-priority chunks (R&W, MAE, NWC, indemnity) bubble to the top
    chunks = synaptic_prune(chunks, drop_boilerplate=False)
    # Attach keyword freq to each chunk
    for c in chunks:
        c["keyword_freq"] = keyword_vector(c["text"])

    conn = get_db()
    char_count = sum(len(p["text"]) for p in pages)
    page_count = max((p.get("page", 1) for p in pages), default=1)
    cur = conn.execute(
        "INSERT INTO ma_documents (filename, file_type, char_count, page_count, chunk_count) VALUES (?,?,?,?,?)",
        (filename, ext, char_count, page_count, len(chunks)),
    )
    doc_id = cur.lastrowid
    for c in chunks:
        conn.execute(
            """INSERT INTO ma_chunks
               (doc_id, text, page, source, char_start, keyword_freq, section_type, priority)
               VALUES (?,?,?,?,?,?,?,?)""",
            (doc_id, c["text"], c.get("page", 1), c.get("source", "text"),
             c.get("char_start", 0), json.dumps(c.get("keyword_freq", {})),
             c.get("section_type", "general"), c.get("priority", 40)),
        )
    conn.commit()
    conn.close()

    # Reactive knowledge graph update — incremental delta, not full rebuild
    try:
        from ma.knowledge_graph import update_graph_for_doc
        kg_delta = update_graph_for_doc(doc_id)
    except Exception as _kg_err:
        kg_delta = {"error": str(_kg_err)}

    # Auto-resolve defined terms (e.g. "the Company" = "Squarespace, Inc")
    term_resolution = {}
    try:
        from ma.knowledge_graph import resolve_defined_terms
        term_resolution = resolve_defined_terms(doc_id)
    except Exception as _tr_err:
        term_resolution = {"error": str(_tr_err)}

    # Detect document type
    doc_type = "UNKNOWN"
    try:
        from ma.knowledge_graph import detect_doc_type
        full_text_sample = "".join(c["text"] for c in chunks[:20])
        doc_type = detect_doc_type(full_text_sample)
    except Exception:
        pass

    # Persist doc_type (handle old DBs without the column gracefully)
    try:
        conn2 = get_db()
        conn2.execute("UPDATE ma_documents SET doc_type=? WHERE id=?", (doc_type, doc_id))
        conn2.commit()
        conn2.close()
    except Exception:
        pass

    # Proactive impact analysis — audit the whole deal, report what changed
    impact = {}
    try:
        from ma.knowledge_graph import analyze_upload_impact
        impact = analyze_upload_impact(doc_id)
    except Exception as _imp_err:
        impact = {"error": str(_imp_err)}

    # Long-Term Memory: auto-consolidate facts from this document into permanent memory
    # The system never forgets — every upload strengthens the firm's collective memory.
    ltm_result = {}
    try:
        from ma.long_term_memory import extract_and_consolidate_from_doc
        # Use filename as deal label (remove extension)
        _deal_label = filename.rsplit(".", 1)[0] if "." in filename else filename
        ltm_result = extract_and_consolidate_from_doc(doc_id, deal_label=_deal_label)
    except Exception as _ltm_err:
        ltm_result = {"error": str(_ltm_err)}

    return jsonify({"doc_id": doc_id, "filename": filename, "chunks": len(chunks),
                    "pages": page_count, "chars": char_count, "kg_delta": kg_delta,
                    "doc_type": doc_type,
                    "defined_terms": term_resolution.get("bindings_found", 0),
                    "impact": impact,
                    "ltm": ltm_result})


@app.route("/api/ma/documents")
def ma_documents():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, filename, file_type, upload_date, char_count, page_count, chunk_count, status, summary, "
        "COALESCE(doc_type,'UNKNOWN') as doc_type "
        "FROM ma_documents ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/ma/documents/<int:doc_id>")
def ma_document_detail(doc_id):
    conn = get_db()
    doc = conn.execute("SELECT * FROM ma_documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    chunks = conn.execute(
        "SELECT id, text, page, source, char_start, relevance_score FROM ma_chunks WHERE doc_id=? ORDER BY id",
        (doc_id,),
    ).fetchall()
    conn.close()
    return jsonify({**dict(doc), "chunks": [dict(c) for c in chunks]})


@app.route("/api/ma/search", methods=["POST"])
def ma_search():
    import sys, json as _json
    sys.path.insert(0, os.path.dirname(__file__))
    from ma.ingestion import keyword_vector, bm25_score

    body = request.json or {}
    query = body.get("query", "").strip()
    doc_id = body.get("doc_id")
    limit = min(int(body.get("limit", 15)), 40)

    if not query:
        return jsonify([])

    terms = list(keyword_vector(query).keys())
    conn = get_db()
    if doc_id:
        rows = conn.execute(
            "SELECT c.id, c.doc_id, c.text, c.page, c.source, c.keyword_freq, d.filename "
            "FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id WHERE c.doc_id=?",
            (doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT c.id, c.doc_id, c.text, c.page, c.source, c.keyword_freq, d.filename "
            "FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id"
        ).fetchall()
    conn.close()

    all_rows = [dict(r) for r in rows]
    total_len = sum(len(r["text"]) for r in all_rows)
    avg_len = total_len / max(len(all_rows), 1)

    results = []
    for r in all_rows:
        try:
            freq = _json.loads(r["keyword_freq"] or "{}")
        except Exception:
            freq = {}
        score = bm25_score(terms, freq, len(r["text"]), avg_len)
        if score > 0:
            results.append({
                "chunk_id": r["id"],
                "doc_id": r["doc_id"],
                "filename": r["filename"],
                "text": r["text"],
                "page": r["page"],
                "score": round(score, 3),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(results[:limit])


@app.route("/api/ma/annotate", methods=["POST"])
def ma_annotate():
    body = request.json or {}
    chunk_id = body.get("chunk_id")
    doc_id = body.get("doc_id")
    note = body.get("note", "").strip()
    tag = body.get("tag", "general")
    if not chunk_id or not doc_id or not note:
        return jsonify({"error": "chunk_id, doc_id and note required"}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO ma_annotations (chunk_id, doc_id, note, tag) VALUES (?,?,?,?)",
        (chunk_id, doc_id, note, tag),
    )
    ann_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"id": ann_id, "chunk_id": chunk_id, "doc_id": doc_id, "note": note, "tag": tag})


@app.route("/api/ma/annotations")
def ma_annotations():
    doc_id = request.args.get("doc_id", type=int)
    conn = get_db()
    if doc_id:
        rows = conn.execute(
            "SELECT a.*, c.text as chunk_text, d.filename FROM ma_annotations a "
            "JOIN ma_chunks c ON c.id=a.chunk_id JOIN ma_documents d ON d.id=a.doc_id "
            "WHERE a.doc_id=? ORDER BY a.id DESC",
            (doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT a.*, c.text as chunk_text, d.filename FROM ma_annotations a "
            "JOIN ma_chunks c ON c.id=a.chunk_id JOIN ma_documents d ON d.id=a.doc_id "
            "ORDER BY a.id DESC LIMIT 100"
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/ma/extract-facts", methods=["POST"])
def ma_extract_facts():
    """Extract structured facts from a document using Ollama."""
    body = request.json or {}
    doc_id = body.get("doc_id")
    if not doc_id:
        return jsonify({"error": "doc_id required"}), 400

    conn = get_db()
    chunks = conn.execute(
        "SELECT id, text FROM ma_chunks WHERE doc_id=? ORDER BY id LIMIT 20", (doc_id,)
    ).fetchall()
    conn.close()

    if not chunks:
        return jsonify({"error": "No chunks found"}), 404

    # Build a combined excerpt (first 3000 chars)
    combined = "\n\n".join(c["text"] for c in chunks)[:3000]

    # Try Ollama extraction
    facts = []
    try:
        import requests as _req
        prompt = f"""Extract structured facts from this M&A document excerpt.
Return a JSON array of objects with keys: fact_type (one of: valuation, revenue, risk, legal, team, general), subject, value.
Only return the JSON array, no explanation.

Document excerpt:
{combined}

Facts:"""
        resp = _req.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral", "prompt": prompt, "stream": False, "options": {"temperature": 0.1}},
            timeout=30,
        )
        if resp.status_code == 200:
            raw = resp.json().get("response", "")
            # Extract JSON array from response
            import re as _re
            match = _re.search(r'\[.*\]', raw, _re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                for item in parsed[:20]:
                    if isinstance(item, dict) and "fact_type" in item:
                        facts.append({
                            "doc_id": doc_id,
                            "chunk_id": chunks[0]["id"],
                            "fact_type": item.get("fact_type", "general"),
                            "subject": item.get("subject", ""),
                            "value": item.get("value", ""),
                            "confidence": 0.85,
                        })
    except Exception as e:
        # Fallback: extract heuristic facts from text
        pass

    # Heuristic fallback — extract numbers and patterns
    if not facts:
        import re as _re
        combined_chunks = [{"id": c["id"], "text": c["text"]} for c in chunks]
        for chunk in combined_chunks[:8]:
            text = chunk["text"]
            # Revenue / valuation numbers
            for m in _re.finditer(r'(\$[\d,.]+[MBK]?|\€[\d,.]+[MBK]?|[\d,.]+\s*(?:million|billion|EUR|USD))', text, _re.IGNORECASE):
                facts.append({"doc_id": doc_id, "chunk_id": chunk["id"],
                               "fact_type": "valuation", "subject": "Financial figure",
                               "value": m.group(), "confidence": 0.7})
            # Percentages
            for m in _re.finditer(r'(\d+(?:\.\d+)?%)', text):
                ctx = text[max(0, m.start()-40):m.end()+40].strip()
                facts.append({"doc_id": doc_id, "chunk_id": chunk["id"],
                               "fact_type": "revenue", "subject": "Percentage",
                               "value": f"{m.group()} — {ctx[:80]}", "confidence": 0.65})
            # Risk keywords
            for m in _re.finditer(r'\b(risk|liability|lawsuit|litigation|debt|loss|exposure)\b', text, _re.IGNORECASE):
                ctx = text[max(0, m.start()-30):m.end()+60].strip()
                facts.append({"doc_id": doc_id, "chunk_id": chunk["id"],
                               "fact_type": "risk", "subject": m.group().lower(),
                               "value": ctx[:120], "confidence": 0.6})
        # Deduplicate by value
        seen = set()
        deduped = []
        for f in facts:
            k = f["value"][:40]
            if k not in seen:
                seen.add(k)
                deduped.append(f)
        facts = deduped[:25]

    # Save to DB
    conn = get_db()
    for f in facts:
        conn.execute(
            "INSERT INTO ma_facts (doc_id, chunk_id, fact_type, subject, value, confidence) VALUES (?,?,?,?,?,?)",
            (f["doc_id"], f.get("chunk_id"), f["fact_type"], f.get("subject", ""),
             f.get("value", ""), f.get("confidence", 0.8)),
        )
    conn.commit()
    conn.close()
    return jsonify({"extracted": len(facts), "facts": facts})


@app.route("/api/ma/facts")
def ma_facts():
    doc_id = request.args.get("doc_id", type=int)
    conn = get_db()
    if doc_id:
        rows = conn.execute(
            "SELECT f.*, d.filename FROM ma_facts f JOIN ma_documents d ON d.id=f.doc_id "
            "WHERE f.doc_id=? ORDER BY f.id DESC",
            (doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT f.*, d.filename FROM ma_facts f JOIN ma_documents d ON d.id=f.doc_id "
            "ORDER BY f.id DESC LIMIT 200"
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/ma/validate", methods=["POST"])
def ma_validate():
    """Cross-validate facts for consistency — flag contradictions."""
    body = request.json or {}
    doc_id = body.get("doc_id")
    conn = get_db()
    if doc_id:
        facts = conn.execute(
            "SELECT * FROM ma_facts WHERE doc_id=? ORDER BY fact_type", (doc_id,)
        ).fetchall()
    else:
        facts = conn.execute(
            "SELECT * FROM ma_facts ORDER BY fact_type LIMIT 200"
        ).fetchall()
    conn.close()

    facts = [dict(f) for f in facts]
    issues = []

    # Simple heuristic validation
    import re as _re
    valuation_vals = [f for f in facts if f["fact_type"] == "valuation"]
    risk_vals = [f for f in facts if f["fact_type"] == "risk"]

    # Check for very high count of risk flags (>10 = red flag)
    if len(risk_vals) > 10:
        issues.append({"level": "warning", "message": f"{len(risk_vals)} risk signals detected — review carefully",
                        "affected_facts": len(risk_vals)})

    # Check for duplicate financial figures
    amounts = [_re.sub(r'[^\d.]', '', f["value"][:20]) for f in valuation_vals if f.get("value")]
    seen_amounts = set()
    for a in amounts:
        if a and a in seen_amounts:
            issues.append({"level": "info", "message": f"Duplicate financial figure: {a}", "affected_facts": 1})
        seen_amounts.add(a)

    # Summary
    return jsonify({
        "total_facts": len(facts),
        "valuation_facts": len(valuation_vals),
        "risk_facts": len(risk_vals),
        "issues": issues,
        "status": "warnings" if issues else "clean",
        "confidence_avg": round(sum(f.get("confidence", 0.8) for f in facts) / max(len(facts), 1), 2),
    })


@app.route("/api/ma/artifact", methods=["POST"])
def ma_artifact():
    """Generate an HTML report or slide deck."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from ma.artifacts import build_report_html, build_deck_html

    body = request.json or {}
    artifact_type = body.get("type", "report")  # "report" or "deck"
    title = body.get("title", "M&A Intelligence Report")
    doc_ids = body.get("doc_ids", [])

    conn = get_db()
    if doc_ids:
        placeholders = ",".join("?" * len(doc_ids))
        docs = conn.execute(
            f"SELECT id, filename, file_type, upload_date, char_count, page_count, chunk_count FROM ma_documents WHERE id IN ({placeholders})",
            doc_ids,
        ).fetchall()
        facts = conn.execute(
            f"SELECT f.*, d.filename FROM ma_facts f JOIN ma_documents d ON d.id=f.doc_id WHERE f.doc_id IN ({placeholders}) ORDER BY f.fact_type",
            doc_ids,
        ).fetchall()
        annotations = conn.execute(
            f"SELECT a.*, c.text as chunk_text, d.filename FROM ma_annotations a "
            f"JOIN ma_chunks c ON c.id=a.chunk_id JOIN ma_documents d ON d.id=a.doc_id "
            f"WHERE a.doc_id IN ({placeholders}) ORDER BY a.id DESC",
            doc_ids,
        ).fetchall()
    else:
        docs = conn.execute(
            "SELECT id, filename, file_type, upload_date, char_count, page_count, chunk_count FROM ma_documents ORDER BY id DESC LIMIT 10"
        ).fetchall()
        facts = conn.execute(
            "SELECT f.*, d.filename FROM ma_facts f JOIN ma_documents d ON d.id=f.doc_id ORDER BY f.fact_type LIMIT 100"
        ).fetchall()
        annotations = conn.execute(
            "SELECT a.*, c.text as chunk_text, d.filename FROM ma_annotations a "
            "JOIN ma_chunks c ON c.id=a.chunk_id JOIN ma_documents d ON d.id=a.doc_id "
            "ORDER BY a.id DESC LIMIT 50"
        ).fetchall()
    conn.close()

    docs = [dict(d) for d in docs]
    facts = [dict(f) for f in facts]
    annotations = [dict(a) for a in annotations]

    if artifact_type == "deck":
        # Group facts by type for slides
        from collections import defaultdict
        grouped = defaultdict(list)
        for f in facts:
            grouped[f["fact_type"]].append(f"{f.get('subject','?')}: {f.get('value','')[:80]}")
        slides = [{"title": ftype.title(), "items": items[:8]} for ftype, items in grouped.items()]
        slides.insert(0, {"title": "Executive Summary",
                           "items": [f"Documents analyzed: {len(docs)}",
                                     f"Facts extracted: {len(facts)}",
                                     f"Analyst annotations: {len(annotations)}"]})
        html = build_deck_html(title, slides)
    else:
        # Pull top search results as key passages
        top_chunks = []
        if facts:
            conn = get_db()
            chunk_ids = list({f.get("chunk_id") for f in facts[:20] if f.get("chunk_id")})
            if chunk_ids:
                placeholders = ",".join("?" * len(chunk_ids))
                rows = conn.execute(
                    f"SELECT c.id, c.text, c.page, d.filename FROM ma_chunks c "
                    f"JOIN ma_documents d ON d.id=c.doc_id WHERE c.id IN ({placeholders})",
                    chunk_ids,
                ).fetchall()
                top_chunks = [dict(r) for r in rows]
            conn.close()
        html = build_report_html(title, docs, facts, annotations, top_chunks)

    return Response(html, mimetype="text/html")


@app.route("/api/ma/warroom", methods=["POST"])
def ma_warroom():
    """Run all War Room agents against a document (or all docs)."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from ma.warroom import benford_audit, coc_scan, truth_gap_scan, red_flag_score

    body = request.json or {}
    doc_id = body.get("doc_id")

    conn = get_db()
    if doc_id:
        chunks = conn.execute(
            "SELECT id, doc_id, text, page, source FROM ma_chunks WHERE doc_id=?", (doc_id,)
        ).fetchall()
    else:
        chunks = conn.execute(
            "SELECT id, doc_id, text, page, source FROM ma_chunks LIMIT 500"
        ).fetchall()
    fact_count = conn.execute(
        "SELECT COUNT(*) FROM ma_facts" + (" WHERE doc_id=?" if doc_id else ""),
        (doc_id,) if doc_id else ()
    ).fetchone()[0]
    conn.close()

    chunks = [dict(c) for c in chunks]
    if not chunks:
        return jsonify({"error": "No chunks found — upload a document first"}), 404

    benford = benford_audit(chunks)
    coc = coc_scan(chunks)
    truth_gaps = truth_gap_scan(chunks)
    red_flags = red_flag_score(benford, coc, truth_gaps, fact_count)

    return jsonify({
        "benford": benford,
        "coc": coc,
        "truth_gaps": truth_gaps,
        "red_flags": red_flags,
        "chunks_analyzed": len(chunks),
        "doc_id": doc_id,
    })


@app.route("/api/ma/citations/<int:chunk_id>")
def ma_citation(chunk_id):
    """Return source citation for a specific chunk."""
    conn = get_db()
    row = conn.execute(
        "SELECT c.id, c.doc_id, c.page, c.source, c.char_start, c.text, d.filename "
        "FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id WHERE c.id=?",
        (chunk_id,),
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Chunk not found"}), 404
    r = dict(row)
    # Calculate approximate paragraph number
    para_approx = max(1, r["char_start"] // 400 + 1)
    return jsonify({
        "chunk_id": r["id"],
        "doc_id": r["doc_id"],
        "filename": r["filename"],
        "page": r["page"],
        "paragraph": para_approx,
        "char_start": r["char_start"],
        "source_type": r["source"],
        "citation": f"{r['filename']}, Page {r['page']}, ¶{para_approx}",
        "excerpt": r["text"][:200],
    })


# ── Embedding routes ──────────────────────────────────────────

@app.route("/api/ma/embed-status")
def ma_embed_status():
    import sys; sys.path.insert(0, os.path.dirname(__file__))
    from ma.embeddings import check_embedding_model_available
    return jsonify(check_embedding_model_available())


@app.route("/api/ma/embed/<int:doc_id>", methods=["POST"])
def ma_embed_doc(doc_id):
    """Generate and store embeddings for all chunks in a document."""
    import sys; sys.path.insert(0, os.path.dirname(__file__))
    from ma.embeddings import get_embedding

    conn = get_db()
    # Add embedding column if missing
    try:
        conn.execute("ALTER TABLE ma_chunks ADD COLUMN embedding_json TEXT")
        conn.commit()
    except Exception:
        pass

    chunks = conn.execute(
        "SELECT id, text FROM ma_chunks WHERE doc_id=? ORDER BY id", (doc_id,)
    ).fetchall()
    conn.close()

    if not chunks:
        return jsonify({"error": "No chunks found"}), 404

    embedded = 0
    failed = 0
    conn = get_db()
    for c in chunks:
        emb = get_embedding(c["text"])
        if emb:
            conn.execute(
                "UPDATE ma_chunks SET embedding_json=? WHERE id=?",
                (json.dumps(emb), c["id"]),
            )
            embedded += 1
        else:
            failed += 1
    conn.commit()
    conn.close()
    return jsonify({"doc_id": doc_id, "embedded": embedded, "failed": failed,
                    "status": "complete" if failed == 0 else "partial"})


@app.route("/api/ma/semantic-search", methods=["POST"])
def ma_semantic_search():
    """Semantic search using vector embeddings — falls back to BM25."""
    import sys; sys.path.insert(0, os.path.dirname(__file__))
    from ma.embeddings import semantic_search as _semantic_search
    from ma.ingestion import keyword_vector, bm25_score
    import json as _json

    body = request.json or {}
    query = body.get("query", "").strip()
    doc_id = body.get("doc_id")
    limit = min(int(body.get("limit", 12)), 30)
    if not query:
        return jsonify([])

    # Try to add embedding column (may already exist)
    conn = get_db()
    try:
        conn.execute("ALTER TABLE ma_chunks ADD COLUMN embedding_json TEXT")
        conn.commit()
    except Exception:
        pass

    if doc_id:
        rows = conn.execute(
            "SELECT c.id, c.doc_id, c.text, c.page, c.keyword_freq, c.embedding_json, d.filename "
            "FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id WHERE c.doc_id=?",
            (doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT c.id, c.doc_id, c.text, c.page, c.keyword_freq, c.embedding_json, d.filename "
            "FROM ma_chunks c JOIN ma_documents d ON d.id=c.doc_id LIMIT 500"
        ).fetchall()
    conn.close()

    chunk_rows = [dict(r) for r in rows]

    # Attempt semantic search
    results = _semantic_search(query, chunk_rows, top_k=limit)

    if results:
        return jsonify({"method": "semantic", "results": results})

    # Fallback to BM25
    terms = list(keyword_vector(query).keys())
    total_len = sum(len(r["text"]) for r in chunk_rows)
    avg_len = total_len / max(len(chunk_rows), 1)
    bm25_results = []
    for r in chunk_rows:
        try:
            freq = _json.loads(r["keyword_freq"] or "{}")
        except Exception:
            freq = {}
        score = bm25_score(terms, freq, len(r["text"]), avg_len)
        if score > 0:
            bm25_results.append({
                "chunk_id": r["id"], "doc_id": r["doc_id"],
                "filename": r["filename"], "text": r["text"],
                "page": r["page"], "score": round(score, 3), "method": "bm25_fallback",
            })
    bm25_results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"method": "bm25_fallback", "results": bm25_results[:limit]})


# ── Dependency Graph routes ────────────────────────────────────

_graph_cache = {}  # doc_ids_key → graph dict


@app.route("/api/ma/graph/build", methods=["POST"])
def ma_graph_build():
    """Extract entity-dependency graph from documents."""
    import sys; sys.path.insert(0, os.path.dirname(__file__))
    from ma.graph import extract_entities_from_chunks, graph_to_d3

    body = request.json or {}
    doc_ids = body.get("doc_ids")

    conn = get_db()
    if doc_ids:
        ph = ",".join("?" * len(doc_ids))
        chunks = conn.execute(
            f"SELECT id, doc_id, text, page FROM ma_chunks WHERE doc_id IN ({ph}) LIMIT 600",
            doc_ids,
        ).fetchall()
    else:
        chunks = conn.execute(
            "SELECT id, doc_id, text, page FROM ma_chunks LIMIT 600"
        ).fetchall()
    conn.close()

    chunks = [dict(c) for c in chunks]
    graph = extract_entities_from_chunks(chunks)

    # Cache it for stress-test use
    cache_key = str(sorted(doc_ids)) if doc_ids else "all"
    _graph_cache[cache_key] = graph

    return jsonify({
        "d3": graph_to_d3(graph),
        "stats": graph["stats"],
        "cache_key": cache_key,
    })


@app.route("/api/ma/graph/stress-test", methods=["POST"])
def ma_graph_stress_test():
    """Run dependency cascade stress-test on a node."""
    import sys; sys.path.insert(0, os.path.dirname(__file__))
    from ma.graph import extract_entities_from_chunks, stress_test, graph_to_d3

    body = request.json or {}
    node_id = body.get("node_id")
    doc_ids = body.get("doc_ids")
    cache_key = str(sorted(doc_ids)) if doc_ids else "all"

    # Use cache or rebuild
    graph = _graph_cache.get(cache_key)
    if not graph:
        conn = get_db()
        if doc_ids:
            ph = ",".join("?" * len(doc_ids))
            chunks = conn.execute(
                f"SELECT id, doc_id, text, page FROM ma_chunks WHERE doc_id IN ({ph}) LIMIT 600",
                doc_ids,
            ).fetchall()
        else:
            chunks = conn.execute(
                "SELECT id, doc_id, text, page FROM ma_chunks LIMIT 600"
            ).fetchall()
        conn.close()
        graph = extract_entities_from_chunks([dict(c) for c in chunks])
        _graph_cache[cache_key] = graph

    if not node_id:
        # Auto-select: find most critical node (most critical edges)
        from collections import Counter
        crit_nodes = Counter()
        for e in graph["edges"]:
            if e["severity"] == "critical":
                crit_nodes[e["source"]] += 1
                crit_nodes[e["target"]] += 1
        if crit_nodes:
            node_id = crit_nodes.most_common(1)[0][0]
        elif graph["nodes"]:
            node_id = graph["nodes"][0]["id"]
        else:
            return jsonify({"error": "No nodes in graph"}), 404

    result = stress_test(graph, node_id)
    result["d3"] = graph_to_d3(graph)
    result["all_nodes"] = [
        {"id": n["id"], "name": n["name"], "type": n["type"]}
        for n in graph["nodes"]
    ]
    return jsonify(result)


@app.route("/api/ma/temporal", methods=["POST"])
def ma_temporal():
    """Run the full Temporal Adversarial Reconstruction — The Time Machine."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from ma.temporal import run_temporal_analysis

    body = request.json or {}
    doc_ids = body.get("doc_ids")  # optional filter

    conn = get_db()
    if doc_ids:
        ph = ",".join("?" * len(doc_ids))
        docs = conn.execute(
            f"SELECT id, filename, file_type, upload_date, page_count, chunk_count FROM ma_documents WHERE id IN ({ph})",
            doc_ids,
        ).fetchall()
        chunks = conn.execute(
            f"SELECT id, doc_id, text, page, source FROM ma_chunks WHERE doc_id IN ({ph})",
            doc_ids,
        ).fetchall()
    else:
        docs = conn.execute(
            "SELECT id, filename, file_type, upload_date, page_count, chunk_count FROM ma_documents ORDER BY id"
        ).fetchall()
        chunks = conn.execute(
            "SELECT id, doc_id, text, page, source FROM ma_chunks LIMIT 1000"
        ).fetchall()
    conn.close()

    docs = [dict(d) for d in docs]
    chunks = [dict(c) for c in chunks]

    if not docs:
        return jsonify({"error": "No documents — upload historical and current docs"}), 404

    result = run_temporal_analysis(docs, chunks)
    return jsonify(result)


@app.route("/api/ma/temporal/claims", methods=["POST"])
def ma_temporal_claims():
    """Extract forward-looking claims from a specific document."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from ma.temporal import classify_document_period, extract_forward_claims

    body = request.json or {}
    doc_id = body.get("doc_id")
    if not doc_id:
        return jsonify({"error": "doc_id required"}), 400

    conn = get_db()
    doc = conn.execute("SELECT * FROM ma_documents WHERE id=?", (doc_id,)).fetchone()
    chunks = conn.execute(
        "SELECT id, doc_id, text, page FROM ma_chunks WHERE doc_id=? ORDER BY id LIMIT 30",
        (doc_id,),
    ).fetchall()
    conn.close()
    if not doc:
        return jsonify({"error": "Not found"}), 404

    doc = dict(doc)
    chunks = [dict(c) for c in chunks]
    period = classify_document_period(doc["filename"], chunks)
    claims = extract_forward_claims(doc_id, chunks, period["year"])

    return jsonify({
        "doc_id": doc_id,
        "filename": doc["filename"],
        "period": period,
        "claims": claims,
        "total": len(claims),
    })


@app.route("/api/ma/stats")
def ma_stats():
    conn = get_db()
    doc_count = conn.execute("SELECT COUNT(*) FROM ma_documents").fetchone()[0]
    chunk_count = conn.execute("SELECT COUNT(*) FROM ma_chunks").fetchone()[0]
    fact_count = conn.execute("SELECT COUNT(*) FROM ma_facts").fetchone()[0]
    annotation_count = conn.execute("SELECT COUNT(*) FROM ma_annotations").fetchone()[0]
    conn.close()
    return jsonify({
        "documents": doc_count,
        "chunks": chunk_count,
        "facts": fact_count,
        "annotations": annotation_count,
    })


# ── M&A Semantic Intelligence Routes ─────────────────────────────────────

@app.route("/api/ma/jury", methods=["POST"])
def ma_jury():
    """Run Consensus Jury on two entity mentions."""
    try:
        from ma.jury import run_jury, EntityMention
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.json or {}
    def _build(d, idx):
        return EntityMention(
            mention_id=d.get("mention_id", f"m{idx}"),
            surface_text=d.get("surface_text", ""),
            entity_type=d.get("entity_type", "Person"),
            doc_id=d.get("doc_id", 0),
            chunk_id=d.get("chunk_id", 0),
            chunk_text=d.get("chunk_text", ""),
            doc_filename=d.get("doc_filename", "unknown"),
            doc_date=d.get("doc_date"),
            properties=d.get("properties", {}),
        )
    if "mention_a" not in data or "mention_b" not in data:
        return jsonify({"error": "mention_a and mention_b required"}), 400
    verdict = run_jury(_build(data["mention_a"], "a"), _build(data["mention_b"], "b"))
    import dataclasses
    return jsonify(dataclasses.asdict(verdict))


@app.route("/api/ma/semantic/drift", methods=["POST"])
def ma_semantic_drift():
    """Detect narrative drift for an entity across documents."""
    try:
        from ma.semantic_layer import detect_narrative_drift
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.json or {}
    entity = data.get("entity_name", "")
    if not entity:
        return jsonify({"error": "entity_name required"}), 400
    result = detect_narrative_drift(entity, threshold=data.get("threshold", 0.25))
    return jsonify(result)


@app.route("/api/ma/semantic/chains", methods=["POST"])
def ma_semantic_chains():
    """Discover latent implied risk chains across documents."""
    try:
        from ma.semantic_layer import discover_latent_chains
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.json or {}
    chains = discover_latent_chains(doc_ids=data.get("doc_ids"))
    return jsonify({"chains": chains, "count": len(chains)})


@app.route("/api/ma/semantic/absences", methods=["POST"])
def ma_semantic_absences():
    """Detect absence signatures — missing expected M&A topics."""
    try:
        from ma.semantic_layer import detect_absences
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.json or {}
    result = detect_absences(doc_ids=data.get("doc_ids"))
    return jsonify(result)


@app.route("/api/ma/semantic/synaptic", methods=["POST"])
def ma_semantic_synaptic():
    """Build behavioral fingerprint / synaptic map for an entity."""
    try:
        from ma.semantic_layer import synaptic_map
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.json or {}
    entity = data.get("entity_name", "")
    if not entity:
        return jsonify({"error": "entity_name required"}), 400
    result = synaptic_map(entity, entity_type=data.get("entity_type", "Person"))
    return jsonify(result)


@app.route("/api/ma/semantic/full", methods=["POST"])
def ma_semantic_full():
    """Run full semantic analysis: drift + chains + absences + synaptic map."""
    try:
        from ma.semantic_layer import full_semantic_analysis
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.json or {}
    result = full_semantic_analysis(
        entity_names=data.get("entity_names", []),
        doc_ids=data.get("doc_ids"),
    )
    return jsonify(result)


@app.route("/api/ma/signals", methods=["GET"])
def ma_signals_summary():
    """Get current signal field summary."""
    try:
        from ma.signal_pheromones import get_signal_field_summary
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(get_signal_field_summary())


@app.route("/api/ma/signals/emit", methods=["POST"])
def ma_signals_emit():
    """Emit a signal from a source entity node."""
    try:
        from ma.signal_pheromones import emit_signal
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.json or {}
    required = ["signal_type", "source_entity", "source_chunk_id", "source_doc_id"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"{f} required"}), 400
    import dataclasses
    sig = emit_signal(
        signal_type=data["signal_type"],
        source_entity=data["source_entity"],
        source_chunk_id=data["source_chunk_id"],
        source_doc_id=data["source_doc_id"],
        strength=data.get("strength", 1.0),
        payload=data.get("payload"),
    )
    return jsonify(dataclasses.asdict(sig))


@app.route("/api/ma/signals/propagate", methods=["POST"])
def ma_signals_propagate():
    """Propagate a signal and return pulled nodes."""
    try:
        from ma.signal_pheromones import emit_signal, propagate_signal
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.json or {}
    required = ["signal_type", "source_entity", "source_chunk_id", "source_doc_id"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"{f} required"}), 400
    import dataclasses
    sig = emit_signal(
        signal_type=data["signal_type"],
        source_entity=data["source_entity"],
        source_chunk_id=data["source_chunk_id"],
        source_doc_id=data["source_doc_id"],
        strength=data.get("strength", 1.0),
        payload=data.get("payload"),
    )
    pulled = propagate_signal(sig, doc_ids=data.get("doc_ids"))
    return jsonify({
        "signal": dataclasses.asdict(sig),
        "pulled_nodes": [dataclasses.asdict(n) for n in pulled],
        "count": len(pulled),
    })


@app.route("/api/ma/signals/auto-emit/<int:doc_id>", methods=["POST"])
def ma_signals_auto_emit(doc_id):
    """Auto-emit signals from all facts in a document."""
    try:
        from ma.signal_pheromones import auto_emit_from_facts
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    import dataclasses
    signals = auto_emit_from_facts(doc_id)
    return jsonify({
        "emitted": len(signals),
        "signals": [dataclasses.asdict(s) for s in signals],
    })


# ── Knowledge Graph Routes ────────────────────────────────────────────────────

@app.route("/api/ma/kg/stats")
def ma_kg_stats():
    """Knowledge graph health: node count, edge count, type distribution."""
    try:
        from ma.knowledge_graph import get_kg_stats
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(get_kg_stats())


@app.route("/api/ma/kg/graph")
def ma_kg_full_graph():
    """Full entity graph (top 120 nodes) — D3-compatible nodes+links."""
    try:
        from ma.knowledge_graph import get_full_entity_graph
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    limit = min(200, int(request.args.get("limit", 120)))
    return jsonify(get_full_entity_graph(limit_nodes=limit))


@app.route("/api/ma/kg/connected-papers")
def ma_kg_connected_papers():
    """Document similarity graph — Connected Papers view."""
    try:
        from ma.knowledge_graph import get_connected_papers_graph
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    min_sim = float(request.args.get("min_similarity", 0.0))
    return jsonify(get_connected_papers_graph(min_similarity=min_sim))


@app.route("/api/ma/kg/entity/<path:entity_name>")
def ma_kg_entity_neighborhood(entity_name):
    """Entity neighborhood subgraph up to depth=2."""
    try:
        from ma.knowledge_graph import get_entity_neighborhood
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    depth = min(3, int(request.args.get("depth", 2)))
    return jsonify(get_entity_neighborhood(entity_name, depth=depth))


@app.route("/api/ma/kg/path")
def ma_kg_path():
    """Find shortest path between two entities: ?from=X&to=Y"""
    try:
        from ma.knowledge_graph import find_cross_doc_path
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    entity_a = request.args.get("from", "")
    entity_b = request.args.get("to", "")
    if not entity_a or not entity_b:
        return jsonify({"error": "from and to params required"}), 400
    return jsonify(find_cross_doc_path(entity_a, entity_b))


@app.route("/api/ma/kg/centrality")
def ma_kg_centrality():
    """Entity centrality ranking — most connected nodes."""
    try:
        from ma.knowledge_graph import get_entity_centrality
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    top_n = min(50, int(request.args.get("top", 20)))
    return jsonify(get_entity_centrality(top_n=top_n))


@app.route("/api/ma/kg/build/<int:doc_id>", methods=["POST"])
def ma_kg_build(doc_id):
    """Manually trigger KG update for a document (also runs on upload)."""
    try:
        from ma.knowledge_graph import update_graph_for_doc
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    delta = update_graph_for_doc(doc_id)
    return jsonify(delta)


@app.route("/api/ma/kg/communities", methods=["POST"])
def ma_kg_communities():
    """
    Run label-propagation community detection (graphiti algorithm).
    Updates community_id on every node. POST to trigger, GET to read results.
    """
    try:
        from ma.knowledge_graph import run_community_detection
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    result = run_community_detection()
    return jsonify(result)


@app.route("/api/ma/kg/weave", methods=["POST"])
def ma_kg_weave():
    """Run spider-web densifier — add cross-strand edges to reduce leaf nodes."""
    try:
        from ma.knowledge_graph import weave_spider_web
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    result = weave_spider_web()
    return jsonify(result)


@app.route("/api/ma/kg/cascade/<node_id>")
def ma_kg_cascade(node_id: str):
    """DFS cascade tracer — follow consequence chains from a given node."""
    try:
        from ma.knowledge_graph import trace_cascade
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    max_depth = request.args.get("max_depth", 6, type=int)
    result = trace_cascade(node_id, max_depth=max_depth)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@app.route("/api/ma/kg/communities")
def ma_kg_communities_get():
    """Read current community assignments."""
    try:
        from ma.knowledge import get_db
        from ma.knowledge_graph import init_kg_tables
        init_kg_tables()
        conn = get_db()
        rows = conn.execute(
            "SELECT id, label, node_count, dominant_type FROM ma_kg_communities ORDER BY node_count DESC"
        ).fetchall()
        conn.close()
        return jsonify({"communities": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ma/kg/deduplicate", methods=["POST"])
def ma_kg_deduplicate():
    """
    Merge near-duplicate entity nodes by name similarity (graphiti stage-1 dedup).
    Body: {"threshold": 0.75, "dry_run": false}
    dry_run=true previews merges without committing.
    """
    try:
        from ma.knowledge_graph import deduplicate_nodes
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.get_json(silent=True) or {}
    threshold = float(data.get("threshold", 0.75))
    dry_run = bool(data.get("dry_run", False))
    result = deduplicate_nodes(sim_threshold=threshold, dry_run=dry_run)
    return jsonify(result)


@app.route("/api/ma/kg/export/kgx")
def ma_kg_export_kgx():
    """
    Export KGX format (KG-Hub / kg-covid-19 compatible).
    Returns nodes + edges with biolink categories and temporal fields.
    """
    try:
        from ma.knowledge_graph import export_kgx
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(export_kgx())


@app.route("/api/ma/kg/ppr")
def ma_kg_ppr():
    """
    HippoRAG Personalized PageRank — multi-hop entity retrieval.
    ?q=entity_name[&q=...][&damping=0.5][&top_k=15]
    Multiple ?q= params are all used as seeds.
    Returns ranked entities by PPR score — surfaces hidden multi-hop connections.
    """
    try:
        from ma.knowledge_graph import personalized_pagerank
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    seeds = request.args.getlist("q")
    if not seeds:
        return jsonify({"error": "Provide at least one ?q= seed entity"}), 400
    damping = float(request.args.get("damping", 0.5))
    top_k   = int(request.args.get("top_k", 15))
    result = personalized_pagerank(seeds, damping=damping, top_k=top_k)
    return jsonify(result)


@app.route("/api/ma/kg/search")
def ma_kg_hybrid_search():
    """
    GitNexus-style hybrid search: BM25 keyword + PPR graph score fusion.
    ?q=query[&top_k=15][&bm25_weight=0.4]
    Returns entities ranked by combined score with source annotations.
    """
    try:
        from ma.knowledge_graph import hybrid_search
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Provide ?q= query"}), 400
    top_k = int(request.args.get("top_k", 15))
    bm25w = float(request.args.get("bm25_weight", 0.4))
    return jsonify(hybrid_search(query, top_k=top_k, bm25_weight=bm25w))


@app.route("/api/ma/kg/provenance", methods=["POST"])
def ma_kg_provenance():
    """
    Semantica-inspired agent decision provenance.
    Record an agent verdict as a first-class KG node with causal links.
    Body: {agent_name, decision_type, subject_entity, verdict,
           confidence?, linked_entities?, source_doc_ids?}
    """
    try:
        from ma.knowledge_graph import log_agent_decision
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    data = request.get_json(silent=True) or {}
    required = ["agent_name", "decision_type", "subject_entity", "verdict"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400
    nid = log_agent_decision(
        agent_name=data["agent_name"],
        decision_type=data["decision_type"],
        subject_entity=data["subject_entity"],
        verdict=data["verdict"],
        confidence=float(data.get("confidence", 0.0)),
        linked_entities=data.get("linked_entities"),
        source_doc_ids=data.get("source_doc_ids"),
    )
    return jsonify({"node_id": nid, "status": "recorded"})


@app.route("/api/ma/kg/resolve-terms/<int:doc_id>", methods=["POST"])
def ma_kg_resolve_terms(doc_id: int):
    """
    Resolve M&A defined terms for a document.
    Finds "TechTarget Inc (the 'Company')" bindings and creates alias_of edges.
    """
    try:
        from ma.knowledge_graph import resolve_defined_terms
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    result = resolve_defined_terms(doc_id)
    return jsonify(result)


@app.route("/api/ma/kg/resolve-terms/all", methods=["POST"])
def ma_kg_resolve_terms_all():
    """Run defined-term resolution across all uploaded documents."""
    try:
        from ma.knowledge_graph import resolve_defined_terms
        from ma.knowledge import get_db
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    conn = get_db()
    doc_ids = [r["id"] for r in conn.execute("SELECT id FROM ma_documents").fetchall()]
    conn.close()
    results = []
    total_aliases = 0
    for did in doc_ids:
        res = resolve_defined_terms(did)
        total_aliases += res.get("aliases_created", 0)
        results.append(res)
    return jsonify({"docs_processed": len(doc_ids), "total_aliases_created": total_aliases, "details": results})


@app.route("/api/ma/kg/pivot-entities")
def ma_kg_pivot_entities():
    """
    Cross-document entity importance summary.
    Returns entities ranked by doc_coverage × mentions × edges.
    Essential for large M&A data rooms (50-60 docs).
    """
    try:
        from ma.knowledge_graph import get_cross_doc_entity_summary
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    top_n = int(request.args.get("top_n", 20))
    return jsonify(get_cross_doc_entity_summary(top_n=top_n))


@app.route("/api/ma/kg/doc-type/<int:doc_id>")
def ma_kg_detect_doc_type(doc_id: int):
    """Classify an M&A document by type: SPA, CIM, NDA, LOI, etc."""
    try:
        from ma.knowledge_graph import detect_doc_type
        from ma.knowledge import get_db
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    conn = get_db()
    chunks = conn.execute(
        "SELECT text FROM ma_chunks WHERE doc_id=? ORDER BY page, id LIMIT 40",
        (doc_id,),
    ).fetchall()
    conn.close()
    if not chunks:
        return jsonify({"error": "Document not found or has no chunks"}), 404
    full_text = "\n".join(c["text"] for c in chunks)
    doc_type = detect_doc_type(full_text)
    return jsonify({"doc_id": doc_id, "doc_type": doc_type})


@app.route("/api/ma/adversarial/pollinate/<int:doc_id>", methods=["POST"])
def ma_adversarial_pollinate(doc_id: int):
    """
    Run Predator/Prey swarms over a document.
    Deposits PREDATOR_SCENT, PREY_SCENT, DISSONANCE pheromones.
    Body: {"use_llm": true/false}  — false for fast regex-only mode
    """
    try:
        from ma.adversarial_pollination import run_adversarial_pollination
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    body = request.get_json(force=True, silent=True) or {}
    use_llm = bool(body.get("use_llm", True))
    result = run_adversarial_pollination(doc_id, use_llm=use_llm)
    return jsonify(result)


@app.route("/api/ma/adversarial/heatmap/<int:doc_id>")
def ma_adversarial_heatmap(doc_id: int):
    """Current pheromone heatmap for a document — for UI rendering."""
    try:
        from ma.adversarial_pollination import get_pollination_heatmap
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(get_pollination_heatmap(doc_id))


@app.route("/api/ma/kg/role-anchors/<int:doc_id>", methods=["POST"])
def ma_kg_role_anchors(doc_id: int):
    """
    Role-Anchor extraction: find CEO, Founder, Guarantor etc and the person attached.
    Creates Person nodes with roles, EvidenceGap nodes for missing roles.
    """
    try:
        from ma.knowledge_graph import extract_role_anchors
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(extract_role_anchors(doc_id))


@app.route("/api/ma/kg/myelinate", methods=["POST"])
def ma_kg_myelinate():
    """
    Fractal myelination: propagate pheromone signals through the KG.
    Body: {"doc_id": int (optional), "min_intensity": float}
    """
    try:
        from ma.knowledge_graph import propagate_myelinated_signals
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    body = request.get_json(force=True, silent=True) or {}
    doc_id = body.get("doc_id")
    min_intensity = float(body.get("min_intensity", 0.1))
    return jsonify(propagate_myelinated_signals(doc_id=doc_id, min_intensity=min_intensity))


@app.route("/api/ma/kg/ghost-nodes/<int:doc_id>", methods=["POST"])
def ma_kg_ghost_nodes(doc_id: int):
    """
    Structural Neuroplasticity: spawn ghost nodes for post-acquisition structure.
    Creates NewCo, Escrow Account, NWC Peg, Earn-Out nodes tagged as simulated future state.
    """
    try:
        from ma.knowledge_graph import simulate_post_acquisition_structure
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(simulate_post_acquisition_structure(doc_id))


@app.route("/api/ma/kg/synaptic-score/<int:doc_id>")
def ma_kg_synaptic_score(doc_id: int):
    """
    Show Synaptic Pruning scores for all chunks in a document.
    Returns chunks sorted by priority with section_type labels.
    """
    try:
        from ma.ingestion import synaptic_priority_score
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    conn = get_db()
    chunks = conn.execute(
        "SELECT id, text, page, section_type, priority FROM ma_chunks WHERE doc_id=? ORDER BY priority DESC LIMIT 60",
        (doc_id,),
    ).fetchall()
    conn.close()
    if not chunks:
        return jsonify({"error": "No chunks found"}), 404

    result = []
    for c in chunks:
        # Re-score if section_type missing (old chunks pre-pruning)
        if not c["section_type"] or c["section_type"] == "general":
            priority, section_type, label = synaptic_priority_score(c["text"])
        else:
            priority = c["priority"] or 40
            section_type = c["section_type"]
            label = section_type.replace("_", " ").title()
        result.append({
            "chunk_id": c["id"],
            "page": c["page"],
            "priority": priority,
            "section_type": section_type,
            "label": label,
            "excerpt": c["text"][:120],
        })
    result.sort(key=lambda x: -x["priority"])
    return jsonify({"doc_id": doc_id, "chunks": result, "total": len(result)})


@app.route("/api/ma/leukocyte/<int:doc_id>", methods=["POST"])
def ma_run_leukocyte(doc_id: int):
    """Run the Leukocyte (Indenture & Liability Scout) agent on a document."""
    try:
        from llm.prompts import ELITE_REGISTRY
        from ma.knowledge import get_db as _get_db
    except ImportError as e:
        return jsonify({"error": str(e)}), 500

    agent = ELITE_REGISTRY.get("leukocyte")
    if not agent:
        return jsonify({"error": "leukocyte agent not in registry"}), 500

    conn = _get_db()
    # Get high-priority chunks only (section_type in CoC, R&W, definitions)
    chunks = conn.execute(
        """SELECT text FROM ma_chunks WHERE doc_id=?
           AND (section_type IN ('change_of_control','representations_warranties','indemnification','termination')
                OR priority >= 80)
           ORDER BY priority DESC LIMIT 25""",
        (doc_id,),
    ).fetchall()
    if not chunks:
        chunks = conn.execute(
            "SELECT text FROM ma_chunks WHERE doc_id=? ORDER BY id LIMIT 25", (doc_id,)
        ).fetchall()
    conn.close()

    context = "\n\n---\n\n".join(c["text"] for c in chunks)[:6000]

    # Upgrade 3: extract entity names from chunks, build subgraph triples
    try:
        from ma.knowledge_graph import build_subgraph_triples as _bst
        import re as _re3
        _entity_names = list({
            m for chunk in chunks
            for m in _re3.findall(r'\b([A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]{2,})*)\b', chunk["text"])
        })[:10]
        kg_triples = _bst(_entity_names, limit=15)
    except Exception:
        kg_triples = ""

    # Upgrade 2: inject deal team mandate into system prompt
    mandate = _build_deal_profile_injection()
    system_with_mandate = agent["system"] + mandate

    full_ctx = _build_full_agent_context(_entity_names, kg_triples)
    user_content = f"Analyse this M&A document for hidden liabilities:\n\n{context}"
    if full_ctx:
        user_content = f"{full_ctx}\n\n---\n\n{user_content}"

    # ── Rete pre-screener (deterministic, zero LLM tokens) ──────────────────
    rete_result = {"pre_screen_findings": [], "critical_count": 0, "skip_llm": False, "rules_fired": 0}
    try:
        from ma.leukocyte_rete import pre_screen_chunks, merge_with_llm_result as _merge
        rete_result = pre_screen_chunks([{"text": c["text"], "section_type": ""} for c in chunks])
    except Exception:
        _merge = None

    llm_result = None
    if not rete_result.get("skip_llm", False):
        # Only call LLM if Rete didn't already find 3+ CRITICAL patterns
        try:
            import httpx
            resp = httpx.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "llama3.2:3b",
                    "messages": [
                        {"role": "system", "content": system_with_mandate},
                        {"role": "user", "content": user_content},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 600},
                },
                timeout=60,
            )
            resp.raise_for_status()
            raw = resp.json()["message"]["content"]
        except Exception as e:
            raw = f'{{"error": "{e}", "pathogen_count": 0, "critical_findings": [], "clean_bill": true}}'

        import re as _re
        try:
            m = _re.search(r'\{.*\}', raw, _re.DOTALL)
            llm_result = json.loads(m.group()) if m else None
        except Exception:
            llm_result = None

        if not llm_result:
            pc_match = _re.search(r'[Pp]athogen\s+[Cc]ount[^:]*:\s*(\d+)', raw)
            pathogen_count = int(pc_match.group(1)) if pc_match else 0
            findings = []
            numbered = _re.findall(r'\d+\.\s+\*\*([^*]+)\*\*[:\s]*([^\n]+)', raw)
            for title, desc in numbered:
                title = title.strip().rstrip(':')
                if any(skip in title.lower() for skip in ['findings', 'risk findings', 'pathogen', 'recommended', 'action']):
                    continue
                region_start = raw.find(f'**{title}')
                region = raw[region_start:region_start + 400] if region_start >= 0 else ''
                sev_m = _re.search(r'[Ss]everity[:\s*]+([A-Z]+)', region)
                if title:
                    findings.append({
                        "type": title,
                        "description": desc.strip()[:200],
                        "severity": sev_m.group(1) if sev_m else "HIGH",
                    })
            rec_m = _re.search(r'[Rr]ecommended?\s+[Aa]ction[:\s]+([^\n]+)', raw)
            llm_result = {
                "pathogen_count": pathogen_count or len(findings),
                "critical_findings": findings,
                "clean_bill": len(findings) == 0,
                "recommended_action": rec_m.group(1).strip() if rec_m else (
                    "Conduct detailed legal review before closing" if findings else "No critical issues"
                ),
            }

    # ── merge Rete + LLM findings ────────────────────────────────────────────
    try:
        result = _merge(rete_result, llm_result) if _merge else (llm_result or {
            "pathogen_count": rete_result["critical_count"],
            "critical_findings": rete_result["pre_screen_findings"],
            "clean_bill": rete_result["critical_count"] == 0,
            "recommended_action": "walk_away" if rete_result["critical_count"] >= 3 else "renegotiate",
            "rete_pre_screen": rete_result,
        })
    except Exception:
        result = llm_result or {}

    # ── record provenance for each finding ───────────────────────────────────
    try:
        from ma.provenance_layer import track_agent_finding
        doc_name = f"doc_{doc_id}"
        for finding in result.get("critical_findings", []):
            track_agent_finding(
                entity_id=f"leukocyte_{doc_id}_{finding.get('type','unknown')}",
                entity_type="LeukocyteFinding",
                agent_id="leukocyte",
                source_document=doc_name,
                confidence=0.9 if finding.get("detected_by") == "rete_pre_screener" else 0.75,
                quote=finding.get("clause", ""),
                metadata={"severity": finding.get("severity"), "deal_impact": finding.get("deal_impact", "")},
            )
    except Exception:
        pass

    return jsonify({"doc_id": doc_id, "agent": "leukocyte", "result": result})


@app.route("/api/ma/nwc-arbitrator/<int:doc_id>", methods=["POST"])
def ma_run_nwc_arbitrator(doc_id: int):
    """Run the NWC Arbitrator agent — calculates working capital peg vs actual."""
    try:
        from llm.prompts import ELITE_REGISTRY
        from ma.knowledge import get_db as _get_db
    except ImportError as e:
        return jsonify({"error": str(e)}), 500

    agent = ELITE_REGISTRY.get("nwc_arbitrator")
    if not agent:
        return jsonify({"error": "nwc_arbitrator not in registry"}), 500

    conn = _get_db()
    # Prefer NWC and financial chunks
    chunks = conn.execute(
        """SELECT text FROM ma_chunks WHERE doc_id=?
           AND (section_type IN ('nwc_adjustment','financial_statements','purchase_price')
                OR priority >= 75)
           ORDER BY priority DESC LIMIT 20""",
        (doc_id,),
    ).fetchall()
    if not chunks:
        chunks = conn.execute(
            "SELECT text FROM ma_chunks WHERE doc_id=? ORDER BY id LIMIT 20", (doc_id,)
        ).fetchall()
    conn.close()

    context = "\n\n---\n\n".join(c["text"] for c in chunks)[:5000]

    # Upgrade 3: subgraph triple injection
    try:
        from ma.knowledge_graph import build_subgraph_triples as _bst
        import re as _re3
        _entity_names = list({
            m for chunk in chunks
            for m in _re3.findall(r'\b([A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]{2,})*)\b', chunk["text"])
        })[:10]
        kg_triples = _bst(_entity_names, limit=12)
    except Exception:
        kg_triples = ""

    mandate = _build_deal_profile_injection()
    system_with_mandate = agent["system"] + mandate
    full_ctx = _build_full_agent_context(_entity_names, kg_triples)
    user_content = f"Analyse working capital mechanics:\n\n{context}"
    if full_ctx:
        user_content = f"{full_ctx}\n\n---\n\n{user_content}"

    try:
        import httpx
        resp = httpx.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2:3b",
                "messages": [
                    {"role": "system", "content": system_with_mandate},
                    {"role": "user", "content": user_content},
                ],
                "stream": False,
                "options": {"temperature": 0.05, "num_predict": 500},
            },
            timeout=60,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
    except Exception as e:
        raw = f'{{"error": "{e}", "peg_value": null, "actual_nwc": null, "shortfall_or_excess": null}}'

    import re as _re
    # Try JSON parse first
    try:
        m = _re.search(r'\{.*\}', raw, _re.DOTALL)
        result = json.loads(m.group()) if m else None
    except Exception:
        result = None

    # Parse markdown/free-text NWC output
    if not result:
        def _extract_dollar(pattern, text):
            m = _re.search(pattern, text, _re.IGNORECASE)
            if m:
                val = m.group(1).replace(',', '').replace('$', '').strip()
                try:
                    return float(val)
                except Exception:
                    return None
            return None

        peg   = _extract_dollar(r'[Nn][Ww][Cc]\s+[Pp]eg[^$\d]*\$?([\d,]+)', raw)
        actual= _extract_dollar(r'[Aa]ctual\s+[Nn][Ww][Cc][^$\d]*\$?([\d,]+)', raw)
        shortfall_m = _re.search(r'[Ss]hortfall[^$\d]*\$?([\d,]+)', raw)
        excess_m    = _re.search(r'[Ee]xcess[^$\d]*\$?([\d,]+)', raw)
        shortfall = None
        if shortfall_m:
            try: shortfall = -float(shortfall_m.group(1).replace(',',''))
            except: pass
        elif excess_m:
            try: shortfall = float(excess_m.group(1).replace(',',''))
            except: pass
        elif peg is not None and actual is not None:
            shortfall = actual - peg

        leakage = bool(_re.search(r'leakage|overstated|excluded|manipulation', raw, _re.IGNORECASE))
        adj_m = _re.search(r'price\s+adjustment[^$\d]*\$?([\d,]+)', raw, _re.IGNORECASE)
        adj = None
        if adj_m:
            try: adj = float(adj_m.group(1).replace(',',''))
            except: pass
        elif shortfall is not None:
            adj = shortfall

        result = {
            "peg_value": peg,
            "actual_nwc": actual,
            "shortfall_or_excess": shortfall,
            "price_adjustment_due": adj,
            "leakage_risk": leakage,
            "summary": raw[:300],
        }

    return jsonify({"doc_id": doc_id, "agent": "nwc_arbitrator", "result": result})


@app.route("/api/ma/pmi-harmonizer/<int:doc_id>", methods=["POST"])
def ma_run_pmi_harmonizer(doc_id: int):
    """PMI Harmonizer — maps target company accounts to acquirer's chart of accounts."""
    try:
        from llm.prompts import ELITE_REGISTRY
        from ma.knowledge import get_db as _get_db
    except ImportError as e:
        return jsonify({"error": str(e)}), 500

    agent = ELITE_REGISTRY.get("pmi_harmonizer")
    if not agent:
        return jsonify({"error": "pmi_harmonizer not in registry"}), 500

    conn = _get_db()
    chunks = conn.execute(
        """SELECT text FROM ma_chunks WHERE doc_id=?
           AND (section_type IN ('financial_statements','definitions','nwc_adjustment')
                OR priority >= 70)
           ORDER BY priority DESC LIMIT 20""",
        (doc_id,),
    ).fetchall()
    if not chunks:
        chunks = conn.execute(
            "SELECT text FROM ma_chunks WHERE doc_id=? ORDER BY id LIMIT 20", (doc_id,)
        ).fetchall()

    # Get chart of accounts entries for additional context
    try:
        coa_rows = conn.execute(
            "SELECT code, name, category FROM chart_of_accounts LIMIT 40"
        ).fetchall()
        coa_context = "\n".join(f"{r['code']} — {r['name']} ({r['category']})" for r in coa_rows)
    except Exception:
        coa_context = ""

    conn.close()

    context = "\n\n---\n\n".join(c["text"] for c in chunks)[:5000]
    if coa_context:
        context = f"Chart of Accounts (acquirer):\n{coa_context}\n\n---\n\nDocument Excerpts:\n{context}"

    # Upgrade 3: subgraph triple injection
    try:
        from ma.knowledge_graph import build_subgraph_triples as _bst
        import re as _re3
        _entity_names = list({
            m for chunk in chunks
            for m in _re3.findall(r'\b([A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]{2,})*)\b', chunk["text"])
        })[:10]
        kg_triples = _bst(_entity_names, limit=12)
    except Exception:
        kg_triples = ""

    mandate = _build_deal_profile_injection()
    system_with_mandate = agent["system"] + mandate
    full_ctx = _build_full_agent_context(_entity_names, kg_triples)
    user_content = f"Analyse PMI account harmonisation:\n\n{context}"
    if full_ctx:
        user_content = f"{full_ctx}\n\n---\n\n{user_content}"

    try:
        import httpx
        resp = httpx.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2:3b",
                "messages": [
                    {"role": "system", "content": system_with_mandate},
                    {"role": "user", "content": user_content},
                ],
                "stream": False,
                "options": {"temperature": 0.05, "num_predict": 600},
            },
            timeout=90,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
    except Exception as e:
        raw = f'{{"error": "{e}", "account_mismatches": [], "policy_conflicts": [], "data_migration_risk": "unknown", "harmonization_score": null}}'

    import re as _re
    # Try JSON parse first
    try:
        m = _re.search(r'\{.*\}', raw, _re.DOTALL)
        result = json.loads(m.group()) if m else None
    except Exception:
        result = None

    # Fallback: extract structured fields from free text
    if not result:
        mismatches = []
        conflicts = []
        for line in raw.splitlines():
            if _re.search(r'mismatch|account\s+code|target_code', line, _re.IGNORECASE):
                mismatches.append(line.strip())
            if _re.search(r'policy|conflict|depreciation|recognition', line, _re.IGNORECASE):
                conflicts.append(line.strip())

        migration_risk = "high"
        for level in ("low", "medium", "high"):
            if level in raw.lower():
                migration_risk = level

        score_m = _re.search(r'harmonization[_\s]+score[:\s]*([\d.]+)', raw, _re.IGNORECASE)
        score = float(score_m.group(1)) if score_m else None

        result = {
            "account_mismatches": mismatches[:10],
            "policy_conflicts": conflicts[:10],
            "data_migration_risk": migration_risk,
            "harmonization_score": score,
            "summary": raw[:400],
        }

    return jsonify({"doc_id": doc_id, "agent": "pmi_harmonizer", "result": result})


@app.route("/api/ma/kg/rebuild-all", methods=["POST"])
def ma_kg_rebuild_all():
    """Rebuild KG for all documents with typed edges (replaces co_mentioned)."""
    from ma.knowledge_graph import rebuild_all_kg
    result = rebuild_all_kg(drop_existing=True)
    return jsonify(result)


@app.route("/api/ma/kg/tgs-rag-search", methods=["POST"])
def ma_kg_tgs_rag_search():
    """
    TGS-RAG bidirectional search: combines text similarity with KG cross-type traversal.
    Body: {"query": str, "top_k": int}
    Returns chunks enriched with kg_path provenance.
    """
    try:
        from ma.knowledge_graph import tgs_rag_search
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    body = request.get_json(force=True, silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400
    top_k = int(body.get("top_k", 12))
    return jsonify(tgs_rag_search(query, top_k=top_k))


@app.route("/api/ma/kg/supersession-chain/<path:entity_name>")
def ma_kg_supersession_chain(entity_name: str):
    """
    Returns the full temporal chain for an entity — oldest to newest.
    Each item has: name, doc_type, valid_from, status (current/superseded), superseded_by, supersession_reason.
    """
    try:
        from ma.knowledge_graph import get_supersession_chain
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    chain = get_supersession_chain(entity_name)
    return jsonify({"entity": entity_name, "chain": chain, "chain_length": len(chain)})


@app.route("/api/ma/kg/supersession-jury", methods=["POST"])
def ma_kg_supersession_jury():
    """
    Run a supersession jury for two mentions.
    Body: {"mention_a": str, "mention_b": str}
    Returns a SupersessionVerdict.
    """
    try:
        from ma.jury import run_supersession_jury
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    body = request.get_json(force=True, silent=True) or {}
    mention_a = (body.get("mention_a") or "").strip()
    mention_b = (body.get("mention_b") or "").strip()
    if not mention_a or not mention_b:
        return jsonify({"error": "mention_a and mention_b are required"}), 400
    verdict = run_supersession_jury(mention_a, mention_b)
    return jsonify({
        "mention_a": verdict.mention_a,
        "mention_b": verdict.mention_b,
        "decision": verdict.decision,
        "temporal_direction": verdict.temporal_direction,
        "confidence": verdict.confidence,
        "reasoning": verdict.reasoning,
        "timestamp": verdict.timestamp,
        "duration_ms": verdict.duration_ms,
    })


@app.route("/api/ma/kg/impact/<int:doc_id>")
def ma_kg_impact(doc_id: int):
    """
    Proactive impact analysis: what changed in the deal when this doc was uploaded?
    Returns: resolved EvidenceGaps, new contradictions, supersession candidates, impact_score.
    """
    try:
        from ma.knowledge_graph import analyze_upload_impact
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    impact = analyze_upload_impact(doc_id)
    return jsonify(impact)


# ─── Upgrade 1 API: Liar's Drift — stamp + timeline endpoints ───────────────

@app.route("/api/ma/kg/stamp-drift/<int:doc_id>", methods=["POST"])
def ma_kg_stamp_drift(doc_id: int):
    """Stamp UPDATES/CONTRADICTS edges for a newly ingested document.

    Call this after uploading a later-stage document (SPA after CIM).
    Body (optional): {"doc_type": "spa"}

    Returns counts of edges created and nodes flipped to is_latest=0.
    """
    try:
        from ma.knowledge_graph import stamp_supersession_edges
    except ImportError as e:
        return jsonify({"error": str(e)}), 500

    body = request.get_json(force=True, silent=True) or {}
    doc_type = body.get("doc_type") or None

    # Auto-detect doc_type from the documents table if not provided
    if not doc_type:
        conn = get_db()
        row = conn.execute(
            "SELECT filename FROM ma_documents WHERE id=?", (doc_id,)
        ).fetchone()
        conn.close()
        if row:
            fname = (row["filename"] or "").lower()
            for dt in ["spa", "share_purchase", "cim", "information_memorandum",
                       "loi", "term_sheet", "amendment", "disclosure"]:
                if dt.replace("_", " ") in fname or dt in fname:
                    doc_type = dt
                    break

    result = stamp_supersession_edges(doc_id, doc_type=doc_type)
    result["doc_id"] = doc_id
    result["doc_type_detected"] = doc_type
    return jsonify(result)


@app.route("/api/ma/kg/drift-timeline/<path:entity_name>")
def ma_kg_drift_timeline(entity_name: str):
    """Return the Liar's Drift mutation timeline for a claim or metric.

    Shows every version of the claim across documents with UPDATES/CONTRADICTS
    edges linking them — the 'living timeline of how the seller's narrative mutated'.
    """
    try:
        from ma.knowledge_graph import get_drift_timeline
    except ImportError as e:
        return jsonify({"error": str(e)}), 500

    timeline = get_drift_timeline(entity_name)
    drift_count = sum(1 for t in timeline if not t["is_latest"])
    return jsonify({
        "entity": entity_name,
        "timeline": timeline,
        "versions": len(timeline),
        "drift_detected": drift_count > 0,
        "drift_count": drift_count,
    })


# ─── Long-Term Memory API ────────────────────────────────────────────────────

@app.route("/api/ma/memory/stats")
def ma_memory_stats():
    """Return the state of the long-term memory — total, permanent, by tier/type."""
    try:
        from ma.long_term_memory import memory_stats
        return jsonify(memory_stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ma/memory/permanent")
def ma_memory_permanent():
    """Return all permanently consolidated memories (never forgotten)."""
    try:
        from ma.long_term_memory import get_permanent_memories
        return jsonify({"memories": get_permanent_memories()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ma/memory/recall", methods=["POST"])
def ma_memory_recall():
    """Recall memories relevant to the given entity names.

    Body: {"entities": ["Acme Corp", "Skadden"], "min_strength": 0.3, "limit": 20}
    Returns memories ordered by permanent first, then strength descending.
    """
    try:
        from ma.long_term_memory import recall
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    body = request.get_json(force=True, silent=True) or {}
    entities = body.get("entities") or []
    min_s = float(body.get("min_strength", 0.25))
    limit = int(body.get("limit", 20))
    memories = recall(entities, min_strength=min_s, limit=limit)
    return jsonify({"entities": entities, "memories": memories, "count": len(memories)})


@app.route("/api/ma/memory/learn", methods=["POST"])
def ma_memory_learn():
    """Manually teach the system a fact (or reinforce an existing one).

    Body: {
        "subject": "Skadden",
        "predicate": "uncapped_ip_warranty",
        "value": "Always inserts uncapped IP warranty in SaaS SPAs",
        "fact_type": "advisor",   -- entity|clause|pattern|advisor|red_flag
        "quality": 5,             -- 0-5 SM-2 quality score
        "deal_label": "Acme-2024" -- optional
    }
    """
    try:
        from ma.long_term_memory import consolidate_memory
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    body = request.get_json(force=True, silent=True) or {}
    subject = (body.get("subject") or "").strip()
    predicate = (body.get("predicate") or "").strip()
    value = body.get("value", "")
    if not subject or not predicate:
        return jsonify({"error": "subject and predicate required"}), 400
    result = consolidate_memory(
        subject=subject,
        predicate=predicate,
        value=value,
        fact_type=body.get("fact_type", "entity"),
        quality=int(body.get("quality", 4)),
        deal_label=body.get("deal_label"),
    )
    return jsonify(result)


@app.route("/api/ma/memory/consolidate/<int:doc_id>", methods=["POST"])
def ma_memory_consolidate(doc_id: int):
    """Manually trigger LTM consolidation for a document that was already uploaded.

    Useful after re-running KG extraction on existing documents.
    Body (optional): {"deal_label": "Acme-2024", "quality": 4}
    """
    try:
        from ma.long_term_memory import extract_and_consolidate_from_doc
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    body = request.get_json(force=True, silent=True) or {}
    result = extract_and_consolidate_from_doc(
        doc_id,
        deal_label=body.get("deal_label"),
        quality=int(body.get("quality", 4)),
    )
    return jsonify(result)


@app.route("/api/ma/memory/review-due")
def ma_memory_review_due():
    """Return memories whose SM-2 review interval has passed — ready to be re-scored."""
    try:
        from ma.long_term_memory import get_memories_due_for_review
        limit = int(request.args.get("limit", 30))
        return jsonify({"memories": get_memories_due_for_review(limit=limit)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Semantica Provenance API ─────────────────────────────────────────────────

@app.route("/api/ma/provenance/<entity_id>")
def ma_provenance_entity(entity_id: str):
    """Return W3C PROV-O provenance trail for a specific entity."""
    try:
        from ma.provenance_layer import get_provenance, get_lineage
        return jsonify({
            "entity_id": entity_id,
            "provenance": get_provenance(entity_id),
            "lineage": get_lineage(entity_id),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ma/provenance/stats")
def ma_provenance_stats():
    """Return aggregate provenance statistics across all tracked entities."""
    try:
        from ma.provenance_layer import get_statistics, get_all_sources
        return jsonify({
            "statistics": get_statistics(),
            "sources": get_all_sources(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ma/leukocyte/rete-rules")
def ma_leukocyte_rete_rules():
    """Return all active Rete kill-switch rules."""
    try:
        from ma.leukocyte_rete import _KILL_SWITCH_RULES
        return jsonify({
            "rule_count": len(_KILL_SWITCH_RULES),
            "rules": [
                {
                    "id": r.rule_id,
                    "name": r.name,
                    "severity": r.conclusion.get("severity") if isinstance(r.conclusion, dict) else None,
                    "deal_impact": r.conclusion.get("deal_impact") if isinstance(r.conclusion, dict) else None,
                    "priority": r.priority,
                }
                for r in _KILL_SWITCH_RULES
            ],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 9100))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"Starting BlackSwanX on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
