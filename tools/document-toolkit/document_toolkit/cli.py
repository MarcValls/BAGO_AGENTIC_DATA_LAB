"""Small JSON CLI sharing the public Python API."""
from pathlib import Path
import argparse
import json
import sys

from .core import Limits, OPERATIONS, capabilities, execute


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded document tools; input is never modified.")
    parser.add_argument("operation", choices=(*OPERATIONS, "capabilities"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--arguments", default="{}", help="JSON object; @file reads JSON arguments from a file")
    parser.add_argument("--limits", default="{}", help="JSON object overriding bounded limits")
    args = parser.parse_args(argv)
    try:
        if args.operation == "capabilities":
            result = capabilities()
        else:
            raw = Path(args.arguments[1:]).read_text(encoding="utf8") if args.arguments.startswith("@") else args.arguments
            result = execute(args.operation, args.root, json.loads(raw), limits=Limits(**json.loads(args.limits)))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 1 if result.get("state") == "FAILED" else 0
    except (ValueError, OSError, TypeError) as error:
        print(json.dumps({"state": "FAILED", "errors": [{"code": "INVALID_CLI_ARGUMENTS"}]}))
        return 2
