#!/usr/bin/env python3
"""Convert pytest JUnit XML to a canonical lane summary JSON.

Reads JUnit XML (produced by pytest --junitxml) and emits a structured JSON
summary with exact test counts, duration, and lane identity.

Usage::

    python scripts/junit_to_lane_summary.py \\
        --junitxml lane-results.xml \\
        --os ubuntu-latest \\
        --python-version 3.12 \\
        --job-name "test (ubuntu-latest, 3.12)" \\
        --output lane-summary-ubuntu-3.12.json
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_junit(xml_path: Path) -> dict[str, object]:
    """Parse JUnit XML and return test counts and duration."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    collected = 0
    passed = 0
    skipped = 0
    xfailed = 0
    xpassed = 0
    failed = 0
    errors = 0
    duration = 0.0

    # Handle both <testsuites> and <testsuite> root elements
    if root.tag == "testsuites":
        suites = root.findall("testsuite")
    elif root.tag == "testsuite":
        suites = [root]
    else:
        suites = []

    for suite in suites:
        duration += float(suite.get("time", 0))
        for tc in suite.findall("testcase"):
            collected += 1
            # Check for failure, error, skipped, etc.
            if tc.find("failure") is not None:
                failed += 1
            elif tc.find("error") is not None:
                errors += 1
            elif tc.find("skipped") is not None:
                skipped += 1
                # Check for xfail vs xpass via attributes or message
                skipped_el = tc.find("skipped")
                message = (skipped_el.get("message", "") if skipped_el is not None else "").lower()
                if "xfail" in message:
                    xfailed += 1
            else:
                passed += 1

    return {
        "collected": collected,
        "passed": passed,
        "skipped": skipped,
        "xfailed": xfailed,
        "xpassed": xpassed,
        "failed": failed,
        "errors": errors,
        "duration_seconds": round(duration, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junitxml", type=Path, required=True)
    parser.add_argument("--os", type=str, required=True, help="OS runner label")
    parser.add_argument("--python-version", type=str, required=True)
    parser.add_argument("--job-name", type=str, required=True)
    parser.add_argument("--workflow-run-id", type=str, default="")
    parser.add_argument("--workflow-head-sha", type=str, default="")
    parser.add_argument("--conclusion", type=str, default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    counts = parse_junit(args.junitxml)

    summary = {
        "os": args.os,
        "python_version": args.python_version,
        "job_name": args.job_name,
        "workflow_run_id": args.workflow_run_id,
        "workflow_head_sha": args.workflow_head_sha,
        "conclusion": args.conclusion,
        **counts,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
