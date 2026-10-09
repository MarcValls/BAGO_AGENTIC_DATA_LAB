"""FastAPI server with control UI for running BAGO demo and managing agents.

Includes WebSocket for live logs, demo execution endpoint, artifact management,
agent builder API, and job history tracking.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.jobs import JobExecution, get_agent_metrics, list_jobs, load_job, save_job

DEMO_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "demo_output" / "latest"
AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "agents" / "created"
FRONTEND_BUILD = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

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
    name: str
    description: str
    type: str
    system_prompt: str
    tools: list[str]
    retrieval_config: dict[str, Any] | None = None
    sandbox_profile: str | None = None


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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def _load_team_status() -> dict[str, Any]:
    """Read a sanitized snapshot of the local teamctl coordination state."""
    team_dir = REPO_ROOT / ".codex-team"
    state_path = team_dir / "state.json"
    events_path = team_dir / "events.jsonl"

    if not state_path.is_file():
        raise HTTPException(status_code=404, detail="Team coordination state not found.")

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Team coordination state is invalid JSON: {exc}",
        ) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Team coordination state could not be read: {exc}",
        ) from exc

    if not isinstance(state, dict):
        raise HTTPException(status_code=503, detail="Team coordination state must be a JSON object.")

    mission = state.get("mission")
    work_items = mission.get("work_items") if isinstance(mission, dict) else None
    work_status = state.get("work_status")
    if not isinstance(mission, dict) or not isinstance(work_items, list) or not isinstance(work_status, dict):
        raise HTTPException(status_code=503, detail="Team coordination state has an unsupported shape.")

    tasks = []
    counts: dict[str, int] = {}
    for item in work_items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise HTTPException(status_code=503, detail="Team coordination state contains an invalid work item.")
        work_id = item["id"]
        title = item.get("title", work_id)
        role = item.get("role", "unknown")
        depends_on = item.get("depends_on", [])
        if (
            not isinstance(title, str)
            or not isinstance(role, str)
            or not isinstance(depends_on, list)
            or not all(isinstance(dependency, str) for dependency in depends_on)
        ):
            raise HTTPException(
                status_code=503,
                detail=f"Team coordination state contains invalid metadata for {work_id}.",
            )
        runtime = work_status.get(work_id)
        if not isinstance(runtime, dict) or not isinstance(runtime.get("status"), str):
            raise HTTPException(
                status_code=503,
                detail=f"Team coordination state is missing runtime status for {work_id}.",
            )
        status = runtime["status"]
        counts[status] = counts.get(status, 0) + 1
        tasks.append({
            "id": work_id,
            "title": title,
            "role": role,
            "depends_on": depends_on,
            "status": status,
            "agent": runtime.get("agent") if isinstance(runtime.get("agent"), str) else None,
            "claimed_at": runtime.get("claimed_at") if isinstance(runtime.get("claimed_at"), str) else None,
            "done_at": runtime.get("done_at") if isinstance(runtime.get("done_at"), str) else None,
        })

    recent_events: deque[dict[str, Any]] = deque(maxlen=50)
    if events_path.is_file():
        try:
            with events_path.open(encoding="utf-8") as event_file:
                for line_number, line in enumerate(event_file, start=1):
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise HTTPException(
                            status_code=503,
                            detail=f"Team event log has invalid JSON on line {line_number}: {exc}",
                        ) from exc
                    if not isinstance(event, dict):
                        raise HTTPException(
                            status_code=503,
                            detail=f"Team event log contains a non-object on line {line_number}.",
                        )
                    recent_events.append({
                        key: event[key]
                        for key in ("at", "kind", "work_id", "agent", "role", "from_agent", "note_kind")
                        if isinstance(event.get(key), str)
                    })
        except HTTPException:
            raise
        except (OSError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Team event log could not be read: {exc}",
            ) from exc

    active_agents = sorted({
        task["agent"]
        for task in tasks
        if task["status"] == "CLAIMED" and isinstance(task["agent"], str)
    })
    return {
        "source": "teamctl coordination files",
        "mission": {
            "id": mission.get("mission_id") if isinstance(mission.get("mission_id"), str) else "unknown",
            "title": mission.get("title") if isinstance(mission.get("title"), str) else "Untitled mission",
            "objective": mission.get("objective") if isinstance(mission.get("objective"), str) else "",
            "terminal_gate": state.get("terminal_gate") if isinstance(state.get("terminal_gate"), str) else "UNKNOWN",
            "max_concurrency": mission.get("max_concurrency")
            if isinstance(mission.get("max_concurrency"), int)
            else None,
        },
        "snapshot_updated_at": state.get("updated_at") if isinstance(state.get("updated_at"), str) else None,
        "observed_at": datetime.now().astimezone().isoformat(),
        "counts": counts,
        "active_agents": active_agents,
        "tasks": tasks,
        "recent_events": list(recent_events),
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


@app.get("/api/team/status")
def team_status() -> dict[str, Any]:
    """Return a read-only snapshot for the local team monitor page."""
    return _load_team_status()


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
    await websocket.accept()
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

@app.post("/api/agents/create")
async def create_agent(agent_config: AgentConfig) -> AgentResponse:
    """Create and save a new agent configuration."""
    if not agent_config.name or not agent_config.description:
        raise HTTPException(status_code=400, detail="Name and description required")

    agent_id = f"agent_{hash(agent_config.name) & 0xffffffff:08x}"
    agent_file = AGENTS_DIR / f"{agent_id}.json"

    response_data = {
        "id": agent_id,
        "config": agent_config.dict(),
        "created_at": datetime.utcnow().isoformat(),
    }

    agent_file.write_text(json.dumps(response_data, indent=2))

    return AgentResponse(**response_data)


@app.get("/api/agents/list")
async def list_agents() -> dict[str, list[AgentResponse]]:
    """List all created agents."""
    agents = []

    if AGENTS_DIR.exists():
        for agent_file in AGENTS_DIR.glob("*.json"):
            try:
                data = json.loads(agent_file.read_text())
                agents.append(AgentResponse(**data))
            except (json.JSONDecodeError, TypeError):
                pass

    return {"agents": agents}


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
    agent_file = AGENTS_DIR / f"{agent_id}.json"

    if not agent_file.exists():
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        data = json.loads(agent_file.read_text())
        return AgentResponse(**data)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail="Error reading agent")


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
    """WebSocket for agent execution with streaming logs."""
    await websocket.accept()
    active_connections.append(websocket)

    job_id = f"job_{uuid.uuid4().hex[:8]}"
    agent_id = None

    try:
        # Wait for agent config
        data = await websocket.receive_text()
        msg = json.loads(data)
        agent_id = msg.get("agent_id")
        config = msg.get("config")

        if not config:
            raise ValueError("Missing agent config")

        job = JobExecution(
            job_id=job_id,
            agent_id=agent_id,
            job_type="agent",
            status="running",
            created_at=datetime.utcnow().isoformat(),
        )
        save_job(job)

        await websocket.send_json({"type": "stdout", "data": f"[INFO] Starting agent execution: {config.get('name', 'Unknown')}"})
        await websocket.send_json({"type": "stdout", "data": f"[INFO] Agent ID: {agent_id}"})
        await websocket.send_json({"type": "stdout", "data": f"[INFO] Job ID: {job_id}"})
        await websocket.send_json({"type": "stdout", "data": f"[INFO] Agent Type: {config.get('type')}"})
        await websocket.send_json({"type": "stdout", "data": f"[INFO] Tools: {', '.join(config.get('tools', []))}"})

        start_time = datetime.utcnow()

        # Simulate agent execution (in production, would call actual agent)
        await asyncio.sleep(1)
        await websocket.send_json({"type": "stdout", "data": "[INFO] Retrieving context..."})
        await asyncio.sleep(1)
        await websocket.send_json({"type": "stdout", "data": "[INFO] Reasoning over context..."})
        await asyncio.sleep(1)
        await websocket.send_json({"type": "stdout", "data": "[SUCCESS] Agent execution completed."})

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        job.status = "success"
        job.exit_code = 0
        job.duration_ms = duration_ms
        job.completed_at = datetime.utcnow().isoformat()
        job.metrics = {
            "retrieval_hits": 2,
            "ontology_paths": 1,
            "tools_used": len(config.get("tools", [])),
        }
        save_job(job)

        await websocket.send_json({
            "type": "done",
            "exit_code": 0,
            "job_id": job_id,
            "duration_ms": duration_ms,
            "cost_usd": 0.0,
            "metrics": job.metrics,
        })

    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000) if 'start_time' in locals() else 0
        job = JobExecution(
            job_id=job_id,
            agent_id=agent_id,
            job_type="agent",
            status="failed",
            created_at=datetime.utcnow().isoformat(),
            completed_at=datetime.utcnow().isoformat(),
            duration_ms=duration_ms,
            stderr=str(e),
        )
        save_job(job)

        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except RuntimeError:
            pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)


# ===== WebSocket: Agent Chat =====

@app.websocket("/ws/agents/chat")
async def websocket_agent_chat(websocket: WebSocket) -> None:
    """WebSocket for interactive agent chat with streaming responses."""
    await websocket.accept()
    active_connections.append(websocket)

    try:
        # Receive chat request
        data = await websocket.receive_text()
        msg = json.loads(data)

        agent_id = msg.get("agent_id")
        config = msg.get("config")
        user_message = msg.get("message")
        conversation_history = msg.get("conversation_history", [])

        if not config or not user_message:
            raise ValueError("Missing agent config or message")

        # Simulate agent response (in production, would call LLM)
        await websocket.send_json({"type": "chunk", "data": f"I'm {config.get('name')}. "})
        await asyncio.sleep(0.1)

        await websocket.send_json({"type": "chunk", "data": "You asked: "})
        await asyncio.sleep(0.1)

        await websocket.send_json({"type": "chunk", "data": f"{user_message} "})
        await asyncio.sleep(0.1)

        await websocket.send_json({"type": "chunk", "data": ""})
        await asyncio.sleep(0.2)

        # Simulate context-aware response
        tools_mention = f"I have access to {len(config.get('tools', []))} tools: "
        await websocket.send_json({"type": "chunk", "data": tools_mention})
        await asyncio.sleep(0.1)

        for tool in config.get("tools", [])[:2]:
            await websocket.send_json({"type": "chunk", "data": f"{tool}, "})
            await asyncio.sleep(0.05)

        await websocket.send_json({"type": "chunk", "data": "and more. "})
        await asyncio.sleep(0.1)

        await websocket.send_json({"type": "chunk", "data": "How can I help you further?"})
        await asyncio.sleep(0.1)

        # Send completion signal
        await websocket.send_json({"type": "done"})

    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
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

    uvicorn.run(app, host="0.0.0.0", port=8080)
