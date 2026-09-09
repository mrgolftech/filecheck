# FileCheck v0.2.1

FileCheck v0.2.1 是针对 v0.2.0 的路径兼容性修复版本，建议所有使用 GUI 或 CLI 执行备份/恢复的用户升级。

## 修复：Windows 7 深层目录备份可能报 `[Errno 2]`

v0.2.0 在备份时为了保证原子落盘，会先在目标文件同目录创建临时文件。旧临时文件名会重复完整原文件名并附加 32 位 UUID，例如：

```text
.新建文本文档.txt.65738f732c5e459ebdb471a472b7c935.part
```

当原始目录层级较深时，正式备份目标路径本身仍低于传统 Windows `MAX_PATH`，但临时文件名额外增加的长度可能把完整路径推到 260 字符附近，从而在 Windows 7 上表现为：

```text
[Errno 2] No such file or directory
```

v0.2.1 将备份和恢复的原子临时文件统一改为固定长度的短名称，例如：

```text
.fc-b-65738f732c5e459e.part
.fc-r-0123456789abcdef.part
```

临时文件仍位于最终目标同一目录，因此原子替换、SHA-256 校验和异常清理语义不变。

针对实际报告案例，最终备份文件路径长度为 221 字符；旧临时路径正好达到 260 字符；新临时路径缩短为 238 字符。

## 回归测试

本版本新增专门的路径回归测试：

- 使用实际报错路径验证旧临时路径为 260 字符、新路径为 238 字符；
- 验证备份原子复制确实使用短临时文件名，并在完成后正确清理；
- 验证恢复流程同样不再重复原始文件名；
- 新增版本一致性测试，确保 `pyproject.toml` 与运行时 `filecheck.__version__` 不再出现版本号不一致。

正式发布仍通过 Python 3.8.10 Win7 兼容构建链，并重新执行完整回归、GUI/CLI 打包、EXE smoke test、ZIP 内容验证和 SHA-256 生成。

## 发布包

- `FileCheck-v0.2.1-gui-x64.zip` — GUI 完整版，Windows 7 SP1 / 10 / 11 64 位，推荐普通用户使用；包内含 x64 CLI。
- `FileCheck-v0.2.1-cli-x64.zip` — Windows 7 SP1 / 10 / 11 64 位 CLI。
- `FileCheck-v0.2.1-cli-x86.zip` — Windows 7 SP1 32 位 CLI。
- `SHA256SUMS-v0.2.1.txt` — 三个正式 ZIP 的 SHA-256 校验值。

备份格式、`manifest.json` schema、Everything 专用数据库以及现有 v0.2.0 备份批次均保持兼容，不需要迁移已有备份。
