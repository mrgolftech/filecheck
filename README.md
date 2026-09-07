# FileCheck

FileCheck 是一个面向 Windows 终端的离线文件自查、批量备份、可靠迁移和原路径恢复工具。

> **当前安全策略：只读扫描 → 批量备份 → 全量 SHA-256 验证 → 源文件再次复核 → 一次批次确认 → 可选移除源文件。**
>
> `backup` 永远不移除源文件；只有显式执行 `migrate` 才会进入源文件移除阶段。程序不提供 Recent、浏览器历史、USBSTOR、注册表 MRU 等“清痕”功能。

## 已实现

- 复用 **Everything 1.4 已有索引**，不创建 FileCheck 自有全盘索引，也不默认触发 `-reindex`。
- 使用 ES CLI 1.1.0.37+（`-argv`）按“**一个关键词 + 全部目标扩展名**”查询文件名；可选匹配完整路径。
- 指定盘符/目录时使用 ES `-path` 在 Everything 端先限定范围，再执行结果数量限制。
- 扫描结果按完整绝对路径去重；同一文件命中多个关键词时合并命中原因并取最高风险级别。
- 候选很多时控制台默认只显示前 100 个，完整结果全部写入 `scan-results.json`。
- `backup --from-scan` **默认批量处理扫描结果中的全部候选**，不要求逐个确认；`--select` 仅作为可选高级过滤。
- 不把不同来源的同名文件拍平到一个目录，而是映射原始绝对路径，例如 `C:\A\报告.docx -> files/C/A/报告.docx`。
- 支持目录备份和 ZIP 备份。
- 每个备份文件记录原始绝对路径、备份相对路径、大小、mtime、SHA-256。
- 备份前检查目标剩余空间；ZIP 模式按“完整 staging + 临时 ZIP”进行保守估算。
- 正式批次发布前使用 `.FC-....incomplete` 暂存，失败时不留下看似成功的正式批次。
- 文件与 JSON manifest 在发布前刷盘；Windows 使用可写句柄执行 `fsync`，兼容只读源文件复制后的属性。
- 备份完成后逐文件执行大小 + SHA-256 全量复核；ZIP 同时检查 CRC 与逐文件 SHA-256。
- 恢复前先验证整个备份集；恢复先写同目录临时文件、校验成功后再 `os.replace` 原子落盘。
- 恢复冲突策略：`skip` / `overwrite` / `rename`。
- `migrate` 在删除前重新验证整个备份，并再次 SHA-256 复核全部源文件。
- 源文件移除只针对 `manifest.items[].source_path`，**不会递归删除整个目录，也不会自动删除空目录**。
- 若部分文件被占用/无权限，记录 `.migration.json` 状态；关闭占用程序或修正权限后可 `migrate-resume`。
- `migrate-resume` 每次都会重新验证备份；已移除路径若后来重新出现，不自动删除，防止误删新数据。
- 自带 `selftest`，覆盖目录/ZIP 的备份、验证、迁移、恢复回环。

## 主流程

```text
Everything 1.4 快速扫描
        ↓
scan-results.json
        ↓
全部候选批量备份（默认）
        ↓
逐文件 SHA-256 + 整批 verify
        ↓
┌───────────────────────────────┐
│ backup：到此结束，源文件不动 │
└───────────────────────────────┘
        或
        ↓
┌──────────────────────────────────────────────┐
│ migrate：全部源文件再次 SHA-256 复核        │
│          ↓                                   │
│          一次批次级 YES 确认                 │
│          ↓                                   │
│          仅移除 manifest 中列出的源文件       │
│          ↓                                   │
│          保存 migration state，可断点继续     │
└──────────────────────────────────────────────┘
```

## 安装开发版

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

ES CLI 可放在：

1. `tools/es.exe`
2. 系统 `PATH`
3. 环境变量 `FILECHECK_ES`
4. Everything 常见安装目录

Everything 本体需要已启动并完成索引。V0.1 要求 Everything 1.4.x 和 ES CLI 1.1.0.37+。

## 使用

### 1. 环境检查

```powershell
filecheck doctor
```

### 2. 快速扫描

```powershell
filecheck scan --path D:\ --output scan-results.json
```

关键词也匹配完整目录路径：

```powershell
filecheck scan --path D:\ --match-path --output scan-results.json
```

大量结果时只显示汇总：

```powershell
filecheck scan --path D:\ --list-limit 0 --output scan-results.json
```

当前规则在 `config/rules.json`。每个关键词会构造成类似：

```text
"机密" ext:doc;docx;xls;xlsx;ppt;pptx;pdf;txt;wps;zip;rar;7z;dwg
```

### 3. 批量备份扫描结果中的全部候选

```powershell
filecheck backup --from-scan scan-results.json --dest X:\FileCheckBackup
```

ZIP：

```powershell
filecheck backup --from-scan scan-results.json --dest X:\FileCheckBackup --zip
```

如果确实只想处理部分候选，仍可使用：

```powershell
filecheck backup --from-scan scan-results.json --select 1,3-5 --dest X:\FileCheckBackup
```

也可以直接备份指定文件/目录：

```powershell
filecheck backup D:\Work\ProjectA --dest X:\FileCheckBackup
```

### 4. 批量迁移：备份验证后移除源文件

```powershell
filecheck migrate --from-scan scan-results.json --dest X:\FileCheckBackup
```

程序依次执行：

```text
创建备份
→ 全量 verify
→ 全部源文件再次 size + SHA-256 复核
→ 显示批次汇总
→ 要求输入 YES 一次确认
→ 逐文件再次即时复核后 unlink
→ 保存迁移状态
```

明确的无人值守场景可使用：

```powershell
filecheck migrate --from-scan scan-results.json --dest X:\FileCheckBackup --yes
```

ZIP 迁移：

```powershell
filecheck migrate --from-scan scan-results.json --dest X:\FileCheckBackup --zip
```

如果有文件因占用或权限问题未能移除：

```powershell
filecheck migrate-resume "X:\FileCheckBackup\FC-xxxx.migration.json"
```

ZIP 的状态文件名类似：

```text
FC-xxxx.zip.migration.json
```

### 5. 独立验证备份

```powershell
filecheck verify X:\FileCheckBackup\FC-xxxx
filecheck verify X:\FileCheckBackup\FC-xxxx.zip
```

### 6. 原路径恢复

```powershell
filecheck restore X:\FileCheckBackup\FC-xxxx --conflict skip
```

需要覆盖已有文件时：

```powershell
filecheck restore X:\FileCheckBackup\FC-xxxx --conflict overwrite
```

`overwrite` 也会先写临时文件并完成 SHA-256 校验，最后才替换现有目标。

### 7. 自检

```powershell
filecheck selftest
```

## 运行产物

### `scan-results.json`

扫描候选清单。主要包含：

- 扫描时间、Everything 版本、扫描范围；
- `rules.file`：规则文件名；
- `rules.sha256`：本次规则文件 SHA-256，不保存规则文件绝对路径；
- 每个候选的完整路径、目录、命中关键词、风险级别、大小、mtime、可访问状态。

扫描阶段不对全部候选计算内容 SHA-256，以保持 Everything 快速扫描优势。

### `manifest.json`

备份/恢复的权威清单。每个文件包含：

- `source_path`
- `backup_path`
- `size`
- `mtime_ns`
- `sha256`

同名文件依靠 `source_path -> backup_path` 路径映射区分。

### `*.migration.json`

迁移源文件移除状态，记录：

- 对应 backup/batch；
- 每个源文件的 size/SHA-256；
- `pending / deleted / already_absent / failed / reappeared` 状态；
- 失败原因；
- 汇总计数。

migration state 与备份 manifest 分离，不修改已经验证发布的备份内容。

## 自动化测试

```powershell
python -m pytest -q
```

CI 矩阵：

- Windows latest + Python 3.10
- Windows latest + Python 3.12
- Ubuntu latest + Python 3.10
- Ubuntu latest + Python 3.12

每个平台同时执行单元/故障注入/压力测试和 `filecheck selftest`。真实 Everything IPC 仍需在安装 Everything 的 Windows 目标机验收。

## 安全边界与已知限制

- 关键词命中仅代表候选，不自动认定文件性质。
- `scan` 和 `backup` 都不会删除源文件；只有显式 `migrate` 会进入源文件移除流程。
- 不杀进程、不强制解锁；占用文件留在原位置并写入迁移状态，关闭应用后重试。
- 不清理 Recent、浏览器历史、USBSTOR、Office/WPS MRU、注册表等记录。
- 扫描结果、真实文件名/路径、manifest、migration state、备份包均可能包含敏感运行信息，不应提交 Git 或随意外发。
- ZIP 是压缩格式，不是加密格式。
- 当前可靠性承诺是普通文件内容、原始绝对路径、大小、基本 mtime 和 SHA-256；NTFS ACL、EFS、ADS、硬链接、稀疏文件、重解析点等高级文件系统语义暂不作为恢复承诺。
- 空目录不会单独备份或恢复；迁移也不会自动删除空目录。

## 文档

- `docs/REQUIREMENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/TEST_PLAN.md`
