"""FastAPI server with control UI for running BAGO demo and managing agents.

Includes WebSocket for live logs, demo execution endpoint, artifact management,
agent builder API, and job history tracking.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.jobs import JobExecution, get_agent_metrics, list_jobs, load_job, save_job
from src.providers import ollama

DEMO_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "demo_output" / "latest"
AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "agents" / "created"
FRONTEND_BUILD = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_TOOL_ALLOWLIST = frozenset({
    "bedrock.converse",
    "mcp.execute",
    "ontology.query",
    "retrieval.search",
    "sandbox.run",
})

# Ensure agents directory exists
AGENTS_DIR.mkdir(parents=True, exist_ok=True)


class DemoRequest(BaseModel):
    write_evidence: bool = False
    json_output: bool = False


class DemoRunResponse(BaseModel):
    status: str
    exit_code: int
    stdout: str
    stderr: str


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    type: Literal["rag", "tool", "multi-agent"]
    system_prompt: str = Field(min_length=1, max_length=12000)
    # Older user-created agents predate provider/model pinning. Keep them
    # readable without migrating their persisted records as a side effect.
    provider_id: Literal["ollama-cloud"] | None = None
    model_id: str | None = Field(default=None, min_length=1, max_length=128)
    tools: list[str] = Field(default_factory=list, max_length=20)
    retrieval_config: dict[str, Any] | None = None
    sandbox_profile: str | None = Field(default=None, max_length=100)

    @field_validator("tools")
    @classmethod
    def only_registered_tools(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(tool not in AGENT_TOOL_ALLOWLIST for tool in value):
            raise ValueError("Agent contains an unregistered tool.")
        return value

    @field_validator("model_id")
    @classmethod
    def valid_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return ollama.validate_model_id(value)
        except ollama.ProviderError as error:
            raise ValueError(error.message) from None


class OllamaConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_mode: Literal["api_key", "local_cli"]
    api_key: str | None = Field(default=None, max_length=4096)
    model_id: str | None = Field(default=None, max_length=128)


class OllamaVerifyRequest(BaseModel):
    model_id: str | None = Field(default=None, max_length=128)


class AgentCreateRequest(BaseModel):
    """Create body also accepts the legacy Builder shape without provider fields."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    type: Literal["rag", "tool", "multi-agent"]
    system_prompt: str = Field(min_length=1, max_length=12000)
    provider_id: Literal["ollama-cloud"] | None = None
    model_id: str | None = Field(default=None, max_length=128)
    tools: list[str] = Field(default_factory=list, max_length=20)
    retrieval_config: dict[str, Any] | None = None
    sandbox_profile: str | None = Field(default=None, max_length=100)

    @field_validator("tools")
    @classmethod
    def only_registered_tools(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(tool not in AGENT_TOOL_ALLOWLIST for tool in value):
            raise ValueError("Agent contains an unregistered tool.")
        return value

    @field_validator("model_id")
    @classmethod
    def valid_model(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return ollama.validate_model_id(value)
        except ollama.ProviderError as error:
            raise ValueError(error.message) from None


class ControlChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["chat", "list_agents", "draft_agent", "navigate"] = "chat"
    message: str = Field(default="", max_length=8000)
    view: Literal["inspector", "builder", "chat", "runner", "control", "jobs", "traces"] | None = None


class AgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=8000)
    conversation_history: list[dict[str, str]] = Field(default_factory=list, max_length=30)


class AgentResponse(BaseModel):
    id: str
    config: AgentConfig
    created_at: str


class JobResponse(BaseModel):
    job_id: str
    agent_id: str | None
    job_type: str
    status: str
    created_at: str
    completed_at: str | None
    duration_ms: int | None
    exit_code: int | None
    cost_usd: float
    metrics: dict[str, Any] | None


app = FastAPI(title="BAGO Portfolio Control", version="1.0.0")


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic validation details can contain submitted values, including API keys.
    return JSONResponse(status_code=422, content={"detail": {"code": "invalid_request", "message": "Request data failed validation."}})

# CORS
_local_ui_origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_configured_api_port = os.environ.get("BAGO_API_PORT", "8080")
if not _configured_api_port.isdigit() or not 1 <= int(_configured_api_port) <= 65535:
    raise RuntimeError("BAGO_API_PORT must be an integer between 1 and 65535.")
if _configured_api_port != "8080":
    _local_ui_origins.extend([
        f"http://localhost:{_configured_api_port}",
        f"http://127.0.0.1:{_configured_api_port}",
    ])
_cors_origins = [origin.strip() for origin in os.environ.get("BAGO_CORS_ORIGINS", ",".join(_local_ui_origins)).split(",") if origin.strip()]
for _origin in _cors_origins:
    _parsed_origin = urlsplit(_origin)
    if (
        _parsed_origin.scheme not in {"http", "https"}
        or _parsed_origin.hostname not in {"localhost", "127.0.0.1", "::1"}
        or _parsed_origin.path
        or _parsed_origin.query
        or _parsed_origin.fragment
        or _parsed_origin.username
        or _parsed_origin.password
    ):
        raise RuntimeError("BAGO_CORS_ORIGINS may contain only explicit localhost origins until API authentication is enabled.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _accept_local_websocket(websocket: WebSocket) -> bool:
    """Require the same explicit local browser origin as the HTTP UI."""
    origin = websocket.headers.get("origin")
    if not origin or origin not in _cors_origins:
        await websocket.close(code=1008, reason="WebSocket origin is not allowed.")
        return False
    await websocket.accept()
    return True


def _load_artifacts() -> dict[str, Any]:
    """Load all demo artifacts from disk."""
    if not DEMO_OUTPUT_DIR.exists():
        raise HTTPException(
            status_code=404,
            detail="No demo artifacts found. Run demo first.",
        )

    summary_path = DEMO_OUTPUT_DIR / "summary.json"
    agent_run_path = DEMO_OUTPUT_DIR / "agent_run.json"
    receipts_path = DEMO_OUTPUT_DIR / "receipts.json"
    trace_path = DEMO_OUTPUT_DIR / "trace.json"
    evaluation_path = DEMO_OUTPUT_DIR / "evaluation.json"

    missing = [
        p.name for p in [summary_path, agent_run_path, receipts_path, trace_path, evaluation_path]
        if not p.exists()
    ]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Missing artifacts: {', '.join(missing)}",
        )

    return {
        "summary": json.loads(summary_path.read_text()),
        "agent_run": json.loads(agent_run_path.read_text()),
        "receipts": json.loads(receipts_path.read_text()),
        "trace": json.loads(trace_path.read_text()),
        "evaluation": json.loads(evaluation_path.read_text()),
    }


# ===== API: Artifact Viewing =====

@app.get("/api/artifacts")
def get_artifacts() -> dict[str, Any]:
    """Get all demo artifacts."""
    return _load_artifacts()


@app.get("/api/summary")
def get_summary() -> dict[str, Any]:
    """Get summary only."""
    return _load_artifacts()["summary"]


@app.get("/api/agent-run")
def get_agent_run() -> dict[str, Any]:
    """Get agent run details."""
    return _load_artifacts()["agent_run"]


@app.get("/api/receipts")
def get_receipts() -> dict[str, Any]:
    """Get receipts."""
    return _load_artifacts()["receipts"]


@app.get("/api/trace")
def get_trace() -> dict[str, Any]:
    """Get trace events."""
    return _load_artifacts()["trace"]


@app.get("/api/evaluation")
def get_evaluation() -> dict[str, Any]:
    """Get evaluation results."""
    return _load_artifacts()["evaluation"]


# ===== API: Health & Demo Status =====

@app.get("/api/health")
def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


# ===== API: Ollama provider configuration =====

def _provider_http_error(error: ollama.ProviderError) -> HTTPException:
    status_code = 503
    if error.code.startswith("invalid_") or error.code == "unexpected_secret":
        status_code = 422
    elif error.code in {"authentication_required", "authentication_failed"}:
        status_code = 401
    return HTTPException(status_code=status_code, detail={"code": error.code, "message": error.message, "state": error.status})


@app.get("/api/providers/ollama/status")
def ollama_status() -> dict[str, Any]:
    return ollama.status()


@app.put("/api/providers/ollama/config")
def configure_ollama(request: OllamaConfigRequest) -> dict[str, Any]:
    try:
        return ollama.save_config(request.auth_mode, request.model_id, request.api_key)
    except ollama.ProviderError as error:
        raise _provider_http_error(error) from None
    except Exception:
        raise HTTPException(status_code=503, detail={"code": "provider_configuration_failed", "message": "Ollama settings could not be saved."}) from None


@app.get("/api/providers/ollama/models")
def ollama_models() -> dict[str, Any]:
    try:
        return ollama.discover_models()
    except ollama.ProviderError as error:
        raise _provider_http_error(error) from None


@app.post("/api/providers/ollama/verify")
def verify_ollama(request: OllamaVerifyRequest) -> dict[str, Any]:
    try:
        return ollama.verify(request.model_id)
    except ollama.ProviderError as error:
        raise _provider_http_error(error) from None


@app.get("/api/demo/status")
def demo_status() -> dict[str, Any]:
    """Check if demo has been run."""
    if not DEMO_OUTPUT_DIR.exists():
        return {"status": "not_run", "has_artifacts": False}

    artifacts = [
        DEMO_OUTPUT_DIR / "summary.json",
        DEMO_OUTPUT_DIR / "agent_run.json",
        DEMO_OUTPUT_DIR / "receipts.json",
        DEMO_OUTPUT_DIR / "trace.json",
        DEMO_OUTPUT_DIR / "evaluation.json",
    ]
    has_all = all(a.exists() for a in artifacts)

    return {
        "status": "ready" if has_all else "incomplete",
        "has_artifacts": has_all,
        "artifact_count": sum(1 for a in artifacts if a.exists()),
    }


# ===== API: Demo Execution =====

@app.post("/api/demo/run")
async def run_demo(request: DemoRequest) -> DemoRunResponse:
    """Execute python demo.py with optional flags."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    job = JobExecution(
        job_id=job_id,
        agent_id=None,
        job_type="demo",
        status="running",
        created_at=datetime.utcnow().isoformat(),
    )
    save_job(job)

    cmd = ["python", str(REPO_ROOT / "demo.py"), "--no-bootstrap"]

    if request.write_evidence:
        cmd.append("--write-evidence")
    if request.json_output:
        cmd.append("--json")

    start_time = datetime.utcnow()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        job.status = "success" if result.returncode == 0 else "failed"
        job.exit_code = result.returncode
        job.completed_at = datetime.utcnow().isoformat()
        job.duration_ms = duration_ms
        job.stdout = result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout
        job.stderr = result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr
        save_job(job)

        return DemoRunResponse(
            status=job.status,
            exit_code=result.returncode,
            stdout=result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
            stderr=result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        job.status = "timeout"
        job.duration_ms = duration_ms
        job.completed_at = datetime.utcnow().isoformat()
        job.stderr = "Demo execution timed out after 300 seconds"
        save_job(job)

        return DemoRunResponse(
            status="timeout",
            exit_code=-1,
            stdout="",
            stderr="Demo execution timed out after 300 seconds",
        )
    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        job.status = "failed"
        job.duration_ms = duration_ms
        job.completed_at = datetime.utcnow().isoformat()
        job.stderr = str(e)
        save_job(job)

        return DemoRunResponse(
            status="error",
            exit_code=-1,
            stdout="",
            stderr=str(e),
        )


# ===== WebSocket: Live Demo Execution =====

active_connections: list[WebSocket] = []


@app.websocket("/ws/demo/run")
async def websocket_demo_run(websocket: WebSocket) -> None:
    """WebSocket for live demo execution with streaming logs."""
    if not await _accept_local_websocket(websocket):
        return
    active_connections.append(websocket)

    job_id = f"job_{uuid.uuid4().hex[:8]}"
    job = JobExecution(
        job_id=job_id,
        agent_id=None,
        job_type="demo",
        status="running",
        created_at=datetime.utcnow().isoformat(),
    )
    save_job(job)

    try:
        # Wait for command
        data = await websocket.receive_text()
        msg = json.loads(data)

        cmd = ["python", str(REPO_ROOT / "demo.py"), "--no-bootstrap"]
        if msg.get("write_evidence"):
            cmd.append("--write-evidence")
        if msg.get("json_output"):
            cmd.append("--json")

        start_time = datetime.utcnow()

        # Start process
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(REPO_ROOT),
        )

        # Stream stdout
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            await websocket.send_json({
                "type": "stdout",
                "data": line.decode().rstrip(),
            })

        # Wait for completion
        await proc.wait()

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        job.status = "success" if proc.returncode == 0 else "failed"
        job.exit_code = proc.returncode
        job.duration_ms = duration_ms
        job.completed_at = datetime.utcnow().isoformat()
        save_job(job)

        # Send exit code
        await websocket.send_json({
            "type": "done",
            "exit_code": proc.returncode,
            "job_id": job_id,
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        job.status = "failed"
        job.stderr = str(e)
        job.completed_at = datetime.utcnow().isoformat()
        save_job(job)

        try:
            await websocket.send_json({
                "type": "error",
                "data": str(e),
            })
        except RuntimeError:
            pass
    finally:
        active_connections.remove(websocket)


# ===== API: Agent Management =====

def _read_agent_records() -> tuple[list[AgentResponse], list[str]]:
    records: list[AgentResponse] = []
    warnings: list[str] = []
    if not AGENTS_DIR.exists():
        return records, warnings
    for agent_file in sorted(AGENTS_DIR.glob("*.json")):
        try:
            data = json.loads(agent_file.read_text(encoding="utf-8"))
            record = AgentResponse.model_validate(data)
            if not re.fullmatch(r"agent_[0-9a-f]{8,32}", record.id) or agent_file.name != f"{record.id}.json":
                raise ValueError("Agent identity does not match its file.")
            records.append(record)
        except Exception:
            warnings.append(agent_file.name)
    return records, warnings


def _load_agent(agent_id: str) -> AgentResponse:
    if not re.fullmatch(r"agent_[0-9a-f]{8,32}", agent_id):
        raise HTTPException(status_code=404, detail="Agent not found.")
    agent_file = AGENTS_DIR / f"{agent_id}.json"
    try:
        data = json.loads(agent_file.read_text(encoding="utf-8"))
        record = AgentResponse.model_validate(data)
        if record.id != agent_id:
            raise ValueError("Agent identity mismatch.")
        return record
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found.") from None
    except Exception:
        raise HTTPException(status_code=500, detail="Stored agent configuration is invalid.") from None


def _write_agent(config: AgentConfig) -> AgentResponse:
    response_data = {"id": f"agent_{uuid.uuid4().hex}", "config": config.model_dump(), "created_at": datetime.utcnow().isoformat()}
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    agent_file = AGENTS_DIR / f"{response_data['id']}.json"
    temporary = agent_file.with_suffix(".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(response_data, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, agent_file)
    finally:
        if temporary.exists():
            temporary.unlink()
    return AgentResponse.model_validate(response_data)


def _selected_model_id() -> str:
    provider_status = ollama.status()
    model_id = provider_status.get("model_id")
    if not model_id or provider_status.get("state") in {"not_configured", "needs_authentication", "local_service_unavailable", "error"}:
        raise HTTPException(status_code=503, detail={"code": "provider_not_ready", "message": "Configure an Ollama model before sending a chat message."})
    return model_id

@app.post("/api/agents/create")
async def create_agent(request: AgentCreateRequest) -> AgentResponse:
    """Create and save a new agent configuration."""
    provider_status = ollama.status()
    if provider_status.get("state") not in {"configured_unverified", "ready"}:
        raise HTTPException(status_code=409, detail={"code": "provider_not_configured", "message": "Configure and authenticate Ollama before creating an agent."})
    body = request.model_dump(exclude_none=True)
    body["provider_id"] = request.provider_id or "ollama-cloud"
    # The legacy Builder has no model selector. In that case, use only the model
    # explicitly saved in Provider Settings; never choose the first catalog entry.
    body["model_id"] = request.model_id or provider_status.get("model_id")
    if not body["model_id"]:
        raise HTTPException(status_code=409, detail={"code": "model_selection_required", "message": "Choose a model in Ollama Provider Settings before creating an agent."})
    try:
        agent_config = AgentConfig.model_validate(body)
    except Exception:
        raise HTTPException(status_code=422, detail={"code": "invalid_agent_config", "message": "Agent configuration is invalid."}) from None
    return _write_agent(agent_config)


@app.get("/api/agents/list")
async def list_agents() -> dict[str, Any]:
    """List all created agents."""
    agents, warnings = _read_agent_records()
    return {"agents": agents, "count": len(agents), "warning_count": len(warnings), "warnings": warnings}


@app.get("/api/agents/export")
async def export_agents() -> dict[str, Any]:
    """Export all agents as JSON (for download)."""
    agents = []

    if AGENTS_DIR.exists():
        for agent_file in AGENTS_DIR.glob("*.json"):
            try:
                data = json.loads(agent_file.read_text())
                agents.append(data)
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        "agents": agents,
        "export_date": datetime.utcnow().isoformat(),
        "count": len(agents),
    }


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str) -> AgentResponse:
    """Get a specific agent by ID."""
    return _load_agent(agent_id)


@app.post("/api/chat/control")
async def control_chat(request: ControlChatRequest) -> dict[str, Any]:
    """One bounded chat turn; model output cannot execute app capabilities."""
    if request.operation == "list_agents":
        agents, warnings = _read_agent_records()
        return {"operation": "list_agents", "assistant_message": f"There are {len(agents)} configured application agents.", "agents": agents, "count": len(agents), "warning_count": len(warnings), "warnings": warnings}
    if request.operation == "navigate":
        if request.view is None:
            raise HTTPException(status_code=422, detail={"code": "view_required", "message": "Choose one of the existing views."})
        return {"operation": "navigate", "assistant_message": f"Opening {request.view}.", "navigation": {"view": request.view}}
    if not request.message.strip():
        raise HTTPException(status_code=422, detail={"code": "message_required", "message": "Enter a message."})

    model_id = _selected_model_id()
    if request.operation == "draft_agent":
        system_prompt = (
            "Create a proposed application agent configuration from the user's request. Return only one JSON object "
            "with keys name, description, type, system_prompt, tools, retrieval_config, sandbox_profile. "
            "type must be rag, tool, or multi-agent. tools may contain only: "
            + ", ".join(sorted(AGENT_TOOL_ALLOWLIST))
            + ". Do not request, claim, or perform any tool or app action. Keep tools empty unless requested and justified. "
            "This is a proposal only; do not claim that an agent was created."
        )
        try:
            raw = await asyncio.to_thread(ollama.chat, model_id, [{"role": "system", "content": system_prompt}, {"role": "user", "content": request.message.strip()}])
            draft_data = json.loads(raw)
            if not isinstance(draft_data, dict):
                raise ValueError("Expected object")
            draft_data["provider_id"] = "ollama-cloud"
            draft_data["model_id"] = model_id
            draft = AgentConfig.model_validate(draft_data)
        except ollama.ProviderError as error:
            raise _provider_http_error(error) from None
        except Exception:
            raise HTTPException(status_code=502, detail={"code": "invalid_agent_draft", "message": "The model did not produce a valid agent proposal. No agent was created."}) from None
        return {"operation": "draft_agent", "assistant_message": "Review this proposal. It will not be saved until you choose Create agent.", "agent_draft": draft.model_dump(), "created": False}

    try:
        answer = await asyncio.to_thread(ollama.chat, model_id, [
            {"role": "system", "content": "You are BAGO's app assistant. You can explain the application and its registered views. You cannot execute tools, create agents, run jobs, change files, or claim those actions occurred. If a user asks for an action, explain the available review flow."},
            {"role": "user", "content": request.message.strip()},
        ])
    except ollama.ProviderError as error:
        raise _provider_http_error(error) from None
    return {"operation": "chat", "assistant_message": answer, "agent_draft": None}


@app.post("/api/agents/{agent_id}/chat")
async def chat_with_agent(agent_id: str, request: AgentChatRequest) -> dict[str, Any]:
    """Chat with one persisted agent; never accept config/tool authority from the client."""
    record = _load_agent(agent_id)
    if not request.message.strip():
        raise HTTPException(status_code=422, detail={"code": "message_required", "message": "Enter a message."})
    messages = [{"role": "system", "content": record.config.system_prompt + "\n\nYou do not have live tool execution or app-control capabilities in this chat. Never claim to have executed them."}]
    for entry in request.conversation_history:
        role = entry.get("role")
        content = entry.get("content", "")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip() or len(content) > 4000:
            raise HTTPException(status_code=422, detail={"code": "invalid_history", "message": "Conversation history contains an invalid entry."})
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": request.message.strip()})
    # New records pin a model; legacy records may not. In that case use only
    # the explicitly selected provider model for this request, without writing
    # the fallback into the stored agent configuration.
    model_id = record.config.model_id or _selected_model_id()
    try:
        answer = await asyncio.to_thread(ollama.chat, model_id, messages)
    except ollama.ProviderError as error:
        raise _provider_http_error(error) from None
    return {"agent_id": agent_id, "assistant_message": answer, "source": "ollama"}


# ===== API: Job History & Metrics =====

@app.get("/api/jobs/list")
async def jobs_list(limit: int = 50) -> dict[str, list[JobResponse]]:
    """List all jobs, most recent first."""
    jobs = list_jobs(limit)
    return {
        "jobs": [
            JobResponse(
                job_id=j.job_id,
                agent_id=j.agent_id,
                job_type=j.job_type,
                status=j.status,
                created_at=j.created_at,
                completed_at=j.completed_at,
                duration_ms=j.duration_ms,
                exit_code=j.exit_code,
                cost_usd=j.cost_usd,
                metrics=j.metrics,
            )
            for j in jobs
        ]
    }


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> JobResponse | dict:
    """Get a specific job by ID."""
    job = load_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        job_id=job.job_id,
        agent_id=job.agent_id,
        job_type=job.job_type,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        duration_ms=job.duration_ms,
        exit_code=job.exit_code,
        cost_usd=job.cost_usd,
        metrics=job.metrics,
    )


@app.get("/api/agents/{agent_id}/metrics")
async def agent_metrics(agent_id: str) -> dict[str, Any]:
    """Get aggregated metrics for an agent."""
    return get_agent_metrics(agent_id)


# ===== API: Agent Export/Import =====

@app.get("/api/agents/export")
async def export_agents() -> dict[str, Any]:
    """Export all agents as JSON (for download)."""
    agents = []

    if AGENTS_DIR.exists():
        for agent_file in AGENTS_DIR.glob("*.json"):
            try:
                data = json.loads(agent_file.read_text())
                agents.append(data)
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        "agents": agents,
        "export_date": datetime.utcnow().isoformat(),
        "count": len(agents),
    }


@app.post("/api/agents/import")
async def import_agents(file: Any) -> dict[str, Any]:
    """Import agents from JSON file."""
    # In production, would parse JSON/ZIP and save agents
    return {"status": "imported", "count": 0}


# ===== API: GitHub Actions Integration =====

@app.get("/api/ci/workflows")
async def list_workflows() -> dict[str, Any]:
    """List GitHub Actions workflows (mock)."""
    return {
        "workflows": [
            {
                "id": "ci",
                "name": "CI",
                "state": "active",
                "path": ".github/workflows/ci.yml",
            },
        ],
        "total_count": 1,
    }


@app.post("/api/ci/workflows/{workflow_id}/dispatch")
async def dispatch_workflow(workflow_id: str) -> dict[str, Any]:
    """Trigger a GitHub Actions workflow (mock)."""
    return {
        "status": "dispatched",
        "workflow_id": workflow_id,
        "run_id": f"run_{uuid.uuid4().hex[:8]}",
        "created_at": datetime.utcnow().isoformat(),
    }


# ===== WebSocket: Agent Execution =====

@app.websocket("/ws/agents/run")
async def websocket_agent_run(websocket: WebSocket) -> None:
    """Fail closed until an agent has a real governed execution path."""
    if not await _accept_local_websocket(websocket):
        return
    try:
        await websocket.send_json({
            "type": "error",
            "code": "execution_unavailable",
            "data": "Agent execution is unavailable: no governed execution capability is registered. No job was started or recorded.",
        })
    except (RuntimeError, WebSocketDisconnect):
        pass
    finally:
        try:
            await websocket.close(code=1008)
        except RuntimeError:
            pass


# ===== WebSocket: Agent Chat =====

@app.websocket("/ws/agents/chat")
async def websocket_agent_chat(websocket: WebSocket) -> None:
    """Legacy transport backed by the same real, server-owned agent chat."""
    if not await _accept_local_websocket(websocket):
        return
    active_connections.append(websocket)

    try:
        # Receive chat request
        msg = json.loads(await websocket.receive_text())
        if not isinstance(msg, dict) or not isinstance(msg.get("agent_id"), str) or not isinstance(msg.get("message"), str):
            raise ValueError("A valid agent ID and message are required.")
        record = _load_agent(msg["agent_id"])
        history = msg.get("conversation_history", [])
        if not isinstance(history, list) or len(history) > 30:
            raise ValueError("Conversation history is invalid.")
        messages = [{"role": "system", "content": record.config.system_prompt + "\n\nYou do not have live tool execution or app-control capabilities in this chat."}]
        for entry in history:
            if not isinstance(entry, dict) or entry.get("role") not in {"user", "assistant"} or not isinstance(entry.get("content"), str) or len(entry["content"]) > 4000:
                raise ValueError("Conversation history is invalid.")
            messages.append({"role": entry["role"], "content": entry["content"]})
        messages.append({"role": "user", "content": msg["message"][:8000]})
        try:
            model_id = record.config.model_id or _selected_model_id()
        except HTTPException as error:
            detail = error.detail if isinstance(error.detail, dict) else {}
            await websocket.send_json({
                "type": "error",
                "code": detail.get("code", "provider_not_ready"),
                "data": detail.get("message", "Configure an Ollama model before chatting with this agent."),
            })
            return
        try:
            answer = await asyncio.to_thread(ollama.chat, model_id, messages)
        except ollama.ProviderError as error:
            await websocket.send_json({"type": "error", "data": error.message, "code": error.code})
            return
        await websocket.send_json({"type": "chunk", "data": answer})
        await websocket.send_json({"type": "done", "source": "ollama"})
    except (ValueError, json.JSONDecodeError):
        try:
            await websocket.send_json({"type": "error", "data": "Invalid chat request."})
        except RuntimeError:
            pass
    except HTTPException as error:
        try:
            detail = error.detail
            message = detail.get("message", "Agent chat could not be completed.") if isinstance(detail, dict) else "Agent chat could not be completed."
            await websocket.send_json({"type": "error", "data": message})
        except RuntimeError:
            pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)


# ===== API: GitHub Actions Integration =====

@app.get("/api/ci/workflows")
async def list_workflows() -> dict[str, Any]:
    """List GitHub Actions workflows (mock)."""
    return {
        "workflows": [
            {
                "id": "ci",
                "name": "CI",
                "state": "active",
                "path": ".github/workflows/ci.yml",
            },
        ],
        "total_count": 1,
    }


@app.post("/api/ci/workflows/{workflow_id}/dispatch")
async def dispatch_workflow(workflow_id: str) -> dict[str, Any]:
    """Trigger a GitHub Actions workflow (mock)."""
    return {
        "status": "dispatched",
        "workflow_id": workflow_id,
        "run_id": f"run_{uuid.uuid4().hex[:8]}",
        "created_at": datetime.utcnow().isoformat(),
    }


# ===== Serve React Frontend =====

if FRONTEND_BUILD.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_BUILD), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    runtime_mode = os.environ.get("BAGO_RUNTIME_MODE", "host").lower()
    api_host = os.environ.get("BAGO_API_HOST", "127.0.0.1")
    if runtime_mode == "container":
        if api_host != "0.0.0.0":
            raise RuntimeError("Container runtime must bind the API to its container interface.")
    elif api_host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Host-local runtime only supports loopback API binding until API authentication is enabled.")
    uvicorn.run(app, host=api_host, port=int(_configured_api_port))
