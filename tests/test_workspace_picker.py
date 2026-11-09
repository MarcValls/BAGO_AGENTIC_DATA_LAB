"""The native picker keeps its cancellation, cleanup and error contracts."""
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from src.api.workspace_picker import pick_workspace_directory


@pytest.mark.parametrize("selection, expected", [(r"C:\\project", r"C:\\project"), ("", None)])
def test_picker_returns_selection_and_closes_window(monkeypatch, selection, expected):
    events = []
    window = SimpleNamespace(
        withdraw=lambda: events.append("withdraw"),
        attributes=lambda *args: events.append(args),
        destroy=lambda: events.append("destroy"),
    )
    tk = ModuleType("tkinter")
    tk.Tk = lambda: window
    tk.filedialog = SimpleNamespace(askdirectory=lambda **kwargs: events.append(kwargs) or selection)
    monkeypatch.setitem(sys.modules, "tkinter", tk)

    assert pick_workspace_directory(Path("initial")) == expected
    assert events == ["withdraw", ("-topmost", True),
                      {"initialdir": str(Path("initial")), "title": "Select workspace folder", "mustexist": True},
                      "destroy"]


def test_picker_failure_closes_window_and_reports_unavailable(monkeypatch):
    events = []
    window = SimpleNamespace(withdraw=lambda: None, attributes=lambda *args: None,
                             destroy=lambda: events.append("destroy"))
    def fail(**kwargs):
        raise OSError("native failure")
    tk = ModuleType("tkinter")
    tk.Tk = lambda: window
    tk.filedialog = SimpleNamespace(askdirectory=fail)
    monkeypatch.setitem(sys.modules, "tkinter", tk)

    with pytest.raises(RuntimeError, match="folder picker is unavailable") as error:
        pick_workspace_directory(Path("initial"))
    assert isinstance(error.value.__cause__, OSError)
    assert events == ["destroy"]


def test_browse_endpoint_uses_extracted_picker_and_binds_selection(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from src.api import server

    selected = tmp_path / "chosen"
    selected.mkdir()
    window = SimpleNamespace(withdraw=lambda: None, attributes=lambda *args: None, destroy=lambda: None)
    tk = ModuleType("tkinter")
    tk.Tk = lambda: window
    tk.filedialog = SimpleNamespace(askdirectory=lambda **kwargs: str(selected))
    monkeypatch.setitem(sys.modules, "tkinter", tk)
    monkeypatch.setattr(server, "current_workspace_root", lambda: tmp_path)
    applied = []
    monkeypatch.setattr(server, "_set_workspace_root", lambda path: applied.append(path) or Path(path))

    response = TestClient(server.app).post("/api/workspace/browse")
    assert response.status_code == 200
    assert response.json() == {"workspace_root": str(selected), "cancelled": False}
    assert applied == [str(selected)]
