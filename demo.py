"""Run the local one-command governed knowledge-agent demo.

The launcher keeps the public five-artifact contract and accepts the CI
portfolio flags used by older callers. It runs in the active Python
environment; install ``requirements.txt`` first when needed.
"""

from __future__ import annotations

import argparse

from scripts.run_public_e2e_demo import main as run_public_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        "--artifacts-dir",
        dest="artifacts_dir",
        help="directory for the linked JSON artifact bundle (default: ./demo_output)",
    )
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="use the active Python environment (the launcher never creates a venv)",
    )
    parser.add_argument("--json", action="store_true", help="print the JSON summary")
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="refresh evidence/public_e2e_demo.md after a passing run",
    )
    parser.add_argument("--check", action="store_true", help="run the local demo checks")
    args = parser.parse_args(argv)

    output_dir = args.artifacts_dir or "demo_output"
    delegated = ["--artifacts-dir", output_dir]
    if args.write_evidence:
        delegated.append("--write-evidence")
    if args.check:
        delegated.append("--check")
    return run_public_demo(delegated)


if __name__ == "__main__":
    raise SystemExit(main())
