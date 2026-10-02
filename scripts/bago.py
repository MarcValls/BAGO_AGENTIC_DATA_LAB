"""Simple command-line entry point for the local BAGO client demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SCRIPTS_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_public_e2e_demo import (  # noqa: E402
    CLIENT_NAME,
    CASE_DESCRIPTION,
    EVIDENCE_PATH,
    QUERY,
    render_evidence,
    run_demo,
    summary,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bago",
        description="Ejecuta la demo local del cliente ficticio Bruma Market.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="ejecuta el caso de entrega exprés")
    demo.add_argument("--json", action="store_true", help="imprime el resultado JSON")
    demo.add_argument(
        "--write-evidence",
        action="store_true",
        help="actualiza evidence/public_e2e_demo.md tras un resultado PASS",
    )
    args = parser.parse_args(argv)

    result = run_demo()
    if args.write_evidence:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(render_evidence(result), encoding="utf-8")

    if args.json:
        print(json.dumps(summary(result), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        details = summary(result)
        print(f"BAGO · Demo de cliente ficticio — {CLIENT_NAME}")
        print(f"Caso: {CASE_DESCRIPTION}")
        print(f"Pregunta: {QUERY}")
        print(f"Respuesta: {result['agent_run'].answer}")
        print(
            "Validación: "
            f"RAG {details['retrieval_hits']} fuentes · "
            f"ontología {details['ontology_outcome']} · "
            f"sandbox {details['sandbox_status']} · "
            f"eval {details['evaluation_status']} ({details['evaluation_score']:.2f})"
        )
        print("Coste del demo: 0 USD · servicios externos: no utilizados")
        if args.write_evidence:
            print(f"Evidencia: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
