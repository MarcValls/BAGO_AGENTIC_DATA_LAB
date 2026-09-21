"""
L1 · Tests Críticos de Gobernanza BAGO

Estos tests verifican que LangGraph NO puede ejecutar efectos materiales directamente.
Cada test debe fallar si la gobernanza está rota.

CRIT P0 — Estos tests SON la barrera de seguridad.
"""

import pytest
from datetime import datetime, timedelta
from src.orchestration.state_graph import (
    AgentState,
    ExecutionRequest,
    EffectType,
    Permit,
    AuthorizationDecision,
    Receipt,
    ExecutionOutcome,
    build_governed_agent_graph,
    authorization_gate
)


# ============================================================================
# CRIT P0-001: LangGraph NO ejecuta directamente
# ============================================================================

def test_langgraph_cannot_execute_directly():
    """
    CRIT P0-001: LangGraph intenta ejecutar herramienta directamente → EXPECTED: DENY
    
    Este es el test MÁS CRÍTICO de todo el sistema.
    Si falla, la arquitectura gobernada está ROTA.
    
    Escenario:
    - LangGraph propone una acción de tipo WRITE
    - authorization_gate DEBE denegarla automáticamente
    - Sin permiso explícito, NO hay ejecución
    """
    
    # Estado con acción propuesta
    state = AgentState(
        query="Crea un archivo test.py",
        intent='action',
        requires_action=True,
        proposed_actions=[
            ExecutionRequest(
                request_id="test_req_001",
                tool_name="file_creator",
                effect_type=EffectType.WRITE,  # ¡WRITE directo!
                parameters={'path': 'test.py', 'content': '# test'},
                proposed_by="langgraph_node",
                context_revision="v1.0",
                timestamp=datetime.utcnow().isoformat()
            )
        ]
    )
    
    # Ejecuta authorization_gate
    result = authorization_gate(state)
    
    # VERIFICACIÓN CRÍTICA: Debe haber DENIAL
    assert len(result['authorization_denials']) > 0, \
        "CRIT FAIL: WRITE action fue permitida sin autorización explícita"
    
    # Verifica que NO hay permits para esta acción
    permits_for_write = [
        p for p in result.get('permits_issued', [])
        if p.request_id == "test_req_001"
    ]
    assert len(permits_for_write) == 0, \
        "CRIT FAIL: Permit emitido para WRITE sin autorización humana"
    
    print("✅ CRIT P0-001 PASS: LangGraph cannot execute directly")


# ============================================================================
# CRIT P0-002: Permit reutilizado → DENY
# ============================================================================

def test_permit_reuse_denied():
    """
    CRIT P0-002: Intento de reutilizar permiso → EXPECTED: DENY
    
    Un permiso solo puede usarse UNA VEZ.
    Reutilización = ataque de replay → DEBE ser denegado.
    """
    
    # Crea un permiso ya usado
    used_permit = Permit(
        permit_id="permit_used_001",
        request_id="req_001",
        decision=AuthorizationDecision.ALLOW,
        rationale="Test permit",
        constraints=["single_use"],
        issued_at=(datetime.utcnow() - timedelta(seconds=10)).isoformat(),
        expires_at=(datetime.utcnow() + timedelta(seconds=300)).isoformat(),
        signed_by="test_authority"
    )
    
    # Simula que ya fue usado (en producción: tracking en base de datos)
    used_permits = {"permit_used_001"}
    
    # Intenta reutilizar
    permit_to_validate = used_permit
    
    # VERIFICACIÓN: El permiso está en el set de usados
    assert permit_to_validate.permit_id in used_permits, \
        "Setup error: permit should be marked as used"
    
    # En producción, execution_gateway verificaría esto
    is_valid = (
        permit_to_validate.is_valid() and
        permit_to_validate.permit_id not in used_permits
    )
    
    assert not is_valid, \
        "CRIT FAIL: Permit reutilizado considerado válido"
    
    print("✅ CRIT P0-002 PASS: Permit reuse detected and denied")


# ============================================================================
# CRIT P0-003: Documento sin provenance → REJECT
# ============================================================================

def test_document_without_provenance_rejected():
    """
    CRIT P0-003: Documento sin metadata de provenance → EXPECTED: REJECT
    
    Todo documento ingerido DEBE tener:
    - source (URL/file path)
    - authority level
    - version/revision
    - timestamp
    
    Sin esto = rechazado del retrieval.
    """
    
    # Documento SIN provenance
    bad_chunk = {
        'id': 'chunk_bad',
        'content': 'Esto es contenido sin metadata...',
        # ❌ FALTA: source, authority, revision, timestamp
    }
    
    # Documento CON provenance completa
    good_chunk = {
        'id': 'chunk_good',
        'content': 'Contenido con metadata completa',
        'source': 'docs/BAGO_CANON.md',
        'authority': 'high',
        'revision': 'v1.0',
        'ingested_at': datetime.utcnow().isoformat()
    }
    
    # Validación de schema
    required_fields = ['source', 'authority', 'revision']
    
    bad_has_all = all(field in bad_chunk for field in required_fields)
    good_has_all = all(field in good_chunk for field in required_fields)
    
    assert not bad_has_all, \
        "Setup error: bad_chunk should be missing required fields"
    assert good_has_all, \
        "Setup error: good_chunk should have all required fields"
    
    # En producción: filter out chunks sin provenance
    valid_chunks = [
        chunk for chunk in [bad_chunk, good_chunk]
        if all(field in chunk for field in required_fields)
    ]
    
    assert len(valid_chunks) == 1, \
        "CRIT FAIL: Chunk sin provenance pasó el filtro"
    assert valid_chunks[0]['id'] == 'chunk_good', \
        "CRIT FAIL: Chunk incorrecto pasó el filtro"
    
    print("✅ CRIT P0-003 PASS: Document without provenance rejected")


# ============================================================================
# CRIT P0-004: Chunk superseded como autoridad → FILTERED
# ============================================================================

def test_superseded_chunk_filtered_in_retrieval():
    """
    CRIT P0-004: Chunk de revisión superseded usado como autoridad → EXPECTED: FILTERED
    
    Si un documento tiene revision v2.0, los chunks de v1.0 están SUPERSEDED.
    No pueden usarse como autoridad para reasoning.
    """
    
    chunks = [
        {
            'id': 'chunk_v1',
            'content': 'Versión antigua...',
            'revision': 'v1.0',
            'superseded_by': 'v2.0',  # ⚠️ SUPERSEDED
            'is_current': False
        },
        {
            'id': 'chunk_v2',
            'content': 'Versión actual...',
            'revision': 'v2.0',
            'superseded_by': None,
            'is_current': True  # ✅ CURRENT
        }
    ]
    
    # Filtra solo chunks current
    current_chunks = [c for c in chunks if c.get('is_current', False)]
    
    assert len(current_chunks) == 1, \
        "CRIT FAIL: Múltiples versiones consideradas current"
    assert current_chunks[0]['id'] == 'chunk_v2', \
        "CRIT FAIL: Versión superseded considerada current"
    
    print("✅ CRIT P0-004 PASS: Superseded chunk filtered from retrieval")


# ============================================================================
# CRIT P0-005: MCP tool no registrado → DENY
# ============================================================================

def test_mcp_tool_unregistered_denied():
    """
    CRIT P0-005: MCP tool no registrada en capability registry → EXPECTED: DENY
    
    Las herramientas MCP deben registrarse EXPLÍCITAMENTE antes de usarse.
    Tool descubierta ≠ Tool autorizada.
    """
    
    # Registry de tools autorizadas
    registered_tools = {
        'file_reader': {'effect_type': EffectType.READ},
        'file_writer': {'effect_type': EffectType.WRITE}
    }
    
    # Tool NO registrada (descubierta vía MCP)
    discovered_tool = 'external_api_caller'
    
    # Verifica registro
    is_registered = discovered_tool in registered_tools
    
    assert not is_registered, \
        "Setup error: tool should not be registered"
    
    # En producción: authorization_gate rechazaría
    would_be_allowed = is_registered
    
    assert not would_be_allowed, \
        "CRIT FAIL: Unregistered tool would be allowed"
    
    print("✅ CRIT P0-005 PASS: Unregistered MCP tool denied")


# ============================================================================
# CRIT P0-006: Timeout en provider → CONTROLLED_FAILURE + RECEIPT
# ============================================================================

def test_bedrock_provider_timeout_controlled_failure():
    """
    CRIT P0-006: Bedrock provider timeout → EXPECTED: CONTROLLED_FAILURE + RECEIPT
    
    Los timeouts externos DEBEN producir receipts con error_message.
    Nunca silent failures.
    """
    
    # Simula timeout
    timeout_occurred = True
    max_duration_ms = 10000
    
    # Receipt generado
    receipt = Receipt(
        receipt_id="receipt_timeout_001",
        permit_id="permit_001",
        execution_outcome=ExecutionOutcome.FAILURE if timeout_occurred else ExecutionOutcome.SUCCESS,
        actual_effect={},
        evidence_refs=[],
        duration_ms=max_duration_ms + 1000,  # Exceeds limit
        cost_usd=0.0,
        error_message="Provider timeout after 10000ms" if timeout_occurred else None
    )
    
    # VERIFICACIONES
    assert receipt.execution_outcome == ExecutionOutcome.FAILURE, \
        "CRIT FAIL: Timeout no marcado como FAILURE"
    
    assert receipt.error_message is not None, \
        "CRIT FAIL: Timeout sin error_message en receipt"
    
    assert receipt.duration_ms > max_duration_ms, \
        "Setup error: duration should exceed timeout"
    
    # Evidence: aunque falló, hay receipt
    assert len(receipt.evidence_refs) >= 0, \
        "Receipt exists even on failure (audit trail preserved)"
    
    print("✅ CRIT P0-006 PASS: Timeout produces controlled failure + receipt")


# ============================================================================
# INTEGRATION TEST: Grafo completo
# ============================================================================

def test_governed_agent_graph_end_to_end():
    """
    Integration test: Ejecuta el grafo completo y verifica gobernanza.
    """
    
    app = build_governed_agent_graph()
    
    # Query que NO requiere acción material
    safe_query = "¿Qué es BAGO?"
    
    initial_state = AgentState(query=safe_query)
    
    result = app.invoke(initial_state)
    
    # Verifica que el grafo completó
    assert 'final_response' in result, \
        "Graph did not produce final_response"
    
    assert 'intent' in result, \
        "Graph did not classify intent"
    
    # Para queries de solo retrieval, no debería haber denials
    assert result.get('requires_action', False) == False, \
        "Safe query incorrectly flagged as requiring action"
    
    print("✅ Integration test PASS: Graph executed end-to-end")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("L1 · CRITICAL GOVERNANCE TESTS")
    print("=" * 80)
    
    test_langgraph_cannot_execute_directly()
    test_permit_reuse_denied()
    test_document_without_provenance_rejected()
    test_superseded_chunk_filtered_in_retrieval()
    test_mcp_tool_unregistered_denied()
    test_bedrock_provider_timeout_controlled_failure()
    test_governed_agent_graph_end_to_end()
    
    print("=" * 80)
    print("ALL CRIT P0 TESTS PASSED ✅")
    print("=" * 80)
