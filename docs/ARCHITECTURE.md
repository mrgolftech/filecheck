# FileCheck V0.1 技术架构

## 1. 当前实现架构

```text
CLI (cli.py)
  |
  |-- doctor / scan
  |       `--> EverythingAdapter (everything.py)
  |               `--> es.exe -argv --> Everything 1.4 IPC
  |
  |-- backup / verify / restore
  |       `--> BackupEngine (backup.py)
  |               |-- directory backup
  |               |-- ZIP backup
  |               |-- manifest validation
  |               |-- SHA-256 verification
  |               `-- atomic restore
  |
  |-- migrate / migrate-resume
  |       `--> MigrationEngine (migration.py)
  |               |-- backup verification gate
  |               |-- source recheck gate
  |               |-- manifest-only source removal
  |               `-- resumable migration state
  |
  `-- selftest
          `--> isolated temporary backup/migrate/restore loop
```

核心原则：

1. Everything 只负责快速产生候选路径；
2. 扫描、备份、迁移、恢复职责分离；
3. `backup` 永不删除源文件；
4. `migrate` 必须经过完整性门禁后才能移除 manifest 中的源文件；
5. manifest 是恢复权威数据，migration state 是源文件移除过程状态，两者分离。

## 2. Everything 1.4 集成

### 2.1 版本与 IPC

V0.1 要求：

- Everything 1.4.x；
- ES CLI >= 1.1.0.37。

ES 1.1.0.37 的 `-argv` 必须作为第一个 ES 参数，以避免 Python/PowerShell 传递包含空格、引号等查询参数时被旧自定义解析器错误拆分。

Python 使用：

```text
subprocess.run([...], shell=False)
```

禁止拼接 shell 命令字符串。

### 2.2 查询结构

对每一个关键词生成一次查询：

```text
"<keyword>" ext:doc;docx;xls;xlsx;ppt;pptx;pdf;txt;wps;zip;rar;7z;dwg
```

常用 ES 选项：

```text
-argv
-timeout 10000
/a-d
-full-path-and-name
-n <limit>
-s
-path <scan-root>
-p                  # 仅 --match-path 时
```

`-path` 必须在 Everything 侧生效，再由 FileCheck 对返回路径做一次范围防御校验。

## 3. 扫描聚合模型

Everything 每个关键词独立查询，FileCheck 按规范化绝对路径聚合：

```text
normalized absolute path
        ↓
{
  path,
  directory,
  matched_keywords[],
  levels[],
  severity,
  size,
  mtime_ns,
  accessible
}
```

同一文件命中多个词时：

- 结果只保留一条；
- `matched_keywords` 合并；
- `levels` 合并；
- `severity` 取最高级别。

扫描阶段不对所有候选读取正文，也不计算内容 SHA-256，避免破坏 Everything 快速检索优势。

## 4. `scan-results.json`

用途：发现清单/后续批处理输入，不作为恢复依据。

顶层：

```text
schema_version
created_at
engine
everything_version
match_path
path_filter
rules.file
rules.sha256
items[]
```

规则只记录文件名和 SHA-256，不记录规则绝对路径。

候选很多时控制台只显示前 N 条；JSON 保存全部候选。`backup/migrate --from-scan` 默认处理全部 `items`，无需逐文件确认。

## 5. 备份路径映射

Windows 绝对路径映射为备份内部相对路径：

```text
C:\Work\ProjectA\报告.docx
=> files/C/Work/ProjectA/报告.docx

D:\资料\报告.docx
=> files/D/资料/报告.docx
```

因此不同目录下同名文件不会互相覆盖。

UNC 使用 `files/UNC/...` 映射。路径分量经过安全化；若不同源路径映射到相同 `backup_path`，manifest 校验必须拒绝整个批次。

## 6. 备份事务

### 6.1 空间预检

```text
collect files
→ sum(source.size)
→ directory: total + reserve
→ zip: 2 * total + reserve
→ disk_usage(destination)
→ 不足则在 staging 创建前拒绝
```

ZIP 之所以按约 2 倍估算，是因为生成阶段同时存在完整 staging 与临时 ZIP。

### 6.2 单文件复制

```text
source.stat(before)
→ source SHA-256
→ shutil.copy2(source, .part)
→ writable-handle fsync(.part)
→ copied SHA-256
→ source.stat/hash(after)
→ 检测源文件是否变化
→ os.replace(.part, backup target)
→ fsync(target)
```

Windows 对只读文件描述符执行 `os.fsync` 会失败，因此 `_sync_file` 使用可写句柄；若 `copy2` 已复制源只读属性，则临时增加 owner-write，刷盘后恢复原模式。

### 6.3 批次发布

目录：

```text
.FC-<id>.incomplete/
→ files...
→ manifest.json atomic write + fsync
→ verify staging
→ os.replace(staging, FC-<id>)
→ verify final
```

ZIP：

```text
.FC-<id>.incomplete/
→ verify staging
→ .FC-<id>.<uuid>.tmp.zip
→ CRC + manifest + per-entry SHA-256 verify
→ fsync
→ os.replace(..., FC-<id>.zip)
→ final verify
```

任一步失败，清理 incomplete/final partial artifact，不能把失败批次暴露为正式成功备份。

## 7. Manifest

manifest schema v1：

```text
schema_version
batch_id
created_at
mode
source_removed=false          # 创建备份时的状态，不作为迁移进度权威值
source_bytes_total
space_required_estimate
space_free_at_start
items[]
```

每个 item：

```text
source_path
backup_path
size
mtime_ns
sha256
backup_verified
source_removed=false
```

迁移不修改已发布 manifest；源文件移除状态由独立 migration state 记录，避免为了更新状态重新打包 ZIP 或改变已经验证的备份内容。

## 8. Verify

目录备份：

```text
manifest schema/path validation
→ 每个 backup_path 必须位于 files/
→ source_path 必须为绝对路径
→ source/backup 路径不得重复
→ size 验证
→ SHA-256 验证
```

ZIP：

```text
zipfile.testzip() CRC
→ manifest validation
→ member existence
→ member size
→ stream SHA-256
```

恢复和迁移都以 `verify_backup()` 作为前置门禁。

## 9. 恢复事务

```text
verify entire backup
→ Windows 原始驱动器/共享 preflight
→ 对每个 item：
     skip / rename / overwrite conflict resolution
     → 同目录 .filecheck-restore-*.part
     → copy/decompress
     → fsync
     → size + SHA-256
     → best-effort mtime
     → os.replace(temp, target)
     → final SHA-256
```

关键不变量：`overwrite` 在临时恢复副本通过 SHA-256 之前不能修改已有目标。

## 10. 批量迁移事务

### 10.1 阶段一：不可破坏阶段

```text
scan result / explicit sources
→ create_backup
→ verify_backup
→ preflight_migration
     → 全部 source_path 存在且为普通文件
     → size 一致
     → SHA-256 一致
     → hash 前后 stat 一致
```

任一源文件不一致，**整批停止，尚未删除任何源文件**。

### 10.2 阶段二：用户授权

CLI 默认只要求一次批次确认：

```text
files / bytes / backup path
→ 输入 YES
```

`--yes` 仅用于用户明确选择的无人值守场景。

### 10.3 阶段三：manifest-only removal

删除前先写 migration sidecar。之后：

```text
for each manifest item:
    再次即时检查 size + SHA-256 + stat stability
    → unlink(source_path)
    → checkpoint migration state
```

只允许删除 manifest 中逐项列出的文件，不允许对父目录 `rmtree`，不自动删除空目录。

文件锁/权限错误不会触发杀进程或强制解锁；该项标记 `failed`，其他已完成项保留状态。

## 11. Migration state 与断点恢复

sidecar：

```text
FC-xxxx.migration.json
FC-xxxx.zip.migration.json
```

item state：

```text
pending
failed
deleted
already_absent
reappeared
```

`migrate-resume`：

```text
read state
→ verify complete backup again
→ state ↔ manifest batch/files/size/SHA validation
→ 对 pending/failed 重试
→ 已记录 removed 的路径若重新出现：标记 reappeared，不自动删除
→ checkpoint
```

这样避免应用在迁移后重新生成同名文件时，被续跑逻辑误删。

## 12. 故障模型

| 故障 | 策略 |
|---|---|
| 目标空间不足 | staging 前拒绝 |
| 备份盘中途掉线 | 抛错，未完成批次不发布 |
| 源文件备份中变化 | 整批备份失败 |
| 目录/ZIP 被篡改 | verify 拒绝恢复/迁移 |
| ZIP CRC 正常但内容被改 | SHA-256 拒绝 |
| 恢复临时文件损坏 | 不替换现有目标 |
| 源文件备份后被修改 | migrate preflight 整批拒绝删除 |
| 源文件在真正删除前又变化 | 当前 item 不删除，记录 failed |
| 文件被应用占用 | failed，关闭应用后 resume |
| migration 中断 | sidecar checkpoint；resume 重验备份 |
| 已删除路径后来重新出现 | `reappeared`，不自动删除 |

## 13. 当前代码目录

```text
filecheck/
├─ config/
│  └─ rules.json
├─ docs/
│  ├─ REQUIREMENTS.md
│  ├─ ARCHITECTURE.md
│  └─ TEST_PLAN.md
├─ src/filecheck/
│  ├─ __init__.py
│  ├─ backup.py
│  ├─ cli.py
│  ├─ everything.py
│  ├─ migration.py
│  ├─ selftest.py
│  └─ util.py
├─ tests/
│  ├─ test_backup_restore.py
│  ├─ test_cli_bulk.py
│  ├─ test_everything.py
│  ├─ test_migration.py
│  ├─ test_resilience_hardening.py
│  ├─ test_restore_safety.py
│  └─ test_stress.py
└─ .github/workflows/ci.yml
```

## 14. 当前边界

- V0.1 快速扫描主要针对文件名/路径，不是 Office/PDF 正文深度扫描器；
- 空目录不单独保存；
- 不承诺 NTFS ACL、EFS、ADS、硬链接、稀疏文件、重解析点等高级语义；
- ZIP 仅压缩不加密；
- Everything 实机 IPC 无法由普通 CI 模拟，必须在目标 Windows 环境单独验收。
