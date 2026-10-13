"""A bounded chat-context adaptation of BAGO5 native attention.

This module does not import the BAGO5 prototype at runtime. It adapts its
typed units, weighted activation and bounded workspace to a lexical cue graph
that can guide a model prompt. It is prompt orchestration, not model-internal
reasoning, verified knowledge, persistent learning, or execution authority.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
import math
import re
import unicodedata
from typing import Any


PROFILE = "BAGO5_CHAT_COGNITION_V0.1"
MAX_FOCUS_UNITS = 6
MAX_HOPS = 2
MAX_EXPANSIONS = 32
DECAY = 0.65


@dataclass(frozen=True)
class Unit:
    unit_id: str
    kind: "UnitKind"
    label: str
    guidance: str = ""

    def __post_init__(self) -> None:
        if not self.unit_id or not self.label or not isinstance(self.kind, UnitKind):
            raise ValueError("Cognitive units require an id, label and typed kind.")


class UnitKind(str, Enum):
    NEED = "need"
    GOAL = "goal"
    DOMAIN = "domain"
    CONSTRAINT = "constraint"
    FORMAT = "format"
    STRATEGY = "strategy"


class Relation(str, Enum):
    TRIGGERS = "TRIGGERS"
    ENABLES = "ENABLES"
    INHIBITS = "INHIBITS"


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relation: Relation
    weight: float

    def __post_init__(self) -> None:
        if not self.source or not self.target or not isinstance(self.relation, Relation):
            raise ValueError("Cognitive links require endpoint ids and a typed relation.")
        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)) or not math.isfinite(self.weight) or not 0 <= self.weight <= 1:
            raise ValueError("Cognitive link weight must be bounded between zero and one.")


@dataclass(frozen=True)
class Activation:
    unit_id: str
    score: float
    hops: int
    source: str


@dataclass(frozen=True)
class Cue:
    unit: Unit
    terms: tuple[str, ...]
    links: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class CognitiveWorkspace:
    capacity: int = MAX_FOCUS_UNITS

    def __post_init__(self) -> None:
        if not 1 <= self.capacity <= 16:
            raise ValueError("Cognitive workspace capacity must be bounded.")


_STRATEGIES = {
    "strategy.direct": Unit("strategy.direct", UnitKind.STRATEGY, "Direct answer", "Answer the user's request directly and keep the response proportionate."),
    "strategy.steps": Unit("strategy.steps", UnitKind.STRATEGY, "Ordered steps", "Use ordered, actionable steps when the request calls for a procedure."),
    "strategy.tradeoffs": Unit("strategy.tradeoffs", UnitKind.STRATEGY, "Compare trade-offs", "Compare the relevant criteria and trade-offs before recommending."),
    "strategy.evidence": Unit("strategy.evidence", UnitKind.STRATEGY, "Evidence and inference", "Separate evidence from inference; state when requested evidence is absent."),
    "strategy.uncertainty": Unit("strategy.uncertainty", UnitKind.STRATEGY, "Uncertainty", "State material uncertainty and what would verify it; do not invent missing facts."),
    "strategy.examples": Unit("strategy.examples", UnitKind.STRATEGY, "Concrete examples", "Use a small concrete example only when it clarifies the answer."),
    "strategy.concise": Unit("strategy.concise", UnitKind.STRATEGY, "Concise response", "Prefer a concise response and omit background the user did not request."),
    "strategy.table": Unit("strategy.table", UnitKind.STRATEGY, "Tabular comparison", "Use a compact table when comparing multiple items."),
}

_CUES = (
    Cue(Unit("need.explain", UnitKind.GOAL, "Explain"), ("explain", "explica", "explicar", "define", "que significa", "what is"), (("strategy.direct", .9), ("strategy.examples", .55))),
    Cue(Unit("need.compare", UnitKind.GOAL, "Compare"), ("compare", "compara", "comparar", "difference", "diferencia", "versus", "vs"), (("strategy.tradeoffs", .95), ("strategy.table", .45))),
    Cue(Unit("need.recommend", UnitKind.GOAL, "Recommend"), ("recommend", "recomienda", "aconseja", "suggest", "sugiere", "which should"), (("strategy.tradeoffs", .85), ("strategy.uncertainty", .35))),
    Cue(Unit("need.analyze", UnitKind.GOAL, "Analyze"), ("analyze", "analiza", "audit", "audita", "review", "revisa", "diagnose", "diagnostica"), (("strategy.evidence", .8), ("strategy.uncertainty", .35))),
    Cue(Unit("need.plan", UnitKind.GOAL, "Plan"), ("plan", "planning", "paso a paso", "steps", "procedure", "procedimiento", "como hago", "how do i"), (("strategy.steps", .95), ("strategy.evidence", .35))),
    Cue(Unit("need.summarize", UnitKind.GOAL, "Summarize"), ("summarize", "summary", "resume", "resumen", "sintetiza", "in brief"), (("strategy.concise", .85), ("strategy.evidence", .35))),
    Cue(Unit("need.code", UnitKind.DOMAIN, "Code"), ("code", "codigo", "program", "programa", "function", "funcion", "bug", "repository", "repositorio"), (("strategy.evidence", .55), ("strategy.examples", .45))),
    Cue(Unit("constraint.evidence", UnitKind.CONSTRAINT, "Evidence requested"), ("evidence", "evidencia", "source", "fuente", "cite", "cita", "verify", "verifica"), (("strategy.evidence", .95),)),
    Cue(Unit("constraint.uncertainty", UnitKind.CONSTRAINT, "Uncertainty matters"), ("uncertain", "uncertainty", "duda", "incierto", "latest", "actualizado", "current", "vigente"), (("strategy.uncertainty", .9),)),
    Cue(Unit("format.concise", UnitKind.FORMAT, "Concise"), ("briefly", "brief", "concise", "breve", "brevemente", "short answer"), (("strategy.concise", .9),)),
    Cue(Unit("format.steps", UnitKind.FORMAT, "Steps"), ("step by step", "paso a paso", "numbered steps", "lista de pasos"), (("strategy.steps", .95),)),
    Cue(Unit("format.table", UnitKind.FORMAT, "Table"), ("table", "tabla", "tabular"), (("strategy.table", .95),)),
)

_RELATION_KINDS = {
    Relation.TRIGGERS: ({UnitKind.NEED}, {UnitKind.GOAL, UnitKind.DOMAIN, UnitKind.CONSTRAINT, UnitKind.FORMAT}),
    Relation.ENABLES: ({UnitKind.NEED, UnitKind.GOAL, UnitKind.DOMAIN, UnitKind.CONSTRAINT, UnitKind.FORMAT}, {UnitKind.STRATEGY}),
    Relation.INHIBITS: ({UnitKind.FORMAT}, {UnitKind.STRATEGY}),
}


def _validate_edge(units: dict[str, Unit], edge: Edge) -> None:
    if edge.source not in units or edge.target not in units:
        raise ValueError("Cognitive link references an unknown unit.")
    allowed_source, allowed_target = _RELATION_KINDS[edge.relation]
    if units[edge.source].kind not in allowed_source or units[edge.target].kind not in allowed_target:
        raise ValueError("Cognitive link relation is incompatible with its unit kinds.")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def _matches(text: str, term: str) -> bool:
    normalized_term = _normalize(term)
    return bool(normalized_term and re.search(rf"(?:^| ){re.escape(normalized_term)}(?: |$)", text))


def _activated_cues(message: str) -> list[tuple[Cue, float]]:
    text = _normalize(message[:8000])
    selected: list[tuple[Cue, float]] = []
    for cue in _CUES:
        matches = sum(1 for term in cue.terms if _matches(text, term))
        if matches:
            selected.append((cue, min(1.0, round(0.55 + 0.15 * (matches - 1), 4))))
    return selected


def build_chat_cognition(message: str) -> dict[str, Any]:
    """Build deterministic focus and prompt guidance from one user turn."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("A non-empty user message is required.")

    cues = _activated_cues(message)
    need = Unit("need.current_turn", UnitKind.NEED, "Current user request")
    units = {need.unit_id: need, **_STRATEGIES}
    edges: list[Edge] = []
    seeds = [need.unit_id]
    seed_scores = {need.unit_id: 1.0}
    for cue, strength in cues:
        units[cue.unit.unit_id] = cue.unit
        edges.append(Edge(need.unit_id, cue.unit.unit_id, Relation.TRIGGERS, strength))
        seed_scores[cue.unit.unit_id] = strength
        for strategy_id, weight in cue.links:
            edges.append(Edge(cue.unit.unit_id, strategy_id, Relation.ENABLES, weight))
    if not cues:
        edges.append(Edge(need.unit_id, "strategy.direct", Relation.ENABLES, 1.0))

    # A brevity cue suppresses examples unless the user explicitly asked for one.
    if any(cue.unit.unit_id == "format.concise" for cue, _ in cues) and not any(
        term in _normalize(message) for term in ("example", "example", "ejemplo")
    ):
        edges.append(Edge("format.concise", "strategy.examples", Relation.INHIBITS, .8))

    for edge in edges:
        _validate_edge(units, edge)

    outgoing: dict[str, list[Edge]] = {}
    for edge in sorted(edges, key=lambda item: (item.source, item.target, item.relation.value)):
        outgoing.setdefault(edge.source, []).append(edge)
    scores = dict(seed_scores)
    hops = {seed: 0 for seed in seeds + [unit_id for unit_id in seed_scores if unit_id != need.unit_id]}
    origins = {unit_id: "lexical_match" for unit_id in seed_scores if unit_id != need.unit_id}
    origins[need.unit_id] = "current_turn"
    frontier = deque((unit_id, score, 0) for unit_id, score in sorted(seed_scores.items()))
    expansions = 0
    while frontier:
        source, source_score, depth = frontier.popleft()
        if depth >= MAX_HOPS:
            continue
        for edge in outgoing.get(source, []):
            expansions += 1
            if expansions > MAX_EXPANSIONS:
                raise ValueError("Cognitive attention expansion budget exceeded.")
            if edge.relation == Relation.INHIBITS:
                continue
            candidate = round(source_score * edge.weight * DECAY, 6)
            if candidate > scores.get(edge.target, 0.0):
                scores[edge.target] = candidate
                hops[edge.target] = depth + 1
                origins[edge.target] = f"{source}::{edge.relation}::{edge.target}"
                frontier.append((edge.target, candidate, depth + 1))

    for edge in edges:
        if edge.relation == Relation.INHIBITS and edge.source in scores and edge.target in scores:
            scores[edge.target] = max(0.0, round(scores[edge.target] - scores[edge.source] * edge.weight, 6))

    ranked = sorted(
        (Activation(unit_id, score, hops.get(unit_id, 0), origins.get(unit_id, "activation"))
         for unit_id, score in scores.items() if score > 0),
        key=lambda item: (-item.score, item.unit_id),
    )[:CognitiveWorkspace().capacity]
    focus = [
        {"id": item.unit_id, "kind": units[item.unit_id].kind.value, "label": units[item.unit_id].label,
         "score": item.score, "hops": item.hops, "source": item.source}
        for item in ranked
    ]
    strategy_ids = [item["id"] for item in focus if units[item["id"]].kind == UnitKind.STRATEGY]
    guidance = [units[unit_id].guidance for unit_id in strategy_ids if units[unit_id].guidance]
    system_instruction = (
        "BAGO5 experimental cognitive context: the following bounded, deterministic attention focus is guidance for this reply. "
        "Follow the user's explicit request and all higher-priority instructions first. This focus is not verified knowledge. "
        "Do not reveal hidden chain-of-thought; give the answer and only a brief user-facing rationale when useful.\n"
        + "\n".join(f"- {item}" for item in guidance)
    )
    return {
        "profile": PROFILE,
        "method": "deterministic_lexical_cues_bounded_weighted_attention",
        "focus": focus,
        "expansions": expansions,
        "capacity": CognitiveWorkspace().capacity,
        "max_hops": MAX_HOPS,
        "prompt_guidance": system_instruction,
    }


def baseline_chat_context() -> dict[str, Any]:
    return {"profile": None, "method": "baseline", "focus": [], "expansions": 0,
            "capacity": 0, "max_hops": 0, "prompt_guidance": ""}
