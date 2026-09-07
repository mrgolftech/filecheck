# FileCheck

FileCheck 是一个面向 Windows 终端的离线文件自查、人工复核、备份与原路径恢复工具。

> **V0.1 安全策略：只读扫描 + 复制备份 + 全量校验 + 恢复。暂不自动移除源文件。**
>
> 原因很简单：在真实 Windows + Everything 1.4 环境完成多轮恢复演练以前，不把“移出原文件”加入第一版。文件恢复可靠性优先于功能完整度。

## V0.1 已实现

- 复用 **Everything 1.4 已有索引**，不创建 FileCheck 自有全盘索引，也不默认触发 `-reindex`。
- 使用 ES CLI（`es.exe`）按关键词 + 扩展名快速搜索文件名；可选匹配完整路径。
- 扫描指定盘符/目录时使用 ES `-path` 在 Everything 端先限定范围，再进行结果数量限制，避免大索引下漏掉目标目录结果。
- Everything 返回的候选即使暂时不可访问也保留在扫描结果中，并标记 `accessible=false`，避免静默漏项。
- 支持从扫描结果按编号选择文件，或直接指定文件/目录备份。
- 支持目录备份和 ZIP 备份。
- 每个文件记录：原始绝对路径、大小、修改时间、SHA-256、备份相对路径。
- 复制时检测源文件是否在备份过程中发生变化。
- 备份完成后执行逐文件 **大小 + SHA-256** 全量复核；ZIP 同时执行 CRC 和逐文件 SHA-256，不只依赖 ZIP 自身 CRC。
- 恢复开始前先验证**整个备份集**，发现任意一项损坏时不开始写入原路径。
- 恢复先写同目录临时文件并验证 SHA-256，再通过 `os.replace` 原子落盘；`overwrite` 也不会在恢复副本验证前覆盖已有文件。
- 支持恢复冲突策略：`skip` / `overwrite` / `rename`。
- 自带 `selftest`，在临时目录执行目录备份、ZIP 备份、删除测试副本、原路径恢复及冲突策略回环测试。

## 安装开发版

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

ES CLI 可放在以下任一位置：

1. `tools/es.exe`
2. 系统 `PATH`
3. 环境变量 `FILECHECK_ES`
4. Everything 常见安装目录

Everything 本体需要已启动并加载索引。

## 使用

先检查 Everything 环境：

```powershell
filecheck doctor
```

快速扫描：

```powershell
filecheck scan --path D:\ --output scan-results.json
```

如果关键词也需要匹配目录路径：

```powershell
filecheck scan --path D:\ --match-path --output scan-results.json
```

从扫描结果选择候选项进行目录备份：

```powershell
filecheck backup --from-scan scan-results.json --select 1,3-5 --dest X:\FileCheckBackup
```

ZIP 备份：

```powershell
filecheck backup --from-scan scan-results.json --select 1,3-5 --dest X:\FileCheckBackup --zip
```

再次独立验证备份：

```powershell
filecheck verify X:\FileCheckBackup\FC-xxxx
filecheck verify X:\FileCheckBackup\FC-xxxx.zip
```

恢复：

```powershell
filecheck restore X:\FileCheckBackup\FC-xxxx --conflict skip
```

本机备份/恢复回环自检：

```powershell
filecheck selftest
```

## 自动化测试

```powershell
python -m pytest -q
```

CI 在 Windows / Ubuntu、Python 3.10 / 3.12 上同时运行单元测试和 `filecheck selftest`。真实 Everything 1.4 的 IPC/索引联调仍必须在装有 Everything 的 Windows 机器进行，详见 `docs/TEST_PLAN.md`。

## 关键安全边界

- V0.1 **不会自动删除或移动原文件**。
- 不清理 Recent、浏览器历史、USBSTOR、注册表等记录。
- 不根据关键词自动认定文件性质；所有候选必须人工复核。
- 扫描结果、真实文件名、路径、主机名、manifest 和备份包属于运行数据，不得提交到 Git 仓库。
- V0.1 以“普通文件内容完整恢复”为可靠性目标；NTFS ACL、EFS、备用数据流（ADS）、硬链接等文件系统高级元数据暂不作为恢复承诺范围。

## 文档

- `docs/REQUIREMENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/TEST_PLAN.md`
