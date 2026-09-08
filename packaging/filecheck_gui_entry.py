from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _bootstrap_frozen_runtime() -> None:
    if not getattr(sys, "frozen", False):
        return

    exe_dir = Path(sys.executable).resolve().parent
    bundled_root = Path(getattr(sys, "_MEIPASS", exe_dir))

    # Final packages keep the runtime EXE/DLL/PYD files under app\ while
    # config/tools/runtime stay at package root. Raw PyInstaller smoke builds
    # fall back to the onedir itself.
    parent = exe_dir.parent
    if (parent / "config" / "rules.json").is_file() or (parent / "tools").is_dir():
        portable_home = parent
    else:
        portable_home = exe_dir
    os.environ.setdefault("FILECHECK_HOME", str(portable_home))

    external_rules = portable_home / "config" / "rules.json"
    if external_rules.is_file():
        os.chdir(portable_home)
    else:
        local_appdata = os.environ.get("LOCALAPPDATA")
        runtime_root = Path(local_appdata) / "FileCheck" if local_appdata else exe_dir / "FileCheck-data"
        config_dir = runtime_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        target_rules = config_dir / "rules.json"
        bundled_rules = bundled_root / "config" / "rules.json"
        if not target_rules.exists() and bundled_rules.is_file():
            shutil.copy2(bundled_rules, target_rules)
        os.environ["FILECHECK_HOME"] = str(runtime_root)
        os.chdir(runtime_root)

    adjacent_es = Path(os.environ["FILECHECK_HOME"]) / "tools" / "es.exe"
    if adjacent_es.is_file() and not os.environ.get("FILECHECK_ES"):
        os.environ["FILECHECK_ES"] = str(adjacent_es)
    adjacent_everything = Path(os.environ["FILECHECK_HOME"]) / "tools" / "Everything.exe"
    if adjacent_everything.is_file() and not os.environ.get("FILECHECK_EVERYTHING"):
        os.environ["FILECHECK_EVERYTHING"] = str(adjacent_everything)


_bootstrap_frozen_runtime()

from filecheck.gui.entry import create_app, main  # noqa: E402


def _smoke_test() -> int:
    # Construct through the real GUI entry so administrator detection, theme
    # loading, runtime policy and backup-batch selectors are exercised in the
    # packaged executable as well as in source tests.
    app = create_app()
    try:
        app.update_idletasks()
    finally:
        app.destroy()
    return 0


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        raise SystemExit(_smoke_test())
    raise SystemExit(main())
