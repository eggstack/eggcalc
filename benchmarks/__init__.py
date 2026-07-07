"""Benchmark suite for eggcalc performance measurement."""

from .results import BASELINE, format_benchmark_result
from .run import (
    benchmark_all,
    benchmark_evaluate,
    benchmark_evaluate_cached,
    benchmark_evaluate_raw,
    benchmark_normalize,
)

__all__ = [
    "benchmark_evaluate",
    "benchmark_evaluate_raw",
    "benchmark_evaluate_cached",
    "benchmark_normalize",
    "benchmark_all",
    "BASELINE",
    "format_benchmark_result",
]
