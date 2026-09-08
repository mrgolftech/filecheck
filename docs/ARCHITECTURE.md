# FileCheck V0.1.1 技术架构

## 1. 总体架构

```text
launcher.py
  └─ menu.py / cli.py
       |
       |-- doctor / index
       |     └─ portable_everything.py
       |           ├─ tools\Everything.exe
       |           ├─ tools\es.exe
       |           ├─ dedicated instance: FileCheck
       |           └─ runtime\everything\*
       |
       |-- scan
       |     └─ everything.py
       |           └─ es.exe -argv -> FileCheck Everything IPC
       |
       |-- backup / verify / restore
       |     └─ backup.py
       |           ├─ mirrored directory backup
       |           ├─ manifest validation
       |           ├─ SHA-256 verification
       |           └─ atomic restore
       |
       |-- resumable backup
       |     └─ resumable.py
       |           ├─ operation journal
       |           ├─ per-file copy state
       |           └─ resume + final verify
       |
       |-- remove-sources / remove-resume
       |     └─ migration.py
       |           ├─ full backup verification gate
       |           ├─ whole-source preflight
       |           ├─ per-file immediate recheck
       |           ├─ manifest-only unlink
       |           ├─ source-removal.json
       |           └─ not-deleted.txt
       |
       └─ selftest
             └─ temporary directory backup/delete/restore loop
```

`migrate` / `migrate-resume` 作为高级兼容别名保留，但推荐交互流程把“备份”和“删除”拆成独立阶段。

## 2. 运行目录

正式便携包：

```text
FileCheck\
├─ FileCheck.exe
├─ config\rules.json
├─ tools\Everything.exe
├─ tools\es.exe
├─ runtime\
│  ├─ everything\
│  │  ├─ Everything.ini
│  │  ├─ Everything.db
│  │  └─ index-config.json
│  └─ operations\*.operation.json
└─ scan-results\*.json / *.csv
```

`program_dir()` 作为便携根目录。冻结 EXE 时是 `FileCheck.exe` 所在目录；开发环境可通过 `FILECHECK_HOME` 指定隔离运行目录。

## 3. Portable Everything

### 3.1 专用实例

FileCheck 不复用用户默认 Everything 服务，而是启动：

```text
Everything.exe -instance FileCheck ...
```

ES 查询同一实例。

这样可以让 FileCheck 自己控制：

- 索引范围；
- 排除目录；
- Everything.ini；
- Everything.db；
- 生命周期。

同时不修改用户已有 Everything 配置。

### 3.2 索引配置

`portable_everything.py` 负责：

```text
选择 roots
→ 规范化路径
→ 保存 backup_root
→ 自动加入 program_dir 排除
→ 自动加入 backup_root 排除
→ 写 Everything.ini
→ 启动/重启 FileCheck instance
→ 等待 ES IPC 可用
→ 保存 index-config.json
```

## 4. 扫描架构

Everything 只负责**发现候选路径**，不负责文件性质判定。

```text
rules.json
→ keywords × extensions
→ ES -argv / UTF-8 export
→ path candidates
→ normalize absolute path
→ deduplicate
→ merge matched keywords
→ severity max
→ scan-results.json / CSV
```

默认关键词只匹配文件名；`--match-path` 才包含完整路径。

扫描 JSON 是候选发现记录，不是恢复权威数据。

## 5. 目录备份架构

V0.1.1 的唯一备份格式是目录：

```text
FC-...\
├─ manifest.json
└─ files\
   ├─ C\...
   ├─ D\...
   └─ ...
```

路径映射示例：

```text
D:\Work\A\报告.pdf
→ files\D\Work\A\报告.pdf
```

同名文件不会冲突，因为 `backup_path` 来源于完整源路径结构。

### 5.1 创建事务

```text
collect/deduplicate sources
→ destination space preflight
→ create .FC-....incomplete
→ for each source:
     stat(before)
     → copy source once to temp while calculating SHA-256
     → fsync temp
     → stat(after)
     → reject source mutation
     → os.replace(temp, backup target)
→ write manifest.json
→ verify every payload size + SHA-256
→ os.replace(staging, final FC-* directory)
```

未完成或未通过 verify 的 staging 不发布为正式备份。

### 5.2 manifest

manifest 是恢复的权威映射，记录：

```text
source_path
backup_path
size
mtime_ns
sha256
```

它表示“备份创建时发生了什么”，不表示后续源文件是否被删除，因此 V0.1.1 不再包含 `source_removed`。

## 6. 可续传备份

`resumable.py` 使用独立 operation journal：

```text
runtime\operations\<batch>.operation.json
```

每个 item 记录复制状态。已标记 `copied` 的 staging payload 在 resume 时会重新验证；仍有效则跳过复制，否则回到 `pending`。

只有全部 item 成功并通过最终 verify 才发布正式批次。

## 7. 源文件删除架构

删除状态与 manifest 分离：

```text
FC-...\
├─ manifest.json
├─ source-removal.json
├─ not-deleted.txt       # 仅失败时存在
└─ files\...
```

### 7.1 第一阶段：整批门禁

```text
verify entire backup
→ for every manifest source:
     reject symlink/reparse entry
     require existing regular file
     check size
     hash SHA-256
     check stat stable before/after hash
→ any failure => delete nothing
```

### 7.2 第二阶段：逐文件删除

整批门禁通过且用户确认后：

```text
write initial source-removal.json
→ each item:
     immediate source recheck
     → unlink source_path only
     → checkpoint immediately
     → failure => mark failed and continue
```

不会递归删除父目录，也不会删除 manifest 以外的文件。

### 7.3 Resume

resume 前再次 verify 整个备份，然后：

- 只重试 `pending/failed`；
- 已经消失的失败项可记为 `already_absent`；
- `deleted/already_absent` 路径重新出现时标记 `reappeared`；
- `reappeared` 不自动删除。

这是为了避免把后来创建的新文件误认为原始待删除文件。

## 8. 恢复架构

恢复流程：

```text
read + validate manifest
→ verify entire backup first
→ preflight original Windows drive/share anchors
→ each item:
     choose conflict strategy
     → copy backup payload to target-directory temp
     → fsync
     → verify temp size + SHA-256
     → best-effort mtime
     → os.replace
     → fsync target
     → final size + SHA-256
```

`overwrite` 不会先破坏现有目标；只有临时恢复文件通过校验才替换。

## 9. 旧 ZIP 兼容边界

V0.1.1 不含 ZIP 读取/解压/创建逻辑。

但 `backup.py` 接受**目录输入中的旧 manifest `mode=zip`**：

```text
V0.1.0 ZIP
→ 用户人工完整解压
→ manifest.json + files\
→ V0.1.1 verify / restore
```

因此兼容的是“旧 ZIP 的解压目录”，不是 ZIP 文件本身。

## 10. 数据耐久性

关键写入使用：

- 同目录临时文件；
- flush + `os.fsync`；
- `os.replace`；
- JSON 临时文件原子替换；
- 删除状态逐文件 checkpoint。

这些措施显著降低进程中断/异常造成的数据状态不一致，但不承诺在所有文件系统、掉电、介质故障情况下具有数据库式强原子性。

## 11. 当前支持范围

V0.1.1 主要保证普通文件：

```text
content bytes
absolute source path
mirrored backup path
size
SHA-256
basic mtime
```

不承诺完整恢复：ACL、EFS、ADS、hardlink、sparse、reparse、owner、audit 等高级 NTFS 元数据。

## 12. GUI 后续接入

CLI 先作为稳定业务内核。

后续 GUI 应只包装现有生命周期能力：

```text
index
scan
review
backup
verify
remove/resume
restore
```

GUI 不应重新实现备份、校验或删除算法，而应复用同一 Python core，从而保持 CLI/GUI 行为一致。
