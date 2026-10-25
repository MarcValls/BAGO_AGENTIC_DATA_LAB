"""Install the distribution in a disposable directory and invoke it outside ADL."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="document-toolkit-installed-") as temporary:
    target = Path(temporary) / "installed"
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--no-build-isolation",
                    "--target", str(target), str(repo / "tools/document-toolkit")], check=True,
                   capture_output=True, text=True, timeout=60)
    source = Path(temporary) / "corpus"; source.mkdir()
    (source / "synthetic.txt").write_text("FAC-TEST EUR 20.00", encoding="utf8")
    env = dict(os.environ, PYTHONPATH=str(target))
    proc = subprocess.run([sys.executable, "-m", "document_toolkit", "extract", "--root", str(source)],
                          cwd=temporary, env=env, capture_output=True, text=True, encoding="utf8", timeout=10, check=True)
    result = json.loads(proc.stdout)
    assert result["state"] == "EXECUTED", result
    assert result["records"][0]["segments"][0]["text"] == "FAC-TEST EUR 20.00"
    probe = subprocess.run([sys.executable, "-c", "import document_toolkit,json;print(json.dumps(document_toolkit.__file__))"],
                           cwd=temporary, env=env, capture_output=True, text=True, check=True)
    assert Path(json.loads(probe.stdout)).is_relative_to(target)
    print(json.dumps({"result": "PASS", "installed_outside_repository": True,
                      "invocation": "python -m document_toolkit extract", "synthetic_files": 1}))
