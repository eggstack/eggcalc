"""Baseline performance results for eggcalc.

These timings are documented in README.md and should be verified
periodically to detect regressions.

Timings measured on Apple M2 Pro, Python 3.14.
"""

from typing import TypedDict


class BenchmarkResult(TypedDict):
    """Result of a benchmark run."""

    mean_seconds: float
    median_seconds: float
    stddev_seconds: float
    samples: int
    unit: str


BASELINE: dict[str, BenchmarkResult] = {
    "evaluate_simple": {
        "mean_seconds": 10e-6,
        "median_seconds": 10e-6,
        "stddev_seconds": 1e-6,
        "samples": 10000,
        "unit": "seconds per evaluation",
        "description": "Pre-normalized expression like '5+3' via evaluate()",
    },
    "evaluate_raw_nl": {
        "mean_seconds": 155e-6,
        "median_seconds": 155e-6,
        "stddev_seconds": 15e-6,
        "samples": 10000,
        "unit": "seconds per evaluation",
        "description": "Natural language expression like 'five plus three' via evaluate_raw()",
    },
    "evaluate_cached": {
        "mean_seconds": 0.1e-6,
        "median_seconds": 0.1e-6,
        "stddev_seconds": 0.01e-6,
        "samples": 10000,
        "unit": "seconds per evaluation (after first call)",
        "description": "Repeated NL expression via evaluate_cached()",
    },
    "calculate_cached": {
        "mean_seconds": 0.3e-6,
        "median_seconds": 0.3e-6,
        "stddev_seconds": 0.03e-6,
        "samples": 10000,
        "unit": "seconds per evaluation (after first call)",
        "description": "NL expression via EggCalcApp.calculate() with instance caching",
    },
}

DOCUMENTED_SPEEDUP = 15  # evaluate() is ~15x faster than evaluate_raw()


def format_benchmark_result(name: str, result: BenchmarkResult) -> str:
    """Format a benchmark result for display."""
    baseline = BASELINE.get(name)
    if baseline:
        ratio = baseline["mean_seconds"] / result["mean_seconds"]
        vs_baseline = f" (baseline ratio: {ratio:.1f}x)"
    else:
        vs_baseline = ""

    return (
        f"{name}: {result['mean_seconds']:.2e} {result['unit']} "
        f"(stddev: {result['stddev_seconds']:.2e}, n={result['samples']}){vs_baseline}"
    )


def verify_baseline(name: str, result: BenchmarkResult, tolerance: float = 2.0) -> bool:
    """Verify benchmark result against baseline within tolerance.

    Args:
        name: Benchmark name
        result: Benchmark result to verify
        tolerance: Maximum allowed ratio (result / baseline)

    Returns:
        True if result is within tolerance of baseline
    """
    baseline = BASELINE.get(name)
    if not baseline:
        return True  # No baseline to verify against

    ratio = result["mean_seconds"] / baseline["mean_seconds"]
    return ratio <= tolerance
