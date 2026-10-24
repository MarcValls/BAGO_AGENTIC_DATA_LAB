"""Verify actual Python/Pillow/ffmpeg and a fresh local SDK effect."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

sys.path.insert(0, "/workspace")
from src.conversations import ConversationStore

assert sys.version_info[:2] == (3, 11)
assert shutil.which("ffmpeg")
assert shutil.which("git")
with tempfile.TemporaryDirectory(prefix="bago-container-sdk-") as temporary:
    path = Path(temporary)
    repository = path / "fresh-git"
    subprocess.run(["git", "init", "--initial-branch=main", str(repository)], check=True, capture_output=True)
    assert subprocess.check_output(["git", "-C", str(repository), "rev-parse", "--is-inside-work-tree"], text=True).strip() == "true"
    image = path / "synthetic.png"
    Image.new("RGB", (8, 8), "#183650").save(image)
    assert Image.open(image).size == (8, 8)
    store = ConversationStore(path / "explicit-new.sqlite3")
    added = store.create("assistant", "app-assistant", "Synthetic container SDK")
    assert ConversationStore(path / "explicit-new.sqlite3").get(added["id"])["title"] == "Synthetic container SDK"
print(json.dumps({"result": "PASS", "python": sys.version, "pillow": Image.__version__,
                  "ffmpeg": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
                  "git": subprocess.check_output(["git", "--version"], text=True).strip(),
                  "git_effect": "new isolated repository initialized and independently observed",
                  "sdk_effect": "fresh SQLite row read by another store instance", "providers_copied": False}))
