"""Native project-folder picker used by the local ADL host."""

from pathlib import Path


def pick_workspace_directory(initial: Path) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
        window = tk.Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        try:
            return filedialog.askdirectory(initialdir=str(initial), title="Select workspace folder", mustexist=True) or None
        finally:
            window.destroy()
    except Exception as error:
        raise RuntimeError("The Windows folder picker is unavailable in this session.") from error
