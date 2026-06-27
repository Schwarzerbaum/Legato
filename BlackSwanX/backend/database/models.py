"""SQLite database models for BlackSwanX — Biomimetic Financial Organism.

Layers:
  1. Prediction Engine (original) — Topics, Posts, Personas, Simulations, Reports
  2. Accounting Organism — Chart of Accounts, Bookings, Invoices, USt-VA, Bank Transactions
  3. Neural Communication — Pheromones, Pathways, Signals, AWEB Veins, Apoptosis Logs
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Date, JSON, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Topic(Base):
    """A user-submitted analysis topic."""
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    query = Column(String(500), nullable=False)
    status = Column(String(50), default="pending")  # pending, crawling, analyzing, simulating, complete
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    posts = relationship("RawPost", back_populates="topic", cascade="all, delete-orphan")
    personas = relationship("SocialPersona", back_populates="topic", cascade="all, delete-orphan")
    simulations = relationship("Simulation", back_populates="topic", cascade="all, delete-orphan")


class RawPost(Base):
    """A crawled post from any platform."""
    __tablename__ = "raw_posts"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    platform = Column(String(50), nullable=False)  # reddit, twitter, youtube, web
    author = Column(String(200))
    content = Column(Text, nullable=False)
    url = Column(String(1000))
    engagement = Column(Integer, default=0)  # likes + comments + shares
    published_at = Column(DateTime)
    crawled_at = Column(DateTime, default=datetime.utcnow)
    embedding_cluster = Column(Integer)  # Set during compression

    topic = relationship("Topic", back_populates="posts")


class SocialPersona(Base):
    """A compressed 'Vibe' — cluster of similar opinions."""
    __tablename__ = "social_personas"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    label = Column(String(200), nullable=False)  # e.g., "Skeptical Technologists"
    vibe_summary = Column(Text, nullable=False)  # Compressed description
    post_count = Column(Integer, default=0)
    avg_sentiment = Column(Float, default=0.0)  # -1.0 to 1.0
    platforms = Column(JSON)  # {"reddit": 45, "twitter": 30, "youtube": 25}
    representative_quotes = Column(JSON)  # Top 3 representative posts
    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic", back_populates="personas")


class BlackSwanXFlow(Base):
    """Tracks how an idea moves across platforms."""
    __tablename__ = "blackswanx_flows"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    concept = Column(String(300), nullable=False)  # The idea/meme being tracked
    origin_platform = Column(String(50))
    flow_path = Column(JSON)  # [{"platform": "reddit", "timestamp": ..., "volume": ...}, ...]
    velocity = Column(Float)  # How fast it spread
    created_at = Column(DateTime, default=datetime.utcnow)


class Simulation(Base):
    """A prediction simulation run."""
    __tablename__ = "simulations"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, running, complete
    total_rounds = Column(Integer, default=5)
    current_round = Column(Integer, default=0)
    config = Column(JSON)  # Simulation parameters
    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic", back_populates="simulations")
    rounds = relationship("SimulationRound", back_populates="simulation", cascade="all, delete-orphan")


class SimulationRound(Base):
    """A single round of agent debate."""
    __tablename__ = "simulation_rounds"

    id = Column(Integer, primary_key=True)
    simulation_id = Column(Integer, ForeignKey("simulations.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    provocateur_output = Column(Text)  # Agent Provocateur's argument
    whale_output = Column(Text)  # Sentiment Whale's argument
    catalyst_output = Column(Text)  # Catalyst's argument
    moderator_synthesis = Column(Text)  # Forum moderator summary
    recursive_challenge = Column(Text)  # Self-critique round
    pressure_points = Column(JSON)  # Identified pressure points this round
    created_at = Column(DateTime, default=datetime.utcnow)

    simulation = relationship("Simulation", back_populates="rounds")


class Report(Base):
    """A generated Decision-Ready Map."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    simulation_id = Column(Integer, ForeignKey("simulations.id"))
    title = Column(String(500))
    content_md = Column(Text)  # Markdown content
    content_html = Column(Text)  # Rendered HTML
    pressure_points = Column(JSON)  # Final pressure point map
    token_usage = Column(JSON)  # {"cluster": 0, "reasoning": 0, "total": 0}
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# LAYER 2: ACCOUNTING ORGANISM
# ============================================================

class ChartOfAccounts(Base):
    """German chart of accounts (Kontenrahmen) — SKR03 or SKR04."""
    __tablename__ = "chart_of_accounts"

    id = Column(Integer, primary_key=True)
    code = Column(String(10), nullable=False)  # e.g. "1200" for Bank
    name = Column(String(200), nullable=False)  # e.g. "Bank"
    account_type = Column(String(20), nullable=False)  # asset, liability, equity, revenue, expense
    skr_variant = Column(String(10), nullable=False, default="SKR03")  # SKR03 or SKR04
    parent_code = Column(String(10))  # For hierarchical grouping
    is_custom = Column(Boolean, default=False)  # User-added accounts
    tax_relevant = Column(Boolean, default=True)  # Relevant for tax calculations

    __table_args__ = (
        UniqueConstraint("code", "skr_variant", name="uq_account_code_variant"),
    )


class FiscalYear(Base):
    """Geschaeftsjahr — accounting period."""
    __tablename__ = "fiscal_years"

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False, unique=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_closed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("Booking", back_populates="fiscal_year")


class Booking(Base):
    """Double-entry booking — GoBD-compliant with immutability.

    GoBD rules:
    - Sequential gapless booking_number per fiscal year
    - is_locked = True makes booking immutable (no edits, no deletes)
    - Corrections only via Stornobuchung (reverse booking)
    - AuditLog tracks all changes
    """
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    booking_number = Column(Integer, nullable=False)  # Sequential, gapless per fiscal year
    date = Column(Date, nullable=False)
    debit_account_code = Column(String(10), nullable=False)  # Soll
    credit_account_code = Column(String(10), nullable=False)  # Haben
    amount = Column(Float, nullable=False)  # Always positive
    tax_rate = Column(Float, default=0.0)  # 0.19, 0.07, 0.0
    tax_amount = Column(Float, default=0.0)
    description = Column(String(500))  # Buchungstext
    document_ref = Column(String(200))  # Belegfeld / Belegnummer
    receipt_path = Column(String(500))  # Path to scanned receipt
    is_locked = Column(Boolean, default=False)  # GoBD: locked = immutable
    is_storno = Column(Boolean, default=False)  # True if this is a reversal
    storno_of_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)  # FK to original if storno
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"), nullable=False)
    pheromone_intensity = Column(Float, default=0.0)  # Living Ledger: how much agent attention
    created_at = Column(DateTime, default=datetime.utcnow)

    fiscal_year = relationship("FiscalYear", back_populates="bookings")
    storno_of = relationship("Booking", remote_side="Booking.id", foreign_keys=[storno_of_id])


class Invoice(Base):
    """Rechnung — section 14 UStG compliant invoice.

    Required fields per section 14 UStG:
    - Rechnungsnummer (sequential, no gaps)
    - Rechnungsdatum + Leistungsdatum
    - Seller: Name, Address, Steuernummer or USt-IdNr
    - Buyer: Name, Address
    - Line items with Nettobetrag, USt-Satz, USt-Betrag, Bruttobetrag
    """
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    invoice_number = Column(String(50), nullable=False, unique=True)  # RE-2026-0001
    date = Column(Date, nullable=False)  # Rechnungsdatum
    service_date = Column(Date)  # Leistungsdatum
    due_date = Column(Date)  # Faelligkeitsdatum
    # Seller (Rechnungssteller)
    seller_name = Column(String(200))
    seller_address = Column(Text)
    seller_ust_id = Column(String(20))  # DE123456789
    seller_steuernummer = Column(String(20))  # 12/345/67890
    seller_tax_id = Column(String(20))  # Steuer-Identifikationsnummer
    # Buyer (Rechnungsempfaenger)
    customer_name = Column(String(200), nullable=False)
    customer_address = Column(Text)
    customer_ust_id = Column(String(20))  # For reverse charge
    # Amounts
    line_items = Column(JSON, nullable=False)  # [{description, quantity, unit_price, tax_rate, net, tax, gross}]
    subtotal = Column(Float, nullable=False)  # Netto gesamt
    tax_total = Column(Float, nullable=False)  # USt gesamt
    total = Column(Float, nullable=False)  # Brutto gesamt
    # Status
    status = Column(String(20), default="draft")  # draft, sent, paid, overdue
    payment_date = Column(Date)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BankTransaction(Base):
    """Imported bank transaction for matching/categorization."""
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)  # Positive = credit, negative = debit
    currency = Column(String(3), default="EUR")
    counterparty = Column(String(200))  # Empfaenger/Auftraggeber
    reference = Column(String(500))  # Verwendungszweck
    raw_text = Column(Text)  # Full bank statement line
    category_code = Column(String(10))  # Mapped SKR account code
    is_matched = Column(Boolean, default=False)
    matched_booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    import_source = Column(String(50))  # "fints", "csv", "manual"
    imported_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """GoBD Verfahrensdokumentation — immutable audit trail.

    Every create, modify, lock, storno, and apoptosis event is logged.
    This table itself is append-only — no updates, no deletes.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False)  # booking, invoice, fiscal_year, ust_va
    entity_id = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # create, modify, lock, storno, apoptosis
    old_value = Column(JSON)  # Previous state (null for create)
    new_value = Column(JSON)  # New state
    user_action = Column(String(200))  # Description of what triggered this
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class UStVoranmeldung(Base):
    """Umsatzsteuer-Voranmeldung — VAT pre-registration.

    Kennzahlen map to ELSTER form fields.
    Apoptosis: if agent consensus < 99.5%, status = 'apoptosed' and filing is blocked.
    """
    __tablename__ = "ust_voranmeldungen"

    id = Column(Integer, primary_key=True)
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)  # 1-12 (monthly) or 3/6/9/12 (quarterly)
    # Core Kennzahlen
    kennzahl_81 = Column(Float, default=0.0)  # Steuerpflichtige Umsaetze 19%
    kennzahl_86 = Column(Float, default=0.0)  # Steuerpflichtige Umsaetze 7%
    kennzahl_36 = Column(Float, default=0.0)  # USt auf KZ81 (19%)
    kennzahl_35 = Column(Float, default=0.0)  # USt auf KZ86 (7%)
    kennzahl_66 = Column(Float, default=0.0)  # Abziehbare Vorsteuer
    kennzahl_83 = Column(Float, default=0.0)  # Verbleibende USt-Vorauszahlung (Zahllast)
    kennzahl_67 = Column(Float, default=0.0)  # Vorsteuer aus innergemeinschaftlichem Erwerb
    kennzahl_61 = Column(Float, default=0.0)  # Steuerfreie Umsaetze mit Vorsteuerabzug (Export)
    kennzahl_45 = Column(Float, default=0.0)  # Innergemeinschaftliche Lieferungen
    kennzahl_21 = Column(Float, default=0.0)  # Nicht steuerbare Umsaetze
    # Organism fields
    consensus_score = Column(Float, default=1.0)  # Agent agreement level (0-1)
    status = Column(String(20), default="draft")  # draft, submitted, apoptosed
    apoptosis_reason = Column(Text)  # Why the immune system killed this filing
    created_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("period_year", "period_month", name="uq_ust_va_period"),
    )


# ============================================================
# LAYER 3: NEURAL COMMUNICATION — THE ORGANISM
# ============================================================

class PheromoneDeposit(Base):
    """Digital pheromone — stigmergic communication between agents.

    Agents deposit pheromones on entities (bookings, invoices, etc).
    Multiple deposits on same entity amplify (super-linear).
    Pheromones evaporate over time — old signals fade.
    """
    __tablename__ = "pheromone_deposits"

    id = Column(Integer, primary_key=True)
    pheromone_type = Column(String(30), nullable=False)
    # Types: asset_trail, anomaly_scent, urgency_alarm, opportunity_bloom,
    #        danger_marker, state_residue, regulatory_wind, liquidity_trace
    intensity = Column(Float, nullable=False)  # 0.0 - 1.0
    decay_rate = Column(Float, default=0.95)  # Per-minute decay (0.95 = 5% per min)
    position_node = Column(String(100), nullable=False)  # Agent/node identifier
    target_entity_type = Column(String(50))  # "booking", "invoice", "ust_va" etc.
    target_entity_id = Column(Integer)  # FK to the specific entity
    payload = Column(JSON)  # Data cargo
    source_agent = Column(String(100), nullable=False)  # Which agent deposited
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # When intensity drops below 0.01


class NeuralPathway(Base):
    """Communication channel between nodes — myelinated or unmyelinated.

    Myelinated = fast (signal jumps between nodes, skipping intermediates)
    Unmyelinated = slow (signal traverses every intermediate node)
    Myelination is EARNED — pathways carrying frequent signals auto-optimize.
    """
    __tablename__ = "neural_pathways"

    id = Column(Integer, primary_key=True)
    from_node = Column(String(100), nullable=False)
    to_node = Column(String(100), nullable=False)
    pathway_type = Column(String(20), default="unmyelinated")  # myelinated, unmyelinated
    myelination_score = Column(Float, default=0.0)  # 0.0-1.0, >= 0.7 = myelinated
    signal_count = Column(Integer, default=0)
    avg_priority = Column(Float, default=0.0)  # Average priority of signals carried
    last_signal_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    signals = relationship("NeuralSignalLog", back_populates="pathway")

    __table_args__ = (
        UniqueConstraint("from_node", "to_node", name="uq_pathway_nodes"),
    )


class NeuralSignalLog(Base):
    """Record of a neural signal transmission.

    Tracks whether signal propagated or was stopped at a Node of Ranvier.
    """
    __tablename__ = "neural_signal_log"

    id = Column(Integer, primary_key=True)
    pathway_id = Column(Integer, ForeignKey("neural_pathways.id"), nullable=True)
    signal_type = Column(String(50), nullable=False)  # fraud_alert, tax_deadline, anomaly, etc.
    priority = Column(String(10), nullable=False)  # CRITICAL, HIGH, NORMAL, LOW
    payload = Column(JSON)
    intensity = Column(Float, nullable=False)  # 0.0-1.0
    propagated = Column(Boolean, default=False)  # Did signal reach target?
    stopped_at_node = Column(String(100))  # Which node killed it (if any)
    apoptosis_triggered = Column(Boolean, default=False)  # Did this signal trigger apoptosis?
    created_at = Column(DateTime, default=datetime.utcnow)

    pathway = relationship("NeuralPathway", back_populates="signals")


class AWEBVein(Base):
    """Adaptive Web vein — data delivery pathway.

    AWEB = the vascular system. Data is oxygen. Agents are cells.
    If a vein blocks (API timeout, crawler failure), AWEB reroutes through fallback.
    """
    __tablename__ = "aweb_veins"

    id = Column(Integer, primary_key=True)
    vein_id = Column(String(50), nullable=False, unique=True)  # e.g. "bank_api_sparkasse"
    source_type = Column(String(30), nullable=False)  # bank_api, crawler, file_import, ollama
    endpoint_url = Column(String(500))  # The actual endpoint
    status = Column(String(20), default="healthy")  # healthy, degraded, blocked
    last_heartbeat = Column(DateTime)
    avg_latency_ms = Column(Float, default=0.0)
    failure_count = Column(Integer, default=0)
    fallback_vein_id = Column(String(50))  # Fall back to this vein if blocked
    created_at = Column(DateTime, default=datetime.utcnow)


class ApoptosisLog(Base):
    """Record of immune system self-termination events.

    When agent consensus drops below threshold, the system kills
    that reporting branch rather than submitting incorrect data.
    """
    __tablename__ = "apoptosis_logs"

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False)  # ust_va, report, booking_batch
    entity_id = Column(Integer, nullable=False)
    trigger_reason = Column(Text, nullable=False)
    consensus_score = Column(Float, nullable=False)  # What the agents agreed on
    threshold_required = Column(Float, nullable=False)  # What was needed
    agents_involved = Column(JSON)  # List of agent IDs that participated
    timestamp = Column(DateTime, default=datetime.utcnow)
