"""Benchmark runner for eggcalc performance measurement."""

import statistics
import timeit
from typing import TypedDict


class BenchmarkStats(TypedDict):
    """Statistics from a benchmark run."""

    mean_seconds: float
    median_seconds: float
    stddev_seconds: float
    samples: int


def benchmark_evaluate(n: int = 10000, warmup: int = 100) -> BenchmarkStats:
    """Benchmark evaluate() for pre-normalized expressions.

    Args:
        n: Number of iterations
        warmup: Number of warmup runs before timing

    Returns:
        BenchmarkStats with timing results
    """
    from eggcalc import evaluate

    # Warmup
    for _ in range(warmup):
        evaluate("5 + 3")

    # Benchmark
    timer = timeit.Timer(lambda: evaluate("5 + 3"))
    times = timer.repeat(repeat=10, number=n)

    times_seconds = [t / n for t in times]
    return BenchmarkStats(
        mean_seconds=statistics.mean(times_seconds),
        median_seconds=statistics.median(times_seconds),
        stddev_seconds=statistics.stdev(times_seconds) if len(times_seconds) > 1 else 0,
        samples=n,
    )


def benchmark_evaluate_raw(n: int = 10000, warmup: int = 100) -> BenchmarkStats:
    """Benchmark evaluate_raw() for natural language expressions.

    Args:
        n: Number of iterations
        warmup: Number of warmup runs before timing

    Returns:
        BenchmarkStats with timing results
    """
    from eggcalc import evaluate_raw

    # Warmup
    for _ in range(warmup):
        evaluate_raw("five plus three")

    # Benchmark
    timer = timeit.Timer(lambda: evaluate_raw("five plus three"))
    times = timer.repeat(repeat=10, number=n)

    times_seconds = [t / n for t in times]
    return BenchmarkStats(
        mean_seconds=statistics.mean(times_seconds),
        median_seconds=statistics.median(times_seconds),
        stddev_seconds=statistics.stdev(times_seconds) if len(times_seconds) > 1 else 0,
        samples=n,
    )


def benchmark_normalize(n: int = 10000, warmup: int = 100) -> BenchmarkStats:
    """Benchmark normalize_expression() for natural language input.

    Args:
        n: Number of iterations
        warmup: Number of warmup runs before timing

    Returns:
        BenchmarkStats with timing results
    """
    from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression

    # Warmup
    for _ in range(warmup):
        normalize_expression("five plus three", NORMALIZE, PATTERNS)

    # Benchmark
    timer = timeit.Timer(lambda: normalize_expression("five plus three", NORMALIZE, PATTERNS))
    times = timer.repeat(repeat=10, number=n)

    times_seconds = [t / n for t in times]
    return BenchmarkStats(
        mean_seconds=statistics.mean(times_seconds),
        median_seconds=statistics.median(times_seconds),
        stddev_seconds=statistics.stdev(times_seconds) if len(times_seconds) > 1 else 0,
        samples=n,
    )


def benchmark_evaluate_cached(n: int = 10000, warmup: int = 100) -> BenchmarkStats:
    """Benchmark evaluate_cached() for repeated expressions.

    Args:
        n: Number of iterations (after single warmup)
        warmup: Number of warmup runs before timing

    Returns:
        BenchmarkStats with timing results
    """
    from eggcalc import evaluate_cached

    # One warmup - cached results used for all iterations
    evaluate_cached("five plus three")

    # Benchmark - all hits cache
    timer = timeit.Timer(lambda: evaluate_cached("five plus three"))
    times = timer.repeat(repeat=10, number=n)

    times_seconds = [t / n for t in times]
    return BenchmarkStats(
        mean_seconds=statistics.mean(times_seconds),
        median_seconds=statistics.median(times_seconds),
        stddev_seconds=statistics.stdev(times_seconds) if len(times_seconds) > 1 else 0,
        samples=n,
    )


def benchmark_all() -> dict[str, BenchmarkStats]:
    """Run all benchmarks and return results.

    Returns:
        Dict of benchmark name to BenchmarkStats
    """
    print("Running benchmarks...")
    print()

    results: dict[str, BenchmarkStats] = {}

    print("benchmark_evaluate (pre-normalized: '5+3')...")
    results["evaluate_simple"] = benchmark_evaluate()
    print(f"  mean: {results['evaluate_simple']['mean_seconds']:.2e}s")

    print()
    print("benchmark_evaluate_raw (NL: 'five plus three')...")
    results["evaluate_raw_nl"] = benchmark_evaluate_raw()
    print(f"  mean: {results['evaluate_raw_nl']['mean_seconds']:.2e}s")

    print()
    print("benchmark_normalize (normalize only)...")
    results["normalize_only"] = benchmark_normalize()
    print(f"  mean: {results['normalize_only']['mean_seconds']:.2e}s")

    print()
    print("benchmark_evaluate_cached (repeated NL)...")
    results["evaluate_cached"] = benchmark_evaluate_cached()
    print(f"  mean: {results['evaluate_cached']['mean_seconds']:.2e}s")

    return results


if __name__ == "__main__":
    results = benchmark_all()
    print()
    print("=== Summary ===")
    for name, stats in results.items():
        print(f"{name}: {stats['mean_seconds']:.2e}s (stddev: {stats['stddev_seconds']:.2e})")
