#!/usr/bin/env python3
"""
EchoStack Quality Assurance & Testing Pipeline Runner
Executes real-world test cases across Unit, API, Integration, and WebSocket suites.
Intercepts test failures and displays structured error logs with full context and tracebacks.
"""

import sys
import os
import time
import io
import argparse
import pytest

# Ensure UTF-8 stdout/stderr streams for Windows compatibility
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add repository root to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)


def main():
    parser = argparse.ArgumentParser(description="EchoStack Automated Test Pipeline")
    parser.add_argument(
        "--suite", "-s",
        choices=["all", "unit", "api", "integration", "websocket"],
        default="all",
        help="Select target test suite to run (default: all)"
    )
    parser.add_argument(
        "--fail-fast", "-x",
        action="store_true",
        help="Stop pipeline on first test failure"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Increase verbosity level of test output"
    )
    parser.add_argument(
        "--keyword", "-k",
        type=str,
        default="",
        help="Only run tests matching the given expression"
    )
    args = parser.parse_args()

    # Determine test targets based on selected suite
    test_paths = []
    pipeline_dir = os.path.join(REPO_ROOT, "test_pipeline")

    if args.suite == "all":
        test_paths.append(pipeline_dir)
    elif args.suite == "unit":
        test_paths.append(os.path.join(pipeline_dir, "unit"))
    elif args.suite == "api":
        test_paths.append(os.path.join(pipeline_dir, "api"))
    elif args.suite == "integration":
        test_paths.append(os.path.join(pipeline_dir, "integration"))
    elif args.suite == "websocket":
        test_paths.append(os.path.join(pipeline_dir, "integration", "test_websocket_speech.py"))

    # Build pytest CLI arguments
    pytest_args = [
        "-c", os.path.join(pipeline_dir, "pytest.ini"),
        "-p", "test_pipeline.logging_plugin",
        "--tb=short",
    ]

    if args.fail_fast:
        pytest_args.append("-x")
    if args.verbose:
        pytest_args.append("-v")
    else:
        pytest_args.append("-q")
    if args.keyword:
        pytest_args.extend(["-k", args.keyword])

    pytest_args.extend(test_paths)

    # Header display
    banner = "=" * 80
    print(banner)
    print(" [ECHOSTACK QUALITY ASSURANCE TEST PIPELINE]")
    print(banner)
    print(f" Target Suite       : {args.suite.upper()}")
    print(f" Target Paths       : {', '.join(test_paths)}")
    print(f" Pytest Config      : {os.path.join(pipeline_dir, 'pytest.ini')}")
    print(banner + "\n")

    start_time = time.time()
    exit_code = pytest.main(pytest_args)
    elapsed = time.time() - start_time

    print("\n" + banner)
    if exit_code == 0:
        print(f" [SUCCESS] All test cases passed successfully in {elapsed:.2f}s!")
    else:
        print(f" [FAILURE] One or more test cases failed in {elapsed:.2f}s.")
        print(f" See detailed error logs above for failure diagnostics.")
    print(banner + "\n")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
