"""Generate a reviewable ontology proposal from documentation files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from metadata.ontology_generator import (  # noqa: E402
    OntologyGenerator,
    OntologyProposal,
    OntologyValidationReport,
    OntologyValidator,
    ProposalStatus,
)


DEFAULT_DOCUMENTS = ("LAB_CONTRACT.md", "ARCHITECTURE.md", "ROADMAP.md")


def render_report(
    proposal: OntologyProposal,
    report: OntologyValidationReport,
) -> str:
    """Render proposals and rule results without persisting accepted edges."""
    accepted_ids = {item.proposal_id for item in report.accepted}
    lines = [
        "# Ontology Proposal · BAGO Agentic Data Lab",
        "",
        "This is a review artifact generated from documentation. It is not the",
        "canonical ontology store: relation proposals remain pending human or",
        "contract-level approval and are not written into the proposal graph.",
        "",
        "## Summary",
        "",
        f"- Documents: {len(proposal.document_uris)}",
        f"- Candidate entities: {len(proposal.graph.assets)}",
        f"- Relation proposals: {len(proposal.relation_proposals)}",
        f"- Validator rule-pass: {len(report.accepted)}",
        f"- Validator rejected: {len(report.rejected)}",
        "",
        "## Documents",
        "",
    ]
    lines.extend(f"- `{uri}`" for uri in proposal.document_uris)
    lines.extend(["", "## Candidate entities", ""])
    for asset in sorted(proposal.graph.assets.values(), key=lambda item: item.asset_id):
        lines.append(
            f"- `{asset.asset_id}` — **{asset.title}** "
            f"(`TYPE={asset.asset_type}`, `AUTHORITY={asset.authority.value}`, "
            f"`VALIDITY={asset.validity.value}`)"
        )

    lines.extend(["", "## Relation proposals", ""])
    if not proposal.relation_proposals:
        lines.append("No explicit relation statements were detected.")
    for item in sorted(proposal.relation_proposals, key=lambda candidate: candidate.proposal_id):
        relation = item.relation
        status = (
            "RULE_PASS_PENDING_APPROVAL"
            if item.proposal_id in accepted_ids
            else item.status.value
        )
        lines.extend(
            [
                f"### `{item.proposal_id}` · `{status}`",
                "",
                f"`{relation.source_id}` **{relation.relation_type.value}** "
                f"`{relation.target_id}`",
                f"- Confidence: `{relation.confidence:.2f}`",
                f"- Evidence: `{item.evidence_ref.strip()}`",
            ]
        )
        if item.rejection_reason:
            lines.append(f"- Rejection reason: `{item.rejection_reason}`")
        lines.append("")

    lines.extend(
        [
            "## Governance boundary",
            "",
            "`LLM or extractor proposes → OntologyValidator checks → human/contract "
            "rules decide → accepted graph`.",
            "",
            "This command intentionally stops before the accepted graph is persisted.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "documents",
        nargs="*",
        default=list(DEFAULT_DOCUMENTS),
        help="UTF-8 Markdown files; defaults to the three lab design documents",
    )
    parser.add_argument(
        "--output",
        default="evidence/ontology_proposal.md",
        help="review artifact path relative to the repository root",
    )
    args = parser.parse_args()

    generator = OntologyGenerator()
    proposal = generator.generate_from_files(args.documents)
    report = OntologyValidator().validate(proposal)
    output_path = (REPO_ROOT / args.output).resolve()
    if REPO_ROOT not in output_path.parents:
        raise SystemExit("--output must remain inside the repository")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(proposal, report), encoding="utf-8")

    print(f"Generated {output_path.relative_to(REPO_ROOT)}")
    print(
        f"Entities: {len(proposal.graph.assets)} | "
        f"Proposals: {len(proposal.relation_proposals)} | "
        f"Rule-pass: {len(report.accepted)} | Rejected: {len(report.rejected)}"
    )
    print("No relation was persisted as canonical; human/contract approval remains required.")


if __name__ == "__main__":
    main()
