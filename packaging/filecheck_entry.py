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

    # Prefer an editable external rules file next to the executable. This keeps
    # the packaged app practical for real use without hard-coding a private
    # ruleset into the binary.
    external_rules = exe_dir / "config" / "rules.json"
    if external_rules.is_file():
        os.chdir(exe_dir)
    else:
        # A one-file executable also carries the default rules internally. If
        # the external file is missing, materialize one in LOCALAPPDATA so the
        # executable can still start when copied by itself or installed under a
        # non-writable directory such as Program Files.
        local_appdata = os.environ.get("LOCALAPPDATA")
        runtime_root = (
            Path(local_appdata) / "FileCheck"
            if local_appdata
            else exe_dir / "FileCheck-data"
        )
        config_dir = runtime_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        target_rules = config_dir / "rules.json"
        bundled_rules = bundled_root / "config" / "rules.json"
        if not target_rules.exists() and bundled_rules.is_file():
            shutil.copy2(bundled_rules, target_rules)
        os.chdir(runtime_root)

    # Official v0.1.1 portable packages bundle ES beside Everything under the
    # adjacent tools directory.  Record its explicit path before the working
    # directory can change (for example when FileCheck.exe is copied alone).
    adjacent_es = exe_dir / "tools" / "es.exe"
    if adjacent_es.is_file() and not os.environ.get("FILECHECK_ES"):
        os.environ["FILECHECK_ES"] = str(adjacent_es)


_bootstrap_frozen_runtime()

from filecheck.launcher import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
