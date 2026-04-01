from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    ledger_path: Path
    db_path: Path
    evidence_store_dir: Path
    evidence_key_path: Path
    debug: bool
    log_level: str


def get_settings() -> Settings:
    base = Path(__file__).resolve().parents[1]
    data_dir = base / "data"
    
    # Load environment variables
    debug = os.getenv("DEBUG", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    return Settings(
        base_dir=base,
        data_dir=data_dir,
        ledger_path=data_dir / "ledger.jsonl",
        db_path=data_dir / "sentinel.db",
        evidence_store_dir=base / "evidence_store",
        evidence_key_path=data_dir / "keys" / "evidence.fernet.key",
        debug=debug,
        log_level=log_level,
    )
