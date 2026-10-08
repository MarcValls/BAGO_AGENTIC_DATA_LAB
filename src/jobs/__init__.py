"""Job history and execution tracking for agent runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

JOBS_DIR = Path(__file__).resolve().parent.parent.parent / "jobs" / "history"
JOBS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class JobExecution:
    """Represents a single job execution."""

    job_id: str
    agent_id: str | None  # None for demo runs
    job_type: str  # 'demo' or 'agent'
    status: str  # 'running', 'success', 'failed', 'timeout'
    created_at: str
    completed_at: str | None = None
    duration_ms: int | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    cost_usd: float = 0.0
    metrics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def save_job(job: JobExecution) -> None:
    """Save job to disk."""
    job_file = JOBS_DIR / f"{job.job_id}.json"
    job_file.write_text(json.dumps(job.to_dict(), indent=2))


def load_job(job_id: str) -> JobExecution | None:
    """Load job from disk."""
    job_file = JOBS_DIR / f"{job_id}.json"
    if not job_file.exists():
        return None

    try:
        data = json.loads(job_file.read_text())
        return JobExecution(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def list_jobs(limit: int = 50) -> list[JobExecution]:
    """List all jobs, most recent first."""
    jobs = []

    if JOBS_DIR.exists():
        for job_file in sorted(JOBS_DIR.glob("*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(job_file.read_text())
                jobs.append(JobExecution(**data))
            except (json.JSONDecodeError, TypeError):
                pass

    return jobs


def list_jobs_by_agent(agent_id: str, limit: int = 50) -> list[JobExecution]:
    """List all jobs for a specific agent."""
    return [j for j in list_jobs(limit * 2) if j.agent_id == agent_id][:limit]


def get_agent_metrics(agent_id: str) -> dict[str, Any]:
    """Compute aggregated metrics for an agent."""
    jobs = list_jobs_by_agent(agent_id, limit=100)

    if not jobs:
        return {
            "agent_id": agent_id,
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "avg_duration_ms": 0,
            "total_cost_usd": 0.0,
        }

    successful = [j for j in jobs if j.status == "success"]
    failed = [j for j in jobs if j.status == "failed"]

    avg_duration = (
        sum(j.duration_ms for j in successful if j.duration_ms) / len(successful)
        if successful
        else 0
    )
    total_cost = sum(j.cost_usd for j in jobs)

    return {
        "agent_id": agent_id,
        "total_runs": len(jobs),
        "successful_runs": len(successful),
        "failed_runs": len(failed),
        "success_rate": len(successful) / len(jobs) if jobs else 0,
        "avg_duration_ms": int(avg_duration),
        "total_cost_usd": round(total_cost, 4),
    }
