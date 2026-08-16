"""Reproducibility helpers: seeding and config snapshots."""

from __future__ import annotations

import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from common.io_utils import ensure_dir, write_json

CODE_VERSION_FALLBACK = "final-audit-v1"


def get_code_version() -> str:
    """Return short git commit hash, or fallback label for final-audit CSVs."""
    try:
        root = Path(__file__).resolve().parents[1]
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or CODE_VERSION_FALLBACK
    except Exception:
        return CODE_VERSION_FALLBACK


def set_global_seed(seed: int) -> random.Random:
    """Seed the stdlib RNG and return a dedicated Random instance."""
    random.seed(seed)
    return random.Random(seed)


def config_to_jsonable(obj: Any) -> Any:
    """Recursively convert config values into JSON-serializable forms."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Mapping):
        return {str(k): config_to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [config_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)


def snapshot_config(
    out_path: Path,
    config: Mapping[str, Any],
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    """Persist experiment configuration for reproducibility."""
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config": config_to_jsonable(dict(config)),
    }
    if extra:
        payload["extra"] = config_to_jsonable(dict(extra))
    write_json(out_path, payload)


def make_run_dir(results_root: Path, name: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = results_root / f"{name}_{stamp}"
    ensure_dir(path)
    return path
