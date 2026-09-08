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

    # The portable package keeps an editable rules file beside the GUI bundle.
    # Prefer it so CLI and GUI always share exactly the same configuration.
    external_rules = exe_dir / "config" / "rules.json"
    if external_rules.is_file():
        os.chdir(exe_dir)
    else:
        # When the raw PyInstaller onedir output is smoke-tested before package
        # assembly, materialize the embedded default rules into LOCALAPPDATA.
        local_appdata = os.environ.get("LOCALAPPDATA")
        runtime_root = Path(local_appdata) / "FileCheck" if local_appdata else exe_dir / "FileCheck-data"
        config_dir = runtime_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        target_rules = config_dir / "rules.json"
        bundled_rules = bundled_root / "config" / "rules.json"
        if not target_rules.exists() and bundled_rules.is_file():
            shutil.copy2(bundled_rules, target_rules)
        os.chdir(runtime_root)

    adjacent_es = exe_dir / "tools" / "es.exe"
    if adjacent_es.is_file() and not os.environ.get("FILECHECK_ES"):
        os.environ["FILECHECK_ES"] = str(adjacent_es)


_bootstrap_frozen_runtime()

from filecheck.gui.app import FileCheckApp, main  # noqa: E402


def _smoke_test() -> int:
    app = FileCheckApp()
    try:
        app.update_idletasks()
    finally:
        app.destroy()
    return 0


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        raise SystemExit(_smoke_test())
    raise SystemExit(main())
