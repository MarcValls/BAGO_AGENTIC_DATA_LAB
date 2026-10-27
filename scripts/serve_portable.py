"""Start this ADL source copy with its own portable application data."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def portable_development_profile(value: str | Path) -> Path:
    """Resolve a migrated profile inside owned data without rewriting it."""
    from src.storage.portable import data_path, data_root

    root = data_root().resolve(strict=False)
    candidate = Path(value).expanduser().absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        raise ValueError("An explicitly migrated development profile must be inside portable data.") from None
    if not relative.parts:
        raise ValueError("A development profile file is required.")
    resolved = data_path(*relative.parts)
    try:
        info = resolved.lstat()
    except OSError:
        raise ValueError("The portable development profile is unavailable.") from None
    if not resolved.is_file() or info.st_nlink != 1:
        raise ValueError("The portable development profile must be a regular, unlinked file.")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("BAGO_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("BAGO_API_PORT") or "8098"))
    parser.add_argument("--data-root", type=Path, default=None,
                        help="explicit portable data root; otherwise <application>/.bago/data")
    parser.add_argument("--development-profile", type=Path, default=None,
                        help="explicit profile file already migrated inside portable data; its target/root permissions are not rewritten")
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    app_root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("BAGO_APP_ROOT", str(app_root))
    if arguments.data_root is not None:
        os.environ["BAGO_DATA_ROOT"] = str(arguments.data_root.expanduser().absolute())
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    from src.storage.portable import data_path, storage_status
    profile_mode = "configured_host_profile" if os.environ.get("BAGO_DEVELOPMENT_PROFILE") else "not_configured"
    if arguments.development_profile is not None:
        try:
            selected_profile = portable_development_profile(arguments.development_profile)
        except ValueError as error:
            parser.error(str(error))
        os.environ["BAGO_DEVELOPMENT_PROFILE"] = str(selected_profile)
        profile_mode = "explicit_migrated_profile"
    # This is an owned GEX database location, not a project root or authority target.
    os.environ.setdefault("BAGO_GEX_IDENTITY_DB_PATH", str(data_path("gex", "identity.sqlite3")))
    os.environ["BAGO_API_HOST"] = arguments.host
    os.environ["BAGO_API_PORT"] = str(arguments.port)

    print("BAGO portable runtime", flush=True)
    print({**storage_status(), "development_profile_mode": profile_mode}, flush=True)
    import uvicorn
    uvicorn.run("src.api.server:app", host=arguments.host, port=arguments.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
