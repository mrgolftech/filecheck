# FileCheck v0.2.5

v0.2.5 修复了 Windows GUI 删除只读源文件时报 **[WinError 5] 拒绝访问** 的问题。

## 问题根因

- v0.2.4 的 CLI 专用删除实现（`deletion_runtime.py`）已支持删除前清除 Windows READONLY 属性。
- GUI「源文件删除」与「继续未完成删除」实际调用旧版 `migration.py`，直接执行 `Path.unlink()`，没有清除 READONLY 属性。
- Windows `DeleteFile` 遇到只读文件会返回 `ERROR_ACCESS_DENIED`，即使 FileCheck 进程已以管理员身份运行也一样。

## 修复内容

- GUI 和 CLI 复用同一个 `source_delete.unlink_ignoring_readonly()`。
- 已完成备份校验/源文件复核后，删除前只清除只读位；若删除仍失败，则尽可能恢复原只读属性。
- 失败继续记录到原有 `source-removal.json` 和 `not-deleted.txt`，可以用「继续未完成删除」重试。
- 新增 GUI 完整流程测试：只读文件删除、模拟 WinError 5 后属性恢复和失败记录、继续删除成功。

## 安全边界

**本修复仅处理普通只读属性。** 不自动取得文件所有权、不修改 ACL、不强制关闭其他程序占用的文件，也不绕过杀毒软件或 Windows 安全防护。如果仍然提示 WinError 5，请检查 NTFS 删除权限、程序占用、系统/安全软件保护，以及文件所在目录的权限配置。

原有双模式文件扫描、独立 Everything 索引、目录备份、SHA-256 验证和原路径恢复均保留。

## 兼容平台及文件

- `FileCheck-v0.2.5-gui-x64.zip`：Windows 7 SP1 / 10 / 11 64 位 GUI 完整包，内含 CLI。
- `FileCheck-v0.2.5-cli-x64.zip`：Windows 7 SP1 / 10 / 11 64 位 CLI。
- `FileCheck-v0.2.5-cli-x86.zip`：Windows 7 SP1 32 位 CLI。
- `SHA256SUMS-v0.2.5.txt`：三个正式包的 SHA-256 校验值。

构建使用 Python 3.8.10 与 PyInstaller 5.13.2 Windows 7 兼容基线，流水线验证不等同于目标 Windows 7 机器实际运行验收。
