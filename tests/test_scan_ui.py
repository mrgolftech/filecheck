from __future__ import annotations

import json
from pathlib import Path

from filecheck import cli, scan_ui


def test_print_scan_rules_shows_keywords_extensions_and_config_path(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    rules_path = tmp_path / "config" / "rules.json"
    rules_path.parent.mkdir(parents=True)
    rules_path.write_text(
        json.dumps(
            {
                "keywords": {
                    "high": ["绝密", "机密"],
                    "sensitive": ["密码"],
                    "review": ["报告"],
                },
                "extensions": ["docx", "pdf", ".txt"],
                "max_results_per_keyword": 1000,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "_default_rules_path", lambda: str(rules_path))

    scan_ui._print_scan_rules()
    text = capsys.readouterr().out

    assert "当前扫描规则" in text
    assert "high: 绝密, 机密" in text
    assert "sensitive: 密码" in text
    assert "review: 报告" in text
    assert "文件扩展名: .docx, .pdf, .txt" in text
    assert str(rules_path.resolve()) in text
    assert "config\\rules.json" in text
    assert "重新执行扫描" in text
