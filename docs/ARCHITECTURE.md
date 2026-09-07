# FileCheck V0.1 技术架构

## 1. 总体架构

```text
UI / CLI
  |
  v
Application Service
  |-- ScanService
  |-- ReviewService
  |-- BackupService
  |-- RestoreService
  |
  +--> SearchEngine
  |      |-- EverythingSearchEngine
  |      `-- NativeSearchEngine
  |
  +--> RuleEngine
  |
  +--> BackupRepository
  |      |-- DirectoryBackup
  |      `-- ZipBackup
  |
  `--> ManifestRepository
```

核心原则：搜索引擎与备份/恢复逻辑解耦。Everything 只负责高速产生候选路径，后续处理不依赖 Everything。

## 2. Everything 1.4 集成

V0.1 使用官方 ES CLI 与 Everything 1.4 IPC 通信，不直接操作 Everything 数据库文件。

### 2.1 调用方式

Python 使用 `subprocess.run()` 调用 `es.exe`，参数使用列表形式传入，禁止拼接 `shell=True` 命令字符串。

示意：

```python
subprocess.run(
    [es_path, query],
    capture_output=True,
    text=True,
    check=False,
)
```

需要处理：

- `es.exe` 不存在；
- Everything 未运行；
- IPC 不可用；
- 查询超时；
- 中文路径编码；
- 大量结果；
- 重复结果；
- 路径在查询后被删除或移动。

### 2.2 查询构造

不要把业务规则散落在调用代码中。使用 `EverythingQueryBuilder` 根据：

- keywords
- extensions
- roots
- excludes

生成 Everything 查询。

返回结果统一转换为内部 `SearchHit` 模型。

## 3. 数据模型

### SearchHit

```text
path
name
parent
matched_keywords
priority
size
mtime_ns
engine
```

### ReviewDecision

```text
path
decision = keep | review | backup_file | backup_directory
note
```

### BackupItem

```text
source_path
backup_relative_path
size
sha256
mtime_ns
matched_keywords
status
```

### BackupBatch

```text
batch_id
created_at
mode
backup_root
items[]
```

## 4. “记录目录”逻辑

不能因为某个文件命中关键词就自动迁移其整个目录。

系统只做建议：

- 同目录仅 1 个候选文件：建议单文件处理；
- 同目录候选文件达到可配置阈值：UI 显示“建议按目录检查/备份”；
- 用户选择目录后，记录 `selected_root`，并为每个实际备份文件记录相对于该根目录的路径。

这样既能保持目录结构，也避免误把大量无关文件扩大到备份范围。

## 5. 备份路径映射

为了能无歧义恢复，Windows 绝对路径映射为备份相对路径。

例如：

```text
D:\work\project\a.docx
=> files\D\work\project\a.docx
```

UNC 路径后续可设计为：

```text
\\server\share\folder\a.docx
=> files\UNC\server\share\folder\a.docx
```

V0.1 如不支持 UNC，应明确阻止而不是静默处理。

## 6. 备份事务

单文件备份：

```text
读取源元数据
 -> 计算源 SHA-256
 -> 复制到临时目标
 -> 计算目标 SHA-256
 -> 比较一致
 -> 原子重命名为正式文件
 -> 写 manifest
```

批量备份过程中失败：

- 已成功项保持 `verified`；
- 失败项记录 `failed` 与错误码；
- 不自动删除源文件；
- manifest 始终可以反映实际状态。

## 7. ZIP 打包

建议先将文件复制并校验到临时批次目录，再生成 ZIP，避免直接一边读取源文件一边打包导致无法独立验证。

流程：

```text
source
 -> staging/files/...
 -> SHA-256 verify
 -> manifest.json
 -> batch.zip.tmp
 -> verify zip entries / manifest
 -> batch.zip
```

压缩仅用于便于搬运，不等同于加密。若后续需要加密备份，应单独设计密码学方案。

## 8. 恢复策略

恢复前必须验证：

- manifest schema；
- 备份文件存在；
- SHA-256 一致；
- 原路径是否合法；
- 目标是否已存在。

冲突策略必须由用户选择：

- skip
- rename
- overwrite

默认 `skip`，禁止默认覆盖。

## 9. 推荐目录

```text
filecheck/
├─ README.md
├─ pyproject.toml
├─ docs/
│  ├─ REQUIREMENTS.md
│  └─ ARCHITECTURE.md
├─ src/filecheck/
│  ├─ app/
│  ├─ search/
│  │  ├─ base.py
│  │  ├─ everything.py
│  │  └─ native.py
│  ├─ rules/
│  ├─ backup/
│  ├─ restore/
│  ├─ manifest/
│  └─ models/
├─ config/
│  └─ rules.example.yaml
├─ tests/
└─ tools/
```

`tools/es.exe` 不直接提交，是否随发布包分发需按官方许可和发布策略确定。

## 10. 开发顺序

1. Everything 能力检测；
2. QueryBuilder；
3. ES 查询 -> `SearchHit`；
4. 关键词/扩展名配置；
5. CLI 输出候选文件；
6. 目录聚合与人工选择数据模型；
7. Directory backup + SHA-256；
8. Manifest；
9. Restore；
10. ZIP backup；
11. 自动测试；
12. PySide6 GUI。
