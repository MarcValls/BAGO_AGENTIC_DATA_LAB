"""Exact pure source extractions from MarcValls/BAGO_AGENTIC_DATA_LAB.
MIT license: THIRD_PARTY_LICENSE_ADL.txt. Provenance: SYNC_EXTRACTION.json.
No execute(), remote push/merge or subprocess runner is included.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import shutil
from typing import Any, Sequence


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    @property
    def output_hashes(self) -> dict[str, str]:
        return {
            "stdout_sha256": hashlib.sha256(self.stdout.encode("utf-8", "replace")).hexdigest(),
            "stderr_sha256": hashlib.sha256(self.stderr.encode("utf-8", "replace")).hexdigest(),
        }


@dataclass(frozen=True)
class ValidatorSpec:
    name: str
    argv: tuple[str, ...]

    @property
    def command_sha256(self) -> str:
        return hashlib.sha256("\0".join(self.argv).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GitSnapshot:
    root: str
    branch: str
    head: str
    remote: str
    remote_url: str
    upstream: str
    dirty_paths: tuple[str, ...]
    staged_paths: tuple[str, ...]
    ahead: int | None
    behind: int | None
    remote_branch_exists: bool

    @property
    def dirty(self) -> bool:
        return bool(self.dirty_paths)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "branch": self.branch,
            "head": self.head,
            "remote": self.remote,
            "remote_url": self.remote_url,
            "upstream": self.upstream,
            "dirty": self.dirty,
            "dirty_paths": list(self.dirty_paths),
            "staged_paths": list(self.staged_paths),
            "ahead": self.ahead,
            "behind": self.behind,
            "remote_branch_exists": self.remote_branch_exists,
        }


def _path_is_allowed(path: str, allowed: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    for raw in allowed:
        candidate = raw.replace("\\", "/").lstrip("./").rstrip("/")
        if normalized == candidate or normalized.startswith(candidate + "/"):
            return True
    return False


def _preflight_blockers(
    current: GitSnapshot,
    *,
    base: str,
    paths: Sequence[str],
    commit: bool,
    push: bool,
    merge_pr: int | None,
    preserve_unrelated_dirty: bool,
    allow_main_push: bool,
    validators: Sequence[ValidatorSpec],
    skip_validation: bool,
) -> list[str]:
    blockers: list[str] = []
    if not current.remote_url:
        blockers.append(f"no existe el remote {current.remote!r}")
    if current.branch == "detached":
        blockers.append("HEAD esta detached; el agente necesita una rama nombrada")
    if current.ahead is not None and current.behind is not None and current.ahead and current.behind:
        blockers.append(
            f"rama divergente: ahead={current.ahead}, behind={current.behind}; resolver manualmente"
        )
    if commit and not paths:
        blockers.append("commit solicitado sin --path; el alcance debe ser explicito")
    if commit and current.staged_paths:
        blockers.append("hay cambios staged preexistentes; no se pueden atribuir al agente")
    if commit and paths:
        outside = [path for path in current.dirty_paths if not _path_is_allowed(path, paths)]
        if outside and not preserve_unrelated_dirty:
            blockers.append(
                "hay cambios sucios fuera del alcance: " + ", ".join(outside[:8])
                + "; usar --preserve-unrelated-dirty solo si se desea preservarlos"
            )
    if (push or merge_pr is not None) and current.dirty and not commit and not preserve_unrelated_dirty:
        blockers.append("push/merge con worktree sucio requiere --preserve-unrelated-dirty")
    if (push or merge_pr is not None) and current.branch == base and not allow_main_push:
        blockers.append(
            f"push directo a {base!r} bloqueado; usar una rama/PR o --allow-main-push explicitamente"
        )
    if commit and not validators and not skip_validation:
        blockers.append("commit sin validadores; proporcionar --validator o --skip-validation explicitamente")
    if merge_pr is not None and shutil.which("gh") is None:
        blockers.append("merge solicitado pero GitHub CLI (gh) no esta disponible")
    return blockers


def build_plan(
    current: GitSnapshot,
    *,
    base: str,
    paths: Sequence[str],
    commit: bool,
    push: bool,
    merge_pr: int | None,
    preserve_unrelated_dirty: bool = False,
    allow_main_push: bool = False,
    validators: Sequence[ValidatorSpec] = (),
    skip_validation: bool = False,
) -> dict[str, Any]:
    blockers = _preflight_blockers(
        current,
        base=base,
        paths=paths,
        commit=commit,
        push=push,
        merge_pr=merge_pr,
        preserve_unrelated_dirty=preserve_unrelated_dirty,
        allow_main_push=allow_main_push,
        validators=validators,
        skip_validation=skip_validation,
    )
    actions: list[str] = ["fetch"]
    if current.behind and not current.ahead:
        actions.append("fast_forward_if_requested")
    if validators:
        actions.append(f"run_{len(validators)}_validator(s)_in_parallel")
    if commit:
        actions.extend(["stage_scoped_paths", "commit"])
    if push or merge_pr is not None:
        actions.append("push")
    if merge_pr is not None:
        actions.extend(["verify_pr_binding", "merge_pr", "verify_remote_merge"])
    return {
        "status": "BLOCKED" if blockers else "PREPARED",
        "branch": current.branch,
        "base": base,
        "actions": actions,
        "blockers": blockers,
        "paths": list(paths),
        "validators": [spec.name for spec in validators],
        "requested": {
            "commit": commit,
            "push": push,
            "merge_pr": merge_pr,
            "preserve_unrelated_dirty": preserve_unrelated_dirty,
            "allow_main_push": allow_main_push,
            "skip_validation": skip_validation,
        },
    }


def _action(name: str, status: str, result: CommandResult | None = None, detail: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"action": name, "status": status}
    if detail:
        payload["detail"] = detail
    if result is not None:
        payload["returncode"] = result.returncode
        payload["duration_ms"] = result.duration_ms
        payload["output_hashes"] = result.output_hashes
    return payload
