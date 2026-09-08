from __future__ import annotations

from filecheck import menu_layout


def test_main_menu_reorders_backup_resume_and_removes_diagnostic_items(capsys) -> None:
    menu_layout._print_main_menu()
    text = capsys.readouterr().out
    assert "4. 创建目录备份" in text
    assert "5. 继续未完成的备份复制任务" in text
    assert "6. 检查并再次验证备份" in text
    assert "7. 删除源文件 / 继续未完成删除" in text
    assert "8. 恢复备份文件到各自原路径" in text
    assert "9. 运行本机自检" not in text
    assert "10. 显示高级命令帮助" not in text
