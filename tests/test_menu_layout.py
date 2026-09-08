from __future__ import annotations

from filecheck import menu_layout


def test_main_menu_is_compact_and_uses_combined_backup_entry(capsys) -> None:
    menu_layout._print_main_menu()
    text = capsys.readouterr().out
    assert "1. 环境检查与索引创建" in text
    assert "2. 扫描文件列表" in text
    assert "3. 核对扫描结果" in text
    assert "4. 创建备份 / 继续未完成的备份任务" in text
    assert "5. 检查备份" in text
    assert "6. 删除源文件 / 继续未完成的删除任务" in text
    assert "7. 恢复备份文件到源路径" in text
    assert "8." not in text
    assert "9." not in text
    assert "10." not in text


def test_combined_backup_entry_can_create_or_resume(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(menu_layout.menu, "_backup_flow", lambda: calls.append("create") or 0)
    monkeypatch.setattr(menu_layout.menu, "_resume_flow", lambda: calls.append("resume") or 0)

    monkeypatch.setattr(menu_layout.menu, "_ask_choice", lambda *args, **kwargs: "1")
    assert menu_layout._backup_task_flow() == 0
    assert calls == ["create"]

    calls.clear()
    monkeypatch.setattr(menu_layout.menu, "_ask_choice", lambda *args, **kwargs: "2")
    assert menu_layout._backup_task_flow() == 0
    assert calls == ["resume"]
