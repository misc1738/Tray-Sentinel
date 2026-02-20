from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    ledger_path: Path
    db_path: Path
    evidence_store_dir: Path


def get_settings() -> Settings:
    base = Path(__file__).resolve().parents[1]
    data_dir = base / "data"
    return Settings(
        base_dir=base,
        data_dir=data_dir,
        ledger_path=data_dir / "ledger.jsonl",
        db_path=data_dir / "sentinel.db",
        evidence_store_dir=base / "evidence_store",
    )
