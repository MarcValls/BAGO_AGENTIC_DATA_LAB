"""Trusted local operator bootstrap. Stdout contains a one-time SECRET API key.

Do not redirect stdout to evidence/logs. Agent registration is a separate action.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.execution.gex_control import provision, ControlError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--principal", required=True)
    parser.add_argument("--agent-id", required=True)
    args = parser.parse_args()
    try:
        # Reuse exact repository saved-agent loader; no alternate bootstrap API.
        from src.api.server import _load_agent
        result = provision(state_dir=args.state_dir, workspace=args.workspace, principal_id=args.principal,
                           agent_id=args.agent_id, load_agent=_load_agent)
    except Exception as exc:
        code = exc.code if isinstance(exc, ControlError) else "PROVISIONING_FAILED"
        print(json.dumps({"error": code}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
