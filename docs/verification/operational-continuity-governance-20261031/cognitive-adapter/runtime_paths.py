from pathlib import Path

def skill_root(path):
    path = Path(path).resolve(strict=True)
    if (path / "PACKAGE_IDENTITY.json").is_file():
        return path
    if (path / "skill/PACKAGE_IDENTITY.json").is_file():
        return path / "skill"
    raise ValueError("missing installed Suite identity")
