"""CRIT P0 contract tests for the canonical workspace binding."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.context.workspace_binding import (
    WorkspaceBinding,
    WorkspaceBindingError,
    normalize_repository_identity,
    workspace_binding_is_governed,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_workspace_binding_contract() -> None:
    binding = WorkspaceBinding.from_git(
        REPOSITORY_ROOT,
        context_revision="l9-workspace-v1",
    )

    assert workspace_binding_is_governed(binding)
    assert binding.repository_root == REPOSITORY_ROOT.resolve()
    assert binding.commit_sha
    assert len(binding.fingerprint) == 64


def test_workspace_binding_is_deterministic_for_same_snapshot() -> None:
    first = WorkspaceBinding.from_git(REPOSITORY_ROOT, context_revision="ctx-v1")
    second = WorkspaceBinding.from_git(REPOSITORY_ROOT, context_revision="ctx-v1")

    assert first == second
    assert first.to_dict() == second.to_dict()


def test_workspace_binding_rejects_path_escape() -> None:
    binding = WorkspaceBinding.from_git(REPOSITORY_ROOT, context_revision="ctx-v1")

    assert binding.is_in_scope(REPOSITORY_ROOT / "tests" / "test_workspace_binding.py")
    assert not binding.is_in_scope(REPOSITORY_ROOT.parent / "outside.txt")
    with pytest.raises(WorkspaceBindingError, match="outside bound workspace"):
        binding.assert_in_scope(REPOSITORY_ROOT.parent / "outside.txt")


def test_workspace_binding_requires_context_revision() -> None:
    with pytest.raises(WorkspaceBindingError, match="context_revision is required"):
        WorkspaceBinding.from_git(REPOSITORY_ROOT, context_revision=" ")


def test_workspace_binding_strips_remote_credentials() -> None:
    identity = normalize_repository_identity(
        "https://user:secret@example.com/owner/project.git"
    )

    assert identity == "example.com/owner/project"
    assert "secret" not in identity
    assert "user" not in identity


def test_workspace_binding_does_not_authorize_material_effects() -> None:
    binding = WorkspaceBinding.from_git(REPOSITORY_ROOT, context_revision="ctx-v1")

    assert workspace_binding_is_governed(binding)
    # The binding proves repository/context identity; permits still govern effects.
    assert not hasattr(binding, "permit_id")
