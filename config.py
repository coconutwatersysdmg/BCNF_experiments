"""Global experiment configuration defaults."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
TPCH_DIR = DATA_DIR / "tpch"
LLM_QA_DIR = DATA_DIR / "llm_qa"

DEFAULT_SEED = 42
DEFAULT_TIMEOUT_SEC = 600.0
DEFAULT_WARMUP = 1
DEFAULT_REPEATS = 5
DEFAULT_MAX_DELETED_ORACLE = 15

# Static benchmark defaults
DEFAULT_SIZES = (1_000, 10_000, 100_000, 1_000_000)
OPTIONAL_SIZE = 10_000_000
DEFAULT_CONFLICT_RATIO = 0.1
DEFAULT_KEY_WIDTHS = (1, 2, 4)
DEFAULT_FD_COUNTS = (1, 2, 4, 8, 16)

# Sensitivity defaults
SENSITIVITY_N = 1_000_000
SENSITIVITY_CONFLICT_RATIOS = (0.01, 0.05, 0.10, 0.20, 0.40)
SENSITIVITY_FD_COUNTS = (1, 2, 4, 8, 16)
SENSITIVITY_KEY_WIDTHS = (1, 2, 4)
SENSITIVITY_SKEWS = ("uniform", "zipf_0.5", "zipf_1.0", "zipf_1.5")

# Incremental defaults
INCREMENTAL_BATCH_SIZES = (1, 10, 100, 1_000, 10_000)

# LLM QA defaults
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 64
QA_TARGET_COUNT = 900
QA_CATEGORY_RATIOS = {
    "No-Conflict": 0.30,
    "Irrelevant-Conflict": 0.30,
    "Answer-Critical-Conflict": 0.40,
}
CANDIDATE_ERROR_RATIOS = (0.01, 0.05, 0.10, 0.20)
