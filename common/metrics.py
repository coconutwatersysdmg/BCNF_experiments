"""Timing, memory, and statistical helpers for benchmarks."""

from __future__ import annotations

import statistics
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Iterable, Optional


@dataclass
class MemorySnapshot:
    python_peak_mb: float = 0.0
    rss_peak_mb: Optional[float] = None


@dataclass
class TimedRun:
    elapsed_sec: float
    python_peak_mb: float
    rss_peak_mb: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _rss_mb() -> Optional[float]:
    try:
        import psutil  # type: ignore

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return None


@contextmanager
def measure_resources(track_memory: bool = True) -> Generator[dict[str, Any], None, None]:
    """Context manager recording wall time and peak memory.

    - python_peak_mb: tracemalloc peak during THIS context (Python allocator
      extra allocation; NOT total process physical RAM). Each call resets the
      peak (or starts a fresh tracemalloc session).
    - rss_peak_mb: process RSS via psutil if available. Unreliable as a primary
      paper metric when multiple algorithms share one process (allocator reuse).
    """
    info: dict[str, Any] = {
        "elapsed_sec": 0.0,
        "python_peak_mb": 0.0,
        "rss_peak_mb": None,
    }
    started_tracemalloc = False
    if track_memory:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            started_tracemalloc = True
        else:
            tracemalloc.reset_peak()
    rss_before = _rss_mb()
    t0 = time.perf_counter()
    try:
        yield info
    finally:
        info["elapsed_sec"] = time.perf_counter() - t0
        if track_memory:
            _, peak = tracemalloc.get_traced_memory()
            info["python_peak_mb"] = peak / (1024 * 1024)
            if started_tracemalloc:
                tracemalloc.stop()
        rss_after = _rss_mb()
        if rss_before is not None and rss_after is not None:
            info["rss_peak_mb"] = max(rss_before, rss_after)
        elif rss_after is not None:
            info["rss_peak_mb"] = rss_after


def median(values: Iterable[float]) -> float:
    xs = list(values)
    if not xs:
        return float("nan")
    return float(statistics.median(xs))


def mean(values: Iterable[float]) -> float:
    xs = list(values)
    if not xs:
        return float("nan")
    return float(statistics.mean(xs))


def stdev(values: Iterable[float]) -> float:
    xs = list(values)
    if len(xs) < 2:
        return 0.0
    return float(statistics.stdev(xs))


def percentile(values: Iterable[float], p: float) -> float:
    xs = sorted(values)
    if not xs:
        return float("nan")
    if len(xs) == 1:
        return float(xs[0])
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return float(xs[f])
    return float(xs[f] + (xs[c] - xs[f]) * (k - f))


def summarize_runs(values: Iterable[float]) -> dict[str, float]:
    xs = list(values)
    return {
        "median": median(xs),
        "mean": mean(xs),
        "std": stdev(xs),
        "p25": percentile(xs, 25),
        "p75": percentile(xs, 75),
    }
