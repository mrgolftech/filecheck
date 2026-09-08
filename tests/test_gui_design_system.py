from __future__ import annotations

import re
from pathlib import Path


GUI_DIR = Path(__file__).resolve().parents[1] / "src" / "filecheck" / "gui"
HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}\b")


def test_gui_views_do_not_hardcode_hex_colors() -> None:
    for name in ("app.py", "components.py", "pages.py"):
        text = (GUI_DIR / name).read_text(encoding="utf-8")
        matches = HEX_COLOR.findall(text)
        assert not matches, f"{name} contains hardcoded colors: {matches}; use Palette tokens instead"


def test_pages_use_shared_button_components() -> None:
    text = (GUI_DIR / "pages.py").read_text(encoding="utf-8")
    assert "ctk.CTkButton(" not in text, "pages must use shared Primary/Secondary/Danger button components"


def test_font_family_is_defined_only_in_tokens() -> None:
    for name in ("app.py", "components.py", "pages.py"):
        text = (GUI_DIR / name).read_text(encoding="utf-8")
        assert "Microsoft YaHei UI" not in text, f"{name} must reference Typography tokens instead of font names"
