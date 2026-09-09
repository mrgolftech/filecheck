from __future__ import annotations

import re
from pathlib import Path


GUI_DIR = Path(__file__).resolve().parents[1] / "src" / "filecheck" / "gui"
HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}\b")


def _gui_source_files():
    return sorted(path for path in GUI_DIR.glob("*.py") if path.name != "tokens.py")


def test_gui_views_do_not_hardcode_hex_colors() -> None:
    for path in _gui_source_files():
        text = path.read_text(encoding="utf-8")
        matches = HEX_COLOR.findall(text)
        assert not matches, f"{path.name} contains hardcoded colors: {matches}; use Palette tokens instead"


def test_pages_use_shared_button_components() -> None:
    page_files = [GUI_DIR / "pages.py", *sorted(GUI_DIR.glob("*_page.py"))]
    for path in page_files:
        text = path.read_text(encoding="utf-8")
        assert "ctk.CTkButton(" not in text, f"{path.name} must use shared Primary/Secondary/Danger button components"


def test_font_family_is_defined_only_in_tokens() -> None:
    for path in _gui_source_files():
        text = path.read_text(encoding="utf-8")
        assert "Microsoft YaHei UI" not in text, f"{path.name} must reference Typography tokens instead of font names"
