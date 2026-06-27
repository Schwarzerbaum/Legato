"""BlackSwanX - Configuration"""
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
DB_PATH = BASE_DIR / "blackswanx.db"


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # Models (auto-detected by hardware.py, can override)
    cluster_model: str = ""
    reasoning_model: str = ""

    # Database
    database_url: str = f"sqlite+aiosqlite:///{DB_PATH}"

    # Simulation defaults
    default_simulation_rounds: int = 5
    max_personas: int = 5
    max_debate_rounds: int = 3

    # Crawling
    max_posts_per_platform: int = 200
    crawl_timeout: int = 30

    # Accounting
    default_skr_variant: str = "SKR03"
    receipt_upload_dir: str = str(BASE_DIR / "receipts")
    invoice_upload_dir: str = str(BASE_DIR / "invoices")

    # Neural Organism
    neural_tick_interval_seconds: int = 60
    pheromone_default_decay_rate: float = 0.95  # 5% per minute
    signal_threshold_default: float = 0.3  # Min intensity to pass Node of Ranvier
    myelination_threshold: int = 10  # Signals before pathway gets myelinated
    myelination_score_increment: float = 0.1  # Per signal after threshold

    # Apoptosis (Immune System)
    apoptosis_threshold_ust_va: float = 0.995  # 99.5% consensus for tax filings
    apoptosis_threshold_report: float = 0.90  # 90% for reports
    apoptosis_threshold_categorization: float = 0.80  # 80% for booking categorization

    # AWEB (Vascular System)
    aweb_heartbeat_interval: int = 30  # Seconds between health checks
    aweb_max_fallback_depth: int = 3  # Max vein chain length
    aweb_degrade_after_failures: int = 3  # Degrade vein after N failures
    aweb_block_after_failures: int = 10  # Block vein after N failures

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "extra": "ignore"}


settings = Settings()
