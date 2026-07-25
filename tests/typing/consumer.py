"""External consumer type-check test.

This file exercises the public API surface of eggcalc as an external consumer
would use it. It is type-checked with mypy in strict mode but is NOT executed
at runtime (it has no test functions — mypy --strict is the only consumer).

The file is excluded from pytest collection via conftest configuration.
"""

from __future__ import annotations

from typing import cast

from eggcalc import (
    EggCalcApp,
    evaluate,
    evaluate_async,
    evaluate_cached,
    evaluate_raw,
    evaluate_with_timeout,
    load_user_config,
)
from eggcalc.normalize import run
from eggcalc.units import Dimension, UnitExpression, UnitSpec, UnitValue


def check_evaluate() -> float:
    result: float = evaluate("5 + 3")
    return result


def check_evaluate_raw() -> float:
    result: float = evaluate_raw("five plus three")
    return result


def check_evaluate_cached() -> float:
    result: float = evaluate_cached("2 ** 10")
    return result


def check_evaluate_with_timeout() -> float:
    result: float = evaluate_with_timeout("sqrt(16)", timeout=5.0)
    return result


async def check_evaluate_async() -> float:
    result: float = await evaluate_async("1 + 1")
    return result


def check_unit_value() -> float:
    uv: UnitValue = UnitValue(30, "m")
    converted: UnitValue = uv.convert_to("ft")
    return float(cast(float, converted.value))


def check_unit_spec() -> str:
    spec: UnitSpec = UnitSpec(
        canonical="m",
        aliases=("meter", "metres"),
        dimension=Dimension(length=1),
        scale_to_base=1.0,
    )
    return spec.canonical


def check_unit_expression() -> str:
    from eggcalc.units import parse_unit_expression

    expr: UnitExpression = parse_unit_expression("m/s")
    return str(expr.dimension)


def check_eggcalc_app() -> float:
    app: EggCalcApp = EggCalcApp()
    result: float = app.calculate("5 + 3")
    return result


def check_run() -> float:
    from eggcalc.normalize import NORMALIZE, PATTERNS

    result, _ = run("five plus three", NORMALIZE, PATTERNS)
    return cast(float, result)


def check_load_user_config() -> None:
    load_user_config()
