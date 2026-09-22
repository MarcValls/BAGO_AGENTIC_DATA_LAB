"""L9 end-to-end knowledge agent with an explicit BAGO execution boundary.

The agent owns orchestration and answer assembly.  It does not treat a model,
LangGraph node or discovered MCP capability as authority.  Retrieval is
performed by :class:`GovernedRAG`; material actions become
``ExecutionRequest`` objects and are authorized before an optional MCP or
Bedrock transport is called.

The default answer path is deterministic and offline.  A real or fixture
Bedrock adapter can be injected when provider execution is explicitly wanted.
That makes the portfolio demo reproducible without pretending to have AWS
credentials or a live commercetools account.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Optional, TypedDict

from langgraph.graph import END, StateGraph

from adapters.bedrock_provider_adapter import (
    BedrockCallResult,
    GovernedBedrockAdapter,
)
from adapters.mcp_adapter import (
    GovernedMCPAdapter,
    MCPCallReceipt,
    MCPGovernanceError,
)
from orchestration.state_graph import (
    AuthorizationDecision,
    EffectType,
    ExecutionOutcome,
    ExecutionRequest,
    Permit,
)
from retrieval.governed_rag import (
    GovernedRAG,
    QueryIntent,
    RetrievalResponse,
)


class AgentRunStatus(str, Enum):
    """Terminal status of one agent run."""

    COMPLETED = "COMPLETED"
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AgentPolicy:
    """Boundaries that keep the end-to-end demo deterministic and finite."""

    max_retrieval_hits: int = 5
    context_max_chars: int = 4500
    default_context_revision: str = "l9-offline-v1"
    proposed_by: str = "l9-governed-knowledge-agent"
    execute_mcp_reads: bool = True

    def __post_init__(self) -> None:
        if self.max_retrieval_hits <= 0:
            raise ValueError("max_retrieval_hits must be positive")
        if self.context_max_chars <= 0:
            raise ValueError("context_max_chars must be positive")
        if not self.default_context_revision.strip():
            raise ValueError("default_context_revision is required")
        if not self.proposed_by.strip():
            raise ValueError("proposed_by is required")


@dataclass(frozen=True)
class AgentToolProposal:
    """A proposed capability call, before or after BAGO authorization."""

    proposal_id: str
    request: ExecutionRequest
    transport: str
    rationale: str
    decision: Optional[AuthorizationDecision] = None
    permit_id: str = ""
    called: bool = False
    outcome: Optional[ExecutionOutcome] = None
    receipt_id: str = ""
    result: Any = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "tool_name": self.request.tool_name,
            "transport": self.transport,
            "effect_type": self.request.effect_type.value,
            "arguments": dict(self.request.parameters),
            "request_id": self.request.request_id,
            "context_revision": self.request.context_revision,
            "rationale": self.rationale,
            "decision": self.decision.value if self.decision else None,
            "permit_id": self.permit_id,
            "called": self.called,
            "outcome": self.outcome.value if self.outcome else None,
            "receipt_id": self.receipt_id,
            "result": self.result,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class AgentDecisionReceipt:
    """Receipt for a proposal that was denied or stopped before transport."""

    receipt_id: str
    request_id: str
    tool_name: str
    decision: AuthorizationDecision
    execution_outcome: ExecutionOutcome
    actual_effect: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    error_message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "decision": self.decision.value,
            "execution_outcome": self.execution_outcome.value,
            "actual_effect": dict(self.actual_effect),
            "evidence_refs": list(self.evidence_refs),
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class AgentRun:
    """Evidence-bearing result of one end-to-end agent invocation."""

    run_id: str
    query: str
    intent: QueryIntent
    status: AgentRunStatus
    answer: str
    citations: tuple[str, ...]
    retrieval: RetrievalResponse
    proposals: tuple[AgentToolProposal, ...]
    decision_receipts: tuple[AgentDecisionReceipt, ...]
    mcp_receipts: tuple[MCPCallReceipt, ...]
    provider_result: Optional[BedrockCallResult]
    trace: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        provider_receipt = None
        provider_text = None
        if self.provider_result is not None:
            provider_receipt = self.provider_result.receipt.to_dict()
            provider_text = self.provider_result.text
        return {
            "run_id": self.run_id,
            "query": self.query,
            "intent": self.intent.value,
            "status": self.status.value,
            "answer": self.answer,
            "citations": list(self.citations),
            "retrieval": self.retrieval.to_dict(),
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "decision_receipts": [receipt.to_dict() for receipt in self.decision_receipts],
            "mcp_receipts": [receipt.to_dict() for receipt in self.mcp_receipts],
            "provider_receipt": provider_receipt,
            "provider_text": provider_text,
            "trace": list(self.trace),
            "errors": list(self.errors),
        }


class KnowledgeAgentState(TypedDict, total=False):
    """State passed through the L9 LangGraph nodes."""

    run_id: str
    query: str
    context_revision: str
    model_id: str
    use_bedrock: bool
    intent: QueryIntent
    entities: list[str]
    retrieval: RetrievalResponse
    context: str
    proposals: list[AgentToolProposal]
    permits: dict[str, Permit]
    decision_receipts: list[AgentDecisionReceipt]
    mcp_receipts: list[MCPCallReceipt]
    provider_result: Optional[BedrockCallResult]
    answer: str
    citations: list[str]
    status: AgentRunStatus
    trace: list[str]
    errors: list[str]


class GovernedKnowledgeAgent:
    """Compose governed retrieval, reasoning, tool proposals and verification."""

    def __init__(
        self,
        retriever: GovernedRAG,
        *,
        policy: Optional[AgentPolicy] = None,
        mcp_adapter: Optional[GovernedMCPAdapter] = None,
        mcp_session: Any = None,
        bedrock_adapter: Optional[GovernedBedrockAdapter] = None,
    ) -> None:
        self.retriever = retriever
        self.policy = policy or AgentPolicy()
        self.mcp_adapter = mcp_adapter
        self.mcp_session = mcp_session
        self.bedrock_adapter = bedrock_adapter
        self.graph = self._build_graph()

    async def run(
        self,
        query: str,
        *,
        context_revision: Optional[str] = None,
        model_id: Optional[str] = None,
        use_bedrock: bool = False,
    ) -> AgentRun:
        """Run the complete graph and return an evidence-bearing result."""

        if not query.strip():
            raise ValueError("query no puede estar vacío")
        revision = context_revision or self.policy.default_context_revision
        run_id = self._stable_id("agent_run", query, revision)
        initial: KnowledgeAgentState = {
            "run_id": run_id,
            "query": query,
            "context_revision": revision,
            "model_id": model_id or "",
            "use_bedrock": use_bedrock,
            "trace": [],
            "errors": [],
        }
        state = await self.graph.ainvoke(initial)
        return self._to_result(state)

    def run_sync(self, query: str, **kwargs: Any) -> AgentRun:
        """Synchronous convenience wrapper for CLI users outside an event loop."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(query, **kwargs))
        raise RuntimeError("run_sync no puede invocarse dentro de un event loop")

    def _build_graph(self):
        workflow = StateGraph(KnowledgeAgentState)
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("reason_and_propose", self._reason_and_propose)
        workflow.add_node("authorization_gate", self._authorization_gate)
        workflow.add_node("execute_authorized", self._execute_authorized)
        workflow.add_node("verify_and_respond", self._verify_and_respond)
        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "retrieve_context")
        workflow.add_edge("retrieve_context", "reason_and_propose")
        workflow.add_edge("reason_and_propose", "authorization_gate")
        workflow.add_edge("authorization_gate", "execute_authorized")
        workflow.add_edge("execute_authorized", "verify_and_respond")
        workflow.add_edge("verify_and_respond", END)
        return workflow.compile()

    def _classify_intent(self, state: KnowledgeAgentState) -> KnowledgeAgentState:
        query = state["query"]
        normalized = query.casefold()
        intent = self.retriever.classify_intent(query)
        if self._is_action_query(normalized):
            intent = QueryIntent.ACTION
        entities = sorted(
            {
                entity
                for entity in (
                    "BAGO",
                    "LangGraph",
                    "MCP",
                    "Bedrock",
                    "OpenMetadata",
                    "session_manager",
                    "workspace_binding",
                    "RC6",
                )
                if entity.casefold() in normalized
            }
        )
        return {
            "intent": intent,
            "entities": entities,
            "trace": [
                *state.get("trace", []),
                f"classify_intent={intent.value}; entities={','.join(entities) or 'none'}",
            ],
        }

    def _retrieve_context(self, state: KnowledgeAgentState) -> KnowledgeAgentState:
        response = self.retriever.retrieve(
            state["query"],
            top_k=self.policy.max_retrieval_hits,
        )
        return {
            "retrieval": response,
            "context": response.assemble_context(self.policy.context_max_chars),
            "trace": [
                *state.get("trace", []),
                f"retrieve_context=hits:{len(response.hits)}; filtered:{response.filtered_count}",
            ],
        }

    def _reason_and_propose(self, state: KnowledgeAgentState) -> KnowledgeAgentState:
        query = state["query"]
        normalized = query.casefold()
        context_revision = state["context_revision"]
        proposals: list[AgentToolProposal] = []
        trace = list(state.get("trace", []))
        errors = list(state.get("errors", []))

        if self._is_technical_query(normalized):
            mcp_proposal = self._build_mcp_proposal(
                "get_lab_status",
                {},
                proposed_by=self.policy.proposed_by,
                context_revision=context_revision,
                rationale="Read-only status may enrich a technical answer.",
            )
            if mcp_proposal is not None:
                proposals.append(mcp_proposal)

        if self._is_implementation_query(normalized):
            path = self._test_path_from_query(query)
            content = (
                "def test_workspace_binding_contract():\n"
                "    assert workspace_binding_is_governed()\n"
            )
            proposals.append(
                self._build_generic_proposal(
                    tool_name="file_creator",
                    effect_type=EffectType.CREATE,
                    arguments={"path": path, "content": content},
                    context_revision=context_revision,
                    rationale="A generated test is a CREATE effect and needs human approval.",
                )
            )
            mcp_write = self._build_mcp_proposal(
                "propose_lab_note",
                {"path": "notes/l9-test-proposal.md", "content": content},
                proposed_by=self.policy.proposed_by,
                context_revision=context_revision,
                rationale="Demonstrate that an MCP WRITE is blocked before transport.",
            )
            if mcp_write is not None:
                proposals.append(mcp_write)

        if self._is_architecture_query(normalized):
            report = self._gap_report(state)
            proposals.append(
                self._build_generic_proposal(
                    tool_name="github.create_issue",
                    effect_type=EffectType.EXTERNAL_API,
                    arguments={
                        "title": "BAGO canon compliance review",
                        "body": report,
                    },
                    context_revision=context_revision,
                    rationale="Creating a GitHub issue is external and requires explicit approval.",
                )
            )

        if state.get("use_bedrock"):
            if self.bedrock_adapter is None:
                errors.append("Bedrock requested but adapter is not configured")
            else:
                model_id = state.get("model_id", "")
                if not model_id:
                    errors.append("Bedrock requested without model_id")
                else:
                    try:
                        request = self.bedrock_adapter.build_execution_request(
                            model_id,
                            [{
                                "role": "user",
                                "content": [{"text": self._provider_prompt(state)}],
                            }],
                            proposed_by=self.policy.proposed_by,
                            context_revision=context_revision,
                            system=[
                                {
                                    "text": (
                                        "Answer only from the governed context. "
                                        "Do not execute proposed tools."
                                    )
                                }
                            ],
                            inference_config={"maxTokens": 384, "temperature": 0.0},
                            tool_config=self._bedrock_tool_config(),
                        )
                        proposals.append(
                            AgentToolProposal(
                                proposal_id=self._stable_id("proposal", request.request_id),
                                request=request,
                                transport="bedrock",
                                rationale="Provider generation is a separately governed external call.",
                            )
                        )
                    except (TypeError, ValueError) as error:
                        errors.append(f"Bedrock proposal invalid: {error}")

        trace.append(f"reason_and_propose=proposals:{len(proposals)}")
        return {"proposals": proposals, "trace": trace, "errors": errors}

    def _authorization_gate(self, state: KnowledgeAgentState) -> KnowledgeAgentState:
        permits: dict[str, Permit] = {}
        authorized: list[AgentToolProposal] = []
        trace = list(state.get("trace", []))
        errors = list(state.get("errors", []))

        for proposal in state.get("proposals", []):
            request = proposal.request
            try:
                if proposal.transport == "mcp":
                    if self.mcp_adapter is None:
                        raise MCPGovernanceError("MCP adapter is not configured")
                    permit = self.mcp_adapter.authorize(request)
                elif proposal.transport == "bedrock":
                    if self.bedrock_adapter is None:
                        raise RuntimeError("Bedrock adapter is not configured")
                    permit = self.bedrock_adapter.authorize(request)
                else:
                    decision = (
                        AuthorizationDecision.ALLOW
                        if request.effect_type is EffectType.READ
                        else AuthorizationDecision.REQUIRE_HUMAN
                    )
                    permit = None
                    updated = replace(proposal, decision=decision)
                    authorized.append(updated)
                    trace.append(f"authorize={request.tool_name}:{decision.value}:no_transport")
                    continue
            except (MCPGovernanceError, RuntimeError, ValueError) as error:
                errors.append(f"authorization {request.tool_name}: {error}")
                authorized.append(
                    replace(
                        proposal,
                        decision=AuthorizationDecision.DENY,
                        error_message=str(error),
                    )
                )
                continue

            permits[proposal.proposal_id] = permit
            authorized.append(
                replace(
                    proposal,
                    decision=permit.decision,
                    permit_id=permit.permit_id,
                )
            )
            trace.append(
                f"authorize={request.tool_name}:{permit.decision.value}:permit={permit.permit_id}"
            )

        return {
            "proposals": authorized,
            "permits": permits,
            "trace": trace,
            "errors": errors,
        }

    async def _execute_authorized(self, state: KnowledgeAgentState) -> KnowledgeAgentState:
        proposals: list[AgentToolProposal] = []
        decision_receipts = list(state.get("decision_receipts", []))
        mcp_receipts = list(state.get("mcp_receipts", []))
        provider_result = state.get("provider_result")
        permits = state.get("permits", {})
        trace = list(state.get("trace", []))
        errors = list(state.get("errors", []))

        for proposal in state.get("proposals", []):
            if proposal.decision is not AuthorizationDecision.ALLOW:
                permit = permits.get(proposal.proposal_id)
                if proposal.transport == "mcp" and self.mcp_adapter is not None:
                    receipt = await self.mcp_adapter.call(
                        self.mcp_session,
                        proposal.request,
                        permit,
                    )
                    mcp_receipts.append(receipt)
                    proposals.append(
                        replace(
                            proposal,
                            called=bool(receipt.actual_effect.get("called")),
                            outcome=receipt.execution_outcome,
                            receipt_id=receipt.receipt_id,
                            result=receipt.result,
                            error_message=receipt.error_message,
                        )
                    )
                elif proposal.transport == "bedrock" and self.bedrock_adapter is not None and permit:
                    provider_result = self.bedrock_adapter.converse(
                        proposal.request,
                        permit,
                    )
                    receipt = provider_result.receipt
                    proposals.append(
                        replace(
                            proposal,
                            called=bool(receipt.actual_effect.get("called")),
                            outcome=receipt.execution_outcome,
                            receipt_id=receipt.receipt_id,
                            result=provider_result.text,
                            error_message=receipt.error_message,
                        )
                    )
                else:
                    receipt = self._decision_receipt(proposal)
                    decision_receipts.append(receipt)
                    proposals.append(
                        replace(
                            proposal,
                            called=False,
                            outcome=receipt.execution_outcome,
                            receipt_id=receipt.receipt_id,
                            error_message=receipt.error_message,
                        )
                    )
                continue
            permit = permits.get(proposal.proposal_id)
            if permit is None:
                proposals.append(
                    replace(
                        proposal,
                        outcome=ExecutionOutcome.FAILURE,
                        error_message="ALLOW sin permit asociado",
                    )
                )
                decision_receipts.append(
                    self._decision_receipt(
                        proposal,
                        error_message="ALLOW sin permit asociado",
                    )
                )
                errors.append(f"{proposal.request.tool_name}: ALLOW sin permit")
                continue

            if proposal.transport == "mcp":
                if not self.policy.execute_mcp_reads or self.mcp_session is None:
                    proposals.append(
                        replace(
                            proposal,
                            outcome=ExecutionOutcome.FAILURE,
                            error_message="MCP session not configured",
                        )
                    )
                    decision_receipts.append(
                        self._decision_receipt(
                            proposal,
                            error_message="MCP session not configured",
                        )
                    )
                    errors.append(f"{proposal.request.tool_name}: MCP session not configured")
                    continue
                receipt = await self.mcp_adapter.call(  # type: ignore[union-attr]
                    self.mcp_session,
                    proposal.request,
                    permit,
                )
                mcp_receipts.append(receipt)
                proposals.append(
                    replace(
                        proposal,
                        called=bool(receipt.actual_effect.get("called")),
                        outcome=receipt.execution_outcome,
                        receipt_id=receipt.receipt_id,
                        result=receipt.result,
                        error_message=receipt.error_message,
                    )
                )
                trace.append(
                    f"execute={proposal.request.tool_name}:{receipt.execution_outcome.value}"
                )
                continue

            if proposal.transport == "bedrock":
                provider_result = self.bedrock_adapter.converse(  # type: ignore[union-attr]
                    proposal.request,
                    permit,
                )
                receipt = provider_result.receipt
                proposals.append(
                    replace(
                        proposal,
                        called=bool(receipt.actual_effect.get("called")),
                        outcome=receipt.execution_outcome,
                        receipt_id=receipt.receipt_id,
                        result=provider_result.text,
                        error_message=receipt.error_message,
                    )
                )
                trace.append(
                    f"execute={proposal.request.tool_name}:{receipt.execution_outcome.value}"
                )
                continue

            proposals.append(
                replace(
                    proposal,
                    outcome=ExecutionOutcome.FAILURE,
                    error_message="No execution transport configured for proposal",
                )
            )
            decision_receipts.append(
                self._decision_receipt(
                    proposal,
                    error_message="No execution transport configured for proposal",
                )
            )
            errors.append(f"{proposal.request.tool_name}: no execution transport")

        return {
            "proposals": proposals,
            "decision_receipts": decision_receipts,
            "mcp_receipts": mcp_receipts,
            "provider_result": provider_result,
            "trace": trace,
            "errors": errors,
        }

    def _verify_and_respond(self, state: KnowledgeAgentState) -> KnowledgeAgentState:
        retrieval = state["retrieval"]
        provider_result = state.get("provider_result")
        answer = ""
        if provider_result is not None and provider_result.receipt.execution_outcome is ExecutionOutcome.SUCCESS:
            answer = provider_result.text.strip()
        if not answer:
            answer = self._deterministic_answer(state)

        citations = list(retrieval.citations)
        if citations:
            answer = answer.rstrip() + "\n\nEvidence:\n" + "\n".join(
                f"- {citation}" for citation in citations
            )

        proposals = state.get("proposals", [])
        pending = any(
            proposal.decision in {
                AuthorizationDecision.REQUIRE_HUMAN,
                AuthorizationDecision.DENY,
            }
            for proposal in proposals
        )
        failed = bool(state.get("errors")) or any(
            proposal.outcome is ExecutionOutcome.FAILURE for proposal in proposals
        )
        if pending:
            status = AgentRunStatus.PENDING_AUTHORIZATION
        elif failed:
            status = AgentRunStatus.FAILED
        else:
            status = AgentRunStatus.COMPLETED
        trace = [
            *state.get("trace", []),
            f"verify_and_respond=status:{status.value}; citations:{len(citations)}",
        ]
        return {
            "answer": answer,
            "citations": citations,
            "status": status,
            "trace": trace,
        }

    def _to_result(self, state: KnowledgeAgentState) -> AgentRun:
        return AgentRun(
            run_id=state["run_id"],
            query=state["query"],
            intent=state["intent"],
            status=state.get("status", AgentRunStatus.FAILED),
            answer=state.get("answer", ""),
            citations=tuple(state.get("citations", [])),
            retrieval=state["retrieval"],
            proposals=tuple(state.get("proposals", [])),
            decision_receipts=tuple(state.get("decision_receipts", [])),
            mcp_receipts=tuple(state.get("mcp_receipts", [])),
            provider_result=state.get("provider_result"),
            trace=tuple(state.get("trace", [])),
            errors=tuple(state.get("errors", [])),
        )

    def _build_mcp_proposal(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        *,
        proposed_by: str,
        context_revision: str,
        rationale: str,
    ) -> Optional[AgentToolProposal]:
        if self.mcp_adapter is None:
            return None
        registered = {
            item.descriptor.name for item in self.mcp_adapter.registry.registered
        }
        if tool_name not in registered:
            return None
        try:
            request = self.mcp_adapter.build_execution_request(
                tool_name,
                arguments,
                proposed_by=proposed_by,
                context_revision=context_revision,
            )
        except MCPGovernanceError:
            return None
        return AgentToolProposal(
            proposal_id=self._stable_id("proposal", request.request_id),
            request=request,
            transport="mcp",
            rationale=rationale,
        )

    def _build_generic_proposal(
        self,
        *,
        tool_name: str,
        effect_type: EffectType,
        arguments: Mapping[str, Any],
        context_revision: str,
        rationale: str,
    ) -> AgentToolProposal:
        payload = f"{tool_name}:{effect_type.value}:{sorted(arguments.items())}:{context_revision}"
        request_id = self._stable_id("agent_request", payload)
        request = ExecutionRequest(
            request_id=request_id,
            tool_name=tool_name,
            effect_type=effect_type,
            parameters=dict(arguments),
            proposed_by=self.policy.proposed_by,
            context_revision=context_revision,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        return AgentToolProposal(
            proposal_id=self._stable_id("proposal", request_id),
            request=request,
            transport="none",
            rationale=rationale,
        )

    def _decision_receipt(
        self,
        proposal: AgentToolProposal,
        *,
        error_message: Optional[str] = None,
    ) -> AgentDecisionReceipt:
        decision = proposal.decision or AuthorizationDecision.DENY
        message = error_message or (
            "Material effect requires explicit human authorization"
            if decision is AuthorizationDecision.REQUIRE_HUMAN
            else "Proposal denied before transport"
        )
        evidence_ref = (
            f"agent://{proposal.request.tool_name}"
            f"#request={proposal.request.request_id}"
        )
        return AgentDecisionReceipt(
            receipt_id=self._stable_id(
                "agent_receipt",
                proposal.proposal_id,
                decision.value,
                message,
            ),
            request_id=proposal.request.request_id,
            tool_name=proposal.request.tool_name,
            decision=decision,
            execution_outcome=ExecutionOutcome.FAILURE,
            actual_effect={
                "called": False,
                "tool": proposal.request.tool_name,
                "transport": proposal.transport,
            },
            evidence_refs=(evidence_ref,),
            error_message=message,
        )

    @staticmethod
    def _stable_id(prefix: str, *parts: str) -> str:
        digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:16]
        return f"{prefix}_{digest}"

    @staticmethod
    def _is_action_query(normalized: str) -> bool:
        return bool(
            re.search(
                r"\b(crea|crear|ejecuta|ejecutar|modifica|elimina|escribe|push|merge|commit|llama|invoca)\b",
                normalized,
            )
        )

    @staticmethod
    def _is_technical_query(normalized: str) -> bool:
        return any(
            token in normalized
            for token in ("cómo", "como", "how", "qué es", "que es", "describe", "explica")
        )

    @staticmethod
    def _is_implementation_query(normalized: str) -> bool:
        return any(
            token in normalized
            for token in ("crea un test", "crear un test", "implementa", "modifica", "escribe un test")
        )

    @staticmethod
    def _is_architecture_query(normalized: str) -> bool:
        return any(
            token in normalized
            for token in ("cumple", "canon", "arquitectura", "github issue", "gap")
        )

    @staticmethod
    def _test_path_from_query(query: str) -> str:
        if "workspace_binding" in query.casefold():
            return "tests/test_workspace_binding.py"
        return "tests/test_generated_contract.py"

    @staticmethod
    def _provider_prompt(state: KnowledgeAgentState) -> str:
        return (
            f"Question: {state['query']}\n\n"
            "Governed context:\n"
            f"{state.get('context', '')}\n\n"
            "Return a concise answer with no unsupported claims."
        )

    @staticmethod
    def _bedrock_tool_config() -> dict[str, Any]:
        return {
            "tools": [
                {
                    "toolSpec": {
                        "name": "propose_governed_action",
                        "description": "Propose an action for BAGO authorization; never execute it directly.",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "tool_name": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["tool_name", "reason"],
                            }
                        },
                    }
                }
            ]
        }

    @staticmethod
    def _gap_report(state: KnowledgeAgentState) -> str:
        retrieval = state.get("retrieval")
        citations = list(retrieval.citations) if retrieval else []
        return (
            "Offline BAGO architecture review. "
            "Evidence was retrieved through the governed RAG boundary. "
            f"Citations: {', '.join(citations) or 'none'}. "
            "Human review is required before creating an external issue."
        )

    @staticmethod
    def _deterministic_answer(state: KnowledgeAgentState) -> str:
        retrieval = state["retrieval"]
        query = state["query"].casefold()
        if retrieval.hits:
            snippets = [hit.chunk.content.strip() for hit in retrieval.hits[:3]]
            answer = "Respuesta construida con retrieval gobernado:\n" + "\n".join(
                f"- {snippet}" for snippet in snippets if snippet
            )
        else:
            answer = "No hay contexto elegible con la política de metadata actual."
        if GovernedKnowledgeAgent._is_implementation_query(query):
            answer += (
                "\n\nSe preparó una propuesta de test; no se creó ningún archivo "
                "porque CREATE requiere autorización humana."
            )
        if GovernedKnowledgeAgent._is_architecture_query(query):
            answer += (
                "\n\nSe preparó un informe de gaps; no se envió ningún issue "
                "externo sin autorización explícita."
            )
        return answer


__all__ = [
    "AgentPolicy",
    "AgentDecisionReceipt",
    "AgentRun",
    "AgentRunStatus",
    "AgentToolProposal",
    "GovernedKnowledgeAgent",
    "KnowledgeAgentState",
]
