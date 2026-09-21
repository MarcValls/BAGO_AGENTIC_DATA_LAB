"""
L1 · LangGraph Governed Execution — StateGraph Principal

Arquitectura:
START → classify_intent → retrieve_context → reason → propose_action → authorization_gate → execute → verify → END

Principio crítico: LangGraph ORQUESTA pero NO EJECUTA efectos materiales directamente.
Toda acción material se convierte en ExecutionRequest → AuthorizationBoundary → Permit → ExecutionGateway.
"""

from typing import TypedDict, Literal, List, Optional
from dataclasses import dataclass
from enum import Enum
import hashlib


# ============================================================================
# DOMAIN MODEL
# ============================================================================

class EffectType(str, Enum):
    """Tipos de efectos materiales que requieren autorización."""
    READ = "READ"
    WRITE = "WRITE"
    CREATE = "CREATE"
    DELETE = "DELETE"
    EXTERNAL_API = "EXTERNAL_API"
    EXTERNAL_TOOL = "EXTERNAL_TOOL"


class AuthorizationDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_HUMAN = "REQUIRE_HUMAN"


class ExecutionOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"


@dataclass
class ExecutionRequest:
    """Solicitud de ejecución gobernada."""
    request_id: str
    tool_name: str
    effect_type: EffectType
    parameters: dict
    proposed_by: str  # agent/tool identifier
    context_revision: str
    timestamp: str
    
    def to_hash(self) -> str:
        """Hash único para esta request."""
        content = f"{self.request_id}:{self.tool_name}:{self.effect_type.value}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass  
class Permit:
    """Permiso firmado para ejecutar una acción."""
    permit_id: str
    request_id: str
    decision: AuthorizationDecision
    rationale: str
    constraints: List[str]  # time limits, resource limits, scope limits
    issued_at: str
    expires_at: str
    signed_by: str  # authority identifier
    
    def is_valid(self) -> bool:
        """Verifica si el permiso está vigente."""
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        return self.issued_at <= now <= self.expires_at


@dataclass
class Receipt:
    """Recibo de ejecución con evidencia."""
    receipt_id: str
    permit_id: str
    execution_outcome: ExecutionOutcome
    actual_effect: dict
    evidence_refs: List[str]
    duration_ms: int
    cost_usd: float = 0.0
    error_message: Optional[str] = None


# ============================================================================
# STATE SCHEMA
# ============================================================================

class AgentState(TypedDict, total=False):
    """Estado del grafo de LangGraph."""
    
    # Input
    query: str
    
    # Classification
    intent: str  # 'retrieval', 'reasoning', 'action', 'mixed'
    entities: List[str]
    requires_action: bool
    
    # Retrieval
    retrieved_chunks: List[dict]
    context_assembled: str
    metadata_filters: dict
    
    # Reasoning
    reasoning_trace: str
    proposed_actions: List[ExecutionRequest]
    
    # Authorization
    authorization_requests: List[ExecutionRequest]
    permits_issued: List[Permit]
    authorization_denials: List[str]
    
    # Execution
    execution_receipts: List[Receipt]
    execution_failures: List[str]
    
    # Output
    final_response: str
    evidence_links: List[str]
    
    # Error handling
    errors: List[str]
    error_recovery_attempted: bool


# ============================================================================
# NODES IMPLEMENTATION
# ============================================================================

def classify_intent(state: AgentState) -> AgentState:
    """
    Node 1: Clasifica la intención del usuario.
    
    Returns:
        intent: 'retrieval', 'reasoning', 'action', 'mixed'
        entities: entidades extraídas
        requires_action: True si hay acción material propuesta
    """
    query = state.get('query', '').lower()
    
    # Heurística simple (en producción usaría LLM)
    retrieval_keywords = ['qué', 'cómo', 'cuándo', 'dónde', 'por qué', 'explica', 'describe']
    action_keywords = ['crea', 'ejecuta', 'modifica', 'elimina', 'llama', 'invoca']
    
    intent = 'reasoning'  # default
    requires_action = False
    
    if any(kw in query for kw in retrieval_keywords):
        intent = 'retrieval'
    
    if any(kw in query for kw in action_keywords):
        intent = 'action' if 'retrieval' not in intent else 'mixed'
        requires_action = True
    
    # Extracción básica de entidades (mejorable con NLP)
    entities = []
    if 'bago' in query:
        entities.append('BAGO')
    if 'langgraph' in query:
        entities.append('LangGraph')
    
    return {
        'intent': intent,
        'entities': entities,
        'requires_action': requires_action
    }


def retrieve_context(state: AgentState) -> AgentState:
    """
    Node 2: Recupera contexto relevante.
    
    En producción: RAG gobernado con metadata filters.
    Aquí: mock para demostrar el flujo.
    """
    intent = state.get('intent', 'reasoning')
    
    # Mock retrieval (en L4 implementar RAG real)
    retrieved_chunks = [
        {
            'id': 'chunk_001',
            'content': 'BAGO es un sistema de ejecución gobernada...',
            'source': 'LAB_CONTRACT.md',
            'authority': 'high',
            'revision': 'v1.0'
        }
    ]
    
    context_assembled = '\n'.join([chunk['content'] for chunk in retrieved_chunks])
    
    return {
        'retrieved_chunks': retrieved_chunks,
        'context_assembled': context_assembled,
        'metadata_filters': {'authority_gte': 'medium'}
    }


def reason(state: AgentState) -> AgentState:
    """
    Node 3: Razona sobre el contexto y propone acciones.
    
    CRÍTICO: Las acciones se proponen como ExecutionRequest,
    NO se ejecutan directamente.
    """
    context = state.get('context_assembled', '')
    intent = state.get('intent', 'reasoning')
    query = state.get('query', '')
    
    # Mock reasoning trace
    reasoning_trace = f"""
    ANALYSIS:
    - Query: {query}
    - Intent: {intent}
    - Context disponible: {len(context)} caracteres
    
    REASONING:
    1. El usuario pregunta sobre {state.get('entities', [])}
    2. Contexto recuperado sugiere que...
    3. Posibles acciones identificadas: ...
    """
    
    # Propone acciones si es necesario
    proposed_actions = []
    if state.get('requires_action', False):
        # Ejemplo: usuario pide "crea un test para workspace_binding"
        from datetime import datetime, timedelta
        
        action = ExecutionRequest(
            request_id=f"req_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            tool_name="file_creator",
            effect_type=EffectType.CREATE,
            parameters={
                'path': 'tests/test_workspace_binding.py',
                'content': '# Test scaffold...'
            },
            proposed_by="reasoning_node",
            context_revision="v1.0",
            timestamp=datetime.utcnow().isoformat()
        )
        proposed_actions.append(action)
    
    return {
        'reasoning_trace': reasoning_trace,
        'proposed_actions': proposed_actions
    }


def authorization_gate(state: AgentState) -> AgentState:
    """
    Node 4: PUERTA DE AUTORIZACIÓN CRÍTICA.
    
    Aquí se valida si las acciones propuestas pueden ejecutarse.
    
    Reglas:
    - READ actions: auto-allow (generalmente)
    - WRITE/CREATE/DELETE: requieren validación explícita
    - EXTERNAL_API: requieren permisos específicos + timeout
    
    ESTE ES EL CORAZÓN DE LA GOBERNANZA BAGO.
    """
    from datetime import datetime, timedelta
    
    proposed = state.get('proposed_actions', [])
    permits_issued = []
    denials = []
    
    for request in proposed:
        # Regla de gobernanza crítica
        if request.effect_type == EffectType.READ:
            # Auto-allow para lecturas
            permit = Permit(
                permit_id=f"permit_{request.to_hash()}",
                request_id=request.request_id,
                decision=AuthorizationDecision.ALLOW,
                rationale="READ action auto-allowed",
                constraints=["timeout_30s"],
                issued_at=datetime.utcnow().isoformat(),
                expires_at=(datetime.utcnow() + timedelta(seconds=30)).isoformat(),
                signed_by="authorization_gate"
            )
            permits_issued.append(permit)
            
        elif request.effect_type in [EffectType.WRITE, EffectType.CREATE, EffectType.DELETE]:
            # VALIDACIÓN EXPLÍCITA REQUERIDA
            # En producción: verificar signatures, quotas, etc.
            
            # Demo: denegamos todo para mostrar el mecanismo
            denial_reason = f"Action {request.effect_type.value} requires explicit human authorization"
            denials.append(denial_reason)
            
            # Alternativamente, podríamos emitir REQUIRE_HUMAN
            # permit = Permit(..., decision=AuthorizationDecision.REQUIRE_HUMAN, ...)
            
        elif request.effect_type == EffectType.EXTERNAL_API:
            # APIs externas requieren timeouts estrictos
            permit = Permit(
                permit_id=f"permit_{request.to_hash()}",
                request_id=request.request_id,
                decision=AuthorizationDecision.ALLOW,
                rationale="External API allowed with strict timeout",
                constraints=["timeout_10s", "retry_max_2", "rate_limit_1_per_s"],
                issued_at=datetime.utcnow().isoformat(),
                expires_at=(datetime.utcnow() + timedelta(seconds=10)).isoformat(),
                signed_by="authorization_gate"
            )
            permits_issued.append(permit)
    
    return {
        'authorization_requests': proposed,
        'permits_issued': permits_issued,
        'authorization_denials': denials
    }


def execute_actions(state: AgentState) -> AgentState:
    """
    Node 5: Ejecuta acciones autorizadas.
    
    CRÍTICO: Solo ejecuta si tiene Permit válido.
    Sin Permit = NO EXECUTION.
    """
    permits = state.get('permits_issued', [])
    receipts = []
    failures = []
    
    for permit in permits:
        if not permit.is_valid():
            failures.append(f"Permit {permit.permit_id} expired")
            continue
        
        if permit.decision != AuthorizationDecision.ALLOW:
            failures.append(f"Permit {permit.permit_id} decision={permit.decision.value}")
            continue
        
        # Simulación de ejecución (en producción: adapter pattern)
        from datetime import datetime
        import random
        
        receipt = Receipt(
            receipt_id=f"receipt_{permit.permit_id}",
            permit_id=permit.permit_id,
            execution_outcome=ExecutionOutcome.SUCCESS if random.random() > 0.1 else ExecutionOutcome.FAILURE,
            actual_effect={'mock': 'effect_data'},
            evidence_refs=['evidence_001'],
            duration_ms=random.randint(50, 500),
            cost_usd=0.001,
            error_message=None if random.random() > 0.1 else "Mock timeout"
        )
        receipts.append(receipt)
    
    return {
        'execution_receipts': receipts,
        'execution_failures': failures
    }


def verify_and_respond(state: AgentState) -> AgentState:
    """
    Node 6: Verifica resultados y genera respuesta final.
    
    Incluye evidence links para trazabilidad completa.
    """
    receipts = state.get('execution_receipts', [])
    errors = state.get('errors', [])
    reasoning = state.get('reasoning_trace', '')
    
    # Construye respuesta con evidence
    evidence_links = [ref for receipt in receipts for ref in receipt.evidence_refs]
    
    final_response = f"""
    RESPONSE:
    {reasoning}
    
    EXECUTION SUMMARY:
    - Actions proposed: {len(state.get('authorization_requests', []))}
    - Permits issued: {len(receipts)}
    - Executions successful: {sum(1 for r in receipts if r.execution_outcome == ExecutionOutcome.SUCCESS)}
    - Executions failed: {len(state.get('execution_failures', []))}
    
    EVIDENCE:
    {chr(10).join(evidence_links) if evidence_links else 'No external actions executed'}
    
    ERRORS:
    {chr(10).join(errors) if errors else 'None'}
    """
    
    return {
        'final_response': final_response,
        'evidence_links': evidence_links
    }


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

from langgraph.graph import StateGraph, END


def build_governed_agent_graph() -> StateGraph:
    """
    Construye el grafo de LangGraph con gobernanza BAGO.
    
    Flujo:
    START → classify → retrieve → reason → authorization_gate → execute → verify → END
    """
    
    # Define el grafo
    workflow = StateGraph(AgentState)
    
    # Añade nodes
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("reason", reason)
    workflow.add_node("authorization_gate", authorization_gate)
    workflow.add_node("execute_actions", execute_actions)
    workflow.add_node("verify_and_respond", verify_and_respond)
    
    # Define edges
    workflow.set_entry_point("classify_intent")
    
    workflow.add_edge("classify_intent", "retrieve_context")
    workflow.add_edge("retrieve_context", "reason")
    workflow.add_edge("reason", "authorization_gate")
    workflow.add_edge("authorization_gate", "execute_actions")
    workflow.add_edge("execute_actions", "verify_and_respond")
    workflow.add_edge("verify_and_respond", END)
    
    # Compila el grafo
    app = workflow.compile()
    
    return app


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Ejecuta el grafo
    app = build_governed_agent_graph()
    
    # Test query
    test_query = "¿Cómo funciona session_manager en BAGO?"
    
    initial_state = AgentState(query=test_query)
    
    result = app.invoke(initial_state)
    
    print("=" * 80)
    print("L1 · LANGGRAPH GOVERNED EXECUTION — TEST RUN")
    print("=" * 80)
    print(f"Query: {test_query}")
    print(f"Intent: {result.get('intent')}")
    print(f"Requires action: {result.get('requires_action')}")
    print(f"Retrieved chunks: {len(result.get('retrieved_chunks', []))}")
    print(f"Proposed actions: {len(result.get('proposed_actions', []))}")
    print(f"Permits issued: {len(result.get('permits_issued', []))}")
    print(f"Denials: {len(result.get('authorization_denials', []))}")
    print(f"Executions: {len(result.get('execution_receipts', []))}")
    print("=" * 80)
    print(result.get('final_response'))
    print("=" * 80)
